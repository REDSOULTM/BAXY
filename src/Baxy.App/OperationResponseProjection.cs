using System.Text.Json;
using Baxy.Contracts;

namespace Baxy.App;

internal sealed record OperationResponseProjection(string Message)
{
    public static OperationResponseProjection Create(OperationResponse response, string operationName)
    {
        ArgumentNullException.ThrowIfNull(response);
        ArgumentException.ThrowIfNullOrWhiteSpace(operationName);
        // The look's whole view is the receipt's result; the kernel's visible facts keep only its first rows.
        if (operationName == "input.visible.controls"
            && response.Result is { ValueKind: JsonValueKind.Object } look
            && ScreenViewProjection.TryCreate(response.Message, look, out string view))
        {
            return new OperationResponseProjection(view);
        }

        // The kernel's visible facts as they came: it bounds them (8 KiB; 48 000 characters for the process list, a
        // console's output and OCR) and the protocol checks every message non-empty and within 48 000 (ContractValidator).
        return new OperationResponseProjection(response.Message.Trim());
    }
}
