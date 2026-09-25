using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Tandas 6c and 7 (2026-09-25, official window): the shell's twin of the mind's fixes for single-message misses.
/// The phrasings are paraphrases, not the tandas' literals, with negative controls.
/// </summary>
[TestFixture]
public sealed class C03Tanda07SingleMissTests
{
    // «¿cuánto rato queda para las seis?»: the countdown is asked with any measure of time and any verb of
    // remaining; the shell reads the same head as the mind, so the computed remaining time is not refused for
    // leaving out the observed clock.
    [TestCase("¿cuánto rato queda para las nueve?")]
    [TestCase("cuántas horas faltan para las 8 de la noche")]
    [TestCase("qué tanto falta para las once")]
    [TestCase("how many minutes until 5 pm")]
    [TestCase("how much time is left till noon")]
    [TestCase("how long do we have until six")]
    [TestCase("cuánto falta para las 3 de la tarde")]
    public void TheTimeLeftToAClockTimeIsACountdown(string request)
    {
        Assert.That(UserMessagePolicy.IsCountdownRequest(request), Is.True);
    }

    [TestCase("qué hora es")]
    [TestCase("cuánto dura la película")]
    [TestCase("how long is the movie")]
    [TestCase("pon un temporizador de 5 minutos")]
    public void AnotherTimeQuestionIsNotACountdown(string request)
    {
        Assert.That(UserMessagePolicy.IsCountdownRequest(request), Is.False);
    }
}
