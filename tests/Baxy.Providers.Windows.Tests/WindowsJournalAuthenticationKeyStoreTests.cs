using System.Security.Cryptography;
using Baxy.Security.Windows;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

[TestFixture]
[NonParallelizable]
public sealed class WindowsJournalAuthenticationKeyStoreTests
{
    [Test]
    public void DpapiWrappedKeyRoundTripsAndMissingOrTamperedStateFailsClosed()
    {
        if (!OperatingSystem.IsWindows())
        {
            Assert.Ignore("DPAPI CurrentUser is a Windows-only boundary.");
        }

        using TemporaryDirectory temporary = new();
        var protector = new WindowsProtectedPayload(
            Path.Combine(temporary.Path, "private-payload.v1.key"));
        string journalKeyPath = Path.Combine(temporary.Path, "journal-hmac.v2.key");
        var store = new WindowsJournalAuthenticationKeyStore(journalKeyPath, protector);
        byte[] first = store.LoadOrCreate(allowCreate: true);
        byte[] second = store.LoadOrCreate(allowCreate: false);
        byte[] atRest = File.ReadAllBytes(journalKeyPath);
        try
        {
            Assert.Multiple(() =>
            {
                Assert.That(first, Has.Length.EqualTo(WindowsJournalAuthenticationKeyStore.KeyLength));
                Assert.That(second, Is.EqualTo(first));
                Assert.That(atRest.AsSpan().IndexOf(first), Is.EqualTo(-1));
            });

            atRest[atRest.Length / 2] ^= 0x5A;
            File.WriteAllBytes(journalKeyPath, atRest);
            Assert.That(
                () => store.LoadOrCreate(allowCreate: false),
                Throws.TypeOf<ProtectedPayloadException>());

            File.Delete(journalKeyPath);
            Assert.That(
                () => store.LoadOrCreate(allowCreate: false),
                Throws.TypeOf<ProtectedPayloadException>());
            Assert.That(File.Exists(journalKeyPath), Is.False);
        }
        finally
        {
            CryptographicOperations.ZeroMemory(first);
            CryptographicOperations.ZeroMemory(second);
            CryptographicOperations.ZeroMemory(atRest);
        }
    }

    private sealed class TemporaryDirectory : IDisposable
    {
        public TemporaryDirectory()
        {
            Path = System.IO.Path.Combine(
                System.IO.Path.GetTempPath(),
                $"baxy-journal-key-tests-{Guid.NewGuid():N}");
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
