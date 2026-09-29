using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Goal v3 paso 5 (M60): the shell's side of the DEV-D ⚠ in the official window (v3c-devD, v3d-devD-np2, q4-devD,
/// 2026-09-28/29). Every situation is the one the run recorded; every text is the one the mind now publishes for it
/// (a recorded draft, its clip, or the deterministic last resort), which the shell must accept as it stands.
/// </summary>
[TestFixture]
public sealed class M60AvisosDevDTests
{
    private const string WishlistIphone =
        """{"kind":"operation","operation":"task.create","polarity":"success","verified":true,"succeeded":true,"observed":{"taskId":"03450cf2-834c-4448-8fa4-af73f66a36b3","title":"iPhone","details":"lista de deseos que hice la semana pasada","completed":false,"deleted":false,"createdAtUtc":"2026-09-29T03:40:58.842357+00:00","updatedAtUtc":"2026-09-29T03:40:58.842357+00:00","version":1}}""";

    private const string ChipsDeleted =
        """{"kind":"status","polarity":"success","cause":"mission_completed","stepCount":2,"steps":["{\"kind\":\"operation\",\"operation\":\"task.resolve.exact\",\"polarity\":\"success\",\"verified\":true,\"succeeded\":true,\"observed\":{\"taskId\":\"75c31918-bda1-4821-a8e4-00d650598946\",\"expectedVersion\":1,\"reviewLabel\":\"chips\",\"deleted\":false,\"status\":\"open\"},\"readOnly\":true}","{\"kind\":\"operation\",\"operation\":\"task.delete\",\"polarity\":\"success\",\"verified\":true,\"succeeded\":true,\"observed\":{\"taskId\":\"75c31918-bda1-4821-a8e4-00d650598946\",\"title\":\"chips\",\"details\":\"shopping list\",\"completed\":false,\"deleted\":true,\"createdAtUtc\":\"2026-09-29T03:46:03.1292962\\u002B00:00\",\"updatedAtUtc\":\"2026-09-29T03:46:05.0247208\\u002B00:00\",\"version\":2},\"readOnly\":false}"],"completedRequest":"Remove chips from my shopping list."}""";

    private const string SearchUnavailable =
        """{"kind":"failure","polarity":"failure","cause":"mission_failed","stepCount":0,"steps":[],"reason":{"kind":"operation","operation":"web.search","polarity":"failure","verified":false,"succeeded":false,"error":"web_search_unavailable"}}""";

    private const string WeatherUnavailable =
        """{"kind":"failure","polarity":"failure","cause":"mission_failed","stepCount":0,"steps":[],"reason":{"kind":"operation","operation":"weather.current","polarity":"failure","verified":false,"succeeded":false,"error":"weather_service_unavailable"}}""";

    private const string SeekUnverified =
        """{"kind":"failure","polarity":"failure","cause":"mission_failed","stepCount":0,"steps":[],"reason":{"kind":"operation","operation":"media.seek.relative","polarity":"failure","verified":false,"succeeded":false,"error":"media_seek_postcondition_not_verified","cause":"external_effect_ambiguous","effectUncertain":true}}""";

    private const string Medellin =
        """{"kind":"operation","operation":"weather.current","polarity":"success","verified":true,"succeeded":true,"observed":{"version":1,"location":"Medellín","region":"Antioquia","country":"Colombia","locatedBy":"named_place_geocoded","observedAtLocal":"2026-09-28T21:30","timezone":"America/Bogota","temperatureC":18.9,"apparentC":21.3,"humidityPercent":95,"windKmh":3.4,"precipitationMm":0,"uvIndex":0,"dewPointC":18,"weatherCode":2,"condition":"parcialmente nublado","today":{"date":"2026-09-28","weekday":"lunes","maxC":26.9,"minC":17.6,"rainProbabilityPercent":82,"uvIndexMax":8.2,"sunrise":"05:50","sunset":"17:55"},"tomorrow":{"date":"2026-09-29","weekday":"martes","maxC":29.6,"minC":17.2,"rainProbabilityPercent":51,"uvIndexMax":9.7,"condition":"llovizna","sunrise":"05:50","sunset":"17:54"},"airQuality":{"usAqi":28,"category":"buena","pm25":8,"pm10":8.1},"authority":"open_meteo_forecast_v1"}}""";

    private const string Patatas =
        """{"kind":"operation","operation":"task.create","polarity":"success","verified":true,"succeeded":true,"observed":{"taskId":"32bd0da8-7a94-49a2-9d21-2894ddd679d8","title":"patatas y patatas y huevos","details":"lista de deseos","completed":false,"deleted":false,"createdAtUtc":"2026-09-29T03:43:11.8097653+00:00","updatedAtUtc":"2026-09-29T03:43:11.8097653+00:00","version":1}}""";

    private const string TaylorSwift =
        """{"kind":"operation","operation":"web.news.headlines","polarity":"success","verified":true,"succeeded":true,"observed":{"version":1,"topic":"Taylor Swift","edition":"es-419/CL","count":5,"headlines":[{"title":"Taylor Swift supera a Beyoncé como la artista más premiada de los MTV VMA 2026","source":"CNN en Español","publishedAt":"Mon, 28 Sep 2026 03:46:00 GMT"},{"title":"Taylor Swift y Lisa hacen historia y Madonna reina otra vez: los ganadores de los MTV VMA 2026","source":"BioBioChile","publishedAt":"Mon, 28 Sep 2026 03:57:28 GMT"},{"title":"Dakota Johnson tiene malas noticias para los fans que esperaban ver fotos de la boda de Taylor Swift","source":"HOLA","publishedAt":"Mon, 28 Sep 2026 22:40:48 GMT"},{"title":": Taylor Swift abre su intimidad con Travis Kelce","source":"MUNDIARIO","publishedAt":"Tue, 29 Sep 2026 00:14:30 GMT"},{"title":"Taylor Swift lanza video de ‘Patient Zero’ con giro en la trama inquietante: Dónde verlo","source":"Billboard","publishedAt":"Mon, 28 Sep 2026 15:20:17 GMT"}],"authority":"google_news_rss_es419_cl"}}""";

    private const string Limit = """{"kind":"failure","polarity":"failure","cause":"out_of_catalog"}""";

    // D-s024 q4: the person's own «que hice» in the verified details is not BAXY's act, so «la lista que creaste la
    // semana pasada» does not tell BAXY's add as the person's.
    [Test]
    public void ThePersonsOwnVerbInTheReadIsNotBaxysAct()
    {
        var draft = new UserMessageDraft(WishlistIphone, "status", null);
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "He añadido el iPhone a la lista de deseos que creaste la semana pasada.",
                draft,
                "Añade un iPhone a mi lista de deseos que hice la semana pasada."),
            Is.Null);
    }

    // A prose source still names BAXY's act, and telling it as the person's is still refused.
    [Test]
    public void BaxysProseActToldAsThePersonsIsStillWrongActor()
    {
        var draft = new UserMessageDraft("Abrí Chrome.", "status", null);
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason("Abriste Chrome.", draft, "abre chrome"),
            Is.EqualTo("wrong_actor"));
    }

    // The texts the mind now publishes for the other DEV-D ⚠: the shell accepts each as it stands.
    [TestCase(Limit, "error", "prende la luz de la cosina", "No enciendo la luz de la cocina.")]
    [TestCase(Limit, "error", "prende la luz de la cosina", "Eso no lo hago.")]
    [TestCase(Limit, "error", "recomprar el último billete de tren a huesca", "No recomprobo billetes de tren.")]
    [TestCase(ChipsDeleted, "status", "Nevermind I do not want chips on there",
        "I have removed chips from your shopping list.")]
    [TestCase(SearchUnavailable, "error", "Oh, I meant to search for valet parking at the Kenzi Rose Garden.",
        "The valet parking information at the Kenzi Rose Garden could not be looked up right now. I can open the search page in your web browser for you.")]
    [TestCase(SearchUnavailable, "error", "Oh, I meant to search for valet parking at the Kenzi Rose Garden.",
        "I couldn't look it up right now; I can open it in your web browser.")]
    [TestCase(WeatherUnavailable, "error",
        "I'm visiting Martinez soon and would like the check the weather there please",
        "I checked the weather service for Martinez, but it did not respond, so no forecast was available.")]
    [TestCase(WeatherUnavailable, "error",
        "I'm visiting Martinez soon and would like the check the weather there please",
        "I couldn't read the weather: the weather service didn't answer.")]
    [TestCase(SeekUnverified, "error", "Diez", "No pude confirmar el salto en la reproducción.")]
    [TestCase(Medellin, "status",
        "Parce, mi hermana vive en Medellín y va a salir en moto en un rato, ¿sabes si allá está lloviendo ahorita?",
        "No está lloviendo ahora en Medellín.")]
    [TestCase(Medellin, "status",
        "Parce, mi hermana vive en Medellín y va a salir en moto en un rato, ¿sabes si allá está lloviendo ahorita?",
        "En Medellín hay 18,9 °C ahora, parcialmente nublado; no llueve ahora.")]
    [TestCase(Patatas, "status", "Pon patatas y patatas y huevos en la lista de deseos.",
        "Añadí «patatas y patatas y huevos».")]
    [TestCase(TaylorSwift, "status", "Noticias sobre Taylor Swift.",
        "Taylor Swift supera a Beyoncé como la artista más premiada de los MTV VMA 2026; Taylor Swift y Lisa hacen historia y Madonna reina otra vez: los ganadores de los MTV VMA 2026; Taylor Swift abre su intimidad con Travis Kelce.")]
    [TestCase(TaylorSwift, "status", "Noticias sobre Taylor Swift.",
        "Titulares sobre Taylor Swift: «Taylor Swift supera a Beyoncé como la artista más premiada de los MTV VMA 2026»; «Taylor Swift y Lisa hacen historia y Madonna reina otra vez: los ganadores de los MTV VMA 2026»; «Dakota Johnson tiene malas noticias para los fans que esperaban ver fotos de la boda de Taylor Swift».")]
    public void TheMindsNewFinalIsAcceptedByTheShell(string source, string intent, string userText, string reply)
    {
        var draft = new UserMessageDraft(source, intent, null);
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(reply, draft, userText), Is.Null);
    }
}
