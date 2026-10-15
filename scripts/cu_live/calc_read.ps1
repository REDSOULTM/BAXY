Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes
[Console]::OutputEncoding=[Text.Encoding]::UTF8
$root=[Windows.Automation.AutomationElement]::RootElement
$c=New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::NameProperty,'Calculadora')
$w=$root.FindFirst([Windows.Automation.TreeScope]::Children,$c)
if(-not $w){'no calc window';exit}
$d=$w.FindFirst([Windows.Automation.TreeScope]::Descendants,(New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::AutomationIdProperty,'CalculatorResults')))
$e=$w.FindFirst([Windows.Automation.TreeScope]::Descendants,(New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::AutomationIdProperty,'CalculatorExpression')))
"result: $($d.Current.Name) | expression: $($e.Current.Name)"
Get-Process CalculatorApp -ErrorAction SilentlyContinue | Select Id,StartTime | Format-Table | Out-String
