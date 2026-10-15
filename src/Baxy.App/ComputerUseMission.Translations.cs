using System.Globalization;
using System.Text.Json.Nodes;

namespace Baxy.App;

// The labels the mind translated (§4.4.1): noted, seen, weakened by similarity and settled when the sub-goal closes.
internal static partial class ComputerUseMission
{
    /// <summary>
    /// A step the mind took on a translated label (§4.4.1), noted in the mission's state «translations» (by folded
    /// label: names, whether any was on screen, the alias clicked and its step). A click whose alias names what the
    /// view shows extends the mission's check (state «aliases», read by <see cref="ComputerUseSuccessCheck.Evaluate"/>);
    /// an alias the view does not show extends nothing. Nothing is learned here: the cache hears of the translation
    /// only when the sub-goal closes (<see cref="SettleTranslations"/>), once it is known whether the click got there.
    /// </summary>
    internal static void NoteTranslation(JsonObject state, MindComputerUseStep decision, JsonObject? view, int step, int subgoal)
    {
        string? from = (string?)decision.Alias?["from"];
        string? to = (string?)decision.Alias?["to"];
        string label = ComputerUseSuccessCheck.Fold((string?)decision.Translation?["label"] ?? from).Trim();
        if (label.Length == 0)
        {
            return;
        }

        JsonObject noted = state["translations"] as JsonObject ?? new JsonObject();
        state["translations"] = noted;
        if (noted[label] is not JsonObject entry || (bool?)entry["settled"] == true)
        {
            entry = new JsonObject { ["names"] = new JsonArray(), ["seen"] = false, ["subgoal"] = subgoal };
            noted[label] = entry;
        }

        JsonArray names = (JsonArray)entry["names"]!;
        IEnumerable<string> given = decision.Translation?["names"] is JsonArray reported ? Texts(reported).ToList() : [];
        foreach (string name in given.Append(to ?? string.Empty))
        {
            if (!string.IsNullOrWhiteSpace(name)
                && !Texts(names).Any(known => ComputerUseSuccessCheck.Fold(known) == ComputerUseSuccessCheck.Fold(name)))
            {
                names.Add((JsonNode?)JsonValue.Create(name.Trim()));
            }
        }

        if (decision.Translation is not null)
        {
            // Only a translation the mind looked up may count a rejection; an alias armed from the cache never does.
            entry["reported"] = true;
        }

        if (view is not null && Texts(names).Any(name => ComputerUseSuccessCheck.ViewContains(view, name)))
        {
            entry["seen"] = true;
        }

        if (decision.Operation == "input.visible.click" && view is not null
            && !string.IsNullOrWhiteSpace(from) && !string.IsNullOrWhiteSpace(to)
            && ComputerUseSuccessCheck.ViewContains(view, to))
        {
            AddAlias(state, from, to);
            entry["to"] = to;
            entry["step"] = step;
            entry.Remove("failed");
            // Review r10a finding 5: a name picked by resemblance (the mind's encoder, alias «by: semantic») that no
            // translation of the model gave is no translation confirmed: an arrival through it is weak.
            bool similar = (string?)decision.Alias?["by"] == SimilarAliasSource
                && !given.Any(name => ComputerUseSuccessCheck.Fold(name) == ComputerUseSuccessCheck.Fold(to));
            JsonArray marked = state["similarAliases"] as JsonArray ?? new JsonArray();
            if (similar && !Texts(marked).Contains(ComputerUseSuccessCheck.Fold(to), StringComparer.Ordinal))
            {
                marked.Add((JsonNode?)JsonValue.Create(ComputerUseSuccessCheck.Fold(to)));
            }

            state["similarAliases"] = marked;
        }
    }

    /// <summary>The mind's mark of an alias picked by resemblance (cu_meaning.SOURCE_SEMANTIC).</summary>
    internal const string SimilarAliasSource = "semantic";

    /// <summary>The atom kind that marks an arrival through a name picked by resemblance (data
    /// «computerUse.placeAlready.weakAtoms», semantic.claims.weak_proof): it never proves by itself.</summary>
    internal const string SimilarAtom = "similar";

    /// <summary>
    /// Review r10a finding 5: the check held through an alias the encoder picked by resemblance, with nothing else to
    /// back it (no translation of the model named it; the term that held is no title nor header of the window): the
    /// term is marked «&amp;similar:{name}», so the arrival is weak (no «Ya estás en», the book of
    /// acts judges the final) and the cache never keeps it as a translation seen. Any other term comes back as it is.
    /// </summary>
    internal static string? WeakenedBySimilarity(JsonObject state, string? check, string? satisfiedBy)
    {
        if (string.IsNullOrWhiteSpace(satisfiedBy) || satisfiedBy == "model_evidence"
            || state["similarAliases"] is not JsonArray { Count: > 0 } marked)
        {
            return satisfiedBy;
        }

        var planned = (check ?? string.Empty).Split('|', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
        string[] atoms = satisfiedBy.Split('&', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
        if (planned.Contains(satisfiedBy, StringComparer.Ordinal)
            || atoms.Any(atom => AtomKindOf(atom) is "title" or "header"))
        {
            return satisfiedBy;
        }

        string folded = ComputerUseSuccessCheck.Fold(satisfiedBy);
        string? through = Texts(marked).FirstOrDefault(name => folded.Contains(name, StringComparison.Ordinal));
        return through is null ? satisfiedBy : $"{satisfiedBy}&{SimilarAtom}:{through}";
    }

    /// <summary>
    /// Pasada v3 r9 (v3-42): which term of the planned check held, as a trace label with no content (the trace keeps
    /// stable labels only): «term.{n}.{kinds}» for the n-th alternative of the check (its atom kinds joined by «-»,
    /// «-similar» when a resemblance weakened it), «alias.{kinds}» for one held through a name the place carries on
    /// screen, «model_evidence», or «none». Read live with the check the mission planned, it says what passed.
    /// </summary>
    internal static string SatisfiedLabel(string? check, string? satisfiedBy)
    {
        if (string.IsNullOrWhiteSpace(satisfiedBy))
        {
            return "none";
        }

        if (satisfiedBy == "model_evidence")
        {
            return satisfiedBy;
        }

        string[] planned = (check ?? string.Empty).Split('|', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
        string kinds = string.Join('-', satisfiedBy
            .Split('&', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
            .Select(atom => new string(AtomKindOf(atom).Where(char.IsAsciiLetterLower).ToArray()))
            .Where(kind => kind.Length > 0));
        int term = Array.FindIndex(planned, said =>
            satisfiedBy == said || satisfiedBy.StartsWith(said + "&" + SimilarAtom + ":", StringComparison.Ordinal));
        string label = term >= 0
            ? $"term.{(term + 1).ToString(CultureInfo.InvariantCulture)}.{kinds}"
            : $"alias.{kinds}";
        return label.Length > 48 ? label[..48] : label;
    }

    internal static string AtomKindOf(string atom)
    {
        int colon = atom.IndexOf(':', StringComparison.Ordinal);
        return colon <= 0 ? string.Empty : atom[..colon].Trim().ToLowerInvariant();
    }

    /// <summary>
    /// The translation this mission already looked up for the label <paramref name="goal"/> names ({label: {names}}),
    /// while the cache has none yet: the next step's request carries it, so the model is asked once per mission and
    /// label, not once per step (nothing reaches the cache before the sub-goal closes).
    /// </summary>
    internal static JsonObject? NotedEntryFor(JsonObject state, string? goal)
    {
        if (state["translations"] is not JsonObject noted)
        {
            return null;
        }

        string folded = " " + ComputerUseSuccessCheck.Fold(goal).Trim() + " ";
        string? best = null;
        foreach ((string label, JsonNode? node) in noted)
        {
            if (node is JsonObject entry && (bool?)entry["settled"] != true && entry["names"] is JsonArray { Count: > 0 }
                && label.Length > 0 && folded.Contains(" " + label + " ", StringComparison.Ordinal)
                && (best is null || label.Length > best.Length))
            {
                best = label;
            }
        }

        return best is null
            ? null
            : new JsonObject { [best] = new JsonObject { ["names"] = noted[best]!["names"]!.DeepClone() } };
    }

    /// <summary>Ronda 24: every name a translation noted in this mission gave a label (the place's names in the window's language).</summary>
    internal static IEnumerable<string> TranslatedNames(JsonObject state) =>
        (state["translations"] as JsonObject ?? new JsonObject())
            .Select(entry => entry.Value?["names"] as JsonArray ?? [])
            .SelectMany(names => names.Select(name => (string?)name))
            .OfType<string>()
            .ToList();

    /// <summary>A look that shows any name of a translation noted in this sub-goal: it was on screen.</summary>
    internal static void NoteTranslationsSeen(JsonObject state, JsonObject view)
    {
        if (state["translations"] is not JsonObject noted)
        {
            return;
        }

        foreach ((string _, JsonNode? node) in noted)
        {
            if (node is JsonObject entry && (bool?)entry["settled"] != true && (bool?)entry["seen"] != true
                && entry["names"] is JsonArray names && Texts(names).Any(name => ComputerUseSuccessCheck.ViewContains(view, name)))
            {
                entry["seen"] = true;
            }
        }
    }

    /// <summary>
    /// The click on a translated name failed: its alias stops extending the check (a name that could not be pressed
    /// proves nothing), and the sub-goal's close counts it as a rejection.
    /// </summary>
    internal static void NoteTranslatedClick(JsonObject state, JsonObject record)
    {
        if ((string?)record["operation"] != "input.visible.click" || (bool?)record["ok"] == true
            || state["translations"] is not JsonObject noted)
        {
            return;
        }

        foreach ((string label, JsonNode? node) in noted)
        {
            if (node is JsonObject entry && (bool?)entry["settled"] != true && (int?)entry["step"] == (int?)record["step"]
                && (string?)entry["to"] is { Length: > 0 } to)
            {
                RemoveAlias(state, label, to);
                entry["failed"] = true;
            }
        }
    }

    /// <summary>
    /// The sub-goal closed: each translation noted in it is settled once. Reached through an alias (its check held on
    /// a term the alias renamed), the name it reached through is kept in the cache as seen. A click on an alias that
    /// failed, or that the sub-goal did not reach through, counts one rejection and the alias is dropped; so does a
    /// translation the mind looked up whose names no look of the sub-goal showed. At most one rejection per label and
    /// mission: the steps before the place appears (the start page, the search, Enter) are no evidence against it.
    /// </summary>
    internal static void SettleTranslations(
        ComputerUseLabelTranslations? cache, JsonObject state, string? check, bool reached, string? satisfiedBy)
    {
        if (state["translations"] is not JsonObject noted)
        {
            return;
        }

        var planned = new HashSet<string>(
            (check ?? string.Empty).Split('|', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries),
            StringComparer.Ordinal);
        bool throughAlias = reached && satisfiedBy is { Length: > 0 } && satisfiedBy != "model_evidence"
            && !planned.Contains(satisfiedBy);
        JsonArray rejected = state["translationsRejected"] as JsonArray ?? new JsonArray();
        state["translationsRejected"] = rejected;
        foreach ((string label, JsonNode? node) in noted.ToList())
        {
            if (node is not JsonObject entry || (bool?)entry["settled"] == true)
            {
                continue;
            }

            entry["settled"] = true;
            List<string> names = entry["names"] is JsonArray given ? [.. Texts(given)] : [];
            string? to = (string?)entry["to"];
            bool failed = (bool?)entry["failed"] == true;
            List<string> candidates = entry["armed"] is JsonArray armed ? [.. Texts(armed)] : [];
            if (to is { Length: > 0 } && !failed)
            {
                candidates.Insert(0, to);
            }

            string? through = throughAlias
                ? candidates.FirstOrDefault(name => ComputerUseSuccessCheck.Fold(satisfiedBy).Contains(
                    ComputerUseSuccessCheck.Fold(name), StringComparison.Ordinal))
                : null;
            if (through is not null)
            {
                // Review r10a finding 5: reached through a name picked by resemblance alone (marked «similar:»), it
                // is no translation confirmed: neither kept as seen nor counted against it.
                if (!satisfiedBy!.Split('&').Any(atom => AtomKindOf(atom) == SimilarAtom))
                {
                    cache?.Seen(label, names, through);
                }

                continue;
            }

            bool clickedInVain = to is { Length: > 0 } && (failed || !reached);
            if (clickedInVain)
            {
                RemoveAlias(state, label, to!);
            }

            bool unseen = (bool?)entry["reported"] == true && (bool?)entry["seen"] != true && names.Count > 0;
            if ((clickedInVain || unseen) && !Texts(rejected).Contains(label, StringComparer.Ordinal))
            {
                rejected.Add((JsonNode?)JsonValue.Create(label));
                cache?.Rejected(label, names);
            }
        }
    }

    /// <summary>
    /// The translations of the sub-goal's label that earlier missions reached through are aliases from the start
    /// (a later click on «Fecha y hora» must still hold the check «control:date and time»).
    /// Such an armed alias is never counted against: only a translation the mind looks up again can be rejected.
    /// </summary>
    internal static void ArmConfirmedTranslations(
        ComputerUseLabelTranslations? translations, JsonObject state, string goal, int subgoal)
    {
        if (translations?.ConfirmedFor(goal) is not { } confirmed || confirmed.Names.Count == 0)
        {
            return;
        }

        JsonObject noted = state["translations"] as JsonObject ?? new JsonObject();
        state["translations"] = noted;
        foreach (string name in confirmed.Names)
        {
            AddAlias(state, confirmed.Label, name);
        }

        noted[confirmed.Label] = new JsonObject
        {
            ["names"] = new JsonArray([.. confirmed.Names.Select(name => (JsonNode?)JsonValue.Create(name))]),
            ["armed"] = new JsonArray([.. confirmed.Names.Select(name => (JsonNode?)JsonValue.Create(name))]),
            ["seen"] = false,
            ["subgoal"] = subgoal,
        };
    }

    private static void AddAlias(JsonObject state, string from, string to)
    {
        JsonObject aliases = state["aliases"] as JsonObject ?? new JsonObject();
        string key = ComputerUseSuccessCheck.Fold(from).Trim();
        JsonArray targets = aliases[key] as JsonArray ?? new JsonArray();
        if (!Texts(targets).Any(known => ComputerUseSuccessCheck.Fold(known) == ComputerUseSuccessCheck.Fold(to)))
        {
            targets.Add((JsonNode?)JsonValue.Create(to));
        }

        aliases[key] = targets;
        state["aliases"] = aliases;
    }

    private static void RemoveAlias(JsonObject state, string from, string to)
    {
        if (state["aliases"] is not JsonObject aliases
            || aliases[ComputerUseSuccessCheck.Fold(from).Trim()] is not JsonArray targets)
        {
            return;
        }

        foreach (JsonNode? node in targets.ToList())
        {
            if (node is JsonValue value && value.TryGetValue(out string? text)
                && ComputerUseSuccessCheck.Fold(text) == ComputerUseSuccessCheck.Fold(to))
            {
                targets.Remove(node);
            }
        }
    }

    private static IEnumerable<string> Texts(JsonArray array) =>
        array.Select(node => node is JsonValue value && value.TryGetValue(out string? text) ? text : null)
            .Where(text => !string.IsNullOrWhiteSpace(text)).Select(text => text!);

    // ------------------------------------------------------------ the view
}
