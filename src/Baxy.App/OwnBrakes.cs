using System.Text.Json.Nodes;

namespace Baxy.App;

/// <summary>
/// COR1 (prueba en vivo VIVO3, fila A3, 2026-11-10, 2 de 2: with «Búsqueda web» off, «Busca en YouTube un vídeo de…»
/// was refused, the model called baxy.settings.set, switched it back on unasked and played the video; APP1 had read it
/// in the code as COR-1). The settings of BAXY's own that are a brake the person put on it, and the value that relaxes
/// each one: what goes out to the internet (web_search), BAXY's voice aloud (voice), speaking to them while they play,
/// are in a call or watch a video (no_interrupt_*), and the silence of its proposals (proposals). Such a change runs
/// unasked only when the person asked for it in this turn (<see cref="NetworkEgress.Holds"/>: a form compared, a
/// clause of their words that ends in the setting's own name and nothing else done first); one the model proposes on its own waits for their
/// «sí», as memory.enable does (RiskPolicy, encargo 76). The other direction keeps more private or more quiet and
/// goes directly. Not here: the overlay and the accessible mode (how BAXY's own window looks, no brake), and
/// confirmation_bypass, whose «on» the chat cannot do at all (BaxySettingHandler.BypassInterfaceOnly). OWASP LLM06
/// (Excessive Agency, 2025: «require a human to approve high-impact actions»), identity: «nada sale del PC salvo lo
/// que «La red» permite».
/// </summary>
internal static class OwnBrakes
{
    internal const string Operation = "baxy.settings.set";

    /// <summary>Why a call waits for the person's «sí» (or, where nothing asks, does not run): the code the model reads.</summary>
    internal const string Cause = "setting_not_asked";

    /// <summary>What the model reads besides, with a change held for the person's «sí».</summary>
    internal const string HeldNext =
        "the person did not ask for this change to BAXY's own settings in this turn: your question says which setting "
        + "it is and what it would be set to";

    /// <summary>What the model reads where nothing asks (Bypass): how the setting stays, and that the change is the
    /// person's to ask for, by the setting's name as Ajustes shows it. Banco cor1_ho en Bypass (2026-11-10): told only
    /// «tell them how it is set», the 4B said «la búsqueda web ya está activada» or that it could already search in 7 of 9 refusals; the value is said.</summary>
    internal static string RefusedNext(string brake) =>
        $"nothing changed: {brake} stays {Kept(brake)}, as the person set it, and they did not ask to change it in this "
        + $"turn; tell them it is {Kept(brake)} and that they change it by asking for it by its name ("
        + string.Join(", ", Names(brake).Select(static name => "«" + name + "»")) + "), or in BAXY's Settings";

    /// <summary>The value a brake that is on has: the one that does not relax it.</summary>
    internal static string Kept(string brake) =>
        Brakes.TryGetValue(brake, out (string Relaxes, string[] Names, string Es, string En) known) && known.Relaxes == "off"
            ? "on"
            : "off";

    // Each brake: the value that relaxes it, the name the person's words are weighed against (its row in Ajustes:
    // SettingsPanel «Búsqueda web», «Silenciar su voz»; ProposalsSection «Propuestas» and, under «No me interrumpas
    // durante…», «Llamadas», «Juegos», «Vídeo a pantalla completa»), and what the card and the step show, each in
    // Spanish and in English.
    private static readonly Dictionary<string, (string Relaxes, string[] Names, string Es, string En)> Brakes =
        new(StringComparer.Ordinal)
        {
            ["no_interrupt_calls"] = ("off", ["Llamadas", "Calls"], "No interrumpir en llamadas", "Don’t interrupt in calls"),
            ["no_interrupt_games"] = ("off", ["Juegos", "Games"], "No interrumpir en juegos", "Don’t interrupt in games"),
            ["no_interrupt_videos"] = ("off", ["Vídeo a pantalla completa", "Full-screen video"],
                "No interrumpir en vídeos", "Don’t interrupt in videos"),
            ["proposals"] = ("on", ["Propuestas", "Proposals"], "Propuestas", "Proposals"),
            ["voice"] = ("on", ["Voz", "Voice"], "Voz de BAXY", "BAXY’s voice"),
            ["web_search"] = ("on", ["Búsqueda web", "Web search"], "Búsqueda web", "Web search"),
        };

    // The other settings baxy.settings.set takes, by the name Ajustes gives each.
    private static readonly Dictionary<string, (string Es, string En)> Others = new(StringComparer.Ordinal)
    {
        ["accessible_mode"] = ("Modo accesible", "Accessible mode"),
        ["confirmation_bypass"] = ("Bypass", "Bypass"),
        ["overlay"] = ("Overlay", "Overlay"),
    };

    private static readonly Dictionary<string, (string Es, string En)> Values = new(StringComparer.Ordinal)
    {
        ["on"] = ("activar", "turn on"),
        ["off"] = ("desactivar", "turn off"),
        ["30m"] = ("silenciar 30 min", "mute for 30 min"),
        ["1h"] = ("silenciar 1 h", "mute for 1 h"),
        ["tomorrow"] = ("silenciar hasta mañana", "mute until tomorrow"),
    };

    /// <summary>The brake this call relaxes, by its setting, or null: any other call, setting or value.</summary>
    internal static string? Relaxed(string operation, JsonObject arguments) =>
        operation == Operation && Text(arguments["setting"]) is { } setting
        && Brakes.TryGetValue(setting, out (string Relaxes, string[] Names, string Es, string En) brake)
        && Text(arguments["value"]) == brake.Relaxes
            ? setting
            : null;

    /// <summary>The names the person may call this brake by: the one Ajustes shows, in each language.</summary>
    internal static string[] Names(string setting) =>
        Brakes.TryGetValue(setting, out (string Relaxes, string[] Names, string Es, string En) brake) ? brake.Names : [];

    /// <summary>What a change of one of BAXY's own settings is about, as the card and the step show it («Búsqueda web:
    /// activar»), or null for another call or a setting or value it does not know.</summary>
    internal static string? Shown(string operation, JsonObject arguments, bool english)
    {
        if (operation != Operation || Text(arguments["setting"]) is not { } setting
            || Text(arguments["value"]) is not { } value || !Values.TryGetValue(value, out (string Es, string En) to))
        {
            return null;
        }

        (string Es, string En)? name = Brakes.TryGetValue(setting, out (string Relaxes, string[] Names, string Es, string En) brake)
            ? (brake.Es, brake.En)
            : Others.TryGetValue(setting, out (string Es, string En) other) ? other : null;
        return name is { } known ? UiLanguage.Say(english, known.Es + ": " + to.Es, known.En + ": " + to.En) : null;
    }

    private static string? Text(JsonNode? node) =>
        node is JsonValue value && value.TryGetValue(out string? text) && !string.IsNullOrWhiteSpace(text) ? text : null;
}
