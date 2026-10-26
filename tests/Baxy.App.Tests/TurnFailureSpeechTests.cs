using Baxy.App;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// Final 4, accesibilidad (src/Baxy.App/TurnFailureSpeech.cs): a turn that ends without an answer from the model is
/// said aloud with its cause, never only shown, and never as if something had been done.
/// </summary>
[TestFixture]
public sealed class TurnFailureSpeechTests
{
    // Every code NativeTurnLoop.Host.Fail and RunGatedTurnAsync give a turn of the person's.
    private static readonly string[] TurnFailures =
        ["mind_unavailable", "decision_unavailable", "decision_unavailable_after_call", "turn_failed"];

    [TestCaseSource(nameof(TurnFailures))]
    public void EveryTurnFailureHasAPlainSpokenLineWithItsCause(string failure)
    {
        string? line = TurnFailureSpeech.LineOf(failure);

        Assert.That(line, Is.Not.Null.And.Not.Empty);
        Assert.That(line, Does.Not.Contain("_"), "a code is never read aloud");
        Assert.That(line, Does.Contain(":").Or.Contain(", así que"), "the line says why");
    }

    [Test]
    public void AFailureAfterACallDoesNotClaimTheResult()
    {
        string line = TurnFailureSpeech.LineOf("decision_unavailable_after_call")!;

        Assert.That(line, Does.Contain("no sé si"));
        Assert.That(line, Does.Not.Contain("Listo").And.Not.Contain("hecho."));
    }

    [TestCase(null)]
    [TestCase("")]
    [TestCase("voice_error")]
    [TestCase("core_disconnected")]
    public void WhatIsNotATurnFailureSaysNothing(string? failure) =>
        Assert.That(TurnFailureSpeech.LineOf(failure), Is.Null);
}
