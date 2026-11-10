using System.Diagnostics;
using System.IO;
using System.Net;
using System.Net.Http;
using System.Net.Sockets;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json.Nodes;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// QWB2 (documentacion/PLAN_QWEN_BASE.md §4, §6): BAXY's tuned model is downloaded only when the person asks, kept only with
/// the SHA-256 of the package's registration, used only once verified at a start, and the stock model comes back when it is
/// missing, damaged, turned off or removed. The downloads run against a real HTTP server on this PC.
/// </summary>
[TestFixture]
[NonParallelizable]
public sealed class TunedModelTests
{
    private const string Stock = @"C:\BAXY\models\Qwen3.5-4B-Q4_K_M.gguf";
    private const string StockSha256 = "00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4";
    private static readonly byte[] Content = Encoding.ASCII.GetBytes(string.Concat(Enumerable.Repeat("tuned model bytes. ", 40000)));
    private string _root = "";

    [SetUp]
    public void SetUp()
    {
        _root = Directory.CreateTempSubdirectory("baxy-tuned-model-").FullName;
        Environment.SetEnvironmentVariable(TunedModel.GgufVariable, Stock);
        Environment.SetEnvironmentVariable(MindRuntimeDiscovery.GgufSha256Variable, StockSha256);
    }

    [TearDown]
    public void TearDown()
    {
        Environment.SetEnvironmentVariable(TunedModel.GgufVariable, null);
        Environment.SetEnvironmentVariable(MindRuntimeDiscovery.GgufSha256Variable, null);
        Directory.Delete(_root, recursive: true);
    }

    [Test]
    public void WithoutAnOfferThereIsNothingToInstall()
    {
        using var model = new TunedModel(_root, () => null);

        Assert.That((bool?)model.Json()["available"], Is.False);
        Assert.That(model.Install(CancellationToken.None), Is.EqualTo("tuned_model_unavailable"));
    }

    [Test]
    public void ItIsOfferedNotInstalledAndNotUsed()
    {
        using var server = new Server(Content);
        using var model = Model(server);

        JsonObject json = model.Json();

        Assert.Multiple(() =>
        {
            Assert.That((bool?)json["available"], Is.True);
            Assert.That((bool?)json["installed"], Is.False);
            Assert.That((bool?)json["use"], Is.False);
            Assert.That((long?)json["bytes"], Is.EqualTo(Content.Length));
            Assert.That((string?)json["license"], Is.EqualTo("Apache-2.0"));
            Assert.That((string?)json["source"], Is.EqualTo("127.0.0.1"));
            Assert.That((string?)json["repo"], Is.EqualTo("REDSOULTM/resolve"));
        });
        Assert.That(model.Apply(new JsonObject { ["use"] = true }), Is.EqualTo("tuned_model_not_installed"));
    }

    [Test]
    public async Task InstallDownloadsIntoAPartAndKeepsItOnlyWithTheRegisteredHash()
    {
        using var server = new Server(Content);
        using var model = Model(server);
        var online = new List<string>();
        model.WentOnline += online.Add;

        Assert.That(model.Install(CancellationToken.None), Is.Null);
        await model.Installing!;

        Assert.Multiple(() =>
        {
            Assert.That(File.ReadAllBytes(InstalledPath), Is.EqualTo(Content));
            Assert.That(File.Exists(InstalledPath + ".part"), Is.False);
            Assert.That((bool?)model.Json()["installed"], Is.True);
            Assert.That(model.Json()["downloadProblem"], Is.Null);
            Assert.That(online, Is.EqualTo(new[] { "127.0.0.1" }), "it shows in «Salidas a internet»");
        });
    }

    [Test]
    public async Task ACutDownloadResumesWithRangeFromWhatItKept()
    {
        using var server = new Server(Content) { DropFirstAfter = 100_000 };
        using var model = Model(server);

        Assert.That(model.Install(CancellationToken.None), Is.Null);
        await model.Installing!;

        Assert.That(File.ReadAllBytes(InstalledPath), Is.EqualTo(Content));
        Assert.That(server.RangeStarts, Is.EqualTo(new long?[] { null, 100_000 }));
    }

    [Test]
    public async Task APartLeftByAnEarlierInstallIsResumed()
    {
        Directory.CreateDirectory(Path.GetDirectoryName(InstalledPath)!);
        File.WriteAllBytes(InstalledPath + ".part", Content[..250_000]);
        using var server = new Server(Content);
        using var model = Model(server);

        Assert.That((long?)model.Json()["downloadedBytes"], Is.EqualTo(250_000), "what it already downloaded is not lost");
        Assert.That(model.Install(CancellationToken.None), Is.Null);
        await model.Installing!;

        Assert.That(File.ReadAllBytes(InstalledPath), Is.EqualTo(Content));
        Assert.That(server.RangeStarts, Is.EqualTo(new long?[] { 250_000 }));
    }

    [Test]
    public async Task AResumedDownloadCountsWhatWasAlreadyThereOnce()
    {
        Directory.CreateDirectory(Path.GetDirectoryName(InstalledPath)!);
        File.WriteAllBytes(InstalledPath + ".part", Content[..250_000]);
        using var server = new Server(Content);
        using var model = Model(server);

        Assert.That(model.Install(CancellationToken.None), Is.Null);
        await model.Installing!;

        long counted = (long)typeof(TunedModel).GetField("_downloaded", System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic)!
            .GetValue(model)!;
        Assert.That(counted, Is.EqualTo(Content.Length), "«Llevo» never passes the model's size");
    }

    // MOD1 D6 / REV_VISTA V-06 (owner, 2026-11-09): the tuned model's download said only «Llevo X de Y», while Ollama's and its
    // models' say how fast they go and how long they have left (DownloadRate). The same figures, for the same bar.
    [Test]
    public async Task ADownloadSaysHowFastItGoesAndHowLongItHasLeft()
    {
        using var server = new Server(Content) { HoldAt = 500_000 };
        using var model = Model(server);
        Assert.That(model.Json()["downloadBytesPerSecond"], Is.Null, "nothing is being downloaded");

        Assert.That(model.Install(CancellationToken.None), Is.Null);

        // The line gave 250.000 bytes, 250.000 more a moment later, and holds the rest.
        Assert.That(() => (long?)model.Json()["downloadBytesPerSecond"], Is.GreaterThan(0).After(10_000, 50));
        JsonObject going = model.Json();
        long speed = (long)going["downloadBytesPerSecond"]!;
        Assert.Multiple(() =>
        {
            Assert.That((bool?)going["downloading"], Is.True);
            Assert.That((long?)going["downloadedBytes"], Is.LessThanOrEqualTo(500_000));
            Assert.That((long?)going["downloadSecondsLeft"], Is.InRange(1, (long)Math.Ceiling(Content.Length / (double)speed)));
        });

        server.Release();
        await model.Installing!;

        JsonObject done = model.Json();
        Assert.Multiple(() =>
        {
            Assert.That((bool?)done["installed"], Is.True);
            Assert.That(done["downloadBytesPerSecond"], Is.Null, "a download that ended has no speed");
            Assert.That(done["downloadSecondsLeft"], Is.Null);
        });
    }

    [Test]
    public async Task ReinstallingADamagedOneTheMindWasToUseSwitchesToItOnceItIsThere()
    {
        using var server = new Server(Content);
        using var model = Model(server);
        Install();
        model.Apply(new JsonObject { ["use"] = true });
        File.WriteAllBytes(InstalledPath, [.. Content[..^1], 0]);
        await model.StartAsync(CancellationToken.None);
        Assert.That(model.Problem, Is.EqualTo("ajustado_danado"));
        int installed = 0;
        model.Installed += () => installed++;

        Assert.That(model.Install(CancellationToken.None), Is.Null);
        Assert.That(model.NeedsSwitch, Is.False, "deleting the damaged file changes nothing for the mind running on the stock one");
        Assert.That(model.Problem, Is.Null);
        await model.Installing!;

        Assert.That(installed, Is.EqualTo(1));
        Assert.That(model.NeedsSwitch, Is.True);
        await model.StartAsync(CancellationToken.None);
        Assert.That(model.Active, Is.True);
    }

    [Test]
    public async Task AMissingOneIsNotSaidMissingOnceItIsBeingInstalledAgain()
    {
        using var server = new Server(Content);
        using var model = Model(server);
        Install();
        model.Apply(new JsonObject { ["use"] = true });
        File.Delete(InstalledPath);
        await model.StartAsync(CancellationToken.None);
        Assert.That(model.Problem, Is.EqualTo("ajustado_ausente"));

        Assert.That(model.Install(CancellationToken.None), Is.Null);

        Assert.That(model.Problem, Is.Null);
        await model.Installing!;
    }

    [Test]
    public async Task AFileTheClosingServerStillHoldsForAMomentIsRemovedAtTheSameStart()
    {
        using var model = Model(new Server(Content));
        Install();
        model.Apply(new JsonObject { ["use"] = true });
        await model.StartAsync(CancellationToken.None);
        model.Apply(new JsonObject { ["remove"] = true });
        var held = new FileStream(InstalledPath, FileMode.Open, FileAccess.Read, FileShare.Read);
        _ = Task.Delay(800).ContinueWith(_ => held.Dispose(), TaskScheduler.Default);

        await model.StartAsync(CancellationToken.None);

        Assert.That(File.Exists(InstalledPath), Is.False);
        Assert.That((bool?)model.Json()["installed"], Is.False);
    }

    [Test]
    public async Task AServerWithoutRangeStartsAgainFromTheBeginning()
    {
        Directory.CreateDirectory(Path.GetDirectoryName(InstalledPath)!);
        File.WriteAllBytes(InstalledPath + ".part", Content[..250_000]);
        using var server = new Server(Content) { IgnoreRange = true };
        using var model = Model(server);

        Assert.That(model.Install(CancellationToken.None), Is.Null);
        await model.Installing!;

        Assert.That(File.ReadAllBytes(InstalledPath), Is.EqualTo(Content));
    }

    [Test]
    public async Task ADamagedDownloadIsDeletedAndDownloadedAgain()
    {
        using var server = new Server(Content) { CorruptFirst = 1 };
        using var model = Model(server);

        Assert.That(model.Install(CancellationToken.None), Is.Null);
        await model.Installing!;

        Assert.That(File.ReadAllBytes(InstalledPath), Is.EqualTo(Content));
        Assert.That(server.RangeStarts, Is.EqualTo(new long?[] { null, null }));
    }

    [Test]
    public async Task ADownloadThatNeverMatchesIsNotKept()
    {
        using var server = new Server(Content) { CorruptFirst = int.MaxValue };
        using var model = Model(server);

        Assert.That(model.Install(CancellationToken.None), Is.Null);
        await model.Installing!;

        Assert.Multiple(() =>
        {
            Assert.That(File.Exists(InstalledPath), Is.False);
            Assert.That(File.Exists(InstalledPath + ".part"), Is.False);
            Assert.That((string?)model.Json()["downloadProblem"], Is.EqualTo("danado"));
        });
    }

    [Test]
    public async Task WithNoServerThePartIsKeptAndItSaysSo()
    {
        Directory.CreateDirectory(Path.GetDirectoryName(InstalledPath)!);
        File.WriteAllBytes(InstalledPath + ".part", Content[..1000]);
        using var model = new TunedModel(_root, () => Offer($"http://127.0.0.1:{ClosedPort()}/m.gguf"), retryDelay: TimeSpan.Zero);

        Assert.That(model.Install(CancellationToken.None), Is.Null);
        await model.Installing!;

        Assert.That((string?)model.Json()["downloadProblem"], Is.EqualTo("sin_red"));
        Assert.That(new FileInfo(InstalledPath + ".part").Length, Is.EqualTo(1000));
    }

    [Test]
    public void WithoutRoomOnTheDiskItDoesNotStart()
    {
        using var server = new Server(Content);
        using var model = new TunedModel(_root, () => Offer(server.Url), retryDelay: TimeSpan.Zero, freeBytes: _ => Content.Length);

        Assert.That(model.Install(CancellationToken.None), Is.EqualTo("tuned_model_no_space"));
        Assert.That(server.RangeStarts, Is.Empty);
    }

    [Test]
    public async Task UsingItPointsTheMindAtItOnlyOnceVerifiedAndStopPutsTheStockModelBack()
    {
        using var model = Model(new Server(Content));
        Install();

        Assert.That(model.Apply(new JsonObject { ["use"] = true }), Is.Null);
        await model.StartAsync(CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(model.Active, Is.True);
            Assert.That(Environment.GetEnvironmentVariable(TunedModel.GgufVariable), Is.EqualTo(InstalledPath));
            Assert.That(Environment.GetEnvironmentVariable(MindRuntimeDiscovery.GgufSha256Variable), Is.EqualTo(Sha256(Content)));
            Assert.That(model.NeedsSwitch, Is.False);
        });

        model.Stop();

        Assert.That(Environment.GetEnvironmentVariable(TunedModel.GgufVariable), Is.EqualTo(Stock));
        Assert.That(Environment.GetEnvironmentVariable(MindRuntimeDiscovery.GgufSha256Variable), Is.EqualTo(StockSha256));
    }

    [Test]
    public async Task TurningItOnOrOffAsksForTheMindToBeSwitched()
    {
        using var model = Model(new Server(Content));
        Install();
        await model.StartAsync(CancellationToken.None);
        Assert.That(model.NeedsSwitch, Is.False);

        model.Apply(new JsonObject { ["use"] = true });
        Assert.That(model.NeedsSwitch, Is.True);
        await model.StartAsync(CancellationToken.None);
        Assert.That(model.NeedsSwitch, Is.False);

        model.Apply(new JsonObject { ["use"] = false });
        Assert.That(model.NeedsSwitch, Is.True);
        await model.StartAsync(CancellationToken.None);
        Assert.That(model.Active, Is.False);
        Assert.That(Environment.GetEnvironmentVariable(TunedModel.GgufVariable), Is.EqualTo(Stock));
    }

    [Test]
    public async Task AMissingTunedModelLeavesTheStockOneAndSaysSo()
    {
        using var model = Model(new Server(Content));
        Install();
        model.Apply(new JsonObject { ["use"] = true });
        File.Delete(InstalledPath);

        await model.StartAsync(CancellationToken.None);

        Assert.That(model.Active, Is.False);
        Assert.That(model.Problem, Is.EqualTo("ajustado_ausente"));
        Assert.That(Environment.GetEnvironmentVariable(TunedModel.GgufVariable), Is.EqualTo(Stock));
    }

    [TestCase(0)]
    [TestCase(1)]
    public async Task ADamagedOrResizedTunedModelLeavesTheStockOneAndSaysSo(int extraBytes)
    {
        using var model = Model(new Server(Content));
        Install();
        model.Apply(new JsonObject { ["use"] = true });
        byte[] damaged = [.. Content, .. new byte[extraBytes]];
        damaged[10] ^= 0xFF;
        File.WriteAllBytes(InstalledPath, damaged);

        await model.StartAsync(CancellationToken.None);

        Assert.That(model.Active, Is.False);
        Assert.That(model.Problem, Is.EqualTo("ajustado_danado"));
        Assert.That((bool?)model.Json()["installed"], Is.False);
        Assert.That(Environment.GetEnvironmentVariable(TunedModel.GgufVariable), Is.EqualTo(Stock));
    }

    [Test]
    public async Task RemovingItDeletesTheFileAndGoesBackToTheStockModel()
    {
        using var model = Model(new Server(Content));
        Install();
        model.Apply(new JsonObject { ["use"] = true });
        await model.StartAsync(CancellationToken.None);

        Assert.That(model.Apply(new JsonObject { ["remove"] = true }), Is.Null);
        Assert.That(model.NeedsSwitch, Is.True);
        await model.StartAsync(CancellationToken.None);

        Assert.That(File.Exists(InstalledPath), Is.False);
        Assert.That(model.Active, Is.False);
        Assert.That((bool?)model.Json()["use"], Is.False);
        Assert.That(Environment.GetEnvironmentVariable(TunedModel.GgufVariable), Is.EqualTo(Stock));
    }

    [Test]
    public async Task AFileTheServerStillHoldsIsRemovedAtTheNextStart()
    {
        using var model = Model(new Server(Content));
        Install();
        using (new FileStream(InstalledPath, FileMode.Open, FileAccess.Read, FileShare.Read))
        {
            Assert.That(model.Apply(new JsonObject { ["remove"] = true }), Is.Null);
            Assert.That(File.Exists(InstalledPath), Is.True);
        }

        await model.StartAsync(CancellationToken.None);

        Assert.That(File.Exists(InstalledPath), Is.False);
    }

    // REV_APP TUN-a (2026-11-09): with a removal still pending (the server that is closing maps the file), the view says «Sin
    // instalar» and offers «Instalar». Asked then, the removal stayed pending and the next start of the mind deleted the model
    // the person had just asked back. Asking for it again takes the removal back: the file that never went is the one installed.
    [Test]
    public async Task AskingForItAgainWhileItsRemovalIsPendingKeepsIt()
    {
        using var server = new Server(Content);
        using var model = Model(server);
        Install();
        using (new FileStream(InstalledPath, FileMode.Open, FileAccess.Read, FileShare.Read))
        {
            Assert.That(model.Apply(new JsonObject { ["remove"] = true }), Is.Null);
            Assert.That((bool?)model.Json()["installed"], Is.False, "removed for the person, though the file is still held");

            Assert.That(model.Install(CancellationToken.None), Is.Null);
        }

        if (model.Installing is { } installing)
        {
            await installing;
        }

        await model.StartAsync(CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(File.ReadAllBytes(InstalledPath), Is.EqualTo(Content), "the next start does not delete what was asked back");
            Assert.That((bool?)model.Json()["installed"], Is.True);
            Assert.That(server.RangeStarts, Is.Empty, "the file never went: nothing is downloaded again");
        });
    }

    // REV_APP TUN-a: a damaged file another program still holds cannot be replaced yet. Said as a refusal, not thrown at the view.
    [Test]
    public void AFileThatCannotBeReplacedYetIsARefusalNotAFailure()
    {
        using var server = new Server(Content);
        using var model = Model(server);
        Directory.CreateDirectory(Path.GetDirectoryName(InstalledPath)!);
        File.WriteAllBytes(InstalledPath, Content[..1000]);
        using (new FileStream(InstalledPath, FileMode.Open, FileAccess.Read, FileShare.Read))
        {
            string? refused = null;
            Assert.DoesNotThrow(() => refused = model.Install(CancellationToken.None));
            Assert.That(refused, Is.EqualTo("tuned_model_file_busy"));
            Assert.That(model.Installing, Is.Null, "nothing was started");
        }

        // control: free again, it is replaced
        Assert.That(model.Install(CancellationToken.None), Is.Null);
    }

    // REV_APP DL-c: a failure of the disk that is not «full» was said as «No logré conectarme a internet».
    [Test]
    public async Task AFailureOfTheDiskWhileItDownloadsIsNotSaidAsTheNetworks()
    {
        using var server = new Server(Content);
        using var model = Model(server);
        Directory.CreateDirectory(Path.GetDirectoryName(InstalledPath)!);
        using (new FileStream(InstalledPath + ".part", FileMode.Create, FileAccess.Write, FileShare.None))
        {
            Assert.That(model.Install(CancellationToken.None), Is.Null);
            await model.Installing!;
        }

        Assert.That(model.DownloadProblem, Is.EqualTo("sin_disco"));
        Assert.That((string?)model.Json()["downloadProblem"], Is.EqualTo("sin_disco"));

        // control: free again, the same request ends well
        Assert.That(model.Install(CancellationToken.None), Is.Null);
        await model.Installing!;
        Assert.That(model.DownloadProblem, Is.Null);
        Assert.That(File.ReadAllBytes(InstalledPath), Is.EqualTo(Content));
    }

    [Test]
    public async Task UsingItSwitchesTheMindTheWayTheModelByApiDoes()
    {
        System.Reflection.FieldInfo field = typeof(MainWindowViewModel)
            .GetField("_tunedModel", System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic)!;
        using var server = new Server(Content);
        using var model = Model(server);
        Install();
        model.Apply(new JsonObject { ["use"] = true });
        await model.StartAsync(CancellationToken.None);
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        {
            field.SetValue(viewModel, model);
            viewModel.TunedModelChanged();
            Assert.That(Environment.GetEnvironmentVariable(TunedModel.GgufVariable), Is.EqualTo(InstalledPath), "nothing changed");

            model.Apply(new JsonObject { ["use"] = false });
            viewModel.TunedModelChanged();

            // The running mind stops and the stock model is what the next one gets; with no engine here, none starts yet.
            Assert.That(() => viewModel.ExternalModelState.Switching, Is.False.After(5000, 50));
            Assert.That(Environment.GetEnvironmentVariable(TunedModel.GgufVariable), Is.EqualTo(Stock));
            field.SetValue(viewModel, null);
        }
    }

    [Test]
    public async Task TheViewAsksThroughItsRoutesAndHearsOfAStartThatCouldNotUseIt()
    {
        System.Reflection.FieldInfo field = typeof(MainWindowViewModel)
            .GetField("_tunedModel", System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic)!;
        using var server = new Server(Content);
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        {
            field.SetValue(viewModel, null);
            TunedModel model = Model(server);
            field.SetValue(viewModel, model);
            await using var view = new ChannelHarness(viewModel);

            (int status, JsonObject body) = await view.SendAsync("PUT", "/settings/tuned-model", new JsonObject { ["use"] = true });
            Assert.That((status, (string?)body["error"]), Is.EqualTo((409, "tuned_model_not_installed")));

            (status, body) = await view.SendAsync("POST", "/settings/tuned-model/install");
            Assert.That(status, Is.EqualTo(200));
            Assert.That((bool?)body["switching"], Is.False);
            await model.Installing!;
            Assert.That(File.Exists(InstalledPath), Is.True);

            File.WriteAllBytes(InstalledPath, [.. Content[..^1], 0]);
            model.Apply(new JsonObject { ["use"] = true });
            await model.StartAsync(CancellationToken.None);
            Assert.That((string?)view.Channel.BootEvent()["tunedProblem"], Is.EqualTo("ajustado_danado"));
            field.SetValue(viewModel, null);
            model.Dispose();
        }
    }

    // MOD1 V-07 / VIVO2 F11 (2026-11-09): in «Modelos en este PC» the stock model's row said «—» for its size, and no row of
    // BAXY's own said its VRAM. The view reads both models' files where it reads the context they run with: the stock one is
    // the file the mind had as its own before the tuned one took its place, whichever of the two runs now.
    [Test]
    public async Task TheViewReadsWhatTheStockAndTheTunedModelsTakeWhicheverRunsNow()
    {
        const System.Reflection.BindingFlags Private = System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic;
        System.Reflection.FieldInfo tunedField = typeof(MainWindowViewModel).GetField("_tunedModel", Private)!;
        System.Reflection.FieldInfo contextField = typeof(MainWindowViewModel).GetField("_localContext", Private)!;
        string stock = Path.Combine(_root, "de-serie.gguf");
        File.WriteAllBytes(stock, new byte[4321]);
        Environment.SetEnvironmentVariable(TunedModel.GgufVariable, stock);
        using var server = new Server(Content);
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        {
            tunedField.SetValue(viewModel, null);
            TunedModel model = Model(server);
            tunedField.SetValue(viewModel, model);
            contextField.SetValue(viewModel, new LocalContext(_root));
            await using var view = new ChannelHarness(viewModel);

            (int status, JsonObject body) = await view.SendAsync("GET", "/settings/local-context");
            Assert.That((status, (long?)body["stock"]?["bytes"]), Is.EqualTo((200, 4321L)));
            Assert.That(body["tuned"], Is.Null, "the tuned model is not installed");

            Install();
            model.Apply(new JsonObject { ["use"] = true });
            await model.StartAsync(CancellationToken.None);
            Assert.That(Environment.GetEnvironmentVariable(TunedModel.GgufVariable), Is.EqualTo(InstalledPath));

            (status, body) = await view.SendAsync("GET", "/settings/local-context");
            Assert.Multiple(() =>
            {
                Assert.That((long?)body["stock"]?["bytes"], Is.EqualTo(4321L), "the stock model's file, not the one in its place");
                Assert.That((long?)body["tuned"]?["bytes"], Is.EqualTo(Content.Length));
                Assert.That(body.ToJsonString(), Does.Not.Contain("de-serie"), "no path goes to the view");
            });
            contextField.SetValue(viewModel, null);
            tunedField.SetValue(viewModel, null);
            model.Dispose();
        }
    }

    // Owner, 2026-11-09 (Settings › Modelo in the dev BAXY): «De serie» showed «BAXY-Qwen3.5-4B-ft-c2e1-Q4_K_M», a tuned file
    // the development launcher gives the mind as BAXY's own. The view names the stock model always, and the App says whether
    // the model BAXY runs as its own is it, by the registry's SHA-256 (null when the launcher set the file itself: not known).
    [TestCase("00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4", true)]
    [TestCase("2c445631782a5c27b9948369e9432309528688b9b761fce56586d796ea2f57c7", false)]
    [TestCase(null, null)]
    public async Task TheSettingsSayTheStockModelAndWhetherBaxysOwnIsIt(string? sha256, bool? stock)
    {
        string? before = Environment.GetEnvironmentVariable(MindRuntimeDiscovery.GgufSha256Variable);
        Environment.SetEnvironmentVariable(MindRuntimeDiscovery.GgufSha256Variable, sha256);
        try
        {
            var viewModel = new MainWindowViewModel();
            await using (viewModel)
            await using (var view = new ChannelHarness(viewModel))
            {
                (int status, JsonObject body) = await view.SendAsync("GET", "/settings");
                Assert.That(status, Is.EqualTo(200));
                Assert.That((string?)body["stockName"], Is.EqualTo("Qwen3.5-4B"));
                Assert.That((bool?)body["ownIsStock"], Is.EqualTo(stock));
            }
        }
        finally
        {
            Environment.SetEnvironmentVariable(MindRuntimeDiscovery.GgufSha256Variable, before);
        }
    }

    // Owner, 2026-11-08: «tengo activo el modelo ajustado y activo usar otro modelo. Eso no tiene sentido». One model at a
    // time: turning one on turns the other off, and a pair kept on from before is told as what really runs (the other one).
    [Test]
    public async Task OnlyOneModelIsOnAtATime()
    {
        const System.Reflection.BindingFlags Private = System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic;
        System.Reflection.FieldInfo tunedField = typeof(MainWindowViewModel).GetField("_tunedModel", Private)!;
        System.Reflection.FieldInfo externalField = typeof(MainWindowViewModel).GetField("_externalModel", Private)!;
        using var server = new Server(Content);
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        {
            TunedModel tuned = Model(server);
            var external = new ExternalModel(Path.Combine(_root, "external"));
            tunedField.SetValue(viewModel, tuned);
            externalField.SetValue(viewModel, external);
            bool TunedOn() => (bool?)tuned.Json()["use"] == true;
            bool ExternalOn() => (bool?)external.Json()["enabled"] == true;

            await using (var view = new ChannelHarness(viewModel))
            {
                Assert.That((await view.SendAsync("POST", "/settings/tuned-model/install")).Status, Is.EqualTo(200));
                await tuned.Installing!;
                Assert.That(external.Apply(new JsonObject { ["provider"] = "local", ["model"] = "qwen3:8b", ["enabled"] = true }), Is.Null);

                Assert.That((await view.SendAsync("PUT", "/settings/tuned-model", new JsonObject { ["use"] = true })).Status, Is.EqualTo(200));
                Assert.That((TunedOn(), ExternalOn()), Is.EqualTo((true, false)), "the tuned model was turned on beside another model");

                Assert.That((await view.SendAsync("PUT", "/settings/external-model", new JsonObject { ["enabled"] = true })).Status, Is.EqualTo(200));
                Assert.That((TunedOn(), ExternalOn()), Is.EqualTo((false, true)), "another model was turned on beside the tuned one");
            }

            // Kept on together before this was known: a start keeps the other model, the one that ran.
            Assert.That(tuned.Apply(new JsonObject { ["use"] = true }), Is.Null);
            viewModel.KeepOneModel(tunedChosen: false);
            Assert.That((TunedOn(), ExternalOn()), Is.EqualTo((false, true)));

            Assert.That(() => viewModel.ExternalModelState.Switching, Is.False.After(5000, 50));
            tunedField.SetValue(viewModel, null);
            externalField.SetValue(viewModel, null);
            tuned.Dispose();
        }
    }

    // INT17, revisión ciega: «Instalar y usar» (OpenModels.Pulled) turned the model Ollama finished on beside the tuned one
    // in use, and «Ajustado» then sent nothing (it was already on) while Ollama's ran. It keeps one, as the switches do.
    [Test]
    public async Task AModelInstalledAndUsedFromSettingsTurnsTheTunedOneOff()
    {
        const System.Reflection.BindingFlags Private = System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic;
        System.Reflection.FieldInfo tunedField = typeof(MainWindowViewModel).GetField("_tunedModel", Private)!;
        System.Reflection.FieldInfo externalField = typeof(MainWindowViewModel).GetField("_externalModel", Private)!;
        string? dataDir = Environment.GetEnvironmentVariable("BAXY_DATA_DIR");
        // The App's own ExternalModel (its getter subscribes to OpenModels.Pulled), in a data root of this test's own, where
        // the App accepts one (WindowsPrivateStorage: a child of %LOCALAPPDATA%\BAXY), as FakeMind makes it.
        string data = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "BAXY", "apptest-" + Guid.NewGuid().ToString("N"));
        using var server = new Server(Content);
        try
        {
            Environment.SetEnvironmentVariable("BAXY_DATA_DIR", data);
            var viewModel = new MainWindowViewModel();
            await using (viewModel)
            {
                TunedModel tuned = Model(server);
                tunedField.SetValue(viewModel, tuned);
                ExternalModel external = viewModel.ExternalModelState;
                await using (var view = new ChannelHarness(viewModel))
                {
                    Assert.That((await view.SendAsync("POST", "/settings/tuned-model/install")).Status, Is.EqualTo(200));
                    await tuned.Installing!;
                    Assert.That((await view.SendAsync("PUT", "/settings/tuned-model", new JsonObject { ["use"] = true })).Status, Is.EqualTo(200));
                }

                // What OpenModels raises once Ollama made the model (InstallAsync, PullAsync).
                var pulled = (Action<string>)typeof(OpenModels).GetField(nameof(OpenModels.Pulled), Private)!.GetValue(external.Open)!;
                pulled("unsloth/Qwen3.5-2B-GGUF:Q4_K_M");

                Assert.That(() => (bool?)external.Json()["enabled"] == true, Is.True.After(5000, 50), "the model installed is not the one chosen");
                Assert.That(() => (bool?)tuned.Json()["use"], Is.False.After(5000, 50), "the tuned model stayed on beside the one installed");
                Assert.That(() => viewModel.ExternalModelState.Switching, Is.False.After(5000, 50));
                tunedField.SetValue(viewModel, null);
                externalField.SetValue(viewModel, null);
                tuned.Dispose();
                external.Dispose();
            }
        }
        finally
        {
            Environment.SetEnvironmentVariable("BAXY_DATA_DIR", dataDir);
            if (Directory.Exists(data))
            {
                Directory.Delete(data, recursive: true);
            }
        }
    }

    // Its folder may be a junction or a mounted folder to another disk (a full system drive, models kept elsewhere): the room
    // that counts is that disk's, not the drive letter's.
    [Test]
    public void TheRoomIsOfTheDiskThatHoldsTheFolderThroughAJunction()
    {
        string here = Path.GetPathRoot(_root)!;
        DriveInfo? other = DriveInfo.GetDrives().FirstOrDefault(d => d.DriveType == DriveType.Fixed && d.IsReady
            && !string.Equals(d.Name, here, StringComparison.OrdinalIgnoreCase)
            && Math.Abs(d.AvailableFreeSpace - new DriveInfo(here).AvailableFreeSpace) > (1L << 30));
        if (other is null)
        {
            Assert.Ignore("this PC has no second fixed disk with another amount of room");
        }

        string elsewhere = Path.Combine(other!.Name, "baxy-tuned-elsewhere-" + Guid.NewGuid().ToString("N"));
        try
        {
            Directory.CreateDirectory(elsewhere);
        }
        catch (UnauthorizedAccessException)
        {
            Assert.Ignore($"{other.Name} takes no folder of this user's");
        }

        string junction = Path.Combine(_root, "models");
        try
        {
            using (Process mklink = Process.Start(new ProcessStartInfo("cmd.exe", $"/c mklink /J \"{junction}\" \"{elsewhere}\"")
                   { UseShellExecute = false, CreateNoWindow = true })!)
            {
                mklink.WaitForExit();
            }

            long seen = TunedModel.FreeBytes(Path.Combine(junction, "BAXY-Qwen3.5-4B-c4-Q4_K_M.gguf"));

            Assert.That(Math.Abs(seen - other.AvailableFreeSpace), Is.LessThan(256L << 20), $"{other.Name} has {other.AvailableFreeSpace} free");
        }
        finally
        {
            Directory.Delete(junction);
            Directory.Delete(elsewhere);
        }
    }

    [TestCase("Qwen3.5-4B-Q4_K_M.gguf", "Qwen3.5-4B-Q4_K_M")]
    [TestCase("BAXY-Qwen3.5-4B-c4-Q4_K_M.gguf", "BAXY-Qwen3.5-4B-c4-Q4_K_M")]
    public void BothModelsAreShownByTheirOwnName(string file, string alias)
    {
        FieldModelIdentity identity = FieldProductChannel.ResolveModelIdentity(Path.Combine(_root, "models", file));

        Assert.That(identity, Is.EqualTo(new FieldModelIdentity(alias, file, "qwen 3.5", "4b")));
    }

    private string InstalledPath => Path.Combine(_root, "models", "BAXY-Qwen3.5-4B-c4-Q4_K_M.gguf");

    private TunedModel Model(Server server) => new(_root, () => Offer(server.Url), retryDelay: TimeSpan.Zero);

    private void Install()
    {
        Directory.CreateDirectory(Path.GetDirectoryName(InstalledPath)!);
        File.WriteAllBytes(InstalledPath, Content);
    }

    private static TunedModelOffer Offer(string url) =>
        new("BAXY-Qwen3.5-4B-c4-Q4_K_M.gguf", Sha256(Content), Content.Length, url, "Apache-2.0");

    private static string Sha256(byte[] data) => Convert.ToHexStringLower(SHA256.HashData(data));

    private static int ClosedPort()
    {
        using var probe = new TcpListener(IPAddress.Loopback, 0);
        probe.Start();
        return ((IPEndPoint)probe.LocalEndpoint).Port;
    }

    /// <summary>
    /// A file served over HTTP/1.1 on this PC, as a CDN serves it: «Range: bytes=N-» answered with 206 and the rest (or 200
    /// and the whole file, <see cref="IgnoreRange"/>), the first answer cut after <see cref="DropFirstAfter"/> bytes, and
    /// the first <see cref="CorruptFirst"/> answers with one byte changed. With <see cref="HoldAt"/>, a slow line: half of
    /// what comes before it, the other half a moment later, and the rest only once <see cref="Release"/> is called.
    /// </summary>
    private sealed class Server : IDisposable
    {
        private readonly byte[] _content;
        private readonly TcpListener _listener = new(IPAddress.Loopback, 0);
        private readonly CancellationTokenSource _stop = new();
        private readonly TaskCompletionSource _released = new(TaskCreationOptions.RunContinuationsAsynchronously);
        private int _answers;

        internal Server(byte[] content)
        {
            _content = content;
            _listener.Start();
            _ = Task.Run(ServeAsync);
        }

        internal long? DropFirstAfter { get; init; }

        internal int CorruptFirst { get; init; }

        internal bool IgnoreRange { get; init; }

        internal long? HoldAt { get; init; }

        internal List<long?> RangeStarts { get; } = [];

        internal void Release() => _released.TrySetResult();

        internal string Url => $"http://127.0.0.1:{((IPEndPoint)_listener.LocalEndpoint).Port}/REDSOULTM/resolve/abc/m.gguf";

        public void Dispose()
        {
            _released.TrySetResult();
            _stop.Cancel();
            _listener.Stop();
            _stop.Dispose();
        }

        private async Task ServeAsync()
        {
            while (!_stop.IsCancellationRequested)
            {
                TcpClient client;
                try
                {
                    client = await _listener.AcceptTcpClientAsync(_stop.Token);
                }
                catch (Exception exception) when (exception is OperationCanceledException or SocketException or ObjectDisposedException)
                {
                    return;
                }

                using (client)
                {
                    try
                    {
                        await AnswerAsync(client.GetStream());
                    }
                    catch (IOException)
                    {
                        // the client went away
                    }
                }
            }
        }

        private async Task AnswerAsync(NetworkStream stream)
        {
            var reader = new StreamReader(stream, Encoding.ASCII, leaveOpen: true);
            long? from = null;
            while (await reader.ReadLineAsync() is { Length: > 0 } line)
            {
                if (line.StartsWith("Range: bytes=", StringComparison.OrdinalIgnoreCase))
                {
                    from = long.Parse(line["Range: bytes=".Length..].TrimEnd('-'), System.Globalization.CultureInfo.InvariantCulture);
                }
            }

            int answer = _answers++;
            lock (RangeStarts)
            {
                RangeStarts.Add(from);
            }

            byte[] content = (byte[])_content.Clone();
            if (answer < CorruptFirst)
            {
                content[^1] ^= 0xFF;
            }

            long start = IgnoreRange ? 0 : from ?? 0;
            string status = start > 0 ? "206 Partial Content" : "200 OK";
            string head = $"HTTP/1.1 {status}\r\nContent-Length: {content.Length - start}\r\nAccept-Ranges: bytes\r\nConnection: close\r\n"
                + (start > 0 ? $"Content-Range: bytes {start}-{content.Length - 1}/{content.Length}\r\n" : string.Empty) + "\r\n";
            await stream.WriteAsync(Encoding.ASCII.GetBytes(head));
            long end = answer == 0 && DropFirstAfter is { } drop ? Math.Max(start, drop) : content.Length;
            if (HoldAt is { } hold && start < hold && hold < end)
            {
                long half = start + ((hold - start) / 2);
                await stream.WriteAsync(content.AsMemory((int)start, (int)(half - start)));
                await stream.FlushAsync();
                await Task.Delay(400);
                await stream.WriteAsync(content.AsMemory((int)half, (int)(hold - half)));
                await stream.FlushAsync();
                await _released.Task;
                start = hold;
            }

            await stream.WriteAsync(content.AsMemory((int)start, (int)(end - start)));
            await stream.FlushAsync();
        }
    }
}
