using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Rows C14 and C4 on the real desktop, opt-in only (Explicit and BAXY_KEYS_LIVE_CHECK=1): the real keyboard and lease on
/// windows the check opens itself, closed by their own handle or process id. Nothing is ever sent unless the window of the
/// check holds the front.
/// </summary>
[TestFixture]
[Explicit("Opens windows of its own, brings them to the front and types into them.")]
public sealed class KeysLiveDesktopCheck
{
    private const string Emoji = "\U0001F600";

    // Row C14: the question that comes after a pair stops the text with the whole character in a real field; the same stop
    // between the halves (what the keyboard did before) leaves what the second arm prints.
    [Test]
    public async Task ATextStoppedAfterAPairLeavesTheWholeCharacter()
    {
        Live();
        string tag = Guid.NewGuid().ToString("N")[..8];
        using Process form = OpenForm("BAXY pares " + tag);
        try
        {
            nint window = await MainWindowAsync(form);
            Assert.That(window, Is.Not.Zero);
            await TakeFrontAsync(window);
            await Task.Delay(500);
            nint edit = FindWindowExW(window, 0, null, null);
            var keyboard = new WindowsDesktopKeyboard();

            int asked = 0;
            uint accepted = keyboard.TypeText("a" + Emoji + "b", () => ++asked <= 2 && VisibleControlSurface.ForegroundIs(window));
            await Task.Delay(300);
            string whole = Text(edit);
            TestContext.Out.WriteLine($"parado tras el par: «{Units(whole)}», aceptados {accepted}");

            SetText(edit, string.Empty);
            uint half = keyboard.TypeText("a\uD83D", () => VisibleControlSurface.ForegroundIs(window));
            await Task.Delay(300);
            string cut = Text(edit);
            TestContext.Out.WriteLine($"parado entre mitades (lo de antes): «{Units(cut)}», aceptados {half}");

            Assert.Multiple(() =>
            {
                Assert.That(whole, Is.EqualTo("a" + Emoji));
                Assert.That(accepted, Is.EqualTo(6u));
            });
        }
        finally
        {
            Close(form);
        }
    }

    // Row C4: BAXY's own bench lost the first key on a window just brought up («125+75» → «25+75», on the Calculator, an
    // application inside a frame of another process). Ten tries of each arm, in turns: the keys right after the bringing,
    // and the keys in a burst of the lease, on the Calculator the check opens.
    [Test]
    public async Task TheFirstKeyOnAWindowJustBroughtUp()
    {
        Live();
        string tag = Guid.NewGuid().ToString("N")[..8];
        using Process form = OpenForm("BAXY bloqueo " + tag);
        nint[] before = FramesNow();
        using Process? launcher = Process.Start(new ProcessStartInfo("calc.exe") { UseShellExecute = true });
        nint calculator = 0;
        try
        {
            nint blocker = await MainWindowAsync(form);
            Assert.That(blocker, Is.Not.Zero);
            await TakeFrontAsync(blocker);
            for (int attempt = 0; attempt < 100 && calculator == 0; attempt++)
            {
                await Task.Delay(100);
                calculator = FramesNow().Except(before).FirstOrDefault();
            }

            Assert.That(calculator, Is.Not.Zero, "the check's own Calculator");
            await Task.Delay(1500);
            var keyboard = new WindowsDesktopKeyboard();
            var desktop = new WindowsLeaseDesktop();
            var counts = new Dictionary<string, (int Whole, int Lost, int Void)> { ["sin espera"] = default, ["ráfaga"] = default };
            var waits = new List<long>();
            int notConfirmed = 0;
            foreach (bool burst in Enumerable.Range(0, 20).Select(index => index % 2 == 1))
            {
                string arm = burst ? "ráfaga" : "sin espera";
                (int whole, int lost, int voided) = counts[arm];
                // The display cleared with its own window in front, then the other window on top of it.
                if (!VisibleControlSurface.BringToFront(calculator))
                {
                    counts[arm] = (whole, lost, voided + 1);
                    continue;
                }

                await Task.Delay(250);
                _ = keyboard.PressChord([0x1B], () => VisibleControlSurface.ForegroundIs(calculator));
                await Task.Delay(150);
                if (!VisibleControlSurface.BringToFront(blocker))
                {
                    counts[arm] = (whole, lost, voided + 1);
                    continue;
                }

                await Task.Delay(400);
                bool stays() => VisibleControlSurface.ForegroundIs(calculator);
                uint accepted;
                if (burst)
                {
                    var watch = Stopwatch.StartNew();
                    IInputBurst held = await ForegroundLease.Shared.AcquireForKeysAsync(calculator, CancellationToken.None);
                    waits.Add(watch.ElapsedMilliseconds);
                    if (held.KeysNotConfirmed)
                        notConfirmed++;
                    accepted = held.MayAct ? keyboard.TypeText("12", stays) : 0;
                    await Task.Delay(120);
                    _ = held.Restore();
                }
                else
                {
                    _ = desktop.BringToFront(calculator);
                    accepted = keyboard.TypeText("12", stays);
                    await Task.Delay(120);
                }

                if (accepted != 4)
                {
                    counts[arm] = (whole, lost, voided + 1);
                    continue;
                }

                string display = await CalculatorDisplayAsync(calculator);
                TestContext.Out.WriteLine($"{arm}: «{display}»");
                counts[arm] = display.Contains("12", StringComparison.Ordinal) ? (whole + 1, lost, voided) : (whole, lost + 1, voided);
            }

            foreach ((string arm, (int whole, int lost, int voided)) in counts)
                TestContext.Out.WriteLine($"{arm}: enteras {whole}, perdidas {lost}, anuladas {voided}");
            TestContext.Out.WriteLine($"ráfaga: keysNotConfirmed {notConfirmed}; ms hasta la ráfaga: {string.Join(' ', waits)}");
        }
        finally
        {
            if (calculator != 0 && IsWindow(calculator))
                _ = PostMessageW(calculator, 0x0010, 0, 0);
            Close(form);
        }
    }

    // The check's own window first: a window of a service in front (GameInputSvc, seen on this PC) refuses the usual bid.
    private static async Task TakeFrontAsync(nint window)
    {
        if (!VisibleControlSurface.BringToFront(window))
        {
            SwitchToThisWindow(window, true);
            await Task.Delay(300);
        }

        Assert.That(VisibleControlSurface.ForegroundIs(window), Is.True, "the check's own window in front");
    }

    private static void Live()
    {
        if (Environment.GetEnvironmentVariable("BAXY_KEYS_LIVE_CHECK") != "1")
            Assert.Ignore("Set BAXY_KEYS_LIVE_CHECK=1 to run the live check.");
    }

    private static string Units(string text) =>
        string.Concat(text.Select(unit => char.IsSurrogate(unit) ? $"\\u{(int)unit:X4}" : unit.ToString()));

    // What the Calculator's display says, read by UI Automation in a PowerShell of its own (no window, no input).
    private static async Task<string> CalculatorDisplayAsync(nint window)
    {
        string script =
            "Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes;" +
            "[Console]::OutputEncoding=New-Object System.Text.UTF8Encoding($false);" +
            "$AE=[System.Windows.Automation.AutomationElement];" +
            "$r=$AE::FromHandle([IntPtr]" + (long)window + ");" +
            "$d=$r.FindFirst([System.Windows.Automation.TreeScope]::Descendants,(New-Object System.Windows.Automation.PropertyCondition($AE::AutomationIdProperty,'CalculatorResults')));" +
            "if($d){[Console]::Out.Write($d.Current.Name)}";
        var start = new ProcessStartInfo("powershell.exe")
        {
            RedirectStandardOutput = true,
            UseShellExecute = false,
            CreateNoWindow = true,
            StandardOutputEncoding = Encoding.UTF8,
        };
        foreach (string argument in new[] { "-NoProfile", "-NonInteractive", "-Command", script })
            start.ArgumentList.Add(argument);
        using Process reader = Process.Start(start)!;
        string output = ChildOutput.Read(reader);
        await reader.WaitForExitAsync();
        return output;
    }

    private static nint[] FramesNow()
    {
        var frames = new List<nint>();
        _ = EnumWindows((window, _) =>
        {
            var name = new char[64];
            int length = GetClassNameW(window, name, name.Length);
            if (new string(name, 0, length) == "ApplicationFrameWindow" && IsWindowVisible(window))
                frames.Add(window);
            return true;
        }, 0);
        return [.. frames];
    }

    private static Process OpenForm(string title)
    {
        string script =
            "Add-Type -AssemblyName System.Windows.Forms;" +
            "$f=New-Object System.Windows.Forms.Form;$f.Text='" + title + "';$f.StartPosition='Manual';" +
            "$f.Left=80;$f.Top=80;$f.Width=420;$f.Height=240;" +
            "$t=New-Object System.Windows.Forms.TextBox;$t.Multiline=$true;$t.Dock='Fill';$f.Controls.Add($t);" +
            "[System.Windows.Forms.Application]::Run($f)";
        var start = new ProcessStartInfo("powershell.exe") { UseShellExecute = false, CreateNoWindow = true };
        foreach (string argument in new[] { "-NoProfile", "-NonInteractive", "-Command", script })
            start.ArgumentList.Add(argument);
        return Process.Start(start) ?? throw new InvalidOperationException("powershell did not start");
    }

    private static async Task<nint> MainWindowAsync(Process process)
    {
        for (int attempt = 0; attempt < 100; attempt++)
        {
            process.Refresh();
            if (process.MainWindowHandle != 0)
                return process.MainWindowHandle;
            await Task.Delay(100);
        }

        return 0;
    }

    private static void Close(Process process)
    {
        try
        {
            if (!process.HasExited)
                process.Kill();
        }
        catch (InvalidOperationException)
        {
        }
    }

    private static string Text(nint edit)
    {
        var buffer = new char[256];
        int length = (int)GetText(edit, 0x000D, buffer.Length, buffer);
        return new string(buffer, 0, Math.Max(0, length));
    }

    private static void SetText(nint edit, string text) => _ = SetTextW(edit, 0x000C, 0, text);

    private delegate bool EnumProc(nint window, nint value);

    [DllImport("user32.dll")]
    private static extern void SwitchToThisWindow(nint window, [MarshalAs(UnmanagedType.Bool)] bool altTab);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool EnumWindows(EnumProc callback, nint value);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern int GetClassNameW(nint window, [Out] char[] name, int count);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool IsWindowVisible(nint window);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool IsWindow(nint window);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool PostMessageW(nint window, uint message, nint wParam, nint lParam);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern nint FindWindowExW(nint parent, nint after, string? className, string? title);

    [DllImport("user32.dll", EntryPoint = "SendMessageW", CharSet = CharSet.Unicode)]
    private static extern nint GetText(nint window, uint message, nint wParam, [Out] char[] buffer);

    [DllImport("user32.dll", EntryPoint = "SendMessageW", CharSet = CharSet.Unicode)]
    private static extern nint SetTextW(nint window, uint message, nint wParam, string text);
}
