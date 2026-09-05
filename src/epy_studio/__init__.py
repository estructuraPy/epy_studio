"""ePy Studio — pick the right editor for the document at hand.

A selector that launches one of the family's applications from the
shared install directory. It deliberately contains no editing logic:
zero duplication with the applications themselves.

It is also where the family's optional ePy Docs backend is FOUND. That
cannot be done by importing inside a frozen bundle, so Studio locates an
interpreter that has it, asks that interpreter, and passes the answer to
the applications it launches as an environment hint. A hint, never a
dependency -- an application started any other way behaves identically
without it, which is what keeps this package out of their dependency
graphs.
"""

from __future__ import annotations

__version__ = "0.6.1"
__author__ = "Ing. Angel Navarro-Mora M.Sc."

__all__ = ["__author__", "__version__"]
