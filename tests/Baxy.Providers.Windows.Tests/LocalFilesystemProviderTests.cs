using System.Globalization;
using System.Text;
using System.Text.Json;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Filesystem;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

[TestFixture]
public sealed class LocalFilesystemProviderTests
{
    [Test]
    public void SearchDistinguishesUnsupportedAbsolutePathsFromEmptyNameSearches()
    {
        using TemporaryDirectory temporary = new();
        string sandbox = Path.Combine(temporary.Path, "sandbox");
        var provider = new LocalFilesystemProvider(sandbox);
        provider.WriteText("same.txt", "inside", null);
        string outside = Path.Combine(temporary.Path, "same.txt");
        File.WriteAllText(outside, "outside");
        string[] absolutePaths =
        [
            outside,
            outside.Replace('\\', '/'),
            Path.Combine(sandbox, "same.txt"),
            Path.Combine(temporary.Path, "absent.txt"),
            @"\\server\share\same.txt",
        ];

        Assert.Multiple(() =>
        {
            foreach (string path in absolutePaths)
            {
                Assert.That(() => provider.Search(path, 10),
                    Throws.TypeOf<FilesystemProviderException>()
                        .With.Property(nameof(FilesystemProviderException.Code))
                        .EqualTo("absolute_path_search_unsupported"), path);
            }

            FilesystemEntry match = provider.Search("SAME.txt", 10).Entries.Single();
            Assert.That(provider.ReadText(match.ResourceId, 100).Text, Is.EqualTo("inside"));
            Assert.That(provider.Search("absent.txt", 10).Count, Is.Zero);
            Assert.That(File.ReadAllText(outside), Is.EqualTo("outside"));
        });
    }

    [Test]
    public void ListReadWriteAndTransferUseOpaqueRevalidatedResources()
    {
        using TemporaryDirectory temporary = new();
        var provider = new LocalFilesystemProvider(temporary.Path);
        FilesystemMutationResult written = provider.WriteText("entrada.txt", "hola", null);
        FilesystemListResult listed = provider.List(string.Empty, 10);
        string resourceId = listed.Entries.Single().ResourceId;
        FilesystemTextResult read = provider.ReadText(resourceId, 100);
        FilesystemMutationResult copied = provider.Transfer(
            resourceId, "copias/salida.txt", read.Sha256, move: false);

        Assert.Multiple(() =>
        {
            Assert.That(written.ResourceId, Does.Match("^fs_[0-9a-f]{32}$"));
            Assert.That(read.Text, Is.EqualTo("hola"));
            Assert.That(copied.Sha256, Is.EqualTo(read.Sha256));
            Assert.That(File.ReadAllText(
                Path.Combine(temporary.Path, "copias", "salida.txt"), Encoding.UTF8), Is.EqualTo("hola"));
        });
    }

    // file.write (BAXY Renew agent tools): replacing takes the exact current hash and sends the previous version to
    // the Recycle Bin first (a stand-in bin here; WindowsRecycleBinLiveCheck uses the real one).
    [Test]
    public void ExistingWriteRequiresExactHashRecyclesThePreviousVersionAndReachedStateIsSafe()
    {
        using TemporaryDirectory temporary = new();
        var bin = new KnownFileToolsTests.FolderRecycleBin(Path.Combine(temporary.Path, "bin"));
        var provider = new LocalFilesystemProvider(Path.Combine(temporary.Path, "sandbox"), bin);
        FilesystemMutationResult first = provider.WriteText("dato.txt", "uno", null);
        FilesystemMutationResult replay = provider.WriteText("dato.txt", "uno", null);

        Assert.Multiple(() =>
        {
            Assert.That(first.PreviousVersionRecycled, Is.False);
            Assert.That(replay.ReachedState, Is.True);
            Assert.That(replay.PreviousVersionRecycled, Is.False);
            Assert.That(provider.Hash(replay.ResourceId).Sha256, Is.EqualTo(first.Sha256));
            Assert.That(
                () => provider.WriteText("dato.txt", "dos", new string('0', 64)),
                Throws.TypeOf<FilesystemProviderException>()
                    .With.Property(nameof(FilesystemProviderException.Code)).EqualTo("version_conflict"));
            Assert.That(
                () => provider.WriteText("dato.txt", "dos", null),
                Throws.TypeOf<FilesystemProviderException>()
                    .With.Property(nameof(FilesystemProviderException.Code)).EqualTo("version_conflict"));
            Assert.That(bin.Recycled, Is.Empty);
            FilesystemMutationResult replaced = provider.WriteText("dato.txt", "dos", first.Sha256);
            Assert.That(replaced.Sha256, Is.Not.EqualTo(first.Sha256));
            Assert.That(replaced.PreviousVersionRecycled, Is.True);
            Assert.That(bin.Recycled.Select(File.ReadAllText), Is.EqualTo(new[] { "uno" }));
            Assert.That(File.ReadAllText(Path.Combine(temporary.Path, "sandbox", "dato.txt")), Is.EqualTo("dos"));
        });
    }

    [Test]
    public void AReplaceTheBinCannotTakeChangesNothing()
    {
        using TemporaryDirectory temporary = new();
        var bin = new KnownFileToolsTests.FolderRecycleBin(Path.Combine(temporary.Path, "bin"), accepts: false);
        string sandbox = Path.Combine(temporary.Path, "sandbox");
        var provider = new LocalFilesystemProvider(sandbox, bin);
        FilesystemMutationResult first = provider.WriteText("dato.txt", "uno", null);

        Assert.Multiple(() =>
        {
            Assert.That(
                () => provider.WriteText("dato.txt", "dos", first.Sha256),
                Throws.TypeOf<FilesystemProviderException>()
                    .With.Property(nameof(FilesystemProviderException.Code)).EqualTo("previous_version_not_recycled"));
            Assert.That(File.ReadAllText(Path.Combine(sandbox, "dato.txt")), Is.EqualTo("uno"));
            Assert.That(Directory.GetFiles(sandbox), Is.EqualTo(new[] { Path.Combine(sandbox, "dato.txt") }));
        });
    }

    // FT/proveedores goal (review of receipts): a file another program holds open with no sharing (Excel) threw past the
    // handler and ended the core; it is file.write's failure, file_in_use, and the file is untouched.
    [Test]
    public async Task AFileHeldOpenByAnotherProgramIsInUseNotACrash()
    {
        using TemporaryDirectory temporary = new();
        var bin = new KnownFileToolsTests.FolderRecycleBin(Path.Combine(temporary.Path, "bin"));
        string sandbox = Path.Combine(temporary.Path, "sandbox");
        var provider = new LocalFilesystemProvider(sandbox, bin);
        string path = Path.Combine(sandbox, "ventas.csv");
        File.WriteAllText(path, "a;b");
        using JsonDocument arguments = JsonDocument.Parse("""{"relativePath":"ventas.csv","text":"c;d","append":true}""");

        OperationOutcome outcome;
        using (new FileStream(path, FileMode.Open, FileAccess.ReadWrite, FileShare.None))
        {
            outcome = await new FilesystemHandler("file.write", provider).ExecuteAsync(
                new OperationInvocation("r", "m", "i", arguments.RootElement.Clone()), CancellationToken.None);
        }

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo("file_in_use"));
            Assert.That(File.ReadAllText(path), Is.EqualTo("a;b"));
        });
    }

    // file.write append (it absorbed filesystem.sandbox.append.named): what is there stays, the text goes at the end
    // in the file's own encoding, no hash is needed (a given one must match), and a missing file is created.
    [Test]
    public void AppendKeepsWhatIsThereInTheFilesEncodingAndCreatesAMissingFile()
    {
        using TemporaryDirectory temporary = new();
        var bin = new KnownFileToolsTests.FolderRecycleBin(Path.Combine(temporary.Path, "bin"));
        string sandbox = Path.Combine(temporary.Path, "sandbox");
        var provider = new LocalFilesystemProvider(sandbox, bin);
        File.WriteAllText(Path.Combine(sandbox, "lista.txt"), "pan\n", new UnicodeEncoding(false, true));

        FilesystemMutationResult appended = provider.WriteText("lista.txt", "leche\n", null, append: true);
        FilesystemMutationResult created = provider.WriteText("logs/nuevo.txt", "uno\n", null, append: true);
        FilesystemMutationResult again = provider.WriteText("logs/nuevo.txt", "dos\n", created.Sha256, append: true);

        Assert.Multiple(() =>
        {
            Assert.That(File.ReadAllText(Path.Combine(sandbox, "lista.txt"), Encoding.Unicode), Is.EqualTo("pan\nleche\n"));
            Assert.That(File.ReadAllBytes(Path.Combine(sandbox, "lista.txt"))[..2], Is.EqualTo(new byte[] { 0xFF, 0xFE }));
            Assert.That(appended.PreviousVersionRecycled, Is.False);
            Assert.That(File.ReadAllText(Path.Combine(sandbox, "logs", "nuevo.txt")), Is.EqualTo("uno\ndos\n"));
            Assert.That(again.ReachedState, Is.False);
            Assert.That(
                () => provider.WriteText("logs/nuevo.txt", "tres\n", created.Sha256, append: true),
                Throws.TypeOf<FilesystemProviderException>()
                    .With.Property(nameof(FilesystemProviderException.Code)).EqualTo("version_conflict"));
            Assert.That(provider.WriteText("logs/nuevo.txt", "", null, append: true).ReachedState, Is.True);
            Assert.That(bin.Recycled, Is.Empty);
        });
    }

    // BAXY Renew (notebook): a hash expected of a file that is not there is said as that, not as another version;
    // the refusal says what it saw, and nothing is written.
    [TestCase("")]
    [TestCase("0000000000000000000000000000000000000000000000000000000000000000")]
    public async Task AWriteExpectingAHashOfAMissingFileSaysTheFileIsNotThere(string expected)
    {
        using TemporaryDirectory temporary = new();
        string sandbox = Path.Combine(temporary.Path, "sandbox");
        var provider = new LocalFilesystemProvider(sandbox);

        OperationOutcome outcome = await Handle(
            provider, "file.write",
            $$"""{"relativePath":"nuevo.txt","text":"hola","expectedSha256":"{{expected}}"}""");

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo("expected_hash_for_missing_file"));
            Assert.That(outcome.EffectMayHaveOccurred, Is.False);
            Assert.That(outcome.Result!.Value.GetProperty("exists").GetBoolean(), Is.False);
            Assert.That(outcome.Result!.Value.GetProperty("fullPath").GetString(),
                Is.EqualTo(Path.Combine(sandbox, "nuevo.txt")));
            Assert.That(outcome.Result!.Value.GetProperty("append").GetBoolean(), Is.False);
            Assert.That(File.Exists(Path.Combine(sandbox, "nuevo.txt")), Is.False);
        });
    }

    // A refused write leaves nothing behind, not even the folder a new file would have gone in (the receipt says no
    // effect happened).
    [Test]
    public async Task ARefusedWriteOfANewFileInANewFolderLeavesNoFolder()
    {
        using TemporaryDirectory temporary = new();
        string sandbox = Path.Combine(temporary.Path, "sandbox");
        var provider = new LocalFilesystemProvider(sandbox);

        OperationOutcome outcome = await Handle(
            provider, "file.write", """{"relativePath":"viaje/plan.txt","text":"hola","expectedSha256":""}""");

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("expected_hash_for_missing_file"));
            Assert.That(outcome.EffectMayHaveOccurred, Is.False);
            Assert.That(Directory.Exists(Path.Combine(sandbox, "viaje")), Is.False);
        });
    }

    [Test]
    public async Task AVersionConflictSaysTheFileIsThereAndWhere()
    {
        using TemporaryDirectory temporary = new();
        string sandbox = Path.Combine(temporary.Path, "sandbox");
        var provider = new LocalFilesystemProvider(sandbox);
        provider.WriteText("dato.txt", "uno", null);

        OperationOutcome outcome = await Handle(
            provider, "file.write", """{"relativePath":"dato.txt","text":"dos"}""");

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("version_conflict"));
            Assert.That(outcome.Result!.Value.GetProperty("exists").GetBoolean(), Is.True);
            Assert.That(outcome.Result!.Value.GetProperty("fullPath").GetString(),
                Is.EqualTo(Path.Combine(sandbox, "dato.txt")));
            Assert.That(File.ReadAllText(Path.Combine(sandbox, "dato.txt")), Is.EqualTo("uno"));
        });
    }

    // The list says which folder it read and whether its limit left entries out.
    [Test]
    public async Task AListSaysItsFolderAndWhetherTheLimitLeftEntriesOut()
    {
        using TemporaryDirectory temporary = new();
        string sandbox = Path.Combine(temporary.Path, "sandbox");
        var provider = new LocalFilesystemProvider(sandbox);
        foreach (string name in new[] { "a.txt", "b.txt", "c.txt" }) provider.WriteText("notas/" + name, name, null);

        OperationOutcome cut = await Handle(
            provider, "filesystem.list", """{"relativeDirectory":"notas","limit":2}""");
        OperationOutcome whole = await Handle(provider, "filesystem.list", """{"relativeDirectory":"notas"}""");

        Assert.Multiple(() =>
        {
            Assert.That(cut.Succeeded, Is.True, cut.ErrorCode);
            Assert.That(cut.Result!.Value.GetProperty("fullPath").GetString(), Is.EqualTo(Path.Combine(sandbox, "notas")));
            Assert.That(cut.Result!.Value.GetProperty("count").GetInt32(), Is.EqualTo(2));
            Assert.That(cut.Result!.Value.GetProperty("totalCount").GetInt32(), Is.EqualTo(3));
            Assert.That(cut.Result!.Value.GetProperty("hasMore").GetBoolean(), Is.True);
            Assert.That(whole.Result!.Value.GetProperty("count").GetInt32(), Is.EqualTo(3));
            Assert.That(whole.Result!.Value.GetProperty("hasMore").GetBoolean(), Is.False);
        });
    }

    // Round A: a read-back that did not match once the file was written, or a provider failure after its move, came
    // back as a clean failure, as if nothing had changed. It says the change may be on disk; a write whose content was
    // already there changed nothing and says so.
    [TestCase("nuevo.txt", true)]
    [TestCase("dato.txt", false)]
    public async Task AWriteWhoseReadBackDoesNotMatchSaysWhetherTheChangeMayBeOnDisk(string name, bool effectMayHaveOccurred)
    {
        using TemporaryDirectory temporary = new();
        var provider = new MisreadingProvider(new LocalFilesystemProvider(Path.Combine(temporary.Path, "sandbox")));
        provider.WriteText("dato.txt", "igual", null);

        OperationOutcome outcome = await Handle(
            provider, "file.write", $$"""{"relativePath":"{{name}}","text":"igual"}""");

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("verification_failed"));
            Assert.That(outcome.EffectMayHaveOccurred, Is.EqualTo(effectMayHaveOccurred));
        });
    }

    [Test]
    public async Task AProviderFailureAfterTheMoveReachesTheOutcomeAsAPossibleEffect()
    {
        using TemporaryDirectory temporary = new();
        var provider = new MisreadingProvider(new LocalFilesystemProvider(temporary.Path)) { TransferFailsAfterEffect = true };
        FilesystemMutationResult source = provider.WriteText("origen.txt", "dato", null);

        OperationOutcome outcome = await Handle(
            provider, "filesystem.move",
            $$"""{"resourceId":"{{source.ResourceId}}","destinationRelativePath":"destino.txt","expectedSha256":"{{source.Sha256}}"}""");

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo("verification_failed"));
            Assert.That(outcome.EffectMayHaveOccurred, Is.True);
        });
    }

    // Ronda B: a full table of handles refuses a write, a new folder, a copy and a move before anything is touched,
    // instead of after the change (it came out as a clean handle_capacity_reached with the change on disk).
    [Test]
    public void AFullTableOfHandlesRefusesBeforeTheChange()
    {
        using TemporaryDirectory temporary = new();
        var provider = new LocalFilesystemProvider(temporary.Path);
        FilesystemMutationResult source = provider.WriteText("origen.txt", "dato", null);
        for (int issued = 1; issued < 512; issued++)
            _ = provider.WriteText("origen.txt", "dato", null);

        Assert.Multiple(() =>
        {
            foreach (TestDelegate change in new TestDelegate[]
            {
                () => provider.WriteText("nuevo/escrito.txt", "dato", null),
                () => provider.CreateDirectory("carpeta", null),
                () => provider.Transfer(source.ResourceId, "copia/copia.txt", source.Sha256!, move: false),
                () => provider.Transfer(source.ResourceId, "movido/movido.txt", source.Sha256!, move: true),
            })
            {
                Assert.That(change, Throws.TypeOf<FilesystemProviderException>()
                    .With.Property(nameof(FilesystemProviderException.Code)).EqualTo("handle_capacity_reached")
                    .And.Property(nameof(FilesystemProviderException.EffectMayHaveOccurred)).False);
            }
            Assert.That(Directory.GetFileSystemEntries(temporary.Path).Select(Path.GetFileName),
                Is.EquivalentTo(new[] { "origen.txt", ".backups" }));
            Assert.That(File.ReadAllText(Path.Combine(temporary.Path, "origen.txt")), Is.EqualTo("dato"));
        });
    }

    // Ronda B: the handle of what was just written no longer resolving (the file changed or went meanwhile) says the
    // change may be on disk; a write whose content was already there changed nothing.
    [TestCase("nuevo.txt", true)]
    [TestCase("dato.txt", false)]
    public async Task AHandleThatNoLongerResolvesAfterAWriteSaysWhetherTheChangeMayBeOnDisk(string name, bool effectMayHaveOccurred)
    {
        using TemporaryDirectory temporary = new();
        var provider = new MisreadingProvider(new LocalFilesystemProvider(Path.Combine(temporary.Path, "sandbox")))
        {
            HashFailure = "resource_changed",
        };
        provider.WriteText("dato.txt", "igual", null);

        OperationOutcome outcome = await Handle(
            provider, "file.write", $$"""{"relativePath":"{{name}}","text":"igual"}""");

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("resource_changed"));
            Assert.That(outcome.EffectMayHaveOccurred, Is.EqualTo(effectMayHaveOccurred));
        });
    }

    // The real provider, except that its hash read-back never matches (or fails, or its transfer fails after moving).
    private sealed class MisreadingProvider(LocalFilesystemProvider inner) : IFilesystemProvider
    {
        internal bool TransferFailsAfterEffect { get; init; }
        internal string? HashFailure { get; init; }

        public FilesystemListResult List(string relativeDirectory, int limit) => inner.List(relativeDirectory, limit);
        public FilesystemListResult Search(string query, int limit) => inner.Search(query, limit);
        public FilesystemTextResult ReadText(string resourceId, int maximumBytes) => inner.ReadText(resourceId, maximumBytes);
        public FilesystemEntry Hash(string resourceId) => HashFailure is { } code
            ? throw new FilesystemProviderException(code)
            : inner.Hash(resourceId) with { Sha256 = new string('0', 64) };
        public FilesystemMutationResult CreateDirectory(string relativePath, string? folder) =>
            inner.CreateDirectory(relativePath, folder);
        public FilesystemMutationResult WriteText(
            string relativePath, string text, string? expectedSha256, string? folder = null, bool append = false) =>
            inner.WriteText(relativePath, text, expectedSha256, folder, append);
        public FilesystemMutationResult Transfer(
            string resourceId, string destinationRelativePath, string expectedSha256, bool move)
        {
            FilesystemMutationResult moved = inner.Transfer(resourceId, destinationRelativePath, expectedSha256, move);
            return TransferFailsAfterEffect
                ? throw new FilesystemProviderException("verification_failed") { EffectMayHaveOccurred = true }
                : moved;
        }
        public BackupReceipt CreateBackup(string resourceId, string expectedSha256) =>
            inner.CreateBackup(resourceId, expectedSha256);
        public BackupListResult ListBackups(int limit) => inner.ListBackups(limit);
        public BackupReceipt VerifyBackup(string backupId) => inner.VerifyBackup(backupId);
        public FilesystemMutationResult RestoreBackup(string backupId, string destinationRelativePath) =>
            inner.RestoreBackup(backupId, destinationRelativePath);
    }

    private static ValueTask<OperationOutcome> Handle(IFilesystemProvider provider, string operation, string arguments)
    {
        using JsonDocument document = JsonDocument.Parse(arguments);
        return new FilesystemHandler(operation, provider).ExecuteAsync(
            new OperationInvocation("request", "mission", "invocation", document.RootElement.Clone()),
            CancellationToken.None);
    }

    [Test]
    public void BackupCreateVerifyAndRestorePreserveExactHash()
    {
        using TemporaryDirectory temporary = new();
        var provider = new LocalFilesystemProvider(temporary.Path);
        FilesystemMutationResult source = provider.WriteText("origen.txt", "respaldo", null);
        BackupReceipt created = provider.CreateBackup(source.ResourceId, source.Sha256!);
        BackupReceipt verified = provider.VerifyBackup(created.BackupId);
        FilesystemMutationResult restored = provider.RestoreBackup(created.BackupId, "restaurado.txt");

        Assert.Multiple(() =>
        {
            Assert.That(verified, Is.EqualTo(created));
            Assert.That(restored.Sha256, Is.EqualTo(created.Sha256));
            Assert.That(File.ReadAllText(Path.Combine(temporary.Path, "restaurado.txt")), Is.EqualTo("respaldo"));
        });
    }

    // Auditoría final V3: «verified» compares the backup's bytes with the SHA-256 recorded when it was made; a backup
    // changed since, or one without that record, is not verified and is never restored.
    [TestCase(true)]
    [TestCase(false)]
    public void ABackupChangedSinceItWasMadeOrWithoutItsRecordedHashIsNotVerifiedNorRestored(bool changed)
    {
        using TemporaryDirectory temporary = new();
        var provider = new LocalFilesystemProvider(temporary.Path);
        FilesystemMutationResult source = provider.WriteText("origen.txt", "respaldo", null);
        BackupReceipt created = provider.CreateBackup(source.ResourceId, source.Sha256!);
        string backups = Path.Combine(temporary.Path, ".backups");
        if (changed)
        {
            File.WriteAllText(Path.Combine(backups, created.BackupId + ".bin"), "otra cosa");
        }
        else
        {
            File.Delete(Path.Combine(backups, created.BackupId + ".sha256"));
        }

        BackupReceipt verified = provider.VerifyBackup(created.BackupId);

        Assert.Multiple(() =>
        {
            Assert.That(created.Verified, Is.True);
            Assert.That(verified.Verified, Is.False);
            Assert.That(provider.ListBackups(1).Backups.Single().Verified, Is.False);
            Assert.That(() => provider.RestoreBackup(created.BackupId, "restaurado.txt"),
                Throws.TypeOf<FilesystemProviderException>()
                    .With.Property(nameof(FilesystemProviderException.Code)).EqualTo("backup_not_verified"));
            Assert.That(File.Exists(Path.Combine(temporary.Path, "restaurado.txt")), Is.False);
        });
    }

    [Test]
    public void BackupListReturnsVerifiedNewestFirstAndHonorsLimit()
    {
        using TemporaryDirectory temporary = new();
        var provider = new LocalFilesystemProvider(temporary.Path);
        FilesystemMutationResult first = provider.WriteText("uno.txt", "uno", null);
        BackupReceipt older = provider.CreateBackup(first.ResourceId, first.Sha256!);
        FilesystemMutationResult second = provider.WriteText("dos.txt", "dos", null);
        BackupReceipt newer = provider.CreateBackup(second.ResourceId, second.Sha256!);
        File.SetLastWriteTimeUtc(
            Path.Combine(temporary.Path, ".backups", older.BackupId + ".bin"),
            DateTime.UtcNow.AddMinutes(-2));
        File.SetLastWriteTimeUtc(
            Path.Combine(temporary.Path, ".backups", newer.BackupId + ".bin"),
            DateTime.UtcNow);

        BackupListResult listed = provider.ListBackups(1);

        Assert.Multiple(() =>
        {
            Assert.That(listed.Count, Is.EqualTo(1));
            Assert.That(listed.Backups.Single().BackupId, Is.EqualTo(newer.BackupId));
            Assert.That(listed.Backups.Single().Verified, Is.True);
            Assert.That(listed.Backups.Single().BackupId, Is.Not.EqualTo(older.BackupId));
        });
    }

    [TestCase("../escape.txt")]
    [TestCase("C:\\escape.txt")]
    public void AbsoluteOrEscapingDestinationsFailClosed(string path)
    {
        using TemporaryDirectory temporary = new();
        var provider = new LocalFilesystemProvider(temporary.Path);
        Assert.That(() => provider.WriteText(path, "x", null),
            Throws.TypeOf<FilesystemProviderException>());
    }

    // A full path inside the folder is the same place as its relative path; one outside it is refused before writing.
    [Test]
    public void AFullPathInsideTheFolderIsWrittenThereAndOneOutsideIsRefused()
    {
        using TemporaryDirectory temporary = new();
        var bin = new KnownFileToolsTests.FolderRecycleBin(Path.Combine(temporary.Path, "bin"));
        string sandbox = Path.Combine(temporary.Path, "sandbox");
        var provider = new LocalFilesystemProvider(sandbox, bin) { KnownFolderPath = Absent(temporary) };

        provider.WriteText(Path.Combine(sandbox, "viaje", "plan.txt"), "uno", null);

        Assert.Multiple(() =>
        {
            Assert.That(File.ReadAllText(Path.Combine(sandbox, "viaje", "plan.txt")), Is.EqualTo("uno"));
            Assert.That(
                () => provider.WriteText(Path.Combine(temporary.Path, "fuera.txt"), "dos", null),
                Throws.TypeOf<FilesystemProviderException>()
                    .With.Property(nameof(FilesystemProviderException.Code)).EqualTo("path_outside_sandbox"));
            Assert.That(File.Exists(Path.Combine(temporary.Path, "fuera.txt")), Is.False);
        });
    }

    // The refusal says what the call can do instead only where the operation takes a folder (round 1: the model wrote
    // a path of the person's without folder and read a bare path_outside_sandbox).
    [Test]
    public void APathOutsideTheWorkingFolderSaysToNameTheFolderOnlyWhereTheCallTakesOne()
    {
        using TemporaryDirectory temporary = new();
        string sandbox = Path.Combine(temporary.Path, "sandbox");
        Directory.CreateDirectory(sandbox);
        var provider = new LocalFilesystemProvider(sandbox) { KnownFolderPath = Absent(temporary) };
        string outside = Path.Combine(temporary.Path, "fuera");

        FilesystemProviderException written = Assert.Throws<FilesystemProviderException>(
            () => provider.WriteText(Path.Combine(outside, "nota.txt"), "uno", null))!;
        FilesystemProviderException created = Assert.Throws<FilesystemProviderException>(
            () => provider.CreateDirectory(outside, null))!;
        FilesystemProviderException listed = Assert.Throws<FilesystemProviderException>(
            () => provider.List(outside, 10))!;

        Assert.Multiple(() =>
        {
            Assert.That(written.Code, Is.EqualTo("path_outside_sandbox"));
            Assert.That(written.Result?.GetProperty("next").GetString(), Does.Contain("folder").And.Contain("home"));
            Assert.That(created.Result?.GetProperty("next").GetString(),
                Is.EqualTo(written.Result?.GetProperty("next").GetString()));
            Assert.That(listed.Code, Is.EqualTo("path_outside_sandbox"));
            Assert.That(listed.Result, Is.Null);
        });
    }

    // FT/proveedores goal (e2e E019): a full path with no folder that lies in a known folder of the person's is made
    // there, the subfolders included; one in no known folder is still refused, and «..» never leaves the folder.
    [Test]
    public void AFullPathWithNoFolderIsMadeInTheKnownFolderItLiesIn()
    {
        using TemporaryDirectory temporary = new();
        var bin = new KnownFileToolsTests.FolderRecycleBin(Path.Combine(temporary.Path, "bin"));
        string home = Path.Combine(temporary.Path, "home");
        Directory.CreateDirectory(Path.Combine(home, "BAXY-bench"));
        var provider = new LocalFilesystemProvider(Path.Combine(temporary.Path, "sandbox"), bin)
        {
            KnownFolderPath = folder => folder == "home" ? home : Path.Combine(temporary.Path, "absent", folder),
        };

        FilesystemMutationResult made = provider.CreateDirectory(Path.Combine(home, "BAXY-bench", "proyecto"), null);
        FilesystemMutationResult written = provider.WriteText(
            Path.Combine(home, "BAXY-bench", "compras.txt"), "pan, leche y huevos", null);

        Assert.Multiple(() =>
        {
            Assert.That(Directory.Exists(Path.Combine(home, "BAXY-bench", "proyecto")), Is.True);
            Assert.That(made.FullPath, Is.EqualTo(Path.Combine(home, "BAXY-bench", "proyecto")));
            Assert.That(File.ReadAllText(Path.Combine(home, "BAXY-bench", "compras.txt")), Is.EqualTo("pan, leche y huevos"));
            Assert.That(written.FullPath, Is.EqualTo(Path.Combine(home, "BAXY-bench", "compras.txt")));
            Assert.That(() => provider.WriteText(Path.Combine(temporary.Path, "fuera.txt"), "dos", null),
                Throws.TypeOf<FilesystemProviderException>()
                    .With.Property(nameof(FilesystemProviderException.Code)).EqualTo("path_outside_sandbox"));
            Assert.That(() => provider.WriteText(Path.Combine(home, "..", "fuera2.txt"), "tres", null),
                Throws.TypeOf<FilesystemProviderException>());
            Assert.That(() => provider.WriteText(Path.Combine(home, "a\0b.txt"), "cuatro", null),
                Throws.TypeOf<FilesystemProviderException>()
                    .With.Property(nameof(FilesystemProviderException.Code)).EqualTo("invalid_path"));
            Assert.That(File.Exists(Path.Combine(temporary.Path, "fuera.txt")), Is.False);
            Assert.That(File.Exists(Path.Combine(temporary.Path, "fuera2.txt")), Is.False);
        });
    }

    // Known folders that do not exist: a path under the test's temporary folder is in none of them.
    private static Func<string, string> Absent(TemporaryDirectory temporary) =>
        folder => Path.Combine(temporary.Path, "absent", folder);

    private sealed class TemporaryDirectory : IDisposable
    {
        public TemporaryDirectory()
        {
            Path = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "baxy-fs-tests",
                Guid.NewGuid().ToString("N", CultureInfo.InvariantCulture));
            Directory.CreateDirectory(Path);
        }
        public string Path { get; }
        public void Dispose() { if (Directory.Exists(Path)) Directory.Delete(Path, recursive: true); }
    }
}
