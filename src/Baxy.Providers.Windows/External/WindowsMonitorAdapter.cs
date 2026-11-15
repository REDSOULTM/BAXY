using System.ComponentModel;
using System.Text.Json;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// RUT2 (pedido del dueño 10-11-2026: «desactiva la pantalla de la izquierda»): display.status reads every connected
/// monitor from the display topology, on and off, with its desktop position (left, right, above, below or middle of the
/// ones on), whether it is the primary one and its mode; display.monitor.set takes one off the desktop or puts it back,
/// chosen by that position or by being (or not being) the primary one, and reads the topology again. Never the only
/// monitor on (PAN2: that one goes dark instead, Darken, and active true wakes it; PAN7: on a Modern Standby PC, where the
/// display turning off is the standby, it goes black under a window instead, Blackout); the receipt says when BAXY's own window was on the one taken off (Windows moves it to one that stays).
/// What a monitor looked like when this adapter took it off is kept, and putting it back says whether it came back the
/// same (asBefore). Windows itself restores the layout that set of monitors last had (<see cref="WindowsMonitorPlatform"/>).
/// </summary>
internal sealed class WindowsMonitorAdapter : IExternalOperationAdapter
{
    internal const string OnlyMonitor = "only_active_monitor";
    internal const string NotFound = "monitor_not_found";
    internal const string Ambiguous = "monitor_ambiguous";
    internal const string NotVerified = "monitor_change_not_verified";
    internal const string WouldSleep = "screen_off_would_sleep";

    private readonly IMonitorPlatform _platform;
    private readonly Dictionary<string, (MonitorState State, string Position)> _takenOff = new(StringComparer.Ordinal);
    private readonly Lock _gate = new();
    // PAN5 (REV19 P-4): the name of the monitor BAXY darkened, null when it darkened none (or it was woken).
    private string? _darkened;

    // PAN5 (REV19 P-5): this session's last input when the screen went dark; a different one later is a key or a mouse
    // move, which lit it.
    private uint? _darkenedInput;

    // PAN7: whether what BAXY darkened went black (a window over it, Modern Standby) rather than powered off.
    private bool _blackedOut;

    // PAN7: whether going black lowered the panel's brightness (and taking the black off gives it back).
    private bool _brightnessLowered;

    internal WindowsMonitorAdapter()
        : this(new WindowsMonitorPlatform())
    {
    }

    internal WindowsMonitorAdapter(IMonitorPlatform platform) =>
        _platform = platform ?? throw new ArgumentNullException(nameof(platform));

    public bool CanHandle(string operation) => operation is "display.status" or "display.monitor.set";

    public ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        var effectBoundary = new ExternalEffectBoundary();
        try
        {
            cancellationToken.ThrowIfCancellationRequested();
            lock (_gate)
            {
                ForgetDarkAfterInput();
                return ValueTask.FromResult(operation == "display.status"
                    ? Status(operation)
                    : Set(operation, arguments, effectBoundary));
            }
        }
        catch (Exception exception) when (exception is Win32Exception or InvalidOperationException
            or EntryPointNotFoundException or InvalidDataException)
        {
            return ValueTask.FromResult(effectBoundary.Failure(operation, "display_topology_failed"));
        }
    }

    private ExternalCapabilityReceipt Status(string operation)
    {
        IReadOnlyList<MonitorState> monitors = _platform.Monitors();
        if (!monitors.Any(static monitor => monitor.Active))
        {
            return ExternalJson.Failure(operation, "display_devices_not_found");
        }

        return ExternalJson.Success(operation, ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 2);
            writer.WriteNumber("monitorCount", monitors.Count(static monitor => monitor.Active));
            WriteMonitors(writer, monitors);
            WriteDark(writer);
            writer.WriteString("authority", "windows_display_config_read");
            writer.WriteEndObject();
        }), effectObserved: false);
    }

    private ExternalCapabilityReceipt Set(string operation, JsonElement arguments, ExternalEffectBoundary effectBoundary)
    {
        bool active = arguments.TryGetProperty("active", out JsonElement activeValue)
            && activeValue.ValueKind == JsonValueKind.True;
        string? which = arguments.TryGetProperty("monitor", out JsonElement monitorValue)
            && monitorValue.ValueKind == JsonValueKind.String ? monitorValue.GetString() : null;
        IReadOnlyList<MonitorState> monitors = _platform.Monitors();
        MonitorState[] on = monitors.Where(static monitor => monitor.Active).ToArray();
        MonitorState[] pool = active
            ? monitors.Where(static monitor => !monitor.Active).ToArray()
            : on;
        // PAN2 (CMP1: «Apaga la pantalla.» with one monitor went to system.power lock 30 of 40, as no tool darkened the
        // screen): the only monitor on stays on the desktop and goes dark instead, as Windows darkens it when idle.
        if (!active && on.Length <= 1)
        {
            // PAN4 (puerta INT34, c129-V4: «el Belmora sigue ahí abajo… apágalo completo» → monitor below, 9 of 10, and the
            // screen went dark): a monitor named that is not the one on (a place among several, secondary) is no monitor
            // here, as with more than one; nothing changes and the result lists the one there is.
            if (on.Length == 1 && which is not null && !Is(on[0], which, on))
            {
                return Refused(operation, NotFound, monitors, alone: on[0].Name);
            }

            // PAN7 (VIVO21: on the notebook SC_MONITORPOWER put the whole PC on Modern Standby; the network went down and
            // BAXY stopped hearing): where the display turning off is the standby (or Windows does not say), the display
            // is never turned off; a black window and the lowest brightness darken it, and the PC stays on.
            if (on.Length == 1 && _platform.ModernStandby() is not false)
            {
                effectBoundary.Cross();
                ScreenBlackout? black = _platform.Blackout();
                if (black is null)
                {
                    return Refused(operation, WouldSleep, monitors);
                }

                _darkened = on[0].Name;
                _blackedOut = true;
                // Revisión ciega PAN7 (4): the input the window itself started from, not one read seconds later.
                _darkenedInput = black.InputAtStart ?? _platform.LastInput();
                return Black(operation, _darkened, black);
            }

            effectBoundary.Cross();
            if (on.Length == 0 || !_platform.Darken())
            {
                return Refused(operation, OnlyMonitor, monitors);
            }

            _darkened = on[0].Name;
            _blackedOut = false;
            _darkenedInput = _platform.LastInput();
            return Lit(operation, false, _darkened);
        }

        // PAN5 (REV19 P-2: with a TV connected off the desktop, «vuelve a encender la pantalla» after darkening put the TV
        // on the desktop and the dark screen stayed dark): what BAXY darkened wakes first, unless what was asked names
        // another monitor; the topology is not touched.
        if (active && _darkened is { } dark && (pool.Length == 0 || which is null || (on.Length == 1 && Is(on[0], which, on))))
        {
            effectBoundary.Cross();
            if (_blackedOut)
            {
                // PAN7: what went black comes back by taking the window off; nothing is posted to Windows. Revisión ciega
                // PAN7 (5): with no window up any more (or one that did not end in time), the receipt says so.
                bool ended = _platform.EndBlackout();
                _darkened = null;
                _blackedOut = false;
                return Black(operation, dark, null, ended);
            }

            if (!_platform.Wake())
            {
                return ExternalJson.FailureBeforeEffect(operation, NotVerified);
            }

            _darkened = null;
            return Lit(operation, true, dark);
        }

        if (active && pool.Length == 0)
        {
            // Every connected monitor is on already: the request is the state reached, nothing changes.
            return ExternalJson.Switched(operation, ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteBoolean("active", true);
                writer.WriteBoolean("changed", false);
                WriteMonitors(writer, monitors);
                writer.WriteEndObject();
            }), effectObserved: false);
        }

        // Revisión ciega RUT2 (1, 6): the one monitor off comes back on unless what was asked contradicts where it was
        // when this adapter turned it off; with nothing named and more than one it could be, the choice is unclear.
        MonitorState[] chosen = which is null
            ? active && pool.Length == 1 ? pool : []
            : active && pool.Length == 1 && !Contradicts(pool[0], which)
                ? pool
                : pool.Where(monitor => Is(monitor, which, on)).ToArray();
        if (chosen.Length != 1)
        {
            return Refused(operation, chosen.Length == 0 && which is not null ? NotFound : Ambiguous, monitors);
        }

        MonitorState target = chosen[0];
        string position = active
            ? _takenOff.TryGetValue(target.Key, out var kept) ? kept.Position : string.Empty
            : Position(target, on);
        bool baxyThere = !active && _platform.ProductWindows().Any(window => Holds(target, window));
        effectBoundary.Cross();
        int result = _platform.SetActive(target.Key, active);
        IReadOnlyList<MonitorState> after = _platform.Monitors();
        MonitorState? now = after.FirstOrDefault(monitor => monitor.Key == target.Key);
        // Revisión ciega RUT2 (3): turned off is the monitor read back off, not one the read-back did not find.
        bool reached = result == 0 && now is not null && now.Active == active
            && after.Any(static monitor => monitor.Active);
        if (!reached)
        {
            return ExternalJson.WithStateAfter(
                ExternalJson.FailureAfterEffect(operation, NotVerified),
                ExternalJson.Create(writer =>
                {
                    writer.WriteStartObject();
                    writer.WriteBoolean("active", now?.Active == true);
                    writer.WriteBoolean("requested", false);
                    writer.WriteEndObject();
                }));
        }

        bool? asBefore = null;
        if (active)
        {
            if (_takenOff.Remove(target.Key, out var before))
            {
                asBefore = now!.X == before.State.X && now.Y == before.State.Y
                    && now.Width == before.State.Width && now.Height == before.State.Height;
            }
        }
        else
        {
            _takenOff[target.Key] = (target, position);
        }

        return ExternalJson.Success(operation, ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteBoolean("active", active);
            writer.WriteBoolean("changed", true);
            writer.WriteString("monitor", target.Name);
            if (position.Length > 0)
            {
                writer.WriteString("position", position);
            }

            if (target.Primary)
            {
                writer.WriteBoolean("wasPrimary", true);
            }

            if (baxyThere)
            {
                writer.WriteBoolean("baxyWindowThere", true);
            }

            if (asBefore is { } same)
            {
                writer.WriteBoolean("asBefore", same);
            }

            WriteMonitors(writer, after);
            WriteDark(writer);
            writer.WriteString("authority", "windows_display_config_postread");
            writer.WriteEndObject();
        }));
    }

    // PAN5 (blind review of PAN5, 2 and 3): what BAXY darkened and nothing lit since is said by name wherever the monitors
    // are listed, a monitor put on while it is dark included (whether that lights it is not read); with no last input
    // from Windows when it went dark, BAXY cannot tell whether a key or the mouse lit it.
    private void WriteDark(Utf8JsonWriter writer)
    {
        if (_darkened is null)
        {
            return;
        }

        writer.WriteBoolean("screenTurnedOffByBaxy", true);
        writer.WriteString("darkenedMonitor", _darkened);
        writer.WriteString("note", _blackedOut
            ? "BAXY covered this screen with a black window; the display and the PC are still on"
                + (_darkenedInput is null ? "" : " and no key or mouse move came since")
            : _darkenedInput is null
            ? "BAXY asked Windows to turn this screen off; BAXY cannot tell whether a key or mouse move lit it since: "
                + "active only says the monitor is still on the desktop"
            : "BAXY asked Windows to turn this screen off and no key or mouse move came since: active only says the "
                + "monitor is still on the desktop");
    }

    // PAN5 (REV19 P-5: darkened at 10:00, the mouse moved, and at 18:00 display.status still said screenTurnedOffByBaxy):
    // input after darkening lit the screen; it is no longer BAXY's dark one. Unknown input changes nothing.
    private void ForgetDarkAfterInput()
    {
        if (_darkened is not null && _darkenedInput is { } then && _platform.LastInput() is { } now && now != then)
        {
            // PAN7: the black window took itself off on that input (WindowsScreenBlackout).
            _darkened = null;
            _blackedOut = false;
        }
    }

    // PAN7: what going black did (black: what Blackout did) or taking the black off (black null). The display was never
    // turned off: on a Modern Standby PC that is the standby (Microsoft Learn, «Prepare software for modern standby»).
    private ExternalCapabilityReceipt Black(string operation, string monitor, ScreenBlackout? black, bool ended = true)
    {
        bool on = black is null;
        if (black is { } shown)
        {
            _brightnessLowered = shown.BrightnessBefore is not null;
        }

        bool lowered = _brightnessLowered;
        if (on && !ended)
        {
            return ExternalJson.Switched(operation, ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteBoolean("active", true);
                writer.WriteBoolean("changed", false);
                writer.WriteString("monitor", monitor);
                writer.WriteString("next", "BAXY's black window was no longer up on this screen (a key or a mouse move "
                    + "takes it off): nothing changed now");
                writer.WriteEndObject();
            }), effectObserved: false);
        }

        return ExternalJson.Success(operation, ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteBoolean("active", on);
            writer.WriteBoolean("changed", true);
            writer.WriteString("monitor", monitor);
            writer.WriteBoolean("screenBlack", !on);
            writer.WriteBoolean("displayPoweredOff", false);
            writer.WriteBoolean("pcStaysOn", true);
            writer.WriteBoolean(on ? "brightnessGivenBack" : "brightnessLowered", lowered);
            writer.WriteString("authority", "baxy_black_window");
            writer.WriteString("next", on
                ? "BAXY took its black window off the screen" + (lowered ? " and gave the brightness back" : "")
                : "the screen is black now: BAXY put a black window over it"
                    + (lowered ? " and set the brightness to its minimum" : "")
                    + "; it did not turn the display off, because on this PC that puts the whole PC on standby and BAXY "
                    + "would stop hearing; the PC stays on and BAXY keeps listening; a key, a mouse move or turning the "
                    + "screen on again takes the black off");
            writer.WriteEndObject();
        }));
    }

    // What darkening or waking the screens was: asked of Windows, not read back (no read of the displays' power state).
    // No monitor list: the one darkened is still active on the desktop, and the model read that as never turned off.
    // PAN5 (REV19 P-4: «apaga la tele» with the TV off the desktop darkens the monitor): the monitor's name is said.
    // REV20 P5-2: nothing says whether the session locked (with Modern Standby, Screen Off leads to sleep in S0 and waking
    // can ask for the password; BAXY never reads it), so the receipt does not say it did not.
    private static ExternalCapabilityReceipt Lit(string operation, bool on, string monitor) =>
        ExternalJson.Success(operation, ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteBoolean("active", on);
            writer.WriteBoolean("changed", true);
            writer.WriteString("monitor", monitor);
            writer.WriteBoolean("screenOff", !on);
            writer.WriteString("authority", "windows_sc_monitorpower_request");
            writer.WriteBoolean("effectReadBack", false);
            // INT36B (BAN2 b2p-06 «Windows la apagó porque está en modo inactividad», 3 of 10; b2p-13 «Ya apagaste la
            // pantalla de la izquierda», 7 of 10; the 1.5.2 0 and 0): «Windows was asked …, as when idle» said neither
            // who asked nor that it was now, and the model told an idle timer as the cause or gave the act to the
            // person. It says BAXY asked it, now; how Windows does it stays in WindowsMonitorPlatform.
            writer.WriteString("next", on
                ? "BAXY asked Windows to turn the screen on again; a key or a mouse move turns it on too"
                : "BAXY asked Windows to turn this screen off now; BAXY cannot see whether it did; nothing closed; a key "
                    + "or a mouse move turns it on again");
            writer.WriteEndObject();
        }));

    private ExternalCapabilityReceipt Refused(
        string operation,
        string errorCode,
        IReadOnlyList<MonitorState> monitors,
        string? alone = null) =>
        ExternalJson.FailureBeforeEffect(operation, errorCode) with
        {
            Result = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteBoolean("changed", false);
                WriteMonitors(writer, monitors);
                writer.WriteString("next", errorCode switch
                {
                    OnlyMonitor => "nothing changed: it is the only monitor on, and turning it off would leave no screen",
                    // PAN7 (b): posting the display off would put this PC on standby; nothing was done.
                    WouldSleep => "nothing changed: on this PC turning the display off puts the whole PC on standby and "
                        + "BAXY would stop hearing, and BAXY could not cover the screen with black instead; the brightness "
                        + "can be lowered instead",
                    Ambiguous => "nothing changed: more than one monitor fits; ask the person which one",
                    // PAN4: with one monitor on there is no other to choose; «which one» would ask for one that is not there.
                    // INT36B (BAN2 b2p-13, «apaga las dos pantallas»: the left one off, then «right» refused here, and
                    // «la de la derecha ya no está activa / ya no se ve», 8 of 10, the 1.5.2 0): «this is the only
                    // monitor on and what was said names no other» did not say which one it is nor that it stays on.
                    NotFound when alone is not null =>
                        $"nothing changed: {alone}, the only monitor on, is still on; what was said names no other "
                        + "monitor; ask the person what they meant",
                    _ => "nothing changed: no monitor fits what was said; these are the monitors: ask the person which one",
                });
                writer.WriteEndObject();
            }),
        };

    // A place asked for that is not the one the monitor had when this adapter turned it off.
    private bool Contradicts(MonitorState monitor, string which) =>
        which is not ("primary" or "secondary")
        && _takenOff.TryGetValue(monitor.Key, out var kept)
        && kept.Position.Length > 0
        && kept.Position != which;

    // primary / secondary by the primary flag; a position by where the monitor sits among the ones on.
    private bool Is(MonitorState monitor, string which, IReadOnlyList<MonitorState> on) => which switch
    {
        "primary" => monitor.Primary,
        "secondary" => !monitor.Primary,
        _ => (monitor.Active
            ? Position(monitor, on)
            : _takenOff.TryGetValue(monitor.Key, out var kept) ? kept.Position : string.Empty) == which,
    };

    /// <summary>
    /// Where a monitor that is on sits among the ones on, by their desktop rectangles: above when every other one lies
    /// wholly below it, below the reverse (a row of monitors with one under it); otherwise left or right when its center
    /// is the one furthest that way across; middle otherwise (one of three in a row); «only» when it is the one monitor on.
    /// </summary>
    internal static string Position(MonitorState monitor, IReadOnlyList<MonitorState> on)
    {
        if (on.Count <= 1)
        {
            return "only";
        }

        MonitorState[] others = on.Where(other => other.Key != monitor.Key).ToArray();
        if (others.All(other => other.Y >= monitor.Y + monitor.Height))
        {
            return "above";
        }

        if (others.All(other => other.Y + other.Height <= monitor.Y))
        {
            return "below";
        }

        static double Center(MonitorState state) => state.X + (state.Width / 2.0);
        double center = Center(monitor);
        if (others.All(other => Center(other) > center))
        {
            return "left";
        }

        return others.All(other => Center(other) < center) ? "right" : "middle";
    }

    private static bool Holds(MonitorState monitor, (int X, int Y, int Width, int Height) window)
    {
        int centerX = window.X + (window.Width / 2), centerY = window.Y + (window.Height / 2);
        return centerX >= monitor.X && centerX < monitor.X + monitor.Width
            && centerY >= monitor.Y && centerY < monitor.Y + monitor.Height;
    }

    private void WriteMonitors(Utf8JsonWriter writer, IReadOnlyList<MonitorState> monitors)
    {
        MonitorState[] on = monitors.Where(static monitor => monitor.Active).ToArray();
        writer.WriteStartArray("monitors");
        foreach (MonitorState monitor in monitors)
        {
            writer.WriteStartObject();
            writer.WriteString("name", monitor.Name);
            writer.WriteBoolean("active", monitor.Active);
            if (monitor.Active)
            {
                writer.WriteBoolean("primary", monitor.Primary);
                writer.WriteString("position", Position(monitor, on));
                writer.WriteNumber("width", monitor.Width);
                writer.WriteNumber("height", monitor.Height);
                writer.WriteNumber("refreshHz", monitor.RefreshHz);
            }
            else if (_takenOff.TryGetValue(monitor.Key, out var kept) && kept.Position.Length > 0)
            {
                writer.WriteString("wasPosition", kept.Position);
            }

            writer.WriteEndObject();
        }

        writer.WriteEndArray();
    }
}
