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

__all__ = [
    "App",
    "REGISTER_MODES",
    "apps",
    "catalog_path",
    "entry_point",
    "for_build",
    "install_dir",
]

REGISTER_MODES = frozenset({"default", "openwith", "none"})
"""What an application may do with the document types it names.

``default`` claims the handler, ``openwith`` advertises an Open-with
entry only, and ``none`` claims nothing at all: no ``--register``, no
``[Run]`` line in the installer. An application that authors no
document type has nothing to register.
"""


@dataclass(frozen=True)
class App:
    """One application the bundle can carry.

    Attributes:
        app_id: Executable stem, and the package name it is built from.
        display: What a person reads in the selector.
        description: One line saying what it is for.
        component: The Inno Setup component that installs it.
        register: One of :data:`REGISTER_MODES`.
        optional: Whether Studio may be built and installed WITHOUT
            it. An optional application is one the owner hands out:
            its sibling checkout may be absent at build time, and
            when its executable is not installed the selector does
            not offer it at all -- not greyed, absent.
        asset_packages: The ``_config/_assets/<sub>`` subpackages the
            application imports dynamically, which the dependency
            graph cannot see. Build-time data, kept here so that a new
            application is one catalog entry and not a spec edit.
        hidden_imports: Whatever else it resolves at run time that
            static analysis misses -- entry-point plugins, backends.
        icon: The executable's icon, relative to the package root.
    """

    app_id: str
    display: str
    description: str
    component: str
    register: str
    optional: bool = False
    asset_packages: tuple[str, ...] = ()
    hidden_imports: tuple[str, ...] = ()
    icon: str = ""

    @property
    def claims_default(self) -> bool:
        """Whether this application may register as the default handler."""
        return self.register == "default"

    @property
    def registers(self) -> bool:
        """Whether this application registers any document type at all."""
        return self.register != "none"


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
    found: list[App] = []
    for item in data["apps"]:
        register = str(item["register"])
        if register not in REGISTER_MODES:
            raise ValueError(
                f"{item['id']}: register is {register!r}, which is none of "
                f"{sorted(REGISTER_MODES)}. A mode nobody handles would "
                f"register nothing and say nothing."
            )
        found.append(
            App(
                app_id=str(item["id"]),
                display=str(item["display"]),
                description=str(item["description"]),
                component=str(item["component"]),
                register=register,
                optional=bool(item.get("optional", False)),
                asset_packages=tuple(
                    str(sub) for sub in item.get("asset_packages", [])
                ),
                hidden_imports=tuple(
                    str(mod) for mod in item.get("hidden_imports", [])
                ),
                icon=str(item.get("icon", "")),
            )
        )
    return tuple(found)


def entry_point(app: App, suite_root: Path) -> Path:
    """Return the script the application is built from.

    ``<suite>/<id>/src/<id>/__main__.py`` -- the file the spec hands to
    PyInstaller. Its EXISTENCE is the switch: an application enters the
    bundle the day this file exists, so an application under
    development keeps it out until it opens.

    Args:
        app: The catalog entry.
        suite_root: The folder holding the sibling repositories.

    Returns:
        The path, existing or not.
    """
    return suite_root / app.app_id / "src" / app.app_id / "__main__.py"


def for_build(suite_root: Path) -> tuple[list[App], list[str]]:
    """Return the applications this build can carry, and why not the rest.

    Deciding here rather than in the spec keeps the rule testable
    without running PyInstaller. An OPTIONAL application whose sibling
    checkout is absent is skipped BY NAME -- said, never silent, because
    a bundle missing an application looks identical from the outside.
    A REQUIRED one that is absent refuses the build, which is what
    happened before too, only now it says which.

    Args:
        suite_root: The folder holding the sibling repositories.

    Returns:
        ``(buildable, skipped)``: the applications to build, in catalog
        order, and one line per optional application left out.

    Raises:
        SystemExit: Naming a required application whose entry point is
            missing.
    """
    buildable: list[App] = []
    skipped: list[str] = []
    for app in apps():
        script = entry_point(app, suite_root)
        if script.is_file():
            buildable.append(app)
        elif app.optional:
            skipped.append(
                f"SKIPPED optional app {app.app_id}: no sibling checkout "
                f"at {script}"
            )
        else:
            raise SystemExit(
                f"refusing to build: {app.app_id} is a required "
                f"application and {script} does not exist"
            )
    return buildable, skipped


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
