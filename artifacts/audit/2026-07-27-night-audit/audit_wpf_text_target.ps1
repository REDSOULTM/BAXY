$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName PresentationFramework
Add-Type -AssemblyName PresentationCore
Add-Type -AssemblyName WindowsBase

$window = [System.Windows.Window]::new()
$window.Title = 'BAXY audit WPF text target'
$window.Left = 180
$window.Top = 160
$window.Width = 720
$window.Height = 480

$text = [System.Windows.Controls.TextBox]::new()
$text.AcceptsReturn = $true
$text.VerticalScrollBarVisibility = 'Auto'
$text.FontSize = 20
$window.Content = $text
$window.Add_ContentRendered({
    $window.Activate()
    $text.Focus()
})

[void]$window.ShowDialog()
