using System.Net;
using System.Text;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using Microsoft.Win32;
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

    // A new tab or the browser's start page leaves the address field empty: the read finds no address there.
    // The whole frame read with no address on show (a new tab, the start page): an empty value, not «not read» (null).
    private static string? EmptyAddressField(nint window) => string.Empty;

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

    // Feria (NB-W5): Windows 11 from 25H2 writes the default browser to UserChoiceLatest\ProgId and leaves the legacy
    // UserChoice on the one chosen before; reading the legacy key opened links in the old browser.
    [Test]
    public void TheDefaultBrowserIsTheNewerChoiceWhenWindowsKeepsBoth()
    {
        string root = @"Software\BAXY-tests-" + Guid.NewGuid().ToString("N");
        try
        {
            using RegistryKey both = Registry.CurrentUser.CreateSubKey(root + @"\both");
            using (RegistryKey legacy = both.CreateSubKey("UserChoice")) legacy.SetValue("ProgId", "ChromeHTML");
            using (RegistryKey latest = both.CreateSubKey(@"UserChoiceLatest\ProgId")) latest.SetValue("ProgId", "Opera GXStable");
            using RegistryKey legacyOnly = Registry.CurrentUser.CreateSubKey(root + @"\legacy");
            using (RegistryKey legacy = legacyOnly.CreateSubKey("UserChoice")) legacy.SetValue("ProgId", "MSEdgeHTM");
            using RegistryKey emptyLatest = Registry.CurrentUser.CreateSubKey(root + @"\empty-latest");
            using (RegistryKey legacy = emptyLatest.CreateSubKey("UserChoice")) legacy.SetValue("ProgId", "ChromeHTML");
            emptyLatest.CreateSubKey(@"UserChoiceLatest\ProgId").Dispose();
            using RegistryKey none = Registry.CurrentUser.CreateSubKey(root + @"\none");

            Assert.Multiple(() =>
            {
                Assert.That(UserBrowserIdentityResolver.ChosenProgId(both), Is.EqualTo("Opera GXStable"));
                Assert.That(UserBrowserIdentityResolver.ChosenProgId(legacyOnly), Is.EqualTo("MSEdgeHTM"));
                Assert.That(UserBrowserIdentityResolver.ChosenProgId(emptyLatest), Is.EqualTo("ChromeHTML"));
                Assert.That(UserBrowserIdentityResolver.ChosenProgId(none), Is.Null);
            });
        }
        finally
        {
            Registry.CurrentUser.DeleteSubKeyTree(root, throwOnMissingSubKey: false);
        }
    }

    [Test]
    public async Task AYouTubeResultsPageOverItsBoundIsNotReadToTheEnd()
    {
        // Ronda q-web: the whole body was read into memory and only then held to its 4 MB; the read stops at the bound.
        var body = new CountingStream(64 * 1024 * 1024);
        using var http = new HttpClient(new StreamHttpHandler(body));

        YouTubeSearchResult video = await YouTubeSearch.FirstVideoAsync(http, "red lista", CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(video.ErrorCode, Is.EqualTo("youtube_search_response_too_large"));
            Assert.That(body.BytesRead, Is.LessThanOrEqualTo(4_000_000 + 128 * 1024));
        });
    }

    [Test]
    public async Task AYouTubeResultsPageThatStopsMidBodyEndsAtTheClientTimeout()
    {
        var body = new CountingStream(64 * 1024, stallAfter: 16 * 1024);
        using var http = new HttpClient(new StreamHttpHandler(body)) { Timeout = TimeSpan.FromMilliseconds(300) };

        Task<YouTubeSearchResult> search = YouTubeSearch.FirstVideoAsync(http, "red lista", CancellationToken.None).AsTask();
        Task finished = await Task.WhenAny(search, Task.Delay(TimeSpan.FromSeconds(10)));

        Assert.That(finished, Is.SameAs(search), "the body read is bounded in time too");
        Assert.That((await search).ErrorCode, Is.EqualTo("youtube_search_timeout"));
    }

    [Test]
    public void YouTubeResultsPageGivesTheFirstVideoAndItsOwnTitle()
    {
        YouTubeSearchResult video = YouTubeSearch.Parse(YouTubePage("dQw4w9WgXcQ", "Rick Astley \\u0026 Co - Never"));
        YouTubeSearchResult none = YouTubeSearch.Parse("<html><script>var ytInitialData = {};</script></html>");
        // Ronda final 11: a page without the results data (consent, captcha) is not read, never «no video».
        YouTubeSearchResult unread = YouTubeSearch.Parse("<html>nothing</html>");

        Assert.Multiple(() =>
        {
            Assert.That(video.Found, Is.True);
            Assert.That(video.VideoId, Is.EqualTo("dQw4w9WgXcQ"));
            Assert.That(video.Title, Is.EqualTo("Rick Astley & Co - Never"));
            Assert.That(video.WatchUri.AbsoluteUri, Is.EqualTo("https://www.youtube.com/watch?v=dQw4w9WgXcQ"));
            Assert.That(none.ErrorCode, Is.EqualTo("youtube_result_not_found"));
            Assert.That(unread.ErrorCode, Is.EqualTo("youtube_search_page_unreadable"));
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
            Assert.That(platform.Fronted, Is.EqualTo(new[] { 11 }), "the page asked to be seen is put in front");
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
            Assert.That(receipt.Result?.GetRawText(), Does.Not.Contain("finalUrl").And.Not.Contain("mail.example.org"));
            Assert.That(harness.Edge.NavigateCalls, Is.Zero, "an opened link is never repeated elsewhere");
            Assert.That(platform.Fronted, Is.Empty, "another site's window is never put in front");
        });
    }

    private const string OldSearch = "www.google.com/search?q=si+hay+pel%C3%ADcula+de+El+Aleph";
    private const string AskedSearch = "https://www.google.com/search?q=los+horarios+del+cercanias+de+madrid";

    [Test]
    public async Task AnotherSearchThePersonHadOpenIsNeverTakenForTheOneAskedFor()
    {
        // Uso real v3 t4 (c10): the Google tab of the previous conversation was still on show in the window whose
        // title moved; the host matched and BAXY announced that old search as the one it had opened.
        var platform = new FakePlatform(OperaGx)
        {
            WindowsBeforeOpen = [new(11, "si hay película de El Aleph - Buscar con Google - Opera")],
            AddressOf = _ => OldSearch,
        };
        platform.WindowsAfterOpen = [new(11, "Buscar con Google - Opera")];
        using Harness harness = new(platform);

        ExternalCapabilityReceipt receipt = await harness.Adapter.InvokeAsync(
            "browser.navigate", Json($$"""{"url":"{{AskedSearch}}"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            Assert.That(receipt.ErrorCode, Is.EqualTo(UserBrowserSurface.NavigationUnconfirmed));
            Assert.That(receipt.Result?.GetRawText(), Does.Not.Contain("finalUrl").And.Not.Contain("Aleph"),
                "the old search is never reported as the arrival");
            Assert.That(platform.BaselineReads, Is.EqualTo(1), "only the front window is read before the link opens");
            Assert.That(harness.Edge.NavigateCalls, Is.Zero);
        });
    }

    private const string ShownSearch = "www.google.com/search?q=los+horarios+del+cercanias+de+madrid";

    [Test]
    public async Task TheDestinationAlreadyOnShowInTheFrontWindowIsAnArrival()
    {
        // Semilla r8 t3: the same search opened again in a new tab leaves the window's title as it was; the front
        // window still showing the destination after the link is opened is what the person sees.
        var platform = new FakePlatform(OperaGx)
        {
            WindowsBeforeOpen = [new(11, "los horarios del cercanias de madrid - Buscar con Google - Opera")],
            AddressOf = _ => ShownSearch,
        };
        using Harness harness = new(platform);

        ExternalCapabilityReceipt receipt = await harness.Adapter.InvokeAsync(
            "browser.navigate", Json($$"""{"url":"{{AskedSearch}}"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("finalUrl").GetString(), Is.EqualTo("https://" + ShownSearch));
            Assert.That(platform.AddressReads, Is.EqualTo(1), "one read of the front window after the link opened");
            Assert.That(harness.Edge.NavigateCalls, Is.Zero);
            // Review r10a finding 6: nothing was seen to open; the receipt says the page was already on show.
            Assert.That(receipt.Result?.GetProperty("authority").GetString(), Is.EqualTo(UserBrowserSurface.AlreadyShownAuthority));
        });
    }

    [Test]
    public async Task ALoadingTabTitledWithTheDestinationIsTheArrivalWhenTheAddressFieldIsStale()
    {
        // Semilla r8 t2 (probe 2026-10-08): Opera GX's address field kept the previous search for minutes while the
        // new tab, still loading, titled the window with its own address.
        var platform = new FakePlatform(OperaGx)
        {
            WindowsBeforeOpen = [new(11, "si hay película de El Aleph - Buscar con Google - Opera")],
            AddressOf = _ => OldSearch,
        };
        platform.WindowSteps.Add([new(11, "Cargando… - Opera")]);
        platform.WindowSteps.Add([new(11, "google.com/search?q=los+horarios+del+cercanías+de+madrid - Opera")]);
        using Harness harness = new(platform);

        ExternalCapabilityReceipt receipt = await harness.Adapter.InvokeAsync(
            "browser.navigate",
            Json("""{"url":"https://www.google.com/search?q=los+horarios+del+cercan%C3%ADas+de+madrid"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("authority").GetString(),
                Is.EqualTo(UserBrowserSurface.TitleAuthority));
            Assert.That(platform.AddressReads, Is.EqualTo(1), "only the loading title was read through UIA");
        });
    }

    [Test]
    public async Task AWindowTitledWithAnotherAddressIsNeverTheArrival()
    {
        // Contracaso: another search's address in the title, or a page title that is no address, proves nothing.
        var platform = new FakePlatform(OperaGx)
        {
            AddressOf = _ => OldSearch,
        };
        platform.WindowSteps.Add([new(11, "google.com/search?q=si+hay+película+de+El+Aleph - Opera")]);
        platform.WindowSteps.Add([new(11, "Buscar con Google - Opera")]);
        using Harness harness = new(platform);

        ExternalCapabilityReceipt receipt = await harness.Adapter.InvokeAsync(
            "browser.navigate", Json($$"""{"url":"{{AskedSearch}}"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo(UserBrowserSurface.NavigationUnconfirmed));
            Assert.That(UserBrowserSurface.TitleAddress("Buscar con Google - Opera"), Is.Null);
            Assert.That(UserBrowserSurface.TitleAddress("Inicio - Opera"), Is.Null);
        });
    }

    [Test]
    public async Task TheDestinationOnShowBeforeButGoneAfterTheLinkStaysUnconfirmed()
    {
        // Contracaso: what the front window showed before the link is opened is never the arrival by itself.
        var platform = new FakePlatform(OperaGx)
        {
            WindowsBeforeOpen = [new(11, "los horarios del cercanias de madrid - Buscar con Google - Opera")],
            AddressBeforeOpen = _ => ShownSearch,
            AddressOf = _ => OldSearch,
        };
        using Harness harness = new(platform);

        ExternalCapabilityReceipt receipt = await harness.Adapter.InvokeAsync(
            "browser.navigate", Json($$"""{"url":"{{AskedSearch}}"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo(UserBrowserSurface.NavigationUnconfirmed));
            Assert.That(receipt.Result?.GetRawText(), Does.Not.Contain("finalUrl"));
        });
    }

    [Test]
    public async Task AnotherQueryOnTheSamePageIsNoRedirectEvenInANewWindow()
    {
        var platform = new FakePlatform(OperaGx)
        {
            AddressBeforeOpen = EmptyAddressField,
            AddressOf = window => window == 12 ? OldSearch : null,
        };
        platform.WindowsAfterOpen = [new(11, "Inicio - Opera"), new(12, "Buscar con Google - Opera")];
        using Harness harness = new(platform);

        ExternalCapabilityReceipt receipt = await harness.Adapter.InvokeAsync(
            "browser.navigate", Json($$"""{"url":"{{AskedSearch}}"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo(UserBrowserSurface.NavigationUnconfirmed));
        });
    }

    [Test]
    public async Task TheSearchAskedForIsWaitedForPastTheTabOfAnotherOne()
    {
        int reads = 0;
        var platform = new FakePlatform(OperaGx)
        {
            WindowsBeforeOpen = [new(11, "si hay película de El Aleph - Buscar con Google - Opera")],
            AddressBeforeOpen = _ => OldSearch,
            AddressOf = _ => ++reads == 1 ? OldSearch : AskedSearch.Replace("https://", string.Empty),
        };
        platform.WindowSteps.Add([new(11, "Buscar con Google - Opera")]);
        platform.WindowSteps.Add([new(11, "los horarios del cercanias de madrid - Buscar con Google - Opera")]);
        using Harness harness = new(platform);

        ExternalCapabilityReceipt receipt = await harness.Adapter.InvokeAsync(
            "browser.navigate", Json($$"""{"url":"{{AskedSearch}}"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("finalUrl").GetString(), Is.EqualTo(AskedSearch));
            // Ronda 23: the changed title that names every word searched is the arrival, with no second address read.
            Assert.That(platform.AddressReads, Is.EqualTo(1));
            Assert.That(receipt.Result?.GetProperty("authority").GetString(),
                Is.EqualTo(UserBrowserSurface.SearchTitleAuthority));
        });
    }

    [Test]
    public async Task TheSearchAskedForIsWaitedForPastTheTabOfAnotherOneByItsAddress()
    {
        // The same wait when the new title does not name the words searched: the address read decides, as before.
        int reads = 0;
        var platform = new FakePlatform(OperaGx)
        {
            WindowsBeforeOpen = [new(11, "si hay película de El Aleph - Buscar con Google - Opera")],
            AddressBeforeOpen = _ => OldSearch,
            AddressOf = _ => ++reads == 1 ? OldSearch : AskedSearch.Replace("https://", string.Empty),
        };
        platform.WindowSteps.Add([new(11, "Buscar con Google - Opera")]);
        platform.WindowSteps.Add([new(11, "Google - Opera")]);
        using Harness harness = new(platform);

        ExternalCapabilityReceipt receipt = await harness.Adapter.InvokeAsync(
            "browser.navigate", Json($$"""{"url":"{{AskedSearch}}"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("finalUrl").GetString(), Is.EqualTo(AskedSearch));
            Assert.That(platform.AddressReads, Is.EqualTo(2));
            Assert.That(receipt.Result?.GetProperty("authority").GetString(),
                Is.EqualTo(UserBrowserSurface.AddressAuthority));
        });
    }

    [Test]
    public async Task TheSameSearchTwiceInARowArrives()
    {
        // Contracase: the destination itself is the arrival even when the front tab already showed it.
        var platform = new FakePlatform(OperaGx)
        {
            WindowsBeforeOpen = [new(11, "los horarios del cercanias de madrid - Buscar con Google - Opera")],
            AddressOf = _ => AskedSearch.Replace("https://", string.Empty) + "&sca_esv=1f2e&ei=abc",
        };
        platform.WindowsAfterOpen = [new(11, "Buscar con Google - Opera")];
        using Harness harness = new(platform);

        ExternalCapabilityReceipt receipt = await harness.Adapter.InvokeAsync(
            "browser.navigate", Json($$"""{"url":"{{AskedSearch}}"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("finalUrl").GetString(),
                Is.EqualTo(AskedSearch + "&sca_esv=1f2e&ei=abc"), "parameters the page adds are not compared");
            // Review r10a finding 6, contracase: the window changed (a new tab was seen opening), so it is no page
            // that was merely already on show.
            Assert.That(receipt.Result?.GetProperty("authority").GetString(),
                Is.Not.EqualTo(UserBrowserSurface.AlreadyShownAuthority));
        });
    }

    [Test]
    public async Task AConsentPageThatGivesWayToTheResultsArrivesAtTheResults()
    {
        int reads = 0;
        var platform = new FakePlatform(OperaGx)
        {
            AddressBeforeOpen = EmptyAddressField,
            AddressOf = _ => ++reads == 1
                ? "consent.google.com/ml?continue=https://www.google.com/search&hl=es"
                : AskedSearch.Replace("https://", string.Empty),
        };
        platform.WindowSteps.Add([new(11, "Antes de ir a Google - Opera")]);
        platform.WindowSteps.Add([new(11, "los horarios del cercanias de madrid - Buscar con Google - Opera")]);
        using Harness harness = new(platform);

        ExternalCapabilityReceipt receipt = await harness.Adapter.InvokeAsync(
            "browser.navigate", Json($$"""{"url":"{{AskedSearch}}"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("finalUrl").GetString(), Is.EqualTo(AskedSearch));
        });
    }

    [Test]
    public async Task ARedirectOfTheSiteInTheTabJustOpenedIsWhereTheLinkLanded()
    {
        var platform = new FakePlatform(OperaGx)
        {
            AddressBeforeOpen = EmptyAddressField,
            AddressOf = _ => "www.youtube.com/feed/you",
        };
        platform.WindowsAfterOpen = [new(11, "YouTube - Opera")];
        using Harness harness = new(platform);

        ExternalCapabilityReceipt receipt = await harness.Adapter.InvokeAsync(
            "browser.navigate", Json("""{"url":"https://youtube.com/"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("finalUrl").GetString(), Is.EqualTo("https://www.youtube.com/feed/you"));
        });
    }

    [Test]
    public async Task ARedirectAfterAnUnreadEarlierAddressIsNeverTakenForTheLanding()
    {
        // Auditoría final (regla 3): the front tab's address before the link was not read, so a page of the same site
        // there may be the one the person already had: the navigation stays unconfirmed.
        var platform = new FakePlatform(OperaGx)
        {
            AddressBeforeOpen = _ => null,
            AddressOf = _ => "www.youtube.com/feed/you",
        };
        platform.WindowsAfterOpen = [new(11, "YouTube - Opera")];
        using Harness harness = new(platform);

        ExternalCapabilityReceipt receipt = await harness.Adapter.InvokeAsync(
            "browser.navigate", Json("""{"url":"https://youtube.com/"}"""), CancellationToken.None);

        Assert.That(receipt.Verified, Is.False);
    }

    [Test]
    public async Task APageOfTheSiteThePersonAlreadyHadIsNoRedirect()
    {
        // Contracase: the same site, but the very address the front tab showed before the link was opened, or a
        // page in a window whose earlier address is unknown, is not what the link opened.
        var shown = new FakePlatform(OperaGx)
        {
            WindowsBeforeOpen = [new(11, "Video - YouTube - Opera")],
            AddressOf = _ => "www.youtube.com/watch?v=abc",
        };
        shown.WindowsAfterOpen = [new(11, "(1) Video - YouTube - Opera")];
        var elsewhere = new FakePlatform(OperaGx)
        {
            WindowsBeforeOpen = [new(11, "Inicio - Opera"), new(12, "Video - YouTube - Opera")],
            AddressBeforeOpen = EmptyAddressField,
            AddressOf = window => window == 12 ? "www.youtube.com/watch?v=abc" : null,
        };
        elsewhere.WindowsAfterOpen = [new(11, "Inicio - Opera"), new(12, "(1) Video - YouTube - Opera")];
        using Harness first = new(shown);
        using Harness second = new(elsewhere);

        ExternalCapabilityReceipt same = await first.Adapter.InvokeAsync(
            "browser.navigate", Json("""{"url":"https://youtube.com/"}"""), CancellationToken.None);
        ExternalCapabilityReceipt other = await second.Adapter.InvokeAsync(
            "browser.navigate", Json("""{"url":"https://youtube.com/"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(same.ErrorCode, Is.EqualTo(UserBrowserSurface.NavigationUnconfirmed));
            Assert.That(other.ErrorCode, Is.EqualTo(UserBrowserSurface.NavigationUnconfirmed));
        });
    }

    private const string EarlierArticle = "es.wikipedia.org/wiki/Revoluci%C3%B3n_francesa";
    private const string EarlierArticleTitle = "Revolución francesa - Wikipedia, la enciclopedia libre - Opera";
    private const string SiteHome = "es.wikipedia.org/wiki/Wikipedia:Portada";

    [Test]
    public async Task AnAddressFieldStillShowingThePageFromBeforeIsReadAgainUntilTheRedirectShows()
    {
        // Noche r7 (R7-NB-5): the front tab showed a page of the site before the link; the window title moved on to the
        // new tab, but the address field read right then still showed the page from before, and with no further title
        // change nothing read it again: the redirect of the site the link landed on was never seen.
        int reads = 0;
        var platform = new FakePlatform(OperaGx)
        {
            WindowsBeforeOpen = [new(11, EarlierArticleTitle)],
            AddressBeforeOpen = _ => EarlierArticle,
            AddressOf = _ => ++reads == 1 ? EarlierArticle : SiteHome,
        };
        platform.WindowsAfterOpen = [new(11, "Wikipedia, la enciclopedia libre - Opera")];
        using Harness harness = new(platform);

        ExternalCapabilityReceipt receipt = await harness.Adapter.InvokeAsync(
            "browser.navigate", Json("""{"url":"https://es.wikipedia.org/"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("finalUrl").GetString(), Is.EqualTo("https://" + SiteHome));
            Assert.That(receipt.Result?.GetProperty("authority").GetString(),
                Is.EqualTo(UserBrowserSurface.AddressAuthority));
            Assert.That(platform.AddressReads, Is.EqualTo(2), "the field from before is read once more, not more");
        });
    }

    [Test]
    public async Task AFrontAddressThatCouldNotBeReadBeforeTheLinkIsReadOnceMore()
    {
        // Noche r7 (R7-NB-5): one failed read of the front tab before the link left its page unknown, so the redirect
        // the link landed on could not be told from a page the person already had.
        int before = 0;
        var platform = new FakePlatform(OperaGx)
        {
            WindowsBeforeOpen = [new(11, EarlierArticleTitle)],
            AddressBeforeOpen = _ => ++before == 1 ? null : EarlierArticle,
            AddressOf = _ => SiteHome,
        };
        platform.WindowsAfterOpen = [new(11, "Wikipedia, la enciclopedia libre - Opera")];
        using Harness harness = new(platform);

        ExternalCapabilityReceipt receipt = await harness.Adapter.InvokeAsync(
            "browser.navigate", Json("""{"url":"https://es.wikipedia.org/"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("finalUrl").GetString(), Is.EqualTo("https://" + SiteHome));
            Assert.That(platform.BaselineReads, Is.EqualTo(2));
        });
    }

    [TestCase("page_from_before", true)]
    [TestCase("not_read", false)]
    [TestCase("no_address", true)]
    [TestCase("other_page", true)]
    [TestCase("same_site_not_known_new", true)]
    public async Task AnUnconfirmedNavigationSaysWhatWasCheckedAndNoAddressItRead(string seen, bool windowChanged)
    {
        // Decisión del dueño (noche, pre-web-comprobar): «abrí, pero no pude comprobarlo» is honest; the result says what
        // was checked (the link handed to the browser, whether a window of it changed, what its address field showed)
        // and never an address read from a tab, which may be another page of the person's.
        var platform = seen switch
        {
            "page_from_before" => new FakePlatform(OperaGx)
            {
                WindowsBeforeOpen = [new(11, EarlierArticleTitle)],
                AddressOf = _ => EarlierArticle,
            },
            "not_read" => new FakePlatform(OperaGx)
            {
                AddressBeforeOpen = _ => "www.example.org/private",
                AddressOf = _ => "www.example.org/private",
            },
            "no_address" => new FakePlatform(OperaGx)
            {
                AddressBeforeOpen = EmptyAddressField,
                AddressOf = _ => null,
            },
            "other_page" => new FakePlatform(OperaGx)
            {
                AddressBeforeOpen = EmptyAddressField,
                AddressOf = _ => "mail.example.org/inbox?private=1",
            },
            _ => new FakePlatform(OperaGx)
            {
                AddressBeforeOpen = _ => null,
                AddressOf = _ => SiteHome,
            },
        };
        if (windowChanged)
            platform.WindowsAfterOpen = [new(11, "Wikipedia, la enciclopedia libre - Opera")];
        using Harness harness = new(platform);

        ExternalCapabilityReceipt receipt = await harness.Adapter.InvokeAsync(
            "browser.navigate", Json("""{"url":"https://es.wikipedia.org/"}"""), CancellationToken.None);

        string raw = receipt.Result?.GetRawText() ?? string.Empty;
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            Assert.That(receipt.ErrorCode, Is.EqualTo(UserBrowserSurface.NavigationUnconfirmed));
            Assert.That(receipt.Result?.GetProperty("requestedUrl").GetString(), Is.EqualTo("https://es.wikipedia.org/"));
            Assert.That(receipt.Result?.GetProperty("browser").GetString(), Is.EqualTo("Opera GX"));
            Assert.That(receipt.Result?.GetProperty("linkSent").GetBoolean(), Is.True);
            Assert.That(receipt.Result?.GetProperty("windowChanged").GetBoolean(), Is.EqualTo(windowChanged));
            Assert.That(receipt.Result?.GetProperty("addressSeen").GetString(), Is.EqualTo(seen));
            Assert.That(raw, Does.Not.Contain("finalUrl"));
            Assert.That(raw, Does.Not.Contain("Revoluci").And.Not.Contain("Portada").And.Not.Contain("example"),
                "no address read from a tab is reported");
            Assert.That(platform.Fronted, Is.Empty, "no window is put in front on an unconfirmed navigation");
        });
    }

    [TestCase("https://www.google.com/search?q=los+horarios", "google.com/search?q=los%20horarios", true)]
    [TestCase("http://example.org/page", "https://example.org/page/", true)]
    [TestCase("https://example.org/page#top", "https://www.example.org/page", true)]
    [TestCase("https://www.google.com/search?q=El+fin+de+los+tiempos.", "www.google.com/search?q=El+fin+de+los+tiempos.", true)]
    [TestCase("https://www.google.com/search?q=El+fin+de+los+tiempos.", "www.google.com/search?q=El+fin+de+los+tiempos", false)]
    [TestCase("https://www.google.com/search?q=cercanias", "www.google.com/search?q=El+Aleph", false)]
    [TestCase("https://www.google.com/search?q=cercanias", "www.google.com/webhp?q=cercanias", false)]
    [TestCase("https://www.google.com/search?q=pel%C3%ADcula", "www.google.com/search?q=película", true)]
    [TestCase("https://es.wikipedia.org/wiki/Aleph", "es.wikipedia.org/wiki/aleph", false)]
    public void TheDestinationIsTheAddressAskedForWithTheSpellingsABrowserShows(
        string requested, string observed, bool reached)
    {
        Assert.That(UserBrowserSurface.TryAddress(observed, out Uri? seen), Is.True);
        Assert.That(UserBrowserSurface.ReachedTarget(new Uri(requested), seen!), Is.EqualTo(reached));
    }

    // Renew al máximo (w8): a named browser's navigation compared the path and not the query, so youtube.com/watch?v=A
    // that ended on ?v=B was told as arrived.
    [TestCase("https://youtube.com/watch?v=A", "https://www.youtube.com/watch?v=B", false)]
    [TestCase("https://youtube.com/watch?v=A", "https://www.youtube.com/watch", false)]
    [TestCase("https://youtube.com/watch?v=A", "https://www.youtube.com/watch?v=A&pp=x", true)]
    [TestCase("https://youtube.com/", "https://www.youtube.com/", true)]
    [TestCase("https://youtube.com/watch?v=A", "https://accounts.google.com/watch?v=A", false)]
    public void ANamedBrowserArrivesOnlyWithTheQueryAskedFor(string requested, string observed, bool reached) =>
        Assert.That(NamedBrowserAdapter.DestinationMatches(new Uri(requested), new Uri(observed)), Is.EqualTo(reached));

    [TestCase("https://www.google.com/search?q=cercanias", "www.google.com/search?q=El+Aleph", true)]
    [TestCase("https://www.google.com/search?q=cercanias", "www.google.com/search?q=cercanias&hl=es", false)]
    [TestCase("https://www.google.com/search?q=cercanias", "consent.google.com/ml?q=otra", false)]
    [TestCase("https://youtube.com/", "www.youtube.com/feed/you", false)]
    public void AnotherQueryOnThePathAskedForContradictsTheDestination(string requested, string observed, bool contradicts)
    {
        Assert.That(UserBrowserSurface.TryAddress(observed, out Uri? seen), Is.True);
        Assert.That(UserBrowserSurface.ContradictsTarget(new Uri(requested), seen!), Is.EqualTo(contradicts));
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
            Assert.That(context.UserBrowserHoldingThePage?.DisplayName, Is.EqualTo("Opera GX"));
            Assert.That(Directory.Exists(root), Is.False, "no private profile was created");
        });
    }

    [Test]
    public async Task AnAddressWithUserInfoIsNotOpenedInThePersonsNamedBrowser()
    {
        // https://bank@evil.example/ reads as «bank» and goes to evil.example: browser.navigate refuses it
        // (RequireWebUri) and so does the named browser, before anything opens.
        var platform = new FakePlatform(OperaGx) { AddressOf = _ => "evil.example/" };
        platform.WindowsAfterOpen = [new(11, "Evil - Opera")];
        var context = new CdpBrowserSessionContext();
        string root = Path.Combine(Path.GetTempPath(), "baxy-user-browser-" + Guid.NewGuid().ToString("N"));
        using var named = new NamedBrowserAdapter(
            root, context, opera: null,
            userBrowser: new UserBrowserSurface(platform, _ => null));

        ExternalCapabilityReceipt receipt = await named.InvokeAsync(
            "browser.navigate.named",
            Json("""{"browser":"opera_gx","url":"https://bank@evil.example/"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("named_browser_url_invalid"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(platform.Opened, Is.Empty);
            Assert.That(Directory.Exists(root), Is.False, "no private profile was created");
        });
    }

    [Test]
    public async Task NoWindowChangeLeavesTheNavigationUncertain()
    {
        // The front window showed another page before the link opened (semilla r8: the destination already on show
        // there is read again, TheDestinationAlreadyOnShowInTheFrontWindowIsAnArrival).
        var platform = new FakePlatform(OperaGx)
        {
            AddressBeforeOpen = _ => "www.example.org/",
            AddressOf = _ => "wikipedia.org",
        };
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

    // Feria 2026-10-27 (caso 19): a video asked for in a named browser opens with that browser's registered executable,
    // not with the default one, and only that browser's media session verifies it: the default browser showing the
    // same title proves nothing.
    [Test]
    public async Task AYouTubeVideoInANamedBrowserOpensThereAndOnlyItsOwnSessionVerifiesIt()
    {
        var platform = new FakePlatform(OperaGx) { Registered = { ["chrome"] = Chrome } };
        var inTheDefault = new UserMediaSession("Opera GXStable", "Never Gonna Give You Up", "Rick Astley", "playing");
        platform.SessionsAfterOpen =
        [
            [inTheDefault],
            [inTheDefault, new("Chrome", "Never Gonna Give You Up", "Rick Astley", "playing")],
        ];
        using Harness harness = new(platform, http: YouTubePage("dQw4w9WgXcQ", "Never Gonna Give You Up"));

        ExternalCapabilityReceipt receipt = await harness.Adapter.InvokeAsync(
            "media.play.youtube", Json("""{"query":"never gonna give you up","browser":"chrome"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(platform.Opened, Is.Empty, "the default browser is not the one named");
            Assert.That(platform.OpenedWith.Select(static opened => opened.Executable),
                Is.EqualTo(new[] { Chrome.Executable }));
            Assert.That(new Uri(platform.OpenedWith[0].Address).Query, Is.EqualTo("?v=dQw4w9WgXcQ"));
            Assert.That(receipt.Result?.GetProperty("browser").GetString(), Is.EqualTo("Google Chrome"));
            Assert.That(receipt.Result?.GetProperty("sourceAppUserModelId").GetString(), Is.EqualTo("Chrome"));
            Assert.That(harness.Edge.YouTubeCalls, Is.Zero);
        });
    }

    // E016 again: after a video played in a named browser (Chrome while the default is Opera GX), a tab step acts on
    // Chrome, where the page is, not on the person's default browser.
    [Test]
    public async Task ATabStepAfterAVideoInANamedBrowserActsOnThatBrowser()
    {
        var platform = new FakePlatform(OperaGx) { Registered = { ["chrome"] = Chrome } };
        platform.OtherWindows["chrome"] = [new(21, "YouTube - Google Chrome")];
        platform.SessionsAfterOpen = [[new("Chrome", "Never Gonna Give You Up", "Rick Astley", "playing")]];
        platform.Frames.AddRange([Frame("doc-1"), Frame("doc-1"), Frame("doc-9")]);
        var context = new CdpBrowserSessionContext();
        using Harness harness = new(
            platform, http: YouTubePage("dQw4w9WgXcQ", "Never Gonna Give You Up"), context: context);

        ExternalCapabilityReceipt played = await harness.Adapter.InvokeAsync(
            "media.play.youtube", Json("""{"query":"never gonna give you up","browser":"chrome"}"""),
            CancellationToken.None);
        ExternalCapabilityReceipt reloaded = await Control(harness, "reload");

        Assert.Multiple(() =>
        {
            Assert.That(played.Verified, Is.True);
            Assert.That(reloaded.Verified, Is.True);
            Assert.That(platform.MessageWindows, Is.EqualTo(new[] { 21 }), "the default browser's window is not touched");
        });
    }

    // A browser named that Windows has not registered is not replaced by another one: nothing opens.
    [Test]
    public async Task AYouTubeVideoInANamedBrowserWindowsDoesNotKnowOpensNothing()
    {
        var platform = new FakePlatform(OperaGx);
        using Harness harness = new(platform, http: YouTubePage("dQw4w9WgXcQ", "Never Gonna Give You Up"));

        ExternalCapabilityReceipt receipt = await harness.Adapter.InvokeAsync(
            "media.play.youtube", Json("""{"query":"never gonna give you up","browser":"brave"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo(WebBrowserAdapter.NamedBrowserNotRegistered));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(platform.Opened, Is.Empty);
            Assert.That(platform.OpenedWith, Is.Empty);
            Assert.That(harness.Edge.YouTubeCalls, Is.Zero);
        });
    }

    // Opera and Opera GX are two browsers: a session of one is never the other's.
    [Test]
    public void OperaAndOperaGxOwnOnlyTheirOwnMediaSessions()
    {
        var opera = new UserBrowserIdentity(
            "OperaStable", "opera", "Opera", @"C:\Users\owner\AppData\Local\Programs\Opera\launcher.exe");

        Assert.Multiple(() =>
        {
            Assert.That(OperaGx.OwnsMediaSession("OperaSoftware.OperaGXWebBrowser.1732473326"), Is.True);
            Assert.That(OperaGx.OwnsMediaSession("Opera GXStable"), Is.True);
            Assert.That(OperaGx.OwnsMediaSession("OperaSoftware.OperaWebBrowser.1732473326"), Is.False);
            Assert.That(opera.OwnsMediaSession("OperaSoftware.OperaWebBrowser.1732473326"), Is.True);
            Assert.That(opera.OwnsMediaSession("OperaSoftware.OperaGXWebBrowser.1732473326"), Is.False);
            Assert.That(opera.ProcessName, Is.EqualTo("opera"), "the launcher draws no window");
        });
    }

    // Review R6: a video asked for in Opera GX is not verified by the plain Opera's new session of the same title.
    [Test]
    public async Task AYouTubeVideoInNamedOperaGxIsNotVerifiedByThePlainOperasSession()
    {
        var platform = new FakePlatform(Chrome) { Registered = { ["opera_gx"] = OperaGxLauncher } };
        platform.SessionsAfterOpen =
        [
            [],
            [new("OperaSoftware.OperaWebBrowser.1735227809", "Never Gonna Give You Up", "Rick Astley", "playing")],
        ];
        using Harness harness = new(platform, http: YouTubePage("dQw4w9WgXcQ", "Never Gonna Give You Up"));

        ExternalCapabilityReceipt receipt = await harness.Adapter.InvokeAsync(
            "media.play.youtube", Json("""{"query":"never gonna give you up","browser":"opera_gx"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo(UserBrowserSurface.PlaybackUnconfirmed));
            Assert.That(receipt.Result?.GetProperty("browser").GetString(), Is.EqualTo("Opera GX"));
            Assert.That(platform.OpenedWith.Select(static opened => opened.Executable),
                Is.EqualTo(new[] { OperaGxLauncher.Executable }));
        });
    }

    // Review R6: Opera registered by its launcher.exe and already running is not taken for a browser this request
    // launched, so a new session of it with another title (another tab) does not verify the video asked for.
    [Test]
    public async Task AYouTubeVideoInARunningOperaRegisteredByItsLauncherNeedsItsTitle()
    {
        var platform = new FakePlatform(Chrome) { Registered = { ["opera_gx"] = OperaGxLauncher } };
        platform.OtherWindows["opera"] = [new(31, "Inicio - Opera GX")];
        platform.SessionsAfterOpen =
        [
            [],
            [new("OperaSoftware.OperaGXWebBrowser.1735227809", "Lo-fi para estudiar", string.Empty, "playing")],
        ];
        using Harness harness = new(platform, http: YouTubePage("dQw4w9WgXcQ", "Never Gonna Give You Up"));

        ExternalCapabilityReceipt receipt = await harness.Adapter.InvokeAsync(
            "media.play.youtube", Json("""{"query":"never gonna give you up","browser":"opera_gx"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo(UserBrowserSurface.PlaybackUnconfirmed));
        });
    }

    private static readonly UserBrowserIdentity OperaGxLauncher = new(
        "Opera GXStable", "opera_gx", "Opera GX", @"C:\Users\owner\AppData\Local\Programs\Opera GX\launcher.exe");

    // A named browser that could not be launched is not replaced by the product's own browser either.
    [Test]
    public async Task AYouTubeVideoInANamedBrowserThatDoesNotStartFallsToNoOtherBrowser()
    {
        var platform = new FakePlatform(OperaGx) { OpenFails = true, Registered = { ["chrome"] = Chrome } };
        using Harness harness = new(platform, http: YouTubePage("dQw4w9WgXcQ", "Never Gonna Give You Up"));

        ExternalCapabilityReceipt receipt = await harness.Adapter.InvokeAsync(
            "media.play.youtube", Json("""{"query":"never gonna give you up","browser":"chrome"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo(WebBrowserAdapter.NamedBrowserNotLaunched));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(platform.Opened, Is.Empty);
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
            // Caso 19: the page was opened; the failure says in which browser.
            Assert.That(receipt.Result?.GetProperty("browser").GetString(), Is.EqualTo("Opera GX"));
            Assert.That(receipt.Result?.GetProperty("openedUrl").GetString(),
                Does.EndWith("/watch?v=dQw4w9WgXcQ"));
            Assert.That(platform.Played, Is.Empty);
            Assert.That(harness.Edge.YouTubeCalls, Is.Zero, "the video is not started a second time elsewhere");
        });
    }

    // Tanda t4-r6: a YouTube page that never played held the turn for the whole 15 s.
    [Test]
    public async Task ARunningBrowserWithoutAnyMediaTraceEndsTheWaitAfterEightSeconds()
    {
        var platform = new FakePlatform(OperaGx);
        using Harness harness = new(platform, http: YouTubePage("dQw4w9WgXcQ", "Never Gonna Give You Up"));

        ExternalCapabilityReceipt receipt = await harness.Adapter.InvokeAsync(
            "media.play.youtube", Json("""{"query":"never gonna give you up"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            Assert.That(receipt.ErrorCode, Is.EqualTo(UserBrowserSurface.PlaybackUnconfirmed));
            Assert.That(platform.SessionReads, Is.EqualTo(1 + UserBrowserSurface.SilentPlaybackPolls));
        });
    }

    [Test]
    public async Task ABrowserThatWasNotRunningKeepsTheWholePlaybackHorizon()
    {
        var platform = new FakePlatform(OperaGx)
        {
            WindowsBeforeOpen = [],
            WindowsAfterOpen = [new(11, "YouTube - Opera")],
        };
        using Harness harness = new(platform, http: YouTubePage("dQw4w9WgXcQ", "Never Gonna Give You Up"));

        ExternalCapabilityReceipt receipt = await harness.Adapter.InvokeAsync(
            "media.play.youtube", Json("""{"query":"never gonna give you up"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(platform.SessionReads, Is.EqualTo(1 + UserBrowserSurface.SlowStartPlaybackPolls),
                "a cold launch is not a negative signal");
        });
    }

    // Tandas on redpc 2026-10-12, Opera GX closed before the first YouTube play of the tanda. fin3 t1 «ponme algo de
    // los prisioneros» was verified at the edge of the 60-poll horizon (core call 17,6 s); fin4 t1 (same request,
    // 16,9 s) and fin1 t2 «no mejor en youtube, algun video largo…» (Spotify playing before, 15,8 s) ran it out and
    // said «no pude confirmar que esté sonando»; fin4's next turn, browser up, played in 4,1 s. The session the page
    // starts after the launch is waited for past the running browser's horizon.
    [TestCase("fin3 t1", 58, "", "los prisioneros", "Los Prisioneros - Estrechez De Corazón (Audio)")]
    [TestCase("fin4 t1", 61, "", "los prisioneros", "Los Prisioneros - Estrechez De Corazón (Audio)")]
    [TestCase("fin1 t2", 61, "Los Bunkers - Llueve Sobre La Ciudad", "video largo de Los Bunkers",
        "Los Bunkers - video largo")]
    [TestCase("slow launch", 110, "", "los prisioneros", "Los Prisioneros - Estrechez De Corazón (Audio)")]
    public async Task ABrowserThisRequestLaunchedIsWaitedForPastTheRunningBrowsersHorizon(
        string run, int pollsBeforePlaying, string spotifyBefore, string query, string sessionTitle)
    {
        const string Opera = "OperaSoftware.OperaGXWebBrowser.1735227809";
        var platform = new FakePlatform(OperaGx)
        {
            WindowsBeforeOpen = [],
            WindowsAfterOpen = [new(11, "YouTube - Opera")],
        };
        IReadOnlyList<UserMediaSession> others = spotifyBefore.Length == 0
            ? []
            : [new UserMediaSession("Spotify.exe", spotifyBefore, "Los Bunkers", "playing")];
        platform.SessionsBeforeOpen = others;
        platform.SessionsAfterOpen =
        [
            .. Enumerable.Repeat(others, pollsBeforePlaying - 1),
            [.. others, new UserMediaSession(Opera, sessionTitle, string.Empty, "playing")],
        ];
        using Harness harness = new(platform, http: YouTubePage("nNbowGjKQHc", sessionTitle));

        ExternalCapabilityReceipt receipt = await harness.Adapter.InvokeAsync(
            "media.play.youtube", Json($$"""{"query":"{{query}}"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, run);
            Assert.That(platform.SessionReads, Is.EqualTo(1 + pollsBeforePlaying), run);
            Assert.That(receipt.Result?.GetProperty("title").GetString(), Is.EqualTo(sessionTitle), run);
            Assert.That(receipt.Result?.GetProperty("sourceAppUserModelId").GetString(), Is.EqualTo(Opera), run);
        });
    }

    [Test]
    public async Task ARunningBrowserKeepsItsOwnHorizonWhenThePageNeverPlays()
    {
        var platform = new FakePlatform(OperaGx);
        var loading = new UserMediaSession("Opera GXStable", "YouTube", "", "opened");
        platform.SessionsAfterOpen = [[loading]];
        using Harness harness = new(platform, http: YouTubePage("dQw4w9WgXcQ", "Never Gonna Give You Up"));

        ExternalCapabilityReceipt receipt = await harness.Adapter.InvokeAsync(
            "media.play.youtube", Json("""{"query":"never gonna give you up"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo(UserBrowserSurface.PlaybackUnconfirmed));
            Assert.That(platform.SessionReads, Is.EqualTo(1 + 60), "only a launch pays the longer wait");
        });
    }

    [Test]
    public async Task AnyMediaTraceOfTheBrowserKeepsWaitingUntilThePagePlays()
    {
        var platform = new FakePlatform(OperaGx);
        var loading = new UserMediaSession("Opera GXStable", "YouTube", "", "paused");
        var playing = new UserMediaSession("Opera GXStable", "Never Gonna Give You Up", "Rick Astley", "playing");
        platform.SessionsAfterOpen = [.. Enumerable.Repeat<IReadOnlyList<UserMediaSession>>([loading], 40), [playing]];
        using Harness harness = new(platform, http: YouTubePage("dQw4w9WgXcQ", "Never Gonna Give You Up"));

        ExternalCapabilityReceipt receipt = await harness.Adapter.InvokeAsync(
            "media.play.youtube", Json("""{"query":"never gonna give you up"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(platform.SessionReads, Is.EqualTo(1 + 41));
        });
    }

    // Ronda 19, t1-c01 #1 «ponme algo de los prisioneros» with Opera closed: the page started a session whose title
    // was not the video's, the title-only check never took it and the whole 60-poll horizon ran out (27,6 s).
    [Test]
    public async Task ABrowserThisRequestLaunchedIsVerifiedByItsNewSessionWhateverItsTitle()
    {
        var platform = new FakePlatform(OperaGx)
        {
            WindowsBeforeOpen = [],
            WindowsAfterOpen = [new(11, "YouTube - Opera")],
        };
        var spotify = new UserMediaSession("Spotify.exe", "Some song", "Someone", "playing");
        platform.SessionsBeforeOpen = [spotify];
        platform.SessionsAfterOpen =
        [
            [spotify],
            [spotify, new("Opera GXStable", "Los Prisioneros - Tren al sur (video oficial)", "", "playing")],
        ];
        using Harness harness = new(platform, http: YouTubePage("aB3dEf9hIjk", "Algo de Los Prisioneros en vivo 1986"));

        ExternalCapabilityReceipt receipt = await harness.Adapter.InvokeAsync(
            "media.play.youtube", Json("""{"query":"algo de los prisioneros"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(platform.SessionReads, Is.EqualTo(1 + 2), "the wait ends on the first playing session");
            Assert.That(receipt.Result?.GetProperty("sourceAppUserModelId").GetString(), Is.EqualTo("Opera GXStable"));
            Assert.That(receipt.Result?.GetProperty("title").GetString(),
                Is.EqualTo("Los Prisioneros - Tren al sur (video oficial)"));
        });
    }

    [Test]
    public async Task ABrowserThisRequestLaunchedGetsItsNewHeldBackSessionPressedOnce()
    {
        var platform = new FakePlatform(OperaGx)
        {
            WindowsBeforeOpen = [],
            WindowsAfterOpen = [new(11, "YouTube - Opera")],
        };
        var held = new UserMediaSession("Opera GXStable", "YouTube", "", "paused");
        platform.SessionsAfterOpen = [[held]];
        platform.OnPlay = session => platform.SessionsAfterOpen = [[session with { PlaybackStatus = "playing" }]];
        using Harness harness = new(platform, http: YouTubePage("aB3dEf9hIjk", "Algo de Los Prisioneros en vivo 1986"));

        ExternalCapabilityReceipt receipt = await harness.Adapter.InvokeAsync(
            "media.play.youtube", Json("""{"query":"algo de los prisioneros"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(platform.Played, Has.Count.EqualTo(1));
            Assert.That(platform.Played[0].Title, Is.EqualTo("YouTube"));
        });
    }

    [Test]
    public void ASessionThePersonAlreadyHadWithTheTitleIsNeverThePagesOrPressed()
    {
        var theirs = new UserMediaSession("Opera GXStable", "Never Gonna Give You Up", "Rick Astley", "playing");
        var paused = theirs with { PlaybackStatus = "paused" };
        Assert.Multiple(() =>
        {
            Assert.That(UserBrowserSurface.PlaybackCandidate(
                OperaGx, "Never Gonna Give You Up", [theirs], [theirs], anyNewBrowserSession: false), Is.Null);
            Assert.That(UserBrowserSurface.MayPressPlay(OperaGx, "Never Gonna Give You Up", [paused], paused, false),
                Is.False);
        });
    }

    [Test]
    public void ARunningBrowsersNewSessionWithAnotherTitleIsStillNotTheVideo()
    {
        var other = new UserMediaSession("Opera GXStable", "Another video", "", "playing");
        var theirs = new UserMediaSession("Opera GXStable", "Their podcast", "Someone", "paused");
        Assert.Multiple(() =>
        {
            Assert.That(UserBrowserSurface.PlaybackCandidate(
                OperaGx, "Never Gonna Give You Up", [], [other], anyNewBrowserSession: false), Is.Null);
            Assert.That(UserBrowserSurface.PlaybackCandidate(
                OperaGx, "Never Gonna Give You Up", [], [other], anyNewBrowserSession: false, coldLaunch: true),
                Is.EqualTo(other));
            // Cold or not, a session that was already there, title and state alike, is never the page's.
            Assert.That(UserBrowserSurface.PlaybackCandidate(
                OperaGx, "Never Gonna Give You Up", [theirs], [theirs], anyNewBrowserSession: false, coldLaunch: true),
                Is.Null);
            Assert.That(UserBrowserSurface.MayPressPlay(OperaGx, "Never Gonna Give You Up", [theirs], theirs, true),
                Is.False);
            Assert.That(UserBrowserSurface.MayPressPlay(OperaGx, "Never Gonna Give You Up", [], theirs, false),
                Is.False);
            Assert.That(UserBrowserSurface.MayPressPlay(OperaGx, "Never Gonna Give You Up", [], theirs, true),
                Is.True);
        });
    }

    [Test]
    public void OnlyTheBrowsersOwnSessionsDecideWhetherAnythingChanged()
    {
        var theirs = new UserMediaSession("Opera GXStable", "Their podcast", "Someone", "paused");
        var spotify = new UserMediaSession("Spotify.exe", "Some song", "Someone", "playing");
        Assert.Multiple(() =>
        {
            Assert.That(UserBrowserSurface.BrowserSessionsUnchanged(OperaGx, [theirs], [spotify, theirs]), Is.True);
            Assert.That(UserBrowserSurface.BrowserSessionsUnchanged(OperaGx, [theirs], [theirs with { PlaybackStatus = "playing" }]), Is.False);
            Assert.That(UserBrowserSurface.BrowserSessionsUnchanged(OperaGx, [theirs], []), Is.False);
            Assert.That(UserBrowserSurface.BrowserSessionsUnchanged(OperaGx, [], [theirs]), Is.False);
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

    // Ronda B: after IDC_NEW_TAB with no read showing one tab more, a strip that cannot be read is uncertain and a late tab
    // is said. Ronda final 42 (regla: doble pulsación): a strip read with as many tabs as before does not prove the message
    // was not run (a busy browser answers the reads first), so the button is never pressed after it: unconfirmed.
    [Test]
    public async Task ANewTabMessageNotSeenIsUnconfirmedAndTheButtonIsNotPressed()
    {
        var unreadable = new FakePlatform(Chrome);
        unreadable.Frames.AddRange([Frame("doc-1", tabs: 2), null]);
        var notRun = new FakePlatform(Chrome);
        notRun.Frames.AddRange([.. Enumerable.Repeat(Frame("doc-1", tabs: 2), 6), Frame("doc-2", tabs: 3)]);
        var late = new FakePlatform(Chrome);
        late.Frames.AddRange([.. Enumerable.Repeat(Frame("doc-1", tabs: 2), 5), Frame("doc-2", tabs: 3)]);
        using Harness first = new(unreadable);
        using Harness second = new(notRun);
        using Harness third = new(late);

        ExternalCapabilityReceipt uncertain = await Control(first, "new_tab");
        ExternalCapabilityReceipt notSeen = await Control(second, "new_tab");
        ExternalCapabilityReceipt lateTab = await Control(third, "new_tab");

        Assert.Multiple(() =>
        {
            Assert.That(uncertain.Verified, Is.False);
            Assert.That(uncertain.EffectMayHaveOccurred, Is.True);
            Assert.That(uncertain.ErrorCode, Is.EqualTo(UserBrowserSurface.TabStepUnconfirmed));
            Assert.That(unreadable.Acts, Is.Empty, "a strip that cannot be read is never pressed for a second tab");
            Assert.That(notSeen.Verified, Is.False);
            Assert.That(notSeen.EffectMayHaveOccurred, Is.True);
            Assert.That(notSeen.ErrorCode, Is.EqualTo(UserBrowserSurface.TabStepUnconfirmed));
            Assert.That(notRun.BrowserCommands, Is.EqualTo(new[] { UserBrowserSurface.BrowserCommandNewTab }));
            Assert.That(notRun.Acts, Is.Empty, "a posted message not seen run is never followed by the button");
            Assert.That(lateTab.Verified, Is.True);
            Assert.That(lateTab.Result?.GetProperty("tabCount").GetInt32(), Is.EqualTo(3));
            Assert.That(late.Acts, Is.Empty);
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

    // Ronda B: a failure of UI Automation or of the script (its deadline) may come after Scroll() or Invoke() was sent:
    // it is uncertain, never «before the effect»; a page not found is before any act.
    [TestCase("scroll_down", "uia_failed: ElementNotAvailableException", true)]
    [TestCase("scroll_down", "script_failed", true)]
    [TestCase("scroll_down", "page_not_found", false)]
    [TestCase("fullscreen_video", "uia_failed: ElementNotAvailableException", true)]
    [TestCase("fullscreen_video", "script_failed", true)]
    [TestCase("fullscreen_video", "page_not_found", false)]
    public async Task AFailureAfterTheActIsUncertain(string action, string step, bool mayHaveOccurred)
    {
        var platform = new FakePlatform(OperaGx) { ActResult = _ => new UserBrowserAct(step, -1, -1) };
        using Harness harness = new(platform);

        ExternalCapabilityReceipt receipt = await Control(harness, action);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.EqualTo(mayHaveOccurred));
            Assert.That(receipt.ErrorCode, Is.EqualTo(mayHaveOccurred
                ? UserBrowserSurface.TabStepUnconfirmed
                : UserBrowserSurface.PageUnreadable));
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

    // Uso real 2026-10-21: «sal de pantalla completa» had no action; the model chose close, which fails in full screen.
    [Test]
    public async Task LeavingFullScreenIsTheWindowNoLongerCoveringItsMonitor()
    {
        var leaves = new FakePlatform(OperaGx);
        leaves.Covers.AddRange([true, true, false]);
        var windowed = new FakePlatform(OperaGx) { ActResult = _ => throw new AssertionException("nothing to press") };
        var missing = new FakePlatform(OperaGx) { ActResult = _ => new UserBrowserAct("fullscreen_control_not_found", -1, -1) };
        missing.Covers.Add(true);
        using Harness first = new(leaves);
        using Harness second = new(windowed);
        using Harness third = new(missing);

        ExternalCapabilityReceipt left = await Control(first, "exit_fullscreen");
        ExternalCapabilityReceipt already = await Control(second, "exit_fullscreen");
        ExternalCapabilityReceipt none = await Control(third, "exit_fullscreen");

        Assert.Multiple(() =>
        {
            Assert.That(left.Verified, Is.True);
            Assert.That(left.Result?.GetProperty("observedState").GetString(), Is.EqualTo("windowed"));
            Assert.That(already.Verified, Is.True);
            Assert.That(already.Result?.GetProperty("observedState").GetString(), Is.EqualTo("windowed"));
            Assert.That(none.ErrorCode, Is.EqualTo(UserBrowserSurface.FullscreenControlMissing));
            Assert.That(none.EffectMayHaveOccurred, Is.False);
        });
    }

    // Uso real 2026-10-21: «Red Ready» played «Rare Earth - Get Ready», YouTube's first result.
    [Test]
    public void TheVideoChosenIsTheFirstWhoseTitleHoldsEveryWordSearched()
    {
        string html = "var ytInitialData = {"
            + "\"videoRenderer\":{\"videoId\":\"rareearth01\",\"title\":{\"runs\":[{\"text\":\"Rare Earth - Get Ready - complete track\"}]}},"
            + "\"videoRenderer\":{\"videoId\":\"redready001\",\"title\":{\"runs\":[{\"text\":\"RED READY - Live\"}]}}};";

        YouTubeSearchResult asked = YouTubeSearch.Parse(html, "Red Ready");
        YouTubeSearchResult none = YouTubeSearch.Parse(html, "canción relajante");
        YouTubeSearchResult unasked = YouTubeSearch.Parse(html);

        Assert.Multiple(() =>
        {
            Assert.That(asked.VideoId, Is.EqualTo("redready001"));
            Assert.That(asked.TitleMatchesQuery, Is.True);
            Assert.That(none.VideoId, Is.EqualTo("rareearth01"), "with none matching, YouTube's first");
            Assert.That(none.TitleMatchesQuery, Is.False);
            Assert.That(unasked.VideoId, Is.EqualTo("rareearth01"));
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

    // FT/proveedores goal (E3): Opera GX's always-on-top pop-out of a YouTube video is a window of the browser listed
    // before the frame; it has no tab strip (its frame reads null), so the page, the tabs and the step are the frame's.
    [Test]
    public async Task AWindowWithNoTabStripOnTopIsPassedOverForTheBrowserFrame()
    {
        IReadOnlyList<UserBrowserWindow> windows =
            [new(12, "Rick Astley - Never Gonna Give You Up", Topmost: true), new(11, "Rick Astley - Never Gonna Give You Up - YouTube - Opera")];
        var reads = new FakePlatform(OperaGx)
        {
            WindowsBeforeOpen = windows,
            AddressOf = window => window == 11 ? "https://www.youtube.com/watch?v=dQw4w9WgXcQ" : null,
            FrameOf = window => window == 11 ? Frame("doc-1") : null,
            PageTextOf = window => window == 11
                ? new UserBrowserPageText("Rick Astley - Never Gonna Give You Up - YouTube", "Rick Astley…", false)
                : null,
        };
        var history = new List<UserBrowserFrame> { Frame("doc-1"), Frame("doc-1"), Frame("doc-1"), Frame("doc-2") };
        var steps = new FakePlatform(OperaGx)
        {
            WindowsBeforeOpen = windows,
            FrameOf = window =>
            {
                if (window != 11)
                    return null;
                UserBrowserFrame current = history[0];
                if (history.Count > 1)
                    history.RemoveAt(0);
                return current;
            },
        };
        using Harness first = new(reads);
        using Harness second = new(steps);

        ExternalCapabilityReceipt page = await first.Adapter.InvokeAsync(
            "browser.page.read", Json("""{"maximumCharacters":2000}"""), CancellationToken.None);
        ExternalCapabilityReceipt tabs = await first.Adapter.InvokeAsync(
            "browser.tabs.list", Json("""{"limit":20}"""), CancellationToken.None);
        ExternalCapabilityReceipt back = await Control(second, "back");

        Assert.Multiple(() =>
        {
            Assert.That(page.Verified, Is.True);
            Assert.That(page.Result?.GetProperty("title").GetString(),
                Is.EqualTo("Rick Astley - Never Gonna Give You Up - YouTube"));
            Assert.That(page.Result?.GetProperty("url").GetString(), Is.EqualTo("https://www.youtube.com/watch?v=dQw4w9WgXcQ"));
            Assert.That(reads.PageReads, Is.EqualTo(new[] { (11, 2000) }), "the pop-out's page is never read");
            Assert.That(tabs.Verified, Is.True);
            Assert.That(tabs.Result?.GetProperty("count").GetInt32(), Is.EqualTo(3));
            Assert.That(back.Verified, Is.True);
            Assert.That(back.Result?.GetProperty("observedState").GetString(), Is.EqualTo("went_back"));
            Assert.That(steps.MessageWindows, Is.EqualTo(new[] { 11 }), "the command goes to the frame, not the pop-out");
        });
    }

    // Review of E3: a window in front with no tabs that is not on top (a video full screen hides the strip) is the one
    // the person sees: a step never moves on to a window behind it, it acts on the front one or fails.
    [Test]
    public async Task AFrontWindowWithoutTabsThatIsNotOnTopIsNeverPassedOver()
    {
        IReadOnlyList<UserBrowserWindow> windows =
            [new(11, "Video - YouTube - Opera"), new(13, "Otra página - Opera")];
        var steps = new FakePlatform(OperaGx)
        {
            WindowsBeforeOpen = windows,
            FrameOf = window => window == 11 ? Frame("doc-1") with { Tabs = [] } : Frame("doc-9"),
        };
        using Harness harness = new(steps);

        ExternalCapabilityReceipt close = await Control(harness, "close");

        Assert.Multiple(() =>
        {
            Assert.That(close.Verified, Is.False);
            Assert.That(steps.MessageWindows, Has.No.Member(13), "a hidden window is never acted on");
        });
    }

    // FT/proveedores goal (E3): with no window of the browser showing tabs, the front one is read as before (a page read
    // needs no tab strip); a front window not on top is never passed over (review of E3), so no other window is tried.
    [Test]
    public async Task WithNoWindowShowingTabsThePageOfTheFrontOneIsRead()
    {
        var platform = new FakePlatform(OperaGx)
        {
            WindowsBeforeOpen = [new(14, "Uno - Opera"), new(13, "Dos - Opera"), new(12, "Tres - Opera"), new(11, "Cuatro - Opera")],
            FrameOf = _ => null,
            PageTextOf = window => new UserBrowserPageText("Uno", "texto " + window, false),
        };
        using Harness harness = new(platform);

        ExternalCapabilityReceipt page = await harness.Adapter.InvokeAsync(
            "browser.page.read", Json("""{"maximumCharacters":2000}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(page.Verified, Is.True);
            Assert.That(platform.PageReads, Is.EqualTo(new[] { (14, 2000) }));
            Assert.That(platform.FrameWindows.Distinct(), Is.EqualTo(new[] { 14 }));
        });
    }

    // FT/proveedores goal (E3): a heavy page whose accessibility tree is built after the script's looks is read once more.
    [Test]
    public async Task APageNotReadAtFirstIsReadOnceMore()
    {
        var platform = new FakePlatform(OperaGx)
        {
            PageText = new UserBrowserPageText("Pesada - Opera", "Mucho texto", false),
        };
        platform.PageTextSteps.Add(null);
        using Harness harness = new(platform);

        ExternalCapabilityReceipt page = await harness.Adapter.InvokeAsync(
            "browser.page.read", Json("""{"maximumCharacters":2000}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(page.Verified, Is.True);
            Assert.That(page.Result?.GetProperty("text").GetString(), Is.EqualTo("Mucho texto"));
            Assert.That(platform.PageReads, Has.Count.EqualTo(2));
        });
    }

    private static UserBrowserFrame StripOnly(UserBrowserFrame frame, bool pageMatched = true) =>
        frame with { Complete = false, PageMatched = pageMatched };

    // FT/proveedores goal (E3): after a Speed Dial, Opera GX keeps a dead first child under LiveBackgroundView until it
    // restarts: the frame is never read whole, while its tab strip is. Tabs are counted on the strip read whole, and a
    // back or reload is seen by the page document named as the window title begins; the receipt says the frame was not
    // read whole.
    [Test]
    public async Task AStripReadWholeIsActedOnThoughTheRestOfTheFrameWasNot()
    {
        var back = new FakePlatform(OperaGx);
        back.Frames.AddRange([StripOnly(Frame("doc-1")), StripOnly(Frame("doc-1")), StripOnly(Frame("doc-2"))]);
        var close = new FakePlatform(OperaGx);
        close.Frames.AddRange([StripOnly(Frame("doc-1", tabs: 3)), StripOnly(Frame("doc-1", tabs: 3)),
            StripOnly(Frame("doc-7", tabs: 2))]);
        using Harness first = new(back);
        using Harness second = new(close);

        ExternalCapabilityReceipt wentBack = await Control(first, "back");
        ExternalCapabilityReceipt closed = await Control(second, "close");

        Assert.Multiple(() =>
        {
            Assert.That(wentBack.Verified, Is.True);
            Assert.That(wentBack.Result?.GetProperty("observedState").GetString(), Is.EqualTo("went_back"));
            Assert.That(wentBack.Result?.GetProperty("tabCount").GetInt32(), Is.EqualTo(3));
            Assert.That(wentBack.Result?.GetProperty("frameComplete").GetBoolean(), Is.False);
            Assert.That(closed.Verified, Is.True);
            Assert.That(closed.Result?.GetProperty("observedState").GetString(), Is.EqualTo("tab_closed"));
            Assert.That(closed.Result?.GetProperty("tabCount").GetInt32(), Is.EqualTo(2));
            Assert.That(close.MiddleClicks, Has.Count.EqualTo(1));
        });
    }

    // FT/proveedores goal (E3): in a frame not read whole, a page document not named as the window title begins may be
    // one a partial read put in place of the page (a side panel), and its address may be stale: neither is taken for the
    // change. A strip not read whole still counts no tab.
    [Test]
    public async Task APartialFrameIsNeverTakenForAChangeItCouldNotSee()
    {
        var unmatched = new FakePlatform(OperaGx);
        unmatched.Frames.Add(StripOnly(Frame("doc-1"), pageMatched: false));
        var addressOnly = new FakePlatform(OperaGx);
        addressOnly.Frames.AddRange([StripOnly(Frame("doc-1")), StripOnly(Frame("doc-1")),
            StripOnly(Frame("doc-1", address: "https://example.org/"))]);
        var stripPartial = new FakePlatform(OperaGx);
        stripPartial.Frames.Add(Frame("doc-1", tabs: 3) with { TabsComplete = false });
        using Harness first = new(unmatched);
        using Harness second = new(addressOnly);
        using Harness third = new(stripPartial);

        ExternalCapabilityReceipt notKnown = await Control(first, "back");
        ExternalCapabilityReceipt notSeen = await Control(second, "back");
        ExternalCapabilityReceipt notCounted = await Control(third, "close");

        Assert.Multiple(() =>
        {
            Assert.That(notKnown.ErrorCode, Is.EqualTo(UserBrowserSurface.PageUnreadable));
            Assert.That(unmatched.AppCommands, Is.Empty);
            Assert.That(notSeen.ErrorCode, Is.EqualTo(UserBrowserSurface.TabStepUnconfirmed));
            Assert.That(notSeen.EffectMayHaveOccurred, Is.True);
            Assert.That(notCounted.ErrorCode, Is.EqualTo(UserBrowserSurface.PageUnreadable));
            Assert.That(stripPartial.MiddleClicks, Is.Empty);
        });
    }

    [Test]
    public void TheFrameReadSaysApartTheStripTheWholeFrameAndTheMatchedPage()
    {
        using JsonDocument stripOnly = JsonDocument.Parse(
            """{"version":1,"ok":true,"tabs":[{"title":"A","selected":true}],"tabsComplete":true,"complete":false,"page":{"id":"1.2","title":"A","scroll":-1,"matched":true}}""");
        using JsonDocument whole = JsonDocument.Parse(
            """{"version":1,"ok":true,"tabs":[{"title":"A","selected":true}],"tabsComplete":true,"complete":true,"page":{"id":"1.2","title":"Panel","scroll":-1,"matched":false}}""");

        UserBrowserFrame? partial = WindowsUserBrowserPlatform.ParseFrame(stripOnly.RootElement);
        UserBrowserFrame? complete = WindowsUserBrowserPlatform.ParseFrame(whole.RootElement);

        Assert.Multiple(() =>
        {
            Assert.That(partial?.TabsComplete, Is.True);
            Assert.That(partial?.Complete, Is.False);
            Assert.That(partial?.PageMatched, Is.True);
            Assert.That(complete?.Complete, Is.True);
            Assert.That(complete?.PageMatched, Is.False);
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
    public async Task AStreamingPageWithoutACardNamedAsTheTitlePressesNothingAndSaysTheNamesSeen()
    {
        var platform = new FakePlatform(OperaGx)
        {
            AddressOf = _ => "www.netflix.com/search?q=Coco",
            PageStep = new UserBrowserPageStep(false, "title", string.Empty, ["Coco 2", "Cocomelon"]),
        };
        platform.WindowsAfterOpen = [new(11, "Netflix - Opera")];
        using Harness harness = new(platform);

        ExternalCapabilityReceipt receipt = await harness.Adapter.InvokeAsync(
            "streaming.play.named", Json("""{"service":"netflix","title":"Coco"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo(UserBrowserSurface.StreamingTitleNotFound));
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            Assert.That(receipt.Result?.GetProperty("requested").GetString(), Is.EqualTo("Coco"));
            Assert.That(receipt.Result?.GetProperty("candidates")[1].GetString(), Is.EqualTo("Cocomelon"));
            Assert.That(harness.Edge.StreamingCalls, Is.Zero);
        });
    }

    [Test]
    public async Task DisneyTypesTheTitleInItsOwnSearchField()
    {
        var platform = new FakePlatform(OperaGx)
        {
            AddressBeforeOpen = EmptyAddressField,
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
            AddressBeforeOpen = EmptyAddressField,
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
        var platform = new FakePlatform(OperaGx)
        {
            AddressBeforeOpen = EmptyAddressField,
            AddressOf = _ => "www.netflix.com/login",
        };
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

    [Test]
    public async Task AChangedSearchTitleNamingEveryWordIsTheArrivalWhenTheAddressFieldIsStale()
    {
        // Ronda 23 t4-c10 «busca en google los horarios del cercanias de madrid»: Opera GX titled the window
        // «… - Buscar con Google» and its address field kept the previous search; the turn waited 12 s unconfirmed.
        var platform = new FakePlatform(OperaGx)
        {
            WindowsBeforeOpen = [new(11, "si hay película de El Aleph - Buscar con Google - Opera")],
            AddressOf = _ => OldSearch,
        };
        platform.WindowSteps.Add([new(11, "los horarios del cercanías de madrid - Buscar con Google - Opera")]);
        using Harness harness = new(platform);

        ExternalCapabilityReceipt receipt = await harness.Adapter.InvokeAsync(
            "browser.navigate", Json($$"""{"url":"{{AskedSearch}}"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("authority").GetString(),
                Is.EqualTo(UserBrowserSurface.SearchTitleAuthority));
            Assert.That(receipt.Result?.GetProperty("finalUrl").GetString(), Is.EqualTo(AskedSearch));
            Assert.That(platform.AddressReads, Is.Zero, "the title alone, read at once");
            Assert.That(platform.Delays, Is.EqualTo(1));
        });
    }

    [Test]
    public async Task ASearchTitleTheWindowAlreadyHadBeforeTheLinkIsNeverTheArrival()
    {
        // Contracaso: the tab already had that title before navigating; nothing changed, so it proves nothing, and with
        // no window changing at all the wait ends early instead of running out the whole horizon.
        var platform = new FakePlatform(OperaGx)
        {
            WindowsBeforeOpen = [new(11, "los horarios del cercanías de madrid - Buscar con Google - Opera")],
            AddressOf = _ => OldSearch,
        };
        using Harness harness = new(platform);

        ExternalCapabilityReceipt receipt = await harness.Adapter.InvokeAsync(
            "browser.navigate", Json($$"""{"url":"{{AskedSearch}}"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo(UserBrowserSurface.NavigationUnconfirmed));
            Assert.That(platform.Delays, Is.EqualTo(UserBrowserSurface.QuietNavigationPolls));
        });
    }

    [Test]
    public async Task AHostTitleNamingTheWordSearchedInTheBrowsersSegmentIsNeverTheArrival()
    {
        // Revisión 1 r24u contracaso: Opera GX with no network, «busca opera en google». The tab is titled by the host
        // and the browser («www.google.com - Opera»); «opera» is the browser's segment, not a results page.
        const string asked = "https://www.google.com/search?q=opera";
        var platform = new FakePlatform(OperaGx)
        {
            WindowsBeforeOpen = [new(11, "Inicio - Opera")],
            AddressOf = _ => OldSearch,
        };
        platform.WindowSteps.Add([new(11, "www.google.com - Opera")]);
        using Harness harness = new(platform);

        ExternalCapabilityReceipt receipt = await harness.Adapter.InvokeAsync(
            "browser.navigate", Json($$"""{"url":"{{asked}}"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo(UserBrowserSurface.NavigationUnconfirmed));
        });
    }

    [Test]
    public async Task AnotherWindowWhoseVideoNamesTheWordsIsNeverTheArrival()
    {
        // Revisión 1 r24u contracaso: another window of the same browser moves to the next video of its list while the
        // link opens, and that video names the words searched; it is no results page.
        const string asked = "https://www.google.com/search?q=opera";
        var platform = new FakePlatform(OperaGx)
        {
            WindowsBeforeOpen = [new(11, "Inicio - Opera"), new(12, "Lista de música - YouTube - Opera")],
            AddressOf = _ => OldSearch,
        };
        platform.WindowSteps.Add([new(11, "Inicio - Opera"), new(12, "Opera de París en vivo - YouTube - Opera")]);
        using Harness harness = new(platform);

        ExternalCapabilityReceipt receipt = await harness.Adapter.InvokeAsync(
            "browser.navigate", Json($$"""{"url":"{{asked}}"}"""), CancellationToken.None);

        Assert.That(receipt.Verified, Is.False);
    }

    [Test]
    public async Task AChangedSearchTitleMissingAWordAskedIsNeverTheArrival()
    {
        // Contracaso: a search title that does not name every word asked is another search.
        var platform = new FakePlatform(OperaGx)
        {
            WindowsBeforeOpen = [new(11, "Inicio - Opera")],
            AddressOf = _ => OldSearch,
        };
        platform.WindowSteps.Add([new(11, "los horarios del metro de madrid - Buscar con Google - Opera")]);
        using Harness harness = new(platform);

        ExternalCapabilityReceipt receipt = await harness.Adapter.InvokeAsync(
            "browser.navigate", Json($$"""{"url":"{{AskedSearch}}"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo(UserBrowserSurface.NavigationUnconfirmed));
        });
    }

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

    // FT/proveedores goal (review of receipts): the last page BAXY opened went to a named browser (Chrome, a CDP session
    // of its own, while the person's default is Opera): its tabs are listed there, as its page is read there (E016),
    // and the person's Opera is not touched.
    [Test]
    public async Task TheNamedBrowserBaxyLastOpenedIsTheOneItsTabsAreListedIn()
    {
        var context = new CdpBrowserSessionContext();
        using var chrome = new TabbedSession(Path.Combine(Path.GetTempPath(), "baxy-chrome-" + Guid.NewGuid().ToString("N")));
        context.Activate(chrome);
        var opera = new FakePlatform(OperaGx) { Tabs = [new("Inicio", true), new("Correo", false)] };
        using Harness harness = new(opera, context: context);

        ExternalCapabilityReceipt tabs = await harness.Adapter.InvokeAsync(
            "browser.tabs.list", Json("""{"limit":20}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(tabs.Verified, Is.True, tabs.ErrorCode);
            Assert.That(chrome.TabCalls, Is.EqualTo(1));
            Assert.That(opera.FrameWindows, Is.Empty, "the person's Opera is not read");
        });
    }

    // FT/proveedores goal (review of receipts): a page read that found no document named as the window title read the
    // first one on screen (maybe a side panel): the receipt says the page was not matched.
    [TestCase(true)]
    [TestCase(false)]
    public async Task APageReadSaysWhenItWasNotTheTitledPage(bool matched)
    {
        var platform = new FakePlatform(OperaGx) { PageText = new UserBrowserPageText("Panel", "texto", false, matched) };
        using Harness harness = new(platform);

        ExternalCapabilityReceipt page = await harness.Adapter.InvokeAsync(
            "browser.page.read", Json("""{"maximumCharacters":2000}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(page.Verified, Is.True, page.ErrorCode);
            Assert.That(page.Result?.TryGetProperty("pageMatched", out JsonElement value) == true && !value.GetBoolean(),
                Is.EqualTo(!matched));
        });
    }

    private sealed class TabbedSession(string profile) : CdpBrowserSession(profile)
    {
        internal int TabCalls { get; private set; }

        internal override ValueTask<CdpBrowserTabsResult> ListTabsAsync(int limit, CancellationToken cancellationToken)
        {
            TabCalls++;
            return ValueTask.FromResult(new CdpBrowserTabsResult(
                true, [new("chrome-page", "Example Domain", "https://example.com/")], 1, false, string.Empty));
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
        /// <summary>Windows listed in turn after the link is opened (the last one stays); empty uses <see cref="WindowsAfterOpen"/>.</summary>
        internal List<IReadOnlyList<UserBrowserWindow>> WindowSteps { get; } = [];
        internal Func<nint, string?>? AddressBeforeOpen { get; init; }
        internal int BaselineReads { get; private set; }
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
        /// <summary>FT/proveedores goal (E3): a frame and a page text per window, when set (a pop-out reads null).</summary>
        internal Func<nint, UserBrowserFrame?>? FrameOf { get; init; }
        internal Func<nint, UserBrowserPageText?>? PageTextOf { get; init; }
        /// <summary>Page texts read in turn before <see cref="PageText"/> answers (a heavy page read late).</summary>
        internal List<UserBrowserPageText?> PageTextSteps { get; } = [];
        internal List<int> FrameWindows { get; } = [];
        internal List<int> MessageWindows { get; } = [];

        public UserBrowserIdentity? ResolveDefault() => identity;

        /// <summary>The browsers Windows has registered, by family.</summary>
        internal Dictionary<string, UserBrowserIdentity> Registered { get; } = [];
        internal List<(string Executable, string Address)> OpenedWith { get; } = [];

        public UserBrowserIdentity? ResolveRegistered(string family) => Registered.GetValueOrDefault(family);

        public void Open(Uri address)
        {
            if (OpenFails)
                throw new System.ComponentModel.Win32Exception(1155, "No application is associated.");
            Opened.Add(address.AbsoluteUri);
            _opened = true;
        }

        public void OpenWith(UserBrowserIdentity browser, Uri address)
        {
            if (OpenFails)
                throw new System.ComponentModel.Win32Exception(2, "The system cannot find the file specified.");
            OpenedWith.Add((browser.Executable, address.AbsoluteUri));
            _opened = true;
        }

        internal List<int> Fronted { get; } = [];

        public ValueTask<bool> BringToFrontAsync(nint window, CancellationToken cancellationToken)
        {
            Fronted.Add((int)window);
            return ValueTask.FromResult(true);
        }

        /// <summary>The windows of a browser other than the default one, by process name.</summary>
        internal Dictionary<string, IReadOnlyList<UserBrowserWindow>> OtherWindows { get; } = [];

        public IReadOnlyList<UserBrowserWindow> ListWindows(string processName)
        {
            if (processName != identity?.ProcessName)
                return OtherWindows.GetValueOrDefault(processName) ?? [];
            if (!_opened)
                return WindowsBeforeOpen;
            if (WindowSteps.Count == 0)
                return WindowsAfterOpen ?? WindowsBeforeOpen;
            IReadOnlyList<UserBrowserWindow> current = WindowSteps[0];
            if (WindowSteps.Count > 1)
                WindowSteps.RemoveAt(0);
            return current;
        }

        internal int SessionReads { get; private set; }

        public ValueTask<IReadOnlyList<UserMediaSession>?> ReadMediaSessionsAsync(CancellationToken cancellationToken)
        {
            SessionReads++;
            if (!_opened)
                return ValueTask.FromResult<IReadOnlyList<UserMediaSession>?>(SessionsBeforeOpen);
            if (SessionsAfterOpen.Count == 0)
                return ValueTask.FromResult<IReadOnlyList<UserMediaSession>?>([]);
            IReadOnlyList<UserMediaSession> current = SessionsAfterOpen[0];
            if (SessionsAfterOpen.Count > 1)
                SessionsAfterOpen.RemoveAt(0);
            return ValueTask.FromResult<IReadOnlyList<UserMediaSession>?>(current);
        }

        public ValueTask<bool> PlayMediaSessionAsync(UserMediaSession session, CancellationToken cancellationToken)
        {
            Played.Add(session);
            OnPlay?.Invoke(session);
            return ValueTask.FromResult(true);
        }

        /// <summary>
        /// Reads before the link is opened (the front window's address kept as the baseline of a navigation, or a page
        /// read) are counted apart in <see cref="BaselineReads"/>; <see cref="AddressBeforeOpen"/>, when set, answers
        /// them, otherwise <see cref="AddressOf"/> does.
        /// </summary>
        public ValueTask<string?> ReadAddressAsync(nint window, CancellationToken cancellationToken)
        {
            if (!_opened)
            {
                BaselineReads++;
                return ValueTask.FromResult((AddressBeforeOpen ?? AddressOf)(window));
            }
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
            FrameWindows.Add((int)window);
            if (FrameOf is not null)
                return ValueTask.FromResult(FrameOf(window));
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
            MessageWindows.Add((int)window);
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
            MessageWindows.Add((int)window);
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
            if (PageTextSteps.Count > 0)
            {
                UserBrowserPageText? step = PageTextSteps[0];
                PageTextSteps.RemoveAt(0);
                return ValueTask.FromResult(step);
            }
            return ValueTask.FromResult(PageTextOf is not null ? PageTextOf(window) : PageText);
        }

        internal int Delays { get; private set; }

        public ValueTask DelayAsync(TimeSpan delay, CancellationToken cancellationToken)
        {
            Delays++;
            return ValueTask.CompletedTask;
        }
    }

    private sealed class StreamHttpHandler(Stream body) : HttpMessageHandler
    {
        protected override Task<HttpResponseMessage> SendAsync(
            HttpRequestMessage request, CancellationToken cancellationToken) => Task.FromResult(
                new HttpResponseMessage(HttpStatusCode.OK) { Content = new StreamContent(body) });
    }

    // A body of «length» bytes of markup that never carries a result; with «stallAfter», it stops answering there.
    private sealed class CountingStream(long length, long stallAfter = -1) : Stream
    {
        internal long BytesRead { get; private set; }

        public override bool CanRead => true;
        public override bool CanSeek => false;
        public override bool CanWrite => false;
        public override long Length => throw new NotSupportedException();
        public override long Position { get => BytesRead; set => throw new NotSupportedException(); }
        public override void Flush() { }
        public override long Seek(long offset, SeekOrigin origin) => throw new NotSupportedException();
        public override void SetLength(long value) => throw new NotSupportedException();
        public override void Write(byte[] buffer, int offset, int count) => throw new NotSupportedException();

        public override int Read(byte[] buffer, int offset, int count) =>
            ReadAsync(buffer.AsMemory(offset, count)).AsTask().GetAwaiter().GetResult();

        public override async ValueTask<int> ReadAsync(Memory<byte> buffer, CancellationToken cancellationToken = default)
        {
            if (stallAfter >= 0 && BytesRead >= stallAfter)
                await Task.Delay(Timeout.Infinite, cancellationToken);
            int count = (int)Math.Min(buffer.Length, length - BytesRead);
            buffer.Span[..count].Fill((byte)'a');
            BytesRead += count;
            return count;
        }
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
