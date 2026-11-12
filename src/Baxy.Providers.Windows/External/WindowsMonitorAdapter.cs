using System.ComponentModel;
using System.Text.Json;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// RUT2 (pedido del dueño 10-11-2026: «desactiva la pantalla de la izquierda»): display.status reads every connected
/// monitor from the display topology, on and off, with its desktop position (left, right, above, below or middle of the
/// ones on), whether it is the primary one and its mode; display.monitor.set takes one off the desktop or puts it back,
/// chosen by that position or by being (or not being) the primary one, and reads the topology again. Never the only
/// monitor on; the receipt says when BAXY's own window was on the one taken off (Windows moves it to one that stays).
/// What a monitor looked like when this adapter took it off is kept, and putting it back says whether it came back the
/// same (asBefore). Windows itself restores the layout that set of monitors last had (<see cref="WindowsMonitorPlatform"/>).
/// </summary>
internal sealed class WindowsMonitorAdapter : IExternalOperationAdapter
{
    internal const string OnlyMonitor = "only_active_monitor";
    internal const string NotFound = "monitor_not_found";
    internal const string Ambiguous = "monitor_ambiguous";
    internal const string NotVerified = "monitor_change_not_verified";

    private readonly IMonitorPlatform _platform;
    private readonly Dictionary<string, (MonitorState State, string Position)> _takenOff = new(StringComparer.Ordinal);
    private readonly Lock _gate = new();

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
        if (!active && on.Length <= 1)
        {
            return Refused(operation, OnlyMonitor, monitors);
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
            writer.WriteString("authority", "windows_display_config_postread");
            writer.WriteEndObject();
        }));
    }

    private ExternalCapabilityReceipt Refused(
        string operation,
        string errorCode,
        IReadOnlyList<MonitorState> monitors) =>
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
                    Ambiguous => "nothing changed: more than one monitor fits; ask the person which one",
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
