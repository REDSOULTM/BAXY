using System.Diagnostics;
using System.Text;
using System.Text.Json;
using Baxy.Contracts;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Notes;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class CoreNotesEndToEndTests
{
    [Test]
    [CancelAfter(30_000)]
    public async Task LegacyV1JournalIsPreservedAndCoreStartsWithAuthenticatedJournal()
    {
        string journalDirectory = Path.Combine(_dataRoot, "journal");
        Directory.CreateDirectory(journalDirectory);
        string journalPath = Path.Combine(journalDirectory, "missions.jsonl");
        const string legacyRecord =
            "{\"payload\":{\"missionId\":\"legacy\"},\"previousHash\":\"" +
            "0000000000000000000000000000000000000000000000000000000000000000" +
            "\",\"hash\":\"" +
            "1111111111111111111111111111111111111111111111111111111111111111" +
            "\"}\n";
        await File.WriteAllTextAsync(
            journalPath,
            legacyRecord,
            new UTF8Encoding(encoderShouldEmitUTF8Identifier: false));

        await using (CoreSession session = await CoreSession.StartAsync(_dataRoot))
        {
            Assert.That(session.Hello.Capabilities, Is.Not.Empty);
        }

        string[] archives = Directory.GetFiles(
            journalDirectory,
            "missions.legacy-v1-untrusted.*.jsonl");
        Assert.Multiple(() =>
        {
            Assert.That(archives, Has.Length.EqualTo(1));
            Assert.That(File.ReadAllText(archives.Single()), Is.EqualTo(legacyRecord));
            Assert.That(new FileInfo(journalPath).Length, Is.Zero);
            Assert.That(File.Exists(journalPath + ".anchor"), Is.True);
            Assert.That(
                File.Exists(Path.Combine(_dataRoot, "security", "journal-hmac.v2.key")),
                Is.True);
        });
    }

    [Test]
    [CancelAfter(30_000)]
    public async Task ReminderIsDurableResolvableAndPublishedEndToEnd()
    {
        string missionId = NewId();
        await using CoreSession session = await CoreSession.StartAsync(_dataRoot);
        string due = DateTimeOffset.UtcNow.AddDays(1).ToString("O");
        OperationResponse created = await session.SendAsync(Request(
            missionId, NewId(), "reminder.create",
            Parse($$"""{"dueUtc":"{{due}}","title":"Revisar corte"}""")));
        string reminderId = RequiredString(created.Result, "reminderId");
        OperationResponse resolved = await session.SendAsync(Request(
            missionId, NewId(), "reminder.resolve.exact",
            Parse("{\"title\":\"revisar corte\"}")));
        OperationResponse listed = await session.SendAsync(Request(
            missionId, NewId(), "reminder.list", Parse("{}")));

        Assert.Multiple(() =>
        {
            Assert.That(created.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(created.Verified, Is.True);
            Assert.That(RequiredString(resolved.Result, "reminderId"), Is.EqualTo(reminderId));
            Assert.That(listed.Result!.Value.GetProperty("count").GetInt32(), Is.EqualTo(1));
            Assert.That(
                listed.Result.Value.GetProperty("reminders")[0].GetProperty("reminderId").GetString(),
                Is.EqualTo(reminderId));
        });
    }

    [Test]
    [CancelAfter(30_000)]
    public async Task FilesystemSandboxUsesOpaqueIdsCasAndVerifiedCopiesEndToEnd()
    {
        string missionId = NewId();
        await using CoreSession session = await CoreSession.StartAsync(_dataRoot);
        OperationResponse written = await session.SendAsync(Request(
            missionId, NewId(), "filesystem.write.text",
            Parse("{\"relativePath\":\"entrada.txt\",\"text\":\"hola BAXY\"}")));
        OperationResponse listed = await session.SendAsync(Request(
            missionId, NewId(), "filesystem.list", Parse("{}")));
        string resourceId = listed.Result!.Value.GetProperty("entries")[0]
            .GetProperty("resourceId").GetString()!;
        OperationResponse read = await session.SendAsync(Request(
            missionId, NewId(), "filesystem.read.text",
            Parse($$"""{"resourceId":"{{resourceId}}"}""")));
        string hash = RequiredString(read.Result, "sha256");
        OperationResponse hashed = await session.SendAsync(Request(
            missionId, NewId(), "filesystem.hash",
            Parse($$"""{"resourceId":"{{resourceId}}"}""")));
        OperationResponse afterHash = await session.SendAsync(Request(
            NewId(), NewId(), "system.time", Parse("{}")));
        OperationResponse copied = await session.SendAsync(Request(
            missionId, NewId(), "filesystem.copy",
            Parse($$"""{"destinationRelativePath":"copias/salida.txt","expectedSha256":"{{hash}}","resourceId":"{{resourceId}}"}""")));
        string copiedId = RequiredString(copied.Result, "resourceId");
        OperationResponse backup = await session.SendAsync(Request(
            missionId, NewId(), "backup.create",
            Parse($$"""{"expectedSha256":"{{hash}}","resourceId":"{{copiedId}}"}""")));
        string backupId = RequiredString(backup.Result, "backupId");
        OperationResponse backupVerified = await session.SendAsync(Request(
            missionId, NewId(), "backup.verify",
            Parse($$"""{"backupId":"{{backupId}}"}""")));
        OperationResponse backupRestored = await session.SendAsync(Request(
            missionId, NewId(), "backup.restore",
            Parse($$"""{"backupId":"{{backupId}}","destinationRelativePath":"restored.txt"}""")));

        Assert.Multiple(() =>
        {
            Assert.That(written.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(written.Verified, Is.True);
            Assert.That(resourceId, Does.Match("^fs_[0-9a-f]{32}$"));
            Assert.That(RequiredString(read.Result, "text"), Is.EqualTo("hola BAXY"));
            Assert.That(hashed.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(hashed.Verified, Is.True);
            Assert.That(RequiredString(hashed.Result, "sha256"), Is.EqualTo(hash));
            Assert.That(afterHash.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(afterHash.Verified, Is.True);
            Assert.That(RequiredString(copied.Result, "sha256"), Is.EqualTo(hash));
            Assert.That(copied.Result!.Value.GetProperty("name").GetString(), Is.EqualTo("salida.txt"));
            Assert.That(backup.Result!.Value.GetProperty("verified").GetBoolean(), Is.True);
            Assert.That(RequiredString(backupVerified.Result, "sha256"), Is.EqualTo(hash));
            Assert.That(RequiredString(backupRestored.Result, "sha256"), Is.EqualTo(hash));
        });
    }

    [Test]
    [CancelAfter(30_000)]
    public async Task ExternalProviderFailuresDoNotTerminateTheJsonlLoop()
    {
        await using CoreSession session = await CoreSession.StartAsync(_dataRoot);

        OperationResponse steam = await session.SendAsync(Request(
            NewId(),
            NewId(),
            "game.install.prepare",
            Parse("""{"appId":"audit-missing-id"}""")));
        OperationResponse afterSteam = await session.SendAsync(Request(
            NewId(), NewId(), "system.time", Parse("{}")));

        OperationResponse package = await session.SendAsync(Request(
            NewId(),
            NewId(),
            "package.install.prepare",
            Parse("""{"packageId":"Microsoft.PowerToys"}""")));
        OperationResponse afterPackage = await session.SendAsync(Request(
            NewId(), NewId(), "system.time", Parse("{}")));

        OperationResponse bluetooth = await session.SendAsync(Request(
            NewId(), NewId(), "bluetooth.device.list", Parse("{}")));
        OperationResponse afterBluetooth = await session.SendAsync(Request(
            NewId(), NewId(), "system.time", Parse("{}")));

        Assert.Multiple(() =>
        {
            Assert.That(steam.Status, Is.EqualTo(OperationStatuses.Failed));
            Assert.That(steam.ErrorCode, Is.EqualTo("steam_app_id_invalid"));
            Assert.That(afterSteam.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(afterSteam.Verified, Is.True);

            Assert.That(
                package.Status,
                Is.AnyOf(OperationStatuses.Completed, OperationStatuses.Failed));
            Assert.That(afterPackage.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(afterPackage.Verified, Is.True);

            Assert.That(
                bluetooth.Status,
                Is.AnyOf(OperationStatuses.Completed, OperationStatuses.Failed));
            Assert.That(afterBluetooth.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(afterBluetooth.Verified, Is.True);
            Assert.That(session.HasExited, Is.False);
        });
    }

    [Test]
    [CancelAfter(30_000)]
    public async Task TaskLifecycleIsPublishedJournaledAndVerifiedEndToEnd()
    {
        string missionId = NewId();
        await using CoreSession session = await CoreSession.StartAsync(_dataRoot);
        OperationResponse created = await session.SendAsync(Request(
            missionId,
            NewId(),
            "task.create",
            Parse("{\"title\":\"Revisar BAXY\",\"details\":\"ejecutar corte\"}")));
        string taskId = RequiredString(created.Result, "taskId");
        long version = created.Result!.Value.GetProperty("version").GetInt64();

        OperationResponse resolved = await session.SendAsync(Request(
            missionId,
            NewId(),
            "task.resolve.exact",
            Parse("{\"title\":\"revisar baxy\"}")));
        OperationResponse completed = await session.SendAsync(Request(
            missionId,
            NewId(),
            "task.complete",
            Parse($$"""{"taskId":"{{taskId}}","expectedVersion":{{version}}}""")));
        long completedVersion = completed.Result!.Value.GetProperty("version").GetInt64();
        OperationResponse search = await session.SendAsync(Request(
            missionId,
            NewId(),
            "task.search",
            Parse("{\"query\":\"corte\",\"status\":\"completed\"}")));
        OperationResponse reopened = await session.SendAsync(Request(
            missionId,
            NewId(),
            "task.reopen",
            Parse($$"""{"taskId":"{{taskId}}","expectedVersion":{{completedVersion}}}""")));
        OperationResponse listed = await session.SendAsync(Request(
            missionId,
            NewId(),
            "task.list",
            Parse("{\"status\":\"open\"}")));

        Assert.Multiple(() =>
        {
            Assert.That(created.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(created.Verified, Is.True);
            Assert.That(RequiredString(resolved.Result, "taskId"), Is.EqualTo(taskId));
            Assert.That(resolved.Result!.Value.TryGetProperty("details", out _), Is.False);
            Assert.That(completed.Result!.Value.GetProperty("completed").GetBoolean(), Is.True);
            Assert.That(search.Result!.Value.GetProperty("count").GetInt32(), Is.EqualTo(1));
            Assert.That(reopened.Result!.Value.GetProperty("completed").GetBoolean(), Is.False);
            Assert.That(listed.Result!.Value.GetProperty("count").GetInt32(), Is.EqualTo(1));
            Assert.That(
                listed.Result.Value.GetProperty("tasks")[0].GetProperty("taskId").GetString(),
                Is.EqualTo(taskId));
        });
    }

    private string _dataRoot = null!;

    [SetUp]
    public void SetUp()
    {
        _dataRoot = PrivateDataRootTestSupport.NewPath("integration-core");
    }

    [TearDown]
    public void TearDown()
    {
        if (Directory.Exists(_dataRoot))
        {
            Directory.Delete(_dataRoot, recursive: true);
        }
    }

    [Test]
    [CancelAfter(30_000)]
    public async Task UpdateRequiresExactSnapshotAndVerifiesReopenedContent()
    {
        string missionId = NewId();
        await using CoreSession session = await CoreSession.StartAsync(_dataRoot);
        OperationResponse created = await session.SendAsync(Request(
            missionId,
            NewId(),
            "note.create",
            Parse("{\"title\":\"Borrador\",\"content\":\"uno\"}")));
        string noteId = RequiredString(created.Result, "noteId");
        long revision = created.Result!.Value.GetProperty("revision").GetInt64();

        OperationResponse updated = await session.SendAsync(Request(
            missionId,
            NewId(),
            "note.update",
            Parse($$"""{"noteId":"{{noteId}}","expectedTitle":"Borrador","expectedRevision":{{revision}},"title":"Final","content":"dos"}""")));
        OperationResponse read = await session.SendAsync(Request(
            missionId,
            NewId(),
            "note.read",
            Parse($$"""{"noteId":"{{noteId}}"}""")));
        OperationResponse search = await session.SendAsync(Request(
            missionId,
            NewId(),
            "note.search",
            Parse("{\"query\":\"dos\"}")));

        Assert.Multiple(() =>
        {
            Assert.That(updated.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(updated.Verified, Is.True);
            Assert.That(updated.Result!.Value.GetProperty("revision").GetInt64(), Is.EqualTo(revision + 1));
            Assert.That(RequiredString(read.Result, "title"), Is.EqualTo("Final"));
            Assert.That(RequiredString(read.Result, "content"), Is.EqualTo("dos"));
            Assert.That(search.Result!.Value.GetProperty("count").GetInt32(), Is.EqualTo(1));
            Assert.That(
                search.Result.Value.GetProperty("notes")[0].GetProperty("noteId").GetString(),
                Is.EqualTo(noteId));
        });
    }

    [Test]
    [CancelAfter(30_000)]
    public async Task TextRequestCreatesVerifiesReplaysAndRestoresDurableNote()
    {
        string missionId = NewId();
        string createInvocationId = NewId();
        JsonElement createArguments = Parse("{\"title\":\"Compras\",\"content\":\"leche, pan y café\"}");

        await using (CoreSession session = await CoreSession.StartAsync(_dataRoot))
        {
            OperationDescriptor[] expectedTools = ProductCatalog.ToolDescriptors
                .Select(static descriptor => ProductCatalog.CreateToolDescriptor(
                    new OperationDefinition(descriptor)))
                .ToArray();
            Assert.That(
                session.Hello.Capabilities.Select(ComparableDescriptor),
                Is.EqualTo(expectedTools.Select(ComparableDescriptor)));

            ProtocolError malformed = await session.SendMalformedAsync("{\"type\":");
            Assert.That(malformed.ErrorCode, Is.EqualTo("malformed_json"));
            Assert.That(session.HasExited, Is.False);

            OperationRequest create = Request(
                missionId,
                createInvocationId,
                "note.create",
                createArguments);
            OperationResponse created = await session.SendAsync(create);
            string noteId = RequiredString(created.Result, "noteId");

            Assert.Multiple(() =>
            {
                Assert.That(created.Status, Is.EqualTo(OperationStatuses.Completed));
                Assert.That(created.Verified, Is.True);
                Assert.That(created.Replayed, Is.False);
                Assert.That(Guid.TryParseExact(noteId, "D", out _), Is.True);
            });

            OperationResponse replay = await session.SendAsync(
                create with { RequestId = NewId() });
            Assert.Multiple(() =>
            {
                Assert.That(replay.Replayed, Is.True);
                Assert.That(RequiredString(replay.Result, "noteId"), Is.EqualTo(noteId));
                Assert.That(replay.RequestId, Is.Not.EqualTo(created.RequestId));
            });

            OperationResponse conflict = await session.SendAsync(
                create with
                {
                    RequestId = NewId(),
                    Arguments = Parse("{\"title\":\"Compras\",\"content\":\"contenido distinto\"}"),
                });
            Assert.Multiple(() =>
            {
                Assert.That(conflict.Status, Is.EqualTo(OperationStatuses.Rejected));
                Assert.That(conflict.ErrorCode, Is.EqualTo("idempotency_conflict"));
                Assert.That(conflict.Replayed, Is.False);
            });

            OperationResponse listed = await session.SendAsync(Request(
                missionId,
                NewId(),
                "note.list",
                Parse("{}")));
            Assert.That(listed.Result?.GetProperty("count").GetInt32(), Is.EqualTo(1));

            JsonElement idArguments = Parse($"{{\"noteId\":\"{noteId}\"}}");
            OperationResponse read = await session.SendAsync(Request(
                missionId,
                NewId(),
                "note.read",
                idArguments));
            Assert.That(RequiredString(read.Result, "content"), Is.EqualTo("leche, pan y café"));

            OperationResponse trashed = await session.SendAsync(Request(
                missionId,
                NewId(),
                "note.trash",
                idArguments));
            Assert.That(trashed.Result?.GetProperty("isTrashed").GetBoolean(), Is.True);

            OperationResponse activeAfterTrash = await session.SendAsync(Request(
                missionId,
                NewId(),
                "note.list",
                Parse("{}")));
            Assert.That(activeAfterTrash.Result?.GetProperty("count").GetInt32(), Is.Zero);

            OperationResponse restored = await session.SendAsync(Request(
                missionId,
                NewId(),
                "note.restore",
                idArguments));
            Assert.That(restored.Result?.GetProperty("isTrashed").GetBoolean(), Is.False);
        }

        await using (CoreSession restarted = await CoreSession.StartAsync(_dataRoot))
        {
            OperationResponse replayAfterRestart = await restarted.SendAsync(Request(
                missionId,
                createInvocationId,
                "note.create",
                createArguments));
            Assert.That(replayAfterRestart.Replayed, Is.True);

            OperationResponse listed = await restarted.SendAsync(Request(
                missionId,
                NewId(),
                "note.list",
                Parse("{}")));
            Assert.That(listed.Result?.GetProperty("count").GetInt32(), Is.EqualTo(1));
        }
    }

    [Test]
    [CancelAfter(30_000)]
    public async Task ExactTitleLifecycleIsStrictDurableAndReplayableAcrossRestart()
    {
        string missionId = NewId();
        string createInvocationId = NewId();
        string trashInvocationId = NewId();
        JsonElement createArguments = Parse(
            "{\"title\":\"Café Central\",\"content\":\"reservar una mesa\"}");
        JsonElement titleArguments = Parse("{\"title\":\"  CAFE\\u0301 CENTRAL  \"}");
        string noteId;

        await using (CoreSession session = await CoreSession.StartAsync(_dataRoot))
        {
            OperationResponse created = await session.SendAsync(Request(
                missionId,
                createInvocationId,
                "note.create",
                createArguments));
            noteId = RequiredString(created.Result, "noteId");

            OperationResponse read = await session.SendAsync(Request(
                missionId,
                NewId(),
                "note.read",
                titleArguments));
            OperationResponse neitherSelector = await session.SendAsync(Request(
                missionId,
                NewId(),
                "note.read",
                Parse("{}")));
            OperationResponse bothSelectors = await session.SendAsync(Request(
                missionId,
                NewId(),
                "note.read",
                Parse($"{{\"noteId\":\"{noteId}\",\"title\":\"Café Central\"}}")));
            OperationResponse unknownSelectorField = await session.SendAsync(Request(
                missionId,
                NewId(),
                "note.read",
                Parse("{\"title\":\"Café Central\",\"scope\":\"all\"}")));
            OperationResponse trashed = await session.SendAsync(Request(
                missionId,
                trashInvocationId,
                "note.trash",
                titleArguments));
            OperationResponse retriedAfterReachedTrash = await session.SendAsync(Request(
                missionId,
                NewId(),
                "note.trash",
                titleArguments));

            Assert.Multiple(() =>
            {
                Assert.That(read.Status, Is.EqualTo(OperationStatuses.Completed));
                Assert.That(RequiredString(read.Result, "noteId"), Is.EqualTo(noteId));
                Assert.That(RequiredString(read.Result, "content"), Is.EqualTo("reservar una mesa"));
                Assert.That(neitherSelector.ErrorCode, Is.EqualTo("invalid_arguments"));
                Assert.That(bothSelectors.ErrorCode, Is.EqualTo("invalid_arguments"));
                Assert.That(unknownSelectorField.ErrorCode, Is.EqualTo("invalid_arguments"));
                Assert.That(trashed.Status, Is.EqualTo(OperationStatuses.Completed));
                Assert.That(trashed.Result?.GetProperty("isTrashed").GetBoolean(), Is.True);
                Assert.That(retriedAfterReachedTrash.Status, Is.EqualTo(OperationStatuses.Completed));
                Assert.That(retriedAfterReachedTrash.Result?.GetProperty("revision").GetInt64(), Is.EqualTo(2));
            });
        }

        await using (CoreSession restarted = await CoreSession.StartAsync(_dataRoot))
        {
            OperationResponse replayedTrash = await restarted.SendAsync(Request(
                missionId,
                trashInvocationId,
                "note.trash",
                titleArguments));
            OperationResponse hiddenFromActiveRead = await restarted.SendAsync(Request(
                missionId,
                NewId(),
                "note.read",
                titleArguments));
            OperationResponse restored = await restarted.SendAsync(Request(
                missionId,
                NewId(),
                "note.restore",
                titleArguments));
            OperationResponse retriedAfterReachedRestore = await restarted.SendAsync(Request(
                missionId,
                NewId(),
                "note.restore",
                titleArguments));
            OperationResponse readAfterRestore = await restarted.SendAsync(Request(
                missionId,
                NewId(),
                "note.read",
                Parse("{\"title\":\"café central\"}")));

            Assert.Multiple(() =>
            {
                Assert.That(replayedTrash.Replayed, Is.True);
                Assert.That(replayedTrash.Result?.GetProperty("isTrashed").GetBoolean(), Is.True);
                Assert.That(hiddenFromActiveRead.Status, Is.EqualTo(OperationStatuses.Failed));
                Assert.That(hiddenFromActiveRead.ErrorCode, Is.EqualTo("note_not_found"));
                Assert.That(restored.Status, Is.EqualTo(OperationStatuses.Completed));
                Assert.That(restored.Result?.GetProperty("isTrashed").GetBoolean(), Is.False);
                Assert.That(retriedAfterReachedRestore.Status, Is.EqualTo(OperationStatuses.Completed));
                Assert.That(retriedAfterReachedRestore.Result?.GetProperty("revision").GetInt64(), Is.EqualTo(3));
                Assert.That(RequiredString(readAfterRestore.Result, "noteId"), Is.EqualTo(noteId));
                Assert.That(readAfterRestore.Result?.GetProperty("revision").GetInt64(), Is.EqualTo(3));
            });
        }
    }

    [Test]
    [CancelAfter(30_000)]
    public async Task AmbiguousExactTitleFailsWithoutMovingEitherNote()
    {
        string missionId = NewId();
        await using (CoreSession session = await CoreSession.StartAsync(_dataRoot))
        {
            OperationResponse first = await session.SendAsync(Request(
                missionId,
                NewId(),
                "note.create",
                Parse("{\"title\":\"Duplicada\",\"content\":\"primera\"}")));
            OperationResponse second = await session.SendAsync(Request(
                missionId,
                NewId(),
                "note.create",
                Parse("{\"title\":\"DUPLICADA\",\"content\":\"segunda\"}")));
            OperationResponse ambiguousTrash = await session.SendAsync(Request(
                missionId,
                NewId(),
                "note.trash",
                Parse("{\"title\":\"duplicada\"}")));
            OperationResponse firstRead = await session.SendAsync(Request(
                missionId,
                NewId(),
                "note.read",
                Parse($"{{\"noteId\":\"{RequiredString(first.Result, "noteId")}\"}}")));
            OperationResponse secondRead = await session.SendAsync(Request(
                missionId,
                NewId(),
                "note.read",
                Parse($"{{\"noteId\":\"{RequiredString(second.Result, "noteId")}\"}}")));
            OperationResponse active = await session.SendAsync(Request(
                missionId,
                NewId(),
                "note.list",
                Parse("{}")));
            OperationResponse trashed = await session.SendAsync(Request(
                missionId,
                NewId(),
                "note.list",
                Parse("{\"scope\":\"trashed\"}")));

            Assert.Multiple(() =>
            {
                Assert.That(ambiguousTrash.Status, Is.EqualTo(OperationStatuses.Failed));
                Assert.That(ambiguousTrash.ErrorCode, Is.EqualTo("note_ambiguous"));
                Assert.That(ambiguousTrash.Message, Does.Contain("note_ambiguous"));
                Assert.That(ambiguousTrash.Result, Is.Not.Null);
                JsonElement[] candidates = ambiguousTrash.Result!.Value
                    .GetProperty("candidates")
                    .EnumerateArray()
                    .ToArray();
                Assert.That(candidates, Has.Length.EqualTo(2));
                Assert.That(
                    candidates.Select(static candidate => candidate.GetProperty("noteId").GetString()),
                    Is.EquivalentTo(new[]
                    {
                        RequiredString(first.Result, "noteId"),
                        RequiredString(second.Result, "noteId"),
                    }));
                Assert.That(candidates, Has.All.Matches<JsonElement>(static candidate =>
                    candidate.GetProperty("revision").GetInt64() == 1
                    && !candidate.GetProperty("isTrashed").GetBoolean()
                    && Encoding.UTF8.GetByteCount(candidate.GetProperty("contentPreview").GetString()!)
                        <= LocalNoteStore.MaximumContentPreviewUtf8Bytes));
                Assert.That(firstRead.Result?.GetProperty("isTrashed").GetBoolean(), Is.False);
                Assert.That(secondRead.Result?.GetProperty("isTrashed").GetBoolean(), Is.False);
                Assert.That(firstRead.Result?.GetProperty("revision").GetInt64(), Is.EqualTo(1));
                Assert.That(secondRead.Result?.GetProperty("revision").GetInt64(), Is.EqualTo(1));
                Assert.That(active.Result?.GetProperty("count").GetInt32(), Is.EqualTo(2));
                Assert.That(trashed.Result?.GetProperty("count").GetInt32(), Is.Zero);
            });
        }
    }

    [Test]
    [CancelAfter(30_000)]
    public async Task SelectedSnapshotMutatesOnlyItsUuidReconcilesAndFailsClosedWhenStale()
    {
        string missionId = NewId();
        await using CoreSession session = await CoreSession.StartAsync(_dataRoot);
        OperationResponse first = await session.SendAsync(Request(
            missionId,
            NewId(),
            "note.create",
            Parse("{\"title\":\"Elegida\",\"content\":\"primera\"}")));
        OperationResponse second = await session.SendAsync(Request(
            missionId,
            NewId(),
            "note.create",
            Parse("{\"title\":\"ELEGIDA\",\"content\":\"segunda\"}")));
        OperationResponse ambiguous = await session.SendAsync(Request(
            missionId,
            NewId(),
            "note.trash",
            Parse("{\"title\":\"elegida\"}")));
        JsonElement candidate = ambiguous.Result!.Value
            .GetProperty("candidates")
            .EnumerateArray()
            .First();
        string selectedId = candidate.GetProperty("noteId").GetString()!;
        string selectedTitle = "elegida";
        long selectedRevision = candidate.GetProperty("revision").GetInt64();
        bool selectedWasTrashed = candidate.GetProperty("isTrashed").GetBoolean();
        string selectedArgumentsJson = JsonSerializer.Serialize(new
        {
            noteId = selectedId,
            expectedTitle = selectedTitle,
            expectedRevision = selectedRevision,
            expectedIsTrashed = selectedWasTrashed,
        });
        JsonElement selectedArguments = Parse(selectedArgumentsJson);
        string selectedInvocationId = NewId();

        OperationResponse trashed = await session.SendAsync(Request(
            missionId,
            selectedInvocationId,
            "note.trash",
            selectedArguments));
        OperationResponse journalReplay = await session.SendAsync(Request(
            missionId,
            selectedInvocationId,
            "note.trash",
            selectedArguments));
        OperationResponse reachedReplay = await session.SendAsync(Request(
            missionId,
            NewId(),
            "note.trash",
            selectedArguments));
        JsonElement trashedReadArguments = Parse(JsonSerializer.Serialize(new
        {
            noteId = selectedId,
            expectedTitle = selectedTitle,
            expectedRevision = selectedRevision + 1,
            expectedIsTrashed = true,
        }));
        OperationResponse selectedReadWhileTrashed = await session.SendAsync(Request(
            missionId,
            NewId(),
            "note.read",
            trashedReadArguments));
        OperationResponse restoredOutsideSnapshot = await session.SendAsync(Request(
            missionId,
            NewId(),
            "note.restore",
            Parse($"{{\"noteId\":\"{selectedId}\"}}")));
        OperationResponse stale = await session.SendAsync(Request(
            missionId,
            NewId(),
            "note.trash",
            selectedArguments));
        OperationResponse selectedRead = await session.SendAsync(Request(
            missionId,
            NewId(),
            "note.read",
            Parse($"{{\"noteId\":\"{selectedId}\"}}")));
        string otherId = string.Equals(selectedId, RequiredString(first.Result, "noteId"), StringComparison.Ordinal)
            ? RequiredString(second.Result, "noteId")
            : RequiredString(first.Result, "noteId");
        OperationResponse otherRead = await session.SendAsync(Request(
            missionId,
            NewId(),
            "note.read",
            Parse($"{{\"noteId\":\"{otherId}\"}}")));
        OperationResponse partialSnapshot = await session.SendAsync(Request(
            missionId,
            NewId(),
            "note.read",
            Parse($"{{\"noteId\":\"{selectedId}\",\"expectedTitle\":{JsonSerializer.Serialize(selectedTitle)}}}")));

        Assert.Multiple(() =>
        {
            Assert.That(trashed.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(trashed.Result?.GetProperty("revision").GetInt64(), Is.EqualTo(selectedRevision + 1));
            Assert.That(trashed.Result?.GetProperty("isTrashed").GetBoolean(), Is.True);
            Assert.That(journalReplay.Replayed, Is.True);
            Assert.That(reachedReplay.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(reachedReplay.Result?.GetProperty("revision").GetInt64(), Is.EqualTo(selectedRevision + 1));
            Assert.That(selectedReadWhileTrashed.Status, Is.EqualTo(OperationStatuses.Failed));
            Assert.That(selectedReadWhileTrashed.ErrorCode, Is.EqualTo("note_selection_stale"));
            Assert.That(selectedReadWhileTrashed.Result, Is.Null);
            Assert.That(restoredOutsideSnapshot.Result?.GetProperty("revision").GetInt64(),
                Is.EqualTo(selectedRevision + 2));
            Assert.That(stale.Status, Is.EqualTo(OperationStatuses.Failed));
            Assert.That(stale.ErrorCode, Is.EqualTo("note_selection_stale"));
            Assert.That(stale.Message, Does.Contain("note_selection_stale"));
            Assert.That(selectedRead.Result?.GetProperty("revision").GetInt64(),
                Is.EqualTo(selectedRevision + 2));
            Assert.That(selectedRead.Result?.GetProperty("isTrashed").GetBoolean(), Is.False);
            Assert.That(otherRead.Result?.GetProperty("revision").GetInt64(), Is.EqualTo(1));
            Assert.That(otherRead.Result?.GetProperty("isTrashed").GetBoolean(), Is.False);
            Assert.That(partialSnapshot.ErrorCode, Is.EqualTo("invalid_arguments"));
        });
    }

    [Test]
    [CancelAfter(30_000)]
    public async Task ProtocolBoundaryRejectsUnknownCaseAndExtraArgumentsThenRecovers()
    {
        string missionId = NewId();
        await using CoreSession session = await CoreSession.StartAsync(_dataRoot);

        OperationResponse unknown = await session.SendAsync(Request(
            missionId,
            NewId(),
            "note.missing",
            Parse("{}")));
        Assert.Multiple(() =>
        {
            Assert.That(unknown.Status, Is.EqualTo(OperationStatuses.Rejected));
            Assert.That(unknown.ErrorCode, Is.EqualTo("unknown_operation"));
        });

        OperationRequest wrongCase = Request(
            missionId,
            NewId(),
            "note.create",
            Parse("{\"title\":\"No creada\",\"content\":\"case\"}"));
        string validLine = Encoding.UTF8.GetString(ProtocolJson.SerializeToUtf8Bytes(wrongCase));
        string wrongCaseLine = validLine.Replace(
            "\"operation\":\"note.create\"",
            "\"operation\":\"NOTE.CREATE\"",
            StringComparison.Ordinal);
        Assert.That(wrongCaseLine, Is.Not.EqualTo(validLine));
        ProtocolError wrongCaseError = await session.SendMalformedAsync(wrongCaseLine);
        Assert.That(wrongCaseError.ErrorCode, Is.EqualTo("malformed_json"));

        OperationResponse extraArgument = await session.SendAsync(Request(
            missionId,
            NewId(),
            "note.create",
            Parse("{\"title\":\"No creada\",\"content\":\"extra\",\"path\":\"..\\\\outside\"}")));
        Assert.Multiple(() =>
        {
            Assert.That(extraArgument.Status, Is.EqualTo(OperationStatuses.Failed));
            Assert.That(extraArgument.ErrorCode, Is.EqualTo("invalid_arguments"));
        });

        OperationResponse wrongArgumentCase = await session.SendAsync(Request(
            missionId,
            NewId(),
            "note.create",
            Parse("{\"Title\":\"No creada\",\"content\":\"case\"}")));
        Assert.That(wrongArgumentCase.ErrorCode, Is.EqualTo("invalid_arguments"));

        OperationResponse extraStatusArgument = await session.SendAsync(Request(
            missionId,
            NewId(),
            "app.status",
            Parse("{\"unexpected\":true}")));
        Assert.That(extraStatusArgument.ErrorCode, Is.EqualTo("invalid_arguments"));

        ProtocolError oversized = await session.SendMalformedAsync(new string('x', (1024 * 1024) + 1));
        Assert.That(oversized.ErrorCode, Is.EqualTo("invalid_message_size"));

        OperationResponse status = await session.SendAsync(Request(
            missionId,
            NewId(),
            "app.status",
            Parse("{}")));
        OperationResponse listed = await session.SendAsync(Request(
            missionId,
            NewId(),
            "note.list",
            Parse("{}")));
        Assert.Multiple(() =>
        {
            Assert.That(session.HasExited, Is.False);
            Assert.That(status.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(status.Verified, Is.True);
            Assert.That(
                status.Result?.GetProperty("operations").EnumerateArray()
                    .Select(static item => item.GetString()),
                Is.EqualTo(ProductCatalog.OperationNames));
            // 190 herramientas públicas tras las 21 operaciones de C03 (plan post-goal 2026-09-20, grupo B);
            // 193 con weather.current, web.news.headlines y package.uninstall (auditoría semántica REOPEN1993, grupos W, N y G).
            Assert.That(session.Hello.Capabilities, Has.Count.EqualTo(193));
            Assert.That(
                session.Hello.Capabilities.Select(static capability => capability.Name),
                Does.Not.Contain("app.status"));
            Assert.That(listed.Result?.GetProperty("count").GetInt32(), Is.Zero);
        });
    }

    [Test]
    [CancelAfter(60_000)]
    public async Task LargeNotesListIsBoundedPaginatedAndLeavesProtocolResponsive()
    {
        const int noteCount = 24;
        const int pageSize = 7;
        string maximumContent = new('x', LocalNoteStore.MaximumContentUtf8Bytes);
        string longTitleSuffix = new('t', 440);
        var store = new LocalNoteStore(Path.Combine(_dataRoot, "notes-store"));
        for (int index = 0; index < noteCount; index++)
        {
            _ = store.Create($"Nota {index:D2} {longTitleSuffix}", maximumContent);
        }

        string missionId = NewId();
        await using CoreSession session = await CoreSession.StartAsync(_dataRoot);

        OperationResponse defaultPage = await session.SendAsync(Request(
            missionId,
            NewId(),
            "note.list",
            Parse("{}")));
        int defaultResponseBytes = session.LastResponseUtf8ByteCount;
        JsonElement defaultResult = defaultPage.Result!.Value;
        JsonElement defaultNotes = defaultResult.GetProperty("notes");

        Assert.Multiple(() =>
        {
            Assert.That(defaultPage.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(defaultResult.GetProperty("count").GetInt32(), Is.EqualTo(noteCount));
            Assert.That(defaultResult.GetProperty("totalCount").GetInt32(), Is.EqualTo(noteCount));
            Assert.That(defaultResult.GetProperty("limit").GetInt32(), Is.EqualTo(50));
            Assert.That(defaultResult.GetProperty("offset").GetInt32(), Is.Zero);
            Assert.That(defaultResult.GetProperty("nextOffset").ValueKind, Is.EqualTo(JsonValueKind.Null));
            Assert.That(defaultNotes.GetArrayLength(), Is.EqualTo(noteCount));
            Assert.That(
                defaultNotes.EnumerateArray().All(static note => !note.TryGetProperty("content", out _)),
                Is.True);
            Assert.That(defaultResponseBytes, Is.LessThan(1024 * 1024));
        });

        OperationResponse middlePage = await session.SendAsync(Request(
            missionId,
            NewId(),
            "note.list",
            Parse($"{{\"scope\":\"active\",\"limit\":{pageSize},\"offset\":{pageSize}}}")));
        JsonElement middleResult = middlePage.Result!.Value;
        Assert.Multiple(() =>
        {
            Assert.That(middleResult.GetProperty("count").GetInt32(), Is.EqualTo(pageSize));
            Assert.That(middleResult.GetProperty("totalCount").GetInt32(), Is.EqualTo(noteCount));
            Assert.That(middleResult.GetProperty("limit").GetInt32(), Is.EqualTo(pageSize));
            Assert.That(middleResult.GetProperty("offset").GetInt32(), Is.EqualTo(pageSize));
            Assert.That(middleResult.GetProperty("nextOffset").GetInt32(), Is.EqualTo(pageSize * 2));
        });

        OperationResponse excessiveLimit = await session.SendAsync(Request(
            missionId,
            NewId(),
            "note.list",
            Parse("{\"limit\":101}")));
        OperationResponse negativeOffset = await session.SendAsync(Request(
            missionId,
            NewId(),
            "note.list",
            Parse("{\"offset\":-1}")));
        OperationResponse unknownArgument = await session.SendAsync(Request(
            missionId,
            NewId(),
            "note.list",
            Parse("{\"limit\":7,\"continuation\":\"unsafe\"}")));
        OperationResponse status = await session.SendAsync(Request(
            missionId,
            NewId(),
            "app.status",
            Parse("{}")));

        Assert.Multiple(() =>
        {
            Assert.That(excessiveLimit.Status, Is.EqualTo(OperationStatuses.Failed));
            Assert.That(excessiveLimit.ErrorCode, Is.EqualTo("invalid_arguments"));
            Assert.That(negativeOffset.Status, Is.EqualTo(OperationStatuses.Failed));
            Assert.That(negativeOffset.ErrorCode, Is.EqualTo("invalid_arguments"));
            Assert.That(unknownArgument.Status, Is.EqualTo(OperationStatuses.Failed));
            Assert.That(unknownArgument.ErrorCode, Is.EqualTo("invalid_arguments"));
            Assert.That(status.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(status.Verified, Is.True);
            Assert.That(session.HasExited, Is.False);
        });
    }

    [Test]
    [CancelAfter(30_000)]
    public async Task TruncatedCommittedCompletionFailsClosedWithoutRepairingJournal()
    {
        string missionId = NewId();
        string invocationId = NewId();
        JsonElement arguments = Parse("{\"title\":\"Resiliente\",\"content\":\"una sola copia\"}");

        await using (CoreSession session = await CoreSession.StartAsync(_dataRoot))
        {
            OperationResponse created = await session.SendAsync(Request(
                missionId,
                invocationId,
                "note.create",
                arguments));
            Assert.That(created.Verified, Is.True);
        }

        await TruncateLastJournalRecordAsync(_dataRoot);
        string journalPath = Path.Combine(_dataRoot, "journal", "missions.jsonl");
        byte[] truncated = await File.ReadAllBytesAsync(journalPath);

        (int exitCode, string stdout, string stderr) =
            await CoreSession.RunUntilExitAsync(_dataRoot);
        byte[] afterRejectedStart = await File.ReadAllBytesAsync(journalPath);

        Assert.Multiple(() =>
        {
            Assert.That(exitCode, Is.EqualTo(74));
            Assert.That(stdout, Is.Empty);
            Assert.That(
                stderr,
                Does.Contain("mission journal failed integrity validation"));
            Assert.That(afterRejectedStart, Is.EqualTo(truncated));
        });
    }

    private static async Task TruncateLastJournalRecordAsync(string dataRoot)
    {
        string path = Path.Combine(dataRoot, "journal", "missions.jsonl");
        byte[] complete = await File.ReadAllBytesAsync(path);
        Assert.That(complete, Is.Not.Empty);
        Assert.That(complete[^1], Is.EqualTo((byte)'\n'));
        int recordStart = Array.LastIndexOf(complete, (byte)'\n', complete.Length - 2) + 1;
        Assert.That(recordStart, Is.GreaterThan(0));
        int partialLength = recordStart + ((complete.Length - recordStart) / 2);
        await File.WriteAllBytesAsync(path, complete[..partialLength]);
    }

    private static OperationRequest Request(
        string missionId,
        string invocationId,
        string operation,
        JsonElement arguments) =>
        new(
            ProtocolTypes.OperationRequest,
            NewId(),
            missionId,
            invocationId,
            operation,
            arguments);

    private static string RequiredString(JsonElement? element, string propertyName)
    {
        Assert.That(element, Is.Not.Null);
        string? value = element!.Value.GetProperty(propertyName).GetString();
        Assert.That(value, Is.Not.Null.And.Not.Empty);
        return value!;
    }

    private static JsonElement Parse(string json) =>
        JsonDocument.Parse(json).RootElement.Clone();

    private static (string Name, string ArgumentsSchema, string Risk, string Verifier, string Description)
        ComparableDescriptor(OperationDescriptor descriptor) =>
        (
            descriptor.Name,
            descriptor.ArgumentsSchema.GetRawText(),
            descriptor.Risk,
            descriptor.VerifierContractId,
            descriptor.Description);

    private static string NewId() => Guid.NewGuid().ToString("D");

    private sealed class CoreSession : IAsyncDisposable
    {
        private readonly Process _process;
        private readonly Task<string> _stderr;

        private CoreSession(Process process, Task<string> stderr, ProtocolHello hello)
        {
            _process = process;
            _stderr = stderr;
            Hello = hello;
        }

        public ProtocolHello Hello { get; }

        public bool HasExited => _process.HasExited;

        public int LastResponseUtf8ByteCount { get; private set; }

        public static async Task<CoreSession> StartAsync(string dataRoot)
        {
            var process = new Process { StartInfo = CreateStartInfo(dataRoot) };
            Assert.That(process.Start(), Is.True);
            Task<string> stderr = process.StandardError.ReadToEndAsync();
            try
            {
                string helloLine = await ReadRequiredLineAsync(process).ConfigureAwait(false);
                ProtocolHello hello = ProtocolJson.DeserializeHello(Encoding.UTF8.GetBytes(helloLine));
                return new CoreSession(process, stderr, hello);
            }
            catch
            {
                if (!process.HasExited)
                {
                    process.Kill(entireProcessTree: true);
                }

                process.Dispose();
                throw;
            }
        }

        public static async Task<(int ExitCode, string Stdout, string Stderr)> RunUntilExitAsync(
            string dataRoot)
        {
            using var process = new Process { StartInfo = CreateStartInfo(dataRoot) };
            Assert.That(process.Start(), Is.True);
            process.StandardInput.Close();
            Task<string> stdout = process.StandardOutput.ReadToEndAsync();
            Task<string> stderr = process.StandardError.ReadToEndAsync();
            try
            {
                await process.WaitForExitAsync()
                    .WaitAsync(TimeSpan.FromSeconds(10))
                    .ConfigureAwait(false);
            }
            catch (TimeoutException)
            {
                process.Kill(entireProcessTree: true);
                await process.WaitForExitAsync().ConfigureAwait(false);
                throw;
            }

            return (
                process.ExitCode,
                await stdout.ConfigureAwait(false),
                await stderr.ConfigureAwait(false));
        }

        private static ProcessStartInfo CreateStartInfo(string dataRoot)
        {
            string corePath = Path.Combine(AppContext.BaseDirectory, "baxy-core.dll");
            Assert.That(File.Exists(corePath), Is.True, $"Core binary missing at {corePath}");

            var startInfo = new ProcessStartInfo
            {
                // VSTest provides the muxer that launched this test host. Reuse
                // it instead of resolving a different SDK from the machine PATH.
                FileName = Environment.GetEnvironmentVariable("DOTNET_HOST_PATH")
                    ?? "dotnet",
                UseShellExecute = false,
                RedirectStandardInput = true,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                CreateNoWindow = true,
                StandardInputEncoding = new UTF8Encoding(false, true),
                StandardOutputEncoding = new UTF8Encoding(false, true),
                StandardErrorEncoding = new UTF8Encoding(false, true),
            };
            startInfo.ArgumentList.Add(corePath);
            startInfo.Environment["BAXY_DATA_DIR"] = dataRoot;
            startInfo.Environment["DOTNET_NOLOGO"] = "1";
            return startInfo;
        }

        public async Task<OperationResponse> SendAsync(OperationRequest request)
        {
            byte[] payload = ProtocolJson.SerializeToUtf8Bytes(request);
            await _process.StandardInput.WriteLineAsync(Encoding.UTF8.GetString(payload)).ConfigureAwait(false);
            await _process.StandardInput.FlushAsync().ConfigureAwait(false);

            string line = await ReadRequiredLineAsync(_process).ConfigureAwait(false);
            LastResponseUtf8ByteCount = Encoding.UTF8.GetByteCount(line);
            using JsonDocument document = JsonDocument.Parse(line);
            string? type = document.RootElement.GetProperty("type").GetString();
            Assert.That(type, Is.EqualTo(ProtocolTypes.OperationResponse), line);
            OperationResponse response = ProtocolJson.DeserializeResponse(Encoding.UTF8.GetBytes(line));
            Assert.Multiple(() =>
            {
                Assert.That(response.RequestId, Is.EqualTo(request.RequestId));
                Assert.That(response.MissionId, Is.EqualTo(request.MissionId));
                Assert.That(response.InvocationId, Is.EqualTo(request.InvocationId));
            });
            return response;
        }

        public async Task<ProtocolError> SendMalformedAsync(string line)
        {
            await _process.StandardInput.WriteLineAsync(line).ConfigureAwait(false);
            await _process.StandardInput.FlushAsync().ConfigureAwait(false);
            string response = await ReadRequiredLineAsync(_process).ConfigureAwait(false);
            return ProtocolJson.DeserializeError(Encoding.UTF8.GetBytes(response));
        }

        public async ValueTask DisposeAsync()
        {
            if (!_process.HasExited)
            {
                _process.StandardInput.Close();
                try
                {
                    await _process.WaitForExitAsync().WaitAsync(TimeSpan.FromSeconds(5)).ConfigureAwait(false);
                }
                catch (TimeoutException)
                {
                    _process.Kill(entireProcessTree: true);
                    await _process.WaitForExitAsync().ConfigureAwait(false);
                }
            }

            string stderr = await _stderr.ConfigureAwait(false);
            int exitCode = _process.ExitCode;
            _process.Dispose();
            Assert.That(exitCode, Is.Zero, stderr);
        }

        private static async Task<string> ReadRequiredLineAsync(Process process)
        {
            string? line = await process.StandardOutput
                .ReadLineAsync()
                .WaitAsync(TimeSpan.FromSeconds(10))
                .ConfigureAwait(false);
            if (line is null)
            {
                throw new EndOfStreamException("BAXY core closed stdout unexpectedly.");
            }

            return line;
        }
    }
}
