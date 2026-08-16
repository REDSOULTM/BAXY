using System.Runtime.ExceptionServices;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using NUnit.Framework;

namespace Baxy.Setup.Tests;

[TestFixture]
public sealed class OwnedStartMenuShortcutTests
{
    [Test]
    public void Probe_IsReadOnlyAndReportsAMissingDirectory()
    {
        using ShortcutTestTree tree = ShortcutTestTree.Create();
        OwnedStartMenuShortcut shortcut = tree.CreateShortcut();

        OwnedStartMenuShortcutSnapshot observed = RunOnDedicatedSta(shortcut.Probe);

        Assert.That(observed, Is.EqualTo(OwnedStartMenuShortcutSnapshot.Missing));
        Assert.That(Directory.Exists(tree.StartMenuDirectory), Is.False);
    }

    [Test]
    public void Ensure_CreatesAndAttestsAnExactPhysicalUnicodeShortcut()
    {
        using ShortcutTestTree tree = ShortcutTestTree.Create();
        OwnedStartMenuShortcut shortcut = tree.CreateShortcut();

        OwnedStartMenuShortcutSnapshot created = RunOnDedicatedSta(shortcut.Ensure);

        Assert.Multiple(() =>
        {
            Assert.That(created.State, Is.EqualTo(OwnedStartMenuShortcutState.Exact));
            Assert.That(created.Sha256, Does.Match("^[0-9a-f]{64}$"));
            Assert.That(created.Bytes, Is.GreaterThan(0));
            Assert.That(File.Exists(tree.ShortcutPath), Is.True);
            Assert.That(new FileInfo(tree.ShortcutPath).Length, Is.EqualTo(created.Bytes));
            Assert.That(EnumerateTemporaryLinks(tree.StartMenuDirectory), Is.Empty);
        });
        RunOnDedicatedSta(
            () => WindowsShellLink.ReadAndVerify(tree.ShortcutPath, tree.Specification));
    }

    [Test]
    public void Ensure_IsIdempotentAndDoesNotRewriteAnExactShortcut()
    {
        using ShortcutTestTree tree = ShortcutTestTree.Create();
        OwnedStartMenuShortcut shortcut = tree.CreateShortcut();
        OwnedStartMenuShortcutSnapshot first = RunOnDedicatedSta(shortcut.Ensure);
        byte[] originalBytes = File.ReadAllBytes(tree.ShortcutPath);
        DateTime originalWriteTime = File.GetLastWriteTimeUtc(tree.ShortcutPath);

        OwnedStartMenuShortcutSnapshot second = RunOnDedicatedSta(shortcut.Ensure);

        Assert.Multiple(() =>
        {
            Assert.That(second, Is.EqualTo(first));
            Assert.That(File.ReadAllBytes(tree.ShortcutPath), Is.EqualTo(originalBytes));
            Assert.That(File.GetLastWriteTimeUtc(tree.ShortcutPath), Is.EqualTo(originalWriteTime));
            Assert.That(EnumerateTemporaryLinks(tree.StartMenuDirectory), Is.Empty);
        });
    }

    [Test]
    public void EnsureFromJournal_CreatesAnExactLinkWithoutTemporaryResidue()
    {
        using ShortcutTestTree tree = ShortcutTestTree.Create();
        OwnedStartMenuShortcut shortcut = tree.CreateShortcut();
        string transactionId = Guid.NewGuid().ToString("N");

        OwnedStartMenuShortcutSnapshot created = RunOnDedicatedSta(
            () => shortcut.EnsureFromJournal(transactionId));

        Assert.Multiple(() =>
        {
            Assert.That(created.State, Is.EqualTo(OwnedStartMenuShortcutState.Exact));
            Assert.That(File.Exists(tree.ShortcutPath), Is.True);
            Assert.That(EnumerateTemporaryLinks(tree.StartMenuDirectory), Is.Empty);
        });
    }

    [Test]
    public void EnsureFromJournal_PromotesAnExactTemporaryLeftByAnInterruptedProcess()
    {
        using ShortcutTestTree tree = ShortcutTestTree.Create();
        Directory.CreateDirectory(tree.StartMenuDirectory);
        string transactionId = Guid.NewGuid().ToString("N");
        string temporary = JournalTemporary(tree, transactionId);
        RunOnDedicatedSta(
            () => WindowsShellLink.WriteNewVerified(temporary, tree.Specification));
        OwnedStartMenuShortcut shortcut = tree.CreateShortcut();

        OwnedStartMenuShortcutSnapshot recovered = RunOnDedicatedSta(
            () => shortcut.EnsureFromJournal(transactionId));

        Assert.Multiple(() =>
        {
            Assert.That(recovered.State, Is.EqualTo(OwnedStartMenuShortcutState.Exact));
            Assert.That(File.Exists(tree.ShortcutPath), Is.True);
            Assert.That(File.Exists(temporary), Is.False);
        });
    }

    [Test]
    public void EnsureFromJournal_RemovesOnlyAnExactRedundantTemporaryAfterCommit()
    {
        using ShortcutTestTree tree = ShortcutTestTree.Create();
        OwnedStartMenuShortcut shortcut = tree.CreateShortcut();
        OwnedStartMenuShortcutSnapshot committed = RunOnDedicatedSta(shortcut.Ensure);
        string transactionId = Guid.NewGuid().ToString("N");
        string temporary = JournalTemporary(tree, transactionId);
        RunOnDedicatedSta(
            () => WindowsShellLink.WriteNewVerified(temporary, tree.Specification));

        OwnedStartMenuShortcutSnapshot recovered = RunOnDedicatedSta(
            () => shortcut.EnsureFromJournal(transactionId));

        Assert.Multiple(() =>
        {
            Assert.That(recovered, Is.EqualTo(committed));
            Assert.That(File.Exists(temporary), Is.False);
            Assert.That(File.Exists(tree.ShortcutPath), Is.True);
        });
    }

    [Test]
    public void EnsureFromJournal_RejectsAndPreservesAForeignTemporary()
    {
        using ShortcutTestTree tree = ShortcutTestTree.Create();
        Directory.CreateDirectory(tree.StartMenuDirectory);
        string transactionId = Guid.NewGuid().ToString("N");
        string temporary = JournalTemporary(tree, transactionId);
        byte[] foreign = [0x46, 0x4f, 0x52, 0x45, 0x49, 0x47, 0x4e];
        File.WriteAllBytes(temporary, foreign);
        OwnedStartMenuShortcut shortcut = tree.CreateShortcut();

        Assert.That(
            () => RunOnDedicatedSta(() => shortcut.EnsureFromJournal(transactionId)),
            Throws.TypeOf<InstallationSafetyException>());

        Assert.Multiple(() =>
        {
            Assert.That(File.ReadAllBytes(temporary), Is.EqualTo(foreign));
            Assert.That(File.Exists(tree.ShortcutPath), Is.False);
        });
    }

    [TestCase("")]
    [TestCase("00000000-0000-0000-0000-000000000000")]
    [TestCase("ABCDEF0123456789ABCDEF0123456789")]
    public void EnsureFromJournal_RejectsANoncanonicalTransactionWithoutMutation(string transactionId)
    {
        using ShortcutTestTree tree = ShortcutTestTree.Create();
        OwnedStartMenuShortcut shortcut = tree.CreateShortcut();

        Assert.That(
            () => RunOnDedicatedSta(() => shortcut.EnsureFromJournal(transactionId)),
            Throws.TypeOf<InstallationSafetyException>());
        Assert.That(Directory.Exists(tree.StartMenuDirectory), Is.False);
    }

    [Test]
    public void Ensure_NeverOverwritesForeignBytes()
    {
        using ShortcutTestTree tree = ShortcutTestTree.Create();
        Directory.CreateDirectory(tree.StartMenuDirectory);
        byte[] foreign = [0x42, 0x41, 0x58, 0x59];
        File.WriteAllBytes(tree.ShortcutPath, foreign);
        OwnedStartMenuShortcut shortcut = tree.CreateShortcut();

        Assert.That(
            () => RunOnDedicatedSta(shortcut.Ensure),
            Throws.TypeOf<InstallationSafetyException>());

        Assert.Multiple(() =>
        {
            Assert.That(File.ReadAllBytes(tree.ShortcutPath), Is.EqualTo(foreign));
            Assert.That(EnumerateTemporaryLinks(tree.StartMenuDirectory), Is.Empty);
        });
    }

    [Test]
    public void Ensure_RejectsAnInvalidSpecificationBeforeCreatingTheOwnedDirectory()
    {
        using ShortcutTestTree tree = ShortcutTestTree.Create();
        OwnedStartMenuShortcut shortcut = new(
            tree.StartMenuDirectory,
            tree.ShortcutPath,
            tree.Specification with { Arguments = "unsafe\0argument" });

        Assert.That(
            () => RunOnDedicatedSta(shortcut.Ensure),
            Throws.TypeOf<InstallationSafetyException>());

        Assert.Multiple(() =>
        {
            Assert.That(Directory.Exists(tree.StartMenuDirectory), Is.False);
            Assert.That(File.Exists(tree.ShortcutPath), Is.False);
            Assert.That(EnumerateTemporaryLinks(tree.StartMenuDirectory), Is.Empty);
        });
    }

    [Test]
    public void ProbeAndDelete_RejectASemanticallyForeignLinkAndPreserveIt()
    {
        using ShortcutTestTree tree = ShortcutTestTree.Create();
        Directory.CreateDirectory(tree.StartMenuDirectory);
        ShellLinkSpecification foreign = tree.CreateForeignSpecification();
        RunOnDedicatedSta(
            () => WindowsShellLink.WriteNewVerified(tree.ShortcutPath, foreign));
        byte[] foreignBytes = File.ReadAllBytes(tree.ShortcutPath);
        OwnedStartMenuShortcut shortcut = tree.CreateShortcut();

        Assert.That(
            () => RunOnDedicatedSta(shortcut.Probe),
            Throws.TypeOf<InstallationSafetyException>());
        Assert.That(
            () => RunOnDedicatedSta(
                () => shortcut.DeleteOwnedVerified(new string('0', 64), 1)),
            Throws.TypeOf<InstallationSafetyException>());

        Assert.That(File.ReadAllBytes(tree.ShortcutPath), Is.EqualTo(foreignBytes));
    }

    [Test]
    public void ProbeAndDelete_RejectADirectoryAtTheLinkPathAndPreserveIt()
    {
        using ShortcutTestTree tree = ShortcutTestTree.Create();
        Directory.CreateDirectory(tree.ShortcutPath);
        OwnedStartMenuShortcut shortcut = tree.CreateShortcut();

        Assert.That(
            () => RunOnDedicatedSta(shortcut.Probe),
            Throws.TypeOf<InstallationSafetyException>());
        Assert.That(
            () => RunOnDedicatedSta(
                () => shortcut.DeleteOwnedVerified(new string('0', 64), 1)),
            Throws.TypeOf<InstallationSafetyException>());

        Assert.That(Directory.Exists(tree.ShortcutPath), Is.True);
    }

    [Test]
    public void ProbeAndDelete_RejectAReparsePointAtTheLinkPathAndPreserveIt()
    {
        using ShortcutTestTree tree = ShortcutTestTree.Create();
        Directory.CreateDirectory(tree.StartMenuDirectory);
        string targetDirectory = Path.Combine(tree.AssetsDirectory, "foreign-target");
        string targetLink = Path.Combine(targetDirectory, "target.lnk");
        Directory.CreateDirectory(targetDirectory);
        RunOnDedicatedSta(
            () => WindowsShellLink.WriteNewVerified(targetLink, tree.Specification));
        _ = Baxy.Tests.NtfsTestJunction.Create(tree.ShortcutPath, targetDirectory);
        try
        {
            OwnedStartMenuShortcut shortcut = tree.CreateShortcut();
            Assert.That(
                () => RunOnDedicatedSta(shortcut.Probe),
                Throws.TypeOf<InstallationSafetyException>());
            Assert.That(
                () => RunOnDedicatedSta(
                    () => shortcut.DeleteOwnedVerified(new string('0', 64), 1)),
                Throws.TypeOf<InstallationSafetyException>());

            Assert.Multiple(() =>
            {
                Assert.That(File.GetAttributes(tree.ShortcutPath) & FileAttributes.ReparsePoint, Is.Not.Zero);
                Assert.That(File.Exists(targetLink), Is.True);
            });
        }
        finally
        {
            if (Path.Exists(tree.ShortcutPath))
            {
                Directory.Delete(tree.ShortcutPath);
            }
        }
    }

    [Test]
    public void ProbeAndDelete_RejectAHardLinkedShortcutAndPreserveBothNames()
    {
        using ShortcutTestTree tree = ShortcutTestTree.Create();
        OwnedStartMenuShortcut shortcut = tree.CreateShortcut();
        OwnedStartMenuShortcutSnapshot created = RunOnDedicatedSta(shortcut.Ensure);
        string alias = Path.Combine(tree.AssetsDirectory, "hard-link-alias.lnk");
        Assert.That(CreateHardLink(alias, tree.ShortcutPath, 0), Is.True,
            $"CreateHardLinkW failed with Win32 error {Marshal.GetLastWin32Error()}.");

        Assert.That(
            () => RunOnDedicatedSta(shortcut.Probe),
            Throws.TypeOf<InstallationSafetyException>());
        Assert.That(
            () => RunOnDedicatedSta(
                () => shortcut.DeleteOwnedVerified(created.Sha256!, created.Bytes)),
            Throws.TypeOf<InstallationSafetyException>());

        Assert.Multiple(() =>
        {
            Assert.That(File.Exists(tree.ShortcutPath), Is.True);
            Assert.That(File.Exists(alias), Is.True);
        });
    }

    [Test]
    public void ProbeAndDelete_RejectAlternateDataStreamsAndPreserveTheLink()
    {
        using ShortcutTestTree tree = ShortcutTestTree.Create();
        OwnedStartMenuShortcut shortcut = tree.CreateShortcut();
        OwnedStartMenuShortcutSnapshot created = RunOnDedicatedSta(shortcut.Ensure);
        File.WriteAllText(tree.ShortcutPath + ":foreign", "foreign stream");

        Assert.That(
            () => RunOnDedicatedSta(shortcut.Probe),
            Throws.TypeOf<InstallationSafetyException>());
        Assert.That(
            () => RunOnDedicatedSta(
                () => shortcut.DeleteOwnedVerified(created.Sha256!, created.Bytes)),
            Throws.TypeOf<InstallationSafetyException>());

        Assert.Multiple(() =>
        {
            Assert.That(File.Exists(tree.ShortcutPath), Is.True);
            Assert.That(File.ReadAllText(tree.ShortcutPath + ":foreign"), Is.EqualTo("foreign stream"));
        });
    }

    [Test]
    public void DeleteOwnedVerified_DeletesOnlyTheExactIdentityAndRemovesAnEmptyOwnedDirectory()
    {
        using ShortcutTestTree tree = ShortcutTestTree.Create();
        OwnedStartMenuShortcut shortcut = tree.CreateShortcut();
        OwnedStartMenuShortcutSnapshot created = RunOnDedicatedSta(shortcut.Ensure);

        bool deleted = RunOnDedicatedSta(
            () => shortcut.DeleteOwnedVerified(created.Sha256!, created.Bytes));

        Assert.Multiple(() =>
        {
            Assert.That(deleted, Is.True);
            Assert.That(File.Exists(tree.ShortcutPath), Is.False);
            Assert.That(Directory.Exists(tree.StartMenuDirectory), Is.False);
        });
    }

    [Test]
    public void DeleteOwnedVerified_StillRequiresInstallationPathsAfterTheRootWasMoved()
    {
        using ShortcutTestTree tree = ShortcutTestTree.Create();
        OwnedStartMenuShortcut shortcut = tree.CreateShortcut();
        OwnedStartMenuShortcutSnapshot created = RunOnDedicatedSta(shortcut.Ensure);
        string tombstone = tree.MoveInstallationToTombstone();

        Assert.That(
            () => RunOnDedicatedSta(
                () => shortcut.DeleteOwnedVerified(created.Sha256!, created.Bytes)),
            Throws.TypeOf<InstallationSafetyException>());

        Assert.Multiple(() =>
        {
            Assert.That(File.Exists(tree.ShortcutPath), Is.True);
            Assert.That(Directory.Exists(tree.InstallationRoot), Is.False);
            Assert.That(Directory.Exists(tombstone), Is.True);
        });
    }

    [Test]
    public void DeleteOwnedVerifiedAfterInstallationMove_DeletesTheExactHistoricalLink()
    {
        using ShortcutTestTree tree = ShortcutTestTree.Create();
        OwnedStartMenuShortcut shortcut = tree.CreateShortcut();
        OwnedStartMenuShortcutSnapshot created = RunOnDedicatedSta(shortcut.Ensure);
        string tombstone = tree.MoveInstallationToTombstone();

        bool deleted = RunOnDedicatedSta(
            () => shortcut.DeleteOwnedVerifiedAfterInstallationMove(
                created.Sha256!,
                created.Bytes));

        Assert.Multiple(() =>
        {
            Assert.That(deleted, Is.True);
            Assert.That(File.Exists(tree.ShortcutPath), Is.False);
            Assert.That(Directory.Exists(tree.StartMenuDirectory), Is.False);
            Assert.That(Directory.Exists(tree.InstallationRoot), Is.False);
            Assert.That(Directory.Exists(tombstone), Is.True);
        });
    }

    [Test]
    public void DeleteOwnedVerifiedAfterInstallationMove_RejectsForeignSemanticsEvenWithTheirExactIdentity()
    {
        using ShortcutTestTree tree = ShortcutTestTree.Create();
        Directory.CreateDirectory(tree.StartMenuDirectory);
        ShellLinkSpecification foreign = tree.CreateForeignSpecification();
        RunOnDedicatedSta(
            () => WindowsShellLink.WriteNewVerified(tree.ShortcutPath, foreign));
        byte[] foreignBytes = File.ReadAllBytes(tree.ShortcutPath);
        string foreignSha256 = Convert.ToHexStringLower(SHA256.HashData(foreignBytes));
        _ = tree.MoveInstallationToTombstone();
        OwnedStartMenuShortcut shortcut = tree.CreateShortcut();

        Assert.That(
            () => RunOnDedicatedSta(
                () => shortcut.DeleteOwnedVerifiedAfterInstallationMove(
                    foreignSha256,
                    foreignBytes.LongLength)),
            Throws.TypeOf<InstallationSafetyException>());

        Assert.That(File.ReadAllBytes(tree.ShortcutPath), Is.EqualTo(foreignBytes));
    }

    [Test]
    public void DeleteOwnedVerifiedAfterInstallationMove_RejectsAWrongHashAndPreservesTheLink()
    {
        using ShortcutTestTree tree = ShortcutTestTree.Create();
        OwnedStartMenuShortcut shortcut = tree.CreateShortcut();
        OwnedStartMenuShortcutSnapshot created = RunOnDedicatedSta(shortcut.Ensure);
        byte[] before = File.ReadAllBytes(tree.ShortcutPath);
        string wrongHash = (created.Sha256![0] == '0' ? "1" : "0") + created.Sha256[1..];
        _ = tree.MoveInstallationToTombstone();

        Assert.That(
            () => RunOnDedicatedSta(
                () => shortcut.DeleteOwnedVerifiedAfterInstallationMove(
                    wrongHash,
                    created.Bytes)),
            Throws.TypeOf<InstallationSafetyException>());

        Assert.That(File.ReadAllBytes(tree.ShortcutPath), Is.EqualTo(before));
    }

    [Test]
    public void DeleteOwnedVerifiedAfterInstallationMove_RejectsAReparsePointAndPreservesItsTarget()
    {
        using ShortcutTestTree tree = ShortcutTestTree.Create();
        Directory.CreateDirectory(tree.StartMenuDirectory);
        string targetDirectory = Path.Combine(tree.AssetsDirectory, "exact-target");
        string targetLink = Path.Combine(targetDirectory, "target.lnk");
        Directory.CreateDirectory(targetDirectory);
        RunOnDedicatedSta(
            () => WindowsShellLink.WriteNewVerified(targetLink, tree.Specification));
        byte[] targetBytes = File.ReadAllBytes(targetLink);
        string targetSha256 = Convert.ToHexStringLower(SHA256.HashData(targetBytes));
        _ = Baxy.Tests.NtfsTestJunction.Create(tree.ShortcutPath, targetDirectory);
        try
        {
            _ = tree.MoveInstallationToTombstone();
            OwnedStartMenuShortcut shortcut = tree.CreateShortcut();

            Assert.That(
                () => RunOnDedicatedSta(
                    () => shortcut.DeleteOwnedVerifiedAfterInstallationMove(
                        targetSha256,
                        targetBytes.LongLength)),
                Throws.TypeOf<InstallationSafetyException>());

            Assert.Multiple(() =>
            {
                Assert.That(
                    File.GetAttributes(tree.ShortcutPath) & FileAttributes.ReparsePoint,
                    Is.Not.Zero);
                Assert.That(File.Exists(targetLink), Is.True);
            });
        }
        finally
        {
            if (Path.Exists(tree.ShortcutPath))
            {
                Directory.Delete(tree.ShortcutPath);
            }
        }
    }

    [Test]
    public void DeleteOwnedVerifiedAfterInstallationMove_RejectsAHardLinkAndPreservesBothNames()
    {
        using ShortcutTestTree tree = ShortcutTestTree.Create();
        OwnedStartMenuShortcut shortcut = tree.CreateShortcut();
        OwnedStartMenuShortcutSnapshot created = RunOnDedicatedSta(shortcut.Ensure);
        string alias = Path.Combine(tree.AssetsDirectory, "post-move-hard-link-alias.lnk");
        Assert.That(CreateHardLink(alias, tree.ShortcutPath, 0), Is.True,
            $"CreateHardLinkW failed with Win32 error {Marshal.GetLastWin32Error()}.");
        _ = tree.MoveInstallationToTombstone();

        Assert.That(
            () => RunOnDedicatedSta(
                () => shortcut.DeleteOwnedVerifiedAfterInstallationMove(
                    created.Sha256!,
                    created.Bytes)),
            Throws.TypeOf<InstallationSafetyException>());

        Assert.Multiple(() =>
        {
            Assert.That(File.Exists(tree.ShortcutPath), Is.True);
            Assert.That(File.Exists(alias), Is.True);
        });
    }

    [Test]
    public void DeleteOwnedVerifiedAfterInstallationMove_RejectsAlternateDataStreamsAndPreservesTheLink()
    {
        using ShortcutTestTree tree = ShortcutTestTree.Create();
        OwnedStartMenuShortcut shortcut = tree.CreateShortcut();
        OwnedStartMenuShortcutSnapshot created = RunOnDedicatedSta(shortcut.Ensure);
        File.WriteAllText(tree.ShortcutPath + ":foreign", "foreign stream");
        _ = tree.MoveInstallationToTombstone();

        Assert.That(
            () => RunOnDedicatedSta(
                () => shortcut.DeleteOwnedVerifiedAfterInstallationMove(
                    created.Sha256!,
                    created.Bytes)),
            Throws.TypeOf<InstallationSafetyException>());

        Assert.Multiple(() =>
        {
            Assert.That(File.Exists(tree.ShortcutPath), Is.True);
            Assert.That(
                File.ReadAllText(tree.ShortcutPath + ":foreign"),
                Is.EqualTo("foreign stream"));
        });
    }

    [Test]
    public void DeleteOwnedVerified_PreservesUnrelatedSiblingsAndTheirDirectory()
    {
        using ShortcutTestTree tree = ShortcutTestTree.Create();
        Directory.CreateDirectory(tree.StartMenuDirectory);
        string sibling = Path.Combine(tree.StartMenuDirectory, "keep-me.txt");
        File.WriteAllText(sibling, "not owned");
        OwnedStartMenuShortcut shortcut = tree.CreateShortcut();
        OwnedStartMenuShortcutSnapshot created = RunOnDedicatedSta(shortcut.Ensure);

        bool deleted = RunOnDedicatedSta(
            () => shortcut.DeleteOwnedVerified(created.Sha256!, created.Bytes));

        Assert.Multiple(() =>
        {
            Assert.That(deleted, Is.True);
            Assert.That(File.Exists(tree.ShortcutPath), Is.False);
            Assert.That(Directory.Exists(tree.StartMenuDirectory), Is.True);
            Assert.That(File.ReadAllText(sibling), Is.EqualTo("not owned"));
        });
    }

    [Test]
    public void DeleteOwnedVerified_IsIdempotentForMissingDirectoryAndLink()
    {
        using ShortcutTestTree missingDirectory = ShortcutTestTree.Create();
        OwnedStartMenuShortcut first = missingDirectory.CreateShortcut();
        Assert.That(
            RunOnDedicatedSta(() => first.DeleteOwnedVerified(new string('0', 64), 1)),
            Is.False);

        using ShortcutTestTree emptyDirectory = ShortcutTestTree.Create();
        Directory.CreateDirectory(emptyDirectory.StartMenuDirectory);
        OwnedStartMenuShortcut second = emptyDirectory.CreateShortcut();
        Assert.That(
            RunOnDedicatedSta(() => second.DeleteOwnedVerified(new string('0', 64), 1)),
            Is.False);
        Assert.That(Directory.Exists(emptyDirectory.StartMenuDirectory), Is.False);

        using ShortcutTestTree siblingDirectory = ShortcutTestTree.Create();
        Directory.CreateDirectory(siblingDirectory.StartMenuDirectory);
        string sibling = Path.Combine(siblingDirectory.StartMenuDirectory, "foreign.txt");
        File.WriteAllText(sibling, "foreign");
        OwnedStartMenuShortcut third = siblingDirectory.CreateShortcut();
        Assert.That(
            RunOnDedicatedSta(() => third.DeleteOwnedVerified(new string('0', 64), 1)),
            Is.False);
        Assert.That(File.ReadAllText(sibling), Is.EqualTo("foreign"));
    }

    [Test]
    public void DeleteOwnedVerified_RejectsWrongHashOrByteLengthWithoutDeleting()
    {
        using ShortcutTestTree tree = ShortcutTestTree.Create();
        OwnedStartMenuShortcut shortcut = tree.CreateShortcut();
        OwnedStartMenuShortcutSnapshot created = RunOnDedicatedSta(shortcut.Ensure);
        string wrongHash = (created.Sha256![0] == '0' ? "1" : "0") + created.Sha256[1..];

        Assert.That(
            () => RunOnDedicatedSta(
                () => shortcut.DeleteOwnedVerified(wrongHash, created.Bytes)),
            Throws.TypeOf<InstallationSafetyException>());
        Assert.That(
            () => RunOnDedicatedSta(
                () => shortcut.DeleteOwnedVerified(created.Sha256, created.Bytes + 1)),
            Throws.TypeOf<InstallationSafetyException>());

        Assert.That(File.Exists(tree.ShortcutPath), Is.True);
    }

    [Test]
    public void DeleteOwnedVerified_RejectsAChangedLinkAfterItsOwnedIdentityWasCaptured()
    {
        using ShortcutTestTree tree = ShortcutTestTree.Create();
        OwnedStartMenuShortcut shortcut = tree.CreateShortcut();
        OwnedStartMenuShortcutSnapshot captured = RunOnDedicatedSta(shortcut.Ensure);
        File.Delete(tree.ShortcutPath);
        ShellLinkSpecification foreignSpecification = tree.CreateForeignSpecification();
        RunOnDedicatedSta(
            () => WindowsShellLink.WriteNewVerified(tree.ShortcutPath, foreignSpecification));
        byte[] foreignBytes = File.ReadAllBytes(tree.ShortcutPath);

        Assert.That(
            () => RunOnDedicatedSta(
                () => shortcut.DeleteOwnedVerified(captured.Sha256!, captured.Bytes)),
            Throws.TypeOf<InstallationSafetyException>());

        Assert.That(File.ReadAllBytes(tree.ShortcutPath), Is.EqualTo(foreignBytes));
    }

    [Test]
    public void DeleteOwnedVerified_RejectsASwapBetweenSemanticAndDeleteLocks()
    {
        using ShortcutTestTree tree = ShortcutTestTree.Create();
        OwnedStartMenuShortcut creator = tree.CreateShortcut();
        OwnedStartMenuShortcutSnapshot captured = RunOnDedicatedSta(creator.Ensure);
        byte[] ownedBytes = File.ReadAllBytes(tree.ShortcutPath);
        string ownedBackup = Path.Combine(tree.AssetsDirectory, "owned-backup.lnk");
        string foreignSource = Path.Combine(tree.AssetsDirectory, "foreign-swap.lnk");
        ShellLinkSpecification foreignSpecification = tree.CreateForeignSpecification();
        RunOnDedicatedSta(
            () => WindowsShellLink.WriteNewVerified(foreignSource, foreignSpecification));
        byte[] foreignBytes = File.ReadAllBytes(foreignSource);
        OwnedStartMenuShortcut shortcut = tree.CreateShortcut(new ActionFaultInjector(
            OwnedStartMenuShortcutFaultPoint.BeforeLinkDeleteLock,
            () =>
            {
                File.Move(tree.ShortcutPath, ownedBackup);
                File.Move(foreignSource, tree.ShortcutPath);
            }));

        Assert.That(
            () => RunOnDedicatedSta(
                () => shortcut.DeleteOwnedVerified(captured.Sha256!, captured.Bytes)),
            Throws.TypeOf<InstallationSafetyException>());

        Assert.Multiple(() =>
        {
            Assert.That(File.ReadAllBytes(tree.ShortcutPath), Is.EqualTo(foreignBytes));
            Assert.That(File.ReadAllBytes(ownedBackup), Is.EqualTo(ownedBytes));
        });
    }

    [Test]
    public void DeleteOwnedVerified_FinalHandlePreventsAConcurrentNameSwap()
    {
        using ShortcutTestTree tree = ShortcutTestTree.Create();
        OwnedStartMenuShortcut creator = tree.CreateShortcut();
        OwnedStartMenuShortcutSnapshot captured = RunOnDedicatedSta(creator.Ensure);
        string displaced = Path.Combine(tree.AssetsDirectory, "unexpected-displaced.lnk");
        string replacement = Path.Combine(tree.AssetsDirectory, "replacement.lnk");
        ShellLinkSpecification foreignSpecification = tree.CreateForeignSpecification();
        RunOnDedicatedSta(
            () => WindowsShellLink.WriteNewVerified(replacement, foreignSpecification));
        bool swapWasBlocked = false;
        OwnedStartMenuShortcut shortcut = tree.CreateShortcut(new ActionFaultInjector(
            OwnedStartMenuShortcutFaultPoint.LinkLockedAndVerifiedBeforeDeletion,
            () =>
            {
                try
                {
                    File.Move(tree.ShortcutPath, displaced);
                }
                catch (IOException)
                {
                    swapWasBlocked = true;
                }
            }));

        bool deleted = RunOnDedicatedSta(
            () => shortcut.DeleteOwnedVerified(captured.Sha256!, captured.Bytes));

        Assert.Multiple(() =>
        {
            Assert.That(deleted, Is.True);
            Assert.That(swapWasBlocked, Is.True);
            Assert.That(File.Exists(tree.ShortcutPath), Is.False);
            Assert.That(File.Exists(displaced), Is.False);
            Assert.That(File.Exists(replacement), Is.True);
        });
    }

    [Test]
    public void DeleteOwnedVerified_AFaultBeforeHandleDispositionPreservesTheExactLink()
    {
        using ShortcutTestTree tree = ShortcutTestTree.Create();
        OwnedStartMenuShortcut creator = tree.CreateShortcut();
        OwnedStartMenuShortcutSnapshot captured = RunOnDedicatedSta(creator.Ensure);
        byte[] before = File.ReadAllBytes(tree.ShortcutPath);
        OwnedStartMenuShortcut shortcut = tree.CreateShortcut(
            new ThrowingFaultInjector(
                OwnedStartMenuShortcutFaultPoint.LinkLockedAndVerifiedBeforeDeletion));

        Assert.That(
            () => RunOnDedicatedSta(
                () => shortcut.DeleteOwnedVerified(captured.Sha256!, captured.Bytes)),
            Throws.TypeOf<SimulatedShortcutFaultException>());

        Assert.That(File.ReadAllBytes(tree.ShortcutPath), Is.EqualTo(before));
    }

    [Test]
    public void Constructor_RequiresAbsoluteCanonicalOwnedPathsAndAnExistingParent()
    {
        using ShortcutTestTree tree = ShortcutTestTree.Create();

        Assert.Multiple(() =>
        {
            Assert.That(
                () => new OwnedStartMenuShortcut("BAXY", "BAXY.lnk", tree.Specification),
                Throws.TypeOf<InstallationSafetyException>());
            Assert.That(
                () => new OwnedStartMenuShortcut(
                    Path.Combine(tree.StartMenuParent, "Foreign"),
                    Path.Combine(tree.StartMenuParent, "Foreign", "BAXY.lnk"),
                    tree.Specification),
                Throws.TypeOf<InstallationSafetyException>());
            Assert.That(
                () => new OwnedStartMenuShortcut(
                    tree.StartMenuDirectory,
                    Path.Combine(tree.StartMenuDirectory, "baxy.lnk"),
                    tree.Specification),
                Throws.TypeOf<InstallationSafetyException>());
            Assert.That(
                () => new OwnedStartMenuShortcut(
                    tree.StartMenuDirectory,
                    Path.Combine(tree.StartMenuParent, "BAXY.lnk"),
                    tree.Specification),
                Throws.TypeOf<InstallationSafetyException>());
            Assert.That(
                () => new OwnedStartMenuShortcut(
                    Path.Combine(tree.Root, "missing-parent", "BAXY"),
                    Path.Combine(tree.Root, "missing-parent", "BAXY", "BAXY.lnk"),
                    tree.Specification),
                Throws.TypeOf<InstallationSafetyException>());
        });
    }

    [Test]
    public void Ensure_RollsBackAnEmptyDirectoryAfterADeterministicCreationFault()
    {
        using ShortcutTestTree tree = ShortcutTestTree.Create();
        OwnedStartMenuShortcut shortcut = tree.CreateShortcut(
            new ThrowingFaultInjector(OwnedStartMenuShortcutFaultPoint.DirectoryCreated));

        Assert.That(
            () => RunOnDedicatedSta(shortcut.Ensure),
            Throws.TypeOf<SimulatedShortcutFaultException>());

        Assert.Multiple(() =>
        {
            Assert.That(Directory.Exists(tree.StartMenuDirectory), Is.False);
            Assert.That(File.Exists(tree.ShortcutPath), Is.False);
        });
    }

    [Test]
    public void Ensure_RollsBackOnlyItsVerifiedLinkAfterADeterministicLinkFault()
    {
        using ShortcutTestTree tree = ShortcutTestTree.Create();
        Directory.CreateDirectory(tree.StartMenuDirectory);
        string sibling = Path.Combine(tree.StartMenuDirectory, "unrelated.txt");
        File.WriteAllText(sibling, "preserve");
        OwnedStartMenuShortcut shortcut = tree.CreateShortcut(
            new ThrowingFaultInjector(
                OwnedStartMenuShortcutFaultPoint.LinkCreatedAndVerified));

        Assert.That(
            () => RunOnDedicatedSta(shortcut.Ensure),
            Throws.TypeOf<SimulatedShortcutFaultException>());

        Assert.Multiple(() =>
        {
            Assert.That(File.Exists(tree.ShortcutPath), Is.False);
            Assert.That(File.ReadAllText(sibling), Is.EqualTo("preserve"));
            Assert.That(EnumerateTemporaryLinks(tree.StartMenuDirectory), Is.Empty);
        });
    }

    private static string JournalTemporary(ShortcutTestTree tree, string transactionId) =>
        Path.Combine(tree.StartMenuDirectory, $".baxy-{transactionId}.lnk");

    private static string[] EnumerateTemporaryLinks(string directory)
    {
        return Directory.Exists(directory)
            ? Directory.GetFiles(directory, ".baxy-*.lnk", SearchOption.TopDirectoryOnly)
            : [];
    }

    private static T RunOnDedicatedSta<T>(Func<T> action)
    {
        T? result = default;
        RunOnDedicatedSta(() =>
        {
            result = action();
        });
        return result!;
    }

    private static void RunOnDedicatedSta(Action action)
    {
        Exception? observed = null;
        Thread thread = new(() =>
        {
            try
            {
                action();
            }
            catch (Exception exception)
            {
                observed = exception;
            }
        });
        thread.SetApartmentState(ApartmentState.STA);
        thread.Start();
        if (!thread.Join(TimeSpan.FromSeconds(30)))
        {
            throw new TimeoutException("The dedicated shortcut STA thread did not finish.");
        }

        if (observed is not null)
        {
            ExceptionDispatchInfo.Capture(observed).Throw();
        }
    }

    private sealed class ThrowingFaultInjector(OwnedStartMenuShortcutFaultPoint faultPoint) :
        IOwnedStartMenuShortcutFaultInjector
    {
        public void Checkpoint(OwnedStartMenuShortcutFaultPoint point)
        {
            if (point == faultPoint)
            {
                throw new SimulatedShortcutFaultException();
            }
        }
    }

    private sealed class ActionFaultInjector(
        OwnedStartMenuShortcutFaultPoint faultPoint,
        Action action) : IOwnedStartMenuShortcutFaultInjector
    {
        public void Checkpoint(OwnedStartMenuShortcutFaultPoint point)
        {
            if (point == faultPoint)
            {
                action();
            }
        }
    }

    private sealed class SimulatedShortcutFaultException : Exception;

    private sealed class ShortcutTestTree : IDisposable
    {
        private ShortcutTestTree(
            string root,
            string startMenuParent,
            string startMenuDirectory,
            string shortcutPath,
            string assetsDirectory,
            ShellLinkSpecification specification)
        {
            Root = root;
            StartMenuParent = startMenuParent;
            StartMenuDirectory = startMenuDirectory;
            ShortcutPath = shortcutPath;
            AssetsDirectory = assetsDirectory;
            Specification = specification;
        }

        internal string Root { get; }

        internal string StartMenuParent { get; }

        internal string StartMenuDirectory { get; }

        internal string ShortcutPath { get; }

        internal string AssetsDirectory { get; }

        internal string InstallationRoot => Specification.WorkingDirectory;

        internal ShellLinkSpecification Specification { get; }

        internal static ShortcutTestTree Create()
        {
            string root = Path.Combine(
                Path.GetTempPath(),
                $"baxy-owned-shortcut-{Guid.NewGuid():N}");
            string startMenuParent = Path.Combine(root, "Menú Inicio ñ 漢字", "Programs");
            string startMenuDirectory = Path.Combine(startMenuParent, "BAXY");
            string shortcutPath = Path.Combine(startMenuDirectory, "BAXY.lnk");
            string assets = Path.Combine(root, "recursos ñ 漢字");
            string workingDirectory = Path.Combine(assets, "trabajo ñ 漢字");
            Directory.CreateDirectory(startMenuParent);
            Directory.CreateDirectory(workingDirectory);
            string target = Path.Combine(workingDirectory, "Baxy.Setup.exe");
            string icon = target;
            File.WriteAllBytes(target, [0x4d, 0x5a]);
            ShellLinkSpecification specification = new(
                target,
                workingDirectory,
                "BAXY — Español / English / Spanglish ñ 漢字",
                "--modo \"español-漢字\"",
                icon,
                IconIndex: 0,
                ShowCommand: 1);
            return new ShortcutTestTree(
                root,
                startMenuParent,
                startMenuDirectory,
                shortcutPath,
                assets,
                specification);
        }

        internal OwnedStartMenuShortcut CreateShortcut(
            IOwnedStartMenuShortcutFaultInjector? faultInjector = null)
        {
            return new OwnedStartMenuShortcut(
                StartMenuDirectory,
                ShortcutPath,
                Specification,
                faultInjector);
        }

        internal string MoveInstallationToTombstone()
        {
            string tombstone = Path.Combine(
                Path.GetDirectoryName(InstallationRoot)!,
                $".BAXY-uninstall-{Guid.NewGuid():N}");
            Directory.Move(InstallationRoot, tombstone);
            return tombstone;
        }

        internal ShellLinkSpecification CreateForeignSpecification()
        {
            string target = Path.Combine(AssetsDirectory, "foreign.exe");
            File.WriteAllBytes(target, [0x4d, 0x5a, 0x90]);
            return Specification with
            {
                TargetPath = target,
                Description = "Foreign shortcut",
            };
        }

        public void Dispose()
        {
            if (Directory.Exists(Root))
            {
                Directory.Delete(Root, recursive: true);
            }
        }
    }

    [DllImport(
        "kernel32.dll",
        EntryPoint = "CreateHardLinkW",
        CharSet = CharSet.Unicode,
        SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool CreateHardLink(
        string fileName,
        string existingFileName,
        nint securityAttributes);
}
