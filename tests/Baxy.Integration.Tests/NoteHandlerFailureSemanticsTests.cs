using System.Text.Json;
using Baxy.Contracts;
using Baxy.Core.Operations;
using Baxy.Kernel.Journal;
using Baxy.Kernel.Mission;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Notes;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class NoteHandlerFailureSemanticsTests
{
    [TestCase("note.trash", true, 2L)]
    [TestCase("note.restore", false, 3L)]
    public async Task TitleMutationRecoversAfterEffectWhenJournalCompletionFails(
        string operation,
        bool expectedTrashed,
        long expectedRevision)
    {
        string root = Path.Combine(
            Path.GetTempPath(),
            "baxy-note-completion-failure",
            Guid.NewGuid().ToString("N"));
        try
        {
            var store = new LocalNoteStore(Path.Combine(root, "store"));
            NoteRecord created = store.Create("Compras", "pan");
            if (string.Equals(operation, "note.restore", StringComparison.Ordinal))
            {
                _ = store.Trash(created.Id);
            }

            IOperationHandler handler = string.Equals(operation, "note.trash", StringComparison.Ordinal)
                ? new TrashNoteHandler(store)
                : new RestoreNoteHandler(store);
            using var journal = new FailFirstCompletionJournal();
            using var engine = new MissionEngine(new OperationRegistry([handler]), journal);
            OperationRequest request = CreateRequest(operation, "{\"title\":\"compras\"}");

            Assert.That(
                async () => await engine.ExecuteAsync(request, CancellationToken.None),
                Throws.TypeOf<IOException>());

            NoteRecord afterInterruptedCompletion = store.Read(created.Id, includeTrashed: true);
            OperationResponse recovered = await engine.ExecuteAsync(
                request with { RequestId = Guid.NewGuid().ToString("D") },
                CancellationToken.None);
            OperationResponse replay = await engine.ExecuteAsync(
                request with { RequestId = Guid.NewGuid().ToString("D") },
                CancellationToken.None);
            NoteRecord final = store.Read(created.Id, includeTrashed: true);

            Assert.Multiple(() =>
            {
                Assert.That(afterInterruptedCompletion.IsTrashed, Is.EqualTo(expectedTrashed));
                Assert.That(afterInterruptedCompletion.Revision, Is.EqualTo(expectedRevision));
                Assert.That(recovered.Status, Is.EqualTo(OperationStatuses.Completed));
                Assert.That(recovered.Replayed, Is.False);
                Assert.That(recovered.Result?.GetProperty("revision").GetInt64(), Is.EqualTo(expectedRevision));
                Assert.That(replay.Replayed, Is.True);
                Assert.That(final, Is.EqualTo(afterInterruptedCompletion));
            });
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
    public async Task MutatingStorageFailureRemainsIncompleteForSameIdentityRecovery()
    {
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(
            new OperationRegistry([new CreateNoteHandler(new CorruptNoteStore())]),
            journal);
        OperationRequest request = CreateRequest(
            "note.create",
            "{\"title\":\"Compras\",\"content\":\"pan\"}");

        Assert.That(
            async () => await engine.ExecuteAsync(request, CancellationToken.None),
            Throws.TypeOf<NoteCorruptionException>());

        string? started = await journal.FindStartedFingerprintAsync(
            request.InvocationId,
            CancellationToken.None);
        CompletedInvocation? completed = await journal.FindCompletedAsync(
            request.InvocationId,
            CancellationToken.None);
        Assert.Multiple(() =>
        {
            Assert.That(started, Is.EqualTo(RequestFingerprint.Compute(request)));
            Assert.That(completed, Is.Null);
        });
    }

    [Test]
    public async Task ReadOnlyStorageFailureIsAReplayableTerminalResponse()
    {
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(
            new OperationRegistry([new ListNotesHandler(new CorruptNoteStore())]),
            journal);
        OperationRequest request = CreateRequest("note.list", "{}");

        OperationResponse response = await engine.ExecuteAsync(request, CancellationToken.None);
        OperationResponse replay = await engine.ExecuteAsync(
            request with { RequestId = Guid.NewGuid().ToString("D") },
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(response.Status, Is.EqualTo(OperationStatuses.Failed));
            Assert.That(response.ErrorCode, Is.EqualTo("note_integrity_failed"));
            Assert.That(replay.Replayed, Is.True);
            Assert.That(replay.ErrorCode, Is.EqualTo("note_integrity_failed"));
        });
    }

    private static OperationRequest CreateRequest(string operation, string arguments) =>
        new(
            ProtocolTypes.OperationRequest,
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            operation,
            JsonDocument.Parse(arguments).RootElement.Clone());

    private sealed class CorruptNoteStore : INoteStore
    {
        public NoteRecord Create(string title, string content, string? idempotencyKey = null) =>
            throw Failure();

        public NoteRecord Read(Guid id, bool includeTrashed = false) => throw Failure();

        public NoteRecord ReadExactTitle(string title) => throw Failure();

        public NoteRecord ReadSelected(NoteSelection selection) => throw Failure();

        public NoteRecord UpdateSelected(NoteSelection selection, string title, string content) =>
            throw Failure();

        public IReadOnlyList<NoteRecord> List(NoteListScope scope = NoteListScope.Active) =>
            throw Failure();

        public NotePage ListPage(NoteListScope scope, int limit, int offset) => throw Failure();

        public IReadOnlyList<NoteSummaryRecord> Search(string query, bool includeTrashed, int limit) =>
            throw Failure();

        public NoteRecord Trash(Guid id) => throw Failure();

        public NoteRecord TrashExactTitle(string title) => throw Failure();

        public NoteRecord TrashSelected(NoteSelection selection) => throw Failure();

        public NoteRecord Restore(Guid id) => throw Failure();

        public NoteRecord RestoreExactTitle(string title) => throw Failure();

        public NoteRecord RestoreSelected(NoteSelection selection) => throw Failure();

        private static NoteCorruptionException Failure() => new("simulated unreadable committed note");
    }

    private sealed class FailFirstCompletionJournal : IInvocationJournal, IDisposable
    {
        private readonly InMemoryInvocationJournal _inner = new();
        private int _completionFailuresRemaining = 1;

        public ValueTask<string?> FindStartedFingerprintAsync(
            string invocationId,
            CancellationToken cancellationToken) =>
            _inner.FindStartedFingerprintAsync(invocationId, cancellationToken);

        public ValueTask<CompletedInvocation?> FindCompletedAsync(
            string invocationId,
            CancellationToken cancellationToken) =>
            _inner.FindCompletedAsync(invocationId, cancellationToken);

        public ValueTask RecordStartedAsync(
            OperationRequest request,
            string requestFingerprint,
            CancellationToken cancellationToken) =>
            _inner.RecordStartedAsync(request, requestFingerprint, cancellationToken);

        public ValueTask RecordCompletedAsync(
            OperationRequest request,
            string requestFingerprint,
            OperationResponse response,
            CancellationToken cancellationToken)
        {
            if (Interlocked.Exchange(ref _completionFailuresRemaining, 0) == 1)
            {
                throw new IOException("simulated interruption before journal completion");
            }

            return _inner.RecordCompletedAsync(
                request,
                requestFingerprint,
                response,
                cancellationToken);
        }

        public void Dispose() => _inner.Dispose();
    }
}
