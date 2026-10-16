using System.IO;
using System.Text.Json.Nodes;
using Baxy.Providers.Windows.Network;

namespace Baxy.App;

/// <summary>
/// BAXY's heartbeat (owner, 2026-10-15; OpenClaw's heartbeat): every five minutes and when something changes (an
/// application opens, a file appears in Downloads, Windows' internet check changes, the battery runs low, the person
/// leaves or comes back), the moment goes to the model, which decides by instinct. The five-minute look pauses while the person plays or the
/// GPU is busy; a change still wakes it. <c>BAXY_RENEW_HEARTBEAT=0</c> turns it off.
/// </summary>
internal sealed class Heartbeat : IAsyncDisposable
{
    private static readonly TimeSpan Watch = TimeSpan.FromSeconds(15);
    private static readonly TimeSpan Tick = TimeSpan.FromMinutes(5);

    private readonly Func<JsonObject, bool, Task> _beat;
    private readonly Func<bool> _canBeat;
    private readonly Func<IReadOnlyList<ConversationMessage>> _recent;
    private readonly Func<Task<IReadOnlyList<string>>> _remembered;
    private readonly Func<Task<JsonArray>> _reminders;
    private readonly CancellationTokenSource _lifetime = new();
    private readonly List<string> _events = [];
    private readonly object _gate = new();
    private readonly FileSystemWatcher? _downloads;
    private readonly WindowsNetworkStatusProvider _network = new();
    private HashSet<string> _windows = [];
    private string? _connectivity;
    private int? _battery;
    private readonly AwayWatch _awayWatch = new();
    private DateTimeOffset _lastBeat = DateTimeOffset.UtcNow;
    private Task _loop = Task.CompletedTask;

    /// <param name="beat">Runs one heartbeat with the moment; the flag says whether its words may be spoken.</param>
    /// <param name="canBeat">Whether a heartbeat may run now (the mind is ready and nothing else holds the turn).</param>
    /// <param name="remembered">What BAXY remembers of the person, read when a heartbeat runs.</param>
    internal Heartbeat(
        Func<JsonObject, bool, Task> beat,
        Func<bool> canBeat,
        Func<IReadOnlyList<ConversationMessage>> recent,
        Func<Task<IReadOnlyList<string>>> remembered,
        Func<Task<JsonArray>> reminders)
    {
        _reminders = reminders;
        _beat = beat;
        _canBeat = canBeat;
        _recent = recent;
        _remembered = remembered;
        string downloads = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), "Downloads");
        if (Directory.Exists(downloads))
        {
            _downloads = new FileSystemWatcher(downloads) { IncludeSubdirectories = false, EnableRaisingEvents = false };
            _downloads.Created += (_, e) => FileAppeared(e.Name);
            _downloads.Renamed += (_, e) => FileAppeared(e.Name);
        }
    }

    internal static bool Enabled =>
        !string.Equals(Environment.GetEnvironmentVariable("BAXY_RENEW_HEARTBEAT"), "0", StringComparison.Ordinal);

    internal void Start()
    {
        _windows = CurrentApplications();
        if (_downloads is not null)
        {
            _downloads.EnableRaisingEvents = true;
        }

        // Off the interface thread: observing the moment reads the GPU and the windows.
        _loop = Task.Run(() => RunAsync(_lifetime.Token));
    }

    private async Task RunAsync(CancellationToken cancellationToken)
    {
        while (!cancellationToken.IsCancellationRequested)
        {
            try
            {
                await Task.Delay(Watch, cancellationToken).ConfigureAwait(false);
            }
            catch (OperationCanceledException)
            {
                return;
            }

            // One look that fails (a network or window read, the memory or the reminders, the beat itself) is traced
            // and the next one comes as usual: it ended the heartbeat for the rest of the session (audit 2026-10-15,
            // App 4).
            try
            {
                await LookAsync(cancellationToken).ConfigureAwait(false);
            }
            catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
            {
                return;
            }
            catch (Exception exception)
            {
                // An inner deadline's cancellation included: only the heartbeat's own end stops it.
                ShellTraceSink.Record(ShellTraceScopes.Turn, "beat", "beat.failed", exception.GetType().Name);
            }
        }
    }

    private async Task LookAsync(CancellationToken cancellationToken)
    {
        await NoteChangesAsync(cancellationToken).ConfigureAwait(false);
        bool changed;
        lock (_gate)
        {
            changed = _events.Count > 0;
        }

        bool due = DateTimeOffset.UtcNow - _lastBeat >= Tick;
        if ((!changed && !due) || !_canBeat())
        {
            return;
        }

        string activity = HeartbeatMoment.Activity(out _, out bool gpuBusy);
        if (!changed && (activity == HeartbeatMoment.Playing || gpuBusy))
        {
            // The five-minute look pauses while the person plays or the GPU is busy; a change still wakes it.
            _lastBeat = DateTimeOffset.UtcNow;
            return;
        }

        string[] events;
        lock (_gate)
        {
            events = changed ? [.. _events] : ["tick: 5 min"];
            _events.Clear();
        }

        _lastBeat = DateTimeOffset.UtcNow;
        JsonObject moment;
        try
        {
            moment = HeartbeatMoment.Observe(events, _recent(), _connectivity);
            moment["memory"] = new JsonArray((await _remembered().ConfigureAwait(false))
                .Select(static line => (JsonNode?)JsonValue.Create(line)).ToArray());
            moment["reminders"] = await _reminders().ConfigureAwait(false);
        }
        catch when (changed)
        {
            // The moment could not be made: what changed waits for the next look instead of being lost.
            lock (_gate)
            {
                _events.InsertRange(0, events);
            }

            throw;
        }

        await _beat(moment, HeartbeatMoment.Speaks((string?)moment["owner_activity"] ?? string.Empty))
            .ConfigureAwait(false);
    }

    // What changed since the last look, as the lines the model reads («app opened: …», «internet connectivity: …» …).
    private async Task NoteChangesAsync(CancellationToken cancellationToken)
    {
        HashSet<string> windows = CurrentApplications();
        foreach (string opened in windows.Except(_windows))
        {
            Note($"app opened: {opened}");
        }

        _windows = windows;
        // Windows' own internet check, the signal network.status reads; a reading that changed between its two looks
        // is left for the next one.
        if ((await _network.ReadVerifiedAsync(cancellationToken).ConfigureAwait(false))?.Connectivity is { } connectivity)
        {
            if (_connectivity is { } before && before != connectivity)
            {
                Note($"internet connectivity: {connectivity} (was {before})");
            }

            _connectivity = connectivity;
        }

        JsonObject pc = HeartbeatMoment.Machine(gpuBusy: false, connectivity: null);
        if ((int?)pc["battery_pct"] is { } battery && (bool?)pc["plugged"] != true)
        {
            foreach (int threshold in new[] { 20, 10 })
            {
                if (battery <= threshold && (_battery is null || _battery > threshold))
                {
                    Note($"battery below {threshold}%: {battery}%");
                }
            }

            _battery = battery;
        }

        TimeSpan idle = HeartbeatMoment.IdleTime();
        if (_awayWatch.Look(DateTimeOffset.UtcNow, idle, HeartbeatMoment.Presence(out _) == HeartbeatMoment.Away)
            is { } presence)
        {
            Note(presence);
        }
    }

    private void FileAppeared(string? name)
    {
        if (string.IsNullOrWhiteSpace(name)
            || name.EndsWith(".crdownload", StringComparison.OrdinalIgnoreCase)
            || name.EndsWith(".part", StringComparison.OrdinalIgnoreCase)
            || name.EndsWith(".tmp", StringComparison.OrdinalIgnoreCase)
            || name.StartsWith('.'))
        {
            return;
        }

        Note($"file appeared in Descargas: {name}");
    }

    private void Note(string line)
    {
        lock (_gate)
        {
            if (!_events.Contains(line))
            {
                _events.Add(line);
            }
        }
    }

    // Applications by process: a window's title changes with every page or song, an application opening does not.
    private static HashSet<string> CurrentApplications() =>
        HeartbeatMoment.TopLevelWindows()
            .Select(static window => HeartbeatMoment.ProcessOf(window))
            .OfType<string>()
            .ToHashSet(StringComparer.OrdinalIgnoreCase);

    public async ValueTask DisposeAsync()
    {
        await _lifetime.CancelAsync();
        try
        {
            await _loop.ConfigureAwait(false);
        }
        catch (OperationCanceledException)
        {
        }

        _downloads?.Dispose();
        _lifetime.Dispose();
    }
}
