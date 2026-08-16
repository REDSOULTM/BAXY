$ErrorActionPreference = 'Stop'
$step = 'start'
try {
    Add-Type -AssemblyName UIAutomationClient
    Add-Type -AssemblyName System.Windows.Forms
    $step = 'focused_element'
    $focused = [Windows.Automation.AutomationElement]::FocusedElement
    if ($null -eq $focused) {
        throw 'focused_element_missing'
    }
    $summary = [ordered]@{
        step = $step
        processId = $focused.Current.ProcessId
        controlType = $focused.Current.ControlType.ProgrammaticName
        className = $focused.Current.ClassName
        textPatternAvailable = $false
        selectionCount = $null
        startCompared = $null
        endCompared = $null
        exceptionType = $null
        exceptionMessage = $null
        hresult = $null
    }
    $pattern = $null
    $step = 'try_text_pattern'
    $available = $focused.TryGetCurrentPattern(
        [Windows.Automation.TextPattern]::Pattern,
        [ref]$pattern)
    $summary.textPatternAvailable = $available
    if (-not $available) {
        throw 'focused_control_has_no_text_pattern'
    }
    $text = [Windows.Automation.TextPattern]$pattern
    $step = 'send_ctrl_a'
    [System.Windows.Forms.SendKeys]::SendWait('^a')
    Start-Sleep -Milliseconds 250
    $step = 'get_selection'
    $selection = @($text.GetSelection())
    $summary.selectionCount = $selection.Count
    if ($selection.Count -eq 1) {
        $step = 'compare_start'
        $summary.startCompared = $selection[0].CompareEndpoints(
            [Windows.Automation.TextPatternRangeEndpoint]::Start,
            $text.DocumentRange,
            [Windows.Automation.TextPatternRangeEndpoint]::Start)
        $step = 'compare_end'
        $summary.endCompared = $selection[0].CompareEndpoints(
            [Windows.Automation.TextPatternRangeEndpoint]::End,
            $text.DocumentRange,
            [Windows.Automation.TextPatternRangeEndpoint]::End)
    }
    $summary.step = 'complete'
    [pscustomobject]$summary | ConvertTo-Json -Compress
} catch {
    if ($null -eq $summary) {
        $summary = [ordered]@{
            processId = $null
            controlType = $null
            className = $null
            textPatternAvailable = $null
            selectionCount = $null
            startCompared = $null
            endCompared = $null
        }
    }
    $summary.step = $step
    $summary.exceptionType = $_.Exception.GetType().FullName
    $summary.exceptionMessage = $_.Exception.Message
    $summary.hresult = $_.Exception.HResult
    [pscustomobject]$summary | ConvertTo-Json -Compress
    exit 2
}
