using System.Text.Json.Nodes;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Infrastructure;

namespace Baxy.App;

/// <summary>
/// Renew al máximo (w7, apps). E2e E014, «abre la configuración de sonido»: the model wrote «Configuración del sistema»
/// (msconfig), a name next to «Configuración» in the installed list, at 0.99, with place sound 34 times in the PC's
/// practice runs (p4-p7, 2026-10-15) and on the notebook (int3 s0, 2026-10-22); the opening refused the place, and the
/// model then called the same again or opened msconfig with no place. In a turn the person opened, an app.open of an
/// application their words do not name, at a place that application does not have and only one other application has
/// (ApplicationPlaces), opens that one at the place before anything runs, and its result says so and how the one the
/// model wrote is opened. Opening an application at a page is app.open's own risk (low_reversible), whichever it is.
/// Aid «place_owner» (BAXY_AYUDAS).
/// </summary>
internal sealed class SaidApplication
{
    /// <summary>The fact in the result of a call opened at another application: the key it goes under.</summary>
    internal const string NoteKey = "placeOwner";

    private string _spoken = string.Empty;

    /// <summary>The person's words open a turn.</summary>
    internal void Heard(string words) => _spoken = SaidFolders.Spoken(words ?? string.Empty);

    /// <summary>A heartbeat or a new session: no words of the person's hold.</summary>
    internal void Clear() => _spoken = string.Empty;

    /// <summary>The call opened at the application that has its place, and what its result says; null: it runs as it is.</summary>
    internal (JsonObject Arguments, string Note)? Rule(string operation, JsonObject arguments)
    {
        if (operation != "app.open" || _spoken.Trim().Length == 0 || !ModelAids.On(ModelAids.PlaceOwner)
            || Text(arguments["appId"]) is not { } application || Text(arguments["place"]) is not { } place
            || ApplicationPlaces.PlacesOf(application).Any(declared => declared.Place == place) || Said(application)
            || ApplicationPlaces.ApplicationsWith(place) is not [string owner])
            return null;
        var routed = (JsonObject)arguments.DeepClone();
        routed["appId"] = owner;
        return (routed, $"the person did not name {application}, and {place} is a place of {owner} alone: this call "
            + $"opened {owner} at {place} instead of {application}, as it was written; app_open with appId "
            + $"\"{application}\" and no place opens {application} itself");
    }

    // Every word of the name is among the person's words («la configuración de sonido» names «Configuración», not
    // «Configuración del sistema»).
    private bool Said(string application)
    {
        string[] words = SaidFolders.Spoken(application).Split(' ', StringSplitOptions.RemoveEmptyEntries);
        return words.Length > 0 && words.All(word => _spoken.Contains(" " + word + " ", StringComparison.Ordinal));
    }

    private static string? Text(JsonNode? node) =>
        node is JsonValue value && value.TryGetValue(out string? text) && !string.IsNullOrWhiteSpace(text) ? text.Trim() : null;
}
