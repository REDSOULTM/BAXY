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
            return new OperationResponseProjection(Replay(response, view));
        }

        // The kernel's visible facts as they came: it bounds them (8 KiB; 48 000 characters for the process list, a
        // console's output and OCR) and the protocol checks every message non-empty and within 48 000 (ContractValidator).
        return new OperationResponseProjection(Replay(response, response.Message.Trim()));
    }

    // Ronda final 35 (regla 3): the journal's answer to this same invocation, run before, is said as such: it did not
    // run again now (a second «sube el volumen 10» answered by the first one's receipt).
    private static string Replay(OperationResponse response, string message) =>
        response.Replayed
            ? message + "\nreplayed: this is the recorded result of the same call made earlier; it did not run again now."
            : message;
}
