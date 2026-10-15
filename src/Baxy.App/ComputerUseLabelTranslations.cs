using System.Globalization;
using System.IO;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace Baxy.App;

/// <summary>
/// The labels the mind translated with the local model (CONTRATO_VISTA_ACCION.md §4.4.1): a place said in one
/// language and shown in the other, whose names the mind's table does not know. Kept in the shell's data root,
/// so the mind stays stateless: each step request carries only the entry of the
/// label its goal names. The mission writes here only when a sub-goal closes: a translation it reached its place
/// through is kept as seen (seenOnScreen, and the name in onScreen, armed as an alias of later missions' checks so a
/// click on the shown name still proves the place said); one clicked in vain, or that no look of the sub-goal showed, counts
/// one rejection per mission, and three in a row forget it (the next time the model is asked again). The mind's
/// table goes first: the mind never translates, nor reads this cache for, a label the table knows.
/// </summary>
internal sealed class ComputerUseLabelTranslations
{
    internal const int ForgetAfterRejections = 3;
    private const int MaximumLabels = 512;
    private const int MaximumNames = 4;
    private readonly string _path;
    private JsonObject? _document;

    internal ComputerUseLabelTranslations(string path)
    {
        _path = path ?? throw new ArgumentNullException(nameof(path));
    }

    internal static ComputerUseLabelTranslations CreateDefault() =>
        new(Path.Combine(MemoryOperationProtector.ResolveDataRoot(), "computer-use", "label-translations.v1.json"));

    /// <summary>The stored entry of a label (folded), or null.</summary>
    internal JsonObject? Find(string label) =>
        Labels()[ComputerUseSuccessCheck.Fold(label).Trim()] as JsonObject;

    /// <summary>
    /// What the step request carries for <paramref name="goal"/>: the entry of the longest stored label the goal
    /// names as whole words ({label: {names: […]}}), or null. Only the names travel.
    /// </summary>
    internal JsonObject? EntryFor(string? goal)
    {
        string? best = LabelNamedBy(goal, "names");
        return best is null
            ? null
            : new JsonObject { [best] = new JsonObject { ["names"] = Labels()[best]!["names"]!.DeepClone() } };
    }

    /// <summary>
    /// The names of the longest stored label the goal names as whole words that an earlier mission reached through
    /// (<c>onScreen</c>), or null: the mission arms them as aliases of its check from the start, so a click on
    /// that name still proves the place said.
    /// </summary>
    internal (string Label, List<string> Names)? ConfirmedFor(string? goal)
    {
        string? best = LabelNamedBy(goal, "onScreen");
        return best is null ? null : (best, NamesOf(Labels()[best]!.AsObject(), "onScreen").ToList());
    }

    // The longest stored label, among those with a non-empty array <paramref name="field"/>, the goal names whole.
    private string? LabelNamedBy(string? goal, string field)
    {
        string folded = " " + ComputerUseSuccessCheck.Fold(goal).Trim() + " ";
        string? best = null;
        foreach ((string label, JsonNode? entry) in Labels())
        {
            if (entry is JsonObject { } stored && stored[field] is JsonArray { Count: > 0 }
                && label.Length > 0 && folded.Contains(" " + label + " ", StringComparison.Ordinal)
                && (best is null || label.Length > best.Length))
            {
                best = label;
            }
        }

        return best;
    }

    /// <summary>
    /// The sub-goal reached its place through the translation <paramref name="to"/> of <paramref name="label"/> (the
    /// mission calls this only then, never when a translation was merely clicked): kept first and as seen on screen.
    /// </summary>
    internal void Seen(string label, IEnumerable<string> names, string to)
    {
        string key = ComputerUseSuccessCheck.Fold(label).Trim();
        if (key.Length == 0 || string.IsNullOrWhiteSpace(to))
        {
            return;
        }

        JsonObject labels = Labels();
        JsonObject entry = labels[key] as JsonObject ?? new JsonObject();
        // The name seen first, then the ones already known and the ones just given, without repeats.
        var kept = new List<string>();
        foreach (string name in new[] { to }.Concat(NamesOf(entry)).Concat(names))
        {
            if (!string.IsNullOrWhiteSpace(name) && kept.Count < MaximumNames
                && !kept.Any(known => ComputerUseSuccessCheck.Fold(known) == ComputerUseSuccessCheck.Fold(name)))
            {
                kept.Add(name.Trim());
            }
        }

        entry["names"] = new JsonArray([.. kept.Select(name => (JsonNode?)JsonValue.Create(name))]);
        var reached = NamesOf(entry, "onScreen").ToList();
        if (!reached.Any(known => ComputerUseSuccessCheck.Fold(known) == ComputerUseSuccessCheck.Fold(to)) && reached.Count < MaximumNames)
        {
            reached.Add(to.Trim());
        }

        entry["onScreen"] = new JsonArray([.. reached.Select(name => (JsonNode?)JsonValue.Create(name))]);
        entry["seenOnScreen"] = ((int?)entry["seenOnScreen"] ?? 0) + 1;
        entry["rejected"] = 0;
        entry["learnedUtc"] ??= DateTimeOffset.UtcNow.ToString("O", CultureInfo.InvariantCulture);
        entry["lastSeenUtc"] = DateTimeOffset.UtcNow.ToString("O", CultureInfo.InvariantCulture);
        Put(labels, key, entry);
    }

    /// <summary>
    /// The translation of <paramref name="label"/> was not on screen: one more rejection; the third in a row forgets
    /// it. A translation not stored yet is kept with its first rejection, so the model is not asked again at once.
    /// </summary>
    internal void Rejected(string label, IEnumerable<string> names)
    {
        string key = ComputerUseSuccessCheck.Fold(label).Trim();
        if (key.Length == 0)
        {
            return;
        }

        JsonObject labels = Labels();
        JsonObject entry = labels[key] as JsonObject ?? new JsonObject
        {
            ["names"] = new JsonArray([.. names.Where(name => !string.IsNullOrWhiteSpace(name)).Take(MaximumNames)
                .Select(name => (JsonNode?)JsonValue.Create(name.Trim()))]),
            ["seenOnScreen"] = 0,
            ["learnedUtc"] = DateTimeOffset.UtcNow.ToString("O", CultureInfo.InvariantCulture),
        };
        int rejected = ((int?)entry["rejected"] ?? 0) + 1;
        if (rejected >= ForgetAfterRejections)
        {
            labels.Remove(key);
            Save(Load());
            return;
        }

        entry["rejected"] = rejected;
        Put(labels, key, entry);
    }

    private static IEnumerable<string> NamesOf(JsonObject entry, string field = "names") =>
        entry[field] is JsonArray names
            ? names.Select(name => name is JsonValue value && value.TryGetValue(out string? text) ? text : null)
                .Where(text => !string.IsNullOrWhiteSpace(text)).Select(text => text!)
            : [];

    private void Put(JsonObject labels, string key, JsonObject entry)
    {
        if (entry.Parent is null)
        {
            labels[key] = entry;
        }

        while (labels.Count > MaximumLabels)
        {
            labels.Remove(labels.First().Key);
        }

        Save(Load());
    }

    private JsonObject Labels()
    {
        JsonObject document = Load();
        if (document["labels"] is not JsonObject labels)
        {
            labels = new JsonObject();
            document["labels"] = labels;
        }

        return labels;
    }

    private JsonObject Load()
    {
        if (_document is not null)
        {
            return _document;
        }

        try
        {
            if (File.Exists(_path)
                && new FileInfo(_path).Length <= 1024 * 1024
                && JsonNode.Parse(File.ReadAllText(_path)) is JsonObject stored
                && (int?)stored["version"] == 1)
            {
                _document = stored;
                return stored;
            }
        }
        catch (Exception exception) when (exception is IOException or JsonException or UnauthorizedAccessException or InvalidOperationException)
        {
        }

        _document = new JsonObject { ["version"] = 1, ["labels"] = new JsonObject() };
        return _document;
    }

    private void Save(JsonObject document)
    {
        try
        {
            Directory.CreateDirectory(Path.GetDirectoryName(_path)!);
            string temporary = _path + "." + Guid.NewGuid().ToString("N") + ".tmp";
            File.WriteAllText(temporary, document.ToJsonString(), new UTF8Encoding(false));
            File.Move(temporary, _path, overwrite: true);
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
        }
    }
}
