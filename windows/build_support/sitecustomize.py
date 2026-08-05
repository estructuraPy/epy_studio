"""Build-time interpreter hook: pin the Windows system ICU before Qt loads.

PyInstaller introspects Qt by importing PySide6 inside isolated child
processes. In conda environments the conda ``icu`` package exposes an
unversioned ``icuuc.dll`` whose exports are version-suffixed; when the
loader binds Qt6Core against that copy, ``import PySide6.QtCore`` dies
with ``WinError 127`` and PyInstaller silently skips the whole Qt
plugin/resource collection: no ``qwindows.dll``, no
``QtWebEngineProcess.exe``, no WebEngine resources. The frozen app then
fails at startup with "no Qt platform plugin could be initialized".

``build.py`` puts this directory on ``PYTHONPATH`` so every Python
process in the build tree (PyInstaller itself and its isolated children)
imports this module at startup and binds the module name ``icuuc.dll``
to the System32 copy first. Scope is strictly the build process tree;
the conda environment itself is not modified.
"""

import os
import sys

if sys.platform == "win32":
    import ctypes

    _system_icu = os.path.join(
        os.environ.get("SYSTEMROOT", r"C:\Windows"), "System32", "icuuc.dll"
    )
    if os.path.isfile(_system_icu):
        try:
            ctypes.WinDLL(_system_icu)
        except OSError:
            pass
