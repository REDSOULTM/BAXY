using System.Globalization;
using System.Security.Cryptography;
using System.Text.Json;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Filesystem;
using Baxy.Providers.Windows.Notes;
using Baxy.Providers.Windows.Routines;
using Baxy.Providers.Windows.Tasks;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class MvpLocalStatefulHandlerMatrixTests
{
    private const int ExpectedOperations = 45;
    private static readonly JsonSerializerOptions EvidenceJsonOptions = new()
    {
        WriteIndented = true,
    };

    [Test]
    public async Task EveryLocalStatefulHandlerReachesVerifiedStateInIsolatedStores()
    {
        using var temporary = new TemporaryDirectory();
        var rows = new List<MatrixRow>(ExpectedOperations);

        await ExerciseFilesystemAsync(temporary.Path, rows);
        await ExerciseNotesAsync(temporary.Path, rows);
        await ExerciseTasksAsync(temporary.Path, rows);
        await ExerciseRemindersAsync(temporary.Path, rows);
        await ExerciseRoutinesAsync(temporary.Path, rows);

        Assert.Multiple(() =>
        {
            Assert.That(rows, Has.Count.EqualTo(ExpectedOperations));
            Assert.That(rows.Select(row => row.Operation), Is.Unique);
            Assert.That(rows, Has.All.Matches<MatrixRow>(row => row.Verified));
            Assert.That(rows, Has.All.Matches<MatrixRow>(row => !row.EffectMayHaveOccurred));
        });
        WriteOptionalEvidence(rows);
    }

    private static async Task ExerciseFilesystemAsync(string root, List<MatrixRow> rows)
    {
        var provider = new LocalFilesystemProvider(Path.Combine(root, "filesystem"));
        Dictionary<string, IOperationHandler> handlers = FilesystemHandlers.Create(provider)
            .ToDictionary(handler => handler.Definition.Name, StringComparer.Ordinal);

        await RunAsync(handlers, "filesystem.create.directory",
            """{"relativePath":"workspace"}""", "local_filesystem_cas", rows);
        JsonElement written = await RunAsync(handlers, "filesystem.write.text",
            """{"relativePath":"workspace/source.txt","text":"BAXY MVP"}""",
            "local_filesystem_cas", rows);
        string sourceId = RequiredString(written, "resourceId");
        string sourceHash = RequiredString(written, "sha256");
        await RunAsync(handlers, "filesystem.list",
            """{"relativeDirectory":"workspace","limit":20}""",
            "local_filesystem_cas", rows);
        await RunAsync(handlers, "filesystem.search",
            """{"query":"source","limit":20}""", "local_filesystem_cas", rows);
        await RunAsync(handlers, "filesystem.read.text",
            $$"""{"resourceId":"{{sourceId}}","maximumBytes":4096}""",
            "local_filesystem_cas", rows);
        await RunAsync(handlers, "filesystem.hash",
            $$"""{"resourceId":"{{sourceId}}"}""", "local_filesystem_cas", rows);
        JsonElement copied = await RunAsync(handlers, "filesystem.copy",
            $$"""{"resourceId":"{{sourceId}}","destinationRelativePath":"workspace/copy.txt","expectedSha256":"{{sourceHash}}"}""",
            "local_filesystem_cas", rows);
        string copiedId = RequiredString(copied, "resourceId");
        JsonElement moved = await RunAsync(handlers, "filesystem.move",
            $$"""{"resourceId":"{{copiedId}}","destinationRelativePath":"workspace/moved.txt","expectedSha256":"{{sourceHash}}"}""",
            "local_filesystem_cas", rows);
        string movedId = RequiredString(moved, "resourceId");
        JsonElement backup = await RunAsync(handlers, "backup.create",
            $$"""{"resourceId":"{{movedId}}","expectedSha256":"{{sourceHash}}"}""",
            "local_filesystem_hash_postread", rows);
        string backupId = RequiredString(backup, "backupId");
        await RunAsync(handlers, "backup.list", """{"limit":20}""",
            "local_filesystem_hash_postread", rows);
        await RunAsync(handlers, "backup.verify",
            $$"""{"backupId":"{{backupId}}"}""",
            "local_filesystem_hash_postread", rows);
        await RunAsync(handlers, "backup.restore",
            $$"""{"backupId":"{{backupId}}","destinationRelativePath":"workspace/restored-backup.txt"}""",
            "local_filesystem_hash_postread", rows);
        JsonElement prepared = await RunAsync(handlers, "filesystem.trash.prepare",
            $$"""{"resourceId":"{{movedId}}"}""", "local_filesystem_cas", rows);
        string trashId = RequiredString(prepared, "trashId");
        string reviewLabel = RequiredString(prepared, "reviewLabel");
        JsonElement trashed = await RunAsync(handlers, "filesystem.trash.commit",
            $$"""{"trashId":"{{trashId}}","reviewLabel":"{{reviewLabel}}"}""",
            "local_filesystem_cas", rows);
        await RunAsync(handlers, "filesystem.trash.restore",
            $$"""{"restoreId":"{{RequiredString(trashed, "restoreId")}}"}""",
            "local_filesystem_cas", rows);
    }

    private static async Task ExerciseNotesAsync(string root, List<MatrixRow> rows)
    {
        var store = new LocalNoteStore(Path.Combine(root, "notes"));
        IOperationHandler[] all =
        [
            new CreateNoteHandler(store), new ListNotesHandler(store),
            new ReadNoteHandler(store), new RestoreNoteHandler(store),
            new SearchNotesHandler(store), new TrashNoteHandler(store),
            new UpdateNoteHandler(store),
        ];
        Dictionary<string, IOperationHandler> handlers = all.ToDictionary(
            handler => handler.Definition.Name, StringComparer.Ordinal);
        JsonElement created = await RunAsync(handlers, "note.create",
            """{"title":"MVP local","content":"evidencia inicial"}""",
            "note_store_verified_postread", rows);
        string id = RequiredString(created, "noteId");
        await RunAsync(handlers, "note.list", "{}", "note_store_verified_postread", rows);
        await RunAsync(handlers, "note.read", $$"""{"noteId":"{{id}}"}""",
            "note_store_verified_postread", rows);
        await RunAsync(handlers, "note.search", """{"query":"evidencia"}""",
            "note_store_verified_postread", rows);
        JsonElement updated = await RunAsync(handlers, "note.update",
            $$"""{"noteId":"{{id}}","expectedTitle":"MVP local","expectedRevision":{{created.GetProperty("revision").GetInt64()}},"title":"MVP local verificado","content":"evidencia final"}""",
            "note_store_verified_postread", rows);
        await RunAsync(handlers, "note.trash", $$"""{"noteId":"{{id}}"}""",
            "note_store_verified_postread", rows);
        await RunAsync(handlers, "note.restore", $$"""{"noteId":"{{id}}"}""",
            "note_store_verified_postread", rows);
        Assert.That(updated.GetProperty("revision").GetInt64(), Is.GreaterThan(1));
    }

    private static async Task ExerciseTasksAsync(string root, List<MatrixRow> rows)
    {
        var store = new LocalTaskStore(Path.Combine(root, "tasks"));
        Dictionary<string, IOperationHandler> handlers = TaskHandlers.Create(store)
            .ToDictionary(handler => handler.Definition.Name, StringComparer.Ordinal);
        JsonElement current = await RunAsync(handlers, "task.create",
            """{"title":"Validar MVP","details":"matriz local","due":null}""",
            "task_store_cas_postread", rows);
        string id = RequiredString(current, "taskId");
        await RunAsync(handlers, "task.list", "{}", "task_store_cas_postread", rows);
        await RunAsync(handlers, "task.search", """{"query":"matriz"}""",
            "task_store_cas_postread", rows);
        await RunAsync(handlers, "task.resolve.exact",
            """{"title":"validar mvp"}""", "task_store_cas_postread", rows);
        current = await RunAsync(handlers, "task.update",
            TaskUpdateJson(id, current, "Validar MVP final"),
            "task_store_cas_postread", rows);
        current = await RunAsync(handlers, "task.complete",
            TaskCasJson(id, current), "task_store_cas_postread", rows);
        current = await RunAsync(handlers, "task.reopen",
            TaskCasJson(id, current), "task_store_cas_postread", rows);
        current = await RunAsync(handlers, "task.delete",
            $$"""{"taskId":"{{id}}","expectedVersion":{{Version(current)}},"reviewLabel":"Validar MVP final"}""",
            "task_store_cas_postread", rows);
        await RunAsync(handlers, "task.restore", TaskCasJson(id, current),
            "task_store_cas_postread", rows);
    }

    private static async Task ExerciseRemindersAsync(string root, List<MatrixRow> rows)
    {
        DateTimeOffset now = new(2026, 8, 11, 12, 0, 0, TimeSpan.Zero);
        var time = new MutableTimeProvider(now);
        var store = new LocalTaskStore(Path.Combine(root, "reminders"));
        Dictionary<string, IOperationHandler> handlers = ReminderHandlers.Create(store, time)
            .ToDictionary(handler => handler.Definition.Name, StringComparer.Ordinal);
        string due = now.AddMinutes(1).ToString("O", CultureInfo.InvariantCulture);
        JsonElement current = await RunAsync(handlers, "reminder.create",
            $$"""{"title":"Revisar matriz","dueUtc":"{{due}}"}""",
            "reminder_store_cas_postread", rows);
        string id = RequiredString(current, "reminderId");
        await RunAsync(handlers, "reminder.list", "{}",
            "reminder_store_cas_postread", rows);
        await RunAsync(handlers, "reminder.resolve.exact",
            """{"title":"revisar matriz"}""", "reminder_store_cas_postread", rows);
        time.UtcNow = now.AddMinutes(2);
        await RunAsync(handlers, "notification.list.due", "{}",
            "reminder_store_cas_postread", rows);
        current = await RunAsync(handlers, "notification.dismiss",
            ReminderCasJson(id, current), "reminder_store_cas_postread", rows);
        current = await RunAsync(handlers, "reminder.delete",
            $$"""{"reminderId":"{{id}}","expectedVersion":{{Version(current)}},"reviewLabel":"Revisar matriz"}""",
            "reminder_store_cas_postread", rows);
        await RunAsync(handlers, "reminder.restore", ReminderCasJson(id, current),
            "reminder_store_cas_postread", rows);
    }

    private static async Task ExerciseRoutinesAsync(string root, List<MatrixRow> rows)
    {
        var store = new LocalRoutineStore(Path.Combine(root, "routines"));
        Dictionary<string, IOperationHandler> handlers = RoutineHandlers.Create(store)
            .ToDictionary(handler => handler.Definition.Name, StringComparer.Ordinal);
        JsonElement created = await RunAsync(handlers, "routine.phrase.create",
            """{"name":"Captura MVP","phrase":"pantallazo mvp","action":"capture.screenshot"}""",
            "routine_store_cas", rows);
        JsonElement routine = created.GetProperty("routine");
        string id = RequiredString(routine, "routineId");
        long revision = routine.GetProperty("revision").GetInt64();
        await RunAsync(handlers, "routine.list", "{}", "routine_store_cas", rows);
        await RunAsync(handlers, "routine.read", $$"""{"routineId":"{{id}}"}""",
            "routine_store_cas", rows);
        await RunAsync(handlers, "routine.resolve.exact",
            """{"name":"captura mvp"}""", "routine_store_cas", rows);
        JsonElement current = await RunAsync(handlers, "routine.set.enabled",
            $$"""{"routineId":"{{id}}","expectedRevision":{{revision}},"enabled":false}""",
            "routine_store_cas", rows);
        current = await RunAsync(handlers, "routine.delete",
            $$"""{"routineId":"{{id}}","expectedRevision":{{current.GetProperty("revision").GetInt64()}},"reviewLabel":"Captura MVP"}""",
            "routine_store_cas", rows);
        await RunAsync(handlers, "routine.restore",
            $$"""{"routineId":"{{id}}","expectedRevision":{{current.GetProperty("revision").GetInt64()}}}""",
            "routine_store_cas", rows);
    }

    private static async Task<JsonElement> RunAsync(
        Dictionary<string, IOperationHandler> handlers,
        string operation,
        string json,
        string verifier,
        List<MatrixRow> rows)
    {
        using JsonDocument document = JsonDocument.Parse(json);
        var invocation = new OperationInvocation(
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            document.RootElement.Clone());
        OperationOutcome outcome = await handlers[operation].ExecuteAsync(
            invocation,
            CancellationToken.None);
        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True, operation);
            Assert.That(outcome.Verified, Is.True, operation);
            Assert.That(outcome.Result, Is.Not.Null, operation);
            Assert.That(outcome.EffectMayHaveOccurred, Is.False, operation);
        });
        rows.Add(new MatrixRow(operation, verifier, outcome.Verified,
            outcome.EffectMayHaveOccurred, 0));
        return outcome.Result!.Value.Clone();
    }

    private static string RequiredString(JsonElement value, string name) =>
        value.GetProperty(name).GetString()
        ?? throw new InvalidDataException($"Missing {name}.");

    private static long Version(JsonElement value) =>
        value.GetProperty("version").GetInt64();

    private static string TaskCasJson(string id, JsonElement current) =>
        $$"""{"taskId":"{{id}}","expectedVersion":{{Version(current)}}}""";

    private static string TaskUpdateJson(string id, JsonElement current, string title) =>
        $$"""{"taskId":"{{id}}","expectedVersion":{{Version(current)}},"title":"{{title}}","details":"matriz verificada","due":null}""";

    private static string ReminderCasJson(string id, JsonElement current) =>
        $$"""{"reminderId":"{{id}}","expectedVersion":{{Version(current)}}}""";

    private static void WriteOptionalEvidence(List<MatrixRow> rows)
    {
        string? configured = Environment.GetEnvironmentVariable(
            "BAXY_MVP_LOCAL_STATEFUL_MATRIX_OUTPUT");
        if (string.IsNullOrWhiteSpace(configured)) return;
        string output = Path.GetFullPath(configured);
        if (File.Exists(output))
            throw new InvalidOperationException($"Refusing to overwrite evidence: {output}");
        Directory.CreateDirectory(Path.GetDirectoryName(output)!);
        string coreAssembly = typeof(FilesystemHandlers).Assembly.Location;
        string testAssembly = typeof(MvpLocalStatefulHandlerMatrixTests).Assembly.Location;
        var report = new
        {
            schema = "baxy.mvp-local-stateful-handler-matrix.v1",
            measuredAtUtc = DateTimeOffset.UtcNow.ToString("O"),
            scope = "all_local_stateful_handlers_with_isolated_real_stores",
            actualUserEffectsExecuted = 0,
            isolatedStoreMutations = rows.Count,
            coreAssemblySha256 = FileSha256(coreAssembly),
            testAssemblySha256 = FileSha256(testAssembly),
            metrics = new
            {
                operations = rows.Count,
                verified = rows.Count(row => row.Verified),
                possibleEffects = rows.Count(row => row.EffectMayHaveOccurred),
                failed = 0,
            },
            rows,
            gatePassed = rows.Count == ExpectedOperations
                && rows.All(row => row.Verified && !row.EffectMayHaveOccurred),
        };
        File.WriteAllText(output,
            JsonSerializer.Serialize(report, EvidenceJsonOptions) + Environment.NewLine);
    }

    private static string FileSha256(string path) =>
        Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))).ToLowerInvariant();

    private sealed record MatrixRow(
        string Operation,
        string Verifier,
        bool Verified,
        bool EffectMayHaveOccurred,
        int ActualUserEffectsExecuted);

    private sealed class MutableTimeProvider(DateTimeOffset utcNow) : TimeProvider
    {
        public DateTimeOffset UtcNow { get; set; } = utcNow;
        public override DateTimeOffset GetUtcNow() => UtcNow;
    }

    private sealed class TemporaryDirectory : IDisposable
    {
        public TemporaryDirectory()
        {
            Path = System.IO.Path.Combine(
                System.IO.Path.GetTempPath(),
                "baxy-mvp-local-matrix",
                Guid.NewGuid().ToString("N", CultureInfo.InvariantCulture));
            Directory.CreateDirectory(Path);
        }

        public string Path { get; }

        public void Dispose()
        {
            if (Directory.Exists(Path)) Directory.Delete(Path, recursive: true);
        }
    }
}
