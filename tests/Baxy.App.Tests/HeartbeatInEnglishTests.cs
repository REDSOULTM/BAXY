using System.Text.Json.Nodes;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// ING6 (owner's decision of 2026-11-13, «with English, not a word of Spanish in what the model reads»; INFORME_ING5
/// §4.8.2): the heartbeat's moment is written by the App and read by the model as it is (the mind's beat_message). Its
/// own words follow the language: the weekday, what the person is doing, the rows that say which windows were not
/// listed, the mark of a message cut short and the change a downloaded file is told as. In Spanish each is the one of
/// always, to the byte. Titles, processes and what the person said are theirs and stay as they are.
/// </summary>
[TestFixture]
public sealed class HeartbeatInEnglishTests
{
    // 2026-11-14 is a Saturday.
    private static readonly DateTimeOffset Saturday = new(2026, 11, 14, 9, 30, 0, TimeSpan.Zero);

    private static readonly string[] Activities =
    [
        HeartbeatMoment.Free, HeartbeatMoment.Away, HeartbeatMoment.InCall, HeartbeatMoment.Playing,
        HeartbeatMoment.Watching, HeartbeatMoment.Unknown,
    ];

    // Words the fixture gives (a file's name, the person's message), and those of the change a file is told as, which
    // was already written in English but for the folder's name.
    private const string Data = "informe pdf file appeared in " + LongBody;

    private const string LongBody =
        "uno dos tres cuatro cinco seis siete ocho nueve diez uno dos tres cuatro cinco seis siete ocho nueve diez "
        + "uno dos tres cuatro cinco seis siete ocho nueve diez uno dos tres cuatro cinco seis siete ocho nueve diez "
        + "uno dos tres cuatro cinco seis siete ocho nueve diez";

    private static string[] OwnTexts(bool english)
    {
        JsonObject cloaked = HeartbeatMoment.CloakedNote(3, english);
        JsonObject unread = HeartbeatMoment.UnreadWindowsNote(english);
        return
        [
            HeartbeatMoment.Weekday(Saturday, english),
            (string?)cloaked["title"] ?? string.Empty,
            (string?)cloaked["process"] ?? string.Empty,
            (string?)unread["title"] ?? string.Empty,
            (string?)unread["process"] ?? string.Empty,
            HeartbeatMoment.Shown(LongBody, english),
            Heartbeat.FileAppearedNote("informe.pdf", english),
            .. Activities.Select(activity => (string?)HeartbeatMoment.AsTheModelReadsIt(
                new JsonObject { ["owner_activity"] = activity }, english)["owner_activity"] ?? string.Empty),
        ];
    }

    [Test]
    public void InSpanishTheMomentIsTheOneOfAlways()
    {
        var moment = new JsonObject { ["owner_activity"] = HeartbeatMoment.Playing, ["weekday"] = "sábado" };

        Assert.Multiple(() =>
        {
            Assert.That(OwnTexts(english: false), Is.EqualTo(new[]
            {
                "sábado",
                "y 3 más que Windows oculta (encubiertas: no se ven en la pantalla)",
                "sin leer",
                "las ventanas no se pudieron leer",
                "sin leer",
                LongBody[..200] + "… (cortado)",
                "file appeared in Descargas: informe.pdf",
                "libre", "ausente", "llamada", "jugando", "viendo", "desconocido",
            }));
            // The same object, untouched: what the App sends the mind in Spanish is what it always sent.
            Assert.That(HeartbeatMoment.AsTheModelReadsIt(moment, english: false), Is.SameAs(moment));
            Assert.That(HeartbeatMoment.Shown("corto", english: false), Is.EqualTo("corto"));
        });
    }

    [Test]
    public void InEnglishTheMomentKeepsNoneOfItsSpanishWords()
    {
        string[] spanish = OwnTexts(english: false);
        string[] english = OwnTexts(english: true);
        var moment = new JsonObject
        {
            ["owner_activity"] = HeartbeatMoment.Playing,
            ["foreground"] = new JsonObject { ["title"] = "Notas", ["process"] = "notas" },
        };

        JsonObject read = HeartbeatMoment.AsTheModelReadsIt(moment, english: true);

        Assert.Multiple(() =>
        {
            Assert.That(ModelTextsInEnglishTests.SpanishWordsIn(string.Join('\n', english), string.Join('\n', spanish), Data),
                Is.Empty, string.Join('\n', english));
            Assert.That(english, Is.EqualTo(new[]
            {
                "Saturday",
                "and 3 more that Windows hides (cloaked: they are not seen on the screen)",
                "not read",
                "the windows could not be read",
                "not read",
                LongBody[..200] + "… (cut off)",
                "file appeared in Downloads: informe.pdf",
                "free", "away", "on a call", "gaming", "watching", "unknown",
            }));
            // The App goes on reading the activity by its own key: what the model reads is a copy.
            Assert.That((string?)moment["owner_activity"], Is.EqualTo(HeartbeatMoment.Playing));
            Assert.That((string?)read["owner_activity"], Is.EqualTo("gaming"));
            Assert.That(read["foreground"]?.ToJsonString(), Is.EqualTo(moment["foreground"]?.ToJsonString()));
            // An activity that is none of the App's (a scene's own word) is left as it came.
            Assert.That((string?)HeartbeatMoment.AsTheModelReadsIt(new JsonObject { ["owner_activity"] = "x" }, english: true)["owner_activity"],
                Is.EqualTo("x"));
        });
    }
}
