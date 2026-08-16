using System.Runtime.InteropServices;
using System.Security.Cryptography;
using NUnit.Framework;

namespace Baxy.Setup.Tests;

[TestFixture]
public sealed class StableSetupHostManagerTests
{
    [Test]
    public void VerifyUnchangedStableExactRequiresStableAndNoTransactionArtifacts()
    {
        using HostTestTree tree = HostTestTree.Create();
        File.WriteAllBytes(tree.Paths.Stable, tree.TargetBytes);

        tree.Manager.VerifyUnchangedStableExact(tree.Target);

        File.WriteAllBytes(tree.Paths.Next, tree.TargetBytes);
        Assert.That(
            () => tree.Manager.VerifyUnchangedStableExact(tree.Target),
            Throws.TypeOf<InstallationSafetyException>());
        File.Delete(tree.Paths.Next);
        File.WriteAllBytes(tree.Paths.Previous, tree.TargetBytes);
        Assert.That(
            () => tree.Manager.VerifyUnchangedStableExact(tree.Target),
            Throws.TypeOf<InstallationSafetyException>());
    }

    [Test]
    public void VerifyExact_IsReadOnlyAndRequiresBothHashAndLength()
    {
        using HostTestTree tree = HostTestTree.Create();
        tree.WriteStable(tree.TargetBytes);
        DateTime unchanged = DateTime.UtcNow.AddHours(-2);
        File.SetLastWriteTimeUtc(tree.Paths.Stable, unchanged);

        tree.Manager.VerifyStableExact(tree.Target);
        StableSetupHostManager.VerifyExact(tree.Paths.Stable, tree.Target);

        Assert.Multiple(() =>
        {
            Assert.That(File.GetLastWriteTimeUtc(tree.Paths.Stable), Is.EqualTo(unchanged));
            Assert.That(File.ReadAllBytes(tree.Paths.Stable), Is.EqualTo(tree.TargetBytes));
            Assert.Throws<InstallationSafetyException>(() =>
                StableSetupHostManager.VerifyExact(
                    tree.Paths.Stable,
                    tree.Target with { Bytes = tree.Target.Bytes + 1 }));
            Assert.Throws<InstallationSafetyException>(() =>
                StableSetupHostManager.VerifyExact(
                    tree.Paths.Stable,
                    tree.Target with { Sha256 = new string('0', 64) }));
        });
        Assert.That(File.ReadAllBytes(tree.Paths.Stable), Is.EqualTo(tree.TargetBytes));
    }

    [Test]
    public void VerifyExact_RejectsMalformedIdentitiesMissingFilesAndDirectories()
    {
        using HostTestTree tree = HostTestTree.Create();
        tree.WriteStable(tree.TargetBytes);
        StableSetupHostIdentity[] malformed =
        [
            tree.Target with { Bytes = 0 },
            tree.Target with { Bytes = -1 },
            tree.Target with { Sha256 = tree.Target.Sha256.ToUpperInvariant() },
            tree.Target with { Sha256 = tree.Target.Sha256[..63] },
            tree.Target with { Sha256 = new string('g', 64) },
        ];

        foreach (StableSetupHostIdentity identity in malformed)
        {
            Assert.Throws<InstallationSafetyException>(() =>
                StableSetupHostManager.VerifyExact(tree.Paths.Stable, identity));
        }

        string missing = Path.Combine(tree.Root, "missing.exe");
        string directory = Path.Combine(tree.Root, "directory.exe");
        Directory.CreateDirectory(directory);
        Assert.Multiple(() =>
        {
            Assert.Throws<InstallationSafetyException>(() =>
                StableSetupHostManager.VerifyExact(missing, tree.Target));
            Assert.Throws<InstallationSafetyException>(() =>
                StableSetupHostManager.VerifyExact(directory, tree.Target));
        });
        Assert.That(File.ReadAllBytes(tree.Paths.Stable), Is.EqualTo(tree.TargetBytes));
    }

    [Test]
    public void Constructor_RequiresCanonicalDistinctSiblingPaths()
    {
        using HostTestTree tree = HostTestTree.Create();
        string other = Path.Combine(tree.Root, "other");
        Directory.CreateDirectory(other);

        Assert.Multiple(() =>
        {
            Assert.Throws<InstallationSafetyException>(() => new StableSetupHostManager(
                tree.Paths with { Stable = Path.Combine(tree.Root, "setup.exe") }));
            Assert.Throws<InstallationSafetyException>(() => new StableSetupHostManager(
                tree.Paths with { Next = tree.Paths.Stable }));
            Assert.Throws<InstallationSafetyException>(() => new StableSetupHostManager(
                tree.Paths with { Previous = Path.Combine(other, "previous.exe") }));
            Assert.Throws<InstallationSafetyException>(() => new StableSetupHostManager(
                tree.Paths with { Next = "relative-next.exe" }));
            Assert.Throws<InstallationSafetyException>(() => new StableSetupHostManager(
                tree.Paths with { Next = tree.Paths.Next + ":stream" }));
        });
    }

    [Test]
    public void StageCandidate_FirstInstallCreatesOnlyAnExactDurableNextFile()
    {
        using HostTestTree tree = HostTestTree.Create();

        tree.Manager.StageCandidate(tree.TargetSource, tree.Target);

        Assert.Multiple(() =>
        {
            Assert.That(tree.Manager.Inspect(null, tree.Target).State,
                Is.EqualTo(StableSetupHostRecoveryState.FirstInstallStaged));
            Assert.That(File.Exists(tree.Paths.Stable), Is.False);
            Assert.That(File.Exists(tree.Paths.Previous), Is.False);
            Assert.That(File.ReadAllBytes(tree.Paths.Next), Is.EqualTo(tree.TargetBytes));
            Assert.That(File.ReadAllBytes(tree.TargetSource), Is.EqualTo(tree.TargetBytes));
        });
    }

    [Test]
    public void StageCandidate_UpdateRequiresAnExplicitExactPriorIdentity()
    {
        using HostTestTree tree = HostTestTree.Create();
        tree.WriteStable(tree.BeforeBytes);

        tree.Manager.StageCandidate(tree.TargetSource, tree.Target, tree.Before);

        Assert.That(
            tree.Manager.Inspect(tree.Before, tree.Target).State,
            Is.EqualTo(StableSetupHostRecoveryState.UpdateStaged));
        Assert.That(File.ReadAllBytes(tree.Paths.Stable), Is.EqualTo(tree.BeforeBytes));
        Assert.That(File.ReadAllBytes(tree.Paths.Next), Is.EqualTo(tree.TargetBytes));
    }

    [Test]
    public void StageCandidate_RejectsIdentityMismatchWithoutLeavingANextFile()
    {
        using HostTestTree tree = HostTestTree.Create();
        StableSetupHostIdentity wrongHash = tree.Target with { Sha256 = new string('0', 64) };

        Assert.Throws<InstallationSafetyException>(() =>
            tree.Manager.StageCandidate(tree.TargetSource, wrongHash));

        Assert.Multiple(() =>
        {
            Assert.That(File.Exists(tree.Paths.Next), Is.False);
            Assert.That(File.ReadAllBytes(tree.TargetSource), Is.EqualTo(tree.TargetBytes));
        });
    }

    [Test]
    public void StageCandidate_RejectsStableAliasesAndUsesVerifyForIdempotence()
    {
        using HostTestTree tree = HostTestTree.Create();
        tree.WriteStable(tree.TargetBytes);

        tree.Manager.VerifyStableExact(tree.Target);
        Assert.Throws<InstallationSafetyException>(() =>
            tree.Manager.StageCandidate(tree.Paths.Stable, tree.Before, tree.Target));

        Assert.Multiple(() =>
        {
            Assert.That(File.ReadAllBytes(tree.Paths.Stable), Is.EqualTo(tree.TargetBytes));
            Assert.That(File.Exists(tree.Paths.Next), Is.False);
            Assert.That(File.Exists(tree.Paths.Previous), Is.False);
        });
    }

    [Test]
    public void StageCandidate_RejectsForeignTransactionArtifactsWithoutMutation()
    {
        using HostTestTree tree = HostTestTree.Create();
        HostTestTree.Write(tree.Paths.Next, tree.ForeignBytes);
        byte[] nextBefore = File.ReadAllBytes(tree.Paths.Next);

        Assert.Throws<InstallationSafetyException>(() =>
            tree.Manager.StageCandidate(tree.TargetSource, tree.Target));

        Assert.That(File.ReadAllBytes(tree.Paths.Next), Is.EqualTo(nextBefore));
        Assert.That(File.Exists(tree.Paths.Stable), Is.False);
    }

    [Test]
    public void StageCandidate_RejectsAdsHardLinksAndDirectories()
    {
        using HostTestTree adsTree = HostTestTree.Create();
        File.WriteAllText(adsTree.TargetSource + ":foreign", "foreign stream");
        Assert.Throws<InstallationSafetyException>(() =>
            adsTree.Manager.StageCandidate(adsTree.TargetSource, adsTree.Target));
        Assert.That(File.Exists(adsTree.Paths.Next), Is.False);

        using HostTestTree hardLinkTree = HostTestTree.Create();
        string hardLink = Path.Combine(hardLinkTree.Root, "candidate-hardlink.exe");
        Assert.That(CreateHardLink(hardLink, hardLinkTree.TargetSource, 0), Is.True);
        Assert.Throws<InstallationSafetyException>(() =>
            hardLinkTree.Manager.StageCandidate(hardLink, hardLinkTree.Target));
        Assert.That(File.Exists(hardLinkTree.Paths.Next), Is.False);

        using HostTestTree directoryTree = HostTestTree.Create();
        string directory = Path.Combine(directoryTree.Root, "candidate-directory.exe");
        Directory.CreateDirectory(directory);
        Assert.Throws<InstallationSafetyException>(() =>
            directoryTree.Manager.StageCandidate(directory, directoryTree.Target));
        Assert.That(File.Exists(directoryTree.Paths.Next), Is.False);
    }

    [Test]
    public void StageCandidate_RejectsAReparseSourceWhenWindowsAllowsCreatingIt()
    {
        using HostTestTree tree = HostTestTree.Create();
        string link = Path.Combine(tree.Root, "candidate-link.exe");
        string target = Path.Combine(tree.Root, "candidate-reparse-target");
        Directory.CreateDirectory(target);
        _ = Baxy.Tests.NtfsTestJunction.Create(link, target);

        try
        {
            Assert.Throws<InstallationSafetyException>(() =>
                tree.Manager.StageCandidate(link, tree.Target));
            Assert.That(File.Exists(tree.Paths.Next), Is.False);
        }
        finally
        {
            if (Path.Exists(link))
            {
                Directory.Delete(link);
            }
        }
    }

    [Test]
    public void PublishFirstInstall_UsesCreateNewSemanticsAndPreservesForeignDestination()
    {
        using HostTestTree tree = HostTestTree.Create();
        tree.Manager.StageCandidate(tree.TargetSource, tree.Target);
        tree.WriteStable(tree.ForeignBytes);
        byte[] foreign = File.ReadAllBytes(tree.Paths.Stable);

        Assert.Throws<InstallationSafetyException>(() =>
            tree.Manager.PublishFirstInstall(tree.Target));

        Assert.Multiple(() =>
        {
            Assert.That(File.ReadAllBytes(tree.Paths.Stable), Is.EqualTo(foreign));
            Assert.That(File.ReadAllBytes(tree.Paths.Next), Is.EqualTo(tree.TargetBytes));
            Assert.That(File.Exists(tree.Paths.Previous), Is.False);
        });
    }

    [Test]
    public void PublishFirstInstall_MovesTheExactTargetWithoutBackup()
    {
        using HostTestTree tree = HostTestTree.Create();
        tree.Manager.StageCandidate(tree.TargetSource, tree.Target);

        tree.Manager.PublishFirstInstall(tree.Target);

        Assert.Multiple(() =>
        {
            Assert.That(tree.Manager.Inspect(null, tree.Target).State,
                Is.EqualTo(StableSetupHostRecoveryState.TargetPublished));
            Assert.That(File.ReadAllBytes(tree.Paths.Stable), Is.EqualTo(tree.TargetBytes));
            Assert.That(File.Exists(tree.Paths.Next), Is.False);
            Assert.That(File.Exists(tree.Paths.Previous), Is.False);
        });
    }

    [Test]
    public void PublishUpdate_CreatesAnExactBackupThenDurablyMovesTheTarget()
    {
        using HostTestTree tree = HostTestTree.Create();
        tree.WriteStable(tree.BeforeBytes);
        File.SetAttributes(tree.Paths.Stable, FileAttributes.Hidden);
        tree.Manager.StageCandidate(tree.TargetSource, tree.Target, tree.Before);

        tree.Manager.PublishUpdate(tree.Before, tree.Target);

        Assert.Multiple(() =>
        {
            Assert.That(tree.Manager.Inspect(tree.Before, tree.Target).State,
                Is.EqualTo(StableSetupHostRecoveryState.UpdateReplaced));
            Assert.That(File.ReadAllBytes(tree.Paths.Stable), Is.EqualTo(tree.TargetBytes));
            Assert.That(File.ReadAllBytes(tree.Paths.Previous), Is.EqualTo(tree.BeforeBytes));
            Assert.That(File.Exists(tree.Paths.Next), Is.False);
            Assert.That(
                (File.GetAttributes(tree.Paths.Stable) & FileAttributes.Hidden) != 0,
                Is.False);
        });
    }

    [Test]
    public void PublishUpdate_RefusesAnIncorrectPriorAndPreservesEveryArtifact()
    {
        using HostTestTree tree = HostTestTree.Create();
        tree.WriteStable(tree.BeforeBytes);
        tree.Manager.StageCandidate(tree.TargetSource, tree.Target, tree.Before);
        StableSetupHostIdentity wrongBefore = HostTestTree.Identity([0x4d, 0x5a, 0x99]);

        Assert.Throws<InstallationSafetyException>(() =>
            tree.Manager.PublishUpdate(wrongBefore, tree.Target));

        Assert.Multiple(() =>
        {
            Assert.That(File.ReadAllBytes(tree.Paths.Stable), Is.EqualTo(tree.BeforeBytes));
            Assert.That(File.ReadAllBytes(tree.Paths.Next), Is.EqualTo(tree.TargetBytes));
            Assert.That(File.Exists(tree.Paths.Previous), Is.False);
        });
    }

    [Test]
    public void PublishUpdate_WhenDestinationDeniesDelete_PreservesARecoverableBackupReadyState()
    {
        using HostTestTree tree = HostTestTree.Create();
        tree.WriteStable(tree.BeforeBytes);
        tree.Manager.StageCandidate(tree.TargetSource, tree.Target, tree.Before);
        using FileStream blocker = new(
            tree.Paths.Stable,
            FileMode.Open,
            FileAccess.Read,
            FileShare.Read);

        Assert.Throws<InstallationSafetyException>(() =>
            tree.Manager.PublishUpdate(tree.Before, tree.Target));

        Assert.Multiple(() =>
        {
            Assert.That(tree.Manager.Inspect(tree.Before, tree.Target).State,
                Is.EqualTo(StableSetupHostRecoveryState.UpdateBackupReady));
            Assert.That(File.ReadAllBytes(tree.Paths.Stable), Is.EqualTo(tree.BeforeBytes));
            Assert.That(File.ReadAllBytes(tree.Paths.Next), Is.EqualTo(tree.TargetBytes));
            Assert.That(File.ReadAllBytes(tree.Paths.Previous), Is.EqualTo(tree.BeforeBytes));
        });
    }

    [Test]
    public void Inspect_ExhaustivelyClassifiesFirstInstallArtifactCombinations()
    {
        using HostTestTree tree = HostTestTree.Create();
        ArtifactFixture[] fixtures =
        [
            ArtifactFixture.Missing,
            ArtifactFixture.Target,
            ArtifactFixture.Foreign,
        ];

        foreach (ArtifactFixture stable in fixtures)
            foreach (ArtifactFixture next in fixtures)
                foreach (ArtifactFixture previous in fixtures)
                {
                    tree.SetArtifacts(stable, next, previous);
                    StableSetupHostRecoveryState expected = ExpectedFirstInstallState(stable, next, previous);
                    StableSetupHostInspection actual = tree.Manager.Inspect(null, tree.Target);
                    Assert.That(actual.State, Is.EqualTo(expected),
                        $"stable={stable}, next={next}, previous={previous}");
                }
    }

    [Test]
    public void Inspect_ExhaustivelyClassifiesUpdateArtifactCombinations()
    {
        using HostTestTree tree = HostTestTree.Create();
        ArtifactFixture[] fixtures = Enum.GetValues<ArtifactFixture>();

        foreach (ArtifactFixture stable in fixtures)
            foreach (ArtifactFixture next in fixtures)
                foreach (ArtifactFixture previous in fixtures)
                {
                    tree.SetArtifacts(stable, next, previous);
                    StableSetupHostRecoveryState expected = ExpectedUpdateState(stable, next, previous);
                    StableSetupHostInspection actual = tree.Manager.Inspect(tree.Before, tree.Target);
                    Assert.That(actual.State, Is.EqualTo(expected),
                        $"stable={stable}, next={next}, previous={previous}");
                }
    }

    [Test]
    public void FaultAfterNextDurable_LeavesAClassifiedFirstInstallStage()
    {
        using HostTestTree tree = HostTestTree.Create(
            new OneShotFaultInjector(StableSetupHostFaultPoint.NextDurable));

        Assert.Throws<SimulatedStableHostCrashException>(() =>
            tree.Manager.StageCandidate(tree.TargetSource, tree.Target));

        Assert.That(
            tree.InspectWithoutFault(null, tree.Target).State,
            Is.EqualTo(StableSetupHostRecoveryState.FirstInstallStaged));
    }

    [Test]
    public void FaultAfterFirstMove_LeavesThePublishedTargetRecoverable()
    {
        using HostTestTree tree = HostTestTree.Create(
            new OneShotFaultInjector(StableSetupHostFaultPoint.FirstInstallMoved));
        tree.Manager.StageCandidate(tree.TargetSource, tree.Target);

        Assert.Throws<SimulatedStableHostCrashException>(() =>
            tree.Manager.PublishFirstInstall(tree.Target));

        Assert.That(
            tree.InspectWithoutFault(null, tree.Target).State,
            Is.EqualTo(StableSetupHostRecoveryState.TargetPublished));
    }

    [Test]
    public void FaultAfterPreviousBackup_IsResumedWithoutRewritingTheBackup()
    {
        using HostTestTree tree = HostTestTree.Create(
            new OneShotFaultInjector(StableSetupHostFaultPoint.PreviousBackupDurable));
        tree.WriteStable(tree.BeforeBytes);
        tree.Manager.StageCandidate(tree.TargetSource, tree.Target, tree.Before);

        Assert.Throws<SimulatedStableHostCrashException>(() =>
            tree.Manager.PublishUpdate(tree.Before, tree.Target));
        Assert.That(tree.InspectWithoutFault(tree.Before, tree.Target).State,
            Is.EqualTo(StableSetupHostRecoveryState.UpdateBackupReady));

        tree.ManagerWithoutFault.PublishUpdate(tree.Before, tree.Target);
        Assert.That(tree.InspectWithoutFault(tree.Before, tree.Target).State,
            Is.EqualTo(StableSetupHostRecoveryState.UpdateReplaced));
    }

    [Test]
    public void FaultAfterUpdateMove_LeavesTargetAndPreviousExactlyClassified()
    {
        using HostTestTree tree = HostTestTree.Create(
            new OneShotFaultInjector(StableSetupHostFaultPoint.UpdateReplaced));
        tree.WriteStable(tree.BeforeBytes);
        tree.Manager.StageCandidate(tree.TargetSource, tree.Target, tree.Before);

        Assert.Throws<SimulatedStableHostCrashException>(() =>
            tree.Manager.PublishUpdate(tree.Before, tree.Target));

        Assert.That(tree.InspectWithoutFault(tree.Before, tree.Target).State,
            Is.EqualTo(StableSetupHostRecoveryState.UpdateReplaced));
    }

    [Test]
    public void FinalizePublishedTarget_DeletesOnlyAnExactPreviousAndIsIdempotent()
    {
        using HostTestTree tree = HostTestTree.Create();
        tree.PrepareReplacedUpdate();

        Assert.That(tree.Manager.FinalizePublishedTarget(tree.Before, tree.Target), Is.True);
        Assert.That(tree.Manager.FinalizePublishedTarget(tree.Before, tree.Target), Is.False);

        Assert.Multiple(() =>
        {
            Assert.That(tree.Manager.Inspect(tree.Before, tree.Target).State,
                Is.EqualTo(StableSetupHostRecoveryState.TargetPublished));
            Assert.That(File.Exists(tree.Paths.Previous), Is.False);
            Assert.That(File.ReadAllBytes(tree.Paths.Stable), Is.EqualTo(tree.TargetBytes));
        });
    }

    [Test]
    public void FinalizePublishedTarget_RefusesTamperedPreviousWithoutDeletion()
    {
        using HostTestTree tree = HostTestTree.Create();
        tree.PrepareReplacedUpdate();
        HostTestTree.Write(tree.Paths.Previous, tree.ForeignBytes, overwrite: true);
        byte[] foreign = File.ReadAllBytes(tree.Paths.Previous);

        Assert.Throws<InstallationSafetyException>(() =>
            tree.Manager.FinalizePublishedTarget(tree.Before, tree.Target));

        Assert.That(File.ReadAllBytes(tree.Paths.Previous), Is.EqualTo(foreign));
        Assert.That(File.ReadAllBytes(tree.Paths.Stable), Is.EqualTo(tree.TargetBytes));
    }

    [Test]
    public void FaultAfterPreviousDelete_LeavesACompletedTargetState()
    {
        using HostTestTree tree = HostTestTree.Create(
            new OneShotFaultInjector(StableSetupHostFaultPoint.PreviousDeleted));
        tree.PrepareReplacedUpdate();

        Assert.Throws<SimulatedStableHostCrashException>(() =>
            tree.Manager.FinalizePublishedTarget(tree.Before, tree.Target));

        Assert.That(tree.InspectWithoutFault(tree.Before, tree.Target).State,
            Is.EqualTo(StableSetupHostRecoveryState.TargetPublished));
    }

    [Test]
    public void DeleteStagedTarget_OnlyDeletesAnExactClassifiedNextFile()
    {
        using HostTestTree tree = HostTestTree.Create();
        tree.Manager.StageCandidate(tree.TargetSource, tree.Target);

        Assert.That(tree.Manager.DeleteStagedTarget(null, tree.Target), Is.True);
        Assert.That(tree.Manager.DeleteStagedTarget(null, tree.Target), Is.False);
        Assert.That(tree.Manager.Inspect(null, tree.Target).State,
            Is.EqualTo(StableSetupHostRecoveryState.Empty));

        tree.Manager.StageCandidate(tree.TargetSource, tree.Target);
        HostTestTree.Write(tree.Paths.Next, tree.ForeignBytes, overwrite: true);
        byte[] foreign = File.ReadAllBytes(tree.Paths.Next);
        Assert.Throws<InstallationSafetyException>(() =>
            tree.Manager.DeleteStagedTarget(null, tree.Target));
        Assert.That(File.ReadAllBytes(tree.Paths.Next), Is.EqualTo(foreign));
    }

    [Test]
    public void RestorePrevious_CreatesAnExactTargetBackupAndReturnsToUpdateStaged()
    {
        using HostTestTree tree = HostTestTree.Create();
        tree.PrepareReplacedUpdate();

        tree.Manager.RestorePrevious(tree.Before, tree.Target);

        Assert.Multiple(() =>
        {
            Assert.That(tree.Manager.Inspect(tree.Before, tree.Target).State,
                Is.EqualTo(StableSetupHostRecoveryState.UpdateStaged));
            Assert.That(File.ReadAllBytes(tree.Paths.Stable), Is.EqualTo(tree.BeforeBytes));
            Assert.That(File.ReadAllBytes(tree.Paths.Next), Is.EqualTo(tree.TargetBytes));
            Assert.That(File.Exists(tree.Paths.Previous), Is.False);
        });

        Assert.That(tree.Manager.DeleteStagedTarget(tree.Before, tree.Target), Is.True);
        Assert.That(tree.Manager.Inspect(tree.Before, tree.Target).State,
            Is.EqualTo(StableSetupHostRecoveryState.BeforeStable));
    }

    [Test]
    public void FaultDuringRestoreBackup_IsClassifiedAndResumed()
    {
        using HostTestTree tree = HostTestTree.Create(
            new OneShotFaultInjector(StableSetupHostFaultPoint.RestoreTargetBackupDurable));
        tree.PrepareReplacedUpdate();

        Assert.Throws<SimulatedStableHostCrashException>(() =>
            tree.Manager.RestorePrevious(tree.Before, tree.Target));
        Assert.That(tree.InspectWithoutFault(tree.Before, tree.Target).State,
            Is.EqualTo(StableSetupHostRecoveryState.RestoreBackupReady));

        tree.ManagerWithoutFault.RestorePrevious(tree.Before, tree.Target);
        Assert.That(tree.InspectWithoutFault(tree.Before, tree.Target).State,
            Is.EqualTo(StableSetupHostRecoveryState.UpdateStaged));
    }

    [Test]
    public void FaultAfterStagedTargetDelete_LeavesAnEmptyStateAndIsIdempotent()
    {
        using HostTestTree tree = HostTestTree.Create(
            new OneShotFaultInjector(StableSetupHostFaultPoint.StagedTargetDeleted));
        tree.Manager.StageCandidate(tree.TargetSource, tree.Target);

        // Crash after the staged candidate is gone but before the caller can
        // learn that it was deleted: the recovered state must be the empty one,
        // and a repeated delete must report that there was nothing left to do.
        Assert.Throws<SimulatedStableHostCrashException>(() =>
            tree.Manager.DeleteStagedTarget(null, tree.Target));

        Assert.Multiple(() =>
        {
            Assert.That(tree.InspectWithoutFault(null, tree.Target).State,
                Is.EqualTo(StableSetupHostRecoveryState.Empty));
            Assert.That(File.Exists(tree.Paths.Next), Is.False);
            Assert.That(
                tree.ManagerWithoutFault.DeleteStagedTarget(null, tree.Target),
                Is.False);
        });
    }

    [Test]
    public void FaultAfterStagedTargetDelete_KeepsTheExistingStableHostIntact()
    {
        using HostTestTree tree = HostTestTree.Create(
            new OneShotFaultInjector(StableSetupHostFaultPoint.StagedTargetDeleted));
        tree.WriteStable(tree.BeforeBytes);
        tree.Manager.StageCandidate(tree.TargetSource, tree.Target, tree.Before);

        Assert.Throws<SimulatedStableHostCrashException>(() =>
            tree.Manager.DeleteStagedTarget(tree.Before, tree.Target));

        Assert.Multiple(() =>
        {
            Assert.That(tree.InspectWithoutFault(tree.Before, tree.Target).State,
                Is.EqualTo(StableSetupHostRecoveryState.BeforeStable));
            // Abandoning an update must not touch the host the user already has.
            Assert.That(File.ReadAllBytes(tree.Paths.Stable), Is.EqualTo(tree.BeforeBytes));
            Assert.That(File.Exists(tree.Paths.Next), Is.False);
            Assert.That(File.Exists(tree.Paths.Previous), Is.False);
            Assert.That(
                tree.ManagerWithoutFault.DeleteStagedTarget(tree.Before, tree.Target),
                Is.False);
        });
    }

    [Test]
    public void FaultAfterPreviousRestore_LeavesTheRestoredStateClassified()
    {
        using HostTestTree tree = HostTestTree.Create(
            new OneShotFaultInjector(StableSetupHostFaultPoint.PreviousRestored));
        tree.PrepareReplacedUpdate();

        Assert.Throws<SimulatedStableHostCrashException>(() =>
            tree.Manager.RestorePrevious(tree.Before, tree.Target));

        Assert.That(tree.InspectWithoutFault(tree.Before, tree.Target).State,
            Is.EqualTo(StableSetupHostRecoveryState.UpdateStaged));
    }

    private static StableSetupHostRecoveryState ExpectedFirstInstallState(
        ArtifactFixture stable,
        ArtifactFixture next,
        ArtifactFixture previous)
    {
        if (stable == ArtifactFixture.Foreign ||
            next == ArtifactFixture.Foreign ||
            previous == ArtifactFixture.Foreign)
        {
            return StableSetupHostRecoveryState.Foreign;
        }

        if (stable == ArtifactFixture.Missing &&
            next == ArtifactFixture.Missing &&
            previous == ArtifactFixture.Missing)
        {
            return StableSetupHostRecoveryState.Empty;
        }

        if (stable == ArtifactFixture.Missing &&
            next == ArtifactFixture.Target &&
            previous == ArtifactFixture.Missing)
        {
            return StableSetupHostRecoveryState.FirstInstallStaged;
        }

        if (stable == ArtifactFixture.Target &&
            next == ArtifactFixture.Missing &&
            previous == ArtifactFixture.Missing)
        {
            return StableSetupHostRecoveryState.TargetPublished;
        }

        return StableSetupHostRecoveryState.Contradictory;
    }

    private static StableSetupHostRecoveryState ExpectedUpdateState(
        ArtifactFixture stable,
        ArtifactFixture next,
        ArtifactFixture previous)
    {
        if (stable == ArtifactFixture.Foreign ||
            next == ArtifactFixture.Foreign ||
            previous == ArtifactFixture.Foreign)
        {
            return StableSetupHostRecoveryState.Foreign;
        }

        if (stable == ArtifactFixture.Before &&
            next == ArtifactFixture.Missing &&
            previous == ArtifactFixture.Missing)
        {
            return StableSetupHostRecoveryState.BeforeStable;
        }

        if (stable == ArtifactFixture.Before &&
            next == ArtifactFixture.Target &&
            previous == ArtifactFixture.Missing)
        {
            return StableSetupHostRecoveryState.UpdateStaged;
        }

        if (stable == ArtifactFixture.Before &&
            next == ArtifactFixture.Target &&
            previous == ArtifactFixture.Before)
        {
            return StableSetupHostRecoveryState.UpdateBackupReady;
        }

        if (stable == ArtifactFixture.Target &&
            next == ArtifactFixture.Missing &&
            previous == ArtifactFixture.Missing)
        {
            return StableSetupHostRecoveryState.TargetPublished;
        }

        if (stable == ArtifactFixture.Target &&
            next == ArtifactFixture.Missing &&
            previous == ArtifactFixture.Before)
        {
            return StableSetupHostRecoveryState.UpdateReplaced;
        }

        if (stable == ArtifactFixture.Target &&
            next == ArtifactFixture.Target &&
            previous == ArtifactFixture.Before)
        {
            return StableSetupHostRecoveryState.RestoreBackupReady;
        }

        return StableSetupHostRecoveryState.Contradictory;
    }

    private enum ArtifactFixture
    {
        Missing,
        Before,
        Target,
        Foreign,
    }

    private sealed class OneShotFaultInjector : IStableSetupHostFaultInjector
    {
        private readonly StableSetupHostFaultPoint _target;
        private bool _thrown;

        internal OneShotFaultInjector(StableSetupHostFaultPoint target)
        {
            _target = target;
        }

        public void Checkpoint(StableSetupHostFaultPoint point)
        {
            if (!_thrown && point == _target)
            {
                _thrown = true;
                throw new SimulatedStableHostCrashException(point);
            }
        }
    }

    private sealed class SimulatedStableHostCrashException : Exception
    {
        internal SimulatedStableHostCrashException(StableSetupHostFaultPoint point)
            : base($"Simulated stable Setup host crash at {point}.")
        {
        }
    }

    private sealed class HostTestTree : IDisposable
    {
        private HostTestTree(IStableSetupHostFaultInjector? faultInjector)
        {
            Root = Path.Combine(
                Path.GetTempPath(),
                "baxy-stable-host-tests",
                Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(Root);
            Paths = new StableSetupHostPaths(
                Path.Combine(Root, "Baxy.Setup.exe"),
                Path.Combine(Root, "Baxy.Setup.next.exe"),
                Path.Combine(Root, "Baxy.Setup.previous.exe"));
            BeforeBytes = [0x4d, 0x5a, 0x01, 0x00, 0x42, 0x41, 0x58, 0x59];
            TargetBytes = [0x4d, 0x5a, 0x02, 0x00, 0x42, 0x41, 0x58, 0x59, 0x32];
            ForeignBytes = [0x46, 0x4f, 0x52, 0x45, 0x49, 0x47, 0x4e];
            Before = Identity(BeforeBytes);
            Target = Identity(TargetBytes);
            TargetSource = Path.Combine(Root, "candidate.exe");
            File.WriteAllBytes(TargetSource, TargetBytes);
            Manager = new StableSetupHostManager(Paths, faultInjector);
            ManagerWithoutFault = new StableSetupHostManager(Paths);
        }

        internal string Root { get; }

        internal StableSetupHostPaths Paths { get; }

        internal byte[] BeforeBytes { get; }

        internal byte[] TargetBytes { get; }

        internal byte[] ForeignBytes { get; }

        internal StableSetupHostIdentity Before { get; }

        internal StableSetupHostIdentity Target { get; }

        internal string TargetSource { get; }

        internal StableSetupHostManager Manager { get; }

        internal StableSetupHostManager ManagerWithoutFault { get; }

        internal static HostTestTree Create(IStableSetupHostFaultInjector? faultInjector = null) =>
            new(faultInjector);

        internal static StableSetupHostIdentity Identity(byte[] bytes) =>
            new(Convert.ToHexStringLower(SHA256.HashData(bytes)), bytes.LongLength);

        internal void WriteStable(byte[] bytes) => Write(Paths.Stable, bytes);

        internal static void Write(string path, byte[] bytes, bool overwrite = false)
        {
            if (overwrite)
            {
                File.WriteAllBytes(path, bytes);
            }
            else
            {
                using FileStream stream = new(path, FileMode.CreateNew, FileAccess.Write, FileShare.None);
                stream.Write(bytes);
                stream.Flush(flushToDisk: true);
            }
        }

        internal void SetArtifacts(
            ArtifactFixture stable,
            ArtifactFixture next,
            ArtifactFixture previous)
        {
            DeleteIfPresent(Paths.Stable);
            DeleteIfPresent(Paths.Next);
            DeleteIfPresent(Paths.Previous);
            WriteFixture(Paths.Stable, stable);
            WriteFixture(Paths.Next, next);
            WriteFixture(Paths.Previous, previous);
        }

        internal StableSetupHostInspection InspectWithoutFault(
            StableSetupHostIdentity? before,
            StableSetupHostIdentity target) =>
            ManagerWithoutFault.Inspect(before, target);

        internal void PrepareReplacedUpdate()
        {
            WriteStable(BeforeBytes);
            Manager.StageCandidate(TargetSource, Target, Before);
            Manager.PublishUpdate(Before, Target);
        }

        public void Dispose()
        {
            if (Directory.Exists(Root))
            {
                foreach (string entry in Directory.EnumerateFiles(Root, "*", SearchOption.AllDirectories))
                {
                    File.SetAttributes(entry, FileAttributes.Normal);
                }

                Directory.Delete(Root, recursive: true);
            }
        }

        private void WriteFixture(string path, ArtifactFixture fixture)
        {
            byte[]? bytes = fixture switch
            {
                ArtifactFixture.Missing => null,
                ArtifactFixture.Before => BeforeBytes,
                ArtifactFixture.Target => TargetBytes,
                ArtifactFixture.Foreign => ForeignBytes,
                _ => throw new InvalidOperationException("Unsupported artifact fixture."),
            };
            if (bytes is not null)
            {
                Write(path, bytes);
            }
        }

        private static void DeleteIfPresent(string path)
        {
            if (File.Exists(path))
            {
                File.SetAttributes(path, FileAttributes.Normal);
                File.Delete(path);
            }
            else if (Directory.Exists(path))
            {
                Directory.Delete(path, recursive: true);
            }
        }
    }

    [DllImport("kernel32.dll", EntryPoint = "CreateHardLinkW", CharSet = CharSet.Unicode, SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool CreateHardLink(
        string fileName,
        string existingFileName,
        nint securityAttributes);
}
