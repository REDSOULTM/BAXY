using System.IO;
using System.Text;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// Encargo del dueño 2026-11-08 («nunca mentir» con la VRAM): the one estimate against what nvidia-smi measured on the
/// notebook (RTX 3060 Laptop, llama.cpp b11609, the product's arguments; documentacion/VRAM_ESTIMADA.md). The headers are
/// the four models' own keys, written here as GGUF.
/// </summary>
[TestFixture]
public sealed class ModelMemoryTests
{
    private const long MiB = 1L << 20;

    // Qwen3.5-4B Q4_K_M (unsloth), its file and its token embedding (2,560 × 248,320 at Q6_K).
    internal const long QwenFile = 2_740_937_888;
    internal const long QwenProjector = 672_423_616;

    internal static byte[] Qwen35 => Gguf.Header("qwen35", tokenEmbedding: (2560, 248320, 14),
        ("block_count", 32u), ("context_length", 262144u), ("embedding_length", 2560u), ("feed_forward_length", 9216u),
        ("attention.head_count", 16u), ("attention.head_count_kv", 4u), ("attention.key_length", 256u),
        ("attention.value_length", 256u), ("ssm.conv_kernel", 4u), ("ssm.state_size", 128u), ("ssm.group_count", 16u),
        ("ssm.time_step_rank", 32u), ("ssm.inner_size", 4096u), ("full_attention_interval", 4u));

    internal static byte[] Llama32 => Gguf.Header("llama", tokenEmbedding: null,
        ("block_count", 28u), ("context_length", 131072u), ("embedding_length", 3072u), ("feed_forward_length", 8192u),
        ("attention.head_count", 24u), ("attention.head_count_kv", 8u), ("attention.key_length", 128u), ("attention.value_length", 128u));

    private static byte[] Qwen3 => Gguf.Header("qwen3", tokenEmbedding: null,
        ("block_count", 28u), ("context_length", 40960u), ("embedding_length", 2048u), ("feed_forward_length", 6144u),
        ("attention.head_count", 16u), ("attention.head_count_kv", 8u), ("attention.key_length", 128u), ("attention.value_length", 128u));

    private static byte[] Gemma3 => Gguf.Header("gemma3", tokenEmbedding: null,
        ("context_length", 131072u), ("embedding_length", 2560u), ("block_count", 34u), ("feed_forward_length", 10240u),
        ("attention.head_count", 8u), ("attention.key_length", 256u), ("attention.value_length", 256u),
        ("attention.sliding_window", 1024u), ("attention.head_count_kv", 4u));

    [Test]
    public void TheHeaderGivesTheLayersThatKeepACacheAndTheState()
    {
        GgufShape qwen = Shape(Qwen35, tensors: true);
        GgufShape gemma = Shape(Gemma3, tensors: false);

        Assert.Multiple(() =>
        {
            Assert.That(qwen.FullLayers, Is.EqualTo(8), "Qwen3.5 keeps a cache in one layer of four");
            Assert.That(qwen.FullCellValues, Is.EqualTo(8 * 4 * 512));
            // llama.cpp: «CUDA0 RS buffer size = 50.25 MiB».
            Assert.That(qwen.RecurrentValues * 4, Is.EqualTo((long)(50.25 * MiB)));
            Assert.That(qwen.TokenEmbeddingBytes, Is.EqualTo(2560L * 248320 / 256 * 210));
            Assert.That(qwen.ContextLength, Is.EqualTo(262144));
            Assert.That((gemma.FullLayers, gemma.SlidingLayers, gemma.SlidingWindow), Is.EqualTo((5, 29, 1024)), "five of every six slide");
            Assert.That(gemma.TokenEmbeddingBytes, Is.Null, "read without the tensors");
        });
    }

    // What nvidia-smi said over the GPU's own use, the most of after loading, after the prompt and after the image.
    [TestCase("qwen35", 8192, true, false, 2526)]
    [TestCase("qwen35", 32768, true, false, 3054)]
    [TestCase("qwen35", 57344, true, false, 3582)]
    [TestCase("qwen35", 77824, true, false, 4022)]
    [TestCase("qwen35", 8192, true, true, 3444)]
    [TestCase("qwen35", 32768, true, true, 3972)]
    [TestCase("qwen35", 57344, true, true, 4500)]
    [TestCase("qwen35", 77824, true, true, 4940)]
    [TestCase("qwen35", 8192, false, false, 3022)]
    [TestCase("qwen35", 53248, false, false, 3990)]
    [TestCase("qwen3", 8192, false, false, 1712)]
    [TestCase("qwen3", 32768, false, false, 3260)]
    [TestCase("qwen3", 40960, false, false, 3772)]
    [TestCase("llama", 8192, false, false, 2601)]
    [TestCase("llama", 32768, false, false, 4139)]
    [TestCase("llama", 57344, false, false, 5687)]
    [TestCase("gemma3", 8192, false, false, 2768)]
    [TestCase("gemma3", 32768, false, false, 3118)]
    [TestCase("gemma3", 32768, false, true, 4112)]
    public void TheEstimateIsNeverBelowWhatLlamaServerTookAndCloseToIt(string model, int context, bool outputInRam, bool projector, int measuredMiB)
    {
        (byte[] header, long file, long vision) = model switch
        {
            "qwen35" => (Qwen35, QwenFile, QwenProjector),
            "qwen3" => (Qwen3, 1_107_409_472L, 0L),
            "llama" => (Llama32, 2_019_377_696L, 0L),
            _ => (Gemma3, 2_489_894_016L, 851_251_328L),
        };

        long estimate = ModelMemory.GpuBytes(Shape(header, tensors: true), file, context, "q8_0", outputInRam, projector ? vision : 0);

        Assert.That(estimate / (double)MiB, Is.InRange(measuredMiB, measuredMiB * 1.12));
    }

    // Ollama 0.40.15 (its f16 cache, flash attention on its own): nvidia-smi with the whole model on the GPU.
    [TestCase("llama", 8192, 3094)]
    [TestCase("qwen35", 8192, 3198)]
    [TestCase("qwen35", 32768, 3908)]
    public void TheEstimateIsNeverBelowWhatOllamaTook(string model, int context, int measuredMiB)
    {
        (byte[] header, long file) = model == "llama" ? (Llama32, 2_019_377_696L) : (Qwen35, QwenFile);

        long estimate = ModelMemory.GpuBytes(Shape(header, tensors: true), file, context, "f16");

        Assert.That(estimate / (double)MiB, Is.InRange(measuredMiB, measuredMiB * 1.12));
    }

    [Test]
    public void AnOllamaModelsOptionsComeFromItsFilesAsEachWillRun()
    {
        // Ollama's own size for Qwen3.5-4B at 8,192 was 3,074 MiB where nvidia-smi saw 3,198: the files' headers say it.
        string folder = Directory.CreateTempSubdirectory("baxy-ollama-files-").FullName;
        try
        {
            string model = Path.Combine(folder, "sha256-model");
            string projector = Path.Combine(folder, "sha256-projector");
            using (var file = new FileStream(model, FileMode.Create))
            {
                file.Write(Qwen35);
                file.SetLength(QwenFile);
            }

            using (var file = new FileStream(projector, FileMode.Create))
            {
                file.Write("GGUF"u8);
                file.SetLength(QwenProjector);
            }

            var answer = new System.Text.Json.Nodes.JsonObject
            {
                ["contextLength"] = 65536,
                ["modelFiles"] = new System.Text.Json.Nodes.JsonArray(model, projector),
                ["options"] = new System.Text.Json.Nodes.JsonArray(
                    new System.Text.Json.Nodes.JsonObject { ["context"] = 8192, ["bytes"] = 3074 * MiB },
                    new System.Text.Json.Nodes.JsonObject { ["context"] = 78000, ["bytes"] = 1L }),
            };

            ExternalModel.SayVideoMemory(answer);

            long Bytes(int index) => (long?)answer["options"]![index]!["bytes"] ?? 0;
            GgufShape shape = Shape(Qwen35, tensors: true);
            Assert.Multiple(() =>
            {
                Assert.That(Bytes(0), Is.EqualTo(ModelMemory.GpuBytes(shape, QwenFile, 8192, "f16", projectorBytes: QwenProjector)));
                Assert.That(Bytes(0), Is.GreaterThanOrEqualTo(3198 * MiB));
                Assert.That(Bytes(1), Is.EqualTo(ModelMemory.GpuBytes(shape, QwenFile, 78000, "q8_0")), "past what it declares it runs on BAXY's server");
                Assert.That((string?)answer["bytesFrom"], Is.EqualTo("cabecera"));
                Assert.That(answer.ContainsKey("modelFiles"), Is.False, "no path goes to the view");
            });
        }
        finally
        {
            Directory.Delete(folder, recursive: true);
        }
    }

    [Test]
    public void EachInstalledModelSaysTheVideoMemoryItTakesAtTheLeastContextItWouldRunWith()
    {
        // MOD1 V-07 (REV_VISTA, 2026-11-09): «Modelos en este PC» said each model's weight on disk and nothing of the card. A
        // model of Ollama's is connected with the context the card holds, never under what the tool profile's prompt and a turn
        // take: that least, on Ollama as it runs it there (f16 cache, its projector), is what its row says, from its own files.
        string folder = Directory.CreateTempSubdirectory("baxy-ollama-list-").FullName;
        try
        {
            string large = Path.Combine(folder, "sha256-largo");
            string projector = Path.Combine(folder, "sha256-proyector");
            string small = Path.Combine(folder, "sha256-corto");
            using (var file = new FileStream(large, FileMode.Create))
            {
                file.Write(Qwen35);
                file.SetLength(QwenFile);
            }

            using (var file = new FileStream(projector, FileMode.Create))
            {
                file.Write("GGUF"u8);
                file.SetLength(QwenProjector);
            }

            using (var file = new FileStream(small, FileMode.Create))
            {
                file.Write(Qwen3);
                file.SetLength(1_100_000_000);
            }

            int complete = ToolProfile.NeededContext(ToolProfile.Completo, null, null);
            int essential = ToolProfile.NeededContext("esencial", null, null);
            System.Text.Json.Nodes.JsonObject Row(string id, bool fits, int? context, string? profile, params string[] files)
            {
                var row = new System.Text.Json.Nodes.JsonObject { ["id"] = id, ["fits"] = fits, ["context"] = context, ["profile"] = profile };
                if (files.Length > 0)
                {
                    row["modelFiles"] = new System.Text.Json.Nodes.JsonArray([.. files.Select(static file => (System.Text.Json.Nodes.JsonNode?)file)]);
                }

                return row;
            }

            var listed = new System.Text.Json.Nodes.JsonObject
            {
                ["models"] = new System.Text.Json.Nodes.JsonArray(
                    Row("largo", fits: true, 262144, null, large, projector),
                    Row("corto", fits: false, 40960, "esencial", small),
                    Row("calla", fits: true, null, null, small),
                    Row("no-sirve", fits: false, 40960, null, small),
                    Row("ido", fits: true, 262144, null, Path.Combine(folder, "no-esta")),
                    Row("nube", fits: true, 262144, null)),
            };

            ExternalModel.WithVideoMemory(listed, complete, profile => ToolProfile.NeededContext(profile, null, null));

            System.Text.Json.Nodes.JsonObject Said(string id) =>
                listed["models"]!.AsArray().Single(row => (string?)row!["id"] == id)!.AsObject();
            GgufShape qwen35 = Shape(Qwen35, tensors: true);
            GgufShape qwen3 = Shape(Qwen3, tensors: true);
            Assert.Multiple(() =>
            {
                Assert.That(essential, Is.LessThan(40960), "Esencial fits the short model's own context");
                Assert.That(((int?)Said("largo")["vramContext"], (long?)Said("largo")["vramBytes"]),
                    Is.EqualTo(((int?)complete, (long?)ModelMemory.GpuBytes(qwen35, QwenFile, complete, "f16", projectorBytes: QwenProjector))));
                Assert.That(((int?)Said("corto")["vramContext"], (long?)Said("corto")["vramBytes"]),
                    Is.EqualTo(((int?)essential, (long?)ModelMemory.GpuBytes(qwen3, 1_100_000_000, essential, "f16"))),
                    "one offered with a smaller profile, at that profile's need");
                Assert.That(((int?)Said("calla")["vramContext"], (long?)Said("calla")["vramBytes"]),
                    Is.EqualTo(((int?)40960, (long?)ModelMemory.GpuBytes(qwen3, 1_100_000_000, 40960, "f16"))),
                    "Ollama gave no context: the file's own, which is under the need, and it never runs past it there");
                Assert.That(Said("no-sirve").ContainsKey("vramBytes"), Is.False, "one BAXY cannot use takes nothing with it");
                Assert.That(Said("ido").ContainsKey("vramBytes"), Is.False, "no file read, no figure");
                Assert.That(Said("nube").ContainsKey("vramBytes"), Is.False);
                Assert.That(listed.ToJsonString(), Does.Not.Contain("sha256-"), "no path goes to the view");
            });
        }
        finally
        {
            Directory.Delete(folder, recursive: true);
        }
    }

    [Test]
    public void AShortModelConnectedWithTheProfileThatFitsItIsRecommendedItsOwnContext()
    {
        // VIVO2: mistral:latest declares 32,768 and «Usar con Esencial» connected it asking for 52,000, BAXY's least for its
        // whole catalog, so it was refused for VRAM at a context it does not take. With the chosen profile's need, a short model
        // runs with what it declares; with Completo's, BAXY's least as before.
        string folder = Directory.CreateTempSubdirectory("baxy-ollama-short-").FullName;
        try
        {
            string model = Path.Combine(folder, "sha256-model");
            using (var file = new FileStream(model, FileMode.Create))
            {
                file.Write(Qwen3);
                file.SetLength(1_100_000_000);
            }

            System.Text.Json.Nodes.JsonObject Said(int need)
            {
                var answer = new System.Text.Json.Nodes.JsonObject
                {
                    ["contextLength"] = 40960,
                    ["modelFiles"] = new System.Text.Json.Nodes.JsonArray(model),
                    ["options"] = new System.Text.Json.Nodes.JsonArray(new System.Text.Json.Nodes.JsonObject { ["context"] = 8192, ["bytes"] = 1L }),
                };
                ExternalModel.SayVideoMemory(answer, free: 64L << 30, need: need);
                return answer;
            }

            int essential = ToolProfile.NeededContext("esencial", null, null);
            System.Text.Json.Nodes.JsonObject withEssential = Said(essential);
            System.Text.Json.Nodes.JsonObject withComplete = Said(ToolProfile.NeededContext(ToolProfile.Completo, null, null));
            Assert.Multiple(() =>
            {
                Assert.That(essential, Is.LessThan(40960), "Esencial fits the model's own context");
                Assert.That((int?)withEssential["recommended"], Is.EqualTo(40960));
                Assert.That((string?)withEssential["recommendedWhy"], Is.EqualTo("nativo"));
                Assert.That((string?)withComplete["recommendedWhy"], Is.EqualTo("minimo_baxy"), "Completo's prompt needs more than it declares");
            });
        }
        finally
        {
            Directory.Delete(folder, recursive: true);
        }
    }

    [Test]
    public void AModelThePersonRunsPartlyInRamConnectsAtTheContextTheyAccepted()
    {
        // VIVO2: mistral with Esencial was refused at 18,013 tokens and offered «Cargarlo en parte en la RAM»; once the mind had
        // read Esencial's prompt the recommendation was 16,947, so the yes given for 18,013 no longer matched and it was refused
        // again, with no option left. What the person accepted is what it connects with; what they chose comes first.
        var measured = new System.Text.Json.Nodes.JsonObject
        {
            ["bytesFrom"] = "cabecera", ["recommended"] = 16947, ["recommendedWhy"] = "no_cabe", ["contextLength"] = 32768,
        };
        Assert.Multiple(() =>
        {
            Assert.That(ExternalModel.ConnectContext(null, 18013, measured, 16947), Is.EqualTo(18013));
            Assert.That(ExternalModel.ConnectContext(null, null, measured, 16947), Is.EqualTo(16947), "nothing accepted: the recommendation");
            Assert.That(ExternalModel.ConnectContext(32768, 18013, measured, 16947), Is.EqualTo(32768), "a context the person chose comes first");
        });
    }

    [Test]
    public void AContextAcceptedOrChosenForAnotherProfileOrAnotherCardIsNotKept()
    {
        // VIVO2, blind review of the fix above: the yes to run partly in RAM, and a chosen context, are kept per model. With a
        // bigger profile afterwards (Completo needs more than the 18,013 accepted with Esencial) the model would connect short of
        // its prompt and be refused with «elige un perfil más pequeño»; and once its recommendation fits the card whole, there is
        // no reason left to run it partly in RAM.
        var shortOfCard = new System.Text.Json.Nodes.JsonObject
        {
            ["bytesFrom"] = "cabecera", ["recommended"] = 52670, ["recommendedWhy"] = "no_cabe", ["contextLength"] = 131072,
        };
        var fitsWhole = new System.Text.Json.Nodes.JsonObject
        {
            ["bytesFrom"] = "cabecera", ["recommended"] = 16947, ["recommendedWhy"] = "tarjeta", ["contextLength"] = 32768,
        };
        Assert.Multiple(() =>
        {
            Assert.That(ExternalModel.ConnectContext(null, 18013, shortOfCard, 52670), Is.EqualTo(52670), "accepted under the profile's need");
            Assert.That(ExternalModel.ConnectContext(20480, null, shortOfCard, 52670), Is.EqualTo(52670), "chosen under the profile's need");
            Assert.That(ExternalModel.ConnectContext(null, 18013, fitsWhole, 16947), Is.EqualTo(16947), "the recommendation now fits whole");
        });
    }

    // gpt-oss-20b's own keys (ggml-org/gpt-oss-20b-GGUF, MXFP4, read 2026-11-09): a window of 128 on every other layer.
    private static byte[] GptOss => Gguf.Header("gpt-oss", tokenEmbedding: null,
        ("block_count", 24u), ("context_length", 131072u), ("embedding_length", 2880u), ("feed_forward_length", 2880u),
        ("attention.head_count", 64u), ("attention.head_count_kv", 8u), ("expert_count", 32u), ("expert_used_count", 4u),
        ("attention.key_length", 64u), ("attention.value_length", 64u), ("attention.sliding_window", 128u),
        ("expert_feed_forward_length", 2880u));

    [Test]
    public void GptOssKeepsAWholeCacheInHalfItsLayersAndItsExpertsSizeTheBatch()
    {
        GgufShape shape = Shape(GptOss, tensors: false);
        long cache8k = ModelMemory.GpuBytes(shape, 0, 8192, "f16") - ModelMemory.GpuBytes(shape, 0, 0, "f16");

        Assert.Multiple(() =>
        {
            Assert.That((shape.FullLayers, shape.SlidingLayers, shape.SlidingWindow), Is.EqualTo((12, 12, 128)));
            Assert.That(shape.FeedForward, Is.EqualTo(2880 * 4), "four experts at a time");
            // 12 layers × 8 heads × (64 + 64) × 2 bytes = 24 KiB a cell: 192 MiB per 8,192 (and its compute share beside it).
            Assert.That(cache8k, Is.InRange(192 * MiB, 192 * MiB + (8192L * 3 * 1024) + (24 * MiB)));
        });
    }

    // gpt-oss-20b does not fit the notebook's 6 GB: what it needs whole on the GPU is llama.cpp's own count before loading
    // («projected to use N MiB of device memory», b11609) and the CUDA runtime it leaves out (134 MiB measured beside it).
    // llama-server with the product's q8_0 cache on ggml-org's MXFP4 file; Ollama 0.40.15 (f16) on its own gpt-oss:20b.
    [TestCase(12_109_566_624L, "q8_0", 4096, 11104)]
    [TestCase(12_109_566_624L, "q8_0", 8192, 11159)]
    [TestCase(12_109_566_624L, "q8_0", 78000, 12199)]
    [TestCase(13_793_441_566L, "f16", 4096, 12245)]
    [TestCase(13_793_441_566L, "f16", 8192, 12345)]
    [TestCase(13_793_441_566L, "f16", 32768, 12945)]
    public void GptOssIsNeverBelowWhatLlamaCppCountsForItWhole(long file, string kv, int context, int projectedMiB)
    {
        long needs = (projectedMiB + 134) * MiB;

        long estimate = ModelMemory.GpuBytes(Shape(GptOss, tensors: false), file, context, kv);

        Assert.That(estimate, Is.InRange(needs, needs * 1.12));
    }

    [Test]
    public void TheRecommendedContextIsTheModelsOwnWhenItFitsElseTheMostThatDoes()
    {
        GgufShape llama = Shape(Llama32, tensors: false);
        long At(int tokens) => ModelMemory.GpuBytes(llama, 2_019_377_696, tokens, "f16");
        const long Sixteen = 16L << 30;

        (int whole, string wholeWhy) = ModelMemory.Recommend(At, 131072, 52000, 64L << 30);
        (int card, string cardWhy) = ModelMemory.Recommend(At, 131072, 52000, Sixteen);
        (int none, string noneWhy) = ModelMemory.Recommend(At, 131072, 52000, 4L << 30);
        (int least, string leastWhy) = ModelMemory.Recommend(At, 40960, 52000, Sixteen);
        (int unknown, string unknownWhy) = ModelMemory.Recommend(At, 131072, 52000, null);

        Assert.Multiple(() =>
        {
            Assert.That((whole, wholeWhy), Is.EqualTo((131072, "nativo")));
            Assert.That(cardWhy, Is.EqualTo("tarjeta"));
            Assert.That(At(card), Is.LessThanOrEqualTo(Sixteen), "what is recommended fits");
            Assert.That(At(card + 2048), Is.GreaterThan(Sixteen), "and is the most that does");
            Assert.That((none, noneWhy), Is.EqualTo((52000, "no_cabe")));
            Assert.That((least, leastWhy), Is.EqualTo((52000, "minimo_baxy")), "BAXY's prompt needs more than this model declares");
            Assert.That((unknown, unknownWhy), Is.EqualTo((131072, "nativo")));
        });
    }

    [Test]
    public void AModelThatDoesNotFitItsContextIsNotLoadedUntilThePersonChooses()
    {
        // Owner's order 2026-11-09 (gpt-oss crashed Ollama's runner 9 times on the PC): what its own estimate says does not fit is
        // said before loading, with what it needs and what is free, and the most that fits; past what it declares it runs on
        // BAXY's server, where it cannot go partly to RAM.
        var measured = new System.Text.Json.Nodes.JsonObject
        {
            ["bytesFrom"] = "cabecera",
            ["contextLength"] = 131072,
            ["recommended"] = 64000,
            ["recommendedWhy"] = "tarjeta",
            ["options"] = new System.Text.Json.Nodes.JsonArray(
                new System.Text.Json.Nodes.JsonObject { ["context"] = 64000, ["bytes"] = 9L << 30 },
                new System.Text.Json.Nodes.JsonObject { ["context"] = 131072, ["bytes"] = 15L << 30 },
                new System.Text.Json.Nodes.JsonObject { ["context"] = 200000, ["bytes"] = 17L << 30 }),
        };
        const long Free = 10L << 30;

        var tooBig = ExternalModel.ShortOfVramFor(measured, 131072, Free, partialAccepted: null);
        var beyond = ExternalModel.ShortOfVramFor(measured, 200000, Free, partialAccepted: null);

        Assert.Multiple(() =>
        {
            Assert.That(tooBig, Is.EqualTo((131072, 15L << 30, Free, (int?)64000, true)));
            Assert.That(beyond?.PartialPossible, Is.False, "BAXY's own server keeps every layer on the card");
            Assert.That(ExternalModel.ShortOfVramFor(measured, 64000, Free, partialAccepted: null), Is.Null, "what fits loads");
            Assert.That(ExternalModel.ShortOfVramFor(measured, 131072, Free, partialAccepted: 131072), Is.Null, "the person chose RAM at this context");
            Assert.That(ExternalModel.ShortOfVramFor(measured, 131072, Free, partialAccepted: 96000), Is.Not.Null, "a choice for another context is not this one");
            Assert.That(ExternalModel.ShortOfVramFor(measured, 131072, null, partialAccepted: null), Is.Null, "with the free VRAM not known nothing is claimed");
            Assert.That(ExternalModel.ShortOfVramFor(new System.Text.Json.Nodes.JsonObject { ["bytesFrom"] = "ollama" }, 131072, Free, null), Is.Null,
                "without the model's files there is no estimate of BAXY's to go by");
        });
    }

    [Test]
    public void TheTranslatorChecksTheRamWithTheEstimateTheViewSaysAndWhereTheModelGoes()
    {
        // INT18 blind review: with no measure of Ollama's kept (refused, or failed), the translator checked the RAM by the file
        // alone, without the context, as if whole on the card; the view said «sin memoria» by the estimate from the model's files.
        // The App passes that estimate at the context it connects with, and «whole» only when it saw it fit the free VRAM.
        var measured = new System.Text.Json.Nodes.JsonObject
        {
            ["bytesFrom"] = "cabecera",
            ["options"] = new System.Text.Json.Nodes.JsonArray(
                new System.Text.Json.Nodes.JsonObject { ["context"] = 64000, ["bytes"] = 9L << 30 },
                new System.Text.Json.Nodes.JsonObject { ["context"] = 131072, ["bytes"] = 15L << 30 }),
        };
        const long Free = 10L << 30;
        string nine = (9L << 30).ToString(System.Globalization.CultureInfo.InvariantCulture);
        string fifteen = (15L << 30).ToString(System.Globalization.CultureInfo.InvariantCulture);

        Assert.Multiple(() =>
        {
            Assert.That(ExternalModel.MemoryArguments(measured, 64000, Free, partialAccepted: null), Is.EqualTo(new[] { "--vram-bytes", nine, "--entero" }));
            Assert.That(ExternalModel.MemoryArguments(measured, 131072, Free, partialAccepted: 131072), Is.EqualTo(new[] { "--en-parte", "--vram-bytes", fifteen }),
                "the person chose RAM at this context");
            Assert.That(ExternalModel.MemoryArguments(measured, 64000, null, partialAccepted: null), Is.EqualTo(new[] { "--vram-bytes", nine }),
                "with the free VRAM not known, where it goes is not claimed");
            Assert.That(ExternalModel.MemoryArguments(measured, 96000, Free, partialAccepted: null), Is.Empty, "no estimate at this context");
            Assert.That(ExternalModel.MemoryArguments(new System.Text.Json.Nodes.JsonObject { ["bytesFrom"] = "ollama", ["options"] = measured["options"]!.DeepClone() },
                64000, Free, partialAccepted: null), Is.EqualTo(new[] { "--entero" }), "Ollama's own figure is the translator's already; it fits the card");
        });
    }

    [Test]
    public void TheRecommendedContextFitsWhatWindowsCanPromiseToo()
    {
        // Seen in the real App on the PC (2026-11-09): llama3.2:3b recommended at the most the card held, then refused by the
        // translator for RAM («necesita unos 13,7 GB de RAM libre… y este PC tiene 8,8»). The recommendation keeps to both: the
        // VRAM free and what Windows can promise less what the process holds and 3 GiB (external_model.memory_problem).
        string folder = Directory.CreateTempSubdirectory("baxy-ollama-ram-").FullName;
        try
        {
            string model = Path.Combine(folder, "sha256-model");
            using (var file = new FileStream(model, FileMode.Create))
            {
                file.Write(Llama32);
                file.SetLength(2_019_377_696);
            }

            System.Text.Json.Nodes.JsonObject Answer() => new()
            {
                ["contextLength"] = 131072,
                ["modelFiles"] = new System.Text.Json.Nodes.JsonArray(model),
                ["options"] = new System.Text.Json.Nodes.JsonArray(new System.Text.Json.Nodes.JsonObject { ["context"] = 64000, ["bytes"] = 1L }),
            };
            var cardOnly = Answer();
            var both = Answer();
            const long Free = 14L << 30;
            const long Promise = 15L << 30;

            ExternalModel.SayVideoMemory(cardOnly, Free);
            ExternalModel.SayVideoMemory(both, Free, commitFree: Promise);

            GgufShape shape = Shape(Llama32, tensors: false);
            int recommended = (int?)both["recommended"] ?? 0;
            Assert.Multiple(() =>
            {
                Assert.That(recommended, Is.LessThan((int?)cardOnly["recommended"] ?? 0));
                Assert.That(ModelMemory.GpuBytes(shape, 2_019_377_696, recommended, "f16") + ModelMemory.CommitHostBytes + ModelMemory.CommitReserveBytes,
                    Is.LessThanOrEqualTo(Promise), "what is recommended passes the translator's check");
            });
        }
        finally
        {
            Directory.Delete(folder, recursive: true);
        }
    }

    [Test]
    public void TheRamRuleIsTheTranslatorsOwn()
    {
        // The App says before a download what the translator checks before connecting (external_model.memory_problem): the same
        // two numbers, measured on the PC on 2026-11-09, in both languages.
        string? repository = AppContext.BaseDirectory;
        while (repository is not null && !Directory.Exists(Path.Combine(repository, "src", "baxy_mind")))
        {
            repository = Path.GetDirectoryName(repository);
        }

        string python = File.ReadAllText(Path.Combine(repository!, "src", "baxy_mind", "external_model.py"));
        Assert.Multiple(() =>
        {
            Assert.That(python, Does.Contain("\nCOMMIT_HOST = int(2.75 * 2**30)\n"));
            Assert.That(ModelMemory.CommitHostBytes, Is.EqualTo((long)(2.75 * (1L << 30))));
            Assert.That(python, Does.Contain("\nMEMORY_RESERVE = 3 * 2**30\n"));
            Assert.That(ModelMemory.CommitReserveBytes, Is.EqualTo(3L << 30));
            Assert.That(ModelMemory.Room(14L << 30, 10L << 30), Is.EqualTo((10L << 30) - ModelMemory.CommitHostBytes - ModelMemory.CommitReserveBytes));
            Assert.That(ModelMemory.Room(4L << 30, 20L << 30), Is.EqualTo(4L << 30));
            Assert.That(ModelMemory.Room(null, null), Is.Null);
        });
    }

    [Test]
    public void WhatBaxysOwnModelFreesOfTheCommitIsWhatItHoldsNotOnlyItsVram()
    {
        // Seen in the real App on the PC (2026-11-09): BAXY's own llama-server held 6.7 GB of commit for 4.8 GB of VRAM; counting
        // only its VRAM as what a switch frees said «no cabe en este PC» of a 0.5 GB model.
        const long Promised = 2L << 30;
        Assert.Multiple(() =>
        {
            Assert.That(ExternalModel.CommitForAnother(Promised, ownVramGb: 4.8, ownCommitGb: 6.7), Is.EqualTo(Promised + (long)(6.7 * (1L << 30))));
            Assert.That(ExternalModel.CommitForAnother(Promised, ownVramGb: 4.8, ownCommitGb: null), Is.EqualTo(Promised + (long)(4.8 * (1L << 30))),
                "without its commit read, its VRAM, which it holds at least");
            Assert.That(ExternalModel.CommitForAnother(null, 4.8, 6.7), Is.Null);
        });
    }

    [Test]
    public void ATruncatedOrForeignHeaderIsNoShape()
    {
        byte[] whole = Qwen35;
        Assert.Multiple(() =>
        {
            Assert.That(GgufShape.Read(new MemoryStream(whole[..40]), tensors: false), Is.Null);
            Assert.That(GgufShape.Read(new MemoryStream(Encoding.ASCII.GetBytes("PK\u0003\u0004 not a model")), tensors: false), Is.Null);
            Assert.That(GgufShape.Read(Path.Combine(Path.GetTempPath(), "baxy-no-such-model.gguf")), Is.Null);
        });
    }

    // APP2 (REV11 A-5): a header from any Hugging Face repo with an empty head_count (or head_count_kv) array threw
    // IndexOutOfRangeException at heads[0], which neither Read's catch nor OpenModels' caught: it is no shape.
    [TestCase("attention.head_count")]
    [TestCase("attention.head_count_kv")]
    public void AHeaderWithAnEmptyHeadsArrayIsNoShape(string empty)
    {
        byte[] header = Gguf.Header("llama", tokenEmbedding: null,
            [("block_count", 16), ("embedding_length", 2048), ("attention.head_count", 32)], empty);

        Assert.That(() => GgufShape.Read(new MemoryStream(header), tensors: false), Throws.Nothing);
        Assert.That(GgufShape.Read(new MemoryStream(header), tensors: false), Is.Null);
    }

    private static GgufShape Shape(byte[] header, bool tensors) =>
        GgufShape.Read(new MemoryStream(header), tensors) ?? throw new AssertionException("the header was not read");
}

/// <summary>A GGUF v3 header as llama.cpp's converter writes it: general keys, the architecture's, then the tokenizer's
/// (a long string array, which a search never reads), then the tensors' infos.</summary>
internal static class Gguf
{
    internal static byte[] Header(string architecture, (long Width, long Rows, uint Type)? tokenEmbedding, params (string Key, uint Value)[] keys) =>
        Header(architecture, tokenEmbedding, keys, emptyArray: null);

    /// <summary>The same header; <paramref name="emptyArray"/>, when given, is an array of no numbers instead of that key's value.</summary>
    internal static byte[] Header(string architecture, (long Width, long Rows, uint Type)? tokenEmbedding, (string Key, uint Value)[] keys, string? emptyArray)
    {
        using var memory = new MemoryStream();
        using var writer = new BinaryWriter(memory);
        writer.Write("GGUF"u8);
        writer.Write(3u);
        writer.Write(tokenEmbedding is null ? 1UL : 2UL);
        writer.Write((ulong)(keys.Length + 3 + (emptyArray is not null && keys.All(k => k.Key != emptyArray) ? 1 : 0)));
        Text(writer, "general.architecture");
        writer.Write(8u);
        Text(writer, architecture);
        Text(writer, "general.alignment");
        writer.Write(4u);
        writer.Write(32u);
        foreach ((string key, uint value) in keys)
        {
            if (key == emptyArray)
            {
                continue;
            }

            Text(writer, architecture + "." + key);
            writer.Write(4u);
            writer.Write(value);
        }

        if (emptyArray is not null)
        {
            Text(writer, architecture + "." + emptyArray);
            writer.Write(9u);
            writer.Write(4u);
            writer.Write(0UL);
        }

        Text(writer, "tokenizer.ggml.tokens");
        writer.Write(9u);
        writer.Write(8u);
        writer.Write(3000UL);
        for (int token = 0; token < 3000; token++)
        {
            Text(writer, "token" + token);
        }

        Tensor(writer, "output_norm.weight", [2560], 0);
        if (tokenEmbedding is { } embedding)
        {
            Tensor(writer, "token_embd.weight", [(ulong)embedding.Width, (ulong)embedding.Rows], embedding.Type);
        }

        writer.Flush();
        return memory.ToArray();
    }

    private static void Tensor(BinaryWriter writer, string name, ulong[] shape, uint type)
    {
        Text(writer, name);
        writer.Write((uint)shape.Length);
        foreach (ulong dimension in shape)
        {
            writer.Write(dimension);
        }

        writer.Write(type);
        writer.Write(0UL);
    }

    private static void Text(BinaryWriter writer, string text)
    {
        byte[] bytes = Encoding.UTF8.GetBytes(text);
        writer.Write((ulong)bytes.Length);
        writer.Write(bytes);
    }
}
