# setup_python.ps1 - One-shot fix for "python not found" in this repo.
#
# What it does:
#   1. Searches every plausible install location for a REAL python.exe
#      (skips the WindowsApps shim that keeps intercepting `python`).
#   2. If no real Python is found, installs one via winget (Python.Python.3.12).
#   3. Creates .venv\ in the repo root using that Python.
#   4. Installs pyyaml into the venv.
#   5. Runs a tiny sanity check (import yaml).
#   6. Prints the exact command to run the scanner - no PATH changes needed,
#      we just invoke the venv's python.exe directly.
#
# Usage (from any shell, in the repo root or scripts/ dir):
#   powershell -ExecutionPolicy Bypass -File .\scripts\setup_python.ps1
#
# Safe to re-run - idempotent.

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path $PSScriptRoot -Parent
$VenvDir  = Join-Path $RepoRoot ".venv"
$VenvPy   = Join-Path $VenvDir "Scripts\python.exe"

function Write-Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "    OK: $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "    WARN: $msg" -ForegroundColor Yellow }
function Write-Err($msg)  { Write-Host "    ERROR: $msg" -ForegroundColor Red }

function Test-RealPython([string]$exe) {
    # The WindowsApps shim exits non-zero with a message and no --version output.
    # A real python prints "Python 3.x.y" and exits 0.
    if (-not (Test-Path $exe)) { return $false }
    try {
        $out = & $exe --version 2>&1
        if ($LASTEXITCODE -ne 0) { return $false }
        if ($out -match "^Python\s+3\.") { return $true }
    } catch {}
    return $false
}

function Find-RealPython {
    $candidates = New-Object System.Collections.Generic.List[string]

    # Standard install locations
    foreach ($v in @("313","312","311","310","39")) {
        $candidates.Add("C:\Python$v\python.exe")
        $candidates.Add("C:\Program Files\Python$v\python.exe")
        $candidates.Add("C:\Program Files (x86)\Python$v\python.exe")
        $candidates.Add("$env:LOCALAPPDATA\Programs\Python\Python$v\python.exe")
    }

    # MS Store actual install (not the shim)
    Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WindowsApps\PythonSoftwareFoundation.*" -ErrorAction SilentlyContinue |
        ForEach-Object { $candidates.Add((Join-Path $_.FullName "python.exe")) }

    # py launcher - resolves to whatever Python is registered
    foreach ($pyLauncher in @("C:\Windows\py.exe","C:\Program Files\Python Launcher\py.exe")) {
        if (Test-Path $pyLauncher) {
            try {
                $resolved = & $pyLauncher -c "import sys; print(sys.executable)" 2>$null
                if ($LASTEXITCODE -eq 0 -and $resolved) { $candidates.Add($resolved.Trim()) }
            } catch {}
        }
    }

    # Conda / Anaconda / Scoop / Chocolatey
    foreach ($p in @(
        "$env:USERPROFILE\anaconda3\python.exe",
        "$env:USERPROFILE\miniconda3\python.exe",
        "C:\ProgramData\Anaconda3\python.exe",
        "$env:USERPROFILE\scoop\apps\python\current\python.exe",
        "C:\tools\python312\python.exe",
        "C:\tools\python311\python.exe",
        "C:\ProgramData\chocolatey\bin\python.exe"
    )) { $candidates.Add($p) }

    # Broad fallback scan - look for any python.exe under Program Files and the user profile
    foreach ($root in @(
        "$env:ProgramFiles",
        "${env:ProgramFiles(x86)}",
        "$env:LOCALAPPDATA\Programs",
        "$env:USERPROFILE\AppData\Local"
    )) {
        if (Test-Path $root) {
            Get-ChildItem -Path $root -Filter python.exe -Recurse -ErrorAction SilentlyContinue -Depth 4 |
                ForEach-Object { $candidates.Add($_.FullName) }
        }
    }

    foreach ($c in ($candidates | Select-Object -Unique)) {
        if (Test-RealPython $c) { return $c }
    }
    return $null
}

function Install-PythonFromPythonOrg {
    # Fallback when winget fails - downloads the official python.org installer
    # via Invoke-WebRequest (uses WinINET by default, often works when winget
    # cannot reach its endpoints).
    $version = "3.12.7"
    $url     = "https://www.python.org/ftp/python/$version/python-$version-amd64.exe"
    $dest    = Join-Path $env:TEMP "python-$version-amd64.exe"

    Write-Step "Downloading Python installer from python.org..."
    Write-Host "    $url"
    try {
        # Use the .NET WebClient for a simple GET; works with system proxy if configured
        $ProgressPreference = "SilentlyContinue"
        Invoke-WebRequest -Uri $url -OutFile $dest -UseBasicParsing -TimeoutSec 180
    } catch {
        Write-Err "Download from python.org failed: $_"
        Write-Err "Your network is blocking both winget AND direct HTTPS to python.org."
        Write-Err "Manual fix: download $url on a machine that has internet, copy the .exe here,"
        Write-Err "and run: $dest /quiet InstallAllUsers=0 PrependPath=1 Include_test=0"
        return $false
    }
    Write-Ok "Downloaded to $dest"

    Write-Step "Running silent install (user scope, adds python to PATH)..."
    $installArgs = @("/quiet","InstallAllUsers=0","PrependPath=1","Include_test=0","SimpleInstall=1")
    $p = Start-Process -FilePath $dest -ArgumentList $installArgs -Wait -PassThru
    if ($p.ExitCode -ne 0) {
        Write-Err "python.org installer exited $($p.ExitCode). Try running it manually: $dest"
        return $false
    }
    Write-Ok "Python $version installed."
    return $true
}

function Install-PythonViaWinget {
    Write-Step "No Python found - trying winget first..."
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) {
        throw "winget is not available on this machine."
    }
    $wingetArgs = @(
        "install","--id","Python.Python.3.12",
        "-e","--source","winget","--scope","user",
        "--accept-package-agreements","--accept-source-agreements",
        "--silent"
    )
    & winget @wingetArgs
    if ($LASTEXITCODE -ne 0) {
        throw "winget install failed (exit $LASTEXITCODE)."
    }
    Write-Ok "winget install finished."
}

# -- Main --------------------------------------------------------------

Write-Step "Looking for a real Python install (ignoring the WindowsApps shim)..."
$py = Find-RealPython
if (-not $py) {
    # Try winget first (fast if it works)
    $wingetOk = $false
    try {
        Install-PythonViaWinget
        $wingetOk = $true
    } catch {
        Write-Warn "winget path failed: $_"
    }

    # If winget failed, fall back to direct python.org download
    if (-not $wingetOk) {
        Write-Warn "winget unavailable - falling back to direct python.org download..."
        $ok = Install-PythonFromPythonOrg
        if (-not $ok) { exit 1 }
    }

    Start-Sleep -Seconds 3
    $py = Find-RealPython
    if (-not $py) {
        Write-Err "Still cannot find python.exe after install. Open a NEW terminal and re-run this script."
        exit 1
    }
}
Write-Ok "Found Python: $py"
& $py --version

Write-Step "Creating venv at $VenvDir ..."
if (-not (Test-Path $VenvPy)) {
    & $py -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) { Write-Err "venv creation failed."; exit 1 }
    Write-Ok "venv created."
} else {
    Write-Ok "venv already exists - reusing."
}

Write-Step "Upgrading pip + installing pyyaml into venv ..."
& $VenvPy -m pip install --upgrade pip --quiet
& $VenvPy -m pip install pyyaml --quiet
if ($LASTEXITCODE -ne 0) { Write-Err "pip install failed."; exit 1 }
Write-Ok "pyyaml installed."

Write-Step "Sanity check: import yaml + read config/services.yml ..."
$checkPy = Join-Path $env:TEMP "tech-leads-pycheck.py"
@'
import yaml, pathlib, sys
p = pathlib.Path(sys.argv[1]) / "config" / "services.yml"
d = yaml.safe_load(p.read_text(encoding="utf-8"))
print("services:", len(d["services"]))
'@ | Set-Content -Path $checkPy -Encoding UTF8
$check = & $VenvPy $checkPy $RepoRoot 2>&1
Remove-Item $checkPy -ErrorAction SilentlyContinue
Write-Host "    $check"
if ($LASTEXITCODE -ne 0) { Write-Err "yaml / config check failed."; exit 1 }

$cmdScan = '& "' + $VenvPy + '" scripts\scan_jobs.py --scope local --max-queries 2'
$cmdDry  = '& "' + $VenvPy + '" scripts\scan_jobs.py --scope all --dry-run'

Write-Host ""
Write-Host "====================================================================" -ForegroundColor Green
Write-Host " Python is ready. Use the venv interpreter directly - no PATH juggling." -ForegroundColor Green
Write-Host "====================================================================" -ForegroundColor Green
Write-Host ""
Write-Host " Interpreter: $VenvPy"
Write-Host ""
Write-Host " Run a tiny real scan (2 queries, local only):"
Write-Host "   $cmdScan" -ForegroundColor Yellow
Write-Host ""
Write-Host " Dry run (no API credits burned):"
Write-Host "   $cmdDry" -ForegroundColor Yellow
Write-Host ""
