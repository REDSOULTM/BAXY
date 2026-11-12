using System.IO;
using System.Text.Json;
using Microsoft.Web.WebView2.Core;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// SRCH1: «Baxy.exe --hidden-page-reader &lt;folder&gt;» is baxy-core's hidden page reader and nothing else (no App
/// start, no window); any other start of the App is the App's. Its answer is one JSON line per page.
/// </summary>
[TestFixture]
public sealed class HiddenPageReaderTests
{
    [Test]
    public void OnlyItsOwnArgumentAndAFolderStartTheReader()
    {
        Assert.Multiple(() =>
        {
            Assert.That(HiddenPageReader.IsRequested(["--hidden-page-reader", @"C:\data\webview2-search"]), Is.True);
            Assert.That(HiddenPageReader.IsRequested([]), Is.False);
            Assert.That(HiddenPageReader.IsRequested(["--hidden-page-reader"]), Is.False);
            Assert.That(HiddenPageReader.IsRequested(["--hidden-page-reader", " "]), Is.False);
            Assert.That(HiddenPageReader.IsRequested(["--conductor", @"C:\x"]), Is.False);
        });
    }

    [Test]
    public void AnAnswerIsOneLineWithWhatThePageAnswered()
    {
        string line = HiddenPageReader.Answer("loaded", 200, "https://example.com/", "<p>\n«hola»</p>");
        using JsonDocument answer = JsonDocument.Parse(line);

        Assert.Multiple(() =>
        {
            Assert.That(line, Does.Not.Contain("\n"));
            Assert.That(answer.RootElement.GetProperty("outcome").GetString(), Is.EqualTo("loaded"));
            Assert.That(answer.RootElement.GetProperty("httpStatus").GetInt32(), Is.EqualTo(200));
            Assert.That(answer.RootElement.GetProperty("html").GetString(), Is.EqualTo("<p>\n«hola»</p>"));
            Assert.That(HiddenPageReader.Answer("timeout", null, null, null),
                Is.EqualTo("""{"outcome":"timeout","html":""}"""));
        });
    }

    // INT10: once its browser process ended, the view is closed for good and every page answered «failed» at once
    // (measured: 3 of 3 in 0.00 s, the reader alive), and each search said it could not search until the reader sat idle
    // for ten minutes. The reader ends then, and the Core starts another one on the next page; a render process that
    // ended is made again by the view's next navigation.
    [TestCase(Microsoft.Web.WebView2.Core.CoreWebView2ProcessFailedKind.BrowserProcessExited, true)]
    [TestCase(Microsoft.Web.WebView2.Core.CoreWebView2ProcessFailedKind.RenderProcessExited, false)]
    [TestCase(Microsoft.Web.WebView2.Core.CoreWebView2ProcessFailedKind.RenderProcessUnresponsive, false)]
    [TestCase(Microsoft.Web.WebView2.Core.CoreWebView2ProcessFailedKind.FrameRenderProcessExited, false)]
    public void TheReaderEndsWhenItsBrowserProcessEnded(
        Microsoft.Web.WebView2.Core.CoreWebView2ProcessFailedKind kind, bool ends)
    {
        Assert.That(HiddenPageReader.EndsTheReader(kind), Is.EqualTo(ends));
    }

    // SIS1 (REV10 M1): AllSite («all site data … inclusive of AllDomStorage and Cookies») kept the browsing history and
    // the disk cache, so the address of every search read stayed in the reader's folder.
    [Test]
    public void APageLeftForgetsItsHistoryAndCacheToo()
    {
        Assert.Multiple(() =>
        {
            Assert.That(HiddenPageReader.Forgotten.HasFlag(CoreWebView2BrowsingDataKinds.AllSite), Is.True);
            Assert.That(HiddenPageReader.Forgotten.HasFlag(CoreWebView2BrowsingDataKinds.BrowsingHistory), Is.True);
            Assert.That(HiddenPageReader.Forgotten.HasFlag(CoreWebView2BrowsingDataKinds.DiskCache), Is.True);
        });
    }

    // SIS1 (REV10 M1): «Olvidar todo» empties the reader's folder; a file a running reader holds stays, and is counted.
    [Test]
    public void ForgettingEverythingEmptiesTheReadersFolder()
    {
        string dataRoot = Path.Combine(Path.GetTempPath(), "baxy-app-tests", Guid.NewGuid().ToString("N"));
        string folder = Path.Combine(dataRoot, HiddenPageReader.FolderName);
        Directory.CreateDirectory(Path.Combine(folder, "EBWebView", "Default", "Cache"));
        File.WriteAllText(Path.Combine(folder, "EBWebView", "Default", "History"), "https://buscador.example/?q=pan");
        File.WriteAllText(Path.Combine(folder, "EBWebView", "Default", "Cache", "data_0"), "x");
        string held = Path.Combine(folder, "lockfile");
        File.WriteAllText(held, string.Empty);
        try
        {
            int stayed;
            using (new FileStream(held, FileMode.Open, FileAccess.Read, FileShare.None))
            {
                stayed = HiddenPageReader.Forget(dataRoot);
            }

            Assert.Multiple(() =>
            {
                Assert.That(stayed, Is.EqualTo(1));
                Assert.That(Directory.Exists(Path.Combine(folder, "EBWebView")), Is.False);
                Assert.That(HiddenPageReader.Forget(dataRoot), Is.Zero);
                Assert.That(Directory.EnumerateFileSystemEntries(folder), Is.Empty);
                Assert.That(HiddenPageReader.Forget(Path.Combine(dataRoot, "ninguna")), Is.Zero);
            });
        }
        finally
        {
            Directory.Delete(dataRoot, recursive: true);
        }
    }
}
