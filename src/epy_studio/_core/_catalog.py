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
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "App",
    "REGISTER_MODES",
    "SHIPS_INSTALLED",
    "SHIPS_MODES",
    "SHIPS_OWN_INSTALLER",
    "SHIPS_WITH_STUDIO",
    "adopted_cli_env",
    "apps",
    "catalog_path",
    "craft_env",
    "download_page",
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

SHIPS_INSTALLED = "installed"
"""A foreign application the family ADOPTS and Studio's INSTALLER installs.

The ArtCraft applications (``github.com/storytold``) live here, renamed into
the ePy family: ``epy_cadcraft``, ``epy_photocraft``, ``epy_wordcraft`` and
the rest (owner directive 2026-10-07: "artcraft pasa a ser epy_artcraft, y
asi todas, con el prefijo epy_"). They are pure-Rust, MIT OR Apache-2.0
clean-room reimplementations of Adobe / Microsoft / Autodesk products.

They are not Python, so PyInstaller can never produce them, and Studio's
BUILD never touches them -- but Studio's INSTALLER does: it copies the
upstream tree the owner drops under ``dist/epy_studio/crafts/<binary>/`` into
``{app}\\crafts\\<binary>\\``, behind ``#ifexist`` so the build still works
when the tool was not staged. That is the difference from
:data:`SHIPS_OWN_INSTALLER` (the application supplies its own installer) and
from a plain foreign binary on ``PATH``: an installed one ships WITH this
bundle.

``binary`` is the upstream executable stem (``cadcraft``) while ``id`` is the
family name (``epy_cadcraft``); the file on disk keeps the upstream name, so
the installer renames nothing the tool itself depends on. An installed
application MUST record its ``upstream`` URL -- a foreign program the bundle
redistributes without saying where it came from is exactly the claim this
repository refuses to ship -- and always carries ``register: "none"`` (it
owns its own file types).

The three axes stay independent: ``optional`` says the binary may be absent
at BUILD time; ``ships`` says which route the application reaches the user
by; ``register`` says what it claims."""


SHIPS_MODES = frozenset(
    {SHIPS_WITH_STUDIO, SHIPS_OWN_INSTALLER, SHIPS_INSTALLED}
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


def adopted_cli_env(app_id: str) -> str:
    """Return the environment variable naming an adopted app's ``-cli``.

    The adopted tools ship a ``<name>-cli`` (batch/MCP) beside their GUI
    ``<name>.exe``. A launched application reaches that CLI by reading this
    variable, so Studio sets it for every adopted tool it can find.
    ``EPY_<ID>_CLI`` -- a SEPARATE name from :func:`external_exe_env`,
    because the two are different executables of the same project.

    Args:
        app_id: The catalog id, e.g. ``cadcraft``.

    Returns:
        ``EPY_<ID>_CLI`` in upper case, e.g. ``EPY_CADCRAFT_CLI``.
    """
    return f"{_EXE_ENV_PREFIX}{app_id.upper()}_CLI"


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
        install_page: Where a user installs an ADOPTED application, when
            the catalog declares it. Empty for our own applications and
            for an adopted one whose page is instead derived from
            ``upstream`` (:func:`download_page`).
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
    binary: str = ""
    install_page: str = ""

    @property
    def exe_stem(self) -> str:
        """The executable stem to look for: the upstream one when named.

        An adopted application keeps the upstream file name on disk
        (``cadcraft.exe``) while its family id is the ePy one
        (``epy_cadcraft``); the resolver looks for the BINARY, so the
        installer renames nothing the tool itself depends on.
        """
        return self.binary or self.app_id

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


_GITHUB_RE = re.compile(r"github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)")


def download_page(app: App) -> str:
    """Return where a user gets an ADOPTED application, or ``""``.

    Studio never redistributes an adopted application, so installing one
    means the user fetches it from its own project. The page is the
    explicit ``install.page`` the catalog may declare, and otherwise the
    GitHub releases page of the repository the ``upstream`` field already
    names -- derived from the provenance the entry is REQUIRED to carry,
    never invented. An application whose ``upstream`` names no GitHub
    repository yields ``""`` and the selector offers no install link.

    Args:
        app: The catalog entry.

    Returns:
        A URL, or ``""`` when none can be derived.
    """
    if app.install_page:
        return app.install_page
    match = _GITHUB_RE.search(app.upstream)
    if match is None:
        return ""
    return f"https://github.com/{match.group(1)}/releases"


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
        if ships == SHIPS_INSTALLED:
            if not item.get("upstream"):
                raise ValueError(
                    f"{item['id']}: ships={ships!r} needs upstream, the "
                    f"project URL (and license) the adopted application comes "
                    f"from. A bundle that redistributes a foreign program "
                    f"without naming its source is a bundle that lies, and "
                    f"this repository refuses to ship one."
                )
            if not item.get("component"):
                raise ValueError(
                    f"{item['id']}: ships={ships!r} needs component, the Inno "
                    f"component that installs it. Studio's installer is what "
                    f"puts an installed application on the machine, so an "
                    f"entry with no component installs nothing."
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
                binary=str(item.get("binary", "")),
                install_page=str(
                    (item.get("install") or {}).get("page", "")
                ),
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
            why = {
                SHIPS_OWN_INSTALLER: "ships with its own installer",
                SHIPS_INSTALLED: "is installed by Studio's installer",
            }.get(app.ships, "is not built here")
            skipped.append(
                f"NOT BUILT HERE: {app.app_id} {why} ({app.ships}); "
                f"Studio does not build it"
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
    if app.ships == SHIPS_INSTALLED:
        return _installed_exe(app)
    for folder in _own_install_dirs(app):
        candidate = folder / f"{app.app_id}.exe"
        if candidate.is_file():
            return candidate
    return None


def _installed_exe(app: App) -> Path | None:
    r"""Locate an INSTALLED adopted application, or ``None``.

    Routes, most specific first. The first two let a user who keeps a copy
    elsewhere point at it; the third is where THIS bundle installs it (the
    ``crafts\<binary>`` tree beside the launcher); the rest are the
    conventional upstream install folders, for a machine that installed
    the tool on its own.

    1. The environment variable :func:`external_exe_env` names.
    2. ``PATH``.
    3. ``<launcher>\crafts\<binary>\<binary>.exe``, then
       ``<launcher>\<binary>.exe``.
    4. ``%LOCALAPPDATA%\Programs\<binary>`` and the ``%ProgramFiles%`` roots.

    Absence is a normal answer -- the tool may not have been staged -- so
    every miss returns ``None`` rather than raising.

    Args:
        app: The catalog entry.

    Returns:
        The executable, or ``None`` when it is not installed.
    """
    stem = app.exe_stem
    named = os.environ.get(external_exe_env(stem), "")
    if named and Path(named).is_file():
        return Path(named)
    on_path = shutil.which(stem)
    if on_path:
        return Path(on_path)
    for folder in (install_dir() / "crafts" / stem, install_dir()):
        candidate = folder / f"{stem}.exe"
        if candidate.is_file():
            return candidate
    for folder in _installed_dirs(stem):
        candidate = folder / f"{stem}.exe"
        if candidate.is_file():
            return candidate
    return None


def _installed_dirs(stem: str) -> tuple[Path, ...]:
    """Where the upstream tool's conventional install folder may be."""
    found: list[Path] = []
    for base in ("LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)"):
        root = os.environ.get(base)
        if not root:
            continue
        # LOCALAPPDATA holds per-user installs under Programs\\, the two
        # ProgramFiles roots hold machine installs directly.
        folder = Path(root) / "Programs" / stem \
            if base == "LOCALAPPDATA" else Path(root) / stem
        found.append(folder)
    return tuple(found)


def _adopted_cli(app: App) -> Path | None:
    """Locate an adopted app's ``<name>-cli`` executable, or ``None``.

    The CLI ships BESIDE the GUI executable, so the search is the same one
    :func:`_installed_exe` runs, ending at the app's own folder. The stem is
    the UPSTREAM one (``cadcraft``), not the family id.
    """
    stem = f"{app.exe_stem}-cli"
    named = os.environ.get(adopted_cli_env(app.exe_stem), "")
    if named and Path(named).is_file():
        return Path(named)
    on_path = shutil.which(stem)
    if on_path:
        return Path(on_path)
    exe = installed_exe(app)
    if exe is not None:
        for candidate in (f"{stem}.exe", stem):
            beside = exe.parent / candidate
            if beside.is_file():
                return beside
    return None


def craft_env() -> dict[str, str]:
    """Return every adopted CLI found, as environment variables for a child.

    The "hint, never a dependency" handoff for the adopted ArtCraft tools,
    beside the ePy Docs backend in :mod:`._backends`: for every adopted
    application the catalog carries, this finds its ``<name>-cli`` and
    returns ``EPY_<NAME>_CLI`` -> its path. A launched application -- or a
    drawing flow IT drives -- then reaches the tool without importing
    anything of Studio's, and an application started any other way behaves
    the same minus the shortcut.

    This is also how a drawing flow reaches ``cadcraft-cli convert`` when it
    was started FROM the Studio: Studio sets the variable, and
    ``epy_plotter`` reads it. A machine with the tool on ``PATH`` works even
    without Studio.

    Returns:
        Variables to add to a child's environment; empty when no adopted
        tool is installed.
    """
    found: dict[str, str] = {}
    for app in apps():
        if app.ships != SHIPS_INSTALLED:
            continue
        cli = _adopted_cli(app)
        if cli is not None:
            found[adopted_cli_env(app.exe_stem)] = str(cli)
    return found


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
