using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// M122 manual check, opt-in only: opens example.com and one YouTube video in
/// the person's default browser (two new tabs; nothing is closed), reports what
/// the address field and the media session showed, then pauses the video it
/// started through that same session. Never runs in a suite: it is Explicit and
/// also needs BAXY_USER_BROWSER_LIVE_CHECK=1. Run it through
/// scripts/check_user_browser.ps1, and not while a measurement or the person
/// is using the browser or the speakers.
/// </summary>
[TestFixture]
[Explicit("Opens the person's default browser and plays a video.")]
public sealed class UserBrowserLiveCheck
{
    [Test]
    public async Task DefaultBrowserOpensVerifiesAndPausesWhatItStarted()
    {
        if (Environment.GetEnvironmentVariable("BAXY_USER_BROWSER_LIVE_CHECK") != "1")
            Assert.Ignore("Set BAXY_USER_BROWSER_LIVE_CHECK=1 to run the live check.");
        string query = Environment.GetEnvironmentVariable("BAXY_USER_BROWSER_LIVE_QUERY")
            ?? "Rick Astley Never Gonna Give You Up";
        var platform = new WindowsUserBrowserPlatform();
        UserBrowserIdentity? identity = platform.ResolveDefault();
        TestContext.Out.WriteLine("default_browser=" + (identity is null
            ? "none"
            : $"{identity.DisplayName} ({identity.ProgId}) {identity.Executable}"));
        Assert.That(identity, Is.Not.Null, "no default browser resolved");

        string profile = Path.Combine(Path.GetTempPath(), "baxy-live-check-" + Guid.NewGuid().ToString("N"));
        using var http = new HttpClient { Timeout = TimeSpan.FromSeconds(20) };
        using var edge = new UserBrowserTests.CountingEdge(profile);
        using var adapter = new WebBrowserAdapter(edge, http, null, new UserBrowserSurface(platform));

        ExternalCapabilityReceipt navigation = await adapter.InvokeAsync(
            "browser.navigate", Json("""{"url":"https://example.com/"}"""), CancellationToken.None);
        TestContext.Out.WriteLine("navigate: " + Describe(navigation));

        string arguments = JsonSerializer.Serialize(new Dictionary<string, string> { ["query"] = query });
        ExternalCapabilityReceipt playback = await adapter.InvokeAsync(
            "media.play.youtube", Json(arguments), CancellationToken.None);
        TestContext.Out.WriteLine("youtube: " + Describe(playback));

        if (playback.Verified
            && playback.Result?.GetProperty("sourceAppUserModelId").GetString() is { Length: > 0 } source)
        {
            using var media = new WindowsMediaSessionAdapter();
            string pause = JsonSerializer.Serialize(new Dictionary<string, string>
            {
                ["action"] = "pause",
                ["sourceApp"] = source,
            });
            ExternalCapabilityReceipt paused = await media.InvokeAsync(
                "media.control", Json(pause), CancellationToken.None);
            TestContext.Out.WriteLine("pause_through_smtc: " + Describe(paused));
        }
        Assert.That(edge.NavigateCalls + edge.YouTubeCalls, Is.Zero, "the product browser was not used");
    }

    private static string Describe(ExternalCapabilityReceipt receipt) =>
        $"verified={receipt.Verified} effect={receipt.EffectObserved} uncertain={receipt.EffectMayHaveOccurred} "
        + $"error={receipt.ErrorCode ?? "-"} result={receipt.Result?.GetRawText() ?? "-"}";

    private static JsonElement Json(string value) => JsonDocument.Parse(value).RootElement.Clone();
}
