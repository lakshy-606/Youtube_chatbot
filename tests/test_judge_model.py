"""eval/judge_model.py — _parse_retry_after_seconds(), a pure function. Regression test for a
real Phase 7 bug: the original regex only captured a plain "Y.Zs" wait and silently mis-parsed
Groq's "XmY.Zs" form (used for longer, daily-quota-scale waits) as just the seconds part —
verified against the exact real RateLimitError message text hit live during Phase 7's eval run.
"""
from eval.judge_model import _parse_retry_after_seconds

_REAL_TPD_ERROR = (
    "Error code: 429 - {'error': {'message': 'Rate limit reached for model "
    "`openai/gpt-oss-20b` in organization `org_xxx` service tier `on_demand` on tokens per day "
    "(TPD): Limit 200000, Used 198924, Requested 1676. Please try again in 4m19.2s. Need more "
    "tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', "
    "'type': 'tokens', 'code': 'rate_limit_exceeded'}}"
)


def test_parses_minutes_and_seconds_form():
    # 4m19.2s = 259.2s, plus the function's own +1.0s safety margin.
    assert _parse_retry_after_seconds(_REAL_TPD_ERROR, default=0.0) == 260.2


def test_parses_plain_seconds_form():
    message = "Rate limit reached. Please try again in 12.3s."
    assert _parse_retry_after_seconds(message, default=0.0) == 13.3


def test_parses_hours_minutes_seconds_form():
    message = "Please try again in 1h2m3.0s."
    assert _parse_retry_after_seconds(message, default=0.0) == 1 * 3600 + 2 * 60 + 3.0 + 1.0


def test_falls_back_to_default_when_unparseable():
    assert _parse_retry_after_seconds("some unrelated error", default=42.0) == 42.0
