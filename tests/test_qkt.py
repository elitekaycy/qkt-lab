"""qkt subprocess output parsing, including JVM logs before JSON errors."""

from __future__ import annotations

import json

import pytest

from lab.qkt import _parse_json_output


def test_parse_clean_object_and_array():
    assert _parse_json_output('{"ok":true}') == {"ok": True}
    assert _parse_json_output('[{"ticket":1}]') == [{"ticket": 1}]


def test_parse_final_json_after_jvm_logs():
    out = "\n".join(
        [
            "12:17:55.049 [main] WARN MT5Client GET failed",
            "java.net.UnknownHostException: mt5-gateway",
            "\tat okhttp3.RealCall.execute(RealCall.kt:154)",
            '{"ok":false,"error":"venue account read failed"}',
        ]
    )
    assert _parse_json_output(out) == {
        "ok": False,
        "error": "venue account read failed",
    }


def test_parse_output_without_json_raises():
    with pytest.raises(json.JSONDecodeError):
        _parse_json_output("warning only")
