using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Text.Json.Nodes;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// API1 (12-11-2026, a friend of the owner's with a 4 GB card): BAXY's own model read too slowly to ever load, and he turned
/// on «Usar otro modelo» («Se aplica al momento. Con esto activo, BAXY no carga su propio modelo»), saved his key and chose a
/// model. Settings stayed on «Cambiando…» and the start card went on preparing BAXY's own model: the change waited for that
/// start (MainWindowViewModel.SwitchMindAsync on _mindStart) and for the «hola» he wrote, which waited for a mind (_turnGate).
/// Here the own model's start is the fake mind holding catalog.configure, and the other model is «Otra» at an address of
/// this PC where nobody answers: the translator starts without asking it (NoCheckVariable), so nothing leaves this PC.
/// </summary>
[TestFixture]
[NonParallelizable]
public sealed class OtherModelWhileOwnLoadsTests
{
    private const BindingFlags Private = BindingFlags.Instance | BindingFlags.NonPublic;
    private const string Key = "sk-clave-de-prueba";
    private string _root = "";
    private string? _localAppData;
    private Process? _core;

    [SetUp]
    public void SetUp()
    {
        _root = Directory.CreateTempSubdirectory("baxy-api1-").FullName;
        _localAppData = Environment.GetEnvironmentVariable("LOCALAPPDATA");
        Environment.SetEnvironmentVariable("LOCALAPPDATA", _root);
        string? repository = AppContext.BaseDirectory;
        while (repository is not null && !Directory.Exists(Path.Combine(repository, "src", "baxy_mind")))
        {
            repository = Path.GetDirectoryName(repository);
        }

        string python = Path.Combine(repository ?? string.Empty, ".venv-modelo-api", "Scripts", "python.exe");
        Assume.That(File.Exists(python), ".venv-modelo-api, with the SDK, is not on this machine");
        Environment.SetEnvironmentVariable(ExternalModel.PythonVariable, python);
        Environment.SetEnvironmentVariable(ExternalModel.NoCheckVariable, "1");
    }

    [TearDown]
    public void TearDown()
    {
        if (_core is { } core)
        {
            try
            {
                core.Kill();
                core.WaitForExit(5000);
            }
            catch (InvalidOperationException)
            {
                // already ended
            }

            core.Dispose();
            _core = null;
        }

        foreach (string name in new[]
        {
            ExternalModel.PythonVariable, ExternalModel.NoCheckVariable, "BAXY_MIND_LLAMA_REMOTE", MindSidecarClient.TurnSecondsVariable,
            "BAXY_RENEW_PREFILL", "BAXY_RENEW_WAKE_WARM", "BAXY_VISION_ENDPOINT", "BAXY_RENEW_CTX",
        })
        {
            Environment.SetEnvironmentVariable(name, null);
        }

        Environment.SetEnvironmentVariable("LOCALAPPDATA", _localAppData);
        Directory.Delete(_root, recursive: true);
    }

    private static JsonObject Loading() => new() { ["hold"] = new JsonObject { ["catalog.configure"] = "never" } };

    private static JsonObject TooSlow() => new()
    {
        ["reply"] = new JsonObject
        {
            ["catalog.configure"] = new JsonObject
            {
                ["type"] = "error",
                ["startup"] = new JsonObject { ["cause"] = "lectura_lenta", ["tokensPerS"] = 20, ["needMinutes"] = 42 },
            },
        },
    };

    // «Otra», chosen whole, at an address of this PC: any other model goes the same way.
    private static JsonObject Other() => new()
    {
        ["provider"] = "compatible", ["url"] = "http://127.0.0.1:9160/v1", ["model"] = "modelo-de-prueba", ["key"] = Key,
    };

    // The engine counts as up (a process of this test's own stands for it), so a switch may start a mind.
    private void CoreUp(MainWindowViewModel viewModel)
    {
        _core = Process.Start(new ProcessStartInfo("ping", "-n 600 127.0.0.1") { CreateNoWindow = true, UseShellExecute = false })!;
        var core = new CoreProcessClient();
        typeof(CoreProcessClient).GetField("_ready", Private)!.SetValue(core, true);
        typeof(CoreProcessClient).GetField("_process", Private)!.SetValue(core, _core);
        typeof(MainWindowViewModel).GetField("_coreClient", Private)!.SetValue(viewModel, core);
        typeof(MainWindowViewModel).GetProperty(nameof(MainWindowViewModel.IsReady))!.SetValue(viewModel, true);
    }

    // The translator runs from the mind's path (ExternalModel.TranslatorProcess), here the fake's: the real one goes beside it.
    private static FakeMind WithTranslator(FakeMind fake)
    {
        string? repository = AppContext.BaseDirectory;
        while (repository is not null && !Directory.Exists(Path.Combine(repository, "src", "baxy_mind")))
        {
            repository = Path.GetDirectoryName(repository);
        }

        File.Copy(Path.Combine(repository!, "src", "baxy_mind", "external_model.py"), Path.Combine(fake.Folder, "baxy_mind", "external_model.py"));
        return fake;
    }

    private ExternalModel Model(MainWindowViewModel viewModel)
    {
        var model = new ExternalModel(_root);
        typeof(MainWindowViewModel).GetField("_externalModel", Private)!.SetValue(viewModel, model);
        return model;
    }

    // Before the view model ends: its engine is this test's process, which the test ends itself.
    private static void CoreDown(MainWindowViewModel viewModel) =>
        typeof(MainWindowViewModel).GetField("_coreClient", Private)!.SetValue(viewModel, null);

    [Test]
    public async Task TurnedOnWhileItsOwnModelLoadsItAppliesInSecondsAndTheLoadEnds()
    {
        using FakeMind fake = WithTranslator(new FakeMind());
        fake.Script(Loading());
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        {
            CoreUp(viewModel);
            ExternalModel model = Model(viewModel);
            Task loading = ViewModelHarness.StartMindAsync(viewModel);
            Assert.That(await fake.WaitSeenAsync("catalog.configure"), Is.True);
            int loader = fake.LiveProcesses.Single();
            fake.Script(new JsonObject());

            Assert.That(model.Apply(Other()), Is.Null);
            Assert.That(model.Apply(new JsonObject { ["enabled"] = true }), Is.Null);
            var clock = Stopwatch.StartNew();
            viewModel.ExternalModelChanged();

            Assert.That(await ViewModelHarness.UntilAsync(() => !model.Switching, 30), Is.True, "«Cambiando…» for ever");
            Assert.Multiple(() =>
            {
                Assert.That(clock.Elapsed, Is.LessThan(TimeSpan.FromSeconds(20)));
                Assert.That(model.Active, Is.True);
                Assert.That(viewModel.IsMindReady, Is.True);
                Assert.That(fake.LiveProcesses, Does.Not.Contain(loader), "the own model's start is ended, not left behind");
                Assert.That(loading.IsCompleted, Is.True);
            });
            TestContext.Out.WriteLine($"API1: switch while loading took {clock.Elapsed.TotalSeconds:0.0} s");
            CoreDown(viewModel);
        }
    }

    [Test]
    public async Task WhatThePersonWroteWhileItLoadedIsAnsweredByTheModelTheyChose()
    {
        using FakeMind fake = WithTranslator(new FakeMind());
        fake.Script(Loading());
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            CoreUp(viewModel);
            ExternalModel model = Model(viewModel);
            _ = ViewModelHarness.StartMindAsync(viewModel);
            Assert.That(await fake.WaitSeenAsync("catalog.configure"), Is.True);
            Task<(int Status, JsonObject Body)> hola = view.SendAsync("POST", "/turn", new JsonObject { ["text"] = "hola" });
            Assert.That(await ViewModelHarness.UntilAsync(() => viewModel.IsAwaitingMind), Is.True, "it waits for the mind");
            fake.Script(new JsonObject());

            model.Apply(Other());
            model.Apply(new JsonObject { ["enabled"] = true });
            viewModel.ExternalModelChanged();

            Assert.That(await ViewModelHarness.UntilAsync(() => hola.IsCompleted, 30), Is.True, "the «hola» waits for ever");
            Assert.Multiple(() =>
            {
                Assert.That(hola.Result.Status, Is.EqualTo(200));
                Assert.That(model.Active, Is.True);
                Assert.That(fake.Requests("turn.decide").Select(static request => (string?)request["text"]), Is.EqualTo(new[] { "hola" }),
                    "answered once, by the mind on the model chosen");
                Assert.That(viewModel.LastTurnFailure, Is.Null);
            });
            CoreDown(viewModel);
        }
    }

    [Test]
    public async Task TurnedOnAfterTheBreakdownItConnectsAndTheBreakdownEnds()
    {
        using FakeMind fake = WithTranslator(new FakeMind());
        fake.Script(TooSlow());
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        {
            CoreUp(viewModel);
            ExternalModel model = Model(viewModel);
            await ViewModelHarness.StartMindAsync(viewModel);
            Assert.That(viewModel.Failure, Is.EqualTo(MainWindowViewModel.EngineUnavailable));
            fake.Script(new JsonObject());

            model.Apply(Other());
            model.Apply(new JsonObject { ["enabled"] = true });
            viewModel.ExternalModelChanged();

            Assert.That(await ViewModelHarness.UntilAsync(() => !model.Switching && viewModel.IsMindReady, 30), Is.True);
            Assert.Multiple(() =>
            {
                Assert.That(model.Active, Is.True);
                Assert.That(viewModel.Failure, Is.Null);
            });
            CoreDown(viewModel);
        }
    }

    [Test]
    public async Task OneThatDoesNotConnectIsSaidInSecondsEvenWhileItsOwnModelLoads()
    {
        // Its translator cannot start (here: none to start): the change ended, and Settings says why, without waiting
        // out the own model's start that follows it.
        Environment.SetEnvironmentVariable(ExternalModel.PythonVariable, Path.Combine(_root, "no-hay", "python.exe"));
        using FakeMind fake = WithTranslator(new FakeMind());
        fake.Script(Loading());
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        {
            CoreUp(viewModel);
            ExternalModel model = Model(viewModel);
            _ = ViewModelHarness.StartMindAsync(viewModel);
            Assert.That(await fake.WaitSeenAsync("catalog.configure"), Is.True);

            model.Apply(Other());
            model.Apply(new JsonObject { ["enabled"] = true });
            viewModel.ExternalModelChanged();

            Assert.That(await ViewModelHarness.UntilAsync(() => (bool?)model.Json()["switching"] == false, 20), Is.True,
                "«Cambiando…» until the own model's start ends");
            Assert.That((string?)model.Json()["problem"], Is.Not.Null);
            Assert.That(model.Active, Is.False);
            CoreDown(viewModel);
        }
    }

    [Test]
    public async Task TurnedOnAndBackOffWhileItsOwnModelLoadsAMindStillComes()
    {
        // Blind review of API1: the switch's own start (BAXY's own model) cut by turning it on, and that taken back before the
        // switch looked again: nothing was left to switch, and no mind came, nor any retry.
        using FakeMind fake = WithTranslator(new FakeMind());
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        {
            CoreUp(viewModel);
            ExternalModel model = Model(viewModel);
            model.Apply(Other());
            model.Apply(new JsonObject { ["enabled"] = true });
            await ViewModelHarness.StartMindAsync(viewModel);
            Assert.That(model.Active && viewModel.IsMindReady, Is.True);

            fake.Script(Loading());
            model.Apply(new JsonObject { ["enabled"] = false });
            viewModel.ExternalModelChanged();
            Assert.That(await fake.WaitSeenAsync("catalog.configure", 2), Is.True, "the switch starts BAXY's own model");
            fake.Script(new JsonObject());
            model.Apply(new JsonObject { ["enabled"] = true });
            viewModel.ExternalModelChanged();
            model.Apply(new JsonObject { ["enabled"] = false });
            viewModel.ExternalModelChanged();

            Assert.That(await ViewModelHarness.UntilAsync(() => !model.Switching && viewModel.IsMindReady, 20), Is.True,
                () => $"no mind: switching {model.Switching}, preparing {viewModel.IsMindPreparing}, failure {viewModel.Failure}, seen "
                    + string.Join(",", fake.Seen) + ", live " + fake.LiveProcesses.Count + ", " + model.Json()["problem"]);
            Assert.That(model.Active, Is.False);
            CoreDown(viewModel);
        }
    }

    [Test]
    public async Task OpenedWithItOnTheOwnModelIsNotLoaded()
    {
        // Point 4: a start with the other model chosen points the mind at its translator (BAXY_MIND_LLAMA_REMOTE), with which
        // the mind starts no llama-server (llm_server.LlmServer: «nothing is launched»).
        using FakeMind fake = WithTranslator(new FakeMind());
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        {
            ExternalModel model = Model(viewModel);
            model.Apply(Other());
            model.Apply(new JsonObject { ["enabled"] = true });

            await ViewModelHarness.StartMindAsync(viewModel);

            Assert.Multiple(() =>
            {
                Assert.That(model.Active, Is.True, model.Json().ToJsonString());
                Assert.That(viewModel.IsMindReady, Is.True);
                Assert.That(Environment.GetEnvironmentVariable("BAXY_MIND_LLAMA_REMOTE"), Is.Not.Null.And.Not.Empty);
            });
        }
    }
}
