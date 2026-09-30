import pytest

from app.security import FixedWindowRateLimiter, RateLimitExceeded


def test_fixed_window_rate_limiter_enforces_limit_and_expires_old_requests():
    limiter = FixedWindowRateLimiter(limit=2, window_seconds=60)

    assert limiter.consume("operator", now=0) == (1, 60)
    assert limiter.consume("operator", now=1) == (0, 60)
    with pytest.raises(RateLimitExceeded) as raised_error:
        limiter.consume("operator", now=2)

    assert raised_error.value.retry_after_seconds == 59
    assert limiter.consume("operator", now=61) == (1, 60)
