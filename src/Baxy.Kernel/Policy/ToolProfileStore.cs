using System.Text.Json;
using System.Text.Json.Nodes;

namespace Baxy.Kernel.Policy;

/// <summary>
/// Settings → Tools: the tool profile the person chose lives in one file of the profile, like BAXY's other settings
/// (<see cref="FieldSettingsStore"/>): the view's Tools tab writes it through the App (<c>ToolProfile</c>, which also keeps
/// Personalizado's list) and the chat's <c>baxy.settings.set</c> (setting tool_profile, a ready-made profile) through the
/// engine; the App reads it. Completo, the factory's, is the file's absence.
/// </summary>
public static class ToolProfileStore
{
    public const string FileName = "tool-profile.v1.json";

    public const string Completo = "completo";

    /// <summary>The ready-made profiles, from fewest tools to all.</summary>
    public static readonly string[] Presets = ["esencial", "diario", "avanzado", Completo];

    /// <summary>The profile the file says, Completo when there is none; false when it cannot be read or names no profile
    /// (APP2, REV11 A-4: a broken file is not Completo, which would open every tool; the App keeps the last one read).</summary>
    public static bool TryRead(string dataRoot, out string profile) => TryRead(dataRoot, out profile, out _);

    /// <summary>
    /// <see cref="TryRead(string, out string)"/>, and when it is false whether the file was read and is broken (not JSON,
    /// or naming no profile: a cut write), which reading again will not mend, unlike one another program holds a moment
    /// (REM1, REV12 B-2).
    /// </summary>
    public static bool TryRead(string dataRoot, out string profile, out bool broken)
    {
        profile = Completo;
        broken = false;
        string path = Path.Combine(dataRoot, FileName);
        try
        {
            if (!File.Exists(path))
            {
                return true;
            }

            if (JsonNode.Parse(File.ReadAllText(path)) is JsonObject read
                && read["profile"] is JsonValue value && value.TryGetValue(out string? named))
            {
                profile = named;
                return true;
            }

            broken = true;
            return false;
        }
        catch (JsonException)
        {
            broken = true;
            return false;
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            return false;
        }
    }

    /// <summary>Keeps a ready-made profile (Completo removes the file); the caller reads it back.</summary>
    public static void WritePreset(string dataRoot, string profile)
    {
        string path = Path.Combine(dataRoot, FileName);
        if (profile == Completo)
        {
            File.Delete(path);
            return;
        }

        Directory.CreateDirectory(dataRoot);
        string temporary = path + ".tmp";
        File.WriteAllText(temporary, new JsonObject { ["profile"] = profile }.ToJsonString());
        File.Move(temporary, path, overwrite: true);
    }
}
