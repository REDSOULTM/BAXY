using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Higiene del perfil (auditoría de estabilidad r19, hallazgos 4 y 5): los
/// registros del perfil tienen tope y sólo el BAXY del dueño (el instalado o la
/// build de su propio checkout), en su perfil, registra el autoarranque de Windows.
/// </summary>
[TestFixture]
public sealed class ProfileHygieneTests
{
    [Test]
    public void BoundedJsonlNeverHoldsMoreThanTwoCapsAfterManyWrites()
    {
        string directory = NewDirectory("bounded-jsonl");
        try
        {
            var file = new BoundedJsonlFile(Path.Combine(directory, "log.v1.jsonl"), maximumBytes: 1_024);
            string line = "{\"n\":\"" + new string('x', 90) + "\"}";
            for (int index = 0; index < 500; index++)
            {
                file.AppendLine(line);
            }

            long live = new FileInfo(file.FilePath).Length;
            long archive = new FileInfo(file.ArchivePath).Length;
            string[] lastLines = File.ReadAllLines(file.FilePath);
            Assert.Multiple(() =>
            {
                Assert.That(live, Is.LessThanOrEqualTo(1_024));
                Assert.That(archive, Is.LessThanOrEqualTo(1_024));
                Assert.That(Directory.GetFiles(directory), Has.Length.EqualTo(2));
                Assert.That(lastLines, Is.Not.Empty);
                Assert.That(lastLines.All(text => text == line), Is.True);
            });
        }
        finally
        {
            Directory.Delete(directory, recursive: true);
        }
    }

    [Test]
    public void BoundedJsonlBelowItsCapKeepsEveryLineInOneFile()
    {
        string directory = NewDirectory("bounded-jsonl-small");
        try
        {
            var file = new BoundedJsonlFile(Path.Combine(directory, "log.v1.jsonl"), maximumBytes: 1_024);
            file.AppendLine("{\"a\":1}");
            file.AppendLine("{\"a\":2}");

            Assert.Multiple(() =>
            {
                Assert.That(File.ReadAllLines(file.FilePath), Is.EqualTo(new[] { "{\"a\":1}", "{\"a\":2}" }));
                Assert.That(File.Exists(file.ArchivePath), Is.False);
            });
        }
        finally
        {
            Directory.Delete(directory, recursive: true);
        }
    }

    [Test]
    public void ConversationLogRotatesAtItsCapAndKeepsTheLatestTurns()
    {
        string directory = NewDirectory("conversation-cap");
        try
        {
            var log = new ConversationLog(directory, maximumBytes: 2_048);
            DateTimeOffset start = new(2026, 10, 9, 3, 0, 0, TimeSpan.Zero);
            for (int turn = 0; turn < 200; turn++)
            {
                log.Append(new ConversationMessage("Vos", "mensaje " + turn, true, start.AddSeconds(turn)));
            }

            string[] live = File.ReadAllLines(log.FilePath);
            Assert.Multiple(() =>
            {
                Assert.That(new FileInfo(log.FilePath).Length, Is.LessThanOrEqualTo(2_048));
                Assert.That(new FileInfo(log.ArchivePath).Length, Is.LessThanOrEqualTo(2_048));
                Assert.That(live[^1], Does.Contain("mensaje 199"));
                Assert.That(live[^1], Does.Contain("\"turn\":200"));
            });
        }
        finally
        {
            Directory.Delete(directory, recursive: true);
        }
    }

    [Test]
    public void PresenceSamplesStayCappedOnDiskAndInMemory()
    {
        string directory = NewDirectory("presence-cap");
        try
        {
            var store = new PresenceStatusStore(directory, maximumSampleBytes: 4_096);
            var sampler = new PresenceIdleSampler(new FixedReader(), retainedSamples: 8);
            for (int index = 0; index < 300; index++)
            {
                store.AppendSample(sampler.Capture(true, true, true, null, "ready"));
            }

            Assert.Multiple(() =>
            {
                Assert.That(sampler.Samples, Has.Count.EqualTo(8));
                Assert.That(new FileInfo(store.SamplesPath).Length, Is.LessThanOrEqualTo(4_096));
                Assert.That(new FileInfo(store.SamplesArchivePath).Length, Is.LessThanOrEqualTo(4_096));
            });
        }
        finally
        {
            Directory.Delete(directory, recursive: true);
        }
    }

    [Test]
    public void SamplerBelowItsRetentionKeepsEverySample()
    {
        var sampler = new PresenceIdleSampler(new FixedReader(), retainedSamples: 8);
        for (int index = 0; index < 5; index++)
        {
            sampler.Capture(true, true, true, null, "ready");
        }

        Assert.That(sampler.Samples, Has.Count.EqualTo(5));
        Assert.That(PresenceIdleSampler.DefaultRetainedSamples, Is.EqualTo(240));
    }

    [Test]
    public void AWorktreeBuildNeverRegistersAndRemovesItsOwnLeftover()
    {
        Checkouts checkouts = Checkouts.Create("worktree-leftover");
        try
        {
            var run = new PresenceAutostartTests.MemoryRunKey();
            run.Write(PresenceLimits.AutostartValueName, Command(checkouts.WorktreeExe));
            WindowsAutostartRegistration registration = checkouts.Registration(run, checkouts.WorktreeExe);

            string? command = registration.EnsureRegistered([]);

            Assert.Multiple(() =>
            {
                Assert.That(command, Is.Null);
                Assert.That(run.Read(PresenceLimits.AutostartValueName), Is.Null);
                Assert.That(registration.MayRegister(checkouts.WorktreeExe, []), Is.False);
            });
        }
        finally
        {
            checkouts.Dispose();
        }
    }

    [Test]
    public void ANonRegisteringRunLeavesTheInstalledRegistrationAlone()
    {
        Checkouts checkouts = Checkouts.Create("installed-kept");
        try
        {
            string installed = Command(Path.Combine(checkouts.InstallationRoot, "versions", "1.0.0", "Baxy.exe"));
            var run = new PresenceAutostartTests.MemoryRunKey();
            run.Write(PresenceLimits.AutostartValueName, installed);
            WindowsAutostartRegistration registration = checkouts.Registration(run, checkouts.WorktreeExe);

            Assert.That(registration.EnsureRegistered([]), Is.Null);
            Assert.That(run.Read(PresenceLimits.AutostartValueName), Is.EqualTo(installed));
        }
        finally
        {
            checkouts.Dispose();
        }
    }

    // Revisión adversarial r19: with nothing installed, the owner's normal App is the
    // build of his own checkout; it registers itself on the default profile, and a
    // second start writes nothing.
    [Test]
    public void TheOwnersCheckoutBuildOnTheDefaultProfileRegisters()
    {
        Checkouts checkouts = Checkouts.Create("owner-build");
        try
        {
            var run = new PresenceAutostartTests.MemoryRunKey();
            WindowsAutostartRegistration registration = checkouts.Registration(run, checkouts.OwnerExe);

            string? first = registration.EnsureRegistered([PresenceLimits.FromWindowsStartArgument]);
            string? second = registration.EnsureRegistered([]);

            Assert.Multiple(() =>
            {
                Assert.That(first, Is.EqualTo(Command(checkouts.OwnerExe)));
                Assert.That(second, Is.EqualTo(first));
                Assert.That(run.Read(PresenceLimits.AutostartValueName), Is.EqualTo(first));
                Assert.That(run.Writes, Is.EqualTo(1));
                Assert.That(registration.IsRegistered(), Is.True);
            });
        }
        finally
        {
            checkouts.Dispose();
        }
    }

    // The owner's entry points at his existing checkout build: a worktree build, a
    // probe or the conductor of that same build, or a test profile starts, writes
    // nothing and leaves the entry as it was.
    [TestCase("worktree", null, null)]
    [TestCase("owner", "--ui-probe=C:\\turnos.jsonl", null)]
    [TestCase("owner", "--conductor", null)]
    [TestCase("owner", null, "uso-real-v3")]
    [TestCase("elsewhere", null, null)]
    public void ARunThatMayNotRegisterKeepsTheOwnersEntry(
        string build, string? argument, string? testProfile)
    {
        Checkouts checkouts = Checkouts.Create("owner-kept-" + build);
        try
        {
            string owner = Command(checkouts.OwnerExe);
            var run = new PresenceAutostartTests.MemoryRunKey();
            run.Write(PresenceLimits.AutostartValueName, owner);
            string exe = build switch
            {
                "worktree" => checkouts.WorktreeExe,
                "elsewhere" => checkouts.ElsewhereExe,
                _ => checkouts.OwnerExe,
            };
            WindowsAutostartRegistration registration = checkouts.Registration(
                run,
                exe,
                testProfile is null ? null : Path.Combine(checkouts.Root, testProfile));

            string? command = registration.EnsureRegistered(argument is null ? [] : [argument]);

            Assert.Multiple(() =>
            {
                Assert.That(command, Is.Null);
                Assert.That(run.Read(PresenceLimits.AutostartValueName), Is.EqualTo(owner));
                Assert.That(run.Writes, Is.EqualTo(1));
            });
        }
        finally
        {
            checkouts.Dispose();
        }
    }

    // An entry whose binary is gone starts nothing any more: a run that may not
    // register removes it, and the owner's next start writes his own again.
    [Test]
    public void ADeadEntryGoesAndTheOwnersNextStartRegistersAgain()
    {
        Checkouts checkouts = Checkouts.Create("dead-entry");
        try
        {
            var run = new PresenceAutostartTests.MemoryRunKey();
            run.Write(
                PresenceLimits.AutostartValueName,
                Command(Path.Combine(checkouts.Root, "gone", "Baxy.exe")));

            Assert.That(checkouts.Registration(run, checkouts.WorktreeExe).EnsureRegistered([]), Is.Null);
            Assert.That(run.Read(PresenceLimits.AutostartValueName), Is.Null);

            string? owner = checkouts.Registration(run, checkouts.OwnerExe).EnsureRegistered([]);
            Assert.That(run.Read(PresenceLimits.AutostartValueName), Is.EqualTo(owner));
            Assert.That(owner, Is.EqualTo(Command(checkouts.OwnerExe)));
        }
        finally
        {
            checkouts.Dispose();
        }
    }

    [TestCase("--ui-probe=C:\\turnos.jsonl")]
    [TestCase("--conductor")]
    public void TheInstalledBinaryUnderAProbeOrTheConductorDoesNotRegister(string argument)
    {
        string exe = InstalledExe("probe-" + (argument.Length));
        var run = new PresenceAutostartTests.MemoryRunKey();
        WindowsAutostartRegistration registration = PresenceAutostartTests.InstalledRegistration(run, exe);

        Assert.Multiple(() =>
        {
            Assert.That(registration.EnsureRegistered([argument]), Is.Null);
            Assert.That(run.Writes, Is.EqualTo(0));
        });
    }

    [Test]
    public void TheInstalledBinaryOnATestProfileDoesNotRegister()
    {
        string exe = InstalledExe("test-profile");
        var run = new PresenceAutostartTests.MemoryRunKey();
        WindowsAutostartRegistration registration = PresenceAutostartTests.InstalledRegistration(
            run,
            exe,
            configuredDataRoot: Path.Combine(TestContext.CurrentContext.WorkDirectory, "uso-real-v3"));

        Assert.That(registration.EnsureRegistered([]), Is.Null);
        Assert.That(run.Writes, Is.EqualTo(0));
    }

    [Test]
    public void TheInstalledBinaryOnTheOwnersProfileRegisters()
    {
        string exe = InstalledExe("owner-profile");
        var run = new PresenceAutostartTests.MemoryRunKey();
        WindowsAutostartRegistration explicitDefault = PresenceAutostartTests.InstalledRegistration(
            run,
            exe,
            configuredDataRoot: Path.Combine(TestContext.CurrentContext.WorkDirectory, "profile-1") + "\\");

        string? command = explicitDefault.EnsureRegistered([PresenceLimits.FromWindowsStartArgument]);

        Assert.Multiple(() =>
        {
            Assert.That(command, Does.Contain(Path.GetFullPath(exe)));
            Assert.That(run.Read(PresenceLimits.AutostartValueName), Is.EqualTo(command));
            Assert.That(explicitDefault.IsRegistered(), Is.True);
        });
    }

    private static string Command(string exe) =>
        "\"" + Path.GetFullPath(exe) + "\" " + PresenceLimits.FromWindowsStartArgument;

    // A repository of the owner (its .git is a directory) with a build of its own,
    // a linked worktree inside it (its .git is a file) with another build, a binary
    // outside any checkout, and an installation root holding nothing.
    private sealed class Checkouts : IDisposable
    {
        private Checkouts(string root)
        {
            Root = root;
            string repository = Path.Combine(root, "BAXY");
            Directory.CreateDirectory(Path.Combine(repository, ".git"));
            string worktree = Path.Combine(repository, ".claude", "worktrees", "wf_test");
            Directory.CreateDirectory(worktree);
            File.WriteAllText(
                Path.Combine(worktree, ".git"),
                "gitdir: " + Path.Combine(repository, ".git", "worktrees", "wf_test"));
            OwnerExe = Build(Path.Combine(repository, "src", "Baxy.App", "bin", "Release"));
            WorktreeExe = Build(Path.Combine(worktree, "src", "Baxy.App", "bin", "Release"));
            ElsewhereExe = Build(Path.Combine(root, "copy"));
            InstallationRoot = Path.Combine(root, "Programs", "BAXY");
        }

        internal string Root { get; }

        internal string OwnerExe { get; }

        internal string WorktreeExe { get; }

        internal string ElsewhereExe { get; }

        internal string InstallationRoot { get; }

        internal static Checkouts Create(string name) => new(NewDirectory(name));

        internal WindowsAutostartRegistration Registration(
            PresenceAutostartTests.MemoryRunKey run,
            string exe,
            string? configuredDataRoot = null) =>
            new(
                run,
                () => exe,
                installationRoot: InstallationRoot,
                defaultDataRoot: Path.Combine(Root, "profile-1"),
                configuredDataRoot: () => configuredDataRoot);

        public void Dispose() => Directory.Delete(Root, recursive: true);

        private static string Build(string directory)
        {
            Directory.CreateDirectory(directory);
            string exe = Path.Combine(directory, "Baxy.exe");
            File.WriteAllBytes(exe, [0x4D, 0x5A]);
            return exe;
        }
    }

    private static string InstalledExe(string name)
    {
        string directory = Path.Combine(TestContext.CurrentContext.WorkDirectory, "installed-" + name);
        Directory.CreateDirectory(directory);
        string exe = Path.Combine(directory, "Baxy.exe");
        File.WriteAllBytes(exe, [0x4D, 0x5A]);
        return exe;
    }

    private static string NewDirectory(string prefix)
    {
        string directory = Path.Combine(Path.GetTempPath(), "baxy-" + prefix + "-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(directory);
        return directory;
    }

    private sealed class FixedReader : IPresenceProcessReader
    {
        public IReadOnlyList<PresenceProcessSample> ReadOwned() =>
            [new PresenceProcessSample(7, "Baxy", "C:\\BAXY\\Baxy.exe", 40_000_000, 200, 1.0, 0)];
    }
}
