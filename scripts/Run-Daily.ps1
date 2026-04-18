# Run-Daily.ps1 -- Daily Task Scheduler entrypoint.
#
# Flow:
#   1. git pull --rebase (pick up config updates from other sessions -- affects
#      dept mapping and services.yml used by draft-reply skill)
#   2. Check-Replies.ps1 (writes tracking/replies/{date}.md -- gitignored, no commit)
#
# Pull failure does not block the reply check -- we'd rather run with slightly
# stale config than miss a reply.

param(
    [switch]$SkipGit
)

$ErrorActionPreference = "Continue"
$RepoRoot = Split-Path $PSScriptRoot -Parent
$exitCode = 0

Push-Location $RepoRoot
try {
    if (-not $SkipGit) {
        Write-Host "=== git pull ==="
        & git fetch origin main 2>&1 | Write-Host
        & git pull --rebase origin main 2>&1 | Write-Host
        if ($LASTEXITCODE -ne 0) {
            Write-Host "git pull failed (exit $LASTEXITCODE). Continuing with local state." -ForegroundColor Yellow
        }
    }

    Write-Host ""
    Write-Host "=== Check-Replies.ps1 ==="
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $RepoRoot "scripts\Check-Replies.ps1")
    if ($LASTEXITCODE -ne 0) { $exitCode = $LASTEXITCODE }
} finally {
    Pop-Location
}

exit $exitCode
