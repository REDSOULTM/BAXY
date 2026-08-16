using System.Collections.ObjectModel;
using System.ComponentModel;
using System.Globalization;
using System.IO;
using System.Runtime.CompilerServices;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Contracts;
using Baxy.Kernel.Operations;
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
    private DurablePlanStore? _planStore;
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
    private PendingMemoryConfirmation? _pendingMemoryConfirmation;
    private bool _pendingMemoryConfirmationIsDurable;
    private bool _pendingMemoryConfirmationRequiresReconciliation;
    private PreparedOperation? _pendingMemoryOperation;
    private PendingPublicAfterMemory? _pendingPublicAfterMemory;
    private bool _pendingMemoryRecoveryAnnounced;
    private readonly PendingNoteInteractionState _pendingNoteInteraction = new();
    private PreparedOperation? _pendingAudioOperation;
    private PendingMindPlanExecution? _pendingMindPlan;
    private string? _pendingMindClarificationObjective;
    private Action? _coreDisconnectedHandler;
    private int _coreDisconnectObserved;
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
    private string _currentTurnTraceId = "t0";

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
            OnModelMessageQueued);
    }

    private void OnModelMessageQueued()
    {
        IsBusy = true;
        StatusText = "Trabajando";
        // The Field UI already renders a non-linguistic thinking animation.
        // Leave prose empty until a policy-checked model response is available.
        StatusDescription = string.Empty;
    }

    private async Task PublishComposedMessageAsync(string text, string? failure) =>
        await InvokeOnUiAsync(
            () =>
            {
                if (_isDisposed)
                {
                    return;
                }

                LastMessageCompositionFailure = failure;
                AddMessageCore("BAXY", text, isUser: false);
                RestorePresentationState();
            });

    public event PropertyChangedEventHandler? PropertyChanged;

    public event Action<ConversationMessage>? MessageAdded;

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

    internal string? LastMessageCompositionFailure { get; private set; }

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
        ClearVolatileMemoryConfirmation();
        _pendingMindClarificationObjective = null;
        _pendingMemoryOperation = null;
        _pendingMemoryRecoveryAnnounced = false;

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
            _retryableOperations ??= RetryableOperationRegistry.CreateDefault(_memoryProtector);
            _planStore ??= DurablePlanStore.CreateDefault();
            _pendingMindPlan ??= _planStore.Load(_retryableOperations);
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
                "Hola. Estoy lista para ayudarte con este equipo.",
                isUser: false,
                messageEvent: UserMessageEvent.Welcome);
            if (_pendingMindPlan is not null)
            {
                AddMessage(
                    "BAXY",
                    MissionNarration.CreateRecoveryPrompt(_pendingMindPlan),
                    isUser: false,
                    messageEvent: UserMessageEvent.Confirmation);
            }
            RecoverPendingAudioOperation(announce: true);
            RecoverPendingMemoryOperation(announce: true);
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
            AddMessage(
                "BAXY",
                MissionInputContract.SafeRejectionGuidance,
                isUser: false,
                messageEvent: UserMessageEvent.Clarification);
        }
    }

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
        AddMessage("Tú", publicUserText, isUser: true);

        _turnExecutionActive = true;
        IsBusy = true;
        StatusText = "Trabajando";
        StatusDescription = "Entendiendo tu petición";

        try
        {
            RetryableOperationRegistry registry = _retryableOperations
                ?? throw new InvalidOperationException("La cola durable no está disponible.");
            if (_pendingMindPlan is not null)
            {
                await HandlePendingMindPlanAsync(text, registry, cancellationToken);
                return;
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
                if (!await TryExecuteWithMindAsync(
                        route,
                        registry,
                        cancellationToken,
                        pendingClarificationObjective: pendingObjective))
                {
                    AddMessage(
                        "BAXY",
                        "No pude interpretar la aclaración con suficiente seguridad. No ejecuté ninguna acción.",
                        isUser: false,
                        messageEvent: UserMessageEvent.Error(
                            UserMessageDiagnosticCodes.ActionNotCompleted));
                }

                return;
            }

            if (_pendingMemoryConfirmation is not null)
            {
                await HandlePendingMemoryConfirmationAsync(text, registry, cancellationToken);
                return;
            }

            if (_pendingAudioOperation is not null)
            {
                await HandlePendingAudioOperationAsync(text, registry, cancellationToken);
                return;
            }

            if (_pendingMemoryOperation is not null)
            {
                await HandlePendingMemoryOperationAsync(text, registry, cancellationToken);
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
                    await ExecuteMemoryRouteAsync(
                        memory.Operation,
                        registry,
                        durableBeforeSend: true,
                        cancellationToken,
                        route.PublicObjective,
                        route.Source);
                    return;
                case MemoryParseOutcome.ConfirmSensitiveSave when memory.Operation is not null:
                    await ExecuteMemoryRouteAsync(
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
                        "No pude aislar el dato sensible de forma segura. No lo guardé ni lo envié para ejecución.",
                        isUser: false,
                        messageEvent: UserMessageEvent.Error(
                            UserMessageDiagnosticCodes.MissingData));
                    return;
                case MemoryParseOutcome.Clarify:
                    AddMessage(
                        "BAXY",
                        PrivateOperationNarration.CreateMemoryClarification(memory),
                        isUser: false,
                        messageEvent: UserMessageEvent.Clarification);
                    return;
                case MemoryParseOutcome.AskToSave:
                    AddMessage(
                        "BAXY",
                        "Entendí ese dato como contexto, pero no lo guardaré sin una petición explícita. Si quieres conservarlo, dime exactamente qué debo recordar.",
                        isUser: false);
                    return;
                case MemoryParseOutcome.SessionContextOnly:
                    AddMessage(
                        "BAXY",
                        "Entendí que es solo contexto de esta sesión. No lo guardé ni ejecuté una acción de memoria.",
                        isUser: false);
                    return;
                case MemoryParseOutcome.RejectAuthorizationPersistence:
                    AddMessage(
                        "BAXY",
                        "No guardaré autorizaciones generales ni ampliaré mis permisos. Cada acción seguirá limitada y sujeta a sus propias reglas de seguridad.",
                        isUser: false);
                    return;
                case MemoryParseOutcome.NoRoute when memory.MustNotClaimStandaloneRoute:
                    AddMessage(
                        "BAXY",
                        "No interpreté ese mensaje como una petición independiente de memoria y no guardé, borré ni inventé información.",
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

            AddMessage(
                "BAXY",
                MindSidecarClient.IsConfigured
                    ? "No pude interpretar esa petición con suficiente seguridad. No ejecuté ninguna acción."
                    : "La inteligencia local no está disponible todavía. No ejecuté ninguna acción.",
                isUser: false,
                messageEvent: MindSidecarClient.IsConfigured
                    ? UserMessageEvent.Error(UserMessageDiagnosticCodes.ActionNotCompleted)
                    : UserMessageEvent.Error(UserMessageDiagnosticCodes.LocalService));
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
                "Necesité más tiempo del esperado. No repetí ninguna acción; puedes intentarlo de nuevo.",
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
                "unavailable");
            AddMessage(
                "BAXY",
                "No pude completar la petición de forma segura; no afirmaré que terminó.",
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

    private async Task HandlePendingMemoryConfirmationAsync(
        string text,
        RetryableOperationRegistry registry,
        CancellationToken cancellationToken)
    {
        PendingMemoryConfirmation pending = _pendingMemoryConfirmation
            ?? throw new InvalidOperationException("No hay una confirmación de memoria activa.");
        switch (ConfirmationReplyParser.Parse(text))
        {
            case ConfirmationReplyKind.Invalid:
                AddMessage(
                    "BAXY",
                    _pendingMemoryConfirmationRequiresReconciliation
                        ? "Para reconciliar esta acción responde únicamente «confirmar / confirm». Esa respuesta no reenvió nada y el resultado anterior sigue incierto."
                        : "Para esta acción de memoria responde únicamente «confirmar / confirm» o «cancelar / cancel». No ejecuté nada.",
                    isUser: false,
                    messageEvent: UserMessageEvent.Confirmation);
                return;
            case ConfirmationReplyKind.Cancel:
                if (_pendingMemoryConfirmationRequiresReconciliation)
                {
                    AddMessage(
                        "BAXY",
                        "No puedo afirmar que la acción no ocurrió ni retirar su identidad: pudo haber comenzado antes de perderse la respuesta. Responde «confirmar / confirm» para reconciliar exactamente el mismo intento.",
                        isUser: false,
                        messageEvent: UserMessageEvent.Confirmation);
                    return;
                }

                if (!TryRemoveMemoryOperation(registry, pending.Prepared))
                {
                    AddMessage(
                        "BAXY",
                        "No pude retirar de forma segura la petición pendiente. No la ejecuté y seguiré bloqueando otras acciones hasta comprobar su estado.",
                        isUser: false,
                        messageEvent: UserMessageEvent.Error(
                            UserMessageDiagnosticCodes.ActionNotCompleted));
                    return;
                }

                ClearPendingPublicAfterMemory(pending.Prepared);
                ClearVolatileMemoryConfirmation();
                AddMessage("BAXY", "Cancelé la acción de memoria. No la ejecuté.", isUser: false);
                ContinueMemoryRecovery(registry);
                return;
            case ConfirmationReplyKind.Confirm:
                PreparedOperation prepared = pending.Prepared;
                if (!_pendingMemoryConfirmationIsDurable)
                {
                    MemoryOperationProtector protector = _memoryProtector
                        ?? throw new InvalidOperationException("La protección de memoria no está disponible.");
                    prepared = registry.GetOrAdd(protector.AuthenticateForOutbox(prepared));
                    _pendingMemoryConfirmationIsDurable = true;
                }

                // Once a grant leaves the shell, an effect may occur even if
                // the response is lost. Cancellation must remain conservative.
                _pendingMemoryConfirmationRequiresReconciliation = true;

                await SendMemoryPreparedOperationAsync(
                    prepared,
                    registry,
                    isDurable: true,
                    pending.Token,
                    cancellationToken);
                return;
            default:
                throw new InvalidDataException("La respuesta de confirmación no es válida.");
        }
    }

    private async Task HandlePendingMemoryOperationAsync(
        string text,
        RetryableOperationRegistry registry,
        CancellationToken cancellationToken)
    {
        PreparedOperation pending = _pendingMemoryOperation
            ?? throw new InvalidOperationException("No hay una operación de memoria por reconciliar.");
        if (NoteChoiceReplyParser.Parse(text).Kind != NoteChoiceReplyKind.Continue)
        {
            AddMessage(
                "BAXY",
                PrivateOperationNarration.CreateMemoryRecoveryPrompt(pending),
                isUser: false,
                messageEvent: UserMessageEvent.Confirmation);
            return;
        }

        await SendMemoryPreparedOperationAsync(
            pending,
            registry,
            isDurable: true,
            confirmationToken: null,
            cancellationToken);
    }

    private async Task ExecuteMemoryRouteAsync(
        MemoryRoutedOperation routed,
        RetryableOperationRegistry registry,
        bool durableBeforeSend,
        CancellationToken cancellationToken,
        string? publicObjective = null,
        MissionInputSource publicSource = MissionInputSource.Text)
    {
        MemoryOperationProtector protector = _memoryProtector
            ?? throw new InvalidOperationException("La protección de memoria no está disponible.");
        ProtectedMemoryOperation protectedOperation = protector.Prepare(routed);
        PreparedOperation prepared = durableBeforeSend
            ? registry.GetOrAdd(protectedOperation)
            : protectedOperation.Prepared;
        if (!string.IsNullOrWhiteSpace(publicObjective))
        {
            _pendingPublicAfterMemory = new PendingPublicAfterMemory(
                prepared,
                publicObjective,
                publicSource);
        }
        await SendMemoryPreparedOperationAsync(
            prepared,
            registry,
            durableBeforeSend,
            confirmationToken: null,
            cancellationToken);
    }

    private async Task SendMemoryPreparedOperationAsync(
        PreparedOperation prepared,
        RetryableOperationRegistry registry,
        bool isDurable,
        string? confirmationToken,
        CancellationToken cancellationToken)
    {
        CoreProcessClient client = _coreClient
            ?? throw new InvalidOperationException("El motor local no está disponible.");
        MemoryOperationProtector protector = _memoryProtector
            ?? throw new InvalidOperationException("La protección de memoria no está disponible.");
        OperationResponse response = await client.SendOperationAsync(
            prepared,
            TimeSpan.FromSeconds(20),
            cancellationToken,
            confirmationToken);

        if (PendingMemoryConfirmation.TryCreate(
                response,
                prepared,
                TimeProvider.System,
                out PendingMemoryConfirmation? challenge)
            && challenge is not null)
        {
            _pendingMemoryConfirmation = challenge;
            _pendingMemoryConfirmationIsDurable = isDurable;
            _pendingMemoryConfirmationRequiresReconciliation =
                challenge.ReconciliationRequired;
            if (IsSameMemoryOperation(_pendingMemoryOperation, prepared))
            {
                _pendingMemoryOperation = null;
                _pendingMemoryRecoveryAnnounced = false;
            }

            AddMessage(
                "BAXY",
                PrivateOperationNarration.CreateMemoryConfirmationPrompt(
                    prepared,
                    challenge.ReconciliationRequired),
                isUser: false,
                messageEvent: UserMessageEvent.Confirmation);
            return;
        }

        // A sensitive draft is deliberately non-durable. The only acceptable
        // first response is a validated challenge; no other response may turn
        // the RAM-only draft into a success claim or an outbox entry.
        if (!isDurable)
        {
            ClearPendingPublicAfterMemory(prepared);
            AddMessage(
                "BAXY",
                "No recibí una confirmación segura para guardar ese dato sensible. No lo añadí a la cola de recuperación.",
                isUser: false,
                messageEvent: UserMessageEvent.Error(
                    UserMessageDiagnosticCodes.ActionNotCompleted));
            return;
        }

        if (string.Equals(response.Status, OperationStatuses.Completed, StringComparison.Ordinal))
        {
            try
            {
                using OpenedBoundProtectedJson opened = protector.OpenResult(response, prepared);
                if (!MemoryOperationResponseProjection.TryCreateCompleted(
                        prepared.OperationName,
                        opened.Payload,
                        out MemoryOperationResponseProjection? projection,
                        response.Replayed)
                    || projection is null)
                {
                    throw new InvalidDataException("La respuesta privada no admite una proyección segura.");
                }

                AddMessage("BAXY", projection.Message, isUser: false);
            }
            catch
            {
                ClearMemoryConfirmationFor(prepared);
                SetPendingMemoryOperation(registry, prepared);
                throw;
            }

            ClearMemoryConfirmationFor(prepared);
            ResolveMemoryOperation(registry, prepared);
            await ContinuePendingPublicAfterMemoryAsync(
                prepared,
                registry,
                cancellationToken);
            return;
        }

        AddMessage(
            "BAXY",
            PrivateOperationNarration.CreateMemoryFailureMessage(prepared.OperationName, response),
            isUser: false,
            messageEvent: UserMessageEvent.Error(
                UserMessageDiagnosticCodes.ActionNotCompleted));
        if (ShouldRetainRetryIdentity(response))
        {
            if (confirmationToken is null || _pendingMemoryConfirmation is null)
            {
                SetPendingMemoryOperation(registry, prepared);
            }

            return;
        }

        ClearPendingPublicAfterMemory(prepared);
        ClearMemoryConfirmationFor(prepared);
        ResolveMemoryOperation(registry, prepared);
    }

    private async Task ContinuePendingPublicAfterMemoryAsync(
        PreparedOperation predecessor,
        RetryableOperationRegistry registry,
        CancellationToken cancellationToken)
    {
        PendingPublicAfterMemory? continuation = _pendingPublicAfterMemory;
        if (continuation is null
            || !IsSameMemoryOperation(continuation.Predecessor, predecessor))
        {
            return;
        }

        _pendingPublicAfterMemory = null;
        var publicRoute = new MissionInputRoute(
            continuation.Objective,
            continuation.Source,
            MemoryParseResult.NoRoute());
        if (!await TryExecuteWithMindAsync(publicRoute, registry, cancellationToken))
        {
            AddMessage(
                "BAXY",
                "No pude interpretar esa petición con suficiente seguridad. No ejecuté ninguna acción.",
                isUser: false,
                messageEvent: UserMessageEvent.Error(
                    UserMessageDiagnosticCodes.ActionNotCompleted));
        }
    }

    private void ClearPendingPublicAfterMemory(PreparedOperation predecessor)
    {
        if (_pendingPublicAfterMemory is { } continuation
            && IsSameMemoryOperation(continuation.Predecessor, predecessor))
        {
            _pendingPublicAfterMemory = null;
        }
    }

    private void ResolveMemoryOperation(
        RetryableOperationRegistry registry,
        PreparedOperation prepared)
    {
        if (!TryRemoveMemoryOperation(registry, prepared))
        {
            SetPendingMemoryOperation(registry, prepared);
            return;
        }

        if (IsSameMemoryOperation(_pendingMemoryOperation, prepared))
        {
            _pendingMemoryOperation = null;
            _pendingMemoryRecoveryAnnounced = false;
        }

        ContinueMemoryRecovery(registry);
    }

    private bool TryRemoveMemoryOperation(
        RetryableOperationRegistry registry,
        PreparedOperation prepared)
    {
        try
        {
            PreparedOperation? registered = registry
                .SnapshotPendingOperations()
                .FirstOrDefault(candidate => IsSameMemoryOperation(candidate, prepared));
            if (registered is null)
            {
                return true;
            }

            registry.MarkResolved(registered);
            return !registry
                .SnapshotPendingOperations()
                .Any(candidate => IsSameMemoryOperation(candidate, prepared));
        }
        catch (Exception exception) when (IsDurableStoreFailure(exception))
        {
            AddMessage(
                "BAXY",
                "No pude cerrar el registro protegido de recuperación. Lo conservaré sin iniciar otra acción.",
                isUser: false,
                messageEvent: UserMessageEvent.Error(
                    UserMessageDiagnosticCodes.ActionNotCompleted));
            return false;
        }
    }

    private void SetPendingMemoryOperation(
        RetryableOperationRegistry registry,
        PreparedOperation prepared)
    {
        _pendingMemoryOperation = registry
            .SnapshotPendingOperations()
            .FirstOrDefault(candidate => IsSameMemoryOperation(candidate, prepared))
            ?? prepared;
        _pendingMemoryRecoveryAnnounced = false;
        AnnouncePendingMemoryRecoveryIfReady();
    }

    private void ContinueMemoryRecovery(RetryableOperationRegistry registry)
    {
        RecoverPendingMemoryOperation(announce: true);
        RecoverPendingNoteInteraction(announce: true);
    }

    private void ClearMemoryConfirmationFor(PreparedOperation prepared)
    {
        if (_pendingMemoryConfirmation is not null
            && IsSameMemoryOperation(_pendingMemoryConfirmation.Prepared, prepared))
        {
            ClearVolatileMemoryConfirmation();
        }
    }

    private void ClearVolatileMemoryConfirmation()
    {
        _pendingMemoryConfirmation = null;
        _pendingMemoryConfirmationIsDurable = false;
        _pendingMemoryConfirmationRequiresReconciliation = false;
    }

    private static bool IsSameMemoryOperation(
        PreparedOperation? left,
        PreparedOperation right) =>
        left is not null
        && string.Equals(left.IdentityKey, right.IdentityKey, StringComparison.Ordinal)
        && string.Equals(left.MissionId, right.MissionId, StringComparison.Ordinal)
        && string.Equals(left.InvocationId, right.InvocationId, StringComparison.Ordinal);

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
                "Primero debo reconciliar el ajuste de audio pendiente. Responde «continuar / continue / retry» o repite la misma petición de volumen o silencio; no iniciaré otra acción mientras su resultado siga incierto.",
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
                pending.CreateRecoveryPrompt()
                    + " No iniciaré otra acción mientras este resultado siga pendiente.",
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
                    ? "voz · Hablando (puedes interrumpir)"
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
        if (mind is null || !mind.IsReady || !IsMicAvailable)
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
        MindSidecarClient? mind = _mindClient;
        if (mind is null || !mind.IsReady || !IsMicAvailable)
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
            IsListening = false;
            IsWakeListening = true;
            StatusDescription = "Esperando «Baxy»";
        }
        else
        {
            // The direct microphone can still work when only the optional
            // acoustic wake model has not been installed/calibrated.
            IsWakeListening = false;
            StatusDescription = "Falta activar el modelo de wake; puedes usar el micrófono";
        }
    }

    internal async Task<bool> SetWakeVoiceAsync(
        bool enabled,
        CancellationToken cancellationToken)
    {
        MindSidecarClient? mind = _mindClient;
        if (mind is null || !mind.IsReady || !IsMicAvailable)
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
                StatusDescription = "Falta activar el modelo de wake; puedes usar el micrófono";
                return false;
            }

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
        if (mind is null || !mind.IsReady || !IsMicAvailable)
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

        Messages.Clear();
        AddMessage(
            "BAXY",
            "Hola. Estoy lista para ayudarte con este equipo.",
            isUser: false,
            messageEvent: UserMessageEvent.Welcome);
        return true;
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
                }
                else if (eventName == "wake_detected")
                {
                    // Only the dedicated acoustic detector emits this event.
                    // The following ASR turn transcribes content; it does not
                    // decide whether BAXY woke up.
                    StatusDescription = "Te escucho…";
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
                "No pude usar esa transcripción de voz. ¿Puedes repetirlo?",
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
                _mindClient = mind;
                _mindStartupState = MindStartupState.Ready;
                if (!IsBusy)
                {
                    StatusDescription = "Todo listo";
                }
                MindVoiceStatus? voice = await mind.VoiceStatusAsync(
                    TimeSpan.FromSeconds(10),
                    cancellationToken);
                IsMicAvailable = voice?.Available == true;
                if (IsMicAvailable && WakeOnStartRequested())
                {
                    bool wakeStarted = await mind.VoiceStartAsync(
                        "wake",
                        TimeSpan.FromSeconds(60),
                        cancellationToken);
                    IsWakeListening = wakeStarted;
                    if (wakeStarted)
                    {
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
                AddMessage(
                    "BAXY",
                    "Un momento, estoy preparando esa respuesta.",
                    isUser: false,
                    messageEvent: UserMessageEvent.Status);
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
                    "No pude terminar esa respuesta. Volveré a preparar el servicio automáticamente.",
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

        StatusDescription = "Entendiendo tu petición";
        IReadOnlyList<(string Role, string Content)> decisionHistory =
            pendingClarificationObjective is null
                ? BuildMindHistory()
                : [];
        string decisionTraceId = _currentTurnTraceId;
        ShellTraceSink.Record(
            ShellTraceScopes.Turn,
            decisionTraceId,
            ShellTraceStages.DecisionStart);
        MindTurnDecision? turn = await mind.DecideTurnAsync(
            route.Text,
            decisionHistory,
            MindSidecarClient.TurnDecisionRequestTimeout,
            cancellationToken);
        ShellTraceSink.Record(
            ShellTraceScopes.Turn,
            decisionTraceId,
            ShellTraceStages.DecisionReady,
            turn is null ? "unavailable" : SanitizedTurnKind(turn.Kind));
        if (turn is null)
        {
            return false;
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

        if (turn.Kind == "conversation")
        {
            if (UserMessagePolicy.IsSafeConversationReply(route.Text, turn.Reply))
            {
                AddMessage("BAXY", turn.Reply, isUser: false, formulatedByMind: true);
                return true;
            }

            return AddMindConversationFallback();
        }

        if (turn.Kind == "clarify")
        {
            _pendingMindClarificationObjective = turn.PreserveObjective
                ? route.Text
                : null;
            if (UserMessagePolicy.IsSafeConversationReply(route.Text, turn.Question))
            {
                AddMessage("BAXY", turn.Question, isUser: false, formulatedByMind: true);
            }
            else
            {
                AddMessage(
                    "BAXY",
                    "Necesito un poco más de contexto para continuar de forma segura.",
                    isUser: false,
                    messageEvent: UserMessageEvent.Clarification);
            }

            return true;
        }

        if (turn.Kind == "action"
            && turn.Operation is { Length: > 0 } routedOperation
            // app.close consumes an opaque window identity issued by a prior
            // verified window.resolve. It can never be grounded safely from
            // the user's text alone, so keep the semantic routing decision but
            // send it through the dependency-aware planner below.
            && !string.Equals(routedOperation, "app.close", StringComparison.Ordinal))
        {
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
                    "No pude construir un plan completo y seguro. No ejecuté una versión parcial de tu petición.",
                    isUser: false,
                    messageEvent: UserMessageEvent.Error(
                        UserMessageDiagnosticCodes.ActionNotCompleted));
                return true;
            }

            if (plan.Kind == "clarify")
            {
                _pendingMindClarificationObjective = route.Text;
                AddMessage(
                    "BAXY",
                    plan.Question,
                    isUser: false,
                    messageEvent: UserMessageEvent.Clarification);
                return true;
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
                        "No pude verificar el plan completo y no ejecuté ninguna acción. Puedes reformular la petición o intentarlo de nuevo.",
                        isUser: false,
                        messageEvent: UserMessageEvent.Error(
                            UserMessageDiagnosticCodes.ActionNotCompleted));
                    return true;
                }
                var execution = new PendingMindPlanExecution(route.Text, plan.Steps);
                _pendingMindPlan = execution;
                PersistMindPlan(execution);
                await ExecuteMindPlanAsync(execution, registry, cancellationToken);
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
                "Entendí que quieres usar la memoria privada, pero necesito la " +
                "petición explícita para no equivocarme con tus datos. Por " +
                "ejemplo: «recuerda que …», «qué sabes de …» u «olvida …».",
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
                cancellationToken);

            if (extraction is null)
            {
                return false;
            }

            if (extraction.Arguments is null)
            {
                if (!UserMessagePolicy.IsSafeConversationReply(
                        route.Text,
                        extraction.Question))
                {
                    return false;
                }

                _pendingMindClarificationObjective = route.Text;
                AddMessage(
                    "BAXY",
                    extraction.Question,
                    isUser: false,
                    formulatedByMind: true);
                return true;
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
        _pendingMindPlan = execution;
        PersistMindPlan(execution);
        await ExecuteMindPlanAsync(execution, registry, cancellationToken);
        return true;
    }

    private async Task ExecuteMindPlanAsync(
        PendingMindPlanExecution execution,
        RetryableOperationRegistry registry,
        CancellationToken cancellationToken)
    {
        CoreProcessClient client = _coreClient
            ?? throw new InvalidOperationException("El motor local no está disponible.");
        MindSidecarClient mind = _mindClient
            ?? throw new InvalidOperationException("La mente local no está disponible.");

        while (execution.NextIndex < execution.Steps.Count)
        {
            MindPlanStep step = execution.CurrentStep;
            StatusDescription = execution.Steps.Count == 1
                ? "Ejecutando la petición"
                : $"Ejecutando paso {execution.NextIndex + 1} de {execution.Steps.Count}";
            JsonObject? arguments = step.Arguments?.DeepClone() as JsonObject;
            JsonObject? identityArguments = null;
            JsonArray groundingObservations = [];
            if (string.Equals(
                    step.ArgumentsMode,
                    "after_dependencies",
                    StringComparison.Ordinal))
            {
                if (!PlanObservationProjector.TrySelectVerifiedDependencies(
                        step,
                        execution.Observations,
                        out groundingObservations))
                {
                    FinishMindPlanWithFailure(
                        execution,
                        "No pude verificar los resultados necesarios para el siguiente paso. La misión quedó detenida sin ejecutar ese efecto.");
                    return;
                }

                if (PlanObservationProjector.TryGroundIdentityArguments(
                        step,
                        groundingObservations,
                        out identityArguments)
                    && identityArguments is not null)
                {
                    arguments ??= new JsonObject();
                    foreach ((string key, JsonNode? value) in identityArguments)
                    {
                        arguments[key] = value?.DeepClone();
                    }
                }
            }
            if (arguments is null
                || !MindPlanBoundary.ArgumentsSatisfyExactSchema(
                    step.Operation,
                    arguments))
            {
                arguments = await mind.GroundPlanStepAsync(
                    execution.Objective,
                    step,
                    groundingObservations,
                    TimeSpan.FromSeconds(30),
                    cancellationToken);

                if (arguments is null)
                {
                    FinishMindPlanWithFailure(
                        execution,
                        "No pude obtener los datos exactos para el siguiente paso. La misión quedó detenida sin ejecutar ese efecto.");
                    return;
                }

                // Opaque identities come only from verified dependency
                // observations. The mind may fill remaining literals, but it
                // cannot replace that authority with another value.
                if (identityArguments is not null)
                {
                    foreach ((string key, JsonNode? value) in identityArguments)
                    {
                        arguments[key] = value?.DeepClone();
                    }
                }
            }

            arguments = MindArgumentNormalization.Normalize(
                step.Operation,
                execution.Objective,
                arguments);
            if (string.Equals(
                    step.ArgumentsMode,
                    "after_dependencies",
                    StringComparison.Ordinal)
                && !PlanObservationProjector
                    .ArgumentsUseVerifiedDependencyAuthority(
                        step.Operation,
                        arguments,
                        groundingObservations))
            {
                FinishMindPlanWithFailure(
                    execution,
                    "No pude vincular de forma segura el resultado anterior con el siguiente paso. La misión quedó detenida sin ejecutar ese efecto.");
                return;
            }

            MindPlanBoundary.ValidateGroundedArguments(step.Operation, arguments);
            var routed = new RoutedOperation(step.Operation, arguments);
            PreparedOperation prepared = execution.PendingOperation
                ?? registry.GetOrAdd(routed);
            execution.PendingOperation = prepared;
            PersistMindPlan(execution);
            OperationResponse response = await client.SendOperationAsync(
                prepared,
                TimeSpan.FromSeconds(20),
                cancellationToken);
            if (PendingOperationConfirmation.TryCreate(
                    response,
                    prepared,
                    TimeProvider.System,
                    out PendingOperationConfirmation? confirmation)
                && confirmation is not null)
            {
                StageMindPlanConfirmation(execution, confirmation);
                return;
            }

            if (response.Status == OperationStatuses.Pending)
            {
                execution.PendingEffectMayHaveOccurred |= response.EffectMayHaveOccurred;
                _pendingMindPlan = execution;
                PersistMindPlan(execution);
                AddMessage(
                    "BAXY",
                    response.EffectMayHaveOccurred
                        ? $"El paso {execution.NextIndex + 1} quedó inconcluso y el efecto puede haber ocurrido. No continuaré ni lo repetiré a ciegas."
                        : $"El paso {execution.NextIndex + 1} quedó pendiente sin efecto observado. Puedes decir «continuar» para reintentarlo o «cancelar» para detener el resto del plan.",
                    isUser: false,
                    messageEvent: response.EffectMayHaveOccurred
                        ? UserMessageEvent.Error(
                            UserMessageDiagnosticCodes.ActionNotCompleted)
                        : UserMessageEvent.Confirmation);
                return;
            }

            if (response.Status == OperationStatuses.Completed && response.Verified)
            {
                CompleteMindPlanStep(execution, registry, prepared, step, response);
                continue;
            }

            if (MindPlanBoundary.MustRetainAmbiguousEffect(response))
            {
                execution.PendingOperation = prepared;
                execution.PendingEffectMayHaveOccurred = true;
                _pendingMindPlan = execution;
                PersistMindPlan(execution);
                AddMessage(
                    "BAXY",
                    $"El paso {execution.NextIndex + 1} no pudo verificarse y el efecto puede haber ocurrido. Conservé su identidad durable; no continuaré, replanearé ni lo repetiré hasta reconciliarlo.",
                    isUser: false,
                    messageEvent: UserMessageEvent.Error(
                        UserMessageDiagnosticCodes.ActionNotCompleted));
                return;
            }

            _ = TryMarkResolved(registry, prepared);
            execution.PendingOperation = null;
            PersistMindPlan(execution);

            if (!response.EffectMayHaveOccurred && execution.ReplanCount < 2)
            {
                MindPlanResult? replacement = await TryReplanMindMissionAsync(
                    execution,
                    step,
                    response,
                    cancellationToken);
                if (replacement is { Kind: "plan" }
                    && MindPlanBoundary.IsSafeReplanSuffix(execution, replacement))
                {
                    try
                    {
                        _ = MindPlanBoundary.ValidateAndConvert(execution.Objective, replacement);
                    }
                    catch (Baxy.Kernel.Planning.MissionPlanValidationException)
                    {
                        FinishMindPlanWithFailure(
                            execution,
                            "No pude continuar de forma segura. Detuve los pasos restantes sin repetir acciones.");
                        return;
                    }
                    var replanned = new PendingMindPlanExecution(
                        execution.Objective,
                        replacement.Steps,
                        execution.ReplanCount + 1);
                    foreach (JsonNode? observation in execution.Observations)
                    {
                        replanned.Observations.Add(observation?.DeepClone());
                    }

                    replanned.CompletedMessages.AddRange(execution.CompletedMessages);
                    _pendingMindPlan = replanned;
                    PersistMindPlan(replanned);
                    execution = replanned;
                    continue;
                }
            }

            FinishMindPlanWithFailure(
                execution,
                $"No pude completar el paso {execution.NextIndex + 1}; detuve los pasos restantes sin repetir acciones.");
            return;
        }

        ClearMindPlan();
        AddMessage(
            "BAXY",
            MissionNarration.CreateCompletionMessage(execution.CompletedMessages),
            isUser: false);
    }

    private void StageMindPlanConfirmation(
        PendingMindPlanExecution execution,
        PendingOperationConfirmation confirmation)
    {
        execution.RequireConfirmation(confirmation);
        _pendingMindPlan = execution;
        PersistMindPlan(execution);
        AddMessage(
            "BAXY",
            confirmation.ReconciliationRequired
                ? $"El paso {execution.NextIndex + 1} ya había comenzado antes de una interrupción y el efecto puede haber ocurrido. Conservé la misma identidad. Responde «confirmar / confirm» para reconciliarlo; no continuaré ni lo repetiré a ciegas."
                : $"El paso {execution.NextIndex + 1} requiere tu confirmación. Responde únicamente «confirmar / confirm» o «cancelar / cancel». Aún no ejecuté ese efecto.",
            isUser: false,
            messageEvent: UserMessageEvent.Confirmation);
    }

    private async Task HandlePendingMindPlanAsync(
        string text,
        RetryableOperationRegistry registry,
        CancellationToken cancellationToken)
    {
        PendingMindPlanExecution execution = _pendingMindPlan
            ?? throw new InvalidOperationException("No hay un plan pendiente.");
        if (execution.Confirmation is { } confirmation)
        {
            switch (ConfirmationReplyParser.Parse(text))
            {
                case ConfirmationReplyKind.Invalid:
                    AddMessage(
                        "BAXY",
                        confirmation.ReconciliationRequired
                            ? "Este paso necesita comprobar un intento que ya había comenzado. Responde «confirmar / confirm»; no ejecutaré nada distinto ni borraré su evidencia de recuperación."
                            : "Para este paso responde únicamente «confirmar / confirm» o «cancelar / cancel». No ejecuté nada nuevo.",
                        isUser: false,
                        messageEvent: UserMessageEvent.Confirmation);
                    return;
                case ConfirmationReplyKind.Cancel:
                    if (!execution.CanAbandonConfirmation)
                    {
                        PersistMindPlan(execution);
                        AddMessage(
                            "BAXY",
                            "No puedo dar este paso por cancelado como si no hubiera empezado. Detuve los pasos nuevos y conservé su evidencia de recuperación. Responde «confirmar / confirm» para comprobar exactamente el mismo intento.",
                            isUser: false,
                            messageEvent: UserMessageEvent.Confirmation);
                        return;
                    }

                    registry.MarkResolved(confirmation.Prepared);
                    ClearMindPlan();
                    AddMessage(
                        "BAXY",
                        $"Cancelé el paso {execution.NextIndex + 1} y detuve el resto de la misión. Los {execution.CompletedMessages.Count} pasos anteriores permanecen completados.",
                        isUser: false);
                    return;
                case ConfirmationReplyKind.Confirm:
                    CoreProcessClient client = _coreClient
                        ?? throw new InvalidOperationException("El motor local no está disponible.");
                    OperationResponse response = await client.SendOperationAsync(
                        confirmation.Prepared,
                        TimeSpan.FromSeconds(20),
                        cancellationToken,
                        confirmation.Token);
                    execution.Confirmation = null;
                    if (response.Status == OperationStatuses.Completed && response.Verified)
                    {
                        CompleteMindPlanStep(
                            execution,
                            registry,
                            confirmation.Prepared,
                            execution.CurrentStep,
                            response);
                        await ExecuteMindPlanAsync(execution, registry, cancellationToken);
                        return;
                    }

                    if (PendingOperationConfirmation.TryCreate(
                            response,
                            confirmation.Prepared,
                            TimeProvider.System,
                            out PendingOperationConfirmation? refreshed)
                        && refreshed is not null)
                    {
                        StageMindPlanConfirmation(execution, refreshed);
                        return;
                    }

                    if (ShouldRetainRetryIdentity(response))
                    {
                        execution.PendingOperation = confirmation.Prepared;
                        execution.PendingEffectMayHaveOccurred |=
                            response.EffectMayHaveOccurred;
                        _pendingMindPlan = execution;
                        PersistMindPlan(execution);
                        AddMessage(
                            "BAXY",
                            response.EffectMayHaveOccurred
                                ? "La acción confirmada quedó inconclusa y puede haber ocurrido. Conservaré su identidad y no la repetiré a ciegas."
                                : "La acción confirmada quedó pendiente sin efecto observado. Puedes decir «continuar» para reintentar exactamente la misma invocación.",
                            isUser: false);
                        return;
                    }

                    _ = TryMarkResolved(registry, confirmation.Prepared);
                    execution.PendingOperation = null;
                    FinishMindPlanWithFailure(
                        execution,
                        "La acción confirmada no se completó y está verificado que no hubo efecto; detuve el resto de la misión.");
                    return;
                default:
                    throw new InvalidDataException("La respuesta de confirmación no es válida.");
            }
        }

        ConfirmationReplyKind reply = ConfirmationReplyParser.Parse(text);
        if (reply == ConfirmationReplyKind.Cancel)
        {
            if (execution.PendingEffectMayHaveOccurred)
            {
                PersistMindPlan(execution);
                AddMessage(
                    "BAXY",
                    "Detuve los pasos restantes, pero conservaré la evidencia de recuperación hasta comprobar el efecto inconcluso sin duplicarlo.",
                    isUser: false);
            }
            else
            {
                if (execution.PendingOperation is not null)
                {
                    registry.MarkResolved(execution.PendingOperation);
                }

                ClearMindPlan();
                AddMessage(
                    "BAXY",
                    "Cancelé los pasos restantes de la misión.",
                    isUser: false);
            }

            return;
        }

        if (execution.PendingEffectMayHaveOccurred)
        {
            if ((reply == ConfirmationReplyKind.Confirm
                    || string.Equals(
                        text.Trim(),
                        "continuar",
                        StringComparison.OrdinalIgnoreCase)
                    || string.Equals(
                        text.Trim(),
                        "continue",
                        StringComparison.OrdinalIgnoreCase))
                && MindPlanBoundary.CanRefreshConfirmationChallenge(execution))
            {
                await ExecuteMindPlanAsync(execution, registry, cancellationToken);
                return;
            }

            AddMessage(
                "BAXY",
                MindPlanBoundary.CanRefreshConfirmationChallenge(execution)
                    ? "No borraré la evidencia de recuperación porque el paso ya había comenzado. Responde «confirmar / confirm» para solicitar una nueva comprobación del mismo intento."
                    : "No repetiré este paso porque el efecto anterior puede haber ocurrido. Debe reconciliarse con el estado real antes de continuar.",
                isUser: false);
            return;
        }

        if (reply != ConfirmationReplyKind.Confirm
            && !string.Equals(text.Trim(), "continuar", StringComparison.OrdinalIgnoreCase)
            && !string.Equals(text.Trim(), "continue", StringComparison.OrdinalIgnoreCase))
        {
            AddMessage(
                "BAXY",
                "Di «continuar» para reintentar el paso pendiente o «cancelar» para detener el resto del plan.",
                isUser: false,
                messageEvent: UserMessageEvent.Confirmation);
            return;
        }

        await ExecuteMindPlanAsync(execution, registry, cancellationToken);
    }

    private void CompleteMindPlanStep(
        PendingMindPlanExecution execution,
        RetryableOperationRegistry registry,
        PreparedOperation prepared,
        MindPlanStep step,
        OperationResponse response)
    {
        _ = TryMarkResolved(registry, prepared);
        execution.PendingOperation = null;
        execution.PendingEffectMayHaveOccurred = false;
        execution.Observations.Add(
            PlanObservationProjector.Create(step.Id, step.Operation, response));
        execution.CompletedMessages.Add(
            OperationResponseProjection.Create(response, step.Operation).Message);
        execution.NextIndex++;
        if (execution.NextIndex < execution.Steps.Count)
        {
            PersistMindPlan(execution);
        }
    }

    private async Task<MindPlanResult?> TryReplanMindMissionAsync(
        PendingMindPlanExecution execution,
        MindPlanStep failedStep,
        OperationResponse response,
        CancellationToken cancellationToken)
    {
        MindSidecarClient? mind = _mindClient;
        if (mind is null || !mind.IsReady)
        {
            return null;
        }

        MindReplanSuffixContract pendingSuffix =
            MindPlanBoundary.CapturePendingSuffix(execution);
        var recovery = new JsonObject
        {
            ["failedOperation"] = failedStep.Operation,
            ["errorCode"] = response.ErrorCode ?? "operation_failed",
            ["effectMayHaveOccurred"] = false,
            ["completed"] = execution.Observations.DeepClone(),
            ["instruction"] =
                "Conserva los pasos completados; propone solo el sufijo pendiente y preserva exactamente la operación, el propósito y los argumentos literales declarados para cada paso.",
        };
        return await mind.PlanAsync(
            execution.Objective,
            [],
            TimeSpan.FromSeconds(60),
            cancellationToken,
            recovery,
            expectedSuffix: pendingSuffix);
    }

    private void FinishMindPlanWithFailure(
        PendingMindPlanExecution execution,
        string reason)
    {
        ClearMindPlan();
        AddMessage(
            "BAXY",
            MissionNarration.CreateFailureMessage(execution.CompletedMessages, reason),
            isUser: false,
            messageEvent: UserMessageEvent.Error(
                UserMessageDiagnosticCodes.ActionNotCompleted));
    }

    private void PersistMindPlan(PendingMindPlanExecution execution)
    {
        DurablePlanStore store = _planStore
            ?? throw new InvalidOperationException("El store durable del planner no está disponible.");
        store.Save(execution);
    }

    private void ClearMindPlan()
    {
        _pendingMindPlan = null;
        _planStore?.Clear();
    }

    private bool AddMindConversationFallback()
    {
        // turn.decide already produces the conversational answer. A second
        // open-ended generation used to duplicate the request and could add
        // another timeout after the 22 s turn boundary. Degrade through the
        // bounded LLM message composer instead of restarting semantic work.
        AddMessage(
            "BAXY",
            "No pude formular una respuesta segura para esta petición. Puedes reformularla.",
            isUser: false,
            messageEvent: UserMessageEvent.Error(
                UserMessageDiagnosticCodes.ActionNotCompleted));
        return true;
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
                    "Conservé la identidad de recuperación. Cuando haya espacio, repetiré esta petición sin cambiarla ni duplicarla.",
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
            RecoverPendingMemoryOperation(announce: true);
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
                "La acción terminó, pero no pude cerrar su registro de recuperación. Si la repites, la reconciliaré sin duplicarla.",
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

    private void RecoverPendingMemoryOperation(bool announce)
    {
        RetryableOperationRegistry? registry = _retryableOperations;
        MemoryOperationProtector? protector = _memoryProtector;
        if (registry is null || protector is null || _pendingMemoryConfirmation is not null)
        {
            return;
        }

        if (_pendingMemoryOperation is not null)
        {
            if (announce)
            {
                AnnouncePendingMemoryRecoveryIfReady();
            }

            return;
        }

        PreparedOperation? firstPreserved = null;
        foreach (PreparedOperation operation in registry.SnapshotPendingOperations())
        {
            if (!MemoryOperationProtector.IsMemoryOperation(operation.OperationName))
            {
                continue;
            }

            MemoryOperationInspection inspection = protector.InspectForRecovery(operation);
            if (!inspection.OriginatesInCurrentSession
                && inspection.CancelAfterSessionChange)
            {
                registry.MarkResolved(operation);
                if (registry.SnapshotPendingOperations().Any(
                        candidate => IsSameMemoryOperation(candidate, operation)))
                {
                    throw new InvalidDataException(
                        "No se pudo retirar una operación privada vencida de la recuperación.");
                }

                continue;
            }

            firstPreserved ??= operation;
        }

        if (firstPreserved is null)
        {
            return;
        }

        _pendingMemoryOperation = firstPreserved;
        _pendingMemoryRecoveryAnnounced = false;
        if (announce)
        {
            AnnouncePendingMemoryRecoveryIfReady();
        }
    }

    private void AnnouncePendingMemoryRecoveryIfReady()
    {
        if (_pendingMemoryOperation is null
            || _pendingMemoryRecoveryAnnounced
            || _pendingMemoryConfirmation is not null
            || _pendingAudioOperation is not null)
        {
            return;
        }

        _pendingMemoryRecoveryAnnounced = true;
        StatusDescription = "Esperando comprobar la memoria";
        AddMessage(
            "BAXY",
            PrivateOperationNarration.CreateMemoryRecoveryPrompt(_pendingMemoryOperation),
            isUser: false,
            messageEvent: UserMessageEvent.Confirmation);
    }

    private void RecoverPendingNoteInteraction(bool announce)
    {
        RetryableOperationRegistry? registry = _retryableOperations;
        if (registry is null
            || _pendingAudioOperation is not null
            || _pendingMemoryConfirmation is not null
            || _pendingMemoryOperation is not null
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
        ClearVolatileMemoryConfirmation();
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
            await _mindClient.DisposeAsync();
            _mindClient = null;
        }
        _mindLifetimeCancellation.Dispose();
    }

    private async Task HandleStartupFailureAsync(CoreProcessClient client)
    {
        ClearVolatileMemoryConfirmation();
        DetachCoreDisconnectedHandler(client);
        await client.DisposeAsync();
        if (ReferenceEquals(_coreClient, client))
        {
            _coreClient = null;
        }

        IsReady = false;
        HasStartupError = true;
        StatusText = "No disponible";
        StatusDescription = "Puedes reintentar sin cerrar BAXY";
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
                owner.ClearVolatileMemoryConfirmation();
                owner.HasStartupError = true;
                owner.StatusText = "Desconectada";
                owner.StatusDescription = "Conexión interrumpida";
                owner.AddMessage(
                    "BAXY",
                    "Perdí la conexión con las funciones del equipo. Detuve las acciones pendientes; puedes reintentarlo.",
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
        UserMessageEvent? messageEvent = null)
    {
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
            JsonObject facts = ModelMessageComposer.CreateFacts(draft);
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

                if (outcome.Text is { } finalBody)
                {
                    LastMessageCompositionFailure = outcome.Failure;
                    AddMessageCore("BAXY", finalBody, isUser: false);
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

        AddMessageCore(speaker, body, isUser);
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
        bool hasPendingModelMessage = PendingModelMessageCount > 0;
        IsBusy = _turnExecutionActive || hasPendingModelMessage;
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

        StatusText = "Lista";
        StatusDescription = _pendingMemoryConfirmation is not null
            ? "Esperando confirmación de memoria"
            : _pendingAudioOperation is not null
            ? "Esperando comprobar el audio"
            : _pendingMindPlan is not null
                ? "Esperando reanudar una misión"
            : _pendingMindClarificationObjective is not null
                ? "Esperando tu aclaración"
            : _pendingMemoryOperation is not null
                ? "Esperando comprobar la memoria"
            : _pendingNoteInteraction.Current
                is PendingNoteInteraction.ReconcilingSelection
                ? "Esperando una comprobación segura"
            : _pendingNoteInteraction.Current
                is PendingNoteInteraction.ReconcilingTitle
                ? "Esperando recuperar una petición"
            : _pendingNoteInteraction.Current
                is PendingNoteInteraction.AwaitingChoice
                ? "Esperando tu elección"
                : "BAXY disponible";
    }

    private void AddMessageCore(string speaker, string body, bool isUser)
    {
        var message = new ConversationMessage(speaker, body, isUser, DateTimeOffset.Now);
        Messages.Add(message);
        MessageAdded?.Invoke(message);
        MindSidecarClient? mind = _mindClient;
        if (mind is { IsReady: true } && (IsListening || IsWakeListening))
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

    private sealed record PendingPublicAfterMemory(
        PreparedOperation Predecessor,
        string Objective,
        MissionInputSource Source);

    private enum MindStartupState
    {
        NotConfigured,
        Starting,
        Ready,
        Failed,
    }
}
