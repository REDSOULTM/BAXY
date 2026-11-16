using System.IO;
using System.Text;
using System.Text.Json.Nodes;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// MOD5 (MOD2 §1, path a): a GGUF of the person's own in BAXY's engine, chosen in Settings → Model. Before it the App took
/// the stock model with its SHA-256, or the tuned one, and another file only through BAXY_MIND_LLM_GGUF set by hand. Now
/// the choice is kept, taken at a start when the file is a GGUF whose template takes tools and whose context holds BAXY's
/// smallest profile, its projector only when it fits the model, and a start with it that fails goes back to the stock
/// model with the cause said.
/// </summary>
[TestFixture]
[NonParallelizable]
public sealed class LocalModelTests
{
    private const string Stock = @"C:\BAXY\models\Qwen3.5-4B-Q4_K_M.gguf";
    private const string StockSha256 = "00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4";
    private const string Projector = "BAXY_MIND_MMPROJ";
    private const int Esencial = 30_071;
    private string _root = "";
    private string _stockProjector = "";

    [SetUp]
    public void SetUp()
    {
        _root = Directory.CreateTempSubdirectory("baxy-local-model-").FullName;
        _stockProjector = Path.Combine(_root, "stock-mmproj.gguf");
        WriteGguf(_stockProjector, "clip", [("clip.vision.projection_dim", 2560u)], []);
        Environment.SetEnvironmentVariable(TunedModel.GgufVariable, Stock);
        Environment.SetEnvironmentVariable(MindRuntimeDiscovery.GgufSha256Variable, StockSha256);
        Environment.SetEnvironmentVariable(Projector, _stockProjector);
    }

    [TearDown]
    public void TearDown()
    {
        Environment.SetEnvironmentVariable(TunedModel.GgufVariable, null);
        Environment.SetEnvironmentVariable(MindRuntimeDiscovery.GgufSha256Variable, null);
        Environment.SetEnvironmentVariable(Projector, null);
        Directory.Delete(_root, recursive: true);
    }

    [Test]
    public void WithNothingChosenTheStartIsTheRegisteredOne()
    {
        var local = new LocalModel(_root, () => Esencial);

        local.Start();

        Assert.Multiple(() =>
        {
            Assert.That(local.Active, Is.False);
            Assert.That(local.Problem, Is.Null);
            Assert.That(Environment.GetEnvironmentVariable(TunedModel.GgufVariable), Is.EqualTo(Stock));
            Assert.That(Environment.GetEnvironmentVariable(MindRuntimeDiscovery.GgufSha256Variable), Is.EqualTo(StockSha256));
            Assert.That(Environment.GetEnvironmentVariable(Projector), Is.EqualTo(_stockProjector));
        });
    }

    [Test]
    public void AChosenGgufWithToolsIsTheModelOfTheNextStartAndItsHashGoes()
    {
        string model = Model("Qwen3.5-9B-Q4_K_M.gguf", embedding: 4096);
        var local = new LocalModel(_root, () => Esencial);

        Assert.That(local.Apply(new JsonObject { ["path"] = model, ["use"] = true }), Is.Null);
        Assert.That(local.NeedsSwitch, Is.False, "no mind has started yet");
        local.Start();

        Assert.Multiple(() =>
        {
            Assert.That(local.Active, Is.True);
            Assert.That(Environment.GetEnvironmentVariable(TunedModel.GgufVariable), Is.EqualTo(model));
            Assert.That(Environment.GetEnvironmentVariable(MindRuntimeDiscovery.GgufSha256Variable), Is.Null);
            // the stock model's projector is 2,560 wide: not this model's 4,096, so vision is off and said
            Assert.That(Environment.GetEnvironmentVariable(Projector), Is.Null);
            Assert.That(local.Sees, Is.False);
            Assert.That((bool?)local.Json()["sees"], Is.False);
        });

        local.Stop();
        Assert.Multiple(() =>
        {
            Assert.That(Environment.GetEnvironmentVariable(TunedModel.GgufVariable), Is.EqualTo(Stock));
            Assert.That(Environment.GetEnvironmentVariable(MindRuntimeDiscovery.GgufSha256Variable), Is.EqualTo(StockSha256));
            Assert.That(Environment.GetEnvironmentVariable(Projector), Is.EqualTo(_stockProjector));
        });
    }

    [Test]
    public void TheProjectorGoesWithTheModelOnlyWhenItIsAsWideAsItsEmbedding()
    {
        // the same width as the stock model's projector: it fits
        string same = Model("Qwen3.5-2B-Q4_K_M.gguf", embedding: 2560);
        Assert.That(LocalModel.FittingProjector(same, _stockProjector), Is.EqualTo(_stockProjector));

        // a model of its own folder with its own projector beside it
        string folder = Directory.CreateDirectory(Path.Combine(_root, "otro")).FullName;
        string wide = Model(Path.Combine("otro", "modelo.gguf"), embedding: 4096);
        string beside = Path.Combine(folder, "mmproj-F16.gguf");
        WriteGguf(beside, "clip", [("clip.vision.projection_dim", 4096u)], []);
        Assert.That(LocalModel.FittingProjector(wide, _stockProjector), Is.EqualTo(beside));

        // none that fits
        File.Delete(beside);
        Assert.That(LocalModel.FittingProjector(wide, _stockProjector), Is.Null);
    }

    [TestCase("missing", "local_model_missing")]
    [TestCase("not-gguf", "local_model_not_gguf")]
    [TestCase("no-tools", "local_model_no_tools")]
    [TestCase("short", "local_model_short_context")]
    public void AFileThatCannotBeBaxysModelIsRefusedWithItsCause(string kind, string code)
    {
        string path = Path.Combine(_root, kind + ".gguf");
        if (kind == "not-gguf")
        {
            File.WriteAllText(path, "not a model");
        }
        else if (kind == "no-tools")
        {
            path = Model(kind + ".gguf", embedding: 3072, template: "{{ messages }}");
        }
        else if (kind == "short")
        {
            path = Model(kind + ".gguf", embedding: 3072, context: 8192);
        }

        var local = new LocalModel(_root, () => Esencial);

        Assert.That(local.Apply(new JsonObject { ["path"] = path, ["use"] = true }), Is.EqualTo(code));
        Assert.That((bool?)local.Json()["use"], Is.False, "a refused choice is not kept as one");
    }

    [Test]
    public void AChosenFileThatWentAwayLeavesTheStockModelAndSaysWhy()
    {
        string model = Model("modelo.gguf", embedding: 3072);
        var local = new LocalModel(_root, () => Esencial);
        _ = local.Apply(new JsonObject { ["path"] = model, ["use"] = true });
        File.Delete(model);

        local.Start();

        Assert.Multiple(() =>
        {
            Assert.That(local.Active, Is.False);
            Assert.That(local.Problem, Is.EqualTo("local_model_missing"));
            Assert.That(Environment.GetEnvironmentVariable(TunedModel.GgufVariable), Is.EqualTo(Stock));
        });
    }

    [Test]
    public void AStartThatFailsOnItGoesBackToTheStockModelUntilThePersonChoosesAgain()
    {
        string model = Model("modelo.gguf", embedding: 3072);
        var local = new LocalModel(_root, () => Esencial);
        _ = local.Apply(new JsonObject { ["path"] = model, ["use"] = true });
        local.Start();

        Assert.That(local.FellBack("vram_insuficiente"), Is.True);
        Assert.Multiple(() =>
        {
            Assert.That(local.Active, Is.False);
            Assert.That(local.Problem, Is.EqualTo("local_model_failed"));
            Assert.That(local.FailedCause, Is.EqualTo("vram_insuficiente"));
            Assert.That(Environment.GetEnvironmentVariable(TunedModel.GgufVariable), Is.EqualTo(Stock));
        });

        // the stock model's start that follows does not try the same file again
        local.Start();
        Assert.Multiple(() =>
        {
            Assert.That(local.Active, Is.False);
            Assert.That(local.Problem, Is.EqualTo("local_model_failed"));
            Assert.That(Environment.GetEnvironmentVariable(TunedModel.GgufVariable), Is.EqualTo(Stock));
            Assert.That(local.FellBack("otra"), Is.False, "a start on the stock model is no fall back");
        });

        // the person chooses again (another file): it is tried
        string other = Model("otro.gguf", embedding: 3072);
        _ = local.Apply(new JsonObject { ["path"] = other, ["use"] = true });
        Assert.That(local.NeedsSwitch, Is.True);
        local.Start();
        Assert.That(Environment.GetEnvironmentVariable(TunedModel.GgufVariable), Is.EqualTo(other));
    }

    [Test]
    public void ChoosingItAgainAfterAFailedStartTriesTheSameFileAgain()
    {
        // REV (blind review 2): «Puedes elegirlo otra vez» has to be true for the same file too.
        string model = Model("modelo.gguf", embedding: 3072);
        var local = new LocalModel(_root, () => Esencial);
        _ = local.Apply(new JsonObject { ["path"] = model, ["use"] = true });
        local.Start();
        Assert.That(local.FellBack("tiempo"), Is.True);
        local.Start();
        Assert.That(local.Active, Is.False);

        Assert.That(local.Apply(new JsonObject { ["use"] = true }), Is.Null);
        Assert.That(local.NeedsSwitch, Is.True, "the mind is switched to try it");
        local.Start();

        Assert.Multiple(() =>
        {
            Assert.That(local.Active, Is.True);
            Assert.That(local.Problem, Is.Null);
            Assert.That(Environment.GetEnvironmentVariable(TunedModel.GgufVariable), Is.EqualTo(model));
            Assert.That(local.NeedsSwitch, Is.False);
        });
    }

    [Test]
    public void AStartThatIsNoSwitchKeepsTheModelsOwnPiecesNotTheStockProjector()
    {
        // REV (blind review 1): a lost mind's restart finds the stock projector put back (ApplyPieces fills what is empty).
        string model = Model("Qwen3.5-9B-Q4_K_M.gguf", embedding: 4096);
        var local = new LocalModel(_root, () => Esencial);
        _ = local.Apply(new JsonObject { ["path"] = model, ["use"] = true });
        local.Start();
        Assert.That(Environment.GetEnvironmentVariable(Projector), Is.Null);

        Environment.SetEnvironmentVariable(Projector, _stockProjector);
        local.Start();

        Assert.Multiple(() =>
        {
            Assert.That(Environment.GetEnvironmentVariable(Projector), Is.Null, "not a projector of another width");
            Assert.That(Environment.GetEnvironmentVariable(TunedModel.GgufVariable), Is.EqualTo(model));
        });
        local.Stop();
        Assert.That(Environment.GetEnvironmentVariable(Projector), Is.EqualTo(_stockProjector));
    }

    [Test]
    public void AConfigurationOfOtherTypesIsNoChoiceAndThrowsNothing()
    {
        // REV (blind review 8): a hand-edited file at a start.
        Directory.CreateDirectory(Path.Combine(_root, "local-model"));
        File.WriteAllText(Path.Combine(_root, "local-model", "config.json"), new JsonObject { ["path"] = 3, ["use"] = "yes" }.ToJsonString());
        var local = new LocalModel(_root, () => Esencial);

        Assert.That(() => local.Start(), Throws.Nothing);
        Assert.Multiple(() =>
        {
            Assert.That(local.Chosen, Is.False);
            Assert.That((bool?)local.Json()["use"], Is.False);
            Assert.That(local.Apply(new JsonObject { ["path"] = 7, ["use"] = "no" }), Is.EqualTo("local_model_missing"));
            Assert.That(Environment.GetEnvironmentVariable(TunedModel.GgufVariable), Is.EqualTo(Stock));
        });
    }

    [Test]
    public async Task TurningOnTheTunedModelOrAnotherOneTurnsThePersonsGgufOff()
    {
        // REV (blind review 3): one model at a time.
        using var fake = new FakeMind();
        string model = Model("modelo.gguf", embedding: 3072);
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        {
            Assert.That(viewModel.LocalModelState.Apply(new JsonObject { ["path"] = model, ["use"] = true }), Is.Null);
            viewModel.LocalModelGivesWay(new JsonObject { ["use"] = false });
            Assert.That(viewModel.LocalModelState.Chosen, Is.True, "turning the tuned one off changes nothing");

            viewModel.LocalModelGivesWay(new JsonObject { ["use"] = true });
            Assert.That(viewModel.LocalModelState.Chosen, Is.False);

            Assert.That(viewModel.LocalModelState.Apply(new JsonObject { ["use"] = true }), Is.Null);
            viewModel.LocalModelGivesWay(new JsonObject { ["enabled"] = true, ["provider"] = "local" });
            Assert.That(viewModel.LocalModelState.Chosen, Is.False);
            Assert.That((string?)viewModel.LocalModelState.Json()["path"], Is.EqualTo(model), "the file stays for the next time");
        }
    }

    [Test]
    public void TurningItOffGoesBackToTheStockModelOnTheNextStart()
    {
        string model = Model("modelo.gguf", embedding: 3072);
        var local = new LocalModel(_root, () => Esencial);
        _ = local.Apply(new JsonObject { ["path"] = model, ["use"] = true });
        local.Start();

        Assert.That(local.Apply(new JsonObject { ["use"] = false }), Is.Null);
        Assert.That(local.NeedsSwitch, Is.True);
        local.Start();

        Assert.Multiple(() =>
        {
            Assert.That(local.Active, Is.False);
            Assert.That(Environment.GetEnvironmentVariable(TunedModel.GgufVariable), Is.EqualTo(Stock));
            Assert.That((string?)local.Json()["path"], Is.EqualTo(model), "the file is kept for the next time");
        });
    }

    [Test]
    public async Task AMindThatDoesNotComeUpOnThePersonsGgufComesUpOnTheStockModelAndSaysWhy()
    {
        using var fake = new FakeMind();
        string stock = Environment.GetEnvironmentVariable(TunedModel.GgufVariable) ?? "";
        string model = Model("modelo.gguf", embedding: 3072);
        Directory.CreateDirectory(Path.Combine(fake.DataRoot, "local-model"));
        File.WriteAllText(Path.Combine(fake.DataRoot, "local-model", "config.json"),
            new JsonObject { ["path"] = model, ["use"] = true }.ToJsonString());
        // The first start (on the person's file) fails as a model that does not come up; the next one is ready.
        fake.Script(new JsonObject
        {
            ["replies"] = new JsonObject
            {
                ["catalog.configure"] = new JsonArray(
                    new JsonObject { ["type"] = "error", ["startup"] = new JsonObject { ["cause"] = "modelo_ausente" } },
                    new JsonObject { ["type"] = "catalog.ready", ["count"] = 0 }),
            },
        });
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            await ViewModelHarness.StartMindAsync(viewModel);
            Assert.Multiple(() =>
            {
                Assert.That(viewModel.LocalModelProblem, Is.EqualTo("local_model_failed"));
                Assert.That(viewModel.Failure, Is.Not.EqualTo(MainWindowViewModel.EngineUnavailable), "no breakdown: the stock model comes next");
                Assert.That(Environment.GetEnvironmentVariable(TunedModel.GgufVariable), Is.EqualTo(stock));
            });

            // the start that follows at once (RetryMindAfterAsync, with the engine up)
            await ViewModelHarness.StartMindAsync(viewModel);
            (int status, JsonObject state) = await view.SendAsync("GET", "/settings/local-model");

            Assert.Multiple(() =>
            {
                Assert.That(viewModel.IsMindReady, Is.True);
                Assert.That(File.ReadAllLines(Path.Combine(fake.Folder, "models.log")), Is.EqualTo(new[] { model, stock }));
                Assert.That(status, Is.EqualTo(200));
                Assert.That((string?)state["problem"], Is.EqualTo("local_model_failed"));
                Assert.That((string?)state["failedCause"], Is.EqualTo("modelo_ausente"));
                Assert.That((bool?)state["use"], Is.True, "the person's choice stays: they may try again");
            });
        }
    }

    private string Model(string name, long embedding, string template = "{%- if tools %}{{ tools }}{%- endif %}", uint context = 131072)
    {
        string path = Path.Combine(_root, name);
        WriteGguf(path, "llama",
            [("llama.block_count", 28u), ("llama.context_length", context), ("llama.embedding_length", (uint)embedding),
                ("llama.feed_forward_length", 8192u), ("llama.attention.head_count", 24u), ("llama.attention.head_count_kv", 8u)],
            [("tokenizer.chat_template", template)]);
        return path;
    }

    /// <summary>A GGUF header (the GGUF specification: magic, version, counts, key-value pairs) of u32 and text keys, no tensors.</summary>
    private static void WriteGguf(string path, string architecture, (string Key, uint Value)[] numbers, (string Key, string Value)[] texts)
    {
        using var file = File.Create(path);
        using var writer = new BinaryWriter(file);
        writer.Write("GGUF"u8);
        writer.Write(3u);
        writer.Write(0UL);
        writer.Write((ulong)(numbers.Length + texts.Length + 1));
        Text(writer, "general.architecture");
        writer.Write(8u);
        Text(writer, architecture);
        foreach ((string key, uint value) in numbers)
        {
            Text(writer, key);
            writer.Write(4u);
            writer.Write(value);
        }

        foreach ((string key, string value) in texts)
        {
            Text(writer, key);
            writer.Write(8u);
            Text(writer, value);
        }
    }

    private static void Text(BinaryWriter writer, string value)
    {
        byte[] bytes = Encoding.UTF8.GetBytes(value);
        writer.Write((ulong)bytes.Length);
        writer.Write(bytes);
    }
}
