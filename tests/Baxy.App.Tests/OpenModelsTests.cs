using System.IO;
using System.IO.Compression;
using System.Net;
using System.Net.Http;
using System.Net.Sockets;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json.Nodes;
using Baxy.Installer;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// Pedido del dueño 2026-11-08: the person writes a model's name in Settings, BAXY says what Hugging Face has under it (size,
/// license, tools, whether it fits) and Ollama installs it; Ollama itself is installed from Settings, verified by SHA-256.
/// Hugging Face and GitHub are stand-ins here; Ollama is a stand-in on this PC.
/// </summary>
[TestFixture]
[NonParallelizable]
public sealed class OpenModelsTests
{
    private const long Gigabyte = 1_000_000_000;
    private string _root = "";

    [SetUp]
    public void SetUp() => _root = Directory.CreateTempSubdirectory("baxy-open-models-").FullName;

    [TearDown]
    public void TearDown()
    {
        Environment.SetEnvironmentVariable("OLLAMA_HOST", null);
        Directory.Delete(_root, recursive: true);
    }

    [TestCase("Qwen3.5-4B-Q4_K_M.gguf", "Q4_K_M")]
    [TestCase("gemma-4-E2B-it-UD-Q4_K_XL.gguf", "Q4_K_XL")]
    [TestCase("Llama-3.2-3B-Instruct-IQ4_XS.gguf", "IQ4_XS")]
    [TestCase("granite-4.0-h-micro-Q8_0.gguf", "Q8_0")]
    [TestCase("Qwen3.5-4B-BF16.gguf", "BF16")]
    [TestCase("modelo.gguf", null)]
    public void TheQuantizationIsTheEndOfTheFilesName(string file, string? quant) =>
        Assert.That(OpenModels.QuantOf(file), Is.EqualTo(quant));

    [Test]
    public async Task ASearchSaysWhatItWouldInstallItsSizeLicenseToolsAndWhetherItFits()
    {
        var hub = new Hub();
        hub.Pages["/api/models"] = """[{"id":"unsloth/Qwen3.5-4B-GGUF"},{"id":"alguien/SinHerramientas-GGUF"},{"id":"no es un repo"}]""";
        hub.Pages["/api/models/unsloth/Qwen3.5-4B-GGUF"] = Repository(
            "apache-2.0", "{% if tools %}{{ tools }}{% endif %}", 262144,
            ("Qwen3.5-4B-Q8_0.gguf", 4_500_000_000), ("Qwen3.5-4B-Q4_K_M.gguf", 2_740_937_888), ("mmproj-F16.gguf", 670_000_000),
            ("BF16/Qwen3.5-4B-BF16-00001-of-00002.gguf", 4_000_000_000));
        hub.Pages["/api/models/alguien/SinHerramientas-GGUF"] = Repository("mit", "{{ messages }}", 131072, ("m-Q4_K_M.gguf", 1_000_000_000));
        hub.Files["/unsloth/Qwen3.5-4B-GGUF/resolve/main/Qwen3.5-4B-Q4_K_M.gguf"] = ModelMemoryTests.Qwen35;
        using var models = new OpenModels(_root, hub);
        var online = new List<string>();
        models.WentOnline += online.Add;

        JsonObject found = await models.SearchAsync("gemma 4b", 8L << 30, CancellationToken.None);

        var results = (JsonArray)found["results"]!;
        Assert.Multiple(() =>
        {
            Assert.That(hub.Asked[0], Does.Contain("search=gemma%204b").And.Contain("filter=gguf"));
            Assert.That(results, Has.Count.EqualTo(2), "an id that is not a repository is not asked for");
            // Pedido del dueño 2026-11-08: the model alone is installed, and its vision only if the person adds it.
            Assert.That((string?)results[0]!["name"], Is.EqualTo("unsloth/Qwen3.5-4B-GGUF:Q4_K_M"));
            Assert.That((string?)results[0]!["visionName"], Is.EqualTo("hf.co/unsloth/Qwen3.5-4B-GGUF:Q4_K_M"));
            Assert.That((long?)results[0]!["bytes"], Is.EqualTo(2_740_937_888), "the model alone");
            Assert.That((long?)results[0]!["projectorBytes"], Is.EqualTo(670_000_000), "and its vision apart");
            Assert.That((string?)results[0]!["sha256"], Is.EqualTo(Sha("Qwen3.5-4B-Q4_K_M.gguf")));
            Assert.That(results[1]!["visionName"], Is.Null, "a repository with no projector has no vision to add");
            Assert.That((string?)results[0]!["license"], Is.EqualTo("apache-2.0"));
            Assert.That((bool?)results[0]!["tools"], Is.True);
            Assert.That((string?)results[0]!["fit"], Is.EqualTo("cabe"), "7 GB with its f16 cache at 78,000 and its projector, of 8 free");
            Assert.That((long?)results[0]!["vramBytes"] ?? 0, Is.GreaterThan((long?)results[0]!["bytes"] ?? 0));
            Assert.That(results[0]!["why"], Is.Null);
            Assert.That((string?)results[1]!["fit"], Is.EqualTo("desconocido"), "a file whose header was not read says nothing");
            Assert.That((string?)results[1]!["why"], Is.EqualTo("sin_herramientas"), "what BAXY cannot run goes last, and says why");
            Assert.That(online, Has.Count.EqualTo(1));
        });
    }

    [Test]
    public async Task WhatDoesNotFitTheCardOrLacksContextIsSaid()
    {
        var hub = new Hub();
        hub.Pages["/api/models"] = """[{"id":"a/Grande-GGUF"},{"id":"a/Corto-GGUF"}]""";
        hub.Pages["/api/models/a/Grande-GGUF"] = RepositoryOf("llama", "apache-2.0", "tools", 131072, ("g-Q4_K_M.gguf", 9 * Gigabyte));
        hub.Pages["/api/models/a/Corto-GGUF"] = Repository("apache-2.0", "tools", 8192, ("c-Q4_K_M.gguf", 1 * Gigabyte));
        hub.Files["/a/Grande-GGUF/resolve/main/g-Q4_K_M.gguf"] = ModelMemoryTests.Llama32;
        using var models = new OpenModels(_root, hub);

        var results = (JsonArray)(await models.SearchAsync("modelo", 6L << 30, CancellationToken.None))["results"]!;

        Assert.Multiple(() =>
        {
            Assert.That((string?)results[0]!["fit"], Is.EqualTo("no_cabe"));
            Assert.That(results[0]!["why"], Is.Null, "it still runs, more slowly, and the person may choose it");
            Assert.That((string?)results[1]!["why"], Is.EqualTo("poco_contexto"));
        });
    }

    // VIVO2 F13 / ABIERTOS_VIVO D1 (2026-11-09, notebook, 6 GB): a model that declares 40,960 tokens was said «contexto máximo
    // 40.960 tokens, recomendado 52.000 en tu tarjeta», with its VRAM at those 52,000, and «admite muy poco contexto para BAXY»
    // with nothing to install; the same model already in Ollama was offered with the profile that fits it, and connects at what
    // it declares (ExternalModel.WithProfiles, SayVideoMemory with that profile's need). The search says what will happen.
    private static byte[] ShortModel(uint context) => Gguf.Header("llama", tokenEmbedding: null,
        ("block_count", 28u), ("context_length", context), ("embedding_length", 2048u), ("feed_forward_length", 6144u),
        ("attention.head_count", 16u), ("attention.head_count_kv", 8u), ("attention.key_length", 128u), ("attention.value_length", 128u));

    private static (string Profile, int Need)? Lesser(int context) =>
        ToolProfile.LargestFitting(context, null, null) is { } profile ? (profile, ToolProfile.NeededContext(profile, null, null)) : null;

    [Test]
    public async Task AModelShortOfTheChosenProfileIsOfferedWithTheOneThatFitsItAndNeverPastItsOwnContext()
    {
        var hub = new Hub();
        hub.Pages["/api/models"] = """[{"id":"a/Corto-GGUF"},{"id":"a/Minimo-GGUF"},{"id":"a/Largo-GGUF"}]""";
        hub.Pages["/api/models/a/Corto-GGUF"] = RepositoryOf("llama", "apache-2.0", "tools", 40960, ("c-Q4_K_M.gguf", 1_100_000_000));
        hub.Pages["/api/models/a/Minimo-GGUF"] = RepositoryOf("llama", "apache-2.0", "tools", 8192, ("m-Q4_K_M.gguf", 1_100_000_000));
        hub.Pages["/api/models/a/Largo-GGUF"] = RepositoryOf("llama", "apache-2.0", "tools", 131072, ("l-Q4_K_M.gguf", 2_019_377_696));
        hub.Files["/a/Corto-GGUF/resolve/main/c-Q4_K_M.gguf"] = ShortModel(40960);
        hub.Files["/a/Minimo-GGUF/resolve/main/m-Q4_K_M.gguf"] = ShortModel(8192);
        hub.Files["/a/Largo-GGUF/resolve/main/l-Q4_K_M.gguf"] = ModelMemoryTests.Llama32;
        using var models = new OpenModels(_root, hub);
        int complete = ToolProfile.NeededContext(ToolProfile.Completo, null, null);
        int essential = ToolProfile.NeededContext("esencial", null, null);
        var roomy = Task.FromResult<(long?, long?)>((64L << 30, null));

        JsonObject found = await models.SearchAsync("modelo", roomy, CancellationToken.None, complete, Lesser);
        // The same model with the profile that fits it already chosen: what it will connect with once installed.
        JsonObject withEssential = await models.SearchAsync("modelo", roomy, CancellationToken.None, essential, Lesser);

        static JsonNode? Row(JsonObject answer, string repo) => ((JsonArray)answer["results"]!).FirstOrDefault(row => (string?)row!["repo"] == repo);
        JsonNode? shortOne = Row(found, "a/Corto-GGUF");
        JsonNode? least = Row(found, "a/Minimo-GGUF");
        JsonNode? longOne = Row(found, "a/Largo-GGUF");
        JsonNode? chosen = Row(withEssential, "a/Corto-GGUF");
        Assert.Multiple(() =>
        {
            Assert.That(essential, Is.LessThan(40960).And.GreaterThan(8192), "Esencial fits the short model's context, and not the least one's");
            Assert.That((int?)found["needContext"], Is.EqualTo(complete), "what the chosen profile takes, for the view to say");
            Assert.That((string?)shortOne?["profile"], Is.EqualTo("esencial"), "the profile with the most tools that fits what it declares");
            Assert.That(shortOne?["why"], Is.Null, "it can be installed and used, with that profile");
            Assert.That((int?)shortOne?["contexts"]?["native"], Is.EqualTo(40960));
            Assert.That((int?)shortOne?["contexts"]?["recommended"], Is.EqualTo(40960), "its own context, which a roomy card holds: never more than it declares");
            Assert.That((string?)shortOne?["contexts"]?["why"], Is.EqualTo("nativo"));
            Assert.That(shortOne?["contexts"]?["options"]?.AsArray().Select(static option => (int?)option?["tokens"]), Is.All.LessThanOrEqualTo(40960));
            Assert.That((int?)shortOne?["vramContext"], Is.EqualTo(40960));
            Assert.That((long?)shortOne?["vramBytes"], Is.Not.Null.And.EqualTo((long?)chosen?["vramBytes"]), "the VRAM at the context it will run with");
            Assert.That(chosen?["profile"], Is.Null, "with that profile chosen it simply fits");
            Assert.That(chosen?["why"], Is.Null);
            Assert.That((string?)least?["why"], Is.EqualTo("poco_contexto"), "no profile's prompt fits 8,192 tokens");
            Assert.That(least?["profile"], Is.Null);
            Assert.That((int?)least?["contexts"]?["recommended"], Is.EqualTo(8192), "nor is it said to run past what it declares");
            Assert.That(longOne?["profile"], Is.Null, "a model that holds the chosen profile is offered as before");
            Assert.That(longOne?["why"], Is.Null);
            Assert.That((int?)longOne?["contexts"]?["recommended"], Is.EqualTo(131072));
        });
    }

    [Test]
    public async Task AShortModelsFitIsSaidAtTheContextItWillRunWith()
    {
        // A card that holds the model with the smaller profile's prompt, and not with all it declares: the most that fits, said
        // with its VRAM, and never counted at the chosen profile's need, which it will not run with.
        var hub = new Hub();
        hub.Pages["/api/models"] = """[{"id":"a/Corto-GGUF"}]""";
        hub.Pages["/api/models/a/Corto-GGUF"] = RepositoryOf("llama", "apache-2.0", "tools", 40960, ("c-Q4_K_M.gguf", 1_100_000_000));
        hub.Files["/a/Corto-GGUF/resolve/main/c-Q4_K_M.gguf"] = ShortModel(40960);
        using var models = new OpenModels(_root, hub);
        string header = Path.Combine(_root, "corto.gguf");
        File.WriteAllBytes(header, ShortModel(40960));
        GgufShape shape = GgufShape.Read(header)!;
        long At(int tokens) => ModelMemory.GpuBytes(shape, 1_100_000_000, tokens, "f16");
        int complete = ToolProfile.NeededContext(ToolProfile.Completo, null, null);
        int essential = ToolProfile.NeededContext("esencial", null, null);
        // Room for 32,000 tokens of it: more than Esencial's prompt, less than what it declares.
        long card = At(32000);

        JsonObject found = await models.SearchAsync("modelo", Task.FromResult<(long?, long?)>((card, null)), CancellationToken.None, complete, Lesser);

        JsonNode row = ((JsonArray)found["results"]!)[0]!;
        int recommended = (int?)row["contexts"]?["recommended"] ?? 0;
        Assert.Multiple(() =>
        {
            Assert.That(essential, Is.LessThan(32000));
            Assert.That(row["why"], Is.Null);
            Assert.That((string?)row["fit"], Is.EqualTo("cabe"));
            Assert.That((string?)row["contexts"]?["why"], Is.EqualTo("tarjeta"));
            Assert.That(recommended, Is.GreaterThanOrEqualTo(essential).And.LessThan(40960), "the most this card holds, at least the profile's prompt");
            Assert.That((int?)row["vramContext"], Is.EqualTo(recommended));
            Assert.That((long?)row["vramBytes"], Is.EqualTo(At(recommended)).And.LessThanOrEqualTo(card));
        });
    }

    [Test]
    public async Task AFileThatIsNotTheRepositorysModelIsNeverOfferedAsIt()
    {
        // VIVO1 (2026-11-09, notebook, 6 GB): «ggml-org/gpt-oss-20b-GGUF · Q8_0 · 0,9 GB · usa unos 1,9 GB de VRAM · cabe» was
        // the repository's EAGLE-3 draft head (eagle3-gpt-oss-20b-Q8_0.gguf, general.architecture eagle3, 855M), preferred by
        // its quantization over the 12 GB gpt-oss-20b-MXFP4.gguf. Hugging Face reads the repository as gpt-oss.
        var hub = new Hub();
        hub.Pages["/api/models"] = """[{"id":"org/Modelo-GGUF"},{"id":"org/Variantes-GGUF"}]""";
        hub.Pages["/api/models/org/Modelo-GGUF"] = RepositoryOf("llama", "apache-2.0", "tools", 131072,
            ("eagle3-modelo-Q4_K_M.gguf", 900_000_000), ("modelo-Q8_0.gguf", 3_400_000_000));
        // blind review: a repository Hugging Face reads as another architecture than all its files (variants mixed) is
        // still offered, its first file as before
        hub.Pages["/api/models/org/Variantes-GGUF"] = RepositoryOf("qwen3moe", "apache-2.0", "tools", 262144,
            ("variante-Q4_K_M.gguf", 2_700_000_000));
        // the keys of the real eagle3-gpt-oss-20b-Q8_0.gguf (its first MiB, read on 2026-11-09)
        byte[] draft = Gguf.Header("eagle3", tokenEmbedding: null, ("block_count", 1u), ("context_length", 131072u),
            ("embedding_length", 2880u), ("attention.head_count", 64u), ("attention.head_count_kv", 8u));
        hub.Files["/org/Modelo-GGUF/resolve/main/eagle3-modelo-Q4_K_M.gguf"] = draft;
        hub.Files["/org/Modelo-GGUF/resolve/main/modelo-Q8_0.gguf"] = ModelMemoryTests.Llama32;
        hub.Files["/org/Variantes-GGUF/resolve/main/variante-Q4_K_M.gguf"] = ModelMemoryTests.Qwen35;
        using var models = new OpenModels(_root, hub);

        var results = (JsonArray)(await models.SearchAsync("modelo", 6L << 30, CancellationToken.None))["results"]!;

        JsonNode? model = results.FirstOrDefault(row => (string?)row!["repo"] == "org/Modelo-GGUF");
        JsonNode? variants = results.FirstOrDefault(row => (string?)row!["repo"] == "org/Variantes-GGUF");
        Assert.Multiple(() =>
        {
            Assert.That((string?)model?["file"], Is.EqualTo("modelo-Q8_0.gguf"), "the model, not the draft beside it");
            Assert.That((string?)model?["architecture"], Is.EqualTo("llama"));
            Assert.That((long?)model?["bytes"], Is.EqualTo(3_400_000_000));
            Assert.That((string?)variants?["file"], Is.EqualTo("variante-Q4_K_M.gguf"));
            Assert.That((string?)variants?["architecture"], Is.EqualTo("qwen35"), "its header's, read once");
            Assert.That(hub.Ranges, Has.Count.EqualTo(3), "two headers in the first repository, one in the second");
        });
    }

    [Test]
    public async Task EachResultSaysTheVideoMemoryItTakesWithTheDefaultContextAgainstWhatIsFree()
    {
        // Llama-3.2-3B Q4_K_M declares 131,072 tokens, so Ollama runs it at BAXY's default 78,000 with its f16 cache:
        // 8.3 GiB of cache alone. On the notebook's 6 GB card it did not fit: Ollama left 3.8 GB on the GPU and 6.1 GB of
        // cache in RAM (2026-11-08). 2 GB of file is not what decides.
        var hub = new Hub();
        hub.Pages["/api/models"] = """[{"id":"bartowski/Llama-3.2-3B-Instruct-GGUF"}]""";
        hub.Pages["/api/models/bartowski/Llama-3.2-3B-Instruct-GGUF"] = RepositoryOf("llama", "llama3.2", "tools", 131072,
            ("Llama-3.2-3B-Instruct-Q4_K_M.gguf", 2_019_377_696));
        hub.Files["/bartowski/Llama-3.2-3B-Instruct-GGUF/resolve/main/Llama-3.2-3B-Instruct-Q4_K_M.gguf"] = ModelMemoryTests.Llama32;
        using var models = new OpenModels(_root, hub);

        var results = (JsonArray)(await models.SearchAsync("llama 3.2 3b", 6L << 30, CancellationToken.None))["results"]!;

        long vram = (long?)results[0]!["vramBytes"] ?? 0;
        Assert.Multiple(() =>
        {
            Assert.That((string?)results[0]!["fit"], Is.EqualTo("no_cabe"));
            Assert.That((int?)results[0]!["contexts"]!["native"], Is.EqualTo(131072), "its file's own llama.context_length");
            Assert.That((string?)results[0]!["contexts"]!["why"], Is.EqualTo("no_cabe"), "not even BAXY's 52,000 fit 6 GB with an f16 cache");
            Assert.That((int?)results[0]!["vramContext"], Is.EqualTo(52000));
            Assert.That(vram, Is.GreaterThan(6L << 30), "2 GB of weights and 5.6 GiB of f16 cache at 52,000");
            Assert.That(hub.Ranges, Is.Not.Empty.And.All.StartWith("bytes=0-"), "only the file's header is read");
        });
    }

    [Test]
    public async Task TheSearchRecommendsTheContextItWillConnectWithAndSaysWhetherTheCardOrTheRamIsShort()
    {
        // Seen in the real App on the PC (2026-11-09): «cabe en tu tarjeta», 5.7 GB downloaded, then refused for RAM; and the
        // search's context was not the one it connected with. Both go by the same room (ModelMemory.Room: the VRAM free, and what
        // Windows can promise less what the process holds and 3 GiB) and the same recommendation (ExternalModel.SayVideoMemory).
        var hub = new Hub();
        hub.Pages["/api/models"] = """[{"id":"bartowski/Llama-3.2-3B-Instruct-GGUF"}]""";
        hub.Pages["/api/models/bartowski/Llama-3.2-3B-Instruct-GGUF"] = Repository("llama3.2", "tools", 131072,
            ("Llama-3.2-3B-Instruct-Q4_K_M.gguf", 2_019_377_696));
        hub.Files["/bartowski/Llama-3.2-3B-Instruct-GGUF/resolve/main/Llama-3.2-3B-Instruct-Q4_K_M.gguf"] = ModelMemoryTests.Llama32;
        using var models = new OpenModels(_root, hub);
        const long Card = 14L << 30;

        JsonObject roomy = (JsonObject)((JsonArray)(await models.SearchAsync("llama", Task.FromResult<(long?, long?)>((Card, 20L << 30)), CancellationToken.None))["results"]!)[0]!;
        JsonObject tight = (JsonObject)((JsonArray)(await models.SearchAsync("llama", Task.FromResult<(long?, long?)>((Card, 9L << 30)), CancellationToken.None))["results"]!)[0]!;

        string file = Path.Combine(_root, "sha256-llama");
        using (var stream = new FileStream(file, FileMode.Create))
        {
            stream.Write(ModelMemoryTests.Llama32);
            stream.SetLength(2_019_377_696);
        }

        var connecting = new JsonObject
        {
            ["contextLength"] = 131072,
            ["modelFiles"] = new JsonArray(file),
            ["options"] = new JsonArray(new JsonObject { ["context"] = 64000, ["bytes"] = 1L }),
        };
        ExternalModel.SayVideoMemory(connecting, Card, commitFree: 20L << 30);

        Assert.Multiple(() =>
        {
            Assert.That((int?)roomy["vramContext"], Is.EqualTo((int?)connecting["recommended"]), "the context it will connect with");
            Assert.That((string?)roomy["fit"], Is.EqualTo("cabe"));
            Assert.That((string?)tight["fit"], Is.EqualTo("no_cabe_ram"), "the card holds 52,000, what Windows can promise does not");
            Assert.That((long?)tight["ramBytes"], Is.EqualTo((long?)tight["vramBytes"] + ModelMemory.CommitHostBytes + ModelMemory.CommitReserveBytes));
        });
    }

    [Test]
    public async Task AGatedRepositoryIsNotOfferedAndNoNetworkIsSaid()
    {
        var hub = new Hub();
        hub.Pages["/api/models"] = """[{"id":"a/Cerrado-GGUF"}]""";
        hub.Pages["/api/models/a/Cerrado-GGUF"] = Repository("llama3.2", "tools", 131072, ("x-Q4_K_M.gguf", Gigabyte)).Replace("\"gated\":false", "\"gated\":\"manual\"", StringComparison.Ordinal);
        using var models = new OpenModels(_root, hub);

        JsonObject found = await models.SearchAsync("llama", 8L << 30, CancellationToken.None);
        hub.Pages.Clear();
        JsonObject failed = await models.SearchAsync("llama", 8L << 30, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That((JsonArray)found["results"]!, Is.Empty);
            Assert.That((string?)failed["error"], Is.EqualTo("sin_red"));
        });
    }

    [Test]
    public async Task OllamaIsInstalledVerifiedAndThenItIsTheOneBaxyOpens()
    {
        byte[] zip = OllamaZip();
        var hub = new Hub { Bytes = zip };
        using var models = new OpenModels(_root, hub, static _ => long.MaxValue,
            ("https://github.invalid/ollama.zip", new ReleasePart("ollama-windows-amd64.zip", zip.Length, Convert.ToHexStringLower(SHA256.HashData(zip)))));

        bool installed = false;
        models.OllamaInstalled += () => installed = true;
        Assert.That(models.InstallOllama(CancellationToken.None), Is.Null);
        await models.Working!;

        Assert.Multiple(() =>
        {
            Assert.That(installed, Is.True, "an older Ollama BAXY opened goes once its own is here");
            Assert.That(models.OllamaProblem, Is.Null);
            Assert.That(models.OllamaProgram(), Is.EqualTo(models.OwnOllama));
            Assert.That(File.Exists(Path.Combine(Path.GetDirectoryName(models.OwnOllama)!, "lib", "ollama", "ggml-cuda.dll")), Is.True);
            Assert.That(Directory.GetFiles(Path.Combine(_root, "ollama")), Is.Empty, "the zip goes once it is unpacked");
            Assert.That((bool?)models.Json()["ollamaOwn"], Is.True);
        });
    }

    [Test]
    public async Task AnOllamaThatArrivesDamagedIsNotInstalled()
    {
        byte[] zip = OllamaZip();
        var hub = new Hub { Bytes = zip };
        using var models = new OpenModels(_root, hub, static _ => long.MaxValue,
            ("https://github.invalid/ollama.zip", new ReleasePart("ollama-windows-amd64.zip", zip.Length, new string('0', 64))));

        Assert.That(models.InstallOllama(CancellationToken.None), Is.Null);
        await models.Working!;

        Assert.Multiple(() =>
        {
            Assert.That(models.OllamaProblem, Is.EqualTo("danado"));
            Assert.That(File.Exists(models.OwnOllama), Is.False);
        });
    }

    [Test]
    public void WithoutRoomOllamaIsNotDownloaded()
    {
        using var models = new OpenModels(_root, new Hub(), static _ => Gigabyte);

        Assert.Multiple(() =>
        {
            Assert.That(models.InstallOllama(CancellationToken.None), Is.EqualTo("open_models_no_space"));
            Assert.That(models.OllamaProblem, Is.EqualTo("sin_espacio"));
        });
    }

    [Test]
    public async Task OllamaDownloadsTheModelWithItsProgressAndThenItIsConnected()
    {
        using var ollama = new FakeOllama(
            """{"status":"pulling manifest"}""",
            """{"status":"pulling sha256:aa","digest":"sha256:aa","total":100,"completed":40}""",
            """{"status":"pulling sha256:aa","digest":"sha256:aa","total":100,"completed":100}""",
            """{"status":"success"}""");
        using var models = new OpenModels(_root, new Hub());
        string? pulled = null;
        models.Pulled += name => pulled = name;

        Assert.That(models.Pull("no es un nombre", static _ => Task.FromResult(true), CancellationToken.None), Is.EqualTo("open_models_invalid_name"));
        Assert.That(models.Pull("hf.co/unsloth/Qwen3.5-4B-GGUF:Q4_K_M", static _ => Task.FromResult(true), CancellationToken.None), Is.Null);
        await models.Working!;

        Assert.Multiple(() =>
        {
            Assert.That(pulled, Is.EqualTo("hf.co/unsloth/Qwen3.5-4B-GGUF:Q4_K_M"));
            Assert.That(ollama.Bodies.Single(), Does.Contain("\"model\":\"hf.co/unsloth/Qwen3.5-4B-GGUF:Q4_K_M\""));
            Assert.That((long?)models.Json()["pullDone"], Is.EqualTo(100));
            Assert.That(models.PullProblem, Is.Null);
        });
    }

    [Test]
    public async Task TheProgressIsEveryLayerOllamaDownloadsSoItNeverGoesBack()
    {
        // Encargo del dueño 2026-11-08: «un porcentaje de descarga que se vea bonito». Ollama tells each layer apart (the model,
        // then its projector): its last line alone would go from 100 of 100 back to 20 of 50.
        using var ollama = new FakeOllama(
            """{"status":"pulling sha256:aa","digest":"sha256:aa","total":100,"completed":100}""",
            """{"status":"pulling sha256:bb","digest":"sha256:bb","total":50,"completed":20}""",
            """{"status":"pulling sha256:aa","digest":"sha256:aa","total":100,"completed":100}""",
            """{"status":"pulling sha256:bb","digest":"sha256:bb","total":50,"completed":50}""",
            """{"status":"success"}""");
        using var models = new OpenModels(_root, new Hub());

        Assert.That(models.Pull("hf.co/a/b:Q4_K_M", static _ => Task.FromResult(true), CancellationToken.None, expectedBytes: 140), Is.Null);
        JsonObject first = models.Json();
        await models.Working!;
        JsonObject done = models.Json();

        Assert.Multiple(() =>
        {
            Assert.That((long?)first["pullTotal"], Is.EqualTo(140), "before Ollama says its layers, the size the search gave");
            Assert.That((long?)done["pullTotal"], Is.EqualTo(150));
            Assert.That((long?)done["pullDone"], Is.EqualTo(150));
        });
    }

    [Test]
    public void TheSpeedAndTimeLeftComeFromTheLastSecondsOfTheDownload()
    {
        var at = new DateTimeOffset(2026, 11, 8, 23, 0, 0, TimeSpan.Zero);
        var rate = new DownloadRate(() => at);
        rate.Saw(0);
        Assert.That(rate.BytesPerSecond, Is.Null, "one sample is no speed");
        at += TimeSpan.FromSeconds(2);
        rate.Saw(20_000_000);
        Assert.Multiple(() =>
        {
            Assert.That(rate.BytesPerSecond, Is.EqualTo(10_000_000));
            Assert.That(rate.SecondsLeft(100_000_000), Is.EqualTo(8));
        });
        at += TimeSpan.FromSeconds(20);
        rate.Saw(20_000_000);
        Assert.That(rate.BytesPerSecond, Is.EqualTo(0), "stalled: the samples of the last seconds moved nothing");
        Assert.That(rate.SecondsLeft(100_000_000), Is.Null, "with no speed no time is said");
    }

    [Test]
    public void TheTimeLeftDoesNotSwingWithEachBurstOfTheDownload()
    {
        // Seen in the real App (2026-11-09, Qwen3.5-9B, 5.68 GB): with the speed of the last 5 s the time left went 4 → 3 → 2 →
        // 3 → 3 → 2 min as the speed swung 23-73 MB/s. Those speeds, one per second, read every second once it settled.
        double[] speeds = [23.3, 36.3, 47.3, 30.3, 32, 72.8, 53.7, 35.4, 40.8, 50.9, 23.3, 36.3, 47.3, 30.3, 32, 72.8, 53.7, 35.4, 40.8, 50.9];
        var at = new DateTimeOffset(2026, 11, 9, 2, 0, 0, TimeSpan.Zero);
        var rate = new DownloadRate(() => at);
        long done = 0;
        rate.Saw(done);
        var left = new List<long>();
        foreach (double speed in speeds)
        {
            at += TimeSpan.FromSeconds(1);
            done += (long)(speed * 1e6);
            rate.Saw(done);
            if (rate.SecondsLeft(5_680_000_000) is { } seconds)
            {
                left.Add(seconds);
            }
        }

        // Past its first 10 s, a reading never moves more than 10 % from the one before.
        var settled = left.Skip(10).ToList();
        Assert.That(settled.Zip(settled.Skip(1), static (a, b) => Math.Abs(b - a) / (double)a).Max(), Is.LessThanOrEqualTo(0.10));
    }

    [Test]
    public async Task AStoppedDownloadSaysWhatCanGoOnFrom()
    {
        using var ollama = new FakeOllama("""{"status":"pulling sha256:aa","digest":"sha256:aa","total":100,"completed":40}""");
        using var models = new OpenModels(_root, new Hub());

        Assert.That(models.Pull("hf.co/a/b:Q4_K_M", static _ => Task.FromResult(true), CancellationToken.None, expectedBytes: 100), Is.Null);
        await models.Working!;
        JsonObject cut = models.Json();

        Assert.Multiple(() =>
        {
            Assert.That((string?)cut["pullStopped"], Is.EqualTo("hf.co/a/b:Q4_K_M"), "a cut is one to go on with");
            Assert.That((long?)cut["pullDone"], Is.EqualTo(40));
            Assert.That((string?)cut["pullProblem"], Is.EqualTo("cortado"));
        });
    }

    [Test]
    public async Task AModelOllamaCannotDownloadIsSaidAndNothingIsConnected()
    {
        using var ollama = new FakeOllama("""{"status":"pulling manifest"}""", """{"error":"pull model manifest: file does not exist: not found"}""");
        using var models = new OpenModels(_root, new Hub());
        string? pulled = null;
        models.Pulled += name => pulled = name;

        Assert.That(models.Pull("hf.co/a/b:Q4_K_M", static _ => Task.FromResult(true), CancellationToken.None), Is.Null);
        await models.Working!;
        Assert.That(models.Pull("hf.co/a/b:Q4_K_M", static _ => Task.FromResult(false), CancellationToken.None), Is.Null);
        string? first = models.PullProblem;
        await models.Working!;

        Assert.Multiple(() =>
        {
            Assert.That(first, Is.Null, "a new download clears the last one's failure");
            Assert.That(pulled, Is.Null);
            Assert.That(models.PullProblem, Is.EqualTo("sin_ollama"));
        });
    }

    private static string Repository(string license, string template, int context, params (string Name, long Bytes)[] files) =>
        RepositoryOf("qwen35", license, template, context, files);

    private static string RepositoryOf(string architecture, string license, string template, int context, params (string Name, long Bytes)[] files)
    {
        var siblings = new JsonArray();
        foreach ((string name, long bytes) in files)
        {
            siblings.Add(new JsonObject { ["rfilename"] = name, ["size"] = bytes, ["lfs"] = new JsonObject { ["sha256"] = Sha(name), ["size"] = bytes } });
        }

        return new JsonObject
        {
            ["gated"] = false,
            ["cardData"] = new JsonObject { ["license"] = license },
            ["gguf"] = new JsonObject { ["chat_template"] = template, ["context_length"] = context, ["architecture"] = architecture },
            ["siblings"] = siblings,
        }.ToJsonString();
    }

    private static string Sha(string name) => Convert.ToHexStringLower(SHA256.HashData(Encoding.UTF8.GetBytes(name)));

    [Test]
    public async Task TheModelAloneIsInstalledFromItsFileWithNoProjectorAndThenItIsConnected()
    {
        byte[] gguf = Encoding.ASCII.GetBytes(string.Concat(Enumerable.Repeat("GGUF modelo. ", 20000)));
        string sha = Convert.ToHexStringLower(SHA256.HashData(gguf));
        var hub = new Hub { Bytes = gguf };
        using var ollama = new FilesOllama(hasBlob: false);
        using var models = new OpenModels(_root, hub, static _ => long.MaxValue);
        string? pulled = null;
        models.Pulled += name => pulled = name;

        Assert.That(models.Install("unsloth/Qwen3.5-2B-GGUF", "Qwen3.5-2B-Q4_K_M.gguf", sha, gguf.Length, "Q4_K_M",
            static _ => Task.FromResult(true), CancellationToken.None), Is.Null);
        await models.Working!;

        Assert.Multiple(() =>
        {
            Assert.That(models.PullProblem, Is.Null);
            Assert.That(pulled, Is.EqualTo("unsloth/Qwen3.5-2B-GGUF:Q4_K_M"));
            Assert.That(hub.Asked.Single(), Is.EqualTo("https://huggingface.co/unsloth/Qwen3.5-2B-GGUF/resolve/main/Qwen3.5-2B-Q4_K_M.gguf"));
            Assert.That(ollama.Pushed, Is.EqualTo(gguf), "Ollama gets the file the Hub's SHA-256 names");
            Assert.That(ollama.Paths, Does.Contain("POST /api/blobs/sha256:" + sha));
            Assert.That(ollama.Created.Single(), Does.Contain("\"model\":\"unsloth/Qwen3.5-2B-GGUF:Q4_K_M\"")
                .And.Contain("\"files\":{\"Qwen3.5-2B-Q4_K_M.gguf\":\"sha256:" + sha + "\"}"), "the model alone: no projector");
            Assert.That(Directory.GetFiles(Path.Combine(_root, "ollama", "descargas")), Is.Empty, "Ollama keeps its own copy");
            Assert.That((long?)models.Json()["pullDone"], Is.EqualTo(gguf.Length));
        });
    }

    [Test]
    public async Task AFileOllamaAlreadyHoldsIsNotDownloadedAgain()
    {
        var hub = new Hub();
        using var ollama = new FilesOllama(hasBlob: true);
        using var models = new OpenModels(_root, hub, static _ => long.MaxValue);
        string? pulled = null;
        models.Pulled += name => pulled = name;

        Assert.That(models.Install("a/Modelo-GGUF", "m-Q4_K_M.gguf", new string('a', 64), 1000, "Q4_K_M",
            static _ => Task.FromResult(true), CancellationToken.None), Is.Null);
        await models.Working!;

        Assert.Multiple(() =>
        {
            Assert.That(hub.Asked, Is.Empty);
            Assert.That(ollama.Pushed, Is.Null);
            Assert.That(pulled, Is.EqualTo("a/Modelo-GGUF:Q4_K_M"));
        });
    }

    [Test]
    public async Task AModelFileThatArrivesDamagedIsNotInstalled()
    {
        var hub = new Hub { Bytes = Encoding.ASCII.GetBytes(string.Concat(Enumerable.Repeat("otra cosa ", 3000))) };
        using var ollama = new FilesOllama(hasBlob: false);
        using var models = new OpenModels(_root, hub, static _ => long.MaxValue);

        Assert.That(models.Install("a/Modelo-GGUF", "m-Q4_K_M.gguf", new string('b', 64), 30000, "Q4_K_M",
            static _ => Task.FromResult(true), CancellationToken.None), Is.Null);
        await models.Working!;

        Assert.Multiple(() =>
        {
            Assert.That(models.PullProblem, Is.EqualTo("danado"));
            Assert.That(ollama.Created, Is.Empty);
        });
    }

    // REV_APP DL-b (2026-11-09): a model's download that stalled (PartFetcher cuts each try at its stall limit and gives up
    // after its tries) ended InstallAsync with an exception nobody caught: the bar went away and nothing said why. Ollama's own
    // download and the tuned model's did say it.
    [Test]
    public async Task AModelDownloadThatStallsIsSaidAsCutAndNotDroppedInSilence()
    {
        var hub = new Hub { Stalls = true };
        using var ollama = new FilesOllama(hasBlob: false);
        using var models = new OpenModels(_root, hub, static _ => long.MaxValue, retryDelay: TimeSpan.Zero);

        Assert.That(models.Install("a/Modelo-GGUF", "m-Q4_K_M.gguf", new string('b', 64), 30000, "Q4_K_M",
            static _ => Task.FromResult(true), CancellationToken.None), Is.Null);
        Assert.DoesNotThrowAsync(async () => await models.Working!);

        Assert.Multiple(() =>
        {
            Assert.That(models.PullProblem, Is.EqualTo("cortado"));
            Assert.That((string?)models.Json()["pullProblem"], Is.EqualTo("cortado"));
            Assert.That(ollama.Created, Is.Empty);
        });
    }

    // REV_APP DL-c (2026-11-09): a failure of the disk that is not «full» (a file another program holds, a device error) was
    // said as the network's: «No logré conectarme» for Ollama's zip, «La descarga se cortó» for a model. PartFetcher already
    // turns a line that drops into an HttpRequestException, so an IOException that leaves it is the disk's.
    [Test]
    public async Task AFailureOfTheDiskIsNotSaidAsTheNetworks()
    {
        byte[] zip = OllamaZip();
        var hub = new Hub { Bytes = zip };
        using var ollama = new FilesOllama(hasBlob: false);
        using var models = new OpenModels(_root, hub, static _ => long.MaxValue,
            ("https://github.invalid/ollama.zip", new ReleasePart("ollama-windows-amd64.zip", zip.Length, Convert.ToHexStringLower(SHA256.HashData(zip)))),
            retryDelay: TimeSpan.Zero);
        Directory.CreateDirectory(Path.Combine(_root, "ollama", "descargas"));
        using (new FileStream(Path.Combine(_root, "ollama", "ollama-windows-amd64.zip.part"), FileMode.Create, FileAccess.Write, FileShare.None))
        {
            Assert.That(models.InstallOllama(CancellationToken.None), Is.Null);
            await models.Working!;
        }

        Assert.That(models.OllamaProblem, Is.EqualTo("sin_disco"));

        using (new FileStream(Path.Combine(_root, "ollama", "descargas", "m-Q4_K_M.gguf.part"), FileMode.Create, FileAccess.Write, FileShare.None))
        {
            Assert.That(models.Install("a/Modelo-GGUF", "m-Q4_K_M.gguf", Convert.ToHexStringLower(SHA256.HashData(zip)), zip.Length, "Q4_K_M",
                static _ => Task.FromResult(true), CancellationToken.None), Is.Null);
            await models.Working!;
        }

        Assert.That(models.PullProblem, Is.EqualTo("sin_disco"));

        // control: with the disk free again, the same two requests end well
        Assert.That(models.InstallOllama(CancellationToken.None), Is.Null);
        await models.Working!;
        Assert.That(models.OllamaProblem, Is.Null);
        Assert.That(models.Install("a/Modelo-GGUF", "m-Q4_K_M.gguf", Convert.ToHexStringLower(SHA256.HashData(zip)), zip.Length, "Q4_K_M",
            static _ => Task.FromResult(true), CancellationToken.None), Is.Null);
        await models.Working!;
        Assert.That(models.PullProblem, Is.Null);
    }

    // REV_APP SRCH-a (2026-11-09): one repository Hugging Face refused (deleted or made private since it was listed) failed the
    // whole search as «sin red». It is left out; a line that is down, or Hugging Face asking to wait, still is the search's.
    [Test]
    public async Task ARepositoryHuggingFaceRefusesIsLeftOutAndTheOthersAreStillSaid()
    {
        var hub = new Hub();
        hub.Pages["/api/models"] = """[{"id":"a/Retirado-GGUF"},{"id":"unsloth/Qwen3.5-4B-GGUF"}]""";
        hub.Pages["/api/models/unsloth/Qwen3.5-4B-GGUF"] = Repository(
            "apache-2.0", "{% if tools %}{{ tools }}{% endif %}", 262144, ("Qwen3.5-4B-Q4_K_M.gguf", 2_740_937_888));
        hub.Files["/unsloth/Qwen3.5-4B-GGUF/resolve/main/Qwen3.5-4B-Q4_K_M.gguf"] = ModelMemoryTests.Qwen35;
        using var models = new OpenModels(_root, hub);

        // «a/Retirado-GGUF» has no page here: 404, as Hugging Face answers for a repository that is gone
        JsonObject found = await models.SearchAsync("qwen", 8L << 30, CancellationToken.None);
        hub.Statuses["/api/models/a/Retirado-GGUF"] = HttpStatusCode.TooManyRequests;
        JsonObject wait = await models.SearchAsync("qwen", 8L << 30, CancellationToken.None);
        hub.Statuses.Clear();
        hub.Down.Add("/api/models/a/Retirado-GGUF");
        JsonObject down = await models.SearchAsync("qwen", 8L << 30, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(found["error"], Is.Null);
            Assert.That(((JsonArray?)found["results"])?.Select(static row => (string?)row!["repo"]), Is.EqualTo(new[] { "unsloth/Qwen3.5-4B-GGUF" }));
            Assert.That((string?)wait["error"], Is.EqualTo("limite"), "asked to wait: the whole search waits");
            Assert.That((string?)down["error"], Is.EqualTo("sin_red"), "no answer at all is the line, not that repository");
        });
    }

    // REV_APP DL-a (2026-11-09): a stall showed only when a sample came, and a download that stopped dead sends none: the speed
    // and the time left stayed as they were until the download was cut (60 s). Read against the clock.
    [Test]
    public void ADownloadThatStoppedDeadSaysNoSpeedThoughNoSampleComes()
    {
        var at = new DateTimeOffset(2026, 11, 9, 23, 0, 0, TimeSpan.Zero);
        var rate = new DownloadRate(() => at);
        rate.Saw(0);
        at += TimeSpan.FromSeconds(2);
        rate.Saw(20_000_000);
        at += TimeSpan.FromSeconds(4);
        Assert.That((rate.BytesPerSecond, rate.SecondsLeft(100_000_000)), Is.EqualTo((10_000_000L, 8L)), "under the stall: as it was");

        at += TimeSpan.FromSeconds(2);

        Assert.Multiple(() =>
        {
            Assert.That(rate.BytesPerSecond, Is.EqualTo(0));
            Assert.That(rate.SecondsLeft(100_000_000), Is.Null);
        });
    }

    [Test]
    public async Task AModelIsRemovedFromOllamaButNeverTheOneInUse()
    {
        // Interfaz v5 2026-11-08: uninstalling a model from Settings. Ollama's own removal (docs/api.md, «Delete a Model»).
        using var ollama = new FilesOllama(hasBlob: true);
        using var models = new OpenModels(_root, new Hub());

        string? inUse = await models.RemoveAsync("hf.co/a/b:Q4_K_M", "hf.co/a/b:Q4_K_M", static _ => Task.FromResult(true), CancellationToken.None);
        string? removed = await models.RemoveAsync("a/b:Q4_K_M", "hf.co/a/b:Q4_K_M", static _ => Task.FromResult(true), CancellationToken.None);
        string? invalid = await models.RemoveAsync("no es; un nombre", null, static _ => Task.FromResult(true), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(inUse, Is.EqualTo("open_models_in_use"));
            Assert.That(removed, Is.Null);
            Assert.That(invalid, Is.EqualTo("open_models_invalid_name"));
            Assert.That(ollama.Paths.Count(path => path == "DELETE /api/delete"), Is.EqualTo(1));
            Assert.That(ollama.Deleted.Single(), Does.Contain("\"model\":\"a/b:Q4_K_M\""));
        });
    }

    /// <summary>Ollama's blobs and create (docs/api.md), on this PC.</summary>
    private sealed class FilesOllama : IDisposable
    {
        private readonly HttpListener _listener = new();

        internal FilesOllama(bool hasBlob)
        {
            using var probe = new TcpListener(IPAddress.Loopback, 0);
            probe.Start();
            int port = ((IPEndPoint)probe.LocalEndpoint).Port;
            probe.Stop();
            _listener.Prefixes.Add($"http://localhost:{port}/");
            _listener.Start();
            Environment.SetEnvironmentVariable("OLLAMA_HOST", $"http://localhost:{port}");
            _ = Task.Run(async () =>
            {
                while (_listener.IsListening)
                {
                    HttpListenerContext context;
                    try
                    {
                        context = await _listener.GetContextAsync();
                    }
                    catch (Exception exception) when (exception is HttpListenerException or ObjectDisposedException)
                    {
                        return;
                    }

                    string path = context.Request.Url!.AbsolutePath;
                    Paths.Add($"{context.Request.HttpMethod} {path}");
                    using var memory = new MemoryStream();
                    await context.Request.InputStream.CopyToAsync(memory);
                    byte[] reply = [];
                    if (context.Request.HttpMethod == "HEAD")
                    {
                        context.Response.StatusCode = hasBlob ? 200 : 404;
                    }
                    else if (path.StartsWith("/api/blobs/", StringComparison.Ordinal))
                    {
                        Pushed = memory.ToArray();
                        context.Response.StatusCode = 201;
                    }
                    else if (path == "/api/delete")
                    {
                        Deleted.Add(Encoding.UTF8.GetString(memory.ToArray()));
                    }
                    else if (path == "/api/create")
                    {
                        Created.Add(Encoding.UTF8.GetString(memory.ToArray()));
                        reply = Encoding.UTF8.GetBytes("""{"status":"success"}""");
                    }

                    await context.Response.OutputStream.WriteAsync(reply);
                    context.Response.Close();
                }
            });
        }

        internal List<string> Paths { get; } = [];

        internal List<string> Created { get; } = [];

        internal List<string> Deleted { get; } = [];

        internal byte[]? Pushed { get; private set; }

        public void Dispose()
        {
            _listener.Stop();
            _listener.Close();
        }
    }

    private static byte[] OllamaZip()
    {
        using var memory = new MemoryStream();
        using (var archive = new ZipArchive(memory, ZipArchiveMode.Create, leaveOpen: true))
        {
            foreach (string name in new[] { "ollama.exe", "lib/ollama/ggml-cuda.dll" })
            {
                using Stream entry = archive.CreateEntry(name).Open();
                entry.Write(Encoding.ASCII.GetBytes(string.Concat(Enumerable.Repeat(name, 5000))));
            }
        }

        return memory.ToArray();
    }

    /// <summary>Hugging Face's API and GitHub's download: a page per path, or the zip's bytes for any other.</summary>
    private sealed class Hub : HttpMessageHandler
    {
        internal Dictionary<string, string> Pages { get; } = [];

        // A model file's first bytes, served from a range as Hugging Face's resolve does (206).
        internal Dictionary<string, byte[]> Files { get; } = [];

        internal List<string> Asked { get; } = [];

        internal List<string> Ranges { get; } = [];

        internal byte[]? Bytes { get; init; }

        // A path answered with this status, a path whose request never gets an answer (the line is down), and every request
        // ending as one cut for stalling does (a cancellation nobody asked for).
        internal Dictionary<string, HttpStatusCode> Statuses { get; } = [];

        internal HashSet<string> Down { get; } = [];

        internal bool Stalls { get; init; }

        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        {
            Asked.Add(request.RequestUri!.AbsoluteUri);
            if (Stalls)
            {
                throw new TaskCanceledException("stalled");
            }

            if (Down.Contains(request.RequestUri.AbsolutePath))
            {
                throw new HttpRequestException("no route to host");
            }

            if (Statuses.TryGetValue(request.RequestUri.AbsolutePath, out HttpStatusCode status))
            {
                return Task.FromResult(new HttpResponseMessage(status));
            }

            if (Pages.TryGetValue(request.RequestUri.AbsolutePath, out string? page))
            {
                return Task.FromResult(new HttpResponseMessage(HttpStatusCode.OK) { Content = new StringContent(page) });
            }

            if (Files.TryGetValue(request.RequestUri.AbsolutePath, out byte[]? file))
            {
                Ranges.Add(request.Headers.Range?.ToString() ?? string.Empty);
                return Task.FromResult(new HttpResponseMessage(HttpStatusCode.PartialContent) { Content = new ByteArrayContent(file) });
            }

            return Task.FromResult(Bytes is null
                ? new HttpResponseMessage(HttpStatusCode.NotFound)
                : new HttpResponseMessage(HttpStatusCode.OK) { Content = new ByteArrayContent(Bytes) });
        }
    }

    /// <summary>Ollama's /api/pull on this PC, streaming its lines as it does.</summary>
    private sealed class FakeOllama : IDisposable
    {
        private readonly HttpListener _listener = new();

        internal FakeOllama(params string[] lines)
        {
            using var probe = new TcpListener(IPAddress.Loopback, 0);
            probe.Start();
            int port = ((IPEndPoint)probe.LocalEndpoint).Port;
            probe.Stop();
            _listener.Prefixes.Add($"http://localhost:{port}/");
            _listener.Start();
            Environment.SetEnvironmentVariable("OLLAMA_HOST", $"http://localhost:{port}");
            _ = Task.Run(async () =>
            {
                while (_listener.IsListening)
                {
                    HttpListenerContext context;
                    try
                    {
                        context = await _listener.GetContextAsync();
                    }
                    catch (Exception exception) when (exception is HttpListenerException or ObjectDisposedException)
                    {
                        return;
                    }

                    using (var reader = new StreamReader(context.Request.InputStream))
                    {
                        Bodies.Add(await reader.ReadToEndAsync());
                    }

                    byte[] data = Encoding.UTF8.GetBytes(string.Join('\n', lines) + "\n");
                    context.Response.ContentType = "application/x-ndjson";
                    await context.Response.OutputStream.WriteAsync(data);
                    context.Response.Close();
                }
            });
        }

        internal List<string> Bodies { get; } = [];

        public void Dispose()
        {
            _listener.Stop();
            _listener.Close();
        }
    }
}
