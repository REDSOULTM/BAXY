using System.Text.Json.Nodes;

namespace Baxy.App;

// The «mark:» atom: a label a window without an accessible tree marks chosen by its ink.
internal static partial class ComputerUseSuccessCheck
{
    // Two colourless inks are the same within this brightness (0–255), and apart from this much on (contract §1.7).
    private const int SameInkValue = 40;
    private const int OtherInkValue = 64;
    private static readonly char[] LabelEdges = ['"', '\'', '«', '»', '“', '”', '‘', '’', ' ', '.', ',', ':', ';', '·', '•'];

    /// <summary>
    /// «mark:X» (contract §1.7, v3 punto 5): on a window drawn without an accessible tree, the label that is X alone is
    /// written in an ink none of its row shares while at least two other labels of the row (their centres within half
    /// its height of its own) share one ink; a colourless one must also stand out from the background more than they do. That is how a row of navigation labels marks the page the window is on
    /// (live 2026-10-07 v2-s12, v2-c17: on its library a game launcher writes «BIBLIOTECA» blue and «TIENDA»,
    /// «COMUNIDAD» and the account's name white). A row with a single other label, or neighbours of mixed inks, tell
    /// nothing; another application's window in front never passes (a covered one is read from its own drawing, v3
    /// point 0: banco r23b x10); and a label a click of the sub-goal may have pressed (verified or not) is not judged by
    /// its ink (the pointer resting on it, or the press, may light it): that arrival is page:'s to judge.
    /// </summary>
    private static bool MarkAtom(string rest, JsonObject view, JsonArray steps)
    {
        string target = Fold(rest).Trim(LabelEdges);
        if (target.Length < 3 || ComputerUseMission.ActionableCount(view) > 1 || view["textMarks"] is not JsonArray marks)
        {
            return false;
        }

        // Only the mission's own window: the named application's (requested by the adapter), or the one in front when
        // the mission names none (the loop's onTheApplication). With the named application closed the adapter reads the
        // window in front, and another launcher's library marked there is not the place reached (review 2026-10-07).
        if ((bool?)view["window"]?["requested"] != true && (bool?)view["onTheApplication"] != true)
        {
            return false;
        }

        // A click of the sub-goal on X that may have pressed it (verified or not: a slow page's post-read may not hold)
        // leaves X lit by the pointer or by the press itself: that arrival is page:'s to judge (review 2026-10-07).
        if (steps.OfType<JsonObject>().Any(step => (string?)step["operation"] == "input.visible.click"
            && ComputerUseMission.MayHaveActed(step)
            && (Fold((string?)step["label"]).Trim(LabelEdges) == target || Fold((string?)step["name"]).Trim(LabelEdges) == target)))
        {
            return false;
        }

        List<JsonObject> labels = marks.OfType<JsonObject>()
            .Where(mark => mark["rect"] is JsonObject && ((string?)mark["ink"] ?? string.Empty).Length > 0)
            .ToList();
        foreach (JsonObject named in labels.Where(mark => Fold((string?)mark["text"]).Trim(LabelEdges) == target))
        {
            (int x, int y, int w, int h) = MarkBox(named);
            if (h <= 0)
            {
                continue;
            }

            double middle = y + h / 2.0;
            List<JsonObject> row = labels
                .Where(mark => !ReferenceEquals(mark, named))
                .Where(mark =>
                {
                    (int mx, int my, int mw, int mh) = MarkBox(mark);
                    // In the row (its centre within half the label's height), and beside the label, not over it (the
                    // same words read again in the OCR's other pass).
                    return Math.Abs(my + mh / 2.0 - middle) <= h / 2.0 && (mx + mw <= x || mx >= x + w);
                })
                .ToList();
            if (row.Count >= 2
                && row.All(mark => SameInk(mark, row[0]))
                && row.All(mark => OtherInk(named, mark))
                && StandsOut(named, row))
            {
                return true;
            }
        }

        return false;
    }

    /// <summary>The labels a window without an accessible tree marks by their ink (mark:), as it writes them.</summary>
    internal static IEnumerable<string> MarkedLabels(JsonObject view) =>
        (view["textMarks"] as JsonArray ?? [])
            .OfType<JsonObject>()
            .Select(mark => (string?)mark["text"] ?? string.Empty)
            .Where(text => Fold(text).Trim(LabelEdges).Length >= 3 && MarkAtom(text, view, []))
            .Distinct(StringComparer.Ordinal);

    private static (int X, int Y, int W, int H) MarkBox(JsonObject mark) =>
        mark["rect"] is JsonObject rect
            ? ((int?)rect["x"] ?? 0, (int?)rect["y"] ?? 0, (int?)rect["w"] ?? 0, (int?)rect["h"] ?? 0)
            : (0, 0, 0, 0);

    private static readonly HashSet<string> ColourlessInks = new(StringComparer.Ordinal) { "white", "gray", "black" };

    // The same ink: one hue class, or two colourless inks of about the same brightness.
    private static bool SameInk(JsonObject one, JsonObject other)
    {
        string a = (string?)one["ink"] ?? string.Empty;
        string b = (string?)other["ink"] ?? string.Empty;
        bool colourless = ColourlessInks.Contains(a);
        if (colourless != ColourlessInks.Contains(b))
        {
            return false;
        }

        return colourless
            ? Math.Abs(((int?)one["inkV"] ?? 0) - ((int?)other["inkV"] ?? 0)) <= SameInkValue
            : a == b;
    }

    // A label marked without a hue of its own stands out from what it is written on (bgV) more than each neighbour
    // does, by OtherInkValue at least: a colourless label dimmer than its row is the disabled or unavailable one, never
    // the chosen one (review 2026-10-07). Without the background's brightness it tells nothing.
    private static bool StandsOut(JsonObject named, List<JsonObject> row)
    {
        if (!ColourlessInks.Contains((string?)named["ink"] ?? string.Empty))
        {
            return true;
        }

        static int? Contrast(JsonObject mark) =>
            (int?)mark["inkV"] is int ink && (int?)mark["bgV"] is int background ? Math.Abs(ink - background) : null;

        return Contrast(named) is int own
            && row.All(mark => Contrast(mark) is int other && own - other >= OtherInkValue);
    }

    // Another ink, beyond doubt: a hue against none, another hue class, or a brightness far apart.
    private static bool OtherInk(JsonObject one, JsonObject other)
    {
        string a = (string?)one["ink"] ?? string.Empty;
        string b = (string?)other["ink"] ?? string.Empty;
        bool colourless = ColourlessInks.Contains(a);
        if (colourless != ColourlessInks.Contains(b))
        {
            return true;
        }

        return colourless
            ? Math.Abs(((int?)one["inkV"] ?? 0) - ((int?)other["inkV"] ?? 0)) >= OtherInkValue
            : a != b;
    }
}
