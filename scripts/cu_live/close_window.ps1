param([string]$Title)
# Closes top-level windows whose name contains $Title through UIA WindowPattern (a normal close, never a kill).
if([string]::IsNullOrWhiteSpace($Title) -or $Title.Length -lt 4){ throw "close_window: a title of 4+ characters is required" }
Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes
$r=[Windows.Automation.AutomationElement]::RootElement
foreach($w in @($r.FindAll('Children',[Windows.Automation.Condition]::TrueCondition) | Where-Object { $_.Current.Name -like "*$Title*" -and $_.Current.Name -notlike "*Visual Studio Code*" -and $_.Current.Name -notlike "*Opera*" })){
  try{ $w.GetCurrentPattern([Windows.Automation.WindowPattern]::Pattern).Close(); "closed: $($w.Current.Name)" }catch{ "could not close: $($w.Current.Name)" }
}
