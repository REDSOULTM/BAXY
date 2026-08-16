using System.Reflection;
using System.Runtime.InteropServices;
using NUnit.Framework;

namespace Baxy.Setup.Tests;

[TestFixture]
public sealed class WindowsSetupResumeLauncherTests
{
    [TestCase("InstallOrUpdate", "")]
    [TestCase("Rollback", " --rollback")]
    public void Launch_UsesOnlyTheVerifiedStableOrNextTargetAndCanonicalArguments(
        string operationName,
        string expectedSuffix)
    {
        WindowsProductLifecycleOperation operation = Enum.Parse<WindowsProductLifecycleOperation>(
            operationName);
        using ResumeTestTree tree = ResumeTestTree.Create();
        CapturingPlatform platform = new(request =>
        {
            Assert.Multiple(() =>
            {
                Assert.That(request.ApplicationName, Is.EqualTo(tree.Next));
                Assert.That(request.WorkingDirectory, Is.EqualTo(tree.Paths.InstallationRoot));
                Assert.That(request.CommandLine, Is.EqualTo($"\"{tree.Next}\"{expectedSuffix}"));
                Assert.That(request.EnvironmentBlock, Is.EqualTo(new[] { '\0', '\0' }));
                Assert.That(request.CreationFlags,
                    Is.EqualTo(WindowsSetupResumeLauncher.CreateUnicodeEnvironment));
                Assert.That(request.InheritHandles, Is.False);
                Assert.That(
                    () => File.Open(tree.Next, FileMode.Open, FileAccess.Write, FileShare.Read),
                    Throws.InstanceOf<IOException>());
            });
        });
        WindowsSetupResumeLauncher launcher = new(
            tree.Paths,
            platform,
            new EmptyEnvironment());

        uint processId = launcher.Launch(tree.Requirement, operation);

        Assert.Multiple(() =>
        {
            Assert.That(processId, Is.EqualTo(4042));
            Assert.That(platform.CallCount, Is.EqualTo(1));
        });
    }

    [Test]
    public void Launch_RejectsForeignMissingChangedAndNoncanonicalRequirementsBeforeSpawn()
    {
        using ResumeTestTree tree = ResumeTestTree.Create();
        CapturingPlatform platform = new();
        WindowsSetupResumeLauncher launcher = new(
            tree.Paths,
            platform,
            new EmptyEnvironment());
        string foreign = Path.Combine(tree.Paths.InstallationRoot, "foreign.exe");
        File.Copy(tree.Next, foreign);
        WindowsProductLifecycleResumeRequirement[] invalid =
        [
            tree.Requirement with { VerifiedTargetSetupPath = null },
            tree.Requirement with { VerifiedTargetSetupPath = foreign },
            tree.Requirement with { TransactionId = tree.Requirement.TransactionId.ToUpperInvariant() },
            tree.Requirement with { TransactionId = Guid.Empty.ToString("N") },
            tree.Requirement with
            {
                TargetSetupIdentity = tree.Requirement.TargetSetupIdentity with
                {
                    Bytes = tree.Requirement.TargetSetupIdentity.Bytes + 1,
                },
            },
        ];

        foreach (WindowsProductLifecycleResumeRequirement requirement in invalid)
        {
            Assert.That(
                () => launcher.Launch(
                    requirement,
                    WindowsProductLifecycleOperation.InstallOrUpdate),
                Throws.TypeOf<InstallationSafetyException>());
        }

        Assert.That(
            () => launcher.Launch(
                tree.Requirement,
                WindowsProductLifecycleOperation.Reconcile),
            Throws.TypeOf<InstallationSafetyException>());
        File.AppendAllText(tree.Next, "changed");
        Assert.That(
            () => launcher.Launch(
                tree.Requirement,
                WindowsProductLifecycleOperation.InstallOrUpdate),
            Throws.TypeOf<InstallationSafetyException>());
        Assert.That(platform.CallCount, Is.Zero);
    }

    [Test]
    public void Launch_AcceptsTheExactPublishedStableTarget()
    {
        using ResumeTestTree tree = ResumeTestTree.Create();
        CapturedSetupHost stable = new SetupHostCandidateVerifier(
            new StaticProcessPath(tree.Paths.StableSetupHost),
            new UnusedCandidateRunner()).CaptureCurrentHost();
        WindowsProductLifecycleResumeRequirement requirement = tree.Requirement with
        {
            VerifiedTargetSetupPath = tree.Paths.StableSetupHost,
            TargetSetupIdentity = stable.Identity,
        };
        CapturingPlatform platform = new(request =>
            Assert.That(request.ApplicationName, Is.EqualTo(tree.Paths.StableSetupHost)));
        WindowsSetupResumeLauncher launcher = new(
            tree.Paths,
            platform,
            new EmptyEnvironment());

        Assert.That(
            launcher.Launch(
                requirement,
                WindowsProductLifecycleOperation.InstallOrUpdate),
            Is.EqualTo(4042));
    }

    [Test]
    public void Launch_RejectsAZeroProcessIdentityAndKeepsTheVerifiedTarget()
    {
        using ResumeTestTree tree = ResumeTestTree.Create();
        byte[] before = File.ReadAllBytes(tree.Next);
        WindowsSetupResumeLauncher launcher = new(
            tree.Paths,
            new CapturingPlatform(processId: 0),
            new EmptyEnvironment());

        Assert.That(
            () => launcher.Launch(
                tree.Requirement,
                WindowsProductLifecycleOperation.InstallOrUpdate),
            Throws.TypeOf<InstallationSafetyException>());
        Assert.That(File.ReadAllBytes(tree.Next), Is.EqualTo(before));
    }

    [Test]
    public void NativePlatformImportsCreateProcessOnlyAndNeverShellExecute()
    {
        string[] imports = typeof(WindowsSetupResumeProcessPlatform)
            .GetMethods(BindingFlags.Static | BindingFlags.NonPublic)
            .Where(method =>
                method.GetCustomAttribute<LibraryImportAttribute>() is not null ||
                method.GetCustomAttribute<DllImportAttribute>() is not null)
            .Select(method => method.Name)
            .Order(StringComparer.Ordinal)
            .ToArray();

        Assert.Multiple(() =>
        {
            Assert.That(imports, Does.Contain("CreateProcessW"));
            Assert.That(imports, Is.Not.Empty);
            Assert.That(imports, Has.All.Contains("CreateProcessW"));
            Assert.That(imports, Has.None.Contains("ShellExecute"));
        });
    }

    private sealed class CapturingPlatform : IWindowsSetupResumeProcessPlatform
    {
        private readonly Action<WindowsSetupResumeStartRequest>? _inspect;
        private readonly uint _processId;

        internal CapturingPlatform(
            Action<WindowsSetupResumeStartRequest>? inspect = null,
            uint processId = 4042)
        {
            _inspect = inspect;
            _processId = processId;
        }

        internal CapturingPlatform(uint processId)
            : this(inspect: null, processId)
        {
        }

        internal int CallCount { get; private set; }

        public uint CreateProcess(WindowsSetupResumeStartRequest request)
        {
            CallCount++;
            _inspect?.Invoke(request);
            return _processId;
        }
    }

    private sealed class EmptyEnvironment : IInstalledApplicationEnvironment
    {
        public IReadOnlyList<KeyValuePair<string, string>> Capture() => [];
    }

    private sealed class ResumeTestTree : IDisposable
    {
        private ResumeTestTree(
            string outer,
            CanonicalWindowsPaths paths,
            string next,
            WindowsProductLifecycleResumeRequirement requirement)
        {
            Outer = outer;
            Paths = paths;
            Next = next;
            Requirement = requirement;
        }

        internal string Outer { get; }

        internal CanonicalWindowsPaths Paths { get; }

        internal string Next { get; }

        internal WindowsProductLifecycleResumeRequirement Requirement { get; }

        internal static ResumeTestTree Create()
        {
            string outer = Path.Combine(
                Path.GetTempPath(),
                "baxy-setup-resume-" + Guid.NewGuid().ToString("N"));
            string installation = Path.Combine(outer, "Programs", "BAXY");
            string data = Path.Combine(outer, "BAXY-Data");
            string startMenu = Path.Combine(outer, "StartMenu", "BAXY");
            Directory.CreateDirectory(installation);
            string stable = Path.Combine(installation, "Baxy.Setup.exe");
            string next = Path.Combine(installation, "Baxy.Setup.next.exe");
            File.WriteAllBytes(stable, [0x4d, 0x5a, 0x01]);
            File.WriteAllBytes(next, [0x4d, 0x5a, 0x02, 0x03]);
            CanonicalWindowsPaths paths = new(
                installation,
                stable,
                Path.Combine(installation, "versions"),
                Path.Combine(installation, "current"),
                data,
                startMenu,
                Path.Combine(startMenu, "BAXY.lnk"));
            CapturedSetupHost captured = new SetupHostCandidateVerifier(
                new StaticProcessPath(next),
                new UnusedCandidateRunner()).CaptureCurrentHost();
            WindowsProductLifecycleResumeRequirement requirement = new(
                Guid.NewGuid().ToString("N"),
                next,
                captured.Identity);
            return new ResumeTestTree(outer, paths, next, requirement);
        }

        public void Dispose()
        {
            try
            {
                Directory.Delete(Outer, recursive: true);
            }
            catch (DirectoryNotFoundException)
            {
            }
        }
    }

    private sealed class StaticProcessPath(string path) : ISetupHostProcessPathProvider
    {
        public string? GetProcessPath() => path;
    }

    private sealed class UnusedCandidateRunner : ISetupHostCandidateRunner
    {
        public SetupHostCandidateRunResult Run(SetupHostCandidateRunRequest request) =>
            throw new AssertionException("Candidate execution was not expected.");
    }
}
