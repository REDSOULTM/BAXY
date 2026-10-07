param([Parameter(Mandatory=$true)][int]$ProcessId)
# Empties and closes the Notepad window of exactly this process (a test window); nothing else.
Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes
$p=Get-Process -Id $ProcessId -ErrorAction Stop
if($p.ProcessName -ne 'Notepad'){ throw "pid $ProcessId is $($p.ProcessName), not Notepad" }
$c=New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::ProcessIdProperty,$ProcessId)
foreach($w in @([Windows.Automation.AutomationElement]::RootElement.FindAll('Children',$c))){
  $e=New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::ControlTypeProperty,[Windows.Automation.ControlType]::Document)
  $d=$w.FindFirst('Descendants',$e); if($d){ $d.GetCurrentPattern([Windows.Automation.ValuePattern]::Pattern).SetValue('') }
  Start-Sleep -Milliseconds 300
  $w.GetCurrentPattern([Windows.Automation.WindowPattern]::Pattern).Close(); "closed $($w.Current.Name)"
}
