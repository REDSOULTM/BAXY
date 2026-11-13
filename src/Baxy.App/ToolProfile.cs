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
    // VRAM4B: the ready-made profile this run started in because the card's free video memory did not hold the factory's
    // and the person never chose one (FitCard). VRAM4C: written as BAXY's choice for this PC (ByCard); this field is the
    // start that chose it, the only one whose view says it (SaidNow), and the profile if the folder refused the file.
    // VRAM4D: on a card that is not short, this start's alone (ThisStart), never written.
    private CardFitted? _fitted;

    /// <summary>VRAM4B: the profile a start took by itself for the card (<paramref name="Profile"/>), with the video
    /// memory that was free and what the factory's profile takes, MiB. VRAM4D (REV18 R18-2): <paramref name="ThisStart"/>
    /// on a card with room that a start found short of free memory (a game open): that start's alone, not kept.</summary>
    internal sealed record CardFitted(string Profile, int FreeMb, int NeedMb, bool ThisStart = false);

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

    /// <summary>VRAM4B: the ready-made profiles under the factory's with the context each needs, the one with the most
    /// tools first: what a start may take by itself on a card that does not hold the factory's (<see cref="FitCard"/>).</summary>
    internal static IReadOnlyList<(string Profile, int Need)> Smaller(int? measured, string? measuredProfile) =>
        [.. MeasuredPrefix.Reverse().Where(static preset => preset.Name != Completo)
            .Select(preset => (preset.Name, NeededContext(preset.Name, measured, measuredProfile)))];

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

    /// <summary>VRAM4B: whether a profile is kept (its file is there): the person's, or, VRAM4C, the one BAXY chose for this
    /// PC's card (<see cref="Fitted"/>). Until then the profile is the factory's, and a start may take a smaller one for the
    /// card (<see cref="FitCard"/>). VRAM4D: the person's only; BAXY's is <see cref="KeptForTheCard"/>.</summary>
    internal bool Chosen => File.Exists(_path) && KeptForTheCard is null;

    /// <summary>VRAM4D: the profile BAXY chose for this PC's card on a start before, while the file keeps it (byCard); null
    /// with none. The next start gives the mind its need to serve alone while the card is short (LocalContext.KeptVariable),
    /// the list as for a new install, and a card with room does not keep it (<see cref="FitCard"/>).</summary>
    internal CardFitted? KeptForTheCard
    {
        get
        {
            lock (_sync)
            {
                try
                {
                    return File.Exists(_path) ? ByCardOf(JsonNode.Parse(File.ReadAllText(_path))) : null;
                }
                catch (Exception exception) when (exception is IOException or UnauthorizedAccessException or JsonException)
                {
                    return null;
                }
            }
        }
    }

    /// <summary>VRAM4B (the leader's decision, 2026-11-12: «si la persona nunca eligió perfil y el de fábrica no cabe, BAXY
    /// arranca sola en el perfil que sí cabe»): the mind's start found the card holds <paramref name="fitted"/>'s profile
    /// whole and not the factory's (MindSidecarClient.CardSaid, before the catalog is configured), or found nothing of the
    /// kind (null). VRAM4C (the leader's decision on VRAM4B's §7.2: «un asistente tiene que portarse igual todos los
    /// días… esa elección se queda fija… no vuelve sola a Completo aunque otro día haya memoria»): kept, while no profile
    /// is, as BAXY's choice for this PC (<see cref="Baxy.Kernel.Policy.ToolProfileStore.ByCard"/>), never the person's;
    /// changing it stays theirs (<see cref="Apply"/>, by voice too). VRAM4D (REV18 R18-2; the leader: «BAXY sólo fija una
    /// elección suya cuando la tarjeta es pequeña de verdad»): kept only when the mind found the card short in all
    /// (<paramref name="shortCard"/> true, LocalContext.CardMemory); on a card with room, or not known, this start's alone,
    /// and a choice of BAXY's kept from before goes (the 1.5.1's, on a card a game held at one start).</summary>
    internal void FitCard(CardFitted? fitted, bool? shortCard = null)
    {
        lock (_sync)
        {
            _fitted = null;
            if (shortCard == false && KeptForTheCard is not null)
            {
                _ = Keep(null);
            }

            if (fitted is null || !IsPreset(fitted.Profile) || fitted.Profile == Completo || File.Exists(_path))
            {
                return;
            }

            if (shortCard != true)
            {
                _fitted = fitted with { ThisStart = true };
                return;
            }

            _fitted = fitted with { ThisStart = false };
            // A folder that refuses the file leaves the profile this run's (Read), as before VRAM4C.
            _ = Keep(new JsonObject { ["profile"] = fitted.Profile, [ByCard] = CardJson(_fitted) });
        }
    }

    private const string ByCard = Baxy.Kernel.Policy.ToolProfileStore.ByCard;

    /// <summary>The view's notice of <paramref name="fitted"/> (boot «cardProfile»): the profile and Settings' figures.</summary>
    internal static JsonObject Notice(CardFitted fitted)
    {
        JsonObject json = CardJson(fitted);
        json.Insert(0, "profile", fitted.Profile);
        return json;
    }

    private static JsonObject CardJson(CardFitted fitted)
    {
        var json = new JsonObject { ["factory"] = Completo, ["freeMb"] = fitted.FreeMb, ["needMb"] = fitted.NeedMb };
        if (fitted.ThisStart)
        {
            json["thisStart"] = true;
        }

        return json;
    }

    // VRAM4C: BAXY's choice for the card as a file (or Json(), put back) says it: a smaller ready-made profile and the two
    // figures. Anything else is no such choice.
    private static CardFitted? ByCardOf(JsonNode? said) =>
        said is JsonObject file && file["profile"] is JsonValue named && named.TryGetValue(out string? profile)
        && profile is not null && IsPreset(profile) && profile != Completo && file[ByCard] is JsonObject card
        && card["freeMb"] is JsonValue free && free.TryGetValue(out int freeMb) && freeMb > 0
        && card["needMb"] is JsonValue need && need.TryGetValue(out int needMb) && needMb > 0
            ? new CardFitted(profile, freeMb, needMb, card["thisStart"] is JsonValue start && start.TryGetValue(out bool alone) && alone)
            : null;

    /// <summary>VRAM4B: what the mind is told of a profile this run took for the card (catalog.configure «cardProfile»,
    /// mind.CARD_PROFILE_FACT): the two profiles as Settings → Tools names them and the two figures; null with none.
    /// VRAM4D: none for a start's alone (ThisStart): the fact says the profile is kept, and the system text stays the one
    /// a person's Esencial reads.</summary>
    internal JsonObject? CardProfileFact() => Fitted is { ThisStart: false } fitted
        ? new JsonObject
        {
            ["profile"] = Shown(fitted.Profile, UiLanguage.IsEnglish),
            ["factory"] = Shown(Completo, UiLanguage.IsEnglish),
            ["freeMb"] = fitted.FreeMb,
            ["needMb"] = fitted.NeedMb,
        }
        : null;

    /// <summary>VRAM4B: what the profile is by the card, while it is (<see cref="FitCard"/>, nothing chosen since). VRAM4C: read
    /// from the file, so every start after the one that chose it says the same (Settings → Tools, the mind's fact).</summary>
    internal CardFitted? Fitted
    {
        get
        {
            lock (_sync)
            {
                if (!File.Exists(_path))
                {
                    return _fitted;
                }

                try
                {
                    return ByCardOf(JsonNode.Parse(File.ReadAllText(_path)));
                }
                catch (Exception exception) when (exception is IOException or UnauthorizedAccessException or JsonException)
                {
                    return null;
                }
            }
        }
    }

    /// <summary>VRAM4C (the leader: «el aviso sale una sola vez (la primera)»): the profile BAXY chose for the card on this
    /// run's start, while it is still the profile: the view's notice. Every start after it says nothing.</summary>
    internal CardFitted? SaidNow
    {
        get
        {
            CardFitted? now;
            lock (_sync)
            {
                now = _fitted;
            }

            return now is not null && Fitted == now ? now : null;
        }
    }

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
    /// tab never shows): the profile is named as the view shows it, in its language.
    /// AJU1 (dueño, 10-11: everything by voice, «actívalo en Ajustes» is never the only way): the call that turns it on by
    /// speaking, and no menu: with «turnOn» (Settings → Tools) beside it the 4B sent the person there instead of offering.
    internal JsonObject OffFacts(string operation)
    {
        (string profile, _) = Read();
        bool english = UiLanguage.IsEnglish;
        int level = FieldStepProjection.ProfileLevel(operation);
        // TPV1 (dueño, 10-11: everything by voice): the smallest ready-made profile that has it, switched by BAXY with the
        // person's «sí».
        string smallest = Presets.First(preset => preset.Level >= level).Name;
        return new JsonObject
        {
            ["tool"] = FieldStepProjection.EnglishTitle(operation),
            ["profile"] = Shown(profile, english),
            ["turnOnBySpeaking"] = WireNames.Call(OwnBrakes.Operation, new() { ["setting"] = OwnBrakes.ToolProfile, ["value"] = smallest })
                + $" switches to the profile {Shown(smallest, english)}, which has it; BAXY asks the person's yes itself",
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

        // VRAM4B: the same for the profile a start took for the card (Json's «byCard»): put back, it is still no choice of
        // the person's. VRAM4C: what was written in between (a profile lent to another model) goes, and BAXY's choice for
        // the card is kept again as it was.
        if (body[ByCard] is JsonObject)
        {
            if (ByCardOf(body) is not { } card)
            {
                return Invalid;
            }

            if (card.ThisStart)
            {
                // VRAM4D: this start's alone was never written: no file again, and the profile this run's.
                lock (_sync)
                {
                    _fitted = card;
                    return Keep(null);
                }
            }

            return Keep(new JsonObject { ["profile"] = card.Profile, [ByCard] = CardJson(card) });
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
            // VRAM4C: the person's now. VRAM4D (REV18 R18-1): Completo is written too, theirs, kept as any other.
            _fitted = null;
            return Keep(file);
        }
    }

    // The profile's file (null: none, the factory's). Null when kept, or why not.
    private string? Keep(JsonObject? file)
    {
        lock (_sync)
        {
            try
            {
                if (file is null)
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

        // VRAM4B: the profile is the card's, not the person's: Settings → Tools says why (VRAM4C: for as long as it is).
        if (Fitted is { } fitted)
        {
            json[ByCard] = CardJson(fitted);
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
                // VRAM4B: with no choice of the person's, the factory's, or the one this run's start took for the card.
                read = !File.Exists(_path) ? (_fitted?.Profile ?? Completo, null) : Parse(File.ReadAllText(_path));
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
