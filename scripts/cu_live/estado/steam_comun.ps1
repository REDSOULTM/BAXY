# Steam helpers for the harness states. Dot-source after comun.ps1.
# Steam's window (SDL_app + CEF) has no UIA tree (accessibility stays off even after an MSAA request) and ignores POSTED
# mouse and keyboard messages (measured 2026-10-07: tab clicks, Escape and Backspace had no effect). So the page is read
# from the window's own pixels (PrintWindow + local Windows OCR, no network) and changed only through Steam's own URL
# protocol: steam://open/games shows the Library AND empties its search box; steam://store shows the Store.
# The protocol brings Steam to the front, so the foreground goes back to the person's window right after.
# comun.ps1 is loaded only when the caller has not (reloading it resets its OCR state).
if(-not (Get-Command Read-BitmapText -ErrorAction SilentlyContinue)){ . (Join-Path $PSScriptRoot 'comun.ps1') }

function Get-SteamMain(){
  # The visible top-level SDL_app window titled exactly "Steam" of steamwebhelper.
  $ids=@(Get-Process steamwebhelper -ErrorAction SilentlyContinue | ForEach-Object Id)
  if($ids.Count -eq 0){ return $null }
  $found=New-Object Collections.ArrayList
  [void][EstadoW32]::EnumWindows({ param($h,$l)
    $p=0; [void][EstadoW32]::GetWindowThreadProcessId($h,[ref]$p)
    if($ids -contains $p -and [EstadoW32]::IsWindowVisible($h) -and [EstadoW32]::Klass($h) -eq 'SDL_app' -and [EstadoW32]::Title($h) -eq 'Steam'){ [void]$found.Add($h) }
    $true },[IntPtr]::Zero)
  if($found.Count -eq 0){ return $null }
  [IntPtr]$found[0]
}

function Get-WordColor($Bitmap,$Line){
  # Mean colour of the bright pixels inside an OCR box: the selected Steam tab is drawn blue, the others light grey.
  $sr=0;$sg=0;$sb=0;$n=0
  for($x=$Line.x; $x -lt ($Line.x+$Line.w); $x+=2){ for($y=$Line.y; $y -lt ($Line.y+$Line.h); $y+=2){
    if($x -ge $Bitmap.Width -or $y -ge $Bitmap.Height){ continue }
    $c=$Bitmap.GetPixel($x,$y); if(($c.R+$c.G+$c.B) -gt 300){ $sr+=$c.R;$sg+=$c.G;$sb+=$c.B;$n++ }
  } }
  if($n -eq 0){ return $null }
  [pscustomobject]@{ r=[int]($sr/$n); g=[int]($sg/$n); b=[int]($sb/$n) }
}

$script:SteamTabs=@{ tienda=@('TIENDA','STORE'); biblioteca=@('BIBLIOTECA','LIBRARY'); comunidad=@('COMUNIDAD','COMMUNITY') }

function Read-SteamPage([IntPtr]$Top){
  # @{ pagina = tienda|biblioteca|comunidad|desconocida; tabs = @{name=@{x;y;w;h;azul}}; lineas; bitmap }
  if([EstadoW32]::IsIconic($Top)){ return [pscustomobject]@{ pagina='minimizado'; tabs=@{}; lineas=@(); bitmap=$null } }
  $bmp=Get-WindowBitmap $Top
  if(-not $bmp){ return [pscustomobject]@{ pagina='sin_captura'; tabs=@{}; lineas=@(); bitmap=$null } }
  $lines=Read-BitmapText $bmp
  # The tab row sits in the top 120 px; OCR may glue tabs into one line, so locate each word by splitting the line.
  $tabs=@{}
  foreach($l in @($lines | Where-Object { $_.y -lt 120 })){
    $words=$l.text -split '\s+'
    foreach($key in $script:SteamTabs.Keys){
      foreach($alias in $script:SteamTabs[$key]){
        $i=[Array]::IndexOf(@($words | ForEach-Object { ($_ -replace '[^\p{L}]','').ToUpperInvariant() }),$alias)
        if($i -lt 0 -or $tabs.ContainsKey($key)){ continue }
        # Proportional box of the word inside the line (good enough to sample its colour and click its middle).
        $total=($words | Measure-Object -Property Length -Sum).Sum + ($words.Count-1)
        $before=0; for($k=0;$k -lt $i;$k++){ $before+=$words[$k].Length+1 }
        $wx=$l.x+[int]($l.w*$before/$total); $ww=[int]($l.w*$words[$i].Length/$total)
        $box=[pscustomobject]@{ x=$wx; y=$l.y; w=[Math]::Max(8,$ww); h=[Math]::Max(8,$l.h) }
        $col=Get-WordColor $bmp $box
        $azul=$false; if($col){ $azul=($col.b -gt ($col.r+60)) }
        $tabs[$key]=[pscustomobject]@{ x=$box.x; y=$box.y; w=$box.w; h=$box.h; azul=$azul; color=$col }
      }
    }
  }
  $sel=@($tabs.Keys | Where-Object { $tabs[$_].azul })
  $pagina=if($sel.Count -eq 1){ $sel[0] }else{ 'desconocida' }
  [pscustomobject]@{ pagina=$pagina; tabs=$tabs; lineas=$lines; bitmap=$bmp }
}

function Test-SteamSearch($Page){
  # Library search box: 'vacia' | 'con_texto' | 'no_visible'. With text in it, Steam titles the list "Resultados de la búsqueda".
  if($Page.pagina -ne 'biblioteca'){ return 'no_visible' }
  $lim=[int]($Page.bitmap.Width*0.25)
  $side=@($Page.lineas | Where-Object { $_.x -lt $lim -and $_.y -gt 100 -and $_.y -lt 360 })
  if(@($side | Where-Object { $_.text -match 'Resultados de la b.squeda|Search results' }).Count -gt 0){ return 'con_texto' }
  if(@($side | Where-Object { $_.text -match 'Juegos y Software|Games and Software|Juegos|Games|Software' }).Count -gt 0){ return 'vacia' }
  'no_visible'
}

function Invoke-SteamNav([IntPtr]$Top,[string]$Url,[string]$Want,[scriptblock]$Done){
  # Opens a steam:// URL, waits (up to ~6 s) until the page reads as $Want and $Done (if any) holds, gives the
  # foreground back and re-minimizes Steam when it was minimized. Returns @{ page; foco; minimizado }.
  $fg=Get-Foreground
  $min=[EstadoW32]::IsIconic($Top)
  Start-Process $Url
  $page=$null
  for($i=0;$i -lt 12;$i++){
    Start-Sleep -Milliseconds 500
    $page=Read-SteamPage $Top
    if($page.pagina -eq $Want -and (-not $Done -or (& $Done $page))){ break }
  }
  if($min){ [void][EstadoW32]::ShowWindow($Top,7) }   # SW_SHOWMINNOACTIVE: back to how the person left it
  $foco=Restore-Foreground $fg @('steamwebhelper','steam')
  [pscustomobject]@{ page=$page; foco=$foco; minimizado=$min }
}

function Get-SteamOrReport([string]$Estado){
  # The Steam window ([IntPtr]), or else only the state line (a string): Steam is never started by the harness.
  # Steam running in the tray gets its window back through its own protocol (steam://open/main), which changes
  # nothing in the account; the foreground goes back to where it was. Banco r30: g1 and x10 ran on the library
  # filter an earlier case left, because the state could not read or reset a Steam with no window.
  # Banco r23 (x10): the line was followed by 'return $null', so the function gave Object[] (line, null), the caller's
  # '-not $t' was false, Read-SteamPage([IntPtr]$Top) threw and the case ran on a dirty base with that error instead
  # of 'steam_sin_ventana'. The line goes out by Write-Output and the helper ends with a bare return; the caller
  # checks '$t -isnot [IntPtr]' and prints $t (the line) before returning.
  if(@(Get-Process steam -ErrorAction SilentlyContinue).Count -eq 0){ Write-Output (Write-Estado $Estado 'steam_no_abierto' @{ verificado=$false }); return }
  $t=Get-SteamMain
  if(-not $t){
    $fg=Get-Foreground
    Start-Process 'steam://open/main'
    for($i=0;$i -lt 20 -and -not $t;$i++){ Start-Sleep -Milliseconds 500; $t=Get-SteamMain }
    if($t){ [void](Restore-Foreground $fg @('steamwebhelper','steam')) }
  }
  if(-not $t){ Write-Output (Write-Estado $Estado 'steam_sin_ventana' @{ verificado=$false; nota='Steam corre sin ventana y steam://open/main no la trajo' }); return }
  [IntPtr]$t
}
