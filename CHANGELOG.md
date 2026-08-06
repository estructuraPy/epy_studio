# Changelog

All notable changes to `epy_studio` are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
