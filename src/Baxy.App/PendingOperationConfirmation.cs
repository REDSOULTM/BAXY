using System.Text.Json;
using Baxy.Contracts;

namespace Baxy.App;

/// <summary>A call the kernel challenged: the exact invocation, its token and when the token expires.</summary>
internal sealed class PendingOperationConfirmation
{
    private PendingOperationConfirmation(
        PreparedOperation prepared,
        string token,
        DateTimeOffset expiresAtUtc,
        bool reconciliationRequired)
    {
        Prepared = prepared;
        Token = token;
        ExpiresAtUtc = expiresAtUtc;
        ReconciliationRequired = reconciliationRequired;
    }

    internal PreparedOperation Prepared { get; }

    internal string Token { get; }

    internal DateTimeOffset ExpiresAtUtc { get; }

    internal bool ReconciliationRequired { get; }

    /// <summary>Encargo 83: what the kernel's read found of the call it challenged; null when it found nothing to say.</summary>
    internal JsonElement? Facts { get; private init; }

    internal const string SystemChangeCause = "system_change";

    /// <summary>Encargo 83: the setting of Windows this call would change, when that is why the kernel asks.</summary>
    internal JsonElement? SystemChange =>
        Facts is { } facts && facts.TryGetProperty("systemChange", out JsonElement change) ? change : null;

    /// <summary>
    /// Whether the person's «sí» to a heartbeat's proposal also answers this challenge: the same invocation, not one that
    /// may have run already (C16). That one (<see cref="ReconciliationRequired"/>) asks the person as such: their «sí» came
    /// before the kernel said its earlier run may have acted, and the kernel's yes is for one run only.
    /// </summary>
    internal bool AnsweredByProposal(PreparedOperation proposal) =>
        ReferenceEquals(Prepared, proposal) && !ReconciliationRequired;

    internal static bool TryCreate(
        OperationResponse response,
        PreparedOperation prepared,
        TimeProvider timeProvider,
        out PendingOperationConfirmation? confirmation)
    {
        ArgumentNullException.ThrowIfNull(response);
        ArgumentNullException.ThrowIfNull(prepared);
        ArgumentNullException.ThrowIfNull(timeProvider);
        confirmation = null;
        if (!ConfirmationChallengeParser.TryParse(
                response,
                prepared,
                timeProvider,
                out ValidatedConfirmationChallenge challenge))
        {
            return false;
        }

        confirmation = new PendingOperationConfirmation(
            prepared,
            challenge.Token,
            challenge.ExpiresAtUtc,
            challenge.ReconciliationRequired)
        {
            Facts = challenge.Facts,
        };
        return true;
    }

    public override string ToString() =>
        $"{nameof(PendingOperationConfirmation)} {{ Operation = {Prepared.OperationName}, "
        + $"Token = [REDACTED], ExpiresAtUtc = {ExpiresAtUtc:O}, "
        + $"ReconciliationRequired = {ReconciliationRequired} }}";
}
