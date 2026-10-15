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
        function Get-ShownName($el){ return @{ name=$el.Name } }

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
            function Get-ShownName($el){ $script:reads++; Start-Sleep -Milliseconds 25; return @{ name=$el.Name } }
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

    [Test]
    public void ARevealPastItsDeadlineAnswersNotFoundWithoutTurningPages()
    {
        string output = Run(RevealPrelude + """
            $script:RevealSeconds=0
            function Get-Descendants($root){ return @((Row 'Otra fila')) }
            function Find-InContainers($root,[string[]]$aliases,$until,[ref]$touched){ return $null }
            $answer=Do-Reveal @{ aliases=@('Spotify'); hwnd=1; direction='down'; amount=1 }
            "$($answer.ok)|$($answer.error)|$($answer.method)"
            """);
        Assert.That(output, Is.EqualTo("False|reveal_not_found|"));
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
        function Row([string]$name,[string]$kind='ControlType.ListItem',[bool]$shown=$false){
          [pscustomobject]@{ Name=$name; Current=[pscustomobject]@{ IsOffscreen=(-not $shown); ControlType=[pscustomobject]@{ ProgrammaticName=$kind } } }
        }
        function Get-Root($hwnd){ return @{ root=[pscustomobject]@{ Name='ventana' } } }

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
        string output = process.StandardOutput.ReadToEnd();
        Assert.That(process.WaitForExit(60_000), Is.True, "the script answers");
        Assert.That(process.ExitCode, Is.EqualTo(0), error.Result);
        return output.Trim();
    }
}
