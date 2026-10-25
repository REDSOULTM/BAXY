using System.Text.Json;
using Baxy.Contracts;

namespace Baxy.App;

internal sealed record OperationResponseProjection(string Message)
{
    /// <param name="asked">The application and place this turn's app.open asked for (TurnPlace), told in a look.</param>
    public static OperationResponseProjection Create(
        OperationResponse response, string operationName, (string Application, string Place)? asked = null)
    {
        ArgumentNullException.ThrowIfNull(response);
        ArgumentException.ThrowIfNullOrWhiteSpace(operationName);
        // The look's whole view is the receipt's result; the kernel's visible facts keep only its first rows.
        if (operationName == "input.visible.controls"
            && response.Result is { ValueKind: JsonValueKind.Object } look
            && ScreenViewProjection.TryCreate(response.Message, look, out string view, asked))
        {
            return new OperationResponseProjection(Replay(response, view));
        }

        // The kernel's visible facts as they came: it bounds them (8 KiB; 48 000 characters for the process list, a
        // console's output and OCR; the clipboard, page and email reads stop at 6 000 characters of their own) and the
        // protocol checks every message non-empty and within 48 000 (ContractValidator).
        return new OperationResponseProjection(Replay(response, response.Message.Trim()));
    }

    // Ronda final 35 (regla 3): the journal's answer to this same invocation, run before, is said as such: it did not
    // run again now (a second «sube el volumen 10» answered by the first one's receipt).
    // Ronda final 36: inside the JSON when the message is one (mind.py's summary parses it), else as a line.
    private static string Replay(OperationResponse response, string message)
    {
        if (!response.Replayed)
        {
            return message;
        }

        const string note = "this is the recorded result of the same call made earlier; it did not run again now";
        try
        {
            if (System.Text.Json.Nodes.JsonNode.Parse(message) is System.Text.Json.Nodes.JsonObject facts)
            {
                facts["replayed"] = note;
                return facts.ToJsonString(new JsonSerializerOptions
                {
                    Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
                });
            }
        }
        catch (JsonException)
        {
        }

        return message + "\nreplayed: " + note + ".";
    }
}
