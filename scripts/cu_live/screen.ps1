param([string]$Out)
Add-Type -AssemblyName System.Drawing,System.Windows.Forms
$b=[Windows.Forms.Screen]::PrimaryScreen.Bounds
$bmp=New-Object Drawing.Bitmap $b.Width,$b.Height; $g=[Drawing.Graphics]::FromImage($bmp); $g.CopyFromScreen(0,0,0,0,$bmp.Size)
$s=New-Object Drawing.Bitmap $bmp,([int]($b.Width/2)),([int]($b.Height/2)); $s.Save($Out,[Drawing.Imaging.ImageFormat]::Png); "ok $($b.Width)x$($b.Height)"
