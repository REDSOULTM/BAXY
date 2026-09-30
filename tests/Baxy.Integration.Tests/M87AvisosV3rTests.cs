using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// M87: the shell's side of the five turns the official-window DEV-D run v3r (development set) ended unpublished. The
/// sources and replies are the ones that run recorded (window/v3r-devD/compose-audit.jsonl and events.jsonl).
/// </summary>
[TestFixture]
public sealed class M87AvisosV3rTests
{
    // 2026-09-30T20:14:24Z at UTC-3: 17:14 on this PC.
    private const string ClockAtSeventeenFourteen =
        """{"kind":"operation","operation":"system.time","polarity":"success","verified":true,"succeeded":true,"observed":{"version":1,"utc":"2026-09-30T20:14:24.7359239+00:00","localUtcOffsetMinutes":-180}}""";

    // 2026-09-30T20:13:07Z at UTC-3: Wednesday 17:13.
    private const string WednesdayClock =
        """{"kind":"operation","operation":"system.time","polarity":"success","verified":true,"succeeded":true,"observed":{"version":1,"utc":"2026-09-30T20:13:07.3962994+00:00","localUtcOffsetMinutes":-180}}""";

    // D-s025 (t25): the mind's deterministic final, the clock forty minutes on, was filtered here as a plain clock
    // request (missing_literal_fact: 17:14 not stated) because this twin did not read «si pasan cuarenta minutos».
    [Test]
    public void TheClockAfterASpanThatPassesIsTheAnswer()
    {
        const string Request = "si pasan cuarenta minutos, ¿qué hora será?";
        var draft = new UserMessageDraft(ClockAtSeventeenFourteen, "status", null);
        Assert.That(UserMessagePolicy.IsLaterClockRequest(Request), Is.True);
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason("Serán las 17:54.", draft, Request), Is.Null);
        // Asked the time now, a clock that is not this PC's is still invented.
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason("Serán las 17:54.", draft, "¿qué hora es?"),
            Is.EqualTo("missing_literal_fact"));
    }

    // The heads of the mind's semantic.temporal._LATER_BY, one by one.
    [TestCase("si pasan cuarenta minutos, ¿qué hora será?", true)]
    [TestCase("cuando pasen dos horas, ¿qué hora será?", true)]
    [TestCase("¿qué hora será pasadas tres horas?", true)]
    [TestCase("¿qué hora será de aquí a doce minutos?", true)]
    [TestCase("what time will it be after 20 minutes?", true)]
    [TestCase("what time will it be if another two hours pass?", true)]
    [TestCase("¿qué hora será en Tokio?", false)]
    [TestCase("¿qué hora es?", false)]
    public void TheLaterClockReaderMatchesTheMind(string request, bool later)
    {
        Assert.That(UserMessagePolicy.IsLaterClockRequest(request), Is.EqualTo(later));
    }

    // D-s001 (t1): the mind refused its own three drafts; the ones that state today's weekday and the hours left are
    // accepted here too, and the weekday stays owed (the mind's missing_name, this side's missing_literal_fact).
    [TestCase("Hoy es miércoles y quedan 54 horas y 46 minutos para el fin de semana.")]
    [TestCase("Hoy es miércoles y faltan 54 horas y 46 minutos para el fin de semana.")]
    [TestCase("Hoy es miércoles; quedan 54 h 46 min para el fin de semana.")]
    public void TheHoursLeftUntilTheWeekendWithTodaysWeekdayArePublished(string reply)
    {
        const string Request = "¿cuántas horas quedan para el finde?";
        var draft = new UserMessageDraft(WednesdayClock, "status", null);
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(reply, draft, Request), Is.Null);
    }

    [Test]
    public void TheHoursLeftWithoutTodaysWeekdayStayRefused()
    {
        var draft = new UserMessageDraft(WednesdayClock, "status", null);
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "Quedan 54 horas y 46 minutos para el fin de semana.", draft, "¿cuántas horas quedan para el finde?"),
            Is.EqualTo("missing_literal_fact"));
    }

    private const string ScaryMoviesSearch =
        """{"kind":"operation","operation":"web.search","polarity":"success","verified":true,"succeeded":true,"observed":{"version":1,"query":"scary movies","count":2,"results":[{"title":"Scary Movie","url":"https://es.wikipedia.org/wiki/Scary_Movie","snippet":"Scary Movie (titulada Scary Movie: Una película de miedo en Hispanoamérica) es una película estadounidense de humor negro del año 2000, dirigida por Keenen Ivory Wayans y escrita por sus hermanos Shawn Wayans y Marlon Wayans."},{"title":"Scary Movie 5","url":"https://es.wikipedia.org/wiki/Scary_Movie_5","snippet":"Scary Movie 5 (estilizado como Scary MoVie) es una película estadounidense de humor negro de 2013."}],"authority":"wikipedia_es_api"}}""";

    private const string DramaFilmSearch =
        """{"kind":"operation","operation":"web.search","polarity":"success","verified":true,"succeeded":true,"observed":{"version":1,"query":"a drama film online","count":1,"results":[{"title":"Drama histórico (cinematografía)","url":"https://es.wikipedia.org/wiki/Drama_hist%C3%B3rico_(cinematograf%C3%ADa)","snippet":"Se conoce como drama histórico (también conocido como drama de época) a una obra ambientada en un período de tiempo pasado, generalmente utilizada en el contexto del cine y la televisión."}],"authority":"wikipedia_es_api"}}""";

    // D-p29-t2 (t225), D-p23-t2 (t200) and D-p24-t1 (t204): the answers from memory the mind published unjudged, asked
    // in three forms at once; this side refused them and the turns ended in ⚠. Those refusals stand (the mind now makes
    // the same judgement before publishing); the answer in the one form asked is accepted.
    [Test]
    public void TheRecordedAnswersFromMemoryStayRefused()
    {
        const string ScaryRecipe =
            "I couldn't check this; from memory, it may not be exact:\n\n**Scary Movies**\n\n1.  The Conjuring\n2.  Hereditary\n"
            + "3.  The Exorcist\n\n**A recipe for a spooky atmosphere**\n\nIngredients:\n- Dimmed lights\n- A flickering candle\n\n"
            + "Steps:\n1. Turn off the main lights and leave only a single candle burning in the center of the room.\n"
            + "2. Lower the volume of any background music to a barely audible hum or rumble.";
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                ScaryRecipe, new UserMessageDraft(ScaryMoviesSearch, "status", null), "Search for scary movies."),
            Is.EqualTo("missing_literal_fact"));
        const string DramaRecipe =
            "I couldn't check this; from memory, it may not be exact: I cannot browse the live internet to find specific "
            + "drama films for you right now. However, I can recall a classic example from my training data.";
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                DramaRecipe, new UserMessageDraft(DramaFilmSearch, "status", null), "Look for a drama film."),
            Is.EqualTo("reversed_result"));
        const string ElijahWoodSteps =
            "I couldn't check this; from memory, it may not be exact:\n\n1.  **The Lord of the Rings Trilogy**\n\n"
            + "**Steps to find more:**\n1.  Visit a streaming service like Netflix, Hulu, or Disney+.\n"
            + "2.  Filter results by \"Top Rated\" or \"User Score\" to find the highest quality options.";
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                ElijahWoodSteps, new UserMessageDraft(ScaryMoviesSearch, "status", null),
                "I am in a mood to watch movie online and I need your help to search for a nice Fantasy Movie like Elijah Wood."),
            Is.EqualTo("unsafe_language"));
    }

    [Test]
    public void AnAnswerFromMemoryInTheFormAskedIsPublished()
    {
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "I couldn't check this; from memory, it may not be exact:\n1. The Conjuring (2013)\n2. Hereditary (2018)\n"
                + "3. The Exorcist (1973)",
                new UserMessageDraft(ScaryMoviesSearch, "status", null), "Search for scary movies."),
            Is.Null);
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "I couldn't check this; from memory, it may not be exact: The Shawshank Redemption (1994) is a drama film "
                + "about two prisoners who become friends over many years.",
                new UserMessageDraft(DramaFilmSearch, "status", null), "Look for a drama film."),
            Is.Null);
    }
}
