# Cobertura de los controles sin nombre (goal v3, punto 3). Solo lectura: recorre el arbol UIA de cada ventana
# visible de primer nivel con una CacheRequest, sin SetFocus, sin mover el mouse ni enviar teclas, asi que no roba
# el foco a nadie.
#
# Por ventana cuenta los controles accionables en pantalla, los que no tienen Name y cuantos de esos recupera cada
# fuente de respaldo del worker (HelpText, LabeledBy, AutomationId legible), cada una por separado y en el orden en
# que el worker las usa. «antes» es lo que la vista listaba sin respaldo (accionables con nombre mas los Edit y
# Document sin nombre, que salen como «(edit)»); «despues» suma los recuperados. El nombre legible del AutomationId
# lo decide la propia funcion del worker (Get-ReadableId), leida por su arbol sintactico: la medida es la del
# producto, no una copia.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts/cu_live/cobertura_sin_arbol.ps1
#   ... -Process steam,Discord,WhatsApp,Spotify,mspaint     (solo esos procesos)
#   ... -Json                                                (una linea JSON por ventana)
#   ... -Detalle                                             (lista los controles recuperados)
#
# Excluye siempre Visual Studio Code y Opera (del dueno) y las ventanas del shell.
param([string[]]$Process=@(),[switch]$Json,[switch]$Detalle,[string]$Worker='')
$ErrorActionPreference='Stop'
# Con -File la lista llega como un solo texto «a,b,c»: se parte aqui.
$Process=@($Process | ForEach-Object { ([string]$_) -split ',' } | ForEach-Object { $_.Trim() } | Where-Object { $_.Length -gt 0 })
[Console]::OutputEncoding=New-Object System.Text.UTF8Encoding($false)
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
if([string]::IsNullOrWhiteSpace($Worker)){
  $Worker=Join-Path $PSScriptRoot '..\..\src\Baxy.Providers.Windows\External\DesktopUiaWorker.ps1'
}
$tokens=$null;$errors=$null
$ast=[System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path $Worker).Path,[ref]$tokens,[ref]$errors)
if($errors.Count -gt 0){ throw 'el worker no se puede leer' }
$wanted=@('Format-Name','Get-Name','Get-Prop','Get-ReadableId','Get-FallbackName','Get-ShownName')
$found=@($ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $wanted -contains $node.Name },$true))
if($found.Count -ne $wanted.Count){ throw 'al worker le faltan las funciones del nombre de respaldo' }
foreach($definition in $found){ . ([scriptblock]::Create($definition.Extent.Text)) }
$actionableAst=$ast.Find({ param($node) $node -is [System.Management.Automation.Language.AssignmentStatementAst] -and $node.Left.Extent.Text -eq '$Actionable' },$true)
$Actionable=@(& ([scriptblock]::Create($actionableAst.Right.Extent.Text)))

$AE=[System.Windows.Automation.AutomationElement]
$skip=@('Code','opera','opera_gx','explorer','TextInputHost','ShellExperienceHost','StartMenuExperienceHost','SearchHost','ApplicationFrameHost','Baxy','baxy-core','powershell','pwsh','WindowsTerminal','conhost')
$cache=New-Object System.Windows.Automation.CacheRequest
foreach($prop in @($AE::NameProperty,$AE::ControlTypeProperty,$AE::IsOffscreenProperty,$AE::IsEnabledProperty,
                   $AE::HelpTextProperty,$AE::AutomationIdProperty,$AE::LabeledByProperty,$AE::ClassNameProperty)){ $cache.Add($prop) }
$cache.AutomationElementMode=[System.Windows.Automation.AutomationElementMode]::Full
$enabled=New-Object System.Windows.Automation.PropertyCondition($AE::IsEnabledProperty,$true)

$windows=$AE::RootElement.FindAll([System.Windows.Automation.TreeScope]::Children,[System.Windows.Automation.Condition]::TrueCondition)
$rows=@()
foreach($window in $windows){
  try { $procId=$window.Current.ProcessId; $proc=(Get-Process -Id $procId -ErrorAction Stop).ProcessName; $title=[string]$window.Current.Name } catch { continue }
  if($skip -contains $proc){ continue }
  if($Process.Count -gt 0 -and -not ($Process | Where-Object { [string]::Equals($_,$proc,[StringComparison]::OrdinalIgnoreCase) })){ continue }
  $watch=[Diagnostics.Stopwatch]::StartNew()
  $activated=$cache.Activate()
  try { $all=$window.FindAll([System.Windows.Automation.TreeScope]::Descendants,$enabled) } catch { $all=@() } finally { $activated.Dispose() }
  $row=[ordered]@{ proceso=$proc; ventana=$(if($title.Length -gt 40){$title.Substring(0,40)}else{$title}); nodos=@($all).Count;
                  accionables=0; sinNombre=0; helpText=0; labeledBy=0; automationId=0; recuperados=0; nada=0; antes=0; despues=0; ms=0 }
  $detail=@()
  foreach($item in $all){
    try {
      if($item.Cached.IsOffscreen){ continue }
      $kind=$item.Cached.ControlType.ProgrammaticName -replace '^ControlType\.',''
      if($Actionable -notcontains $kind){ continue }
      $row.accionables++
      if((Get-Name $item).Length -gt 0){ $row.antes++; $row.despues++; continue }
      $row.sinNombre++
      if($kind -eq 'Edit' -or $kind -eq 'Document'){ $row.antes++ }
      # Cada fuente por separado (cuantos controles tiene cada una) ...
      if((Format-Name ([string]$item.Cached.HelpText)).Length -gt 0){ $row.helpText++ }
      $label=$null; try { $label=$item.Cached.LabeledBy } catch {}
      if($null -ne $label -and (Get-Name $label).Length -gt 0){ $row.labeledBy++ }
      if((Get-ReadableId ([string]$item.Cached.AutomationId) $kind ([string]$item.Cached.ClassName)).Length -gt 0){ $row.automationId++ }
      # ... y la que el worker elige, en su orden.
      $shown=Get-ShownName $item
      if($shown.name.Length -gt 0){
        $row.recuperados++
        $row.despues++
        if($Detalle){ $detail+=('    {0} "{1}" <- {2}' -f $kind,$shown.name,$shown.source) }
      } else {
        $row.nada++
        if($kind -eq 'Edit' -or $kind -eq 'Document'){ $row.despues++ }
      }
    } catch [System.Windows.Automation.ElementNotAvailableException] {}
  }
  $row.ms=$watch.ElapsedMilliseconds
  $rows+=,([pscustomobject]$row)
  if($Json){ [Console]::Out.WriteLine(([pscustomobject]$row | ConvertTo-Json -Compress)) }
  else {
    [Console]::Out.WriteLine(('{0,-16} {1,-28} nodos={2,5} accionables={3,4} sinNombre={4,3} helpText={5,3} labeledBy={6,3} automationId={7,3} recuperados={8,3} nada={9,3} antes={10,4} despues={11,4} ({12} ms)' -f
      $row.proceso,$row.ventana,$row.nodos,$row.accionables,$row.sinNombre,$row.helpText,$row.labeledBy,$row.automationId,$row.recuperados,$row.nada,$row.antes,$row.despues,$row.ms))
    foreach($line in $detail){ [Console]::Out.WriteLine($line) }
  }
}
