using System.Net;
using System.Text;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// M122 (owner 2026-10-02): pages, YouTube and streaming open in the person's
/// default browser and are verified without taking it over. Every PC touch goes
/// through a fake platform: no browser, window or media session is used here.
/// </summary>
[TestFixture]
public sealed class UserBrowserTests
{
    private const string OperaCommand =
        "\"C:\\Users\\owner\\AppData\\Local\\Programs\\Opera GX\\opera.exe\" -noautoupdate -- \"%1\"";

    private static readonly UserBrowserIdentity OperaGx = new(
        "Opera GXStable", "opera_gx", "Opera GX",
        @"C:\Users\owner\AppData\Local\Programs\Opera GX\opera.exe");

    [Test]
    public void DefaultBrowserIsReadFromTheUserChoiceProgIdAndItsOpenCommand()
    {
        UserBrowserIdentity? opera = UserBrowserIdentityResolver.Resolve("Opera GXStable", OperaCommand);
        UserBrowserIdentity? chrome = UserBrowserIdentityResolver.Resolve(
            "ChromeHTML", "\"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe\" --single-argument %1");
        UserBrowserIdentity? firefox = UserBrowserIdentityResolver.Resolve(
            "FirefoxURL-308046B0AF4A39CB", "C:\\Program Files\\Mozilla Firefox\\firefox.exe -osint -url \"%1\"");
        UserBrowserIdentity? edge = UserBrowserIdentityResolver.Resolve(
            "MSEdgeHTM", "\"C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe\" --single-argument %1");

        Assert.Multiple(() =>
        {
            Assert.That(opera?.Family, Is.EqualTo("opera_gx"));
            Assert.That(opera?.DisplayName, Is.EqualTo("Opera GX"));
            Assert.That(opera?.Executable, Is.EqualTo(@"C:\Users\owner\AppData\Local\Programs\Opera GX\opera.exe"));
            Assert.That(opera?.ProcessName, Is.EqualTo("opera"));
            Assert.That(chrome?.Family, Is.EqualTo("chrome"));
            Assert.That(firefox?.Family, Is.EqualTo("firefox"));
            Assert.That(firefox?.Executable, Is.EqualTo(@"C:\Program Files\Mozilla Firefox\firefox.exe"));
            Assert.That(firefox!.OwnsMediaSession("308046B0AF4A39CB"), Is.True);
            Assert.That(edge?.Family, Is.EqualTo("edge"));
            Assert.That(UserBrowserIdentityResolver.Resolve("", OperaCommand), Is.Null);
            Assert.That(UserBrowserIdentityResolver.Resolve("OperaStable", "opera.exe %1"), Is.Null,
                "a relative executable is no browser identity");
        });
    }

    [Test]
    public void YouTubeResultsPageGivesTheFirstVideoAndItsOwnTitle()
    {
        YouTubeSearchResult video = YouTubeSearch.Parse(YouTubePage("dQw4w9WgXcQ", "Rick Astley \\u0026 Co - Never"));
        YouTubeSearchResult none = YouTubeSearch.Parse("<html>nothing</html>");

        Assert.Multiple(() =>
        {
            Assert.That(video.Found, Is.True);
            Assert.That(video.VideoId, Is.EqualTo("dQw4w9WgXcQ"));
            Assert.That(video.Title, Is.EqualTo("Rick Astley & Co - Never"));
            Assert.That(video.WatchUri.AbsoluteUri, Is.EqualTo("https://www.youtube.com/watch?v=dQw4w9WgXcQ"));
            Assert.That(none.ErrorCode, Is.EqualTo("youtube_result_not_found"));
        });
    }

    [Test]
    public async Task NavigationOpensInTheDefaultBrowserAndVerifiesTheAddressItShows()
    {
        var platform = new FakePlatform(OperaGx)
        {
            AddressOf = _ => "www.wikipedia.org/",
        };
        platform.WindowsAfterOpen = [new(11, "Wikipedia - Opera")];
        using Harness harness = new(platform);

        ExternalCapabilityReceipt receipt = await harness.Adapter.InvokeAsync(
            "browser.navigate", Json("""{"url":"https://wikipedia.org/"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(platform.Opened, Is.EqualTo(new[] { "https://wikipedia.org/" }));
            Assert.That(receipt.Result?.GetProperty("finalUrl").GetString(), Is.EqualTo("https://www.wikipedia.org/"));
            Assert.That(receipt.Result?.GetProperty("browser").GetString(), Is.EqualTo("Opera GX"));
            Assert.That(receipt.Result?.GetProperty("authority").GetString(),
                Is.EqualTo("user_browser_uia_address_postread"));
            Assert.That(harness.Edge.NavigateCalls, Is.Zero, "the product browser is not launched");
        });
    }

    [Test]
    public async Task AnotherSitesAddressIsNeverReportedAndLeavesTheNavigationUncertain()
    {
        var platform = new FakePlatform(OperaGx)
        {
            AddressOf = _ => "mail.example.org/inbox?private=1",
        };
        platform.WindowsAfterOpen = [new(11, "Inbox - Opera")];
        using Harness harness = new(platform);

        ExternalCapabilityReceipt receipt = await harness.Adapter.InvokeAsync(
            "browser.navigate", Json("""{"url":"https://wikipedia.org/"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            Assert.That(receipt.ErrorCode, Is.EqualTo(UserBrowserSurface.NavigationUnconfirmed));
            Assert.That(receipt.Result, Is.Null);
            Assert.That(harness.Edge.NavigateCalls, Is.Zero, "an opened link is never repeated elsewhere");
        });
    }

    [Test]
    public async Task AnUnreadableAddressFieldIsReadOncePerTitleAndLeavesTheNavigationUncertain()
    {
        var platform = new FakePlatform(OperaGx) { AddressOf = _ => null };
        platform.WindowsAfterOpen = [new(11, "Wikipedia, la enciclopedia libre - Opera")];
        using Harness harness = new(platform);

        ExternalCapabilityReceipt receipt = await harness.Adapter.InvokeAsync(
            "browser.navigate", Json("""{"url":"https://es.wikipedia.org/"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            Assert.That(receipt.ErrorCode, Is.EqualTo(UserBrowserSurface.NavigationUnconfirmed));
            Assert.That(platform.AddressReads, Is.EqualTo(1), "a title that did not move is not read again");
        });
    }

    [Test]
    public async Task NamingThePersonsOwnBrowserOpensTheirSessionNotAPrivateProfile()
    {
        var platform = new FakePlatform(OperaGx) { AddressOf = _ => "www.youtube.com/" };
        platform.WindowsAfterOpen = [new(11, "YouTube - Opera")];
        var context = new CdpBrowserSessionContext();
        string root = Path.Combine(Path.GetTempPath(), "baxy-user-browser-" + Guid.NewGuid().ToString("N"));
        using var named = new NamedBrowserAdapter(
            root, context, opera: null,
            userBrowser: new UserBrowserSurface(platform, _ => null));

        ExternalCapabilityReceipt receipt = await named.InvokeAsync(
            "browser.navigate.named",
            Json("""{"browser":"opera_gx","url":"https://youtube.com/"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(platform.Opened, Is.EqualTo(new[] { "https://youtube.com/" }));
            Assert.That(receipt.Result?.GetProperty("browser").GetString(), Is.EqualTo("Opera GX"));
            Assert.That(receipt.Result?.GetProperty("finalUrl").GetString(), Is.EqualTo("https://www.youtube.com/"));
            Assert.That(context.UserBrowserHoldsThePage, Is.True);
            Assert.That(Directory.Exists(root), Is.False, "no private profile was created");
        });
    }

    [Test]
    public async Task NoWindowChangeLeavesTheNavigationUncertain()
    {
        var platform = new FakePlatform(OperaGx) { AddressOf = _ => "wikipedia.org" };
        using Harness harness = new(platform);

        ExternalCapabilityReceipt receipt = await harness.Adapter.InvokeAsync(
            "browser.navigate", Json("""{"url":"https://wikipedia.org/"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            Assert.That(platform.AddressReads, Is.Zero, "with no changed window nothing is read");
        });
    }

    [Test]
    public async Task ABrowserThatCannotLaunchKeepsTheProductBrowserAsFallback()
    {
        var platform = new FakePlatform(OperaGx) { OpenFails = true };
        using Harness harness = new(platform);

        ExternalCapabilityReceipt receipt = await harness.Adapter.InvokeAsync(
            "browser.navigate", Json("""{"url":"https://wikipedia.org/"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("authority").GetString(), Is.EqualTo("cdp"));
            Assert.That(harness.Edge.NavigateCalls, Is.EqualTo(1));
        });
    }

    [TestCase("BAXY_BROWSER", "product")]
    [TestCase("BAXY_CDP_ENDPOINT", "http://127.0.0.1:9333/")]
    public async Task ProductBrowserModeAndMeasurementFixturesKeepTheCdpBrowser(string name, string value)
    {
        var platform = new FakePlatform(OperaGx);
        using Harness harness = new(platform, new Dictionary<string, string> { [name] = value });

        ExternalCapabilityReceipt receipt = await harness.Adapter.InvokeAsync(
            "browser.navigate", Json("""{"url":"https://wikipedia.org/"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(platform.Opened, Is.Empty);
            Assert.That(harness.Edge.NavigateCalls, Is.EqualTo(1));
        });
    }

    [Test]
    public async Task NoDefaultBrowserKeepsTheCdpBrowser()
    {
        var platform = new FakePlatform(null);
        using Harness harness = new(platform);

        ExternalCapabilityReceipt receipt = await harness.Adapter.InvokeAsync(
            "browser.navigate", Json("""{"url":"https://wikipedia.org/"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(harness.Edge.NavigateCalls, Is.EqualTo(1));
        });
    }

    [Test]
    public async Task YouTubePlaysInTheDefaultBrowserAndIsVerifiedByItsMediaSession()
    {
        var platform = new FakePlatform(OperaGx);
        platform.SessionsAfterOpen =
        [
            [],
            [new("Opera GXStable", "Never Gonna Give You Up", "Rick Astley", "playing")],
        ];
        using Harness harness = new(platform, http: YouTubePage("dQw4w9WgXcQ", "Never Gonna Give You Up"));

        ExternalCapabilityReceipt receipt = await harness.Adapter.InvokeAsync(
            "media.play.youtube", Json("""{"query":"never gonna give you up"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(platform.Opened, Is.EqualTo(new[] { "https://www.youtube.com/watch?v=dQw4w9WgXcQ" }));
            Assert.That(receipt.Result?.GetProperty("title").GetString(), Is.EqualTo("Never Gonna Give You Up"));
            Assert.That(receipt.Result?.GetProperty("playbackStatus").GetString(), Is.EqualTo("playing"));
            Assert.That(receipt.Result?.GetProperty("browser").GetString(), Is.EqualTo("Opera GX"));
            Assert.That(receipt.Result?.GetProperty("sourceAppUserModelId").GetString(), Is.EqualTo("Opera GXStable"));
            Assert.That(receipt.Result?.GetProperty("authority").GetString(), Is.EqualTo("user_browser_smtc_postread"));
            Assert.That(harness.Edge.YouTubeCalls, Is.Zero);
        });
    }

    [Test]
    public async Task AutoplayHeldBackIsPressedOnceThroughTheSessionsOwnPlayControl()
    {
        var platform = new FakePlatform(OperaGx);
        var paused = new UserMediaSession("Opera GXStable", "Never Gonna Give You Up", "Rick Astley", "paused");
        platform.SessionsAfterOpen = [[paused]];
        platform.OnPlay = session => platform.SessionsAfterOpen = [[session with { PlaybackStatus = "playing" }]];
        using Harness harness = new(platform, http: YouTubePage("dQw4w9WgXcQ", "Never Gonna Give You Up"));

        ExternalCapabilityReceipt receipt = await harness.Adapter.InvokeAsync(
            "media.play.youtube", Json("""{"query":"never gonna give you up"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(platform.Played, Has.Count.EqualTo(1));
            Assert.That(platform.Played[0].Title, Is.EqualTo("Never Gonna Give You Up"));
        });
    }

    [Test]
    public async Task APausedVideoThePersonAlreadyHadIsNeverPressedOrTakenForTheNewOne()
    {
        var platform = new FakePlatform(OperaGx);
        var theirs = new UserMediaSession("Opera GXStable", "Their podcast", "Someone", "paused");
        platform.SessionsBeforeOpen = [theirs];
        platform.SessionsAfterOpen = [[theirs]];
        using Harness harness = new(platform, http: YouTubePage("dQw4w9WgXcQ", "Never Gonna Give You Up"));

        ExternalCapabilityReceipt receipt = await harness.Adapter.InvokeAsync(
            "media.play.youtube", Json("""{"query":"never gonna give you up"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            Assert.That(receipt.ErrorCode, Is.EqualTo(UserBrowserSurface.PlaybackUnconfirmed));
            Assert.That(platform.Played, Is.Empty);
            Assert.That(harness.Edge.YouTubeCalls, Is.Zero, "the video is not started a second time elsewhere");
        });
    }

    [Test]
    public async Task TabsOfThePersonsBrowserAreNotReadThroughTheProductBrowser()
    {
        var platform = new FakePlatform(OperaGx) { AddressOf = _ => "wikipedia.org/" };
        platform.WindowsAfterOpen = [new(11, "Wikipedia - Opera")];
        var context = new CdpBrowserSessionContext();
        using Harness harness = new(platform, context: context);

        ExternalCapabilityReceipt navigation = await harness.Adapter.InvokeAsync(
            "browser.navigate", Json("""{"url":"https://wikipedia.org/"}"""), CancellationToken.None);
        ExternalCapabilityReceipt page = await harness.Adapter.InvokeAsync(
            "browser.page.read", Json("""{"maximumCharacters":2000}"""), CancellationToken.None);
        ExternalCapabilityReceipt control = await harness.Adapter.InvokeAsync(
            "browser.control", Json("""{"action":"reload"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(navigation.Verified, Is.True);
            Assert.That(page.ErrorCode, Is.EqualTo(WebBrowserAdapter.UserBrowserTabsNotAutomatable));
            Assert.That(control.ErrorCode, Is.EqualTo(WebBrowserAdapter.UserBrowserTabsNotAutomatable));
            Assert.That(page.EffectMayHaveOccurred || control.EffectMayHaveOccurred, Is.False);
            Assert.That(harness.Edge.ReadCalls, Is.Zero);
            Assert.That(context.Active, Is.Null);
        });
    }

    [Test]
    public async Task StreamingTitleStartsInTheSignedInSessionAndIsVerifiedByANewBrowserSession()
    {
        var platform = new FakePlatform(OperaGx)
        {
            AddressOf = _ => "www.netflix.com/search?q=Stranger%20Things",
            PageStep = new UserBrowserPageStep(true, "play_invoked", "Stranger Things"),
        };
        platform.WindowsAfterOpen = [new(11, "Netflix - Opera")];
        platform.SessionsAfterOpen = [[], [new("Opera GXStable", "Netflix", string.Empty, "playing")]];
        using Harness harness = new(platform);

        ExternalCapabilityReceipt receipt = await harness.Adapter.InvokeAsync(
            "streaming.play.named", Json("""{"service":"netflix","title":"stranger things"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(platform.Opened, Is.EqualTo(new[] { "https://www.netflix.com/search?q=stranger%20things" }));
            Assert.That(platform.PageSteps, Is.EqualTo(new[] { (11, "stranger things", false) }));
            Assert.That(receipt.Result?.GetProperty("title").GetString(), Is.EqualTo("Stranger Things"));
            Assert.That(receipt.Result?.GetProperty("playbackStatus").GetString(), Is.EqualTo("playing"));
            Assert.That(harness.Edge.StreamingCalls, Is.Zero);
        });
    }

    [Test]
    public async Task DisneyTypesTheTitleInItsOwnSearchField()
    {
        var platform = new FakePlatform(OperaGx)
        {
            AddressOf = _ => "www.disneyplus.com/es-419/browse/search",
            PageStep = new UserBrowserPageStep(false, "play", "Daredevil"),
        };
        platform.WindowsAfterOpen = [new(11, "Disney+ - Opera")];
        using Harness harness = new(platform);

        ExternalCapabilityReceipt receipt = await harness.Adapter.InvokeAsync(
            "streaming.play.named", Json("""{"service":"disney_plus","title":"Daredevil"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(platform.PageSteps, Is.EqualTo(new[] { (11, "Daredevil", true) }));
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            Assert.That(receipt.ErrorCode, Is.EqualTo(UserBrowserSurface.StreamingPlaybackUnconfirmed));
        });
    }

    [Test]
    public async Task AStreamingServiceAskingToSignInIsSaidAsSuch()
    {
        var platform = new FakePlatform(OperaGx) { AddressOf = _ => "www.netflix.com/login" };
        platform.WindowsAfterOpen = [new(11, "Netflix - Opera")];
        using Harness harness = new(platform);

        ExternalCapabilityReceipt receipt = await harness.Adapter.InvokeAsync(
            "streaming.play.named", Json("""{"service":"netflix","title":"Dark"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("netflix_authentication_required"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            Assert.That(platform.PageSteps, Is.Empty);
        });
    }

    [Test]
    public async Task StreamingResourceOpensInTheDefaultBrowser()
    {
        var platform = new FakePlatform(OperaGx) { AddressOf = _ => "www.netflix.com/title/80057281" };
        platform.WindowsAfterOpen = [new(11, "Stranger Things | Netflix - Opera")];
        using Harness harness = new(platform);

        ExternalCapabilityReceipt receipt = await harness.Adapter.InvokeAsync(
            "streaming.navigate",
            Json("""{"service":"netflix","resourceUri":"https://www.netflix.com/title/80057281"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("resourceUri").GetString(),
                Is.EqualTo("https://www.netflix.com/title/80057281"));
            Assert.That(receipt.Result?.GetProperty("browser").GetString(), Is.EqualTo("Opera GX"));
        });
    }

    [TestCase("Never Gonna Give You Up", "Rick Astley - Never Gonna Give You Up (Official Music Video)", true)]
    [TestCase("Despacito", "Luis Fonsi - Despacito ft. Daddy Yankee", true)]
    [TestCase("Canción del mariachi", "cancion del mariachi", true)]
    [TestCase("Their podcast", "Never Gonna Give You Up", false)]
    [TestCase("", "Never Gonna Give You Up", false)]
    public void MediaTitlesMatchAsAPersonWouldReadThem(string observed, string expected, bool match) =>
        Assert.That(UserBrowserSurface.TitlesMatch(observed, expected), Is.EqualTo(match));

    private static JsonElement Json(string value) => JsonDocument.Parse(value).RootElement.Clone();

    private static string YouTubePage(string id, string escapedTitle) =>
        "var ytInitialData = {\"contents\":{\"videoRenderer\":{\"videoId\":\"" + id
        + "\",\"thumbnail\":{\"thumbnails\":[]},\"title\":{\"runs\":[{\"text\":\"" + escapedTitle + "\"}]}}}};";

    private sealed class Harness : IDisposable
    {
        private readonly HttpClient _http;

        internal Harness(
            FakePlatform platform,
            IReadOnlyDictionary<string, string>? environment = null,
            string http = "<html></html>",
            CdpBrowserSessionContext? context = null)
        {
            Edge = new CountingEdge(Path.Combine(Path.GetTempPath(), "baxy-user-browser-" + Guid.NewGuid().ToString("N")));
            _http = new HttpClient(new FixedHttpHandler(http));
            var surface = new UserBrowserSurface(
                platform, name => environment is not null && environment.TryGetValue(name, out string? value) ? value : null);
            Adapter = new WebBrowserAdapter(Edge, _http, context, surface);
        }

        internal CountingEdge Edge { get; }

        internal WebBrowserAdapter Adapter { get; }

        public void Dispose()
        {
            Adapter.Dispose();
            _http.Dispose();
        }
    }

    internal sealed class CountingEdge(string profile) : CdpBrowserSession(profile)
    {
        internal int NavigateCalls { get; private set; }
        internal int ReadCalls { get; private set; }
        internal int YouTubeCalls { get; private set; }
        internal int StreamingCalls { get; private set; }

        internal override ValueTask<CdpNavigationResult> NavigateAsync(Uri target, CancellationToken cancellationToken)
        {
            NavigateCalls++;
            return ValueTask.FromResult(new CdpNavigationResult(
                true, true, target.AbsoluteUri, target.AbsoluteUri, "edge-page", string.Empty));
        }

        internal override ValueTask<CdpPageReadResult> ReadPageAsync(int maximumCharacters, CancellationToken cancellationToken)
        {
            ReadCalls++;
            return ValueTask.FromResult(new CdpPageReadResult(
                true, "edge-page", "https://edge.example/", "Edge", "Edge text", false, string.Empty));
        }

        internal override ValueTask<CdpMediaPlaybackResult> PlayYouTubeAsync(
            string query, Uri watchUri, CancellationToken cancellationToken)
        {
            YouTubeCalls++;
            return ValueTask.FromResult(new CdpMediaPlaybackResult(
                false, false, query, string.Empty, string.Empty, string.Empty, "edge_not_expected"));
        }

        internal override ValueTask<CdpStreamingPlaybackResult> PlayNetflixAsync(
            string title, CancellationToken cancellationToken)
        {
            StreamingCalls++;
            return ValueTask.FromResult(new CdpStreamingPlaybackResult(
                false, false, title, string.Empty, string.Empty, string.Empty, 0, "edge_not_expected"));
        }
    }

    private sealed class FakePlatform(UserBrowserIdentity? identity) : IUserBrowserPlatform
    {
        private bool _opened;

        internal bool OpenFails { get; init; }
        internal Func<nint, string?> AddressOf { get; init; } = _ => null;
        internal UserBrowserPageStep PageStep { get; init; } = new(false, "title", string.Empty);
        internal IReadOnlyList<UserBrowserWindow> WindowsBeforeOpen { get; set; } = [new(11, "Inicio - Opera")];
        internal IReadOnlyList<UserBrowserWindow>? WindowsAfterOpen { get; set; }
        internal IReadOnlyList<UserMediaSession> SessionsBeforeOpen { get; set; } = [];
        internal List<IReadOnlyList<UserMediaSession>> SessionsAfterOpen { get; set; } = [];
        internal Action<UserMediaSession>? OnPlay { get; set; }
        internal List<string> Opened { get; } = [];
        internal List<UserMediaSession> Played { get; } = [];
        internal List<(int, string, bool)> PageSteps { get; } = [];
        internal int AddressReads { get; private set; }

        public UserBrowserIdentity? ResolveDefault() => identity;

        public void Open(Uri address)
        {
            if (OpenFails)
                throw new System.ComponentModel.Win32Exception(1155, "No application is associated.");
            Opened.Add(address.AbsoluteUri);
            _opened = true;
        }

        public IReadOnlyList<UserBrowserWindow> ListWindows(string processName) =>
            processName == "opera"
                ? (_opened ? WindowsAfterOpen ?? WindowsBeforeOpen : WindowsBeforeOpen)
                : [];

        public ValueTask<IReadOnlyList<UserMediaSession>> ReadMediaSessionsAsync(CancellationToken cancellationToken)
        {
            if (!_opened)
                return ValueTask.FromResult(SessionsBeforeOpen);
            if (SessionsAfterOpen.Count == 0)
                return ValueTask.FromResult<IReadOnlyList<UserMediaSession>>([]);
            IReadOnlyList<UserMediaSession> current = SessionsAfterOpen[0];
            if (SessionsAfterOpen.Count > 1)
                SessionsAfterOpen.RemoveAt(0);
            return ValueTask.FromResult(current);
        }

        public ValueTask<bool> PlayMediaSessionAsync(UserMediaSession session, CancellationToken cancellationToken)
        {
            Played.Add(session);
            OnPlay?.Invoke(session);
            return ValueTask.FromResult(true);
        }

        public ValueTask<string?> ReadAddressAsync(nint window, CancellationToken cancellationToken)
        {
            AddressReads++;
            return ValueTask.FromResult(AddressOf(window));
        }

        public ValueTask<UserBrowserPageStep> StartTitleInPageAsync(
            nint window, string title, bool typeSearch, CancellationToken cancellationToken)
        {
            PageSteps.Add(((int)window, title, typeSearch));
            return ValueTask.FromResult(PageStep);
        }

        public ValueTask DelayAsync(TimeSpan delay, CancellationToken cancellationToken) => ValueTask.CompletedTask;
    }

    private sealed class FixedHttpHandler(string body) : HttpMessageHandler
    {
        protected override Task<HttpResponseMessage> SendAsync(
            HttpRequestMessage request, CancellationToken cancellationToken) => Task.FromResult(
                new HttpResponseMessage(HttpStatusCode.OK)
                {
                    Content = new StringContent(body, Encoding.UTF8, "text/html"),
                });
    }
}
