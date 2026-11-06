using System.Diagnostics;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Uso real 03-11 (U53), on the real desktop, opt-in only (Explicit and BAXY_TAB_LIVE_CHECK=1): an Edge of the test's
/// own (a temporary profile, three local pages with invented titles) closed tab by tab through browser.control's real
/// UI Automation frame reads and window messages. Every window step is confined to the windows of that Edge's own
/// process (<see cref="OwnWindows"/>), so no other browser window is read or touched; the Edge is closed by its exact
/// process id and its profile deleted.
/// </summary>
[TestFixture]
[Explicit("Opens an Edge window of its own with three local pages and closes its tabs.")]
public sealed class UserBrowserNamedTabLiveCheck
{
    private const string EdgeExecutable = @"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe";

    [Test]
    public async Task ANamedTabIsClosedByItsTitleAndTheReceiptSaysWhichWentAndWhichAreLeft()
    {
        if (Environment.GetEnvironmentVariable("BAXY_TAB_LIVE_CHECK") != "1")
            Assert.Ignore("Set BAXY_TAB_LIVE_CHECK=1 to run the live check.");
        string root = Path.Combine(Path.GetTempPath(), "baxy-tab-live-" + Guid.NewGuid().ToString("N")[..8]);
        string profile = Path.Combine(root, "profile");
        Directory.CreateDirectory(profile);
        string[] titles = ["Alfa Cuaderno", "Bravo Facturas", "Charlie Musica"];
        string[] pages = [.. titles.Select(title =>
        {
            string path = Path.Combine(root, title.Replace(' ', '-') + ".html");
            File.WriteAllText(path, "<!doctype html><html><head><title>" + title + "</title></head><body>" + title + "</body></html>");
            return new Uri(path).AbsoluteUri;
        })];
        using Process edge = Process.Start(new ProcessStartInfo(EdgeExecutable)
        {
            Arguments = "--user-data-dir=\"" + profile + "\" --no-first-run --no-default-browser-check --new-window "
                + string.Join(' ', pages.Select(page => "\"" + page + "\"")),
            UseShellExecute = false,
        })!;
        try
        {
            var platform = new OwnWindows(new WindowsUserBrowserPlatform(), edge.Id);
            var browser = new UserBrowserIdentity("MSEdgeHTM", "edge", "Microsoft Edge", EdgeExecutable);
            var surface = new UserBrowserSurface(platform);
            UserBrowserFrame? frame = await ThreeTabsAsync(platform, titles);
            Assert.That(frame, Is.Not.Null, "the Edge of the test showed its three tabs");
            TestContext.Out.WriteLine("before: " + string.Join(" | ", frame!.Tabs.Select(tab => (tab.Selected ? "*" : "") + tab.Title + " [" + tab.Id + "]")));
            UserBrowserFrame? again = await platform.ReadFrameAsync(platform.Window, CancellationToken.None);
            TestContext.Out.WriteLine("again:  " + string.Join(" | ", again!.Tabs.Select(tab => (tab.Selected ? "*" : "") + tab.Title + " [" + tab.Id + "]")));

            ExternalCapabilityReceipt notFound = await surface.ControlAsync(
                "browser.control", browser, "close", "netflix", new ExternalEffectBoundary(), CancellationToken.None);
            // Uso real 03-11 (U64): a switch to a tab that is not the active one, its name split as the ear splits it
            // («fact uras» for «Facturas»), seen as that tab (by its runtime id) selected in the strip read again.
            UserBrowserTab goTo = frame.Tabs.First(tab => !tab.Selected
                && titles.Any(title => UserBrowserSurface.TitleBears(tab.Title, title)));
            string word = titles.First(title => UserBrowserSurface.TitleBears(goTo.Title, title)).Split(' ')[1].ToLowerInvariant();
            string split = word[..4] + " " + word[4..];
            ExternalCapabilityReceipt switched = await surface.ControlAsync(
                "browser.control", browser, "switch_tab", split, new ExternalEffectBoundary(), CancellationToken.None);
            UserBrowserFrame? afterSwitch = await platform.ReadFrameAsync(platform.Window, CancellationToken.None);
            TestContext.Out.WriteLine("switch «" + split + "»: " + switched.Verified + " " + switched.ErrorCode + " " + switched.Result);
            TestContext.Out.WriteLine("after switch: " + string.Join(" | ", afterSwitch!.Tabs.Select(tab => (tab.Selected ? "*" : "") + tab.Title + " [" + tab.Id + "]")));
            Assert.Multiple(() =>
            {
                Assert.That(switched.Verified, Is.True);
                Assert.That(afterSwitch.Tabs.Single(tab => tab.Selected).Id, Is.EqualTo(goTo.Id),
                    "the strip read again shows the tab named as the active one");
                Assert.That(afterSwitch.Tabs, Has.Count.EqualTo(frame.Tabs.Count), "nothing was closed");
            });
            frame = afterSwitch;
            string said = titles.Select(title => title.Split(' ')[1].ToLowerInvariant())
                .First(word => frame.Tabs.Single(tab => UserBrowserSurface.TitleBears(tab.Title, word)) is { Selected: false });
            string otherThanActive = frame.Tabs.Single(tab => UserBrowserSurface.TitleBears(tab.Title, said)).Title;
            ExternalCapabilityReceipt named = await surface.ControlAsync(
                "browser.control", browser, "close", said, new ExternalEffectBoundary(), CancellationToken.None);
            UserBrowserFrame? afterNamed = await platform.ReadFrameAsync(platform.Window, CancellationToken.None);
            ExternalCapabilityReceipt active = await surface.ControlAsync(
                "browser.control", browser, "close", null, new ExternalEffectBoundary(), CancellationToken.None);
            UserBrowserFrame? afterActive = await platform.ReadFrameAsync(platform.Window, CancellationToken.None);
            TestContext.Out.WriteLine("not found: " + notFound.ErrorCode + " " + notFound.Result);
            TestContext.Out.WriteLine("named «" + said + "»: " + named.Verified + " " + named.Result);
            TestContext.Out.WriteLine("active: " + active.Verified + " " + active.ErrorCode + " " + active.Result);

            Assert.Multiple(() =>
            {
                Assert.That(notFound.ErrorCode, Is.EqualTo(UserBrowserSurface.TabNotFound));
                Assert.That(named.Verified, Is.True);
                Assert.That(named.Result?.GetProperty("closedTab").GetString(), Is.EqualTo(otherThanActive));
                Assert.That(afterNamed?.Tabs.Select(tab => tab.Title), Has.No.Member(otherThanActive),
                    "the strip read again no longer shows the tab named");
                Assert.That(Remaining(named), Is.EqualTo(afterNamed?.Tabs.Select(tab => tab.Title)));
                Assert.That(active.Verified, Is.True);
                Assert.That(afterActive?.Tabs, Has.Count.EqualTo(afterNamed!.Tabs.Count - 1));
                Assert.That(afterNamed.Tabs, Has.Count.EqualTo(frame.Tabs.Count - 1));
                Assert.That(Remaining(active), Is.EqualTo(afterActive?.Tabs.Select(tab => tab.Title)));
            });
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
                catch (UnauthorizedAccessException)
                {
                    await Task.Delay(500);
                }
            }
        }
    }

    private static string[] Remaining(ExternalCapabilityReceipt receipt) =>
        [.. receipt.Result!.Value.GetProperty("remainingTabs").EnumerateArray().Select(title => title.GetString()!)];

    private static async Task<UserBrowserFrame?> ThreeTabsAsync(OwnWindows platform, string[] titles)
    {
        for (int attempt = 0; attempt < 40; attempt++)
        {
            await Task.Delay(500);
            if (platform.ListWindows("msedge") is [var window, ..])
            {
                platform.Window = window.Handle;
                UserBrowserFrame? frame = await platform.ReadFrameAsync(window.Handle, CancellationToken.None);
                TestContext.Out.WriteLine("seen «" + window.Title + "»: " + (frame is null ? "no frame"
                    : frame.TabsComplete + " " + string.Join(" | ", frame.Tabs.Select(tab => tab.Title))));
                // Edge may add a tab of its own (an extension's welcome page) beside the three pages.
                if (frame is { TabsComplete: true }
                    && titles.All(title => frame.Tabs.Count(tab => UserBrowserSurface.TitleBears(tab.Title, title)) == 1))
                {
                    await Task.Delay(1500);
                    return await platform.ReadFrameAsync(window.Handle, CancellationToken.None);
                }
            }
        }
        return null;
    }

    /// <summary>The real platform with its windows narrowed to those of one process: the test's own Edge.</summary>
    internal sealed class OwnWindows(WindowsUserBrowserPlatform real, int processId) : IUserBrowserPlatform
    {
        internal nint Window { get; set; }

        public IReadOnlyList<UserBrowserWindow> ListWindows(string processName) =>
            [.. real.ListWindows(processName)
                .Where(window => VisibleControlSurface.WindowProcess(window.Handle).ProcessId == processId)];

        public UserBrowserIdentity? ResolveDefault() => throw new NotSupportedException();
        public UserBrowserIdentity? ResolveRegistered(string family) => throw new NotSupportedException();
        public void Open(Uri address) => throw new NotSupportedException();
        public void OpenWith(UserBrowserIdentity browser, Uri address) => throw new NotSupportedException();
        public nint FrontWindow() => real.FrontWindow();
        public ValueTask<bool> BringToFrontAsync(nint window, CancellationToken cancellationToken) => real.BringToFrontAsync(window, cancellationToken);
        public ValueTask<IReadOnlyList<UserMediaSession>?> ReadMediaSessionsAsync(CancellationToken cancellationToken) =>
            throw new NotSupportedException();
        public ValueTask<bool> PlayMediaSessionAsync(UserMediaSession session, CancellationToken cancellationToken) =>
            throw new NotSupportedException();
        public ValueTask<string?> ReadAddressAsync(nint window, CancellationToken cancellationToken) =>
            Own(window) ? real.ReadAddressAsync(window, cancellationToken) : throw new InvalidOperationException("not ours");
        public ValueTask<UserBrowserPageStep> StartTitleInPageAsync(
            nint window, string title, bool typeSearch, CancellationToken cancellationToken) => throw new NotSupportedException();

        public ValueTask<UserBrowserFrame?> ReadFrameAsync(nint window, CancellationToken cancellationToken) =>
            Own(window) ? real.ReadFrameAsync(window, cancellationToken) : throw new InvalidOperationException("not ours");

        public bool PostAppCommand(nint window, int command) => Own(window) && real.PostAppCommand(window, command);
        public bool PostBrowserCommand(nint window, int command) => Own(window) && real.PostBrowserCommand(window, command);
        public bool PostMiddleClick(nint window, double x, double y) => Own(window) && real.PostMiddleClick(window, x, y);
        public ValueTask<UserBrowserAct> ActAsync(nint window, string action, CancellationToken cancellationToken) =>
            Own(window) ? real.ActAsync(window, action, cancellationToken) : throw new InvalidOperationException("not ours");
        public ValueTask<UserBrowserAct> SelectTabAsync(nint window, string tabId, CancellationToken cancellationToken) =>
            Own(window) ? real.SelectTabAsync(window, tabId, cancellationToken) : throw new InvalidOperationException("not ours");
        public ValueTask<UserBrowserAct> PressVideoPlayAsync(nint window, Uri page, CancellationToken cancellationToken) =>
            throw new NotSupportedException();
        public bool CoversMonitor(nint window) => Own(window) && real.CoversMonitor(window);
        public ValueTask<UserBrowserPageText?> ReadPageTextAsync(
            nint window, int maximumCharacters, CancellationToken cancellationToken) =>
            Own(window) ? real.ReadPageTextAsync(window, maximumCharacters, cancellationToken) : throw new InvalidOperationException("not ours");
        public ValueTask DelayAsync(TimeSpan delay, CancellationToken cancellationToken) => real.DelayAsync(delay, cancellationToken);

        private bool Own(nint window) => VisibleControlSurface.WindowProcess(window).ProcessId == processId;
    }
}
