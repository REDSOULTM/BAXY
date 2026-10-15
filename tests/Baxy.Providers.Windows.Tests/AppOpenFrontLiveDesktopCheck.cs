using System.Diagnostics;
using System.Runtime.InteropServices;
using Baxy.Providers.Windows.Applications;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// cu-v3-foco-segunda (v3 point 0) on the real desktop: three applications opened one after another by app.open in one
/// process (Bloc de notas, Paint, Calculadora, all three packaged: Windows activates them by themselves), and after
/// each the window that was in front before is in front again, read every 100 ms for 4 s (past the provider's front
/// guard), and the receipt says the hand-back held. Measured 2026-10-08 before the fix: Paint's and Calculadora's
/// hand-backs refused (SetForegroundWindow false with the input attached, error 0) and Bloc de notas taking the front
/// back 30 ms after its own from another of its processes; after it (ForegroundRight): the three held, the first with
/// no bid, Paint with one, Calculadora with one bid and a second try. Never
/// runs in a suite: Explicit and BAXY_CU_FRENTE_LIVE=1, only with the desktop turn (scripts/cu_live/turno.sh); the
/// windows it opens close by their exact process id.
/// </summary>
[TestFixture]
[Explicit("Opens three applications on the person's desktop.")]
[Category("LiveDesktop")]
public sealed class AppOpenFrontLiveDesktopCheck
{
    [Test]
    public async Task EveryOpeningInOneProcessLeavesTheFrontWhereItWas()
    {
        if (Environment.GetEnvironmentVariable("BAXY_CU_FRENTE_LIVE") != "1")
            Assert.Ignore("BAXY_CU_FRENTE_LIVE=1 is needed to touch the desktop.");
        nint front = GetForegroundWindow();
        Assert.That(front, Is.Not.Zero, "a window in front to keep");
        var provider = new WindowsInstalledApplicationOpenProvider();
        var opened = new List<int>();
        var kept = new List<string>();
        try
        {
            foreach (string application in new[] { "Bloc de notas", "Paint", "Calculadora" })
            {
                var watch = Stopwatch.StartNew();
                ApplicationOpenResult result = await provider.OpenAsync(
                    new ApplicationOpenRequest(application, "frente_" + Guid.NewGuid().ToString("N")),
                    CancellationToken.None);
                if (result.ProcessId is > 0 and int id)
                    opened.Add(id);
                var fronts = new List<string>();
                nint after = 0;
                for (int look = 0; look < 40; look++)
                {
                    nint now = GetForegroundWindow();
                    if (now != after)
                    {
                        _ = GetWindowThreadProcessId(now, out uint owner);
                        fronts.Add($"{watch.ElapsedMilliseconds}ms:{now}/{owner}");
                        after = now;
                    }
                    await Task.Delay(100);
                }
                TestContext.Out.WriteLine($"{application}: verified={result.Verified} error={result.ErrorCode} pid={result.ProcessId} "
                    + $"activation={result.WindowsActivation} restored={result.FrontRestored} front {front} then {string.Join(" ", fronts)}");
                // Each opening is judged, and all three run (a refused hand-back on the second must not hide the third).
                if (!result.Verified)
                    kept.Add($"{application}: not verified ({result.ErrorCode})");
                else if (after != front)
                    kept.Add($"{application}: kept the front");
                else if (result.FrontRestored != result.WindowsActivation)
                    kept.Add($"{application}: receipt frontRestored={result.FrontRestored} with windowsActivation={result.WindowsActivation}");
            }

            Assert.That(kept, Is.Empty, "every opening leaves the person's window in front and says so");
        }
        finally
        {
            foreach (int id in opened)
            {
                try
                {
                    using Process process = Process.GetProcessById(id);
                    process.Kill();
                }
                catch (ArgumentException)
                {
                }
            }
        }
    }

    [DllImport("user32.dll")]
    private static extern nint GetForegroundWindow();

    [DllImport("user32.dll")]
    private static extern uint GetWindowThreadProcessId(nint window, out uint processId);
}
