"""Candidate disclosure checklist, scored against public US and EU rules as a yardstick.

This is a checklist, not legal advice. Whether a rule applies to you depends on where
the role and the candidate are, who decides, and what the tool records. Read the
sources, and ask counsel before you rely on it.

Input (``disclosure.yaml``)::

    answers:
      tell_ai_used:        {status: yes, note: "first screen of the interview page"}
      tell_interacting_with_ai: {status: yes, note: "avatar says it is an AI in the first clip"}
      explain_how:         {status: partly}
      bias_audit:          {status: no}
      ...

``status`` is one of ``yes``, ``partly``, ``no``, ``n/a``. Missing items count as ``no``.
``hireburn disclosure --page page.html`` additionally checks a candidate page built by
``hireburn avatar page`` for the markers that page must carry.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

from hireburn._io import md_table

SOURCES = {
    "NYC LL 144": "https://www.nyc.gov/site/dca/about/automated-employment-decision-tools.page",
    "Illinois AIVIA": "https://www.ilga.gov/legislation/ilcs/ilcs3.asp?ActID=4015&ChapterID=68",
    "Illinois HB 3773": "https://www.ilga.gov/ (HB 3773, 103rd General Assembly; amends the Illinois Human Rights Act)",
    "EU AI Act": "https://eur-lex.europa.eu/eli/reg/2024/1689/oj",
}

# id, framework(s), requirement, page marker that can show it (or "")
REQUIREMENTS: list[dict[str, str]] = [
    {"id": "tell_ai_used", "rule": "NYC LL 144 · Illinois AIVIA · Illinois HB 3773 · EU AI Act Art. 26(11) (deployer)",
     "requirement": "Tell the candidate, before the interview, that AI is used to make or assist the hiring decision. "
                    "EU: deployers of Annex III high-risk systems that make or assist decisions about people must inform them",
     "marker": "disclosure"},
    {"id": "tell_interacting_with_ai", "rule": "EU AI Act Art. 50(1), 50(5) (provider)",
     "requirement": "Make clear the candidate is talking to an AI avatar, not a person, at the latest at the first interaction. "
                    "EU: a provider design duty for systems that interact directly with people, unless it is obvious",
     "marker": "disclosure"},
    {"id": "explain_how", "rule": "Illinois AIVIA · NYC LL 144",
     "requirement": "Explain how the AI works and which qualifications and characteristics it evaluates",
     "marker": "evaluates"},
    {"id": "consent", "rule": "Illinois AIVIA",
     "requirement": "Obtain consent before the interview starts (a separate, unticked checkbox)",
     "marker": "consent"},
    {"id": "notice_10_days", "rule": "NYC LL 144",
     "requirement": "Give notice at least 10 business days before use (job posting or mail counts)",
     "marker": ""},
    {"id": "alternative", "rule": "NYC LL 144 · safeguard for EU AI Act Art. 14, 26(2) (human oversight)",
     "requirement": "Offer a way to request an alternative process or accommodation, and real human review. "
                    "NYC LL 144 notice covers this; under the EU AI Act it is a safeguard that supports human oversight",
     "marker": "alternative"},
    {"id": "retention", "rule": "NYC LL 144 · Illinois AIVIA",
     "requirement": "State what is recorded, who sees it and how long it is kept; delete on request (Illinois: within 30 days)",
     "marker": "retention"},
    {"id": "limit_sharing", "rule": "Illinois AIVIA",
     "requirement": "Share recordings only with people needed to evaluate the candidate",
     "marker": ""},
    {"id": "bias_audit", "rule": "NYC LL 144",
     "requirement": "Independent bias audit within one year before use; public summary of results",
     "marker": ""},
    {"id": "no_discriminatory_effect", "rule": "Illinois HB 3773 · EU AI Act Annex III(4)",
     "requirement": "Check for discriminatory effect; do not use proxies such as ZIP codes",
     "marker": ""},
    {"id": "human_reads_before_reject", "rule": "Safeguard for EU AI Act Art. 14, 26(2) (human oversight)",
     "requirement": "A person with the competence and authority to overrule the AI label reads the transcript before any "
                    "rejection based on it. A safeguard for this process, not a step the Act names",
     "marker": "human_review"},
    {"id": "no_emotion_inference", "rule": "EU AI Act Art. 5(1)(f)",
     "requirement": "Do not infer emotions from voice or face; score the content of answers only",
     "marker": ""},
    {"id": "demographic_reporting", "rule": "Illinois AIVIA",
     "requirement": "If AI alone selects who gets an in-person interview: collect and report race and ethnicity data",
     "marker": ""},
]

STATUSES = ("yes", "partly", "no", "n/a")
PAGE_MARKERS = tuple(r["marker"] for r in REQUIREMENTS if r["marker"])


def _status(v: Any) -> tuple[str, str]:
    note = ""
    if isinstance(v, Mapping):
        note = str(v.get("note", "") or "")
        v = v.get("status")
    if v is True:
        v = "yes"
    if v is False or v is None:
        v = "no"
    s = str(v).strip().lower()
    if s in ("na", "n-a", "not applicable"):
        s = "n/a"
    if s not in STATUSES:
        raise ValueError(f"disclosure status {v!r}: use one of {', '.join(STATUSES)}")
    return s, note


def check_page(html: str) -> dict[str, bool]:
    """Which disclosure markers a candidate page carries (``data-hireburn="<marker>"`` with text)."""
    found = {}
    for marker in PAGE_MARKERS:
        m = re.search(rf'data-hireburn="{marker}"[^>]*>(.*?)</', html, flags=re.S)
        found[marker] = bool(m and re.sub(r"<[^>]+>", "", m.group(1)).strip())
    return found


def evaluate(config: Mapping[str, Any] | None, page_html: str | None = None) -> dict[str, Any]:
    answers = dict((config or {}).get("answers", {}) or {})
    unknown = sorted(set(answers) - {r["id"] for r in REQUIREMENTS})
    page = check_page(page_html) if page_html is not None else None
    items = []
    for r in REQUIREMENTS:
        status, note = _status(answers.get(r["id"]))
        if page is not None and r["marker"]:
            on_page = page[r["marker"]]
            note = (note + "; " if note else "") + ("page: present" if on_page else "page: MISSING")
            if not on_page and status == "yes":
                status = "partly"
        items.append({**r, "status": status, "note": note})
    counts = {s: sum(i["status"] == s for i in items) for s in STATUSES}
    return {"items": items, "counts": counts, "unknown_ids": unknown, "page_checked": page is not None,
            "sources": SOURCES,
            "disclaimer": "Yardstick, not legal advice. Whether each rule applies depends on jurisdiction, role and tool."}


def render(res: dict[str, Any]) -> str:
    icon = {"yes": "✅ yes", "partly": "◐ partly", "no": "❌ no", "n/a": "· n/a"}
    rows = [[i["requirement"], i["rule"], icon[i["status"]], i["note"]] for i in res["items"]]
    c = res["counts"]
    out = ["## Candidate disclosure checklist", "", md_table(["requirement", "rule (yardstick)", "status", "note"], rows, "llll"), "",
           f"- yes {c['yes']} · partly {c['partly']} · no {c['no']} · n/a {c['n/a']}",
           f"- ⚠ {res['disclaimer']}"]
    if res["unknown_ids"]:
        out.append(f"- ⚠ unknown ids ignored: {', '.join(res['unknown_ids'])}")
    out.append("- sources: " + " · ".join(f"{k}: {v}" for k, v in res["sources"].items()))
    return "\n".join(out) + "\n"
