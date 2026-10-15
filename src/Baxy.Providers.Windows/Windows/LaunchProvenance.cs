using System.Diagnostics;

namespace Baxy.Providers.Windows.Windows;

/// <summary>
/// v3 r22 uso real (t3-c18 «ya ciérrala» sobre la Calculadora que BAXY había abierto en esa conversación y en la que
/// sólo hizo clics → pidió confirmación): the processes a verified app.open of BAXY launched in this session
/// (alreadyRunning false), by process id and creation time so a recycled id never inherits them, with the window the
/// opening verified (a packaged application draws inside a shared frame whose process is not the one launched).
/// That window (and only that window, never another window of the same process) holds nothing of the person while
/// BAXY has not written into any window since the launch: any operation that may write (typing, keys, pasting,
/// dragging, a click that types its search, and anything not known to only point or read) marks every launched
/// process as written, because which window it reached is not always known (fail-closed). Only a process created
/// after the opening began is noted (AppOpenHandler), never one the person already had.
/// The record lives as long as the Core process; nothing is persisted.
/// v3 r22 revisión 2 (bloqueante: BAXY abre el navegador por la mañana, ventana 777, y por la tarde la persona rellena
/// un formulario en esa misma ventana; «cierra el navegador» lo cerraba sin preguntar): the person's own
/// input reaching the window since the launch (<see cref="IPersonInputWitness"/>) makes it theirs too, and when that
/// input cannot be read the window keeps asking (fail-closed).
/// </summary>
public sealed class LaunchProvenance
{
    private const int MaximumEntries = 64;

    private readonly object _gate = new();
    private readonly List<Entry> _entries = [];
    private readonly Func<int, long?> _processCreationTicks;
    private readonly IPersonInputWitness _personInput;

    public LaunchProvenance()
        : this(ReadProcessCreationTicks, WindowsPersonInputWitness.Shared)
    {
    }

    /// <param name="processCreationTicks">The UTC creation ticks of a live process, or null when it is gone.</param>
    /// <param name="personInput">What of the person's input (anything without BAXY's mark) reached a window.</param>
    public LaunchProvenance(Func<int, long?> processCreationTicks, IPersonInputWitness personInput)
    {
        _processCreationTicks = processCreationTicks ?? throw new ArgumentNullException(nameof(processCreationTicks));
        _personInput = personInput ?? throw new ArgumentNullException(nameof(personInput));
    }

    /// <summary>
    /// Called before an opening launches anything, so the person's input into what it launches is watched from the
    /// start (a watch that began after the launch cannot vouch for it and the window keeps asking).
    /// </summary>
    public void PrepareLaunch() => _personInput.EnsureWatching();

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
            }

            _entries.Add(new Entry(processId, processCreationTimeUtcTicks, Math.Max(0, windowHandle)));
        }
    }

    /// <summary>
    /// An operation that may have written into a window ran: every process launched so far counts as written.
    /// </summary>
    public void NoteWritten()
    {
        lock (_gate)
        {
            for (int index = 0; index < _entries.Count; index++)
            {
                _entries[index] = _entries[index] with { Written = true };
            }
        }
    }

    /// <summary>
    /// Whether a window (its handle, process id and process creation time) is the very window a verified opening of
    /// BAXY launched in this session, and BAXY never wrote into any window since. Only that window counts: another
    /// window of the same process (one the person opened with Ctrl+N and filled) may hold their work and keeps asking.
    /// The window's process must be the launched one (id and creation time), or, for a frame drawn by another process
    /// (a packaged application), the launched process must still be alive with the same creation time.
    /// v3 r22 revisión (sonda: la ventana 888 de un proceso anotado con la ventana 777 salía sin escribir).
    /// </summary>
    public bool LaunchedAndUnwritten(long windowHandle, int processId, long processCreationTimeUtcTicks)
    {
        if (windowHandle <= 0)
        {
            return false;
        }

        Entry? found;
        lock (_gate)
        {
            found = _entries.LastOrDefault(entry => entry.WindowHandle != 0 && entry.WindowHandle == windowHandle);
        }

        if (found is null || found.Written)
        {
            return false;
        }

        bool launched = (found.ProcessId == processId && found.CreationTicks == processCreationTimeUtcTicks)

            // The window is a frame of another process: it is the launched application's only while that process is
            // still the one launched.
            || _processCreationTicks(found.ProcessId) == found.CreationTicks;

        // v3 r22 revisión 2: a key or a click of the person (without BAXY's mark, injected or not) in that window since
        // the launch may have put their work there; not being able to tell keeps it asking.
        return launched
            && _personInput.ReachedSince(windowHandle, found.CreationTicks) == PersonInputVerdict.Untouched;
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

    private sealed record Entry(int ProcessId, long CreationTicks, long WindowHandle, bool Written = false);
}
