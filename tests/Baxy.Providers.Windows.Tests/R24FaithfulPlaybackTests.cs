using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Ronda 24, «latencia de lo fácil y reproducción fiel»: a Spotify search says whether what plays was shown to be
/// what the query asked for (t2-c01 «pone los bunkers en spotify pa estudiar» played «Fother Muckers» and was told as
/// the request done), and a browser search arrives by a changed window title that names every word searched (t4-c10,
/// t3-c06: Opera GX's stale address field).
/// </summary>
[TestFixture]
public sealed class R24FaithfulPlaybackTests
{
    private static string Output(string title, string matches) =>
        "{\"ok\":true,\"effectObserved\":true,\"error\":null,\"title\":\"" + title
        + "\",\"selectedControl\":\"Reproducir\",\"matchesQuery\":" + matches + ",\"processId\":42}";

    [Test]
    public async Task AQueryWhosePlayingTrackDoesNotMatchCarriesThatFactNeverAMatch()
    {
        var adapter = new SpotifyDesktopAdapter(new Runner(Output("Fother Muckers - Nada en este Mundo", "false")));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "media.play.query", Json("""{"provider":"spotify","query":"los bunkers"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, "something plays: that is a fact");
            Assert.That(receipt.Result?.GetProperty("matchesQuery").GetBoolean(), Is.False);
            Assert.That(receipt.Result?.GetProperty("title").GetString(), Is.EqualTo("Fother Muckers - Nada en este Mundo"));
        });
    }

    [Test]
    public async Task AQueryWhosePlayingTrackMatchesSaysSo()
    {
        var adapter = new SpotifyDesktopAdapter(new Runner(Output("Los Bunkers - Llueve sobre la ciudad", "true")));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "media.play.query", Json("""{"provider":"spotify","query":"los bunkers"}"""), CancellationToken.None);

        Assert.That(receipt.Result?.GetProperty("matchesQuery").GetBoolean(), Is.True);
    }

    // Contracaso: «pon Vida de perros de Los Bunkers» in exact mode keeps its receipt as it was.
    [Test]
    public async Task TheExactModeReceiptIsUnchanged()
    {
        var adapter = new SpotifyDesktopAdapter(new Runner(Output("Los Bunkers - Vida de perros", "null")));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "media.play.exact", Json("""{"provider":"spotify","title":"Vida de perros"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.TryGetProperty("matchesQuery", out _), Is.False);
            Assert.That(receipt.Result?.TryGetProperty("query", out _), Is.False);
        });
    }

    // A script that says nothing about the match keeps the receipt without the fact (never a guessed true).
    [Test]
    public async Task AScriptThatDoesNotSayLeavesNoMatchFact()
    {
        var adapter = new SpotifyDesktopAdapter(new Runner(
            "{\"ok\":true,\"effectObserved\":true,\"error\":null,\"title\":\"x\",\"processId\":42}"));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "media.play.query", Json("""{"provider":"spotify","query":"musica para estudiar"}"""), CancellationToken.None);

        Assert.That(receipt.Result?.TryGetProperty("matchesQuery", out _), Is.False);
    }

    // Revisión 2 («rap para entrenar» → «Rock para entrenar»): a query is compared in the script without its function
    // words and with its purpose apart, words the provider reads from data (query_function_words.v1.json) and passes.
    [Test]
    public async Task AQuerySearchPassesTheFunctionWordsFromData()
    {
        var runner = new Runner(Output("Rap Chileno", "true"));
        var adapter = new SpotifyDesktopAdapter(runner);

        await adapter.InvokeAsync(
            "media.play.query", Json("""{"provider":"spotify","query":"rap para entrenar"}"""), CancellationToken.None);

        IReadOnlyList<string> arguments = runner.Calls.Single();
        int flag = arguments.ToList().IndexOf("-QueryWordsBase64");
        Assert.That(flag, Is.GreaterThan(0));
        using JsonDocument words = JsonDocument.Parse(Convert.FromBase64String(arguments[flag + 1]));
        string[] Read(string key) =>
            words.RootElement.GetProperty(key).EnumerateArray().Select(static w => w.GetString()!).ToArray();
        Assert.Multiple(() =>
        {
            Assert.That(Read("purpose_markers"), Does.Contain("para"));
            Assert.That(Read("function_words"), Does.Contain("lo").And.Contain("los"));
            // Short content words are never function words: they count.
            Assert.That(Read("function_words").Concat(Read("medium_words")),
                Has.None.AnyOf("rap", "pop", "fi", "rock", "cumbia"));
        });
    }

    // Contracaso: the exact mode compares the exact title and passes no words.
    [Test]
    public async Task AnExactSearchPassesNoWords()
    {
        var runner = new Runner(Output("Los Bunkers - Vida de perros", "null"));
        var adapter = new SpotifyDesktopAdapter(runner);

        await adapter.InvokeAsync(
            "media.play.exact", Json("""{"provider":"spotify","title":"Vida de perros"}"""), CancellationToken.None);

        Assert.That(runner.Calls.Single(), Does.Not.Contain("-QueryWordsBase64"));
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
