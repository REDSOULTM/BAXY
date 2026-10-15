using System.Runtime.InteropServices;
using Baxy.Providers.Windows.External;

namespace Baxy.Providers.Windows.Windows;

/// <summary>What is known of the person's input into a window since a moment.</summary>
public enum PersonInputVerdict
{
    /// <summary>Watched the whole time and none of the person's input reached the window.</summary>
    Untouched,

    /// <summary>A key or a click of the person (any input without BAXY's mark, injected or not) reached the window.</summary>
    Touched,

    /// <summary>The input was not watched the whole time (fail-closed: treat as touched).</summary>
    Unknown,
}

/// <summary>
/// v3 r22 revisión 2 (bloqueante: BAXY abre el navegador por la mañana y la persona rellena un formulario en esa misma
/// ventana por la tarde; «cierra el navegador» lo cerraba sin preguntar): whether the person's input (a key while the
/// window was in the foreground, a click on it; anything without BAXY's mark, injected or not) reached a window.
/// </summary>
public interface IPersonInputWitness
{
    /// <summary>Starts watching, if it can, before something is launched. Idempotent.</summary>
    void EnsureWatching();

    /// <summary>What reached the window (by its top-level handle) since a UTC moment.</summary>
    PersonInputVerdict ReachedSince(long windowHandle, long sinceUtcTicks);
}

/// <summary>
/// The record behind a witness: the last moment the person's input reached each top-level window, bounded.
/// Whatever it cannot vouch for is Unknown: watching started after the moment asked about, the watch is no longer
/// live (<paramref name="live"/>), or the window's record was dropped to keep the bound.
/// </summary>
public sealed class PersonInputLedger(Func<bool> start, Func<bool> live, Func<long> utcNowTicks) : IPersonInputWitness
{
    private const int MaximumWindows = 512;

    // A process creation time is stamped by a clock that may read up to one tick (15.6 ms) behind; input that close
    // before the moment asked about still counts.
    private static readonly long ClockGranularityTicks = TimeSpan.FromMilliseconds(16).Ticks;

    private readonly object _gate = new();
    private readonly Dictionary<long, long> _lastInput = [];
    private long _watchingSince;
    private long _droppedUpTo;

    public void EnsureWatching()
    {
        lock (_gate)
        {
            if (_watchingSince > 0)
            {
                return;
            }
        }

        long before = utcNowTicks();
        if (!start())
        {
            return;
        }

        lock (_gate)
        {
            if (_watchingSince == 0)
            {
                _watchingSince = Math.Max(1, before);
            }
        }
    }

    /// <summary>The person's input reached these top-level windows (zero handles are ignored).</summary>
    public void Record(long rootWindow, long rootOwnerWindow)
    {
        long now = utcNowTicks();
        lock (_gate)
        {
            Remember(rootWindow, now);
            Remember(rootOwnerWindow, now);
        }
    }

    public PersonInputVerdict ReachedSince(long windowHandle, long sinceUtcTicks)
    {
        long since = Math.Max(1, sinceUtcTicks - ClockGranularityTicks);

        // Asked first: telling whether the watch is live may record input it had missed (v3 r22 revisión 3).
        bool isLive = live();
        lock (_gate)
        {
            if (_watchingSince == 0 || _watchingSince > since)
            {
                return PersonInputVerdict.Unknown;
            }

            if (_lastInput.TryGetValue(windowHandle, out long last) && last >= since)
            {
                return PersonInputVerdict.Touched;
            }

            if (_droppedUpTo >= since)
            {
                return PersonInputVerdict.Unknown;
            }
        }

        return isLive ? PersonInputVerdict.Untouched : PersonInputVerdict.Unknown;
    }

    private void Remember(long window, long now)
    {
        if (window == 0)
        {
            return;
        }

        if (!_lastInput.ContainsKey(window) && _lastInput.Count >= MaximumWindows)
        {
            KeyValuePair<long, long> oldest = _lastInput.MinBy(static pair => pair.Value);
            _lastInput.Remove(oldest.Key);
            _droppedUpTo = Math.Max(_droppedUpTo, oldest.Value);
        }

        _lastInput[window] = now;
    }
}

/// <summary>
/// The Windows witness, fed by the Core's passive Raw Input detector (<see cref="WindowsUserInputPause"/>): nothing of
/// BAXY sits in the input path (v3 r22 revisión 3, bloqueante 2: low-level hooks made every key and move of the person,
/// in any application, wait on the Core). Every input without BAXY's mark (<see cref="BaxyInputMark"/>) is the
/// person's, injected or not (revisión 3, bloqueante 1: Synergy, Deskflow, remote desktops, on-screen keyboards, Voice
/// Access and the live harness's simulated user inject without it): a key goes to the foreground window, a button or
/// a wheel turn to the top-level window under the pointer, and input Raw Input never delivers (VK_PACKET typing) that
/// the detector's self-check finds goes to the window in front then. Each is recorded with its root owner (a dialog the
/// window owns counts as the window). The watch counts as live only while the detector runs and has seen, or reconciled,
/// the system's last input (GetLastInputInfo); otherwise the verdict is Unknown.
/// </summary>
public static partial class WindowsPersonInputWitness
{
    private const uint GaRoot = 2;
    private const uint GaRootOwner = 3;

    /// <summary>The witness the Core shares.</summary>
    public static PersonInputLedger Shared { get; } =
        new(Install, Live, static () => DateTime.UtcNow.Ticks);

    /// <summary>The person's input (never BAXY's) reached this window: its root and root owner are recorded.</summary>
    internal static void NoteReached(nint window)
    {
        if (window == 0)
        {
            return;
        }

        try
        {
            Shared.Record(GetAncestor(window, GaRoot), GetAncestor(window, GaRootOwner));
        }
        catch (Exception exception) when (exception is InvalidOperationException or ArgumentException)
        {
            // Never let the detector's thread fail; the read stays fail-closed through Live().
        }
    }

    private static bool Install() => WindowsUserInputPause.Shared.TellsOwnInput;

    private static bool Live()
    {
        WindowsUserInputPause pause = WindowsUserInputPause.Shared;
        if (!pause.TellsOwnInput)
        {
            return false;
        }

        // Reconciled first: input the detector missed (it is the person's) is recorded on the window in front; input
        // still too recent to tell keeps the read Unknown.
        _ = pause.LastForeignInputMs;
        return pause.UnexplainedInputMs == 0;
    }

    [LibraryImport("user32.dll")]
    private static partial nint GetAncestor(nint window, uint flags);
}
