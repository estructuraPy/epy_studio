; Inno Setup script for ePy Studio — unified installer for the ePy
; document apps (epy_reports, epy_slides, epy_papers) + launcher.
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
#define AppVersion "0.4.1"
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

[Types]
Name: "full"; Description: "Full installation (all apps)"
Name: "custom"; Description: "Custom installation"; Flags: iscustom

[Components]
Name: "reports"; Description: "ePy Reports — technical reports (PDF / Word / HTML)"; Types: full custom
Name: "slides"; Description: "ePy Slides — presentation decks (reveal.js / PowerPoint)"; Types: full custom
Name: "papers"; Description: "ePy Papers — academic manuscripts"; Types: full custom

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

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\epy_studio.exe"; IconFilename: "{app}\epy_studio.exe"
Name: "{autoprograms}\ePy Reports"; Filename: "{app}\epy_reports.exe"; IconFilename: "{app}\epy_reports.exe"; Components: reports
Name: "{autoprograms}\ePy Slides"; Filename: "{app}\epy_slides.exe"; IconFilename: "{app}\epy_slides.exe"; Components: slides
Name: "{autoprograms}\ePy Papers"; Filename: "{app}\epy_papers.exe"; IconFilename: "{app}\epy_papers.exe"; Components: papers
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

[UninstallRun]
Filename: "{app}\epy_studio.exe"; Parameters: "--unregister"; \
    RunOnceId: "UnregStudio"; Flags: runascurrentuser nowait
Filename: "{app}\epy_reports.exe"; Parameters: "--unregister"; \
    RunOnceId: "UnregReports"; Flags: runascurrentuser nowait; Components: reports
Filename: "{app}\epy_slides.exe"; Parameters: "--unregister"; \
    RunOnceId: "UnregSlides"; Flags: runascurrentuser nowait; Components: slides
Filename: "{app}\epy_papers.exe"; Parameters: "--unregister"; \
    RunOnceId: "UnregPapers"; Flags: runascurrentuser nowait; Components: papers
