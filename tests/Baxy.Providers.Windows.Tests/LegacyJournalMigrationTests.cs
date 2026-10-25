using System.Security.Cryptography;
using System.Text;
using Baxy.Core;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// The core's first step on the journal (calidad del PC, 2026-10-25: nobody tested it). An unkeyed v1 journal, with no
/// anchor and no key beside it, is moved aside under its digest so a keyed journal can start; anything else is left
/// where it was, and the core then refuses to create a key over it (Program.OpenJournalAsync: a fresh key is allowed
/// only after a migration, with no journal or with an empty one). A file that only resembles a v1 journal must never be
/// moved, or deleting the key would buy a fresh one over a journal that was tampered with.
/// </summary>
[TestFixture]
public sealed class LegacyJournalMigrationTests
{
    private static readonly string Hash = new('a', 64);

    private static string Record(string payload = "{\"invocationId\":\"x\"}", string? previous = null, string? hash = null) =>
        $"{{\"payload\":{payload},\"previousHash\":\"{previous ?? Hash}\",\"hash\":\"{hash ?? new string('b', 64)}\"}}";

    [TestCase("\n")]
    [TestCase("")]
    public void An_unkeyed_v1_journal_is_moved_aside_under_its_digest(string ending)
    {
        using var folder = new Folder();
        byte[] content = Encoding.UTF8.GetBytes(Record() + "\n" + Record(previous: new string('b', 64)) + ending);
        File.WriteAllBytes(folder.Journal, content);

        LegacyJournalMigrationResult result = Migrate(folder);

        string digest = Convert.ToHexStringLower(SHA256.HashData(content));
        Assert.Multiple(() =>
        {
            Assert.That(result.Migrated, Is.True);
            Assert.That(result.Sha256, Is.EqualTo(digest));
            Assert.That(result.Length, Is.EqualTo(content.LongLength));
            Assert.That(File.Exists(folder.Journal), Is.False);
            Assert.That(result.ArchivePath, Is.Not.Null);
            Assert.That(Path.GetDirectoryName(result.ArchivePath), Is.EqualTo(folder.Path));
            Assert.That(Path.GetFileName(result.ArchivePath),
                Does.Match($"^missions\\.legacy-v1-untrusted\\.{digest}\\.[0-9a-f]{{32}}\\.jsonl$"));
            Assert.That(File.ReadAllBytes(result.ArchivePath!), Is.EqualTo(content));
        });
    }

    [Test]
    public void A_journal_beside_its_anchor_or_its_key_is_not_touched()
    {
        using var folder = new Folder();
        byte[] content = Encoding.UTF8.GetBytes(Record() + "\n");
        File.WriteAllBytes(folder.Journal, content);

        File.WriteAllText(folder.Anchor, "anchor");
        LegacyJournalMigrationResult anchored = Migrate(folder);
        File.Delete(folder.Anchor);
        File.WriteAllText(folder.Key, "key");
        LegacyJournalMigrationResult keyed = Migrate(folder);

        Assert.Multiple(() =>
        {
            Assert.That(anchored.Migrated, Is.False);
            Assert.That(keyed.Migrated, Is.False);
            Assert.That(File.ReadAllBytes(folder.Journal), Is.EqualTo(content));
            Assert.That(Directory.GetFiles(folder.Path), Has.Length.EqualTo(2));
        });
    }

    [Test]
    public void No_journal_or_an_empty_one_is_not_a_migration()
    {
        using var folder = new Folder();
        LegacyJournalMigrationResult missing = Migrate(folder);
        File.WriteAllBytes(folder.Journal, []);
        LegacyJournalMigrationResult empty = Migrate(folder);

        Assert.Multiple(() =>
        {
            Assert.That(missing, Is.EqualTo(new LegacyJournalMigrationResult(false, null, null, 0)));
            Assert.That(empty, Is.EqualTo(new LegacyJournalMigrationResult(false, null, null, 0)));
            Assert.That(File.Exists(folder.Journal), Is.True);
        });
    }

    // What only resembles a v1 journal: a fourth property, a hash in upper case or of another length, a payload that is
    // not an object, a blank line between records or at the start, a trailing line that is not JSON, a JSON array.
    [TestCase("{\"payload\":{},\"previousHash\":\"" + "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" + "\",\"hash\":\"" + "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb" + "\",\"tag\":\"x\"}\n")]
    [TestCase("{\"payload\":{},\"previousHash\":\"" + "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA" + "\",\"hash\":\"" + "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb" + "\"}\n")]
    [TestCase("{\"payload\":{},\"previousHash\":\"aaaa\",\"hash\":\"" + "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb" + "\"}\n")]
    [TestCase("{\"payload\":\"x\",\"previousHash\":\"" + "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" + "\",\"hash\":\"" + "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb" + "\"}\n")]
    [TestCase("{\"payload\":{},\"previousHash\":\"" + "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" + "\",\"hash\":\"" + "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb" + "\"}\n\n")]
    [TestCase("\n{\"payload\":{},\"previousHash\":\"" + "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" + "\",\"hash\":\"" + "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb" + "\"}\n")]
    [TestCase("{\"payload\":{},\"previousHash\":\"" + "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" + "\",\"hash\":\"" + "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb" + "\"}\nnot json\n")]
    [TestCase("[1,2,3]\n")]
    [TestCase("\n")]
    public void What_only_resembles_a_v1_journal_stays_where_it_was(string text)
    {
        using var folder = new Folder();
        byte[] content = Encoding.UTF8.GetBytes(text);
        File.WriteAllBytes(folder.Journal, content);

        LegacyJournalMigrationResult result = Migrate(folder);

        Assert.Multiple(() =>
        {
            Assert.That(result.Migrated, Is.False);
            Assert.That(result.ArchivePath, Is.Null);
            Assert.That(result.Length, Is.EqualTo(content.LongLength));
            Assert.That(File.ReadAllBytes(folder.Journal), Is.EqualTo(content));
            Assert.That(Directory.GetFiles(folder.Path), Has.Length.EqualTo(1));
        });
    }

    private static LegacyJournalMigrationResult Migrate(Folder folder) =>
        LegacyJournalMigration.PreserveUnkeyedV1(folder.Journal, folder.Anchor, folder.Key);

    private sealed class Folder : IDisposable
    {
        internal Folder()
        {
            Path = System.IO.Path.Combine(System.IO.Path.GetTempPath(), $"baxy-legacy-journal-{Guid.NewGuid():N}");
            Directory.CreateDirectory(Path);
        }

        internal string Path { get; }

        internal string Journal => System.IO.Path.Combine(Path, "missions.jsonl");

        internal string Anchor => Journal + ".anchor";

        internal string Key => System.IO.Path.Combine(Path, "journal-hmac.v2.key");

        public void Dispose()
        {
            try
            {
                Directory.Delete(Path, recursive: true);
            }
            catch (IOException)
            {
            }
        }
    }
}
