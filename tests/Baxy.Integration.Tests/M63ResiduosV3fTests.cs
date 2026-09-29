using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// M63 (v3f-final, 2026-09-29) F-s019 «Cambia la alarma despertador de las 8:00 a las 9:00.»: the mind wrote «No se
/// pudo cambiar la alarma porque no estaba configurada para las 8:00. ¿Te gustaría que la establezca para las 9:00?»
/// and the App dropped it as missing_literal_fact (events.jsonl, mindRejectedReply): the failure carried no clock, so
/// any clock in the reply was taken for an invented one. The clocks the person named are theirs to hear back, said in
/// any equivalent form; a clock nobody named stays invented. The mind judges the same
/// (tests/test_c03_m63_residuos_v3f.py).
/// </summary>
[TestFixture]
public sealed class M63ResiduosV3fTests
{
    private const string AlarmChange = "Cambia la alarma despertador de las 8:00 a las 9:00.";

    // The situation of turn t19 as the App composed it (compose-audit.jsonl, v3f-final).
    private const string NoAlarmAtThatTime =
        "{\"kind\":\"failure\",\"polarity\":\"failure\",\"cause\":\"mission_failed\",\"stepCount\":0,\"steps\":[],"
        + "\"reason\":{\"kind\":\"operation\",\"operation\":\"notification.cancel.at\",\"polarity\":\"failure\","
        + "\"verified\":false,\"succeeded\":false,\"error\":\"notification_clock_not_found\"}}";

    private static UserMessageDraft FailureDraft() =>
        UserMessagePolicy.Create(
            NoAlarmAtThatTime, UserMessageEvent.Error(UserMessageDiagnosticCodes.ActionNotCompleted));

    [TestCase(AlarmChange,
        "No se pudo cambiar la alarma porque no estaba configurada para las 8:00. ¿Te gustaría que la establezca para las 9:00?")]
    [TestCase(AlarmChange, "No hay ninguna alarma a las 08:00. ¿Quieres que ponga una a las 09:00?")]
    [TestCase(AlarmChange, "No hay ninguna alarma a las 8:00 a. m., así que no cambié nada. ¿La pongo a las 9:00?")]
    [TestCase("Cambia la alarma de las 8 de la mañana a las 9 de la mañana.",
        "No hay ninguna alarma a las 8:00. ¿Quieres que ponga una a las 9:00?")]
    [TestCase("Cambia la alarma de las 8:00 a. m. a las 9:00 a. m.",
        "No hay ninguna alarma a las 08:00. ¿Quieres que ponga una a las 9:00?")]
    [TestCase("move my 8 pm alarm to 9 pm", "There is no alarm at 20:00, so nothing changed. Should I set one at 9:00 pm?")]
    public void TheClocksThePersonNamedAreNotInvented(string userText, string reply)
    {
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(reply, FailureDraft(), userText), Is.Null);
    }

    [Test]
    public void ANamedClockFailureDoesNotOweThisPcsClock()
    {
        // The same failure read beside this PC's clock (07:45 local): the alarm's clock is the fact, not the time now.
        const string withClock =
            "{\"kind\":\"operation\",\"operation\":\"notification.cancel.at\",\"polarity\":\"failure\","
            + "\"verified\":false,\"succeeded\":false,\"error\":\"notification_clock_not_found\","
            + "\"observed\":{\"version\":1,\"utc\":\"2026-09-29T10:45:53Z\",\"localUtcOffsetMinutes\":-180}}";
        UserMessageDraft draft = UserMessagePolicy.Create(
            withClock, UserMessageEvent.Error(UserMessageDiagnosticCodes.ActionNotCompleted));
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "No hay ninguna alarma a las 8:00, así que no cambié nada. ¿Quieres que ponga una a las 9:00?",
                draft,
                AlarmChange),
            Is.Null);
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "No hay ninguna alarma a las 8:00. ¿Quieres que ponga una a las 10:30?", draft, AlarmChange),
            Is.EqualTo("missing_literal_fact"));
    }

    // F-w01-t6 «¿Va a llover en Ñuñoa?»: the mind's plain answers (tests/test_c03_m63_residuos_v3f.py) reach
    // the person through the App's policy as they are.
    private const string VinaWeather =
        "{\"kind\":\"operation\",\"operation\":\"weather.current\",\"polarity\":\"success\",\"verified\":true,"
        + "\"succeeded\":true,\"observed\":{\"version\":1,\"location\":\"Ñuñoa\",\"region\":\"Región de Curicó\","
        + "\"country\":\"Chile\",\"locatedBy\":\"named_place_geocoded\",\"observedAtLocal\":\"2026-09-29T07:45\","
        + "\"timezone\":\"America/Santiago\",\"temperatureC\":12.4,\"apparentC\":10.6,\"humidityPercent\":87,"
        + "\"windKmh\":13.7,\"precipitationMm\":0,\"uvIndex\":0,\"dewPointC\":10.3,\"weatherCode\":3,\"condition\":\"nublado\","
        + "\"today\":{\"date\":\"2026-09-29\",\"weekday\":\"martes\",\"maxC\":20.4,\"minC\":10.1,\"rainProbabilityPercent\":4,"
        + "\"uvIndexMax\":5,\"sunrise\":\"07:25\",\"sunset\":\"19:47\"},\"tomorrow\":{\"date\":\"2026-09-30\","
        + "\"weekday\":\"miércoles\",\"maxC\":23,\"minC\":7.9,\"rainProbabilityPercent\":0,\"uvIndexMax\":6.8,"
        + "\"condition\":\"llovizna\",\"sunrise\":\"07:24\",\"sunset\":\"19:48\"},\"authority\":\"open_meteo_forecast_v1\"}}";

    [TestCase("¿Va a llover en Ñuñoa?",
        "En Ñuñoa no se espera lluvia: hoy 4 % y mañana 0 % de probabilidad, aunque el pronóstico de mañana marca llovizna.")]
    [TestCase("¿Lloverá mañana en Ñuñoa?",
        "En Ñuñoa no se espera lluvia mañana: 0 % de probabilidad, aunque el pronóstico marca llovizna.")]
    [TestCase("¿Qué tiempo hará mañana en Ñuñoa?",
        "En Ñuñoa, mañana: de 7,9 a 23 °C, 0 % de lluvia, aunque el pronóstico marca llovizna.")]
    public void ThePlainRainAnswerIsPublished(string userText, string reply)
    {
        UserMessageDraft draft = UserMessagePolicy.Create(VinaWeather, UserMessageEvent.Status);
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(reply, draft, userText), Is.Null);
    }

    [TestCase("No hay ninguna alarma a las 7:00. ¿Quieres que ponga una a las 9:00?")]
    [TestCase("No hay ninguna alarma a las 8:00. ¿Quieres que ponga una a las 9:30?")]
    public void AClockNobodyNamedIsStillInvented(string reply)
    {
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(reply, FailureDraft(), AlarmChange),
            Is.EqualTo("missing_literal_fact"));
    }
}
