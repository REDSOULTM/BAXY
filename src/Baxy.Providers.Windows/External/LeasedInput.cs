namespace Baxy.Providers.Windows.External;

/// <summary>
/// A flow of real input (keys, clicks by coordinates, a helper that brings its own window up) run inside one burst of
/// the foreground lease (GOAL_COMPUTER_USE_V3 point 0, fix 3): it starts only after the person's pause, every raw event
/// of the flow first asks <see cref="EnsureMayAct"/> and the flow stops at the person's first input, and the window in
/// front and the cursor are given back at the end. Used by the primitives that cannot reach their window without the
/// real keyboard or mouse; the ones that can (UI Automation patterns, window messages) never come here.
/// </summary>
internal static class LeasedInput
{
    /// <summary>The flow stopped because the person acted during its burst.</summary>
    internal const string Interrupted = "input_user_interrupted";

    /// <summary>The flow stopped because its window lost the front without the person's input (a toast, a popup).</summary>
    internal const string WindowChanged = "input_window_changed";

    /// <summary>How often the watcher of a helper's process looks at the burst.</summary>
    internal const int HelperWatchMs = 40;

    private static readonly AsyncLocal<IInputBurst?> Current = new();

    /// <summary>
    /// Before each raw event of a flow running inside a burst: throws <see cref="BurstStoppedException"/> when the
    /// person acted since the burst began (<see cref="Interrupted"/>) or the leased window no longer holds the front
    /// (<see cref="WindowChanged"/>), so nothing more is sent over the person or into another window. Outside a burst
    /// it does nothing.
    /// </summary>
    internal static void EnsureMayAct()
    {
        if (Current.Value is not { } burst)
            return;
        if (!burst.MayAct)
            throw new BurstStoppedException(Interrupted);
        if (!burst.HoldsWindow)
            throw new BurstStoppedException(WindowChanged);
    }

    /// <summary>
    /// As <see cref="EnsureMayAct"/>, before a raw event that jumps the cursor (a click by coordinates): it also stops
    /// the flow (<see cref="Interrupted"/>) while the person's hand moves the mouse
    /// (<see cref="IInputBurst.PointerResting"/>), which does not stop its keys, so the cursor never jumps from under it.
    /// </summary>
    internal static void EnsureMayMovePointer()
    {
        EnsureMayAct();
        if (Current.Value is { PointerResting: false })
            throw new BurstStoppedException(Interrupted);
    }

    /// <summary>
    /// Runs <paramref name="act"/> in a typed flow's burst on <paramref name="window"/> (brought to the front by the
    /// lease, <see cref="IForegroundLease.AcquireForFlowAsync"/>). When the lease refuses (<c>input_user_not_paused</c>,
    /// <c>input_window_not_in_front</c>) nothing runs and <paramref name="stopped"/> answers with that code and
    /// <c>false</c> (nothing sent); when the person's input reaches during the flow (a key, a click, the wheel, the
    /// cursor over the window) it answers <see cref="Interrupted"/> (<see cref="WindowChanged"/> when the window lost
    /// the front, or the code the flow stopped with) and <c>true</c> (something may have been sent).
    /// </summary>
    internal static async ValueTask<T> RunAsync<T>(
        IForegroundLease lease,
        nint window,
        Func<CancellationToken, ValueTask<T>> act,
        Func<string, bool, T> stopped,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(lease);
        IInputBurst burst = await lease.AcquireForFlowAsync(window, cancellationToken).ConfigureAwait(false);
        return await InBurstAsync(burst, act, stopped, cancellationToken).ConfigureAwait(false);
    }

    /// <summary>
    /// As <see cref="RunAsync{T}"/> for a helper that locates and brings up its own window (a script): the lease waits
    /// for the pause and gives back whatever front and cursor the helper took.
    /// </summary>
    internal static async ValueTask<T> RunHelperAsync<T>(
        IForegroundLease lease,
        Func<CancellationToken, ValueTask<T>> act,
        Func<string, bool, T> stopped,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(lease);
        IInputBurst burst = await lease.AcquireForHelperAsync(cancellationToken).ConfigureAwait(false);
        return await InBurstAsync(burst, act, stopped, cancellationToken).ConfigureAwait(false);
    }

    /// <summary>
    /// The helper burst of a script host (a PowerShell helper that finds and brings up its own window and sends real
    /// keys or clicks there), or null when the host runs without a lease (the test seams, whose runners are fakes). A
    /// refused burst (<see cref="IInputBurst.Refusal"/>) means nothing may run; the burst is restored either way.
    /// </summary>
    internal static async ValueTask<IInputBurst?> HelperBurstAsync(
        IForegroundLease? lease,
        CancellationToken cancellationToken) =>
        lease is null ? null : await lease.AcquireForHelperAsync(cancellationToken).ConfigureAwait(false);

    /// <summary>
    /// Runs a helper's process inside its burst with a watcher: every <see cref="HelperWatchMs"/> it notes the window
    /// in front (<see cref="IInputBurst.ObserveFront"/>) and, at the person's first input that reaches (a key, a click,
    /// the wheel, the cursor over a window the helper brought up; a bare move elsewhere does not), cancels the run,
    /// which kills the process, so the script never goes on typing over them. Answers the run's result, or
    /// <c>Interrupted: true</c> when the watcher stopped it (something may have been sent). With no burst (the test
    /// seams) the run goes as it is.
    /// </summary>
    internal static async ValueTask<(T? Result, bool Interrupted)> WatchHelperAsync<T>(
        IInputBurst? burst,
        Func<CancellationToken, ValueTask<T>> run,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(run);
        if (burst is null)
            return (await run(cancellationToken).ConfigureAwait(false), false);
        if (!burst.MayAct)
            return (default, true);

        // The helper's Unicode keys never reach Raw Input and cannot be noted from here one by one (review of
        // interrupcion-fantasma, bloqueante): the detector does not escalate missed input across reads meanwhile.
        using IDisposable sending = WindowsUserInputPause.HelperSending();
        using var stop = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        using var watching = new CancellationTokenSource();
        Task watcher = WatchAsync(burst, stop, watching.Token);
        try
        {
            T result = await run(stop.Token).ConfigureAwait(false);
            return (result, false);
        }
        catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested && stop.IsCancellationRequested)
        {
            return (default, true);
        }
        finally
        {
            await watching.CancelAsync().ConfigureAwait(false);
            await watcher.ConfigureAwait(false);
        }
    }

    private static async Task WatchAsync(IInputBurst burst, CancellationTokenSource stop, CancellationToken watching)
    {
        while (!watching.IsCancellationRequested)
        {
            burst.ObserveFront();
            if (!burst.MayAct)
            {
                await stop.CancelAsync().ConfigureAwait(false);
                return;
            }

            try
            {
                await Task.Delay(HelperWatchMs, watching).ConfigureAwait(false);
            }
            catch (OperationCanceledException)
            {
                return;
            }
        }
    }

    private static async ValueTask<T> InBurstAsync<T>(
        IInputBurst burst,
        Func<CancellationToken, ValueTask<T>> act,
        Func<string, bool, T> stopped,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(act);
        ArgumentNullException.ThrowIfNull(stopped);
        if (burst.Refusal is string refusal)
        {
            _ = burst.Restore();
            return stopped(refusal, false);
        }

        IInputBurst? previous = Current.Value;
        Current.Value = burst;
        try
        {
            cancellationToken.ThrowIfCancellationRequested();
            return await act(cancellationToken).ConfigureAwait(false);
        }
        catch (BurstStoppedException stop)
        {
            return stopped(stop.Code, true);
        }
        finally
        {
            Current.Value = previous;
            _ = burst.Restore();
        }
    }

    /// <summary>
    /// The burst may not send any more (the person acted, or the window lost the front): the flow stops before its next
    /// raw event. A flow may stop with a code of its own that says what its interruption left (<see cref="Code"/>).
    /// </summary>
    internal sealed class BurstStoppedException : Exception
    {
        public BurstStoppedException()
            : this(Interrupted)
        {
        }

        public BurstStoppedException(string code)
            : base(code)
        {
            Code = code;
        }

        public BurstStoppedException(string code, Exception innerException)
            : base(code, innerException)
        {
            Code = code;
        }

        /// <summary>The receipt's error code for the stop.</summary>
        public string Code { get; }
    }
}

/// <summary>Gives a helper burst back at the end of a <c>using</c> scope (nothing when there is no burst).</summary>
internal readonly struct BurstRestore(IInputBurst? burst) : IDisposable
{
    public void Dispose() => _ = burst?.Restore();
}
