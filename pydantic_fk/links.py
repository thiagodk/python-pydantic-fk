
from copy import deepcopy
from typing import Any, Optional, TypeAlias, Union
from typing import cast, get_args, get_origin
from typing import TYPE_CHECKING

from pydantic import BaseModel
from pydantic import model_validator
from pydantic.fields import FieldInfo
from pydantic._internal import _model_construction

if TYPE_CHECKING:
    from pydantic._internal import _generics, _decorators


ModelValidatorFunc: TypeAlias = (
    "_decorators.PydanticDescriptorProxy["
    "_decorators.ModelValidatorDecoratorInfo]")


def _get_source_value(source: Any, field_name: str) -> tuple[bool, Any]:
    """
    Get a field data from a specific source.

    :param source: Could either be a dictionary or a model instance.
    :param field_name: Field name to extract value from.

    :returns: A tuple containing a boolean as first item indicating if value
        exist in the source object, and the extracted value itself as second
        item.
    """
    if isinstance(source, dict):
        return (field_name in source, source.get(field_name))

    if isinstance(source, BaseModel):
        return (hasattr(source, field_name), getattr(source, field_name, None))

    return (False, None)


def _get_base_model_type(annotation: Any) -> Optional[type[BaseModel]]:
    """
    Try to extract a BaseModel type from annotation.

    :param annotation: Source field annotation.

    :returns: BaseModel type extracted from annotation of None if nothing was
        found.
    """
    origin = get_origin(annotation)

    if origin is Union:
        for arg in get_args(annotation):
            if model_type := _get_base_model_type(arg):
                return model_type
        return None

    if origin in (list, dict, set, tuple):
        if args := get_args(annotation):
            for arg in args:
                if model_type := _get_base_model_type(arg):
                    return model_type
        return None

    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation

    return None


def _copy_source_value(
    data: dict[str, Any],
    dest_values: dict[str, Any],
    source_mappings: dict[type[BaseModel], str],
    source_model_type: type[BaseModel],
    field_mappings: dict[str, str],
):
    """
    Copy source value to destination linked field.
    """
    if (source_field_name := source_mappings.get(source_model_type)) is None:
        return

    source_values = data.get(source_field_name)
    if not isinstance(source_values, (dict, BaseModel)):
        return

    for dest_field, source_field in field_mappings.items():
        if dest_field in dest_values:
            continue  # Do not override user input values.

        source_exists, source_value = _get_source_value(source_values, source_field)

        if source_exists:
            dest_values[dest_field] = source_value


def _copy_to_dest(
    data: dict[str, Any],
    source_mappings: dict[type[BaseModel], str],
    dest_model_type: type[BaseModel],
    dest_field_name: str,
):
    """
    Check if destination have linked fields to copy and then proceed.
    """
    links: Optional[list[tuple[type[BaseModel], dict[str, str]]]] = getattr(
        dest_model_type, "__link_model__", None)
    if links is None:
        return

    dest_values = data.get(dest_field_name)

    if isinstance(dest_values, dict):
        for source_model_type, field_mappings in links:
            _copy_source_value(
                data,
                dest_values,
                source_mappings,
                source_model_type,
                field_mappings)


def _get_link_validator_func() -> ModelValidatorFunc:
    """
    Create link validator function.
    """

    @model_validator(mode="before")
    def validate_linked_fields(cls, data: Any) -> Any:
        """
        Validator function to copy linked fields.
        """
        if not isinstance(data, dict):
            return data

        # Mapping BaseModel types to field names
        source_mappings: dict[type[BaseModel], str] = {}
        for field_name, field_def in cls.model_fields.items():
            if model_type := _get_base_model_type(field_def.annotation):
                source_mappings[model_type] = field_name

        for dest_model_type, dest_field_name in source_mappings.items():
            _copy_to_dest(data, source_mappings, dest_model_type, dest_field_name)

        return data

    return validate_linked_fields

def _create_linked_fields(
    links: dict[str, Any],
    link_model: list[tuple[type[BaseModel], dict[str, str]]],
    annotations: dict[str, Any],
) -> dict[str, Any]:
    """
    Create new linked fields for a LinkModelMetaclass.

    :param links: Links definitions.
    :param link_model: Reference to __link_model__ attribute.
    :param annotations: Referente to annotations dictionary.

    :returns: Namespace dictionary with new created fields.
    """
    namespace: dict[str, FieldInfo] = {}

    for prefix, values in links.items():
        if isinstance(values, type) and issubclass(values, BaseModel):
            _model = values
            _fields = list(_model.model_fields.keys())
        elif isinstance(values, (tuple, list)):
            _model = cast(type[BaseModel], values[0])
            _fields = [v for v in values[1:] if isinstance(v, str)]
        else:
            continue

        link_attr: dict[str, str] = {}

        for field_name in _fields:
            key = f"{prefix}_{field_name}"
            field_info = _model.model_fields[field_name]
            namespace[key] = deepcopy(field_info)
            annotations[key] = field_info.annotation
            link_attr[key] = field_name

        if link_attr:
            link_model.append((_model, link_attr))

    return namespace


class LinkModelMetaclass(_model_construction.ModelMetaclass):
    """
    Metaclass for models using linked fields.
    """

    def __new__(
        mcs,
        cls_name: str,
        bases: tuple[type[Any], ...],
        namespace: dict[str, Any],
        __pydantic_generic_metadata__: Optional["_generics.PydanticGenericMetadata"] = None,
        __pydantic_reset_parent_namespace__: bool = True,
        _create_model_module: Optional[str] = None,
        **kwargs: Any,
    ) -> type:
        """
        Metaclass constructor.
        """
        namespace.update(_create_linked_fields(
            namespace.pop("_links", {}),
            namespace.setdefault("__link_model__", []),
            namespace.setdefault("__annotations__", {})))

        # Create a validator function to copy linked fields.
        namespace[f"__link_validator_{cls_name}__"] = _get_link_validator_func()

        return super().__new__(
            mcs, cls_name, bases, namespace,
            __pydantic_generic_metadata__,
            __pydantic_reset_parent_namespace__,
            _create_model_module,
            **kwargs)
