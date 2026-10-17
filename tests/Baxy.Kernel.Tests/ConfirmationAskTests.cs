using Baxy.App;
using NUnit.Framework;

namespace Baxy.Kernel.Tests;

/// <summary>
/// When BAXY's line is the confirmation of the call that waits (src/Baxy.App/ConfirmationAsk.cs, linked here: the App
/// has no test project).
/// </summary>
[TestFixture]
public sealed class ConfirmationAskTests
{
    [Test]
    public void ACallTheTurnAskedForIsWhatItsLineAsks()
    {
        Assert.That(ConfirmationAsk.Asks(waiting: true, askedAt: 50, turnStarted: 40), Is.True);
    }

    // Ronda final 30 (regla 3): a call asked before the person's words is answered by those words through the model;
    // a line of their turn is no question about it, so it gets no Sí/No (a reply in words only, with a «Sí» under it,
    // ran the call). Their words still answer it.
    [Test]
    public void ACallAskedBeforeThePersonsWordsGetsNoButtonsUnderTheirTurnsLine()
    {
        Assert.Multiple(() =>
        {
            Assert.That(ConfirmationAsk.Asks(waiting: true, askedAt: 10, turnStarted: 40), Is.False);
            Assert.That(ConfirmationAsk.Answers(askedAt: 10, personAt: 30), Is.True);
        });
    }

    [Test]
    public void AHeartbeatsCallHeldWhileThePersonsWordsWaitedIsNotWhatTheirTurnAsks()
    {
        // They spoke at 30, the heartbeat held its call at 35, their turn started at 40: the model never read it.
        Assert.That(ConfirmationAsk.Asks(waiting: true, askedAt: 35, turnStarted: 40), Is.False);
    }

    [Test]
    public void ACallWhoseQuestionIsNotPublishedIsTheTurnsAndNoWordsAnswerIt()
    {
        Assert.That(ConfirmationAsk.Asks(waiting: true, ConfirmationAsk.Unpublished, turnStarted: 40), Is.True);
        Assert.That(ConfirmationAsk.Answers(ConfirmationAsk.Unpublished, personAt: long.MaxValue - 1), Is.False);
    }

    [Test]
    public void OnlyWordsAfterTheQuestionWasPublishedAnswerIt()
    {
        Assert.That(ConfirmationAsk.Answers(askedAt: 35, personAt: 30), Is.False);
        Assert.That(ConfirmationAsk.Answers(askedAt: 35, personAt: 35), Is.False);
        Assert.That(ConfirmationAsk.Answers(askedAt: 35, personAt: 36), Is.True);
    }

    [Test]
    public void WithNothingWaitingNoLineIsAConfirmation()
    {
        Assert.That(ConfirmationAsk.Asks(waiting: false, askedAt: 50, turnStarted: 40), Is.False);
    }
}
