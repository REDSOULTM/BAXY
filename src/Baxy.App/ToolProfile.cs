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
    private bool _memoryOff;
    private (string Profile, HashSet<string>? On)? _lastRead;
    // REM1 (APP2's A-4 medio): _lastRead is the most closed profile kept while nothing could be read yet, not a choice.
    private bool _provisional;

    internal ToolProfile(string dataRoot) => _path = Path.Combine(dataRoot, Baxy.Kernel.Policy.ToolProfileStore.FileName);

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
    // ESE3 (2026-11-10): alarms and reminders are Esencial's (schedule.alarms, level 1): its description instead of the
    // stub, +468 counted by the model's own server on the mind's warm of int24-cand's Esencial (20.827 → 21.295).
    // RUT2 (2026-11-10): audio_device_list, audio_device_set and display_monitor_set in every preset, and display_status
    // says where each monitor is: +753 in each, counted the same way against int28-cand.
    // RUT6 (2026-11-11): baxy_routines keeps an order for a routine with a phrase (its description and the «order»
    // argument) and audio_microphone_mute says which names are not its own: +163 in each; media_control is Esencial's
    // (level 1), its description instead of its stub: +190 more there. Counted by the model's own server on the
    // mind's warm, with each side's catalog.configure (Esencial 22.998 → 23.351).
    // ESE6 (2026-11-11): Esencial shows memory_save off with its arguments (FieldStepProjection.HeldWhole) and its
    // memory fact names that call: +316 there, counted by the model's own server (tokenize) on the system text and the
    // tools of each side, bench catalog of int33-cand (22.579 → 22.895); the others are byte for byte the same.
    // ESE7 (2026-11-12): Esencial shows memory_enable and memory_sensitive_save off with their arguments too, and its
    // memory fact says what goes in each: +506 there, counted the same way (22.895 → 23.401); the others, byte for byte.
    // INT33G (2026-11-12): on int33-cand2 (rut10's table, no rut11), ESE6 and ESE7 without memory_sensitive_save held whole
    // (reverted: it brought «I have no tool to turn the memory off» with the memory already off, 1 → 6 of 10 seeds) count
    // +467 in Esencial with the stock tokenizer and the GGUF template, bench catalog of int33-cand2's App and of this one
    // (22.939 → 23.406); the others, byte for byte.
    // RUT13 (2026-11-12): three descriptions say their frontier (audio_microphone_mute takes no name, +10; media_control is
    // about what already plays, +6; office_document_create is not opening the program, +17, a stub in Esencial and Diario):
    // +16 and +16, +33 and +33, counted with the model's tokenizer on each text and, for Completo, by the model's own
    // server on the same turn (48.123 → 48.156).
    // INT33K (2026-11-12): measured on the union (rem6, sis4, rem7 = ese7 + mem3, ese8, rut13) against int33-pre4, the
    // stock tokenizer and the GGUF template, each preset's catalog.configure from this App with the memory switch on and
    // off (the larger kept): Esencial 23.406 → 23.433 (+27: rut13's 16 and rem7's memory fact), Diario +16, Avanzado
    // and Completo +33 (rut13's; the memory switch off is 2 fewer there).
    private static readonly (string Name, int Prefix)[] MeasuredPrefix =
        [("esencial", 26342), ("diario", 40035), ("avanzado", 49708), (Completo, 51450)];

    /// <summary>The context a model needs for <paramref name="profile"/>'s prompt and a turn beside it: the measured prefix, scaled
    /// by the one the mind read (<paramref name="measured"/>, for <paramref name="measuredProfile"/>) when known. Personalizado
    /// has none measured: the mind's, if it read that one, else the one its tools take (<paramref name="kept"/>, by
    /// <see cref="PersonalPrefix"/>), else Completo's.</summary>
    internal static int NeededContext(string profile, int? measured, string? measuredProfile, int? kept = null)
    {
        if (profile == measuredProfile && measured is { } own && Prefix(profile) is null)
        {
            return LocalContext.MinimumContext(own);
        }

        int prefix = Prefix(profile) ?? (kept is { } tools ? PersonalPrefix(tools) : Prefix(Completo)!.Value);
        if (measured is { } read && measuredProfile is not null && Prefix(measuredProfile) is { } table)
        {
            prefix = (int)Math.Round(prefix * (double)read / table);
        }

        return LocalContext.MinimumContext(prefix);
    }

    /// <summary>The largest prefix measured for a ready-made profile (Completo's): a Personalizado's is never above it.</summary>
    internal static int LargestPrefix => MeasuredPrefix.Max(static preset => preset.Prefix);

    /// <summary>The preset with the most tools whose prompt and a turn fit in <paramref name="context"/>, or null if none.</summary>
    internal static string? LargestFitting(int context, int? measured, string? measuredProfile) =>
        MeasuredPrefix.Reverse().Select(static preset => preset.Name)
            .FirstOrDefault(name => NeededContext(name, measured, measuredProfile) <= context);

    /// <summary>Whether <paramref name="profile"/> is one of the ready-made profiles.</summary>
    internal static bool IsPreset(string? profile) => Presets.Any(preset => preset.Name == profile);

    private static int? Prefix(string profile) =>
        MeasuredPrefix.Where(preset => preset.Name == profile).Select(static preset => (int?)preset.Prefix).FirstOrDefault();

    /// <summary>The tools the mind sees whole in the profile chosen now (the others go as stubs).</summary>
    internal int Kept
    {
        get
        {
            (string profile, HashSet<string>? on) = Read();
            return CatalogNames.Count(name => Keeps(profile, on, name));
        }
    }

    /// <summary>TPV5 (TPV4, revisión ciega: Esencial with the memory turned on is Personalizado, and its need was weighed as
    /// Completo's 49,575 where it takes about Esencial's): a Personalizado's prefix by the tools it keeps whole, on the line
    /// between the two presets whose counts hold it (each tool kept whole instead of its stub adds about the same: the
    /// presets' own prefixes rise with their counts), never below Esencial's nor above Completo's.</summary>
    internal static int PersonalPrefix(int kept)
    {
        (int Tools, int Prefix)[] points =
            [.. MeasuredPrefix.Select(static preset => (CatalogNames.Count(name => Keeps(preset.Name, null, name)), preset.Prefix))];
        if (kept <= points[0].Tools)
        {
            return points[0].Prefix;
        }

        for (int i = 1; i < points.Length; i++)
        {
            if (kept <= points[i].Tools)
            {
                (int fewer, int low) = points[i - 1];
                (int more, int high) = points[i];
                return low + (int)Math.Ceiling((double)(high - low) * (kept - fewer) / Math.Max(1, more - fewer));
            }
        }

        return points[^1].Prefix;
    }

    private static IEnumerable<string> CatalogNames => ProductCatalog.ToolDescriptors.Select(static d => d.Name);

    /// <summary>The profile chosen: one of the presets or <see cref="Personalizado"/>; Completo until one is chosen. A file
    /// that cannot be read or names no profile keeps the last one read (<see cref="Read"/>).</summary>
    internal string Profile => Read().Profile;

    /// <summary>MEM3 (VIVO15 fila 3, Completo with the memory's own switch off: «Recuerda que mi perro se llama Chispo.» →
    /// «¡Genial, ahora sé que tu perro se llama Chispo!» 5 of 5, nothing called nor offered): with the switch off, memory.save
    /// was shown whole, as if it saved, and nothing the model read said the memory was off. Off, the memory call shown with
    /// its arguments (FieldStepProjection.HeldWhole) is withheld and held in any profile, as ESE6 holds it out of Esencial:
    /// the mind shows it off with its arguments and the person's «sí» turns the memory on and runs it
    /// (NativeTurnLoop.AnswerMemoryOffHeldAsync). Set from memory.status at the start and from each switch after.</summary>
    internal bool MemoryOff
    {
        get => Volatile.Read(ref _memoryOff);
        set => Volatile.Write(ref _memoryOff, value);
    }

    // REM7 (union of mem3 and ese7): ese7 shows the switch itself whole too, so with the switch off only the calls that
    // save are held; memory.enable is the person's own way to turn it on, held only where the profile keeps it off.
    private bool HeldWhileMemoryOff(string operation) => MemoryOff && FieldStepProjection.HeldWhole(operation)
        && MemoryOperationProtector.IsMemoryOperation(operation) && operation != "memory.enable";

    /// <summary>The operations of <paramref name="catalog"/> the profile keeps off; none with Completo (but the memory's
    /// own held call while the memory is off, <see cref="MemoryOff"/>).</summary>
    internal IReadOnlySet<string> Withheld(IEnumerable<string> catalog)
    {
        ArgumentNullException.ThrowIfNull(catalog);
        (string profile, HashSet<string>? on) = Read();
        return catalog.Where(name => !Keeps(profile, on, name) || HeldWhileMemoryOff(name))
            .ToHashSet(StringComparer.Ordinal);
    }

    /// <summary><see cref="OffCode"/> for a catalog operation this profile keeps off (or held while the memory is off,
    /// <see cref="MemoryOff"/>), null otherwise (a name of no catalog is the App's unknown_operation).</summary>
    internal string? Refusal(string operation)
    {
        if (!CatalogNames.Contains(operation, StringComparer.Ordinal))
        {
            return null;
        }

        (string profile, HashSet<string>? on) = Read();
        return Keeps(profile, on, operation) && !HeldWhileMemoryOff(operation) ? null : OffCode;
    }

    /// <summary>ESE1 (VIVO5 fila 7, 2 de 2: «Read a web page», off in Esencial, refused as «this tool off in Settings →
    /// Tools», was told as web search switched off in the settings, which was on): what a refusal as <see cref="OffCode"/>
    /// says of it, the tool, the profile and the ready-made profiles that have it, so what is off and where it turns on are
    /// the receipt's and not the model's guess.</summary>
    /// ESE3 (VIVO7 fila 4: «with this tool on» was told as «activa la opción "Alarmas o recordatorios"», an option the
    /// tab never shows): the profiles and the tool's box in Personalizado are named as the view shows them, in its language.
    internal JsonObject OffFacts(string operation)
    {
        (string profile, _) = Read();
        bool english = UiLanguage.IsEnglish;
        int level = FieldStepProjection.ProfileLevel(operation);
        string[] with = [.. Presets.Where(preset => preset.Level >= level).Select(preset => Shown(preset.Name, english))];
        string presets = with.Length > 1 ? string.Join(", ", with[..^1]) + " or " + with[^1] : with[0];
        string where = english ? "Settings → Tools" : "Settings → Tools («Ajustes → Herramientas»)";
        // TPV1 (dueño, 10-11: everything by voice): the smallest ready-made profile that has it, switched by BAXY with the
        // person's «sí»; where Settings has it stays beside, never as the only way.
        string smallest = Presets.First(preset => preset.Level >= level).Name;
        return new JsonObject
        {
            ["tool"] = FieldStepProjection.EnglishTitle(operation),
            ["profile"] = Shown(profile, english),
            ["turnOnBySpeaking"] = WireNames.Call(OwnBrakes.Operation, new() { ["setting"] = OwnBrakes.ToolProfile, ["value"] = smallest })
                + $" switches to the profile {Shown(smallest, english)}, which has it; BAXY asks the person's yes itself",
            ["turnOn"] = $"{where}: the profile {presets}, or {Shown(Personalizado, english)} with «{FieldStepProjection.Title(operation, english)}» ticked",
        };
    }

    // The profile as Settings → Tools names it (ToolsSection.tsx, PRESETS): esencial → Esencial, or Essential in English.
    private static string Shown(string profile, bool english) => english
        ? profile switch
        {
            "esencial" => "Essential",
            "diario" => "Everyday",
            "avanzado" => "Advanced",
            Completo => "Complete",
            _ => "Custom",
        }
        : char.ToUpperInvariant(profile[0]) + profile[1..];

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

    /// <summary>REM8 (REV16 M-4): whether the person's profile keeps this operation on, the memory's switch aside: what holds
    /// a held memory call is the switch, the profile or both, and its card says which.</summary>
    internal bool InProfile(string operation)
    {
        (string profile, HashSet<string>? on) = Read();
        return Keeps(profile, on, operation);
    }

    /// <summary>TPV6 (VIVO11, Esencial: «Crea una nota que diga hola» was answered with Settings → Tools, or by switching to
    /// Diario, a whole larger profile, after three «sí»): with the person's «sí» to the call refused as off, the profile keeps
    /// what it kept and that one tool, and nothing else (Personalizado); a memory tool brings the memory's operations, which
    /// work together. Null when it is on now, or why it could not be kept.</summary>
    internal string? KeepOn(string operation)
    {
        (string profile, HashSet<string>? on) = Read();
        if (Keeps(profile, on, operation))
        {
            return null;
        }

        bool memory = MemoryOperationProtector.IsMemoryOperation(operation);
        string[] kept = [.. CatalogNames.Where(name => FieldStepProjection.ProfileLevel(name) > 0
            && (Keeps(profile, on, name) || name == operation
                || (memory && MemoryOperationProtector.IsMemoryOperation(name))))];
        return Apply(new JsonObject
        {
            ["profile"] = Personalizado,
            ["on"] = new JsonArray([.. kept.Select(static n => (JsonNode?)n)]),
        });
    }

    /// <summary>The person's choice: <c>profile</c> one of the presets, or <see cref="Personalizado"/> with <c>on</c> the
    /// operations to keep. Null when kept, or why it was refused (nothing is kept then).</summary>
    internal string? Apply(JsonObject body)
    {
        ArgumentNullException.ThrowIfNull(body);
        // REM1 (APP2's A-4 medio): what the panel puts back (Json() before a model change that was refused, a lent profile
        // settled) may be the most closed one kept while the file could not be read: it is not the person's choice, and
        // writing it would make it one. Nothing is written.
        if (body["provisional"] is JsonValue kept && kept.TryGetValue(out bool provisional) && provisional)
        {
            return null;
        }

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
        var json = new JsonObject
        {
            ["profile"] = profile,
            ["on"] = new JsonArray([.. CatalogNames.Where(name => Keeps(profile, on, name)).Select(static n => (JsonNode?)n)]),
        };
        lock (_sync)
        {
            if (_provisional)
            {
                json["provisional"] = true;
            }
        }

        return json;
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

    // REM7 (REV15 D-1): with a memory call held, the mind's fact says the switch (MindSidecarClient memoryOff), so a mind
    // started with it off is another one than with it on, even where the switch withholds nothing more (Esencial).
    private string Key(IReadOnlySet<string> withheld) =>
        string.Join('\n', withheld.Order(StringComparer.Ordinal))
        + (MemoryOff && withheld.Any(static name => FieldStepProjection.HeldWhole(name)
            && MemoryOperationProtector.IsMemoryOperation(name)) ? "\n(memory off)" : "");

    // APP2 (REV11 A-4): a file that cannot be read now (another program holds it a moment, a broken write) or that names no
    // profile was Completo, and what the person had off ran. It keeps the last profile read, or, with none read yet, the
    // most closed one: only BAXY's own (Personalizado with nothing on). Every look reads the file again.
    private (string Profile, HashSet<string>? On) Read()
    {
        lock (_sync)
        {
            (string Profile, HashSet<string>? On)? read;
            try
            {
                read = !File.Exists(_path) ? (Completo, null) : Parse(File.ReadAllText(_path));
            }
            catch (Exception exception) when (exception is IOException or UnauthorizedAccessException or JsonException)
            {
                read = null;
            }

            if (read is not null || _lastRead is null)
            {
                _provisional = read is null;
            }

            _lastRead = read ?? _lastRead ?? (Personalizado, []);
            return _lastRead.Value;
        }
    }

    private static (string Profile, HashSet<string>? On)? Parse(string text)
    {
        if (JsonNode.Parse(text) is not JsonObject file || file["profile"] is not JsonValue chosen
            || !chosen.TryGetValue(out string? profile))
        {
            return null;
        }

        if (profile == Personalizado)
        {
            HashSet<string> on = file["on"] is JsonArray list
                ? [.. list.OfType<JsonValue>().Select(static v => v.TryGetValue(out string? n) ? n : null).OfType<string>()]
                : [];
            return (Personalizado, on);
        }

        return Presets.Any(p => p.Name == profile) ? (profile, null) : null;
    }
}
