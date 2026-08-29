"""Which applications this bundle carries.

The list used to be written out in five places -- the launcher, the
PyInstaller spec in three sections, the Inno Setup script in five, the
build script and the README -- and by the time a fourth application
shipped, three of those still said "three editors". A list repeated
five times is a list that will disagree with itself.

It is data now, in ``_config/apps.epyson``, read here at run time and by
the spec at build time. The Inno Setup script cannot read JSON, so it
keeps its own copy and ``build.py`` refuses to build when the two
disagree -- "refuse to ship a bundle that lies" is already this repo's
idiom for the Qt runtime, and this belongs beside it.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

__all__ = ["App", "apps", "catalog_path", "install_dir"]


@dataclass(frozen=True)
class App:
    """One application the bundle can carry.

    Attributes:
        app_id: Executable stem, and the package name it is built from.
        display: What a person reads in the selector.
        description: One line saying what it is for.
        component: The Inno Setup component that installs it.
        register: ``"default"`` to claim the document default, or
            ``"openwith"`` to advertise an Open-with entry only.
    """

    app_id: str
    display: str
    description: str
    component: str
    register: str

    @property
    def claims_default(self) -> bool:
        """Whether this application may register as the default handler."""
        return self.register == "default"


def catalog_path() -> Path:
    """Return the catalog file, frozen or from source."""
    return Path(__file__).resolve().parent.parent / "_config" / "apps.epyson"


def apps() -> tuple[App, ...]:
    """Return every application in the catalog, in presentation order.

    Returns:
        One :class:`App` per entry.

    Raises:
        FileNotFoundError: When the catalog did not reach the bundle.
            Raised rather than defaulted: a spec that walks ``_config``
            too narrowly has silently dropped catalogs before, and an
            empty selector that looks like "nothing is installed" is
            worse than a loud failure.
    """
    path = catalog_path()
    if not path.is_file():
        raise FileNotFoundError(
            f"the application catalog is missing: {path}. It ships inside "
            f"_config/; a build that does not carry it produces an empty "
            f"selector that looks like a broken install."
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    return tuple(
        App(
            app_id=str(item["id"]),
            display=str(item["display"]),
            description=str(item["description"]),
            component=str(item["component"]),
            register=str(item["register"]),
        )
        for item in data["apps"]
    )


def install_dir() -> Path:
    """Return the directory holding the tool executables.

    Frozen: the directory of the launcher executable, which every tool
    shares. Running from source: this package's repository root, which
    has no executables, so the buttons disable -- launching from a
    checkout uses each repository's ``python -m`` entry instead.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parents[3]
