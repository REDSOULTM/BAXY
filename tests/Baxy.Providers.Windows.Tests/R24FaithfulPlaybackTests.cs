using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Ronda 24, «latencia de lo fácil y reproducción fiel»: a Spotify playback's receipt carries what was pressed and
/// what plays as the script observed them, and nothing BAXY's own grammar derived from the query (BAXY Renew audit
/// 2026-10-15, S1-S7; t2-c01 «pone los bunkers en spotify pa estudiar» played «Fother Muckers»: the receipt shows it,
/// the model judges it), and a browser search arrives by a changed window title that names every word searched
/// (t4-c10, t3-c06: Opera GX's stale address field).
/// </summary>
[TestFixture]
public sealed class R24FaithfulPlaybackTests
{
    private const string Played =
        "{\"ok\":true,\"effectObserved\":true,\"error\":null,\"title\":\"Fother Muckers - Nada en este Mundo\","
        + "\"selectedControl\":\"Reproducir Fother Muckers\",\"beforeNowPlaying\":\"aruarian dance de nujabes\","
        + "\"observedNowPlaying\":\"nada en este mundo de fother muckers\",\"playbackEvidence\":\"now_playing_changed\","
        + "\"presses\":1,\"processId\":42}";

    // S2, S7: what was pressed, what plays and the observation that told the playback started travel as the script
    // read them; no field says whether it is what the query asked for.
    [Test]
    public async Task AQueryReceiptCarriesWhatWasPressedAndWhatPlaysAsObserved()
    {
        var adapter = new SpotifyDesktopAdapter(new Runner(Played));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "media.play.query", Json("""{"provider":"spotify","query":"los bunkers"}"""), CancellationToken.None);

        JsonElement result = receipt.Result!.Value;
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, "something plays: that is a fact");
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(result.GetProperty("query").GetString(), Is.EqualTo("los bunkers"));
            Assert.That(result.GetProperty("title").GetString(), Is.EqualTo("Fother Muckers - Nada en este Mundo"));
            Assert.That(result.GetProperty("selectedControl").GetString(), Is.EqualTo("Reproducir Fother Muckers"));
            Assert.That(result.GetProperty("observedNowPlaying").GetString(),
                Is.EqualTo("nada en este mundo de fother muckers"));
            Assert.That(result.GetProperty("playbackEvidence").GetString(), Is.EqualTo("now_playing_changed"));
            Assert.That(result.TryGetProperty("matchesQuery", out _), Is.False);
            Assert.That(result.TryGetProperty("alreadyPlaying", out _), Is.False);
        });
    }

    // S1: the script gets the text to search and its deadline, never a list of words to compare it with.
    [TestCase("media.play.query", """{"provider":"spotify","query":"rap para entrenar"}""", "query")]
    [TestCase("media.play.exact", """{"provider":"spotify","title":"Vida de perros"}""", "exact")]
    public async Task ASearchPassesOnlyItsTextAndItsDeadline(string operation, string arguments, string mode)
    {
        var runner = new Runner(Played);
        var adapter = new SpotifyDesktopAdapter(runner);

        await adapter.InvokeAsync(operation, Json(arguments), CancellationToken.None);

        IReadOnlyList<string> passed = runner.Calls.Single();
        Assert.Multiple(() =>
        {
            Assert.That(passed.Where(static argument => argument.StartsWith('-')),
                Is.EqualTo(new[] { "-NoProfile", "-NonInteractive", "-STA", "-File", "-DeadlineMs" }));
            Assert.That(passed[^1], Is.EqualTo(mode));
        });
    }

    // S4 («pon Vida de perros» while it already plays): nothing is pressed; the receipt is verified with no effect, says
    // it was already playing and carries the window title the script read, never the title asked for.
    [Test]
    public async Task AnExactTitleAlreadyPlayingIsVerifiedWithNoEffectAndTheObservedTitle()
    {
        var adapter = new SpotifyDesktopAdapter(new Runner(
            "{\"ok\":true,\"effectObserved\":false,\"alreadyPlaying\":true,\"error\":null,"
            + "\"title\":\"Los Bunkers - Vida de perros\",\"observedNowPlaying\":\"vida de perros de los bunkers\",\"processId\":42}"));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "media.play.exact", Json("""{"provider":"spotify","title":"Vida de perros"}"""), CancellationToken.None);

        JsonElement result = receipt.Result!.Value;
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.False, "nothing was pressed");
            Assert.That(receipt.StateAlreadyReached, Is.True, "already playing is the request done, not unobserved");
            Assert.That(result.GetProperty("alreadyPlaying").GetBoolean(), Is.True);
            Assert.That(result.GetProperty("title").GetString(), Is.EqualTo("Los Bunkers - Vida de perros"));
            Assert.That(result.GetProperty("observedNowPlaying").GetString(), Is.EqualTo("vida de perros de los bunkers"));
            Assert.That(result.TryGetProperty("query", out _), Is.False);
            Assert.That(result.TryGetProperty("selectedControl", out _), Is.False);
        });
    }

    // S5: a script that read no title leaves the receipt without one, never the requested title in its place.
    [TestCase("""{"ok":true,"effectObserved":true,"error":null,"processId":42}""")]
    [TestCase("""{"ok":true,"effectObserved":true,"error":null,"title":"","processId":42}""")]
    public async Task AReceiptWithNoObservedTitleCarriesNone(string output)
    {
        var adapter = new SpotifyDesktopAdapter(new Runner(output));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "media.play.exact", Json("""{"provider":"spotify","title":"Vida de perros"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.TryGetProperty("title", out _), Is.False);
        });
    }

    private static readonly SearchAddress[] Engines = LoadEngines();

    private static SearchAddress[] LoadEngines()
    {
        using FileStream stream = File.OpenRead(DataFile("search_addresses.v1.json"));
        return [.. SearchAddresses.Parse(stream)];
    }

    private static string DataFile(string name)
    {
        for (DirectoryInfo? directory = new(AppContext.BaseDirectory); directory is not null; directory = directory.Parent)
        {
            string candidate = Path.Combine(directory.FullName, "src", "baxy_mind", "data", name);
            if (File.Exists(candidate))
                return candidate;
        }
        throw new FileNotFoundException(name);
    }

    [Test]
    public void TheEmbeddedEnginesAreTheDataFile()
    {
        Assert.That(SearchAddresses.All.Select(engine => engine.Host), Is.EqualTo(Engines.Select(engine => engine.Host)));
        Assert.That(SearchAddresses.All, Is.Not.Empty);
    }

    // t4-c10 and t3-c06: the window title after the link names every word searched.
    [TestCase("https://www.google.com/search?q=los+horarios+del+cercan%C3%ADas+de+madrid",
        "los horarios del cercanías de madrid - Buscar con Google - Opera", true)]
    [TestCase("https://www.google.com/search?q=como+hacer+un+pivot+table+en+excel",
        "como hacer un pivot table en excel - Buscar con Google - Opera", true)]
    [TestCase("https://www.bing.com/search?q=clima+curico", "clima curicó - Search - Opera", true)]
    // Contracaso: a search title missing one of the words asked is not the arrival.
    [TestCase("https://www.google.com/search?q=los+horarios+del+cercanias+de+madrid",
        "los horarios del metro de madrid - Buscar con Google - Opera", false)]
    [TestCase("https://www.google.com/search?q=los+horarios+del+cercanias+de+madrid", "Buscar con Google - Opera", false)]
    // A destination that is no known engine's results page never arrives by its title.
    [TestCase("https://es.wikipedia.org/wiki/Cercan%C3%ADas_Madrid", "Cercanías Madrid - Wikipedia - Opera", false)]
    [TestCase("https://www.google.com/maps?q=madrid", "madrid - Google Maps - Opera", false)]
    public void ASearchTitleArrivesOnlyWithEveryWordSearched(string target, string title, bool arrives) =>
        Assert.That(UserBrowserSurface.SearchTitleArrives(new Uri(target), title, "Opera", Engines), Is.EqualTo(arrives));

    // Revisión 1 r24u (bloqueante 2): the words are looked for only in the page part of the title, never in the
    // browser's own segment nor in a page that merely names them.
    [TestCase("https://www.google.com/search?q=opera", "opera - Buscar con Google - Opera", "Opera", true)]
    [TestCase("https://www.google.com/search?q=microsoft+edge",
        "microsoft edge - Buscar con Google y 2 páginas más - Personal - Microsoft\u200b Edge", "Microsoft\u200b Edge", true)]
    // Contracaso: Opera GX with no network, «busca opera en google»: the tab is titled by the host and the browser.
    [TestCase("https://www.google.com/search?q=opera", "www.google.com - Opera", "Opera", false)]
    [TestCase("https://www.google.com/search?q=opera", "www.google.com - Opera", null, false)]
    [TestCase("https://www.google.com/search?q=opera", "Opera", "Opera", false)]
    [TestCase("https://www.google.com/search?q=opera", "No se puede acceder a este sitio - Opera", "Opera", false)]
    // Contracaso: Edge, «busca en google microsoft edge», a new tab or the bare host titled with the browser's name.
    [TestCase("https://www.google.com/search?q=microsoft+edge",
        "www.google.com - Personal - Microsoft\u200b Edge", "Microsoft\u200b Edge", false)]
    [TestCase("https://www.google.com/search?q=microsoft+edge",
        "Nueva pestaña - Personal - Microsoft\u200b Edge", "Microsoft\u200b Edge", false)]
    // Contracaso: another window of the browser whose video moved on and names the words is no results page.
    [TestCase("https://www.google.com/search?q=opera", "Opera de París en vivo - YouTube - Opera", "Opera", false)]
    [TestCase("https://www.google.com/search?q=clima+curico", "clima curicó en vivo - YouTube - Opera", "Opera", false)]
    public void ASearchTitleIsReadWithoutTheBrowsersSegment(string target, string title, string? segment, bool arrives) =>
        Assert.That(UserBrowserSurface.SearchTitleArrives(new Uri(target), title, segment, Engines), Is.EqualTo(arrives));

    [Test]
    public void TheBrowsersSegmentIsLearnedFromTheTitlesBeforeTheLink()
    {
        Assert.Multiple(() =>
        {
            Assert.That(UserBrowserSurface.BrowserTitleSegment(["Inicio - Opera", "YouTube - Opera"]), Is.EqualTo("Opera"));
            Assert.That(UserBrowserSurface.BrowserTitleSegment(["Nueva pestaña - Personal - Microsoft\u200b Edge"]),
                Is.EqualTo("Microsoft\u200b Edge"));
            // Contracaso: titles that disagree, or no title with a segment, teach nothing.
            Assert.That(UserBrowserSurface.BrowserTitleSegment(["a - Opera", "b - Otro"]), Is.Null);
            Assert.That(UserBrowserSurface.BrowserTitleSegment(["Opera"]), Is.Null);
            Assert.That(UserBrowserSurface.BrowserTitleSegment([]), Is.Null);
        });
    }

    [Test]
    public void TheSearchedTextComesFromTheEnginesParameter()
    {
        Assert.Multiple(() =>
        {
            Assert.That(SearchAddresses.SearchedText(new Uri("https://duckduckgo.com/?q=pivot+table"), Engines),
                Is.EqualTo("pivot table"));
            Assert.That(SearchAddresses.SearchedText(new Uri("https://search.yahoo.com/search?p=hola"), Engines),
                Is.EqualTo("hola"));
            Assert.That(SearchAddresses.SearchedText(new Uri("https://www.google.com/search?tbm=isch"), Engines), Is.Null);
            Assert.That(SearchAddresses.SearchedText(new Uri("https://notgoogle.com/search?q=x"), Engines), Is.Null);
        });
    }

    private sealed class Runner(string output) : IExternalProcessRunner
    {
        public List<IReadOnlyList<string>> Calls { get; } = [];

        public ValueTask<ExternalProcessResult> RunAsync(
            string executable, IReadOnlyList<string> arguments, TimeSpan timeout,
            CancellationToken cancellationToken)
        {
            Calls.Add(arguments);
            return ValueTask.FromResult(new ExternalProcessResult(0, output, ""));
        }
    }

    private static JsonElement Json(string text)
    {
        using JsonDocument document = JsonDocument.Parse(text);
        return document.RootElement.Clone();
    }
}
