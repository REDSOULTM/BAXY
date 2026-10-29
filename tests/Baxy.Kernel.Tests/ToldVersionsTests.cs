using System.Text.Json;
using Baxy.Contracts;
using Baxy.Kernel.Mission;
using Baxy.Kernel.Operations;
using Baxy.Kernel.Policy;
using NUnit.Framework;

namespace Baxy.Kernel.Tests;

/// <summary>
/// Hallazgo de seguridad E030 (w9-sha): «sobrescribe notas.txt…» was refused with the file's current SHA-256, the model
/// retried with it and the file was replaced unasked. A version only a refusal or a failure told is no sighting: the
/// replacement asks, bound to that invocation; one a completed read gave goes as before.
/// </summary>
[TestFixture]
public sealed class ToldVersionsTests
{
    private const string Current = "1111111111111111111111111111111111111111111111111111111111111111";
    private const string NoteA = "0b8e7d2a-6f3c-4f7e-9a51-2f4b7c9d0e11";
    private const string NoteB = "5c1d9e3f-2a4b-4c6d-8e7f-9a0b1c2d3e44";

    [Test]
    public async Task AReplacementUnderAHashOnlyARefusalToldAsksAndRunsOnlyOnTheYesToThatCall()
    {
        var write = FileWrite();
        using var journal = new InMemoryInvocationJournal();
        using var engine = Engine(journal, ConfirmationMode.Normal, write);

        OperationResponse refused = await engine.ExecuteAsync(
            Request("file.write", """{"path":"notas.txt","text":"vacío"}"""), CancellationToken.None);
        OperationRequest retry = Request(
            "file.write", $$"""{"path":"notas.txt","text":"vacío","expectedSha256":"{{Current}}"}""");
        OperationResponse asked = await engine.ExecuteAsync(retry, CancellationToken.None);
        int replacedBeforeTheYes = write.Replaced;
        OperationResponse confirmed = await engine.ExecuteAsync(
            retry with
            {
                RequestId = Guid.NewGuid().ToString("D"),
                ConfirmationToken = asked.Result!.Value.GetProperty("token").GetString(),
            },
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(refused.ErrorCode, Is.EqualTo("version_conflict"));
            Assert.That(refused.Result!.Value.GetProperty("currentSha256").GetString(), Is.EqualTo(Current));
            Assert.That(asked.ErrorCode, Is.EqualTo(ConfirmationChallengeContract.RequiredErrorCode));
            Assert.That(replacedBeforeTheYes, Is.Zero);
            Assert.That(confirmed.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(write.Replaced, Is.EqualTo(1));
        });
    }

    [Test]
    public async Task TheYesToTheToldReplacementIsNotTheYesToAnotherText()
    {
        var write = FileWrite();
        using var journal = new InMemoryInvocationJournal();
        using var engine = Engine(journal, ConfirmationMode.Normal, write);
        await engine.ExecuteAsync(
            Request("file.write", """{"path":"notas.txt","text":"vacío"}"""), CancellationToken.None);
        OperationResponse asked = await engine.ExecuteAsync(
            Request("file.write", $$"""{"path":"notas.txt","text":"vacío","expectedSha256":"{{Current}}"}"""),
            CancellationToken.None);

        OperationResponse other = await engine.ExecuteAsync(
            Request("file.write", $$"""{"path":"notas.txt","text":"otro","expectedSha256":"{{Current}}"}""")
                with { ConfirmationToken = asked.Result!.Value.GetProperty("token").GetString() },
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(other.ErrorCode, Is.EqualTo(ConfirmationChallengeContract.RequiredErrorCode));
            Assert.That(write.Replaced, Is.Zero);
        });
    }

    // A real read of the file (file.read completed) is still a sighting, whether it came before the refusal or after it.
    [TestCase(true)]
    [TestCase(false)]
    public async Task AHashACompletedReadGaveIsObserved(bool readFirst)
    {
        var write = FileWrite();
        var read = new ScriptedHandler("file.read", _ => OperationOutcome.Success(Json(
            $$"""{"fileSha256":"{{Current}}","text":"uno\ndos\ntres\n"}""")));
        using var journal = new InMemoryInvocationJournal();
        using var engine = Engine(journal, ConfirmationMode.Normal, write, read);
        OperationRequest reading = Request("file.read", """{"path":"home/notas.txt"}""");
        OperationRequest refused = Request("file.write", """{"path":"notas.txt","text":"vacío"}""");
        foreach (OperationRequest request in readFirst ? [reading, refused] : new[] { refused, reading })
        {
            await engine.ExecuteAsync(request, CancellationToken.None);
        }

        OperationResponse replaced = await engine.ExecuteAsync(
            Request("file.write", $$"""{"path":"notas.txt","text":"vacío","expectedSha256":"{{Current}}"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(replaced.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(write.Replaced, Is.EqualTo(1));
        });
    }

    [Test]
    public async Task BypassAndAnAppendGoAsBefore()
    {
        var write = FileWrite();
        using var journal = new InMemoryInvocationJournal();
        using (var engine = Engine(journal, ConfirmationMode.Bypass, write))
        {
            await engine.ExecuteAsync(
                Request("file.write", """{"path":"notas.txt","text":"vacío"}"""), CancellationToken.None);
            OperationResponse bypassed = await engine.ExecuteAsync(
                Request("file.write", $$"""{"path":"notas.txt","text":"vacío","expectedSha256":"{{Current}}"}"""),
                CancellationToken.None);
            Assert.That(bypassed.Status, Is.EqualTo(OperationStatuses.Completed));
        }

        using var normal = Engine(journal, ConfirmationMode.Normal, write);
        await normal.ExecuteAsync(
            Request("file.write", """{"path":"notas.txt","text":"vacío"}"""), CancellationToken.None);
        OperationResponse appended = await normal.ExecuteAsync(
            Request(
                "file.write",
                $$"""{"path":"notas.txt","text":"cuatro","append":true,"expectedSha256":"{{Current}}"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(appended.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(write.Replaced, Is.EqualTo(1));
        });
    }

    // The same pattern in note.update: note_selection_stale tells the note's revision, never its content. The version
    // belongs to its note: another note at the same revision in a listing is no sighting of this one, its own read is.
    [Test]
    public async Task ANoteUpdateUnderARevisionOnlyAStaleRefusalToldAsks()
    {
        var update = new ScriptedHandler("note.update", arguments =>
            arguments.GetProperty("expectedRevision").GetInt64() == 3
                ? OperationOutcome.Success(Json($$"""{"noteId":"{{NoteA}}","revision":4}"""))
                : OperationOutcome.Failure(
                    "note_selection_stale",
                    Json($$"""{"note":{"noteId":"{{NoteA}}","title":"Compras","revision":3,"isTrashed":false} }""")));
        var list = new ScriptedHandler("note.list", _ => OperationOutcome.Success(Json(
            $$"""{"notes":[{"noteId":"{{NoteB}}","title":"Viaje","revision":3}]}""")));
        var read = new ScriptedHandler("note.read", _ => OperationOutcome.Success(Json(
            $$"""{"noteId":"{{NoteA}}","title":"Compras","content":"pan","revision":3}""")));
        using var journal = new InMemoryInvocationJournal();
        using var engine = Engine(journal, ConfirmationMode.Normal, update, list, read);
        string Arguments(int revision) =>
            $$"""{"noteId":"{{NoteA}}","expectedRevision":{{revision}},"expectedTitle":"Compras","title":"Compras","content":"leche"}""";

        await engine.ExecuteAsync(Request("note.update", Arguments(2)), CancellationToken.None);
        await engine.ExecuteAsync(Request("note.list", "{}"), CancellationToken.None);
        OperationResponse asked = await engine.ExecuteAsync(Request("note.update", Arguments(3)), CancellationToken.None);
        int updatesBeforeTheRead = update.Executions;
        await engine.ExecuteAsync(Request("note.read", $$"""{"noteId":"{{NoteA}}"}"""), CancellationToken.None);
        OperationResponse updated = await engine.ExecuteAsync(Request("note.update", Arguments(3)), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(asked.ErrorCode, Is.EqualTo(ConfirmationChallengeContract.RequiredErrorCode));
            Assert.That(updatesBeforeTheRead, Is.EqualTo(1));
            Assert.That(updated.Status, Is.EqualTo(OperationStatuses.Completed));
        });
    }

    [Test]
    public async Task ATaskUpdateUnderAVersionOnlyAConflictToldAsks()
    {
        const string task = "9d4c2b1a-7e6f-4a3b-8c2d-1e0f9a8b7c66";
        var update = new ScriptedHandler("task.update", arguments =>
            arguments.GetProperty("expectedVersion").GetInt64() == 2
                ? OperationOutcome.Success()
                : OperationOutcome.Failure(
                    "task_version_conflict",
                    Json($$"""{"taskId":"{{task}}","current":{"taskId":"{{task}}","title":"Pagar luz","version":2} }""")));
        using var journal = new InMemoryInvocationJournal();
        using var engine = Engine(journal, ConfirmationMode.Normal, update);
        string Arguments(int version) =>
            $$"""{"taskId":"{{task}}","expectedVersion":{{version}},"title":"Pagar luz","details":"","due":null}""";

        await engine.ExecuteAsync(Request("task.update", Arguments(1)), CancellationToken.None);
        OperationResponse asked = await engine.ExecuteAsync(Request("task.update", Arguments(2)), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(asked.ErrorCode, Is.EqualTo(ConfirmationChallengeContract.RequiredErrorCode));
            Assert.That(update.Executions, Is.EqualTo(1));
        });
    }

    // Revisión 2026-10-25: a version a completed response later gave left the told set but stayed in its order, which
    // still counted it; past a thousand versions known only from refusals, one still only told was forgotten early and
    // its replacement went unasked. Only the versions still told count.
    [Test]
    public void AVersionLaterObservedDoesNotPushOutOneStillOnlyTold()
    {
        var versions = new ToldVersions();
        string[] told = [.. Enumerable.Range(0, 1024).Select(static i => Hash(i))];
        foreach (string hash in told)
        {
            versions.Record(Answer(OperationStatuses.Failed, "currentSha256", hash));
        }

        foreach (string hash in told[^24..])
        {
            versions.Record(Answer(OperationStatuses.Completed, "sha256", hash));
        }

        foreach (int i in Enumerable.Range(5000, 24))
        {
            versions.Record(Answer(OperationStatuses.Failed, "currentSha256", Hash(i)));
        }

        Assert.Multiple(() =>
        {
            Assert.That(versions.OnlyToldBy("file.write", Replace(told[0])), Is.True);
            Assert.That(versions.OnlyToldBy("file.write", Replace(told[^1])), Is.False);
            Assert.That(versions.OnlyToldBy("file.write", Replace(Hash(5023))), Is.True);
        });

        static OperationResponse Answer(string status, string name, string hash) => new(
            ProtocolTypes.OperationResponse,
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            status,
            "hechos",
            status == OperationStatuses.Completed,
            false,
            Json($$"""{"{{name}}":"{{hash}}"}"""),
            status == OperationStatuses.Completed ? null : "version_conflict");

        static string Hash(int value) => value.ToString("x64", System.Globalization.CultureInfo.InvariantCulture);

        static JsonElement Replace(string hash) =>
            Json($$"""{"path":"notas.txt","text":"vacío","expectedSha256":"{{hash}}"}""");
    }

    private static MissionEngine Engine(
        InMemoryInvocationJournal journal,
        ConfirmationMode mode,
        params IOperationHandler[] handlers) =>
        new(new OperationRegistry(handlers), journal, new MissionEngineOptions { ConfirmationMode = () => mode });

    // file.write as LocalFilesystemProvider answers it: a replace needs the file's exact current hash, and the refusal
    // tells it (currentSha256); an append keeps what is there.
    private static ScriptedHandler FileWrite() => new("file.write", arguments =>
        arguments.TryGetProperty("append", out JsonElement append) && append.ValueKind == JsonValueKind.True
            ? OperationOutcome.Success(Json("""{"sha256":"2222222222222222222222222222222222222222222222222222222222222222"}"""))
            : arguments.TryGetProperty("expectedSha256", out JsonElement hash) && hash.GetString() == Current
                ? OperationOutcome.Success(Json("""{"sha256":"3333333333333333333333333333333333333333333333333333333333333333","previousVersionRecycled":true}"""))
                : OperationOutcome.Failure(
                    "version_conflict",
                    Json($$"""{"exists":true,"append":false,"currentSha256":"{{Current}}","size":15}""")));

    private static OperationRequest Request(string operation, string arguments) => new(
        ProtocolTypes.OperationRequest,
        Guid.NewGuid().ToString("D"),
        Guid.NewGuid().ToString("D"),
        Guid.NewGuid().ToString("D"),
        operation,
        Json(arguments));

    private static JsonElement Json(string json) => JsonDocument.Parse(json).RootElement.Clone();

    private sealed class ScriptedHandler(string operation, Func<JsonElement, OperationOutcome> run) : IOperationHandler
    {
        public int Executions { get; private set; }

        public int Replaced { get; private set; }

        public OperationDefinition Definition { get; } = ProductCatalog.CreateDefinition(operation);

        public ValueTask<OperationOutcome> ExecuteAsync(OperationInvocation invocation, CancellationToken cancellationToken)
        {
            Executions++;
            OperationOutcome outcome = run(invocation.Arguments);
            if (outcome.Succeeded
                && invocation.Arguments.TryGetProperty("expectedSha256", out _)
                && !invocation.Arguments.TryGetProperty("append", out _))
            {
                Replaced++;
            }

            return ValueTask.FromResult(outcome);
        }
    }
}
