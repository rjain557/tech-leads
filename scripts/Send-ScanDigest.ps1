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

$inner = @"
<p><strong>Weekly scan summary — $total leads in the last $Days days.</strong></p>
<p>HOT (score ≥ 4.0): <strong>$hot</strong> · WARM (2.5–3.99): <strong>$warm</strong> · Local: $local · Remote: $remote</p>
$($deptSections -join "")
<p style='color:#888;font-size:12px;'>Department totals above. Full lead files in <code>leads/active/</code>. Drafts for HOT leads in <code>templates/drafts/$((Get-Date).ToString('yyyy-MM-dd'))/</code>. Reply to this message if you want me to adjust the scoring model or the department mapping.</p>
"@

$today = Get-Date -Format "yyyy-MM-dd"
$subj = "[tech-leads] Weekly scan — $total leads (Tech Support: $($byDept['Tech Support'].Count), Dev: $($byDept['Development'].Count), SEO: $($byDept['SEO'].Count)) — $today"
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
