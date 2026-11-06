using System.Text.Json.Nodes;
using Baxy.Contracts;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Infrastructure;

namespace Baxy.App;

/// <summary>
/// Renew al máximo (w7, apps). E2e E014, «abre la configuración de sonido»: the model wrote «Configuración del sistema»
/// (msconfig), a name next to «Configuración» in the installed list, at 0.99, with place sound 34 times in the PC's
/// practice runs (p4-p7, 2026-10-15) and on the notebook (int3 s0, 2026-10-22); the opening refused the place, and the
/// model then called the same again or opened msconfig with no place. In a turn the person opened, an app.open of an
/// application their words do not name, at a place that application does not have and only one other application has
/// (ApplicationPlaces), opens that one at the place before anything runs, when their words name that one (by any of its
/// names), and its result says so and how the one the model wrote is opened. Encargo 62 (U41, «Abre Gmail»: Google Chrome
/// at about opened Settings, which no word asked for): without that name the call runs as written, and its refusal says
/// how the application it wrote opens. Opening an application at a page is app.open's own risk (low_reversible), whichever
/// it is. Aid «place_owner» (BAXY_AYUDAS).
/// </summary>
internal sealed class SaidApplication
{
    /// <summary>The fact in the result of a call opened at another application: the key it goes under.</summary>
    internal const string NoteKey = "placeOwner";

    private string _spoken = string.Empty;

    /// <summary>The person's words open a turn.</summary>
    internal void Heard(string words) => _spoken = SaidFolders.Spoken(words ?? string.Empty);

    /// <summary>
    /// The person's words answer the call that waits for their «sí»: the words of the turn that asked it still hold, with
    /// these added, as in SaidFolders.Answered (auditoría de la App, 2026-10-23: voice and the Sí button agree).
    /// </summary>
    internal void Answered(string words)
    {
        string spoken = SaidFolders.Spoken(words ?? string.Empty);
        _spoken = _spoken.Length == 0 ? spoken : _spoken + "\n" + spoken;
    }

    /// <summary>A heartbeat or a new session: no words of the person's hold.</summary>
    internal void Clear() => _spoken = string.Empty;

    /// <summary>The call opened at the application that has its place, and what its result says; null: it runs as it is.</summary>
    internal (JsonObject Arguments, string Note)? Rule(string operation, JsonObject arguments)
    {
        if (operation != "app.open" || _spoken.Trim().Length == 0 || !ModelAids.On(ModelAids.PlaceOwner)
            || Text(arguments["appId"]) is not { } application || Text(arguments["place"]) is not { } place
            || ApplicationPlaces.PlacesOf(application).Any(declared => declared.Place == place) || Said(application)
            || ApplicationPlaces.ApplicationsWith(place) is not [string owner]
            || !ApplicationPlaces.NamesOf(owner).Any(Said))
            return null;
        var routed = (JsonObject)arguments.DeepClone();
        routed["appId"] = owner;
        return (routed, $"the person did not name {application}, and {place} is a place of {owner} alone: this call "
            + $"opened {owner} at {place} instead of {application}, as it was written; app_open with appId "
            + $"\"{application}\" and no place opens {application} itself");
    }

    // Every word of the name, or of the name without its qualifiers (CatalogNames.Stems; ajuste c4, banco ciego c3,
    // causa 16: «open PowerToys» names «PowerToys (Preview)»), is among the person's words («la configuración de sonido»
    // names «Configuración», not «Configuración del sistema»); or one of the application's non-ambiguous abbreviations is
    // (encargo 12: «abre el wsp» names WhatsApp), the owner's one accepted help, a name-equivalence list.
    private bool Said(string application) => CatalogNames.Stems(application).Any(stem =>
        SaidFolders.Spoken(stem).Split(' ', StringSplitOptions.RemoveEmptyEntries) is { Length: > 0 } words
        && words.All(word => _spoken.Contains(" " + word + " ", StringComparison.Ordinal)))
        || ApplicationAliases.Names(_spoken, application);

    private static string? Text(JsonNode? node) =>
        node is JsonValue value && value.TryGetValue(out string? text) && !string.IsNullOrWhiteSpace(text) ? text.Trim() : null;
}
