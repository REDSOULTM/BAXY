param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('schedule', 'schedule-recurring', 'cancel', 'cancel-exact', 'diagnose', 'resolve-at')]
    [string]$Mode,
    [Parameter(Mandatory = $true)]
    [ValidateSet('alarm', 'reminder')]
    [string]$Kind,
    [string]$TaskName,
    [string]$DueUtc,
    [string]$RingScriptPath,
    [string]$AlarmRoot,
    [ValidateSet('daily', 'hourly')]
    [string]$Recurrence,
    [int]$Hour = -1,
    [int]$Minute = 0,
    [ValidateSet('am', 'pm')]
    [string]$Period
)

$ErrorActionPreference = 'Stop'

if ($Mode -eq 'diagnose') {
    $service = Get-Service -Name 'Schedule' -ErrorAction Stop
    $tasks = @(Get-ScheduledTask -TaskName 'BAXY-*' -ErrorAction SilentlyContinue)
    $observed = @()
    $issueCount = 0
    foreach ($task in $tasks) {
        $info = Get-ScheduledTaskInfo -TaskName $task.TaskName -ErrorAction Stop
        $code = [int64]$info.LastTaskResult
        $acceptable = $code -eq 0 -or $code -eq 267011
        if (-not $acceptable) { $issueCount++ }
        $observed += [pscustomobject]@{
            taskName = [string]$task.TaskName
            state = [string]$task.State
            nextRunUtc = if ($info.NextRunTime -gt [datetime]::MinValue) { ([DateTimeOffset]$info.NextRunTime).ToUniversalTime().ToString('O') } else { $null }
            lastRunUtc = if ($info.LastRunTime -gt [datetime]::MinValue) { ([DateTimeOffset]$info.LastRunTime).ToUniversalTime().ToString('O') } else { $null }
            lastTaskResult = $code
            resultAcceptable = $acceptable
        }
    }
    $toastEnabled = $true
    $notificationPath = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Notifications\Settings'
    $notificationSettings = Get-ItemProperty -Path $notificationPath -ErrorAction SilentlyContinue
    if ($null -ne $notificationSettings -and $null -ne $notificationSettings.NOC_GLOBAL_SETTING_TOASTS_ENABLED) {
        $toastEnabled = [int]$notificationSettings.NOC_GLOBAL_SETTING_TOASTS_ENABLED -ne 0
    }
    $receipts = if ($AlarmRoot -and [IO.Directory]::Exists($AlarmRoot)) {
        @(Get-ChildItem -LiteralPath $AlarmRoot -Filter '*.fired' -File -ErrorAction SilentlyContinue)
    } else { @() }
    $schedulerRunning = [string]$service.Status -eq 'Running'
    if (-not $schedulerRunning) { $issueCount++ }
    if (-not $toastEnabled) { $issueCount++ }
    [pscustomobject]@{
        version = 1
        ok = $true
        schedulerRunning = $schedulerRunning
        toastEnabled = $toastEnabled
        healthy = $issueCount -eq 0
        taskCount = $observed.Count
        firedReceiptCount = $receipts.Count
        issueCount = $issueCount
        tasks = $observed
        authority = 'windows_task_scheduler_notification_diagnostics_postread'
    } | ConvertTo-Json -Compress -Depth 5
    exit 0
}

if ($Mode -eq 'resolve-at') {
    if ($Hour -lt 0 -or $Hour -gt 23 -or $Minute -lt 0 -or $Minute -gt 59 -or
        ($Period -and ($Hour -lt 1 -or $Hour -gt 12))) {
        throw 'invalid_clock_selector'
    }
    $targetHour = $Hour
    if ($Period -eq 'am') { $targetHour = $Hour % 12 }
    elseif ($Period -eq 'pm') { $targetHour = ($Hour % 12) + 12 }
    $prefix = if ($Kind -eq 'alarm') { 'BAXY-Alarm-*' } else { 'BAXY-Reminder-*' }
    $now = [DateTimeOffset]::Now
    $matches = @()
    foreach ($task in @(Get-ScheduledTask -TaskName $prefix -ErrorAction SilentlyContinue)) {
        $info = Get-ScheduledTaskInfo -TaskName $task.TaskName -ErrorAction Stop
        if ($info.NextRunTime -le [datetime]::MinValue) { continue }
        $next = [DateTimeOffset]$info.NextRunTime
        if ($next -le $now) { continue }
        $hourMatches = if ($Period) {
            $next.Hour -eq $targetHour
        } elseif ($Hour -le 12) {
            ($next.Hour % 12) -eq ($Hour % 12)
        } else {
            $next.Hour -eq $Hour
        }
        if ($hourMatches -and $next.Minute -eq $Minute) {
            $matches += [pscustomobject]@{
                taskName = [string]$task.TaskName
                nextRunUtc = $next.ToUniversalTime().ToString('O')
            }
        }
    }
    if ($matches.Count -ne 1) {
        [pscustomobject]@{
            version = 1
            ok = $false
            effectObserved = $false
            effectBoundaryCrossed = $false
            matchCount = $matches.Count
            authority = 'windows_task_scheduler_clock_resolution_snapshot'
        } | ConvertTo-Json -Compress
        exit 0
    }
    [pscustomobject]@{
        version = 1
        ok = $true
        effectObserved = $false
        effectBoundaryCrossed = $false
        matchCount = 1
        taskName = $matches[0].taskName
        nextRunUtc = $matches[0].nextRunUtc
        authority = 'windows_task_scheduler_clock_resolution_snapshot'
    } | ConvertTo-Json -Compress
    exit 0
}

if ($Mode -eq 'schedule' -or $Mode -eq 'schedule-recurring') {
    if ($TaskName -notmatch '^BAXY-(Alarm|Reminder)-[0-9a-f]{32}$') {
        throw 'invalid_task_name'
    }
    if (-not [IO.File]::Exists($RingScriptPath)) {
        throw 'ring_script_missing'
    }
    $due = [DateTimeOffset]::Parse(
        $DueUtc,
        [Globalization.CultureInfo]::InvariantCulture,
        [Globalization.DateTimeStyles]::RoundtripKind)
    $dueLocal = $due.LocalDateTime
    if ($due -le [DateTimeOffset]::UtcNow.AddSeconds(5)) {
        throw 'due_time_not_future'
    }
    $quotedScript = '"' + $RingScriptPath.Replace('"', '""') + '"'
    $action = New-ScheduledTaskAction `
        -Execute 'powershell.exe' `
        -Argument ('-NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File ' + $quotedScript)
    if ($Mode -eq 'schedule-recurring' -and $Recurrence -eq 'daily') {
        $trigger = New-ScheduledTaskTrigger -Daily -At $dueLocal
    }
    elseif ($Mode -eq 'schedule-recurring' -and $Recurrence -eq 'hourly') {
        $trigger = New-ScheduledTaskTrigger `
            -Once `
            -At $dueLocal `
            -RepetitionInterval (New-TimeSpan -Hours 1) `
            -RepetitionDuration (New-TimeSpan -Days 3650)
    }
    else {
        $trigger = New-ScheduledTaskTrigger -Once -At $dueLocal
    }
    $settings = New-ScheduledTaskSettingsSet `
        -StartWhenAvailable `
        -ExecutionTimeLimit (New-TimeSpan -Minutes 10)
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Description ('BAXY verified ' + $Kind) `
        -Force | Out-Null
    $task = Get-ScheduledTask -TaskName $TaskName
    $info = Get-ScheduledTaskInfo -TaskName $TaskName
    $deltaSeconds = [Math]::Abs(($info.NextRunTime - $dueLocal).TotalSeconds)
    [pscustomobject]@{
        version = 1
        ok = ($task.TaskName -eq $TaskName -and $deltaSeconds -le 2)
        effectObserved = $true
        taskName = $task.TaskName
        state = [string]$task.State
        nextRunUtc = ([DateTimeOffset]$info.NextRunTime).ToUniversalTime().ToString('O')
        recurrence = if ($Mode -eq 'schedule-recurring') { $Recurrence } else { 'none' }
        authority = 'windows_task_scheduler_postread'
    } | ConvertTo-Json -Compress
    exit 0
}

if ($Mode -eq 'cancel-exact') {
    $expectedPrefix = if ($Kind -eq 'alarm') { '^BAXY-Alarm-[0-9a-f]{32}$' } else { '^BAXY-Reminder-[0-9a-f]{32}$' }
    if ($TaskName -notmatch $expectedPrefix) { throw 'invalid_task_name' }
    $expectedDue = [DateTimeOffset]::Parse(
        $DueUtc,
        [Globalization.CultureInfo]::InvariantCulture,
        [Globalization.DateTimeStyles]::RoundtripKind)
    $candidate = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($null -eq $candidate) {
        [pscustomobject]@{
            version = 1
            ok = $false
            effectObserved = $false
            effectBoundaryCrossed = $false
            error = 'task_missing_before_effect'
        } | ConvertTo-Json -Compress
        exit 0
    }
    $candidateInfo = Get-ScheduledTaskInfo -TaskName $TaskName -ErrorAction Stop
    $observedDue = ([DateTimeOffset]$candidateInfo.NextRunTime).ToUniversalTime()
    if ([Math]::Abs(($observedDue - $expectedDue.ToUniversalTime()).TotalSeconds) -gt 2) {
        [pscustomobject]@{
            version = 1
            ok = $false
            effectObserved = $false
            effectBoundaryCrossed = $false
            error = 'task_changed_before_effect'
        } | ConvertTo-Json -Compress
        exit 0
    }
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    $stillPresent = $null -ne (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue)
    [pscustomobject]@{
        version = 1
        ok = (-not $stillPresent)
        effectObserved = $true
        effectBoundaryCrossed = $true
        canceled = (-not $stillPresent)
        taskName = $TaskName
        nextRunUtc = $observedDue.ToString('O')
        authority = 'windows_task_scheduler_exact_identity_absence_postread'
    } | ConvertTo-Json -Compress
    exit 0
}

$prefix = if ($Kind -eq 'alarm') { 'BAXY-Alarm-*' } else { 'BAXY-Reminder-*' }
$candidate = Get-ScheduledTask -TaskName $prefix -ErrorAction SilentlyContinue |
    Sort-Object { $_.RegistrationInfo.Date } -Descending |
    Select-Object -First 1
if ($null -eq $candidate) {
    [pscustomobject]@{
        version = 1
        ok = $true
        effectObserved = $false
        canceled = $false
        authority = 'windows_task_scheduler_absence_postread'
    } | ConvertTo-Json -Compress
    exit 0
}
$selected = $candidate.TaskName
Unregister-ScheduledTask -TaskName $selected -Confirm:$false
$stillPresent = $null -ne (Get-ScheduledTask -TaskName $selected -ErrorAction SilentlyContinue)
[pscustomobject]@{
    version = 1
    ok = (-not $stillPresent)
    effectObserved = $true
    canceled = (-not $stillPresent)
    taskName = $selected
    authority = 'windows_task_scheduler_absence_postread'
} | ConvertTo-Json -Compress
