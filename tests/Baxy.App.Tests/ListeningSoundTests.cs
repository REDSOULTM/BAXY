using System.Collections.Concurrent;
using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// The ear's two sounds (uso real 03-11: the wake sound came late, and nothing told when BAXY stopped listening):
/// <see cref="Chime.Wake"/> when «Baxy» is heard and <see cref="Chime.Heard"/> when the request closes
/// (the mind's transcribing), one each per request, under the person's wake-sound switch and BAXY's silenced voice; and
/// both sound as the mind's event arrives, whatever the interface's thread is doing.
/// </summary>
[TestFixture]
public sealed class ListeningSoundTests
{
    [Test]
    public async Task TheEarsSoundsDoNotWaitForTheInterfacesThread()
    {
        using var fake = new FakeMind();
        var sounds = new ConcurrentQueue<Chime>();
        var ui = new HeldContext();
        MainWindowViewModel viewModel = await WithContextAsync(ui, sounds);
        await using (viewModel)
        {
            Assert.That(await viewModel.SetWakeVoiceAsync(true, CancellationToken.None), Is.True);

            // The interface's thread is busy: nothing it was asked to do runs until it is let go.
            ui.Hold();
            await EmitAsync(fake, viewModel, Voice("wake_detected"));
            Assert.That(await ViewModelHarness.UntilAsync(() => sounds.Count == 1, seconds: 3), Is.True,
                "«Baxy» heard waited for the interface's thread to sound");
            await EmitAsync(fake, viewModel, Voice("transcribing"));
            Assert.That(await ViewModelHarness.UntilAsync(() => sounds.Count == 2, seconds: 3), Is.True,
                "the end of the request waited for the interface's thread to sound");
            Assert.That(viewModel.StatusDescription, Is.Not.EqualTo("Transcribiendo…"), "the thread was not held");

            // Let go, it shows what the ear said and sounds nothing more.
            ui.Release();
            Assert.That(await ViewModelHarness.UntilAsync(() => viewModel.StatusDescription == "Transcribiendo…"), Is.True);
            Assert.That(sounds, Is.EqualTo(new[] { Chime.Wake, Chime.Heard }));
        }
    }

    [Test]
    public async Task EachRequestSoundsItsStartAndItsEndOnceUnderThePersonsSwitch()
    {
        using var fake = new FakeMind();
        var sounds = new ConcurrentQueue<Chime>();
        MainWindowViewModel viewModel = await ViewModelHarness.WithMindAsync(sounds.Enqueue);
        await using (viewModel)
        {
            Assert.That(await viewModel.SetWakeVoiceAsync(true, CancellationToken.None), Is.True);

            // Two requests, each with its live caption between: a start and an end each.
            for (int request = 0; request < 2; request++)
            {
                await HearAsync(fake, viewModel, Voice("wake_detected"), () => viewModel.StatusDescription == "Te escucho…");
                await HearAsync(fake, viewModel, Voice("partial"), () => viewModel.StatusDescription == "Te escucho…");
                await HearAsync(fake, viewModel, Voice("transcribing"), () => viewModel.StatusDescription == "Transcribiendo…");
            }

            Assert.That(await ViewModelHarness.UntilAsync(() => sounds.Count == 4), Is.True);

            // Switched off by the person: neither sounds.
            viewModel.Settings.ApplyGeneral(new JsonObject { ["wakeSound"] = false });
            await HearAsync(fake, viewModel, Voice("wake_detected"), () => viewModel.StatusDescription == "Te escucho…");
            await HearAsync(fake, viewModel, Voice("transcribing"), () => viewModel.StatusDescription == "Transcribiendo…");

            Assert.That(sounds, Is.EqualTo(new[] { Chime.Wake, Chime.Heard, Chime.Wake, Chime.Heard }));
        }
    }

    [Test]
    public async Task ASilencedVoiceSoundsNeitherWithTheSwitchOn()
    {
        using var fake = new FakeMind();
        var sounds = new ConcurrentQueue<Chime>();
        MainWindowViewModel viewModel = await ViewModelHarness.WithMindAsync(sounds.Enqueue);
        await using (viewModel)
        {
            viewModel.Settings.ApplyGeneral(new JsonObject { ["voiceMuted"] = true, ["wakeSound"] = true });
            Assert.That(await viewModel.SetWakeVoiceAsync(true, CancellationToken.None), Is.True);

            await HearAsync(fake, viewModel, Voice("wake_detected"), () => viewModel.StatusDescription == "Te escucho…");
            await HearAsync(fake, viewModel, Voice("transcribing"), () => viewModel.StatusDescription == "Transcribiendo…");

            Assert.That(sounds, Is.Empty);
        }
    }

    [Test]
    public void TheStartRisesAndTheEndFallsShortAndEachItsOwn()
    {
        Chime[] tones = [Chime.Wake, Chime.Heard, Chime.TurnFailed, Chime.ListenFailed, Chime.Wait, Chime.StillReading];
        Assert.Multiple(() =>
        {
            foreach (Chime tone in (Chime[])[Chime.Wake, Chime.Heard])
            {
                byte[] wave = tone.Wave;
                int dataBytes = BitConverter.ToInt32(wave, 40);
                double milliseconds = dataBytes / 2.0 / BitConverter.ToInt32(wave, 24) * 1000;
                Assert.That(milliseconds, Is.InRange(80, 200));
                Assert.That(tones.Count(other => other.Wave.SequenceEqual(wave)), Is.EqualTo(1));
            }

            // Its first half is the higher note when it falls: more zero crossings per sample.
            Assert.That(Crossings(Chime.Wake.Wave, first: true), Is.LessThan(Crossings(Chime.Wake.Wave, first: false)));
            Assert.That(Crossings(Chime.Heard.Wave, first: true), Is.GreaterThan(Crossings(Chime.Heard.Wave, first: false)));
        });
    }

    private static int Crossings(byte[] wave, bool first)
    {
        int samples = (wave.Length - 44) / 2, from = first ? 0 : samples / 2, to = first ? samples / 2 : samples;
        int crossings = 0;
        for (int i = from + 1; i < to; i++)
        {
            short a = BitConverter.ToInt16(wave, 44 + (i - 1) * 2), b = BitConverter.ToInt16(wave, 44 + i * 2);
            crossings += (a < 0) != (b < 0) ? 1 : 0;
        }

        return crossings;
    }

    // The view model built under ``ui`` as the App builds it under its window's thread.
    private static async Task<MainWindowViewModel> WithContextAsync(SynchronizationContext ui, ConcurrentQueue<Chime> sounds)
    {
        SynchronizationContext? before = SynchronizationContext.Current;
        SynchronizationContext.SetSynchronizationContext(ui);
        try
        {
            return await ViewModelHarness.WithMindAsync(sounds.Enqueue);
        }
        finally
        {
            SynchronizationContext.SetSynchronizationContext(before);
        }
    }

    // One message from the mind, as its voice sends it (the fake mind sends it on voice.release).
    private static async Task EmitAsync(FakeMind fake, MainWindowViewModel viewModel, JsonObject message)
    {
        fake.Script(new JsonObject { ["emit"] = new JsonObject { ["voice.release"] = new JsonArray(message) } });
        Assert.That(await viewModel.ReleaseDirectVoiceAsync(CancellationToken.None), Is.True);
    }

    private static async Task HearAsync(FakeMind fake, MainWindowViewModel viewModel, JsonObject message, Func<bool> taken)
    {
        await EmitAsync(fake, viewModel, message);
        Assert.That(await ViewModelHarness.UntilAsync(taken), Is.True, $"the App did not take {message.ToJsonString()}");
    }

    private static JsonObject Voice(string name) =>
        name == "partial"
            ? new JsonObject { ["type"] = "voice.event", ["event"] = name, ["mode"] = "wake", ["text"] = "abre" }
            : new JsonObject { ["type"] = "voice.event", ["event"] = name, ["mode"] = "wake" };

    /// <summary>A window's thread that can be kept busy: while held, what is posted to it waits.</summary>
    private sealed class HeldContext : SynchronizationContext
    {
        private readonly List<(SendOrPostCallback Callback, object? State)> _held = [];
        private bool _holding;

        public override void Post(SendOrPostCallback d, object? state)
        {
            lock (_held)
            {
                if (_holding)
                {
                    _held.Add((d, state));
                    return;
                }
            }

            ThreadPool.QueueUserWorkItem(_ => d(state));
        }

        internal void Hold()
        {
            lock (_held)
            {
                _holding = true;
            }
        }

        internal void Release()
        {
            (SendOrPostCallback Callback, object? State)[] held;
            lock (_held)
            {
                _holding = false;
                held = [.. _held];
                _held.Clear();
            }

            foreach ((SendOrPostCallback callback, object? state) in held)
            {
                callback(state); // in order, as the thread would run them
            }
        }
    }
}
