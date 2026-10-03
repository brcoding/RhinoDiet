"""Input and output compressors.

Caveman drops fluff. Ponytail keeps short sentences. Default is ponytail.
Protected spans keep identifiers, requirements, and error text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from rhinodiet.tokens import estimate_tokens

_MARK = "\ue000"

# Longer phrases first so shorter ones do not steal a prefix.
_PHRASES: tuple[tuple[str, str], ...] = (
    ("it is important to note that", ""),
    ("in spite of the fact that", "although"),
    ("due to the fact that", "because"),
    ("at this point in time", "now"),
    ("in the event that", "if"),
    ("the reason is that", "because"),
    ("has the ability to", "can"),
    ("for the purpose of", "to"),
    ("it should be noted that", ""),
    ("with regard to", "about"),
    ("in terms of", "for"),
    ("a large number of", "many"),
    ("in order to", "to"),
    ("as well as", "and"),
    ("could you please", ""),
    ("would you please", ""),
    ("i would like you to", ""),
    ("please note that", ""),
    ("make sure to", ""),
    ("be sure to", ""),
    ("needless to say", ""),
    ("at the end of the day", ""),
    ("in addition", "also"),
    ("a total of", ""),
)

_FILLER = frozenset(
    {
        "please",
        "kindly",
        "just",
        "really",
        "very",
        "basically",
        "actually",
        "literally",
        "simply",
        "currently",
        "honestly",
    }
)
_ARTICLES = frozenset({"a", "an", "the"})
_CAVEMAN_EXTRA = frozenset({"that", "of"})

_US = {
    "colour": "color",
    "colours": "colors",
    "favourite": "favorite",
    "favourites": "favorites",
    "organise": "organize",
    "organised": "organized",
    "organising": "organizing",
    "behaviour": "behavior",
    "behaviours": "behaviors",
    "honour": "honor",
    "honours": "honors",
    "licence": "license",
    "centre": "center",
    "theatre": "theater",
    "grey": "gray",
    "analyse": "analyze",
    "defence": "defense",
    "offence": "offense",
}

_FENCE = re.compile(r"```[\s\S]*?```")
# Span, not the whole line. A paragraph can mention an error and still compress.
_ERROR = re.compile(
    r"(?:Traceback \(most recent call last\):(?:\n[^\n]*){0,12})"
    r"|(?:[A-Za-z_][\w.]*(?:Error|Exception):[^\n.]*)",
    re.I,
)
_REQ = re.compile(
    r"[^.!?\n]*\b(?:must|shall|required|requirement|needs to)\b[^.!?\n]*[.!?]?",
    re.I,
)
_URL = re.compile(r"https?://[^\s)]+")
_INLINE = re.compile(r"`[^`\n]+`")
_PATH = re.compile(
    r"(?:(?:\.{1,2}|[\w.-]+)/(?:[\w.-]+/)*[\w.-]+\.[\w]+|(?:[\w.-]+/)+[\w.-]+)"
)
_IDENT = re.compile(
    r"\b(?:[A-Za-z][A-Za-z0-9]*_[A-Za-z0-9_]+|[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]+)+|[A-Z][A-Z0-9]{2,})\b"
)
_WORD = re.compile(r"\b[A-Za-z]+\b")


@dataclass(frozen=True)
class CompressResult:
    text: str
    before_tokens: int
    after_tokens: int
    mode: str

    @property
    def saved(self) -> int:
        return self.before_tokens - self.after_tokens


def compress(text: str, mode: str = "default") -> CompressResult:
    resolved = _resolve_mode(mode)
    before = estimate_tokens(text)
    if resolved == "tighten":
        out = _tighten(text)
    else:
        out = _compress_body(text, caveman=resolved == "caveman")
    return CompressResult(out, before, estimate_tokens(out), resolved)


def compress_output(text: str, mode: str = "caveman") -> CompressResult:
    return compress(text, mode)


def user_visible(text: str) -> str:
    return compress(text, "tighten").text


def _resolve_mode(mode: str) -> str:
    if mode == "default":
        return "ponytail"
    if mode not in {"ponytail", "caveman", "tighten"}:
        raise ValueError(f"unknown mode: {mode}")
    return mode


def _protect(text: str) -> tuple[str, list[str]]:
    slots: list[str] = []

    def take(match: re.Match[str]) -> str:
        slots.append(match.group(0))
        return f"{_MARK}{len(slots) - 1}{_MARK}"

    for pattern in (_FENCE, _ERROR, _REQ, _URL, _INLINE, _PATH, _IDENT):
        text = pattern.sub(take, text)
    return text, slots


def _restore(text: str, slots: list[str]) -> str:
    def put(match: re.Match[str]) -> str:
        return slots[int(match.group(1))]

    return re.sub(_MARK + r"(\d+)" + _MARK, put, text)


def _us(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        word = match.group(0)
        mapped = _US.get(word.lower())
        if not mapped:
            return word
        if word.isupper():
            return mapped.upper()
        if word[0].isupper():
            return mapped.capitalize()
        return mapped

    return _WORD.sub(repl, text)


def _semicolons_to_periods(text: str) -> str:
    text = re.sub(r"\s*;\s*", ". ", text)
    text = re.sub(r"\.(\s*)([a-z])", lambda m: ". " + m.group(2).upper(), text)
    return text


def _dashes(text: str) -> str:
    text = text.replace("\u2014", ", ").replace("\u2013", ", ")
    return re.sub(r"\s+,", ",", text)


def _tidy(text: str) -> str:
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r" +\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" +([,.:!?])", r"\1", text)
    text = re.sub(r"\s+,", ",", text)
    return text.strip()


def _tighten(text: str) -> str:
    text, slots = _protect(text)
    text = _dashes(text)
    text = _us(text)
    text = _semicolons_to_periods(text)
    return _restore(_tidy(text), slots)


def _apply_phrases(text: str) -> str:
    for src, dst in _PHRASES:
        text = re.sub(re.escape(src), dst, text, flags=re.I)
    return text


def _drop_words(text: str, caveman: bool) -> str:
    parts = re.split(r"(\s+)", text)
    kept: list[str] = []
    for part in parts:
        if not part or part.isspace() or _MARK in part:
            kept.append(part)
            continue
        bare = re.sub(r"^[^\w]+|[^\w]+$", "", part).lower()
        if bare in _FILLER:
            continue
        if caveman and (bare in _ARTICLES or bare in _CAVEMAN_EXTRA):
            continue
        kept.append(part)
    return "".join(kept)


def _compress_body(text: str, caveman: bool) -> str:
    text, slots = _protect(text)
    text = _apply_phrases(text)
    text = _dashes(text)
    text = _us(text)
    text = _semicolons_to_periods(text)
    text = _drop_words(text, caveman=caveman)
    return _restore(_tidy(text), slots)
