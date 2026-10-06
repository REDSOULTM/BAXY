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
            try { $type = $node.Current.ControlType } catch { continue }
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
            # Opera GX after a Speed Dial tab keeps a dead first child under LiveBackgroundView: GetFirstChild
            # throws there, and the live children are reached from the last one backwards.
            $children = New-Object System.Collections.Generic.List[object]
            try {
              $child = $walker.GetFirstChild($node)
              while ($child -ne $null) { $children.Add($child); $child = $walker.GetNextSibling($child) }
            } catch {
              $children.Clear()
              try {
                $child = $walker.GetLastChild($node)
                while ($child -ne $null) { $children.Insert(0, $child); $child = $walker.GetPreviousSibling($child) }
              } catch { }
            }
            foreach ($child in $children) { $queue.Enqueue(@($child, ($depth + 1))) }
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
    /// reached and the chosen title as the service writes it, nothing else of
    /// the page; playback is verified by the caller through SMTC, never by this
    /// script's word. A "Who's watching?" profile gate stops it (step
    /// "profile"): the person picks their own profile. Names measured in Opera
    /// GX on 2026-10-06 (documentacion/NAVEGADOR_USUARIO.md): Disney+ cards
    /// "Coco Clasificación: 0+…" and "VER AHORA"/"CONTINUAR"; HBO Max cards
    /// wrapped in bidi isolates and "Ver The Last of Us, Temporada 1…" or
    /// "Reanudar Superman…".
    /// </summary>
    internal const string PagePlay = """
        $ErrorActionPreference = 'Stop'
        # The runner reads UTF-8: page text, tab and video titles keep their accents.
        [Console]::OutputEncoding = [Text.Encoding]::UTF8
        function Emit([bool]$ok, [string]$step, [string]$chosen) {
          [pscustomobject]@{ version = 1; ok = $ok; step = $step; chosen = $chosen } | ConvertTo-Json -Compress
        }
        # Format characters (HBO Max wraps titles in bidi isolates) are dropped and spaces collapsed, so a name and its
        # folded form keep the same length.
        function Plain([string]$text) {
          if (-not $text) { return '' }
          $builder = New-Object Text.StringBuilder
          foreach ($c in $text.ToCharArray()) {
            if ([Globalization.CharUnicodeInfo]::GetUnicodeCategory($c) -ne [Globalization.UnicodeCategory]::Format) {
              [void]$builder.Append($c)
            }
          }
          return (($builder.ToString()) -replace '\s+', ' ').Trim()
        }
        function Fold([string]$text) {
          $plain = (Plain $text).Normalize([Text.NormalizationForm]::FormD)
          $builder = New-Object Text.StringBuilder
          foreach ($c in $plain.ToCharArray()) {
            if ([Globalization.CharUnicodeInfo]::GetUnicodeCategory($c) -ne [Globalization.UnicodeCategory]::NonSpacingMark) {
              [void]$builder.Append($c)
            }
          }
          return $builder.ToString().ToLowerInvariant()
        }
        # The title a card names first: its first bidi-isolated run when the page uses them.
        function Isolated([string]$text) {
          $match = [regex]::Match([string]$text, '^[\u2066-\u2069\s]*([^\u2066-\u2069]+)\u2069')
          if ($match.Success) { return (Plain $match.Groups[1].Value) }
          return ''
        }
        # 0 the name is the title; 1 it begins with it and goes on after a space, a comma or a full stop (Disney+ cards add
        # "Clasificacion..."); 2 it begins with it and goes on as another title ("Daredevil: Born Again", "Cocoon"); 3 it
        # only contains it; 9 nothing.
        function Rank([string]$name, [string]$want) {
          $isolated = Fold (Isolated $name)
          $folded = Fold $name
          if (-not $folded) { return 9 }
          if ($isolated -eq $want -or $folded -eq $want) { return 0 }
          if ($folded.StartsWith($want)) {
            $next = $folded[$want.Length]
            if ($next -eq ' ' -or $next -eq '.' -or $next -eq ',') { return 1 }
            return 2
          }
          if ($folded.Contains($want)) { return 3 }
          return 9
        }
        # The children of a node in the control view. Opera GX, once a Speed Dial tab was opened, keeps a dead first child
        # under LiveBackgroundView: GetFirstChild throws there (and FindAll from the window finds nothing), while the live
        # children are still reached from the last one backwards.
        function Kids($walker, $node) {
          $list = New-Object System.Collections.Generic.List[object]
          try {
            $child = $walker.GetFirstChild($node)
            while ($child -ne $null) { $list.Add($child); $child = $walker.GetNextSibling($child) }
            return ,$list
          } catch { }
          $list.Clear()
          try {
            $child = $walker.GetLastChild($node)
            while ($child -ne $null) { $list.Insert(0, $child); $child = $walker.GetPreviousSibling($child) }
          } catch { }
          return ,$list
        }
        # The page of the active tab: the document named as the window title begins (Opera GX's side panels are documents
        # too and are never touched), or the only document there is. Walked, never entered.
        function FindPage($root, [string]$windowTitle) {
          $walker = [System.Windows.Automation.TreeWalker]::ControlViewWalker
          $documentType = [System.Windows.Automation.ControlType]::Document
          $queue = New-Object System.Collections.Generic.Queue[object]
          $queue.Enqueue(@($root, 0))
          $visited = 0
          $found = New-Object System.Collections.Generic.List[object]
          while ($queue.Count -gt 0 -and $visited -lt 3000) {
            $pair = $queue.Dequeue()
            $node = $pair[0]; $depth = $pair[1]
            $visited++
            try { $type = $node.Current.ControlType } catch { continue }
            if ($type -eq $documentType) {
              try { $name = [string]$node.Current.Name } catch { continue }
              if ($name -and $windowTitle.StartsWith($name)) { return $node }
              $found.Add($node)
              continue
            }
            if ($depth -ge 28) { continue }
            foreach ($child in (Kids $walker $node)) { $queue.Enqueue(@($child, ($depth + 1))) }
          }
          if ($found.Count -eq 1) { return $found[0] }
          return $null
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
          # "Ver The Last of Us, Temporada 1...": a watch verb followed by the title is the play control too.
          $watchVerbs = @('ver', 'reproducir', 'watch', 'play')
          $notPlay = '(trailer|avance|teaser|mi lista|my list)'
          $profileGate = '^[\s\u00bf?]*(quien esta (viendo|mirando)( ahora)?|who.?s watching( now)?|who is watching( now)?)[\s?]*$'
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
          $headingCondition = New-Object System.Windows.Automation.OrCondition(
            (New-Object System.Windows.Automation.PropertyCondition($AE::ControlTypeProperty, $CT::Text)),
            (New-Object System.Windows.Automation.PropertyCondition($AE::ControlTypeProperty, $CT::Header)))
          $deadline = (Get-Date).AddSeconds($Seconds)
          $step = 'page'
          $chosen = ''
          $chosenFolded = ''
          $document = $null
          $typed = -not $TypeSearch
          while ((Get-Date) -lt $deadline) {
            # The page of the active tab is the document named as the window title begins; side panels (Opera GX's sidebar
            # web panels) are documents too and are never touched.
            $windowTitle = [string]$root.Current.Name
            if ($document -ne $null) {
              try {
                $documentName = [string]$document.Current.Name
                if (-not ($documentName -and $windowTitle.StartsWith($documentName))) { $document = $null }
              } catch { $document = $null }
            }
            if ($document -eq $null) { $document = FindPage $root $windowTitle }
            if ($document -eq $null) { Start-Sleep -Milliseconds 500; continue }
            if ($chosen -eq '') {
              # A profile gate is the person's choice, never BAXY's: stop and say it.
              foreach ($heading in $document.FindAll($descendants, $headingCondition)) {
                $headingName = [string]$heading.Current.Name
                if ($headingName.Length -le 40 -and (Fold $headingName) -match $profileGate) { Emit $false 'profile' ''; exit 0 }
              }
            }
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
                $current = Rank ([string]$item.Current.Name) $want
                if ($current -lt $rank) {
                  $rank = $current
                  $best = $item
                  if ($current -eq 0) { break }
                }
              }
              $bestName = ''
              if ($best -ne $null) { $bestName = [string]$best.Current.Name }
              if ($best -ne $null -and (Press $best)) {
                # The title as the service writes it: its isolated run, or the name cut to the length of what was asked
                # when the name begins with it; otherwise the name itself, short.
                $chosen = Isolated $bestName
                $plain = Plain $bestName
                if (-not $chosen -and $rank -le 2 -and $plain.Length -ge $want.Length) { $chosen = $plain.Substring(0, $want.Length) }
                if (-not $chosen) { $chosen = $plain }
                if ($chosen.Length -gt 120) { $chosen = $chosen.Substring(0, 120) }
                $chosenFolded = Fold $chosen
                Start-Sleep -Milliseconds 2500
                continue
              }
              Start-Sleep -Milliseconds 700
              continue
            }
            $step = 'play'
            foreach ($item in $items) {
              $name = Fold $item.Current.Name
              if (-not $name -or $name -match $notPlay) { continue }
              $isPlay = $false
              foreach ($word in $playWords) {
                if ($name -eq $word -or $name.StartsWith($word + ' ')) { $isPlay = $true; break }
              }
              if (-not $isPlay) {
                foreach ($verb in $watchVerbs) {
                  if ($name.StartsWith($verb + ' ' + $want) -or ($chosenFolded -and $name.StartsWith($verb + ' ' + $chosenFolded))) { $isPlay = $true; break }
                }
              }
              if ($isPlay -and (Press $item)) {
                Emit $true 'play_invoked' $chosen
                exit 0
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
