# Check-Replies.ps1 -- Daily safety-net for inbound replies to our cold outreach.
#
# Runs via Windows Task Scheduler (see Install-Tasks.ps1). For each run:
#   1. Auths to M365 Graph
#   2. Pulls last ~30 days of Sent Items -> builds a conversationId set of our outreach
#   3. Pulls Inbox messages received in the last N hours
#   4. Filters to external senders (not @technijian.com) whose conversationId matches our outreach
#   5. Skips auto-replies (OOO, vacation, bounce, unsubscribe-confirmation)
#   6. Checks "already handled" by looking for a Sent Items message from rjain in the same
#      conversation with sentDateTime > the inbound reply's receivedDateTime
#   7. De-dupes against tracking/replies/_seen.json
#   8. Appends new replies to tracking/replies/{YYYY-MM-DD}.md
#   9. Emails rjain a digest ONLY if there are new unhandled replies
#
# Everything stays read-only against the mailbox (no marking as read, no moving).
# Response drafting is separate -- see .claude/skills/draft-reply/SKILL.md.

param(
    [int]$LookbackHours = 36,
    [int]$SentHistoryDays = 30,
    [switch]$NoDigest,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\_Config.ps1"

if (-not (Connect-PipelineGraph)) { Write-PipelineLog "Graph connect failed; aborting." "ERROR"; exit 1 }

$repliesDir = Join-Path $script:TrackingDir "replies"
if (-not (Test-Path $repliesDir)) { New-Item -ItemType Directory -Path $repliesDir -Force | Out-Null }
$seenFile = Join-Path $repliesDir "_seen.json"
$seen = @{}
if (Test-Path $seenFile) {
    try { (Get-Content $seenFile -Raw | ConvertFrom-Json).PSObject.Properties | ForEach-Object { $seen[$_.Name] = $_.Value } } catch {}
}

# --- 1. Fetch our Sent Items window and build a lookup of our outreach threads ---
$sentFrom = [datetime]::UtcNow.AddDays(-$SentHistoryDays).ToString("yyyy-MM-ddTHH:mm:ssZ")
$sentUrl = "https://graph.microsoft.com/v1.0/users/$script:UserId/mailFolders/SentItems/messages" +
           "?`$filter=sentDateTime ge $sentFrom" +
           "&`$select=id,conversationId,subject,toRecipients,sentDateTime" +
           "&`$top=500"
$ourThreads = @{}  # conversationId -> @{ firstSubject, recipients, lastReplyFromUs }
try {
    $resp = Invoke-GraphGet $sentUrl
    foreach ($m in $resp.value) {
        $cid = $m.conversationId
        if (-not $cid) { continue }
        $tos = @()
        if ($m.toRecipients) { $tos = $m.toRecipients | ForEach-Object { $_.emailAddress.address } }
        if (-not $ourThreads.ContainsKey($cid)) {
            $ourThreads[$cid] = @{ subject = $m.subject; to = $tos; lastSent = [datetime]$m.sentDateTime }
        } elseif ([datetime]$m.sentDateTime -gt $ourThreads[$cid].lastSent) {
            $ourThreads[$cid].lastSent = [datetime]$m.sentDateTime
        }
    }
    Write-PipelineLog "Sent Items window: $($resp.value.Count) messages; $($ourThreads.Count) distinct conversations."
} catch {
    Write-PipelineLog "Sent Items fetch failed: $_" "ERROR"
    exit 2
}

# --- 2. Fetch recent Inbox messages ---
$inboxFrom = [datetime]::UtcNow.AddHours(-$LookbackHours).ToString("yyyy-MM-ddTHH:mm:ssZ")
$inboxUrl = "https://graph.microsoft.com/v1.0/users/$script:UserId/mailFolders/Inbox/messages" +
            "?`$filter=receivedDateTime ge $inboxFrom" +
            "&`$select=id,conversationId,subject,from,receivedDateTime,bodyPreview,isDraft" +
            "&`$top=200"
$inbox = @()
try {
    $resp = Invoke-GraphGet $inboxUrl
    $inbox = $resp.value
    Write-PipelineLog "Inbox window ($LookbackHours h): $($inbox.Count) messages."
} catch {
    Write-PipelineLog "Inbox fetch failed: $_" "ERROR"
    exit 3
}

# --- 3. Filter + classify ---
$autoReplyPatterns = @(
    'out of (the )?office', 'vacation', 'away from (my|the) desk', 'automatic reply',
    'automatically generated', 'delivery (status|has) failed', 'undeliverable',
    'message blocked', 'mail delivery', 'postmaster', 'mailer-daemon'
)
function Classify-Sentiment {
    param([string]$Text)
    $t = ($Text ?? "").ToLowerInvariant()
    if ($t -match 'unsubscribe|remove me|take me off|do not contact') { return "unsubscribe" }
    if ($t -match 'not interested|no thanks|not a fit|pass') { return "negative" }
    if ($t -match "let's talk|sounds good|interested|worth a call|schedule|set up a (call|meeting)|yes|sure|please do|send (it|over)") { return "positive" }
    if ($t -match 'who are you|how did you|where did you get') { return "curious" }
    return "neutral"
}

$new = @()
foreach ($msg in $inbox) {
    if ($msg.isDraft) { continue }
    $cid = $msg.conversationId
    if (-not $cid -or -not $ourThreads.ContainsKey($cid)) { continue }
    $fromAddr = $null
    if ($msg.from -and $msg.from.emailAddress) { $fromAddr = $msg.from.emailAddress.address }
    if (-not $fromAddr) { continue }
    if ($fromAddr -match '@technijian\.com$') { continue }  # our own sends

    # auto-reply filter
    $probe = ($msg.subject + " " + $msg.bodyPreview).ToLowerInvariant()
    $isAuto = $false
    foreach ($p in $autoReplyPatterns) { if ($probe -match $p) { $isAuto = $true; break } }

    # already-handled: did we send in this conversation AFTER this inbound received?
    $received = [datetime]$msg.receivedDateTime
    $handled = $ourThreads[$cid].lastSent -gt $received

    # dedup against seen
    if ($seen.ContainsKey($msg.id)) { continue }

    $new += [PSCustomObject]@{
        Id          = $msg.id
        Cid         = $cid
        Subject     = $msg.subject
        From        = $fromAddr
        Received    = $received
        BodyPreview = $msg.bodyPreview
        Sentiment   = (Classify-Sentiment $probe)
        AutoReply   = $isAuto
        Handled     = $handled
        OriginalTo  = ($ourThreads[$cid].to -join ", ")
    }
}

Write-PipelineLog "New replies to surface: $($new.Count) (handled=$(($new | Where-Object Handled).Count), auto=$(($new | Where-Object AutoReply).Count))"

# --- 4. Append to daily markdown log ---
$today = Get-Date -Format "yyyy-MM-dd"
$logPath = Join-Path $repliesDir "$today.md"
$pending = @($new | Where-Object { -not $_.Handled -and -not $_.AutoReply -and $_.Sentiment -ne "unsubscribe" })

if ($new.Count -gt 0 -and -not $DryRun) {
    $hdr = if (Test-Path $logPath) { "" } else { "# Replies -- $today`n`n" }
    $body = foreach ($r in $new) {
        $flag = if ($r.Handled) { "[OK] HANDLED" } elseif ($r.AutoReply) { "AUTO" } elseif ($r.Sentiment -eq "unsubscribe") { "!! UNSUBSCRIBE" } else { "-> PENDING" }
@"

## $flag -- $($r.From) -- $($r.Subject)

- **Received:** $($r.Received.ToString('yyyy-MM-dd HH:mm')) UTC
- **Sentiment:** $($r.Sentiment)
- **ConversationId:** ``$($r.Cid)``
- **Original sent to:** $($r.OriginalTo)
- **Snippet:**
  > $($r.BodyPreview -replace "`r?`n", " ")

"@
    }
    Add-Content -Path $logPath -Value ($hdr + ($body -join ""))
    foreach ($r in $new) { $seen[$r.Id] = $r.Received.ToString("o") }
    ($seen | ConvertTo-Json -Compress) | Set-Content -Path $seenFile -Encoding UTF8
    Write-PipelineLog "Appended $($new.Count) entries to $logPath"
}

# --- 5. Digest email (pending only) ---
if ($pending.Count -gt 0 -and -not $NoDigest -and -not $DryRun) {
    # Attempt to attach a matched service per reply by scanning draft JSONs.
    # The JSON for each outreach lead contains contact_email + matched_service.
    $draftIndex = @{}
    $draftsRoot = Join-Path $script:RepoRoot "templates\drafts"
    if (Test-Path $draftsRoot) {
        Get-ChildItem -Path $draftsRoot -Filter "*.json" -Recurse -ErrorAction SilentlyContinue | ForEach-Object {
            try {
                $d = Get-Content $_.FullName -Raw | ConvertFrom-Json
                if ($d.contact_email -and $d.matched_service) {
                    $draftIndex[$d.contact_email.ToLowerInvariant()] = $d.matched_service
                }
            } catch {}
        }
    }
    foreach ($r in $pending) {
        $svc = $null
        if ($r.From -and $draftIndex.ContainsKey($r.From.ToLowerInvariant())) { $svc = $draftIndex[$r.From.ToLowerInvariant()] }
        $r | Add-Member -NotePropertyName MatchedService -NotePropertyValue $svc -Force
        $r | Add-Member -NotePropertyName Department -NotePropertyValue (Get-Department -ServiceSlug $svc) -Force
    }

    # Per-department tallies (fixed order)
    $deptCounts = @{}
    foreach ($d in ($script:DepartmentOrder + @("Unknown"))) { $deptCounts[$d] = 0 }
    foreach ($r in $pending) { $deptCounts[$r.Department]++ }
    $deptLine = ($script:DepartmentOrder + @("Unknown") | ForEach-Object { "$_`: $($deptCounts[$_])" }) -join " | "

    $rows = foreach ($r in $pending) {
        $age = [math]::Round((([datetime]::UtcNow - $r.Received).TotalHours), 1)
        "<tr><td style='padding:8px;border-bottom:1px solid #EEE;'>$($r.From)</td><td style='padding:8px;border-bottom:1px solid #EEE;'>$($r.Subject)</td><td style='padding:8px;border-bottom:1px solid #EEE;'>$($r.Department)</td><td style='padding:8px;border-bottom:1px solid #EEE;'>$($r.Sentiment)</td><td style='padding:8px;border-bottom:1px solid #EEE;'>${age}h ago</td></tr>"
    }
    $inner = @"
<p><strong>$($pending.Count) reply$(if ($pending.Count -ne 1) { 'ies' } else { 'y' }) pending your response.</strong></p>
<p><strong>By department:</strong> $deptLine</p>
<p>Full log: <code>tracking/replies/$today.md</code><br>
To draft responses: open Claude Code in the repo and say <em>"draft replies for today"</em> -- the <code>draft-reply</code> skill will render drafts into <code>templates/replies/$today/</code>.</p>
<table style='border-collapse:collapse;width:100%;font-size:14px;'>
<tr style='background:#F0F4F8;'><th style='padding:8px;text-align:left;'>From</th><th style='padding:8px;text-align:left;'>Subject</th><th style='padding:8px;text-align:left;'>Dept</th><th style='padding:8px;text-align:left;'>Sentiment</th><th style='padding:8px;text-align:left;'>Age</th></tr>
$($rows -join "")
</table>
<p style='color:#888;font-size:12px;'>Automated safety-net from scripts/Check-Replies.ps1. You are receiving this because at least one reply was detected.</p>
"@
    $html = Build-BrandedEmail -BodyContent $inner
    $subj = "[tech-leads] $($pending.Count) pending repl$(if ($pending.Count -ne 1) { 'ies' } else { 'y' }) -- $today"
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
        Write-PipelineLog "Digest sent: $($pending.Count) pending."
    } catch {
        Write-PipelineLog "Digest send failed: $_" "ERROR"
    }
} elseif ($pending.Count -eq 0) {
    Write-PipelineLog "No pending replies -- no digest (per `only-when-pending` policy)."
}

Write-PipelineLog "Check-Replies run complete. new=$($new.Count) pending=$($pending.Count)"
