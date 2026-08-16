param(
    [Parameter(Mandatory = $true)]
    [string]$Title,
    [Parameter(Mandatory = $true)]
    [AllowEmptyString()]
    [string]$InitialText,
    [Parameter(Mandatory = $true)]
    [string]$OutputPath,
    [switch]$SelectAll
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName PresentationFramework
Add-Type -AssemblyName PresentationCore
Add-Type -AssemblyName WindowsBase

$window = [System.Windows.Window]::new()
$window.Title = $Title
$window.Left = 180
$window.Top = 160
$window.Width = 720
$window.Height = 480

$text = [System.Windows.Controls.TextBox]::new()
$text.AcceptsReturn = $true
$text.VerticalScrollBarVisibility = 'Auto'
$text.FontSize = 20
$text.Text = $InitialText
$window.Content = $text
$window.Add_ContentRendered({
    $window.Activate()
    $text.Focus()
    if ($SelectAll) {
        $text.SelectAll()
    }
})
$window.Add_Closed({
    [System.IO.File]::WriteAllText(
        [System.IO.Path]::GetFullPath($OutputPath),
        $text.Text,
        [System.Text.UTF8Encoding]::new($false))
})

[void]$window.ShowDialog()
