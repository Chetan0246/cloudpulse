"""
Application-level domain exceptions.

These are domain exceptions, not HTTP exceptions.
The FastAPI exception handlers translate these into standardized
HTTP responses with appropriate status codes and error payloads.
"""


class CloudPulseError(Exception):
    """Base exception for all CloudPulse application errors."""

    def __init__(self, message: str, error_code: str = "INTERNAL_ERROR") -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code


class ResourceNotFoundError(CloudPulseError):
    """Raised when a virtual resource does not exist in DynamoDB."""

    def __init__(self, resource_id: str) -> None:
        self.resource_id = resource_id
        super().__init__(
            message=f"Resource '{resource_id}' not found",
            error_code="RESOURCE_NOT_FOUND",
        )


class IncidentNotFoundError(CloudPulseError):
    """Raised when an incident record does not exist in DynamoDB."""

    def __init__(self, incident_id: str) -> None:
        self.incident_id = incident_id
        super().__init__(
            message=f"Incident '{incident_id}' not found",
            error_code="INCIDENT_NOT_FOUND",
        )


class MetricNotFoundError(CloudPulseError):
    """Raised when a reliability metric record does not exist in DynamoDB."""

    def __init__(self, resource_id: str, window_key: str | None = None) -> None:
        self.resource_id = resource_id
        self.window_key = window_key
        msg = (
            f"Metric for resource '{resource_id}' and window '{window_key}' not found"
            if window_key
            else f"No metrics found for resource '{resource_id}'"
        )
        super().__init__(
            message=msg,
            error_code="METRIC_NOT_FOUND",
        )


class InvalidStateTransitionError(CloudPulseError):
    """Raised when a recovery or resource state transition is not permitted."""

    def __init__(self, from_state: str, to_state: str) -> None:
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(
            message=f"Cannot transition from '{from_state}' to '{to_state}'",
            error_code="INVALID_STATE_TRANSITION",
        )


class DatabaseError(CloudPulseError):
    """Raised when an unexpected DynamoDB or AWS SDK operation fails."""

    def __init__(self, message: str) -> None:
        super().__init__(
            message=f"Database operation failed: {message}",
            error_code="DATABASE_ERROR",
        )


class SimulationError(CloudPulseError):
    """Raised when a failure simulation cannot be applied."""

    def __init__(self, message: str) -> None:
        super().__init__(
            message=message,
            error_code="SIMULATION_ERROR",
        )
