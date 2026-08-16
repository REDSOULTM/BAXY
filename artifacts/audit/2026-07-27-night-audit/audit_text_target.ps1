$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$form = [System.Windows.Forms.Form]::new()
$form.Text = 'BAXY audit text target'
$form.StartPosition = 'Manual'
$form.Location = [System.Drawing.Point]::new(180, 160)
$form.Size = [System.Drawing.Size]::new(720, 480)

$text = [System.Windows.Forms.TextBox]::new()
$text.Multiline = $true
$text.AcceptsReturn = $true
$text.ScrollBars = [System.Windows.Forms.ScrollBars]::Vertical
$text.Dock = [System.Windows.Forms.DockStyle]::Fill
$text.Font = [System.Drawing.Font]::new('Segoe UI', 14)
$form.Controls.Add($text)
$form.Add_Shown({
    $form.Activate()
    $text.Focus()
})

[System.Windows.Forms.Application]::Run($form)
