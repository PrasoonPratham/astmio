# -*- coding: utf-8 -*-
#
# Copyright (C) 2013 Alexander Shorin
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.
#

import datetime
import decimal
import inspect
import time
import warnings
from operator import itemgetter
from itertools import islice
from itertools import zip_longest
import logging
from functools import partial
from collections.abc import MutableMapping, Iterable

log = logging.getLogger(__name__)


def make_string(value):
    if isinstance(value, str):
        return value
    elif isinstance(value, bytes):
        return str(value, 'utf-8')
    else:
        return str(value)


class Field(object):
    """Base mapping field class."""
    def __init__(self, name=None, default=None, required=False, length=None):
        self.name = name
        self.default = default
        self.required = required
        self.length = length

    def __get__(self, instance, owner):
        if instance is None:
            return self
        value = instance._data.get(self.name)
        if value is not None:
            value = self._get_value(value)
        elif self.default is not None:
            default = self.default
            if hasattr(default, '__call__'):
                default = default()
            value = default
        return value

    def __set__(self, instance, value):
        if value is not None:
            value = self._set_value(value)
        instance._data[self.name] = value

    def _get_value(self, value):
        return value

    def _set_value(self, value):
        value = make_string(value)
        if self.length is not None and len(value) > self.length:
            raise ValueError('Field %r value is too long (max %d, got %d)'
                            '' % (self.name, self.length, len(value)))
        return value


class MetaMapping(type):

    def __new__(mcs, name, bases, d):
        fields = []
        names = []
        def merge_fields(items):
            for n, field in items:
                if field.name is None:
                    field.name = n
                if n not in names:
                    fields.append((n, field))
                    names.append(n)
                else:
                    fields[names.index(n)] = (n, field)
        for base in bases:
            if hasattr(base, '_fields'):
                merge_fields(base._fields)
        merge_fields([(k, v) for k, v in d.items() if isinstance(v, Field)])
        if '_fields' not in d:
            d['_fields'] = fields
        else:
            merge_fields(d['_fields'])
            d['_fields'] = fields
        return super(MetaMapping, mcs).__new__(mcs, name, bases, d)


class Mapping(metaclass=MetaMapping):

    def __init__(self, *args, **kwargs):
        fieldnames = map(itemgetter(0), self._fields)
        values = dict(zip_longest(fieldnames, args))
        values.update(kwargs)
        self._data = {}
        for attrname, field in self._fields:
            attrval = values.pop(attrname, None)
            if attrval is None:
                setattr(self, attrname, getattr(self, attrname))
            else:
                setattr(self, attrname, attrval)
        if values:
            raise ValueError('Unexpected kwargs found: %r' % values)

    @classmethod
    def build(cls, *a):
        fields = []
        newcls = type('Generic' + cls.__name__, (cls,), {})
        for field in a:
            if field.name is None:
                raise ValueError('Name is required for ordered fields.')
            setattr(newcls, field.name, field)
            fields.append((field.name, field))
        newcls._fields = fields
        return newcls

    def __getitem__(self, key):
        return self.values()[key]

    def __setitem__(self, key, value):
        setattr(self, self._fields[key][0], value)

    def __delitem__(self, key):
        self._data[self._fields[key][0]] = None

    def __iter__(self):
        return iter(self.values())

    def __contains__(self, item):
        return item in self.values()

    def __len__(self):
        return len(self._data)

    def __eq__(self, other):
        if len(self) != len(other):
            return False
        for key, value in zip(self.keys(), other):
            if getattr(self, key) != value:
                return False
        return True

    def __ne__(self, other):
        return not (self == other)

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__,
                           ', '.join('%s=%r' % (key, value)
                                     for key, value in self.items()))

    def keys(self):
        return [key for key, field in self._fields]

    def values(self):
        return [getattr(self, key) for key in self.keys()]

    def items(self):
        return [(key, getattr(self, key)) for key, field in self._fields]

    def to_astm(self):
        def values(obj):
            for key, field in obj._fields:
                value = obj._data[key]
                if isinstance(value, Mapping):
                    yield list(values(value))
                elif isinstance(value, list):
                    stack = []
                    for item in value:
                        if isinstance(item, Mapping):
                            stack.append(list(values(item)))
                        else:
                            stack.append(item)
                    yield stack
                elif value is None and field.required:
                    raise ValueError('Field %r value should not be None' % key)
                else:
                    yield value
        return list(values(self))


class Record(Mapping):
    """ASTM record mapping class."""


class Component(Mapping):
    """ASTM component mapping class."""


class TextField(Field):
    """Mapping field for string values."""
    def _set_value(self, value):
        if not isinstance(value, str):
            raise TypeError('String value expected, got %r' % value)
        return super(TextField, self)._set_value(value)


class ConstantField(Field):
    def __init__(self, name=None, default=None, field=None):
        field = field or Field()
        super(ConstantField, self).__init__(name, default, True, None)
        self.field = field
        self.required = True
        if self.default is None:
            raise ValueError('Constant value should be defined')

    def _get_value(self, value):
        return self.default

    def _set_value(self, value):
        value = self.field._get_value(value)
        if self.default != value:
            raise ValueError('Field changing not allowed: got %r, accepts %r'
                            '' % (value, self.default))
        return super(ConstantField, self)._set_value(value)


class IntegerField(Field):
    """Mapping field for integer values."""
    def _get_value(self, value):
        return int(value)

    def _set_value(self, value):
        if not isinstance(value, int):
            try:
                value = self._get_value(value)
            except Exception:
                raise TypeError('Integer value expected, got %r' % value)
        return super(IntegerField, self)._set_value(value)


class DecimalField(Field):
    """Mapping field for decimal values."""
    def _get_value(self, value):
        return decimal.Decimal(value)

    def _set_value(self, value):
        if not isinstance(value, (int, float, decimal.Decimal)):
            raise TypeError('Decimal value expected, got %r' % value)
        return super(DecimalField, self)._set_value(value)


class DateField(Field):
    """Mapping field for storing date/time values."""
    format = '%Y%m%d'
    def _get_value(self, value):
        return datetime.datetime.strptime(value, self.format)

    def _set_value(self, value):
        if isinstance(value, str):
            value = self._get_value(value)
        if not isinstance(value, (datetime.datetime, datetime.date)):
            raise TypeError('Datetime value expected, got %r' % value)
        return value.strftime(self.format)


class TimeField(Field):
    """Mapping field for storing times."""
    format = '%H%M%S'
    def _get_value(self, value):
        if isinstance(value, str):
            try:
                value = value.split('.', 1)[0] # strip out microseconds
                value = datetime.time(*time.strptime(value, self.format)[3:6])
            except ValueError:
                raise ValueError('Value %r does not match format %s'
                                 '' % (value, self.format))
        return value

    def _set_value(self, value):
        if isinstance(value, str):
            value = self._get_value(value)
        if not isinstance(value, (datetime.datetime, datetime.time)):
            raise TypeError('Datetime value expected, got %r' % value)
        if isinstance(value, datetime.datetime):
            value = value.time()
        return value.replace(microsecond=0).strftime(self.format)


class DateTimeField(Field):
    """Mapping field for storing date/time values."""
    format = '%Y%m%d%H%M%S'
    def _get_value(self, value):
        return datetime.datetime.strptime(value, self.format)

    def _set_value(self, value):
        if isinstance(value, str):
            value = self._get_value(value)
        if not isinstance(value, (datetime.datetime, datetime.date)):
            raise TypeError('Datetime value expected, got %r' % value)
        return value.strftime(self.format)


class SetField(Field):
    """Mapping field for predefined set of values."""
    def __init__(self, name=None, default=None,
                 required=False, length=None,
                 values=None, field=None):
        field = field or Field()
        super(SetField, self).__init__(name, default, required, length)
        self.field = field
        self.values = values and set(values) or set([])

    def _get_value(self, value):
        return self.field._get_value(value)

    def _set_value(self, value):
        value = self.field._get_value(value)
        if value not in self.values:
            raise ValueError('Unexpectable value %r' % value)
        return self.field._set_value(value)


class ComponentField(Field):
    """Mapping field for storing record component."""
    def __init__(self, mapping, name=None, default=None):
        self.mapping = mapping
        default = default or mapping()
        super(ComponentField, self).__init__(name, default)


    def _get_value(self, value):
        if isinstance(value, dict):
            return self.mapping(**value)
        elif isinstance(value, self.mapping):
            return value
        else:
            return self.mapping(*value)

    def _set_value(self, value):
        if isinstance(value, dict):
            return self.mapping(**value)
        elif isinstance(value, self.mapping):
            return value
        if isinstance(value, str):
            value = [value]
        return self.mapping(*value)


class RepeatedComponentField(Field):
    """Mapping field for storing list of record components."""
    def __init__(self, field, name=None, default=None):
        if isinstance(field, ComponentField):
            self.field = field
        else:
            assert isinstance(field, type) and issubclass(field, Mapping)
            self.field = ComponentField(field)
        default = default or []
        super(RepeatedComponentField, self).__init__(name, default)

    class Proxy(list):
        def __init__(self, seq, field):
            super(RepeatedComponentField.Proxy, self).__init__(field._get_value(i) for i in seq)
            self.field = field

        def __setitem__(self, index, value):
            if isinstance(index, slice):
                super(RepeatedComponentField.Proxy, self).__setitem__(index, [self.field._set_value(v) for v in value])
            else:
                super(RepeatedComponentField.Proxy, self).__setitem__(index, self.field._set_value(value))

        def append(self, item):
            super(RepeatedComponentField.Proxy, self).append(self.field._set_value(item))

        def extend(self, other):
            super(RepeatedComponentField.Proxy, self).extend(self.field._set_value(i) for i in other)

    def _get_value(self, value):
        return self.Proxy(value, self.field)

    def _set_value(self, value):
        return [self.field._set_value(item) for item in value]


class NotUsedField(Field):
    def __init__(self, name=None):
        super(NotUsedField, self).__init__(name)

    def _get_value(self, value):
        return None

    def _set_value(self, value):
        warnings.warn('Field %r is not used, any assignments are omitted'
                      '' % self.name, UserWarning)
        return None
