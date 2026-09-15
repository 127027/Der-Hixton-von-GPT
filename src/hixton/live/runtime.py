"""One-shot lifecycle driver, independent of Paper fills and Paper cash.

No arming action lives here. A separate, accepted user authorization path must
create the single entitlement. Production submission remains release-gated.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from threading import Event, RLock

from hixton.domain.models import IndicatorPoint
from hixton.live.reconciliation import AccountSnapshot, TrialReconciler
from hixton.live.trial import SignalTrial


class TrialRuntime:
    def __init__(
        self,
        trial: SignalTrial,
        reconciler: TrialReconciler,
        snapshot: Callable[[], AccountSnapshot],
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.trial = trial
        self.reconciler = reconciler
        self.snapshot = snapshot
        self.clock = clock
        self.stopped = Event()
        self.lock = RLock()
        self.last_error: str | None = None

    def stop(self) -> None:
        # Fail closed immediately, even if a current network request is returning.
        # No liquidation; already sent/uncertain orders remain durable obligations.
        self.stopped.set()

    def tick(
        self,
        points: Mapping[str, Sequence[IndicatorPoint]],
        *,
        now: datetime,
        healthy: bool,
        entries_allowed: bool,
    ) -> dict[str, object]:
        with self.lock:
            if self.stopped.is_set():
                return self.trial.report()
            self.last_error = None
            try:
                report = self.trial.report()
                if not report["has_unsettled"]:
                    return report  # No keys/account calls for an inactive test.
                if not entries_allowed:
                    self.trial.disable_entries()
                # A separate 2-second lifecycle tick is crucial: selection and send
                # must not be separated by the next one-hour strategy candle.
                report = self.trial.advance(points, now=now, healthy=healthy)
                if report["state"] == "AWAITING_RECONCILIATION" and not self.stopped.is_set():
                    snapshot = self.snapshot()
                    self.reconciler.complete_if_proven(self.trial, snapshot, now=self.clock())
                    report = self.trial.report()
                return report
            except Exception:
                # Never send raw network/vault exceptions to public UI or logs.
                self.last_error = "TRIAL_LIFECYCLE_REQUIRES_REVIEW"
                return {**self.trial.report(), "runtime_error": self.last_error}
