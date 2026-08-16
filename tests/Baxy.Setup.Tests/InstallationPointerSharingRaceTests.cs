using NUnit.Framework;

namespace Baxy.Setup.Tests;

/// <summary>
/// Another process holding the current pointer open is exactly what antivirus
/// and indexers do for short windows. These tests pin the real contract, which
/// is not what the retry budget around File.Replace suggests on its own: the
/// operation reads the pointer before it ever reaches the guarded swap, and that
/// read is not retried, so a lock of any duration aborts the whole operation.
/// It aborts cleanly, which is what matters: the version already in use stays in
/// use, no half-applied pointer is left, and the update succeeds once the lock
/// clears.
/// </summary>
[TestFixture]
public sealed class InstallationPointerSharingRaceTests
{
    [Test]
    public void PointerLockAbortsTheOperationAndTheUpdateSucceedsOnceItClears()
    {
        using TemporaryDirectory temporary = new();
        InstallationEngine engine = new(temporary.InstallationRoot);
        _ = engine.InstallOrUpdate(
            new MemoryStream(TestProductPackageFactory.Create("1.0.0", "a")));

        string pointer = Path.Combine(temporary.InstallationRoot, "current");
        using (FileStream exclusive = new(
            pointer, FileMode.Open, FileAccess.Read, FileShare.None))
        {
            // The failure surfaces from the initial pointer read, before the
            // retry budget around File.Replace is ever reached.
            Assert.Throws<IOException>(() => engine.InstallOrUpdate(
                new MemoryStream(TestProductPackageFactory.Create("1.1.0", "b"))));

            Assert.Multiple(() =>
            {
                Assert.That(
                    File.Exists(Path.Combine(temporary.InstallationRoot, "current.next")),
                    Is.False);
                Assert.That(
                    File.Exists(Path.Combine(temporary.InstallationRoot, "current.rollback")),
                    Is.False);
            });
        }

        InstallationResult updated = engine.InstallOrUpdate(
            new MemoryStream(TestProductPackageFactory.Create("1.1.0", "b")));

        Assert.Multiple(() =>
        {
            Assert.That(updated.Disposition, Is.EqualTo(InstallationDisposition.Updated));
            Assert.That(engine.GetCurrentVersion(), Is.EqualTo("1.1.0"));
            Assert.That(
                File.Exists(Path.Combine(temporary.InstallationRoot, "current.next")),
                Is.False);
            Assert.That(
                File.Exists(Path.Combine(temporary.InstallationRoot, "current.rollback")),
                Is.False);
        });
    }

    [Test]
    public void PermanentSharingViolationFailsWithoutStrandingThePointer()
    {
        using TemporaryDirectory temporary = new();
        InstallationEngine engine = new(temporary.InstallationRoot);
        _ = engine.InstallOrUpdate(
            new MemoryStream(TestProductPackageFactory.Create("1.0.0", "a")));

        string pointer = Path.Combine(temporary.InstallationRoot, "current");
        using (FileStream exclusive = new(
            pointer, FileMode.Open, FileAccess.Read, FileShare.None))
        {
            Assert.Throws<IOException>(() => engine.InstallOrUpdate(
                new MemoryStream(TestProductPackageFactory.Create("1.1.0", "b"))));
        }

        // The version that was already active must still be the active one, and
        // the failed attempt must leave a state the next run can recover from
        // rather than a pointer that names nothing.
        Assert.Multiple(() =>
        {
            Assert.That(File.Exists(pointer), Is.True);
            Assert.That(
                File.Exists(Path.Combine(temporary.InstallationRoot, "current.rollback")),
                Is.False);
        });

        InstallationEngine recovered = new(temporary.InstallationRoot);
        Assert.That(recovered.GetCurrentVersion(), Is.EqualTo("1.0.0"));
    }

    private sealed class TemporaryDirectory : IDisposable
    {
        internal TemporaryDirectory()
        {
            Path = System.IO.Path.Combine(
                System.IO.Path.GetTempPath(),
                "baxy-setup-sharing-tests",
                Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(Path);
            InstallationRoot = System.IO.Path.Combine(Path, "install");
        }

        internal string Path { get; }

        internal string InstallationRoot { get; }

        public void Dispose()
        {
            // These tests deliberately hold handles on the installation tree, and
            // Windows releases them a moment after the owning thread ends, so the
            // teardown retries instead of failing a passing test.
            for (int attempt = 0; attempt < 50; attempt++)
            {
                if (!Directory.Exists(Path))
                {
                    return;
                }

                try
                {
                    Directory.Delete(Path, recursive: true);
                    return;
                }
                catch (IOException)
                {
                    Thread.Sleep(20);
                }
                catch (UnauthorizedAccessException)
                {
                    Thread.Sleep(20);
                }
            }
        }
    }
}
