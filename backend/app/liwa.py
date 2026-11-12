"""Liwa: the inspection planner in FirstLook. Retrieval-augmented, and local. No prompt box.

Whenever the picture changes (a new storm or interruption, a field result, a repair), Liwa
writes the inspection plan: which places to check, in what order, and why.

    reference documents            the storm as it stands
    (backend/reference/*.md)       (barangays, places, messages)
            \\                            /
             v                          v
        SQLite database  ->  vector search (sqlite-vec)  +  keyword search (FTS5)
                                   |
                                   |  the guidance that fits this situation, plus the candidates
                                   v
        Claude Opus 5.5, run through the Claude Code CLI on this machine's login
                                   |
                                   v
        inspection plan: ordered places, a reason for each, the guidance it rests on

The reference documents decide the ranking. Until some are added, the only reference is
FirstLook's built-in rule (safety, then essential facilities, then homes), and the plan keeps
the engine's own order.

Storage is one SQLite file (backend/.cache/firstlook.db):
    doc        every record: the storm's (rebuilt as it changes) and the reference chunks
    doc_fts    full-text index over doc (kept in step by triggers)
    doc_vec    one embedding per record (sqlite-vec, cosine distance)
    embedding  cache of vectors by content hash, so unchanged records are never re-embedded
    plan       log of every plan written: when, by what, the order, the references used

The generator is the `claude` command in print mode. It uses whatever account Claude Code is
signed in to, and this module removes any ANTHROPIC_* variables from its environment so an API
key can never be picked up and billed. If the command is missing, signed out or slow, the plan
is the engine's own order with the engine's own reasons, and says so.

Liwa only advises. It cannot dispatch, repair or send anything.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import threading
import time
from pathlib import Path

import numpy as np

from . import knowledge

BACKEND = Path(__file__).resolve().parent.parent
CACHE = BACKEND / ".cache"
REFERENCE = Path(os.environ.get("FIRSTLOOK_REFERENCE") or BACKEND / "reference")
DIM = 384
EMBED_MODEL = "BAAI/bge-small-en-v1.5"
CLAUDE_MODEL = os.environ.get("FIRSTLOOK_LIWA_MODEL", "claude-opus-5-5")
CLAUDE_TIMEOUT = 90
MAX_CANDIDATES = 8          # places Claude ranks; any beyond these keep the engine's order after them
SCHEMA_VERSION = "2"
GROUP = {"note": 0, "message": 1, "reference": 2}        # what a search looks through
STOP = set("""a an the is are was were be been do does did can could would should will what when where which who why how
any some there here this that these those it its of in on at to for from with about and or not no we you i me my our us they
them have has had tell show give know get got please now many much more most than then so if into po ba ang ng sa mga may
ano saan bakit ilan sino kailan paano""".split())
NAME_NOISE = set("power line along switch transformer pole on in at near and to the of hwy ave blvd rd dr st gen brgy "
                 "interchange i ii iii 1 2".split())
EQUIPMENT = ("transformer", "switch", "pole", "line")

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS doc (
    id         INTEGER PRIMARY KEY,
    storm      TEXT NOT NULL,             -- the storm's id, or 'reference' for the reference documents
    kind       TEXT NOT NULL CHECK (kind IN ('topic', 'place', 'barangay', 'city', 'advisory', 'message', 'reference')),
    ref        TEXT NOT NULL,
    title      TEXT NOT NULL,
    body       TEXT NOT NULL,
    link_kind  TEXT CHECK (link_kind IN ('area', 'priority', 'report')),
    link_id    TEXT,
    digest     TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (storm, kind, ref)
);
CREATE INDEX IF NOT EXISTS doc_digest ON doc (digest);
CREATE VIRTUAL TABLE IF NOT EXISTS doc_fts USING fts5(title, body, content = 'doc', content_rowid = 'id',
                                                      tokenize = 'unicode61 remove_diacritics 2');
CREATE TRIGGER IF NOT EXISTS doc_ai AFTER INSERT ON doc BEGIN
    INSERT INTO doc_fts (rowid, title, body) VALUES (new.id, new.title, new.body);
END;
CREATE TRIGGER IF NOT EXISTS doc_ad AFTER DELETE ON doc BEGIN
    INSERT INTO doc_fts (doc_fts, rowid, title, body) VALUES ('delete', old.id, old.title, old.body);
END;
CREATE TRIGGER IF NOT EXISTS doc_au AFTER UPDATE OF title, body ON doc BEGIN
    INSERT INTO doc_fts (doc_fts, rowid, title, body) VALUES ('delete', old.id, old.title, old.body);
    INSERT INTO doc_fts (rowid, title, body) VALUES (new.id, new.title, new.body);
END;
CREATE VIRTUAL TABLE IF NOT EXISTS doc_vec USING vec0(embedding float[{DIM}] distance_metric = cosine, grp integer);
CREATE TABLE IF NOT EXISTS embedding (
    digest TEXT NOT NULL,
    model  TEXT NOT NULL,
    vector BLOB NOT NULL,
    PRIMARY KEY (digest, model)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS plan (
    id          INTEGER PRIMARY KEY,
    storm       TEXT NOT NULL,
    made_at     TEXT NOT NULL DEFAULT (datetime('now')),
    generator   TEXT NOT NULL,
    steps       TEXT NOT NULL,            -- JSON: asset ids in plan order
    refs        TEXT NOT NULL,            -- JSON: reference records the plan was given
    retrieve_ms INTEGER NOT NULL,
    generate_ms INTEGER NOT NULL
);
"""


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------
class HashEmbedder:
    """No model, no download: words and character trigrams hashed into a fixed-size vector.
    Matches wording rather than meaning. Used in tests and when the real model cannot load."""
    name = f"hash-{DIM}"

    def embed(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), DIM), dtype=np.float32)
        for row, text in enumerate(texts):
            words = re.findall(r"[a-z0-9ñ]+", text.lower())
            grams = [w for w in words if w not in STOP] + [w[i:i + 3] for w in words for i in range(max(len(w) - 2, 0))]
            for g in grams:
                h = int.from_bytes(hashlib.blake2b(g.encode(), digest_size=8).digest(), "little")
                out[row, h % DIM] += 1.0 if (h >> 32) & 1 else -1.0
        norms = np.linalg.norm(out, axis=1, keepdims=True)
        return out / np.where(norms == 0, 1, norms)

    embed_query = embed


class ModelEmbedder:
    """BAAI/bge-small-en-v1.5 run locally with ONNX (67 MB, downloaded once into backend/.cache/models)."""
    name = EMBED_MODEL

    def __init__(self):
        from fastembed import TextEmbedding
        self.model = TextEmbedding(EMBED_MODEL, cache_dir=str(CACHE / "models"), threads=2)

    def embed(self, texts: list[str]) -> np.ndarray:
        return np.asarray(list(self.model.embed(texts, batch_size=32)), dtype=np.float32)

    def embed_query(self, texts: list[str]) -> np.ndarray:
        return np.asarray(list(self.model.query_embed(texts)), dtype=np.float32)


_embedder = None
_embedder_lock = threading.Lock()


def embedder():
    """The embedding model, loaded once. FIRSTLOOK_EMBED=hash skips the model (tests, tiny machines)."""
    global _embedder
    with _embedder_lock:
        if _embedder is None:
            if os.environ.get("FIRSTLOOK_EMBED", "").lower() == "hash":
                _embedder = HashEmbedder()
            else:
                try:
                    _embedder = ModelEmbedder()
                except Exception:                       # noqa: BLE001 - no model is not fatal, search still works on wording
                    _embedder = HashEmbedder()
        return _embedder


# ---------------------------------------------------------------------------
# The database
# ---------------------------------------------------------------------------
class Store:
    def __init__(self, path: str | Path):
        import sqlite_vec
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = str(path)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.enable_load_extension(True)
        sqlite_vec.load(self.db)
        self.db.enable_load_extension(False)
        self.db.execute("PRAGMA journal_mode = WAL")
        self.db.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL) WITHOUT ROWID")
        version = self.db.execute("SELECT value FROM meta WHERE key = 'schema'").fetchone()
        if version is None or version["value"] != SCHEMA_VERSION:
            # Everything in here can be rebuilt from the storm and the reference folder, so an old layout is simply replaced.
            for name in ("doc_fts", "doc_vec", "doc", "question", "plan"):
                self.db.execute(f"DROP TABLE IF EXISTS {name}")
            self.db.execute("INSERT INTO meta (key, value) VALUES ('schema', ?) ON CONFLICT (key) DO UPDATE SET value = excluded.value", (SCHEMA_VERSION,))
        self.db.executescript(SCHEMA)
        self.db.commit()

    @staticmethod
    def digest(d: dict) -> str:
        return hashlib.sha1(f"{d['title']}\n{d['body']}".encode()).hexdigest()

    def sync(self, scope: str, docs: list[dict], emb) -> dict:
        """Make the records of one scope (a storm id, or 'reference') match `docs`, touching only
        what changed. A storm replaces the previous storm; the reference records stay. One transaction."""
        with self.lock, self.db:
            db = self.db
            model = db.execute("SELECT value FROM meta WHERE key = 'embedder'").fetchone()
            if model is None or model["value"] != emb.name:       # vectors from another model are not comparable
                db.execute("DELETE FROM doc_vec")
                db.execute("DELETE FROM doc")
                db.execute("INSERT INTO meta (key, value) VALUES ('embedder', ?) ON CONFLICT (key) DO UPDATE SET value = excluded.value", (emb.name,))
            old = [] if scope == "reference" else [r["id"] for r in db.execute("SELECT id FROM doc WHERE storm NOT IN (?, 'reference')", (scope,))]
            have = {(r["kind"], r["ref"]): (r["id"], r["digest"]) for r in db.execute("SELECT id, kind, ref, digest FROM doc WHERE storm = ?", (scope,))}
            want = {(d["kind"], d["ref"]): {**d, "digest": self.digest(d)} for d in docs}

            gone = old + [row for key, (row, _) in have.items() if key not in want]
            changed = [(have[key][0], d) for key, d in want.items() if key in have and have[key][1] != d["digest"]]
            new = [d for key, d in want.items() if key not in have]
            for row in gone + [row for row, _ in changed]:
                db.execute("DELETE FROM doc_vec WHERE rowid = ?", (row,))
            db.executemany("DELETE FROM doc WHERE id = ?", [(row,) for row in gone])
            for row, d in changed:
                db.execute("UPDATE doc SET title = ?, body = ?, link_kind = ?, link_id = ?, digest = ?, updated_at = datetime('now') WHERE id = ?",
                           (d["title"], d["body"], d["link_kind"], d["link_id"], d["digest"], row))
            fresh = list(changed)
            for d in new:
                cur = db.execute("INSERT INTO doc (storm, kind, ref, title, body, link_kind, link_id, digest) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                                 (scope, d["kind"], d["ref"], d["title"], d["body"], d["link_kind"], d["link_id"], d["digest"]))
                fresh.append((cur.lastrowid, d))

            # Vectors: reuse the cache by content hash, embed only what is truly new.
            digests = sorted({d["digest"] for _, d in fresh})
            cached = {}
            for i in range(0, len(digests), 500):
                part = digests[i:i + 500]
                marks = ",".join("?" * len(part))
                cached.update({r["digest"]: r["vector"] for r in db.execute(
                    f"SELECT digest, vector FROM embedding WHERE model = ? AND digest IN ({marks})", (emb.name, *part))})
            # the title says what a record is about, so it counts twice in the vector
            missing = {d["digest"]: f"{d['title']}. {d['title']}. {d['body']}" for _, d in fresh if d["digest"] not in cached}
            if missing:
                vectors = emb.embed(list(missing.values()))
                for digest, vector in zip(missing, vectors):
                    cached[digest] = vector.astype(np.float32).tobytes()
                db.executemany("INSERT OR REPLACE INTO embedding (digest, model, vector) VALUES (?, ?, ?)",
                               [(digest, emb.name, cached[digest]) for digest in missing])
            group = lambda kind: GROUP.get(kind, GROUP["note"])      # noqa: E731
            db.executemany("INSERT INTO doc_vec (rowid, embedding, grp) VALUES (?, ?, ?)",
                           [(row, cached[d["digest"]], group(d["kind"])) for row, d in fresh])
            if db.execute("SELECT count(*) FROM embedding").fetchone()[0] > 5000:
                db.execute("DELETE FROM embedding WHERE digest NOT IN (SELECT digest FROM doc)")
            return {"added": len(new), "changed": len(changed), "removed": len(gone), "embedded": len(missing)}

    def counts(self) -> dict:
        with self.lock:
            return {r["kind"]: r["n"] for r in self.db.execute("SELECT kind, count(*) AS n FROM doc GROUP BY kind ORDER BY kind")}

    def get(self, kind: str, ref: str) -> sqlite3.Row | None:
        with self.lock:
            return self.db.execute("SELECT * FROM doc WHERE kind = ? AND ref = ?", (kind, ref)).fetchone()

    def search(self, text: str, vector: np.ndarray, group: str = "note", k: int = 6) -> list[sqlite3.Row]:
        """Hybrid search within one group: 'note' (the storm's own records), 'message' (what
        residents wrote) or 'reference' (the reference documents).

        Rankings by meaning (vector distance) and by wording (BM25, title weighted 4x) are fused
        with reciprocal rank fusion, which needs no score calibration between them. Among the
        storm's records, one whose own name is in the text (a barangay, a city, a place) counts double."""
        pool = max(k * 3, 12)
        kinds = {"note": "NOT IN ('message', 'reference')", "message": "= 'message'", "reference": "= 'reference'"}[group]
        with self.lock:
            by_name = self._named(text) if group == "note" else []
            by_meaning = [r["rowid"] for r in self.db.execute(
                "SELECT rowid FROM doc_vec WHERE embedding MATCH ? AND k = ? AND grp = ? ORDER BY distance",
                (vector.astype(np.float32).tobytes(), pool, GROUP[group]))]
            by_wording = []
            terms = [w for w in re.findall(r"[a-z0-9ñ]+", text.lower()) if w not in STOP and len(w) > 1]
            if terms:
                match = " OR ".join(f'"{w}"*' for w in list(dict.fromkeys(terms))[:40])
                by_wording = [r["id"] for r in self.db.execute(
                    f"SELECT doc.id FROM doc_fts JOIN doc ON doc.id = doc_fts.rowid WHERE doc_fts MATCH ? AND doc.kind {kinds} "
                    "ORDER BY bm25(doc_fts, 4.0, 1.0) LIMIT ?", (match, pool))]
            score: dict[int, float] = {}
            for weight, ranking in ((1.0, by_meaning), (1.0, by_wording), (2.0, by_name)):
                for position, row in enumerate(ranking):
                    score[row] = score.get(row, 0.0) + weight / (60 + position)
            best = sorted(score, key=lambda row: -score[row])[:k * 2]
            if not best:
                return []
            rows = {r["id"]: r for r in self.db.execute(f"SELECT * FROM doc WHERE id IN ({','.join('?' * len(best))})", best)}
            out, seen = [], set()
            for row in best:                                # the same words stored twice count once
                key = (rows[row]["body"], rows[row]["kind"])
                if key not in seen:
                    seen.add(key)
                    out.append(rows[row])
            return out[:k]

    def _named(self, text: str) -> list[int]:
        """Barangays, cities and places whose name appears in full in the text, best match first."""
        words = set(re.findall(r"[a-z0-9ñ]+", text.lower()))
        equipment = any(w in words for w in (*EQUIPMENT, "number", "rank"))
        found = []
        for r in self.db.execute("SELECT id, kind, title FROM doc WHERE kind IN ('barangay', 'city', 'place')"):
            name = r["title"].split(":")[0]
            if r["kind"] == "barangay":
                name = name.split("Brgy. ")[-1].split(",")[0]
            tokens = {t for t in re.findall(r"[a-z0-9ñ]+", name.lower()) if t not in NAME_NOISE}
            if not tokens or not tokens <= words:
                continue
            fit = len(tokens) + (0.5 if r["kind"] == "place" and any(w in words and w in name.lower() for w in EQUIPMENT) else 0)
            prefer = {"place": 0.3 if equipment else 0.0, "barangay": 0.0 if equipment else 0.3, "city": 0.1}[r["kind"]]
            found.append((fit + prefer, r["id"]))
        return [row for _, row in sorted(found, key=lambda f: -f[0])]

    def log_plan(self, storm: str, generator_name: str, steps: list[str], refs: list[str], retrieve_ms: int, generate_ms: int) -> None:
        with self.lock, self.db:
            self.db.execute("INSERT INTO plan (storm, generator, steps, refs, retrieve_ms, generate_ms) VALUES (?, ?, ?, ?, ?, ?)",
                            (storm, generator_name, json.dumps(steps), json.dumps(refs), retrieve_ms, generate_ms))


_store: Store | None = None
_store_lock = threading.Lock()


def store() -> Store:
    global _store
    with _store_lock:
        if _store is None:
            _store = Store(os.environ.get("FIRSTLOOK_DB") or CACHE / "firstlook.db")
        return _store


def index(session) -> dict:
    """Bring the database up to date with the storm and the reference folder. Cheap when nothing changed."""
    with session.lock:
        docs = knowledge.build(session)
        storm = session.id
    db, emb = store(), embedder()
    reference = db.sync("reference", knowledge.reference_docs(REFERENCE), emb)
    return {**db.sync(storm, docs, emb), "reference": reference}


def warm(session) -> None:
    """Load the model and index the storm in the background so the first plan is fast."""
    def run():
        try:
            index(session)
        except Exception:                                   # noqa: BLE001 - the next request will try again
            pass
    threading.Thread(target=run, name="liwa-index", daemon=True).start()


# ---------------------------------------------------------------------------
# The generator: Claude Opus through the Claude Code CLI
# ---------------------------------------------------------------------------
_claude_lock = threading.Lock()
PROMPT = """You are Liwa, the inspection planner inside FirstLook, a tool a power utility in the Philippines uses after a \
typhoon or a power interruption to decide where to look for damage first. Write the inspection plan: the order in which the \
candidate places should be checked.

HOW TO DECIDE
- Follow the REFERENCE records. They are the guidance for ranking inspections. Guidance from the utility's own documents \
takes priority over FirstLook's built-in rule.
- Where the references do not settle the order between two places, keep the order the candidates are listed in.
- Use only the facts given here. Do not invent places, numbers or times. Never give a restoration time.
- In "summary" and "why", call places by their names, never by the id in square brackets.
- You only advise. People decide, and the utility's crews do the work.

REFERENCE (retrieved from the reference database for this situation)
{references}

SITUATION
{situation}

CANDIDATES, in FirstLook's own order
{candidates}

Reply with only a JSON object, no markdown fences and no other text, in exactly this form:
{{"summary": "two plain sentences on the plan as a whole", "steps": [{{"id": "candidate id", "why": "one plain sentence, at most 30 words", "refs": [1]}}]}}
List every candidate exactly once. "refs" holds the numbers of the reference records that decided that step's position."""


def generator() -> str:
    """'claude-code' when the Claude Code CLI can be used, otherwise 'offline'."""
    if os.environ.get("FIRSTLOOK_LIWA", "").lower() == "offline":
        return "offline"
    return "claude-code" if shutil.which("claude") else "offline"


def _claude(prompt: str) -> str | None:
    """One reply from Claude Code in print mode, or None. Never raises, never uses an API key."""
    exe = shutil.which("claude")
    if not exe:
        return None
    env = {k: v for k, v in os.environ.items() if not k.startswith(("ANTHROPIC_", "CLAUDECODE", "CLAUDE_CODE_"))}
    cwd = CACHE / "liwa"                                     # an empty folder: no project files, settings or memory to pick up
    cwd.mkdir(parents=True, exist_ok=True)
    cmd = [exe, "-p", "--model", CLAUDE_MODEL, "--effort", "low", "--tools", "", "--strict-mcp-config", "--disable-slash-commands",
           "--no-session-persistence", "--setting-sources", "project", "--output-format", "json",
           "--system-prompt", "You are Liwa, an inspection planner. Follow the instructions in the message exactly and reply with JSON only."]
    try:
        with _claude_lock:                                   # one at a time is plenty for a control room
            done = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8", env=env, cwd=cwd, timeout=CLAUDE_TIMEOUT)
        reply = json.loads(done.stdout)
        if done.returncode != 0 or reply.get("is_error") or not (reply.get("result") or "").strip():
            return None
        return reply["result"].strip()
    except Exception:                                        # noqa: BLE001 - missing, signed out, slow or garbled: fall back
        return None


def _parse(reply: str | None) -> dict | None:
    """The JSON object in Claude's reply, or None if there is not a usable one."""
    if not reply:
        return None
    start, end = reply.find("{"), reply.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(reply[start:end + 1])
    except ValueError:
        return None
    return data if isinstance(data, dict) and isinstance(data.get("steps"), list) else None


# ---------------------------------------------------------------------------
# The plan
# ---------------------------------------------------------------------------
def _candidate_line(r: dict) -> str:
    b = r["basis"]
    safety = "; ".join(b["safety"]).lower() + " (open)" if b["safety"] else "none"
    essential = ", ".join(f"{e['name']} in {e['area']}" for e in b["essential"]) or "none"
    return (f"[{r['asset_id']}] {r['name']}, {r['place']}. {r['travel_min']} min drive, about {r['inspect_min']} min on site. "
            f"Safety hazard: {safety}. Essential facilities likely without power behind it: {essential}. Network: {b['level_label'].lower()}. "
            f"Customers: about {b['predicted_accounts']:,} accounts predicted without power, roughly {b['load_mw']} MW; "
            f"{b['reported_people']} people reported; {round(b['p_damaged'] * 100)}% chance the damage is here.")


def _key(st: dict, refs: list[sqlite3.Row]) -> str:
    """Changes whenever a new plan is due: the candidates, their levels, what has been found, the reference records."""
    parts = [st["event"]["id"], [(r["asset_id"], r["tier"]) for r in st["recommendations"]], len(st["log"]), len(st["repaired"]),
             st["summary"]["hazards_open"], st["summary"]["reports"], sorted(r["digest"] for r in refs)]
    return hashlib.sha1(json.dumps(parts).encode()).hexdigest()[:16]


def plan(session, force: bool = False) -> dict:
    """The inspection plan for the storm as it stands. Written once per change, then served from memory."""
    started = time.perf_counter()
    index(session)
    db, st = store(), session.state()
    worth = [r for r in st["recommendations"] if r["tier"] != "low"]
    candidates, later = worth[:MAX_CANDIDATES], worth[MAX_CANDIDATES:]
    by_id = {r["asset_id"]: r for r in candidates}

    # Retrieval: the guidance that fits this situation, from the reference documents.
    notes = [row for row in (db.get("topic", ref) for ref in ("situation", "hazards", "essential")) if row is not None]
    situation = " ".join(row["body"] for row in notes)
    query = "inspection planning: which place to inspect first, ranking and priority. " + situation
    found = db.search(query, embedder().embed_query([query])[0], group="reference", k=6)
    rule = db.get("topic", "rule")
    references = found + ([rule] if rule is not None else [])
    key = _key(st, references)
    cached = getattr(session, "liwa_plan", None)
    if cached and cached["key"] == key and not force:
        return cached
    retrieve_ms = round((time.perf_counter() - started) * 1000)

    started = time.perf_counter()
    written = None
    if generator() == "claude-code" and candidates:
        written = _parse(_claude(PROMPT.format(
            references="\n\n".join(f"[{n}] {('FirstLook built-in rule' if r['kind'] == 'topic' else r['title'])}\n{r['body']}" for n, r in enumerate(references, 1)),
            situation=situation, candidates="\n".join(_candidate_line(r) for r in candidates))))
    steps, seen = [], set()
    for item in (written or {}).get("steps", []):
        rec = by_id.get(str(item.get("id", "")).strip("[] ")) if isinstance(item, dict) else None
        if rec is None or rec["asset_id"] in seen:           # an id Claude made up, or repeated, is ignored
            continue
        seen.add(rec["asset_id"])
        refs = [n for n in item.get("refs", []) if isinstance(n, int) and 1 <= n <= len(references)]
        steps.append((rec, " ".join(str(item.get("why") or rec["headline"]).split()), refs))
    by = "claude-code" if steps else "offline"
    for rec in candidates + later:                           # anything Claude left out keeps the engine's place and reason
        if rec["asset_id"] not in seen:
            steps.append((rec, rec["headline"] + ".", []))
    generate_ms = round((time.perf_counter() - started) * 1000)

    used = sorted({n for _, _, refs in steps for n in refs})
    order = [rec["asset_id"] for rec, _, _ in steps]
    result = {
        "key": key, "storm": st["event"]["id"], "generator": by, "model": CLAUDE_MODEL if by == "claude-code" else None,
        "summary": " ".join(str(written["summary"]).split()) if by == "claude-code" and written.get("summary") else knowledge.situation(st),
        "steps": [{"n": n, "asset_id": rec["asset_id"], "name": rec["name"], "place": rec["place"], "tier": rec["tier"],
                   "travel_min": rec["travel_min"], "engine_rank": rec["rank"], "why": why, "refs": refs}
                  for n, (rec, why, refs) in enumerate(steps, 1)],
        "references": [{"n": n, "title": "FirstLook's built-in rule" if r["kind"] == "topic" else r["title"], "text": r["body"],
                        "own": r["kind"] == "reference", "used": n in used} for n, r in enumerate(references, 1)],
        "reference_documents": len(found),
        "reordered": order != [r["asset_id"] for r in candidates + later],
        "ms": {"retrieve": retrieve_ms, "generate": generate_ms},
    }
    session.liwa_plan = result
    db.log_plan(st["event"]["id"], by, order, [r["ref"] for r in references], retrieve_ms, generate_ms)
    return result


def status(session) -> dict:
    index(session)
    db = store()
    brief = db.get("topic", "situation")
    counts = db.counts()
    files = sorted({r["ref"].split("#")[0] for r in db.db.execute("SELECT ref FROM doc WHERE kind = 'reference'")})
    return {"name": "Liwa", "generator": generator(), "model": CLAUDE_MODEL, "embedder": embedder().name,
            "records": counts, "brief": brief["body"] if brief else "", "database": Path(db.path).name,
            "reference": {"folder": "backend/reference", "files": files, "chunks": counts.get("reference", 0)}}
