using System.Security.AccessControl;
using System.Security.Principal;
using Baxy.Security.Windows;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// The private key directory is created with a protected DACL that only the
/// current user and SYSTEM can reach. Creating it correctly is not enough: a
/// directory that already exists can be weakened afterwards by another program,
/// by a restore, or by someone editing permissions by hand. These tests pin that
/// both the sealing and the reading path repair and re-verify the DACL, and that
/// repairing on read still never creates anything.
/// </summary>
[TestFixture]
public sealed class ProtectedPayloadDaclRepairTests
{
    private const string Purpose = "baxy.tests.dacl-repair";

    [Test]
    public void ReadingAnExistingKeyRepairsAWeakenedDirectoryDacl()
    {
        using TemporaryTree tree = new();
        string keyDirectory = Path.Combine(tree.Path, "security");
        string keyPath = Path.Combine(keyDirectory, "payload.key");
        byte[] envelope = new WindowsProtectedPayload(keyPath).SealUtf8("privado", Purpose);
        Weaken(keyDirectory);

        // Only the seal path used to repair, so a workload that only reads left
        // the directory open to everyone for as long as it kept reading.
        string recovered = new WindowsProtectedPayload(keyPath).OpenUtf8(envelope, Purpose);

        AssertPrivateDacl(keyDirectory, recovered, "privado");
    }

    [Test]
    public void SealingOverAWeakenedDirectoryRepairsItsDacl()
    {
        using TemporaryTree tree = new();
        string keyDirectory = Path.Combine(tree.Path, "security");
        string keyPath = Path.Combine(keyDirectory, "payload.key");
        _ = new WindowsProtectedPayload(keyPath).SealUtf8("uno", Purpose);
        Weaken(keyDirectory);

        var protector = new WindowsProtectedPayload(keyPath);
        byte[] envelope = protector.SealUtf8("dos", Purpose);

        AssertPrivateDacl(keyDirectory, protector.OpenUtf8(envelope, Purpose), "dos");
    }

    [Test]
    public void RepairingOnReadNeverCreatesAMissingStore()
    {
        using TemporaryTree tree = new();
        string keyDirectory = Path.Combine(tree.Path, "absent", "security");
        string keyPath = Path.Combine(keyDirectory, "payload.key");
        byte[] envelope = new byte[64];

        // Reading a store that does not exist must stay a read: the repair added
        // to the read path must not bring the directory into being.
        Assert.Throws<ProtectedPayloadException>(
            () => new WindowsProtectedPayload(keyPath).OpenUtf8(envelope, Purpose));

        Assert.Multiple(() =>
        {
            Assert.That(Directory.Exists(keyDirectory), Is.False);
            Assert.That(Directory.Exists(Path.Combine(tree.Path, "absent")), Is.False);
        });
    }

    private static void Weaken(string keyDirectory)
    {
        var directory = new DirectoryInfo(keyDirectory);
        DirectorySecurity weakened = directory.GetAccessControl();
        weakened.SetAccessRuleProtection(isProtected: false, preserveInheritance: true);
        weakened.AddAccessRule(new FileSystemAccessRule(
            new SecurityIdentifier(WellKnownSidType.WorldSid, null),
            FileSystemRights.FullControl,
            InheritanceFlags.ContainerInherit | InheritanceFlags.ObjectInherit,
            PropagationFlags.None,
            AccessControlType.Allow));
        directory.SetAccessControl(weakened);

        Assert.That(
            new DirectoryInfo(keyDirectory).GetAccessControl().AreAccessRulesProtected,
            Is.False,
            "the directory was not actually weakened, so the test would prove nothing");
    }

    private static void AssertPrivateDacl(
        string keyDirectory,
        string recovered,
        string expectedPlaintext)
    {
        DirectorySecurity after = new DirectoryInfo(keyDirectory).GetAccessControl();
        string[] identities = after
            .GetAccessRules(includeExplicit: true, includeInherited: true, typeof(SecurityIdentifier))
            .Cast<FileSystemAccessRule>()
            .Select(static rule => rule.IdentityReference.Value)
            .ToArray();
        var expected = new[]
        {
            WindowsIdentity.GetCurrent().User!.Value,
            new SecurityIdentifier(WellKnownSidType.LocalSystemSid, null).Value,
        };

        Assert.Multiple(() =>
        {
            Assert.That(recovered, Is.EqualTo(expectedPlaintext));
            Assert.That(after.AreAccessRulesProtected, Is.True);
            Assert.That(identities, Is.EquivalentTo(expected));
        });
    }

    private sealed class TemporaryTree : IDisposable
    {
        internal TemporaryTree()
        {
            Path = System.IO.Path.Combine(
                System.IO.Path.GetTempPath(),
                "baxy-dacl-repair-tests",
                Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(Path);
        }

        internal string Path { get; }

        public void Dispose()
        {
            for (int attempt = 0; attempt < 50; attempt++)
            {
                if (!Directory.Exists(Path))
                {
                    return;
                }

                try
                {
                    Directory.Delete(Path, recursive: true);
                    return;
                }
                catch (IOException)
                {
                    Thread.Sleep(20);
                }
                catch (UnauthorizedAccessException)
                {
                    Thread.Sleep(20);
                }
            }
        }
    }
}
