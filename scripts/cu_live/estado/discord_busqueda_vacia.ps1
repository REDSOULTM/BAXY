# State discord_busqueda_vacia: neither of Discord's two searches holds what an earlier case left: the message search
# box of the chat shown is empty (its results panel closed) and the place selector ("Cambio Rapido", Ctrl+K) is not
# open. Why (banco c24b/c25, s11 c7 s13): the first read of the case already had "cotele" in the message search box
# and the selector open with the keyboard, so the case was measured over leftovers. It goes AFTER discord_md, which
# picks the chat: this state never changes it. Harness only, never product code.
#  - The box is the ComboBox named "Buscar <chat>", never the message composer (an Edit, never read nor touched).
#    First the app's own button, the one right after the box that exists only while a search is shown ("Borrar"),
#    through UIA Invoke: it closes the results panel but leaves the words in the box (measured 2026-10-10). Then the
#    box itself is set to the empty text through ValuePattern, as config_busqueda_vacia does. No text is ever
#    written, nothing is sent, no chat, channel or call is invoked.
#  - The selector, and the box's own drop-down when it stays unfolded, have no button and no pattern that closes
#    them: ONE Escape each, only after reading it open in the tree and only with Discord's exact window in front
#    (Send-EscapeEnFrente, the rule of discord_escape.ps1). Escape closes that layer and nothing else; with nothing
#    open no key is ever pressed.
#  - Discord is never started: without its window the line says discord_no_abierto (verificado=false).
#  - Read back from the tree: the value of the box, the button gone, the box folded, no selector. Any other dialog over Discord is
#    named in the line (dialogos) and left alone.
#  - The window that had the foreground gets it back.
if(-not ('EstadoW32' -as [type])){ . (Join-Path $PSScriptRoot 'comun.ps1') }
$E='discord_busqueda_vacia'
# Names of the Spanish client (measured) and of the English one. ASCII only (PowerShell 5.1 reads ANSI).
$NBuscar=@('Buscar','Search')
$NBorrar=@('Borrar','Clear','Clear search')

function Find-Typed($W,[Windows.Automation.ControlType]$Type){
  $c=New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::ControlTypeProperty,$Type)
  @($W.FindAll('Descendants',$c))
}

function Read-Discord($W){
  # @{ caja; texto (trimmed value or $null without a box); boton (the box's own "empty" button or $null);
  #    desplegada (the box's drop-down is open); selector (search dialogs open); dialogos (names of any other dialog) }
  $caja=@(Find-Typed $W ([Windows.Automation.ControlType]::ComboBox) | Where-Object {
      $n=[string]$_.Current.Name
      @($NBuscar | Where-Object { $n -ceq $_ -or $n.StartsWith("$_ ") }).Count -gt 0
    })[0]
  $texto=$null; $boton=$null; $desplegada=$false
  if($caja){
    $x=$null
    if($caja.TryGetCurrentPattern([Windows.Automation.ExpandCollapsePattern]::Pattern,[ref]$x)){ $desplegada=($x.Current.ExpandCollapseState -ne [Windows.Automation.ExpandCollapseState]::Collapsed) }
    # A rich-text box may report a lone line break or a zero-width mark when empty.
    $texto=([string](Get-Value $caja)) -replace '[\s\u200B\uFEFF]',''
    $sig=[Windows.Automation.TreeWalker]::ControlViewWalker.GetNextSibling($caja)
    if($sig -and $sig.Current.ControlType -eq [Windows.Automation.ControlType]::Button -and $NBorrar -ccontains $sig.Current.Name){ $boton=$sig }
  }
  # A dialog whose own search box carries the dialog's name is the place selector.
  $selector=@(); $otros=@()
  foreach($d in @(Find-Typed $W ([Windows.Automation.ControlType]::Window))){
    $n=[string]$d.Current.Name
    if($n -and @(Find-Typed $d ([Windows.Automation.ControlType]::ComboBox) | Where-Object { $_.Current.Name -ceq $n }).Count -gt 0){ $selector+=$d }else{ $otros+=$n }
  }
  [pscustomobject]@{ caja=$caja; texto=$texto; boton=$boton; desplegada=$desplegada; selector=$selector; dialogos=$otros }
}

function Test-Base($S){ $null -ne $S.caja -and $S.texto -eq '' -and -not $S.boton -and -not $S.desplegada -and $S.selector.Count -eq 0 }

$p=@(Get-Process -Name Discord -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne [IntPtr]::Zero })
if($p.Count -eq 0){ Write-Estado $E 'discord_no_abierto' @{ verificado=$false; nota='Discord no se abre desde el arnes' }; return }
$h=$p[0].MainWindowHandle
$w=[Windows.Automation.AutomationElement]::FromHandle($h)
$a=Read-Discord $w
if(Test-Base $a){ Write-Estado $E 'ok' @{ verificado=$true; texto=$a.texto; selector=$false; dialogos=@($a.dialogos); titulo=[string]$w.Current.Name }; return }
$fg=Get-Foreground
$pasos=@()
$s=$a
try{
  # Up to three Escapes while the selector still reads open (banco h1/h2: after s11/c7 typed in it, one Escape left it
  # open and c6 ran over it); each one only with Discord in front and after reading the layer open again.
  for($r=0;$r -lt 3 -and $s.selector.Count -gt 0;$r++){
    $pasos+="selector:$(Send-EscapeEnFrente $h)"
    for($i=0;$i -lt 20;$i++){ Start-Sleep -Milliseconds 150; $s=Read-Discord $w; if($s.selector.Count -eq 0){ break } }
  }
  if($s.boton){
    $pasos+="borrar:$(Invoke-Element $s.boton)"
    for($i=0;$i -lt 20;$i++){ Start-Sleep -Milliseconds 150; $s=Read-Discord $w; if(-not $s.boton){ break } }
  }
  if($s.caja -and $s.texto){
    $s.caja.GetCurrentPattern([Windows.Automation.ValuePattern]::Pattern).SetValue(''); $pasos+='vaciar:valor'
    for($i=0;$i -lt 20;$i++){ Start-Sleep -Milliseconds 150; $s=Read-Discord $w; if($s.texto -eq ''){ break } }
  }
  if($s.desplegada){
    $pasos+="desplegable:$(Send-EscapeEnFrente $h)"
    for($i=0;$i -lt 20;$i++){ Start-Sleep -Milliseconds 150; $s=Read-Discord $w; if(-not $s.desplegada){ break } }
  }
}catch{ $pasos+="error:$($_.Exception.Message)" }
$s=Read-Discord $w
$ok=[bool](Test-Base $s)
$foco=Restore-Foreground $fg @('Discord')
# Words the box would not let go, or a layer that stayed open (Discord could not be brought to the front): nothing
# else is tried.
Write-Estado $E ($(if($ok){'corregido'}else{'no_verificado'})) @{ verificado=$ok; texto_antes=$a.texto; texto=$s.texto; selector_antes=($a.selector.Count -gt 0); selector=($s.selector.Count -gt 0); desplegada=[bool]$s.desplegada; dialogos=@($s.dialogos); pasos=$pasos; foco=$foco; titulo=[string]$w.Current.Name }
