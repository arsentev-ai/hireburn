"""Personal LinkedIn messages from templates and candidate cards.

Input::

    # templates.yaml
    note_max_chars: 200          # connection-note limit; check LinkedIn's current one
    message_max_chars: 1000
    required_fields: [first_name, hook]
    templates:
      connect: "Hi {first_name} — {hook} We're hiring a {role}; open to a short chat?"
      first: |
        Hi {first_name}, {hook} ...
      follow_up_1: ...

    # candidates.csv
    id,first_name,profile_url,role,hook
    p01,Sam,https://www.linkedin.com/in/example-sam,support associate,"Your write-up on ..."

``hook`` is one sentence a person wrote after actually reading the profile. A draft
without it is refused: personalisation is the point, and a mail-merge that only swaps
the first name reads as spam to candidates and to LinkedIn alike.
"""

from __future__ import annotations

import re
import string
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Mapping

SPAMMY = ("guaranteed", "act now", "limited time", "100%", "click here", "dear candidate", "!!!")
_FIELD = re.compile(r"{(\w+)}")


@dataclass
class Draft:
    id: str
    candidate_id: str
    profile_url: str
    kind: str
    text: str
    chars: int
    warnings: list[str] = field(default_factory=list)


class MissingField(ValueError):
    pass


def fields(template: str) -> set[str]:
    return {f for _, f, _, _ in string.Formatter().parse(template) if f}


def render_one(template: str, card: Mapping[str, Any], required: Iterable[str] = ()) -> str:
    need = set(fields(template)) | set(required)
    missing = sorted(k for k in need if not str(card.get(k, "") or "").strip())
    if missing:
        raise MissingField(f"candidate {card.get('id', '?')}: empty {', '.join(missing)}")
    text = template.format_map({k: str(v).strip() for k, v in card.items()})
    return re.sub(r"[ \t]+\n", "\n", text).strip()


def lint(text: str, kind: str, cfg: Mapping[str, Any]) -> list[str]:
    warns = []
    limit = int(cfg.get("note_max_chars", 200)) if kind == "connect" else int(cfg.get("message_max_chars", 1000))
    if len(text) > limit:
        warns.append(f"{len(text)} chars > {limit} limit for {kind}")
    low = text.lower()
    for s in SPAMMY:
        if s in low:
            warns.append(f"spammy phrase: {s!r}")
    if _FIELD.search(text):
        warns.append("unfilled placeholder left in text")
    if "http" in low and kind == "connect":
        warns.append("links in a connection note look like spam")
    return warns


def draft_all(cards: Iterable[Mapping[str, Any]], cfg: Mapping[str, Any], kinds: Iterable[str] = ("first",)) -> tuple[list[Draft], list[str]]:
    templates = cfg.get("templates") or {}
    required = cfg.get("required_fields") or ["first_name", "hook"]
    drafts, errors = [], []
    seen: set[str] = set()
    for card in cards:
        cid = str(card.get("id", "")).strip()
        if not cid:
            errors.append("a candidate card has no id")
            continue
        if cid in seen:
            errors.append(f"candidate {cid}: duplicate card, skipped")
            continue
        seen.add(cid)
        if str(card.get("do_not_contact", "")).strip().lower() in ("yes", "true", "1"):
            errors.append(f"candidate {cid}: do_not_contact, skipped")
            continue
        for kind in kinds:
            if kind not in templates:
                raise ValueError(f"no template {kind!r} in templates file")
            try:
                text = render_one(templates[kind], card, required)
            except MissingField as e:
                errors.append(str(e))
                continue
            drafts.append(Draft(f"{cid}:{kind}", cid, str(card.get("profile_url", "")), kind, text, len(text),
                                lint(text, kind, cfg)))
    return drafts, errors


def to_json(drafts: list[Draft]) -> list[dict[str, Any]]:
    return [asdict(d) for d in drafts]
