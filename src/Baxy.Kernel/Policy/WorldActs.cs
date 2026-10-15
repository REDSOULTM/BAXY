using System.Text.Json;
using System.Text.RegularExpressions;

namespace Baxy.Kernel.Policy;

/// <summary>
/// The words a control's label says when its click leaves the computer or reaches another person: sending, publishing,
/// sharing, joining, calling, going live. One source, in data (src/baxy_mind/data/world_acts.v1.json, embedded), read
/// here by <see cref="RiskPolicy"/> and by the mind (semantic/account_acts.world_act); the file's own examples tie both
/// readers in their tests. Each family says where its words count: anywhere in the label as whole words, as its first
/// word whatever follows, or as its first word and at most three more.
/// </summary>
internal static class WorldActs
{
    private const string Resource = "Baxy.Kernel.WorldActs.json";

    private static readonly Lazy<Words> Loaded = new(Load);

    /// <summary>A trailing shortcut hint of a label («Enviar (Ctrl+Enter)»), which never hides its verb.</summary>
    internal static Regex ShortcutHint => Loaded.Value.ShortcutHint;

    /// <summary>The labels the data itself gives as asking and as free: the contract both readers are tested on.</summary>
    internal static (IReadOnlyList<string> Asks, IReadOnlyList<string> Free) Examples =>
        (Loaded.Value.Asks, Loaded.Value.Free);

    /// <summary>Whether a folded label names an act that leaves the computer or reaches a person.</summary>
    internal static bool Reaches(string folded) => Loaded.Value.Families.Any(family => family.Matches(folded));

    /// <summary>Whether a folded label joins a call, a voice channel or a meeting (the data's «joins»).</summary>
    internal static bool Joins(string folded) => Loaded.Value.Joins.Any(family => family.Matches(folded));

    /// <summary>The family (its «name» in the data) of the first family a folded label matches, or null.</summary>
    internal static string? FamilyOf(string folded) =>
        Loaded.Value.Families.FirstOrDefault(family => family.Matches(folded))?.Name;

    /// <summary>Each family as its pattern and its exception, for the one pattern the UIA worker is handed.</summary>
    internal static IEnumerable<(string Pattern, string? Unless)> Rules =>
        Loaded.Value.Families.Select(family => (family.Pattern.ToString(), family.Unless?.ToString()));

    private sealed record Family(string Name, string Where, string[] Said, Regex Pattern, Regex? Unless)
    {
        internal bool Matches(string folded) => Pattern.IsMatch(folded) && Unless?.IsMatch(folded) != true;
    }

    private sealed record Words(
        Regex ShortcutHint, Family[] Families, Family[] Joins, IReadOnlyList<string> Asks, IReadOnlyList<string> Free);

    private static Words Load()
    {
        using Stream stream = typeof(WorldActs).Assembly.GetManifestResourceStream(Resource)
            ?? throw new InvalidOperationException(Resource);
        using JsonDocument document = JsonDocument.Parse(stream);
        JsonElement root = document.RootElement;
        Family[] families = [.. root.GetProperty("families").EnumerateArray().Select(Read)];
        string[] joining = Strings(root.GetProperty("joins"));
        // A family that joins by its first word joins whatever follows it («Join the meeting of the whole team»), unless its
        // exception says otherwise («Abandonar llamada»).
        Family[] joins =
        [
            .. families.Where(family => joining.Contains(family.Name, StringComparer.Ordinal))
                .Select(family => family.Where == "anywhere" ? family : family with { Pattern = Compile(Shape("first", family.Said)) }),
        ];
        JsonElement examples = root.GetProperty("examples");
        return new Words(
            Compile(root.GetProperty("shortcutHint").GetString()!), families, joins,
            Strings(examples.GetProperty("asks")), Strings(examples.GetProperty("free")));
    }

    private static Family Read(JsonElement family)
    {
        string where = family.GetProperty("where").GetString()!;
        string[] said = Strings(family.GetProperty("words"));
        Regex? unless = family.TryGetProperty("unless", out JsonElement pattern) ? Compile(pattern.GetString()!) : null;
        return new Family(family.GetProperty("name").GetString()!, where, said, Compile(Shape(where, said)), unless);
    }

    private static string Shape(string where, string[] said)
    {
        string words = string.Join('|', said.Select(Regex.Escape));
        return where switch
        {
            "anywhere" => $@"\b(?:{words})\b",
            "first" => $@"^(?:{words})\b",
            "firstShort" => $@"^(?:{words})(?:\s+\S+){{0,3}}$",
            _ => throw new InvalidDataException(where),
        };
    }

    private static string[] Strings(JsonElement list) => [.. list.EnumerateArray().Select(item => item.GetString()!)];

    private static Regex Compile(string pattern) => new(pattern, RegexOptions.CultureInvariant);
}
