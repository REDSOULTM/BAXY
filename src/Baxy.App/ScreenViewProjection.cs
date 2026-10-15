using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace Baxy.App;

/// <summary>
/// How the model reads a look at an application window (<c>input.visible.controls</c>): one line per control with the
/// index it clicks by, its kind, name and state, then the text on screen grouped top, middle and bottom in reading
/// order. Pixel rectangles, colours, repeated OCR marks and the reader's own bookkeeping are left out: the model acts by
/// index or label, and a 4B reads a short text view far better than a long JSON one (AgentOccam, ICLR 2025: the same
/// agent +161 % from the observation alone; OSWorld and UFO2 filter the tree to visible, enabled, named controls).
/// Presentation only: every control and every line the reader returned is kept, nothing is ranked or chosen.
/// </summary>
internal static class ScreenViewProjection
{
    private static readonly (string Label, string[] Zones)[] Bands =
    [
        ("arriba", ["TL", "T", "TR"]),
        ("centro", ["L", "C", "R"]),
        ("abajo", ["BL", "B", "BR"]),
    ];

    /// <param name="message">The kernel's visible facts of the look (operation, verified, succeeded).</param>
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
            text.Append((bool?)window["foreground"] == false ? ", no está al frente" : ", al frente");
            if (window["coveredBy"] is JsonObject cover)
            {
                text.Append(", tapada por «").Append((string?)cover["title"]).Append('»');
            }

            text.Append('\n');
            if (window["focused"] is JsonObject focused)
            {
                text.Append("Foco: ").Append(Control(focused)).Append('\n');
            }
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
            text.Append("(ninguno: la ventana no expone sus controles; actúa por el texto en pantalla)\n");
        }

        int count = (int?)view["controlCount"] ?? controls.Count;
        if (count > controls.Count)
        {
            text.Append("(+").Append(count - controls.Count).Append(" más fuera de la vista)\n");
        }

        if (view["text"] is JsonObject zones)
        {
            var seen = new HashSet<string>(StringComparer.Ordinal);
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
                        string value = ((string?)line ?? string.Empty).Trim();
                        if (value.Length > 0 && seen.Add(value))
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
        }

        if ((string?)view["error"] is { Length: > 0 } error)
        {
            text.Append("Error: ").Append(error).Append('\n');
        }

        projected = new JsonObject
        {
            ["kind"] = facts["kind"]?.DeepClone(),
            ["operation"] = facts["operation"]?.DeepClone(),
            ["verified"] = facts["verified"]?.DeepClone(),
            ["succeeded"] = facts["succeeded"]?.DeepClone(),
            ["view"] = text.ToString().TrimEnd(),
        }.ToJsonString(new JsonSerializerOptions
        {
            Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
        });
        return true;
    }

    private static string Control(JsonObject control)
    {
        var line = new StringBuilder();
        line.Append('[').Append((int?)control["i"]).Append("] ").Append((string?)control["kind"]).Append(" «")
            .Append((string?)control["name"]).Append('»');
        if ((string?)control["value"] is { Length: > 0 } value)
        {
            line.Append(" = ").Append(value);
        }

        if ((string?)control["state"] is { Length: > 0 } state)
        {
            line.Append(" (").Append(state).Append(')');
        }

        if ((int?)control["repeated"] is > 1 and int repeated)
        {
            line.Append(" ×").Append(repeated);
        }

        return line.ToString();
    }
}
