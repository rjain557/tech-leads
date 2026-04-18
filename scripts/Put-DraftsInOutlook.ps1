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
    [ValidateSet("1","2","3","all")][string]$Touch = "1",
    [switch]$DryRun,
    [switch]$ReplaceExisting  # delete any existing drafts tagged tech-leads before pushing
)
# Default is Touch 1 only. Multi-touch auto-cadence reads as automation to recipients
# (and feels spammy to send 3 emails to one person about one job posting).
# Touches 2 and 3 are still rendered locally in templates/drafts/{date}/ for cases
# where rjain decides a specific lead merits a follow-up — push them individually
# with -Touch 2 / -Touch 3 / -Touch all when warranted.

function Build-ContactTodoBlockHtml {
    param($Meta)
    # HTML version: a highlighted yellow callout block at the top of the body.
    # User deletes this block before sending. Clearly visual in Outlook.
    $company = if ($Meta -and $Meta.company) { [System.Web.HttpUtility]::HtmlEncode($Meta.company) } else { "[company]" }
    $role    = if ($Meta -and $Meta.role) { [System.Web.HttpUtility]::HtmlEncode($Meta.role) } else { "[role]" }
    $buyer   = if ($Meta -and $Meta.likely_buyer) { [System.Web.HttpUtility]::HtmlEncode($Meta.likely_buyer) } else { "Decision-maker" }
    $posting = if ($Meta -and $Meta.posting_url) { $Meta.posting_url } else { "" }
    $esc = { param($s) ($s -replace '"','%22' -replace ' ','%20') }
    $q1 = & $esc "`"$($Meta.likely_buyer)`" `"$($Meta.company)`""
    $q2 = & $esc "`"$($Meta.company)`" $($Meta.likely_buyer) email"
    $linkedIn = "https://www.linkedin.com/search/results/people/?keywords=$q1"
    $google = "https://www.google.com/search?q=$q2"

    return @"
<div style="background:#FFF8E1;border-left:4px solid #F67D4B;padding:14px 18px;margin:0 0 24px 0;font-family:'Segoe UI',Arial,sans-serif;font-size:13px;color:#5D4037;border-radius:4px">
<div style="font-weight:700;margin-bottom:8px;color:#BF360C">CONTACT TODO &mdash; find their email, paste into To:, then delete this entire block before sending</div>
<div><strong>Company:</strong> $company</div>
<div><strong>Role they posted:</strong> $role</div>
<div><strong>Likely decision-maker:</strong> $buyer</div>
<div style="margin-top:8px;"><strong>Look them up:</strong></div>
<div style="margin-left:12px">&bull; LinkedIn: <a href="$linkedIn" style="color:#006DB6">$linkedIn</a></div>
<div style="margin-left:12px">&bull; Google: <a href="$google" style="color:#006DB6">$google</a></div>
<div style="margin-left:12px">&bull; Original posting: <a href="$posting" style="color:#006DB6">$posting</a></div>
</div>
"@
}

function Convert-BodyToHtml {
    param([string]$PlainBody)
    # Turn a plain-text body with double-newline paragraphs into HTML paragraphs
    # wrapped in the Aptos 12pt style that matches rjain's composition default.
    # Drop the plain-text signature block if present (we append the real HTML one).
    $text = $PlainBody -replace "`r`n", "`n"
    $text = [regex]::Replace($text, "(?s)`n+-- Rajiv Jain.*$", "")
    $text = [regex]::Replace($text, "(?s)`n+--Ravi\s*$", "")
    $text = $text.Trim()
    # If the LLM returned one giant paragraph (no \n\n separators), heuristically
    # break it at sentence boundaries every ~2 sentences so spacing isn't one wall of text.
    if ($text -notmatch "`n`n") {
        $sentences = [regex]::Split($text, '(?<=[.!?])\s+(?=[A-Z"])') | Where-Object { $_.Trim() -ne "" }
        if ($sentences.Count -ge 4) {
            $grouped = for ($i = 0; $i -lt $sentences.Count; $i += 2) {
                $end = [Math]::Min($i + 1, $sentences.Count - 1)
                ($sentences[$i..$end]) -join " "
            }
            $text = ($grouped) -join "`n`n"
        }
    }
    $paragraphs = ($text -split "`n`n+") | Where-Object { $_.Trim() -ne "" } | ForEach-Object {
        $p = [System.Web.HttpUtility]::HtmlEncode($_.Trim()) -replace "`n", "<br>"
        "<p style=`"margin:0 0 16px 0;line-height:1.55`">$p</p>"
    }
    $bodyDiv = "<div style=`"font-family:Aptos,Calibri,'Helvetica Neue',Helvetica,Arial,sans-serif;font-size:12pt;color:rgb(0,0,0);line-height:1.55;margin-bottom:8px`">" + ($paragraphs -join "`n") + "</div>"
    # Add clear spacing before the signature so body + signature don't run together
    return $bodyDiv + "<div style=`"height:24px;line-height:24px`">&nbsp;</div>"
}

function Get-SignatureHtml {
    $p = Join-Path $script:RepoRoot "templates\signature.html"
    if (Test-Path $p) { return Get-Content $p -Raw -Encoding UTF8 }
    return ""
}

# Load System.Web for HtmlEncode
Add-Type -AssemblyName System.Web

function Remove-ExistingTechLeadsDrafts {
    # Query Outlook for drafts categorized 'tech-leads' and delete them.
    # Only touches isDraft=true items; will not delete anything already sent.
    $url = "https://graph.microsoft.com/v1.0/users/$script:UserId/messages?`$filter=isDraft eq true&`$select=id,subject,categories&`$top=200"
    $resp = Invoke-GraphGet $url
    $techLeadDrafts = @($resp.value | Where-Object { $_.categories -and ($_.categories -contains 'tech-leads') })
    if ($techLeadDrafts.Count -eq 0) { Write-PipelineLog "  no existing tech-leads drafts to remove."; return 0 }
    Write-PipelineLog "  removing $($techLeadDrafts.Count) existing tech-leads drafts..."
    $removed = 0
    foreach ($m in $techLeadDrafts) {
        try {
            Invoke-RestMethod -Uri "https://graph.microsoft.com/v1.0/users/$script:UserId/messages/$($m.id)" -Headers (Get-GraphHeaders) -Method DELETE | Out-Null
            $removed++
        } catch { Write-PipelineLog "  delete fail $($m.id.Substring(0,16))...: $($_.Exception.Message)" "WARN" }
    }
    Write-PipelineLog "  removed $removed/$($techLeadDrafts.Count)."
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

    $researchBlockHtml = if ($needsResearch) { Build-ContactTodoBlockHtml -Meta $meta } else { "" }
    $signatureHtml = Get-SignatureHtml

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
        $bodyHtml = Convert-BodyToHtml -PlainBody $body
        $finalBodyHtml = $researchBlockHtml + $bodyHtml + $signatureHtml

        $payload = @{
            subject      = $subject
            body         = @{ contentType = "HTML"; content = $finalBodyHtml }
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
