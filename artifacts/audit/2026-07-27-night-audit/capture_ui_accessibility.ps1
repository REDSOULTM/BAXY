param(
    [Parameter(Mandatory = $true)]
    [int]$ProcessId,
    [Parameter(Mandatory = $true)]
    [string]$OutputPath
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

$process = Get-Process -Id $ProcessId
$root = [System.Windows.Automation.AutomationElement]::FromHandle(
    $process.MainWindowHandle)
$all = $root.FindAll(
    [System.Windows.Automation.TreeScope]::Descendants,
    [System.Windows.Automation.Condition]::TrueCondition)

$items = @(
    for ($index = 0; $index -lt $all.Count; $index++) {
        $element = $all.Item($index)
        $name = $element.Current.Name
        if (-not [string]::IsNullOrWhiteSpace($name)) {
            [pscustomobject]@{
                index = $index
                control_type = $element.Current.ControlType.ProgrammaticName
                name = $name
                automation_id = $element.Current.AutomationId
                enabled = $element.Current.IsEnabled
                offscreen = $element.Current.IsOffscreen
                bounds = $element.Current.BoundingRectangle.ToString()
            }
        }
    }
)

$evidence = [ordered]@{
    captured_at_utc = [DateTimeOffset]::UtcNow.ToString('O')
    process_id = $ProcessId
    process_name = $process.ProcessName
    main_window_title = $process.MainWindowTitle
    elements = $items
}
$json = $evidence | ConvertTo-Json -Depth 5
$absoluteOutput = [System.IO.Path]::GetFullPath($OutputPath)
[System.IO.File]::WriteAllText(
    $absoluteOutput,
    $json,
    [System.Text.UTF8Encoding]::new($false))

[pscustomobject]@{
    output = $absoluteOutput
    element_count = $items.Count
} | ConvertTo-Json -Compress
