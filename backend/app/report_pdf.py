"""The PDF reports: a restoration report for a past typhoon, and a situation report for the one in progress.

A restoration report has what such a report needs in practice:
    document control (number, status, period, who it is for), the event, the impact, restoration
    progress with its milestones and curve, impact by customer tier, causes and the work done,
    customer reports by channel, safety and holds, how the work was prioritised and where a
    dispatcher changed it, crews, the full interruption log, open items and follow-up actions,
    definitions and limits of the data, and a sign-off block.

Every figure comes from the event's record (see history.py); nothing is typed into this file.
The built-in Helvetica is used, so text is reduced to Latin-1 before it is written.
"""
from __future__ import annotations

from datetime import datetime

from fpdf import FPDF
from fpdf.fonts import FontFace

from .reports import MANILA

INK, MUTED, LINE, SOFT, BLUE, RED = (31, 31, 31), (94, 99, 104), (218, 220, 224), (241, 243, 244), (11, 87, 208), (165, 14, 14)
NOTE = "Simulated data, prepared for a demonstration. Not a Meralco record."
HIERARCHY = ("Work was ranked in this order: safety of the crew and the route first, then flood clearance, then the highest customer tier "
             "(Critical, Community services, Residential), then the most customers restored, then the most linked customer reports, "
             "then the shortest driving time. Customer reports were weighed lightly: they never moved a job past safety, flood "
             "clearance, tier or customers restored.")


def _plain(text) -> str:
    text = str(text)
    for a, b in (("’", "'"), ("‘", "'"), ("“", '"'), ("”", '"'), ("–", "-"), ("—", "-"), ("•", "-")):
        text = text.replace(a, b)
    return text.encode("latin-1", "replace").decode("latin-1")


def _when(iso: str, with_date: bool = True) -> str:
    t = datetime.fromisoformat(iso).astimezone(MANILA)
    return f"{t.day} {t:%b %Y}, {t:%H:%M}" if with_date else f"{t.day} {t:%b} {t:%H:%M}"


def _n(value) -> str:
    return f"{value:,}"


def _hours(h) -> str:
    return "n/a" if h is None else f"{h:g} h"


class _Doc(FPDF):
    def __init__(self, title: str, number: str):
        super().__init__(format="A4", unit="mm")
        self.title_text, self.number = _plain(title), _plain(number)
        self.set_margins(16, 16, 16)
        self.set_auto_page_break(True, margin=18)
        self.set_title(self.title_text)
        self.set_author("FirstLook")
        self.set_creator("FirstLook")

    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*MUTED)
        self.cell(0, 5, self.title_text, new_x="LMARGIN", new_y="TOP")
        self.cell(0, 5, self.number, align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*LINE)
        self.set_line_width(0.2)
        self.line(self.l_margin, self.get_y() + 1, self.w - self.r_margin, self.get_y() + 1)
        self.ln(5)

    def footer(self):
        self.set_y(-13)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*MUTED)
        self.cell(0, 5, NOTE, new_x="LMARGIN", new_y="TOP")
        self.cell(0, 5, f"Page {self.page_no()} of {{nb}}", align="R")

    # ---- pieces -----------------------------------------------------------------------------
    def need(self, height: float):
        if self.will_page_break(height):
            self.add_page()

    def h2(self, text: str, room: float = 30):
        self.need(room)
        self.ln(3)
        self.set_font("Helvetica", "B", 12.5)
        self.set_text_color(*INK)
        self.cell(0, 7, _plain(text), new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*INK)
        self.set_line_width(0.4)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(2.5)

    def para(self, text: str, size: float = 9.5, color=INK, style: str = ""):
        self.set_font("Helvetica", style, size)
        self.set_text_color(*color)
        self.multi_cell(0, size * 0.5, _plain(text), align="L", new_x="LMARGIN", new_y="NEXT")
        self.ln(1.2)

    def bullets(self, items: list[str]):
        self.set_font("Helvetica", "", 9.5)
        self.set_text_color(*INK)
        for item in items:
            self.set_x(self.l_margin)
            self.cell(4, 4.8, "-")
            self.multi_cell(0, 4.8, _plain(item), align="L", new_x="LMARGIN", new_y="NEXT")
            self.ln(0.8)

    def facts(self, rows: list[tuple[str, str]], label_width: float = 46):
        for label, value in rows:
            self.need(6)
            self.set_font("Helvetica", "", 9)
            self.set_text_color(*MUTED)
            self.cell(label_width, 5.2, _plain(label))
            self.set_font("Helvetica", "", 9.5)
            self.set_text_color(*INK)
            self.multi_cell(0, 5.2, _plain(value), align="L", new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def stats(self, items: list[tuple[str, str]]):
        """A row of figures: the number large, what it counts beneath it."""
        self.need(22)
        gap, width = 3, (self.epw - 3 * (len(items) - 1)) / len(items)
        x0, y0 = self.l_margin, self.get_y()
        for i, (figure, label) in enumerate(items):
            x = x0 + i * (width + gap)
            self.set_fill_color(*SOFT)
            self.rect(x, y0, width, 18, style="F")
            self.set_xy(x + 3, y0 + 2.5)
            self.set_font("Helvetica", "B", 15)
            self.set_text_color(*INK)
            self.cell(width - 6, 7, _plain(figure))
            self.set_xy(x + 3, y0 + 10)
            self.set_font("Helvetica", "", 8)
            self.set_text_color(*MUTED)
            self.multi_cell(width - 6, 3.4, _plain(label), align="L")
        self.set_xy(x0, y0 + 21)

    def grid(self, headings: list[str], rows: list[list], widths: list[float], align: list[str] | None = None, size: float = 8.5):
        self.set_font("Helvetica", "", size)
        self.set_text_color(*INK)
        self.set_draw_color(*LINE)
        self.set_line_width(0.2)
        head = FontFace(emphasis="BOLD", color=INK, fill_color=SOFT, size_pt=size)
        with self.table(col_widths=tuple(widths), text_align=tuple(align or ["LEFT"] * len(headings)), borders_layout="HORIZONTAL_LINES",
                        line_height=size * 0.48, headings_style=head, padding=(1.1, 1.2), cell_fill_color=(255, 255, 255), cell_fill_mode="ALL") as table:
            row = table.row()
            for h in headings:
                row.cell(_plain(h))
            for data in rows:
                row = table.row()
                for value in data:
                    row.cell(_plain(value))
        self.ln(2)

    def bars(self, rows: list[tuple[str, int, str]]):
        """Horizontal bars, one hue, for a single measure. The value is written beside each bar."""
        top = max(v for _, v, _ in rows) or 1
        label_w, value_w = 42, 54
        track = self.epw - label_w - value_w
        for label, value, note in rows:
            self.need(7)
            y = self.get_y()
            self.set_font("Helvetica", "", 9)
            self.set_text_color(*INK)
            self.cell(label_w, 6, _plain(label))
            self.set_fill_color(*BLUE)
            self.rect(self.l_margin + label_w, y + 1.4, max(0.6, track * value / top), 3.2, style="F")
            self.set_xy(self.l_margin + label_w + track + 2, y)
            self.set_text_color(*MUTED)
            self.cell(value_w - 2, 6, _plain(note), new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def curve(self, points: list[tuple[float, float]], marks: list[tuple[float, float, str]], height: float = 40):
        """Share of customers restored against hours after the all clear. A step line: power returns a repair at a time."""
        self.need(height + 14)
        left, top = self.l_margin + 11, self.get_y() + 2
        width = self.epw - 15
        last = max(p[0] for p in points)
        span = max(6, int(-(-last // 6)) * 6)                    # the axis ends on a multiple of 6 hours
        px = lambda h: left + width * h / span
        py = lambda pct: top + height * (1 - pct / 100)
        self.set_font("Helvetica", "", 7.5)
        self.set_text_color(*MUTED)
        self.set_draw_color(*LINE)
        self.set_line_width(0.15)
        for pct in (0, 25, 50, 75, 100):
            self.line(left, py(pct), left + width, py(pct))
            self.set_xy(self.l_margin, py(pct) - 2)
            self.cell(9.5, 4, f"{pct}%", align="R")
        step = 6 if span <= 36 else 12
        for h in range(0, span + 1, step):
            self.set_xy(px(h) - 6, top + height + 1)
            self.cell(12, 4, f"{h} h", align="C")
        self.set_draw_color(*BLUE)
        self.set_line_width(0.7)
        x, y = px(0), py(0)
        for h, pct in points[1:]:
            self.line(x, y, px(h), y)
            self.line(px(h), y, px(h), py(pct))
            x, y = px(h), py(pct)
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(*INK)
        for h, pct, label in marks:                              # the milestones, labelled where they fall
            self.set_fill_color(*BLUE)
            self.ellipse(px(h) - 1.1, py(pct) - 1.1, 2.2, 2.2, style="F")
            self.set_xy(px(h) + 1.8 if px(h) < left + width - 34 else px(h) - 34, py(pct) + 2.2)
            self.cell(32, 4, _plain(label), align="L" if px(h) < left + width - 34 else "R")
        self.set_xy(self.l_margin, top + height + 6)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*MUTED)
        self.cell(0, 4, "Hours after the all clear. Vertical axis: share of affected customers with power back.", new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def cover(self, kind: str, name: str, status: str, rows: list[tuple[str, str]]):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*BLUE)
        self.cell(0, 5, "FirstLook", new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*MUTED)
        self.cell(0, 5, _plain(kind), new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "B", 22)
        self.set_text_color(*INK)
        self.multi_cell(0, 10, _plain(name), align="L", new_x="LMARGIN", new_y="NEXT")
        self.ln(1)
        y = self.get_y()
        self.set_draw_color(*RED)
        self.set_line_width(0.3)
        self.rect(self.l_margin, y, self.epw, 7.5)
        self.set_xy(self.l_margin + 3, y + 1.3)
        self.set_font("Helvetica", "B", 8.5)
        self.set_text_color(*RED)
        self.cell(0, 5, NOTE)
        self.set_xy(self.l_margin, y + 10.5)
        self.facts([("Status", status)] + rows)

    def sign_off(self):
        self.h2("Sign-off", room=48)
        width, gap = (self.epw - 8) / 3, 4
        y = self.get_y() + 1
        for i, role in enumerate(("Prepared by", "Reviewed by", "Approved by")):
            x = self.l_margin + i * (width + gap)
            self.set_xy(x, y)
            self.set_font("Helvetica", "B", 9)
            self.set_text_color(*INK)
            self.cell(width, 5, role)
            for k, field in enumerate(("Name", "Position", "Signature", "Date")):
                yy = y + 14 + k * 9
                self.set_draw_color(*MUTED)
                self.set_line_width(0.2)
                self.line(x, yy, x + width, yy)
                self.set_xy(x, yy + 0.4)
                self.set_font("Helvetica", "", 7.5)
                self.set_text_color(*MUTED)
                self.cell(width, 3.5, field)
        self.set_xy(self.l_margin, y + 14 + 3 * 9 + 6)


def _made() -> str:
    return _when(datetime.now(MANILA).isoformat())


def restoration(event: dict) -> bytes:
    """The restoration report for a closed event."""
    s, log = event["summary"], event["log"]
    pdf = _Doc(f"Restoration report: {event['name']}", event["document"])
    pdf.add_page()
    pdf.cover("Typhoon restoration report", event["name"], "Final. All customers restored.", [
        ("Document number", event["document"]),
        ("Period covered", f"{_when(event['landfall'])} to {_when(s['restored'])} (Philippine time)"),
        ("Area covered", f"FirstLook demonstration sector: 24 barangays in {', '.join(s['cities'])}"),
        ("Generated", f"{_made()} by FirstLook from the event's interruption log"),
        ("For", "Sector operations head, system operations, customer care, regulatory reporting"),
    ])

    pdf.h2("1. The event")
    pdf.facts([
        ("Classification", event["class"]),
        ("Strongest winds near the center", f"{event['peak_kmh']} km/h"),
        ("Highest wind signal in the area", f"Signal no. {event['signal']}"),
        ("Closest approach", _when(event["landfall"])),
        ("All clear for crews", _when(event["all_clear"])),
        ("Last customer restored", f"{_when(s['restored'])} ({_hours(s['hours_to_all'])} after the all clear)"),
        ("Track", event["track"]),
    ])
    pdf.para(event["what"])

    pdf.h2("2. Impact at a glance", room=52)
    pdf.stats([(_n(s["customers"]), "customers affected"), (_n(s["interruptions"]), "power interruptions"),
               (_hours(s["hours_to_90"]), "to restore 90% of customers"), (_hours(s["hours_to_all"]), "to restore every customer")])
    pdf.stats([(_n(s["reports"]), "reports from customers"), (_n(s["customer_minutes"]), "customer-minutes interrupted"),
               (_hours(s["average_outage_h"]), "average outage per affected customer"), (str(s["crews"]), "crews deployed")])

    pdf.h2("3. Restoration progress", room=66)
    pdf.curve(s["curve"], [(s["hours_to_half"], next(p for h, p in s["curve"] if h >= s["hours_to_half"] and p >= 50), "50% restored"),
                           (s["hours_to_90"], next(p for h, p in s["curve"] if h >= s["hours_to_90"] and p >= 90), "90% restored")])
    pdf.grid(["Milestone", "Hours after the all clear", "Date and time"], [
        ["Half of affected customers restored", _hours(s["hours_to_half"]), _when(next(r["restored"] for r in log if r["after_clear_h"] >= s["hours_to_half"]))],
        ["90% of affected customers restored", _hours(s["hours_to_90"]), _when(next(r["restored"] for r in log if r["after_clear_h"] >= s["hours_to_90"]))],
        ["All Critical customers restored", _hours(s["critical_all_h"]) if s["critical_count"] else "None were interrupted",
         _when(max(r["restored"] for r in log if r["tier"] == 1)) if s["critical_count"] else "-"],
        ["Every customer restored", _hours(s["hours_to_all"]), _when(s["restored"])],
    ], [78, 46, 54], ["LEFT", "RIGHT", "RIGHT"])

    pdf.h2("4. Impact by customer tier")
    pdf.grid(["Customer tier", "Interruptions", "Customers", "Average time to restore", "Last one restored"],
             [[t["name"], _n(t["interruptions"]), _n(t["customers"]), _hours(t["average_h"]), _hours(t["last_h"])] for t in s["by_tier"]],
             [50, 28, 28, 40, 32], ["LEFT", "RIGHT", "RIGHT", "RIGHT", "RIGHT"])
    pdf.para("Times are hours after the all clear. Critical: hospitals, evacuation centers, schools serving as evacuation centers. "
             "Community services: schools in regular use, barangay halls, public markets. Residential: houses and apartments.", 8, MUTED)

    pdf.h2("5. Causes of damage and work done", room=46)
    pdf.bars([(c["cause"], c["customers"], f"{_n(c['customers'])} customers, {c['interruptions']} interruptions") for c in s["causes"]])
    work = {}
    for r in log:
        work[r["repair"]] = work.get(r["repair"], 0) + 1
    pdf.grid(["Work done", "Interruptions"], [[k, str(v)] for k, v in sorted(work.items(), key=lambda kv: -kv[1])], [140, 38], ["LEFT", "RIGHT"])
    pdf.para(f"{_n(s['equipment_checked'])} pieces of equipment (poles, transformers, line sections) were checked across the {s['interruptions']} interruptions.", 8, MUTED)

    pdf.h2("6. Customer reports")
    pdf.bars([(c, n, f"{_n(n)} reports, {round(100 * n / s['reports'])}%") for c, n in s["by_channel"].items()])
    pdf.facts([
        ("Reports received", f"{_n(s['reports'])}, each from a different customer"),
        ("Describing a hazard", f"{_n(s['hazard_reports'])} (live wire, fallen pole, sparks, tree on the line). Passed to the crews to confirm on arrival."),
        ("Mentioning someone who depends on power", f"{_n(s['vulnerable_reports'])} (oxygen, dialysis, nebulizer, bedridden or elderly). Passed to customer care."),
    ], 74)

    held = [r for r in log if r["hold_minutes"]]
    pdf.h2("7. Safety and holds")
    pdf.facts([
        ("Injuries to crews or the public", f"{s['injuries']} reported"),
        ("Interruptions held before work could start", f"{s['held']} of {s['interruptions']}, {_hours(s['held_hours'])} of holding in total"),
    ], 74)
    if held:
        pdf.grid(["No.", "Location", "Reason for the hold", "Held for", "Crew sent"],
                 [[str(r["no"]), f"Brgy. {r['barangay']}, {r['city']}", r["hold_reason"], _hours(round(r["hold_minutes"] / 60, 1)), _when(r["dispatched"], False)] for r in held],
                 [12, 56, 58, 22, 30], ["RIGHT", "LEFT", "LEFT", "RIGHT", "RIGHT"])

    pdf.h2("8. How the work was prioritised")
    pdf.para(HIERARCHY)
    pdf.facts([("Recommended first check followed", f"{s['followed']} of {s['interruptions']} interruptions"),
               ("Changed by the dispatcher", f"{s['changed']}")], 74)
    if event["changed"]:
        pdf.grid(["Why the dispatcher changed it", "What was done instead"], [[c["why"], c["what"]] for c in event["changed"]], [89, 89])

    pdf.h2("9. Crews and resources")
    pdf.facts([("Crews deployed", f"{s['crews']}, each sent from the Meralco office nearest to the work"),
               ("First crews sent", _when(min(r["dispatched"] for r in log))),
               ("Average work per crew", f"{s['interruptions'] / s['crews']:.1f} interruptions")], 74)

    pdf.h2("10. Interruption log", room=40)
    pdf.para("In the order power was restored. All times are Philippine time.", 8, MUTED)
    pdf.grid(["No.", "Location", "Tier", "Serves", "Cause", "Cust.", "Rep.", "Began", "Crew sent", "Restored", "Outage"],
             [[str(r["no"]), f"{r['barangay']}, {r['city']}", r["tier_name"], r["serves"], r["cause"], _n(r["customers"]), _n(r["reports"]),
               _when(r["began"], False), _when(r["dispatched"], False), _when(r["restored"], False), _hours(round(r["minutes"] / 60, 1))] for r in log],
             [8, 26, 19, 21, 21, 10, 9, 17, 17, 17, 13], ["RIGHT", "LEFT", "LEFT", "LEFT", "LEFT", "RIGHT", "RIGHT", "RIGHT", "RIGHT", "RIGHT", "RIGHT"], size=6.8)

    pdf.h2("11. Open items and follow-up")
    if event["open"]:
        pdf.para("Still open when this report was closed:", 9.5, INK, "B")
        pdf.bullets(event["open"])
    else:
        pdf.para("No items were left open.")
    pdf.para("Follow-up actions:", 9.5, INK, "B")
    pdf.bullets(event["lessons"])

    pdf.h2("12. Definitions and limits of the data")
    pdf.bullets([
        "Customers are customer accounts, not people. A customer is counted once, in the interruption that affected it.",
        "An outage runs from when power was lost to when it was restored. Customer-minutes interrupted is the sum, over all interruptions, of customers multiplied by minutes of outage.",
        "Hours to restore are counted from the all clear, the time crews could safely be sent, not from when the storm arrived.",
        "This report covers one sector. It does not give system-wide reliability figures such as SAIFI or SAIDI.",
        "Customer reports come from the Meralco App, SMS, Hotline 16211, Facebook and X. Reports that could not be linked to an interruption are not counted.",
        NOTE + " The event, its interruption log and every figure in this report were generated for the demonstration.",
    ])
    pdf.sign_off()
    return bytes(pdf.output())


def situation(now: dict) -> bytes:
    """The situation report for the typhoon in progress: what is waiting, and what to check first in each interruption."""
    rows = now["interruptions"]
    pdf = _Doc(f"Situation report: {now['name']}", now["document"])
    pdf.add_page()
    pdf.cover("Typhoon situation report", now["name"], "In progress. Restoration has not been completed.", [
        ("Document number", now["document"]),
        ("Situation as of", f"{_made()} (Philippine time)"),
        ("All clear for crews", _when(now["all_clear"])),
        ("Area covered", f"FirstLook demonstration sector: {', '.join(now['cities'])}"),
        ("For", "Sector operations head, dispatch, customer care"),
    ])
    pdf.h2("1. Where things stand", room=52)
    pdf.stats([(_n(now["customers"]), "customers without power"), (_n(len(rows)), "power interruptions"),
               (_n(now["reports"]), "reports from customers"), (_n(now["equipment"]), "pieces of equipment to check")])
    pdf.stats([(_n(now["on_hold"]), "pieces of equipment on hold"), (_n(now["critical"]), "interruptions with Critical customers"),
               (_n(now["ranked"]), "interruptions ranked by Liwa"), (_n(len(rows) - now["ranked"]), "ranked by the written rule only")])

    pdf.h2("2. Interruptions and what to check first", room=40)
    pdf.para("Grouped by the highest customer tier still waiting. The first check is a recommendation: a person sends the crew.", 8, MUTED)
    pdf.grid(["Location", "Highest tier", "Customers", "Reports", "To check", "On hold", "Check first", "Ranked by"],
             [[r["place"], r["tier_name"], _n(r["customers"]), _n(r["reports"]), str(r["equipment"]), str(r["on_hold"]), r["first"], r["by"]] for r in rows],
             [34, 26, 17, 15, 14, 13, 40, 19], ["LEFT", "LEFT", "RIGHT", "RIGHT", "RIGHT", "RIGHT", "LEFT", "LEFT"], size=7.6)

    pdf.h2("3. Customer reports")
    pdf.bars([(c, n, f"{_n(n)} reports, {round(100 * n / max(1, now['reports']))}%") for c, n in now["by_channel"].items()])
    pdf.facts([("Describing a hazard", f"{_n(now['hazard_reports'])}. For the crews to confirm on arrival."),
               ("Mentioning someone who depends on power", f"{_n(now['vulnerable_reports'])}. For customer care.")], 74)

    pdf.h2("4. How the work is being prioritised")
    pdf.para(HIERARCHY)

    pdf.h2("5. Definitions and limits of the data")
    pdf.bullets([
        "Customers without power is the sum of the customer accounts each unfinished job would restore. It counts accounts, not people.",
        "Equipment on hold is not safe for the crew yet, or is flooded and waiting for clearance.",
        "\"Ranked by Liwa\" means the order was written by the planner from the reference records and the customer reports. \"Written rule\" means the same hierarchy applied mechanically, used where an interruption has not been opened yet.",
        "This is a snapshot. Equipment marked resolved on screen during a session is not recorded here.",
        NOTE + " The interruptions are test cases and the customer reports are invented.",
    ])
    pdf.sign_off()
    return bytes(pdf.output())
