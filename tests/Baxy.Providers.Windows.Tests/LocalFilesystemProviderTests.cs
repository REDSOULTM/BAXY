using System.Globalization;
using System.Text;
using Baxy.Providers.Windows.Filesystem;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

[TestFixture]
public sealed class LocalFilesystemProviderTests
{
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

    [Test]
    public void ExistingWriteRequiresExactHashAndReachedStateIsSafe()
    {
        using TemporaryDirectory temporary = new();
        var provider = new LocalFilesystemProvider(temporary.Path);
        FilesystemMutationResult first = provider.WriteText("dato.txt", "uno", null);
        FilesystemMutationResult replay = provider.WriteText("dato.txt", "uno", null);

        Assert.Multiple(() =>
        {
            Assert.That(replay.ReachedState, Is.True);
            Assert.That(
                () => provider.WriteText("dato.txt", "dos", new string('0', 64)),
                Throws.TypeOf<FilesystemProviderException>()
                    .With.Property(nameof(FilesystemProviderException.Code)).EqualTo("version_conflict"));
            Assert.That(provider.WriteText("dato.txt", "dos", first.Sha256).Sha256,
                Is.Not.EqualTo(first.Sha256));
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
