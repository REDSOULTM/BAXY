# State config_inicio: an open Settings window is back on its home page ("Inicio"), so a case that goes to a section
# never starts already there (s03 once passed as "ya estaba en esa página"). A closed Settings opens on Inicio and is
# left closed. The nav item is selected with SelectionItemPattern: no click, no focus.
if(-not ('EstadoW32' -as [type])){ . (Join-Path $PSScriptRoot 'comun.ps1') }
$E='config_inicio'
$fg=Get-Foreground
$wins=@(Find-TopWindowByName $global:EstadoTituloConfig)
if($wins.Count -eq 0){ Write-Estado $E 'ok' @{ verificado=$true; ventana='cerrada'; nota='Configuracion cerrada: abre en Inicio' }; return }

function Get-NavHome($W){
  # The first item of the permanent navigation list is the home page (Inicio / Home).
  $host_=Find-ById $W 'MenuItemsHost'; if(-not $host_){ return $null }
  $c=New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::ControlTypeProperty,[Windows.Automation.ControlType]::ListItem)
  $host_.FindFirst('Children',$c)
}

$out=@()
foreach($w in $wins){
  $home_=Get-NavHome $w
  if(-not $home_){ $out+=[pscustomobject]@{ antes=$null; despues=$null; ok=$false }; continue }
  $antes=@(Get-Selected (Find-ById $w 'MenuItemsHost')) -join ','
  $p=$home_.GetCurrentPattern([Windows.Automation.SelectionItemPattern]::Pattern)
  if(-not $p.Current.IsSelected -or $antes -ne $home_.Current.Name){ $p.Select(); for($i=0;$i -lt 15 -and -not $p.Current.IsSelected;$i++){ Start-Sleep -Milliseconds 150 }; Start-Sleep -Milliseconds 300 }
  # Read back: the selected nav item and the breadcrumb both say Inicio.
  $sel=@(Get-Selected (Find-ById $w 'MenuItemsHost')) -join ','
  $crumb=$null; $bc=Find-ById $w 'PermanentNavigationViewBreadcrumbBar'
  if($bc){ $t=$bc.FindAll('Descendants',(New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::ControlTypeProperty,[Windows.Automation.ControlType]::Text))); $crumb=@($t | ForEach-Object { $_.Current.Name }) -join ' > ' }
  $out+=[pscustomobject]@{ antes=$antes; despues=$sel; miga=$crumb; ok=($sel -eq $home_.Current.Name -and $crumb -eq $home_.Current.Name) }
}
$ok=@($out | Where-Object { -not $_.ok }).Count -eq 0
$cambio=@($out | Where-Object { $_.antes -ne $_.despues }).Count -gt 0
$r=if(-not $ok){ 'no_verificado' }elseif($cambio){ 'corregido' }else{ 'ok' }
# A pattern call can bring Settings to the front (measured): the person's window gets the foreground back.
$foco=Restore-Foreground $fg @('ApplicationFrameHost','SystemSettings')
Write-Estado $E $r @{ verificado=$ok; ventana='abierta'; foco=$foco; pagina_antes=@($out | ForEach-Object { $_.antes }); pagina=@($out | ForEach-Object { $_.despues }); miga=@($out | ForEach-Object { $_.miga }) }
