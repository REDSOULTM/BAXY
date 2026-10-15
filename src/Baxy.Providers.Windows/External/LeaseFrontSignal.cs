using System.IO.MemoryMappedFiles;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// The foreground lease says, in a small shared block of the session, which window it is bringing to the front and
/// when (its handle and <see cref="Environment.TickCount64"/>). The UIA worker's front net reads it before it gives a
/// front back: a front BAXY's own lease took on purpose (the pointer, the wheel or the keyboard after a pattern that
/// did not act) is not a theft, and fighting it would make the lease's input fall in the person's window (review of
/// 1b9b736e7). Only a handle and a time are written; nothing of the person's.
/// </summary>
internal static class LeaseFrontSignal
{
    /// <summary>The block's name; the worker opens the same one (BaxyFrontKeeper.LeaseBlock).</summary>
    internal const string Name = @"Local\BaxyLeaseFront";

    private static readonly Lock Gate = new();
    private static MemoryMappedFile? _block;
    private static MemoryMappedViewAccessor? _view;

    /// <summary>The lease is about to bring <paramref name="window"/> to the front.</summary>
    internal static void Mark(nint window)
    {
        try
        {
            lock (Gate)
            {
                if (_view is null)
                {
                    _block = MemoryMappedFile.CreateOrOpen(Name, 16);
                    _view = _block.CreateViewAccessor(0, 16);
                }

                _view.Write(8, Environment.TickCount64);
                _view.Write(0, (long)window);
            }
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            // Without the block the net cannot tell the lease's front apart; the lease's own guard still holds.
        }
    }
}
