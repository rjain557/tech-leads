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

# --- Weekly scan + digest (chained via Run-Weekly.ps1) ---
Remove-TaskIfExists $TaskScan
$weeklyPs = Join-Path $RepoRoot "scripts\Run-Weekly.ps1"
$scanAction = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$weeklyPs`"" -WorkingDirectory $RepoRoot
$scanTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At 6:00am
$scanSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd -ExecutionTimeLimit (New-TimeSpan -Hours 1)
Register-ScheduledTask -TaskName $TaskScan -Action $scanAction -Trigger $scanTrigger -Settings $scanSettings -Description "Technijian lead-gen weekly scan (SerpAPI) + department digest email" | Out-Null
Write-Host "Installed: $TaskScan (Mon 06:00 — scan + digest chained)"

# --- Daily reply check (git pull + Check-Replies chained via Run-Daily.ps1) ---
Remove-TaskIfExists $TaskReply
$dailyPs = Join-Path $RepoRoot "scripts\Run-Daily.ps1"
$replyAction = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$dailyPs`"" -WorkingDirectory $RepoRoot
$replyTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At 8:00am
$replySettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd -ExecutionTimeLimit (New-TimeSpan -Minutes 15)
Register-ScheduledTask -TaskName $TaskReply -Action $replyAction -Trigger $replyTrigger -Settings $replySettings -Description "Technijian lead-gen daily reply safety-net (pulls config from other sessions first)" | Out-Null
Write-Host "Installed: $TaskReply (Mon-Fri 08:00 — pull + reply check)"

Write-Host ""
Write-Host "Both tasks installed. Manage via Task Scheduler UI or:"
Write-Host "  Get-ScheduledTask -TaskName '$TaskScan','$TaskReply'"
Write-Host "  Start-ScheduledTask -TaskName '$TaskScan'   # run now"
Write-Host "  Start-ScheduledTask -TaskName '$TaskReply'  # run now"
