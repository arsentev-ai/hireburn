"""Transcript rubric → HIRE / MAYBE / NO, with the caveat attached to every label.

Input (``rubric.yaml``)::

    thresholds: {hire: 4.0, maybe: 3.0}
    criteria:
      - id: result
        question_id: q1
        weight: 2
        what: A concrete result from past work and the candidate's own part in it
        anchors: {1: no example, 3: example without own part or number, 5: specific result, own part, number}

Rules built in, not configurable:

* scoring reads the content of the answers only — never tone of voice or face;
* a missing answer is reported, not silently scored as 1;
* every NO, and every label with a missing answer, is flagged ``needs_human_review``;
  a person reads the transcript before anyone is rejected;
* every report carries the caveat that a label is not a measurement.
"""

from __future__ import annotations

from typing import Any, Mapping

from hireburn import CONCEPT_DOI
from hireburn._io import md_table
from hireburn.avatar.providers import Scorer

CAVEAT = (
    "A label is a cut-off on a model's reading of one conversation. It is not a measurement of how the "
    "person will work. In the case this method comes from, AI-interview labels did not line up with who "
    f"was still working weeks later (payrollburn AI-hiring report, DOI {CONCEPT_DOI}). Check your labels "
    "against your own outcomes with `hireburn labels`."
)


def validate(rubric: Mapping[str, Any]) -> None:
    crit = rubric.get("criteria") or []
    if not crit:
        raise ValueError("rubric: no criteria")
    ids = [c.get("id") for c in crit]
    if len(set(ids)) != len(ids) or not all(ids):
        raise ValueError("rubric: every criterion needs a unique id")
    th = rubric.get("thresholds") or {}
    hire, maybe = float(th.get("hire", 4.0)), float(th.get("maybe", 3.0))
    if not 1 <= maybe <= hire <= 5:
        raise ValueError("rubric: thresholds must satisfy 1 ≤ maybe ≤ hire ≤ 5")
    banned = ("tone", "emotion", "facial", "accent", "enthusiasm in voice")
    for c in crit:
        text = f"{c.get('what', '')} {c.get('id', '')}".lower()
        if any(b in text for b in banned):
            raise ValueError(f"rubric: criterion {c['id']!r} reads voice or face ({text.strip()}); score content only")


def label(transcript: Mapping[str, Any], rubric: Mapping[str, Any], scorer: Scorer) -> dict[str, Any]:
    validate(rubric)
    result = scorer.score(transcript, rubric)
    got = {c.id: c for c in result.criteria}
    rows, num, den, missing = [], 0.0, 0.0, []
    for c in rubric["criteria"]:
        w = float(c.get("weight", 1))
        s = got.get(c["id"])
        if s is None:
            missing.append(c["id"])
            rows.append({"id": c["id"], "weight": w, "score": None, "evidence": "no answer"})
            continue
        if not 1 <= s.score <= 5:
            raise ValueError(f"scorer returned {s.score} for {c['id']}; scores are 1–5")
        rows.append({"id": c["id"], "weight": w, "score": s.score, "evidence": s.evidence})
        num += w * s.score
        den += w
    total = round(num / den, 2) if den else None
    th = rubric.get("thresholds") or {}
    hire, maybe = float(th.get("hire", 4.0)), float(th.get("maybe", 3.0))
    if total is None:
        lab = "NO"
    elif total >= hire:
        lab = "HIRE"
    elif total >= maybe:
        lab = "MAYBE"
    else:
        lab = "NO"
    review = lab == "NO" or bool(missing)
    reasons = []
    if lab == "NO":
        reasons.append("NO label: a person reads the transcript before any rejection")
    if missing:
        reasons.append(f"missing answers: {', '.join(missing)}")
    return {
        "candidate": transcript.get("candidate", ""),
        "label": lab,
        "weighted_score": total,
        "criteria": rows,
        "needs_human_review": review,
        "review_reasons": reasons,
        "scorer_note": result.reason,
        "caveat": CAVEAT,
    }


def render(results: list[dict[str, Any]]) -> str:
    rows = [[r["candidate"], r["label"], "—" if r["weighted_score"] is None else f"{r['weighted_score']:.2f}",
             "yes" if r["needs_human_review"] else "", "; ".join(r["review_reasons"])] for r in results]
    out = ["## AI interview labels", "", md_table(["candidate", "label", "weighted score", "human review", "why"], rows, "llrll"), ""]
    notes = {r["scorer_note"] for r in results if r["scorer_note"]}
    for n in sorted(notes):
        out.append(f"- scorer: {n}")
    out.append(f"- ⚠ {CAVEAT}")
    return "\n".join(out) + "\n"
