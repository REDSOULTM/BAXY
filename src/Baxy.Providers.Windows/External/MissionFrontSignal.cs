using System.IO.MemoryMappedFiles;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// What the App tells the Core of a computer-use mission (the owner's decision of 2026-10-10, «no molestar» in its simple
/// form): that one is running, and when it ends. The Core takes the mission's window to the front before each act
/// (<see cref="IForegroundLease.TakeForMissionAsync"/>) and gives the person's window the front back itself once the
/// mission ended, behind the act it may still be doing (the Core answers one request at a time and a cancelled turn
/// cannot stop it); an act of a mission that already ended is never sent.
/// </summary>
public interface IMissionFrontSignal
{
    /// <summary>A mission runs (idempotent while one already runs).</summary>
    void MissionBegins();

    /// <summary>The mission ended: reached, failed, out of time, waiting for a confirmation, cancelled or thrown.</summary>
    void MissionEnds();
}

/// <summary>The Core's read of the signal: the mission's generation and whether it runs.</summary>
internal interface IMissionRunning
{
    /// <summary>
    /// The generation of the last mission begun and whether it still runs; generation 0 when no App ever said anything
    /// (a Core driven without the App counts as running).
    /// </summary>
    (long Generation, bool Running) Read();
}

/// <summary>
/// The signal in a small shared block of the session (a generation and a running flag, nothing of the person's), as
/// <see cref="LeaseFrontSignal"/> tells the UIA worker which front the lease takes.
/// </summary>
public sealed class WindowsMissionFrontSignal : IMissionFrontSignal, IMissionRunning
{
    internal const string Name = @"Local\BaxyMissionFront";

    private readonly Lock _gate = new();
    private MemoryMappedViewAccessor? _view;
    private MemoryMappedFile? _block;

    private WindowsMissionFrontSignal()
    {
    }

    public static WindowsMissionFrontSignal Instance { get; } = new();

    public void MissionBegins() => Write(begin: true);

    public void MissionEnds() => Write(begin: false);

    public (long Generation, bool Running) Read()
    {
        lock (_gate)
        {
            if (View() is not { } view)
                return (0, true);
            long generation = view.ReadInt64(0);
            return (generation, generation == 0 || view.ReadInt64(8) != 0);
        }
    }

    private void Write(bool begin)
    {
        lock (_gate)
        {
            if (View() is not { } view)
                return;
            bool running = view.ReadInt64(0) != 0 && view.ReadInt64(8) != 0;
            if (begin && !running)
                view.Write(0, view.ReadInt64(0) + 1);
            view.Write(8, begin ? 1L : 0L);
        }
    }

    // Opened once and kept open for the process's life: the block lives while one of the two holds it.
    private MemoryMappedViewAccessor? View()
    {
        try
        {
            if (_view is null)
            {
                _block = MemoryMappedFile.CreateOrOpen(Name, 16);
                _view = _block.CreateViewAccessor(0, 16);
            }

            return _view;
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            return null;
        }
    }
}
