using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// The primitives of the round-1 pending list on the real desktop, opt-in only (Explicit and BAXY_MOLESTIA_LIVE=1),
/// meant to run while the harness's annoyance meter (scripts/cu_live/molestia/medidor.py) types in its own window:
/// with BAXY_MOLESTIA_PERSON_FOREGROUND=1 the window in front when the test starts (the meter's simulated user) is
/// the person's; otherwise the test opens one. Every other window is the test's own (WinForms forms closed by their
/// exact process id), and every key BAXY sends goes to them:
/// <list type="number">
/// <item>a click right after an opening, on the opened window behind the person's, pressed by its accessible tree:
/// the person's window never leaves the front (fix 1);</item>
/// <item>a flow of keys inside a lease burst, as the messaging and Steam clients now send them (LeasedInput): typed
/// only in the mission's window, the front and the cursor given back (fix 3);</item>
/// <item>a helper burst, as the calculator, quick-switcher and Spotify scripts now run: the helper brings its own
/// window up and types there, and the lease gives the front and the cursor back.</item>
/// </list>
/// </summary>
[TestFixture]
[Explicit("Brings windows of its own to the front and types into them.")]
public sealed class MolestiaPrimitivesLiveCheck
{
    [Test]
    public async Task TheLeasedPrimitivesActOnTheirOwnWindowsAndGiveTheDesktopBack()
    {
        if (Environment.GetEnvironmentVariable("BAXY_MOLESTIA_LIVE") != "1")
            Assert.Ignore("Set BAXY_MOLESTIA_LIVE=1 to run the live check.");
        string tag = Guid.NewGuid().ToString("N")[..8];
        bool meterIsPerson = Environment.GetEnvironmentVariable("BAXY_MOLESTIA_PERSON_FOREGROUND") == "1";
        using Process? ownPerson = meterIsPerson ? null : OpenForm("BAXY molestia persona " + tag, 80, 80, button: false);
        using Process opened = OpenForm("BAXY molestia abierta " + tag, 560, 80, button: true);
        using Process mission = OpenForm("BAXY molestia mision " + tag, 560, 340, button: false);
        using Process helper = OpenForm("BAXY molestia ayudante " + tag, 1000, 340, button: false);
        try
        {
            // With the meter: the test's windows open first (their own activation is setup, not BAXY's), then the
            // meter starts and brings its simulated user's window up; the test waits for that and measures from there.
            if (meterIsPerson)
                await WaitForMeterAsync();
            nint person = meterIsPerson ? GetForegroundWindow() : await MainWindowAsync(ownPerson!);
            nint openedWindow = await MainWindowAsync(opened);
            nint missionWindow = await MainWindowAsync(mission);
            nint helperWindow = await MainWindowAsync(helper);
            Assert.That(new[] { person, openedWindow, missionWindow, helperWindow }, Has.None.Zero);
            if (!meterIsPerson)
                Assert.That(VisibleControlSurface.BringToFront(person), Is.True, "the person's window in front");
            await Task.Delay(400);

            // 1. The click after an opening, behind the person's window. With the meter, its simulated user moves the
            // cursor inside its own window while typing: the cursor is the meter's to judge (BAXY's jumps), not here.
            (int X, int Y) cursor = WindowsLeaseDesktop.Instance.Cursor();
            int otherFronts = 0;
            using var watching = new CancellationTokenSource();
            Task watcher = Task.Run(async () =>
            {
                while (!watching.IsCancellationRequested)
                {
                    nint front = GetForegroundWindow();
                    if (front != person && front != 0)
                        otherFronts++;
                    await Task.Delay(10);
                }
            });
            VisibleControlSurface.NoteOpened(opened.Id, launched: false, window: openedWindow);
            var adapter = new WindowsVisibleControlAdapter();
            var clickWatch = Stopwatch.StartNew();
            ExternalCapabilityReceipt click = await adapter.InvokeAsync(
                "input.visible.click", Json("""{"label":"Aceptar"}"""), CancellationToken.None);
            long clickMs = clickWatch.ElapsedMilliseconds;
            await watching.CancelAsync();
            await watcher;
            string pressed = EditText(openedWindow);
            TestContext.Out.WriteLine(
                $"click: verified {click.Verified}, error {click.ErrorCode}, stage {Stage(click)}, {clickMs} ms, " +
                $"other fronts sampled {otherFronts}, edit «{pressed}»");
            Assert.Multiple(() =>
            {
                Assert.That(click.Verified, Is.True, click.ErrorCode);
                Assert.That(pressed, Is.EqualTo("pulsado"));
                Assert.That(otherFronts, Is.Zero, "the person's window never left the front");
                if (!meterIsPerson)
                    Assert.That(WindowsLeaseDesktop.Instance.Cursor(), Is.EqualTo(cursor), "the cursor did not move");
            });

            // 2. A flow of keys in a lease burst on the mission's window.
            var keyboard = new WindowsDesktopKeyboard();
            var flowWatch = Stopwatch.StartNew();
            (uint Sent, string? Stop) flow = await LeasedInput.RunAsync<(uint, string?)>(
                ForegroundLease.Shared,
                missionWindow,
                _ =>
                {
                    uint sent = 0;
                    foreach (char character in "hola")
                    {
                        LeasedInput.EnsureMayAct();
                        sent += keyboard.TypeText(character.ToString(), () => keyboard.Holds(missionWindow));
                    }

                    return ValueTask.FromResult((sent, (string?)null));
                },
                (code, _) => (0u, code),
                CancellationToken.None);
            long flowMs = flowWatch.ElapsedMilliseconds;
            await Task.Delay(300);
            TestContext.Out.WriteLine($"flow: sent {flow.Sent}, stop {flow.Stop}, {flowMs} ms (pause wait included)");
            Assert.Multiple(() =>
            {
                Assert.That(flow.Stop, Is.Null);
                Assert.That(EditText(missionWindow), Is.EqualTo("hola"));
                Assert.That(VisibleControlSurface.ForegroundIs(person), Is.True, "the person's window is back in front");
                if (!meterIsPerson)
                    Assert.That(WindowsLeaseDesktop.Instance.Cursor(), Is.EqualTo(cursor));
            });

            // 3. A helper that brings its own window up and types there (the scripts' way), in a helper burst.
            var helperWatch = Stopwatch.StartNew();
            IInputBurst burst = await ForegroundLease.Shared.AcquireForHelperAsync(CancellationToken.None);
            Assert.That(burst.MayAct, Is.True, burst.Refusal ?? "the person acted");
            Assert.That(VisibleControlSurface.BringToFront(helperWindow), Is.True);
            uint typed = keyboard.TypeText("ok", () => keyboard.Holds(helperWindow));
            await keyboard.SettleAsync(CancellationToken.None);
            bool restored = burst.Restore();
            long helperMs = helperWatch.ElapsedMilliseconds;
            await Task.Delay(300);
            TestContext.Out.WriteLine($"helper: typed {typed}, restored {restored}, waited {burst.WaitedMs} ms, {helperMs} ms");
            Assert.Multiple(() =>
            {
                Assert.That(EditText(helperWindow), Is.EqualTo("ok"));
                Assert.That(restored, Is.True);
                Assert.That(VisibleControlSurface.ForegroundIs(person), Is.True, "the person's window is back in front");
                if (!meterIsPerson)
                    Assert.That(WindowsLeaseDesktop.Instance.Cursor(), Is.EqualTo(cursor));
            });
        }
        finally
        {
            if (ownPerson is not null)
                Close(ownPerson);
            Close(opened);
            Close(mission);
            Close(helper);
        }
    }

    /// <summary>
    /// molestia-ayudantes, live: with the meter's simulated user only moving the mouse in its own window
    /// (<c>medidor.py medir --solo-raton</c>: 2 s moving, 0.7 s still), a helper script of a few hundred ms (its own
    /// window brought up, two keys typed there) is granted at the hand's rest (review r2: never from under a moving
    /// hand), runs to its end inside a helper burst and its watcher while the moves come back, and the front and the
    /// cursor go back to the person.
    /// </summary>
    [Test]
    public async Task AHelperScriptOutlivesThePersonsBareMoves()
    {
        if (Environment.GetEnvironmentVariable("BAXY_MOLESTIA_LIVE") != "1"
            || Environment.GetEnvironmentVariable("BAXY_MOLESTIA_PERSON_FOREGROUND") != "1")
            Assert.Ignore("Set BAXY_MOLESTIA_LIVE=1 and BAXY_MOLESTIA_PERSON_FOREGROUND=1 (the meter moving the mouse).");
        string tag = Guid.NewGuid().ToString("N")[..8];
        using Process helper = OpenForm("BAXY molestia ayudante " + tag, 1000, 340, button: false);
        try
        {
            await WaitForMeterAsync();
            nint person = GetForegroundWindow();
            nint helperWindow = await MainWindowAsync(helper);
            Assert.That(new[] { person, helperWindow }, Has.None.Zero);

            var keyboard = new WindowsDesktopKeyboard();
            var watch = Stopwatch.StartNew();
            IInputBurst burst = await ForegroundLease.Shared.AcquireForHelperAsync(CancellationToken.None);
            long began = Environment.TickCount64;
            Assert.That(burst.Refusal, Is.Null, "granted at the rest of the person's hand");
            (string? result, bool interrupted) = await LeasedInput.WatchHelperAsync(
                burst,
                async run =>
                {
                    _ = VisibleControlSurface.BringToFront(helperWindow);
                    foreach (char character in "ok")
                    {
                        await Task.Delay(300, run);
                        _ = keyboard.TypeText(character.ToString(), () => keyboard.Holds(helperWindow));
                    }

                    await keyboard.SettleAsync(run);
                    return "done";
                },
                CancellationToken.None);
            bool movedMeanwhile = WindowsUserInputPause.Shared.LastForeignInputMs > began;
            (long AtMs, int X, int Y)? theirs = WindowsUserInputPause.Shared.LastPointerAt;
            bool restored = burst.Restore();
            (int X, int Y) cursor = WindowsLeaseDesktop.Instance.Cursor();
            long helperMs = watch.ElapsedMilliseconds;
            await Task.Delay(300);
            TestContext.Out.WriteLine(
                $"helper: result {result}, interrupted {interrupted}, waited {burst.WaitedMs} ms, {helperMs} ms, " +
                $"person moved meanwhile {movedMeanwhile}, restored {restored}, cursor {cursor} (theirs {theirs}), " +
                $"edit «{EditText(helperWindow)}»");
            Assert.Multiple(() =>
            {
                Assert.That(burst.WaitedMs, Is.LessThan(ForegroundLease.DefaultMaxWaitMs), "the hand's rest was found");
                Assert.That(movedMeanwhile, Is.True, "the person moved the mouse during the script");
                Assert.That(restored, Is.True);
                Assert.That(theirs, Is.Not.Null, "where the person's moves left the cursor is told");
                Assert.That(interrupted, Is.False);
                Assert.That(result, Is.EqualTo("done"));
                Assert.That(EditText(helperWindow), Is.EqualTo("ok"));
                Assert.That(VisibleControlSurface.ForegroundIs(person), Is.True, "the person's window is back in front");
            });
        }
        finally
        {
            Close(helper);
        }
    }

    // BAXY_MOLESTIA_READY: written once the test's windows are open; BAXY_MOLESTIA_GO: waited for (the meter runs).
    private static async Task WaitForMeterAsync()
    {
        string? ready = Environment.GetEnvironmentVariable("BAXY_MOLESTIA_READY");
        string? go = Environment.GetEnvironmentVariable("BAXY_MOLESTIA_GO");
        await Task.Delay(1500);
        if (ready is not null)
            await File.WriteAllTextAsync(ready, "ok");
        for (int wait = 0; go is not null && wait < 600 && !File.Exists(go); wait++)
            await Task.Delay(100);
        await Task.Delay(1000);
    }

    private static string Stage(ExternalCapabilityReceipt receipt) =>
        receipt.Result is { ValueKind: JsonValueKind.Object } result
        && result.TryGetProperty("cascadeStage", out JsonElement stage)
            ? stage.GetString() ?? string.Empty
            : string.Empty;

    private static JsonElement Json(string text)
    {
        using JsonDocument document = JsonDocument.Parse(text);
        return document.RootElement.Clone();
    }

    private static Process OpenForm(string title, int left, int top, bool button)
    {
        string pressButton = button
            ? "$b=New-Object System.Windows.Forms.Button;$b.Text='Aceptar';$b.Dock='Bottom';" +
              "$b.Add_Click({$t.Text='pulsado'});$f.Controls.Add($b);"
            : string.Empty;
        string script =
            "Add-Type -AssemblyName System.Windows.Forms;" +
            "$f=New-Object System.Windows.Forms.Form;$f.Text='" + title + "';$f.StartPosition='Manual';" +
            "$f.ShowInTaskbar=$true;$f.Left=" + left + ";$f.Top=" + top + ";$f.Width=420;$f.Height=220;" +
            "$t=New-Object System.Windows.Forms.TextBox;$t.Multiline=$true;$t.Dock='Fill';$f.Controls.Add($t);" +
            pressButton +
            "$f.Add_Shown({});" +
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

    // The text box of a form: the first child whose class is an edit control (the button is another child).
    private static string EditText(nint form)
    {
        nint child = 0;
        while ((child = FindWindowExW(form, child, null, null)) != 0)
        {
            var name = new char[64];
            int length = GetClassNameW(child, name, name.Length);
            if (new string(name, 0, Math.Max(0, length)).Contains("EDIT", StringComparison.OrdinalIgnoreCase))
            {
                var buffer = new char[256];
                int read = (int)SendMessageW(child, 0x000D, buffer.Length, buffer);
                return new string(buffer, 0, Math.Max(0, read));
            }
        }

        return string.Empty;
    }

    [DllImport("user32.dll")]
    private static extern IntPtr GetForegroundWindow();

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern IntPtr FindWindowExW(IntPtr parent, IntPtr after, string? className, string? title);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern int GetClassNameW(IntPtr window, [Out] char[] name, int count);

    [DllImport("user32.dll", EntryPoint = "SendMessageW", CharSet = CharSet.Unicode)]
    private static extern IntPtr SendMessageW(IntPtr window, uint message, IntPtr wParam, [Out] char[] buffer);
}
