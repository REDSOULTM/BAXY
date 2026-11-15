using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;
using Baxy.Contracts;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// ING5B (owner's decision of 2026-11-13, ENCARGO_ING5: «with English, not a word of Spanish in what the model
/// reads»; INFORME_ING5 §2.3): the texts the App itself writes for the model follow the language setting. Each test
/// takes a real body of the App in both languages: the Spanish one is the one of always, and none of the words the
/// Spanish projection puts (those that are not the fixture's own data) is in the English one.
/// </summary>
[TestFixture]
public sealed partial class ModelTextsInEnglishTests
{
    // Words the two languages share: the names the tools take (window, wanted, lines…) and words written alike.
    private static readonly HashSet<string> Shared = new(StringComparer.Ordinal)
    {
        "window", "app_open", "appId", "place", "placeValue", "wanted", "includeText", "lines", "label", "OCR", "Error",
        "control", "modal", "no", "a", "BAXY", "Windows", "ext", "editor", "terminal", "cursor", "decimal",
    };

    // A look with all the reader can say of a window, its controls and its text by columns; the data are no language's.
    private const string Whole =
        "{\"version\":2,\"ok\":true,\"error\":\"E_SAMPLE\"," +
        "\"window\":{\"title\":\"Notes\",\"process\":\"notes\",\"hwnd\":77,\"foreground\":false," +
        "\"coveredBy\":{\"title\":\"Mail\"},\"modal\":true,\"shownFromMinimized\":true,\"protected\":true," +
        "\"elevated\":true,\"reopensUnraised\":true," +
        "\"focused\":{\"kind\":\"Edit\",\"name\":\"Body\",\"value\":null,\"i\":0,\"caret\":\"end\"," +
        "\"text\":\"C:\\\\x>ver\",\"textCut\":true}," +
        "\"fileDialog\":{\"folder\":\"C:\\\\Users\\\\x\\\\Docs\",\"name\":\"list\",\"nameIndex\":21," +
        "\"path\":\"C:\\\\Users\\\\x\\\\Docs\\\\list.txt\",\"accept\":\"Save\",\"acceptIndex\":22}}," +
        "\"place\":{\"application\":\"Steam\",\"name\":\"store\",\"shown\":\"store.steampowered.com\"}," +
        "\"controls\":[" +
        "{\"i\":0,\"kind\":\"Edit\",\"name\":\"Body\",\"nameCut\":4,\"zone\":\"TL\",\"value\":\"abc\",\"valueCut\":7," +
        "\"state\":\"focused\",\"itemType\":\"Row\",\"repeated\":2,\"shortcut\":\"Ctrl+B\"}," +
        "{\"i\":1,\"kind\":\"TabItem\",\"name\":\"Inbox\",\"zone\":\"BR\",\"state\":\"selected\",\"value\":null}," +
        "{\"i\":2,\"kind\":\"Button\",\"name\":\"Send\",\"zone\":\"C\",\"state\":\"\",\"value\":null}]," +
        "\"controlCount\":9,\"wantedMissing\":[\"Draft\"]," +
        "\"disabled\":[{\"kind\":\"Button\",\"name\":\"Undo\"}],\"disabledCut\":true," +
        "\"partial\":true,\"frameOnly\":true,\"uiaFailed\":\"E_TREE\"," +
        "\"textOmittedLines\":12,\"textOmittedZones\":{\"L\":9,\"BL\":3},\"textOmittedListRows\":12,\"textRestWith\":\"lines\"," +
        "\"text\":{\"TL\":[\"Inbox\",\"Kim 10:02\"]}," +
        "\"textColumns\":[{\"zone\":\"L\",\"blocks\":[[\"Inbox\",\"Inbox\",\"Inbox\",\"Inbox\",\"3 new\"]]}," +
        "{\"zone\":\"C\",\"blocks\":[[\"Kim 10:02\",\"See you\"],[\"Lee 10:05\",\"OK\"]]}," +
        "{\"zone\":\"R\",\"toBottomEdge\":true,\"blocks\":[[\"Kim 10:02\"],[\"Lee 10:05\",\"Send it now 12\"]]}]," +
        "\"textLanguages\":[\"en-US\"]," +
        "\"textAuthority\":\"windows_media_ocr_lines\",\"authority\":\"windows_uia_snapshot_ocr_zones\"}";

    // A window that gives no controls, read by its text in bands, with a system tool's mark and no place.
    private const string Drawn =
        "{\"version\":2,\"ok\":true,\"error\":\"\"," +
        "\"window\":{\"title\":\"Game\",\"process\":\"game\",\"hwnd\":5,\"foreground\":true,\"systemTool\":true," +
        "\"elevated\":true," +
        "\"focused\":{\"kind\":\"Edit\",\"name\":\"Body\",\"value\":null,\"i\":0,\"caret\":\"selection\",\"text\":\"x\"}," +
        "\"fileDialog\":{\"shown\":\"This PC\",\"accept\":\"Open\"}}," +
        "\"controls\":[],\"controlCount\":0," +
        "\"text\":{\"T\":[\"LIBRARY\"],\"C\":[\"Play 12\"],\"B\":[\"Friends 3\"]}," +
        "\"textAuthority\":\"windows_media_ocr_lines\",\"authority\":\"windows_uia_snapshot_ocr_zones\"}";

    // The same without its text: not read, and the reader that could not read it; a caret at the start and in the middle.
    private const string NotRead =
        "{\"version\":2,\"ok\":true,\"error\":\"\"," +
        "\"window\":{\"title\":\"Notes\",\"process\":\"notes\",\"hwnd\":7,\"foreground\":true," +
        "\"focused\":{\"kind\":\"Edit\",\"name\":\"Body\",\"value\":null,\"i\":0,\"caret\":\"CARET\"}," +
        "\"fileDialog\":{\"accept\":\"Open\"}}," +
        "\"place\":{\"application\":\"Configuración\",\"name\":\"sound\",\"shown\":\"Sound\"}," +
        "\"controls\":[],\"controlCount\":0,\"textAuthority\":\"AUTHORITY\",\"authority\":\"uia\"}";

    [TearDown]
    public void BackToSpanish() => UiLanguage.Use(UiLanguage.Spanish);

    private static IEnumerable<TestCaseData> Looks()
    {
        yield return new TestCaseData(Whole, null).SetName("LookWhole");
        yield return new TestCaseData(Whole, "store").SetName("LookAtThePlaceAsked");
        yield return new TestCaseData(Whole, "library").SetName("LookAtAnotherPlaceThanAsked");
        yield return new TestCaseData(Drawn, null).SetName("LookDrawn");
        yield return new TestCaseData(NotRead.Replace("CARET", "start", StringComparison.Ordinal)
            .Replace("AUTHORITY", "not_read", StringComparison.Ordinal), null).SetName("LookTextNotRead");
        yield return new TestCaseData(NotRead.Replace("CARET", "middle", StringComparison.Ordinal)
            .Replace("AUTHORITY", "unavailable", StringComparison.Ordinal), null).SetName("LookTextUnavailable");
    }

    [TestCaseSource(nameof(Looks))]
    public void ALookInEnglishHasNoneOfTheSpanishLooksWords(string lookJson, string? askedPlace)
    {
        string spanish = Look(lookJson, askedPlace, UiLanguage.Spanish);
        string english = Look(lookJson, askedPlace, UiLanguage.English);

        Assert.Multiple(() =>
        {
            // The places of an application are its data (ApplicationPlaces), the names app_open takes.
            string data = lookJson + " " + string.Join(' ', ApplicationPlaces.PlacesOf("Steam").Select(static place => place.Place));
            Assert.That(SpanishWordsIn(english, spanish, data), Is.Empty, english);
            Assert.That(english, Does.StartWith("Window «"));
            Assert.That(english, Does.Contain("\nControls"));
            // The same facts, line by line: only the words change.
            Assert.That(english.Split('\n'), Has.Length.EqualTo(spanish.Split('\n').Length));
        });
    }

    // What the answer check reads of a look (answer_check.py) has one fixed form in each language.
    [Test]
    public void TheMarksTheAnswerCheckReadsOfALookInEnglish()
    {
        string english = Look(Whole, null, UiLanguage.English);

        Assert.Multiple(() =>
        {
            Assert.That(english, Does.Contain("\n(text cut off: 12 lines read are not listed"));
            Assert.That(english, Does.Contain("\nText column 2 (center), block 1: Kim 10:02 | See you\n"));
            Assert.That(english, Does.Contain("\nControls (not the window's complete list: it may have more):\n"));
            Assert.That(english, Does.Contain("\n(+6 more, not listed because of the cap"));
            Assert.That(english, Does.Contain(" (name cut off: 4 characters missing)"));
            Assert.That(english, Does.Contain(" (value cut off: 7 characters missing)"));
            Assert.That(english, Does.Contain("\n(the reading was left incomplete: "));
            Assert.That(english, Does.Contain("\n(4 lines of text are not listed: "));
            Assert.That(english, Does.Contain("(notes, window 77)"));
        });
    }

    // What a switch of Privacidad that refuses a call is named: as the English view shows it (PrivacySection, OwnBrakes).
    [TestCase("web_disabled_by_owner", "Web search", "Búsqueda web")]
    [TestCase("weather_disabled_by_owner", "Weather", "Clima")]
    [TestCase("screen_disabled_by_owner", "Look at the screen", "Mirar la pantalla")]
    public void ACallAPrivacySwitchRefusesNamesTheSwitchInEnglish(string code, string english, string spanish)
    {
        string? inSpanish = (string?)JsonNode.Parse(NativeTurnLoop.Refused(code))?["next"];
        UiLanguage.Use(UiLanguage.English);
        string? inEnglish = (string?)JsonNode.Parse(NativeTurnLoop.Refused(code))?["next"];

        Assert.Multiple(() =>
        {
            Assert.That(inSpanish, Does.Contain($"the person switched «{spanish}» off"));
            Assert.That(inEnglish, Does.Contain($"the person switched «{english}» off").And.Not.Contain(spanish));
        });
    }

    // The session's internet exits (assistant.status): a step of an English view carries its words in the two languages
    // (FieldProductChannel.OnStepCompleted), and the log is read in the one in use.
    [Test]
    public void TheInternetLogIsReadInTheLanguageInUse()
    {
        var transcript = new FieldTranscript();
        transcript.You("x");
        transcript.Step(new JsonObject { ["id"] = "c1", ["net"] = "search «rain»", ["netEs"] = "búsqueda «rain»" });
        transcript.Words("Done.", null);

        string? inSpanish = Destination(OwnReadings.Internet(transcript.Items));
        UiLanguage.Use(UiLanguage.English);
        string? inEnglish = Destination(OwnReadings.Internet(transcript.Items));

        Assert.Multiple(() =>
        {
            Assert.That(inSpanish, Is.EqualTo("búsqueda «rain»"));
            Assert.That(inEnglish, Is.EqualTo("search «rain»"));
        });

        static string? Destination(Baxy.Kernel.Operations.OperationOutcome read) =>
            read.Result?.GetProperty("exits")[0].GetProperty("destination").GetString();
    }

    // ING6: what baxy-core writes for the model (the weather's sky and weekday, a window's mark, a reading's unit) is
    // written in another process: each request tells it the language in use; none in Spanish, the wire of always.
    [Test]
    public void ARequestToTheCoreSaysTheLanguageInUse()
    {
        PreparedOperation operation = PreparedOperation.Create("weather.current", new JsonObject());

        UiLanguage.Use(UiLanguage.Spanish);
        OperationRequest inSpanish = operation.CreateRequest();
        UiLanguage.Use(UiLanguage.English);
        OperationRequest inEnglish = operation.CreateRequest();

        Assert.Multiple(() =>
        {
            Assert.That(inSpanish.Language, Is.Null);
            Assert.That(System.Text.Encoding.UTF8.GetString(ProtocolJson.SerializeToUtf8Bytes(inSpanish)),
                Does.Not.Contain("language"));
            Assert.That(inEnglish.Language, Is.EqualTo(ProtocolLanguages.English));
        });
    }

    private static string Look(string lookJson, string? askedPlace, string language)
    {
        UiLanguage.Use(language);
        using JsonDocument look = JsonDocument.Parse(lookJson);
        var response = new OperationResponse(ProtocolTypes.OperationResponse, Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"), Guid.NewGuid().ToString("D"), "completed", "{\"status\":\"completed\"}",
            Verified: true, Replayed: false, look.RootElement.Clone(), ErrorCode: null);
        string message = OperationResponseProjection.Create(response, "input.visible.controls",
            askedPlace is null ? null : ("Steam", askedPlace)).Message;
        return (string?)JsonNode.Parse(message)?["view"] ?? throw new AssertionException("the projection has no view");
    }

    /// <summary>The words of <paramref name="spanish"/> that are the projection's own (not in <paramref name="data"/>,
    /// not shared by the two languages) and are in <paramref name="english"/> too.</summary>
    internal static string[] SpanishWordsIn(string english, string spanish, string data)
    {
        HashSet<string> dataWords = [.. Words().Matches(data).Select(static match => match.Value)];
        HashSet<string> englishWords = [.. Words().Matches(english).Select(static match => match.Value)];
        return [.. Words().Matches(spanish).Select(static match => match.Value)
            .Where(word => !dataWords.Contains(word) && !Shared.Contains(word) && englishWords.Contains(word))
            .Distinct(StringComparer.Ordinal)];
    }

    [GeneratedRegex(@"[\p{L}_]+")]
    private static partial Regex Words();
}
