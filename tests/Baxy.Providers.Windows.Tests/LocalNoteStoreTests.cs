using System.Globalization;
using System.Text;
using Baxy.Providers.Windows.Notes;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

[TestFixture]
public sealed class LocalNoteStoreTests
{
    [Test]
    public void UpdateSelectedUsesOptimisticRevisionAndSafeReachedStateReplay()
    {
        using TemporaryDirectory temporary = new();
        var store = new LocalNoteStore(Path.Combine(temporary.Path, "store"));
        NoteRecord created = store.Create("Original", "uno");
        var selection = new NoteSelection(created.Id, created.Title, created.Revision, false);

        NoteRecord updated = store.UpdateSelected(selection, "Renombrada", "dos");
        NoteRecord replayed = store.UpdateSelected(selection, "Renombrada", "dos");

        Assert.Multiple(() =>
        {
            Assert.That(updated.Revision, Is.EqualTo(2));
            Assert.That(updated.Title, Is.EqualTo("Renombrada"));
            Assert.That(updated.Content, Is.EqualTo("dos"));
            Assert.That(replayed, Is.EqualTo(updated));
            Assert.That(store.Read(created.Id), Is.EqualTo(updated));
            Assert.That(
                () => store.UpdateSelected(selection, "Otra", "dos"),
                Throws.TypeOf<NoteSelectionStaleException>());
        });
    }

    [Test]
    public void SearchFindsTitleOrContentAndOmitsTrashUnlessRequested()
    {
        using TemporaryDirectory temporary = new();
        var store = new LocalNoteStore(Path.Combine(temporary.Path, "store"));
        NoteRecord title = store.Create("Proyecto Atlas", "pendientes");
        NoteRecord content = store.Create("Ideas", "revisar atlas mañana");
        store.Trash(content.Id);

        IReadOnlyList<NoteSummaryRecord> active = store.Search("ATLAS", false, 10);
        IReadOnlyList<NoteSummaryRecord> all = store.Search("atlas", true, 10);

        Assert.Multiple(() =>
        {
            Assert.That(active.Select(static item => item.Id), Is.EqualTo(new[] { title.Id }));
            Assert.That(all.Select(static item => item.Id), Is.EquivalentTo(new[] { title.Id, content.Id }));
            Assert.That(all.Single(item => item.Id == content.Id).IsTrashed, Is.True);
        });
    }

    [Test]
    public void CreateReadAndListSurviveAStoreRestart()
    {
        using TemporaryDirectory temporary = new();
        string storeRoot = Path.Combine(temporary.Path, "private-notes");
        LocalNoteStore firstStore = new(storeRoot);

        NoteRecord created = firstStore.Create("  Reunión 🧭  ", "línea uno\nlínea dos");

        Assert.Multiple(() =>
        {
            Assert.That(created.Id, Is.Not.EqualTo(Guid.Empty));
            Assert.That(created.Title, Is.EqualTo("Reunión 🧭"));
            Assert.That(created.Content, Is.EqualTo("línea uno\nlínea dos"));
            Assert.That(created.CreatedAtUtc.Offset, Is.EqualTo(TimeSpan.Zero));
            Assert.That(created.UpdatedAtUtc, Is.EqualTo(created.CreatedAtUtc));
            Assert.That(created.Revision, Is.EqualTo(1));
            Assert.That(created.IsTrashed, Is.False);
        });

        LocalNoteStore restartedStore = new(storeRoot);
        NoteRecord read = restartedStore.Read(created.Id);
        IReadOnlyList<NoteRecord> listed = restartedStore.List();

        Assert.That(read, Is.EqualTo(created));
        Assert.That(listed, Is.EqualTo(new[] { created }));

        string primaryPath = GetPrimaryPath(storeRoot, created.Id);
        string json = File.ReadAllText(primaryPath, new UTF8Encoding(false, true));
        Assert.That(json, Does.Contain("\"title\""));
        Assert.That(
            File.ReadAllBytes(primaryPath).Take(3),
            Is.Not.EqualTo(new byte[] { 0xEF, 0xBB, 0xBF }));
    }

    [Test]
    public void TrashAndRestoreUseAReversibleTombstone()
    {
        using TemporaryDirectory temporary = new();
        SequenceTimeProvider clock = new(
            DateTimeOffset.Parse("2026-07-14T12:00:00Z", CultureInfo.InvariantCulture),
            TimeSpan.FromSeconds(1));
        LocalNoteStore store = new(Path.Combine(temporary.Path, "store"), clock);
        NoteRecord created = store.Create("Pendiente", "reservar hora");

        NoteRecord trashed = store.Trash(created.Id);
        NoteRecord replayedTrash = store.Trash(created.Id);

        Assert.Multiple(() =>
        {
            Assert.That(trashed.IsTrashed, Is.True);
            Assert.That(trashed.Revision, Is.EqualTo(2));
            Assert.That(trashed.Title, Is.EqualTo(created.Title));
            Assert.That(trashed.Content, Is.EqualTo(created.Content));
            Assert.That(replayedTrash, Is.EqualTo(trashed));
            Assert.That(store.List(), Is.Empty);
            Assert.That(store.List(NoteListScope.Trashed), Is.EqualTo(new[] { trashed }));
            Assert.That(() => store.Read(created.Id), Throws.TypeOf<NoteNotFoundException>());
            Assert.That(store.Read(created.Id, includeTrashed: true), Is.EqualTo(trashed));
        });

        NoteRecord restored = store.Restore(created.Id);
        NoteRecord replayedRestore = store.Restore(created.Id);

        Assert.Multiple(() =>
        {
            Assert.That(restored.IsTrashed, Is.False);
            Assert.That(restored.Revision, Is.EqualTo(3));
            Assert.That(restored.Title, Is.EqualTo(created.Title));
            Assert.That(restored.Content, Is.EqualTo(created.Content));
            Assert.That(replayedRestore, Is.EqualTo(restored));
            Assert.That(store.Read(created.Id), Is.EqualTo(restored));
        });
    }

    [Test]
    public void ExactTitleSelectorsNormalizeUnicodeCaseAndWhitespaceAcrossARestart()
    {
        using TemporaryDirectory temporary = new();
        string storeRoot = Path.Combine(temporary.Path, "store");
        LocalNoteStore store = new(storeRoot);
        NoteRecord created = store.Create("Café Central", "reservar mesa");

        NoteRecord read = store.ReadExactTitle("  CAFE\u0301 CENTRAL  ");
        NoteRecord trashed = store.TrashExactTitle("cafe\u0301 central");

        Assert.Multiple(() =>
        {
            Assert.That(read, Is.EqualTo(created));
            Assert.That(trashed.Id, Is.EqualTo(created.Id));
            Assert.That(trashed.IsTrashed, Is.True);
            Assert.That(
                () => store.ReadExactTitle("Café Central"),
                Throws.TypeOf<NoteTitleNotFoundException>()
                    .With.Property(nameof(NoteTitleNotFoundException.Scope)).EqualTo(NoteListScope.Active));
        });

        LocalNoteStore restarted = new(storeRoot);
        NoteRecord restored = restarted.RestoreExactTitle("CAFÉ CENTRAL");

        Assert.Multiple(() =>
        {
            Assert.That(restored.Id, Is.EqualTo(created.Id));
            Assert.That(restored.IsTrashed, Is.False);
            Assert.That(restored.Revision, Is.EqualTo(3));
            Assert.That(restarted.ReadExactTitle("café central"), Is.EqualTo(restored));
        });
    }

    [Test]
    public void ExactTitleAmbiguityFailsClosedAcrossLifecycleStates()
    {
        using TemporaryDirectory temporary = new();
        LocalNoteStore store = new(Path.Combine(temporary.Path, "store"));
        NoteRecord first = store.Create("Compras", "pan");
        NoteRecord second = store.Create("COMPRAS", "leche");

        Assert.Multiple(() =>
        {
            Assert.That(
                () => store.ReadExactTitle("compras"),
                Throws.TypeOf<NoteTitleAmbiguousException>()
                    .With.Property(nameof(NoteTitleAmbiguousException.Scope)).EqualTo(NoteListScope.Active)
                    .And.Property(nameof(NoteTitleAmbiguousException.MatchCount)).EqualTo(2));
            Assert.That(
                () => store.TrashExactTitle("compras"),
                Throws.TypeOf<NoteTitleAmbiguousException>());
            Assert.That(store.Read(first.Id), Is.EqualTo(first));
            Assert.That(store.Read(second.Id), Is.EqualTo(second));
        });

        NoteRecord firstTrashed = store.Trash(first.Id);

        Assert.Multiple(() =>
        {
            Assert.That(firstTrashed.Id, Is.EqualTo(first.Id));
            Assert.That(store.Read(second.Id), Is.EqualTo(second));
            Assert.That(
                () => store.TrashExactTitle(" compras "),
                Throws.TypeOf<NoteTitleAmbiguousException>()
                    .With.Property(nameof(NoteTitleAmbiguousException.Scope)).EqualTo(NoteListScope.All)
                    .And.Property(nameof(NoteTitleAmbiguousException.MatchCount)).EqualTo(2));
            Assert.That(
                () => store.RestoreExactTitle("compras"),
                Throws.TypeOf<NoteTitleAmbiguousException>()
                    .With.Property(nameof(NoteTitleAmbiguousException.Scope)).EqualTo(NoteListScope.All)
                    .And.Property(nameof(NoteTitleAmbiguousException.MatchCount)).EqualTo(2));
            Assert.That(store.Read(first.Id, includeTrashed: true), Is.EqualTo(firstTrashed));
            Assert.That(store.Read(second.Id), Is.EqualTo(second));
        });
    }

    [Test]
    public void AmbiguityCarriesBoundedNaturalCandidatesInStableOrderWithoutMutation()
    {
        using TemporaryDirectory temporary = new();
        SequenceTimeProvider clock = new(
            DateTimeOffset.Parse("2026-07-14T12:00:00Z", CultureInfo.InvariantCulture),
            TimeSpan.FromSeconds(1));
        LocalNoteStore store = new(Path.Combine(temporary.Path, "store"), clock);
        NoteRecord older = store.Create(
            "Duplicada",
            "  primera\n\t" + string.Concat(Enumerable.Repeat("🧭", 100)));
        NoteRecord newer = store.Create("DUPLICADA", "segunda opción");
        NoteRecord moved = store.Trash(older.Id);

        NoteTitleAmbiguousException? exception = Assert.Throws<NoteTitleAmbiguousException>(
            () => store.RestoreExactTitle("duplicada"));

        Assert.That(exception, Is.Not.Null);
        NoteAmbiguityCandidate[] candidates = exception!.Candidates.ToArray();
        Assert.Multiple(() =>
        {
            Assert.That(exception.Scope, Is.EqualTo(NoteListScope.All));
            Assert.That(candidates, Has.Length.EqualTo(2));
            Assert.That(candidates.Select(static candidate => candidate.Id),
                Is.EqualTo(new[] { moved.Id, newer.Id }));
            Assert.That(candidates[0].Title, Is.EqualTo(moved.Title));
            Assert.That(candidates[0].ContentPreview, Does.StartWith("primera "));
            Assert.That(
                Encoding.UTF8.GetByteCount(candidates[0].ContentPreview),
                Is.LessThanOrEqualTo(LocalNoteStore.MaximumContentPreviewUtf8Bytes));
            Assert.That(candidates[0].Revision, Is.EqualTo(moved.Revision));
            Assert.That(candidates[0].IsTrashed, Is.True);
            Assert.That(candidates[1].ContentPreview, Is.EqualTo("segunda opción"));
            Assert.That(candidates[1].IsTrashed, Is.False);
            Assert.That(store.Read(moved.Id, includeTrashed: true), Is.EqualTo(moved));
            Assert.That(store.Read(newer.Id), Is.EqualTo(newer));
        });
    }

    [Test]
    public void AmbiguityBreaksEqualTimestampTiesByUuid()
    {
        using TemporaryDirectory temporary = new();
        SequenceTimeProvider clock = new(
            DateTimeOffset.Parse("2026-07-14T12:00:00Z", CultureInfo.InvariantCulture),
            TimeSpan.Zero);
        LocalNoteStore store = new(Path.Combine(temporary.Path, "store"), clock);
        NoteRecord first = store.Create("Igual", "uno");
        NoteRecord second = store.Create("IGUAL", "dos");

        NoteTitleAmbiguousException? exception = Assert.Throws<NoteTitleAmbiguousException>(
            () => store.ReadExactTitle("igual"));

        Assert.That(
            exception!.Candidates.Select(static candidate => candidate.Id),
            Is.EqualTo(new[] { first.Id, second.Id }.Order()));
    }

    [Test]
    public void SnapshotSelectionIsAtomicStaleSafeAndReconcilesReachedMutations()
    {
        using TemporaryDirectory temporary = new();
        string root = Path.Combine(temporary.Path, "store");
        LocalNoteStore store = new(root);
        NoteRecord created = store.Create("Elegida", "contenido");
        var activeSelection = new NoteSelection(
            created.Id,
            created.Title,
            created.Revision,
            ExpectedIsTrashed: false);

        NoteRecord read = store.ReadSelected(activeSelection);
        NoteRecord trashed = store.TrashSelected(activeSelection);
        LocalNoteStore restarted = new(root);
        NoteRecord reconciledTrash = restarted.TrashSelected(activeSelection);
        var trashedSelection = new NoteSelection(
            trashed.Id,
            trashed.Title,
            trashed.Revision,
            ExpectedIsTrashed: true);
        Assert.That(
            () => restarted.ReadSelected(trashedSelection),
            Throws.TypeOf<NoteSelectionStaleException>());
        NoteRecord restored = restarted.RestoreSelected(trashedSelection);
        NoteRecord reconciledRestore = restarted.RestoreSelected(trashedSelection);

        Assert.Multiple(() =>
        {
            Assert.That(read, Is.EqualTo(created));
            Assert.That(trashed.Revision, Is.EqualTo(created.Revision + 1));
            Assert.That(trashed.IsTrashed, Is.True);
            Assert.That(reconciledTrash, Is.EqualTo(trashed));
            Assert.That(restored.Revision, Is.EqualTo(trashed.Revision + 1));
            Assert.That(restored.IsTrashed, Is.False);
            Assert.That(reconciledRestore, Is.EqualTo(restored));
            Assert.That(
                () => restarted.ReadSelected(activeSelection),
                Throws.TypeOf<NoteSelectionStaleException>());
            Assert.That(
                () => restarted.TrashSelected(activeSelection with { ExpectedTitle = "ELEGIDA" }),
                Throws.TypeOf<NoteSelectionStaleException>());
            Assert.That(restarted.Read(created.Id), Is.EqualTo(restored));
        });
    }

    [Test]
    public void InvalidOrStaleSnapshotCannotChangeTheStoredRevision()
    {
        using TemporaryDirectory temporary = new();
        LocalNoteStore store = new(Path.Combine(temporary.Path, "store"));
        NoteRecord created = store.Create("Segura", "contenido");
        var stale = new NoteSelection(
            created.Id,
            created.Title,
            created.Revision + 5,
            ExpectedIsTrashed: false);

        Assert.Multiple(() =>
        {
            Assert.That(() => store.TrashSelected(stale), Throws.TypeOf<NoteSelectionStaleException>());
            Assert.That(
                () => store.RestoreSelected(stale with { ExpectedRevision = 0 }),
                Throws.TypeOf<NoteValidationException>());
            Assert.That(store.Read(created.Id), Is.EqualTo(created));
        });
    }

    [Test]
    public void ExactTitleMutationsReplayTheReachedStateWithoutAnotherRevision()
    {
        using TemporaryDirectory temporary = new();
        LocalNoteStore store = new(Path.Combine(temporary.Path, "store"));
        NoteRecord created = store.Create("Pendiente", "reservar hora");

        NoteRecord trashed = store.TrashExactTitle("pendiente");
        NoteRecord replayedTrash = store.TrashExactTitle("PENDIENTE");
        NoteRecord restored = store.RestoreExactTitle(" pendiente ");
        NoteRecord replayedRestore = store.RestoreExactTitle("Pendiente");

        Assert.Multiple(() =>
        {
            Assert.That(trashed.Id, Is.EqualTo(created.Id));
            Assert.That(trashed.Revision, Is.EqualTo(2));
            Assert.That(replayedTrash, Is.EqualTo(trashed));
            Assert.That(restored.Revision, Is.EqualTo(3));
            Assert.That(replayedRestore, Is.EqualTo(restored));
            Assert.That(store.List(NoteListScope.All), Is.EqualTo(new[] { restored }));
        });
    }

    [Test]
    public void ExactTitleSelectorsReuseBoundedTextValidation()
    {
        using TemporaryDirectory temporary = new();
        LocalNoteStore store = new(Path.Combine(temporary.Path, "store"));
        _ = store.Create("Válida", "contenido");
        string oversized = new('a', LocalNoteStore.MaximumTitleUtf8Bytes + 1);

        Assert.Multiple(() =>
        {
            Assert.That(() => store.ReadExactTitle(""), Throws.TypeOf<NoteValidationException>());
            Assert.That(() => store.TrashExactTitle("mal\nformado"), Throws.TypeOf<NoteValidationException>());
            Assert.That(() => store.RestoreExactTitle("nul\0title"), Throws.TypeOf<NoteValidationException>());
            Assert.That(() => store.ReadExactTitle(oversized), Throws.TypeOf<NoteValidationException>());
            Assert.That(store.List(), Has.Count.EqualTo(1));
        });
    }

    [Test]
    public void CreateReplaysAnIdempotencyKeyWithoutDuplicatingTheNote()
    {
        using TemporaryDirectory temporary = new();
        LocalNoteStore store = new(Path.Combine(temporary.Path, "store"));

        NoteRecord first = store.Create("Bitácora", "entrada", "mission-007");
        NoteRecord replay = store.Create("Bitácora", "entrada", " mission-007 ");

        Assert.Multiple(() =>
        {
            Assert.That(replay, Is.EqualTo(first));
            Assert.That(store.List(NoteListScope.All), Has.Count.EqualTo(1));
            Assert.That(
                () => store.Create("Bitácora", "contenido distinto", "mission-007"),
                Throws.TypeOf<NoteConflictException>());
        });

        LocalNoteStore restarted = new(Path.Combine(temporary.Path, "store"));
        Assert.That(restarted.Create("Bitácora", "entrada", "mission-007"), Is.EqualTo(first));
    }

    [Test]
    public void TextValidationRejectsDangerousControlsAndUtf8Overflow()
    {
        using TemporaryDirectory temporary = new();
        LocalNoteStore store = new(Path.Combine(temporary.Path, "store"));

        Assert.Multiple(() =>
        {
            Assert.That(() => store.Create("", "content"), Throws.TypeOf<NoteValidationException>());
            Assert.That(() => store.Create("line\nbreak", "content"), Throws.TypeOf<NoteValidationException>());
            Assert.That(() => store.Create("nul\0title", "content"), Throws.TypeOf<NoteValidationException>());
            Assert.That(() => store.Create("title", "bell\u0007content"), Throws.TypeOf<NoteValidationException>());
            Assert.That(
                () => store.Create(new string('a', LocalNoteStore.MaximumTitleUtf8Bytes + 1), "content"),
                Throws.TypeOf<NoteValidationException>());
            Assert.That(
                () => store.Create(
                    "title",
                    new string('a', LocalNoteStore.MaximumContentUtf8Bytes + 1)),
                Throws.TypeOf<NoteValidationException>());
            Assert.That(() => store.Create("title", "tabs\tand\nlines are allowed"), Throws.Nothing);
        });
    }

    [Test]
    public void CorruptPrimaryRecoversTheLastValidRevisionFromBackup()
    {
        using TemporaryDirectory temporary = new();
        string storeRoot = Path.Combine(temporary.Path, "store");
        LocalNoteStore store = new(storeRoot);
        NoteRecord created = store.Create("Recuperable", "contenido");
        _ = store.Trash(created.Id);
        string primaryPath = GetPrimaryPath(storeRoot, created.Id);
        File.WriteAllText(primaryPath, "{truncated", new UTF8Encoding(false));

        LocalNoteStore restarted = new(storeRoot);
        NoteRecord recovered = restarted.Read(created.Id, includeTrashed: true);

        Assert.Multiple(() =>
        {
            Assert.That(recovered, Is.EqualTo(created));
            Assert.That(restarted.Read(created.Id), Is.EqualTo(created));
            Assert.That(File.Exists(primaryPath + ".bak"), Is.False);
            Assert.That(Directory.GetFiles(Path.Combine(storeRoot, "notes"), "*.tmp"), Is.Empty);
        });
    }

    [Test]
    public void CorruptOnlyCopyFailsClosed()
    {
        using TemporaryDirectory temporary = new();
        string storeRoot = Path.Combine(temporary.Path, "store");
        LocalNoteStore store = new(storeRoot);
        NoteRecord created = store.Create("Irrecuperable", "contenido");
        File.WriteAllText(GetPrimaryPath(storeRoot, created.Id), "{}", new UTF8Encoding(false));

        Assert.That(
            () => new LocalNoteStore(storeRoot).Read(created.Id, includeTrashed: true),
            Throws.TypeOf<NoteCorruptionException>());
    }

    [Test]
    public void StartupRemovesAnAbandonedAtomicWriteWithoutChangingValidData()
    {
        using TemporaryDirectory temporary = new();
        string storeRoot = Path.Combine(temporary.Path, "store");
        LocalNoteStore store = new(storeRoot);
        NoteRecord created = store.Create("Persistente", "contenido");
        string abandoned = Path.Combine(
            storeRoot,
            "notes",
            ".baxy-note-11111111111111111111111111111111.tmp");
        File.WriteAllText(abandoned, "partial", new UTF8Encoding(false));

        LocalNoteStore restarted = new(storeRoot);

        Assert.Multiple(() =>
        {
            Assert.That(File.Exists(abandoned), Is.False);
            Assert.That(restarted.Read(created.Id), Is.EqualTo(created));
        });
    }

    [Test]
    public void TraversalInTheConfiguredRootIsRejectedAndCannotTouchSiblingData()
    {
        using TemporaryDirectory temporary = new();
        string outside = Path.Combine(temporary.Path, "outside");
        Directory.CreateDirectory(outside);
        string sentinel = Path.Combine(outside, "sentinel.txt");
        File.WriteAllText(sentinel, "unchanged", new UTF8Encoding(false));
        string traversingRoot = Path.Combine(temporary.Path, "private", "..", "outside");

        Assert.That(() => new LocalNoteStore(traversingRoot), Throws.TypeOf<UnsafeNoteStorePathException>());
        Assert.That(File.ReadAllText(sentinel, Encoding.UTF8), Is.EqualTo("unchanged"));
        Assert.That(Directory.GetFiles(outside), Is.EqualTo(new[] { sentinel }));
    }

    [Test]
    public void UncRootIsRejectedBeforeAnyNetworkPathIsInspected()
    {
        Assert.That(
            () => new LocalNoteStore(@"\\server.invalid\share\baxy"),
            Throws.TypeOf<UnsafeNoteStorePathException>());
    }

    [Test]
    public void NoteTextCannotControlAFileNameOrEscapeTheStore()
    {
        using TemporaryDirectory temporary = new();
        string storeRoot = Path.Combine(temporary.Path, "store");
        LocalNoteStore store = new(storeRoot);

        NoteRecord created = store.Create("..\\..\\owned.json", "safe");

        string[] noteFiles = Directory.GetFiles(Path.Combine(storeRoot, "notes"), "*.json");
        Assert.Multiple(() =>
        {
            Assert.That(noteFiles, Is.EqualTo(new[] { GetPrimaryPath(storeRoot, created.Id) }));
            Assert.That(File.Exists(Path.Combine(temporary.Path, "owned.json")), Is.False);
        });
    }

    [Test]
    public void MultipleStoreInstancesSerializeConcurrentCreates()
    {
        using TemporaryDirectory temporary = new();
        string storeRoot = Path.Combine(temporary.Path, "store");
        LocalNoteStore first = new(storeRoot);
        LocalNoteStore second = new(storeRoot);

        Task<NoteRecord>[] creates = Enumerable.Range(0, 24)
            .Select(index => Task.Run(
                () => (index & 1) == 0
                    ? first.Create($"note {index}", "content")
                    : second.Create($"note {index}", "content")))
            .ToArray();
        Task.WaitAll(creates);

        NoteRecord[] records = creates.Select(static task => task.Result).ToArray();
        Assert.Multiple(() =>
        {
            Assert.That(records.Select(static note => note.Id).Distinct().Count(), Is.EqualTo(24));
            Assert.That(first.List(), Has.Count.EqualTo(24));
            Assert.That(Directory.GetFiles(Path.Combine(storeRoot, "notes"), "*.tmp"), Is.Empty);
        });
    }

    [Test]
    public void ConcurrentReplaysOfOneIdempotencyKeyCreateExactlyOneNote()
    {
        using TemporaryDirectory temporary = new();
        string storeRoot = Path.Combine(temporary.Path, "store");
        LocalNoteStore first = new(storeRoot);
        LocalNoteStore second = new(storeRoot);

        Task<NoteRecord>[] creates = Enumerable.Range(0, 16)
            .Select(index => Task.Run(
                () => (index & 1) == 0
                    ? first.Create("Bitacora", "entrada concurrente", "mission-shared")
                    : second.Create("Bitacora", "entrada concurrente", "mission-shared")))
            .ToArray();
        Task.WaitAll(creates);

        NoteRecord[] records = creates.Select(static task => task.Result).ToArray();
        Assert.Multiple(() =>
        {
            Assert.That(records.Select(static note => note.Id).Distinct().Count(), Is.EqualTo(1));
            Assert.That(records, Has.All.EqualTo(records[0]));
            Assert.That(first.List(NoteListScope.All), Is.EqualTo(new[] { records[0] }));
            Assert.That(
                () => second.Create("Bitacora", "contenido en conflicto", "mission-shared"),
                Throws.TypeOf<NoteConflictException>());
        });
    }

    [Test]
    public void PostCommitReadLockIsReconciledWithoutInvitingADuplicate()
    {
        using TemporaryDirectory temporary = new();
        string storeRoot = Path.Combine(temporary.Path, "store");
        FileStream? postCommitLock = null;
        LocalNoteStore store = new(
            storeRoot,
            timeProvider: null,
            afterNewDocumentCommitted: path =>
            {
                postCommitLock = new FileStream(
                    path,
                    FileMode.Open,
                    FileAccess.ReadWrite,
                    FileShare.None);
            });

        NoteRecord created;
        LocalNoteStore? restarted = null;
        try
        {
            created = store.Create("Una sola", "efecto confirmado", "stable-invocation");
            restarted = new LocalNoteStore(storeRoot);
            Assert.That(
                () => restarted.Create("Una sola", "efecto confirmado", "stable-invocation"),
                Throws.TypeOf<NoteCorruptionException>());
        }
        finally
        {
            postCommitLock?.Dispose();
        }

        Assert.That(restarted, Is.Not.Null);
        NoteRecord replay = restarted!.Create("Una sola", "efecto confirmado", "stable-invocation");
        Assert.Multiple(() =>
        {
            Assert.That(replay, Is.EqualTo(created));
            Assert.That(restarted.List(NoteListScope.All), Is.EqualTo(new[] { created }));
        });
    }

    [Test]
    public void ProviderPaginationOmitsContentAndCapacityBoundsMaximumWork()
    {
        using TemporaryDirectory temporary = new();
        SequenceTimeProvider clock = new(
            DateTimeOffset.Parse("2026-07-14T12:00:00Z", CultureInfo.InvariantCulture),
            TimeSpan.FromSeconds(1));
        LocalNoteStore store = new(
            Path.Combine(temporary.Path, "store"),
            clock,
            afterNewDocumentCommitted: null,
            maximumStoredNotes: 4);
        string maximumContent = new('x', LocalNoteStore.MaximumContentUtf8Bytes);
        NoteRecord first = store.Create("Nota 0", maximumContent, "key-0");
        _ = store.Create("Nota 1", maximumContent, "key-1");
        _ = store.Create("Nota 2", maximumContent, "key-2");
        _ = store.Create("Nota 3", maximumContent, "key-3");

        NotePage page = store.ListPage(NoteListScope.All, limit: 2, offset: 1);
        NoteRecord replayAtCapacity = store.Create("Nota 0", maximumContent, "key-0");

        Assert.Multiple(() =>
        {
            Assert.That(page.TotalCount, Is.EqualTo(4));
            Assert.That(page.Limit, Is.EqualTo(2));
            Assert.That(page.Offset, Is.EqualTo(1));
            Assert.That(page.Notes.Select(static note => note.Title), Is.EqualTo(new[] { "Nota 2", "Nota 1" }));
            Assert.That(page.Notes, Has.All.InstanceOf<NoteSummaryRecord>());
            Assert.That(replayAtCapacity, Is.EqualTo(first));
            Assert.That(
                () => store.Create("Nota 4", maximumContent, "key-4"),
                Throws.TypeOf<NoteCapacityException>());
            Assert.That(
                () => store.ListPage(NoteListScope.All, LocalNoteStore.MaximumListPageSize + 1, 0),
                Throws.TypeOf<ArgumentOutOfRangeException>());
            Assert.That(
                () => store.ListPage(NoteListScope.All, 1, -1),
                Throws.TypeOf<ArgumentOutOfRangeException>());
        });
    }

    [Test]
    public void ReparsePointRootIsRejectedWhenThePlatformAllowsCreatingOne()
    {
        using TemporaryDirectory temporary = new();
        string target = Path.Combine(temporary.Path, "target");
        string link = Path.Combine(temporary.Path, "linked-store");
        Directory.CreateDirectory(target);

        _ = Baxy.Tests.NtfsTestJunction.Create(link, target);

        try
        {
            Assert.That(() => new LocalNoteStore(link), Throws.TypeOf<UnsafeNoteStorePathException>());
            Assert.That(Directory.GetFileSystemEntries(target), Is.Empty);
        }
        finally
        {
            Directory.Delete(link);
        }
    }

    [Test]
    public void ReparsePointDocumentIsRejectedWithoutReadingItsTarget()
    {
        using TemporaryDirectory temporary = new();
        string storeRoot = Path.Combine(temporary.Path, "store");
        LocalNoteStore store = new(storeRoot);
        Guid linkedId = Guid.NewGuid();
        string outside = Path.Combine(temporary.Path, "outside");
        string sentinelPath = Path.Combine(outside, "sentinel.txt");
        string link = GetPrimaryPath(storeRoot, linkedId);
        const string sentinel = "outside sentinel";
        Directory.CreateDirectory(outside);
        File.WriteAllText(sentinelPath, sentinel, new UTF8Encoding(false));
        _ = Baxy.Tests.NtfsTestJunction.Create(link, outside);

        try
        {
            Assert.That(() => store.Read(linkedId), Throws.TypeOf<UnsafeNoteStorePathException>());
            Assert.That(File.ReadAllText(sentinelPath, Encoding.UTF8), Is.EqualTo(sentinel));
        }
        finally
        {
            Directory.Delete(link);
        }
    }

    private static string GetPrimaryPath(string storeRoot, Guid id) =>
        Path.Combine(storeRoot, "notes", id.ToString("D", CultureInfo.InvariantCulture) + ".json");

    private sealed class SequenceTimeProvider : TimeProvider
    {
        private readonly TimeSpan _step;
        private DateTimeOffset _next;

        public SequenceTimeProvider(DateTimeOffset start, TimeSpan step)
        {
            _next = start;
            _step = step;
        }

        public override DateTimeOffset GetUtcNow()
        {
            DateTimeOffset current = _next;
            _next = _next.Add(_step);
            return current;
        }
    }

    private sealed class TemporaryDirectory : IDisposable
    {
        public TemporaryDirectory()
        {
            Path = System.IO.Path.Combine(
                System.IO.Path.GetTempPath(),
                "baxy-notes-tests",
                Guid.NewGuid().ToString("N", CultureInfo.InvariantCulture));
            Directory.CreateDirectory(Path);
        }

        public string Path { get; }

        public void Dispose()
        {
            if (Directory.Exists(Path))
            {
                Directory.Delete(Path, recursive: true);
            }
        }
    }
}
