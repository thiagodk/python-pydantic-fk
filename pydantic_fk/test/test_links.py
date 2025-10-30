
from typing import Optional, Union

import pytest
from pydantic import BaseModel, ValidationError
from pydantic.fields import FieldInfo

from ..links import LinkModelMetaclass
from ..links import _get_base_model_type


class Foo(BaseModel):
    """
    Testing model.

    This model fields will be linked to others.
    """
    a: int
    b: str


class Bar(BaseModel, metaclass=LinkModelMetaclass):
    """
    Testing linked model.

    Link fields from Foo.
    """
    _links = {"f": Foo}

    c: float


class PartialBar(BaseModel, metaclass=LinkModelMetaclass):
    """
    Testing partial linked model.

    Only link field "a" from "Foo".
    """
    _links = {"f": (Foo, "a")}

    c: float


class AppConfig(BaseModel, metaclass=LinkModelMetaclass):
    """
    Testing Config App model.
    """
    foo: Foo
    bar: Bar


class AppConfigPartial(BaseModel, metaclass=LinkModelMetaclass):
    """
    Testing Config App model.
    """
    foo: Foo
    bar: PartialBar


class AppConfigOptional(BaseModel, metaclass=LinkModelMetaclass):
    """
    Testing Config App model.
    """
    foo: Optional[Foo] = None
    bar: Bar


def test_helper_get_base_model_type():
    """
    Test _get_base_model_type function.
    """

    assert _get_base_model_type(Foo) is Foo
    assert _get_base_model_type(Optional[Foo]) is Foo
    assert _get_base_model_type(Union[str, Foo]) is Foo
    assert _get_base_model_type(list[Foo]) is Foo
    assert _get_base_model_type(dict[str, Foo]) is Foo
    assert _get_base_model_type(str) is None
    assert _get_base_model_type(int) is None
    assert _get_base_model_type(Optional[str]) is None
    assert _get_base_model_type(Union[str, int]) is None
    assert _get_base_model_type(list[str]) is None
    assert _get_base_model_type(dict[str, int]) is None


def test_field_link():
    """
    Test field_link decorator.
    """

    # pylint: disable=unsubscriptable-object
    assert Bar.model_fields["f_a"].annotation is int
    assert Bar.model_fields["f_b"].annotation is str


def test_validate_link():
    """
    Test validate_link decorator.
    """

    # Test not overridden values
    cfg = AppConfig(
        foo=Foo(a=1, b="test"),
        bar={"c": 3.14159265})
    assert cfg.bar.f_a == 1
    assert cfg.bar.f_b == "test"
    assert cfg.bar.c == 3.14159265

    # Test override values
    cfg = AppConfig.model_validate({
        "foo": Foo(a=2, b="test"),
        "bar": {"c": 3.14159265, "f_b": "override"}})
    assert cfg.bar.f_a == 2
    assert cfg.bar.f_b == "override"
    assert cfg.bar.c == 3.14159265

    # Test PartialBar
    # pylint: disable=unsubscriptable-object
    assert isinstance(PartialBar.model_fields["f_a"], FieldInfo)
    with pytest.raises(KeyError):
        assert isinstance(PartialBar.model_fields["f_b"], FieldInfo)

    cfg = AppConfigPartial(
        foo=Foo(a=3, b="test"),
        bar={"c": 2.5})
    assert cfg.bar.f_a == 3
    assert not hasattr(cfg.bar, "f_b")

    # Testing missing Foo in AppConfigOptional
    with pytest.raises(ValidationError) as exc:
        cfg = AppConfigOptional.model_validate({"bar": {"c": 3.14159265}})

    error_fields = [".".join(err["loc"]) for err in exc.value.errors()]
    assert "bar.f_a" in error_fields
    assert "bar.f_b" in error_fields

    # Testing user provided fields in AppConfigOptional
    cfg = AppConfigOptional.model_validate({
        "bar": {"f_a": 4, "f_b": "user-input", "c": 3.14159265}})
    assert cfg.bar.f_a == 4
    assert cfg.bar.f_b == "user-input"
    assert cfg.bar.c == 3.14159265
