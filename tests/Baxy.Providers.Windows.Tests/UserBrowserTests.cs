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
    public async Task PageAndTabsAreReadFromThePersonsBrowserNeverFromTheProductBrowser()
    {
        var platform = new FakePlatform(OperaGx)
        {
            AddressOf = _ => "https://es.wikipedia.org/wiki/Valpara%C3%ADso",
            PageText = new UserBrowserPageText("Curicó - Wikipedia", "Curicó es una ciudad…", false),
            Tabs = [new("Curicó - Wikipedia", true), new("Gmail", false), new("YouTube", false)],
        };
        var context = new CdpBrowserSessionContext();
        using Harness harness = new(platform, context: context);

        ExternalCapabilityReceipt page = await harness.Adapter.InvokeAsync(
            "browser.page.read", Json("""{"maximumCharacters":2000}"""), CancellationToken.None);
        ExternalCapabilityReceipt tabs = await harness.Adapter.InvokeAsync(
            "browser.tabs.list", Json("""{"limit":2}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(page.Verified, Is.True);
            Assert.That(page.EffectObserved, Is.False);
            Assert.That(page.Result?.GetProperty("title").GetString(), Is.EqualTo("Curicó - Wikipedia"));
            Assert.That(page.Result?.GetProperty("text").GetString(), Is.EqualTo("Curicó es una ciudad…"));
            Assert.That(page.Result?.GetProperty("url").GetString(),
                Is.EqualTo("https://es.wikipedia.org/wiki/Valpara%C3%ADso"));
            Assert.That(page.Result?.GetProperty("authority").GetString(), Is.EqualTo(UserBrowserSurface.PageAuthority));
            Assert.That(page.Result?.GetProperty("browser").GetString(), Is.EqualTo("Opera GX"));
            Assert.That(platform.PageReads, Is.EqualTo(new[] { (11, 2000) }));
            Assert.That(tabs.Verified, Is.True);
            Assert.That(tabs.Result?.GetProperty("count").GetInt32(), Is.EqualTo(3));
            Assert.That(tabs.Result?.GetProperty("truncated").GetBoolean(), Is.True);
            Assert.That(tabs.Result?.GetProperty("tabs").GetArrayLength(), Is.EqualTo(2));
            Assert.That(tabs.Result?.GetProperty("tabs")[0].GetProperty("active").GetBoolean(), Is.True);
            Assert.That(harness.Edge.ReadCalls, Is.Zero);
            Assert.That(context.Active, Is.Null);
        });
    }

    private static readonly UserBrowserIdentity Chrome = new(
        "ChromeHTML", "chrome", "Google Chrome", @"C:\Program Files\Google\Chrome\Application\chrome.exe");

    private static UserBrowserFrame Frame(
        string page, int tabs = 3, bool? back = true, string address = "https://example.com/", double scroll = -1) =>
        new(
            [.. Enumerable.Range(0, tabs).Select(index => new UserBrowserTab(
                index == tabs - 1 ? "Mine" : "Theirs " + index, index == tabs - 1, true, 0.1 + index * 0.1, 0.02))],
            back,
            address,
            page,
            "Mine",
            scroll);

    private static async Task<ExternalCapabilityReceipt> Control(Harness harness, string action) =>
        await harness.Adapter.InvokeAsync(
            "browser.control", Json("{\"action\":\"" + action + "\"}"), CancellationToken.None);

    [Test]
    public async Task BackIsAWindowCommandToThePersonsBrowserVerifiedByAnotherPage()
    {
        var platform = new FakePlatform(OperaGx);
        platform.Frames.AddRange([Frame("doc-1"), Frame("doc-1"), Frame("doc-2", address: "https://example.org/")]);
        var context = new CdpBrowserSessionContext();
        using Harness harness = new(platform, context: context);

        ExternalCapabilityReceipt control = await Control(harness, "back");

        Assert.Multiple(() =>
        {
            Assert.That(control.Verified, Is.True);
            Assert.That(control.EffectObserved, Is.True);
            Assert.That(platform.AppCommands, Is.EqualTo(new[] { UserBrowserSurface.AppCommandBack }));
            Assert.That(control.Result?.GetProperty("observedState").GetString(), Is.EqualTo("went_back"));
            Assert.That(control.Result?.GetProperty("browser").GetString(), Is.EqualTo("Opera GX"));
            Assert.That(control.Result?.GetProperty("authority").GetString(),
                Is.EqualTo(UserBrowserSurface.FrameAuthority));
            Assert.That(platform.Opened, Is.Empty);
            Assert.That(context.Active, Is.Null, "the product browser is never used for the person's tabs");
        });
    }

    [Test]
    public async Task BackWithNoHistoryDoesNothingAndSaysSo()
    {
        var platform = new FakePlatform(OperaGx);
        platform.Frames.Add(Frame("doc-1", back: false));
        using Harness harness = new(platform);

        ExternalCapabilityReceipt control = await Control(harness, "back");

        Assert.Multiple(() =>
        {
            Assert.That(control.ErrorCode, Is.EqualTo(UserBrowserSurface.HistoryStart));
            Assert.That(control.EffectObserved || control.EffectMayHaveOccurred, Is.False);
            Assert.That(platform.AppCommands, Is.Empty);
        });
    }

    [Test]
    public async Task AReloadIsSeenAsANewDocumentAndNoChangeIsUnconfirmed()
    {
        var reloads = new FakePlatform(OperaGx);
        reloads.Frames.AddRange([Frame("doc-1"), Frame("doc-1"), Frame("doc-9")]);
        var stuck = new FakePlatform(OperaGx);
        stuck.Frames.Add(Frame("doc-1"));
        using Harness first = new(reloads);
        using Harness second = new(stuck);

        ExternalCapabilityReceipt reloaded = await Control(first, "reload");
        ExternalCapabilityReceipt unconfirmed = await Control(second, "reload");

        Assert.Multiple(() =>
        {
            Assert.That(reloaded.Verified, Is.True);
            Assert.That(reloads.AppCommands, Is.EqualTo(new[] { UserBrowserSurface.AppCommandRefresh }));
            Assert.That(reloaded.Result?.GetProperty("observedState").GetString(), Is.EqualTo("reloaded"));
            Assert.That(unconfirmed.Verified, Is.False);
            Assert.That(unconfirmed.EffectMayHaveOccurred, Is.True);
            Assert.That(unconfirmed.ErrorCode, Is.EqualTo(UserBrowserSurface.TabStepUnconfirmed));
        });
    }

    [Test]
    public async Task OperaGetsItsNewTabButtonPressedAndChromeItsOwnCommand()
    {
        var opera = new FakePlatform(OperaGx);
        opera.Frames.AddRange([Frame("doc-1", tabs: 3), Frame("doc-2", tabs: 4)]);
        var chrome = new FakePlatform(Chrome);
        chrome.Frames.AddRange([Frame("doc-1", tabs: 2), Frame("doc-2", tabs: 3)]);
        using Harness inOpera = new(opera);
        using Harness inChrome = new(chrome);

        ExternalCapabilityReceipt operaTab = await Control(inOpera, "new_tab");
        ExternalCapabilityReceipt chromeTab = await Control(inChrome, "new_tab");

        Assert.Multiple(() =>
        {
            Assert.That(operaTab.Verified, Is.True);
            Assert.That(opera.BrowserCommands, Is.Empty, "Opera runs no IDC_* message: no wait for one");
            Assert.That(opera.Acts, Is.EqualTo(new[] { "new_tab" }));
            Assert.That(operaTab.Result?.GetProperty("observedState").GetString(), Is.EqualTo("tab_opened"));
            Assert.That(operaTab.Result?.GetProperty("tabCount").GetInt32(), Is.EqualTo(4));
            Assert.That(chromeTab.Verified, Is.True);
            Assert.That(chrome.BrowserCommands, Is.EqualTo(new[] { UserBrowserSurface.BrowserCommandNewTab }));
            Assert.That(chrome.Acts, Is.Empty);
        });
    }

    [Test]
    public async Task TheActiveTabIsClosedWhereItIsAndSeenAsOneTabLess()
    {
        var opera = new FakePlatform(OperaGx);
        opera.Frames.AddRange([Frame("doc-1", tabs: 3), Frame("doc-1", tabs: 3), Frame("doc-7", tabs: 2)]);
        var chrome = new FakePlatform(Chrome);
        chrome.Frames.AddRange([Frame("doc-1", tabs: 3), Frame("doc-7", tabs: 2)]);
        using Harness inOpera = new(opera);
        using Harness inChrome = new(chrome);

        ExternalCapabilityReceipt operaClose = await Control(inOpera, "close");
        ExternalCapabilityReceipt chromeClose = await Control(inChrome, "close");

        Assert.Multiple(() =>
        {
            Assert.That(operaClose.Verified, Is.True);
            Assert.That(opera.MiddleClicks, Is.EqualTo(new[] { (0.30000000000000004, 0.02) }),
                "the click goes to the active tab's own place");
            Assert.That(operaClose.Result?.GetProperty("observedState").GetString(), Is.EqualTo("tab_closed"));
            Assert.That(operaClose.Result?.GetProperty("closedTab").GetString(), Is.EqualTo("Mine"));
            Assert.That(operaClose.Result?.GetProperty("tabCount").GetInt32(), Is.EqualTo(2));
            Assert.That(chromeClose.Verified, Is.True);
            Assert.That(chrome.BrowserCommands, Is.EqualTo(new[] { UserBrowserSurface.BrowserCommandCloseTab }));
            Assert.That(chrome.MiddleClicks, Is.Empty);
        });
    }

    [Test]
    public async Task ATabThatMovedIsNeverClickedAndTheLastTabIsKept()
    {
        var moved = new FakePlatform(OperaGx);
        UserBrowserFrame switched = Frame("doc-3", tabs: 3) with
        {
            Tabs = [new("Theirs 0", true, true, 0.1, 0.02), new("Theirs 1", false, true, 0.2, 0.02), new("Mine", false, true, 0.3, 0.02)],
        };
        moved.Frames.AddRange([Frame("doc-1", tabs: 3), switched]);
        var single = new FakePlatform(OperaGx);
        single.Frames.Add(Frame("doc-1", tabs: 1));
        using Harness first = new(moved);
        using Harness second = new(single);

        ExternalCapabilityReceipt notClicked = await Control(first, "close");
        ExternalCapabilityReceipt kept = await Control(second, "close");

        Assert.Multiple(() =>
        {
            Assert.That(notClicked.Verified, Is.False);
            Assert.That(notClicked.EffectMayHaveOccurred, Is.False, "nothing was posted");
            Assert.That(notClicked.ErrorCode, Is.EqualTo(UserBrowserSurface.TabStepUnavailable));
            Assert.That(moved.MiddleClicks, Is.Empty);
            Assert.That(kept.ErrorCode, Is.EqualTo(UserBrowserSurface.LastTabKept));
            Assert.That(kept.EffectMayHaveOccurred, Is.False);
            Assert.That(single.MiddleClicks, Is.Empty);
        });
    }

    [Test]
    public async Task EveryTabButTheLastIsClosedOneAtATimeAndEachCloseIsSeen()
    {
        var chrome = new FakePlatform(Chrome);
        chrome.Frames.AddRange([Frame("doc-1", tabs: 3), Frame("doc-2", tabs: 2), Frame("doc-3", tabs: 1)]);
        var opera = new FakePlatform(OperaGx);
        opera.Frames.AddRange([
            Frame("doc-1", tabs: 3), Frame("doc-1", tabs: 3), Frame("doc-2", tabs: 2), Frame("doc-2", tabs: 2),
            Frame("doc-3", tabs: 1)]);
        using Harness inChrome = new(chrome);
        using Harness inOpera = new(opera);

        ExternalCapabilityReceipt chromeAll = await Control(inChrome, "close_all");
        ExternalCapabilityReceipt operaAll = await Control(inOpera, "close_all");

        Assert.Multiple(() =>
        {
            Assert.That(chromeAll.Verified, Is.True);
            Assert.That(chromeAll.EffectObserved, Is.True);
            Assert.That(chrome.BrowserCommands, Is.EqualTo(new[]
            {
                UserBrowserSurface.BrowserCommandCloseTab, UserBrowserSurface.BrowserCommandCloseTab,
            }));
            Assert.That(chrome.MiddleClicks, Is.Empty);
            Assert.That(chromeAll.Result?.GetProperty("observedState").GetString(), Is.EqualTo("tabs_closed"));
            Assert.That(chromeAll.Result?.GetProperty("closedTabs").GetInt32(), Is.EqualTo(2));
            Assert.That(chromeAll.Result?.GetProperty("tabCount").GetInt32(), Is.EqualTo(1));
            Assert.That(chromeAll.Result?.GetProperty("activeTab").GetString(), Is.EqualTo("Mine"));
            Assert.That(chromeAll.Result?.GetProperty("authority").GetString(),
                Is.EqualTo(UserBrowserSurface.FrameAuthority));
            Assert.That(operaAll.Verified, Is.True);
            Assert.That(opera.BrowserCommands, Is.Empty);
            Assert.That(opera.MiddleClicks, Has.Count.EqualTo(2), "each close is a click on the tab then active");
            Assert.That(operaAll.Result?.GetProperty("closedTabs").GetInt32(), Is.EqualTo(2));
            Assert.That(inChrome.Edge.ReadCalls + inOpera.Edge.ReadCalls, Is.Zero);
        });
    }

    [Test]
    public async Task ClosingEveryTabKeepsTheLastAndAStoppedCloseSaysHowManyWereClosed()
    {
        var single = new FakePlatform(Chrome);
        single.Frames.Add(Frame("doc-1", tabs: 1));
        var stuck = new FakePlatform(Chrome);
        stuck.Frames.AddRange([Frame("doc-1", tabs: 3), Frame("doc-2", tabs: 2)]);
        using Harness first = new(single);
        using Harness second = new(stuck);

        ExternalCapabilityReceipt kept = await Control(first, "close_all");
        ExternalCapabilityReceipt stopped = await Control(second, "close_all");

        Assert.Multiple(() =>
        {
            Assert.That(kept.ErrorCode, Is.EqualTo(UserBrowserSurface.LastTabKept));
            Assert.That(kept.EffectObserved || kept.EffectMayHaveOccurred, Is.False);
            Assert.That(single.BrowserCommands, Is.Empty);
            Assert.That(single.MiddleClicks, Is.Empty);
            Assert.That(kept.Result?.GetProperty("observedState").GetString(), Is.EqualTo("nothing_to_close"));
            Assert.That(kept.Result?.GetProperty("closedTabs").GetInt32(), Is.Zero);
            Assert.That(kept.Result?.GetProperty("tabCount").GetInt32(), Is.EqualTo(1));
            Assert.That(stopped.Verified, Is.False);
            Assert.That(stopped.ErrorCode, Is.EqualTo(UserBrowserSurface.TabStepUnconfirmed));
            Assert.That(stopped.EffectObserved, Is.True, "one tab was seen closed");
            Assert.That(stopped.EffectMayHaveOccurred, Is.True);
            Assert.That(stopped.Result?.GetProperty("closedTabs").GetInt32(), Is.EqualTo(1));
            Assert.That(stopped.Result?.TryGetProperty("tabCount", out _), Is.False, "what is left is not guessed");
            Assert.That(stuck.BrowserCommands, Has.Count.EqualTo(2));
        });
    }

    [Test]
    public async Task ScrollingIsReadBackFromThePageAndAnEndMovesNothing()
    {
        var scrolls = new FakePlatform(OperaGx) { ActResult = _ => new UserBrowserAct("scrolled", 0, 21.04) };
        var ends = new FakePlatform(OperaGx) { ActResult = _ => new UserBrowserAct("boundary", 100, 100) };
        using Harness first = new(scrolls);
        using Harness second = new(ends);

        ExternalCapabilityReceipt down = await Control(first, "scroll_down");
        ExternalCapabilityReceipt end = await Control(second, "scroll_down");

        Assert.Multiple(() =>
        {
            Assert.That(down.Verified, Is.True);
            Assert.That(down.EffectObserved, Is.True);
            Assert.That(scrolls.Acts, Is.EqualTo(new[] { "scroll_down" }));
            Assert.That(down.Result?.GetProperty("scrollPercent").GetDouble(), Is.EqualTo(21.0));
            Assert.That(end.ErrorCode, Is.EqualTo(UserBrowserSurface.ScrollBoundary));
            Assert.That(end.EffectObserved || end.EffectMayHaveOccurred, Is.False);
        });
    }

    [Test]
    public async Task FullScreenIsTheWindowCoveringItsMonitor()
    {
        var goes = new FakePlatform(OperaGx);
        goes.Covers.AddRange([false, false, true]);
        var missing = new FakePlatform(OperaGx) { ActResult = _ => new UserBrowserAct("fullscreen_control_not_found", -1, -1) };
        using Harness first = new(goes);
        using Harness second = new(missing);

        ExternalCapabilityReceipt full = await Control(first, "fullscreen_video");
        ExternalCapabilityReceipt none = await Control(second, "fullscreen_video");

        Assert.Multiple(() =>
        {
            Assert.That(full.Verified, Is.True);
            Assert.That(full.Result?.GetProperty("observedState").GetString(), Is.EqualTo("fullscreen"));
            Assert.That(none.ErrorCode, Is.EqualTo(UserBrowserSurface.FullscreenControlMissing));
            Assert.That(none.EffectMayHaveOccurred, Is.False);
        });
    }

    [Test]
    public void TheFrameReadKeepsATabStripOfOneAndTheBackButtonState()
    {
        using JsonDocument one = JsonDocument.Parse(
            """{"version":1,"ok":true,"tabs":{"title":"Solo","selected":true,"shown":true,"x":0.2,"y":0.01},"back":"disabled","address":"example.com","page":{"id":"42.1","title":"Solo","scroll":12.5}}""");
        using JsonDocument none = JsonDocument.Parse("""{"version":1,"ok":false,"tabs":[],"error":"tab_strip_not_found"}""");

        UserBrowserFrame? frame = WindowsUserBrowserPlatform.ParseFrame(one.RootElement);

        Assert.Multiple(() =>
        {
            Assert.That(frame?.Tabs, Has.Count.EqualTo(1));
            Assert.That(frame?.Tabs[0], Is.EqualTo(new UserBrowserTab("Solo", true, true, 0.2, 0.01)));
            Assert.That(frame?.BackEnabled, Is.False);
            Assert.That(frame?.PageId, Is.EqualTo("42.1"));
            Assert.That(frame?.Scroll, Is.EqualTo(12.5));
            Assert.That(WindowsUserBrowserPlatform.ParseFrame(none.RootElement), Is.Null);
        });
    }

    [Test]
    public async Task NothingIsReadWhenThePersonsBrowserIsClosed()
    {
        var platform = new FakePlatform(OperaGx) { WindowsBeforeOpen = [] };
        using Harness harness = new(platform);

        ExternalCapabilityReceipt page = await harness.Adapter.InvokeAsync(
            "browser.page.read", Json("""{"maximumCharacters":2000}"""), CancellationToken.None);
        ExternalCapabilityReceipt tabs = await harness.Adapter.InvokeAsync(
            "browser.tabs.list", Json("""{"limit":20}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(page.ErrorCode, Is.EqualTo(UserBrowserSurface.BrowserNotRunning));
            Assert.That(tabs.ErrorCode, Is.EqualTo(UserBrowserSurface.BrowserNotRunning));
            Assert.That(harness.Edge.ReadCalls, Is.Zero);
        });
    }

    [Test]
    public async Task APageThatCannotBeReadIsSaidAsSuch()
    {
        var platform = new FakePlatform(OperaGx);
        using Harness harness = new(platform);

        ExternalCapabilityReceipt page = await harness.Adapter.InvokeAsync(
            "browser.page.read", Json("""{"maximumCharacters":2000}"""), CancellationToken.None);
        ExternalCapabilityReceipt tabs = await harness.Adapter.InvokeAsync(
            "browser.tabs.list", Json("""{"limit":20}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(page.ErrorCode, Is.EqualTo(UserBrowserSurface.PageUnreadable));
            Assert.That(tabs.ErrorCode, Is.EqualTo(UserBrowserSurface.PageUnreadable));
            Assert.That(page.EffectMayHaveOccurred, Is.False);
            Assert.That(harness.Edge.ReadCalls, Is.Zero);
        });
    }

    [Test]
    public async Task TheProductBrowserIsReadOnlyWhenAMeasurementAsksForIt()
    {
        var platform = new FakePlatform(OperaGx);
        using Harness harness = new(platform, new Dictionary<string, string> { ["BAXY_BROWSER"] = "product" });

        ExternalCapabilityReceipt page = await harness.Adapter.InvokeAsync(
            "browser.page.read", Json("""{"maximumCharacters":2000}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(page.Verified, Is.True);
            Assert.That(harness.Edge.ReadCalls, Is.EqualTo(1));
            Assert.That(platform.PageReads, Is.Empty);
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
            Assert.That(platform.Opened, Is.EqualTo(new[] { "https://www.disneyplus.com/browse/search" }));
            Assert.That(platform.PageSteps, Is.EqualTo(new[] { (11, "Daredevil", true) }));
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            Assert.That(receipt.ErrorCode, Is.EqualTo(UserBrowserSurface.StreamingPlaybackUnconfirmed));
        });
    }

    [Test]
    public async Task HboMaxSearchesInTheAddressAndIsVerifiedByTheSessionOfTheTitle()
    {
        // Opera GX 2026-10-06: «pon The Last of Us en HBO Max» → search/result?q=, card, «Ver The Last of Us, …»,
        // and the browser's one media session turns from what it had into «The Last of Us» playing.
        var platform = new FakePlatform(OperaGx)
        {
            AddressOf = _ => "play.hbomax.com/search/result?q=The+Last+of+Us",
            PageStep = new UserBrowserPageStep(true, "play_invoked", "The Last of Us"),
        };
        var before = new UserMediaSession("Opera GXStable", "Daredevil | Disney+", string.Empty, "paused");
        platform.SessionsBeforeOpen = [before];
        platform.WindowsAfterOpen = [new(11, "Buscar: The Last of Us • HBO Max - Opera")];
        platform.SessionsAfterOpen = [[before], [before], [new("Opera GXStable", "The Last of Us", string.Empty, "playing")]];
        using Harness harness = new(platform);

        ExternalCapabilityReceipt receipt = await harness.Adapter.InvokeAsync(
            "streaming.play.named", Json("""{"service":"hbo_max","title":"the last of us"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(platform.Opened, Is.EqualTo(new[] { "https://play.hbomax.com/search/result?q=the+last+of+us" }));
            Assert.That(platform.PageSteps, Is.EqualTo(new[] { (11, "the last of us", false) }));
            Assert.That(receipt.Result?.GetProperty("title").GetString(), Is.EqualTo("The Last of Us"));
            Assert.That(receipt.Result?.GetProperty("sessionTitle").GetString(), Is.EqualTo("The Last of Us"));
            Assert.That(receipt.Result?.GetProperty("service").GetString(), Is.EqualTo("hbo_max"));
            Assert.That(platform.Played, Is.Empty);
            Assert.That(harness.Edge.StreamingCalls, Is.Zero);
        });
    }

    [Test]
    public async Task ATitleThePersonHadPausedIsNotTakenForTheOneJustAskedFor()
    {
        // Opera keeps one media session for the whole browser: «Bluey | Disney+» paused in another tab is theirs.
        var platform = new FakePlatform(OperaGx)
        {
            AddressOf = _ => "www.disneyplus.com/browse/search",
            PageStep = new UserBrowserPageStep(true, "play_invoked", "Bluey"),
        };
        var theirs = new UserMediaSession("Opera GXStable", "Bluey | Disney+", string.Empty, "paused");
        platform.SessionsBeforeOpen = [theirs];
        platform.WindowsAfterOpen = [new(11, "Búsqueda | Disney+ - Opera")];
        platform.SessionsAfterOpen = [[theirs]];
        using Harness harness = new(platform);

        ExternalCapabilityReceipt receipt = await harness.Adapter.InvokeAsync(
            "streaming.play.named", Json("""{"service":"disney_plus","title":"Bluey"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo(UserBrowserSurface.StreamingPlaybackUnconfirmed));
            Assert.That(platform.Played, Is.Empty);
        });
    }

    [Test]
    public async Task AWhoIsWatchingGateIsLeftToThePerson()
    {
        var platform = new FakePlatform(OperaGx)
        {
            AddressOf = _ => "play.hbomax.com/search/result?q=Superman",
            PageStep = new UserBrowserPageStep(false, "profile", string.Empty),
        };
        platform.WindowsAfterOpen = [new(11, "HBO Max - Opera")];
        platform.SessionsAfterOpen = [[new("Opera GXStable", "Tráiler", string.Empty, "playing")]];
        using Harness harness = new(platform);

        ExternalCapabilityReceipt receipt = await harness.Adapter.InvokeAsync(
            "streaming.play.named", Json("""{"service":"hbo_max","title":"Superman"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            Assert.That(receipt.ErrorCode, Is.EqualTo(UserBrowserSurface.StreamingProfileChoice));
            Assert.That(harness.Edge.StreamingCalls, Is.Zero);
        });
    }

    [Test]
    public async Task HboMaxSigningInOnItsOwnAuthHostIsSaidAsSuch()
    {
        int reads = 0;
        var platform = new FakePlatform(OperaGx)
        {
            AddressOf = _ => ++reads == 1 ? "play.hbomax.com/search/result?q=Dune" : "auth.hbomax.com/login",
        };
        platform.WindowsAfterOpen = [new(11, "HBO Max - Opera")];
        using Harness harness = new(platform);

        ExternalCapabilityReceipt receipt = await harness.Adapter.InvokeAsync(
            "streaming.play.named", Json("""{"service":"hbo_max","title":"Dune"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("hbo_max_authentication_required"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            Assert.That(platform.PageSteps, Is.Empty);
        });
    }

    [Test]
    public async Task HboMaxIsNeverOpenedInTheProductBrowser()
    {
        var platform = new FakePlatform(null);
        using Harness harness = new(platform);

        ExternalCapabilityReceipt receipt = await harness.Adapter.InvokeAsync(
            "streaming.play.named", Json("""{"service":"hbo_max","title":"Dune"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo(WebBrowserAdapter.HboMaxNeedsDefaultBrowser));
            Assert.That(harness.Edge.StreamingCalls + harness.Edge.NavigateCalls, Is.Zero);
        });
    }

    [TestCase("play.hbomax.com", true)]
    [TestCase("auth.hbomax.com", true)]
    [TestCase("play.max.com", true)]
    [TestCase("maxhbo.com", false)]
    public void HboMaxHostsBelongToTheService(string host, bool belongs) =>
        Assert.That(WebBrowserAdapter.HostMatchesService(host, "hbo_max"), Is.EqualTo(belongs));

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
        internal UserBrowserPageText? PageText { get; init; }
        internal IReadOnlyList<UserBrowserTab>? Tabs { get; init; }
        internal List<(int, int)> PageReads { get; } = [];

        public UserBrowserIdentity? ResolveDefault() => identity;

        public void Open(Uri address)
        {
            if (OpenFails)
                throw new System.ComponentModel.Win32Exception(1155, "No application is associated.");
            Opened.Add(address.AbsoluteUri);
            _opened = true;
        }

        public IReadOnlyList<UserBrowserWindow> ListWindows(string processName) =>
            processName == identity?.ProcessName
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

        /// <summary>Frames read in turn (the last one stays); without them, a frame made of <see cref="Tabs"/>.</summary>
        internal List<UserBrowserFrame?> Frames { get; } = [];
        internal int FrameReads { get; private set; }
        internal List<int> AppCommands { get; } = [];
        internal List<int> BrowserCommands { get; } = [];
        internal List<(double, double)> MiddleClicks { get; } = [];
        internal List<string> Acts { get; } = [];
        internal Func<string, UserBrowserAct> ActResult { get; init; } = _ => new UserBrowserAct("invoked", -1, -1);
        internal Action? OnMessage { get; init; }
        internal List<bool> Covers { get; } = [];

        public ValueTask<UserBrowserFrame?> ReadFrameAsync(nint window, CancellationToken cancellationToken)
        {
            FrameReads++;
            if (Frames.Count == 0)
                return ValueTask.FromResult(Tabs is null ? null : new UserBrowserFrame(Tabs, true, "", "doc-1", "", -1));
            UserBrowserFrame? current = Frames[0];
            if (Frames.Count > 1)
                Frames.RemoveAt(0);
            return ValueTask.FromResult(current);
        }

        public bool PostAppCommand(nint window, int command)
        {
            AppCommands.Add(command);
            OnMessage?.Invoke();
            return true;
        }

        public bool PostBrowserCommand(nint window, int command)
        {
            BrowserCommands.Add(command);
            OnMessage?.Invoke();
            return true;
        }

        public bool PostMiddleClick(nint window, double x, double y)
        {
            MiddleClicks.Add((x, y));
            OnMessage?.Invoke();
            return true;
        }

        public ValueTask<UserBrowserAct> ActAsync(nint window, string action, CancellationToken cancellationToken)
        {
            Acts.Add(action);
            OnMessage?.Invoke();
            return ValueTask.FromResult(ActResult(action));
        }

        public bool CoversMonitor(nint window)
        {
            bool current = Covers.Count > 0 && Covers[0];
            if (Covers.Count > 1)
                Covers.RemoveAt(0);
            return current;
        }

        public ValueTask<UserBrowserPageText?> ReadPageTextAsync(
            nint window, int maximumCharacters, CancellationToken cancellationToken)
        {
            PageReads.Add(((int)window, maximumCharacters));
            return ValueTask.FromResult(PageText);
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
