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
        "BAXY_MIND_NGL", "BAXY_RENEW_TTS_DIR", "BAXY_RENEW_WAKE_DIR", "BAXY_RENEW_STT_DIR", "BAXY_S1_GGUF",
        "BAXY_S1_THREADS", "BAXY_MIND_MMPROJ", "BAXY_MIND_LLAMA_PORT", "BAXY_VISION_OFF", "BAXY_VISION_ENDPOINT",
        "BAXY_VISION_MODEL", "BAXY_VISION_SLOT", "BAXY_VISION_SLOT_DIR",
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
            ["BAXY_RENEW_STT_DIR"] = pieces.Stt,
            ["BAXY_S1_GGUF"] = pieces.SystemOne,
            ["BAXY_S1_THREADS"] = "6",
            ["BAXY_MIND_MMPROJ"] = pieces.Projector,
            ["BAXY_MIND_LLAMA_PORT"] = "8077",
            ["BAXY_VISION_ENDPOINT"] = "http://127.0.0.1:8077/v1/chat/completions",
            ["BAXY_VISION_MODEL"] = "baxy",
            ["BAXY_VISION_SLOT"] = "0",
            ["BAXY_VISION_SLOT_DIR"] = Path.Combine(_local, "BAXY", "renew", "slots"),
        }));
        Assert.That(Environment.GetEnvironmentVariable("BAXY_MIND_PYTHON"), Does.EndWith("python.exe"));
    }

    [Test]
    public void ABenchKeepsWhatItGivesAndTheVisionFollowsItsPort()
    {
        string registration = Register(out _);
        Environment.SetEnvironmentVariable("BAXY_RENEW_TTS_DIR", @"D:\otra-voz");
        Environment.SetEnvironmentVariable("BAXY_RENEW_WAKE_DIR", "none");
        Environment.SetEnvironmentVariable("BAXY_MIND_LLAMA_PORT", "8099");
        Environment.SetEnvironmentVariable("BAXY_VISION_SLOT_DIR", @"F:\slots");

        Assert.That(Apply(registration), Is.True);

        Assert.That(Environment.GetEnvironmentVariable("BAXY_RENEW_TTS_DIR"), Is.EqualTo(@"D:\otra-voz"));
        Assert.That(Environment.GetEnvironmentVariable("BAXY_RENEW_WAKE_DIR"), Is.EqualTo("none"));
        Assert.That(Environment.GetEnvironmentVariable("BAXY_VISION_ENDPOINT"),
            Is.EqualTo("http://127.0.0.1:8099/v1/chat/completions"));
        Assert.That(Environment.GetEnvironmentVariable("BAXY_VISION_SLOT_DIR"), Is.EqualTo(@"F:\slots"));
    }

    [Test]
    public void TheOwnersSwitchKeepsSystemOneOffAndVisionOffKeepsTheProjector()
    {
        string registration = Register(out _);
        string off = Path.Combine(_local, "BAXY", "renew", "system_one.off");
        Directory.CreateDirectory(Path.GetDirectoryName(off)!);
        File.WriteAllText(off, string.Empty);
        Environment.SetEnvironmentVariable("BAXY_VISION_OFF", "1");

        Assert.That(Apply(registration), Is.True);

        foreach (string name in (string[])["BAXY_S1_GGUF", "BAXY_S1_THREADS", "BAXY_MIND_MMPROJ", "BAXY_VISION_ENDPOINT",
                     "BAXY_MIND_LLAMA_PORT"])
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

        Assert.That(Apply(registration), Is.True);

        Assert.That(Environment.GetEnvironmentVariable("BAXY_RENEW_TTS_DIR"), Is.Null);
        Assert.That(Environment.GetEnvironmentVariable("BAXY_MIND_MMPROJ"), Is.Null);
        Assert.That(Environment.GetEnvironmentVariable("BAXY_VISION_ENDPOINT"), Is.Null);
        Assert.That(Environment.GetEnvironmentVariable("BAXY_S1_GGUF"), Is.EqualTo(pieces.SystemOne));
        Assert.That(Environment.GetEnvironmentVariable("BAXY_MIND_LLM_GGUF"), Does.EndWith("qwen.gguf"));
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

    [Test]
    public void AnUnknownPropertyStillRefusesTheRegistration()
    {
        string registration = Register(out _);
        JsonObject document = JsonNode.Parse(File.ReadAllText(registration))!.AsObject();
        document["tts_voice"] = "x";
        File.WriteAllText(registration, document.ToJsonString());

        Assert.That(MindRuntimeDiscovery.DiscoverVerified(registration).Runtime, Is.Null);
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

    private sealed record Pieces(string Voice, string Wake, string Stt, string SystemOne, string Projector);

    private bool Apply(string registration) =>
        MindRuntimeDiscovery.ApplyVerified(MindRuntimeDiscovery.DiscoverVerified(registration), _local);

    private static Dictionary<string, string?> Variables() =>
        new[]
        {
            "BAXY_RENEW_TTS_DIR", "BAXY_RENEW_WAKE_DIR", "BAXY_RENEW_STT_DIR", "BAXY_S1_GGUF", "BAXY_S1_THREADS",
            "BAXY_MIND_MMPROJ", "BAXY_MIND_LLAMA_PORT", "BAXY_VISION_ENDPOINT", "BAXY_VISION_MODEL", "BAXY_VISION_SLOT",
            "BAXY_VISION_SLOT_DIR",
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
