using NUnit.Framework;

namespace Baxy.Setup.Tests;

public sealed class SetupProductLifecycleExecutorTests
{
    [Test]
    public void InstallUsesExactReopenableEmbeddedFactoryOnceThroughLifecycle()
    {
        Harness harness = new();
        Stream? first = null;
        Stream? second = null;
        harness.OnLifecycle = request =>
        {
            Assert.Multiple(() =>
            {
                Assert.That(
                    request.Operation,
                    Is.EqualTo(WindowsProductLifecycleOperation.InstallOrUpdate));
                Assert.That(request.CapturedHost, Is.SameAs(harness.Host));
                Assert.That(request.ParentPackage, Is.SameAs(harness.Package));
                Assert.That(request.OpenPackageStream, Is.SameAs(harness.OpenPackage));
                Assert.That(harness.OpenCount, Is.Zero);
            });
            first = request.OpenPackageStream!();
            second = request.OpenPackageStream!();
            return Result(WindowsProductLifecycleDisposition.Installed);
        };

        int exitCode = harness.Executor.Execute(SetupCommandKind.Install);

        Assert.Multiple(() =>
        {
            Assert.That(exitCode, Is.Zero);
            Assert.That(harness.CaptureCount, Is.EqualTo(1));
            Assert.That(harness.VerifyCount, Is.EqualTo(1));
            Assert.That(harness.LifecycleCount, Is.EqualTo(1));
            Assert.That(harness.OpenCount, Is.EqualTo(2));
            Assert.That(first, Is.Not.Null);
            Assert.That(second, Is.Not.Null.And.Not.SameAs(first));
            Assert.That(harness.ResumeCount, Is.Zero);
        });
        first?.Dispose();
        second?.Dispose();
    }

    [Test]
    public void RollbackUsesCurrentHostsVerifiedEmbeddedPackageWithoutStreamFactory()
    {
        Harness harness = new();
        harness.OnLifecycle = request =>
        {
            Assert.Multiple(() =>
            {
                Assert.That(
                    request.Operation,
                    Is.EqualTo(WindowsProductLifecycleOperation.Rollback));
                Assert.That(request.CapturedHost, Is.SameAs(harness.Host));
                Assert.That(request.ParentPackage, Is.SameAs(harness.Package));
                Assert.That(request.OpenPackageStream, Is.Null);
            });
            return Result(WindowsProductLifecycleDisposition.RolledBack);
        };

        int exitCode = harness.Executor.Execute(SetupCommandKind.Rollback);

        Assert.Multiple(() =>
        {
            Assert.That(exitCode, Is.Zero);
            Assert.That(harness.CaptureCount, Is.EqualTo(1));
            Assert.That(harness.VerifyCount, Is.EqualTo(1));
            Assert.That(harness.LifecycleCount, Is.EqualTo(1));
            Assert.That(harness.OpenCount, Is.Zero);
            Assert.That(harness.ResumeCount, Is.Zero);
        });
    }

    [TestCase("Install", "InstallOrUpdate")]
    [TestCase("Rollback", "Rollback")]
    public void RequiresTargetSetupRelaunchesExactlyReturnedRequirementAndStopsSuccessfully(
        string commandName,
        string operationName)
    {
        SetupCommandKind command = Enum.Parse<SetupCommandKind>(commandName);
        WindowsProductLifecycleOperation expectedOperation =
            Enum.Parse<WindowsProductLifecycleOperation>(operationName);
        Harness harness = new();
        WindowsProductLifecycleResumeRequirement requirement = new(
            Guid.NewGuid().ToString("N"),
            @"C:\Program Files\BAXY\Baxy.Setup.next.exe",
            new StableSetupHostIdentity(new string('b', 64), 123));
        harness.OnLifecycle = request =>
        {
            Assert.That(request.Operation, Is.EqualTo(expectedOperation));
            return new WindowsProductLifecycleResult(
                WindowsProductLifecycleDisposition.RequiresTargetSetup,
                "2.0.0",
                requirement.TransactionId,
                requirement);
        };
        harness.OnResume = (actual, operation) =>
        {
            Assert.Multiple(() =>
            {
                Assert.That(actual, Is.SameAs(requirement));
                Assert.That(operation, Is.EqualTo(expectedOperation));
            });
            return 42;
        };

        int exitCode = harness.Executor.Execute(command);

        Assert.Multiple(() =>
        {
            Assert.That(exitCode, Is.Zero);
            Assert.That(
                harness.Events,
                Is.EqualTo(new[] { "capture", "verify", "lifecycle", "resume" }));
            Assert.That(harness.CaptureCount, Is.EqualTo(1));
            Assert.That(harness.VerifyCount, Is.EqualTo(1));
            Assert.That(harness.LifecycleCount, Is.EqualTo(1));
            Assert.That(harness.ResumeCount, Is.EqualTo(1));
            Assert.That(harness.OpenCount, Is.Zero);
        });
    }

    [TestCase("Installed")]
    [TestCase("Updated")]
    [TestCase("RolledBack")]
    [TestCase("Reconciled")]
    [TestCase("Recovered")]
    [TestCase("AlreadyCurrent")]
    public void CompletedLifecycleDispositionNeverRelaunches(string dispositionName)
    {
        WindowsProductLifecycleDisposition disposition =
            Enum.Parse<WindowsProductLifecycleDisposition>(dispositionName);
        Harness harness = new();
        harness.OnLifecycle = _ => new WindowsProductLifecycleResult(
            disposition,
            "1.0.0",
            TransactionId: null);

        Assert.That(harness.Executor.Execute(SetupCommandKind.Install), Is.Zero);
        Assert.That(harness.ResumeCount, Is.Zero);
    }

    [Test]
    public void RequiresTargetSetupWithoutRequirementFailsClosedWithoutRelaunch()
    {
        Harness harness = new();
        harness.OnLifecycle = _ => new WindowsProductLifecycleResult(
            WindowsProductLifecycleDisposition.RequiresTargetSetup,
            "2.0.0",
            Guid.NewGuid().ToString("N"));

        Assert.Multiple(() =>
        {
            Assert.That(
                () => harness.Executor.Execute(SetupCommandKind.Install),
                Throws.TypeOf<InstallationSafetyException>());
            Assert.That(harness.ResumeCount, Is.Zero);
            Assert.That(harness.LifecycleCount, Is.EqualTo(1));
        });
    }

    [Test]
    public void CompletedLifecycleWithResumeTargetFailsClosedWithoutRelaunch()
    {
        Harness harness = new();
        harness.OnLifecycle = _ => new WindowsProductLifecycleResult(
            WindowsProductLifecycleDisposition.AlreadyCurrent,
            "1.0.0",
            TransactionId: null,
            new WindowsProductLifecycleResumeRequirement(
                Guid.NewGuid().ToString("N"),
                @"C:\foreign.exe",
                new StableSetupHostIdentity(new string('c', 64), 4)));

        Assert.Multiple(() =>
        {
            Assert.That(
                () => harness.Executor.Execute(SetupCommandKind.Install),
                Throws.TypeOf<InstallationSafetyException>());
            Assert.That(harness.ResumeCount, Is.Zero);
        });
    }

    [Test]
    public void RequiresTargetSetupWithChangedTransactionFailsClosedWithoutRelaunch()
    {
        Harness harness = new();
        harness.OnLifecycle = _ => new WindowsProductLifecycleResult(
            WindowsProductLifecycleDisposition.RequiresTargetSetup,
            "2.0.0",
            Guid.NewGuid().ToString("N"),
            new WindowsProductLifecycleResumeRequirement(
                Guid.NewGuid().ToString("N"),
                @"C:\Program Files\BAXY\Baxy.Setup.next.exe",
                new StableSetupHostIdentity(new string('d', 64), 12)));

        Assert.Multiple(() =>
        {
            Assert.That(
                () => harness.Executor.Execute(SetupCommandKind.Install),
                Throws.TypeOf<InstallationSafetyException>());
            Assert.That(harness.ResumeCount, Is.Zero);
        });
    }

    [Test]
    public void ResumeLaunchWithoutProcessIdentityFailsClosed()
    {
        Harness harness = new();
        string transactionId = Guid.NewGuid().ToString("N");
        harness.OnLifecycle = _ => new WindowsProductLifecycleResult(
            WindowsProductLifecycleDisposition.RequiresTargetSetup,
            "2.0.0",
            transactionId,
            new WindowsProductLifecycleResumeRequirement(
                transactionId,
                @"C:\Program Files\BAXY\Baxy.Setup.next.exe",
                new StableSetupHostIdentity(new string('d', 64), 12)));
        harness.OnResume = static (_, _) => 0;

        Assert.Multiple(() =>
        {
            Assert.That(
                () => harness.Executor.Execute(SetupCommandKind.Install),
                Throws.TypeOf<InstallationSafetyException>());
            Assert.That(harness.ResumeCount, Is.EqualTo(1));
        });
    }

    [Test]
    public void UnsupportedLifecycleDispositionFailsClosedWithoutRelaunch()
    {
        Harness harness = new();
        harness.OnLifecycle = _ => new WindowsProductLifecycleResult(
            (WindowsProductLifecycleDisposition)int.MaxValue,
            "1.0.0",
            TransactionId: null);

        Assert.Multiple(() =>
        {
            Assert.That(
                () => harness.Executor.Execute(SetupCommandKind.Install),
                Throws.TypeOf<InstallationSafetyException>());
            Assert.That(harness.ResumeCount, Is.Zero);
        });
    }

    [TestCase("Launch")]
    [TestCase("Uninstall")]
    [TestCase("VerifyEmbedded")]
    public void NonLifecycleCommandIsRejectedBeforeAnyEffect(string commandName)
    {
        SetupCommandKind command = Enum.Parse<SetupCommandKind>(commandName);
        Harness harness = new();

        Assert.Multiple(() =>
        {
            Assert.That(
                () => harness.Executor.Execute(command),
                Throws.TypeOf<ArgumentException>());
            Assert.That(harness.Events, Is.Empty);
        });
    }

    [Test]
    public void CaptureFailurePropagatesWithoutLaterEffects()
    {
        Harness harness = new()
        {
            OnCapture = () => throw new InstallationSafetyException("capture"),
        };

        Assert.Multiple(() =>
        {
            Assert.That(
                () => harness.Executor.Execute(SetupCommandKind.Install),
                Throws.TypeOf<InstallationSafetyException>());
            Assert.That(harness.Events, Is.EqualTo(new[] { "capture" }));
        });
    }

    [Test]
    public void PackageFailurePropagatesWithoutLifecycleOrRelaunch()
    {
        Harness harness = new()
        {
            OnVerify = () => throw new ProductPackageException("package"),
        };

        Assert.Multiple(() =>
        {
            Assert.That(
                () => harness.Executor.Execute(SetupCommandKind.Install),
                Throws.TypeOf<ProductPackageException>());
            Assert.That(harness.Events, Is.EqualTo(new[] { "capture", "verify" }));
        });
    }

    [Test]
    public void LifecycleFailurePropagatesOnceWithoutRelaunch()
    {
        Harness harness = new()
        {
            OnLifecycle = _ => throw new InstallationSafetyException("lifecycle"),
        };

        Assert.Multiple(() =>
        {
            Assert.That(
                () => harness.Executor.Execute(SetupCommandKind.Rollback),
                Throws.TypeOf<InstallationSafetyException>());
            Assert.That(
                harness.Events,
                Is.EqualTo(new[] { "capture", "verify", "lifecycle" }));
            Assert.That(harness.LifecycleCount, Is.EqualTo(1));
            Assert.That(harness.ResumeCount, Is.Zero);
        });
    }

    [Test]
    public void RelaunchFailurePropagatesAfterOneLifecycleAndOneLaunchAttempt()
    {
        Harness harness = new();
        string transactionId = Guid.NewGuid().ToString("N");
        harness.OnLifecycle = _ => new WindowsProductLifecycleResult(
            WindowsProductLifecycleDisposition.RequiresTargetSetup,
            "2.0.0",
            transactionId,
            new WindowsProductLifecycleResumeRequirement(
                transactionId,
                @"C:\Program Files\BAXY\Baxy.Setup.next.exe",
                new StableSetupHostIdentity(new string('d', 64), 12)));
        harness.OnResume = (_, _) => throw new InstallationSafetyException("resume");

        Assert.Multiple(() =>
        {
            Assert.That(
                () => harness.Executor.Execute(SetupCommandKind.Install),
                Throws.TypeOf<InstallationSafetyException>());
            Assert.That(
                harness.Events,
                Is.EqualTo(new[] { "capture", "verify", "lifecycle", "resume" }));
            Assert.That(harness.LifecycleCount, Is.EqualTo(1));
            Assert.That(harness.ResumeCount, Is.EqualTo(1));
        });
    }

    [Test]
    public void NullLifecycleResultFailsClosedWithoutRelaunch()
    {
        Harness harness = new()
        {
            OnLifecycle = _ => null!,
        };

        Assert.Multiple(() =>
        {
            Assert.That(
                () => harness.Executor.Execute(SetupCommandKind.Install),
                Throws.TypeOf<InstallationSafetyException>());
            Assert.That(harness.LifecycleCount, Is.EqualTo(1));
            Assert.That(harness.ResumeCount, Is.Zero);
        });
    }

    private static WindowsProductLifecycleResult Result(
        WindowsProductLifecycleDisposition disposition) =>
        new(disposition, "1.0.0", Guid.NewGuid().ToString("N"));

    private sealed class Harness
    {
        internal Harness()
        {
            Host = new CapturedSetupHost(
                @"C:\Setup\Baxy.Setup.exe",
                new StableSetupHostIdentity(new string('a', 64), 100));
            Package = new VerifiedProductPackage(
                PackageContract.DataSchema,
                "1.0.0",
                new string('1', 64),
                new string('2', 64),
                new string('3', 64),
                new string('4', 40),
                packageLength: 100,
                sourceDateEpoch: 0,
                entries: []);
            OnCapture = CaptureDefault;
            OnVerify = VerifyDefault;
            OnLifecycle = LifecycleDefault;
            Capture = () =>
            {
                CaptureCount++;
                Events.Add("capture");
                return OnCapture();
            };
            Verify = () =>
            {
                VerifyCount++;
                Events.Add("verify");
                return OnVerify();
            };
            OpenPackage = () =>
            {
                OpenCount++;
                Events.Add("open");
                return OnOpen();
            };
            Lifecycle = request =>
            {
                LifecycleCount++;
                Events.Add("lifecycle");
                return OnLifecycle(request);
            };
            Resume = (requirement, operation) =>
            {
                ResumeCount++;
                Events.Add("resume");
                return OnResume(requirement, operation);
            };
            Executor = new SetupProductLifecycleExecutor(
                new SetupProductLifecycleExecutorFactories(
                    Capture,
                    Verify,
                    OpenPackage,
                    Lifecycle,
                    Resume));
        }

        internal CapturedSetupHost Host { get; }

        internal VerifiedProductPackage Package { get; }

        internal Func<CapturedSetupHost> Capture { get; }

        internal Func<VerifiedProductPackage> Verify { get; }

        internal Func<Stream> OpenPackage { get; }

        internal Func<WindowsProductLifecycleRequest, WindowsProductLifecycleResult> Lifecycle { get; }

        internal Func<WindowsProductLifecycleResumeRequirement,
            WindowsProductLifecycleOperation, uint> Resume
        { get; }

        internal SetupProductLifecycleExecutor Executor { get; }

        internal List<string> Events { get; } = [];

        internal int CaptureCount { get; private set; }

        internal int VerifyCount { get; private set; }

        internal int OpenCount { get; private set; }

        internal int LifecycleCount { get; private set; }

        internal int ResumeCount { get; private set; }

        internal Func<CapturedSetupHost> OnCapture { get; set; }

        internal Func<VerifiedProductPackage> OnVerify { get; set; }

        internal Func<Stream> OnOpen { get; set; } =
            static () => new MemoryStream([0x42], writable: false);

        internal Func<WindowsProductLifecycleRequest, WindowsProductLifecycleResult>
            OnLifecycle
        { get; set; }

        internal Func<WindowsProductLifecycleResumeRequirement,
            WindowsProductLifecycleOperation, uint> OnResume
        { get; set; } =
            static (_, _) => 1;

        private CapturedSetupHost CaptureDefault() => Host;

        private VerifiedProductPackage VerifyDefault() => Package;

        private static WindowsProductLifecycleResult LifecycleDefault(
            WindowsProductLifecycleRequest _) =>
            Result(WindowsProductLifecycleDisposition.AlreadyCurrent);

    }
}
