using System.Text.Json;
using System.Text.Json.Nodes;

namespace Baxy.Kernel.Policy;

/// <summary>
/// Settings → Tools: the tool profile the person chose lives in one file of the profile, like BAXY's other settings
/// (<see cref="FieldSettingsStore"/>): the view's Tools tab writes it through the App (<c>ToolProfile</c>, which also keeps
/// Personalizado's list) and the chat's <c>baxy.settings.set</c> (setting tool_profile, a ready-made profile) through the
/// engine; the App reads it. Completo, the factory's, is the file's absence (VRAM4D: or a file the person's choice wrote).
/// </summary>
public static class ToolProfileStore
{
    public const string FileName = "tool-profile.v1.json";

    public const string Completo = "completo";

    /// <summary>VRAM4C (the leader's decision, 2026-11-12: «cuando BAXY arranca sola en Esencial porque el perfil de
    /// fábrica no cabe, esa elección se queda fija… guardada como "elegido por BAXY para este equipo"»): the field of a
    /// file whose profile BAXY chose by itself for this PC's card (what was free and what the factory's takes), not the
    /// person; the profile itself is read as any other.</summary>
    public const string ByCard = "byCard";

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

    /// <summary>VRAM4C: whether the file at <paramref name="path"/> holds BAXY's own choice for the card (<see cref="ByCard"/>).</summary>
    public static bool ChosenForTheCard(string path)
    {
        try
        {
            return File.Exists(path) && JsonNode.Parse(File.ReadAllText(path)) is JsonObject read && read[ByCard] is JsonObject;
        }
        catch (Exception exception) when (exception is JsonException or IOException or UnauthorizedAccessException)
        {
            return false;
        }
    }

    /// <summary>Keeps a ready-made profile; the caller reads it back. VRAM4C: Completo over the profile BAXY chose for the
    /// card is written, the person's choice. VRAM4D (REV18 R18-1; the leader: «lo que elige la persona es suyo y se guarda
    /// siempre, incluido Completo»): Completo is written over any file too. Removing it made the next start the factory's
    /// on a card of 4 GB, which took a smaller profile again by itself and said BAXY chose it; kept, a start the card cannot
    /// hold says so in seconds with the ways out (VRAM4B), and a card with room starts it as it did with no file.</summary>
    public static void WritePreset(string dataRoot, string profile)
    {
        string path = Path.Combine(dataRoot, FileName);
        Directory.CreateDirectory(dataRoot);
        string temporary = path + ".tmp";
        File.WriteAllText(temporary, new JsonObject { ["profile"] = profile }.ToJsonString());
        File.Move(temporary, path, overwrite: true);
    }
}
