namespace Baxy.Providers.Windows.External;

/// <summary>
/// The UI Automation reads/acts the user-browser surface runs in Windows
/// PowerShell 5.1 (System.Windows.Automation lives there, not in the AOT core).
/// Inline, like the other adapters' scripts, so the package contract does not
/// grow. Arguments arrive as <c>$args</c>; text arrives base64 UTF-8.
/// </summary>
internal static class UserBrowserScripts
{
    /// <summary>
    /// The children of a node of the browser frame. Opera GX, once its Speed Dial (a new tab) has been shown, keeps a
    /// dead first child under LiveBackgroundView: GetFirstChild and FindAll fail there until Opera restarts, while the
    /// last child (WindowDecoratorGx, which holds the tab strip, the toolbar and the page) answers. When the forward
    /// walk fails the children are taken from the end, so the frame stays readable without touching the browser.
    /// </summary>
    private const string Walk = """
        # Auditoría final (regla 3): a node whose children could not all be read (both walks failed, or 400 of them) marks
        # the read partial, through a table the script and this function share (a block run by & { } has no $script:).
        $WalkState = @{ partial = $false }
        function Children($walker, $node) {
          $kids = New-Object System.Collections.Generic.List[object]
          try {
            $child = $walker.GetFirstChild($node)
            while ($child -ne $null -and $kids.Count -lt 400) { $kids.Add($child); $child = $walker.GetNextSibling($child) }
          } catch {
            try {
              $child = $walker.GetLastChild($node)
              while ($child -ne $null -and $kids.Count -lt 400) { $kids.Add($child); $child = $walker.GetPreviousSibling($child) }
            } catch { $WalkState.partial = $true }
          }
          if ($child -ne $null) { $WalkState.partial = $true }
          return $kids
        }

        """;

    /// <summary>
    /// $args[0] = window handle. Reads the browser frame's address field: walks
    /// the control view breadth-first, never enters the page content
    /// (Document), and returns the first editable field whose value looks like
    /// an address. No tabs, history, cookies or forms are read; the caller only
    /// compares the site.
    /// </summary>
    internal const string Address = Walk + """
        $ErrorActionPreference = 'Stop'
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
          # Auditoría final (regla 3): no address is read as «none shown» (a new tab, the start page: ok with an empty
          # value) only when the whole frame was walked with every node read; a node that failed, a field whose value
          # could not be read or a walk cut by its limits is the address not read.
          $unread = $false
          while ($queue.Count -gt 0 -and $visited -lt 1500) {
            $pair = $queue.Dequeue()
            $node = $pair[0]; $depth = $pair[1]
            $visited++
            try { $type = $node.Current.ControlType } catch { $unread = $true; continue }
            if ($type -eq $document) { continue }
            if ($type -eq $edit) {
              $pattern = $null
              try {
                if ($node.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern, [ref]$pattern)) {
                  $value = [string]$pattern.Current.Value
                  if ($value -and $value -notmatch '\s' -and $value -match '[\.:/]') {
                    Emit $true $value ''
                    exit 0
                  }
                }
              } catch { $unread = $true }
            }
            if ($depth -ge 24) { $unread = $true; continue }
            foreach ($child in (Children $walker $node)) { $queue.Enqueue(@($child, ($depth + 1))) }
          }
          if (-not $unread -and -not $WalkState.partial -and $queue.Count -eq 0) { Emit $true '' ''; exit 0 }
          Emit $false '' 'address_field_not_found'
        } catch {
          Emit $false '' ('uia_failed: ' + $_.Exception.GetType().Name)
        }
        """;

    /// <summary>
    /// $args[0] = window handle, $args[1] = title (base64 UTF-8), $args[2] =
    /// seconds, $args[3] = "1" to type the title into the page's own search
    /// field first. On a streaming page the person's session shows, presses the
    /// item named exactly as the title (case, accents and spacing aside) and
    /// then its play control. It only presses elements named as the title or as
    /// a play word and returns the step reached and the chosen title as the
    /// service writes it; when no item is named as the title it presses nothing
    /// and returns the names it saw (seen). Playback is verified by the caller
    /// through SMTC, never by this script's word. A "Who's watching?" profile
    /// gate stops it (step "profile"): the person picks their own profile. Names measured in Opera
    /// GX on 2026-10-06 (documentacion/NAVEGADOR_USUARIO.md): Disney+ cards
    /// "Coco Clasificación: 0+…" and "VER AHORA"/"CONTINUAR"; HBO Max cards
    /// wrapped in bidi isolates and "Ver The Last of Us, Temporada 1…" or
    /// "Reanudar Superman…".
    /// </summary>
    internal const string PagePlay = """
        $ErrorActionPreference = 'Stop'
        function Emit([bool]$ok, [string]$step, [string]$chosen, [string[]]$seen = @()) {
          [pscustomobject]@{ version = 1; ok = $ok; step = $step; chosen = $chosen; seen = @($seen) } | ConvertTo-Json -Compress
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
        # The title a card names: its first bidi-isolated run (HBO Max), or its name before the labels Disney+ appends to it
        # ("Coco Clasificacion: 0+. Estreno: 2017..."); otherwise the whole name.
        function CardTitle([string]$name) {
          $isolated = Isolated $name
          if ($isolated) { return $isolated }
          $labels = '\s+(?:(?:Clasificaci[oó]n|Rating|Estreno|Release|G[eé]nero|Genre)\s*:|Selecciona esta opci[oó]n|Select this option)'
          return (Plain ([regex]::Split((Plain $name), $labels, 'IgnoreCase')[0]))
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
          $seen = @()
          $document = $null
          $typed = -not $TypeSearch
          # Auditoría final (regla 3): «the title is not there» only from cards that were read; no card read at all, or the
          # exact card found without a way to press it, is said as that, never as candidates of a missing title.
          $anyCard = $false
          $exactUnpressable = $false
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
              # Only a card named as the title is pressed; the others are what the page showed, said back as they read.
              $exact = $null
              $exactTitle = ''
              $titles = New-Object System.Collections.Generic.List[string]
              foreach ($item in $items) {
                $cardTitle = CardTitle ([string]$item.Current.Name)
                if (-not $cardTitle) { continue }
                $anyCard = $true
                if ((Fold $cardTitle) -eq $want) { $exact = $item; $exactTitle = $cardTitle; break }
                if ($cardTitle.Length -le 120 -and -not $titles.Contains($cardTitle)) { $titles.Add($cardTitle) }
              }
              if ($exact -ne $null -and -not (Press $exact)) { $exactUnpressable = $true }
              elseif ($exact -ne $null) {
                $chosen = $exactTitle
                $chosenFolded = Fold $chosen
                $seen = @()
                Start-Sleep -Milliseconds 2500
                continue
              }
              $near = @($titles | Where-Object { (Fold $_).Contains($want) })
              $seen = if ($near.Count -gt 0) { $near } else { @($titles) }
              $seen = @($seen | Select-Object -First 10)
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
          if ($step -eq 'title' -and $exactUnpressable) { $step = 'title_unpressable'; $seen = @() }
          elseif ($step -eq 'title' -and -not $anyCard) { $step = 'title_unread' }
          Emit $false $step $chosen $seen
        } catch {
          Emit $false ('uia_failed: ' + $_.Exception.GetType().Name) ''
        }
        """;

    /// <summary>
    /// $args[0] = window handle. One read of the browser frame, what the tab steps decide on and verify with: each tab
    /// (title, selected, centre as a fraction of the window, on screen), the back button's state, the address field
    /// and the page document (its UI Automation runtime id, which changes when the page is reloaded or left, its name
    /// and vertical scroll). Chromium names: tabs are TabItem with SelectionItemPattern, the back button carries the
    /// view id «view_1001» (class BackForwardButton in Chrome, BackForwardButtonView in Opera GX), the page is the
    /// Document whose AutomationId is RootWebArea. Never enters a page; the address is only compared by the caller.
    /// </summary>
    internal const string Frame = Walk + """
        $ErrorActionPreference = 'Stop'
        function Fail([string]$reason) {
          [pscustomobject]@{ version = 1; ok = $false; tabs = @(); error = $reason } | ConvertTo-Json -Compress
        }
        try {
          $Window = [long]$args[0]
          if ($Window -eq 0) { Fail 'window_missing'; exit 0 }
          Add-Type -AssemblyName UIAutomationClient
          Add-Type -AssemblyName UIAutomationTypes
          $CT = [System.Windows.Automation.ControlType]
          $root = [System.Windows.Automation.AutomationElement]::FromHandle([IntPtr]$Window)
          $windowTitle = [string]$root.Current.Name
          $frame = $root.Current.BoundingRectangle
          $walker = [System.Windows.Automation.TreeWalker]::ControlViewWalker
          $tabs = New-Object System.Collections.Generic.List[object]
          $documents = New-Object System.Collections.Generic.List[object]
          $back = ''
          $address = ''
          $queue = New-Object System.Collections.Generic.Queue[object]
          $queue.Enqueue(@($root, 0))
          $visited = 0
          # Auditoría final (regla 3): a node or a tab that could not be read, or a walk cut by its limit, leaves the
          # tab list incomplete, never shorter.
          $unreadNodes = 0
          while ($queue.Count -gt 0 -and $visited -lt 2500) {
            $pair = $queue.Dequeue()
            $node = $pair[0]; $depth = $pair[1]
            $visited++
            try { $current = $node.Current; $type = $current.ControlType } catch { $unreadNodes++; continue }
            if ($type -eq $CT::Document) {
              if ($current.AutomationId -eq 'RootWebArea') { $documents.Add($node) }
              continue
            }
            if ($type -eq $CT::TabItem) {
              try {
                $selected = $false; $pattern = $null
                if ($node.TryGetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern, [ref]$pattern)) {
                  $selected = [bool]$pattern.Current.IsSelected
                }
                $box = $current.BoundingRectangle
                $shown = (-not $current.IsOffscreen) -and (-not $box.IsEmpty) -and $box.Width -gt 0 -and $frame.Width -gt 0
                $x = 0.0; $y = 0.0
                if ($shown) {
                  $x = ($box.Left + $box.Width / 2 - $frame.Left) / $frame.Width
                  $y = ($box.Top + $box.Height / 2 - $frame.Top) / $frame.Height
                }
                $tabs.Add([pscustomobject]@{ title = [string]$current.Name; selected = $selected; shown = $shown; x = $x; y = $y })
              } catch { $unreadNodes++ }
              continue
            }
            if ($type -eq $CT::Button -and $back -eq '') {
              if ($current.AutomationId -eq 'view_1001' -or $current.ClassName -match '^BackForwardButton') {
                $back = if ($current.IsEnabled) { 'enabled' } else { 'disabled' }
              }
            }
            if ($type -eq $CT::Edit -and $address -eq '') {
              $pattern = $null
              try {
                if ($node.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern, [ref]$pattern)) {
                  $value = [string]$pattern.Current.Value
                  if ($value -and $value -notmatch '\s' -and $value -match '[\.:/]') { $address = $value }
                }
              } catch { }
            }
            if ($depth -ge 26) { $unreadNodes++; continue }
            foreach ($child in (Children $walker $node)) { $queue.Enqueue(@($child, ($depth + 1))) }
          }
          # The page of the active tab: the document whose name begins the window title (Opera GX also exposes its
          # Speed Dial and side panels as documents), else the first one on screen.
          $page = $null
          foreach ($candidate in $documents) {
            $name = [string]$candidate.Current.Name
            if ($name -and $windowTitle.StartsWith($name)) { $page = $candidate; break }
          }
          if ($page -eq $null) { foreach ($candidate in $documents) { if (-not $candidate.Current.IsOffscreen) { $page = $candidate; break } } }
          $pageId = ''; $pageTitle = ''; $scroll = -1.0
          if ($page -ne $null) {
            $pageId = ($page.GetRuntimeId()) -join '.'
            $pageTitle = [string]$page.Current.Name
            $pattern = $null
            if ($page.TryGetCurrentPattern([System.Windows.Automation.ScrollPattern]::Pattern, [ref]$pattern) -and $pattern.Current.VerticallyScrollable) {
              $scroll = [double]$pattern.Current.VerticalScrollPercent
            }
          }
          $reason = if ($tabs.Count -gt 0) { '' } else { 'tab_strip_not_found' }
          $tabsComplete = $unreadNodes -eq 0 -and $queue.Count -eq 0 -and -not $WalkState.partial
          [pscustomobject]@{
            version = 1; ok = ($tabs.Count -gt 0); tabs = $tabs.ToArray(); tabsComplete = $tabsComplete; back = $back; address = $address
            page = [pscustomobject]@{ id = $pageId; title = $pageTitle; scroll = $scroll }; error = $reason
          } | ConvertTo-Json -Compress -Depth 4
        } catch {
          Fail ('uia_failed: ' + $_.Exception.GetType().Name)
        }
        """;

    /// <summary>
    /// $args[0] = window handle, $args[1] = new_tab | scroll_down | scroll_up | fullscreen_video. The steps UI
    /// Automation itself takes without the keyboard or the foreground: press the tab strip's new-tab button (class
    /// NewTabButton in Chromium, GxAddTabButton in Opera GX), scroll the page by a screen with its ScrollPattern (the
    /// page document, else its first element that scrolls vertically) and read the position back, or press the
    /// page's own full-screen button. It reports the step reached; whether a tab opened or the window went full
    /// screen is read again by the caller.
    /// </summary>
    internal const string Act = Walk + """
        $ErrorActionPreference = 'Stop'
        function Emit([string]$step, [double]$before, [double]$after) {
          [pscustomobject]@{ version = 1; step = $step; before = $before; after = $after } | ConvertTo-Json -Compress
        }
        function Fold([string]$text) {
          if (-not $text) { return '' }
          $decomposed = $text.Normalize([Text.NormalizationForm]::FormD)
          $builder = New-Object Text.StringBuilder
          foreach ($c in $decomposed.ToCharArray()) {
            if ([Globalization.CharUnicodeInfo]::GetUnicodeCategory($c) -ne [Globalization.UnicodeCategory]::NonSpacingMark) { [void]$builder.Append($c) }
          }
          return (($builder.ToString().ToLowerInvariant()) -replace '\s+', ' ').Trim()
        }
        try {
          $Window = [long]$args[0]
          $Action = [string]$args[1]
          if ($Window -eq 0) { Emit 'window_missing' -1 -1; exit 0 }
          Add-Type -AssemblyName UIAutomationClient
          Add-Type -AssemblyName UIAutomationTypes
          $AE = [System.Windows.Automation.AutomationElement]
          $CT = [System.Windows.Automation.ControlType]
          $root = $AE::FromHandle([IntPtr]$Window)
          $windowTitle = [string]$root.Current.Name
          $walker = [System.Windows.Automation.TreeWalker]::ControlViewWalker
          $documents = New-Object System.Collections.Generic.List[object]
          $newTab = $null
          $queue = New-Object System.Collections.Generic.Queue[object]
          $queue.Enqueue(@($root, 0))
          $visited = 0
          while ($queue.Count -gt 0 -and $visited -lt 2500) {
            $pair = $queue.Dequeue()
            $node = $pair[0]; $depth = $pair[1]
            $visited++
            try { $current = $node.Current; $type = $current.ControlType } catch { continue }
            if ($type -eq $CT::Document) {
              if ($current.AutomationId -eq 'RootWebArea') { $documents.Add($node) }
              continue
            }
            if ($type -eq $CT::Button -and $newTab -eq $null -and $current.ClassName -match '(NewTab|AddTab)') { $newTab = $node }
            if ($depth -ge 26) { continue }
            foreach ($child in (Children $walker $node)) { $queue.Enqueue(@($child, ($depth + 1))) }
          }
          if ($Action -eq 'new_tab') {
            $pattern = $null
            if ($newTab -ne $null -and $newTab.TryGetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern, [ref]$pattern)) {
              $pattern.Invoke()
              Emit 'invoked' -1 -1
            } else { Emit 'new_tab_button_not_found' -1 -1 }
            exit 0
          }
          $page = $null
          foreach ($candidate in $documents) {
            $name = [string]$candidate.Current.Name
            if ($name -and $windowTitle.StartsWith($name)) { $page = $candidate; break }
          }
          if ($page -eq $null) { foreach ($candidate in $documents) { if (-not $candidate.Current.IsOffscreen) { $page = $candidate; break } } }
          if ($page -eq $null) { Emit 'page_not_found' -1 -1; exit 0 }
          if ($Action -eq 'scroll_down' -or $Action -eq 'scroll_up') {
            $scroller = $null; $pattern = $null
            if ($page.TryGetCurrentPattern([System.Windows.Automation.ScrollPattern]::Pattern, [ref]$pattern) -and $pattern.Current.VerticallyScrollable) {
              $scroller = $pattern
            } else {
              # Pages that scroll an inner element (mail, chat and video sites): the first one on screen that scrolls vertically.
              $condition = New-Object System.Windows.Automation.PropertyCondition($AE::IsScrollPatternAvailableProperty, $true)
              foreach ($candidate in $page.FindAll([System.Windows.Automation.TreeScope]::Descendants, $condition)) {
                $inner = $candidate.GetCurrentPattern([System.Windows.Automation.ScrollPattern]::Pattern)
                if ($inner.Current.VerticallyScrollable -and -not $candidate.Current.IsOffscreen) { $scroller = $inner; break }
              }
            }
            if ($scroller -eq $null) { Emit 'not_scrollable' -1 -1; exit 0 }
            $before = [double]$scroller.Current.VerticalScrollPercent
            $down = $Action -eq 'scroll_down'
            if (($down -and $before -ge 99.9) -or (-not $down -and $before -le 0.1)) { Emit 'boundary' $before $before; exit 0 }
            $amount = if ($down) { [System.Windows.Automation.ScrollAmount]::LargeIncrement } else { [System.Windows.Automation.ScrollAmount]::LargeDecrement }
            $scroller.Scroll([System.Windows.Automation.ScrollAmount]::NoAmount, $amount)
            $after = $before
            for ($look = 0; $look -lt 8 -and [math]::Abs($after - $before) -lt 0.01; $look++) {
              Start-Sleep -Milliseconds 150
              $after = [double]$scroller.Current.VerticalScrollPercent
            }
            $step = if ([math]::Abs($after - $before) -ge 0.01) { 'scrolled' } else { 'unmoved' }
            Emit $step $before $after
            exit 0
          }
          if ($Action -eq 'fullscreen_video') {
            $words = @('pantalla completa', 'full screen', 'fullscreen', 'plein ecran', 'tela cheia', 'vollbild')
            $condition = New-Object System.Windows.Automation.PropertyCondition($AE::ControlTypeProperty, $CT::Button)
            foreach ($button in $page.FindAll([System.Windows.Automation.TreeScope]::Descendants, $condition)) {
              $name = Fold $button.Current.Name
              foreach ($word in $words) {
                $pattern = $null
                if ($name.StartsWith($word) -and $button.TryGetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern, [ref]$pattern)) {
                  $pattern.Invoke()
                  Emit 'invoked' -1 -1
                  exit 0
                }
              }
            }
            Emit 'fullscreen_control_not_found' -1 -1
            exit 0
          }
          Emit 'action_invalid' -1 -1
        } catch {
          Emit ('uia_failed: ' + $_.Exception.GetType().Name) -1 -1
        }
        """;

    /// <summary>
    /// $args[0] = window handle, $args[1] = maximum characters. The title and the visible text of the page the window
    /// shows: the Document whose AutomationId is RootWebArea (Chromium's page; Opera GX's side panels are other
    /// documents), read with TextPattern, or from its Text nodes when the pattern is missing. Nothing else of the
    /// browser (history, cookies, forms) is read.
    /// </summary>
    internal const string PageText = Walk + """
        $ErrorActionPreference = 'Stop'
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
              foreach ($child in (Children $walker $node)) { $queue.Enqueue(@($child, ($depth + 1))) }
            }
          }
          if ($page -eq $null) { Emit $false '' '' $false 'page_document_not_found'; exit 0 }
          $text = ''
          $walkCut = $false
          $failedNodes = 0
          $pattern = $null
          if ($page.TryGetCurrentPattern([System.Windows.Automation.TextPattern]::Pattern, [ref]$pattern)) {
            $text = [string]$pattern.DocumentRange.GetText($Maximum + 1)
          }
          if (-not $text) {
            $builder = New-Object System.Text.StringBuilder
            $queue = New-Object System.Collections.Generic.Queue[object]
            $queue.Enqueue($page)
            $visited = 0
            # Auditoría final (regla 3): nodes that could not be read, and a walk cut by its node limit, are said: an
            # empty text from a walk that failed is the page not read, never an empty page.
            while ($queue.Count -gt 0 -and $visited -lt 6000 -and $builder.Length -le $Maximum) {
              $node = $queue.Dequeue()
              $visited++
              try {
                if ($node.Current.ControlType -eq $textType) { [void]$builder.Append([string]$node.Current.Name).Append("`n") }
                $child = $walker.GetFirstChild($node)
                while ($child -ne $null) { $queue.Enqueue($child); $child = $walker.GetNextSibling($child) }
              } catch { $failedNodes++ }
            }
            $text = $builder.ToString()
            $walkCut = ($queue.Count -gt 0 -and $builder.Length -le $Maximum) -or $WalkState.partial
            if (-not $text -and ($failedNodes -gt 0 -or $walkCut)) { Emit $false '' '' $false 'page_text_not_read'; exit 0 }
          }
          # A node that failed lost its subtree: the text read is not the whole page either.
          $truncated = $text.Length -gt $Maximum -or $walkCut -or $failedNodes -gt 0
          if ($truncated) { $text = $text.Substring(0, $Maximum) }
          Emit $true ([string]$page.Current.Name) $text $truncated ''
        } catch {
          Emit $false '' '' $false ('uia_failed: ' + $_.Exception.GetType().Name)
        }
        """;
}
