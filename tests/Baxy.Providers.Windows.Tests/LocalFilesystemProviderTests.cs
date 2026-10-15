using System.Globalization;
using System.Text;
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

    [Test]
    public void TrashRequiresPreparedExactLabelAndCanRestore()
    {
        using TemporaryDirectory temporary = new();
        var provider = new LocalFilesystemProvider(temporary.Path);
        string id = provider.WriteText("borrar.txt", "contenido", null).ResourceId;
        FilesystemTrashPreparation prepared = provider.PrepareTrash(id);
        FilesystemTrashReceipt receipt = provider.CommitTrash(prepared.TrashId, prepared.ReviewLabel);
        FilesystemMutationResult restored = provider.Restore(receipt.RestoreId);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Trashed, Is.True);
            Assert.That(restored.Name, Is.EqualTo("borrar.txt"));
            Assert.That(File.Exists(Path.Combine(temporary.Path, "borrar.txt")), Is.True);
        });
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
        var provider = new LocalFilesystemProvider(sandbox, bin);

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
