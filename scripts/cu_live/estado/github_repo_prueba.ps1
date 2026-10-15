# State github_repo_prueba[:claro]: GitHub Desktop freshly open (app_abierta) on the harness's test repository
# (repo_prueba_comun.ps1) as its current repository. Pasada r9: its only repository was the owner's "RicardoYMontiel",
# missing on disk, so v3-54, v3-55 and v3-56 met "Can't find" with no History, branch or Options to work on.
#  - The repo is rebuilt when it is not exactly the expected one (3 commits on main, branch prueba-rama, clean).
#  - Measured 2026-10-08: GitHub Desktop 3.6.6 ignored both x-github-client://openLocalRepo/<path> and
#    --cli-open=<path> (what its "github" tool runs); its own dialog works through UIA: File > "Add local repository"
#    > Local path (ValuePattern) > "Add repository". A repo it already knows is picked from the "Current repository"
#    list instead. GitHub Desktop remembers the current repository for the next launch (v3-54 starts it closed).
#  - :claro also leaves the light theme (v3-56 switches it to dark): File > Options > Appearance > Light > Save, read
#    back from the window's pixels.
#  - Verified through UIA: the toolbar button is "Current repository <repo>" and nothing says "Can't find".
# Only UIA patterns: no key or mouse input. A copy the person opened is never touched (app_abierta says ajena_abierta).
# Harness only. ASCII only.
param([string]$Arg='')
if(-not (Get-Command Write-Estado -ErrorAction SilentlyContinue)){ . (Join-Path $PSScriptRoot 'comun.ps1') }
. (Join-Path $PSScriptRoot 'apps_comun.ps1')
. (Join-Path $PSScriptRoot 'repo_prueba_comun.ps1')
. (Join-Path $PSScriptRoot 'decisiones_comun.ps1')
$E=$(if($Arg){ "github_repo_prueba:$Arg" }else{ 'github_repo_prueba' })
if($Arg -and $Arg -ne 'claro'){ Write-Estado $E 'sin_argumento' @{ verificado=$false; nota='github_repo_prueba[:claro]' }; return }
$repo=Split-Path $global:RepoPruebaRaiz -Leaf
$elipsis=[string][char]0x2026

function Get-Todos($W){ try{ @($W.FindAll('Descendants',[Windows.Automation.Condition]::TrueCondition)) }catch{ @() } }
function Get-Nombres($W){ @(Get-Todos $W | ForEach-Object { try{ [string]$_.Current.Name }catch{ '' } }) }
function Find-Control($W,[string]$Tipo,[scriptblock]$Nombre){
  # First element of that control type whose name passes $Nombre.
  @(Get-Todos $W | Where-Object { try{ $_.Current.ControlType.ProgrammaticName -eq "ControlType.$Tipo" -and (& $Nombre ([string]$_.Current.Name)) }catch{ $false } })[0]
}
function Wait-Control($W,[string]$Tipo,[scriptblock]$Nombre,[int]$Segundos=8){
  $fin=(Get-Date).AddSeconds($Segundos)
  do{ $c=Find-Control $W $Tipo $Nombre; if($c){ return $c }; Start-Sleep -Milliseconds 400 }while((Get-Date) -lt $fin)
  $null
}
function Open-MenuArchivo($W,[string]$Item){
  # File menu of GitHub Desktop's own title bar, then the item whose name starts with $Item.
  $f=Find-Control $W 'MenuItem' { param($n) $n -ceq 'File' }
  if(-not $f){ return $false }
  [void](Invoke-Element $f)
  $i=Wait-Control $W 'MenuItem' { param($n) $n.StartsWith($Item) } 4
  if(-not $i){ return $false }
  [void](Invoke-Element $i); $true
}
function Get-Brillo([long]$Hwnd){
  $bmp=Get-WindowBitmap ([IntPtr]$Hwnd); if(-not $bmp){ return $null }
  try{ $s=0.0; $n=0; for($x=10;$x -lt $bmp.Width;$x+=37){ for($y=40;$y -lt $bmp.Height;$y+=37){ $p=$bmp.GetPixel($x,$y); $s+=($p.R+$p.G+$p.B)/3.0; $n++ } }; if($n){ [int]($s/$n) }else{ $null } }finally{ $bmp.Dispose() }
}
function Select-RepoPrueba($W){
  # Already known: picked from the Current repository list. Otherwise added through File > Add local repository.
  $b=Find-Control $W 'Button' { param($n) $n.StartsWith('Current repository') }
  if($b){
    [void](Invoke-Element $b)
    $it=Wait-Control $W 'ListItem' { param($n) $n -ceq $repo -or $n.StartsWith("$repo ") } 3
    if(-not $it){ $it=Wait-Control $W 'Text' { param($n) $n -ceq $repo } 1 }
    if($it){ try{ [void](Invoke-Element $it) }catch{} ; Start-Sleep -Milliseconds 800; if(Get-DecisionGithubRepo (Get-Nombres $W) $repo){ return 'elegido' } }
    try{ [void](Invoke-Element $b) }catch{}
  }
  if(-not (Open-MenuArchivo $W ('Add local repository'+$elipsis))){ return 'sin_menu' }
  $ed=Wait-Control $W 'Edit' { param($n) $n -ceq 'Local path' } 5
  if(-not $ed){ return 'sin_dialogo' }
  $ed.GetCurrentPattern([Windows.Automation.ValuePattern]::Pattern).SetValue($global:RepoPruebaRaiz)
  Start-Sleep -Milliseconds 600
  $add=Find-Control $W 'Button' { param($n) $n -ceq 'Add repository' }
  if(-not $add){ return 'sin_boton' }
  [void](Invoke-Element $add)
  'agregado'
}

$repoHecho=$false
if(-not (Test-RepoPruebaValido (Get-RepoPruebaEstado))){
  $repoHecho=$true
  if(-not (New-RepoPrueba)){ Write-Estado $E 'repo_no_creado' @{ verificado=$false; ruta=$global:RepoPruebaRaiz; motivo=$global:RepoPruebaMotivo }; return }
}
$fg=Get-Foreground
$abre=@(& (Join-Path $PSScriptRoot 'app_abierta.ps1') -Arg 'GitHub Desktop' | Where-Object { "$_" -match '^\{"estado"' } | ForEach-Object { "$_" | ConvertFrom-Json })
if($abre.Count -eq 0 -or -not $abre[-1].verificado){
  Write-Estado $E 'no_abre' @{ verificado=$false; app_abierta=$(if($abre.Count){ [string]$abre[-1].resultado }else{ 'sin_informe' }) }; return
}
$prop=@(Get-Propios | Where-Object { $_.tipo -eq 'app' -and $_.proceso -eq 'GitHubDesktop' -and [EstadoW32]::IsWindow([IntPtr][long]$_.hwnd) })
if($prop.Count -eq 0){ Write-Estado $E 'sin_ventana' @{ verificado=$false }; return }
$hwnd=[long]$prop[-1].hwnd
$w=[Windows.Automation.AutomationElement]::FromHandle([IntPtr]$hwnd)
# Chromium builds its UIA tree on the first query: wait for the toolbar.
[void](Wait-Control $w 'Button' { param($n) $n.StartsWith('Current repository') } 20)
$paso='ya_estaba'
if(-not (Get-DecisionGithubRepo (Get-Nombres $w) $repo)){
  $paso=Select-RepoPrueba $w
  $fin=(Get-Date).AddSeconds(15)
  while(-not (Get-DecisionGithubRepo (Get-Nombres $w) $repo) -and (Get-Date) -lt $fin){ Start-Sleep -Milliseconds 600 }
}
$actual=Get-DecisionGithubRepo (Get-Nombres $w) $repo
$tema=''; $brillo=$null
if($Arg -eq 'claro'){
  $brillo=Get-Brillo $hwnd
  if(-not (Get-DecisionTemaClaro $brillo) -and (Open-MenuArchivo $w ('Options'+$elipsis))){
    $t=Wait-Control $w 'TabItem' { param($n) $n -ceq 'Appearance' } 5
    if($t){ [void](Invoke-Element $t) }
    $r=Wait-Control $w 'RadioButton' { param($n) $n -ceq 'Light' } 4
    if($r){ [void](Invoke-Element $r) }
    $s=Wait-Control $w 'Button' { param($n) $n -ceq 'Save' } 3
    if($s){ [void](Invoke-Element $s) }
    Start-Sleep -Milliseconds 1200
    # Options must not stay open (revision 2026-10-08: with no Save button it sat on Appearance, and v3-56 would have
    # started with half the case done): its own Cancel closes it; one still open makes the state unverified.
    if(Get-DecisionOpcionesAbiertas (Get-Nombres $w)){
      $c=Find-Control $w 'Button' { param($n) $n -ceq 'Cancel' }
      if($c){ [void](Invoke-Element $c); Start-Sleep -Milliseconds 800 }
    }
    $brillo=Get-Brillo $hwnd
  }
  $tema=$(if(Get-DecisionTemaClaro $brillo){ 'claro' }else{ 'oscuro' })
}
$opciones=Get-DecisionOpcionesAbiertas (Get-Nombres $w)
$foco=Restore-Foreground $fg @('GitHubDesktop')
$ok=($actual -and -not $opciones -and ($Arg -ne 'claro' -or $tema -eq 'claro'))
Write-Estado $E ($(if(-not $ok){'no_verificado'}elseif($paso -eq 'ya_estaba' -and -not $repoHecho){'ok'}else{'corregido'})) @{ verificado=$ok; repo=$repo
  repo_rehecho=$repoHecho; paso=$paso; tema=$tema; brillo=$brillo; opciones_abiertas=$opciones; foco=$foco }
