"""Shared configuration and exceptions for Student Code Diagnosis."""

from .config import CONFIG_DIR, DATA_DIR, PROJECT_ROOT, TEMP_DIR, USER_DATA_ROOT
from .exceptions import (
    CompilerNotFoundError,
    InfrastructureError,
    ModelValidationError,
    ProcessStartError,
)
from .version import __version__

__all__ = [
    "CompilerNotFoundError",
    "CONFIG_DIR",
    "DATA_DIR",
    "InfrastructureError",
    "ModelValidationError",
    "ProcessStartError",
    "PROJECT_ROOT",
    "TEMP_DIR",
    "USER_DATA_ROOT",
    "__version__",
]
