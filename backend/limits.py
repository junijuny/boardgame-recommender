"""요청 제한: IP별 슬라이딩 윈도우 rate limiter와 전역 일일 호출 예산."""

import threading
import time
from collections import deque
from collections.abc import Callable
from datetime import UTC, date, datetime

from fastapi import Request


def _utc_today() -> date:
    return datetime.now(UTC).date()


class RateLimiter:
    """키별 슬라이딩 윈도우. 허용된 요청만 기록한다."""

    def __init__(
        self,
        limit: int,
        window_seconds: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.limit = limit
        self.window = window_seconds
        self.clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = self.clock()
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and now - hits[0] >= self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(now)
            return True


class DailyBudget:
    """날짜(기본 UTC)가 바뀌면 초기화되는 일일 호출 예산."""

    def __init__(self, limit: int, today: Callable[[], date] = _utc_today):
        self.limit = limit
        self.today = today
        self._day = today()
        self._used = 0
        self._lock = threading.Lock()

    def _roll(self) -> None:
        d = self.today()
        if d != self._day:
            self._day = d
            self._used = 0

    def try_spend(self, n: int = 1) -> bool:
        with self._lock:
            self._roll()
            if self._used + n > self.limit:
                return False
            self._used += n
            return True

    def remaining(self) -> int:
        with self._lock:
            self._roll()
            return self.limit - self._used


def client_ip(request: Request) -> str:
    # 가장 왼쪽 항목은 위조 가능하나, 전역 DailyBudget이 비용을 제한하므로 허용한다.
    # 가장 오른쪽을 쓰면 Cloud Run 사용자 전부가 프록시 IP 하나로 묶인다.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    if request.client and request.client.host:
        return request.client.host
    return "unknown"
