<#
Tabs of the person's default browser for the e2e runners (bench_e2e.Isolation, R8-NB-1): what a case's setup and turns
opened in it stayed open (NB-R7: Opera GX went from 47 to more than 70 tabs, and a page left by one case changed the next
one's result). Tabs are told apart by their UI Automation runtime id, never by title or address.

  -List                     one line per window of the default browser, «BROWSER-WINDOW <hwnd> whole|partial», one per
                            tab, «BROWSER-TAB <hwnd> <runtime id>», and «BROWSER-TABS-READ» when the list finished.
  -Window <hwnd> -Close a,b closes those tabs one by one: «TAB-CLOSED <hwnd> <id>» when that tab is gone and no other
                            one went with it, else «TAB-LEFT <hwnd> <id> <reason>».

A tab is closed the way the product closes one in Opera GX, which runs no tab command by window message
(UserBrowserTabs.PostTabCommand): a middle click posted to the window at the tab's centre, only after UI Automation says
the element at that point is the tab itself.
#>
param([switch]$List, [int64]$Window = 0, [string[]]$Close = @())
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -AssemblyName WindowsBase
if (-not ('BenchTabs' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
public static class BenchTabs {
    public delegate bool EnumProc(IntPtr h, IntPtr l);
    [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X; public int Y; }
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder sb, int n);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll")] static extern bool ScreenToClient(IntPtr h, ref POINT p);
    [DllImport("user32.dll")] static extern bool PostMessage(IntPtr h, uint msg, IntPtr w, IntPtr l);
    [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
    public static List<IntPtr> TopLevel() { var r = new List<IntPtr>(); EnumWindows((h, l) => { r.Add(h); return true; }, IntPtr.Zero); return r; }
    public static string Cls(IntPtr h) { var sb = new StringBuilder(256); GetClassName(h, sb, 256); return sb.ToString(); }
    public static uint Pid(IntPtr h) { uint p; GetWindowThreadProcessId(h, out p); return p; }
    public static bool MiddleClick(IntPtr h, int x, int y) {
        var p = new POINT { X = x, Y = y };
        if (!ScreenToClient(h, ref p)) return false;
        var at = (IntPtr)(((p.Y & 0xFFFF) << 16) | (p.X & 0xFFFF));
        return PostMessage(h, 0x0200, IntPtr.Zero, at) && PostMessage(h, 0x0207, (IntPtr)0x10, at) && PostMessage(h, 0x0208, IntPtr.Zero, at);
    }
}
'@
}
# UI Automation rectangles and the posted click in the same (physical) pixels.
[void][BenchTabs]::SetProcessDPIAware()
$CT = [System.Windows.Automation.ControlType]
$Walker = [System.Windows.Automation.TreeWalker]::ControlViewWalker

function Get-DefaultBrowserProcess {
    # The process name of the program that opens https links for this user (UserChoice ProgId → its open command).
    $choice = 'HKCU:\Software\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoice'
    $progId = (Get-ItemProperty -LiteralPath $choice -Name ProgId).ProgId
    $command = (Get-ItemProperty -LiteralPath "Registry::HKEY_CLASSES_ROOT\$progId\shell\open\command").'(default)'
    $exe = if ($command -match '^\s*"([^"]+)"') { $Matches[1] } else { ($command -split '\s+')[0] }
    return [IO.Path]::GetFileNameWithoutExtension($exe)
}
function Get-BrowserWindows {
    $name = Get-DefaultBrowserProcess
    $ids = @(Get-Process -Name $name -ErrorAction SilentlyContinue | ForEach-Object { [uint32]$_.Id })
    foreach ($h in [BenchTabs]::TopLevel()) {
        if (-not [BenchTabs]::IsWindowVisible($h) -or [BenchTabs]::Cls($h) -ne 'Chrome_WidgetWin_1') { continue }
        if ($ids -contains [BenchTabs]::Pid($h)) { [int64]$h }
    }
}
function Key($element) { ($element.GetRuntimeId()) -join '.' }
function Get-WindowTabs([int64]$Hwnd) {
    # The tab items of the window's frame (never inside a page), and whether the frame was read whole.
    $root = [System.Windows.Automation.AutomationElement]::FromHandle([IntPtr]$Hwnd)
    $tabs = New-Object System.Collections.Generic.List[object]
    $queue = New-Object System.Collections.Generic.Queue[object]
    $queue.Enqueue(@($root, 0))
    $visited = 0; $unread = 0
    while ($queue.Count -gt 0 -and $visited -lt 2500) {
        $pair = $queue.Dequeue(); $node = $pair[0]; $depth = $pair[1]
        $visited++
        try { $type = $node.Current.ControlType } catch { $unread++; continue }
        if ($type -eq $CT::Document) { continue }
        if ($type -eq $CT::TabItem) {
            try { $tabs.Add([pscustomobject]@{ Id = (Key $node); Node = $node }) } catch { $unread++ }
            continue
        }
        if ($depth -ge 26) { $unread++; continue }
        try {
            $child = $Walker.GetFirstChild($node)
            while ($child -ne $null) { $queue.Enqueue(@($child, ($depth + 1))); $child = $Walker.GetNextSibling($child) }
        } catch { $unread++ }
    }
    [pscustomobject]@{ Tabs = $tabs; Whole = ($unread -eq 0 -and $queue.Count -eq 0) }
}
function Get-TabAt([System.Windows.Automation.AutomationElement]$Element) {
    # The tab item an element belongs to (itself or an ancestor), or null.
    $node = $Element
    for ($i = 0; $node -ne $null -and $i -lt 8; $i++) {
        if ($node.Current.ControlType -eq $CT::TabItem) { return $node }
        $node = $Walker.GetParent($node)
    }
    return $null
}
function Close-Tab([int64]$Hwnd, [string]$Id) {
    $read = Get-WindowTabs $Hwnd
    $target = @($read.Tabs | Where-Object { $_.Id -eq $Id })
    if ($target.Count -eq 0) { return "TAB-LEFT $Hwnd $Id not_found" }
    if (-not $read.Whole) { return "TAB-LEFT $Hwnd $Id strip_partial" }
    $others = @($read.Tabs | Where-Object { $_.Id -ne $Id } | ForEach-Object { $_.Id })
    $tab = $target[0].Node
    if ($tab.Current.IsOffscreen) {
        # Selecting it scrolls the strip to it; the tab is closed right after, so the selection does not stay.
        $pattern = $null
        if ($tab.TryGetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern, [ref]$pattern)) { $pattern.Select() }
        Start-Sleep -Milliseconds 400
    }
    $box = $tab.Current.BoundingRectangle
    if ($tab.Current.IsOffscreen -or $box.IsEmpty -or $box.Width -le 0) { return "TAB-LEFT $Hwnd $Id offscreen" }
    $x = [int]($box.Left + $box.Width / 2); $y = [int]($box.Top + $box.Height / 2)
    $hit = Get-TabAt ([System.Windows.Automation.AutomationElement]::FromPoint((New-Object System.Windows.Point($x, $y))))
    if ($hit -eq $null -or (Key $hit) -ne $Id) { return "TAB-LEFT $Hwnd $Id point_not_the_tab" }
    if (-not [BenchTabs]::MiddleClick([IntPtr]$Hwnd, $x, $y)) { return "TAB-LEFT $Hwnd $Id click_not_posted" }
    for ($i = 0; $i -lt 10; $i++) {
        Start-Sleep -Milliseconds 300
        $now = @((Get-WindowTabs $Hwnd).Tabs | ForEach-Object { $_.Id })
        if ($now -notcontains $Id) {
            $lost = @($others | Where-Object { $now -notcontains $_ })
            if ($lost.Count -gt 0) { return "TAB-LEFT $Hwnd $Id other_tab_gone $($lost -join ',')" }
            return "TAB-CLOSED $Hwnd $Id"
        }
    }
    return "TAB-LEFT $Hwnd $Id still_open"
}

if ($List) {
    foreach ($h in @(Get-BrowserWindows)) {
        # A window that cannot be read is listed as partial: none of its tabs is closed after the case.
        try { $read = Get-WindowTabs $h } catch { "BROWSER-WINDOW $h partial"; continue }
        "BROWSER-WINDOW $h $(if ($read.Whole) { 'whole' } else { 'partial' })"
        foreach ($t in $read.Tabs) { "BROWSER-TAB $h $($t.Id)" }
    }
    'BROWSER-TABS-READ'
    exit 0
}
if ($Window -ne 0) {
    foreach ($id in $Close) {
        try { Close-Tab $Window $id } catch { "TAB-LEFT $Window $id uia_failed $($_.Exception.GetType().Name)" }
    }
}
