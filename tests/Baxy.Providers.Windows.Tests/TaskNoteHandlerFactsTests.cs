using System.Text.Json;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Infrastructure;
using Baxy.Providers.Windows.Notes;
using Baxy.Providers.Windows.Tasks;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Renew al máximo (w5): a task or note refused for its target says what the store holds there now, and a deletion
/// whose target is not there fails before the person is asked for a yes.
/// </summary>
[TestFixture]
public sealed class TaskNoteHandlerFactsTests
{
    // A task.complete retried after it was done (its version moved) came back a bare task_version_conflict; it says the
    // task is completed at its version now, and that nothing was changed.
    [TestCase("all", true)]
    [TestCase("none", false)]
    public async Task AStaleTaskVersionSaysTheTaskAsItIsNow(string aids, bool hint)
    {
        using IDisposable setting = ModelAids.Use(aids);
        using TemporaryDirectory temporary = new();
        var store = new LocalTaskStore(Path.Combine(temporary.Path, "tasks"));
        LocalTaskRecord created = store.Create("Comprar pan", string.Empty, null);
        store.SetCompleted(created.Id, created.Version, true);

        OperationOutcome outcome = await new CompleteTaskHandler(store).ExecuteAsync(
            Invocation($$"""{"taskId":"{{created.Id:D}}","expectedVersion":{{created.Version}}}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("task_version_conflict"));
            JsonElement current = outcome.Result!.Value.GetProperty("current");
            Assert.That(current.GetProperty("completed").GetBoolean(), Is.True);
            Assert.That(current.GetProperty("version").GetInt64(), Is.EqualTo(created.Version + 1));
            Assert.That(outcome.Result!.Value.TryGetProperty("next", out JsonElement next), Is.EqualTo(hint));
            if (hint)
            {
                Assert.That(next.GetString(), Is.EqualTo(
                    $"nothing was changed: the task is completed at version {created.Version + 1} now"));
            }
        });
    }

    // Renew al máximo (w8): «10/11/2026» was read month first (11 October, where a Spanish speaker means 10 November)
    // and stored without a word; only the ISO shape is read, and the refusal says which field and why.
    [TestCase("10/11/2026", false)]
    [TestCase("2026-11-10", true)]
    [TestCase("2026-11-10T08:00:00-03:00", true)]
    public async Task ATaskDueIsReadOnlyInTheIsoShape(string due, bool accepted)
    {
        using IDisposable setting = ModelAids.Use("all");
        using TemporaryDirectory temporary = new();
        var store = new LocalTaskStore(Path.Combine(temporary.Path, "tasks"));

        OperationOutcome outcome = await new CreateTaskHandler(store).ExecuteAsync(
            Invocation($$"""{"title":"Pagar la luz","due":"{{due}}"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.EqualTo(accepted), outcome.ErrorCode);
            if (accepted)
                return;
            Assert.That(outcome.ErrorCode, Is.EqualTo("invalid_task"));
            Assert.That(outcome.Result!.Value.GetProperty("problem").GetString(), Is.EqualTo("due must be an ISO date-time."));
            Assert.That(outcome.Result!.Value.GetProperty("next").GetString(), Does.StartWith("nothing was written"));
            Assert.That(store.List(TaskListStatus.All, includeDeleted: true, limit: 10).MatchCount, Is.Zero);
        });
    }

    // An id no task has says where it was looked (deleted ones included) and where the ids are.
    [Test]
    public async Task AnUnknownTaskIdSaysNoTaskHasIt()
    {
        using IDisposable setting = ModelAids.Use("all");
        using TemporaryDirectory temporary = new();
        var store = new LocalTaskStore(Path.Combine(temporary.Path, "tasks"));
        store.Create("Comprar pan", string.Empty, null);

        OperationOutcome outcome = await new CompleteTaskHandler(store).ExecuteAsync(
            Invocation("""{"taskId":"8f1d2c3b-0a4e-4f5d-9c6b-7a8e9f0a1b2c","expectedVersion":1}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("task_not_found"));
            Assert.That(outcome.Result!.Value.GetProperty("searched").GetString(), Is.EqualTo("active and deleted tasks"));
            Assert.That(outcome.Result!.Value.GetProperty("next").GetString(), Does.Contain("task.search or task.list"));
        });
    }

    // A task.delete (it asks the person's yes) whose label is not the task's title failed only after the yes; it fails
    // before asking, saying the exact title, and a matching one goes on to ask.
    [Test]
    public async Task ATaskDeleteWhoseLabelIsNotTheTitleFailsBeforeTheYes()
    {
        using IDisposable setting = ModelAids.Use("all");
        using TemporaryDirectory temporary = new();
        var store = new LocalTaskStore(Path.Combine(temporary.Path, "tasks"));
        LocalTaskRecord created = store.Create("Comprar pan", string.Empty, null);
        var handler = new DeleteTaskHandler(store);

        InvocationPreflightResult wrong = await Preflight(handler,
            Json($$"""{"taskId":"{{created.Id:D}}","expectedVersion":1,"reviewLabel":"comprar pan"}"""),
            CancellationToken.None);
        InvocationPreflightResult right = await Preflight(handler,
            Json($$"""{"taskId":"{{created.Id:D}}","expectedVersion":1,"reviewLabel":"Comprar pan"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(wrong.Failure?.ErrorCode, Is.EqualTo("task_version_conflict"));
            Assert.That(wrong.Failure?.EffectMayHaveOccurred, Is.False);
            Assert.That(wrong.Failure?.Result?.GetProperty("next").GetString(),
                Is.EqualTo("nothing was changed: reviewLabel must be the task's exact title, \"Comprar pan\""));
            Assert.That(right, Is.SameAs(InvocationPreflightResult.Proceed));
            Assert.That(store.Read(created.Id).Deleted, Is.False);
        });
    }

    // A note.read by the title of a note in the trash was a bare note_not_found («no existe»); it names the one in the
    // trash and where it was looked, and (aid note_not_found_next) how it comes back.
    [TestCase("all", true)]
    [TestCase("none", false)]
    public async Task ANoteReadByTheTitleOfATrashedNoteSaysItIsInTheTrash(string aids, bool hint)
    {
        using IDisposable setting = ModelAids.Use(aids);
        using TemporaryDirectory temporary = new();
        var store = new LocalNoteStore(Path.Combine(temporary.Path, "notes"));
        NoteRecord note = store.Create("Lista de compras", "pan");
        store.Trash(note.Id);

        OperationOutcome outcome = await new ReadNoteHandler(store).ExecuteAsync(
            Invocation("""{"title":"lista de compras"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("note_not_found"));
            Assert.That(outcome.Result!.Value.GetProperty("searched").GetString(), Is.EqualTo("active notes"));
            Assert.That(outcome.Result!.Value.GetProperty("inTrash")[0].GetProperty("noteId").GetString(),
                Is.EqualTo(note.Id.ToString("D")));
            Assert.That(outcome.Result!.Value.TryGetProperty("next", out JsonElement next), Is.EqualTo(hint));
            if (hint)
            {
                Assert.That(next.GetString(), Is.EqualTo(
                    "a note titled \"lista de compras\" is in the trash; note.restore brings it back"));
            }
        });
    }

    // A title written a little differently names the notes whose titles come close.
    [Test]
    public async Task ANoteTitleNotFoundNamesTheTitlesCloseToIt()
    {
        using IDisposable setting = ModelAids.Use("all");
        using TemporaryDirectory temporary = new();
        var store = new LocalNoteStore(Path.Combine(temporary.Path, "notes"));
        store.Create("Compras del súper", "pan");
        store.Create("Ideas", "x");

        OperationOutcome outcome = await new ReadNoteHandler(store).ExecuteAsync(
            Invocation("""{"title":"compras"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("note_not_found"));
            Assert.That(outcome.Result!.Value.GetProperty("similarTitles").GetArrayLength(), Is.EqualTo(1));
            Assert.That(outcome.Result!.Value.GetProperty("next").GetString(), Is.EqualTo(
                "no note is titled \"compras\" exactly among active notes; titles close to it: \"Compras del súper\"; "
                + "note.search finds notes by the words they contain"));
        });
    }

    // A note.trash (it asks the person's yes) of a title no note has failed only after the yes; it fails before asking.
    // Renew al máximo (w9): one note of that title asks for its snapshot first (ANoteTrashYesIsAskedForASnapshot).
    [Test]
    public async Task ANoteTrashOfATitleNoNoteHasFailsBeforeTheYes()
    {
        using TemporaryDirectory temporary = new();
        var store = new LocalNoteStore(Path.Combine(temporary.Path, "notes"));
        store.Create("Ideas", "x");
        var handler = new TrashNoteHandler(store);

        InvocationPreflightResult missing = await Preflight(handler, Json("""{"title":"Recetas"}"""), CancellationToken.None);
        InvocationPreflightResult present = await Preflight(handler, Json("""{"title":"ideas"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(missing.Failure?.ErrorCode, Is.EqualTo("note_not_found"));
            Assert.That(missing.Failure?.EffectMayHaveOccurred, Is.False);
            Assert.That(missing.Failure?.Result?.GetProperty("searched").GetString(),
                Is.EqualTo("active and trashed notes"));
            Assert.That(present.Failure?.ErrorCode, Is.EqualTo("note_trash_snapshot_required"));
        });
    }

    // Renew al máximo (w9): the yes of a note.trash named only the title or the id, so a note edited between the yes and
    // the run was trashed as it was by then. A call without a snapshot fails before the yes with the call that names
    // the note as it is now; that call goes on to ask.
    [TestCase("all", true)]
    [TestCase("none", false)]
    public async Task ANoteTrashYesIsAskedForASnapshot(string aids, bool hint)
    {
        using IDisposable setting = ModelAids.Use(aids);
        using TemporaryDirectory temporary = new();
        var store = new LocalNoteStore(Path.Combine(temporary.Path, "notes"));
        NoteRecord note = store.Create("Ideas", "x");
        var handler = new TrashNoteHandler(store);

        InvocationPreflightResult byTitle = await Preflight(handler, Json("""{"title":"ideas"}"""), CancellationToken.None);
        InvocationPreflightResult byId = await Preflight(handler, Json($$"""{"noteId":"{{note.Id:D}}"}"""),
            CancellationToken.None);
        JsonElement call = byTitle.Failure!.Result!.Value.GetProperty("call");
        InvocationPreflightResult snapshot = await Preflight(handler, call, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(byTitle.Failure.ErrorCode, Is.EqualTo("note_trash_snapshot_required"));
            Assert.That(byTitle.Failure.EffectMayHaveOccurred, Is.False);
            Assert.That(byId.Failure?.ErrorCode, Is.EqualTo("note_trash_snapshot_required"));
            Assert.That(call.GetProperty("noteId").GetString(), Is.EqualTo(note.Id.ToString("D")));
            Assert.That(call.GetProperty("expectedTitle").GetString(), Is.EqualTo("Ideas"));
            Assert.That(call.GetProperty("expectedRevision").GetInt64(), Is.EqualTo(note.Revision));
            Assert.That(call.GetProperty("expectedIsTrashed").GetBoolean(), Is.False);
            Assert.That(byTitle.Failure.Result!.Value.TryGetProperty("next", out _), Is.EqualTo(hint));
            Assert.That(snapshot, Is.SameAs(InvocationPreflightResult.Proceed));
            Assert.That(store.Read(note.Id).IsTrashed, Is.False);
        });
    }

    // Renew al máximo (w9): a note changed after its yes (edited) is not trashed: the confirmed call's read and the run
    // both say note_selection_stale with the note as it is now, and the note stays where it was.
    [Test]
    public async Task ANoteChangedAfterItsYesIsNotTrashed()
    {
        using TemporaryDirectory temporary = new();
        var store = new LocalNoteStore(Path.Combine(temporary.Path, "notes"));
        NoteRecord note = store.Create("Ideas", "x");
        var handler = new TrashNoteHandler(store);
        string snapshot = $$"""{"noteId":"{{note.Id:D}}","expectedTitle":"Ideas","expectedRevision":{{note.Revision}},"expectedIsTrashed":false}""";
        InvocationPreflightResult asked = await Preflight(handler, Json(snapshot), CancellationToken.None);
        NoteRecord edited = store.UpdateSelected(new NoteSelection(note.Id, "Ideas", note.Revision, false), "Ideas", "y");

        InvocationPreflightResult confirmed = await Preflight(handler, Json(snapshot), CancellationToken.None);
        OperationOutcome run = await handler.ExecuteAsync(Invocation(snapshot), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(asked, Is.SameAs(InvocationPreflightResult.Proceed));
            Assert.That(confirmed.Failure?.ErrorCode, Is.EqualTo("note_selection_stale"));
            Assert.That(run.ErrorCode, Is.EqualTo("note_selection_stale"));
            Assert.That(run.EffectMayHaveOccurred, Is.False);
            Assert.That(run.Result!.Value.GetProperty("note").GetProperty("revision").GetInt64(),
                Is.EqualTo(edited.Revision));
            Assert.That(store.Read(note.Id).IsTrashed, Is.False);
        });
    }

    // A confirmed note.trash already run (its note one revision on, in the trash) is read as that run, not as stale.
    [Test]
    public async Task ANoteTrashAlreadyRunIsNotReadAsStale()
    {
        using TemporaryDirectory temporary = new();
        var store = new LocalNoteStore(Path.Combine(temporary.Path, "notes"));
        NoteRecord note = store.Create("Ideas", "x");
        var handler = new TrashNoteHandler(store);
        string snapshot = $$"""{"noteId":"{{note.Id:D}}","expectedTitle":"Ideas","expectedRevision":{{note.Revision}},"expectedIsTrashed":false}""";
        OperationOutcome first = await handler.ExecuteAsync(Invocation(snapshot), CancellationToken.None);

        InvocationPreflightResult again = await Preflight(handler, Json(snapshot), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(first.Succeeded, Is.True);
            Assert.That(again, Is.SameAs(InvocationPreflightResult.Proceed));
        });
    }

    private sealed class TemporaryDirectory : IDisposable
    {
        internal string Path { get; } = System.IO.Path.Combine(
            System.IO.Path.GetTempPath(), "baxy-task-note-facts-" + Guid.NewGuid().ToString("N"));

        internal TemporaryDirectory() => Directory.CreateDirectory(Path);

        public void Dispose()
        {
            try { Directory.Delete(Path, recursive: true); }
            catch (IOException) { }
            catch (UnauthorizedAccessException) { }
        }
    }

    // Read through the interface the engine reads a handler by.
    private static ValueTask<InvocationPreflightResult> Preflight(
        object handler, JsonElement arguments, CancellationToken cancellationToken) =>
        ((IInvocationPreflight)handler).PreflightAsync(arguments, cancellationToken);

    private static JsonElement Json(string text) => JsonDocument.Parse(text).RootElement.Clone();

    private static OperationInvocation Invocation(string arguments) =>
        new("request", "mission", "invocation", Json(arguments));
}
