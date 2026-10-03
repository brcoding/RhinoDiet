from rhinodiet.compress import compress

from support import FLUFFY


FACTS = (
    "UserToken",
    "src/auth/session.py",
    "must reject expired tokens",
    "TokenExpiredError: token exp 1710000000",
)


def test_modes_shrink_and_keep_facts():
    default = compress(FLUFFY, "default")
    ponytail = compress(FLUFFY, "ponytail")
    caveman = compress(FLUFFY, "caveman")
    assert default.mode == "ponytail"
    assert default.text == ponytail.text
    assert default.after_tokens < default.before_tokens
    assert caveman.after_tokens <= ponytail.after_tokens
    assert caveman.after_tokens < caveman.before_tokens
    for result in (default, ponytail, caveman):
        for fact in FACTS:
            assert fact in result.text
        assert "\u2014" not in result.text
        assert "it is important to note that" not in result.text.lower()


def test_error_span_does_not_swallow_the_paragraph():
    raw = "Please really just " + ("very " * 30) + "look now. TokenExpiredError: token exp 1."
    result = compress(raw, "caveman")
    assert result.after_tokens < result.before_tokens
    assert "TokenExpiredError: token exp 1" in result.text


def test_output_compression_and_tighten():
    raw = "Please really use colour here. Wait; stop. Range is 1\u20143. Keep `a; b` in code."
    tightened = compress(raw, "tighten")
    assert "color" in tightened.text
    assert "colour" not in tightened.text
    assert "\u2014" not in tightened.text
    assert "`a; b`" in tightened.text
    assert "Wait. Stop." in tightened.text
    inter = compress(FLUFFY, "caveman")
    assert inter.saved > 0


def test_unknown_mode():
    try:
        compress("hello", "telegraph")
    except ValueError as exc:
        assert "unknown mode" in str(exc)
    else:
        raise AssertionError("expected ValueError")
