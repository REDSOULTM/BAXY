# Vuelca los Edit del arbol UIA de BAXY con su estado enabled/offscreen.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$app = Get-Process -Name 'Baxy' -ErrorAction SilentlyContinue | Select-Object -First 1
if ($null -eq $app) { throw 'BAXY no esta en marcha.' }
$app.Refresh()
("pid={0} hwnd={1}" -f $app.Id, $app.MainWindowHandle)
$root = [Windows.Automation.AutomationElement]::FromHandle($app.MainWindowHandle)
$all = $root.FindAll([Windows.Automation.TreeScope]::Descendants, [Windows.Automation.Condition]::TrueCondition)
("nodos={0}" -f $all.Count)
$cond = New-Object Windows.Automation.PropertyCondition(
    [Windows.Automation.AutomationElement]::ControlTypeProperty,
    [Windows.Automation.ControlType]::Edit)
$edits = $root.FindAll([Windows.Automation.TreeScope]::Descendants, $cond)
("edits={0}" -f $edits.Count)
for ($i = 0; $i -lt $edits.Count; $i++) {
    $e = $edits.Item($i).Current
    ("  [{0}] name='{1}' enabled={2} offscreen={3}" -f $i, $e.Name, $e.IsEnabled, $e.IsOffscreen)
}
# Textos visibles, para ver que dice BAXY.
$tcond = New-Object Windows.Automation.PropertyCondition(
    [Windows.Automation.AutomationElement]::ControlTypeProperty,
    [Windows.Automation.ControlType]::Text)
$texts = $root.FindAll([Windows.Automation.TreeScope]::Descendants, $tcond)
("textos={0}" -f $texts.Count)
# Telemetry occupies the beginning of the accessibility tree; the conversation
# is appended near the end. Keep the signal bounded but show the latest text.
$firstText = [Math]::Max(0, $texts.Count - 50)
for ($i = $firstText; $i -lt $texts.Count; $i++) {
    $t = $texts.Item($i).Current.Name
    if (-not [string]::IsNullOrWhiteSpace($t)) { ("  T[{0}]: {1}" -f $i, $t) }
}
