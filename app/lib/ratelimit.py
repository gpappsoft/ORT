# Copyright (c) 2025 Marco Moenig (info@moenig.it)
#
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT

import time
from collections import defaultdict
from fastapi import HTTPException, status


_buckets: dict[str, list[float]] = defaultdict(list)


def check_rate_limit(key: str, max_attempts: int, window_seconds: int) -> None:
    """Raise HTTP 429 if `key` has exceeded `max_attempts` in `window_seconds`."""
    now = time.monotonic()
    attempts = [t for t in _buckets[key] if now - t < window_seconds]
    _buckets[key] = attempts
    if len(attempts) >= max_attempts:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please try again later.",
        )
    _buckets[key].append(now)
