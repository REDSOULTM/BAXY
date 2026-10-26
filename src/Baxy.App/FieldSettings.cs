using System.IO;
using System.Text.Json.Nodes;
using Baxy.Kernel.Policy;

namespace Baxy.App;

/// <summary>
/// What the owner chose in the view's Settings and Proposals panels (design v4), in one file of the profile
/// (<c>&lt;datos&gt;/field-settings.v1.json</c>, <see cref="FieldSettingsStore"/>; the chat's <c>baxy.settings.set</c>
/// writes it too, <see cref="Reload"/>). Each switch changes what BAXY does, never how the model decides:
/// the privacy switches refuse a call before it runs (<see cref="NativeTurnLoop"/>), the voice ones change what the
/// App asks the mind, and the proposal ones change when the heartbeat looks and whether its words are spoken.
/// </summary>
internal sealed class FieldSettings
{
    // Operations that read what is on the screen (a capture, the text or controls of a window): «Mirar la pantalla».
    private static readonly HashSet<string> ScreenOperations = new(StringComparer.Ordinal)
    {
        "capture.screenshot", "capture.active.window", "vision.describe", "ocr.read", "input.visible.controls",
    };

    private readonly string _dataRoot;
    private readonly object _gate = new();
    private JsonObject _values;

    internal FieldSettings(string dataRoot)
    {
        _dataRoot = dataRoot;
        _values = FieldSettingsStore.TryRead(dataRoot, out JsonObject values) ? values : new JsonObject();
    }

    /// <summary>
    /// Reads the file again: baxy.settings.set wrote it from the engine. A file that cannot be read now keeps what was
    /// read before.
    /// </summary>
    internal void Reload()
    {
        lock (_gate)
        {
            if (FieldSettingsStore.TryRead(_dataRoot, out JsonObject values))
            {
                _values = values;
            }
        }
    }

    internal static FieldSettings CreateDefault() => new(MemoryOperationProtector.ResolveDataRoot());

    internal bool CloseToTray => Flag("closeToTray", true);

    /// <summary>The owner's «Arrancar con Windows»; until they switch it off, BAXY registers itself as before.</summary>
    internal bool AutostartWanted => Flag("autostart", true);

    internal bool VoiceMuted => Flag("voiceMuted", false);

    internal bool WakeSound => Flag("wakeSound", false);

    /// <summary>«Un momento» when a turn is silent 2.5 s (SilenceNotice); the owner can switch it off (2026-10-20: «está
    /// poniendo muchas trabas»).</summary>
    internal bool WaitNotice => Flag("waitNotice", true);

    internal bool WebAllowed => Flag("web", true);

    internal bool WeatherAllowed => Flag("weather", true);

    internal bool ScreenAllowed => Flag("screen", true);

    /// <summary>Not to be interrupted (spoken to) while the person plays, is in a call or watches a video.</summary>
    internal bool QuietDuring(string activity) => activity switch
    {
        HeartbeatMoment.Playing => Flag("ctx.game", true),
        HeartbeatMoment.InCall => Flag("ctx.call", true),
        HeartbeatMoment.Watching => Flag("ctx.video", true),
        _ => false,
    };

    /// <summary>Proposals are silenced until this moment (UTC), or null when they are on.</summary>
    internal DateTimeOffset? QuietUntil
    {
        get
        {
            lock (_gate)
            {
                return FieldSettingsStore.QuietUntil(_values, DateTimeOffset.UtcNow);
            }
        }
    }

    internal string? QuietSpan => QuietUntil is null ? null : (string?)Snapshot()["quiet"];

    /// <summary>
    /// The privacy switch that refuses this call, as the code the model reads, or null when it may run: «Búsqueda web»
    /// (web.search, web.fetch, web.download), «Clima» (weather.current and a place's clock) and «Mirar la pantalla».
    /// </summary>
    internal string? Refusal(string operation, JsonObject arguments)
    {
        if (!WebAllowed && operation is "web.search" or "web.fetch" or "web.download")
        {
            return "web_disabled_by_owner";
        }

        if (!WeatherAllowed && (operation == "weather.current"
            || (operation == "system.time" && arguments["place"] is JsonValue place && place.TryGetValue(out string? named)
                && !string.IsNullOrWhiteSpace(named))))
        {
            return "weather_disabled_by_owner";
        }

        return !ScreenAllowed && ScreenOperations.Contains(operation) ? "screen_disabled_by_owner" : null;
    }

    internal JsonObject Snapshot()
    {
        lock (_gate)
        {
            return (JsonObject)_values.DeepClone();
        }
    }

    /// <summary>Writes the general switches the body names; anything else in it is ignored.</summary>
    internal void ApplyGeneral(JsonObject body)
    {
        lock (_gate)
        {
            Reload();
            foreach (string key in (string[])["autostart", "closeToTray", "voiceMuted", "wakeSound", "waitNotice", "web", "weather", "screen"])
            {
                if (body[key] is JsonValue value && value.TryGetValue(out bool on))
                {
                    _values[key] = on;
                }
            }

            Write();
        }
    }

    /// <summary>Writes «no me interrumpas» and the silence: 30m, 1h or tomorrow (until 08:00 local), null to end it.</summary>
    internal void ApplyProposals(JsonObject body, DateTimeOffset now)
    {
        lock (_gate)
        {
            Reload();
            if (body["ctx"] is JsonObject ctx)
            {
                foreach ((string name, string key) in (ReadOnlySpan<(string, string)>)[("game", "ctx.game"), ("call", "ctx.call"), ("video", "ctx.video")])
                {
                    if (ctx[name] is JsonValue value && value.TryGetValue(out bool on))
                    {
                        _values[key] = on;
                    }
                }
            }

            if (body.ContainsKey("quiet"))
            {
                string? span = body["quiet"] is JsonValue q && q.TryGetValue(out string? text) ? text : null;
                DateTimeOffset? until = FieldSettingsStore.QuietUntil(span, now);
                _values["quiet"] = until is null ? null : span;
                _values["quietUntil"] = until?.ToUnixTimeMilliseconds();
            }

            Write();
        }
    }

    internal JsonObject GeneralJson((bool? On, string? Blocked) autostart) => new()
    {
        ["autostart"] = autostart.On,
        ["autostartBlocked"] = autostart.Blocked,
        ["closeToTray"] = CloseToTray,
        ["voiceMuted"] = VoiceMuted,
        ["wakeSound"] = WakeSound,
        ["waitNotice"] = WaitNotice,
        ["web"] = WebAllowed,
        ["weather"] = WeatherAllowed,
        ["screen"] = ScreenAllowed,
    };

    internal JsonObject ProposalsJson()
    {
        DateTimeOffset? until = QuietUntil;
        return new JsonObject
        {
            ["quietUntil"] = until?.ToUnixTimeMilliseconds(),
            ["quiet"] = until is null ? null : QuietSpan,
            ["ctx"] = new JsonObject
            {
                ["game"] = Flag("ctx.game", true),
                ["call"] = Flag("ctx.call", true),
                ["video"] = Flag("ctx.video", true),
            },
        };
    }

    private bool Flag(string key, bool fallback)
    {
        lock (_gate)
        {
            return _values[key] is JsonValue value && value.TryGetValue(out bool on) ? on : fallback;
        }
    }

    private void Write()
    {
        try
        {
            FieldSettingsStore.Write(_dataRoot, _values);
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException or ArgumentException)
        {
            // The choice holds for this run; the file is written again with the next one.
        }
    }
}
