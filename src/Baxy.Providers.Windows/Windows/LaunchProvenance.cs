using System.Diagnostics;

namespace Baxy.Providers.Windows.Windows;

/// <summary>
/// The processes a verified app.open of BAXY launched in this session (alreadyRunning false), by process id and
/// creation time so a recycled id never inherits them, with the window the opening verified (a packaged application
/// draws inside a shared frame whose process is not the one launched): the reads that tell which windows are open say
/// whether BAXY launched each one (F002). Only a process created after the opening began is noted (AppOpenHandler),
/// never one the person already had. The record lives as long as the Core process; nothing is persisted.
/// </summary>
public sealed class LaunchProvenance
{
    private const int MaximumEntries = 64;

    private readonly object _gate = new();
    private readonly List<Entry> _entries = [];
    private readonly Func<int, long?> _processCreationTicks;
    private bool _forgotten;

    public LaunchProvenance()
        : this(ReadProcessCreationTicks)
    {
    }

    /// <param name="processCreationTicks">The UTC creation ticks of a live process, or null when it is gone.</param>
    public LaunchProvenance(Func<int, long?> processCreationTicks)
    {
        _processCreationTicks = processCreationTicks ?? throw new ArgumentNullException(nameof(processCreationTicks));
    }

    /// <summary>The record the Core's handlers share.</summary>
    public static LaunchProvenance Shared { get; } = new();

    /// <summary>
    /// Notes a process a verified app.open launched (never one that was already running) and the window the opening
    /// verified. Invalid identities are ignored.
    /// </summary>
    public void NoteLaunched(int processId, long processCreationTimeUtcTicks, long windowHandle)
    {
        if (processId <= 0 || processCreationTimeUtcTicks <= 0)
        {
            return;
        }

        lock (_gate)
        {
            _entries.RemoveAll(entry => entry.ProcessId == processId);
            if (_entries.Count >= MaximumEntries)
            {
                _entries.RemoveAt(0);
                _forgotten = true;
            }

            _entries.Add(new Entry(processId, processCreationTimeUtcTicks, Math.Max(0, windowHandle)));
        }
    }

    /// <summary>
    /// BAXY Renew al máximo, F002 («¿abriste Spotify?» con un Spotify que la persona ya tenía abierto → «Sí, Spotify
    /// tiene una ventana abierta», 9 de 9 corridas): whether a window (its handle, process id and process creation
    /// time) is of what a verified opening of BAXY launched in this run. Its process is a launched one (id and creation
    /// time), or it is the very window an opening verified while the launched process is still the one launched (a
    /// frame drawn by another process). Null when that cannot be told: the window's process creation time is unknown,
    /// or a launch was forgotten to keep the record bounded.
    /// </summary>
    public bool? Launched(long windowHandle, int processId, long processCreationTimeUtcTicks)
    {
        Entry[] entries;
        bool forgotten;
        lock (_gate)
        {
            entries = [.. _entries];
            forgotten = _forgotten;
        }

        if (windowHandle > 0
            && entries.LastOrDefault(entry => entry.WindowHandle == windowHandle) is { } verified
            && ((verified.ProcessId == processId && verified.CreationTicks == processCreationTimeUtcTicks)
                || _processCreationTicks(verified.ProcessId) == verified.CreationTicks))
        {
            return true;
        }

        if (entries.Any(entry => entry.ProcessId == processId && entry.CreationTicks == processCreationTimeUtcTicks))
        {
            return true;
        }

        return processId <= 0 || processCreationTimeUtcTicks <= 0 || forgotten ? null : false;
    }

    private static long? ReadProcessCreationTicks(int processId)
    {
        try
        {
            using Process process = Process.GetProcessById(processId);
            return process.HasExited ? null : process.StartTime.ToUniversalTime().Ticks;
        }
        catch (Exception exception) when (exception is ArgumentException
            or InvalidOperationException or System.ComponentModel.Win32Exception or NotSupportedException)
        {
            return null;
        }
    }

    private sealed record Entry(int ProcessId, long CreationTicks, long WindowHandle);
}
