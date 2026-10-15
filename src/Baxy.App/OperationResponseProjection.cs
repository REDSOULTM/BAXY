using System.Text.Json;
using System.Text.Json.Nodes;
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
            // The look's whole view is the receipt's result; the kernel's visible facts keep only its first rows.
            if (operationName == "input.visible.controls"
                && response.Result is { ValueKind: JsonValueKind.Object } look
                && ScreenViewProjection.TryCreate(response.Message, look, out string view))
            {
                return new OperationResponseProjection(view);
            }

            if (operationName == "ocr.read")
            {
                string message = response.Message.Trim();
                if (message.Length <= ProtocolLimits.MaximumOperationResponseMessageChars)
                    return new OperationResponseProjection(message);
                // An omitted observation does not change the executed operation's outcome.
                bool completed = response.Status == OperationStatuses.Completed;
                return new OperationResponseProjection(new JsonObject
                {
                    ["kind"] = "operation",
                    ["operation"] = operationName,
                    ["status"] = response.Status,
                    ["verified"] = response.Verified,
                    ["succeeded"] = completed,
                    ["polarity"] = response.Status == OperationStatuses.Pending ? "pending"
                        : completed && response.Verified ? "success" : "failure",
                    ["error"] = response.ErrorCode,
                    ["effectUncertain"] = response.EffectMayHaveOccurred,
                    ["observed"] = new JsonObject
                    {
                        ["available"] = false,
                        ["reason"] = "observation_size_limit",
                    },
                }.ToJsonString());
            }
            // The process catalog allows fifty verified rows. Keep its bounded
            // structured facts whole; cutting JSON makes every observation vanish.
            // SHELL2075 «ejecutá dir en el escritorio»: the console adapter already
            // bounds its output (8 KiB and sixty lines), and the listing crossed
            // 16 KiB of JSON, so the cut left the mind without «seen» and the final
            // said nothing of what came out.
            return new OperationResponseProjection(TruncateMessage(response.Message.Trim(),
                maximumLength: operationName is "system.process.list" or "shell.command.run"
                    ? ProtocolLimits.MaximumOperationResponseMessageChars : MaximumMessageLength));
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
