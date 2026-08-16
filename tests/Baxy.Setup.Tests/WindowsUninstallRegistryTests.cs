using System.Security.Cryptography;
using Microsoft.Win32;
using NUnit.Framework;

namespace Baxy.Setup.Tests;

[TestFixture]
public sealed class WindowsUninstallRegistryTests
{
    private const int ExactValueCount = 13;

    [Test]
    public void WriteNewOrUpdateOwnedVerified_WritesTheExactInstalledAppsContract()
    {
        using RegistryTestTree tree = RegistryTestTree.Create();
        FakeRegistryBackend backend = new();
        WindowsUninstallRegistry registry = new(backend);

        registry.WriteNewOrUpdateOwnedVerified(tree.Specification);

        WindowsUninstallRegistrySnapshot snapshot = RequireState(backend);
        Assert.That(snapshot.SubkeyNames, Is.Empty);
        Assert.That(snapshot.Values, Has.Count.EqualTo(ExactValueCount));
        AssertValue(snapshot, "DisplayName", "BAXY", RegistryValueKind.String);
        AssertValue(snapshot, "DisplayVersion", "1.2.3-beta.1+build.7", RegistryValueKind.String);
        AssertValue(snapshot, "Publisher", "BAXY", RegistryValueKind.String);
        AssertValue(snapshot, "InstallLocation", tree.Root, RegistryValueKind.String);
        AssertValue(
            snapshot,
            "UninstallString",
            $"\"{tree.Host}\" --uninstall",
            RegistryValueKind.String);
        AssertValue(
            snapshot,
            "QuietUninstallString",
            $"\"{tree.Host}\" --uninstall --keep-data --quiet",
            RegistryValueKind.String);
        AssertValue(snapshot, "DisplayIcon", $"\"{tree.Host}\",0", RegistryValueKind.String);
        AssertValue(snapshot, "NoModify", 1, RegistryValueKind.DWord);
        AssertValue(snapshot, "NoRepair", 1, RegistryValueKind.DWord);
        AssertValue(snapshot, "EstimatedSize", 4096, RegistryValueKind.DWord);
        AssertValue(snapshot, "BaxyInstallId", tree.InstallId, RegistryValueKind.String);
        AssertValue(snapshot, "BaxyDataSchema", 1, RegistryValueKind.DWord);
        AssertValue(snapshot, "BaxyStableSetupSha256", tree.HostHash, RegistryValueKind.String);
        Assert.That(
            (string)snapshot.Values["QuietUninstallString"].Value,
            Does.Contain("--keep-data"));

        backend.ResetCounters();
        registry.WriteNewOrUpdateOwnedVerified(tree.Specification);
        Assert.That(backend.SetCallCount, Is.Zero);
    }

    [Test]
    public void ProbeOwnedVerified_IsReadOnlyAndDistinguishesMissingTargetAndExplicitPrior()
    {
        using RegistryTestTree tree = RegistryTestTree.Create();
        FakeRegistryBackend backend = new();
        WindowsUninstallRegistry registry = new(backend);

        Assert.That(
            registry.ProbeOwnedVerified(tree.Specification),
            Is.EqualTo(WindowsUninstallRegistryProbe.Missing));
        Assert.That(backend.SetCallCount, Is.Zero);

        registry.WriteNewOrUpdateOwnedVerified(tree.Specification);
        backend.ResetCounters();
        Assert.That(
            registry.ProbeOwnedVerified(tree.Specification),
            Is.EqualTo(WindowsUninstallRegistryProbe.ExactTarget));
        Assert.That(backend.SetCallCount, Is.Zero);

        WindowsUninstallRegistryExpectedExisting prior = PriorFrom(tree.Specification);
        string updatedHostHash = tree.ReplaceHost([0x4d, 0x5a, 0x02, 0x00]);
        WindowsUninstallRegistrySpecification target = tree.Specification with
        {
            Version = "2.0.0",
            StableSetupSha256 = updatedHostHash,
            EstimatedSizeKilobytes = 8192,
        };
        Assert.That(
            registry.ProbeOwnedVerified(target, prior),
            Is.EqualTo(WindowsUninstallRegistryProbe.ExactExpectedExisting));
        Assert.That(backend.SetCallCount, Is.Zero);
    }

    [TestCase(TamperKind.ForeignInstallId)]
    [TestCase(TamperKind.ExtraValue)]
    [TestCase(TamperKind.ExtraSubkey)]
    [TestCase(TamperKind.WrongType)]
    [TestCase(TamperKind.ForeignCommand)]
    public void ProbeOwnedVerified_RejectsForeignStateWithoutMutation(TamperKind tamperKind)
    {
        using RegistryTestTree tree = RegistryTestTree.Create();
        FakeRegistryBackend backend = new();
        WindowsUninstallRegistry registry = new(backend);
        registry.WriteNewOrUpdateOwnedVerified(tree.Specification);
        backend.Tamper(tamperKind);
        WindowsUninstallRegistrySnapshot before = RequireState(backend);
        backend.ResetCounters();

        Assert.Throws<InstallationSafetyException>(
            () => registry.ProbeOwnedVerified(tree.Specification));

        Assert.That(backend.SetCallCount, Is.Zero);
        AssertSnapshotsEqual(RequireState(backend), before);
    }

    [Test]
    public void EnsureAbsentVerified_AcceptsAMissingKeyWithoutMutation()
    {
        FakeRegistryBackend backend = new();
        WindowsUninstallRegistry registry = new(backend);

        registry.EnsureAbsentVerified();

        Assert.That(backend.State, Is.Null);
        Assert.That(backend.SetCallCount, Is.Zero);
        Assert.That(backend.ReadCallCount, Is.EqualTo(1));
    }

    [TestCase(false)]
    [TestCase(true)]
    public void EnsureAbsentVerified_RejectsAnyExistingKeyWithoutMutation(bool foreign)
    {
        using RegistryTestTree tree = RegistryTestTree.Create();
        FakeRegistryBackend backend = new();
        WindowsUninstallRegistry registry = new(backend);
        registry.WriteNewOrUpdateOwnedVerified(tree.Specification);
        if (foreign)
        {
            backend.Tamper(TamperKind.ForeignInstallId);
        }

        WindowsUninstallRegistrySnapshot before = RequireState(backend);
        backend.ResetCounters();

        Assert.Throws<InstallationSafetyException>(() => registry.EnsureAbsentVerified());

        Assert.That(backend.SetCallCount, Is.Zero);
        Assert.That(backend.ReadCallCount, Is.EqualTo(1));
        AssertSnapshotsEqual(RequireState(backend), before);
    }

    [TestCase(0)]
    [TestCase(1)]
    [TestCase(6)]
    [TestCase(12)]
    [TestCase(13)]
    public void ReconcileOwnedFromJournal_CompletesOnlyASafeFirstInstallSubset(int retainedValues)
    {
        using RegistryTestTree tree = RegistryTestTree.Create();
        WindowsUninstallRegistrySnapshot target = BuildExpectedState(tree.Specification);
        FakeRegistryBackend backend = new();
        backend.SetState(new WindowsUninstallRegistrySnapshot(
            target.Values.Take(retainedValues)));
        WindowsUninstallRegistry registry = new(backend);

        registry.ReconcileOwnedFromJournal(tree.Specification);

        AssertSnapshotsEqual(RequireState(backend), target);
    }

    [Test]
    public void ReconcileOwnedFromJournal_ConvergesAnExplicitOldNewUpdateMixture()
    {
        using RegistryTestTree tree = RegistryTestTree.Create();
        FakeRegistryBackend backend = new();
        WindowsUninstallRegistry registry = new(backend);
        registry.WriteNewOrUpdateOwnedVerified(tree.Specification);
        WindowsUninstallRegistrySnapshot before = RequireState(backend);
        WindowsUninstallRegistryExpectedExisting expectedExisting = PriorFrom(tree.Specification);

        string updatedHostHash = tree.ReplaceHost([0x4d, 0x5a, 0x02, 0x00]);
        WindowsUninstallRegistrySpecification targetSpecification = tree.Specification with
        {
            Version = "2.0.0",
            StableSetupSha256 = updatedHostHash,
            EstimatedSizeKilobytes = 8192,
        };
        WindowsUninstallRegistrySnapshot target = BuildExpectedState(targetSpecification);
        Dictionary<string, WindowsUninstallRegistryValue> mixed = new(StringComparer.Ordinal);
        int index = 0;
        foreach ((string name, WindowsUninstallRegistryValue value) in before.Values)
        {
            mixed.Add(name, index++ % 2 == 0 ? value : target.Values[name]);
        }

        backend.SetState(new WindowsUninstallRegistrySnapshot(mixed));
        backend.ResetCounters();
        registry.ReconcileOwnedFromJournal(targetSpecification, expectedExisting);

        AssertSnapshotsEqual(RequireState(backend), target);
        Assert.That(backend.SetCallCount, Is.EqualTo(ExactValueCount));
    }

    [TestCase(TamperKind.ForeignInstallId)]
    [TestCase(TamperKind.ExtraValue)]
    [TestCase(TamperKind.ExtraSubkey)]
    [TestCase(TamperKind.WrongType)]
    [TestCase(TamperKind.ForeignCommand)]
    [TestCase(TamperKind.ForeignHash)]
    [TestCase(TamperKind.ForeignVersion)]
    [TestCase(TamperKind.ForeignSize)]
    public void ReconcileOwnedFromJournal_RejectsValuesOutsideTheJournaledTransition(
        TamperKind tamperKind)
    {
        using RegistryTestTree tree = RegistryTestTree.Create();
        FakeRegistryBackend backend = new();
        WindowsUninstallRegistry registry = new(backend);
        registry.WriteNewOrUpdateOwnedVerified(tree.Specification);
        WindowsUninstallRegistryExpectedExisting expectedExisting = PriorFrom(tree.Specification);
        backend.Tamper(tamperKind);
        WindowsUninstallRegistrySnapshot before = RequireState(backend);
        string updatedHostHash = tree.ReplaceHost([0x4d, 0x5a, 0x02, 0x00]);
        WindowsUninstallRegistrySpecification target = tree.Specification with
        {
            Version = "2.0.0",
            StableSetupSha256 = updatedHostHash,
            EstimatedSizeKilobytes = 8192,
        };
        backend.ResetCounters();

        Assert.Throws<InstallationSafetyException>(
            () => registry.ReconcileOwnedFromJournal(target, expectedExisting));

        Assert.That(backend.SetCallCount, Is.Zero);
        AssertSnapshotsEqual(RequireState(backend), before);
    }

    [Test]
    public void ReconcileOwnedFromJournal_RejectsMissingPriorStateWithoutCreatingAKey()
    {
        using RegistryTestTree tree = RegistryTestTree.Create();
        FakeRegistryBackend backend = new();
        WindowsUninstallRegistry registry = new(backend);

        Assert.Throws<InstallationSafetyException>(
            () => registry.ReconcileOwnedFromJournal(
                tree.Specification,
                PriorFrom(tree.Specification)));

        Assert.That(backend.State, Is.Null);
        Assert.That(backend.SetCallCount, Is.Zero);
    }

    [TestCase(1)]
    [TestCase(7)]
    [TestCase(13)]
    public void ReconcileOwnedFromJournal_LeavesARetryableSafeSubsetAfterAnInterruptedWrite(
        int failingSet)
    {
        using RegistryTestTree tree = RegistryTestTree.Create();
        WindowsUninstallRegistrySnapshot target = BuildExpectedState(tree.Specification);
        FakeRegistryBackend backend = new()
        {
            FaultSetOrdinal = failingSet,
            FaultAfterMutation = true,
        };
        WindowsUninstallRegistry registry = new(backend);

        Assert.Throws<InstallationSafetyException>(
            () => registry.ReconcileOwnedFromJournal(tree.Specification));
        AssertSafeSubset(RequireState(backend), target);

        backend.ResetCounters();
        registry.ReconcileOwnedFromJournal(tree.Specification);
        AssertSnapshotsEqual(RequireState(backend), target);
    }

    [Test]
    public void WriteNewOrUpdateOwnedVerified_UpdatesOnlyARecognizedOwnedSnapshot()
    {
        using RegistryTestTree tree = RegistryTestTree.Create();
        FakeRegistryBackend backend = new();
        WindowsUninstallRegistry registry = new(backend);
        registry.WriteNewOrUpdateOwnedVerified(tree.Specification);

        WindowsUninstallRegistryExpectedExisting expectedExisting = PriorFrom(tree.Specification);
        string updatedHostHash = tree.ReplaceHost([0x4d, 0x5a, 0x02, 0x00]);
        WindowsUninstallRegistrySpecification update = tree.Specification with
        {
            Version = "2.0.0",
            StableSetupSha256 = updatedHostHash,
            EstimatedSizeKilobytes = 8192,
        };
        registry.WriteNewOrUpdateOwnedVerified(update, expectedExisting);

        WindowsUninstallRegistrySnapshot snapshot = RequireState(backend);
        AssertValue(snapshot, "DisplayVersion", "2.0.0", RegistryValueKind.String);
        AssertValue(snapshot, "EstimatedSize", 8192, RegistryValueKind.DWord);
        AssertValue(snapshot, "BaxyStableSetupSha256", updatedHostHash, RegistryValueKind.String);
        AssertValue(snapshot, "BaxyInstallId", tree.InstallId, RegistryValueKind.String);
        AssertValue(snapshot, "InstallLocation", tree.Root, RegistryValueKind.String);
    }

    [TestCase(TamperKind.ForeignInstallId)]
    [TestCase(TamperKind.ExtraValue)]
    [TestCase(TamperKind.ExtraSubkey)]
    [TestCase(TamperKind.WrongType)]
    [TestCase(TamperKind.ForeignCommand)]
    [TestCase(TamperKind.ForeignHash)]
    [TestCase(TamperKind.ForeignVersion)]
    [TestCase(TamperKind.ForeignSize)]
    public void WriteNewOrUpdateOwnedVerified_RejectsAndPreservesForeignOrTamperedState(
        TamperKind tamperKind)
    {
        using RegistryTestTree tree = RegistryTestTree.Create();
        FakeRegistryBackend backend = new();
        WindowsUninstallRegistry registry = new(backend);
        registry.WriteNewOrUpdateOwnedVerified(tree.Specification);
        backend.Tamper(tamperKind);
        WindowsUninstallRegistrySnapshot before = RequireState(backend);
        backend.ResetCounters();

        Assert.Throws<InstallationSafetyException>(
            () => registry.WriteNewOrUpdateOwnedVerified(
                tree.Specification with { Version = "2.0.0" }));

        Assert.That(backend.SetCallCount, Is.Zero);
        AssertSnapshotsEqual(RequireState(backend), before);
    }

    [TestCase(1)]
    [TestCase(2)]
    [TestCase(3)]
    [TestCase(4)]
    [TestCase(5)]
    [TestCase(6)]
    [TestCase(7)]
    [TestCase(8)]
    [TestCase(9)]
    [TestCase(10)]
    [TestCase(11)]
    [TestCase(12)]
    [TestCase(13)]
    public void WriteNewOrUpdateOwnedVerified_RollsBackANewKeyAfterEverySetFailure(
        int failingSet)
    {
        using RegistryTestTree tree = RegistryTestTree.Create();
        FakeRegistryBackend backend = new()
        {
            FaultSetOrdinal = failingSet,
            FaultAfterMutation = true,
        };
        WindowsUninstallRegistry registry = new(backend);

        Assert.Throws<InstallationSafetyException>(
            () => registry.WriteNewOrUpdateOwnedVerified(tree.Specification));

        Assert.That(backend.State, Is.Null);
    }

    [Test]
    public void WriteNewOrUpdateOwnedVerified_RejectsAnIncorrectExpectedExistingSnapshotWithoutMutation()
    {
        using RegistryTestTree tree = RegistryTestTree.Create();
        FakeRegistryBackend backend = new();
        WindowsUninstallRegistry registry = new(backend);
        registry.WriteNewOrUpdateOwnedVerified(tree.Specification);
        WindowsUninstallRegistrySnapshot before = RequireState(backend);
        string updatedHostHash = tree.ReplaceHost([0x4d, 0x5a, 0x02, 0x00]);
        WindowsUninstallRegistrySpecification target = tree.Specification with
        {
            Version = "2.0.0",
            StableSetupSha256 = updatedHostHash,
            EstimatedSizeKilobytes = 8192,
        };
        WindowsUninstallRegistryExpectedExisting incorrectPrior = new(
            tree.Specification.Version,
            new string('0', 64),
            tree.Specification.EstimatedSizeKilobytes);
        backend.ResetCounters();

        Assert.Throws<InstallationSafetyException>(
            () => registry.WriteNewOrUpdateOwnedVerified(target, incorrectPrior));

        Assert.That(backend.SetCallCount, Is.Zero);
        AssertSnapshotsEqual(RequireState(backend), before);
    }

    [Test]
    public void WriteNewOrUpdateOwnedVerified_RejectsAMissingKeyWhenAnExistingSnapshotWasExpected()
    {
        using RegistryTestTree tree = RegistryTestTree.Create();
        FakeRegistryBackend backend = new();
        WindowsUninstallRegistry registry = new(backend);

        Assert.Throws<InstallationSafetyException>(
            () => registry.WriteNewOrUpdateOwnedVerified(
                tree.Specification,
                PriorFrom(tree.Specification)));

        Assert.That(backend.State, Is.Null);
        Assert.That(backend.SetCallCount, Is.Zero);
    }

    [TestCase(1)]
    [TestCase(2)]
    [TestCase(3)]
    [TestCase(4)]
    [TestCase(5)]
    [TestCase(6)]
    [TestCase(7)]
    [TestCase(8)]
    [TestCase(9)]
    [TestCase(10)]
    [TestCase(11)]
    [TestCase(12)]
    [TestCase(13)]
    public void WriteNewOrUpdateOwnedVerified_RestoresAnUpdateAfterEverySetFailure(
        int failingSet)
    {
        using RegistryTestTree tree = RegistryTestTree.Create();
        FakeRegistryBackend backend = new();
        WindowsUninstallRegistry registry = new(backend);
        registry.WriteNewOrUpdateOwnedVerified(tree.Specification);
        WindowsUninstallRegistrySnapshot before = RequireState(backend);
        WindowsUninstallRegistryExpectedExisting expectedExisting = PriorFrom(tree.Specification);
        string updatedHostHash = tree.ReplaceHost([0x4d, 0x5a, 0x02, 0x00]);
        backend.ResetCounters();
        backend.FaultSetOrdinal = failingSet;
        backend.FaultAfterMutation = true;

        Assert.Throws<InstallationSafetyException>(
            () => registry.WriteNewOrUpdateOwnedVerified(
                tree.Specification with
                {
                    Version = "2.0.0",
                    StableSetupSha256 = updatedHostHash,
                    EstimatedSizeKilobytes = 8192,
                },
                expectedExisting));

        AssertSnapshotsEqual(RequireState(backend), before);
    }

    [Test]
    public void WriteNewOrUpdateOwnedVerified_RollsBackWhenPostWriteVerificationCannotRead()
    {
        using RegistryTestTree tree = RegistryTestTree.Create();
        FakeRegistryBackend backend = new() { FaultReadOrdinal = 2 };
        WindowsUninstallRegistry registry = new(backend);

        Assert.Throws<InstallationSafetyException>(
            () => registry.WriteNewOrUpdateOwnedVerified(tree.Specification));

        Assert.That(backend.State, Is.Null);
    }

    [TestCase(DeleteFaultTiming.Before)]
    [TestCase(DeleteFaultTiming.After)]
    public void DeleteOwnedVerified_RestoresTheExactSnapshotAfterDeleteFailure(
        DeleteFaultTiming timing)
    {
        using RegistryTestTree tree = RegistryTestTree.Create();
        FakeRegistryBackend backend = new();
        WindowsUninstallRegistry registry = new(backend);
        registry.WriteNewOrUpdateOwnedVerified(tree.Specification);
        WindowsUninstallRegistrySnapshot before = RequireState(backend);
        backend.FaultDeleteTiming = timing;

        Assert.Throws<InstallationSafetyException>(
            () => registry.DeleteOwnedVerified(tree.Specification));

        AssertSnapshotsEqual(RequireState(backend), before);
    }

    [Test]
    public void DeleteOwnedVerified_DeletesOnlyAnExactOwnedSnapshotAndIsIdempotentWhenMissing()
    {
        using RegistryTestTree tree = RegistryTestTree.Create();
        FakeRegistryBackend backend = new();
        WindowsUninstallRegistry registry = new(backend);

        Assert.That(registry.DeleteOwnedVerified(tree.Specification), Is.False);
        registry.WriteNewOrUpdateOwnedVerified(tree.Specification);
        Assert.That(registry.DeleteOwnedVerified(tree.Specification), Is.True);
        Assert.That(registry.DeleteOwnedVerified(tree.Specification), Is.False);
    }

    [TestCase(TamperKind.ForeignInstallId)]
    [TestCase(TamperKind.ExtraValue)]
    [TestCase(TamperKind.ExtraSubkey)]
    [TestCase(TamperKind.WrongType)]
    [TestCase(TamperKind.ForeignCommand)]
    [TestCase(TamperKind.ForeignHash)]
    [TestCase(TamperKind.ForeignVersion)]
    [TestCase(TamperKind.ForeignSize)]
    public void DeleteOwnedVerified_RejectsAndPreservesForeignOrTamperedState(TamperKind tamperKind)
    {
        using RegistryTestTree tree = RegistryTestTree.Create();
        FakeRegistryBackend backend = new();
        WindowsUninstallRegistry registry = new(backend);
        registry.WriteNewOrUpdateOwnedVerified(tree.Specification);
        backend.Tamper(tamperKind);
        WindowsUninstallRegistrySnapshot before = RequireState(backend);

        Assert.Throws<InstallationSafetyException>(
            () => registry.DeleteOwnedVerified(tree.Specification));

        AssertSnapshotsEqual(RequireState(backend), before);
    }

    [Test]
    public void CaptureOwnedForDeletion_IsReadOnlyAndCapturesTheCanonicalExactSnapshot()
    {
        using RegistryTestTree tree = RegistryTestTree.Create();
        FakeRegistryBackend backend = new();
        WindowsUninstallRegistry registry = new(backend);
        registry.WriteNewOrUpdateOwnedVerified(tree.Specification);
        backend.ResetCounters();

        WindowsUninstallRegistryDeletionIntent intent =
            registry.CaptureOwnedForDeletion(tree.Specification);

        Assert.Multiple(() =>
        {
            Assert.That(backend.ReadCallCount, Is.EqualTo(1));
            Assert.That(backend.SetCallCount, Is.Zero);
            Assert.That(backend.DeleteCallCount, Is.Zero);
            Assert.That(intent.SubkeyNames, Is.Empty);
            Assert.That(intent.Values.Select(value => value.Name), Is.EqualTo(new[]
            {
                "DisplayName",
                "DisplayVersion",
                "Publisher",
                "InstallLocation",
                "UninstallString",
                "QuietUninstallString",
                "DisplayIcon",
                "NoModify",
                "NoRepair",
                "EstimatedSize",
                "BaxyInstallId",
                "BaxyDataSchema",
                "BaxyStableSetupSha256",
            }));
            Assert.That(intent.InstallId, Is.EqualTo(tree.InstallId));
            Assert.That(intent.InstallationRoot, Is.EqualTo(tree.Root));
            Assert.That(intent.StableSetupHostSha256, Is.EqualTo(tree.HostHash));
            Assert.That(intent.UninstallCommand, Is.EqualTo($"\"{tree.Host}\" --uninstall"));
            Assert.That(
                intent.QuietUninstallCommand,
                Is.EqualTo($"\"{tree.Host}\" --uninstall --keep-data --quiet"));
        });

        WindowsUninstallRegistrySnapshot captured = intent.CopyExpectedSnapshot();
        AssertSnapshotsEqual(captured, RequireState(backend));
        Assert.That(
            captured.Values.Where(pair => pair.Value.Kind == RegistryValueKind.DWord)
                .Select(pair => pair.Key),
            Is.EquivalentTo(new[]
            {
                "NoModify",
                "NoRepair",
                "EstimatedSize",
                "BaxyDataSchema",
            }));
    }

    [TestCase(TamperKind.ForeignInstallId)]
    [TestCase(TamperKind.ExtraValue)]
    [TestCase(TamperKind.ExtraSubkey)]
    [TestCase(TamperKind.WrongType)]
    [TestCase(TamperKind.ForeignCommand)]
    public void CaptureOwnedForDeletion_RejectsNonexactStateWithoutMutation(TamperKind tamperKind)
    {
        using RegistryTestTree tree = RegistryTestTree.Create();
        FakeRegistryBackend backend = new();
        WindowsUninstallRegistry registry = new(backend);
        registry.WriteNewOrUpdateOwnedVerified(tree.Specification);
        backend.Tamper(tamperKind);
        WindowsUninstallRegistrySnapshot before = RequireState(backend);
        backend.ResetCounters();

        Assert.Throws<InstallationSafetyException>(
            () => registry.CaptureOwnedForDeletion(tree.Specification));

        Assert.Multiple(() =>
        {
            Assert.That(backend.SetCallCount, Is.Zero);
            Assert.That(backend.DeleteCallCount, Is.Zero);
        });
        AssertSnapshotsEqual(RequireState(backend), before);
    }

    [Test]
    public void DeleteCapturedOwned_HasNoDependencyOnTheRemovedStableHostAndIsIdempotent()
    {
        using RegistryTestTree tree = RegistryTestTree.Create();
        FakeRegistryBackend backend = new();
        WindowsUninstallRegistry registry = new(backend);
        registry.WriteNewOrUpdateOwnedVerified(tree.Specification);
        WindowsUninstallRegistryDeletionIntent intent =
            registry.CaptureOwnedForDeletion(tree.Specification);
        File.Delete(tree.Host);
        backend.ResetCounters();

        Assert.That(registry.DeleteCapturedOwned(intent), Is.True);
        Assert.That(registry.DeleteCapturedOwned(intent), Is.False);

        Assert.Multiple(() =>
        {
            Assert.That(backend.State, Is.Null);
            Assert.That(backend.SetCallCount, Is.Zero);
            Assert.That(backend.DeleteCallCount, Is.EqualTo(1));
        });
    }

    [Test]
    public void DeleteCapturedOwned_ADeleteFailureBeforeMutationIsRetryableAndPreservesExactState()
    {
        using RegistryTestTree tree = RegistryTestTree.Create();
        FakeRegistryBackend backend = new();
        WindowsUninstallRegistry registry = new(backend);
        registry.WriteNewOrUpdateOwnedVerified(tree.Specification);
        WindowsUninstallRegistryDeletionIntent intent =
            registry.CaptureOwnedForDeletion(tree.Specification);
        WindowsUninstallRegistrySnapshot before = RequireState(backend);
        File.Delete(tree.Host);
        backend.ResetCounters();
        backend.FaultDeleteTiming = DeleteFaultTiming.Before;

        Assert.Throws<InstallationSafetyException>(
            () => registry.DeleteCapturedOwned(intent));

        AssertSnapshotsEqual(RequireState(backend), before);
        Assert.That(backend.SetCallCount, Is.Zero);
    }

    [Test]
    public void DeleteCapturedOwned_ADeleteFailureAfterMutationConvergesAsSuccess()
    {
        using RegistryTestTree tree = RegistryTestTree.Create();
        FakeRegistryBackend backend = new();
        WindowsUninstallRegistry registry = new(backend);
        registry.WriteNewOrUpdateOwnedVerified(tree.Specification);
        WindowsUninstallRegistryDeletionIntent intent =
            registry.CaptureOwnedForDeletion(tree.Specification);
        File.Delete(tree.Host);
        backend.FaultDeleteTiming = DeleteFaultTiming.After;

        Assert.That(registry.DeleteCapturedOwned(intent), Is.True);
        Assert.That(backend.State, Is.Null);
    }

    [TestCase(TamperKind.ForeignInstallId)]
    [TestCase(TamperKind.ExtraValue)]
    [TestCase(TamperKind.ExtraSubkey)]
    [TestCase(TamperKind.WrongType)]
    [TestCase(TamperKind.ForeignCommand)]
    [TestCase(TamperKind.ForeignHash)]
    [TestCase(TamperKind.ForeignVersion)]
    [TestCase(TamperKind.ForeignSize)]
    [TestCase(TamperKind.MissingValue)]
    public void DeleteCapturedOwned_RejectsAndPreservesForeignOrPartialState(
        TamperKind tamperKind)
    {
        using RegistryTestTree tree = RegistryTestTree.Create();
        FakeRegistryBackend backend = new();
        WindowsUninstallRegistry registry = new(backend);
        registry.WriteNewOrUpdateOwnedVerified(tree.Specification);
        WindowsUninstallRegistryDeletionIntent intent =
            registry.CaptureOwnedForDeletion(tree.Specification);
        backend.Tamper(tamperKind);
        WindowsUninstallRegistrySnapshot foreign = RequireState(backend);
        File.Delete(tree.Host);
        backend.ResetCounters();

        Assert.Throws<InstallationSafetyException>(
            () => registry.DeleteCapturedOwned(intent));

        Assert.That(backend.DeleteCallCount, Is.Zero);
        AssertSnapshotsEqual(RequireState(backend), foreign);
    }

    [Test]
    public void DeleteCapturedOwned_FailsClosedIfForeignStateAppearsAfterDeleteFailure()
    {
        using RegistryTestTree tree = RegistryTestTree.Create();
        FakeRegistryBackend backend = new();
        WindowsUninstallRegistry registry = new(backend);
        registry.WriteNewOrUpdateOwnedVerified(tree.Specification);
        WindowsUninstallRegistryDeletionIntent intent =
            registry.CaptureOwnedForDeletion(tree.Specification);
        WindowsUninstallRegistrySnapshot replacement = RequireState(backend);
        Dictionary<string, WindowsUninstallRegistryValue> foreignValues =
            new(replacement.Values, StringComparer.Ordinal)
            {
                ["BaxyInstallId"] = new(
                    Guid.NewGuid().ToString("N"),
                    RegistryValueKind.String),
            };
        backend.StateAfterDeleteFailure = new WindowsUninstallRegistrySnapshot(foreignValues);
        backend.FaultDeleteTiming = DeleteFaultTiming.Before;
        File.Delete(tree.Host);

        Assert.Throws<InstallationSafetyException>(
            () => registry.DeleteCapturedOwned(intent));

        Assert.That(
            RequireState(backend).Values["BaxyInstallId"].Value,
            Is.Not.EqualTo(tree.InstallId));
    }

    [Test]
    public void SpecificationValidation_RejectsInvalidIdentityVersionSchemaPathsHashAndSizeBeforeRead()
    {
        using RegistryTestTree tree = RegistryTestTree.Create();
        WindowsUninstallRegistrySpecification[] invalid =
        [
            tree.Specification with { InstallId = tree.InstallId.ToUpperInvariant() },
            tree.Specification with { Version = "01.2.3" },
            tree.Specification with { DataSchema = 2 },
            tree.Specification with { InstallationRoot = "relative-root" },
            tree.Specification with { StableSetupHost = Path.Combine(tree.Root, "foreign.exe") },
            tree.Specification with { StableSetupSha256 = tree.HostHash.ToUpperInvariant() },
            tree.Specification with { StableSetupSha256 = new string('0', 64) },
            tree.Specification with { EstimatedSizeKilobytes = 0 },
        ];

        foreach (WindowsUninstallRegistrySpecification specification in invalid)
        {
            FakeRegistryBackend backend = new();
            WindowsUninstallRegistry registry = new(backend);
            Assert.Throws<InstallationSafetyException>(
                () => registry.WriteNewOrUpdateOwnedVerified(specification));
            Assert.That(backend.ReadCallCount, Is.Zero);
            Assert.That(backend.State, Is.Null);
        }
    }

    [Test]
    public void SpecificationValidation_RejectsANonRegularStableHost()
    {
        using RegistryTestTree tree = RegistryTestTree.Create();
        File.Delete(tree.Host);
        Directory.CreateDirectory(tree.Host);
        WindowsUninstallRegistry registry = new(new FakeRegistryBackend());

        Assert.Throws<InstallationSafetyException>(
            () => registry.WriteNewOrUpdateOwnedVerified(tree.Specification));
    }

    [Test]
    public void Registry64Backend_RoundTripsOnlyAnIsolatedHkcuTestSubkey()
    {
        using RegistryTestTree tree = RegistryTestTree.Create();
        string subkey = $@"Software\BAXY.Tests-{Guid.NewGuid():N}";
        try
        {
            WindowsUninstallRegistry registry = WindowsUninstallRegistry.CreateForTestSubkey(subkey);
            registry.WriteNewOrUpdateOwnedVerified(tree.Specification);

            using RegistryKey currentUser = RegistryKey.OpenBaseKey(
                RegistryHive.CurrentUser,
                RegistryView.Registry64);
            using (RegistryKey? key = currentUser.OpenSubKey(subkey, writable: false))
            {
                Assert.That(key, Is.Not.Null);
                Assert.That(key!.GetValue("BaxyInstallId"), Is.EqualTo(tree.InstallId));
                Assert.That(key.GetValueKind("BaxyDataSchema"), Is.EqualTo(RegistryValueKind.DWord));
                Assert.That(key.GetValue("QuietUninstallString"),
                    Is.EqualTo($"\"{tree.Host}\" --uninstall --keep-data --quiet"));
            }

            Assert.That(registry.DeleteOwnedVerified(tree.Specification), Is.True);
            using RegistryKey? deleted = currentUser.OpenSubKey(subkey, writable: false);
            Assert.That(deleted, Is.Null);
        }
        finally
        {
            using RegistryKey currentUser = RegistryKey.OpenBaseKey(
                RegistryHive.CurrentUser,
                RegistryView.Registry64);
            currentUser.DeleteSubKeyTree(subkey, throwOnMissingSubKey: false);
        }
    }

    [Test]
    public void Registry64Backend_JournalDeletionRemainsIndependentAfterStableHostRemoval()
    {
        using RegistryTestTree tree = RegistryTestTree.Create();
        string subkey = $@"Software\BAXY.Tests-{Guid.NewGuid():N}";
        try
        {
            WindowsUninstallRegistry registry = WindowsUninstallRegistry.CreateForTestSubkey(subkey);
            registry.WriteNewOrUpdateOwnedVerified(tree.Specification);
            WindowsUninstallRegistryDeletionIntent intent =
                registry.CaptureOwnedForDeletion(tree.Specification);
            File.Delete(tree.Host);

            Assert.That(registry.DeleteCapturedOwned(intent), Is.True);
            Assert.That(registry.DeleteCapturedOwned(intent), Is.False);

            using RegistryKey currentUser = RegistryKey.OpenBaseKey(
                RegistryHive.CurrentUser,
                RegistryView.Registry64);
            using RegistryKey? deleted = currentUser.OpenSubKey(subkey, writable: false);
            Assert.That(deleted, Is.Null);
        }
        finally
        {
            using RegistryKey currentUser = RegistryKey.OpenBaseKey(
                RegistryHive.CurrentUser,
                RegistryView.Registry64);
            currentUser.DeleteSubKeyTree(subkey, throwOnMissingSubKey: false);
        }
    }

    private static WindowsUninstallRegistrySnapshot RequireState(FakeRegistryBackend backend)
    {
        Assert.That(backend.State, Is.Not.Null);
        return Clone(backend.State!);
    }

    private static void AssertValue(
        WindowsUninstallRegistrySnapshot snapshot,
        string name,
        object value,
        RegistryValueKind kind)
    {
        Assert.That(snapshot.Values.ContainsKey(name), Is.True, name);
        Assert.Multiple(() =>
        {
            Assert.That(snapshot.Values[name].Value, Is.EqualTo(value), name);
            Assert.That(snapshot.Values[name].Kind, Is.EqualTo(kind), name);
        });
    }

    private static void AssertSnapshotsEqual(
        WindowsUninstallRegistrySnapshot actual,
        WindowsUninstallRegistrySnapshot expected)
    {
        Assert.That(actual.SubkeyNames, Is.EqualTo(expected.SubkeyNames));
        Assert.That(actual.Values.Keys, Is.EquivalentTo(expected.Values.Keys));
        foreach ((string name, WindowsUninstallRegistryValue value) in expected.Values)
        {
            AssertValue(actual, name, value.Value, value.Kind);
        }
    }

    private static WindowsUninstallRegistrySnapshot Clone(WindowsUninstallRegistrySnapshot snapshot) =>
        new(snapshot.Values, snapshot.SubkeyNames);

    private static WindowsUninstallRegistrySnapshot BuildExpectedState(
        WindowsUninstallRegistrySpecification specification)
    {
        FakeRegistryBackend backend = new();
        new WindowsUninstallRegistry(backend).WriteNewOrUpdateOwnedVerified(specification);
        return RequireState(backend);
    }

    private static void AssertSafeSubset(
        WindowsUninstallRegistrySnapshot actual,
        WindowsUninstallRegistrySnapshot target)
    {
        Assert.That(actual.SubkeyNames, Is.Empty);
        foreach ((string name, WindowsUninstallRegistryValue value) in actual.Values)
        {
            Assert.That(target.Values.ContainsKey(name), Is.True, name);
            AssertValue(target, name, value.Value, value.Kind);
        }
    }

    private static WindowsUninstallRegistryExpectedExisting PriorFrom(
        WindowsUninstallRegistrySpecification specification) =>
        new(
            specification.Version,
            specification.StableSetupSha256,
            specification.EstimatedSizeKilobytes);

    public enum TamperKind
    {
        ForeignInstallId,
        ExtraValue,
        ExtraSubkey,
        WrongType,
        ForeignCommand,
        ForeignHash,
        ForeignVersion,
        ForeignSize,
        MissingValue,
    }

    public enum DeleteFaultTiming
    {
        None,
        Before,
        After,
    }

    private sealed class FakeRegistryBackend : IWindowsUninstallRegistryBackend
    {
        internal WindowsUninstallRegistrySnapshot? State { get; private set; }

        internal int? FaultSetOrdinal { get; set; }

        internal int? FaultReadOrdinal { get; set; }

        internal bool FaultAfterMutation { get; set; }

        internal DeleteFaultTiming FaultDeleteTiming { get; set; }

        internal int SetCallCount { get; private set; }

        internal int ReadCallCount { get; private set; }

        internal int DeleteCallCount { get; private set; }

        internal WindowsUninstallRegistrySnapshot? StateAfterDeleteFailure { get; set; }

        public WindowsUninstallRegistrySnapshot? Read()
        {
            ReadCallCount++;
            if (FaultReadOrdinal == ReadCallCount)
            {
                FaultReadOrdinal = null;
                throw new IOException("Injected registry read failure.");
            }

            return State is null ? null : Clone(State);
        }

        public void CreateWithOwnershipMarkers(string installId, string installationRoot)
        {
            if (State is not null)
            {
                throw new IOException("Fake registry key already exists.");
            }

            State = new WindowsUninstallRegistrySnapshot(
            [
                new("BaxyInstallId", new WindowsUninstallRegistryValue(
                    installId,
                    RegistryValueKind.String)),
                new("InstallLocation", new WindowsUninstallRegistryValue(
                    installationRoot,
                    RegistryValueKind.String)),
            ]);
        }

        public void SetValue(string name, object value, RegistryValueKind kind)
        {
            SetCallCount++;
            bool fault = FaultSetOrdinal == SetCallCount;
            if (fault && !FaultAfterMutation)
            {
                FaultSetOrdinal = null;
                throw new IOException("Injected registry SetValue failure.");
            }

            if (State is null)
            {
                throw new IOException("Fake registry key is missing.");
            }

            Dictionary<string, WindowsUninstallRegistryValue> values =
                new(State.Values, StringComparer.Ordinal)
                {
                    [name] = new WindowsUninstallRegistryValue(value, kind),
                };
            State = new WindowsUninstallRegistrySnapshot(values, State.SubkeyNames);
            if (fault)
            {
                FaultSetOrdinal = null;
                throw new IOException("Injected registry SetValue failure after mutation.");
            }
        }

        public void DeleteKey()
        {
            DeleteCallCount++;
            if (FaultDeleteTiming == DeleteFaultTiming.Before)
            {
                FaultDeleteTiming = DeleteFaultTiming.None;
                if (StateAfterDeleteFailure is not null)
                {
                    State = Clone(StateAfterDeleteFailure);
                    StateAfterDeleteFailure = null;
                }

                throw new IOException("Injected registry delete failure.");
            }

            if (State is null)
            {
                throw new IOException("Fake registry key is missing.");
            }

            State = null;
            if (FaultDeleteTiming == DeleteFaultTiming.After)
            {
                FaultDeleteTiming = DeleteFaultTiming.None;
                throw new IOException("Injected registry delete failure after mutation.");
            }
        }

        internal void ResetCounters()
        {
            SetCallCount = 0;
            ReadCallCount = 0;
            DeleteCallCount = 0;
        }

        internal void SetState(WindowsUninstallRegistrySnapshot? snapshot)
        {
            State = snapshot is null ? null : Clone(snapshot);
        }

        internal void Tamper(TamperKind tamperKind)
        {
            WindowsUninstallRegistrySnapshot snapshot = State ??
                throw new InvalidOperationException("A fake registry key is required.");
            Dictionary<string, WindowsUninstallRegistryValue> values =
                new(snapshot.Values, StringComparer.Ordinal);
            string[] subkeys = snapshot.SubkeyNames.ToArray();
            switch (tamperKind)
            {
                case TamperKind.ForeignInstallId:
                    values["BaxyInstallId"] = new(
                        Guid.NewGuid().ToString("N"),
                        RegistryValueKind.String);
                    break;
                case TamperKind.ExtraValue:
                    values["ForeignValue"] = new("do-not-touch", RegistryValueKind.String);
                    break;
                case TamperKind.ExtraSubkey:
                    subkeys = ["ForeignSubkey"];
                    break;
                case TamperKind.WrongType:
                    values["NoModify"] = new("1", RegistryValueKind.String);
                    break;
                case TamperKind.ForeignCommand:
                    values["QuietUninstallString"] = new(
                        "foreign.exe --quiet",
                        RegistryValueKind.String);
                    break;
                case TamperKind.ForeignHash:
                    values["BaxyStableSetupSha256"] = new(
                        new string('0', 64),
                        RegistryValueKind.String);
                    break;
                case TamperKind.ForeignVersion:
                    values["DisplayVersion"] = new("9.9.9", RegistryValueKind.String);
                    break;
                case TamperKind.ForeignSize:
                    values["EstimatedSize"] = new(123456, RegistryValueKind.DWord);
                    break;
                case TamperKind.MissingValue:
                    values.Remove("Publisher");
                    break;
                default:
                    throw new ArgumentOutOfRangeException(nameof(tamperKind));
            }

            State = new WindowsUninstallRegistrySnapshot(values, subkeys);
        }
    }

    private sealed class RegistryTestTree : IDisposable
    {
        private RegistryTestTree(
            string outerRoot,
            string root,
            string host,
            string hostHash,
            string installId)
        {
            OuterRoot = outerRoot;
            Root = root;
            Host = host;
            HostHash = hostHash;
            InstallId = installId;
            Specification = new WindowsUninstallRegistrySpecification(
                installId,
                "1.2.3-beta.1+build.7",
                DataSchema: 1,
                root,
                host,
                hostHash,
                EstimatedSizeKilobytes: 4096);
        }

        internal string OuterRoot { get; }

        internal string Root { get; }

        internal string Host { get; }

        internal string HostHash { get; }

        internal string InstallId { get; }

        internal WindowsUninstallRegistrySpecification Specification { get; }

        internal static RegistryTestTree Create()
        {
            string outerRoot = Path.Combine(
                Path.GetTempPath(),
                $"baxy-registry-{Guid.NewGuid():N}");
            string root = Path.Combine(outerRoot, "BAXY");
            Directory.CreateDirectory(root);
            string host = Path.Combine(root, "Baxy.Setup.exe");
            byte[] bytes = [0x4d, 0x5a, 0x42, 0x41, 0x58, 0x59];
            File.WriteAllBytes(host, bytes);
            string hash = Convert.ToHexStringLower(SHA256.HashData(bytes));
            return new RegistryTestTree(
                outerRoot,
                root,
                host,
                hash,
                Guid.NewGuid().ToString("N"));
        }

        internal string ReplaceHost(byte[] bytes)
        {
            File.WriteAllBytes(Host, bytes);
            return Convert.ToHexStringLower(SHA256.HashData(bytes));
        }

        public void Dispose()
        {
            if (Directory.Exists(OuterRoot))
            {
                Directory.Delete(OuterRoot, recursive: true);
            }
        }
    }
}
