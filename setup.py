from setuptools import find_packages, setup
import ast
import re

_version_re = re.compile(r'__version__\s+=\s+(.*)')

with open('graphene_tornado/__init__.py', 'rb') as f:
    version = str(ast.literal_eval(_version_re.search(
        f.read().decode('utf-8')).group(1)))

tests_require = [
    'coveralls',
    'mock',
    'pytest==3.10.0',
    'pytest-cov',
    'pytest-tornado'
]

setup(
    name='graphene-tornado',
    version=version,

    description='Graphene Tornado integration',
    long_description=open('README.rst').read(),

    url='https://github.com/graphql-python/graphene-tornado',

    author='Eric Hauser',
    author_email='ewhauser@gmail.com',

    license='MIT',

    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Libraries',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: Implementation :: PyPy',
    ],

    keywords='api graphql protocol rest relay graphene',

    packages=find_packages(exclude=['tests']),

    install_requires=[
        'six>=1.10.0',
        'graphene>=2.0.1',
        'Jinja2==2.9.6',
        'tornado>=5.1.0',
        'werkzeug==0.12.2'
    ],
    setup_requires=[
        'pytest',
    ],
    tests_require=tests_require,
    extras_require={
        'test': tests_require
    },
    include_package_data=True,
    zip_safe=False,
    platforms='any',
)
