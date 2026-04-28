"""Performance instrumentation — timed_event ctx manager and rolling stats.

Probes are opt-in via the SLMKIII_PERF environment variable. When unset
(default in production runs) the timed_event ctx manager is effectively a
no-op (~30ns overhead from a single dict lookup + the ctx manager protocol).

Targets enforced in tests/test_perf.py:
  * knob delta -> CC out: < 5ms p95
  * page change render:   < 50ms p95
  * spec compile (full):  < 2s wall
  * full test suite:      < 30s wall

Usage::

    from slmkiii.perf import timed, perf_log

    with timed("knob_event"):
        controller._handle_event(event)

    print(perf_log.summary())
"""

from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from contextlib import contextmanager
from typing import Iterator


_ENABLED = bool(os.environ.get("SLMKIII_PERF"))


class PerfLog:
    """Rolling per-label timing buffer with p50/p95 stats.

    Keeps the most recent ``maxlen`` samples per label. Memory bound is
    O(labels * maxlen) — at the default 1024 samples × 8 labels typical
    in our hot paths, ~8 KB."""

    def __init__(self, maxlen: int = 1024) -> None:
        self.maxlen = maxlen
        self._samples: dict[str, deque[float]] = defaultdict(
            lambda: deque(maxlen=maxlen)
        )

    def record(self, label: str, dt_ms: float) -> None:
        self._samples[label].append(dt_ms)

    def stats(self, label: str) -> dict[str, float]:
        """p50, p95, max, n for a label. Returns zeros if no samples."""
        samples = list(self._samples.get(label, ()))
        if not samples:
            return {"n": 0, "p50": 0.0, "p95": 0.0, "max": 0.0, "mean": 0.0}
        ordered = sorted(samples)
        n = len(ordered)
        return {
            "n": n,
            "p50": ordered[n // 2],
            "p95": ordered[min(n - 1, int(n * 0.95))],
            "max": ordered[-1],
            "mean": sum(ordered) / n,
        }

    def all_labels(self) -> list[str]:
        return sorted(self._samples)

    def summary(self) -> str:
        lines = ["label                   n       p50    p95    max    mean (ms)"]
        for label in self.all_labels():
            s = self.stats(label)
            lines.append(
                f"{label:<22s}  {int(s['n']):>5d}  "
                f"{s['p50']:>5.2f}  {s['p95']:>5.2f}  "
                f"{s['max']:>5.2f}  {s['mean']:>5.2f}"
            )
        return "\n".join(lines)

    def reset(self) -> None:
        self._samples.clear()


# Module-level singleton; tests reset it via perf_log.reset()
perf_log = PerfLog()


@contextmanager
def timed(label: str) -> Iterator[None]:
    """Context manager that records elapsed wall time under ``label``.

    No-op (still has ctx manager overhead) when SLMKIII_PERF is unset, so
    tests can invoke probed code without polluting the rolling buffer.
    """
    if not _ENABLED:
        yield
        return
    t0 = time.perf_counter()
    try:
        yield
    finally:
        dt_ms = (time.perf_counter() - t0) * 1000.0
        perf_log.record(label, dt_ms)


def is_enabled() -> bool:
    return _ENABLED


def force_enable() -> None:
    """Used by tests to enable probes regardless of environment variable."""
    global _ENABLED
    _ENABLED = True


def force_disable() -> None:
    global _ENABLED
    _ENABLED = False
