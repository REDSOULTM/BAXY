using System.Text.Encodings.Web;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// M116 (DEV-F v4e2, a1739b28: F-s005, F-s014, F-s033, F-w01-t4, F-w05-t2, F-w29-t2 drafts with WhatsApp or Discord
/// closed; F-w51-t2 the volume already at its maximum; F-w30-t2/t3/t4, F-w58-t4 a window to maximize or place whose
/// application was absent or closed): the arguments were understood and the PC failed, but the failure facts carried
/// only the cause and one target, so the final could not say what was attempted and the turn's record hid it. A failed
/// or unverified step now carries its readable arguments (<c>attempted</c>) and the effects it left undone
/// (<c>notDone</c>); never an id, a handle, an AUMID, a machine stamp or a path beyond its last name. Names and texts
/// below are our own.
/// </summary>
[TestFixture]
public sealed class M116HechosFalloTests
{
    private static string Failed(string operation, string error) =>
        $$"""{"kind":"operation","operation":"{{operation}}","polarity":"failure","verified":false,"succeeded":false,"error":"{{error}}"}""";

    private static JsonObject Facts(string message) => (JsonObject)JsonNode.Parse(message)!;

    private static string? Attempted(string operation, string error, JsonObject arguments) =>
        Facts(MindPlanBoundary.WithStepFacts(Failed(operation, error), arguments))["attempted"]?.ToJsonString(Relaxed);

    private static readonly JsonSerializerOptions Relaxed = new() { Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping };

    // ------------------------------------------------------------------ what each family carries

    [Test]
    public void ADraftWithTheClientClosedSaysForWhomWhereAndWhichWords()
    {
        JsonObject facts = Facts(MindPlanBoundary.WithStepFacts(
            Failed("message.draft", "whatsapp_client_not_running"),
            new JsonObject { ["channel"] = "whatsapp", ["recipient"] = "Ana", ["text"] = "llego tarde al ensayo" }));
        Assert.Multiple(() =>
        {
            Assert.That(facts["target"]!.GetValue<string>(), Is.EqualTo("Ana"), "M94/M111's target stays");
            Assert.That(facts["attempted"]!.ToJsonString(Relaxed), Is.EqualTo(
                """{"channel":"whatsapp","recipient":"Ana","text":"llego tarde al ensayo"}"""));
            Assert.That(facts["error"]!.GetValue<string>(), Is.EqualTo("whatsapp_client_not_running"));
        });
    }

    [Test]
    public void TheMessageTextIsBoundedAsAnObservationIs()
    {
        string words = string.Join(' ', Enumerable.Repeat("nos vemos mañana en la plaza", 20));
        string text = Facts(MindPlanBoundary.WithStepFacts(
            Failed("message.draft", "discord_client_not_running"),
            new JsonObject { ["channel"] = "discord", ["recipient"] = "Tomás", ["text"] = words }))
            ["attempted"]!["text"]!.GetValue<string>();
        Assert.Multiple(() =>
        {
            Assert.That(text.Length, Is.LessThanOrEqualTo(281));
            Assert.That(text, Does.EndWith("…"));
            Assert.That(words, Does.StartWith(text.TrimEnd('…')));
        });
    }

    [TestCase("audio.volume.adjust", "volume_already_at_maximum",
        """{"direction":"up","amount":15}""", """{"direction":"up","amount":15}""")]
    [TestCase("audio.volume", "volume_set_not_verified", """{"level":40}""", """{"level":40}""")]
    [TestCase("window.snap", "window_not_found",
        """{"windowId":"win_fcee2653bf13d46a190ccd42e1c24d5e","side":"left"}""", """{"side":"left"}""")]
    [TestCase("weather.current", "weather_place_not_found", """{"location":"Villa Ficticia"}""",
        """{"location":"Villa Ficticia"}""")]
    [TestCase("reminder.create", "invalid_reminder",
        """{"title":"regar las plantas","due":"mañana a las 7","dueUtc":"2026-10-02T10:00:00Z"}""",
        """{"title":"regar las plantas","due":"mañana a las 7"}""")]
    [TestCase("filesystem.move", "file_not_found",
        """{"path":"C:\\Users\\marta\\Documents\\Privado\\informe.docx","destinationRelativePath":"Trabajo/2026"}""",
        """{"path":"informe.docx","destinationRelativePath":"2026"}""")]
    [TestCase("filesystem.known.search", "file_search_no_matches",
        """{"folder":"downloads","query":"factura luz","limit":20,"offset":0}""",
        """{"folder":"downloads","query":"factura luz"}""")]
    [TestCase("browser.navigate", "navigation_not_verified",
        """{"url":"https://www.ejemplo.test/ver?v=abc&token=zzz"}""", """{"url":"www.ejemplo.test/ver"}""")]
    [TestCase("email.read.latest", "outlook_not_configured", """{"folder":"inbox","maximumCharacters":2000}""",
        """{"folder":"inbox"}""")]
    public void EachFamilyCarriesItsReadableArguments(string operation, string error, string arguments, string expected)
    {
        Assert.That(Attempted(operation, error, (JsonObject)JsonNode.Parse(arguments)!), Is.EqualTo(expected));
    }

    [Test]
    public void IdentifiersHandlesAumidsAndTokensAreNeverCarried()
    {
        var arguments = new JsonObject
        {
            ["recipientId"] = "recipient_0123456789abcdef0123",
            ["windowId"] = "win_e6372f90395ca4e8267b0748350328d9",
            ["appId"] = "Microsoft.WindowsCamera_8wekyb3d8bbwe!App",
            ["hwnd"] = 655_360,
            ["token"] = "c2VjcmV0",
            ["expectedVersion"] = 3,
            ["label"] = "Microsoft.WindowsCamera_8wekyb3d8bbwe!App",
            ["reviewLabel"] = "3f2504e0-4f89-11d3-9a0c-0305e82c3301",
        };
        string failed = Failed("app.open", "app_not_found");
        Assert.That(MindPlanBoundary.WithStepFacts(failed, arguments), Is.EqualTo(failed));
    }

    // ------------------------------------------------------------------ the effects a failure left undone

    private static MindPlanStep Resolve(string id, string application) =>
        new(id, "window.resolve", $"Localiza {application}.", [], "literal",
            new JsonObject { ["applicationName"] = application });

    [Test]
    public void AResolveThatFailedNamesTheEffectItLeftUndone()
    {
        var plan = new PendingMindPlanExecution("ponlo a la izquierda",
            [Resolve("step_1", "Nébula"),
             new MindPlanStep("step_2", "window.snap", "Coloca la ventana.", ["step_1"], "after_dependencies", null)]);
        string failure = MindPlanBoundary.WithStepFacts(
            Failed("window.resolve", "app_not_found"), plan.CurrentStep.Arguments);
        JsonObject facts = Facts(MindPlanBoundary.WithNotDone(failure, plan, []));
        Assert.Multiple(() =>
        {
            Assert.That(facts["target"]!.GetValue<string>(), Is.EqualTo("Nébula"));
            Assert.That(facts["notDone"]!.ToJsonString(Relaxed), Is.EqualTo(
                """[{"operation":"window.snap","target":"Nébula"}]"""));
        });
    }

    [Test]
    public void OnlyTheEffectsThatDoNotRunAreListed()
    {
        // Word's resolve failed; Chrome's chain still runs (M56), so only Word's snap is left undone.
        var plan = new PendingMindPlanExecution("pon el word a la izquierda y el chrome a la derecha",
            [Resolve("step_1", "Word"),
             new MindPlanStep("step_2", "window.snap", "Coloca Word.", ["step_1"], "after_dependencies",
                 new JsonObject { ["side"] = "left" }),
             Resolve("step_3", "Google Chrome"),
             new MindPlanStep("step_4", "window.snap", "Coloca Chrome.", ["step_3"], "after_dependencies",
                 new JsonObject { ["side"] = "right" })]);
        string failure = MindPlanBoundary.WithStepFacts(
            Failed("window.resolve", "window_not_found"), plan.CurrentStep.Arguments);
        JsonObject kept = Facts(MindPlanBoundary.WithNotDone(failure, plan, [plan.Steps[2], plan.Steps[3]]));
        Assert.That(kept["notDone"]!.ToJsonString(Relaxed), Is.EqualTo(
            """[{"operation":"window.snap","target":"Word","attempted":{"side":"left"}}]"""));

        // An effect that does not act on the failed read keeps its own target, never the read's.
        var independent = new PendingMindPlanExecution("abre obsidian y sube el volumen a 50",
            [new MindPlanStep("step_1", "app.open", "Abre Obsidian.", [], "literal",
                 new JsonObject { ["applicationName"] = "Obsidian" }),
             new MindPlanStep("step_2", "audio.volume", "Pon el volumen.", [], "literal",
                 new JsonObject { ["level"] = 50 }),
             new MindPlanStep("step_3", "system.time", "Lee la hora.", [], "literal", new JsonObject())]);
        string openFailed = MindPlanBoundary.WithStepFacts(
            Failed("app.open", "app_not_found"), independent.CurrentStep.Arguments);
        Assert.That(Facts(MindPlanBoundary.WithNotDone(openFailed, independent, []))["notDone"]!.ToJsonString(Relaxed),
            Is.EqualTo("""[{"operation":"audio.volume","attempted":{"level":50}}]"""), "a read left undone is not listed");
    }

    [Test]
    public void TwoFailuresOfTheSameKindKeepWhatEachAttempted()
    {
        string word = MindPlanBoundary.WithStepFacts(
            Failed("window.resolve", "window_not_found"), new JsonObject { ["applicationName"] = "Word" });
        string chrome = MindPlanBoundary.WithStepFacts(
            Failed("window.resolve", "window_not_found"), new JsonObject { ["applicationName"] = "Google Chrome" });
        JsonObject merged = Facts(MindPlanBoundary.MergeFailures(word, chrome));
        Assert.That(merged["attempted"]!.ToJsonString(Relaxed), Is.EqualTo(
            """[{"applicationName":"Word"},{"applicationName":"Google Chrome"}]"""));
    }

    [Test]
    public void TheMissionFailureKeepsWhatWasAttempted()
    {
        string failure = MindPlanBoundary.WithStepFacts(
            Failed("message.draft", "whatsapp_client_not_running"),
            new JsonObject { ["channel"] = "whatsapp", ["recipient"] = "Ana", ["text"] = "llego tarde" });
        JsonObject mission = Facts(MissionNarration.CreateFailureMessage([], failure));
        Assert.That(mission["reason"]!["attempted"]!["text"]!.GetValue<string>(), Is.EqualTo("llego tarde"));
    }

    // ------------------------------------------------------------------ the shell's twin of the mind's vetting

    [Test]
    public void AClockTheFailedStepAttemptedIsNoInventedClock()
    {
        string attempted = MissionNarration.CreateFailureMessage([], MindPlanBoundary.WithStepFacts(
            Failed("message.draft", "whatsapp_client_not_running"),
            new JsonObject { ["channel"] = "whatsapp", ["recipient"] = "Ana", ["text"] = "paso por ti a las 8" }));
        string bare = MissionNarration.CreateFailureMessage([], Failed("message.draft", "whatsapp_client_not_running"));
        const string reply = "No pude dejarle escrito a Ana en WhatsApp «paso por ti a las 8:00» porque WhatsApp no está abierto.";
        Assert.Multiple(() =>
        {
            Assert.That(UserMessagePolicy.ModelResponseRejectionReason(
                reply, new UserMessageDraft(attempted, "error", null), "igual déjaselo escrito"), Is.Null);
            Assert.That(UserMessagePolicy.ModelResponseRejectionReason(
                reply, new UserMessageDraft(bare, "error", null), "igual déjaselo escrito"),
                Is.EqualTo("missing_literal_fact"), "a clock the facts never held is still invented");
        });
    }
}
