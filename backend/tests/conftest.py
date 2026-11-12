import os
import tempfile

# Tests never call an AI service: no key, no network, no cost, no Claude Code.
_tmp = tempfile.mkdtemp(prefix="firstlook-test-")
os.environ["FIRSTLOOK_AI"] = "off"
os.environ["FIRSTLOOK_LIWA"] = "offline"                 # the plan is the engine's own order
os.environ["FIRSTLOOK_EMBED"] = "hash"                   # no embedding model to download
os.environ["FIRSTLOOK_DB"] = os.path.join(_tmp, "test.db")
os.environ["FIRSTLOOK_REFERENCE"] = os.path.join(_tmp, "reference")   # empty unless a test fills it
