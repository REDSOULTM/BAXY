using System.IO;
using System.Text.Json.Nodes;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// PRV1 (revisión de privacidad 2026-11-09, PRIV-02): what BAXY left on the disk in clear text and nothing of the product
/// named: the conversation log, the mind's trace and the screens it captured. The person who deletes everything
/// deletes them too, file by file; a captured screen does not outlive the request that took it; and the product's
/// conversation log keeps no words.
/// </summary>
[TestFixture]
[NonParallelizable]
public sealed class LeftInClearTests
{
    private const System.Reflection.BindingFlags Private =
        System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic;

    // The two ways the person deletes everything: every conversation (the view's DELETE /sessions) and memory's «olvidar
    // todo» (as the loop tells it, NativeTurnLoop.Host.ForgotEverything).
    [TestCase("conversations")]
    [TestCase("forget")]
    public async Task DeletingEverythingRemovesTheLogsAndTheCapturesFileByFile(string way)
    {
        using var fake = new FakeMind();
        MainWindowViewModel viewModel = await WithCapturesAsync();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            string root = MemoryOperationProtector.ResolveDataRoot();
            string log = Path.Combine(root, "conversation", "conversation.v1.jsonl");
            Directory.CreateDirectory(Path.GetDirectoryName(log)!);
            File.WriteAllText(log, "{\"text\":\"mi clave es tulipán\"}\n");
            File.WriteAllText(log + BoundedJsonlFile.ArchiveSuffix, "{\"text\":\"vivo en Viña del Mar\"}\n");
            string[] captures = Captures(root);
            // The note of a playback that was not verified names what the person asked to play: it goes too.
            string note = Path.Combine(root, "captures", "streaming-playback-rejections.jsonl");
            File.WriteAllText(note, "{\"title\":\"la casa del lago\"}\n");
            string other = Path.Combine(root, "captures", "notas.jsonl");
            File.WriteAllText(other, "{}\n");

            if (way == "conversations")
            {
                Assert.That((await view.SendAsync("DELETE", "/sessions", new JsonObject { ["scope"] = "all" })).Status,
                    Is.EqualTo(200));
            }
            else
            {
                var loop = (NativeTurnLoop)typeof(MainWindowViewModel).GetField("_loop", Private)!.GetValue(viewModel)!;
                ((NativeTurnLoop.Host)typeof(NativeTurnLoop).GetField("_host", Private)!.GetValue(loop)!).ForgotEverything!();
            }

            Assert.Multiple(() =>
            {
                Assert.That(File.Exists(log), Is.False, "conversation.v1.jsonl stayed");
                Assert.That(File.Exists(log + BoundedJsonlFile.ArchiveSuffix), Is.False, "conversation.v1.jsonl.1 stayed");
                foreach (string capture in captures)
                {
                    Assert.That(File.Exists(capture), Is.False, Path.GetFileName(capture) + " stayed");
                }

                Assert.That(File.Exists(note), Is.False, "streaming-playback-rejections.jsonl stayed");
                Assert.That(File.Exists(other), Is.True, "a file that is no capture went with them");
            });
            // turns.jsonl and turns.jsonl.1 are the mind's: it is asked to remove them (tests/test_mind_trace.py and
            // tests/test_mind_w8_audit.py hold that it does, file by file).
            Assert.That(await fake.WaitSeenAsync("trace.forget"), Is.True, "the mind was not asked to forget its trace");
        }
    }

    [Test]
    public async Task ACapturedScreenIsGoneWhenTheTurnThatTookItEnds()
    {
        using var fake = new FakeMind();
        MainWindowViewModel viewModel = await WithCapturesAsync();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            ViewModelHarness.AcceptTurns(viewModel);
            string[] captures = Captures(MemoryOperationProtector.ResolveDataRoot());

            await TalkAsync(view, viewModel, "¿qué dice ahí?");

            Assert.That(captures.Where(File.Exists), Is.Empty, "a captured screen outlived its turn");
        }
    }

    // A call that waits for the person's «sí» may be the one that reads the capture: it stays while one waits.
    [Test]
    public async Task ACapturedScreenStaysWhileACallWaitsForTheYesAndGoesOnceNoneDoes()
    {
        using var fake = new FakeMind();
        MainWindowViewModel viewModel = await WithCapturesAsync();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            ViewModelHarness.AcceptTurns(viewModel);
            string[] captures = Captures(MemoryOperationProtector.ResolveDataRoot());
            WaitingCalls.Ask(viewModel);

            // What the end of a turn or of a heartbeat runs (MainWindowViewModel.RunGatedTurnAsync, RunBeatAsync).
            typeof(MainWindowViewModel).GetMethod("ClearCapturesNoCallWaitsFor", Private)!.Invoke(viewModel, null);

            Assert.That(viewModel.HasPendingConfirmation, Is.True);
            Assert.That(captures.All(File.Exists), Is.True, "the capture went while a call waited for the yes");

            Assert.That(await viewModel.StartNewUiSessionAsync(CancellationToken.None), Is.True);
            await TalkAsync(view, viewModel, "déjalo");

            Assert.That(viewModel.HasPendingConfirmation, Is.False);
            Assert.That(captures.Where(File.Exists), Is.Empty);
        }
    }

    [Test]
    public async Task ClosingBaxyLeavesNoCapturedScreen()
    {
        using var fake = new FakeMind();
        MainWindowViewModel viewModel = await WithCapturesAsync();
        string[] captures = Captures(MemoryOperationProtector.ResolveDataRoot());

        await viewModel.DisposeAsync();

        Assert.That(captures.Where(File.Exists), Is.Empty);
    }

    [Test]
    public async Task TheProductsModelKeepsThisPcsCaptureFolderAndATestsModelActsOnNone()
    {
        using var fake = new FakeMind();
        await using MainWindowViewModel product = MainWindowViewModel.ForThisPc();
        await using var bare = new MainWindowViewModel();
        string[] captures = Captures(MemoryOperationProtector.ResolveDataRoot());

        Assert.That(product.CapturesDirectory,
            Is.EqualTo(Path.Combine(MemoryOperationProtector.ResolveDataRoot(), "captures")));
        Assert.That(bare.CapturesDirectory, Is.Null);
        bare.ClearCaptures();
        Assert.That(captures.All(File.Exists), Is.True);
        product.ClearCaptures();
        Assert.That(captures.Where(File.Exists), Is.Empty);
    }

    [Test]
    public void TheProductsLogKeepsNoWordsUnlessThePcsOwnerAsksForThem()
    {
        string folder = Path.Combine(Path.GetTempPath(), "baxy-app-tests", Guid.NewGuid().ToString("N"));
        try
        {
            var log = new ConversationLog(folder, keepsWords: false);
            DateTimeOffset asked = DateTimeOffset.Now;
            log.Append(new ConversationMessage("Tú", "mi clave es tulipán", true, asked));
            log.Append(new ConversationMessage("BAXY", "Anotado: tulipán.", false, asked.AddSeconds(2), "modelo"));

            string written = File.ReadAllText(Path.Combine(folder, "conversation.v1.jsonl"));
            JsonObject answer = (JsonObject)JsonNode.Parse(written.Split('\n', StringSplitOptions.RemoveEmptyEntries)[1])!;
            Assert.Multiple(() =>
            {
                Assert.That(written, Does.Not.Contain("tulip").And.Not.Contain("clave").And.Not.Contain("\"text\""));
                Assert.That((string?)answer["role"], Is.EqualTo("assistant"));
                Assert.That((string?)answer["route"], Is.EqualTo("modelo"));
                Assert.That((long?)answer["latency_ms"], Is.EqualTo(2000));
                Assert.That(ConversationLog.KeepsWords(null), Is.False);
                Assert.That(ConversationLog.KeepsWords(string.Empty), Is.False);
                Assert.That(ConversationLog.KeepsWords("0"), Is.False);
                // UNI1 (REV8 P3): «true» is a usual yes; with it the earlier logs were removed although the owner meant to keep.
                Assert.That(ConversationLog.KeepsWords("true"), Is.True);
                Assert.That(ConversationLog.KeepsWords("false"), Is.False);
                Assert.That(ConversationLog.KeepsWords(" 1 "), Is.True);
            });
        }
        finally
        {
            if (Directory.Exists(folder))
            {
                Directory.Delete(folder, recursive: true);
            }
        }
    }

    // The view model as the product builds it (MainWindowViewModel.ForThisPc), silent, with the fake mind up.
    private static async Task<MainWindowViewModel> WithCapturesAsync()
    {
        var viewModel = new MainWindowViewModel
        {
            Sound = static _ => { },
            CapturesDirectory = Path.Combine(MemoryOperationProtector.ResolveDataRoot(), "captures"),
        };
        await ViewModelHarness.StartMindAsync(viewModel);
        Assert.That(viewModel.IsMindReady, Is.True);
        return viewModel;
    }

    // Two stored captures and the temporary of one that was being written, as WindowsScreenshotProvider names them.
    private static string[] Captures(string root)
    {
        string folder = Path.Combine(root, "captures");
        Directory.CreateDirectory(folder);
        string[] files =
        [
            Path.Combine(folder, "capture_" + Guid.NewGuid().ToString("N") + ".bmp"),
            Path.Combine(folder, "capture_" + Guid.NewGuid().ToString("N") + ".bmp"),
            Path.Combine(folder, ".capture_" + Guid.NewGuid().ToString("N") + ".tmp"),
        ];
        foreach (string file in files)
        {
            File.WriteAllBytes(file, [(byte)'B', (byte)'M']);
        }

        return files;
    }

    private static async Task TalkAsync(ChannelHarness view, MainWindowViewModel viewModel, string text)
    {
        int before = viewModel.Messages.Count;
        Assert.That((await view.SendAsync("POST", "/turn", new JsonObject { ["text"] = text })).Status, Is.EqualTo(200));
        Assert.That(await ViewModelHarness.UntilAsync(() => !viewModel.IsBusy && viewModel.Messages.Count >= before + 2),
            Is.True);
    }
}
