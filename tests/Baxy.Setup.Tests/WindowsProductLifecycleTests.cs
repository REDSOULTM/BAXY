using System.Security.Cryptography;
using NUnit.Framework;

namespace Baxy.Setup.Tests;

public sealed class WindowsProductLifecycleTests
{
    [Test]
    public void FirstInstallPublishesProductHostShortcutRegistryAndStateUnderBothLocks()
    {
        using LifecycleTestTree tree = LifecycleTestTree.Create();
        PackageFixture package = tree.CreatePackage("1.0.0", "first");
        CapturedSetupHost setup = tree.CreateSetup("setup-v1.exe", [0x4d, 0x5a, 0x01]);
        tree.Candidate.OnVerify = () =>
        {
            Assert.That(
                () => ProductOperationLease.Acquire(
                    tree.InstallationRoot,
                    requireExistingRootAndLock: true),
                Throws.TypeOf<InstallationSafetyException>());
            Assert.That(
                () => new InstallationEngine(tree.InstallationRoot).GetCurrentVersion(),
                Throws.TypeOf<InstallationSafetyException>());
        };

        WindowsProductLifecycleResult result = tree.Execute(
            WindowsProductLifecycleOperation.InstallOrUpdate,
            setup,
            package);

        Assert.Multiple(() =>
        {
            Assert.That(result.Disposition, Is.EqualTo(WindowsProductLifecycleDisposition.Installed));
            Assert.That(result.Version, Is.EqualTo("1.0.0"));
            Assert.That(result.ResumeRequirement, Is.Null);
            Assert.That(package.OpenCount, Is.EqualTo(3));
            Assert.That(tree.Candidate.VerifyCount, Is.EqualTo(1));
            Assert.That(tree.Registry.Current?.Version, Is.EqualTo("1.0.0"));
            Assert.That(tree.Shortcut.State.State, Is.EqualTo(OwnedStartMenuShortcutState.Exact));
            Assert.That(File.ReadAllBytes(tree.HostPaths.Stable), Is.EqualTo(File.ReadAllBytes(setup.Path)));
            Assert.That(new InstallationEngine(tree.InstallationRoot).GetCurrentVersion(), Is.EqualTo("1.0.0"));
        });
        tree.AssertCompleteAndClean("1.0.0");
    }

    [Test]
    public void UpdateRollbackAndReactivationPreserveOrReplaceHostExactlyAsPlanned()
    {
        using LifecycleTestTree tree = LifecycleTestTree.Create();
        PackageFixture first = tree.CreatePackage("1.0.0", "first");
        PackageFixture second = tree.CreatePackage("2.0.0", "second");
        CapturedSetupHost setupOne = tree.CreateSetup("setup-v1.exe", [0x4d, 0x5a, 0x01]);
        CapturedSetupHost setupTwo = tree.CreateSetup("setup-v2.exe", [0x4d, 0x5a, 0x02, 0x02]);
        _ = tree.Execute(WindowsProductLifecycleOperation.InstallOrUpdate, setupOne, first);
        int verifiedBeforeUpdate = tree.Candidate.VerifyCount;

        WindowsProductLifecycleResult updated = tree.Execute(
            WindowsProductLifecycleOperation.InstallOrUpdate,
            setupTwo,
            second);
        int verifiedAfterUpdate = tree.Candidate.VerifyCount;
        CapturedSetupHost stableTwo = tree.CaptureStable();

        WindowsProductLifecycleResult rolledBack = tree.Execute(
            WindowsProductLifecycleOperation.Rollback,
            stableTwo,
            second,
            includeStreamFactory: false);
        int verifiedAfterRollback = tree.Candidate.VerifyCount;
        WindowsProductLifecycleResult reactivated = tree.Execute(
            WindowsProductLifecycleOperation.InstallOrUpdate,
            stableTwo,
            second);

        Assert.Multiple(() =>
        {
            Assert.That(updated.Disposition, Is.EqualTo(WindowsProductLifecycleDisposition.Updated));
            Assert.That(rolledBack.Disposition, Is.EqualTo(WindowsProductLifecycleDisposition.RolledBack));
            Assert.That(reactivated.Disposition, Is.EqualTo(WindowsProductLifecycleDisposition.Updated));
            Assert.That(verifiedAfterUpdate, Is.EqualTo(verifiedBeforeUpdate + 1));
            Assert.That(verifiedAfterRollback, Is.EqualTo(verifiedAfterUpdate));
            Assert.That(tree.Candidate.VerifyCount, Is.EqualTo(verifiedAfterRollback));
            Assert.That(tree.Candidate.RecoverCount, Is.EqualTo(2));
            Assert.That(File.ReadAllBytes(tree.HostPaths.Stable), Is.EqualTo(File.ReadAllBytes(setupTwo.Path)));
            Assert.That(new InstallationEngine(tree.InstallationRoot).GetCurrentVersion(), Is.EqualTo("2.0.0"));
            Assert.That(tree.Registry.Current?.Version, Is.EqualTo("2.0.0"));
        });
        tree.AssertCompleteAndClean("2.0.0");
    }

    [Test]
    public void ExactReinstallIsReadOnlyAlreadyCurrentWithoutStreamJournalOrCandidate()
    {
        using LifecycleTestTree tree = LifecycleTestTree.Create();
        PackageFixture package = tree.CreatePackage("0.9.0", "idempotent");
        CapturedSetupHost setup = tree.CreateSetup("setup.exe", [0x4d, 0x5a, 0x09]);
        _ = tree.Execute(WindowsProductLifecycleOperation.InstallOrUpdate, setup, package);
        CapturedSetupHost stable = tree.CaptureStable();
        int opensBefore = package.OpenCount;
        int verifyBefore = tree.Candidate.VerifyCount;
        int recoverBefore = tree.Candidate.RecoverCount;

        WindowsProductLifecycleResult result = tree.Execute(
            WindowsProductLifecycleOperation.InstallOrUpdate,
            stable,
            package,
            includeStreamFactory: false);

        Assert.Multiple(() =>
        {
            Assert.That(result.Disposition, Is.EqualTo(WindowsProductLifecycleDisposition.AlreadyCurrent));
            Assert.That(result.TransactionId, Is.Null);
            Assert.That(package.OpenCount, Is.EqualTo(opensBefore));
            Assert.That(tree.Candidate.VerifyCount, Is.EqualTo(verifyBefore));
            Assert.That(tree.Candidate.RecoverCount, Is.EqualTo(recoverBefore));
            Assert.That(File.Exists(Path.Combine(
                tree.InstallationRoot,
                WindowsIntegrationStore.TransactionFileName)), Is.False);
        });
        tree.AssertCompleteAndClean("0.9.0");
    }

    [Test]
    public void RepeatedRollbackAcceptsPreservedStablePackageOnEitherVerifiedProductSide()
    {
        using LifecycleTestTree tree = LifecycleTestTree.Create();
        PackageFixture first = tree.CreatePackage("1.0.0", "rollback-first");
        PackageFixture second = tree.CreatePackage("2.0.0", "rollback-second");
        CapturedSetupHost setupOne = tree.CreateSetup("setup-v1.exe", [0x4d, 0x5a, 0x41]);
        CapturedSetupHost setupTwo = tree.CreateSetup("setup-v2.exe", [0x4d, 0x5a, 0x42]);
        _ = tree.Execute(WindowsProductLifecycleOperation.InstallOrUpdate, setupOne, first);
        _ = tree.Execute(WindowsProductLifecycleOperation.InstallOrUpdate, setupTwo, second);
        CapturedSetupHost stable = tree.CaptureStable();

        WindowsProductLifecycleResult firstRollback = tree.Execute(
            WindowsProductLifecycleOperation.Rollback,
            stable,
            second,
            includeStreamFactory: false);
        WindowsProductLifecycleResult secondRollback = tree.Execute(
            WindowsProductLifecycleOperation.Rollback,
            stable,
            second,
            includeStreamFactory: false);

        Assert.Multiple(() =>
        {
            Assert.That(firstRollback.Version, Is.EqualTo("1.0.0"));
            Assert.That(secondRollback.Version, Is.EqualTo("2.0.0"));
            Assert.That(tree.Candidate.VerifyCount, Is.EqualTo(2));
            Assert.That(new InstallationEngine(tree.InstallationRoot).GetCurrentVersion(), Is.EqualTo("2.0.0"));
        });
        tree.AssertCompleteAndClean("2.0.0");
    }

    [Test]
    public void SameProductWithDifferentHostOrTamperedExteriorFailsWithoutJournal()
    {
        using LifecycleTestTree tree = LifecycleTestTree.Create();
        PackageFixture package = tree.CreatePackage("0.9.0", "idempotent-tamper");
        CapturedSetupHost setup = tree.CreateSetup("setup.exe", [0x4d, 0x5a, 0x19]);
        _ = tree.Execute(WindowsProductLifecycleOperation.InstallOrUpdate, setup, package);
        CapturedSetupHost differentHost = tree.CreateSetup(
            "different-setup.exe",
            [0x4d, 0x5a, 0x19, 0x01]);
        int opensBefore = package.OpenCount;

        Assert.That(
            () => tree.Execute(
                WindowsProductLifecycleOperation.InstallOrUpdate,
                differentHost,
                package,
                includeStreamFactory: false),
            Throws.TypeOf<InstallationSafetyException>());
        tree.Registry.SeedForeign(tree.InstallationRoot);
        Assert.That(
            () => tree.Execute(
                WindowsProductLifecycleOperation.InstallOrUpdate,
                tree.CaptureStable(),
                package,
                includeStreamFactory: false),
            Throws.TypeOf<InstallationSafetyException>());

        Assert.Multiple(() =>
        {
            Assert.That(package.OpenCount, Is.EqualTo(opensBefore));
            Assert.That(File.Exists(Path.Combine(
                tree.InstallationRoot,
                WindowsIntegrationStore.TransactionFileName)), Is.False);
            Assert.That(new InstallationEngine(tree.InstallationRoot).GetCurrentVersion(), Is.EqualTo("0.9.0"));
        });
    }

    [Test]
    public void ReconcileAdoptsVerifiedEngineOnlyWhenExteriorStateIsMissing()
    {
        using LifecycleTestTree tree = LifecycleTestTree.Create();
        PackageFixture package = tree.CreatePackage("1.0.0", "legacy");
        using (Stream stream = package.Open())
        {
            _ = new InstallationEngine(tree.InstallationRoot).InstallOrUpdate(stream);
        }

        CapturedSetupHost setup = tree.CreateSetup("setup-reconcile.exe", [0x4d, 0x5a, 0x03]);
        int opensBefore = package.OpenCount;

        WindowsProductLifecycleResult result = tree.Execute(
            WindowsProductLifecycleOperation.Reconcile,
            setup,
            package,
            includeStreamFactory: false);

        Assert.Multiple(() =>
        {
            Assert.That(result.Disposition, Is.EqualTo(WindowsProductLifecycleDisposition.Reconciled));
            Assert.That(package.OpenCount, Is.EqualTo(opensBefore));
            Assert.That(tree.Registry.Current?.Version, Is.EqualTo("1.0.0"));
            Assert.That(tree.Candidate.VerifyCount, Is.EqualTo(1));
        });
        tree.AssertCompleteAndClean("1.0.0");
    }

    [Test]
    public void InvalidFreshRollbackDoesNotCreateImmutableInstallationIdentity()
    {
        using LifecycleTestTree tree = LifecycleTestTree.Create();
        PackageFixture package = tree.CreatePackage("1.0.0", "rollback-fresh");
        CapturedSetupHost setup = tree.CreateSetup("setup.exe", [0x4d, 0x5a, 0x31]);

        Assert.That(
            () => tree.Execute(
                WindowsProductLifecycleOperation.Rollback,
                setup,
                package,
                includeStreamFactory: false),
            Throws.TypeOf<InstallationSafetyException>());

        Assert.That(Directory.Exists(tree.InstallationRoot), Is.False);
    }

    [Test]
    public void ReconcileWithoutVerifiedEngineProductDoesNotCreateInstallationIdentity()
    {
        using LifecycleTestTree tree = LifecycleTestTree.Create();
        PackageFixture package = tree.CreatePackage("1.0.0", "reconcile-missing");
        CapturedSetupHost setup = tree.CreateSetup("setup.exe", [0x4d, 0x5a, 0x32]);

        Assert.That(
            () => tree.Execute(
                WindowsProductLifecycleOperation.Reconcile,
                setup,
                package,
                includeStreamFactory: false),
            Throws.TypeOf<InstallationSafetyException>());

        Assert.That(Directory.Exists(tree.InstallationRoot), Is.False);
    }

    [Test]
    public void ForeignFirstInstallRegistryLeavesInstallationRootCompletelyAbsent()
    {
        using LifecycleTestTree tree = LifecycleTestTree.Create();
        PackageFixture package = tree.CreatePackage("1.0.0", "foreign-exterior");
        CapturedSetupHost setup = tree.CreateSetup("setup.exe", [0x4d, 0x5a, 0x33]);
        tree.Registry.SeedForeign(tree.InstallationRoot);

        Assert.That(
            () => tree.Execute(
                WindowsProductLifecycleOperation.InstallOrUpdate,
                setup,
                package),
            Throws.TypeOf<InstallationSafetyException>());

        Assert.Multiple(() =>
        {
            Assert.That(Directory.Exists(tree.InstallationRoot), Is.False);
            Assert.That(File.Exists(tree.InstallationRoot), Is.False);
            Assert.That(tree.Registry.Current?.Version, Is.EqualTo("9.9.9"));
        });
    }

    [Test]
    public void ForeignFirstInstallShortcutLeavesInstallationRootCompletelyAbsent()
    {
        using LifecycleTestTree tree = LifecycleTestTree.Create();
        PackageFixture package = tree.CreatePackage("1.0.0", "foreign-shortcut");
        CapturedSetupHost setup = tree.CreateSetup("setup.exe", [0x4d, 0x5a, 0x35]);
        tree.Shortcut.SeedExact();

        Assert.That(
            () => tree.Execute(
                WindowsProductLifecycleOperation.InstallOrUpdate,
                setup,
                package),
            Throws.TypeOf<InstallationSafetyException>());

        Assert.Multiple(() =>
        {
            Assert.That(Directory.Exists(tree.InstallationRoot), Is.False);
            Assert.That(tree.Shortcut.State.State, Is.EqualTo(OwnedStartMenuShortcutState.Exact));
            Assert.That(tree.Registry.Current, Is.Null);
        });
    }

    [Test]
    public void InvalidFirstInstallStreamFactoriesLeaveInstallationRootCompletelyAbsent()
    {
        using LifecycleTestTree tree = LifecycleTestTree.Create();
        PackageFixture expected = tree.CreatePackage("1.0.0", "expected");
        PackageFixture different = tree.CreatePackage("2.0.0", "different");
        CapturedSetupHost setup = tree.CreateSetup("setup.exe", [0x4d, 0x5a, 0x36]);
        MemoryStream unreadable = new([0x42]);
        unreadable.Dispose();
        Func<Stream>?[] invalidFactories =
        [
            null,
            () => unreadable,
            different.Open,
        ];

        foreach (Func<Stream>? factory in invalidFactories)
        {
            Assert.That(
                () => tree.ExecuteRaw(
                    WindowsProductLifecycleOperation.InstallOrUpdate,
                    setup,
                    expected.Verified,
                    factory),
                Throws.TypeOf<InstallationSafetyException>());
            Assert.Multiple(() =>
            {
                Assert.That(Directory.Exists(tree.InstallationRoot), Is.False);
                Assert.That(tree.Registry.Current, Is.Null);
                Assert.That(tree.Shortcut.State.State, Is.EqualTo(OwnedStartMenuShortcutState.Missing));
            });
        }
    }

    [Test]
    public void MissingIdentityWithExistingTransactionFailsReadOnlyAndDoesNotInventGuid()
    {
        using LifecycleTestTree tree = LifecycleTestTree.Create();
        PackageFixture package = tree.CreatePackage("1.0.0", "missing-identity");
        CapturedSetupHost setup = tree.CreateSetup("setup.exe", [0x4d, 0x5a, 0x34]);
        OneShotLifecycleCrash crash = new(WindowsProductLifecycleFaultPoint.PreparedDurable);
        Assert.That(
            () => tree.Execute(
                WindowsProductLifecycleOperation.InstallOrUpdate,
                setup,
                package,
                crash),
            Throws.TypeOf<SimulatedLifecycleCrashException>());
        string journalPath = Path.Combine(
            tree.InstallationRoot,
            WindowsIntegrationStore.TransactionFileName);
        byte[] journalBefore = File.ReadAllBytes(journalPath);
        File.Delete(tree.InstallationIdentityPath);

        Assert.That(
            () => tree.Execute(
                WindowsProductLifecycleOperation.InstallOrUpdate,
                setup,
                package),
            Throws.TypeOf<InstallationSafetyException>());

        Assert.Multiple(() =>
        {
            Assert.That(File.Exists(tree.InstallationIdentityPath), Is.False);
            Assert.That(File.ReadAllBytes(journalPath), Is.EqualTo(journalBefore));
            Assert.That(File.Exists(tree.HostPaths.Next), Is.False);
        });
    }

    [Test]
    public void CrashAfterAbortCleanupLeavesTheAbortResumableAndStillConverges()
    {
        // AbortCleanupComplete is the only lifecycle fault point the
        // roll-forward matrix cannot reach: it fires on the abort path, after a
        // recovered transaction has undone its external state but before the
        // journal entry that authorised it is gone. Crashing exactly there must
        // leave the abort resumable rather than a half-undone transaction.
        using LifecycleTestTree tree = LifecycleTestTree.Create();
        PackageFixture package = tree.CreatePackage("1.0.0", "abort-cleanup");
        CapturedSetupHost setup = tree.CreateSetup("setup-abort.exe", [0x4d, 0x5a, 0x51]);

        OneShotLifecycleCrash prepared = new(WindowsProductLifecycleFaultPoint.PreparedDurable);
        Assert.That(
            () => tree.Execute(
                WindowsProductLifecycleOperation.InstallOrUpdate,
                setup,
                package,
                prepared),
            Throws.TypeOf<SimulatedLifecycleCrashException>());

        string journalPath = Path.Combine(
            tree.InstallationRoot,
            WindowsIntegrationStore.TransactionFileName);
        Assert.That(File.Exists(journalPath), Is.True);

        OneShotLifecycleCrash abort = new(WindowsProductLifecycleFaultPoint.AbortCleanupComplete);
        Assert.That(
            () => tree.Execute(
                WindowsProductLifecycleOperation.InstallOrUpdate,
                setup,
                package,
                abort),
            Throws.TypeOf<SimulatedLifecycleCrashException>());

        // The authorising journal entry survives the crash, so the next run
        // still knows an abort was in progress instead of finding orphan state.
        Assert.That(File.Exists(journalPath), Is.True);

        WindowsProductLifecycleResult recovered = tree.Execute(
            WindowsProductLifecycleOperation.InstallOrUpdate,
            setup,
            package);

        Assert.That(
            recovered.Disposition,
            Is.EqualTo(WindowsProductLifecycleDisposition.Recovered));
        tree.AssertCompleteAndClean("1.0.0");
    }

    [Test]
    public void OldStableSetupReturnsRequiresTargetSetupWithoutMutatingPendingUpdate()
    {
        using LifecycleTestTree tree = LifecycleTestTree.Create();
        PackageFixture first = tree.CreatePackage("1.0.0", "first");
        PackageFixture second = tree.CreatePackage("2.0.0", "second");
        CapturedSetupHost setupOne = tree.CreateSetup("setup-v1.exe", [0x4d, 0x5a, 0x11]);
        CapturedSetupHost setupTwo = tree.CreateSetup("setup-v2.exe", [0x4d, 0x5a, 0x22]);
        _ = tree.Execute(WindowsProductLifecycleOperation.InstallOrUpdate, setupOne, first);
        CapturedSetupHost oldStable = tree.CaptureStable();
        OneShotLifecycleCrash crash = new(WindowsProductLifecycleFaultPoint.ProductReadyBeforeJournal);

        Assert.That(
            () => tree.Execute(
                WindowsProductLifecycleOperation.InstallOrUpdate,
                setupTwo,
                second,
                crash),
            Throws.TypeOf<SimulatedLifecycleCrashException>());
        byte[] journalBefore = File.ReadAllBytes(Path.Combine(
            tree.InstallationRoot,
            WindowsIntegrationStore.TransactionFileName));
        byte[] stableBefore = File.ReadAllBytes(tree.HostPaths.Stable);
        byte[] nextBefore = File.ReadAllBytes(tree.HostPaths.Next);
        WindowsUninstallRegistrySpecification registryBefore = tree.Registry.Current!;
        OwnedStartMenuShortcutSnapshot shortcutBefore = tree.Shortcut.State;

        WindowsProductLifecycleResult requirement = tree.Execute(
            WindowsProductLifecycleOperation.InstallOrUpdate,
            oldStable,
            first);

        Assert.Multiple(() =>
        {
            Assert.That(
                requirement.Disposition,
                Is.EqualTo(WindowsProductLifecycleDisposition.RequiresTargetSetup));
            Assert.That(requirement.ResumeRequirement, Is.Not.Null);
            Assert.That(
                requirement.ResumeRequirement!.VerifiedTargetSetupPath,
                Is.EqualTo(tree.HostPaths.Next));
            Assert.That(
                File.ReadAllBytes(Path.Combine(
                    tree.InstallationRoot,
                    WindowsIntegrationStore.TransactionFileName)),
                Is.EqualTo(journalBefore));
            Assert.That(File.ReadAllBytes(tree.HostPaths.Stable), Is.EqualTo(stableBefore));
            Assert.That(File.ReadAllBytes(tree.HostPaths.Next), Is.EqualTo(nextBefore));
            Assert.That(tree.Registry.Current, Is.EqualTo(registryBefore));
            Assert.That(tree.Shortcut.State, Is.EqualTo(shortcutBefore));
        });

        CapturedSetupHost resumeSetup = tree.Capture(tree.HostPaths.Next);
        WindowsProductLifecycleResult recovered = tree.Execute(
            WindowsProductLifecycleOperation.InstallOrUpdate,
            resumeSetup,
            second);
        Assert.That(recovered.Disposition, Is.EqualTo(WindowsProductLifecycleDisposition.Recovered));
        tree.AssertCompleteAndClean("2.0.0");
    }

    [TestCaseSource(nameof(RollForwardFaultPoints))]
    public void FirstInstallRecoversEveryCoordinatorFaultBoundary(
        object faultValue)
    {
        WindowsProductLifecycleFaultPoint faultPoint =
            (WindowsProductLifecycleFaultPoint)faultValue;
        using LifecycleTestTree tree = LifecycleTestTree.Create();
        PackageFixture package = tree.CreatePackage("1.0.0", faultPoint.ToString());
        CapturedSetupHost setup = tree.CreateSetup(
            "setup-fault.exe",
            [0x4d, 0x5a, checked((byte)((int)faultPoint + 1))]);
        OneShotLifecycleCrash crash = new(faultPoint);

        Assert.That(
            () => tree.Execute(
                WindowsProductLifecycleOperation.InstallOrUpdate,
                setup,
                package,
                crash),
            Throws.TypeOf<SimulatedLifecycleCrashException>());

        WindowsProductLifecycleResult recovered = tree.Execute(
            WindowsProductLifecycleOperation.InstallOrUpdate,
            setup,
            package,
            crash);

        Assert.That(recovered.Disposition, Is.EqualTo(WindowsProductLifecycleDisposition.Recovered));
        tree.AssertCompleteAndClean("1.0.0");
    }

    private static IEnumerable<object> RollForwardFaultPoints =>
    [
        WindowsProductLifecycleFaultPoint.PreparedDurable,
        WindowsProductLifecycleFaultPoint.HostReadyBeforeJournal,
        WindowsProductLifecycleFaultPoint.HostStagedDurable,
        WindowsProductLifecycleFaultPoint.ProductReadyBeforeJournal,
        WindowsProductLifecycleFaultPoint.ProductCommittedDurable,
        WindowsProductLifecycleFaultPoint.HostPublishedBeforeJournal,
        WindowsProductLifecycleFaultPoint.HostCommittedDurable,
        WindowsProductLifecycleFaultPoint.ShortcutReadyBeforeJournal,
        WindowsProductLifecycleFaultPoint.ShortcutCommittedDurable,
        WindowsProductLifecycleFaultPoint.RegistryIntentDurable,
        WindowsProductLifecycleFaultPoint.RegistryReadyBeforeIntegration,
        WindowsProductLifecycleFaultPoint.IntegrationReadyBeforeJournal,
        WindowsProductLifecycleFaultPoint.IntegrationCommittedDurable,
        WindowsProductLifecycleFaultPoint.CleanupComplete,
        WindowsProductLifecycleFaultPoint.CompleteDurable,
    ];

    private sealed class LifecycleTestTree : IDisposable
    {
        private LifecycleTestTree(string root)
        {
            Root = root;
            InstallationRoot = Path.Combine(root, "install");
            Directory.CreateDirectory(root);
            HostPaths = new StableSetupHostPaths(
                Path.Combine(InstallationRoot, "Baxy.Setup.exe"),
                Path.Combine(InstallationRoot, "Baxy.Setup.next.exe"),
                Path.Combine(InstallationRoot, "Baxy.Setup.previous.exe"));
            Registry = new FakeRegistry();
            Shortcut = new FakeShortcut();
            Candidate = new FakeCandidateVerifier();
        }

        internal string Root { get; }

        internal string InstallationRoot { get; }

        internal StableSetupHostPaths HostPaths { get; }

        internal string InstallationIdentityPath => Path.Combine(
            InstallationRoot,
            WindowsIntegrationStore.InstallationIdentityFileName);

        internal FakeRegistry Registry { get; }

        internal FakeShortcut Shortcut { get; }

        internal FakeCandidateVerifier Candidate { get; }

        internal static LifecycleTestTree Create()
        {
            string root = Path.Combine(
                Path.GetTempPath(),
                "baxy-lifecycle-tests",
                Guid.NewGuid().ToString("N"));
            return new LifecycleTestTree(root);
        }

        internal PackageFixture CreatePackage(string version, string salt)
        {
            if (!Directory.Exists(Root))
            {
                throw new InvalidOperationException("The lifecycle test root is missing.");
            }

            byte[] bytes = TestProductPackageFactory.Create(version, salt);
            using Stream stream = TestProductPackageFactory.Open(bytes);
            VerifiedProductPackage verified = new ProductPackageVerifier().Verify(stream);
            return new PackageFixture(bytes, verified);
        }

        internal CapturedSetupHost CreateSetup(string leaf, byte[] bytes)
        {
            string path = Path.Combine(Root, leaf);
            File.WriteAllBytes(path, bytes);
            return Capture(path);
        }

        internal CapturedSetupHost CaptureStable() => Capture(HostPaths.Stable);

        internal CapturedSetupHost Capture(string path)
        {
            string fullPath = Path.GetFullPath(path);
            if (!fullPath.StartsWith(Root + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
            {
                throw new InvalidOperationException("The captured test Setup escaped its test root.");
            }

            byte[] bytes = File.ReadAllBytes(fullPath);
            return new CapturedSetupHost(
                fullPath,
                new StableSetupHostIdentity(
                    Convert.ToHexStringLower(SHA256.HashData(bytes)),
                    bytes.LongLength));
        }

        internal WindowsProductLifecycleResult Execute(
            WindowsProductLifecycleOperation operation,
            CapturedSetupHost setup,
            PackageFixture package,
            IWindowsProductLifecycleFaultInjector? faultInjector = null,
            bool includeStreamFactory = true)
        {
            return ExecuteRaw(
                operation,
                setup,
                package.Verified,
                includeStreamFactory ? package.Open : null,
                faultInjector);
        }

        internal WindowsProductLifecycleResult ExecuteRaw(
            WindowsProductLifecycleOperation operation,
            CapturedSetupHost setup,
            VerifiedProductPackage verifiedPackage,
            Func<Stream>? openPackageStream,
            IWindowsProductLifecycleFaultInjector? faultInjector = null)
        {
            WindowsProductLifecycle lifecycle = CreateLifecycle(faultInjector);
            return lifecycle.Execute(
                new WindowsProductLifecycleRequest(
                    operation,
                    setup,
                    verifiedPackage,
                    openPackageStream));
        }

        internal WindowsProductLifecycle CreateLifecycle(
            IWindowsProductLifecycleFaultInjector? faultInjector)
        {
            return new WindowsProductLifecycle(
                InstallationRoot,
                new WindowsProductLifecycleFactories(
                    () => new InstallationEngine(InstallationRoot),
                    () => new WindowsIntegrationStore(InstallationRoot),
                    () => Registry,
                    () => Shortcut,
                    () => new WindowsProductLifecycleHostAdapter(
                        new StableSetupHostManager(HostPaths)),
                    () => Candidate),
                faultInjector);
        }

        internal void AssertCompleteAndClean(string version)
        {
            WindowsIntegrationStore store = new(InstallationRoot);
            WindowsInstallationIdentity? identity = store.RecoverAndReadInstallationIdentity();
            WindowsIntegrationState? state = store.ReadCommittedState();
            Assert.Multiple(() =>
            {
                Assert.That(identity, Is.Not.Null);
                Assert.That(state?.Active.Version, Is.EqualTo(version));
                Assert.That(state?.StableSetup.HostSha256, Is.EqualTo(CaptureStable().Identity.Sha256));
                Assert.That(File.Exists(Path.Combine(
                    InstallationRoot,
                    WindowsIntegrationStore.TransactionFileName)), Is.False);
                Assert.That(File.Exists(HostPaths.Next), Is.False);
                Assert.That(File.Exists(HostPaths.Previous), Is.False);
                Assert.That(Registry.Current?.Version, Is.EqualTo(version));
                Assert.That(Shortcut.State.State, Is.EqualTo(OwnedStartMenuShortcutState.Exact));
            });
        }

        public void Dispose()
        {
            if (Directory.Exists(Root))
            {
                Directory.Delete(Root, recursive: true);
            }
        }
    }

    private sealed class PackageFixture(
        byte[] bytes,
        VerifiedProductPackage verified)
    {
        private readonly byte[] _bytes = bytes;

        internal VerifiedProductPackage Verified { get; } = verified;

        internal int OpenCount { get; private set; }

        internal MemoryStream Open()
        {
            OpenCount++;
            return TestProductPackageFactory.Open(_bytes);
        }
    }

    private sealed class FakeRegistry : IWindowsProductLifecycleRegistry
    {
        internal WindowsUninstallRegistrySpecification? Current { get; private set; }

        internal void SeedForeign(string installationRoot)
        {
            Current = new WindowsUninstallRegistrySpecification(
                Guid.NewGuid().ToString("N"),
                "9.9.9",
                PackageContract.DataSchema,
                installationRoot,
                Path.Combine(installationRoot, "Baxy.Setup.exe"),
                new string('f', 64),
                999);
        }

        public void EnsureAbsentVerified()
        {
            if (Current is not null)
            {
                throw new InstallationSafetyException("Fake registry is occupied.");
            }
        }

        public WindowsUninstallRegistryProbe ProbeOwnedVerified(
            WindowsUninstallRegistrySpecification target,
            WindowsUninstallRegistryExpectedExisting? expectedExisting = null)
        {
            if (Current is null)
            {
                return WindowsUninstallRegistryProbe.Missing;
            }

            if (Current == target)
            {
                return WindowsUninstallRegistryProbe.ExactTarget;
            }

            if (expectedExisting is not null &&
                string.Equals(Current.InstallId, target.InstallId, StringComparison.Ordinal) &&
                string.Equals(Current.InstallationRoot, target.InstallationRoot, StringComparison.Ordinal) &&
                string.Equals(Current.StableSetupHost, target.StableSetupHost, StringComparison.Ordinal) &&
                string.Equals(Current.Version, expectedExisting.Version, StringComparison.Ordinal) &&
                string.Equals(
                    Current.StableSetupSha256,
                    expectedExisting.StableSetupSha256,
                    StringComparison.Ordinal) &&
                Current.EstimatedSizeKilobytes == expectedExisting.EstimatedSizeKilobytes)
            {
                return WindowsUninstallRegistryProbe.ExactExpectedExisting;
            }

            throw new InstallationSafetyException("Fake registry is foreign.");
        }

        public void ReconcileOwnedFromJournal(
            WindowsUninstallRegistrySpecification target,
            WindowsUninstallRegistryExpectedExisting? expectedExisting = null)
        {
            WindowsUninstallRegistryProbe probe = ProbeOwnedVerified(target, expectedExisting);
            if (probe == WindowsUninstallRegistryProbe.Missing && expectedExisting is not null)
            {
                throw new InstallationSafetyException("Fake prior registry is missing.");
            }

            Current = target;
        }
    }

    private sealed class FakeShortcut : IWindowsProductLifecycleShortcut
    {
        internal OwnedStartMenuShortcutSnapshot State { get; private set; } =
            OwnedStartMenuShortcutSnapshot.Missing;

        internal void SeedExact()
        {
            State = new OwnedStartMenuShortcutSnapshot(
                OwnedStartMenuShortcutState.Exact,
                new string('c', 64),
                256);
        }

        public OwnedStartMenuShortcutSnapshot Probe() => State;

        public OwnedStartMenuShortcutSnapshot EnsureFromJournal(string transactionId)
        {
            _ = Guid.ParseExact(transactionId, "N");
            State = new OwnedStartMenuShortcutSnapshot(
                OwnedStartMenuShortcutState.Exact,
                new string('a', 64),
                512);
            return State;
        }
    }

    private sealed class FakeCandidateVerifier : IWindowsProductLifecycleCandidateVerifier
    {
        internal Action? OnVerify { get; set; }

        internal int VerifyCount { get; private set; }

        internal int RecoverCount { get; private set; }

        internal int DeleteCount { get; private set; }

        public VerifiedSetupHostCandidate VerifyStagedCandidate(
            string applicationPath,
            StableSetupHostIdentity expectedIdentity,
            string transactionId,
            VerifiedProductPackage parentPackage)
        {
            _ = parentPackage;
            StableSetupHostManager.VerifyExact(applicationPath, expectedIdentity);
            VerifyCount++;
            OnVerify?.Invoke();
            string evidencePath = Path.Combine(
                Path.GetDirectoryName(applicationPath)!,
                $".baxy-setup-verify-{transactionId}.json");
            VerifiedSetupHostEvidence evidence = new(
                applicationPath,
                transactionId,
                evidencePath,
                new StableSetupHostIdentity(new string('b', 64), 128));
            return new VerifiedSetupHostCandidate(
                applicationPath,
                expectedIdentity,
                evidence);
        }

        public VerifiedSetupHostEvidence? RecoverVerifiedEvidenceIfPresent(
            string applicationPath,
            StableSetupHostIdentity expectedIdentity,
            string transactionId,
            VerifiedProductPackage parentPackage)
        {
            _ = transactionId;
            _ = parentPackage;
            StableSetupHostManager.VerifyExact(applicationPath, expectedIdentity);
            RecoverCount++;
            return null;
        }

        public bool DeleteVerifiedEvidence(
            VerifiedSetupHostEvidence evidence,
            VerifiedProductPackage parentPackage)
        {
            _ = evidence;
            _ = parentPackage;
            DeleteCount++;
            return true;
        }
    }

    private sealed class OneShotLifecycleCrash(
        WindowsProductLifecycleFaultPoint target) : IWindowsProductLifecycleFaultInjector
    {
        private bool _thrown;

        public void Checkpoint(WindowsProductLifecycleFaultPoint point)
        {
            if (!_thrown && point == target)
            {
                _thrown = true;
                throw new SimulatedLifecycleCrashException(point);
            }
        }
    }

    private sealed class SimulatedLifecycleCrashException(
        WindowsProductLifecycleFaultPoint point) : Exception(point.ToString());
}
