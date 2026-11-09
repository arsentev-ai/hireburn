# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed
- Disclosure checklist: the EU notice is split in two. `tell_ai_used` now cites Art. 26(11)
  (deployer of an Annex III system informs the people it decides about); the new
  `tell_interacting_with_ai` cites Art. 50(1) and 50(5) (provider duty, at the latest at the
  first interaction). `alternative` and `human_reads_before_reject` are framed as safeguards
  supporting human oversight under Art. 14 and 26(2), not as steps the Act names.
  Thanks to the awesome-eu-ai-act review.

## [0.1.1] — 2026-11-05

### Fixed
- `hireburn demo` after `pip install hireburn`: the synthetic example company now ships inside
  the package, so the demo runs without a clone of the repository.

### Added
- GitHub Actions workflow that publishes to PyPI through Trusted Publishing (no API tokens).

## [0.1.0] — 2026-11-05

### Added
- `hireburn avatar`: recording checklist, recording script with an AI-disclosure opening and
  clip-length warnings, interview plan with at most one voice-AI follow-up per question, a
  single-file candidate page that will not build without the disclosure facts and gates Start
  behind consent, and a transcript rubric (HIRE / MAYBE / NO) that flags every NO for human
  review and refuses voice- or face-based criteria.
- Provider interfaces (`AvatarRenderer`, `VoiceAgent`, `Transcriber`, `Scorer`), a
  `ManualScorer` and an offline `KeywordDemoScorer` for the demo only.
- `hireburn outreach`: personal drafts that require a human-written hook, a human-pace queue
  (random pauses with millisecond jitter, hourly and daily caps, working hours, periodic
  breaks), a live pacer that checks the real action log, a STOP switch with a 48-hour
  cool-down, and a reply / follow-up tracker. Nothing is sent by the tool.
- `hireburn funnel`, `labels`, `disclosure`: losses per stage, show-up and completion rates,
  AI label against who is working on day N with a Fisher exact test, decision lag with an
  equal-window view, and a disclosure checklist against NYC LL 144, Illinois AIVIA,
  Illinois HB 3773 and the EU AI Act.
- `hireburn demo` on a synthetic example company; tests; CITATION.cff, codemeta.json, Dockerfile.
