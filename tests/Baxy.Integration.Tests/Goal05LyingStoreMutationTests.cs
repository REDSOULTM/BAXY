using System.Globalization;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Clipboard;
using Baxy.Providers.Windows.Filesystem;
using Baxy.Providers.Windows.Memory;
using Baxy.Providers.Windows.Notes;
using Baxy.Providers.Windows.Routines;
using Baxy.Providers.Windows.Tasks;
using Baxy.Security.Windows;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class Goal05LyingStoreMutationTests
{
    private static readonly Guid FakeId = Guid.Parse("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee");
    private static readonly string FakeHashA =
        new string('a', 64);
    private static readonly string FakeHashB =
        new string('b', 64);

    [TestCase("note.create", """{"title":"Goal05","content":"x"}""")]
    [TestCase("note.update")]
    [TestCase("note.trash")]
    [TestCase("note.restore")]
    public async Task LyingNoteStoreCannotCompleteMutations(string operation, string? json = null)
    {
        var handler = NoteHandler(operation, new LyingNoteStore());
        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation(json ?? NoteJson(operation)),
            CancellationToken.None);
        AssertFailedClosed(outcome, operation);
    }

    [TestCase("task.create", """{"title":"Goal05 task"}""")]
    [TestCase("task.complete")]
    [TestCase("task.reopen")]
    [TestCase("task.update")]
    [TestCase("task.delete")]
    [TestCase("task.restore")]
    public async Task LyingTaskStoreCannotCompleteMutations(string operation, string? json = null)
    {
        IOperationHandler handler = TaskHandlers.Create(new LyingTaskStore())
            .Single(candidate => candidate.Definition.Name == operation);
        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation(json ?? TaskJson(operation)),
            CancellationToken.None);
        AssertFailedClosed(outcome, operation);
    }

    [TestCase("reminder.create")]
    [TestCase("reminder.delete")]
    [TestCase("reminder.restore")]
    [TestCase("notification.dismiss")]
    public async Task LyingReminderStoreCannotCompleteMutations(string operation)
    {
        IOperationHandler handler = ReminderHandlers.Create(new LyingTaskStore(), TimeProvider.System)
            .Single(candidate => candidate.Definition.Name == operation);
        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation(ReminderJson(operation)),
            CancellationToken.None);
        AssertFailedClosed(outcome, operation);
    }

    [TestCase("routine.phrase.create")]
    [TestCase("routine.set.enabled")]
    [TestCase("routine.delete")]
    [TestCase("routine.restore")]
    public async Task LyingRoutineStoreCannotCompleteMutations(string operation)
    {
        IOperationHandler handler = RoutineHandlers.Create(new LyingRoutineStore())
            .Single(candidate => candidate.Definition.Name == operation);
        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation(RoutineJson(operation)),
            CancellationToken.None);
        AssertFailedClosed(outcome, operation);
    }

    [Test]
    public async Task LyingFilesystemProviderCannotCompleteWrite()
    {
        IOperationHandler handler = FilesystemHandlers.Create(new LyingFilesystemProvider())
            .Single(candidate => candidate.Definition.Name == "filesystem.write.text");
        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation("""{"relativePath":"goal05.txt","text":"x"}"""),
            CancellationToken.None);
        AssertFailedClosed(outcome, "filesystem.write.text");
    }

    [Test]
    public async Task LyingClipboardProviderCannotCompleteWrite()
    {
        var handler = new ClipboardWriteTextHandler(new LyingClipboardProvider());
        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation("""{"text":"goal05"}"""),
            CancellationToken.None);
        AssertFailedClosed(outcome, "clipboard.write.text");
    }

    [TestCase("memory.save")]
    [TestCase("memory.sensitive.save")]
    [TestCase("memory.enable")]
    [TestCase("memory.disable")]
    [TestCase("memory.forget")]
    [TestCase("memory.session.clear")]
    [TestCase("memory.correct")]
    public async Task LyingMemoryStoreCannotCompleteMutations(string operation)
    {
        string root = PrivateDataRootTestSupport.NewPath("goal05-lying-memory");
        Directory.CreateDirectory(root);
        try
        {
            var payload = new WindowsProtectedPayload(
                Path.Combine(root, "security", "private-payload.v1.key"));
            var codec = new BoundProtectedJsonCodec(payload);
            var store = new LyingMemoryStore();
            IOperationHandler handler = MemoryHandlers.Create(
                    store,
                    codec,
                    TimeProvider.System,
                    new LyingMemoryExportWriter())
                .Single(candidate => candidate.Definition.Name == operation);
            string missionId = Guid.NewGuid().ToString("D");
            string invocationId = Guid.NewGuid().ToString("D");
            string sessionId = Guid.NewGuid().ToString("D");
            JsonElement arguments = codec.SealArguments(
                operation,
                missionId,
                invocationId,
                sessionId,
                MemoryPayload(operation));
            OperationOutcome outcome = await handler.ExecuteAsync(
                new OperationInvocation(
                    Guid.NewGuid().ToString("D"),
                    missionId,
                    invocationId,
                    arguments),
                CancellationToken.None);
            AssertFailedClosed(outcome, operation);
        }
        finally
        {
            if (Directory.Exists(root))
            {
                Directory.Delete(root, recursive: true);
            }
        }
    }

    [Test]
    public async Task LyingMemoryExportCannotComplete()
    {
        string root = PrivateDataRootTestSupport.NewPath("goal05-lying-export");
        Directory.CreateDirectory(root);
        try
        {
            var payload = new WindowsProtectedPayload(
                Path.Combine(root, "security", "private-payload.v1.key"));
            var codec = new BoundProtectedJsonCodec(payload);
            IOperationHandler handler = MemoryHandlers.Create(
                    new LyingMemoryStore(),
                    codec,
                    TimeProvider.System,
                    new LyingMemoryExportWriter())
                .Single(candidate => candidate.Definition.Name == "memory.export");
            string missionId = Guid.NewGuid().ToString("D");
            string invocationId = Guid.NewGuid().ToString("D");
            string sessionId = Guid.NewGuid().ToString("D");
            JsonElement arguments = codec.SealArguments(
                "memory.export",
                missionId,
                invocationId,
                sessionId,
                new JsonObject
                {
                    ["version"] = 1,
                    ["destination"] = "documents",
                    ["includeSecrets"] = false,
                });
            OperationOutcome outcome = await handler.ExecuteAsync(
                new OperationInvocation(
                    Guid.NewGuid().ToString("D"),
                    missionId,
                    invocationId,
                    arguments),
                CancellationToken.None);
            AssertFailedClosed(outcome, "memory.export");
        }
        finally
        {
            if (Directory.Exists(root))
            {
                Directory.Delete(root, recursive: true);
            }
        }
    }

    [Test]
    public void EveryIsolatedObservedMutationHasALyingExecutorTest()
    {
        string[] covered =
        [
            "note.create", "note.update", "note.trash", "note.restore",
            "task.create", "task.complete", "task.reopen", "task.update",
            "task.delete", "task.restore",
            "reminder.create", "reminder.delete", "reminder.restore",
            "notification.dismiss",
            "routine.phrase.create", "routine.set.enabled", "routine.delete",
            "routine.restore",
            "memory.save", "memory.sensitive.save", "memory.enable", "memory.disable",
            "memory.forget", "memory.session.clear", "memory.correct", "memory.export",
            "filesystem.write.text",
            "clipboard.write.text",
        ];
        string[] observedMutations = Goal05CatalogObservation.ClassifyCatalog()
            .Where(row => row.Verdict == "observed"
                && row.Surface == "isolated_store"
                && row.Risk is not "read_only")
            .Select(row => row.Operation)
            .ToArray();
        string[] missing = observedMutations
            .Except(covered, StringComparer.Ordinal)
            .Where(name => name is not "clipboard.read.text"
                && !name.StartsWith("filesystem.", StringComparison.Ordinal)
                && !name.StartsWith("backup.", StringComparison.Ordinal)
                && !name.StartsWith("capture.", StringComparison.Ordinal))
            .ToArray();
        Assert.That(missing, Is.Empty, string.Join(", ", missing));
    }

    private static IOperationHandler NoteHandler(string operation, INoteStore store) =>
        operation switch
        {
            "note.create" => new CreateNoteHandler(store),
            "note.update" => new UpdateNoteHandler(store),
            "note.trash" => new TrashNoteHandler(store),
            "note.restore" => new RestoreNoteHandler(store),
            _ => throw new ArgumentOutOfRangeException(nameof(operation)),
        };

    private static void AssertFailedClosed(OperationOutcome outcome, string operation)
    {
        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False, operation);
            Assert.That(outcome.Verified, Is.False, operation);
            Assert.That(outcome.ErrorCode, Is.EqualTo("verification_failed"), operation);
            Assert.That(
                ProductOperationNarrator.Instance.Narrate(operation, outcome),
                Does.Not.StartWith("Listo"),
                operation);
        });
    }

    private static OperationInvocation Invocation(string json) => new(
        Guid.NewGuid().ToString("D"),
        Guid.NewGuid().ToString("D"),
        Guid.NewGuid().ToString("D"),
        JsonDocument.Parse(json).RootElement.Clone());

    private static string NoteJson(string operation) => operation switch
    {
        "note.update" =>
            $$"""{"noteId":"{{FakeId:D}}","expectedTitle":"Goal05","expectedRevision":1,"title":"Goal05","content":"y"}""",
        "note.trash" or "note.restore" => $$"""{"noteId":"{{FakeId:D}}"}""",
        _ => """{"title":"Goal05","content":"x"}""",
    };

    private static string TaskJson(string operation) => operation switch
    {
        "task.update" =>
            $$"""{"taskId":"{{FakeId:D}}","expectedVersion":1,"title":"Goal05 task","details":"","due":null}""",
        "task.delete" =>
            $$"""{"taskId":"{{FakeId:D}}","expectedVersion":1,"reviewLabel":"Goal05 task"}""",
        _ => $$"""{"taskId":"{{FakeId:D}}","expectedVersion":1}""",
    };

    private static string ReminderJson(string operation)
    {
        string due = DateTimeOffset.UtcNow.AddHours(1).ToString("O", CultureInfo.InvariantCulture);
        return operation switch
        {
            "reminder.create" => $$"""{"title":"Goal05","dueUtc":"{{due}}"}""",
            "reminder.delete" =>
                $$"""{"reminderId":"{{FakeId:D}}","expectedVersion":1,"reviewLabel":"Goal05"}""",
            _ => $$"""{"reminderId":"{{FakeId:D}}","expectedVersion":1}""",
        };
    }

    private static string RoutineJson(string operation) => operation switch
    {
        "routine.phrase.create" =>
            """{"name":"Goal05","phrase":"frase mvp","action":"capture.screenshot"}""",
        "routine.set.enabled" =>
            $$"""{"routineId":"{{FakeId:D}}","expectedRevision":1,"enabled":false}""",
        "routine.delete" =>
            $$"""{"routineId":"{{FakeId:D}}","expectedRevision":1,"reviewLabel":"Goal05"}""",
        _ => $$"""{"routineId":"{{FakeId:D}}","expectedRevision":1}""",
    };

    private static JsonObject MemoryPayload(string operation) => operation switch
    {
        "memory.enable" => new JsonObject { ["version"] = 1, ["enabled"] = true },
        "memory.disable" => new JsonObject { ["version"] = 1, ["enabled"] = false },
        "memory.forget" => new JsonObject
        {
            ["version"] = 1,
            ["scope"] = "exact",
            ["selector"] = "goal05",
            ["confirmationRequired"] = true,
        },
        "memory.session.clear" => new JsonObject
        {
            ["version"] = 1,
            ["scope"] = "session",
            ["selector"] = null,
            ["confirmationRequired"] = false,
            ["mustNotDeletePersistent"] = true,
        },
        "memory.correct" => new JsonObject
        {
            ["version"] = 1,
            ["selector"] = "goal05",
            ["value"] = "y",
            ["retention"] = "persistent",
        },
        "memory.sensitive.save" => new JsonObject
        {
            ["version"] = 1,
            ["selector"] = "goal05",
            ["value"] = "secret",
            ["kind"] = "fact",
            ["retention"] = "persistent",
            ["sensitivity"] = "secret",
            ["tags"] = new JsonArray(),
        },
        _ => new JsonObject
        {
            ["version"] = 1,
            ["selector"] = "goal05",
            ["value"] = "x",
            ["kind"] = "fact",
            ["retention"] = "persistent",
            ["sensitivity"] = "normal",
            ["tags"] = new JsonArray(),
        },
    };

    private sealed class LyingNoteStore : INoteStore
    {
        public NoteRecord Create(string title, string content, string? idempotencyKey = null) =>
            FakeNote(title, content);

        public NoteRecord Read(Guid id, bool includeTrashed = false) =>
            throw new NoteNotFoundException(id);

        public NoteRecord ReadExactTitle(string title) =>
            throw new NoteNotFoundException(FakeId);

        public NoteRecord ReadSelected(NoteSelection selection) =>
            throw new NoteNotFoundException(selection.Id);

        public NoteRecord UpdateSelected(NoteSelection selection, string title, string content) =>
            FakeNote(title, content);

        public IReadOnlyList<NoteRecord> List(NoteListScope scope = NoteListScope.Active) => [];

        public NotePage ListPage(NoteListScope scope, int limit, int offset) =>
            new([], 0, limit, offset);

        public IReadOnlyList<NoteSummaryRecord> Search(string query, bool includeTrashed, int limit) =>
            [];

        public NoteRecord Trash(Guid id) => FakeNote("Goal05", "x", trashed: true);

        public NoteRecord TrashExactTitle(string title) => FakeNote(title, "x", trashed: true);

        public NoteRecord TrashSelected(NoteSelection selection) =>
            FakeNote(selection.ExpectedTitle, "x", trashed: true);

        public NoteRecord Restore(Guid id) => FakeNote("Goal05", "x");

        public NoteRecord RestoreExactTitle(string title) => FakeNote(title, "x");

        public NoteRecord RestoreSelected(NoteSelection selection) =>
            FakeNote(selection.ExpectedTitle, "x");

        private static NoteRecord FakeNote(string title, string content, bool trashed = false) =>
            new(
                FakeId,
                title,
                content,
                DateTimeOffset.UtcNow,
                DateTimeOffset.UtcNow,
                trashed ? DateTimeOffset.UtcNow : null,
                1);
    }

    private sealed class LyingTaskStore : ILocalTaskStore
    {
        public LocalTaskRecord Create(string title, string details, string? due) => FakeTask();

        public LocalTaskRecord Read(Guid id, bool includeDeleted = false) =>
            throw new LocalTaskNotFoundException($"missing {id:D}");

        public LocalTaskRecord ResolveExact(string title, bool includeDeleted) => FakeTask();

        public IReadOnlyList<LocalTaskRecord> List(
            TaskListStatus status,
            bool includeDeleted,
            int limit) => [];

        public IReadOnlyList<LocalTaskRecord> Search(
            string query,
            TaskListStatus status,
            int limit) => [];

        public LocalTaskRecord Update(
            Guid id,
            long expectedVersion,
            string title,
            string details,
            string? due) => FakeTask();

        public LocalTaskRecord SetCompleted(Guid id, long expectedVersion, bool completed) =>
            FakeTask(completed: completed);

        public LocalTaskRecord Delete(Guid id, long expectedVersion, string reviewLabel) =>
            FakeTask(deleted: true);

        public LocalTaskRecord Restore(Guid id, long expectedVersion) => FakeTask();

        private static LocalTaskRecord FakeTask(bool completed = false, bool deleted = false) =>
            new(
                FakeId,
                "Goal05",
                "",
                DateTimeOffset.UtcNow.AddHours(1),
                completed,
                completed ? DateTimeOffset.UtcNow : null,
                deleted,
                DateTimeOffset.UtcNow,
                DateTimeOffset.UtcNow,
                1);
    }

    private sealed class LyingRoutineStore : IRoutineStore
    {
        public RoutineRecord CreatePhrase(string name, string phrase, string action = "media.control") =>
            FakeRoutine();

        public RoutineRecord Read(Guid id, bool includeDeleted) =>
            throw new LocalTaskNotFoundException($"missing {id:D}");

        public IReadOnlyList<RoutineRecord> List(bool includeDeleted, int limit) => [];

        public RoutineRecord ResolveExact(string name, bool includeDeleted) => FakeRoutine();

        public RoutineRecord SetEnabled(Guid id, long expectedRevision, bool enabled) =>
            FakeRoutine(enabled: enabled);

        public RoutineRecord Delete(Guid id, long expectedRevision, string reviewLabel) =>
            FakeRoutine(deleted: true);

        public RoutineRecord Restore(Guid id, long expectedRevision) => FakeRoutine();

        private static RoutineRecord FakeRoutine(bool enabled = true, bool deleted = false) =>
            new(
                FakeId,
                "Goal05",
                "workflow",
                "1",
                [],
                "phrase",
                null,
                enabled,
                deleted,
                1,
                DateTimeOffset.UtcNow,
                DateTimeOffset.UtcNow);
    }

    private sealed class LyingFilesystemProvider : IFilesystemProvider
    {
        public FilesystemListResult List(string relativeDirectory, int limit) => new([], 0);

        public FilesystemListResult Search(string query, int limit) => new([], 0);

        public FilesystemTextResult ReadText(string resourceId, int maximumBytes) =>
            new(resourceId, "", 0, FakeHashB);

        public FilesystemEntry Hash(string resourceId) =>
            new(resourceId, "goal05.txt", "file", 1, DateTimeOffset.UtcNow, FakeHashB);

        public FilesystemMutationResult CreateDirectory(string relativePath) =>
            new("res", relativePath, "directory", 0, null, true);

        public FilesystemMutationResult WriteText(
            string relativePath,
            string text,
            string? expectedSha256) =>
            new("res", relativePath, "file", text.Length, FakeHashA, true);

        public FilesystemMutationResult Transfer(
            string resourceId,
            string destinationRelativePath,
            string expectedSha256,
            bool move) =>
            new(resourceId, destinationRelativePath, "file", 1, FakeHashA, true);

        public FilesystemTrashPreparation PrepareTrash(string resourceId) =>
            new("trash", "label", "file", 1);

        public FilesystemTrashReceipt CommitTrash(string trashId, string reviewLabel) =>
            new("restore", reviewLabel, true);

        public FilesystemMutationResult Restore(string restoreId) =>
            new("res", "restored.txt", "file", 1, FakeHashA, true);

        public BackupReceipt CreateBackup(string resourceId, string expectedSha256) =>
            new("bak", 1, FakeHashA, true);

        public BackupListResult ListBackups(int limit) => new([], 0);

        public BackupReceipt VerifyBackup(string backupId) =>
            new(backupId, 1, FakeHashB, true);

        public FilesystemMutationResult RestoreBackup(
            string backupId,
            string destinationRelativePath) =>
            new("res", destinationRelativePath, "file", 1, FakeHashA, true);
    }

    private sealed class LyingClipboardProvider : IClipboardProvider
    {
        public ValueTask<ClipboardTextSnapshot> ReadTextAsync(
            int maximumCharacters,
            CancellationToken cancellationToken) =>
            ValueTask.FromResult(new ClipboardTextSnapshot("other", 5, false, 1));

        public ValueTask<ClipboardWriteResult> WriteTextAsync(
            string text,
            CancellationToken cancellationToken) =>
            ValueTask.FromResult(new ClipboardWriteResult(2, text.Length, true));
    }

    private sealed class LyingMemoryStore : IMemoryStore
    {
        private bool LastConfigured { get; set; } = true;

        public string RootDirectory => "lying-memory";

        public MemoryConfigurationResult Configure(MemoryConfigureRequest request)
        {
            LastConfigured = request.Enabled;
            return new(request.Enabled, false);
        }

        public MemoryBeginSessionResult BeginSession(MemoryBeginSessionRequest request) =>
            new(0, false);

        public MemoryStatusResult Status(MemoryStatusRequest request) =>
            new(Enabled: !LastConfigured, 3, 1, 3, 0, 8);

        public MemorySaveResult Save(MemorySaveRequest request) =>
            new(FakeId, 1, request.Selector, false);

        public MemoryRecallResult Recall(MemoryRecallRequest request) => new(
        [
            new MemoryRecord(
                Guid.NewGuid(),
                1,
                request.Query.ToUpperInvariant(),
                request.Query.ToUpperInvariant(),
                "still-there",
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
                request.SessionId),
        ]);

        public MemoryListResult List(MemoryListRequest request) => new([]);

        public MemoryCorrectResult Correct(MemoryCorrectRequest request) =>
            new(FakeId, 2, request.Selector, false);

        public MemoryForgetResult Forget(MemoryForgetRequest request) => new(1, false);
    }

    private sealed class LyingMemoryExportWriter : IMemoryExportWriter
    {
        public MemoryExportResult Export(MemoryExportRequest request) =>
            new(@"C:\missing-goal05-export.json", request.Records.Count, FakeHashA, false);

        public bool Verify(MemoryExportVerificationRequest request) => false;
    }
}
