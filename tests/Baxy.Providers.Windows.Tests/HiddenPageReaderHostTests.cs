using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// SRCH1: the web search's pages are read by the App's executable in its hidden reader mode (Baxy.App.HiddenPageReader),
/// asked one JSON line per page. What the host sends and how it reads the answer, where it finds the executable, and
/// that a machine without it reads nothing and opens nothing.
/// </summary>
[TestFixture]
[NonParallelizable]
public sealed class HiddenPageReaderHostTests
{
    private string _folder = string.Empty;

    [SetUp]
    public void SetUp()
    {
        _folder = Path.Combine(Path.GetTempPath(), "baxy-hidden-reader-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(Path.Combine(_folder, "core"));
    }

    [TearDown]
    public void TearDown()
    {
        Environment.SetEnvironmentVariable(HiddenPageReaderHost.ExecutableOverride, null);
        Directory.Delete(_folder, recursive: true);
    }

    [Test]
    public void ThePageAskedIsItsAddressAndHowLongItIsWaitedFor()
    {
        string line = HiddenPageReaderHost.Request(
            new Uri("https://html.duckduckgo.com/html/?q=caf%C3%A9%20%26%20pan&kl=cl-es"), TimeSpan.FromSeconds(10), TimeSpan.Zero);
        string drawn = HiddenPageReaderHost.Request(new Uri("https://x.example/"), TimeSpan.FromSeconds(10), TimeSpan.FromSeconds(3));

        Assert.That(line, Is.EqualTo(
            """{"url":"https://html.duckduckgo.com/html/?q=caf%C3%A9%20%26%20pan\u0026kl=cl-es","withinMs":10000}"""));
        Assert.That(drawn, Is.EqualTo("""{"url":"https://x.example/","withinMs":10000,"settleMs":3000}"""));
    }

    [TestCase("""{"outcome":"loaded","httpStatus":200,"final":"https://x.example/","html":"<p>a</p>"}""", "Loaded", 200, "<p>a</p>")]
    [TestCase("""{"outcome":"loaded","httpStatus":202,"html":"<form id=\"challenge-form\"></form>"}""", "Loaded", 202, "<form id=\"challenge-form\"></form>")]
    [TestCase("""{"outcome":"timeout","html":""}""", "Timeout", null, "")]
    [TestCase("""{"outcome":"unavailable","html":""}""", "Unavailable", null, "")]
    [TestCase("""{"outcome":"something new"}""", "Failed", null, "")]
    public void AnAnswerIsReadAsTheReaderGaveIt(string line, string outcome, int? status, string html)
    {
        HiddenPage page = HiddenPageReaderHost.Parse(line);

        Assert.Multiple(() =>
        {
            Assert.That(page.Outcome.ToString(), Is.EqualTo(outcome));
            Assert.That(page.HttpStatus, Is.EqualTo(status));
            Assert.That(page.Html, Is.EqualTo(html));
            Assert.That(page.Final, Is.EqualTo(line.Contains("\"final\"", StringComparison.Ordinal) ? new Uri("https://x.example/") : null));
        });
    }

    // The product's core sits in «core» beside the App's executable; a development build has both in one folder.
    [Test]
    public void TheReaderIsTheAppsExecutableBesideOrAboveTheCore()
    {
        string core = Path.Combine(_folder, "core");
        Assert.That(HiddenPageReaderHost.FindExecutable(core), Is.Null);

        File.WriteAllText(Path.Combine(_folder, "Baxy.exe"), "");
        Assert.That(HiddenPageReaderHost.FindExecutable(core), Is.EqualTo(Path.Combine(_folder, "Baxy.exe")));

        File.WriteAllText(Path.Combine(core, "Baxy.exe"), "");
        Assert.That(HiddenPageReaderHost.FindExecutable(core), Is.EqualTo(Path.Combine(core, "Baxy.exe")));
    }

    [Test]
    public async Task WithoutTheReaderNothingIsReadAndNothingStarts()
    {
        using var host = new HiddenPageReaderHost(executable: null, Path.Combine(_folder, "webview2-search"));

        HiddenPage page = await host.ReadAsync(
            new Uri("https://html.duckduckgo.com/html/?q=x"), TimeSpan.FromSeconds(1), TimeSpan.Zero, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(page.Outcome, Is.EqualTo(HiddenPageOutcome.Unavailable));
            Assert.That(Directory.Exists(Path.Combine(_folder, "webview2-search")), Is.False);
        });
    }

    // INT10: the reader's folder is BAXY's own (no sign-in, nothing of the person) and Chromium bounds it only by its own
    // caches' limits and each site's quota. Past its cap it is emptied before a reader starts on it; under it, kept.
    [TestCase(1L, true)]
    [TestCase(-1L, false)]
    public async Task AReaderFolderPastItsCapIsEmptiedBeforeAReaderStarts(long overCap, bool emptied)
    {
        string profile = Path.Combine(_folder, "webview2-search");
        string cache = Path.Combine(profile, "EBWebView", "Default", "Cache", "Cache_Data");
        Directory.CreateDirectory(cache);
        File.WriteAllText(Path.Combine(profile, "EBWebView", "Local State"), "{}");
        using (FileStream data = File.Create(Path.Combine(cache, "data_1")))
            data.SetLength(HiddenPageReaderHost.ProfileCap + overCap - 2);
        // An executable that cannot start: the folder is looked at, and nothing is read.
        string unstartable = Path.Combine(_folder, "Baxy.exe");
        File.WriteAllText(unstartable, "");
        using var host = new HiddenPageReaderHost(unstartable, profile);

        HiddenPage page = await host.ReadAsync(
            new Uri("https://html.duckduckgo.com/html/?q=x"), TimeSpan.FromSeconds(1), TimeSpan.Zero, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(page.Outcome, Is.EqualTo(HiddenPageOutcome.Unavailable));
            Assert.That(Directory.Exists(profile), Is.True);
            Assert.That(Directory.EnumerateFileSystemEntries(profile).Any(), Is.EqualTo(!emptied));
        });
    }
}
