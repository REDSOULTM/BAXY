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
    private readonly Func<MindSidecarClient> _mindClientFactory;
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
    private volatile MindStartupState _mindStartupState;
    private MindStartupFailure? _mindStartupFailure;
    private int _mindStartupFailureCount;
    private Action? _coreDisconnectedHandler;
    private int _coreDisconnectObserved;
    private bool _coreRecoveryPending;
    private Task _coreRecovery = Task.CompletedTask;
    private int _voiceCommandBusy;
    // The voice the mind turns on by itself at startup yields to the person: once they give a voice command it never
    // applies, and a command that arrives while it is starting waits for it first.
    private int _personVoiceChoice;
    private Task _startupVoice = Task.CompletedTask;
    private bool _startupMindPending;
    private bool _isListening;
    private bool _isWakeListening;
    private bool _isVoiceSpeaking;
    private bool _isMicAvailable;
    private string _draft = string.Empty;
    private string _statusText = "Iniciando";
    private string _statusDescription = "Preparando BAXY";
    private bool _isReady;
    private bool _isBusy;
    private bool _hasStartupError;
    private bool _isInitializing;
    private bool _isDisposed;
    private bool _turnExecutionActive;
    private long _turnTraceSequence;
    private DateTimeOffset? _firstWakeUtc;

    public MainWindowViewModel()
        : this(mindClientFactory: null)
    {
    }

    internal MainWindowViewModel(Func<MindSidecarClient>? mindClientFactory)
    {
        _uiContext = SynchronizationContext.Current ?? new SynchronizationContext();
        _memorySessionId = Guid.NewGuid().ToString("D");
        _mindClientFactory = mindClientFactory ?? (static () => new MindSidecarClient());
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
                    AddMessageCore("BAXY", text, isUser: false, route, speak: !quiet);
                    if (_beatActive && quiet)
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
                StepCompleted = step => StepCompleted?.Invoke(step),
                MemoryChanged = () => MemoryChanged?.Invoke(),
            });
    }

    public event PropertyChangedEventHandler? PropertyChanged;

    public event Action<ConversationMessage>? MessageAdded;

    /// <summary>Each call the model made in a turn and what came of it (trace, conductor capture).</summary>
    internal event Action<NativeTurnStep>? StepCompleted;

    /// <summary>The chat changed what the memory holds (the interface reads its count again).</summary>
    internal event Action? MemoryChanged;

    /// <summary>A heartbeat's words for a person who is playing, in a call, watching or away: shown, not spoken.</summary>
    internal event Action<string>? NotificationRequested;

    public ObservableCollection<ConversationMessage> Messages { get; }

    /// <summary>The engine and the private-memory sealing the interface's memory panel uses, the same the chat uses.</summary>
    internal CoreProcessClient? CoreClient => _coreClient;

    internal MemoryOperationProtector? MemoryProtector => _memoryProtector;

    /// <summary>Why the last turn ended without an answer from the model (mind_unavailable, decision_unavailable).</summary>
    internal string? LastTurnFailure { get; private set; }

    /// <summary>A risky call waits for the person's Sí or No (the interface shows the two buttons).</summary>
    public bool HasPendingConfirmation => _loop.HasPendingConfirmation;

    public string Draft
    {
        get => _draft;
        set
        {
            if (SetField(ref _draft, value))
            {
                OnPropertyChanged(nameof(CanSend));
            }
        }
    }

    public string StatusText
    {
        get => _statusText;
        private set => SetField(ref _statusText, value);
    }

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
                OnPropertyChanged(nameof(CanSend));
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
                OnPropertyChanged(nameof(CanSend));
            }
        }
    }

    public bool HasStartupError
    {
        get => _hasStartupError;
        private set => SetField(ref _hasStartupError, value);
    }

    public bool IsInputEnabled => IsReady && !IsBusy;

    public bool CanSend => IsInputEnabled && !string.IsNullOrWhiteSpace(Draft);

    public DateTimeOffset? FirstWakeUtc => _firstWakeUtc;

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
        HasStartupError = false;
        IsReady = false;
        StatusText = "Iniciando";
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
            RetryableOperationRegistry registry = _retryableOperations
                ??= RetryableOperationRegistry.CreateDefault(_memoryProtector);
            if (!recovering)
            {
                // A call of an earlier session is never resumed or retried by itself: the person's consent and the
                // screen it was decided on belong to that session.
                registry.RetireWhere(static _ => true);
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
            StatusText = _startupMindPending ? "Iniciando" : "Lista";
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

    public async Task SubmitAsync(CancellationToken cancellationToken)
    {
        if (!CanSend || _coreClient is null)
        {
            return;
        }

        string draft = Draft;
        Draft = string.Empty;
        try
        {
            await SubmitAsync(new MissionInput(draft, MissionInputSource.Text), cancellationToken);
        }
        catch (MissionInputRejectedException)
        {
            // The draft is given back untouched; the composer shows its own limit.
            Draft = draft;
        }
    }

    /// <summary>The person's words (typed, transcribed or sent by the conductor) open a turn.</summary>
    internal async Task SubmitAsync(MissionInput input, CancellationToken cancellationToken)
    {
        if (!IsInputEnabled || _coreClient is null)
        {
            return;
        }

        string text = MissionInputContract.ValidateAndTrim(input);
        // Secrets the person typed never enter the transcript, the conversation log or the voice.
        string visible = SensitiveText.Contains(text) ? SensitiveText.Hidden : text;
        await RunTurnAsync(visible, () => _loop.RunAsync(text, cancellationToken), cancellationToken);
    }

    /// <summary>The person pressed Sí (<paramref name="approve"/>) or No on the pending confirmation.</summary>
    internal async Task AnswerConfirmationAsync(bool approve, CancellationToken cancellationToken)
    {
        if (!IsInputEnabled || !_loop.HasPendingConfirmation)
        {
            return;
        }

        string label = approve ? "Sí" : "No";
        await RunTurnAsync(label, () => _loop.AnswerConfirmationAsync(approve, label, cancellationToken),
            cancellationToken);
    }

    /// <summary>Whether a heartbeat may run now: everything is up and nothing holds the turn or waits for the person.</summary>
    internal bool CanBeat => IsReady && IsMindReady && !IsBusy && !_beatActive && !_loop.HasPendingConfirmation;

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
        await _turnGate.WaitAsync(cancellationToken);
        try
        {
            await RunGatedTurnAsync(visibleUserText, turn, cancellationToken);
        }
        finally
        {
            _turnGate.Release();
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
        StatusText = "Trabajando";
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
                StatusText = "Lista";
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
    internal bool StartNewUiSession()
    {
        if (IsBusy)
        {
            return false;
        }

        _loop.Reset();
        Messages.Clear();
        if (_mindClient is { IsReady: true } mind)
        {
            _ = mind.NewSessionAsync(CancellationToken.None);
        }

        OnPropertyChanged(nameof(HasPendingConfirmation));
        StatusDescription = IdleStatus();
        return true;
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
        if (Interlocked.CompareExchange(ref _voiceCommandBusy, 1, 0) != 0)
        {
            return IsWakeListening == enabled;
        }

        try
        {
            await AwaitStartupVoiceAsync();
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
            Volatile.Write(ref _voiceCommandBusy, 0);
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
        _uiContext.Post(_ => _ = DispatchTranscriptAsync(transcript), null);
    }

    private async Task DispatchTranscriptAsync(string transcript)
    {
        if (_isDisposed || !IsInputEnabled)
        {
            return;
        }

        try
        {
            await SubmitAsync(new MissionInput(transcript, MissionInputSource.VoiceTranscript), CancellationToken.None);
        }
        catch (MissionInputRejectedException)
        {
            // An unusable transcript starts no turn.
        }
    }

    private void OnMindVoiceEvent(System.Text.Json.Nodes.JsonObject voiceEvent)
    {
        string eventName = (string?)voiceEvent["event"] ?? string.Empty;
        string mode = (string?)voiceEvent["mode"] ?? string.Empty;
        bool? speaking = (bool?)voiceEvent["speaking"];
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
                        StatusDescription = "Te escucho…";
                        if (_firstWakeUtc is null)
                        {
                            _firstWakeUtc = DateTimeOffset.UtcNow;
                            OnPropertyChanged(nameof(FirstWakeUtc));
                        }

                        break;
                    case "partial":
                        StatusDescription = "Transcribiendo…";
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
        _mindStartupState = MindStartupState.Starting;
        MindSidecarClient? mind = null;
        try
        {
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

            mind = _mindClientFactory();
            if (!await mind.TryStartAsync(catalog, TimeSpan.FromSeconds(120), linked.Token))
            {
                RecordMindStartupFailure(mind.LastStartupFailure);
                await mind.DisposeAsync();
                return;
            }

            mind.TranscriptReceived += OnMindTranscript;
            mind.VoiceEventReceived += OnMindVoiceEvent;
            Volatile.Write(ref _personVoiceChoice, 0);
            _mindClient = mind;
            _mindStartupState = MindStartupState.Ready;
            _mindStartupFailure = null;
            _mindStartupFailureCount = 0;
            ShellTraceSink.Record(ShellTraceScopes.Startup, "boot", ShellTraceStages.StartupMindReady);
            OnPropertyChanged(nameof(IsMindReady));
            MindVoiceStatus? voice = await mind.VoiceStatusAsync(TimeSpan.FromSeconds(10), linked.Token);
            IsMicAvailable = voice?.Available == true || voice?.InputAvailable == true;
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

            if (_mindStartupState == MindStartupState.Starting)
            {
                _mindStartupState = MindStartupState.Failed;
            }
        }
        finally
        {
            _startupMindPending = false;
            OnPropertyChanged(nameof(IsMindPreparing));
            if (IsReady && !IsBusy)
            {
                StatusText = "Lista";
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
        _mindStartupFailure = failure;
        _mindStartupFailureCount++;
        _mindStartupState = MindStartupState.Failed;
        ShellTraceSink.Record(ShellTraceScopes.Startup, "boot", ShellTraceStages.StartupMindFailed,
            failure?.TraceLabel ?? "desconocida");
        _ = RetryMindAfterAsync(MindRetryDelay(_mindStartupFailureCount));
    }

    internal static TimeSpan MindRetryDelay(int failures) =>
        TimeSpan.FromSeconds(Math.Min(60, 10 * Math.Pow(2, Math.Clamp(failures, 1, 16) - 1)));

    /// <summary>The cause of a model that is not up, for the interface's state; null when it is up or unknown.</summary>
    internal string? MindUnavailableCause() =>
        _mindStartupState == MindStartupState.Starting ? "iniciando" : _mindStartupFailure?.Cause;

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
        HasStartupError = true;
        StatusText = "No disponible";
        StatusDescription = "retry_without_close";
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
                owner.HasStartupError = true;
                owner.StatusText = "Desconectada";
                owner.StatusDescription = "core_disconnected";
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

    private void AddMessageCore(string speaker, string body, bool isUser, string? route = null, bool speak = true)
    {
        var message = new ConversationMessage(speaker, body, isUser, DateTimeOffset.Now, route);
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
