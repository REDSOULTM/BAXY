using System.Globalization;
using System.IO;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;

namespace Baxy.App;

/// <summary>
/// M107 twin of the mind's baxy_mind.operation_floor: the final of an action said from the turn's facts alone when
/// no composition could be published. It reads the same data (src/baxy_mind/data/operation_floor.v1.json, embedded):
/// the plain clause of every catalog operation, the typed failures said whole, and the templates that put the
/// operation, its outcome (done, failed, left uncertain) and what was observed into one sentence. A mission says
/// each step. Nothing the result did not hold is stated.
/// </summary>
internal static class OperationFloor
{
    private const string ResourceName = "Baxy.App.OperationFloor.json";
    private const int LongestName = 120;
    private const int LongestContent = 200;
    private const int ListedNames = 3;

    private static readonly Lazy<JsonObject> Data = new(Load);

    private static readonly string[] Clitics = ["nos", "les", "los", "las", "me", "te", "se", "lo", "la", "le"];

    private static readonly Lazy<IReadOnlySet<string>> Infinitives = new(LoadInfinitives);

    /// <summary>
    /// M108 twin of operation_floor.spanish_infinitives: the verb of every operation's plain clause («apagar»,
    /// «abrir», «buscarlo» → «buscar»). The final gate reads a first-person future of any of them as an act promised
    /// (UserMessagePolicy.PromisesTheAct).
    /// </summary>
    internal static IReadOnlySet<string> SpanishInfinitives => Infinitives.Value;

    private static HashSet<string> LoadInfinitives()
    {
        var verbs = new HashSet<string>(StringComparer.Ordinal);
        if (Data.Value["operations"] is not JsonObject operations)
        {
            return verbs;
        }

        foreach ((string _, JsonNode? node) in operations)
        {
            if (node is not JsonObject entry)
            {
                continue;
            }

            var clauses = new List<string?> { (entry["es"] as JsonArray)?[0]?.GetValue<string>() };
            if (entry["variants"] is JsonObject variants && variants["values"] is JsonObject values)
            {
                clauses.AddRange(values.Select(pair => ((pair.Value as JsonObject)?["es"] as JsonArray)?[0]?.GetValue<string>()));
            }

            foreach (string? clause in clauses)
            {
                if (string.IsNullOrWhiteSpace(clause))
                {
                    continue;
                }

                string verb = clause.Split(' ', StringSplitOptions.RemoveEmptyEntries)[0];
                string? clitic = Clitics.FirstOrDefault(c =>
                    verb.EndsWith(c, StringComparison.Ordinal)
                    && verb[..^c.Length] is { } stem
                    && (stem.EndsWith("ar", StringComparison.Ordinal) || stem.EndsWith("er", StringComparison.Ordinal)
                        || stem.EndsWith("ir", StringComparison.Ordinal)));
                verbs.Add(clitic is null ? verb : verb[..^clitic.Length]);
            }
        }

        return verbs;
    }

    private static JsonObject Load()
    {
        using Stream stream = typeof(OperationFloor).Assembly.GetManifestResourceStream(ResourceName)
            ?? throw new InvalidOperationException("The operation floor data is not embedded.");
        return JsonNode.Parse(stream) as JsonObject
            ?? throw new InvalidDataException("The operation floor data is not an object.");
    }

    /// <summary>The typed failure said whole (its cause known), from the result's codes or its reason's.</summary>
    internal static string? FailureSentence(JsonObject situation, bool english)
    {
        ArgumentNullException.ThrowIfNull(situation);
        if (Data.Value["failures"] is not JsonObject failures)
        {
            return null;
        }

        var codes = new List<string?>();
        if (Decoded(situation["reason"]) is JsonObject reason)
        {
            codes.Add(Text(reason, "error"));
            codes.Add(Text(reason, "cause"));
        }

        codes.Add(Text(situation, "error"));
        codes.Add(Text(situation, "cause"));
        foreach (string? code in codes)
        {
            if (code is not null && failures[code] is JsonObject said)
            {
                return Text(said, english ? "en" : "es");
            }

            if (code is not null && AbsentDeviceSentence(code, english) is { } absent)
            {
                return absent;
            }
        }

        return null;
    }

    /// <summary>
    /// Encargo H2 (twin of the mind's operation_floor.failure_sentences): a device the computer lacks, one of the
    /// «absent» codes of data «computerUse.limits.devices», said with that device's cause as a mission says it.
    /// </summary>
    private static string? AbsentDeviceSentence(string code, bool english)
    {
        string language = english ? "en" : "es";
        if (ComputerUseData["limits"] is not JsonObject limits || limits["devices"] is not JsonObject devices
            || limits[language]?["absent"] is not JsonValue template)
        {
            return null;
        }

        JsonObject? device = devices.Select(pair => pair.Value).OfType<JsonObject>().FirstOrDefault(entry =>
            entry["absent"] is JsonArray absent && absent.Any(node => (string?)node == code));
        return device is not null && Text(device, language) is { Length: > 0 } cause
            ? Sentence(((string)template!).Replace("{cause}", cause, StringComparison.Ordinal))
            : null;
    }

    /// <summary>
    /// Live 2026-10-07 («en el Explorador de archivos andá a Documentos y creá una carpeta…» → the person read
    /// «⚠ (internal_code;retry_exhausted)»): the line a composition that every draft failed leaves when no floor tells
    /// it, by what the turn was (data: compositionFailures). The diagnostic code stays in the private log.
    /// </summary>
    internal static string? CompositionFailureSentence(string intent, bool english, string? source = null)
    {
        if (Data.Value["compositionFailures"] is not JsonObject lines)
        {
            return null;
        }

        string kind = intent switch
        {
            "clarification" => "clarification",
            "confirmation" => "confirmation",
            "status" or "error" => "result",
            _ => "default",
        };
        if (kind == "confirmation")
        {
            // Not one of the composition failures' lines (owner's M75: those are for a question or a result): the
            // confirmation's own floor (data: confirmationFloor), said from its pending act.
            return Data.Value["confirmationFloor"] is JsonObject asked ? ConfirmationSentence(asked, source, english) : null;
        }

        return lines[kind] is JsonObject said ? Text(said, english ? "en" : "es") : null;
    }

    /// <summary>
    /// Ronda 24 (pasada r23): the confirmation no draft could word, said from its pending act (data: confirmationFloor):
    /// the plain clause of the operation, with the name it acts on.
    /// </summary>
    private static string? ConfirmationSentence(JsonObject asked, string? source, bool english)
    {
        string language = english ? "en" : "es";
        JsonObject? pending = null;
        try
        {
            pending = source is null ? null : (JsonNode.Parse(source) as JsonObject)?["pendingAction"] as JsonObject;
        }
        catch (JsonException)
        {
            pending = null;
        }

        string? operation = pending is null ? null : Text(pending, "operation");
        string? clause = operation is not null
            && Data.Value["operations"] is JsonObject operations
            && operations[operation] is JsonObject entry
            && entry[language] is JsonArray forms
            && forms.Count > 0
                ? (string?)forms[0]
                : null;
        string act;
        if (clause is null)
        {
            act = asked["unknown"] is JsonObject unknown ? Text(unknown, language) ?? string.Empty : string.Empty;
        }
        else
        {
            JsonObject? arguments = pending!["arguments"] as JsonObject;
            string? label = Named(arguments is null ? null : Text(arguments, "label"));
            act = label is not null && asked["label"] is JsonObject shaped && Text(shaped, language) is { } template
                ? template.Replace("{act}", clause, StringComparison.Ordinal).Replace("{label}", label, StringComparison.Ordinal)
                : clause;
        }

        return act.Length == 0 ? null : Text(asked, language)?.Replace("{act}", act, StringComparison.Ordinal);
    }

    /// <summary>
    /// Estabilización M3 (data: memoryKeys): the question of which kept datum a forget means, with the candidates by their
    /// names (<paramref name="labels"/> more than one), or the sentence that the datum named was not kept (one label).
    /// </summary>
    internal static string MemoryKeysSentence(IReadOnlyList<string> labels, bool english)
    {
        ArgumentNullException.ThrowIfNull(labels);
        string language = english ? "en" : "es";
        JsonObject data = (JsonObject)Data.Value["memoryKeys"]!;
        if (labels.Count == 1)
        {
            return Text((JsonObject)data["absent"]!, language)!.Replace("{label}", labels[0], StringComparison.Ordinal);
        }

        string item = Text((JsonObject)data["item"]!, language)!;
        string[] named = labels.Select(label => item.Replace("{label}", label, StringComparison.Ordinal)).ToArray();
        string candidates = string.Join(", ", named[..^1]) + Text((JsonObject)data["or"]!, language) + named[^1];
        return Text((JsonObject)data["which"]!, language)!.Replace("{candidates}", candidates, StringComparison.Ordinal);
    }

    private static string? Named(string? name)
    {
        string trimmed = (name ?? string.Empty).Trim();
        return trimmed.Length == 0 ? null : trimmed.Length > LongestName ? trimmed[..LongestName] : trimmed;
    }

    /// <summary>
    /// r22 (2026-10-09): the line for the mind's model not being up, by the cause the mind reported
    /// (<c>vram_insuficiente</c>, <c>ram_insuficiente</c>, <c>proceso_salio</c>, <c>tiempo</c>) or
    /// <c>iniciando</c> while it still starts (data: mindStartup). Null for any other cause.
    /// </summary>
    internal static string? MindStartupSentence(string? cause, bool english)
    {
        if (cause is null
            || Data.Value["mindStartup"] is not JsonObject lines
            || lines[cause] is not JsonObject said)
        {
            return null;
        }

        return Text(said, english ? "en" : "es");
    }

    /// <summary>The startup cause a turn's facts carry (<c>startup</c>), or null.</summary>
    internal static string? MindStartupCause(string source)
    {
        try
        {
            return JsonNode.Parse(source) is JsonObject facts
                && facts["startup"] is JsonValue value
                && value.TryGetValue(out string? cause)
                    ? cause
                    : null;
        }
        catch (JsonException)
        {
            return null;
        }
    }

    /// <summary>
    /// Regresiones r2 M5 (live v2-s02): the decider was unavailable (it was warming up again and again) and the turn's
    /// failure could not be worded either («no_response;recovery:no_response»): the person saw nothing for 171 s. True
    /// for the facts of a turn whose request the decider never read (<c>mind_unavailable</c>): its failed composition
    /// is published at once, with the line any failed composition leaves (owner's M75: no new fixed sentence), instead
    /// of being queued for a mind that may not come back.
    /// </summary>
    internal static bool DeciderCouldNotRead(string source)
    {
        try
        {
            return JsonNode.Parse(source) is JsonObject facts && (string?)facts["cause"] == "mind_unavailable";
        }
        catch (JsonException)
        {
            return false;
        }
    }

    /// <summary>The sentence for one operation result or one mission, or null when there is no action to tell.</summary>
    internal static string? Final(JsonObject situation, bool english, TimeProvider? clock = null)
    {
        ArgumentNullException.ThrowIfNull(situation);
        if (ComputerUse(situation, english) is { } mission)
        {
            return Sentence(mission);
        }

        JsonObject templates = Templates(english);
        string cause = (Text(situation, "cause") ?? string.Empty).Trim().ToLowerInvariant();
        if (cause == "clarification_cancelled" && Data.Value["clarificationCancelled"] is JsonObject dropped)
        {
            // Estabilización M3 (live 2026-10-12: «No, cancelá» to a pending question → «No pude contarte cómo salió lo
            // que pediste.»): the dropped question is said by the floor, as the mind says it (operation_floor.pending_final).
            return Text(dropped, english ? "en" : "es");
        }

        string text;
        // Estabilización F: a plan's step left unconfirmed goes, like a failed one, with its own facts.
        if (cause is "mission_completed" or "mission_failed" or "result_unverified")
        {
            text = Mission(situation, cause, english, templates, clock ?? TimeProvider.System);
        }
        else if (Text(situation, "kind") != "operation" && !VerifiedStatusOfAnOperation(situation))
        {
            // No action named to tell: a sentence without one would be a fixed reply (owner's review of M75).
            return null;
        }
        else
        {
            text = Step(situation, english, templates, clock ?? TimeProvider.System);
        }

        return Sentence(text);
    }

    // Windows writes bidi marks inside the names and clocks it shows («7‎:‎58»).
    private static readonly Regex BidiMarks = new("[‎‏‪-‮⁦-⁩]", RegexOptions.CultureInvariant);

    private static readonly Lazy<Regex> OverwriteConfirmPattern = new(() => OverwritePattern("confirm"));

    private static readonly Lazy<Regex> OverwriteWarningPattern = new(() => OverwritePattern("warning"));

    /// <summary>Goal v3 point 2: a folded label that answers yes to writing over a file (data «computerUse.overwrite»).</summary>
    internal static Regex OverwriteConfirm => OverwriteConfirmPattern.Value;

    /// <summary>Goal v3 point 2: a folded text that warns that a file already exists and would be written over.</summary>
    internal static Regex OverwriteWarning => OverwriteWarningPattern.Value;

    private static Regex OverwritePattern(string name) => new(
        T((JsonObject)((JsonObject)Data.Value["computerUse"]!)["overwrite"]!, name),
        RegexOptions.CultureInvariant);

    private static readonly Lazy<Regex> ContentErasingPattern = new(() => new Regex(
        T((JsonObject)((JsonObject)Data.Value["computerUse"]!)["contentErasing"]!, "label"),
        RegexOptions.CultureInvariant));

    /// <summary>
    /// Goal v3 ventana-misión: a folded label of a command that selects all, cuts, erases, pastes, replaces or undoes
    /// (data «computerUse.contentErasing»).
    /// </summary>
    internal static bool ContentErasingCommand(string foldedLabel) =>
        foldedLabel.Length > 0 && ContentErasingPattern.Value.IsMatch(foldedLabel.Trim());

    private static readonly Lazy<Regex> SearchFieldPattern = new(() => new Regex(
        T((JsonObject)((JsonObject)Data.Value["computerUse"]!)["searchField"]!, "name"), RegexOptions.CultureInvariant));

    private static readonly Lazy<Regex> AddressFieldPattern = new(() => new Regex(
        T((JsonObject)((JsonObject)Data.Value["computerUse"]!)["searchField"]!, "address"), RegexOptions.CultureInvariant));

    /// <summary>
    /// Ronda 24b (banco r23 c6): a folded field name that says it looks a name up and never that it is an address (data
    /// «computerUse.searchField», the mind's cu_fields._SEARCH_NAME and _ADDRESS_NAME).
    /// </summary>
    internal static bool SearchFieldName(string folded) =>
        folded.Length > 0 && SearchFieldPattern.Value.IsMatch(SearchWords(folded)) && !AddressFieldPattern.Value.IsMatch(folded);

    private static readonly Lazy<Regex> ComposerFieldPattern = new(() => new Regex(
        T((JsonObject)((JsonObject)Data.Value["computerUse"]!)["searchField"]!, "composer"), RegexOptions.CultureInvariant));

    private static readonly Lazy<Regex> RecipientPattern = new(() => new Regex(
        T((JsonObject)((JsonObject)Data.Value["computerUse"]!)["searchField"]!, "recipient"), RegexOptions.CultureInvariant));

    /// <summary>
    /// Revisión 2 de r24b (B1): the part of a folded field name whose search words make it a search (the mind's
    /// cu_fields._search_words). A name that is a message box once its recipients (#channel, @person) are read off
    /// («enviar mensaje a #busqueda-de-equipo», «mensaje @buscador99») has its search words only in who it writes to;
    /// any other name is read whole («buscar o empezar un chat nuevo» is a search).
    /// </summary>
    internal static string SearchWords(string folded)
    {
        string without = RecipientPattern.Value.Replace(folded, " ");
        return ComposerFieldPattern.Value.IsMatch(without) ? without : folded;
    }

    private static readonly Lazy<Regex> SearchLabelPattern = new(() => new Regex(
        T((JsonObject)((JsonObject)Data.Value["computerUse"]!)["searchField"]!, "label"), RegexOptions.CultureInvariant));

    /// <summary>
    /// Revisión 1 de r24b (B3): a folded whole name, trimmed of its closing «:», «.» or «…», that is only a search label
    /// («buscar», «search», «find»; data «computerUse.searchField.label», the mind's cu_semejanza.is_search_label): what
    /// makes a Document a search box, never a search word inside a document's title.
    /// </summary>
    internal static bool SearchLabelName(string folded) => folded.Length > 0 && SearchLabelPattern.Value.IsMatch(folded);

    /// <summary>Ronda 24b: a folded field name that says it is an address (data «computerUse.searchField.address»).</summary>
    internal static bool AddressFieldName(string folded) => folded.Length > 0 && AddressFieldPattern.Value.IsMatch(folded);

    private static readonly Lazy<(string[] Opening, string[] LeadsTo, string[] Closing)> PlaceToggleVerbs = new(() =>
    {
        var toggle = (JsonObject)((JsonObject)Data.Value["computerUse"]!)["placeToggle"]!;
        string[] Words(string key) => ((JsonArray)toggle[key]!).Select(word => (string)word!).ToArray();
        return (Words("opening"), Words("leadsTo"), Words("closing"));
    });

    /// <summary>
    /// Encargo S: the folded verbs, each with its trailing space, before a place's name on the button that opens its
    /// panel («abre tu biblioteca»), on one that only leads there («ir a inicio») and on the one that closes it
    /// («comprimir tu biblioteca», there only while the place is open) (data «computerUse.placeToggle», the mind's
    /// cu_vocabulary._PLACE_TOGGLE).
    /// </summary>
    internal static IReadOnlyList<string> PlaceOpeningVerbs => PlaceToggleVerbs.Value.Opening;

    internal static IReadOnlyList<string> PlaceLeadingVerbs => PlaceToggleVerbs.Value.LeadsTo;

    internal static IReadOnlyList<string> PlaceClosingVerbs => PlaceToggleVerbs.Value.Closing;

    private static readonly Lazy<JsonObject> ContentKeys = new(() =>
        (JsonObject)((JsonObject)Data.Value["computerUse"]!)["contentKeys"]!);

    /// <summary>
    /// Ronda 21: the keys of a class of data «computerUse.contentKeys» («keeping», «container», «altering»; ronda 24:
    /// «paste», «copy»; review 4: «unseenEffect», «writtenEffect»), as the mission names them (folded, words joined by «_»).
    /// </summary>
    internal static IReadOnlySet<string> ContentKeyClass(string name) =>
        ContentKeyClasses.Value.TryGetValue(name, out HashSet<string>? keys) ? keys : new HashSet<string>(StringComparer.Ordinal);

    private static readonly Lazy<Dictionary<string, HashSet<string>>> ContentKeyClasses = new(() =>
        new[] { "keeping", "container", "altering", "paste", "copy", "unseenEffect", "writtenEffect" }.ToDictionary(
            name => name,
            name => new HashSet<string>(
                (ContentKeys.Value[name] as JsonArray ?? []).Select(node => (string?)node ?? string.Empty).Where(key => key.Length > 0),
                StringComparer.Ordinal),
            StringComparer.Ordinal));

    private static readonly Lazy<Regex> PlaceGoal = new(() => new Regex(
        T((JsonObject)Data.Value["computerUse"]!, "placeGoal"),
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant));

    /// <summary>
    /// Live 2026-10-07 twin of the mind's cu_finals.floor_sentence (data «computerUse»): a computer-use mission the
    /// mind left without a final said «Lo hice en la aplicación «Reloj»; hay 2: «Reloj mundial».» (its steps counted
    /// as a list read) or «No pude hacerlo en la aplicación «Configuración».» (no cause). It says the place reached
    /// as the window writes it, or what was not reached and the typed stop cause. Null when the turn is no such
    /// mission or its facts hold nothing to say (the plain clause then tells it).
    /// </summary>
    private static string? ComputerUse(JsonObject situation, bool english)
    {
        if (ComputerUseMission(situation) is not { } mission || mission["observed"] is not JsonObject observed)
        {
            return null;
        }

        var data = (JsonObject)Data.Value["computerUse"]!;
        string language = english ? "en" : "es";
        var said = (JsonObject)data[language]!;
        string question = T(data, "questionMark");
        string? goal = Text(observed, "goal");
        var names = new List<string>();
        IEnumerable<JsonObject> steps = (observed["steps"] as JsonArray ?? new JsonArray()).OfType<JsonObject>();
        IEnumerable<JsonObject> values = ((observed["screen"] as JsonObject)?["values"] as JsonArray ?? new JsonArray())
            .OfType<JsonObject>();
        foreach (JsonNode? candidate in steps.Where(step => Flag(step, "ok") == true).Select(step => step["name"])
            .Concat(values.Select(item => item["name"])))
        {
            if (FloorName(candidate, data) is { Length: > 0 } name)
            {
                names.Add(name);
            }
        }

        var window = observed["window"] as JsonObject;
        // Ronda 24 (pasada r23 t-drag-2): the title of a window nobody asked for (observed «windowAsked» false) never
        // names the place; twin of the mind's cu_finals._mission_app. Revisión U, H3: nor a protected window's.
        string app = FloorName(observed["application"], data) is { Length: > 0 } application
            ? application
            : Flag(observed, "windowAsked") == false || (window is not null && Flag(window, "protected") == true)
                ? string.Empty
                : FloorName(window?["title"], data);
        if (goal is not null && goal.Contains(question, StringComparison.Ordinal))
        {
            // «… y decime si el modo es claro u oscuro»: the answer is the mind's to read from the window. Pasada r15b
            // (v3-43, v3-61): when the mind left a reached mission with a question without a final, this floor said
            // «Lo hice en la aplicación…» with no answer; it says the place reached and the question unread instead
            // (twin of the mind's cu_finals.unanswered_sentence), never that it did it.
            return Flag(mission, "verified") == true && Flag(mission, "succeeded") == true
                && Flag(observed, "reached") == true
                    ? Unanswered(goal, question, names, app, data, english)
                    : null;
        }
        List<JsonObject> subgoals = (observed["subgoals"] as JsonArray ?? new JsonArray())
            .OfType<JsonObject>().Take(8).ToList();
        string Quoted(string value) => Quote(value, Templates(english));
        if (Flag(mission, "verified") == true && Flag(mission, "succeeded") == true)
        {
            if (Flag(observed, "reached") != true)
            {
                // A verified result that does not say it reached anything is never told as a failure.
                return null;
            }

            if (Parts(observed, subgoals, goal, app, english) is { Length: > 0 } parts)
            {
                return parts;
            }

            // Revisión 1 de r24b (B3), twin of cu_finals.floor_sentence: an arrival only a focused field proved is
            // told as the search opened even when the window does not spell the place asked; never «lo hice en X» nor
            // the weak count of a result (focus is a weak atom of data «weakDone»).
            if (SearchOpenedSaid(observed, english, data) is { Length: > 0 } opened)
            {
                return opened;
            }

            string reached = Place(subgoals.Count > 0 ? Text(subgoals[^1], "goal") : goal, names, question, data);
            if (reached.Length > 0)
            {
                return PlaceSaid(observed, english).Replace("{place}", Quoted(reached), StringComparison.Ordinal);
            }

            // «Listo, lo hice en X» only after a verified act of the mission besides opening the application (falsos
            // éxitos v3 M1: «Listo, lo hice en «Fotos»» with no step taken).
            // Ronda 22 (pasada r18 t3-c18, t3-c19, t4-c06): only when a check of the window proved it; on the model's own
            // citation or a resemblance the acts are counted and the result is not told as done (data «weakDone»).
            int acts = steps.Count(step => Flag(step, "ok") == true && Text(step, "operation") is { } act && act != "app.open");
            if (app.Length == 0 || acts == 0)
            {
                return null;
            }

            if (WeaklyReached(observed, subgoals, data))
            {
                var weak = (JsonObject)data["weakDone"]!;
                // Ronda 24 (pasada r23, v3-14): the value the last click named, shown chosen, is said as seen, never
                // denied (data «weakDone.seen»).
                if (WeakSeen(steps, values) is { } shown)
                {
                    var seenTemplates = (JsonObject)weak["seen"]!;
                    string stateWord = (string)((JsonObject)((JsonObject)seenTemplates["states"]!)[language]!)[shown.State]!;
                    return T(seenTemplates, language)
                        .Replace("{app}", Quoted(app), StringComparison.Ordinal)
                        .Replace("{value}", Quoted(shown.Name), StringComparison.Ordinal)
                        .Replace("{state}", stateWord, StringComparison.Ordinal);
                }

                // Revisión 1 de r22 (hallazgo d): the count in words (countWords, countMany), never a figure.
                var words = (JsonArray)((JsonObject)weak["countWords"]!)[language]!;
                string count = acts <= words.Count ? (string)words[acts - 1]! : T((JsonObject)weak["countMany"]!, language);
                return T(weak, acts == 1 ? language + "One" : language)
                    .Replace("{count}", count, StringComparison.Ordinal)
                    .Replace("{app}", Quoted(app), StringComparison.Ordinal);
            }

            return T(said, "app").Replace("{app}", Quoted(app), StringComparison.Ordinal);
        }

        JsonObject? unreached = subgoals.FirstOrDefault(item => Flag(item, "reached") != true);
        string place = Place((unreached is null ? null : Text(unreached, "goal")) ?? goal, names, question, data);
        // Encargo H1 (tandas fin1/fin2 t3-c02 t1), twin of cu_finals.floor_sentence: the application the mission
        // started is said before what it could not do.
        string started = app.Length > 0 && OpenedByMission(steps) ? "Opened" : string.Empty;
        string head = place.Length > 0
            ? T(said, "notPlace" + started).Replace("{place}", Quoted(place), StringComparison.Ordinal)
                .Replace("{app}", Quoted(app), StringComparison.Ordinal)
            : app.Length > 0
                ? T(said, "notApp" + started).Replace("{app}", Quoted(app), StringComparison.Ordinal)
                : T(said, "not");
        string? stoppedBy = Text(observed, "stoppedBy");
        if (stoppedBy == "computer_use_already_there_unconfirmed" && place.Length > 0)
        {
            // The click on the place's own name left the window as it was (live v2-s12: Steam already on its library):
            // probably there already, never told as arrived.
            return T((JsonObject)data["alreadyThere"]!, language).Replace("{place}", Quoted(place), StringComparison.Ordinal);
        }

        if (stoppedBy == "computer_use_seen_not_done" && FloorName(observed["seenNotDone"], data) is { Length: > 0 } seen
            && !steps.Any(step => Flag(step, "ok") == true && Text(step, "operation") is { } act && act != "app.open"))
        {
            // Seen, not done (falsos éxitos v3 M1): nothing of its own was done and what the model cited already shows.
            var seenNotDone = (JsonObject)data["seenNotDone"]!;
            return app.Length > 0
                ? T(seenNotDone, language).Replace("{seen}", Quoted(seen), StringComparison.Ordinal)
                    .Replace("{app}", Quoted(app), StringComparison.Ordinal)
                : T(seenNotDone, language + "Bare").Replace("{seen}", Quoted(seen), StringComparison.Ordinal);
        }

        string typedLeft = TypedLeft(steps, english, data);
        if (stoppedBy is null || (data["causes"] as JsonObject)?[stoppedBy] is not JsonObject causes)
        {
            // An untyped stop code is never said as prose.
            return head + typedLeft;
        }

        string cause = Text(causes, language) ?? string.Empty;
        JsonObject? cover = window?["coveredBy"] as JsonObject;
        string? coveredBy = cover is null ? null : (NonEmpty(cover, "title") ?? NonEmpty(cover, "process"));
        if (stoppedBy == "computer_use_window_covered" && coveredBy is not null)
        {
            cause = T((JsonObject)data["coveredBy"]!, language).Replace("{window}", coveredBy, StringComparison.Ordinal);
        }

        // Estabilización U (revisión H3): a protected window is said by its application (its process), never by its
        // title, which in an editor or a console carries the person's paths and commands. Twin of cu_projection.project_seen.
        if (stoppedBy == "computer_use_window_protected" && window is not null
            && FloorName(window["process"], data) is { Length: > 0 } process)
        {
            string protectedApp = process.EndsWith(".exe", StringComparison.OrdinalIgnoreCase) ? process[..^4] : process;
            cause = T((JsonObject)data["protectedWindow"]!, language).Replace("{app}", protectedApp, StringComparison.Ordinal);
        }

        if (stoppedBy == "computer_use_place_not_found" && FloorName(observed["missingPlace"], data) is { Length: > 0 } missing)
        {
            cause = T((JsonObject)data["placeNotFound"]!, language).Replace("{place}", Quoted(missing), StringComparison.Ordinal);
        }

        // Ronda 21, destino por contenido: the windows the request fits, by the titles they write, so the person says which.
        if (stoppedBy == "computer_use_destination_ambiguous"
            && observed["destinationCandidates"] is JsonArray { Count: > 1 } candidates
            && candidates.Select(node => FloorName(node, data)).Where(name => name is { Length: > 0 }).ToList() is { Count: > 1 } titles)
        {
            cause = T((JsonObject)data["destinationCandidates"]!, language)
                .Replace("{windows}", string.Join(", ", titles.Select(title => Quoted(title!))), StringComparison.Ordinal);
        }

        // Ronda 20 P5 (pasada r18 v3-29): a vague stop said with what its steps observed (a search that found
        // nothing). Twin of the mind's cu_projection.refined_stop.
        if (RefinedStop(observed, data) is { } refined && data["refinedStops"]?[refined] is JsonObject refinedSaid)
        {
            cause = T(refinedSaid, language);
        }

        // v3 limits (M2): a gate screen said with the text it writes (an account, a sign-in, an update, a resource),
        // and what was pressed on it: nothing, or the «Ahora no» after which it stayed.
        if (stoppedBy == "computer_use_app_gate" && observed["gate"] is JsonObject gate
            && FloorName(gate["text"], data) is { Length: > 0 } gateText
            && (string?)gate["kind"] is { } gateKind
            && (data["appGate"] as JsonObject)?[gateKind] is JsonObject gateSaid
            && data["appGateTail"] is JsonObject tails)
        {
            string tail = FloorName(gate["pressed"], data) is { Length: > 0 } pressed
                ? T((JsonObject)tails["pressed"]!, language).Replace("{pressed}", Quoted(pressed), StringComparison.Ordinal)
                : T((JsonObject)tails["untouched"]!, language);
            cause = T(gateSaid, language).Replace("{text}", Quoted(gateText), StringComparison.Ordinal)
                .Replace("{tail}", tail, StringComparison.Ordinal);
        }

        return (cause.Trim().Length > 0
            ? T(said, "cause").Replace("{head}", head, StringComparison.Ordinal)
                .Replace("{cause}", cause, StringComparison.Ordinal)
            : head) + typedLeft;
    }

    /// <summary>
    /// Pasada r15b twin of the mind's cu_finals.unanswered_sentence: «Llegué a «Opciones de energía», pero no pude
    /// leer en la pantalla la respuesta a «dime qué plan de energía está activo».» — the place the goal went to as the
    /// window writes it, else the application. Null without a place or a question.
    /// </summary>
    private static string? Unanswered(string goal, string mark, List<string> names, string app, JsonObject data, bool english)
    {
        int at = goal.IndexOf(mark, StringComparison.Ordinal);
        string asked = Regex.Replace(goal[(at + mark.Length)..], @"\s+", " ", RegexOptions.CultureInvariant)
            .Trim(' ', '.', '?', '¿', '!', '¡');
        string place = Place(goal[..at].Trim(), names, mark, data);
        place = place.Length > 0 ? place : app;
        if (asked.Length == 0 || place.Length == 0 || data["unanswered"] is not JsonObject unanswered)
        {
            return null;
        }

        return T(unanswered, english ? "en" : "es")
            .Replace("{place}", Quote(place, Templates(english)), StringComparison.Ordinal)
            .Replace("{question}", Quote(asked, Templates(english)), StringComparison.Ordinal);
    }

    /// <summary>
    /// Falsos éxitos v3 M4 (t-form-2: «No pude hacerlo en «Bloc de notas»…» after typing «casa» and «hogar» into the
    /// document): a mission that did not get there says the texts it left typed. Twin of the mind's
    /// cu_finals._typed_left.
    /// </summary>
    private static string TypedLeft(IEnumerable<JsonObject> steps, bool english, JsonObject data)
    {
        var said = (JsonObject)data[english ? "en" : "es"]!;
        // Encargo TZ-DC3 (banco zt1 c6): a text the look after it did not show («arrived» false, set by the mission's
        // MarkAppeared) is no text left typed: the final says only the rest.
        List<string> texts = steps
            .Where(step => Flag(step, "ok") == true && Text(step, "operation") == "input.text.type"
                && Flag(step, "arrived") != false)
            .Select(step => (step, text: FloorName(step["text"], data)))
            .Where(typed => typed.text.Length > 0)
            .Select(typed => TypedIntoUnnamedPart(typed.step)
                // Ronda 20 P1: a text that went into a part of a document the step did not choose says that part.
                ? T(said, "typedPart")
                    .Replace("{text}", Quote(typed.text, Templates(english)), StringComparison.Ordinal)
                    .Replace("{field}", Quote(FloorName(typed.step["into"], data), Templates(english)), StringComparison.Ordinal)
                : Quote(typed.text, Templates(english)))
            .ToList();
        // Ronda 24 (pasada r23 v3-11: «no lo abrí ni lo creé yo… no escribí nada» after «Agregar página» made «Sin
        // título»): what the mission left counts what it created too (the click's «createdDocument»), first.
        List<string> created = steps
            .Where(step => Flag(step, "ok") == true && Text(step, "operation") == "input.visible.click")
            .Select(step => (document: FloorName(step["createdDocument"], data), label: FloorName(step["label"], data)))
            .Where(made => made.document.Length > 0 && made.label.Length > 0)
            .Select(made => T(said, "createdThing")
                .Replace("{document}", Quote(made.document, Templates(english)), StringComparison.Ordinal)
                .Replace("{label}", Quote(made.label, Templates(english)), StringComparison.Ordinal))
            .ToList();
        string typed = Joined(texts, Templates(english));
        if (created.Count > 0)
        {
            return T(said, "createdLeft").Replace("{created}", Joined(created, Templates(english)), StringComparison.Ordinal)
                + (texts.Count == 0 ? string.Empty : T(said, "createdAndTyped").Replace("{texts}", typed, StringComparison.Ordinal));
        }

        return texts.Count == 0
            ? string.Empty
            : T(said, "typedLeft").Replace("{texts}", typed, StringComparison.Ordinal);
    }

    // Live 2026-10-07: «calcular 1.500 + 500» read as 1,5 + 500. A «.» followed by exactly three digits groups
    // thousands (the Chilean writing); a comma after them is the decimal one.
    private static readonly Regex CalcToken = new(
        @"[0-9]{1,3}(?:\.[0-9]{3})+(?:,[0-9]+)?(?![0-9.])|[0-9]+(?:[.,][0-9]+)?|\S", RegexOptions.CultureInvariant);

    private static readonly Regex GroupedNumber = new(@"^[0-9]{1,3}(?:\.[0-9]{3})+(?:,[0-9]+)?$", RegexOptions.CultureInvariant);

    // What a window writes of the expression itself («La expresión es 144 ÷ 12=») never proves its value.
    private static readonly Regex WrittenExpression = new(
        @"[0-9][0-9.,]*(?:\s*[-+×÷*/xX]\s*\(?\s*[0-9][0-9.,]*\)?)+\s*=?", RegexOptions.CultureInvariant);

    private const int LongestDecimals = 10;
    private static readonly string[] ScreenTextKeys = ["numbers", "lines"];
    private static readonly string[] DecimalPoints = [".", ","];
    private static readonly string[] GroupSeparators = [string.Empty, ".", ",", " ", "\u00a0"];
    private const string QuoteMarks = "«»\"“”'";

    /// <summary>
    /// Twin of the mind's cu_finals._place_said: «Ya estás en {place}» when the mission did nothing on the way (its
    /// check held on the first look; opening the application is no act there: v3 punto 5, Steam already on its
    /// library), else the place reached. A click that pressed but whose post-read did not hold is an act (review
    /// 2026-10-07: BAXY navigated there, the person was not «already» in it). Review r10a finding 1: «already» only when
    /// the check that held proves it by itself and as planned, in a window that was already open
    /// (<see cref="ProvedOnFirstLook"/>); BAXY opened it with that proof: the place reached; with none: «placeSeems».
    /// </summary>
    private static string PlaceSaid(JsonObject observed, bool english)
    {
        var data = (JsonObject)Data.Value["computerUse"]!;
        string language = english ? "en" : "es";
        if (SearchOpenedSaid(observed, english, data) is { Length: > 0 } opened)
        {
            return opened;
        }

        JsonObject[] steps = [.. (observed["steps"] as JsonArray ?? new JsonArray()).OfType<JsonObject>()];
        // An act is a step that may have changed the screen: verified, or pressed with a post-read that did not hold
        // (effectUncertain); never opening the application alone (ComputerUseMission.MayHaveActed, the one rule).
        bool acted = steps.Any(global::Baxy.App.ComputerUseMission.MayHaveActed);
        if (acted)
        {
            return T((JsonObject)data[language]!, "place");
        }

        bool launched = steps.Any(step => Text(step, "operation") == "app.open" && Flag(step, "alreadyRunning") != true);
        if (ProvedOnFirstLook(observed, (JsonObject)data["placeAlready"]!))
        {
            return launched ? T((JsonObject)data[language]!, "place") : T((JsonObject)data["placeAlready"]!, language);
        }

        return T((JsonObject)data["placeSeems"]!, launched ? language : language + "Already");
    }

    /// <summary>
    /// Ronda 24 (pasada r23, v3-14): what the screen shows of the mission's last verified click when its arrival is weak:
    /// the one value of the window in a chosen state (on, selected) whose name the click's label holds as whole words
    /// («Fecha de modificación» on, after a click on «Opción de ordenación Fecha de modificación seleccionada»). Null
    /// when no value or two relate (no guess). Twin of the mind's cu_finals._weak_seen.
    /// </summary>
    internal static (string Name, string State)? WeakSeen(IEnumerable<JsonObject> steps, IEnumerable<JsonObject> values)
    {
        JsonObject? last = steps.LastOrDefault(step => (bool?)step["ok"] == true
            && (string?)step["operation"] == "input.visible.click" && !ComputerUseSuccessCheck.OnlyOpened(step));
        string label = last is null ? string.Empty : ComputerUseSuccessCheck.Bare((string?)last["label"]);
        if (label.Length == 0)
        {
            return null;
        }

        var found = new Dictionary<string, string>(StringComparer.Ordinal);
        foreach (JsonObject item in values)
        {
            string[] states = ((string?)item["state"] ?? string.Empty).Split(' ');
            string state = states.Contains("on", StringComparer.Ordinal) ? "on"
                : states.Contains("selected", StringComparer.Ordinal) ? "selected" : string.Empty;
            string name = ((string?)item["name"] ?? string.Empty).Trim();
            string bare = ComputerUseSuccessCheck.Bare(name);
            if (state.Length > 0 && bare.Length > 0
                && Regex.IsMatch(label, $@"(?<!\w){Regex.Escape(bare)}(?!\w)", RegexOptions.CultureInvariant))
            {
                found.TryAdd(name, state);
            }
        }

        return found.Count == 1 ? (found.First().Key, found.First().Value) : null;
    }

    /// <summary>
    /// Ronda 24b (banco r23 x7, «Listo, estoy en «search»»), twin of the mind's cu_finals._search_opened_said: an
    /// arrival only a focused field proved (data «computerUse.searchOpened.atoms») is told as the search opened and the
    /// field the cursor is in (observed focusedField), never as a place reached. Null for any other proof.
    /// </summary>
    private static string? SearchOpenedSaid(JsonObject observed, bool english, JsonObject data)
    {
        var rules = (JsonObject)data["searchOpened"]!;
        JsonObject? last = (observed["subgoals"] as JsonArray)?.OfType<JsonObject>().LastOrDefault();
        string? term = last is not null ? Text(last, "satisfiedBy") : Text(observed, "satisfiedBy");
        if (!SearchOpenedProof(term, data))
        {
            return null;
        }

        string language = english ? "en" : "es";
        string field = FloorName(observed["focusedField"], data);
        return field.Length == 0
            ? T(rules, language + "NoField")
            : T(rules, language).Replace("{field}", Quote(field, Templates(english)), StringComparison.Ordinal);
    }

    /// <summary>Twin of the mind's cu_finals._search_opened_proof: a check's term proved by an atom of
    /// «computerUse.searchOpened.atoms» (a focused field).</summary>
    private static bool SearchOpenedProof(string? term, JsonObject data)
    {
        var atoms = (((JsonObject)data["searchOpened"]!)["atoms"] as JsonArray ?? []).Select(node => (string?)node)
            .ToHashSet(StringComparer.Ordinal);
        return !string.IsNullOrWhiteSpace(term)
            && term.Split('&').Any(atom => atoms.Contains(atom.Split(':', 2)[0].Trim().ToLowerInvariant()));
    }

    /// <summary>
    /// Review 1 of r24b (B1), twin of the mind's cu_finals._search_opened_clause: the clause of a chain's last part a
    /// focused field proved, the search opened and the field the cursor is in (observed focusedField).
    /// </summary>
    private static string SearchOpenedClause(JsonObject observed, bool english, JsonObject data)
    {
        var rules = (JsonObject)data["searchOpened"]!;
        string language = english ? "en" : "es";
        string field = FloorName(observed["focusedField"], data);
        return field.Length == 0
            ? T(rules, language + "ClauseNoField")
            : T(rules, language + "Clause").Replace("{field}", Quote(field, Templates(english)), StringComparison.Ordinal);
    }

    /// <summary>
    /// Ronda 22, twin of the mind's cu_finals._weakly_reached: a reached mission (or one of its reached sub-goals)
    /// whose term only the model's citation, an alternative («|») or a resemblance gave (data «weakDone»: weakTerms,
    /// weakAtoms; the mind's semantic.claims.weak_proof). A mission that carries no term keeps its final.
    /// </summary>
    private static bool WeaklyReached(JsonObject observed, List<JsonObject> subgoals, JsonObject data)
    {
        var rules = (JsonObject)data["weakDone"]!;
        var weakTerms = (rules["weakTerms"] as JsonArray ?? []).Select(node => (string?)node).ToHashSet(StringComparer.Ordinal);
        var weakAtoms = (rules["weakAtoms"] as JsonArray ?? []).Select(node => (string?)node).ToHashSet(StringComparer.Ordinal);
        List<JsonObject> reached = subgoals.Where(item => Flag(item, "reached") == true).ToList();
        IEnumerable<string?> terms = reached.Count > 0
            ? reached.Select(item => Text(item, "satisfiedBy"))
            : [Text(observed, "satisfiedBy")];
        return terms.Any(term => !string.IsNullOrWhiteSpace(term)
            && (weakTerms.Contains(term) || term.Contains('|', StringComparison.Ordinal)
                || term.Split('&').Any(atom => weakAtoms.Contains(atom.Split(':', 2)[0].Trim().ToLowerInvariant()))));
    }

    /// <summary>
    /// Twin of the mind's cu_finals._proved_on_first_look: the term that satisfied the mission's (last) check is
    /// neither the model's evidence nor an alternative (weakTerms), has no atom of an arrival by resemblance
    /// (weakAtoms), and is one of the terms the plan's check lists, not one an alias renamed.
    /// </summary>
    private static bool ProvedOnFirstLook(JsonObject observed, JsonObject rules)
    {
        JsonObject? last = (observed["subgoals"] as JsonArray)?.OfType<JsonObject>().LastOrDefault();
        string? term = last is not null ? Text(last, "satisfiedBy") : Text(observed, "satisfiedBy");
        string? check = last is not null ? Text(last, "successCheck") : Text(observed, "successCheck");
        var weakTerms = (rules["weakTerms"] as JsonArray ?? []).Select(node => (string?)node).ToHashSet(StringComparer.Ordinal);
        if (string.IsNullOrWhiteSpace(term) || weakTerms.Contains(term) || term.Contains('|', StringComparison.Ordinal)
            || Resembled(term, rules))
        {
            return false;
        }

        return (check ?? string.Empty).Split('|', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
            .Contains(term.Trim(), StringComparer.Ordinal);
    }

    /// <summary>Twin of the mind's cu_finals._resembled: the term carries an atom of an arrival by resemblance
    /// (<paramref name="rules"/>: data «placeAlready», its weakAtoms).</summary>
    private static bool Resembled(string? term, JsonObject rules) =>
        term is not null && rules["weakAtoms"] is JsonArray weak
        && term.Split('&').Any(atom => weak.Any(node =>
            string.Equals((string?)node, atom.Split(':', 2)[0].Trim(), StringComparison.OrdinalIgnoreCase)));

    /// <summary>
    /// Ronda 24b (x10), twin of the mind's _strong_arrival: a term that proves by itself where the window is (a mark of
    /// the navigation row, the window's or the page's title, a control shown selected or current). A page read by its
    /// header or a resemblance is weak.
    /// </summary>
    internal static bool StrongArrival(string? satisfiedBy)
    {
        if (string.IsNullOrWhiteSpace(satisfiedBy) || satisfiedBy == "model_evidence")
        {
            return false;
        }

        foreach (string atom in satisfiedBy.Split('&', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries))
        {
            int colon = atom.IndexOf(':', StringComparison.Ordinal);
            string kind = colon <= 0 ? string.Empty : atom[..colon].Trim().ToLowerInvariant();
            string state = atom[(atom.LastIndexOf(':') + 1)..];
            if (kind is "mark" or "title" || (kind == "control" && state is "selected" or "current"))
            {
                return true;
            }
        }

        return false;
    }

    /// <summary>
    /// Encargo H1: an opening of the mission verified that it started the application (receipt «alreadyRunning» false).
    /// Twin of the mind's cu_finals._opened_by_mission.
    /// </summary>
    internal static bool OpenedByMission(IEnumerable<JsonObject> steps) =>
        steps.Any(step => Text(step, "operation") == "app.open" && Flag(step, "ok") == true
            && Flag(step, "alreadyRunning") == false);

    /// <summary>
    /// Revisión 1 de la ronda 24b (B3), twin of the mind's _mission_launched: an opening of the mission started the
    /// application (alreadyRunning not true), so the place its first look shows is where BAXY's launch left it, never
    /// where the person already was (the rule of PlaceSaid, review r10a finding 1).
    /// </summary>
    internal static bool MissionLaunched(JsonObject observed) =>
        (observed["steps"] as JsonArray ?? new JsonArray()).OfType<JsonObject>()
            .Any(step => Text(step, "operation") == "app.open" && Flag(step, "alreadyRunning") != true);

    /// <summary>
    /// Revisión 1 de la ronda 24b (B4), twin of the mind's _mission_acted_until: whether any act of the mission came
    /// before the close of the part at <paramref name="position"/>: an earlier part that acted, or a step that may have
    /// acted (ComputerUseMission.MayHaveActed) of that part or an earlier one (its «subgoal», which a chained mission
    /// writes on every step, its opening's too). A place an act of the mission put on screen («General» selected by the click on «Opciones») was never
    /// «already» there.
    /// </summary>
    internal static bool MissionActedUntil(JsonObject observed, List<JsonObject> subgoals, int position) =>
        subgoals.Take(position).Any(item => Flag(item, "acted") == true)
        || (observed["steps"] as JsonArray ?? new JsonArray()).OfType<JsonObject>().Any(step =>
            global::Baxy.App.ComputerUseMission.MayHaveActed(step)
            && step["subgoal"] is JsonValue part && part.TryGetValue(out int index) && index <= position);

    /// <summary>
    /// Voice audit 2026-10-07 (cu-r16) twin of the mind's cu_finals._parts_final: a reached mission told part by
    /// part from its facts (data «computerUse.parts»): the places reached, the controls picked, the text typed or
    /// searched, a calculation whose value the window shows. Null when one part cannot be told. The mind also names
    /// a colour's shade («Añil, el azul de la paleta»); the App says the swatch as the window names it when the term
    /// that closed the part read it (arrivedAs: «Añil»), else as the person named it. Tied by
    /// tests/data/cu_floor_twins.json «appAndMindDiffer» (ComputerUseFloorTests).
    /// </summary>
    private static string? Parts(JsonObject observed, List<JsonObject> subgoals, string? goal, string app, bool english)
    {
        var floor = (JsonObject)Data.Value["computerUse"]!;
        var data = (JsonObject)floor["parts"]!;
        string language = english ? "en" : "es";
        var said = (JsonObject)data[language]!;
        JsonObject templates = Templates(english);
        string question = T(floor, "questionMark");
        List<(string? Goal, JsonNode? Application)> parts = subgoals.Count > 0
            ? subgoals.Select(item => (Text(item, "goal"), item["application"])).ToList()
            : (goal ?? string.Empty).Split(T(data, "chain")).Select(part => ((string?)part, observed["application"])).ToList();
        List<JsonObject> done = (observed["steps"] as JsonArray ?? new JsonArray()).OfType<JsonObject>()
            .Where(step => Flag(step, "ok") == true).ToList();
        List<string> typed = done.Where(step => Text(step, "operation") == "input.text.type" && Text(step, "text") is not null)
            .Select(step => Folded(PartObject(Text(step, "text")))).ToList();
        var screen = observed["screen"] as JsonObject;
        var names = new List<string>();
        var texts = new List<string>();
        foreach (JsonNode? candidate in done.Select(step => step["name"])
            .Concat(((screen?["values"] as JsonArray) ?? new JsonArray()).OfType<JsonObject>().Select(item => item["name"]))
            .Concat(((screen?["lines"] as JsonArray) ?? new JsonArray()).Select(line => line))
            .Append((observed["window"] as JsonObject)?["title"]))
        {
            if (FloorName(candidate, floor) is { Length: > 0 } name)
            {
                names.Add(name);
            }
        }

        foreach (string key in ScreenTextKeys)
        {
            texts.AddRange(((screen?[key] as JsonArray) ?? new JsonArray()).OfType<JsonValue>()
                .Select(value => value.TryGetValue(out string? text) ? text : null).OfType<string>());
        }

        foreach (JsonObject item in ((screen?["values"] as JsonArray) ?? new JsonArray()).OfType<JsonObject>())
        {
            texts.AddRange(new[] { Text(item, "name"), Text(item, "value") }.OfType<string>());
        }

        if (screen is not null && Text(screen, "title") is { } title)
        {
            texts.Add(title);
        }

        string Quoted(string value) => Quote(value, templates);
        string? Spelled(string asked) => names.FirstOrDefault(name => Folded(name) == Folded(asked)) is { } name
            ? CalmCaps(name)
            : null;
        // Encargo E, twin of the mind's _parts_final: a chat writes its people and channels with a sigil («@Ron92»);
        // a place is spelled as that name without it (data «parts.nameSigils»).
        string sigils = T(data, "nameSigils");
        string? Unsigiled(string asked) => names
            .Where(name => name.Length > 1 && sigils.Contains(name[0], StringComparison.Ordinal) && name[1..].Trim().Length > 0)
            .Select(name => name[1..])
            .FirstOrDefault(name => Folded(name) == Folded(asked)) is { } bare
            ? CalmCaps(bare)
            : null;
        var clauses = new List<(string Kind, string Said, string Where, bool Spelled)>();
        // Encargo E: the text each type clause wrote (the one a send part sent).
        var typedTexts = new Dictionary<int, string>();
        // Review 1 of r24b (B1): the place clauses a focused field proved (data «computerUse.searchOpened.atoms»): the
        // search opened, never a place reached. A part's proof is its sub-goal's; a goal split by the chain, the mission's.
        var opened = new HashSet<int>();
        // Ronda 24b (x10), twin of the mind's _parts_final: the clauses of places the window was already in.
        var alreadyAt = new HashSet<int>();
        string shownTitle = Text(observed["window"] as JsonObject ?? new JsonObject(), "title") ?? string.Empty;

        // Ronda 24b (x10), r30, twin of the mind's _parts_final.proved: the name the term that held read in the part's
        // window, as the window writes it (arrivedAs: the mark its check read, «Cronómetro» for «ir a stopwatch», the
        // verified click «Borrador» for «seleccionar eraser»), and whether the part was found already there. Only of a
        // part an act got there, found already there or reached on a strong term; a part reached with no act on a weak
        // term keeps the window's names only. A mission of one goal carries it itself (its arrivedAs, steps and term).
        // Revisión de r30: never from a term that arrived by resemblance («ir a language» closed on
        // «control:hora e idioma:current&similar:…»: where the window is, not that it is what was asked; the model words
        // it under the book of acts), and a pick only after an act of the part («Lápiz» found chosen with no act was
        // not picked by BAXY: «elegí» is the only sentence a pick has).
        (string? Name, bool Already) Proved(int position, bool pick = false)
        {
            bool alone = subgoals.Count == 0 && parts.Count == 1;
            JsonObject? item = position < subgoals.Count ? subgoals[position] : alone ? observed : null;
            string arrived = (item is null ? null : Text(item, "arrivedAs"))?.Trim() ?? string.Empty;
            bool acted = alone
                ? (observed["steps"] as JsonArray ?? new JsonArray()).OfType<JsonObject>().Any(global::Baxy.App.ComputerUseMission.MayHaveActed)
                : item is not null && Flag(item, "acted") == true;
            // Revisión 2 (B3): a part reached on a strong term is verified even with no act and never «already» after
            // a launch; it is told as passed through, never left out.
            bool strong = item is not null && (alone || Flag(item, "reached") == true) && StrongArrival(Text(item, "satisfiedBy"));
            // Revisión 1 (B3, B4): never when an opening of the mission launched the application (MissionLaunched) nor
            // after an act of the mission up to this part's close (MissionActedUntil).
            bool already = !alone && strong && Flag(item!, "acted") == false && position < parts.Count - 1
                && !MissionLaunched(observed) && !MissionActedUntil(observed, subgoals, position);
            bool told = (pick ? acted : acted || already || strong)
                && !Resembled(item is null ? null : Text(item, "satisfiedBy"), (JsonObject)floor["placeAlready"]!);
            return (arrived.Length > 0 && told ? CalmCaps(arrived) : null, already);
        }

        for (int position = 0; position < parts.Count; position++)
        {
            (string? rawPart, JsonNode? partApp) = parts[position];
            string part = (rawPart ?? string.Empty).Trim();
            string where = FloorName(partApp, floor) is { Length: > 0 } named ? named : app;
            if (part.Length == 0 || part.Contains(question, StringComparison.Ordinal))
            {
                return null;
            }

            if (PartMatch(data, "key", part) is not null)
            {
                // A key is never told; its application is told by another part.
                continue;
            }

            if (PartMatch(data, "mode", part) is { } moded)
            {
                string mode = ModeChosen(FloorName(JsonValue.Create(PartObject(moded)), floor), done, where, data, floor);
                if (mode.Length == 0)
                {
                    return null;
                }

                clauses.Add(("place", Quoted(mode), where, true));
                continue;
            }

            if (PlaceGoal.Value.Match(part) is { Success: true } place)
            {
                string asked = FloorName(JsonValue.Create(PartObject(place.Groups[1].Value)), floor);
                if (asked.Length == 0)
                {
                    return null;
                }

                (string? read, bool already) = Proved(position);
                string? placeSpelled = Spelled(asked) ?? Unsigiled(asked) ?? read;
                string? proof = subgoals.Count > 0
                    ? (position < subgoals.Count ? Text(subgoals[position], "satisfiedBy") : null)
                    : (position == parts.Count - 1 ? Text(observed, "satisfiedBy") : null);
                if (SearchOpenedProof(proof, floor))
                {
                    opened.Add(clauses.Count);
                }

                if (already && placeSpelled is not null)
                {
                    alreadyAt.Add(clauses.Count);
                }

                clauses.Add(("place", Quoted(placeSpelled ?? asked), where, placeSpelled is not null));
                continue;
            }

            if (PartMatch(data, "create", part) is { } createdPart)
            {
                // Revisión 2 de r24b (B2, n6), twin of the mind's _parts_final: a blank item created is told by what the
                // mission made, only as the last part and never when nothing of the mission made it.
                // Revisión 3 (B1): only the whole blank document (the data's «create» names no other part) and only a new
                // one the mission made; the offer clicked with an unnamed document in front and no proof of a new one is
                // told as chosen, as a «seleccionar» part is; anything else is no parts final.
                string askedItem = FloorName(JsonValue.Create(PartObject(createdPart)), floor);
                if (askedItem.Length == 0 || position != parts.Count - 1)
                {
                    return null;
                }

                string created = MadeDocument(done, observed, floor);
                if (created.Length > 0)
                {
                    clauses.Add(("create", T(said, "create").Replace("{items}", Quoted(created), StringComparison.Ordinal), where, true));
                    continue;
                }

                if (!OfferChosen(askedItem, done, observed, floor))
                {
                    return null;
                }

                clauses.Add(("select", Quoted(Spelled(askedItem) ?? askedItem), where, Spelled(askedItem) is not null));
                continue;
            }

            if (PartMatch(data, "select", part) is { } selected)
            {
                string asked = FloorName(JsonValue.Create(PartObject(selected)), floor);
                if (asked.Length == 0)
                {
                    return null;
                }

                string? picked = Spelled(asked) ?? Proved(position, pick: true).Name;
                clauses.Add(("select", Quoted(picked ?? asked), where, picked is not null));
                continue;
            }

            if (PartMatch(data, "click", part) is { } clickedPart)
            {
                // v3-43 r11: a click part is told by its verified click on the control it names, never as «lo hice en X».
                string asked = FloorName(JsonValue.Create(PartObject(clickedPart)), floor);
                string clicked = asked.Length == 0
                    ? string.Empty
                    : done.Where(step => Text(step, "operation") == "input.visible.click")
                        .Select(step => FloorName(step["name"], floor))
                        .FirstOrDefault(name => name.Length > 0 && Folded(name) == Folded(asked)) ?? string.Empty;
                if (clicked.Length == 0)
                {
                    return null;
                }

                string screenTitle = FloorName(screen?["title"], floor);
                clauses.Add(screenTitle.Length > 0 && Folded(screenTitle) == Folded(asked)
                    ? ("place", Quoted(screenTitle), where, true)
                    : ("click", T(said, "click").Replace("{items}", Quoted(clicked), StringComparison.Ordinal), where, true));
                continue;
            }

            if (PartMatch(data, "type", part) is { } written)
            {
                string text = PartObject(written);
                if (text.Length == 0 || !typed.Contains(Folded(text)) || where.Length == 0)
                {
                    return null;
                }

                typedTexts[clauses.Count] = text;
                clauses.Add(("type", Quoted(text), where, true));
                continue;
            }

            if (PartMatch(data, "send", part) is not null)
            {
                // Encargo E (banco i1 c6), twin of the mind's _parts_final: the send told with what it sent, never
                // «escribí» alone, only when the part held on the text the App saw sent (ProvenSent) and that text is
                // the one the part before it typed, in the same application; the place reached right before that in it
                // is who it went to.
                string? proof = subgoals.Count > 0
                    ? (position < subgoals.Count ? Text(subgoals[position], "satisfiedBy") : null)
                    : (position == parts.Count - 1 ? Text(observed, "satisfiedBy") : null);
                int last = clauses.Count - 1;
                string sent = ProvenSent(proof);
                if (last < 0 || clauses[last].Kind != "type" || clauses[last].Where != where || sent.Length == 0
                    || !typedTexts.TryGetValue(last, out string? typedText) || sent != Folded(typedText))
                {
                    return null;
                }

                string sentText = clauses[last].Said;
                clauses.RemoveAt(last);
                (string Kind, string Said, string Where, bool Spelled)? to = null;
                if (clauses.Count > 0 && clauses[^1].Kind == "place" && clauses[^1].Where == where)
                {
                    to = clauses[^1];
                    clauses.RemoveAt(clauses.Count - 1);
                }

                opened.Remove(clauses.Count);
                alreadyAt.Remove(clauses.Count);
                string sentSaid = to is { } person
                    ? T(said, "sendTo").Replace("{texts}", sentText, StringComparison.Ordinal)
                        .Replace("{place}", person.Said, StringComparison.Ordinal)
                        .Replace("{app}", Quoted(where), StringComparison.Ordinal)
                    : T(said, "send").Replace("{texts}", sentText, StringComparison.Ordinal)
                        .Replace("{app}", Quoted(where), StringComparison.Ordinal);
                clauses.Add(("send", sentSaid, where, to is not { } unspelled || unspelled.Spelled));
                continue;
            }

            if (PartMatch(data, "search", part) is { } searched)
            {
                string query = PartObject(searched);
                if (query.Length == 0 || !typed.Any(text => text.Contains(Folded(query), StringComparison.Ordinal))
                    || where.Length == 0)
                {
                    return null;
                }

                clauses.Add(("search", T(said, "search").Replace("{query}", Quoted(query), StringComparison.Ordinal)
                    .Replace("{app}", Quoted(where), StringComparison.Ordinal), where, true));
                continue;
            }

            // Only the calculating window's own display proves the value: a chain that ends in another application
            // shows that one's numbers («Línea 1, Columna 13» of the Bloc de notas). A part reached before the last
            // carries what its own window showed then (regresiones r4, v2-c2).
            List<string> own = position < subgoals.Count
                ? ((subgoals[position]["numbers"] as JsonArray) ?? new JsonArray()).OfType<JsonValue>()
                    .Select(value => value.TryGetValue(out string? text) ? text : null).OfType<string>().ToList()
                : [];
            if (PartMatch(data, "calculate", part) is not { } expression
                || where.Length == 0
                || (own.Count == 0
                    && Folded(where) != Folded(app) && !Folded(shownTitle).Contains(Folded(where), StringComparison.Ordinal))
                || CalculationShown(expression, own.Count > 0 ? own : texts, data) is not { } shown)
            {
                return null;
            }

            if (parts.Count == 1)
            {
                return T(said, "calculateAlone").Replace("{expression}", shown.Expression, StringComparison.Ordinal)
                    .Replace("{value}", shown.Value, StringComparison.Ordinal) + ".";
            }

            clauses.Add(("calculate", T(said, "calculate").Replace("{expression}", shown.Expression, StringComparison.Ordinal)
                .Replace("{value}", shown.Value, StringComparison.Ordinal), where, true));
        }

        if (clauses.Count == 0)
        {
            return null;
        }

        string placeSaid = T((JsonObject)floor[language]!, "place");
        if (clauses.Count == 1 && clauses[0].Kind == "place")
        {
            return PlaceSaid(observed, english).Replace("{place}", clauses[0].Said, StringComparison.Ordinal) + ".";
        }

        var told = new List<string>();
        // Live 2026-10-07: «ir a cotele» in Discord then «ir a tienda» in Steam came out «estoy en «TIENDA»»; a mission
        // across applications tells each place with its application.
        bool crossed = clauses.Select(clause => Folded(clause.Where)).Distinct().Count() > 1;
        for (int index = 0; index < clauses.Count; index++)
        {
            (string kind, string text, string where, bool spelled) = clauses[index];
            var run = new List<(string Said, bool Spelled)> { (text, spelled) };
            var runAt = new List<int> { index };
            while (index + 1 < clauses.Count && kind is "place" or "select" or "type"
                && clauses[index + 1].Kind == kind && clauses[index + 1].Where == where)
            {
                index++;
                run.Add((clauses[index].Said, clauses[index].Spelled));
                runAt.Add(index);
            }

            List<string> runSaid = run.Select(item => item.Said).ToList();
            if (kind == "place")
            {
                // A search a focused field proved opened is no place passed through (review 1 of r24b, B1).
                int first = index - run.Count + 1;
                List<(string Said, bool Spelled)> places = run.Where((_, offset) => !opened.Contains(first + offset)).ToList();
                if (index == clauses.Count - 1)
                {
                    // Only the places the window spelled are told as passed through; a search a focused field
                    // proved opened is none of them (review 1 of r24b, B1). Ronda 24b (x10): a place the window was
                    // already in, with no act, is told as such, never left out.
                    var before = run.Select((item, at) => (item, at: runAt[at]))
                        .Where(pair => pair.at != index && !opened.Contains(pair.at)).ToList();
                    List<string> foundThere = before
                        .Where(pair => pair.item.Spelled && alreadyAt.Contains(pair.at)).Select(pair => pair.item.Said).ToList();
                    List<string> passed = before
                        .Where(pair => pair.item.Spelled && !alreadyAt.Contains(pair.at)).Select(pair => pair.item.Said).ToList();
                    if (foundThere.Count > 0)
                    {
                        told.Add(T(said, "alreadyPlaces").Replace("{places}", Joined(foundThere, templates), StringComparison.Ordinal));
                    }

                    if (passed.Count > 0)
                    {
                        told.Add(T(said, "places").Replace("{places}", Joined(passed, templates), StringComparison.Ordinal));
                    }

                    // The last part is where the cursor is: the search opened and its field, never «ya estoy en».
                    bool now = foundThere.Count > 0 && passed.Count == 0;
                    told.Add(opened.Contains(index)
                        ? SearchOpenedClause(observed, english, floor)
                        : T(said, crossed && where.Length > 0 ? (now ? "lastPlaceInNow" : "lastPlaceIn") : (now ? "lastPlaceNow" : "lastPlace"))
                            .Replace("{place}", run[^1].Said, StringComparison.Ordinal)
                            .Replace("{app}", Quoted(where), StringComparison.Ordinal));
                }
                else if (where.Length > 0 && Folded(where) != Folded(clauses[index + 1].Where) && places.Count > 0)
                {
                    // A place in an application the mission then left is told with it.
                    told.Add(T(said, runAt.Where(at => !opened.Contains(at)).All(alreadyAt.Contains) ? "alreadyPlacesIn" : "placesIn")
                        .Replace("{places}", Joined([.. places.Select(item => item.Said)], templates), StringComparison.Ordinal)
                        .Replace("{app}", Quoted(where), StringComparison.Ordinal));
                }

                continue;
            }

            told.Add(kind switch
            {
                "select" => T(said, "select").Replace("{items}", Joined(runSaid, templates), StringComparison.Ordinal),
                "type" => T(said, "type").Replace("{texts}", Joined(runSaid, templates), StringComparison.Ordinal)
                    .Replace("{app}", Quoted(where), StringComparison.Ordinal),
                _ => text,
            });
        }

        if (told.Count == 1 && clauses[^1].Kind == "place"
            && told[0] == T(said, "lastPlace").Replace("{place}", clauses[^1].Said, StringComparison.Ordinal))
        {
            return placeSaid.Replace("{place}", clauses[^1].Said, StringComparison.Ordinal) + ".";
        }

        return T(said, "clauses").Replace("{clauses}", Joined(told, templates), StringComparison.Ordinal) + ".";
    }

    private static readonly Regex OneGenderedWord = new("^[a-z]+[oa]$", RegexOptions.CultureInvariant);

    /// <summary>
    /// Live 2026-10-07 (cu-r20) twin of the mind's cu_finals._mode_chosen: the mode a goal «activar modo X» reached
    /// by choosing it, as the window writes it without the application's name («Científica Calculadora» →
    /// «Científica», either gender); empty when no click chose it or a switch set it.
    /// </summary>
    private static string ModeChosen(string asked, List<JsonObject> done, string app, JsonObject data, JsonObject floor)
    {
        string wanted = Folded(asked);
        if (wanted.Length == 0)
        {
            return string.Empty;
        }

        var names = new HashSet<string>(StringComparer.Ordinal) { wanted };
        if (OneGenderedWord.IsMatch(wanted))
        {
            names.Add(wanted[..^1] + (wanted[^1] == 'o' ? "a" : "o"));
        }

        var appWords = new HashSet<string>(Folded(app).Split(' ', StringSplitOptions.RemoveEmptyEntries), StringComparer.Ordinal);
        var switchKinds = ((JsonArray)data["switchKinds"]!).Select(kind => (string)kind!).ToHashSet(StringComparer.Ordinal);
        string chosen = string.Empty;
        foreach (JsonObject step in done)
        {
            string name = FloorName(step["name"], floor);
            if (Text(step, "operation") != "input.visible.click" || name.Length == 0)
            {
                continue;
            }

            string mode = string.Join(' ', name.Split(' ', StringSplitOptions.RemoveEmptyEntries)
                .Where(word => !appWords.Contains(Folded(word))));
            if (mode.Length == 0 || !names.Contains(Folded(mode)))
            {
                continue;
            }

            if (Text(step, "kind") is { } kind && switchKinds.Contains(kind))
            {
                return string.Empty;
            }

            chosen = CalmCaps(mode);
        }

        return chosen;
    }

    /// <summary>
    /// Revisión 2 de r24b (B2, n6), twin of the mind's cu_finals._created_document: the document a creating part
    /// made, as its window's title writes it («Documento1» of «Documento1 - Word»). Revisión 3 (B1: a verified click
    /// whose name matched the part, on «Proyectos - Explorador de archivos» or «Informe - Word», was told «creé
    /// «Proyectos»»): only a new document proves it, never a click's name. The title names a document with no name yet
    /// (evidence «untitledDocument», «defaultDocument») and a step of the mission made exactly that one: the opening that
    /// made the new document and saw it made (ComputerUseMission.MadeNewDocument), or the click whose receipt recorded the
    /// document it created (createdDocument, ComputerUseMissionWindow.NoteCreatedDocument). Empty otherwise.
    /// </summary>
    private static string MadeDocument(List<JsonObject> done, JsonObject observed, JsonObject floor)
    {
        string title = UnnamedDocumentTitle(observed);
        if (title.Length == 0)
        {
            return string.Empty;
        }

        string document = global::Baxy.App.ComputerUseMissionWindow.DocumentKey(title);
        bool made = done.Any(step => global::Baxy.App.ComputerUseMission.MadeNewDocument(step)
            || (Text(step, "operation") == "input.visible.click" && Text(step, "createdDocument") is { Length: > 0 } createdDocument
                && global::Baxy.App.ComputerUseMissionWindow.DocumentKey(createdDocument) == document));
        if (!made)
        {
            return string.Empty;
        }

        string written = Regex.Split(title.Trim(), @"\s+[-–—|•·]\s+", RegexOptions.CultureInvariant)[0].Trim().TrimStart('*').Trim();
        return FloorName(JsonValue.Create(written), floor);
    }

    /// <summary>
    /// Revisión 3 de r24b (B1), twin of the mind's cu_finals._offer_chosen: the offer the part names was clicked and
    /// verified, and the window now shows a document with no name yet: chosen, never told as created (nothing proves
    /// the document new).
    /// </summary>
    private static bool OfferChosen(string asked, List<JsonObject> done, JsonObject observed, JsonObject floor) =>
        UnnamedDocumentTitle(observed).Length > 0
        && done.Any(step => Text(step, "operation") == "input.visible.click" && Folded(FloorName(step["name"], floor)) == Folded(asked));

    // The final window's title when it names a document with no name yet («Documento1 - Word», «Sin título - OneNote»).
    private static string UnnamedDocumentTitle(JsonObject observed)
    {
        string title = Text(observed["window"] as JsonObject ?? new JsonObject(), "title") ?? string.Empty;
        return Regex.IsMatch(title, @"\s+[-–—|]\s+", RegexOptions.CultureInvariant)
            && global::Baxy.App.ComputerUseMissionWindow.UnnamedDocument(title)
                ? title
                : string.Empty;
    }

    private static string? PartMatch(JsonObject data, string kind, string part) =>
        Regex.Match(part, T(data, kind), RegexOptions.IgnoreCase | RegexOptions.CultureInvariant) is { Success: true } found
            ? (found.Groups.Count > 1 ? found.Groups[1].Value : found.Value)
            : null;

    /// <summary>
    /// Encargo E, twin of the mind's semantic.messaging.proven_sent: the text a check that held saw sent
    /// («stepDone:input.key.press:enter&amp;sent:prueba baxy c6» → «prueba baxy c6»), folded; empty when no atom of it
    /// says so, or the term only held by one of its alternatives («|»).
    /// </summary>
    private static string ProvenSent(string? term)
    {
        if (term is null || term.Contains('|', StringComparison.Ordinal))
        {
            return string.Empty;
        }

        return term.Split('&').Select(atom => atom.Trim())
            .FirstOrDefault(atom => atom.StartsWith("sent:", StringComparison.OrdinalIgnoreCase)) is { } found
            ? Folded(found["sent:".Length..])
            : string.Empty;
    }

    private static string PartObject(string? value) =>
        Regex.Replace(value ?? string.Empty, @"\s+", " ", RegexOptions.CultureInvariant).Trim()
            .Trim((QuoteMarks + " .;:").ToCharArray());

    // The expression as said and its value as the window writes it, when «calcular E» shows E's value.
    private static (string Expression, string Value)? CalculationShown(string expression, List<string> texts, JsonObject data)
    {
        var operators = (JsonObject)data["operators"]!;
        List<string> tokens = CalcToken.Matches(expression).Select(match =>
            operators[match.Value] is JsonValue mapped ? (string)mapped! : match.Value).ToList();
        if (tokens.Count == 0 || tokens.Any(token => !(char.IsAsciiDigit(token[0]) || token is "+" or "-" or "×" or "÷" or "(" or ")")))
        {
            return null;
        }

        int position = 0;
        (System.Numerics.BigInteger N, System.Numerics.BigInteger D)? value = Sum();
        if (value is null || position != tokens.Count)
        {
            return null;
        }

        List<string> shown = texts.Select(text => WrittenExpression.Replace(
            Regex.Replace(BidiMarks.Replace(text, string.Empty), @"\s+", " ", RegexOptions.CultureInvariant).Trim(), " ")).ToList();
        foreach (string spelling in Spellings(value.Value.N, value.Value.D))
        {
            var pattern = new Regex(@"(?<![0-9.,])" + Regex.Escape(spelling) + @"(?![0-9]|[.,][0-9])", RegexOptions.CultureInvariant);
            if (shown.Any(text => pattern.IsMatch(text)))
            {
                return (string.Join(" ", tokens).Replace("( ", "(", StringComparison.Ordinal).Replace(" )", ")", StringComparison.Ordinal), spelling);
            }
        }

        return null;

        string? Peek() => position < tokens.Count ? tokens[position] : null;

        (System.Numerics.BigInteger, System.Numerics.BigInteger)? Factor()
        {
            string? token = Peek();
            if (token == "-")
            {
                position++;
                return Factor() is { } inner ? Reduced(-inner.Item1, inner.Item2) : null;
            }

            if (token == "(")
            {
                position++;
                if (Sum() is not { } inner || Peek() != ")")
                {
                    return null;
                }

                position++;
                return inner;
            }

            if (token is not null && char.IsAsciiDigit(token[0]))
            {
                position++;
                string plain = GroupedNumber.IsMatch(token) ? token.Replace(".", string.Empty, StringComparison.Ordinal) : token;
                string[] pieces = plain.Replace(',', '.').Split('.');
                System.Numerics.BigInteger scale = System.Numerics.BigInteger.Pow(10, pieces.Length > 1 ? pieces[1].Length : 0);
                return Reduced(System.Numerics.BigInteger.Parse(string.Concat(pieces), CultureInfo.InvariantCulture), scale);
            }

            return null;
        }

        (System.Numerics.BigInteger, System.Numerics.BigInteger)? Product()
        {
            var current = Factor();
            while (current is not null && Peek() is "×" or "÷")
            {
                string op = Peek()!;
                position++;
                if (Factor() is not { } right || (op == "÷" && right.Item1.IsZero))
                {
                    return null;
                }

                current = op == "×"
                    ? Reduced(current.Value.Item1 * right.Item1, current.Value.Item2 * right.Item2)
                    : Reduced(current.Value.Item1 * right.Item2, current.Value.Item2 * right.Item1);
            }

            return current;
        }

        (System.Numerics.BigInteger, System.Numerics.BigInteger)? Sum()
        {
            var current = Product();
            while (current is not null && Peek() is "+" or "-")
            {
                string op = Peek()!;
                position++;
                if (Product() is not { } right)
                {
                    return null;
                }

                System.Numerics.BigInteger numerator = op == "+"
                    ? current.Value.Item1 * right.Item2 + right.Item1 * current.Value.Item2
                    : current.Value.Item1 * right.Item2 - right.Item1 * current.Value.Item2;
                current = Reduced(numerator, current.Value.Item2 * right.Item2);
            }

            return current;
        }
    }

    private static (System.Numerics.BigInteger, System.Numerics.BigInteger) Reduced(
        System.Numerics.BigInteger numerator, System.Numerics.BigInteger denominator)
    {
        if (denominator.Sign < 0)
        {
            (numerator, denominator) = (-numerator, -denominator);
        }

        System.Numerics.BigInteger divisor = System.Numerics.BigInteger.GreatestCommonDivisor(numerator, denominator);
        return divisor.IsZero || divisor.IsOne ? (numerator, denominator) : (numerator / divisor, denominator / divisor);
    }

    // How a window may write a value: plain, with its thousands grouped, with a decimal point or comma.
    private static List<string> Spellings(System.Numerics.BigInteger numerator, System.Numerics.BigInteger denominator)
    {
        System.Numerics.BigInteger rest = denominator;
        int twos = 0, fives = 0;
        while (rest % 2 == 0)
        {
            rest /= 2;
            twos++;
        }

        while (rest % 5 == 0)
        {
            rest /= 5;
            fives++;
        }

        int decimals = Math.Max(twos, fives);
        var spellings = new List<string>();
        if (!rest.IsOne || decimals > LongestDecimals)
        {
            return spellings;
        }

        string sign = numerator.Sign < 0 ? "-" : string.Empty;
        System.Numerics.BigInteger power = System.Numerics.BigInteger.Pow(10, decimals);
        System.Numerics.BigInteger scaled = System.Numerics.BigInteger.Abs(numerator) * power / denominator;
        System.Numerics.BigInteger whole = System.Numerics.BigInteger.DivRem(scaled, power, out System.Numerics.BigInteger fraction);
        string digits = whole.ToString(CultureInfo.InvariantCulture);
        var groups = new List<string>();
        for (int end = digits.Length; end > 0; end -= 3)
        {
            groups.Insert(0, digits[Math.Max(0, end - 3)..end]);
        }

        foreach (string separator in GroupSeparators)
        {
            if (separator.Length > 0 && groups.Count < 2)
            {
                continue;
            }

            string integer = string.Join(separator, groups);
            if (decimals == 0)
            {
                spellings.Add(sign + integer);
                continue;
            }

            string tail = fraction.ToString(CultureInfo.InvariantCulture).PadLeft(decimals, '0');
            spellings.AddRange(DecimalPoints.Where(point => point != separator).Select(point => sign + integer + point + tail));
        }

        return spellings;
    }

    // The mission a turn tells: the result itself, the reason of a mission that failed on it alone, or the only step
    // of a plan (the mind's llm._computer_use_mission).
    private static JsonObject? ComputerUseMission(JsonObject situation)
    {
        const string Operation = "mission.computer.use";
        if (Text(situation, "operation") == Operation)
        {
            return situation;
        }

        string cause = (Text(situation, "cause") ?? string.Empty).Trim().ToLowerInvariant();
        List<JsonObject> steps = DecodedSteps(situation["steps"]);
        if (cause == "mission_completed")
        {
            return steps.Count == 1 && Text(steps[0], "operation") == Operation ? steps[0] : null;
        }

        return cause == "mission_failed" && (situation["steps"] as JsonArray ?? new JsonArray()).Count == 0
            && Decoded(situation["reason"]) is JsonObject reason && Text(reason, "operation") == Operation
            ? reason
            : null;
    }

    /// <summary>
    /// Ronda 20 P5: the cause a vague stop («computerUse.refinedStops.stops») had by what its steps observed, as a key of
    /// that data: «emptySearch» when a search was made and found nothing (text typed and, on it or on the key pressed
    /// right after it, a line saying nothing was found among what appeared: «evidence.noResults» or
    /// «emptySearch.afterSearch») and no step after it but one of «emptySearch.passes»; null otherwise. A click after the
    /// search left it, and a line with no search before it is a state of the window (revisión 1 de r20 P5, hallazgo 4).
    /// Twin of the mind's cu_projection.refined_stop.
    /// </summary>
    internal static string? RefinedStop(JsonObject observed, JsonObject computerUse)
    {
        ArgumentNullException.ThrowIfNull(observed);
        ArgumentNullException.ThrowIfNull(computerUse);
        if (computerUse["refinedStops"] is not JsonObject rule
            || rule["emptySearch"] is not JsonObject empty
            || Text(observed, "stoppedBy") is not { } stoppedBy
            || !(rule["stops"] as JsonArray ?? new JsonArray()).Any(stop => (string?)stop == stoppedBy))
        {
            return null;
        }

        List<JsonObject> done = (observed["steps"] as JsonArray ?? new JsonArray()).OfType<JsonObject>()
            .Where(step => Flag(step, "ok") == true).ToList();
        Regex[] nothingFound =
        [
            new((string)EvidenceRules["noResults"]!, RegexOptions.CultureInvariant),
            new((string)empty["afterSearch"]!, RegexOptions.CultureInvariant),
        ];
        HashSet<string> passes = (empty["passes"] as JsonArray ?? new JsonArray())
            .Select(item => (string?)item).OfType<string>().ToHashSet(StringComparer.Ordinal);
        for (int index = done.Count - 1; index >= 0; index--)
        {
            string? operation = Text(done[index], "operation");
            if ((done[index]["appeared"] as JsonArray ?? new JsonArray()).Any(line =>
                    line is JsonValue value && value.TryGetValue(out string? said)
                    && said is not null && nothingFound.Any(regex => regex.IsMatch(Folded(said)))))
            {
                bool searched = operation == "input.text.type"
                    || (operation == "input.key.press" && index > 0 && Text(done[index - 1], "operation") == "input.text.type");
                return searched ? "emptySearch" : null;
            }

            if (operation is null || !passes.Contains(operation))
            {
                return null;
            }
        }

        return null;
    }

    /// <summary>The words the judge of the model's «done» reads (data «computerUse.evidence»).</summary>
    internal static JsonObject EvidenceRules => (JsonObject)((JsonObject)Data.Value["computerUse"]!)["evidence"]!;

    internal static JsonObject ComputerUseData => (JsonObject)Data.Value["computerUse"]!;

    /// <summary>A reached place whose question the window did not answer (data «computerUse.unanswered»).</summary>
    internal static JsonObject UnansweredRules => (JsonObject)((JsonObject)Data.Value["computerUse"]!)["unanswered"]!;

    /// <summary>The question a goal carries after «; y responder: » (data «computerUse.questionMark»).</summary>
    internal static string QuestionMark => T((JsonObject)Data.Value["computerUse"]!, "questionMark");

    /// <summary>
    /// A name a loading indicator carries on any control (data «computerUse.loading», over a folded name): «Cargando».
    /// Twin of the mind's screen-value filter (computer_use.seen_from_observed).
    /// </summary>
    internal static bool NamesLoading(string? foldedName) =>
        !string.IsNullOrWhiteSpace(foldedName) && LoadingName.Value.IsMatch(foldedName);

    /// <summary>
    /// A name a ProgressBar carries while its window is not drawn yet (data «computerUse.loadingBar», over a folded
    /// name): those of <see cref="NamesLoading"/> and «Ocupado»/«Busy», which on any other control are a fact (review
    /// of fable/cu-v3-carga-preguntas, finding 4).
    /// </summary>
    internal static bool NamesLoadingBar(string? foldedName) =>
        !string.IsNullOrWhiteSpace(foldedName) && LoadingBarName.Value.IsMatch(foldedName);

    /// <summary>
    /// Ronda 20 P1 (v3-11 t2): a step written at the caret whose receipt says the text went into a part of a document
    /// other than its body (data «computerUse.documentPart» over the folded «into»). Such a text reached no sub-goal,
    /// and the final says where it went. «into» is what had the keyboard on the view before the step: a step that chose
    /// its field («field») was delivered there by the provider, wherever the keyboard was (review of r20 P1, finding 2),
    /// and so was one given the index of the field the sub-goal's last click aimed at. An index read from the focus
    /// («atCaret», <see cref="ComputerUseMission.NoteWhereTheTextGoes"/>) is no choice of the step (review 2, finding 1:
    /// the worker gives window.focused its «i», so every text at the caret carried one). Twin of
    /// cu_finals._typed_into_unnamed_part.
    /// </summary>
    internal static bool TypedIntoUnnamedPart(JsonObject step)
    {
        if (!string.IsNullOrWhiteSpace(Text(step, "field")) || (step["index"] is not null && Flag(step, "atCaret") != true)
            || Flag(step, "intoDocument") == true)
        {
            return false;
        }

        string into = Folded(Text(step, "into") ?? string.Empty);
        return into.Length > 0 && DocumentPart.Value.IsMatch(into);
    }

    /// <summary>
    /// Review 3 of r20 P1 (B1): the control's name is the one the window's title gives its document, at its start or
    /// after a separator, then perhaps the file's extension and a separator or the end («Proyecto de título.docx -
    /// Word», «Sin título: Bloc de notas»): the document itself, never a part of it, whatever words the person's file
    /// name holds («Seminario de Título», «Cover letter header»). Twin of cu_text_place._names_the_window.
    /// </summary>
    internal static bool NamesTheWindow(string? name, string? title)
    {
        string folded = Folded(WithoutFormat(name));
        string whole = Folded(WithoutFormat(title));
        if (folded.Length == 0 || whole.Length == 0)
        {
            return false;
        }

        const string separator = @"\s*[-–—|:]\s";
        return Regex.IsMatch(
            whole, $@"(?:^|{separator}){Regex.Escape(folded)}(?:\.\w{{1,5}})?(?:{separator}|\s*$)", RegexOptions.CultureInvariant);
    }

    // Format characters out (a browser writes a zero-width space inside its own name in its titles), as the mind's _window_fold.
    private static string WithoutFormat(string? value) =>
        string.Concat((value ?? string.Empty).Where(character => CharUnicodeInfo.GetUnicodeCategory(character) != UnicodeCategory.Format));

    private static readonly Lazy<Regex> DocumentPart = new(() => new Regex(
        T((JsonObject)Data.Value["computerUse"]!, "documentPart"), RegexOptions.CultureInvariant));

    private static readonly Lazy<Regex> LoadingName = new(() => new Regex(
        T((JsonObject)Data.Value["computerUse"]!, "loading"), RegexOptions.CultureInvariant));

    private static readonly Lazy<Regex> LoadingBarName = new(() => new Regex(
        T((JsonObject)Data.Value["computerUse"]!, "loadingBar"), RegexOptions.CultureInvariant));

    /// <summary>
    /// cu-v3-elevacion: whether the request asks to open with administrator rights («abrí el administrador de tareas
    /// como administrador», «open services as admin»): one of the data's cues («administratorAsked.cues») as whole
    /// words of the folded request. Only then does app.open keep the shell's path (MindArgumentNormalization).
    /// </summary>
    internal static bool AdministratorAsked(string? request)
    {
        if (string.IsNullOrWhiteSpace(request))
            return false;
        string words = " " + Regex.Replace(Folded(request), @"[^\p{L}\p{N}]+", " ", RegexOptions.CultureInvariant).Trim() + " ";
        return ((JsonArray)((JsonObject)Data.Value["administratorAsked"]!)["cues"]!)
            .Select(cue => (string?)cue)
            .Any(cue => !string.IsNullOrWhiteSpace(cue) && words.Contains(" " + Folded(cue!) + " ", StringComparison.Ordinal));
    }

    /// <summary>The X of a goal «ir a X» (data «computerUse.placeGoal»), or empty when the goal is no place.</summary>
    internal static string PlaceAsked(string? goal)
    {
        var data = (JsonObject)Data.Value["computerUse"]!;
        return goal is null || goal.Contains(T(data, "questionMark"), StringComparison.Ordinal)
            || PlaceGoal.Value.Match(goal.Trim()) is not { Success: true } found
            ? string.Empty
            : FloorName(JsonValue.Create(found.Groups[1].Value), data);
    }

    // The place a goal «ir a X» went to, spelled as the window wrote it when one of its names is X.
    private static string Place(string? goal, List<string> names, string question, JsonObject data)
    {
        if (goal is null || goal.Contains(question, StringComparison.Ordinal)
            || PlaceGoal.Value.Match(goal.Trim()) is not { Success: true } found)
        {
            return string.Empty;
        }

        string asked = FloorName(JsonValue.Create(found.Groups[1].Value), data);
        return names.FirstOrDefault(name => Folded(name) == Folded(asked)) is { } spelled ? CalmCaps(spelled) : asked;
    }

    // A name the window writes in capitals («TIENDA», read off the screen) told with only its first letter so; an
    // acronym («VPN», «HDMI») keeps them. Twin of the mind's cu_goals._calm_caps.
    private static string CalmCaps(string name)
    {
        int longest = (int)((JsonObject)((JsonObject)Data.Value["computerUse"]!)["parts"]!)["capsWord"]!;
        List<char> letters = name.Where(char.IsLetter).ToList();
        int run = 0, widest = 0;
        foreach (char letter in name)
        {
            run = char.IsLetter(letter) ? run + 1 : 0;
            widest = Math.Max(widest, run);
        }

        if (letters.Count == 0 || letters.Any(letter => !char.IsUpper(letter)) || widest < longest)
        {
            return name;
        }

        return name[..1] + name[1..].ToLowerInvariant();
    }

    private static string FloorName(JsonNode? node, JsonObject data)
    {
        if (node is not JsonValue value || !value.TryGetValue(out string? raw) || raw is null)
        {
            return string.Empty;
        }

        string text = Regex.Replace(BidiMarks.Replace(raw, string.Empty), @"\s+", " ", RegexOptions.CultureInvariant)
            .Trim().Trim(' ', '.', ';', ':');
        int longest = data["longestName"]!.GetValue<int>();
        return text.Length > 0 && text.Length <= longest && !text.Contains('«') && !text.Contains('»')
            ? text
            : string.Empty;
    }

    // The mind's semantic.missions.fold: case and accents out, spaces collapsed.
    private static string Folded(string value)
    {
        string decomposed = value.ToLowerInvariant().Normalize(System.Text.NormalizationForm.FormKD);
        string bare = string.Concat(decomposed.Where(character =>
            CharUnicodeInfo.GetUnicodeCategory(character) != UnicodeCategory.NonSpacingMark));
        return Regex.Replace(bare, @"\s+", " ", RegexOptions.CultureInvariant).Trim();
    }

    private static string? NonEmpty(JsonObject node, string key) =>
        Text(node, key) is { } text && text.Length > 0 ? text : null;

    private static string Mission(
        JsonObject situation, string cause, bool english, JsonObject templates, TimeProvider clock)
    {
        List<JsonObject> steps = DecodedSteps(situation["steps"]);
        var told = new List<string>();
        // Ronda 22 (r18 t4-c19): a quiet read is only what an effect needed; in a failed mission it is never told as
        // done, even alone, so its list of windows the request never named stays out (twin of operation_floor).
        bool quietOut = steps.Count > 1 || cause != "mission_completed";
        foreach (JsonObject step in steps)
        {
            if (quietOut && Entry(step)?["quiet"] is JsonValue quiet && quiet.TryGetValue(out bool isQuiet)
                && isQuiet)
            {
                continue;
            }

            string clause = Step(step, english, templates, clock);
            if (clause.Length > 0)
            {
                told.Add(clause);
            }
        }

        if (cause == "mission_completed")
        {
            return Joined(told, templates);
        }

        JsonObject? reason = Decoded(situation["reason"]) as JsonObject;
        if (reason is not null && !string.IsNullOrEmpty(Text(reason, "operation")) && Text(reason, "kind") == "failure")
        {
            // Ronda 22 (r18 t4-c19): the plan's own failure names the step it stopped at, told as not done.
            reason = (JsonObject)reason.DeepClone();
            reason["kind"] = "operation";
        }

        string failed = reason is not null && !string.IsNullOrEmpty(Text(reason, "operation"))
            ? Step(reason, english, templates, clock)
            : string.Empty;
        if (told.Count == 0)
        {
            // Nothing done before: the failed step is the whole report, or there is no action to name.
            return failed;
        }

        if (failed.Length == 0)
        {
            failed = T(templates, "rest");
        }

        bool uncertain = reason is not null && Uncertain(reason);
        return Joined(told, templates) + T(templates, uncertain ? "and" : "but") + failed;
    }

    private static string Step(JsonObject step, bool english, JsonObject templates, TimeProvider clock)
    {
        JsonObject? entry = Entry(step);
        if (entry is null)
        {
            return string.Empty;
        }

        string language = english ? "en" : "es";
        JsonObject observed = Observed(step);
        if (Flag(step, "verified") == true && Flag(step, "succeeded") == true)
        {
            if (Flag(entry, "noSuccessFloor") == true)
            {
                return string.Empty;
            }

            // Ronda 22 (r18 t4-c07): «is» true picks a receipt that found the state already there (reachedState).
            // Estabilización M2: a «told» wording with no «key» is always the receipt's (a memory result).
            if (entry["told"] is JsonObject toldWording
                && (Text(toldWording, "key") is not { } toldKey
                    || Flag(observed, toldKey) == (Flag(toldWording, "is") ?? false))
                && toldWording["values"] is JsonObject toldValues)
            {
                // v3 r6 lectores: the wording picks by the observed field the data names («state» of a radio already
                // on or off), or by «kind».
                string by = Text(toldWording, "by") ?? "kind";
                JsonNode? picked = observed[by];
                string pickedKey = picked is JsonValue flag && flag.GetValueKind() is JsonValueKind.True or JsonValueKind.False
                    ? (flag.GetValue<bool>() ? "true" : "false")
                    : Text(observed, by) ?? string.Empty;
                JsonObject said = toldValues[pickedKey] as JsonObject
                    ?? (JsonObject)toldValues[string.Empty]!;
                string told = Filled(Text(said, language) ?? string.Empty, observed)
                    ?? Text((JsonObject)toldValues[string.Empty]!, language) ?? string.Empty;
                return told.Replace(
                    "{object}", ObjectNamed(entry, observed, language, templates, target: null), StringComparison.Ordinal);
            }

            JsonObject? variant = Variant(entry, observed);
            string clause = (string)((JsonArray)(variant ?? entry)[language]!)[1]!
                + ObjectNamed(entry, observed, language, templates, target: null);
            if (Flag(entry, "when") == true)
            {
                clause += When(step, observed, templates, clock);
            }

            return T(templates, "done").Replace(
                "{clause}", clause + Detail(entry, variant, observed, language, templates), StringComparison.Ordinal);
        }

        if (Text(step, "polarity") == "pending")
        {
            return string.Empty;
        }

        // Only a verified result picks its variant by what it observed (muted, on, the kind set): a state read
        // beside a failure is the one that held, not the one asked.
        string attempted = AttemptedClause(entry, step, observed, language, templates);
        // M116: a read that only looked for what an effect needed (the window to place) is told by the effect it
        // left undone — «no pude colocar la ventana «Obsidian» a la izquierda» — when the facts carry it.
        if (Flag(entry, "quiet") == true && step["notDone"] is JsonArray notDone)
        {
            var undone = new List<string>();
            foreach (JsonObject item in notDone.OfType<JsonObject>())
            {
                if (Text(item, "operation") is { } undoneOperation
                    && Data.Value["operations"] is JsonObject operations
                    && operations[undoneOperation] is JsonObject undoneEntry
                    && AttemptedClause(undoneEntry, item, new JsonObject(), language, templates) is { Length: > 0 } said)
                {
                    undone.Add(said);
                }
            }

            if (undone.Count > 0)
            {
                attempted = Joined(undone, templates);
            }
        }

        return T(templates, Uncertain(step) ? "uncertain" : "failed")
            .Replace("{clause}", attempted, StringComparison.Ordinal);
    }

    // The plain clause of a step not done, with what it was about and, since M116, what it attempted: the client and
    // the side said in words, the message's text quoted (data «attempted» and «content»).
    private static string AttemptedClause(
        JsonObject entry, JsonObject step, JsonObject observed, string language, JsonObject templates)
    {
        // Revisión F (H5, r31 B2): the variant the step asked for (the setting) words it, with that variant's facts
        // (the level asked); twin of operation_floor._attempted_clause.
        JsonObject? asked = step["attempted"] as JsonObject;
        JsonObject? variant = asked is null ? null : Variant(entry, asked);
        string clause = (string)((JsonArray)(variant ?? entry)[language]!)[0]!
            + ObjectNamed(entry, observed, language, templates, step["target"] is JsonValue target
                && target.TryGetValue(out string? targetText) ? targetText : null);
        if (asked is not JsonObject attempted)
        {
            return clause;
        }

        foreach (JsonObject spec in ((JsonArray)Data.Value["attempted"]!).OfType<JsonObject>())
        {
            if (Text(attempted, Text(spec, "key")!) is { } value
                && spec["values"] is JsonObject values
                && values[value] is JsonObject said)
            {
                clause += " " + Text(said, language);
            }
        }

        List<string> facts = variant?["facts"] is JsonArray variantFacts
            ? variantFacts.OfType<JsonObject>().Select(item => Fact(item, attempted, language))
                .Where(static item => item.Length > 0).ToList()
            : [];
        if (facts.Count > 0)
        {
            return clause + T(templates, "detail") + string.Join(T(templates, "list"), facts);
        }

        foreach (JsonNode? key in (JsonArray)Data.Value["content"]!)
        {
            string text = Usable(attempted[(string)key!], LongestContent);
            if (text.Length > 0)
            {
                return clause + T(templates, "detail") + Quote(text, templates);
            }
        }

        return clause;
    }

    // Revisión F (H5): a told wording with its observed fields ({value}) filled, «{object}» kept; null when one is
    // not observed (twin of operation_floor._filled).
    private static string? Filled(string text, JsonObject observed)
    {
        foreach (string name in Regex.Matches(text, @"\{(\w+)\}").Select(match => match.Groups[1].Value)
            .Where(static name => name != "object").Distinct())
        {
            string? value = observed[name] is JsonValue node ? node.GetValueKind() switch
            {
                JsonValueKind.Number => node.TryGetValue(out long whole)
                    ? whole.ToString(CultureInfo.InvariantCulture)
                    : node.GetValue<double>().ToString("G6", CultureInfo.InvariantCulture),
                JsonValueKind.String => node.GetValue<string>(),
                _ => null,
            } : null;
            if (string.IsNullOrEmpty(value))
            {
                return null;
            }

            text = text.Replace("{" + name + "}", value, StringComparison.Ordinal);
        }

        return text;
    }

    private static bool Uncertain(JsonObject step) =>
        Flag(step, "effectUncertain") == true
        || (Flag(step, "succeeded") == true && Flag(step, "verified") != true);

    private static JsonObject? Entry(JsonObject step)
    {
        if (step.ContainsKey("kind") && Text(step, "kind") != "operation" && !VerifiedStatusOfAnOperation(step))
        {
            return null;
        }

        return Text(step, "operation") is { } operation && Data.Value["operations"] is JsonObject operations
            ? operations[operation] as JsonObject
            : null;
    }

    // Estabilización M (live identity check §3e: a verified «olvida todo lo que sabes de mí» ended «No pude contarte cómo
    // salió lo que pediste.»): the private memory says its verified results as status facts that name their operation
    // (MemoryOperationResponseProjection); they are an operation's result all the same. Twin: operation_floor.py.
    private static bool VerifiedStatusOfAnOperation(JsonObject step) =>
        Text(step, "kind") == "status" && Text(step, "operation") is not null
        && Flag(step, "verified") == true && Flag(step, "succeeded") == true;

    // The variant of the operation the observation names (muted or not, on or off, the kind set), if any.
    private static JsonObject? Variant(JsonObject entry, JsonObject observed)
    {
        if (entry["variants"] is not JsonObject variants || Text(variants, "key") is not { } key)
        {
            return null;
        }

        JsonNode? value = observed[key];
        string chosenKey = value is JsonValue flag && flag.GetValueKind() is JsonValueKind.True or JsonValueKind.False
            ? (flag.GetValue<bool>() ? "true" : "false")
            : value is JsonValue number && number.GetValueKind() == JsonValueKind.Number
                ? number.ToJsonString()
                : Text(observed, key) ?? string.Empty;
        if (variants["values"] is not JsonObject values || values[chosenKey] is not JsonObject chosen)
        {
            return null;
        }

        // Encargo I2: a variant may pick again by another field (a setting's switch by the value set: «activé», never
        // «cambié»), keeping what it says itself (its facts) under the inner one. Twin: operation_floor._variant.
        if (Variant(chosen, observed) is not { } inner)
        {
            return chosen;
        }

        JsonObject merged = (JsonObject)chosen.DeepClone();
        foreach ((string name, JsonNode? node) in inner)
        {
            merged[name] = node?.DeepClone();
        }

        return merged;
    }

    private static string Usable(JsonNode? node, int longest = LongestName)
    {
        if (node is not JsonValue value || !value.TryGetValue(out string? raw) || raw is null)
        {
            return string.Empty;
        }

        string text = Regex.Replace(raw.Trim(), @"\s+", " ", RegexOptions.CultureInvariant);
        return text.Length == 0 || text.Length > longest || text.Contains('«') || text.Contains('»')
            ? string.Empty
            : text;
    }

    private static string Quote(string value, JsonObject templates) =>
        T(templates, "quote").Replace("{value}", value, StringComparison.Ordinal);

    // What was acted on: the step's target when it names one, else the first identifying field observed, and who
    // made it when the read names them. Nothing for an operation whose target is no name to say.
    private static string ObjectNamed(
        JsonObject entry, JsonObject observed, string language, JsonObject templates, string? target)
    {
        if (Flag(entry, "anonymous") == true)
        {
            return string.Empty;
        }

        JsonObject data = Data.Value;
        // Ronda 22 revisión 2 (r18 t2-c18, t3-c15): a receipt that reports the object acted on as a record of its own
        // (data «objectIn»: the snapped «window») is named from that record too. Twin of operation_floor._object.
        JsonObject[] sources = Text(entry, "objectIn") is { Length: > 0 } objectIn
            && observed[objectIn] is JsonObject nested
                ? [observed, nested]
                : [observed];
        IEnumerable<JsonNode?> candidates = target is not null
            ? [JsonValue.Create(target)]
            : sources.SelectMany(source => ((JsonArray)data["identity"]!).Select(key => source[(string)key!]));
        foreach (JsonNode? candidate in candidates)
        {
            string text = Usable(candidate);
            if (text.Length == 0)
            {
                continue;
            }

            string named = " " + Quote(text, templates);
            string? word = entry["objectWord"] is JsonObject words ? Text(words, language) : null;
            JsonObject byline = (JsonObject)data["byline"]!;
            string author = Usable(observed[Text(byline, "key")!]);
            string by = author.Length > 0
                ? Text(byline, language)!.Replace("{value}", author, StringComparison.Ordinal)
                : string.Empty;
            return (word is { Length: > 0 } ? $" {word}{named}" : named) + by;
        }

        return string.Empty;
    }

    private static string When(JsonObject step, JsonObject observed, JsonObject templates, TimeProvider clock)
    {
        DateTimeOffset? due = Utc(Text(observed, "dueUtc"));
        if (Text(step, "operation") == "notification.schedule")
        {
            due = due is null ? null : Utc(Text(observed, "nextRunUtc"));
        }

        if (due is not { } instant)
        {
            return string.Empty;
        }

        DateTimeOffset local = instant.ToLocalTime();
        DateTime today = clock.GetUtcNow().ToLocalTime().Date;
        string article = T(templates, local.Hour == 1 ? "articleOne" : "article");
        string hhmm = local.ToString("HH:mm", CultureInfo.InvariantCulture);
        string said = local.Date == today
            ? T(templates, "whenToday")
            : local.Date == today.AddDays(1) ? T(templates, "whenTomorrow") : T(templates, "whenDate");
        said = said
            .Replace("{article}", article, StringComparison.Ordinal)
            .Replace("{clock}", hhmm, StringComparison.Ordinal)
            .Replace("{day}", local.Day.ToString(CultureInfo.InvariantCulture), StringComparison.Ordinal)
            .Replace("{month}", (string)((JsonArray)templates["months"]!)[local.Month - 1]!, StringComparison.Ordinal);
        return " " + Regex.Replace(said.Trim(), @"\s+", " ", RegexOptions.CultureInvariant);
    }

    private static DateTimeOffset? Utc(string? value) =>
        !string.IsNullOrWhiteSpace(value)
        && DateTimeOffset.TryParse(
            value.Trim(), CultureInfo.InvariantCulture, DateTimeStyles.AssumeUniversal, out DateTimeOffset parsed)
            ? parsed
            : null;

    private static string Detail(
        JsonObject entry, JsonObject? variant, JsonObject observed, string language, JsonObject templates)
    {
        var facts = new List<string>();
        string attached = string.Empty;
        IEnumerable<JsonNode?> specs = (entry["facts"] as JsonArray ?? new JsonArray())
            .Concat(variant?["facts"] as JsonArray ?? new JsonArray())
            .Concat((JsonArray)Data.Value["facts"]!);
        foreach (JsonNode? spec in specs)
        {
            if (spec is JsonObject fact && Fact(fact, observed, language) is { Length: > 0 } said)
            {
                // Ronda 22 revisión 2 (r18 t3-c15): a fact that completes the clause («a la izquierda», data
                // «attached») follows it with a space, never after the detail separator. Twin of _detail.
                if (Flag(fact, "attached") == true)
                {
                    attached += " " + said;
                }
                else
                {
                    facts.Add(said);
                }
            }
        }

        if (Content(entry, observed, templates) is { Length: > 0 } content)
        {
            facts.Add(content);
        }

        if (facts.Count > 0)
        {
            return attached + T(templates, "detail") + string.Join(T(templates, "list"), facts);
        }

        if (attached.Length > 0)
        {
            return attached;
        }

        // v3 r5a M3 (v3-43, v3-44): a mission's steps are no list it read. Twin of operation_floor._detail.
        string listed = Flag(entry, "noListing") == true ? string.Empty : Listing(observed, templates);
        return listed.Length > 0 ? T(templates, "listDetail") + listed : string.Empty;
    }

    private static string Fact(JsonObject fact, JsonObject observed, string language)
    {
        JsonNode? node = observed[Text(fact, "key")!];
        if (fact["values"] is JsonObject values)
        {
            return Text(observed, Text(fact, "key")!) is { } key && values[key] is JsonObject said
                ? Text(said, language) ?? string.Empty
                : string.Empty;
        }

        JsonArray texts = (JsonArray)fact[language]!;
        if (node is not JsonValue value)
        {
            return string.Empty;
        }

        switch (value.GetValueKind())
        {
            case JsonValueKind.True:
            case JsonValueKind.False:
                return texts.Count == 2 ? (string)texts[value.GetValue<bool>() ? 0 : 1]! : string.Empty;
            case JsonValueKind.Number:
                string number = value.TryGetValue(out long whole)
                    ? whole.ToString(CultureInfo.InvariantCulture)
                    : value.GetValue<double>().ToString("G6", CultureInfo.InvariantCulture);
                return ((string)texts[0]!).Replace("{value}", number, StringComparison.Ordinal);
            default:
                string text = Usable(value);
                return text.Length > 0 && texts.Count == 1
                    ? ((string)texts[0]!).Replace("{value}", text, StringComparison.Ordinal)
                    : string.Empty;
        }
    }

    private static string Content(JsonObject entry, JsonObject observed, JsonObject templates)
    {
        if (Flag(entry, "content") != true)
        {
            return string.Empty;
        }

        foreach (JsonNode? key in (JsonArray)Data.Value["content"]!)
        {
            string text = Usable(observed[(string)key!], LongestContent);
            if (text.Length > 0)
            {
                return T(templates, "content").Replace("{value}", Quote(text, templates), StringComparison.Ordinal);
            }
        }

        return string.Empty;
    }

    private static string Listing(JsonObject observed, JsonObject templates)
    {
        JsonObject data = Data.Value;
        long? count = null;
        foreach (JsonNode? key in (JsonArray)data["listCounts"]!)
        {
            if (Integer(observed[(string)key!]) is { } found)
            {
                count = found;
                break;
            }
        }

        foreach ((string key, JsonNode? node) in observed)
        {
            if (node is not JsonArray items)
            {
                continue;
            }

            var names = new List<string>();
            foreach (JsonNode? item in items)
            {
                string name = item is JsonObject record
                    ? ((JsonArray)data["listNames"]!)
                        .Select(field => Usable(record[(string)field!]))
                        .FirstOrDefault(said => said.Length > 0) ?? string.Empty
                    : Usable(item);
                if (name.Length > 0 && !names.Contains(name, StringComparer.Ordinal))
                {
                    names.Add(name);
                }
            }

            if (names.Count == 0)
            {
                // An empty list beside others («failures»: []) is not the read's answer; only its count says nothing.
                continue;
            }

            long total = count ?? Integer(observed[key + "Count"]) ?? items.Count;

            string listed = Joined(names.Take(ListedNames).Select(name => Quote(name, templates)).ToList(), templates);
            return T(templates, total == 1 ? "countOne" : "countNamed")
                .Replace("{count}", total.ToString(CultureInfo.InvariantCulture), StringComparison.Ordinal)
                .Replace("{names}", listed, StringComparison.Ordinal);
        }

        if (count == 0)
        {
            return T(templates, "none");
        }

        return count is { } counted
            ? T(templates, "count").Replace("{count}", counted.ToString(CultureInfo.InvariantCulture),
                StringComparison.Ordinal)
            : string.Empty;
    }

    private static long? Integer(JsonNode? node) =>
        node is JsonValue value && value.GetValueKind() == JsonValueKind.Number && value.TryGetValue(out long whole)
            ? whole
            : null;

    private static string Joined(List<string> parts, JsonObject templates) =>
        parts.Count <= 1
            ? string.Concat(parts)
            : string.Join(T(templates, "list"), parts.Take(parts.Count - 1)) + T(templates, "and") + parts[^1];

    private static string? Sentence(string text)
    {
        text = text.Trim();
        if (text.Length == 0)
        {
            return null;
        }

        int lead = text.Length - text.TrimStart('«', '¿', '¡', '"', '\'').Length;
        if (lead < text.Length)
        {
            text = text[..lead] + char.ToUpper(text[lead], CultureInfo.InvariantCulture) + text[(lead + 1)..];
        }

        return text.EndsWith('.') || text.EndsWith('!') || text.EndsWith('?') ? text : text + ".";
    }

    private static JsonObject Templates(bool english) =>
        (JsonObject)((JsonObject)Data.Value["templates"]!)[english ? "en" : "es"]!;

    private static string T(JsonObject templates, string key) => (string)templates[key]!;

    private static JsonNode? Decoded(JsonNode? node)
    {
        if (node is JsonValue value && value.TryGetValue(out string? text) && text.TrimStart().StartsWith('{'))
        {
            try
            {
                return JsonNode.Parse(text);
            }
            catch (JsonException)
            {
                return null;
            }
        }

        return node;
    }

    private static List<JsonObject> DecodedSteps(JsonNode? steps) =>
        steps is JsonArray items
            ? items.Select(Decoded).OfType<JsonObject>().ToList()
            : [];

    // The observation with its read-back state lifted (state/final: muted, level), as the mind's _observed does.
    private static JsonObject Observed(JsonObject step)
    {
        if (step["observed"] is not JsonObject observed)
        {
            return new JsonObject();
        }

        var lifted = (JsonObject)observed.DeepClone();
        JsonObject? state = observed["state"] as JsonObject ?? observed["final"] as JsonObject;
        if (state is not null)
        {
            if (state.ContainsKey("muted"))
            {
                lifted["muted"] = state["muted"]?.DeepClone();
            }

            JsonNode? level = state.ContainsKey("volumePercent") ? state["volumePercent"] : state["level"];
            if (level is not null && !observed.ContainsKey("level"))
            {
                lifted["level"] = level.DeepClone();
            }
        }

        return lifted;
    }

    private static string? Text(JsonObject node, string key) =>
        node[key] is JsonValue value && value.TryGetValue(out string? text) ? text : null;

    private static bool? Flag(JsonObject node, string key) =>
        node[key] is JsonValue value && value.TryGetValue(out bool flag) ? flag : null;
}
