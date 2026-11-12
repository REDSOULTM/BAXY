using System.IO;
using System.Security.Cryptography;
using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// The registered runtime (src/Baxy.App/MindRuntimeDiscovery.cs). Entrega 1.1.0: BAXY installed and opened from the Start
/// menu has no launcher, so the voice, the ear, System One and the vision that scripts/run_renew.cmd gave the benches
/// reach the mind from the registration, each only where no variable names one.
/// </summary>
[TestFixture]
[NonParallelizable]
public sealed class MindRuntimeDiscoveryTests
{
    private static readonly string[] Touched =
    [
        "BAXY_MIND_DISABLED", "BAXY_MIND_PYTHON", "BAXY_MIND_PYTHONPATH", "BAXY_MIND_LLM_GGUF", "BAXY_MIND_LLAMA_SERVER",
        "BAXY_MIND_NGL", "BAXY_RENEW_TTS_DIR", "BAXY_RENEW_WAKE_DIR", "BAXY_RENEW_WAKE_FAST_DIR", "BAXY_RENEW_STT_DIR",
        "BAXY_S1_GGUF", "BAXY_S1_THREADS", "BAXY_MIND_MMPROJ", "BAXY_MIND_LLAMA_PORT", "BAXY_VISION_OFF",
        "BAXY_VISION_ENDPOINT", "BAXY_VISION_MODEL", "BAXY_VISION_SLOT", "BAXY_VISION_SLOT_DIR", "BAXY_MIND_SLOT",
        "BAXY_MIND_LLAMA_BACKEND", "BAXY_MIND_LLM_GGUF_SHA256", "BAXY_MIND_LLAMA_KEY", "BAXY_VISION_API_KEY",
    ];

    private readonly Dictionary<string, string?> _saved = [];
    private string _folder = null!;
    private string _local = null!;

    [SetUp]
    public void SetUp()
    {
        foreach (string name in Touched)
        {
            _saved[name] = Environment.GetEnvironmentVariable(name);
            Environment.SetEnvironmentVariable(name, null);
        }

        _folder = Path.Combine(Path.GetTempPath(), "baxy-app-tests", Guid.NewGuid().ToString("N"));
        _local = Path.Combine(_folder, "local");
        Directory.CreateDirectory(_local);
    }

    [TearDown]
    public void TearDown()
    {
        foreach ((string name, string? value) in _saved)
        {
            Environment.SetEnvironmentVariable(name, value);
        }

        Directory.Delete(_folder, recursive: true);
    }

    [Test]
    public void TheInstalledProductGetsEveryRegisteredPieceAndTheVisionOnItsProjector()
    {
        string registration = Register(out Pieces pieces);

        Assert.That(Apply(registration), Is.True);

        Assert.That(Variables(), Is.EqualTo(new Dictionary<string, string?>
        {
            ["BAXY_RENEW_TTS_DIR"] = pieces.Voice,
            ["BAXY_RENEW_WAKE_DIR"] = pieces.Wake,
            ["BAXY_RENEW_WAKE_FAST_DIR"] = pieces.WakeFast,
            ["BAXY_RENEW_STT_DIR"] = pieces.Stt,
            ["BAXY_S1_GGUF"] = null,
            ["BAXY_S1_THREADS"] = null,
            ["BAXY_MIND_MMPROJ"] = pieces.Projector,
            ["BAXY_MIND_LLAMA_PORT"] = "8077",
            ["BAXY_VISION_ENDPOINT"] = "http://127.0.0.1:8077/v1/chat/completions",
            ["BAXY_VISION_MODEL"] = "baxy",
            ["BAXY_VISION_SLOT"] = "0",
            ["BAXY_VISION_SLOT_DIR"] = Path.Combine(_local, "BAXY", "renew", "slots"),
        }));
        Assert.That(Environment.GetEnvironmentVariable("BAXY_MIND_PYTHON"), Does.EndWith("python.exe"));
    }

    // PRV1 (revisión de privacidad 2026-11-09, PRIV-04): the mind's llama-server started with no key, on a port any page
    // of this PC reaches. Each start of BAXY makes one at random before the mind and the engine start: the mind's
    // server asks it of every request, and the engine's vision calls carry it (LocalVisionEndpoint.Authorize).
    [Test]
    public void EachStartMakesAKeyForTheMindsServerAndTheEnginesVisionCarriesIt()
    {
        string registration = Register(out _);

        Assert.That(Apply(registration), Is.True);
        string? first = Environment.GetEnvironmentVariable(MindRuntimeDiscovery.ServerKeyVariable);
        Assert.That(first, Does.Match("^[0-9a-f]{64}$"));
        Assert.That(Environment.GetEnvironmentVariable("BAXY_VISION_API_KEY"), Is.EqualTo(first));

        // The same start again (a mind that is relaunched) keeps it: the server that is up was started with it.
        Assert.That(Apply(registration), Is.True);
        Assert.That(Environment.GetEnvironmentVariable(MindRuntimeDiscovery.ServerKeyVariable), Is.EqualTo(first));

        // Another start of BAXY, with nothing in its environment yet: another key.
        foreach (string name in Touched)
        {
            Environment.SetEnvironmentVariable(name, null);
        }

        Assert.That(Apply(registration), Is.True);
        Assert.That(Environment.GetEnvironmentVariable(MindRuntimeDiscovery.ServerKeyVariable),
            Does.Match("^[0-9a-f]{64}$").And.Not.EqualTo(first));
    }

    [Test]
    public void AKeyABenchGaveIsKeptAndAVisionServerOfItsOwnIsNotGivenTheMinds()
    {
        string registration = Register(out _);
        Environment.SetEnvironmentVariable(MindRuntimeDiscovery.ServerKeyVariable, "la-del-banco");
        Environment.SetEnvironmentVariable("BAXY_VISION_ENDPOINT", "http://127.0.0.1:9000/v1/chat/completions");

        Assert.That(Apply(registration), Is.True);

        Assert.That(Environment.GetEnvironmentVariable(MindRuntimeDiscovery.ServerKeyVariable), Is.EqualTo("la-del-banco"));
        Assert.That(Environment.GetEnvironmentVariable("BAXY_VISION_API_KEY"), Is.Null);
    }

    [Test]
    public void ABenchKeepsWhatItGivesAndTheVisionFollowsItsPort()
    {
        string registration = Register(out _);
        Environment.SetEnvironmentVariable("BAXY_RENEW_TTS_DIR", @"D:\otra-voz");
        Environment.SetEnvironmentVariable("BAXY_RENEW_WAKE_DIR", "none");
        Environment.SetEnvironmentVariable("BAXY_RENEW_WAKE_FAST_DIR", "none");
        Environment.SetEnvironmentVariable("BAXY_MIND_LLAMA_PORT", "8099");
        Environment.SetEnvironmentVariable("BAXY_VISION_SLOT_DIR", @"F:\slots");

        Assert.That(Apply(registration), Is.True);

        Assert.That(Environment.GetEnvironmentVariable("BAXY_RENEW_TTS_DIR"), Is.EqualTo(@"D:\otra-voz"));
        Assert.That(Environment.GetEnvironmentVariable("BAXY_RENEW_WAKE_DIR"), Is.EqualTo("none"));
        Assert.That(Environment.GetEnvironmentVariable("BAXY_RENEW_WAKE_FAST_DIR"), Is.EqualTo("none"));
        Assert.That(Environment.GetEnvironmentVariable("BAXY_VISION_ENDPOINT"),
            Is.EqualTo("http://127.0.0.1:8099/v1/chat/completions"));
        Assert.That(Environment.GetEnvironmentVariable("BAXY_VISION_SLOT_DIR"), Is.EqualTo(@"F:\slots"));
    }

    [Test]
    public void TheVisionTakesTheMindsSlotOnASharedServer()
    {
        // Encargo 11: several machines' minds share one server, each on its slot (BAXY_MIND_SLOT, measurement only); the
        // vision sets aside and asks on that same slot, never on slot 0, another machine's.
        string registration = Register(out _);
        Environment.SetEnvironmentVariable("BAXY_MIND_SLOT", "5");

        Assert.That(Apply(registration), Is.True);

        Assert.That(Environment.GetEnvironmentVariable("BAXY_VISION_SLOT"), Is.EqualTo("5"));
    }

    [Test]
    public void VisionOffKeepsTheProjector()
    {
        string registration = Register(out _);
        Environment.SetEnvironmentVariable("BAXY_VISION_OFF", "1");

        Assert.That(Apply(registration), Is.True);

        foreach (string name in (string[])["BAXY_MIND_MMPROJ", "BAXY_VISION_ENDPOINT", "BAXY_MIND_LLAMA_PORT"])
        {
            Assert.That(Environment.GetEnvironmentVariable(name), Is.Null, name);
        }

        Assert.That(Environment.GetEnvironmentVariable("BAXY_RENEW_TTS_DIR"), Is.Not.Null);
    }

    // A piece that is not what was registered stays off; the mind and the other pieces still start.
    [Test]
    public void AChangedPieceStaysOffAndTheRestStarts()
    {
        string registration = Register(out Pieces pieces);
        File.WriteAllText(Path.Combine(pieces.Voice, "voice.bin"), "otra voz");
        File.WriteAllText(pieces.Projector, "otro proyector");
        File.WriteAllText(Path.Combine(pieces.WakeFast, "head.onnx"), "otra cabeza");

        Assert.That(Apply(registration), Is.True);

        Assert.That(Environment.GetEnvironmentVariable("BAXY_RENEW_TTS_DIR"), Is.Null);
        Assert.That(Environment.GetEnvironmentVariable("BAXY_RENEW_WAKE_FAST_DIR"), Is.Null);
        Assert.That(Environment.GetEnvironmentVariable("BAXY_RENEW_WAKE_DIR"), Is.EqualTo(pieces.Wake));
        Assert.That(Environment.GetEnvironmentVariable("BAXY_MIND_MMPROJ"), Is.Null);
        Assert.That(Environment.GetEnvironmentVariable("BAXY_VISION_ENDPOINT"), Is.Null);
        Assert.That(Environment.GetEnvironmentVariable("BAXY_S1_GGUF"), Is.Null);
        Assert.That(Environment.GetEnvironmentVariable("BAXY_MIND_LLM_GGUF"), Does.EndWith("qwen.gguf"));
    }

    // V132 (1.3.2): the product's wake folder gone, emptied or not the installed one: everything else starts, the mind hears
    // no wake word, and the App knows why, to say it (FieldProductChannel's voice status) instead of a silent ear.
    [TestCase("gone", "wake_missing")]
    [TestCase("emptied", "wake_missing")]
    [TestCase("changed", "wake_changed")]
    [TestCase("extra", "wake_changed")]
    [TestCase("a file", "wake_missing")] // held-out (V132): a file where the folder was
    public void AWakeThatIsNotTheInstalledOneStartsTheRestAndSaysWhy(string how, string problem)
    {
        string registration = Register(out Pieces pieces);
        switch (how)
        {
            case "gone":
                Directory.Delete(pieces.Wake, recursive: true);
                break;
            case "emptied":
                foreach (string file in Directory.GetFiles(pieces.Wake))
                {
                    File.Delete(file);
                }

                break;
            case "changed":
                File.WriteAllText(Path.Combine(pieces.Wake, "config.json"), "{\"otro\": 1}");
                break;
            case "a file":
                Directory.Delete(pieces.Wake, recursive: true);
                File.WriteAllText(pieces.Wake, string.Empty);
                break;
            default:
                File.WriteAllText(Path.Combine(pieces.Wake, "desktop.ini"), "[.ShellClassInfo]");
                break;
        }

        MindRuntimeDiscoveryResult discovery = MindRuntimeDiscovery.DiscoverVerified(registration);

        Assert.That(discovery.Runtime?.Pieces.WakeProblem, Is.EqualTo(problem));
        Assert.That(MindRuntimeDiscovery.ApplyVerified(discovery, _local), Is.True);
        Assert.That(MindRuntimeDiscovery.WakeProblem(discovery), Is.EqualTo(problem));
        Assert.That(Environment.GetEnvironmentVariable("BAXY_RENEW_WAKE_DIR"), Is.Null);
        Assert.That(Environment.GetEnvironmentVariable("BAXY_RENEW_STT_DIR"), Is.EqualTo(pieces.Stt));
        Assert.That(Environment.GetEnvironmentVariable("BAXY_RENEW_TTS_DIR"), Is.EqualTo(pieces.Voice));
        Assert.That(Environment.GetEnvironmentVariable("BAXY_MIND_LLM_GGUF"), Does.EndWith("qwen.gguf"));
    }

    // The installed wake, a registration that names none, or a bench's own variable: nothing to say.
    [TestCase("installed")]
    [TestCase("unregistered")]
    [TestCase("bench")]
    [TestCase("pycache")] // held-out (V132): the mind's import writes __pycache__ inside it; subfolders are not its hash
    public void AWakeThatIsTheInstalledOneOrNotTheRegistrationsHasNothingToSay(string how)
    {
        string registration = Register(out Pieces pieces);
        if (how == "pycache")
        {
            Directory.CreateDirectory(Path.Combine(pieces.Wake, "__pycache__"));
            File.WriteAllText(Path.Combine(pieces.Wake, "__pycache__", "baxy_wake_runtime.cpython-312.pyc"), "x");
        }
        else if (how == "unregistered")
        {
            JsonObject document = JsonNode.Parse(File.ReadAllText(registration))!.AsObject();
            document.Remove("renew_wake_dir");
            document.Remove("renew_wake_sha256");
            File.WriteAllText(registration, document.ToJsonString());
        }
        else if (how == "bench")
        {
            Directory.Delete(pieces.Wake, recursive: true);
            Environment.SetEnvironmentVariable("BAXY_RENEW_WAKE_DIR", "none");
        }

        MindRuntimeDiscoveryResult discovery = MindRuntimeDiscovery.DiscoverVerified(registration);

        Assert.That(MindRuntimeDiscovery.ApplyVerified(discovery, _local), Is.True);
        Assert.That(MindRuntimeDiscovery.WakeProblem(discovery), Is.Null);
        Assert.That(discovery.Runtime?.Pieces.WakeProblem, how == "bench" ? Is.EqualTo("wake_missing") : Is.Null);
    }

    // A registration written before 1.1.0 (Definitivo's voice entries, no piece) still starts the mind, with no piece.
    [Test]
    public void ARegistrationBeforeThePiecesStillStartsTheMind()
    {
        string registration = Register(out _, legacy: true);

        Assert.That(Apply(registration), Is.True);

        Assert.That(Environment.GetEnvironmentVariable("BAXY_MIND_LLM_GGUF"), Does.EndWith("qwen.gguf"));
        Assert.That(Variables().Values, Is.All.Null);
    }

    // uso-93: a registration written before the fast package (or on a machine without it) starts every other piece, and
    // the mind hears k5 alone.
    [Test]
    public void ARegistrationWithoutTheFastPackageStartsTheRestAndK5Alone()
    {
        string registration = Register(out Pieces pieces);
        JsonObject document = JsonNode.Parse(File.ReadAllText(registration))!.AsObject();
        document.Remove("renew_wake_fast_dir");
        document.Remove("renew_wake_fast_sha256");
        File.WriteAllText(registration, document.ToJsonString());

        Assert.That(Apply(registration), Is.True);

        Assert.That(Environment.GetEnvironmentVariable("BAXY_RENEW_WAKE_FAST_DIR"), Is.Null);
        Assert.That(Environment.GetEnvironmentVariable("BAXY_RENEW_WAKE_DIR"), Is.EqualTo(pieces.Wake));
        Assert.That(Environment.GetEnvironmentVariable("BAXY_RENEW_STT_DIR"), Is.EqualTo(pieces.Stt));
    }

    [Test]
    public void AnUnknownPropertyStillRefusesTheRegistration()
    {
        string registration = Register(out _);
        JsonObject document = JsonNode.Parse(File.ReadAllText(registration))!.AsObject();
        document["tts_voice"] = "x";
        File.WriteAllText(registration, document.ToJsonString());

        Assert.That(MindRuntimeDiscovery.DiscoverVerified(registration).Runtime, Is.Null);
    }

    // QWB2: the package carries the stock model and offers the tuned one (scripts/build_steam.ps1, tuned_*). The offer does
    // not refuse the registration, and the stock model starts.
    [Test]
    public void ARegistrationWithTheTunedOfferStillStartsTheStockModel()
    {
        string registration = WithTunedOffer(RegisterPackaged(Path.Combine(_folder, "steamapps", "common", "BAXY"), @"python\python.exe"));

        MindRuntimeConfiguration? runtime = MindRuntimeDiscovery.DiscoverVerified(registration).Runtime;

        Assert.That(runtime, Is.Not.Null);
        Assert.That(runtime!.Gguf, Is.EqualTo(Path.Combine(Path.GetDirectoryName(registration)!, "models", "qwen.gguf")));
    }

    [Test]
    public void TheTunedOfferIsReadFromTheRegistration()
    {
        string registration = WithTunedOffer(RegisterPackaged(Path.Combine(_folder, "BAXY"), @"python\python.exe"));

        TunedModelOffer? offer = MindRuntimeDiscovery.TunedOffer(registration);

        Assert.That(offer, Is.EqualTo(new TunedModelOffer(TunedFile, TunedSha256, TunedBytes, TunedUrl, "Apache-2.0")));
    }

    [TestCase("tuned_gguf", @"..\BAXY-Qwen3.5-4B-c4-Q4_K_M.gguf")]
    [TestCase("tuned_gguf", "BAXY-Qwen3.5-4B-c4-Q4_K_M.bin")]
    [TestCase("tuned_gguf_sha256", "2C445631782A5C27B9948369E9432309528688B9B761FCE56586D796EA2F57C7")]
    [TestCase("tuned_gguf_url", "http://huggingface.co/REDSOULTM/BAXY-Qwen3.5-4B-GGUF/resolve/main/x.gguf")]
    [TestCase("tuned_gguf_bytes", "2740937440")]
    [TestCase("tuned_gguf_license", "")]
    public void AnOfferThatIsNotWellFormedIsNoOfferAndTheStockModelStillStarts(string property, string value)
    {
        string registration = WithTunedOffer(RegisterPackaged(Path.Combine(_folder, "BAXY"), @"python\python.exe"));
        JsonObject document = JsonNode.Parse(File.ReadAllText(registration))!.AsObject();
        document[property] = value;
        File.WriteAllText(registration, document.ToJsonString());

        Assert.That(MindRuntimeDiscovery.TunedOffer(registration), Is.Null);
        Assert.That(MindRuntimeDiscovery.DiscoverVerified(registration).Runtime, Is.Not.Null);
    }

    [Test]
    public void ARegistrationWithoutTheOfferOffersNothing()
    {
        string registration = RegisterPackaged(Path.Combine(_folder, "BAXY"), @"python\python.exe");

        Assert.That(MindRuntimeDiscovery.TunedOffer(registration), Is.Null);
        Assert.That(MindRuntimeDiscovery.TunedOffer(Path.Combine(_folder, "missing.json")), Is.Null);
    }

    // The mind keys its kept prompt prefix by the model's verified SHA-256 (llm_server.prefix_key), not by its size alone.
    [Test]
    public void TheRegisteredModelReachesTheMindWithItsVerifiedHash()
    {
        string registration = Register(out _);
        string sha256 = (string)JsonNode.Parse(File.ReadAllText(registration))!["gguf_sha256"]!;

        Assert.That(Apply(registration), Is.True);

        Assert.That(Environment.GetEnvironmentVariable(MindRuntimeDiscovery.GgufSha256Variable), Is.EqualTo(sha256));
    }

    [Test]
    public void AModelGivenByAVariableGetsNoRegisteredHash()
    {
        string registration = Register(out _);
        Environment.SetEnvironmentVariable("BAXY_MIND_LLM_GGUF", Write(Path.Combine(_folder, "other.gguf"), "other"));

        Assert.That(Apply(registration), Is.True);

        Assert.That(Environment.GetEnvironmentVariable(MindRuntimeDiscovery.GgufSha256Variable), Is.Null);
    }

    // The Steam build (scripts/build_steam.ps1) ships its registration with the product, its paths relative to it, in a
    // folder that may be named BAXY (Steam's install folder): the files beside it start the mind.
    [Test]
    public void APackagedRegistrationNamesTheProductsFilesBesideIt()
    {
        string registration = RegisterPackaged(Path.Combine(_folder, "steamapps", "common", "BAXY"), @"python\python.exe");

        MindRuntimeConfiguration? runtime = MindRuntimeDiscovery.DiscoverVerified(registration).Runtime;

        Assert.That(runtime, Is.Not.Null);
        Assert.That(runtime!.Python, Is.EqualTo(Path.Combine(Path.GetDirectoryName(registration)!, "python", "python.exe")));
        Assert.That(runtime.Gguf, Is.EqualTo(Path.Combine(Path.GetDirectoryName(registration)!, "models", "qwen.gguf")));
        Assert.That(runtime.Pieces.Voice, Is.EqualTo(Path.Combine(Path.GetDirectoryName(registration)!, "voice")));
    }

    [Test]
    public void ARelativePathNeverLeavesTheRegistrationsFolder()
    {
        string product = Path.Combine(_folder, "product");
        Write(Path.Combine(_folder, "outside", "python.exe"), "python");
        string registration = RegisterPackaged(product, @"..\outside\python.exe");

        Assert.That(MindRuntimeDiscovery.DiscoverVerified(registration).Runtime, Is.Null);
    }

    [Test]
    public void TheRegistrationTheAppShipsWinsOverTheMachines()
    {
        string product = Path.Combine(_folder, "product");
        string app = Path.Combine(product, "app");
        Directory.CreateDirectory(app);

        Assert.That(MindRuntimeDiscovery.DefaultRegistrationPath(app, _local),
            Is.EqualTo(Path.Combine(_local, "BAXYRuntime", "mind-runtime-v1.json")));

        string packaged = Write(Path.Combine(product, "mind-runtime-v1.json"), "{}");

        Assert.That(MindRuntimeDiscovery.DefaultRegistrationPath(app, _local), Is.EqualTo(packaged));
    }

    // uso-101: a store's package brings one llama-server folder per GPU backend and cannot rewrite its registration (a
    // store's folder is the store's), so the App picks the folder at every start by the GPU's PCI vendor (10DE NVIDIA, 1002
    // AMD, 8086 Intel). PCI ids are simulated here; the real reading is WindowsGpuVendors.
    [TestCase(0x10DEu, "llama", "cuda")]
    [TestCase(0x1002u, "llama-vulkan", "vulkan")]
    [TestCase(0x8086u, "llama-vulkan", "vulkan")]
    public void APackageWithBothServersPicksTheFolderOfThisMachinesGpu(uint vendor, string folder, string backend)
    {
        string registration = RegisterPackagedWithBothServers();

        MindRuntimeConfiguration? runtime = MindRuntimeDiscovery.DiscoverVerified(registration, () => [vendor]).Runtime;

        Assert.That(runtime, Is.Not.Null);
        Assert.That(runtime!.LlamaServer, Is.EqualTo(Path.Combine(Path.GetDirectoryName(registration)!, folder, "llama-server.exe")));
        Assert.That(runtime.LlamaBackend, Is.EqualTo(backend));
    }

    [TestCase(new[] { 0x8086u, 0x10DEu }, "llama")]
    [TestCase(new[] { 0x1002u, 0x10DEu }, "llama")]
    [TestCase(new[] { 0x8086u, 0x1002u }, "llama-vulkan")]
    public void NvidiaWinsBesideAnotherGpu(uint[] vendors, string folder)
    {
        string registration = RegisterPackagedWithBothServers();

        MindRuntimeConfiguration? runtime = MindRuntimeDiscovery.DiscoverVerified(registration, () => vendors).Runtime;

        Assert.That(runtime?.LlamaServer, Is.EqualTo(Path.Combine(Path.GetDirectoryName(registration)!, folder, "llama-server.exe")));
    }

    // 1414 is Microsoft's basic display adapter: a GPU without its driver looks like this.
    [TestCase(new uint[0])]
    [TestCase(new[] { 0x1414u })]
    public void AMachineWithNoSupportedGpuIsToldApartAndGetsNoRuntime(uint[] vendors)
    {
        string registration = RegisterPackagedWithBothServers();

        MindRuntimeDiscoveryResult found = MindRuntimeDiscovery.DiscoverVerified(registration, () => vendors);

        Assert.Multiple(() =>
        {
            Assert.That(found.NoSupportedGpu, Is.True);
            Assert.That(found.Runtime, Is.Null);
            Assert.That(found.CanConfigure, Is.False);
            Assert.That(MindRuntimeDiscovery.ApplyVerified(found, _local), Is.False);
            Assert.That(Environment.GetEnvironmentVariable("BAXY_MIND_LLAMA_SERVER"), Is.Null);
        });
    }

    [Test]
    public void TheChosenServerAndItsBackendReachTheMind()
    {
        string registration = RegisterPackagedWithBothServers();

        Assert.That(MindRuntimeDiscovery.ApplyVerified(MindRuntimeDiscovery.DiscoverVerified(registration, () => [0x1002u]), _local), Is.True);

        Assert.Multiple(() =>
        {
            Assert.That(Environment.GetEnvironmentVariable("BAXY_MIND_LLAMA_SERVER"),
                Is.EqualTo(Path.Combine(Path.GetDirectoryName(registration)!, "llama-vulkan", "llama-server.exe")));
            Assert.That(Environment.GetEnvironmentVariable("BAXY_MIND_LLAMA_BACKEND"), Is.EqualTo("vulkan"));
        });
    }

    // A bench names its own server, on any machine: no choice is made and nothing is refused.
    [Test]
    public void AGivenServerStillWinsAndNoChoiceIsMade()
    {
        string registration = RegisterPackagedWithBothServers();
        string given = Write(Path.Combine(_folder, "bench", "llama-server.exe"), "server");
        Environment.SetEnvironmentVariable("BAXY_MIND_LLAMA_SERVER", given);

        MindRuntimeDiscoveryResult found = MindRuntimeDiscovery.DiscoverVerified(
            registration, () => throw new AssertionException("the GPU is not read"));

        Assert.Multiple(() =>
        {
            Assert.That(found.NoSupportedGpu, Is.False);
            Assert.That(found.Runtime, Is.Not.Null);
            Assert.That(MindRuntimeDiscovery.ApplyVerified(found, _local), Is.True);
            Assert.That(Environment.GetEnvironmentVariable("BAXY_MIND_LLAMA_SERVER"), Is.EqualTo(given));
            Assert.That(Environment.GetEnvironmentVariable("BAXY_MIND_LLAMA_BACKEND"), Is.Null);
        });
    }

    [Test]
    public void AVulkanServerThatIsNotWhatWasRegisteredStartsNothing()
    {
        string registration = RegisterPackagedWithBothServers();
        File.WriteAllText(Path.Combine(Path.GetDirectoryName(registration)!, "llama-vulkan", "llama-server.exe"), "another");

        MindRuntimeDiscoveryResult found = MindRuntimeDiscovery.DiscoverVerified(registration, () => [0x1002u]);

        Assert.Multiple(() =>
        {
            Assert.That(found.Runtime, Is.Null);
            Assert.That(found.NoSupportedGpu, Is.False, "the GPU is supported; it is the package that is broken");
        });
    }

    // The GitHub release installs the CUDA folder only where the installer saw an NVIDIA GPU: a card added later, or one the
    // installer could not see, computes with the Vulkan folder that every installation has instead of not starting.
    [Test]
    public void ANvidiaMachineWhoseInstallationHasNoCudaFolderComputesWithVulkan()
    {
        string registration = RegisterPackagedWithBothServers();
        string folder = Path.GetDirectoryName(registration)!;
        Directory.Delete(Path.Combine(folder, "llama"), recursive: true);

        MindRuntimeConfiguration? runtime = MindRuntimeDiscovery.DiscoverVerified(registration, () => [0x10DEu]).Runtime;

        Assert.That(runtime?.LlamaServer, Is.EqualTo(Path.Combine(folder, "llama-vulkan", "llama-server.exe")));
        Assert.That(runtime?.LlamaBackend, Is.EqualTo("vulkan"));
    }

    [Test]
    public void ACudaServerThatIsThereButIsNotWhatWasRegisteredStartsNothing()
    {
        string registration = RegisterPackagedWithBothServers();
        File.WriteAllText(Path.Combine(Path.GetDirectoryName(registration)!, "llama", "llama-server.exe"), "another");

        MindRuntimeDiscoveryResult found = MindRuntimeDiscovery.DiscoverVerified(registration, () => [0x10DEu]);

        Assert.That(found.Runtime, Is.Null, "a damaged folder is a broken package, not a machine without the part");
    }

    // A registration with one server (this machine's, register_mind_runtime.ps1, or an earlier package) stays as it was.
    [Test]
    public void ARegistrationWithOneServerMakesNoChoice()
    {
        string registration = RegisterPackaged(Path.Combine(_folder, "one"), @"python\python.exe");

        MindRuntimeDiscoveryResult found = MindRuntimeDiscovery.DiscoverVerified(
            registration, () => throw new AssertionException("the GPU is not read"));

        Assert.Multiple(() =>
        {
            Assert.That(found.Runtime?.LlamaServer, Is.EqualTo(Path.Combine(Path.GetDirectoryName(registration)!, "llama", "llama-server.exe")));
            Assert.That(found.Runtime?.LlamaBackend, Is.Null);
            Assert.That(found.NoSupportedGpu, Is.False);
        });
    }

    // itch.io has no installer: a zip unpacked where this account cannot write starts just the same, each start reading
    // the files again because the hash store has nowhere to go.
    [Test]
    public void APackageInAFolderBaxyCannotWriteToStillStarts()
    {
        string registration = RegisterPackagedWithBothServers();
        var folder = new DirectoryInfo(Path.GetDirectoryName(registration)!);
        var user = System.Security.Principal.WindowsIdentity.GetCurrent().User!;
        var deny = new System.Security.AccessControl.FileSystemAccessRule(
            user,
            System.Security.AccessControl.FileSystemRights.CreateFiles | System.Security.AccessControl.FileSystemRights.WriteData,
            System.Security.AccessControl.AccessControlType.Deny);
        System.Security.AccessControl.DirectorySecurity security = folder.GetAccessControl();
        security.AddAccessRule(deny);
        folder.SetAccessControl(security);
        try
        {
            Assert.That(() => File.WriteAllText(Path.Combine(folder.FullName, "probe.txt"), "x"), Throws.TypeOf<UnauthorizedAccessException>());
            Assert.That(MindRuntimeDiscovery.DiscoverVerified(registration, () => [0x1002u]).Runtime, Is.Not.Null);
            Assert.That(File.Exists(Path.Combine(folder.FullName, RuntimeFileHashCache.FileName)), Is.False);
        }
        finally
        {
            security.RemoveAccessRule(deny);
            folder.SetAccessControl(security);
        }
    }

    [Test]
    public async Task AMachineWithNoSupportedGpuIsABreakdownSaidAsItsCauseAndNothingIsRelaunched()
    {
        using var fake = new FakeMind();
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            string registration = RegisterPackagedWithBothServers();
            // The fake's interpreter and this machine's server are variables, which would win; a store's package has none.
            Environment.SetEnvironmentVariable(MindSidecarClient.PythonEnvironmentVariable, null);
            Environment.SetEnvironmentVariable("BAXY_MIND_LLAMA_SERVER", null);
            bool started = viewModel.ApplyMindRuntime(MindRuntimeDiscovery.DiscoverVerified(registration, () => []));
            (int status, JsonObject agent) = await view.SendAsync("GET", "/agent/status");

            Assert.Multiple(() =>
            {
                Assert.That(started, Is.False);
                Assert.That(status, Is.EqualTo(200));
                Assert.That((string?)agent["failure"], Is.EqualTo(MainWindowViewModel.NoSupportedGpu));
                Assert.That(viewModel.MindFailed, Is.True);
            });
        }
    }

    // The real reading of this machine's GPUs (DXGI): whatever they are, it answers.
    [Test]
    public void TheMachinesGpuVendorsAreRead()
    {
        Assert.That(Baxy.Providers.Windows.SystemStatus.WindowsGpuVendors.Read, Throws.Nothing);
    }

    // uso-116 (N23): an install gets what is measured: without the decision model, registered or not. A bench gives it.
    [Test]
    public void ARegisteredDecisionModelIsNotHandedAndAGivenOneIsKept()
    {
        string registration = Register(out _);
        Assert.That(Apply(registration), Is.True);
        Assert.That(Environment.GetEnvironmentVariable("BAXY_S1_GGUF"), Is.Null);

        Environment.SetEnvironmentVariable("BAXY_S1_GGUF", "dado.gguf");
        Assert.That(Apply(registration), Is.True);
        Assert.That(Environment.GetEnvironmentVariable("BAXY_S1_GGUF"), Is.EqualTo("dado.gguf"));
    }

    // uso-116 (N23): a new user whose install is short of something read «El modelo no está disponible» and nothing else.
    [Test]
    public void NoRegistrationSaysBaxyIsNotInstalled()
    {
        Assert.That(MindRuntimeDiscovery.DiscoverVerified(Path.Combine(_folder, "nada.json")).Problem, Is.EqualTo("sin_instalar"));
    }

    [Test]
    public void AModelThatIsNotThereIsNamed()
    {
        string registration = Register(out _);
        File.Delete(Path.Combine(_folder, "runtime", "qwen.gguf"));

        MindRuntimeDiscoveryResult found = MindRuntimeDiscovery.DiscoverVerified(registration);

        Assert.Multiple(() =>
        {
            Assert.That(found.Runtime, Is.Null);
            Assert.That(found.Problem, Is.EqualTo("modelo_ausente"));
        });
    }

    [Test]
    public void AModelThatIsNotTheRegisteredOneIsNamed()
    {
        string registration = Register(out _);
        File.WriteAllText(Path.Combine(_folder, "runtime", "qwen.gguf"), "otro");

        Assert.That(MindRuntimeDiscovery.DiscoverVerified(registration).Problem, Is.EqualTo("modelo_danado"));
    }

    [TestCase("python", "python.exe")]
    [TestCase("llama", "llama-server.exe")]
    public void AnotherPieceThatIsNotThereIsAMissingComponent(string folder, string file)
    {
        string registration = Register(out _);
        File.Delete(Path.Combine(_folder, "runtime", folder, file));

        Assert.That(MindRuntimeDiscovery.DiscoverVerified(registration).Problem, Is.EqualTo("componente_ausente"));
    }

    [Test]
    public void AGoodRegistrationHasNoProblem()
    {
        Assert.That(MindRuntimeDiscovery.DiscoverVerified(Register(out _)).Problem, Is.Null);
    }

    [Test]
    public void AnExplicitInterpreterThatIsNotThereIsAMissingComponent()
    {
        Environment.SetEnvironmentVariable(MindSidecarClient.PythonEnvironmentVariable, Path.Combine(_folder, "no", "python.exe"));

        Assert.That(MindRuntimeDiscovery.DiscoverVerified(Register(out _)).Problem, Is.EqualTo("componente_ausente"));
    }

    // A store's package names its files relative to the registration: the cause is read in the package, not in the current folder.
    [Test]
    public void APackagesMissingModelIsNamedAndAPackagesMissingPieceIsNotTheModel()
    {
        string registration = RegisterPackagedWithBothServers();
        string folder = Path.GetDirectoryName(registration)!;
        File.Delete(Path.Combine(folder, "python", "python.exe"));

        Assert.That(MindRuntimeDiscovery.DiscoverVerified(registration, () => [0x1002u]).Problem, Is.EqualTo("componente_ausente"));

        File.Delete(Path.Combine(folder, "models", "qwen.gguf"));

        Assert.That(MindRuntimeDiscovery.DiscoverVerified(registration, () => [0x1002u]).Problem, Is.EqualTo("modelo_ausente"));
    }

    // The folder's hash is the one scripts/mind_runtime_manifest.ps1 writes (Get-BaxyDirectorySha256).
    [Test]
    public void AFoldersHashIsOfItsFilesByOrdinalName()
    {
        string folder = Path.Combine(_folder, "dir");
        Directory.CreateDirectory(Path.Combine(folder, "__pycache__"));
        File.WriteAllText(Path.Combine(folder, "a.txt"), "a");
        File.WriteAllText(Path.Combine(folder, "B.txt"), "B");
        File.WriteAllText(Path.Combine(folder, "__pycache__", "x.pyc"), "x");
        string expected = Sha256Text($"B.txt:{Sha256Text("B")}\na.txt:{Sha256Text("a")}\n");

        Assert.That(MindRuntimeDiscovery.DirectorySha256(Hashes(), folder), Is.EqualTo(expected));
    }

    private sealed record Pieces(
        string Voice, string Wake, string WakeFast, string Stt, string SystemOne, string Projector);

    private const string TunedFile = "BAXY-Qwen3.5-4B-c4-Q4_K_M.gguf";
    private const string TunedSha256 = "2c445631782a5c27b9948369e9432309528688b9b761fce56586d796ea2f57c7";
    private const long TunedBytes = 2740937440;
    private const string TunedUrl =
        "https://huggingface.co/REDSOULTM/BAXY-Qwen3.5-4B-GGUF/resolve/da66d8bbb0b90ae15fc54cb4386370a4a471d54f/" + TunedFile;

    private static string WithTunedOffer(string registration)
    {
        JsonObject document = JsonNode.Parse(File.ReadAllText(registration))!.AsObject();
        document["tuned_gguf"] = TunedFile;
        document["tuned_gguf_sha256"] = TunedSha256;
        document["tuned_gguf_bytes"] = TunedBytes;
        document["tuned_gguf_url"] = TunedUrl;
        document["tuned_gguf_license"] = "Apache-2.0";
        File.WriteAllText(registration, document.ToJsonString());
        return registration;
    }

    private bool Apply(string registration) =>
        MindRuntimeDiscovery.ApplyVerified(MindRuntimeDiscovery.DiscoverVerified(registration), _local);

    private static Dictionary<string, string?> Variables() =>
        new[]
        {
            "BAXY_RENEW_TTS_DIR", "BAXY_RENEW_WAKE_DIR", "BAXY_RENEW_WAKE_FAST_DIR", "BAXY_RENEW_STT_DIR", "BAXY_S1_GGUF",
            "BAXY_S1_THREADS", "BAXY_MIND_MMPROJ", "BAXY_MIND_LLAMA_PORT", "BAXY_VISION_ENDPOINT", "BAXY_VISION_MODEL",
            "BAXY_VISION_SLOT", "BAXY_VISION_SLOT_DIR",
        }.ToDictionary(static name => name, static name => Environment.GetEnvironmentVariable(name));

    private string Register(out Pieces pieces, bool legacy = false)
    {
        string runtime = Path.Combine(_folder, "runtime");
        string python = Write(Path.Combine(runtime, "python", "python.exe"), "python");
        string source = Path.Combine(runtime, "src");
        Write(Path.Combine(source, "baxy_mind", "__main__.py"), "# mind");
        string gguf = Write(Path.Combine(runtime, "qwen.gguf"), "qwen");
        string server = Write(Path.Combine(runtime, "llama", "llama-server.exe"), "server");
        pieces = new Pieces(
            Folder(Path.Combine(runtime, "voice"), "baxy-voice.json", "voice.bin"),
            Folder(Path.Combine(runtime, "wake"), "config.json", "baxy_wake_runtime.py"),
            Folder(Path.Combine(runtime, "wake-fast"), "config.json", "head.onnx", "baxy_wake_runtime.py"),
            Folder(Path.Combine(runtime, "stt"), "tokens.txt", "encoder.int8.onnx"),
            Write(Path.Combine(runtime, "laya.gguf"), "laya"),
            Write(Path.Combine(runtime, "mmproj.gguf"), "mmproj"));
        var document = new JsonObject
        {
            ["schema"] = "baxy-mind-runtime-v1",
            ["python"] = python,
            ["python_sha256"] = Sha256File(python),
            ["python_path"] = source,
            ["gguf"] = gguf,
            ["gguf_sha256"] = Sha256File(gguf),
            ["llama_server"] = server,
            ["llama_server_sha256"] = Sha256File(server),
            ["ngl"] = 99,
        };
        if (legacy)
        {
            document["stt_dir"] = pieces.Stt;
            document["stt_sha256"] = new string('0', 64);
            document["wake_manifest"] = null;
            document["wake_manifest_sha256"] = null;
            document["tts_model"] = null;
            document["tts_sha256"] = null;
            document["wake_on_start"] = false;
        }
        else
        {
            document["renew_tts_dir"] = pieces.Voice;
            document["renew_tts_sha256"] = MindRuntimeDiscovery.DirectorySha256(Hashes(), pieces.Voice);
            document["renew_wake_dir"] = pieces.Wake;
            document["renew_wake_sha256"] = MindRuntimeDiscovery.DirectorySha256(Hashes(), pieces.Wake);
            document["renew_wake_fast_dir"] = pieces.WakeFast;
            document["renew_wake_fast_sha256"] = MindRuntimeDiscovery.DirectorySha256(Hashes(), pieces.WakeFast);
            document["renew_stt_dir"] = pieces.Stt;
            document["renew_stt_sha256"] = MindRuntimeDiscovery.DirectorySha256(Hashes(), pieces.Stt);
            document["s1_gguf"] = pieces.SystemOne;
            document["s1_gguf_sha256"] = Sha256File(pieces.SystemOne);
            document["s1_threads"] = 6;
            document["mmproj"] = pieces.Projector;
            document["mmproj_sha256"] = Sha256File(pieces.Projector);
        }

        string registration = Path.Combine(_folder, "registration", "mind-runtime-v1.json");
        Write(registration, document.ToJsonString());
        return registration;
    }

    private string RegisterPackagedWithBothServers()
    {
        string registration = RegisterPackaged(Path.Combine(_folder, "steamapps", "common", "BAXY"), @"python\python.exe");
        string vulkan = Write(Path.Combine(Path.GetDirectoryName(registration)!, "llama-vulkan", "llama-server.exe"), "server");
        JsonObject document = JsonNode.Parse(File.ReadAllText(registration))!.AsObject();
        document["llama_server_vulkan"] = @"llama-vulkan\llama-server.exe";
        document["llama_server_vulkan_sha256"] = Sha256File(vulkan);
        File.WriteAllText(registration, document.ToJsonString());
        return registration;
    }

    private static string RegisterPackaged(string product, string python)
    {
        string interpreter = Write(Path.GetFullPath(Path.Combine(product, python)), "python");
        Write(Path.Combine(product, "mind", "baxy_mind", "__main__.py"), "# mind");
        string gguf = Write(Path.Combine(product, "models", "qwen.gguf"), "qwen");
        string server = Write(Path.Combine(product, "llama", "llama-server.exe"), "server");
        string voice = Folder(Path.Combine(product, "voice"), "baxy-voice.json", "voice.bin");
        var document = new JsonObject
        {
            ["schema"] = "baxy-mind-runtime-v1",
            ["python"] = python,
            ["python_sha256"] = Sha256File(interpreter),
            ["python_path"] = "mind",
            ["gguf"] = @"models\qwen.gguf",
            ["gguf_sha256"] = Sha256File(gguf),
            ["llama_server"] = @"llama\llama-server.exe",
            ["llama_server_sha256"] = Sha256File(server),
            ["ngl"] = 99,
            ["renew_tts_dir"] = "voice",
            ["renew_tts_sha256"] = MindRuntimeDiscovery.DirectorySha256(Hashes(), voice),
        };
        return Write(Path.Combine(product, "mind-runtime-v1.json"), document.ToJsonString());
    }

    private static string Folder(string folder, params string[] names)
    {
        foreach (string name in names)
        {
            Write(Path.Combine(folder, name), name);
        }

        return folder;
    }

    private static string Write(string path, string text)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        File.WriteAllText(path, text);
        return path;
    }

    private static RuntimeFileHashCache Hashes() => new(null, Sha256File);

    private static string Sha256File(string path) => Convert.ToHexStringLower(SHA256.HashData(File.ReadAllBytes(path)));

    private static string Sha256Text(string text) =>
        Convert.ToHexStringLower(SHA256.HashData(System.Text.Encoding.UTF8.GetBytes(text)));
}
