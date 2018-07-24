from setuptools import find_packages, setup

setup(
    name='TracHyperestraierPlugin', version='1.0.0.0',
    packages=find_packages(exclude=['*.tests*']),
    entry_points = """
        [trac.plugins]
        searchhyperestraier.searchhyperestraier = searchhyperestraier.searchhyperestraier
        searchhyperestraier.searchattachmenthyperestraier = searchhyperestraier.searchattachmenthyperestraier
        searchhyperestraier.searchdocumenthyperestraier = searchhyperestraier.searchdocumenthyperestraier
        searchhyperestraier.searchchangesethyperestraier = searchhyperestraier.searchchangesethyperestraier
    """,
)

