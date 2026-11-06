using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using Baxy.Providers.Windows.Windows;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// A window whose thread stopped pumping, on BAXY's own managed stack and the real desktop: how long a look, a click, a key,
/// a window move and a bringing to the front take and what comes back. agent-desktop measured only its COM client
/// (FINDINGS A14-11, A14-12); this is the measure of the managed one. Never runs in a suite: Explicit and
/// BAXY_CU_HUNG_LIVE=1. The windows it opens are its own and close by process id. BAXY_CU_HUNG_REPORT names a file to
/// append the report to.
/// </summary>
[TestFixture]
[Explicit("Opens its own windows and moves the front on the person's desktop.")]
[Category("LiveDesktop")]
public sealed class HungWindowLiveCheck
{
    private static readonly TimeSpan Bound = TimeSpan.FromSeconds(40);

    [Test]
    public async Task WhatEachActCostsOnAWindowThatStoppedPumping()
    {
        if (Environment.GetEnvironmentVariable("BAXY_CU_HUNG_LIVE") != "1")
            Assert.Ignore("BAXY_CU_HUNG_LIVE=1 is needed to touch the desktop.");
        using StallingWindow target = StallingWindow.Open(x: 120, y: 120);
        using StallingWindow other = StallingWindow.Open(x: 800, y: 300, width: 420, height: 300);
        using var controls = new WindowsVisibleControlAdapter();
        await controls.PrewarmAsync();
        var keys = new WindowsDesktopInteractionAdapter(fields: null);
        var windows = new WindowsWindowControlProvider();
        JsonElement look = Json($$"""{"application":"{{target.Title}}","includeText":false}""");
        JsonElement click = Json($$"""{"label":"Aceptar","window":{{(long)target.Handle}}}""");
        JsonElement key = Json($$"""{"key":"tab","window":{{(long)target.Handle}}}""");
        JsonElement keyAny = Json("""{"key":"tab"}""");

        // A bare key goes to whatever is in front: only ever while that is this check's own window (other work may share
        // the desktop and take the front).
        async Task<string> KeyToOwnFront() => GetForegroundWindow() == target.Handle || VisibleControlSurface.IsGhost(GetForegroundWindow())
            ? await Receipt(keys.InvokeAsync("input.key.press", keyAny, CancellationToken.None))
            : "skipped: the front is not this check's window";

        // Healthy, in front: the control.
        _ = VisibleControlSurface.BringToFront(target.Handle);
        Report($"apis: {await Timed(() => ApisAsync(target))}");
        _ = VisibleControlSurface.BringToFront(target.Handle);
        Report($"healthy: {await Timed(() => Receipt(controls.InvokeAsync("input.visible.controls", look, CancellationToken.None)))}");
        Report($"healthy: {await Timed(() => Receipt(controls.InvokeAsync("input.visible.click", click, CancellationToken.None)))}");
        Report($"healthy: {await Timed(() => Receipt(keys.InvokeAsync("input.key.press", key, CancellationToken.None)))}");
        Report($"healthy move: {await Timed(() => MoveAsync(windows, target, 130))}");
        Report($"healthy received: {target.Received()}");

        await Stalled(target, "probe", () => Task.FromResult(Probes(target.Handle)));
        foreach (int wait in new[] { 0, 6000 })
        {
            string when = $"stalled {wait} ms";
            _ = VisibleControlSurface.BringToFront(target.Handle);
            await Stalled(target, when + ", in front, look", () => Receipt(controls.InvokeAsync("input.visible.controls", look, CancellationToken.None)), wait);
            _ = VisibleControlSurface.BringToFront(target.Handle);
            await Stalled(target, when + ", in front, click", () => Receipt(controls.InvokeAsync("input.visible.click", click, CancellationToken.None)), wait);
            _ = VisibleControlSurface.BringToFront(target.Handle);
            await Stalled(target, when + ", in front, key", () => Receipt(keys.InvokeAsync("input.key.press", key, CancellationToken.None)), wait);
            _ = VisibleControlSurface.BringToFront(target.Handle);
            await Stalled(target, when + ", in front, key to the front", KeyToOwnFront, wait);
            _ = VisibleControlSurface.BringToFront(other.Handle);
            await Stalled(target, when + ", behind, click", () => Receipt(controls.InvokeAsync("input.visible.click", click, CancellationToken.None)), wait);
            _ = VisibleControlSurface.BringToFront(other.Handle);
            await Stalled(target, when + ", behind, key", () => Receipt(keys.InvokeAsync("input.key.press", key, CancellationToken.None)), wait);
            _ = VisibleControlSurface.BringToFront(other.Handle);
            await Stalled(target, when + ", behind, BringToFront", () => Task.FromResult(VisibleControlSurface.BringToFront(target.Handle).ToString()), wait);
            _ = VisibleControlSurface.BringToFront(other.Handle);
            await Stalled(target, when + ", behind, move", () => MoveAsync(windows, target, 140 + wait / 1000), wait);
        }
    }

    // uso-108 A13. Measured at the base: asked 643x407 of a window of 10 px cells, it took 640x400, and
    // verification_failed. A window that takes its time does the same, later. A cell of 30 px is farther than the tolerance:
    // the failure stands, with where the window is.
    [TestCase(10, 0, true)]
    [TestCase(10, 400, true)]
    [TestCase(30, 0, false)]
    [TestCase(0, 0, true)]
    public async Task AWindowThatAdjustsItsOwnSizeIsNotAFalseFailure(int cell, int adjustAfterMs, bool confirmed)
    {
        if (Environment.GetEnvironmentVariable("BAXY_CU_HUNG_LIVE") != "1")
            Assert.Ignore("BAXY_CU_HUNG_LIVE=1 is needed to touch the desktop.");
        using StallingWindow window = StallingWindow.Open(x: 300, y: 260, cell: cell, adjustAfterMs: adjustAfterMs);
        var windows = new WindowsWindowControlProvider();
        WindowResolveResult found = await windows.ResolveAsync(window.Title, 5, CancellationToken.None, byTitle: true);
        Assert.That(found.Windows, Is.Not.Empty);
        var watch = Stopwatch.StartNew();
        WindowActionResult resized = await windows.SetBoundsAsync(found.Windows[0].WindowId, null, null, 703, 487, CancellationToken.None);
        Report($"cell={cell} after={adjustAfterMs}: {watch.ElapsedMilliseconds} ms verified={resized.Verified} error={resized.ErrorCode} "
            + $"window=({resized.Window?.Width}x{resized.Window?.Height}) after=({resized.StateAfter?.Width}x{resized.StateAfter?.Height})");
        Assert.That(resized.Verified, Is.EqualTo(confirmed));
    }

    // uso-108 A9 (fixture_hung_after_probe.rs, window_op_tests.rs:275-319): a window that passes the check and stops: the
    // write does not wait for it, it is unconfirmed, not failed, and it lands when the window comes back. Measured at the base:
    // MoveWindow blocked past 40 s.
    [Test]
    public async Task AWindowThatStopsRightAfterTheCheckDoesNotHoldTheMove()
    {
        if (Environment.GetEnvironmentVariable("BAXY_CU_HUNG_LIVE") != "1")
            Assert.Ignore("BAXY_CU_HUNG_LIVE=1 is needed to touch the desktop.");
        using StallingWindow window = StallingWindow.Open(x: 300, y: 260);
        var windows = new WindowsWindowControlProvider();
        WindowResolveResult found = await windows.ResolveAsync(window.Title, 5, CancellationToken.None, byTitle: true);
        Assert.That(found.Windows, Is.Not.Empty);
        window.StallAfterNextProbe();
        var watch = Stopwatch.StartNew();
        Task<WindowActionResult> moving = windows.SetBoundsAsync(found.Windows[0].WindowId, 340, 300, null, null, CancellationToken.None).AsTask();
        bool returned = await Task.WhenAny(moving, Task.Delay(8000)) == moving;
        long took = watch.ElapsedMilliseconds;
        window.Resume();
        WindowActionResult moved = await moving;
        await Task.Delay(300);
        WindowResolveResult after = await windows.ResolveAsync(window.Title, 5, CancellationToken.None, byTitle: true);
        Report($"stopped after the check: returned={returned} in {took} ms error={moved.ErrorCode} effectMay={moved.EffectMayHaveOccurred} "
            + $"landed at ({after.Windows[0].X},{after.Windows[0].Y})");
        Assert.Multiple(() =>
        {
            Assert.That(returned, Is.True);
            Assert.That(took, Is.LessThan(3500));
            Assert.That(moved.ErrorCode, Is.EqualTo(WindowControlErrorCodes.VerificationFailed));
            Assert.That(moved.EffectMayHaveOccurred, Is.True);
            Assert.That((after.Windows[0].X, after.Windows[0].Y), Is.EqualTo((340, 300)));
        });
    }

    // uso-108 A9: bringing up a window that passed the check and stopped, minimized or not, does not hold the caller, and a
    // window in front that stopped does not hold the bringing up of another one.
    [Test]
    public async Task BringingToTheFrontDoesNotWaitForAWindowThatStopped()
    {
        if (Environment.GetEnvironmentVariable("BAXY_CU_HUNG_LIVE") != "1")
            Assert.Ignore("BAXY_CU_HUNG_LIVE=1 is needed to touch the desktop.");
        using StallingWindow hung = StallingWindow.Open(x: 120, y: 120);
        using StallingWindow other = StallingWindow.Open(x: 800, y: 300, width: 420, height: 300);
        _ = VisibleControlSurface.BringToFront(other.Handle);
        hung.Stall();
        Report($"bring up a stopped window: {await Timed(() => Task.FromResult(VisibleControlSurface.BringToFront(hung.Handle).ToString()))}");
        hung.Resume();
        await Task.Delay(300);
        _ = ShowWindowAsync(hung.Handle, 6);
        await Task.Delay(500);
        hung.Stall();
        Report($"bring up a stopped minimized window: {await Timed(() => Task.FromResult(VisibleControlSurface.BringToFront(hung.Handle).ToString()))}");
        Report($"show behind a stopped minimized window: {await Timed(() => Task.FromResult(VisibleControlSurface.ShowBehind(hung.Handle).ToString()))}");
        hung.Resume();
        await Task.Delay(500);
        _ = VisibleControlSurface.BringToFront(hung.Handle);
        hung.Stall();
        var watch = Stopwatch.StartNew();
        string front = await Timed(() => Task.FromResult(VisibleControlSurface.BringToFront(other.Handle).ToString()));
        Report($"bring up another with a stopped window in front: {front}");
        hung.Resume();
        Assert.That(watch.ElapsedMilliseconds, Is.LessThan(8000));
    }

    // Review of uso-108: through the real adapters, a window busy for 1 s and for 3 s gets the look and the key, late; what each
    // costs on a window that pumps is the control.
    [TestCase(1000)]
    [TestCase(3000)]
    public async Task AWindowBusyForAWhileGetsTheLookAndTheKey(int busyMs)
    {
        if (Environment.GetEnvironmentVariable("BAXY_CU_HUNG_LIVE") != "1")
            Assert.Ignore("BAXY_CU_HUNG_LIVE=1 is needed to touch the desktop.");
        using StallingWindow window = StallingWindow.Open(x: 200, y: 200);
        using var controls = new WindowsVisibleControlAdapter();
        await controls.PrewarmAsync();
        var keys = new WindowsDesktopInteractionAdapter(fields: null);
        JsonElement look = Json($$"""{"application":"{{window.Title}}","includeText":false}""");
        JsonElement key = Json($$"""{"key":"tab","window":{{(long)window.Handle}}}""");
        _ = VisibleControlSurface.BringToFront(window.Handle);
        _ = await controls.InvokeAsync("input.visible.controls", look, CancellationToken.None);
        Report($"pumping, look: {await Timed(() => Receipt(controls.InvokeAsync("input.visible.controls", look, CancellationToken.None)))}");
        Report($"pumping, key: {await Timed(() => Receipt(keys.InvokeAsync("input.key.press", key, CancellationToken.None)))}");
        (int Keys, int Presses, int Commands) before = window.Received();

        string busyLook = await Busy(window, busyMs, () => Receipt(controls.InvokeAsync("input.visible.controls", look, CancellationToken.None)));
        string busyKey = await Busy(window, busyMs, () => Receipt(keys.InvokeAsync("input.key.press", key, CancellationToken.None)));
        await Task.Delay(300);
        (int Keys, int Presses, int Commands) after = window.Received();
        Report($"busy {busyMs} ms, look: {busyLook}");
        Report($"busy {busyMs} ms, key: {busyKey}");
        Report($"busy {busyMs} ms, keys delivered: {after.Keys - before.Keys}");
        Assert.Multiple(() =>
        {
            Assert.That(busyLook, Does.Not.Contain("no responde"));
            Assert.That(busyKey, Does.Not.Contain("window_not_responding"));
        });
    }

    private static async Task<string> Busy(StallingWindow window, int busyMs, Func<Task<string>> act)
    {
        window.Stall();
        Task resume = Task.Run(async () =>
        {
            await Task.Delay(busyMs);
            window.Resume();
        });
        string timed = await Timed(act);
        await resume;
        return timed;
    }

    // uso-108 A9: the Ghost Windows puts in front of a window that stopped: a look, a click and a key with no window named
    // reach it, and each says the window does not respond. Each acts only while its own Ghost holds the front. Windows
    // decides when one comes: a run with none says so and proves nothing.
    [Test]
    public async Task TheGhostInFrontIsToldAsAWindowThatDoesNotRespond()
    {
        if (Environment.GetEnvironmentVariable("BAXY_CU_HUNG_LIVE") != "1")
            Assert.Ignore("BAXY_CU_HUNG_LIVE=1 is needed to touch the desktop.");
        using StallingWindow window = StallingWindow.Open(x: 160, y: 160);
        using var controls = new WindowsVisibleControlAdapter();
        await controls.PrewarmAsync();
        var keys = new WindowsDesktopInteractionAdapter(fields: null);
        var taking = Stopwatch.StartNew();
        while (GetForegroundWindow() != window.Handle && taking.ElapsedMilliseconds < 4000)
        {
            _ = VisibleControlSurface.BringToFront(window.Handle);
            await Task.Delay(200);
        }

        Report($"before stopping: front class {VisibleControlSurface.ClassName(GetForegroundWindow())}, own {GetForegroundWindow() == window.Handle}, after {taking.ElapsedMilliseconds} ms");
        (int Keys, int Presses, int Commands) before = window.Received();
        window.Stall();
        // Windows puts its Ghost in when input waits unread for the hung window (a window left alone stayed 15 s with none,
        // measured). F15, which nothing binds, and only while this window holds the front.
        if (GetForegroundWindow() == window.Handle)
        {
            keybd_event(0x7E, 0, 0, 0);
            keybd_event(0x7E, 0, 2, 0);
        }

        var waited = Stopwatch.StartNew();
        while (!OwnGhostInFront(window) && waited.ElapsedMilliseconds < 15000)
            await Task.Delay(100);
        bool ghost = OwnGhostInFront(window);
        Report($"ghost in front: {ghost} after {waited.ElapsedMilliseconds} ms, front class {VisibleControlSurface.ClassName(GetForegroundWindow())}");
        string look = "not reached", click = "not reached", key = "not reached";
        if (ghost)
        {
            bool probed = VisibleControlSurface.NotResponding(GetForegroundWindow());
            Report($"probe on the ghost: {probed}");
            if (OwnGhostInFront(window))
                look = await Timed(() => Receipt(controls.InvokeAsync("input.visible.controls", Json("""{"includeText":false}"""), CancellationToken.None)));
            if (OwnGhostInFront(window))
                click = await Timed(() => Receipt(controls.InvokeAsync("input.visible.click", Json("""{"label":"Aceptar"}"""), CancellationToken.None)));
            if (OwnGhostInFront(window))
                key = await Timed(() => Receipt(keys.InvokeAsync("input.key.press", Json("""{"key":"tab"}"""), CancellationToken.None)));
        }

        window.Resume();
        await Task.Delay(300);
        (int Keys, int Presses, int Commands) after = window.Received();
        Report($"ghost look: {look}");
        Report($"ghost click: {click}");
        Report($"ghost key: {key}");
        Report($"ghost delivered: ({after.Keys - before.Keys} keys, {after.Presses - before.Presses} presses, {after.Commands - before.Commands} commands)");
        if (!ghost)
            Assert.Inconclusive("Windows put no Ghost in front in this run.");
        Assert.Multiple(() =>
        {
            Assert.That(look, Does.Contain("la ventana no responde"));
            Assert.That(look, Does.Not.Contain("\"elevated\""));
            Assert.That(click, Does.Contain("window_not_responding"));
            Assert.That(key, Does.Contain("window_not_responding"));
        });
    }

    // Review of uso-108: a window that rounds its size to 7 px cells, placed on a half and asked again: both confirmed.
    [Test]
    public async Task AWindowThatRoundsItsSizeIsPlacedOnTheHalfTwice()
    {
        if (Environment.GetEnvironmentVariable("BAXY_CU_HUNG_LIVE") != "1")
            Assert.Ignore("BAXY_CU_HUNG_LIVE=1 is needed to touch the desktop.");
        using StallingWindow window = StallingWindow.Open(x: 300, y: 260, cell: 7);
        var windows = new WindowsWindowControlProvider();
        async Task<WindowActionResult> SnapOnce()
        {
            WindowResolveResult found = await windows.ResolveAsync(window.Title, 5, CancellationToken.None, byTitle: true);
            return await windows.SnapAsync(found.Windows[0].WindowId, "left", CancellationToken.None);
        }

        var watch = Stopwatch.StartNew();
        WindowActionResult first = await SnapOnce();
        long firstMs = watch.ElapsedMilliseconds;
        watch.Restart();
        WindowActionResult second = await SnapOnce();
        Report($"snap with 7 px cells: first {firstMs} ms verified={first.Verified} error={first.ErrorCode} ({first.Window?.Width}x{first.Window?.Height}); "
            + $"second {watch.ElapsedMilliseconds} ms verified={second.Verified} error={second.ErrorCode} ({second.Window?.Width}x{second.Window?.Height})");
        Assert.Multiple(() =>
        {
            Assert.That(first.Verified, Is.True);
            Assert.That(second.Verified, Is.True);
        });
    }

    // uso-108 A9, the control of the async forms: two windows that pump take the front from each other as they did with
    // BringWindowToTop and ShowWindow (the old form is here, as it was), from the front as it is and minimized.
    [Test]
    public async Task AWindowThatPumpsTakesTheFrontAsItDidWithTheBlockingForms()
    {
        if (Environment.GetEnvironmentVariable("BAXY_CU_HUNG_LIVE") != "1")
            Assert.Ignore("BAXY_CU_HUNG_LIVE=1 is needed to touch the desktop.");
        using StallingWindow first = StallingWindow.Open(x: 120, y: 120);
        using StallingWindow second = StallingWindow.Open(x: 800, y: 300, width: 420, height: 300);
        const int tries = 8;
        async Task<(int Held, long Ms, string Fronts)> Tally(Func<nint, bool> bring, bool minimized)
        {
            int held = 0;
            long ms = 0;
            var fronts = new HashSet<string>();
            for (int attempt = 0; attempt < tries; attempt++)
            {
                StallingWindow to = attempt % 2 == 0 ? first : second;
                if (minimized)
                {
                    _ = ShowWindowAsync(to.Handle, 6);
                    await Task.Delay(250);
                }

                var watch = Stopwatch.StartNew();
                bool said = bring(to.Handle);
                ms += watch.ElapsedMilliseconds;
                await Task.Delay(150);
                if (said && GetForegroundWindow() == to.Handle && !IsIconic(to.Handle))
                    held++;
                else
                    fronts.Add(VisibleControlSurface.ClassName(GetForegroundWindow()));
            }

            return (held, ms / tries, string.Join(",", fronts));
        }

        (int Held, long Ms, string Fronts) current = await Tally(VisibleControlSurface.BringToFront, minimized: false);
        (int Held, long Ms, string Fronts) old = await Tally(OldBringToFront, minimized: false);
        (int Held, long Ms, string Fronts) currentMinimized = await Tally(VisibleControlSurface.BringToFront, minimized: true);
        (int Held, long Ms, string Fronts) oldMinimized = await Tally(OldBringToFront, minimized: true);
        Report($"front held of {tries}: async {current}, blocking {old}; minimized: async {currentMinimized}, blocking {oldMinimized}");
        Assert.Multiple(() =>
        {
            Assert.That(current.Held, Is.GreaterThanOrEqualTo(old.Held));
            Assert.That(currentMinimized.Held, Is.GreaterThanOrEqualTo(oldMinimized.Held));
        });
    }

    // VisibleControlSurface.BringToFront before uso-108: BringWindowToTop and ShowWindow, the rest the same.
    private static bool OldBringToFront(nint window)
    {
        nint foreground = GetForegroundWindow();
        uint foregroundThread = GetWindowThreadProcessId(foreground, out _);
        uint currentThread = GetCurrentThreadId();
        bool attached = foregroundThread != 0 && currentThread != foregroundThread
            && AttachThreadInput(currentThread, foregroundThread, true);
        try
        {
            if (IsIconic(window))
                _ = ShowWindow(window, 9);
            _ = BringWindowToTop(window);
            _ = SetForegroundWindow(window);
            if (GetForegroundWindow() == window)
                return true;
        }
        finally
        {
            if (attached)
                _ = AttachThreadInput(currentThread, foregroundThread, false);
        }

        return ForegroundRight.Give(window).Held && GetForegroundWindow() == window;
    }

    // The front is a Ghost with this window's title (Windows adds its own suffix to it).
    private static bool OwnGhostInFront(StallingWindow window)
    {
        nint front = GetForegroundWindow();
        return VisibleControlSurface.IsGhost(front)
            && VisibleControlSurface.WindowTitle(front).StartsWith(window.Title, StringComparison.Ordinal);
    }

    private static async Task Stalled(StallingWindow window, string what, Func<Task<string>> act, int waitMs = 0)
    {
        (int Keys, int Presses, int Commands) before = window.Received();
        window.Stall();
        if (waitMs > 0)
            await Task.Delay(waitMs);
        string frontClass = VisibleControlSurface.ClassName(GetForegroundWindow());
        string timed = await Timed(act);
        window.Resume();
        await Task.Delay(300);
        (int Keys, int Presses, int Commands) after = window.Received();
        Report($"{what}: {timed} front={frontClass} delivered=({after.Keys - before.Keys} keys, " +
            $"{after.Presses - before.Presses} presses, {after.Commands - before.Commands} commands)");
    }

    private static async Task<string> Timed(Func<Task<string>> act)
    {
        var watch = Stopwatch.StartNew();
        Task<string> running = Task.Run(act);
        Task first = await Task.WhenAny(running, Task.Delay(Bound));
        return first == running
            ? $"{watch.ElapsedMilliseconds} ms {await running}"
            : $"BLOCKED past {watch.ElapsedMilliseconds} ms";
    }

    private static async Task<string> Receipt(ValueTask<ExternalCapabilityReceipt> asked)
    {
        ExternalCapabilityReceipt receipt = await asked;
        string result = receipt.Result?.GetRawText() ?? string.Empty;
        if (result.Length > 420)
            result = result[..420] + "…";
        return $"verified={receipt.Verified} error={receipt.ErrorCode} effectMay={receipt.EffectMayHaveOccurred} result={result}";
    }

    private static async Task<string> MoveAsync(WindowsWindowControlProvider windows, StallingWindow window, int x)
    {
        WindowResolveResult found = await windows.ResolveAsync(window.Title, 5, CancellationToken.None, byTitle: true);
        string? id = found.Windows.Count > 0 ? found.Windows[0].WindowId : null;
        if (id is null)
            return $"not resolved: {found.ErrorCode}";
        WindowActionResult moved = await windows.SetBoundsAsync(id, x, x, null, null, CancellationToken.None);
        return $"succeeded={moved.Succeeded} verified={moved.Verified} error={moved.ErrorCode} effectMay={moved.EffectMayHaveOccurred}";
    }

    // Which user32 call blocks on a window that stopped pumping, each with its own bound: the unblocked ones first.
    private static async Task<string> ApisAsync(StallingWindow window)
    {
        nint hwnd = window.Handle;
        var calls = new (string Name, Func<bool> Call)[]
        {
            ("IsWindow", () => IsWindow(hwnd)),
            ("GetWindowTextW", () => GetWindowTextW(hwnd, new char[64], 64) >= 0),
            ("ShowWindowAsync(noop)", () => ShowWindowAsync(hwnd, 5)),
            ("SetWindowPos async", () => SetWindowPos(hwnd, 0, 300, 300, 0, 0, 0x4000 | 0x0001 | 0x0004 | 0x0010)),
            ("SetForegroundWindow", () => SetForegroundWindow(hwnd)),
            ("PrintWindow", () => PrintNull(hwnd)),
            ("SetWindowPos", () => SetWindowPos(hwnd, 0, 300, 300, 0, 0, 0x0001 | 0x0004 | 0x0010)),
            ("BringWindowToTop", () => BringWindowToTop(hwnd)),
            ("MoveWindow", () => MoveWindow(hwnd, 310, 310, 640, 400, true)),
            ("ShowWindow", () => ShowWindow(hwnd, 5)),
        };
        var report = new List<string>();
        foreach ((string name, Func<bool> call) in calls)
        {
            window.Stall();
            var watch = Stopwatch.StartNew();
            Task<bool> running = Task.Run(call);
            Task first = await Task.WhenAny(running, Task.Delay(4000));
            report.Add(first == running ? $"{name}={watch.ElapsedMilliseconds}ms" : $"{name}=BLOCKED>{watch.ElapsedMilliseconds}ms");
            window.Resume();
            await Task.WhenAny(running, Task.Delay(3000));
        }

        return string.Join(" ", report);
    }

    private static bool PrintNull(nint window)
    {
        nint screen = GetDC(0);
        nint memory = CreateCompatibleDC(screen);
        nint bitmap = CreateCompatibleBitmap(screen, 64, 64);
        nint old = SelectObject(memory, bitmap);
        bool printed = PrintWindow(window, memory, 2);
        _ = SelectObject(memory, old);
        _ = DeleteObject(bitmap);
        _ = DeleteDC(memory);
        _ = ReleaseDC(0, screen);
        return printed;
    }

    private static string Probes(nint window)
    {
        var watch = Stopwatch.StartNew();
        bool answered = SendMessageTimeoutW(window, 0, 0, 0, 2, 500, out _) != 0;
        string first = $"first probe {answered} in {watch.ElapsedMilliseconds} ms";
        watch.Restart();
        while (!IsHungAppWindow(window) && watch.ElapsedMilliseconds < 15000)
            Thread.Sleep(20);
        string marked = $"IsHungAppWindow true after {watch.ElapsedMilliseconds} ms";
        watch.Restart();
        answered = SendMessageTimeoutW(window, 0, 0, 0, 2, 500, out _) != 0;
        return $"{first}; {marked}; second probe {answered} in {watch.ElapsedMilliseconds} ms";
    }

    private static void Report(string line)
    {
        TestContext.Out.WriteLine(line);
        if (Environment.GetEnvironmentVariable("BAXY_CU_HUNG_REPORT") is { Length: > 0 } file)
            File.AppendAllText(file, line + Environment.NewLine);
    }

    private static JsonElement Json(string text) => JsonDocument.Parse(text).RootElement;

    [DllImport("user32.dll", SetLastError = true)]
    private static extern nint SendMessageTimeoutW(nint window, uint message, nint w, nint l, uint flags, uint timeout, out nint result);

    [DllImport("user32.dll")]
    private static extern bool IsHungAppWindow(nint window);

    [DllImport("user32.dll")]
    private static extern bool IsIconic(nint window);

    [DllImport("user32.dll")]
    private static extern uint GetWindowThreadProcessId(nint window, out uint process);

    [DllImport("kernel32.dll")]
    private static extern uint GetCurrentThreadId();

    [DllImport("user32.dll")]
    private static extern bool AttachThreadInput(uint attach, uint to, bool on);

    [DllImport("user32.dll")]
    private static extern void keybd_event(byte key, byte scan, uint flags, nuint extra);

    [DllImport("user32.dll")]
    private static extern bool IsWindow(nint window);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern int GetWindowTextW(nint window, char[] text, int capacity);

    [DllImport("user32.dll")]
    private static extern bool ShowWindowAsync(nint window, int command);

    [DllImport("user32.dll")]
    private static extern bool ShowWindow(nint window, int command);

    [DllImport("user32.dll")]
    private static extern bool SetWindowPos(nint window, nint after, int x, int y, int width, int height, uint flags);

    [DllImport("user32.dll")]
    private static extern bool SetForegroundWindow(nint window);

    [DllImport("user32.dll")]
    private static extern bool BringWindowToTop(nint window);

    [DllImport("user32.dll")]
    private static extern bool MoveWindow(nint window, int x, int y, int width, int height, bool repaint);

    [DllImport("user32.dll")]
    private static extern bool PrintWindow(nint window, nint target, uint flags);

    [DllImport("user32.dll")]
    private static extern nint GetDC(nint window);

    [DllImport("user32.dll")]
    private static extern int ReleaseDC(nint window, nint dc);

    [DllImport("gdi32.dll")]
    private static extern nint CreateCompatibleDC(nint dc);

    [DllImport("gdi32.dll")]
    private static extern nint CreateCompatibleBitmap(nint dc, int width, int height);

    [DllImport("gdi32.dll")]
    private static extern nint SelectObject(nint dc, nint thing);

    [DllImport("gdi32.dll")]
    private static extern bool DeleteObject(nint thing);

    [DllImport("gdi32.dll")]
    private static extern bool DeleteDC(nint dc);

    [DllImport("user32.dll")]
    private static extern nint GetForegroundWindow();
}
