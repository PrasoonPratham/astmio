#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2025 Pratham Prasoon
# All rights reserved.
#
# This library builds on Alexandr Shorin's ASTM pypi package
# https://pypi.org/project/astm/
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.
#

from astm.version import __version__
from setuptools import setup, find_packages

setup(
    name = 'astmio',
    version = __version__,
    description = 'Python implementation of ASTM E1381/1394 protocol.',
    long_description = open('README').read(),
    long_description_content_type='text/plain',

    author = 'Pratham Prasson',
    author_email = 'prathamprasoonyt@gmail.com',
    license='BSD-3-Clause',
    url = 'http://code.google.com/p/python-astm',

    install_requires = [],
    zip_safe = True,

    classifiers = [
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: 3.13',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Scientific/Engineering :: Medical Science Apps.'
    ],

    packages = find_packages(),
)
