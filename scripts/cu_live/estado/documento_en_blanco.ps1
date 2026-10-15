# State documento_en_blanco:<PowerPoint|Word|Excel>[|contenido]: that Office app open with ONE new, unsaved, blank
# document ("Presentacion1", "Documento1", "Libro1"), in an instance the harness started.
#  - Built through the app's own COM automation (no keys, no clicks): PowerPoint gets one title slide, like File > New
#    > Blank presentation; Word one empty document; Excel one empty book.
#  - Optional contenido, generic per app: PowerPoint "Uno;Dos;Tres" = one title slide per item with that title;
#    Word "Hola mundo" = that one paragraph (Calibri 11), all of it selected; Excel "a;b;c" = column A from A1.
#  - A copy the harness opened earlier is closed first (its test document is discarded, never saved).
#  - A running copy the harness did not open is the person's: nothing is added to it (ajena_abierta).
param([string]$Arg='')
if(-not ('EstadoW32' -as [type])){ . (Join-Path $PSScriptRoot 'comun.ps1') }
. (Join-Path $PSScriptRoot 'apps_comun.ps1')
$E="documento_en_blanco:$Arg"
$app,$contenido=$Arg -split '\|',2
$def=@{
  'PowerPoint'=@{ prog='PowerPoint.Application'; proc='POWERPNT' }
  'Word'=@{ prog='Word.Application'; proc='WINWORD' }
  'Excel'=@{ prog='Excel.Application'; proc='EXCEL' }
}[$app]
if(-not $def){ Write-Estado $E 'app_desconocida' @{ verificado=$false; nota='PowerPoint, Word o Excel' }; return }
$cerradas=@(Close-AppsPropias $def.proc)
# Inside a batch, a copy an earlier case left (born in the batch, no window of the person) exits first.
$cerradas+=@(Close-ProcesosDelLote $def.proc)
$otros=@(Get-Process -Name $def.proc -ErrorAction SilentlyContinue)
if($otros.Count -gt 0){ Write-Estado $E 'ajena_abierta' @{ verificado=$false; procesos=$otros.Count; cerradas_antes=$cerradas; nota='una copia que el arnes no abrio: no se le agrega nada' }; return }

$fg=Get-Foreground
$hAntes=@((Get-TopWindows) | ForEach-Object { $_.hwnd })
$pAntes=@(Get-Process | ForEach-Object { $_.Id })
$leido=$null; $creado=$null
try{
  $o=New-Object -ComObject $def.prog
  switch($app){
    'PowerPoint' {
      $o.Visible=-1
      $pr=$o.Presentations.Add(-1)
      $titulos=@(if($contenido){ $contenido -split ';' }else{ '' })
      $i=1
      foreach($t in $titulos){
        # ppLayoutTitle=1 for the first slide (what a blank presentation shows), ppLayoutTitleOnly=11 for the rest.
        $s=$pr.Slides.Add($i,$(if($i -eq 1){1}else{11}))
        if($t){ $s.Shapes.Title.TextFrame.TextRange.Text=$t }
        $i++
      }
      $leido=@(foreach($s in $pr.Slides){ try{ $s.Shapes.Title.TextFrame.TextRange.Text }catch{ '' } }) -join ';'
      $pr.Saved=-1; $creado=[string]$pr.Name
    }
    'Word' {
      $o.Visible=$true
      $d=$o.Documents.Add()
      if($contenido){
        $d.Content.Text=$contenido; $d.Content.Font.Name='Calibri'; $d.Content.Font.Size=11
        $d.Content.Select()
      }
      $leido=$d.Content.Text.TrimEnd("`r")
      $d.Saved=$true; $creado=[string]$d.Name
    }
    'Excel' {
      $o.Visible=$true; $o.UserControl=$true
      $b=$o.Workbooks.Add()
      $r=1; foreach($v in @(if($contenido){ $contenido -split ';' })){ $b.Worksheets.Item(1).Cells.Item($r,1).Value2=$v; $r++ }
      $leido=$b.Name
      $b.Saved=$true; $creado=[string]$b.Name
    }
  }
}catch{ Write-Estado $E 'error_com' @{ verificado=$false; error=$_.Exception.Message }; return }
finally{ if($o){ [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($o) }; $o=$null; [GC]::Collect(); [GC]::WaitForPendingFinalizers() }
$nuevas=@(Wait-NewWindows $hAntes { $_.app_proceso -eq $def.proc } 20)
if($nuevas.Count -eq 0){ Write-Estado $E 'no_abre' @{ verificado=$false; leido=$leido }; return }
Add-PropiosApp $nuevas $app $pAntes
# The new document's name lets sin_restos.ps1 close this copy by its window titles when COM reads nothing.
if($creado){ Add-DocumentoCreado ([int]$nuevas[0].app_pid) $def.proc $creado }
Set-AppAprendida $app $def.proc
$foco=Restore-Foreground $fg @($def.proc)
Start-Sleep -Milliseconds 500
$vivas=@($nuevas | Where-Object { [EstadoW32]::IsWindow([IntPtr][long]$_.hwnd) })
$esperado=if($app -eq 'PowerPoint'){ $(if($contenido){$contenido}else{''}) }elseif($app -eq 'Word'){ [string]$contenido }else{ $null }
# No prompt over the new document (t-form-4, round 7: Word showed BAXY only a save prompt): read back, never answered.
$dialogos=@(Get-DialogosModales ([int]$nuevas[0].app_pid) | ForEach-Object { [EstadoW32]::Title([IntPtr][long]$_) })
$ok=($vivas.Count -gt 0 -and $dialogos.Count -eq 0 -and ($null -eq $esperado -or $leido -ceq $esperado))
Write-Estado $E ($(if($ok){'corregido'}else{'no_verificado'})) @{ verificado=$ok; ventanas=@($vivas | ForEach-Object { $_.titulo }); leido=$leido; dialogos=$dialogos; cerradas_antes=$cerradas; foco=$foco }
