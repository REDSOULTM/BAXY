using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json.Nodes;

namespace Baxy.App;

// Marks a look leaves for the next steps: what appeared, the same view, the window's surface and the signature.
internal static partial class ComputerUseMission
{
    /// <summary>
    /// What the last act made appear (a menu it opened, a page it loaded), read apart by the mind: <c>newText</c>
    /// against the previous look, and <c>newTextAfterClick</c>, what is on screen now and was not right before the
    /// sub-goal's last verified click (at most 12 lines). It is measured again on every look until the next step, then
    /// kept in the state (the click's effect is still what it was), and every view carries it, empty when no verified
    /// click was seen.
    /// </summary>
    internal static void NoteWhatAppeared(JsonObject state, JsonObject view, JsonArray currentText, JsonArray steps, int start)
    {
        int done = steps.Count - start;
        if (currentText.Count > 0)
        {
            if (done > 0 && state["lastText"] is JsonArray previousText)
            {
                var before = new HashSet<string>(previousText.Select(line => (string?)line ?? string.Empty), StringComparer.Ordinal);
                view["newText"] = new JsonArray([.. currentText
                    .Select(line => (string?)line ?? string.Empty)
                    .Where(line => !before.Contains(line))
                    .Take(12)
                    .Select(line => (JsonNode?)JsonValue.Create(line))]);
            }

            state["lastText"] = currentText.DeepClone();
        }

        // The last verified step of the sub-goal, with only failed steps after it (a click that failed after the click
        // that opened a menu leaves that menu the thing to read).
        JsonObject? last = null;
        for (int position = steps.Count - 1; position >= start && position >= 0; position--)
        {
            if (steps[position] is JsonObject candidate && (bool?)candidate["ok"] == true)
            {
                last = candidate;
                break;
            }
        }

        if (done > 0 && last is not null
            && (string?)last["operation"] == "input.visible.click"
            && ((int?)last["step"] ?? steps.Count) is int clickStep)
        {
            // Every look until the next step measures the click's effect against the text seen right before it: the
            // first look can come before the effect is drawn (a menu, a page still loading), a later one finds it.
            if (currentText.Count > 0
                && state["textBeforeClick"]?[clickStep.ToString(CultureInfo.InvariantCulture)] is JsonArray { Count: > 0 } beforeClick)
            {
                var before = new HashSet<string>(beforeClick.Select(line => (string?)line ?? string.Empty), StringComparer.Ordinal);
                state["newTextAfterClickStep"] = clickStep;
                state["newTextAfterClick"] = new JsonArray([.. currentText
                    .Select(line => (string?)line ?? string.Empty)
                    .Where(line => !before.Contains(line))
                    .Take(12)
                    .Select(line => (JsonNode?)JsonValue.Create(line))]);
            }
            else if ((int?)state["newTextAfterClickStep"] != clickStep)
            {
                // The text before the click is unknown: the first look after it says what it found new.
                state["newTextAfterClickStep"] = clickStep;
                state["newTextAfterClick"] = view["newText"] is JsonArray appeared ? appeared.DeepClone() : new JsonArray();
            }
        }

        view["newTextAfterClick"] = state["newTextAfterClick"] is JsonArray kept ? kept.DeepClone() : new JsonArray();
    }

    /// <summary>
    /// Teclas sin efecto (r9: v3-37, v3-39, v3-16): the first look after a verified act that keeps the view's
    /// signature (title, controls, states, values) says the act left the window as it was; the step is marked
    /// <c>sameView</c>. The mark is a fact about the signature, not a verdict: the mind reads it only on a key meant to
    /// bring something up (a typed text, a caret or clipboard key lands where the signature does not look). A look with
    /// the window behind (the person brought theirs up, or the Core gave it back) proves nothing either way and leaves
    /// the act unmarked.
    /// </summary>
    internal static void MarkSameView(
        JsonObject state, JsonArray steps, int start, string signature, bool lookedBehind, string? text = null)
    {
        if (steps.Count <= start || steps[^1] is not JsonObject acted || (int?)state["sameViewStep"] == steps.Count)
        {
            return;
        }

        state["sameViewStep"] = steps.Count;
        if ((bool?)acted["ok"] == true && !lookedBehind && state["lastSignature"] is not null
            && string.Equals(signature, (string?)state["lastSignature"], StringComparison.Ordinal))
        {
            acted["sameView"] = true;
            // Review 4 of ronda 24: the written text read too was the same as at the look before the act (both looks
            // read it): a key whose effect lands on the written text (data «computerUse.contentKeys.writtenEffect»)
            // left the view as it was only with this mark (ComputerUseSuccessCheck.KeyLeftTheViewAsItWas).
            if (text is not null && state["lastSignatureText"] is JsonValue lastText
                && lastText.TryGetValue(out string? previous) && string.Equals(text, previous, StringComparison.Ordinal))
            {
                acted["sameText"] = true;
            }
        }
    }

    // At most this many names that appeared are kept on a key's step.
    private const int AppearedNames = 32;

    // The kinds that are entries of a list or a tree, kept after the other controls that appeared.
    private static readonly HashSet<string> ListEntryKinds = new(StringComparer.Ordinal) { "ListItem", "DataItem", "TreeItem" };

    /// <summary>
    /// The names a verified act on the window (a key, a click, a text: an <c>input.</c> step, never an application
    /// opened, whose whole window is new) made appear: in the first look after it, in no control of the look before it
    /// (folded, at most <see cref="AppearedNames"/>, in the view's order, the entries of a list last), kept on the
    /// act's step as <c>appeared</c>.
    /// The mind presses a Cancel after its own Escape only when that Cancel came with its search key, never one the
    /// person's window already showed (review finding 2 of menus-teclas); the check atom <c>appeared:</c> reads it
    /// (a form opened by an act of the sub-goal, pasada r15b). Every look leaves its names for the next one.
    /// </summary>
    internal static void MarkAppeared(JsonObject state, JsonArray steps, int start, JsonObject view)
    {
        JsonArray names = ComputerUseSuccessCheck.ControlNames(view);
        if (steps.Count > start && steps[^1] is JsonObject acted && (int?)state["appearedStep"] != steps.Count
            && ((string?)acted["operation"])?.StartsWith("input.", StringComparison.Ordinal) == true
            && (bool?)acted["ok"] == true
            && state["lastControlNames"] is JsonArray before)
        {
            state["appearedStep"] = steps.Count;
            var known = new HashSet<string>(StringComparer.Ordinal);
            foreach (JsonNode? name in before)
            {
                if ((string?)name is { } seen)
                {
                    known.Add(seen);
                }
            }

            // Review of cierre-de-subobjetivos (finding 5): the entries of a list come after every other control, so a
            // font list's dozens of names never push a form's own field («Tamaño:») out of the names kept.
            var appeared = new JsonArray();
            bool onlyMenu = true;
            // Revision 1 of ronda 21: a control listed only for the goal's words came with the look, not with the act.
            List<JsonObject> controls = [.. ComputerUseSuccessCheck.ComparedControls(view)];
            foreach (bool entries in new[] { false, true })
            {
                foreach (JsonObject control in controls)
                {
                    string now = ComputerUseSuccessCheck.Fold((string?)control["name"]);
                    if (now.Length > 0 && ListEntryKinds.Contains((string?)control["kind"] ?? string.Empty) == entries
                        && appeared.Count < AppearedNames && known.Add(now))
                    {
                        appeared.Add((JsonNode?)JsonValue.Create(now));
                        onlyMenu &= ComputerUseSuccessCheck.MenuKinds.Contains((string?)control["kind"] ?? string.Empty);
                    }
                }
            }

            acted["appeared"] = appeared;
            // Encargo K (banco def1 x8): the keys' receipt counts what was sent, not what arrived; the look after a text
            // typed by the keyboard shows «125+75» as «25 +» «75». A word of the text shown only cut at its start is a
            // text that did not arrive whole: the final never says it was typed. Encargo TZ-DC3 (banco zt1 c6: Discord took
            // none of «prueba BAXY C6», its box stayed empty and the final said «antes de parar escribí «prueba BAXY C6»»):
            // nor a text this look does not show where it was typed (TypedTextShows, the sub-goal's own «written»).
            if ((string?)acted["operation"] == "input.text.type" && (string?)acted["method"] == "keyboard"
                && (ArrivedCut((string?)acted["text"], appeared) || !ComputerUseSuccessCheck.TypedTextShows(acted, view)))
            {
                acted["arrived"] = false;
            }

            if (appeared.Count > 0 && onlyMenu)
            {
                // Revision 2 of ronda 20b: all the act brought were the entries of a menu (a context menu opened on
                // an entry, a key that opened one): the window is where it was (ComputerUseSuccessCheck.MovedThePlace).
                acted["appearedOnlyMenu"] = true;
            }
        }

        state["lastControlNames"] = names;
    }

    /// <summary>
    /// Encargo K: whether the names a text made appear show one of its words (three characters or more) only cut at its
    /// start, as a word of their own («125» typed, «25» shown), and never whole. A number's thousands separator is not a
    /// cut («1000» shown «1.000»). Nothing shown of the text says nothing.
    /// </summary>
    internal static bool ArrivedCut(string? text, JsonArray appeared)
    {
        var shown = new HashSet<string>(StringComparer.Ordinal);
        foreach (string? name in appeared.Select(node => (string?)node))
        {
            shown.UnionWith(Words(ThousandsSeparator().Replace(ComputerUseSuccessCheck.Fold(name), string.Empty)));
        }

        return Words(ComputerUseSuccessCheck.Fold(text)).Any(word => word.Length >= 3 && !shown.Contains(word)
            && Enumerable.Range(1, word.Length - 2).Any(cut => shown.Contains(word[cut..])));

        static IEnumerable<string> Words(string folded) =>
            folded.Split(folded.Where(character => !char.IsLetterOrDigit(character)).Distinct().ToArray(),
                StringSplitOptions.RemoveEmptyEntries);
    }

    [System.Text.RegularExpressions.GeneratedRegex(@"(?<=\d)[.,\u00a0\u202f ](?=\d{3}(?!\d))")]
    private static partial System.Text.RegularExpressions.Regex ThousandsSeparator();

    /// <summary>
    /// Ronda 20 P6: the trace label of a look whose application's window showed only its chrome (the provider's
    /// «window.surface»): the step, whether its family's content window was read («above», «under») or why not, that
    /// window's extended style and owner. Null when the look says nothing of it.
    /// </summary>
    internal static string? SurfaceTrace(JsonObject view, int step)
    {
        if (view["window"]?["surface"] is not JsonObject surface || (string?)surface["reason"] is not { Length: > 0 } reason)
        {
            return null;
        }

        string exStyle = (string?)surface["exStyle"] ?? "0";
        long owner = surface["owner"] is not JsonValue value ? 0
            : value.TryGetValue(out long number) ? number
            : value.TryGetValue(out int small) ? small
            : 0;
        return string.Create(CultureInfo.InvariantCulture,
            $"step.{step}.{reason.ToLowerInvariant()}.ex.{exStyle.ToLowerInvariant()}.owner.{owner:x}");
    }

    // What the screen shows for «did it change»: the title and the controls; the
    // written text only on a window drawn without an accessible tree (≤ 1
    // control), where the provider reads it always. So a look taken with the
    // OCR text and one taken without it compare equal when nothing moved.
    internal static string ViewSignature(JsonObject view)
    {
        var parts = new StringBuilder();
        if (view["window"] is JsonObject window)
        {
            parts.Append((string?)window["title"]).Append('\n');
        }

        // Revision 1 of ronda 21: what a look listed only for the goal's words («reserved») is not part of what it shows
        // for «did it change»: the look before the sub-goal's first act carried no words.
        foreach (JsonObject item in ComputerUseSuccessCheck.ComparedControls(view))
        {
            parts.Append((string?)item["kind"]).Append('|').Append((string?)item["name"])
                .Append('|').Append((string?)item["state"]).Append('|').Append((string?)item["value"]).Append('\n');
        }

        if (ControlCount(view) <= 1 && view["text"] is JsonObject text)
        {
            parts.Append(text.ToJsonString());
        }

        return parts.ToString();
    }

    private static string Hash(string signature) =>
        Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(signature)), 0, 8);

    private static int ControlCount(JsonObject view) =>
        view["controls"] is JsonArray controls ? controls.Count : 0;

    private static int TextCount(JsonObject view)
    {
        int count = 0;
        if (view["text"] is JsonObject text)
        {
            foreach ((string _, JsonNode? zone) in text)
            {
                count += zone is JsonArray lines ? lines.Count : 0;
            }
        }

        return count;
    }
}
