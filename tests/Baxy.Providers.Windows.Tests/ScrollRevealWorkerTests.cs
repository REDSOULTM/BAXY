using System.Diagnostics;
using System.Text;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// cu-v3-scroll-pegar-direccion, t-scroll-1 (pasada r9): «bajá en la lista hasta el Bloc de notas» en Aplicaciones
/// instaladas. Measured in the journal: the reveal by name answered nothing within the adapter's 15 s
/// (<c>scroll_receipt_invalid</c>, 15.6 s): the list's row is named «Bloc de notas, 11.2…, Microsoft Corporation, …»,
/// never «Bloc de notas», so the exact match found nothing and the page-by-page search walked the whole window after
/// every page. Auditoría C10: such a row is never revealed for the label; its name comes back as a candidate, for the
/// model to name it as it is. The worker's own functions, taken from its text, run here on stand-in elements.
/// </summary>
[TestFixture]
public sealed class ScrollRevealWorkerTests
{
    // The name functions of the worker, from its text, with stand-ins for the tree it walks.
    private const string Prelude = """
        $text=[IO.File]::ReadAllText($env:BAXY_REVEAL_WORKER)
        function Take([string]$from,[string]$to){
          $start=$text.IndexOf($from); $end=$text.IndexOf($to,$start+1)
          if($start -lt 0 -or $end -lt $start){ throw "missing $from" }
          return $text.Substring($start,$end-$start)
        }
        Invoke-Expression (Take 'function Test-NameMatch(' '# El nombre lleva la etiqueta')
        Invoke-Expression (Take '$script:TitledKinds=' '# Lo que un control ofrece')
        Invoke-Expression (Take 'function Find-AnyNamed(' 'function Test-Shown(')
        function Row([string]$name,[string]$kind='ControlType.ListItem'){
          [pscustomobject]@{ Name=$name; Current=[pscustomobject]@{ ControlType=[pscustomobject]@{ ProgrammaticName=$kind } } }
        }
        function Get-ShownName($el){ return $el.Name }

        """;

    [Test]
    public void ARowNamedWithItsDetailsIsACandidateNeverAHit()
    {
        string output = Run("""
            function Get-Descendants($root){ return @((Row 'BAXY, 1.0.9, BAXY, 27-07-2026'), (Row 'Bloc de notas, 11.2507.26.0, Microsoft Corporation, 20-07-2026')) }
            $hits=@(Find-AnyNamed $null @('bloc de notas'))
            "$($hits.Count)|$($script:NamedCandidates -join ';')"
            """);
        Assert.That(output, Is.EqualTo("0|Bloc de notas, 11.2507.26.0, Microsoft Corporation, 20-07-2026"));
    }

    [Test]
    public void CounterCaseAnExactNameWinsOverTheRowsThatHoldIt()
    {
        string output = Run("""
            function Get-Descendants($root){ return @((Row 'Bloc de notas, 11.2, Microsoft'), (Row 'Bloc de notas' 'ControlType.Button')) }
            $hits=@(Find-AnyNamed $null @('Bloc de notas'))
            "$($hits.Count)|$($hits[0].Current.ControlType.ProgrammaticName)"
            """);
        Assert.That(output, Is.EqualTo("1|ControlType.Button"));
    }

    [Test]
    public void CounterCaseAPaneOrAPartOfAWordIsNoRowThatHoldsTheName()
    {
        string output = Run("""
            function Get-Descendants($root){ return @((Row 'Bloc de notas, 11.2' 'ControlType.Pane'), (Row 'Bloc de notasX, 1.0')) }
            @(Find-AnyNamed $null @('bloc de notas')).Count
            """);
        Assert.That(output, Is.EqualTo("0"));
    }

    [Test]
    public void TheWorkerAnswersARevealBeforeTheAdaptersBudget()
    {
        string text = File.ReadAllText(WorkerPath());
        Assert.Multiple(() =>
        {
            Assert.That(text, Does.Contain("$script:RevealSeconds=11"), "under the adapter's 15 s");
            Assert.That(text, Does.Contain("Find-AnyNamed $holder $aliases"), "each page re-reads only what scrolls");
            Assert.That(text, Does.Contain("$owner=Find-ScrollOwner $element $target.root"),
                "a control without its own ScrollPattern scrolls by the container that holds it");
        });
    }

    [Test]
    public void AWalkPastTheDeadlineStopsReadingNames()
    {
        // Each name read crosses to the window's process: past the worker's deadline the walk stops with what it has.
        string output = Run("""
            $script:reads=0
            function Get-ShownName($el){ $script:reads++; Start-Sleep -Milliseconds 25; return $el.Name }
            function Get-Descendants($root){ return @(1..40 | ForEach-Object { Row "Otra fila $_" }) }
            $until=[DateTime]::UtcNow.AddMilliseconds(200)
            $hits=@(Find-AnyNamed $null @('bloc de notas') $until)
            $partial=$script:reads
            $passed=@(Find-AnyNamed $null @('bloc de notas') ([DateTime]::UtcNow.AddSeconds(-1)))
            "$($hits.Count)|$($partial -lt 40)|$($passed.Count)|$($script:reads -eq $partial)"
            """);
        Assert.That(output, Is.EqualTo("0|True|0|True"));
    }

    [Test]
    public void ARowThatOnlyHoldsTheLabelWaitsForTheExactRowOfTheContainer()
    {
        // «Spotify Widget» is shown, «Spotify» is further down and not loaded: the container's exact row comes first.
        string output = Run(RevealPrelude + """
            function Get-Descendants($root){ return @((Row 'Spotify Widget' 'ControlType.ListItem' $true)) }
            function Find-InContainers($root,[string[]]$aliases,$until,[ref]$touched){
              $touched.Value=$true
              return (Reveal-Result $true '' 'itemcontainer' (Row 'Spotify' 'ControlType.ListItem' $true))
            }
            $answer=Do-Reveal @{ aliases=@('Spotify'); hwnd=1; direction='down'; amount=1 }
            "$($answer.method)|$($answer.name)"
            """);
        Assert.That(output, Is.EqualTo("itemcontainer|Spotify"));
    }

    [Test]
    public void CounterCaseAShownExactRowAnswersAlreadyWithoutTheContainers()
    {
        string output = Run(RevealPrelude + """
            function Get-Descendants($root){ return @((Row 'Spotify Widget' 'ControlType.ListItem' $true), (Row 'Spotify' 'ControlType.ListItem' $true)) }
            function Find-InContainers($root,[string[]]$aliases,$until,[ref]$touched){ throw 'the containers were searched' }
            $answer=Do-Reveal @{ aliases=@('Spotify'); hwnd=1; direction='down'; amount=1 }
            "$($answer.method)|$($answer.name)"
            """);
        Assert.That(output, Is.EqualTo("already|Spotify"));
    }

    [Test]
    public void WithoutTheExactRowTheShownRowThatHoldsTheLabelIsOnlyACandidate()
    {
        string output = Run(RevealPrelude + """
            function Get-Descendants($root){ return @((Row 'Bloc de notas, 11.2, Microsoft' 'ControlType.ListItem' $true)) }
            function Find-InContainers($root,[string[]]$aliases,$until,[ref]$touched){ return $null }
            $answer=Do-Reveal @{ aliases=@('bloc de notas'); hwnd=1; direction='down'; amount=1 }
            "$($answer.method)|$($answer.ok)|$($answer.error)|$(@($answer.candidates) -join ';')"
            """);
        Assert.That(output, Is.EqualTo("|False|reveal_not_found|Bloc de notas, 11.2, Microsoft"));
    }

    // Uso-108, the exact rule of agent-desktop's scroll_ladder.rs visibility_verified.
    [TestCase("10,10,100,20", "0,0,200,100", "True", TestName = "Wholly inside its list is seen")]
    [TestCase("10,90,100,20", "0,0,200,100", "False", TestName = "A row cut by the bottom of its list is not seen")]
    [TestCase("10,-5,100,20", "0,0,200,100", "False", TestName = "A row cut by the top of its list is not seen")]
    [TestCase("10,300,100,20", "0,0,200,100", "False", TestName = "Outside its list is not seen")]
    [TestCase("10,10,500,20", "0,0,200,100", "True", TestName = "Wider than its list and touching it is seen")]
    [TestCase("500,10,500,20", "0,0,200,100", "False", TestName = "Wider than its list and away from it is not seen")]
    [TestCase("10,81,100,20", "0,0,200,100", "True", TestName = "One pixel of rounding is seen")]
    [TestCase("150,10,100,20", "0,0,200,100", "True", TestName = "Cut sideways only is seen (a deep row of a narrow tree)")]
    [TestCase("150,90,100,20", "0,0,200,100", "False", TestName = "Cut sideways and by the bottom is not seen")]
    [TestCase("10,10,100,20", "", "True", TestName = "Counter case a list that publishes no viewport never hides a row (Explorer)")]
    [TestCase("10,10,0,20", "", "False", TestName = "No area is not seen")]
    public void WhatCountsAsSeen(string box, string viewport, string seen)
    {
        static string Rect(string kind, string text) => text.Length == 0
            ? "$null"
            : "(" + kind + " " + text.Replace(',', ' ') + ")";
        string output = Run(RevealPrelude + $$"""
            Test-BoxShown {{Rect("Box", box)}} {{Rect("View", viewport)}}
            """);
        Assert.That(output, Is.EqualTo(seen));
    }

    // hondo 14 finding 1: «already», revealed false, for a row with 2 px inside its list; the next press hit the neighbour.
    [Test]
    public void ARowCutByItsListIsNotAlreadySeen()
    {
        string output = Run(RevealPrelude + """
            $script:Viewport=View 0 0 200 25
            $row=Row 'Spotify' 'ControlType.ListItem' $true
            $row | Add-Member -MemberType ScriptMethod -Name TryGetCurrentPattern -Value { param($p,$r) return $false }
            function Get-Descendants($root){ return @($row) }
            function Find-InContainers($root,[string[]]$aliases,$until,[ref]$touched){ throw 'the row in sight in part is not searched for again' }
            Test-Shown $row
            Test-PartlyShown $row
            $answer=Do-Reveal @{ aliases=@('Spotify'); hwnd=1; direction='down'; amount=1 }
            "$($answer.method)|$($answer.ok)|$($answer.visible)"
            """);
        Assert.That(output.Split('\n').Select(static line => line.Trim()), Is.EqualTo(new[] { "False", "True", "already|True|True" }),
            "no pattern can bring it further: in sight in part, as before, and no turn of pages away from it");
    }

    // Merge of uso-108: two routes each defined a Get-ScrollViewport, one answering x,y,w,h and one a Rect, and the last one
    // defined won at run time: the pointer's Get-VisiblePart read no width and took a cut row for whole.
    [Test]
    public void NoFunctionIsDefinedTwiceInTheWorker()
    {
        string[] twice = [.. File.ReadAllLines(WorkerPath())
            .Where(static line => line.StartsWith("function ", StringComparison.Ordinal))
            .Select(static line => line["function ".Length..].Split('(', '{', ' ')[0])
            .GroupBy(static name => name, StringComparer.OrdinalIgnoreCase)
            .Where(static group => group.Count() > 1)
            .Select(static group => group.Key)];
        Assert.That(twice, Is.Empty);
    }

    // Both routes read the one viewport: reveal says a cut row is not seen, the press keeps to its part in sight.
    [Test]
    public void TheOneViewportServesRevealAndThePress()
    {
        string output = Run(RevealPrelude + """
            Add-Type -AssemblyName UIAutomationClient
            Invoke-Expression (Take 'function Get-ScrollViewport(' '# Lo que se ve del rectangulo')
            Invoke-Expression (Take 'function Get-VisiblePart(' '# El centro y los cuatro')
            Invoke-Expression (Take 'function Get-CurrentRect(' '# Pulsa el control por la primera')
            $list=[pscustomobject]@{ Current=[pscustomobject]@{ BoundingRectangle=(Box 0 0 200 100) } }
            $list | Add-Member -MemberType ScriptMethod -Name TryGetCurrentPattern -Value { param($p,$r) return $true }
            function Get-ParentOf($node){ return $list }
            $row=[pscustomobject]@{ Current=[pscustomobject]@{ IsOffscreen=$false; BoundingRectangle=(Box 10 90 100 20) } }
            $part=Get-VisiblePart @{ x=10; y=90; w=100; h=20 } (Get-ScrollViewport $row)
            "$(Test-Shown $row)|$(Test-PartlyShown $row)|$($part.y)|$($part.h)"
            """);
        Assert.That(output, Is.EqualTo("False|True|90|10"));
    }

    // The trap agent-desktop shipped: with no viewport known, today's answer stays.
    [Test]
    public void CounterCaseWithNoViewportAShownRowIsStillAlreadySeen()
    {
        string output = Run(RevealPrelude + """
            function Get-Descendants($root){ return @((Row 'Spotify' 'ControlType.ListItem' $true)) }
            function Find-InContainers($root,[string[]]$aliases,$until,[ref]$touched){ throw 'searched' }
            $answer=Do-Reveal @{ aliases=@('Spotify'); hwnd=1; direction='down'; amount=1 }
            "$($answer.method)|$($answer.visible)"
            """);
        Assert.That(output, Is.EqualTo("already|True"));
    }

    // A row off the list entirely is out of sight: it goes on to the containers as a row with IsOffscreen did.
    [Test]
    public void ARowAwayFromItsListGoesOnToTheContainers()
    {
        string output = Run(RevealPrelude + """
            $script:Viewport=View 0 500 200 100
            $row=Row 'Spotify' 'ControlType.ListItem' $true
            $row | Add-Member -MemberType ScriptMethod -Name TryGetCurrentPattern -Value { param($p,$r) return $false }
            function Get-Descendants($root){ return @($row) }
            function Find-InContainers($root,[string[]]$aliases,$until,[ref]$touched){
              $touched.Value=$true
              $script:Viewport=View 0 0 200 100
              return (Reveal-Result $true '' 'itemcontainer' $row)
            }
            $answer=Do-Reveal @{ aliases=@('Spotify'); hwnd=1; direction='down'; amount=1 }
            "$($answer.method)|$($answer.visible)"
            """);
        Assert.That(output, Is.EqualTo("itemcontainer|True"));
    }

    // hondo 14 finding 2: a scroller that answers late, read once, was told «nothing moved» or «end of the list».
    [Test]
    public void AScrollerThatMovesLateIsNotToldStill()
    {
        string output = Run(RevealPrelude + """
            $late=[System.Diagnostics.Stopwatch]::StartNew()
            $current=[pscustomobject]@{}
            $current | Add-Member -MemberType ScriptProperty -Name VerticalScrollPercent -Value { if($late.ElapsedMilliseconds -ge 300){ 40.0 } else { 10.0 } }
            $scroll=[pscustomobject]@{ Current=$current }
            Get-SettledPercent $scroll 10.0
            """);
        Assert.That(output, Is.EqualTo("40"));
    }

    [Test]
    public void CounterCaseAScrollerThatStaysPaysOnlyTheSettleAndIsToldStill()
    {
        string output = Run(RevealPrelude + """
            $scroll=[pscustomobject]@{ Current=[pscustomobject]@{ VerticalScrollPercent=100.0 } }
            $watch=[System.Diagnostics.Stopwatch]::StartNew()
            $still=Get-SettledPercent $scroll 100.0
            $took=$watch.ElapsedMilliseconds
            $moved=[pscustomobject]@{ Current=[pscustomobject]@{ VerticalScrollPercent=50.0 } }
            $watch.Restart()
            $at=Get-SettledPercent $moved 0.0
            "$still|$($took -ge $script:SettleMs)|$at|$($watch.ElapsedMilliseconds -lt 100)"
            """);
        Assert.That(output, Is.EqualTo("100|True|50|True"), "a scroll that moved waits for nothing");
    }

    // Review of batch 2 (I5): the system-wide focus is another process's, read before Get-Root's check and any wait limit;
    // a window in front that stopped pumping would hold a write to a healthy window behind.
    [Test]
    public void TheSystemWideFocusIsNotReadAroundAField()
    {
        string output = Run("""
            Invoke-Expression (Take 'function Add-FrontReport(' '# Las clases de ventana de la superficie de render')
            Add-Type -TypeDefinition 'public static class BaxyFrontKeeper { public static int WatchTaken=0; public static int WatchFailed=0; public static long WatchLongestMs=0; public static void Begin(System.IntPtr t){} public static void End(bool a){} }'
            function Test-ActedByPattern($result){ return $true }
            function Get-FocusKey(){ throw 'the focus of the whole desktop was read' }
            $answer=Invoke-Kept ([pscustomobject]@{ cmd='field'; hwnd=1 }) { param($r) @{ ok=$true; method='setvalue' } }
            [bool]$answer.ok
            """);
        Assert.That(output, Is.EqualTo("True"));
    }

    // Review of batch 2 (M7): PowerShell turns a raising property read into null (measured on 5.1: a getter that throws reads
    // $null, and [double]$null is 0), so a list rebuilt by its own scroll read as «moved to 0».
    [Test]
    public void AScrollerThatDiedIsNotReadAsPercentZero()
    {
        string output = Run(RevealPrelude + """
            $current=[pscustomobject]@{ VerticalScrollPercent=$null }
            $scroll=[pscustomobject]@{ Current=$current }
            try { $value=Get-SettledPercent $scroll 30.0; "read $value" } catch { 'unread' }
            """);
        Assert.That(output, Is.EqualTo("unread"));
    }

    [Test]
    public void ARevealPastItsDeadlineAnswersAnIncompleteSearchWithoutTurningPages()
    {
        string output = Run(RevealPrelude + """
            $script:RevealSeconds=0
            function Get-Descendants($root){ return @((Row 'Otra fila')) }
            function Find-InContainers($root,[string[]]$aliases,$until,[ref]$touched){ return $null }
            $answer=Do-Reveal @{ aliases=@('Spotify'); hwnd=1; direction='down'; amount=1 }
            "$($answer.ok)|$($answer.error)|$($answer.method)"
            """);
        // Auditoría final (regla 3): the window was not walked whole, so nothing is said to be missing.
        Assert.That(output, Is.EqualTo("False|reveal_search_incomplete|"));
    }

    [Test]
    public void AControlWithoutItsOwnScrollPatternScrollsByTheContainerThatHoldsIt()
    {
        string output = Run(OwnerPrelude + """
            $page=Node 'pagina' 'scroll-de-la-pagina'
            $list=Node 'lista' $null $page
            $row=Node 'fila' $null $list
            $owner=Find-ScrollOwner $row $page
            $own=Find-ScrollOwner (Node 'propio' 'scroll-propio' $list) $page
            "$($owner.scroll)|$($owner.own)|$($own.scroll)|$($own.own)"
            """);
        Assert.That(output, Is.EqualTo("scroll-de-la-pagina|False|scroll-propio|True"));
    }

    [Test]
    public void CounterCaseNothingScrollsUpToTheWindowGivesNoOwner()
    {
        string output = Run(OwnerPrelude + """
            $outside=Node 'fuera' 'scroll-de-otra-ventana'
            $window=Node 'ventana' $null $outside
            $row=Node 'fila' $null (Node 'lista' $null $window)
            $null -eq (Find-ScrollOwner $row $window)
            """);
        Assert.That(output, Is.EqualTo("True"), "the walk stops at the window, never above it");
    }

    [TestCase("""{"ok":true,"scrolled":true,"percentBefore":0,"percentAfter":12.5,"container":true}""", "True")]
    [TestCase("""{"ok":true,"scrolled":true,"percentBefore":0,"percentAfter":12.5,"container":false}""", "False")]
    [TestCase("""{"ok":true,"scrolled":true,"percentBefore":0,"percentAfter":12.5}""", "absent")]
    public void TheReceiptSaysWhetherAContainerMovedInsteadOfTheControl(string answer, string expected)
    {
        using JsonDocument read = JsonDocument.Parse(answer);
        JsonElement receipt = WindowsScrollAdapter.Result(
            "down", 3, 4, "uia_scroll_pattern_percent_postread", read.RootElement);

        string container = receipt.TryGetProperty("container", out JsonElement value) ? value.GetBoolean().ToString() : "absent";
        Assert.Multiple(() =>
        {
            Assert.That(container, Is.EqualTo(expected));
            Assert.That(receipt.GetProperty("index").GetInt32(), Is.EqualTo(4));
            Assert.That(receipt.GetProperty("percentAfter").GetDouble(), Is.EqualTo(12.5));
        });
    }

    // Do-Reveal, Reveal-Listed and the reveal's deadline, from the worker's text, on stand-in rows.
    private const string RevealPrelude = """
        Invoke-Expression (Take 'function Test-Shown(' '# Los guiones del navegador')
        function Box([double]$x,[double]$y,[double]$w,[double]$h){ [pscustomobject]@{ X=$x; Y=$y; Width=$w; Height=$h; IsEmpty=$false } }
        function View([double]$x,[double]$y,[double]$w,[double]$h){ return @{ x=$x; y=$y; w=$w; h=$h } }
        function Row([string]$name,[string]$kind='ControlType.ListItem',[bool]$shown=$false){
          [pscustomobject]@{ Name=$name; Current=[pscustomobject]@{ IsOffscreen=(-not $shown); BoundingRectangle=(Box 10 10 100 20); ControlType=[pscustomobject]@{ ProgrammaticName=$kind } } }
        }
        function Get-Root($hwnd){ return @{ root=[pscustomobject]@{ Name='ventana' } } }
        function Get-ScrollViewport($el){ return $script:Viewport }
        $script:Viewport=$null

        """;

    // Find-ScrollOwner from the worker's text, with stand-ins for the tree: a node's scroll and its parent.
    private const string OwnerPrelude = """
        Invoke-Expression (Take 'function Find-ScrollOwner(' 'function Do-Scroll(')
        function Node([string]$name,$scroll,$parent=$null){ [pscustomobject]@{ Name=$name; Scroll=$scroll; Parent=$parent } }
        function Get-VerticalScroll($node){ return $node.Scroll }
        function Get-ParentOf($node){ return $node.Parent }
        function Test-SameElement($a,$b){ return [object]::ReferenceEquals($a,$b) }

        """;

    private static string WorkerPath()
    {
        string worker = Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1");
        Assume.That(File.Exists(worker), "the worker script is copied next to the tests");
        return worker;
    }

    private static string Run(string body)
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
        start.ArgumentList.Add(Convert.ToBase64String(Encoding.Unicode.GetBytes(Prelude + body)));
        start.Environment["BAXY_REVEAL_WORKER"] = WorkerPath();
        using Process process = Process.Start(start)!;
        Task<string> error = process.StandardError.ReadToEndAsync();
        string output = ChildOutput.Read(process);
        Assert.That(process.WaitForExit(60_000), Is.True, "the script answers");
        Assert.That(process.ExitCode, Is.EqualTo(0), error.Result);
        return output.Trim();
    }
}
