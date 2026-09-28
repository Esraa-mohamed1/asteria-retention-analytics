"""Exception types. Callers catch these instead of raw requests/JSON errors."""

from __future__ import annotations


class AsteriaError(Exception):
    """Base class for all expected, explainable pipeline failures."""


class SourceFetchError(AsteriaError):
    """An external source could not be reached or returned an error."""

    def __init__(self, provider: str, indicator_id: str, reason: str) -> None:
        super().__init__(f"[{provider}/{indicator_id}] {reason}")
        self.provider = provider
        self.indicator_id = indicator_id
        self.reason = reason


class ContractViolation(AsteriaError):
    """Data does not match the contract we depend on (shape, keys, dimensions)."""


class DataIntegrityError(AsteriaError):
    """Supplied input files do not match their published checksums."""
