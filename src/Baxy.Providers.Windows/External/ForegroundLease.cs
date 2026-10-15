using System.Globalization;
using System.Runtime.InteropServices;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// The rule for an act that still needs the real keyboard or mouse (GOAL_COMPUTER_USE_V3 point 0, fix 3): wait for
/// the person to pause, take the front for a short burst, and give back exactly what was taken. Nothing is sent
/// over the person: the wait has a ceiling and, when it runs out, the act fails with <c>input_user_not_paused</c>.
/// </summary>
internal interface IForegroundLease
{
    /// <summary>
    /// Waits for a pause of the person (<see cref="ForegroundLease.QuietMs"/> without their input, no modifier key
    /// and no mouse button down), saves the window in front, the place of <paramref name="window"/> in the window
    /// order and the cursor, and brings <paramref name="window"/> to the front. The burst says whether it may act;
    /// it must always be restored.
    /// </summary>
    ValueTask<IInputBurst> AcquireAsync(nint window, CancellationToken cancellationToken);

    /// <summary>
    /// The burst of a helper that finds and brings up its own window (a script that locates it by itself): waits for
    /// the person's pause like <see cref="AcquireAsync"/> (a bare move too: a helper may jump the cursor to a click, and
    /// never from under a hand that is moving it), saves the window in front and the cursor, and takes nothing yet. As
    /// a typed flow (<see cref="AcquireForFlowAsync"/>), it is cut only by an input that reaches: a key, a mouse button,
    /// the wheel, or the cursor passing over a window the helper brought up. <see cref="IInputBurst.Restore"/> gives the
    /// front back when the window in front is one the helper brought up (<see cref="IInputBurst.ObserveFront"/>) or the
    /// person did nothing meanwhile that could have brought it up themselves, and the cursor to where the person last
    /// left it.
    /// </summary>
    ValueTask<IInputBurst> AcquireForHelperAsync(CancellationToken cancellationToken);

    /// <summary>
    /// The burst of a typed flow on a known window (the messaging and Steam clients' keys and clicks,
    /// <see cref="LeasedInput.RunAsync{T}"/>): as <see cref="AcquireAsync"/>, but a flow cannot resume after the
    /// person's pause the way a mission's act does (it is stopped and fails), so once granted it is cut only by an
    /// input of theirs that reaches: a key, a mouse button or the wheel, or the cursor passing over the leased window.
    /// A bare move of the mouse elsewhere changes nothing of that window (molestia-ayudantes: a move during a script of
    /// a few hundred ms killed it). The pause waited for before it is the whole pause, a bare move too (review of
    /// molestia-ayudantes, 2: a window brought up under a moving cursor caught the next move and the flow stopped half
    /// done, where waiting refused it cleanly with nothing sent).
    /// </summary>
    ValueTask<IInputBurst> AcquireForFlowAsync(nint window, CancellationToken cancellationToken) =>
        AcquireAsync(window, cancellationToken);

    /// <summary>
    /// An act of a computer-use mission on its own window (the owner's decision of 2026-10-10, «no molestar» in its
    /// simple form: BAXY never types nor clicks in the person's window; for the rest it brings the mission's window to
    /// the front while it acts and gives the front back when the mission ends). After the person's pause, as
    /// <see cref="AcquireAsync"/> waits for it, the window is brought to the front and kept there while the person stays
    /// still; the lease gives the person's window the front back at their first input, after a text, and once the
    /// mission ended (<see cref="IMissionFrontSignal"/>), behind the act in flight. Null when the window holds the front;
    /// otherwise why nothing may be sent (<c>input_user_not_paused</c>, <c>input_window_not_in_front</c>, or
    /// <c>input_mission_ended</c> for an act of a mission that already ended).
    /// </summary>
    ValueTask<string?> TakeForMissionAsync(nint window, CancellationToken cancellationToken) =>
        ValueTask.FromResult<string?>(null);

    /// <summary>The mission's act taken by <see cref="TakeForMissionAsync"/> was done (whatever its outcome).</summary>
    void MissionActEnded(string operation)
    {
    }

    /// <summary>
    /// Waits for the person's pause as <see cref="AcquireAsync"/> does, and takes nothing: whether they paused before
    /// the ceiling and how long it took. What must be read right before a burst (a pointer's baseline) is read after it.
    /// </summary>
    ValueTask<(bool Paused, long WaitedMs)> WaitForPauseAsync(CancellationToken cancellationToken) =>
        ValueTask.FromResult((true, 0L));
}

/// <summary>A burst of real input on one window: acting is allowed while <see cref="MayAct"/> holds.</summary>
internal interface IInputBurst
{
    /// <summary>Why nothing may be sent (<c>input_user_not_paused</c>, <c>input_window_not_in_front</c>), or null.</summary>
    string? Refusal { get; }

    /// <summary>How long the person's pause was waited for.</summary>
    long WaitedMs { get; }

    /// <summary>Whether the person's input arrived since the burst began: the burst stops there.</summary>
    bool UserActed { get; }

    /// <summary>
    /// Whether the person's input since the burst began could reach a window's content (a key, a mouse button, the
    /// wheel): only a bare move of the mouse could not. A key of theirs while the leased window held the front went
    /// into it, mixed with what the burst sent.
    /// </summary>
    bool UserReached => UserActed;

    /// <summary>
    /// Whether the person's input is told apart from BAXY's (Raw Input started). When it is not,
    /// <see cref="UserActed"/> never says they acted, so an act of many inputs (a long text) is cut into short bursts,
    /// each after a pause of the whole session's input (safety review r10a).
    /// </summary>
    bool TellsPerson => true;

    /// <summary>Whether the burst may still send: it was granted and the person has not acted since.</summary>
    bool MayAct => Refusal is null && !UserActed;

    /// <summary>
    /// Whether the person's hand is off the mouse: none of their mouse input for <see cref="ForegroundLease.QuietMs"/>.
    /// A typed flow is not cut by a bare move, but its click never jumps the cursor from under a hand that is moving it
    /// (<see cref="LeasedInput.EnsureMayMovePointer"/>; review of molestia-ayudantes, the owner's «no robar el ratón»).
    /// </summary>
    bool PointerResting => true;

    /// <summary>
    /// Whether the leased window (or a window inside it or its own dialog) still holds the front. The lease checks it
    /// once when it takes the front; a toast, a popup or an activation Windows imposes can take it afterwards without
    /// any input of the person, and a key sent then lands in that other window. A helper's burst has no window of its
    /// own and always answers true.
    /// </summary>
    bool HoldsWindow => true;

    /// <summary>
    /// A look at the window in front while a helper runs (its watcher calls it): a window the helper brought up before
    /// the person acted is the helper's, and <see cref="Restore"/> gives the front back from it even when the person
    /// went on typing afterwards. Bursts on a known window ignore it.
    /// </summary>
    void ObserveFront()
    {
    }

    /// <summary>
    /// A helper's burst whose script did not get its own window to the front (estab G4: the media client's script
    /// stopped before its search with <c>spotify_foreground_not_verified</c>): its host brings that window up the way a
    /// mission's act takes it (the bringing, then the right to set the foreground won once) before running it again. The
    /// window counts as one the helper brought up, so <see cref="Restore"/> gives the person their front back. Nothing
    /// is brought once the person acted, nor by a burst on a known window. Whether the window holds the front.
    /// </summary>
    ValueTask<bool> BringUpAsync(nint window, CancellationToken cancellationToken) => ValueTask.FromResult(false);

    /// <summary>
    /// Gives back the cursor and the window in front as they were before the burst (the window order too), and
    /// says whether both are back. Idempotent: a second call returns the first answer.
    /// </summary>
    bool Restore();

    /// <summary>How many of BAXY's own inputs the pause detector has seen so far (0 when it cannot tell).</summary>
    long OwnInputsSeen => 0;

    /// <summary>
    /// Waits until the pause detector saw <paramref name="count"/> more of BAXY's own inputs than
    /// <paramref name="seenBefore"/> (Windows routed them to the window under the cursor), up to
    /// <see cref="ForegroundLease.OwnInputSettleMs"/>; without telling them apart, a short fixed settle. A click injected
    /// with <c>mouse_event</c> is processed later by Windows: given back before, its press or its release could land
    /// in the person's window or where their cursor went back to (review of fable/cu-v3-rafaga).
    /// </summary>
    ValueTask SettleOwnInputAsync(long seenBefore, int count, CancellationToken cancellationToken) =>
        ValueTask.CompletedTask;
}

/// <summary>A clock the lease waits on (fakes advance it in tests).</summary>
internal interface ILeaseClock
{
    long NowMs { get; }

    ValueTask DelayAsync(int milliseconds, CancellationToken cancellationToken);
}

/// <summary>The desktop the lease reads and changes: the window in front, the window order and the cursor.</summary>
internal interface ILeaseDesktop
{
    nint Foreground();

    /// <summary>
    /// Whether this window, a window inside it or a window it owns (its own dialog) holds the foreground; another
    /// window of the same process is the person's and does not count.
    /// </summary>
    bool Holds(nint window);

    bool IsAlive(nint window);

    bool IsMinimized(nint window);

    /// <summary>
    /// Whether two windows belong to the same application (the same process): a dialog or a new window that one opened
    /// with the person's keys. When it cannot be told, false.
    /// </summary>
    bool SameApplication(nint window, nint other) => false;

    /// <summary>The window right above this one in the window order (0 when it is the first).</summary>
    nint WindowAbove(nint window);

    /// <summary>The cursor in physical pixels.</summary>
    (int X, int Y) Cursor();

    /// <summary>
    /// Whether the window Windows shows at this point (physical pixels: the one a press or the wheel there reaches) is
    /// this window, one inside it or one it owns. When it cannot be told, true.
    /// </summary>
    bool Shows(nint window, int x, int y) => true;

    bool SetCursor(int x, int y);

    /// <summary>Brings the window to the front; whether it holds it afterwards.</summary>
    bool BringToFront(nint window);

    /// <summary>
    /// Encargo K (banco def1 x8, c2): whether the window in front already takes the keyboard. Windows activates a window
    /// first and its thread puts the keyboard's focus in it a moment later; a key sent in between is lost. True when the
    /// keyboard's focus is a window inside the one in front, and not the frame itself while it shows a part another
    /// thread draws (an application inside a frame of another process, which gets the focus from the frame). True when
    /// it cannot be told or the window is not in front (the act's own checks decide then).
    /// </summary>
    bool TakesKeys(nint window) => true;

    /// <summary>Hands the front back to a window that had it (attached to the thread in front).</summary>
    void GiveFront(nint window);

    /// <summary>Puts the window right below another without activating either.</summary>
    void PlaceBelow(nint window, nint above);

    /// <summary>Minimizes the window without activating anything.</summary>
    void Minimize(nint window);
}

internal sealed class ForegroundLease : IForegroundLease
{
    /// <summary>The pause the person must leave before BAXY acts (the goal's ≥ ~500 ms).</summary>
    internal const int QuietMs = 500;

    /// <summary>The default ceiling of the wait, overridable with <c>BAXY_INPUT_PAUSE_MAX_WAIT_MS</c>.</summary>
    internal const int DefaultMaxWaitMs = 8000;

    /// <summary>The longest a burst waits for its own inputs to reach the detector before giving the front back.</summary>
    internal const int OwnInputSettleMs = 100;

    // The settle when the detector cannot tell BAXY's input apart (the keyboard's own settle).
    private const int OwnInputFallbackMs = 40;
    private const int OwnInputPollMs = 5;

    private const int FrontAttempts = 4;
    private const int FrontRetryMs = 50;

    /// <summary>
    /// How long the lease keeps asking for the front of a window that has not taken it (r20b palanca 4): past this, the
    /// burst is refused with <c>input_window_not_in_front</c> and nothing is sent.
    /// </summary>
    internal const int FrontTakeCapMs = 1000;

    // How often the watcher of a mission's front looks at the person, the mission and the window.
    private const int MissionWatchMs = 25;

    /// <summary>
    /// Encargo K: the longest a window just brought up is given to take the keyboard (<see cref="ILeaseDesktop.TakesKeys"/>)
    /// before the act goes anyway, as it went before; how often it is looked at meanwhile.
    /// </summary>
    internal const int KeysReadyCapMs = 300;

    private const int KeysReadyPollMs = 15;

    private static readonly Lazy<ForegroundLease> SharedInstance = new(() => new ForegroundLease(
        WindowsUserInputPause.Shared, new SystemLeaseClock(), WindowsLeaseDesktop.Instance, ConfiguredMaxWait(),
        WindowsMissionFrontSignal.Instance));

    private readonly IUserInputPause _pause;
    private readonly ILeaseClock _clock;
    private readonly ILeaseDesktop _desktop;
    private readonly int _maxWaitMs;
    private readonly IMissionRunning _missions;
    private readonly bool _watchMission;
    private readonly Lock _missionGate = new();
    private MissionFront? _mission;
    private bool _watching;
    private bool _missionActInFlight;

    /// <param name="missions">What the App says of its missions; null: one always runs (generation 0).</param>
    /// <param name="watchMission">Whether a mission's front is watched by a task of its own (tests drive
    /// <see cref="CheckMissionFront"/> by hand on their fake clock).</param>
    internal ForegroundLease(
        IUserInputPause pause, ILeaseClock clock, ILeaseDesktop desktop, int maxWaitMs = DefaultMaxWaitMs,
        IMissionRunning? missions = null, bool watchMission = true)
    {
        _pause = pause ?? throw new ArgumentNullException(nameof(pause));
        _clock = clock ?? throw new ArgumentNullException(nameof(clock));
        _desktop = desktop ?? throw new ArgumentNullException(nameof(desktop));
        _maxWaitMs = Math.Max(0, maxWaitMs);
        _missions = missions ?? AlwaysRunning.Instance;
        _watchMission = watchMission;
    }

    private sealed class AlwaysRunning : IMissionRunning
    {
        internal static readonly AlwaysRunning Instance = new();

        public (long Generation, bool Running) Read() => (0, true);
    }

    /// <summary>The lease of the Core process, on its pause detector.</summary>
    internal static ForegroundLease Shared => SharedInstance.Value;

    public ValueTask<IInputBurst> AcquireAsync(nint window, CancellationToken cancellationToken) =>
        AcquireAsync(window, typedFlow: false, cancellationToken);

    public ValueTask<IInputBurst> AcquireForFlowAsync(nint window, CancellationToken cancellationToken) =>
        AcquireAsync(window, typedFlow: true, cancellationToken);

    public async ValueTask<string?> TakeForMissionAsync(nint window, CancellationToken cancellationToken)
    {
        (long generation, bool running) = _missions.Read();
        if (!running)
            return "input_mission_ended";
        if (window == 0 || !_desktop.IsAlive(window))
            return "input_window_not_in_front";
        Volatile.Write(ref _missionActInFlight, true);
        if (_desktop.Holds(window))
        {
            lock (_missionGate)
                _mission?.Windows.Add(window);
            return null;
        }

        (bool paused, _) = await WaitForPauseAsync(cancellationToken).ConfigureAwait(false);
        // Revisión D (H3): the person's window is the one in front after their pause, right before the bringing.
        nint person = paused ? _desktop.Foreground() : 0;
        bool fronted = paused && await TakeFrontAsync(window, cancellationToken).ConfigureAwait(false);
        if (!fronted)
        {
            Volatile.Write(ref _missionActInFlight, false);
            return paused ? "input_window_not_in_front" : "input_user_not_paused";
        }

        bool watch;
        lock (_missionGate)
        {
            if (_mission is not { } held || held.Generation != generation)
            {
                _mission = new MissionFront(person, [window], _clock.NowMs, generation);
            }
            else
            {
                if (!held.Windows.Contains(person))
                    held.Person = person;
                held.Windows.Add(window);
                held.TakenAt = _clock.NowMs;
            }

            watch = _watchMission && !_watching;
            _watching |= watch;
        }

        if (watch)
            _ = Task.Run(WatchMissionAsync, CancellationToken.None);
        // Encargo K (banco def1: «125+75» arrived as «25+75» and an Enter was lost, each the first key on a window just
        // brought up): the act goes once the window takes the keyboard, bounded. A window already in front waits for
        // nothing; the person's input meanwhile gives their front back (the watcher) and the act's own check refuses.
        long brought = _clock.NowMs;
        while (!_desktop.TakesKeys(window) && _desktop.Holds(window) && _clock.NowMs - brought < KeysReadyCapMs)
            await _clock.DelayAsync(KeysReadyPollMs, CancellationToken.None).ConfigureAwait(false);
        return null;
    }

    public void MissionActEnded(string operation)
    {
        Volatile.Write(ref _missionActInFlight, false);
        // Revisión D (H1): a text never leaves its window in front while the next act is decided (an Enter of the
        // person's would send what BAXY wrote); without telling the person's input apart, no front stays after any act.
        if (operation == "input.text.type" || !_pause.TellsOwnInput)
            GiveMissionFrontBack();
    }

    /// <summary>
    /// The watcher's look at a mission's front (tests call it on their fake clock): given back at once when the person's
    /// input that can reach a window (a key, a mouse button, the wheel) came after the take; given back when the mission
    /// ended or another began, once no act of it is in flight; forgotten, never fought, when the person or anything else
    /// brought another window up. Whether nothing is held any more.
    /// </summary>
    internal bool CheckMissionFront()
    {
        MissionFront? held;
        lock (_missionGate)
            held = _mission;
        if (held is null)
            return true;
        if (!held.Windows.Any(_desktop.Holds))
        {
            lock (_missionGate)
            {
                if (ReferenceEquals(_mission, held))
                    _mission = null;
            }

            return true;
        }

        if (_pause.TellsOwnInput && _pause.LastReachingInputMs > held.TakenAt)
        {
            GiveMissionFrontBack();
            return true;
        }

        (long generation, bool running) = _missions.Read();
        if ((!running || generation != held.Generation) && !Volatile.Read(ref _missionActInFlight))
        {
            GiveMissionFrontBack();
            return true;
        }

        return false;
    }

    // The person's window gets the front back from the mission's, if it still lives and the front is still the mission's.
    private void GiveMissionFrontBack()
    {
        MissionFront? held;
        lock (_missionGate)
        {
            held = _mission;
            _mission = null;
        }

        if (held is not null && held.Person != 0 && _desktop.IsAlive(held.Person) && held.Windows.Any(_desktop.Holds))
            _desktop.GiveFront(held.Person);
    }

    private async Task WatchMissionAsync()
    {
        try
        {
            while (!CheckMissionFront())
                await _clock.DelayAsync(MissionWatchMs, CancellationToken.None).ConfigureAwait(false);
        }
        finally
        {
            lock (_missionGate)
                _watching = false;
        }

        // A take that came between the last look and the end of the watch is watched again.
        bool again;
        lock (_missionGate)
        {
            again = _mission is not null && !_watching;
            _watching |= again;
        }

        if (again)
            await WatchMissionAsync().ConfigureAwait(false);
    }

    // The front a mission took: the person's window it came from, the mission's windows brought or acted on in front,
    // when it was last taken, and the mission's generation.
    private sealed class MissionFront(nint person, HashSet<nint> windows, long takenAt, long generation)
    {
        internal nint Person { get; set; } = person;

        internal HashSet<nint> Windows { get; } = windows;

        internal long TakenAt { get; set; } = takenAt;

        internal long Generation { get; } = generation;
    }

    private async ValueTask<IInputBurst> AcquireAsync(nint window, bool typedFlow, CancellationToken cancellationToken)
    {
        (bool paused, long waited) = await WaitForPauseAsync(cancellationToken).ConfigureAwait(false);
        if (!paused)
            return Burst.Refused("input_user_not_paused", waited);
        if (window == 0 || !_desktop.IsAlive(window))
            return Burst.Refused("input_window_not_in_front", waited);
        long began = _clock.NowMs;
        var saved = new Saved(
            _desktop.Foreground(),
            _desktop.WindowAbove(window),
            _desktop.IsMinimized(window),
            _desktop.Cursor(),
            _desktop.Holds(window));
        var burst = new Burst(this, window, saved, began, waited, typedFlow);
        if (!saved.WindowHeldFront && !await BringAsync(window, began, cancellationToken).ConfigureAwait(false))
            burst.Refuse("input_window_not_in_front");
        return burst;
    }

    // Revisión D (H5): the bringing, and when it does not hold, the right to set the foreground won once (this process
    // may lack it). Only a take for BAXY's own window comes here: a mission's act and a helper's window brought up by its
    // host (IInputBurst.BringUpAsync); a burst on a known window never bids.
    private async ValueTask<bool> TakeFrontAsync(nint window, CancellationToken cancellationToken)
    {
        if (await BringAsync(window, _clock.NowMs, cancellationToken).ConfigureAwait(false))
            return true;
        Applications.ForegroundHandBack.NoteFrontTaken();
        _desktop.GiveFront(window);
        return _desktop.Holds(window);
    }

    // r4a M4 (w1): the guard of an opening reads the front and hands it back under the same gate, so it never hands back,
    // between the bringing and the check, the front the lease just took; and a front that did not come is asked for again
    // on every attempt, not only looked at. r20b palanca 4 (t-file-4): the attempts end at FrontTakeCapMs.
    private async ValueTask<bool> BringAsync(nint window, long began, CancellationToken cancellationToken)
    {
        await Applications.ForegroundHandBack.FrontGate.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            bool fronted = _desktop.BringToFront(window);
            for (int attempt = 0; attempt < FrontAttempts && !fronted && _clock.NowMs - began < FrontTakeCapMs; attempt++)
            {
                await _clock.DelayAsync(FrontRetryMs, cancellationToken).ConfigureAwait(false);
                fronted = _desktop.Holds(window) || _desktop.BringToFront(window);
            }

            return fronted;
        }
        finally
        {
            _ = Applications.ForegroundHandBack.FrontGate.Release();
        }
    }

    public async ValueTask<IInputBurst> AcquireForHelperAsync(CancellationToken cancellationToken)
    {
        (bool paused, long waited) = await WaitForPauseAsync(cancellationToken).ConfigureAwait(false);
        if (!paused)
            return Burst.Refused("input_user_not_paused", waited);
        var saved = new Saved(_desktop.Foreground(), 0, false, _desktop.Cursor(), WindowHeldFront: false);
        return new Burst(this, 0, saved, _clock.NowMs, waited, typedFlow: true);
    }

    // The person's pause: QuietMs without their input and nothing held down, waited for up to the ceiling.
    public async ValueTask<(bool Paused, long WaitedMs)> WaitForPauseAsync(CancellationToken cancellationToken)
    {
        long start = _clock.NowMs;
        while (true)
        {
            cancellationToken.ThrowIfCancellationRequested();
            long now = _clock.NowMs;
            long quiet = now - _pause.LastForeignInputMs;
            if (quiet >= QuietMs && !_pause.HeldDown())
                return (true, now - start);
            if (now - start >= _maxWaitMs)
                return (false, now - start);
            long rest = quiet >= QuietMs ? 50 : QuietMs - quiet;
            await _clock.DelayAsync((int)Math.Clamp(rest, 20, 100), cancellationToken).ConfigureAwait(false);
        }
    }

    // userActed: the person's input that stopped the burst (it decides a helper's front); began: when the burst saved
    // what it gives back.
    private bool RestoreFor(nint window, Saved saved, bool userActed, IReadOnlySet<nint> helperFronts, long began)
    {
        if (window == 0)
            return RestoreForHelper(saved, userActed, helperFronts, began);

        // Only what the lease took is given back. When the window in front is no longer the leased one (the person
        // switched to another window during the burst), that front is the person's choice: handing it back to the
        // saved window, or minimizing or reordering the mission's window, would take it from them, so nothing is
        // touched and the desktop counts as theirs (restored).
        bool front = true;
        if (!saved.WindowHeldFront && saved.Foreground != 0 && _desktop.IsAlive(saved.Foreground)
            && _desktop.Holds(window))
        {
            for (int attempt = 0; attempt < 2 && _desktop.Foreground() != saved.Foreground; attempt++)
                _desktop.GiveFront(saved.Foreground);
            front = _desktop.Foreground() == saved.Foreground;
            if (_desktop.IsAlive(window))
            {
                if (saved.WasMinimized)
                    _desktop.Minimize(window);
                else if (saved.Above != 0 && saved.Above != window && _desktop.IsAlive(saved.Above))
                    _desktop.PlaceBelow(window, saved.Above);
            }
        }

        return front && RestoreCursor(saved, began);
    }

    // The cursor goes back where the person last left it: where it was when the burst began, or where their own mouse
    // input put it during the burst. A jump of BAXY's after their move (a click of a typed flow or a helper, which a
    // bare move does not stop) is not theirs (review of molestia-ayudantes, 1: the cursor stayed on the button BAXY
    // clicked, in a window gone behind). When where they put it cannot be told, it stays where it is.
    private bool RestoreCursor(Saved saved, long began)
    {
        if (PersonCursor(saved, began) is not { } target || _desktop.Cursor() == target)
            return true;
        _ = _desktop.SetCursor(target.X, target.Y);
        return _desktop.Cursor() == target;
    }

    private (int X, int Y)? PersonCursor(Saved saved, long began)
    {
        if (!_pause.TellsOwnInput || _pause.LastForeignInputMs <= began)
            return saved.Cursor;
        if (_pause.LastPointerAt is not { } pointer)
            return null;
        return pointer.AtMs > began ? (pointer.X, pointer.Y) : saved.Cursor;
    }

    // A helper's burst: the front goes back to the person's window when the window in front is one the helper brought
    // up (seen by the watcher before the person acted), as RestoreFor does while the leased window is still in front;
    // the person typing on afterwards does not make that window theirs. A third window, one that came up after the
    // person acted, is their choice and stays only when what they did could bring it up: a click, Alt or a Windows key
    // anywhere, or their keys in their own window when the new one is of that window's application (a dialog or a
    // window it opened: Ctrl+O, Ctrl+S, Ctrl+N; review of molestia-ayudantes, 3). Their keys in their window do not
    // bring up another application's (molestia-ayudantes, c6/s11/s13 «final_frente=no»: their keys cut the helper
    // before the watcher saw the window it brought up, and that window kept the front). With no input of theirs at
    // all, any change is the helper's.
    private bool RestoreForHelper(Saved saved, bool userActed, IReadOnlySet<nint> helperFronts, long began)
    {
        bool front = true;
        nint now = _desktop.Foreground();
        bool theirFront = userActed && !helperFronts.Contains(now)
            && (_pause.LastFrontMovingInputMs > began || _desktop.SameApplication(now, saved.Foreground));
        if (!theirFront && saved.Foreground != 0 && _desktop.IsAlive(saved.Foreground)
            && now != saved.Foreground)
        {
            for (int attempt = 0; attempt < 2 && _desktop.Foreground() != saved.Foreground; attempt++)
                _desktop.GiveFront(saved.Foreground);
            front = _desktop.Foreground() == saved.Foreground;
        }

        return front && RestoreCursor(saved, began);
    }

    private static int ConfiguredMaxWait() =>
        int.TryParse(
            Environment.GetEnvironmentVariable("BAXY_INPUT_PAUSE_MAX_WAIT_MS"),
            NumberStyles.Integer,
            CultureInfo.InvariantCulture,
            out int configured) && configured >= 0
            ? configured
            : DefaultMaxWaitMs;

    private readonly record struct Saved(
        nint Foreground,
        nint Above,
        bool WasMinimized,
        (int X, int Y) Cursor,
        bool WindowHeldFront);

    private sealed class Burst : IInputBurst
    {
        private readonly ForegroundLease? _lease;
        private readonly nint _window;
        private readonly Saved _saved;
        private readonly long _began;
        private readonly bool _typedFlow;
        private readonly HashSet<nint> _helperFronts = [];
        private bool? _restored;

        internal Burst(
            ForegroundLease lease, nint window, Saved saved, long began, long waited, bool typedFlow = false)
        {
            _lease = lease;
            _window = window;
            _saved = saved;
            _began = began;
            _typedFlow = typedFlow;
            WaitedMs = waited;
        }

        private Burst(string refusal, long waited)
        {
            Refusal = refusal;
            WaitedMs = waited;
            _restored = true;
        }

        internal static Burst Refused(string refusal, long waited) => new(refusal, waited);

        public string? Refusal { get; private set; }

        public long WaitedMs { get; }

        // Whether and when Restore gave the front back, whether the person had acted by then,
        // and whether an input of theirs since reached the burst's window.
        private bool _handedBack;
        private long _handedAt;
        private bool _actedBeforeHandBack;
        private bool _reachedAfterHandBack;

        /// <summary>
        /// Before the front is given back, any input of the person since the burst began. After it (interrupcion-fantasma,
        /// r9 v3-56: a click pressed in the person's pause and given back, whose post-read their typing in their own
        /// window cut three times as «you were using the PC»), only an input that could reach the burst's window: the
        /// window holds the front again; a press, the wheel, Alt, a Windows key or a media key of theirs since; the
        /// cursor passing over it since; or the cursor over it now. Their other keys go into the window they have in
        /// front and their bare moves elsewhere change nothing of it. An input in flight when the front went back
        /// counts as made before. A typed flow's or a helper's burst (<see cref="IForegroundLease.AcquireForFlowAsync"/>)
        /// is cut, before the front goes back, only by an input that reaches: a key, a mouse button, the wheel, or the
        /// cursor passing over its window (a helper's: any window it brought up).
        /// </summary>
        public bool UserActed
        {
            get
            {
                if (_lease is null || !_lease._pause.TellsOwnInput)
                    return false;
                long last = _lease._pause.LastForeignInputMs;
                if (last <= _began)
                    return false;
                if (_typedFlow && !_handedBack)
                    return ReachedFlow();
                if (!_handedBack || _actedBeforeHandBack || _reachedAfterHandBack || last <= _handedAt)
                    return true;
                // Review r2: not only at the instant of the read. A press, the wheel, Alt, a Windows key or a media key
                // of theirs since (they may act past the window in front), and the cursor passing over the window
                // between two reads (a hover changes what it draws), reach it too.
                (int x, int y) = _lease._desktop.Cursor();
                _reachedAfterHandBack = _lease._desktop.Holds(_window)
                    || _lease._pause.LastBeyondFrontInputMs > _handedAt
                    || _lease._pause.LastPointerOverMs(_window) > _handedAt
                    || _lease._desktop.Shows(_window, x, y);
                return _reachedAfterHandBack;
            }
        }

        // A typed flow's stop: an input of the person since it began that reaches (a key, a button, the wheel, or one the
        // detector missed), or the cursor over the flow's window since then; a helper's windows are the ones it brought
        // up and the one in front now when it is not the person's saved front.
        private bool ReachedFlow()
        {
            IUserInputPause pause = _lease!._pause;
            if (pause.LastReachingInputMs > _began)
                return true;
            if (_window != 0)
                return pause.LastPointerOverMs(_window) > _began;
            nint front = _lease._desktop.Foreground();
            if (front != 0 && front != _saved.Foreground && pause.LastPointerOverMs(front) > _began)
                return true;
            lock (_helperFronts)
                return _helperFronts.Any(window => pause.LastPointerOverMs(window) > _began);
        }

        public bool PointerResting
        {
            get
            {
                if (_lease is null || !_lease._pause.TellsOwnInput)
                    return true;
                long last = _lease._pause.LastPointerAt is { } pointer ? pointer.AtMs : _lease._pause.LastForeignInputMs;
                return _lease._clock.NowMs - last >= QuietMs;
            }
        }

        public bool UserReached =>
            _lease is not null && (!_lease._pause.TellsOwnInput || _lease._pause.LastReachingInputMs > _began);

        public bool TellsPerson => _lease is null || _lease._pause.TellsOwnInput;

        public bool HoldsWindow => _lease is null || _window == 0 || _lease._desktop.Holds(_window);

        public long OwnInputsSeen => _lease?._pause.OwnInputCount ?? 0;

        public async ValueTask SettleOwnInputAsync(long seenBefore, int count, CancellationToken cancellationToken)
        {
            if (_lease is null)
                return;
            if (!_lease._pause.TellsOwnInput)
            {
                await _lease._clock.DelayAsync(OwnInputFallbackMs, cancellationToken).ConfigureAwait(false);
                return;
            }

            long start = _lease._clock.NowMs;
            while (_lease._pause.OwnInputCount < seenBefore + count && _lease._clock.NowMs - start < OwnInputSettleMs)
                await _lease._clock.DelayAsync(OwnInputPollMs, cancellationToken).ConfigureAwait(false);
        }

        internal void Refuse(string refusal) => Refusal = refusal;

        public async ValueTask<bool> BringUpAsync(nint window, CancellationToken cancellationToken)
        {
            if (_lease is not { } lease || _window != 0 || window == 0 || Refusal is not null || UserActed
                || !lease._desktop.IsAlive(window))
                return false;
            bool fronted = lease._desktop.Holds(window)
                || await lease.TakeFrontAsync(window, cancellationToken).ConfigureAwait(false);
            ObserveFront();
            return fronted;
        }

        public void ObserveFront()
        {
            if (_lease is null || _window != 0 || Refusal is not null || _restored is not null || UserActed)
                return;
            nint front = _lease._desktop.Foreground();
            if (front != 0 && front != _saved.Foreground)
            {
                lock (_helperFronts)
                    _ = _helperFronts.Add(front);
            }
        }

        public bool Restore()
        {
            if (_restored is null)
            {
                ObserveFront();
                HashSet<nint> fronts;
                lock (_helperFronts)
                    fronts = [.. _helperFronts];
                bool acted = UserActed;
                _restored = _lease!.RestoreFor(_window, _saved, acted, fronts, _began);
                if (_window != 0 && Refusal is null)
                {
                    _actedBeforeHandBack = acted || _lease._pause.UnexplainedInputMs > _began;
                    _handedAt = _lease._clock.NowMs;
                    _handedBack = true;
                }
            }

            return _restored.Value;
        }
    }
}

internal sealed class SystemLeaseClock : ILeaseClock
{
    public long NowMs => Environment.TickCount64;

    public ValueTask DelayAsync(int milliseconds, CancellationToken cancellationToken) =>
        new(Task.Delay(milliseconds, cancellationToken));
}

/// <summary>The lease's desktop on Win32; the cursor is read and set in physical pixels, the unit of the views.</summary>
internal sealed partial class WindowsLeaseDesktop : ILeaseDesktop
{
    /// <summary>The one Win32 desktop; it keeps no state.</summary>
    internal static readonly WindowsLeaseDesktop Instance = new();

    private const uint NoSize = 0x0001;
    private const uint NoMove = 0x0002;
    private const uint NoActivate = 0x0010;
    private const uint NoOwnerZOrder = 0x0200;
    private const int ShowMinimizedNoActivate = 7;
    private const uint PreviousWindow = 3;

    public nint Foreground() => GetForegroundWindow();

    public bool Holds(nint window) => VisibleControlSurface.ForegroundIsOrOwnedBy(window);

    public bool IsAlive(nint window) => window != 0 && IsWindow(window);

    public bool IsMinimized(nint window) => IsIconic(window);

    public bool SameApplication(nint window, nint other)
    {
        if (window == 0 || other == 0)
            return false;
        _ = GetWindowThreadProcessId(window, out uint process);
        _ = GetWindowThreadProcessId(other, out uint otherProcess);
        return process != 0 && process == otherProcess;
    }

    public nint WindowAbove(nint window) => GetWindow(window, PreviousWindow);

    public (int X, int Y) Cursor() => VisibleControlSurface.InPhysicalPixels(
        () => GetCursorPos(out Point point) ? (point.X, point.Y) : (0, 0));

    public bool SetCursor(int x, int y) => VisibleControlSurface.InPhysicalPixels(() => SetCursorPos(x, y));

    public bool Shows(nint window, int x, int y) => VisibleControlSurface.PointMayShow(window, x, y);

    public bool BringToFront(nint window)
    {
        // Said before it happens: the UIA worker's front net must not take this front back (LeaseFrontSignal).
        LeaseFrontSignal.Mark(window);
        return VisibleControlSurface.BringToFront(window);
    }

    public bool TakesKeys(nint window)
    {
        nint front = GetForegroundWindow();
        if (front == 0 || !Holds(window))
            return true;
        uint thread = GetWindowThreadProcessId(front, out _);
        var info = new GuiThreadInfo { Size = Marshal.SizeOf<GuiThreadInfo>() };
        if (thread == 0 || !GetGUIThreadInfo(thread, ref info))
            return true;
        if (info.Focus == 0 || (info.Focus != front && !IsChild(front, info.Focus)))
            return false;
        if (info.Focus != front)
            return true;
        // The focus on the frame itself while a direct child of another thread (a hosted part, its input queue attached
        // to the frame's) is shown: the frame has not handed it on yet. A window whose own part has the focus (a
        // browser's page beside its compositor's child) is ready.
        for (nint child = GetWindow(front, FirstChild); child != 0; child = GetWindow(child, NextWindow))
        {
            if (IsWindowVisible(child) && GetWindowThreadProcessId(child, out _) is var hosted && hosted != 0
                && hosted != thread)
                return false;
        }

        return true;
    }

    // Verified, and with the right won when this process lacks it (ForegroundRight, cu-v3-foco-segunda).
    public void GiveFront(nint window) => _ = ForegroundRight.Give(window);

    public void PlaceBelow(nint window, nint above) =>
        _ = SetWindowPos(window, above, 0, 0, 0, 0, NoSize | NoMove | NoActivate | NoOwnerZOrder);

    public void Minimize(nint window) => _ = ShowWindow(window, ShowMinimizedNoActivate);

    [StructLayout(LayoutKind.Sequential)]
    private struct Point
    {
        public int X;
        public int Y;
    }

    private const uint FirstChild = 5;
    private const uint NextWindow = 2;

    [StructLayout(LayoutKind.Sequential)]
    private struct GuiThreadInfo
    {
        public int Size;
        public uint Flags;
        public nint Active;
        public nint Focus;
        public nint Capture;
        public nint MenuOwner;
        public nint MoveSize;
        public nint Caret;
        public int CaretLeft;
        public int CaretTop;
        public int CaretRight;
        public int CaretBottom;
    }

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool GetGUIThreadInfo(uint thread, ref GuiThreadInfo info);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool IsChild(nint parent, nint window);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool IsWindowVisible(nint window);

    [LibraryImport("user32.dll")]
    private static partial nint GetForegroundWindow();

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool IsWindow(nint window);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool IsIconic(nint window);

    [LibraryImport("user32.dll")]
    private static partial nint GetWindow(nint window, uint command);

    [LibraryImport("user32.dll")]
    private static partial uint GetWindowThreadProcessId(nint window, out uint processId);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool GetCursorPos(out Point point);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool SetCursorPos(int x, int y);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool SetWindowPos(nint window, nint insertAfter, int x, int y, int width, int height, uint flags);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool ShowWindow(nint window, int command);
}
