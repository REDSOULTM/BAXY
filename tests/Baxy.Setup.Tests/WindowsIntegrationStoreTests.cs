using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using NUnit.Framework;

namespace Baxy.Setup.Tests;

[TestFixture]
public sealed class WindowsIntegrationStoreTests
{
    [Test]
    public void InstallationIdentity_IsCanonicalImmutableAndIdempotent()
    {
        using IntegrationTestTree tree = IntegrationTestTree.Create();

        WindowsInstallationIdentity created = tree.Store.EnsureInstallationIdentity(tree.Identity);
        WindowsInstallationIdentity repeated = tree.Store.EnsureInstallationIdentity(tree.Identity);

        Assert.Multiple(() =>
        {
            Assert.That(created, Is.EqualTo(tree.Identity));
            Assert.That(repeated, Is.EqualTo(tree.Identity));
            Assert.That(tree.Store.ReadInstallationIdentity(), Is.EqualTo(tree.Identity));
            Assert.That(File.Exists(tree.PathOf(WindowsIntegrationStore.InstallationIdentityNextFileName)), Is.False);
        });

        byte[] bytes = File.ReadAllBytes(tree.PathOf(WindowsIntegrationStore.InstallationIdentityFileName));
        Assert.Multiple(() =>
        {
            Assert.That(bytes[^1], Is.EqualTo((byte)'\n'));
            Assert.That(bytes.Take(3).ToArray(), Is.Not.EqualTo(new byte[] { 0xef, 0xbb, 0xbf }));
            Assert.That(
                Encoding.UTF8.GetString(bytes),
                Is.EqualTo(
                    $"{{\"schema\":\"baxy-installation-v1\",\"install_id\":\"{tree.InstallId}\",\"data_schema\":1,\"installation_root\":{JsonSerializer.Serialize(tree.Root)}}}\n"));
        });

        Assert.That(
            () => tree.Store.EnsureInstallationIdentity(tree.Identity with
            {
                InstallId = Guid.NewGuid().ToString("N"),
            }),
            Throws.TypeOf<InstallationSafetyException>());
    }

    [TestCase(nameof(WindowsIntegrationStoreFaultPoint.InstallationNextDurable))]
    [TestCase(nameof(WindowsIntegrationStoreFaultPoint.InstallationSwitched))]
    public void InstallationIdentity_RecoversAcrossDurableBoundaries(
        string faultPointName)
    {
        using IntegrationTestTree tree = IntegrationTestTree.Create();
        WindowsIntegrationStoreFaultPoint faultPoint = Enum.Parse<WindowsIntegrationStoreFaultPoint>(faultPointName);
        WindowsIntegrationStore crashing = new(tree.Root, new OneShotCrashInjector(faultPoint));

        Assert.That(
            () => crashing.EnsureInstallationIdentity(tree.Identity),
            Throws.TypeOf<StoreSimulatedCrashException>());

        WindowsIntegrationStore recovered = new(tree.Root);
        Assert.That(recovered.RecoverAndReadInstallationIdentity(), Is.EqualTo(tree.Identity));
        Assert.That(recovered.ReadInstallationIdentity(), Is.EqualTo(tree.Identity));
        AssertNoStoreStaging(tree);
    }

    [Test]
    public void InstallationIdentity_RejectsInstallIdSchemaAndRootMutation()
    {
        using IntegrationTestTree tree = IntegrationTestTree.Create();
        WindowsInstallationIdentity[] invalid =
        [
            tree.Identity with { Schema = "baxy-installation-v2" },
            tree.Identity with { InstallId = tree.InstallId.ToUpperInvariant() },
            tree.Identity with { DataSchema = 2 },
            tree.Identity with { InstallationRoot = tree.Root + Path.DirectorySeparatorChar },
            tree.Identity with { InstallationRoot = Path.Combine(tree.Outer, "foreign") },
        ];

        foreach (WindowsInstallationIdentity identity in invalid)
        {
            Assert.That(
                () => tree.Store.EnsureInstallationIdentity(identity),
                Throws.TypeOf<InstallationSafetyException>(),
                identity.ToString());
        }

        Assert.That(tree.Store.ReadInstallationIdentity(), Is.Null);
    }

    [Test]
    public void InstallationIdentityInitializationGuard_IsReadOnlyForAnEmptyStore()
    {
        using IntegrationTestTree tree = IntegrationTestTree.Create();
        string[] before = Directory.GetFileSystemEntries(tree.Root);

        tree.Store.AssertInstallationIdentityMayBeInitialized();

        Assert.That(Directory.GetFileSystemEntries(tree.Root), Is.EqualTo(before));
    }

    [TestCase(WindowsIntegrationStore.InstallationIdentityFileName)]
    [TestCase(WindowsIntegrationStore.InstallationIdentityNextFileName)]
    [TestCase(WindowsIntegrationStore.IntegrationFileName)]
    [TestCase(WindowsIntegrationStore.IntegrationNextFileName)]
    [TestCase(WindowsIntegrationStore.IntegrationPreviousFileName)]
    [TestCase(WindowsIntegrationStore.TransactionFileName)]
    [TestCase(WindowsIntegrationStore.TransactionNextFileName)]
    [TestCase(WindowsIntegrationStore.TransactionPreviousFileName)]
    public void InstallationIdentityInitializationGuard_RejectsAndPreservesEveryExteriorArtifact(
        string fileName)
    {
        using IntegrationTestTree tree = IntegrationTestTree.Create();
        string path = tree.PathOf(fileName);
        byte[] foreign = [0x66, 0x6f, 0x72, 0x65, 0x69, 0x67, 0x6e];
        File.WriteAllBytes(path, foreign);

        Assert.That(
            tree.Store.AssertInstallationIdentityMayBeInitialized,
            Throws.TypeOf<InstallationSafetyException>());

        Assert.That(File.ReadAllBytes(path), Is.EqualTo(foreign));
    }

    [Test]
    public void FirstCreateUpdateAndRollback_PersistOnlyExactCommittedSnapshots()
    {
        using IntegrationTestTree tree = IntegrationTestTree.Create();
        _ = tree.Store.EnsureInstallationIdentity(tree.Identity);
        WindowsIntegrationState first = tree.State("1.0.0", "first", stableVersion: "1.0.0");
        Commit(tree, tree.Transaction(null, first, WindowsIntegrationOperation.InstallUpdate));

        WindowsIntegrationState update = tree.State("1.1.0", "update", stableVersion: "1.1.0");
        Commit(tree, tree.Transaction(first, update, WindowsIntegrationOperation.InstallUpdate));

        WindowsIntegrationState rollback = tree.State(
            "1.0.0",
            "first",
            stableVersion: update.StableSetup.Version,
            stableSetup: update.StableSetup,
            shortcut: update.Shortcut,
            estimatedSize: 170000);
        Commit(tree, tree.Transaction(update, rollback, WindowsIntegrationOperation.Rollback));

        Assert.That(tree.Store.ReadCommittedState(), Is.EqualTo(rollback));
        Assert.That(tree.Store.RecoverAndReadTransaction(), Is.Null);
        AssertNoStoreStaging(tree);

        byte[] bytes = File.ReadAllBytes(tree.PathOf(WindowsIntegrationStore.IntegrationFileName));
        Assert.Multiple(() =>
        {
            Assert.That(bytes[^1], Is.EqualTo((byte)'\n'));
            Assert.That(bytes, Does.Not.Contain((byte)'\r'));
            Assert.That(Encoding.UTF8.GetString(bytes), Does.StartWith(
                "{\"schema\":\"baxy-windows-integration-v1\",\"install_id\":"));
            Assert.That(Encoding.UTF8.GetString(bytes), Does.Contain(
                "\"active\":{\"schema\":\"baxy-current-v2\",\"version\":\"1.0.0\",\"data_schema\":1,\"package_sha256\":"));
        });
    }

    [TestCase(nameof(WindowsIntegrationStoreFaultPoint.TransactionNextDurable))]
    [TestCase(nameof(WindowsIntegrationStoreFaultPoint.TransactionPreviousDurable))]
    [TestCase(nameof(WindowsIntegrationStoreFaultPoint.TransactionSwitched))]
    public void JournalAdvance_RecoversAcrossNextAndReplaceBoundaries(
        string faultPointName)
    {
        using IntegrationTestTree tree = IntegrationTestTree.Create();
        WindowsIntegrationStoreFaultPoint faultPoint = Enum.Parse<WindowsIntegrationStoreFaultPoint>(faultPointName);
        _ = tree.Store.EnsureInstallationIdentity(tree.Identity);
        WindowsIntegrationTransaction prepared = tree.Transaction(
            null,
            tree.State("1.0.0", "first", "1.0.0"),
            WindowsIntegrationOperation.InstallUpdate);
        tree.Store.BeginTransaction(prepared);
        WindowsIntegrationTransaction staged = prepared with { Phase = WindowsIntegrationPhase.HostStaged };
        WindowsIntegrationStore crashing = new(tree.Root, new OneShotCrashInjector(faultPoint));

        Assert.That(
            () => crashing.AdvanceTransaction(prepared, staged),
            Throws.TypeOf<StoreSimulatedCrashException>());

        WindowsIntegrationStore recovered = new(tree.Root);
        Assert.That(recovered.RecoverAndReadTransaction(), Is.EqualTo(staged));
        Assert.Multiple(() =>
        {
            Assert.That(File.Exists(tree.PathOf(WindowsIntegrationStore.TransactionNextFileName)), Is.False);
            Assert.That(File.Exists(tree.PathOf(WindowsIntegrationStore.TransactionPreviousFileName)), Is.False);
        });
    }

    [TestCase(nameof(WindowsIntegrationStoreFaultPoint.TransactionNextDurable))]
    [TestCase(nameof(WindowsIntegrationStoreFaultPoint.TransactionSwitched))]
    public void JournalBegin_RecoversItsAuthoritativePreparedIntentAcrossProcessRestart(
        string faultPointName)
    {
        using IntegrationTestTree tree = IntegrationTestTree.Create();
        _ = tree.Store.EnsureInstallationIdentity(tree.Identity);
        WindowsIntegrationTransaction prepared = tree.Transaction(
            null,
            tree.State("1.0.0", "first", "1.0.0"),
            WindowsIntegrationOperation.InstallUpdate);
        WindowsIntegrationStoreFaultPoint point =
            Enum.Parse<WindowsIntegrationStoreFaultPoint>(faultPointName);
        WindowsIntegrationStore crashing = new(tree.Root, new OneShotCrashInjector(point));

        Assert.That(
            () => crashing.BeginTransaction(prepared),
            Throws.TypeOf<StoreSimulatedCrashException>());

        WindowsIntegrationStore recovered = new(tree.Root);
        Assert.That(recovered.RecoverAndReadTransaction(), Is.EqualTo(prepared));
        Assert.That(File.Exists(tree.PathOf(WindowsIntegrationStore.TransactionNextFileName)), Is.False);
        Assert.That(File.Exists(tree.PathOf(WindowsIntegrationStore.TransactionPreviousFileName)), Is.False);
    }

    [TestCase(nameof(WindowsIntegrationStoreFaultPoint.IntegrationNextDurable))]
    [TestCase(nameof(WindowsIntegrationStoreFaultPoint.IntegrationSwitched))]
    public void FirstIntegrationCommit_RecoversAcrossNextAndSwitchBoundaries(
        string faultPointName)
    {
        using IntegrationTestTree tree = IntegrationTestTree.Create();
        WindowsIntegrationStoreFaultPoint faultPoint = Enum.Parse<WindowsIntegrationStoreFaultPoint>(faultPointName);
        _ = tree.Store.EnsureInstallationIdentity(tree.Identity);
        WindowsIntegrationState target = tree.State("1.0.0", "first", "1.0.0");
        WindowsIntegrationTransaction registry = AdvanceTo(
            tree,
            tree.Transaction(null, target, WindowsIntegrationOperation.InstallUpdate),
            WindowsIntegrationPhase.RegistryIntent);
        WindowsIntegrationStore crashing = new(tree.Root, new OneShotCrashInjector(faultPoint));

        Assert.That(
            () => crashing.ApplyTransactionTarget(registry),
            Throws.TypeOf<StoreSimulatedCrashException>());

        WindowsIntegrationStore recovered = new(tree.Root);
        Assert.That(recovered.ApplyTransactionTarget(registry), Is.EqualTo(target));
        Assert.That(recovered.ReadCommittedState(), Is.EqualTo(target));
        Assert.That(File.Exists(tree.PathOf(WindowsIntegrationStore.IntegrationPreviousFileName)), Is.False);
    }

    [TestCase(nameof(WindowsIntegrationStoreFaultPoint.IntegrationNextDurable))]
    [TestCase(nameof(WindowsIntegrationStoreFaultPoint.IntegrationPreviousDurable))]
    [TestCase(nameof(WindowsIntegrationStoreFaultPoint.IntegrationSwitched))]
    public void IntegrationUpdate_RecoversAcrossNextAndReplaceBoundaries(
        string faultPointName)
    {
        using IntegrationTestTree tree = IntegrationTestTree.Create();
        WindowsIntegrationStoreFaultPoint faultPoint = Enum.Parse<WindowsIntegrationStoreFaultPoint>(faultPointName);
        _ = tree.Store.EnsureInstallationIdentity(tree.Identity);
        WindowsIntegrationState before = tree.State("1.0.0", "first", "1.0.0");
        Commit(tree, tree.Transaction(null, before, WindowsIntegrationOperation.InstallUpdate));
        WindowsIntegrationState target = tree.State("1.1.0", "update", "1.1.0");
        WindowsIntegrationTransaction registry = AdvanceTo(
            tree,
            tree.Transaction(before, target, WindowsIntegrationOperation.InstallUpdate),
            WindowsIntegrationPhase.RegistryIntent);
        WindowsIntegrationStore crashing = new(tree.Root, new OneShotCrashInjector(faultPoint));

        Assert.That(
            () => crashing.ApplyTransactionTarget(registry),
            Throws.TypeOf<StoreSimulatedCrashException>());

        WindowsIntegrationStore recovered = new(tree.Root);
        Assert.That(recovered.ApplyTransactionTarget(registry), Is.EqualTo(target));
        Assert.That(recovered.ReadCommittedState(), Is.EqualTo(target));
        Assert.That(File.Exists(tree.PathOf(WindowsIntegrationStore.IntegrationPreviousFileName)), Is.False);
    }

    [Test]
    public void ReconcileAdoption_IsJournalGatedAndRecoverable()
    {
        using IntegrationTestTree tree = IntegrationTestTree.Create();
        _ = tree.Store.EnsureInstallationIdentity(tree.Identity);
        WindowsIntegrationState target = tree.State("1.0.0", "first", "1.0.0");
        WindowsIntegrationTransaction adoption = AdvanceTo(
            tree,
            tree.Transaction(null, target, WindowsIntegrationOperation.Reconcile),
            WindowsIntegrationPhase.RegistryIntent);

        Assert.That(tree.Store.ApplyTransactionTarget(adoption), Is.EqualTo(target));
        Assert.That(tree.Store.ReadCommittedState(), Is.EqualTo(target));

        WindowsIntegrationTransaction integration = adoption with
        {
            Phase = WindowsIntegrationPhase.IntegrationCommitted,
        };
        tree.Store.AdvanceTransaction(adoption, integration);
        WindowsIntegrationTransaction complete = integration with { Phase = WindowsIntegrationPhase.Complete };
        tree.Store.AdvanceTransaction(integration, complete);
        tree.Store.CompleteTransaction(complete);
        AssertNoStoreStaging(tree);
    }

    [Test]
    public void RecoveryDecision_IsExactlyBeforeAbortTargetRollForwardOtherwiseFailClosed()
    {
        using IntegrationTestTree tree = IntegrationTestTree.Create();
        WindowsIntegrationState before = tree.State("1.0.0", "first", "1.0.0");
        WindowsIntegrationState target = tree.State("1.1.0", "update", "1.1.0");
        WindowsIntegrationTransaction update = tree.Transaction(
            before,
            target,
            WindowsIntegrationOperation.InstallUpdate);
        WindowsIntegrationTransaction first = tree.Transaction(
            null,
            before,
            WindowsIntegrationOperation.InstallUpdate);

        Assert.Multiple(() =>
        {
            Assert.That(
                WindowsIntegrationStore.DecideRecovery(before.Active, update),
                Is.EqualTo(WindowsIntegrationRecoveryDecision.Abort));
            Assert.That(
                WindowsIntegrationStore.DecideRecovery(target.Active, update),
                Is.EqualTo(WindowsIntegrationRecoveryDecision.RollForward));
            Assert.That(
                WindowsIntegrationStore.DecideRecovery(null, first),
                Is.EqualTo(WindowsIntegrationRecoveryDecision.Abort));
            Assert.That(
                WindowsIntegrationStore.DecideRecovery(before.Active, first),
                Is.EqualTo(WindowsIntegrationRecoveryDecision.RollForward));
        });

        WindowsIntegrationActiveIdentity foreign = target.Active with
        {
            PackageSha256 = Hash("foreign"),
        };
        Assert.That(
            () => WindowsIntegrationStore.DecideRecovery(foreign, update),
            Throws.TypeOf<InstallationSafetyException>());
    }

    [Test]
    public void Transactions_RejectInvalidOperationsSnapshotsIdentityAndPhase()
    {
        using IntegrationTestTree tree = IntegrationTestTree.Create();
        _ = tree.Store.EnsureInstallationIdentity(tree.Identity);
        WindowsIntegrationState before = tree.State("1.0.0", "first", "1.0.0");
        WindowsIntegrationState target = tree.State("1.1.0", "update", "1.1.0");
        WindowsIntegrationTransaction valid = tree.Transaction(
            before,
            target,
            WindowsIntegrationOperation.InstallUpdate);
        WindowsIntegrationTransaction[] invalid =
        [
            valid with { Schema = "foreign" },
            valid with { TransactionId = valid.TransactionId.ToUpperInvariant() },
            valid with { Operation = "uninstall" },
            valid with { Phase = "unknown" },
            valid with { InstallId = "0123456789ABCDEF0123456789ABCDEF" },
            valid with { DataSchema = 2 },
            valid with { InstallationRoot = Path.Combine(tree.Outer, "foreign") },
            valid with { TargetActive = before.Active },
            valid with { TargetStableSetup = valid.TargetStableSetup with { HostBytes = 0 } },
            valid with { Target = target },
            valid with { Phase = WindowsIntegrationPhase.ShortcutCommitted, Target = null },
            valid with
            {
                Phase = WindowsIntegrationPhase.ShortcutCommitted,
                Target = target with { InstallId = Guid.NewGuid().ToString("N") },
            },
            valid with
            {
                Phase = WindowsIntegrationPhase.ShortcutCommitted,
                Target = target with { DataSchema = 2 },
            },
            valid with
            {
                Phase = WindowsIntegrationPhase.ShortcutCommitted,
                Target = target with { InstallationRoot = Path.Combine(tree.Outer, "foreign") },
            },
            valid with { Operation = WindowsIntegrationOperation.Rollback },
            valid with { Operation = WindowsIntegrationOperation.Reconcile },
        ];

        foreach (WindowsIntegrationTransaction transaction in invalid)
        {
            Assert.That(
                () => WindowsIntegrationStore.DecideRecovery(before.Active, transaction),
                Throws.TypeOf<InstallationSafetyException>(),
                transaction.ToString());
        }

        WindowsIntegrationTransaction changedHostRollback = tree.Transaction(
            target,
            before,
            WindowsIntegrationOperation.Rollback);
        Assert.That(
            () => WindowsIntegrationStore.DecideRecovery(target.Active, changedHostRollback),
            Throws.TypeOf<InstallationSafetyException>());
    }

    [Test]
    public void StateValidation_RejectsEveryInvalidIdentitySizeHashAndVersionClass()
    {
        using IntegrationTestTree tree = IntegrationTestTree.Create();
        WindowsIntegrationState valid = tree.State("1.0.0", "first", "1.0.0");
        WindowsIntegrationState[] invalid =
        [
            valid with { Schema = "baxy-windows-integration-v2" },
            valid with { InstallId = "0123456789ABCDEF0123456789ABCDEF" },
            valid with { DataSchema = 2 },
            valid with { Active = valid.Active with { Schema = "baxy-current-v3" } },
            valid with { Active = valid.Active with { Version = "01.0.0" } },
            valid with { Active = valid.Active with { DataSchema = 2 } },
            valid with { Active = valid.Active with { PackageSha256 = valid.Active.PackageSha256.ToUpperInvariant() } },
            valid with { Active = valid.Active with { ManifestSha256 = "0" } },
            valid with { Active = valid.Active with { ContentId = new string('g', 64) } },
            valid with { StableSetup = valid.StableSetup with { Version = "not-semver" } },
            valid with
            {
                StableSetup = valid.StableSetup with
                {
                    EmbeddedPackageSha256 = valid.StableSetup.EmbeddedPackageSha256.ToUpperInvariant(),
                },
            },
            valid with { StableSetup = valid.StableSetup with { HostSha256 = new string('0', 63) } },
            valid with { StableSetup = valid.StableSetup with { HostBytes = 0 } },
            valid with { StableSetup = valid.StableSetup with { HostBytes = 513L * 1024 * 1024 } },
            valid with { Shortcut = valid.Shortcut with { Sha256 = "foreign" } },
            valid with { Shortcut = valid.Shortcut with { Bytes = 0 } },
            valid with { Shortcut = valid.Shortcut with { Bytes = 5L * 1024 * 1024 } },
            valid with { EstimatedSizeKilobytes = 0 },
        ];

        foreach (WindowsIntegrationState state in invalid)
        {
            WindowsIntegrationTransaction prepared = tree.Transaction(
                null,
                state,
                WindowsIntegrationOperation.InstallUpdate);
            WindowsIntegrationTransaction transaction = prepared with
            {
                Phase = WindowsIntegrationPhase.ShortcutCommitted,
                Target = state,
            };
            Assert.That(
                () => WindowsIntegrationStore.DecideRecovery(null, transaction),
                Throws.TypeOf<InstallationSafetyException>(),
                state.ToString());
        }
    }

    [Test]
    public void TargetPlan_BindsSetupToProductAndNeverDowngradesMaintenanceHost()
    {
        using IntegrationTestTree tree = IntegrationTestTree.Create();
        WindowsIntegrationState first = tree.State("1.0.0", "first", "1.0.0");
        WindowsIntegrationState second = tree.State("2.0.0", "second", "2.0.0");

        WindowsIntegrationTransaction mismatchedPackage = tree.Transaction(
            null,
            first,
            WindowsIntegrationOperation.InstallUpdate) with
        {
            TargetStableSetup = first.StableSetup with
            {
                EmbeddedPackageSha256 = Hash("different-embedded-package"),
            },
        };
        WindowsIntegrationTransaction mismatchedVersion = tree.Transaction(
            null,
            first,
            WindowsIntegrationOperation.Reconcile) with
        {
            TargetStableSetup = first.StableSetup with { Version = "1.1.0" },
        };

        WindowsIntegrationState rolledBack = tree.State(
            "1.0.0",
            "first",
            stableVersion: second.StableSetup.Version,
            stableSetup: second.StableSetup,
            shortcut: second.Shortcut);
        WindowsIntegrationState exactExistingHost = tree.State(
            "2.0.0",
            "second",
            stableVersion: second.StableSetup.Version,
            stableSetup: second.StableSetup,
            shortcut: second.Shortcut);
        WindowsIntegrationState sameVersionDifferentHost = exactExistingHost with
        {
            StableSetup = exactExistingHost.StableSetup with { HostSha256 = Hash("different-host") },
        };
        WindowsIntegrationState lowerHost = tree.State("1.5.0", "lower", "1.5.0");

        Assert.Multiple(() =>
        {
            Assert.That(
                () => WindowsIntegrationStore.DecideRecovery(null, mismatchedPackage),
                Throws.TypeOf<InstallationSafetyException>());
            Assert.That(
                () => WindowsIntegrationStore.DecideRecovery(null, mismatchedVersion),
                Throws.TypeOf<InstallationSafetyException>());
            Assert.That(
                WindowsIntegrationStore.DecideRecovery(
                    rolledBack.Active,
                    tree.Transaction(
                        rolledBack,
                        exactExistingHost,
                        WindowsIntegrationOperation.InstallUpdate)),
                Is.EqualTo(WindowsIntegrationRecoveryDecision.Abort));
            Assert.That(
                () => WindowsIntegrationStore.DecideRecovery(
                    rolledBack.Active,
                    tree.Transaction(
                        rolledBack,
                        sameVersionDifferentHost,
                        WindowsIntegrationOperation.InstallUpdate)),
                Throws.TypeOf<InstallationSafetyException>());
            Assert.That(
                () => WindowsIntegrationStore.DecideRecovery(
                    rolledBack.Active,
                    tree.Transaction(
                        rolledBack,
                        lowerHost,
                        WindowsIntegrationOperation.InstallUpdate)),
                Throws.TypeOf<InstallationSafetyException>());
        });
    }

    [Test]
    public void TransactionAdvance_RejectsSkipBacktrackAndSnapshotChanges()
    {
        using IntegrationTestTree tree = IntegrationTestTree.Create();
        _ = tree.Store.EnsureInstallationIdentity(tree.Identity);
        WindowsIntegrationTransaction prepared = tree.Transaction(
            null,
            tree.State("1.0.0", "first", "1.0.0"),
            WindowsIntegrationOperation.InstallUpdate);
        tree.Store.BeginTransaction(prepared);

        WindowsIntegrationTransaction[] invalid =
        [
            prepared,
            prepared with { Phase = WindowsIntegrationPhase.ProductCommitted },
            prepared with { TransactionId = Guid.NewGuid().ToString("N"), Phase = WindowsIntegrationPhase.HostStaged },
            prepared with
            {
                Phase = WindowsIntegrationPhase.HostStaged,
                Target = tree.TargetFor(prepared) with { EstimatedSizeKilobytes = 999 },
            },
            prepared with
            {
                Phase = WindowsIntegrationPhase.HostStaged,
                TargetActive = prepared.TargetActive with { PackageSha256 = Hash("changed-plan") },
            },
        ];

        foreach (WindowsIntegrationTransaction transaction in invalid)
        {
            Assert.That(
                () => tree.Store.AdvanceTransaction(prepared, transaction),
                Throws.TypeOf<InstallationSafetyException>());
        }

        Assert.That(tree.Store.RecoverAndReadTransaction(), Is.EqualTo(prepared));
    }

    [Test]
    public void JournalReader_RejectsNonCanonicalButAdoptsCanonicalPreparedNext()
    {
        using IntegrationTestTree canonical = IntegrationTestTree.Create();
        _ = canonical.Store.EnsureInstallationIdentity(canonical.Identity);
        WindowsIntegrationTransaction prepared = canonical.Transaction(
            null,
            canonical.State("1.0.0", "first", "1.0.0"),
            WindowsIntegrationOperation.InstallUpdate);
        canonical.Store.BeginTransaction(prepared);
        string journalPath = canonical.PathOf(WindowsIntegrationStore.TransactionFileName);
        string text = File.ReadAllText(journalPath);
        File.WriteAllText(
            journalPath,
            text.Replace(
                "\"phase\":\"prepared\"",
                "\"phase\":\"prepared\",\"foreign\":true",
                StringComparison.Ordinal),
            new UTF8Encoding(encoderShouldEmitUTF8Identifier: false));
        byte[] foreignJournal = File.ReadAllBytes(journalPath);

        Assert.That(
            () => canonical.Store.RecoverAndReadTransaction(),
            Throws.TypeOf<InstallationSafetyException>());
        Assert.That(File.ReadAllBytes(journalPath), Is.EqualTo(foreignJournal));

        using IntegrationTestTree orphan = IntegrationTestTree.Create();
        _ = orphan.Store.EnsureInstallationIdentity(orphan.Identity);
        WriteCanonicalTransaction(
            orphan.PathOf(WindowsIntegrationStore.TransactionNextFileName),
            orphan.Transaction(
                null,
                orphan.State("1.0.0", "first", "1.0.0"),
                WindowsIntegrationOperation.InstallUpdate));
        WindowsIntegrationTransaction? recovered = orphan.Store.RecoverAndReadTransaction();
        Assert.That(recovered, Is.Not.Null);
        Assert.That(recovered!.Phase, Is.EqualTo(WindowsIntegrationPhase.Prepared));
        Assert.That(File.Exists(orphan.PathOf(WindowsIntegrationStore.TransactionNextFileName)), Is.False);
        Assert.That(File.Exists(orphan.PathOf(WindowsIntegrationStore.TransactionFileName)), Is.True);
    }

    [Test]
    public void ApplyTarget_RequiresExactDurableJournalBeforeCreatingAnyStateArtifact()
    {
        using IntegrationTestTree tree = IntegrationTestTree.Create();
        _ = tree.Store.EnsureInstallationIdentity(tree.Identity);
        WindowsIntegrationTransaction transaction = tree.Transaction(
            null,
            tree.State("1.0.0", "first", "1.0.0"),
            WindowsIntegrationOperation.InstallUpdate) with
        {
            Phase = WindowsIntegrationPhase.RegistryIntent,
        };

        Assert.That(
            () => tree.Store.ApplyTransactionTarget(transaction),
            Throws.TypeOf<InstallationSafetyException>());
        Assert.That(File.Exists(tree.PathOf(WindowsIntegrationStore.IntegrationFileName)), Is.False);
        Assert.That(File.Exists(tree.PathOf(WindowsIntegrationStore.IntegrationNextFileName)), Is.False);
    }

    [Test]
    public void ReconcileRecovery_UsesTheTargetPlanBeforeTheFullTargetExists()
    {
        using IntegrationTestTree tree = IntegrationTestTree.Create();
        _ = tree.Store.EnsureInstallationIdentity(tree.Identity);
        WindowsIntegrationState before = tree.State("1.0.0", "first", "1.0.0");
        WindowsIntegrationTransaction adoption = tree.Transaction(
            null,
            before,
            WindowsIntegrationOperation.Reconcile);
        Assert.That(
            WindowsIntegrationStore.DecideRecovery(before.Active, adoption),
            Is.EqualTo(WindowsIntegrationRecoveryDecision.RollForward));
    }

    [TestCase("no_lf")]
    [TestCase("crlf")]
    [TestCase("bom")]
    [TestCase("leading_space")]
    [TestCase("extra_property")]
    [TestCase("reordered")]
    [TestCase("wrong_type")]
    [TestCase("duplicate")]
    public void CanonicalReader_RejectsNonCanonicalInstallationJson(string mutation)
    {
        using IntegrationTestTree tree = IntegrationTestTree.Create();
        _ = tree.Store.EnsureInstallationIdentity(tree.Identity);
        string path = tree.PathOf(WindowsIntegrationStore.InstallationIdentityFileName);
        byte[] canonical = File.ReadAllBytes(path);
        File.Delete(path);
        File.WriteAllBytes(path, MutateIdentity(canonical, mutation));

        Assert.That(
            () => tree.Store.ReadInstallationIdentity(),
            Throws.TypeOf<InstallationSafetyException>());
    }

    [Test]
    public void CanonicalReader_RejectsOversizedDirectoryHardlinkAndAlternateStream()
    {
        using IntegrationTestTree oversized = IntegrationTestTree.Create();
        string identityPath = oversized.PathOf(WindowsIntegrationStore.InstallationIdentityFileName);
        File.WriteAllBytes(
            identityPath,
            new byte[PackageContract.MaximumInstallationIdentityBytes + 1]);
        Assert.That(
            () => oversized.Store.ReadInstallationIdentity(),
            Throws.TypeOf<InstallationSafetyException>());

        using IntegrationTestTree directory = IntegrationTestTree.Create();
        Directory.CreateDirectory(directory.PathOf(WindowsIntegrationStore.InstallationIdentityFileName));
        Assert.That(
            () => directory.Store.ReadInstallationIdentity(),
            Throws.TypeOf<InstallationSafetyException>());

        using IntegrationTestTree linked = IntegrationTestTree.Create();
        _ = linked.Store.EnsureInstallationIdentity(linked.Identity);
        string linkedIdentity = linked.PathOf(WindowsIntegrationStore.InstallationIdentityFileName);
        string external = Path.Combine(linked.Outer, "external-identity.json");
        File.Move(linkedIdentity, external);
        if (CreateHardLink(linkedIdentity, external, 0))
        {
            Assert.That(
                () => linked.Store.ReadInstallationIdentity(),
                Throws.TypeOf<InstallationSafetyException>());
        }

        using IntegrationTestTree streamed = IntegrationTestTree.Create();
        _ = streamed.Store.EnsureInstallationIdentity(streamed.Identity);
        string streamedIdentity = streamed.PathOf(WindowsIntegrationStore.InstallationIdentityFileName);
        try
        {
            File.WriteAllText(streamedIdentity + ":foreign", "foreign stream");
            Assert.That(
                () => streamed.Store.ReadInstallationIdentity(),
                Throws.TypeOf<InstallationSafetyException>());
        }
        catch (Exception exception) when (
            exception is IOException or NotSupportedException or UnauthorizedAccessException)
        {
            // The filesystem does not expose NTFS alternate streams; other physical checks still ran.
        }
    }

    [Test]
    public void StateTransition_RejectsForeignOrContradictoryStagingWithoutDeletingIt()
    {
        using IntegrationTestTree tree = IntegrationTestTree.Create();
        _ = tree.Store.EnsureInstallationIdentity(tree.Identity);
        WindowsIntegrationState target = tree.State("1.0.0", "first", "1.0.0");
        WindowsIntegrationTransaction registry = AdvanceTo(
            tree,
            tree.Transaction(null, target, WindowsIntegrationOperation.InstallUpdate),
            WindowsIntegrationPhase.RegistryIntent);
        WindowsIntegrationState foreign = tree.State("9.0.0", "foreign", "9.0.0");
        WriteCanonicalState(tree.PathOf(WindowsIntegrationStore.IntegrationNextFileName), foreign);
        byte[] before = File.ReadAllBytes(tree.PathOf(WindowsIntegrationStore.IntegrationNextFileName));

        Assert.That(
            () => tree.Store.ApplyTransactionTarget(registry),
            Throws.TypeOf<InstallationSafetyException>());
        Assert.That(
            File.ReadAllBytes(tree.PathOf(WindowsIntegrationStore.IntegrationNextFileName)),
            Is.EqualTo(before));
    }

    [Test]
    public void AbortAndComplete_RequireExactJournaledStableSide()
    {
        using IntegrationTestTree tree = IntegrationTestTree.Create();
        _ = tree.Store.EnsureInstallationIdentity(tree.Identity);
        WindowsIntegrationState target = tree.State("1.0.0", "first", "1.0.0");
        WindowsIntegrationTransaction prepared = tree.Transaction(
            null,
            target,
            WindowsIntegrationOperation.InstallUpdate);
        tree.Store.BeginTransaction(prepared);
        tree.Store.AbortTransaction(prepared);
        Assert.That(tree.Store.RecoverAndReadTransaction(), Is.Null);

        WindowsIntegrationTransaction registry = AdvanceTo(
            tree,
            tree.Transaction(null, target, WindowsIntegrationOperation.InstallUpdate),
            WindowsIntegrationPhase.RegistryIntent);
        _ = tree.Store.ApplyTransactionTarget(registry);
        Assert.That(
            () => tree.Store.CompleteTransaction(registry),
            Throws.TypeOf<InstallationSafetyException>());
        Assert.That(
            () => tree.Store.AbortTransaction(registry),
            Throws.TypeOf<InstallationSafetyException>());
        Assert.That(tree.Store.ReadCommittedState(), Is.EqualTo(target));
    }

    private static void Commit(
        IntegrationTestTree tree,
        WindowsIntegrationTransaction prepared)
    {
        WindowsIntegrationTransaction registry = AdvanceTo(
            tree,
            prepared,
            WindowsIntegrationPhase.RegistryIntent);
        _ = tree.Store.ApplyTransactionTarget(registry);
        WindowsIntegrationTransaction integration = registry with
        {
            Phase = WindowsIntegrationPhase.IntegrationCommitted,
        };
        tree.Store.AdvanceTransaction(registry, integration);
        WindowsIntegrationTransaction complete = integration with
        {
            Phase = WindowsIntegrationPhase.Complete,
        };
        tree.Store.AdvanceTransaction(integration, complete);
        tree.Store.CompleteTransaction(complete);
    }

    private static WindowsIntegrationTransaction AdvanceTo(
        IntegrationTestTree tree,
        WindowsIntegrationTransaction prepared,
        string targetPhase)
    {
        tree.Store.BeginTransaction(prepared);
        WindowsIntegrationTransaction current = prepared;
        int targetIndex = Array.IndexOf(WindowsIntegrationPhase.Ordered, targetPhase);
        for (int index = 1; index <= targetIndex; index++)
        {
            WindowsIntegrationTransaction next = current with
            {
                Phase = WindowsIntegrationPhase.Ordered[index],
                Target = string.Equals(
                    WindowsIntegrationPhase.Ordered[index],
                    WindowsIntegrationPhase.ShortcutCommitted,
                    StringComparison.Ordinal)
                    ? tree.TargetFor(prepared)
                    : current.Target,
            };
            tree.Store.AdvanceTransaction(current, next);
            current = next;
        }

        return current;
    }

    private static byte[] MutateIdentity(byte[] canonical, string mutation)
    {
        string text = Encoding.UTF8.GetString(canonical);
        return mutation switch
        {
            "no_lf" => canonical[..^1],
            "crlf" => Encoding.UTF8.GetBytes(text[..^1] + "\r\n"),
            "bom" => [0xef, 0xbb, 0xbf, .. canonical],
            "leading_space" => Encoding.UTF8.GetBytes(" " + text),
            "extra_property" => Encoding.UTF8.GetBytes(text[..^2] + ",\"foreign\":true}\n"),
            "reordered" => ReorderIdentity(text),
            "wrong_type" => Encoding.UTF8.GetBytes(
                text.Replace("\"data_schema\":1", "\"data_schema\":\"1\"", StringComparison.Ordinal)),
            "duplicate" => Encoding.UTF8.GetBytes(
                text.Replace(
                    "\"data_schema\":1",
                    "\"data_schema\":1,\"data_schema\":1",
                    StringComparison.Ordinal)),
            _ => throw new ArgumentOutOfRangeException(nameof(mutation)),
        };
    }

    private static byte[] ReorderIdentity(string canonical)
    {
        using JsonDocument document = JsonDocument.Parse(canonical);
        JsonElement root = document.RootElement;
        string reordered =
            $"{{\"install_id\":{JsonSerializer.Serialize(root.GetProperty("install_id").GetString())}," +
            $"\"schema\":{JsonSerializer.Serialize(root.GetProperty("schema").GetString())}," +
            $"\"data_schema\":{root.GetProperty("data_schema").GetInt32()}," +
            $"\"installation_root\":{JsonSerializer.Serialize(root.GetProperty("installation_root").GetString())}}}\n";
        return Encoding.UTF8.GetBytes(reordered);
    }

    private static void WriteCanonicalState(string path, WindowsIntegrationState state)
    {
        byte[] json = JsonSerializer.SerializeToUtf8Bytes(
            state,
            SetupJsonContext.Default.WindowsIntegrationState);
        File.WriteAllBytes(path, [.. json, (byte)'\n']);
    }

    private static void WriteCanonicalTransaction(
        string path,
        WindowsIntegrationTransaction transaction)
    {
        byte[] json = JsonSerializer.SerializeToUtf8Bytes(
            transaction,
            SetupJsonContext.Default.WindowsIntegrationTransaction);
        File.WriteAllBytes(path, [.. json, (byte)'\n']);
    }

    private static void AssertNoStoreStaging(IntegrationTestTree tree)
    {
        string[] stagingNames =
        [
            WindowsIntegrationStore.InstallationIdentityNextFileName,
            WindowsIntegrationStore.IntegrationNextFileName,
            WindowsIntegrationStore.IntegrationPreviousFileName,
            WindowsIntegrationStore.TransactionNextFileName,
            WindowsIntegrationStore.TransactionPreviousFileName,
            WindowsIntegrationStore.TransactionFileName,
        ];
        foreach (string name in stagingNames)
        {
            Assert.That(File.Exists(tree.PathOf(name)), Is.False, name);
        }
    }

    private static string Hash(string value) =>
        Convert.ToHexStringLower(SHA256.HashData(Encoding.UTF8.GetBytes(value)));

    [DllImport("kernel32.dll", EntryPoint = "CreateHardLinkW", CharSet = CharSet.Unicode, SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool CreateHardLink(
        string fileName,
        string existingFileName,
        nint securityAttributes);

    private sealed class StoreSimulatedCrashException : Exception;

    private sealed class OneShotCrashInjector : IWindowsIntegrationStoreFaultInjector
    {
        private readonly WindowsIntegrationStoreFaultPoint _target;
        private bool _fired;

        internal OneShotCrashInjector(WindowsIntegrationStoreFaultPoint target)
        {
            _target = target;
        }

        public void Checkpoint(WindowsIntegrationStoreFaultPoint point)
        {
            if (!_fired && point == _target)
            {
                _fired = true;
                throw new StoreSimulatedCrashException();
            }
        }
    }

    private sealed class IntegrationTestTree : IDisposable
    {
        private readonly Dictionary<string, WindowsIntegrationState> plannedTargets =
            new(StringComparer.Ordinal);

        private IntegrationTestTree(string outer, string root, string installId)
        {
            Outer = outer;
            Root = root;
            InstallId = installId;
            Store = new WindowsIntegrationStore(root);
            Identity = new WindowsInstallationIdentity
            {
                InstallId = installId,
                DataSchema = PackageContract.DataSchema,
                InstallationRoot = root,
            };
        }

        internal string Outer { get; }

        internal string Root { get; }

        internal string InstallId { get; }

        internal WindowsIntegrationStore Store { get; }

        internal WindowsInstallationIdentity Identity { get; }

        internal static IntegrationTestTree Create()
        {
            string outer = Path.Combine(
                Path.GetTempPath(),
                $"baxy-integration-store-{Guid.NewGuid():N}");
            string root = Path.Combine(outer, "Programs", "BAXY");
            Directory.CreateDirectory(root);
            return new IntegrationTestTree(outer, root, Guid.NewGuid().ToString("N"));
        }

        internal string PathOf(string fileName) => Path.Combine(Root, fileName);

        internal WindowsIntegrationState State(
            string version,
            string salt,
            string stableVersion,
            WindowsIntegrationStableSetupState? stableSetup = null,
            WindowsIntegrationShortcutState? shortcut = null,
            int estimatedSize = 160000)
        {
            string packageHash = Hash($"package-{salt}");
            return new WindowsIntegrationState
            {
                InstallId = InstallId,
                DataSchema = PackageContract.DataSchema,
                InstallationRoot = Root,
                Active = new WindowsIntegrationActiveIdentity
                {
                    Version = version,
                    DataSchema = PackageContract.DataSchema,
                    PackageSha256 = packageHash,
                    ManifestSha256 = Hash($"manifest-{salt}"),
                    ContentId = Hash($"content-{salt}"),
                },
                StableSetup = stableSetup ?? new WindowsIntegrationStableSetupState
                {
                    Version = stableVersion,
                    EmbeddedPackageSha256 = packageHash,
                    HostSha256 = Hash($"host-{salt}"),
                    HostBytes = 85_000_000,
                },
                Shortcut = shortcut ?? new WindowsIntegrationShortcutState
                {
                    Sha256 = Hash("shortcut"),
                    Bytes = 2048,
                },
                EstimatedSizeKilobytes = estimatedSize,
            };
        }

        internal WindowsIntegrationTransaction Transaction(
            WindowsIntegrationState? before,
            WindowsIntegrationState target,
            string operation)
        {
            ArgumentNullException.ThrowIfNull(target);
            WindowsIntegrationTransaction transaction = new()
            {
                TransactionId = Guid.NewGuid().ToString("N"),
                Operation = operation,
                Phase = WindowsIntegrationPhase.Prepared,
                InstallId = InstallId,
                DataSchema = PackageContract.DataSchema,
                InstallationRoot = Root,
                Before = before,
                TargetActive = target.Active,
                TargetStableSetup = target.StableSetup,
                Target = null,
            };
            plannedTargets.Add(transaction.TransactionId, target);
            return transaction;
        }

        internal WindowsIntegrationState TargetFor(WindowsIntegrationTransaction transaction) =>
            plannedTargets.TryGetValue(transaction.TransactionId, out WindowsIntegrationState? target)
                ? target
                : throw new InvalidOperationException("The test transaction has no full target plan.");

        public void Dispose()
        {
            if (Directory.Exists(Outer))
            {
                Directory.Delete(Outer, recursive: true);
            }
        }
    }
}
