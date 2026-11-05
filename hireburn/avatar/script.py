"""Recording script: everything the avatar will ever say, recorded once.

Input (``interview.yaml``)::

    company: Example Company (synthetic)
    role: Customer support associate
    minutes: 20
    interviewer: {name: Alex Example, title: Head of Support}
    alternative_contact: hiring@example.com
    retention_days: 90
    questions:
      - id: q1
        text: How would you explain a delayed delivery to a customer?
        listen_for: a clear, step-by-step explanation

The script has fixed clips: an opening that discloses the avatar, one clip per
question, a transition after every question but the last, a closing, and three
fallbacks (did not hear you, technical problem, prefer a person). Each clip has a
target length; the script warns when the text will not fit at a calm pace.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

WORDS_PER_SECOND = 2.3  # calm speaking pace

TEMPLATES = {
    "intro": (
        "Hi, I'm {name}, {title} at {company}. Before we start, one thing you should know: the person "
        "on this screen is an AI avatar made from my recordings. You are not talking to me live. "
        "Short follow-up questions come from a voice AI. A person on our team reads every answer — "
        "the AI does not decide on its own. This takes about {minutes} minutes, you can re-record any "
        "answer, and if you would rather talk to a person, use the link under the video."
    ),
    "transition": [
        "Thank you. Next question.",
        "Got it, thanks. Let's move on.",
        "Thanks, that's helpful. Here's the next one.",
        "Appreciate it. One more area I'd like to cover.",
        "Thank you. Let's keep going.",
    ],
    "closing": (
        "That's everything. Thank you for your time, {first_name_placeholder}. A person from our team will "
        "read your answers and get back to you within {reply_days} working days. If you have questions, "
        "the contact is under the video."
    ),
    "fx_repeat": "Sorry, I didn't catch that. Could you record your answer again?",
    "fx_tech": "Something seems to have gone wrong on our side. Reload the page — your earlier answers are saved.",
    "fx_human": "Of course. Use the link under the video and a person from our team will set up a call instead.",
}

TARGET_SECONDS = {"intro": 45, "question": 30, "transition": 6, "closing": 20, "fx": 10}


@dataclass
class Clip:
    id: str
    kind: str
    text: str
    target_seconds: int
    estimated_seconds: float
    warning: str = ""


def _need(cfg: Mapping[str, Any], *keys: str) -> None:
    missing = [k for k in keys if not cfg.get(k)]
    if missing:
        raise ValueError(f"interview config: missing {', '.join(missing)}")


def build(cfg: Mapping[str, Any]) -> list[Clip]:
    _need(cfg, "company", "role", "interviewer", "questions")
    who = cfg["interviewer"]
    if not who.get("name"):
        raise ValueError("interview config: interviewer.name is required — the avatar must say whose recordings these are")
    values = {
        "name": who["name"],
        "title": who.get("title", "hiring manager"),
        "company": cfg["company"],
        "minutes": cfg.get("minutes", 20),
        "reply_days": cfg.get("reply_days", 3),
        "first_name_placeholder": "and good luck",
    }
    clips: list[Clip] = []

    def add(cid: str, kind: str, text: str, target_key: str) -> None:
        est = round(len(text.split()) / WORDS_PER_SECOND, 1)
        target = TARGET_SECONDS[target_key]
        warn = f"~{est:.0f}s spoken, target {target}s — shorten" if est > target * 1.15 else ""
        clips.append(Clip(cid, kind, text, target, est, warn))

    add("00-intro", "intro", TEMPLATES["intro"].format(**values), "intro")
    questions = cfg["questions"]
    if not 1 <= len(questions) <= 8:
        raise ValueError("interview config: use 1–8 questions (five is a good default)")
    for n, q in enumerate(questions, 1):
        if not q.get("text"):
            raise ValueError(f"question {n}: empty text")
        add(f"{n:02d}-{q.get('id', f'q{n}')}", "question", q["text"].strip(), "question")
        if n < len(questions):
            t = TEMPLATES["transition"][(n - 1) % len(TEMPLATES["transition"])]
            add(f"{n:02d}t-transition", "transition", t, "transition")
    closing = TEMPLATES["closing"].replace(", {first_name_placeholder}", "")
    add("90-closing", "closing", closing.format(**values), "closing")
    for k in ("fx_repeat", "fx_tech", "fx_human"):
        add(f"95-{k.replace('_', '-')}", "fallback", TEMPLATES[k], "fx")
    return clips


def render(clips: list[Clip], cfg: Mapping[str, Any]) -> str:
    total = sum(c.estimated_seconds for c in clips)
    out = [f"# Recording script — {cfg['role']} · {cfg['company']}", "",
           f"{len(clips)} clips, about {total / 60:.1f} minutes of speech. Record each clip as a separate file "
           "named by its id. Read naturally; small stumbles are fine — they sound human.", ""]
    for c in clips:
        out.append(f"## `{c.id}` — {c.kind} · target {c.target_seconds}s · ~{c.estimated_seconds:.0f}s")
        out.append("")
        out.append(c.text)
        if c.warning:
            out.append("")
            out.append(f"⚠ {c.warning}")
        out.append("")
    return "\n".join(out)


def to_json(clips: list[Clip]) -> list[dict[str, Any]]:
    return [asdict(c) for c in clips]
