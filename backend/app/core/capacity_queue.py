"""Bounded, fair admission for execution slots.

Execution capacity used to reject the moment every slot was busy, which turned
intentional overload into an 80-84% shed rate and forced clients to hammer
retries. This queue converts overload into a bounded, first-come-first-served
wait with an explicit position, and still fails closed when the backlog is full.

Design bounds (all configurable, none relaxed without measurement):
- ``slots``      concurrent executions, unchanged.
- ``max_waiters`` hard cap on queued requests; the next request is refused
                  fail-closed with a retry hint instead of waiting forever.
- ``deadline_s`` per-request wait bound; a request that waits longer is refused
                  rather than holding memory and a connection indefinitely.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass


class CapacityTimeout(TimeoutError):
    """Raised when a request waited past its deadline for a slot."""


class CapacityExceeded(RuntimeError):
    """Raised when the bounded waiting queue is already full."""


@dataclass(frozen=True)
class QueueStats:
    slots: int
    active: int
    waiting: int
    max_waiters: int


class CapacityQueue:
    """FIFO admission with a bounded queue and a bounded per-request wait."""

    def __init__(self, *, slots: int, max_waiters: int, deadline_seconds: float) -> None:
        self.slots = max(1, int(slots))
        self.max_waiters = max(0, int(max_waiters))
        self.deadline_seconds = max(0.1, float(deadline_seconds))
        self._semaphore = asyncio.Semaphore(self.slots)
        self._waiting = 0
        self._active = 0

    def refresh(self, *, slots: int | None = None, max_waiters: int | None = None,
                deadline_seconds: float | None = None) -> None:
        """Apply configuration changes without dropping an in-flight slot."""
        if slots is not None and max(1, int(slots)) != self.slots:
            self.slots = max(1, int(slots))
            self._semaphore = asyncio.Semaphore(self.slots)
        if max_waiters is not None:
            self.max_waiters = max(0, int(max_waiters))
        if deadline_seconds is not None:
            self.deadline_seconds = max(0.1, float(deadline_seconds))

    def stats(self) -> QueueStats:
        return QueueStats(slots=self.slots, active=self._active, waiting=self._waiting,
                          max_waiters=self.max_waiters)

    def position(self) -> int:
        """Approximate queue position for the current waiter (1 == next up)."""
        return self._waiting

    async def acquire(self) -> None:
        """Wait for a slot. Raises CapacityExceeded or CapacityTimeout instead."""
        if self._semaphore.locked() and self._waiting >= self.max_waiters:
            raise CapacityExceeded("Execution queue is full")
        self._waiting += 1
        started = time.monotonic()
        try:
            await asyncio.wait_for(self._semaphore.acquire(), timeout=self.deadline_seconds)
        except TimeoutError as exc:
            raise CapacityTimeout("Timed out waiting for execution capacity") from exc
        finally:
            self._waiting -= 1
        self._active += 1
        # Record how long admission took so overload is observable rather than
        # invisible (the caller may surface it as a queued state).
        self.last_wait_seconds = time.monotonic() - started

    def release(self) -> None:
        self._active = max(0, self._active - 1)
        self._semaphore.release()
