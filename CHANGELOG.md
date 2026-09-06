# Changelog

All notable changes to `epy_studio` are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **An application may be optional.** The catalog gained `optional`,
  `register: none`, and the build-time lists the spec used to carry in
  code (`asset_packages`, `hidden_imports`, `icon`), so a new
  application really is one catalog entry. An optional application
  whose sibling checkout is absent is skipped BY NAME at build time,
  its installer lines sit inside `#ifexist` blocks so the script
  compiles either way, the probes report it as skipped rather than
  missing, and when its executable is not installed the selector does
  not offer it at all -- not greyed, absent. A required application
  keeps every contract it had: an absent checkout refuses the build,
  naming it, and an absent executable keeps its greyed row.
- The first optional entry: `epy_quoting` (ePy Quoting), a private
  application for service offers, developed separately. Nothing the
  user receives changes until its executable exists.
- **A release manifest** (`release.epyson`) and its check. The catalog
  answers what the bundle CAN carry; this answers what the release
  being cut PROMISES to carry, and the release step refuses a bundle
  that is short. The two questions were the same while every
  application was required; they stop being the same the moment one
  can be absent, and a release is where nobody re-reads a build log.

### Changed
- **`optional` now follows PRIVACY, and ePy Draft is optional.** Its
  repository is private while this one is public, so a clone of this
  repository could not be built at all: the build refused, naming a
  checkout a stranger cannot have. The three public editors stay
  required. Draft keeps its `openwith` registration, so its `[Run]`
  lines are guarded like the rest -- optional and register are
  independent axes.
- The release script no longer assumes ePy Draft is installed, and the
  installed-bundle probe skips the file types of an application this
  release does not carry.

## [0.7.0] — 2026-09-05

### Changed
- **Ships ePy Draft 0.2.1.** The project is its `.kepy`: it opens by
  file or by folder under any name, *New project* makes the working
  folders, *Seal into one file* writes a `.zepy` whose integrity is
  checkable, structural drawings (`.dxf`) are indexed, and the prompts,
  rubrics and document identity belong to the project rather than to
  the machine -- so two projects no longer share a client, and the same
  project opened elsewhere has its own prompts. See epy_draft's
  changelog for the eight defects that closed with it.
- Ships epy_reports 0.5.1, epy_slides 0.4.1, epy_papers 0.4.1 and the
  shared engine at 0.2.0, unchanged.
- The shipped-fixes probe names five literals of the new ePy Draft. The
  previous row named a function that release retired, so an unchanged
  probe list would have refused this build -- which is what the probe
  is for.

## [0.6.1] — 2026-09-05

### Fixed
- **Ships a working PDF export.** Two imports in epy_reports' export
  path still named a module that had moved to the shared engine, so
  every PDF export from that window failed in the 0.6.0 bundle. The
  build carried it because the imports are inside the export function
  and nothing on the way to a bundle reaches them.

### Changed
- Ships epy_reports 0.5.1, epy_slides 0.4.1, epy_papers 0.4.1 and ePy
  Draft 0.1.0, and the shared engine at 0.2.0.
- This housekeeper runs the same nine audits as the rest of the suite,
  with `--strict`, instead of the three it was frozen at.

## [0.6.0] — 2026-09-04

### Added
- **A first-start offer to register the file associations.** Every
  `[Run]` entry in the installer carries `skipifsilent`, so a silent
  deployment installs ePy Studio and registers nothing: the documents it
  was installed for keep opening in whatever handled them before, with
  nothing on screen to say why. The first start now asks, once, and
  remembers either answer. Saying no writes nothing at all; saying yes
  adds an "Open with" entry (Windows still asks the reader to confirm a
  default in Settings) and asks each installed editor to register
  itself. A source checkout never writes the registry, and a machine
  whose policy blocks the read is never asked again.

### Fixed
- **The selector never found the language a reader had already chosen.**
  It read `language` under `ANM Ingenieria` while three editors wrote it
  under `ANM Ingeniería` — on Windows, two registry trees. The
  organisation name now comes from `epy_export.ORGANIZATION`, one place
  for the whole family, and the unaccented scope this launcher and ePy
  Draft used to write is still read after it, so nobody is asked twice.
- The layout section of the README still described three applications
  and a module that had been moved.

### Changed
- **The build refuses to ship a stale bundle.** `SHIPPED_FIXES` names a
  module and a literal per fix that must be present inside each produced
  executable's PYZ; the build fails when one is missing. It now covers
  the optional autosave in all three editors and the shared settings
  identity in the launcher.
- Ships epy_reports 0.5.0, epy_slides 0.4.0, epy_papers 0.4.0 and ePy
  Draft 0.1.0.

## [0.5.0] — 2026-08-29

### Added
- **A fourth application: ePy Craft** (0.1.0), batch LLM processing over
  your own reference library. It advertises an "Open with" entry only and
  never registers as the default handler, because it consumes Markdown and
  text as batch INPUT and authors neither.

### Fixed
- **The bundle carried torch and tensorflow, and nothing imports them.**
  Measured: 872 MB / 3,429 files in June against 6.7 GB / 12,840 files
  now, of which torch was 3.5 GB and tensorflow 1.2 GB, plus cv2,
  nltk_data, faiss, pyarrow, scipy, kaleido, llvmlite and imageio_ffmpeg.

  None of it is used. The chain starts at a dependency nothing imports:
  epy_reports declares plotly, but its `_core/_plotly` imports only `re`
  -- a plotly fence becomes a div and a JSON payload that the bundled
  Plotly.js draws in the page. PyInstaller still found plotly in the
  build environment and its hook pulled kaleido, skimage, scipy, torch
  and tensorflow behind it.

  Worse than the size is what it meant: the bundle's contents depended on
  what happened to be installed on the machine doing the build, so the
  same commit shipped differently from two laptops.

  **6.7 GB to 1.02 GB**, 12,840 to 3,688 files, all five executables
  present and all four applications starting. Verified where a smoke test
  cannot reach: a report carrying a plotly fence still renders its figure
  with plotly, kaleido, torch and scipy blocked at import.

### Changed
- Ships epy_reports 0.4.4, epy_slides 0.3.1, epy_papers 0.3.1 and
  epy_craft 0.1.0.
- The epy_docs exclusion now records the reasons that bind -- it is a
  commercial package while this installer is a free MIT download, and
  bundling it would not work regardless, since it shells out to `quarto`
  and to a TeX distribution that PyInstaller cannot collect.

## [0.4.1] — 2026-08-06

### Fixed
- Ships epy_reports 0.4.4, epy_slides 0.3.1 and epy_papers 0.3.1: the
  welcome document's scripting example no longer shows an import that
  fails, and the Ubuntu `.deb` packagers no longer build themselves as
  version 0.0.0.

### Changed
- The three bundled editors now share one internal layout — same
  folders, same module names — so a fix written in one lands in the
  same place in the others. No user-facing behaviour changed.

## [0.4.0] — 2026-08-05

### Fixed
- **Office exports carry the right geometry** (ships epy_reports 0.4.3,
  epy_slides 0.3.0): PowerPoint decks no longer overflow their slides —
  exported placeholders get shrink-on-overflow with a computed font
  scale, and the reference typography now matches the live preview;
  Word exports honor the document's `page-size:` (letter / a4 / legal)
  instead of the reference doc's fixed size or the reader's locale.

### Added
- **4:3 PowerPoint export** (epy_slides): `aspect-ratio: "4:3"` decks
  export on a true 10 x 7.5 in canvas.

## [0.3.2] — 2026-08-05

### Fixed
- **PDF links now navigate** (ships epy_reports 0.4.1, epy_slides
  0.2.1): exported PDFs kept their link annotations but internal links
  were dead — the stamping/scaling passes dropped the named
  destinations they point at. TOC, index and cross-reference links in
  the PDF now jump, and external links open.

## [0.3.1] — 2026-08-05

### Fixed
- **Startup crash: "no Qt platform plugin could be initialized".** Bundles
  built on conda machines shipped without the Qt runtime pieces
  (`qwindows.dll`, `QtWebEngineProcess.exe`, WebEngine resources):
  the conda ICU shadowed the system one, PyInstaller's isolated Qt
  introspection failed to import PySide6, and the plugin collection was
  skipped silently. The build now pins the System32 ICU for the whole
  build process tree (`windows/build_support/sitecustomize.py`) and
  `build.py` refuses to ship a bundle whose Qt runtime is incomplete.
- The spec now strips any ICU DLL picked up from the build environment,
  so a bundled conda ICU can never shadow the system one Qt links
  against on end-user machines.

## [0.3.0] — 2026-08-05

### Added
- Preview navigation parity across the three editors (in-page links,
  external links to the system browser, Back/Forward with position or
  slide restore): ships epy_reports 0.4.0, epy_slides 0.2.0,
  epy_papers 0.3.0.

## [0.2.0] — 2026-08-05

### Added
- Ships epy_reports 0.4.0 (working preview links + history) and
  epy_papers 0.2.0 (file-association CLI).

## [0.1.0] — 2026-08-05

Initial release. One PyInstaller bundle with four executables
(`epy_studio` launcher selector, `epy_reports`, `epy_slides`,
`epy_papers`) over a single shared `_internal/` runtime, an Inno Setup
installer with per-app components, HKCU file associations for
`.md` / `.markdown` / `.qmd`, and a bilingual user manual.
