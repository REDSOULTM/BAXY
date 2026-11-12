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
/// goes directly. Not here: the overlay and the accessible mode (how BAXY's own window looks, no brake). OWASP LLM06
/// (Excessive Agency, 2025: «require a human to approve high-impact actions»), identity: «nada sale del PC salvo lo
/// que «La red» permite».
/// TPV1 (dueño, 10-11-2026: «todo se controle por voz… no tiene que delegar al usuario nada»): the «sí» is spoken, in
/// Bypass too (a change nobody asked for waits for it there as well, instead of being refused with «ask for it by its
/// name, or in Settings»), and three more: Clima and Mirar la pantalla (Privacidad), Bypass itself, whose «on» always
/// waits for the «sí» (the identity's «ajuste consciente», said aloud), and the tool profile, which changes the tools
/// BAXY has: asked by the profile's own name, or with the «sí». APP2 (REV11 A-3): and «Avisar de versiones nuevas», whose
/// «on» asks GitHub at every start.
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

    internal const string ToolProfile = "tool_profile";

    internal const string Bypass = "confirmation_bypass";

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
            ["weather"] = ("on", ["Clima", "Weather"], "Clima", "Weather"),
            ["screen"] = ("on", ["Mirar la pantalla", "Look at the screen"], "Mirar la pantalla", "Look at the screen"),
            // SettingsPanel «Confirmación»: «Sin frenos»; the Rail's pill says the same.
            [Bypass] = ("on", ["Sin frenos", "Bypass", "No brakes"], "Sin frenos", "No brakes"),
            // Any ready-made profile: its own name is what the person asks for (ToolsSection's PRESETS), not the setting's.
            [ToolProfile] = ("*", [], "Perfil de herramientas", "Tool profile"),
            // APP2 (REV11 A-3): on, BAXY asks GitHub at every start (UpdateSection, PRIVACIDAD.md «Sin que lo pidas»).
            ["update_notice"] = ("on", ["Avisar de versiones nuevas", "Tell me about new versions"],
                "Avisar de versiones nuevas", "Tell me about new versions"),
        };

    // Each ready-made tool profile by the name Settings → Tools shows, in each language.
    private static readonly Dictionary<string, (string Es, string En)> Profiles = new(StringComparer.Ordinal)
    {
        ["esencial"] = ("Esencial", "Essential"),
        ["diario"] = ("Diario", "Everyday"),
        ["avanzado"] = ("Avanzado", "Advanced"),
        ["completo"] = ("Completo", "Complete"),
    };

    // The other settings baxy.settings.set takes, by the name Ajustes gives each.
    private static readonly Dictionary<string, (string Es, string En)> Others = new(StringComparer.Ordinal)
    {
        ["accessible_mode"] = ("Modo accesible", "Accessible mode"),
        ["overlay"] = ("Overlay", "Overlay"),
        ["close_to_tray"] = ("Al cerrar, seguir en la bandeja", "On close, stay in the tray"),
        ["minimize_to_tray"] = ("Al minimizar, ir a la bandeja", "On minimize, go to the tray"),
        ["echo_cancel"] = ("Ignorar lo que suena en el PC", "Ignore what the PC plays"),
        ["wait_notice"] = ("Decir «Un momento»", "Say «One moment»"),
        ["wake_sound"] = ("Sonido al despertar", "Wake sound"),
    };

    private static readonly Dictionary<string, (string Es, string En)> Values = new(StringComparer.Ordinal)
    {
        ["on"] = ("activar", "turn on"),
        ["off"] = ("desactivar", "turn off"),
        ["30m"] = ("silenciar 30 min", "mute for 30 min"),
        ["1h"] = ("silenciar 1 h", "mute for 1 h"),
        ["tomorrow"] = ("silenciar hasta mañana", "mute until tomorrow"),
    };

    /// <summary>The brake this call relaxes, by its setting, or null: any other call, setting or value. Any change of
    /// tool profile counts. Not memory.enable: RiskPolicy asks it in normal mode, and held in Bypass too (measured, TPV1)
    /// the 4B called it again after the person's «sí» to its own offer in words and the fact was never saved (0 of 12).</summary>
    internal static string? Relaxed(string operation, JsonObject arguments) =>
        operation == Operation && Text(arguments["setting"]) is { } setting
        && Brakes.TryGetValue(setting, out (string Relaxes, string[] Names, string Es, string En) brake)
        && (setting == ToolProfile
            ? Text(arguments["value"]) is { } profile && Profiles.ContainsKey(profile)
            : Text(arguments["value"]) == brake.Relaxes)
            ? setting
            : null;

    /// <summary>Whether this brake waits for the person's «sí» even when they named it: Bypass, the conscious setting.</summary>
    internal static bool AlwaysAsks(string brake) => brake == Bypass;

    /// <summary>The names the person may call this change by: the one Ajustes shows, in each language; for a tool
    /// profile, the profile's own.</summary>
    internal static string[] Names(string setting, JsonObject arguments)
    {
        ArgumentNullException.ThrowIfNull(arguments);
        if (setting == ToolProfile)
        {
            return Text(arguments["value"]) is { } profile && Profiles.TryGetValue(profile, out (string Es, string En) shown)
                ? [shown.Es, shown.En]
                : [];
        }

        return Brakes.TryGetValue(setting, out (string Relaxes, string[] Names, string Es, string En) brake) ? brake.Names : [];
    }

    /// <summary>What a change of one of BAXY's own settings is about, as the card and the step show it («Búsqueda web:
    /// activar»), or null for another call or a setting or value it does not know.</summary>
    internal static string? Shown(string operation, JsonObject arguments, bool english)
    {
        if (operation != Operation || Text(arguments["setting"]) is not { } setting
            || Text(arguments["value"]) is not { } value)
        {
            return null;
        }

        if (Profiles.TryGetValue(value, out (string Es, string En) profile))
        {
            return setting == ToolProfile
                ? UiLanguage.Say(english, "Perfil de herramientas: " + profile.Es, "Tool profile: " + profile.En)
                : null;
        }

        if (!Values.TryGetValue(value, out (string Es, string En) to))
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
