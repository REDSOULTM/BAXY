using System.ComponentModel;
using System.Diagnostics;

namespace Baxy.Providers.Windows.Applications;

/// <summary>
/// Estabilización, encargo C: hands the address of an application's place (composed by
/// <see cref="Baxy.Kernel.Operations.ApplicationPlaces"/> from its data, never here) to Windows, which gives it to the
/// handler the application registered for its protocol (the shell's own launch of a URL, as SteamLocalAdapter and the
/// harness do; measured 2026-10-11 on redpc: through explorer.exe an address with a query, «…/search/?term=Cuphead», was
/// dropped, and the shell's launch opened it). Whether the window arrived is read on the window by the mission's check,
/// never assumed from this hand-over. Review H2: the protocol's handler raises the application's window by itself
/// (measured: Steam and Spotify took the front after every address); unless the front was asked for, it goes back to
/// the window that had it, and the receipt says the front changed and whether it is back.
/// </summary>
public interface IApplicationPlaceOpener
{
    PlaceOpening Open(string address, bool keepFront, long applicationWindow);
}

/// <summary>The hand-over: whether Windows took the address, the front moved, and the front is back.</summary>
public sealed record PlaceOpening(bool Opened, bool FrontChanged = false, bool FrontRestored = false);

public sealed class ShellApplicationPlaceOpener : IApplicationPlaceOpener
{
    // The handler raises the window a moment after the hand-over; a front still unmoved past this is left alone.
    internal static readonly TimeSpan FrontWatch = TimeSpan.FromMilliseconds(1200);

    public PlaceOpening Open(string address, bool keepFront, long applicationWindow)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(address);
        long before = ForegroundHandBack.Foreground();
        try
        {
            // A protocol's handler usually hands the address to the running application and leaves: there may be no
            // process to keep, and none is waited for.
            using Process? process = Process.Start(new ProcessStartInfo(address) { UseShellExecute = true });
        }
        catch (Win32Exception)
        {
            return new PlaceOpening(false);
        }

        // The application's own window already in front (or the front asked for) is nobody else's to hand back.
        if (keepFront || before == 0 || before == applicationWindow)
        {
            return new PlaceOpening(true);
        }

        var watch = Stopwatch.StartNew();
        while (watch.Elapsed < FrontWatch)
        {
            long now = ForegroundHandBack.Foreground();
            if (now != 0 && now != before)
            {
                // Under the front's gate, as every hand-back of an opening, so it never undoes a burst of the lease.
                bool gated = ForegroundHandBack.FrontGate.Wait(FrontWatch);
                try
                {
                    return new PlaceOpening(true, FrontChanged: true, FrontRestored: gated && ForegroundHandBack.Return(before, now));
                }
                finally
                {
                    if (gated)
                    {
                        ForegroundHandBack.FrontGate.Release();
                    }
                }
            }

            Thread.Sleep(40);
        }

        return new PlaceOpening(true);
    }
}
