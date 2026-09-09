using System.Collections.ObjectModel;
using System.ComponentModel;
using System.Globalization;
using System.IO;
using System.Runtime.CompilerServices;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Contracts;
using Baxy.Kernel.Operations;
using Baxy.Kernel.Policy;
using Baxy.Security.Windows;

namespace Baxy.App;

internal sealed class MainWindowViewModel : INotifyPropertyChanged, IAsyncDisposable
{
    private readonly SynchronizationContext _uiContext;
    private readonly string _memorySessionId;
    private readonly Func<MissionInputRoute, RoutedOperation?>? _testTurnResolver;
    private readonly Func<MindSidecarClient> _mindClientFactory;
    private readonly CancellationTokenSource _mindLifetimeCancellation = new();
    private readonly PendingModelMessageQueue _modelMessages;
    private RetryableOperationRegistry? _retryableOperations;
    private CoreProcessClient? _coreClient;
    private MindSidecarClient? _mindClient;
    private Task? _mindInitializationTask;
    private volatile MindStartupState _mindStartupState;
    private DateTime _mindRetryAfterUtc = DateTime.MinValue;
    private bool _isListening;
    private bool _isWakeListening;
    private bool _isVoiceSpeaking;
    private bool _resumeWakeAfterDirect;
    private bool _isMicAvailable;
    private MemoryOperationProtector? _memoryProtector;
    private readonly MemoryTurnSession _memoryTurns;
    private readonly MindPlanSession _mindPlans;
    private readonly PendingNoteInteractionState _pendingNoteInteraction = new();
    private PreparedOperation? _pendingAudioOperation;
    private string? _pendingMindClarificationObjective;
    private Action? _coreDisconnectedHandler;
    private int _coreDisconnectObserved;
    private int _voiceCommandBusy;
    private string _draft = string.Empty;
    private string _statusText = "Iniciando";
    private string _statusDescription = "Preparando BAXY";
    private bool _isReady;
    private bool _isBusy;
    private bool _hasStartupError;
    private bool _hasCompositionError;
    private bool _isInitializing;
    private bool _isDisposed;
    private bool _turnExecutionActive;
    private long _turnTraceSequence;
    private string _currentTurnTraceId = "t0";
    private DateTimeOffset? _lastMilestoneAttemptUtc;
    private Task? _milestoneCompositionTask;

    /// <summary>
    /// Por qué se descartó la respuesta que la mente había redactado en el
    /// último turno, o null si se publicó. Sin esto, degradar a un mensaje de
    /// estado dejaba el turno sin causa y no se distinguía un veto correcto
    /// de uno falso sin repetir la campaña entera.
    /// </summary>
    internal string? LastMindReplyRejection { get; private set; }
    private string? _progressLabel;
    private DateTimeOffset? _lastBaxyVisibleUtc;
    private DateTimeOffset? _firstWakeUtc;

    public MainWindowViewModel()
        : this(testTurnResolver: null)
    {
    }

    internal MainWindowViewModel(
        Func<MissionInputRoute, RoutedOperation?>? testTurnResolver,
        Func<MindSidecarClient>? mindClientFactory = null)
    {
        _uiContext = SynchronizationContext.Current ?? new SynchronizationContext();
        _memorySessionId = Guid.NewGuid().ToString("D");
        _testTurnResolver = testTurnResolver;
        _mindClientFactory =
            mindClientFactory ?? (static () => new MindSidecarClient());
        Messages = new ObservableCollection<ConversationMessage>();
        _modelMessages = new PendingModelMessageQueue(
            WaitForMindReadyAsync,
            PublishComposedMessageAsync,
            failure => InvokeOnUiAsync(() => LastMessageCompositionFailure = failure),
            OnModelMessageQueued,
            () => InvokeOnUiAsync(RestorePresentationState),
            onExhaustedAsync: PublishCompositionFailureAsync,
            isStale: IsStalePendingMessage);
        _mindPlans = new MindPlanSession(
            new MindPlanSession.Host
            {
                Core = () => _coreClient,
                Mind = () => _mindClient,
                Publish = PublishBaxy,
                SetStatus = text => StatusDescription = text,
                TryMarkResolved = TryMarkResolved,
            });
        _memoryTurns = new MemoryTurnSession(
            new MemoryTurnSession.Host
            {
                Core = () => _coreClient,
                Protector = () => _memoryProtector,
                Publish = PublishBaxy,
                SetStatus = text => StatusDescription = text,
                HasPendingAudio = () => _pendingAudioOperation is not null,
                RecoverNotes = RecoverPendingNoteInteraction,
                ContinuePublic = (route, registry, token) =>
                    TryExecuteWithMindAsync(route, registry, token),
            });
    }

    private void PublishBaxy(string body, UserMessageEvent? messageEvent) =>
        AddMessage("BAXY", body, isUser: false, messageEvent: messageEvent);

    private void OnModelMessageQueued()
    {
        OnPropertyChanged(nameof(PendingModelMessageCount));
        // Composition is presentation work, not an executing mission. A slow or
        // recovering narrator must not lock text and voice input indefinitely.
        IsBusy = _turnExecutionActive;
        StatusText = "Trabajando";
        // The Field UI already renders a non-linguistic thinking animation.
        // Leave prose empty until a policy-checked model response is available.
        StatusDescription = string.Empty;
    }

    /// <summary>
    /// Una bienvenida o aviso de voz anterior a un turno no debe publicarse
    /// encima de su respuesta. El acuse de wake también caduca al cerrar escucha.
    /// </summary>
    private bool IsStalePendingMessage(PendingModelMessage pending)
    {
        bool voiceFeedback = (bool?)pending.Facts["voiceFeedback"] == true;
        bool superseded = !string.Equals(
            pending.TraceId, _currentTurnTraceId, StringComparison.Ordinal);
        return ((pending.Draft.Intent == "welcome" || voiceFeedback) && superseded)
            || (voiceFeedback
                && pending.Draft.Intent == "conversation"
                && !IsWakeListening);
    }

    private async Task PublishComposedMessageAsync(
        string text,
        string? failure,
        PendingModelMessage pending) =>
        await InvokeOnUiAsync(
            () =>
            {
                if (_isDisposed || IsStalePendingMessage(pending))
                {
                    return;
                }

                LastMessageCompositionFailure = failure;
                HasCompositionError = false;
                AddMessageCore("BAXY", text, isUser: false, PublicResponseRoute.FromDraft(pending.Draft));
                RestorePresentationState();
            });

    private async Task PublishCompositionFailureAsync(
        PendingModelMessage pending,
        string failure)
    {
        await InvokeOnUiAsync(
            () =>
            {
                if (_isDisposed)
                {
                    return;
                }

                LastMessageCompositionFailure = failure;
                HasCompositionError = true;
                CompositionFailed?.Invoke(pending, failure);
                RestorePresentationState();
            }).ConfigureAwait(false);
    }

    public event PropertyChangedEventHandler? PropertyChanged;

    public event Action<ConversationMessage>? MessageAdded;

    public event Action<PendingModelMessage, string>? CompositionFailed;

    public ObservableCollection<ConversationMessage> Messages { get; }

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
        private set
        {
            if (SetField(ref _statusDescription, value) && _progressLabel is not null)
            {
                _progressLabel = null;
                OnPropertyChanged(nameof(ProgressLabel));
            }
        }
    }

    public string? ProgressLabel => _progressLabel;

    internal void ApplyInProgressSignal(string text, DateTimeOffset? nowUtc = null)
    {
        if (string.IsNullOrWhiteSpace(text))
        {
            return;
        }

        _progressLabel = text.Trim();
        _lastBaxyVisibleUtc = nowUtc ?? DateTimeOffset.UtcNow;
        OnPropertyChanged(nameof(ProgressLabel));
    }

    internal void BeginTurnPresentation(string publicUserText, DateTimeOffset startedUtc)
    {
        AddMessage("Tú", publicUserText, isUser: true);
        _turnExecutionActive = true;
        LastMindReplyRejection = null;
        HasCompositionError = false;
        LastMessageCompositionFailure = null;
        IsBusy = true;
        StatusText = "Trabajando";
        StatusDescription = "understanding";
        ClearProgressLabel();
        _lastBaxyVisibleUtc = startedUtc;
    }

    internal bool TryEmitDueMilestone(DateTimeOffset nowUtc)
    {
        if (!_turnExecutionActive || !IsBusy)
        {
            return false;
        }

        if (!FirstSignal.ShouldEmitMilestone(_lastBaxyVisibleUtc, nowUtc))
        {
            return false;
        }

        if (_lastMilestoneAttemptUtc is { } attempted
            && !FirstSignal.ShouldEmitMilestone(attempted, nowUtc))
        {
            return false;
        }

        // Un aviso de progreso rechazado no puede reintentarse en caliente: sin
        // esta marca, cada tic del temporizador lanzaba otra composición (hasta
        // seis llamadas al modelo) y un turno lento acababa consumiendo miles.
        string userText = Messages.LastOrDefault(static message => message.IsUser)?.Body
            ?? string.Empty;
        int step = 0;
        int total = 0;
        if (_mindPlans.Current is { } plan && plan.Steps.Count > 1)
        {
            step = Math.Min(plan.NextIndex + 1, plan.Steps.Count);
            total = plan.Steps.Count;
        }

        if (UserMessagePolicy.BypassLlmCompositionForTests)
        {
            _lastMilestoneAttemptUtc = nowUtc;
            ApplyInProgressSignal(
                FirstSignal.FormulateProgress(
                    userText,
                    FirstSignal.KindMilestone,
                    step,
                    total),
                nowUtc);
            return true;
        }

        if (_mindClient is not { IsReady: true } mind
            || mind.HasActiveRequest
            || _milestoneCompositionTask is { IsCompleted: false })
        {
            return false;
        }

        _lastMilestoneAttemptUtc = nowUtc;
        _milestoneCompositionTask = ComposeMilestoneAsync(
            mind, userText, _currentTurnTraceId, StatusDescription, step, total);
        return true;
    }

    internal static UserMessageDraft CreateMilestoneDraft(string statusDescription, int step, int total)
    {
        string phase = FieldBridgeContract.ResolveProgress(
            isReady: true, isBusy: true, hasStartupError: false, statusDescription)?.Stage
            ?? FieldProgressNotice.StageWorking;
        var extra = new JsonObject { ["phase"] = phase };
        if (phase == FieldProgressNotice.StageActing && total > 1 && step > 0 && step <= total)
        {
            extra["step"] = step;
            extra["totalSteps"] = total;
        }
        return UserMessagePolicy.Create(TurnVisibleFacts.Status("acting", extra), UserMessageEvent.Status);
    }

    internal bool TryApplyMilestone(string text, string turnId, string statusDescription)
    {
        if (_isDisposed || !_turnExecutionActive || !IsBusy
            || !string.Equals(turnId, _currentTurnTraceId, StringComparison.Ordinal)
            || !string.Equals(statusDescription, StatusDescription, StringComparison.Ordinal))
        {
            return false;
        }
        ApplyInProgressSignal(text);
        return true;
    }

    private async Task ComposeMilestoneAsync(
        MindSidecarClient mind, string userText, string turnId, string statusDescription, int step, int total)
    {
        UserMessageDraft draft = CreateMilestoneDraft(statusDescription, step, total);
        JsonObject facts = ModelMessageComposer.CreateFacts(draft, turnId);
        try
        {
            ModelMessageCompositionOutcome outcome = await ModelMessageComposer.ComposeAsync(
                    draft,
                    userText,
                    facts,
                    mind.ComposeUserMessageAsync,
                    MindSidecarClient.IsCpuFallbackProfile,
                    allowRecovery: false,
                    _mindLifetimeCancellation.Token).ConfigureAwait(false);
            if (outcome.Text is not { Length: > 0 } text)
            {
                return;
            }

            await InvokeOnUiAsync(() =>
            {
                TryApplyMilestone(text, turnId, statusDescription);
            }).ConfigureAwait(false);
        }
        catch (Exception exception) when (ModelMessageComposer.IsTransientFailure(exception))
        {
            // Progress is optional; it cannot replace or fail the final reply.
        }
        catch (OperationCanceledException) when (_mindLifetimeCancellation.IsCancellationRequested)
        {
        }
    }

    internal void ClearProgressLabel()
    {
        if (_progressLabel is null && _lastBaxyVisibleUtc is null)
        {
            return;
        }

        _progressLabel = null;
        _lastBaxyVisibleUtc = null;
        _lastMilestoneAttemptUtc = null;
        OnPropertyChanged(nameof(ProgressLabel));
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

    public DateTimeOffset? FirstWakeUtc => _firstWakeUtc;

    public bool IsMindReady => _mindClient is { IsReady: true };

    public bool CanSend => IsInputEnabled && !string.IsNullOrWhiteSpace(Draft);

    internal string? LastMessageCompositionFailure { get; private set; }

    internal bool HasCompositionError
    {
        get => _hasCompositionError;
        private set => SetField(ref _hasCompositionError, value);
    }

    internal int PendingModelMessageCount => _modelMessages.Count;

    public async Task InitializeAsync(CancellationToken cancellationToken)
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
        _memoryTurns.ResetSession();
        _pendingMindClarificationObjective = null;

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

        try
        {
            _memoryProtector ??= MemoryOperationProtector.CreateDefault(_memorySessionId);
            RetryableOperationRegistry registry = _retryableOperations
                ??= RetryableOperationRegistry.CreateDefault(_memoryProtector);
            _mindPlans.EnsureStore();
            _mindPlans.TryRestore(registry);
            Task<MindRuntimeDiscoveryResult>? mindDiscovery = null;
            if (_testTurnResolver is null)
            {
                _mindStartupState = MindStartupState.Starting;
                mindDiscovery = StartMindRuntimeDiscovery();
            }
            await client.StartAsync(TimeSpan.FromSeconds(10), cancellationToken);
            if (!client.IsReady || Volatile.Read(ref _coreDisconnectObserved) != 0)
            {
                throw new IOException("El motor local se desconectó durante el arranque.");
            }

            // The mind only needs the authenticated capability catalog, which
            // is available as soon as the core handshake completes. Start its
            // model warmup while the private-memory session is initialized so
            // the first user turn does not pay both costs serially.
            if (mindDiscovery is not null)
            {
                _mindInitializationTask = InitializeMindAsync(
                    mindDiscovery,
                    cancellationToken);
            }
            await InitializeMemorySessionAsync(client, _memoryProtector, cancellationToken);
            if (!client.IsReady || Volatile.Read(ref _coreDisconnectObserved) != 0)
            {
                throw new IOException("El motor local se desconectó al iniciar la memoria privada.");
            }

            if (_mindInitializationTask is not null
                && _mindStartupState == MindStartupState.Starting)
            {
                DateTime mindDeadline = DateTime.UtcNow.AddSeconds(12);
                while (_mindClient is not { IsReady: true }
                    && _mindStartupState == MindStartupState.Starting
                    && DateTime.UtcNow < mindDeadline)
                {
                    await Task.Delay(TimeSpan.FromMilliseconds(50), cancellationToken);
                }
            }

            IsReady = true;
            if (!client.IsReady || Volatile.Read(ref _coreDisconnectObserved) != 0)
            {
                throw new IOException("El motor local se desconectó al finalizar el arranque.");
            }

            StatusText = "Lista";
            StatusDescription = "BAXY disponible";
            AddMessage(
                "BAXY",
                TurnVisibleFacts.Welcome(),
                isUser: false,
                messageEvent: UserMessageEvent.Welcome);
            if (_mindPlans.Current is { } restoredPlan)
            {
                AddMessage(
                    "BAXY",
                    MissionNarration.CreateRecoveryPrompt(restoredPlan),
                    isUser: false,
                    messageEvent: UserMessageEvent.Confirmation);
            }
            RecoverPendingAudioOperation(announce: true);
            _memoryTurns.RecoverFrom(registry, announce: true);
            RecoverPendingNoteInteraction(announce: true);
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            throw;
        }
        catch (Exception exception) when (IsExpectedStartupFailure(exception))
        {
            await HandleStartupFailureAsync(client);
        }
        finally
        {
            _isInitializing = false;
        }
    }

    public async Task SubmitAsync(CancellationToken cancellationToken)
    {
        if (!CanSend || _coreClient is null)
        {
            return;
        }

        MissionInput input = new(Draft, MissionInputSource.Text);
        try
        {
            await DispatchMissionInputAsync(
                input,
                () => Draft = string.Empty,
                cancellationToken);
        }
        catch (MissionInputRejectedException)
        {
            PublishInputRejection();
        }
    }

    internal void PublishInputRejection()
    {
        AddMessage(
            "BAXY",
            MissionInputContract.SafeRejectionGuidance,
            isUser: false,
            messageEvent: UserMessageEvent.Clarification);
    }

    internal bool HasPendingPlan => _mindPlans.HasPending;

    internal async Task SubmitAsync(
        MissionInput input,
        CancellationToken cancellationToken)
    {
        if (!IsInputEnabled || _coreClient is null)
        {
            return;
        }

        await DispatchMissionInputAsync(
            input,
            onAccepted: null,
            cancellationToken);
    }

    private Task DispatchMissionInputAsync(
        MissionInput input,
        Action? onAccepted,
        CancellationToken cancellationToken) =>
        MissionInputPipeline.DispatchAsync(
            input,
            async (route, token) =>
            {
                onAccepted?.Invoke();
                await ExecuteMissionInputAsync(route, token);
            },
            cancellationToken);

    private async Task ExecuteMissionInputAsync(
        MissionInputRoute route,
        CancellationToken cancellationToken)
    {
        string text = route.Text;
        if (VoiceListenCommand.TryParse(text, out bool listenEnabled))
        {
            AddMessage("Tú", text, isUser: true);
            bool changed = await SetWakeVoiceAsync(listenEnabled, cancellationToken);
            AddMessage(
                "BAXY",
                VoiceListenVisibleFacts(listenEnabled, changed),
                isUser: false,
                messageEvent: changed
                    ? UserMessageEvent.Status
                    : UserMessageEvent.Error(
                        listenEnabled
                            ? UserMessageDiagnosticCodes.LocalService
                            : UserMessageDiagnosticCodes.ActionNotCompleted));
            return;
        }

        MemoryParseResult memory = route.Memory;
        string publicUserText = memory.MaskPublicProjection
            || NaturalMemoryRequestParser.ContainsSensitiveMaterial(text)
                ? "Solicitud de memoria sensible [contenido oculto / sensitive content hidden]"
                : text;
        string turnTraceId = "t" + Interlocked.Increment(ref _turnTraceSequence)
            .ToString(CultureInfo.InvariantCulture);
        _currentTurnTraceId = turnTraceId;
        ShellTraceSink.TurnId = turnTraceId;
        ShellTraceSink.Record(
            ShellTraceScopes.Turn,
            turnTraceId,
            ShellTraceStages.QueueWaitEnd);
        BeginTurnPresentation(publicUserText, DateTimeOffset.UtcNow);

        try
        {
            RetryableOperationRegistry registry = _retryableOperations
                ?? throw new InvalidOperationException("La cola durable no está disponible.");
            if (_mindPlans.HasPending
                && !NaturalSystemStatusRequestParser.IsCurrentTimeRequest(text)
                && !UserMessagePolicy.IsConnectivityStatusRequest(text))
            {
                await _mindPlans.HandlePendingAsync(text, registry, cancellationToken);
                return;
            }

            if (!_memoryTurns.HasConfirmation && !_memoryTurns.HasPendingOperation
                && _pendingAudioOperation is null && _pendingNoteInteraction.Current is null)
            {
                if (_memoryTurns.TryCancelSaveInput(text))
                {
                    _pendingMindClarificationObjective = null;
                    AddMessage("BAXY", TurnVisibleFacts.Status("memory_cancelled"), isUser: false);
                    return;
                }

                if (_memoryTurns.TryResolveSaveInput(route, out MissionInputRoute? bound))
                {
                    route = bound!;
                    memory = route.Memory;
                    _pendingMindClarificationObjective = null;
                }
            }

            // An explicit private request already has its own typed route or
            // missing-value contract. It supersedes a public clarification;
            // personal context alone still follows the ordinary mind policy.
            if (memory.Outcome is not (MemoryParseOutcome.NoRoute or MemoryParseOutcome.AskToSave))
            {
                _pendingMindClarificationObjective = null;
            }

            if (_pendingMindClarificationObjective is { } pendingObjective)
            {
                // Consume before retrying so a failed/cancelled retry cannot
                // leave stale context behind. A fresh clarify result will
                // preserve the newly combined objective below. The incoming
                // text is first classified without conversation history: a
                // self-contained request supersedes this stale clarification,
                // while a fragment still resumes it.
                _pendingMindClarificationObjective = null;
                if (ConfirmationReplyParser.Parse(text) == ConfirmationReplyKind.Cancel)
                {
                    AddMessage(
                        "BAXY",
                        TurnVisibleFacts.Status("clarification_cancelled"),
                        isUser: false);
                    return;
                }

                if (!await TryExecuteWithMindAsync(
                        route,
                        registry,
                        cancellationToken,
                        pendingClarificationObjective: pendingObjective))
                {
                    AddMessage(
                        "BAXY",
                        TurnVisibleFacts.Failure("ambiguous_clarification"),
                        isUser: false,
                        messageEvent: UserMessageEvent.Error(
                            UserMessageDiagnosticCodes.ActionNotCompleted));
                }

                return;
            }

            if (_memoryTurns.HasConfirmation)
            {
                await _memoryTurns.HandleConfirmationAsync(text, registry, cancellationToken);
                return;
            }

            if (_pendingAudioOperation is not null)
            {
                await HandlePendingAudioOperationAsync(text, registry, cancellationToken);
                return;
            }

            if (_memoryTurns.HasPendingOperation)
            {
                await _memoryTurns.HandlePendingOperationAsync(text, registry, cancellationToken);
                return;
            }

            switch (_pendingNoteInteraction.Current)
            {
                case PendingNoteInteraction.ReconcilingSelection selected:
                    await HandlePendingSelectedNoteAsync(
                        selected,
                        text,
                        registry,
                        cancellationToken);
                    return;
                case PendingNoteInteraction.ReconcilingTitle title:
                    await HandlePendingTitleNoteAsync(
                        title,
                        text,
                        registry,
                        cancellationToken);
                    return;
                case PendingNoteInteraction.AwaitingChoice choice:
                    await HandlePendingNoteChoiceAsync(
                        choice,
                        text,
                        registry,
                        cancellationToken);
                    return;
            }

            switch (memory.Outcome)
            {
                case MemoryParseOutcome.Route when memory.Operation is not null:
                    if (memory.Operation.Name == "memory.recall"
                        && NaturalMemoryRequestParser.RefersToCurrentNameConversation(
                            route.Text,
                            BuildMindHistory().Where(static message => message.Role == "user")
                                .Select(static message => message.Content)))
                    {
                        break;
                    }
                    await _memoryTurns.ExecuteRouteAsync(
                        memory.Operation,
                        registry,
                        durableBeforeSend: true,
                        cancellationToken,
                        route.PublicObjective,
                        route.Source);
                    return;
                case MemoryParseOutcome.ConfirmSensitiveSave when memory.Operation is not null:
                    await _memoryTurns.ExecuteRouteAsync(
                        memory.Operation,
                        registry,
                        durableBeforeSend: false,
                        cancellationToken,
                        route.PublicObjective,
                        route.Source);
                    return;
                case MemoryParseOutcome.ConfirmSensitiveSave:
                    AddMessage(
                        "BAXY",
                        TurnVisibleFacts.Failure("sensitive_data_unparsed"),
                        isUser: false,
                        messageEvent: UserMessageEvent.Error(
                            UserMessageDiagnosticCodes.MissingData));
                    return;
                case MemoryParseOutcome.Clarify:
                    _memoryTurns.AwaitSaveInput(memory);
                    AddMessage(
                        "BAXY",
                        PrivateOperationNarration.CreateMemoryClarification(memory),
                        isUser: false,
                        messageEvent: UserMessageEvent.Clarification);
                    return;
                case MemoryParseOutcome.AskToSave:
                    // Stating personal context does not request persistence,
                    // and may also contain a conversational request. Let the
                    // existing turn policy handle the whole input. Memory
                    // selections still require an explicit parser route:
                    // execution and plan validation reject implicit writes.
                    break;
                case MemoryParseOutcome.SessionContextOnly:
                    AddMessage(
                        "BAXY",
                        TurnVisibleFacts.Status("session_context_only"),
                        isUser: false);
                    return;
                case MemoryParseOutcome.RejectAuthorizationPersistence:
                    AddMessage(
                        "BAXY",
                        TurnVisibleFacts.Status("no_permission_escalation"),
                        isUser: false);
                    return;
                case MemoryParseOutcome.NoRoute when memory.MustNotClaimStandaloneRoute:
                    AddMessage(
                        "BAXY",
                        TurnVisibleFacts.Status("not_a_memory_request"),
                        isUser: false);
                    return;
                case MemoryParseOutcome.NoRoute:
                    break;
                default:
                    throw new InvalidDataException("El resultado del parser de memoria no es válido.");
            }

            // The semantic turn policy is covered by its own real-model gate.
            // Shell integration tests may inject a typed contract oracle so
            // they can exercise execution, retries and projections without a
            // phrase classifier or a heavyweight model in the product path.
            if (_testTurnResolver is not null)
            {
                RoutedOperation? testOperation = _testTurnResolver(route);
                if (testOperation is null)
                {
                    AddMessage(
                        "BAXY",
                        NaturalNoteRequestParser.Guidance,
                        isUser: false,
                        messageEvent: UserMessageEvent.Clarification);
                }
                else
                {
                    await ExecuteRoutedOperationAsync(
                        testOperation,
                        registry,
                        cancellationToken);
                }

                return;
            }

            // La política contextual decide si este turno conversa, necesita
            // una aclaración, ejecuta una acción o abre una misión. Cuando la
            // mente no está disponible se degrada sin ejecutar: no existe una
            // segunda clasificación de lenguaje basada en frases.
            bool handledByMind = await TryExecuteWithMindAsync(
                route,
                registry,
                cancellationToken);
            if (handledByMind)
            {
                return;
            }

            if (MindSidecarClient.IsConfigured
                && UserMessagePolicy.ShouldComposeAsConversationNotError(route.Text)
                && AddMindConversationFallback())
            {
                return;
            }

            bool mindUnavailable = !MindSidecarClient.IsConfigured
                || LastMindReplyRejection == "decision_unavailable";
            AddMessage(
                "BAXY",
                TurnVisibleFacts.Failure(mindUnavailable ? "mind_unavailable" : "ambiguous_request"),
                isUser: false,
                messageEvent: UserMessageEvent.Error(mindUnavailable
                    ? UserMessageDiagnosticCodes.LocalService
                    : UserMessageDiagnosticCodes.ActionNotCompleted));
        }
        catch (TimeoutException)
        {
            ShellTraceSink.Record(
                ShellTraceScopes.Turn,
                turnTraceId,
                ShellTraceStages.TurnError,
                "timeout");
            AddMessage(
                "BAXY",
                TurnVisibleFacts.Failure("timeout"),
                isUser: false,
                messageEvent: UserMessageEvent.Error(UserMessageDiagnosticCodes.Timeout));
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            ShellTraceSink.Record(
                ShellTraceScopes.Turn,
                turnTraceId,
                ShellTraceStages.TurnCancelled);
            return;
        }
        catch (Exception exception) when (
            exception is IOException
                or InvalidDataException
                or InvalidOperationException
                or JsonException
                or UnauthorizedAccessException
                or ProtectedPayloadException)
        {
            ShellTraceSink.Record(
                ShellTraceScopes.Turn,
                turnTraceId,
                ShellTraceStages.TurnError,
                $"{exception.GetType().Name}.{exception.TargetSite?.Name ?? "unknown"}".ToLowerInvariant());
            AddMessage(
                "BAXY",
                TurnVisibleFacts.Failure("result_unverified"),
                isUser: false,
                messageEvent: UserMessageEvent.Error(
                    UserMessageDiagnosticCodes.ActionNotCompleted));
        }
        finally
        {
            ShellTraceSink.Record(
                ShellTraceScopes.Turn,
                turnTraceId,
                ShellTraceStages.ResponseFinal);
            _turnExecutionActive = false;
            RestorePresentationState();
        }
    }

    private static async Task InitializeMemorySessionAsync(
        CoreProcessClient client,
        MemoryOperationProtector protector,
        CancellationToken cancellationToken)
    {
        var status = new MemoryRoutedOperation(
            "memory.status",
            new JsonObject { ["version"] = 1 });
        PreparedOperation prepared = protector.Prepare(status).Prepared;
        OperationResponse response = await client.SendOperationAsync(
            prepared,
            TimeSpan.FromSeconds(20),
            cancellationToken);
        using OpenedBoundProtectedJson opened = protector.OpenResult(response, prepared);
        if (!MemoryOperationResponseProjection.TryCreateCompleted(
                prepared.OperationName,
                opened.Payload,
                out _))
        {
            throw new InvalidDataException("El estado privado inicial no tiene una forma válida.");
        }
    }

    private async Task HandlePendingAudioOperationAsync(
        string text,
        RetryableOperationRegistry registry,
        CancellationToken cancellationToken)
    {
        PreparedOperation pending = _pendingAudioOperation
            ?? throw new InvalidOperationException("No hay un ajuste de audio pendiente.");
        RoutedOperation? routed;
        if (NoteChoiceReplyParser.Parse(text).Kind == NoteChoiceReplyKind.Continue)
        {
            routed = new RoutedOperation(
                pending.OperationName,
                JsonNode.Parse(pending.Arguments.GetRawText())!.AsObject());
        }
        else if (!NaturalNoteRequestParser.TryParse(text, out routed))
        {
            routed = null;
        }

        if (routed is null || !pending.Matches(routed))
        {
            AddMessage(
                "BAXY",
                TurnVisibleFacts.Confirmation(
                    "pending_audio_reconcile",
                    TurnVisibleFacts.ContinueRetry),
                isUser: false,
                messageEvent: UserMessageEvent.Confirmation);
            return;
        }

        await ExecutePreparedOperationAsync(
            pending,
            routed,
            registry,
            allowAmbiguity: false,
            cancellationToken);
    }

    private async Task HandlePendingNoteChoiceAsync(
        PendingNoteInteraction.AwaitingChoice interaction,
        string text,
        RetryableOperationRegistry registry,
        CancellationToken cancellationToken)
    {
        PendingNoteChoice choice = interaction.Choice;
        NoteChoiceReply reply = NoteChoiceReplyParser.Parse(text);
        switch (reply.Kind)
        {
            case NoteChoiceReplyKind.Cancel:
                if (TryMarkResolved(registry, interaction.Source))
                {
                    _pendingNoteInteraction.ClearChoice(interaction);
                    AddMessage("BAXY", "Cancelé la selección. No hice cambios.", isUser: false);
                }

                return;
            case NoteChoiceReplyKind.Next:
                if (!choice.MoveNext())
                {
                    AddMessage("BAXY", "Ya estás en la última página de opciones.", isUser: false);
                    return;
                }

                AddMessage(
                    "BAXY",
                    choice.CreatePrompt(),
                    isUser: false,
                    messageEvent: UserMessageEvent.Clarification);
                return;
            case NoteChoiceReplyKind.Previous:
                if (!choice.MovePrevious())
                {
                    AddMessage("BAXY", "Ya estás en la primera página de opciones.", isUser: false);
                    return;
                }

                AddMessage(
                    "BAXY",
                    choice.CreatePrompt(),
                    isUser: false,
                    messageEvent: UserMessageEvent.Clarification);
                return;
            case NoteChoiceReplyKind.Select:
                if (!choice.TrySelect(reply.Number, out NoteChoiceCandidate? candidate)
                    || candidate is null)
                {
                    AddMessage(
                        "BAXY",
                        $"Esa opción no está visible. Elige un número del {choice.FirstVisibleNumber} al {choice.LastVisibleNumber}, cambia de página o cancela.",
                        isUser: false,
                        messageEvent: UserMessageEvent.Clarification);
                    return;
                }

                RoutedOperation selectedRoute = choice.CreateSelectedRoute(candidate);
                PreparedOperation prepared = registry.ReplaceWithFollowUp(
                    interaction.Source,
                    selectedRoute);
                if (!PendingSelectedNote.TryCreate(
                        prepared,
                        reply.Number,
                        out PendingSelectedNote? selected)
                    || selected is null)
                {
                    throw new InvalidDataException("La selección durable no se pudo validar.");
                }

                _pendingNoteInteraction.PromoteToSelection(interaction, selected);
                await ExecutePreparedOperationAsync(
                    prepared,
                    selectedRoute,
                    registry,
                    allowAmbiguity: false,
                    cancellationToken);
                return;
            case NoteChoiceReplyKind.Invalid:
                if (NaturalNoteRequestParser.TryParse(text, out RoutedOperation? replacement)
                    && replacement is not null)
                {
                    PreparedOperation replacementPrepared = registry.Replace(
                        interaction.Source,
                        replacement);
                    _pendingNoteInteraction.ClearChoice(interaction);
                    await ExecutePreparedOperationAsync(
                        replacementPrepared,
                        replacement,
                        registry,
                        allowAmbiguity: true,
                        cancellationToken);
                    return;
                }

                AddMessage(
                    "BAXY",
                    $"Para esta selección responde con un número del {choice.FirstVisibleNumber} al {choice.LastVisibleNumber}, cambia de página o cancela.",
                    isUser: false,
                    messageEvent: UserMessageEvent.Clarification);
                return;
            default:
                AddMessage(
                    "BAXY",
                    choice.CreatePrompt(),
                    isUser: false,
                    messageEvent: UserMessageEvent.Clarification);
                return;
        }
    }

    private async Task HandlePendingTitleNoteAsync(
        PendingNoteInteraction.ReconcilingTitle interaction,
        string text,
        RetryableOperationRegistry registry,
        CancellationToken cancellationToken)
    {
        PendingTitleNote pending = interaction.Pending;
        NoteChoiceReply reply = NoteChoiceReplyParser.Parse(text);
        bool repeatsOriginalRequest = false;
        if (NaturalNoteRequestParser.TryParse(text, out RoutedOperation? repeated)
            && repeated is not null)
        {
            PreparedOperation candidate = PreparedOperation.Create(repeated.Name, repeated.Arguments);
            repeatsOriginalRequest = string.Equals(
                candidate.IdentityKey,
                pending.Prepared.IdentityKey,
                StringComparison.Ordinal);
        }

        if (reply.Kind != NoteChoiceReplyKind.Continue && !repeatsOriginalRequest)
        {
            AddMessage(
                "BAXY",
                pending.CreateRecoveryPrompt(),
                isUser: false,
                messageEvent: UserMessageEvent.Confirmation);
            return;
        }

        await ExecutePreparedOperationAsync(
            pending.Prepared,
            pending.CreateRoute(),
            registry,
            allowAmbiguity: true,
            cancellationToken);
    }

    private async Task HandlePendingSelectedNoteAsync(
        PendingNoteInteraction.ReconcilingSelection interaction,
        string text,
        RetryableOperationRegistry registry,
        CancellationToken cancellationToken)
    {
        PendingSelectedNote pending = interaction.Pending;
        NoteChoiceReply reply = NoteChoiceReplyParser.Parse(text);
        bool repeatsSelectedNumber = reply.Kind == NoteChoiceReplyKind.Select
            && pending.SelectedNumber is int selectedNumber
            && reply.Number == selectedNumber;
        if (reply.Kind != NoteChoiceReplyKind.Continue && !repeatsSelectedNumber)
        {
            AddMessage(
                "BAXY",
                pending.CreateRecoveryPrompt()
                    + " No cambiaré esa elección mientras su resultado sea incierto.",
                isUser: false,
                messageEvent: UserMessageEvent.Confirmation);
            return;
        }

        await ExecutePreparedOperationAsync(
            pending.Prepared,
            new RoutedOperation(
                pending.Prepared.OperationName,
                JsonNode.Parse(pending.Prepared.Arguments.GetRawText())!.AsObject()),
            registry,
            allowAmbiguity: false,
            cancellationToken);
    }

    public bool IsListening
    {
        get => _isListening;
        private set
        {
            if (SetField(ref _isListening, value))
            {
                OnPropertyChanged(nameof(MicToolTip));
                OnPropertyChanged(nameof(VoiceModeLabel));
                OnPropertyChanged(nameof(VoiceModeToolTip));
            }
        }
    }

    public bool IsWakeListening
    {
        get => _isWakeListening;
        private set
        {
            if (SetField(ref _isWakeListening, value))
            {
                OnPropertyChanged(nameof(VoiceModeLabel));
                OnPropertyChanged(nameof(VoiceModeToolTip));
            }
        }
    }

    public bool IsVoiceSpeaking
    {
        get => _isVoiceSpeaking;
        private set
        {
            if (SetField(ref _isVoiceSpeaking, value))
            {
                OnPropertyChanged(nameof(VoiceModeLabel));
            }
        }
    }

    public bool IsMicAvailable
    {
        get => _isMicAvailable;
        private set
        {
            if (SetField(ref _isMicAvailable, value))
            {
                OnPropertyChanged(nameof(MicToolTip));
                OnPropertyChanged(nameof(VoiceModeLabel));
                OnPropertyChanged(nameof(VoiceModeToolTip));
            }
        }
    }

    public string MicToolTip => !IsMicAvailable
        ? "Micrófono no disponible"
        : IsListening
            ? "Dejar de escuchar"
            : "Hablar con BAXY";

    public string VoiceModeLabel => !IsMicAvailable
        ? "voz · No disponible"
        : IsListening
            ? "voz · Escucha directa"
            : IsWakeListening
                ? IsVoiceSpeaking
                    ? "voz · speaking"
                    : "voz · Activa (di «Baxy»)"
                : "voz · Activar wake word";

    public string VoiceModeToolTip => !IsMicAvailable
        ? "La pila local de voz no está disponible"
        : IsWakeListening
            ? "Desactivar la escucha por «Baxy»"
            : "Escuchar en segundo plano y activarse solo al oír «Baxy»";

    /// <summary>
    /// Alterna la escucha de voz. La transcripción entra por la MISMA puerta
    /// de misión que el texto (MissionInput con fuente VoiceTranscript).
    /// </summary>
    public async Task ToggleVoiceAsync(CancellationToken cancellationToken)
    {
        MindSidecarClient? mind = _mindClient;
        if (mind is null || !mind.IsReady)
        {
            return;
        }

        if (IsListening)
        {
            bool resumed = _resumeWakeAfterDirect
                && await mind.VoiceStartAsync(
                    "wake",
                    TimeSpan.FromSeconds(60),
                    cancellationToken);
            if (!resumed)
            {
                _ = await mind.VoiceStopAsync(TimeSpan.FromSeconds(10), cancellationToken);
            }

            _resumeWakeAfterDirect = false;
            IsListening = false;
            IsWakeListening = resumed;
            StatusDescription = resumed ? "Esperando «Baxy»" : "BAXY disponible";
            return;
        }

        _resumeWakeAfterDirect = IsWakeListening;
        bool started = await mind.VoiceStartAsync(
            "direct",
            TimeSpan.FromSeconds(60),
            cancellationToken);
        if (started)
        {
            IsMicAvailable = true;
            IsListening = true;
            IsWakeListening = false;
            StatusDescription = "Escuchando";
        }
        else
        {
            IsMicAvailable = false;
        }
    }

    public async Task ToggleWakeVoiceAsync(CancellationToken cancellationToken)
    {
        if (Interlocked.CompareExchange(ref _voiceCommandBusy, 1, 0) != 0)
        {
            return;
        }

        try
        {
            await ToggleWakeVoiceCoreAsync(cancellationToken);
        }
        finally
        {
            Volatile.Write(ref _voiceCommandBusy, 0);
        }
    }

    private async Task ToggleWakeVoiceCoreAsync(CancellationToken cancellationToken)
    {
        MindSidecarClient? mind = _mindClient;
        if (mind is null || !mind.IsReady)
        {
            return;
        }

        if (IsWakeListening)
        {
            _ = await mind.VoiceStopAsync(TimeSpan.FromSeconds(10), cancellationToken);
            IsWakeListening = false;
            IsListening = false;
            IsVoiceSpeaking = false;
            _resumeWakeAfterDirect = false;
            StatusDescription = "BAXY disponible";
            return;
        }

        bool started = await mind.VoiceStartAsync(
            "wake",
            TimeSpan.FromSeconds(60),
            cancellationToken);
        if (started)
        {
            IsMicAvailable = true;
            IsListening = false;
            IsWakeListening = true;
            StatusDescription = "Esperando «Baxy»";
        }
        else
        {
            // The direct microphone can still work when only the optional
            // acoustic wake model has not been installed/calibrated.
            IsWakeListening = false;
            StatusDescription = "wake_inactive";
        }
    }

    internal static string VoiceListenVisibleFacts(bool listenEnabled, bool changed)
    {
        if (listenEnabled)
        {
            return changed
                ? TurnVisibleFacts.Status(
                    "wake_listen_on",
                    new JsonObject
                    {
                        ["observed"] = new JsonObject
                        {
                            ["listening"] = true,
                            ["wakeWord"] = "Baxy",
                        },
                    })
                : TurnVisibleFacts.Failure("wake_listen_unavailable");
        }

        return changed
            ? TurnVisibleFacts.Status(
                "wake_listen_off",
                new JsonObject
                {
                    ["observed"] = new JsonObject
                    {
                        ["listening"] = false,
                    },
                })
            : TurnVisibleFacts.Failure("wake_listen_stop_failed");
    }

    internal async Task<bool> SetWakeVoiceAsync(
        bool enabled,
        CancellationToken cancellationToken)
    {
        if (Interlocked.CompareExchange(ref _voiceCommandBusy, 1, 0) != 0)
        {
            return IsWakeListening == enabled;
        }

        try
        {
            return await SetWakeVoiceCoreAsync(enabled, cancellationToken);
        }
        finally
        {
            Volatile.Write(ref _voiceCommandBusy, 0);
        }
    }

    private async Task<bool> SetWakeVoiceCoreAsync(
        bool enabled,
        CancellationToken cancellationToken)
    {
        MindSidecarClient? mind = _mindClient;
        if (mind is null || !mind.IsReady)
        {
            return false;
        }

        if (enabled)
        {
            if (IsWakeListening)
            {
                return true;
            }

            bool started = await mind.VoiceStartAsync(
                "wake",
                TimeSpan.FromSeconds(60),
                cancellationToken);
            if (!started)
            {
                IsWakeListening = false;
                StatusDescription = "wake_inactive";
                return false;
            }

            IsMicAvailable = true;
            IsListening = false;
            IsWakeListening = true;
            IsVoiceSpeaking = false;
            _resumeWakeAfterDirect = false;
            StatusDescription = "Esperando «Baxy»";
            return true;
        }

        if (!IsListening && !IsWakeListening)
        {
            return true;
        }

        bool stopped = await mind.VoiceStopAsync(
            TimeSpan.FromSeconds(10),
            cancellationToken);
        if (stopped)
        {
            IsListening = false;
            IsWakeListening = false;
            IsVoiceSpeaking = false;
            _resumeWakeAfterDirect = false;
            StatusDescription = "BAXY disponible";
        }

        return stopped;
    }

    internal async Task<bool> StartDirectVoiceAsync(CancellationToken cancellationToken)
    {
        MindSidecarClient? mind = _mindClient;
        if (mind is null || !mind.IsReady)
        {
            return false;
        }

        bool started = await mind.VoiceStartAsync(
            "direct",
            TimeSpan.FromSeconds(60),
            cancellationToken);
        if (!started)
        {
            IsMicAvailable = false;
            return false;
        }

        IsMicAvailable = true;
        IsListening = true;
        IsWakeListening = false;
        IsVoiceSpeaking = false;
        _resumeWakeAfterDirect = true;
        StatusDescription = "Escuchando";
        return true;
    }

    internal bool StartNewUiSession()
    {
        if (IsBusy)
        {
            return false;
        }

        _mindPlans.Clear();
        _pendingMindClarificationObjective = null;
        Messages.Clear();
        AddMessage(
            "BAXY",
            TurnVisibleFacts.Welcome(),
            isUser: false,
            messageEvent: UserMessageEvent.Welcome);
        return true;
    }

    private void OnMindTurnSignal(string text)
    {
        string turnId = _currentTurnTraceId;
        string statusDescription = StatusDescription;
        _uiContext.Post(
            _ => TryApplyMilestone(text, turnId, statusDescription),
            null);
    }

    private void OnMindTranscript(string transcript)
    {
        _uiContext.Post(
            _ => _ = DispatchTranscriptAsync(transcript),
            null);
    }

    private void OnMindVoiceEvent(JsonObject voiceEvent)
    {
        string eventName = (string?)voiceEvent["event"] ?? string.Empty;
        string mode = (string?)voiceEvent["mode"] ?? string.Empty;
        bool? speaking = (bool?)voiceEvent["speaking"];
        UserMessageDraft? feedback = TurnVisibleFacts.VoiceFeedback(
            eventName, (string?)voiceEvent["reason"]);
        _uiContext.Post(
            _ =>
            {
                if (_isDisposed)
                {
                    return;
                }

                if (eventName == "state")
                {
                    IsVoiceSpeaking = speaking ?? false;
                    if (mode == "wake")
                    {
                        IsWakeListening = true;
                        IsListening = false;
                    }
                    else if (mode == "direct")
                    {
                        IsWakeListening = false;
                        IsListening = true;
                    }
                    else if (mode == "off")
                    {
                        IsWakeListening = false;
                        IsListening = false;
                    }
                }
                else if (eventName == "wake")
                {
                    StatusDescription = "Te escucho";
                    if (_firstWakeUtc is null)
                    {
                        _firstWakeUtc = DateTimeOffset.UtcNow;
                        OnPropertyChanged(nameof(FirstWakeUtc));
                    }
                }
                else if (eventName == "wake_detected")
                {
                    // Only the dedicated acoustic detector emits this event.
                    // The following ASR turn transcribes content; it does not
                    // decide whether BAXY woke up.
                    StatusDescription = "Te escucho…";
                    if (_firstWakeUtc is null)
                    {
                        _firstWakeUtc = DateTimeOffset.UtcNow;
                        OnPropertyChanged(nameof(FirstWakeUtc));
                    }
                }
                else if (eventName == "partial")
                {
                    StatusDescription = "Transcribiendo…";
                }
                else if (eventName == "barge_in")
                {
                    StatusDescription = "Interrupción detectada";
                }
                else if (eventName == "error")
                {
                    StatusDescription = "La voz se degradó; el motor sigue disponible";
                }

                if (feedback is not null)
                {
                    // Compose asynchronously: waiting here blocks both the UI and
                    // the next voice request. No previous request is invented for
                    // a wake signal or an unintelligible transcript.
                    JsonObject facts = ModelMessageComposer.CreateFacts(
                        feedback, _currentTurnTraceId);
                    facts["voiceFeedback"] = true;
                    _modelMessages.Enqueue(
                        new PendingModelMessage(
                            feedback, string.Empty, facts, _currentTurnTraceId),
                        _mindLifetimeCancellation.Token);
                }
            },
            null);
    }

    private async Task DispatchTranscriptAsync(string transcript)
    {
        if (_isDisposed || !IsInputEnabled)
        {
            return;
        }

        try
        {
            await DispatchMissionInputAsync(
                new MissionInput(transcript, MissionInputSource.VoiceTranscript),
                onAccepted: null,
                CancellationToken.None);
        }
        catch (MissionInputRejectedException)
        {
            AddMessage(
                "BAXY",
                TurnVisibleFacts.Clarification("voice_transcript_unusable"),
                isUser: false,
                messageEvent: UserMessageEvent.Error(
                    UserMessageDiagnosticCodes.ActionNotCompleted));
        }
    }

    /// <summary>
    /// Arranque opcional del sidecar de mente. Nunca bloquea ni degrada el
    /// arranque determinista: si no está configurado o falla, BAXY opera
    /// exactamente como antes.
    /// </summary>
    private Task InitializeMindAsync(CancellationToken cancellationToken)
    {
        _mindStartupState = MindStartupState.Starting;
        return InitializeMindAsync(StartMindRuntimeDiscovery(), cancellationToken);
    }

    internal async Task InitializeMindAsync(
        Task<MindRuntimeDiscoveryResult> discoveryTask,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(discoveryTask);
        using var linkedCancellation = CancellationTokenSource.CreateLinkedTokenSource(
            cancellationToken,
            _mindLifetimeCancellation.Token);
        cancellationToken = linkedCancellation.Token;
        _mindStartupState = MindStartupState.Starting;
        MindRuntimeDiscoveryResult discovery;
        try
        {
            discovery = await discoveryTask.WaitAsync(cancellationToken);
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            _mindStartupState = MindStartupState.Failed;
            _mindRetryAfterUtc = DateTime.UtcNow.AddSeconds(10);
            throw;
        }
        cancellationToken.ThrowIfCancellationRequested();
        if (!MindRuntimeDiscovery.ApplyVerified(discovery)
            || !MindSidecarClient.IsConfigured)
        {
            _mindStartupState = MindStartupState.NotConfigured;
            return;
        }

        if (_mindClient is { IsReady: true })
        {
            _mindStartupState = MindStartupState.Ready;
            return;
        }

        if (_mindClient is not null)
        {
            _mindClient.TranscriptReceived -= OnMindTranscript;
            _mindClient.VoiceEventReceived -= OnMindVoiceEvent;
            _mindClient.TurnSignalReceived -= OnMindTurnSignal;
            await _mindClient.DisposeAsync();
            _mindClient = null;
        }

        _mindStartupState = MindStartupState.Starting;
        MindSidecarClient mind = _mindClientFactory();
        try
        {
            bool started = await mind.TryStartAsync(
                _coreClient?.Capabilities ?? Array.Empty<OperationDescriptor>(),
                _coreClient?.ApplicationCatalog,
                _coreClient?.GameCatalog,
                TimeSpan.FromSeconds(120),
                cancellationToken);
            if (started)
            {
                mind.TranscriptReceived += OnMindTranscript;
                mind.VoiceEventReceived += OnMindVoiceEvent;
                mind.TurnSignalReceived += OnMindTurnSignal;
                _mindClient = mind;
                MindVoiceStatus? voice = await mind.VoiceStatusAsync(
                    TimeSpan.FromSeconds(10),
                    cancellationToken);
                IsMicAvailable = voice?.Available == true || voice?.InputAvailable == true;
                _mindStartupState = MindStartupState.Ready;
                OnPropertyChanged(nameof(IsMindReady));
                if (!IsBusy)
                {
                    StatusDescription = "Todo listo";
                }
                if ((IsMicAvailable || voice?.SttAvailable == true) && WakeOnStartRequested())
                {
                    bool wakeStarted = await mind.VoiceStartAsync(
                        "wake",
                        TimeSpan.FromSeconds(60),
                        cancellationToken);
                    IsWakeListening = wakeStarted;
                    if (wakeStarted)
                    {
                        IsMicAvailable = true;
                        StatusDescription = "Esperando «Baxy»";
                    }
                }
            }
            else
            {
                await mind.DisposeAsync();
                _mindStartupState = MindStartupState.Failed;
                _mindRetryAfterUtc = DateTime.UtcNow.AddSeconds(10);
            }
        }
        catch (Exception)
        {
            await mind.DisposeAsync();
            _mindStartupState = MindStartupState.Failed;
            _mindRetryAfterUtc = DateTime.UtcNow.AddSeconds(10);
        }
    }

    private static Task<MindRuntimeDiscoveryResult> StartMindRuntimeDiscovery() =>
        Task.Run(static () => MindRuntimeDiscovery.DiscoverVerified());

    private async Task<MindSidecarClient?> WaitForMindReadyAsync(
        CancellationToken cancellationToken)
    {
        MindSidecarClient? mind = _mindClient;
        if (mind is { IsReady: true })
        {
            return mind;
        }

        if (!MindSidecarClient.IsConfigured
            && _mindStartupState != MindStartupState.Starting)
        {
            return null;
        }

        if (_mindStartupState == MindStartupState.Ready)
        {
            _mindStartupState = MindStartupState.Failed;
            _mindRetryAfterUtc = DateTime.MinValue;
        }

        Task? initialization = _mindInitializationTask;
        if (_mindStartupState == MindStartupState.Failed
            && DateTime.UtcNow >= _mindRetryAfterUtc
            && !_isDisposed)
        {
            initialization = InitializeMindAsync(cancellationToken);
            _mindInitializationTask = initialization;
        }

        if (_mindStartupState == MindStartupState.Starting && initialization is not null)
        {
            try
            {
                await initialization.WaitAsync(
                    TimeSpan.FromMilliseconds(250),
                    cancellationToken);
            }
            catch (TimeoutException)
            {
                return null;
            }
        }

        mind = _mindClient;
        return mind is { IsReady: true } ? mind : null;
    }

    private static bool WakeOnStartRequested()
    {
        string value = Environment.GetEnvironmentVariable("BAXY_VOICE_WAKE_ON_START")
            ?? string.Empty;
        return value.Equals("1", StringComparison.Ordinal)
            || value.Equals("true", StringComparison.OrdinalIgnoreCase)
            || value.Equals("yes", StringComparison.OrdinalIgnoreCase)
            || value.Equals("on", StringComparison.OrdinalIgnoreCase);
    }

    /// <summary>
    /// Camino de la mente (ADR-0005), fail-closed en cada borde: una política
    /// contextual decide conversación, aclaración, acción o plan; los
    /// argumentos faltantes los extrae el LLM con gramática constreñida; la
    /// conversación general la responde el LLM. Toda operación resultante entra por el MISMO camino
    /// tipado que valida el core (schema, riesgo, confirmaciones). Las
    /// operaciones memory.* nunca se puentean: su canal protegido exige la
    /// gramática determinista, así que aquí solo se ofrece la vía concreta.
    /// </summary>
    /// <summary>
    /// Reduce la clase de turno a una etiqueta estable del vocabulario del
    /// contrato. El registro nunca recibe texto libre ni prosa del modelo.
    /// </summary>
    private static string SanitizedTurnKind(string kind) => kind switch
    {
        "conversation" or "clarify" or "action" or "plan" => kind,
        _ => "invalid",
    };

    private async Task<bool> TryExecuteWithMindAsync(
        MissionInputRoute route,
        RetryableOperationRegistry registry,
        CancellationToken cancellationToken,
        string? pendingClarificationObjective = null)
    {
        // A bare numbered reply is meaningful only while a verified
        // disambiguation is pending. Pending choices are handled before this
        // method, so a number reaching this point must never wait for or enter
        // the neural path.
        bool isContextlessSelection =
            NoteChoiceReplyParser.Parse(route.Text).Kind
            == NoteChoiceReplyKind.Select;
        if (isContextlessSelection)
        {
            return false;
        }

        MindSidecarClient? mind = await WaitForMindReadyAsync(cancellationToken);
        if (mind is null)
        {
            if (_mindStartupState == MindStartupState.Starting
                && _mindInitializationTask is { } initialization)
            {
                try
                {
                    await initialization.WaitAsync(
                        TimeSpan.FromSeconds(30),
                        cancellationToken);
                }
                catch (TimeoutException)
                {
                    // The bounded message below keeps the request fail-closed.
                }

                mind = _mindClient is { IsReady: true } readyMind
                    ? readyMind
                    : null;
            }

            if (mind is null && MindSidecarClient.IsConfigured)
            {
                AddMessage(
                    "BAXY",
                    TurnVisibleFacts.Failure("compose_unavailable"),
                    isUser: false,
                    messageEvent: UserMessageEvent.Error(
                        UserMessageDiagnosticCodes.LocalService));
                return true;
            }

            if (mind is null)
            {
                return false;
            }
        }

        if (NaturalSystemStatusRequestParser.IsCurrentTimeRequest(route.Text))
        {
            return await TryExecuteMindOperationAsync(
                mind,
                route,
                "system.time",
                registry,
                cancellationToken);
        }

        if (UserMessagePolicy.IsConnectivityStatusRequest(route.Text))
        {
            return await TryExecuteMindOperationAsync(
                mind,
                route,
                "network.status",
                registry,
                cancellationToken);
        }

        if (UserMessagePolicy.IsSelfDescriptionQuestion(route.Text))
        {
            AddMessage(
                "BAXY",
                TurnVisibleFacts.Event("conversation"),
                isUser: false,
                messageEvent: UserMessageEvent.Conversation);
            return true;
        }

        if (UserMessagePolicy.IsContinueConstraintRequest(route.Text))
        {
            AddMessage(
                "BAXY",
                TurnVisibleFacts.Event("conversation"),
                isUser: false,
                messageEvent: UserMessageEvent.Conversation);
            return true;
        }

        if (UserMessagePolicy.IsGreetingRequest(route.Text))
        {
            AddMessage(
                "BAXY",
                TurnVisibleFacts.Welcome(),
                isUser: false,
                messageEvent: UserMessageEvent.Welcome);
            return true;
        }

        StatusDescription = "understanding";
        // A pending objective does not erase facts supplied in conversation.
        // The pendingClarification flag below owns the independent reading;
        // dialogue remains reference data, not permission to resume an effect.
        IReadOnlyList<(string Role, string Content)> decisionHistory = BuildMindHistory();
        string decisionTraceId = _currentTurnTraceId;
        ShellTraceSink.Record(
            ShellTraceScopes.Turn,
            decisionTraceId,
            ShellTraceStages.DecisionStart);
        MindTurnDecision? turn = await mind.DecideTurnAsync(
            route.Text,
            decisionHistory,
            MindSidecarClient.TurnDecisionRequestTimeout,
            cancellationToken,
            // Keep this classification independent of the pending objective.
            // A slot fragment still resumes below through MindClarificationPolicy.
            pendingClarification: false);
        ShellTraceSink.Record(
            ShellTraceScopes.Turn,
            decisionTraceId,
            ShellTraceStages.DecisionReady,
            turn is null ? "unavailable" : SanitizedTurnKind(turn.Kind));
        if (turn is null)
        {
            LastMindReplyRejection = "decision_unavailable";
            return UserMessagePolicy.ShouldComposeAsConversationNotError(route.Text)
                && AddMindConversationFallback();
        }

        if (turn.RecoveryFailureCode is { } failureCode)
        {
            _pendingMindClarificationObjective = null;
            AddMessage(
                "BAXY",
                TurnVisibleFacts.Failure(failureCode, new JsonObject
                {
                    ["operationAttempted"] = false,
                    ["retryable"] = true,
                }),
                isUser: false,
                messageEvent: UserMessageEvent.Error(UserMessageDiagnosticCodes.ActionNotCompleted));
            return true;
        }

        if (pendingClarificationObjective is not null
            && MindClarificationPolicy.ShouldResumePendingObjective(
                route.Text,
                turn))
        {
            string clarifiedObjective = MindClarificationPolicy.ResumeObjective(
                pendingClarificationObjective,
                route.Text);
            var clarifiedRoute = new MissionInputRoute(
                clarifiedObjective,
                route.Source,
                NaturalMemoryRequestParser.Classify(clarifiedObjective));
            return await TryExecuteWithMindAsync(
                clarifiedRoute,
                registry,
                cancellationToken);
        }

        if (turn.Kind is "conversation" or "clarify"
            && NaturalSystemStatusRequestParser.IsCurrentTimeRequest(route.Text))
        {
            return await TryExecuteMindOperationAsync(
                mind,
                route,
                "system.time",
                registry,
                cancellationToken);
        }

        if (UserMessagePolicy.IsConnectivityStatusRequest(route.Text))
        {
            return await TryExecuteMindOperationAsync(
                mind,
                route,
                "network.status",
                registry,
                cancellationToken);
        }


        if (turn.Kind == "conversation")
        {
            LastMindReplyRejection =
                UserMessagePolicy.ConversationReplyRejectionReason(
                    route.Text,
                    turn.Reply,
                    turn.ResponseLanguage,
                    string.Join(" ", PreviousUserRequests()));
            if (LastMindReplyRejection is null)
            {
                AddMessage(
                    "BAXY",
                    turn.Reply,
                    isUser: false,
                    formulatedByMind: true,
                    route: PublicResponseRoute.Conversation);
                return true;
            }

            return AddMindConversationFallback(turn.ConversationKind);
        }

        if (turn.Kind == "clarify")
        {
            return AddMindClarification(
                route.Text,
                turn.Question,
                turn.ResponseLanguage,
                turn.PreserveObjective);
        }

        if (turn.Kind == "action"
            && turn.Operation is { Length: > 0 } routedOperation
            // app.close consumes an opaque window identity issued by a prior
            // verified window.resolve. It can never be grounded safely from
            // the user's text alone, so keep the semantic routing decision but
            // send it through the dependency-aware planner below.
            && !string.Equals(routedOperation, "app.close", StringComparison.Ordinal))
        {
            // The mind owns semantic grounding, including contextual requests.
            // The shell's positive fast-path recognizer is not an exhaustive
            // veto: discarding a grounded reading here loses its observed facts.
            return await TryExecuteMindOperationAsync(
                mind,
                route,
                routedOperation,
                registry,
                cancellationToken);
        }

        if ((turn.Kind == "plan"
                || (turn.Kind == "action"
                    && string.Equals(turn.Operation, "app.close", StringComparison.Ordinal)))
            && mind.IsPlannerAvailable)
        {
            StatusDescription = "Preparando los pasos";
            MindPlanResult? plan = await mind.PlanAsync(
                route.Text,
                decisionHistory,
                TimeSpan.FromSeconds(60),
                cancellationToken,
                expectedOperations: turn.EffectOperations);
            if (plan is null || plan.Kind == "failed")
            {
                AddMessage(
                    "BAXY",
                    TurnVisibleFacts.Failure("plan_incomplete"),
                    isUser: false,
                    messageEvent: UserMessageEvent.Error(
                        UserMessageDiagnosticCodes.ActionNotCompleted));
                return true;
            }

            if (plan.Kind == "clarify")
            {
                return AddMindClarification(route.Text, plan.Question);
            }

            if (plan.Kind == "plan")
            {
                try
                {
                    _ = MindPlanBoundary.ValidateAndConvert(route.Text, plan);
                }
                catch (Baxy.Kernel.Planning.MissionPlanValidationException)
                {
                    AddMessage(
                        "BAXY",
                        TurnVisibleFacts.Failure("plan_unverified"),
                        isUser: false,
                        messageEvent: UserMessageEvent.Error(
                            UserMessageDiagnosticCodes.ActionNotCompleted));
                    return true;
                }
                var execution = new PendingMindPlanExecution(route.Text, plan.Steps);
                _mindPlans.Begin(execution);
                await _mindPlans.ExecuteAsync(execution, registry, cancellationToken);
                return true;
            }

            if (plan.Kind == "conversation")
            {
                return AddMindConversationFallback();
            }
        }

        return AddMindConversationFallback();
    }

    private async Task<bool> TryExecuteMindOperationAsync(
        MindSidecarClient mind,
        MissionInputRoute route,
        string operationName,
        RetryableOperationRegistry registry,
        CancellationToken cancellationToken)
    {
        if (operationName.StartsWith("memory.", StringComparison.Ordinal))
        {
            AddMessage(
                "BAXY",
                TurnVisibleFacts.Clarification("memory_needs_explicit_request"),
                isUser: false,
                messageEvent: UserMessageEvent.Clarification);
            return true;
        }

        if (!ProductCatalog.TryGet(
                operationName,
                out ProductOperationDescriptor? descriptor)
            || descriptor is null)
        {
            return AddMindConversationFallback();
        }

        JsonObject groundedArguments;
        if (MindArgumentNormalization.RequiresExtraction(descriptor))
        {
            MindArgumentResult? extraction = await mind.ExtractArgumentResultAsync(
                operationName,
                route.Text,
                MindSidecarClient.ArgumentRequestTimeout,
                cancellationToken,
                BuildMindHistory());

            if (extraction is null)
            {
                return false;
            }

            if (extraction.Arguments is null)
            {
                return AddMindClarification(route.Text, extraction.Question);
            }

            groundedArguments = MindArgumentNormalization.Normalize(
                operationName,
                route.Text,
                extraction.Arguments);
        }
        else
        {
            groundedArguments = new JsonObject();
        }

        var step = new MindPlanStep(
            "step_1",
            operationName,
            "Cumplir exactamente el efecto solicitado.",
            Array.Empty<string>(),
            "literal",
            groundedArguments);
        var execution = new PendingMindPlanExecution(route.Text, [step]);
        _mindPlans.Begin(execution);
        await _mindPlans.ExecuteAsync(execution, registry, cancellationToken);
        return true;
    }

    private bool AddMindClarification(
        string request,
        string question,
        string? responseLanguage = null,
        bool preserveObjective = true)
    {
        // Turn classification, planning and argument extraction share the same
        // pending state. Rewording a rejected question must not turn it into
        // conversation or discard the objective required by the next fragment.
        _pendingMindClarificationObjective = preserveObjective ? request : null;
        if (UserMessagePolicy.IsSafeConversationReply(request, question, responseLanguage, clarification: true))
        {
            AddMessage(
                "BAXY", question, isUser: false, formulatedByMind: true,
                route: PublicResponseRoute.Clarification);
        }
        else
        {
            AddMessage(
                "BAXY", TurnVisibleFacts.Clarification("ambiguous_request"),
                isUser: false, messageEvent: UserMessageEvent.Clarification);
        }
        return true;
    }

    private bool AddMindConversationFallback(string? conversationKind = null)
    {
        // turn.decide already produces the conversational answer. A second
        // open-ended generation used to duplicate the request and could add
        // another timeout after the 22 s turn boundary. Degrade through the
        // bounded LLM message composer instead of restarting semantic work.
        // Failure("model_invalid") used to publish «No pude: unusable answer»
        // for greetings and catalog holes — a polarity flip, not a Core miss.
        string userText = Messages.LastOrDefault(static message => message.IsUser)?.Body
            ?? string.Empty;
        string intent = conversationKind == "unsupported"
            ? "out_of_catalog"
            : UserMessagePolicy.ConversationFallbackIntent(userText);
        switch (intent)
        {
            case "clarification":
                // La pregunta es sobre este pedido: sin guardarlo, el fragmento
                // siguiente («mañana a las 9») se quedaba sin tema.
                _pendingMindClarificationObjective = userText.Length > 0
                    ? userText
                    : null;
                AddMessage(
                    "BAXY",
                    TurnVisibleFacts.Clarification("ambiguous_request"),
                    isUser: false,
                    messageEvent: UserMessageEvent.Clarification);
                return true;
            case "out_of_catalog":
                AddMessage(
                    "BAXY",
                    TurnVisibleFacts.Failure("out_of_catalog"),
                    isUser: false,
                    messageEvent: UserMessageEvent.Error(
                        UserMessageDiagnosticCodes.ActionNotCompleted));
                return true;
            case "welcome":
                AddMessage(
                    "BAXY",
                    TurnVisibleFacts.Welcome(),
                    isUser: false,
                    messageEvent: UserMessageEvent.Welcome);
                return true;
            default:
                // Un pedido que no se reconoce se contesta, no se saluda: la
                // degradación conserva la conversación con el texto del turno.
                AddMessage(
                    "BAXY",
                    TurnVisibleFacts.Event("conversation"),
                    isUser: false,
                    messageEvent: UserMessageEvent.Conversation);
                return true;
        }
    }

    private List<(string Role, string Content)> BuildMindHistory()
    {
        // Six dialogue exchanges are at most twelve role messages. The old
        // value kept only six messages (roughly three exchanges), despite its
        // "turns" name, and could evict the user's contextual fact before the
        // follow-up reached the bounded mind protocol.
        const int maximumMessages = 12;
        var history = new List<(string Role, string Content)>();
        for (int index = Math.Max(0, Messages.Count - maximumMessages);
             index < Messages.Count;
             index++)
        {
            ConversationMessage message = Messages[index];
            history.Add((message.IsUser ? "user" : "assistant", message.Body));
        }

        return history;
    }

    private async Task ExecuteRoutedOperationAsync(
        RoutedOperation routed,
        RetryableOperationRegistry registry,
        CancellationToken cancellationToken)
    {
        PreparedOperation prepared = registry.GetOrAdd(routed);
        await ExecutePreparedOperationAsync(
            prepared,
            routed,
            registry,
            allowAmbiguity: true,
            cancellationToken);
    }

    private async Task ExecutePreparedOperationAsync(
        PreparedOperation prepared,
        RoutedOperation routed,
        RetryableOperationRegistry registry,
        bool allowAmbiguity,
        CancellationToken cancellationToken)
    {
        CoreProcessClient client = _coreClient
            ?? throw new InvalidOperationException("El motor local no está disponible.");
        // La marca del tramo de Core vive dentro de CoreProcessClient, que es
        // el punto por el que pasan todas las rutas de ejecución.
        OperationResponse response = await client.SendOperationAsync(
            prepared,
            TimeSpan.FromSeconds(20),
            cancellationToken);
        if (allowAmbiguity
            && PendingNoteChoice.TryCreate(response, routed, out PendingNoteChoice? choice)
            && choice is not null)
        {
            _pendingNoteInteraction.BeginChoice(choice, prepared);
            AddMessage(
                "BAXY",
                choice.CreatePrompt(),
                isUser: false,
                messageEvent: UserMessageEvent.Clarification);
            return;
        }

        var projection = OperationResponseProjection.Create(response, routed.Name);
        AddMessage(
            "BAXY",
            projection.Message,
            isUser: false,
            messageEvent: string.Equals(
                response.Status,
                OperationStatuses.Completed,
                StringComparison.Ordinal)
                ? UserMessageEvent.Status
                : UserMessageEvent.Error(
                    UserMessageDiagnosticCodes.ActionNotCompleted));
        if (ShouldRetainRetryIdentity(response))
        {
            if (response.Status == OperationStatuses.Pending
                && IsAudioOperation(prepared.OperationName))
            {
                _pendingAudioOperation = prepared;
            }
            else
            {
                AddMessage(
                    "BAXY",
                    TurnVisibleFacts.Status("recovery_identity_kept"),
                    isUser: false);
            }

            return;
        }

        bool resolved = TryMarkResolved(registry, prepared);
        if (_pendingAudioOperation is not null
            && ReferenceEquals(_pendingAudioOperation, prepared)
            && resolved)
        {
            _pendingAudioOperation = null;
            RecoverPendingAudioOperation(announce: true);
            if (_retryableOperations is not null)
            {
                _memoryTurns.RecoverFrom(_retryableOperations, announce: true);
            }
            RecoverPendingNoteInteraction(announce: true);
        }
        else if (resolved && _pendingNoteInteraction.TryClearResolved(prepared))
        {
            RecoverPendingNoteInteraction(announce: true);
        }
    }

    private bool TryMarkResolved(
        RetryableOperationRegistry registry,
        PreparedOperation prepared)
    {
        try
        {
            registry.MarkResolved(prepared);
            return true;
        }
        catch (Exception exception) when (IsDurableStoreFailure(exception))
        {
            AddMessage(
                "BAXY",
                TurnVisibleFacts.Failure("recovery_journal_incomplete"),
                isUser: false,
                messageEvent: UserMessageEvent.Error(
                    UserMessageDiagnosticCodes.ActionNotCompleted));
            return false;
        }
    }

    private void RecoverPendingAudioOperation(bool announce)
    {
        RetryableOperationRegistry? registry = _retryableOperations;
        if (registry is null || _pendingAudioOperation is not null)
        {
            return;
        }

        PreparedOperation? pending = registry
            .SnapshotPendingOperations()
            .FirstOrDefault(static operation => IsAudioOperation(operation.OperationName));
        if (pending is null)
        {
            return;
        }

        _pendingAudioOperation = pending;
        StatusDescription = "Esperando comprobar el audio";
        if (announce)
        {
            AddMessage(
                "BAXY",
                PrivateOperationNarration.CreateAudioRecoveryPrompt(pending),
                isUser: false,
                messageEvent: UserMessageEvent.Confirmation);
        }
    }

    private void RecoverPendingNoteInteraction(bool announce)
    {
        RetryableOperationRegistry? registry = _retryableOperations;
        if (registry is null
            || _pendingAudioOperation is not null
            || _memoryTurns.HasConfirmation
            || _memoryTurns.HasPendingOperation
            || _pendingNoteInteraction.HasPending)
        {
            return;
        }

        PreparedOperation[] pendingOperations = registry.SnapshotPendingOperations().ToArray();
        foreach (PreparedOperation operation in pendingOperations)
        {
            if (!PendingSelectedNote.TryCreate(operation, selectedNumber: null, out PendingSelectedNote? pending)
                || pending is null)
            {
                continue;
            }

            _pendingNoteInteraction.RestoreSelection(pending);
            if (announce)
            {
                AddMessage(
                    "BAXY",
                    pending.CreateRecoveryPrompt(),
                    isUser: false,
                    messageEvent: UserMessageEvent.Confirmation);
            }

            return;
        }

        foreach (PreparedOperation operation in pendingOperations)
        {
            if (!PendingTitleNote.TryCreate(operation, out PendingTitleNote? pending)
                || pending is null)
            {
                continue;
            }

            _pendingNoteInteraction.RestoreTitle(pending);
            if (announce)
            {
                AddMessage(
                    "BAXY",
                    pending.CreateRecoveryPrompt(),
                    isUser: false,
                    messageEvent: UserMessageEvent.Confirmation);
            }

            return;
        }
    }

    public async ValueTask DisposeAsync()
    {
        if (_isDisposed)
        {
            return;
        }

        _isDisposed = true;
        IsReady = false;
        _mindLifetimeCancellation.Cancel();
        await _modelMessages.CloseAsync();
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
        _memoryTurns.ClearConfirmation();
        if (_coreClient is not null)
        {
            DetachCoreDisconnectedHandler(_coreClient);
            await _coreClient.DisposeAsync();
            _coreClient = null;
        }

        if (_mindClient is not null)
        {
            _mindClient.TranscriptReceived -= OnMindTranscript;
            _mindClient.VoiceEventReceived -= OnMindVoiceEvent;
            _mindClient.TurnSignalReceived -= OnMindTurnSignal;
            await _mindClient.DisposeAsync();
            _mindClient = null;
        }
        _mindLifetimeCancellation.Dispose();
    }

    private async Task HandleStartupFailureAsync(CoreProcessClient client)
    {
        _memoryTurns.ClearConfirmation();
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
        AddMessage(
            "BAXY",
            "BAXY no pudo iniciar correctamente. Pulsa reintentar para recuperarlo.",
            isUser: false,
            messageEvent: UserMessageEvent.Error(UserMessageDiagnosticCodes.LocalService));
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
                owner.IsBusy = false;
                owner._memoryTurns.ClearConfirmation();
                owner.HasStartupError = true;
                owner.StatusText = "Desconectada";
                owner.StatusDescription = "Conexión interrumpida";
                owner.AddMessage(
                    "BAXY",
                    TurnVisibleFacts.Failure("core_disconnected"),
                    isUser: false,
                    messageEvent: UserMessageEvent.Error(
                        UserMessageDiagnosticCodes.LocalService));
            },
            (this, client));
    }

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

    internal static bool ShouldRetainRetryIdentity(OperationResponse response)
    {
        ArgumentNullException.ThrowIfNull(response);
        return response.EffectMayHaveOccurred
            || string.Equals(response.Status, OperationStatuses.Pending, StringComparison.Ordinal)
            || string.Equals(
                response.ErrorCode,
                "journal_capacity_reached",
                StringComparison.Ordinal);
    }

    internal static bool IsAudioOperation(string operationName) => operationName is
        "audio.mute" or "audio.volume";

    private static bool IsDurableStoreFailure(Exception exception) =>
        exception is IOException
            or InvalidDataException
            or InvalidOperationException
            or JsonException
            or UnauthorizedAccessException;

    private void DetachCoreDisconnectedHandler(CoreProcessClient client)
    {
        if (_coreDisconnectedHandler is not null)
        {
            client.Disconnected -= _coreDisconnectedHandler;
            _coreDisconnectedHandler = null;
        }
    }

    private void AddMessage(
        string speaker,
        string body,
        bool isUser,
        bool formulatedByMind = false,
        UserMessageEvent? messageEvent = null,
        string? route = null)
    {
        if (formulatedByMind)
        {
            body = UserMessagePolicy.StripLeadingPromptLabels(body);
        }

        if (!isUser
            && string.Equals(speaker, "BAXY", StringComparison.Ordinal)
            && !formulatedByMind
            && !UserMessagePolicy.BypassLlmCompositionForTests)
        {
            UserMessageDraft draft = UserMessagePolicy.Create(
                body,
                messageEvent ?? UserMessageEvent.Status);
            string userText = Messages.LastOrDefault(static message => message.IsUser)?.Body
                ?? string.Empty;
            JsonObject facts = ModelMessageComposer.CreateFacts(
                draft,
                _currentTurnTraceId,
                PreviousPublishedAnswer(),
                PreviousUserRequests());
            var pending = new PendingModelMessage(
                draft,
                userText,
                facts,
                _currentTurnTraceId);
            if (_mindClient is { IsReady: true } mind)
            {
                ShellTraceSink.Record(
                    ShellTraceScopes.Turn,
                    _currentTurnTraceId,
                    ShellTraceStages.ComposeStart,
                    draft.Intent);
                LastMessageCompositionFailure = null;
                ModelMessageCompositionOutcome outcome;
                try
                {
                    outcome = ModelMessageComposer.ComposeAsync(
                            draft,
                            userText,
                            facts,
                            mind.ComposeUserMessageAsync,
                            MindSidecarClient.IsCpuFallbackProfile,
                            allowRecovery: true,
                            CancellationToken.None)
                        .GetAwaiter()
                        .GetResult();
                }
                catch (Exception exception) when (
                    ModelMessageComposer.IsTransientFailure(exception))
                {
                    outcome = new ModelMessageCompositionOutcome(
                        null,
                        "composer_request_failed",
                        UsedRecovery: false);
                }
                finally
                {
                    ShellTraceSink.Record(
                        ShellTraceScopes.Turn,
                        _currentTurnTraceId,
                        ShellTraceStages.ComposeEnd);
                }

                if (IsStalePendingMessage(pending))
                {
                    return;
                }

                if (outcome.Text is { } finalBody)
                {
                    LastMessageCompositionFailure = outcome.Failure;
                    AddMessageCore(
                        "BAXY",
                        finalBody,
                        isUser: false,
                        PublicResponseRoute.FromDraft(draft));
                }
                else
                {
                    LastMessageCompositionFailure = outcome.Failure;
                    pending.Attempts = 1;
                    _modelMessages.Enqueue(pending, _mindLifetimeCancellation.Token);
                }
                return;
            }

            LastMessageCompositionFailure = "composer_unavailable";
            _modelMessages.Enqueue(pending, _mindLifetimeCancellation.Token);
            return;
        }

        AddMessageCore(
            speaker,
            body,
            isUser,
            route
                ?? (formulatedByMind
                    ? PublicResponseRoute.Conversation
                    : messageEvent is null
                        ? null
                        : PublicResponseRoute.FromDraft(
                            UserMessagePolicy.Create(body, messageEvent))));
    }

    private Task<bool> InvokeOnUiAsync(Action action)
    {
        var completion = new TaskCompletionSource<bool>(
            TaskCreationOptions.RunContinuationsAsynchronously);
        _uiContext.Post(
            static state =>
            {
                var invocation = ((Action Action, TaskCompletionSource<bool> Completion))state!;
                try
                {
                    invocation.Action();
                    invocation.Completion.TrySetResult(true);
                }
                catch (Exception exception)
                {
                    invocation.Completion.TrySetException(exception);
                }
            },
            (action, completion));
        return completion.Task;
    }

    private void RestorePresentationState()
    {
        OnPropertyChanged(nameof(PendingModelMessageCount));
        bool hasPendingModelMessage = PendingModelMessageCount > 0;
        IsBusy = _turnExecutionActive;
        if (hasPendingModelMessage)
        {
            StatusText = "Trabajando";
            StatusDescription = string.Empty;
            return;
        }

        if (_turnExecutionActive || !IsReady)
        {
            return;
        }

        ClearProgressLabel();
        StatusText = "Lista";
        StatusDescription = _memoryTurns.HasConfirmation
            ? "Esperando confirmación de memoria"
            : _pendingAudioOperation is not null
            ? "Esperando comprobar el audio"
            : _mindPlans.HasPending
                ? "awaiting_mission_resume"
            : _pendingMindClarificationObjective is not null
                ? "Esperando tu aclaración"
            : _memoryTurns.HasPendingOperation
                ? "Esperando comprobar la memoria"
            : _pendingNoteInteraction.Current
                is PendingNoteInteraction.ReconcilingSelection
                ? "Esperando una comprobación segura"
            : _pendingNoteInteraction.Current
                is PendingNoteInteraction.ReconcilingTitle
                ? "awaiting_request_recovery"
            : _pendingNoteInteraction.Current
                is PendingNoteInteraction.AwaitingChoice
                ? "Esperando tu elección"
                : "BAXY disponible";
    }

    /// <summary>
    /// La última respuesta publicada, para que un seguimiento («¿por qué
    /// importa?») conserve el tema. Un turno acotado, no la conversación
    /// entera: el compositor sólo necesita de qué se estaba hablando.
    /// </summary>
    /// <summary>
    /// Lo que la persona pidió antes en esta conversación, sin el turno en
    /// curso. Un seguimiento elíptico —«¿por qué importa?»— deja su tema en el
    /// pedido anterior; cuando la respuesta de la mente se descarta y compone
    /// el compositor, sin esto contesta en abstracto. Es dato, no instrucción:
    /// quien lo lee es la lectura única del pedido, en la mente.
    /// </summary>
    private List<string> PreviousUserRequests()
    {
        var requests = new List<string>();
        for (int index = Messages.Count - 1; index >= 0 && requests.Count < 6; index--)
        {
            ConversationMessage message = Messages[index];
            if (!message.IsUser)
            {
                continue;
            }

            string body = message.Body.Trim();
            if (body.Length == 0)
            {
                continue;
            }

            requests.Add(body.Length > 320 ? body[..320] : body);
        }

        requests.Reverse();
        return requests;
    }

    private string? PreviousPublishedAnswer()
    {
        for (int index = Messages.Count - 1; index >= 0; index--)
        {
            ConversationMessage message = Messages[index];
            if (message.IsUser
                || !string.Equals(message.Speaker, "BAXY", StringComparison.Ordinal))
            {
                continue;
            }

            string body = message.Body.Trim();
            if (body.Length == 0 || UserMessagePolicy.IsStructuredFacts(body))
            {
                continue;
            }

            return body.Length > 320 ? body[..320] : body;
        }

        return null;
    }

    private void AddMessageCore(
        string speaker,
        string body,
        bool isUser,
        string? route = null)
    {
        // Sólo se descarta una repetición literal. Descartar cualquier segundo
        // mensaje de BAXY hacía desaparecer en silencio avisos distintos —el
        // pendiente de audio, de nota o de memoria— detrás de la bienvenida.
        if (!isUser
            && string.Equals(speaker, "BAXY", StringComparison.Ordinal)
            && Messages.LastOrDefault() is { IsUser: false } previous
            && string.Equals(previous.Speaker, "BAXY", StringComparison.Ordinal)
            && string.Equals(previous.Body, body, StringComparison.Ordinal))
        {
            return;
        }

        var message = new ConversationMessage(
            speaker,
            body,
            isUser,
            DateTimeOffset.Now,
            route);
        Messages.Add(message);
        MessageAdded?.Invoke(message);
        MindSidecarClient? mind = _mindClient;
        if (mind is { IsReady: true })
        {
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
