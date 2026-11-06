using System.Diagnostics;
using System.IO;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// Encargo 65 (cosecha F2), on the real desktop, opt-in only (Explicit and BAXY_TAB_LIVE_CHECK=1): a browser of the
/// test's own (a temporary profile, two local pages with invented titles: a notes page in front and a webmail inbox
/// beside it) is read by the App's reader of the tabs (VisibleRows), only that browser's windows, by the process it
/// started. The inbox's tab comes back named by the person's words, as not the one shown, and the result of another
/// application's read says it with the call that reaches it (NetworkEgress.Elsewhere). Nothing is clicked; the
/// process it started is closed by its id, with its tree, and the profile deleted.
/// </summary>
[TestFixture]
[Explicit("Opens a browser window of its own on the person's desktop.")]
public sealed class VisibleRowsBrowserLiveCheck
{
    private const string Notes = "Proyecto Faro - Notas";
    private const string Inbox = "Recibidos (2) - ana@ejemplo.test - Gmail";

    [TestCase(@"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")]
    [TestCase(@"C:\Program Files\Google\Chrome\Application\chrome.exe")]
    public async Task TheTabOfABrowserNamedByThePersonIsReadWithWhetherItIsShown(string browser)
    {
        if (Environment.GetEnvironmentVariable("BAXY_TAB_LIVE_CHECK") != "1")
            Assert.Ignore("BAXY_TAB_LIVE_CHECK=1 is needed to touch the desktop.");
        if (!File.Exists(browser))
            Assert.Ignore("No browser at " + browser);
        string folder = Path.Combine(Path.GetTempPath(), "baxy-pestana-app-" + Guid.NewGuid().ToString("N")[..8]);
        string profile = Path.Combine(folder, "perfil");
        Directory.CreateDirectory(profile);
        string[] pages = [Page(folder, "notas.html", Notes), Page(folder, "bandeja.html", Inbox)];
        HashSet<nint> before = [.. HeartbeatMoment.OtherWindowHandles()];
        Process? started = null;
        try
        {
            var start = new ProcessStartInfo(browser)
            {
                ArgumentList =
                {
                    "--user-data-dir=" + profile, "--no-first-run", "--no-default-browser-check", "--disable-extensions",
                    "--new-window",
                },
                UseShellExecute = false,
            };
            if (string.Equals(Path.GetFileName(browser), "msedge.exe", StringComparison.OrdinalIgnoreCase))
                start.ArgumentList.Add("--inprivate");
            foreach (string page in pages)
                start.ArgumentList.Add(new Uri(page).AbsoluteUri);
            // A fresh profile is never handed to a browser already running: the process started owns the window.
            started = Process.Start(start);

            nint window = 0;
            for (int attempt = 0; attempt < 40 && window == 0; attempt++)
            {
                await Task.Delay(500);
                window = HeartbeatMoment.OtherWindowHandles().FirstOrDefault(handle =>
                    !before.Contains(handle) && HeartbeatMoment.WindowTitle(handle).StartsWith(Notes, StringComparison.Ordinal));
            }

            Assert.That(window, Is.Not.EqualTo((nint)0), "the test's own browser window, the notes page in front");
            await Task.Delay(2000);
            var egress = new NetworkEgress();
            egress.Heard("abre en el Gmail lo último que me mandó Codeberg");
            // The first search may wake the browser's accessibility (said, not asserted); the second is asserted.
            var clock = Stopwatch.StartNew();
            int cold = VisibleRows.Read([window], egress.NamesRow(), egress.NamesTab(), VisibleRows.Budget).Count;
            long coldMs = clock.ElapsedMilliseconds;
            clock.Restart();
            IReadOnlyList<VisibleRow> rows = VisibleRows.Read([window], egress.NamesRow(), egress.NamesTab(), VisibleRows.Budget);
            TestContext.Out.WriteLine($"first read: {cold} in {coldMs} ms; second: {rows.Count} in {clock.ElapsedMilliseconds} ms");

            // Measured 03-11 on the development PC: Chrome showed UI Automation only its frame («Chrome Legacy Window»), no tab strip
            // nor page, to this reader and to input.visible.controls alike; what cannot be read is not measured here.
            TestContext.Out.WriteLine("tabs: " + string.Join(" | ", TabNames(window)));

            if (rows.Count == 0 && TabItems(window) == 0)
                Assert.Inconclusive(Path.GetFileName(browser) + " shows UI Automation no tab of its strip on this PC");
            string title = HeartbeatMoment.WindowTitle(window);
            string? elsewhere = NetworkEgress.Elsewhere("Outlook",
                () => egress.Named([(title, HeartbeatMoment.ProcessOf(window))], rows));
            TestContext.Out.WriteLine($"{Path.GetFileName(browser)} «{title}»: "
                + string.Join(" | ", rows.Select(static row => $"{row.Name} tab={row.Tab} shown={row.Shown}")));
            TestContext.Out.WriteLine("next: " + elsewhere);
            Assert.Multiple(() =>
            {
                Assert.That(rows.Select(static row => (row.Name, row.Tab, row.Shown)).ToArray(),
                    Is.EqualTo(new[] { (Inbox, true, false) }));
                Assert.That(elsewhere, Does.Contain("«" + Inbox + "», not the one shown"));
            });
        }
        finally
        {
            if (started is { HasExited: false })
                started.Kill(entireProcessTree: true);
            started?.Dispose();
            for (int attempt = 0; attempt < 10 && Directory.Exists(folder); attempt++)
            {
                try
                {
                    Directory.Delete(folder, recursive: true);
                }
                catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
                {
                    await Task.Delay(500);
                }
            }
        }
    }

    private static string Page(string folder, string name, string title)
    {
        string path = Path.Combine(folder, name);
        File.WriteAllText(path, $"<!doctype html><html lang=\"es\"><head><meta charset=\"utf-8\"><title>{title}</title>"
            + $"</head><body><h1>{title}</h1></body></html>");
        return path;
    }

    private static int TabItems(nint window) =>
        System.Windows.Automation.AutomationElement.FromHandle(window).FindAll(
            System.Windows.Automation.TreeScope.Descendants,
            new System.Windows.Automation.PropertyCondition(System.Windows.Automation.AutomationElement.ControlTypeProperty,
                System.Windows.Automation.ControlType.TabItem)).Count;

    private static IEnumerable<string> TabNames(nint window) =>
        System.Windows.Automation.AutomationElement.FromHandle(window).FindAll(
            System.Windows.Automation.TreeScope.Descendants,
            new System.Windows.Automation.PropertyCondition(System.Windows.Automation.AutomationElement.ControlTypeProperty,
                System.Windows.Automation.ControlType.TabItem)).Cast<System.Windows.Automation.AutomationElement>()
            .Select(static tab => tab.Current.Name + (tab.TryGetCurrentPattern(
                System.Windows.Automation.SelectionItemPattern.Pattern, out object? pattern)
                && ((System.Windows.Automation.SelectionItemPattern)pattern).Current.IsSelected ? " (shown)" : ""));
}
