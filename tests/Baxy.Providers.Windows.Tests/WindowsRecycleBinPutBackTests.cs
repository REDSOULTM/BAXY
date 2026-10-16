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
