using System.IO;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Kernel.Operations;

namespace Baxy.App;

/// <summary>
/// Settings → Tools (owner's decision, 2026-11-08: ready-made tool profiles and a manual choice): how many of BAXY's tools the
/// model sees, kept only when the person chooses (<c>&lt;datos&gt;\tool-profile.v1.json</c>). Esencial, Diario and
/// Avanzado keep the operations whose first profile (FieldStepProjection.ProfileLevel, data in operation-labels) is theirs
/// or a lower one; Completo, the factory's, keeps them all; Personalizado, the ones the person turned on. BAXY's own (level
/// 0: its settings, its exit, its conversations) are in every profile. A tool off is withheld from the mind's catalog
/// (MindSidecarClient) and refused before it runs if the model names it anyway (<see cref="Refusal(string)"/>, NativeTurnLoop);
/// what asks for a yes asks the same in every profile: a profile only takes tools away.
/// </summary>
internal sealed class ToolProfile
{
    internal const string Completo = "completo";
    internal const string Personalizado = "personalizado";
    internal const int Highest = 4;
    internal const string OffCode = "tool_off_in_profile";
    private const string Invalid = "tool_profile_invalid";

    // The presets in their order, with the highest level each keeps.
    private static readonly (string Name, int Level)[] Presets =
        [("esencial", 1), ("diario", 2), ("avanzado", 3), (Completo, Highest)];

    private readonly string _path;
    private readonly object _sync = new();
    private string? _applied;
    private bool _started;

    internal ToolProfile(string dataRoot) => _path = Path.Combine(dataRoot, "tool-profile.v1.json");

    // Each preset's prompt prefix, counted with Qwen3.5's tokenizer and its GGUF's template on the PC's catalog (2026-11-08,
    // documentacion/PERFILES_HERRAMIENTAS.md). Another model's tokenizer counts about as many (mistral:latest read 13.584 and
    // 45.527 where these said 14.967 and 49.086 before the stubs, VIVO1 F4); the apps installed change them, and one the mind read scales them.
    // With the tools kept off shown as stubs (VIVO1 F8) each prompt grew by what its stubs take, counted the same way on
    // the mind's own configure of each side (INT20, 2026-11-09): Esencial +7.694, Diario +3.633, Avanzado +795, Completo 0.
    // VER1 (2026-11-10): the date asked of system.time is typed arguments now, and web_search says who holds an office is
    // looked up; counted the same way against int21-base, +489 in each.
    // ALR5 (2026-11-10, counted the same way against int21-base): Esencial's stub of schedule.alarms, which answers what
    // rings (M2), +198; the others show schedule.alarms' description, byte for byte int21-base's. The two together,
    // counted on their merge.
    private static readonly (string Name, int Prefix)[] MeasuredPrefix =
        [("esencial", 23348), ("diario", 38177), ("avanzado", 47833), (Completo, 49575)];

    /// <summary>The context a model needs for <paramref name="profile"/>'s prompt and a turn beside it: the measured prefix, scaled
    /// by the one the mind read (<paramref name="measured"/>, for <paramref name="measuredProfile"/>) when known. Personalizado
    /// has none measured: the mind's, if it read that one, else Completo's.</summary>
    internal static int NeededContext(string profile, int? measured, string? measuredProfile)
    {
        if (profile == measuredProfile && measured is { } own && Prefix(profile) is null)
        {
            return LocalContext.MinimumContext(own);
        }

        int prefix = Prefix(profile) ?? Prefix(Completo)!.Value;
        if (measured is { } read && measuredProfile is not null && Prefix(measuredProfile) is { } table)
        {
            prefix = (int)Math.Round(prefix * (double)read / table);
        }

        return LocalContext.MinimumContext(prefix);
    }

    /// <summary>The preset with the most tools whose prompt and a turn fit in <paramref name="context"/>, or null if none.</summary>
    internal static string? LargestFitting(int context, int? measured, string? measuredProfile) =>
        MeasuredPrefix.Reverse().Select(static preset => preset.Name)
            .FirstOrDefault(name => NeededContext(name, measured, measuredProfile) <= context);

    /// <summary>Whether <paramref name="profile"/> is one of the ready-made profiles.</summary>
    internal static bool IsPreset(string? profile) => Presets.Any(preset => preset.Name == profile);

    private static int? Prefix(string profile) =>
        MeasuredPrefix.Where(preset => preset.Name == profile).Select(static preset => (int?)preset.Prefix).FirstOrDefault();

    private static IEnumerable<string> CatalogNames => ProductCatalog.ToolDescriptors.Select(static d => d.Name);

    /// <summary>The profile chosen: one of the presets or <see cref="Personalizado"/>; Completo until one is chosen, and
    /// for a file that cannot be read or says something else.</summary>
    internal string Profile => Read().Profile;

    /// <summary>The operations of <paramref name="catalog"/> the profile keeps off; none with Completo.</summary>
    internal IReadOnlySet<string> Withheld(IEnumerable<string> catalog)
    {
        ArgumentNullException.ThrowIfNull(catalog);
        (string profile, HashSet<string>? on) = Read();
        return catalog.Where(name => !Keeps(profile, on, name)).ToHashSet(StringComparer.Ordinal);
    }

    /// <summary><see cref="OffCode"/> for a catalog operation this profile keeps off, null otherwise (a name of no catalog
    /// is the App's unknown_operation).</summary>
    internal string? Refusal(string operation)
    {
        if (!CatalogNames.Contains(operation, StringComparer.Ordinal))
        {
            return null;
        }

        (string profile, HashSet<string>? on) = Read();
        return Keeps(profile, on, operation) ? null : OffCode;
    }

    /// <summary>ALR5 (M2, uso real 09-11: with Alarmas outside the profile one set before rang, and no words stopped it):
    /// as <see cref="Refusal(string)"/>, but a stop or a snooze of what rings now (<paramref name="ringing"/>) is not
    /// refused, as the buttons of its card never were: a profile takes away setting alarms, not silencing one that rings.</summary>
    internal string? Refusal(string operation, JsonObject arguments, bool ringing) =>
        ringing && AnswersRing(operation, arguments) ? null : Refusal(operation);

    /// <summary>A schedule.alarms call that only answers what rings: action stop or snooze.</summary>
    internal static bool AnswersRing(string operation, JsonObject arguments)
    {
        ArgumentNullException.ThrowIfNull(arguments);
        return operation == "schedule.alarms" && arguments["action"] is JsonValue value
            && value.TryGetValue(out string? action) && action is "stop" or "snooze";
    }

    /// <summary>A mind came up with these operations withheld.</summary>
    internal void Started(IReadOnlySet<string> withheld)
    {
        ArgumentNullException.ThrowIfNull(withheld);
        lock (_sync)
        {
            _applied = Key(withheld);
            _started = true;
        }
    }

    /// <summary>Whether a mind came up and the profile now withholds other operations than the ones it was started without.</summary>
    internal bool NeedsSwitch
    {
        get
        {
            string now = Key(Withheld(CatalogNames));
            lock (_sync)
            {
                return _started && !string.Equals(now, _applied, StringComparison.Ordinal);
            }
        }
    }

    /// <summary>The person's choice: <c>profile</c> one of the presets, or <see cref="Personalizado"/> with <c>on</c> the
    /// operations to keep. Null when kept, or why it was refused (nothing is kept then).</summary>
    internal string? Apply(JsonObject body)
    {
        ArgumentNullException.ThrowIfNull(body);
        if (body["profile"] is not JsonValue chosen || !chosen.TryGetValue(out string? profile)
            || (profile != Personalizado && !Presets.Any(p => p.Name == profile)))
        {
            return Invalid;
        }

        var file = new JsonObject { ["profile"] = profile };
        if (profile == Personalizado)
        {
            if (body["on"] is not JsonArray list)
            {
                return Invalid;
            }

            var on = new SortedSet<string>(StringComparer.Ordinal);
            foreach (JsonNode? item in list)
            {
                if (item is not JsonValue value || !value.TryGetValue(out string? name)
                    || !CatalogNames.Contains(name, StringComparer.Ordinal))
                {
                    return Invalid;
                }

                on.Add(name);
            }

            file["on"] = new JsonArray([.. on.Select(static n => (JsonNode?)n)]);
        }

        lock (_sync)
        {
            try
            {
                if (profile == Completo)
                {
                    File.Delete(_path);
                }
                else
                {
                    Directory.CreateDirectory(Path.GetDirectoryName(_path)!);
                    string temporary = _path + ".tmp";
                    File.WriteAllText(temporary, file.ToJsonString());
                    File.Move(temporary, _path, overwrite: true);
                }
            }
            catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
            {
                return "tool_profile_not_saved";
            }
        }

        return null;
    }

    /// <summary>For Settings: the profile and the operations it keeps (the catalog with each one's level is GET /catalog).</summary>
    internal JsonObject Json()
    {
        (string profile, HashSet<string>? on) = Read();
        return new JsonObject
        {
            ["profile"] = profile,
            ["on"] = new JsonArray([.. CatalogNames.Where(name => Keeps(profile, on, name)).Select(static n => (JsonNode?)n)]),
        };
    }

    private static bool Keeps(string profile, HashSet<string>? on, string operation)
    {
        int level = FieldStepProjection.ProfileLevel(operation);
        if (level == 0)
        {
            return true;
        }

        return profile == Personalizado
            ? on?.Contains(operation) == true
            : level <= Presets.First(p => p.Name == profile).Level;
    }

    private static string Key(IReadOnlySet<string> withheld) =>
        string.Join('\n', withheld.Order(StringComparer.Ordinal));

    private (string Profile, HashSet<string>? On) Read()
    {
        lock (_sync)
        {
            try
            {
                if (!File.Exists(_path) || JsonNode.Parse(File.ReadAllText(_path)) is not JsonObject file
                    || file["profile"] is not JsonValue chosen || !chosen.TryGetValue(out string? profile))
                {
                    return (Completo, null);
                }

                if (profile == Personalizado)
                {
                    HashSet<string> on = file["on"] is JsonArray list
                        ? [.. list.OfType<JsonValue>().Select(static v => v.TryGetValue(out string? n) ? n : null).OfType<string>()]
                        : [];
                    return (Personalizado, on);
                }

                return Presets.Any(p => p.Name == profile) ? (profile, null) : (Completo, null);
            }
            catch (Exception exception) when (exception is IOException or UnauthorizedAccessException or JsonException)
            {
                return (Completo, null);
            }
        }
    }
}
