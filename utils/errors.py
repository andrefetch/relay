from typing import Any

class AgentError(Exception):
    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.cause = cause

    def __str__(self) -> str:
        base = self.message
        if self.details:
            detail_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            base = f"{base} ({detail_str})"
        if self.cause:
            base = f"{base} [caused by: {self.cause}]"
        return base

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.__class__.__name__,
            "message": self.message,
            "details": self.details,
            "cause": str(self.cause) if self.cause else None,
        }


class ConfigError(AgentError):
    def __init__(
        self,
        message: str,
        config_key: str | None = None,
        config_file: str | None = None,
        **kwargs: Any,
    ) -> None:
        details = kwargs.pop("details", {}) or {}
        if config_key:
            details["config_key"] = config_key
        if config_file:
            details["config_file"] = config_file
        super().__init__(message, details=details, **kwargs)
        self.config_key = config_key
        self.config_file = config_file