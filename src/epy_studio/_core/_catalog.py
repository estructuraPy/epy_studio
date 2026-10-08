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
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "App",
    "REGISTER_MODES",
    "SHIPS_EXTERNAL",
    "SHIPS_MODES",
    "SHIPS_OWN_INSTALLER",
    "SHIPS_WITH_STUDIO",
    "apps",
    "catalog_path",
    "entry_point",
    "external_exe_env",
    "for_build",
    "install_dir",
    "installed_exe",
]

REGISTER_MODES = frozenset({"default", "openwith", "none"})
"""What an application may do with the document types it names.

``default`` claims the handler, ``openwith`` advertises an Open-with
entry only, and ``none`` claims nothing at all: no ``--register``, no
``[Run]`` line in the installer. An application that authors no
document type has nothing to register.
"""

SHIPS_WITH_STUDIO = "studio"
"""Studio's own build produces this application's executable."""

SHIPS_OWN_INSTALLER = "own_installer"
"""The application ships on its own and Studio only OFFERS it.

A third axis, independent of ``optional`` and ``register``. ``optional``
says the sibling checkout may be absent when Studio is BUILT; this says
Studio never builds the application at all, because it has its own
installer and its own install directory.

It exists for an application that is a FRONT END over other libraries
rather than a self-contained editor. Measured on epy_lab, 2026-09-25:
its own PyInstaller spec collects EIGHTEEN packages -- itself plus
epy_analysis, epy_plotter, epy_units and fourteen design libraries --
plus the openseespy and Pynite engines, while every application Studio
builds needs only its own ``src`` tree and pandoc. Studio's
``_app_analysis`` gives each application ``pathex=[<its own src>]`` and
one ``_config`` tree, so bundling that one would mean teaching the spec
to carry a dependency closure, and the bundle already stands at 6.7 GB.

So Studio offers the door and the application supplies itself. The
selector finds it through :func:`installed_exe` instead of assuming the
executable sits beside the launcher.
"""

SHIPS_EXTERNAL = "external"
"""A foreign application the family ADOPTS and Studio only OFFERS.

The ArtCraft applications (``github.com/storytold``) live here. They are
pure-Rust, Apache-2.0 clean-room reimplementations of Adobe / Microsoft
/ Autodesk products -- Photoshop, Illustrator, Word, Excel, AutoCAD and
the rest -- adopted into the ePy family as its own creative and CAD
tools. They are not Python, so PyInstaller can never produce them, and
they carry their own upstream installers, so this repository installs
nothing and registers nothing on their behalf.

Unlike :data:`SHIPS_OWN_INSTALLER`, there is no Inno AppId to read: an
adopted application is located by a documented resolver instead -- an
environment variable (:func:`external_exe_env`), then ``PATH``, then the
conventional install folders. And unlike it, an adopted application
MUST record its ``upstream`` URL: a foreign application the bundle
offers without saying where it came from is exactly the kind of claim
this repository refuses to ship.

The three axes stay independent: ``optional`` says a sibling checkout
may be absent at BUILD time; ``ships`` says which of the three routes
the application reaches the user by; ``register`` says what it claims.
An adopted application is always ``optional`` (most machines do not have
it) and always ``register: "none"`` (it owns its own file types, and the
ePy bundle must not claim a document type on a program it does not
produce)."""


SHIPS_MODES = frozenset(
    {SHIPS_WITH_STUDIO, SHIPS_OWN_INSTALLER, SHIPS_EXTERNAL}
)
"""The three ways an application can reach the user."""

_EXE_ENV_PREFIX = "EPY_"
"""Prefix of the variable that points at an adopted application's exe.

``EPY_CADCRAFT_EXE`` and the rest. The same convention the selector
already uses to hand ePy Docs to the applications it launches, and the
one a user who installed a tool somewhere unusual can set without a
rebuild.
"""


def external_exe_env(app_id: str) -> str:
    """Return the environment variable naming an adopted app's executable.

    Args:
        app_id: The catalog id, e.g. ``cadcraft``.

    Returns:
        ``EPY_<ID>_EXE`` in upper case, e.g. ``EPY_CADCRAFT_EXE``.
    """
    return f"{_EXE_ENV_PREFIX}{app_id.upper()}_EXE"


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
        upstream: Where an ADOPTED application comes from -- its project
            URL and license. Empty for an application of ours, which
            needs no provenance because this repository IS one. For an
            adopted one it is required: the selector shows a foreign
            program, and the reader is owed the name of its source.
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
    ships: str = SHIPS_WITH_STUDIO
    own_install_appid: str = ""
    upstream: str = ""

    @property
    def claims_default(self) -> bool:
        """Whether this application may register as the default handler."""
        return self.register == "default"

    @property
    def registers(self) -> bool:
        """Whether this application registers any document type at all."""
        return self.register != "none"

    @property
    def built_here(self) -> bool:
        """Whether Studio's own build produces this executable."""
        return self.ships == SHIPS_WITH_STUDIO


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
        ships = str(item.get("ships", SHIPS_WITH_STUDIO))
        if ships not in SHIPS_MODES:
            raise ValueError(
                f"{item['id']}: ships is {ships!r}, which is none of "
                f"{sorted(SHIPS_MODES)}. Refused rather than defaulted: "
                f"falling back to {SHIPS_WITH_STUDIO!r} would put an "
                f"application into the build that was meant to stay out."
            )
        if ships == SHIPS_OWN_INSTALLER and not item.get("own_install_appid"):
            raise ValueError(
                f"{item['id']}: ships={ships!r} needs own_install_appid, the "
                f"Inno AppId its own installer records. Without it the "
                f"selector can only guess at the default folder, and an "
                f"application installed elsewhere reads as not installed."
            )
        if ships == SHIPS_EXTERNAL and not item.get("upstream"):
            raise ValueError(
                f"{item['id']}: ships={ships!r} needs upstream, the project "
                f"URL (and license) the adopted application comes from. An "
                f"entry that offers a foreign program without naming its "
                f"source is a bundle that lies, and this repository refuses "
                f"to ship one."
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
                ships=ships,
                own_install_appid=str(item.get("own_install_appid", "")),
                upstream=str(item.get("upstream", "")),
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
        if not app.built_here:
            # Said by name like every other omission. An own-installer
            # application's entry point very probably DOES exist in the
            # sibling checkout -- epy_lab has one -- so checking the file
            # would build an application the catalog declares Studio does
            # not build; an adopted one is not even Python.
            why = (
                "ships with its own installer"
                if app.ships == SHIPS_OWN_INSTALLER
                else "is adopted upstream"
            )
            skipped.append(
                f"NOT BUILT HERE: {app.app_id} {why} ({app.ships}); "
                f"Studio offers it and does not bundle it"
            )
            continue
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


def installed_exe(app: App) -> Path | None:
    r"""Where this application's executable actually is, or ``None``.

    An application Studio BUILDS sits beside the launcher, which is the
    assumption every caller made. One that ships with its own installer
    does not: it installs into its own folder -- epy_lab's own script
    says ``{localappdata}\\Programs\\epy_lab`` -- and the user may have
    chosen another during setup, so the folder is READ and not assumed.

    Two routes, in that order:

    1. The Inno uninstall key its own installer wrote, which honours a
       custom folder. Per-user installs land in HKCU; Inno suffixes the
       AppId with ``_is1``.
    2. The default folder its script declares, for the case where the
       registry cannot be read.

    Args:
        app: The catalog entry.

    Returns:
        The executable, or ``None`` when it is not installed.
    """
    if app.built_here:
        candidate = install_dir() / f"{app.app_id}.exe"
        return candidate if candidate.is_file() else None
    if app.ships == SHIPS_EXTERNAL:
        return _external_exe(app)
    for folder in _own_install_dirs(app):
        candidate = folder / f"{app.app_id}.exe"
        if candidate.is_file():
            return candidate
    return None


def _external_exe(app: App) -> Path | None:
    r"""Locate an ADOPTED application, which installed itself somewhere.

    Three routes, most specific first, because an adopted application is
    a foreign program whose folder is not something this repository ever
    chose:

    1. The environment variable :func:`external_exe_env` names. A person
       who installed it somewhere unusual can point at it without a
       rebuild, and a test can point at a fixture.
    2. ``PATH``. A per-user or machine install that put its launcher on
       the path -- the common release case for all of these.
    3. The conventional install folders (an ``<Name>`` folder under
       ``%LOCALAPPDATA%\\Programs`` or ``%ProgramFiles%``).

    Absence is the normal answer -- most machines do not have it -- so
    every miss returns ``None`` rather than raising.

    Args:
        app: The catalog entry.

    Returns:
        The executable, or ``None`` when it is not installed.
    """
    named = os.environ.get(external_exe_env(app.app_id), "")
    if named and Path(named).is_file():
        return Path(named)
    on_path = shutil.which(app.app_id)
    if on_path:
        return Path(on_path)
    for folder in _external_dirs(app):
        candidate = folder / f"{app.app_id}.exe"
        if candidate.is_file():
            return candidate
    return None


def _external_dirs(app: App) -> tuple[Path, ...]:
    """Where an adopted application's conventional install folder may be."""
    found: list[Path] = []
    for base in ("LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)"):
        root = os.environ.get(base)
        if not root:
            continue
        # LOCALAPPDATA holds per-user installs under Programs\\, the two
        # ProgramFiles roots hold machine installs directly.
        folder = Path(root) / "Programs" / app.app_id \
            if base == "LOCALAPPDATA" else Path(root) / app.app_id
        found.append(folder)
    return tuple(found)


def _own_install_dirs(app: App) -> tuple[Path, ...]:
    """Where a separately-installed application may be, best route first."""
    found: list[Path] = []
    recorded = _uninstall_location(app.own_install_appid)
    if recorded is not None:
        found.append(recorded)
    local = os.environ.get("LOCALAPPDATA")
    if local:
        found.append(Path(local) / "Programs" / app.app_id)
    return tuple(found)


def _uninstall_location(appid: str) -> Path | None:
    """The ``InstallLocation`` an Inno per-user install recorded, if any.

    Read through ``winreg`` rather than by shelling out to ``reg``: this
    runs while the selector is being drawn, and a subprocess per
    application is a visible pause on a cold start.

    Absence is the normal answer -- the application is simply not
    installed -- so every failure returns ``None`` rather than raising.
    """
    if not appid:
        return None
    try:
        import winreg  # noqa: PLC0415 - Windows only, and only when asked
    except ImportError:
        return None
    key = (r"Software\Microsoft\Windows\CurrentVersion\Uninstall"
           rf"\{appid}_is1")
    for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(root, key) as handle:
                where, _kind = winreg.QueryValueEx(handle, "InstallLocation")
        except OSError:
            continue
        if where:
            return Path(str(where))
    return None
