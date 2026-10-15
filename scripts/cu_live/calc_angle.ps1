param([switch]$Fix)
# Reads (and with -Fix, returns to degrees) the Calculator's angle unit button; only the Calculator window is touched.
Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes
[Console]::OutputEncoding=[Text.Encoding]::UTF8
$r=[Windows.Automation.AutomationElement]::RootElement
$w=$null
foreach($c in $r.FindAll('Children',[Windows.Automation.Condition]::TrueCondition)){ if($c.Current.Name -eq 'Calculadora'){ $w=$c; break } }
if(-not $w){ 'no calculator window'; exit 1 }
function Angle(){ foreach($e in $w.FindAll('Descendants',[Windows.Automation.Condition]::TrueCondition)){ if($e.Current.Name -match '^Alternar (grados|radianes|gradianes)$'){ return $e } }; return $null }
$a=Angle
if(-not $a){ 'no angle button (not in scientific mode)'; exit 2 }
"angle: $($a.Current.Name)"
if($Fix){
  for($i=0;$i -lt 3 -and $a.Current.Name -ne 'Alternar grados';$i++){
    $a.GetCurrentPattern([Windows.Automation.InvokePattern]::Pattern).Invoke(); Start-Sleep -Milliseconds 400; $a=Angle; "now: $($a.Current.Name)"
  }
}
