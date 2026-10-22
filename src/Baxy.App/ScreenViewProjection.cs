using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace Baxy.App;

/// <summary>
/// How the model reads a look at an application window (<c>input.visible.controls</c>): one line per control with the
/// index it clicks by, its kind, name, zone of the window (when the reader gave it) and state, after one line with the
/// controls the reader marked as selected or on, then the text on screen grouped top, middle and bottom in reading
/// order. The reader's own bookkeeping is left out: version, ok, elapsedMs, authority, the name of the text's reader
/// (textAuthority; only its absence or its cut is said), and of the window its processId, its family of processes and the
/// process of the window covering it. The model acts by index or label, and a 4B reads a short text view far better
/// than a long JSON one (AgentOccam, ICLR 2025: the same agent +161 % from the observation alone; OSWorld and UFO2
/// filter the tree to visible, enabled, named controls).
/// Presentation only: every control the reader returned is kept, one it found several times once with «×N», N the
/// times it found it (the worker's «repeated» counts the copies after the first); every line of text the reader
/// returned is kept in its zone, a line that repeats included (a chat read by its lines repeats a bubble's text, and
/// two «ok» are two messages), except one that only repeats a listed control's name, left out and counted; nothing is
/// ranked or chosen, and what the reader said about its own reading stays said: a cut walk, a frame without content, a
/// tree it could not read, text it could not read, the disabled controls, the window being a modal dialog, protected or
/// run as administrator (audit 2026-10-15: those were dropped, and a cut walk read as «(ninguno)» with no cause).
/// </summary>
internal static class ScreenViewProjection
{
    private static readonly (string Label, string[] Zones)[] Bands =
    [
        ("arriba", ["TL", "T", "TR"]),
        ("centro", ["L", "C", "R"]),
        ("abajo", ["BL", "B", "BR"]),
    ];

    // BAXY Renew al máximo 7.3 (A11y-Compressor; OSWorld, UFO2): where a control's centre sits in the window's 3×3
    // grid, in the words of the text's bands, so two «Buscar» or «el primer resultado» are told apart.
    private static readonly Dictionary<string, string> Zones = new(StringComparer.Ordinal)
    {
        ["TL"] = "arriba izq.", ["T"] = "arriba", ["TR"] = "arriba der.",
        ["L"] = "centro izq.", ["C"] = "centro", ["R"] = "centro der.",
        ["BL"] = "abajo izq.", ["B"] = "abajo", ["BR"] = "abajo der.",
    };

    /// <param name="message">The kernel's visible facts of the look (status, error, cause, effectUncertain).</param>
    /// <param name="result">The look's receipt: the whole view the reader returned.</param>
    internal static bool TryCreate(string message, JsonElement result, out string projected)
    {
        projected = string.Empty;
        JsonObject? facts;
        JsonObject? view;
        try
        {
            facts = JsonNode.Parse(message) as JsonObject;
            view = JsonNode.Parse(result.GetRawText()) as JsonObject;
        }
        catch (JsonException)
        {
            return false;
        }

        if (facts is null || view?["controls"] is not JsonArray controls)
        {
            return false;
        }

        var text = new StringBuilder();
        if (view["window"] is JsonObject window)
        {
            // Its number is what the acting tools take as window, so they act in it and not in the person's window.
            text.Append("Ventana «").Append((string?)window["title"]).Append("» (").Append((string?)window["process"])
                .Append(", window ").Append((long?)window["hwnd"]).Append(')');
            // Said only as observed: a reader that did not report the front says nothing about it.
            text.Append((bool?)window["foreground"] switch
            {
                true => ", al frente",
                false => ", no está al frente",
                null => string.Empty,
            });
            if (window["coveredBy"] is JsonObject cover)
            {
                text.Append(", tapada por «").Append((string?)cover["title"]).Append('»');
            }

            if ((bool?)window["modal"] == true)
            {
                text.Append(", es el diálogo modal que bloquea la ventana");
            }

            // Ronda final 22 (regla 3): the look itself showed a minimized window; said, as it stays shown.
            if ((bool?)window["shownFromMinimized"] == true)
            {
                text.Append(", estaba minimizada: la mirada la mostró detrás de la de delante, sin activarla, y queda así");
            }

            if ((bool?)window["systemTool"] == true)
            {
                // Incidente del 2026-10-15: no name opens a system configuration tool to acts.
                text.Append(", herramienta de configuración del sistema (BAXY no pulsa ni escribe en ella: lo hace la persona)");
            }
            else if ((bool?)window["protected"] == true)
            {
                text.Append(", ventana protegida (no se actúa en ella; si es un editor o una terminal, sí cuando una mirada la nombra por su aplicación; la de BAXY, nunca)");
            }

            if ((bool?)window["elevated"] == true)
            {
                // The reader marks it when the window's process runs with more rights than BAXY or that could not be
                // read (VisibleControlSurface.RunsAboveUs).
                text.Append((bool?)window["reopensUnraised"] == true
                    ? ", corre como administrador o no se pudo comprobar (se puede reabrir sin permisos de administrador)"
                    : ", corre como administrador o no se pudo comprobar");
            }

            text.Append('\n');
            if (window["focused"] is JsonObject focused)
            {
                text.Append("Foco: ").Append(Control(focused)).Append('\n');
            }
        }

        // BAXY Renew al máximo P8.4 (sonda F019: «quedó en la tienda» with the library's tab selected): what the reader
        // marked as chosen (selected, or toggled on) is said first, before the reading order buries it between brackets.
        string[] chosen = controls.OfType<JsonObject>()
            .Where(static control => ((string?)control["state"] ?? string.Empty).Split(' ')
                .Any(static part => part is "selected" or "on"))
            .Select(static control => $"[{(int?)control["i"]}] {(string?)control["kind"]} «{(string?)control["name"]}»")
            .ToArray();
        if (chosen.Length > 0)
        {
            text.Append("Seleccionados o activados: ").Append(string.Join(" | ", chosen)).Append('\n');
        }

        text.Append("Controles:\n");
        foreach (JsonNode? node in controls)
        {
            if (node is JsonObject control)
            {
                text.Append(Control(control)).Append('\n');
            }
        }

        if (controls.Count == 0)
        {
            text.Append("(ninguno)\n");
        }

        int count = (int?)view["controlCount"] ?? controls.Count;
        if (count > controls.Count)
        {
            text.Append("(+").Append(count - controls.Count).Append(" más, sin listar por el tope)\n");
        }

        if (view["disabled"] is JsonArray disabled && disabled.Count > 0)
        {
            text.Append("Desactivados: ").Append(string.Join(" | ", disabled.OfType<JsonObject>()
                .Select(static control => $"{(string?)control["kind"]} «{(string?)control["name"]}»"))).Append('\n');
        }

        // Ronda final 20 (regla 3): disabled controls the look did not list are not controls that do not exist.
        if ((bool?)view["disabledCut"] == true)
        {
            text.Append("(puede haber controles desactivados sin listar)\n");
        }

        // What the reader said about its own reading.
        if ((bool?)view["partial"] == true)
        {
            text.Append("(la lectura quedó incompleta: puede haber más controles sin listar)\n");
        }

        if ((bool?)view["frameOnly"] == true)
        {
            text.Append("(sólo se leyó el marco de la ventana: sus controles no se pudieron leer)\n");
        }

        if ((string?)view["uiaFailed"] is { Length: > 0 } walkFailed)
        {
            text.Append("(no se pudo leer el árbol accesible de la ventana: ").Append(walkFailed).Append(")\n");
        }

        if ((string?)view["textAuthority"] == "unavailable")
        {
            text.Append("(no se pudo leer el texto en pantalla)\n");
        }

        // Ronda final 19 (regla 3): text not read, or read and cut, is said, never taken for what the window shows.
        if ((string?)view["textAuthority"] == "not_read")
        {
            text.Append("(el texto en pantalla no se leyó en esta mirada: se lee con includeText)\n");
        }

        if ((int?)view["textOmittedLines"] is > 0 and int omittedLines)
        {
            text.Append("(texto cortado: ").Append(omittedLines)
                .Append(" líneas leídas no se listan, por largas o pasado el tope)\n");
        }

        if (view["text"] is JsonObject zones)
        {
            // BAXY Renew al máximo 7.2 (A11y-Compressor; AgentOccam, table 10): a line that only repeats the name of a
            // control listed above says nothing new; it is left out and how many were is said, so a notice worded as a
            // button is never taken for absent.
            var listedNames = new HashSet<string>(
                controls.Concat(view["disabled"] as JsonArray ?? [])
                    .Select(static control => Folded((string?)control?["name"]))
                    .Where(static name => name.Length > 0),
                StringComparer.OrdinalIgnoreCase);
            int repeatedNames = 0;
            foreach ((string label, string[] bandZones) in Bands)
            {
                var lines = new List<string>();
                foreach (string zone in bandZones)
                {
                    if (zones[zone] is not JsonArray zoneLines)
                    {
                        continue;
                    }

                    foreach (JsonNode? line in zoneLines)
                    {
                        if ((string?)line is not { Length: > 0 } value)
                        {
                            continue;
                        }

                        if (listedNames.Contains(Folded(value)))
                        {
                            repeatedNames++;
                        }
                        else
                        {
                            lines.Add(value);
                        }
                    }
                }

                if (lines.Count > 0)
                {
                    text.Append("Texto ").Append(label).Append(": ").Append(string.Join(" | ", lines)).Append('\n');
                }
            }

            if (repeatedNames > 0)
            {
                text.Append('(').Append(repeatedNames)
                    .Append(" líneas de texto no se listan: repiten el nombre de un control listado)\n");
            }
        }

        if ((string?)view["error"] is { Length: > 0 } error)
        {
            text.Append("Error: ").Append(error).Append('\n');
        }

        // The kernel's facts of the look travel whole (status, error, cause, effectUncertain included); only what it
        // observed is re-presented, as the view, made from the whole receipt: the kernel's mark that its own copy of the
        // observation was cut (observedLimit) does not describe this view.
        var projection = new JsonObject();
        foreach ((string key, JsonNode? fact) in facts)
        {
            if (key is not ("observed" or "observedLimit"))
            {
                projection[key] = fact?.DeepClone();
            }
        }

        projection["view"] = text.ToString().TrimEnd();
        projected = projection.ToJsonString(new JsonSerializerOptions
        {
            Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
        });
        return true;
    }

    private static string Folded(string? text) => string.Join(' ',
        (text ?? string.Empty).Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries));

    private static string Control(JsonObject control)
    {
        var line = new StringBuilder();
        line.Append('[').Append((int?)control["i"]).Append("] ").Append((string?)control["kind"]).Append(" «")
            .Append((string?)control["name"]).Append('»');
        // Only when the reader gave one: a control without its rectangle has no zone.
        if ((string?)control["zone"] is { } zone && Zones.TryGetValue(zone, out string? place))
        {
            line.Append(" (").Append(place).Append(')');
        }

        if ((string?)control["value"] is { Length: > 0 } value)
        {
            line.Append(" = ").Append(value);
        }

        if ((string?)control["state"] is { Length: > 0 } state)
        {
            line.Append(" (").Append(state).Append(')');
        }

        // BAXY Renew cu (C11): what the application says the item is (Excel's «1» is «Encabezado de fila»).
        if ((string?)control["itemType"] is { Length: > 0 } itemType)
        {
            line.Append(" (tipo: ").Append(itemType).Append(')');
        }

        // The worker counts the copies after the first (DesktopUiaWorker.ps1, $seen[$key].repeated): found three
        // times it says 2, and the view says the three.
        if ((int?)control["repeated"] is > 0 and int copies)
        {
            line.Append(" ×").Append(copies + 1);
        }

        if ((string?)control["shortcut"] is { Length: > 0 } shortcut)
        {
            line.Append(" [atajo ").Append(shortcut).Append(']');
        }

        return line.ToString();
    }
}
