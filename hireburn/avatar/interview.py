"""Interview plan: pre-recorded clips + at most ONE voice-AI follow-up per question.

Why the cap: the avatar is a recording, so every question is asked the same way to
every candidate — that is what makes answers comparable. A live voice AI is only
allowed one short clarification per question. More than one turns a structured
interview into an unstructured chat whose content differs per candidate.

``plan`` builds the step list a player follows. ``run`` drives a plan with any
``VoiceAgent`` and a function that returns the candidate's answer, and refuses to
ask a second follow-up even if the agent offers one.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping

from hireburn.avatar.providers import VoiceAgent
from hireburn.avatar.script import build

MAX_FOLLOW_UPS = 1


def plan(cfg: Mapping[str, Any]) -> dict[str, Any]:
    clips = build(cfg)
    steps: list[dict[str, Any]] = [{"step": "disclosure_and_consent", "requires": "consent checkbox ticked"},
                                   {"step": "play", "clip": "00-intro"}]
    for n, q in enumerate(cfg["questions"], 1):
        cap = int(q.get("max_followups", MAX_FOLLOW_UPS))
        if cap > MAX_FOLLOW_UPS or cap < 0:
            raise ValueError(f"question {n}: max_followups={cap}; hireburn allows 0 or 1")
        qid = q.get("id", f"q{n}")
        steps.append({"step": "play", "clip": f"{n:02d}-{qid}"})
        steps.append({"step": "record_answer", "question_id": qid, "re_record": True,
                      "max_seconds": int(q.get("max_answer_seconds", 120))})
        if cap:
            steps.append({"step": "optional_follow_up", "question_id": qid, "source": "voice AI", "max": 1})
        if n < len(cfg["questions"]):
            steps.append({"step": "play", "clip": f"{n:02d}t-transition"})
    steps.append({"step": "play", "clip": "90-closing"})
    steps.append({"step": "candidate_questions", "note": "optional free-form questions, recorded for a person to answer"})
    return {"clips": [c.id for c in clips], "steps": steps, "max_follow_ups_per_question": MAX_FOLLOW_UPS}


def run(cfg: Mapping[str, Any], agent: VoiceAgent, answer: Callable[[str, str], str]) -> dict[str, Any]:
    """Simulate one interview. ``answer(question_id, prompt_text)`` returns the candidate's reply."""
    turns = []
    for n, q in enumerate(cfg["questions"], 1):
        qid = q.get("id", f"q{n}")
        a = answer(qid, q["text"])
        turn: dict[str, Any] = {"question_id": qid, "question": q["text"], "answer": a,
                                "follow_up": None, "follow_up_answer": None}
        if int(q.get("max_followups", MAX_FOLLOW_UPS)) >= 1:
            fu = agent.follow_up(q, a)
            if fu:
                turn["follow_up"] = fu
                turn["follow_up_answer"] = answer(qid + ":follow_up", fu)
                # a second follow-up is never asked, whatever the agent returns
        turns.append(turn)
    return {"turns": turns}
