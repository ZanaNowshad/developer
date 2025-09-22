"""Simplified runtime-compatible stand-ins for Pydantic v2 APIs."""

from __future__ import annotations

from dataclasses import MISSING
from typing import Any, Dict, Mapping, Optional, Type, TypeVar, Union, get_type_hints

T = TypeVar("T", bound="BaseModel")


class ValidationError(ValueError):
    """Exception raised when data validation fails."""


class _FieldInfo:
    __slots__ = ("default", "default_factory", "description")

    def __init__(
        self,
        *,
        default: Any = MISSING,
        default_factory: Any = MISSING,
        description: Optional[str] = None,
    ) -> None:
        self.default = default
        self.default_factory = default_factory
        self.description = description


def Field(
    default: Any = MISSING,
    *,
    default_factory: Any = MISSING,
    description: Optional[str] = None,
) -> _FieldInfo:
    """Create lightweight field metadata used by the stub BaseModel."""

    return _FieldInfo(default=default, default_factory=default_factory, description=description)


def ConfigDict(**kwargs: Any) -> Dict[str, Any]:
    """Return configuration mapping compatible with Pydantic v2."""

    return dict(kwargs)


def model_validator(_mode: str) -> Any:
    """Decorator placeholder matching Pydantic's model_validator."""

    def decorator(func):
        return func

    return decorator


class BaseModel:
    """Tiny subset of the Pydantic v2 BaseModel behaviour used in the project."""

    model_config: Dict[str, Any] = {"extra": "forbid"}

    def __init__(self, **data: Any) -> None:
        hints = get_type_hints(self.__class__)
        values: Dict[str, Any] = {}
        provided = set(data.keys())
        for name, hint in hints.items():
            if name.startswith("_"):
                continue
            default = getattr(self.__class__, name, MISSING)
            field_info: Optional[_FieldInfo] = None
            if isinstance(default, _FieldInfo):
                field_info = default
                default = field_info.default
            if name in data:
                values[name] = data[name]
                provided.discard(name)
            elif default is not MISSING:
                values[name] = default
            elif field_info and field_info.default_factory is not MISSING:
                values[name] = field_info.default_factory()
            else:
                raise ValidationError(f"Missing field '{name}'")
        extras_policy = self.model_config.get("extra", "forbid")
        if extras_policy != "allow" and provided:
            unexpected = ", ".join(sorted(provided))
            raise ValidationError(f"Unexpected field(s): {unexpected}")
        if extras_policy == "allow":
            for name in provided:
                values[name] = data[name]
        object.__setattr__(self, "__dict__", values)

    @classmethod
    def model_validate(cls: Type[T], data: Mapping[str, Any]) -> T:
        if not isinstance(data, Mapping):
            raise ValidationError("model_validate expects a mapping")
        return cls(**dict(data))

    def model_dump(self) -> Dict[str, Any]:
        return dict(self.__dict__)

    @classmethod
    def _field_info(cls, name: str) -> Optional[_FieldInfo]:
        value = getattr(cls, name, None)
        return value if isinstance(value, _FieldInfo) else None

    @classmethod
    def model_json_schema(cls) -> Dict[str, Any]:
        hints = get_type_hints(cls)
        properties: Dict[str, Dict[str, Any]] = {}
        required: list[str] = []
        for name, hint in hints.items():
            if name.startswith("_"):
                continue
            field_info = cls._field_info(name)
            schema = {"type": _python_type_to_json(hint)}
            if field_info and field_info.description:
                schema["description"] = field_info.description
            properties[name] = schema
            if not field_info or field_info.default is MISSING:
                required.append(name)
        return {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": cls.model_config.get("extra", "forbid") == "allow",
        }


def _python_type_to_json(tp: Any) -> str:
    origin = getattr(tp, "__origin__", None)
    if origin is Union:
        args = getattr(tp, "__args__", ())
        if len(args) == 2 and type(None) in args:
            return _python_type_to_json(args[0 if args[1] is type(None) else 1])
        return "array"
    if origin in (list,):
        return "array"
    if origin in (dict,):
        return "object"
    if tp in (str,):
        return "string"
    if tp in (int,):
        return "integer"
    if tp in (bool,):
        return "boolean"
    if tp in (float,):
        return "number"
    return "string"


class BaseSettings(BaseModel):
    """Very small BaseSettings shim used together with AppSettings."""

    model_config: Dict[str, Any] = {"extra": "allow"}

    def __init__(self, **data: Any) -> None:
        from os import environ

        hints = get_type_hints(self.__class__)
        env_prefix = self.model_config.get("env_prefix", "")
        merged: Dict[str, Any] = {}
        for name in hints:
            env_key = f"{env_prefix}{name}".upper()
            if env_key in environ:
                merged[name] = environ[env_key]
        merged.update(data)
        super().__init__(**merged)


__all__ = [
    "BaseModel",
    "BaseSettings",
    "ConfigDict",
    "Field",
    "ValidationError",
    "model_validator",
]
