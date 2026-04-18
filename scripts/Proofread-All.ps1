# Pull every tech-leads Touch 1 draft from Outlook, strip HTML, and
# print a proofreading summary for each.
. "$PSScriptRoot\_Config.ps1"
Connect-PipelineGraph | Out-Null

# Grab more drafts and match both category AND subject heuristic (some drafts
# lose category metadata — the filter backs off to subject keywords)
$url = "https://graph.microsoft.com/v1.0/users/$($script:UserId)/messages?`$filter=isDraft eq true&`$top=500&`$select=id,subject,body,toRecipients,categories,createdDateTime&`$orderby=createdDateTime desc"
$r = Invoke-GraphGet -Url $url
$cutoff = [datetime]::UtcNow.AddHours(-2)
$drafts = $r.value | Where-Object {
    $_.createdDateTime -and ([datetime]$_.createdDateTime) -gt $cutoff -and
    $_.toRecipients -and
    ($_.toRecipients[0].emailAddress.address -match '@(mercyhouse|ampam|developlus|westernhealth|earthcam|corient|vialytics|desotec|bvital)\.')
} | Sort-Object { $_.toRecipients[0].emailAddress.address }

$banned = @(
    'fractional-MSP', 'coverage gaps', '24/7 layer', 'MSP layer',
    'Not arguing against', 'whoever you bring on', 'Before committing',
    'I hope this finds', 'Quick question', 'Touching base', 'Circling back'
)

$idx = 0
foreach ($d in $drafts) {
    $idx++
    $html = $d.body.content
    $htmlBody = $html -replace '(?is)<table[^>]*max-width:600px.*$', ''
    $htmlBody = $htmlBody -replace '(?is)<div[^>]*height:24px.*$', ''
    $paras = [regex]::Matches($htmlBody, '(?is)<p[^>]*>(.+?)</p>') | ForEach-Object {
        $t = $_.Groups[1].Value -replace '<br[^>]*>', ' ' -replace '<[^>]+>', '' -replace '&nbsp;', ' ' -replace '&quot;', '"' -replace '&#39;', "'" -replace '&amp;', '&'
        ($t -replace '\s+', ' ').Trim()
    } | Where-Object { $_ -ne "" }
    $paraCount = @($paras).Count
    $wordCount = ($paras -join ' ').Split(@(' ', "`t"), [System.StringSplitOptions]::RemoveEmptyEntries).Count
    $to = if ($d.toRecipients) { $d.toRecipients[0].emailAddress.address } else { '(empty)' }

    # Flag if first paragraph is JUST a name (1-2 words) then next para starts the body
    $greetingOnOwnLine = $paraCount -ge 2 -and $paras[0].Split(' ').Count -le 2
    $body = ($paras -join ' ')
    $mentionsBooking = $body -match '(?i)calendar link|book.*meeting|grab.*time|signature|link below'
    $bannedHits = @()
    foreach ($bp in $banned) { if ($body -match [regex]::Escape($bp)) { $bannedHits += $bp } }

    Write-Host ""
    Write-Host ("[$idx] $($d.subject)")
    Write-Host ("    To:               $to")
    Write-Host ("    Paras / Words:    $paraCount / $wordCount")
    Write-Host ("    Greeting own para (BAD): " + $(if ($greetingOnOwnLine) { 'YES — needs inlining with sentence 1' } else { 'no' }))
    Write-Host ("    Booking mention:  " + $(if ($mentionsBooking) { 'YES' } else { 'NO' }))
    Write-Host ("    Banned hits:      " + $(if ($bannedHits.Count -eq 0) { 'none' } else { $bannedHits -join ', ' }))
    Write-Host ("    P1: " + $paras[0].Substring(0, [Math]::Min(80, $paras[0].Length)))
    if ($paraCount -ge 2) { Write-Host ("    P2: " + $paras[1].Substring(0, [Math]::Min(80, $paras[1].Length))) }
}
Write-Host ""
Write-Host "Total drafts: $($drafts.Count)"
