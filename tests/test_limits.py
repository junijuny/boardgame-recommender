"""RateLimiter, DailyBudget, client_ip 단위 테스트."""

import unittest
from datetime import date
from types import SimpleNamespace

from backend.limits import DailyBudget, RateLimiter, client_ip


class RateLimiterTests(unittest.TestCase):
    def test_allows_up_to_limit_then_blocks(self):
        now = [0.0]
        limiter = RateLimiter(3, 60, clock=lambda: now[0])
        self.assertEqual([limiter.allow("a") for _ in range(4)], [True, True, True, False])
        self.assertTrue(limiter.allow("b"))  # other key unaffected

    def test_window_slides(self):
        now = [0.0]
        limiter = RateLimiter(1, 60, clock=lambda: now[0])
        self.assertTrue(limiter.allow("a"))
        now[0] = 59.9
        self.assertFalse(limiter.allow("a"))
        now[0] = 60.1
        self.assertTrue(limiter.allow("a"))

    def test_idle_keys_are_removed_after_window(self):
        now = [0.0]
        limiter = RateLimiter(2, 60, clock=lambda: now[0])
        for key in ("a", "b", "c"):
            self.assertTrue(limiter.allow(key))
        self.assertEqual(len(limiter._hits), 3)
        now[0] = 61.0
        self.assertTrue(limiter.allow("d"))  # other traffic sweeps expired keys
        self.assertEqual(set(limiter._hits), {"d"})

    def test_same_key_after_window_keeps_single_entry(self):
        now = [0.0]
        limiter = RateLimiter(1, 60, clock=lambda: now[0])
        self.assertTrue(limiter.allow("a"))
        now[0] = 100.0
        self.assertTrue(limiter.allow("a"))
        self.assertEqual(len(limiter._hits["a"]), 1)


class DailyBudgetTests(unittest.TestCase):
    def test_spends_until_limit_and_resets_next_day(self):
        day = [date(2026, 11, 15)]
        budget = DailyBudget(2, today=lambda: day[0])
        self.assertTrue(budget.try_spend())
        self.assertTrue(budget.try_spend())
        self.assertFalse(budget.try_spend())
        self.assertEqual(budget.remaining(), 0)
        day[0] = date(2026, 11, 16)
        self.assertTrue(budget.try_spend())

    def test_multi_spend_is_all_or_nothing(self):
        budget = DailyBudget(2, today=lambda: date(2026, 11, 15))
        self.assertFalse(budget.try_spend(3))
        self.assertEqual(budget.remaining(), 2)


def _req(headers, host=None):
    client = SimpleNamespace(host=host) if host else None
    return SimpleNamespace(headers=headers, client=client)


class ClientIpTests(unittest.TestCase):
    def test_uses_first_forwarded_entry(self):
        req = _req({"x-forwarded-for": "1.2.3.4, 10.0.0.1"}, host="9.9.9.9")
        self.assertEqual(client_ip(req), "1.2.3.4")

    def test_falls_back_to_client_host(self):
        self.assertEqual(client_ip(_req({}, host="9.9.9.9")), "9.9.9.9")

    def test_unknown_when_no_client(self):
        self.assertEqual(client_ip(_req({})), "unknown")


if __name__ == "__main__":
    unittest.main()
