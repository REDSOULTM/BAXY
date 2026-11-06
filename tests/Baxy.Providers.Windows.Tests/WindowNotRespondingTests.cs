using System.Diagnostics;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// uso-108 A9: a window whose thread stopped pumping, a real one of a process of its own that never shows (StallingWindow).
/// The check before a window is touched (VisibleControlSurface.NotResponding) and the real worker on it: measured before
/// the check, the worker's FromHandle did not return and its host ended it at 20 s (HungWindowLiveCheck has the acts on the
/// desktop). A window that pumps pays about nothing: that is the control.
/// </summary>
[TestFixture]
public sealed class WindowNotRespondingTests
{
    [Test]
    public void AWindowThatPumpsAnswersInAboutNoTime()
    {
        using StallingWindow window = StallingWindow.Open(visible: false);
        const int probes = 200;
        var watch = Stopwatch.StartNew();
        for (int probe = 0; probe < probes; probe++)
            Assert.That(VisibleControlSurface.NotResponding(window.Handle), Is.False);
        double each = watch.Elapsed.TotalMilliseconds / probes;
        TestContext.Out.WriteLine($"probe on a window that pumps: {each:F3} ms each, over {probes}");
        Assert.That(each, Is.LessThan(5));
    }

    // Windows' own limit, 5 s unless this machine changed it (HKCU\Control Panel\Desktop, HungAppTimeout; the notebook has 1 s).
    private static int HungMs { get; } = int.TryParse(
        Microsoft.Win32.Registry.GetValue(@"HKEY_CURRENT_USER\Control Panel\Desktop", "HungAppTimeout", null) as string, out int ms) ? ms : 5000;

    [Test]
    public void AWindowThatStoppedPumpingIsToldApartFromOneThatCameBackAndFromOneThatIsGone()
    {
        using StallingWindow window = StallingWindow.Open(visible: false);
        window.Stall();
        var watch = Stopwatch.StartNew();
        bool hung = VisibleControlSurface.NotResponding(window.Handle);
        long took = watch.ElapsedMilliseconds;
        window.Resume();
        // Resume only signals its thread: under load the window is still marked hung for a moment.
        bool cameBack = true;
        for (var again = Stopwatch.StartNew(); cameBack && again.Elapsed < TimeSpan.FromSeconds(10); )
            cameBack = VisibleControlSurface.NotResponding(window.Handle);
        nint handle = window.Handle;
        window.Kill();
        Assert.Multiple(() =>
        {
            Assert.That(hung, Is.True);
            Assert.That(took, Is.InRange(HungMs - 1000, HungMs + 2000), "until Windows itself marks it hung");
            Assert.That(cameBack, Is.False);
            Assert.That(VisibleControlSurface.NotResponding(handle), Is.False, "a window that is gone is not a hung one");
            Assert.That(VisibleControlSurface.NotResponding(0), Is.False);
        });
    }

    // The Ghost Windows shows in a hung window's place answers messages and takes nothing (measured): told by its class. Here
    // a window of that class that pumps; a real one comes only when Windows decides (HungWindowLiveCheck).
    [Test]
    public void AWindowOfTheGhostClassStandsForOneThatDoesNotRespond()
    {
        using StallingWindow ghost = StallingWindow.Open(visible: false, windowClass: "Ghost");
        Assert.Multiple(() =>
        {
            Assert.That(VisibleControlSurface.IsGhost(ghost.Handle), Is.True);
            Assert.That(VisibleControlSurface.NotResponding(ghost.Handle), Is.True);
        });
    }

    // A thread busy for a while (a document opening, a sheet recalculating) is not a frozen one: Windows itself calls a window
    // hung at 5 s. The act waits for it and goes on.
    [TestCase(700)]
    [TestCase(1000)]
    [TestCase(3000)]
    public async Task AWindowBusyForAWhileIsNotCalledFrozen(int busyMs)
    {
        Assume.That(busyMs, Is.LessThanOrEqualTo(HungMs), "on this machine Windows itself calls it hung first");
        using StallingWindow window = StallingWindow.Open(visible: false);
        window.Stall();
        Task resume = Task.Run(async () =>
        {
            await Task.Delay(busyMs);
            window.Resume();
        });
        var watch = Stopwatch.StartNew();
        bool frozen = VisibleControlSurface.NotResponding(window.Handle);
        long took = watch.ElapsedMilliseconds;
        await resume;
        TestContext.Out.WriteLine($"busy {busyMs} ms: frozen={frozen} in {took} ms");
        Assert.Multiple(() =>
        {
            Assert.That(frozen, Is.False);
            Assert.That(took, Is.LessThan(busyMs + 1000));
        });
    }

    // Frozen: refused well under the 20 s of the host's budget, at about 5 s the first time and at once from then on.
    [Test]
    public void AFrozenWindowCostsItsWaitOnce()
    {
        using StallingWindow window = StallingWindow.Open(visible: false);
        window.Stall();
        var watch = Stopwatch.StartNew();
        bool first = VisibleControlSurface.NotResponding(window.Handle);
        long firstMs = watch.ElapsedMilliseconds;
        watch.Restart();
        bool again = VisibleControlSurface.NotResponding(window.Handle);
        long againMs = watch.ElapsedMilliseconds;
        window.Resume();
        TestContext.Out.WriteLine($"frozen: first {firstMs} ms, again {againMs} ms");
        Assert.Multiple(() =>
        {
            Assert.That(first && again, Is.True);
            Assert.That(firstMs, Is.LessThan(7000));
            Assert.That(againMs, Is.LessThan(100));
        });
    }

    // Review of uso-108 (VA:981): the read after a verified act waits 3 s, and a window left busy over that (a document
    // opening) cost the worker: the host ended it, and the next order paid its start. The worker's wait fits the host's.
    [TestCase(3000)]
    [TestCase(1500)]
    public async Task AWaitShorterThanTheChecksLeavesTheWorkerAlive(int budgetMs)
    {
        using StallingWindow window = StallingWindow.Open(visible: false);
        using var worker = new UiaWorkerHost(Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1"));
        string view = WindowsVisibleControlAdapter.ViewCommand(window.Handle, 10, null, false, WindowsVisibleControlAdapter.AfterReadSeconds);
        using JsonDocument? warm = await worker.SendAsync(view, TimeSpan.FromSeconds(20), CancellationToken.None);
        window.Stall();
        var watch = Stopwatch.StartNew();
        using JsonDocument? answer = await worker.SendAsync(view, TimeSpan.FromMilliseconds(budgetMs), CancellationToken.None);
        long took = watch.ElapsedMilliseconds;
        window.Resume();
        watch.Restart();
        using JsonDocument? next = await worker.SendAsync(view, TimeSpan.FromSeconds(20), CancellationToken.None);
        long nextMs = watch.ElapsedMilliseconds;
        TestContext.Out.WriteLine($"budget {budgetMs} ms: answer in {took} ms ({answer?.RootElement.GetRawText()}); next order {nextMs} ms");
        Assert.Multiple(() =>
        {
            Assert.That(answer?.RootElement.GetProperty("error").GetString(), Is.EqualTo(VisibleControlSurface.WindowNotResponding));
            Assert.That(nextMs, Is.LessThan(500), "no new worker to start");
        });
    }

    [Test]
    public void TheWorkerIsToldHowLongItsAnswerIsWaitedFor()
    {
        Assert.Multiple(() =>
        {
            Assert.That(UiaWorkerHost.WithBudget("""{"cmd":"view"}""", TimeSpan.FromSeconds(3)), Is.EqualTo("""{"withinMs":3000,"cmd":"view"}"""));
            Assert.That(UiaWorkerHost.WithBudget("{}", TimeSpan.FromSeconds(3)), Is.EqualTo("{}"));
        });
    }

    // Review of uso-108: the wait for a busy window ends with the request.
    [Test]
    public void TheCheckHonoursItsCancellation()
    {
        using StallingWindow window = StallingWindow.Open(visible: false);
        window.Stall();
        using var cancel = new CancellationTokenSource(Math.Min(800, HungMs / 4));
        var watch = Stopwatch.StartNew();
        Assert.Throws<OperationCanceledException>(() => VisibleControlSurface.NotResponding(window.Handle, cancel.Token));
        long took = watch.ElapsedMilliseconds;
        window.Resume();
        Assert.That(took, Is.LessThan(1700));
    }

    // The worker too: a look at a window busy for a while reads it, with no walk failed.
    [TestCase(1000)]
    [TestCase(3000)]
    public async Task TheWorkerWaitsForAWindowBusyForAWhile(int busyMs)
    {
        Assume.That(busyMs, Is.LessThanOrEqualTo(HungMs), "on this machine Windows itself calls it hung first");
        using StallingWindow window = StallingWindow.Open(visible: false);
        using var worker = new UiaWorkerHost(Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1"));
        string view = """{"cmd":"view","hwnd":HWND,"limit":10}""".Replace("HWND", ((long)window.Handle).ToString(System.Globalization.CultureInfo.InvariantCulture), StringComparison.Ordinal);
        using JsonDocument? warm = await worker.SendAsync(view, TimeSpan.FromSeconds(20), CancellationToken.None);
        var watch = Stopwatch.StartNew();
        using JsonDocument? healthy = await worker.SendAsync(view, TimeSpan.FromSeconds(20), CancellationToken.None);
        long healthyMs = watch.ElapsedMilliseconds;
        window.Stall();
        Task resume = Task.Run(async () =>
        {
            await Task.Delay(busyMs);
            window.Resume();
        });
        watch.Restart();
        using JsonDocument? answer = await worker.SendAsync(view, TimeSpan.FromSeconds(20), CancellationToken.None);
        long took = watch.ElapsedMilliseconds;
        await resume;
        TestContext.Out.WriteLine($"worker, busy {busyMs} ms: {took} ms; healthy look {healthyMs} ms");
        Assert.That(answer?.RootElement.GetProperty("ok").GetBoolean(), Is.True, answer?.RootElement.GetRawText());
    }

    // Each command with a window answers it without touching it, and the worker stays (a kill costs the next command its
    // start). Before the check: no answer within the host's budget, and the worker ended.
    [TestCase("""{"cmd":"view","hwnd":HWND,"limit":10}""")]
    [TestCase("""{"cmd":"click","hwnd":HWND,"aliases":["Aceptar"],"controlId":"","asks":[],"changes":[]}""")]
    [TestCase("""{"cmd":"at","hwnd":HWND,"x":10,"y":10}""")]
    [TestCase("""{"cmd":"field","hwnd":HWND,"index":0,"text":"hola"}""")]
    [TestCase("""{"cmd":"focus","hwnd":HWND,"index":0}""")]
    public async Task TheWorkerAnswersAtOnceAndStaysForAWindowThatDoesNotRespond(string command)
    {
        using StallingWindow window = StallingWindow.Open(visible: false);
        using var worker = new UiaWorkerHost(Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1"));
        string asked = command.Replace("HWND", ((long)window.Handle).ToString(System.Globalization.CultureInfo.InvariantCulture), StringComparison.Ordinal);
        using JsonDocument? healthy = await worker.SendAsync(
            """{"cmd":"view","hwnd":HWND,"limit":10}""".Replace("HWND", ((long)window.Handle).ToString(System.Globalization.CultureInfo.InvariantCulture), StringComparison.Ordinal),
            TimeSpan.FromSeconds(20), CancellationToken.None);
        window.Stall();
        var watch = Stopwatch.StartNew();
        using JsonDocument? answer = await worker.SendAsync(asked, TimeSpan.FromSeconds(12), CancellationToken.None);
        long took = watch.ElapsedMilliseconds;
        window.Resume();
        using JsonDocument? again = await worker.SendAsync("""{"cmd":"ping"}""", TimeSpan.FromSeconds(2), CancellationToken.None);
        Assert.Multiple(() =>
        {
            Assert.That(healthy?.RootElement.GetProperty("ok").GetBoolean(), Is.True, "the same window, pumping");
            Assert.That(answer, Is.Not.Null, $"no answer in {took} ms");
            Assert.That(answer?.RootElement.GetProperty("error").GetString(), Is.EqualTo(VisibleControlSurface.WindowNotResponding));
            Assert.That(took, Is.LessThan(7500));
            Assert.That(again, Is.Not.Null, "the worker was not ended");
        });
    }

    // A click, by the adapter, on a hung window (a real one, of a process of its own, not shown): told before anything is
    // captured or asked of the worker, with no effect in doubt.
    [Test]
    public async Task AClickOnAWindowThatDoesNotRespondIsToldWithNothingSent()
    {
        using StallingWindow window = StallingWindow.Open(visible: false);
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker();
        using var adapter = new WindowsVisibleControlAdapter(worker, null, null, requestedWindow: (_, _) => ValueTask.FromResult(window.Handle));
        window.Stall();
        var watch = Stopwatch.StartNew();
        ExternalCapabilityReceipt click = await adapter.InvokeAsync(
            "input.visible.click", JsonDocument.Parse($$"""{"label":"Aceptar","window":{{(long)window.Handle}}}""").RootElement.Clone(), CancellationToken.None);
        long took = watch.ElapsedMilliseconds;
        window.Resume();
        Assert.Multiple(() =>
        {
            Assert.That(click.ErrorCode, Is.EqualTo(VisibleControlSurface.WindowNotResponding));
            Assert.That(click.EffectMayHaveOccurred, Is.False);
            Assert.That(worker.Commands, Is.Empty);
            Assert.That(took, Is.LessThan(7500));
        });
    }

    // uso-108 C16: a window of Chromium's class that never lists a Document, looked at twice with the same count: the second
    // look does not wait again; a changed count does. Before: 6 reads and about 2 s of waits on each look.
    [Test]
    public async Task ALookAtAWindowWhoseWaitForADocumentRanOutDoesNotPayItAgain()
    {
        using StallingWindow window = StallingWindow.Open(visible: false, windowClass: "Chrome_WidgetWin_1");
        string frame = View(window.Handle, 12);
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(
            [.. Enumerable.Repeat(frame, 6), frame, View(window.Handle, 13), .. Enumerable.Repeat(View(window.Handle, 13), 5)]);
        using var adapter = new WindowsVisibleControlAdapter(worker, null, null, requestedWindow: (_, _) => ValueTask.FromResult(window.Handle));
        JsonElement look = JsonDocument.Parse("""{"application":"la ventana","includeText":false}""").RootElement.Clone();

        var watch = Stopwatch.StartNew();
        _ = await adapter.InvokeAsync("input.visible.controls", look, CancellationToken.None);
        int first = worker.Commands.Count;
        long firstMs = watch.ElapsedMilliseconds;
        watch.Restart();
        _ = await adapter.InvokeAsync("input.visible.controls", look, CancellationToken.None);
        int second = worker.Commands.Count - first;
        long secondMs = watch.ElapsedMilliseconds;
        _ = await adapter.InvokeAsync("input.visible.controls", look, CancellationToken.None);
        int changed = worker.Commands.Count - first - second;
        TestContext.Out.WriteLine($"first {firstMs} ms, {first} reads; second {secondMs} ms, {second} reads; changed count {changed} reads");

        Assert.Multiple(() =>
        {
            Assert.That(first, Is.EqualTo(1 + WindowsVisibleControlAdapter.TreeSettleReads), "the first look still waits (uso-89)");
            Assert.That(second, Is.EqualTo(1));
            Assert.That(changed, Is.EqualTo(1 + WindowsVisibleControlAdapter.TreeSettleReads));
        });
    }

    private static string View(nint window, int controls) =>
        "{\"ok\":true,\"error\":\"\",\"hwnd\":" + (long)window + ",\"window\":\"Marco\",\"controls\":["
        + string.Join(",", Enumerable.Range(0, controls).Select(k =>
            "{\"kind\":\"Button\",\"name\":\"Boton " + k + "\",\"id\":\"9." + k + "\",\"state\":\"\",\"value\":null,\"rect\":null,\"repeated\":0}"))
        + "],\"controlCount\":" + controls + ",\"focused\":null}";

    [Test]
    public void ALookAtAWindowThatDoesNotRespondGoesOnFromWhatItDrawsAndSaysWhy()
    {
        using JsonDocument answer = JsonDocument.Parse("""{"ok":false,"error":"window_not_responding"}""");
        using JsonDocument? there = WindowsVisibleControlAdapter.WithoutTree(answer.RootElement, 7, _ => true);
        using JsonDocument? gone = WindowsVisibleControlAdapter.WithoutTree(answer.RootElement, 7, _ => false);
        using JsonDocument? stoppedAfter = WindowsVisibleControlAdapter.UnfinishedWalk(7, _ => true, _ => true);
        using JsonDocument? slow = WindowsVisibleControlAdapter.UnfinishedWalk(7, _ => true, _ => false);
        Assert.Multiple(() =>
        {
            Assert.That(there?.RootElement.GetProperty("ok").GetBoolean(), Is.True);
            Assert.That(there?.RootElement.GetProperty("uiaFailed").GetString(), Is.EqualTo("la ventana no responde"));
            Assert.That(gone, Is.Null);
            Assert.That(stoppedAfter?.RootElement.GetProperty("uiaFailed").GetString(), Is.EqualTo("la ventana no responde"));
            Assert.That(slow?.RootElement.GetProperty("uiaFailed").GetString(), Is.EqualTo(WindowsVisibleControlAdapter.UnfinishedWalkReason));
        });
    }
}
