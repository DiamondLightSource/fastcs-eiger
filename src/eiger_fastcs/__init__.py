import sys

if sys.version_info < (3, 8):
    from importlib_metadata import version  # noqa
else:
    from importlib.metadata import version  # noqa

__version__ = version("eiger-fastcs")
del version

__all__ = ["__version__"]
