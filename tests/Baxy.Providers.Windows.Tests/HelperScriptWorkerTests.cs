using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Renew al máximo (rendimiento): calculator.expression.evaluate and filesystem.folder.open ran their script in a
/// PowerShell started cold for each call (its start and its UI Automation load were most of a Calculator evaluation).
/// With the product's UI Automation worker they run there: the same script and arguments, no process started, and a
/// worker that does not answer is the same failure as a script over its budget.
/// </summary>
[TestFixture]
public sealed class HelperScriptWorkerTests
{
    [Test]
    public async Task TheCalculatorScriptRunsInTheWorkerWithoutStartingAPowerShell()
    {
        using var root = new Root();
        var runner = new CountingRunner();
        var worker = new AnsweringWorker(_ => Line(
            """{"ok":true,"typed":"6*7","method":"invoke","pressed":4,"displayName":"Se muestra 42","expressionName":"6 × 7=","value":"42"}"""));
        var adapter = new WindowsDeviceControlAdapter(root.Scans, root.Path, runner) { Scripts = worker };

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "calculator.expression.evaluate", Json("""{"expression":"6 * 7"}"""), CancellationToken.None);

        JsonObject command = worker.Commands.Single();
        Assert.Multiple(() =>
        {
            Assert.That(runner.Calls, Is.Zero, "no PowerShell is started for the script");
            Assert.That((string?)command["cmd"], Is.EqualTo("script"));
            Assert.That((string?)command["script"], Is.EqualTo(WindowsDeviceControlAdapter.CalculatorScript));
            Assert.That(Decoded(command["args"]![0]), Is.EqualTo("6*7"));
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("value").GetString(), Is.EqualTo("42"));
        });
    }

    // The script's own refusal keeps its code and its «nothing pressed», as from its own PowerShell.
    [Test]
    public async Task TheCalculatorScriptsRefusalReadsTheSameFromTheWorker()
    {
        using var root = new Root();
        const string Refusal = """{"ok":false,"error":"calculator_mode_not_supported"}""";
        ExternalCapabilityReceipt fromWorker = await new WindowsDeviceControlAdapter(
                root.Scans, root.Path, new CountingRunner()) { Scripts = new AnsweringWorker(_ => Line(Refusal)) }
            .InvokeAsync("calculator.expression.evaluate", Json("""{"expression":"6*7"}"""), CancellationToken.None);
        ExternalCapabilityReceipt fromProcess = await new WindowsDeviceControlAdapter(
                root.Scans, root.Path, new CountingRunner(Refusal))
            .InvokeAsync("calculator.expression.evaluate", Json("""{"expression":"6*7"}"""), CancellationToken.None);

        AssertSame(fromWorker, fromProcess, "calculator_mode_not_supported");
    }

    // A script that wrote no receipt (it threw) is the display not read, possibly pressed, from either.
    [Test]
    public async Task ACalculatorScriptWithoutAReceiptReadsTheSameFromTheWorker()
    {
        using var root = new Root();
        ExternalCapabilityReceipt fromWorker = await new WindowsDeviceControlAdapter(
                root.Scans, root.Path, new CountingRunner())
            {
                Scripts = new AnsweringWorker(_ => """{"ok":false,"error":"visible_controls_uia_failed","detail":"x"}"""),
            }
            .InvokeAsync("calculator.expression.evaluate", Json("""{"expression":"6*7"}"""), CancellationToken.None);
        ExternalCapabilityReceipt fromProcess = await new WindowsDeviceControlAdapter(
                root.Scans, root.Path, new CountingRunner(string.Empty))
            .InvokeAsync("calculator.expression.evaluate", Json("""{"expression":"6*7"}"""), CancellationToken.None);

        AssertSame(fromWorker, fromProcess, "calculator_display_not_read");
    }

    [Test]
    public async Task ACalculatorWorkerThatDoesNotAnswerIsAScriptOverItsBudget()
    {
        using var root = new Root();
        ExternalCapabilityReceipt fromWorker = await new WindowsDeviceControlAdapter(
                root.Scans, root.Path, new CountingRunner()) { Scripts = new AnsweringWorker(_ => null) }
            .InvokeAsync("calculator.expression.evaluate", Json("""{"expression":"6*7"}"""), CancellationToken.None);
        ExternalCapabilityReceipt fromProcess = await new WindowsDeviceControlAdapter(
                root.Scans, root.Path, new CountingRunner(failure: new TimeoutException()))
            .InvokeAsync("calculator.expression.evaluate", Json("""{"expression":"6*7"}"""), CancellationToken.None);

        AssertSame(fromWorker, fromProcess, "windows_device_adapter_failed");
    }

    // Renew al máximo (w5): the brightness's set, step and read ran in a PowerShell started cold for each call (400-700 ms
    // on the notebook against 10-20 ms for the WMI read itself); with the worker they run there, same script and level.
    [TestCase("system.settings.set", """{"setting":"brightness","value":40}""", "40")]
    [TestCase("system.settings.adjust", """{"setting":"brightness","direction":"down","amount":10}""", "-10")]
    [TestCase("system.settings.status", """{"setting":"brightness"}""", null)]
    public async Task TheBrightnessScriptsRunInTheWorkerWithoutStartingAPowerShell(
        string operation, string arguments, string? level)
    {
        using var root = new Root();
        var runner = new CountingRunner();
        var worker = new AnsweringWorker(_ => Line(
            """{"ok":true,"effectObserved":true,"changed":true,"baselineValues":[50],"values":[40],"monitors":[{"instanceName":"m","value":40}]}"""));
        var adapter = new WindowsDeviceControlAdapter(root.Scans, root.Path, runner) { Scripts = worker };

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(operation, Json(arguments), CancellationToken.None);

        JsonObject command = worker.Commands.Single();
        string expected = operation switch
        {
            "system.settings.set" => WindowsDeviceControlAdapter.BrightnessScript,
            "system.settings.adjust" => WindowsDeviceControlAdapter.BrightnessAdjustScript,
            _ => WindowsDeviceControlAdapter.BrightnessStatusScript,
        };
        Assert.Multiple(() =>
        {
            Assert.That(runner.Calls, Is.Zero, "no PowerShell is started for the script");
            Assert.That((string?)command["script"], Is.EqualTo(expected));
            Assert.That(command["args"]!.AsArray().Select(node => (string?)node),
                Is.EqualTo(level is null ? Array.Empty<string>() : new[] { level }));
            Assert.That(receipt.Verified, Is.True);
        });
    }

    // Renew al máximo (w5): a set or a step is read back every 100 ms within 1.5 s, never once after a fixed 300 ms (a
    // panel still fading towards the level was told a failure).
    [Test]
    public void TheBrightnessIsReadBackOftenUntilItIsReached()
    {
        foreach (string script in new[]
            { WindowsDeviceControlAdapter.BrightnessScript, WindowsDeviceControlAdapter.BrightnessAdjustScript })
        {
            Assert.Multiple(() =>
            {
                Assert.That(script, Does.Not.Contain("Start-Sleep -Milliseconds 300"));
                Assert.That(script, Does.Contain("$deadline=(Get-Date).AddMilliseconds(1500)"));
                Assert.That(script, Does.Contain("do{Start-Sleep -Milliseconds 100"));
                Assert.That(script, Does.Contain("-and (Get-Date) -lt $deadline)"));
            });
        }
    }

    // Renew al máximo (w5): a Wi-Fi connection was looked at by a PowerShell started cold every 500 ms (each look about a
    // second); with the worker the status is read there and looked at every 100 ms within the same 15 s, and only the
    // connection itself (netsh wlan connect) starts a process.
    [Test]
    public async Task TheWifiConnectionIsLookedAtInTheWorkerEvery100Ms()
    {
        using var root = new Root();
        var runner = new CountingRunner();
        int looks = 0;
        var worker = new AnsweringWorker(command => (string?)command["script"] == WindowsDeviceControlAdapter.WifiProfilesScript
            ? Line("""{"ok":true,"profiles":["Casa"]}""")
            : ++looks <= 3
                ? Line("""{"ok":true,"connected":false,"profile":""}""")
                : Line("""{"ok":true,"connected":true,"profile":"Casa"}"""));
        var pauses = new List<TimeSpan>();
        var adapter = new WindowsDeviceControlAdapter(root.Scans, root.Path, runner, (pause, _) =>
        {
            pauses.Add(pause);
            return ValueTask.CompletedTask;
        }) { Scripts = worker };

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "wifi.connect.named", Json("""{"profileName":"Casa"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(runner.Calls, Is.EqualTo(1), "only netsh wlan connect starts a process");
            Assert.That(looks, Is.EqualTo(4), "one read before, three after until it is connected");
            Assert.That(pauses, Is.EqualTo(Enumerable.Repeat(TimeSpan.FromMilliseconds(100), 2)));
        });
    }

    [TestCase("wifi.connect.named", """{"profileName":"Casa"}""", "wifi_connect_not_verified", 150)]
    [TestCase("wifi.disconnect", "{}", "wifi_disconnect_not_verified", 60)]
    public async Task AWifiChangeNeverSeenKeepsItsHorizonAt100MsInTheWorker(
        string operation, string arguments, string code, int expectedPauses)
    {
        using var root = new Root();
        bool connecting = operation == "wifi.connect.named";
        var worker = new AnsweringWorker(command => (string?)command["script"] == WindowsDeviceControlAdapter.WifiProfilesScript
            ? Line("""{"ok":true,"profiles":["Casa"]}""")
            : connecting
                ? Line("""{"ok":true,"connected":false,"profile":""}""")
                : Line("""{"ok":true,"connected":true,"profile":"Casa"}"""));
        var pauses = new List<TimeSpan>();
        var adapter = new WindowsDeviceControlAdapter(root.Scans, root.Path, new CountingRunner(), (pause, _) =>
        {
            pauses.Add(pause);
            return ValueTask.CompletedTask;
        }) { Scripts = worker };

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(operation, Json(arguments), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo(code));
            Assert.That(pauses, Has.Count.EqualTo(expectedPauses));
            Assert.That(pauses, Has.All.EqualTo(TimeSpan.FromMilliseconds(100)));
        });
    }

    [Test]
    public async Task TheFolderScriptRunsInTheWorkerWithItsArgumentsByPosition()
    {
        using var root = new Root();
        await File.WriteAllTextAsync(root.FolderScript, "param($Folder,$Subdirectory) # fixture");
        var runner = new CountingRunner();
        var worker = new AnsweringWorker(_ => Line(
            """{"version":1,"ok":true,"effectObserved":true,"folder":"home","authority":"windows_shell_location_postread"}"""));
        WindowsDesktopInteractionAdapter adapter = root.Interaction(runner, worker);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "filesystem.folder.open", Json("""{"folder":"home","subdirectory":"-raro/tesis"}"""), CancellationToken.None);
        ExternalCapabilityReceipt bare = await adapter.InvokeAsync(
            "filesystem.folder.open", Json("""{"folder":"downloads"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(runner.Calls, Is.Zero, "no PowerShell is started for the script");
            Assert.That((string?)worker.Commands[0]["script"], Is.EqualTo("param($Folder,$Subdirectory) # fixture"));
            Assert.That(worker.Commands[0]["args"]!.AsArray().Select(node => (string?)node),
                Is.EqualTo(new[] { "home", "-raro/tesis" }));
            Assert.That(worker.Commands[1]["args"]!.AsArray().Select(node => (string?)node),
                Is.EqualTo(new[] { "downloads" }));
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(bare.Verified, Is.True);
        });
    }

    [Test]
    public async Task AFolderWorkerThatDoesNotAnswerIsAScriptOverItsBudget()
    {
        using var root = new Root();
        ExternalCapabilityReceipt fromWorker = await root.Interaction(new CountingRunner(), new AnsweringWorker(_ => null))
            .InvokeAsync("filesystem.folder.open", Json("""{"folder":"home"}"""), CancellationToken.None);
        ExternalCapabilityReceipt fromProcess = await root.Interaction(
                new CountingRunner(failure: new TimeoutException()), worker: null)
            .InvokeAsync("filesystem.folder.open", Json("""{"folder":"home"}"""), CancellationToken.None);

        AssertSame(fromWorker, fromProcess, "desktop_interaction_adapter_failed");
    }

    [Test]
    public async Task AFolderScriptWithoutAReceiptReadsTheSameFromTheWorker()
    {
        using var root = new Root();
        ExternalCapabilityReceipt fromWorker = await root.Interaction(
                new CountingRunner(), new AnsweringWorker(_ => """{"ok":false,"error":"script_no_receipt"}"""))
            .InvokeAsync("filesystem.folder.open", Json("""{"folder":"home"}"""), CancellationToken.None);
        ExternalCapabilityReceipt fromProcess = await root.Interaction(new CountingRunner(string.Empty), worker: null)
            .InvokeAsync("filesystem.folder.open", Json("""{"folder":"home"}"""), CancellationToken.None);

        AssertSame(fromWorker, fromProcess, "desktop_interaction_no_receipt");
    }

    // The product's folder script in the product's worker and in its own PowerShell, on refusals that open nothing:
    // the receipt it writes before its «exit 2» arrives from both, with the same code.
    [TestCase("..", "known_subdirectory_invalid")]
    [TestCase("baxy-no-such-folder-7f3e", "known_folder_missing")]
    public async Task TheProductsFolderScriptRefusesTheSameInTheWorker(string subdirectory, string code)
    {
        string script = Path.Combine(AppContext.BaseDirectory, "KnownFolderOpen.ps1");
        string missing = Path.Combine(Path.GetTempPath(), "baxy-missing-" + Guid.NewGuid().ToString("N"));
        using var worker = new UiaWorkerHost(Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1"));
        string arguments = $$"""{"folder":"home","subdirectory":"{{subdirectory}}"}""";
        ExternalCapabilityReceipt fromWorker = await Product(script, missing, worker)
            .InvokeAsync("filesystem.folder.open", Json(arguments), CancellationToken.None);
        ExternalCapabilityReceipt fromProcess = await Product(script, missing, worker: null)
            .InvokeAsync("filesystem.folder.open", Json(arguments), CancellationToken.None);

        AssertSame(fromWorker, fromProcess, code);
    }

    // The new window is looked for every 100 ms (it was every 250 ms) within the same 8 s.
    [Test]
    public void TheFolderScriptLooksForTheNewWindowOftenWithinTheSameBudget()
    {
        string script = File.ReadAllText(Path.Combine(AppContext.BaseDirectory, "KnownFolderOpen.ps1"));
        Assert.Multiple(() =>
        {
            Assert.That(script, Does.Contain("$deadline=(Get-Date).AddSeconds(8)"));
            Assert.That(script, Does.Contain("while((Wait-BaxyPoll $deadline 100))"));
        });
    }

    private static WindowsDesktopInteractionAdapter Product(string folderScript, string missing, IUiaWorker? worker) =>
        new(new ExternalProcessRunner(), folderScript, missing, missing, missing) { Scripts = worker };

    private static void AssertSame(ExternalCapabilityReceipt fromWorker, ExternalCapabilityReceipt fromProcess, string code) =>
        Assert.Multiple(() =>
        {
            Assert.That(fromProcess.ErrorCode, Is.EqualTo(code));
            Assert.That(fromWorker.ErrorCode, Is.EqualTo(fromProcess.ErrorCode));
            Assert.That(fromWorker.Verified, Is.EqualTo(fromProcess.Verified));
            Assert.That(fromWorker.EffectObserved, Is.EqualTo(fromProcess.EffectObserved));
            Assert.That(fromWorker.EffectMayHaveOccurred, Is.EqualTo(fromProcess.EffectMayHaveOccurred));
        });

    // The worker's answer to «script»: the script's last JSON line.
    private static string Line(string json) =>
        new JsonObject { ["ok"] = true, ["error"] = string.Empty, ["line"] = json }.ToJsonString();

    private static string Decoded(JsonNode? encoded) =>
        Encoding.UTF8.GetString(Convert.FromBase64String((string)encoded!));

    private static JsonElement Json(string json) => JsonDocument.Parse(json).RootElement.Clone();

    private sealed class Root : IDisposable
    {
        internal Root()
        {
            Directory.CreateDirectory(Path);
            foreach (string name in new[] { "KnownFolderOpen.ps1", "KnownFileOpen.ps1", "DesktopSelectAll.ps1", "DesktopKeyPress.ps1" })
                File.WriteAllText(System.IO.Path.Combine(Path, name), "# test fixture");
        }

        internal string Path { get; } = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "baxy-worker-script-" + Guid.NewGuid().ToString("N"));

        internal string Scans => System.IO.Path.Combine(Path, "scans");

        internal string FolderScript => System.IO.Path.Combine(Path, "KnownFolderOpen.ps1");

        internal WindowsDesktopInteractionAdapter Interaction(IExternalProcessRunner runner, IUiaWorker? worker) =>
            new(runner,
                FolderScript,
                System.IO.Path.Combine(Path, "KnownFileOpen.ps1"),
                System.IO.Path.Combine(Path, "DesktopSelectAll.ps1"),
                System.IO.Path.Combine(Path, "DesktopKeyPress.ps1"))
            {
                Scripts = worker,
            };

        public void Dispose()
        {
            if (Directory.Exists(Path))
                Directory.Delete(Path, recursive: true);
        }
    }

    private sealed class AnsweringWorker(Func<JsonObject, string?> answer) : IUiaWorker
    {
        internal List<JsonObject> Commands { get; } = [];

        public ValueTask<JsonDocument?> SendAsync(string commandJson, TimeSpan timeout, CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            JsonObject command = JsonNode.Parse(commandJson)!.AsObject();
            Commands.Add(command);
            return ValueTask.FromResult(answer(command) is { } line ? JsonDocument.Parse(line) : null);
        }
    }

    private sealed class CountingRunner(string output = "", Exception? failure = null) : IExternalProcessRunner
    {
        internal int Calls { get; private set; }

        public ValueTask<ExternalProcessResult> RunAsync(
            string executable, IReadOnlyList<string> arguments, TimeSpan timeout, CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            Calls++;
            if (failure is not null)
                throw failure;
            return ValueTask.FromResult(new ExternalProcessResult(0, output, string.Empty));
        }
    }
}
