using System.ComponentModel;
using System.Diagnostics;

namespace Baxy.Providers.Windows.Applications;

/// <summary>
/// Estabilización, encargo C: hands the address of an application's place (composed by
/// <see cref="Baxy.Kernel.Operations.ApplicationPlaces"/> from its data, never here) to Windows, which gives it to the
/// handler the application registered for its protocol (the shell's own launch of a URL, as SteamLocalAdapter and the
/// harness do; measured 2026-10-11 on redpc: through explorer.exe an address with a query, «…/search/?term=Cuphead», was
/// dropped, and the shell's launch opened it). Whether the place arrived is for a look at the window to say, never
/// assumed from this hand-over. Review H2: the protocol's handler raises the application's window by itself
/// (measured: Steam and Spotify took the front after every address); unless the front was asked for, it goes back to
/// the window that had it when the window that took it is the application's, and the receipt says the front changed
/// and whether it is back. A front that went to any other window (the person's own move) is not undone.
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

    // PLAN_GENERAL (uso real 2026-10-21: Epic's search came 1-2 s after its address and the look right after the opening
    // read the page before, so the model pressed «Tienda» over the results): how long a place may take to be drawn, and
    // how often the window is read meanwhile.
    internal static readonly TimeSpan PlaceArrival = TimeSpan.FromSeconds(5);
    private const int ArrivalPollMs = 200;

    public PlaceOpening Open(string address, bool keepFront, long applicationWindow)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(address);
        long before = ForegroundHandBack.Foreground();
        nint window = (nint)applicationWindow;
        External.VisibleControlSurface.CapturedWindow? drawnBefore = window == 0
            ? null
            : External.VisibleControlSurface.CaptureAsync(window, CancellationToken.None, selfDrawn: true)
                .AsTask().GetAwaiter().GetResult();
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

        PlaceOpening opening = HandFront(keepFront, before, applicationWindow);
        AwaitPlaceDrawn(drawnBefore);
        return opening;
    }

    // The application's window, drawn by itself, until its drawing changes from the one before the address and then
    // stays still (VisibleControlSurface.StableSurfaceAsync), within PlaceArrival: what a look reads next is the place,
    // not the page before it. Nothing is said from it: a place that did not change the window is for the look to tell.
    private static void AwaitPlaceDrawn(External.VisibleControlSurface.CapturedWindow? drawnBefore)
    {
        if (drawnBefore is not { } earlier)
            return;
        ValueTask<External.VisibleControlSurface.CapturedWindow?> Capture(nint hwnd, CancellationToken token) =>
            External.VisibleControlSurface.CaptureAsync(hwnd, token, selfDrawn: true);
        var watch = Stopwatch.StartNew();
        while (watch.Elapsed < PlaceArrival)
        {
            Thread.Sleep(ArrivalPollMs);
            if (Capture(earlier.Hwnd, CancellationToken.None).AsTask().GetAwaiter().GetResult() is not { } now)
                return;
            if (!External.VisibleControlSurface.SameSurface(earlier, now))
            {
                _ = External.VisibleControlSurface.StableSurfaceAsync(
                        now, Capture, (ms, token) => Task.Delay(ms, token), CancellationToken.None)
                    .AsTask().GetAwaiter().GetResult();
                return;
            }
        }
    }

    private static PlaceOpening HandFront(bool keepFront, long before, long applicationWindow)
    {
        // The application's own window already in front (or the front asked for) is nobody else's to hand back.
        if (keepFront || before == 0 || before == applicationWindow)
        {
            return new PlaceOpening(true);
        }

        int applicationProcess = applicationWindow == 0 ? 0 : ForegroundHandBack.ProcessOf(applicationWindow);
        var watch = Stopwatch.StartNew();
        while (watch.Elapsed < FrontWatch)
        {
            long now = ForegroundHandBack.Foreground();
            if (now != 0 && now != before)
            {
                // Auditoría final 2 (CU16): only a front the application took is handed back.
                if (applicationProcess == 0 || ForegroundHandBack.ProcessOf(now) != applicationProcess)
                {
                    return new PlaceOpening(true, FrontChanged: true);
                }

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
