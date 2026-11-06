using System.Text.Json.Nodes;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// The microphone the App believes closed is closed: a voice.start that did not succeed in time is stopped
/// (MindSidecarClient), and words heard while the App is not listening start nothing (MainWindowViewModel).
/// </summary>
[TestFixture]
public sealed class MicrophoneStateTests
{
    [Test]
    public async Task AVoiceStartAnsweredTooLateIsStopped()
    {
        using var fake = new FakeMind();
        fake.Script(new JsonObject { ["delay"] = new JsonObject { ["voice.start"] = 1.5 } });
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();

        bool started = await mind.VoiceStartAsync("wake", TimeSpan.FromMilliseconds(300), CancellationToken.None);

        Assert.That(started, Is.False);
        Assert.That(await fake.WaitSeenAsync("voice.stop"), Is.True, "the microphone the late start opened stays open");
        Assert.That(mind.IsReady, Is.True);
    }

    [Test]
    public async Task AVoiceStartCancelledBeforeItsAnswerIsStopped()
    {
        using var fake = new FakeMind();
        fake.Script(new JsonObject { ["delay"] = new JsonObject { ["voice.start"] = 1.5 } });
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        using var cancel = new CancellationTokenSource(TimeSpan.FromMilliseconds(300));

        Assert.That(async () => await mind.VoiceStartAsync("direct", TimeSpan.FromSeconds(10), cancel.Token),
            Throws.InstanceOf<OperationCanceledException>());
        Assert.That(await fake.WaitSeenAsync("voice.stop"), Is.True, "the microphone the late start opened stays open");
    }

    [Test]
    public async Task AVoiceStartThatStartedIsNotStopped()
    {
        using var fake = new FakeMind();
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();

        Assert.That(await mind.VoiceStartAsync("wake", TimeSpan.FromSeconds(5), CancellationToken.None), Is.True);
        Assert.That(fake.Seen, Does.Not.Contain("voice.stop"));
    }

    [Test]
    public async Task AVoiceStartCarriesTheOwnersEchoCancelSwitch()
    {
        using var fake = new FakeMind();
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();

        Assert.That(await mind.VoiceStartAsync("wake", TimeSpan.FromSeconds(5), CancellationToken.None), Is.True);
        Assert.That(await mind.VoiceStartAsync("wake", TimeSpan.FromSeconds(5), CancellationToken.None, echoCancel: false),
            Is.True);

        IReadOnlyList<JsonObject> starts = fake.Requests("voice.start");
        Assert.That(starts.Select(static start => (bool?)start["echoCancel"]), Is.EqualTo(new bool?[] { true, false }));
    }

    [Test]
    public async Task WordsHeardWhileTheAppIsNotListeningStartNoTurn()
    {
        using var fake = new FakeMind();
        fake.Script(new JsonObject
        {
            ["emit"] = new JsonObject
            {
                ["voice.release"] = new JsonArray(new JsonObject { ["type"] = "voice.transcript", ["text"] = "abre la calculadora" }),
            },
        });
        MainWindowViewModel viewModel = await ViewModelHarness.WithMindAsync();
        await using (viewModel)
        {
            ViewModelHarness.AcceptTurns(viewModel);
            Assert.That(viewModel.IsListening || viewModel.IsWakeListening, Is.False);

            Assert.That(await viewModel.ReleaseDirectVoiceAsync(CancellationToken.None), Is.True);

            Assert.That(await ViewModelHarness.UntilAsync(() => fake.Seen.Contains("turn.decide"), seconds: 1.5), Is.False,
                "a transcript from a microphone the App believes closed started a turn");
            Assert.That(viewModel.Messages, Is.Empty);
        }
    }

    [Test]
    public async Task WordsHeardWhileListeningStartATurn()
    {
        using var fake = new FakeMind();
        fake.Script(new JsonObject
        {
            ["emit"] = new JsonObject
            {
                ["voice.release"] = new JsonArray(new JsonObject { ["type"] = "voice.transcript", ["text"] = "abre la calculadora" }),
            },
        });
        MainWindowViewModel viewModel = await ViewModelHarness.WithMindAsync();
        await using (viewModel)
        {
            ViewModelHarness.AcceptTurns(viewModel);
            Assert.That(await viewModel.SetWakeVoiceAsync(true, CancellationToken.None), Is.True);

            Assert.That(await viewModel.ReleaseDirectVoiceAsync(CancellationToken.None), Is.True);

            Assert.That(await fake.WaitSeenAsync("turn.decide"), Is.True);
            Assert.That(await ViewModelHarness.UntilAsync(() => viewModel.Messages.Count == 2), Is.True);
            Assert.That(viewModel.Messages[0].Body, Is.EqualTo("abre la calculadora"));
        }
    }
}
