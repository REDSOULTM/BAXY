param([string]$B64)
$line = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($B64)) + "`n"
$bytes = [Text.Encoding]::UTF8.GetBytes($line)
for ($i = 0; $i -lt 20; $i++) {
  try {
    $f = [IO.File]::Open('C:/Users/usuario/BAXY-coord/buzon.md', 'Append', 'Write', 'ReadWrite')
    $f.Write($bytes, 0, $bytes.Length); $f.Close(); 'written'; exit 0
  } catch { Start-Sleep -Milliseconds 500 }
}
'FAILED'; exit 1
