using System.Diagnostics;
using System.Text.Json.Nodes;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// A mind relaunched after the last one was lost (MainWindowViewModel.InitializeMindAsync) gets back the conversation the
/// view shows, as the view's channel last kept it (FieldProductChannel, FieldSessionStore).
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
            string sessions = System.IO.Path.Combine(fake.DataRoot, "sessions");
            Assert.That(await ViewModelHarness.UntilAsync(() =>
                System.IO.Directory.Exists(sessions) && System.IO.Directory.GetFiles(sessions, "*.json").Length == 1), Is.True);

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
    public async Task ALostMindLeavesWhyItWasRelaunchedInTheProfileAndNothingOfThePerson()
    {
        // Feria 2026-10-27: two relaunches in a morning left no trace of their cause outside development.
        using var fake = new FakeMind();
        MainWindowViewModel viewModel = await ViewModelHarness.WithMindAsync();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            ViewModelHarness.AcceptTurns(viewModel);
            Assert.That((await view.SendAsync("POST", "/turn",
                new JsonObject { ["text"] = "abre el informe de Ñuñoa" })).Status, Is.EqualTo(200));
            foreach (int pid in fake.LiveProcesses)
            {
                using Process process = Process.GetProcessById(pid);
                process.Kill();
            }

            string log = System.IO.Path.Combine(fake.DataRoot, "diagnostics", MindRelaunches.FileName);
            Assert.That(await ViewModelHarness.UntilAsync(() => System.IO.File.Exists(log)), Is.True);
            string text = System.IO.File.ReadAllText(log);
            JsonObject line = JsonNode.Parse(text)!.AsObject();
            Assert.Multiple(() =>
            {
                Assert.That(line.Select(static field => field.Key),
                    Is.EquivalentTo(new[] { "utc", "cause", "request", "exitCode", "sinceStartSeconds" }));
                Assert.That((string?)line["cause"], Is.EqualTo(MindLoss.ProcessEnded));
                Assert.That(line["exitCode"], Is.Not.Null, "a killed mind has an exit code");
                Assert.That((double?)line["sinceStartSeconds"], Is.GreaterThanOrEqualTo(0));
                Assert.That(text, Does.Not.Contain("Ñuñoa").And.Not.Contain("informe"));
            });
        }
    }

    [Test]
    public void ARequestThatInvalidatedTheMindIsRecordedByItsTypeAndCause()
    {
        string folder = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "baxy-app-tests", Guid.NewGuid().ToString("N"));
        try
        {
            MindRelaunches.Record(new MindLoss("request_timeout", "turn.continue"), TimeSpan.FromSeconds(4012.34), folder);

            JsonNode? line = JsonNode.Parse(System.IO.File.ReadAllText(System.IO.Path.Combine(folder, MindRelaunches.FileName)));
            Assert.Multiple(() =>
            {
                Assert.That((string?)line?["cause"], Is.EqualTo("request_timeout"));
                Assert.That((string?)line?["request"], Is.EqualTo("turn.continue"));
                Assert.That(line?["exitCode"], Is.Null);
                Assert.That((double?)line?["sinceStartSeconds"], Is.EqualTo(4012.3));
            });
        }
        finally
        {
            if (System.IO.Directory.Exists(folder))
            {
                System.IO.Directory.Delete(folder, recursive: true);
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
