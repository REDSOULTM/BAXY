using System.Globalization;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Kernel.Operations;
using Baxy.Kernel.Policy;
using Baxy.Providers.Windows.Infrastructure;

namespace Baxy.Core.Operations;

/// <summary>
/// pc-f6-ajustes (f4-accesibilidad): BAXY's own settings by voice, the same switches the view's Settings and Proposals
/// panels write (<see cref="FieldSettingsStore"/>): its voice, web search, not interrupting while the person plays, is
/// in a call or watches a video, and the proposals' silence (30m, 1h or until tomorrow at 08:00; «on» ends it). Every
/// one is reversible and none asks. The file is read back and the result says the setting, its new value and, for a
/// silence, until when. Encargo 25 (G2): the confirmation mode is one of them too. Switching it off is done as
/// system.settings.set does. TPV1 (dueño, 10-11-2026: «la aplicación todo se controle por voz… el usuario probablemente no
/// tenga manos»; identidad: «No hay ninguna capacidad que exija ver la pantalla o usar el ratón»): switching it on is done
/// here too, after the person's «sí» the App always asks for it (OwnBrakes: the conscious setting of the identity, said
/// aloud), and so is the tool profile of Settings → Tools, a ready-made one (<see cref="ToolProfileStore"/>; the App
/// relaunches the mind with its tools once the turn ends). A value a setting does not take is refused with the values it
/// does take.
/// </summary>
internal sealed class OwnSettingsHandler(string? dataRoot, TimeProvider? time = null) : IOperationHandler
{
    internal const string Operation = "baxy.settings.set";

    // Each on/off setting: its key in the file, its default and whether «on» is stored as false (the voice is kept as
    // voiceMuted).
    private static readonly Dictionary<string, (string Key, bool Default, bool Inverted)> Switches =
        new(StringComparer.Ordinal)
        {
            ["no_interrupt_calls"] = ("ctx.call", true, false),
            ["no_interrupt_games"] = ("ctx.game", true, false),
            ["no_interrupt_videos"] = ("ctx.video", true, false),
            // actualizar-ordenes-app: the overlay of Settings › Personalización (FieldSettings.Overlay), shown by default.
            ["overlay"] = ("overlay", true, false),
            ["voice"] = ("voiceMuted", false, true),
            ["web_search"] = ("web", true, false),
            // TPV1 (dueño, 10-11: everything the view switches, by voice too): the rest of Ajustes' own switches, by the
            // keys FieldSettings keeps (General, Voz, Privacidad, Versión).
            ["close_to_tray"] = ("closeToTray", true, false),
            ["echo_cancel"] = ("echoCancel", true, false),
            ["minimize_to_tray"] = ("minimizeToTray", false, false),
            ["screen"] = ("screen", true, false),
            ["update_notice"] = ("updateNotice", true, false),
            ["wait_notice"] = ("waitNotice", true, false),
            ["wake_sound"] = ("wakeSound", true, false),
            ["weather"] = ("weather", true, false),
        };

    private const string Proposals = "proposals";

    // actualizar-ordenes-app (held-out 09-11: the model asked for it here, with baxy_settings_set, in 4 of 4 samples): the
    // accessible mode of BAXY's own window (PresentationModeStore, the one Ajustes › Accesibilidad and PUT /accessibility
    // write). It left system.settings.set, so BAXY's own switches are in one tool.
    internal const string AccessibleMode = "accessible_mode";

    internal const string ToolProfile = "tool_profile";

    private static readonly string[] SwitchValues = ["on", "off"];

    private static readonly string[] SilenceValues = ["30m", "1h", "tomorrow", "on"];

    private readonly TimeProvider _time = time ?? TimeProvider.System;

    public OperationDefinition Definition { get; } = ProductCatalog.CreateDefinition(Operation);

    public ValueTask<OperationOutcome> ExecuteAsync(OperationInvocation invocation, CancellationToken cancellationToken) =>
        ValueTask.FromResult(Execute(invocation.Arguments));

    private OperationOutcome Execute(JsonElement arguments)
    {
        string? setting = Text(arguments, "setting");
        string? value = Text(arguments, "value");
        if (ValuesOf(setting) is not { } taken)
        {
            return OperationOutcome.InvalidArguments(Definition, arguments);
        }

        if (value is null || !taken.Contains(value))
        {
            return OperationOutcome.InvalidArguments(
                Definition, arguments, new ArgumentProblem("value", "expected one of the values this setting takes")
                {
                    Allowed = taken,
                });
        }

        if (string.IsNullOrWhiteSpace(dataRoot))
        {
            return OperationOutcome.Failure("baxy_setting_unavailable");
        }

        if (setting == BaxySettingHandler.ConfirmationBypass)
        {
            return Bypass(dataRoot, value == "on");
        }

        if (setting == ToolProfile)
        {
            return Profile(dataRoot, value!);
        }

        if (setting == AccessibleMode)
        {
            return Accessible(dataRoot, value == "on");
        }

        if (!FieldSettingsStore.TryRead(dataRoot, out JsonObject values))
        {
            return OperationOutcome.Failure("baxy_setting_unreadable");
        }

        DateTimeOffset now = _time.GetUtcNow();
        DateTimeOffset? until = null;
        bool changed;
        if (setting == Proposals)
        {
            until = FieldSettingsStore.QuietUntil(value, now);
            changed = until is not null || FieldSettingsStore.QuietUntil(values, now) is not null;
            values["quiet"] = until is null ? null : value;
            values["quietUntil"] = until?.ToUnixTimeMilliseconds();
        }
        else
        {
            (string key, bool fallback, bool inverted) = Switches[setting!];
            bool stored = (value == "on") != inverted;
            changed = Flag(values, key, fallback) != stored;
            values[key] = stored;
        }

        try
        {
            FieldSettingsStore.Write(dataRoot, values);
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            return OperationOutcome.Failure(
                "baxy_setting_write_failed", effectMayHaveOccurred: true, causeCode: "external_effect_ambiguous");
        }

        if (!FieldSettingsStore.TryRead(dataRoot, out JsonObject after) || !Holds(after, setting!, value!, until, now))
        {
            return OperationOutcome.Failure("baxy_setting_postread_failed", effectMayHaveOccurred: changed);
        }

        return Receipt(setting!, value!, changed, until);
    }

    // The values each setting takes; null for one BAXY does not have.
    private static string[]? ValuesOf(string? setting) =>
        setting == Proposals ? SilenceValues
        : setting == ToolProfile ? ToolProfileStore.Presets
        : setting is BaxySettingHandler.ConfirmationBypass or AccessibleMode || (setting is not null && Switches.ContainsKey(setting))
            ? SwitchValues
            : null;

    // The confirmation mode, as system.settings.set switches it off: a file that cannot be read is not «normal», it is
    // written only when it says otherwise, and then read back.
    private static OperationOutcome Bypass(string dataRoot, bool on)
    {
        if (!ConfirmationModeStore.TryRead(dataRoot, out ConfirmationMode before))
        {
            return OperationOutcome.Failure("baxy_setting_unreadable");
        }

        ConfirmationMode wanted = on ? ConfirmationMode.Bypass : ConfirmationMode.Normal;
        bool changed = before != wanted;
        try
        {
            if (changed)
            {
                ConfirmationModeStore.Write(dataRoot, wanted);
            }
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            return OperationOutcome.Failure(
                "baxy_setting_write_failed", effectMayHaveOccurred: true, causeCode: "external_effect_ambiguous");
        }

        if (!ConfirmationModeStore.TryRead(dataRoot, out ConfirmationMode after) || after != wanted)
        {
            return OperationOutcome.Failure("baxy_setting_postread_failed", effectMayHaveOccurred: changed);
        }

        return Receipt(BaxySettingHandler.ConfirmationBypass, on ? "on" : "off", changed, until: null);
    }

    // A ready-made tool profile, read back from its file. The mind keeps the tools it started with until the App
    // relaunches it, once this turn ends: the receipt says so, so a reply never claims a tool this turn does not have.
    // REM1 (REV12 B-2): a broken file (a cut write) is replaced by the profile the person asked for: refusing left every
    // «pásate a…» unreadable for good, and only the panel could mend it. One another program holds is not written over.
    private static OperationOutcome Profile(string dataRoot, string profile)
    {
        bool read = ToolProfileStore.TryRead(dataRoot, out string before, out bool broken);
        if (!read && !broken)
        {
            return OperationOutcome.Failure("baxy_setting_unreadable");
        }

        bool changes = broken || before != profile;
        try
        {
            if (changes)
            {
                ToolProfileStore.WritePreset(dataRoot, profile);
            }
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            return OperationOutcome.Failure(
                "baxy_setting_write_failed", effectMayHaveOccurred: true, causeCode: "external_effect_ambiguous");
        }

        if (!ToolProfileStore.TryRead(dataRoot, out string after) || after != profile)
        {
            return OperationOutcome.Failure("baxy_setting_postread_failed", effectMayHaveOccurred: changes);
        }

        return Receipt(ToolProfile, profile, changes, until: null, repaired: broken);
    }

    // The accessible mode, read back from its file. A file that cannot be read is not «normal» (Revisión 2026-10-22, C-3).
    private static OperationOutcome Accessible(string dataRoot, bool on)
    {
        if (!PresentationModeStore.TryReadAccessible(dataRoot, out bool before))
        {
            return OperationOutcome.Failure("baxy_setting_unreadable");
        }

        try
        {
            if (before != on)
            {
                PresentationModeStore.WriteAccessible(dataRoot, on);
            }
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            return OperationOutcome.Failure(
                "baxy_setting_write_failed", effectMayHaveOccurred: true, causeCode: "external_effect_ambiguous");
        }

        if (!PresentationModeStore.TryReadAccessible(dataRoot, out bool after) || after != on)
        {
            return OperationOutcome.Failure("baxy_setting_postread_failed", effectMayHaveOccurred: before != on);
        }

        return Receipt(AccessibleMode, on ? "on" : "off", before != on, until: null);
    }

    // REM3 (REV13 D-1): repaired, a broken tool profile file written over. The App keeps the tools the mind started
    // with and relaunches it only if the file now withholds others (ToolProfile.NeedsSwitch); which ones it started with
    // this process does not know, so whether the profile in effect changed is not said, nor a restart promised.
    private static OperationOutcome Receipt(
        string setting, string value, bool changed, DateTimeOffset? until, bool repaired = false)
    {
        var receipt = new JsonObject
        {
            ["version"] = 1,
            ["setting"] = setting,
            ["value"] = value,
        };
        if (repaired)
        {
            receipt["repaired"] = true;
        }
        else
        {
            receipt["changed"] = changed;
        }
        if (setting == AccessibleMode && ModelAids.On(ModelAids.AccessibleScope))
        {
            // pc-ayudas: what the mode changes (SettingsPanel's «Modo accesible») and the modes the interface shows as not
            // ready yet (Rail's PROFILES), so a reply never promises more than the switch did.
            receipt["scope"] = "BAXY's own window only: larger text, more contrast, wider buttons";
            receipt["notAvailableYet"] = "a blind (screen reader) mode and a hands-free mobility mode";
        }
        if (setting == ToolProfile && changed)
        {
            // MUS1 (VIVO13: «BAXY se reiniciará en unos segundos», paraphrasing prose that said its model restarts; the
            // App never closed, only the model got ready again): what happens is typed. A tool the profile brings is
            // callable from the person's next request, not in this reply; the model gets ready with them once this
            // reply ends; the App stays open and the conversation is kept.
            receipt["toolsFrom"] = "next_request";
            receipt["modelGetsReady"] = repaired ? "after_this_reply_if_its_tools_differ" : "after_this_reply";
            receipt["appStaysOpen"] = true;
            receipt["conversationKept"] = true;
        }

        if (until is { } end)
        {
            receipt["until"] = TimeZoneInfo.ConvertTime(end, TimeZoneInfo.Local)
                .ToString("yyyy-MM-dd'T'HH:mm", CultureInfo.InvariantCulture);
        }

        receipt["authority"] = "baxy_profile_setting_postread";
        using JsonDocument result = JsonDocument.Parse(receipt.ToJsonString());
        return OperationOutcome.Success(result.RootElement.Clone());
    }

    // What the file says now is what was asked.
    private static bool Holds(JsonObject values, string setting, string value, DateTimeOffset? until, DateTimeOffset now)
    {
        if (setting == Proposals)
        {
            return FieldSettingsStore.QuietUntil(values, now)?.ToUnixTimeMilliseconds() == until?.ToUnixTimeMilliseconds();
        }

        (string key, bool fallback, bool inverted) = Switches[setting];
        return Flag(values, key, fallback) == ((value == "on") != inverted);
    }

    private static bool Flag(JsonObject values, string key, bool fallback) =>
        values[key] is JsonValue stored && stored.TryGetValue(out bool on) ? on : fallback;

    private static string? Text(JsonElement arguments, string name) =>
        arguments.ValueKind == JsonValueKind.Object
        && arguments.TryGetProperty(name, out JsonElement named)
        && named.ValueKind == JsonValueKind.String
            ? named.GetString()
            : null;
}
