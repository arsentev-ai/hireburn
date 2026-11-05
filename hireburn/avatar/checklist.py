"""Recording checklist for the record-once avatar.

Most people put off recording an avatar because they expect a studio. You need a
window, a phone and twenty minutes. The checklist keeps the clips usable by any
avatar provider and keeps the person who is recorded in control of their likeness.
"""

CHECKLIST: dict[str, list[str]] = {
    "Consent and likeness": [
        "The person recorded signs a written consent for an AI avatar of their face and voice, for hiring use only",
        "Consent says how long the avatar may be used and how to withdraw it; withdrawal deletes the avatar",
        "The avatar is never used to say anything the person has not read and approved (this script only)",
    ],
    "Light": [
        "Face a window or a soft light at eye level; no light source behind you",
        "Even light on both sides of the face, no hard shadows under the eyes",
        "Record all clips in one session so the light does not change between them",
    ],
    "Sound": [
        "Quiet room with soft furnishings; turn off fans, notifications and air conditioning",
        "Microphone 20–30 cm from the mouth (a wired lavalier or the phone on a stand is enough)",
        "Record 10 seconds of room silence first — providers use it to clean noise",
        "Peaks around −12 dB, never clipping; listen back to the first clip on headphones",
    ],
    "Framing": [
        "Camera at eye level, head and shoulders, eyes on the upper third line",
        "Plain, tidy background without logos or anything you would not want in every interview",
        "Same clothes, same seat, same distance for every clip; 1080p or better, 25–30 fps",
    ],
    "Delivery": [
        "Look into the lens, not at the screen",
        "Start each clip with 1 second of neutral silence and end with a light smile and 1 second of stillness",
        "Calm pace (about 140 words a minute); pauses are fine, rushing is not",
        "Read the disclosure in the opening clip exactly as written — it is the feature, not small print",
    ],
    "Clip length": [
        "Opening ≤ 45 s, each question ≤ 30 s, transitions ≤ 6 s, closing ≤ 20 s, fallbacks ≤ 10 s",
        "One file per clip, named by the clip id from the script (e.g. 03-q3.mp4)",
        "Keep the raw recordings; re-render the avatar later instead of re-recording",
    ],
}


def render() -> str:
    out = ["# Avatar recording checklist", ""]
    for section, items in CHECKLIST.items():
        out.append(f"## {section}")
        out.append("")
        out.extend(f"- [ ] {i}" for i in items)
        out.append("")
    return "\n".join(out)
