using System.Diagnostics;
using System.Text.Json;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.External;
using Baxy.Providers.Windows.Windows;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// uso-129, live: a tray program of the test's own (BAXY_TRAY_FIXTURE, its path): closing its window hides it, it keeps a
/// helper that starts again in a subfolder. Explicit: it starts and ends only processes it started itself, by id.
/// </summary>
[TestFixture]
[Explicit("Live: needs the tray fixture in BAXY_TRAY_FIXTURE")]
public sealed class ApplicationQuitLiveCheck
{
    private readonly List<Process> _started = [];

    private Process Start(string arguments)
    {
        string path = Environment.GetEnvironmentVariable("BAXY_TRAY_FIXTURE") ?? throw new InconclusiveException("no fixture");
        Process process = Process.Start(new ProcessStartInfo(path, arguments) { UseShellExecute = false })!;
        _started.Add(process);
        process.WaitForInputIdle(5000);
        Thread.Sleep(1200);
        return process;
    }

    [TearDown]
    public void EndWhatThisStarted()
    {
        foreach (Process process in _started)
        {
            int id = process.Id;
            foreach (ApplicationProcess child in ApplicationFamily.Read().Values.Where(p => p.Parent == id))
                if (child.Name == "Ayudante129")
                {
                    using Process running = Process.GetProcessById(child.Id);
                    running.Kill();
                }
            if (!process.HasExited)
                process.Kill();
            process.Dispose();
        }
        _started.Clear();
    }

    [TestCase("--oculto")]
    [TestCase("--oculto --hijo")]
    public async Task ATrayProgramQuitsWhenWindowsAsksItAndNothingOfItIsLeft(string arguments)
    {
        Process tray = Start(arguments);
        ApplicationQuitResult quit = await ApplicationQuit.AskAsync([tray.Id], CancellationToken.None);
        tray.WaitForExit(2000);
        TestContext.Out.WriteLine(JsonSerializer.Serialize(quit));
        Assert.Multiple(() =>
        {
            Assert.That(quit.Exited, Is.True);
            Assert.That(tray.HasExited, Is.True);
            Assert.That(quit.MainProcessName, Is.Null);
        });
    }

    [Test]
    public async Task AProgramThatRefusesStaysAndIsSaid()
    {
        Process tray = Start("--oculto --terco");
        ApplicationQuitResult quit = await ApplicationQuit.AskAsync([tray.Id], CancellationToken.None);
        TestContext.Out.WriteLine(JsonSerializer.Serialize(quit));
        Assert.Multiple(() =>
        {
            Assert.That(quit.Asked, Is.True);
            Assert.That(quit.Exited, Is.False);
            Assert.That(tray.HasExited, Is.False, "nothing is forced");
            Assert.That(quit.MainProcessName, Is.EqualTo("Bandeja129"));
            Assert.That(quit.StillRunning.Select(p => p.ProcessId), Does.Contain(tray.Id));
        });
    }

    [Test]
    public async Task ForcingAHelperThatComesBackSaysTheMainProcessStillRuns()
    {
        Process tray = Start("--oculto --terco --hijo");
        var adapter = new WindowsProcessTerminationAdapter();
        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync("system.process.terminate.named",
            JsonDocument.Parse("{\"name\":\"Ayudante129.exe\"}").RootElement, CancellationToken.None);
        TestContext.Out.WriteLine(receipt.Result?.GetRawText());
        JsonElement result = receipt.Result!.Value;
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(tray.HasExited, Is.False);
            Assert.That(result.GetProperty("mainStillRunning").GetBoolean(), Is.True);
            Assert.That(result.GetProperty("mainProcessName").GetString(), Is.EqualTo("Bandeja129"));
            Assert.That(result.GetProperty("next").GetString(),
                Does.StartWith("system_process_terminate_named {\"name\":\"Bandeja129\"}"));
        });
    }

    [Test]
    public async Task ForcingTheMainProcessSaysNoMainAndWhatOfItStayed()
    {
        Process tray = Start("--oculto --terco");
        var adapter = new WindowsProcessTerminationAdapter();
        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync("system.process.terminate.named",
            JsonDocument.Parse("{\"name\":\"Bandeja129\"}").RootElement, CancellationToken.None);
        TestContext.Out.WriteLine(receipt.Result?.GetRawText());
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(tray.WaitForExit(2000), Is.True);
            Assert.That(receipt.Result!.Value.TryGetProperty("mainStillRunning", out _), Is.False);
        });
    }

    [Test]
    public async Task ControlAPlainProgramIsNotTrayAndOneOfTwoIsNotTouched()
    {
        Process one = Start("--plano");
        Process other = Start("--plano");
        Assert.That(one.CloseMainWindow(), Is.True);
        Assert.That(one.WaitForExit(3000), Is.True, "a plain program goes with its window");
        Assert.That(other.HasExited, Is.False, "closing one window leaves the other");
        ApplicationQuitResult quit = await ApplicationQuit.AskAsync([], CancellationToken.None);
        Assert.That(quit.Asked, Is.False, "nothing named, nothing asked");
    }

    [Test]
    public async Task AWindowThatHidIsFollowedToTheEnd()
    {
        Process tray = Start("");
        Assert.That(tray.CloseMainWindow(), Is.True);
        Thread.Sleep(500);
        Assert.That(tray.HasExited, Is.False, "closing its window only hid it");
        ApplicationQuitResult quit = await ApplicationQuit.AskAsync([tray.Id], CancellationToken.None);
        Assert.That(quit.Exited, Is.True);
    }

    // A program with unsaved work that answers with its own dialog is not forced, and the request has a limit.
    [Test]
    public async Task AProgramThatAsksToSaveStaysAndTheRequestEnds()
    {
        Process tray = Start("--oculto --pregunta");
        var watch = Stopwatch.StartNew();
        ApplicationQuitResult quit = await ApplicationQuit.AskAsync([tray.Id], CancellationToken.None);
        TestContext.Out.WriteLine($"{watch.Elapsed.TotalSeconds:F1} s {JsonSerializer.Serialize(quit)}");
        Assert.Multiple(() =>
        {
            Assert.That(quit.Exited, Is.False);
            Assert.That(tray.HasExited, Is.False);
            Assert.That(watch.Elapsed.TotalSeconds, Is.LessThan(25));
        });
    }

    [TestCase("--oculto", true)]
    [TestCase("--oculto --terco", false)]
    public async Task TheHandlerSaysWhatCame(string arguments, bool exits)
    {
        Process tray = Start(arguments);
        OperationOutcome outcome = await new Baxy.Core.Operations.AppCloseHandler(new Real(tray.Id)).ExecuteAsync(
            new("r", "m", "i", JsonDocument.Parse("{\"appId\":\"Bandeja\"}").RootElement), CancellationToken.None);
        TestContext.Out.WriteLine($"{outcome.ErrorCode} {outcome.Result?.GetRawText()}");
        Assert.That(outcome.Succeeded, Is.EqualTo(exits));
        Assert.That(outcome.Result!.Value.GetProperty("applicationExited").GetBoolean(), Is.EqualTo(exits));
    }

    private sealed class Real(int processId) : IWindowControlProvider
    {
        public ValueTask<WindowResolveResult> ResolveForegroundAsync(CancellationToken cancellationToken) =>
            throw new AssertionException("not used");

        public ValueTask<WindowResolveResult> ResolveAsync(
            string processName, int limit, CancellationToken cancellationToken, bool byTitle = false, int offset = 0) =>
            throw new AssertionException("not used");

        public ValueTask<WindowResolveResult> ResolveApplicationAsync(
            string applicationName, int limit, CancellationToken cancellationToken) =>
            ValueTask.FromResult(new WindowResolveResult(false, false, [], WindowControlErrorCodes.WindowNotFound));

        public ValueTask<IReadOnlyList<int>> BackgroundProcessesAsync(
            string applicationName, CancellationToken cancellationToken) =>
            ValueTask.FromResult<IReadOnlyList<int>>([processId]);

        public ValueTask<ApplicationQuitResult> QuitApplicationAsync(
            IReadOnlyCollection<int> processIds, CancellationToken cancellationToken) =>
            ApplicationQuit.AskAsync(processIds, cancellationToken);

        public ValueTask<WindowActionResult> ExecuteAsync(
            string windowId, WindowControlAction action, CancellationToken cancellationToken) =>
            throw new AssertionException("not used");

        public ValueTask<WindowCloseResult> CloseAsync(string windowId, CancellationToken cancellationToken) =>
            throw new AssertionException("not used");

        public ValueTask<WindowActionResult> SetBoundsAsync(
            string windowId, int? x, int? y, int? width, int? height, CancellationToken cancellationToken) =>
            throw new AssertionException("not used");
    }

    [Test]
    public async Task BaxysOwnProcessIsNeverAsked()
    {
        ApplicationQuitResult quit = await ApplicationQuit.AskAsync([Environment.ProcessId], CancellationToken.None);
        Assert.That(quit.Asked, Is.False);
    }
}
