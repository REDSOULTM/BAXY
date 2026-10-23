using Baxy.App;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// The conductor's labels of what the voice says (src/Baxy.App/ConductorUtterances.cs). Renew al máximo: the notice,
/// said from its ready audio, sounded before the voice's acceptance of it reached the App, so the conductor named it
/// with the last line BAXY published (the previous case's answer: nb-int5-X-s0 E005, nb-int-M-s0 E003), took it for the
/// response and the bench read the case's own answer as never said.
/// </summary>
[TestFixture]
public sealed class ConductorUtterancesTests
{
    private const string Notice = "Estoy procesando tu solicitud.";
    private const string Previous = "Listo, te recuerdo en 10 minutos sacar la ropa de la lavadora.";
    private const string Answer = "Listo, puse «Reunión a las 5 en la sala B» en el portapapeles.";

    [Test]
    public void ANoticeThatSoundsBeforeItsAcceptanceArrivesIsTheNotice()
    {
        // nb-int5-X-s0 E005's order: the sound at 2514 ms, notice.queued at 2517 ms, the answer at 4253 / 5596 ms.
        var utterances = new ConductorUtterances();
        utterances.Published(Previous);
        utterances.TurnStarted();

        Assert.That(utterances.Sounded(2514, Notice), Is.EqualTo((Notice, true)));
        Assert.That(utterances.ResponseSpeechStartedMs, Is.Null);

        utterances.Published(Answer);
        Assert.That(utterances.Sounded(5596, null), Is.EqualTo((Answer, false)));
        Assert.That(utterances.SpeechStartedMs, Is.EqualTo(2514));
        Assert.That(utterances.ResponseSpeechStartedMs, Is.EqualTo(5596));
    }

    [Test]
    public void ANoticeSaidAfterTheAnswerIsPublishedIsNotTheAnswer()
    {
        // The answer is on screen at 2.3 s and still being synthesized when the notice sounds at 2.5 s.
        var utterances = new ConductorUtterances();
        utterances.TurnStarted();
        utterances.Published(Answer);

        Assert.That(utterances.Sounded(2500, Notice), Is.EqualTo((Notice, true)));
        Assert.That(utterances.Sounded(4300, null), Is.EqualTo((Answer, false)));
        Assert.That(utterances.ResponseSpeechStartedMs, Is.EqualTo(4300));
    }

    [Test]
    public void TheUsualOrderStillNamesBoth()
    {
        var utterances = new ConductorUtterances();
        utterances.Published(Previous);
        utterances.TurnStarted();

        Assert.That(utterances.Sounded(2501, Notice), Is.EqualTo((Notice, true)));
        utterances.Published(Answer);
        Assert.That(utterances.Sounded(4303, null), Is.EqualTo((Answer, false)));
        Assert.That(utterances.SpeechStartedMs, Is.EqualTo(2501));
        Assert.That(utterances.ResponseSpeechStartedMs, Is.EqualTo(4303));
    }
}
