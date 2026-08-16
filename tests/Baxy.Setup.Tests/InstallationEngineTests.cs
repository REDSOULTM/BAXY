using NUnit.Framework;
using System.Runtime.InteropServices;
using System.Text.Json;

namespace Baxy.Setup.Tests;

[TestFixture]
public sealed class InstallationEngineTests
{
    [Test]
    public void InstallAndExactSameVersionAreIdempotent()
    {
        using TemporaryDirectory temporary = new();
        byte[] package = TestProductPackageFactory.Create();
        InstallationEngine engine = new(temporary.InstallationRoot);

        InstallationResult installed = Install(engine, package);
        InstallationResult repeated = Install(engine, package);

        Assert.Multiple(() =>
        {
            Assert.That(installed.Disposition, Is.EqualTo(InstallationDisposition.Installed));
            Assert.That(repeated.Disposition, Is.EqualTo(InstallationDisposition.Idempotent));
            Assert.That(engine.GetCurrentVersion(), Is.EqualTo("1.0.0"));
            Assert.That(Directory.Exists(Path.Combine(temporary.InstallationRoot, "versions", "1.0.0")), Is.True);
        });
        AssertTransactionClean(temporary.InstallationRoot);
    }

    [Test]
    public void InstalledIdentityPropagatesCanonicalDataSchema()
    {
        using TemporaryDirectory temporary = new();
        _ = Install(new InstallationEngine(temporary.InstallationRoot), TestProductPackageFactory.Create());

        string pointer = File.ReadAllText(Path.Combine(temporary.InstallationRoot, "current"));
        string attestation = File.ReadAllText(Path.Combine(
            temporary.InstallationRoot,
            "versions",
            "1.0.0",
            ".baxy-version.json"));

        Assert.Multiple(() =>
        {
            Assert.That(
                pointer,
                Does.StartWith("{\"schema\":\"baxy-current-v2\",\"version\":\"1.0.0\",\"data_schema\":1"));
            Assert.That(
                attestation,
                Does.StartWith("{\"schema\":\"baxy-installed-version-v2\",\"version\":\"1.0.0\",\"data_schema\":1"));
        });
    }

    [Test]
    public void UpdateRejectsForeignDataSchemaWithoutChangingActivation()
    {
        using TemporaryDirectory temporary = new();
        InstallationEngine engine = new(temporary.InstallationRoot);
        _ = Install(engine, TestProductPackageFactory.Create("1.0.0", "a"));
        byte[] currentBefore = File.ReadAllBytes(Path.Combine(temporary.InstallationRoot, "current"));

        Assert.That(
            () => Install(engine, TestProductPackageFactory.Create("1.1.0", "b", dataSchema: 2)),
            Throws.TypeOf<ProductPackageException>());

        Assert.Multiple(() =>
        {
            Assert.That(File.ReadAllBytes(Path.Combine(temporary.InstallationRoot, "current")), Is.EqualTo(currentBefore));
            Assert.That(Directory.Exists(Path.Combine(temporary.InstallationRoot, "versions", "1.1.0")), Is.False);
        });
        AssertTransactionClean(temporary.InstallationRoot);
    }

    [Test]
    public void RollbackRejectsForeignDataSchemaPointerBeforeOpeningJournal()
    {
        using TemporaryDirectory temporary = new();
        InstallationEngine engine = new(temporary.InstallationRoot);
        _ = Install(engine, TestProductPackageFactory.Create("1.0.0", "a"));
        _ = Install(engine, TestProductPackageFactory.Create("1.1.0", "b"));
        string currentPath = Path.Combine(temporary.InstallationRoot, "current");
        string previousPath = Path.Combine(temporary.InstallationRoot, "current.previous");
        byte[] currentBefore = File.ReadAllBytes(currentPath);
        ReplaceDataSchema(previousPath, 2);

        Assert.That(() => engine.Rollback(), Throws.TypeOf<InstallationSafetyException>());

        Assert.That(File.ReadAllBytes(currentPath), Is.EqualTo(currentBefore));
        AssertTransactionClean(temporary.InstallationRoot);
    }

    [Test]
    public void InstalledVersionRejectsForeignDataSchemaAttestation()
    {
        using TemporaryDirectory temporary = new();
        InstallationEngine engine = new(temporary.InstallationRoot);
        _ = Install(engine, TestProductPackageFactory.Create());
        ReplaceDataSchema(
            Path.Combine(temporary.InstallationRoot, "versions", "1.0.0", ".baxy-version.json"),
            2);

        Assert.That(() => engine.GetCurrentVersion(), Throws.TypeOf<InstallationSafetyException>());
    }

    [Test]
    public void SameVersionWithDifferentBytesIsRejectedWithoutChangingCurrent()
    {
        using TemporaryDirectory temporary = new();
        InstallationEngine engine = new(temporary.InstallationRoot);
        _ = Install(engine, TestProductPackageFactory.Create(salt: "a"));

        Assert.That(
            () => Install(engine, TestProductPackageFactory.Create(salt: "b")),
            Throws.TypeOf<InstallationSafetyException>());

        Assert.That(engine.GetCurrentVersion(), Is.EqualTo("1.0.0"));
        AssertTransactionClean(temporary.InstallationRoot);
    }

    [TestCase("1.1.0", "1.0.0")]
    [TestCase("1.0.0+first", "1.0.0+second")]
    public void InstallUpdateRejectsDowngradeAndEqualPrecedenceVersion(string currentVersion, string candidateVersion)
    {
        using TemporaryDirectory temporary = new();
        InstallationEngine engine = new(temporary.InstallationRoot);
        _ = Install(engine, TestProductPackageFactory.Create(currentVersion, "a"));

        Assert.That(
            () => Install(engine, TestProductPackageFactory.Create(candidateVersion, "b")),
            Throws.TypeOf<InstallationSafetyException>());

        Assert.That(engine.GetCurrentVersion(), Is.EqualTo(currentVersion));
        Assert.That(Directory.Exists(Path.Combine(temporary.InstallationRoot, "versions", candidateVersion)), Is.False);
        AssertTransactionClean(temporary.InstallationRoot);
    }

    [Test]
    public void UpdateKeepsPreviousImmutableVersionAndRollbackTogglesPointers()
    {
        using TemporaryDirectory temporary = new();
        InstallationEngine engine = new(temporary.InstallationRoot);
        _ = Install(engine, TestProductPackageFactory.Create("1.0.0", "a"));
        string oldPayload = Path.Combine(temporary.InstallationRoot, "versions", "1.0.0", "Baxy.exe");
        byte[] oldBytes = File.ReadAllBytes(oldPayload);

        InstallationResult updated = Install(engine, TestProductPackageFactory.Create("1.1.0", "b"));
        InstallationResult rolledBack = engine.Rollback();

        Assert.Multiple(() =>
        {
            Assert.That(updated.Disposition, Is.EqualTo(InstallationDisposition.Updated));
            Assert.That(updated.PreviousVersion, Is.EqualTo("1.0.0"));
            Assert.That(rolledBack.Disposition, Is.EqualTo(InstallationDisposition.RolledBack));
            Assert.That(engine.GetCurrentVersion(), Is.EqualTo("1.0.0"));
            Assert.That(File.ReadAllBytes(oldPayload), Is.EqualTo(oldBytes));
            Assert.That(Directory.Exists(Path.Combine(temporary.InstallationRoot, "versions", "1.1.0")), Is.True);
        });
        AssertTransactionClean(temporary.InstallationRoot);
    }

    [Test]
    public void InvalidPackageCleansOnlyItsJournaledStaging()
    {
        using TemporaryDirectory temporary = new();
        InstallationEngine engine = new(temporary.InstallationRoot);
        byte[] tampered = TestProductPackageFactory.TamperPayloadByte(TestProductPackageFactory.Create());

        Assert.That(() => Install(engine, tampered), Throws.TypeOf<ProductPackageException>());

        Assert.That(Directory.GetFileSystemEntries(Path.Combine(temporary.InstallationRoot, "versions")), Is.Empty);
        AssertTransactionClean(temporary.InstallationRoot);
    }

    [Test]
    public void UnknownGuidStagingWithoutJournalFailsClosed()
    {
        using TemporaryDirectory temporary = new();
        InstallationEngine engine = new(temporary.InstallationRoot);
        Assert.That(engine.GetCurrentVersion(), Is.Null);
        string unknown = Path.Combine(
            temporary.InstallationRoot,
            "staging",
            Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(unknown);
        File.WriteAllText(Path.Combine(unknown, "sentinel.txt"), "owned by somebody else");

        Assert.That(() => engine.GetCurrentVersion(), Throws.TypeOf<InstallationSafetyException>());
        Assert.That(File.Exists(Path.Combine(unknown, "sentinel.txt")), Is.True);
    }

    [Test]
    public void InterruptedJournalNextBeforePromotionIsDiscardedSafely()
    {
        using TemporaryDirectory temporary = new();
        InstallationEngine engine = new(temporary.InstallationRoot);
        Assert.That(engine.GetCurrentVersion(), Is.Null);
        string journalNext = Path.Combine(temporary.InstallationRoot, "transaction.next");
        File.WriteAllText(journalNext, "incomplete next generation");

        Assert.That(engine.GetCurrentVersion(), Is.Null);
        Assert.That(File.Exists(journalNext), Is.False);
    }

    [Test]
    public void JournalCannotClaimAStagingIdDifferentFromItsTransactionId()
    {
        using TemporaryDirectory temporary = new();
        InstallationEngine engine = new(temporary.InstallationRoot);
        Assert.That(engine.GetCurrentVersion(), Is.Null);
        string claimed = Guid.NewGuid().ToString("N");
        string sentinel = Path.Combine(temporary.InstallationRoot, "staging", claimed, "sentinel.txt");
        Directory.CreateDirectory(Path.GetDirectoryName(sentinel)!);
        File.WriteAllText(sentinel, "preserve");
        InstallTransaction invalid = new()
        {
            TransactionId = Guid.NewGuid().ToString("N"),
            StagingId = claimed,
            Operation = "install_update",
            Phase = "prepared",
        };
        byte[] json = JsonSerializer.SerializeToUtf8Bytes(invalid, SetupJsonContext.Default.InstallTransaction);
        File.WriteAllBytes(Path.Combine(temporary.InstallationRoot, "transaction.v1.json"), [.. json, (byte)'\n']);

        Assert.That(() => engine.GetCurrentVersion(), Throws.TypeOf<InstallationSafetyException>());
        Assert.That(File.ReadAllText(sentinel), Is.EqualTo("preserve"));
    }

    [Test]
    public void AlternateDataStreamInPublishedVersionFailsClosed()
    {
        using TemporaryDirectory temporary = new();
        InstallationEngine engine = new(temporary.InstallationRoot);
        _ = Install(engine, TestProductPackageFactory.Create());
        string payload = Path.Combine(temporary.InstallationRoot, "versions", "1.0.0", "Baxy.exe");
        try
        {
            File.WriteAllText(payload + ":hostile", "hidden bytes");
        }
        catch (Exception exception) when (exception is IOException or NotSupportedException or UnauthorizedAccessException)
        {
            Assert.Ignore("The test filesystem does not support creating NTFS alternate data streams.");
            return;
        }

        Assert.That(() => engine.GetCurrentVersion(), Throws.TypeOf<InstallationSafetyException>());
    }

    [Test]
    public void HardLinkedPublishedPayloadFailsClosedAndPreservesExternalFile()
    {
        using TemporaryDirectory temporary = new();
        InstallationEngine engine = new(temporary.InstallationRoot);
        _ = Install(engine, TestProductPackageFactory.Create());
        string payload = Path.Combine(temporary.InstallationRoot, "versions", "1.0.0", "Baxy.exe");
        string external = Path.Combine(temporary.Path, "external-sentinel.bin");
        File.WriteAllText(external, "external bytes");
        File.Delete(payload);
        if (!CreateHardLink(payload, external, 0))
        {
            Assert.Ignore($"The test filesystem could not create a hard link (Win32 {Marshal.GetLastWin32Error()}).");
            return;
        }

        Assert.That(() => engine.GetCurrentVersion(), Throws.TypeOf<InstallationSafetyException>());
        Assert.That(File.ReadAllText(external), Is.EqualTo("external bytes"));
    }

    [Test]
    public void HardLinkedCurrentPointerFailsClosedAndPreservesExternalFile()
    {
        using TemporaryDirectory temporary = new();
        InstallationEngine engine = new(temporary.InstallationRoot);
        _ = Install(engine, TestProductPackageFactory.Create());
        string pointer = Path.Combine(temporary.InstallationRoot, "current");
        string external = Path.Combine(temporary.Path, "external-pointer.json");
        File.Copy(pointer, external);
        File.Delete(pointer);
        if (!CreateHardLink(pointer, external, 0))
        {
            Assert.Ignore($"The test filesystem could not create a hard link (Win32 {Marshal.GetLastWin32Error()}).");
            return;
        }

        Assert.That(() => engine.GetCurrentVersion(), Throws.TypeOf<InstallationSafetyException>());
        Assert.That(File.Exists(external), Is.True);
    }

    [Test]
    public async Task PersistentLockFileRejectsConcurrentEngineOperation()
    {
        using TemporaryDirectory temporary = new();
        using BlockingFaultInjector blocker = new(SetupFaultPoint.PackageCopied);
        InstallationEngine first = new(temporary.InstallationRoot, faultInjector: blocker);
        byte[] package = TestProductPackageFactory.Create();
        Task<InstallationResult> running = Task.Run(() => Install(first, package));
        Assert.That(blocker.WaitUntilEntered(TimeSpan.FromSeconds(5)), Is.True);
        try
        {
            InstallationEngine concurrent = new(temporary.InstallationRoot);
            Assert.That(() => concurrent.GetCurrentVersion(), Throws.TypeOf<InstallationSafetyException>());
        }
        finally
        {
            blocker.Release();
        }

        InstallationResult completed = await running;
        Assert.That(completed.Disposition, Is.EqualTo(InstallationDisposition.Installed));
    }

    [Test]
    public void ExclusivePersistentLockAloneBlocksAnEngineOperation()
    {
        using TemporaryDirectory temporary = new();
        InstallationEngine initialized = new(temporary.InstallationRoot);
        Assert.That(initialized.GetCurrentVersion(), Is.Null);
        string lockPath = Path.Combine(temporary.InstallationRoot, "setup.lock");
        using FileStream externalHolder = new(lockPath, FileMode.Open, FileAccess.ReadWrite, FileShare.None);

        InstallationEngine blocked = new(temporary.InstallationRoot);
        Assert.That(() => blocked.GetCurrentVersion(), Throws.TypeOf<InstallationSafetyException>());
    }

    [Test]
    public void ExclusiveInstallationSession_HoldsTheLeaseAcrossProductAndIntegrationWork()
    {
        using TemporaryDirectory temporary = new();
        InstallationEngine engine = new(temporary.InstallationRoot);
        byte[] package = TestProductPackageFactory.Create("1.2.3", "exclusive");

        VerifiedInstallationIdentity identity = engine.UseExclusiveInstallation(
            requireExistingRootAndLock: false,
            session =>
            {
                using MemoryStream stream = TestProductPackageFactory.Open(package);
                InstallationResult result = session.InstallOrUpdate(stream);
                Assert.That(result.Disposition, Is.EqualTo(InstallationDisposition.Installed));
                Assert.That(
                    () => new InstallationEngine(temporary.InstallationRoot).GetCurrentVersion(),
                    Throws.TypeOf<InstallationSafetyException>());
                return session.GetVerifiedCurrentIdentity();
            });

        Assert.Multiple(() =>
        {
            Assert.That(identity.Version, Is.EqualTo("1.2.3"));
            Assert.That(identity.DataSchema, Is.EqualTo(1));
            Assert.That(identity.PackageSha256, Does.Match("^[0-9a-f]{64}$"));
            Assert.That(identity.ManifestSha256, Does.Match("^[0-9a-f]{64}$"));
            Assert.That(identity.ContentId, Does.Match("^[0-9a-f]{64}$"));
            Assert.That(engine.GetCurrentVersion(), Is.EqualTo("1.2.3"));
        });
    }

    [Test]
    public void ExclusiveInstallationSession_CannotEscapeItsLeaseLifetime()
    {
        using TemporaryDirectory temporary = new();
        InstallationEngine engine = new(temporary.InstallationRoot);
        InstallationEngine.ExclusiveInstallationSession? escaped = null;

        _ = engine.UseExclusiveInstallation(
            requireExistingRootAndLock: false,
            session =>
            {
                escaped = session;
                return session.GetCurrentVersion();
            });

        Assert.That(escaped, Is.Not.Null);
        Assert.That(
            () => escaped!.GetCurrentVersion(),
            Throws.TypeOf<InstallationSafetyException>());
    }

    [Test]
    public void ExclusiveInstallationSession_ReadsVerifiedRollbackTargetWithoutMutation()
    {
        using TemporaryDirectory temporary = new();
        InstallationEngine engine = new(temporary.InstallationRoot);
        byte[] first = TestProductPackageFactory.Create("1.0.0", "first");
        byte[] second = TestProductPackageFactory.Create("2.0.0", "second");
        _ = Install(engine, first);
        _ = Install(engine, second);
        string currentPath = Path.Combine(temporary.InstallationRoot, "current");
        string previousPath = Path.Combine(temporary.InstallationRoot, "current.previous");
        byte[] currentBefore = File.ReadAllBytes(currentPath);
        byte[] previousBefore = File.ReadAllBytes(previousPath);

        VerifiedInstallationIdentity target = engine.UseExclusiveInstallation(
            requireExistingRootAndLock: true,
            static session => session.GetVerifiedRollbackTargetIdentity());

        Assert.Multiple(() =>
        {
            Assert.That(target.Version, Is.EqualTo("1.0.0"));
            Assert.That(target.DataSchema, Is.EqualTo(PackageContract.DataSchema));
            Assert.That(target.PackageSha256, Does.Match("^[0-9a-f]{64}$"));
            Assert.That(target.ManifestSha256, Does.Match("^[0-9a-f]{64}$"));
            Assert.That(target.ContentId, Does.Match("^[0-9a-f]{64}$"));
            Assert.That(File.ReadAllBytes(currentPath), Is.EqualTo(currentBefore));
            Assert.That(File.ReadAllBytes(previousPath), Is.EqualTo(previousBefore));
        });
    }

    [Test]
    public void ExclusiveInstallationSession_RejectsMissingRollbackTargetWithoutMutation()
    {
        using TemporaryDirectory temporary = new();
        InstallationEngine engine = new(temporary.InstallationRoot);
        _ = Install(engine, TestProductPackageFactory.Create());
        string currentPath = Path.Combine(temporary.InstallationRoot, "current");
        byte[] currentBefore = File.ReadAllBytes(currentPath);

        Assert.That(
            () => engine.UseExclusiveInstallation(
                requireExistingRootAndLock: true,
                static session => session.GetVerifiedRollbackTargetIdentity()),
            Throws.TypeOf<InstallationSafetyException>());
        Assert.That(File.ReadAllBytes(currentPath), Is.EqualTo(currentBefore));
        Assert.That(File.Exists(Path.Combine(temporary.InstallationRoot, "current.previous")), Is.False);
    }

    [Test]
    public void ExclusiveInstallationSession_RejectsTamperedRollbackTargetWithoutMutation()
    {
        using TemporaryDirectory temporary = new();
        InstallationEngine engine = new(temporary.InstallationRoot);
        _ = Install(engine, TestProductPackageFactory.Create("1.0.0", "first"));
        _ = Install(engine, TestProductPackageFactory.Create("2.0.0", "second"));
        string currentPath = Path.Combine(temporary.InstallationRoot, "current");
        string previousPath = Path.Combine(temporary.InstallationRoot, "current.previous");
        byte[] currentBefore = File.ReadAllBytes(currentPath);
        byte[] previousBefore = File.ReadAllBytes(previousPath);
        File.AppendAllText(
            Path.Combine(temporary.InstallationRoot, "versions", "1.0.0", "Baxy.exe"),
            "tamper");

        Assert.That(
            () => engine.UseExclusiveInstallation(
                requireExistingRootAndLock: true,
                static session => session.GetVerifiedRollbackTargetIdentity()),
            Throws.TypeOf<ProductPackageException>());
        Assert.Multiple(() =>
        {
            Assert.That(File.ReadAllBytes(currentPath), Is.EqualTo(currentBefore));
            Assert.That(File.ReadAllBytes(previousPath), Is.EqualTo(previousBefore));
        });
    }

    [Test]
    public void ExclusiveInstallationSession_RollbackTargetReaderCannotEscapeLeaseLifetime()
    {
        using TemporaryDirectory temporary = new();
        InstallationEngine engine = new(temporary.InstallationRoot);
        _ = Install(engine, TestProductPackageFactory.Create("1.0.0", "first"));
        _ = Install(engine, TestProductPackageFactory.Create("2.0.0", "second"));
        InstallationEngine.ExclusiveInstallationSession? escaped = null;

        _ = engine.UseExclusiveInstallation(
            requireExistingRootAndLock: true,
            session =>
            {
                escaped = session;
                return session.GetVerifiedRollbackTargetIdentity();
            });

        Assert.That(escaped, Is.Not.Null);
        Assert.That(
            () => escaped!.GetVerifiedRollbackTargetIdentity(),
            Throws.TypeOf<InstallationSafetyException>());
    }

    [Test]
    public void ExclusiveInstallationSession_ReleasesTheLeaseWhenTheCallbackFails()
    {
        using TemporaryDirectory temporary = new();
        InstallationEngine engine = new(temporary.InstallationRoot);

        Assert.That(
            () => engine.UseExclusiveInstallation<string>(
                requireExistingRootAndLock: false,
                static _ => throw new InvalidOperationException("injected callback failure")),
            Throws.TypeOf<InvalidOperationException>());
        Assert.That(engine.GetCurrentVersion(), Is.Null);
    }

    [Test]
    public void ExclusiveInstallationSession_ExistingModeDoesNotCreateMissingState()
    {
        using TemporaryDirectory temporary = new();
        InstallationEngine engine = new(temporary.InstallationRoot);

        Assert.That(
            () => engine.UseExclusiveInstallation(
                requireExistingRootAndLock: true,
                static session => session.GetCurrentVersion()),
            Throws.TypeOf<InstallationSafetyException>());
        Assert.That(Directory.Exists(temporary.InstallationRoot), Is.False);
    }

    [TestCase(SetupFaultPoint.PackageCopied)]
    [TestCase(SetupFaultPoint.PackageVerified)]
    [TestCase(SetupFaultPoint.StagingExtracted)]
    [TestCase(SetupFaultPoint.VersionPublished)]
    [TestCase(SetupFaultPoint.PointerNextDurable)]
    [TestCase(SetupFaultPoint.CurrentReplaced)]
    [TestCase(SetupFaultPoint.OperationCompleted)]
    public void FirstInstallRecoversFromJournaledFaultBoundaries(SetupFaultPoint faultPoint)
    {
        using TemporaryDirectory temporary = new();
        byte[] package = TestProductPackageFactory.Create();
        InstallationEngine crashing = new(
            temporary.InstallationRoot,
            faultInjector: new OneShotCrashInjector(faultPoint));

        Assert.That(
            () => Install(crashing, package),
            Throws.TypeOf<SetupSimulatedCrashException>());

        InstallationEngine recovered = new(temporary.InstallationRoot);
        _ = Install(recovered, package);
        Assert.That(recovered.GetCurrentVersion(), Is.EqualTo("1.0.0"));
        AssertTransactionClean(temporary.InstallationRoot);
    }

    [TestCase(SetupFaultPoint.VersionPublished)]
    [TestCase(SetupFaultPoint.PointerNextDurable)]
    [TestCase(SetupFaultPoint.CurrentReplaced)]
    [TestCase(SetupFaultPoint.PreviousPromoted)]
    [TestCase(SetupFaultPoint.OperationCompleted)]
    public void UpdateRecoversAcrossPublishAndPointerFaultBoundaries(SetupFaultPoint faultPoint)
    {
        using TemporaryDirectory temporary = new();
        _ = Install(new InstallationEngine(temporary.InstallationRoot), TestProductPackageFactory.Create("1.0.0", "a"));
        byte[] update = TestProductPackageFactory.Create("1.1.0", "b");
        InstallationEngine crashing = new(
            temporary.InstallationRoot,
            faultInjector: new OneShotCrashInjector(faultPoint));

        Assert.That(
            () => Install(crashing, update),
            Throws.TypeOf<SetupSimulatedCrashException>());

        InstallationEngine recovered = new(temporary.InstallationRoot);
        _ = Install(recovered, update);
        Assert.Multiple(() =>
        {
            Assert.That(recovered.GetCurrentVersion(), Is.EqualTo("1.1.0"));
            Assert.That(Directory.Exists(Path.Combine(temporary.InstallationRoot, "versions", "1.0.0")), Is.True);
            Assert.That(Directory.Exists(Path.Combine(temporary.InstallationRoot, "versions", "1.1.0")), Is.True);
        });
        AssertTransactionClean(temporary.InstallationRoot);
    }

    [Test]
    public void IdempotentOperationCompletedFaultRecoversWithoutInventingPrevious()
    {
        using TemporaryDirectory temporary = new();
        byte[] package = TestProductPackageFactory.Create();
        _ = Install(new InstallationEngine(temporary.InstallationRoot), package);
        InstallationEngine crashing = new(
            temporary.InstallationRoot,
            faultInjector: new OneShotCrashInjector(SetupFaultPoint.OperationCompleted));

        Assert.That(() => Install(crashing, package), Throws.TypeOf<SetupSimulatedCrashException>());

        InstallationEngine recovered = new(temporary.InstallationRoot);
        Assert.That(recovered.GetCurrentVersion(), Is.EqualTo("1.0.0"));
        Assert.That(File.Exists(Path.Combine(temporary.InstallationRoot, "current.previous")), Is.False);
        AssertTransactionClean(temporary.InstallationRoot);
    }

    [TestCase(SetupFaultPoint.PointerNextDurable)]
    [TestCase(SetupFaultPoint.CurrentReplaced)]
    [TestCase(SetupFaultPoint.PreviousPromoted)]
    [TestCase(SetupFaultPoint.OperationCompleted)]
    public void RollbackRecoversAcrossEveryPointerFaultBoundary(SetupFaultPoint faultPoint)
    {
        using TemporaryDirectory temporary = new();
        _ = Install(new InstallationEngine(temporary.InstallationRoot), TestProductPackageFactory.Create("1.0.0", "a"));
        _ = Install(new InstallationEngine(temporary.InstallationRoot), TestProductPackageFactory.Create("1.1.0", "b"));
        InstallationEngine crashing = new(
            temporary.InstallationRoot,
            faultInjector: new OneShotCrashInjector(faultPoint));

        Assert.That(() => crashing.Rollback(), Throws.TypeOf<SetupSimulatedCrashException>());

        InstallationEngine recovered = new(temporary.InstallationRoot);
        Assert.That(recovered.GetCurrentVersion(), Is.EqualTo("1.0.0"));
        AssertTransactionClean(temporary.InstallationRoot);
    }

    [Test]
    public void RecoveryRejectsCorruptPreviousBeforeReplacingCurrent()
    {
        using TemporaryDirectory temporary = new();
        LeaveUpdateAtDurableNextPointer(temporary.InstallationRoot);
        string current = Path.Combine(temporary.InstallationRoot, "current");
        string previous = Path.Combine(temporary.InstallationRoot, "current.previous");
        byte[] currentBefore = File.ReadAllBytes(current);
        const string sentinel = "corrupt previous sentinel";
        File.WriteAllText(previous, sentinel);

        Assert.That(
            () => new InstallationEngine(temporary.InstallationRoot).GetCurrentVersion(),
            Throws.TypeOf<InstallationSafetyException>());

        Assert.Multiple(() =>
        {
            Assert.That(File.ReadAllBytes(current), Is.EqualTo(currentBefore));
            Assert.That(File.ReadAllText(previous), Is.EqualTo(sentinel));
            Assert.That(File.Exists(Path.Combine(temporary.InstallationRoot, "current.next")), Is.True);
            Assert.That(File.Exists(Path.Combine(temporary.InstallationRoot, "transaction.v1.json")), Is.True);
        });
    }

    [Test]
    public void RecoveryRejectsHardLinkedPreviousWithoutTouchingExternalSentinelOrCurrent()
    {
        using TemporaryDirectory temporary = new();
        LeaveUpdateAtDurableNextPointer(temporary.InstallationRoot);
        string current = Path.Combine(temporary.InstallationRoot, "current");
        string previous = Path.Combine(temporary.InstallationRoot, "current.previous");
        string external = Path.Combine(temporary.Path, "external-previous-sentinel.json");
        byte[] currentBefore = File.ReadAllBytes(current);
        File.Copy(previous, external);
        byte[] externalBefore = File.ReadAllBytes(external);
        File.Delete(previous);
        if (!CreateHardLink(previous, external, 0))
        {
            Assert.Ignore($"The test filesystem could not create a hard link (Win32 {Marshal.GetLastWin32Error()}).");
            return;
        }

        Assert.That(
            () => new InstallationEngine(temporary.InstallationRoot).GetCurrentVersion(),
            Throws.TypeOf<InstallationSafetyException>());

        Assert.Multiple(() =>
        {
            Assert.That(File.ReadAllBytes(current), Is.EqualTo(currentBefore));
            Assert.That(File.ReadAllBytes(external), Is.EqualTo(externalBefore));
            Assert.That(File.Exists(Path.Combine(temporary.InstallationRoot, "current.next")), Is.True);
            Assert.That(File.Exists(Path.Combine(temporary.InstallationRoot, "transaction.v1.json")), Is.True);
        });
    }

    [Test]
    public void RecoveryRejectsPreviousDirectoryBeforeReplacingCurrent()
    {
        using TemporaryDirectory temporary = new();
        LeaveUpdateAtDurableNextPointer(temporary.InstallationRoot);
        string current = Path.Combine(temporary.InstallationRoot, "current");
        string previous = Path.Combine(temporary.InstallationRoot, "current.previous");
        byte[] currentBefore = File.ReadAllBytes(current);
        File.Delete(previous);
        Directory.CreateDirectory(previous);
        string sentinel = Path.Combine(previous, "sentinel.txt");
        File.WriteAllText(sentinel, "preserve");

        Assert.That(
            () => new InstallationEngine(temporary.InstallationRoot).GetCurrentVersion(),
            Throws.TypeOf<InstallationSafetyException>());

        Assert.Multiple(() =>
        {
            Assert.That(File.ReadAllBytes(current), Is.EqualTo(currentBefore));
            Assert.That(File.ReadAllText(sentinel), Is.EqualTo("preserve"));
            Assert.That(File.Exists(Path.Combine(temporary.InstallationRoot, "current.next")), Is.True);
            Assert.That(File.Exists(Path.Combine(temporary.InstallationRoot, "transaction.v1.json")), Is.True);
        });
    }

    [Test]
    public void StableStateRejectsDuplicatePreviousBeforeOpeningJournal()
    {
        using TemporaryDirectory temporary = new();
        _ = Install(new InstallationEngine(temporary.InstallationRoot), TestProductPackageFactory.Create("1.0.0", "a"));
        _ = Install(new InstallationEngine(temporary.InstallationRoot), TestProductPackageFactory.Create("1.1.0", "b"));
        string current = Path.Combine(temporary.InstallationRoot, "current");
        string previous = Path.Combine(temporary.InstallationRoot, "current.previous");
        byte[] currentBefore = File.ReadAllBytes(current);
        File.Copy(current, previous, overwrite: true);

        Assert.That(
            () => Install(
                new InstallationEngine(temporary.InstallationRoot),
                TestProductPackageFactory.Create("1.2.0", "c")),
            Throws.TypeOf<InstallationSafetyException>());

        Assert.Multiple(() =>
        {
            Assert.That(File.ReadAllBytes(current), Is.EqualTo(currentBefore));
            Assert.That(File.ReadAllBytes(previous), Is.EqualTo(currentBefore));
            Assert.That(File.Exists(Path.Combine(temporary.InstallationRoot, "transaction.v1.json")), Is.False);
            Assert.That(Directory.GetFileSystemEntries(Path.Combine(temporary.InstallationRoot, "staging")), Is.Empty);
        });
    }

    [Test]
    public void GetCurrentVersionRejectsOrphanPrevious()
    {
        using TemporaryDirectory temporary = new();
        _ = Install(new InstallationEngine(temporary.InstallationRoot), TestProductPackageFactory.Create());
        string current = Path.Combine(temporary.InstallationRoot, "current");
        string previous = Path.Combine(temporary.InstallationRoot, "current.previous");
        byte[] pointer = File.ReadAllBytes(current);
        File.Move(current, previous);

        Assert.That(
            () => new InstallationEngine(temporary.InstallationRoot).GetCurrentVersion(),
            Throws.TypeOf<InstallationSafetyException>());
        Assert.That(File.ReadAllBytes(previous), Is.EqualTo(pointer));
    }

    [Test]
    public void EarlyRecoveryPreservesJournalWhenStablePointersAreContradictory()
    {
        using TemporaryDirectory temporary = new();
        _ = Install(new InstallationEngine(temporary.InstallationRoot), TestProductPackageFactory.Create("1.0.0", "a"));
        _ = Install(new InstallationEngine(temporary.InstallationRoot), TestProductPackageFactory.Create("1.1.0", "b"));
        InstallationEngine crashing = new(
            temporary.InstallationRoot,
            faultInjector: new OneShotCrashInjector(SetupFaultPoint.PackageCopied));
        Assert.That(
            () => Install(crashing, TestProductPackageFactory.Create("1.2.0", "c")),
            Throws.TypeOf<SetupSimulatedCrashException>());
        string current = Path.Combine(temporary.InstallationRoot, "current");
        string previous = Path.Combine(temporary.InstallationRoot, "current.previous");
        File.Copy(current, previous, overwrite: true);

        Assert.That(
            () => new InstallationEngine(temporary.InstallationRoot).GetCurrentVersion(),
            Throws.TypeOf<InstallationSafetyException>());

        Assert.Multiple(() =>
        {
            Assert.That(File.Exists(Path.Combine(temporary.InstallationRoot, "transaction.v1.json")), Is.True);
            Assert.That(Directory.GetFileSystemEntries(Path.Combine(temporary.InstallationRoot, "staging")), Has.Length.EqualTo(1));
        });
    }

    [Test]
    public void RecoveryRejectsInstallJournalThatWouldDowngradeCurrent()
    {
        using TemporaryDirectory temporary = new();
        _ = Install(new InstallationEngine(temporary.InstallationRoot), TestProductPackageFactory.Create("1.0.0", "a"));
        _ = Install(new InstallationEngine(temporary.InstallationRoot), TestProductPackageFactory.Create("2.0.0", "b"));
        string currentPath = Path.Combine(temporary.InstallationRoot, "current");
        string previousPath = Path.Combine(temporary.InstallationRoot, "current.previous");
        byte[] currentBefore = File.ReadAllBytes(currentPath);
        string transactionId = Guid.NewGuid().ToString("N");
        InstallTransaction transaction = new()
        {
            TransactionId = transactionId,
            StagingId = transactionId,
            Operation = "install_update",
            Phase = "pointer_intent",
            Target = ReadPointer(previousPath),
            BeforeCurrent = ReadPointer(currentPath),
        };
        WriteJournal(temporary.InstallationRoot, transaction);
        File.Copy(previousPath, Path.Combine(temporary.InstallationRoot, "current.next"));

        Assert.That(
            () => new InstallationEngine(temporary.InstallationRoot).GetCurrentVersion(),
            Throws.TypeOf<InstallationSafetyException>());

        Assert.Multiple(() =>
        {
            Assert.That(File.ReadAllBytes(currentPath), Is.EqualTo(currentBefore));
            Assert.That(File.Exists(Path.Combine(temporary.InstallationRoot, "current.next")), Is.True);
            Assert.That(File.Exists(Path.Combine(temporary.InstallationRoot, "transaction.v1.json")), Is.True);
        });
    }

    [Test]
    public void RecoveryRejectsRollbackTargetThatWasNotPrevious()
    {
        using TemporaryDirectory temporary = new();
        _ = Install(new InstallationEngine(temporary.InstallationRoot), TestProductPackageFactory.Create("1.0.0", "a"));
        string currentPath = Path.Combine(temporary.InstallationRoot, "current");
        byte[] versionOnePointer = File.ReadAllBytes(currentPath);
        _ = Install(new InstallationEngine(temporary.InstallationRoot), TestProductPackageFactory.Create("2.0.0", "b"));
        _ = Install(new InstallationEngine(temporary.InstallationRoot), TestProductPackageFactory.Create("3.0.0", "c"));
        string previousPath = Path.Combine(temporary.InstallationRoot, "current.previous");
        byte[] currentBefore = File.ReadAllBytes(currentPath);
        byte[] previousBefore = File.ReadAllBytes(previousPath);
        InstallTransaction transaction = new()
        {
            TransactionId = Guid.NewGuid().ToString("N"),
            StagingId = null,
            Operation = "rollback",
            Phase = "pointer_intent",
            Target = ReadPointer(versionOnePointer),
            BeforeCurrent = ReadPointer(currentPath),
        };
        WriteJournal(temporary.InstallationRoot, transaction);
        File.WriteAllBytes(Path.Combine(temporary.InstallationRoot, "current.next"), versionOnePointer);

        Assert.That(
            () => new InstallationEngine(temporary.InstallationRoot).GetCurrentVersion(),
            Throws.TypeOf<InstallationSafetyException>());

        Assert.Multiple(() =>
        {
            Assert.That(File.ReadAllBytes(currentPath), Is.EqualTo(currentBefore));
            Assert.That(File.ReadAllBytes(previousPath), Is.EqualTo(previousBefore));
            Assert.That(File.Exists(Path.Combine(temporary.InstallationRoot, "current.next")), Is.True);
            Assert.That(File.Exists(Path.Combine(temporary.InstallationRoot, "transaction.v1.json")), Is.True);
        });
    }

    [Test]
    public void PublishedExtraBytesAreRejectedBeforeLaunchOrRollback()
    {
        using TemporaryDirectory temporary = new();
        InstallationEngine engine = new(temporary.InstallationRoot);
        _ = Install(engine, TestProductPackageFactory.Create());
        File.WriteAllText(
            Path.Combine(temporary.InstallationRoot, "versions", "1.0.0", "extra.bin"),
            "tamper");

        Assert.That(() => engine.GetCurrentVersion(), Throws.TypeOf<InstallationSafetyException>());
    }

    [Test]
    public void OversizedInstalledAttestationIsRejectedBeforeAllocation()
    {
        using TemporaryDirectory temporary = new();
        InstallationEngine engine = new(temporary.InstallationRoot);
        _ = Install(engine, TestProductPackageFactory.Create());
        File.WriteAllBytes(
            Path.Combine(temporary.InstallationRoot, "versions", "1.0.0", ".baxy-version.json"),
            new byte[2049]);

        Assert.That(() => engine.GetCurrentVersion(), Throws.TypeOf<InstallationSafetyException>());
    }

    [Test]
    public void ReparsePointInstallationRootIsRejectedWhenWindowsAllowsCreatingIt()
    {
        using TemporaryDirectory temporary = new();
        string target = Path.Combine(temporary.Path, "target");
        string link = Path.Combine(temporary.Path, "linked-install");
        Directory.CreateDirectory(target);
        File.WriteAllText(Path.Combine(target, "sentinel.txt"), "outside");
        _ = Baxy.Tests.NtfsTestJunction.Create(link, target);

        try
        {
            Assert.That(() => new InstallationEngine(link), Throws.TypeOf<InstallationSafetyException>());
            Assert.That(File.ReadAllText(Path.Combine(target, "sentinel.txt")), Is.EqualTo("outside"));
        }
        finally
        {
            Directory.Delete(link);
        }
    }

    private static InstallationResult Install(InstallationEngine engine, byte[] package)
    {
        using MemoryStream stream = TestProductPackageFactory.Open(package);
        return engine.InstallOrUpdate(stream);
    }

    private static void LeaveUpdateAtDurableNextPointer(string root)
    {
        _ = Install(new InstallationEngine(root), TestProductPackageFactory.Create("1.0.0", "a"));
        _ = Install(new InstallationEngine(root), TestProductPackageFactory.Create("1.1.0", "b"));
        InstallationEngine crashing = new(
            root,
            faultInjector: new OneShotCrashInjector(SetupFaultPoint.PointerNextDurable));

        Assert.That(
            () => Install(crashing, TestProductPackageFactory.Create("1.2.0", "c")),
            Throws.TypeOf<SetupSimulatedCrashException>());
    }

    private static InstallationPointer ReadPointer(string path) => ReadPointer(File.ReadAllBytes(path));

    private static InstallationPointer ReadPointer(byte[] bytes) =>
        JsonSerializer.Deserialize(bytes, SetupJsonContext.Default.InstallationPointer) ??
        throw new AssertionException("The test pointer could not be deserialized.");

    private static void WriteJournal(string root, InstallTransaction transaction)
    {
        byte[] json = JsonSerializer.SerializeToUtf8Bytes(transaction, SetupJsonContext.Default.InstallTransaction);
        File.WriteAllBytes(Path.Combine(root, "transaction.v1.json"), [.. json, (byte)'\n']);
    }

    private static void ReplaceDataSchema(string path, int dataSchema)
    {
        string text = File.ReadAllText(path);
        string changed = text.Replace(
            "\"data_schema\":1",
            $"\"data_schema\":{dataSchema}",
            StringComparison.Ordinal);
        if (string.Equals(text, changed, StringComparison.Ordinal))
        {
            throw new AssertionException("The durable identity did not contain data_schema=1.");
        }

        File.WriteAllText(path, changed);
    }

    private static void AssertTransactionClean(string root)
    {
        Assert.Multiple(() =>
        {
            Assert.That(File.Exists(Path.Combine(root, "transaction.v1.json")), Is.False);
            Assert.That(File.Exists(Path.Combine(root, "transaction.next")), Is.False);
            Assert.That(File.Exists(Path.Combine(root, "current.next")), Is.False);
            Assert.That(File.Exists(Path.Combine(root, "current.rollback")), Is.False);
            Assert.That(Directory.GetFileSystemEntries(Path.Combine(root, "staging")), Is.Empty);
        });
    }

    private sealed class OneShotCrashInjector : ISetupFaultInjector
    {
        private readonly SetupFaultPoint _target;
        private bool _thrown;

        internal OneShotCrashInjector(SetupFaultPoint target)
        {
            _target = target;
        }

        public void Checkpoint(SetupFaultPoint point)
        {
            if (!_thrown && point == _target)
            {
                _thrown = true;
                throw new SetupSimulatedCrashException(point);
            }
        }
    }

    private sealed class BlockingFaultInjector : ISetupFaultInjector, IDisposable
    {
        private readonly SetupFaultPoint _target;
        private readonly ManualResetEventSlim _entered = new(initialState: false);
        private readonly ManualResetEventSlim _released = new(initialState: false);

        internal BlockingFaultInjector(SetupFaultPoint target)
        {
            _target = target;
        }

        public void Checkpoint(SetupFaultPoint point)
        {
            if (point != _target)
            {
                return;
            }

            _entered.Set();
            _released.Wait(TimeSpan.FromSeconds(10));
        }

        internal bool WaitUntilEntered(TimeSpan timeout) => _entered.Wait(timeout);

        internal void Release() => _released.Set();

        public void Dispose()
        {
            _entered.Dispose();
            _released.Dispose();
        }
    }

    private sealed class TemporaryDirectory : IDisposable
    {
        internal TemporaryDirectory()
        {
            Path = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "baxy-setup-tests", Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(Path);
            InstallationRoot = System.IO.Path.Combine(Path, "install");
        }

        internal string Path { get; }

        internal string InstallationRoot { get; }

        public void Dispose()
        {
            if (Directory.Exists(Path))
            {
                Directory.Delete(Path, recursive: true);
            }
        }
    }

    [DllImport("kernel32.dll", EntryPoint = "CreateHardLinkW", CharSet = CharSet.Unicode, SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool CreateHardLink(string fileName, string existingFileName, nint securityAttributes);
}
