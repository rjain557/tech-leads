# Put-DraftsInOutlook.ps1
# Create Outlook draft messages in rjain@technijian.com's Drafts folder, one per
# rendered outreach draft in templates/drafts/{date}/. Pushes Touch 1 only by
# default; pass -Touch 2 or -Touch 3 when follow-up day rolls around.
#
# Drafts land with empty toRecipients -- rjain fills in the contact email at
# send time. Body is plain text (no HTML, no links) matching the policy in
# templates/emails/_base.md.
#
# Requires Mail.ReadWrite application permission on the M365 Graph app reg.
# If the app only has Mail.Send + Mail.Read, creating drafts via POST
# /users/{id}/messages will return 403 -- handled with a clear error below.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\Put-DraftsInOutlook.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\Put-DraftsInOutlook.ps1 -Touch 2
#   powershell -ExecutionPolicy Bypass -File scripts\Put-DraftsInOutlook.ps1 -DryRun

param(
    [string]$DraftsDate = (Get-Date -Format "yyyy-MM-dd"),
    [ValidateSet("1","2","3")][string]$Touch = "1",
    [switch]$DryRun,
    [switch]$IncludeRecipient  # if the lead file has an email address, set To:
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\_Config.ps1"

if (-not (Connect-PipelineGraph)) { Write-PipelineLog "Graph connect failed; aborting." "ERROR"; exit 1 }

$draftsDir = Join-Path $script:RepoRoot "templates\drafts\$DraftsDate"
if (-not (Test-Path $draftsDir)) {
    Write-PipelineLog "No drafts directory at $draftsDir. Run build_outreach.py first." "ERROR"
    exit 2
}

$files = Get-ChildItem $draftsDir -Filter "*.md" -File | Where-Object { $_.Name -notmatch '^_' }
if ($files.Count -eq 0) {
    Write-PipelineLog "No draft .md files in $draftsDir." "WARN"
    exit 0
}

Write-PipelineLog "Pushing Touch $Touch for $($files.Count) drafts from $draftsDir to Outlook..."

$ok = 0; $fail = 0; $skipped = 0
foreach ($file in $files) {
    $content = Get-Content $file.FullName -Raw -Encoding UTF8

    # Match: ## Touch {N} -- Day {D}\n**Subject:** {subj}\n\n{body}\n(signature)\n---
    $pattern = "(?ms)## Touch $Touch -- Day \d+\s*`r?`n\*\*Subject:\*\*\s*(?<subj>[^\r\n]+)`r?`n`r?`n(?<body>.+?)(?:`r?`n---|\Z)"
    $m = [regex]::Match($content, $pattern)
    if (-not $m.Success) {
        Write-PipelineLog "  [skip] Could not parse Touch $Touch from $($file.Name)" "WARN"
        $skipped++
        continue
    }
    $subject = $m.Groups['subj'].Value.Trim()
    $body    = $m.Groups['body'].Value.Trim()

    # Optional recipient from {slug}.json (contact_email, if enriched)
    $toList = @()
    if ($IncludeRecipient) {
        $jsonPath = $file.FullName -replace '\.md$', '.json'
        if (Test-Path $jsonPath) {
            try {
                $meta = Get-Content $jsonPath -Raw -Encoding UTF8 | ConvertFrom-Json
                if ($meta.contact_email) {
                    $toList = @(@{ emailAddress = @{ address = $meta.contact_email } })
                }
            } catch {}
        }
    }

    $payload = @{
        subject      = $subject
        body         = @{ contentType = "Text"; content = $body }
        toRecipients = $toList
        importance   = "normal"
        categories   = @("tech-leads", "outreach-touch-$Touch")
    } | ConvertTo-Json -Depth 6

    if ($DryRun) {
        Write-Host "[DRY] $($file.BaseName): $subject ($(($body -split '\s+').Count) words)"
        $ok++
        continue
    }

    try {
        $url = "https://graph.microsoft.com/v1.0/users/$script:UserId/messages"
        $resp = Invoke-GraphPost -Url $url -Body $payload
        Write-PipelineLog "  [ok] $($file.BaseName) -> draftId=$($resp.id.Substring(0,16))..."
        $ok++
    } catch {
        $errMsg = $_.Exception.Message
        if ($errMsg -match "403" -or $errMsg -match "Forbidden") {
            Write-PipelineLog "  [fail] $($file.BaseName): 403 -- app registration likely missing Mail.ReadWrite" "ERROR"
        } else {
            Write-PipelineLog "  [fail] $($file.BaseName): $errMsg" "ERROR"
        }
        $fail++
    }
}

Write-PipelineLog "Done. ok=$ok fail=$fail skipped=$skipped"
if ($fail -gt 0) { exit 3 }
exit 0
