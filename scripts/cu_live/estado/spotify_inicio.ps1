# State spotify_inicio: Spotify on its home page, with the top search box empty and "Tu biblioteca" folded.
# Why (banco c24b/c25, y8 u1 v8 u9 x7): Spotify stays open between cases, so each one started where the last one left
# it: text of an earlier case in the search box (the button that empties it then takes the place of "Novedades"),
# the keyboard on "Buscar" and the library unfolded. v2 (71/72) closed Spotify after every case, so it always opened
# on the home page with an empty box; its journal (2026-10-07) shows the library folded in 120 of 141 first reads, and
# that is what makes "anda a tu biblioteca" have something to do (r23b: one click on the button that unfolds it).
# Harness only, never product code.
#  - Only UIA patterns on three controls of the top bar and the library header, by exact name: Invoke on the box's own
#    "empty" button, on the home button and on the one that folds the library, and the empty text set in the search
#    box through ValuePattern (as config_busqueda_vacia does). Nothing is typed, no mouse; nothing is played or
#    paused, nothing of the account is touched (no button of a song, a playlist or a profile is ever invoked).
#  - Measured 2026-10-10 on what empties the box: the "empty" button and then home emptied the text a case had left;
#    home alone did NOT empty a text set through ValuePattern with the keyboard elsewhere (the line said
#    no_verificado, as it must); an Escape with the keyboard in the box did. So the box is emptied in that order:
#    its button, the empty value, home. The empty value on this box was not measured live (the turns ran out).
#  - A menu or a drop-down still open after that (a Menu in the tree, or anything that reads as expanded) has no
#    pattern that closes it: ONE Escape, only after reading it open and only with Spotify's exact window in front
#    (Send-EscapeEnFrente). With nothing open no key is ever pressed.
#  - Spotify is never started. Closed, it opens on the home page with an empty box (v2), and the library as it was
#    left: the line says ventana=cerrada. Running without a window (tray) nothing can be read: spotify_sin_ventana.
#  - Read back from the tree: the hidden heading of the main view named like the home button, the value of the search
#    box, and which of the two library buttons is there.
#  - A UIA call on Chromium can bring Spotify to the front: the window that had the foreground gets it back.
if(-not ('EstadoW32' -as [type])){ . (Join-Path $PSScriptRoot 'comun.ps1') }
$E='spotify_inicio'
# Names of the Spanish client (measured) and of the English one. ASCII only (PowerShell 5.1 reads ANSI).
$NInicio=@('Inicio','Home')
$NBuscar=@('Buscar','Search')
$NPlegar=@('Comprimir Tu biblioteca','Collapse Your Library')
$NAbrir=@('Abre Tu biblioteca','Open Your Library')
$NBorrar=@(('Borrar campo de b'+[char]0xFA+'squeda'),'Clear search field')

function Get-SpotifyTop(){
  $p=@(Get-Process -Name Spotify -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne [IntPtr]::Zero })
  if($p.Count -eq 0){ return $null }
  [Windows.Automation.AutomationElement]::FromHandle($p[0].MainWindowHandle)
}

function Find-Typed($W,[Windows.Automation.ControlType]$Type){
  $c=New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::ControlTypeProperty,$Type)
  @($W.FindAll('Descendants',$c))
}

function Read-Spotify($W){
  # @{ inicio; plegar; abrir; borrar (buttons or $null); caja (the top search box); pagina = inicio|otra|no_legible;
  #    busqueda (text or $null); biblioteca = plegada|desplegada|no_legible; abiertos (names of open menus and
  #    expanded controls) }
  $botones=@(Find-Typed $W ([Windows.Automation.ControlType]::Button))
  $inicio=@($botones | Where-Object { $NInicio -ccontains $_.Current.Name })[0]
  $plegar=@($botones | Where-Object { $NPlegar -ccontains $_.Current.Name })[0]
  $abrir=@($botones | Where-Object { $NAbrir -ccontains $_.Current.Name })[0]
  # The top search box: the ComboBox that shares its group with the "Buscar" button (the library has its own box).
  $caja=$null; $borrar=$null
  $tw=[Windows.Automation.TreeWalker]::ControlViewWalker
  $cb=New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::ControlTypeProperty,[Windows.Automation.ControlType]::ComboBox)
  foreach($b in @($botones | Where-Object { $NBuscar -ccontains $_.Current.Name })){
    $grupo=$tw.GetParent($b); $caja=$grupo.FindFirst('Children',$cb)
    if($caja){
      $bt=New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::ControlTypeProperty,[Windows.Automation.ControlType]::Button)
      $borrar=@($grupo.FindAll('Children',$bt) | Where-Object { $NBorrar -ccontains $_.Current.Name })[0]
      break
    }
  }
  $pagina='no_legible'
  if($inicio){
    # The main view of the home page starts with a heading (a Text) named like the home button; no other page has it.
    $n=[string]$inicio.Current.Name
    $pagina=if(@(Find-Typed $W ([Windows.Automation.ControlType]::Text) | Where-Object { $_.Current.Name -ceq $n }).Count -gt 0){ 'inicio' }else{ 'otra' }
  }
  $ex=New-Object Windows.Automation.PropertyCondition([Windows.Automation.ExpandCollapsePattern]::ExpandCollapseStateProperty,[Windows.Automation.ExpandCollapseState]::Expanded)
  $abiertos=@(@(Find-Typed $W ([Windows.Automation.ControlType]::Menu)) + @($W.FindAll('Descendants',$ex)) | ForEach-Object { [string]$_.Current.Name })
  $biblioteca=if($plegar){ 'desplegada' }elseif($abrir){ 'plegada' }else{ 'no_legible' }
  [pscustomobject]@{ inicio=$inicio; plegar=$plegar; abrir=$abrir; borrar=$borrar; caja=$caja; pagina=$pagina; busqueda=$(if($caja){ [string](Get-Value $caja) }else{ $null }); biblioteca=$biblioteca; abiertos=$abiertos }
}

function Test-Base($S){ $S.pagina -eq 'inicio' -and $null -ne $S.busqueda -and $S.busqueda -eq '' -and $S.biblioteca -eq 'plegada' -and $S.abiertos.Count -eq 0 }

$w=Get-SpotifyTop
if(-not $w){
  if(@(Get-Process -Name Spotify -ErrorAction SilentlyContinue).Count -gt 0){ Write-Estado $E 'spotify_sin_ventana' @{ verificado=$false; nota='Spotify corre sin ventana (bandeja); no se abre' }; return }
  Write-Estado $E 'ok' @{ verificado=$true; ventana='cerrada'; nota='Spotify cerrado: abre en Inicio con el buscador vacio; la biblioteca, como quedo' }; return
}
$h=[IntPtr]$w.Current.NativeWindowHandle
$a=Read-Spotify $w
if(Test-Base $a){ Write-Estado $E 'ok' @{ verificado=$true; ventana='abierta'; pagina=$a.pagina; busqueda=$a.busqueda; biblioteca=$a.biblioteca; abiertos=@() }; return }
$fg=Get-Foreground
$pasos=@()
$s=$a
try{
  if($s.busqueda -and $s.borrar){
    $pasos+="borrar:$(Invoke-Element $s.borrar)"
    for($i=0;$i -lt 4;$i++){ Start-Sleep -Milliseconds 150; $s=Read-Spotify $w; if(-not $s.busqueda){ break } }
  }
  if($s.busqueda -and $s.caja){
    $s.caja.GetCurrentPattern([Windows.Automation.ValuePattern]::Pattern).SetValue(''); $pasos+='vaciar:valor'
    for($i=0;$i -lt 8;$i++){ Start-Sleep -Milliseconds 150; $s=Read-Spotify $w; if(-not $s.busqueda){ break } }
  }
  # Then home: it takes the keyboard out of the box, which folds the box's drop-down.
  if(($s.pagina -ne 'inicio' -or $s.busqueda -or $s.abiertos.Count -gt 0) -and $s.inicio){
    $pasos+="inicio:$(Invoke-Element $s.inicio)"
    for($i=0;$i -lt 12;$i++){ Start-Sleep -Milliseconds 150; $s=Read-Spotify $w; if($s.pagina -eq 'inicio' -and -not $s.busqueda -and $s.abiertos.Count -eq 0){ break } }
  }
  if($s.plegar){
    $pasos+="plegar:$(Invoke-Element $s.plegar)"
    for($i=0;$i -lt 12;$i++){ Start-Sleep -Milliseconds 150; $s=Read-Spotify $w; if($s.biblioteca -eq 'plegada'){ break } }
  }
  # What is still open after that (a menu) only a key closes.
  if($s.abiertos.Count -gt 0){
    $pasos+="abiertos:$(Send-EscapeEnFrente $h)"
    for($i=0;$i -lt 8;$i++){ Start-Sleep -Milliseconds 150; $s=Read-Spotify $w; if($s.abiertos.Count -eq 0){ break } }
  }
}catch{ $pasos+="error:$($_.Exception.Message)" }
$s=Read-Spotify $w
$ok=[bool](Test-Base $s)
$foco=Restore-Foreground $fg @('Spotify')
Write-Estado $E ($(if($ok){'corregido'}else{'no_verificado'})) @{ verificado=$ok; ventana='abierta'; pagina_antes=$a.pagina; pagina=$s.pagina; busqueda_antes=$a.busqueda; busqueda=$s.busqueda; biblioteca_antes=$a.biblioteca; biblioteca=$s.biblioteca; abiertos_antes=@($a.abiertos); abiertos=@($s.abiertos); pasos=$pasos; foco=$foco }
