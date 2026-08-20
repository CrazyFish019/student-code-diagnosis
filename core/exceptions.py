"""Project-specific exceptions."""


class ModelValidationError(ValueError):
    """Raised when a core model is constructed with invalid data."""


class InfrastructureError(RuntimeError):
    """Base class for failures in local judging infrastructure."""


class CompilerNotFoundError(InfrastructureError):
    """Raised internally when the configured C++ compiler cannot be located."""


class ProcessStartError(InfrastructureError):
    """Raised internally when an external process cannot be started."""
