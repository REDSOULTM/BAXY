# State config_busqueda_vacia: the Settings search box is empty (y9 "buscá mouse" leaves the word in it).
# A closed Settings opens with an empty box, so it is not opened. An open one is emptied by ValuePattern, no typing.
if(-not ('EstadoW32' -as [type])){ . (Join-Path $PSScriptRoot 'comun.ps1') }
$E='config_busqueda_vacia'
$fg=Get-Foreground
$wins=@(Find-TopWindowByName $global:EstadoTituloConfig)
if($wins.Count -eq 0){ Write-Estado $E 'ok' @{ verificado=$true; ventana='cerrada'; nota='Configuracion cerrada: abre con el buscador vacio' }; return }
$out=@()
foreach($w in $wins){
  $box=Find-ById $w 'CommandSearchTextBox'
  if(-not $box){ $out+=[pscustomobject]@{ hwnd=$w.Current.NativeWindowHandle; antes=$null; despues=$null; ok=$false }; continue }
  $antes=Get-Value $box
  if($antes){ $box.GetCurrentPattern([Windows.Automation.ValuePattern]::Pattern).SetValue(''); Start-Sleep -Milliseconds 300 }
  $despues=Get-Value $box
  $out+=[pscustomobject]@{ hwnd=$w.Current.NativeWindowHandle; antes=$antes; despues=$despues; ok=[string]::IsNullOrEmpty($despues) }
}
$ok=@($out | Where-Object { -not $_.ok }).Count -eq 0
$cambio=@($out | Where-Object { $_.antes }).Count -gt 0
$r=if(-not $ok){ 'no_verificado' }elseif($cambio){ 'corregido' }else{ 'ok' }
# A pattern call can bring Settings to the front (measured): the person's window gets the foreground back.
$foco=Restore-Foreground $fg @('ApplicationFrameHost','SystemSettings')
Write-Estado $E $r @{ verificado=$ok; ventana='abierta'; foco=$foco; texto_antes=@($out | ForEach-Object { $_.antes }); texto=@($out | ForEach-Object { $_.despues }) }
