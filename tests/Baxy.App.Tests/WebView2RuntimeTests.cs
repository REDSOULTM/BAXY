using System.IO;
using System.Net;
using System.Net.Http;
using Microsoft.Web.WebView2.Core;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// Steam and itch.io install no prerequisite of BAXY's window, and Microsoft says some devices do not have WebView2:
/// the App installs it. What comes from the network runs only with Microsoft's signature, and only the runtime being
/// there afterwards counts as installed (https://learn.microsoft.com/microsoft-edge/webview2/concepts/distribution).
/// </summary>
[TestFixture]
public sealed class WebView2RuntimeTests
{
    private string _directory = "";

    [SetUp]
    public void CreateDirectory() =>
        _directory = Directory.CreateTempSubdirectory("baxy-webview2-test-").FullName;

    [TearDown]
    public void RemoveDirectory() => Directory.Delete(_directory, recursive: true);

    private static byte[] SignedByMicrosoft() =>
        File.ReadAllBytes(typeof(CoreWebView2Environment).Assembly.Location);

    private static HttpClient Serving(byte[] bytes) => new(new Answer(HttpStatusCode.OK, bytes));

    private Task Install(HttpClient http, Func<string, int> run, Func<bool> installed) =>
        WebView2Runtime.InstallAsync(
            http,
            _directory,
            (path, _) => Task.FromResult(run(path)),
            installed,
            CancellationToken.None);

    [Test]
    public async Task A_signed_bootstrapper_runs_once_and_leaves_the_runtime_and_no_file()
    {
        using HttpClient http = Serving(SignedByMicrosoft());
        var ran = new List<string>();
        var there = false;

        await Install(http, path => { ran.Add(path); there = true; return 0; }, () => there);

        Assert.That(ran, Has.Count.EqualTo(1));
        Assert.That(Directory.GetFiles(_directory), Is.Empty);
    }

    [Test]
    public void An_unsigned_download_never_runs_and_is_removed()
    {
        using HttpClient http = Serving([0x4D, 0x5A, 0x00, 0x01]);
        var ran = false;

        Assert.ThrowsAsync<InvalidOperationException>(() => Install(http, _ => { ran = true; return 0; }, () => false));

        Assert.That(ran, Is.False);
        Assert.That(Directory.GetFiles(_directory), Is.Empty);
    }

    [Test]
    public void An_exit_code_of_zero_with_no_runtime_is_a_failure_that_says_so()
    {
        using HttpClient http = Serving(SignedByMicrosoft());

        var failure = Assert.ThrowsAsync<InvalidOperationException>(() => Install(http, _ => 0, () => false));

        Assert.That(failure!.Message, Does.Contain("0"));
        Assert.That(Directory.GetFiles(_directory), Is.Empty);
    }

    [Test]
    public void A_refused_download_is_a_start_failure_the_window_can_show()
    {
        using HttpClient http = new(new Answer(HttpStatusCode.NotFound, []));
        var ran = false;

        Assert.ThrowsAsync<InvalidOperationException>(() => Install(http, _ => { ran = true; return 0; }, () => false));

        Assert.That(ran, Is.False);
    }

    private sealed class Answer(HttpStatusCode status, byte[] bytes) : HttpMessageHandler
    {
        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken) =>
            Task.FromResult(new HttpResponseMessage(status) { Content = new ByteArrayContent(bytes) });
    }
}
