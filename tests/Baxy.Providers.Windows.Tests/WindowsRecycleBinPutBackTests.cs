using Baxy.Providers.Windows.Filesystem;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// BAXY Renew (notebook), ronda B: when the bin does not take a file (it left its place but the bin did not grow), the
/// copy that waited hidden beside it goes back with the attributes the person's file had, never hidden. A stand-in bin
/// here: the shell is never called.
/// </summary>
[TestFixture]
public sealed class WindowsRecycleBinPutBackTests
{
    // A bin that deletes what it is given (read-only or not, as the shell does) and never grows: the drive without a
    // bin, or the file too large for it.
    private static WindowsRecycleBin BinThatLoses() => new(path =>
    {
        if (Directory.Exists(path)) Directory.Delete(path, recursive: true);
        else
        {
            File.SetAttributes(path, FileAttributes.Normal);
            File.Delete(path);
        }
        return 0;
    }, _ => 3);

    // A bin that takes it: what it is given leaves and the bin grows by one.
    private static WindowsRecycleBin BinThatTakes()
    {
        long items = 3;
        return new(path =>
        {
            File.SetAttributes(path, FileAttributes.Normal);
            File.Delete(path);
            items++;
            return 0;
        }, _ => items);
    }

    // The file left its place and the call threw before anything put it back: the copy is all that is left of it, so
    // it stays, visible, with its content; it is never deleted with nothing in the bin or in its place.
    [Test]
    public void WhenNeitherTheBinNorItsPlaceHoldsTheFileTheCopyStays()
    {
        using TemporaryDirectory temporary = new();
        string file = Path.Combine(temporary.Path, "nota.txt");
        File.WriteAllText(file, "contenido");
        var bin = new WindowsRecycleBin(path =>
        {
            File.Delete(path);
            throw new IOException("the shell failed after the file left");
        }, _ => 3);

        Assert.That(() => bin.Recycle(file), Throws.TypeOf<IOException>());

        string[] left = Directory.GetFiles(temporary.Path);
        Assert.Multiple(() =>
        {
            Assert.That(left, Has.Length.EqualTo(1));
            Assert.That(File.ReadAllText(left[0]), Is.EqualTo("contenido"));
            Assert.That(File.GetAttributes(left[0]).HasFlag(FileAttributes.Hidden), Is.False);
        });
    }

    // FT/proveedores goal (review of receipts): a folder whose copy is cut short by a locked file inside: the bin is never
    // asked, the folder stays as it was, and no partial copy is left beside it.
    [Test]
    public void AFolderCopyCutShortLeavesNoPartialCopy()
    {
        using TemporaryDirectory temporary = new();
        string folder = Path.Combine(temporary.Path, "proyecto");
        Directory.CreateDirectory(folder);
        File.WriteAllText(Path.Combine(folder, "a.txt"), "uno");
        string locked = Path.Combine(folder, "b.txt");
        File.WriteAllText(locked, "dos");
        bool asked = false;
        var bin = new WindowsRecycleBin(_ => { asked = true; return 0; }, _ => 3);

        using (new FileStream(locked, FileMode.Open, FileAccess.ReadWrite, FileShare.None))
        {
            Assert.That(() => bin.Recycle(folder), Throws.InstanceOf<IOException>());
        }

        Assert.Multiple(() =>
        {
            Assert.That(asked, Is.False);
            Assert.That(Directory.GetFileSystemEntries(temporary.Path), Is.EqualTo(new[] { folder }));
            Assert.That(Directory.GetFiles(folder), Has.Length.EqualTo(2));
        });
    }

    [Test]
    public void AReadOnlyFileTheBinTookLeavesNoCopyBehind()
    {
        using TemporaryDirectory temporary = new();
        string file = Path.Combine(temporary.Path, "nota.txt");
        File.WriteAllText(file, "contenido");
        File.SetAttributes(file, FileAttributes.ReadOnly);

        bool recycled = BinThatTakes().Recycle(file);

        Assert.Multiple(() =>
        {
            Assert.That(recycled, Is.True);
            Assert.That(Directory.GetFileSystemEntries(temporary.Path), Is.Empty);
        });
    }

    [Test]
    public void AFileTheBinLostComesBackNotHidden()
    {
        using TemporaryDirectory temporary = new();
        string file = Path.Combine(temporary.Path, "nota.txt");
        File.WriteAllText(file, "contenido");
        File.SetAttributes(file, FileAttributes.ReadOnly | FileAttributes.Archive);

        bool recycled = BinThatLoses().Recycle(file);

        FileAttributes after = File.GetAttributes(file);
        File.SetAttributes(file, FileAttributes.Normal);
        Assert.Multiple(() =>
        {
            Assert.That(recycled, Is.False);
            Assert.That(after, Is.EqualTo(FileAttributes.ReadOnly | FileAttributes.Archive));
            Assert.That(File.ReadAllText(file), Is.EqualTo("contenido"));
            Assert.That(Directory.GetFileSystemEntries(temporary.Path), Is.EqualTo(new[] { file }));
        });
    }

    [Test]
    public void AFolderTheBinLostComesBackWithEachFoldersOwnAttributes()
    {
        using TemporaryDirectory temporary = new();
        string folder = Path.Combine(temporary.Path, "carpeta");
        string visible = Path.Combine(folder, "visible");
        string hidden = Path.Combine(folder, "oculta");
        Directory.CreateDirectory(visible);
        Directory.CreateDirectory(hidden);
        File.WriteAllText(Path.Combine(visible, "a.txt"), "a");
        File.SetAttributes(hidden, File.GetAttributes(hidden) | FileAttributes.Hidden);

        bool recycled = BinThatLoses().Recycle(folder);

        Assert.Multiple(() =>
        {
            Assert.That(recycled, Is.False);
            Assert.That(File.GetAttributes(folder).HasFlag(FileAttributes.Hidden), Is.False);
            Assert.That(File.GetAttributes(visible).HasFlag(FileAttributes.Hidden), Is.False);
            Assert.That(File.GetAttributes(hidden).HasFlag(FileAttributes.Hidden), Is.True);
            Assert.That(File.ReadAllText(Path.Combine(visible, "a.txt")), Is.EqualTo("a"));
            Assert.That(Directory.GetFileSystemEntries(temporary.Path), Is.EqualTo(new[] { folder }));
        });
    }

    private sealed class TemporaryDirectory : IDisposable
    {
        public TemporaryDirectory()
        {
            Path = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "baxy-recycle-putback-tests", Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(Path);
        }
        public string Path { get; }
        public void Dispose() { if (Directory.Exists(Path)) Directory.Delete(Path, recursive: true); }
    }
}
