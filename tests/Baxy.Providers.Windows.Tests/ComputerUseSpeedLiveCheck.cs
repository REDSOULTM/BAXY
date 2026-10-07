using System.Diagnostics;
using Baxy.Providers.Windows.Applications;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Computer use speed, manual check, opt-in only: opens one packaged application (the Clock by default; any installed name
/// through BAXY_CU_OPEN_APP) and reports how long the opening took to verify and through which window. Measured
/// before: the open waited its whole 30 s budget with the application on screen, because a packaged app has no
/// top-level window of its own. Never runs in a suite: it is Explicit and also needs BAXY_CU_OPEN_LIVE_CHECK=1;
/// nothing is closed. The browser frame read only reads the person's browser window (BAXY_CU_BROWSER_LIVE_CHECK=1).
/// </summary>
[TestFixture]
[Explicit("Opens an application on the person's desktop.")]
public sealed class ComputerUseSpeedLiveCheck
{
    [Test]
    public async Task APackagedApplicationOpenIsVerifiedThroughItsFrame()
    {
        if (Environment.GetEnvironmentVariable("BAXY_CU_OPEN_LIVE_CHECK") != "1")
            Assert.Ignore("Set BAXY_CU_OPEN_LIVE_CHECK=1 to run the live check.");
        string application = Environment.GetEnvironmentVariable("BAXY_CU_OPEN_APP") ?? "Reloj";
        var provider = new WindowsInstalledApplicationOpenProvider();
        var watch = Stopwatch.StartNew();

        ApplicationOpenResult result = await provider.OpenAsync(
            new ApplicationOpenRequest(application, "live-check"), CancellationToken.None);

        long elapsed = watch.ElapsedMilliseconds;
        Report(application, result, elapsed);
        // Once more with the installed catalog already read (the product keeps it five minutes): the opening alone.
        watch.Restart();
        ApplicationOpenResult again = await provider.OpenAsync(
            new ApplicationOpenRequest(application, "live-check-again"), CancellationToken.None);
        long againElapsed = watch.ElapsedMilliseconds;
        Report(application, again, againElapsed);
        Assert.Multiple(() =>
        {
            Assert.That(result.Verified, Is.True);
            Assert.That(again.Verified, Is.True);
            Assert.That(elapsed, Is.LessThan(10_000));
        });
    }

    /// <summary>
    /// After the opening: one view of the opened application's window, one click on a label of it (BAXY_CU_CLICK,
    /// «Cronómetro» by default) and one Tab key, each timed, through the same adapters the product composes.
    /// </summary>
    [Test]
    public async Task TheOpenedApplicationIsViewedClickedAndTypedOnQuickly()
    {
        if (Environment.GetEnvironmentVariable("BAXY_CU_OPEN_LIVE_CHECK") != "1")
            Assert.Ignore("Set BAXY_CU_OPEN_LIVE_CHECK=1 to run the live check.");
        string application = Environment.GetEnvironmentVariable("BAXY_CU_OPEN_APP") ?? "Reloj";
        string label = Environment.GetEnvironmentVariable("BAXY_CU_CLICK") ?? "Cronómetro";
        ApplicationOpenResult opened = await new WindowsInstalledApplicationOpenProvider().OpenAsync(
            new ApplicationOpenRequest(application, "live-check-view"), CancellationToken.None);
        Assert.That(opened.Verified, Is.True);
        using var controls = new WindowsVisibleControlAdapter();
        var watch = Stopwatch.StartNew();
        await controls.PrewarmAsync();
        long prewarm = watch.ElapsedMilliseconds;

        watch.Restart();
        ExternalCapabilityReceipt view = await controls.InvokeAsync(
            "input.visible.controls",
            System.Text.Json.JsonDocument.Parse($$"""{"processId":{{opened.ProcessId}},"includeText":false}""").RootElement,
            CancellationToken.None);
        long viewed = watch.ElapsedMilliseconds;
        watch.Restart();
        ExternalCapabilityReceipt click = await controls.InvokeAsync(
            "input.visible.click",
            System.Text.Json.JsonDocument.Parse($$"""{"label":"{{label}}"}""").RootElement,
            CancellationToken.None);
        long clicked = watch.ElapsedMilliseconds;
        watch.Restart();
        ExternalCapabilityReceipt key = await new WindowsDesktopInteractionAdapter().InvokeAsync(
            "input.key.press", System.Text.Json.JsonDocument.Parse("""{"key":"tab"}""").RootElement,
            CancellationToken.None);
        long pressed = watch.ElapsedMilliseconds;

        TestContext.Out.WriteLine($"prewarm_ms={prewarm} view_ms={viewed} view_ok={view.Verified} view_error={view.ErrorCode}");
        TestContext.Out.WriteLine($"click_ms={clicked} click_ok={click.Verified} click_error={click.ErrorCode} " +
            $"click={click.Result?.GetRawText()}");
        TestContext.Out.WriteLine($"key_ms={pressed} key_ok={key.Verified} key_error={key.ErrorCode}");
        Assert.Multiple(() =>
        {
            Assert.That(view.Verified, Is.True);
            Assert.That(click.Verified, Is.True);
            Assert.That(key.Verified, Is.True);
        });
    }

    /// <summary>Three reads of the person's browser frame through the shared script worker; the first one starts it.</summary>
    [Test]
    public async Task TheBrowserFrameIsReadWithoutAPowerShellPerRead()
    {
        if (Environment.GetEnvironmentVariable("BAXY_CU_BROWSER_LIVE_CHECK") != "1")
            Assert.Ignore("Set BAXY_CU_BROWSER_LIVE_CHECK=1 to run the live check.");
        var platform = new WindowsUserBrowserPlatform();
        UserBrowserIdentity? identity = platform.ResolveDefault();
        Assert.That(identity, Is.Not.Null, "no default browser resolved");
        IReadOnlyList<UserBrowserWindow> windows = platform.ListWindows(identity!.ProcessName);
        Assert.That(windows, Is.Not.Empty, "the default browser shows no window");
        UserBrowserWindow front = windows[0];
        var watch = Stopwatch.StartNew();
        for (int read = 1; read <= 3; read++)
        {
            watch.Restart();
            UserBrowserFrame? frame = await platform.ReadFrameAsync(front.Handle, CancellationToken.None);
            TestContext.Out.WriteLine($"frame_read={read} ms={watch.ElapsedMilliseconds} tabs={frame?.Tabs.Count}");
            Assert.That(frame, Is.Not.Null);
        }
    }

    private static void Report(string application, ApplicationOpenResult result, long elapsed)
    {
        nint window = (nint)(result.WindowHandle ?? 0);
        TestContext.Out.WriteLine(
            $"app={application} verified={result.Verified} error={result.ErrorCode} ms={elapsed} " +
            $"pid={result.ProcessId} window={result.WindowHandle} class={VisibleControlSurface.ClassName(window)} " +
            $"title={VisibleControlSurface.WindowTitle(window)} reused={result.AlreadyRunning}");
    }
}
