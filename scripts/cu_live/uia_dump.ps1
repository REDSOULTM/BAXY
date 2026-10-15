param([string]$Title)
Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes
[Console]::OutputEncoding=[Text.Encoding]::UTF8
$r=[Windows.Automation.AutomationElement]::RootElement
$w=$null
foreach($c in $r.FindAll('Children',[Windows.Automation.Condition]::TrueCondition)){ if($c.Current.Name -like "*$Title*"){ $w=$c; break } }
if(-not $w){ "no window $Title"; exit }
"WINDOW: $($w.Current.Name) pid=$($w.Current.ProcessId)"
foreach($e in $w.FindAll('Descendants',[Windows.Automation.Condition]::TrueCondition)){
  $n=$e.Current.Name; if(-not $n){continue}
  $sel=''; try{ $p=$e.GetCurrentPattern([Windows.Automation.SelectionItemPattern]::Pattern); if($p.Current.IsSelected){$sel=' [selected]'} }catch{}
  "$($e.Current.ControlType.ProgrammaticName -replace 'ControlType.','') | $n$sel"
}
