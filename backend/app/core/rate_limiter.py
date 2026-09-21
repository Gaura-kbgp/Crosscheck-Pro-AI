import time
import threading
from typing import Dict, List
from fastapi import Request, HTTPException, status
from app.core.config import settings

# Thread-safe in-memory rate limit store for fallback / standalone execution
_in_memory_lock = threading.Lock()
_in_memory_store: Dict[str, List[float]] = {}

def reset_rate_limit_store():
    """Reset the rate limit store (useful for testing)."""
    with _in_memory_lock:
        _in_memory_store.clear()

class RateLimiter:
    """
    Production-compatible rate limiter dependency.
    Tries Redis first for distributed worker nodes; falls back safely to in-memory sliding window.
    """
    def __init__(self, limit: int, window_seconds: int, name: str = "auth"):
        self.limit = limit
        self.window_seconds = window_seconds
        self.name = name

    def _check_redis(self, key: str) -> bool:
        try:
            import redis
            client = redis.Redis.from_url(settings.REDIS_URL, socket_timeout=1.0)
            current = client.incr(key)
            if current == 1:
                client.expire(key, self.window_seconds)
            client.close()
            return current <= self.limit
        except Exception:
            # Redis unavailable or connection error; signal fallback to in-memory store
            return None

    def _check_in_memory(self, key: str) -> bool:
        now = time.time()
        cutoff = now - self.window_seconds
        with _in_memory_lock:
            timestamps = _in_memory_store.get(key, [])
            # Filter out timestamps older than the sliding window
            timestamps = [ts for ts in timestamps if ts > cutoff]
            if len(timestamps) >= self.limit:
                _in_memory_store[key] = timestamps
                return False
            timestamps.append(now)
            _in_memory_store[key] = timestamps
            return True

    async def __call__(self, request: Request):
        if not settings.RATE_LIMIT_ENABLED:
            return

        client_ip = request.client.host if request.client else "127.0.0.1"
        key = f"ratelimit:{self.name}:{client_ip}"

        redis_result = self._check_redis(key)
        if redis_result is not None:
            allowed = redis_result
        else:
            allowed = self._check_in_memory(key)

        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later.",
                headers={"Retry-After": str(self.window_seconds)}
            )
