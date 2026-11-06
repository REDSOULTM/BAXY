using System.Diagnostics;
using System.IO;
using System.Net;
using System.Net.Http;
using System.Net.Sockets;
using System.Reflection;
using System.Text;
using System.Text.Json.Nodes;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// The model by API is off until the person turns it on: a key is never sent back nor kept readable, another company is
/// only used after it is turned on again, a translator that cannot start leaves BAXY on the local model, saying why, and
/// its variable can remove the setting.
/// </summary>
[TestFixture]
[NonParallelizable]
public sealed class ExternalModelTests
{
    private const string Key = "sk-clave-de-prueba";
    private string _root = "";
    private string? _localAppData;

    [SetUp]
    public void SetUp()
    {
        _root = Directory.CreateTempSubdirectory("baxy-external-model-").FullName;
        Environment.SetEnvironmentVariable(ExternalModel.Variable, null);
        // So that no test opens the Ollama this machine has: here there is none.
        _localAppData = Environment.GetEnvironmentVariable("LOCALAPPDATA");
        Environment.SetEnvironmentVariable("LOCALAPPDATA", _root);
    }

    [TearDown]
    public void TearDown()
    {
        foreach (string name in new[]
        {
            ExternalModel.Variable, ExternalModel.PythonVariable, MindSidecarClient.PythonEnvironmentVariable,
            MindSidecarClient.PythonPathEnvironmentVariable, "BAXY_MIND_LLAMA_REMOTE",
            MindSidecarClient.TurnSecondsVariable, "BAXY_RENEW_PREFILL", "BAXY_RENEW_WAKE_WARM", "BAXY_VISION_ENDPOINT",
            ExternalModel.NoCheckVariable, ExternalModel.CeilingVariable, "BAXY_RENEW_CTX", "BAXY_MIND_LLAMA_PORT", "OLLAMA_HOST", "HTTPS_PROXY",
        })
        {
            Environment.SetEnvironmentVariable(name, null);
        }

        Environment.SetEnvironmentVariable("LOCALAPPDATA", _localAppData);
        Directory.Delete(_root, recursive: true);
    }

    [Test]
    public void ItIsOfferedOffAndItsVariableCanRemoveIt()
    {
        Assert.That(ExternalModel.Available, Is.True);
        Assert.That((bool?)new ExternalModel(_root).Json()["enabled"], Is.False);
        Environment.SetEnvironmentVariable(ExternalModel.Variable, "0");
        Assert.That(ExternalModel.Available, Is.False);
    }

    // int-staging-1: hub/i6-l4-arreglos gave a turn's request a ceiling of 126 s until the mind says its own; a model on
    // this PC behind the translator has a window of 300 s (LocalTurnSeconds), and the ceiling must not end it before.
    [TestCase(null, 30.0, 126.0)]
    [TestCase("90", 90.0, 126.0)]
    [TestCase("300", 300.0, 300.0)]
    public async Task ATurnsCeilingIsNeverShorterThanItsWindow(string? turn, double window, double ceiling)
    {
        Environment.SetEnvironmentVariable(MindSidecarClient.TurnSecondsVariable, turn);
        await using var mind = new MindSidecarClient();

        Assert.That(MindSidecarClient.TurnRequestTimeout, Is.EqualTo(TimeSpan.FromSeconds(window)));
        Assert.That(MindSidecarClient.TurnRequestCeiling, Is.EqualTo(TimeSpan.FromSeconds(ceiling)));
        Assert.That(mind.TurnWindow, Is.EqualTo(TimeSpan.FromSeconds(window)));
        Assert.That(mind.TurnCeiling, Is.EqualTo(TimeSpan.FromSeconds(ceiling)));
    }

    [Test]
    public void TheSwitchNeedsAKey()
    {
        var model = new ExternalModel(_root);

        Assert.That(model.Apply(new JsonObject { ["enabled"] = true }), Is.EqualTo("external_model_no_key"));
        Assert.That((bool?)model.Json()["enabled"], Is.False);

        Assert.That(model.Apply(new JsonObject { ["key"] = Key }), Is.Null);
        Assert.That(model.Apply(new JsonObject { ["enabled"] = true }), Is.Null);
        Assert.That((bool?)model.Json()["enabled"], Is.True);
    }

    [Test]
    public void AnotherCompanyNeedsItsOwnModelAndKeyAndToBeTurnedOnAgain()
    {
        var model = new ExternalModel(_root);
        model.Apply(new JsonObject { ["key"] = Key, ["enabled"] = true });

        Assert.That(model.Apply(new JsonObject { ["provider"] = "google" }), Is.Null);

        JsonObject read = model.Json();
        Assert.Multiple(() =>
        {
            Assert.That((bool?)read["enabled"], Is.False);
            Assert.That((bool?)read["hasKey"], Is.False);
            Assert.That((string?)read["model"], Is.Empty);
            Assert.That((bool?)read["ceilingHolds"], Is.False);
            Assert.That(model.Apply(new JsonObject { ["enabled"] = true }), Is.EqualTo("external_model_no_key"));
        });

        model.Apply(new JsonObject { ["key"] = Key });
        Assert.That(model.Apply(new JsonObject { ["enabled"] = true }), Is.EqualTo("external_model_no_model"));
        model.Apply(new JsonObject { ["model"] = " un-modelo " });
        Assert.That(model.Apply(new JsonObject { ["enabled"] = true }), Is.Null);
        Assert.That((string?)model.Json()["model"], Is.EqualTo("un-modelo"));
    }

    [Test]
    public void TheCeilingHoldsOnlyWhereThePricesAreKnown()
    {
        var model = new ExternalModel(_root);
        Assert.That((bool?)model.Json()["ceilingHolds"], Is.True);
        model.Apply(new JsonObject { ["model"] = "otro-claude" });
        Assert.That((bool?)model.Json()["ceilingHolds"], Is.False);
    }

    [Test]
    public void AnotherApiNeedsAnAddressAndItMustBeSafe()
    {
        var model = new ExternalModel(_root);
        model.Apply(new JsonObject { ["provider"] = "compatible", ["model"] = "m", ["key"] = Key });

        Assert.That(model.Apply(new JsonObject { ["enabled"] = true }), Is.EqualTo("external_model_no_url"));
        Assert.That(model.Apply(new JsonObject { ["url"] = "http://ejemplo.com/v1" }), Is.EqualTo("external_model_invalid_url"));
        Assert.That(model.Apply(new JsonObject { ["url"] = "https://ejemplo.com/v1" }), Is.Null);
        Assert.That(model.Apply(new JsonObject { ["enabled"] = true }), Is.Null);
    }

    [Test]
    public void OllamaNeedsNoKeyOnlyAModelChosenFromItsList()
    {
        var model = new ExternalModel(_root);
        model.Apply(new JsonObject { ["provider"] = "local" });

        Assert.Multiple(() =>
        {
            Assert.That((string?)model.Json()["url"], Is.EqualTo("http://127.0.0.1:11434"));
            Assert.That((bool?)model.Json()["ceilingHolds"], Is.False);
            Assert.That(model.Apply(new JsonObject { ["enabled"] = true }), Is.EqualTo("external_model_no_model"));
        });

        // Choosing from the list sends both at once.
        Assert.That(model.Apply(new JsonObject { ["model"] = "qwen:4b", ["enabled"] = true }), Is.Null);
        Assert.Multiple(() =>
        {
            Assert.That((bool?)model.Json()["enabled"], Is.True);
            Assert.That((string?)model.Json()["model"], Is.EqualTo("qwen:4b"));
        });
    }

    [Test]
    public async Task TheContextIsTheChosenModelsAndChangingItSwitchesAtOnce()
    {
        using var model = new ExternalModel(_root);
        // The first start reads what is chosen: a switch is only for what comes after it.
        await model.StartAsync(CancellationToken.None);
        model.Apply(new JsonObject { ["provider"] = "local" });
        Assert.That(model.Apply(new JsonObject { ["context"] = 96000 }), Is.EqualTo("external_model_invalid_context"), "no model to give it to");

        model.Apply(new JsonObject { ["model"] = "uno" });
        Assert.Multiple(() =>
        {
            Assert.That(model.Apply(new JsonObject { ["context"] = 96000 }), Is.Null);
            Assert.That(model.Apply(new JsonObject { ["context"] = 5 }), Is.EqualTo("external_model_invalid_context"));
            Assert.That((int?)model.Json()["context"], Is.EqualTo(96000));
        });

        model.Apply(new JsonObject { ["model"] = "dos" });
        Assert.That(model.Json()["context"], Is.Null, "each model has its own");
        model.Apply(new JsonObject { ["model"] = "uno", ["enabled"] = true });
        bool before = model.NeedsSwitch;
        model.Apply(new JsonObject { ["context"] = 128000 });
        Assert.Multiple(() =>
        {
            Assert.That(before, Is.True);
            Assert.That(model.NeedsSwitch, Is.True);
            Assert.That((int?)model.Json()["context"], Is.EqualTo(128000));
        });
    }

    [Test]
    public async Task AnOldConnectionErrorIsNotSaidWithTheOptionOff()
    {
        var model = new ExternalModel(_root);
        model.Apply(new JsonObject { ["provider"] = "local", ["model"] = "uno", ["enabled"] = true });
        await File.WriteAllTextAsync(Path.Combine(_root, "external-model", "traductor.log"), "ERROR: algo\n");
        Assert.That((string?)model.Json()["lastError"], Is.EqualTo("ERROR: algo"));
        model.Apply(new JsonObject { ["enabled"] = false });
        Assert.That(model.Json()["lastError"], Is.Null);
    }

    [Test]
    public void AnotherApiOnThisPcNeedsNoKey()
    {
        var model = new ExternalModel(_root);
        model.Apply(new JsonObject { ["provider"] = "compatible", ["model"] = "m", ["url"] = "http://localhost:1234/v1" });
        Assert.That(model.Apply(new JsonObject { ["enabled"] = true }), Is.Null);
    }

    [Test]
    public async Task WithNoKeyTheListAsksForOneAndWithNoOllamaItSaysSo()
    {
        using var model = new ExternalModel(_root);
        Assert.That((bool?)(await model.ModelsAsync(CancellationToken.None))["needsKey"], Is.True);

        Environment.SetEnvironmentVariable("OLLAMA_HOST", "127.0.0.1:9");
        model.Apply(new JsonObject { ["provider"] = "local" });
        Assert.That((string?)(await model.ModelsAsync(CancellationToken.None))["ollama"], Is.EqualTo("missing"));
    }

    [TestCase(null, "http://127.0.0.1:11434")]
    [TestCase("0.0.0.0:11434", "http://127.0.0.1:11434")]
    [TestCase("0.0.0.0", "http://127.0.0.1:11434")]
    [TestCase("[::]:11500", "http://127.0.0.1:11500")]
    [TestCase("127.0.0.1:11500", "http://127.0.0.1:11500")]
    [TestCase("http://localhost:8080/", "http://localhost:8080")]
    [TestCase("http://localhost", "http://localhost")]
    public void OllamaIsCalledWhereItsVariableSaysAndNeverOnTheAddressItListensOn(string? variable, string address)
    {
        Environment.SetEnvironmentVariable("OLLAMA_HOST", variable);
        Assert.That(ExternalModel.OllamaAddress(), Is.EqualTo(address));
    }

    [Test]
    public async Task WithNoOllamaTheEstimateSaysSoAndWithNoModelItAsksNothing()
    {
        using var model = new ExternalModel(_root);
        Environment.SetEnvironmentVariable("OLLAMA_HOST", "127.0.0.1:9");
        model.Apply(new JsonObject { ["provider"] = "local" });
        Assert.That(await model.EstimateAsync(null, null, CancellationToken.None), Is.Empty);
        model.Apply(new JsonObject { ["model"] = "uno" });
        Assert.That((string?)(await model.EstimateAsync(null, null, CancellationToken.None))["ollama"], Is.EqualTo("missing"));
    }

    [Test]
    public async Task TheRealTranslatorAnswersTheList()
    {
        string? repository = AppContext.BaseDirectory;
        while (repository is not null && !Directory.Exists(Path.Combine(repository, "src", "baxy_mind")))
        {
            repository = Path.GetDirectoryName(repository);
        }

        string python = Path.Combine(repository ?? string.Empty, ".venv-modelo-api", "Scripts", "python.exe");
        Assume.That(File.Exists(python), ".venv-modelo-api is not on this machine");
        Environment.SetEnvironmentVariable(ExternalModel.PythonVariable, python);
        Environment.SetEnvironmentVariable(MindSidecarClient.PythonPathEnvironmentVariable, Path.Combine(repository!, "src"));
        using var model = new ExternalModel(_root);
        // An address on this PC where nothing listens: the list says so instead of failing.
        model.Apply(new JsonObject { ["provider"] = "compatible", ["url"] = "http://127.0.0.1:9/v1" });

        JsonObject listed = await model.ModelsAsync(CancellationToken.None);

        Assert.That((string?)listed["error"], Is.EqualTo("no hay conexión"));
    }

    [Test]
    public void AnotherAddressForTheOtherApiTurnsItOffSoTheKeyGoesNowhereUnasked()
    {
        var model = new ExternalModel(_root);
        model.Apply(new JsonObject { ["provider"] = "compatible", ["model"] = "m", ["key"] = Key, ["url"] = "https://ejemplo.com/v1" });
        model.Apply(new JsonObject { ["enabled"] = true });

        Assert.That(model.Apply(new JsonObject { ["url"] = " https://ejemplo.com/v1 " }), Is.Null);
        Assert.That((bool?)model.Json()["enabled"], Is.True, "the same address changes nothing");

        Assert.That(model.Apply(new JsonObject { ["url"] = "https://ejmplo.com/v1" }), Is.Null);
        Assert.That((bool?)model.Json()["enabled"], Is.False);

        Assert.That(model.Apply(new JsonObject { ["url"] = "https://ejemplo.com/v1", ["enabled"] = true }), Is.Null);
        Assert.That((bool?)model.Json()["enabled"], Is.True, "the switch with the address written: the person asked for this one");
    }

    [Test]
    public void AnotherAddressForALocalServerSendsNoKeyAndStaysOn()
    {
        var model = new ExternalModel(_root);
        model.Apply(new JsonObject { ["provider"] = "local", ["model"] = "m", ["enabled"] = true });

        Assert.That(model.Apply(new JsonObject { ["url"] = "http://127.0.0.1:1234/v1" }), Is.Null);

        Assert.That((bool?)model.Json()["enabled"], Is.True);
    }

    [TestCase("https://usuario:token@ejemplo.com/v1")]
    [TestCase("https://ejemplo.com/v1?key=token")]
    [TestCase("https://ejemplo.com/v1#token")]
    [TestCase("http://usuario:token@localhost:1234/v1")]
    public void AnApiAddressHidesNoKey(string url)
    {
        var model = new ExternalModel(_root);
        model.Apply(new JsonObject { ["provider"] = "compatible" });

        Assert.That(model.Apply(new JsonObject { ["url"] = url }), Is.EqualTo("external_model_invalid_url"));
    }

    [TestCase("192.168.0.5")]
    [TestCase("192.168.0.5:11434")]
    [TestCase("10.0.0.1:8080")]
    [TestCase("ejemplo.com")]
    [TestCase("http://ejemplo.com:11434")]
    [TestCase("https://ollama.com")]
    [TestCase("http://usuario:token@localhost:1234")]
    [TestCase("http://localhost.ejemplo.com:1234")]
    [TestCase("127.0.0.1.ejemplo.com")]
    [TestCase(@"http://localhost\@ejemplo.com")]
    [TestCase(@"http://localhost\.ejemplo.com")]
    [TestCase("ftp://localhost:21")]
    public void AnOllamaOnAnotherMachineIsNotCalledBecauseLocalSaysNothingLeavesThisPc(string variable)
    {
        Environment.SetEnvironmentVariable("OLLAMA_HOST", variable);

        Assert.That(ExternalModel.OllamaAddress(), Is.EqualTo("http://127.0.0.1:11434"));
    }

    [TestCase("http://LOCALHOST:11434", "http://localhost:11434")]
    [TestCase("[::1]:1234", "http://[::1]:1234")]
    [TestCase("127.0.0.1", "http://127.0.0.1:11434")]
    // What sends would ask a network's DNS for this name.
    [TestCase("loopback:1234", "http://localhost:1234")]
    public void AnOllamaOnThisPcIsCalledAsItWasChecked(string variable, string address)
    {
        Environment.SetEnvironmentVariable("OLLAMA_HOST", variable);

        Assert.That(ExternalModel.OllamaAddress(), Is.EqualTo(address));
    }

    [TestCase("https://ejemplo.com/v1")]
    [TestCase("http://192.168.0.5:1234/v1")]
    public void LocalTakesNoAddressFromThePanel(string url)
    {
        var model = new ExternalModel(_root);
        model.Apply(new JsonObject { ["provider"] = "local" });

        Assert.That(model.Apply(new JsonObject { ["url"] = url }), Is.Null);
        Assert.That((string?)model.Json()["url"], Is.EqualTo("http://127.0.0.1:11434"));
    }

    [TestCase("192.168.0.5:11434")]
    [TestCase("0.0.0.0")]
    public void TheOllamaBaxyOpensListensWhereBaxyCallsIt(string variable)
    {
        Environment.SetEnvironmentVariable("OLLAMA_HOST", variable);

        ProcessStartInfo start = ExternalModel.OllamaServer("ollama.exe");

        Assert.That(start.Environment["OLLAMA_HOST"], Is.EqualTo("http://127.0.0.1:11434"));
    }

    [Test]
    public async Task OllamaIsAskedDirectlyWhateverProxyThisPcHas()
    {
        using var ollama = new OneAddress("{}");
        using var proxy = new OneAddress("{}");
        IWebProxy before = HttpClient.DefaultProxy;
        HttpClient.DefaultProxy = new WebProxy(proxy.Url);
        try
        {
            Environment.SetEnvironmentVariable("OLLAMA_HOST", ollama.Url);
            using var model = new ExternalModel(_root);
            model.Apply(new JsonObject { ["provider"] = "local", ["model"] = "uno" });

            await model.ModelsAsync(CancellationToken.None);
        }
        finally
        {
            HttpClient.DefaultProxy = before;
        }

        Assert.Multiple(() =>
        {
            Assert.That(proxy.Authorizations, Is.Empty);
            Assert.That(ollama.Authorizations, Is.Not.Empty);
        });
    }

    [Test]
    public async Task TheKeyGoesToAnAddressForTheListOnlyIfItWasSavedOrTurnedOnForIt()
    {
        UseTheRealTranslator();
        using var meant = new OneAddress("{\"data\":[{\"id\":\"m\"}]}");
        using var typo = new OneAddress("{\"data\":[{\"id\":\"m\"}]}");
        using var model = new ExternalModel(_root);
        model.Apply(new JsonObject { ["provider"] = "compatible", ["url"] = meant.Url + "/v1", ["key"] = Key });
        await model.ModelsAsync(CancellationToken.None);
        Assert.That(meant.Authorizations, Is.EqualTo(new[] { "Bearer " + Key }));

        model.Apply(new JsonObject { ["url"] = typo.Url + "/v1" });
        await model.ModelsAsync(CancellationToken.None);
        Assert.That(typo.Authorizations, Is.EqualTo(new string?[] { null }), "a typo gets no key");

        model.Apply(new JsonObject { ["model"] = "m", ["enabled"] = true });
        await model.ModelsAsync(CancellationToken.None);
        Assert.That(typo.Authorizations, Is.EqualTo(new[] { null, "Bearer " + Key }), "the person turned it on for this address");
    }

    [TestCase("openai")]
    [TestCase("google")]
    public async Task TheKeyOfACompanyGoesToNoAddressWrittenForOtra(string company)
    {
        UseTheRealTranslator();
        // So that the company itself is not asked: its list fails here, on this PC.
        Environment.SetEnvironmentVariable("HTTPS_PROXY", "http://127.0.0.1:9");
        using var otra = new OneAddress("{\"data\":[{\"id\":\"m\"}]}");
        using var model = new ExternalModel(_root);
        model.Apply(new JsonObject { ["provider"] = "compatible", ["url"] = otra.Url + "/v1" });
        model.Apply(new JsonObject { ["provider"] = company, ["key"] = Key });

        await model.ModelsAsync(CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(otra.Authorizations, Is.Empty);
            Assert.That((string?)model.Json()["url"], Is.Empty);
        });
    }

    [Test]
    public void TheAddressOfOtraIsOnlyOtrasAndAnotherCompanyLeavesItAsItWas()
    {
        var model = new ExternalModel(_root);
        model.Apply(new JsonObject { ["provider"] = "compatible", ["url"] = "https://ejemplo.com/v1" });
        model.Apply(new JsonObject { ["provider"] = "openai", ["key"] = Key });

        // The switch sends what the panel holds, and for a company that is no address.
        Assert.That(model.Apply(new JsonObject { ["model"] = "m", ["url"] = string.Empty, ["enabled"] = true }), Is.Null);
        model.Apply(new JsonObject { ["provider"] = "compatible" });

        Assert.That((string?)model.Json()["url"], Is.EqualTo("https://ejemplo.com/v1"));
    }

    // Uri calls it loopback, and urllib does not: what goes to it would go through a proxy set on this PC, key included.
    [Test]
    public void AnAddressOnlyUriCallsLocalIsNotOnThisPc()
    {
        var model = new ExternalModel(_root);
        model.Apply(new JsonObject { ["provider"] = "compatible" });
        Assert.That(model.Apply(new JsonObject { ["url"] = "http://[::127.0.0.1]:1234/v1" }), Is.EqualTo("external_model_invalid_url"));

        Environment.SetEnvironmentVariable("OLLAMA_HOST", "[::127.0.0.1]:1234");
        Assert.That(ExternalModel.OllamaAddress(), Is.EqualTo("http://127.0.0.1:11434"));
    }

    /// <summary>An address on this PC that answers everything with the same body and keeps each request's Authorization.</summary>
    private sealed class OneAddress : IDisposable
    {
        private readonly TcpListener _listener = new(IPAddress.Loopback, 0);
        private readonly List<string?> _seen = [];

        internal OneAddress(string body)
        {
            _listener.Start();
            _ = ServeAsync(body);
        }

        internal string Url => $"http://127.0.0.1:{((IPEndPoint)_listener.LocalEndpoint).Port}";

        internal IReadOnlyList<string?> Authorizations
        {
            get
            {
                lock (_seen)
                {
                    return [.. _seen];
                }
            }
        }

        public void Dispose() => _listener.Stop();

        private async Task ServeAsync(string body)
        {
            try
            {
                while (true)
                {
                    using TcpClient client = await _listener.AcceptTcpClientAsync();
                    NetworkStream stream = client.GetStream();
                    var reader = new StreamReader(stream, Encoding.ASCII);
                    string? authorization = null;
                    while (await reader.ReadLineAsync() is { Length: > 0 } line)
                    {
                        if (line.StartsWith("Authorization: ", StringComparison.OrdinalIgnoreCase))
                        {
                            authorization = line["Authorization: ".Length..];
                        }
                    }

                    lock (_seen)
                    {
                        _seen.Add(authorization);
                    }

                    byte[] answer = Encoding.ASCII.GetBytes($"HTTP/1.1 200 OK\r\nContent-Length: {body.Length}\r\nConnection: close\r\n\r\n{body}");
                    await stream.WriteAsync(answer);
                }
            }
            catch (Exception exception) when (exception is SocketException or ObjectDisposedException or IOException)
            {
                // the test ended
            }
        }
    }

    [TestCase("http://loopback:1234/v1", "http://localhost:1234/v1")]
    [TestCase("HTTPS://EJEMPLO.com/v1", "https://ejemplo.com/v1")]
    public void AnApiAddressIsKeptAsItWasChecked(string url, string kept)
    {
        var model = new ExternalModel(_root);
        model.Apply(new JsonObject { ["provider"] = "compatible" });

        Assert.That(model.Apply(new JsonObject { ["url"] = url }), Is.Null);
        Assert.That((string?)model.Json()["url"], Is.EqualTo(kept));
    }

    [Test]
    public void AnUnknownCompanyIsRefused()
    {
        Assert.That(new ExternalModel(_root).Apply(new JsonObject { ["provider"] = "nadie" }), Is.EqualTo("external_model_invalid_provider"));
    }

    [Test]
    public void AKeyIsNeverSentBackNorKeptReadable()
    {
        var model = new ExternalModel(_root);
        model.Apply(new JsonObject { ["key"] = "  " + Key + " " });

        Assert.That(model.Json().ToJsonString(), Does.Not.Contain(Key));
        Assert.That((bool?)model.Json()["hasKey"], Is.True);
        foreach (string file in Directory.GetFiles(_root, "*", SearchOption.AllDirectories))
        {
            Assert.That(Encoding.UTF8.GetString(File.ReadAllBytes(file)), Does.Not.Contain(Key));
        }
    }

    [Test]
    public void ForgettingTheKeyTurnsItOff()
    {
        var model = new ExternalModel(_root);
        model.Apply(new JsonObject { ["key"] = Key, ["enabled"] = true });

        Assert.That(model.Apply(new JsonObject { ["forgetKey"] = true }), Is.Null);

        Assert.Multiple(() =>
        {
            Assert.That((bool?)model.Json()["hasKey"], Is.False);
            Assert.That((bool?)model.Json()["enabled"], Is.False);
        });
    }

    [TestCase("")]
    [TestCase("   ")]
    [TestCase("sk-parte\nsecreta")]
    [TestCase("sk-parte\tsecreta")]
    public void AnEmptyKeyOrOneThatCannotGoInAHeaderIsRefused(string key)
    {
        Assert.That(new ExternalModel(_root).Apply(new JsonObject { ["key"] = key }), Is.EqualTo("external_model_invalid_key"));
    }

    [Test]
    public async Task ATranslatorThatIsNotThereLeavesTheLocalModelAndSaysWhy()
    {
        using var model = new ExternalModel(_root);
        model.Apply(new JsonObject { ["key"] = Key, ["enabled"] = true });

        await model.StartAsync(CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(model.Active, Is.False);
            Assert.That(model.Problem, Is.EqualTo("falta_traductor"));
            Assert.That(Environment.GetEnvironmentVariable("BAXY_MIND_LLAMA_REMOTE"), Is.Null);
        });
    }

    // The real translator, with a key no API would take: nothing here reaches a company.
    [TestCase("anthropic", "claude-opus-5-5", null)]
    [TestCase("google", "un-modelo", null)]
    [TestCase("compatible", "un-modelo", "https://ejemplo.invalid/v1")]
    [TestCase("local", "un-modelo", null)]
    public async Task TheAppStartsTheTranslatorPointsTheMindAtItAndLeavesNothingBehind(string provider, string name, string? url)
    {
        Environment.SetEnvironmentVariable("OLLAMA_HOST", "127.0.0.1:9");
        // The port the core's vision address already names: free here, so the translator takes it.
        using (var free = new System.Net.Sockets.TcpListener(System.Net.IPAddress.Loopback, 0))
        {
            free.Start();
            Environment.SetEnvironmentVariable("BAXY_MIND_LLAMA_PORT", ((System.Net.IPEndPoint)free.LocalEndpoint).Port.ToString(System.Globalization.CultureInfo.InvariantCulture));
        }

        UseTheRealTranslator();
        Environment.SetEnvironmentVariable("BAXY_VISION_ENDPOINT", "http://local-vision/");
        int port;
        var model = new ExternalModel(_root);
        try
        {
            var settings = new JsonObject { ["provider"] = provider, ["model"] = name, ["key"] = Key };
            if (url is not null)
            {
                settings["url"] = url;
            }

            Assert.That(model.Apply(settings), Is.Null);
            Assert.That(model.Apply(new JsonObject { ["enabled"] = true }), Is.Null);

            await model.StartAsync(CancellationToken.None);

            Assert.That(model.Problem, Is.Null);
            Assert.That(model.Active, Is.True);
            Assert.That((string?)model.Json()["activeModel"], Is.EqualTo(name));
            port = int.Parse(Environment.GetEnvironmentVariable("BAXY_MIND_LLAMA_REMOTE")!, System.Globalization.CultureInfo.InvariantCulture);
            Assert.That(Environment.GetEnvironmentVariable("BAXY_MIND_LLAMA_REMOTE"), Is.EqualTo(Environment.GetEnvironmentVariable("BAXY_MIND_LLAMA_PORT")));
            Assert.That((bool?)model.Json()["activeLocal"], Is.EqualTo(provider == "local"));
            using var http = new HttpClient();
            Assert.That(await http.GetStringAsync(new Uri($"http://127.0.0.1:{port}/props")), Does.Contain(name));
            Assert.That(Environment.GetEnvironmentVariable(MindSidecarClient.TurnSecondsVariable), Is.EqualTo(provider == "local" ? "300" : "90"));
            Assert.That(Environment.GetEnvironmentVariable("BAXY_RENEW_CTX"), Is.EqualTo(provider == "local" ? "78000" : "200000"));
            Assert.That(MindSidecarClient.TurnRequestTimeout, Is.EqualTo(TimeSpan.FromSeconds(provider == "local" ? 300 : 90)));
            Assert.That(Environment.GetEnvironmentVariable("ANTHROPIC_API_KEY") ?? string.Empty, Does.Not.Contain(Key));
            Assert.That(Environment.GetEnvironmentVariable("BAXY_EXTERNAL_API_KEY"), Is.Null);
        }
        finally
        {
            model.Stop();
        }

        Assert.Multiple(() =>
        {
            Assert.That(Environment.GetEnvironmentVariable("BAXY_MIND_LLAMA_REMOTE"), Is.Null);
            Assert.That(Environment.GetEnvironmentVariable(MindSidecarClient.TurnSecondsVariable), Is.Null);
            Assert.That(Environment.GetEnvironmentVariable("BAXY_RENEW_CTX"), Is.Null);
            Assert.That(Environment.GetEnvironmentVariable("BAXY_VISION_ENDPOINT"), Is.EqualTo("http://local-vision/"));
            Assert.That(MindSidecarClient.TurnRequestTimeout, Is.EqualTo(TimeSpan.FromSeconds(30)));
        });
        using var gone = new HttpClient { Timeout = TimeSpan.FromSeconds(2) };
        Assert.That(async () => await gone.GetAsync(new Uri($"http://127.0.0.1:{port}/health")), Throws.InstanceOf<Exception>());
        Assert.That(model.Active, Is.False);
    }

    private static void UseTheRealTranslator()
    {
        string? repository = AppContext.BaseDirectory;
        while (repository is not null && !Directory.Exists(Path.Combine(repository, "src", "baxy_mind")))
        {
            repository = Path.GetDirectoryName(repository);
        }

        string python = Path.Combine(repository ?? string.Empty, ".venv-modelo-api", "Scripts", "python.exe");
        Assume.That(File.Exists(python), ".venv-modelo-api, with the SDK, is not on this machine");
        Environment.SetEnvironmentVariable(ExternalModel.PythonVariable, python);
        Environment.SetEnvironmentVariable(ExternalModel.NoCheckVariable, "1");
        Environment.SetEnvironmentVariable(MindSidecarClient.PythonPathEnvironmentVariable, Path.Combine(repository!, "src"));
    }

    [Test]
    public async Task StoppedTheTranslatorItselfIsGoneNotOnlyItsLauncher()
    {
        UseTheRealTranslator();
        using var model = new ExternalModel(_root);
        model.Apply(new JsonObject { ["key"] = Key, ["enabled"] = true });
        string log = Path.Combine(_root, "external-model", "traductor.log");
        for (int round = 0; round < 3; round++)
        {
            await model.StartAsync(CancellationToken.None);
            Assert.That(model.Active, Is.True);

            model.Stop();
            // The next start asks at once for this log and for its port, which the same process holds.
            Assert.DoesNotThrow(() => File.Delete(log), "round {0}", round);
            model.Apply(new JsonObject { ["ceilingUsd"] = round + 1.0 });
        }
    }

    [Test]
    public async Task AMindStartedAfterItWasTurnedOffGoesBackToTheLocalModel()
    {
        UseTheRealTranslator();
        using var model = new ExternalModel(_root);
        model.Apply(new JsonObject { ["key"] = Key, ["enabled"] = true });
        await model.StartAsync(CancellationToken.None);
        Assert.That(model.Active, Is.True);

        model.Apply(new JsonObject { ["enabled"] = false });
        await model.StartAsync(CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(model.Active, Is.False);
            Assert.That(Environment.GetEnvironmentVariable("BAXY_MIND_LLAMA_REMOTE"), Is.Null);
        });
    }

    [Test]
    public async Task AnotherChoiceIsNotServedByTheTranslatorOfTheLastOne()
    {
        UseTheRealTranslator();
        using var model = new ExternalModel(_root);
        model.Apply(new JsonObject { ["key"] = Key, ["enabled"] = true });
        await model.StartAsync(CancellationToken.None);

        model.Apply(new JsonObject { ["provider"] = "google", ["model"] = "un-modelo", ["key"] = Key });
        model.Apply(new JsonObject { ["enabled"] = true });
        await model.StartAsync(CancellationToken.None);

        Assert.That((string?)model.Json()["activeModel"], Is.EqualTo("un-modelo"));
    }

    [Test]
    public async Task TurningItOffWhileTheEngineIsDownStopsSendingAtOnce()
    {
        UseTheRealTranslator();
        var model = new ExternalModel(_root);
        model.Apply(new JsonObject { ["key"] = Key, ["enabled"] = true });
        await model.StartAsync(CancellationToken.None);
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        {
            typeof(MainWindowViewModel).GetField("_externalModel", BindingFlags.Instance | BindingFlags.NonPublic)!
                .SetValue(viewModel, model);
            Assert.That(viewModel.CoreClient?.IsReady ?? false, Is.False);

            model.Apply(new JsonObject { ["enabled"] = false });
            viewModel.ExternalModelChanged();

            Assert.That(() => model.Active, Is.False.After(5000, 50));
            Assert.That(Environment.GetEnvironmentVariable("BAXY_MIND_LLAMA_REMOTE"), Is.Null);
        }
    }

    [Test]
    public async Task TurningItOffInTheMiddleOfATurnStopsSendingBeforeTheTurnEnds()
    {
        UseTheRealTranslator();
        var model = new ExternalModel(_root);
        model.Apply(new JsonObject { ["key"] = Key, ["enabled"] = true });
        await model.StartAsync(CancellationToken.None);
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        {
            typeof(MainWindowViewModel).GetField("_externalModel", BindingFlags.Instance | BindingFlags.NonPublic)!
                .SetValue(viewModel, model);
            var turn = (SemaphoreSlim)typeof(MainWindowViewModel).GetField("_turnGate", BindingFlags.Instance | BindingFlags.NonPublic)!
                .GetValue(viewModel)!;
            await turn.WaitAsync();
            try
            {
                string port = Environment.GetEnvironmentVariable("BAXY_MIND_LLAMA_REMOTE")!;
                model.Apply(new JsonObject { ["enabled"] = false });
                viewModel.ExternalModelChanged();

                using var gone = new HttpClient { Timeout = TimeSpan.FromSeconds(2) };
                Assert.That(async () => await gone.GetAsync(new Uri($"http://127.0.0.1:{port}/health")), Throws.InstanceOf<Exception>());
                Assert.That(model.Active, Is.False);
                Assert.That(Environment.GetEnvironmentVariable("BAXY_MIND_LLAMA_REMOTE"), Is.Null);
            }
            finally
            {
                turn.Release();
            }
        }
    }

    [Test]
    public async Task ATranslatorThatDiedAndCannotComeBackLeavesTheLocalModel()
    {
        UseTheRealTranslator();
        using var model = new ExternalModel(_root);
        model.Apply(new JsonObject { ["key"] = Key, ["enabled"] = true });
        await model.StartAsync(CancellationToken.None);
        var running = (System.Diagnostics.Process)typeof(ExternalModel).GetField("_translator", BindingFlags.Instance | BindingFlags.NonPublic)!
            .GetValue(model)!;
        running.Kill();
        running.WaitForExit(5000);
        Environment.SetEnvironmentVariable(ExternalModel.PythonVariable, null);

        await model.StartAsync(CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(model.Active, Is.False);
            Assert.That(model.Problem, Is.EqualTo("falta_traductor"));
            Assert.That(Environment.GetEnvironmentVariable("BAXY_MIND_LLAMA_REMOTE"), Is.Null);
        });
    }

    [Test]
    public async Task AStartCancelledHalfWayLeavesNothingAndTheNextOneWorks()
    {
        UseTheRealTranslator();
        using var model = new ExternalModel(_root);
        model.Apply(new JsonObject { ["key"] = Key, ["enabled"] = true });
        using var cancelled = new CancellationTokenSource();
        await cancelled.CancelAsync();

        Assert.That(async () => await model.StartAsync(cancelled.Token), Throws.InstanceOf<OperationCanceledException>());
        Assert.That(model.Active, Is.False);

        await model.StartAsync(CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(model.Active, Is.True);
            Assert.That(Environment.GetEnvironmentVariable("BAXY_MIND_LLAMA_REMOTE"), Is.Not.Null);
        });
    }

    [Test]
    public async Task ChangingAndGoingBackStillRelaunchesAMindWhoseTranslatorWasStopped()
    {
        UseTheRealTranslator();
        using var model = new ExternalModel(_root);
        model.Apply(new JsonObject { ["key"] = Key, ["enabled"] = true });
        await model.StartAsync(CancellationToken.None);

        model.Apply(new JsonObject { ["enabled"] = false });
        Assert.That(model.Cut(), Is.True);
        model.Apply(new JsonObject { ["enabled"] = true });

        Assert.That(model.NeedsSwitch, Is.True, "its port has nobody there");
        await model.StartAsync(CancellationToken.None);
        Assert.That(model.NeedsSwitch, Is.False);
        Assert.That(model.Active, Is.True);
    }

    [Test]
    public async Task AChangeCancelsAMindStartingOnTheTranslatorButNotOneOnTheLocalModel()
    {
        FieldInfo cut = typeof(MainWindowViewModel).GetField("_mindStartCut", BindingFlags.Instance | BindingFlags.NonPublic)!;
        FieldInfo external = typeof(MainWindowViewModel).GetField("_externalModel", BindingFlags.Instance | BindingFlags.NonPublic)!;
        UseTheRealTranslator();
        using var local = new ExternalModel(_root);
        await local.StartAsync(CancellationToken.None);
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        {
            external.SetValue(viewModel, local);
            CancellationToken starting = ((CancellationTokenSource)cut.GetValue(viewModel)!).Token;
            local.Apply(new JsonObject { ["key"] = Key, ["enabled"] = true });
            viewModel.ExternalModelChanged();
            Assert.That(starting.IsCancellationRequested, Is.False, "its model only has to finish loading");
            Assert.That(() => local.Switching, Is.False.After(5000, 50));

            await local.StartAsync(CancellationToken.None);
            starting = ((CancellationTokenSource)cut.GetValue(viewModel)!).Token;
            local.Apply(new JsonObject { ["enabled"] = false });
            viewModel.ExternalModelChanged();
            Assert.That(starting.IsCancellationRequested, Is.True, "it would wait on a port with nobody there");
        }
    }

    [Test]
    public async Task ATranslatorThatEndedByItselfIsNotShownAsConnected()
    {
        UseTheRealTranslator();
        using var model = new ExternalModel(_root);
        model.Apply(new JsonObject { ["key"] = Key, ["enabled"] = true });
        await model.StartAsync(CancellationToken.None);
        var running = (System.Diagnostics.Process)typeof(ExternalModel).GetField("_translator", BindingFlags.Instance | BindingFlags.NonPublic)!
            .GetValue(model)!;
        running.Kill();
        running.WaitForExit(5000);

        JsonObject read = model.Json();

        Assert.Multiple(() =>
        {
            Assert.That((bool?)read["active"], Is.False);
            Assert.That((string?)read["problem"], Is.EqualTo("traductor_caido"));
        });
    }

    [Test]
    public async Task WhatLeftThisPcInThisRunIsNotForgottenWhenItIsTurnedOff()
    {
        UseTheRealTranslator();
        using var model = new ExternalModel(_root);
        Assert.That((bool?)model.Json()["apiThisRun"], Is.False);
        model.Apply(new JsonObject { ["key"] = Key, ["enabled"] = true });
        await model.StartAsync(CancellationToken.None);

        model.Apply(new JsonObject { ["enabled"] = false });
        await model.StartAsync(CancellationToken.None);

        Assert.That((bool?)model.Json()["apiThisRun"], Is.True);
    }

    [Test]
    public async Task ALocalServerSendsNothingOutOfThisPcInARun()
    {
        UseTheRealTranslator();
        using var model = new ExternalModel(_root);
        model.Apply(new JsonObject { ["provider"] = "local", ["model"] = "m", ["url"] = "http://127.0.0.1:9/v1", ["enabled"] = true });

        await model.StartAsync(CancellationToken.None);

        Assert.That(model.Active, Is.True);
        Assert.That((bool?)model.Json()["apiThisRun"], Is.False);
    }

    [Test]
    public void BeforeAnyStartThereIsNothingToSwitch()
    {
        var model = new ExternalModel(_root);

        model.Apply(new JsonObject { ["key"] = Key, ["enabled"] = true });

        Assert.That(model.NeedsSwitch, Is.False, "the first start reads what is chosen");
    }

    [Test]
    public async Task AChangeAsksForASwitchOnlyWhenItChangesWhatTheMindRunsOn()
    {
        using var model = new ExternalModel(_root);
        await model.StartAsync(CancellationToken.None);
        Assert.That(model.NeedsSwitch, Is.False, "off, as it started");

        model.Apply(new JsonObject { ["key"] = Key });
        Assert.That(model.NeedsSwitch, Is.False, "a key saved while it is off changes nothing that runs");

        model.Apply(new JsonObject { ["enabled"] = true });
        Assert.That(model.NeedsSwitch, Is.True);

        await model.StartAsync(CancellationToken.None);
        Assert.That(model.NeedsSwitch, Is.False);

        model.Apply(new JsonObject { ["provider"] = "anthropic" });
        Assert.Multiple(() =>
        {
            Assert.That((bool?)model.Json()["enabled"], Is.True, "the same company again turns nothing off");
            Assert.That(model.NeedsSwitch, Is.False);
        });

        model.Apply(new JsonObject { ["model"] = "otro" });
        Assert.That(model.NeedsSwitch, Is.True);
    }

    [Test]
    public void ThereIsNoCeilingUnlessThePersonWritesOne()
    {
        var model = new ExternalModel(_root);
        Assert.That(model.Json()["ceilingUsd"], Is.Null);

        Assert.That(model.Apply(new JsonObject { ["ceilingUsd"] = 10.5 }), Is.Null);
        Assert.That((double?)model.Json()["ceilingUsd"], Is.EqualTo(10.5));

        Assert.That(model.Apply(new JsonObject { ["ceilingUsd"] = null }), Is.Null);
        Assert.That(model.Json()["ceilingUsd"], Is.Null);

        Assert.That(model.Apply(new JsonObject { ["ceilingUsd"] = -1.0 }), Is.EqualTo("external_model_invalid_ceiling"));
        Assert.That(model.Apply(new JsonObject { ["ceilingUsd"] = 5000.0 }), Is.EqualTo("external_model_invalid_ceiling"));
    }

    [Test]
    public async Task AWrittenCeilingAppliesAtOnce()
    {
        using var model = new ExternalModel(_root);
        model.Apply(new JsonObject { ["key"] = Key, ["enabled"] = true });
        await model.StartAsync(CancellationToken.None);
        Assert.That(model.NeedsSwitch, Is.False);

        model.Apply(new JsonObject { ["ceilingUsd"] = 5.0 });

        Assert.That(model.NeedsSwitch, Is.True);
    }

    [Test]
    public async Task TurnedOffNothingStarts()
    {
        using var model = new ExternalModel(_root);
        model.Apply(new JsonObject { ["key"] = Key });

        await model.StartAsync(CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(model.Active, Is.False);
            Assert.That(model.Problem, Is.Null);
        });
    }

    [Test]
    public void TheSpendingIsReadFromItsCounts()
    {
        var model = new ExternalModel(_root);
        model.Apply(new JsonObject { ["key"] = Key, ["enabled"] = true });
        string folder = Path.Combine(_root, "external-model");
        File.WriteAllText(Path.Combine(folder, "gasto.jsonl"), "{\"usd\":0.25}\n{\"usd\":0.5}\nroto\n");
        File.WriteAllText(Path.Combine(folder, "traductor.log"), "ok\nERROR: la API rechazó la clave\n");

        JsonObject read = model.Json();

        Assert.Multiple(() =>
        {
            Assert.That((double?)read["spentUsd"], Is.EqualTo(0.75));
            Assert.That((string?)read["lastError"], Does.StartWith("ERROR"));
        });
    }

    [Test]
    public void TurnedOffTheLastRunsFailureIsNotShown()
    {
        var model = new ExternalModel(_root);
        model.Apply(new JsonObject { ["key"] = Key, ["enabled"] = true });
        string folder = Path.Combine(_root, "external-model");
        File.WriteAllText(Path.Combine(folder, "gasto.jsonl"), "{\"usd\":5.0}\n");
        File.WriteAllText(Path.Combine(folder, "traductor.log"), "ok\nTOPE DE GASTO: 5.00 de 5.00 USD. No se llama a la API.\n");
        Assert.That((string?)model.Json()["lastError"], Does.StartWith("TOPE"));

        model.Apply(new JsonObject { ["enabled"] = false });

        JsonObject read = model.Json();
        Assert.Multiple(() =>
        {
            Assert.That((string?)read["lastError"], Is.Null);
            Assert.That((double?)read["spentUsd"], Is.EqualTo(5.0));
        });
    }

    [Test]
    public async Task TheViewsRoutesAnswerUnlessTheVariableRemovesThem()
    {
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            (int on, JsonObject seen) = await view.SendAsync("GET", "/settings/external-model");
            Environment.SetEnvironmentVariable(ExternalModel.Variable, "0");
            (int off, _) = await view.SendAsync("GET", "/settings/external-model");
            (int put, _) = await view.SendAsync("PUT", "/settings/external-model", new JsonObject { ["enabled"] = true });

            Assert.Multiple(() =>
            {
                Assert.That(on, Is.EqualTo(200));
                Assert.That((bool?)seen["available"], Is.True);
                Assert.That(off, Is.EqualTo(404));
                Assert.That(put, Is.EqualTo(404));
            });
        }
    }
}
