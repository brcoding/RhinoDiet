"""Token proxy. Whitespace and punctuation splits, no network, no model file."""

from __future__ import annotations

import re

_PARTS = re.compile(r"\w+|[^\w\s]", re.UNICODE)


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return len(_PARTS.findall(text))
