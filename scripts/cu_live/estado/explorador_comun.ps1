# Explorer helpers for the harness states. Dot-source after comun.ps1.
# The harness keeps ONE Explorer window of its own (its HWND is in propios.json) and moves it with Navigate2, which
# neither activates it nor touches the input. Explorer windows it did not open (the person's) are never navigated
# or closed. A new window is opened with "explorer /n" (a window of its own, never a tab in someone else's window).

function Get-IndicesShellQueResponden([int]$TopeMs=3000){
  # Indexes of the Shell windows (Shell.Application.Windows()) whose host process answers a COM call. Each read runs on
  # a thread of its own (STA runspace): one that does not move in $TopeMs is abandoned (it stays blocked until that
  # process ends) and the next index goes on in a new thread. @{ buenos=[int[]]; colgados=[int[]] }.
  $sync=[hashtable]::Synchronized(@{ i=-1; buenos=(New-Object Collections.ArrayList) })
  $desde=0; $malos=@()
  for($intento=0;$intento -lt 6;$intento++){
    $rs=[runspacefactory]::CreateRunspace(); $rs.ApartmentState='STA'; $rs.Open()
    $pw=[PowerShell]::Create(); $pw.Runspace=$rs
    [void]$pw.AddScript({ param($s,$desde)
      $ws=(New-Object -ComObject Shell.Application).Windows(); $n=$ws.Count
      for($i=$desde;$i -lt $n;$i++){ $s.i=$i; $x=$ws.Item($i); if($x){ [void]$x.HWND; [void]$x.FullName }; [void]$s.buenos.Add($i) }
      $s.i=[int]::MaxValue }).AddArgument($sync).AddArgument($desde)
    $sync.i=$desde-1
    $h=$pw.BeginInvoke(); $ult=$sync.i; $t=[Diagnostics.Stopwatch]::StartNew()
    while(-not $h.IsCompleted){
      Start-Sleep -Milliseconds 40
      if($sync.i -ne $ult){ $ult=$sync.i; $t.Restart() }elseif($t.ElapsedMilliseconds -gt $TopeMs){ break }
    }
    if($h.IsCompleted){ try{ [void]$pw.EndInvoke($h) }catch{}; $pw.Dispose(); $rs.Dispose(); break }
    # The Shell itself does not answer (no index read): nothing more is asked.
    if($sync.i -lt $desde){ break }
    $malos+=$sync.i; $desde=$sync.i+1
  }
  @{ buenos=@($sync.buenos | ForEach-Object { [int]$_ }); colgados=$malos }
}

function Get-ShellExplorerWindows(){
  # Every property of a Shell window is a COM call into the explorer.exe that hosts it: one that hung (t-menu-1,
  # 2026-10-09: a secondary explorer.exe behind an application error dialog) blocked the caller for good. When an
  # Explorer process has a window that does not answer, only the windows whose host answered a timed read are given.
  $sh=New-Object -ComObject Shell.Application
  $exp=@(Get-Process explorer -ErrorAction SilentlyContinue | ForEach-Object { $_.Id })
  if(@(Get-VentanasColgadas -Pids $exp).Count -eq 0){ return @($sh.Windows() | Where-Object { $_ -and $_.FullName -match '\\explorer\.exe$' }) }
  $ix=Get-IndicesShellQueResponden
  $ws=$sh.Windows()
  @(foreach($i in $ix.buenos){ $x=$ws.Item($i); if($x -and (Test-VentanaResponde ([IntPtr][long]$x.HWND)) -and $x.FullName -match '\\explorer\.exe$'){ $x } })
}

function Get-ShellPath($W){ try{ $W.Document.Folder.Self.Path }catch{ $null } }

function Set-ExplorerAt([string]$Estado,[string]$Target,[string]$Etiqueta){
  # $Target: a shell path ("shell:Downloads", "shell:MyComputerFolder"); $Etiqueta: what the report calls it.
  $sh=New-Object -ComObject Shell.Application
  $want=$sh.NameSpace($Target).Self.Path
  $fg=Get-Foreground
  $hechos=@()
  $todas=Get-ShellExplorerWindows
  $vivas=@($todas | ForEach-Object { [long]$_.HWND })
  # Harness windows still alive; the dead ones leave the list.
  $props=@(Get-Propios)
  $mias=@($props | Where-Object { $_.tipo -eq 'explorador' -and $vivas -contains [long]$_.hwnd })
  $otras=@($props | Where-Object { $_.tipo -ne 'explorador' })
  $win=$null; $antes=$null
  if($mias.Count -gt 0){
    $h=[long]$mias[0].hwnd
    $win=@($todas | Where-Object { [long]$_.HWND -eq $h })[0]
    $antes=Get-ShellPath $win
    # Extra harness windows (never the person's) are closed by their exact HWND.
    foreach($m in @($mias | Select-Object -Skip 1)){
      foreach($x in @($todas | Where-Object { [long]$_.HWND -eq [long]$m.hwnd })){ $x.Quit(); $hechos+="cerrada_extra:$($m.hwnd)" }
    }
    $mias=@($mias[0])
    if($antes -ne $want){ $win.Navigate2($Target); $hechos+='navegada' }
  } else {
    $before=@($todas | ForEach-Object { [long]$_.HWND })
    Start-Process explorer.exe -ArgumentList ('/n,"{0}"' -f $want)
    for($i=0;$i -lt 50 -and -not $win;$i++){
      Start-Sleep -Milliseconds 200
      $win=@(Get-ShellExplorerWindows | Where-Object { $before -notcontains [long]$_.HWND })[0]
    }
    if(-not $win){ Write-Estado $Estado 'no_abre' @{ verificado=$false }; return }
    $mias=@([pscustomobject]@{ tipo='explorador'; pid=0; hwnd=[long]$win.HWND; desde=(Get-Date).ToString('s') })
    $hechos+='abierta_por_el_arnes'
  }
  Set-Propios (@($otras)+@($mias))
  $path=$null
  for($i=0;$i -lt 25;$i++){ $path=Get-ShellPath $win; if($path -eq $want){ break }; Start-Sleep -Milliseconds 200 }
  $titulo=[EstadoW32]::Title([IntPtr][long]$win.HWND)
  $ok=($path -eq $want)
  $foco=Restore-Foreground $fg @('explorer')
  $r=if(-not $ok){ 'no_verificado' }elseif($hechos.Count -eq 0){ 'ok' }else{ 'corregido' }
  Write-Estado $Estado $r @{ verificado=$ok; carpeta=$Etiqueta; ruta=$path; ruta_antes=$antes; ventana=$titulo; hwnd=[long]$win.HWND; hechos=$hechos; foco=$foco }
}
