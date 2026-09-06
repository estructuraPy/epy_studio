# Build the installer, install it silently, register the file types, and
# prove the INSTALLED bundle is the one that was built and tested.
#
# Run from the repository root after build.py has produced dist\epy_studio:
#
#     pwsh -File windows\build_support\install_and_verify.ps1
#
# Every step checks the one before it and stops on the first failure, so
# a red probe at the end is never masked by a green message before it.
#
# Two rules this script exists to keep:
#   - The installer and the GUI executables are started with
#     Start-Process -Wait and their output is NOT redirected. A
#     GUI-subsystem exe with its stdout piped hangs its caller.
#   - A silent install registers nothing (every [Run] entry carries
#     skipifsilent), so --register is run explicitly and then VERIFIED
#     in the registry; "the installer ran" is not evidence of it.

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $root

$iss = Join-Path $root "windows\epy_studio.iss"
$iscc = Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"
$version = (Select-String -Path $iss -Pattern '#define AppVersion "([^"]+)"').Matches[0].Groups[1].Value
$setup = Join-Path $root "dist\epy_studio-setup-$version.exe"
$target = Join-Path $env:LOCALAPPDATA "Programs\epy_studio"
$python = "C:\Users\ingah\miniforge3\python.exe"

if (-not (Test-Path (Join-Path $root "dist\epy_studio\epy_studio.exe"))) {
    throw "dist\epy_studio is not built; run build.py first."
}
if (-not (Test-Path $iscc)) { throw "ISCC not found at $iscc" }

Write-Host "== 1/6 does the bundle carry what this release promised? =="
# Asked BEFORE the installer is compiled. An optional application whose
# sibling checkout was absent leaves one printed SKIP line in a build
# log nobody re-reads, and the short installer looks exactly like a
# complete one from the outside.
& $python (Join-Path $root "windows\build_support\verify_release.py")
if ($LASTEXITCODE -ne 0) { throw "the bundle is short of what release.epyson promises" }

Write-Host "== 2/6 installer ($version) =="
# ISCC is a console tool; capturing it is fine.
& $iscc /Qp $iss | Select-Object -Last 3
if ($LASTEXITCODE -ne 0) { throw "ISCC failed with exit $LASTEXITCODE" }
if (-not (Test-Path $setup)) { throw "installer not produced: $setup" }
Write-Host ("   {0}  {1:N1} MB" -f (Split-Path $setup -Leaf), ((Get-Item $setup).Length / 1MB))

Write-Host "== 3/6 silent install over the previous release =="
$p = Start-Process -FilePath $setup -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART" -Wait -PassThru
if ($p.ExitCode -ne 0) { throw "installer exited $($p.ExitCode)" }
$installed = (Get-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*" -ErrorAction SilentlyContinue |
    Where-Object { $_.DisplayName -like "*ePy Studio*" } | Select-Object -First 1).DisplayVersion
Write-Host "   registry DisplayVersion: $installed"
if ($installed -ne $version) { throw "installed $installed, expected $version" }

Write-Host "== 4/6 register the file types (silent installs skip this) =="
# ePy Draft is OPTIONAL, so this cannot assume it is there. Step 1
# already refused if this release promised it and the bundle is short,
# so reaching here without the executable means the release genuinely
# does not carry it -- and then there is nothing to register.
$draft = Join-Path $target "epy_draft.exe"
if (Test-Path $draft) {
    # GUI-subsystem exe: waited on, never piped.
    $r = Start-Process -FilePath $draft -ArgumentList "--register" -Wait -PassThru
    if ($r.ExitCode -ne 0) { throw "epy_draft.exe --register exited $($r.ExitCode)" }
} else {
    Write-Host "   ePy Draft is not in this release; nothing to register."
}

Write-Host "== 5/6 probe the INSTALLED executables and the registry =="
& $python (Join-Path $root "windows\build_support\probe_installed.py") --target $target
if ($LASTEXITCODE -ne 0) { throw "installed-bundle probe failed" }

Write-Host "== 6/6 the drawing reader in the installed exe =="
& $python (Join-Path $root "windows\build_support\probe_dxf_reader.py")
if ($LASTEXITCODE -ne 0) { throw "drawing-reader probe failed" }

Write-Host ""
Write-Host "INSTALLED AND VERIFIED: ePy Studio $version at $target"
