using System.Diagnostics;
using System.Runtime.InteropServices;
using Baxy.Providers.Windows.Applications;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// DIAX10B (H-013, vivo en la Radeon): «abre la Calculadora» with hers minimized opened another one, 2 of 2. Live: the
/// test opens a Calculator of its own, minimizes its frame and opens «Calculadora»; the one it opened is reused and shown,
/// no other starts. Explicit: it needs a desktop with no other Calculator open, and ends only the processes it started,
/// by id.
/// </summary>
[TestFixture]
[Explicit("Live: opens and closes a Calculator of its own; needs no other Calculator open")]
public sealed class MinimizedPackagedAppLiveCheck
{
    private const string Calculator = "Microsoft.WindowsCalculator_8wekyb3d8bbwe!App";
    private readonly HashSet<int> _before = [];

    [SetUp]
    public void NoOtherCalculator()
    {
        foreach (Process process in Process.GetProcessesByName("CalculatorApp"))
        {
            _before.Add(process.Id);
            process.Dispose();
        }

        if (_before.Count > 0)
            Assert.Inconclusive("Another Calculator is open: this check would use it.");
    }

    [TearDown]
    public void EndWhatThisStarted()
    {
        foreach (Process process in Process.GetProcessesByName("CalculatorApp"))
        {
            if (!_before.Contains(process.Id))
                process.Kill();
            process.Dispose();
        }
    }

    [Test]
    public async Task AMinimizedCalculatorIsReusedAndShownNeverOpenedAgain()
    {
        using (Process.Start(new ProcessStartInfo("explorer.exe", "shell:AppsFolder\\" + Calculator)))
        {
        }

        int calculator = 0;
        for (int i = 0; i < 40 && calculator == 0; i++)
        {
            await Task.Delay(500);
            calculator = Running().FirstOrDefault();
        }

        Assert.That(calculator, Is.Not.Zero, "the Calculator did not start");
        await Task.Delay(2500);
        nint frame = FrameOf(calculator);
        Assert.That(frame, Is.Not.Zero, "no frame shows the Calculator");
        _ = ShowWindow(frame, 6); // SW_MINIMIZE
        await Task.Delay(2500);
        Assert.That(IsIconic(frame), Is.True);

        ApplicationOpenResult result = await new WindowsInstalledApplicationOpenProvider().OpenAsync(
            new ApplicationOpenRequest("Calculadora", Guid.NewGuid().ToString("D"), Foreground: false),
            CancellationToken.None);
        await Task.Delay(1500);

        TestContext.Out.WriteLine($"{result.Succeeded} {result.Verified} {result.ErrorCode} reused={result.AlreadyRunning}"
            + $" window={result.WindowHandle} frame={frame} running={string.Join(",", Running())}");
        Assert.Multiple(() =>
        {
            Assert.That(result.Verified, Is.True);
            Assert.That(result.AlreadyRunning, Is.True);
            Assert.That(Running(), Is.EqualTo(new[] { calculator }));
            Assert.That(IsIconic(frame), Is.False);
        });
    }

    private int[] Running()
    {
        Process[] processes = Process.GetProcessesByName("CalculatorApp");
        try
        {
            return [.. processes.Select(static process => process.Id).Where(id => !_before.Contains(id)).Order()];
        }
        finally
        {
            foreach (Process process in processes)
                process.Dispose();
        }
    }

    private static nint FrameOf(int process)
    {
        nint found = 0;
        EnumWindowsProc frames = (window, unusedFrame) =>
        {
            EnumWindowsProc children = (child, unusedChild) =>
            {
                _ = GetWindowThreadProcessId(child, out uint owner);
                if (owner == process)
                    found = window;
                return found == 0;
            };
            _ = EnumChildWindows(window, children, 0);
            GC.KeepAlive(children);
            return found == 0;
        };
        _ = EnumWindows(frames, 0);
        GC.KeepAlive(frames);
        return found;
    }

    private delegate bool EnumWindowsProc(nint window, nint parameter);

    [DllImport("user32.dll")]
    private static extern bool EnumWindows(EnumWindowsProc callback, nint parameter);

    [DllImport("user32.dll")]
    private static extern bool EnumChildWindows(nint parent, EnumWindowsProc callback, nint parameter);

    [DllImport("user32.dll")]
    private static extern uint GetWindowThreadProcessId(nint window, out uint process);

    [DllImport("user32.dll")]
    private static extern bool ShowWindow(nint window, int command);

    [DllImport("user32.dll")]
    private static extern bool IsIconic(nint window);
}
