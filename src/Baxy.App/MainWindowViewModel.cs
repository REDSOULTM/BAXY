using System.Collections.ObjectModel;
using System.ComponentModel;
using System.Globalization;
using System.IO;
using System.Runtime.CompilerServices;
using System.Text.Json;
using Baxy.Contracts;
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
    private readonly NativeTurnLoop _loop;
    // One turn at a time, the person's or the heartbeat's: a person's words that arrive during a heartbeat wait for it.
    private readonly SemaphoreSlim _turnGate = new(1, 1);
    private bool _beatActive;
    private bool _beatSpeaks;
    private readonly ConversationLog? _conversationLog = ConversationLog.CreateDefault();
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
    private int _mindStartupFailureCount;
    private int _coreStartupFailureCount;
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
    private Task _startupVoice = Task.CompletedTask;
    private bool _startupMindPending;
    private bool _isListening;
    private bool _isWakeListening;
    private bool _isVoiceSpeaking;
    private bool _isMicAvailable;
    private string _statusDescription = "Preparando BAXY";
    private bool _isReady;
    private bool _isBusy;
    private string? _startupFailure;
    private string? _lastTurnFailure;
    private string? _voiceFailure;
    private bool _isInitializing;
    private bool _isDisposed;
    private bool _turnExecutionActive;
    private long _turnTraceSequence;
    private bool _isPowered = true;
    private string? _quietProposal;
    private string _beatActivity = string.Empty;
    private MindVoiceStatus? _voicePieces;
    private DateTimeOffset _mindStartedAt = DateTimeOffset.UtcNow;
    private DateTimeOffset? _mindReadyAt;

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
                    // Not said when the owner switched it off or silenced BAXY's voice (it was said even then).
                    if (Settings.WaitNotice && !Settings.VoiceMuted && _mindClient is { IsVoiceAvailable: true } mind)
                    {
                        _ = SpeakNoticeAsync(mind, notice);
                    }
                },
                StepCompleted = step => StepCompleted?.Invoke(step),
                StepStarted = (id, operation, arguments) => StepStarted?.Invoke(id, operation, arguments),
                ConfirmationAsked = asked =>
                {
                    ConfirmationAsked?.Invoke(asked, _beatActive ? _beatActivity : null);
                    if (asked.Proposal && _quietProposal is { } question)
                    {
                        _quietProposal = null;
                        ProposalNotificationRequested?.Invoke(question, SilentBecause(_beatActivity));
                    }
                },
                ConfirmationResolved = outcome => ConfirmationResolved?.Invoke(outcome),
                Refuse = Settings.Refusal,
                MemoryChanged = () => MemoryChanged?.Invoke(),
            });
    }

    /// <summary>What the owner chose in the view's Settings and Proposals panels.</summary>
    internal FieldSettings Settings { get; } = FieldSettings.CreateDefault();

    /// <summary>A call is about to run (the view's chip in progress).</summary>
    internal event Action<string, string, System.Text.Json.Nodes.JsonObject>? StepStarted;

    /// <summary>A call waits for the person's Sí or No; the second value is the heartbeat's reading of the person
    /// when the call is its proposal.</summary>
    internal event Action<NativeTurnConfirmation, string?>? ConfirmationAsked;

    internal event Action<string>? ConfirmationResolved;

    /// <summary>A heartbeat's proposal for a person who should not be spoken to: the model's question and why it is
    /// not said aloud (the Windows notification with Sí / No).</summary>
    internal event Action<string, string>? ProposalNotificationRequested;

    /// <summary>What the ear has heard of the request so far (live captions); it starts nothing.</summary>
    internal event Action<string>? VoicePartial;

    /// <summary>The voice's loudness for the mouth (owner, 2026-10-21: the avatar's speaking animation ended while
    /// BAXY still spoke): a take's levels every <c>step</c> ms from the wall-clock <c>t0</c> it sounds at, or
    /// <c>stop</c>, when the sound was cut. Presentation only.</summary>
    internal event Action<System.Text.Json.Nodes.JsonObject>? VoiceLip;

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

    internal int? MindProcessId => _mindClient?.ProcessId;

    internal DateTimeOffset MindStartedAt => _mindStartedAt;

    internal DateTimeOffset? MindReadyAt => _mindReadyAt;

    internal bool MindFailed => _mindStartupState is MindStartupState.Failed or MindStartupState.NotConfigured;

    private static string SilentBecause(string activity) => activity switch
    {
        HeartbeatMoment.Playing => "estás jugando",
        HeartbeatMoment.InCall => "estás en una llamada",
        HeartbeatMoment.Watching => "estás viendo algo",
        HeartbeatMoment.Away => "no estabas",
        _ => "aviso en pantalla",
    };

    public event PropertyChangedEventHandler? PropertyChanged;

    public event Action<ConversationMessage>? MessageAdded;

    /// <summary>Each call the model made in a turn and what came of it (trace, conductor capture).</summary>
    internal event Action<NativeTurnStep>? StepCompleted;

    /// <summary>The chat changed what the memory holds (the interface reads its count again).</summary>
    internal event Action? MemoryChanged;

    /// <summary>A heartbeat's words for a person who is playing, in a call, watching or away: shown, not spoken.</summary>
    internal event Action<string>? NotificationRequested;

    /// <summary>
    /// The voice accepted the mind's notice of a silent turn (<see cref="SilenceNotice"/>) into its queue: it sounds
    /// after what the voice already holds, or not at all if the voice drops it. It is not a message.
    /// </summary>
    internal event Action<string>? NoticeQueued;

    public ObservableCollection<ConversationMessage> Messages { get; }

    /// <summary>The engine and the private-memory sealing the interface's memory panel uses, the same the chat uses.</summary>
    internal CoreProcessClient? CoreClient => _coreClient;

    internal MemoryOperationProtector? MemoryProtector => _memoryProtector;

    /// <summary>Why the last turn ended without an answer from the model (mind_unavailable, decision_unavailable).</summary>
    internal string? LastTurnFailure
    {
        get => _lastTurnFailure;
        private set
        {
            if (SetField(ref _lastTurnFailure, value))
            {
                OnPropertyChanged(nameof(Failure));
            }
        }
    }

    /// <summary>What the interface shows as the failure: the engine's (retry_without_close, core_disconnected), else the last turn's.</summary>
    internal string? Failure => _startupFailure ?? _lastTurnFailure;

    /// <summary>
    /// The voice's last trouble, until it hears again: voice_dropped_busy (a transcript that arrived while a turn ran
    /// started nothing) or voice_error (the mind's listener failed on a block).
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
    public bool IsMindPreparing => _startupMindPending;

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
        _loop.Reset();

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
            startupCatalog?.TrySetResult(new MindStartupCatalog(
                client.Capabilities,
                client.ApplicationCatalog,
                client.GameCatalog));
            await InitializeMemorySessionAsync(client, _memoryProtector, cancellationToken);
            if (!client.IsReady || Volatile.Read(ref _coreDisconnectObserved) != 0)
            {
                throw new IOException("El motor local se desconectó al iniciar la memoria privada.");
            }

            IsReady = true;
            _coreStartupFailureCount = 0;
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
            await HandleStartupFailureAsync(client);
        }
        finally
        {
            // A core that never said hello hands the mind no catalog: its start ends without it.
            if (startupCatalog?.TrySetCanceled(CancellationToken.None) == true)
            {
                await startupMindAbandoned.CancelAsync();
            }

            _isInitializing = false;
        }
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
        await RunTurnAsync(visible, () => _loop.RunAsync(text, arrivedAt, cancellationToken), cancellationToken);
    }

    /// <summary>
    /// The person pressed Sí (<paramref name="approve"/>) or No on the pending confirmation; the press arrived at
    /// <paramref name="arrivedAt"/>, as in <see cref="SubmitAsync"/>.
    /// </summary>
    internal async Task AnswerConfirmationAsync(bool approve, long arrivedAt, CancellationToken cancellationToken)
    {
        if (!IsInputEnabled || !_loop.HasPendingConfirmation)
        {
            return;
        }

        string label = approve ? "Sí" : "No";
        await RunTurnAsync(label, () => _loop.AnswerConfirmationAsync(approve, label, arrivedAt, cancellationToken),
            cancellationToken);
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
    internal async Task<System.Text.Json.Nodes.JsonArray?> ExportMindSessionAsync(CancellationToken cancellationToken) =>
        _mindClient is { IsReady: true } mind ? await mind.SessionExportAsync(cancellationToken) : null;

    /// <summary>Opens a kept session: nothing pending survives, the mind gets its conversation back and the transcript
    /// the heartbeat reads is that session's words.</summary>
    internal async Task<bool> OpenSessionAsync(System.Text.Json.Nodes.JsonArray? mindConversation,
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
    internal Func<System.Text.Json.Nodes.JsonArray?>? KeptConversation { get; set; }

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
        System.Text.Json.Nodes.JsonObject arguments, CancellationToken cancellationToken)
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
    internal async Task RunBeatAsync(System.Text.Json.Nodes.JsonObject moment, bool speak, CancellationToken cancellationToken)
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
        try
        {
            await _loop.RunBeatAsync(moment, cancellationToken);
        }
        finally
        {
            _beatActive = false;
            _turnGate.Release();
            OnPropertyChanged(nameof(HasPendingConfirmation));
            ShellTraceSink.Record(ShellTraceScopes.Turn, turnTraceId, "beat.end");
        }
    }

    private async Task RunTurnAsync(string visibleUserText, Func<Task> turn, CancellationToken cancellationToken)
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
            await RunGatedTurnAsync(visibleUserText, turn, cancellationToken);
        }
        finally
        {
            if (entered)
            {
                _turnGate.Release();
            }

            IsBusy = false;
        }
    }

    private async Task RunGatedTurnAsync(string visibleUserText, Func<Task> turn, CancellationToken cancellationToken)
    {
        string turnTraceId = "t" + Interlocked.Increment(ref _turnTraceSequence).ToString(CultureInfo.InvariantCulture);
        ShellTraceSink.TurnId = turnTraceId;
        ShellTraceSink.Record(ShellTraceScopes.Turn, turnTraceId, ShellTraceStages.QueueWaitEnd);
        AddMessageCore("Tú", visibleUserText, isUser: true);
        _turnExecutionActive = true;
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
        catch (Exception exception) when (exception is IOException or InvalidDataException
            or InvalidOperationException or JsonException or UnauthorizedAccessException
            or ProtectedPayloadException or TimeoutException)
        {
            LastTurnFailure = "turn_failed";
            ShellTraceSink.Record(ShellTraceScopes.Turn, turnTraceId, ShellTraceStages.TurnError,
                $"{exception.GetType().Name}.{exception.TargetSite?.Name ?? "unknown"}".ToLowerInvariant());
        }
        finally
        {
            ShellTraceSink.Record(ShellTraceScopes.Turn, turnTraceId, ShellTraceStages.ResponseFinal);
            _turnExecutionActive = false;
            IsBusy = false;
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
        : IsWakeListening ? "Esperando «Baxy»"
        : "BAXY disponible";

    /// <summary>A new conversation: the transcript, the model's session and anything pending start over.</summary>
    internal async Task<bool> StartNewUiSessionAsync(CancellationToken cancellationToken)
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
            SilenceVoice();
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
            var list = new MemoryRoutedOperation("memory.list", new System.Text.Json.Nodes.JsonObject
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
                || System.Text.Json.Nodes.JsonNode.Parse(projection.Message) is not System.Text.Json.Nodes.JsonObject facts)
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

        static void Collect(System.Text.Json.Nodes.JsonNode? node, List<string> into)
        {
            switch (node)
            {
                case System.Text.Json.Nodes.JsonObject record
                    when (string?)record["label"] is { } label && (string?)record["value"] is { } value:
                    into.Add($"{label}: {value}");
                    break;
                case System.Text.Json.Nodes.JsonObject other:
                    foreach ((_, System.Text.Json.Nodes.JsonNode? child) in other)
                    {
                        Collect(child, into);
                    }

                    break;
                case System.Text.Json.Nodes.JsonArray items:
                    foreach (System.Text.Json.Nodes.JsonNode? child in items)
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
    internal async Task<System.Text.Json.Nodes.JsonArray> PendingRemindersAsync(CancellationToken cancellationToken)
    {
        var reminders = new System.Text.Json.Nodes.JsonArray();
        if (_coreClient is not { IsReady: true } core || _retryableOperations is not { } registry)
        {
            return reminders;
        }

        try
        {
            PreparedOperation prepared = registry.GetOrAdd(new RoutedOperation(
                "schedule.alarms", new System.Text.Json.Nodes.JsonObject { ["action"] = "list", ["limit"] = 10 }));
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
                reminders.Add(new System.Text.Json.Nodes.JsonObject
                {
                    ["text"] = item.TryGetProperty("title", out JsonElement title) ? title.GetString() : null,
                    ["due"] = item.TryGetProperty("nextRunLocal", out JsonElement due) ? due.GetString() : null,
                });
            }

            // Ronda final 7 (regla 3): past the ten listed, the moment says how many more there are.
            if (result.TryGetProperty("count", out JsonElement count) && count.TryGetInt32(out int total)
                && total > reminders.Count)
            {
                reminders.Add(new System.Text.Json.Nodes.JsonObject
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

    private static async Task InitializeMemorySessionAsync(
        CoreProcessClient client,
        MemoryOperationProtector protector,
        CancellationToken cancellationToken)
    {
        var status = new MemoryRoutedOperation("memory.status", new System.Text.Json.Nodes.JsonObject { ["version"] = 1 });
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
    }

    // ---- voice ---------------------------------------------------------------------------------------------

    public async Task ToggleWakeVoiceAsync(CancellationToken cancellationToken) =>
        _ = await SetWakeVoiceAsync(!IsWakeListening, cancellationToken);

    internal async Task<bool> SetWakeVoiceAsync(bool enabled, CancellationToken cancellationToken)
    {
        await _voiceCommands.WaitAsync(cancellationToken);
        try
        {
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

                bool started = await mind.VoiceStartAsync("wake", TimeSpan.FromSeconds(60), cancellationToken);
                IsWakeListening = started;
                if (started)
                {
                    IsMicAvailable = true;
                    IsListening = false;
                    IsVoiceSpeaking = false;
                }

                StatusDescription = started ? "Esperando «Baxy»" : "wake_inactive";
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
        bool started = await mind.VoiceStartAsync("direct", TimeSpan.FromSeconds(60), cancellationToken);
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
    private void OnMindReadyLost(bool processEnded) => _uiContext.Post(
        _ =>
        {
            if (_isDisposed)
                return;
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
                ShellTraceSink.Record(ShellTraceScopes.Startup, "boot", ShellTraceStages.StartupMindFailed,
                    processEnded ? "mente_salio" : "mente_sin_respuesta");
                _mindStartupFailureCount++;
                _mindStartupState = MindStartupState.Failed;
                _ = RetryMindAfterAsync(MindRetryDelay(_mindStartupFailureCount));
            }
            OnPropertyChanged(nameof(IsMindReady));
        },
        null);

    private void OnMindVoiceEvent(System.Text.Json.Nodes.JsonObject voiceEvent)
    {
        string eventName = (string?)voiceEvent["event"] ?? string.Empty;
        string mode = (string?)voiceEvent["mode"] ?? string.Empty;
        bool? speaking = (bool?)voiceEvent["speaking"];
        string? partial = (string?)voiceEvent["text"];
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
                        IsVoiceSpeaking = speaking ?? false;
                        IsWakeListening = mode == "wake";
                        IsListening = mode == "direct";
                        break;
                    case "wake_detected":
                        VoiceFailure = null;
                        StatusDescription = "Te escucho…";
                        VoiceWake?.Invoke();
                        if (Settings.WakeSound)
                        {
                            WakeChime.Play();
                        }

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
                    case "transcribing":
                        VoiceFailure = null;
                        StatusDescription = "Transcribiendo…";
                        break;
                    case "error":
                        VoiceFailure = "voice_error";
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
        IsMicAvailable = voice?.Available == true || voice?.InputAvailable == true;
        SetVoicePieces(voice);
        if (!StartupWakeApplies(
                voice,
                WakeOnStartRequested(),
                Volatile.Read(ref _personVoiceChoice) != 0,
                IsListening || IsWakeListening))
        {
            return;
        }

        bool wakeStarted = await mind.VoiceStartAsync("wake", TimeSpan.FromSeconds(60), cancellationToken);
        IsWakeListening = wakeStarted;
        if (wakeStarted)
        {
            IsMicAvailable = true;
            if (!IsBusy && Volatile.Read(ref _personVoiceChoice) == 0)
            {
                StatusDescription = "Esperando «Baxy»";
            }
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

    private async Task SettleStartupVoiceAsync(MindSidecarClient mind, CancellationToken cancellationToken)
    {
        try
        {
            MindVoiceStatus? voice = await VoiceStatusSettling.UntilSettledAsync(
                token => ReferenceEquals(_mindClient, mind) && mind.IsReady
                    ? mind.VoiceStatusAsync(TimeSpan.FromSeconds(10), token)
                    : throw new OperationCanceledException("mind_replaced"),
                static (delay, token) => Task.Delay(delay, token),
                cancellationToken);
            if (voice is not null && !voice.Pending && ReferenceEquals(_mindClient, mind))
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

    private async Task InitializeMindAsync(
        Task<MindStartupCatalog> catalog,
        CancellationToken startupAbandoned,
        CancellationToken cancellationToken)
    {
        using var linked = CancellationTokenSource.CreateLinkedTokenSource(
            cancellationToken, startupAbandoned, _mindLifetimeCancellation.Token);
        MindSidecarClient? mind = null;
        bool starting = false;
        try
        {
            await _mindStart.WaitAsync(linked.Token);
            starting = true;
            if (_mindClient is { IsReady: true })
            {
                // The start this one waited for brought the mind up.
                return;
            }

            _mindStartupState = MindStartupState.Starting;
            _mindStartedAt = DateTimeOffset.UtcNow;
            _mindReadyAt = null;
            OnPropertyChanged(nameof(MindStartedAt));
            MindRuntimeDiscoveryResult discovery = await Task.Run(
                static () => MindRuntimeDiscovery.DiscoverVerified(), linked.Token);
            if (!MindRuntimeDiscovery.ApplyVerified(discovery) || !MindSidecarClient.IsConfigured)
            {
                _mindStartupState = MindStartupState.NotConfigured;
                return;
            }

            ShellTraceSink.Record(ShellTraceScopes.Startup, "boot", ShellTraceStages.StartupMindVerified);
            if (_mindClient is not null)
            {
                DetachMind(_mindClient);
                await _mindClient.DisposeAsync();
                _mindClient = null;
            }

            mind = new MindSidecarClient();
            // FT/proveedores goal (review of the App): the mind waits up to 600 s for its model to load (wait_ready in
            // __main__.py) before it says catalog.ready; at 120 s the App ended a slow but healthy load (no GPU, a cold
            // disk) and relaunched it for ever. A model server that dies is told at once (startup_failure).
            if (!await mind.TryStartAsync(catalog, TimeSpan.FromSeconds(600), linked.Token))
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
            _mindClient = mind;
            _mindStartupState = MindStartupState.Ready;
            _mindStartupFailureCount = 0;
            ShellTraceSink.Record(ShellTraceScopes.Startup, "boot", ShellTraceStages.StartupMindReady);
            _mindReadyAt = DateTimeOffset.UtcNow;
            OnPropertyChanged(nameof(IsMindReady));
            MindVoiceStatus? voice = await mind.VoiceStatusAsync(TimeSpan.FromSeconds(10), linked.Token);
            IsMicAvailable = voice?.Available == true || voice?.InputAvailable == true;
            SetVoicePieces(voice);
            if (voice?.Pending == true)
            {
                // The voice runtime is still importing: the mind serves turns now and the voice settles beside them.
                _ = SettleStartupVoiceAsync(mind, _mindLifetimeCancellation.Token);
            }
            else
            {
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
            if (starting)
            {
                _mindStart.Release();
            }

            _startupMindPending = false;
            OnPropertyChanged(nameof(IsMindPreparing));
            if (IsReady && !IsBusy)
            {
                StatusDescription = IdleStatus();
            }
        }
    }

    /// <summary>
    /// r22 (2026-10-09): a model that could not come up is traced with its cause, shown as a state, and retried on its
    /// own with a growing wait (10 s, 20 s, 40 s, then 60 s).
    /// </summary>
    private void RecordMindStartupFailure(MindStartupFailure? failure)
    {
        _mindStartupFailureCount++;
        _mindStartupState = MindStartupState.Failed;
        ShellTraceSink.Record(ShellTraceScopes.Startup, "boot", ShellTraceStages.StartupMindFailed,
            failure?.TraceLabel ?? "desconocida");
        _ = RetryMindAfterAsync(MindRetryDelay(_mindStartupFailureCount));
    }

    internal static TimeSpan MindRetryDelay(int failures) =>
        TimeSpan.FromSeconds(Math.Min(60, 10 * Math.Pow(2, Math.Clamp(failures, 1, 16) - 1)));

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

    public async ValueTask DisposeAsync()
    {
        if (_isDisposed)
        {
            return;
        }

        _isDisposed = true;
        IsReady = false;
        _mindLifetimeCancellation.Cancel();
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

        _mindLifetimeCancellation.Dispose();
    }

    private async Task HandleStartupFailureAsync(CoreProcessClient client)
    {
        _loop.Reset();
        DetachCoreDisconnectedHandler(client);
        await client.DisposeAsync();
        if (ReferenceEquals(_coreClient, client))
        {
            _coreClient = null;
        }

        IsReady = false;
        SetStartupFailure("retry_without_close");
        // FT/proveedores goal (review of the App): a core that could not start (its hello late at a busy sign-in) was
        // never tried again, and BAXY sat in the tray saying «Arrancando»; it is retried with the mind's growing wait.
        _coreStartupFailureCount++;
        _ = RetryCoreAfterAsync(MindRetryDelay(_coreStartupFailureCount));
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
                owner._loop.Reset();
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

    private async Task RecoverCoreAsync()
    {
        try
        {
            await InitializeAsync(recovering: true, _mindLifetimeCancellation.Token);
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

    /// <summary>FT/proveedores goal (review of the App): what BAXY is saying stops (a new conversation, the voice muted
    /// in the settings); before, only the person's own message stopped it.</summary>
    internal void SilenceVoice()
    {
        if (_mindClient is { IsVoiceAvailable: true } mind)
            _ = mind.VoiceCancelAsync(TimeSpan.FromSeconds(3), CancellationToken.None);
    }

    private async Task SpeakNoticeAsync(MindSidecarClient mind, string notice)
    {
        if (await mind.VoiceSpeakAsync(notice, TimeSpan.FromSeconds(5), CancellationToken.None))
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
