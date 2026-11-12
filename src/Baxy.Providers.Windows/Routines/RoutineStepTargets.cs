using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Providers.Windows.External;

namespace Baxy.Providers.Windows.Routines;

/// <summary>
/// RUT4 (owner, 2026-11-10: «cuando te diga audífonos, cambia a los audífonos…»; ENCARGO_RUT4 §3: «un paso que no casa
/// con ningún dispositivo devuelve los candidatos y la rutina no se guarda a ciegas»): a routine's step that names a
/// sound device of this PC is looked up when the routine is saved, with the same read and the same comparison by form
/// the call itself makes (audio.device.list, <see cref="WindowsAudioDeviceAdapter.Matching"/>). A name that is no
/// active device, or that several are, saves nothing: the devices there are go back for the model to ask. Nothing is
/// changed here; the call resolves again each time the routine runs.
/// </summary>
public static class RoutineStepTargets
{
    /// <summary>The operation whose target is a device of the PC that has to be there to save the step.</summary>
    public const string SoundDevice = "audio.device.set";

    /// <summary>
    /// Null when the step's target is there once, when the operation has no such target, or when the devices could not
    /// be read (the routine is saved, and the call says what it finds when it runs). Otherwise what was found instead:
    /// <c>problem</c> (the call's own code: audio_device_not_matched or audio_device_ambiguous), <c>kind</c> and
    /// <c>devices</c> (the ones that match, or all the active ones when none does).
    /// </summary>
    public static async ValueTask<JsonObject?> MissingAsync(
        IExternalCapabilityProvider provider, string operation, JsonObject arguments, CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(provider);
        ArgumentNullException.ThrowIfNull(arguments);
        if (operation != SoundDevice
            || arguments["device"] is not JsonValue named || !named.TryGetValue(out string? said) || string.IsNullOrWhiteSpace(said))
        {
            return null;
        }

        string kind = arguments["kind"] is JsonValue kindValue && kindValue.TryGetValue(out string? given) && given == "input"
            ? "input"
            : "output";
        using JsonDocument none = JsonDocument.Parse("{}");
        ExternalCapabilityReceipt listed = await provider.InvokeAsync("audio.device.list", none.RootElement, cancellationToken)
            .ConfigureAwait(false);
        if (listed.ErrorCode is not null || listed.Result is not { ValueKind: JsonValueKind.Object } result
            || !result.TryGetProperty(kind == "input" ? "inputs" : "outputs", out JsonElement devices)
            || devices.ValueKind != JsonValueKind.Array)
        {
            return null;
        }

        string[] names = [.. devices.EnumerateArray()
            .Select(static device => device.TryGetProperty("name", out JsonElement name) ? name.GetString() : null)
            .OfType<string>()];
        IReadOnlyList<int> matching = WindowsAudioDeviceAdapter.Matching(said, names);
        if (matching.Count == 1)
        {
            return null;
        }

        IEnumerable<string> shown = matching.Count == 0 ? names : matching.Select(index => names[index]);
        return new JsonObject
        {
            ["problem"] = matching.Count == 0 ? WindowsAudioDeviceAdapter.NotMatched : WindowsAudioDeviceAdapter.Ambiguous,
            ["kind"] = kind,
            ["said"] = said,
            ["devices"] = new JsonArray(shown.Select(static name => (JsonNode?)name).ToArray()),
        };
    }
}
