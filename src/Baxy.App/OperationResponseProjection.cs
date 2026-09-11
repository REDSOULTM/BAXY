using System.Text.Json;
using Baxy.Contracts;
using Baxy.Kernel.Operations;

namespace Baxy.App;

internal sealed record OperationResponseProjection(string Message)
{
    private const int MaximumMessageLength = 16_384;

    public static OperationResponseProjection Create(OperationResponse response, string operationName)
    {
        ArgumentNullException.ThrowIfNull(response);
        ArgumentException.ThrowIfNullOrWhiteSpace(operationName);
        if (response.HonestyCorrection is { } honesty
            && !string.IsNullOrWhiteSpace(honesty.Correction))
        {
            return new OperationResponseProjection(TruncateMessage(honesty.Correction.Trim()));
        }

        if (!string.IsNullOrWhiteSpace(response.Message))
        {
            // The process catalog allows fifty verified rows. Keep its bounded
            // structured facts whole; cutting JSON makes every observation vanish.
            return new OperationResponseProjection(TruncateMessage(response.Message.Trim(),
                maximumLength: operationName == "system.process.list" ? 48_000 : MaximumMessageLength));
        }

        return new OperationResponseProjection(
            TruncateMessage(
                OperationVisibleFacts.FromStatus(
                    operationName,
                    response.Status,
                    response.ErrorCode)));
    }

    private static string TruncateMessage(
        string value,
        string suffix = "… [respuesta truncada]",
        int maximumLength = MaximumMessageLength)
    {
        if (value.Length <= maximumLength)
        {
            return value;
        }

        int keep = Math.Max(0, maximumLength - suffix.Length);
        if (keep > 0
            && keep < value.Length
            && char.IsHighSurrogate(value[keep - 1])
            && char.IsLowSurrogate(value[keep]))
        {
            keep--;
        }

        return string.Concat(value.AsSpan(0, keep), suffix);
    }
}
