using System.Diagnostics;
using System.Globalization;
using System.Text;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// DIAX7 (F13, uso real 16-11, 01:03 and 01:10: «pon una canción de …» sounded at 25 s): the client updated itself at
/// 00:24 and its search page no longer names its content «Spotify – Buscar» (the key search.page-title and its use left
/// its language files and its search route). The script waited for that name until its 20 s horizon every time, with the
/// results drawn about 3 s after the search (the client's own log). These run the script's look at the search page,
/// lifted from its text, over a simulated client: looks every 600 ms (a snapshot and a poll), as the client draws them.
/// </summary>
[TestFixture]
public sealed class SpotifySearchPageTests
{
    // The search page's stage, from the search to the press, with the results drawn at 2.5 s: seen at the next look and
    // taken once they stood a second (the old rule waited for the title until its 20 s horizon).
    private const double StageCap = 4.5;

    // A client of tonight's version, already up: Home under the box, the results drawn at 2.5 s, no titled page.
    [Test]
    public async Task AClientThatNoLongerTitlesItsSearchPageIsPressedOnceItsResultsShow()
    {
        (double at, string pressed) = await LookUntilReadyAsync(titled: false, resultsAt: 2.5);

        Assert.That(at, Is.LessThanOrEqualTo(StageCap), "the search page's stage, in simulated seconds");
        Assert.That(pressed, Is.EqualTo("Reproducir Los Andamios"));
    }

    // fin2 (Home rows a client draws after the page before was read, the search page 2-4 s after the search): a Home row
    // is never pressed; the results are, once Home left.
    [Test]
    public async Task HomeRowsDrawnLateAreNeverTakenForResults()
    {
        (double at, string pressed) = await LookUntilReadyAsync(titled: false, resultsAt: 3.5, lateHome: true);

        Assert.That(at, Is.InRange(3.5, 3.5 + 1.5));
        Assert.That(pressed, Is.EqualTo("Reproducir Los Andamios"));
    }

    // A page drawn in parts (its songs at 1.8 s, its top result at 3.0 s, held-out h02) is not taken half drawn.
    [Test]
    public async Task APageDrawnInPartsIsNotTakenHalfDrawn()
    {
        (double at, string pressed) = await LookUntilReadyAsync(titled: false, resultsAt: 3.0, songsAt: 1.8);

        Assert.That(at, Is.InRange(3.0, 3.0 + 1.5));
        Assert.That(pressed, Is.EqualTo("Reproducir Los Andamios"));
    }

    // The page before drawn again under new runtime ids before the results (held-out h06): none of its rows is pressed.
    [Test]
    public async Task ThePageBeforeDrawnAgainUnderNewIdsIsNeverTakenForResults()
    {
        (double at, string pressed) = await LookUntilReadyAsync(titled: false, resultsAt: 3.0, redrawnAt: 1.2);

        Assert.That(at, Is.InRange(3.0, 3.0 + 1.5));
        Assert.That(pressed, Is.EqualTo("Reproducir Los Andamios"));
    }

    // Control: the same search again, on a client that does not title its page: no page before is set aside, so nothing
    // tells the page left; it waits the horizon as before.
    [Test]
    public async Task TheSameSearchAgainWithoutATitledPageWaitsTheHorizonAsBefore()
    {
        (double at, _) = await LookUntilReadyAsync(titled: false, resultsAt: 0, sameSearch: true);

        Assert.That(at, Is.EqualTo(20.0));
    }

    // Control: a client that still titles its search page is pressed at the first look that shows its results, as before.
    [Test]
    public async Task AClientThatTitlesItsSearchPageIsPressedAtItsFirstLook()
    {
        (double at, string pressed) = await LookUntilReadyAsync(titled: true, resultsAt: 2.5);

        Assert.That(at, Is.EqualTo(3.0).Within(0.01));
        Assert.That(pressed, Is.EqualTo("Reproducir Los Andamios"));
    }

    // Control: a search whose page never shows is never ready; the horizon takes the last look as before.
    [Test]
    public async Task ASearchWhosePageNeverShowsWaitsItsWholeHorizon()
    {
        (double at, _) = await LookUntilReadyAsync(titled: false, resultsAt: 99);

        Assert.That(at, Is.EqualTo(20.0));
    }

    // Control: a page before with no play control of its own (only the library's) never leaves; its search waits the
    // horizon as before and presses the result, never the library.
    [Test]
    public async Task APageBeforeWithNoPlayControlOfItsOwnWaitsTheHorizonAsBefore()
    {
        (double at, string pressed) = await LookUntilReadyAsync(titled: false, resultsAt: 2.5, homeRows: false);

        Assert.That(at, Is.EqualTo(20.0));
        Assert.That(pressed, Is.EqualTo("Reproducir Los Andamios"));
    }

    // Uso real («los Bunkers» twice): with the box already holding the query no page before is set aside; a client that
    // still titles its page binds the results to it, never to the library's «Reproducir Tus Me Gusta».
    [Test]
    public async Task TheSameSearchAgainStaysInsideATitledPage()
    {
        (double at, string pressed) = await LookUntilReadyAsync(titled: true, resultsAt: 0, sameSearch: true);

        Assert.That(at, Is.EqualTo(0.0));
        Assert.That(pressed, Is.EqualTo("Reproducir Los Andamios"));
    }

    // DIAX7B (REVX2, D7-1): Home drawn again under new ids while a Home row draws late, at its left, before the results
    // (a client refreshing Home as the search lands): the page before left and the late row stood a second, yet no
    // result had come. The late row is never pressed; the result is, once it shows (4.5 s warm, 8 s cold, 12 s after
    // the search was issued again).
    [TestCase(4.5)]
    [TestCase(8.0)]
    [TestCase(12.0)]
    public async Task HomeDrawnAgainWithALateRowIsNeverTakenForResults(double resultsAt)
    {
        (double at, string pressed) = await LookUntilReadyAsync(titled: false, resultsAt: resultsAt, lateHome: true, redrawnAt: 1.2);

        Assert.That(pressed, Is.EqualTo("Reproducir Los Andamios"));
        Assert.That(at, Is.InRange(resultsAt, resultsAt + 1.8));
    }

    // DIAX7B (REVX2, D7-1): Home drawn again while the library's sidebar draws late: its «Reproducir Tus Me Gusta» is
    // never taken early. It stays the leftmost play control once the results show, so the search waits the horizon and
    // the last look is taken as it is, as the 1.5.5 does (REVX2 D7-2, inherited from the client: not this rule's).
    [Test]
    public async Task ASidebarDrawnLateIsNeverTakenEarly()
    {
        (double at, _) = await LookUntilReadyAsync(titled: false, resultsAt: 4.5, redrawnAt: 1.2, sidebarLate: true);

        Assert.That(at, Is.EqualTo(20.0));
    }

    // DIAX7B: Home drawn again twice, the late row with it.
    [Test]
    public async Task HomeDrawnAgainTwiceIsNeverTakenForResults()
    {
        (double at, string pressed) = await LookUntilReadyAsync(titled: false, resultsAt: 4.5, lateHome: true, redrawnAt: 1.2, redrawnAgainAt: 2.4);

        Assert.That(pressed, Is.EqualTo("Reproducir Los Andamios"));
        Assert.That(at, Is.InRange(4.5, 4.5 + 1.8));
    }

    // DIAX7B: no result ever comes while Home is drawn again and a late row stands: nothing is taken before the horizon.
    [Test]
    public async Task NoResultsWhileHomeIsDrawnAgainWaitTheWholeHorizon()
    {
        (double at, _) = await LookUntilReadyAsync(titled: false, resultsAt: 99, lateHome: true, redrawnAt: 1.2, sidebarLate: true);

        Assert.That(at, Is.EqualTo(20.0));
    }

    // DIAX7B: a search whose first result is a list named as it was asked is pressed once it shows, as a song is.
    [Test]
    public async Task AListNamedAsTheRequestIsPressedOnceItShows()
    {
        (double at, string pressed) = await LookUntilReadyAsync(titled: false, resultsAt: 2.5, lateHome: true, redrawnAt: 1.2,
            query: "lo fi para estudiar", topResult: "Reproducir Lo-Fi para estudiar");

        Assert.That(pressed, Is.EqualTo("Reproducir Lo-Fi para estudiar"));
        Assert.That(at, Is.InRange(2.5, 2.5 + 1.8));
    }

    // DIAX7B: a song asked with its artist: the top result card names the song alone, and is pressed once it shows.
    [Test]
    public async Task ASongAskedWithItsArtistIsPressedOnceItsCardShows()
    {
        (double at, string pressed) = await LookUntilReadyAsync(titled: false, resultsAt: 2.5, lateHome: true, redrawnAt: 1.2,
            query: "lluvia de cobre los andamios", topResult: "Reproducir Lluvia de Cobre");

        Assert.That(pressed, Is.EqualTo("Reproducir Lluvia de Cobre"));
        Assert.That(at, Is.InRange(2.5, 2.5 + 1.8));
    }

    // DIAX7B: a top result card titled as the request whose play control is a bare «Reproducir» is pressed once it shows.
    [Test]
    public async Task ACardTitledAsTheRequestIsPressedOnceItShows()
    {
        (double at, string pressed) = await LookUntilReadyAsync(titled: false, resultsAt: 2.5, lateHome: true, redrawnAt: 1.2, bareCard: true);

        Assert.That(pressed, Is.EqualTo("Reproducir"));
        Assert.That(at, Is.InRange(2.5, 2.5 + 1.8));
    }

    // DIAX7B: a first result that does not carry the words asked tells nothing the late rows would not: the search waits
    // the horizon as the 1.5.5 does, and presses the result.
    [Test]
    public async Task AResultNamedOtherwiseWaitsTheHorizonAsBefore()
    {
        (double at, string pressed) = await LookUntilReadyAsync(titled: false, resultsAt: 2.5, lateHome: true, redrawnAt: 1.2,
            query: "musica para estudiar", topResult: "Reproducir Enfoque profundo");

        Assert.That(at, Is.EqualTo(20.0));
        Assert.That(pressed, Is.EqualTo("Reproducir Enfoque profundo"));
    }

    // Runs the script's Get-BaxySpotifySearchLook, lifted from its text, over a simulated client's looks, as the script's
    // search wait does (the play controls of the last look and how long they stood passed to the next), and answers the simulated second of
    // the first ready look (20 when none was) and the play control it chose.
    private static async Task<(double At, string Pressed)> LookUntilReadyAsync(
        bool titled, double resultsAt, bool lateHome = false, bool sameSearch = false, bool homeRows = true, double songsAt = 99,
        double redrawnAt = 99, double redrawnAgainAt = 99, bool sidebarLate = false, string query = "los andamios",
        string topResult = "Reproducir Los Andamios", bool bareCard = false)
    {
        string flags = string.Create(CultureInfo.InvariantCulture,
            $"$titled=${titled};$resultsAt={resultsAt};$lateHome=${lateHome};$sameSearch=${sameSearch};$homeRows=${homeRows};$songsAt={songsAt};$redrawnAt={redrawnAt};$redrawnAgainAt={redrawnAgainAt};$sidebarLate=${sidebarLate};$query='{query}';$topResult='{topResult}';$bareCard=${bareCard}");
        string simulation = flags + """

            function Row($id,$name,$type,$left,$top,$width=40,$height=40){[pscustomobject]@{Element=$null;Id=[string]$id;Name=$name;Fold=(Fold $name);Type=[Windows.Automation.ControlType]::$type;Rect=[pscustomobject]@{Left=$left;Top=$top;Width=$width;Height=$height;Right=$left+$width;Bottom=$top+$height};Offscreen=$false}}
            $window=[pscustomobject]@{Left=0;Top=0;Width=1600;Height=1000;Right=1600;Bottom=1000}
            $box=[pscustomobject]@{Left=600;Top=10;Width=400;Height=40;Right=1000;Bottom=50}
            $sidebar=Row 1 'Reproducir Tus Me Gusta' Button 20 200
            function Look([double]$t){
                $rows=@((Row 9 'Buscar' ComboBox 600 10))
                if(-not $sidebarLate -or $t -ge 1.0){$rows+=$sidebar}
                if($t -ge $resultsAt){
                    if($titled){$rows+=Row 30 'Spotify – Buscar' Group 300 60 1300 900}
                    if($bareCard){$rows+=Row 12 $query Group 380 240 200 200;$rows+=Row 10 'Reproducir' Button 400 300}else{$rows+=Row 10 $topResult Button 400 250}
                    $rows+=Row 11 'Reproducir Lluvia de Cobre' Button 900 250
                }elseif($t -ge $songsAt){
                    $rows+=Row 11 'Reproducir Lluvia de Cobre' Button 900 250
                }else{
                    $rows+=Row 3 'Spotify - Reproductor web' Group 300 60 1300 900
                    $drawn=if($t -ge $redrawnAgainAt){2}elseif($t -ge $redrawnAt){1}else{0}
                    if($homeRows){$rows+=Row (@(2,5,6)[$drawn]) 'Reproducir Mezcla Diaria 1' Button 400 300}
                    if($lateHome -and $t -ge 1.0){$rows+=Row (@(4,4,7)[$drawn]) 'Reproducir Descubrimiento Semanal' Button 350 420}
                }
                return ,$rows
            }
            $title=Fold $query
            $keys=@((Look 0)|ForEach-Object {Get-BaxySpotifyRowKey $_})
            $pageBefore=Get-BaxySpotifyPageBefore $(if($sameSearch){$title}else{''}) $title $keys
            $before='';$since=0.0
            for($t=0.0;$t -lt 20.0;$t=[Math]::Round($t+0.6,1)){
                $look=Get-BaxySpotifySearchLook (Look $t) $pageBefore 'query' $title $box $window -CandidateBefore $before -StableMs (($t-$since)*1000)
                if($look.Key -ne $before){$before=$look.Key;$since=$t}
                if($look.Ready){'{0}|{1}' -f $t.ToString([Globalization.CultureInfo]::InvariantCulture),$look.Choice.Play.Name;return}
            }
            '20|{0}' -f $look.Choice.Play.Name
            """;
        string answer = await RunFunctionsAsync(simulation);
        string[] parts = answer.Split('|');
        return (double.Parse(parts[0], CultureInfo.InvariantCulture), parts[1]);
    }

    // Runs a call against every function of the script, lifted from its text by PowerShell's own parser (the script
    // itself would start the client), with the script-level assignments the functions read.
    private static async Task<string> RunFunctionsAsync(string call)
    {
        string path = Path.Combine(AppContext.BaseDirectory, "SpotifyDesktopAutomation.ps1").Replace("'", "''", StringComparison.Ordinal);
        string script = $$"""
            Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes
            $errors=$null;$tokens=$null
            $ast=[System.Management.Automation.Language.Parser]::ParseFile('{{path}}',[ref]$tokens,[ref]$errors)
            foreach($item in $ast.EndBlock.Statements){
                $text=$item.Extent.Text
                if($item -is [System.Management.Automation.Language.FunctionDefinitionAst]){Invoke-Expression $text}
                elseif($text -like '$script:BaxySpotifyPlaying*'){Invoke-Expression $text}
            }
            {{call}}
            """;
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
        using Process process = Process.Start(start) ?? throw new InvalidOperationException("powershell did not start");
        Task<string> error = process.StandardError.ReadToEndAsync();
        string output = ChildOutput.Read(process);
        Assert.That(process.WaitForExit(60_000), Is.True, "the script answers");
        // Windows PowerShell writes its progress to the error stream as CLIXML: only the exit code tells a failure.
        Assert.That(process.ExitCode, Is.EqualTo(0), await error);
        return output.Trim();
    }
}
