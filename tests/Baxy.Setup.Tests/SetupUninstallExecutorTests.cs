using System.Diagnostics;
using NUnit.Framework;

namespace Baxy.Setup.Tests;

public sealed class SetupUninstallExecutorTests
{
    [Test]
    public void TombstoneIsAUniqueCanonicalSibling()
    {
        using TemporaryTree tree = new();
        Guid identifier = Guid.ParseExact(
            "0123456789abcdef0123456789abcdef",
            "N");

        string tombstone = SetupUninstallExecutor.BuildTombstonePath(
            tree.InstallationRoot,
            identifier);

        Assert.That(
            tombstone,
            Is.EqualTo(Path.Combine(
                tree.Root,
                ".BAXY-uninstall-0123456789abcdef0123456789abcdef")));
    }

    [Test]
    public void InstallationMoveRenamesOnlyTheExactRoot()
    {
        using TemporaryTree tree = new();
        string neighbor = Path.Combine(tree.Root, "neighbor.txt");
        string installed = Path.Combine(tree.InstallationRoot, "installed.txt");
        Directory.CreateDirectory(tree.InstallationRoot);
        File.WriteAllText(installed, "installed");
        File.WriteAllText(neighbor, "neighbor");
        string tombstone = SetupUninstallExecutor.BuildTombstonePath(
            tree.InstallationRoot,
            Guid.NewGuid());

        SetupUninstallExecutor.MoveInstallationRoot(
            tree.InstallationRoot,
            tombstone);

        Assert.Multiple(() =>
        {
            Assert.That(Directory.Exists(tree.InstallationRoot), Is.False);
            Assert.That(File.ReadAllText(Path.Combine(tombstone, "installed.txt")),
                Is.EqualTo("installed"));
            Assert.That(File.ReadAllText(neighbor), Is.EqualTo("neighbor"));
        });
    }

    [Test]
    public void InstallationMoveFirstLeavesItsOwnWorkingDirectory()
    {
        using TemporaryTree tree = new();
        Directory.CreateDirectory(tree.InstallationRoot);
        File.WriteAllText(
            Path.Combine(tree.InstallationRoot, "installed.txt"),
            "installed");
        string tombstone = SetupUninstallExecutor.BuildTombstonePath(
            tree.InstallationRoot,
            Guid.NewGuid());
        string originalWorkingDirectory = Environment.CurrentDirectory;
        try
        {
            Directory.SetCurrentDirectory(tree.InstallationRoot);

            SetupUninstallExecutor.MoveInstallationRoot(
                tree.InstallationRoot,
                tombstone);

            Assert.Multiple(() =>
            {
                Assert.That(Directory.Exists(tree.InstallationRoot), Is.False);
                Assert.That(Directory.Exists(tombstone), Is.True);
                Assert.That(
                    Environment.CurrentDirectory,
                    Is.EqualTo(tree.Root).IgnoreCase);
            });
        }
        finally
        {
            Directory.SetCurrentDirectory(originalWorkingDirectory);
        }
    }

    [Test]
    public void PurgeCanDeleteDataWhenTheOriginalWorkingDirectoryWasInsideIt()
    {
        using TemporaryTree tree = new();
        string dataRoot = Path.Combine(tree.Root, "data");
        string nestedData = Path.Combine(dataRoot, "nested");
        Directory.CreateDirectory(tree.InstallationRoot);
        Directory.CreateDirectory(nestedData);
        File.WriteAllText(Path.Combine(nestedData, "sentinel.txt"), "data");
        string tombstone = SetupUninstallExecutor.BuildTombstonePath(
            tree.InstallationRoot,
            Guid.NewGuid());
        string originalWorkingDirectory = Environment.CurrentDirectory;
        try
        {
            Directory.SetCurrentDirectory(nestedData);

            SetupUninstallExecutor.MoveInstallationRoot(
                tree.InstallationRoot,
                tombstone);
            PathSafety.DeleteTreeFailClosed(tree.Root, dataRoot);

            Assert.Multiple(() =>
            {
                Assert.That(Directory.Exists(dataRoot), Is.False);
                Assert.That(Environment.CurrentDirectory, Is.EqualTo(tree.Root).IgnoreCase);
            });
        }
        finally
        {
            Directory.SetCurrentDirectory(originalWorkingDirectory);
        }
    }

    [Test]
    public void ForeignTombstoneIsRejectedBeforeMovingAnything()
    {
        using TemporaryTree tree = new();
        Directory.CreateDirectory(tree.InstallationRoot);
        string foreign = Path.Combine(tree.Root, "foreign");

        Assert.That(
            () => SetupUninstallExecutor.MoveInstallationRoot(
                tree.InstallationRoot,
                foreign),
            Throws.TypeOf<InstallationSafetyException>());
        Assert.That(Directory.Exists(tree.InstallationRoot), Is.True);
    }

    [Test]
    public void CleanupCommandUsesOnlyFixedEnvironmentVariablesForPaths()
    {
        string command = SetupUninstallExecutor.BuildCleanupCommand();

        Assert.Multiple(() =>
        {
            Assert.That(command, Does.Contain("%BAXY_UNINSTALL_TOMBSTONE%"));
            Assert.That(command, Does.Contain("%BAXY_UNINSTALL_DELAY%"));
            Assert.That(command, Does.Contain("rd /s /q"));
            Assert.That(command, Does.Contain("127.0.0.1"));
            Assert.That(command, Does.Not.Contain(Path.GetTempPath()));
        });
    }

    [Test]
    public void SystemCleanupDeletesAnUnlockedTombstone()
    {
        using TemporaryTree tree = new();
        string tombstone = SetupUninstallExecutor.BuildTombstonePath(
            tree.InstallationRoot,
            Guid.NewGuid());
        Directory.CreateDirectory(tombstone);
        File.WriteAllText(Path.Combine(tombstone, "file.txt"), "content");

        _ = SetupUninstallExecutor.LaunchTombstoneCleanup(
            tree.InstallationRoot,
            tombstone);

        Assert.That(
            WaitUntil(() => !Directory.Exists(tombstone), TimeSpan.FromSeconds(3)),
            Is.True);
    }

    [Test]
    public void SystemCleanupRetriesADeletingLockedTombstoneAndPreservesItsNeighbor()
    {
        using TemporaryTree tree = new();
        string tombstone = SetupUninstallExecutor.BuildTombstonePath(
            tree.InstallationRoot,
            Guid.NewGuid());
        string lockedFile = Path.Combine(tombstone, "locked.bin");
        string neighbor = Path.Combine(tree.Root, "neighbor.txt");
        Directory.CreateDirectory(tombstone);
        File.WriteAllText(lockedFile, "locked");
        File.WriteAllText(neighbor, "neighbor");

        uint processId;
        using (FileStream locked = new(
            lockedFile,
            FileMode.Open,
            FileAccess.Read,
            FileShare.Read))
        {
            processId = SetupUninstallExecutor.LaunchTombstoneCleanup(
                tree.InstallationRoot,
                tombstone);
            Assert.That(processId, Is.GreaterThan(0));
            Thread.Sleep(250);
            Assert.That(Directory.Exists(tombstone), Is.True);
        }

        bool removed = WaitUntil(
            () => !Directory.Exists(tombstone),
            TimeSpan.FromSeconds(8));
        string processState;
        try
        {
            using Process cleanup = Process.GetProcessById(checked((int)processId));
            processState = cleanup.HasExited
                ? $"exited:{cleanup.ExitCode}"
                : "running";
        }
        catch (ArgumentException)
        {
            processState = "exited:unknown";
        }

        string entries = Directory.Exists(tombstone)
            ? string.Join(",", Directory.GetFileSystemEntries(tombstone)
                .Select(Path.GetFileName))
            : "missing";
        Assert.That(
            removed,
            Is.True,
            $"The fixed cmd.exe retry loop did not remove the unlocked tombstone; process={processState}; entries={entries}.");
        Assert.That(File.ReadAllText(neighbor), Is.EqualTo("neighbor"));
    }

    [Test]
    [Explicit("Physical Windows proof that an active executable does not block its containing directory rename.")]
    public void InstallationMoveWorksWhileAnExecutableRunsFromTheRoot()
    {
        using TemporaryTree tree = new();
        Directory.CreateDirectory(tree.InstallationRoot);
        string system = Environment.GetFolderPath(Environment.SpecialFolder.System);
        string copiedCommandProcessor = Path.Combine(
            tree.InstallationRoot,
            "Baxy.Setup.exe");
        string ping = Path.Combine(system, "ping.exe");
        File.Copy(Path.Combine(system, "cmd.exe"), copiedCommandProcessor);
        ProcessStartInfo startInfo = new()
        {
            FileName = copiedCommandProcessor,
            UseShellExecute = false,
            CreateNoWindow = true,
        };
        startInfo.ArgumentList.Add("/d");
        startInfo.ArgumentList.Add("/q");
        startInfo.ArgumentList.Add("/c");
        startInfo.ArgumentList.Add($"\"{ping}\" -n 4 127.0.0.1 >nul");

        using Process process = Process.Start(startInfo) ??
            throw new AssertionException("Windows did not start the copied executable.");
        try
        {
            Assert.That(process.HasExited, Is.False);
            string tombstone = SetupUninstallExecutor.BuildTombstonePath(
                tree.InstallationRoot,
                Guid.NewGuid());

            SetupUninstallExecutor.MoveInstallationRoot(
                tree.InstallationRoot,
                tombstone);

            Assert.Multiple(() =>
            {
                Assert.That(Directory.Exists(tree.InstallationRoot), Is.False);
                Assert.That(File.Exists(Path.Combine(tombstone, "Baxy.Setup.exe")), Is.True);
            });
        }
        finally
        {
            if (!process.HasExited)
            {
                process.Kill(entireProcessTree: true);
            }

            process.WaitForExit(5_000);
        }
    }

    private static bool WaitUntil(Func<bool> condition, TimeSpan timeout)
    {
        Stopwatch stopwatch = Stopwatch.StartNew();
        while (stopwatch.Elapsed < timeout)
        {
            if (condition())
            {
                return true;
            }

            Thread.Sleep(25);
        }

        return condition();
    }

    private sealed class TemporaryTree : IDisposable
    {
        internal TemporaryTree()
        {
            OriginalWorkingDirectory = Environment.CurrentDirectory;
            Root = Path.Combine(
                Path.GetTempPath(),
                "baxy-minimal-uninstall-tests",
                Guid.NewGuid().ToString("N"));
            InstallationRoot = Path.Combine(Root, "BAXY");
            Directory.CreateDirectory(Root);
        }

        internal string Root { get; }

        internal string InstallationRoot { get; }

        private string OriginalWorkingDirectory { get; }

        public void Dispose()
        {
            string current = Path.GetFullPath(Environment.CurrentDirectory);
            string rootPrefix = Root + Path.DirectorySeparatorChar;
            if (string.Equals(current, Root, StringComparison.OrdinalIgnoreCase) ||
                current.StartsWith(rootPrefix, StringComparison.OrdinalIgnoreCase))
            {
                Directory.SetCurrentDirectory(OriginalWorkingDirectory);
            }

            if (Directory.Exists(Root))
            {
                Directory.Delete(Root, recursive: true);
            }
        }
    }
}
