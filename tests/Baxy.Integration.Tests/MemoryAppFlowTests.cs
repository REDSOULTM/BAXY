using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.App;
using Baxy.Contracts;
using Baxy.Kernel.Journal;
using Baxy.Kernel.Mission;
using Baxy.Security.Windows;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
[NonParallelizable]
public sealed class MemoryAppFlowTests
{
    private const string Canary = "BAXY-MEMORY-APP-private-Alex";
    private const string Timestamp = "2026-07-15T15:00:00.0000000+00:00";

    [TestCase(
        "memory.enable",
        "{\"version\":1,\"enabled\":true,\"replayed\":false}",
        "habilitada")]
    [TestCase(
        "memory.disable",
        "{\"version\":1,\"enabled\":false,\"replayed\":true}",
        "deshabilitada")]
    [TestCase(
        "memory.save",
        "{\"version\":1,\"recordId\":\"52dc83f9-cee9-49e6-bd99-20c9b1c67dda\",\"revision\":1,\"selector\":\"favorite_color\",\"replayed\":false}",
        "Guardé")]
    [TestCase(
        "memory.correct",
        "{\"version\":1,\"recordId\":\"52dc83f9-cee9-49e6-bd99-20c9b1c67dda\",\"revision\":2,\"selector\":\"favorite_color\",\"replayed\":false}",
        "Corregí")]
    [TestCase(
        "memory.forget",
        "{\"version\":1,\"deletedCount\":2,\"replayed\":false}",
        "2 memorias")]
    [TestCase(
        "memory.status",
        "{\"version\":1,\"enabled\":true,\"totalRecords\":3,\"persistentRecords\":1,\"sessionRecords\":1,\"temporaryRecords\":1,\"maximumRecords\":512}",
        "3 en total")]
    [TestCase(
        "memory.export",
        "{\"version\":1,\"path\":\"C:\\\\Users\\\\local\\\\Documents\\\\BAXY\\\\memory-export-0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef.json\",\"recordCount\":3,\"sha256\":\"abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789\",\"replayed\":false}",
        "Documentos/BAXY")]
    public void StrictProjectionAcceptsOnlyKnownCompletedShapes(
        string operation,
        string json,
        string expectedNaturalText)
    {
        bool accepted = MemoryOperationResponseProjection.TryCreateCompleted(
            operation,
            Parse(json),
            out MemoryOperationResponseProjection? projection);
        UserMessageDraft draft = UserMessagePolicy.Create(
            projection?.Message ?? "proyección ausente",
            UserMessageEvent.Status);

        Assert.Multiple(() =>
        {
            Assert.That(accepted, Is.True);
            Assert.That(projection, Is.Not.Null);
            Assert.That(projection!.Message, Does.Contain(expectedNaturalText));
            Assert.That(projection.Message, Does.Not.StartWith("{"));
            Assert.That(projection.Message, Does.Not.Contain("52dc83f9-cee9-49e6-bd99-20c9b1c67dda"));
            Assert.That(projection.Message, Does.Not.Contain("favorite_color"));
            Assert.That(
                UserMessagePolicy.ModelResponseRejectionReason(
                    projection.Message,
                    draft),
                Is.Null);
        });
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
            Assert.That(projection!.Message, Does.Contain("Documentos/BAXY"));
            Assert.That(projection.Message, Does.Contain("redirigida o sincronizada"));
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
            Assert.That(projection!.Message, Does.Contain("ya estaba disponible"));
            Assert.That(projection.Message, Does.Contain("integridad SHA-256 fue verificada"));
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

            await SubmitAsync(viewModel, "activa la memoria");
            PreparedOperation enable = new DurableRetryStore(outbox).Load().Single();
            Assert.Multiple(() =>
            {
                Assert.That(enable.OperationName, Is.EqualTo("memory.enable"));
                Assert.That(LastAssistantMessage(viewModel), Does.Contain("confirmar"));
            });

            await SubmitAsync(viewModel, "sí y guarda");
            PreparedOperation stillPending = new DurableRetryStore(outbox).Load().Single();
            Assert.Multiple(() =>
            {
                Assert.That(stillPending.MissionId, Is.EqualTo(enable.MissionId));
                Assert.That(stillPending.InvocationId, Is.EqualTo(enable.InvocationId));
                Assert.That(LastAssistantMessage(viewModel), Does.Contain("memory_confirm_or_cancel"));
            });

            await SubmitAsync(viewModel, "confirmar");
            Assert.Multiple(() =>
            {
                Assert.That(new DurableRetryStore(outbox).Load(), Is.Empty);
                Assert.That(LastAssistantMessage(viewModel), Does.Contain("memoria local está habilitada"));
            });

            await SubmitAsync(viewModel, "recuerda que mi color favorito es azul");
            Assert.Multiple(() =>
            {
                Assert.That(new DurableRetryStore(outbox).Load(), Is.Empty);
                Assert.That(LastAssistantMessage(viewModel), Does.Contain("Guardé el dato"));
            });

            await SubmitAsync(viewModel, "qué color me gusta");
            Assert.Multiple(() =>
            {
                Assert.That(LastAssistantMessage(viewModel), Does.Contain("favorite_color"));
                Assert.That(LastAssistantMessage(viewModel), Does.Contain("azul"));
                Assert.That(LastAssistantMessage(viewModel), Does.Contain("memory_records"));
            });

            const string sensitiveRequest = "save my api key sk-12345 in your memory";
            await SubmitAsync(viewModel, sensitiveRequest);
            Assert.Multiple(() =>
            {
                Assert.That(new DurableRetryStore(outbox).Load(), Is.Empty);
                Assert.That(LastAssistantMessage(viewModel), Does.Contain("memory_sensitive_save"));
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

            await SubmitAsync(viewModel, "cancelar");
            Assert.Multiple(() =>
            {
                Assert.That(new DurableRetryStore(outbox).Load(), Is.Empty);
                Assert.That(LastAssistantMessage(viewModel), Does.Contain("memory_cancelled"));
            });

            await SubmitAsync(viewModel, "borra mi color favorito");
            Assert.That(new DurableRetryStore(outbox).Load(), Has.Count.EqualTo(1));
            await SubmitAsync(viewModel, "cancelar");
            Assert.That(new DurableRetryStore(outbox).Load(), Is.Empty);

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
                SaveRoute(Canary + "-uncertain", "persistent", "secret")));
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
            Assert.Multiple(() =>
            {
                Assert.That(LastAssistantMessage(viewModel), Does.Contain("memory_reconcile_same_attempt"));
                Assert.That(LastAssistantMessage(viewModel), Does.Contain("confirmar"));
                Assert.That(LastAssistantMessage(viewModel), Does.Not.Contain("memory_cancelled"));
            });

            await SubmitAsync(viewModel, "cancelar");

            PreparedOperation preserved = new DurableRetryStore(outbox).Load().Single();
            Assert.Multiple(() =>
            {
                Assert.That(preserved.MissionId, Is.EqualTo(uncertain.MissionId));
                Assert.That(preserved.InvocationId, Is.EqualTo(uncertain.InvocationId));
                Assert.That(LastAssistantMessage(viewModel), Does.Contain("cannot_withdraw_uncertain"));
                Assert.That(LastAssistantMessage(viewModel), Does.Not.Contain("memory_cancelled"));
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
