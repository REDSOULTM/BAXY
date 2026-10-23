using System.Diagnostics;
using System.Text;
using System.Text.RegularExpressions;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Renew al máximo (rendimiento): media.play.query took 3.3 s at its p50 on the leader's PC, and each call started a
/// powershell.exe and compiled the script's Add-Types again (about half a second on the notebook). The Spotify script
/// now runs in one persistent PowerShell (<see cref="PowerShellScriptWorker"/>): the runs share its process and its
/// types, answer what a run of their own process answered (output, exit code), and a run cut short kills the worker,
/// never what the script opened, and the next one starts another.
/// </summary>
[TestFixture]
[NonParallelizable]
public sealed class PowerShellScriptWorkerTests
{
    private string _folder = string.Empty;

    [SetUp]
    public void SetUp()
    {
        _folder = Path.Combine(Path.GetTempPath(), "baxy-script-worker-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(_folder);
    }

    [TearDown]
    public void TearDown()
    {
        try
        {
            Directory.Delete(_folder, recursive: true);
        }
        catch (IOException)
        {
        }
    }

    // The probe: its PowerShell's id, whether its type was already compiled there, a variable of its own scope, its
    // arguments by name and by position, and an exit code of its own.
    private const string Probe = """
        param([Parameter(Mandatory=$true)][string]$TitleBase64,[ValidateSet('exact','query')][string]$Mode='exact',[int]$DeadlineMs=0)
        $ErrorActionPreference='Stop'
        [Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false)
        $had=$null -ne ('BaxyWorkerProbeNative' -as [type])
        Add-Type -TypeDefinition 'public static class BaxyWorkerProbeNative { public static int Seven(){ return 7; } }'
        $script:seen=1+[int]$script:seen
        $title=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($TitleBase64))
        [pscustomobject]@{pid=$PID;had=$had;seen=$script:seen;title=$title;mode=$Mode;deadline=$DeadlineMs;seven=[BaxyWorkerProbeNative]::Seven()}|ConvertTo-Json -Compress
        if($Mode -eq 'query'){exit 2}
        """;

    private string Script(string name, string text)
    {
        string path = Path.Combine(_folder, name);
        File.WriteAllText(path, text, new UTF8Encoding(false));
        return path;
    }

    private static string[] Arguments(string script, string title, string mode, int deadline = 900) =>
        ["-NoProfile", "-NonInteractive", "-STA", "-File", script, "-DeadlineMs", deadline.ToString(System.Globalization.CultureInfo.InvariantCulture),
            Convert.ToBase64String(Encoding.UTF8.GetBytes(title)), mode];

    private static string LastLine(ExternalProcessResult result) =>
        result.Output.Split(['\r', '\n'], StringSplitOptions.RemoveEmptyEntries).LastOrDefault() ?? string.Empty;

    // Fails before: the product's runner was the one-shot ExternalProcessRunner, one powershell.exe and one Add-Type
    // per call.
    [Test]
    public void TheProductRunsTheSpotifyScriptInThePersistentWorker()
    {
        using var adapter = new SpotifyDesktopAdapter();

        Assert.That(adapter.ScriptRunner, Is.InstanceOf<PowerShellScriptWorker>());
    }

    [Test]
    public async Task RunsShareOneProcessAndItsCompiledTypesAndAnswerWhatTheirOwnProcessAnswered()
    {
        string script = Script("probe.ps1", Probe);
        using var worker = new PowerShellScriptWorker(script);
        var oneShot = new ExternalProcessRunner();
        const string Title = "Canción ñandú — ¿qué?";

        var answers = new List<ExternalProcessResult>();
        for (int run = 0; run < 3; run++)
            answers.Add(await worker.RunAsync("powershell.exe", Arguments(script, Title, run == 1 ? "query" : "exact"),
                TimeSpan.FromSeconds(60), CancellationToken.None));
        ExternalProcessResult alone = await oneShot.RunAsync("powershell.exe", Arguments(script, Title, "query"),
            TimeSpan.FromSeconds(60), CancellationToken.None);

        string[] lines = answers.Select(LastLine).ToArray();
        string pid = Regex.Match(lines[0], "\"pid\":(\\d+)").Groups[1].Value;
        Assert.Multiple(() =>
        {
            Assert.That(worker.Starts, Is.EqualTo(1), "one PowerShell for the three runs");
            Assert.That(lines, Has.All.Contains($"\"pid\":{pid},"));
            Assert.That(lines[0], Does.Contain("\"had\":false"));
            Assert.That(lines[1], Does.Contain("\"had\":true"), "the second run finds its type compiled");
            Assert.That(lines, Has.All.Contains("\"seen\":1,"), "each run in its own script scope");
            Assert.That(lines, Has.All.Contains($"\"title\":\"{Title}\""));
            Assert.That(lines[1], Does.Contain("\"mode\":\"query\",\"deadline\":900,\"seven\":7"));
            Assert.That(answers.Select(answer => answer.ExitCode), Is.EqualTo(new[] { 0, 2, 0 }), "exit ends the run, not the worker");
            // What a process of its own answered: the same line but its process id, and the same exit code.
            Assert.That(alone.ExitCode, Is.EqualTo(2));
            Assert.That(Regex.Replace(LastLine(alone), "\"pid\":\\d+,\"had\":\\w+", ""),
                Is.EqualTo(Regex.Replace(lines[1], "\"pid\":\\d+,\"had\":\\w+", "")));
        });
    }

    // A script that fails before its own try (a missing type) answers as its own process did: what it wrote before,
    // exit code 1; a Write-Host line stays in its output; the worker goes on.
    [Test]
    public async Task AFailingScriptAndAHostLineAnswerAsTheirOwnProcessDid()
    {
        string script = Script("fails.ps1", """
            param([string]$TitleBase64,[string]$Mode,[int]$DeadlineMs)
            $ErrorActionPreference='Stop'
            Write-Host 'host line'
            'before'
            [Missing.Type]::Call()
            'never'
            """);
        using var worker = new PowerShellScriptWorker(script);

        ExternalProcessResult first = await worker.RunAsync("powershell.exe", Arguments(script, "x", "exact"),
            TimeSpan.FromSeconds(60), CancellationToken.None);
        ExternalProcessResult second = await worker.RunAsync("powershell.exe", Arguments(script, "x", "exact"),
            TimeSpan.FromSeconds(60), CancellationToken.None);
        ExternalProcessResult alone = await new ExternalProcessRunner().RunAsync("powershell.exe",
            Arguments(script, "x", "exact"), TimeSpan.FromSeconds(60), CancellationToken.None);

        string[] Lines(ExternalProcessResult result) => result.Output.Split(['\r', '\n'], StringSplitOptions.RemoveEmptyEntries);
        Assert.Multiple(() =>
        {
            Assert.That(Lines(first), Is.EqualTo(new[] { "host line", "before" }));
            Assert.That(first.ExitCode, Is.EqualTo(1));
            Assert.That(second.ExitCode, Is.EqualTo(1));
            Assert.That(worker.Starts, Is.EqualTo(1));
            Assert.That(Lines(alone), Is.EqualTo(new[] { "host line", "before" }));
            Assert.That(alone.ExitCode, Is.EqualTo(1));
        });
    }

    // A run past its budget is ended at once: the worker is killed (never what the script started for the person) and
    // the next run starts another. Fails with no kill: the run would wait its 10 s out.
    [Test]
    public async Task ARunPastItsBudgetKillsTheWorkerButNotWhatTheScriptStarted()
    {
        string childFile = Path.Combine(_folder, "child.txt");
        string script = Script("slow.ps1", $$"""
            param([string]$TitleBase64,[string]$Mode,[int]$DeadlineMs)
            if($Mode -eq 'query'){
                $child=Start-Process powershell.exe -ArgumentList '-NoProfile','-Command','Start-Sleep 30' -WindowStyle Hidden -PassThru
                Set-Content -LiteralPath '{{childFile}}' -Value $child.Id
                Start-Sleep -Seconds 10
            }
            "pid=$PID"
            """);
        using var worker = new PowerShellScriptWorker(script);
        _ = await worker.RunAsync("powershell.exe", Arguments(script, "x", "exact"), TimeSpan.FromSeconds(60), CancellationToken.None);
        int first = worker.WorkerProcessId ?? 0;

        var clock = Stopwatch.StartNew();
        Assert.ThrowsAsync<TimeoutException>(async () => await worker.RunAsync(
            "powershell.exe", Arguments(script, "x", "query"), TimeSpan.FromSeconds(3), CancellationToken.None));
        clock.Stop();
        int child = int.Parse(File.ReadAllText(childFile).Trim(), System.Globalization.CultureInfo.InvariantCulture);
        try
        {
            ExternalProcessResult after = await worker.RunAsync(
                "powershell.exe", Arguments(script, "x", "exact"), TimeSpan.FromSeconds(60), CancellationToken.None);
            Assert.Multiple(() =>
            {
                Assert.That(clock.Elapsed, Is.LessThan(TimeSpan.FromSeconds(6)));
                Assert.That(Exited(first), Is.True, "the worker was killed");
                Assert.That(Exited(child), Is.False, "what the script started is not");
                Assert.That(worker.Starts, Is.EqualTo(2));
                Assert.That(after.Output, Does.Contain($"pid={worker.WorkerProcessId}"));
                Assert.That(worker.WorkerProcessId, Is.Not.EqualTo(first));
            });
        }
        finally
        {
            try
            {
                using Process process = Process.GetProcessById(child);
                process.Kill();
            }
            catch (ArgumentException)
            {
            }
        }
    }

    [Test]
    public async Task ACancelledRunKillsTheWorkerAndADeadWorkerIsReplaced()
    {
        string script = Script("wait.ps1", """
            param([string]$TitleBase64,[string]$Mode,[int]$DeadlineMs)
            if($Mode -eq 'query'){Start-Sleep -Seconds 10}
            "pid=$PID"
            """);
        using var worker = new PowerShellScriptWorker(script);
        _ = await worker.RunAsync("powershell.exe", Arguments(script, "x", "exact"), TimeSpan.FromSeconds(60), CancellationToken.None);
        int first = worker.WorkerProcessId ?? 0;

        using var cancel = new CancellationTokenSource(TimeSpan.FromSeconds(1));
        Assert.CatchAsync<OperationCanceledException>(async () => await worker.RunAsync(
            "powershell.exe", Arguments(script, "x", "query"), TimeSpan.FromSeconds(60), cancel.Token));
        Assert.That(Exited(first), Is.True);

        _ = await worker.RunAsync("powershell.exe", Arguments(script, "x", "exact"), TimeSpan.FromSeconds(60), CancellationToken.None);
        int second = worker.WorkerProcessId ?? 0;
        using (Process process = Process.GetProcessById(second))
            process.Kill();
        Assert.That(SpinWait.SpinUntil(() => Exited(second), 5000), Is.True);
        ExternalProcessResult third = await worker.RunAsync(
            "powershell.exe", Arguments(script, "x", "exact"), TimeSpan.FromSeconds(60), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(worker.Starts, Is.EqualTo(3));
            Assert.That(third.Output, Does.Contain($"pid={worker.WorkerProcessId}"));
        });
    }

    // A run while another is in progress does not wait for it: it runs in its own process, as every run did before.
    [Test]
    public async Task ARunWhileAnotherIsInProgressRunsInItsOwnProcessWithoutWaiting()
    {
        string script = Script("busy.ps1", """
            param([string]$TitleBase64,[string]$Mode,[int]$DeadlineMs)
            if($Mode -eq 'query'){Start-Sleep -Seconds 6}
            "pid=$PID"
            """);
        using var worker = new PowerShellScriptWorker(script);
        _ = await worker.RunAsync("powershell.exe", Arguments(script, "x", "exact"), TimeSpan.FromSeconds(60), CancellationToken.None);
        int workerPid = worker.WorkerProcessId ?? 0;

        Task<ExternalProcessResult> slow = worker.RunAsync(
            "powershell.exe", Arguments(script, "x", "query"), TimeSpan.FromSeconds(60), CancellationToken.None).AsTask();
        await Task.Delay(300);
        var clock = Stopwatch.StartNew();
        ExternalProcessResult beside = await worker.RunAsync(
            "powershell.exe", Arguments(script, "x", "exact"), TimeSpan.FromSeconds(60), CancellationToken.None);
        clock.Stop();
        ExternalProcessResult waited = await slow;

        Assert.Multiple(() =>
        {
            Assert.That(clock.Elapsed, Is.LessThan(TimeSpan.FromSeconds(4)), "it did not wait for the slow run");
            Assert.That(beside.Output, Does.Not.Contain($"pid={workerPid}"));
            Assert.That(waited.Output, Does.Contain($"pid={workerPid}"));
            Assert.That(worker.Starts, Is.EqualTo(1));
        });
    }

    // Only a run of the worker's own script with the worker's flags goes to it; every other run is its own process.
    [Test]
    public void OnlyItsOwnScriptWithItsFlagsGoesToTheWorker()
    {
        string script = Script("own.ps1", "'x'");
        using var worker = new PowerShellScriptWorker(script);

        Assert.Multiple(() =>
        {
            Assert.That(worker.ToRequest("powershell.exe", Arguments(script, "x", "exact")), Is.Not.Null);
            Assert.That(worker.ToRequest("powershell.exe", Arguments(Path.Combine(_folder, "other.ps1"), "x", "exact")), Is.Null);
            Assert.That(worker.ToRequest("pwsh.exe", Arguments(script, "x", "exact")), Is.Null);
            Assert.That(worker.ToRequest("powershell.exe", ["-NoProfile", "-NonInteractive", "-File", script, "x"]), Is.Null);
        });
    }

    // Renew al máximo (w5): the key script's copy and paste are a switch last (-CopySelection, -PasteClipboard). The worker
    // took such a run for its own process, a powershell.exe and an Add-Type compiled for every copy and paste; it now
    // binds the switch present as -File binds it, and the script answers the same from both.
    private const string Switches = """
        [CmdletBinding(DefaultParameterSetName='Pointer')]
        param(
            [Parameter(Mandatory=$true,ParameterSetName='Pointer')][ValidateSet('click','move_center')][string]$PointerAction,
            [Parameter(Mandatory=$true,ParameterSetName='Paste')][switch]$PasteClipboard,
            [Parameter(Mandatory=$true,ParameterSetName='Copy')][switch]$CopySelection
        )
        [pscustomobject]@{set=$PSCmdlet.ParameterSetName;copy=[bool]$CopySelection;paste=[bool]$PasteClipboard;pointer=$PointerAction}|ConvertTo-Json -Compress
        """;

    [TestCase("-CopySelection")]
    [TestCase("-PasteClipboard")]
    [TestCase("-PointerAction", "click")]
    public async Task ASwitchLastIsBoundInTheWorkerAsTheFileBindsIt(params string[] named)
    {
        string script = Script("switches.ps1", Switches);
        using var worker = new PowerShellScriptWorker(script);
        string[] arguments = ["-NoProfile", "-NonInteractive", "-STA", "-File", script, .. named];

        string? request = worker.ToRequest("powershell.exe", arguments);
        ExternalProcessResult inWorker = await worker.RunAsync("powershell.exe", arguments, TimeSpan.FromSeconds(60), CancellationToken.None);
        ExternalProcessResult alone = await new ExternalProcessRunner().RunAsync(
            "powershell.exe", arguments, TimeSpan.FromSeconds(60), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(request, Is.Not.Null, "the run goes to the worker");
            Assert.That(worker.Starts, Is.EqualTo(1));
            Assert.That(inWorker.ExitCode, Is.Zero);
            Assert.That(LastLine(inWorker), Is.EqualTo(LastLine(alone)));
            Assert.That(LastLine(inWorker), Does.Contain(named[0] switch
            {
                "-CopySelection" => "\"set\":\"Copy\",\"copy\":true",
                "-PasteClipboard" => "\"set\":\"Paste\",\"copy\":false,\"paste\":true",
                _ => "\"set\":\"Pointer\"",
            }));
        });
    }

    // The product's key script goes to its persistent worker: copy and paste no longer start a PowerShell each.
    [Test]
    public void TheProductRunsTheKeyScriptInThePersistentWorker()
    {
        string script = Script("DesktopKeyPress.ps1", "'x'");
        IExternalProcessRunner runner = WindowsDesktopInteractionAdapter.KeyScriptRunner(script);
        using var disposable = runner as IDisposable;

        Assert.Multiple(() =>
        {
            Assert.That(runner, Is.InstanceOf<PowerShellScriptWorker>());
            Assert.That(((PowerShellScriptWorker)runner).ToRequest(
                "powershell.exe", ["-NoProfile", "-NonInteractive", "-STA", "-File", script, "-CopySelection"]), Is.Not.Null);
        });
    }

    [Test]
    public async Task DisposeEndsTheWorker()
    {
        string script = Script("one.ps1", "param([string]$TitleBase64,[string]$Mode,[int]$DeadlineMs)\n'x'");
        var worker = new PowerShellScriptWorker(script);
        _ = await worker.RunAsync("powershell.exe", Arguments(script, "x", "exact"), TimeSpan.FromSeconds(60), CancellationToken.None);
        int pid = worker.WorkerProcessId ?? 0;

        worker.Dispose();

        Assert.That(SpinWait.SpinUntil(() => Exited(pid), 5000), Is.True);
    }

    private static bool Exited(int pid)
    {
        try
        {
            using Process process = Process.GetProcessById(pid);
            return process.HasExited;
        }
        catch (ArgumentException)
        {
            return true;
        }
    }
}

/// <summary>
/// Renew al máximo (rendimiento): the Spotify script's discovery looked every 300 ms and its search page, detail and
/// playback waits every 500 ms, so each saw what it waited for up to that late. They look every 100 ms, with the same
/// horizons (12.5 s, 12/20 s, 12 s, 15 s) and the same conditions.
/// </summary>
[TestFixture]
public sealed class SpotifyPollIntervalTests
{
    [Test]
    public void EveryWaitOfTheScriptLooksEvery100MsWithinItsOwnHorizon()
    {
        string script = File.ReadAllText(Path.Combine(AppContext.BaseDirectory, "SpotifyDesktopAutomation.ps1"));
        string[] loops = Regex.Matches(script, @"while\(\(Wait-BaxyPoll \$(\w+) ([^)]+)\)\)")
            .Select(match => match.Groups[1].Value + " " + match.Groups[2].Value)
            .ToArray();

        Assert.Multiple(() =>
        {
            Assert.That(loops, Is.EqualTo(new[]
            {
                "foregroundDeadline 25", "searchDeadline $pollMs", "searchPageDeadline $pollMs",
                "detailDeadline $pollMs", "deadline $pollMs",
            }));
            Assert.That(script, Does.Contain("\n$pollMs=100"));
            Assert.That(script, Does.Contain("$searchDeadline=(Get-Date).AddMilliseconds(12500)"));
            Assert.That(script, Does.Contain("$searchPageDeadline=$searchedAt.AddSeconds(12)"));
            Assert.That(script, Does.Contain("$searchPageDeadline=$searchedAt.AddSeconds(20)"));
            Assert.That(script, Does.Contain("$detailDeadline=(Get-Date).AddSeconds(12)"));
            Assert.That(script, Does.Contain("$deadline=(Get-Date).AddSeconds(15)"));
        });
    }
}
