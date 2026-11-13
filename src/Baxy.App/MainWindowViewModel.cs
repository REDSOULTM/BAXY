using System.Collections.ObjectModel;
using System.ComponentModel;
using System.Globalization;
using System.IO;
using System.Runtime.CompilerServices;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Contracts;
using Baxy.Providers.Windows.External;
using Baxy.Providers.Windows.Routines;
using Baxy.Security.Windows;

namespace Baxy.App;

/// <summary>
/// The shell's state for the window, the interface channel, the tray and the conductor: it starts the core and the
/// mind, takes the person's words (typed or transcribed) and their Sí/No, hands each turn to the native loop
/// (<see cref="NativeTurnLoop"/>) and publishes what the model wrote. It authors no reply of its own: when a turn cannot
/// reach an answer the interface shows a state, not a sentence.
/// </summary>
internal sealed class MainWindowViewModel : INotifyPropertyChanged, IAsyncDisposable
{
    private readonly SynchronizationContext _uiContext;
    private readonly string _memorySessionId;
    private readonly CancellationTokenSource _mindLifetimeCancellation = new();
    private CancellationTokenSource _mindStartCut = new();
    // API1: how many starts a change of the model cut (ExternalModelChanged): a switch whose own start was cut goes round again.
    private int _mindStartsCut;
    private readonly NativeTurnLoop _loop;
    // One turn at a time, the person's or the heartbeat's: a person's words that arrive during a heartbeat wait for it.
    private readonly SemaphoreSlim _turnGate = new(1, 1);
    private bool _beatActive;
    private bool _beatSpeaks;
    // The heartbeat running now stops before its next call when the person's words arrive (al máximo, flujos): they
    // waited for all its calls.
    private CancellationTokenSource? _beatInterrupt;
    // A call of the person's turn running now reached its provider (what it opened was asked for).
    private bool _personActed;
    private readonly ConversationLog? _conversationLog = ConversationLog.CreateDefault();

    /// <summary>
    /// PRV1 (PRIV-02): where the engine stores the screens it captures (its data root's «captures»), so that none stays
    /// past the request that took it (<see cref="ClearCaptures"/>). Given by <see cref="ForThisPc"/>; null removes
    /// nothing (a model built for a test acts on no folder it was not given).
    /// </summary>
    internal string? CapturesDirectory { get; init; }

    /// <summary>
    /// PRV2 (A2): what an earlier version wrote with the person's words, removed once before the first mind starts
    /// (<see cref="EarlierWords"/>). Given by <see cref="ForThisPc"/>, and not there where words are kept on this PC; null
    /// removes nothing (a model built for a test acts on no folder it was not given).
    /// </summary>
    internal EarlierWords? WordsOfEarlierVersions { get; init; }

    private bool _earlierWordsDone;

    /// <summary>The product's view model: the one that keeps this PC's capture folder empty between requests, and that
    /// removes what an earlier version kept with the person's words.</summary>
    internal static MainWindowViewModel ForThisPc() =>
        new()
        {
            CapturesDirectory = Path.Combine(MemoryOperationProtector.ResolveDataRoot(), "captures"),
            WordsOfEarlierVersions = EarlierWords.ForThisPc(),
        };

    private RetryableOperationRegistry? _retryableOperations;
    private MemoryOperationProtector? _memoryProtector;
    private CoreProcessClient? _coreClient;
    private MindSidecarClient? _mindClient;
    private Task? _mindInitializationTask;
    // 2026-10-22, review of the App: one start of the mind at a time. Two at once (a relaunch after a lost mind and the
    // engine's recovery, which starts one whenever none is ready) each launched a process, and the later took
    // _mindClient over the first without ending it: an orphan holding its model's VRAM. A start that waited finds the
    // other's mind ready and leaves it.
    private readonly SemaphoreSlim _mindStart = new(1, 1);
    private volatile MindStartupState _mindStartupState;
    private readonly StartupRetries _mindRetries = new();
    private readonly StartupRetries _coreRetries = new();
    // The mind failed the same way too often (StartupRetries): no relaunch until the person asks for one.
    private bool _mindGaveUp;
    private bool _noSupportedGpu;
    // Uso 95 (F9): a relaunch of the mind waits its turn (StartupRetries' growing wait); until it starts, the mind is
    // still on its way, never «not available».
    private volatile bool _mindRetryPending;
    // Why the last start (or run) of the mind failed (MindStartupFailure.Cause, or the App's own label), until one is up.
    private string? _mindFailureCause;
    private (long TokensPerS, long NeedMinutes, MindCardFull? CardFull)? _mindFailureRead;
    private MindModelReading? _mindReading;
    private bool _mindOnProcessor;
    private (long NeedMb, long? FreeMb)? _mindFailureMemory;
    // Completed and replaced each time the mind's state changes (MindChanged): a message waiting for the mind wakes on it.
    private TaskCompletionSource _mindChanged = new(TaskCreationOptions.RunContinuationsAsynchronously);
    private int _awaitingMind;
    private Action? _coreDisconnectedHandler;
    private int _coreDisconnectObserved;
    private bool _coreRecoveryPending;
    private Task _coreRecovery = Task.CompletedTask;
    // The person's voice commands run one after another: one sent while another waits (the first after a start waits for
    // the voice to load) queues behind it; it used to be refused, and the view's microphone modes seemed to do nothing
    // (owner, 2026-10-17).
    private readonly SemaphoreSlim _voiceCommands = new(1, 1);
    // The voice the mind turns on by itself at startup yields to the person: once they give a voice command it never
    // applies, and a command that arrives while it is starting waits for it first.
    private int _personVoiceChoice;
    private int _wakeAwaitsEar;
    private Task _startupVoice = Task.CompletedTask;
    // Done once the mind's voice state is known (its ear loaded or failed to) and the startup voice was applied. It is
    // set before the mind is announced ready, so a wake word asked for from then on (the interface applies the person's
    // «escucho siempre» as soon as the mind is up) waits for it: 2026-10-25 (spoken A/B c11b-on1), sent while the ear
    // still loaded under load, the start was answered as the App's wait ran out, the App stopped it again, and the
    // startup voice had yielded to that command: the wake word never started.
    private Task _voiceSettled = Task.CompletedTask;
    // Each wake-word command the person gives, numbered: a start that waited for the ear yields to any given after it.
    private int _wakeCommands;
    private const string WakeUnavailable = "wake_unavailable";
    private bool _startupMindPending;
    private bool _isListening;
    private bool _isWakeListening;
    private bool _isVoiceSpeaking;
    private string? _noticeAsked; // the notice's phrase last asked of the voice (VoiceSounded names it)
    private bool _isMicAvailable;
    private string _statusDescription = "Preparando BAXY";
    private bool _isReady;
    private bool _isBusy;
    private string? _startupFailure;
    private string? _lastTurnFailure;
    private string? _voiceFailure;
    // The person is speaking to BAXY (a dictation, or «Baxy» heard and its request not ended): the ear failing now
    // failed them, and sounds once (Chime.ListenFailed); failing at rest bothers nobody.
    private bool _voiceRequestOpen;
    private bool _isInitializing;
    private bool _isDisposed;
    private bool _turnExecutionActive;
    private long _turnTraceSequence;
    private bool _isPowered = true;
    private string? _quietProposal;
    // The call whose question was published last and has not ended (the view's card, the toast): a Sí/No that names
    // another one answers nothing.
    private NativeTurnConfirmation? _askedConfirmation;
    private string _beatActivity = string.Empty;
    private MindVoiceStatus? _voicePieces;
    private DateTimeOffset _mindStartedAt = DateTimeOffset.UtcNow;
    private DateTimeOffset? _mindReadyAt;
    private AlarmRinger? _ringer;

    public MainWindowViewModel()
    {
        _uiContext = SynchronizationContext.Current ?? new SynchronizationContext();
        _memorySessionId = Guid.NewGuid().ToString("D");
        Messages = new ObservableCollection<ConversationMessage>();
        _loop = new NativeTurnLoop(
            new NativeTurnLoop.Host
            {
                Core = () => _coreClient,
                Mind = () => _mindClient,
                MindForTurn = MindForTurnAsync,
                Registry = () => _retryableOperations,
                MemoryProtector = () => _memoryProtector,
                Publish = (text, route) =>
                {
                    // A heartbeat speaks only when the person is free; otherwise its words are a notification.
                    bool quiet = _beatActive && !_beatSpeaks;
                    AddMessageCore("BAXY", text, isUser: false, route, speak: !quiet,
                        silent: quiet ? SilentBecause(_beatActivity) : null);
                    if (_beatActive && quiet && route == PublicResponseRoute.Confirmation)
                    {
                        // A proposal asked while the person should not be spoken to: its question becomes a Windows
                        // notification with Sí / No once the call it asks about is known (ConfirmationAsked).
                        _quietProposal = text;
                    }
                    else if (_beatActive && quiet)
                    {
                        NotificationRequested?.Invoke(text);
                    }
                },
                Fail = failure =>
                {
                    LastTurnFailure = failure;
                    ShellTraceSink.Record(ShellTraceScopes.Turn, ShellTraceSink.TurnId, ShellTraceStages.TurnError,
                        failure);
                },
                // The notice is said aloud and nothing else: no line of the chat, the conversation log or the
                // interface, so it never reads as the turn's answer.
                Notice = notice =>
                {
                    // Not said when the owner switched it off or silenced BAXY's voice (it was said even then); checked
                    // again here because either may change while the mind writes the phrase.
                    if (NoticeWouldBeHeard() && _mindClient is { } mind)
                    {
                        _ = SpeakNoticeAsync(mind, notice);
                    }
                },
                // Nobody would hear it: the mind is not asked to write a notice.
                NoticeHeard = NoticeWouldBeHeard,
                StillReading = () => SoundUnlessMuted(Chime.StillReading),
                StepCompleted = step =>
                {
                    _personActed |= step.Sent && !_beatActive;
                    StepCompleted?.Invoke(step);
                },
                StepStarted = (id, operation, arguments) => StepStarted?.Invoke(id, operation, arguments),
                ConfirmationAsked = asked =>
                {
                    _askedConfirmation = asked;
                    ConfirmationAsked?.Invoke(asked, _beatActive ? _beatActivity : null);
                    if (asked.Proposal && _quietProposal is { } question)
                    {
                        _quietProposal = null;
                        ProposalNotificationRequested?.Invoke(question, SilentBecause(_beatActivity), asked);
                    }
                },
                ConfirmationResolved = outcome =>
                {
                    _askedConfirmation = null;
                    ConfirmationResolved?.Invoke(outcome);
                },
                // Settings → Tools first: a tool off in the person's profile is refused as off, whatever else says.
                // ALR5 (M2): but not the stop or snooze of what rings now, which the card's buttons already ran.
                Refuse = (operation, arguments) =>
                    ToolProfileState.Refusal(operation, arguments, _ringer is { Now.Count: > 0 })
                    ?? Settings.Refusal(operation, arguments),
                OffFacts = ToolProfileState.OffFacts,
                ToolOn = operation =>
                {
                    string? off = ToolProfileState.KeepOn(operation);
                    if (off is null)
                    {
                        ToolsChangedBySpeaking();
                    }

                    return off;
                },
                BrakeOn = Settings.BrakeOn,
                Front = HeartbeatMoment.PersonFront,
                OwnReading = (scope, cancellationToken) => OwnReader is { } read
                    ? read(scope, cancellationToken)
                    : Task.FromResult(Baxy.Kernel.Operations.OperationOutcome.Failure(OwnReadings.Unavailable)),
                MemoryChanged = () =>
                {
                    // MEM8 (revisión ciega 3 #3): a save or a forget makes the count read at the start stale: not known.
                    ToolProfileState.MemoryRecords = null;
                    MemoryChanged?.Invoke();
                },
                MemorySwitched = MemorySwitched,
                MemoryOff = () => ToolProfileState.MemoryOff,
                MemoryRecords = () => ToolProfileState.MemoryRecords,
                InProfile = ToolProfileState.InProfile,
                ForgotEverything = () =>
                {
                    ClearLogAndCaptures();
                    EverythingForgotten?.Invoke();
                },
                Conversation = (operation, arguments) => Conversation?.Invoke(operation, arguments),
                Windows = HeartbeatMoment.OtherWindows,
                Rows = VisibleRows.Read,
                Ringing = RingingNote,
                Routines = RoutinesNote,
            });
    }

    // RUT1: the person's routines for the turn (documentacion/RUTINAS.md §5), read from baxy.routines' store; one that
    // cannot be read is none, and the model's own baxy.routines call says why.
    private static JsonArray? RoutinesNote()
    {
        try
        {
            IReadOnlyList<JsonObject> kept = new LocalRoutineStore(
                Path.Combine(MemoryOperationProtector.ResolveDataRoot(), LocalRoutineStore.FolderName)).Read();
            return kept.Count == 0 ? null : new JsonArray([.. kept]);
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException or InvalidDataException)
        {
            return null;
        }
    }

    /// <summary>An alarm or a reminder this App rings started, changed or ended (the view's card).</summary>
    internal event Action<RingNow>? RingChanged;

    /// <summary>RUT4: BAXY said a routine's text at its time; false when its voice was off or not there, and the
    /// conversation's line is all there was.</summary>
    internal event Action<RingNow, bool>? RoutineSaid;

    /// <summary>What this App rings now (the view's cards when it opens).</summary>
    internal IReadOnlyList<RingNow> Ringing => _ringer?.Now ?? [];

    /// <summary>
    /// ALR1: from now on this App rings the alarms and reminders of its data root (<see cref="AlarmRinger"/>): their
    /// tone on Windows' default output, its voice saying their words unless the owner silenced it, and their card. Only
    /// the real window starts it, once: another instance of the view model (a test, the conductor) never takes them.
    /// </summary>
    internal void StartRinging()
    {
        if (_ringer is not null || _isDisposed)
        {
            return;
        }

        string dataRoot = MemoryOperationProtector.ResolveDataRoot();
        var ringer = new AlarmRinger(
            AlarmRingHandoff.Folder(dataRoot),
            new RingOutput(
                RingTone.Play,
                RingTone.Stop,
                words =>
                {
                    if (!Settings.VoiceMuted && _mindClient is { IsVoiceAvailable: true } mind)
                    {
                        UnhandledFailures.Watch(
                            mind.VoiceSpeakAsync(words, TimeSpan.FromSeconds(5), CancellationToken.None), "ring.voice");
                    }
                },
                () => IsVoiceSpeaking,
                RingToast.RingInWindows),
            // The person speaks to BAXY («Baxy» heard, a dictation) or their turn runs: the ring waits.
            () => _voiceRequestOpen || IsListening || IsBusy,
            () => UiLanguage.IsEnglish,
            // INS1 (PRV-2): the one-time rings that rang leave the Task Scheduler.
            spent: () => _ = RemoveSpentRingsAsync(dataRoot),
            // APP1 (ALR-1): what the ring went on after is kept in the profile's diagnostics and in the trace.
            failed: static failure =>
            {
                ShellTraceSink.Record(ShellTraceScopes.Startup, "ring", "ring_tick_failed", failure.GetType().Name);
                UnhandledFailures.Record("ring", failure);
            });
        try
        {
            ringer.Start();
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            // The data root cannot be written: the ring scripts ring Windows' notification, as before.
            ringer.Dispose();
            return;
        }

        _ringer = ringer;
        ringer.Changed += ring => RingChanged?.Invoke(ring);
        // The same test the ring's voice makes (RingOutput.Say above), on the same thread, right after it spoke.
        ringer.Said += say => RoutineSaid?.Invoke(say, !Settings.VoiceMuted && _mindClient is { IsVoiceAvailable: true });
        // The loop ends only with the App: whatever a tick throws is kept and the next one goes on (AlarmRinger.RunAsync).
        _ = ringer.RunAsync(TimeSpan.FromMilliseconds(500), static () => DateTimeOffset.UtcNow, _mindLifetimeCancellation.Token);
    }

    /// <summary>How long after a ring ends its task is looked at: the ring script that handed it over has ended by
    /// then (it looks every 250 ms for the App to have taken it, writes its receipt and exits).</summary>
    private static readonly TimeSpan SpentRingWait = TimeSpan.FromSeconds(5);

    // PRV-2: the one-time alarms and reminders that rang leave Windows' Task Scheduler (ScheduledRingsRemoval), off the
    // interface thread. One the scheduler would not let go stays recorded, and the next ring that ends or the next
    // start asks again.
    private async Task RemoveSpentRingsAsync(string dataRoot)
    {
        try
        {
            await Task.Delay(SpentRingWait, _mindLifetimeCancellation.Token).ConfigureAwait(false);
            await Task.Run(() => ScheduledRingsRemoval.RemoveSpent(dataRoot), _mindLifetimeCancellation.Token)
                .ConfigureAwait(false);
        }
        catch (OperationCanceledException)
        {
            // The App closes.
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            ShellTraceSink.Record(ShellTraceScopes.Startup, "ring", "ring_spent_removal_failed", exception.GetType().Name);
        }
    }

    /// <summary>The card's Stop or Snooze: schedule.alarms through the kernel, as the model's call.</summary>
    internal Task<OperationResponse?> AnswerRingAsync(string id, string action, CancellationToken cancellationToken) =>
        SendPanelOperationAsync("schedule.alarms", new JsonObject { ["action"] = action, ["id"] = id },
            cancellationToken);

    // What rings now, for the turn's note: its id (the one schedule.alarms stop and snooze take), kind, words and time.
    private JsonArray? RingingNote()
    {
        if (_ringer is not { } ringer || ringer.Now.Count == 0)
        {
            return null;
        }

        var ringing = new JsonArray();
        foreach (RingNow ring in ringer.Now)
        {
            var item = new JsonObject { ["id"] = ring.Id, ["kind"] = ring.Kind, ["clock"] = ring.Clock };
            if (ring.Title is not null)
            {
                item["title"] = ring.Title;
            }

            ringing.Add(item);
        }

        return ringing;
    }

    /// <summary>What the owner chose in the view's Settings and Proposals panels.</summary>
    internal FieldSettings Settings { get; } = FieldSettings.CreateDefault();

    /// <summary>assistant.status by its scope, read from what the view is shown (FieldProductChannel sets it).</summary>
    internal Func<string, CancellationToken, Task<Baxy.Kernel.Operations.OperationOutcome>>? OwnReader { get; set; }

    /// <summary>A call is about to run (the view's chip in progress).</summary>
    internal event Action<string, string, JsonObject>? StepStarted;

    /// <summary>A call waits for the person's Sí or No; the second value is the heartbeat's reading of the person
    /// when the call is its proposal.</summary>
    internal event Action<NativeTurnConfirmation, string?>? ConfirmationAsked;

    internal event Action<string>? ConfirmationResolved;

    /// <summary>A heartbeat's proposal for a person who should not be spoken to: the model's question, why it is not
    /// said aloud (the Windows notification with Sí / No) and the call it asks about, which its answer names.</summary>
    internal event Action<string, string, NativeTurnConfirmation>? ProposalNotificationRequested;

    /// <summary>What the ear has heard of the request so far (live captions); it starts nothing.</summary>
    internal event Action<string>? VoicePartial;

    /// <summary>The voice's loudness for the mouth (owner, 2026-10-21: the avatar's speaking animation ended while
    /// BAXY still spoke): a take's levels every <c>step</c> ms from the wall-clock <c>t0</c> it sounds at, or
    /// <c>stop</c>, when the sound was cut. Presentation only.</summary>
    internal event Action<JsonObject>? VoiceLip;

    /// <summary>«Baxy» was heard.</summary>
    internal event Action? VoiceWake;

    /// <summary>Active (true) or resting: at rest nothing listens and the heartbeat waits.</summary>
    public bool IsPowered
    {
        get => _isPowered;
        private set => SetField(ref _isPowered, value);
    }

    /// <summary>The start's pieces as the mind reported them (null until it says), and when the model started and was ready.</summary>
    internal MindVoiceStatus? VoicePieces => _voicePieces;

    /// <summary>V132: why this start's ear has no wake word although the installation names one (MindRuntimeDiscovery.WakeProblem).</summary>
    internal string? WakeProblem { get; set; }

    internal int? MindProcessId => _mindClient?.ProcessId;

    internal DateTimeOffset MindStartedAt => _mindStartedAt;

    internal DateTimeOffset? MindReadyAt => _mindReadyAt;

    /// <summary>The mind did not start and none is on its way (a relaunch that waits is still coming: uso 95).</summary>
    internal bool MindFailed => _mindStartupState is MindStartupState.Failed or MindStartupState.NotConfigured
        && !IsMindPreparing;

    /// <summary>Uso 95 (F9): why the last start of the mind failed while none is up: <c>ram_insuficiente</c>,
    /// <c>vram_insuficiente</c> or <c>memoria_insuficiente</c> when the model server's log said it ran out of memory
    /// (llm_server.memory_failure), else the start's own label; null once a mind is up.</summary>
    internal string? MindFailureCause => IsMindReady ? null : _mindFailureCause;

    /// <summary>uso-116 (N23): the figures of that lack of memory, when the mind knows them: the buffer that did not fit
    /// and the PC's RAM free (<see cref="MindStartupFailure"/>); null otherwise.</summary>
    internal (long NeedMb, long? FreeMb)? MindFailureMemory => IsMindReady ? null : _mindFailureMemory;

    /// <summary>N9 (L5): the figures of a read too slow, when the mind has them: its pace and what the whole prefix would
    /// take (<see cref="MindStartupFailure"/>); null otherwise.</summary>
    internal (long TokensPerS, long NeedMinutes, MindCardFull? CardFull)? MindFailureRead => IsMindReady ? null : _mindFailureRead;

    /// <summary>N9 (L5): how far the model being started has read its prefix; null when it is not reading one.</summary>
    internal MindModelReading? MindReading => _mindStartupState == MindStartupState.Starting ? _mindReading : null;

    /// <summary>N9 (L5): the mind said the processor computes its model, with no GPU its server can use.</summary>
    internal bool MindOnProcessor => _mindOnProcessor;

    /// <summary>Uso 95 (F9): a message of the person's waits for the mind to come up (it starts or is relaunched).</summary>
    internal bool IsAwaitingMind => Volatile.Read(ref _awaitingMind) > 0;

    private static string SilentBecause(string activity) => activity switch
    {
        HeartbeatMoment.Playing => UiLanguage.Say("estás jugando", "gaming"),
        HeartbeatMoment.InCall => UiLanguage.Say("estás en una llamada", "on a call"),
        HeartbeatMoment.Watching => UiLanguage.Say("estás viendo algo", "watching something"),
        HeartbeatMoment.Away => UiLanguage.Say("no estabas", "away"),
        _ => UiLanguage.Say("aviso en pantalla", "on-screen notice"),
    };

    public event PropertyChangedEventHandler? PropertyChanged;

    public event Action<ConversationMessage>? MessageAdded;

    /// <summary>Each call the model made in a turn and what came of it (trace, conductor capture).</summary>
    internal event Action<NativeTurnStep>? StepCompleted;

    /// <summary>The chat changed what the memory holds (the interface reads its count again).</summary>
    internal event Action? MemoryChanged;

    /// <summary>The chat forgot everything memory held (the kept conversations go too).</summary>
    internal event Action? EverythingForgotten;

    /// <summary>A turn of the person's ended; true when a call in it reached its provider (the heartbeat's pace).</summary>
    internal event Action<bool>? PersonTurnEnded;

    /// <summary>A heartbeat's words for a person who is playing, in a call, watching or away: shown, not spoken.</summary>
    internal event Action<string>? NotificationRequested;

    /// <summary>
    /// The voice accepted the mind's notice of a silent turn (<see cref="SilenceNotice"/>) into its queue: it sounds
    /// after what the voice already holds, or not at all if the voice drops it. It is not a message.
    /// </summary>
    internal event Action<string>? NoticeQueued;

    /// <summary>
    /// Renew al máximo: an utterance's first sound, as the voice tells it: the notice's phrase when the voice says it is
    /// the notice, null when it is an answer. The conductor names what is said from it; the order of
    /// <see cref="NoticeQueued"/> and <see cref="IsVoiceSpeaking"/> does not tell it (the notice sounds before its
    /// acceptance arrives).
    /// </summary>
    internal event Action<string?>? VoiceSounded;

    public ObservableCollection<ConversationMessage> Messages { get; }

    /// <summary>The engine and the private-memory sealing the interface's memory panel uses, the same the chat uses.</summary>
    internal CoreProcessClient? CoreClient => _coreClient;

    internal MemoryOperationProtector? MemoryProtector => _memoryProtector;

    /// <summary>
    /// Why the last turn ended without an answer from the model (mind_unavailable, decision_unavailable). Each turn starts
    /// it empty, so a turn that fails sets it once, and that sounds <see cref="Chime.TurnFailed"/> unless the owner
    /// silenced BAXY's voice; a turn that answers or that was cancelled leaves it empty and sounds nothing.
    /// </summary>
    internal string? LastTurnFailure
    {
        get => _lastTurnFailure;
        private set
        {
            bool failed = _lastTurnFailure is null && value is not null;
            if (SetField(ref _lastTurnFailure, value))
            {
                OnPropertyChanged(nameof(Failure));
                if (failed)
                {
                    SoundUnlessMuted(Chime.TurnFailed);
                }
            }
        }
    }

    /// <summary>How the App plays its <see cref="Chime"/>s; the App's tests record them or keep quiet.</summary>
    internal Action<Chime> Sound { get; init; } = static chime => chime.Play();

    // A chime is heard unless the owner silenced BAXY's voice («Silenciar su voz»).
    private void SoundUnlessMuted(Chime chime)
    {
        if (!Settings.VoiceMuted)
        {
            Sound(chime);
        }
    }

    /// <summary>
    /// The ear's two sounds, Amazon's Start and End of Request (Alexa Auto, «Invoking Alexa»: right after the wake word,
    /// and when the microphone closes, both under one setting): <see cref="Chime.Wake"/> for «Baxy» heard and
    /// <see cref="Chime.Heard"/> when the request closes (transcribing), under the person's «Sonido al despertar» and
    /// BAXY's silenced voice. Played on the mind's reader as its event arrives (uso real 03-11: the wake sound came late):
    /// they used to wait for the interface's thread, behind whatever it ran and the view's own updates of that event.
    /// </summary>
    private void SoundTheEar(string eventName)
    {
        Chime? chime = eventName switch
        {
            "wake_detected" => Chime.Wake,
            "transcribing" => Chime.Heard,
            _ => null,
        };
        if (chime is not null && !Volatile.Read(ref _isDisposed) && Settings.WakeSound)
        {
            SoundUnlessMuted(chime);
        }
    }

    /// <summary>What the interface shows as the failure: the engine's (retry_without_close, core_disconnected,
    /// <see cref="ProfileUnreadable"/>, <see cref="NoSupportedGpu"/>, <see cref="EngineUnavailable"/>), else the last turn's.</summary>
    internal string? Failure => _startupFailure ?? (_noSupportedGpu ? NoSupportedGpu : null)
        ?? (_mindGaveUp ? EngineUnavailable : null) ?? _lastTurnFailure;

    /// <summary>Uso 85: the core cannot read or authenticate the data profile (CoreExitCodes.ProfileUnreadable). Nothing
    /// is relaunched: the interface asks the person to start a new profile (the old one set aside) or to leave.</summary>
    internal const string ProfileUnreadable = "profile_unreadable";

    /// <summary>Uso 85: the core or the mind failed the same way too often (<see cref="StartupRetries"/>). Nothing is
    /// relaunched until the person asks for it (<see cref="RetryEngine"/>).</summary>
    internal const string EngineUnavailable = "engine_unavailable";

    /// <summary>uso-101: a store's package found no GPU it has a server for (MindRuntimeDiscovery). Trying again changes
    /// nothing until the person installs a driver or a GPU, so nothing is relaunched and the interface says the cause.</summary>
    internal const string NoSupportedGpu = "no_supported_gpu";

    /// <summary>The runtime found for this start, in the environment the mind inherits; false when there is none.</summary>
    internal bool ApplyMindRuntime(MindRuntimeDiscoveryResult discovery)
    {
        SetField(ref _noSupportedGpu, discovery.NoSupportedGpu, nameof(Failure));
        if (MindRuntimeDiscovery.ApplyVerified(discovery) && MindSidecarClient.IsConfigured)
        {
            WakeProblem = MindRuntimeDiscovery.WakeProblem(discovery);
            return true;
        }

        _mindStartupState = MindStartupState.NotConfigured;
        return false;
    }

    /// <summary>
    /// The voice's last trouble, until it hears again: voice_dropped_busy (a transcript that arrived while a turn ran
    /// started nothing; each one sounds <see cref="Chime.Wait"/>), voice_error (the mind's listener failed on a block or
    /// the microphone sent nothing; <see cref="Chime.ListenFailed"/> once while the person speaks) or wake_unavailable
    /// (the wake word asked for, at start or by the person, did not start).
    /// </summary>
    internal string? VoiceFailure
    {
        get => _voiceFailure;
        private set => SetField(ref _voiceFailure, value);
    }

    /// <summary>A risky call waits for the person's Sí or No (the interface shows the two buttons).</summary>
    public bool HasPendingConfirmation => _loop.HasPendingConfirmation;


    public string StatusDescription
    {
        get => _statusDescription;
        private set => SetField(ref _statusDescription, value);
    }

    public bool IsReady
    {
        get => _isReady;
        private set
        {
            if (SetField(ref _isReady, value))
            {
                OnPropertyChanged(nameof(IsInputEnabled));
            }
        }
    }

    public bool IsBusy
    {
        get => _isBusy;
        private set
        {
            if (SetField(ref _isBusy, value))
            {
                OnPropertyChanged(nameof(IsInputEnabled));
            }
        }
    }

    public bool HasStartupError => _startupFailure is not null;

    // The engine could not start or went away: its code is the shell's status and the interface's failure.
    private void SetStartupFailure(string? code)
    {
        if (SetField(ref _startupFailure, code, nameof(HasStartupError)))
        {
            OnPropertyChanged(nameof(Failure));
        }

        if (code is not null)
        {
            StatusDescription = code;
        }
    }

    public bool IsInputEnabled => IsReady && !IsBusy;



    public bool IsMindReady => _mindClient is { IsReady: true };

    /// <summary>BAXY's answers are said aloud (the mind offers its voice).</summary>
    internal bool CanSpeak => _mindClient is { IsVoiceAvailable: true };

    /// <summary>The shell opened while the mind it started is still reading its model.</summary>
    /// <summary>The mind is on its way: the shell's first start reads its model, a start is under way, or a relaunch
    /// after a failed start or a lost mind waits its turn (uso 95). Not once it gave up (<see cref="EngineUnavailable"/>)
    /// or when it is not configured.</summary>
    public bool IsMindPreparing => !_isDisposed && _mindClient is not { IsReady: true }
        && (_startupMindPending || _mindStartupState == MindStartupState.Starting
            || (_mindStartupState == MindStartupState.Failed && _mindRetryPending && !_mindGaveUp)
            // API1: a change of the model cut the start under way, and the switch starts the next one.
            || _externalModel is { Switching: true });

    /// <summary>
    /// Uso 95 (F9, uso real 2026-11-04 12:06): the mind a person's turn talks with. While it is on its way
    /// (<see cref="IsMindPreparing"/>) the turn waits for it, said to the view as a state (<see cref="IsAwaitingMind"/>),
    /// instead of ending at once as «mind_unavailable» and being lost: a «hola» written between two relaunches got no
    /// answer when the mind came up a minute later. Null when no mind is coming (it gave up, it is not configured).
    /// </summary>
    internal async Task<MindSidecarClient?> MindForTurnAsync(CancellationToken cancellationToken)
    {
        bool waiting = false;
        try
        {
            while (true)
            {
                // Read before the state: a change after this read completes the task this wait holds.
                Task changed = Volatile.Read(ref _mindChanged).Task;
                if (_mindClient is { IsTurnAvailable: true } mind)
                {
                    return mind;
                }

                if (!IsMindPreparing)
                {
                    return null;
                }

                if (!waiting)
                {
                    waiting = true;
                    Interlocked.Increment(ref _awaitingMind);
                    OnPropertyChanged(nameof(IsAwaitingMind));
                }

                await changed.WaitAsync(cancellationToken);
            }
        }
        finally
        {
            if (waiting)
            {
                Interlocked.Decrement(ref _awaitingMind);
                OnPropertyChanged(nameof(IsAwaitingMind));
            }
        }
    }

    // The mind's state changed (up, failed, a relaunch scheduled or started, gave up): a waiting turn looks again, and
    // the view is told whether the mind is still on its way.
    private void MindChanged()
    {
        Interlocked.Exchange(ref _mindChanged,
            new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously)).TrySetResult();
        OnPropertyChanged(nameof(IsMindPreparing));
    }

    public bool IsListening
    {
        get => _isListening;
        private set => SetField(ref _isListening, value);
    }

    public bool IsWakeListening
    {
        get => _isWakeListening;
        private set => SetField(ref _isWakeListening, value);
    }

    public bool IsVoiceSpeaking
    {
        get => _isVoiceSpeaking;
        private set => SetField(ref _isVoiceSpeaking, value);
    }

    public bool IsMicAvailable
    {
        get => _isMicAvailable;
        private set => SetField(ref _isMicAvailable, value);
    }

    public Task InitializeAsync(CancellationToken cancellationToken) =>
        InitializeAsync(recovering: false, cancellationToken);

    private async Task InitializeAsync(bool recovering, CancellationToken cancellationToken)
    {
        ObjectDisposedException.ThrowIf(_isDisposed, this);
        if (_isInitializing || IsReady)
        {
            return;
        }

        _isInitializing = true;
        SetStartupFailure(null);
        IsReady = false;
        StatusDescription = "Comprobando BAXY";
        // An engine started again (recovering) is the same session: a call it never answered keeps its invocation.
        _loop.Reset(engineRestarted: recovering);

        if (_coreClient is not null)
        {
            DetachCoreDisconnectedHandler(_coreClient);
            await _coreClient.DisposeAsync();
        }

        var client = new CoreProcessClient();
        Volatile.Write(ref _coreDisconnectObserved, 0);
        Action disconnectedHandler = () => OnCoreDisconnected(client);
        _coreDisconnectedHandler = disconnectedHandler;
        client.Disconnected += disconnectedHandler;
        client.ApplicationCatalogChanged += catalog => _ = SendMindApplicationCatalogAsync(client, catalog);
        _coreClient = client;
        TaskCompletionSource<MindStartupCatalog>? startupCatalog = null;
        using var startupMindAbandoned = new CancellationTokenSource();

        try
        {
            _memoryProtector ??= MemoryOperationProtector.CreateDefault(_memorySessionId);
            if (!recovering || _retryableOperations is null)
            {
                // A call of an earlier session is never resumed or retried by itself: the person's consent and the
                // screen it was decided on belong to that session.
                _retryableOperations = new RetryableOperationRegistry();
            }

            // Entrega 1.1.0: the registered runtime completes the environment before the core starts, which only
            // inherits it: the click's vision (BAXY_VISION_*) is pointed at the projector the registration names.
            // The files' hashes are kept between starts (RuntimeFileHashCache); the mind's start verifies it again.
            if (_mindClient is not { IsReady: true })
            {
                MarkStartupMindPending();
            }

            await Task.Run(
                static () => MindRuntimeDiscovery.ApplyVerified(MindRuntimeDiscovery.DiscoverVerified()),
                cancellationToken);
            if (_mindClient is not { IsReady: true })
            {
                // The mind's process and model start beside the core's hello; only its catalog waits for the core.
                startupCatalog = new TaskCompletionSource<MindStartupCatalog>(
                    TaskCreationOptions.RunContinuationsAsynchronously);
                _startupMindPending = true;
                OnPropertyChanged(nameof(IsMindPreparing));
                _mindInitializationTask = InitializeMindAsync(
                    startupCatalog.Task, startupMindAbandoned.Token, cancellationToken);
            }

            await client.StartAsync(CoreStartupBudget.HelloTimeout, cancellationToken);
            if (!client.IsReady || Volatile.Read(ref _coreDisconnectObserved) != 0)
            {
                throw new IOException("El motor local se desconectó durante el arranque.");
            }

            ShellTraceSink.Record(ShellTraceScopes.Startup, "boot", ShellTraceStages.StartupCoreReady);
            // MEM3: the memory's switch is read before the mind takes its catalog, so it starts with the tools that
            // switch leaves (ToolProfile.MemoryOff) instead of being relaunched for it.
            (bool memoryOn, int? kept) = await InitializeMemorySessionAsync(client, _memoryProtector, cancellationToken);
            ToolProfileState.MemoryOff = !memoryOn;
            ToolProfileState.MemoryRecords = kept;
            startupCatalog?.TrySetResult(new MindStartupCatalog(
                client.Capabilities,
                client.ApplicationCatalog,
                client.GameCatalog));
            if (!client.IsReady || Volatile.Read(ref _coreDisconnectObserved) != 0)
            {
                throw new IOException("El motor local se desconectó al iniciar la memoria privada.");
            }

            IsReady = true;
            _coreRetries.Up(DateTimeOffset.UtcNow);
            StatusDescription = _startupMindPending ? "Preparando BAXY" : IdleStatus();
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            throw;
        }
        catch (Exception exception) when (IsExpectedStartupFailure(exception))
        {
            ShellTraceSink.Record(ShellTraceScopes.Startup, "boot", ShellTraceStages.StartupFailed,
                $"{exception.GetType().Name}.{exception.TargetSite?.Name ?? "unknown"}".ToLowerInvariant());
            await HandleStartupFailureAsync(client, exception);
        }
        finally
        {
            // A core that never said hello hands the mind no catalog: its start ends without it.
            if (startupCatalog?.TrySetCanceled(CancellationToken.None) == true)
            {
                await startupMindAbandoned.CancelAsync();
            }

            if (startupCatalog is null && _startupMindPending)
            {
                // The check of the runtime failed or was cancelled before any start of the mind: none is on its way.
                _startupMindPending = false;
                OnPropertyChanged(nameof(IsMindPreparing));
            }

            _isInitializing = false;
        }
    }

    /// <summary>
    /// W1 (REL4, 1.2.x and 1.3.0): the shell's first start checks the runtime's files (DiscoverVerified, ~25 s without
    /// their hash cache) before it starts the mind. That wait is the mind on its way, with its seconds counted from here;
    /// it was told as «the model isn't available» because nothing had been tried yet.
    /// </summary>
    internal void MarkStartupMindPending()
    {
        _mindStartedAt = DateTimeOffset.UtcNow;
        _startupMindPending = true;
        OnPropertyChanged(nameof(MindStartedAt));
        OnPropertyChanged(nameof(IsMindPreparing));
    }


    /// <summary>
    /// The person's words (typed, transcribed or sent by the conductor) open a turn. <paramref name="arrivedAt"/> is when
    /// they arrived (<see cref="System.Diagnostics.Stopwatch.GetTimestamp"/>), before any wait for the turn (a heartbeat
    /// holds it): the notice of a silent turn counts from then.
    /// </summary>
    internal async Task SubmitAsync(MissionInput input, long arrivedAt, CancellationToken cancellationToken)
    {
        if (!IsInputEnabled || _coreClient is null)
        {
            return;
        }

        string text = MissionInputContract.ValidateAndTrim(input);
        // Secrets the person typed never enter the transcript, the conversation log or the voice.
        string visible = SensitiveText.Contains(text) ? SensitiveText.Hidden : text;
        _beatInterrupt?.Cancel();
        await RunTurnAsync(visible, () => _loop.RunAsync(text, arrivedAt, cancellationToken), cancellationToken);
    }

    /// <summary>
    /// The person pressed Sí (<paramref name="approve"/>) or No on the pending confirmation; the press arrived at
    /// <paramref name="arrivedAt"/>, as in <see cref="SubmitAsync"/>. <paramref name="answering"/> is the call whose card
    /// or toast they pressed, when the press says it. 2026-10-22, review of the App: false when the answer was not taken
    /// (a turn runs, nothing waits, or the press was on another call's card: a late click on one approved the next), so
    /// the caller says so instead of reporting it done.
    /// </summary>
    internal async Task<bool> AnswerConfirmationAsync(bool approve, long arrivedAt, CancellationToken cancellationToken,
        NativeTurnConfirmation? answering = null)
    {
        if (!IsInputEnabled || !_loop.HasPendingConfirmation
            || (answering is not null && !ReferenceEquals(answering, _askedConfirmation)))
        {
            return false;
        }

        string label = approve ? "Sí" : "No";
        // Revisión de calidad (2026-10-25): a new or opened conversation holds the turn without being busy, and the press
        // waited for it; the call it answers is asked again once the turn is this press's (Reset dropped it).
        return await RunTurnAsync(label, () => _loop.AnswerConfirmationAsync(approve, label, arrivedAt, cancellationToken),
            cancellationToken,
            () => _loop.HasPendingConfirmation
                && (answering is null || ReferenceEquals(answering, _askedConfirmation)));
    }

    /// <summary>Whether a heartbeat may run now: everything is up and nothing holds the turn or waits for the person.</summary>
    internal bool CanBeat => IsReady && IsMindReady && !IsBusy && !_beatActive && !_loop.HasPendingConfirmation
        && IsPowered && Settings.QuietUntil is null;

    /// <summary>Rest (off) stops listening and holds the heartbeat; active (on) lets them run again (the view turns its
    /// microphone mode back on).</summary>
    internal async Task<bool> SetPowerAsync(bool on, CancellationToken cancellationToken)
    {
        if (!on && !await SetWakeVoiceAsync(false, cancellationToken))
        {
            return IsPowered;
        }

        IsPowered = on;
        return on;
    }

    /// <summary>The session's conversation as the mind holds it, to keep with the session the view shows.</summary>
    internal async Task<JsonArray?> ExportMindSessionAsync(CancellationToken cancellationToken) =>
        _mindClient is { IsReady: true } mind ? await mind.SessionExportAsync(cancellationToken) : null;

    /// <summary>The model's name for a conversation that closed (its mind conversation as exported), or null. Only a model on
    /// this PC names it (INT17, revisión ciega): by API the whole conversation would go to the company to be named, also one
    /// the person had only on this PC (opened from the history, or before switching); it then keeps its first words.</summary>
    internal async Task<string?> TitleMindSessionAsync(JsonArray conversation, CancellationToken cancellationToken) =>
        _mindClient is { IsReady: true } mind && (!ExternalModel.Available || ExternalModelState.ThinksOnThisPc)
            ? await mind.SessionTitleAsync(conversation, cancellationToken)
            : null;

    /// <summary>Auditoría de la mente (2026-10-23): memory forgot everything or every conversation was deleted, and the
    /// mind's trace (%LOCALAPPDATA%\BAXY\renew\turns.jsonl) kept the person's words in clear text: it goes too, with
    /// what the mind set aside (trace.forget). Whether the mind said none is left; a mind that is not up keeps it.</summary>
    internal async Task<bool> ForgetMindTraceAsync(CancellationToken cancellationToken)
    {
        try
        {
            return _mindClient is { IsReady: true } mind && await mind.TraceForgetAsync(cancellationToken);
        }
        catch (OperationCanceledException)
        {
            return false;
        }
    }

    /// <summary>Opens a kept session: nothing pending survives, the mind gets its conversation back and the transcript
    /// the heartbeat reads is that session's words.</summary>
    internal async Task<bool> OpenSessionAsync(JsonArray? mindConversation,
        IReadOnlyList<ConversationMessage> messages, CancellationToken cancellationToken)
    {
        // 2026-10-22, review of the App: the opening holds the turn while the mind loads the session; a person's turn
        // sent meanwhile ran across it (its words cleared with the old conversation) and a heartbeat could start.
        if (IsBusy || _mindClient is not { IsReady: true } mind || !_turnGate.Wait(0, CancellationToken.None))
        {
            return false;
        }

        try
        {
            bool loaded = mindConversation is { Count: > 0 }
                ? await mind.SessionLoadAsync(mindConversation, cancellationToken)
                : await mind.NewSessionAsync(cancellationToken);
            if (!loaded)
            {
                return false;
            }

            _loop.Reset();
            Messages.Clear();
            foreach (ConversationMessage message in messages)
            {
                Messages.Add(message);
            }

            OnPropertyChanged(nameof(HasPendingConfirmation));
            StatusDescription = IdleStatus();
            return true;
        }
        finally
        {
            _turnGate.Release();
        }
    }

    /// <summary>The mind's conversation of the session the view shows, as the view's channel last kept it, or null: what
    /// a mind that starts is given back.</summary>
    internal Func<JsonArray?>? KeptConversation { get; set; }

    /// <summary>Runs a conversation.* call of the person's turn on the conversations the view's channel keeps
    /// (NativeTurnLoop.Host.Conversation): its result as the model reads it.</summary>
    internal Func<string, JsonObject, string?>? Conversation { get; set; }

    /// <summary>A person's turn ended and let the turn go: what waited for it (a conversation to open) can run now.</summary>
    internal event Action? TurnReleased;

    /// <summary>What the heartbeat last saw the person doing (libre, jugando, llamada, viendo, ausente…).</summary>
    internal string OwnerActivity { get; private set; } = string.Empty;

    internal void ReportActivity(string activity)
    {
        if (OwnerActivity != activity)
        {
            OwnerActivity = activity;
            OnPropertyChanged(nameof(OwnerActivity));
        }
    }

    /// <summary>
    /// A panel of the view runs the chat's own catalog operation (the triggers panel: schedule.alarms), through the
    /// kernel like any call, never around it; null when the engine is not ready or did not answer.
    /// </summary>
    internal async Task<OperationResponse?> SendPanelOperationAsync(string operation,
        JsonObject arguments, CancellationToken cancellationToken)
    {
        if (_coreClient is not { IsReady: true } core || _retryableOperations is not { } registry)
        {
            return null;
        }

        PreparedOperation prepared = registry.GetOrAdd(new RoutedOperation(operation, arguments));
        try
        {
            return await core.SendOperationAsync(prepared, TimeSpan.FromSeconds(15), cancellationToken);
        }
        catch (Exception exception) when (exception is TimeoutException or IOException or InvalidOperationException)
        {
            return null;
        }
        finally
        {
            registry.MarkResolved(prepared);
        }
    }

    /// <summary>Push-to-talk let go.</summary>
    internal async Task<bool> ReleaseDirectVoiceAsync(CancellationToken cancellationToken) =>
        _mindClient is { IsReady: true } mind && await mind.VoiceReleaseAsync(TimeSpan.FromSeconds(5), cancellationToken);

    /// <summary>One heartbeat with the moment observed; <paramref name="speak"/>: its words may be said aloud.</summary>
    internal async Task RunBeatAsync(JsonObject moment, bool speak, CancellationToken cancellationToken)
    {
        if (!_turnGate.Wait(0, cancellationToken))
        {
            return;
        }

        string turnTraceId = "b" + Interlocked.Increment(ref _turnTraceSequence).ToString(CultureInfo.InvariantCulture);
        ShellTraceSink.TurnId = turnTraceId;
        ShellTraceSink.Record(ShellTraceScopes.Turn, turnTraceId, "beat.start", speak ? "voz" : "notificacion");
        _beatActive = true;
        _beatSpeaks = speak;
        _beatActivity = (string?)moment["owner_activity"] ?? string.Empty;
        // Not disposed: the person's words may cancel it from another thread as the beat ends; it holds no timer.
        _beatInterrupt = new CancellationTokenSource();
        try
        {
            await _loop.RunBeatAsync(moment, cancellationToken, _beatInterrupt.Token);
        }
        finally
        {
            _beatInterrupt = null;
            _beatActive = false;
            ClearCapturesNoCallWaitsFor();
            _turnGate.Release();
            OnPropertyChanged(nameof(HasPendingConfirmation));
            ShellTraceSink.Record(ShellTraceScopes.Turn, turnTraceId, "beat.end");
        }
    }

    // stillAsked: what the turn answers still holds once the turn is its own; false when it no longer does (nothing ran).
    private async Task<bool> RunTurnAsync(string visibleUserText, Func<Task> turn, CancellationToken cancellationToken,
        Func<bool>? stillAsked = null)
    {
        // Ronda final 41 (regla: doble pulsación): a turn waiting for a heartbeat to end is already busy, so a second
        // Enter (nothing visible had happened yet) is refused instead of queued to run the same request twice.
        // Ronda final 42: whatever throws (the wait cancelled, a view handler before the turn's own try), the turn ends
        // not busy and the gate is released only when it was taken.
        bool entered = false;
        try
        {
            IsBusy = true;
            await _turnGate.WaitAsync(cancellationToken);
            entered = true;
            if (stillAsked?.Invoke() == false)
            {
                return false;
            }

            await RunGatedTurnAsync(visibleUserText, turn, cancellationToken);
            return true;
        }
        finally
        {
            if (entered)
            {
                _turnGate.Release();
            }

            IsBusy = false;
            if (entered)
            {
                TurnReleased?.Invoke();
            }
        }
    }

    private async Task RunGatedTurnAsync(string visibleUserText, Func<Task> turn, CancellationToken cancellationToken)
    {
        string turnTraceId = "t" + Interlocked.Increment(ref _turnTraceSequence).ToString(CultureInfo.InvariantCulture);
        ShellTraceSink.TurnId = turnTraceId;
        ShellTraceSink.Record(ShellTraceScopes.Turn, turnTraceId, ShellTraceStages.QueueWaitEnd);
        AddMessageCore("Tú", visibleUserText, isUser: true);
        _turnExecutionActive = true;
        _personActed = false;
        LastTurnFailure = null;
        IsBusy = true;
        StatusDescription = "understanding";
        try
        {
            await turn();
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            ShellTraceSink.Record(ShellTraceScopes.Turn, turnTraceId, ShellTraceStages.TurnCancelled);
        }
        catch (Exception exception)
        {
            // Auditoría de la App (2026-10-23): any other type (a NullReference, a KeyNotFound, a cancellation that was
            // not the turn's) left the turn through the view's async void handler and ended BAXY; every failure ends
            // the turn as what it is, a failed turn, traced, and recorded with what nothing else caught.
            if (exception is not (IOException or InvalidDataException or InvalidOperationException or JsonException
                or UnauthorizedAccessException or ProtectedPayloadException or TimeoutException))
            {
                UnhandledFailures.Record("turn", exception);
            }

            LastTurnFailure = "turn_failed";
            ShellTraceSink.Record(ShellTraceScopes.Turn, turnTraceId, ShellTraceStages.TurnError,
                $"{exception.GetType().Name}.{exception.TargetSite?.Name ?? "unknown"}".ToLowerInvariant());
        }
        finally
        {
            ShellTraceSink.Record(ShellTraceScopes.Turn, turnTraceId, ShellTraceStages.ResponseFinal);
            _turnExecutionActive = false;
            IsBusy = false;
            ClearCapturesNoCallWaitsFor();
            PersonTurnEnded?.Invoke(_personActed);
            OnPropertyChanged(nameof(HasPendingConfirmation));
            if (_coreRecoveryPending)
            {
                RecoverCoreWhenIdle();
            }

            if (IsReady)
            {
                StatusDescription = LastTurnFailure ?? IdleStatus();
            }
        }
    }

    private string IdleStatus() =>
        _loop.HasPendingConfirmation ? "awaiting_confirmation"
        : _mindStartupState == MindStartupState.Failed ? "mind_unavailable"
        : _noSupportedGpu ? NoSupportedGpu
        : IsWakeListening ? "Esperando «Baxy»"
        : "BAXY disponible";

    /// <summary>A new conversation: the transcript, the model's session and anything pending start over.</summary>
    /// <param name="silence">Whether BAXY's voice stops too: a new conversation asked by voice (conversation.new)
    /// starts while BAXY still says that it did.</param>
    internal async Task<bool> StartNewUiSessionAsync(CancellationToken cancellationToken, bool silence = true)
    {
        // Ronda final 33 (regla 3): not while a heartbeat holds the turn either (its line would land in the new session).
        // 2026-10-22, review of the App: it holds the turn itself while the mind starts over, and it waits for the mind:
        // a session.new that failed left the view empty and the model in the old conversation. A mind that is not up
        // has nothing to start over (the next one starts empty).
        if (IsBusy || !_turnGate.Wait(0, CancellationToken.None))
        {
            return false;
        }

        try
        {
            if (_mindClient is { IsReady: true } mind && !await mind.NewSessionAsync(cancellationToken))
            {
                return false;
            }

            _loop.Reset();
            Messages.Clear();
            if (silence)
            {
                SilenceVoice();
            }
            OnPropertyChanged(nameof(HasPendingConfirmation));
            StatusDescription = IdleStatus();
            return true;
        }
        finally
        {
            _turnGate.Release();
        }
    }

    /// <summary>
    /// What BAXY remembers of the person («label: value»), for the heartbeat's moment: the memory's own list through its
    /// sealed route. Empty when the memory is off, empty or not reachable.
    /// </summary>
    internal async Task<IReadOnlyList<string>> RememberedAsync(CancellationToken cancellationToken)
    {
        if (_coreClient is not { IsReady: true } core || _memoryProtector is not { } protector)
        {
            return [];
        }

        try
        {
            var list = new MemoryRoutedOperation("memory.list", new JsonObject
            {
                ["version"] = 1,
                ["limit"] = 20,
                ["offset"] = 0,
            });
            PreparedOperation prepared = protector.Prepare(list).Prepared;
            OperationResponse response = await core.SendOperationAsync(prepared, TimeSpan.FromSeconds(10), cancellationToken);
            if (response.Status != OperationStatuses.Completed)
            {
                return [];
            }

            using OpenedBoundProtectedJson opened = protector.OpenResult(response, prepared);
            using OpenedBoundProtectedJson arguments = protector.OpenPrivateArguments(prepared);
            if (!MemoryOperationResponseProjection.TryCreateCompleted(
                    prepared.OperationName, opened.Payload, out MemoryOperationResponseProjection? projection,
                    response.Replayed, arguments.Payload)
                || projection is null
                || JsonNode.Parse(projection.Message) is not JsonObject facts)
            {
                return [];
            }

            var remembered = new List<string>();
            Collect(facts, remembered);
            // Ronda final 20 (regla 3): the first twenty of more say so, as the reminders do.
            if ((int?)facts["observed"]?["total"] is int total && total > remembered.Count)
                remembered.Add($"y {total - remembered.Count} más sin listar");
            return remembered;
        }
        catch (Exception exception) when (exception is IOException or InvalidDataException or MemoryRequestRefusedException or JsonException
            or ProtectedPayloadException or TimeoutException or InvalidOperationException)
        {
            return [];
        }

        static void Collect(JsonNode? node, List<string> into)
        {
            switch (node)
            {
                case JsonObject record
                    when (string?)record["label"] is { } label && (string?)record["value"] is { } value:
                    into.Add($"{label}: {value}");
                    break;
                case JsonObject other:
                    foreach ((_, JsonNode? child) in other)
                    {
                        Collect(child, into);
                    }

                    break;
                case JsonArray items:
                    foreach (JsonNode? child in items)
                    {
                        Collect(child, into);
                    }

                    break;
            }
        }
    }

    /// <summary>
    /// BAXY's alarms and reminders still to ring, for the heartbeat's moment: the schedule's own list (a read).
    /// </summary>
    internal async Task<JsonArray> PendingRemindersAsync(CancellationToken cancellationToken)
    {
        var reminders = new JsonArray();
        if (_coreClient is not { IsReady: true } core || _retryableOperations is not { } registry)
        {
            return reminders;
        }

        try
        {
            PreparedOperation prepared = registry.GetOrAdd(new RoutedOperation(
                "schedule.alarms", new JsonObject { ["action"] = "list", ["limit"] = 10 }));
            OperationResponse response;
            try
            {
                response = await core.SendOperationAsync(prepared, TimeSpan.FromSeconds(10), cancellationToken);
            }
            finally
            {
                registry.MarkResolved(prepared);
            }

            if (response.Result is not { ValueKind: JsonValueKind.Object } result
                || !result.TryGetProperty("notifications", out JsonElement items)
                || items.ValueKind != JsonValueKind.Array)
            {
                return reminders;
            }

            foreach (JsonElement item in items.EnumerateArray())
            {
                reminders.Add(new JsonObject
                {
                    ["text"] = item.TryGetProperty("title", out JsonElement title) ? title.GetString() : null,
                    ["due"] = item.TryGetProperty("nextRunLocal", out JsonElement due) ? due.GetString() : null,
                });
            }

            // Ronda final 7 (regla 3): past the ten listed, the moment says how many more there are.
            if (result.TryGetProperty("count", out JsonElement count) && count.TryGetInt32(out int total)
                && total > reminders.Count)
            {
                reminders.Add(new JsonObject
                {
                    ["text"] = $"y {total - reminders.Count} más sin listar",
                    ["due"] = string.Empty,
                });
            }
        }
        catch (Exception exception) when (exception is IOException or InvalidDataException or MemoryRequestRefusedException or JsonException
            or TimeoutException or InvalidOperationException or ArgumentException)
        {
            // The moment goes without them.
        }

        return reminders;
    }

    // Whether the memory is on, as memory.status read it, and (MEM8) how many records it keeps (RecordsKept), or null.
    private static async Task<(bool On, int? Kept)> InitializeMemorySessionAsync(
        CoreProcessClient client,
        MemoryOperationProtector protector,
        CancellationToken cancellationToken)
    {
        var status = new MemoryRoutedOperation("memory.status", new JsonObject { ["version"] = 1 });
        PreparedOperation prepared = protector.Prepare(status).Prepared;
        OperationResponse response = await client.SendOperationAsync(
            prepared,
            TimeSpan.FromSeconds(20),
            cancellationToken);
        using OpenedBoundProtectedJson opened = protector.OpenResult(response, prepared);
        if (!MemoryOperationResponseProjection.TryCreateCompleted(prepared.OperationName, opened.Payload, out _))
        {
            throw new InvalidDataException("El estado privado inicial no tiene una forma válida.");
        }

        bool on = opened.Payload.TryGetProperty("enabled", out System.Text.Json.JsonElement enabled)
            && enabled.ValueKind == System.Text.Json.JsonValueKind.True;
        return (on, RecordsKept(opened.Payload));
    }

    /// <summary>MEM8: how many records memory.status says the memory keeps, all kinds (totalRecords: a session one is kept
    /// too, so only none at all is «nothing kept»), or null. MEM8C (REV20 M-5): with a temporary one among them, null: it
    /// goes when its time ends while BAXY stays open, and the count would then say one more than there is.</summary>
    internal static int? RecordsKept(System.Text.Json.JsonElement status) =>
        status.TryGetProperty("totalRecords", out System.Text.Json.JsonElement kept)
        && kept.TryGetInt32(out int count) && count >= 0
        && status.TryGetProperty("temporaryRecords", out System.Text.Json.JsonElement temporary)
        && temporary.TryGetInt32(out int passing) && passing == 0 ? count : null;

    /// <summary>MEM3: the memory's own switch changed (memory.enable / memory.disable completed, by voice or by the panel's
    /// switch): its held call goes or comes back (ToolProfile.MemoryOff), and the mind is relaunched with it once the
    /// running turn ends, as for a profile chosen by voice.</summary>
    internal void MemorySwitched(bool on)
    {
        if (ToolProfileState.MemoryOff != on)
        {
            return;
        }

        ToolProfileState.MemoryOff = !on;
        ToolsChangedBySpeaking();
    }

    // ---- voice ---------------------------------------------------------------------------------------------

    public async Task ToggleWakeVoiceAsync(CancellationToken cancellationToken) =>
        _ = await SetWakeVoiceAsync(!IsWakeListening, cancellationToken);

    /// <summary>
    /// The owner switched «Quitar lo que suena en el PC» (<see cref="FieldSettings.EchoCancel"/>): an ear waiting for
    /// «Baxy» is started again with it, so the mind opens the microphone again with or without the stage; a request
    /// being heard keeps what it began with and the next start takes the switch.
    /// </summary>
    internal async Task ApplyEchoCancelAsync(CancellationToken cancellationToken)
    {
        await _voiceCommands.WaitAsync(cancellationToken);
        try
        {
            if (IsWakeListening && !IsListening && _mindClient is { IsReady: true } mind)
            {
                IsWakeListening = await mind.VoiceStartAsync(
                    "wake", MindSidecarClient.VoiceStartTimeout, cancellationToken, Settings.EchoCancel);
            }
        }
        finally
        {
            _voiceCommands.Release();
        }
    }

    internal async Task<bool> SetWakeVoiceAsync(bool enabled, CancellationToken cancellationToken)
    {
        int command = Interlocked.Increment(ref _wakeCommands);
        Volatile.Write(ref _wakeAwaitsEar, 0);
        if (enabled)
        {
            // A wake word is a mode, not an utterance: asked for while the ear still loads, it starts once it has loaded
            // (_voiceSettled), instead of reaching a mind that holds it until then. It waits outside the gate of the voice
            // commands (revisión de nb-w11-arranque): a stop given meanwhile (rest, /voice/stop) is not held behind the
            // ear's load, however long, and the start yields to it.
            Volatile.Write(ref _personVoiceChoice, 1);
            await _voiceSettled.WaitAsync(cancellationToken);
            if (Volatile.Read(ref _wakeCommands) != command)
            {
                return IsWakeListening;
            }
        }

        await _voiceCommands.WaitAsync(cancellationToken);
        try
        {
            if (enabled && Volatile.Read(ref _wakeCommands) != command)
            {
                return IsWakeListening;
            }

            await AwaitStartupVoiceAsync();
            // Ronda final 27 (regla 3): nothing listening is already off, whatever the mind's state (a mind that ended
            // turned the flags off): stopping it is done, never «still running».
            if (!enabled && !IsListening && !IsWakeListening)
            {
                return true;
            }

            MindSidecarClient? mind = _mindClient;
            if (mind is not { IsReady: true })
            {
                return false;
            }

            if (enabled)
            {
                if (IsWakeListening)
                {
                    return true;
                }

                bool started = await mind.VoiceStartAsync("wake", MindSidecarClient.VoiceStartTimeout, cancellationToken, Settings.EchoCancel);
                IsWakeListening = started;
                if (started)
                {
                    IsMicAvailable = true;
                    IsListening = false;
                    IsVoiceSpeaking = false;
                }

                WakeStartTold(started);
                StatusDescription = started ? "Esperando «Baxy»" : "wake_inactive";
                // Uso 112, live: the view asks for its wake word at the start; with the ear waiting for memory that fails,
                // and it is asked again when the ear loads (RereadVoiceAsync), unless a later command changed it.
                if (!started && VoicePieces?.WaitingMemory is not null && Volatile.Read(ref _wakeCommands) == command)
                {
                    Volatile.Write(ref _wakeAwaitsEar, 1);
                }

                return started;
            }

            if (!IsListening && !IsWakeListening)
            {
                return true;
            }

            bool stopped = await mind.VoiceStopAsync(TimeSpan.FromSeconds(10), cancellationToken);
            if (stopped)
            {
                IsListening = false;
                IsWakeListening = false;
                IsVoiceSpeaking = false;
                StatusDescription = IdleStatus();
            }

            return stopped;
        }
        finally
        {
            _voiceCommands.Release();
        }
    }

    /// <summary>Dictation: the microphone listens now, without the wake word.</summary>
    internal async Task<bool> StartDirectVoiceAsync(CancellationToken cancellationToken)
    {
        await AwaitStartupVoiceAsync();
        MindSidecarClient? mind = _mindClient;
        if (mind is not { IsReady: true })
        {
            return false;
        }

        // FT/proveedores goal (review of the App): the ear drops what it hears while BAXY speaks (its own voice), so a
        // person who presses to talk over it lost their words; pressing to talk silences BAXY first, as typing does.
        if (IsVoiceSpeaking && mind.IsVoiceAvailable)
            _ = await mind.VoiceCancelAsync(TimeSpan.FromSeconds(3), cancellationToken);
        bool started = await mind.VoiceStartAsync("direct", MindSidecarClient.VoiceStartTimeout, cancellationToken, Settings.EchoCancel);
        IsMicAvailable = started;
        if (started)
        {
            IsListening = true;
            IsWakeListening = false;
            IsVoiceSpeaking = false;
            StatusDescription = "Escuchando";
        }

        return started;
    }

    private void OnMindTranscript(string transcript)
    {
        // The person's words arrived now, before the interface's thread takes them.
        long arrivedAt = System.Diagnostics.Stopwatch.GetTimestamp();
        _uiContext.Post(_ => _ = DispatchTranscriptAsync(transcript, arrivedAt), null);
    }

    private async Task DispatchTranscriptAsync(string transcript, long arrivedAt)
    {
        // 2026-10-22, review of the App: words from a microphone the App does not believe open (a voice.start answered
        // after its deadline, before the stop behind it closed it) start nothing.
        if (_isDisposed || (!IsListening && !IsWakeListening))
        {
            return;
        }

        if (!IsInputEnabled)
        {
            // Heard while a turn runs (or before BAXY is ready): it starts nothing, and that is a state, not silence.
            VoiceFailure = "voice_dropped_busy";
            SoundUnlessMuted(Chime.Wait);
            return;
        }

        VoiceFailure = null;

        try
        {
            await SubmitAsync(new MissionInput(transcript, MissionInputSource.VoiceTranscript), arrivedAt,
                CancellationToken.None);
        }
        catch (MissionInputRejectedException)
        {
            // An unusable transcript starts no turn.
        }
    }

    // Ronda final 18-19 (regla 3): a mind no longer ready is no longer shown ready (IsMindReady reads it), and one whose
    // process ended is no longer shown listening or speaking either: its voice ended with it and sends nothing more.
    private void OnMindReadyLost(MindLoss loss) => _uiContext.Post(
        _ =>
        {
            if (_isDisposed)
                return;
            bool processEnded = loss.Cause == MindLoss.ProcessEnded;
            if (processEnded)
            {
                IsListening = false;
                IsWakeListening = false;
                IsVoiceSpeaking = false;
            }
            // FT/proveedores goal (review of the App): a mind lost while running (its process ended, as when the model
            // server dies and it exits 70, or a request whose reply never came) was never brought back, and the screen
            // and the tray said «Arrancando» for good. It is a failed mind now: shown as such and relaunched with the
            // start-up's growing wait (InitializeMindAsync ends the old process, and its VRAM, first).
            if (_mindStartupState == MindStartupState.Ready && !_mindLifetimeCancellation.IsCancellationRequested)
            {
                string cause = processEnded ? "mente_salio" : "mente_sin_respuesta";
                ShellTraceSink.Record(ShellTraceScopes.Startup, "boot", ShellTraceStages.StartupMindFailed, cause);
                _mindStartupState = MindStartupState.Failed;
                _mindFailureCause = cause;
                _mindFailureMemory = null;
                _mindFailureRead = null;
                RetryMindOrGiveUp(cause);
                MindRestarts.Record(loss, DateTimeOffset.UtcNow - _mindStartedAt);
            }
            OnPropertyChanged(nameof(IsMindReady));
            MindChanged();
        },
        null);

    private void OnMindVoiceEvent(JsonObject voiceEvent)
    {
        string eventName = (string?)voiceEvent["event"] ?? string.Empty;
        string mode = (string?)voiceEvent["mode"] ?? string.Empty;
        bool? speaking = (bool?)voiceEvent["speaking"];
        bool notice = (bool?)voiceEvent["notice"] ?? false;
        string? partial = (string?)voiceEvent["text"];
        SoundTheEar(eventName);
        _uiContext.Post(
            _ =>
            {
                if (_isDisposed)
                {
                    return;
                }

                switch (eventName)
                {
                    case "state":
                        // A dictation is the person speaking; any other change of the voice ends a request heard after
                        // «Baxy» (its transcript was told, or BAXY's own voice dropped it).
                        _voiceRequestOpen = mode == "direct";
                        IsVoiceSpeaking = speaking ?? false;
                        IsWakeListening = mode == "wake";
                        IsListening = mode == "direct";
                        break;
                    case "wake_detected":
                        VoiceFailure = null;
                        _voiceRequestOpen = true;
                        if (_ringer?.Heard(DateTimeOffset.UtcNow) == true && Settings.WakeSound)
                        {
                            // Stopping the ring's tone stopped the wake's chime that had just begun (one sound at a time).
                            SoundUnlessMuted(Chime.Wake);
                        }
                        StatusDescription = "Te escucho…";
                        VoiceWake?.Invoke();
                        break;
                    case "partial":
                        VoiceFailure = null;
                        if (partial is { Length: > 0 })
                        {
                            VoicePartial?.Invoke(partial);
                        }

                        break;
                    case "lip":
                        VoiceLip?.Invoke(voiceEvent);
                        break;
                    case "sound":
                        if (!notice)
                        {
                            // Al máximo 9.2b: the turn's notice counts until its line is heard, not until it is shown.
                            _loop.AnswerSounded();
                        }

                        VoiceSounded?.Invoke(notice ? _noticeAsked ?? string.Empty : null);
                        break;
                    case "transcribing":
                        VoiceFailure = null;
                        StatusDescription = "Transcribiendo…";
                        break;
                    case "voice_ready":
                        // Uso 95: the ear that waited for memory loaded on its own: its state is read again, so the
                        // view stops saying it waits and offers the microphone.
                        _ = RereadVoiceAsync();
                        break;
                    case "error":
                        VoiceFailure = "voice_error";
                        if (_voiceRequestOpen)
                        {
                            _voiceRequestOpen = false;
                            SoundUnlessMuted(Chime.ListenFailed);
                        }

                        break;
                }
            },
            null);
    }

    private async Task ApplyStartupVoiceAsync(
        MindSidecarClient mind,
        MindVoiceStatus? voice,
        CancellationToken cancellationToken)
    {
        IsMicAvailable = voice?.MicUsable == true;
        SetVoicePieces(voice);
        if (!StartupWakeApplies(
                voice,
                WakeOnStartRequested(),
                Volatile.Read(ref _personVoiceChoice) != 0,
                IsListening || IsWakeListening))
        {
            return;
        }

        bool wakeStarted = await mind.VoiceStartAsync("wake", MindSidecarClient.VoiceStartTimeout, cancellationToken, Settings.EchoCancel);
        IsWakeListening = wakeStarted;
        if (wakeStarted)
        {
            IsMicAvailable = true;
        }

        // A wake word that did not start is a state the interface shows (VoiceFailure), as the person's own does.
        WakeStartTold(wakeStarted);
        if (!IsBusy && Volatile.Read(ref _personVoiceChoice) == 0)
        {
            StatusDescription = wakeStarted ? "Esperando «Baxy»" : "wake_inactive";
        }
    }

    private void WakeStartTold(bool started)
    {
        if (!started)
        {
            VoiceFailure = WakeUnavailable;
        }
        else if (VoiceFailure == WakeUnavailable)
        {
            VoiceFailure = null;
        }
    }

    /// <summary>
    /// Whether the mind turns the wake word on by itself at startup: the voice state is known (not <c>pending</c>),
    /// there is a microphone or a recognizer, the product asks for it, and the person has not chosen their voice yet.
    /// </summary>
    internal static bool StartupWakeApplies(
        MindVoiceStatus? voice,
        bool wakeOnStartRequested,
        bool personChoseVoice,
        bool voiceRunning) =>
        voice is { Pending: false }
        && (voice.Available || voice.InputAvailable || voice.SttAvailable)
        && voice.WaitingMemory is null
        && wakeOnStartRequested
        && !personChoseVoice
        && !voiceRunning;

    private async Task AwaitStartupVoiceAsync()
    {
        Volatile.Write(ref _personVoiceChoice, 1);
        try
        {
            await _startupVoice;
        }
        catch (Exception)
        {
            // The startup voice failing leaves the person's command to act.
        }
    }

    private async Task SettleStartupVoiceAsync(
        MindSidecarClient mind,
        TaskCompletionSource settled,
        CancellationToken cancellationToken)
    {
        try
        {
            MindVoiceStatus voice = await VoiceStatusSettling.UntilSettledAsync(
                token => ReferenceEquals(_mindClient, mind) && mind.IsReady
                    ? mind.VoiceStatusAsync(TimeSpan.FromSeconds(10), token)
                    : throw new OperationCanceledException("mind_replaced"),
                static (delay, token) => Task.Delay(delay, token),
                cancellationToken);
            if (ReferenceEquals(_mindClient, mind))
            {
                Task startupVoice = ApplyStartupVoiceAsync(mind, voice, cancellationToken);
                _startupVoice = startupVoice;
                await startupVoice;
            }
        }
        catch (Exception)
        {
            // Voice availability is optional state; a failed read never touches the turn.
        }
        finally
        {
            settled.TrySetResult();
        }
    }

    private static bool WakeOnStartRequested()
    {
        string value = Environment.GetEnvironmentVariable("BAXY_VOICE_WAKE_ON_START") ?? string.Empty;
        return value.Equals("1", StringComparison.Ordinal)
            || value.Equals("true", StringComparison.OrdinalIgnoreCase)
            || value.Equals("yes", StringComparison.OrdinalIgnoreCase)
            || value.Equals("on", StringComparison.OrdinalIgnoreCase);
    }

    // ---- mind start-up -------------------------------------------------------------------------------------

    private ExternalModel? _externalModel;
    private TunedModel? _tunedModel;
    private PersonBehavior? _behavior;
    private ToolProfile? _toolProfile;
    private LocalContext? _localContext;
    private PrefixRead? _prefixRead;

    private async Task InitializeMindAsync(
        Task<MindStartupCatalog> catalog,
        CancellationToken startupAbandoned,
        CancellationToken cancellationToken)
    {
        using var linked = CancellationTokenSource.CreateLinkedTokenSource(
            cancellationToken, startupAbandoned, _mindLifetimeCancellation.Token, _mindStartCut.Token);
        MindSidecarClient? mind = null;
        bool starting = false;
        TaskCompletionSource? voiceSettled = null;
        bool settling = false;
        try
        {
            await _mindStart.WaitAsync(linked.Token);
            starting = true;
            if (_mindClient is { IsReady: true })
            {
                // The start this one waited for brought the mind up.
                return;
            }

            await RemoveEarlierWordsAsync(linked.Token);

            // The shell's first start counts from its check of the runtime, the wait the person already sees (W1); a
            // relaunch from its own start.
            if (!_startupMindPending)
            {
                _mindStartedAt = DateTimeOffset.UtcNow;
            }

            _mindStartupState = MindStartupState.Starting;
            _mindRetryPending = false;
            _mindReadyAt = null;
            _mindReading = null;
            PrefixReadState.Begin();
            _mindOnProcessor = false;
            OnPropertyChanged(nameof(MindStartedAt));
            MindRuntimeDiscoveryResult discovery = await Task.Run(
                static () => MindRuntimeDiscovery.DiscoverVerified(), linked.Token);
            if (!ApplyMindRuntime(discovery))
            {
                _mindFailureCause = discovery.Problem;
                _mindFailureMemory = null;
                _mindFailureRead = null;
                return;
            }

            // One model at a time: a pair kept on together from before is started as what really ran, the other model.
            KeepOneModel(tunedChosen: false);

            // QWB2: after the registered runtime, whose stock model it replaces only once verified.
            await TunedModelState.StartAsync(linked.Token);

            // After the registered runtime: it uses that interpreter and overrides the vision's address.
            if (ExternalModel.Available)
            {
                ExternalModel.ProfileLoan? lent = ExternalModelState.Lent;
                await ExternalModelState.StartAsync(linked.Token);
                // VIVO2 F15: before the profile is read below, and the context of BAXY's own model with it.
                SettleProfile(lent);
            }

            // Settings → Model → Context: BAXY's own model (stock or tuned) starts with the person's preset; another
            // model's context is its own (ExternalModel), and the variable stays as it set it.
            bool ownModel = !ExternalModelState.Active;
            IReadOnlyList<(string Profile, int Need)> orElse = [];
            if (ownModel)
            {
                // VRAM4B: what the person's own profile needs; and, while none is kept, what each smaller ready-made
                // profile needs, for the mind to start in the largest the card's free video memory holds instead of
                // failing (ToolProfile.FitCard, at its hello). VRAM4C: the one it took is kept for this PC (ByCard) and
                // goes alone from then on, as a chosen one: another day's free memory changes nothing by itself.
                // VRAM4D (REV18 R18-2): alone while the card is short; the mind is given the list and which one it is
                // (KeptVariable), so on a card with room the start tries the factory's again and the App drops it.
                bool chosen = ToolProfileState.Chosen;
                orElse = chosen ? [] : ToolProfile.Smaller(MindPrefixTokens, MindPrefixProfile);
                string? keptName = ToolProfileState.KeptForTheCard?.Profile;
                LocalContextState.ApplyEnvironment(MindBackend,
                    chosen ? ExternalModelState.NeededNow : ToolProfile.NeededContext(ToolProfile.Completo, MindPrefixTokens, MindPrefixProfile),
                    orElse.Select(static smaller => smaller.Need),
                    orElse.FirstOrDefault(smaller => smaller.Profile == keptName) is { Profile: not null } keptOne ? keptOne.Need : null);
            }

            ShellTraceSink.Record(ShellTraceScopes.Startup, "boot", ShellTraceStages.StartupMindVerified);
            if (_mindClient is not null)
            {
                DetachMind(_mindClient);
                await _mindClient.DisposeAsync();
                _mindClient = null;
            }

            // Settings → Behavior: the person's own texts, read as this start begins (PersonBehavior).
            JsonObject? behavior = BehaviorState.ForMind();
            // Settings → Tools: the profile, read as this start begins (ToolProfile).
            IReadOnlySet<string> withheld = ToolProfileState.Withheld(
                Baxy.Kernel.Operations.ProductCatalog.ToolDescriptors.Select(static descriptor => descriptor.Name));
            // REM7: read again when the catalog is configured, after the core's hello and memory.status (MEM3), which
            // this start does not wait for.
            mind = new MindSidecarClient
            {
                Behavior = behavior,
                Withheld = withheld,
                WithheldNow = () => ToolProfileState.Withheld(
                    Baxy.Kernel.Operations.ProductCatalog.ToolDescriptors.Select(static descriptor => descriptor.Name)),
                MemoryOffNow = () => ToolProfileState.MemoryOff,
                CardSaid = (fit, memory) => ToolProfileState.FitCard(fit is not null && ownModel && !ToolProfileState.Chosen
                    && orElse.FirstOrDefault(smaller => smaller.Need == fit.Needs) is { Profile: { } fitting }
                        ? new ToolProfile.CardFitted(fitting, fit.FreeMb, fit.NeedMb) : null, ownModel ? memory?.Short : null),
                CardProfileNow = () => ToolProfileState.CardProfileFact(),
            };
            mind.ModelReading += OnMindReading;
            mind.ModelReading += MeasureRead;
            // FT/proveedores goal (review of the App): the mind waits up to 600 s for its model to load (wait_ready in
            // __main__.py) before it says catalog.ready; at 120 s the App ended a slow but healthy load (no GPU, a cold
            // disk) and relaunched it for ever. A model server that dies is told at once (startup_failure). Uso 84: the
            // 600 s are a window the mind's progress through its prompt prefix starts again (a cold read took 167.5 s on
            // an AMD RX 7600, longer on a slower GPU), within MindSidecarClient.StartupCeiling.
            bool started = await mind.TryStartAsync(catalog, TimeSpan.FromSeconds(600), linked.Token);
            mind.ModelReading -= OnMindReading;
            mind.ModelReading -= MeasureRead;
            _mindOnProcessor = mind.ComputesOnProcessor == true;
            _mindReading = null;
            if (!started)
            {
                RecordMindStartupFailure(mind.LastStartupFailure);
                await mind.DisposeAsync();
                return;
            }

            // 2026-10-22, review of the App: a mind started while the view shows a conversation (a relaunch after the
            // last one was lost) began empty, and the model answered as if nothing had been said. It gets back that
            // conversation as it was last kept; with none, nothing pending survives either (the lost mind asked it).
            if (KeptConversation?.Invoke() is not { Count: > 0 } kept || !await mind.SessionLoadAsync(kept, linked.Token))
            {
                _loop.Reset();
            }

            if (!mind.IsReady)
            {
                RecordMindStartupFailure(null);
                await mind.DisposeAsync();
                return;
            }

            mind.TranscriptReceived += OnMindTranscript;
            mind.VoiceEventReceived += OnMindVoiceEvent;
            mind.ReadyLost += OnMindReadyLost;
            Volatile.Write(ref _personVoiceChoice, 0);
            // Before the mind is announced ready: a wake word asked for from then on waits for its voice to settle.
            voiceSettled = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
            _voiceSettled = voiceSettled.Task;
            _mindClient = mind;
            BehaviorState.Started(behavior);
            ToolProfileState.Started(mind.ConfiguredWithheld ?? withheld);
            FactoryBehavior = mind.FactoryBehavior ?? FactoryBehavior;
            // MOD1 D5: what this start took to read the prefix whole, if it did, is this PC's measure from now on.
            PrefixReadState.Ended(ownModel);
            LocalContextState.Started(ownModel, mind.Context, mind.CardShort);
            if (ownModel)
            {
                // Read with BAXY's own model's tokens: another model's prefix is counted by its own.
                _mindBackend = mind.Backend ?? _mindBackend;
                MindPrefixTokens = mind.PrefixTokens ?? MindPrefixTokens;
                MindPrefixProfile = mind.PrefixTokens is null ? MindPrefixProfile : ToolProfileState.Profile;
            }

            _mindStartupState = MindStartupState.Ready;
            _mindRetries.Up(DateTimeOffset.UtcNow);
            ShellTraceSink.Record(ShellTraceScopes.Startup, "boot", ShellTraceStages.StartupMindReady);
            _mindReadyAt = DateTimeOffset.UtcNow;
            _mindFailureCause = null;
            // N9 (L5): a read too slow gives up at the first failure, and a PC that was only busy can bring a mind up
            // afterwards (a core's recovery starts one): a BAXY that works shows no breakdown.
            if (_mindGaveUp)
            {
                _mindGaveUp = false;
                OnPropertyChanged(nameof(Failure));
            }

            OnPropertyChanged(nameof(IsMindReady));
            // A message that waited for this mind is its first turn (uso 95).
            MindChanged();
            // Settings → Behavior: texts the person changed while this mind was starting (it took them as the start
            // began): it is relaunched on them once this start ends.
            if (BehaviorState.NeedsSwitch)
            {
                BehaviorChanged();
            }

            // Settings → Tools: a profile chosen while this mind was starting.
            if (ToolProfileState.NeedsSwitch)
            {
                ToolsChanged();
            }

            // The same for a context chosen while it was starting.
            if (LocalContextState.NeedsSwitch)
            {
                LocalContextChanged();
            }

            // Ajuste c3: a list of installed applications the core read after the mind's catalog was taken.
            if (_coreClient?.ApplicationCatalog is { Verified: true } installed)
            {
                await mind.UpdateApplicationCatalogAsync(installed, MindCatalogUpdateBudget, linked.Token);
            }

            MindVoiceStatus? voice = await mind.VoiceStatusAsync(TimeSpan.FromSeconds(10), linked.Token);
            IsMicAvailable = voice?.MicUsable == true;
            SetVoicePieces(voice);
            if (voice is not { Pending: false })
            {
                // The voice runtime is still importing, or its state did not come in time (a slow answer under load, not
                // «no voice»: it used to be taken as none, and the wake word asked for at start never started): the
                // mind serves turns now and the voice settles beside them, however long its ear takes to load.
                settling = true;
                _ = SettleStartupVoiceAsync(mind, voiceSettled, _mindLifetimeCancellation.Token);
            }
            else
            {
                voiceSettled.TrySetResult();
                _startupVoice = ApplyStartupVoiceAsync(mind, voice, linked.Token);
                await _startupVoice;
            }
        }
        catch (Exception) when (linked.IsCancellationRequested)
        {
            if (mind is not null && !ReferenceEquals(mind, _mindClient))
            {
                await mind.DisposeAsync();
            }

            if (starting && _mindStartupState == MindStartupState.Starting)
            {
                _mindStartupState = MindStartupState.Failed;
            }
        }
        finally
        {
            if (!settling)
            {
                voiceSettled?.TrySetResult();
            }

            if (starting)
            {
                _mindStart.Release();
            }

            _startupMindPending = false;
            MindChanged();
            if (IsReady && !IsBusy)
            {
                StatusDescription = IdleStatus();
            }
        }
    }

    /// <summary>
    /// r22 (2026-10-09): a model that could not come up is traced with its cause, shown as a state, and retried on its
    /// own with a growing wait (<see cref="StartupRetries"/>), within its limit.
    /// </summary>
    private void RecordMindStartupFailure(MindStartupFailure? failure)
    {
        _mindStartupState = MindStartupState.Failed;
        _mindFailureCause = failure?.Cause ?? "desconocida";
        _mindFailureMemory = failure?.NeedMb is { } need ? (need, failure.FreeMb) : null;
        _mindFailureRead = failure is { TokensPerS: { } pace, NeedMinutes: { } minutes } ? (pace, minutes, failure.CardFull) : null;
        LocalContextState.Failed(failure?.CardShort);
        string cause = failure?.TraceLabel ?? "desconocida";
        ShellTraceSink.Record(ShellTraceScopes.Startup, "boot", ShellTraceStages.StartupMindFailed, cause);
        RetryMindOrGiveUp(cause, once: failure?.CardShort is not null);
        MindRestarts.Record(new MindLoss("startup." + cause), DateTimeOffset.UtcNow - _mindStartedAt);
    }

    // On the UI thread, as the mind's other events: the reader's thread cannot publish to the view (WebView2 refuses it, and
    // the bridge swallows that). A line that arrives once the start ended is old news.
    private void OnMindReading(MindModelReading reading) => _uiContext.Post(
        _ =>
        {
            if (_mindStartupState != MindStartupState.Starting)
            {
                return;
            }

            _mindReading = reading;
            _mindOnProcessor = reading.OnProcessor;
            OnPropertyChanged(nameof(MindReading));
        },
        null);

    // MOD1 D5: measured as each line arrives, on the mind's reader thread: every one is in before the start's end is known.
    private void MeasureRead(MindModelReading reading) =>
        PrefixReadState.Saw(reading.Done, reading.Total, System.Diagnostics.Stopwatch.GetElapsedTime(0));

    // Uso 85: the same failure again and again is a breakdown the interface shows, never one more relaunch. N9 (L5): a read
    // too slow is that from the first time: the next would read at the same pace for as long, and only the person knows
    // whether the PC was busy (RetryEngine).
    private void RetryMindOrGiveUp(string cause, bool once = false)
    {
        // VRAM4B: a start on a card that does not hold the profile whole repeats the same on its own: one attempt, and the
        // breakdown says what it found and the ways out (never a chain of starts from zero).
        if (cause != MindStartupFailure.ReadTooSlow && !once
            && _mindRetries.Failed(cause, DateTimeOffset.UtcNow) is { } delay)
        {
            _mindRetryPending = true;
            _ = RetryMindAfterAsync(delay);
            return;
        }

        _mindRetryPending = false;
        _mindGaveUp = true;
        OnPropertyChanged(nameof(Failure));
    }

    private async Task RetryMindAfterAsync(TimeSpan delay)
    {
        try
        {
            await Task.Delay(delay, _mindLifetimeCancellation.Token);
        }
        catch (Exception exception) when (exception is OperationCanceledException or ObjectDisposedException)
        {
            return;
        }

        if (_isDisposed || _mindStartupState != MindStartupState.Failed || _coreClient is not { IsReady: true } core)
        {
            // No relaunch after all: a message waiting for the mind stops waiting (uso 95).
            _mindRetryPending = false;
            MindChanged();
            return;
        }

        Task initialization = InitializeMindAsync(
            Task.FromResult(new MindStartupCatalog(core.Capabilities, core.ApplicationCatalog, core.GameCatalog)),
            CancellationToken.None,
            _mindLifetimeCancellation.Token);
        _mindInitializationTask = initialization;
        await initialization;
    }

    private void DetachMind(MindSidecarClient mind)
    {
        mind.TranscriptReceived -= OnMindTranscript;
        mind.VoiceEventReceived -= OnMindVoiceEvent;
        mind.ReadyLost -= OnMindReadyLost;
        // Ronda final 27 (regla 3): the voice was that mind's: a new one starts nothing listening until it says so.
        IsListening = false;
        IsWakeListening = false;
        IsVoiceSpeaking = false;
    }

    // ---- core ----------------------------------------------------------------------------------------------

    /// <summary>
    /// A change of the model by API applies at once: nothing more goes to what the person left, so a running turn's next step
    /// fails; once it ends, the mind stops and a new one starts on what the person chose, and gets its conversation back
    /// (InitializeMindAsync). The view answers without waiting for it.
    /// </summary>
    internal void ExternalModelChanged()
    {
        ExternalModel model = ExternalModelState;
        // Not waiting for the engine: nothing would ask again, and what the person turned off would go on being sent.
        if (_isDisposed || !model.NeedsSwitch)
        {
            return;
        }

        // A mind starting on the translator stopped here would wait out its 600 s on a port with nobody there. API1 (a friend
        // of the owner's, 4 GB card, 12-11-2026): one starting on BAXY's own model is cut too. It serves a choice the person
        // left, and on a PC that reads the model too slowly it held the switch for up to 45 min (StartupCeiling): «Cambiando…»
        // for ever, behind a card preparing the model the switch says it no longer loads. Its mind ends with its process's
        // job, and the llama-server it started with it (LocalJsonlSidecarProcess, KillOnJobClose).
        _ = model.Cut();
        CancellationTokenSource cut = _mindStartCut;
        _mindStartCut = new CancellationTokenSource();
        Interlocked.Increment(ref _mindStartsCut);
        cut.Cancel();
        cut.Dispose();

        if (model.Switching)
        {
            return;
        }

        model.Switching = true;
        _ = SwitchMindAsync(model);
    }

    /// <summary>
    /// QWB2: turning the tuned model on or off, or removing it, relaunches the mind on it as a change of the model by API
    /// does: once the running turn ends, and with its conversation back. One switch at a time serves both.
    /// </summary>
    /// <summary>
    /// Owner, 2026-11-08: «tengo activo el modelo ajustado y activo usar otro modelo. Eso no tiene sentido». BAXY thinks
    /// with one model: the stock one, the tuned one, or another (local or by API). With both switches on, the one the
    /// person just chose stays and the other goes off; with neither chosen (a start), the other model stays, as it is
    /// the one that ran (it takes the place of BAXY's own model, tuned or not).
    /// </summary>
    internal void KeepOneModel(bool tunedChosen)
    {
        if (!ExternalModel.Available || (bool?)ExternalModelState.Json()["enabled"] != true
            || (bool?)TunedModelState.Json()["use"] != true)
        {
            return;
        }

        _ = tunedChosen
            ? ExternalModelState.Apply(new JsonObject { ["enabled"] = false })
            : TunedModelState.Apply(new JsonObject { ["use"] = false });
    }

    internal void TunedModelChanged()
    {
        ExternalModel model = ExternalModelState;
        if (_isDisposed || !TunedModelState.NeedsSwitch || model.Switching)
        {
            return;
        }

        model.Switching = true;
        _ = SwitchMindAsync(model);
    }

    /// <summary>
    /// Settings → Behavior: the person's texts changed, and the mind is relaunched on them as a change of model does: once
    /// the running turn ends, and with its conversation back. Its prompt prefix is then read once with them, and kept.
    /// </summary>
    internal void BehaviorChanged()
    {
        ExternalModel model = ExternalModelState;
        if (_isDisposed || !BehaviorState.NeedsSwitch || model.Switching)
        {
            return;
        }

        model.Switching = true;
        _ = SwitchMindAsync(model);
    }

    /// <summary>TPV1: a tool profile chosen by voice, or TPV6 a tool turned on with the person's «sí» (ToolProfile.KeepOn),
    /// is applied as PUT /settings/tools applies one: the mind is relaunched with its tools once this turn ends
    /// (ToolsChanged waits for it), and a small context chosen for the profile before may not fit this one's.</summary>
    internal void ToolsChangedBySpeaking()
    {
        if (!ToolProfileState.NeedsSwitch)
        {
            return;
        }

        if (ExternalModel.Available)
        {
            ExternalModelState.ForgetLoan();
        }

        // TPV5: a chosen context grows only as much as the new tools need (LocalContext.KeepFitting).
        _ = LocalContextState.KeepFitting(ExternalModelState.NeededNow);
        ToolsChanged();
    }

    /// <summary>
    /// Settings → Tools: another profile, and the mind is relaunched with its tools as for new texts: once the running turn
    /// ends, and with its conversation back. Its prompt prefix is read once for that profile, and kept under its own key.
    /// </summary>
    internal void ToolsChanged()
    {
        ExternalModel model = ExternalModelState;
        if (_isDisposed || !ToolProfileState.NeedsSwitch || model.Switching)
        {
            return;
        }

        model.Switching = true;
        _ = SwitchMindAsync(model);
    }

    /// <summary>
    /// Settings → Model → Context: llama-server takes its context at its start, so a new one relaunches the mind on BAXY's
    /// own model as a change of model does: once the running turn ends, and with its conversation back.
    /// </summary>
    internal void LocalContextChanged()
    {
        ExternalModel model = ExternalModelState;
        if (_isDisposed || !LocalContextState.NeedsSwitch || model.Switching)
        {
            return;
        }

        model.Switching = true;
        _ = SwitchMindAsync(model);
    }

    private async Task SwitchMindAsync(ExternalModel model)
    {
        CancellationToken lifetime = _mindLifetimeCancellation.Token;
        int cuts = 0;
        try
        {
            bool again;
            do
            {
                bool gated = await TurnGateAndMindStartAsync(lifetime);
                try
                {
                    model.Stop();
                    TunedModelState.Stop();
                    if (_mindClient is { } running)
                    {
                        DetachMind(running);
                        _mindClient = null;
                        OnPropertyChanged(nameof(IsMindReady));
                        await running.DisposeAsync();
                    }
                }
                finally
                {
                    _mindStart.Release();
                    if (gated)
                    {
                        _turnGate.Release();
                    }
                }

                // A recovery under way starts a mind only if none was there when it began.
                await WaitForCoreRecoveryAsync();
                if (_coreClient is not { IsReady: true } core)
                {
                    // The engine's next start brings up the mind, on what is chosen by then.
                    return;
                }

                cuts = Volatile.Read(ref _mindStartsCut);
                Task initialization = InitializeMindAsync(
                    Task.FromResult(new MindStartupCatalog(core.Capabilities, core.ApplicationCatalog, core.GameCatalog)),
                    CancellationToken.None,
                    lifetime);
                _mindInitializationTask = initialization;
                await initialization;

                // A start that brought no mind up (its runtime did not apply) leaves the choice to the next start: going round
                // again would start nothing either, for ever. API1: one a newer change cut goes round again, on what is chosen
                // now, and also when that change was taken back meanwhile (nothing else would start a mind: a cut start
                // schedules no retry).
                bool cut = cuts != Volatile.Read(ref _mindStartsCut);
                again = !_isDisposed
                    && ((cut && _mindClient is null)
                        || ((_mindClient is not null || cut)
                            && (model.NeedsSwitch || TunedModelState.NeedsSwitch || BehaviorState.NeedsSwitch
                                || ToolProfileState.NeedsSwitch || LocalContextState.NeedsSwitch)));
            }
            while (again);
        }
        catch (Exception exception) when (exception is OperationCanceledException or ObjectDisposedException)
        {
            // BAXY is closing.
        }
        finally
        {
            model.Switching = false;
            // A turn that waited for the mind this switch was bringing looks again (IsMindPreparing).
            MindChanged();
        }
    }

    /// <summary>
    /// The turn gate, so that no turn is cut half-way by a relaunch; false when it was not taken because the turn holding it
    /// waits for a mind and none is up (uso 95, MindForTurnAsync). API1: a «hola» written while BAXY's own model loaded
    /// held the gate the switch to another model waited for, while it waited for the mind that switch was to bring.
    /// </summary>
    private async Task<bool> TurnGateOrAwaitedMindAsync(CancellationToken cancellationToken)
    {
        while (!await _turnGate.WaitAsync(TimeSpan.FromMilliseconds(100), cancellationToken))
        {
            if (IsAwaitingMind && _mindClient is not { IsReady: true })
            {
                return false;
            }
        }

        return true;
    }

    /// <summary>
    /// The turn gate as <see cref="TurnGateOrAwaitedMindAsync"/> gives it, and then the start of the mind. Without the gate, a
    /// mind that came up while this waited for the start (the start it waited for was not cut) is the waiting turn's now: the
    /// switch lets the start go and waits for that turn like any other. Holding the start, no other mind can come up.
    /// </summary>
    private async Task<bool> TurnGateAndMindStartAsync(CancellationToken cancellationToken)
    {
        while (true)
        {
            bool gated = await TurnGateOrAwaitedMindAsync(cancellationToken);
            try
            {
                await _mindStart.WaitAsync(cancellationToken);
            }
            catch when (gated)
            {
                _turnGate.Release();
                throw;
            }

            if (gated || _mindClient is not { IsReady: true })
            {
                return gated;
            }

            _mindStart.Release();
        }
    }

    /// <summary>The model by API (ExternalModel), for the view's Settings and the mind's start.</summary>
    internal ExternalModel ExternalModelState
    {
        get
        {
            if (_externalModel is null)
            {
                _externalModel = new ExternalModel(MemoryOperationProtector.ResolveDataRoot())
                {
                    // VIVO1 F4: another model is offered and connected only where the chosen profile's prompt fits.
                    Need = () => ToolProfile.NeededContext(ToolProfileState.Profile, MindPrefixTokens, MindPrefixProfile,
                        ToolProfileState.Kept),
                    Fitting = context => ToolProfile.LargestFitting(context, MindPrefixTokens, MindPrefixProfile),
                    NeedOf = profile => ToolProfile.NeededContext(profile, MindPrefixTokens, MindPrefixProfile),
                };
                _externalModel.Open.WentOnline += what => ModelDownloadOnline?.Invoke(what);
                _externalModel.Open.Pulled += name => _uiContext.Post(_ => UseModelPulled(name), null);
            }

            return _externalModel;
        }
    }

    /// <summary>Whether the conversation's log holds words (ConversationLog): «Olvidar todo» deletes it (PRV1 D7).</summary>
    internal bool ConversationLogHoldsAny => _conversationLog?.HoldsAny == true;

    /// <summary>Whether the mind thinks now with a company's API (or «Otra»): what the person gives it leaves this PC. A model
    /// never set up is BAXY's own, so this does not create one.</summary>
    internal bool ThinksByApi => _externalModel is { ThinksOnThisPc: false };

    /// <summary>The model's start ended, with <paramref name="lent"/> standing when it began (ExternalModel.Lent): a profile
    /// lent to a model that did not connect goes back to the one the person had, before the mind reads it.</summary>
    internal void SettleProfile(ExternalModel.ProfileLoan? lent)
    {
        if (lent is not null && ExternalModelState.Settle(lent, ToolProfileState.Profile) is { } before && ToolProfileState.Apply(before) is null)
        {
            _ = LocalContextState.KeepForEveryProfile();
        }
    }

    /// <summary>«Instalar y usar»: the model Ollama finished downloading is the one chosen, and the mind connects to it. One
    /// model at a time, as the switches keep it (INT17, revisión ciega): the tuned one goes off in the same switch.</summary>
    internal void UseModelPulled(string name)
    {
        if (_isDisposed)
        {
            return;
        }

        // A model short of the chosen profile, installed with the one the search offered it with (VIVO2 F13): that profile too,
        // unless the person chose meanwhile one whose prompt is no bigger.
        ExternalModel external = ExternalModelState;
        string? profile = external.Open.TakeProfile(name);
        _ = UseLocalModel(name, profile is not null && external.NeedFor(profile) < external.NeededNow ? profile : null);
    }

    /// <summary>The model of this PC named is the one chosen and the mind connects to it, with the tool profile
    /// <paramref name="profile"/> if one is given: both, or neither (the refusal's code).</summary>
    internal string? UseLocalModel(string name, string? profile) =>
        UseModel(new JsonObject { ["provider"] = "local", ["model"] = name, ["enabled"] = true }, profile);

    /// <summary>What the panel asks of the model (ExternalModel.Apply) with the tool profile <paramref name="profile"/> if one
    /// is given, in one gesture: both, or neither (the refusal's code). The profile is lent to the model (VIVO2 F15): if its
    /// start does not connect it, the person gets back the one they had (SettleProfile).</summary>
    internal string? UseModel(JsonObject asked, string? profile)
    {
        JsonObject before = ToolProfileState.Json();
        bool changes = profile is not null && profile != ToolProfileState.Profile;
        if (changes && ToolProfileState.Apply(new JsonObject { ["profile"] = profile }) is { } noProfile)
        {
            return noProfile;
        }

        if (ExternalModelState.Apply(asked) is { } refused)
        {
            if (changes)
            {
                _ = ToolProfileState.Apply(before);
            }

            return refused;
        }

        if (changes && profile is not null)
        {
            // A small context chosen for the profile left may not be among the next one's (LocalContext), as in PUT /settings/tools.
            _ = LocalContextState.KeepForEveryProfile();
            if (ExternalModelState.ChosenModel is { Length: > 0 } model)
            {
                ExternalModelState.Lend(model, profile, before);
            }
        }

        KeepOneModel(tunedChosen: false);
        // One relaunch serves both changes (SwitchMindAsync goes by what is chosen when it starts the mind).
        ExternalModelChanged();
        ToolsChanged();
        TunedModelChanged();
        return null;
    }

    /// <summary>A model search or a download of Settings → Model → Local reached the internet: what, for «Salidas a internet».</summary>
    internal event Action<string>? ModelDownloadOnline;

    /// <summary>BAXY's tuned model, offered by the package and downloaded only when the person asks (TunedModel).</summary>
    internal TunedModel TunedModelState
    {
        get
        {
            if (_tunedModel is null)
            {
                _tunedModel = new TunedModel(
                    MemoryOperationProtector.ResolveDataRoot(),
                    static () => MindRuntimeDiscovery.TunedOffer(MindRuntimeDiscovery.DefaultRegistrationPath()));
                _tunedModel.WentOnline += host => TunedModelOnline?.Invoke(host);
                // A download that finishes while the person's choice is to use it switches the mind to it.
                _tunedModel.Installed += () => _uiContext.Post(_ => TunedModelChanged(), null);
            }

            return _tunedModel;
        }
    }

    /// <summary>The person's own texts for how BAXY behaves (Settings → Behavior).</summary>
    internal PersonBehavior BehaviorState => _behavior ??= new PersonBehavior(MemoryOperationProtector.ResolveDataRoot());

    /// <summary>The person's tool profile (Settings → Tools).</summary>
    internal ToolProfile ToolProfileState => _toolProfile ??= new ToolProfile(MemoryOperationProtector.ResolveDataRoot());

    /// <summary>The mind's fixed identity and factory texts, as the last mind that came up told them; null until one did.</summary>
    internal JsonObject? FactoryBehavior { get; private set; }

    /// <summary>The context BAXY's own model runs with (Settings → Model → Context).</summary>
    internal LocalContext LocalContextState => _localContext ??= new LocalContext(MemoryOperationProtector.ResolveDataRoot());

    /// <summary>What this PC took the last time BAXY's own model read its prompt prefix whole (MOD1 D5).</summary>
    internal PrefixRead PrefixReadState => _prefixRead ??= new PrefixRead(MemoryOperationProtector.ResolveDataRoot());

    /// <summary>The backend the last mind on BAXY's own model computed on, and the tokens of the prompt prefix it read; null
    /// until one came up and said them. Before any did, the backend is the one the App's own start chose the server by, where
    /// it chose (MindRuntimeDiscovery: BAXY_MIND_LLAMA_BACKEND, which the mind holds the server's folder to): REV_APP VRAM-b,
    /// the figures of Settings → Model were NVIDIA's until a mind spoke, on any card.</summary>
    internal string? MindBackend => _mindBackend
        ?? (Environment.GetEnvironmentVariable("BAXY_MIND_LLAMA_BACKEND")?.Trim() is { } chosen && LocalContext.Automatic(chosen) is not null ? chosen : null);

    private string? _mindBackend;

    internal int? MindPrefixTokens { get; private set; }

    /// <summary>The tool profile <see cref="MindPrefixTokens"/> was read with: it scales the others' (ToolProfile.NeededContext).</summary>
    internal string? MindPrefixProfile { get; private set; }

    /// <summary>Why this start runs the stock model although the person chose the tuned one, or null.</summary>
    internal string? TunedModelProblem => _tunedModel?.Problem;

    /// <summary>The tuned model's download reached this host: the view's «Salidas a internet».</summary>
    internal event Action<string>? TunedModelOnline;

    public async ValueTask DisposeAsync()
    {
        if (_isDisposed)
        {
            return;
        }

        _isDisposed = true;
        IsReady = false;
        _ringer?.Dispose();
        _externalModel?.Dispose();
        _tunedModel?.Dispose();
        _mindLifetimeCancellation.Cancel();
        MindChanged();
        if (_mindInitializationTask is not null)
        {
            try
            {
                await _mindInitializationTask;
            }
            catch (OperationCanceledException)
            {
            }
        }

        if (_coreClient is not null)
        {
            DetachCoreDisconnectedHandler(_coreClient);
            await _coreClient.DisposeAsync();
            _coreClient = null;
        }

        if (_mindClient is not null)
        {
            DetachMind(_mindClient);
            await _mindClient.DisposeAsync();
            _mindClient = null;
        }

        // PRV1 (PRIV-02): BAXY closes with the engine already stopped: no screen it captured stays on the disk.
        ClearCaptures();
        _mindLifetimeCancellation.Dispose();
        _mindStartCut.Dispose();
    }

    private async Task HandleStartupFailureAsync(CoreProcessClient client, Exception exception)
    {
        _loop.Reset(engineRestarted: true);
        DetachCoreDisconnectedHandler(client);
        await client.DisposeAsync();
        if (ReferenceEquals(_coreClient, client))
        {
            _coreClient = null;
        }

        IsReady = false;
        if (CoreStartFailed(exception, DateTimeOffset.UtcNow) is { } delay)
        {
            _ = RetryCoreAfterAsync(delay);
        }
    }

    /// <summary>
    /// What a core start that failed by <paramref name="exception"/> leaves: the failure the interface shows and the wait
    /// before the next start, or null when there is none to make. FT/proveedores goal (review of the App): a core that
    /// could not start (its hello late at a busy sign-in) was never tried again; it is retried with a growing wait.
    /// Uso 85: a profile the core cannot read is terminal (<see cref="ProfileUnreadable"/>), and the same failure again
    /// and again a breakdown (<see cref="EngineUnavailable"/>): neither relaunches anything.
    /// </summary>
    internal TimeSpan? CoreStartFailed(Exception exception, DateTimeOffset at)
    {
        if (exception is CoreProfileUnreadableException)
        {
            SetStartupFailure(ProfileUnreadable);
            return null;
        }

        TimeSpan? delay = _coreRetries.Failed($"{exception.GetType().Name}: {exception.Message}", at);
        SetStartupFailure(delay is null ? EngineUnavailable : "retry_without_close");
        return delay;
    }

    /// <summary>The person asked to try again after a breakdown (<see cref="EngineUnavailable"/>): the count starts anew
    /// and the piece that is down starts. False when there is no breakdown to retry.</summary>
    internal bool RetryEngine()
    {
        if (_isDisposed || Failure != EngineUnavailable)
        {
            return false;
        }

        _coreRetries.Reset();
        _mindRetries.Reset();
        _mindGaveUp = false;
        OnPropertyChanged(nameof(Failure));
        if (!IsReady)
        {
            // InitializeAsync ends the old client and starts a mind that is not up beside the core.
            RecoverCoreWhenIdle();
        }
        else if (_mindStartupState == MindStartupState.Failed)
        {
            _mindRetryPending = true;
            MindChanged();
            _ = RetryMindAfterAsync(TimeSpan.Zero);
        }

        return true;
    }

    /// <summary>
    /// Uso 85: with the person's Sí on an unreadable profile (<see cref="ProfileUnreadable"/>), the profile's folder is
    /// set aside with the date (renamed, never deleted: <see cref="ProfileSetAside"/>) and BAXY starts on a new one.
    /// Returns the folder it was set aside as, or null when there is no unreadable profile to set aside; a folder that
    /// could not be renamed throws (IOException, UnauthorizedAccessException) and leaves everything as it was.
    /// </summary>
    internal async Task<string?> StartFreshProfileAsync(CancellationToken cancellationToken)
    {
        if (_isDisposed || _isInitializing || _coreClient is not null || _startupFailure != ProfileUnreadable)
        {
            return null;
        }

        string dataRoot = MemoryOperationProtector.ResolveDataRoot();
        string setAside = await Task.Run(() => ProfileSetAside.SetAside(dataRoot, DateTimeOffset.Now), cancellationToken);
        // The protector read the old profile's key: the new profile's is another.
        _memoryProtector = null;
        _coreRetries.Reset();
        ShellTraceSink.Record(ShellTraceScopes.Startup, "boot", ShellTraceStages.StartupProfileSetAside);
        // A new profile is a new session: nothing of the unreadable one is resumed.
        _coreRecovery = RecoverCoreAsync(recovering: false);
        return setAside;
    }

    private async Task RetryCoreAfterAsync(TimeSpan delay)
    {
        try
        {
            await Task.Delay(delay, _mindLifetimeCancellation.Token);
        }
        catch (Exception exception) when (exception is OperationCanceledException or ObjectDisposedException)
        {
            return;
        }

        if (!_isDisposed && !IsReady && _coreClient is null)
            RecoverCoreWhenIdle();
    }

    private static readonly TimeSpan MindCatalogUpdateBudget = TimeSpan.FromSeconds(120);

    // Ajuste c3 (humos del 31-10): the installed applications the core read after its hello go to a ready mind at once;
    // a mind still starting is given them once it is ready (InitializeMindAsync).
    private async Task SendMindApplicationCatalogAsync(CoreProcessClient core, ApplicationCatalogSnapshot catalog)
    {
        if (!ReferenceEquals(_coreClient, core) || _mindClient is not { IsReady: true } mind)
        {
            return;
        }

        try
        {
            await mind.UpdateApplicationCatalogAsync(catalog, MindCatalogUpdateBudget, _mindLifetimeCancellation.Token);
        }
        catch (Exception exception) when (exception is OperationCanceledException or ObjectDisposedException)
        {
            // The mind or the App is ending; the next mind is configured from the core's current list.
        }
    }

    private void OnCoreDisconnected(CoreProcessClient client)
    {
        if (!ReferenceEquals(_coreClient, client))
        {
            return;
        }

        Volatile.Write(ref _coreDisconnectObserved, 1);
        _uiContext.Post(
            static state =>
            {
                var context = ((MainWindowViewModel Owner, CoreProcessClient Client))state!;
                MainWindowViewModel owner = context.Owner;
                if (owner._isDisposed || !ReferenceEquals(owner._coreClient, context.Client))
                {
                    return;
                }

                owner.IsReady = false;
                owner._loop.Reset(engineRestarted: true);
                if (owner._isInitializing)
                {
                    // A core that ends during its start is that start's failure (HandleStartupFailureAsync), counted once.
                    return;
                }

                // Uso 85: a core that comes up and ends again and again is a breakdown, not one more relaunch; one that
                // ran a while (StartupRetries.Stable) is started again at once, as before.
                if (owner._coreRetries.Failed("core_disconnected", DateTimeOffset.UtcNow) is null)
                {
                    owner.SetStartupFailure(EngineUnavailable);
                    return;
                }

                owner.SetStartupFailure("core_disconnected");
                owner.RecoverCoreWhenIdle();
            },
            (this, client));
    }

    /// <summary>
    /// 2026-09-28: a core that ended mid-turn left input disabled for good. After a disconnect the App restarts it
    /// itself, once the turn in flight has ended.
    /// </summary>
    private void RecoverCoreWhenIdle()
    {
        if (_isDisposed || _isInitializing)
        {
            return;
        }

        if (_turnExecutionActive)
        {
            _coreRecoveryPending = true;
            return;
        }

        _coreRecoveryPending = false;
        _coreRecovery = RecoverCoreAsync();
    }

    private async Task RecoverCoreAsync(bool recovering = true)
    {
        try
        {
            await InitializeAsync(recovering, _mindLifetimeCancellation.Token);
        }
        catch (Exception exception) when (exception is OperationCanceledException or ObjectDisposedException)
        {
            // The shell is closing; there is nothing left to recover.
        }
    }

    /// <summary>A turn that arrives while the core restarts waits for it instead of being refused.</summary>
    internal Task WaitForCoreRecoveryAsync() => _coreRecovery;

    internal static bool IsExpectedStartupFailure(Exception exception) =>
        exception is IOException
            or InvalidDataException
            or InvalidOperationException
            or TimeoutException
            or JsonException
            or Win32Exception
            or UnauthorizedAccessException
            or BadImageFormatException
            or ArgumentException
            or ProtectedPayloadException;

    private void DetachCoreDisconnectedHandler(CoreProcessClient client)
    {
        if (_coreDisconnectedHandler is not null)
        {
            client.Disconnected -= _coreDisconnectedHandler;
            _coreDisconnectedHandler = null;
        }
    }

    // ---- publishing ----------------------------------------------------------------------------------------

    // A voice status that is no longer pending names the start's pieces (the view's start list).
    private async Task RereadVoiceAsync()
    {
        if (_mindClient is not { IsReady: true } mind)
        {
            return;
        }

        try
        {
            MindVoiceStatus? voice = await mind.VoiceStatusAsync(TimeSpan.FromSeconds(10), _mindLifetimeCancellation.Token);
            if (voice is not null)
            {
                // Uso 112: as at the start, its wake word included: the ear that waited for memory has just loaded.
                await ApplyStartupVoiceAsync(mind, voice, _mindLifetimeCancellation.Token);
                if (VoiceFailure == WakeUnavailable && voice.SttAvailable)
                {
                    VoiceFailure = null;
                }

                if (voice.SttAvailable && Interlocked.Exchange(ref _wakeAwaitsEar, 0) != 0)
                {
                    _ = await SetWakeVoiceAsync(true, _mindLifetimeCancellation.Token);
                }
            }
        }
        catch (Exception exception) when (exception is OperationCanceledException or ObjectDisposedException
            or IOException or InvalidOperationException)
        {
            // The mind went away meanwhile: its successor reads its own voice state.
        }
    }

    private void SetVoicePieces(MindVoiceStatus? voice)
    {
        if (voice is not null && !voice.Pending)
        {
            _voicePieces = voice;
            OnPropertyChanged(nameof(VoicePieces));
        }
    }

    private void AddMessageCore(string speaker, string body, bool isUser, string? route = null, bool speak = true,
        string? silent = null)
    {
        // The owner silenced BAXY's voice (Settings): it answers in writing only.
        speak = speak && !Settings.VoiceMuted;
        var message = new ConversationMessage(speaker, body, isUser, DateTimeOffset.Now, route, silent);
        Messages.Add(message);
        MessageAdded?.Invoke(message);
        // The private log of the conversation (owner, 2026-09-20): text, route and time of each turn, local only.
        _conversationLog?.Append(message);
        MindSidecarClient? mind = _mindClient;
        if (mind is { IsVoiceAvailable: true } && (isUser || speak))
        {
            // What BAXY answers is said aloud; the person speaking (or typing) over it stops the voice.
            _ = isUser
                ? mind.VoiceCancelAsync(TimeSpan.FromSeconds(3), CancellationToken.None)
                : mind.VoiceSpeakAsync(body, TimeSpan.FromSeconds(5), CancellationToken.None);
        }
    }

    /// <summary>PRV2 (A2): before a mind writes its trace, the files an earlier version wrote with the person's words go,
    /// once (<see cref="EarlierWords.RemoveOnce"/>); one held open stays for the next start, which never fails for it.</summary>
    private async Task RemoveEarlierWordsAsync(CancellationToken cancellationToken)
    {
        if (_earlierWordsDone || WordsOfEarlierVersions is not { } earlier)
        {
            return;
        }

        EarlierWords.Outcome outcome = await Task.Run(earlier.RemoveOnce, cancellationToken);
        _earlierWordsDone = outcome.Done;
        if (outcome.Removed > 0 || !outcome.Done)
        {
            ShellTraceSink.Record(ShellTraceScopes.Startup, "boot", "earlier_words_removed",
                string.Create(CultureInfo.InvariantCulture, $"files={outcome.Removed} bytes={outcome.Bytes} done={outcome.Done} left={outcome.Left}"));
        }
    }

    /// <summary>Memory forgot everything, or every conversation was deleted: the private log of the conversation goes
    /// too (<see cref="ConversationLog.Clear"/>), and the screens captured and the notes kept beside them (PRV1,
    /// PRIV-02: they stayed).</summary>
    internal void ClearLogAndCaptures()
    {
        _conversationLog?.Clear();
        if (CapturesDirectory is { } directory)
        {
            Baxy.Providers.Windows.Capture.StoredCaptures.ClearAll(directory);
        }
    }

    /// <summary>
    /// PRV1 (PRIV-02): the screens the engine captured are removed (<see cref="StoredCaptures.Clear"/>). A capture is
    /// read by the calls that follow it in the same request, so they go when a turn or a heartbeat ends, unless a call
    /// waits for the person's «sí» (it may be the one that reads the capture), when BAXY closes and when the person
    /// deletes everything.
    /// </summary>
    internal void ClearCaptures()
    {
        if (CapturesDirectory is { } directory)
        {
            Baxy.Providers.Windows.Capture.StoredCaptures.Clear(directory);
        }
    }

    private void ClearCapturesNoCallWaitsFor()
    {
        if (!_loop.HasPendingConfirmation)
        {
            ClearCaptures();
        }
    }

    /// <summary>FT/proveedores goal (review of the App): what BAXY is saying stops (a new conversation, the voice muted
    /// in the settings); before, only the person's own message stopped it.</summary>
    internal void SilenceVoice()
    {
        if (_mindClient is { IsVoiceAvailable: true } mind)
            _ = mind.VoiceCancelAsync(TimeSpan.FromSeconds(3), CancellationToken.None);
    }

    private bool NoticeWouldBeHeard() =>
        Settings.WaitNotice && !Settings.VoiceMuted && _mindClient is { IsVoiceAvailable: true };

    private async Task SpeakNoticeAsync(MindSidecarClient mind, string notice)
    {
        _noticeAsked = notice; // set before asking: it may sound before the acceptance arrives
        if (await mind.VoiceSpeakAsync(notice, TimeSpan.FromSeconds(5), CancellationToken.None, notice: true))
        {
            ShellTraceSink.Record(ShellTraceScopes.Turn, ShellTraceSink.TurnId, "notice.queued");
            NoticeQueued?.Invoke(notice);
        }
    }

    private bool SetField<T>(ref T field, T value, [CallerMemberName] string? propertyName = null)
    {
        if (EqualityComparer<T>.Default.Equals(field, value))
        {
            return false;
        }

        field = value;
        OnPropertyChanged(propertyName);
        return true;
    }

    private void OnPropertyChanged([CallerMemberName] string? propertyName = null)
    {
        PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(propertyName));
    }

    private enum MindStartupState
    {
        NotConfigured,
        Starting,
        Ready,
        Failed,
    }
}
