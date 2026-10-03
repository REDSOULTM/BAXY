using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// M139 (DEV-G v4n): turns that ended in ⚠ because this twin refused what the mind composed.
/// <list type="bullet">
/// <item>G-w36-t4/t5: «Está sonando Chachachá de Jósean Log.» was refused as internal_code — the song's title,
/// «chachachá», read as a stuttered word. A word the verified result observed is data.</item>
/// <item>G-w35-t1: «¿A qué hora te gustaría que te lo recuerde?» for a reminder whose missing value is its time was
/// refused as asks_to_invent_clock; asking the declared missing time is the clarification itself.</item>
/// <item>G-s037: the answer from memory over a verified search that did not state it («No pude comprobarlo; de memoria,
/// puede no ser exacto: … no puedo decirte cuándo es este fin de semana sin más detalles.») was refused as
/// reversed_result; not being able to tell from memory is the scope of memory, not a failed search.</item>
/// </list>
/// </summary>
[TestFixture]
public sealed class M139RedaccionTests
{
    private const string MediaControl =
        """{"kind":"operation","operation":"media.control","polarity":"success","verified":true,"succeeded":true,"observed":{"version":1,"sourceAppUserModelId":"SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify","title":"Chachachá","artist":"Jósean Log","playbackStatus":"playing","authority":"windows_smtc"}}""";

    private const string MediaStatus =
        """{"kind":"operation","operation":"media.status","polarity":"success","verified":true,"succeeded":true,"observed":{"version":1,"sourceAppUserModelId":"SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify","title":"Chachachá","artist":"Jósean Log","album":"Háblate de Mí","playbackStatus":"playing","authority":"windows_smtc_current_session_read"}}""";

    private const string OtherSong =
        """{"kind":"operation","operation":"media.status","polarity":"success","verified":true,"succeeded":true,"observed":{"version":1,"sourceAppUserModelId":"SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify","title":"Despacito","artist":"Luis Fonsi","playbackStatus":"playing","authority":"windows_smtc_current_session_read"}}""";

    private const string AmericaSearch =
        """{"kind": "operation", "operation": "web.search", "polarity": "success", "verified": true, "succeeded": true, "observed": {"version": 1, "query": "aq hora juega el america este fin d semana??", "count": 5, "results": [{"title": "Cuándo juega y dónde ver al América: Día, hora, canal de TV y streaming ...", "url": "https://www.sportingnews.com/mx/futbol/news/como-ver-al-america-horario-canal-tv-streaming-alineaciones-partido/mrbto5htextzpcg2oeezqegl", "snippet": "Los detalles para ver el próximo partido del América : día del juego, horario, qué canales lo transmiten por televisión y qué plataformas por streaming online. … ¿Cuándo juega, cómo y dónde ver al América?"}, {"title": "¿Por qué América no juega este fin de semana la jornada 6 del Apertura ...", "url": "https://americamonumental.bolavip.com/noticias/por-que-america-no-juega-este-fin-de-semana-la-jornada-6-del-apertura-2026-ante-xolos", "snippet": "No obstante, este fin de semana el equipo de Guillermo Almada no verá acción en el futbol mexicano, por lo que su siguiente partido en el Apertura 2026 será el Clásico Joven ante Cruz Azul el próximo sábado 12 de septiembre en la cancha del Estadio Azteca. Esto debido a que América no jugará la jornada 7 del torneo en tiempo y forma, debido a que se enfrentará a León en el partido ... … © Imago 7 ¿Por qué América no juega este fin de semana la jornada 7 del Apertura 2026 ante Tijuana?"}, {"title": "cuándo juega el América: calendario, horarios y dónde ver", "url": "https://mipaoverseas.com/cuando-juega-el-america-calendario-horarios-ver/", "snippet": "¿Te preguntas cuándo juega el América este fin de semana o la próxima jornada? Si eres de los que planifica reuniones, compra boletos o simplemente no quiere perderse el partido en vivo, aquí tienes toda la información práctica y contexto sobre por qué esta búsqueda está en auge ahora mismo. Por qué cuándo juega el América está en tendencia Hay dos razones claras para el pico de ... … Para saber cuándo juega el América confío en dos fuentes principales: el sitio oficial de la liga y la página del club. Sigue estos pasos para no perderte cuándo juega el América y disfrutar el evento sin contratiempos: Si quieres, guarda este artículo o comparte el enlace con amigos que preguntan “ cuándo juega el América ” cada vez que hay jornada."}, {"title": "América vs. Puebla: dónde y a qué hora ver EN VIVO", "url": "https://www.mediotiempo.com/futbol/liga-mx/a-que-hora-juega-america-vs-puebla-donde-ver-jornada-6-liga-mx-2026", "snippet": "Conoce los horarios, canales en vivo y pronósticos de América vs. Puebla Jornada 6 Liga MX 2026."}, {"title": "Liga MX: ¿Cuándo se juega el América vs Tijuana?", "url": "https://www.estadiodeportes.mx/ligamx/cuando-jugara-america-su-partido-pendiente-contra-xolos-20260907-0038.html", "snippet": "La Leagues Cup terminó y, con ello, dejó partidos pendientes en la Liga MX, debido a los juegos por el tercer lugar y la gran final que se llevaron a cabo en Houston. América fue uno de los afectados, por lo que tuvo que reprogramar su partido pendiente ante Xolos de Tijuana de la Jornada 7 y ya se tiene fecha y hora para disputarlo."}], "authority": "duckduckgo_lite_https"}}""";

    private const string Predial = "oye, ponme un recordatorio pa mañana de pagar el predial, que ya se me pasó una vez";

    private const string DiscordMicAlreadyMuted =
        """{"kind":"status","polarity":"success","cause":"mission_completed","stepCount":2,"steps":["{\"kind\":\"operation\",\"operation\":\"app.open\",\"polarity\":\"success\",\"verified\":true,\"succeeded\":true,\"observed\":{\"appId\":\"Discord\",\"displayName\":\"Discord\",\"alreadyRunning\":false,\"windowHandle\":2230094},\"readOnly\":false}","{\"kind\":\"operation\",\"operation\":\"audio.microphone.mute\",\"polarity\":\"failure\",\"verified\":false,\"succeeded\":false,\"error\":\"microphone_already_muted\",\"readOnly\":false}"],"completedRequest":"Abre Discord y silencia el micrófono."}""";

    private const string DiscordMicMuted =
        """{"kind":"status","polarity":"success","cause":"mission_completed","stepCount":2,"steps":["{\"kind\":\"operation\",\"operation\":\"app.open\",\"polarity\":\"success\",\"verified\":true,\"succeeded\":true,\"observed\":{\"appId\":\"Discord\",\"displayName\":\"Discord\",\"alreadyRunning\":false,\"windowHandle\":2230094},\"readOnly\":false}","{\"kind\":\"operation\",\"operation\":\"audio.microphone.mute\",\"polarity\":\"success\",\"verified\":true,\"succeeded\":true,\"observed\":{\"muted\":true},\"readOnly\":false}"],"completedRequest":"Abre Discord y silencia el micrófono."}""";

    // G-s021 «bro abre Discord y mutea el micro, que viene mi roommate»: the drafts the mind wrote (the first with its
    // missing accent), and the same told in other words and in English.
    [TestCase("Abri Discord y el micrófono ya estaba silenciado, así que no hubo cambio.")]
    [TestCase("He abierto Discord, pero el micrófono ya estaba silenciado por lo que no ha podido cambiar el estado.")]
    [TestCase("Abrí Discord; el micrófono ya estaba en silencio, así que no hubo ningún cambio.")]
    [TestCase("I opened Discord; the microphone was already muted, so nothing changed.")]
    public void TheMissionTellsTheStateThatAlreadyHeld(string reply)
    {
        var draft = new UserMessageDraft(DiscordMicAlreadyMuted, "status", null);
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(reply, draft, "bro abre Discord y mutea el micro, que viene mi roommate", null),
            Is.Null);
    }

    // What does not change: with the microphone muted by this mission, «nothing changed» reverses it.
    [Test]
    public void NothingChangedOverAnEffectThatHappenedIsStillReversed()
    {
        var draft = new UserMessageDraft(DiscordMicMuted, "status", null);
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "Abrí Discord y el micrófono ya estaba silenciado, así que no hubo cambio.", draft,
                "bro abre Discord y mutea el micro", null),
            Is.Not.Null);
    }

    // G-w36-t4 «esa no me late, pásale a la que sigue», G-w36-t5 «cómo se llama esta rola otra vez?».
    [TestCase(MediaControl, "esa no me late, pásale a la que sigue", "Está sonando Chachachá de Jósean Log.")]
    [TestCase(MediaStatus, "cómo se llama esta rola otra vez?", "Está sonando «Chachachá» de Jósean Log.")]
    [TestCase(MediaStatus, "what's this song called again?", "This is \"Chachachá\" by Jósean Log.")]
    [TestCase(MediaStatus, "y de qué disco es", "Es «Chachachá», del disco Háblate de Mí.")]
    public void ATitleTheResultObservedIsNoStutter(string source, string request, string reply)
    {
        var draft = new UserMessageDraft(source, "status", null);
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(reply, draft, request, null), Is.Null);
    }

    // What does not change: the same word with a result that never observed it, and a stutter of the writer's own.
    [TestCase(OtherSong, "Está sonando Chachachá de Jósean Log.")]
    [TestCase(MediaStatus, "Está sonando Chachachá; lo cerrarrar.")]
    public void AStutterTheResultDidNotObserveIsStillRefused(string source, string reply)
    {
        var draft = new UserMessageDraft(source, "status", null);
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(reply, draft, "qué suena", null),
            Is.EqualTo("internal_code"));
    }

    // G-w35-t1: the mind's question, the composer's question, and the same ask in other words and in English.
    [TestCase(Predial, "¿A qué hora te gustaría que sea el recordatorio de pago del predial para mañana?", "due_time")]
    [TestCase(Predial, "¿A qué hora te gustaría que te lo recuerde?", "due_time")]
    [TestCase("remind me tomorrow to renew the car insurance", "What time would you like the reminder tomorrow?", "due_time")]
    [TestCase("ponme una alarma para mañana", "¿A qué hora te gustaría la alarma?", "alarm_time")]
    [TestCase(Predial, "¿A qué hora te gustaría que te lo recuerde?", "what_to_remind_or_notify_about, due_time")]
    public void AskingTheDeclaredMissingTimeIsTheClarification(string request, string question, string missing)
    {
        Assert.That(
            UserMessagePolicy.ConversationReplyRejectionReason(
                request, question, clarification: true, hasRequiredInput: true, missingFields: [missing]),
            Is.Null);
    }

    // What does not change: with no time declared missing, a question that asks the person to choose the hour is
    // still a clock to invent.
    [TestCase("ponme una alarma para mañana", "¿A qué hora te gustaría la alarma?")]
    [TestCase(Predial, "¿A qué hora te gustaría que te lo recuerde?")]
    public void WithoutADeclaredTimeTheClockIsStillNotAsked(string request, string question)
    {
        Assert.That(
            UserMessagePolicy.ConversationReplyRejectionReason(request, question, clarification: true),
            Is.EqualTo("asks_to_invent_clock"));
    }

    // G-s037 «aq hora juega el america este fin d semana??»: the mind's from_memory draft, word for word, and variants.
    [TestCase("No pude comprobarlo; de memoria, puede no ser exacto: el horario de los partidos del América depende de la "
        + "fecha específica y la liga en la que juegue, por lo que no puedo decirte cuándo es este fin de semana sin más "
        + "detalles.")]
    [TestCase("No pude comprobarlo; de memoria, puede no ser exacto: el América suele jugar los sábados por la noche, "
        + "pero no puedo asegurarte la hora de este fin de semana.")]
    [TestCase("I couldn't check this; from memory, it may not be exact: América usually plays on Saturday nights, but I "
        + "can't tell you this weekend's kickoff time.")]
    public void NotKnowingFromMemoryIsTheScopeOfMemory(string reply)
    {
        var draft = new UserMessageDraft(AmericaSearch, "status", null);
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(reply, draft, "aq hora juega el america este fin d semana??", null),
            Is.Null);
    }

    // What does not change: without the from-memory notice, an inability told over a verified search is reversed.
    [TestCase("No puedo decirte cuándo juega el América este fin de semana.")]
    [TestCase("No pude buscar el partido del América.")]
    public void AnInabilityWithoutTheNoticeIsStillAReversedSearch(string reply)
    {
        var draft = new UserMessageDraft(AmericaSearch, "status", null);
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(reply, draft, "aq hora juega el america este fin d semana??", null),
            Is.EqualTo("reversed_result"));
    }

    // G-w33-t4: «ya que no puedes» is no question about BAXY's limits; the alarm goes to the mind.
    [TestCase("bueno, ya que no puedes con eso, al menos ponme una alarma para las 9 de la noche", false)]
    [TestCase("puesto que no puedes abrir eso, ponme música", false)]
    [TestCase("dado que no puedes con el aire, apaga la pantalla", false)]
    // What does not change.
    [TestCase("¿qué no puedes hacer?", true)]
    [TestCase("dime qué no puedes", true)]
    [TestCase("¿cuáles son tus límites?", true)]
    public void AConnectiveQueAsksNothingAboutBaxy(string text, bool asks)
    {
        Assert.That(UserMessagePolicy.IsSelfDescriptionQuestion(text), Is.EqualTo(asks));
    }
}
