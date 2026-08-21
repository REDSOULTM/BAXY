using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.App;
using Baxy.Contracts;
using Baxy.Core.Operations;
using Baxy.Kernel.Journal;
using Baxy.Kernel.Mission;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Memory;
using Baxy.Security.Windows;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class MemoryHandlersTests
{
    private const string Canary = "BAXY-PRIVATE-MEMORY-CANARY-Alex";
    private static readonly DateTimeOffset Now =
        new(2026, 7, 15, 16, 30, 0, TimeSpan.Zero);

    [Test]
    public void FactoryExposesEveryMemoryOperationWithTheRequiredRisk()
    {
        using Harness harness = new();
        var expected = new Dictionary<string, OperationRisk>(StringComparer.Ordinal)
        {
            [MemoryOperationIds.Enable] = OperationRisk.Sensitive,
            [MemoryOperationIds.Disable] = OperationRisk.Reversible,
            [MemoryOperationIds.Save] = OperationRisk.Reversible,
            [MemoryOperationIds.SensitiveSave] = OperationRisk.Sensitive,
            [MemoryOperationIds.Forget] = OperationRisk.Irreversible,
            [MemoryOperationIds.SessionClear] = OperationRisk.Reversible,
            [MemoryOperationIds.Export] = OperationRisk.Sensitive,
            [MemoryOperationIds.Correct] = OperationRisk.Reversible,
            [MemoryOperationIds.Recall] = OperationRisk.ReadOnly,
            [MemoryOperationIds.List] = OperationRisk.ReadOnly,
            [MemoryOperationIds.Status] = OperationRisk.ReadOnly,
        };

        Assert.That(
            harness.Handlers.ToDictionary(
                pair => pair.Key,
                pair => pair.Value.Definition.Risk,
                StringComparer.Ordinal),
            Is.EqualTo(expected));
    }

    [Test]
    public async Task EnableUsesGlobalStoreScopeAndReturnsOnlyASealedPrivateResult()
    {
        using Harness harness = new();
        InvocationCase request = harness.Invocation(
            MemoryOperationIds.Enable,
            new JsonObject { ["version"] = 1, ["enabled"] = true });

        OperationOutcome outcome = await harness.ExecuteAsync(request);
        using OpenedBoundProtectedJson opened = harness.OpenResult(request, outcome);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True);
            Assert.That(
                Message(outcome),
                Is.EqualTo("Completé y verifiqué la petición sobre la memoria local."));
            Assert.That(outcome.Result?.GetRawText(), Does.Not.Contain("enabled"));
            Assert.That(opened.Payload.GetProperty("enabled").GetBoolean(), Is.True);
            Assert.That(harness.Store.ConfigureRequests.Single().InvocationId,
                Is.EqualTo(request.Invocation.InvocationId));
            Assert.That(harness.Store.BeginSessions, Is.Empty);
        });
    }

    [Test]
    public async Task PersistentSaveDoesNotReactivateSessionAndCanonicalizesScalarValue()
    {
        using Harness harness = new();
        InvocationCase request = harness.Invocation(
            MemoryOperationIds.Save,
            SavePayload(JsonValue.Create(false), "persistent", "normal"));

        OperationOutcome outcome = await harness.ExecuteAsync(request);
        MemorySaveRequest saved = harness.Store.SaveRequests.Single();

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True);
            Assert.That(saved.Value, Is.EqualTo("false"));
            Assert.That(saved.SessionId, Is.Null);
            Assert.That(saved.SourceMissionId, Is.EqualTo(request.Invocation.MissionId));
            Assert.That(saved.CapturedAtUtc, Is.EqualTo(Now));
            Assert.That(harness.Store.BeginSessions, Is.Empty);
            Assert.That(outcome.Result?.GetRawText(), Does.Not.Contain("false"));
        });
    }

    [Test]
    public async Task SessionAndTemporarySaveValidateOriginSessionWithStoreCompatibleRetention()
    {
        using Harness harness = new();
        string session = Guid.NewGuid().ToString("D");
        InvocationCase sessionRequest = harness.Invocation(
            MemoryOperationIds.Save,
            SavePayload(JsonValue.Create("session value"), "session", "normal", "session_end"),
            session);
        InvocationCase temporaryRequest = harness.Invocation(
            MemoryOperationIds.Save,
            SavePayload(
                JsonValue.Create("temporary value"),
                "temporary",
                "normal",
                "after_relevance_window"),
            session);

        _ = await harness.ExecuteAsync(sessionRequest);
        _ = await harness.ExecuteAsync(temporaryRequest);

        Assert.Multiple(() =>
        {
            Assert.That(harness.Store.BeginSessions,
                Is.EqualTo(new[] { session, session }));
            Assert.That(harness.Store.SaveRequests[0].Retention,
                Is.EqualTo(MemoryRetention.Session));
            Assert.That(harness.Store.SaveRequests[0].SessionId, Is.EqualTo(session));
            Assert.That(harness.Store.SaveRequests[0].ExpiresAtUtc, Is.Null);
            Assert.That(harness.Store.SaveRequests[1].Retention,
                Is.EqualTo(MemoryRetention.Temporary));
            Assert.That(harness.Store.SaveRequests[1].SessionId, Is.Null);
            Assert.That(harness.Store.SaveRequests[1].ExpiresAtUtc,
                Is.EqualTo(Now.AddHours(24)));
        });
    }

    [Test]
    public async Task SensitiveAndRegularWireOperationsCannotDowngradeEachOther()
    {
        using Harness harness = new();
        InvocationCase validSensitive = harness.Invocation(
            MemoryOperationIds.SensitiveSave,
            SavePayload(JsonValue.Create(Canary), "persistent", "secret"));
        InvocationCase downgraded = harness.Invocation(
            MemoryOperationIds.Save,
            SavePayload(JsonValue.Create(Canary), "persistent", "secret"));
        InvocationCase inflated = harness.Invocation(
            MemoryOperationIds.SensitiveSave,
            SavePayload(JsonValue.Create("ordinary"), "persistent", "normal"));

        OperationOutcome valid = await harness.ExecuteAsync(validSensitive);
        OperationOutcome lowRisk = await harness.ExecuteAsync(downgraded);
        OperationOutcome highRisk = await harness.ExecuteAsync(inflated);

        Assert.Multiple(() =>
        {
            Assert.That(valid.Succeeded, Is.True);
            Assert.That(harness.Store.SaveRequests.Single().Sensitivity,
                Is.EqualTo(MemorySensitivity.Secret));
            Assert.That(lowRisk.ErrorCode, Is.EqualTo("invalid_arguments"));
            Assert.That(highRisk.ErrorCode, Is.EqualTo("invalid_arguments"));
            Assert.That(Message(lowRisk), Does.Not.Contain(Canary));
        });
    }

    [Test]
    public async Task ForgetIsGlobalWhileSessionClearTouchesOnlyTheBoundSession()
    {
        using Harness harness = new();
        string session = Guid.NewGuid().ToString("D");
        InvocationCase exact = harness.Invocation(
            MemoryOperationIds.Forget,
            new JsonObject
            {
                ["version"] = 1,
                ["scope"] = "exact",
                ["selector"] = "favorite_color",
                ["confirmationRequired"] = true,
            },
            session);
        InvocationCase clear = harness.Invocation(
            MemoryOperationIds.SessionClear,
            new JsonObject
            {
                ["version"] = 1,
                ["scope"] = "session",
                ["selector"] = null,
                ["confirmationRequired"] = false,
                ["mustNotDeletePersistent"] = true,
            },
            session);

        _ = await harness.ExecuteAsync(exact);
        _ = await harness.ExecuteAsync(clear);

        Assert.Multiple(() =>
        {
            Assert.That(harness.Store.ForgetRequests[0].Scope,
                Is.EqualTo(MemoryForgetScope.Exact));
            Assert.That(harness.Store.ForgetRequests[0].SessionId, Is.Null);
            Assert.That(harness.Store.ForgetRequests[1].Scope,
                Is.EqualTo(MemoryForgetScope.Session));
            Assert.That(harness.Store.ForgetRequests[1].SessionId, Is.EqualTo(session));
            Assert.That(harness.Store.BeginSessions, Is.EqualTo(new[] { session }));
        });
    }

    [Test]
    public async Task RecallBeginsSessionAndKeepsPrivateRecordsOutOfPublicOutcome()
    {
        using Harness harness = new();
        string session = Guid.NewGuid().ToString("D");
        harness.Store.RecallResult = new MemoryRecallResult([Record(Canary, session)]);
        InvocationCase request = harness.Invocation(
            MemoryOperationIds.Recall,
            new JsonObject
            {
                ["version"] = 1,
                ["scope"] = "exact",
                ["selector"] = "name",
            },
            session);

        OperationOutcome outcome = await harness.ExecuteAsync(request);
        using OpenedBoundProtectedJson opened = harness.OpenResult(request, outcome);

        Assert.Multiple(() =>
        {
            Assert.That(Message(outcome), Does.Not.Contain(Canary));
            Assert.That(outcome.Result?.GetRawText(), Does.Not.Contain(Canary));
            Assert.That(
                opened.Payload.GetProperty("records")[0].GetProperty("value").GetString(),
                Is.EqualTo(Canary));
            Assert.That(harness.Store.BeginSessions, Is.EqualTo(new[] { session }));
            Assert.That(harness.Store.RecallRequests.Single().SessionId, Is.EqualTo(session));
        });
    }

    [Test]
    public async Task CorrectResolvesExactRevisionThenPassesBothCasGuards()
    {
        using Harness harness = new();
        string session = Guid.NewGuid().ToString("D");
        harness.Store.RecallResult = new MemoryRecallResult([
            Record("old", session) with
            {
                Selector = "RESPONSE_STYLE",
                Revision = 7,
                Retention = MemoryRetention.Persistent,
            },
        ]);
        InvocationCase request = harness.Invocation(
            MemoryOperationIds.Correct,
            new JsonObject
            {
                ["version"] = 1,
                ["selector"] = "response_style",
                ["value"] = false,
                ["expectedValue"] = "old",
                ["kind"] = "fact",
                ["retention"] = "persistent",
            },
            session);

        OperationOutcome outcome = await harness.ExecuteAsync(request);
        MemoryCorrectRequest corrected = harness.Store.CorrectRequests.Single();

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True);
            Assert.That(corrected.ExpectedRevision, Is.EqualTo(7));
            Assert.That(corrected.ExpectedValue, Is.EqualTo("old"));
            Assert.That(corrected.NewValue, Is.EqualTo("false"));
            Assert.That(corrected.SessionId, Is.EqualTo(session));
            Assert.That(harness.Store.BeginSessions, Is.EqualTo(new[] { session }));
        });
    }

    [Test]
    public async Task ExportCreatesInspectableSecretFreeJsonAndReplaysTheSameFile()
    {
        using Harness harness = new();
        MemoryRecord visible = Record("azul", null) with
        {
            Selector = "FAVORITE_COLOR",
            Label = "Color favorito",
            Tags = ["profile"],
        };
        MemoryRecord secret = Record(Canary, null) with
        {
            Selector = Canary,
            Label = Canary,
            Sensitivity = MemorySensitivity.Secret,
            Tags = [Canary],
        };
        harness.Store.ListResult = new MemoryListResult([secret, visible]);
        InvocationCase request = harness.Invocation(
            MemoryOperationIds.Export,
            new JsonObject
            {
                ["version"] = 1,
                ["destination"] = "documents",
                ["includeSecrets"] = false,
            });

        OperationOutcome first = await harness.ExecuteAsync(request);
        using OpenedBoundProtectedJson firstResult = harness.OpenResult(request, first);
        string path = firstResult.Payload.GetProperty("path").GetString()!;
        string firstHash = firstResult.Payload.GetProperty("sha256").GetString()!;
        bool projected = MemoryOperationResponseProjection.TryCreateCompleted(
            MemoryOperationIds.Export,
            firstResult.Payload,
            out MemoryOperationResponseProjection? projection);
        byte[] firstBytes = File.ReadAllBytes(path);
        OperationOutcome second = await harness.ExecuteAsync(request);
        using OpenedBoundProtectedJson secondResult = harness.OpenResult(request, second);
        using JsonDocument export = JsonDocument.Parse(firstBytes);
        JsonElement root = export.RootElement;
        JsonElement secretExport = root.GetProperty("records")
            .EnumerateArray()
            .Single(static record => string.Equals(
                record.GetProperty("sensitivity").GetString(),
                "secret",
                StringComparison.Ordinal));
        string text = Encoding.UTF8.GetString(firstBytes);

        Assert.Multiple(() =>
        {
            Assert.That(first.Succeeded, Is.True);
            Assert.That(second.Succeeded, Is.True);
            Assert.That(Message(first), Does.Not.Contain(Canary));
            Assert.That(first.Result?.GetRawText(), Does.Not.Contain(Canary));
            Assert.That(path, Does.Not.Contain(Canary));
            Assert.That(path, Does.StartWith(
                Path.Combine(harness.DocumentsPath, LocalMemoryExportWriter.ExportDirectoryName)
                    + Path.DirectorySeparatorChar));
            Assert.That(Path.GetFileName(path), Does.Match(
                "^memory-export-[0-9a-f]{64}\\.json$"));
            Assert.That(firstHash, Is.EqualTo(
                Convert.ToHexStringLower(SHA256.HashData(firstBytes))));
            Assert.That(projected, Is.True);
            Assert.That(projection!.Message, Does.Contain("Documentos/BAXY"));
            Assert.That(projection.Message, Does.Not.Contain(path));
            Assert.That(projection.Message, Does.Not.Contain(firstHash));
            Assert.That(projection.Message, Does.Not.Contain(Canary));
            Assert.That(secondResult.Payload.GetProperty("path").GetString(), Is.EqualTo(path));
            Assert.That(secondResult.Payload.GetProperty("sha256").GetString(), Is.EqualTo(firstHash));
            Assert.That(secondResult.Payload.GetProperty("replayed").GetBoolean(), Is.True);
            Assert.That(File.ReadAllBytes(path), Is.EqualTo(firstBytes));
            Assert.That(root.EnumerateObject().Select(static property => property.Name),
                Is.EquivalentTo(new[]
                {
                    "schema",
                    "version",
                    "invocationId",
                    "includeSecretValues",
                    "recordCount",
                    "records",
                }));
            Assert.That(root.GetProperty("schema").GetString(), Is.EqualTo("baxy.memory.export"));
            Assert.That(root.GetProperty("version").GetInt32(), Is.EqualTo(1));
            Assert.That(root.GetProperty("invocationId").GetString(),
                Is.EqualTo(request.Invocation.InvocationId));
            Assert.That(root.GetProperty("includeSecretValues").GetBoolean(), Is.False);
            Assert.That(root.GetProperty("recordCount").GetInt32(), Is.EqualTo(2));
            Assert.That(root.GetProperty("records").GetArrayLength(), Is.EqualTo(2));
            Assert.That(text, Does.Contain("Color favorito"));
            Assert.That(text, Does.Contain("azul"));
            Assert.That(text, Does.Not.Contain(Canary));
            Assert.That(secretExport.GetProperty("selector").GetString(),
                Is.EqualTo(LocalMemoryExportWriter.RedactedValue));
            Assert.That(secretExport.GetProperty("label").GetString(),
                Is.EqualTo(LocalMemoryExportWriter.RedactedValue));
            Assert.That(secretExport.GetProperty("value").GetString(),
                Is.EqualTo(LocalMemoryExportWriter.RedactedValue));
            Assert.That(secretExport.GetProperty("valueRedacted").GetBoolean(), Is.True);
            Assert.That(secretExport.GetProperty("tags").GetArrayLength(), Is.Zero);
            Assert.That(harness.Store.BeginSessions,
                Is.EqualTo(new[] { request.SessionId, request.SessionId }));
            Assert.That(harness.Store.ListRequests.Select(static value => value.SessionId),
                Is.EqualTo(new[] { request.SessionId, request.SessionId }));
        });
    }

    [TestCase("untouched", true)]
    [TestCase("deleted", false)]
    [TestCase("tampered", false)]
    public async Task JournalReplayOfExportRequiresFreshArtifactVerification(
        string artifactState,
        bool expectedVerified)
    {
        using Harness harness = new();
        harness.Store.ListResult = new MemoryListResult([Record("visible", null)]);
        InvocationCase invocation = harness.Invocation(
            MemoryOperationIds.Export,
            new JsonObject
            {
                ["version"] = 1,
                ["destination"] = "documents",
                ["includeSecrets"] = false,
            });
        var request = new OperationRequest(
            ProtocolTypes.OperationRequest,
            invocation.Invocation.RequestId,
            invocation.Invocation.MissionId,
            invocation.Invocation.InvocationId,
            invocation.Operation,
            invocation.Invocation.Arguments);
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(
            new OperationRegistry(harness.Handlers.Values),
            journal,
                               new MissionEngineOptions { PrivateEnvelopeAuthenticator = new MemoryEnvelopeAuthenticator(harness.Codec, harness.ExportWriter) });

        OperationResponse challenge = await engine.ExecuteAsync(
            request,
            CancellationToken.None);
        string token = challenge.Result!.Value.GetProperty("token").GetString()!;
        OperationResponse completed = await engine.ExecuteAsync(
            request with
            {
                RequestId = Guid.NewGuid().ToString("D"),
                ConfirmationToken = token,
            },
            CancellationToken.None);
        using OpenedBoundProtectedJson opened = harness.Codec.OpenResult(
            completed.Result!.Value,
            request.Operation,
            request.MissionId,
            request.InvocationId);
        string path = opened.Payload.GetProperty("path").GetString()!;
        if (string.Equals(artifactState, "deleted", StringComparison.Ordinal))
        {
            File.Delete(path);
        }
        else if (string.Equals(artifactState, "tampered", StringComparison.Ordinal))
        {
            File.WriteAllText(path, "{\"tampered\":true}\n", new UTF8Encoding(false));
        }

        OperationResponse replay = await engine.ExecuteAsync(
            request with
            {
                RequestId = Guid.NewGuid().ToString("D"),
                ConfirmationToken = null,
            },
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(completed.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(completed.Verified, Is.True);
            Assert.That(
                replay.Status,
                Is.EqualTo(expectedVerified
                    ? OperationStatuses.Completed
                    : OperationStatuses.Failed));
            Assert.That(replay.Verified, Is.EqualTo(expectedVerified));
            Assert.That(replay.Replayed, Is.True);
            Assert.That(
                replay.ErrorCode,
                expectedVerified ? Is.Null : Is.EqualTo("memory_operation_failed"));
            Assert.That(
                replay.Result.HasValue,
                Is.EqualTo(expectedVerified));
            Assert.That(replay.Message, Does.Not.Contain(path));
            Assert.That(harness.Store.ListRequests, Has.Count.EqualTo(1));
        });
    }

    [Test]
    public async Task ExportConflictAndUnsafeDestinationFailClosedWithoutOverwriting()
    {
        using Harness harness = new();
        harness.Store.ListResult = new MemoryListResult([Record("visible", null)]);
        InvocationCase request = harness.Invocation(
            MemoryOperationIds.Export,
            new JsonObject
            {
                ["version"] = 1,
                ["destination"] = "documents",
                ["includeSecrets"] = false,
            });
        OperationOutcome created = await harness.ExecuteAsync(request);
        using OpenedBoundProtectedJson createdResult = harness.OpenResult(request, created);
        string path = createdResult.Payload.GetProperty("path").GetString()!;
        const string tampered = "{\"tampered\":true}\n";
        File.WriteAllText(path, tampered, new UTF8Encoding(false));

        OperationOutcome conflict = await harness.ExecuteAsync(request);
        using Harness unsafeHarness = new(unsafeDocumentsPath: true);
        InvocationCase unsafeRequest = unsafeHarness.Invocation(
            MemoryOperationIds.Export,
            new JsonObject
            {
                ["version"] = 1,
                ["destination"] = "documents",
                ["includeSecrets"] = false,
            });
        OperationOutcome unsafeOutcome = await unsafeHarness.ExecuteAsync(unsafeRequest);

        Assert.Multiple(() =>
        {
            Assert.That(conflict.Succeeded, Is.False);
            Assert.That(conflict.ErrorCode, Is.EqualTo("memory_export_conflict"));
            Assert.That(conflict.Result, Is.Null);
            Assert.That(Message(conflict), Does.Not.Contain(path));
            Assert.That(File.ReadAllText(path, Encoding.UTF8), Is.EqualTo(tampered));
            Assert.That(unsafeOutcome.Succeeded, Is.False);
            Assert.That(unsafeOutcome.ErrorCode, Is.EqualTo("memory_export_unavailable"));
            Assert.That(unsafeOutcome.Result, Is.Null);
            Assert.That(Message(unsafeOutcome), Does.Not.Contain(unsafeHarness.DocumentsPath));
            Assert.That(Directory.Exists(
                Path.Combine(
                    unsafeHarness.DocumentsPath,
                    LocalMemoryExportWriter.ExportDirectoryName)),
                Is.False);
        });
    }

    [Test]
    public async Task ExportRejectsMoreThanTheFiniteRecordLimitWithoutCreatingAFile()
    {
        using Harness harness = new();
        harness.Store.ListResult = new MemoryListResult(
            Enumerable.Range(0, LocalMemoryStore.MaximumRecords + 1)
                .Select(index => Record($"visible-{index}", null))
                .ToArray());
        InvocationCase request = harness.Invocation(
            MemoryOperationIds.Export,
            new JsonObject
            {
                ["version"] = 1,
                ["destination"] = "documents",
                ["includeSecrets"] = false,
            });

        OperationOutcome outcome = await harness.ExecuteAsync(request);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo("memory_export_unavailable"));
            Assert.That(outcome.Result, Is.Null);
            Assert.That(Directory.Exists(Path.Combine(
                harness.DocumentsPath,
                LocalMemoryExportWriter.ExportDirectoryName)),
                Is.False);
        });
    }

    [Test]
    public async Task ExportNeverAcceptsSecretValuesOrANonDocumentsDestination()
    {
        using Harness harness = new();
        InvocationCase secrets = harness.Invocation(
            MemoryOperationIds.Export,
            new JsonObject
            {
                ["version"] = 1,
                ["destination"] = "documents",
                ["includeSecrets"] = true,
            });
        InvocationCase redirected = harness.Invocation(
            MemoryOperationIds.Export,
            new JsonObject
            {
                ["version"] = 1,
                ["destination"] = "desktop",
                ["includeSecrets"] = false,
            });

        OperationOutcome secretsOutcome = await harness.ExecuteAsync(secrets);
        OperationOutcome redirectedOutcome = await harness.ExecuteAsync(redirected);

        Assert.Multiple(() =>
        {
            Assert.That(secretsOutcome.ErrorCode, Is.EqualTo("invalid_arguments"));
            Assert.That(redirectedOutcome.ErrorCode, Is.EqualTo("invalid_arguments"));
            Assert.That(secretsOutcome.Result, Is.Null);
            Assert.That(redirectedOutcome.Result, Is.Null);
            Assert.That(harness.Store.TotalCalls, Is.Zero);
            Assert.That(Directory.Exists(Path.Combine(
                harness.DocumentsPath,
                LocalMemoryExportWriter.ExportDirectoryName)),
                Is.False);
        });
    }

    [Test]
    public async Task ExportRejectsAReparsePointInTheDocumentsChain()
    {
        string root = Path.Combine(
            Path.GetTempPath(),
            $"baxy-memory-export-link-{Guid.NewGuid():N}");
        string realDocuments = Path.Combine(root, "real-documents");
        string linkedDocuments = Path.Combine(root, "linked-documents");
        Directory.CreateDirectory(realDocuments);
        try
        {
            _ = Baxy.Tests.NtfsTestJunction.Create(linkedDocuments, realDocuments);

            using Harness harness = new(documentsPath: linkedDocuments);
            InvocationCase request = harness.Invocation(
                MemoryOperationIds.Export,
                new JsonObject
                {
                    ["version"] = 1,
                    ["destination"] = "documents",
                    ["includeSecrets"] = false,
                });

            OperationOutcome outcome = await harness.ExecuteAsync(request);

            Assert.Multiple(() =>
            {
                Assert.That(outcome.Succeeded, Is.False);
                Assert.That(outcome.ErrorCode, Is.EqualTo("memory_export_unavailable"));
                Assert.That(outcome.Result, Is.Null);
                Assert.That(Directory.Exists(Path.Combine(
                    realDocuments,
                    LocalMemoryExportWriter.ExportDirectoryName)),
                    Is.False);
            });
        }
        finally
        {
            if (Directory.Exists(linkedDocuments)
                && (File.GetAttributes(linkedDocuments) & FileAttributes.ReparsePoint) != 0)
            {
                Directory.Delete(linkedDocuments);
            }

            if (Directory.Exists(root))
            {
                Directory.Delete(root, recursive: true);
            }
        }
    }

    [Test]
    public async Task StrictSchemaVersionAndBindingFailuresNeverReachStore()
    {
        using Harness harness = new();
        InvocationCase extra = harness.Invocation(
            MemoryOperationIds.Enable,
            new JsonObject { ["version"] = 1, ["enabled"] = true, ["extra"] = Canary });
        InvocationCase wrongVersion = harness.Invocation(
            MemoryOperationIds.Status,
            new JsonObject { ["version"] = 2 });
        InvocationCase saveEnvelope = harness.Invocation(
            MemoryOperationIds.Save,
            SavePayload(JsonValue.Create(Canary), "persistent", "normal"));
        InvocationCase invalidRecall = harness.Invocation(
            MemoryOperationIds.Recall,
            new JsonObject
            {
                ["version"] = 1,
                ["scope"] = "unknown",
                ["selector"] = "name",
            });
        InvocationCase relabeled = saveEnvelope with
        {
            Invocation = saveEnvelope.Invocation with
            {
                Arguments = saveEnvelope.Invocation.Arguments,
            },
            Operation = MemoryOperationIds.Recall,
        };

        OperationOutcome extraOutcome = await harness.ExecuteAsync(extra);
        OperationOutcome versionOutcome = await harness.ExecuteAsync(wrongVersion);
        OperationOutcome recallOutcome = await harness.ExecuteAsync(invalidRecall);
        OperationOutcome bindingOutcome = await harness.ExecuteAsync(relabeled);

        Assert.Multiple(() =>
        {
            Assert.That(extraOutcome.ErrorCode, Is.EqualTo("invalid_arguments"));
            Assert.That(versionOutcome.ErrorCode, Is.EqualTo("invalid_arguments"));
            Assert.That(recallOutcome.ErrorCode, Is.EqualTo("invalid_arguments"));
            Assert.That(bindingOutcome.ErrorCode, Is.EqualTo("memory_protection_failed"));
            Assert.That(Message(bindingOutcome), Does.Not.Contain(Canary));
            Assert.That(harness.Store.TotalCalls, Is.Zero);
        });
    }

    [Test]
    public async Task StoreErrorsReturnSafeOutcomesWithoutEchoingPrivateInput()
    {
        using Harness harness = new();
        harness.Store.SaveException = new MemoryConflictException();
        InvocationCase request = harness.Invocation(
            MemoryOperationIds.Save,
            SavePayload(JsonValue.Create(Canary), "persistent", "normal"));

        OperationOutcome outcome = await harness.ExecuteAsync(request);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo("memory_conflict"));
            Assert.That(Message(outcome), Does.Not.Contain(Canary));
            Assert.That(outcome.Result, Is.Null);
        });
    }

    private static string Message(OperationOutcome outcome) =>
        OperationOutcomeNarration.For(MemoryOperationIds.Status, outcome);

    private static JsonObject SavePayload(
        JsonNode? value,
        string retention,
        string sensitivity,
        string? expiryPolicy = null)
    {
        var payload = new JsonObject
        {
            ["version"] = 1,
            ["selector"] = "name",
            ["value"] = value,
            ["kind"] = "fact",
            ["retention"] = retention,
            ["sensitivity"] = sensitivity,
            ["tags"] = new JsonArray(),
        };
        if (expiryPolicy is not null)
        {
            payload["expiryPolicy"] = expiryPolicy;
        }

        return payload;
    }

    private static MemoryRecord Record(string value, string? sessionId) => new(
        Guid.NewGuid(),
        1,
        "NAME",
        "Name",
        value,
        MemoryKind.Fact,
        MemoryOrigin.Explicit,
        MemorySensitivity.Personal,
        sessionId is null ? MemoryRetention.Persistent : MemoryRetention.Session,
        [],
        Now,
        Now,
        null,
        Guid.NewGuid().ToString("D"),
        Now,
        sessionId);

    private sealed record InvocationCase(
        string Operation,
        string SessionId,
        OperationInvocation Invocation);

    private sealed class Harness : IDisposable
    {
        private readonly TestProtectedPayload _protector = new();
        private readonly string _testRoot;

        public Harness(
            bool unsafeDocumentsPath = false,
            string? documentsPath = null)
        {
            if (unsafeDocumentsPath && documentsPath is not null)
            {
                throw new ArgumentException("Only one documents-path test mode is allowed.");
            }

            _testRoot = Path.Combine(
                Path.GetTempPath(),
                $"baxy-memory-handler-{Guid.NewGuid():N}");
            Directory.CreateDirectory(_testRoot);
            DocumentsPath = documentsPath ?? Path.Combine(_testRoot, "Documents");
            if (unsafeDocumentsPath)
            {
                File.WriteAllText(DocumentsPath, "blocked", new UTF8Encoding(false));
            }
            else if (documentsPath is null)
            {
                Directory.CreateDirectory(DocumentsPath);
            }

            Codec = new BoundProtectedJsonCodec(_protector);
            Store = new SpyMemoryStore();
            ExportWriter = new LocalMemoryExportWriter(DocumentsPath);
            Handlers = MemoryHandlers.Create(
                    Store,
                    Codec,
                    new FixedTimeProvider(Now),
                    ExportWriter)
                .ToDictionary(handler => handler.Definition.Name, StringComparer.Ordinal);
        }

        public string DocumentsPath { get; }

        public BoundProtectedJsonCodec Codec { get; }

        public SpyMemoryStore Store { get; }

        public LocalMemoryExportWriter ExportWriter { get; }

        public Dictionary<string, IOperationHandler> Handlers { get; }

        public InvocationCase Invocation(
            string operation,
            JsonObject payload,
            string? sessionId = null)
        {
            string session = sessionId ?? Guid.NewGuid().ToString("D");
            string requestId = Guid.NewGuid().ToString("D");
            string missionId = Guid.NewGuid().ToString("D");
            string invocationId = Guid.NewGuid().ToString("D");
            JsonElement arguments = Codec.SealArguments(
                operation,
                missionId,
                invocationId,
                session,
                payload);
            return new InvocationCase(
                operation,
                session,
                new OperationInvocation(requestId, missionId, invocationId, arguments));
        }

        public ValueTask<OperationOutcome> ExecuteAsync(InvocationCase request) =>
            Handlers[request.Operation].ExecuteAsync(request.Invocation, CancellationToken.None);

        public OpenedBoundProtectedJson OpenResult(
            InvocationCase request,
            OperationOutcome outcome) => Codec.OpenResult(
                outcome.Result!.Value,
                request.Operation,
                request.Invocation.MissionId,
                request.Invocation.InvocationId);

        public void Dispose()
        {
            _protector.Dispose();
            if (Directory.Exists(_testRoot))
            {
                Directory.Delete(_testRoot, recursive: true);
            }
        }
    }

    private sealed class SpyMemoryStore : IMemoryStore
    {
        private readonly List<MemoryRecord> _saved = [];
        private bool _enabled = true;

        public string RootDirectory => "memory-test";

        public List<MemoryConfigureRequest> ConfigureRequests { get; } = [];

        public List<string> BeginSessions { get; } = [];

        public List<MemoryStatusRequest> StatusRequests { get; } = [];

        public List<MemorySaveRequest> SaveRequests { get; } = [];

        public List<MemoryRecallRequest> RecallRequests { get; } = [];

        public List<MemoryListRequest> ListRequests { get; } = [];

        public List<MemoryCorrectRequest> CorrectRequests { get; } = [];

        public List<MemoryForgetRequest> ForgetRequests { get; } = [];

        public Exception? SaveException { get; set; }

        public MemoryRecallResult RecallResult { get; set; } = new([]);

        public MemoryListResult ListResult { get; set; } = new([]);

        public int TotalCalls => ConfigureRequests.Count
            + BeginSessions.Count
            + StatusRequests.Count
            + SaveRequests.Count
            + RecallRequests.Count
            + ListRequests.Count
            + CorrectRequests.Count
            + ForgetRequests.Count;

        public MemoryConfigurationResult Configure(MemoryConfigureRequest request)
        {
            ConfigureRequests.Add(request);
            _enabled = request.Enabled;
            return new MemoryConfigurationResult(request.Enabled, Replayed: false);
        }

        public MemoryBeginSessionResult BeginSession(MemoryBeginSessionRequest request)
        {
            BeginSessions.Add(request.SessionId);
            return new MemoryBeginSessionResult(0, Changed: false);
        }

        public MemoryStatusResult Status(MemoryStatusRequest request)
        {
            StatusRequests.Add(request);
            return new MemoryStatusResult(
                _enabled,
                Math.Max(3, _saved.Count),
                1,
                _saved.Count(record => record.Retention == MemoryRetention.Session),
                1,
                LocalMemoryStore.MaximumRecords);
        }

        public MemorySaveResult Save(MemorySaveRequest request)
        {
            if (SaveException is not null)
            {
                throw SaveException;
            }

            SaveRequests.Add(request);
            Guid id = Guid.NewGuid();
            string selector = request.Selector.ToUpperInvariant();
            _saved.Add(new MemoryRecord(
                id,
                1,
                selector,
                request.Label,
                request.Value,
                request.Kind,
                MemoryOrigin.Explicit,
                request.Sensitivity,
                request.Retention,
                request.Tags ?? [],
                request.CapturedAtUtc ?? DateTimeOffset.UtcNow,
                request.CapturedAtUtc ?? DateTimeOffset.UtcNow,
                request.ExpiresAtUtc,
                request.SourceMissionId,
                request.CapturedAtUtc ?? DateTimeOffset.UtcNow,
                request.SessionId));
            return new MemorySaveResult(id, 1, selector, false);
        }

        public MemoryRecallResult Recall(MemoryRecallRequest request)
        {
            RecallRequests.Add(request);
            if (_saved.Count > 0)
            {
                return new MemoryRecallResult(_saved.ToArray());
            }

            return RecallResult;
        }

        public MemoryListResult List(MemoryListRequest request)
        {
            ListRequests.Add(request);
            return ListResult;
        }

        public MemoryCorrectResult Correct(MemoryCorrectRequest request)
        {
            CorrectRequests.Add(request);
            MemoryRecord? source = _saved.FirstOrDefault(record =>
                    string.Equals(record.Selector, request.Selector, StringComparison.OrdinalIgnoreCase))
                ?? RecallResult.Records.FirstOrDefault(record =>
                    string.Equals(record.Selector, request.Selector, StringComparison.OrdinalIgnoreCase));
            Guid id = source?.Id ?? Guid.NewGuid();
            int revision = (source?.Revision ?? 7) + 1;
            string selector = source?.Selector ?? request.Selector.ToUpperInvariant();
            MemoryRecord updated = (source ?? Record(request.NewValue, request.SessionId)) with
            {
                Id = id,
                Revision = revision,
                Selector = selector,
                Value = request.NewValue,
            };
            _saved.Clear();
            _saved.Add(updated);
            return new MemoryCorrectResult(id, revision, selector, false);
        }

        public MemoryForgetResult Forget(MemoryForgetRequest request)
        {
            ForgetRequests.Add(request);
            int deleted = _saved.Count > 0 ? _saved.Count : 1;
            _saved.Clear();
            RecallResult = new([]);
            return new MemoryForgetResult(deleted, false);
        }

        private static MemoryRecord Record(string value, string? sessionId) => new(
            Guid.NewGuid(),
            1,
            "selector",
            "selector",
            value,
            MemoryKind.Fact,
            MemoryOrigin.Explicit,
            MemorySensitivity.Normal,
            MemoryRetention.Persistent,
            [],
            DateTimeOffset.UtcNow,
            DateTimeOffset.UtcNow,
            null,
            null,
            DateTimeOffset.UtcNow,
            sessionId);
    }

    private sealed class FixedTimeProvider(DateTimeOffset now) : TimeProvider
    {
        public override DateTimeOffset GetUtcNow() => now;
    }

    private sealed class TestProtectedPayload : IProtectedPayload, IDisposable
    {
        private const int NonceLength = 12;
        private const int TagLength = 16;
        private readonly byte[] _key = RandomNumberGenerator.GetBytes(32);

        public string ProtectionMode => "test-aes-gcm";

        public byte[] Seal(ReadOnlySpan<byte> plaintext, string purpose)
        {
            byte[] nonce = RandomNumberGenerator.GetBytes(NonceLength);
            byte[] ciphertext = new byte[plaintext.Length];
            byte[] tag = new byte[TagLength];
            using var aes = new AesGcm(_key, TagLength);
            aes.Encrypt(nonce, plaintext, ciphertext, tag, Encoding.UTF8.GetBytes(purpose));
            byte[] envelope = new byte[NonceLength + TagLength + ciphertext.Length];
            nonce.CopyTo(envelope, 0);
            tag.CopyTo(envelope, NonceLength);
            ciphertext.CopyTo(envelope, NonceLength + TagLength);
            return envelope;
        }

        public byte[] Open(ReadOnlySpan<byte> envelope, string purpose)
        {
            if (envelope.Length < NonceLength + TagLength)
            {
                throw new CryptographicException();
            }

            byte[] plaintext = new byte[envelope.Length - NonceLength - TagLength];
            using var aes = new AesGcm(_key, TagLength);
            aes.Decrypt(
                envelope[..NonceLength],
                envelope[(NonceLength + TagLength)..],
                envelope.Slice(NonceLength, TagLength),
                plaintext,
                Encoding.UTF8.GetBytes(purpose));
            return plaintext;
        }

        public byte[] SealUtf8(string plaintext, string purpose) =>
            Seal(Encoding.UTF8.GetBytes(plaintext), purpose);

        public string OpenUtf8(ReadOnlySpan<byte> envelope, string purpose) =>
            Encoding.UTF8.GetString(Open(envelope, purpose));

        public void Dispose() => CryptographicOperations.ZeroMemory(_key);
    }
}
