using System.Diagnostics;
using System.Reflection;
using System.Text.Json.Nodes;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// Al máximo, flujos (audit of the daily flows, finding 1): the heartbeat beat after every «app opened», the one BAXY had
/// just opened for the person too, and held the turn while the person's next words waited for it.
/// </summary>
[TestFixture]
public sealed class HeartbeatTurnTests
{
    [Test]
    public async Task AnApplicationOpenedInATurnWhereBaxyActedForThePersonIsNoNews()
    {
        Heartbeat heartbeat = Heartbeat();
        await using (heartbeat)
        {
            heartbeat.NoteApplications(["explorer"]);
            heartbeat.NoteApplications(["explorer", "Spotify"]);
            heartbeat.PersonTurnEnded(acted: true);
            heartbeat.NoteApplications(["explorer", "Spotify"]);

            Assert.That(Events(heartbeat), Is.Empty);
        }
    }

    [Test]
    public async Task AnApplicationOpenedWhileBaxyDidNothingIsNews()
    {
        Heartbeat heartbeat = Heartbeat();
        await using (heartbeat)
        {
            heartbeat.NoteApplications(["explorer"]);
            heartbeat.PersonTurnEnded(acted: false);
            heartbeat.NoteApplications(["explorer", "Discord"]);

            Assert.That(Events(heartbeat), Is.EqualTo(new[] { "app opened: Discord" }));
        }
    }

    [Test]
    public async Task ThePersonsWordsStopAHeartbeatBeforeItsNextCall()
    {
        using var fake = new FakeMind();
        fake.Script(new JsonObject
        {
            ["hold"] = new JsonObject { ["turn.beat"] = "go" },
            ["reply"] = new JsonObject
            {
                ["turn.beat"] = new JsonObject
                {
                    ["type"] = "turn.result", ["kind"] = "action", ["operation"] = "system.time",
                    ["arguments"] = new JsonObject(),
                },
            },
        });
        MainWindowViewModel viewModel = await ViewModelHarness.WithMindAsync();
        await using (viewModel)
        {
            ViewModelHarness.AcceptTurns(viewModel);
            Task beat = viewModel.RunBeatAsync(new JsonObject { ["owner_activity"] = "libre" }, true,
                CancellationToken.None);
            Assert.That(await fake.WaitSeenAsync("turn.beat"), Is.True);

            Task person = viewModel.SubmitAsync(new MissionInput("hola", MissionInputSource.Text),
                Stopwatch.GetTimestamp(), CancellationToken.None);
            fake.Open("go");
            await Task.WhenAll(beat, person).WaitAsync(TimeSpan.FromSeconds(20));

            Assert.That(fake.Seen, Does.Contain("turn.decide"));
            Assert.That(fake.Seen, Does.Not.Contain("turn.continue"), "the heartbeat ran its call and asked the model again");
        }
    }

    // Revisión de calidad (2026-10-25): whether a heartbeat may run was read before the moment was gathered (memory and
    // reminders: two engine round trips of up to 10 s each); the owner who put BAXY to rest or silenced it meanwhile
    // still got the beat.
    [Test]
    public async Task AHeartbeatThatMayNoLongerRunOnceItsMomentIsGatheredDoesNotBeat()
    {
        bool rested = false;
        int beats = 0;
        Heartbeat heartbeat = new(
            (_, _) =>
            {
                beats++;
                return Task.CompletedTask;
            },
            () => !rested,
            static () => [],
            () =>
            {
                rested = true;
                return Task.FromResult<IReadOnlyList<string>>([]);
            },
            static () => Task.FromResult(new JsonArray()));
        await using (heartbeat)
        {
            var clock = new LaterClock();
            typeof(Heartbeat).GetField("_pace", BindingFlags.Instance | BindingFlags.NonPublic)!
                .SetValue(heartbeat, new HeartbeatPace(clock));
            clock.Later = TimeSpan.FromHours(1);
            Events(heartbeat).Add("app opened: Discord");

            await (Task)typeof(Heartbeat).GetMethod("LookAsync", BindingFlags.Instance | BindingFlags.NonPublic)!
                .Invoke(heartbeat, [CancellationToken.None])!;

            Assert.That(beats, Is.Zero, "the heartbeat beat after the owner put BAXY to rest");
            Assert.That(Events(heartbeat), Does.Contain("app opened: Discord"), "what changed was lost");
        }
    }

    private sealed class LaterClock : TimeProvider
    {
        internal TimeSpan Later { get; set; }

        public override DateTimeOffset GetUtcNow() => base.GetUtcNow() + Later;
    }

    private static Heartbeat Heartbeat() => new(
        static (_, _) => Task.CompletedTask,
        static () => false,
        static () => [],
        static () => Task.FromResult<IReadOnlyList<string>>([]),
        static () => Task.FromResult(new JsonArray()));

    private static List<string> Events(Heartbeat heartbeat) =>
        (List<string>)typeof(Heartbeat).GetField("_events", BindingFlags.Instance | BindingFlags.NonPublic)!
            .GetValue(heartbeat)!;
}
