"""
JobPilot AI - Application Workflow Exceptions
Domain-level exceptions for application lifecycle, state transitions,
approval fingerprinting, and preparation.
"""

class WorkflowError(Exception):
    """Base exception for all workflow domain errors."""
    pass


class InvalidStateTransitionError(WorkflowError):
    def __init__(self, from_status: str, to_status: str, reason: str = ""):
        self.from_status = from_status
        self.to_status = to_status
        self.reason = reason
        msg = f"Invalid application state transition from '{from_status}' to '{to_status}'."
        if reason:
            msg += f" Reason: {reason}"
        super().__init__(msg)


class MissingSubmissionEvidenceError(WorkflowError):
    pass


class InvalidApprovalFingerprintError(WorkflowError):
    pass


class ApplicationNotFoundError(WorkflowError):
    pass


class CandidateNotFoundError(WorkflowError):
    pass


class AmbiguousCandidateError(WorkflowError):
    pass


class CandidateProfileIncompleteError(WorkflowError):
    pass


class JobNotFoundError(WorkflowError):
    pass


class JobDisqualifiedError(WorkflowError):
    pass


class EligibilityNeedsReviewError(WorkflowError):
    pass


class ResumeUnavailableError(WorkflowError):
    pass


class ResumeIntegrityError(WorkflowError):
    pass


class DuplicateApplicationConflictError(WorkflowError):
    pass


class ApplicationNotReviewableError(WorkflowError):
    pass


class ApprovalFingerprintMismatchError(WorkflowError):
    pass


class StaleApprovalError(WorkflowError):
    pass
