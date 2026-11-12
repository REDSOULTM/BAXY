using System.Diagnostics;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// LEC4 (VIVO11), on the real desktop, opt-in only (Explicit and BAXY_PAGE_LIVE_CHECK=1): an Edge window of the test's own
/// in app mode (no tab strip, a temporary profile) in front, and browser.page.read asked of the person's default browser
/// when that is another one with no window open. The window is closed by its process id.
/// </summary>
[TestFixture]
[Explicit("Opens an Edge window of its own with a local page.")]
public sealed class UserBrowserOtherBrowserLiveCheck
{
    private const string EdgeExecutable = @"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe";

    [Test]
    public async Task TheWindowOfAnotherBrowserInFrontIsRead()
    {
        if (Environment.GetEnvironmentVariable("BAXY_PAGE_LIVE_CHECK") != "1")
            Assert.Ignore("Set BAXY_PAGE_LIVE_CHECK=1 to run the live check.");
        var platform = new WindowsUserBrowserPlatform();
        UserBrowserIdentity? person = UserBrowserIdentityResolver.ResolveFromRegistry();
        if (person is null || person.Family == "edge" || platform.ListWindows(person.ProcessName).Count > 0)
            Assert.Ignore("Needs a default browser other than Edge, with no window open.");
        string root = Path.Combine(Path.GetTempPath(), "baxy-other-live-" + Guid.NewGuid().ToString("N")[..8]);
        string profile = Path.Combine(root, "profile");
        Directory.CreateDirectory(profile);
        string file = Path.Combine(root, "charla.html");
        string title = "Charla " + Path.GetFileName(root);
        await File.WriteAllTextAsync(file, "<!doctype html><html><head><title>" + title + "</title></head><body>"
            + "<h1>Huerto del patio</h1><p>Las tomateras se riegan dos veces por semana con cuatro litros cada una.</p>"
            + "<p>El martes llega la malla de sombra de tres metros.</p></body></html>");
        using Process edge = Process.Start(new ProcessStartInfo(EdgeExecutable)
        {
            Arguments = "--user-data-dir=\"" + profile + "\" --no-first-run --no-default-browser-check --app=\""
                + new Uri(file).AbsoluteUri + "\"",
            UseShellExecute = false,
        })!;
        try
        {
            nint window = 0;
            for (int attempt = 0; attempt < 40 && window == 0; attempt++)
            {
                await Task.Delay(500);
                window = platform.ListWindows("msedge").FirstOrDefault(found => found.Title.StartsWith(title, StringComparison.Ordinal))?.Handle ?? 0;
            }
            Assert.That(window, Is.Not.EqualTo((nint)0), "the test's own window");
            _ = VisibleControlSurface.BringToFront(window);
            await Task.Delay(1_500);

            ExternalCapabilityReceipt read = await new UserBrowserSurface(platform).ReadPageAsync(
                "browser.page.read", person, 6_000, CancellationToken.None);
            string result = read.Result is { } json ? JsonSerializer.Serialize(json) : "null";
            TestContext.Out.WriteLine($"default={person.DisplayName} error={read.ErrorCode ?? "-"} result={result}");
            Assert.That(read.Verified, Is.True, read.ErrorCode);
            Assert.That(read.Result!.Value.GetProperty("text").GetString(), Does.Contain("cuatro litros"));
        }
        finally
        {
            if (!edge.HasExited)
                edge.Kill(entireProcessTree: true);
            await edge.WaitForExitAsync();
            for (int attempt = 0; attempt < 10 && Directory.Exists(root); attempt++)
            {
                try
                {
                    Directory.Delete(root, recursive: true);
                }
                catch (IOException)
                {
                    await Task.Delay(500);
                }
            }
        }
    }
}
