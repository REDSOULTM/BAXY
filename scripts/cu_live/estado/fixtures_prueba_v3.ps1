# State fixtures_prueba_v3: the file-case fixture folder <Documentos>\baxy-prueba-v3 exactly as below, every file
# GENERATED here (never copied from the person's data):
#   notas.txt, lista.txt   UTF-8, LF
#   foto.png               64x48
#   paisaje.jpg            1920x1080 (landscape) JPEG
#   prueba.png             300x200 (not square)
#   prueba.zip             3 text files (uno.txt, dos.txt, tres.txt)
#   archivo\               empty subfolder
# A valid fixture is left as it is (cases check that an original keeps its modification date); a changed or missing
# one is rewritten. Valid means the exact CONTENT, not just its size: the generators are deterministic, so an image
# must have the bytes generated in memory now, and the zip the expected entries with their exact text (a case that
# wrongly saves a grey filter over paisaje.jpg keeps 1920x1080, and must not pass as the fixture). Inside that folder only these are ever deleted: fixture names, names starting with "baxy-",
# the case outputs in $Salidas, and copies of a fixture ("prueba (1).png", "prueba - copia.png": same extension, name
# starting with the fixture's name). Anything else is reported as "ajenos" and left where it is. Nothing outside the
# folder is touched.
param([string]$Raiz='')
if(-not ('EstadoW32' -as [type])){ . (Join-Path $PSScriptRoot 'comun.ps1') }
Add-Type -AssemblyName System.IO.Compression,System.IO.Compression.FileSystem
if(-not $Raiz){ $Raiz=Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'baxy-prueba-v3' }
$E='fixtures_prueba_v3'
$Textos=[ordered]@{
  'notas.txt'="Notas de prueba de BAXY.`nComprar pan.`nLlamar a Ana a las 5.`n"
  'lista.txt'="leche`npan`nhuevos`n"
}
$Imagenes=[ordered]@{
  'foto.png'=@{ w=64; h=48; fmt='Png' }
  'paisaje.jpg'=@{ w=1920; h=1080; fmt='Jpeg' }
  'prueba.png'=@{ w=300; h=200; fmt='Png' }
}
$Zip=@{ nombre='prueba.zip'; entradas=[ordered]@{ 'uno.txt'="uno`n"; 'dos.txt'="dos`n"; 'tres.txt'="tres`n" } }
# Files the v3 cases create in the folder without the "baxy-" prefix (v3_manifiesto.json: v3-04, v3-33).
$Salidas=@('proyecto-final.pptx','captura-v3.png')
$Fixtures=@($Textos.Keys)+@($Imagenes.Keys)+@($Zip.nombre)
$utf8=New-Object Text.UTF8Encoding $false
$padre=Split-Path $Raiz
if(-not (Test-Path -LiteralPath $padre)){ Write-Estado $E 'sin_documentos' @{ verificado=$false; ruta=$padre }; return }
$hechos=@(); $ajenos=@()

function Test-Copia([string]$Name){
  foreach($f in $Fixtures){
    $stem=[IO.Path]::GetFileNameWithoutExtension($f); $ext=[IO.Path]::GetExtension($f)
    if($Name -ne $f -and $Name.StartsWith($stem,[StringComparison]::OrdinalIgnoreCase) -and [IO.Path]::GetExtension($Name) -eq $ext){ return $true }
  }
  $false
}
function Test-Borrable([string]$Name){ ($Fixtures -contains $Name) -or $Name -like 'baxy-*' -or ($Salidas -contains $Name) -or (Test-Copia $Name) }
function Remove-Dentro([string]$Dir,[bool]$Arriba){
  # Deletes allowed files; a "baxy-*" subfolder only when everything in it is allowed too. Reports the rest.
  foreach($i in @(Get-ChildItem -LiteralPath $Dir -Force)){
    if($i.PSIsContainer){
      if($Arriba -and $i.Name -eq 'archivo'){ Remove-Dentro $i.FullName $false; continue }
      if($i.Name -like 'baxy-*'){
        $malos=@(Get-ChildItem -LiteralPath $i.FullName -Recurse -Force | Where-Object { -not $_.PSIsContainer -and -not (Test-Borrable $_.Name) })
        if($malos.Count -eq 0){ Remove-Item -LiteralPath $i.FullName -Recurse -Force; $script:hechos+="borrada:$($i.Name)" } else { $script:ajenos+=$i.FullName.Substring($Raiz.Length+1) }
        continue
      }
      $script:ajenos+=$i.FullName.Substring($Raiz.Length+1); continue
    }
    if(Test-Borrable $i.Name){
      # Fixtures at the top are checked below; anywhere else (a copy or a moved one) they go.
      if(-not ($Arriba -and $Fixtures -contains $i.Name)){ Remove-Item -LiteralPath $i.FullName -Force; $script:hechos+="borrado:$($i.FullName.Substring($Raiz.Length+1))" }
    } else { $script:ajenos+=$i.FullName.Substring($Raiz.Length+1) }
  }
}

$script:ImagenBytes=@{}
function Get-ImagenBytes($D){
  # A plain synthetic picture: sky over ground with a sun, so a rotation or a grey filter is visible. Generated in
  # memory and deterministic, so a fixture is valid only when its bytes are exactly these (a grey filter saved over
  # paisaje.jpg keeps 1920x1080 but not these bytes).
  $k='{0}x{1}.{2}' -f $D.w,$D.h,$D.fmt
  if(-not $script:ImagenBytes.ContainsKey($k)){
    $b=New-Object Drawing.Bitmap $D.w,$D.h; $g=[Drawing.Graphics]::FromImage($b)
    $g.Clear([Drawing.Color]::FromArgb(40,110,200))
    $g.FillRectangle((New-Object Drawing.SolidBrush ([Drawing.Color]::FromArgb(60,150,60))),0,[int]($D.h*0.65),$D.w,$D.h)
    $r=[int]([Math]::Min($D.w,$D.h)/4); $g.FillEllipse([Drawing.Brushes]::Gold,[int]($D.w*0.1),[int]($D.h*0.1),$r,$r)
    $g.Dispose(); $ms=New-Object IO.MemoryStream; $b.Save($ms,[Drawing.Imaging.ImageFormat]::($D.fmt)); $b.Dispose()
    $script:ImagenBytes[$k]=$ms.ToArray(); $ms.Dispose()
  }
  ,$script:ImagenBytes[$k]
}
function Test-MismosBytes([byte[]]$A,[byte[]]$B){
  if($A.Length -ne $B.Length){ return $false }
  $h=[Security.Cryptography.SHA256]::Create()
  try{ [BitConverter]::ToString($h.ComputeHash($A)) -eq [BitConverter]::ToString($h.ComputeHash($B)) }finally{ $h.Dispose() }
}
function Test-Imagen([string]$P,$D){
  if(-not (Test-Path -LiteralPath $P)){ return $false }
  try{ Test-MismosBytes ([IO.File]::ReadAllBytes($P)) (Get-ImagenBytes $D) }catch{ $false }
}
function New-Imagen([string]$P,$D){ [IO.File]::WriteAllBytes($P,(Get-ImagenBytes $D)) }
function Test-Zip([string]$P){
  # Valid only with exactly the expected entries AND each entry's exact content.
  if(-not (Test-Path -LiteralPath $P)){ return $false }
  $z=$null
  try{
    $z=[IO.Compression.ZipFile]::OpenRead($P)
    $n=@($z.Entries | ForEach-Object { $_.FullName } | Sort-Object)
    if(($n -join '|') -ne ((@($Zip.entradas.Keys) | Sort-Object) -join '|')){ return $false }
    foreach($e in $z.Entries){
      $s=New-Object IO.StreamReader($e.Open(),$utf8); $t=$s.ReadToEnd(); $s.Dispose()
      if($t -cne $Zip.entradas[$e.FullName]){ return $false }
    }
    $true
  }catch{ $false }finally{ if($z){ $z.Dispose() } }
}
function New-Zip([string]$P){
  if(Test-Path -LiteralPath $P){ Remove-Item -LiteralPath $P -Force }
  $z=[IO.Compression.ZipFile]::Open($P,'Create')
  foreach($k in $Zip.entradas.Keys){ $e=$z.CreateEntry($k); $s=New-Object IO.StreamWriter($e.Open(),$utf8); $s.Write($Zip.entradas[$k]); $s.Dispose() }
  $z.Dispose()
}

if(Test-Path -LiteralPath $Raiz){ Remove-Dentro $Raiz $true } else { New-Item -ItemType Directory -Path $Raiz | Out-Null; $hechos+='creada' }
$arch=Join-Path $Raiz 'archivo'; if(-not (Test-Path -LiteralPath $arch)){ New-Item -ItemType Directory -Path $arch | Out-Null; $hechos+='creada:archivo' }

foreach($k in $Textos.Keys){
  $p=Join-Path $Raiz $k
  if(-not (Test-Path -LiteralPath $p) -or [IO.File]::ReadAllText($p) -cne $Textos[$k]){ [IO.File]::WriteAllText($p,$Textos[$k],$utf8); $hechos+="escrito:$k" }
}
foreach($k in $Imagenes.Keys){ $p=Join-Path $Raiz $k; if(-not (Test-Imagen $p $Imagenes[$k])){ New-Imagen $p $Imagenes[$k]; $hechos+="escrito:$k" } }
$zp=Join-Path $Raiz $Zip.nombre; if(-not (Test-Zip $zp)){ New-Zip $zp; $hechos+="escrito:$($Zip.nombre)" }

# Read back.
$ok=$true
foreach($k in $Textos.Keys){ if([IO.File]::ReadAllText((Join-Path $Raiz $k)) -cne $Textos[$k]){ $ok=$false } }
foreach($k in $Imagenes.Keys){ if(-not (Test-Imagen (Join-Path $Raiz $k) $Imagenes[$k])){ $ok=$false } }
if(-not (Test-Zip $zp)){ $ok=$false }
$enArchivo=@(Get-ChildItem -LiteralPath $arch -Force)
if($enArchivo.Count -gt 0 -and @($enArchivo | Where-Object { Test-Borrable $_.Name }).Count -gt 0){ $ok=$false }
$arriba=@(Get-ChildItem -LiteralPath $Raiz -Force | ForEach-Object { $_.Name } | Sort-Object)
$r=if(-not $ok){ 'no_verificado' }elseif($ajenos.Count -gt 0){ 'ajenos_presentes' }elseif($hechos.Count -gt 0){ 'corregido' }else{ 'ok' }
Write-Estado $E $r @{ verificado=($ok -and $ajenos.Count -eq 0); ruta=$Raiz; contenido=$arriba; archivo_vacio=($enArchivo.Count -eq 0); hechos=$hechos; ajenos=$ajenos }
