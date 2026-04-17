# Run-Weekly.ps1 — Weekly Task Scheduler entrypoint.
# Runs scan_jobs.py first, then Send-ScanDigest.ps1. Either step can fail
# independently and the other still attempts; the task exit code reflects
# the worst case.

$ErrorActionPreference = "Continue"
$RepoRoot = Split-Path $PSScriptRoot -Parent
$exitCode = 0

Write-Host "=== scan_jobs.py ==="
& python (Join-Path $RepoRoot "scripts\scan_jobs.py") --scope all
if ($LASTEXITCODE -ne 0) { $exitCode = $LASTEXITCODE; Write-Host "scan_jobs.py exited $LASTEXITCODE" }

Write-Host ""
Write-Host "=== Send-ScanDigest.ps1 ==="
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $RepoRoot "scripts\Send-ScanDigest.ps1")
if ($LASTEXITCODE -ne 0 -and $exitCode -eq 0) { $exitCode = $LASTEXITCODE; Write-Host "Send-ScanDigest exited $LASTEXITCODE" }

exit $exitCode
