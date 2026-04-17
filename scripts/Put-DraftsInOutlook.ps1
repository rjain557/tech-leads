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
    [ValidateSet("1","2","3","all")][string]$Touch = "all",
    [switch]$DryRun,
    [switch]$ReplaceExisting  # delete any existing drafts tagged tech-leads before pushing
)

function Build-ContactTodoBlock {
    param($Meta)
    # Build a research block the user pastes into the To: field after looking up.
    # User deletes this block before sending. Written as plain text so Outlook keeps it intact.
    $company   = if ($Meta -and $Meta.company) { $Meta.company } else { "[company]" }
    $role      = if ($Meta -and $Meta.role) { $Meta.role } else { "[role]" }
    $buyer     = if ($Meta -and $Meta.likely_buyer) { $Meta.likely_buyer } else { "Decision-maker" }
    $posting   = if ($Meta -and $Meta.posting_url) { $Meta.posting_url } else { "" }
    # URL-encode for search links (minimal — spaces + quotes)
    $esc = { param($s) ($s -replace '"','%22' -replace ' ','%20') }
    $q1 = & $esc "`"$buyer`" `"$company`""
    $q2 = & $esc "`"$company`" $buyer email"
    $linkedIn = "https://www.linkedin.com/search/results/people/?keywords=$q1"
    $google = "https://www.google.com/search?q=$q2"

    $block = @"
[CONTACT TODO -- find their email, paste into To:, then delete this entire block before sending]
Company: $company
Role they posted: $role
Likely decision-maker: $buyer
Look them up:
  LinkedIn: $linkedIn
  Google:   $google
  Original posting: $posting
[END CONTACT TODO -- delete this block]


"@
    return $block
}

function Remove-ExistingTechLeadsDrafts {
    # Query Outlook for drafts categorized 'tech-leads' and delete them.
    # Only touches isDraft=true items; will not delete anything already sent.
    $url = "https://graph.microsoft.com/v1.0/users/$script:UserId/messages?`$filter=isDraft eq true&`$select=id,subject,categories&`$top=200"
    $resp = Invoke-GraphGet $url
    $matches = @($resp.value | Where-Object { $_.categories -and ($_.categories -contains 'tech-leads') })
    if ($matches.Count -eq 0) { Write-PipelineLog "  no existing tech-leads drafts to remove."; return 0 }
    Write-PipelineLog "  removing $($matches.Count) existing tech-leads drafts..."
    $removed = 0
    foreach ($m in $matches) {
        try {
            Invoke-RestMethod -Uri "https://graph.microsoft.com/v1.0/users/$script:UserId/messages/$($m.id)" -Headers (Get-GraphHeaders) -Method DELETE | Out-Null
            $removed++
        } catch { Write-PipelineLog "  delete fail $($m.id.Substring(0,16))...: $($_.Exception.Message)" "WARN" }
    }
    Write-PipelineLog "  removed $removed/$($matches.Count)."
    return $removed
}

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

if ($ReplaceExisting -and -not $DryRun) {
    Write-PipelineLog "ReplaceExisting: cleaning up prior tech-leads drafts..."
    Remove-ExistingTechLeadsDrafts | Out-Null
}

$touchesToPush = if ($Touch -eq "all") { @("1","2","3") } else { @($Touch) }
Write-PipelineLog "Pushing touches $($touchesToPush -join ',') for $($files.Count) drafts from $draftsDir to Outlook..."

$ok = 0; $fail = 0; $skipped = 0
foreach ($file in $files) {
    $content = Get-Content $file.FullName -Raw -Encoding UTF8

    # Load metadata for contact enrichment + research block
    $meta = $null
    $jsonPath = $file.FullName -replace '\.md$', '.json'
    if (Test-Path $jsonPath) {
        try { $meta = Get-Content $jsonPath -Raw -Encoding UTF8 | ConvertFrom-Json } catch {}
    }

    # Recipient: populate from JSON if available, else leave empty + add research block
    $toList = @()
    $needsResearch = $true
    if ($meta -and $meta.contact_email) {
        $toList = @(@{ emailAddress = @{ address = $meta.contact_email } })
        $needsResearch = $false
    }

    $researchBlock = if ($needsResearch) { Build-ContactTodoBlock -Meta $meta } else { "" }

    foreach ($t in $touchesToPush) {
        # Match: ## Touch {N} -- Day {D}\n**Subject:** {subj}\n\n{body}\n(signature)\n---
        $pattern = "(?ms)## Touch $t -- Day \d+\s*`r?`n\*\*Subject:\*\*\s*(?<subj>[^\r\n]+)`r?`n`r?`n(?<body>.+?)(?:`r?`n---|\Z)"
        $m = [regex]::Match($content, $pattern)
        if (-not $m.Success) {
            Write-PipelineLog "  [skip] Could not parse Touch $t from $($file.Name)" "WARN"
            $skipped++
            continue
        }
        $subject = $m.Groups['subj'].Value.Trim()
        $body    = $m.Groups['body'].Value.Trim()
        $finalBody = $researchBlock + $body

        $payload = @{
            subject      = $subject
            body         = @{ contentType = "Text"; content = $finalBody }
            toRecipients = $toList
            importance   = "normal"
            categories   = @("tech-leads", "outreach-touch-$t")
        } | ConvertTo-Json -Depth 6

        if ($DryRun) {
            $flag = if ($needsResearch) { "(NEEDS CONTACT)" } else { "to=$($toList[0].emailAddress.address)" }
            Write-Host "[DRY] $($file.BaseName) t$t : $subject $flag"
            $ok++
            continue
        }

        try {
            $url = "https://graph.microsoft.com/v1.0/users/$script:UserId/messages"
            $resp = Invoke-GraphPost -Url $url -Body $payload
            $flag = if ($needsResearch) { "(research block)" } else { "to=$($toList[0].emailAddress.address)" }
            Write-PipelineLog "  [ok] $($file.BaseName) t$t $flag -> draftId=$($resp.id.Substring(0,16))..."
            $ok++
        } catch {
            $errMsg = $_.Exception.Message
            if ($errMsg -match "403" -or $errMsg -match "Forbidden") {
                Write-PipelineLog "  [fail] $($file.BaseName) t$t : 403 -- app registration likely missing Mail.ReadWrite" "ERROR"
            } else {
                Write-PipelineLog "  [fail] $($file.BaseName) t$t : $errMsg" "ERROR"
            }
            $fail++
        }
    }
}

Write-PipelineLog "Done. ok=$ok fail=$fail skipped=$skipped"
if ($fail -gt 0) { exit 3 }
exit 0
