"""Input loading and Markdown output.

CSV, JSON and a small YAML subset. The YAML reader is built in so the tool runs on
a stock ``python3``: block maps, block lists (including lists of maps), quoted and
plain scalars, ``|`` / ``>`` block strings, ``[a, b]`` inline lists and comments.
Anything fancier (anchors, tags, multi-document files) — use JSON instead.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any, Iterable, Sequence

__all__ = ["load", "read_csv", "load_yaml", "md_table", "pct"]


def load(path: str | Path) -> Any:
    """Load a CSV (list of dicts), JSON or YAML file by its extension."""
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix in (".csv", ".tsv"):
        return read_csv(p)
    text = p.read_text(encoding="utf-8")
    if suffix == ".json":
        return json.loads(text)
    if suffix in (".yaml", ".yml"):
        return load_yaml(text)
    raise ValueError(f"{p}: unsupported file type {suffix!r} (use .csv, .json, .yaml)")


def read_csv(path: str | Path) -> list[dict[str, str]]:
    """Read a CSV into a list of dicts. Blank rows and rows starting with ``#`` are skipped."""
    p = Path(path)
    delimiter = "\t" if p.suffix.lower() == ".tsv" else ","
    rows: list[dict[str, str]] = []
    with p.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(
            (line for line in fh if line.strip() and not line.lstrip().startswith("#")),
            delimiter=delimiter,
        )
        for row in reader:
            clean = {(k or "").strip(): (v or "").strip() for k, v in row.items() if k is not None}
            if any(clean.values()):
                rows.append(clean)
    return rows


# --------------------------------------------------------------------------- YAML subset

_KEY_RE = re.compile(r"""^("(?:[^"\\]|\\.)*"|'(?:[^']|'')*'|[^\s#'"][^:#]*?)\s*:(?:\s+(.*))?$""")


def _strip_comment(s: str) -> str:
    out, quote = [], None
    for i, ch in enumerate(s):
        if quote:
            out.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in "'\"" and (i == 0 or s[i - 1] in " :[,-"):
            quote = ch
        elif ch == "#" and (i == 0 or s[i - 1] in " \t"):
            break
        out.append(ch)
    return "".join(out).rstrip()


def _scalar(raw: str) -> Any:
    s = raw.strip()
    if s == "":
        return None
    if s[0] == '"' and s[-1] == '"' and len(s) >= 2:
        return json.loads(s)
    if s[0] == "'" and s[-1] == "'" and len(s) >= 2:
        return s[1:-1].replace("''", "'")
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        return [] if not inner else [_scalar(part) for part in _split_flow(inner)]
    if s.startswith("{") and s.endswith("}"):
        inner = s[1:-1].strip()
        out = {}
        for part in (_split_flow(inner) if inner else []):
            m = _KEY_RE.match(part)
            if not m:
                raise ValueError(f"YAML: cannot read {part!r} in {s!r}")
            out[str(_scalar(m.group(1)))] = _scalar(m.group(2) or "")
        return out
    low = s.lower()
    if low in ("true",):
        return True
    if low in ("false",):
        return False
    if low in ("null", "~"):
        return None
    if re.fullmatch(r"[-+]?\d+", s):
        return int(s)
    if re.fullmatch(r"[-+]?(\d+\.\d*|\.\d+|\d+)([eE][-+]?\d+)?", s):
        return float(s)
    return s


def _split_flow(s: str) -> list[str]:
    parts, buf, quote, depth = [], [], None, 0
    for ch in s:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
            buf.append(ch)
        elif ch in "[{":
            depth += 1
            buf.append(ch)
        elif ch in "]}":
            depth -= 1
            buf.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    parts.append("".join(buf))
    return [p.strip() for p in parts]


class _MiniYAML:
    def __init__(self, text: str):
        self.raw = text.replace("\t", "    ").splitlines()
        self.lines: list[tuple[int, str, int]] = []  # (indent, content, raw index)
        for idx, line in enumerate(self.raw):
            content = _strip_comment(line)
            if not content.strip() or content.strip() in ("---", "..."):
                continue
            self.lines.append((len(content) - len(content.lstrip(" ")), content.strip(), idx))

    def parse(self) -> Any:
        if not self.lines:
            return None
        value, i = self._block(0, self.lines[0][0])
        if i != len(self.lines):
            raise ValueError(f"YAML: unexpected indentation at line {self.lines[i][2] + 1}")
        return value

    def _block(self, i: int, indent: int) -> tuple[Any, int]:
        content = self.lines[i][1]
        if content == "-" or content.startswith("- "):
            return self._list(i, indent)
        return self._map(i, indent)

    def _list(self, i: int, indent: int) -> tuple[list, int]:
        out: list = []
        while i < len(self.lines):
            ind, content, raw = self.lines[i]
            if ind != indent or not (content == "-" or content.startswith("- ")):
                break
            item = content[1:].strip()
            if not item:
                if i + 1 < len(self.lines) and self.lines[i + 1][0] > indent:
                    value, i = self._block(i + 1, self.lines[i + 1][0])
                else:
                    value, i = None, i + 1
            elif _KEY_RE.match(item) and not item.startswith("["):
                offset = indent + (len(content) - len(item))
                self.lines[i] = (offset, item, raw)
                value, i = self._map(i, offset)
            else:
                value, i = _scalar(item), i + 1
            out.append(value)
        return out, i

    def _block_scalar(self, i: int, indent: int, style: str) -> tuple[str, int]:
        raw_idx = self.lines[i][2]
        body: list[str] = []
        j = raw_idx + 1
        base = None
        while j < len(self.raw):
            line = self.raw[j].replace("\t", "    ")
            if line.strip():
                ind = len(line) - len(line.lstrip(" "))
                if ind <= indent:
                    break
                base = ind if base is None else min(base, ind)
            body.append(line)
            j += 1
        while body and not body[-1].strip():
            body.pop()
        base = base or 0
        text_lines = [ln[base:] if ln.strip() else "" for ln in body]
        if style.startswith(">"):
            text = ""
            for ln in text_lines:
                if not ln:
                    text += "\n"
                else:
                    text += ("" if not text or text.endswith("\n") else " ") + ln
        else:
            text = "\n".join(text_lines)
        if not style.endswith("-"):
            text += "\n"
        k = i + 1
        while k < len(self.lines) and self.lines[k][2] < j:
            k += 1
        return text, k

    def _map(self, i: int, indent: int) -> tuple[dict, int]:
        out: dict = {}
        while i < len(self.lines):
            ind, content, raw = self.lines[i]
            if ind != indent or content == "-" or content.startswith("- "):
                break
            m = _KEY_RE.match(content)
            if not m:
                raise ValueError(f"YAML: cannot read line {raw + 1}: {content!r}")
            key = _scalar(m.group(1))
            key = str(key) if not isinstance(key, str) else key
            rest = (m.group(2) or "").strip()
            if rest in ("|", "|-", ">", ">-"):
                out[key], i = self._block_scalar(i, ind, rest)
                continue
            if rest:
                out[key] = _scalar(rest)
                i += 1
                continue
            nxt = self.lines[i + 1] if i + 1 < len(self.lines) else None
            if nxt and nxt[0] > indent:
                out[key], i = self._block(i + 1, nxt[0])
            elif nxt and nxt[0] == indent and (nxt[1] == "-" or nxt[1].startswith("- ")):
                out[key], i = self._list(i + 1, indent)
            else:
                out[key], i = None, i + 1
        return out, i


def load_yaml(text: str) -> Any:
    """Parse the YAML subset described in the module docstring."""
    return _MiniYAML(text).parse()


# --------------------------------------------------------------------------- output


def pct(num: float, den: float, digits: int = 1) -> str:
    """Format a share as a percentage, or an em dash when the denominator is zero."""
    if not den:
        return "—"
    return f"{100.0 * num / den:.{digits}f}%"


def md_table(headers: Sequence[str], rows: Iterable[Sequence[Any]], align: str | None = None) -> str:
    """Render a Markdown table. ``align`` is a string of l/r per column (default: first l, rest r)."""
    rows = [["" if c is None else str(c) for c in r] for r in rows]
    headers = [str(h) for h in headers]
    align = align or ("l" + "r" * (len(headers) - 1))
    widths = [max([3, len(h)] + [len(r[i]) for r in rows]) for i, h in enumerate(headers)]

    def fmt(cells: Sequence[str]) -> str:
        out = []
        for i, c in enumerate(cells):
            out.append(c.rjust(widths[i]) if align[i] == "r" else c.ljust(widths[i]))
        return "| " + " | ".join(out) + " |"

    sep = ["-" * (w - 1) + ":" if align[i] == "r" else "-" * w for i, w in enumerate(widths)]
    return "\n".join([fmt(headers), "|" + "|".join(f" {s} " for s in sep) + "|"] + [fmt(r) for r in rows])
