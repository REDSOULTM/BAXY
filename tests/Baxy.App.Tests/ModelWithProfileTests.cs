using System.IO;
using System.Reflection;
using System.Text.Json.Nodes;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// MOD1: a model of this PC whose context is short of the chosen tool profile's prompt is used with the profile that fits it,
/// in one gesture of the App's (the search's «Instalar y usar con …», the list's «Usar con …»): the model and the profile, or
/// neither. The App is its own view model, in a data root of each test's own, with no engine: nothing is started.
/// </summary>
[TestFixture]
[NonParallelizable]
public sealed class ModelWithProfileTests
{
    private const BindingFlags Private = BindingFlags.Instance | BindingFlags.NonPublic;
    private const string Short = "a/Corto-GGUF";
    private const string ShortName = "a/Corto-GGUF:Q4_K_M";
    private static readonly string Sha = new('a', 64);
    private string? _dataDir;
    private string _data = "";

    [SetUp]
    public void SetUp()
    {
        _dataDir = Environment.GetEnvironmentVariable("BAXY_DATA_DIR");
        // Where the App accepts a data root (WindowsPrivateStorage: a child of %LOCALAPPDATA%\BAXY), as FakeMind makes it.
        _data = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "BAXY", "apptest-" + Guid.NewGuid().ToString("N"));
        Environment.SetEnvironmentVariable("BAXY_DATA_DIR", _data);
    }

    [TearDown]
    public void TearDown()
    {
        Environment.SetEnvironmentVariable("BAXY_DATA_DIR", _dataDir);
        if (Directory.Exists(_data))
        {
            Directory.Delete(_data, recursive: true);
        }
    }

    // The App with its own ExternalModel and ToolProfile, and a tuned model with nothing offered.
    private async Task WithAppAsync(Func<MainWindowViewModel, ExternalModel, Task> test)
    {
        FieldInfo tunedField = typeof(MainWindowViewModel).GetField("_tunedModel", Private)!;
        FieldInfo externalField = typeof(MainWindowViewModel).GetField("_externalModel", Private)!;
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        {
            var tuned = new TunedModel(Path.Combine(_data, "tuned"), static () => null);
            tunedField.SetValue(viewModel, tuned);
            ExternalModel external = viewModel.ExternalModelState;
            try
            {
                await test(viewModel, external);
                Assert.That(() => external.Switching, Is.False.After(5000, 50));
            }
            finally
            {
                tunedField.SetValue(viewModel, null);
                externalField.SetValue(viewModel, null);
                tuned.Dispose();
                external.Dispose();
            }
        }
    }

    // What OpenModels raises once Ollama made the model (InstallAsync, PullAsync).
    private static void Pulled(ExternalModel external, string name) =>
        ((Action<string>)typeof(OpenModels).GetField(nameof(OpenModels.Pulled), Private)!.GetValue(external.Open)!)(name);

    private static string? Chosen(ExternalModel external) =>
        (bool?)external.Json()["enabled"] == true ? (string?)external.Json()["model"] : null;

    // VIVO2 F13: the search offers a model that declares less than the chosen profile takes with the preset that fits it
    // («Instalar y usar con Esencial»). Once Ollama has it, it is used with that profile, in the same gesture.
    [Test]
    public async Task AModelInstalledWithTheProfileTheSearchOfferedIsUsedWithIt()
    {
        await WithAppAsync(async (viewModel, external) =>
        {
            await using var view = new ChannelHarness(viewModel);
            Assert.That(viewModel.ToolProfileState.Profile, Is.EqualTo(ToolProfile.Completo));
            var install = new JsonObject { ["repo"] = Short, ["file"] = "c-Q4_K_M.gguf", ["sha256"] = Sha, ["bytes"] = 1000, ["quant"] = "Q4_K_M" };

            var unknown = (JsonObject)install.DeepClone();
            unknown["profile"] = "ninguno";
            Assert.That((await view.SendAsync("POST", "/settings/external-model/install", unknown)).Status, Is.EqualTo(400), "a profile that is none of the presets");
            Assert.That(external.Open.Working, Is.Null, "and nothing was started for it");

            // No Ollama answers this test: the install ends at once, and what it was asked with is kept for when it is asked again.
            Assert.That(external.Open.Install(Short, "c-Q4_K_M.gguf", Sha, 1000, "Q4_K_M", static _ => Task.FromResult(false), CancellationToken.None, "esencial"), Is.Null);
            await external.Open.Working!;
            Assert.That(viewModel.ToolProfileState.Profile, Is.EqualTo(ToolProfile.Completo), "nothing changes until the model is here");

            Pulled(external, ShortName);

            Assert.That(() => Chosen(external), Is.EqualTo(ShortName).After(5000, 50), "the model installed is not the one chosen");
            Assert.That(viewModel.ToolProfileState.Profile, Is.EqualTo("esencial"), "nor with the profile it was offered with");
        });
    }

    // VIVO2 F15: «Usar con Esencial» was two requests of the view's (the profile, then the model): a model refused, or one that
    // did not connect, left the person on Esencial with BAXY's own model and nothing said. It is one request of the App's.
    [Test]
    public async Task UsingAModelWithAProfileIsOneRequest_TheModelAndTheProfile_OrNeither()
    {
        await WithAppAsync(async (viewModel, external) =>
        {
            await using var view = new ChannelHarness(viewModel);
            JsonObject Use(string model, string profile) => new() { ["provider"] = "local", ["model"] = model, ["enabled"] = true, ["profile"] = profile };

            Assert.That((await view.SendAsync("PUT", "/settings/external-model", Use("lumen:7b", "ninguno"))).Status, Is.EqualTo(400), "a profile that is none of the presets");
            Assert.That(Chosen(external), Is.Null);
            (int status, JsonObject refused) = await view.SendAsync("PUT", "/settings/external-model", Use(new string('m', 5000), "esencial"));
            Assert.That(status, Is.EqualTo(409));
            Assert.That((string?)refused["error"], Is.EqualTo("external_model_invalid_model"));
            Assert.That(viewModel.ToolProfileState.Profile, Is.EqualTo(ToolProfile.Completo), "a model refused left the profile changed");

            (status, JsonObject taken) = await view.SendAsync("PUT", "/settings/external-model", Use("lumen:7b", "esencial"));

            Assert.That(status, Is.EqualTo(200));
            Assert.That(Chosen(external), Is.EqualTo("lumen:7b"));
            Assert.That(viewModel.ToolProfileState.Profile, Is.EqualTo("esencial"));
            Assert.That(taken["profileBack"], Is.Null, "nothing was given back: it is being connected");
        });
    }

    [Test]
    public async Task AProfileLentToAModelThatDidNotConnectIsGivenBackAndSaid()
    {
        await WithAppAsync(async (viewModel, external) =>
        {
            await using var view = new ChannelHarness(viewModel);
            Assert.That(viewModel.ToolProfileState.Apply(new JsonObject { ["profile"] = "diario" }), Is.Null);
            _ = await view.SendAsync("PUT", "/settings/external-model",
                new JsonObject { ["provider"] = "local", ["model"] = "lumen:7b", ["enabled"] = true, ["profile"] = "esencial" });
            ExternalModel.ProfileLoan? lent = external.Lent;
            Assert.That(lent, Is.Not.Null);

            // What the start of the mind does once the model's own start ended: here nothing connects (no engine, no Ollama).
            Assert.That(external.Active, Is.False);
            viewModel.SettleProfile(lent);

            Assert.That(viewModel.ToolProfileState.Profile, Is.EqualTo("diario"), "the profile the person had, not the one lent to a model that did not connect");
            JsonNode? back = external.Json()["profileBack"];
            Assert.Multiple(() =>
            {
                Assert.That((string?)back?["model"], Is.EqualTo("lumen:7b"));
                Assert.That((string?)back?["profile"], Is.EqualTo("esencial"));
                Assert.That((string?)back?["back"], Is.EqualTo("diario"));
                Assert.That(external.Lent, Is.Null, "given back once");
            });

            // The model's own way out («Usar N tokens, que caben, con el perfil Esencial») asks for it again with that profile:
            // lent once more, and what goes back if it does not connect is still what the person had.
            Assert.That(() => external.Switching, Is.False.After(5000, 50));
            (int status, JsonObject again) = await view.SendAsync("PUT", "/settings/external-model", new JsonObject { ["context"] = 28000, ["profile"] = "esencial" });
            Assert.That(status, Is.EqualTo(200));
            Assert.That(again["profileBack"], Is.Null, "another gesture: the note was the last one's");
            Assert.That(viewModel.ToolProfileState.Profile, Is.EqualTo("esencial"));
            Assert.That(external.Lent, Is.EqualTo(new ExternalModel.ProfileLoan("lumen:7b", "esencial", external.Lent!.Before)));
            Assert.That((string?)external.Lent.Before["profile"], Is.EqualTo("diario"));
            viewModel.SettleProfile(external.Lent);
            Assert.That(viewModel.ToolProfileState.Profile, Is.EqualTo("diario"));

            // The next thing the person asks of the model is another gesture: the note is the last one's.
            _ = await view.SendAsync("PUT", "/settings/external-model", new JsonObject { ["enabled"] = false });
            Assert.That(external.Json()["profileBack"], Is.Null);
        });
    }

    // VIVO2 F15, by the App's own path (MOD1: the two lines of InitializeMindAsync that settle the loan had no test): with a
    // mind up, asking for a model with a profile switches the mind; the model's own start fails (its server answers nothing: an
    // address of this PC with nobody there, so no key and no Ollama are involved) and the mind that comes up is on the profile
    // the person had, with the note for the view.
    [Test]
    public async Task TheMindsOwnStartGivesBackAProfileLentToAModelThatDidNotConnect()
    {
        using var fake = new FakeMind();
        using var nobody = new System.Net.Sockets.TcpListener(System.Net.IPAddress.Loopback, 0);
        nobody.Start();
        int port = ((System.Net.IPEndPoint)nobody.LocalEndpoint).Port;
        nobody.Stop();
        await WithAppAsync(async (viewModel, external) =>
        {
            await using var view = new ChannelHarness(viewModel);
            Assert.That(viewModel.ToolProfileState.Apply(new JsonObject { ["profile"] = "diario" }), Is.Null);
            await ViewModelHarness.StartMindAsync(viewModel);
            Assert.That(viewModel.IsMindReady, Is.True);

            (int status, _) = await view.SendAsync("PUT", "/settings/external-model", new JsonObject
            {
                ["provider"] = "compatible", ["url"] = $"http://127.0.0.1:{port}/v1", ["model"] = "lumen-7b", ["enabled"] = true, ["profile"] = "esencial",
            });
            Assert.That(status, Is.EqualTo(200));
            Assert.That(viewModel.ToolProfileState.Profile, Is.EqualTo("esencial"), "lent while the model starts");

            // The switch stops the mind; with no engine here, the mind's next start is the engine's (ViewModelHarness runs it).
            Assert.That(() => external.Switching, Is.False.After(60_000, 100));
            await ViewModelHarness.StartMindAsync(viewModel);
            Assert.That(viewModel.IsMindReady, Is.True);
            JsonNode? back = external.Json()["profileBack"];
            Assert.Multiple(() =>
            {
                Assert.That(external.Active, Is.False, "nobody answers at that address");
                Assert.That(viewModel.ToolProfileState.Profile, Is.EqualTo("diario"), "the profile the person had, before the mind read it");
                Assert.That((string?)back?["model"], Is.EqualTo("lumen-7b"));
                Assert.That((string?)back?["back"], Is.EqualTo("diario"));
                Assert.That(external.Lent, Is.Null);
            });
        });
    }

    [Test]
    public async Task AProfileThePersonChoseThemselvesIsNeverTakenBack()
    {
        await WithAppAsync(async (viewModel, external) =>
        {
            await using var view = new ChannelHarness(viewModel);
            JsonObject use = new() { ["provider"] = "local", ["model"] = "lumen:7b", ["enabled"] = true, ["profile"] = "esencial" };

            // Chosen in Settings → Tools after the model was asked with it: theirs now.
            _ = await view.SendAsync("PUT", "/settings/external-model", use.DeepClone().AsObject());
            ExternalModel.ProfileLoan? lent = external.Lent;
            Assert.That((await view.SendAsync("PUT", "/settings/tools", new JsonObject { ["profile"] = "esencial" })).Status, Is.EqualTo(200));
            viewModel.SettleProfile(lent);
            Assert.That(viewModel.ToolProfileState.Profile, Is.EqualTo("esencial"));
            Assert.That(external.Json()["profileBack"], Is.Null);
            Assert.That(() => external.Switching, Is.False.After(5000, 50));

            // Already theirs when the model was asked with it: nothing was lent.
            _ = await view.SendAsync("PUT", "/settings/external-model", use.DeepClone().AsObject());
            Assert.That(external.Lent, Is.Null);

            // A second model asked with a profile before the first one's start settled: what is given back is what the person had.
            Assert.That(viewModel.ToolProfileState.Apply(new JsonObject { ["profile"] = ToolProfile.Completo }), Is.Null);
            use["profile"] = "diario";
            _ = await view.SendAsync("PUT", "/settings/external-model", use.DeepClone().AsObject());
            use["model"] = "otro:3b";
            use["profile"] = "esencial";
            _ = await view.SendAsync("PUT", "/settings/external-model", use.DeepClone().AsObject());
            viewModel.SettleProfile(external.Lent);
            Assert.That(viewModel.ToolProfileState.Profile, Is.EqualTo(ToolProfile.Completo));
            Assert.That((string?)external.Json()["profileBack"]?["back"], Is.EqualTo(ToolProfile.Completo));
        });
    }

    [Test]
    public async Task AModelInstalledKeepsTheProfileThePersonHas_WhenNoneWasAsked_OrTheirsIsNoBigger()
    {
        await WithAppAsync(async (viewModel, external) =>
        {
            // None asked (a model that holds the chosen profile): the profile stays.
            Pulled(external, "a/Largo-GGUF:Q4_K_M");
            Assert.That(() => Chosen(external), Is.EqualTo("a/Largo-GGUF:Q4_K_M").After(5000, 50));
            Assert.That(viewModel.ToolProfileState.Profile, Is.EqualTo(ToolProfile.Completo));
            Assert.That(() => external.Switching, Is.False.After(5000, 50));

            // Asked with Diario, and the person chose Esencial while it downloaded: theirs fits it too, and stays.
            Assert.That(external.Open.Install(Short, "c-Q4_K_M.gguf", Sha, 1000, "Q4_K_M", static _ => Task.FromResult(false), CancellationToken.None, "diario"), Is.Null);
            await external.Open.Working!;
            Assert.That(viewModel.ToolProfileState.Apply(new JsonObject { ["profile"] = "esencial" }), Is.Null);

            Pulled(external, ShortName);

            Assert.That(() => Chosen(external), Is.EqualTo(ShortName).After(5000, 50));
            Assert.That(viewModel.ToolProfileState.Profile, Is.EqualTo("esencial"));
        });
    }
}
