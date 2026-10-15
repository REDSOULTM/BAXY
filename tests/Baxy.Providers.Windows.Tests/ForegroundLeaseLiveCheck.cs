using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// The pause rule on the real desktop, opt-in only (Explicit and BAXY_PAUSE_LIVE_CHECK=1): two WinForms windows of
/// the test's own (a «person» window in front and a «mission» window behind it), the real pause detector and the
/// real lease. Checks that Raw Input hands back each event's mark (BAXY's is BAXY's, another is the person's), that
/// keys typed in a burst land in the mission window only, and that the front and the cursor are given back exactly.
/// The mouse events injected to check the detector are zero moves (the cursor does not move); both windows are
/// closed by their exact process id.
/// </summary>
[TestFixture]
[Explicit("Brings windows of its own to the front and types into one of them.")]
public sealed class ForegroundLeaseLiveCheck
{
    [Test]
    public async Task TheBurstTypesInTheMissionWindowAndGivesTheFrontAndTheCursorBack()
    {
        if (Environment.GetEnvironmentVariable("BAXY_PAUSE_LIVE_CHECK") != "1")
            Assert.Ignore("Set BAXY_PAUSE_LIVE_CHECK=1 to run the live check.");
        string tag = Guid.NewGuid().ToString("N")[..8];
        using Process person = OpenForm("BAXY pausa persona " + tag, 80, 80);
        using Process mission = OpenForm("BAXY pausa mision " + tag, 560, 80);
        try
        {
            nint personWindow = await MainWindowAsync(person);
            nint missionWindow = await MainWindowAsync(mission);
            Assert.That(personWindow, Is.Not.Zero);
            Assert.That(missionWindow, Is.Not.Zero);
            Assert.That(VisibleControlSurface.BringToFront(personWindow), Is.True, "the person's window in front");

            // The detector: a marked zero move is BAXY's, an unmarked one (the simulated user's mark) the person's.
            WindowsUserInputPause pause = WindowsUserInputPause.Shared;
            Assert.That(pause.Source, Is.EqualTo("raw_input"));
            await Task.Delay(300);
            long foreignBefore = pause.LastForeignInputMs;
            Assert.That(ZeroMove(BaxyInputMark.Value), Is.EqualTo(1u));
            await Task.Delay(250);
            long afterOwn = pause.LastForeignInputMs;
            Assert.That(ZeroMove(0x12345678), Is.EqualTo(1u));
            await Task.Delay(250);
            long afterForeign = pause.LastForeignInputMs;
            TestContext.Out.WriteLine($"foreign before {foreignBefore}, after own {afterOwn}, after foreign {afterForeign}, missed {pause.Missed}");
            Assert.That(afterOwn, Is.EqualTo(foreignBefore), "BAXY's marked move is not the person's");
            Assert.That(afterForeign, Is.GreaterThan(foreignBefore), "an unmarked move is the person's");

            // Keys: a burst on the mission window, typed only there, and the front given back.
            (int X, int Y) cursor = new WindowsLeaseDesktop().Cursor();
            var keyboard = new WindowsDesktopKeyboard();
            var watch = Stopwatch.StartNew();
            IInputBurst burst = await keyboard.FrontAsync(missionWindow, CancellationToken.None);
            Assert.That(burst.MayAct, Is.True, burst.Refusal ?? "the person acted");
            Assert.That(keyboard.Holds(missionWindow), Is.True);
            uint accepted = keyboard.TypeText("hola", () => burst.MayAct && keyboard.Holds(missionWindow));
            await keyboard.SettleAsync(CancellationToken.None);
            bool restored = burst.Restore();
            long burstMs = watch.ElapsedMilliseconds;
            TestContext.Out.WriteLine($"keys: waited {burst.WaitedMs} ms, burst {burstMs} ms, restored {restored}");
            Assert.Multiple(() =>
            {
                Assert.That(accepted, Is.EqualTo(8u));
                Assert.That(restored, Is.True);
                Assert.That(VisibleControlSurface.ForegroundIs(personWindow), Is.True, "the person's window is back in front");
                Assert.That(new WindowsLeaseDesktop().Cursor(), Is.EqualTo(cursor));
                Assert.That(EditText(missionWindow), Is.EqualTo("hola"));
                Assert.That(EditText(personWindow), Is.Empty, "nothing typed in the person's window");
            });

            // A click: the cursor goes to the mission window and comes back where it was.
            IInputBurst click = await ForegroundLease.Shared.AcquireAsync(missionWindow, CancellationToken.None);
            Assert.That(click.MayAct, Is.True, click.Refusal ?? "the person acted");
            Assert.That(GetWindowRect(missionWindow, out Rect bounds), Is.True);
            bool clicked = VisibleControlSurface.Click(click, (bounds.Left + bounds.Right) / 2, (bounds.Top + bounds.Bottom) / 2);
            bool clickRestored = click.Restore();
            Assert.Multiple(() =>
            {
                Assert.That(clicked, Is.True);
                Assert.That(clickRestored, Is.True);
                Assert.That(VisibleControlSurface.ForegroundIs(personWindow), Is.True);
                Assert.That(new WindowsLeaseDesktop().Cursor(), Is.EqualTo(cursor));
            });
        }
        finally
        {
            Close(person);
            Close(mission);
        }
    }

    // Review of interrupcion-fantasma (bloqueante): BAXY's own Unicode keys never reach Raw Input, and a text longer
    // than about 7 characters was taken for the person's typing and cut. A long text goes whole, and neither during it
    // nor half a second after it does the detector count BAXY's keys as the person's.
    [Test]
    public async Task ALongTextOfBaxysOwnUnicodeKeysGoesWholeAndIsNeverThePersons()
    {
        if (Environment.GetEnvironmentVariable("BAXY_PAUSE_LIVE_CHECK") != "1")
            Assert.Ignore("Set BAXY_PAUSE_LIVE_CHECK=1 to run the live check.");
        const string text = "hola, esto es un texto largo de BAXY: ñandú 123";
        string tag = Guid.NewGuid().ToString("N")[..8];
        using Process person = OpenForm("BAXY pausa persona " + tag, 80, 80);
        using Process mission = OpenForm("BAXY pausa mision " + tag, 560, 80);
        try
        {
            nint personWindow = await MainWindowAsync(person);
            nint missionWindow = await MainWindowAsync(mission);
            Assert.That(personWindow, Is.Not.Zero);
            Assert.That(missionWindow, Is.Not.Zero);
            Assert.That(VisibleControlSurface.BringToFront(personWindow), Is.True, "the person's window in front");
            WindowsUserInputPause pause = WindowsUserInputPause.Shared;
            Assert.That(pause.Source, Is.EqualTo("raw_input"));
            await Task.Delay(300);
            long foreignBefore = pause.LastForeignInputMs;
            long missedBefore = pause.Missed;

            var keyboard = new WindowsDesktopKeyboard();
            IInputBurst burst = await keyboard.FrontAsync(missionWindow, CancellationToken.None);
            Assert.That(burst.MayAct, Is.True, burst.Refusal ?? "the person acted");
            uint accepted = keyboard.TypeText(text, () => burst.MayAct && keyboard.Holds(missionWindow));
            await keyboard.SettleAsync(CancellationToken.None);
            bool restored = burst.Restore();
            await Task.Delay(500);
            bool actedAfter = burst.UserActed;
            long foreignAfter = pause.LastForeignInputMs;
            TestContext.Out.WriteLine(
                $"accepted {accepted}, foreign {foreignBefore}->{foreignAfter}, missed {missedBefore}->{pause.Missed}");
            Assert.Multiple(() =>
            {
                Assert.That(accepted, Is.EqualTo((uint)text.Length * 2));
                Assert.That(restored, Is.True);
                Assert.That(EditText(missionWindow), Is.EqualTo(text));
                Assert.That(EditText(personWindow), Is.Empty, "nothing typed in the person's window");
                Assert.That(foreignAfter, Is.EqualTo(foreignBefore), "BAXY's Unicode keys are not the person's");
                Assert.That(actedAfter, Is.False);
            });
        }
        finally
        {
            Close(person);
            Close(mission);
        }
    }

    // Review r2 of interrupcion-fantasma (importante): after the front went back, the person's cursor crossing the
    // mission's window between two reads (and leaving it) still stops the burst; moves only inside their own window do
    // not. The person's moves are injected with the simulated user's mark, absolute, in small steps.
    [Test]
    public async Task ThePersonsCursorCrossingTheMissionsWindowAfterTheFrontWentBackStopsTheBurst()
    {
        if (Environment.GetEnvironmentVariable("BAXY_PAUSE_LIVE_CHECK") != "1")
            Assert.Ignore("Set BAXY_PAUSE_LIVE_CHECK=1 to run the live check.");
        string tag = Guid.NewGuid().ToString("N")[..8];
        // Narrow and stacked at the right edge of the screen, out of the way of a window kept on top at the left.
        int left = GetSystemMetrics(0) - 270;
        using Process person = OpenForm("BAXY pausa persona " + tag, left, 40, 260, 280);
        using Process mission = OpenForm("BAXY pausa mision " + tag, left, 400, 260, 280);
        (int X, int Y) original = new WindowsLeaseDesktop().Cursor();
        try
        {
            nint personWindow = await MainWindowAsync(person);
            nint missionWindow = await MainWindowAsync(mission);
            // The mission's window right under the person's, over any other window (a pass only changes what it
            // draws where it is seen).
            Assert.That(VisibleControlSurface.BringToFront(missionWindow), Is.True);
            Assert.That(VisibleControlSurface.BringToFront(personWindow), Is.True, "the person's window in front");
            Assert.That(GetWindowRect(personWindow, out Rect own), Is.True);
            Assert.That(GetWindowRect(missionWindow, out Rect theirs), Is.True);
            (int X, int Y) home = ((own.Left + own.Right) / 2, (own.Top + own.Bottom) / 2);
            (int X, int Y) over = ((theirs.Left + theirs.Right) / 2, (theirs.Top + theirs.Bottom) / 2);
            await MoveAsync(home, home);

            IInputBurst burst = await ForegroundLease.Shared.AcquireAsync(missionWindow, CancellationToken.None);
            Assert.That(burst.MayAct, Is.True, burst.Refusal ?? "the person acted");
            Assert.That(burst.Restore(), Is.True);
            Rect shown = VisibleControlSurface.InPhysicalPixels(() => GetWindowRect(missionWindow, out Rect r) ? r : default);
            if (!VisibleControlSurface.PointShows(missionWindow, (shown.Left + shown.Right) / 2, (shown.Top + shown.Bottom) / 2))
                Assert.Inconclusive("another window kept on top covers the mission's window: no pass over it can be made");

            await MoveAsync(home, (home.X + 60, home.Y + 30));
            await MoveAsync((home.X + 60, home.Y + 30), home);
            await Task.Delay(60);
            bool inOwnWindow = burst.UserActed;

            await MoveAsync(home, over);
            await MoveAsync(over, home);
            await Task.Delay(60);
            bool crossed = burst.UserActed;
            WindowsUserInputPause pause = WindowsUserInputPause.Shared;
            TestContext.Out.WriteLine(
                $"own window only: {inOwnWindow}, crossed: {crossed}; now {Environment.TickCount64}, over mission "
                + $"{pause.LastPointerOverMs(missionWindow)}, over person {pause.LastPointerOverMs(personWindow)}, "
                + $"missed {pause.Missed}");
            Assert.Multiple(() =>
            {
                Assert.That(VisibleControlSurface.ForegroundIs(personWindow), Is.True, "their window still in front");
                Assert.That(inOwnWindow, Is.False, "moves inside their own window do not reach the mission's");
                Assert.That(crossed, Is.True, "a pass over the mission's window does");
            });
        }
        finally
        {
            _ = new WindowsLeaseDesktop().SetCursor(original.X, original.Y);
            Close(person);
            Close(mission);
        }
    }

    // The simulated person's mouse: absolute moves over the virtual desktop in 12 steps of 15 ms, with its own mark.
    private static async Task MoveAsync((int X, int Y) from, (int X, int Y) to)
    {
        int left = GetSystemMetrics(76);
        int top = GetSystemMetrics(77);
        int width = Math.Max(2, GetSystemMetrics(78));
        int height = Math.Max(2, GetSystemMetrics(79));
        for (int step = 1; step <= 12; step++)
        {
            int x = from.X + (to.X - from.X) * step / 12;
            int y = from.Y + (to.Y - from.Y) * step / 12;
            var input = new Input[1];
            input[0].Type = 0;
            input[0].Mouse.X = (int)((long)(x - left) * 65535 / (width - 1));
            input[0].Mouse.Y = (int)((long)(y - top) * 65535 / (height - 1));
            input[0].Mouse.Flags = 0x0001 | 0x4000 | 0x8000;
            input[0].Mouse.ExtraInfo = 0x12345678;
            _ = SendInput(1, input, Marshal.SizeOf<Input>());
            await Task.Delay(15);
        }
    }

    [DllImport("user32.dll")]
    private static extern int GetSystemMetrics(int index);

    private static Process OpenForm(string title, int left, int top, int width = 420, int height = 220)
    {
        string script =
            "Add-Type -AssemblyName System.Windows.Forms;" +
            "$f=New-Object System.Windows.Forms.Form;$f.Text='" + title + "';$f.StartPosition='Manual';" +
            "$f.Left=" + left + ";$f.Top=" + top + ";$f.Width=" + width + ";$f.Height=" + height + ";" +
            "$t=New-Object System.Windows.Forms.TextBox;$t.Multiline=$true;$t.Dock='Fill';$f.Controls.Add($t);" +
            "[System.Windows.Forms.Application]::Run($f)";
        var start = new ProcessStartInfo("powershell.exe")
        {
            UseShellExecute = false,
            CreateNoWindow = true,
        };
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

    private static string EditText(nint form)
    {
        nint edit = FindWindowExW(form, 0, null, null);
        var buffer = new char[256];
        int length = (int)SendMessageW(edit, 0x000D, buffer.Length, buffer);
        return new string(buffer, 0, Math.Max(0, length));
    }

    private static uint ZeroMove(uint extra)
    {
        var input = new Input[1];
        input[0].Type = 0;
        input[0].Mouse.Flags = 0x0001;
        input[0].Mouse.ExtraInfo = extra;
        return SendInput(1, input, Marshal.SizeOf<Input>());
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct Rect
    {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }

    // A mouse record: the largest member of the native union, so the record has the native size (40 bytes on x64).
    [StructLayout(LayoutKind.Sequential)]
    private struct Input
    {
        public uint Type;
        public MouseInput Mouse;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct MouseInput
    {
        public int X;
        public int Y;
        public uint Data;
        public uint Flags;
        public uint Time;
        public nuint ExtraInfo;
    }

    [DllImport("user32.dll")]
    private static extern uint SendInput(uint count, [In] Input[] inputs, int size);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern IntPtr FindWindowExW(IntPtr parent, IntPtr after, string? className, string? title);

    [DllImport("user32.dll", EntryPoint = "SendMessageW", CharSet = CharSet.Unicode)]
    private static extern IntPtr SendMessageW(IntPtr window, uint message, IntPtr wParam, [Out] char[] buffer);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool GetWindowRect(IntPtr window, out Rect rect);
}
