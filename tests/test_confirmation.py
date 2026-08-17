"""Unit tests for PendingConfirmation and ConfirmationManager."""

from __future__ import annotations

import unittest

from core.confirmation import ConfirmationManager, PendingConfirmation


class ConfirmationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fake_now = 1000.0

        def fake_time() -> float:
            return self.fake_now

        self.manager = ConfirmationManager(default_timeout=10.0, time_provider=fake_time)

    def test_confirmation_creation(self) -> None:
        pending = self.manager.create("shutdown_computer", description="shut down the computer")
        self.assertIsNotNone(pending)
        self.assertEqual(pending.action, "shutdown_computer")
        self.assertEqual(pending.created_at, 1000.0)
        self.assertFalse(pending.is_expired(1005.0))
        self.assertEqual(self.manager.pending, pending)

    def test_confirmation_retrieval(self) -> None:
        self.manager.create("restart_computer")
        self.fake_now = 1005.0
        pending = self.manager.pending
        self.assertIsNotNone(pending)
        self.assertEqual(pending.action, "restart_computer")

    def test_confirmation_expiration(self) -> None:
        self.manager.create("shutdown_computer")
        self.fake_now = 1011.0  # 11s > 10s
        self.assertIsNone(self.manager.pending)
        self.assertEqual(self.manager.pop_expired_action(), "shutdown_computer")

    def test_confirmation_clearing(self) -> None:
        self.manager.create("sleep_computer")
        self.manager.clear()
        self.assertIsNone(self.manager.pending)

    def test_action_replacement(self) -> None:
        self.manager.create("shutdown_computer")
        self.fake_now = 1002.0
        self.manager.create("restart_computer")
        pending = self.manager.pending
        self.assertIsNotNone(pending)
        self.assertEqual(pending.action, "restart_computer")


if __name__ == "__main__":
    unittest.main()
