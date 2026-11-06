using System.Diagnostics;
using System.Text;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// FT/proveedores goal (E3): the rules of the user-browser scripts that decide whether the tab strip was read whole
/// (<c>StripOf</c>, <c>StripWhole</c>, over the frame walk's <c>Children</c>) and which document is the page
/// (<c>TitledPage</c>, <c>ShownPage</c>) are taken from the scripts by their syntax tree and run on described
/// elements: no browser or window is read or touched.
/// </summary>
[TestFixture]
public sealed class UserBrowserScriptRulesTests
{
    // Described elements: a node answers Current (ControlType, Name) and GetRuntimeId; a dead one throws from every
    // method, as Opera GX's first LiveBackgroundView child does (PowerShell gives $null for its properties).
    private const string Elements = """
        Add-Type -AssemblyName UIAutomationTypes
        $CT = [System.Windows.Automation.ControlType]
        $WalkState = @{ partial = $false }
        $script:nextId = 1
        function MakeNode([string]$name, $type, [bool]$dead = $false) {
          $n = [pscustomobject]@{ name = $name; kids = (New-Object System.Collections.Generic.List[object]); parent = $null; dead = $dead; id = $script:nextId; ctype = $type }
          $script:nextId++
          $n | Add-Member -MemberType ScriptProperty -Name Current -Value { if ($this.dead) { throw 'dead element' }; [pscustomobject]@{ ControlType = $this.ctype; Name = $this.name } }
          $n | Add-Member -MemberType ScriptMethod -Name GetRuntimeId -Value { if ($this.dead) { throw 'dead element' }; return ,([int[]]@(42, $this.id)) }
          return $n
        }
        function Attach($parent, $child) { $parent.kids.Add($child); $child.parent = $parent; return $child }
        $walker = [pscustomobject]@{ deadFirstOf = @{} }
        $walker | Add-Member -MemberType ScriptMethod -Name GetFirstChild -Value { param($n) if ($n.dead -or $this.deadFirstOf.ContainsKey($n.id)) { throw 'dead element' }; if ($n.kids.Count -gt 0) { return $n.kids[0] }; return $null }
        $walker | Add-Member -MemberType ScriptMethod -Name GetLastChild -Value { param($n) if ($n.dead) { throw 'dead element' }; if ($n.kids.Count -gt 0) { return $n.kids[$n.kids.Count - 1] }; return $null }
        $walker | Add-Member -MemberType ScriptMethod -Name GetNextSibling -Value { param($n) $p = $n.parent; $i = $p.kids.IndexOf($n); if ($i + 1 -lt $p.kids.Count) { return $p.kids[$i + 1] }; return $null }
        $walker | Add-Member -MemberType ScriptMethod -Name GetPreviousSibling -Value { param($n) if ($n.dead) { throw 'dead element' }; $p = $n.parent; $i = $p.kids.IndexOf($n); if ($i -gt 0) { return $p.kids[$i - 1] }; return $null }
        $walker | Add-Member -MemberType ScriptMethod -Name GetParent -Value { param($n) if ($n.dead) { throw 'dead element' }; return $n.parent }
        function Say($value) { if ($null -eq $value) { 'none' } else { [string]$value.name } }
        function Tabs { $list = New-Object System.Collections.Generic.List[object]; foreach ($tab in $args) { $list.Add($tab) }; return ,$list }

        """;

    [Test]
    public void TheTabStripIsReadWholeThoughADeadNodeOutsideItIsNot()
    {
        const string cases = """
            # Opera GX after a Speed Dial: window > LiveBackgroundView > [dead, WindowDecoratorGx > [strip > [T1, T2,
            # island > [T3]], toolbar, page]]; the forward walk of LiveBackgroundView fails at its first child.
            $root = MakeNode 'Window' $CT::Window
            $lbv = Attach $root (MakeNode 'LiveBackgroundView' $CT::Pane)
            $null = Attach $lbv (MakeNode 'dead' $CT::Pane $true)
            $wdg = Attach $lbv (MakeNode 'WindowDecoratorGx' $CT::Pane)
            $strip = Attach $wdg (MakeNode 'TabStrip' $CT::Pane)
            $t1 = Attach $strip (MakeNode 'T1' $CT::TabItem)
            $t2 = Attach $strip (MakeNode 'T2' $CT::TabItem)
            $island = Attach $strip (MakeNode 'Island' $CT::Group)
            $t3 = Attach $island (MakeNode 'T3' $CT::TabItem)
            $null = Attach $wdg (MakeNode 'Toolbar' $CT::ToolBar)
            $null = Attach $wdg (MakeNode 'Page' $CT::Document)
            $walker.deadFirstOf[$lbv.id] = $true
            $answers = @()
            $kids = @(Children $walker $lbv)
            $answers += @([string]$kids.Count + ' ' + [string]$WalkState.partial)
            $found = StripOf $walker $root (Tabs $t1 $t2 $t3)
            $answers += @(Say $found)
            $answers += @([string](StripWhole $walker $found 3))
            $answers += @([string]$WalkState.partial)
            $answers += @([string](StripWhole $walker $found 4))
            $answers += @(Say (StripOf $walker $root (Tabs $t3)))
            # A tab of the strip that cannot be read: the strip is not whole, and a dead tab has no strip.
            $deadTab = Attach $strip (MakeNode 'deadTab' $CT::TabItem $true)
            $answers += @([string](StripWhole $walker $found 3))
            $answers += @(Say (StripOf $walker $root (Tabs $t1 $deadTab)))
            # Tabs in two places of the window: the strip is the node that holds both.
            $other = Attach $wdg (MakeNode 'Pinned' $CT::Pane)
            $t4 = Attach $other (MakeNode 'T4' $CT::TabItem)
            $answers += @(Say (StripOf $walker $root (Tabs $t1 $t4)))
            [Console]::Out.Write(($answers -join '|'))
            """;
        string answer = Run(UserBrowserScripts.Frame, ["Children", "FrameKey", "StripOf", "StripWhole"], cases);
        Assert.That(answer.Split('|'), Is.EqualTo(new[]
        {
            "2 True", "TabStrip", "True", "False", "False", "Island", "False", "none", "WindowDecoratorGx",
        }));
    }

    // Encargo 82: the rows of the page read as Opera GX gives them (measured live): a row and its cells are DataItem with
    // their names, so a cell inside the row before is no row; a list's option has only its whole name; a row off the
    // screen or that cannot be read costs that row.
    [Test]
    public void ThePageReadListsTheRowsOnScreenWithTheirCells()
    {
        const string cases = """
            function Cell([string]$name) { return [pscustomobject]@{ Current = [pscustomobject]@{ Name = $name } } }
            function Row([string]$name, [double]$top, [double]$bottom, [string[]]$kids = @(), [bool]$offscreen = $false) {
              return [pscustomobject]@{
                Cached = [pscustomobject]@{ Name = $name; IsOffscreen = $offscreen; BoundingRectangle = [pscustomobject]@{ Top = $top; Bottom = $bottom } }
                Kids = @($kids | ForEach-Object { Cell $_ })
              }
            }
            $dead = [pscustomobject]@{}
            $dead | Add-Member -MemberType ScriptProperty -Name Cached -Value { throw 'dead element' }
            $found = @(
              (Row 'Uno Dos' 100 120 @('Uno', 'Dos')), (Row 'Uno' 100 120), (Row 'Dos' 100 120), $dead,
              (Row 'Oculta' 120 140 @('Oculta') $true),
              (Row 'Tres Cuatro 10:31' 140 160), (Row '' 160 180), (Row 'Cinco' 180 200 @('', 'Cinco')))
            $rows = PageRowsOf $found 10 5 { param($row) $row.Kids }
            $answers = @($rows | ForEach-Object { [string]$_.top + ':' + ($_.cells -join ',') })
            $cut = PageRowsOf $found 1 5 { param($row) $row.Kids }
            $answers += @([string]$cut.Count)
            [Console]::Out.Write(($answers -join '|'))
            """;
        string answer = Run(UserBrowserScripts.PageText, ["PageRowsOf"], cases);
        Assert.That(answer.Split('|'), Is.EqualTo(new[] { "100:Uno,Dos", "140:Tres Cuatro 10:31", "180:Cinco", "1" }));
    }

    // Encargo 62 (R06): the links of the page read, by name, in the page's order: on screen only, each name once, the list
    // bounded, a cut said, and a link that cannot be read costs that link and never the read.
    [Test]
    public void ThePageReadListsTheNamedLinksShownInThePagesOrder()
    {
        const string cases = """
            function Link([string]$name, [bool]$offscreen = $false) {
              return [pscustomobject]@{ Cached = [pscustomobject]@{ Name = $name; IsOffscreen = $offscreen } }
            }
            $dead = [pscustomobject]@{}
            $dead | Add-Member -MemberType ScriptProperty -Name Cached -Value { throw 'dead element' }
            $found = @((Link 'Uno'), (Link ' Dos '), $dead, (Link 'Oculto' $true), (Link ''), (Link 'Uno'), (Link 'Tres'))
            $answers = @()
            foreach ($bound in @(@(10, 100), @(2, 100), @(10, 6))) {
              $got = PageLinks $found $bound[0] $bound[1]
              $answers += @(($got.names -join ',') + ' ' + [string]$got.cut)
            }
            $got = PageLinks @() 10 100
            $answers += @([string]$got.names.Count + ' ' + [string]$got.cut)
            [Console]::Out.Write(($answers -join '|'))
            """;
        string answer = Run(UserBrowserScripts.PageText, ["PageLinks"], cases);
        Assert.That(answer.Split('|'), Is.EqualTo(new[]
        {
            "Uno,Dos,Tres False", "Uno,Dos True", "Uno,Dos True", "0 False",
        }));
    }

    [Test]
    public void WhatIsOnScreenBeginsAtTheHighestPointThatRunsOnToTheMiddle()
    {
        const string cases = """
            # A document as one string; a range is its two ends in it, as TextPattern gives them.
            function TextRange([string]$all, [int]$from, [int]$to) {
              $r = [pscustomobject]@{ name = ''; all = $all; from = $from; to = $to }
              $r | Add-Member -MemberType ScriptMethod -Name Clone -Value { TextRange $this.all $this.from $this.to }
              $r | Add-Member -MemberType ScriptMethod -Name GetText -Value { param($max) $t = $this.all.Substring($this.from, [Math]::Max(0, $this.to - $this.from)); if ($t.Length -gt $max) { $t.Substring(0, $max) } else { $t } }
              $r | Add-Member -MemberType ScriptMethod -Name CompareEndpoints -Value { param($mine, $other, $theirs) $this.from - $other.from }
              $r | Add-Member -MemberType ScriptMethod -Name MoveEndpointByRange -Value {
                param($mine, $other, $theirs)
                $at = if ([string]$theirs -eq 'Start') { $other.from } else { $other.to }
                if ([string]$mine -eq 'Start') { $this.from = $at } else { $this.to = $at }
              }
              return $r
            }
            Add-Type -AssemblyName UIAutomationClient
            $all = 'x' * 10000
            $document = TextRange $all 0 $all.Length
            function At([string]$name, [int]$place) { $r = TextRange $all $place $place; $r.name = $name; return $r }
            $middle = At 'medio' 6000
            $answers = @()
            # A fixed header, at the start of the document, then the first line of the screen.
            $answers += @(Say (ShownStart $document $middle @((At 'cabecera' 10), (At 'arriba' 5000), (At 'mas abajo' 5500)) 4000))
            $answers += @(Say (ShownStart $document $middle @((At 'arriba' 5000)) 4000))
            # Nothing above that runs on to it: the middle itself.
            $answers += @(Say (ShownStart $document $middle @((At 'cabecera' 10)) 4000))
            $answers += @(Say (ShownStart $document $middle @() 4000))
            # A point above the middle whose text comes after it in the document (a column of its own) is not where it begins.
            $answers += @(Say (ShownStart $document $middle @((At 'otra columna' 9000), (At 'arriba' 5000)) 4000))
            [Console]::Out.Write(($answers -join '|'))
            """;
        string answer = Run(UserBrowserScripts.PageText, ["ShownStart"], cases);
        Assert.That(answer.Split('|'), Is.EqualTo(new[] { "arriba", "arriba", "medio", "medio", "arriba" }));
    }

    [Test]
    public void ThePageIsTheDocumentNamedAsTheWindowTitleBegins()
    {
        const string cases = """
            function Document([string]$name, [bool]$offscreen) {
              return [pscustomobject]@{ name = $name; Current = [pscustomobject]@{ Name = $name; IsOffscreen = $offscreen } }
            }
            $panel = Document 'Discord' $false
            $page = Document 'Valparaiso - Wikipedia' $false
            $hidden = Document 'Speed Dial' $true
            $both = Tabs $panel $page
            $answers = @()
            $answers += @(Say (TitledPage $both 'Valparaiso - Wikipedia - Opera'))
            $answers += @(Say (TitledPage $both 'Otra cosa - Opera'))
            $answers += @(Say (ShownPage (Tabs $hidden $page) $false))
            $answers += @(Say (ShownPage (Tabs $hidden) $true))
            $answers += @(Say (ShownPage (Tabs $hidden) $false))
            [Console]::Out.Write(($answers -join '|'))
            """;
        string page = Run(UserBrowserScripts.PageText, ["TitledPage", "ShownPage"], cases);
        string frame = Run(UserBrowserScripts.Frame, ["TitledPage", "ShownPage"], cases);
        Assert.Multiple(() =>
        {
            Assert.That(page.Split('|'), Is.EqualTo(new[]
            {
                "Valparaiso - Wikipedia", "none", "Valparaiso - Wikipedia", "Speed Dial", "none",
            }));
            Assert.That(frame, Is.EqualTo(page), "the frame read and the page read take the same page");
        });
    }

    [Test]
    public void AnEpisodeCardIsNeverTheTitleAskedAndSaysWhatItIs()
    {
        string cases = "$mark = '" + UserBrowserScripts.EpisodeMark.Replace("'", "''", StringComparison.Ordinal) + "'\n"
            + """
            $i = [string][char]0x2066; $o = [string][char]0x2069
            function Card([string]$name) { return [pscustomobject]@{ Current = [pscustomobject]@{ Name = $name } } }
            function Told($read) {
              $exact = if ($read.exact -ne $null) { $read.exactTitle } else { 'none' }
              $cards = @($read.seen | ForEach-Object { $_.title + '/' + [string]$_.kind })
              return $exact + ' [' + ($cards -join ';') + ']'
            }
            $want = Fold 'Ciudad Ceniza'
            # An episode of another series named as the title, marked beside its title, and a movie holding the title.
            $episode = Card ($i + 'Ciudad Ceniza' + $o + '. Faro Norte, Temporada 2, Episodio 4. Fila 1 de 9')
            $movie = Card ($i + 'Ciudad Ceniza 2' + $o + '. Fila 1 de 9')
            $series = Card ($i + 'Ciudad Ceniza' + $o + '. Fila 2 de 9')
            $answers = @()
            $read = ReadCards @($episode, $movie) $want $mark
            $answers += @(Told $read)
            $answers += @([string]$read.seen[0].label)
            # The series named as the title is the one, after the episode too.
            $answers += @(Told (ReadCards @($episode, $series) $want $mark))
            # A card whose title is its whole name, and the English marks.
            $answers += @(Told (ReadCards @((Card 'T1:E3 Ciudad Ceniza')) $want $mark))
            $answers += @(Told (ReadCards @((Card ($i + 'Ciudad Ceniza' + $o + ' Season 1, Episode 2'))) $want $mark))
            # A title that holds the words itself is no episode.
            $saga = Fold 'Saga Lunar: Episodio 3'
            $answers += @(Told (ReadCards @((Card ($i + 'Saga Lunar: Episodio 3' + $o + '. Fila 1 de 9'))) $saga $mark))
            $answers += @(Told (ReadCards @((Card 'Saga Lunar: Episodio 3')) $saga $mark))
            [Console]::Out.Write(($answers -join '|'))
            """;
        string answer = Run(
            UserBrowserScripts.PagePlay, ["Plain", "Fold", "Isolated", "CardTitle", "IsEpisode", "ReadCards"], cases);
        Assert.That(answer.Split('|'), Is.EqualTo(new[]
        {
            "none [Ciudad Ceniza/episode;Ciudad Ceniza 2/]",
            "Ciudad Ceniza. Faro Norte, Temporada 2, Episodio 4. Fila 1 de 9",
            "Ciudad Ceniza [Ciudad Ceniza/episode]",
            "none [T1:E3 Ciudad Ceniza/episode]",
            "none [Ciudad Ceniza/episode]",
            "Saga Lunar: Episodio 3 []",
            "Saga Lunar: Episodio 3 []",
        }));
    }

    [TestCase(false)]
    [TestCase(true)]
    public void TheCardsTheScriptSawReachTheReceiptWhole(bool oneCard)
    {
        string cases = "$mark = '" + UserBrowserScripts.EpisodeMark.Replace("'", "''", StringComparison.Ordinal) + "'\n"
            + "$single = $" + (oneCard ? "true" : "false") + "\n"
            + """
            $i = [string][char]0x2066; $o = [string][char]0x2069
            function Card([string]$name) { return [pscustomobject]@{ Current = [pscustomobject]@{ Name = $name } } }
            $cards = @((Card ($i + 'Ciudad Ceniza' + $o + '. Faro Norte, T2:E4')))
            if (-not $single) { $cards += @((Card ($i + 'Ciudad Ceniza 2' + $o + '. Fila 1 de 9'))) }
            $read = ReadCards $cards (Fold 'Ciudad Ceniza') $mark
            [Console]::Out.Write((Emit $false 'title' '' $read.seen))
            """;
        string answer = Run(
            UserBrowserScripts.PagePlay, ["Emit", "Plain", "Fold", "Isolated", "CardTitle", "IsEpisode", "ReadCards"],
            cases);
        using var document = System.Text.Json.JsonDocument.Parse(answer);
        UserBrowserPageStep step = WindowsUserBrowserPlatform.ParsePageStep(document.RootElement);
        var episode = new StreamingCard("Ciudad Ceniza", "episode", "Ciudad Ceniza. Faro Norte, T2:E4");
        Assert.That(step.Seen, Is.EqualTo(oneCard ? new[] { episode } : new[] { episode, new StreamingCard("Ciudad Ceniza 2") }));
    }

    private static string Run(string source, string[] functions, string cases)
    {
        string script = """
            $ErrorActionPreference = 'Stop'
            $tokens = $null; $errors = $null
            $ast = [System.Management.Automation.Language.Parser]::ParseFile($env:BAXY_BROWSER_SCRIPT, [ref]$tokens, [ref]$errors)
            if ($errors.Count -gt 0) { throw 'script does not parse' }
            $wanted = @($env:BAXY_BROWSER_FUNCTIONS -split ',')
            $found = @($ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $wanted -contains $node.Name }, $true))
            if ($found.Count -ne $wanted.Count) { throw 'rule functions missing' }
            foreach ($definition in $found) { . ([scriptblock]::Create($definition.Extent.Text)) }

            """ + Elements + cases;
        string file = Path.Combine(Path.GetTempPath(), "baxy-browser-script-" + Guid.NewGuid().ToString("N") + ".ps1");
        File.WriteAllText(file, source, new UTF8Encoding(true));
        try
        {
            var start = new ProcessStartInfo("powershell.exe")
            {
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false,
                CreateNoWindow = true,
            };
            foreach (string argument in new[] { "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand" })
                start.ArgumentList.Add(argument);
            start.ArgumentList.Add(Convert.ToBase64String(Encoding.Unicode.GetBytes(script)));
            start.Environment["BAXY_BROWSER_SCRIPT"] = file;
            start.Environment["BAXY_BROWSER_FUNCTIONS"] = string.Join(',', functions);
            using Process process = Process.Start(start)!;
            Task<string> error = process.StandardError.ReadToEndAsync();
            string output = ChildOutput.Read(process);
            Assert.That(process.WaitForExit(60_000), Is.True, "the rule answers");
            Assert.That(process.ExitCode, Is.EqualTo(0), error.Result);
            return output.Trim();
        }
        finally
        {
            File.Delete(file);
        }
    }
}
