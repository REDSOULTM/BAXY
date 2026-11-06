using System.Text.Json.Nodes;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// Uso 95 (F9, uso real 2026-11-03 21:17 and 2026-11-04 12:06): the model server could not reserve its memory and the
/// mind failed to start three times in a row; a «hola» written in the 20 s between two relaunches ended its turn at once
/// (mind_unavailable), got no answer when the mind came up a minute later, and the person was told nothing. A message
/// written while the mind starts or is relaunched waits for it, told as a state, and is answered once it is up; one the
/// mind will not come for ends saying why, the lack of memory included when the server's log gave it.
/// </summary>
[TestFixture]
public sealed class MindComingTests
{
    private static JsonObject FailingStart(string cause) => new()
    {
        ["reply"] = new JsonObject
        {
            ["catalog.configure"] = new JsonObject
            {
                ["type"] = "error",
                ["startup"] = new JsonObject { ["cause"] = cause, ["exitCode"] = 3221226505 },
            },
        },
    };

    [Test]
    public async Task AMessageWrittenWhileTheMindIsRelaunchedIsAnsweredOnceItIsUp()
    {
        using var fake = new FakeMind();
        fake.Script(FailingStart("ram_insuficiente"));
        var viewModel = new MainWindowViewModel { Sound = static _ => { } };
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            await ViewModelHarness.StartMindAsync(viewModel);
            Assert.That(viewModel.IsMindReady, Is.False, "the first start failed");
            ViewModelHarness.AcceptTurns(viewModel);

            // Between two relaunches the mind is on its way: not a failure the view shows as the end of it.
            (_, JsonObject between) = await view.SendAsync("GET", "/agent/status");
            Assert.That((string?)between["failure"], Is.Null, "a relaunch is coming: the mind is starting, not gone");
            Assert.That((string?)between["failureCause"], Is.EqualTo("ram_insuficiente"), "why the last start failed");

            fake.Script(new JsonObject());
            Task<(int Status, JsonObject Body)> turn = view.SendAsync("POST", "/turn", new JsonObject { ["text"] = "hola" });
            Assert.That(await ViewModelHarness.UntilAsync(() => viewModel.IsAwaitingMind), Is.True,
                "the message waits for the mind instead of ending its turn");
            (_, JsonObject waiting) = await view.SendAsync("GET", "/agent/status");
            Assert.That((bool?)waiting["waitingForMind"], Is.True, "the view is told the message waits");
            Assert.That(turn.IsCompleted, Is.False);

            await ViewModelHarness.StartMindAsync(viewModel); // the relaunch the failed start scheduled

            (int status, _) = await turn.WaitAsync(TimeSpan.FromSeconds(30));
            Assert.Multiple(() =>
            {
                Assert.That(status, Is.EqualTo(200));
                Assert.That(fake.Seen, Does.Contain("turn.decide"), "the waiting message reached the model");
                Assert.That(viewModel.LastTurnFailure, Is.Null);
                Assert.That(viewModel.IsAwaitingMind, Is.False);
                Assert.That(viewModel.Messages.Last().Body, Is.EqualTo("hola"), "the model's answer is shown");
                Assert.That(viewModel.Messages.Last().IsUser, Is.False);
            });
        }
    }

    [Test]
    public async Task AMessageTheMindWillNotComeForEndsWithTheBreakdownAndItsCause()
    {
        using var fake = new FakeMind();
        fake.Script(FailingStart("ram_insuficiente"));
        var viewModel = new MainWindowViewModel { Sound = static _ => { } };
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            await ViewModelHarness.StartMindAsync(viewModel);
            ViewModelHarness.AcceptTurns(viewModel);
            Task<(int Status, JsonObject Body)> turn = view.SendAsync("POST", "/turn", new JsonObject { ["text"] = "hola" });
            Assert.That(await ViewModelHarness.UntilAsync(() => viewModel.IsAwaitingMind), Is.True);

            for (int start = 1; start < StartupRetries.IdenticalLimit; start++)
            {
                await ViewModelHarness.StartMindAsync(viewModel);
            }

            await turn.WaitAsync(TimeSpan.FromSeconds(30));
            (_, JsonObject agent) = await view.SendAsync("GET", "/agent/status");
            Assert.Multiple(() =>
            {
                Assert.That(fake.Seen, Does.Not.Contain("turn.decide"));
                Assert.That(viewModel.IsAwaitingMind, Is.False);
                Assert.That((string?)agent["failure"], Is.EqualTo(MainWindowViewModel.EngineUnavailable));
                Assert.That((string?)agent["failureCause"], Is.EqualTo("ram_insuficiente"),
                    "the breakdown says the PC lacked memory");
            });
        }
    }

    [Test]
    public async Task ALackOfMemorySaysHowMuchAsTheMindKnowsIt()
    {
        // uso-116 (N23): «falta tanta RAM». Neither figure is made up when the mind does not know it.
        using var fake = new FakeMind();
        JsonObject start = FailingStart("ram_insuficiente");
        JsonObject startup = start["reply"]!["catalog.configure"]!["startup"]!.AsObject();
        startup["needMb"] = 641;
        startup["freeMb"] = 512;
        fake.Script(start);
        var viewModel = new MainWindowViewModel { Sound = static _ => { } };
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            await ViewModelHarness.StartMindAsync(viewModel);
            (_, JsonObject agent) = await view.SendAsync("GET", "/agent/status");
            Assert.That(agent["failureMemory"]?.ToJsonString(), Is.EqualTo("""{"need_mb":641,"free_mb":512}"""));

            fake.Script(FailingStart("ram_insuficiente"));
            await ViewModelHarness.StartMindAsync(viewModel);
            (_, JsonObject without) = await view.SendAsync("GET", "/agent/status");
            Assert.That(without["failureMemory"], Is.Null);
        }
    }

    [Test]
    public async Task AMessageWithNoMindComingEndsAtOnce()
    {
        using var fake = new FakeMind();
        var viewModel = new MainWindowViewModel { Sound = static _ => { } };
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            // No start was ever made (the mind is not configured): nothing will come, nothing waits.
            ViewModelHarness.AcceptTurns(viewModel);
            (int status, _) = await view.SendAsync("POST", "/turn", new JsonObject { ["text"] = "hola" })
                .WaitAsync(TimeSpan.FromSeconds(10));

            Assert.Multiple(() =>
            {
                Assert.That(status, Is.EqualTo(200));
                Assert.That(viewModel.LastTurnFailure, Is.EqualTo("mind_unavailable"));
                Assert.That(viewModel.IsAwaitingMind, Is.False);
            });
        }
    }

    // Uso 95 (uso real 2026-11-04 13:19): the ear could not load for want of memory (556 MB left of the 1200 MB it needs)
    // and the view said «No hay micrófono»; the microphone was there.
    [Test]
    public async Task AnEarWaitingForMemoryIsSaidWithItsFiguresNotAsAMissingMicrophone()
    {
        using var fake = new FakeMind();
        fake.Script(new JsonObject
        {
            ["reply"] = new JsonObject
            {
                ["voice.status"] = new JsonObject
                {
                    ["type"] = "voice.status.result",
                    ["status"] = new JsonObject
                    {
                        ["available"] = false, ["input"] = false, ["stt"] = false, ["pending"] = false,
                        ["deferred"] = true, ["memory"] = new JsonObject { ["needMb"] = 1200, ["leftMb"] = 556 },
                    },
                },
            },
        });
        MainWindowViewModel viewModel = await ViewModelHarness.WithMindAsync();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            (_, JsonObject voice) = await view.SendAsync("GET", "/voice/status");
            Assert.Multiple(() =>
            {
                Assert.That((string?)voice["last_error"], Is.EqualTo("voice_waiting_memory"));
                Assert.That((int?)voice["waiting_memory"]?["need_mb"], Is.EqualTo(1200));
                Assert.That((int?)voice["waiting_memory"]?["left_mb"], Is.EqualTo(556));
            });
        }
    }
}
