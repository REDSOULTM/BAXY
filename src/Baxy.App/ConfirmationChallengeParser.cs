using System.Globalization;
using System.Security.Cryptography;
using System.Text.Json;
using Baxy.Contracts;

namespace Baxy.App;

internal readonly record struct ValidatedConfirmationChallenge(
    string Token,
    DateTimeOffset ExpiresAtUtc,
    bool ReconciliationRequired);

internal static class ConfirmationChallengeParser
{
    private static readonly TimeSpan MaximumLifetime =
        TimeSpan.FromSeconds(ConfirmationChallengeContract.MaximumLifetimeSeconds);

    internal static bool TryParse(
        OperationResponse response,
        PreparedOperation prepared,
        TimeProvider timeProvider,
        out ValidatedConfirmationChallenge challenge)
    {
        ArgumentNullException.ThrowIfNull(response);
        ArgumentNullException.ThrowIfNull(prepared);
        ArgumentNullException.ThrowIfNull(timeProvider);
        challenge = default;
        if (response.Status != OperationStatuses.Pending
            || !string.Equals(
                response.ErrorCode,
                ConfirmationChallengeContract.RequiredErrorCode,
                StringComparison.Ordinal)
            || response.Verified
            || response.Replayed
            || !string.Equals(response.MissionId, prepared.MissionId, StringComparison.Ordinal)
            || !string.Equals(response.InvocationId, prepared.InvocationId, StringComparison.Ordinal)
            || response.Result is not { ValueKind: JsonValueKind.Object } result
            || !HasExactProperties(
                result,
                ["version", "token", "expiresAtUtc", "reconciliationRequired"])
            || !result.TryGetProperty("version", out JsonElement version)
            || version.ValueKind != JsonValueKind.Number
            || !version.TryGetInt32(out int versionNumber)
            || versionNumber != ConfirmationChallengeContract.CurrentVersion
            || !result.TryGetProperty("token", out JsonElement tokenElement)
            || tokenElement.ValueKind != JsonValueKind.String
            || !TryValidateToken(tokenElement.GetString(), out string? token)
            || !result.TryGetProperty("expiresAtUtc", out JsonElement expiryElement)
            || expiryElement.ValueKind != JsonValueKind.String
            || !DateTimeOffset.TryParseExact(
                expiryElement.GetString(),
                "O",
                CultureInfo.InvariantCulture,
                DateTimeStyles.RoundtripKind,
                out DateTimeOffset expiry)
            || expiry.Offset != TimeSpan.Zero
            || !result.TryGetProperty(
                "reconciliationRequired",
                out JsonElement reconciliationElement)
            || reconciliationElement.ValueKind is not (
                JsonValueKind.True or JsonValueKind.False))
        {
            return false;
        }

        DateTimeOffset now = timeProvider.GetUtcNow().ToUniversalTime();
        if (expiry <= now || expiry > now.Add(MaximumLifetime))
        {
            return false;
        }

        challenge = new ValidatedConfirmationChallenge(
            token!,
            expiry,
            reconciliationElement.GetBoolean());
        return true;
    }

    private static bool TryValidateToken(string? value, out string? canonical)
    {
        canonical = null;
        if (value is null || value.Length != 43 || value.Any(static character =>
                character is not (>= 'A' and <= 'Z')
                and not (>= 'a' and <= 'z')
                and not (>= '0' and <= '9')
                and not '-'
                and not '_'))
        {
            return false;
        }

        byte[] decoded;
        try
        {
            decoded = Convert.FromBase64String(
                (value + "=").Replace('-', '+').Replace('_', '/'));
        }
        catch (FormatException)
        {
            return false;
        }

        try
        {
            string roundTrip = Convert.ToBase64String(decoded)
                .TrimEnd('=')
                .Replace('+', '-')
                .Replace('/', '_');
            if (decoded.Length != 32 || !string.Equals(roundTrip, value, StringComparison.Ordinal))
            {
                return false;
            }

            canonical = value;
            return true;
        }
        finally
        {
            CryptographicOperations.ZeroMemory(decoded);
        }
    }

    private static bool HasExactProperties(JsonElement element, string[] expected)
    {
        var actual = new HashSet<string>(StringComparer.Ordinal);
        foreach (JsonProperty property in element.EnumerateObject())
        {
            if (!actual.Add(property.Name))
            {
                return false;
            }
        }

        return actual.SetEquals(expected);
    }
}
