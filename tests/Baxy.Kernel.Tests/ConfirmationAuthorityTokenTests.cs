using System.Security.Cryptography;
using Baxy.Kernel.Mission;
using NUnit.Framework;

namespace Baxy.Kernel.Tests;

/// <summary>
/// The confirmation authority on its own (calidad del PC, 2026-10-25): what it does with a token that is not the one
/// it issued, with a lifetime out of bounds and once disposed. Whatever the person's client sends back, a token that
/// was not issued for this exact binding never grants, and a malformed one is a fresh challenge, never a failure.
/// </summary>
[TestFixture]
public sealed class ConfirmationAuthorityTokenTests
{
    private static readonly DateTimeOffset InitialTime = new(2026, 10, 25, 12, 0, 0, TimeSpan.Zero);

    [Test]
    public void The_lifetime_is_positive_and_bounded_and_the_capacity_at_least_one()
    {
        Assert.Multiple(() =>
        {
            Assert.That(() => new InMemoryConfirmationAuthority(lifetime: TimeSpan.Zero),
                Throws.TypeOf<ArgumentOutOfRangeException>());
            Assert.That(() => new InMemoryConfirmationAuthority(lifetime: TimeSpan.FromSeconds(-1)),
                Throws.TypeOf<ArgumentOutOfRangeException>());
            Assert.That(
                () => new InMemoryConfirmationAuthority(
                    lifetime: InMemoryConfirmationAuthority.MaximumLifetime + TimeSpan.FromTicks(1)),
                Throws.TypeOf<ArgumentOutOfRangeException>());
            Assert.That(() => new InMemoryConfirmationAuthority(capacity: 0), Throws.TypeOf<ArgumentOutOfRangeException>());
            Assert.That(() => new InMemoryConfirmationAuthority(capacity: -1), Throws.TypeOf<ArgumentOutOfRangeException>());
            Assert.That(
                () => new InMemoryConfirmationAuthority(lifetime: InMemoryConfirmationAuthority.MaximumLifetime).Dispose(),
                Throws.Nothing);
            Assert.That(ConfirmationLifetime.Challenge, Is.EqualTo(InMemoryConfirmationAuthority.DefaultLifetime));
        });
    }

    [TestCase("")]
    [TestCase("a")]
    [TestCase("abcde")]
    [TestCase("!!!!")]
    [TestCase("====")]
    [TestCase("not a token at all")]
    public void A_malformed_token_is_answered_with_the_same_challenge(string presented)
    {
        using var authority = new InMemoryConfirmationAuthority(new FixedTimeProvider(InitialTime));
        ConfirmationBinding binding = Binding();
        string issued = authority.AuthorizeOrIssue(binding, null).Challenge!.Token;

        ConfirmationAuthorization answer = authority.AuthorizeOrIssue(binding, presented);

        Assert.Multiple(() =>
        {
            Assert.That(answer.Status, Is.EqualTo(ConfirmationAuthorizationStatus.ChallengeRequired));
            Assert.That(answer.Challenge!.Token, Is.EqualTo(issued));
            Assert.That(authority.ActiveChallengeCount, Is.EqualTo(1));
        });
    }

    [Test]
    public void Only_the_exact_token_grants_not_a_truncated_or_altered_one()
    {
        using var authority = new InMemoryConfirmationAuthority(new FixedTimeProvider(InitialTime));
        ConfirmationBinding binding = Binding();
        string issued = authority.AuthorizeOrIssue(binding, null).Challenge!.Token;
        char last = issued[^1];
        string[] near =
        [
            issued[..^1],
            issued + "A",
            issued[..^1] + (last == 'A' ? 'B' : 'A'),
            issued.Any(char.IsLower) ? issued.ToUpperInvariant() : issued.ToLowerInvariant(),
            Convert.ToBase64String(RandomNumberGenerator.GetBytes(32)).TrimEnd('=').Replace('+', '-').Replace('/', '_'),
        ];

        Assert.Multiple(() =>
        {
            foreach (string token in near)
            {
                Assert.That(authority.AuthorizeOrIssue(binding, token).Status,
                    Is.EqualTo(ConfirmationAuthorizationStatus.ChallengeRequired), token);
            }

            Assert.That(authority.AuthorizeOrIssue(binding, issued).Status, Is.EqualTo(ConfirmationAuthorizationStatus.Granted));
        });
    }

    [Test]
    public void A_token_issued_by_another_authority_for_the_same_binding_does_not_grant()
    {
        ConfirmationBinding binding = Binding();
        using var first = new InMemoryConfirmationAuthority(new FixedTimeProvider(InitialTime));
        using var restarted = new InMemoryConfirmationAuthority(new FixedTimeProvider(InitialTime));
        string fromBefore = first.AuthorizeOrIssue(binding, null).Challenge!.Token;

        ConfirmationAuthorization answer = restarted.AuthorizeOrIssue(binding, fromBefore);

        Assert.Multiple(() =>
        {
            Assert.That(answer.Status, Is.EqualTo(ConfirmationAuthorizationStatus.ChallengeRequired));
            Assert.That(answer.Challenge!.Token, Is.Not.EqualTo(fromBefore));
            Assert.That(restarted.AuthorizeOrIssue(binding, fromBefore).Status,
                Is.EqualTo(ConfirmationAuthorizationStatus.ChallengeRequired));
        });
    }

    [Test]
    public void A_revoked_challenge_no_longer_grants_and_the_next_one_is_new()
    {
        using var authority = new InMemoryConfirmationAuthority(new FixedTimeProvider(InitialTime));
        ConfirmationBinding binding = Binding();
        string issued = authority.AuthorizeOrIssue(binding, null).Challenge!.Token;

        authority.Revoke(binding);
        authority.Revoke(binding);
        ConfirmationAuthorization answer = authority.AuthorizeOrIssue(binding, issued);

        Assert.Multiple(() =>
        {
            Assert.That(answer.Status, Is.EqualTo(ConfirmationAuthorizationStatus.ChallengeRequired));
            Assert.That(answer.Challenge!.Token, Is.Not.EqualTo(issued));
            Assert.That(authority.ActiveChallengeCount, Is.EqualTo(1));
        });
    }

    [Test]
    public void A_disposed_authority_grants_nothing()
    {
        var authority = new InMemoryConfirmationAuthority(new FixedTimeProvider(InitialTime));
        ConfirmationBinding binding = Binding();
        string issued = authority.AuthorizeOrIssue(binding, null).Challenge!.Token;

        authority.Dispose();
        authority.Dispose();

        Assert.Multiple(() =>
        {
            Assert.That(() => authority.AuthorizeOrIssue(binding, issued), Throws.TypeOf<ObjectDisposedException>());
            Assert.That(() => authority.Revoke(binding), Throws.TypeOf<ObjectDisposedException>());
            Assert.That(() => authority.ActiveChallengeCount, Throws.TypeOf<ObjectDisposedException>());
        });
    }

    private static ConfirmationBinding Binding() =>
        new(Guid.NewGuid().ToString("D"), Guid.NewGuid().ToString("D"), new string('b', 64));

    private sealed class FixedTimeProvider(DateTimeOffset now) : TimeProvider
    {
        public override DateTimeOffset GetUtcNow() => now;
    }
}
