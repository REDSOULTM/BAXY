using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.App;
using Baxy.Contracts;
using Baxy.Kernel.Journal;
using Baxy.Kernel.Mission;
using Baxy.Providers.Windows.Memory;
using Baxy.Security.Windows;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
[NonParallelizable]
public sealed class MemoryAppFlowTests
{
    private const string Canary = "BAXY-MEMORY-APP-private-Alex";
    private const string Timestamp = "2026-07-15T15:00:00.0000000+00:00";

    // MEMORY1249 (8317b26ff, tras MEMORY1247): las banderas falsas (replayed/corrected/sensitive) no son
    // hechos y el compositor las verbalizaba («no se realizaron correcciones ni acciones de replay»); la
    // proyección sólo emite las verdaderas. Sólo se esperan aquí las que son true.
    [TestCase(
        "memory.enable",
        "{\"version\":1,\"enabled\":true,\"replayed\":false}",
        "{\"enabled\":true}")]
    [TestCase(
        "memory.disable",
        "{\"version\":1,\"enabled\":false,\"replayed\":true}",
        "{\"enabled\":false,\"replayed\":true}")]
    [TestCase(
        "memory.save",
        "{\"version\":1,\"recordId\":\"52dc83f9-cee9-49e6-bd99-20c9b1c67dda\",\"revision\":1,\"selector\":\"favorite_color\",\"replayed\":false}",
        "{\"saved\":true}")]
    [TestCase(
        "memory.correct",
        "{\"version\":1,\"recordId\":\"52dc83f9-cee9-49e6-bd99-20c9b1c67dda\",\"revision\":2,\"selector\":\"favorite_color\",\"replayed\":false}",
        "{\"saved\":true,\"corrected\":true}")]
    [TestCase(
        "memory.forget",
        "{\"version\":1,\"deletedCount\":2,\"replayed\":false}",
        "{\"deletedCount\":2}")]
    [TestCase(
        "memory.status",
        "{\"version\":1,\"enabled\":true,\"totalRecords\":3,\"persistentRecords\":1,\"sessionRecords\":1,\"temporaryRecords\":1,\"maximumRecords\":512}",
        "{\"enabled\":true,\"totalRecords\":3,\"persistentRecords\":1,\"sessionRecords\":1,\"temporaryRecords\":1,\"maximumRecords\":512}")]
    [TestCase(
        "memory.export",
        "{\"version\":1,\"path\":\"C:\\\\Users\\\\local\\\\Documents\\\\BAXY\\\\memory-export-0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef.json\",\"recordCount\":3,\"sha256\":\"abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789\",\"replayed\":false}",
        "{\"destination\":\"Documents/BAXY\",\"recordCount\":3,\"integrityVerified\":true,\"mayRedirectOrSync\":true}")]
    public void StrictProjectionAcceptsOnlyKnownCompletedShapes(
        string operation,
        string json,
        string expectedObservations)
    {
        bool accepted = MemoryOperationResponseProjection.TryCreateCompleted(
            operation,
            Parse(json),
            out MemoryOperationResponseProjection? projection);
        UserMessageDraft draft = UserMessagePolicy.Create(
            projection?.Message ?? "proyección ausente",
            UserMessageEvent.Status);

        Assert.That(accepted, Is.True);
        Assert.That(projection, Is.Not.Null);
        Assert.That(UserMessagePolicy.IsStructuredFacts(projection!.Message), Is.True);
        JsonElement facts = Parse(projection.Message);
        JsonElement observed = facts.GetProperty("observed");
        Assert.Multiple(() =>
        {
            Assert.That(facts.GetProperty("operation").GetString(), Is.EqualTo(operation));
            Assert.That(facts.GetProperty("verified").GetBoolean(), Is.True);
            Assert.That(facts.GetProperty("succeeded").GetBoolean(), Is.True);
            foreach (JsonProperty expected in Parse(expectedObservations).EnumerateObject())
            {
                Assert.That(JsonElement.DeepEquals(observed.GetProperty(expected.Name), expected.Value), Is.True,
                    expected.Name);
            }
            foreach (string flag in new[] { "replayed", "corrected", "sensitive" })
            {
                Assert.That(
                    observed.TryGetProperty(flag, out JsonElement value) && !value.GetBoolean(),
                    Is.False,
                    $"{flag}=false no es un hecho (MEMORY1249)");
            }
            Assert.That(projection.Message, Does.Not.Contain("52dc83f9-cee9-49e6-bd99-20c9b1c67dda"));
            Assert.That(projection.Message, Does.Not.Contain("favorite_color"));
            Assert.That(
                UserMessagePolicy.ModelResponseRejectionReason(
                    projection.Message,
                    draft),
                Is.EqualTo("structured_facts_not_prose"));
        });
    }

    [Test]
    public void RecalledValuesAndRedactionAreObservationsForTheComposer()
    {
        JsonElement payload = ToElement(RecordsPayload(
            [Record("name", "Lina", "personal", "persistent"),
             Record("token", Canary, "secret", "persistent")], 2, 0, 20));
        Assert.That(MemoryOperationResponseProjection.TryCreateCompleted("memory.recall", payload,
            out MemoryOperationResponseProjection? projection), Is.True);
        JsonElement observed = Parse(projection!.Message).GetProperty("observed");
        Assert.Multiple(() =>
        {
            Assert.That(observed.GetProperty("shown").GetInt32(), Is.EqualTo(2));
            Assert.That(observed.GetProperty("total").GetInt32(), Is.EqualTo(2));
            Assert.That(observed.GetProperty("records")[0].GetProperty("value").GetString(), Is.EqualTo("Lina"));
            Assert.That(observed.GetProperty("records")[1].GetProperty("value").GetString(), Is.EqualTo("[REDACTED]"));
            Assert.That(projection.Message, Does.Not.Contain(Canary));
        });
    }

    [TestCase("memory.recall", "name", "Priya", "The stored name is Priya.")]
    [TestCase("memory.recall", "color", "turquesa", "El color guardado es turquesa.")]
    [TestCase("memory.list", "name", "Renata", "El nombre guardado es Renata.")]
    [TestCase("memory.list", "color", "indigo", "The stored color is indigo.")]
    public void SingleRecalledValueCrossesTheComposerLiteralContract(
        string operation, string label, string value, string correctReply)
    {
        JsonElement payload = ToElement(RecordsPayload(
            [Record(label, value, "personal", "persistent")], 1, 0, 20));
        Assert.That(MemoryOperationResponseProjection.TryCreateCompleted(operation, payload,
            out MemoryOperationResponseProjection? projection), Is.True);
        UserMessageDraft draft = UserMessagePolicy.Create(projection!.Message, UserMessageEvent.Status);
        JsonObject facts = ModelMessageComposer.CreateFacts(draft);

        Assert.Multiple(() =>
        {
            Assert.That(UserMessagePolicy.RequiredLiteralFacts(draft.Source), Is.EqualTo(new[] { value }));
            Assert.That(facts["requiredFacts"]?.AsArray().Select(item => item!.GetValue<string>()),
                Is.EqualTo(new[] { value }));
            Assert.That(UserMessagePolicy.ModelResponseRejectionReason("No stored information.", draft),
                Is.EqualTo("missing_literal_fact"));
            Assert.That(UserMessagePolicy.ModelResponseRejectionReason(correctReply, draft), Is.Null);
        });
    }

    [TestCase("empty")]
    [TestCase("multiple")]
    [TestCase("long")]
    [TestCase("secret")]
    [TestCase("unverified")]
    public void MemoryLiteralContractDoesNotForceUnboundedOrProtectedRecords(string condition)
    {
        JsonObject[] records = condition switch
        {
            "empty" => [],
            "multiple" => [Record("first", "Lina", "personal", "persistent"),
                           Record("second", "Priya", "personal", "persistent")],
            "long" => [Record("note", new string('a', 257), "personal", "persistent")],
            "secret" => [Record("token", Canary, "secret", "persistent")],
            _ => [Record("name", "Lina", "personal", "persistent")],
        };
        JsonElement payload = ToElement(RecordsPayload(records, records.Length, 0, 20));
        Assert.That(MemoryOperationResponseProjection.TryCreateCompleted("memory.recall", payload,
            out MemoryOperationResponseProjection? projection), Is.True);
        JsonObject source = JsonNode.Parse(projection!.Message)!.AsObject();
        if (condition == "unverified")
        {
            source["verified"] = false;
        }
        UserMessageDraft draft = UserMessagePolicy.Create(source.ToJsonString(), UserMessageEvent.Status);
        JsonObject facts = ModelMessageComposer.CreateFacts(draft);
        Assert.Multiple(() =>
        {
            Assert.That(UserMessagePolicy.RequiredLiteralFacts(draft.Source), Is.Empty);
            Assert.That(facts.ContainsKey("requiredFacts"), Is.False);
            Assert.That(facts.ToJsonString(), Does.Not.Contain(Canary));
        });
    }

    [Test]
    public void PrivateConfirmationAndRecoveryNameThePreparedActionWithoutPrivateArguments()
    {
        using TemporaryDirectory temporary = new();
        MemoryOperationProtector protector = CreateProtector(temporary, Guid.NewGuid().ToString("D"));
        PreparedOperation prepared = protector.Prepare(SaveRoute(Canary, "persistent", "secret")).Prepared;
        foreach (string prompt in new[] {
            PrivateOperationNarration.CreateMemoryConfirmationPrompt(prepared),
            PrivateOperationNarration.CreateMemoryConfirmationPrompt(prepared, reconciliationRequired: true),
            PrivateOperationNarration.CreateMemoryRecoveryPrompt(prepared) })
        {
            JsonElement action = Parse(prompt).GetProperty("pendingAction");
            Assert.Multiple(() =>
            {
                Assert.That(action.GetProperty("operation").GetString(), Is.EqualTo("memory.sensitive.save"));
                Assert.That(action.GetProperty("target").GetString(), Is.EqualTo("private local memory"));
                Assert.That(action.TryGetProperty("arguments", out _), Is.False);
                Assert.That(prompt, Does.Not.Contain(Canary));
                Assert.That(prompt, Does.Not.Contain(prepared.InvocationId));
                Assert.That(prompt, Does.Not.Contain(prepared.MissionId));
            });
        }
    }

    [TestCase(OperationStatuses.Pending)]
    [TestCase(OperationStatuses.Rejected)]
    [TestCase(OperationStatuses.Failed)]
    [TestCase("unexpected")]
    public void MemoryFailureFloorsSurviveTheFullAppAcceptancePolicy(string status)
    {
        var response = new OperationResponse(
            ProtocolTypes.OperationResponse,
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            status,
            "respuesta interna descartada",
            false,
            false,
            null,
            "narration_coverage_probe");

        string message = PrivateOperationNarration.CreateMemoryFailureMessage(
            "memory.recall",
            response);
        UserMessageDraft draft = UserMessagePolicy.Create(
            message,
            UserMessageEvent.Error(UserMessageDiagnosticCodes.ActionNotCompleted));

        Assert.Multiple(() =>
        {
            Assert.That(UserMessagePolicy.IsSafe(message), Is.True);
            Assert.That(UserMessagePolicy.IsStructuredFacts(message), Is.True);
            Assert.That(
                UserMessagePolicy.ModelResponseRejectionReason(message, draft),
                Is.EqualTo("structured_facts_not_prose"));
            Assert.That(
                UserMessagePolicy.AcceptModelAuthoredResponse(
                    "No pude completar la petición sobre la memoria local.",
                    draft),
                Is.Not.Null);
        });
    }

    [TestCase(
        "memory.enable",
        "{\"version\":1,\"enabled\":false,\"replayed\":false}")]
    [TestCase(
        "memory.status",
        "{\"version\":1,\"enabled\":true,\"totalRecords\":3,\"persistentRecords\":1,\"sessionRecords\":1,\"temporaryRecords\":0,\"maximumRecords\":512}")]
    [TestCase(
        "memory.status",
        "{\"version\":1.0,\"enabled\":true,\"totalRecords\":0,\"persistentRecords\":0,\"sessionRecords\":0,\"temporaryRecords\":0,\"maximumRecords\":512}")]
    [TestCase(
        "memory.forget",
        "{\"version\":1,\"deletedCount\":0,\"replayed\":false,\"extra\":true}")]
    [TestCase(
        "memory.export",
        "{\"version\":1,\"path\":\"C:\\\\private\"}")]
    public void StrictProjectionRejectsMismatchedUnknownOrExtendedShapes(
        string operation,
        string json)
    {
        Assert.That(
            MemoryOperationResponseProjection.TryCreateCompleted(
                operation,
                Parse(json),
                out _),
            Is.False);
    }

    [Test]
    public void ExportProjectionNeverEchoesThePrivateAbsolutePathOrDigest()
    {
        const string digest =
            "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";
        string path = $"C:\\Users\\{Canary}\\Documents\\BAXY\\memory-export-{digest}.json";
        JsonElement payload = ToElement(new JsonObject
        {
            ["version"] = 1,
            ["path"] = path,
            ["recordCount"] = 1,
            ["sha256"] = digest,
            ["replayed"] = false,
        });

        bool accepted = MemoryOperationResponseProjection.TryCreateCompleted(
            "memory.export",
            payload,
            out MemoryOperationResponseProjection? projection);

        Assert.Multiple(() =>
        {
            Assert.That(accepted, Is.True);
            JsonElement observed = Parse(projection!.Message).GetProperty("observed");
            Assert.That(observed.GetProperty("destination").GetString(), Is.EqualTo("Documents/BAXY"));
            Assert.That(observed.GetProperty("mayRedirectOrSync").GetBoolean(), Is.True);
            // replayed=false no se emite (MEMORY1249).
            Assert.That(observed.TryGetProperty("replayed", out _), Is.False);
            Assert.That(projection.Message, Does.Not.Contain("local"));
            Assert.That(projection.Message, Does.Not.Contain(path));
            Assert.That(projection.Message, Does.Not.Contain(digest));
            Assert.That(projection.Message, Does.Not.Contain(Canary));
        });
    }

    [Test]
    public void ExportProjectionUsesTheFreshJournalReplayEvidenceFromTheResponse()
    {
        const string digest =
            "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";
        JsonElement payload = ToElement(new JsonObject
        {
            ["version"] = 1,
            ["path"] = $"C:\\Users\\local\\Documents\\BAXY\\memory-export-{digest}.json",
            ["recordCount"] = 1,
            ["sha256"] = digest,
            ["replayed"] = false,
        });

        bool accepted = MemoryOperationResponseProjection.TryCreateCompleted(
            "memory.export",
            payload,
            out MemoryOperationResponseProjection? projection,
            responseReplayed: true);

        Assert.Multiple(() =>
        {
            Assert.That(accepted, Is.True);
            JsonElement observed = Parse(projection!.Message).GetProperty("observed");
            Assert.That(observed.GetProperty("replayed").GetBoolean(), Is.True);
            Assert.That(observed.GetProperty("integrityVerified").GetBoolean(), Is.True);
            Assert.That(observed.GetProperty("integrityAlgorithm").GetString(), Is.EqualTo("SHA-256"));
            Assert.That(projection.Message, Does.Not.Contain(digest));
        });
    }

    [Test]
    public void ExportConfirmationWarnsBeforeConsentThatDocumentsMayBeRedirectedOrSynced()
    {
        using TemporaryDirectory temporary = new();
        MemoryOperationProtector protector = CreateProtector(
            temporary,
            Guid.NewGuid().ToString("D"));
        PreparedOperation prepared = protector.Prepare(
            new MemoryRoutedOperation(
                "memory.export",
                new JsonObject
                {
                    ["version"] = 1,
                    ["destination"] = "documents",
                    ["includeSecrets"] = false,
                })).Prepared;

        string prompt = PrivateOperationNarration.CreateMemoryConfirmationPrompt(prepared);

        Assert.Multiple(() =>
        {
            Assert.That(prompt, Does.Contain("Documents/BAXY"));
            Assert.That(prompt, Does.Contain("mayRedirectOrSync"));
            Assert.That(prompt, Does.Contain("memory_export_privacy"));
            Assert.That(prompt, Does.Contain("confirmar"));
            Assert.That(prompt, Does.Not.Contain(Canary));
        });
    }

    [Test]
    public void ExportReplayFailureExplainsThatIntegrityIsUnknownWithoutEchoingEvidence()
    {
        const string digest =
            "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";
        string path = $"C:\\Users\\{Canary}\\Documents\\BAXY\\memory-export-{digest}.json";
        var response = new OperationResponse(
            ProtocolTypes.OperationResponse,
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            OperationStatuses.Failed,
            Canary,
            false,
            true,
            ToElement(new JsonObject
            {
                ["path"] = path,
                ["sha256"] = digest,
            }),
            "verification_failed");

        string message = PrivateOperationNarration.CreateMemoryFailureMessage(
            "memory.export",
            response);

        Assert.Multiple(() =>
        {
            Assert.That(message, Does.Contain("memory_export_unverified_replay"));
            Assert.That(message, Does.Not.Contain(path));
            Assert.That(message, Does.Not.Contain(digest));
            Assert.That(message, Does.Not.Contain(Canary));
            Assert.That(message, Does.Not.Contain("verifiqué"));
        });
    }

    [Test]
    public void DisabledMemoryFailureKeepsTheStableCauseAndHumanRecoveryStep()
    {
        var response = new OperationResponse(
            ProtocolTypes.OperationResponse,
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            OperationStatuses.Failed,
            "Memoria deshabilitada.",
            false,
            false,
            null,
            "memory_disabled");

        string message = PrivateOperationNarration.CreateMemoryFailureMessage(
            "memory.recall",
            response);
        UserMessageDraft draft = UserMessagePolicy.Create(
            message,
            UserMessageEvent.Error(UserMessageDiagnosticCodes.ActionNotCompleted));

        Assert.Multiple(() =>
        {
            Assert.That(message, Does.Contain("memory_disabled"));
            Assert.That(draft.Source, Is.EqualTo(message));
            Assert.That(draft.Source, Does.Not.Contain("500"));
        });
    }

    [Test]
    public void RecordProjectionIsBoundedAndRedactsSensitiveValuesAgain()
    {
        JsonObject payload = RecordsPayload(
        [
            Record("display_name", "Alex", "normal", "persistent"),
            Record("api_key", Canary, "secret", "persistent"),
        ],
        totalCount: 2,
        offset: 0,
        limit: 5);

        bool accepted = MemoryOperationResponseProjection.TryCreateCompleted(
            "memory.recall",
            ToElement(payload),
            out MemoryOperationResponseProjection? projection);

        Assert.Multiple(() =>
        {
            Assert.That(accepted, Is.True);
            Assert.That(projection!.Message, Does.Contain("display_name"));
            Assert.That(projection.Message, Does.Contain("Alex"));
            Assert.That(projection.Message, Does.Contain("api_key"));
            Assert.That(projection.Message, Does.Contain("[REDACTED]"));
            Assert.That(projection.Message, Does.Not.Contain(Canary));
            Assert.That(projection.Message.Length, Is.LessThanOrEqualTo(16_384));
        });
    }

    [Test]
    public void RecordProjectionCapsTheVisiblePageAndMessageSize()
    {
        JsonObject[] records = Enumerable.Range(0, 100)
            .Select(index => Record(
                $"label-{index:D3}",
                new string((char)('a' + (index % 26)), 4096),
                "normal",
                "persistent"))
            .ToArray();
        JsonObject payload = RecordsPayload(records, 100, offset: 0, limit: 100);

        bool accepted = MemoryOperationResponseProjection.TryCreateCompleted(
            "memory.list",
            ToElement(payload),
            out MemoryOperationResponseProjection? projection);

        Assert.Multiple(() =>
        {
            Assert.That(accepted, Is.True);
            Assert.That(projection!.Message.Length, Is.LessThanOrEqualTo(16_384));
            Assert.That(projection.Message, Does.Contain("label-019"));
            Assert.That(projection.Message, Does.Not.Contain("label-020"));
            Assert.That(projection.Message, Does.Contain("\"shown\":20"));
            Assert.That(projection.Message, Does.Contain("\"total\":100"));
        });
    }

    [Test]
    public void RecordProjectionRejectsDuplicatePropertiesAndInconsistentRetention()
    {
        JsonElement duplicate = Parse(
            "{\"version\":1,\"version\":1,\"records\":[],\"count\":0,\"totalCount\":0,\"offset\":0,\"limit\":5}");
        JsonObject inconsistent = RecordsPayload(
            [Record("temporary", "value", "normal", "temporary", expiry: null)],
            totalCount: 1,
            offset: 0,
            limit: 5);

        Assert.Multiple(() =>
        {
            Assert.That(
                MemoryOperationResponseProjection.TryCreateCompleted(
                    "memory.recall",
                    duplicate,
                    out _),
                Is.False);
            Assert.That(
                MemoryOperationResponseProjection.TryCreateCompleted(
                    "memory.recall",
                    ToElement(inconsistent),
                    out _),
                Is.False);
        });
    }

    [Test]
    public void SensitiveDraftStaysInRamUntilAValidatedChallengeThenEntersOutboxEncrypted()
    {
        using TemporaryDirectory temporary = new();
        string outbox = Path.Combine(temporary.Path, "shell", "retry-outbox.v1.json");
        MemoryOperationProtector protector = CreateProtector(
            temporary,
            Guid.NewGuid().ToString("D"));
        var registry = new RetryableOperationRegistry(outbox, protector);
        PreparedOperation draft = protector.Prepare(SaveRoute(Canary, "persistent", "secret")).Prepared;
        string token = Base64Url(RandomNumberGenerator.GetBytes(32));
        DateTimeOffset now = DateTimeOffset.UtcNow;
        OperationResponse challengeResponse = new(
            ProtocolTypes.OperationResponse,
            Guid.NewGuid().ToString("D"),
            draft.MissionId,
            draft.InvocationId,
            OperationStatuses.Pending,
            "Se requiere confirmación.",
            false,
            false,
            Parse($"{{\"version\":1,\"token\":\"{token}\",\"expiresAtUtc\":\"{now.AddMinutes(2):O}\",\"reconciliationRequired\":false}}"),
            "confirmation_required");

        bool challenged = PendingMemoryConfirmation.TryCreate(
            challengeResponse,
            draft,
            TimeProvider.System,
            out PendingMemoryConfirmation? pending);

        Assert.That(challenged, Is.True);
        Assert.That(registry.SnapshotPendingOperations(), Is.Empty);

        PreparedOperation durable = registry.GetOrAdd(
            protector.AuthenticateForOutbox(pending!.Prepared));
        string outboxText = File.ReadAllText(outbox, Encoding.UTF8);

        Assert.Multiple(() =>
        {
            Assert.That(durable.MissionId, Is.EqualTo(draft.MissionId));
            Assert.That(durable.InvocationId, Is.EqualTo(draft.InvocationId));
            Assert.That(registry.SnapshotPendingOperations(), Has.Count.EqualTo(1));
            Assert.That(outboxText, Does.Not.Contain(Canary));
            Assert.That(outboxText, Does.Not.Contain(token));
            Assert.That(pending.ToString(), Does.Not.Contain(token));
            Assert.That(
                PrivateOperationNarration.CreateMemoryConfirmationPrompt(durable),
                Does.Not.Contain(Canary));
        });
    }

    [Test]
    public void RecoveryDropsPreviousSessionWorkAndPreservesAllowedPersistentWork()
    {
        using TemporaryDirectory temporary = new();
        string outbox = Path.Combine(temporary.Path, "shell", "retry-outbox.v1.json");
        MemoryOperationProtector previous = CreateProtector(
            temporary,
            Guid.NewGuid().ToString("D"));
        var previousRegistry = new RetryableOperationRegistry(outbox, previous);
        _ = previousRegistry.GetOrAdd(previous.Prepare(
            SaveRoute(Canary + "-persistent", "persistent", "personal")));
        _ = previousRegistry.GetOrAdd(previous.Prepare(
            SaveRoute(Canary + "-session", "session", "personal")));

        MemoryOperationProtector current = CreateProtector(
            temporary,
            Guid.NewGuid().ToString("D"));
        var currentRegistry = new RetryableOperationRegistry(outbox, current);
        foreach (PreparedOperation operation in currentRegistry.SnapshotPendingOperations().ToArray())
        {
            MemoryOperationInspection inspection = current.InspectForRecovery(operation);
            if (!inspection.OriginatesInCurrentSession && inspection.CancelAfterSessionChange)
            {
                currentRegistry.MarkResolved(operation);
            }
        }

        PreparedOperation preserved = currentRegistry.SnapshotPendingOperations().Single();
        MemoryOperationInspection preservedInspection = current.InspectForRecovery(preserved);
        string prompt = PrivateOperationNarration.CreateMemoryRecoveryPrompt(preserved);
        string outboxText = File.ReadAllText(outbox, Encoding.UTF8);

        Assert.Multiple(() =>
        {
            Assert.That(preserved.OperationName, Is.EqualTo("memory.save"));
            Assert.That(preservedInspection.OriginatesInCurrentSession, Is.False);
            Assert.That(preservedInspection.CancelAfterSessionChange, Is.False);
            Assert.That(prompt, Does.Not.Contain(Canary));
            Assert.That(prompt.ToLowerInvariant(), Does.Not.Contain("persistent"));
            Assert.That(outboxText, Does.Not.Contain(Canary));
        });
    }

    // D3 (DECISIONES_DUENO_2026-09-20.md): enabling the private memory is not
    // destructive, so a requested save with the memory disabled enables it and
    // saves at once; no «memory_disabled» failure and no question in between.
    [Test]
    public async Task MissingNameFlowEnablesMemoryAndSavesWithoutAsking()
    {
        using TemporaryDirectory temporary = new();
        string? previousDataRoot = Environment.GetEnvironmentVariable("BAXY_DATA_DIR");
        Environment.SetEnvironmentVariable("BAXY_DATA_DIR", temporary.Path);
        try
        {
            await using var viewModel = new MainWindowViewModel();
            await viewModel.InitializeAsync(CancellationToken.None);
            Assert.That(viewModel.IsReady, Is.True);
            await SubmitAsync(viewModel, "Recuerda mi nombre");
            Assert.That(LastAssistantMessage(viewModel), Does.Contain("memory_save_needs_content"));
            await SubmitAsync(viewModel, "me llamo Lina");
            Assert.That(viewModel.Messages, Has.None.Matches<ConversationMessage>(
                static message => !message.IsUser && message.Body.Contains("memory_disabled", StringComparison.Ordinal)));
            Assert.That(viewModel.Messages, Has.None.Matches<ConversationMessage>(
                static message => !message.IsUser && message.Body.Contains("\"kind\":\"confirmation\"", StringComparison.Ordinal)));
            JsonElement saved = Parse(LastAssistantMessage(viewModel));
            Assert.That(saved.GetProperty("operation").GetString(), Is.EqualTo("memory.save"));
            Assert.That(saved.GetProperty("observed").GetProperty("saved").GetBoolean(), Is.True);
            var store = new LocalMemoryStore(
                Path.Combine(temporary.Path, "memory-store"),
                new WindowsProtectedPayload(Path.Combine(
                    temporary.Path, "security", "private-payload.v1.key")));
            MemoryStatusResult status = store.Status(new MemoryStatusRequest(null));
            Assert.Multiple(() =>
            {
                Assert.That(status.Enabled, Is.True);
                Assert.That(status.TotalRecords, Is.EqualTo(1));
            });
            Assert.That(new DurableRetryStore(Path.Combine(
                temporary.Path, "shell", "retry-outbox.v1.json")).Load(), Is.Empty);
        }
        finally
        {
            Environment.SetEnvironmentVariable("BAXY_DATA_DIR", previousDataRoot);
        }
    }

    [TestCase("cómo me llamo")]
    [TestCase("What name have you saved in private memory?")]
    [TestCase("¿Qué nombre tienes guardado en tu memoria privada?")]
    public async Task ViewModelBindsRequestedNameAndRecallsItAfterANewSession(string recallRequest)
    {
        using TemporaryDirectory temporary = new();
        string? previousDataRoot = Environment.GetEnvironmentVariable("BAXY_DATA_DIR");
        Environment.SetEnvironmentVariable("BAXY_DATA_DIR", temporary.Path);
        string outbox = Path.Combine(temporary.Path, "shell", "retry-outbox.v1.json");
        string name = "Nimbo" + new string(Guid.NewGuid().ToString("N")
            .Select(static character => (char)('a' + character % 26)).ToArray());
        try
        {
            await using (var first = new MainWindowViewModel())
            {
                await first.InitializeAsync(CancellationToken.None);
                Assert.That(first.IsReady, Is.True);
                await SubmitAsync(first, "activa la memoria");
                await SubmitAsync(first, "confirmar");
                Assert.That(new DurableRetryStore(outbox).Load(), Is.Empty);
                await SubmitAsync(first, "Recuerda mi nombre");
                Assert.Multiple(() =>
                {
                    Assert.That(new DurableRetryStore(outbox).Load(), Is.Empty);
                    Assert.That(LastAssistantMessage(first), Does.Contain("memory_save_needs_content"));
                    Assert.That(LastAssistantMessage(first), Does.Not.Contain(name));
                });
                await SubmitAsync(first, "me llamo " + name);
                Assert.That(new DurableRetryStore(outbox).Load(), Is.Empty);
                Assert.That(Parse(LastAssistantMessage(first)).GetProperty("observed")
                    .GetProperty("saved").GetBoolean(), Is.True);
            }

            await using var second = new MainWindowViewModel();
            await second.InitializeAsync(CancellationToken.None);
            await SubmitAsync(second, recallRequest);
            Assert.Multiple(() =>
            {
                Assert.That(second.IsReady, Is.True);
                Assert.That(LastAssistantMessage(second), Does.Contain("memory_records"));
                Assert.That(LastAssistantMessage(second), Does.Contain(name));
                Assert.That(new DurableRetryStore(outbox).Load(), Is.Empty);
            });
        }
        finally
        {
            Environment.SetEnvironmentVariable("BAXY_DATA_DIR", previousDataRoot);
        }
    }

    // D3 (2026-09-20): the requested save enables the memory itself and resumes at
    // once — one enable and one save, no challenge, the name never in the outbox.
    [Test]
    public async Task RequestedSaveEnablesMemoryAndResumesWithoutAChallenge()
    {
        using TemporaryDirectory temporary = new();
        string? previousDataRoot = Environment.GetEnvironmentVariable("BAXY_DATA_DIR");
        Environment.SetEnvironmentVariable("BAXY_DATA_DIR", temporary.Path);
        string outbox = Path.Combine(temporary.Path, "shell", "retry-outbox.v1.json");
        string name = "Nimbo" + new string(Guid.NewGuid().ToString("N")
            .Select(static character => (char)('a' + character % 26)).ToArray());
        try
        {
            await using (var first = new MainWindowViewModel())
            {
                await first.InitializeAsync(CancellationToken.None);
                await SubmitAsync(first, "Recuerda mi nombre");
                await SubmitAsync(first, "me llamo " + name);
                Assert.Multiple(() =>
                {
                    Assert.That(new DurableRetryStore(outbox).Load(), Is.Empty);
                    Assert.That(first.Messages, Has.None.Matches<ConversationMessage>(
                        static message => !message.IsUser
                            && message.Body.Contains("\"kind\":\"confirmation\"", StringComparison.Ordinal)));
                    Assert.That(Parse(LastAssistantMessage(first)).GetProperty("observed")
                        .GetProperty("saved").GetBoolean(), Is.True);
                    Assert.That(ReadMemoryStatus(temporary.Path).Enabled, Is.True);
                    Assert.That(ReadMemoryStatus(temporary.Path).TotalRecords, Is.EqualTo(1));
                });
            }

            JsonElement[] saveStarts = File.ReadLines(Path.Combine(temporary.Path, "journal", "missions.jsonl"))
                .Select(static line => Parse(line).GetProperty("payload"))
                .Where(static row => row.GetProperty("operation").GetString() == "memory.save"
                    && row.GetProperty("phase").GetString() == "started")
                .ToArray();
            Assert.That(saveStarts, Has.Length.EqualTo(2));
            Assert.That(saveStarts[0].GetProperty("invocationId").GetString(),
                Is.Not.EqualTo(saveStarts[1].GetProperty("invocationId").GetString()));

            await using var second = new MainWindowViewModel();
            await second.InitializeAsync(CancellationToken.None);
            await SubmitAsync(second, "cómo me llamo");
            Assert.That(LastAssistantMessage(second), Does.Contain(name));
        }
        finally
        {
            Environment.SetEnvironmentVariable("BAXY_DATA_DIR", previousDataRoot);
        }
    }

    // D3 (2026-09-20): there is no enable offer to cancel; a later «cancelar» has
    // nothing pending and the record stays.
    [Test]
    public async Task CancelAfterADirectEnableAndSaveChangesNothing()
    {
        using TemporaryDirectory temporary = new();
        string? previousDataRoot = Environment.GetEnvironmentVariable("BAXY_DATA_DIR");
        Environment.SetEnvironmentVariable("BAXY_DATA_DIR", temporary.Path);
        string outbox = Path.Combine(temporary.Path, "shell", "retry-outbox.v1.json");
        try
        {
            await using var viewModel = new MainWindowViewModel();
            await viewModel.InitializeAsync(CancellationToken.None);
            await SubmitAsync(viewModel, "remember my name");
            await SubmitAsync(viewModel, "my name is Taylor");
            Assert.Multiple(() =>
            {
                Assert.That(new DurableRetryStore(outbox).Load(), Is.Empty);
                Assert.That(ReadMemoryStatus(temporary.Path).Enabled, Is.True);
                Assert.That(ReadMemoryStatus(temporary.Path).TotalRecords, Is.EqualTo(1));
            });
            await SubmitAsync(viewModel, "cancelar");
            Assert.Multiple(() =>
            {
                Assert.That(new DurableRetryStore(outbox).Load(), Is.Empty);
                Assert.That(ReadMemoryStatus(temporary.Path).Enabled, Is.True);
                Assert.That(ReadMemoryStatus(temporary.Path).TotalRecords, Is.EqualTo(1));
            });
        }
        finally
        {
            Environment.SetEnvironmentVariable("BAXY_DATA_DIR", previousDataRoot);
        }
    }

    private static MemoryStatusResult ReadMemoryStatus(string dataRoot) => new LocalMemoryStore(
        Path.Combine(dataRoot, "memory-store"),
        new WindowsProtectedPayload(Path.Combine(dataRoot, "security", "private-payload.v1.key")))
        .Status(new MemoryStatusRequest(null));

    [Test]
    public async Task ViewModelRunsProtectedMemoryConfirmationProjectionAndCancellationEndToEnd()
    {
        using TemporaryDirectory temporary = new();
        string? previousDataRoot = Environment.GetEnvironmentVariable("BAXY_DATA_DIR");
        Environment.SetEnvironmentVariable("BAXY_DATA_DIR", temporary.Path);
        string outbox = Path.Combine(temporary.Path, "shell", "retry-outbox.v1.json");

        try
        {
            await using var viewModel = new MainWindowViewModel();
            await viewModel.InitializeAsync(CancellationToken.None);

            Assert.Multiple(() =>
            {
                Assert.That(viewModel.IsReady, Is.True);
                Assert.That(new DurableRetryStore(outbox).Load(), Is.Empty);
            });

            // D3 (2026-09-20): enabling the memory is not destructive; it runs
            // without a challenge and the outbox never holds it.
            await SubmitAsync(viewModel, "activa la memoria");
            Assert.Multiple(() =>
            {
                Assert.That(new DurableRetryStore(outbox).Load(), Is.Empty);
                Assert.That(Parse(LastAssistantMessage(viewModel)).GetProperty("operation").GetString(),
                    Is.EqualTo("memory.enable"));
                Assert.That(Parse(LastAssistantMessage(viewModel)).GetProperty("observed")
                    .GetProperty("enabled").GetBoolean(), Is.True);
            });

            await SubmitAsync(viewModel, "recuerda que mi color favorito es azul");
            Assert.Multiple(() =>
            {
                Assert.That(new DurableRetryStore(outbox).Load(), Is.Empty);
                Assert.That(Parse(LastAssistantMessage(viewModel)).GetProperty("observed")
                    .GetProperty("saved").GetBoolean(), Is.True);
            });

            await SubmitAsync(viewModel, "qué color me gusta");
            Assert.Multiple(() =>
            {
                Assert.That(LastAssistantMessage(viewModel), Does.Contain("favorite_color"));
                Assert.That(LastAssistantMessage(viewModel), Does.Contain("azul"));
                Assert.That(LastAssistantMessage(viewModel), Does.Contain("memory_records"));
            });

            // D3 (2026-09-20): a sensitive save is not destructive either; it is
            // stored at once and the secret never reaches a visible message.
            const string sensitiveRequest = "save my api key sk-12345 in your memory";
            await SubmitAsync(viewModel, sensitiveRequest);
            Assert.Multiple(() =>
            {
                Assert.That(new DurableRetryStore(outbox).Load(), Is.Empty);
                Assert.That(Parse(LastAssistantMessage(viewModel)).GetProperty("operation").GetString(),
                    Is.EqualTo("memory.sensitive.save"));
                Assert.That(Parse(LastAssistantMessage(viewModel)).GetProperty("observed")
                    .GetProperty("sensitive").GetBoolean(), Is.True);
                Assert.That(LastAssistantMessage(viewModel), Does.Not.Contain("sk-12345"));
                Assert.That(File.ReadAllText(outbox, Encoding.UTF8), Does.Not.Contain("sk-12345"));
                Assert.That(
                    viewModel.Messages,
                    Has.Some.Matches<ConversationMessage>(message =>
                        message.IsUser
                        && message.Body.Contains("contenido oculto", StringComparison.Ordinal)));
                Assert.That(
                    viewModel.Messages.All(message =>
                        !message.Body.Contains("sk-12345", StringComparison.Ordinal)
                        && !message.AccessibleText.Contains("sk-12345", StringComparison.Ordinal)),
                    Is.True);
            });

            // Forgetting destroys a record: it still asks (work_loss).
            await SubmitAsync(viewModel, "borra mi color favorito");
            Assert.That(new DurableRetryStore(outbox).Load(), Has.Count.EqualTo(1));
            await SubmitAsync(viewModel, "cancelar");
            Assert.That(new DurableRetryStore(outbox).Load(), Is.Empty);
            Assert.That(Parse(LastAssistantMessage(viewModel)).GetProperty("cancelledAction")
                .GetProperty("operation").GetString(), Is.EqualTo("memory.forget"));

            await SubmitAsync(viewModel, "qué color me gusta");
            Assert.That(LastAssistantMessage(viewModel), Does.Contain("favorite_color"));
            Assert.That(LastAssistantMessage(viewModel), Does.Contain("azul"));
        }
        finally
        {
            Environment.SetEnvironmentVariable("BAXY_DATA_DIR", previousDataRoot);
        }
    }

    [Test]
    public async Task ExportReplayFromOutboxIsResolvedOnceWithoutAFalseIntegrityClaim()
    {
        using TemporaryDirectory temporary = new();
        string? previousDataRoot = Environment.GetEnvironmentVariable("BAXY_DATA_DIR");
        Environment.SetEnvironmentVariable("BAXY_DATA_DIR", temporary.Path);
        string outbox = Path.Combine(temporary.Path, "shell", "retry-outbox.v1.json");
        string journalPath = Path.Combine(temporary.Path, "journal", "missions.jsonl");
        const string digest =
            "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";
        string absentPrivatePath = Path.Combine(
            Path.GetPathRoot(temporary.Path)!,
            "Users",
            Canary,
            "Documents",
            "BAXY",
            $"memory-export-{digest}.json");

        try
        {
            string previousSession = Guid.NewGuid().ToString("D");
            var codec = new BoundProtectedJsonCodec(
                new WindowsProtectedPayload(
                    Path.Combine(temporary.Path, "security", "private-payload.v1.key")));
            var protector = new MemoryOperationProtector(codec, previousSession);
            var registry = RetryableOperationRegistry.CreateDefault(protector);
            PreparedOperation pending = registry.GetOrAdd(protector.Prepare(
                new MemoryRoutedOperation(
                    "memory.export",
                    new JsonObject
                    {
                        ["version"] = 1,
                        ["destination"] = "documents",
                        ["includeSecrets"] = false,
                    })));
            OperationRequest request = pending.CreateRequest();
            JsonElement sealedResult = codec.SealResult(
                pending.OperationName,
                pending.MissionId,
                pending.InvocationId,
                previousSession,
                ToElement(new JsonObject
                {
                    ["version"] = 1,
                    ["path"] = absentPrivatePath,
                    ["recordCount"] = 1,
                    ["sha256"] = digest,
                    ["replayed"] = false,
                }));
            var completed = new OperationResponse(
                ProtocolTypes.OperationResponse,
                request.RequestId,
                request.MissionId,
                request.InvocationId,
                OperationStatuses.Completed,
                "Resultado privado disponible.",
                true,
                false,
                sealedResult,
                null);
            string fingerprint = RequestFingerprint.Compute(request);
            await using (FileInvocationJournal journal = await FileInvocationJournal.OpenAsync(
                             journalPath,
                             CreateJournalAuthenticator(temporary.Path, journalPath),
                             CancellationToken.None))
            {
                await journal.RecordStartedAsync(
                    request,
                    fingerprint,
                    CancellationToken.None);
                await journal.RecordCompletedAsync(
                    request,
                    fingerprint,
                    completed,
                    CancellationToken.None);
            }

            await using var viewModel = new MainWindowViewModel();
            await viewModel.InitializeAsync(CancellationToken.None);
            Assert.That(new DurableRetryStore(outbox).Load(), Has.Count.EqualTo(1));

            await SubmitAsync(viewModel, "continuar");

            string message = LastAssistantMessage(viewModel);
            Assert.Multiple(() =>
            {
                Assert.That(new DurableRetryStore(outbox).Load(), Is.Empty);
                Assert.That(viewModel.StatusDescription, Is.EqualTo("BAXY disponible"));
                Assert.That(message, Does.Contain("memory_export_unverified_replay"));
                Assert.That(message, Does.Not.Contain("No la ejecuté"));
                Assert.That(message, Does.Not.Contain("verifiqué"));
                Assert.That(message, Does.Not.Contain(absentPrivatePath));
                Assert.That(message, Does.Not.Contain(digest));
                Assert.That(message, Does.Not.Contain(Canary));
            });
        }
        finally
        {
            Environment.SetEnvironmentVariable("BAXY_DATA_DIR", previousDataRoot);
        }
    }

    [Test]
    public async Task ViewModelRecoveryDropsStaleSessionMemoryAndBlocksOnAllowedPersistentWork()
    {
        using TemporaryDirectory temporary = new();
        string? previousDataRoot = Environment.GetEnvironmentVariable("BAXY_DATA_DIR");
        Environment.SetEnvironmentVariable("BAXY_DATA_DIR", temporary.Path);
        string outbox = Path.Combine(temporary.Path, "shell", "retry-outbox.v1.json");

        try
        {
            MemoryOperationProtector previous = MemoryOperationProtector.CreateDefault(
                Guid.NewGuid().ToString("D"));
            var registry = RetryableOperationRegistry.CreateDefault(previous);
            PreparedOperation persistent = registry.GetOrAdd(previous.Prepare(
                SaveRoute(Canary + "-persistent", "persistent", "personal")));
            _ = registry.GetOrAdd(previous.Prepare(
                SaveRoute(Canary + "-session", "session", "personal")));

            await using var viewModel = new MainWindowViewModel();
            await viewModel.InitializeAsync(CancellationToken.None);

            PreparedOperation recovered = new DurableRetryStore(outbox).Load().Single();
            Assert.Multiple(() =>
            {
                Assert.That(viewModel.IsReady, Is.True);
                Assert.That(
                    viewModel.StatusDescription,
                    Is.EqualTo("Esperando comprobar la memoria"));
                Assert.That(recovered.MissionId, Is.EqualTo(persistent.MissionId));
                Assert.That(recovered.InvocationId, Is.EqualTo(persistent.InvocationId));
                Assert.That(LastAssistantMessage(viewModel), Does.Contain("continuar"));
                Assert.That(LastAssistantMessage(viewModel), Does.Not.Contain(Canary));
                Assert.That(File.ReadAllText(outbox, Encoding.UTF8), Does.Not.Contain(Canary));
            });

            await SubmitAsync(viewModel, "anota un dato distinto");
            Assert.Multiple(() =>
            {
                Assert.That(new DurableRetryStore(outbox).Load(), Has.Count.EqualTo(1));
                Assert.That(
                    LastAssistantMessage(viewModel),
                    Does.Contain("memory_recovery_pending"));
            });

            await SubmitAsync(viewModel, "continuar");
            Assert.Multiple(() =>
            {
                Assert.That(new DurableRetryStore(outbox).Load(), Is.Empty);
                Assert.That(
                    LastAssistantMessage(viewModel),
                    Does.Contain("memory_disabled"));
            });
        }
        finally
        {
            Environment.SetEnvironmentVariable("BAXY_DATA_DIR", previousDataRoot);
        }
    }

    [Test]
    public async Task RecoveredPersistentMemoryCanBeCancelledWithoutExecuting()
    {
        using TemporaryDirectory temporary = new();
        string? previousDataRoot = Environment.GetEnvironmentVariable("BAXY_DATA_DIR");
        Environment.SetEnvironmentVariable("BAXY_DATA_DIR", temporary.Path);
        string outbox = Path.Combine(temporary.Path, "shell", "retry-outbox.v1.json");

        try
        {
            MemoryOperationProtector previous = MemoryOperationProtector.CreateDefault(
                Guid.NewGuid().ToString("D"));
            var registry = RetryableOperationRegistry.CreateDefault(previous);
            PreparedOperation persistent = registry.GetOrAdd(previous.Prepare(
                SaveRoute(Canary + "-cancel", "persistent", "personal")));

            await using var viewModel = new MainWindowViewModel();
            await viewModel.InitializeAsync(CancellationToken.None);
            Assert.Multiple(() =>
            {
                Assert.That(LastAssistantMessage(viewModel), Does.Contain("memory_recovery_pending"));
                Assert.That(LastAssistantMessage(viewModel), Does.Contain("cancelar"));
                Assert.That(LastAssistantMessage(viewModel), Does.Not.Contain(Canary));
            });

            await SubmitAsync(viewModel, "cancelar");
            Assert.Multiple(() =>
            {
                Assert.That(new DurableRetryStore(outbox).Load(), Is.Empty);
                Assert.That(
                    LastAssistantMessage(viewModel),
                    Does.Contain("memory_cancelled"));
                JsonElement cancelled = Parse(LastAssistantMessage(viewModel)).GetProperty("cancelledAction");
                Assert.That(cancelled.GetProperty("operation").GetString(), Is.EqualTo("memory.save"));
                Assert.That(cancelled.GetProperty("target").GetString(), Is.EqualTo("private local memory"));
                Assert.That(cancelled.EnumerateObject().Count(), Is.EqualTo(2));
                Assert.That(LastAssistantMessage(viewModel), Does.Not.Contain(Canary));
                Assert.That(LastAssistantMessage(viewModel), Does.Not.Contain(persistent.InvocationId));
            });

            await SubmitAsync(viewModel, "hola, preséntate en una frase y no toques el sistema");
            Assert.That(
                LastAssistantMessage(viewModel),
                Does.Not.Contain("memory_recovery_pending"));
        }
        finally
        {
            Environment.SetEnvironmentVariable("BAXY_DATA_DIR", previousDataRoot);
        }
    }

    // D3 (2026-09-20): a sensitive save no longer challenges, so its uncertain
    // start is retried like any reversible operation; the reconciliation
    // challenge is exercised on memory.forget, which destroys and still asks.
    [Test]
    public async Task ReconciliationChallengeCannotBeCancelledWithAFalseNoEffectClaim()
    {
        using TemporaryDirectory temporary = new();
        string? previousDataRoot = Environment.GetEnvironmentVariable("BAXY_DATA_DIR");
        Environment.SetEnvironmentVariable("BAXY_DATA_DIR", temporary.Path);
        string outbox = Path.Combine(temporary.Path, "shell", "retry-outbox.v1.json");
        string journalPath = Path.Combine(temporary.Path, "journal", "missions.jsonl");

        try
        {
            MemoryOperationProtector previous = MemoryOperationProtector.CreateDefault(
                Guid.NewGuid().ToString("D"));
            var registry = RetryableOperationRegistry.CreateDefault(previous);
            PreparedOperation uncertain = registry.GetOrAdd(previous.Prepare(
                new MemoryRoutedOperation("memory.forget", new JsonObject
                {
                    ["version"] = 1,
                    ["confirmationRequired"] = true,
                    ["scope"] = "exact",
                    ["selector"] = Canary + "-uncertain",
                })));
            OperationRequest startedRequest = uncertain.CreateRequest();
            string fingerprint = RequestFingerprint.Compute(startedRequest);
            await using (FileInvocationJournal journal = await FileInvocationJournal.OpenAsync(
                             journalPath,
                             CreateJournalAuthenticator(temporary.Path, journalPath),
                             CancellationToken.None))
            {
                await journal.RecordStartedAsync(
                    startedRequest,
                    fingerprint,
                    CancellationToken.None);
            }

            await using var viewModel = new MainWindowViewModel();
            await viewModel.InitializeAsync(CancellationToken.None);
            await SubmitAsync(viewModel, "continuar");
            string initialReconciliation = LastAssistantMessage(viewModel);
            Assert.Multiple(() =>
            {
                Assert.That(LastAssistantMessage(viewModel), Does.Contain("memory_reconcile_same_attempt"));
                Assert.That(LastAssistantMessage(viewModel), Does.Contain("confirmar"));
                Assert.That(LastAssistantMessage(viewModel), Does.Not.Contain("memory_cancelled"));
            });

            await SubmitAsync(viewModel, "qué operación estoy confirmando");
            Assert.That(LastAssistantMessage(viewModel), Is.EqualTo(initialReconciliation));
            await SubmitAsync(viewModel, "cancelar");

            PreparedOperation preserved = new DurableRetryStore(outbox).Load().Single();
            Assert.Multiple(() =>
            {
                Assert.That(preserved.MissionId, Is.EqualTo(uncertain.MissionId));
                Assert.That(preserved.InvocationId, Is.EqualTo(uncertain.InvocationId));
                Assert.That(LastAssistantMessage(viewModel), Does.Contain("cannot_withdraw_uncertain"));
                Assert.That(LastAssistantMessage(viewModel), Does.Not.Contain("memory_cancelled"));
                JsonElement facts = Parse(LastAssistantMessage(viewModel));
                Assert.That(facts.GetProperty("pendingAction").GetProperty("operation").GetString(),
                    Is.EqualTo(uncertain.OperationName));
                Assert.That(facts.GetProperty("choices").EnumerateArray()
                    .Select(static choice => choice.GetString()), Is.EqualTo(new[] { "confirmar", "confirm" }));
                Assert.That(File.ReadAllText(outbox, Encoding.UTF8), Does.Not.Contain(Canary));
                Assert.That(
                    viewModel.Messages.All(message =>
                        !message.Body.Contains(Canary, StringComparison.Ordinal)
                        && !message.AccessibleText.Contains(Canary, StringComparison.Ordinal)),
                    Is.True);
            });
        }
        finally
        {
            Environment.SetEnvironmentVariable("BAXY_DATA_DIR", previousDataRoot);
        }
    }

    private static JsonObject RecordsPayload(
        JsonObject[] records,
        int totalCount,
        int offset,
        int limit) => new()
        {
            ["version"] = 1,
            ["records"] = new JsonArray(records.Select(static record => (JsonNode?)record).ToArray()),
            ["count"] = records.Length,
            ["totalCount"] = totalCount,
            ["offset"] = offset,
            ["limit"] = limit,
        };

    private static JsonObject Record(
        string label,
        string value,
        string sensitivity,
        string retention,
        string? expiry = null)
    {
        string? sessionId = retention == "session"
            ? Guid.NewGuid().ToString("D")
            : null;
        return new JsonObject
        {
            ["recordId"] = Guid.NewGuid().ToString("D"),
            ["revision"] = 1,
            ["selector"] = label,
            ["label"] = label,
            ["value"] = value,
            ["kind"] = "fact",
            ["origin"] = "explicit",
            ["sensitivity"] = sensitivity,
            ["retention"] = retention,
            ["tags"] = new JsonArray(JsonValue.Create("test")),
            ["createdAtUtc"] = Timestamp,
            ["updatedAtUtc"] = Timestamp,
            ["expiresAtUtc"] = expiry,
            ["sourceMissionId"] = Guid.NewGuid().ToString("D"),
            ["capturedAtUtc"] = Timestamp,
            ["sessionId"] = sessionId,
        };
    }

    private static MemoryRoutedOperation SaveRoute(
        string value,
        string retention,
        string sensitivity)
    {
        var arguments = new JsonObject
        {
            ["version"] = 1,
            ["selector"] = "name",
            ["value"] = value,
            ["kind"] = "fact",
            ["retention"] = retention,
            ["sensitivity"] = sensitivity,
            ["tags"] = new JsonArray(),
        };
        if (retention == "session")
        {
            arguments["expiryPolicy"] = "session_end";
        }

        return new MemoryRoutedOperation("memory.save", arguments);
    }

    private static MemoryOperationProtector CreateProtector(
        TemporaryDirectory temporary,
        string sessionId) => new(
            new BoundProtectedJsonCodec(
                new WindowsProtectedPayload(
                    Path.Combine(temporary.Path, "security", "private-payload.v1.key"))),
            sessionId);

    private static JournalHmacAuthenticator CreateJournalAuthenticator(
        string dataRoot,
        string journalPath)
    {
        var privatePayload = new WindowsProtectedPayload(
            Path.Combine(dataRoot, "security", "private-payload.v1.key"));
        var keyStore = new WindowsJournalAuthenticationKeyStore(
            Path.Combine(dataRoot, "security", "journal-hmac.v2.key"),
            privatePayload);
        bool allowCreate = !File.Exists(journalPath)
            && !File.Exists(string.Concat(journalPath, ".anchor"));
        byte[] key = keyStore.LoadOrCreate(allowCreate);
        try
        {
            return new JournalHmacAuthenticator(key);
        }
        finally
        {
            CryptographicOperations.ZeroMemory(key);
        }
    }

    private static async Task SubmitAsync(MainWindowViewModel viewModel, string text)
    {
        viewModel.Draft = text;
        await viewModel.SubmitAsync(CancellationToken.None);
    }

    private static string LastAssistantMessage(MainWindowViewModel viewModel) =>
        viewModel.Messages.Last(static message => !message.IsUser).Body;

    private static JsonElement Parse(string json) =>
        JsonDocument.Parse(json).RootElement.Clone();

    private static JsonElement ToElement(JsonNode node) =>
        JsonSerializer.SerializeToElement(node);

    private static string Base64Url(ReadOnlySpan<byte> value) =>
        Convert.ToBase64String(value)
            .TrimEnd('=')
            .Replace('+', '-')
            .Replace('/', '_');

    private sealed class TemporaryDirectory : IDisposable
    {
        internal TemporaryDirectory()
        {
            Path = PrivateDataRootTestSupport.NewPath("memory-app");
            Directory.CreateDirectory(Path);
        }

        internal string Path { get; }

        public void Dispose()
        {
            if (Directory.Exists(Path))
            {
                Directory.Delete(Path, recursive: true);
            }
        }
    }
}
