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
        }

        return null;
    }

    /// <summary>
    /// Live 2026-10-07 («en el Explorador de archivos andá a Documentos y creá una carpeta…» → the person read
    /// «⚠ (internal_code;retry_exhausted)»): the line a composition that every draft failed leaves when no floor tells
    /// it, by what the turn was (data: compositionFailures). The diagnostic code stays in the private log.
    /// </summary>
    internal static string? CompositionFailureSentence(string intent, bool english)
    {
        if (Data.Value["compositionFailures"] is not JsonObject lines)
        {
            return null;
        }

        string kind = intent switch
        {
            "clarification" => "clarification",
            "status" or "error" => "result",
            _ => "default",
        };
        return lines[kind] is JsonObject said ? Text(said, english ? "en" : "es") : null;
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
        string text;
        if (cause is "mission_completed" or "mission_failed")
        {
            text = Mission(situation, cause, english, templates, clock ?? TimeProvider.System);
        }
        else if (Text(situation, "kind") != "operation")
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

    private static readonly Lazy<Regex> PlaceGoal = new(() => new Regex(
        T((JsonObject)Data.Value["computerUse"]!, "placeGoal"),
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant));

    /// <summary>
    /// Live 2026-10-07 twin of the mind's computer_use.floor_sentence (data «computerUse»): a computer-use mission the
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
        if (goal is not null && goal.Contains(question, StringComparison.Ordinal))
        {
            // «… y decime si el modo es claro u oscuro»: the answer is the mind's to read from the window.
            return null;
        }

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
        string app = FloorName(observed["application"], data) is { Length: > 0 } application
            ? application
            : FloorName(window?["title"], data);
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

            string reached = Place(subgoals.Count > 0 ? Text(subgoals[^1], "goal") : goal, names, question, data);
            if (reached.Length > 0)
            {
                return T(said, "place").Replace("{place}", Quoted(reached), StringComparison.Ordinal);
            }

            return app.Length > 0 ? T(said, "app").Replace("{app}", Quoted(app), StringComparison.Ordinal) : null;
        }

        JsonObject? unreached = subgoals.FirstOrDefault(item => Flag(item, "reached") != true);
        string place = Place((unreached is null ? null : Text(unreached, "goal")) ?? goal, names, question, data);
        string head = place.Length > 0
            ? T(said, "notPlace").Replace("{place}", Quoted(place), StringComparison.Ordinal)
            : app.Length > 0
                ? T(said, "notApp").Replace("{app}", Quoted(app), StringComparison.Ordinal)
                : T(said, "not");
        string? stoppedBy = Text(observed, "stoppedBy");
        if (stoppedBy is null || (data["causes"] as JsonObject)?[stoppedBy] is not JsonObject causes)
        {
            // An untyped stop code is never said as prose.
            return head;
        }

        string cause = Text(causes, language) ?? string.Empty;
        JsonObject? cover = window?["coveredBy"] as JsonObject;
        string? coveredBy = cover is null ? null : (NonEmpty(cover, "title") ?? NonEmpty(cover, "process"));
        if (stoppedBy == "computer_use_window_covered" && coveredBy is not null)
        {
            cause = T((JsonObject)data["coveredBy"]!, language).Replace("{window}", coveredBy, StringComparison.Ordinal);
        }

        if (stoppedBy == "computer_use_place_not_found" && FloorName(observed["missingPlace"], data) is { Length: > 0 } missing)
        {
            cause = T((JsonObject)data["placeNotFound"]!, language).Replace("{place}", Quoted(missing), StringComparison.Ordinal);
        }

        return cause.Trim().Length > 0
            ? T(said, "cause").Replace("{head}", head, StringComparison.Ordinal)
                .Replace("{cause}", cause, StringComparison.Ordinal)
            : head;
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
        return names.FirstOrDefault(name => Folded(name) == Folded(asked)) ?? asked;
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
        foreach (JsonObject step in steps)
        {
            if (steps.Count > 1 && Entry(step)?["quiet"] is JsonValue quiet && quiet.TryGetValue(out bool isQuiet)
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

            if (entry["unchanged"] is JsonObject unchanged
                && Text(unchanged, "key") is { } unchangedKey
                && Flag(observed, unchangedKey) == false
                && unchanged["values"] is JsonObject unchangedValues)
            {
                JsonObject said = unchangedValues[Text(observed, "kind") ?? string.Empty] as JsonObject
                    ?? (JsonObject)unchangedValues[string.Empty]!;
                return Text(said, language) ?? string.Empty;
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
        string clause = (string)((JsonArray)entry[language]!)[0]!
            + ObjectNamed(entry, observed, language, templates, step["target"] is JsonValue target
                && target.TryGetValue(out string? targetText) ? targetText : null);
        if (step["attempted"] is not JsonObject attempted)
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

    private static bool Uncertain(JsonObject step) =>
        Flag(step, "effectUncertain") == true
        || (Flag(step, "succeeded") == true && Flag(step, "verified") != true);

    private static JsonObject? Entry(JsonObject step)
    {
        if (step.ContainsKey("kind") && Text(step, "kind") != "operation")
        {
            return null;
        }

        return Text(step, "operation") is { } operation && Data.Value["operations"] is JsonObject operations
            ? operations[operation] as JsonObject
            : null;
    }

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
            : Text(observed, key) ?? string.Empty;
        return variants["values"] is JsonObject values ? values[chosenKey] as JsonObject : null;
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
        IEnumerable<JsonNode?> candidates = target is not null
            ? [JsonValue.Create(target)]
            : ((JsonArray)data["identity"]!).Select(key => observed[(string)key!]);
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
        IEnumerable<JsonNode?> specs = (entry["facts"] as JsonArray ?? new JsonArray())
            .Concat(variant?["facts"] as JsonArray ?? new JsonArray())
            .Concat((JsonArray)Data.Value["facts"]!);
        foreach (JsonNode? spec in specs)
        {
            if (spec is JsonObject fact && Fact(fact, observed, language) is { Length: > 0 } said)
            {
                facts.Add(said);
            }
        }

        if (Content(entry, observed, templates) is { Length: > 0 } content)
        {
            facts.Add(content);
        }

        if (facts.Count > 0)
        {
            return T(templates, "detail") + string.Join(T(templates, "list"), facts);
        }

        string listed = Listing(observed, templates);
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
