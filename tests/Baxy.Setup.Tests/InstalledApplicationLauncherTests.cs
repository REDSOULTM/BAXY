using NUnit.Framework;

namespace Baxy.Setup.Tests;

[TestFixture]
public sealed class InstalledApplicationLauncherTests
{
    [Test]
    public void LaunchWithoutExistingRootFailsWithoutCreatingAnything()
    {
        using TemporaryDirectory temporary = new();
        RecordingPlatform platform = new();
        StaticEnvironment environment = new([]);
        InstalledApplicationLauncher launcher = new(
            new InstallationEngine(temporary.InstallationRoot),
            platform,
            environment);

        Assert.That(() => launcher.Launch(), Throws.TypeOf<InstallationSafetyException>());
        Assert.Multiple(() =>
        {
            Assert.That(Directory.Exists(temporary.InstallationRoot), Is.False);
            Assert.That(platform.CallCount, Is.Zero);
            Assert.That(environment.CaptureCount, Is.Zero);
        });
    }

    [Test]
    public void LaunchBuildsTheExactVerifiedNativeProcessContract()
    {
        using TemporaryDirectory temporary = new();
        InstallationEngine engine = InstallVersion(temporary.InstallationRoot, "1.0.0", "a");
        KeyValuePair<string, string>[] inherited =
        [
            KeyValuePair.Create("zeta", "last"),
            KeyValuePair.Create("bAxY_dAtA_dIr", @"C:\redirected"),
            KeyValuePair.Create("MiXeD", "á=β"),
            KeyValuePair.Create("Alpha", "one"),
        ];
        RecordingPlatform platform = new() { ProcessId = 4242 };
        InstalledApplicationLauncher launcher = new(
            engine,
            platform,
            new StaticEnvironment(inherited));

        uint processId = launcher.Launch();

        string expectedWorkingDirectory = Path.Combine(
            temporary.InstallationRoot,
            "versions",
            "1.0.0");
        InstalledApplicationStartRequest request = platform.LastRequest!;
        Assert.Multiple(() =>
        {
            Assert.That(processId, Is.EqualTo(4242));
            Assert.That(platform.CallCount, Is.EqualTo(1));
            Assert.That(
                request.ApplicationName,
                Is.EqualTo(Path.Combine(expectedWorkingDirectory, "Baxy.exe")));
            Assert.That(Path.IsPathFullyQualified(request.ApplicationName), Is.True);
            Assert.That(request.WorkingDirectory, Is.EqualTo(expectedWorkingDirectory));
            Assert.That(request.CommandLine, Is.Null);
            Assert.That(request.InheritHandles, Is.False);
            Assert.That(
                request.CreationFlags,
                Is.EqualTo(InstalledApplicationLauncher.CreateBreakawayFromJob |
                    InstalledApplicationLauncher.CreateUnicodeEnvironment));
            Assert.That(
                ParseEnvironmentBlock(request.EnvironmentBlock),
                Is.EqualTo(new[] { "Alpha=one", "MiXeD=á=β", "zeta=last" }));
            Assert.That(request.EnvironmentBlock[^2], Is.EqualTo('\0'));
            Assert.That(request.EnvironmentBlock[^1], Is.EqualTo('\0'));
            Assert.That(inherited[1], Is.EqualTo(KeyValuePair.Create("bAxY_dAtA_dIr", @"C:\redirected")));
        });
    }

    [Test]
    public void EnvironmentBuilderFiltersEveryOverrideCasingAndPreservesWindowsDriveEntries()
    {
        KeyValuePair<string, string>[] inherited =
        [
            KeyValuePair.Create("BAXY_DATA_DIR", "one"),
            KeyValuePair.Create("baxy_data_dir", "two"),
            KeyValuePair.Create("=C:", @"C:\work"),
            KeyValuePair.Create("Path", @"C:\Windows\System32"),
        ];

        char[] block = InstalledApplicationLauncher.BuildEnvironmentBlock(inherited);

        Assert.That(
            ParseEnvironmentBlock(block),
            Is.EqualTo(new[] { @"=C:=C:\work", @"Path=C:\Windows\System32" }));
    }

    [Test]
    public void EmptyEnvironmentIsExactlyTheRequiredDoubleNullTerminator()
    {
        char[] block = InstalledApplicationLauncher.BuildEnvironmentBlock([]);

        Assert.That(block, Is.EqualTo(new[] { '\0', '\0' }));
    }

    [TestCase("BAD=NAME", "value")]
    [TestCase("BAD\0NAME", "value")]
    [TestCase("GOOD", "bad\0value")]
    public void MalformedEnvironmentNeverReachesThePlatform(string name, string value)
    {
        using TemporaryDirectory temporary = new();
        InstallationEngine engine = InstallVersion(temporary.InstallationRoot, "1.0.0", "a");
        RecordingPlatform platform = new();
        InstalledApplicationLauncher launcher = new(
            engine,
            platform,
            new StaticEnvironment([KeyValuePair.Create(name, value)]));

        Assert.That(() => launcher.Launch(), Throws.TypeOf<InstalledApplicationLaunchException>());
        Assert.That(platform.CallCount, Is.Zero);
    }

    [Test]
    public void CallbackKeepsSetupMutexAndLockFileUntilItReturns()
    {
        using TemporaryDirectory temporary = new();
        InstallationEngine engine = InstallVersion(temporary.InstallationRoot, "1.0.0", "a");
        InstallationEngine concurrent = new(temporary.InstallationRoot);

        _ = engine.UseVerifiedCurrentApplication(application =>
        {
            Exception? failure = null;
            Task competing = Task.Run(() =>
            {
                try
                {
                    _ = concurrent.GetCurrentVersion();
                }
                catch (Exception exception)
                {
                    failure = exception;
                }
            });
            competing.GetAwaiter().GetResult();

            Assert.Multiple(() =>
            {
                Assert.That(application.Version, Is.EqualTo("1.0.0"));
                Assert.That(failure, Is.TypeOf<InstallationSafetyException>());
            });
            return 0;
        });

        Assert.That(concurrent.GetCurrentVersion(), Is.EqualTo("1.0.0"));
    }

    [Test]
    public void TamperedInstalledTreeNeverReachesTheLaunchCallback()
    {
        using TemporaryDirectory temporary = new();
        InstallationEngine engine = InstallVersion(temporary.InstallationRoot, "1.0.0", "a");
        File.WriteAllText(
            Path.Combine(temporary.InstallationRoot, "versions", "1.0.0", "extra.bin"),
            "tamper");
        bool invoked = false;

        Assert.That(
            () => engine.UseVerifiedCurrentApplication(application =>
            {
                invoked = true;
                return application.Version;
            }),
            Throws.TypeOf<InstallationSafetyException>());
        Assert.That(invoked, Is.False);
    }

    [Test]
    public void RollbackChangesTheTargetOfTheNextStableLaunch()
    {
        using TemporaryDirectory temporary = new();
        InstallationEngine engine = InstallVersion(temporary.InstallationRoot, "1.0.0", "a");
        Install(engine, TestProductPackageFactory.Create("1.1.0", "b"));
        _ = engine.Rollback();
        RecordingPlatform platform = new();
        InstalledApplicationLauncher launcher = new(
            engine,
            platform,
            new StaticEnvironment([]));

        _ = launcher.Launch();

        Assert.Multiple(() =>
        {
            Assert.That(engine.GetCurrentVersion(), Is.EqualTo("1.0.0"));
            Assert.That(
                platform.LastRequest!.ApplicationName,
                Is.EqualTo(Path.Combine(
                    temporary.InstallationRoot,
                    "versions",
                    "1.0.0",
                    "Baxy.exe")));
        });
    }

    [Test]
    public void InvalidProcessIdentityFailsClosed()
    {
        using TemporaryDirectory temporary = new();
        InstallationEngine engine = InstallVersion(temporary.InstallationRoot, "1.0.0", "a");
        RecordingPlatform platform = new() { ProcessId = 0 };
        InstalledApplicationLauncher launcher = new(
            engine,
            platform,
            new StaticEnvironment([]));

        Assert.That(() => launcher.Launch(), Throws.TypeOf<InstalledApplicationLaunchException>());
        Assert.That(platform.CallCount, Is.EqualTo(1));
    }

    [Test]
    public void PlatformFailureIsNormalizedWithoutLaunchingTheRealApplication()
    {
        using TemporaryDirectory temporary = new();
        InstallationEngine engine = InstallVersion(temporary.InstallationRoot, "1.0.0", "a");
        RecordingPlatform platform = new()
        {
            Failure = new InvalidOperationException("synthetic platform failure"),
        };
        InstalledApplicationLauncher launcher = new(
            engine,
            platform,
            new StaticEnvironment([]));

        Assert.That(() => launcher.Launch(), Throws.TypeOf<InstalledApplicationLaunchException>());
        Assert.That(platform.CallCount, Is.EqualTo(1));
    }

    private static InstallationEngine InstallVersion(string root, string version, string salt)
    {
        InstallationEngine engine = new(root);
        Install(engine, TestProductPackageFactory.Create(version, salt));
        return engine;
    }

    private static void Install(InstallationEngine engine, byte[] package)
    {
        using MemoryStream stream = TestProductPackageFactory.Open(package);
        _ = engine.InstallOrUpdate(stream);
    }

    private static string[] ParseEnvironmentBlock(char[] block)
    {
        List<string> entries = [];
        int offset = 0;
        while (offset < block.Length && block[offset] != '\0')
        {
            int end = Array.IndexOf(block, '\0', offset);
            if (end < 0)
            {
                throw new AssertionException("The environment block is not terminated.");
            }

            entries.Add(new string(block, offset, end - offset));
            offset = end + 1;
        }

        if (offset != block.Length - 1)
        {
            throw new AssertionException("The environment block has bytes after its final terminator.");
        }

        return [.. entries];
    }

    private sealed class RecordingPlatform : IInstalledApplicationPlatform
    {
        internal uint ProcessId { get; init; } = 1234;

        internal Exception? Failure { get; init; }

        internal int CallCount { get; private set; }

        internal InstalledApplicationStartRequest? LastRequest { get; private set; }

        public uint CreateProcess(InstalledApplicationStartRequest request)
        {
            CallCount++;
            LastRequest = request;
            if (Failure is not null)
            {
                throw Failure;
            }

            return ProcessId;
        }
    }

    private sealed class StaticEnvironment(
        IReadOnlyList<KeyValuePair<string, string>> entries) : IInstalledApplicationEnvironment
    {
        internal int CaptureCount { get; private set; }

        public IReadOnlyList<KeyValuePair<string, string>> Capture()
        {
            CaptureCount++;
            return entries;
        }
    }

    private sealed class TemporaryDirectory : IDisposable
    {
        private readonly string _root = Path.Combine(
            Path.GetTempPath(),
            "baxy-installed-launcher-tests",
            Guid.NewGuid().ToString("N"));

        internal TemporaryDirectory()
        {
            Directory.CreateDirectory(_root);
            InstallationRoot = Path.Combine(_root, "install");
        }

        internal string InstallationRoot { get; }

        public void Dispose()
        {
            if (Directory.Exists(_root))
            {
                Directory.Delete(_root, recursive: true);
            }
        }
    }
}
