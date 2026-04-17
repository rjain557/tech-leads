# Put-ReplyInOutlook.ps1
# Companion to Put-DraftsInOutlook.ps1 for INBOUND replies. Parses draft
# responses rendered by the draft-reply skill (templates/replies/{date}/*.md)
# and creates Outlook Drafts in rjain's mailbox.
#
# Replies differ from outreach drafts in two ways:
#   1. Single touch per file (not 3)
#   2. They have a conversationId we want Outlook to thread into, so the
#      draft shows up in the original conversation rather than as a net-new
#      message. We set `createReplyDraft` via the Graph convention:
#      POST /users/{id}/messages/{inReplyToId}/createReply
#      Requires the original inbound message id from tracking/replies/{date}.md.
#
# Usage:
#   powershell -File scripts\Put-ReplyInOutlook.ps1
#   powershell -File scripts\Put-ReplyInOutlook.ps1 -ReplyDate 2026-04-18 -DryRun
#   powershell -File scripts\Put-ReplyInOutlook.ps1 -Slug acme-corp     # one only

param(
    [string]$ReplyDate = (Get-Date -Format "yyyy-MM-dd"),
    [string]$Slug,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\_Config.ps1"

if (-not (Connect-PipelineGraph)) { Write-PipelineLog "Graph connect failed; aborting." "ERROR"; exit 1 }

$repliesDir = Join-Path $script:RepoRoot "templates\replies\$ReplyDate"
if (-not (Test-Path $repliesDir)) {
    Write-PipelineLog "No reply drafts at $repliesDir (nothing to push)." "WARN"
    exit 0
}

$files = Get-ChildItem $repliesDir -Filter "*.md" -File | Where-Object { $_.Name -notmatch '^_' }
if ($Slug) { $files = $files | Where-Object { $_.BaseName -like "*$Slug*" } }
if ($files.Count -eq 0) { Write-PipelineLog "No matching reply drafts." "WARN"; exit 0 }

Write-PipelineLog "Pushing $($files.Count) reply drafts from $repliesDir to Outlook..."

$ok = 0; $fail = 0; $skipped = 0
foreach ($file in $files) {
    $content = Get-Content $file.FullName -Raw -Encoding UTF8

    # Parse subject + body from the draft-reply skill's output format:
    #   ## Draft response
    #   **Subject:** Re: ...
    #   {body}
    $pattern = "(?ms)## Draft response\s*`r?`n\*\*Subject:\*\*\s*(?<subj>[^\r\n]+)`r?`n`r?`n(?<body>.+?)(?:`r?`n`r?`n---|\Z)"
    $m = [regex]::Match($content, $pattern)
    if (-not $m.Success) {
        Write-PipelineLog "  [skip] Could not parse reply draft from $($file.Name)" "WARN"
        $skipped++
        continue
    }
    $subject = $m.Groups['subj'].Value.Trim()
    $body    = $m.Groups['body'].Value.Trim()

    # Pull conversationId + inbound messageId from the draft's metadata header
    # (the skill writes `- **ConversationId:** ...` and `- **InReplyTo:** {id}` lines)
    $cid = $null; $inReplyTo = $null
    if ($content -match '(?m)^-\s+\*\*ConversationId:\*\*\s+`?([^`\r\n]+?)`?\s*$') { $cid = $Matches[1].Trim() }
    if ($content -match '(?m)^-\s+\*\*InReplyTo:\*\*\s+`?([^`\r\n]+?)`?\s*$')      { $inReplyTo = $Matches[1].Trim() }

    if ($DryRun) {
        Write-Host "[DRY] $($file.BaseName): $subject ($(($body -split '\s+').Count) words) cid=$cid inReplyTo=$inReplyTo"
        $ok++
        continue
    }

    try {
        if ($inReplyTo) {
            # Use createReply so Outlook threads the draft into the original conversation.
            # POST .../messages/{id}/createReply  -> returns the new draft message.
            $createUrl = "https://graph.microsoft.com/v1.0/users/$script:UserId/messages/$inReplyTo/createReply"
            $draft = Invoke-GraphPost -Url $createUrl -Body "{}"

            # Patch the draft with our custom body + subject
            $patchUrl = "https://graph.microsoft.com/v1.0/users/$script:UserId/messages/$($draft.id)"
            $patch = @{
                subject    = $subject
                body       = @{ contentType = "Text"; content = $body }
                categories = @("tech-leads", "outreach-reply")
            } | ConvertTo-Json -Depth 6
            Invoke-RestMethod -Uri $patchUrl -Headers (Get-GraphHeaders) -Method PATCH -Body $patch | Out-Null
            Write-PipelineLog "  [ok] $($file.BaseName) (threaded) -> draftId=$($draft.id.Substring(0,16))..."
        } else {
            # No InReplyTo known -> create a standalone draft
            $url = "https://graph.microsoft.com/v1.0/users/$script:UserId/messages"
            $payload = @{
                subject      = $subject
                body         = @{ contentType = "Text"; content = $body }
                toRecipients = @()
                categories   = @("tech-leads", "outreach-reply-untethered")
            } | ConvertTo-Json -Depth 6
            $resp = Invoke-GraphPost -Url $url -Body $payload
            Write-PipelineLog "  [ok] $($file.BaseName) (standalone) -> draftId=$($resp.id.Substring(0,16))..."
        }
        $ok++
    } catch {
        Write-PipelineLog "  [fail] $($file.BaseName): $($_.Exception.Message)" "ERROR"
        $fail++
    }
}

Write-PipelineLog "Done. ok=$ok fail=$fail skipped=$skipped"
if ($fail -gt 0) { exit 3 }
exit 0
