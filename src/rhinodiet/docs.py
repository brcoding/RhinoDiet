"""Technical writer. About 30 percent shorter, active voice, facts unchanged."""

from __future__ import annotations

import re
from dataclasses import dataclass

from rhinodiet.compress import user_visible
from rhinodiet.tokens import estimate_tokens

_MARK = "\ue000"

_PHRASES: tuple[tuple[str, str], ...] = (
    ("it is important to note that", ""),
    ("it should be noted that", ""),
    ("please note that", ""),
    ("at this point in time", "now"),
    ("in the event that", "if"),
    ("due to the fact that", "because"),
    ("in order to", "to"),
    ("each and every", "each"),
    ("the reason is that", "because"),
    ("for the purpose of", "to"),
)

_FILLER = frozenset(
    {
        "please",
        "just",
        "really",
        "very",
        "basically",
        "actually",
        "simply",
        "currently",
        "totally",
        "completely",
    }
)

# Present, then past. Unknown verbs stay passive so we do not invent a stem.
_VERBS = {
    "validated": ("validates", "validated"),
    "rejected": ("rejects", "rejected"),
    "performed": ("performs", "performed"),
    "returned": ("returns", "returned"),
    "created": ("creates", "created"),
    "stored": ("stores", "stored"),
    "written": ("writes", "wrote"),
    "loaded": ("loads", "loaded"),
    "called": ("calls", "called"),
    "checked": ("checks", "checked"),
    "updated": ("updates", "updated"),
    "removed": ("removes", "removed"),
    "added": ("adds", "added"),
    "required": ("requires", "required"),
    "provided": ("provides", "provided"),
    "handled": ("handles", "handled"),
    "executed": ("executes", "executed"),
    "generated": ("generates", "generated"),
    "compressed": ("compresses", "compressed"),
    "configured": ("configures", "configured"),
    "accepted": ("accepts", "accepted"),
    "parsed": ("parses", "parsed"),
    "saved": ("saves", "saved"),
    "raised": ("raises", "raised"),
    "repeated": ("repeats", "repeated"),
    "used": ("uses", "used"),
    "processed": ("processes", "processed"),
    "sent": ("sends", "sent"),
    "read": ("reads", "read"),
    "kept": ("keeps", "kept"),
}

_STOP = "if|when|and|or|to|for|then|again|now|because"
_WORD = r"[A-Za-z0-9_-]+"
_PASSIVE = re.compile(
    rf"\b(?P<obj>(?:the|a|an)\s+{_WORD}"
    rf"(?:\s+(?!is\b|are\b|was\b|were\b){_WORD}){{0,6}})\s+"
    rf"(?P<be>is|are|was|were)\s+"
    rf"(?P<verb>[A-Za-z]+)\s+by\s+"
    rf"(?P<subj>(?:the|a|an)\s+{_WORD}"
    rf"(?:\s+(?!{_STOP}\b){_WORD}){{0,4}})",
    re.I,
)
_FENCE = re.compile(r"```[\s\S]*?```")
_ERROR = re.compile(
    r"(?:Traceback \(most recent call last\):(?:\n[^\n]*){0,12})"
    r"|(?:[A-Za-z_][\w.]*(?:Error|Exception):[^\n.]*)",
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
_NUMBER = re.compile(r"\b\d{2,}\b")


@dataclass(frozen=True)
class DocsResult:
    text: str
    before_tokens: int
    after_tokens: int

    @property
    def saved_ratio(self) -> float:
        if not self.before_tokens:
            return 0.0
        return 1 - (self.after_tokens / self.before_tokens)

    @property
    def summary_line(self) -> str:
        return f"Docs pass. {self.before_tokens} to {self.after_tokens} tokens."


class DocsWriter:
    """Worker-tier writer. The supervisor calls this. It does not live in the supervisor."""

    def run(self, text: str) -> DocsResult:
        return rewrite_technical(text)


def rewrite_technical(text: str) -> DocsResult:
    before = estimate_tokens(text)
    masked, slots = _protect(text)
    masked = _phrases(masked)
    masked = _drop_filler(masked)
    masked = _PASSIVE.sub(_activate, masked)
    masked = _drop_redundant_again(masked)
    out = _cap_sentences(user_visible(_restore(masked, slots)))
    return DocsResult(out, before, estimate_tokens(out))


def _protect(text: str) -> tuple[str, list[str]]:
    slots: list[str] = []

    def take(match: re.Match[str]) -> str:
        slots.append(match.group(0))
        return f"{_MARK}{len(slots) - 1}{_MARK}"

    for pattern in (_FENCE, _ERROR, _URL, _INLINE, _PATH, _IDENT, _NUMBER):
        text = pattern.sub(take, text)
    return text, slots


def _restore(text: str, slots: list[str]) -> str:
    def put(match: re.Match[str]) -> str:
        return slots[int(match.group(1))]

    return re.sub(_MARK + r"(\d+)" + _MARK, put, text)


def _phrases(text: str) -> str:
    for src, dst in _PHRASES:
        text = re.sub(re.escape(src), dst, text, flags=re.I)
    return text


def _activate(match: re.Match[str]) -> str:
    verb = match.group("verb").lower()
    forms = _VERBS.get(verb)
    if not forms:
        return match.group(0)
    be = match.group("be").lower()
    active = forms[1] if be in {"was", "were"} else forms[0]
    obj = match.group("obj")
    if obj[0].isupper():
        obj = obj[0].lower() + obj[1:]
    return f"{match.group('subj')} {active} {obj}"


def _drop_filler(text: str) -> str:
    parts = re.split(r"(\s+)", text)
    kept: list[str] = []
    for part in parts:
        if not part or part.isspace() or _MARK in part:
            kept.append(part)
            continue
        bare = re.sub(r"^[^\w]+|[^\w]+$", "", part).lower()
        if bare in _FILLER:
            continue
        kept.append(part)
    return "".join(kept)


def _drop_redundant_again(text: str) -> str:
    sentences = re.split(r"([.!?])", text)
    out: list[str] = []
    for chunk in sentences:
        if re.search(r"\brepeats?\b", chunk, re.I):
            chunk = re.sub(r"\bagain\b", "", chunk, flags=re.I)
            chunk = re.sub(r"\bthe same\b", "the", chunk, flags=re.I)
        out.append(chunk)
    return "".join(out)


def _cap_sentences(text: str) -> str:
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\s+([,.:!?])", r"\1", text)
    text = text.strip()
    parts = re.split(r"([.!?]\s+)", text)

    def cap(chunk: str) -> str:
        for index, char in enumerate(chunk):
            if char.isalpha():
                return chunk[:index] + char.upper() + chunk[index + 1 :]
        return chunk

    built: list[str] = []
    start = True
    for part in parts:
        if start:
            part = cap(part)
            start = False
        if re.fullmatch(r"[.!?]\s+", part):
            start = True
        built.append(part)
    return "".join(built).strip()
