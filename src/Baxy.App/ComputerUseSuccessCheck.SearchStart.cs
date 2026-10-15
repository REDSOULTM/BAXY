using System.Globalization;
using System.Text.Json.Nodes;

namespace Baxy.App;

// The view a search started from (SearchStart): what it already showed is no result of the search.
internal static partial class ComputerUseSuccessCheck
{
    /// <summary>
    /// Ronda 24b (v1, falso éxito): the view a search started from, the look the sub-goal's first verified typing of the
    /// query was decided on (<see cref="ComputerUseSuccessCheck.ViewBeforeTyping"/>, recorded at the act). What that view already showed (a
    /// control by <see cref="ComputerUseSuccessCheck.PlaceKey"/>, a written line in the same zone, the title) is no place of the search's
    /// results: measured on a store, the home page's banner bearing the query (same runtime ids, same rect before and
    /// after) passed for a result while the Enter never reached the box. One exception, a filter in place (a library
    /// read by OCR, a list that narrows): the places already there count when, since the search started, something not
    /// bearing the query left the view and nothing not bearing it arrived. A carousel that turned brings new controls,
    /// so it is no filter. The box's own parts (a control inside a field holding the query) and an OCR's stray letters
    /// (at most two characters) arrive with any typing and are not counted as arrivals.
    /// </summary>
    internal sealed class SearchStart
    {
        private readonly HashSet<string> _places = new(StringComparer.Ordinal);
        private readonly Dictionary<string, HashSet<string>> _lines = new(StringComparer.Ordinal);
        private string _title = string.Empty;
        private bool _filtered;

        internal bool Filtered => _filtered;

        /// <summary>The view the search for <paramref name="folded"/> started from; null when the steps carry no
        /// verified typing of it or nothing was recorded before it (a view without a baseline judges as before).</summary>
        internal static SearchStart? Of(string folded, JsonObject view, JsonArray steps)
        {
            if (folded.Length == 0 || view["viewBeforeTyping"] is not JsonObject typings)
            {
                return null;
            }

            JsonObject? typing = steps.OfType<JsonObject>().FirstOrDefault(step => (bool?)step["ok"] == true
                && (string?)step["operation"] == "input.text.type"
                && Fold((string?)step["text"]).Trim(QuoteMarks).Contains(folded, StringComparison.Ordinal));
            if (typing is null
                || typings[((int?)typing["step"] ?? 0).ToString(CultureInfo.InvariantCulture)] is not JsonObject before
                || before["places"] is not JsonArray places)
            {
                return null;
            }

            var start = new SearchStart { _title = Fold((string?)before["title"]) };
            // Revision 1 of r24b (finding 4): a place is its seat (its runtime id; without one, its kind and rect). The
            // same seat read with another name (a counter «3 aplicaciones» to «1 aplicación», a text the window reused)
            // is neither a place that left nor one that arrived: a filter is judged on the seats alone.
            List<JsonObject> controlsNow = [.. (view["controls"] as JsonArray ?? []).OfType<JsonObject>()];
            var seatsNow = new HashSet<string>(controlsNow.Select(PlaceSeat), StringComparer.Ordinal);
            var seatsThen = new HashSet<string>(StringComparer.Ordinal);
            List<JsonObject> seen = [.. places.OfType<JsonObject>()];
            foreach (JsonObject place in seen)
            {
                string key = (string?)place["key"] ?? string.Empty;
                start._places.Add(key);
                seatsThen.Add((string?)place["seat"] ?? key);
            }

            // Revision 2 of r24b (P2, measured on the store's v1 look 5738): what goes away from inside the box's own
            // frame (a container that holds the box and is about as wide, its drop-down of past searches under it) or
            // from inside a pop-up window that closed narrows nothing: closing the box's drop-down is no filter.
            List<JsonNode> boxRegions = BoxRegions(seen, typing, seatsNow);
            int leftLines = 0;
            List<JsonObject> gonePlaces = [];
            foreach (JsonObject place in seen)
            {
                string seat = (string?)place["seat"] ?? (string?)place["key"] ?? string.Empty;
                if ((bool?)place["reserved"] != true && (string?)place["kind"] is not ("Edit" or "ComboBox" or "Document")
                    && !((string?)place["says"] ?? string.Empty).Contains(folded, StringComparison.Ordinal) && !seatsNow.Contains(seat)
                    && !boxRegions.Any(region => Inside(place["rect"], region)))
                {
                    gonePlaces.Add(place);
                }
            }

            // What left is read where the query shows: in the tree when a control bears it, else in the written lines
            // (an OCR that drops a line between two looks narrows nothing the tree shows). What arrived is read the
            // same way: an OCR's re-reading of a page whose tree bears the query tells nothing of a filter.
            bool treeBears = ComparedControls(view).Any(control => (string?)control["kind"] is not ("Edit" or "ComboBox" or "Document")
                && PlaceSays(control).Contains(folded, StringComparison.Ordinal));

            // The parts of a field that holds the query (its clear button, its magnifier) come with the typing.
            List<JsonObject> fields = [.. controlsNow
                .Where(control => (string?)control["kind"] is "Edit" or "ComboBox" or "Document"
                    && Fold((string?)control["value"]).Contains(folded, StringComparison.Ordinal))];
            // Revision 2 of r24b (P1): what a narrowed list uncovered was there already, below it (Uncovered).
            List<JsonObject> kept = [.. controlsNow.Where(control => seatsThen.Contains(PlaceSeat(control)))];
            bool cut = (bool?)before["cut"] == true
                || ((int?)before["windowBottom"] is int bottom && gonePlaces.Any(place => Bottom(place["rect"]) >= bottom - 2));
            // Revision 3 of r24b (finding 2): a filter narrows the list its result is in. What left counts only when it
            // was a row of that list: of the kind of a place bearing the query that stayed (same seat), lined up with
            // it. A tooltip, a toast or a menu that closed is no row of it.
            List<JsonObject> bearers = [.. ComparedControls(view).Where(control =>
                (string?)control["kind"] is not ("Edit" or "ComboBox" or "Document")
                && PlaceSays(control).Contains(folded, StringComparison.Ordinal) && seatsThen.Contains(PlaceSeat(control)))];
            // Revision 4 of r24b (finding 1, measured on v1's own look 5738 with the carousel half turned): sharing rows
            // alone makes no row of the list. A home page's tiles share rows with its banner across a mosaic; a slide that
            // went while the next one was not yet shown passed for a narrowed list. Lined up is sharing the bearer's
            // columns (a list's rows stack under one another), or lying with it inside a list container that stayed
            // (a List, a DataGrid, a Table or a Tree: a grid of results wraps its rows across).
            List<JsonObject> lists = [.. seen.Where(place => (string?)place["kind"] is "List" or "DataGrid" or "Table" or "Tree"
                && place["rect"] is JsonObject && seatsNow.Contains((string?)place["seat"] ?? string.Empty))];
            Dictionary<string, JsonNode?> rectsThen = seen
                .GroupBy(place => (string?)place["seat"] ?? (string?)place["key"] ?? string.Empty, StringComparer.Ordinal)
                .ToDictionary(group => group.Key, group => group.First()["rect"], StringComparer.Ordinal);
            int left = gonePlaces.Count(place => bearers.Any(bearer =>
                (string?)bearer["kind"] == (string?)place["kind"]
                && (SharesColumns(bearer["rect"], place["rect"])
                    || lists.Any(list => Inside(place["rect"], list["rect"])
                        && (Inside(bearer["rect"], list["rect"])
                            || Inside(rectsThen.GetValueOrDefault(PlaceSeat(bearer)), list["rect"]))))));
            // Revision 3 of r24b (finding 1): what a filter adds about its results (a header over them, a counter with a
            // new id) is no arrival: of a kind none of what left was, and lying over the results that stayed or where
            // nothing left. A control of a kind that left, or one born where something left, turned the view.
            var goneKinds = new HashSet<string>(gonePlaces.Select(place => (string?)place["kind"] ?? string.Empty), StringComparer.Ordinal);
            bool arrived = ComparedControls(view).Any(control =>
                (string?)control["kind"] is not ("Edit" or "ComboBox" or "Document")
                && !PlaceSays(control).Contains(folded, StringComparison.Ordinal)
                && !seatsThen.Contains(PlaceSeat(control))
                && !fields.Any(field => Inside(control["rect"], field["rect"]))
                && !(cut && Uncovered(control, gonePlaces, kept))
                && !(left > 0 && !goneKinds.Contains((string?)control["kind"] ?? string.Empty)
                    && (OverTheResults(control, bearers) || !gonePlaces.Any(place => Overlaps(place["rect"], control["rect"])))));
            if (before["zones"] is JsonObject zones)
            {
                foreach ((string zone, JsonNode? lines) in zones)
                {
                    start._lines[zone] = new HashSet<string>(
                        (lines as JsonArray ?? []).Select(line => (string?)line ?? string.Empty), StringComparer.Ordinal);
                }

                if (view["text"] is JsonObject read)
                {
                    foreach ((string zone, JsonNode? lines) in read)
                    {
                        HashSet<string> then = start._lines.GetValueOrDefault(zone) ?? new HashSet<string>(StringComparer.Ordinal);
                        List<string> shown = [.. (lines as JsonArray ?? []).Select(line => Fold((string?)line)).Where(line => line.Length > 0)];
                        // The zone's lines that are gone, each once: a new line that re-reads one of them (the same
                        // letters, a counter's digits or an OCR's stray marks aside) takes it and is no arrival.
                        List<string> gone = [.. then.Where(line => !shown.Contains(line, StringComparer.Ordinal)
                            && !line.Contains(folded, StringComparison.Ordinal))];
                        int echoes = 0;
                        int born = 0;
                        foreach (string line in shown.Where(line => !then.Contains(line)))
                        {
                            if (EchoLine(line, folded))
                            {
                                echoes++;
                                continue;
                            }

                            if (line.Contains(folded, StringComparison.Ordinal) || line.Count(character => !char.IsWhiteSpace(character)) <= 2)
                            {
                                continue;
                            }

                            int reread = gone.FindIndex(old => SameReading(old, line));
                            if (reread >= 0)
                            {
                                gone.RemoveAt(reread);
                            }
                            else
                            {
                                born++;
                            }
                        }

                        // A box's own line (its placeholder) gives way to the query it now repeats: one line for one echo.
                        int goneHere = Math.Max(0, gone.Count - echoes);
                        leftLines += goneHere;
                        // Revision 3 of r24b (finding 1): a zone whose new lines are at least as many as the lines it lost
                        // turned (a carousel's next slide); one that lost more than it gained narrowed, and what it gained
                        // is said about the results (a header «Resultados…» over them). New lines where nothing left are
                        // no turn either.
                        if (!treeBears && born > 0 && goneHere > 0 && born >= goneHere)
                        {
                            arrived = true;
                        }
                    }

                    leftLines += start._lines.Where(zone => read[zone.Key] is null)
                        .Sum(zone => zone.Value.Count(line => !line.Contains(folded, StringComparison.Ordinal)));
                }
            }

            start._filtered = (left + (treeBears ? 0 : leftLines)) > 0 && !arrived;
            return start;
        }

        /// <summary>The control was on the view the search started from (a filter in place keeps it a place).</summary>
        internal bool OldPlace(JsonObject control) => !_filtered && _places.Contains(PlaceKey(control));

        /// <summary>The written line was in the same zone of the view the search started from.</summary>
        internal bool OldLine(string zone, string foldedLine) =>
            !_filtered && _lines.TryGetValue(zone, out HashSet<string>? lines) && lines.Contains(foldedLine);

        /// <summary>The window bore this title when the search started.</summary>
        internal bool OldTitle(string foldedTitle) => !_filtered && _title.Length > 0 && _title == foldedTitle;

        /// <summary>
        /// Revision 1 of r24b (finding 4): two folded lines of one zone are one reading of the same place when their
        /// letters differ in at most two (a counter «todos (12)» read «todos (1/12)», «juegos recientes» read «juegos
        /// recientes >», an OCR's «bl» for «bi»). Digits and marks never tell two places apart here.
        /// </summary>
        internal static bool SameReading(string old, string now)
        {
            string a = new([.. old.Where(char.IsLetter)]);
            string b = new([.. now.Where(char.IsLetter)]);
            if (a.Length < 3 || b.Length < 3 || Math.Abs(a.Length - b.Length) > 2)
            {
                return false;
            }

            int[] previous = [.. Enumerable.Range(0, b.Length + 1)];
            for (int i = 1; i <= a.Length; i++)
            {
                int[] current = new int[b.Length + 1];
                current[0] = i;
                for (int j = 1; j <= b.Length; j++)
                {
                    current[j] = Math.Min(Math.Min(current[j - 1] + 1, previous[j] + 1), previous[j - 1] + (a[i - 1] == b[j - 1] ? 0 : 1));
                }

                previous = current;
            }

            return previous[b.Length] <= 2;
        }

        /// <summary>
        /// Revision 2 of r24b (P2): the regions of the view a search started from whose leaving narrows nothing: the
        /// box's own frame (a container holding the field the typing went into, at most a quarter wider than it: the
        /// field and its drop-down) and each pop-up window that is gone now. The field is named by the typing's «into»;
        /// without such a name, every field of that view is a box.
        /// </summary>
        private static List<JsonNode> BoxRegions(List<JsonObject> then, JsonObject typing, HashSet<string> seatsNow)
        {
            string into = Fold((string?)typing["into"]).Trim();
            List<JsonObject> boxes = [.. then.Where(place => (string?)place["kind"] is "Edit" or "ComboBox" or "Document"
                && place["rect"] is JsonObject)];
            if (into.Length > 0 && boxes.Any(box => (string?)box["name"] == into))
            {
                boxes = [.. boxes.Where(box => (string?)box["name"] == into)];
            }

            var regions = new List<JsonNode>();
            foreach (JsonObject place in then.Where(place => place["rect"] is JsonObject))
            {
                JsonNode rect = place["rect"]!;
                bool frame = (string?)place["kind"] is not ("Edit" or "ComboBox" or "Document")
                    && boxes.Any(box => Inside(box["rect"], rect) && Width(rect) * 4 <= Width(box["rect"]) * 5);
                bool closedPopup = (string?)place["kind"] == "Window"
                    && !seatsNow.Contains((string?)place["seat"] ?? string.Empty);
                if (frame || closedPopup)
                {
                    regions.Add(rect);
                }
            }

            return regions;
        }

        /// <summary>
        /// Revision 2 of r24b (P1): a control that a narrowed list uncovered rather than one the search brought: it lies
        /// where places of the list went away (at or below the top of one it shares columns with), below every place
        /// that stayed in its columns (it came up from under the list; a container holding it is no such place), and
        /// it is of no kind those places that went were (a row of the list's own kind not bearing the query means the
        /// list did not narrow to it). Asked only when the view the search started from did not show it all (its
        /// listing cut, or a place that went reached the window's bottom edge).
        /// </summary>
        private static bool Uncovered(JsonObject control, List<JsonObject> gone, List<JsonObject> kept)
        {
            if (control["rect"] is not JsonObject rect || (int?)rect["y"] is not int top)
            {
                return false;
            }

            List<JsonObject> over = [.. gone.Where(place => SharesColumns(place["rect"], rect))];
            return over.Count > 0
                && !over.Any(place => (string?)place["kind"] == (string?)control["kind"])
                && top >= over.Min(place => (int?)place["rect"]!["y"] ?? int.MaxValue)
                && kept.Where(place => SharesColumns(place["rect"], rect) && !Inside(rect, place["rect"]))
                    .All(place => top >= Bottom(place["rect"]));
        }

        private static bool SharesColumns(JsonNode? a, JsonNode? b) =>
            a is JsonObject one && b is JsonObject two
            && (int?)one["x"] is int x1 && (int?)one["w"] is int w1 && (int?)two["x"] is int x2 && (int?)two["w"] is int w2
            && x1 < x2 + w2 && x2 < x1 + w1;

        private static bool Overlaps(JsonNode? a, JsonNode? b) =>
            a is JsonObject one && b is JsonObject two && SharesColumns(one, two)
            && (int?)one["y"] is int y1 && (int?)one["h"] is int h1 && (int?)two["y"] is int y2 && (int?)two["h"] is int h2
            && y1 < y2 + h2 && y2 < y1 + h1;

        // Revision 3 of r24b: a control lying over the results that stayed: above every one of them in its columns
        // (and in the columns of one at least), as a header or a counter of a search sits.
        private static bool OverTheResults(JsonObject control, List<JsonObject> bearers)
        {
            List<JsonObject> under = [.. bearers.Where(bearer => SharesColumns(bearer["rect"], control["rect"]))];
            return under.Count > 0 && under.All(bearer => Bottom(control["rect"]) <= ((int?)bearer["rect"]?["y"] ?? int.MinValue));
        }

        private static int Bottom(JsonNode? rect) => ((int?)rect?["y"] ?? 0) + ((int?)rect?["h"] ?? 0);

        private static int Width(JsonNode? rect) => (int?)rect?["w"] ?? 0;

        private static bool Inside(JsonNode? inner, JsonNode? outer) =>
            inner is JsonObject a && outer is JsonObject b
            && (int?)a["x"] >= (int?)b["x"] && (int?)a["y"] >= (int?)b["y"]
            && (int?)a["x"] + (int?)a["w"] <= (int?)b["x"] + (int?)b["w"]
            && (int?)a["y"] + (int?)a["h"] <= (int?)b["y"] + (int?)b["h"];
    }
}
