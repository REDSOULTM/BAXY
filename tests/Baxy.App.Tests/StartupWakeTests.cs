using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// The wake word asked for at start (BAXY_VOICE_WAKE_ON_START, or the interface applying the person's «escucho
/// siempre» as soon as the mind is up) starts once the ear has loaded, however long it takes, and a start that failed
/// is shown as a state. 2026-10-25 (spoken A/B on the notebook, c11b-on1): under load the interface's start reached the
/// mind while its ear still loaded; the mind waited for it (Voice.start, up to 60 s) and opened the microphone just as
/// the App's 60 s for the answer ran out, so the App stopped it again and nothing ever tried once more: twenty minutes
/// with the voice closed and nothing on screen saying so.
/// </summary>
[TestFixture]
[NonParallelizable]
public sealed class StartupWakeTests
{
    private const string WakeOnStart = "BAXY_VOICE_WAKE_ON_START";

    [Test]
    public async Task TheWakeAskedForWhileTheEarLoadsIsStartedOnceItLoaded()
    {
        using var fake = new FakeMind();
        fake.Script(VoiceStatus(pending: true));
        MainWindowViewModel viewModel = await ViewModelHarness.WithMindAsync();
        await using (viewModel)
        {
            Task<bool> asked = viewModel.SetWakeVoiceAsync(true, CancellationToken.None);

            Assert.That(await fake.WaitSeenAsync("voice.status", count: 3), Is.True);
            Assert.That(fake.Seen, Does.Not.Contain("voice.start"),
                "a start sent while the ear loads waits in the mind for it and may be answered after the App gave up");

            fake.Script(VoiceStatus(pending: false));
            Assert.That(await asked.WaitAsync(TimeSpan.FromSeconds(15)), Is.True);
            Assert.That(viewModel.IsWakeListening, Is.True);
            Assert.That(fake.Seen, Does.Not.Contain("voice.stop"));
        }
    }

    // Revisión de nb-w11-arranque: the wake start waited for the ear inside the gate of the voice commands, with no
    // bound, so a stop (rest, /voice/stop) waited behind it as long as the ear took to load, or for ever; once loaded,
    // the wake word started before the stop the person had asked after it.
    [Test]
    public async Task AStopAskedWhileAWakeWaitsForTheEarIsNotHeldBehindItAndTheWakeDoesNotStartAfterIt()
    {
        using var fake = new FakeMind();
        fake.Script(VoiceStatus(pending: true));
        MainWindowViewModel viewModel = await ViewModelHarness.WithMindAsync();
        await using (viewModel)
        {
            Task<bool> asked = viewModel.SetWakeVoiceAsync(true, CancellationToken.None);
            Assert.That(await fake.WaitSeenAsync("voice.status", count: 3), Is.True);

            Task<bool> stop = viewModel.SetWakeVoiceAsync(false, CancellationToken.None);
            Assert.That(await Task.WhenAny(stop, Task.Delay(TimeSpan.FromSeconds(5))), Is.SameAs(stop),
                "the stop waited behind a wake start held until the ear loads");
            Assert.That(await stop, Is.True);

            fake.Script(VoiceStatus(pending: false));
            Assert.That(await asked.WaitAsync(TimeSpan.FromSeconds(15)), Is.False);
            Assert.That(viewModel.IsWakeListening, Is.False);
            Assert.That(fake.Seen, Does.Not.Contain("voice.start"));
        }
    }

    [Test]
    public async Task TheStartupWakeStartsWhenTheFirstVoiceReadGotNoAnswer()
    {
        string? before = Environment.GetEnvironmentVariable(WakeOnStart);
        Environment.SetEnvironmentVariable(WakeOnStart, "1");
        try
        {
            using var fake = new FakeMind();
            // The voice's state unread (its answer late under load): unknown, not «no voice».
            fake.Script(new JsonObject
            {
                ["reply"] = new JsonObject
                {
                    ["voice.status"] = new JsonObject { ["type"] = "error", ["code"] = "request_failed" },
                },
            });
            MainWindowViewModel viewModel = await ViewModelHarness.WithMindAsync();
            await using (viewModel)
            {
                fake.Script(VoiceStatus(pending: false));

                Assert.That(await ViewModelHarness.UntilAsync(() => viewModel.IsWakeListening, seconds: 15), Is.True,
                    "the wake word asked for at start never started");
            }
        }
        finally
        {
            Environment.SetEnvironmentVariable(WakeOnStart, before);
        }
    }

    [Test]
    public async Task AStartupWakeThatDidNotStartIsShown()
    {
        string? before = Environment.GetEnvironmentVariable(WakeOnStart);
        Environment.SetEnvironmentVariable(WakeOnStart, "1");
        try
        {
            using var fake = new FakeMind();
            JsonObject script = VoiceStatus(pending: false);
            script["fail"] = new JsonArray("voice.start");
            fake.Script(script);
            MainWindowViewModel viewModel = await ViewModelHarness.WithMindAsync();
            await using (viewModel)
            {
                Assert.That(fake.Seen, Does.Contain("voice.start"));
                Assert.That(viewModel.IsWakeListening, Is.False);
                Assert.That(viewModel.VoiceFailure, Is.EqualTo("wake_unavailable"));
            }
        }
        finally
        {
            Environment.SetEnvironmentVariable(WakeOnStart, before);
        }
    }

    [Test]
    public async Task TheVoiceIsReadUntilItHasLoadedWithNoFixedNumberOfReads()
    {
        int reads = 0;
        MindVoiceStatus? status = await VoiceStatusSettling.UntilSettledAsync(
            _ => Task.FromResult<MindVoiceStatus?>(++reads <= 200
                ? new MindVoiceStatus(false, false, false, Pending: true)
                : new MindVoiceStatus(true, true, true, Pending: false)),
            static (_, _) => Task.CompletedTask,
            CancellationToken.None);

        Assert.That(status, Is.Not.Null);
        Assert.That(status!.Pending, Is.False);
        Assert.That(reads, Is.EqualTo(201));
    }

    [Test]
    public async Task AnUnreadVoiceStateIsReadAgain()
    {
        int reads = 0;
        MindVoiceStatus? status = await VoiceStatusSettling.UntilSettledAsync(
            _ => Task.FromResult(++reads <= 3 ? null : new MindVoiceStatus(true, true, true, Pending: false)),
            static (_, _) => Task.CompletedTask,
            CancellationToken.None);

        Assert.That(status, Is.Not.Null);
        Assert.That(reads, Is.EqualTo(4));
    }

    private static JsonObject VoiceStatus(bool pending) => new()
    {
        ["reply"] = new JsonObject
        {
            ["voice.status"] = new JsonObject
            {
                ["type"] = "voice.status.result",
                ["status"] = new JsonObject
                {
                    ["available"] = !pending,
                    ["input"] = !pending,
                    ["stt"] = !pending,
                    ["wake"] = !pending,
                    ["pending"] = pending,
                },
            },
        },
    };
}
