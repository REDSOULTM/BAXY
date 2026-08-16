$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName PresentationFramework
Add-Type -AssemblyName PresentationCore
Add-Type -AssemblyName WindowsBase

$window = [System.Windows.Window]::new()
$window.Title = 'BAXY audit button target'
$window.Left = 220
$window.Top = 180
$window.Width = 520
$window.Height = 320

$button = [System.Windows.Controls.Button]::new()
$button.Content = 'BAXY audit button'
$button.FontSize = 24
$button.Margin = 60
$button.Add_Click({
    $button.Content = 'BAXY audit completed'
    $button.IsEnabled = $false
})
$window.Content = $button
$window.Add_ContentRendered({
    $window.Activate()
    $button.Focus()
})

[void]$window.ShowDialog()
