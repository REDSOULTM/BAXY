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

    /// <summary>The sentence for one operation result or one mission, or null when there is no action to tell.</summary>
    internal static string? Final(JsonObject situation, bool english, TimeProvider? clock = null)
    {
        ArgumentNullException.ThrowIfNull(situation);
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
        string attempted = (string)((JsonArray)entry[language]!)[0]!
            + ObjectNamed(entry, observed, language, templates, step["target"] is JsonValue target
                && target.TryGetValue(out string? targetText) ? targetText : null);
        return T(templates, Uncertain(step) ? "uncertain" : "failed")
            .Replace("{clause}", attempted, StringComparison.Ordinal);
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
