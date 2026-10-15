using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;
using Baxy.Contracts;
using Baxy.Kernel.Operations;

namespace Baxy.App;

// The mission's final: what was observed, the excerpt of the screen it quotes, and the synthesized response.
internal static partial class ComputerUseMission
{
    private static JsonObject Observed(
        JsonObject state, JsonArray steps, bool reached, string? satisfiedBy, string? evidence, string? errorCode,
        JsonObject? lastView)
    {
        var told = new JsonArray();
        foreach (JsonNode? node in steps)
        {
            if (node?.DeepClone() is JsonObject step)
            {
                step.Remove(ViewHashField);
                // The title a step was decided on is the loop's own measure (MovedThePlace), never told.
                step.Remove("titleBefore");
                told.Add((JsonNode?)step);
            }
        }

        var observed = new JsonObject
        {
            ["goal"] = state["goal"]?.DeepClone(),
            ["application"] = state["application"]?.DeepClone(),
            ["reached"] = reached,
            ["successCheck"] = state["successCheck"]?.DeepClone(),
            ["stepCount"] = steps.Count,
            ["steps"] = told,
            ["window"] = state["window"]?.DeepClone(),
            ["joined"] = (bool?)state["joined"] == true,
            ["elapsedMs"] = (long?)state["elapsedMs"] ?? 0,
            ["modelMs"] = (long?)state["modelMs"] ?? 0,
            ["authority"] = "shell_loop_over_uia_ocr_postread",
        };
        if (!WindowAsked(state))
        {
            // Ronda 24 (pasada r23 t-drag-2): the window the last look read is no application the person said, nor one
            // the mission was tied or bound to, nor the one they pointed at: its title never names the place in the
            // final («No pude hacerlo en «Spotify Premium»» for a window nobody asked for).
            observed["windowAsked"] = false;
        }

        JsonArray plan = state["subgoals"] as JsonArray ?? [];
        if ((bool?)state["chained"] == true)
        {
            var subgoals = new JsonArray();
            foreach (JsonNode? node in plan)
            {
                // Ronda 23: the last sub-goal carries the mission's question to be read; the final tells the question
                // once, from the mission's goal, and each sub-goal by what it did.
                string? subgoalGoal = (string?)node?["goal"];
                int asked = subgoalGoal?.IndexOf(OperationFloor.QuestionMark, StringComparison.Ordinal) ?? -1;
                var said = new JsonObject
                {
                    ["goal"] = asked > 0 ? subgoalGoal![..asked] : subgoalGoal,
                    ["application"] = node?["application"]?.DeepClone(),
                    ["reached"] = (bool?)node?["reached"] == true,
                    ["stepCount"] = (int?)node?["stepCount"] ?? 0,
                    ["satisfiedBy"] = node?["satisfiedBy"]?.DeepClone(),
                    // Review r10a finding 1: the planned check, against which the floor tells an alias's arrival.
                    ["successCheck"] = node?["successCheck"]?.DeepClone(),
                };
                if (node?["numbers"] is JsonArray numbers)
                {
                    said["numbers"] = numbers.DeepClone();
                }

                if (node?["witness"] is JsonObject subgoalWitness)
                {
                    said["witness"] = subgoalWitness.DeepClone();
                }

                // Ronda 24b (x10): the place as the window wrote it, and whether the part acted to get there.
                if ((string?)node?["arrivedAs"] is { Length: > 0 } arrivedAs)
                {
                    said["arrivedAs"] = arrivedAs;
                }

                if (node?["acted"] is JsonValue acted)
                {
                    said["acted"] = (bool?)acted == true;
                }

                subgoals.Add((JsonNode?)said);
            }

            observed["subgoals"] = subgoals;
        }

        if (satisfiedBy is not null)
        {
            observed["satisfiedBy"] = satisfiedBy;
            // Ronda 24b (banco r23, e1): the measured witness of the term that closed the mission's last sub-goal.
            if (reached && plan.Count > 0 && plan[^1]?["witness"] is JsonObject witness)
            {
                observed["witness"] = witness.DeepClone();
            }

            // r30: a mission of one goal carries, as each part of a chain does above, how the window wrote what the
            // term that closed it read: its final names that, from the facts, and not the person's word for it.
            if (reached && plan.Count == 1 && (string?)plan[0]?["arrivedAs"] is { Length: > 0 } wrote)
            {
                observed["arrivedAs"] = wrote;
            }
        }

        // Ronda 24b (x7): an arrival a focused field proved (check atom focus:) only says the search opened with the
        // cursor in that field; the final names the field as the window does (OperationFloor.PlaceSaid).
        string? provedBy = (string?)(observed["subgoals"] as JsonArray)?.OfType<JsonObject>().LastOrDefault()?["satisfiedBy"]
            ?? satisfiedBy;
        if (reached && lastView is not null && provedBy is { Length: > 0 }
            && provedBy.Split('&').Any(atom => atom.Split(':', 2)[0].Trim() == "focus")
            && (string?)lastView["window"]?["focused"]?["name"] is { Length: > 0 } field)
        {
            observed["focusedField"] = field;
        }

        if (lastView is not null && !IsStale(lastView))
        {
            // Review 1 of ronda 21 (finding 2): a kept look is never quoted as the screen now.
            observed["screen"] = ScreenExcerpt(lastView, (string?)state["goal"], LastAppeared(steps, (int?)state["subgoalStart"] ?? 0));
        }

        if (evidence is not null)
        {
            observed["evidence"] = evidence;
        }

        if (errorCode is not null)
        {
            observed["stoppedBy"] = errorCode;
        }

        if (errorCode == "computer_use_destination_ambiguous" && state["destinationCandidates"] is JsonArray { Count: > 1 } candidates)
        {
            // Ronda 21, destino por contenido: the windows the request fits, by their titles; the final asks which.
            observed["destinationCandidates"] = candidates.DeepClone();
        }

        if (errorCode == "computer_use_place_not_found" && (string?)state["missingPlace"] is { Length: > 0 } missing)
        {
            observed["missingPlace"] = missing;
        }

        if (errorCode == DeviceStop && (string?)state["absentDevice"] is { Length: > 0 } absentDevice)
        {
            // Estabilización L: the device the computer does not have; the floor says it (data «limits.devices»).
            observed["absentDevice"] = absentDevice;
        }

        if (errorCode == "computer_use_seen_not_done" && (string?)state["seenNotDone"] is { Length: > 0 } seen)
        {
            // What the model cited as done, seen but not done by the mission (M1): the floor quotes it.
            observed["seenNotDone"] = seen;
        }

        if (errorCode == "computer_use_app_gate" && state["gate"] is JsonObject gate)
        {
            observed["gate"] = gate.DeepClone();
        }

        if (reached && (string?)state["alreadyChosen"] is { Length: > 0 } already)
        {
            // Pasada v3 r9 (v3-13): the option the goal names was chosen before any act touched it; the floor says
            // it was so already, never that BAXY did it.
            observed["alreadyChosen"] = already;
        }

        if (errorCode == "computer_use_file_not_opened" && (string?)state["fileNotOpened"] is { Length: > 0 } cause)
        {
            // Why the file was not opened (the provider's code, or «notShown»): the floor says it in the language.
            observed["fileNotOpened"] = cause;
        }

        return observed;
    }

    // What was on the screen when the mission ended, for the final to quote:
    // the controls that carry a value (a display, a field) and a few lines.
    internal static JsonObject ScreenExcerpt(JsonObject view, string? goal = null, IReadOnlyCollection<string>? appeared = null)
    {
        // A value or a chosen state answers what the person asked about («¿el modo es claro u oscuro?»: the «Elige tu
        // modo» list shows «Oscuro»): the controls that share a word with the goal come first.
        var goalWords = new HashSet<string>(
            ComputerUseSuccessCheck.Fold(goal).Split([' ', ':', ';', ',', '.', '?', '¿'], StringSplitOptions.RemoveEmptyEntries)
                .Where(word => word.Length >= 4),
            StringComparer.Ordinal);
        HashSet<string> askedWords = QuestionContentWords(goal, view);
        bool asking = CarriesQuestion(goal);
        var candidates = new List<(bool Related, JsonObject Said)>();
        if (view["controls"] is JsonArray controls)
        {
            for (int at = 0; at < controls.Count; at++)
            {
                JsonNode? node = controls[at];
                // A loading indicator is no fact of the window (review of fable/cu-v3-carga-preguntas, finding 4: a
                // ProgressBar «Ocupado» is dropped here; a ListItem «Ocupado» chosen is the window's fact and stays).
                // Ronda 20b: one that stands still (furniture of the window) is no fact either.
                if (node is not JsonObject control || NamedLoadingBar(control))
                {
                    continue;
                }

                string name = (string?)control["name"] ?? string.Empty;
                string state = (string?)control["state"] ?? string.Empty;
                string? value = (string?)control["value"] is { Length: > 0 } held ? held
                    : asking ? GridRowValue(controls, at)
                    : null;
                string? chosen = state.Split(' ').FirstOrDefault(word => word is "selected" or "on" or "checked");
                if (value is null && chosen is null)
                {
                    // Ronda 20b (v3-43): a control the last act brought up whose name carries a content word of the
                    // question («Cambiar la configuración del plan Equilibrado» for «qué plan está activo») is what
                    // the window says about it, though it holds no value of its own. Ronda 23: a word of the same
                    // root counts too («(activa)» for «which network is active»).
                    if (appeared is { Count: > 0 } && askedWords.Count > 0
                        && appeared.Contains(ComputerUseSuccessCheck.Fold(name))
                        && BearsQuestionRoot(name, askedWords))
                    {
                        candidates.Add((true, new JsonObject { ["name"] = name.Length > 80 ? name[..80] : name }));
                    }

                    continue;
                }

                var said = new JsonObject { ["name"] = name.Length > 80 ? name[..80] : name };
                if (value is not null)
                {
                    said["value"] = value.Length > 80 ? value[..80] : value;
                }

                if (chosen is not null)
                {
                    said["state"] = chosen;
                }

                bool related = ComputerUseSuccessCheck.Fold(name).Split(' ').Any(goalWords.Contains)
                    || BearsQuestionRoot(name, askedWords);
                candidates.Add((related, said));
            }
        }

        // A label a window without an accessible tree marks by its ink is the item chosen in its navigation (v3 punto 5:
        // «BIBLIOTECA» blue on Steam's library), told as the window writes it.
        foreach (string marked in ComputerUseSuccessCheck.MarkedLabels(view).Take(2))
        {
            candidates.Insert(0, (true, new JsonObject { ["name"] = marked.Length > 80 ? marked[..80] : marked, ["state"] = "selected" }));
        }

        var values = new JsonArray();
        // A related value first (a list showing what is set), then a related chosen item, then the rest: an item named
        // like one of the answers asked about («Windows (claro)», a theme) is not the setting itself.
        foreach ((bool _, JsonObject said) in candidates
            .OrderByDescending(candidate => candidate.Related && candidate.Said["value"] is not null)
            .ThenByDescending(candidate => candidate.Related)
            .Take(8))
        {
            values.Add((JsonNode?)said);
        }

        var read = new List<string>();
        if (view["text"] is JsonObject text)
        {
            foreach (string zone in new[] { "T", "C", "TL", "TR", "L", "R", "B", "BL", "BR" })
            {
                if (text[zone] is JsonArray zoneLines)
                {
                    read.AddRange(zoneLines.Select(line => (string?)line ?? string.Empty));
                }
            }
        }

        // Ronda 23 (live r21 v3-62: «Red privada (activa)» was the eighth line read, in a zone after the six kept, and the
        // final named «Red de dominio»): with a question the lines that bear on it go first (a word of the same root as
        // one of the question's, then what the last act brought up), and up to twelve are kept; without one, the first six
        // as they are read.
        IEnumerable<string> kept = asking
            ? read.Select((line, order) => (line, order))
                .OrderByDescending(item => BearsQuestionRoot(item.line, askedWords))
                .ThenByDescending(item => appeared?.Contains(ComputerUseSuccessCheck.Fold(item.line)) == true)
                .ThenBy(item => item.order)
                .Take(QuestionExcerptLines)
                .Select(item => item.line)
            : read.Take(ExcerptLines);
        var lines = new JsonArray();
        foreach (string line in kept)
        {
            lines.Add((JsonNode?)JsonValue.Create(line));
        }

        // What carries a number is usually the answer a person looks for (a
        // display, a counter, a price): named controls and lines with digits.
        var numbers = new JsonArray();
        if (view["controls"] is JsonArray named)
        {
            foreach (JsonNode? node in named)
            {
                if (node is JsonObject control && (string?)control["name"] is { Length: > 0 } name
                    && name.Any(char.IsAsciiDigit) && numbers.Count < 6)
                {
                    numbers.Add((JsonNode?)JsonValue.Create(name.Length > 80 ? name[..80] : name));
                }
            }
        }

        foreach (JsonNode? line in lines)
        {
            if ((string?)line is { Length: > 0 } written && written.Any(char.IsAsciiDigit) && numbers.Count < 6)
            {
                numbers.Add((JsonNode?)JsonValue.Create(written));
            }
        }

        var excerpt = new JsonObject { ["title"] = (string?)view["window"]?["title"] };
        if (values.Count > 0)
        {
            excerpt["values"] = values;
        }

        if (numbers.Count > 0)
        {
            excerpt["numbers"] = numbers;
        }

        if (lines.Count > 0)
        {
            excerpt["lines"] = lines;
            excerpt["controlLines"] = ControlLines(view, lines);
        }

        // Imprescindibles de mensajería («qué me escribió Ron92»): with a question, the last named groups of the view in
        // its order. A chat's accessible tree names each message as a group («autor , texto , hora»); the mind keeps them
        // only for a question about what was last written (cu_projection) and answers from them (cu_finals).
        if (asking && view["controls"] is JsonArray shown)
        {
            var groups = new JsonArray();
            // Encargo IMP3: the groups of the look that kept the tree's last entries, when one was taken (NoteTheTailAsync).
            IEnumerable<JsonObject> listedGroups = view["tailGroups"] is JsonArray tail
                ? tail.Select(node => new JsonObject { ["kind"] = "Group", ["name"] = (string?)node })
                : shown.OfType<JsonObject>();
            foreach (string name in listedGroups
                .Where(control => (string?)control["kind"] == "Group")
                .Select(control => (string?)control["name"] ?? string.Empty)
                .Where(name => name.Length > 0)
                .TakeLast(QuestionExcerptGroups))
            {
                groups.Add((JsonNode?)JsonValue.Create(name.Length > 200 ? name[..200] : name));
            }

            if (groups.Count > 0)
            {
                excerpt["groups"] = groups;
            }

            // Encargo IMP4: a chat's lines read with their places (NoteTheChatLinesAsync), for the mind to tell bubbles.
            if (view["chatLines"] is JsonArray chatLines)
            {
                excerpt["chatLines"] = chatLines.DeepClone();
            }
        }

        return excerpt;
    }

    // The kinds whose name is the label a person presses or picks (UIA control types): that label stays written on the
    // screen whether or not pressing it changed anything.
    private static readonly HashSet<string> LabelKinds = new(StringComparer.Ordinal)
    {
        "Button", "SplitButton", "MenuItem", "ListItem", "TabItem", "Hyperlink", "CheckBox", "RadioButton", "TreeItem",
        "ComboBox", "Edit",
    };

    // Revisión 2 de la ronda 22 (bloqueante 1): the indexes of the excerpt's lines that are the label of a control the
    // window offers («Modo de lectura» under the ribbon's button «Modo de lectura», «Archivo Inicio Insertar Vista» over
    // its tabs). A line is a control's when it and a control's name share their words whole (one inside the other). The
    // mind never takes such a line as the state a window is in (semantic.dialogue._screen_parts): a click receipt and
    // the label it clicked prove nothing. Without a tree that names its controls, no line can be told apart from a
    // label, and every line is marked.
    internal static JsonArray ControlLines(JsonObject view, JsonArray lines)
    {
        var labels = new List<string>();
        foreach (string list in new[] { "controls", "disabled" })
        {
            if (view[list] is not JsonArray controls)
            {
                continue;
            }

            foreach (JsonNode? node in controls)
            {
                if (node is JsonObject control && LabelKinds.Contains((string?)control["kind"] ?? string.Empty)
                    && LabelWords((string?)control["name"]) is { Length: > 0 } label)
                {
                    labels.Add($" {label} ");
                }
            }
        }

        var marked = new JsonArray();
        for (int index = 0; index < lines.Count; index++)
        {
            string line = $" {LabelWords((string?)lines[index])} ";
            if (labels.Count == 0 || line.Trim().Length == 0
                || labels.Any(label => line.Contains(label, StringComparison.Ordinal) || label.Contains(line, StringComparison.Ordinal)))
            {
                marked.Add((JsonNode?)JsonValue.Create(index));
            }
        }

        return marked;
    }

    private static string LabelWords(string? text) =>
        string.Join(' ', Regex.Split(ComputerUseSuccessCheck.Fold(text), @"[^\p{L}\p{N}]+").Where(word => word.Length > 0));

    /// <summary>
    /// Revision 2 of ronda 23: the place a goal «ir a X» goes to, for the guards of the arrival («parece que ya estabas»,
    /// the place the window does not have). A chain's last sub-goal carries the mission's question to be read there
    /// («ir a wi-fi; y responder: …»), and is still a going to its place; a single mission whose own goal asks keeps
    /// reading on the place as before (none).
    /// </summary>
    internal static string ArrivalPlace(string? goal, bool chained) =>
        OperationFloor.PlaceAsked(
            chained && goal?.IndexOf(OperationFloor.QuestionMark, StringComparison.Ordinal) is int asked and >= 0
                ? goal[..asked].Trim()
                : goal);

    /// <summary>The lines of the screen the final quotes: six, and twelve when the goal carries a question.</summary>
    internal const int ExcerptLines = 6;

    internal const int QuestionExcerptLines = 12;

    // The groups of the view a question's excerpt keeps, the last ones (a conversation's latest messages).
    internal const int QuestionExcerptGroups = 8;

    /// <summary>
    /// Ronda 23 (twin of the mind's semantic.answer_evidence.shares_root): two folded words of one root, also between
    /// languages that spell it alike: four letters or more alike at the head and at most two more letters in the longer
    /// («active»/«activa», «plan»/«planes»; never «active»/«activado» nor «activa»/«activado»).
    /// </summary>
    internal static bool SharesRoot(string left, string right)
    {
        if (left.Length < 4 || right.Length < 4)
        {
            return false;
        }

        int common = 0;
        while (common < left.Length && common < right.Length && left[common] == right[common])
        {
            common++;
        }

        if (common < 4 || common < Math.Max(left.Length, right.Length) - 2)
        {
            return false;
        }

        // Revision 2: two letters more that begin with a consonant derive another word of the root (the participle
        // «activado» of «activa»), not its inflection («planes», «activos», «memoria»).
        string rest = (left.Length >= right.Length ? left : right)[common..];
        return !(rest.Length == 2 && !"aeiou".Contains(rest[0], StringComparison.Ordinal));
    }

    /// <summary>Some word of the text shares a root with a content word of the question (<see cref="QuestionContentWords"/>).</summary>
    internal static bool BearsQuestionRoot(string? text, IReadOnlyCollection<string> askedWords) =>
        askedWords.Count > 0
        && System.Text.RegularExpressions.Regex.Split(ComputerUseSuccessCheck.Fold(text), @"[^\p{L}\p{Nd}]+")
            .Any(word => askedWords.Any(asked => SharesRoot(word, asked)));

    /// <summary>
    /// Ronda 23 (live r21 v3-46, the table of «Pantalla»: DataItem «Nombre», Text «Nombre», Text «AMD Radeon(TM)
    /// Graphics»): a row of a grid without a value of its own holds it in a cell beside its name, listed right after it
    /// as the cell that repeats the row's name and the cell that follows. Null when the next controls are not so.
    /// </summary>
    internal static string? GridRowValue(JsonArray controls, int at)
    {
        if (controls[at] is not JsonObject row || (string?)row["kind"] != "DataItem" || at + 2 >= controls.Count
            || controls[at + 1] is not JsonObject label || controls[at + 2] is not JsonObject cell
            || (string?)label["kind"] != "Text" || (string?)cell["kind"] != "Text")
        {
            return null;
        }

        string name = ComputerUseSuccessCheck.Fold((string?)row["name"]);
        string? value = (string?)cell["name"];
        return name.Length > 0 && ComputerUseSuccessCheck.Fold((string?)label["name"]) == name
            && value is { Length: > 0 } && ComputerUseSuccessCheck.Fold(value) != name
            ? value
            : null;
    }

    private static OperationResponse Synthesize(
        PreparedOperation prepared, bool reached, string? errorCode, JsonObject observed)
    {
        using JsonDocument document = JsonDocument.Parse(observed.ToJsonString());
        JsonElement result = document.RootElement.Clone();
        OperationOutcome outcome = reached
            ? OperationOutcome.Success(result)
            : OperationOutcome.Failure(errorCode ?? "computer_use_failed", result);
        string message = OperationVisibleFacts.FromOutcome(OperationName, outcome);
        return new OperationResponse(
            ProtocolTypes.OperationResponse,
            prepared.InvocationId,
            prepared.MissionId,
            prepared.InvocationId,
            reached ? OperationStatuses.Completed : OperationStatuses.Failed,
            message,
            reached,
            false,
            result,
            reached ? null : errorCode ?? "computer_use_failed");
    }

    // ------------------------------------------------------- translated labels
}
