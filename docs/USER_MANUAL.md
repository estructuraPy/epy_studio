# ePy Studio — User Manual

ePy Studio is the entry point for the ePy document editors. It installs
the three tools from a single setup, shares one runtime between them
(one install ≈ a third of the size of three separate ones), and gives
every Markdown document a single door: double-click a file, pick the
editor that fits the job.

Author: Ing. Angel Navarro-Mora M.Sc. — ANM Ingeniería.

## The three editors

| Tool | Use it for | Exports |
|---|---|---|
| **ePy Reports** | Technical reports with live preview | PDF, Word, self-contained HTML |
| **ePy Slides** | Presentation decks | reveal.js HTML, PowerPoint |
| **ePy Papers** | Academic manuscripts | Journal-template PDF |

All three edit the same source format — Markdown with Quarto
extensions — so a document can move between them without conversion.

## Opening documents

There are three ways in:

1. **Double-click a `.md` / `.markdown` / `.qmd` file.** When ePy
   Studio is your default app, the selector window opens showing the
   file name; click the editor you want and the file opens there.
2. **Start Menu.** "ePy Studio" opens the selector without a file;
   each editor also has its own direct shortcut.
3. **Open with.** Right-click any Markdown file → *Open with* → pick
   ePy Studio or one of the editors directly.

## Making ePy Studio the default for .md

The installer registers ePy Studio and offers to open Windows Settings
at *Default apps*. Windows requires one manual confirmation (the
default-app choice is cryptographically signed and no installer can set
it silently):

1. Open *Settings → Apps → Default apps → ePy Studio*.
2. Click each extension (`.md`, `.markdown`, `.qmd`) and select
   **ePy Studio**.

Equivalent shortcut: right-click a `.md` file → *Open with → Choose
another app* → ePy Studio → check **Always**.

## Choosing what to install

The installer's *Custom installation* page lets you tick each editor.
The shared runtime and the selector always install; unticked editors
simply do not appear (their row in the selector shows "not installed").
Re-run the installer at any time to add or remove components.

## Languages

Every editor is bilingual (English / Spanish): the interface language
switches from each app's *Language* menu, and numbered captions
("Figure 1" / "Figura 1"), cross-references and generated indexes
follow the interface language automatically. A document can pin its
own language regardless of the interface with front matter:

```yaml
---
lang: es
---
```

## Updating and uninstalling

- **Update**: install the newer `epy_studio-setup-x.y.z.exe` on top;
  settings and documents are untouched.
- **Uninstall**: *Settings → Apps → Installed apps → ePy Studio*.
  File associations registered by the Studio are removed automatically.

## Troubleshooting

- **An editor button says "not installed"** — re-run the installer and
  tick that component.
- **Double-clicking a file opens another program** — the Windows
  default was not confirmed; see *Making ePy Studio the default* above.
- **The selector opens but the editor does not** — start the editor
  from its Start Menu shortcut once and check the error it reports.
