using System.Globalization;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Contracts;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// The kernel's challenge as the App takes it (src/Baxy.App/ConfirmationChallengeParser.cs): a token for the exact
/// invocation the App sent, live and within the contract's lifetime; anything else is no challenge, and nothing waits
/// for the person's «sí» (invariant 4). Auditoría de la App (2026-10-23): it had no test of its own.
/// </summary>
[TestFixture]
public sealed class ConfirmationChallengeParserTests
{
    private static readonly DateTimeOffset Now = new(2026, 10, 23, 12, 0, 0, TimeSpan.Zero);

    // 32 bytes, base64url without padding: 43 characters.
    private static readonly string Token = Convert.ToBase64String(Enumerable.Range(1, 32).Select(static b => (byte)b).ToArray())
        .TrimEnd('=').Replace('+', '-').Replace('/', '_');

    [Test]
    public void AChallengeForTheExactInvocationIsTaken()
    {
        PreparedOperation prepared = Prepared();

        Assert.That(ConfirmationChallengeParser.TryParse(Challenge(prepared), prepared, new Clock(),
            out ValidatedConfirmationChallenge challenge), Is.True);
        Assert.Multiple(() =>
        {
            Assert.That(challenge.Token, Is.EqualTo(Token));
            Assert.That(challenge.ExpiresAtUtc, Is.EqualTo(Now.AddSeconds(60)));
            Assert.That(challenge.ReconciliationRequired, Is.False);
        });
    }

    [Test]
    public void AChallengeForAnotherInvocationOrMissionIsNone()
    {
        PreparedOperation prepared = Prepared();
        PreparedOperation other = Prepared();

        Assert.Multiple(() =>
        {
            Assert.That(ConfirmationChallengeParser.TryParse(Challenge(other), prepared, new Clock(), out _), Is.False);
            Assert.That(ConfirmationChallengeParser.TryParse(
                Challenge(prepared) with { MissionId = other.MissionId }, prepared, new Clock(), out _), Is.False);
        });
    }

    [Test]
    public void AReplayedVerifiedOrOtherwiseCodedResponseIsNoChallenge()
    {
        PreparedOperation prepared = Prepared();
        OperationResponse challenge = Challenge(prepared);

        Assert.Multiple(() =>
        {
            Assert.That(ConfirmationChallengeParser.TryParse(challenge with { Replayed = true }, prepared, new Clock(), out _),
                Is.False);
            Assert.That(ConfirmationChallengeParser.TryParse(challenge with { Verified = true }, prepared, new Clock(), out _),
                Is.False);
            Assert.That(ConfirmationChallengeParser.TryParse(challenge with { ErrorCode = "provider_busy" }, prepared,
                new Clock(), out _), Is.False);
            Assert.That(ConfirmationChallengeParser.TryParse(challenge with { Status = OperationStatuses.Completed },
                prepared, new Clock(), out _), Is.False);
        });
    }

    [TestCase(0)]
    [TestCase(-5)]
    [TestCase(ConfirmationChallengeContract.MaximumLifetimeSeconds + 1)]
    public void ATokenAlreadyDeadOrLivingPastTheContractIsNone(int seconds)
    {
        PreparedOperation prepared = Prepared();

        Assert.That(ConfirmationChallengeParser.TryParse(Challenge(prepared, expiresIn: seconds), prepared, new Clock(),
            out _), Is.False);
    }

    [TestCase("short")]
    [TestCase("AQIDBAUGBwgJCgsMDQ4PEBESExQVFhcYGRobHB0eHyA=")]
    [TestCase("AQIDBAUGBwgJCgsMDQ4PEBESExQVFhcYGRobHB0eH+A")]
    public void AMalformedTokenIsNone(string token)
    {
        PreparedOperation prepared = Prepared();

        Assert.That(ConfirmationChallengeParser.TryParse(Challenge(prepared, token: token), prepared, new Clock(), out _),
            Is.False);
    }

    [Test]
    public void AResultWithAnExtraFieldIsNone()
    {
        PreparedOperation prepared = Prepared();
        JsonObject result = Result(Token, 60);
        result["approved"] = true;

        Assert.That(ConfirmationChallengeParser.TryParse(Challenge(prepared) with { Result = Element(result) }, prepared,
            new Clock(), out _), Is.False);
    }

    private static PreparedOperation Prepared() =>
        PreparedOperation.Create("app.close", new JsonObject { ["appId"] = "Calculadora" });

    private static OperationResponse Challenge(PreparedOperation prepared, int expiresIn = 60, string? token = null) =>
        new(ProtocolTypes.OperationResponse, Guid.NewGuid().ToString("D"), prepared.MissionId, prepared.InvocationId,
            OperationStatuses.Pending, "{\"status\":\"pending\"}", Verified: false, Replayed: false,
            Element(Result(token ?? Token, expiresIn)), ConfirmationChallengeContract.RequiredErrorCode);

    private static JsonObject Result(string token, int expiresIn) => new()
    {
        ["version"] = ConfirmationChallengeContract.CurrentVersion,
        ["token"] = token,
        ["expiresAtUtc"] = Now.AddSeconds(expiresIn).ToString("O", CultureInfo.InvariantCulture),
        ["reconciliationRequired"] = false,
    };

    private static JsonElement Element(JsonObject value) => JsonDocument.Parse(value.ToJsonString()).RootElement.Clone();

    private sealed class Clock : TimeProvider
    {
        public override DateTimeOffset GetUtcNow() => Now;
    }
}
