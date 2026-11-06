using System.Globalization;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Kernel.Operations;
using Baxy.Kernel.Policy;

namespace Baxy.Core.Operations;

/// <summary>
/// pc-f6-ajustes (f4-accesibilidad): BAXY's own settings by voice, the same switches the view's Settings and Proposals
/// panels write (<see cref="FieldSettingsStore"/>): its voice, web search, not interrupting while the person plays, is
/// in a call or watches a video, and the proposals' silence (30m, 1h or until tomorrow at 08:00; «on» ends it). Every
/// one is reversible and none asks. The file is read back and the result says the setting, its new value and, for a
/// silence, until when. Encargo 25 (G2): the confirmation mode is one of them too. Switching it off is done as
/// system.settings.set does; switching it on stays a gesture in BAXY's own window, so it is refused with what is true
/// (<see cref="BaxySettingHandler.BypassInterfaceOnly"/>). A value a setting does not take is refused with the values
/// it does take.
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
            ["voice"] = ("voiceMuted", false, true),
            ["web_search"] = ("web", true, false),
        };

    private const string Proposals = "proposals";

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
            return value == "on" ? BaxySettingHandler.BypassInterfaceOnly(dataRoot) : BypassOff(dataRoot);
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
        : setting == BaxySettingHandler.ConfirmationBypass || (setting is not null && Switches.ContainsKey(setting))
            ? SwitchValues
            : null;

    // Bypass off, as system.settings.set switches it: a file that cannot be read is not «normal», it is written only
    // when it said bypass, and then read back.
    private static OperationOutcome BypassOff(string dataRoot)
    {
        if (!ConfirmationModeStore.TryRead(dataRoot, out ConfirmationMode before))
        {
            return OperationOutcome.Failure("baxy_setting_unreadable");
        }

        bool changed = before == ConfirmationMode.Bypass;
        try
        {
            if (changed)
            {
                ConfirmationModeStore.Write(dataRoot, ConfirmationMode.Normal);
            }
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            return OperationOutcome.Failure(
                "baxy_setting_write_failed", effectMayHaveOccurred: true, causeCode: "external_effect_ambiguous");
        }

        if (!ConfirmationModeStore.TryRead(dataRoot, out ConfirmationMode after) || after != ConfirmationMode.Normal)
        {
            return OperationOutcome.Failure("baxy_setting_postread_failed", effectMayHaveOccurred: changed);
        }

        return Receipt(BaxySettingHandler.ConfirmationBypass, "off", changed, until: null);
    }

    private static OperationOutcome Receipt(string setting, string value, bool changed, DateTimeOffset? until)
    {
        var receipt = new JsonObject
        {
            ["version"] = 1,
            ["setting"] = setting,
            ["value"] = value,
            ["changed"] = changed,
        };
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
