using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;
using Baxy.Kernel.Operations;

namespace Baxy.App;

/// <summary>
/// M116 (DEV-F v4e2 F-s005, F-s014, F-s033, F-w01-t4, F-w05-t2, F-w29-t2, F-w51-t2): a step that failed or was left
/// unverified for a reason of the PC (WhatsApp or Discord closed, the volume already at its end) told the mind only
/// the cause and, since M94, one target, so the final could not say what was attempted («No pude dejar escrito el
/// mensaje «Lupita».») and the turn's record showed no argument that had been understood. The step's grounded
/// arguments that a person can read go with its facts as <c>attempted</c>: names, recipients, clients, titles, the
/// message's words, times and dates as said, folder and file names, queries, levels, amounts, sides. Never an
/// identifier, a handle, an AUMID, a stamp for the machine, a paging or version field, or a path beyond its last
/// name; every text and list is bounded as an observation is (M106, <see cref="OperationVisibleFacts"/>).
/// </summary>
internal static class AttemptedArguments
{
    internal const string Key = "attempted";

    private const int MaximumChars = 1_200;
    private const int MaximumDepth = 2;

    // (free text, any other text, list items): the first that fits the bound wins, as M106's projection steps.
    private static readonly (int Text, int Name, int Items)[] Steps = [(280, 120, 5), (120, 80, 3)];

    private static readonly HashSet<string> Internal = new(StringComparer.Ordinal)
    {
        "id", "limit", "offset", "version", "expectedVersion", "expectedRevision", "expectedIsTrashed",
        "includeDeleted", "includeTrashed", "includeSecrets", "maximumCharacters", "maxCharacters", "maximumBytes",
        "mustNotDeletePersistent", "confirmationRequired", "selector", "resourceUri", "hwnd", "handle", "token",
        "hash", "sha256", "fingerprint", "aumid", "pid", "retention",
    };

    private static readonly string[] InternalSuffixes = ["Id", "Ids", "Utc", "Token", "Hash"];

    private static readonly HashSet<string> FreeText = new(StringComparer.Ordinal)
    {
        "text", "content", "body", "details", "command", "prompt", "phrase", "message",
    };

    private static readonly Regex Identifier = new(
        @"\A(?:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|[0-9a-f]{24,}|[a-z]+_[0-9a-f]{12,})\z"
        // An application user model id («Microsoft.WindowsCamera_8wekyb3d8bbwe!App»).
        + @"|\A[^\s!]+![A-Za-z]\w*\z",
        RegexOptions.CultureInvariant | RegexOptions.IgnoreCase);

    /// <summary>The person-visible arguments of a step, bounded, or null when none is left.</summary>
    internal static JsonObject? Project(JsonObject? arguments)
    {
        if (arguments is null || arguments.Count == 0)
        {
            return null;
        }

        JsonObject? projected = null;
        foreach ((int text, int name, int items) in Steps)
        {
            projected = ProjectObject(arguments, 0, text, name, items);
            if (projected is null || projected.ToJsonString().Length <= MaximumChars)
            {
                return projected;
            }
        }

        // Still over the bound: the longest values go first, the names stay.
        while (projected is { Count: > 0 } && projected.ToJsonString().Length > MaximumChars)
        {
            string longest = projected
                .OrderByDescending(static pair => pair.Value?.ToJsonString().Length ?? 0)
                .First().Key;
            projected.Remove(longest);
        }

        return projected is { Count: > 0 } ? projected : null;
    }

    private static JsonObject? ProjectObject(JsonObject source, int depth, int text, int name, int items)
    {
        var projected = new JsonObject();
        foreach ((string key, JsonNode? value) in source)
        {
            if (value is null || IsInternal(key))
            {
                continue;
            }

            JsonNode? kept = ProjectValue(key, value, depth, text, name, items);
            if (kept is not null)
            {
                projected[key] = kept;
            }
        }

        return projected.Count > 0 ? projected : null;
    }

    private static JsonNode? ProjectValue(string key, JsonNode value, int depth, int text, int name, int items)
    {
        switch (value)
        {
            case JsonObject nested:
                return depth < MaximumDepth ? ProjectObject(nested, depth + 1, text, name, items) : null;
            case JsonArray list:
                if (depth >= MaximumDepth)
                {
                    return null;
                }

                var kept = new JsonArray();
                foreach (JsonNode? item in list)
                {
                    if (kept.Count == items)
                    {
                        break;
                    }

                    if (item is not null && ProjectValue(key, item, depth + 1, text, name, items) is { } said)
                    {
                        kept.Add(said);
                    }
                }

                return kept.Count > 0 ? kept : null;
            case JsonValue scalar:
                switch (scalar.GetValueKind())
                {
                    case JsonValueKind.Number:
                    case JsonValueKind.True:
                    case JsonValueKind.False:
                        return scalar.DeepClone();
                    case JsonValueKind.String:
                        string? said = Said(key, scalar.GetValue<string>(), FreeText.Contains(key) ? text : name);
                        return said is null ? null : JsonValue.Create(said);
                    default:
                        return null;
                }

            default:
                return null;
        }
    }

    private static bool IsInternal(string key) =>
        Internal.Contains(key)
        || InternalSuffixes.Any(suffix => key.Length > suffix.Length && key.EndsWith(suffix, StringComparison.Ordinal));

    private static string? Said(string key, string raw, int bound)
    {
        string value = Regex.Replace(raw.Trim(), @"\s+", " ", RegexOptions.CultureInvariant);
        if (value.Length == 0 || Identifier.IsMatch(value))
        {
            return null;
        }

        if (Uri.TryCreate(value, UriKind.Absolute, out Uri? uri) && (uri.Scheme == Uri.UriSchemeHttp || uri.Scheme == Uri.UriSchemeHttps))
        {
            // A page the person named: its host and path, never a query that may carry a token.
            value = uri.Host + (uri.AbsolutePath == "/" ? string.Empty : uri.AbsolutePath);
        }
        else if (IsPath(key, value))
        {
            // A folder or a file is said by its own name, never by where it lives.
            value = value.TrimEnd('\\', '/').Split('\\', '/').LastOrDefault(static part => part.Length > 0) ?? string.Empty;
            if (value.Length == 0 || value.Contains(':', StringComparison.Ordinal))
            {
                return null;
            }
        }

        return value.Length > bound ? OperationVisibleFacts.Shortened(value, bound) : value;
    }

    private static bool IsPath(string key, string value) =>
        value.Contains('\\', StringComparison.Ordinal)
        || (value.Length > 1 && value[1] == ':' && char.IsAsciiLetter(value[0]))
        || value.StartsWith('~') || value.StartsWith('%')
        || (value.Contains('/', StringComparison.Ordinal)
            && (key.Contains("path", StringComparison.OrdinalIgnoreCase)
                || key.Contains("director", StringComparison.OrdinalIgnoreCase)
                || key is "cwd" or "folder" or "destination" or "subdirectory"));
}
