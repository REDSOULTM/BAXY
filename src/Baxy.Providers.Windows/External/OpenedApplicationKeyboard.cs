namespace Baxy.Providers.Windows.External;

/// <summary>
/// FT/proveedores goal (E6): the window a keyboard act with no <c>window</c> of its own is sent to when an application
/// app.open opened moments ago is not the one in front. Measured: BAXY opened the Notepad (verified) and typed with no
/// window, but Steam had come back to the front, and the text and the select-all went to Steam or failed
/// (<c>select_all_postcondition_not_verified</c>). A click right after an opening already acts on the application opened
/// (M132, <see cref="WindowsVisibleControlAdapter"/>); a key, a text, a select-all, a copy or a paste does too: the act is
/// sent as if it named that application's largest usable window (<see cref="VisibleControlSurface.FrontOpenedAsync"/>,
/// as the click picks it), and the provider's named-window path brings it to the front through the lease after the
/// person's pause, or refuses honestly. Only BAXY's own record of the opening is read, never the person's words.
/// </summary>
internal interface IOpenedApplicationKeyboard
{
    /// <summary>The opened application's window the act goes to; null when there is no fresh opening, one of its
    /// windows is already in front, or it has no usable window (the act goes to the front, as before).</summary>
    ValueTask<OpenedKeyboardWindow?> WindowAsync(CancellationToken cancellationToken);
}

/// <summary>The opened application's window a keyboard act was sent to, and its title for the receipt.</summary>
internal readonly record struct OpenedKeyboardWindow(nint Window, string Title);

internal sealed class OpenedApplicationKeyboard : IOpenedApplicationKeyboard
{
    private readonly IOpenedApplicationFocus _focus;
    private readonly Func<nint> _front;
    private readonly Func<nint, VisibleControlSurface.OpenedApplication, bool> _windowOf;
    private readonly Func<nint, string> _title;

    /// <param name="focus">The opening, with the click path's own freshness (<see cref="OpenedApplicationFocus"/>).</param>
    /// <param name="front">The window in front now.</param>
    /// <param name="windowOf">Whether a window is the opened application's (its process, or the family its launch
    /// started), as the click path judges it (<see cref="WindowsVisibleControlAdapter.WindowOfProcess"/>).</param>
    /// <param name="title">A window's title, for the receipt.</param>
    internal OpenedApplicationKeyboard(
        IOpenedApplicationFocus focus,
        Func<nint> front,
        Func<nint, VisibleControlSurface.OpenedApplication, bool> windowOf,
        Func<nint, string> title)
    {
        _focus = focus ?? throw new ArgumentNullException(nameof(focus));
        _front = front ?? throw new ArgumentNullException(nameof(front));
        _windowOf = windowOf ?? throw new ArgumentNullException(nameof(windowOf));
        _title = title ?? throw new ArgumentNullException(nameof(title));
    }

    /// <summary>The product's: the opening app.open noted, the window in front and the click path's process rule.</summary>
    internal static OpenedApplicationKeyboard Product { get; } = new(
        new OpenedApplicationFocus(),
        VisibleControlSurface.FrontWindow,
        WindowsVisibleControlAdapter.IsWindowOfOpened,
        VisibleControlSurface.WindowTitle);

    public async ValueTask<OpenedKeyboardWindow?> WindowAsync(CancellationToken cancellationToken)
    {
        // FT/proveedores goal (E6): peeked, never taken. The click path takes the opening at its first click (it then
        // waits for the application's page to be drawn and binds the click to it, M132); a key or a text taking it would
        // leave the click right after a typed search without that wait. A keyboard act changes nothing of what was
        // opened: several of them in a row (a text, a select-all, a copy) all go to the same application while the
        // opening is fresh, and a click still finds it.
        if (_focus.PeekOpened() is not { } opened)
            return null;
        nint front = _front();
        if (front != 0 && _windowOf(front, opened))
            return null;
        // Neither brought to the front here nor judged drawn: the provider's lease brings it up after the person's
        // pause, and a key needs no drawn page.
        VisibleControlSurface.OpenedSurface surface = await _focus
            .FrontAsync(opened, judgeDrawn: false, cancellationToken, bringToFront: false)
            .ConfigureAwait(false);
        if (surface.Window != 0)
            return new OpenedKeyboardWindow(surface.Window, _title(surface.Window));
        // FT/proveedores goal (E6): a minimized application has no usable window; its minimized one is restored by the
        // lease's bringing it up (VisibleControlSurface.BringToFront restores an iconic window), or the act is refused.
        nint minimized = _focus.MinimizedWindow(opened);
        return minimized == 0 ? null : new OpenedKeyboardWindow(minimized, _title(minimized));
    }
}
