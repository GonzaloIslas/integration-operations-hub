import secrets
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Deque

from fastapi import Depends, HTTPException, Response, status
from fastapi.security import APIKeyHeader, HTTPBasic, HTTPBasicCredentials

from app.config import get_settings


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    identifier: str
    authentication_method: str


class FixedWindowRateLimiter:
    def __init__(self, limit: int, window_seconds: int) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self.requests: dict[str, Deque[float]] = defaultdict(deque)

    def consume(self, identifier: str, now: float | None = None) -> tuple[int, int]:
        current_time = time.monotonic() if now is None else now
        window_start = current_time - self.window_seconds
        attempts = self.requests[identifier]
        while attempts and attempts[0] <= window_start:
            attempts.popleft()
        if len(attempts) >= self.limit:
            retry_after = max(1, int(attempts[0] + self.window_seconds - current_time) + 1)
            raise RateLimitExceeded(retry_after)
        attempts.append(current_time)
        return self.limit - len(attempts), self.window_seconds


class RateLimitExceeded(Exception):
    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after_seconds = retry_after_seconds


basic_security = HTTPBasic(auto_error=False)
api_key_security = APIKeyHeader(name="X-API-Key", auto_error=False)
rate_limiter: FixedWindowRateLimiter | None = None


def authenticate_principal(
    credentials: HTTPBasicCredentials | None = Depends(basic_security),
    api_key: str | None = Depends(api_key_security),
) -> AuthenticatedPrincipal:
    settings = get_settings()
    if api_key is not None and secrets.compare_digest(api_key, settings.integration_api_key):
        return AuthenticatedPrincipal("integration-client", "api_key")
    if credentials is not None:
        has_valid_username = secrets.compare_digest(credentials.username, settings.operator_username)
        has_valid_password = secrets.compare_digest(credentials.password, settings.operator_password)
        if has_valid_username and has_valid_password:
            return AuthenticatedPrincipal(credentials.username, "basic")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Valid operator credentials or integration API key required.",
        headers={"WWW-Authenticate": "Basic"},
    )


def enforce_rate_limit(
    response: Response,
    principal: AuthenticatedPrincipal = Depends(authenticate_principal),
) -> AuthenticatedPrincipal:
    global rate_limiter
    settings = get_settings()
    if rate_limiter is None or (
        rate_limiter.limit != settings.api_rate_limit or rate_limiter.window_seconds != settings.api_rate_window_seconds
    ):
        rate_limiter = FixedWindowRateLimiter(settings.api_rate_limit, settings.api_rate_window_seconds)
    try:
        remaining, window_seconds = rate_limiter.consume(principal.identifier)
    except RateLimitExceeded as error:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "api_rate_limited", "message": "API rate limit exceeded."},
            headers={"Retry-After": str(error.retry_after_seconds)},
        ) from error
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    response.headers["X-RateLimit-Window"] = str(window_seconds)
    return principal
