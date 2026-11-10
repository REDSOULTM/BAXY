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

    // APP1 (REV_APP ASY-b): what the person chose that is not in the file yet (it could not be written). It holds over
    // the file's old value at every reading and is written again with the next change or reading, until it is.
    private readonly Dictionary<string, JsonNode?> _unwritten = new(StringComparer.Ordinal);

    internal FieldSettings(string dataRoot)
    {
        _dataRoot = dataRoot;
        _values = FieldSettingsStore.TryRead(dataRoot, out JsonObject values) ? values : new JsonObject();
    }

    /// <summary>
    /// Reads the file again: baxy.settings.set wrote it from the engine. A file that cannot be read now keeps what was
    /// read before; a choice that could not be written holds over the file and is written now if it can be.
    /// </summary>
    internal void Reload()
    {
        lock (_gate)
        {
            ReadFile();
            if (_unwritten.Count > 0)
            {
                Write();
            }
        }
    }

    /// <summary>True while a choice of the person is not in the file (<see cref="Write"/> failed): the view says so.</summary>
    internal bool Unsaved
    {
        get
        {
            lock (_gate)
            {
                return _unwritten.Count > 0;
            }
        }
    }

    private void ReadFile()
    {
        if (FieldSettingsStore.TryRead(_dataRoot, out JsonObject values))
        {
            _values = values;
        }

        foreach ((string key, JsonNode? value) in _unwritten)
        {
            _values[key] = value?.DeepClone();
        }
    }

    private void Set(string key, JsonNode? value)
    {
        _values[key] = value;
        _unwritten[key] = value?.DeepClone();
    }

    internal static FieldSettings CreateDefault() => new(MemoryOperationProtector.ResolveDataRoot());

    internal bool CloseToTray => Flag("closeToTray", true);

    /// <summary>«Al minimizar» (owner, 2026-11-08): minimizing hides the window in the tray instead of the taskbar.</summary>
    internal bool MinimizeToTray => Flag("minimizeToTray", false);

    /// <summary>The owner's «Arrancar con Windows»; until they switch it off, BAXY registers itself as before.</summary>
    internal bool AutostartWanted => Flag("autostart", true);

    internal bool VoiceMuted => Flag("voiceMuted", false);

    /// <summary>A short sound when the wake word is heard; on until the person switches it off (uso real 03-11: without
    /// it nothing tells the person BAXY heard «BAXY»).</summary>
    internal bool WakeSound => Flag("wakeSound", true);

    /// <summary>«Un momento» when a turn is silent 2.5 s (SilenceNotice); the owner can switch it off (2026-10-20: «está
    /// poniendo muchas trabas»).</summary>
    internal bool WaitNotice => Flag("waitNotice", true);

    /// <summary>«Quitar lo que suena en el PC»: the mind takes what the PC plays out of the microphone before the wake
    /// word and the recognizer hear it (voice_echo.py; uso real 03-11: a song's words went into a request). On until
    /// the owner switches it off; sent with every voice.start.</summary>
    internal bool EchoCancel => Flag("echoCancel", true);

    /// <summary>The person's choice of the interface's language: «auto» (Windows' display language, the default until
    /// they choose and for a value the file should not hold), «es» or «en»; <see cref="UiLanguage.Resolve"/> says which
    /// language it stands for.</summary>
    internal string Language
    {
        get
        {
            lock (_gate)
            {
                return _values["language"] is JsonValue value && value.TryGetValue(out string? choice)
                    && UiLanguage.IsChoice(choice) ? choice : UiLanguage.Auto;
            }
        }
    }

    internal bool WebAllowed => Flag("web", true);

    /// <summary>«Avisar de versiones nuevas» (actualizar-ordenes-app): one check where BAXY was published at each start; on
    /// until the person switches it off. It only tells: nothing updates without their «Actualizar».</summary>
    internal bool UpdateNotice => Flag("updateNotice", true);

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
    /// PRV1 (revisión de privacidad 2026-11-09, PRIV-07): the calls by which BAXY itself asks a service on the internet
    /// for what the person asked, with a request of its own: the web search and the pages it reads or downloads, the
    /// video it picks from a search of its own, and a game's title looked up in its store's public search. «Búsqueda
    /// web» switched off refused only the first three, and the others went out all the same under a switch that says
    /// «sale la búsqueda». The identity: «nada sale del PC salvo lo que «La red» permite» (00_IDENTIDAD.md), so the
    /// switch covers every one of them. What is opened in the person's own programs (a page in their browser, a place
    /// in an application of theirs) is not BAXY asking: it stays theirs to open. Every call the catalog says goes out
    /// is either here or named, with its reason, in FieldSettingsWebSwitchTests.
    /// </summary>
    internal static readonly IReadOnlySet<string> AsksTheWeb = new HashSet<string>(StringComparer.Ordinal)
    {
        "web.search", "web.fetch", "web.download", "media.play.youtube", "game.store.page", "game.install.named",
    };

    /// <summary>The code of a call «Búsqueda web» refuses.</summary>
    internal const string WebOff = "web_disabled_by_owner";

    /// <summary>
    /// The privacy switch that refuses this call, as the code the model reads, or null when it may run: «Búsqueda web»
    /// (<see cref="AsksTheWeb"/>), «Clima» (weather.current and a place's clock) and «Mirar la pantalla».
    /// </summary>
    internal string? Refusal(string operation, JsonObject arguments)
    {
        if (!WebAllowed && AsksTheWeb.Contains(operation))
        {
            return WebOff;
        }

        if (!WeatherAllowed && (operation == "weather.current"
            || (operation == "system.time" && arguments["place"] is JsonValue place && place.TryGetValue(out string? named)
                && !string.IsNullOrWhiteSpace(named))))
        {
            return "weather_disabled_by_owner";
        }

        return !ScreenAllowed && ScreenOperations.Contains(operation) ? "screen_disabled_by_owner" : null;
    }

    /// <summary>
    /// COR1: whether one of BAXY's own brakes (<see cref="OwnBrakes"/>, by its baxy.settings.set setting) is on now, as
    /// the file says: a change that would relax it is the person's to ask for. A setting that is no brake is not on.
    /// </summary>
    internal bool BrakeOn(string setting) => setting switch
    {
        "web_search" => !WebAllowed,
        "voice" => VoiceMuted,
        "proposals" => QuietUntil is not null,
        "no_interrupt_calls" => Flag("ctx.call", true),
        "no_interrupt_games" => Flag("ctx.game", true),
        "no_interrupt_videos" => Flag("ctx.video", true),
        _ => false,
    };

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
            ReadFile();
            foreach (string key in (string[])["autostart", "closeToTray", "minimizeToTray", "voiceMuted", "wakeSound", "waitNotice", "echoCancel", "web", "weather", "screen", "updateNotice"])
            {
                if (body[key] is JsonValue value && value.TryGetValue(out bool on))
                {
                    Set(key, on);
                }
            }

            Write();
        }
    }

    /// <summary>The overlay that says what BAXY does while its window is behind (owner, 2026-11-08).</summary>
    internal OverlaySettings Overlay
    {
        get
        {
            lock (_gate)
            {
                return new OverlaySettings(
                    Read("overlay", true),
                    ReadChoice("overlayCorner", OverlaySettings.Corners, "br"),
                    ReadChoice("overlaySize", OverlaySettings.Sizes, "m"),
                    ReadNumber("overlayOpacity", 78, static v => v is >= 40 and <= 100),
                    ReadNumber("overlayHide", 8, static v => OverlaySettings.Hides.Contains(v)),
                    Read("overlayNotFullscreen", true),
                    Read("overlayAnswer", false));
            }
        }
    }

    /// <summary>Writes the overlay's settings the body names; null, and nothing written, when any of them is not a choice.</summary>
    internal OverlaySettings? ApplyOverlay(JsonObject body)
    {
        ArgumentNullException.ThrowIfNull(body);
        var writes = new List<(string Key, JsonNode Value)>();
        foreach ((string field, string key) in (ReadOnlySpan<(string, string)>)[("on", "overlay"), ("notFullscreen", "overlayNotFullscreen"), ("answer", "overlayAnswer")])
        {
            if (body[field] is null)
            {
                continue;
            }

            if (body[field] is not JsonValue flag || !flag.TryGetValue(out bool on))
            {
                return null;
            }

            writes.Add((key, JsonValue.Create(on)));
        }

        foreach ((string field, string key, string[] allowed) in (ReadOnlySpan<(string, string, string[])>)[("corner", "overlayCorner", OverlaySettings.Corners), ("size", "overlaySize", OverlaySettings.Sizes)])
        {
            if (body[field] is null)
            {
                continue;
            }

            if ((string?)(body[field] as JsonValue) is not { } choice || !allowed.Contains(choice))
            {
                return null;
            }

            writes.Add((key, JsonValue.Create(choice)));
        }

        foreach ((string field, string key, Func<int, bool> valid) in (ReadOnlySpan<(string, string, Func<int, bool>)>)[
            ("opacity", "overlayOpacity", static v => v is >= 40 and <= 100), ("hideSeconds", "overlayHide", static v => OverlaySettings.Hides.Contains(v))])
        {
            if (body[field] is null)
            {
                continue;
            }

            if (body[field] is not JsonValue number || !number.TryGetValue(out int value) || !valid(value))
            {
                return null;
            }

            writes.Add((key, JsonValue.Create(value)));
        }

        lock (_gate)
        {
            ReadFile();
            foreach ((string key, JsonNode value) in writes)
            {
                Set(key, value);
            }

            Write();
        }

        return Overlay;
    }

    internal JsonObject OverlayJson()
    {
        OverlaySettings o = Overlay;
        return new JsonObject
        {
            ["on"] = o.On,
            ["corner"] = o.Corner,
            ["size"] = o.Size,
            ["opacity"] = o.Opacity,
            ["hideSeconds"] = o.HideSeconds,
            ["notFullscreen"] = o.NotFullscreen,
            ["answer"] = o.Answer,
            ["unsaved"] = Unsaved,
        };
    }

    private bool Read(string key, bool fallback) =>
        _values[key] is JsonValue value && value.TryGetValue(out bool on) ? on : fallback;

    private string ReadChoice(string key, string[] allowed, string fallback) =>
        _values[key] is JsonValue value && value.TryGetValue(out string? choice) && allowed.Contains(choice) ? choice : fallback;

    private int ReadNumber(string key, int fallback, Func<int, bool> valid) =>
        _values[key] is JsonValue value && value.TryGetValue(out int number) && valid(number) ? number : fallback;

    /// <summary>Writes the choice of the interface's language; false, and nothing written, for any word but «auto», «es»
    /// or «en».</summary>
    internal bool ApplyLanguage(string? choice)
    {
        if (!UiLanguage.IsChoice(choice))
        {
            return false;
        }

        lock (_gate)
        {
            ReadFile();
            Set("language", choice);
            Write();
        }

        return true;
    }

    /// <summary>Writes «no me interrumpas» and the silence: 30m, 1h or tomorrow (until 08:00 local), null to end it.</summary>
    internal void ApplyProposals(JsonObject body, DateTimeOffset now)
    {
        lock (_gate)
        {
            ReadFile();
            if (body["ctx"] is JsonObject ctx)
            {
                foreach ((string name, string key) in (ReadOnlySpan<(string, string)>)[("game", "ctx.game"), ("call", "ctx.call"), ("video", "ctx.video")])
                {
                    if (ctx[name] is JsonValue value && value.TryGetValue(out bool on))
                    {
                        Set(key, on);
                    }
                }
            }

            if (body.ContainsKey("quiet"))
            {
                string? span = body["quiet"] is JsonValue q && q.TryGetValue(out string? text) ? text : null;
                DateTimeOffset? until = FieldSettingsStore.QuietUntil(span, now);
                Set("quiet", until is null ? null : span);
                Set("quietUntil", until?.ToUnixTimeMilliseconds());
            }

            Write();
        }
    }

    internal JsonObject GeneralJson((bool? On, string? Blocked) autostart) => new()
    {
        ["autostart"] = autostart.On,
        ["autostartBlocked"] = autostart.Blocked,
        ["closeToTray"] = CloseToTray,
        ["minimizeToTray"] = MinimizeToTray,
        ["voiceMuted"] = VoiceMuted,
        ["wakeSound"] = WakeSound,
        ["waitNotice"] = WaitNotice,
        ["echoCancel"] = EchoCancel,
        ["web"] = WebAllowed,
        ["weather"] = WeatherAllowed,
        ["screen"] = ScreenAllowed,
        ["updateNotice"] = UpdateNotice,
        ["language"] = Language,
        ["languageInUse"] = UiLanguage.Resolve(Language),
        ["unsaved"] = Unsaved,
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
            ["unsaved"] = Unsaved,
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
            _unwritten.Clear();
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException or ArgumentException)
        {
            // The choice holds for this run (_unwritten) and the view says so; the file is written again with the next
            // change or reading. Only the exception's type is kept, never the person's values.
            UnhandledFailures.Record("settings.write", exception, Path.Combine(_dataRoot, "diagnostics"));
        }
    }
}

/// <summary>The overlay's settings: shown or not, its corner (tl, tr, bl, br), size (s, m, l), how opaque it is (40 to 100
/// %), how many seconds the end stays (0 keeps it), whether it stays off full-screen windows, and whether a card can be
/// answered from it.</summary>
internal sealed record OverlaySettings(bool On, string Corner, string Size, int Opacity, int HideSeconds, bool NotFullscreen, bool Answer)
{
    internal static readonly string[] Corners = ["tl", "tr", "bl", "br"];
    internal static readonly string[] Sizes = ["s", "m", "l"];
    internal static readonly int[] Hides = [5, 8, 15, 0];
}
