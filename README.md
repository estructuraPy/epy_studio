# ePy Studio

Unified entry point and installer for the ePy document editors:
[epy_reports](https://github.com/estructuraPy/epy_reports),
[epy_slides](https://github.com/estructuraPy/epy_slides) and
[epy_papers](https://github.com/estructuraPy/epy_papers).

One `setup.exe`, component selection per editor, ONE shared PyInstaller
runtime (a single real `_internal/` — no junctions), and a selector
window that forwards a double-clicked `.md` / `.markdown` / `.qmd` to
whichever editor fits the job.

## Layout

```
launcher.py        selector window + --register/--unregister CLI
_assoc.py          HKCU file-association helpers (Studio identity)
epy_studio.spec    multi-exe PyInstaller spec (3 apps + launcher, one COLLECT)
build.py           builds dist/epy_studio/ (installer input)
windows/           Inno Setup script (components: reports/slides/papers)
docs/              user manual (English + Spanish), shipped with the app
```

## Build

From this directory, with the four app repos as siblings and
`pip install -e` applied to each:

```
python build.py
ISCC.exe windows\epy_studio.iss
```

Output: `dist/epy_studio-setup-<version>.exe`.

## Design notes

- The four applications deduplicate through PyInstaller `COLLECT` (identical
  runtime files collapse to one copy) — never share a runtime through
  NTFS junctions: the Windows loader refuses DLLs behind reparse points.
- Windows 10/11 cannot be given a default app silently (`UserChoice` is
  HMAC-signed); the installer registers capabilities and the user
  confirms once in Settings → Default apps.

## License

MIT — Ing. Angel Navarro-Mora M.Sc., ANM Ingeniería.
