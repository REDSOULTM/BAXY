using Baxy.Providers.Windows.Filesystem;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// BAXY Renew agent tools (2026-10-15): the real Windows Recycle Bin takes the version file.write replaces, and a
/// folder filesystem.known.trash.named deletes. It leaves a small file named baxy-recycle-live.txt and a small folder
/// named baxy-recycle-live in the person's Recycle Bin, so it runs only when asked.
/// </summary>
[TestFixture]
[Explicit("Sends a small file and a small folder to the person's Recycle Bin.")]
[Category("LiveDesktop")]
public sealed class WindowsRecycleBinLiveCheck
{
    [Test]
    public void TheVersionAWriteReplacesGoesToTheRecycleBin()
    {
        if (Environment.GetEnvironmentVariable("BAXY_RECYCLE_LIVE_CHECK") != "1")
            Assert.Ignore("BAXY_RECYCLE_LIVE_CHECK=1 is needed to use the Recycle Bin.");
        string folder = Path.Combine(Path.GetTempPath(), "baxy-recycle-live-" + Guid.NewGuid().ToString("N"));
        try
        {
            var provider = new LocalFilesystemProvider(folder);
            FilesystemMutationResult first = provider.WriteText("baxy-recycle-live.txt", "primera versión", null);
            FilesystemMutationResult second = provider.WriteText("baxy-recycle-live.txt", "segunda versión", first.Sha256);

            Assert.Multiple(() =>
            {
                Assert.That(second.PreviousVersionRecycled, Is.True);
                Assert.That(File.ReadAllText(Path.Combine(folder, "baxy-recycle-live.txt")), Is.EqualTo("segunda versión"));
                Assert.That(Directory.GetFiles(folder), Has.Length.EqualTo(1));
            });
        }
        finally
        {
            if (Directory.Exists(folder)) Directory.Delete(folder, recursive: true);
        }
    }

    [Test]
    public void AFolderGoesToTheRecycleBinWhole()
    {
        if (Environment.GetEnvironmentVariable("BAXY_RECYCLE_LIVE_CHECK") != "1")
            Assert.Ignore("BAXY_RECYCLE_LIVE_CHECK=1 is needed to use the Recycle Bin.");
        string parent = Path.Combine(Path.GetTempPath(), "baxy-recycle-live-" + Guid.NewGuid().ToString("N"));
        string folder = Path.Combine(parent, "baxy-recycle-live");
        try
        {
            Directory.CreateDirectory(Path.Combine(folder, "sub"));
            File.WriteAllText(Path.Combine(folder, "sub", "a.txt"), "dentro");

            bool recycled = WindowsRecycleBin.Instance.Recycle(folder);

            Assert.Multiple(() =>
            {
                Assert.That(recycled, Is.True);
                Assert.That(Directory.Exists(folder), Is.False);
                Assert.That(Directory.GetFileSystemEntries(parent), Is.Empty);
            });
        }
        finally
        {
            if (Directory.Exists(parent)) Directory.Delete(parent, recursive: true);
        }
    }
}
