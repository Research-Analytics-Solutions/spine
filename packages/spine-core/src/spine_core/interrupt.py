"""Human-in-the-loop interrupt signal.

A tool raises :class:`Interrupt` to pause the run. The kernel persists state and
returns a resumable :class:`~spine_core.result.Result`; the pause can outlive
the process because the resume token points at a durable checkpoint.
"""

from __future__ import annotations

import secrets
from typing import Any

from spine_core.errors import SpineError


class Interrupt(SpineError):
    """Raised inside a tool to hand control back to a human.

    ``payload`` is surfaced to the host (e.g. an approval prompt). The host
    later calls ``agent.resume(token, decision)`` to continue.
    """

    def __init__(self, payload: Any = None) -> None:
        super().__init__("run interrupted for human-in-the-loop")
        self.payload = payload


def new_resume_token() -> str:
    """Opaque, unguessable token mapping a paused run to its checkpoint."""
    return secrets.token_urlsafe(24)
