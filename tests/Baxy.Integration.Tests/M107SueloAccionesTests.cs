using System.Globalization;
using System.Text.Json.Nodes;
using Baxy.App;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// M107 (unseen DEV-D run, 2026-10-01): twelve actions and two moves of a notification (M102 plan
/// notification.cancel.latest + notification.schedule) ended with no visible final, «composition_failed:
/// no_response;retry_exhausted». The App's twin of the mind's floor (OperationFloor, the same data the mind reads)
/// tells any action from its facts when the mind returned nothing. Every phrasing here is our own.
/// </summary>
[TestFixture]
public sealed class M107SueloAccionesTests
{
    private static readonly string[] Shapes = ["success", "failure", "uncertain"];

    private static JsonObject Situation(string operation, string shape) => shape switch
    {
        "success" => new JsonObject
        {
            ["kind"] = "operation", ["operation"] = operation, ["polarity"] = "success", ["verified"] = true,
            ["succeeded"] = true, ["observed"] = new JsonObject { ["version"] = 1 },
        },
        "failure" => new JsonObject
        {
            ["kind"] = "operation", ["operation"] = operation, ["polarity"] = "failure", ["verified"] = false,
            ["succeeded"] = false, ["error"] = "provider_failed",
        },
        _ => new JsonObject
        {
            ["kind"] = "operation", ["operation"] = operation, ["polarity"] = "failure", ["verified"] = false,
            ["succeeded"] = false, ["error"] = "verification_failed", ["effectUncertain"] = true,
        },
    };

    // Every catalog operation × result shape × language, as one case each in the report (2460 NUnit cases kept the
    // test host from exiting once they all ran).
    private static IEnumerable<(string Operation, string Shape, bool English)> EveryOperationShape() =>
        from operation in ProductCatalog.OperationNames
        from shape in Shapes
        from english in new[] { false, true }
        select (operation, shape, english);

    // Owner's rule (2026-09-24): the search is not shown; what no draft can say from the pages was not found, which
    // the mind tells. The clock and the PC's measurements are said by their own finals («Son las 11:01.»); «I checked
    // the time» would answer nothing (noSuccessFloor in the data).
    private static bool HasNoFloorOfItsOwn(string operation, string shape) =>
        operation is "web.search" or "system.time" or "system.status" && shape == "success";

    [Test]
    public void EveryCatalogOperationHasItsPlainClause()
    {
        // The file the App embeds and the mind reads.
        var operations = (JsonObject)JsonNode.Parse(File.ReadAllText(Path.Combine(
            FindRepositoryRoot(), "src", "baxy_mind", "data", "operation_floor.v1.json")))!["operations"]!;
        Assert.That(ProductCatalog.OperationNames.Where(name => !operations.ContainsKey(name)), Is.Empty);
    }

    [Test]
    public void EveryCompletableResultHasAFloor()
    {
        var wrong = new List<string>();
        foreach ((string operation, string shape, bool english) in EveryOperationShape())
        {
            string? floor = OperationFloor.Final(Situation(operation, shape), english);
            bool fine = HasNoFloorOfItsOwn(operation, shape)
                ? floor is null
                : floor is { Length: > 0 } && char.IsUpper(floor[0]) && floor.EndsWith('.')
                    && !floor.Contains('{', StringComparison.Ordinal)
                    && !floor.Contains(operation, StringComparison.Ordinal);
            if (!fine)
            {
                wrong.Add($"{operation} {shape} {(english ? "en" : "es")}: {floor ?? "<none>"}");
            }
        }

        Assert.That(wrong, Is.Empty);
    }

    // The floor passes the same acceptance as a composed final, so the App publishes it instead of the warning. Each
    // operation is judged in one language, the two alternating along the catalog (the acceptance is the costly part).
    [Test]
    public void TheAppPublishesTheFloorOfEveryAction()
    {
        var refused = new List<string>();
        List<string> operations = [.. ProductCatalog.OperationNames];
        foreach ((string operation, string shape, bool english) in EveryOperationShape())
        {
            if (HasNoFloorOfItsOwn(operation, shape) || english != (operations.IndexOf(operation) % 2 == 1))
            {
                continue;
            }

            var draft = new UserMessageDraft(
                Situation(operation, shape).ToJsonString(), shape == "success" ? "status" : "error", null);
            string request = english ? "please take care of this for me" : "por favor encárgate de esto";
            string? floor = OperationFloor.Final(Situation(operation, shape), english);
            string? published = ModelMessageComposer.DeterministicFinal(
                draft, request, ModelMessageComposer.CreateFacts(draft), null);
            if (published is null || published != floor)
            {
                refused.Add($"{operation} {shape} {(english ? "en" : "es")}: «{floor}» "
                    + $"{UserMessagePolicy.ModelResponseRejectionReason(floor, draft, request)}");
            }
        }

        Assert.That(refused, Is.Empty);
    }

    private static IEnumerable<TestCaseData> TwinCases()
    {
        JsonObject fixture = (JsonObject)JsonNode.Parse(File.ReadAllText(Path.Combine(
            FindRepositoryRoot(), "tests", "data", "c03_m107_floor_twins.json")))!;
        foreach (JsonNode? row in (JsonArray)fixture["cases"]!)
        {
            string id = (string)row!["id"]!;
            yield return new TestCaseData(row["situation"]!.ToJsonString(), false, (string)row["es"]!).SetName($"Twin({id},es)");
            yield return new TestCaseData(row["situation"]!.ToJsonString(), true, (string)row["en"]!).SetName($"Twin({id},en)");
        }
    }

    // The fixture is written by the mind's baxy_mind.operation_floor (tests/test_c03_m107_suelo_acciones.py reads it
    // back too): the App says the same sentence.
    [TestCaseSource(nameof(TwinCases))]
    public void TheAppSaysWhatTheMindSays(string situation, bool english, string expected)
    {
        var source = (JsonObject)JsonNode.Parse(situation)!;
        string? floor = OperationFloor.Final(source, english);
        Assert.That(floor ?? string.Empty, Is.EqualTo(expected));
        if (expected.Length == 0)
        {
            return;
        }

        // And it is what the App publishes when the mind answered nothing.
        bool done = source["verified"] is JsonValue verified && verified.GetValue<bool>()
            && source["succeeded"] is JsonValue succeeded && succeeded.GetValue<bool>();
        var draft = new UserMessageDraft(situation, done || (string?)source["cause"] == "mission_completed"
            ? "status" : "error", null);
        string request = english ? "please take care of this for me" : "por favor encárgate de esto";
        Assert.That(
            ModelMessageComposer.DeterministicFinal(draft, request, ModelMessageComposer.CreateFacts(draft), string.Empty),
            Is.EqualTo(expected),
            () => $"refused: {UserMessagePolicy.ModelResponseRejectionReason(expected, draft, request)}");
    }

    [Test]
    public void ATypedFailureWithAKnownCauseIsSaidWhole()
    {
        var mission = (JsonObject)JsonNode.Parse(
            """{"kind":"failure","polarity":"failure","cause":"mission_failed","stepCount":0,"steps":[],"reason":{"kind":"operation","operation":"audio.volume.adjust","polarity":"failure","verified":false,"succeeded":false,"error":"external_verification_failed"}}""")!;
        Assert.That(OperationFloor.FailureSentence(mission, english: false),
            Is.EqualTo("No pude confirmar que se hiciera el cambio."));
        Assert.That(OperationFloor.FailureSentence(mission, english: true),
            Is.EqualTo("I couldn't confirm that the change was made."));
    }

    private static string Moved(DateTimeOffset due) =>
        new JsonObject
        {
            ["kind"] = "status", ["polarity"] = "success", ["cause"] = "mission_completed", ["stepCount"] = 2,
            ["steps"] = new JsonArray(
                """{"kind":"operation","operation":"notification.cancel.latest","polarity":"success","verified":true,"succeeded":true,"observed":{"version":1,"kind":"reminder","taskName":"BAXY-Reminder-1","canceled":true,"authority":"windows_task_scheduler_absence_postread"},"readOnly":false}""",
                new JsonObject
                {
                    ["kind"] = "operation", ["operation"] = "notification.schedule", ["polarity"] = "success",
                    ["verified"] = true, ["succeeded"] = true, ["readOnly"] = false,
                    ["observed"] = new JsonObject
                    {
                        ["version"] = 1, ["kind"] = "reminder", ["title"] = "estirar las piernas",
                        ["dueUtc"] = due.UtcDateTime.ToString("O", CultureInfo.InvariantCulture),
                        ["nextRunUtc"] = due.UtcDateTime.ToString("O", CultureInfo.InvariantCulture),
                        ["taskName"] = "BAXY-Reminder-2", ["authority"] = "windows_task_scheduler_postread",
                    },
                }.ToJsonString()),
            ["completedRequest"] = "cancela el recordatorio «estirar las piernas» y ponlo de nuevo dentro de una hora",
        }.ToJsonString();

    // M102 path: «mejor dentro de una hora» moved the reminder just set; every composition was refused and the mind
    // answered nothing. Each step's observed result is said, the new time at this PC's clock.
    [Test]
    public void AMovedNotificationIsToldStepByStep()
    {
        // An hour from now, or a minute from now when that would cross midnight (the day words are tested in Python).
        DateTimeOffset due = DateTimeOffset.Now.AddMinutes(61);
        if (due.ToLocalTime().Date != DateTimeOffset.Now.Date)
        {
            due = DateTimeOffset.Now.AddSeconds(30);
        }

        string clock = due.ToLocalTime().ToString("HH:mm", CultureInfo.InvariantCulture);
        string article = due.ToLocalTime().Hour == 1 ? "la" : "las";
        var draft = new UserMessageDraft(Moved(due), "status", null);
        JsonObject facts = ModelMessageComposer.CreateFacts(draft);
        Assert.That(
            ModelMessageComposer.DeterministicFinal(draft, "espera, mejor dentro de una hora", facts, ""),
            Is.EqualTo($"Cancelé el último recordatorio y puse el recordatorio «estirar las piernas» para {article} {clock}."));
        Assert.That(
            ModelMessageComposer.DeterministicFinal(draft, "wait, make it in an hour instead", facts, null),
            Is.EqualTo($"I cancelled the latest reminder and I scheduled the reminder «estirar las piernas» for {clock}."));
    }

    [Test]
    public void AMoveWhoseSecondStepFailedSaysBothSteps()
    {
        var draft = new UserMessageDraft(
            """{"kind":"failure","polarity":"failure","cause":"mission_failed","stepCount":1,"steps":["{\"kind\":\"operation\",\"operation\":\"notification.cancel.latest\",\"polarity\":\"success\",\"verified\":true,\"succeeded\":true,\"observed\":{\"version\":1,\"kind\":\"alarm\",\"canceled\":true},\"readOnly\":false}"],"reason":{"kind":"operation","operation":"notification.schedule","polarity":"failure","verified":false,"succeeded":false,"error":"notification_scheduler_failed","effectUncertain":true}}""",
            "error", null);
        Assert.That(
            ModelMessageComposer.DeterministicFinal(
                draft, "no, mejor a las siete y media", ModelMessageComposer.CreateFacts(draft), null),
            Is.EqualTo("Cancelé la última alarma y intenté programar el aviso, pero no pude confirmar si se hizo."));
    }

    // The queue end to end: the mind answered an empty text on every attempt; the App never leaves the action
    // without a final and publishes the floor instead of the warning.
    [TestCase("abre la calculadora", """{"kind":"operation","operation":"app.open","polarity":"success","verified":true,"succeeded":true,"observed":{"version":1,"appId":"windows.calculator","displayName":"Calculadora","alreadyRunning":false,"processId":12}}""", "status", "Abrí la aplicación «Calculadora».")]
    [TestCase("open google keep for me", """{"kind":"operation","operation":"app.open","polarity":"failure","verified":false,"succeeded":false,"error":"app_not_found"}""", "error", "I couldn't open the app.")]
    [TestCase("conéctate al wifi de la casa", """{"kind":"operation","operation":"wifi.connect.named","polarity":"success","verified":true,"succeeded":true,"observed":{"version":1,"ssid":"Casa 5G","connected":true}}""", "status", "Me conecté a la red Wi-Fi «Casa 5G».")]
    [TestCase("mueve el informe a la carpeta de trabajo", """{"kind":"operation","operation":"filesystem.move","polarity":"failure","verified":false,"succeeded":false,"error":"verification_failed","effectUncertain":true}""", "error", "Intenté mover el archivo, pero no pude confirmar si se hizo.")]
    public async Task AnActionTheMindLeftEmptyIsPublishedWithItsFloor(
        string userText, string situation, string intent, string expected)
    {
        var draft = new UserMessageDraft(situation, intent, null);
        var pending = new PendingModelMessage(draft, userText, ModelMessageComposer.CreateFacts(draft), "t107");
        var published = new List<(string Text, string? Failure)>();
        var exhausted = new List<string>();
        var done = new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously);
        await using var mind = new MindSidecarClient();
        var queue = new PendingModelMessageQueue(
            _ => Task.FromResult<MindSidecarClient?>(mind),
            (text, failure, _) =>
            {
                published.Add((text, failure));
                done.TrySetResult(true);
                return Task.CompletedTask;
            },
            _ => Task.CompletedTask,
            () => { },
            () =>
            {
                done.TrySetResult(true);
                return Task.CompletedTask;
            },
            (_, _, _) => Task.FromResult(new ModelMessageCompositionOutcome(
                null, "no_response", UsedRecovery: false, RejectedText: string.Empty)),
            (_, _) => Task.CompletedTask,
            (_, failure) =>
            {
                exhausted.Add(failure);
                return Task.CompletedTask;
            });

        queue.Enqueue(pending, CancellationToken.None);
        await done.Task.WaitAsync(TimeSpan.FromSeconds(5));
        await queue.CloseAsync();

        Assert.Multiple(() =>
        {
            Assert.That(exhausted, Is.Empty);
            Assert.That(published, Has.Count.EqualTo(1));
            Assert.That(published[0].Text, Is.EqualTo(expected));
            Assert.That(published[0].Failure, Is.EqualTo("no_response;deterministic_fallback"));
        });
    }

    private static string FindRepositoryRoot()
    {
        // Read while the cases are built, before any test context exists.
        DirectoryInfo? directory = new(AppContext.BaseDirectory);
        while (directory is not null)
        {
            if (File.Exists(Path.Combine(directory.FullName, "Baxy.slnx")))
            {
                return directory.FullName;
            }

            directory = directory.Parent;
        }

        throw new DirectoryNotFoundException("No repository root above the test directory.");
    }
}
