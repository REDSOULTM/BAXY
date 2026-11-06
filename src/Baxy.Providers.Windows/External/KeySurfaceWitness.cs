namespace Baxy.Providers.Windows.External;

/// <summary>
/// Uso-108 (B2, F29: 43 of 87 bare keys were followed by another look, since nothing said the slide had moved): whether a
/// plain key changed its window's image. Pixels and not the tree: agent-desktop's scripts/jev/run.mjs compares a shallow
/// read of the tree and so reads a slide show as unchanged. A change must be first seen within <see cref="LookMs"/> ×
/// <see cref="Looks"/> ms (not the 1 s of a shortcut: most plain keys change nothing, and every one of those pays the whole
/// wait), and the window must then hold still: <see cref="SettledAfterMs"/> ms after it, and for the next
/// <see cref="StillForMs"/> ms read every <see cref="StillEveryMs"/> ms. Measured with real keys on a window of its own that
/// animates (a blinking square, a bar that grows each second): told by cells that move, as a click is, a key that did nothing
/// read as changed 2 of 4, because a bar crosses into new cells that never moved before. A window that keeps moving proves
/// nothing, so it claims nothing: its key stays unverified, which is what it is. An answer that animates and settles still
/// counts. What moves more slowly than once a second can still deceive. Absence says nothing. Never of a window brought up
/// for the key (WindowsDesktopInteractionAdapter).
/// </summary>
internal sealed class KeySurfaceWitness(
    Func<nint, bool?, CancellationToken, ValueTask<VisibleControlSurface.CapturedWindow?>> read,
    Func<nint, long, bool> personTouched)
{
    internal const int Looks = 3;
    internal const int LookMs = 100;
    internal const int SettledAfterMs = 600;
    internal const int StillForMs = 550;
    internal const int StillEveryMs = 110;

    internal static KeySurfaceWitness Product { get; } = new(
        static (window, selfDrawn, token) => VisibleControlSurface.CaptureAsync(window, token, selfDrawn: selfDrawn),
        WindowsUserInputPause.PersonTouched);

    /// <summary>The window right before the key, as it stands. Null when it cannot be read: the key goes anyway.</summary>
    internal async ValueTask<VisibleControlSurface.CapturedWindow?> BeforeAsync(nint window, CancellationToken cancellationToken)
    {
        try
        {
            return await read(window, null, cancellationToken).ConfigureAwait(false);
        }
        catch (Exception exception) when (exception is IOException or InvalidOperationException
            or OverflowException or ArgumentException or System.Runtime.InteropServices.ExternalException)
        {
            return null;
        }
    }

    /// <summary>
    /// Whether the window changed after the key, by what <paramref name="before"/> shows. The person's own input to that
    /// window since <paramref name="pressedAt"/> ends the proof, as in a click's (WindowsVisibleOcrLocator); so does a
    /// screen copy once another window holds the front (<paramref name="readable"/>). The key is already sent: a capture
    /// that fails or a request cancelled now only leaves it unproved.
    /// </summary>
    internal async ValueTask<KeySurfaceVerdict> ChangedAsync(
        VisibleControlSurface.CapturedWindow before, long pressedAt, Func<bool> readable, CancellationToken cancellationToken)
    {
        ValueTask<VisibleControlSurface.CapturedWindow?> Again(CancellationToken token) =>
            read(before.Hwnd, before.SelfDrawn, token);
        try
        {
            for (int look = 0; look < Looks; look++)
            {
                await Task.Delay(LookMs, cancellationToken).ConfigureAwait(false);
                if (!readable() || personTouched(before.Hwnd, pressedAt)
                    || await Again(cancellationToken).ConfigureAwait(false) is not { } after
                    || after.Hwnd != before.Hwnd)
                    return KeySurfaceVerdict.Unknown;
                if (string.Equals(after.Sha256, before.Sha256, StringComparison.Ordinal))
                    continue;
                await Task.Delay(SettledAfterMs, cancellationToken).ConfigureAwait(false);
                if (await Again(cancellationToken).ConfigureAwait(false) is not { } settled
                    || settled.Hwnd != before.Hwnd
                    || string.Equals(settled.Sha256, before.Sha256, StringComparison.Ordinal))
                    return KeySurfaceVerdict.Unknown;
                for (int waited = 0; waited < StillForMs; waited += StillEveryMs)
                {
                    await Task.Delay(StillEveryMs, cancellationToken).ConfigureAwait(false);
                    if (await Again(cancellationToken).ConfigureAwait(false) is not { } later
                        || !string.Equals(later.Sha256, settled.Sha256, StringComparison.Ordinal))
                        return KeySurfaceVerdict.Unknown;
                }

                return readable() && !personTouched(before.Hwnd, pressedAt)
                    ? KeySurfaceVerdict.Changed
                    : KeySurfaceVerdict.Unknown;
            }

            return KeySurfaceVerdict.Still;
        }
        catch (OperationCanceledException)
        {
            return KeySurfaceVerdict.Unknown;
        }
        catch (Exception exception) when (exception is IOException or InvalidOperationException
            or OverflowException or ArgumentException or System.Runtime.InteropServices.ExternalException)
        {
            return KeySurfaceVerdict.Unknown;
        }
    }
}

/// <summary>What a plain key's window showed: changed and settled; the very same image at every look; or no telling (it keeps
/// moving, it could not be read, the person touched it).</summary>
internal enum KeySurfaceVerdict
{
    Unknown,
    Still,
    Changed,
}
