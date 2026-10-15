param([string]$Title)
# Independent check of a window: title, selected items, values of edits/documents (first 200 chars).
Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes
[Console]::OutputEncoding=[Text.Encoding]::UTF8
$r=[Windows.Automation.AutomationElement]::RootElement
$ws=@($r.FindAll('Children',[Windows.Automation.Condition]::TrueCondition) | Where-Object { $_.Current.Name -like "*$Title*" })
if($ws.Count -eq 0){ "NO WINDOW like $Title"; exit }
foreach($w in $ws){
  "WINDOW: $($w.Current.Name) pid=$($w.Current.ProcessId)"
  $n=0
  foreach($e in $w.FindAll('Descendants',[Windows.Automation.Condition]::TrueCondition)){
    $n++; if($n -gt 4000){break}
    try{
      $kind=$e.Current.ControlType.ProgrammaticName -replace 'ControlType.',''
      $name=$e.Current.Name
      $p=$null
      if($e.TryGetCurrentPattern([Windows.Automation.SelectionItemPattern]::Pattern,[ref]$p) -and $p.Current.IsSelected){ "  SELECTED $kind | $name" }
      if($kind -in 'Edit','Document'){ $v=$null; if($e.TryGetCurrentPattern([Windows.Automation.ValuePattern]::Pattern,[ref]$v)){ $t=$v.Current.Value; if($t){ "  VALUE $kind | $name = " + $t.Substring(0,[Math]::Min(200,$t.Length)) } } }
      $tg=$null; if($e.TryGetCurrentPattern([Windows.Automation.TogglePattern]::Pattern,[ref]$tg) -and $tg.Current.ToggleState -eq 'On' -and $kind -in 'Button','ListItem','RadioButton'){ "  ON $kind | $name" }
    }catch{}
  }
}
