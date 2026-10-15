# Frame windows of packaged apps (ApplicationFrameHost: Settings, Calculator, Clock, Store...) around one case; used by
# batch.sh, not a state. ApplicationFrameHost is ONE process for every frame, so its MainWindowTitle names only one of
# them: a Settings window a case left next to a Calculator was never seen as new and stayed for the next cases (r4a:
# Settings covering Steam in g1, "ya estaba abierta" in v11). Every frame is listed and closed by its exact HWND.
#   marcos.ps1 -Listar                                   HWNDs of the visible titled frames now, space separated
#   marcos.ps1 -CerrarNuevos -Antes "h1 h2" -Libro <case photo> [-Pendientes <file>]
#        closes (WindowPattern, a normal close) the frames that are not in -Antes, reads them back, and writes the ones
#        that survived to -Pendientes, so the next case retries them before its states. ApplicationFrameHost is a
#        process of the person, so a new frame follows the ledger's rule for a new window in a process of the person
#        (Get-DecisionVentanaNueva): it is closed only when the owner-input record (CU_REGISTRO) covers the whole case,
#        from the photo -Libro was taken to now, with no input of the person. Otherwise it may be the person's own
#        Calculator or Settings: it is only reported (sin_tocar), never closed and never written to -Pendientes.
#        Without -Libro or without the record the person counts as active (fail closed).
#   marcos.ps1 -Reintentar -Pendientes <file>             closes the frames still alive from that file; empties it.
# Never VS Code, Opera or a title under 4 characters (Close-WindowExact). Prints one JSON line.
param([switch]$Listar,[switch]$CerrarNuevos,[switch]$Reintentar,[string]$Antes='',[string]$Pendientes='',[string]$Libro='')
. (Join-Path $PSScriptRoot 'estado\comun.ps1')
. (Join-Path $PSScriptRoot 'estado\apps_comun.ps1')
. (Join-Path $PSScriptRoot 'estado\decisiones_comun.ps1')

function Get-Marcos(){
  $out=@()
  foreach($p in @(Get-Process ApplicationFrameHost -ErrorAction SilentlyContinue)){
    $c=New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::ProcessIdProperty,[int]$p.Id)
    foreach($w in [Windows.Automation.AutomationElement]::RootElement.FindAll('Children',$c)){
      try{
        $h=[long]$w.Current.NativeWindowHandle
        if($h -ne 0 -and [EstadoW32]::IsWindowVisible([IntPtr]$h) -and -not [string]::IsNullOrWhiteSpace($w.Current.Name)){ $out+=$w }
      }catch{}
    }
  }
  $out
}

function Close-Marcos([long[]]$Hwnds){
  # Returns @{ cerradas; sobreviven } after reading every frame back.
  $cerradas=@(); $fallos=@()
  foreach($h in $Hwnds){
    if(-not [EstadoW32]::IsWindow([IntPtr]$h)){ continue }
    try{ Close-WindowExact ([Windows.Automation.AutomationElement]::FromHandle([IntPtr]$h)); $cerradas+=$h }catch{ $fallos+=$h }
  }
  # Read back once they are gone (at most 1.5 s), not after a fixed 600 ms: nothing asked to close, nothing to wait for.
  $pedidas=@($cerradas+$fallos)
  $fin=(Get-Date).AddMilliseconds(1500)
  while($pedidas.Count -and (Get-Date) -lt $fin -and @($pedidas | Where-Object { [EstadoW32]::IsWindow([IntPtr]$_) -and [EstadoW32]::IsWindowVisible([IntPtr]$_) }).Count){ Start-Sleep -Milliseconds 100 }
  $sobreviven=@(@($cerradas+$fallos) | Where-Object { [EstadoW32]::IsWindow([IntPtr]$_) -and [EstadoW32]::IsWindowVisible([IntPtr]$_) })
  @{ cerradas=@($cerradas | Where-Object { $sobreviven -notcontains $_ }); sobreviven=$sobreviven }
}

function Write-Pendientes([long[]]$Hwnds){
  if(-not $Pendientes){ return }
  $d=Split-Path $Pendientes; if($d -and -not (Test-Path $d)){ New-Item -ItemType Directory -Force $d | Out-Null }
  [IO.File]::WriteAllText($Pendientes,((@($Hwnds) -join ' ')+"`n"),(New-Object Text.UTF8Encoding $false))
}

if($Listar){ (@(Get-Marcos | ForEach-Object { [long]$_.Current.NativeWindowHandle } | Sort-Object -Unique) -join ' '); return }
if($CerrarNuevos){
  $previas=@($Antes -split '\s+' | Where-Object { $_ } | ForEach-Object { [long]$_ })
  $nuevas=@(Get-Marcos | Where-Object { $previas -notcontains [long]$_.Current.NativeWindowHandle })
  $titulos=@($nuevas | ForEach-Object { $_.Current.Name })
  # The person's idleness over the case, from the case photo to now (the ledger's rule, fail closed).
  $quieto=$false
  if($Libro -and (Test-Path -LiteralPath $Libro)){
    try{
      $foto=[IO.File]::ReadAllText($Libro,[Text.Encoding]::UTF8) | ConvertFrom-Json
      $hasta=Get-EpochAhora
      if($foto.hora_epoch){ $quieto=[bool](Get-DecisionDuenoQuieto (Get-RegistroDueno $hasta) ([double]$foto.hora_epoch) $hasta) }
    }catch{ $quieto=$false }
  }
  $decision=Get-DecisionVentanaNueva 'dueno' (-not $quieto) $false $false
  $aCerrar=@(); $sinTocar=@()
  foreach($w in $nuevas){ if($decision -eq 'cerrar_ventana'){ $aCerrar+=[long]$w.Current.NativeWindowHandle }else{ $sinTocar+=[long]$w.Current.NativeWindowHandle } }
  $r=Close-Marcos $aCerrar
  if($r.sobreviven.Count){
    $ya=@(); if($Pendientes -and (Test-Path -LiteralPath $Pendientes)){ $ya=@(([IO.File]::ReadAllText($Pendientes) -split '\s+') | Where-Object { $_ } | ForEach-Object { [long]$_ }) }
    Write-Pendientes @(@($ya)+@($r.sobreviven) | Select-Object -Unique)
  }
  Write-Estado 'marcos_nuevos' 'ok' @{ verificado=($r.sobreviven.Count -eq 0); titulos=$titulos; cerradas=$r.cerradas; sobreviven=$r.sobreviven
    sin_tocar=$sinTocar; dueno_activo=(-not $quieto) }
  return
}
if($Reintentar){
  $h=@()
  if($Pendientes -and (Test-Path -LiteralPath $Pendientes)){ $h=@(([IO.File]::ReadAllText($Pendientes) -split '\s+') | Where-Object { $_ } | ForEach-Object { [long]$_ }) }
  # Only frames still alive AND still frames (a recycled HWND of another program is never closed).
  $vivas=@(Get-Marcos | ForEach-Object { [long]$_.Current.NativeWindowHandle })
  $r=Close-Marcos @($h | Where-Object { $vivas -contains $_ })
  Write-Pendientes $r.sobreviven
  Write-Estado 'marcos_pendientes' 'ok' @{ verificado=($r.sobreviven.Count -eq 0); cerradas=$r.cerradas; sobreviven=$r.sobreviven }
}
