"""Runtime ownership, cancellation, Deadline, and admission contracts."""

from lingshu.runtime.admission import AdmissionLease, AdmissionOutcome, BoundedAdmission
from lingshu.runtime.cancellation import (
    Cancellation,
    CancellationReason,
    CancellationToken,
    ScopeCancelled,
)
from lingshu.runtime.deadline import Deadline, deadline_exceeded_error
from lingshu.runtime.scope import (
    CleanupFailure,
    CleanupReport,
    Scope,
    ScopeKind,
    ScopeState,
    TaskFailure,
    current_scope,
)

__all__ = (
    "AdmissionLease",
    "AdmissionOutcome",
    "BoundedAdmission",
    "Cancellation",
    "CancellationReason",
    "CancellationToken",
    "CleanupFailure",
    "CleanupReport",
    "Deadline",
    "Scope",
    "ScopeCancelled",
    "ScopeKind",
    "ScopeState",
    "TaskFailure",
    "current_scope",
    "deadline_exceeded_error",
)
