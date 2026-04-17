# Send-Email.ps1 - Dedup-safe email sender via Microsoft Graph (tech-leads edition).
# Mirrors D:\vscode\technijian-admin-job-postings\job-postings\Scripts\6-SendEmail.ps1.
#
# Usage:
#   . "$PSScriptRoot\_Config.ps1"
#   Connect-PipelineGraph | Out-Null
#   Send-LeadEmail -To "prospect@example.com" -Subject "..." -HtmlBody "<html>..." -DedupKey "lead-outreach-{company-slug}"

. "$PSScriptRoot\_Config.ps1"

function Send-LeadEmail {
    param(
        [Parameter(Mandatory)][string]$To,
        [Parameter(Mandatory)][string]$Subject,
        [Parameter(Mandatory)][string]$HtmlBody,
        [Parameter(Mandatory)][string]$DedupKey
    )

    if (-not $script:TenantId) {
        Write-PipelineLog "Email disabled - secrets.json missing. Would have sent: $Subject -> $To" "WARN"
        return @{ Success = $false; Reason = "secrets_missing" }
    }

    # Dedup: skip if same subject+recipient already in Sent Items within last 30 days.
    try {
        $filter = [uri]::EscapeDataString("sentDateTime ge $((Get-Date).AddDays(-30).ToString('yyyy-MM-ddTHH:mm:ssZ'))")
        $url = "https://graph.microsoft.com/v1.0/users/$script:UserId/mailFolders/SentItems/messages?`$filter=$filter&`$select=id,subject,toRecipients,sentDateTime&`$top=200"
        $resp = Invoke-GraphGet -Url $url
        $already = $resp.value | Where-Object {
            $_.subject -eq $Subject -and ($_.toRecipients | Where-Object { $_.emailAddress.address -eq $To })
        }
        if ($already) {
            Write-PipelineLog "DEDUP: '$Subject' already sent to $To - skipping." "WARN"
            return @{ Success = $true; Deduped = $true }
        }
    } catch {
        Write-PipelineLog "Dedup check failed (proceeding): $_" "WARN"
    }

    $message = @{
        Subject      = $Subject
        Body         = @{ ContentType = "HTML"; Content = $HtmlBody }
        ToRecipients = @(@{ EmailAddress = @{ Address = $To } })
    }
    $sendBody = @{ message = $message; saveToSentItems = $true } | ConvertTo-Json -Depth 8

    try {
        Invoke-GraphPost -Url "https://graph.microsoft.com/v1.0/users/$script:UserId/sendMail" -Body $sendBody
        Write-PipelineLog "Sent: $Subject -> $To (dedupKey: $DedupKey)"
        Start-Sleep -Milliseconds 500   # rate limit
        return @{ Success = $true; Deduped = $false }
    } catch {
        Write-PipelineLog "Send failed ($To): $_" "ERROR"
        return @{ Success = $false; Error = $_.ToString() }
    }
}

function Send-LeadEmailTemplated {
    param(
        [Parameter(Mandatory)][string]$To,
        [Parameter(Mandatory)][string]$Subject,
        [Parameter(Mandatory)][string]$TemplateName,
        [Parameter(Mandatory)][hashtable]$Replacements,
        [Parameter(Mandatory)][string]$DedupKey
    )
    $html = Get-EmailTemplate -TemplateName $TemplateName
    if (-not $html) { return @{ Success = $false; Error = "template_missing" } }
    foreach ($k in $Replacements.Keys) { $html = $html.Replace("{{$k}}", $Replacements[$k]) }
    return Send-LeadEmail -To $To -Subject $Subject -HtmlBody (Build-BrandedEmail -BodyContent $html) -DedupKey $DedupKey
}
