using System.Security.AccessControl;
using System.Security.Principal;
using System.Text;
using Baxy.Security.Windows;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

[TestFixture]
public sealed class ProtectedPayloadWindowsTests
{
    private const string Purpose = "baxy.memory.journal.v1";

    [Test]
    public void PrivateDataRootIsCreatedOnlyBeneathLocalApplicationDataWithAPrivateDacl()
    {
        string localApplicationData = Environment.GetFolderPath(
            Environment.SpecialFolder.LocalApplicationData,
            Environment.SpecialFolderOption.DoNotVerify);
        string candidate = Path.Combine(
            localApplicationData,
            "BAXY",
            $"baxy-private-root-{Guid.NewGuid():N}");
        try
        {
            string prepared = WindowsPrivateStorage.PreparePrivateDataRoot(candidate);
            DirectorySecurity security = new DirectoryInfo(prepared).GetAccessControl();
            FileSystemAccessRule[] rules = security
                .GetAccessRules(
                    includeExplicit: true,
                    includeInherited: true,
                    typeof(SecurityIdentifier))
                .Cast<FileSystemAccessRule>()
                .ToArray();
            string currentUser = WindowsIdentity.GetCurrent().User!.Value;
            var allowed = new HashSet<string>(StringComparer.Ordinal)
            {
                currentUser,
                new SecurityIdentifier(WellKnownSidType.LocalSystemSid, null).Value,
            };

            Assert.Multiple(() =>
            {
                Assert.That(prepared, Is.EqualTo(Path.GetFullPath(candidate)));
                Assert.That(security.AreAccessRulesProtected, Is.True);
                Assert.That(rules, Has.Length.EqualTo(2));
                Assert.That(
                    rules.Select(static rule => rule.IdentityReference.Value),
                    Is.EquivalentTo(allowed));
            });
        }
        finally
        {
            if (Directory.Exists(candidate))
            {
                Directory.Delete(candidate, recursive: true);
            }
        }
    }

    [Test]
    public void PrivateDataRootRejectsSharedAnchorAnchorItselfAndPrefixSibling()
    {
        string localApplicationData = Environment.GetFolderPath(
            Environment.SpecialFolder.LocalApplicationData,
            Environment.SpecialFolderOption.DoNotVerify);
        string shared = Path.Combine(
            Environment.GetFolderPath(
                Environment.SpecialFolder.CommonApplicationData,
                Environment.SpecialFolderOption.DoNotVerify),
            $"baxy-shared-{Guid.NewGuid():N}");
        string prefixSibling = Path.Combine(
            string.Concat(localApplicationData, "-shared"),
            $"baxy-{Guid.NewGuid():N}");
        string privateParent = Path.Combine(localApplicationData, "BAXY");
        string nested = Path.Combine(
            privateParent,
            $"shared-parent-{Guid.NewGuid():N}",
            "store");

        Assert.Multiple(() =>
        {
            Assert.That(
                () => WindowsPrivateStorage.PreparePrivateDataRoot(localApplicationData),
                Throws.TypeOf<UnsafePrivateStoragePathException>());
            Assert.That(
                () => WindowsPrivateStorage.PreparePrivateDataRoot(privateParent),
                Throws.TypeOf<UnsafePrivateStoragePathException>());
            Assert.That(
                () => WindowsPrivateStorage.PreparePrivateDataRoot(shared),
                Throws.TypeOf<UnsafePrivateStoragePathException>());
            Assert.That(
                () => WindowsPrivateStorage.PreparePrivateDataRoot(prefixSibling),
                Throws.TypeOf<UnsafePrivateStoragePathException>());
            Assert.That(
                () => WindowsPrivateStorage.PreparePrivateDataRoot(nested),
                Throws.TypeOf<UnsafePrivateStoragePathException>());
            Assert.That(Directory.Exists(shared), Is.False);
            Assert.That(Directory.Exists(prefixSibling), Is.False);
            Assert.That(Directory.Exists(Path.GetDirectoryName(nested)!), Is.False);
        });
    }

    [Test]
    public void MissingParentIsReportedAsNotFoundWithoutCreatingDirectories()
    {
        string localApplicationData = Environment.GetFolderPath(
            Environment.SpecialFolder.LocalApplicationData,
            Environment.SpecialFolderOption.DoNotVerify);
        string candidate = Path.Combine(
            localApplicationData,
            "BAXY",
            $"baxy-missing-file-probe-{Guid.NewGuid():N}");
        try
        {
            string prepared = WindowsPrivateStorage.PreparePrivateDataRoot(candidate);
            string missingParent = Path.Combine(prepared, "journal");
            string missingFile = Path.Combine(missingParent, "missions.jsonl");

            bool opened = WindowsPrivateStorage.TryOpenFile(
                missingFile,
                FileAccess.Read,
                FileShare.Read,
                deleteAccess: false,
                out WindowsPrivateFileLease? lease);

            Assert.Multiple(() =>
            {
                Assert.That(opened, Is.False);
                Assert.That(lease, Is.Null);
                Assert.That(Directory.Exists(missingParent), Is.False);
            });
        }
        finally
        {
            if (Directory.Exists(candidate))
            {
                Directory.Delete(candidate, recursive: true);
            }
        }
    }

    [Test]
    public void KeyDirectoryIsCreatedWithAProtectedUserAndSystemDacl()
    {
        using TemporaryDirectory temporary = new();
        string keyDirectory = Path.Combine(temporary.Path, "security");
        var protector = new WindowsProtectedPayload(
            Path.Combine(keyDirectory, "payload.key"));

        _ = protector.SealUtf8("private", Purpose);

        DirectorySecurity security = new DirectoryInfo(keyDirectory).GetAccessControl();
        FileSystemAccessRule[] rules = security
            .GetAccessRules(
                includeExplicit: true,
                includeInherited: true,
                typeof(SecurityIdentifier))
            .Cast<FileSystemAccessRule>()
            .ToArray();
        string currentUser = WindowsIdentity.GetCurrent().User!.Value;
        var allowed = new HashSet<string>(StringComparer.Ordinal)
        {
            currentUser,
            new SecurityIdentifier(WellKnownSidType.LocalSystemSid, null).Value,
        };

        Assert.Multiple(() =>
        {
            Assert.That(security.AreAccessRulesProtected, Is.True);
            Assert.That(rules, Has.Length.EqualTo(2));
            Assert.That(
                rules.Select(static rule => rule.IdentityReference.Value),
                Is.EquivalentTo(allowed));
            Assert.That(rules.All(static rule =>
                rule.AccessControlType == AccessControlType.Allow
                && rule.FileSystemRights.HasFlag(FileSystemRights.FullControl)),
                Is.True);
        });
    }

    [Test]
    public void ProtectedPayloadRoundTripsBinaryAndUtf8AcrossInstances()
    {
        using TemporaryDirectory temporary = new();
        string keyPath = Path.Combine(temporary.Path, "security", "payload.key");
        var first = new WindowsProtectedPayload(keyPath);
        byte[] binary = { 0, 1, 2, 127, 128, 254, 255 };

        byte[] binaryEnvelope = first.Seal(binary, Purpose);
        byte[] utf8Envelope = first.SealUtf8("memoria privada: café 🧭", Purpose);
        var restarted = new WindowsProtectedPayload(keyPath);

        Assert.Multiple(() =>
        {
            Assert.That(first.ProtectionMode,
                Is.EqualTo(WindowsProtectedPayload.WindowsDpapiCurrentUserProtectionMode));
            Assert.That(first.ProtectionMode, Is.EqualTo("windows-dpapi-current-user"));
            Assert.That(first.KeyFilePath, Is.EqualTo(Path.GetFullPath(keyPath)));
            Assert.That(restarted.Open(binaryEnvelope, Purpose), Is.EqualTo(binary));
            Assert.That(
                restarted.OpenUtf8(utf8Envelope, Purpose),
                Is.EqualTo("memoria privada: café 🧭"));
        });
    }

    [Test]
    public void ProtectedPayloadUsesRandomNoncesForRepeatedPlaintext()
    {
        using TemporaryDirectory temporary = new();
        var protector = CreateProtector(temporary);

        byte[] first = protector.SealUtf8("mismo secreto", Purpose);
        byte[] second = protector.SealUtf8("mismo secreto", Purpose);

        Assert.Multiple(() =>
        {
            Assert.That(second, Is.Not.EqualTo(first));
            Assert.That(protector.OpenUtf8(first, Purpose), Is.EqualTo("mismo secreto"));
            Assert.That(protector.OpenUtf8(second, Purpose), Is.EqualTo("mismo secreto"));
        });
    }

    [Test]
    public void ProtectedPayloadBindsAuthenticationToExactPurpose()
    {
        using TemporaryDirectory temporary = new();
        var protector = CreateProtector(temporary);
        const string secret = "no debe aparecer en errores";
        byte[] envelope = protector.SealUtf8(secret, "baxy.memory.outbox.v1");

        ProtectedPayloadException? exception = Assert.Throws<ProtectedPayloadException>(
            () => protector.OpenUtf8(envelope, "baxy.memory.journal.v1"));

        Assert.Multiple(() =>
        {
            Assert.That(exception, Is.Not.Null);
            Assert.That(exception!.ErrorCode, Is.EqualTo(ProtectedPayloadErrorCode.InvalidEnvelope));
            Assert.That(exception.Message, Does.Not.Contain(secret));
            Assert.That(exception.Message, Does.Not.Contain("baxy.memory"));
        });
    }

    [Test]
    public void ProtectedPayloadRejectsHeaderNonceTagAndCiphertextTampering()
    {
        using TemporaryDirectory temporary = new();
        var protector = CreateProtector(temporary);
        byte[] envelope = protector.SealUtf8("contenido autenticado", Purpose);
        int[] offsets = { 0, 16, 28, envelope.Length - 1 };

        foreach (int offset in offsets)
        {
            byte[] tampered = (byte[])envelope.Clone();
            tampered[offset] ^= 0x40;
            ProtectedPayloadException? exception = Assert.Throws<ProtectedPayloadException>(
                () => protector.Open(tampered, Purpose));
            Assert.That(exception!.ErrorCode, Is.EqualTo(ProtectedPayloadErrorCode.InvalidEnvelope));
        }
    }

    [Test]
    public void ProtectedPayloadRejectsCorruptKeyWithoutReplacingIt()
    {
        using TemporaryDirectory temporary = new();
        string keyPath = Path.Combine(temporary.Path, "payload.key");
        var protector = new WindowsProtectedPayload(keyPath);
        byte[] envelope = protector.SealUtf8("dato durable", Purpose);
        byte[] corrupted = File.ReadAllBytes(keyPath);
        corrupted[^1] ^= 0x80;
        File.WriteAllBytes(keyPath, corrupted);

        ProtectedPayloadException? exception = Assert.Throws<ProtectedPayloadException>(
            () => new WindowsProtectedPayload(keyPath).Open(envelope, Purpose));

        Assert.Multiple(() =>
        {
            Assert.That(exception, Is.Not.Null);
            Assert.That(exception!.ErrorCode, Is.EqualTo(ProtectedPayloadErrorCode.InvalidKeyStore));
            Assert.That(File.ReadAllBytes(keyPath), Is.EqualTo(corrupted));
        });
    }

    [Test]
    public void ProtectedPayloadFailsClosedOnPartialPreexistingKey()
    {
        using TemporaryDirectory temporary = new();
        string keyPath = Path.Combine(temporary.Path, "payload.key");
        byte[] partial = "BAXYKEY1"u8.ToArray();
        File.WriteAllBytes(keyPath, partial);
        var protector = new WindowsProtectedPayload(keyPath);

        ProtectedPayloadException? exception = Assert.Throws<ProtectedPayloadException>(
            () => protector.SealUtf8("no escribir", Purpose));

        Assert.Multiple(() =>
        {
            Assert.That(exception, Is.Not.Null);
            Assert.That(exception!.ErrorCode, Is.EqualTo(ProtectedPayloadErrorCode.InvalidKeyStore));
            Assert.That(File.ReadAllBytes(keyPath), Is.EqualTo(partial));
        });
    }

    [Test]
    public void ProtectedPayloadOpenDoesNotSilentlyRegenerateAMissingKey()
    {
        using TemporaryDirectory temporary = new();
        byte[] envelope = CreateProtectorWithoutKey(temporary).SealUtf8("dato", Purpose);
        string missingKeyPath = Path.Combine(temporary.Path, "missing", "payload.key");
        var protector = new WindowsProtectedPayload(missingKeyPath);

        ProtectedPayloadException? exception = Assert.Throws<ProtectedPayloadException>(
            () => protector.OpenUtf8(envelope, Purpose));

        Assert.Multiple(() =>
        {
            Assert.That(exception!.ErrorCode, Is.EqualTo(ProtectedPayloadErrorCode.InvalidKeyStore));
            Assert.That(File.Exists(missingKeyPath), Is.False);
            Assert.That(Directory.Exists(Path.GetDirectoryName(missingKeyPath)!), Is.False);
        });
    }

    [Test]
    public void PublishedSentinelPreventsKeyRegenerationAfterDeletionForSealOpenAndRestart()
    {
        using TemporaryDirectory temporary = new();
        string keyPath = Path.Combine(temporary.Path, "payload.key");
        string sentinelPath = string.Concat(keyPath, ".sentinel");
        var protector = new WindowsProtectedPayload(keyPath);
        byte[] envelope = protector.SealUtf8("dato durable", Purpose);
        byte[] sentinel = File.ReadAllBytes(sentinelPath);
        File.Delete(keyPath);

        ProtectedPayloadException? sameSeal = Assert.Throws<ProtectedPayloadException>(
            () => protector.SealUtf8("no rotar", Purpose));
        ProtectedPayloadException? sameOpen = Assert.Throws<ProtectedPayloadException>(
            () => protector.OpenUtf8(envelope, Purpose));
        var restarted = new WindowsProtectedPayload(keyPath);
        ProtectedPayloadException? restartedSeal = Assert.Throws<ProtectedPayloadException>(
            () => restarted.SealUtf8("tampoco rotar", Purpose));
        ProtectedPayloadException? restartedOpen = Assert.Throws<ProtectedPayloadException>(
            () => restarted.OpenUtf8(envelope, Purpose));

        Assert.Multiple(() =>
        {
            Assert.That(sentinel.AsSpan(0, 8).ToArray(), Is.EqualTo("BAXYSNT1"u8.ToArray()));
            Assert.That(sentinel[8], Is.EqualTo(1));
            Assert.That(sentinel, Has.Length.EqualTo(48));
            Assert.That(sameSeal!.ErrorCode, Is.EqualTo(ProtectedPayloadErrorCode.InvalidKeyStore));
            Assert.That(sameOpen!.ErrorCode, Is.EqualTo(ProtectedPayloadErrorCode.InvalidKeyStore));
            Assert.That(restartedSeal!.ErrorCode, Is.EqualTo(ProtectedPayloadErrorCode.InvalidKeyStore));
            Assert.That(restartedOpen!.ErrorCode, Is.EqualTo(ProtectedPayloadErrorCode.InvalidKeyStore));
            Assert.That(File.Exists(keyPath), Is.False);
            Assert.That(File.ReadAllBytes(sentinelPath), Is.EqualTo(sentinel));
            Assert.That(Directory.EnumerateFiles(temporary.Path, "*.tmp"), Is.Empty);
        });
    }

    [Test]
    public void ProtectedPayloadRejectsCorruptSentinelWithoutReplacingIt()
    {
        using TemporaryDirectory temporary = new();
        string keyPath = Path.Combine(temporary.Path, "payload.key");
        string sentinelPath = string.Concat(keyPath, ".sentinel");
        var protector = new WindowsProtectedPayload(keyPath);
        byte[] envelope = protector.SealUtf8("dato", Purpose);
        byte[] partial = "BAXYSNT1"u8.ToArray();
        File.WriteAllBytes(sentinelPath, partial);

        ProtectedPayloadException? sealException = Assert.Throws<ProtectedPayloadException>(
            () => protector.SealUtf8("otro", Purpose));
        ProtectedPayloadException? openException = Assert.Throws<ProtectedPayloadException>(
            () => protector.OpenUtf8(envelope, Purpose));

        Assert.Multiple(() =>
        {
            Assert.That(sealException!.ErrorCode,
                Is.EqualTo(ProtectedPayloadErrorCode.InvalidKeyStore));
            Assert.That(openException!.ErrorCode,
                Is.EqualTo(ProtectedPayloadErrorCode.InvalidKeyStore));
            Assert.That(File.ReadAllBytes(sentinelPath), Is.EqualTo(partial));
        });
    }

    [Test]
    public void ProtectedPayloadRejectsOversizedKeyBeforeReadingIt()
    {
        using TemporaryDirectory temporary = new();
        string keyPath = Path.Combine(temporary.Path, "payload.key");
        byte[] oversized = new byte[(64 * 1024) + 1];
        File.WriteAllBytes(keyPath, oversized);
        var protector = new WindowsProtectedPayload(keyPath);

        ProtectedPayloadException? exception = Assert.Throws<ProtectedPayloadException>(
            () => protector.Open(new byte[44], Purpose));

        Assert.That(exception!.ErrorCode, Is.EqualTo(ProtectedPayloadErrorCode.InvalidEnvelope));

        byte[] structurallyValidEnvelope = CreateProtectorWithoutKey(temporary).SealUtf8("x", Purpose);
        exception = Assert.Throws<ProtectedPayloadException>(
            () => protector.Open(structurallyValidEnvelope, Purpose));
        Assert.That(exception!.ErrorCode, Is.EqualTo(ProtectedPayloadErrorCode.InvalidKeyStore));
    }

    [Test]
    public void ProtectedPayloadInitializesOneDurableKeyUnderConcurrency()
    {
        using TemporaryDirectory temporary = new();
        string keyPath = Path.Combine(temporary.Path, "nested", "payload.key");
        using var start = new ManualResetEventSlim(false);
        Task<byte[]>[] writers = Enumerable.Range(0, 24)
            .Select(index => Task.Run(() =>
            {
                start.Wait();
                return new WindowsProtectedPayload(keyPath)
                    .SealUtf8($"entrada-{index}", Purpose);
            }))
            .ToArray();

        start.Set();
        Task.WaitAll(writers);
        var reader = new WindowsProtectedPayload(keyPath);

        Assert.Multiple(() =>
        {
            Assert.That(File.Exists(keyPath), Is.True);
            Assert.That(File.Exists(string.Concat(keyPath, ".sentinel")), Is.True);
            Assert.That(
                writers.Select((writer, index) => reader.OpenUtf8(writer.Result, Purpose)),
                Is.EqualTo(Enumerable.Range(0, writers.Length).Select(index => $"entrada-{index}")));
            Assert.That(
                Directory.EnumerateFiles(Path.GetDirectoryName(keyPath)!, "*.tmp"),
                Is.Empty);
        });
    }

    [Test]
    public void ProtectedPayloadRejectsAnUnusedDriveBecauseItIsNotFixedStorage()
    {
        HashSet<char> mountedDriveLetters = DriveInfo.GetDrives()
            .Select(drive => char.ToUpperInvariant(drive.Name[0]))
            .ToHashSet();
        char? unusedDriveLetter = Enumerable.Range('D', ('Z' - 'D') + 1)
            .Select(value => (char)value)
            .FirstOrDefault(letter => !mountedDriveLetters.Contains(letter));
        if (unusedDriveLetter is null or '\0')
        {
            Assert.Ignore("This host has no unused drive letter for a stable DRIVE_NO_ROOT_DIR test.");
            return;
        }

        string path = $"{unusedDriveLetter}:\\baxy-security-test\\payload.key";
        ProtectedPayloadException? exception = Assert.Throws<ProtectedPayloadException>(
            () => new WindowsProtectedPayload(path));

        Assert.That(exception!.ErrorCode,
            Is.EqualTo(ProtectedPayloadErrorCode.InvalidKeyStorePath));
    }

    [Test]
    public void ProtectedPayloadDoesNotPersistPlaintextInEnvelopeOrKeySidecar()
    {
        using TemporaryDirectory temporary = new();
        string keyPath = Path.Combine(temporary.Path, "payload.key");
        var protector = new WindowsProtectedPayload(keyPath);
        byte[] plaintext = Encoding.UTF8.GetBytes(
            "BAXY-SECRET-MARKER-7F8E9D0C-private-memory-content");

        byte[] envelope = protector.Seal(plaintext, Purpose);
        byte[] keyFile = File.ReadAllBytes(keyPath);

        Assert.Multiple(() =>
        {
            Assert.That(ContainsSequence(envelope, plaintext), Is.False);
            Assert.That(ContainsSequence(keyFile, plaintext), Is.False);
            Assert.That(Encoding.UTF8.GetString(envelope), Does.Not.Contain("private-memory-content"));
            Assert.That(Encoding.UTF8.GetString(keyFile), Does.Not.Contain("private-memory-content"));
        });
    }

    [TestCase(@"relative\payload.key")]
    [TestCase(@"\\server\share\payload.key")]
    [TestCase(@"\\?\C:\baxy\payload.key")]
    [TestCase(@"\\.\C:\baxy\payload.key")]
    public void ProtectedPayloadRejectsNonLocalOrNonAbsolutePaths(string unsafePath)
    {
        ProtectedPayloadException? exception = Assert.Throws<ProtectedPayloadException>(
            () => new WindowsProtectedPayload(unsafePath));

        Assert.That(exception!.ErrorCode,
            Is.EqualTo(ProtectedPayloadErrorCode.InvalidKeyStorePath));
    }

    [Test]
    public void ProtectedPayloadRejectsAlternateDataStreamPath()
    {
        using TemporaryDirectory temporary = new();
        string unsafePath = Path.Combine(temporary.Path, "payload.key") + ":hidden";

        ProtectedPayloadException? exception = Assert.Throws<ProtectedPayloadException>(
            () => new WindowsProtectedPayload(unsafePath));

        Assert.That(exception!.ErrorCode,
            Is.EqualTo(ProtectedPayloadErrorCode.InvalidKeyStorePath));
    }

    [TestCase("NUL")]
    [TestCase("COM1.key")]
    [TestCase("payload.key.")]
    [TestCase("payload.key ")]
    public void ProtectedPayloadRejectsDosDeviceAndAliasedFileNames(string unsafeFileName)
    {
        using TemporaryDirectory temporary = new();
        string unsafePath = Path.Combine(temporary.Path, unsafeFileName);

        ProtectedPayloadException? exception = Assert.Throws<ProtectedPayloadException>(
            () => new WindowsProtectedPayload(unsafePath));

        Assert.That(exception!.ErrorCode,
            Is.EqualTo(ProtectedPayloadErrorCode.InvalidKeyStorePath));
    }

    [Test]
    public void ProtectedPayloadRejectsExistingReparsePoint()
    {
        using TemporaryDirectory temporary = new();
        string target = Path.Combine(temporary.Path, "target");
        string link = Path.Combine(temporary.Path, "link");
        Directory.CreateDirectory(target);
        _ = Baxy.Tests.NtfsTestJunction.Create(link, target);

        try
        {
            ProtectedPayloadException? protectedPayloadException =
                Assert.Throws<ProtectedPayloadException>(
                    () => new WindowsProtectedPayload(Path.Combine(link, "payload.key")));

            Assert.That(protectedPayloadException!.ErrorCode,
                Is.EqualTo(ProtectedPayloadErrorCode.InvalidKeyStorePath));
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
    public void ProtectedPayloadRejectsAHardLinkedKeySidecar()
    {
        using TemporaryDirectory temporary = new();
        string keyPath = Path.Combine(temporary.Path, "payload.key");
        var protector = new WindowsProtectedPayload(keyPath);
        byte[] envelope = protector.SealUtf8("dato", Purpose);
        string hardLink = Path.Combine(temporary.Path, "payload-copy.key");
        if (!WindowsPathAttackTestSupport.TryCreateHardLink(hardLink, keyPath))
        {
            Assert.Ignore("This volume does not permit creating a hard link for the test.");
            return;
        }

        ProtectedPayloadException? exception = Assert.Throws<ProtectedPayloadException>(
            () => new WindowsProtectedPayload(keyPath).OpenUtf8(envelope, Purpose));

        Assert.That(exception!.ErrorCode,
            Is.EqualTo(ProtectedPayloadErrorCode.KeyStoreUnavailable));
    }

    [Test]
    public void ExclusiveCandidateHandleBlocksDirectorySwapBeforePublication()
    {
        using TemporaryDirectory temporary = new();
        string guarded = Path.Combine(temporary.Path, "guarded");
        string moved = Path.Combine(temporary.Path, "moved");
        Directory.CreateDirectory(guarded);
        string temporaryPath = Path.Combine(guarded, "candidate.tmp");
        using (WindowsPrivateFileLease candidate = WindowsPrivateStorage.CreateFile(temporaryPath))
        {
            candidate.Stream.Write("PRIVATE-CANARY"u8);
            candidate.Stream.Flush(flushToDisk: true);
            Assert.That(
                () => Directory.Move(guarded, moved),
                Throws.TypeOf<IOException>());
            Assert.That(
                WindowsPrivateStorage.Rename(candidate, "published.bin", replace: false),
                Is.True);
        }

        Assert.Multiple(() =>
        {
            Assert.That(File.Exists(Path.Combine(guarded, "published.bin")), Is.True);
            Assert.That(Directory.Exists(moved), Is.False);
        });
    }

    [Test]
    public void ProtectedPayloadRejectsAuthenticatedBytesThatAreNotUtf8()
    {
        using TemporaryDirectory temporary = new();
        var protector = CreateProtector(temporary);
        byte[] envelope = protector.Seal(new byte[] { 0xC3, 0x28 }, Purpose);

        ProtectedPayloadException? exception = Assert.Throws<ProtectedPayloadException>(
            () => protector.OpenUtf8(envelope, Purpose));

        Assert.That(exception!.ErrorCode, Is.EqualTo(ProtectedPayloadErrorCode.InvalidEnvelope));
    }

    private static WindowsProtectedPayload CreateProtector(TemporaryDirectory temporary) =>
        new(Path.Combine(temporary.Path, "payload.key"));

    private static WindowsProtectedPayload CreateProtectorWithoutKey(TemporaryDirectory temporary) =>
        new(Path.Combine(temporary.Path, "other", "payload.key"));

    private static bool ContainsSequence(ReadOnlySpan<byte> haystack, ReadOnlySpan<byte> needle)
    {
        if (needle.IsEmpty || needle.Length > haystack.Length)
        {
            return false;
        }

        for (int index = 0; index <= haystack.Length - needle.Length; index++)
        {
            if (haystack.Slice(index, needle.Length).SequenceEqual(needle))
            {
                return true;
            }
        }

        return false;
    }

    private sealed class TemporaryDirectory : IDisposable
    {
        public TemporaryDirectory()
        {
            Path = System.IO.Path.Combine(
                System.IO.Path.GetTempPath(),
                $"baxy-protected-payload-{Guid.NewGuid():N}");
            Directory.CreateDirectory(Path);
        }

        public string Path { get; }

        public void Dispose()
        {
            if (Directory.Exists(Path))
            {
                Directory.Delete(Path, recursive: true);
            }
        }
    }
}
