#! /usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import find_packages, setup

def main():
    entry_points = (
        'searchhyperestraier.searchhyperestraier',
    )
    extra = {}

    setup(
        name='TracHyperestraierPlugin',
        version='1.0.0.0',
        packages=find_packages(exclude=['*.tests*']),
        entry_points={
            'trac.plugins': ['%(entry)s = %(entry)s' % dict(entry=entry)
                             for entry in entry_points],
        },
        **extra)

if __name__ == '__main__':
    main()
