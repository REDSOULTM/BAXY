using System.Text.Json;
using System.Text.RegularExpressions;

namespace Baxy.Kernel.Policy;

/// <summary>
/// The words a control's label says when its click leaves the computer or reaches another person: sending, publishing,
/// sharing, joining, calling, going live. One source, in data (src/baxy_mind/data/world_acts.v1.json, embedded), read
/// here for <see cref="RiskPolicy"/>. Each family says where its words count: anywhere in the label as whole words, as
/// its first word whatever follows, or as its first word and at most three more.
/// </summary>
internal static class WorldActs
{
    private const string Resource = "Baxy.Kernel.WorldActs.json";

    private static readonly Lazy<Words> Loaded = new(Load);

    /// <summary>A trailing shortcut hint of a label («Enviar (Ctrl+Enter)»), which never hides its verb.</summary>
    internal static Regex ShortcutHint => Loaded.Value.ShortcutHint;

    /// <summary>Whether a folded label names an act that leaves the computer or reaches a person.</summary>
    internal static bool Reaches(string folded) => Loaded.Value.Families.Any(family => family.Matches(folded));

    /// <summary>Each family as its pattern and its exception, for the one pattern the UIA worker is handed.</summary>
    internal static IEnumerable<(string Pattern, string? Unless)> Rules =>
        Loaded.Value.Families.Select(family => (family.Pattern.ToString(), family.Unless?.ToString()));

    private sealed record Family(Regex Pattern, Regex? Unless)
    {
        internal bool Matches(string folded) => Pattern.IsMatch(folded) && Unless?.IsMatch(folded) != true;
    }

    private sealed record Words(Regex ShortcutHint, Family[] Families);

    private static Words Load()
    {
        using Stream stream = typeof(WorldActs).Assembly.GetManifestResourceStream(Resource)
            ?? throw new InvalidOperationException(Resource);
        using JsonDocument document = JsonDocument.Parse(stream);
        JsonElement root = document.RootElement;
        return new Words(
            Compile(root.GetProperty("shortcutHint").GetString()!),
            [.. root.GetProperty("families").EnumerateArray().Select(Read)]);
    }

    private static Family Read(JsonElement family)
    {
        string where = family.GetProperty("where").GetString()!;
        string[] said = [.. family.GetProperty("words").EnumerateArray().Select(item => item.GetString()!)];
        Regex? unless = family.TryGetProperty("unless", out JsonElement pattern) ? Compile(pattern.GetString()!) : null;
        return new Family(Compile(Shape(where, said)), unless);
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

    private static Regex Compile(string pattern) => new(pattern, RegexOptions.CultureInvariant);
}
