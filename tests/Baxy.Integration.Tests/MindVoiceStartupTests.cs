using System.Collections.Generic;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Arranque de la mente (auditoría 2026-10-08, hallazgos 2 y 7): la voz nunca
/// tumba la mente y cada petición fallida lleva su nombre honesto.
/// </summary>
[TestFixture]
public sealed class MindVoiceStartupTests
{
    [TestCase("voice.status")]
    [TestCase("voice.speak")]
    [TestCase("voice.start")]
    [TestCase("voice.stop")]
    [TestCase("voice.cancel")]
    public void AVoiceDeadlineNeverMarksTheMindDown(string requestType)
    {
        string failure = MindSidecarClient.ClassifyRequestFailure(
            new OperationCanceledException(), static () => true);
        Assert.That(failure, Is.EqualTo("request_timeout"));
        Assert.That(MindSidecarClient.InvalidatesMind(failure, requestType), Is.False);
    }

    [TestCase("turn.decide")]
    [TestCase("message.compose")]
    [TestCase("computer.use.step")]
    public void AModelDeadlineStillMarksTheMindDown(string requestType)
    {
        // Contracaso: un turno sin respuesta sigue llevando a la recuperación.
        string failure = MindSidecarClient.ClassifyRequestFailure(
            new OperationCanceledException(), static () => true);
        Assert.That(MindSidecarClient.InvalidatesMind(failure, requestType), Is.True);
    }

    [Test]
    public void ARequestCutByTheMindClosingIsNotATimeout()
    {
        // v2-v3-51: la app cerró ~150 ms después de pedir voice.speak (plazo 5 s).
        string failure = MindSidecarClient.ClassifyRequestFailure(
            new TaskCanceledException(), static () => false);
        Assert.That(failure, Is.EqualTo("mind_closed"));
        Assert.That(MindSidecarClient.InvalidatesMind(failure, "voice.speak"), Is.False);
    }

    [TestCase("voice.status")]
    [TestCase("turn.decide")]
    public void ABrokenTransportAlwaysMarksTheMindDown(string requestType)
    {
        string failure = MindSidecarClient.ClassifyRequestFailure(
            new System.IO.IOException("pipe"), static () => false);
        Assert.That(failure, Is.EqualTo("request_io"));
        Assert.That(MindSidecarClient.InvalidatesMind(failure, requestType), Is.True);
    }

    [Test]
    public async Task APendingVoiceStateIsReadAgainUntilItSettles()
    {
        var clock = new FakeDelay();
        var replies = new Queue<MindVoiceStatus?>([Pending(), null, Pending(), Settled()]);
        MindVoiceStatus? status = await VoiceStatusSettling.UntilSettledAsync(
            _ => Task.FromResult(replies.Dequeue()),
            clock.Delay,
            CancellationToken.None);

        Assert.That(status, Is.EqualTo(Settled()));
        Assert.That(clock.Waits, Is.EqualTo(new[]
        {
            VoiceStatusSettling.Interval,
            VoiceStatusSettling.Interval,
            VoiceStatusSettling.Interval,
            VoiceStatusSettling.Interval,
        }));
    }

    [Test]
    public async Task AVoiceStateThatNeverSettlesStopsAfterItsBound()
    {
        // Contracaso: un runtime de voz que nunca termina de cargar no deja un sondeo eterno.
        var clock = new FakeDelay();
        int reads = 0;
        MindVoiceStatus? status = await VoiceStatusSettling.UntilSettledAsync(
            _ =>
            {
                reads++;
                return Task.FromResult<MindVoiceStatus?>(Pending());
            },
            clock.Delay,
            CancellationToken.None);

        Assert.That(reads, Is.EqualTo(VoiceStatusSettling.MaximumReads));
        Assert.That(status?.Pending, Is.True);
        Assert.That(clock.Waits, Has.Count.EqualTo(VoiceStatusSettling.MaximumReads));
    }

    [Test]
    public void TheStartupWakeComesOnOnceTheVoiceStateIsKnown()
    {
        Assert.Multiple(() =>
        {
            Assert.That(MainWindowViewModel.StartupWakeApplies(Settled(), true, false, false), Is.True);
            // Contracaso: mientras la voz carga no se sabe si hay micrófono.
            Assert.That(MainWindowViewModel.StartupWakeApplies(Pending(), true, false, false), Is.False);
            Assert.That(MainWindowViewModel.StartupWakeApplies(null, true, false, false), Is.False);
            // Contracaso: las tandas arrancan con el wake apagado (ProductConductorHost).
            Assert.That(MainWindowViewModel.StartupWakeApplies(Settled(), false, false, false), Is.False);
        });
    }

    [Test]
    public void ThePersonsVoiceChoiceDuringTheStartupReadWins()
    {
        // Revisión 2026-10-08, escenario A: «deja de escuchar» durante el pending
        // no encontraba nada que apagar y la relectura encendía el wake después.
        Assert.That(MainWindowViewModel.StartupWakeApplies(Settled(), true, personChoseVoice: true, voiceRunning: false),
            Is.False);
        // Escenario B: un dictado directo en curso no pasa a wake ni se corta.
        Assert.That(MainWindowViewModel.StartupWakeApplies(Settled(), true, personChoseVoice: false, voiceRunning: true),
            Is.False);
    }

    [Test]
    public void TheStartupReadStopsWhenItsMindIsGone()
    {
        // Contracaso del sondeo: una mente relanzada o cerrada no deja 60 lecturas vacías.
        var clock = new FakeDelay();
        int reads = 0;
        Assert.ThrowsAsync<OperationCanceledException>(async () =>
            await VoiceStatusSettling.UntilSettledAsync(
                _ =>
                {
                    reads++;
                    return reads < 2
                        ? Task.FromResult<MindVoiceStatus?>(Pending())
                        : throw new OperationCanceledException("mind_replaced");
                },
                clock.Delay,
                CancellationToken.None));
        Assert.That(reads, Is.EqualTo(2));
    }

    private static MindVoiceStatus Pending() =>
        new(false, false, false, false, false, false, false, "off", false, false, Pending: true);

    private static MindVoiceStatus Settled() =>
        new(true, true, true, true, true, false, false, "off", false, false);

    private sealed class FakeDelay
    {
        public List<TimeSpan> Waits { get; } = [];

        public Task Delay(TimeSpan delay, CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            Waits.Add(delay);
            return Task.CompletedTask;
        }
    }
}
