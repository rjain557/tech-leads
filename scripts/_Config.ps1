# _Config.ps1 - Shared config for tech-leads pipeline.
# Mirrors the pattern from D:\vscode\technijian-admin-job-postings\job-postings\Scripts\_Config.ps1
# so we reuse the same M365 Graph app registration.
#
# Dot-source this file: . "$PSScriptRoot\_Config.ps1"

# --- Paths ---
$script:RepoRoot     = Split-Path $PSScriptRoot -Parent
$script:ConfigDir    = Join-Path $RepoRoot "config"
$script:LeadsDir     = Join-Path $RepoRoot "leads"
$script:TrackingDir  = Join-Path $RepoRoot "tracking"
$script:TemplateDir  = Join-Path $RepoRoot "templates\emails"
$script:DraftsDir    = Join-Path $RepoRoot "templates\drafts"
$script:KnownCompanies = Join-Path $TrackingDir "known-companies.json"
$script:LeadLog      = Join-Path $TrackingDir "lead-log.md"
$script:LessonsFile  = Join-Path $TrackingDir "lessons-learned.md"
$script:LogDir       = Join-Path $RepoRoot "Logs"

# --- M365 Graph (reuse same app registration as hiring repo) ---
# SECRETS: read from user-scoped file scripts/secrets.json (gitignored).
# Expected shape:
# {
#   "graphTenantId":     "cab8077a-3f42-4277-b7bd-5c9023e826d8",
#   "graphAppClientId":  "4c009c1b-650c-42b5-86f5-312c083dec7c",
#   "graphAppClientSecret": "...",
#   "graphUserId":       "RJain@technijian.com"
# }
$script:SecretsFile = Join-Path $RepoRoot "scripts\secrets.json"
if (-not (Test-Path $script:SecretsFile)) {
    Write-Warning "scripts/secrets.json not found. Email sending disabled until it is provisioned."
    $script:TenantId = $null
    $script:AppClientId = $null
    $script:AppClientSecret = $null
    $script:UserId = "rjain@technijian.com"
} else {
    $secrets = Get-Content $script:SecretsFile -Raw | ConvertFrom-Json
    $script:TenantId        = $secrets.graphTenantId
    $script:AppClientId     = $secrets.graphAppClientId
    $script:AppClientSecret = $secrets.graphAppClientSecret
    $script:UserId          = $secrets.graphUserId
}

# --- Logs dir ---
if (-not (Test-Path $script:LogDir)) {
    New-Item -ItemType Directory -Path $script:LogDir -Force | Out-Null
}

# --- Logging ---
function Write-PipelineLog {
    param([string]$Message, [string]$Level = "INFO")
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$ts] [$Level] $Message"
    $logFile = Join-Path $script:LogDir ("tech-leads-" + (Get-Date -Format 'yyyy-MM-dd') + ".log")
    Add-Content -Path $logFile -Value $line
    Write-Host $line
}

# --- M365 Graph Auth (REST, client-credentials) ---
$script:GraphToken       = $null
$script:GraphTokenExpiry = [datetime]::MinValue

function Connect-PipelineGraph {
    if (-not $script:TenantId) {
        Write-PipelineLog "No M365 tenant configured (secrets.json missing) - skipping connect." "WARN"
        return $false
    }
    if ($script:GraphToken -and [datetime]::UtcNow -lt $script:GraphTokenExpiry) { return $true }

    Write-PipelineLog "Connecting to Microsoft Graph via client credentials..."
    try {
        $body = @{
            grant_type    = "client_credentials"
            client_id     = $script:AppClientId
            client_secret = $script:AppClientSecret
            scope         = "https://graph.microsoft.com/.default"
        }
        $resp = Invoke-RestMethod `
            -Uri "https://login.microsoftonline.com/$script:TenantId/oauth2/v2.0/token" `
            -Method POST -Body $body -ContentType "application/x-www-form-urlencoded"
        $script:GraphToken       = $resp.access_token
        $script:GraphTokenExpiry = [datetime]::UtcNow.AddSeconds($resp.expires_in - 60)
        Write-PipelineLog "Graph connected (userId: $script:UserId)."
        return $true
    } catch {
        Write-PipelineLog "Graph connect failed: $_" "ERROR"
        return $false
    }
}

function Get-GraphHeaders { @{ Authorization = "Bearer $script:GraphToken"; "Content-Type" = "application/json" } }

function Invoke-GraphGet  { param([string]$Url) Invoke-RestMethod -Uri $Url -Headers (Get-GraphHeaders) -Method GET }
function Invoke-GraphPost { param([string]$Url, [string]$Body) Invoke-RestMethod -Uri $Url -Headers (Get-GraphHeaders) -Method POST -Body $Body }

# --- Email template + signature helpers ---
function Get-EmailTemplate {
    param([string]$TemplateName)
    $p = Join-Path $script:TemplateDir $TemplateName
    if (-not (Test-Path $p)) { Write-PipelineLog "Template not found: $p" "ERROR"; return $null }
    return Get-Content $p -Raw -Encoding UTF8
}
function Get-EmailSignature {
    $p = Join-Path $script:TemplateDir "signature.html"
    if (Test-Path $p) { return Get-Content $p -Raw -Encoding UTF8 }
    return ""
}
function Build-BrandedEmail {
    param([string]$BodyContent)
    $sig = Get-EmailSignature
    return @"
<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#F8F9FA;font-family:'Open Sans','Segoe UI',Helvetica,Arial,sans-serif;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#F8F9FA;">
<tr><td align="center" style="padding:24px 16px;">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#FFFFFF;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.06);">
  <tr><td style="padding:24px 32px;border-bottom:3px solid #006DB6;">
    <img src="https://technijian.com/wp-content/uploads/2023/08/Logo.jpg" alt="Technijian" width="200" style="display:block;max-width:200px;height:auto;">
  </td></tr>
  <tr><td style="padding:32px;font-size:16px;color:#59595B;line-height:1.6;">
    $BodyContent
  </td></tr>
  <tr><td style="padding:16px 32px 32px;">
    $sig
  </td></tr>
</table>
</td></tr></table>
</body></html>
"@
}
