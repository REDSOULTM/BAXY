using System.Runtime.ExceptionServices;
using NUnit.Framework;

namespace Baxy.Setup.Tests;

[TestFixture]
public sealed class WindowsShellLinkTests
{
    [Test]
    public void WriteNewVerified_RoundTripsExactUnicodeFieldsOnARealLink()
    {
        using ShellLinkTestTree tree = ShellLinkTestTree.Create();

        RunOnDedicatedSta(() => WindowsShellLink.WriteNewVerified(tree.LinkPath, tree.Specification));

        Assert.That(File.Exists(tree.LinkPath), Is.True);
        RunOnDedicatedSta(() => WindowsShellLink.ReadAndVerify(tree.LinkPath, tree.Specification));
        Assert.That(EnumerateTemporaryLinks(tree.Root), Is.Empty);
    }

    [Test]
    public void WriteNewVerifiedFromJournal_UsesOnlyTheExactTransactionTemporary()
    {
        using ShellLinkTestTree tree = ShellLinkTestTree.Create();
        string transactionId = Guid.NewGuid().ToString("N");
        string temporary = Path.Combine(tree.Root, $".baxy-{transactionId}.lnk");

        RunOnDedicatedSta(
            () => WindowsShellLink.WriteNewVerifiedFromJournal(
                tree.LinkPath,
                temporary,
                tree.Specification));

        Assert.Multiple(() =>
        {
            Assert.That(File.Exists(tree.LinkPath), Is.True);
            Assert.That(File.Exists(temporary), Is.False);
            Assert.That(EnumerateTemporaryLinks(tree.Root), Is.Empty);
        });
        RunOnDedicatedSta(() => WindowsShellLink.ReadAndVerify(tree.LinkPath, tree.Specification));
    }

    [Test]
    public void WriteNewVerifiedFromJournal_PreservesAPreexistingTemporaryPath()
    {
        using ShellLinkTestTree tree = ShellLinkTestTree.Create();
        string temporary = Path.Combine(tree.Root, $".baxy-{Guid.NewGuid():N}.lnk");
        byte[] foreign = [0x46, 0x4f, 0x52, 0x45, 0x49, 0x47, 0x4e];
        File.WriteAllBytes(temporary, foreign);

        Assert.That(
            () => RunOnDedicatedSta(
                () => WindowsShellLink.WriteNewVerifiedFromJournal(
                    tree.LinkPath,
                    temporary,
                    tree.Specification)),
            Throws.TypeOf<InstallationSafetyException>());

        Assert.Multiple(() =>
        {
            Assert.That(File.ReadAllBytes(temporary), Is.EqualTo(foreign));
            Assert.That(File.Exists(tree.LinkPath), Is.False);
        });
    }

    [TestCase(".baxy-NOT-A-GUID.lnk")]
    [TestCase("foreign.lnk")]
    public void WriteNewVerifiedFromJournal_RejectsAnUnownedTemporaryName(string leaf)
    {
        using ShellLinkTestTree tree = ShellLinkTestTree.Create();
        string temporary = Path.Combine(tree.Root, leaf);

        Assert.That(
            () => RunOnDedicatedSta(
                () => WindowsShellLink.WriteNewVerifiedFromJournal(
                    tree.LinkPath,
                    temporary,
                    tree.Specification)),
            Throws.TypeOf<InstallationSafetyException>());
        Assert.That(File.Exists(tree.LinkPath), Is.False);
    }

    [Test]
    public void WriteNewVerified_RefusesToOverwriteAndPreservesForeignBytes()
    {
        using ShellLinkTestTree tree = ShellLinkTestTree.Create();
        byte[] foreignBytes = [0x42, 0x41, 0x58, 0x59];
        File.WriteAllBytes(tree.LinkPath, foreignBytes);

        Assert.Throws<InstallationSafetyException>(
            () => RunOnDedicatedSta(
                () => WindowsShellLink.WriteNewVerified(tree.LinkPath, tree.Specification)));

        Assert.That(File.ReadAllBytes(tree.LinkPath), Is.EqualTo(foreignBytes));
        Assert.That(EnumerateTemporaryLinks(tree.Root), Is.Empty);
    }

    [Test]
    public void ReadAndVerify_RejectsAValidLinkWithForeignExactFields()
    {
        using ShellLinkTestTree tree = ShellLinkTestTree.Create();
        string foreignTarget = Path.Combine(tree.Root, "BAXY foreign.exe");
        string foreignLink = Path.Combine(tree.Root, "BAXY foreign.lnk");
        File.WriteAllBytes(foreignTarget, [0x4d, 0x5a]);
        ShellLinkSpecification foreignSpecification = tree.Specification with
        {
            TargetPath = foreignTarget,
            Description = "Foreign shell link",
        };

        RunOnDedicatedSta(() => WindowsShellLink.WriteNewVerified(tree.LinkPath, tree.Specification));
        RunOnDedicatedSta(() => WindowsShellLink.WriteNewVerified(foreignLink, foreignSpecification));
        File.Move(foreignLink, tree.LinkPath, overwrite: true);

        Assert.Throws<InstallationSafetyException>(
            () => RunOnDedicatedSta(
                () => WindowsShellLink.ReadAndVerify(tree.LinkPath, tree.Specification)));
        Assert.That(EnumerateTemporaryLinks(tree.Root), Is.Empty);
    }

    [Test]
    public void Operations_RejectAThreadWithoutAnExplicitStaApartment()
    {
        using ShellLinkTestTree tree = ShellLinkTestTree.Create();
        Exception? observed = null;
        Thread thread = new(() =>
        {
            try
            {
                WindowsShellLink.WriteNewVerified(tree.LinkPath, tree.Specification);
            }
            catch (Exception exception)
            {
                observed = exception;
            }
        });
        thread.SetApartmentState(ApartmentState.MTA);

        thread.Start();
        Assert.That(thread.Join(TimeSpan.FromSeconds(30)), Is.True);

        Assert.That(observed, Is.TypeOf<InstallationSafetyException>());
        Assert.That(File.Exists(tree.LinkPath), Is.False);
        Assert.That(EnumerateTemporaryLinks(tree.Root), Is.Empty);
    }

    [Test]
    public void WriteNewVerified_RejectsUnsafeInputBeforeCreatingATemporaryLink()
    {
        using ShellLinkTestTree tree = ShellLinkTestTree.Create();
        ShellLinkSpecification invalid = tree.Specification with
        {
            Arguments = "unsafe\0argument",
        };

        Assert.Throws<InstallationSafetyException>(
            () => RunOnDedicatedSta(() => WindowsShellLink.WriteNewVerified(tree.LinkPath, invalid)));

        Assert.That(File.Exists(tree.LinkPath), Is.False);
        Assert.That(EnumerateTemporaryLinks(tree.Root), Is.Empty);
    }

    private static string[] EnumerateTemporaryLinks(string root)
    {
        return Directory.GetFiles(root, ".baxy-*.lnk", SearchOption.TopDirectoryOnly);
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
            throw new TimeoutException("The dedicated shell-link STA thread did not finish.");
        }

        if (observed is not null)
        {
            ExceptionDispatchInfo.Capture(observed).Throw();
        }
    }

    private sealed class ShellLinkTestTree : IDisposable
    {
        private ShellLinkTestTree(
            string root,
            string linkPath,
            ShellLinkSpecification specification)
        {
            Root = root;
            LinkPath = linkPath;
            Specification = specification;
        }

        internal string Root { get; }

        internal string LinkPath { get; }

        internal ShellLinkSpecification Specification { get; }

        internal static ShellLinkTestTree Create()
        {
            string root = Path.Combine(
                Path.GetTempPath(),
                $"baxy-shell-link-{Guid.NewGuid():N}",
                "área-ñ-漢字");
            string workingDirectory = Path.Combine(root, "trabajo-ñ-漢字");
            Directory.CreateDirectory(workingDirectory);
            string target = Path.Combine(root, "BAXY-ñ-漢字.exe");
            string icon = Path.Combine(root, "BAXY-ñ-漢字.ico");
            File.WriteAllBytes(target, [0x4d, 0x5a]);
            File.WriteAllBytes(icon, [0x00, 0x00, 0x01, 0x00]);
            string link = Path.Combine(root, "BAXY-ñ-漢字.lnk");
            ShellLinkSpecification specification = new(
                target,
                workingDirectory,
                "BAXY — Español / English / Spanglish ñ 漢字",
                "--mode \"español-漢字\"",
                icon,
                IconIndex: 0,
                ShowCommand: 1);
            return new ShellLinkTestTree(root, link, specification);
        }

        public void Dispose()
        {
            string? outer = Directory.GetParent(Root)?.FullName;
            if (outer is not null && Directory.Exists(outer))
            {
                Directory.Delete(outer, recursive: true);
            }
        }
    }
}
