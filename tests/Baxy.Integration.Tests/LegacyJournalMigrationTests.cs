using System.Security.Cryptography;
using System.Text;
using Baxy.Core;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class LegacyJournalMigrationTests
{
    [Test]
    public void PreservesRecognizedV1BytesAndRemovesOnlyTheLegacyActiveName()
    {
        string root = PrivateDataRootTestSupport.NewPath("legacy-journal-migration");
        string journalDirectory = Path.Combine(root, "journal");
        Directory.CreateDirectory(journalDirectory);
        string journalPath = Path.Combine(journalDirectory, "missions.jsonl");
        byte[] original = Encoding.UTF8.GetBytes(V1Record + "\n");
        File.WriteAllBytes(journalPath, original);

        LegacyJournalMigrationResult result = LegacyJournalMigration.PreserveUnkeyedV1(
            journalPath,
            string.Concat(journalPath, ".anchor"),
            Path.Combine(root, "security", "journal-hmac.v2.key"));

        Assert.Multiple(() =>
        {
            Assert.That(result.Migrated, Is.True);
            Assert.That(result.ArchivePath, Is.Not.Null);
            Assert.That(File.Exists(journalPath), Is.False);
            Assert.That(File.Exists(result.ArchivePath!), Is.True);
            Assert.That(File.ReadAllBytes(result.ArchivePath!), Is.EqualTo(original));
            Assert.That(result.Length, Is.EqualTo(original.LongLength));
            Assert.That(
                result.Sha256,
                Is.EqualTo(Convert.ToHexStringLower(SHA256.HashData(original))));
        });
    }

    [TestCase("anchor")]
    [TestCase("key")]
    public void ExistingAuthenticatedStateNeverEntersLegacyMigration(string state)
    {
        string root = PrivateDataRootTestSupport.NewPath("legacy-journal-authenticated-state");
        string journalDirectory = Path.Combine(root, "journal");
        Directory.CreateDirectory(journalDirectory);
        string journalPath = Path.Combine(journalDirectory, "missions.jsonl");
        File.WriteAllText(journalPath, V1Record + "\n", Encoding.UTF8);
        string anchorPath = string.Concat(journalPath, ".anchor");
        string keyPath = Path.Combine(root, "security", "journal-hmac.v2.key");
        string existingPath = state == "anchor" ? anchorPath : keyPath;
        Directory.CreateDirectory(Path.GetDirectoryName(existingPath)!);
        File.WriteAllText(existingPath, "existing", Encoding.UTF8);

        LegacyJournalMigrationResult result = LegacyJournalMigration.PreserveUnkeyedV1(
            journalPath,
            anchorPath,
            keyPath);

        Assert.Multiple(() =>
        {
            Assert.That(result.Migrated, Is.False);
            Assert.That(File.Exists(journalPath), Is.True);
            Assert.That(
                Directory.GetFiles(journalDirectory, "*.legacy-v1-untrusted.*"),
                Is.Empty);
        });
    }

    [TestCase("not-json")]
    [TestCase("{\"version\":2,\"authentication\":\"hmac-sha256\",\"payload\":{},\"previousTag\":\"00\",\"tag\":\"00\"}")]
    public void UnknownOrAuthenticatedJournalWithoutKeyFailsClosed(string content)
    {
        string root = PrivateDataRootTestSupport.NewPath("legacy-journal-unknown");
        string journalDirectory = Path.Combine(root, "journal");
        Directory.CreateDirectory(journalDirectory);
        string journalPath = Path.Combine(journalDirectory, "missions.jsonl");
        File.WriteAllText(journalPath, content + "\n", Encoding.UTF8);

        LegacyJournalMigrationResult result = LegacyJournalMigration.PreserveUnkeyedV1(
            journalPath,
            string.Concat(journalPath, ".anchor"),
            Path.Combine(root, "security", "journal-hmac.v2.key"));

        Assert.Multiple(() =>
        {
            Assert.That(result.Migrated, Is.False);
            Assert.That(File.Exists(journalPath), Is.True);
            Assert.That(
                Directory.GetFiles(journalDirectory, "*.legacy-v1-untrusted.*"),
                Is.Empty);
        });
    }

    private const string V1Record =
        "{\"payload\":{\"sequence\":1},\"previousHash\":\"0000000000000000000000000000000000000000000000000000000000000000\",\"hash\":\"1111111111111111111111111111111111111111111111111111111111111111\"}";
}
