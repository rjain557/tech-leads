# Quick utility: list the tech-leads scheduled tasks + next run time
$names = @('tech-leads weekly scan', 'tech-leads daily reply check')
foreach ($n in $names) {
    $t = Get-ScheduledTask -TaskName $n -ErrorAction SilentlyContinue
    if (-not $t) {
        Write-Host "NOT INSTALLED: $n"
        continue
    }
    $info = Get-ScheduledTaskInfo -TaskName $n
    Write-Host ("{0,-32} state={1,-10} next={2}" -f $n, $t.State, $info.NextRunTime)
}
