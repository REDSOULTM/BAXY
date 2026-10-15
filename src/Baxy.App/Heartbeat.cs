using System.IO;
using System.Net.NetworkInformation;
using System.Text.Json.Nodes;

namespace Baxy.App;

/// <summary>
/// BAXY's heartbeat (owner, 2026-10-15; OpenClaw's heartbeat): every five minutes and when something changes (an
/// application opens, a download finishes, the network drops or comes back, the battery runs low, the person leaves),
/// the moment goes to the model, which decides by instinct. The five-minute look pauses while the person plays or the
/// GPU is busy; a change still wakes it. <c>BAXY_RENEW_HEARTBEAT=0</c> turns it off.
/// </summary>
internal sealed class Heartbeat : IAsyncDisposable
{
    private static readonly TimeSpan Watch = TimeSpan.FromSeconds(15);
    private static readonly TimeSpan Tick = TimeSpan.FromMinutes(5);

    private readonly Func<JsonObject, bool, Task> _beat;
    private readonly Func<bool> _canBeat;
    private readonly Func<IReadOnlyList<ConversationMessage>> _recent;
    private readonly CancellationTokenSource _lifetime = new();
    private readonly List<string> _events = [];
    private readonly object _gate = new();
    private readonly FileSystemWatcher? _downloads;
    private HashSet<string> _windows = [];
    private bool? _network;
    private int? _battery;
    private bool _away;
    private DateTimeOffset _lastBeat = DateTimeOffset.UtcNow;
    private Task _loop = Task.CompletedTask;

    /// <param name="beat">Runs one heartbeat with the moment; the flag says whether its words may be spoken.</param>
    /// <param name="canBeat">Whether a heartbeat may run now (the mind is ready and nothing else holds the turn).</param>
    internal Heartbeat(
        Func<JsonObject, bool, Task> beat,
        Func<bool> canBeat,
        Func<IReadOnlyList<ConversationMessage>> recent)
    {
        _beat = beat;
        _canBeat = canBeat;
        _recent = recent;
        string downloads = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), "Downloads");
        if (Directory.Exists(downloads))
        {
            _downloads = new FileSystemWatcher(downloads) { IncludeSubdirectories = false, EnableRaisingEvents = false };
            _downloads.Created += (_, e) => DownloadSeen(e.Name);
            _downloads.Renamed += (_, e) => DownloadSeen(e.Name);
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

            NoteChanges();
            bool changed;
            lock (_gate)
            {
                changed = _events.Count > 0;
            }

            bool due = DateTimeOffset.UtcNow - _lastBeat >= Tick;
            if ((!changed && !due) || !_canBeat())
            {
                continue;
            }

            string activity = HeartbeatMoment.Activity(out _, out bool gpuBusy);
            if (!changed && (activity == HeartbeatMoment.Playing || gpuBusy))
            {
                // The five-minute look pauses while the person plays or the GPU is busy; a change still wakes it.
                _lastBeat = DateTimeOffset.UtcNow;
                continue;
            }

            string[] events;
            lock (_gate)
            {
                events = changed ? [.. _events] : ["tick: 5 min"];
                _events.Clear();
            }

            _lastBeat = DateTimeOffset.UtcNow;
            JsonObject moment = HeartbeatMoment.Observe(events, _recent());
            try
            {
                await _beat(moment, HeartbeatMoment.Speaks((string?)moment["owner_activity"] ?? string.Empty))
                    .ConfigureAwait(false);
            }
            catch (Exception exception) when (exception is not OperationCanceledException)
            {
                ShellTraceSink.Record(ShellTraceScopes.Turn, "beat", "beat.failed", exception.GetType().Name);
            }
        }
    }

    // What changed since the last look, as the lines the model reads («app opened: …», «network down» …).
    private void NoteChanges()
    {
        HashSet<string> windows = CurrentApplications();
        foreach (string opened in windows.Except(_windows))
        {
            Note($"app opened: {opened}");
        }

        _windows = windows;
        bool network = NetworkInterface.GetIsNetworkAvailable();
        if (_network is { } before && before != network)
        {
            Note(network ? "network back" : "network down");
        }

        _network = network;
        JsonObject pc = HeartbeatMoment.Machine(gpuBusy: false);
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

        bool away = (int?)pc["idle_min"] >= 10;
        if (away && !_away)
        {
            Note($"user idle: {(int?)pc["idle_min"]} min");
        }

        _away = away;
    }

    private void DownloadSeen(string? name)
    {
        if (string.IsNullOrWhiteSpace(name)
            || name.EndsWith(".crdownload", StringComparison.OrdinalIgnoreCase)
            || name.EndsWith(".part", StringComparison.OrdinalIgnoreCase)
            || name.EndsWith(".tmp", StringComparison.OrdinalIgnoreCase)
            || name.StartsWith('.'))
        {
            return;
        }

        Note($"download finished: {name} en Descargas");
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
