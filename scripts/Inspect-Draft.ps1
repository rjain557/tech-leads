param([string]$SubjectLike = "Mercy House", [string]$Touch = "1")
. "$PSScriptRoot\_Config.ps1"
Connect-PipelineGraph | Out-Null
$url = "https://graph.microsoft.com/v1.0/users/$($script:UserId)/messages?`$filter=isDraft eq true&`$top=200&`$select=id,subject,body,toRecipients,categories&`$orderby=createdDateTime desc"
$r = Invoke-GraphGet -Url $url
$pick = $r.value | Where-Object {
    ($_.categories -contains 'tech-leads') -and
    ($_.categories -contains "outreach-touch-$Touch") -and
    ($_.subject -match $SubjectLike)
} | Select-Object -First 1
if (-not $pick) { Write-Host "no draft matched"; exit 1 }
Write-Host "Subject: $($pick.subject)"
Write-Host "To:      $($pick.toRecipients[0].emailAddress.address)"
Write-Host "Categories: $($pick.categories -join ', ')"
$out = Join-Path $script:LogDir "inspect-$($Touch)-$($SubjectLike -replace '\W','').html"
$pick.body.content | Out-File -FilePath $out -Encoding UTF8
Write-Host "HTML: $out ($($pick.body.content.Length) chars)"
