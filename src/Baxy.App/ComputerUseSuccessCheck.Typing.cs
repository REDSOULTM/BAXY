using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json.Nodes;

namespace Baxy.App;

// Text put in by the mission: whether typed text arrived and shows, whether it was sent, and whether a paste landed.
internal static partial class ComputerUseSuccessCheck
{
    // The text a typing step sent, seen in the focused field when that field shows its content; a field that does
    // not expose it (measured: Discord's editor) or a password cannot be read and the accepted keys stand.
    internal static bool TypedTextShows(JsonObject step, JsonObject view)
    {
        string typed = Fold(((string?)step["text"] ?? string.Empty).Trim().Trim('"', '«', '»', '“', '”'));
        if (typed.Length == 0)
        {
            return true;
        }

        // The field the step named (set by its label, the focus untouched, so the focus may be another field): that
        // field holding the text shows it; its cut value cannot show text at its end.
        JsonArray controls = view["controls"] as JsonArray ?? [];
        string field = Fold((string?)step["field"]).Trim(' ', ':');
        if (field.Length > 0)
        {
            foreach (JsonObject control in controls.OfType<JsonObject>())
            {
                if ((string?)control["kind"] is "Edit" or "Document" or "ComboBox"
                    && Fold((string?)control["name"]).Trim(' ', ':') == field
                    && control["value"] is JsonValue named && named.TryGetValue(out string? inField))
                {
                    return inField.Length >= TypedValueCut || Fold(inField).Contains(typed, StringComparison.Ordinal);
                }
            }
        }

        if (view["window"]?["focused"] is JsonObject focused
            && (string?)focused["kind"] is "Edit" or "Document"
            && focused["value"] is JsonValue value && value.TryGetValue(out string? held))
        {
            // The worker cuts a value at 120 characters: a cut value cannot show text typed at its end.
            return held.Length >= TypedValueCut || Fold(held).Contains(typed, StringComparison.Ordinal);
        }

        if (FocusedIsPassword(view))
        {
            // A password shows dots, never the text: the accepted keys stand (as they did before the written-text rule).
            return true;
        }

        // What the view showed right before this step (recorded at the act): text already on screen then is no proof
        // of the typing (review r2 texto-webview: a contact typed by name passed on the same name already in the chat list).
        JsonObject? before = view["viewBeforeTyping"]?[((int?)step["step"] ?? 0).ToString(CultureInfo.InvariantCulture)] as JsonObject;

        // cu-v3 texto-webview (live wa-1): the keys went to a window whose focus is no field (a frame's pane over a
        // WebView2), Windows accepted them and the step passed while the search box kept its placeholder. Where the
        // focus does not show its content, a field of the view that holds the text more times than before the step
        // shows it (a cut value that changed may hold it past the cut); else the view's written text must show the
        // typed text's start or end more times than before. Only a view that writes nothing (Discord's editor, no
        // text read) leaves the accepted keys standing.
        JsonArray beforeFields = before?["fields"] as JsonArray ?? [];
        foreach (JsonObject control in controls.OfType<JsonObject>())
        {
            if ((string?)control["kind"] is not ("Edit" or "Document" or "ComboBox")
                || control["value"] is not JsonValue shown || !shown.TryGetValue(out string? text))
            {
                continue;
            }

            string name = (string?)control["name"] ?? string.Empty;
            string kind = (string?)control["kind"] ?? string.Empty;
            string? earlier = beforeFields.OfType<JsonObject>()
                .Where(other => (string?)other["name"] == name && (string?)other["kind"] == kind)
                .Select(other => (string?)other["value"]).FirstOrDefault();
            if (Occurrences(Fold(text), typed) > Occurrences(Fold(earlier), typed)
                || (before is not null && text.Length >= TypedValueCut && !string.Equals(text, earlier, StringComparison.Ordinal)))
            {
                return true;
            }
        }

        JsonArray lines = TextLines(view);
        if (lines.Count == 0)
        {
            return true;
        }

        string squeezedTyped = Squeezed(typed);
        if (squeezedTyped.Length == 0)
        {
            // Only punctuation or spaces: the reading drops them.
            return true;
        }

        // The lines joined: a text wrapped over lines the reading keeps apart is read whole.
        string now = Squeezed(string.Concat(lines.Select(line => (string?)line ?? string.Empty)));
        string then = Squeezed(string.Concat((before?["text"] as JsonArray ?? []).Select(line => (string?)line ?? string.Empty)));
        string start = squeezedTyped.Length > TypedShownStart ? squeezedTyped[..TypedShownStart] : squeezedTyped;
        string end = squeezedTyped.Length > TypedShownStart ? squeezedTyped[^TypedShownStart..] : squeezedTyped;
        return Occurrences(now, start) > Occurrences(then, start) || Occurrences(now, end) > Occurrences(then, end);
    }

    // Ronda 24b: the marker of a free text written (missions.WRITTEN_CHECK).
    internal const string WrittenMarker = "written";

    /// <summary>
    /// Ronda 24b (banco r23 c6: the Enter fell on the search holding «prueba BAXY C6» and «lo envié» was said): the text
    /// <paramref name="text"/> was sent by the sub-goal's Enter. Against the view right before that Enter
    /// («viewBeforeEnter», <see cref="ViewBeforeEnter"/>). Revisión 2 (B3): the field that took the text («into», the
    /// mission's last typing) is read first: still holding it, nothing was sent, whatever another field lost. A field
    /// that held the text and is now empty proves a send only when it is no search (<see cref="ComputerUseMission.SearchField"/>,
    /// or the receipt's «intoSearch» for the field that took it): an Enter in a search empties it on opening its first
    /// result and sends nothing. A text typed into a search that no message box lost was not sent. With no typing of the
    /// mission to tell the field, any field still holding it says nothing was sent. Revisión 2 (B2): the text compared
    /// is the one really typed (the last typing's «text», «typed»), never the phrase's place that came with it («hola en
    /// la caja de mensaje»). Revisión 1 (B2): read only as written text (a WebView2 frame with no field value, the live
    /// wa-1), the text shown more times than before the Enter is sent; shown before and no more after with the written
    /// text otherwise changed (the box back to its placeholder, the message in a bubble with its hour) is ambiguous and
    /// the Enter stands as its receipt; only a look the Enter left unchanged, or one that never showed the text, says
    /// nothing was sent. A view that reads neither (an editor with no value and no written text) leaves the Enter as the
    /// receipt it was.
    /// </summary>
    internal static bool Sent(string text, JsonObject view, JsonArray steps)
    {
        string typed = Fold(text.Trim().Trim('"', '«', '»', '“', '”')).Trim();
        JsonObject? enter = steps.OfType<JsonObject>().LastOrDefault(step =>
            (bool?)step["ok"] == true && (string?)step["operation"] == "input.key.press" && Fold((string?)step["key"]) == "enter");
        if (typed.Length == 0 || enter is null)
        {
            return typed.Length == 0 && enter is not null;
        }

        JsonObject? before = view["viewBeforeEnter"]?[((int?)enter["step"] ?? 0).ToString(CultureInfo.InvariantCulture)] as JsonObject;
        if (before is null)
        {
            // No look before the Enter was kept: the Enter stands as the receipt it was.
            return true;
        }

        // «escribí hola en la caja de mensaje y mandalo»: the act typed «hola» (the place read off), the atom says the
        // whole phrase; what was keyed is what a field holds and a bubble shows.
        if (Fold((string?)before["typed"]).Trim() is { Length: > 0 } keyed && typed.Contains(keyed, StringComparison.Ordinal))
        {
            typed = keyed;
        }

        JsonArray controls = view["controls"] as JsonArray ?? [];
        string into = Fold((string?)before["into"]).Trim();
        bool intoSearch = (bool?)before["intoSearch"] == true;
        bool intoKept = false;
        bool anyKept = false;
        bool composerEmptied = false;
        foreach (JsonObject held in (before["fields"] as JsonArray ?? []).OfType<JsonObject>())
        {
            if (!Fold((string?)held["value"]).Contains(typed, StringComparison.Ordinal))
            {
                continue;
            }

            JsonObject? now = controls.OfType<JsonObject>().FirstOrDefault(control =>
                (string?)control["kind"] == (string?)held["kind"] && (string?)control["name"] == (string?)held["name"]);
            if (now?["value"] is not JsonValue shown || !shown.TryGetValue(out string? value))
            {
                continue;
            }

            bool isInto = into.Length > 0 && Fold((string?)held["name"]).Trim() == into;
            if (Fold(value).Contains(typed, StringComparison.Ordinal))
            {
                anyKept = true;
                intoKept |= isInto;
                continue;
            }

            // A field that held the text and was emptied by the Enter sent it, unless it is a search.
            composerEmptied |= !(isInto && intoSearch) && !ComputerUseMission.SearchField(now, view);
        }

        if (intoKept)
        {
            // The text still in the field it was typed into (a search keeps its query after Enter) was not sent.
            return false;
        }

        if (composerEmptied)
        {
            return true;
        }

        if ((anyKept && into.Length == 0) || intoSearch)
        {
            // With no typing of the mission to tell that field, the field still holding it says nothing was sent; a text
            // typed into a search that no message box lost was never a message.
            return false;
        }

        string squeezed = Squeezed(typed);
        JsonArray lines = TextLines(view);
        if (squeezed.Length == 0 || lines.Count == 0)
        {
            return true;
        }

        string nowText = Squeezed(string.Concat(lines.Select(line => (string?)line ?? string.Empty)));
        string thenText = Squeezed(string.Concat((before["text"] as JsonArray ?? []).Select(line => (string?)line ?? string.Empty)));
        int nowCount = Occurrences(nowText, squeezed);
        int thenCount = Occurrences(thenText, squeezed);
        if (nowCount > thenCount)
        {
            return true;
        }

        // Never shown, before or after: no message in the conversation. Shown before (the text in its box) and the look
        // unchanged by the Enter: it stayed where it was. Otherwise the reading cannot tell the box from the bubble.
        return thenCount > 0 && !string.Equals(nowText, thenText, StringComparison.Ordinal);
    }

    /// <summary>
    /// Ronda 24b: what the view showed right before an Enter (<see cref="ViewBeforeTyping"/>) and, revisión 1 (B1),
    /// «into»: the field the mission's last text was typed into (its receipt), the one field whose keeping the text says
    /// it was not sent. Revisión 2: «intoSearch», that field was a search by the receipt; «typed», the text really typed.
    /// </summary>
    internal static JsonObject ViewBeforeEnter(JsonObject? view, JsonArray? steps)
    {
        JsonObject look = ViewBeforeTyping(view);
        JsonObject? typed = (steps ?? []).OfType<JsonObject>().LastOrDefault(step =>
            (string?)step["operation"] == "input.text.type" && (bool?)step["ok"] == true);
        if ((string?)typed?["into"] is { Length: > 0 } into)
        {
            look["into"] = into;
            if ((bool?)typed["intoSearch"] == true)
            {
                look["intoSearch"] = true;
            }
        }

        if ((string?)typed?["text"] is { Length: > 0 } keyed)
        {
            look["typed"] = keyed;
        }

        return look;
    }

    /// <summary>What the view showed right before a typing step, for <see cref="TypedTextShows"/>: its written text and
    /// the values of its fields.</summary>
    internal static JsonObject ViewBeforeTyping(JsonObject? view)
    {
        var fields = new JsonArray();
        foreach (JsonObject control in (view?["controls"] as JsonArray ?? []).OfType<JsonObject>())
        {
            if ((string?)control["kind"] is "Edit" or "Document" or "ComboBox"
                && control["value"] is JsonValue shown && shown.TryGetValue(out string? text))
            {
                fields.Add(new JsonObject
                {
                    ["kind"] = (string?)control["kind"],
                    ["name"] = (string?)control["name"] ?? string.Empty,
                    ["value"] = text,
                });
            }
        }

        // Ronda 24: the window's title too, so a paste's look tells the same window from the one an opening brought.
        var before = new JsonObject
        {
            ["text"] = view is null ? new JsonArray() : TextLines(view),
            ["fields"] = fields,
            ["title"] = (string?)view?["window"]?["title"],
            ["process"] = (string?)view?["window"]?["process"],
            // Review 3 of ronda 24: the view's signature (ComputerUseMission.ViewSignature), hashed, so a paste key's look
            // tells any change of the same window (PasteLanded).
            ["signature"] = view is null ? null : SignatureHash(view),
        };
        if (view is not null)
        {
            // Ronda 24b (v1): the places this view showed, for the search the typing starts (SearchStart).
            var places = new JsonArray();
            foreach (JsonObject control in (view["controls"] as JsonArray ?? []).OfType<JsonObject>())
            {
                places.Add(new JsonObject
                {
                    ["key"] = PlaceKey(control),
                    ["seat"] = PlaceSeat(control),
                    ["says"] = PlaceSays(control),
                    ["kind"] = (string?)control["kind"] ?? string.Empty,
                    ["reserved"] = (bool?)control["reserved"] == true,
                    // Revision 2 of r24b: where it lay and what it is named, for the box's own frame, a pop-up that
                    // closed and what a narrowed list uncovered (SearchStart).
                    ["name"] = Fold((string?)control["name"]).Trim(),
                    ["rect"] = control["rect"]?.DeepClone(),
                });
            }

            before["places"] = places;
            // Revision 2 of r24b (P1): whether this view showed all there was: its listing cut (more controls than it
            // listed) and the window's bottom edge, below which a list taller than the window went on.
            before["cut"] = (int?)view["controlCount"] > places.Count;
            if (view["window"]?["rect"] is JsonObject frame && (int?)frame["y"] is int top && (int?)frame["h"] is int height)
            {
                before["windowBottom"] = top + height;
            }
            if (view["text"] is JsonObject zones)
            {
                var read = new JsonObject();
                foreach ((string zone, JsonNode? lines) in zones)
                {
                    read[zone] = new JsonArray([.. (lines as JsonArray ?? []).Select(line => Fold((string?)line))
                        .Where(line => line.Length > 0).Select(line => (JsonNode?)JsonValue.Create(line))]);
                }

                before["zones"] = read;
            }
        }

        return before;
    }

    private static string SignatureHash(JsonObject view) =>
        Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(ComputerUseMission.ViewSignature(view))), 0, 8);

    private static bool FocusedIsPassword(JsonObject view) =>
        ((string?)view["window"]?["focused"]?["state"] ?? string.Empty).Contains("password", StringComparison.Ordinal)
        || (view["controls"] as JsonArray ?? []).OfType<JsonObject>().Any(control =>
            ((string?)control["state"] ?? string.Empty).Split(' ') is var states
            && states.Contains("focused") && states.Contains("password"));

    private static int Occurrences(string text, string piece)
    {
        int count = 0;
        for (int at = text.IndexOf(piece, StringComparison.Ordinal); at >= 0; at = text.IndexOf(piece, at + 1, StringComparison.Ordinal))
        {
            count++;
        }

        return count;
    }

    // Written text is read with its spaces and punctuation dropped (the reading may join or split words and misread
    // «¿» or «,») and by the typed text's start or end (a long text wraps, a one-line field scrolls to its end).
    private static string Squeezed(string text) =>
        new(text.Where(char.IsLetterOrDigit).ToArray());

    private const int TypedValueCut = 120;
    private const int TypedShownStart = 24;

    /// <summary>Ronda 24: a key that puts the clipboard where the keyboard is (data «computerUse.contentKeys.paste»).</summary>
    internal static bool PasteKey(string? key) =>
        OperationFloor.ContentKeyClass("paste").Contains(Fold(key).Trim().Replace(' ', '_'));

    /// <summary>
    /// Ronda 24 (pasada r23 t-menu-4: an Enter after which the view was identical counted as the act with an effect): a
    /// verified key the first look after it found with the window's signature unchanged (<c>sameView</c>) did nothing a
    /// look sees. A copy key (data «computerUse.contentKeys.copy») never shows on the window: its effect is the
    /// clipboard, which BAXY never reads, so it is never «as it was». Twin of the mind's key_left_the_view_as_it_was.
    /// </summary>
    internal static bool KeyLeftTheViewAsItWas(JsonObject step)
    {
        if ((bool?)step["sameView"] != true)
        {
            return false;
        }

        // Review 4 of ronda 24 (the Terminal's Enter that ran a command, the arrow that brought it back, a Ctrl+V into
        // its console: the console text is no control's value, so the signature kept): a key whose effect lands where
        // the signature does not look (data «computerUse.contentKeys.unseenEffect») left the view as it was only when
        // its effect would land on the written text («writtenEffect») and the App read that text the same too
        // (sameText). A caret, selection, clipboard, save or undo key never does.
        string key = Fold((string?)step["key"]).Trim().Replace(' ', '_');
        if (OperationFloor.ContentKeyClass("copy").Contains(key))
        {
            return false;
        }

        return !OperationFloor.ContentKeyClass("unseenEffect").Contains(key)
            || (OperationFloor.ContentKeyClass("writtenEffect").Contains(key) && (bool?)step["sameText"] == true);
    }

    /// <summary>
    /// Ronda 24 (pasada r23 t-long-1: Ctrl+V accepted 84 ms after an application opened, the tab left with «0
    /// caracteres» and the sub-goal closed on the receipt): a paste key's act shows on the look after it. True for any
    /// other key. On receipts alone (no look) it waits for the look; a key the window answered with the same view put
    /// nothing. The focused field's or document's value, when the focus shows one, must hold something and differ
    /// from that field's value right before the key (<see cref="ViewBeforeTyping"/>, recorded at the act); a cut value
    /// equal to before, or a focus showing no value, leaves the same window (its title) with a field's value or its
    /// written text changed. The clipboard itself is never read. Review 1 of ronda 24 (finding 3: the application opened
    /// on a restored tab already holding text, the look before the key the calculator's): the focused value proves the
    /// paste only when the look before the key was of the same window (<see cref="SameWindowAsBefore"/>); a value that
    /// was already there when the window came up is no paste. Review 3 of ronda 24: past the focused value, the same
    /// window with its view's signature changed since right before the key (any control's name, state or value, the
    /// title) shows the paste.
    /// </summary>
    internal static bool PasteLanded(JsonObject step, JsonObject view)
    {
        if (!PasteKey((string?)step["key"]))
        {
            return true;
        }

        if ((view["window"] is null && view["controls"] is null) || KeyLeftTheViewAsItWas(step))
        {
            return false;
        }

        JsonObject? before = view["viewBeforeTyping"]?[((int?)step["step"] ?? 0).ToString(CultureInfo.InvariantCulture)] as JsonObject;
        JsonArray beforeFields = before?["fields"] as JsonArray ?? [];
        string? Earlier(JsonObject field) => beforeFields.OfType<JsonObject>()
            .Where(other => (string?)other["name"] == ((string?)field["name"] ?? string.Empty) && (string?)other["kind"] == (string?)field["kind"])
            .Select(other => (string?)other["value"]).FirstOrDefault();
        if (SameWindowAsBefore(before, view)
            && view["window"]?["focused"] is JsonObject focused
            && (string?)focused["kind"] is "Edit" or "Document" or "ComboBox"
            && focused["value"] is JsonValue shown && shown.TryGetValue(out string? held))
        {
            string? earlier = Earlier(focused);
            if (held.Length < TypedValueCut || !string.Equals(held, earlier, StringComparison.Ordinal))
            {
                return held.Trim().Length > 0 && !string.Equals(held, earlier, StringComparison.Ordinal);
            }
        }

        if (!SameWindowAsBefore(before, view))
        {
            return false;
        }

        // Review 3 of ronda 24: in the same window (a title an edit marks as modified included), a paste the focused
        // value cannot show (a document past the worker's cut, an editor that exposes no value, a sheet's cell) shows
        // on the view's signature (title, controls' names, states and values): the signature recorded right before the
        // key differs from the one after it. Without a recorded signature, the first look after the key compared it
        // (an unchanged one marked the step sameView, refused above).
        if ((string?)before!["signature"] is not { } signatureBefore
            || !string.Equals(signatureBefore, SignatureHash(view), StringComparison.Ordinal))
        {
            return true;
        }

        bool fieldChanged = (view["controls"] as JsonArray ?? []).OfType<JsonObject>().Any(control =>
            (string?)control["kind"] is "Edit" or "Document" or "ComboBox"
            && control["value"] is JsonValue value && value.TryGetValue(out string? now)
            && Earlier(control) is { } then && !string.Equals(now, then, StringComparison.Ordinal));
        return fieldChanged
            || !TextLines(view).Select(line => (string?)line).SequenceEqual(
                (before["text"] as JsonArray ?? []).Select(line => (string?)line), StringComparer.Ordinal);
    }

    /// <summary>
    /// Review 1 of ronda 24 (finding 3): whether the look recorded right before a key (<see cref="ViewBeforeTyping"/>)
    /// was of the window the look after it shows: the same title, or the same process when the look recorded one (a
    /// title an edit marks as modified stays the same window). No look before, or another window, is no comparison.
    /// </summary>
    private static bool SameWindowAsBefore(JsonObject? before, JsonObject view)
    {
        if (before is null)
        {
            return false;
        }

        string process = Fold((string?)before["process"]).Trim();
        return string.Equals(Fold((string?)view["window"]?["title"]), Fold((string?)before["title"]), StringComparison.Ordinal)
            || (process.Length > 0 && string.Equals(Fold((string?)view["window"]?["process"]).Trim(), process, StringComparison.Ordinal));
    }
}
