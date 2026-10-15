param([string]$Arg='')
# State discord_md:<name>: Discord showing the direct-message chat with <name> (s11, s13, c7 start from @Ron92, so
# "go to the Cotele channel" always has to navigate: in the base s11 passed with 0 steps because Discord was already
# there, and in r2 it started on @Ron92 because no state fixed it). Harness only, never product code.
#  - Only navigation through UIA patterns: the "Direct Messages" item of the server list and the chat's link in the
#    DM list are invoked; nothing is typed, nothing is clicked, nothing is sent. A voice channel is never invoked
#    (that would join it).
#  - Discord is never started: without its window the line says discord_no_abierto (verificado=false).
#  - Read back by the window title ("@<name> - Discord") and the conversation document named "@<name>".
#  - A UIA call on Chromium can bring Discord to the front: the window that had the foreground gets it back.
if(-not ('EstadoW32' -as [type])){ . (Join-Path $PSScriptRoot 'comun.ps1') }
$E="discord_md:$Arg"
if(-not $Arg){ Write-Estado $E 'sin_argumento' @{ verificado=$false }; return }
# Names Discord gives the server-list home item (Spanish and English clients). ASCII only (PowerShell 5.1 reads ANSI).
$Inicio=@('Mensajes directos','Direct Messages')
$Objetivo="@$Arg - Discord"

function Get-DiscordTop(){
  $p=@(Get-Process Discord -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne [IntPtr]::Zero })
  if($p.Count -eq 0){ return $null }
  [Windows.Automation.AutomationElement]::FromHandle($p[0].MainWindowHandle)
}

function Find-Typed($W,[Windows.Automation.ControlType]$Type){
  $c=New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::ControlTypeProperty,$Type)
  @($W.FindAll('Descendants',$c))
}

function Find-DmLink($W){
  # The DM list link of that person: "<name> (mensaje directo)" / "<name> (direct message)"; a voice channel never.
  @(Find-Typed $W ([Windows.Automation.ControlType]::Hyperlink) | Where-Object {
      $n=[string]$_.Current.Name
      $n.StartsWith("$Arg (") -and $n -notmatch 'voz|voice'
    })[0]
}

function Test-EnMd($W){
  $doc=@(Find-Typed $W ([Windows.Automation.ControlType]::Document) | Where-Object { $_.Current.Name -eq "@$Arg" })
  # An unread count may prefix the title: "(1) @Ron92 - Discord".
  ([string]$W.Current.Name).EndsWith($Objetivo) -and $doc.Count -gt 0
}

$w=Get-DiscordTop
if(-not $w){ Write-Estado $E 'discord_no_abierto' @{ verificado=$false; nota='Discord no se abre desde el arnes' }; return }
$antes=[string]$w.Current.Name
if(Test-EnMd $w){ Write-Estado $E 'ok' @{ verificado=$true; titulo_antes=$antes; titulo=$antes }; return }
$fg=Get-Foreground
$pasos=@()
try{
  $link=Find-DmLink $w
  if(-not $link){
    # In a server the DM list is not rendered: the server list's home item shows it first.
    $home_=@(Find-Typed $w ([Windows.Automation.ControlType]::TreeItem) | Where-Object { $Inicio -contains $_.Current.Name })[0]
    if($home_){ $pasos+="inicio:$(Invoke-Element $home_)" }
    for($i=0;$i -lt 20 -and -not $link;$i++){ Start-Sleep -Milliseconds 150; $link=Find-DmLink $w }
  }
  if($link){ $pasos+="md:$(Invoke-Element $link)" }
  for($i=0;$i -lt 25 -and -not (Test-EnMd $w);$i++){ Start-Sleep -Milliseconds 120 }
}catch{ $pasos+="error:$($_.Exception.Message)" }
$ok=Test-EnMd $w
$foco=Restore-Foreground $fg @('Discord')
# Without the home item or the link (a settings layer over the client, or no such chat) nothing else is tried.
Write-Estado $E ($(if($ok){'corregido'}else{'no_verificado'})) @{ verificado=$ok; titulo_antes=$antes; titulo=[string]$w.Current.Name; pasos=$pasos; foco=$foco }
