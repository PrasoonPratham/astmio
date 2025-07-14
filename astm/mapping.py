# -*- coding: utf-8 -*-
#
# Copyright (C) 2013 Alexander Shorin
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.
#
from __future__ import annotations

import datetime
import decimal
import logging
import time
import warnings
from itertools import zip_longest
from operator import itemgetter
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
    Type,
    Union,
)

log = logging.getLogger(__name__)


class Field:
    """Base mapping field class."""

    def __init__(
        self,
        name: Optional[str] = None,
        default: Any = None,
        required: bool = False,
        length: Optional[int] = None,
    ):
        self.name = name
        self.default = default
        self.required = required
        self.length = length

    def __get__(self, instance: Optional[Mapping], owner: Type[Mapping]) -> Any:
        if instance is None:
            return self
        value = instance._data.get(self.name)
        if value is not None:
            return self._get_value(value)
        if self.default is not None:
            default = self.default
            if callable(default):
                return default()
            return default
        return None

    def __set__(self, instance: Mapping, value: Any) -> None:
        if value is not None:
            value = self._set_value(value)
        instance._data[self.name] = value

    def _get_value(self, value: Any) -> Any:
        return value

    def _set_value(self, value: Any) -> Any:
        value = str(value)
        if self.length is not None and len(value) > self.length:
            raise ValueError(
                f"Field {self.name!r} value is too long "
                f"(max {self.length}, got {len(value)})"
            )
        return value


class MetaMapping(type):
    def __new__(
        mcs, name: str, bases: Tuple[Type, ...], d: Dict[str, Any]
    ) -> MetaMapping:
        fields: List[Tuple[str, Field]] = []
        names: List[str] = []

        def merge_fields(items: List[Tuple[str, Field]]) -> None:
            for n, field in items:
                if field.name is None:
                    field.name = n
                if n not in names:
                    fields.append((n, field))
                    names.append(n)
                else:
                    fields[names.index(n)] = (n, field)

        for base in bases:
            if hasattr(base, "_fields"):
                merge_fields(base._fields)
        merge_fields([(k, v) for k, v in d.items() if isinstance(v, Field)])
        d["_fields"] = fields
        return super().__new__(mcs, name, bases, d)


class Mapping(metaclass=MetaMapping):
    _fields: List[Tuple[str, Field]]
    _data: Dict[str, Any]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        fieldnames = [name for name, _ in self._fields]
        values = dict(zip_longest(fieldnames, args))
        values.update(kwargs)
        self._data = {}
        for attrname, field in self._fields:
            attrval = values.pop(attrname, None)
            if attrval is not None:
                setattr(self, attrname, attrval)
            else:
                setattr(self, attrname, getattr(self, attrname))
        if values:
            raise ValueError(f"Unexpected kwargs found: {list(values.keys())!r}")

    @classmethod
    def build(cls, *a: Field) -> Type[Mapping]:
        newcls = type(f"Generic{cls.__name__}", (cls,), {})
        fields: List[Tuple[str, Field]] = []
        for field in a:
            if field.name is None:
                raise ValueError("Name is required for ordered fields.")
            setattr(newcls, field.name, field)
            fields.append((field.name, field))
        newcls._fields = fields
        return newcls

    def __getitem__(self, key: int) -> Any:
        return self.values()[key]

    def __setitem__(self, key: int, value: Any) -> None:
        setattr(self, self._fields[key][0], value)

    def __delitem__(self, key: int) -> None:
        self._data[self._fields[key][0]] = None

    def __iter__(self) -> Iterable[Any]:
        return iter(self.values())

    def __contains__(self, item: Any) -> bool:
        return item in self.values()

    def __len__(self) -> int:
        return len(self._data)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, (list, tuple)) or len(self) != len(other):
            return False
        for key, value in zip(self.keys(), other):
            if getattr(self, key) != value:
                return False
        return True

    def __ne__(self, other: Any) -> bool:
        return not self == other

    def __repr__(self) -> str:
        items_repr = ", ".join(f"{key}={value!r}" for key, value in self.items())
        return f"{self.__class__.__name__}({items_repr})"

    def keys(self) -> List[str]:
        return [key for key, _ in self._fields]

    def values(self) -> List[Any]:
        return [getattr(self, key) for key in self.keys()]

    def items(self) -> List[Tuple[str, Any]]:
        return [(key, getattr(self, key)) for key, _ in self._fields]

    def to_astm(self) -> List[Any]:
        def _values(obj: Mapping) -> Iterable[Any]:
            for key, field in obj._fields:
                value = obj._data.get(key)
                if isinstance(value, Mapping):
                    yield list(_values(value))
                elif isinstance(value, list):
                    yield [
                        list(_values(item)) if isinstance(item, Mapping) else item
                        for item in value
                    ]
                elif value is None and field.required:
                    raise ValueError(f"Field {key!r} value should not be None")
                else:
                    yield value

        return list(_values(self))


class Record(Mapping):
    """ASTM record mapping class."""


class Component(Mapping):
    """ASTM component mapping class."""


class TextField(Field):
    """Mapping field for string values."""

    def _set_value(self, value: Any) -> str:
        if not isinstance(value, str):
            raise TypeError(f"String value expected, got {type(value).__name__}")
        return super()._set_value(value)


class ConstantField(Field):
    def __init__(
        self,
        name: Optional[str] = None,
        default: Any = None,
        field: Optional[Field] = None,
    ):
        if default is None:
            raise ValueError("Constant value should be defined")
        self.field = field or Field()
        super().__init__(name=name, default=default, required=True)

    def _get_value(self, value: Any) -> Any:
        return self.default

    def _set_value(self, value: Any) -> Any:
        processed_value = self.field._get_value(value)
        if self.default != processed_value:
            raise ValueError(
                f"Field changing not allowed: got {value!r}, accepts {self.default!r}"
            )
        return super()._set_value(processed_value)


class IntegerField(Field):
    """Mapping field for integer values."""

    def _get_value(self, value: Any) -> int:
        return int(value)

    def _set_value(self, value: Any) -> int:
        if not isinstance(value, int):
            try:
                value = self._get_value(value)
            except (ValueError, TypeError):
                raise TypeError(f"Integer value expected, got {type(value).__name__}")
        return super()._set_value(value)


class DecimalField(Field):
    """Mapping field for decimal values."""

    def _get_value(self, value: Any) -> decimal.Decimal:
        return decimal.Decimal(str(value))

    def _set_value(self, value: Any) -> decimal.Decimal:
        if not isinstance(value, (int, float, decimal.Decimal)):
            raise TypeError(f"Decimal value expected, got {type(value).__name__}")
        return super()._set_value(value)


class DateField(Field):
    """Mapping field for storing date values."""

    format: str = "%Y%m%d"

    def _get_value(self, value: str) -> datetime.date:
        return datetime.datetime.strptime(value, self.format).date()

    def _set_value(self, value: Union[str, datetime.date, datetime.datetime]) -> str:
        if isinstance(value, str):
            dt_value = self._get_value(value)
        elif isinstance(value, (datetime.datetime, datetime.date)):
            dt_value = value
        else:
            raise TypeError(f"Date(time) value expected, got {type(value).__name__}")
        return dt_value.strftime(self.format)


class TimeField(Field):
    """Mapping field for storing time values."""

    format: str = "%H%M%S"

    def _get_value(self, value: str) -> datetime.time:
        try:
            time_str = value.split(".", 1)[0]
            return datetime.time(*time.strptime(time_str, self.format)[3:6])
        except (ValueError, IndexError):
            raise ValueError(f"Value {value!r} does not match format {self.format}")

    def _set_value(self, value: Union[str, datetime.time, datetime.datetime]) -> str:
        if isinstance(value, str):
            time_value = self._get_value(value)
        elif isinstance(value, datetime.datetime):
            time_value = value.time()
        elif isinstance(value, datetime.time):
            time_value = value
        else:
            raise TypeError(f"Time value expected, got {type(value).__name__}")
        return time_value.replace(microsecond=0).strftime(self.format)


class DateTimeField(Field):
    """Mapping field for storing datetime values."""

    format: str = "%Y%m%d%H%M%S"

    def _get_value(self, value: str) -> datetime.datetime:
        return datetime.datetime.strptime(value, self.format)

    def _set_value(
        self, value: Union[str, datetime.date, datetime.datetime]
    ) -> str:
        if isinstance(value, str):
            dt_value = self._get_value(value)
        elif isinstance(value, (datetime.datetime, datetime.date)):
            dt_value = value
        else:
            raise TypeError(f"Datetime value expected, got {type(value).__name__}")
        return dt_value.strftime(self.format)


class SetField(Field):
    """Mapping field for a predefined set of values."""

    def __init__(
        self,
        name: Optional[str] = None,
        default: Any = None,
        required: bool = False,
        length: Optional[int] = None,
        values: Optional[Iterable[Any]] = None,
        field: Optional[Field] = None,
    ):
        self.field = field or Field()
        self.values: Set[Any] = set(values) if values else set()
        super().__init__(name, default, required, length)

    def _get_value(self, value: Any) -> Any:
        return self.field._get_value(value)

    def _set_value(self, value: Any) -> Any:
        processed_value = self.field._get_value(value)
        if processed_value not in self.values:
            raise ValueError(f"Unexpected value {processed_value!r}")
        return self.field._set_value(processed_value)


class ComponentField(Field):
    """Mapping field for storing a record component."""

    def __init__(
        self, mapping: Type[Mapping], name: Optional[str] = None, default: Any = None
    ):
        self.mapping = mapping
        default = default if default is not None else mapping()
        super().__init__(name, default)

    def _get_value(self, value: Any) -> Mapping:
        if isinstance(value, dict):
            return self.mapping(**value)
        if isinstance(value, self.mapping):
            return value
        if isinstance(value, (list, tuple)):
            return self.mapping(*value)
        return self.mapping(value)

    def _set_value(self, value: Any) -> Mapping:
        return self._get_value(value)


class RepeatedComponentField(Field):
    """Mapping field for storing a list of record components."""

    class Proxy(List[Mapping]):
        def __init__(self, seq: Iterable[Any], field: ComponentField):
            self.field = field
            super().__init__(self.field._get_value(i) for i in seq)

        def __setitem__(self, index: Union[int, slice], value: Any) -> None:
            if isinstance(index, slice):
                super().__setitem__(index, [self.field._set_value(v) for v in value])
            else:
                super().__setitem__(index, self.field._set_value(value))

        def append(self, item: Any) -> None:
            super().append(self.field._set_value(item))

        def extend(self, other: Iterable[Any]) -> None:
            super().extend(self.field._set_value(i) for i in other)

    def __init__(
        self,
        field: Union[ComponentField, Type[Mapping]],
        name: Optional[str] = None,
        default: Any = None,
    ):
        if isinstance(field, ComponentField):
            self.field = field
        elif isinstance(field, type) and issubclass(field, Mapping):
            self.field = ComponentField(field)
        else:
            raise TypeError("A Mapping class or ComponentField instance is required.")
        default = default if default is not None else []
        super().__init__(name, default)

    def _get_value(self, value: Any) -> Proxy:
        return self.Proxy(value, self.field)

    def _set_value(self, value: Iterable[Any]) -> List[Mapping]:
        return [self.field._set_value(item) for item in value]


class NotUsedField(Field):
    def __init__(self, name: Optional[str] = None):
        super().__init__(name=name)

    def _get_value(self, value: Any) -> None:
        return None

    def _set_value(self, value: Any) -> None:
        warnings.warn(
            f"Field {self.name!r} is not used, any assignments are omitted",
            UserWarning,
        )
        return None
