"""Shared write-safety helpers for domain API write methods.

Single home for two small pieces of plumbing every write-capable domain
module in this package needs and that must stay byte-for-byte identical
across modules:

* :func:`warn_uncharacterised_write` -- the one WARNING line a write logs
  when its full side effects have not been confirmed against a live
  network (an unconfirmed field shape, an unconfirmed reboot/disconnect
  consequence, or both). Domain modules call this once, immediately
  before issuing the request, instead of hand-rolling their own log
  line, so the wording and log level are identical everywhere it
  appears.
* :func:`as_envelope` -- a zero-cost type narrowing from the
  ``Mapping[str, Any]`` domain methods accept for their ``parent``
  keyword argument (chosen to signal, at the type level, that the value
  is read-only and never mutated) to the ``Dict[str, Any]`` that
  :mod:`eero.api.links` is typed against. It performs no copy and no
  validation.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Mapping, Optional, Union, cast

from ..logging import SecureLoggerAdapter

#: Either logger shape used across the domain modules: most use
#: :func:`eero.logging.get_secure_logger`, but a few (e.g. ``dns.py``)
#: predate that convention and still use the stdlib logger directly. Both
#: expose the same ``.warning(msg, *args)`` surface this helper needs.
_Logger = Union[SecureLoggerAdapter, logging.Logger]


def warn_uncharacterised_write(logger: _Logger, operation: str) -> None:
    """Log one WARNING before issuing a write with unconfirmed side effects.

    Covers both flavours of unconfirmed write seen across this SDK: a write
    whose request/response shape has never been checked against a live
    network, and a write (like a settings change or a password change) whose
    shape is plausible but whose full consequences -- up to and including a
    mesh reboot or a client disconnect -- have not been characterised. In
    both cases the caller should follow the read-compare-skip discipline:
    read the current state first, skip the write when it already matches,
    and never retry a failed write in a loop.

    Args:
        logger: The calling module's secure logger, so any sensitive value
            named in ``operation`` is still redacted.
        operation: A short, human-readable description of the write being
            issued, naming the operation and the kind of resource only --
            never a caller-supplied identifier (network ID, profile,
            invite ID, user ID, subnet type, MAC, eero serial, schedule ID,
            etc.), which would otherwise end up in a WARNING-level log line.
            For example ``"set nightlight for eero"`` or ``"set network
            name for network"``. A value validated against a small, fixed
            vocabulary (e.g. a node/port ``action``, a DNS ``mode``) is not
            an identifier and may be included. Included verbatim in the log
            line.

    Returns:
        None.
    """
    logger.warning(
        "Issuing write (%s): its side effects have not been fully "
        "characterised against a live network. Read the current state "
        "first and skip the write when it already matches -- never retry "
        "a failed write in a loop.",
        operation,
    )


def as_envelope(parent: Optional[Mapping[str, Any]]) -> Optional[Dict[str, Any]]:
    """Narrow a read-only ``parent`` mapping to the type ``eero.api.links`` expects.

    Domain methods accept ``parent`` as ``Mapping[str, Any]`` to signal, at
    the type level, that the value is read-only and is never mutated,
    copied-with-changes, or otherwise transformed. The link-resolution
    helpers in :mod:`eero.api.links` are typed against ``Dict[str, Any]``.
    This function performs no copy and no validation; it exists solely to
    satisfy static typing for a value that is already read-only by
    convention throughout this SDK.

    Args:
        parent: The caller-supplied parent envelope, or ``None``.

    Returns:
        The same object, retyped as ``Optional[Dict[str, Any]]``.
    """
    return cast(Optional[Dict[str, Any]], parent)


__all__ = ["as_envelope", "warn_uncharacterised_write"]
