using System.Diagnostics;
using System.IO;
using System.Text.Json.Nodes;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// A mind relaunched after the last one was lost (MainWindowViewModel.InitializeMindAsync) gets back the conversation the
/// view shows, as the view's channel last kept it (FieldProductChannel, FieldSessionStore), and why it was relaunched is
/// left in the profile (MindRestarts), never what the person said.
/// </summary>
[TestFixture]
public sealed class MindRelaunchTests
{
    [Test]
    public async Task ARelaunchedMindGetsTheShownConversationBack()
    {
        using var fake = new FakeMind();
        fake.Script(new JsonObject
        {
            ["reply"] = new JsonObject
            {
                ["session.export"] = new JsonObject
                {
                    ["type"] = "session.exported",
                    ["conversation"] = new JsonArray(
                        new JsonObject { ["role"] = "user", ["content"] = "hola" },
                        new JsonObject { ["role"] = "assistant", ["content"] = "hola" }),
                },
            },
        });
        MainWindowViewModel viewModel = await ViewModelHarness.WithMindAsync();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            ViewModelHarness.AcceptTurns(viewModel);
            Assert.That((await view.SendAsync("POST", "/turn", new JsonObject { ["text"] = "hola" })).Status, Is.EqualTo(200));
            // The turn's end keeps the conversation, the mind's own included.
            Assert.That(await fake.WaitSeenAsync("session.export"), Is.True);
            string sessions = Path.Combine(fake.DataRoot, "sessions");
            Assert.That(await ViewModelHarness.UntilAsync(() =>
                Directory.Exists(sessions) && Directory.GetFiles(sessions, "*.json").Length == 1), Is.True);

            foreach (int pid in fake.LiveProcesses)
            {
                using Process process = Process.GetProcessById(pid);
                process.Kill();
            }

            Assert.That(await ViewModelHarness.UntilAsync(() => !viewModel.IsMindReady), Is.True);
            await ViewModelHarness.StartMindAsync(viewModel);

            Assert.That(viewModel.IsMindReady, Is.True);
            Assert.That(fake.Seen.Count(static s => s == "session.load"), Is.EqualTo(1),
                "the relaunched mind does not know the conversation the view shows");
        }
    }

    [Test]
    public async Task ALostMindLeavesWhyItEndedInTheProfileAndNothingOfThePerson()
    {
        // Feria 2026-10-27: three new minds in a morning left no trace of their cause outside development.
        using var fake = new FakeMind();
        MainWindowViewModel viewModel = await ViewModelHarness.WithMindAsync();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            ViewModelHarness.AcceptTurns(viewModel);
            Assert.That((await view.SendAsync("POST", "/turn",
                new JsonObject { ["text"] = "abre el informe secreto" })).Status, Is.EqualTo(200));
            foreach (int pid in fake.LiveProcesses)
            {
                using Process process = Process.GetProcessById(pid);
                process.Kill();
            }

            string log = Path.Combine(fake.DataRoot, "diagnostics", MindRestarts.FileName);
            IReadOnlyList<JsonObject> lines = await LinesAsync(log);
            Assert.That(lines, Has.Count.EqualTo(1), "one line per mind that ended");
            JsonObject line = lines[0];
            Assert.Multiple(() =>
            {
                Assert.That(line.Select(static field => field.Key),
                    Is.EquivalentTo(new[] { "utc", "cause", "request", "exitCode", "runningSeconds" }));
                Assert.That((string?)line["cause"], Is.EqualTo(MindLoss.ProcessEnded));
                Assert.That(line["exitCode"], Is.Not.Null, "a killed mind has an exit code");
                Assert.That((double?)line["runningSeconds"], Is.GreaterThanOrEqualTo(0));
                Assert.That(File.ReadAllText(log), Does.Not.Contain("informe").And.Not.Contain("secreto"));
            });
        }
    }

    [Test]
    public async Task AStartThatFailedIsRecordedWithItsCause()
    {
        using var fake = new FakeMind();
        fake.Script(new JsonObject
        {
            ["reply"] = new JsonObject
            {
                ["catalog.configure"] = new JsonObject
                {
                    ["type"] = "error",
                    ["startup"] = new JsonObject { ["cause"] = "proceso_salio", ["exitCode"] = 70 },
                },
            },
        });
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        {
            await ViewModelHarness.StartMindAsync(viewModel);

            IReadOnlyList<JsonObject> lines =
                await LinesAsync(Path.Combine(fake.DataRoot, "diagnostics", MindRestarts.FileName));
            Assert.That(viewModel.IsMindReady, Is.False);
            Assert.That(lines.Select(static line => (string?)line["cause"]), Is.EqualTo(new[] { "startup.proceso_salio.70" }));
        }
    }

    [Test]
    public void ARequestThatInvalidatedTheMindIsRecordedByItsTypeAndCause()
    {
        string folder = Path.Combine(Path.GetTempPath(), "baxy-app-tests", Guid.NewGuid().ToString("N"));
        try
        {
            MindRestarts.Record(new MindLoss("request_timeout", "turn.continue"), TimeSpan.FromSeconds(4012.34), folder);

            JsonNode? line = JsonNode.Parse(File.ReadAllText(Path.Combine(folder, MindRestarts.FileName)));
            Assert.Multiple(() =>
            {
                Assert.That((string?)line?["cause"], Is.EqualTo("request_timeout"));
                Assert.That((string?)line?["request"], Is.EqualTo("turn.continue"));
                Assert.That(line?["exitCode"], Is.Null);
                Assert.That((double?)line?["runningSeconds"], Is.EqualTo(4012.3));
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

    [Test]
    public async Task AMindStartedForANewConversationLoadsNothing()
    {
        using var fake = new FakeMind();
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            await ViewModelHarness.StartMindAsync(viewModel);

            Assert.That(viewModel.IsMindReady, Is.True);
            Assert.That(fake.Seen, Does.Not.Contain("session.load"));
        }
    }

    [Test]
    public async Task AMindLostMidTurnLeavesTheLastKeptConversationForTheNextOne()
    {
        using var fake = new FakeMind();
        fake.Script(Exporting());
        MainWindowViewModel viewModel = await ViewModelHarness.WithMindAsync();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            ViewModelHarness.AcceptTurns(viewModel);
            Assert.That((await view.SendAsync("POST", "/turn", new JsonObject { ["text"] = "hola" })).Status, Is.EqualTo(200));
            Assert.That(await fake.WaitSeenAsync("session.export"), Is.True);
            Assert.That(await ViewModelHarness.UntilAsync(() => viewModel.KeptConversation?.Invoke() is { Count: > 0 }), Is.True);

            // The next turn loses its mind halfway: its end keeps what the view shows, and the mind's conversation
            // as it was last kept, since the lost mind exports nothing.
            JsonObject holding = Exporting();
            holding["hold"] = new JsonObject { ["turn.decide"] = "never" };
            fake.Script(holding);
            Task<(int Status, JsonObject Body)> turn = view.SendAsync("POST", "/turn", new JsonObject { ["text"] = "otra" });
            Assert.That(await fake.WaitSeenAsync("turn.decide", count: 2), Is.True);
            foreach (int pid in fake.LiveProcesses)
            {
                using Process process = Process.GetProcessById(pid);
                process.Kill();
            }

            await turn;
            // Every save of the conversation says so to the view (its surfaces): the lost turn's is the second.
            Assert.That(await ViewModelHarness.UntilAsync(() =>
                view.Sink.Events.Count(static e => (string?)e["type"] == "surfaces") == 2 && !viewModel.IsMindReady), Is.True);
            fake.Script(Exporting());
            await ViewModelHarness.StartMindAsync(viewModel);

            Assert.That(viewModel.IsMindReady, Is.True);
            Assert.That(fake.Seen.Count(static s => s == "session.load"), Is.EqualTo(1),
                "the save after the lost turn dropped the kept conversation");
        }
    }

    // The record's lines once its first one is whole (it may be read while being written).
    private static async Task<IReadOnlyList<JsonObject>> LinesAsync(string log)
    {
        string text = string.Empty;
        await ViewModelHarness.UntilAsync(() =>
        {
            try
            {
                using var stream = new FileStream(log, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete);
                using var reader = new StreamReader(stream);
                text = reader.ReadToEnd();
                return text.EndsWith('\n');
            }
            catch (IOException)
            {
                return false;
            }
        });
        return [.. text.Split('\n', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
            .Select(static line => JsonNode.Parse(line)!.AsObject())];
    }

    private static JsonObject Exporting() => new()
    {
        ["reply"] = new JsonObject
        {
            ["session.export"] = new JsonObject
            {
                ["type"] = "session.exported",
                ["conversation"] = new JsonArray(
                    new JsonObject { ["role"] = "user", ["content"] = "hola" },
                    new JsonObject { ["role"] = "assistant", ["content"] = "hola" }),
            },
        },
    };
}
