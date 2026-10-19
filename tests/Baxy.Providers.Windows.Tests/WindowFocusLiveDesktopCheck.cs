using System.Diagnostics;
using System.Runtime.InteropServices;
using Baxy.Providers.Windows.Applications;
using Baxy.Providers.Windows.External;
using Baxy.Providers.Windows.Windows;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// The three ways BAXY brings a window to the front, on the real desktop and from a process that is not in front (as
/// Baxy.Core): app.open asked in front (Bloc de notas, with Calculadora opened behind), window.focus to Calculadora, to
/// Bloc de notas and to Calculadora again, and the bringing up before typing into a named window
/// (VisibleControlSurface.BringToFront) to each, all read back with GetForegroundWindow. Measured 2026-10-19 before the
/// fix: with GameInputSvc in front, window.focus to Bloc de notas action_failed and its bringing up refused; from a
/// clean front, the bringing up reported refused with Bloc de notas already in front (read back once, too early).
/// After it: the six took the front. Seen in the e2e on 2026-10-19: with an invisible window of GameInputSvc in front (after
/// Steam) every app.open in front ended behind it, every window.focus failed with action_failed (17 of 17 in one run)
/// and typing into the opened window failed with input_window_not_in_front: the three used a SetForegroundWindow
/// refused once this process used its right; they now win it as a hand-back does (ForegroundRight). Never runs in a
/// suite: Explicit and BAXY_CU_FRENTE_LIVE=1, only while no one uses the desktop; the window it opens closes by its
/// exact process id.
/// </summary>
[TestFixture]
[Explicit("Opens Bloc de notas and moves the front on the person's desktop.")]
[Category("LiveDesktop")]
public sealed class WindowFocusLiveDesktopCheck
{
    [Test]
    public async Task EveryWayToTheFrontInOneProcessTakesIt()
    {
        if (Environment.GetEnvironmentVariable("BAXY_CU_FRENTE_LIVE") != "1")
            Assert.Ignore("BAXY_CU_FRENTE_LIVE=1 is needed to touch the desktop.");
        nint front = GetForegroundWindow();
        Assert.That(front, Is.Not.Zero, "a window in front to come back to");
        _ = GetWindowThreadProcessId(front, out uint frontOwner);
        TestContext.Out.WriteLine($"front at the start: {front} of {ProcessName(frontOwner)}");
        var applications = new WindowsInstalledApplicationOpenProvider();
        var windows = new WindowsWindowControlProvider(applications);
        var opened = new List<int>();
        var refused = new List<string>();
        try
        {
            // A second window to move the front to (the one in front may be invisible, as GameInputSvc's was).
            ApplicationOpenResult other = await applications.OpenAsync(
                new ApplicationOpenRequest("Calculadora", "foco_" + Guid.NewGuid().ToString("N")), CancellationToken.None);
            if (other.ProcessId is > 0 and int otherId)
                opened.Add(otherId);
            Assert.That(other.Verified, Is.True, $"Calculadora opened ({other.ErrorCode})");
            nint calculatorWindow = (nint)other.WindowHandle!.Value;
            ApplicationOpenResult open = await applications.OpenAsync(
                new ApplicationOpenRequest("Bloc de notas", "foco_" + Guid.NewGuid().ToString("N"), Foreground: true),
                CancellationToken.None);
            if (open.ProcessId is > 0 and int openId)
                opened.Add(openId);
            Assert.That(open.Verified, Is.True, $"Bloc de notas opened ({open.ErrorCode})");
            nint notesWindow = (nint)open.WindowHandle!.Value;
            await Task.Delay(1500);
            Judge("app.open in front", notesWindow, refused, verified: true);

            foreach ((string name, nint window) in new[] { ("window.focus to Calculadora", calculatorWindow), ("window.focus to Bloc de notas", notesWindow), ("window.focus to Calculadora again", calculatorWindow) })
            {
                string? windowId = windows.IssueFor(window);
                Assert.That(windowId, Is.Not.Null, $"{name}: the window is on the desktop");
                WindowActionResult result = await windows.ExecuteAsync(windowId!, WindowControlAction.Focus, CancellationToken.None);
                await Task.Delay(300);
                Judge($"{name} (error={result.ErrorCode})", window, refused, result.Verified);
            }

            foreach ((string name, nint window) in new[] { ("bringing up to type into Bloc de notas", notesWindow), ("bringing up to type into Calculadora", calculatorWindow) })
            {
                bool held = VisibleControlSurface.BringToFront(window);
                await Task.Delay(300);
                Judge(name, window, refused, held);
            }

            Assert.That(refused, Is.Empty, "every way to the front takes it and says so");
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

    private static void Judge(string name, nint wanted, List<string> refused, bool verified)
    {
        nint now = GetForegroundWindow();
        _ = GetWindowThreadProcessId(now, out uint owner);
        TestContext.Out.WriteLine($"{name}: verified={verified} front {now} of {ProcessName(owner)} (wanted {wanted})");
        if (!verified || now != wanted)
            refused.Add($"{name}: verified={verified} front={now} of {ProcessName(owner)}");
    }

    private static string ProcessName(uint id)
    {
        try
        {
            using Process process = Process.GetProcessById(checked((int)id));
            return process.ProcessName;
        }
        catch (ArgumentException)
        {
            return "?";
        }
    }

    [DllImport("user32.dll")]
    private static extern nint GetForegroundWindow();

    [DllImport("user32.dll")]
    private static extern uint GetWindowThreadProcessId(nint window, out uint processId);
}
