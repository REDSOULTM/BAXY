namespace Baxy.Providers.Windows.External;

/// <summary>
/// The two UI Automation reads/acts the user-browser surface runs in Windows
/// PowerShell 5.1 (System.Windows.Automation lives there, not in the AOT core).
/// Inline, like the other adapters' scripts, so the package contract does not
/// grow. Arguments arrive as <c>$args</c>; text arrives base64 UTF-8.
/// </summary>
internal static class UserBrowserScripts
{
    /// <summary>
    /// $args[0] = window handle. Reads the browser frame's address field: walks
    /// the control view breadth-first, never enters the page content
    /// (Document), and returns the first editable field whose value looks like
    /// an address. No tabs, history, cookies or forms are read; the caller only
    /// compares the site.
    /// </summary>
    internal const string Address = """
        $ErrorActionPreference = 'Stop'
        # The runner reads UTF-8: page text, tab and video titles keep their accents.
        [Console]::OutputEncoding = [Text.Encoding]::UTF8
        function Emit([bool]$ok, [string]$value, [string]$reason) {
          [pscustomobject]@{ version = 1; ok = $ok; value = $value; error = $reason } | ConvertTo-Json -Compress
        }
        try {
          $Window = [long]$args[0]
          if ($Window -eq 0) { Emit $false '' 'window_missing'; exit 0 }
          Add-Type -AssemblyName UIAutomationClient
          Add-Type -AssemblyName UIAutomationTypes
          $root = [System.Windows.Automation.AutomationElement]::FromHandle([IntPtr]$Window)
          $walker = [System.Windows.Automation.TreeWalker]::ControlViewWalker
          $document = [System.Windows.Automation.ControlType]::Document
          $edit = [System.Windows.Automation.ControlType]::Edit
          $queue = New-Object System.Collections.Generic.Queue[object]
          $queue.Enqueue(@($root, 0))
          $visited = 0
          while ($queue.Count -gt 0 -and $visited -lt 1500) {
            $pair = $queue.Dequeue()
            $node = $pair[0]; $depth = $pair[1]
            $visited++
            $type = $node.Current.ControlType
            if ($type -eq $document) { continue }
            if ($type -eq $edit) {
              $pattern = $null
              if ($node.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern, [ref]$pattern)) {
                $value = [string]$pattern.Current.Value
                if ($value -and $value -notmatch '\s' -and $value -match '[\.:/]') {
                  Emit $true $value ''
                  exit 0
                }
              }
            }
            if ($depth -ge 24) { continue }
            $child = $walker.GetFirstChild($node)
            while ($child -ne $null) {
              $queue.Enqueue(@($child, ($depth + 1)))
              $child = $walker.GetNextSibling($child)
            }
          }
          Emit $false '' 'address_field_not_found'
        } catch {
          Emit $false '' ('uia_failed: ' + $_.Exception.GetType().Name)
        }
        """;

    /// <summary>
    /// $args[0] = window handle, $args[1] = title (base64 UTF-8), $args[2] =
    /// seconds, $args[3] = "1" to type the title into the page's own search
    /// field first. On a streaming page the person's session shows, presses the
    /// item named as the title and then its play control. It only presses
    /// elements named as the title or as a play word and returns the step
    /// reached and the chosen item's name, nothing else of the page; playback is
    /// verified by the caller through SMTC, never by this script's word.
    /// </summary>
    internal const string PagePlay = """
        $ErrorActionPreference = 'Stop'
        # The runner reads UTF-8: page text, tab and video titles keep their accents.
        [Console]::OutputEncoding = [Text.Encoding]::UTF8
        function Emit([bool]$ok, [string]$step, [string]$chosen) {
          [pscustomobject]@{ version = 1; ok = $ok; step = $step; chosen = $chosen } | ConvertTo-Json -Compress
        }
        function Fold([string]$text) {
          if (-not $text) { return '' }
          $decomposed = $text.Normalize([Text.NormalizationForm]::FormD)
          $builder = New-Object Text.StringBuilder
          foreach ($c in $decomposed.ToCharArray()) {
            if ([Globalization.CharUnicodeInfo]::GetUnicodeCategory($c) -ne [Globalization.UnicodeCategory]::NonSpacingMark) {
              [void]$builder.Append($c)
            }
          }
          return (($builder.ToString().ToLowerInvariant()) -replace '\s+', ' ').Trim()
        }
        function Press($element) {
          $pattern = $null
          if ($element.TryGetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern, [ref]$pattern)) {
            $pattern.Invoke()
            return $true
          }
          return $false
        }
        try {
          $Window = [long]$args[0]
          $Title = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String([string]$args[1]))
          $Seconds = [int]$args[2]
          $TypeSearch = ([string]$args[3]) -eq '1'
          if ($Window -eq 0 -or -not $Title) { Emit $false 'arguments' ''; exit 0 }
          if ($Seconds -lt 5) { $Seconds = 5 }
          if ($Seconds -gt 40) { $Seconds = 40 }
          Add-Type -AssemblyName UIAutomationClient
          Add-Type -AssemblyName UIAutomationTypes
          $AE = [System.Windows.Automation.AutomationElement]
          $CT = [System.Windows.Automation.ControlType]
          $descendants = [System.Windows.Automation.TreeScope]::Descendants
          $root = $AE::FromHandle([IntPtr]$Window)
          $want = Fold $Title
          $playWords = @('reproducir', 'ver ahora', 'continuar', 'reanudar', 'play', 'watch now', 'resume', 'continue watching')
          $documentCondition = New-Object System.Windows.Automation.PropertyCondition($AE::ControlTypeProperty, $CT::Document)
          # A search box is an edit or, with role=combobox, a combo box; both take a value.
          $editCondition = New-Object System.Windows.Automation.AndCondition(
            (New-Object System.Windows.Automation.OrCondition(
              (New-Object System.Windows.Automation.PropertyCondition($AE::ControlTypeProperty, $CT::Edit)),
              (New-Object System.Windows.Automation.PropertyCondition($AE::ControlTypeProperty, $CT::ComboBox)))),
            (New-Object System.Windows.Automation.PropertyCondition($AE::IsValuePatternAvailableProperty, $true)),
            (New-Object System.Windows.Automation.PropertyCondition($AE::IsEnabledProperty, $true)))
          $pickCondition = New-Object System.Windows.Automation.OrCondition(
            (New-Object System.Windows.Automation.PropertyCondition($AE::ControlTypeProperty, $CT::Hyperlink)),
            (New-Object System.Windows.Automation.PropertyCondition($AE::ControlTypeProperty, $CT::Button)),
            (New-Object System.Windows.Automation.PropertyCondition($AE::ControlTypeProperty, $CT::ListItem)))
          $deadline = (Get-Date).AddSeconds($Seconds)
          $step = 'page'
          $chosen = ''
          $typed = -not $TypeSearch
          while ((Get-Date) -lt $deadline) {
            # The page of the active tab is the document named as the window
            # title begins; side panels (Opera GX's sidebar web panels) are
            # documents too and are never touched.
            $windowTitle = [string]$root.Current.Name
            $documents = $root.FindAll($descendants, $documentCondition)
            $document = $null
            foreach ($candidate in $documents) {
              $documentName = [string]$candidate.Current.Name
              if ($documentName -and $windowTitle.StartsWith($documentName)) { $document = $candidate; break }
            }
            if ($document -eq $null -and $documents.Count -eq 1) { $document = $documents[0] }
            if ($document -eq $null) { Start-Sleep -Milliseconds 500; continue }
            if (-not $typed) {
              $step = 'search'
              $edit = $document.FindFirst($descendants, $editCondition)
              if ($edit -ne $null) {
                $edit.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern).SetValue($Title)
                $typed = $true
                Start-Sleep -Milliseconds 2000
              } else {
                Start-Sleep -Milliseconds 500
              }
              continue
            }
            $items = $document.FindAll($descendants, $pickCondition)
            if ($chosen -eq '') {
              $step = 'title'
              $best = $null
              $rank = 9
              foreach ($item in $items) {
                $name = Fold $item.Current.Name
                if (-not $name) { continue }
                $current = 9
                if ($name -eq $want) { $current = 0 }
                elseif ($name.StartsWith($want)) { $current = 1 }
                elseif ($name.Contains($want)) { $current = 2 }
                if ($current -lt $rank) {
                  $rank = $current
                  $best = $item
                  if ($current -eq 0) { break }
                }
              }
              $bestName = ''
              if ($best -ne $null) { $bestName = [string]$best.Current.Name }
              if ($best -ne $null -and (Press $best)) {
                $chosen = $bestName
                Start-Sleep -Milliseconds 2500
                continue
              }
              Start-Sleep -Milliseconds 700
              continue
            }
            $step = 'play'
            foreach ($item in $items) {
              $name = Fold $item.Current.Name
              foreach ($word in $playWords) {
                if (($name -eq $word -or $name.StartsWith($word + ' ')) -and (Press $item)) {
                  Emit $true 'play_invoked' $chosen
                  exit 0
                }
              }
            }
            Start-Sleep -Milliseconds 700
          }
          Emit $false $step $chosen
        } catch {
          Emit $false ('uia_failed: ' + $_.Exception.GetType().Name) ''
        }
        """;

    /// <summary>
    /// $args[0] = window handle. The titles of the window's tabs and which one is selected (Chromium and Opera GX
    /// expose each tab as a TabItem with SelectionItemPattern). Never enters a page (Document). A node that vanishes
    /// mid-walk (tab animations) is skipped, not fatal.
    /// </summary>
    internal const string Tabs = """
        $ErrorActionPreference = 'Stop'
        # The runner reads UTF-8: page text, tab and video titles keep their accents.
        [Console]::OutputEncoding = [Text.Encoding]::UTF8
        try {
          $Window = [long]$args[0]
          if ($Window -eq 0) { [pscustomobject]@{ version = 1; ok = $false; tabs = @(); error = 'window_missing' } | ConvertTo-Json -Compress; exit 0 }
          Add-Type -AssemblyName UIAutomationClient
          Add-Type -AssemblyName UIAutomationTypes
          $root = [System.Windows.Automation.AutomationElement]::FromHandle([IntPtr]$Window)
          $walker = [System.Windows.Automation.TreeWalker]::ControlViewWalker
          $document = [System.Windows.Automation.ControlType]::Document
          $tabItem = [System.Windows.Automation.ControlType]::TabItem
          $tabs = New-Object System.Collections.Generic.List[object]
          $queue = New-Object System.Collections.Generic.Queue[object]
          $queue.Enqueue(@($root, 0))
          $visited = 0
          while ($queue.Count -gt 0 -and $visited -lt 2000) {
            $pair = $queue.Dequeue()
            $node = $pair[0]; $depth = $pair[1]
            $visited++
            try { $type = $node.Current.ControlType } catch { continue }
            if ($type -eq $document) { continue }
            if ($type -eq $tabItem) {
              $selected = $false; $pattern = $null
              try {
                if ($node.TryGetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern, [ref]$pattern)) {
                  $selected = [bool]$pattern.Current.IsSelected
                }
                $tabs.Add([pscustomobject]@{ title = [string]$node.Current.Name; selected = $selected })
              } catch { }
              continue
            }
            if ($depth -ge 24) { continue }
            try {
              $child = $walker.GetFirstChild($node)
              while ($child -ne $null) {
                $queue.Enqueue(@($child, ($depth + 1)))
                $child = $walker.GetNextSibling($child)
              }
            } catch { }
          }
          $reason = if ($tabs.Count -gt 0) { '' } else { 'tab_strip_not_found' }
          [pscustomobject]@{ version = 1; ok = ($tabs.Count -gt 0); tabs = $tabs.ToArray(); error = $reason } | ConvertTo-Json -Compress -Depth 4
        } catch {
          [pscustomobject]@{ version = 1; ok = $false; tabs = @(); error = ('uia_failed: ' + $_.Exception.GetType().Name) } | ConvertTo-Json -Compress
        }
        """;

    /// <summary>
    /// $args[0] = window handle, $args[1] = maximum characters. The title and the visible text of the page the window
    /// shows: the Document whose AutomationId is RootWebArea (Chromium's page; Opera GX's side panels are other
    /// documents), read with TextPattern, or from its Text nodes when the pattern is missing. Nothing else of the
    /// browser (history, cookies, forms) is read.
    /// </summary>
    internal const string PageText = """
        $ErrorActionPreference = 'Stop'
        # The runner reads UTF-8: page text, tab and video titles keep their accents.
        [Console]::OutputEncoding = [Text.Encoding]::UTF8
        function Emit([bool]$ok, [string]$title, [string]$text, [bool]$truncated, [string]$reason) {
          [pscustomobject]@{ version = 1; ok = $ok; title = $title; text = $text; truncated = $truncated; error = $reason } | ConvertTo-Json -Compress
        }
        try {
          $Window = [long]$args[0]
          $Maximum = [int]$args[1]
          if ($Window -eq 0) { Emit $false '' '' $false 'window_missing'; exit 0 }
          Add-Type -AssemblyName UIAutomationClient
          Add-Type -AssemblyName UIAutomationTypes
          $root = [System.Windows.Automation.AutomationElement]::FromHandle([IntPtr]$Window)
          $walker = [System.Windows.Automation.TreeWalker]::ControlViewWalker
          $document = [System.Windows.Automation.ControlType]::Document
          $textType = [System.Windows.Automation.ControlType]::Text
          $page = $null
          # Chromium builds the page's accessibility tree on the first request: a second look finds it.
          for ($look = 0; $look -lt 2 -and $page -eq $null; $look++) {
            if ($look -gt 0) { Start-Sleep -Milliseconds 600 }
            $queue = New-Object System.Collections.Generic.Queue[object]
            $queue.Enqueue(@($root, 0))
            $visited = 0
            while ($queue.Count -gt 0 -and $visited -lt 3000 -and $page -eq $null) {
              $pair = $queue.Dequeue()
              $node = $pair[0]; $depth = $pair[1]
              $visited++
              try { $type = $node.Current.ControlType } catch { continue }
              if ($type -eq $document) {
                try { if ($node.Current.AutomationId -eq 'RootWebArea') { $page = $node } } catch { }
                continue
              }
              if ($depth -ge 28) { continue }
              try {
                $child = $walker.GetFirstChild($node)
                while ($child -ne $null) {
                  $queue.Enqueue(@($child, ($depth + 1)))
                  $child = $walker.GetNextSibling($child)
                }
              } catch { }
            }
          }
          if ($page -eq $null) { Emit $false '' '' $false 'page_document_not_found'; exit 0 }
          $text = ''
          $pattern = $null
          if ($page.TryGetCurrentPattern([System.Windows.Automation.TextPattern]::Pattern, [ref]$pattern)) {
            $text = [string]$pattern.DocumentRange.GetText($Maximum + 1)
          }
          if (-not $text) {
            $builder = New-Object System.Text.StringBuilder
            $queue = New-Object System.Collections.Generic.Queue[object]
            $queue.Enqueue($page)
            $visited = 0
            while ($queue.Count -gt 0 -and $visited -lt 6000 -and $builder.Length -le $Maximum) {
              $node = $queue.Dequeue()
              $visited++
              try {
                if ($node.Current.ControlType -eq $textType) { [void]$builder.Append([string]$node.Current.Name).Append("`n") }
                $child = $walker.GetFirstChild($node)
                while ($child -ne $null) { $queue.Enqueue($child); $child = $walker.GetNextSibling($child) }
              } catch { }
            }
            $text = $builder.ToString()
          }
          $truncated = $text.Length -gt $Maximum
          if ($truncated) { $text = $text.Substring(0, $Maximum) }
          Emit $true ([string]$page.Current.Name) $text $truncated ''
        } catch {
          Emit $false '' '' $false ('uia_failed: ' + $_.Exception.GetType().Name)
        }
        """;
}
