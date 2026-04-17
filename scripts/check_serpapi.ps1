# check_serpapi.ps1 - Sanity-check SerpAPI key + Google Jobs engine.
# Usage:  powershell .\scripts\check_serpapi.ps1

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path $PSScriptRoot -Parent
$SecretsFile = Join-Path $RepoRoot "scripts\secrets.json"

if (-not (Test-Path $SecretsFile)) {
    Write-Error "secrets.json not found at $SecretsFile"
    exit 1
}

$secrets = Get-Content $SecretsFile -Raw | ConvertFrom-Json
$key = $secrets.serpApiKey
if (-not $key) {
    Write-Error "secrets.json has no serpApiKey field"
    exit 1
}

$query = "HIPAA+Compliance+Officer"
$location = "Irvine,California"
$url = "https://serpapi.com/search.json?engine=google_jobs&q=$query&location=$location&hl=en&gl=us&api_key=$key"

Write-Host "Calling SerpAPI (Google Jobs, query=$query, location=$location)..."
try {
    $r = Invoke-RestMethod -Uri $url -Method GET -TimeoutSec 45
} catch {
    Write-Error "HTTP call failed: $_"
    exit 1
}

Write-Host ""
Write-Host "Status:          $($r.search_metadata.status)"
Write-Host "Search id:       $($r.search_metadata.id)"
Write-Host "Time taken:      $($r.search_metadata.total_time_taken)s"
Write-Host "Jobs returned:   $(@($r.jobs_results).Count)"
if ($r.search_information) {
    Write-Host "Result summary:  $($r.search_information.query_displayed)"
}

if ($r.error) {
    Write-Error "SerpAPI error: $($r.error)"
    exit 1
}

Write-Host ""
Write-Host "--- First 3 results ---"
@($r.jobs_results) | Select-Object -First 3 | ForEach-Object {
    Write-Host ""
    Write-Host "  $($_.title)"
    Write-Host "    company:  $($_.company_name)"
    Write-Host "    location: $($_.location)"
    Write-Host "    posted:   $($_.detected_extensions.posted_at)"
    Write-Host "    via:      $($_.via)"
    $link = ($_.apply_options | Select-Object -First 1).link
    Write-Host "    apply:    $link"
}

Write-Host ""
Write-Host "OK - SerpAPI wired correctly."
