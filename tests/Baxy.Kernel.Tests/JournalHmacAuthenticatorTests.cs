using System.Security.Cryptography;
using System.Text;
using Baxy.Kernel.Journal;
using NUnit.Framework;

namespace Baxy.Kernel.Tests;

/// <summary>
/// The key that seals every record of the invocation journal (calidad del PC, 2026-10-25: nobody pinned it directly).
/// A tag is HMAC-SHA256 over the domain, a zero byte and the canonical payload: changing that layout would make every
/// journal already on disk read as tampered, and a domain that could hold the separator would let one record's tag
/// stand for another's.
/// </summary>
[TestFixture]
public sealed class JournalHmacAuthenticatorTests
{
    [TestCase(0)]
    [TestCase(16)]
    [TestCase(31)]
    [TestCase(33)]
    [TestCase(64)]
    public void Only_a_256_bit_key_is_accepted(int length) =>
        Assert.That(() => new JournalHmacAuthenticator(new byte[length]), Throws.ArgumentException);

    [Test]
    public void A_tag_is_hmac_sha256_over_the_domain_a_zero_byte_and_the_payload()
    {
        byte[] key = RandomNumberGenerator.GetBytes(JournalHmacAuthenticator.KeyLength);
        byte[] payload = Encoding.UTF8.GetBytes("{\"invocationId\":\"x\"}");
        using var authenticator = new JournalHmacAuthenticator(key);

        byte[] material = [.. Encoding.ASCII.GetBytes("journal.record.v1"), 0, .. payload];
        string expected = Convert.ToHexStringLower(HMACSHA256.HashData(key, material));

        Assert.Multiple(() =>
        {
            Assert.That(authenticator.ComputeTag("journal.record.v1", payload), Is.EqualTo(expected));
            Assert.That(expected, Does.Match("^[0-9a-f]{64}$"));
            Assert.That(JournalHmacAuthenticator.Algorithm, Is.EqualTo("hmac-sha256"));
        });
    }

    [Test]
    public void The_same_payload_under_another_domain_or_key_has_another_tag()
    {
        byte[] key = RandomNumberGenerator.GetBytes(JournalHmacAuthenticator.KeyLength);
        byte[] payload = Encoding.UTF8.GetBytes("bx");
        using var authenticator = new JournalHmacAuthenticator(key);
        using var other = new JournalHmacAuthenticator(RandomNumberGenerator.GetBytes(JournalHmacAuthenticator.KeyLength));

        string tag = authenticator.ComputeTag("a", payload);
        Assert.Multiple(() =>
        {
            Assert.That(authenticator.ComputeTag("a", payload), Is.EqualTo(tag));
            Assert.That(authenticator.ComputeTag("b", payload), Is.Not.EqualTo(tag));
            // The separator keeps the boundary: «ab» + «x» is not «a» + «bx».
            Assert.That(authenticator.ComputeTag("ab", Encoding.UTF8.GetBytes("x")), Is.Not.EqualTo(tag));
            Assert.That(other.ComputeTag("a", payload), Is.Not.EqualTo(tag));
            Assert.That(authenticator.ComputeTag("a", Encoding.UTF8.GetBytes("by")), Is.Not.EqualTo(tag));
        });
    }

    [TestCase("")]
    [TestCase("Journal")]
    [TestCase("journal record")]
    [TestCase("journal-record")]
    [TestCase("journal\0record")]
    [TestCase("diario.ñ")]
    public void A_domain_outside_lower_case_digits_and_dots_is_refused(string domain)
    {
        using var authenticator = new JournalHmacAuthenticator(new byte[JournalHmacAuthenticator.KeyLength]);
        Assert.That(() => authenticator.ComputeTag(domain, [1, 2, 3]), Throws.ArgumentException);
    }

    [Test]
    public void The_authenticator_keeps_its_own_copy_of_the_key()
    {
        byte[] key = RandomNumberGenerator.GetBytes(JournalHmacAuthenticator.KeyLength);
        byte[] original = [.. key];
        using var authenticator = new JournalHmacAuthenticator(key);
        string before = authenticator.ComputeTag("journal.v1", [7]);

        // The caller erases its source buffer after construction, as the class asks.
        CryptographicOperations.ZeroMemory(key);

        Assert.Multiple(() =>
        {
            Assert.That(authenticator.ComputeTag("journal.v1", [7]), Is.EqualTo(before));
            Assert.That(before, Is.EqualTo(Convert.ToHexStringLower(HMACSHA256.HashData(original, (byte[])[.. "journal.v1"u8, 0, 7]))));
        });
    }

    [Test]
    public void A_disposed_authenticator_tags_nothing_and_a_clone_taken_before_outlives_it()
    {
        var authenticator = new JournalHmacAuthenticator(RandomNumberGenerator.GetBytes(JournalHmacAuthenticator.KeyLength));
        string tag = authenticator.ComputeTag("journal.v1", [1]);
        using JournalHmacAuthenticator clone = authenticator.Clone();

        authenticator.Dispose();
        authenticator.Dispose();

        Assert.Multiple(() =>
        {
            Assert.That(() => authenticator.ComputeTag("journal.v1", [1]), Throws.TypeOf<ObjectDisposedException>());
            Assert.That(() => authenticator.Clone(), Throws.TypeOf<ObjectDisposedException>());
            Assert.That(clone.ComputeTag("journal.v1", [1]), Is.EqualTo(tag));
        });
    }
}
