using System.IO;
using System.Text.Json.Nodes;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// Settings → Model → Context (owner's order of 2026-11-08): BAXY's own model, stock or tuned, runs with the context the
/// person picks from fixed presets, each with the video memory measured for it and the room it leaves beside the prompt
/// prefix; «Automático» gives the mind nothing, as before the setting existed.
/// </summary>
[TestFixture]
[NonParallelizable]
public sealed class LocalContextTests
{
    private const long Mib = 1L << 20;
    private string _root = "";
    private string? _before;

    [SetUp]
    public void SetUp()
    {
        _root = Directory.CreateTempSubdirectory("baxy-context-").FullName;
        _before = Environment.GetEnvironmentVariable(LocalContext.Variable);
        Environment.SetEnvironmentVariable(LocalContext.Variable, null);
    }

    [TearDown]
    public void TearDown()
    {
        Environment.SetEnvironmentVariable(LocalContext.Variable, _before);
        Directory.Delete(_root, recursive: true);
    }

    private static JsonObject Option(JsonObject view, int context) =>
        view["options"]!.AsArray().Single(option => (int?)option!["context"] == context)!.AsObject();

    [TestCase(null)]
    [TestCase("40960")]
    public void AutomaticGivesTheMindNothingOfItsOwn(string? inherited)
    {
        Environment.SetEnvironmentVariable(LocalContext.Variable, inherited);
        var context = new LocalContext(_root);
        context.ApplyEnvironment();
        Assert.Multiple(() =>
        {
            Assert.That(context.Chosen(), Is.Null);
            Assert.That(Environment.GetEnvironmentVariable(LocalContext.Variable), Is.EqualTo(inherited));
            Assert.That(File.Exists(Path.Combine(_root, LocalContext.FileName)), Is.False);
        });
    }

    [Test]
    public void AChosenPresetGoesToTheMindAndAutomaticPutsBackWhatWasThere()
    {
        var context = new LocalContext(_root);
        context.ApplyEnvironment();
        Assert.That(context.Apply(new JsonObject { ["context"] = 98304 }, prefixTokens: null), Is.Null);
        // Kept for the next start of BAXY too.
        Assert.That(new LocalContext(_root).Chosen(), Is.EqualTo(98304));
        context.ApplyEnvironment();
        Assert.That(Environment.GetEnvironmentVariable(LocalContext.Variable), Is.EqualTo("98304"));
        Assert.That(context.Apply(new JsonObject { ["context"] = null }, prefixTokens: null), Is.Null);
        context.ApplyEnvironment();
        Assert.Multiple(() =>
        {
            Assert.That(Environment.GetEnvironmentVariable(LocalContext.Variable), Is.Null);
            Assert.That(File.Exists(Path.Combine(_root, LocalContext.FileName)), Is.False);
        });
    }

    [Test]
    public void OnlyAPresetIsKept()
    {
        var context = new LocalContext(_root);
        Assert.That(context.Apply(new JsonObject { ["context"] = 65536 }, prefixTokens: null), Is.Null);
        Assert.Multiple(() =>
        {
            Assert.That(context.Apply(new JsonObject { ["context"] = 70000 }, prefixTokens: null), Is.EqualTo("local_context_invalid"));
            Assert.That(context.Apply(new JsonObject { ["context"] = "mucho" }, prefixTokens: null), Is.EqualTo("local_context_invalid"));
            Assert.That(context.Apply(new JsonObject(), prefixTokens: null), Is.EqualTo("local_context_invalid"));
            Assert.That(context.Chosen(), Is.EqualTo(65536));
        });
    }

    [Test]
    public void AContextWithNoRoomForThePrefixAndTheTurnIsRefusedAndShownOff()
    {
        // The full catalog's prefix measured 49,086 tokens; the mind keeps TURN_ROOM_TOKENS for the turn (mind.py).
        var context = new LocalContext(_root);
        Assert.That(LocalContext.MinimumContext(49086), Is.EqualTo(49086 + 3584));
        Assert.That(context.Apply(new JsonObject { ["context"] = 45056 }, prefixTokens: 49086), Is.EqualTo("local_context_too_small"));
        Assert.That(context.Chosen(), Is.Null);
        JsonObject view = context.Json(prefixTokens: 49086, backend: "cuda", switching: false);
        Assert.Multiple(() =>
        {
            Assert.That((int?)view["minimum"], Is.EqualTo(52670));
            Assert.That((bool?)Option(view, 45056)["fits"], Is.False);
            Assert.That(Option(view, 45056)["room"], Is.Null);
            Assert.That((bool?)Option(view, 53248)["fits"], Is.True);
            Assert.That((int?)Option(view, 53248)["room"], Is.EqualTo(53248 - 49086 - 3584));
        });
        // A smaller prefix (fewer tools) leaves room in the smallest preset.
        JsonObject small = context.Json(prefixTokens: 14967, backend: "cuda", switching: false);
        Assert.That((int?)Option(small, 32768)["room"], Is.EqualTo(32768 - 14967 - 3584));
        Assert.That(context.Apply(new JsonObject { ["context"] = 32768 }, prefixTokens: 14967), Is.Null);
    }

    [Test]
    public void WithThePrefixNotYetKnownOnlyAContextEveryProfileFitsIsOffered()
    {
        // Perfiles de herramientas: before a mind told its prefix, the floor is the one the full catalog fits (49,086 +
        // 3,584 = 52,670 ≤ 53,248), so no choice made then leaves a mind that cannot start.
        var context = new LocalContext(_root);
        JsonObject view = context.Json(prefixTokens: null, backend: null, switching: false);
        Assert.Multiple(() =>
        {
            Assert.That(view["minimum"], Is.Null);
            Assert.That(view["automatic"], Is.Null);
            Assert.That(view["options"]!.AsArray().All(option => option!["room"] is null), Is.True);
            Assert.That((bool?)Option(view, 45056)["fits"], Is.False);
            Assert.That((bool?)Option(view, LocalContext.FitsEveryProfile)["fits"], Is.True);
            Assert.That(context.Apply(new JsonObject { ["context"] = 45056 }, prefixTokens: null), Is.EqualTo("local_context_too_small"));
            Assert.That(context.Apply(new JsonObject { ["context"] = 53248 }, prefixTokens: null), Is.Null);
        });
    }

    [Test]
    public void AnotherToolProfileTakesASmallContextBackToAutomatic()
    {
        // A context chosen for a short prefix (Esencial) may not fit the next profile's: it goes back to «Automático».
        var context = new LocalContext(_root);
        Assert.That(context.Apply(new JsonObject { ["context"] = 32768 }, prefixTokens: 14967), Is.Null);
        Assert.That(context.KeepForEveryProfile(), Is.True);
        Assert.That(context.Chosen(), Is.Null);
        Assert.That(context.Apply(new JsonObject { ["context"] = 65536 }, prefixTokens: 14967), Is.Null);
        Assert.That(context.KeepForEveryProfile(), Is.False);
        Assert.That(context.Chosen(), Is.EqualTo(65536));
    }

    [Test]
    public void WithoutTheModelsFileNoVideoMemoryIsSaidAndVulkanPastItsCacheIsSlower()
    {
        // The figure comes from the model's header (ModelMemory): with no file there is none to give, rather than another
        // model's. A q8_0 cache past 1 GiB on an RX 7600 (62,464 cells or more) ran ~4 times slower (INFORME_60).
        string? model = Environment.GetEnvironmentVariable("BAXY_MIND_LLM_GGUF");
        Environment.SetEnvironmentVariable("BAXY_MIND_LLM_GGUF", null);
        try
        {
            var context = new LocalContext(_root);
            JsonObject cuda = context.Json(prefixTokens: 49086, backend: "cuda", switching: false);
            JsonObject vulkan = context.Json(prefixTokens: 49086, backend: "vulkan", switching: false);
            Assert.Multiple(() =>
            {
                Assert.That(Option(cuda, 77824)["vramBytes"], Is.Null);
                Assert.That((long?)cuda["cardBytes"], Is.EqualTo(4096 * Mib), "the 4 GB budget while the card is not known");
                Assert.That((bool?)cuda["cardKnown"], Is.False);
                Assert.That((bool?)Option(cuda, 131072)["slower"], Is.False);
                Assert.That((bool?)Option(vulkan, 61440)["slower"], Is.False);
                Assert.That((bool?)Option(vulkan, 65536)["slower"], Is.True);
            });
        }
        finally
        {
            Environment.SetEnvironmentVariable("BAXY_MIND_LLM_GGUF", model);
        }
    }

    // REV_APP VRAM-b (2026-11-09): until a mind said its backend, every figure was NVIDIA's, also on an AMD or Intel card, where
    // the same context takes more (three slots on Vulkan, the output matrix on the card): a figure under what it takes, shown
    // beside «igual o mayor que lo medido». No figure is said until the backend is known; the App knows it before any mind
    // where its start chose the server by the card (BAXY_MIND_LLAMA_BACKEND, MindRuntimeDiscovery).
    [Test]
    public async Task UntilTheBackendIsKnownNoVideoMemoryIsSaidRatherThanNvidias()
    {
        string stock = Path.Combine(_root, "de-serie.gguf");
        using (var file = new FileStream(stock, FileMode.Create))
        {
            file.Write(ModelMemoryTests.Qwen35);
            file.SetLength(ModelMemoryTests.QwenFile);
        }

        string? model = Environment.GetEnvironmentVariable("BAXY_MIND_LLM_GGUF");
        string? vision = Environment.GetEnvironmentVariable("BAXY_MIND_MMPROJ");
        string? chosen = Environment.GetEnvironmentVariable("BAXY_MIND_LLAMA_BACKEND");
        Environment.SetEnvironmentVariable("BAXY_MIND_LLM_GGUF", stock);
        Environment.SetEnvironmentVariable("BAXY_MIND_MMPROJ", null);
        try
        {
            const long Card = 8192 * Mib;
            var context = new LocalContext(_root);
            JsonObject unknown = context.Json(prefixTokens: 49086, backend: null, switching: false, cardBytes: Card, freeBytes: 7000 * Mib);
            JsonObject cuda = context.Json(prefixTokens: 49086, backend: "cuda", switching: false, cardBytes: Card, freeBytes: 7000 * Mib);
            JsonObject vulkan = context.Json(prefixTokens: 49086, backend: "vulkan", switching: false, cardBytes: Card, freeBytes: 7000 * Mib);
            Assert.Multiple(() =>
            {
                Assert.That(unknown["options"]!.AsArray().All(static option => option!["vramBytes"] is null), Is.True, "no figure of a backend it may not be");
                Assert.That((unknown["recommended"], unknown["recommendedWhy"]), Is.EqualTo(((JsonNode?)null, (JsonNode?)null)),
                    "and nothing is said not to fit by figures it does not have");
                Assert.That((bool?)Option(unknown, 61440)["fits"], Is.True, "what fits the prompt does not wait for the backend");
                Assert.That((long?)Option(vulkan, 61440)["vramBytes"], Is.GreaterThan((long?)Option(cuda, 61440)["vramBytes"] ?? long.MaxValue),
                    "why: the same context takes more on Vulkan than NVIDIA's figure says");
                Assert.That((int?)cuda["recommended"], Is.Not.Null);
            });

            await using var viewModel = new MainWindowViewModel();
            Environment.SetEnvironmentVariable("BAXY_MIND_LLAMA_BACKEND", null);
            Assert.That(viewModel.MindBackend, Is.Null, "no mind said it and the start chose none");
            Environment.SetEnvironmentVariable("BAXY_MIND_LLAMA_BACKEND", "vulkan");
            Assert.That(viewModel.MindBackend, Is.EqualTo("vulkan"), "the server the App's start chose by the card");
            Environment.SetEnvironmentVariable("BAXY_MIND_LLAMA_BACKEND", "otra cosa");
            Assert.That(viewModel.MindBackend, Is.Null, "not a backend BAXY has figures for");
        }
        finally
        {
            Environment.SetEnvironmentVariable("BAXY_MIND_LLM_GGUF", model);
            Environment.SetEnvironmentVariable("BAXY_MIND_MMPROJ", vision);
            Environment.SetEnvironmentVariable("BAXY_MIND_LLAMA_BACKEND", chosen);
        }
    }

    [Test]
    public void WithItsVisionOnTheCardEachPresetSaysAtLeastWhatTheNotebookMeasured()
    {
        // nvidia-smi on the notebook (RTX 3060 Laptop 6 GB, b11609, documentacion/VRAM_ESTIMADA.md): Qwen3.5-4B with its
        // output in RAM and its projector on the GPU after reading an image, 3,972 MiB at 32,768 cells and 4,940 at 77,824.
        string gguf = Path.Combine(_root, "Qwen3.5-4B-Q4_K_M.gguf");
        string projector = Path.Combine(_root, "mmproj-F16.gguf");
        using (var file = new FileStream(gguf, FileMode.Create))
        {
            file.Write(ModelMemoryTests.Qwen35);
            file.SetLength(ModelMemoryTests.QwenFile);
        }

        using (var file = new FileStream(projector, FileMode.Create))
        {
            file.SetLength(ModelMemoryTests.QwenProjector);
        }

        string? model = Environment.GetEnvironmentVariable("BAXY_MIND_LLM_GGUF");
        string? vision = Environment.GetEnvironmentVariable("BAXY_MIND_MMPROJ");
        Environment.SetEnvironmentVariable("BAXY_MIND_LLM_GGUF", gguf);
        Environment.SetEnvironmentVariable("BAXY_MIND_MMPROJ", projector);
        try
        {
            JsonObject view = new LocalContext(_root).Json(prefixTokens: 49086, backend: "cuda", switching: false, cardBytes: 6144 * Mib, freeBytes: 5900 * Mib);
            long Shown(int cells) => (long?)Option(view, cells)["vramBytes"] ?? 0;

            Assert.Multiple(() =>
            {
                Assert.That(Shown(32768), Is.GreaterThanOrEqualTo(3972 * Mib));
                Assert.That((bool?)Option(view, 77824)["vision"], Is.True, "6 GB hold the server and the projector");
                Assert.That((int?)view["native"], Is.EqualTo(262144), "the GGUF's own qwen35.context_length");
                Assert.That((int?)view["recommended"], Is.EqualTo(98304), "the most that fits 5,900 MiB with the screen's reading on the card");
                Assert.That((string?)view["recommendedWhy"], Is.EqualTo("tarjeta"));
                Assert.That(Shown(77824), Is.GreaterThanOrEqualTo(4940 * Mib));
                Assert.That(Shown(77824), Is.LessThanOrEqualTo(4940 * Mib * 1.12));
            });
        }
        finally
        {
            Environment.SetEnvironmentVariable("BAXY_MIND_LLM_GGUF", model);
            Environment.SetEnvironmentVariable("BAXY_MIND_MMPROJ", vision);
        }
    }

    [Test]
    public void AFileOfBaxysOwnSaysWhatItTakesOnDiskAndOnTheCardWhicheverTheMindRunsNow()
    {
        // MOD1 V-07 / VIVO2 F11 (2026-11-09): in «Modelos en este PC» the stock model's row said «—» for its size and no row of
        // BAXY's own said its VRAM. Each file says its weight and what llama-server takes with it at the context a mind would
        // start with now, counted as the presets' own figures are: also the one the mind is not running (with the tuned model
        // in use, BAXY_MIND_LLM_GGUF names the tuned file, and the stock row is still the stock file's).
        string stock = Path.Combine(_root, "de-serie.gguf");
        string tuned = Path.Combine(_root, "ajustado.gguf");
        string projector = Path.Combine(_root, "mmproj-F16.gguf");
        using (var file = new FileStream(stock, FileMode.Create))
        {
            file.Write(ModelMemoryTests.Qwen35);
            file.SetLength(ModelMemoryTests.QwenFile);
        }

        using (var file = new FileStream(tuned, FileMode.Create))
        {
            file.Write(ModelMemoryTests.Qwen35);
            file.SetLength(ModelMemoryTests.QwenFile - (64 * Mib));
        }

        using (var file = new FileStream(projector, FileMode.Create))
        {
            file.SetLength(ModelMemoryTests.QwenProjector);
        }

        string? model = Environment.GetEnvironmentVariable("BAXY_MIND_LLM_GGUF");
        string? vision = Environment.GetEnvironmentVariable("BAXY_MIND_MMPROJ");
        Environment.SetEnvironmentVariable("BAXY_MIND_MMPROJ", projector);
        try
        {
            const long Card = 6144 * Mib;
            var context = new LocalContext(_root);
            Environment.SetEnvironmentVariable("BAXY_MIND_LLM_GGUF", stock);
            JsonObject asStock = context.Json(prefixTokens: 49086, backend: "cuda", switching: false, cardBytes: Card);
            JsonObject onVulkan = context.Json(prefixTokens: 49086, backend: "vulkan", switching: false, cardBytes: Card);
            Environment.SetEnvironmentVariable("BAXY_MIND_LLM_GGUF", tuned);
            JsonObject asTuned = context.Json(prefixTokens: 49086, backend: "cuda", switching: false, cardBytes: Card);

            JsonObject? stockSaid = context.OnDisk(stock, "cuda", Card);
            JsonObject? tunedSaid = context.OnDisk(tuned, "cuda", Card);
            JsonObject? vulkanSaid = context.OnDisk(stock, "vulkan", Card);
            JsonObject? processorSaid = context.OnDisk(stock, "cpu", Card);
            JsonObject? unknownSaid = context.OnDisk(stock, null, Card);
            Assert.That(context.Apply(new JsonObject { ["context"] = 98304 }, 49086), Is.Null);
            JsonObject? chosenSaid = context.OnDisk(stock, null, Card);
            Assert.Multiple(() =>
            {
                Assert.That((long?)stockSaid?["bytes"], Is.EqualTo(ModelMemoryTests.QwenFile));
                Assert.That((long?)tunedSaid?["bytes"], Is.EqualTo(ModelMemoryTests.QwenFile - (64 * Mib)));
                Assert.That((int?)stockSaid?["vramContext"], Is.EqualTo(LocalContext.CudaAutomatic));
                Assert.That((long?)stockSaid?["vramBytes"], Is.EqualTo((long?)Option(asStock, LocalContext.CudaAutomatic)["vramBytes"]),
                    "the stock file's, though the mind's variable names the tuned one now");
                Assert.That((long?)stockSaid?["vramBytes"], Is.GreaterThanOrEqualTo(4940 * Mib), "what the notebook measured with its projector on the card");
                Assert.That((long?)tunedSaid?["vramBytes"], Is.EqualTo((long?)Option(asTuned, LocalContext.CudaAutomatic)["vramBytes"]));
                Assert.That((long?)tunedSaid?["vramBytes"], Is.LessThan((long?)stockSaid?["vramBytes"] ?? 0), "each file's own weight");
                Assert.That(((int?)vulkanSaid?["vramContext"], (long?)vulkanSaid?["vramBytes"]),
                    Is.EqualTo(((int?)LocalContext.VulkanAutomatic, (long?)Option(onVulkan, LocalContext.VulkanAutomatic)["vramBytes"])));
                Assert.That(processorSaid?["vramBytes"], Is.Null, "on the processor it takes nothing of the card");
                Assert.That((long?)processorSaid?["bytes"], Is.EqualTo(ModelMemoryTests.QwenFile));
                Assert.That((unknownSaid?["vramBytes"], unknownSaid?["vramContext"]), Is.EqualTo(((JsonNode?)null, (JsonNode?)null)),
                    "no mind has said its backend and nothing is chosen: the context it would start with is not known");
                // REV_APP VRAM-b: the context is the person's, and the figure waits for the backend (it was NVIDIA's on any card)
                Assert.That(((int?)chosenSaid?["vramContext"], chosenSaid?["vramBytes"]), Is.EqualTo(((int?)98304, (JsonNode?)null)),
                    "the context the person chose, with no figure until the backend is known");
                Assert.That((long?)context.OnDisk(stock, "cuda", Card)?["vramBytes"], Is.EqualTo((long?)Option(asStock, 98304)["vramBytes"]));
                Assert.That(context.OnDisk(Path.Combine(_root, "no-esta.gguf"), "cuda", Card), Is.Null);
                Assert.That(context.OnDisk(null, "cuda", Card), Is.Null);
            });
        }
        finally
        {
            Environment.SetEnvironmentVariable("BAXY_MIND_LLM_GGUF", model);
            Environment.SetEnvironmentVariable("BAXY_MIND_MMPROJ", vision);
        }
    }

    [TestCase("cuda", 77824)]
    [TestCase("vulkan", 61440)]
    [TestCase("cpu", 53248)]
    [TestCase(null, null)]
    public void AutomaticIsWhatTheMindChoosesOnItsBackend(string? backend, int? cells)
    {
        Assert.That(LocalContext.Automatic(backend), Is.EqualTo(cells));
        Assert.That((int?)new LocalContext(_root).Json(null, backend, switching: false)["automatic"], Is.EqualTo(cells));
    }

    [Test]
    public void OnlyAChangeAgainstAMindOnBaxysOwnModelNeedsARelaunch()
    {
        var context = new LocalContext(_root);
        Assert.That(context.Apply(new JsonObject { ["context"] = 65536 }, prefixTokens: null), Is.Null);
        // No mind came up yet: the next start takes it.
        Assert.That(context.NeedsSwitch, Is.False);
        context.ApplyEnvironment();
        context.Started(ownModel: true);
        Assert.That(context.NeedsSwitch, Is.False);
        context.Apply(new JsonObject { ["context"] = 98304 }, prefixTokens: null);
        Assert.That(context.NeedsSwitch, Is.True);
        Assert.That((bool?)context.Json(null, "cuda", switching: false)["switching"], Is.True);
        context.ApplyEnvironment();
        context.Started(ownModel: true);
        Assert.That(context.NeedsSwitch, Is.False);
        // A mind on another model (ExternalModel) does not run this context: changing it relaunches nothing.
        context.Started(ownModel: false);
        context.Apply(new JsonObject { ["context"] = null }, prefixTokens: null);
        Assert.That(context.NeedsSwitch, Is.False);
    }

    [Test]
    public void AnUnreadableFileIsAutomatic()
    {
        File.WriteAllText(Path.Combine(_root, LocalContext.FileName), "{ no es json");
        Assert.That(new LocalContext(_root).Chosen(), Is.Null);
        File.WriteAllText(Path.Combine(_root, LocalContext.FileName), """{"context":70000}""");
        Assert.That(new LocalContext(_root).Chosen(), Is.Null);
    }

    [Test]
    public async Task TheViewKeepsItThroughItsRoute()
    {
        System.Reflection.FieldInfo field = typeof(MainWindowViewModel)
            .GetField("_localContext", System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic)!;
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        {
            field.SetValue(viewModel, new LocalContext(_root));
            await using var view = new ChannelHarness(viewModel);

            (int status, JsonObject body) = await view.SendAsync("PUT", "/settings/local-context", new JsonObject { ["context"] = 98304 });
            Assert.That((status, (int?)body["chosen"]), Is.EqualTo((200, 98304)));
            Assert.That(body["options"]!.AsArray(), Has.Count.EqualTo(LocalContext.Presets.Length));

            (status, body) = await view.SendAsync("PUT", "/settings/local-context", new JsonObject { ["context"] = 1234 });
            Assert.That((status, (string?)body["error"]), Is.EqualTo((409, "local_context_invalid")));

            (status, body) = await view.SendAsync("GET", "/settings/local-context");
            Assert.That((status, (int?)body["chosen"]), Is.EqualTo((200, 98304)));
            // With no engine here no mind starts; the switch ends and the next start takes it.
            Assert.That(() => viewModel.ExternalModelState.Switching, Is.False.After(5000, 50));
            field.SetValue(viewModel, null);
        }
    }
}
