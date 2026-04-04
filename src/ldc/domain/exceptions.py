"""Domain-level exceptions — raised by pure domain logic."""


class LdcError(Exception):
    """Base for all local-dev-composer errors."""


class CircularDependencyError(LdcError):
    """Raised when a cycle is detected in the service dependency graph."""


class UnknownServiceError(LdcError):
    """Raised when referencing a service name not present in the config."""


class ConfigValidationError(LdcError):
    """Raised when the composer.yml fails structural or semantic validation."""


class PrerequisiteNotMetError(LdcError):
    """Raised when a required prerequisite is absent and cannot be auto-fixed."""


class ServiceStartError(LdcError):
    """Raised when a service process fails to start or reach healthy state."""


class ServiceNotFoundError(LdcError):
    """Raised when a requested service has no running process."""
