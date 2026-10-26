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
/// silence, until when.
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

    private readonly TimeProvider _time = time ?? TimeProvider.System;

    public OperationDefinition Definition { get; } = ProductCatalog.CreateDefinition(Operation);

    public ValueTask<OperationOutcome> ExecuteAsync(OperationInvocation invocation, CancellationToken cancellationToken) =>
        ValueTask.FromResult(Execute(invocation.Arguments));

    private OperationOutcome Execute(JsonElement arguments)
    {
        string? setting = Text(arguments, "setting");
        string? value = Text(arguments, "value");
        bool valid = setting == Proposals
            ? value is "30m" or "1h" or "tomorrow" or "on"
            : setting is not null && Switches.ContainsKey(setting) && value is "on" or "off";
        if (!valid)
        {
            return OperationOutcome.Failure("baxy_setting_value_invalid");
        }

        if (string.IsNullOrWhiteSpace(dataRoot))
        {
            return OperationOutcome.Failure("baxy_setting_unavailable");
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
