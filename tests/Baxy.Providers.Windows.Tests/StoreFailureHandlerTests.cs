using System.Reflection;
using System.Text.Json;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Notes;
using Baxy.Providers.Windows.Tasks;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Revisión 2026-10-22 (C-1): a full store, or a disk that fails a write, is the operation's failure, named; it used to
/// throw past the handler and end baxy-core (exit 70). A full store refuses before any effect; a write that failed may
/// have begun.
/// </summary>
[TestFixture]
public sealed class StoreFailureHandlerTests
{
    [Test]
    public async Task AFullTaskStoreRefusesTheTaskBeforeAnyEffect()
    {
        OperationOutcome outcome = await new CreateTaskHandler(Throwing<ILocalTaskStore>(new NoteCapacityException(10_000)))
            .ExecuteAsync(Invocation("""{"title":"Comprar pan"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo("task_capacity_reached"));
            Assert.That(outcome.EffectMayHaveOccurred, Is.False);
        });
    }

    [Test]
    public async Task AFailedTaskWriteIsNamedAndMayHaveBegun()
    {
        OperationOutcome outcome = await new CreateTaskHandler(Throwing<ILocalTaskStore>(new IOException("disk")))
            .ExecuteAsync(Invocation("""{"title":"Comprar pan"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("storage_failed"));
            Assert.That(outcome.EffectMayHaveOccurred, Is.True);
        });
    }

    [Test]
    public async Task AFailedNoteWriteIsNamedAndMayHaveBegun()
    {
        OperationOutcome outcome = await new CreateNoteHandler(Throwing<INoteStore>(new UnauthorizedAccessException("guarded")))
            .ExecuteAsync(Invocation("""{"title":"Compras","content":"pan"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("storage_failed"));
            Assert.That(outcome.EffectMayHaveOccurred, Is.True);
        });
    }

    // Contracase: a read that failed changed nothing.
    [Test]
    public async Task AFailedTaskReadChangedNothing()
    {
        OperationOutcome outcome = await new ListTasksHandler(Throwing<ILocalTaskStore>(new IOException("disk")))
            .ExecuteAsync(Invocation("{}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("storage_failed"));
            Assert.That(outcome.EffectMayHaveOccurred, Is.False);
        });
    }

    // Auditoría del Core (w8): a corrupt store or an unsafe store path met by a change ended the core (exit 70); it is
    // the operation's failure, named, and may have begun.
    [Test]
    public async Task ACorruptNoteMetByANoteCreateIsNamedAndMayHaveBegun()
    {
        OperationOutcome outcome = await new CreateNoteHandler(Throwing<INoteStore>(new NoteCorruptionException("bad note")))
            .ExecuteAsync(Invocation("""{"title":"Compras","content":"pan"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo("note_integrity_failed"));
            Assert.That(outcome.EffectMayHaveOccurred, Is.True);
        });
    }

    [Test]
    public async Task AnUnsafeNoteStoreMetByANoteUpdateIsNamedAndMayHaveBegun()
    {
        OperationOutcome outcome = await new UpdateNoteHandler(Throwing<INoteStore>(new UnsafeNoteStorePathException("link")))
            .ExecuteAsync(Invocation($$"""
                {"noteId":"{{Guid.NewGuid():D}}","expectedTitle":"Compras","expectedRevision":1,"title":"Compras","content":"pan"}
                """), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("unsafe_storage"));
            Assert.That(outcome.EffectMayHaveOccurred, Is.True);
        });
    }

    [Test]
    public async Task ATaskPayloadThatDoesNotReadBackMetByACompletionIsNamedAndMayHaveBegun()
    {
        OperationOutcome outcome = await new CompleteTaskHandler(
                Throwing<ILocalTaskStore>(new LocalTaskStoreException("Authenticated task payload is invalid.")))
            .ExecuteAsync(Invocation($$"""{"taskId":"{{Guid.NewGuid():D}}","expectedVersion":1}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("task_integrity_failed"));
            Assert.That(outcome.EffectMayHaveOccurred, Is.True);
        });
    }

    // Contracase: the same met by a read changed nothing; an unsafe store read no longer ends the core either.
    [Test]
    public async Task AnUnsafeTaskStoreMetByAListChangedNothing()
    {
        OperationOutcome outcome = await new ListTasksHandler(Throwing<ILocalTaskStore>(new UnsafeNoteStorePathException("link")))
            .ExecuteAsync(Invocation("{}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("unsafe_storage"));
            Assert.That(outcome.EffectMayHaveOccurred, Is.False);
        });
    }

    private static OperationInvocation Invocation(string arguments) =>
        new("request", "mission", "invocation", JsonDocument.Parse(arguments).RootElement.Clone());

    private static T Throwing<T>(Exception exception) where T : class
    {
        T store = DispatchProxy.Create<T, ThrowingStore>();
        ((ThrowingStore)(object)store).Failure = exception;
        return store;
    }

    // Every call to the store fails with the same exception.
    public class ThrowingStore : DispatchProxy
    {
        internal Exception Failure { get; set; } = new InvalidOperationException();

        protected override object? Invoke(MethodInfo? targetMethod, object?[]? args) => throw Failure;
    }
}
