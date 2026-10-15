using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// tanda-02b: honest replies the shell refused, and the shapes it must keep
/// refusing. A refused social reply sent the turn to a recomposition that
/// answered the previous topic with an invented date.
/// </summary>
[TestFixture]
public sealed class C03Tanda02bComposeTests
{
    private const string Weather =
        """{"kind":"operation","operation":"weather.current","polarity":"success","verified":true,"succeeded":true,"observed":{"version":1,"location":"Rosario","country":"Argentina","locatedBy":"public_ip_address","temperatureC":17.3,"apparentC":16,"humidityPercent":71,"windKmh":6.1,"precipitationMm":0,"condition":"nublado","today":{"maxC":21,"minC":11.2,"rainProbabilityPercent":6,"sunrise":"07:02","sunset":"19:21"},"tomorrow":{"date":"2026-09-25","maxC":22.5,"minC":12.5,"rainProbabilityPercent":35,"condition":"nublado","sunrise":"07:01","sunset":"19:22"},"authority":"open_meteo_forecast_v1"}}""";

    [TestCase("¡Ave, César! ¿Cómo estás? ¿Qué tal si contamos un chiste rápido? 😄")]
    [TestCase("¡Ave, César! ¿Qué te trae por aquí?")]
    public void ASalutationReturnedBeforeAnotherQuestionIsNotAnEcho(string reply)
    {
        Assert.That(UserMessagePolicy.ConversationReplyRejectionReason(
            "¡ave, cesar!", reply, "es", "chistes what will the date be in 64 days ¡ave, cesar!"), Is.Null);
    }

    [TestCase("¿Ave, César?")]
    [TestCase("Hola. ¿Me dices ave, cesar otra vez?")]
    public void AQuestionThatCarriesTheRequestStillEchoesIt(string reply)
    {
        Assert.That(UserMessagePolicy.ConversationReplyRejectionReason("¡ave, cesar!", reply, "es"),
            Is.EqualTo("echoes_request"));
    }

    [Test]
    public void AnHtmlTagInATechnicalAnswerIsPublishable()
    {
        Assert.That(UserMessagePolicy.ConversationReplyRejectionReason(
            "¿Cómo incluir un archivo HTML en otro  HTML?",
            "Incluyes el archivo HTML dentro de otro usando la etiqueta <iframe> con la ruta del archivo.",
            "es"), Is.Null);
    }

    [TestCase("necesito el horario de la caída del sol para mañana.", "La puesta del sol mañana en Rosario será a las 19:22.")]
    [TestCase("¿Cuántas pulgadas are we getting today?", "No tengo la cantidad en pulgadas, pero hoy hay un 6 % de probabilidad de lluvia.")]
    public void AnObservedWeatherAnswerIsNotRefusedByTheShell(string request, string reply)
    {
        var draft = new UserMessageDraft(Weather, "status", null);
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(reply, draft, request), Is.Null);
    }
}
