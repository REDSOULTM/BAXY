using System.Diagnostics;
using System.Runtime.InteropServices;
using Baxy.Providers.Windows.Applications;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Renew al máximo (rendimiento): app.open timed on the real desktop with the real provider. The inventory one poll
/// reads, timed for three packaged applications with nothing opened; then cold openings of Bloc de notas, Paint and
/// Calculadora, and «un Bloc de notas nuevo», each timed by a Stopwatch around OpenAsync and closed right after by its
/// window (WM_CLOSE), then by its exact process id. Never runs in a suite: Explicit, and the openings need
/// BAXY_PERF_OPEN_LIVE=1 and none of the three applications running before (BAXY_PERF_OPEN_N rounds, 10 by default).
/// Measured 2026-10-22 on the notebook (N=10), base 9b0eb9ba5 then the one-pass inventory and 150 ms settle looks:
/// one poll's inventory p50 17-22 ms → 4-9 ms; «un Bloc de notas nuevo» p50 8878 → 8474 ms, p90 9151 → 9063 ms.
/// </summary>
[TestFixture]
[Explicit("Times app.open on the person's desktop.")]
[Category("LiveDesktop")]
[NonParallelizable]
public sealed class AppOpenSpeedLiveCheck
{
    private static readonly (string Name, string Aumid, string Process)[] Applications =
    [
        ("Bloc de notas", "Microsoft.WindowsNotepad_8wekyb3d8bbwe!App", "Notepad"),
        ("Paint", "Microsoft.Paint_8wekyb3d8bbwe!App", "mspaint"),
        ("Calculadora", "Microsoft.WindowsCalculator_8wekyb3d8bbwe!App", "CalculatorApp"),
    ];

    private static int Repetitions =>
        int.TryParse(Environment.GetEnvironmentVariable("BAXY_PERF_OPEN_N"), out int n) && n > 0 ? n : 10;

    [Test]
    public void OnePollsInventoryTimes()
    {
        var platform = new WindowsInstalledApplicationPlatform();
        foreach ((string name, string aumid, _) in Applications)
        {
            var entry = new InstalledApplicationEntry(name, aumid);
            _ = platform.Inventory(entry);
            var times = new List<double>();
            for (int read = 0; read < 30; read++)
            {
                var watch = Stopwatch.StartNew();
                _ = platform.Inventory(entry);
                times.Add(watch.Elapsed.TotalMilliseconds);
            }

            TestContext.Out.WriteLine($"inventory {name}: {Summary(times)}");
        }
    }

    [Test]
    public async Task ColdOpeningTimes()
    {
        RequireDesktop();
        var provider = new WindowsInstalledApplicationOpenProvider();
        foreach ((string name, _, string process) in Applications)
        {
            _ = await provider.IsInstalledAsync(name, CancellationToken.None);
            var times = new List<double>();
            int differing = 0;
            for (int round = 0; round < Repetitions; round++)
            {
                RequireNoneRunning(process);
                var watch = Stopwatch.StartNew();
                ApplicationOpenResult result = await provider.OpenAsync(
                    new ApplicationOpenRequest(name, "perf_" + Guid.NewGuid().ToString("N")), CancellationToken.None);
                watch.Stop();
                differing += MainWindowsDiffer();
                await CloseAsync(result, process);
                // An unverified round (the desktop busy with something else) is said, never timed.
                if (result.Verified)
                    times.Add(watch.Elapsed.TotalMilliseconds);
                else
                    TestContext.Out.WriteLine($"{name} round {round}: {result.ErrorCode} after {watch.ElapsedMilliseconds} ms");
                await Task.Delay(500);
            }

            TestContext.Out.WriteLine($"main windows differing from MainWindowHandle with {name} open: {differing}");
            TestContext.Out.WriteLine($"open {name}: {Summary(times)} [{string.Join(' ', times.Select(t => t.ToString("F0", System.Globalization.CultureInfo.InvariantCulture)))}]");
        }
    }

    [Test]
    public async Task ColdNewDocumentTimes()
    {
        RequireDesktop();
        var provider = new WindowsInstalledApplicationOpenProvider();
        (string name, _, string process) = Applications[0];
        _ = await provider.IsInstalledAsync(name, CancellationToken.None);
        var times = new List<double>();
        for (int round = 0; round < Repetitions; round++)
        {
            RequireNoneRunning(process);
            var watch = Stopwatch.StartNew();
            ApplicationOpenResult result = await provider.OpenAsync(
                new ApplicationOpenRequest(name, "perf_" + Guid.NewGuid().ToString("N"), NewDocument: true),
                CancellationToken.None);
            watch.Stop();
            await CloseAsync(result, process);
            if (result.NewDocument)
                times.Add(watch.Elapsed.TotalMilliseconds);
            else
                TestContext.Out.WriteLine($"round {round}: {result.ErrorCode} after {watch.ElapsedMilliseconds} ms");
            await Task.Delay(500);
        }

        TestContext.Out.WriteLine($"new document {name}: {Summary(times)} [{string.Join(' ', times.Select(t => t.ToString("F0", System.Globalization.CultureInfo.InvariantCulture)))}]");
    }

    // Every process's main window by the inventory's one pass against MainWindowHandle, with the opened application on
    // screen: the processes whose window differs in both passes around the per-process reads (a window born or gone
    // in between may differ once).
    private static int MainWindowsDiffer()
    {
        Dictionary<uint, nint> first = WindowsInstalledApplicationPlatform.MainWindowsByProcess();
        var dotnet = new Dictionary<int, nint>();
        foreach (Process process in Process.GetProcesses())
        {
            using (process)
                dotnet[process.Id] = process.MainWindowHandle;
        }

        Dictionary<uint, nint> second = WindowsInstalledApplicationPlatform.MainWindowsByProcess();
        return dotnet.Count(item => item.Value != first.GetValueOrDefault(unchecked((uint)item.Key))
            && item.Value != second.GetValueOrDefault(unchecked((uint)item.Key)));
    }

    private static void RequireDesktop()
    {
        if (Environment.GetEnvironmentVariable("BAXY_PERF_OPEN_LIVE") != "1")
            Assert.Ignore("BAXY_PERF_OPEN_LIVE=1 is needed to touch the desktop.");
    }

    private static void RequireNoneRunning(string process)
    {
        Process[] running = Process.GetProcessesByName(process);
        foreach (Process item in running)
            item.Dispose();
        Assert.That(running, Is.Empty, $"{process} was already running: the check leaves the person's copy alone");
    }

    // The opened window is closed (an unsaved empty document closes without asking); a process that stays is ended
    // by its exact id. Every process of the application is then gone, as before the round.
    private static async Task CloseAsync(ApplicationOpenResult result, string process)
    {
        if (result.WindowHandle is long window)
            _ = PostMessage((nint)window, 0x0010, 0, 0);
        for (int look = 0; look < 50; look++)
        {
            Process[] left = Process.GetProcessesByName(process);
            foreach (Process item in left)
                item.Dispose();
            if (left.Length == 0)
                return;
            if (look % 10 == 9)
            {
                foreach (Process item in Process.GetProcessesByName(process))
                {
                    using (item)
                        _ = item.CloseMainWindow();
                }
            }

            await Task.Delay(100);
        }

        foreach (Process item in Process.GetProcessesByName(process))
        {
            using (item)
            {
                try
                {
                    item.Kill();
                    item.WaitForExit(5000);
                }
                catch (InvalidOperationException)
                {
                }
            }
        }
    }

    private static string Summary(List<double> times)
    {
        if (times.Count == 0)
            return "N=0";
        double[] sorted = [.. times.Order()];
        double At(double quantile) => sorted[Math.Min(sorted.Length - 1, (int)Math.Ceiling(quantile * sorted.Length) - 1)];
        return $"N={sorted.Length} p50={At(0.5):F0} ms p90={At(0.9):F0} ms min={sorted[0]:F0} max={sorted[^1]:F0}";
    }

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool PostMessage(nint window, uint message, nint wParam, nint lParam);
}
