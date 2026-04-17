# Install-Tasks.ps1 — One-shot installer for the two scheduled tasks.
#
#   Weekly scan:  every Monday 06:00 local -> scan_jobs.py --scope all
#   Daily reply:  Mon-Fri 08:00 local       -> Check-Replies.ps1
#
# Idempotent — re-running replaces existing tasks. Run once per workstation.
# Requires Python on PATH for the weekly scan task; the daily task is pure PowerShell.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\Install-Tasks.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\Install-Tasks.ps1 -Uninstall

param([switch]$Uninstall)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path $PSScriptRoot -Parent
$TaskScan   = "tech-leads weekly scan"
$TaskReply  = "tech-leads daily reply check"

function Remove-TaskIfExists {
    param([string]$Name)
    if (Get-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $Name -Confirm:$false
        Write-Host "Removed: $Name"
    }
}

if ($Uninstall) {
    Remove-TaskIfExists $TaskScan
    Remove-TaskIfExists $TaskReply
    Write-Host "Uninstall complete."
    exit 0
}

# --- Weekly scan ---
Remove-TaskIfExists $TaskScan
$scanPy = Join-Path $RepoRoot "scripts\scan_jobs.py"
$scanAction = New-ScheduledTaskAction -Execute "python" -Argument "`"$scanPy`" --scope all" -WorkingDirectory $RepoRoot
$scanTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At 6:00am
$scanSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd -ExecutionTimeLimit (New-TimeSpan -Hours 1)
Register-ScheduledTask -TaskName $TaskScan -Action $scanAction -Trigger $scanTrigger -Settings $scanSettings -Description "Technijian lead-gen weekly scan (SerpAPI)" | Out-Null
Write-Host "Installed: $TaskScan (Mon 06:00)"

# --- Daily reply check ---
Remove-TaskIfExists $TaskReply
$replyPs = Join-Path $RepoRoot "scripts\Check-Replies.ps1"
$replyAction = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$replyPs`"" -WorkingDirectory $RepoRoot
$replyTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At 8:00am
$replySettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd -ExecutionTimeLimit (New-TimeSpan -Minutes 15)
Register-ScheduledTask -TaskName $TaskReply -Action $replyAction -Trigger $replyTrigger -Settings $replySettings -Description "Technijian lead-gen daily reply safety-net" | Out-Null
Write-Host "Installed: $TaskReply (Mon-Fri 08:00)"

Write-Host ""
Write-Host "Both tasks installed. Manage via Task Scheduler UI or:"
Write-Host "  Get-ScheduledTask -TaskName '$TaskScan','$TaskReply'"
Write-Host "  Start-ScheduledTask -TaskName '$TaskScan'   # run now"
Write-Host "  Start-ScheduledTask -TaskName '$TaskReply'  # run now"
