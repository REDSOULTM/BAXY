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
            # The forward walk failed part way: the backward one starts from an empty list, so no child is taken twice.
            $kids.Clear()
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
    /// FT/proveedores goal (E3): the page of the active tab among the RootWebArea documents read, shared by the frame
    /// read and the page read: the one whose name begins the window title (Opera GX also exposes its Speed Dial and
    /// side panels as documents), else the first one on screen.
    /// </summary>
    private const string Pages = """
        function TitledPage($documents, [string]$windowTitle) {
          foreach ($candidate in $documents) {
            $name = ''
            try { $name = [string]$candidate.Current.Name } catch { }
            if ($name -and $windowTitle.StartsWith($name)) { return $candidate }
          }
          return $null
        }
        # $anyHidden: with no document on screen (a minimized window) the first one is taken.
        function ShownPage($documents, [bool]$anyHidden) {
          foreach ($candidate in $documents) {
            $offscreen = $true
            try { $offscreen = [bool]$candidate.Current.IsOffscreen } catch { }
            if (-not $offscreen) { return $candidate }
          }
          if ($anyHidden -and $documents.Count -gt 0) { return $documents[0] }
          return $null
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
    /// Uso real 02-11: how a streaming service marks a card as one episode of a series, beside the card's title, in
    /// its folded form (lower case, no accents): «T2:E4», «S1 E3», «Temporada 2, Episodio 4», «Season 1, Episode 2»,
    /// «Ep. 3». The same pattern for .NET, PowerShell and JavaScript; the page scripts take it as an argument or inline.
    /// </summary>
    internal const string EpisodeMark =
        @"(?<![a-z0-9])(?:[ts]\d{1,2}\s*[:.,|-]?\s*ep?\s*\d{1,3}|(?:episodio|episode|ep\.?)\s*\d{1,4})(?![a-z0-9])";

    /// <summary>
    /// $args[0] = window handle, $args[1] = title (base64 UTF-8), $args[2] =
    /// seconds, $args[3] = "1" to type the title into the page's own search
    /// field first, $args[4] = <see cref="EpisodeMark"/>. On a streaming page the
    /// person's session shows, presses the item named exactly as the title (case,
    /// accents and spacing aside; an episode never is) and then its play control.
    /// It only presses elements named as the title or as a play word and returns
    /// the step reached and the chosen title as the service writes it; when no
    /// item is named as the title it presses nothing and returns the cards it saw
    /// (seen: title, and kind with label for an episode). Playback is verified by the caller
    /// through SMTC, never by this script's word. A "Who's watching?" profile
    /// gate stops it (step "profile"): the person picks their own profile. Names measured in Opera
    /// GX on 2026-10-06 (documentacion/NAVEGADOR_USUARIO.md): Disney+ cards
    /// "Coco Clasificación: 0+…" and "VER AHORA"/"CONTINUAR"; HBO Max cards
    /// wrapped in bidi isolates and "Ver The Last of Us, Temporada 1…" or
    /// "Reanudar Superman…".
    /// </summary>
    internal const string PagePlay = """
        $ErrorActionPreference = 'Stop'
        function Emit([bool]$ok, [string]$step, [string]$chosen, [object[]]$seen = @()) {
          [pscustomobject]@{ version = 1; ok = $ok; step = $step; chosen = $chosen; seen = @($seen) } | ConvertTo-Json -Compress -Depth 4
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
        # Uso real 02-11: a card the service marks as an episode beside its title («T2:E4», «Temporada 2, Episodio 4») is
        # one part of a series, never the movie or series asked for, even named as it. What the card says besides its own
        # title is read; a card whose title is its whole name is read besides the title asked for.
        function IsEpisode([string]$name, [string]$cardTitle, [string]$want, [string]$mark) {
          $rest = Fold $name
          $own = Fold $cardTitle
          if ($own.Length -ge $rest.Length) { $own = $want }
          $at = if ($own) { $rest.IndexOf($own) } else { -1 }
          if ($at -ge 0) { $rest = $rest.Remove($at, $own.Length) }
          return ($rest -match $mark)
        }
        # The cards of the page: the one named as the title, and what the others are as the page names them (those
        # holding the title when any do, ten at most).
        function ReadCards($items, [string]$want, [string]$mark) {
          $exact = $null
          $exactTitle = ''
          $any = $false
          $cards = New-Object System.Collections.Generic.List[object]
          $keys = New-Object System.Collections.Generic.HashSet[string]
          foreach ($item in $items) {
            $name = [string]$item.Current.Name
            $cardTitle = CardTitle $name
            if (-not $cardTitle) { continue }
            $any = $true
            $episode = IsEpisode $name $cardTitle $want $mark
            if (-not $episode -and (Fold $cardTitle) -eq $want) { $exact = $item; $exactTitle = $cardTitle; break }
            if ($cardTitle.Length -gt 120) { continue }
            $card = [ordered]@{ title = $cardTitle }
            if ($episode) {
              $label = Plain $name
              if ($label.Length -gt 160) { $label = $label.Substring(0, 160) }
              $card.kind = 'episode'
              $card.label = $label
            }
            if ($keys.Add($cardTitle + '|' + [string]$card.kind)) { $cards.Add([pscustomobject]$card) }
          }
          $near = @($cards | Where-Object { (Fold ($_.title + ' ' + [string]$_.label)).Contains($want) })
          $seen = if ($near.Count -gt 0) { $near } else { $cards.ToArray() }
          return [pscustomobject]@{ exact = $exact; exactTitle = $exactTitle; any = $any; seen = @($seen | Select-Object -First 10) }
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
          $Mark = [string]$args[4]
          if ($Window -eq 0 -or -not $Title -or -not $Mark) { Emit $false 'arguments' ''; exit 0 }
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
              $read = ReadCards $items $want $Mark
              if ($read.any) { $anyCard = $true }
              if ($read.exact -ne $null -and -not (Press $read.exact)) { $exactUnpressable = $true }
              elseif ($read.exact -ne $null) {
                $chosen = $read.exactTitle
                $chosenFolded = Fold $chosen
                $seen = @()
                Start-Sleep -Milliseconds 2500
                continue
              }
              $seen = @($read.seen)
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
    /// It says apart whether the whole frame was read (complete), whether the tab strip was (tabsComplete) and whether
    /// the page document was the one named as the window title begins (page.matched).
    /// </summary>
    internal const string Frame = Walk + Pages + """
        $ErrorActionPreference = 'Stop'
        function Fail([string]$reason) {
          [pscustomobject]@{ version = 1; ok = $false; tabs = @(); error = $reason } | ConvertTo-Json -Compress
        }
        function FrameKey($element) { return (($element.GetRuntimeId()) -join '.') }
        # FT/proveedores goal (E3): the tab strip is the nearest node that holds every tab read (with Opera GX's islands,
        # the node above them), found from the first tab's parents up to the window; null when a parent cannot be read
        # or a tab is not under the window.
        function StripOf($walker, $root, $tabNodes) {
          try {
            $chain = New-Object System.Collections.Generic.List[object]
            $keys = New-Object System.Collections.Generic.List[string]
            $rootKey = FrameKey $root
            $node = $walker.GetParent($tabNodes[0])
            while ($node -ne $null -and $chain.Count -lt 40) {
              $chain.Add($node)
              $key = FrameKey $node
              $keys.Add($key)
              if ($key -eq $rootKey) { break }
              $node = $walker.GetParent($node)
            }
            if ($chain.Count -eq 0) { return $null }
            $top = 0
            for ($index = 1; $index -lt $tabNodes.Count; $index++) {
              $node = $walker.GetParent($tabNodes[$index])
              $at = -1
              $steps = 0
              while ($node -ne $null -and $at -lt 0 -and $steps -lt 40) {
                $at = $keys.IndexOf((FrameKey $node))
                if ($at -lt 0) { $node = $walker.GetParent($node) }
                $steps++
              }
              if ($at -lt 0) { return $null }
              if ($at -gt $top) { $top = $at }
            }
            return $chain[$top]
          } catch { return $null }
        }
        # FT/proveedores goal (E3): the strip walked again on its own, with a fresh partial flag: whole when every node
        # under it was read, none was cut and it holds as many tabs as the frame walk found. A dead node elsewhere in the
        # frame (Opera GX's first LiveBackgroundView child after a Speed Dial) no longer leaves the tab count unread.
        function StripWhole($walker, $strip, [int]$expected) {
          $WalkState.partial = $false
          $documentType = [System.Windows.Automation.ControlType]::Document
          $tabType = [System.Windows.Automation.ControlType]::TabItem
          $queue = New-Object System.Collections.Generic.Queue[object]
          $queue.Enqueue(@($strip, 0))
          $visited = 0; $unread = 0; $count = 0
          while ($queue.Count -gt 0 -and $visited -lt 1500) {
            $pair = $queue.Dequeue()
            $node = $pair[0]; $depth = $pair[1]
            $visited++
            if ($depth -gt 0) {
              try { $type = $node.Current.ControlType } catch { $unread++; continue }
              if ($type -eq $documentType) { continue }
              if ($type -eq $tabType) { $count++; continue }
            }
            if ($depth -ge 16) { $unread++; continue }
            foreach ($child in (Children $walker $node)) { $queue.Enqueue(@($child, ($depth + 1))) }
          }
          return ($unread -eq 0 -and $queue.Count -eq 0 -and -not $WalkState.partial -and $count -eq $expected)
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
          $tabNodes = New-Object System.Collections.Generic.List[object]
          $unreadTabs = 0
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
              $tabNodes.Add($node)
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
                $tabs.Add([pscustomobject]@{ title = [string]$current.Name; selected = $selected; shown = $shown; x = $x; y = $y; id = (FrameKey $node) })
              } catch { $unreadNodes++; $unreadTabs++ }
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
              } catch { $unreadNodes++ }
            }
            if ($depth -ge 26) { $unreadNodes++; continue }
            foreach ($child in (Children $walker $node)) { $queue.Enqueue(@($child, ($depth + 1))) }
          }
          # The page of the active tab: the document whose name begins the window title (Opera GX also exposes its
          # Speed Dial and side panels as documents), else the first one on screen.
          $page = TitledPage $documents $windowTitle
          $pageMatched = $page -ne $null
          if ($page -eq $null) { $page = ShownPage $documents $false }
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
          # FT/proveedores goal (E3): the whole frame read (complete) and the tab strip read whole (tabsComplete) are
          # said apart. The tabs are counted only on a strip read whole: no tab of it failed, the frame walk was not cut
          # by its node limit (a strip it never reached), and the strip walked again alone was whole.
          $complete = $unreadNodes -eq 0 -and $queue.Count -eq 0 -and -not $WalkState.partial
          $tabsComplete = $complete
          if (-not $complete) {
            $tabsComplete = $false
            if ($tabNodes.Count -gt 0 -and $unreadTabs -eq 0 -and $queue.Count -eq 0) {
              $strip = StripOf $walker $root $tabNodes
              if ($strip -ne $null) { $tabsComplete = [bool](StripWhole $walker $strip $tabNodes.Count) }
            }
          }
          [pscustomobject]@{
            version = 1; ok = ($tabs.Count -gt 0); tabs = $tabs.ToArray(); tabsComplete = $tabsComplete; complete = $complete
            back = $back; address = $address
            page = [pscustomobject]@{ id = $pageId; title = $pageTitle; scroll = $scroll; matched = $pageMatched }; error = $reason
          } | ConvertTo-Json -Compress -Depth 4
        } catch {
          Fail ('uia_failed: ' + $_.Exception.GetType().Name)
        }
        """;

    /// <summary>
    /// $args[0] = window handle, $args[1] = new_tab | scroll_down | scroll_up | fullscreen_video | play_video
    /// ($args[2] = the page's address, base64 UTF-8) | select_tab ($args[2] = the tab's runtime id). The steps UI
    /// Automation itself takes without the keyboard or the foreground: press the tab strip's new-tab button (class
    /// NewTabButton in Chromium, GxAddTabButton in Opera GX), scroll the page by a screen with its ScrollPattern (the
    /// page document, else its first element that scrolls vertically) and read the position back, or press the
    /// page's own full-screen or play button. It reports the step reached; whether a tab opened, the window went full
    /// screen or the video plays is read again by the caller.
    /// </summary>
    internal const string Act = Walk + """
        $ErrorActionPreference = 'Stop'
        function Emit([string]$step, [double]$before, [double]$after) {
          [pscustomobject]@{ version = 1; step = $step; before = $before; after = $after } | ConvertTo-Json -Compress
        }
        function EmitSeen([string]$step, [object[]]$dialogs) {
          [pscustomobject]@{ version = 1; step = $step; before = -1; after = -1; dialogs = @($dialogs) } | ConvertTo-Json -Compress -Depth 5
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
          $tabItem = $null
          $wantTab = if ($Action -eq 'select_tab') { [string]$args[2] } else { '' }
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
            if ($type -eq $CT::TabItem -and $Action -eq 'select_tab' -and $tabItem -eq $null) {
              try { if ((($node.GetRuntimeId()) -join '.') -eq $wantTab) { $tabItem = $node } } catch { }
            }
            if ($depth -ge 26) { continue }
            foreach ($child in (Children $walker $node)) { $queue.Enqueue(@($child, ($depth + 1))) }
          }
          if ($Action -eq 'select_tab') {
            # Uso real 03-11 (U64): the tab of that runtime id selected with its SelectionItemPattern, which every
            # TabItem supports (Microsoft Learn, TabItem control type); whether it became the active tab is read again.
            $pattern = $null
            if ($tabItem -eq $null) { Emit 'tab_not_found' -1 -1; exit 0 }
            if ($tabItem.TryGetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern, [ref]$pattern)) {
              $pattern.Select()
              Emit 'selected' -1 -1
            } else { Emit 'select_unavailable' -1 -1 }
            exit 0
          }
          if ($Action -eq 'new_tab') {
            $pattern = $null
            if ($newTab -ne $null -and $newTab.TryGetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern, [ref]$pattern)) {
              $pattern.Invoke()
              Emit 'invoked' -1 -1
            } else { Emit 'new_tab_button_not_found' -1 -1 }
            exit 0
          }
          if ($Action -eq 'play_video') {
            # Encargo 43: only the page at the address opened (the document's value is its address: same site, same
            # path, every parameter of the address opened), never another tab; there, the first play control on show
            # named only as play, or play with its key hint («Reproducir (k)»).
            $target = [Uri]([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String([string]$args[2])))
            $wantHost = $target.Host -replace '^(www|m)\.', ''
            $wantQuery = @($target.Query.TrimStart('?').Split('&') | Where-Object { $_ })
            $video = $null
            foreach ($candidate in $documents) {
              $pattern = $null; $address = ''
              try {
                if ($candidate.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern, [ref]$pattern)) { $address = [string]$pattern.Current.Value }
              } catch { continue }
              $seen = $null
              if (-not [Uri]::TryCreate($address, [UriKind]::Absolute, [ref]$seen)) { continue }
              if (($seen.Host -replace '^(www|m)\.', '') -ne $wantHost -or $seen.AbsolutePath -ne $target.AbsolutePath) { continue }
              $seenQuery = @($seen.Query.TrimStart('?').Split('&'))
              if (@($wantQuery | Where-Object { $seenQuery -notcontains $_ }).Count -eq 0) { $video = $candidate; break }
            }
            if ($video -eq $null) { Emit 'page_not_found' -1 -1; exit 0 }
            # Encargo 58: the page's own dialogs on show (Chromium gives an ARIA dialog or alertdialog to UI Automation
            # as a Window inside the document), each with its links' names and addresses.
            $dialogs = @()
            $windowCondition = New-Object System.Windows.Automation.PropertyCondition($AE::ControlTypeProperty, $CT::Window)
            $linkCondition = New-Object System.Windows.Automation.PropertyCondition($AE::ControlTypeProperty, $CT::Hyperlink)
            foreach ($dialog in $video.FindAll([System.Windows.Automation.TreeScope]::Descendants, $windowCondition)) {
              try {
                if ($dialog.Current.IsOffscreen) { continue }
                $links = @()
                foreach ($link in $dialog.FindAll([System.Windows.Automation.TreeScope]::Descendants, $linkCondition)) {
                  $pattern = $null; $address = ''
                  if ($link.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern, [ref]$pattern)) { $address = [string]$pattern.Current.Value }
                  $links += [pscustomobject]@{ name = [string]$link.Current.Name; address = $address }
                }
                $dialogs += [pscustomobject]@{ name = [string]$dialog.Current.Name; links = $links }
              } catch { continue }
            }
            $words = @('reproducir', 'play', 'lire', 'reproduzir', 'wiedergabe', 'abspielen')
            $condition = New-Object System.Windows.Automation.PropertyCondition($AE::ControlTypeProperty, $CT::Button)
            foreach ($button in $video.FindAll([System.Windows.Automation.TreeScope]::Descendants, $condition)) {
              $name = Fold $button.Current.Name
              if ($button.Current.IsOffscreen) { continue }
              foreach ($word in $words) {
                $pattern = $null
                if (($name -eq $word -or $name.StartsWith($word + ' (')) -and $button.TryGetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern, [ref]$pattern)) {
                  $pattern.Invoke()
                  EmitSeen 'invoked' $dialogs
                  exit 0
                }
              }
            }
            EmitSeen 'play_control_not_found' $dialogs
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
          if ($Action -eq 'exit_fullscreen') {
            $words = @('salir de pantalla completa', 'salir del modo de pantalla completa', 'exit full screen', 'exit fullscreen', 'quitter le mode plein ecran', 'sair da tela cheia', 'vollbild beenden')
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
    /// shows: the Document whose AutomationId is RootWebArea and whose name begins the window title (Chromium's page;
    /// Opera GX's side panels are other documents), read with TextPattern, or from its Text nodes when the pattern is
    /// missing. Nothing else of the browser (history, cookies, forms) is read.
    /// </summary>
    internal const string PageText = Walk + Pages + """
        $ErrorActionPreference = 'Stop'
        function Emit([bool]$ok, [string]$title, [string]$text, [bool]$truncated, [string]$reason, [bool]$matched = $true, [string[]]$links = @(), [bool]$linksCut = $false, [object[]]$rows = @(), [object[]]$nodes = @(), [bool]$fromScreen = $false, [bool]$canScrollDown = $false) {
          [pscustomobject]@{ version = 1; ok = $ok; title = $title; text = $text; truncated = $truncated; matched = $matched; links = $links; linksCut = $linksCut; rows = @($rows); nodes = @($nodes); fromScreen = $fromScreen; canScrollDown = $canScrollDown; error = $reason } | ConvertTo-Json -Compress -Depth 4
        }
        # Uso-108: a long page the person scrolled is read from what is on screen: from its start the budget never reached it, and
        # the same text came back after any scroll (measured 05-11 in Edge and Chrome, at 62 % of a page: the first 6,000
        # characters, with paragraph 232 on screen). Nothing is said of a page not scrolled, read as ever. So is one that scrolls
        # an inner part: Chromium shows no scroll pattern for it, and nothing says it moved. By the text under points of the
        # screen, not by the visible ranges: those walk the document (0.6 s for 400 paragraphs, past their timeout at 30,000;
        # a point, 1 to 95 ms).
        function ShownPart($page, $pattern, [int]$maximum, [string]$top) {
          # Where what is on screen begins: the highest point whose text runs on to the text at the middle of the screen. A fixed
          # header is on screen too, but it lies at the start of the document, with far more text hidden before the middle.
          function ShownStart($document, $middle, $higher, [int]$screenful) {
            $endpoint = [System.Windows.Automation.Text.TextPatternRangeEndpoint]
            foreach ($candidate in @($higher)) {
              if ($candidate.CompareEndpoints($endpoint::Start, $middle, $endpoint::Start) -gt 0) { continue }
              $between = $document.Clone()
              [void]$between.MoveEndpointByRange($endpoint::Start, $candidate, $endpoint::Start)
              [void]$between.MoveEndpointByRange($endpoint::End, $middle, $endpoint::Start)
              if (([string]$between.GetText($screenful + 1)).Length -le $screenful) { return $candidate }
            }
            return $middle
          }
          # A point in the gap between two lines gives a place inside one: its line, whole.
          function LineAt($share) {
            $line = $pattern.RangeFromPoint((New-Object System.Windows.Point(($box.Left + $box.Width * 0.5), ($box.Top + $box.Height * $share))))
            $line.ExpandToEnclosingUnit([System.Windows.Automation.Text.TextUnit]::Line)
            return $line
          }
          $scroller = $null
          if (-not $page.TryGetCurrentPattern([System.Windows.Automation.ScrollPattern]::Pattern, [ref]$scroller) -or -not $scroller.Current.VerticallyScrollable -or [double]$scroller.Current.VerticalScrollPercent -le 0) { return $null }
          $box = $page.Current.BoundingRectangle
          $middle = LineAt 0.5
          $higher = foreach ($share in 0.02, 0.1, 0.2, 0.3, 0.4) { LineAt $share }
          $document = $pattern.DocumentRange
          $range = $document.Clone()
          $endpoint = [System.Windows.Automation.Text.TextPatternRangeEndpoint]
          [void]$range.MoveEndpointByRange($endpoint::Start, (ShownStart $document $middle $higher 4000), $endpoint::Start)
          $text = [string]$range.GetText($maximum + 1)
          # What shows is what the start already gave: the page is read as ever.
          if (($text -replace '\s+', ' ').Trim() -ceq ($top -replace '\s+', ' ').Trim()) { return $null }
          return $text
        }
        # Encargo 82: the rows on screen (a table's or a grid's, a list's items), each with its place and the text of its
        # cells in order; PageRows reads them. Bounded: a page's first rows, a few short cells of each. Measured live in
        # Opera GX: a row and its cells are all DataItem, each with its name and no Text inside (a cell of the row before
        # lies within it, and is skipped); a list's option has only its whole name.
        function PageRowsOf($found, [int]$count, [int]$cells, $children) {
          $rows = New-Object System.Collections.Generic.List[object]
          $lastTop = -1.0; $lastBottom = -1.0
          foreach ($row in $found) {
            if ($rows.Count -ge $count) { break }
            try {
              if ([bool]$row.Cached.IsOffscreen) { continue }
              $box = $row.Cached.BoundingRectangle
              if ($box.Top -ge $lastTop -and $box.Bottom -le $lastBottom) { continue }
              $texts = New-Object System.Collections.Generic.List[string]
              foreach ($piece in (& $children $row)) {
                if ($texts.Count -ge $cells) { break }
                $name = ([string]$piece.Current.Name).Trim()
                if ($name) { $texts.Add($(if ($name.Length -gt 80) { $name.Substring(0, 80) } else { $name })) }
              }
              if ($texts.Count -eq 0) {
                $name = ([string]$row.Cached.Name).Trim()
                if ($name) { $texts.Add($(if ($name.Length -gt 240) { $name.Substring(0, 240) } else { $name })) }
              }
              if ($texts.Count -gt 0) {
                $rows.Add([pscustomobject]@{ top = $box.Top; bottom = $box.Bottom; cells = $texts.ToArray() })
                $lastTop = $box.Top; $lastBottom = $box.Bottom
              }
            } catch { continue }
          }
          return ,$rows.ToArray()
        }
        # Encargo 62 (R06): the links on screen by name, in the page's order, each name once, so that a later «open that
        # one» has what to click. Bounded beside the 6,000 characters of text in the receipt's 8 KiB (OperationVisibleFacts).
        function PageLinks($found, [int]$count, [int]$chars) {
          $names = New-Object System.Collections.Generic.List[string]
          $seen = New-Object 'System.Collections.Generic.HashSet[string]'
          $used = 0
          foreach ($link in $found) {
            $name = ''
            try {
              if ([bool]$link.Cached.IsOffscreen) { continue }
              $name = ([string]$link.Cached.Name).Trim()
            } catch { continue }
            if (-not $name -or -not $seen.Add($name)) { continue }
            if ($names.Count -ge $count -or $used + $name.Length -gt $chars) { return [pscustomobject]@{ names = $names; cut = $true } }
            $names.Add($name)
            $used += $name.Length
          }
          return [pscustomobject]@{ names = $names; cut = $false }
        }
        # Uso-111 (P3): the page's links and text in document order, for PageBlocks: each with its depth, the node it lies
        # under (a heading is a Text that holds its link or lies in one: no level reaches the managed client) and the
        # shallowest depth walked since the node before, which says a container was left; a blank between two pieces of a
        # line is said too. One cached tree brings it all at
        # once (measured: 21 ms for a page of 37 nodes, against seconds for a walk). Bounded by the text's characters.
        function PageNodesOf($page, [int]$chars, [double]$above = [double]::NegativeInfinity) {
          $element = [System.Windows.Automation.AutomationElement]
          $valueProperty = [System.Windows.Automation.ValuePattern]::ValueProperty
          $cache = New-Object System.Windows.Automation.CacheRequest
          $cache.Add($element::NameProperty)
          $cache.Add($element::ControlTypeProperty)
          $cache.Add($element::BoundingRectangleProperty)
          $cache.Add($valueProperty)
          $cache.TreeScope = [System.Windows.Automation.TreeScope]'Element,Descendants'
          $cache.AutomationElementMode = [System.Windows.Automation.AutomationElementMode]::None
          $active = $cache.Activate()
          try { $tree = $page.GetUpdatedCache($cache) } finally { $active.Dispose() }
          $link = [System.Windows.Automation.ControlType]::Hyperlink
          $plain = [System.Windows.Automation.ControlType]::Text
          $nodes = New-Object System.Collections.Generic.List[object]
          $stack = New-Object System.Collections.Generic.Stack[object]
          $stack.Push(@($tree, 0, -1))
          $used = 0
          $visited = 0
          $rise = 0
          $gap = $false
          # What lies above the screen is not worth the limit; this runs apart, with a limit of its own in time.
          $most = if ([double]::IsNegativeInfinity($above)) { 6000 } else { 60000 }
          while ($stack.Count -gt 0 -and $used -lt (2 * $chars) -and $visited -lt $most) {
            $triple = $stack.Pop()
            $node = $triple[0]; $depth = $triple[1]; $under = $triple[2]
            $visited++
            if ($depth -lt $rise) { $rise = $depth }
            $type = $node.Cached.ControlType
            if ($type -eq $link -or $type -eq $plain) {
              $name = [string]$node.Cached.Name
              $box = $node.Cached.BoundingRectangle
              # With no box a node shows nothing, and its Infinity would make the whole result no JSON. A page read from the
              # part on screen leaves out what lies above it, as its text does.
              if ($box.IsEmpty -or $box.Bottom -le $above) { $name = '' }
              if ($name.Trim()) {
                $address = ''
                if ($type -eq $link) { try { $address = [string]$node.GetCachedPropertyValue($valueProperty) } catch { } }
                $nodes.Add([pscustomobject]@{ link = ($type -eq $link); name = $name; address = $address; depth = $depth; under = $under; rise = $rise; gap = $gap; top = $box.Top; bottom = $box.Bottom })
                $used += $name.Length
                $under = $nodes.Count - 1
                $rise = [int]::MaxValue
                $gap = $false
              } elseif ($name) { $gap = $true }
            }
            $children = @($node.CachedChildren)
            for ($child = $children.Count - 1; $child -ge 0; $child--) { $stack.Push(@($children[$child], ($depth + 1), $under)) }
          }
          return ,$nodes.ToArray()
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
          $pageMatched = $false
          $searchPartial = $false
          # Chromium builds the page's accessibility tree on the first request, and a heavy page takes longer: up to
          # three looks over about two seconds. FT/proveedores goal (E3): the page is the RootWebArea whose name begins
          # the window title, as the frame read takes it (Opera GX's side panels and Speed Dial are documents too); only
          # when no look finds one is the first document on screen taken.
          for ($look = 0; $look -lt 3 -and -not $pageMatched; $look++) {
            if ($look -gt 0) { Start-Sleep -Milliseconds 800 }
            $WalkState.partial = $false
            $windowTitle = ''
            try { $windowTitle = [string]$root.Current.Name } catch { }
            $documents = New-Object System.Collections.Generic.List[object]
            $queue = New-Object System.Collections.Generic.Queue[object]
            $queue.Enqueue(@($root, 0))
            $visited = 0
            while ($queue.Count -gt 0 -and $visited -lt 3000) {
              $pair = $queue.Dequeue()
              $node = $pair[0]; $depth = $pair[1]
              $visited++
              try { $type = $node.Current.ControlType } catch { continue }
              if ($type -eq $document) {
                try { if ($node.Current.AutomationId -eq 'RootWebArea') { $documents.Add($node) } } catch { }
                continue
              }
              if ($depth -ge 28) { continue }
              foreach ($child in (Children $walker $node)) { $queue.Enqueue(@($child, ($depth + 1))) }
            }
            $page = TitledPage $documents $windowTitle
            $pageMatched = $page -ne $null
            if (-not $pageMatched) {
              $page = ShownPage $documents $true
              $searchPartial = $WalkState.partial -or $queue.Count -gt 0
            }
          }
          if ($page -eq $null) { Emit $false '' '' $false 'page_document_not_found'; exit 0 }
          # The text walk below says its own cuts; a document taken without the title match from a search that did not
          # read the whole window may not be the page on show, and is said as a partial read too.
          $WalkState.partial = $searchPartial
          $text = ''
          $walkCut = $false
          $failedNodes = 0
          $pattern = $null
          $shown = $null
          if ($page.TryGetCurrentPattern([System.Windows.Automation.TextPattern]::Pattern, [ref]$pattern)) {
            $text = [string]$pattern.DocumentRange.GetText($Maximum + 1)
            if ($text.Length -gt $Maximum) {
              try { $shown = ShownPart $page $pattern $Maximum $text } catch { $shown = $null }
              if ($shown) { $text = $shown } else { $shown = $null }
            }
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
          if ($text.Length -gt $Maximum) { $text = $text.Substring(0, $Maximum) }
          # Encargo 62: one cached search brings every link's name at once (measured in Edge, 5,000 links: 1.8 s; a walk
          # of 1,500 nodes took 9.3 s and saw fewer). Links that cannot be read leave the text as it was read.
          $links = @()
          $linksCut = $false
          try {
            $cache = New-Object System.Windows.Automation.CacheRequest
            $cache.Add([System.Windows.Automation.AutomationElement]::NameProperty)
            $cache.Add([System.Windows.Automation.AutomationElement]::IsOffscreenProperty)
            $cache.AutomationElementMode = [System.Windows.Automation.AutomationElementMode]::None
            $hyperlink = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty, [System.Windows.Automation.ControlType]::Hyperlink)
            $active = $cache.Activate()
            try { $found = $page.FindAll([System.Windows.Automation.TreeScope]::Descendants, $hyperlink) } finally { $active.Dispose() }
            $read = PageLinks $found 40 1024
            $links = $read.names.ToArray()
            $linksCut = $read.cut
          } catch { }
          $rows = @()
          try {
            $cache = New-Object System.Windows.Automation.CacheRequest
            $cache.Add([System.Windows.Automation.AutomationElement]::NameProperty)
            $cache.Add([System.Windows.Automation.AutomationElement]::IsOffscreenProperty)
            $cache.Add([System.Windows.Automation.AutomationElement]::BoundingRectangleProperty)
            $typeProperty = [System.Windows.Automation.AutomationElement]::ControlTypeProperty
            $isRow = New-Object System.Windows.Automation.OrCondition(
              (New-Object System.Windows.Automation.PropertyCondition($typeProperty, [System.Windows.Automation.ControlType]::DataItem)),
              (New-Object System.Windows.Automation.PropertyCondition($typeProperty, [System.Windows.Automation.ControlType]::ListItem)))
            $active = $cache.Activate()
            try { $found = $page.FindAll([System.Windows.Automation.TreeScope]::Descendants, $isRow) } finally { $active.Dispose() }
            $rows = PageRowsOf $found 40 12 { param($row) $row.FindAll([System.Windows.Automation.TreeScope]::Children, [System.Windows.Automation.Condition]::TrueCondition) }
          } catch { }
          $nodes = @()
          # The whole tree of a huge page takes seconds (a page of 200,000 nodes, 19 s, past this script's 20): apart, with
          # its own limit; past it the page is read as text, as before.
          try {
            $apart = [powershell]::Create()
            $above = if ($shown -ne $null) { [double]$page.Current.BoundingRectangle.Top } else { [double]::NegativeInfinity }
            [void]$apart.AddScript(${function:PageNodesOf}.ToString()).AddArgument($page).AddArgument($Maximum).AddArgument($above)
            $running = $apart.BeginInvoke()
            if ($running.AsyncWaitHandle.WaitOne(4000)) { $nodes = @($apart.EndInvoke($running) | ForEach-Object { $_ }) }
          } catch { }
          $canScrollDown = $false
          try {
            $scroller = $null
            if ($page.TryGetCurrentPattern([System.Windows.Automation.ScrollPattern]::Pattern, [ref]$scroller) -and $scroller.Current.VerticallyScrollable) {
              $canScrollDown = [double]$scroller.Current.VerticalScrollPercent -lt 99.9
            }
          } catch { }
          Emit $true ([string]$page.Current.Name) $text $truncated '' $pageMatched $links $linksCut $rows $nodes ($shown -ne $null) $canScrollDown
        } catch {
          Emit $false '' '' $false ('uia_failed: ' + $_.Exception.GetType().Name)
        }
        """;
}
