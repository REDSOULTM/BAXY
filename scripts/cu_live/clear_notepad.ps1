param([Parameter(Mandatory=$true)][int]$ProcessId)
# Empties and closes the Notepad windows the harness opened in exactly this process; nothing else.
# Windows 11 Notepad keeps EVERY window in one process (review r10a): a window is touched only when its HWND is
# recorded in propios.jsonl with this same pid (what the harness opened), and inside it only an untitled tab whose
# whole text is made of the bank's test texts (textos_de_prueba.json) is emptied (Get-DecisionPestanaBloc, like
# bloc_vacio). A window that keeps any other text (the person's, or a file) is left open and reported. No tab text is
# ever printed.
. (Join-Path $PSScriptRoot 'estado\comun.ps1')
. (Join-Path $PSScriptRoot 'estado\decisiones_comun.ps1')
$p=Get-Process -Id $ProcessId -ErrorAction Stop
if($p.ProcessName -ne 'Notepad'){ throw "pid $ProcessId is $($p.ProcessName), not Notepad" }
$textos=@(([IO.File]::ReadAllText((Join-Path $PSScriptRoot 'estado\textos_de_prueba.json'),[Text.Encoding]::UTF8) | ConvertFrom-Json).textos)
$mias=@(Get-Propios | Where-Object { [int]$_.pid -eq $ProcessId -and [long]$_.hwnd -ne 0 } | ForEach-Object { [long]$_.hwnd })
if($mias.Count -eq 0){ "no window of pid $ProcessId is in propios.jsonl: nothing touched"; return }
$cPid=New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::ProcessIdProperty,$ProcessId)
$cTab=New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::ControlTypeProperty,[Windows.Automation.ControlType]::TabItem)
$cDoc=New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::ControlTypeProperty,[Windows.Automation.ControlType]::Document)
foreach($w in @([Windows.Automation.AutomationElement]::RootElement.FindAll('Children',$cPid))){
  $h=[long]$w.Current.NativeWindowHandle
  if($mias -notcontains $h){ "left alone (not opened by the harness): $h"; continue }
  $ajenas=0
  foreach($tab in @($w.FindAll('Descendants',$cTab))){
    # An untitled tab is named after its first line ("hola BAXY. Modificado."); a file tab after the file.
    $sin=-not ($tab.Current.Name -match '\.[A-Za-z0-9]{1,5}\.\s')
    $s=$null; if($tab.TryGetCurrentPattern([Windows.Automation.SelectionItemPattern]::Pattern,[ref]$s)){ $s.Select(); Start-Sleep -Milliseconds 300 }
    $d=$w.FindFirst('Descendants',$cDoc)
    switch(Get-DecisionPestanaBloc $sin (Get-Value $d) $textos){
      'vaciar' { $d.GetCurrentPattern([Windows.Automation.ValuePattern]::Pattern).SetValue(''); Start-Sleep -Milliseconds 200; if(-not [string]::IsNullOrEmpty((Get-Value $d))){ $ajenas++ } }
      'ajena' { $ajenas++ }
    }
  }
  if($ajenas -gt 0){ "left open ($ajenas tab(s) with other text): $h"; continue }
  Start-Sleep -Milliseconds 300
  try{ Close-WindowExact $w; "closed $h" }catch{ "could not close $h" }
}
