"""Pluggable providers: avatar renderer, voice AI, transcriber, scorer.

hireburn ships interfaces, not integrations. Bring your own provider by writing a
small class with the methods below and pointing the CLI at it with
``--scorer package.module:ClassName``. No API keys live in this repository; read
yours from the environment inside your adapter.

Two offline implementations are included so the demo and the tests run without any
network: ``NoFollowUp`` / ``ScriptedFollowUp`` for the voice AI, and
``KeywordDemoScorer`` for scoring. ``KeywordDemoScorer`` is a toy for wiring things
up. It does not assess anyone; do not use it on real candidates.
"""

from __future__ import annotations

import importlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Protocol, runtime_checkable


@runtime_checkable
class AvatarRenderer(Protocol):
    """Turns one approved script clip into a video file. Called once per clip, offline."""

    def render(self, clip_id: str, text: str, out_dir: Path) -> Path: ...


@runtime_checkable
class VoiceAgent(Protocol):
    """Asks at most one short follow-up after an answer, or returns None to move on."""

    def follow_up(self, question: Mapping[str, Any], answer: str) -> str | None: ...


@runtime_checkable
class Transcriber(Protocol):
    def transcribe(self, audio_path: Path) -> str: ...


@dataclass
class CriterionScore:
    id: str
    score: float  # 1..5
    evidence: str = ""


@dataclass
class ScoreResult:
    criteria: list[CriterionScore]
    reason: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class Scorer(Protocol):
    """Scores the CONTENT of a transcript against the rubric. Must not use voice tone or face."""

    def score(self, transcript: Mapping[str, Any], rubric: Mapping[str, Any]) -> ScoreResult: ...


class NoFollowUp:
    def follow_up(self, question: Mapping[str, Any], answer: str) -> str | None:
        return None


class ScriptedFollowUp:
    """Replays follow-ups from a mapping {question_id: text}. For demos and tests."""

    def __init__(self, mapping: Mapping[str, str]):
        self.mapping = dict(mapping)

    def follow_up(self, question: Mapping[str, Any], answer: str) -> str | None:
        return self.mapping.get(str(question.get("id")))


class ManualScorer:
    """Scores typed in by a person, from a JSON file {criterion_id: score} or {criterion_id: {score, evidence}}."""

    def __init__(self, path: str | Path):
        self.data = json.loads(Path(path).read_text(encoding="utf-8"))

    def score(self, transcript: Mapping[str, Any], rubric: Mapping[str, Any]) -> ScoreResult:
        out = []
        for c in rubric["criteria"]:
            v = self.data.get(c["id"])
            if isinstance(v, Mapping):
                out.append(CriterionScore(c["id"], float(v["score"]), str(v.get("evidence", ""))))
            elif v is not None:
                out.append(CriterionScore(c["id"], float(v)))
        return ScoreResult(out, reason="scored by a person")


class KeywordDemoScorer:
    """DEMO ONLY. Counts rubric ``evidence_words`` in the answers to each question.

    It exists so the pipeline runs end to end with no network and no keys. It is not
    an assessment method and must not be used on real people.
    """

    def score(self, transcript: Mapping[str, Any], rubric: Mapping[str, Any]) -> ScoreResult:
        answers = {
            t.get("question_id"): f"{t.get('answer') or ''} {t.get('follow_up_answer') or ''}".lower()
            for t in transcript.get("turns", [])
        }
        out = []
        for c in rubric["criteria"]:
            text = answers.get(c.get("question_id"), "")
            if not text.strip():
                continue
            words = [w.lower() for w in c.get("evidence_words", [])]
            hits = sum(1 for w in words if w in text)
            score = 1 + min(4, round(4 * hits / max(1, len(words)) + 0.0001))
            out.append(CriterionScore(c["id"], float(score), f"{hits}/{len(words)} evidence words"))
        return ScoreResult(out, reason="keyword demo scorer — not an assessment")


def load_object(spec: str, *args: Any) -> Any:
    """Instantiate ``package.module:ClassName`` with optional constructor args."""
    if ":" not in spec:
        raise ValueError("provider spec must look like package.module:ClassName")
    mod, _, name = spec.partition(":")
    return getattr(importlib.import_module(mod), name)(*args)
