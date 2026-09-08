"""
Application-level exceptions.

These are domain exceptions, not HTTP exceptions.
Routers translate these into appropriate HTTP responses.
"""


class CloudPulseError(Exception):
    """Base exception for all CloudPulse application errors."""


class ResourceNotFoundError(CloudPulseError):
    """Raised when a virtual resource does not exist in DynamoDB."""

    def __init__(self, resource_id: str) -> None:
        self.resource_id = resource_id
        super().__init__(f"Resource '{resource_id}' not found")


class IncidentNotFoundError(CloudPulseError):
    """Raised when an incident record does not exist in DynamoDB."""

    def __init__(self, incident_id: str) -> None:
        self.incident_id = incident_id
        super().__init__(f"Incident '{incident_id}' not found")


class InvalidStateTransitionError(CloudPulseError):
    """Raised when a recovery state transition is not permitted."""

    def __init__(self, from_state: str, to_state: str) -> None:
        super().__init__(
            f"Cannot transition from '{from_state}' to '{to_state}'"
        )


class SimulationError(CloudPulseError):
    """Raised when a failure simulation cannot be applied."""
