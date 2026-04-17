# Run-Weekly.ps1 — Weekly Task Scheduler entrypoint.
#
# Flow:
#   1. git pull --rebase (pick up config/lessons updates from other sessions)
#   2. scan_jobs.py (writes leads/active/, tracking/known-companies.json, tracking/lead-log.md)
#   3. git commit scan results + git push
#   4. Send-ScanDigest.ps1
#
# Any step can fail without blocking the others. Task exit code reflects worst case.
#
# The pull is ff-only by default — if the local tree has uncommitted changes
# that'd conflict with remote, the pull aborts and we skip the pull but still
# run the scan + local commit. This avoids silent state divergence.

param(
    [switch]$SkipGit,
    [switch]$SkipScan,
    [switch]$SkipDigest
)

$ErrorActionPreference = "Continue"
$RepoRoot = Split-Path $PSScriptRoot -Parent
$exitCode = 0

function Write-Step { param([string]$Msg) Write-Host ""; Write-Host "=== $Msg ===" }

Push-Location $RepoRoot
try {
    # --- 1. git pull ---
    if (-not $SkipGit) {
        Write-Step "git pull (fold in other-session config updates)"
        & git fetch origin main 2>&1 | Write-Host
        & git pull --rebase origin main 2>&1 | Write-Host
        if ($LASTEXITCODE -ne 0) {
            Write-Host "git pull failed (exit $LASTEXITCODE). Continuing with local state." -ForegroundColor Yellow
        }
    }

    # --- 2. scan_jobs.py ---
    $venvPy = Join-Path $RepoRoot ".venv\Scripts\python.exe"
    $pyExe = if (Test-Path $venvPy) { $venvPy } else { "python" }

    if (-not $SkipScan) {
        Write-Step "scan_jobs.py (Stage 1 - keyword prefilter)"
        & $pyExe (Join-Path $RepoRoot "scripts\scan_jobs.py") --scope all
        if ($LASTEXITCODE -ne 0) { $exitCode = $LASTEXITCODE; Write-Host "scan_jobs.py exited $LASTEXITCODE" -ForegroundColor Yellow }

        Write-Step "qualify_leads.py (Stage 2 - LLM qualifier)"
        & $pyExe (Join-Path $RepoRoot "scripts\qualify_leads.py")
        if ($LASTEXITCODE -ne 0 -and $exitCode -eq 0) { $exitCode = $LASTEXITCODE; Write-Host "qualify_leads.py exited $LASTEXITCODE" -ForegroundColor Yellow }

        Write-Step "build_outreach.py (Stage 3 - draft rendering)"
        & $pyExe (Join-Path $RepoRoot "scripts\build_outreach.py")
        if ($LASTEXITCODE -ne 0 -and $exitCode -eq 0) { $exitCode = $LASTEXITCODE; Write-Host "build_outreach.py exited $LASTEXITCODE" -ForegroundColor Yellow }
    }

    # --- 3. Commit scan results and push ---
    if (-not $SkipGit -and -not $SkipScan) {
        Write-Step "Commit + push scan results"
        # Stage only the scan-owned paths — never sweep in config changes or stray files
        & git add leads/ tracking/known-companies.json tracking/lead-log.md 2>&1 | Write-Host

        $staged = (& git diff --cached --name-only) -join "`n"
        if ($staged) {
            # Build commit message with department breakdown if digest preview is possible
            $today = Get-Date -Format "yyyy-MM-dd"
            $msg = "Weekly scan $today"
            try {
                # Shell a quick count pulled from known-companies.json for the commit message
                . "$PSScriptRoot\_Config.ps1"
                $kc = Join-Path $RepoRoot "tracking\known-companies.json"
                if (Test-Path $kc) {
                    $data = Get-Content $kc -Raw | ConvertFrom-Json
                    $cutoff = [datetime]::UtcNow.AddDays(-1)  # this run's delta
                    $deptCount = @{ "Tech Support" = 0; "Development" = 0; "SEO" = 0; "Unknown" = 0 }
                    foreach ($cp in $data.companies.PSObject.Properties) {
                        foreach ($sp in $cp.Value.PSObject.Properties) {
                            try { if ([datetime]::Parse($sp.Value.last_seen_utc) -ge $cutoff) { $deptCount[(Get-Department -ServiceSlug $sp.Name)]++ } } catch {}
                        }
                    }
                    $msg = "Weekly scan $today — Tech Support: $($deptCount['Tech Support']), Dev: $($deptCount['Development']), SEO: $($deptCount['SEO'])"
                }
            } catch { Write-Host "Message build warn: $_" }

            & git -c user.email="rjain@technijian.com" -c user.name="Tech-Leads Pipeline" commit -m "$msg" 2>&1 | Write-Host
            if ($LASTEXITCODE -eq 0) {
                & git pull --rebase origin main 2>&1 | Write-Host  # fold in anything pushed mid-run
                & git push origin main 2>&1 | Write-Host
                if ($LASTEXITCODE -ne 0 -and $exitCode -eq 0) { $exitCode = $LASTEXITCODE; Write-Host "git push exited $LASTEXITCODE" -ForegroundColor Yellow }
            }
        } else {
            Write-Host "No scan result changes to commit."
        }
    }

    # --- 4. Send-ScanDigest.ps1 ---
    if (-not $SkipDigest) {
        Write-Step "Send-ScanDigest.ps1"
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $RepoRoot "scripts\Send-ScanDigest.ps1")
        if ($LASTEXITCODE -ne 0 -and $exitCode -eq 0) { $exitCode = $LASTEXITCODE; Write-Host "Send-ScanDigest exited $LASTEXITCODE" -ForegroundColor Yellow }
    }
} finally {
    Pop-Location
}

exit $exitCode
