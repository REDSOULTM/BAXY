using System.Text.Json;
using System.Text.Json.Nodes;

namespace Baxy.Kernel.Policy;

/// <summary>
/// BAXY's own settings (its voice, the privacy switches, the proposals' silence, the interface's language) live in one
/// file of the profile, like the confirmation and presentation modes: the view's Settings and Proposals panels write it
/// through the App
/// (<c>FieldSettings</c>) and the chat's <c>baxy.settings.set</c> through the engine; the App reads it.
/// </summary>
public static class FieldSettingsStore
{
    public const string FileName = "field-settings.v1.json";

    /// <summary>
    /// Whether the file could be read (one another program holds locked cannot); a missing or unparsable file reads as no
    /// choice made yet, every switch at its default.
    /// </summary>
    public static bool TryRead(string? dataRoot, out JsonObject values)
    {
        values = new JsonObject();
        if (string.IsNullOrWhiteSpace(dataRoot))
        {
            return true;
        }

        try
        {
            string path = Path.Combine(dataRoot, FileName);
            if (File.Exists(path) && JsonNode.Parse(File.ReadAllText(path)) is JsonObject read)
            {
                values = read;
            }

            return true;
        }
        catch (JsonException)
        {
            return true;
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            return false;
        }
    }

    /// <summary>Replaces the file whole (a temporary file moved over it); a failure to write throws.</summary>
    public static void Write(string dataRoot, JsonObject values)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(dataRoot);
        Directory.CreateDirectory(dataRoot);
        string path = Path.Combine(dataRoot, FileName);
        string temporary = path + ".tmp";
        File.WriteAllText(temporary, values.ToJsonString());
        AtomicFileReplacement.ReplaceOrCreate(temporary, path);
    }

    /// <summary>Until when the proposals stay silent for a span: 30m, 1h or tomorrow (08:00 local); null for any other.</summary>
    public static DateTimeOffset? QuietUntil(string? span, DateTimeOffset now)
    {
        DateTime morning = now.LocalDateTime.Date.AddDays(1).AddHours(8);
        return span switch
        {
            "30m" => now.AddMinutes(30),
            "1h" => now.AddHours(1),
            "tomorrow" => new DateTimeOffset(morning, TimeZoneInfo.Local.GetUtcOffset(morning)),
            _ => null,
        };
    }

    /// <summary>The silence the values hold (UTC), or null when it is over or there is none.</summary>
    public static DateTimeOffset? QuietUntil(JsonObject values, DateTimeOffset now) =>
        values["quietUntil"] is JsonValue value && value.TryGetValue(out long ms)
        && DateTimeOffset.FromUnixTimeMilliseconds(ms) > now
            ? DateTimeOffset.FromUnixTimeMilliseconds(ms)
            : null;
}
