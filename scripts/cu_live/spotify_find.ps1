param([string]$Needle,[string]$InvokePrefix)
# Lists Spotify controls whose name holds $Needle; with -InvokePrefix, invokes the single one whose name starts with it.
Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes
[Console]::OutputEncoding=[Text.Encoding]::UTF8
if([string]::IsNullOrWhiteSpace($Needle) -or $Needle.Length -lt 6){ throw 'needle of 6+ chars required' }
$p=Get-Process Spotify -ErrorAction SilentlyContinue | Where-Object MainWindowHandle -ne 0 | Select-Object -First 1
if(-not $p){ 'no spotify window'; exit 1 }
$w=[Windows.Automation.AutomationElement]::FromHandle($p.MainWindowHandle)
$hits=@()
foreach($e in $w.FindAll('Descendants',[Windows.Automation.Condition]::TrueCondition)){
  $n=$e.Current.Name; if($n -and $n -like "*$Needle*"){ $hits+=$e; "$($e.Current.ControlType.ProgrammaticName) | $n" }
}
if($InvokePrefix){
  $t=@($hits | Where-Object { $_.Current.Name.StartsWith($InvokePrefix) -and $_.Current.ControlType -eq [Windows.Automation.ControlType]::Button })
  if($t.Count -ne 1){ "not exactly one target ($($t.Count))"; exit 2 }
  $t[0].GetCurrentPattern([Windows.Automation.InvokePattern]::Pattern).Invoke(); "invoked: $($t[0].Current.Name)"
}
