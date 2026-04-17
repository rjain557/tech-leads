# Send-ScanDigest.ps1 — Weekly scan summary emailed to rjain.
#
# Runs after scan_jobs.py in the weekly Task Scheduler chain. Reads
# tracking/known-companies.json, finds every (company × service) pair
# whose last_seen_utc falls within the lookback window, groups by
# department (Tech Support / Development / SEO), and sends an HTML
# digest.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\Send-ScanDigest.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\Send-ScanDigest.ps1 -Days 14 -DryRun

param(
    [int]$Days = 7,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\_Config.ps1"

if (-not (Connect-PipelineGraph)) { Write-PipelineLog "Graph connect failed; aborting." "ERROR"; exit 1 }

$kc = Join-Path $script:TrackingDir "known-companies.json"
if (-not (Test-Path $kc)) { Write-PipelineLog "known-companies.json not found." "ERROR"; exit 2 }

$data = Get-Content $kc -Raw | ConvertFrom-Json
$cutoff = [datetime]::UtcNow.AddDays(-$Days)

# Flatten (company, service, score, title, url, seen) for anything in the window
$rows = @()
foreach ($companyProp in $data.companies.PSObject.Properties) {
    $slug = $companyProp.Name
    $services = $companyProp.Value
    foreach ($svcProp in $services.PSObject.Properties) {
        $svc = $svcProp.Name
        $r = $svcProp.Value
        $seen = $null
        try { $seen = [datetime]::Parse($r.last_seen_utc).ToUniversalTime() } catch { continue }
        if ($seen -lt $cutoff) { continue }
        $rows += [PSCustomObject]@{
            Company    = $slug
            Service    = $svc
            Department = (Get-Department -ServiceSlug $svc)
            Score      = [double]$r.last_score
            Title      = $r.last_title
            Url        = $r.last_url
            Scope      = $r.last_scope
            Seen       = $seen
        }
    }
}

if ($rows.Count -eq 0) {
    Write-PipelineLog "No leads in last $Days days. No digest sent."
    exit 0
}

# Group by department (fixed order), then sort within by score desc
$byDept = @{}
foreach ($dept in $script:DepartmentOrder + @("Unknown")) { $byDept[$dept] = @() }
foreach ($row in $rows) { $byDept[$row.Department] += $row }

# Totals
$total    = $rows.Count
$hot      = ($rows | Where-Object { $_.Score -ge 4.0 }).Count
$warm     = ($rows | Where-Object { $_.Score -ge 2.5 -and $_.Score -lt 4.0 }).Count
$local    = ($rows | Where-Object { $_.Scope -eq "local" }).Count
$remote   = ($rows | Where-Object { $_.Scope -eq "remote" }).Count

# Per-department breakdown
$deptSections = foreach ($dept in ($script:DepartmentOrder + @("Unknown"))) {
    $list = $byDept[$dept]
    if ($list.Count -eq 0) { continue }
    $top = $list | Sort-Object -Property Score -Descending | Select-Object -First 5
    $deptHot = ($list | Where-Object { $_.Score -ge 4.0 }).Count
    $rowsHtml = foreach ($r in $top) {
        $anchor = if ($r.Url) { "<a href='$($r.Url)' style='color:#006DB6;text-decoration:none;'>$($r.Company)</a>" } else { $r.Company }
        "<tr><td style='padding:6px 10px;border-bottom:1px solid #EEE;'>$anchor</td><td style='padding:6px 10px;border-bottom:1px solid #EEE;'>$($r.Service)</td><td style='padding:6px 10px;border-bottom:1px solid #EEE;text-align:right;'>$($r.Score)</td><td style='padding:6px 10px;border-bottom:1px solid #EEE;color:#888;font-size:13px;'>$($r.Title)</td></tr>"
    }
@"
<h3 style='margin:24px 0 8px 0;color:#006DB6;'>$dept — $($list.Count) lead$(if ($list.Count -ne 1) { 's' } else { '' }) ($deptHot HOT)</h3>
<table style='border-collapse:collapse;width:100%;font-size:14px;margin-bottom:16px;'>
<tr style='background:#F0F4F8;'><th style='padding:8px 10px;text-align:left;'>Company</th><th style='padding:8px 10px;text-align:left;'>Service</th><th style='padding:8px 10px;text-align:right;'>Score</th><th style='padding:8px 10px;text-align:left;'>Role</th></tr>
$($rowsHtml -join "")
</table>
"@
}

# --- Stage 2/3 counts: post-qualifier state ---
$activeDir = Join-Path $script:RepoRoot "leads\active"
$rejectedDir = Join-Path $script:RepoRoot "leads\archived\rejected"
$qualifiedFiles = if (Test-Path $activeDir) { @(Get-ChildItem $activeDir -Filter "*.md" -File) } else { @() }
$rejectedFiles  = if (Test-Path $rejectedDir) { @(Get-ChildItem $rejectedDir -Filter "*.md" -File) } else { @() }
$qualifiedCount = $qualifiedFiles.Count
$rejectedCount = $rejectedFiles.Count
$qualifiedNames = $qualifiedFiles | Sort-Object -Property LastWriteTime -Descending | Select-Object -First 10 | ForEach-Object {
    $n = $_.BaseName
    if ($n -match '^\d+-(.+)$') { $Matches[1] } else { $n }
}

# --- Drafts ready to review ---
$today = Get-Date -Format "yyyy-MM-dd"
$draftsDir = Join-Path $script:RepoRoot "templates\drafts\$today"
$draftsReady = if (Test-Path $draftsDir) { @(Get-ChildItem $draftsDir -Filter "*.md" -File).Count } else { 0 }

$qualPct = if ($total -gt 0) { [math]::Round(100.0 * $qualifiedCount / $total, 1) } else { 0 }

$inner = @"
<p><strong>Weekly scan summary — $qualifiedCount qualified of $total prefiltered (${qualPct}%).</strong></p>
<p>Stage 1 (prefilter): $total · Stage 2 (qualifier): <strong>$qualifiedCount qualified</strong>, $rejectedCount rejected · Stage 3 (drafts): $draftsReady rendered · Stage 4: <strong>Touch 1 drafts are in your Outlook Drafts folder — proofread and send from there</strong></p>
<p>Prefilter breakdown — HOT (≥ 4.0): $hot · WARM (2.5–3.99): $warm · Local: $local · Remote: $remote</p>
<h3 style='margin:20px 0 6px 0;color:#006DB6;'>Qualified leads (top $([Math]::Min(10, $qualifiedCount)))</h3>
<ul style='font-size:14px;'>
$(($qualifiedNames | ForEach-Object { "<li>$_</li>" }) -join "`n")
</ul>
$($deptSections -join "")
<p style='color:#888;font-size:12px;'>Department table above shows the prefilter pool. Qualified-vs-rejected is the binary gate by the Sonnet 4.6 qualifier. Touch 1 is waiting in Outlook Drafts; touches 2 and 3 are rendered locally in <code>templates/drafts/$today/</code> and can be pushed to Outlook with <code>scripts\Put-DraftsInOutlook.ps1 -Touch 2</code> / <code>-Touch 3</code> when you're ready to queue follow-ups.</p>
"@

$subj = "[tech-leads] Weekly scan — $qualifiedCount qualified / $total prefiltered (Tech Support: $($byDept['Tech Support'].Count), Dev: $($byDept['Development'].Count), SEO: $($byDept['SEO'].Count)) — $today"
$html = Build-BrandedEmail -BodyContent $inner

if ($DryRun) {
    $out = Join-Path $script:LogDir "scan-digest-preview-$today.html"
    Set-Content -Path $out -Value $html -Encoding UTF8
    Write-PipelineLog "DryRun: preview written to $out"
    exit 0
}

$payload = @{
    message = @{
        subject = $subj
        body = @{ contentType = "HTML"; content = $html }
        toRecipients = @(@{ emailAddress = @{ address = $script:UserId } })
    }
    saveToSentItems = $false
} | ConvertTo-Json -Depth 6

try {
    Invoke-GraphPost -Url "https://graph.microsoft.com/v1.0/users/$script:UserId/sendMail" -Body $payload
    Write-PipelineLog "Scan digest sent: $total total (Tech Support: $($byDept['Tech Support'].Count), Dev: $($byDept['Development'].Count), SEO: $($byDept['SEO'].Count))."
} catch {
    Write-PipelineLog "Scan digest send failed: $_" "ERROR"
    exit 3
}
