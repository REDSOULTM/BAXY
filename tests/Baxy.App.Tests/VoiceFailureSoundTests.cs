using System.Collections.Concurrent;
using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// The voice's failures are heard (final 6, accesibilidad): the ear failing while the person speaks sounds
/// <see cref="Chime.ListenFailed"/> once per request and never at rest, and a request heard while BAXY cannot take it
/// sounds <see cref="Chime.Wait"/> once per drop; a request taken sounds neither, and a silenced voice sounds nothing.
/// The fake mind sends one voice message per voice.release, and each step waits until the App took it (the tests' UI
/// context runs posts in any order).
/// </summary>
[TestFixture]
public sealed class VoiceFailureSoundTests
{
    [Test]
    public async Task TheEarFailingSoundsOnceWhileThePersonSpeaksAndNeverAtRest()
    {
        using var fake = new FakeMind();
        var sounds = new ConcurrentQueue<Chime>();
        MainWindowViewModel viewModel = await ViewModelHarness.WithMindAsync(sounds.Enqueue);
        await using (viewModel)
        {
            Assert.That(await viewModel.SetWakeVoiceAsync(true, CancellationToken.None), Is.True);

            // At rest, waiting for «Baxy»: the microphone failing bothers nobody.
            await HearAsync(fake, viewModel, Voice("error", "wake"), () => viewModel.VoiceFailure == "voice_error");
            await HearAsync(fake, viewModel, Voice("partial", "wake"), () => viewModel.VoiceFailure is null);
            Assert.That(sounds, Is.Empty, "the ear failing at rest sounded");

            // «Baxy» heard, and the ear fails twice in that request: one sound.
            await HearAsync(fake, viewModel, Voice("wake_detected", "wake"), () => viewModel.VoiceFailure is null);
            await HearAsync(fake, viewModel, Voice("error", "wake"), () => viewModel.VoiceFailure == "voice_error");
            Assert.That(await ViewModelHarness.UntilAsync(() => sounds.Count == 1), Is.True);
            await HearAsync(fake, viewModel, Voice("partial", "wake"), () => viewModel.VoiceFailure is null);
            await HearAsync(fake, viewModel, Voice("error", "wake"), () => viewModel.VoiceFailure == "voice_error");

            // A dictation whose microphone stops (the mind turns the ear off as it tells the failure): one sound.
            await HearAsync(fake, viewModel, Voice("partial", "wake"), () => viewModel.VoiceFailure is null);
            await HearAsync(fake, viewModel, Voice("state", "direct"), () => viewModel.IsListening);
            await HearAsync(fake, viewModel, Voice("error", "off"), () => viewModel.VoiceFailure == "voice_error");
            Assert.That(await ViewModelHarness.UntilAsync(() => sounds.Count == 2), Is.True);

            // The request over, the ear waits for «Baxy» again: at rest once more.
            await HearAsync(fake, viewModel, Voice("state", "wake"), () => viewModel.IsWakeListening && !viewModel.IsListening);
            await HearAsync(fake, viewModel, Voice("partial", "wake"), () => viewModel.VoiceFailure is null);
            await HearAsync(fake, viewModel, Voice("error", "wake"), () => viewModel.VoiceFailure == "voice_error");
            await HearAsync(fake, viewModel, Voice("partial", "wake"), () => viewModel.VoiceFailure is null);

            Assert.That(sounds, Is.EqualTo(new[] { Chime.ListenFailed, Chime.ListenFailed }));
        }
    }

    [Test]
    public async Task ARequestHeardWhileBaxyCannotTakeItSoundsWaitOncePerDropAndATakenOneSoundsNothing()
    {
        using var fake = new FakeMind();
        var sounds = new ConcurrentQueue<Chime>();
        MainWindowViewModel viewModel = await ViewModelHarness.WithMindAsync(sounds.Enqueue);
        await using (viewModel)
        {
            Assert.That(await viewModel.SetWakeVoiceAsync(true, CancellationToken.None), Is.True);

            // The engine is not up, so no turn can start: each request heard is dropped, and each drop sounds once.
            await HearAsync(fake, viewModel, Transcript(), () => viewModel.VoiceFailure == "voice_dropped_busy");
            Assert.That(await ViewModelHarness.UntilAsync(() => sounds.Count == 1), Is.True);
            await HearAsync(fake, viewModel, Voice("partial", "wake"), () => viewModel.VoiceFailure is null);
            await HearAsync(fake, viewModel, Transcript(), () => viewModel.VoiceFailure == "voice_dropped_busy");
            Assert.That(await ViewModelHarness.UntilAsync(() => sounds.Count == 2), Is.True);

            // Taken: «Baxy», the transcription and the turn that answers sound nothing.
            ViewModelHarness.AcceptTurns(viewModel);
            await HearAsync(fake, viewModel, Voice("wake_detected", "wake"), () => viewModel.VoiceFailure is null);
            await HearAsync(fake, viewModel, Voice("transcribing", "wake"), () => viewModel.StatusDescription == "Transcribiendo…");
            await HearAsync(fake, viewModel, Transcript(), () => viewModel.Messages.Count == 2);
            Assert.That(await ViewModelHarness.UntilAsync(() => !viewModel.IsBusy), Is.True);

            Assert.That(viewModel.VoiceFailure, Is.Null);
            Assert.That(sounds, Is.EqualTo(new[] { Chime.Wait, Chime.Wait }));
        }
    }

    [Test]
    public async Task ASilencedVoiceShowsTheFailuresAndSoundsNothing()
    {
        using var fake = new FakeMind();
        var sounds = new ConcurrentQueue<Chime>();
        MainWindowViewModel viewModel = await ViewModelHarness.WithMindAsync(sounds.Enqueue);
        await using (viewModel)
        {
            viewModel.Settings.ApplyGeneral(new JsonObject { ["voiceMuted"] = true });
            Assert.That(await viewModel.SetWakeVoiceAsync(true, CancellationToken.None), Is.True);

            await HearAsync(fake, viewModel, Voice("wake_detected", "wake"), () => viewModel.VoiceFailure is null);
            await HearAsync(fake, viewModel, Voice("error", "wake"), () => viewModel.VoiceFailure == "voice_error");
            await HearAsync(fake, viewModel, Voice("partial", "wake"), () => viewModel.VoiceFailure is null);
            await HearAsync(fake, viewModel, Transcript(), () => viewModel.VoiceFailure == "voice_dropped_busy");
            await HearAsync(fake, viewModel, Voice("partial", "wake"), () => viewModel.VoiceFailure is null);

            Assert.That(sounds, Is.Empty);
        }
    }

    [Test]
    public void TheVoiceTonesAreShortAndEachItsOwn()
    {
        Chime[] tones = [Chime.Wake, Chime.TurnFailed, Chime.ListenFailed, Chime.Wait];
        Assert.Multiple(() =>
        {
            foreach (Chime tone in (Chime[])[Chime.ListenFailed, Chime.Wait])
            {
                byte[] wave = tone.Wave;
                int dataBytes = BitConverter.ToInt32(wave, 40);
                double milliseconds = dataBytes / 2.0 / BitConverter.ToInt32(wave, 24) * 1000;
                Assert.That(wave.Length, Is.EqualTo(44 + dataBytes));
                Assert.That(milliseconds, Is.InRange(50, 250));
                Assert.That(tones.Count(other => other.Wave.SequenceEqual(wave)), Is.EqualTo(1));
            }
        });
    }

    // One message from the mind, as its voice sends it, and the moment the App has taken it.
    private static async Task HearAsync(FakeMind fake, MainWindowViewModel viewModel, JsonObject message,
        Func<bool> taken)
    {
        fake.Script(new JsonObject { ["emit"] = new JsonObject { ["voice.release"] = new JsonArray(message) } });
        Assert.That(await viewModel.ReleaseDirectVoiceAsync(CancellationToken.None), Is.True);
        Assert.That(await ViewModelHarness.UntilAsync(taken), Is.True, $"the App did not take {message.ToJsonString()}");
    }

    private static JsonObject Voice(string name, string mode) => name == "state"
        ? new JsonObject { ["type"] = "voice.event", ["event"] = name, ["mode"] = mode, ["speaking"] = false }
        : new JsonObject { ["type"] = "voice.event", ["event"] = name, ["mode"] = mode };

    private static JsonObject Transcript() => new() { ["type"] = "voice.transcript", ["text"] = "abre la calculadora" };
}
