; Inno Setup script for ePy Studio — unified installer for the ePy
; document apps (epy_reports, epy_slides, epy_papers), ePy Draft
; (epy_draft) + launcher.
;
; Build from the epy_studio directory AFTER running `python build.py`:
;   ISCC.exe windows\epy_studio.iss
;
; Output: dist\epy_studio-setup-<AppVersion>.exe
; NOTE: bump AppVersion together with the release tag.
;
; Design decisions:
;   - ONE PyInstaller bundle: all apps share a single REAL _internal/
;     runtime (no junctions/symlinks — see the 2026-06-20 shared-runtime
;     incident). Components therefore toggle only each app's EXE,
;     shortcuts and file-type registration; the runtime always installs.
;   - PrivilegesRequired=lowest -> per-user install; no UAC prompt. The
;     file-association backends write HKCU, consistent with a per-user
;     install.
;   - Windows 10/11 UserChoice limitation: no installer can silently set
;     a default app (the UserChoice key is HMAC-signed by Windows). The
;     per-app --register --as-default writes the legacy handler and the
;     Capabilities tree so each app appears in Settings > Default apps;
;     the user confirms the default there or via "Open with > Always".

#define AppName "ePy Studio"
#define AppDirName "epy_studio"
#define AppVersion "0.8.4"
#define AppPublisher "Ing. Angel Navarro-Mora M.Sc."
#define AppURL "https://github.com/estructuraPy/epy_studio"
#define AppId "{{7E2F9A41-5C38-4D06-B1E9-3A8D24C7F015}"
#define DistDir "..\dist\epy_studio"
#define OutputDir "..\dist"

[Setup]
AppId={#AppId}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
DefaultDirName={localappdata}\Programs\{#AppDirName}
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=commandline
OutputDir={#OutputDir}
OutputBaseFilename=epy_studio-setup-{#AppVersion}
UninstallDisplayIcon={app}\epy_studio.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
UsePreviousGroup=yes
DisableProgramGroupPage=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[CustomMessages]
; The page where a person CHOOSES is the one page that must not be half
; translated. Inno translates its own chrome from the .isl; these are
; ours, so they are ours to translate.
english.TypeFull=Full installation (every tool)
spanish.TypeFull=Instalación completa (todas las herramientas)
english.TypeCustom=Choose which tools to install
spanish.TypeCustom=Elegir qué herramientas instalar
english.CompReports=ePy Reports — technical reports (PDF / Word / HTML)
spanish.CompReports=ePy Reports — informes técnicos (PDF / Word / HTML)
english.CompSlides=ePy Slides — presentation decks (reveal.js / PowerPoint)
spanish.CompSlides=ePy Slides — presentaciones (reveal.js / PowerPoint)
english.CompPapers=ePy Papers — academic manuscripts in a journal's shape
spanish.CompPapers=ePy Papers — manuscritos académicos con el formato de la revista
english.CompCraft=ePy Draft — batch drafting over your reference library
spanish.CompCraft=ePy Draft — redacción por lotes sobre su biblioteca de referencias
english.CompQuoting=ePy Quoting — service offers and fee quotation
spanish.CompQuoting=ePy Quoting — ofertas de servicios y cotización de honorarios
english.CompOutreach=ePy Outreach — contacts, client research and outreach letters
spanish.CompOutreach=ePy Outreach — contactos, investigación del cliente y cartas de prospección
english.CompCadcraft=ePy CAD - 2D drafting and CAD
spanish.CompCadcraft=ePy CAD - Dibujo 2D y CAD
english.CompPhotocraft=ePy Paint - Raster image editor
spanish.CompPhotocraft=ePy Paint - Editor de imágenes de mapa de bits
english.CompLightcraft=ePy Photo - RAW photo catalog and develop
spanish.CompLightcraft=ePy Photo - Catálogo y revelado de fotos RAW
english.CompFilmcraft=ePy Video - Video editor
spanish.CompFilmcraft=ePy Video - Editor de video
english.CompVectorcraft=ePy Vector - Vector graphics
spanish.CompVectorcraft=ePy Vector - Gráficos vectoriales
english.CompPdfcraft=ePy PDF - PDF authoring and batch
spanish.CompPdfcraft=ePy PDF - Autoría y lote de PDF
english.CompDeckcraft=ePy Decks - Presentations
spanish.CompDeckcraft=ePy Decks - Presentaciones
english.CompGridcraft=ePy Sheets - Spreadsheets
spanish.CompGridcraft=ePy Sheets - Hojas de cálculo
english.CompSoundcraft=ePy Audio - Audio production
spanish.CompSoundcraft=ePy Audio - Producción de audio
english.CompWordcraft=ePy Write - Word processor
spanish.CompWordcraft=ePy Write - Procesador de texto
english.CompDesigncraft=ePy Layout - Page layout and composition
spanish.CompDesigncraft=ePy Layout - Maquetación y composición de páginas
english.CompEffectcraft=ePy Motion - Motion graphics and VFX
spanish.CompEffectcraft=ePy Motion - Gráficos en movimiento y VFX


[Types]
Name: "full"; Description: "{cm:TypeFull}"
Name: "custom"; Description: "{cm:TypeCustom}"; Flags: iscustom

[Components]
Name: "reports"; Description: "{cm:CompReports}"; Types: full custom
Name: "slides"; Description: "{cm:CompSlides}"; Types: full custom
Name: "papers"; Description: "{cm:CompPapers}"; Types: full custom
; ePy Draft is a PRIVATE application, so a checkout of this
; PUBLIC repository need not carry it and the build may not
; produce its executable. Every line naming it is guarded the
; way ePy Quoting's are. Unlike Quoting it DOES register
; document types, so its [Run] lines are guarded too: optional
; and register are independent axes.
#ifexist DistDir + "\epy_draft.exe"
Name: "craft"; Description: "{cm:CompCraft}"; Types: full custom
#endif
; An OPTIONAL application: present only when the build produced it.
; Without the guard ISCC refuses to compile over a missing Source.
#ifexist DistDir + "\epy_quoting.exe"
Name: "quoting"; Description: "{cm:CompQuoting}"; Types: full custom
#endif
; An OPTIONAL application that authors no document type, so it claims
; nothing in [Run]: the guard covers its component, its file and its
; shortcut, and nothing else.
#ifexist DistDir + "\epy_outreach.exe"
Name: "outreach"; Description: "{cm:CompOutreach}"; Types: full custom
#endif

; Adopted crafting applications, installed from the staged
; dist/.../crafts/<binary>/ tree this bundle carries. Guarded like the
; optional apps: the binary may not be staged, and #ifexist keeps ISCC
; able to compile either way.
#ifexist DistDir + "\crafts\cadcraft\cadcraft.exe"
Name: "craft_cadcraft"; Description: "{cm:CompCadcraft}"; Types: full custom
#endif
#ifexist DistDir + "\crafts\photocraft\photocraft.exe"
Name: "craft_photocraft"; Description: "{cm:CompPhotocraft}"; Types: full custom
#endif
#ifexist DistDir + "\crafts\lightcraft\lightcraft.exe"
Name: "craft_lightcraft"; Description: "{cm:CompLightcraft}"; Types: full custom
#endif
#ifexist DistDir + "\crafts\filmcraft\filmcraft.exe"
Name: "craft_filmcraft"; Description: "{cm:CompFilmcraft}"; Types: full custom
#endif
#ifexist DistDir + "\crafts\vectorcraft\vectorcraft.exe"
Name: "craft_vectorcraft"; Description: "{cm:CompVectorcraft}"; Types: full custom
#endif
#ifexist DistDir + "\crafts\pdfcraft\pdfcraft.exe"
Name: "craft_pdfcraft"; Description: "{cm:CompPdfcraft}"; Types: full custom
#endif
#ifexist DistDir + "\crafts\deckcraft\deckcraft.exe"
Name: "craft_deckcraft"; Description: "{cm:CompDeckcraft}"; Types: full custom
#endif
#ifexist DistDir + "\crafts\gridcraft\gridcraft.exe"
Name: "craft_gridcraft"; Description: "{cm:CompGridcraft}"; Types: full custom
#endif
#ifexist DistDir + "\crafts\soundcraft\soundcraft.exe"
Name: "craft_soundcraft"; Description: "{cm:CompSoundcraft}"; Types: full custom
#endif
#ifexist DistDir + "\crafts\wordcraft\wordcraft.exe"
Name: "craft_wordcraft"; Description: "{cm:CompWordcraft}"; Types: full custom
#endif
#ifexist DistDir + "\crafts\designcraft\designcraft.exe"
Name: "craft_designcraft"; Description: "{cm:CompDesigncraft}"; Types: full custom
#endif
#ifexist DistDir + "\crafts\effectcraft\effectcraft.exe"
Name: "craft_effectcraft"; Description: "{cm:CompEffectcraft}"; Types: full custom
#endif

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Shared runtime + launcher + bilingual manual: always installed.
Source: "{#DistDir}\epy_studio.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#DistDir}\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\docs\USER_MANUAL.md"; DestDir: "{app}\docs"; Flags: ignoreversion
Source: "..\docs\USER_MANUAL_es.md"; DestDir: "{app}\docs"; Flags: ignoreversion
; Per-app executables, gated by component.
Source: "{#DistDir}\epy_reports.exe"; DestDir: "{app}"; Flags: ignoreversion; Components: reports
Source: "{#DistDir}\epy_slides.exe"; DestDir: "{app}"; Flags: ignoreversion; Components: slides
Source: "{#DistDir}\epy_papers.exe"; DestDir: "{app}"; Flags: ignoreversion; Components: papers
#ifexist DistDir + "\epy_draft.exe"
Source: "{#DistDir}\epy_draft.exe"; DestDir: "{app}"; Flags: ignoreversion; Components: craft
#endif
#ifexist DistDir + "\epy_quoting.exe"
Source: "{#DistDir}\epy_quoting.exe"; DestDir: "{app}"; Flags: ignoreversion; Components: quoting
#endif
#ifexist DistDir + "\epy_outreach.exe"
Source: "{#DistDir}\epy_outreach.exe"; DestDir: "{app}"; Flags: ignoreversion; Components: outreach
#endif

; Adopted crafting applications, installed from the staged
; dist/.../crafts/<binary>/ tree this bundle carries. Guarded like the
; optional apps: the binary may not be staged, and #ifexist keeps ISCC
; able to compile either way.
#ifexist DistDir + "\crafts\cadcraft\cadcraft.exe"
Source: "{#DistDir}\crafts\cadcraft\cadcraft.exe"; DestDir: "{app}\crafts\cadcraft"; Flags: ignoreversion; Components: craft_cadcraft
Source: "{#DistDir}\crafts\cadcraft\*"; DestDir: "{app}\crafts\cadcraft"; Excludes: "cadcraft.exe"; Flags: ignoreversion recursesubdirs createallsubdirs; Components: craft_cadcraft
#endif
#ifexist DistDir + "\crafts\photocraft\photocraft.exe"
Source: "{#DistDir}\crafts\photocraft\photocraft.exe"; DestDir: "{app}\crafts\photocraft"; Flags: ignoreversion; Components: craft_photocraft
Source: "{#DistDir}\crafts\photocraft\*"; DestDir: "{app}\crafts\photocraft"; Excludes: "photocraft.exe"; Flags: ignoreversion recursesubdirs createallsubdirs; Components: craft_photocraft
#endif
#ifexist DistDir + "\crafts\lightcraft\lightcraft.exe"
Source: "{#DistDir}\crafts\lightcraft\lightcraft.exe"; DestDir: "{app}\crafts\lightcraft"; Flags: ignoreversion; Components: craft_lightcraft
Source: "{#DistDir}\crafts\lightcraft\*"; DestDir: "{app}\crafts\lightcraft"; Excludes: "lightcraft.exe"; Flags: ignoreversion recursesubdirs createallsubdirs; Components: craft_lightcraft
#endif
#ifexist DistDir + "\crafts\filmcraft\filmcraft.exe"
Source: "{#DistDir}\crafts\filmcraft\filmcraft.exe"; DestDir: "{app}\crafts\filmcraft"; Flags: ignoreversion; Components: craft_filmcraft
Source: "{#DistDir}\crafts\filmcraft\*"; DestDir: "{app}\crafts\filmcraft"; Excludes: "filmcraft.exe"; Flags: ignoreversion recursesubdirs createallsubdirs; Components: craft_filmcraft
#endif
#ifexist DistDir + "\crafts\vectorcraft\vectorcraft.exe"
Source: "{#DistDir}\crafts\vectorcraft\vectorcraft.exe"; DestDir: "{app}\crafts\vectorcraft"; Flags: ignoreversion; Components: craft_vectorcraft
Source: "{#DistDir}\crafts\vectorcraft\*"; DestDir: "{app}\crafts\vectorcraft"; Excludes: "vectorcraft.exe"; Flags: ignoreversion recursesubdirs createallsubdirs; Components: craft_vectorcraft
#endif
#ifexist DistDir + "\crafts\pdfcraft\pdfcraft.exe"
Source: "{#DistDir}\crafts\pdfcraft\pdfcraft.exe"; DestDir: "{app}\crafts\pdfcraft"; Flags: ignoreversion; Components: craft_pdfcraft
Source: "{#DistDir}\crafts\pdfcraft\*"; DestDir: "{app}\crafts\pdfcraft"; Excludes: "pdfcraft.exe"; Flags: ignoreversion recursesubdirs createallsubdirs; Components: craft_pdfcraft
#endif
#ifexist DistDir + "\crafts\deckcraft\deckcraft.exe"
Source: "{#DistDir}\crafts\deckcraft\deckcraft.exe"; DestDir: "{app}\crafts\deckcraft"; Flags: ignoreversion; Components: craft_deckcraft
Source: "{#DistDir}\crafts\deckcraft\*"; DestDir: "{app}\crafts\deckcraft"; Excludes: "deckcraft.exe"; Flags: ignoreversion recursesubdirs createallsubdirs; Components: craft_deckcraft
#endif
#ifexist DistDir + "\crafts\gridcraft\gridcraft.exe"
Source: "{#DistDir}\crafts\gridcraft\gridcraft.exe"; DestDir: "{app}\crafts\gridcraft"; Flags: ignoreversion; Components: craft_gridcraft
Source: "{#DistDir}\crafts\gridcraft\*"; DestDir: "{app}\crafts\gridcraft"; Excludes: "gridcraft.exe"; Flags: ignoreversion recursesubdirs createallsubdirs; Components: craft_gridcraft
#endif
#ifexist DistDir + "\crafts\soundcraft\soundcraft.exe"
Source: "{#DistDir}\crafts\soundcraft\soundcraft.exe"; DestDir: "{app}\crafts\soundcraft"; Flags: ignoreversion; Components: craft_soundcraft
Source: "{#DistDir}\crafts\soundcraft\*"; DestDir: "{app}\crafts\soundcraft"; Excludes: "soundcraft.exe"; Flags: ignoreversion recursesubdirs createallsubdirs; Components: craft_soundcraft
#endif
#ifexist DistDir + "\crafts\wordcraft\wordcraft.exe"
Source: "{#DistDir}\crafts\wordcraft\wordcraft.exe"; DestDir: "{app}\crafts\wordcraft"; Flags: ignoreversion; Components: craft_wordcraft
Source: "{#DistDir}\crafts\wordcraft\*"; DestDir: "{app}\crafts\wordcraft"; Excludes: "wordcraft.exe"; Flags: ignoreversion recursesubdirs createallsubdirs; Components: craft_wordcraft
#endif
#ifexist DistDir + "\crafts\designcraft\designcraft.exe"
Source: "{#DistDir}\crafts\designcraft\designcraft.exe"; DestDir: "{app}\crafts\designcraft"; Flags: ignoreversion; Components: craft_designcraft
Source: "{#DistDir}\crafts\designcraft\*"; DestDir: "{app}\crafts\designcraft"; Excludes: "designcraft.exe"; Flags: ignoreversion recursesubdirs createallsubdirs; Components: craft_designcraft
#endif
#ifexist DistDir + "\crafts\effectcraft\effectcraft.exe"
Source: "{#DistDir}\crafts\effectcraft\effectcraft.exe"; DestDir: "{app}\crafts\effectcraft"; Flags: ignoreversion; Components: craft_effectcraft
Source: "{#DistDir}\crafts\effectcraft\*"; DestDir: "{app}\crafts\effectcraft"; Excludes: "effectcraft.exe"; Flags: ignoreversion recursesubdirs createallsubdirs; Components: craft_effectcraft
#endif

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\epy_studio.exe"; IconFilename: "{app}\epy_studio.exe"
Name: "{autoprograms}\ePy Reports"; Filename: "{app}\epy_reports.exe"; IconFilename: "{app}\epy_reports.exe"; Components: reports
Name: "{autoprograms}\ePy Slides"; Filename: "{app}\epy_slides.exe"; IconFilename: "{app}\epy_slides.exe"; Components: slides
Name: "{autoprograms}\ePy Papers"; Filename: "{app}\epy_papers.exe"; IconFilename: "{app}\epy_papers.exe"; Components: papers
#ifexist DistDir + "\epy_draft.exe"
Name: "{autoprograms}\ePy Draft"; Filename: "{app}\epy_draft.exe"; IconFilename: "{app}\epy_draft.exe"; Components: craft
#endif
#ifexist DistDir + "\epy_quoting.exe"
Name: "{autoprograms}\ePy Quoting"; Filename: "{app}\epy_quoting.exe"; IconFilename: "{app}\epy_quoting.exe"; Components: quoting
#endif
#ifexist DistDir + "\epy_outreach.exe"
Name: "{autoprograms}\ePy Outreach"; Filename: "{app}\epy_outreach.exe"; IconFilename: "{app}\epy_outreach.exe"; Components: outreach
#endif
; Adopted crafting applications, installed from the staged
; dist/.../crafts/<binary>/ tree this bundle carries. Guarded like the
; optional apps: the binary may not be staged, and #ifexist keeps ISCC
; able to compile either way.
#ifexist DistDir + "\crafts\cadcraft\cadcraft.exe"
Name: "{autoprograms}\ePy CAD"; Filename: "{app}\crafts\cadcraft\cadcraft.exe"; Components: craft_cadcraft
#endif
#ifexist DistDir + "\crafts\photocraft\photocraft.exe"
Name: "{autoprograms}\ePy Paint"; Filename: "{app}\crafts\photocraft\photocraft.exe"; Components: craft_photocraft
#endif
#ifexist DistDir + "\crafts\lightcraft\lightcraft.exe"
Name: "{autoprograms}\ePy Photo"; Filename: "{app}\crafts\lightcraft\lightcraft.exe"; Components: craft_lightcraft
#endif
#ifexist DistDir + "\crafts\filmcraft\filmcraft.exe"
Name: "{autoprograms}\ePy Video"; Filename: "{app}\crafts\filmcraft\filmcraft.exe"; Components: craft_filmcraft
#endif
#ifexist DistDir + "\crafts\vectorcraft\vectorcraft.exe"
Name: "{autoprograms}\ePy Vector"; Filename: "{app}\crafts\vectorcraft\vectorcraft.exe"; Components: craft_vectorcraft
#endif
#ifexist DistDir + "\crafts\pdfcraft\pdfcraft.exe"
Name: "{autoprograms}\ePy PDF"; Filename: "{app}\crafts\pdfcraft\pdfcraft.exe"; Components: craft_pdfcraft
#endif
#ifexist DistDir + "\crafts\deckcraft\deckcraft.exe"
Name: "{autoprograms}\ePy Decks"; Filename: "{app}\crafts\deckcraft\deckcraft.exe"; Components: craft_deckcraft
#endif
#ifexist DistDir + "\crafts\gridcraft\gridcraft.exe"
Name: "{autoprograms}\ePy Sheets"; Filename: "{app}\crafts\gridcraft\gridcraft.exe"; Components: craft_gridcraft
#endif
#ifexist DistDir + "\crafts\soundcraft\soundcraft.exe"
Name: "{autoprograms}\ePy Audio"; Filename: "{app}\crafts\soundcraft\soundcraft.exe"; Components: craft_soundcraft
#endif
#ifexist DistDir + "\crafts\wordcraft\wordcraft.exe"
Name: "{autoprograms}\ePy Write"; Filename: "{app}\crafts\wordcraft\wordcraft.exe"; Components: craft_wordcraft
#endif
#ifexist DistDir + "\crafts\designcraft\designcraft.exe"
Name: "{autoprograms}\ePy Layout"; Filename: "{app}\crafts\designcraft\designcraft.exe"; Components: craft_designcraft
#endif
#ifexist DistDir + "\crafts\effectcraft\effectcraft.exe"
Name: "{autoprograms}\ePy Motion"; Filename: "{app}\crafts\effectcraft\effectcraft.exe"; Components: craft_effectcraft
#endif
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\epy_studio.exe"; IconFilename: "{app}\epy_studio.exe"; Tasks: desktopicon

[Run]
; Register file associations (HKCU). The STUDIO takes --as-default so a
; double-clicked .md opens the selector (Windows still asks the user to
; confirm once in Settings — UserChoice is HMAC-signed). The individual
; apps register WITHOUT --as-default: they appear under "Open with" but
; do not compete with the Studio for the default.
; skipifsilent: silent deployments run these by hand.
Filename: "{app}\epy_studio.exe"; Parameters: "--register --as-default"; \
    Flags: runascurrentuser nowait postinstall skipifsilent; \
    Description: "Set ePy Studio as the handler for .md / .markdown / .qmd files"
Filename: "{app}\epy_reports.exe"; Parameters: "--register"; \
    Flags: runascurrentuser nowait postinstall skipifsilent; \
    Description: "Register ePy Reports under Open with"; \
    Components: reports
Filename: "{app}\epy_slides.exe"; Parameters: "--register"; \
    Flags: runascurrentuser nowait postinstall skipifsilent; \
    Description: "Register ePy Slides under Open with"; \
    Components: slides
Filename: "{app}\epy_papers.exe"; Parameters: "--register"; \
    Flags: runascurrentuser nowait postinstall skipifsilent; \
    Description: "Register ePy Papers under Open with"; \
    Components: papers
; ePy Draft advertises an "Open with" entry only, and never
; --as-default: it consumes Markdown and text as batch INPUT and
; authors neither, so claiming the default would take it from ePy
; Papers or ePy Reports for a type ePy Draft does not own.
#ifexist DistDir + "\epy_draft.exe"
Filename: "{app}\epy_draft.exe"; Parameters: "--register"; \
    Flags: runascurrentuser nowait postinstall skipifsilent; \
    Description: "Register ePy Draft under Open with"; \
    Components: craft
#endif

[UninstallRun]
Filename: "{app}\epy_studio.exe"; Parameters: "--unregister"; \
    RunOnceId: "UnregStudio"; Flags: runascurrentuser nowait
Filename: "{app}\epy_reports.exe"; Parameters: "--unregister"; \
    RunOnceId: "UnregReports"; Flags: runascurrentuser nowait; Components: reports
Filename: "{app}\epy_slides.exe"; Parameters: "--unregister"; \
    RunOnceId: "UnregSlides"; Flags: runascurrentuser nowait; Components: slides
Filename: "{app}\epy_papers.exe"; Parameters: "--unregister"; \
    RunOnceId: "UnregPapers"; Flags: runascurrentuser nowait; Components: papers
#ifexist DistDir + "\epy_draft.exe"
Filename: "{app}\epy_draft.exe"; Parameters: "--unregister"; \
    RunOnceId: "UnregCraft"; Flags: runascurrentuser nowait; Components: craft
#endif
