# Explorer windows around one case (used by batch.sh; not a state).
#   exploradores.ps1 -Listar                 the HWNDs of the Explorer windows open now, space separated
#   exploradores.ps1 -CerrarNuevos -Antes "h1 h2" -Libro <case photo>
#        closes, by exact HWND, the Explorer windows that appeared during the case AND show one of the test places
#        (Descargas, Documentos, Imágenes, Música, Escritorio, Este equipo, Inicio, Panel de control). Explorer is a
#        process of the person, so a new window follows the ledger's rule for a new window in a process of the person
#        (Get-DecisionVentanaNueva, like marcos.ps1): it is closed only when the owner-input record (CU_REGISTRO)
#        covers the whole case, from the photo -Libro was taken to now, with no input of the person. Otherwise it may
#        be the person's own Documentos (review r10a): it is only reported (sin_tocar). Without -Libro or without the
#        record the person counts as active (fail closed). A window the person opens meanwhile somewhere else is left
#        alone; one listed in -Antes is never closed.
#        Positive provenance first (pasada r18, v3-43): a new window whose hwnd a completed app.open of BAXY's mission
#        journal (-Journal or CU_JOURNAL, from the photo on) returned as the window it opened is the batch's, wherever
#        it shows and whatever the person did meanwhile: it is closed by that exact window (Get-VentanasAbiertasPorBaxy,
#        Get-DecisionExploradorNuevo). A window BAXY only looked at or reused is not; without the journal nothing is.
#        One that does not go is added to the batch ledger's ventanas_lote (CU_LIBRO): sin_restos retries it before the
#        next case and app_cerrada does not take it for the person's (sobreviven, verificado=false).
#   exploradores.ps1 -Limpiar                closes the harness's own Explorer windows (propios.jsonl) at the end.
param([switch]$Listar,[switch]$CerrarNuevos,[string]$Antes='',[switch]$Limpiar,[string]$Libro='',[string]$Journal='')
. (Join-Path $PSScriptRoot 'comun.ps1')
. (Join-Path $PSScriptRoot 'explorador_comun.ps1')
$ws=Get-ShellExplorerWindows
if($Listar){ (@($ws | ForEach-Object { [long]$_.HWND } | Sort-Object -Unique) -join ' '); return }
if($CerrarNuevos){
  . (Join-Path $PSScriptRoot 'apps_comun.ps1')
  . (Join-Path $PSScriptRoot 'decisiones_comun.ps1')
  $sh=New-Object -ComObject Shell.Application
  $lugares=@('shell:Downloads','shell:Personal','shell:My Pictures','shell:My Music','shell:Desktop','shell:MyComputerFolder','shell:ControlPanelFolder') | ForEach-Object { try{ $sh.NameSpace($_).Self.Path }catch{} }
  $previas=@($Antes -split '\s+' | Where-Object { $_ } | ForEach-Object { [long]$_ })
  # The person's idleness over the case, from the case photo to now (the ledger's rule, fail closed).
  $quieto=$false
  # The windows BAXY's app.open opened during the case (its mission journal from the photo on); none without both.
  $deBaxy=@()
  if(-not $Journal -and $env:CU_JOURNAL){ $Journal=$env:CU_JOURNAL }
  if($Libro -and (Test-Path -LiteralPath $Libro)){
    try{
      $foto=[IO.File]::ReadAllText($Libro,[Text.Encoding]::UTF8) | ConvertFrom-Json
      $hasta=Get-EpochAhora
      if($foto.hora_epoch){ $quieto=[bool](Get-DecisionDuenoQuieto (Get-RegistroDueno $hasta) ([double]$foto.hora_epoch) $hasta) }
      if($foto.hora_epoch -and $Journal){ $deBaxy=@(Get-VentanasAbiertasPorBaxy (Read-ColaJournal $Journal) ([double]$foto.hora_epoch)) }
    }catch{ $quieto=$false }
  }
  $decision=Get-DecisionVentanaNueva 'dueno' (-not $quieto) $false $false
  $cerradas=@(); $sinTocar=@(); $deProcedencia=@()
  foreach($w in $ws){
    $h=[long]$w.HWND
    if($previas -contains $h){ continue }
    $path=Get-ShellPath $w
    # Home ("Inicio") has no file-system path; its shell id is the only form it takes.
    $lugar=[bool]($lugares -contains $path -or $path -match '^::\{F874310E-B6B7-47DC-BC84-B9E6B38F5903\}$' -or $path -like '::{26EE0668-A00A-44D7-9371-BEB064C98683}*')
    $d=Get-DecisionExploradorNuevo $h $previas $lugar $quieto $deBaxy
    if($d -eq 'cerrar_procedencia'){ try{ $w.Quit() }catch{}; $cerradas+=$h; $deProcedencia+=$h; continue }
    if($lugar){
      if($decision -eq 'cerrar_ventana'){ $w.Quit(); $cerradas+=$h }else{ $sinTocar+=$h }
    }
  }
  # Read back the windows closed by provenance: one still there goes to the batch ledger (sin_restos retries it).
  $sobreviven=@()
  if($deProcedencia.Count){
    $fin=(Get-Date).AddSeconds(3)
    do{
      $sobreviven=@($deProcedencia | Where-Object { [EstadoW32]::IsWindow([IntPtr][long]$_) })
      if(-not $sobreviven.Count){ break }
      Start-Sleep -Milliseconds 200
    }while((Get-Date) -lt $fin)
    if($sobreviven.Count){ [void](Add-VentanasLote $sobreviven) }
  }
  Write-Estado 'exploradores_nuevos' $(if($sobreviven.Count){ 'no_verificado' }else{ 'ok' }) @{ verificado=($sobreviven.Count -eq 0); cerradas=$cerradas; sin_tocar=$sinTocar; dueno_activo=(-not $quieto)
    de_baxy=$deProcedencia; sobreviven=$sobreviven }
  return
}
if($Limpiar){
  $vivas=@($ws | ForEach-Object { [long]$_.HWND })
  $mias=@(Get-Propios | Where-Object { $_.tipo -eq 'explorador' })
  $cerradas=@()
  foreach($m in $mias){ foreach($w in @($ws | Where-Object { [long]$_.HWND -eq [long]$m.hwnd })){ $w.Quit(); $cerradas+=[long]$m.hwnd } }
  Set-Propios @(Get-Propios | Where-Object { $_.tipo -ne 'explorador' })
  Write-Estado 'limpieza_arnes' 'ok' @{ verificado=$true; cerradas=$cerradas }
}
