using System.ComponentModel;
using System.Globalization;
using System.IO;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;
using Baxy.Contracts;
using Baxy.Kernel.Operations;
using Baxy.Kernel.Policy;
using Baxy.Providers.Windows.SystemStatus;
using Baxy.Security.Windows;

namespace Baxy.App;

/// <summary>Where <see cref="FieldProductChannel"/> publishes its events (<see cref="FieldUiBridge"/> posts them to
/// the view).</summary>
internal interface IFieldEventSink
{
    bool Publish(JsonObject eventData);
}

/// <summary>
/// The Field view's routes and public events (design v4): turn admission, the conversation with its steps and cards
/// (<see cref="FieldTranscript"/>), what left the PC, voice, the start's pieces, sessions, settings, the catalog and the
/// triggers. Only <see cref="FieldUiBridge"/> (the WebView adapter) calls this type; the origin policy stays on that
/// adapter, this channel has none. Every value it sends was observed; one it could not read travels as null.
/// </summary>
internal sealed class FieldProductChannel : IAsyncDisposable
{
    internal const int MaximumRequestBodyCharacters = 65_536;
    internal const int MaximumPathCharacters = 2_048;
    private const int MaximumSessionLabel = 80;

    private readonly MainWindowViewModel _viewModel;
    private readonly IFieldEventSink _sink;
    private readonly FieldTelemetrySampler _telemetry;
    private readonly CancellationToken _lifetimeCancellation;
    private readonly FieldTranscript _transcript = new();
    private readonly FieldSessionStore _sessions = FieldSessionStore.CreateDefault();
    private string _sessionId = NewSessionId();
    private string? _sessionLabel;
    private string _sessionLabelBy = FieldSessionStore.LabelByFirst;
    // Each time a kept conversation's name changes after the view listed it (the model named one that closed): the view
    // reads the list again (surfaces, sessions_revision).
    private int _sessionsRevision;
    // The last save of the conversation on screen did not reach the disk: the history says so until one does.
    private bool _unsaved;
    private DateTimeOffset _sessionCreated = DateTimeOffset.UtcNow;
    private int? _triggerCount;
    // The card that waits for the person's Sí or No and the call it shows: an answer that names another card is refused.
    private (string Id, NativeTurnConfirmation Asked)? _pendingCard;
    private bool _disposed;
    // The memory panel runs the chat's own catalog operations; its count is read from the store when the view asks
    // for the surfaces and the store may have changed since (first read, a chat change).
    private readonly MemoryPanel _memory;
    // Settings › General «Buscar actualizaciones» and the notice of a newer BAXY (baxy.update through the engine).
    private readonly UpdatePanel _updates;
    private bool _memoryCountStale = true;
    // Every chat change of the store is numbered and travels in the counter's own event, so an open list is read again.
    private int _memoryRevision;

    /// <summary>Where the search for the package's legal texts starts (the folder of Baxy.exe); a test's own folder.</summary>
    internal string LegalStart { get; set; } = AppContext.BaseDirectory;

    /// <summary>Opens a file or a folder with what Windows has for it; false when it could not. A test's own.</summary>
    internal Func<string, bool> OpenShell { get; set; } = ShellOpen;

    internal FieldProductChannel(
        MainWindowViewModel viewModel,
        IFieldEventSink sink,
        FieldTelemetrySampler telemetry,
        CancellationToken lifetimeCancellation)
    {
        _viewModel = viewModel ?? throw new ArgumentNullException(nameof(viewModel));
        _sink = sink ?? throw new ArgumentNullException(nameof(sink));
        _telemetry = telemetry ?? throw new ArgumentNullException(nameof(telemetry));
        _lifetimeCancellation = lifetimeCancellation;
        FieldStepProjection.Validate();
        _viewModel.MessageAdded += OnMessageAdded;
        _viewModel.PropertyChanged += OnViewModelPropertyChanged;
        _viewModel.MemoryChanged += OnMemoryChanged;
        _viewModel.EverythingForgotten += OnEverythingForgotten;
        _viewModel.StepStarted += OnStepStarted;
        _viewModel.StepCompleted += OnStepCompleted;
        _viewModel.ConfirmationAsked += OnConfirmationAsked;
        _viewModel.ConfirmationResolved += OnConfirmationResolved;
        _viewModel.ProposalNotificationRequested += OnProposalNotified;
        _viewModel.VoicePartial += OnVoicePartial;
        _viewModel.VoiceLip += OnVoiceLip;
        _viewModel.VoiceWake += OnVoiceWake;
        _memory = new MemoryPanel(() => _viewModel.CoreClient, () => _viewModel.MemoryProtector);
        _updates = UpdatePanel.ForEngine(() => _viewModel.CoreClient);
        _updates.InstallEnded += OnInstallEnded;
        _ = WatchForUpdatesAsync(_lifetimeCancellation);
        // A mind that starts again gets back the conversation this view shows (2026-10-22, review of the App).
        _viewModel.KeptConversation = () => _sessions.Load(_sessionId)?.Mind;
        // f6 estado: BAXY's own readings by voice are the ones this channel serves the view.
        _viewModel.OwnReader = ReadOwnAsync;
        _viewModel.Conversation = RunConversation;
        _viewModel.TurnReleased += OnTurnReleased;
        _viewModel.TunedModelOnline += OnTunedModelOnline;
        _viewModel.ModelDownloadOnline += OnModelDownloadOnline;
        _viewModel.RingChanged += OnRingChanged;
        foreach (RingNow ring in _viewModel.Ringing)
        {
            OnRingChanged(ring);
        }
    }

    // A view that (re)connects after the start's check found a newer BAXY sees the notice again.
    private IEnumerable<JsonObject> UpdateNotices()
    {
        if (UpdatePanel.NoticeOf(_updates.Known) is { } notice)
        {
            yield return notice;
        }
    }

    // A check goes to GitHub only (nothing of the person, BAXY's version in the user agent), and «Salidas a internet» says so.
    private async Task<JsonObject> CheckForUpdateAsync()
    {
        JsonObject found = await _updates.CheckAsync(_lifetimeCancellation).ConfigureAwait(true);
        if (_updates.WentOnline("check", found) is { } online)
        {
            OnModelDownloadOnline(online);
        }

        if (UpdatePanel.NoticeOf(found) is { } notice)
        {
            Publish(notice);
        }

        return found;
    }

    // «Actualizar»: GitHub is asked again and the installer comes from it, and «Salidas a internet» says so (INT19) when
    // the install ends, whoever still waits for it (APP1: the button's request answers before the download does).
    private void OnInstallEnded(JsonObject done)
    {
        if (_updates.WentOnline("install", done) is { } online)
        {
            OnModelDownloadOnline(online);
        }
    }

    // Once per start, when the engine is ready and the person has not switched «Avisar de versiones nuevas» off.
    private async Task WatchForUpdatesAsync(CancellationToken cancellationToken)
    {
        try
        {
            for (int tries = 0; tries < 120 && _viewModel.CoreClient is not { IsReady: true }; tries++)
            {
                await Task.Delay(TimeSpan.FromSeconds(5), cancellationToken).ConfigureAwait(true);
            }

            if (_viewModel.CoreClient is { IsReady: true } && _viewModel.Settings.UpdateNotice)
            {
                _ = await CheckForUpdateAsync().ConfigureAwait(true);
            }
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            // BAXY is closing: there is nothing to tell.
        }
    }

    // QWB2: the tuned model's state for Settings → Model, and whether the mind is being relaunched for a change.
    private JsonObject BehaviorJson() =>
        _viewModel.BehaviorState.Json(_viewModel.FactoryBehavior, _viewModel.ExternalModelState.Switching);

    // Settings → Tools: the profile, and whether the mind is being relaunched for a change.
    private JsonObject ToolsJson()
    {
        JsonObject state = _viewModel.ToolProfileState.Json();
        state["switching"] = _viewModel.ExternalModelState.Switching;
        return state;
    }

    // What BAXY's own model takes on the card now (the telemetry's reading of the mind's processes).
    private async Task<double?> OwnModelVramAsync() =>
        (await _telemetry.SampleAsync(_lifetimeCancellation).ConfigureAwait(false)).ModelVramGb;

    // And what its processes hold of what Windows can promise (their private bytes), which a switch frees too.
    private async Task<double?> OwnModelCommitAsync() =>
        (await _telemetry.SampleAsync(_lifetimeCancellation).ConfigureAwait(false)).ModelCommitGb;

    // With the person's graphics card's memory, so each option says whether it fits it (and whether the projector goes there),
    // and what is free on it with BAXY's own model gone, for the recommended context. The card's use is read only when the
    // view asks once, not while it asks every second during a switch (it reads every process's counters, ~1-1.6 s).
    private async Task<JsonObject> LocalContextJsonAsync()
    {
        bool switching = _viewModel.ExternalModelState.Switching || _viewModel.LocalContextState.NeedsSwitch;
        (long Total, long? Free)? card = switching ? null
            : await _viewModel.ExternalModelState.CardAsync(await OwnModelVramAsync().ConfigureAwait(true), _lifetimeCancellation).ConfigureAwait(true);
        long? total = card?.Total ?? await _viewModel.ExternalModelState.CardTotalAsync(_lifetimeCancellation).ConfigureAwait(true);
        JsonObject state = _viewModel.LocalContextState.Json(_viewModel.MindPrefixTokens, _viewModel.MindBackend, _viewModel.ExternalModelState.Switching,
            total, card?.Free);
        // MOD1 V-07: what the stock model and the tuned one take on disk and on the card, for their rows in «Modelos en este PC».
        state["stock"] = _viewModel.LocalContextState.OnDisk(_viewModel.TunedModelState.StockPath, _viewModel.MindBackend, total);
        state["tuned"] = _viewModel.LocalContextState.OnDisk(_viewModel.TunedModelState.InstalledPath, _viewModel.MindBackend, total);
        // MOD1 D5: what this PC took the last time the model read its instructions whole, said before a change that reads them again.
        state["lastRead"] = _viewModel.PrefixReadState.Json();
        return state;
    }

    private JsonObject TunedModelJson()
    {
        JsonObject state = _viewModel.TunedModelState.Json();
        state["switching"] = _viewModel.ExternalModelState.Switching;
        return state;
    }

    private void OnModelDownloadOnline(string what) => Publish(new JsonObject
    {
        ["type"] = "net",
        ["what"] = what,
        ["ts"] = DateTimeOffset.Now.ToString("HH:mm", CultureInfo.InvariantCulture),
    });

    // The download the person asked for goes in «Salidas a internet», as a step that went online does.
    private void OnTunedModelOnline(string host) => Publish(new JsonObject
    {
        ["type"] = "net",
        ["what"] = UiLanguage.Say($"descarga del modelo ajustado a BAXY desde {host}", $"download of BAXY's tuned model from {host}"),
        ["ts"] = DateTimeOffset.Now.ToString("HH:mm", CultureInfo.InvariantCulture),
    });

    // assistant.status: the confirmation mode the engine rereads (null when its file could not be read), GET /metrics'
    // model reading (the same sampler), or this session's internet log, which the view builds from the same transcript
    // (store.ts, netOf).
    private async Task<Baxy.Kernel.Operations.OperationOutcome> ReadOwnAsync(string scope, CancellationToken cancellationToken) =>
        scope switch
        {
            "confirmation" => OwnReadings.Confirmation(
                ConfirmationModeStore.TryRead(MemoryOperationProtector.ResolveDataRoot(), out ConfirmationMode mode) ? mode : null),
            "model" => OwnReadings.Model(await _telemetry.SampleAsync(cancellationToken).ConfigureAwait(true)),
            "internet" => OwnReadings.Internet(_transcript.Items),
            _ => Baxy.Kernel.Operations.OperationOutcome.Failure(OwnReadings.UnknownScope),
        };

    internal async Task<FieldHttpResponse> HandleHttpAsync(string method, string path, string? body)
    {
        method = (method ?? "GET").ToUpperInvariant();
        path ??= "/";
        if (path.Length > MaximumPathCharacters || body?.Length > MaximumRequestBodyCharacters)
        {
            return Error("request_too_large", 413);
        }

        string route = path.Split('?', 2)[0];
        switch (method, route)
        {
            case ("GET", "/agent/status"):
                return Json(AgentStatus());
            case ("GET", "/model"):
                // The model is said loaded only once the mind that serves it is ready.
                return _viewModel.IsMindReady ? Json(ModelInfo())
                    : Error(MindUnavailable ? "mind_unavailable" : "model_not_loaded", 503);
            case ("GET", "/metrics"):
                return Json(MetricsJson(await _telemetry.SampleAsync(_lifetimeCancellation).ConfigureAwait(true)));
            case ("GET", "/metrics/breakdown"):
                // Owner, 2026-11-08: all the memory BAXY uses, piece by piece (Settings › Modelo asks while it is open).
                return Json(await Task.Run(static () => OwnMemory.Read(
                    Environment.ProcessId,
                    WindowsModelResourceReader.ProcessTreeOf(Environment.ProcessId),
                    WindowsModelResourceReader.WorkingSetBytes,
                    WindowsModelResourceReader.DedicatedVideoBytes), _lifetimeCancellation).ConfigureAwait(true));
            case ("GET", "/surfaces"):
                if (_memoryCountStale)
                {
                    _memoryCountStale = !await _memory.RefreshCountAsync(_lifetimeCancellation).ConfigureAwait(true);
                    Publish(SurfacesEvent());
                }

                return Json(Surfaces());
            case ("GET", "/voice/status"):
                return Json(VoiceStatus());
            case ("POST", "/voice/start"):
                return await VoiceStartAsync().ConfigureAwait(true);
            case ("POST", "/voice/stop"):
            {
                bool stopped = await _viewModel.SetWakeVoiceAsync(false, _lifetimeCancellation).ConfigureAwait(true);
                return Json(new JsonObject { ["ok"] = stopped, ["running"] = !stopped }, stopped ? 200 : 503);
            }

            case ("POST", "/voice/trigger"):
            {
                if (!FieldBridgeContract.TryAcceptVoiceControl(_viewModel.IsReady, out string error, out int status))
                {
                    return Error(error, status);
                }

                bool running = await _viewModel.StartDirectVoiceAsync(_lifetimeCancellation).ConfigureAwait(true);
                return Json(new JsonObject { ["ok"] = running, ["running"] = running }, running ? 200 : 503);
            }

            case ("POST", "/voice/release"):
            {
                bool released = await _viewModel.ReleaseDirectVoiceAsync(_lifetimeCancellation).ConfigureAwait(true);
                return Json(new JsonObject { ["ok"] = released }, released ? 200 : 503);
            }

            case ("POST", "/turn"):
                return await HandleTurnAsync(body).ConfigureAwait(true);
            case ("POST", "/confirmation/answer"):
            {
                long arrivedAt = System.Diagnostics.Stopwatch.GetTimestamp();
                if (ParseBody(body)?["approve"] is not JsonValue approveValue || !approveValue.TryGetValue(out bool approve))
                {
                    return Error("invalid_answer", 400);
                }

                // 2026-10-22, review of the App: the answer names the card pressed («card»); see AnswerCardAsync.
                if ((string?)ParseBody(body)?["card"] is not { Length: > 0 } card)
                {
                    return HasPendingCard ? Error("card_required", 400) : Error("nothing_pending", 409);
                }

                return await AnswerCardAsync(approve, card, arrivedAt).ConfigureAwait(true) is { } refused
                    ? Error(refused, 409)
                    : Json(new JsonObject { ["ok"] = true });
            }

            case ("POST", "/power"):
            {
                if (ParseBody(body)?["on"] is not JsonValue onValue || !onValue.TryGetValue(out bool on))
                {
                    return Error("invalid_power", 400);
                }

                bool now = await _viewModel.SetPowerAsync(on, _lifetimeCancellation).ConfigureAwait(true);
                return Json(new JsonObject { ["ok"] = now == on, ["on"] = now });
            }

            // Uso 85: the person's answer to a profile the core cannot read, or to a breakdown (App.tsx, Breakdown).
            case ("POST", "/profile/fresh"):
                return await StartFreshProfileAsync().ConfigureAwait(true);
            case ("POST", "/engine/retry"):
                return _viewModel.RetryEngine() ? Json(new JsonObject { ["ok"] = true }) : Error("nothing_to_retry", 409);
            case ("GET", "/sessions"):
                return Json(Sessions());
            case ("POST", "/sessions/new"):
                return await NewSessionAsync().ConfigureAwait(true);
            case ("POST", "/sessions/load"):
                return await LoadSessionAsync((string?)ParseBody(body)?["id"] ?? string.Empty).ConfigureAwait(true);
            case ("POST", "/sessions/rename"):
                return RenameSession(ParseBody(body));
            case ("DELETE", "/sessions"):
                return await DeleteSessionsAsync(ParseBody(body)).ConfigureAwait(true);
            case ("GET", "/kept"):
                return Json(Kept());
            case ("POST", "/settings/legal/open"):
                return OpenLegal((string?)ParseBody(body)?["doc"]);
            case ("GET", "/catalog"):
                return Json(FieldStepProjection.Catalog());
            case ("GET", "/triggers"):
                return await TriggersAsync().ConfigureAwait(true);
            case ("POST", "/triggers/cancel"):
                return await CancelTriggerAsync(ParseBody(body)).ConfigureAwait(true);
            case ("POST", "/ring/answer"):
                return await AnswerRingAsync(ParseBody(body)).ConfigureAwait(true);
            // actualizar-ordenes-app: whether there is a newer BAXY where it came from, and the person's «Actualizar».
            case ("GET", "/update"):
                return Json(await CheckForUpdateAsync().ConfigureAwait(true));
            // APP1 (UPD-f): the install is a long operation the view reads, not one answer it waits for (UpdatePanel).
            case ("POST", "/update/install"):
                return Json(await _updates.InstallAsync(_lifetimeCancellation).ConfigureAwait(true));
            case ("GET", "/update/install"):
                return Json(_updates.InstallState());
            case ("GET", "/settings/general"):
                return Json(_viewModel.Settings.GeneralJson(Autostart()));
            // Owner, 2026-11-08: the overlay that says what BAXY does while its window is behind (OverlayPresenter).
            case ("GET", "/settings/overlay"):
                return Json(_viewModel.Settings.OverlayJson());
            case ("PUT", "/settings/overlay"):
                return ParseBody(body) is { } overlay && _viewModel.Settings.ApplyOverlay(overlay) is not null
                    ? Json(_viewModel.Settings.OverlayJson())
                    : Error("invalid_overlay", 400);
            case ("POST", "/settings/overlay/preview"):
                OverlayPreviewRequested?.Invoke();
                return Json(new JsonObject { ["ok"] = true });
            case ("PUT", "/settings/general"):
                return PutGeneral(ParseBody(body));
            case ("GET", "/settings/external-model/estimate") when ExternalModel.Available:
                FieldMetricSnapshot own = await _telemetry.SampleAsync(_lifetimeCancellation).ConfigureAwait(true);
                return Json(await _viewModel.ExternalModelState.EstimateAsync(own.ModelVramGb, own.ModelRamGb, _lifetimeCancellation).ConfigureAwait(true));
            case ("GET", "/settings/external-model/models") when ExternalModel.Available:
                // «?provider=local»: the models on this PC (Ollama's), whatever place BAXY thinks in.
                return Json(await _viewModel.ExternalModelState.ModelsAsync(_lifetimeCancellation,
                    onThisPc: path.EndsWith("?provider=local", StringComparison.Ordinal)).ConfigureAwait(true));
            case ("POST", "/settings/external-model/search") when ExternalModel.Available:
                return ParseBody(body) is not { } search || (string?)search["q"] is not { } words
                    ? Error("invalid_settings", 400)
                    : Json(await _viewModel.ExternalModelState.SearchAsync(words, OwnModelVramAsync(), _lifetimeCancellation, OwnModelCommitAsync()).ConfigureAwait(true));
            case ("POST", "/settings/external-model/ollama") when ExternalModel.Available:
                return _viewModel.ExternalModelState.Open.InstallOllama(_lifetimeCancellation) is { } notInstalled
                    ? Error(notInstalled, 409)
                    : Json(_viewModel.ExternalModelState.Json());
            case ("POST", "/settings/external-model/pull") when ExternalModel.Available:
            {
                ExternalModel external = _viewModel.ExternalModelState;
                // «profile»: the tool profile the search offered a short model with, to use it with once it is here.
                return ParseBody(body) is not { } pull || (string?)pull["name"] is not { } name
                    || ((string?)pull["profile"] is { } pullWith && !ToolProfile.IsPreset(pullWith))
                    ? Error("invalid_settings", 400)
                    // The size the search said (the file and its projector): the bar's total until Ollama tells its layers.
                    : external.Open.Pull(name, external.EnsureOllamaAsync, _lifetimeCancellation,
                        pull["bytes"] is JsonValue size && size.TryGetValue(out long expected) ? expected : 0, (string?)pull["profile"]) is { } notPulled
                        ? Error(notPulled, 409)
                        : Json(external.Json());
            }
            case ("POST", "/settings/external-model/install") when ExternalModel.Available:
            {
                // The model alone, with no vision (OpenModels.Install); its vision is the pull of its «visionName».
                ExternalModel external = _viewModel.ExternalModelState;
                return ParseBody(body) is not { } install || (string?)install["repo"] is not { } repo || (string?)install["file"] is not { } file
                    || (string?)install["sha256"] is not { } sha256 || (string?)install["quant"] is not { } quant
                    || install["bytes"] is not JsonValue size || !size.TryGetValue(out long bytes)
                    || ((string?)install["profile"] is { } installWith && !ToolProfile.IsPreset(installWith))
                    ? Error("invalid_settings", 400)
                    : external.Open.Install(repo, file, sha256, bytes, quant, external.EnsureOllamaAsync, _lifetimeCancellation,
                        (string?)install["profile"]) is { } notMade
                        ? Error(notMade, 409)
                        : Json(external.Json());
            }
            case ("POST", "/settings/external-model/remove") when ExternalModel.Available:
            {
                ExternalModel external = _viewModel.ExternalModelState;
                return ParseBody(body) is not { } remove || (string?)remove["name"] is not { } removed
                    ? Error("invalid_settings", 400)
                    : await external.RemoveModelAsync(removed, _lifetimeCancellation).ConfigureAwait(true) is { } notRemoved
                        ? Error(notRemoved, 409)
                        : Json(external.Json());
            }
            case ("POST", "/settings/external-model/cancel") when ExternalModel.Available:
                _viewModel.ExternalModelState.Open.Cancel();
                return Json(_viewModel.ExternalModelState.Json());
            case ("GET", "/settings/external-model") when ExternalModel.Available:
                return Json(_viewModel.ExternalModelState.Json());
            case ("PUT", "/settings/external-model") when ExternalModel.Available:
            {
                if (ParseBody(body) is not { } externalModel)
                {
                    return Error("invalid_settings", 400);
                }

                // VIVO2 F15: «Usar con <perfil>» asks for the model and the tool profile it works with in this one request.
                string? profile = null;
                if (externalModel["profile"] is { } withProfile)
                {
                    profile = withProfile is JsonValue named && named.TryGetValue(out string? preset) ? preset : null;
                    if (!ToolProfile.IsPreset(profile))
                    {
                        return Error("invalid_settings", 400);
                    }

                    externalModel.Remove("profile");
                }

                // One model at a time: turning another one on turns the tuned one off, in the same switch of the mind.
                return _viewModel.UseModel(externalModel, profile) is { } refused
                    ? Error(refused, 409)
                    : Json(_viewModel.ExternalModelState.Json());
            }
            case ("GET", "/settings/tuned-model"):
                return Json(TunedModelJson());
            case ("PUT", "/settings/tuned-model"):
            {
                if (ParseBody(body) is not { } tuned)
                {
                    return Error("invalid_settings", 400);
                }

                if (_viewModel.TunedModelState.Apply(tuned) is { } refused)
                {
                    return Error(refused, 409);
                }

                // One model at a time: turning the tuned one on turns another model off, in the same switch of the mind.
                _viewModel.KeepOneModel(tunedChosen: true);
                _viewModel.ExternalModelChanged();
                _viewModel.TunedModelChanged();
                return Json(TunedModelJson());
            }
            case ("POST", "/settings/tuned-model/install"):
                return _viewModel.TunedModelState.Install(_lifetimeCancellation) is { } notStarted
                    ? Error(notStarted, 409)
                    : Json(TunedModelJson());
            // Settings → Model → Context: the context BAXY's own model runs with (LocalContext).
            case ("GET", "/settings/local-context"):
                return Json(await LocalContextJsonAsync().ConfigureAwait(true));
            case ("PUT", "/settings/local-context"):
            {
                if (ParseBody(body) is not { } context)
                {
                    return Error("invalid_settings", 400);
                }

                if (_viewModel.LocalContextState.Apply(context, _viewModel.MindPrefixTokens) is { } refused)
                {
                    return Error(refused, 409);
                }

                _viewModel.LocalContextChanged();
                return Json(await LocalContextJsonAsync().ConfigureAwait(true));
            }
            // Settings → Behavior: the person's own texts for BAXY's personality, replies and preferences (PersonBehavior).
            case ("GET", "/settings/behavior"):
                return Json(BehaviorJson());
            case ("PUT", "/settings/behavior"):
            {
                if (ParseBody(body) is not { } behavior)
                {
                    return Error("invalid_settings", 400);
                }

                if (_viewModel.BehaviorState.Apply(behavior) is { } refused)
                {
                    return Error(refused, 409);
                }

                _viewModel.BehaviorChanged();
                return Json(BehaviorJson());
            }
            // Settings → Tools: which of BAXY's tools the model sees (ToolProfile); the catalog with each one's level is
            // GET /catalog.
            case ("GET", "/settings/tools"):
                return Json(ToolsJson());
            case ("PUT", "/settings/tools"):
            {
                if (ParseBody(body) is not { } tools)
                {
                    return Error("invalid_settings", 400);
                }

                if (_viewModel.ToolProfileState.Apply(tools) is { } refused)
                {
                    return Error(refused, 409);
                }

                // The profile is the person's own choice now: none lent to a model is taken back (VIVO2 F15).
                if (ExternalModel.Available)
                {
                    _viewModel.ExternalModelState.ForgetLoan();
                }

                // A small context chosen for this profile's prefix may not fit the next one's (LocalContext).
                _ = _viewModel.LocalContextState.KeepForEveryProfile();
                _viewModel.ToolsChanged();
                return Json(ToolsJson());
            }
            case ("PUT", "/settings/language"):
                return PutLanguage(ParseBody(body));
            case ("GET", "/proposals"):
                return Json(_viewModel.Settings.ProposalsJson());
            case ("PUT", "/proposals"):
            {
                if (ParseBody(body) is not { } proposals)
                {
                    return Error("invalid_proposals", 400);
                }

                _viewModel.Settings.ApplyProposals(proposals, DateTimeOffset.UtcNow);
                return Json(_viewModel.Settings.ProposalsJson());
            }

            // The accessible mode is the profile's file (PresentationModeStore), the same one the chat's
            // baxy.settings.set writes. It changes only how the view is presented: the view switches its own styles.
            case ("GET", "/accessibility"):
                return Json(PresentationMode(PresentationModeStore.ReadAccessible(MemoryOperationProtector.ResolveDataRoot())));
            case ("PUT", "/accessibility"):
            {
                string mode = (string?)ParseBody(body)?["mode"] ?? string.Empty;
                if (mode is not (PresentationModeStore.Normal or PresentationModeStore.Accessible))
                {
                    return Error("invalid_accessibility_mode", 400);
                }

                string root = MemoryOperationProtector.ResolveDataRoot();
                PresentationModeStore.WriteAccessible(root, mode == PresentationModeStore.Accessible);
                JsonObject applied = PresentationMode(PresentationModeStore.ReadAccessible(root));
                applied["ok"] = true;
                return Json(applied);
            }

            case ("GET", "/voice/inventory"):
                return Json(VoiceInventory());
            case ("GET", "/settings"):
                return Json(CurrentSettings());
            case ("GET", "/confirmation"):
                return Json(ConfirmationPolicy(MemoryOperationProtector.ResolveDataRoot()));
            case ("PUT", "/confirmation"):
                return PutConfirmationMode(body);
        }

        if (route == "/memory" || route.StartsWith("/memory/", StringComparison.Ordinal))
        {
            int? before = _memory.Count;
            FieldHttpResponse memory = await _memory.HandleAsync(method, route, body, _lifetimeCancellation)
                .ConfigureAwait(true);
            if (_memory.Count != before)
            {
                Publish(SurfacesEvent());
            }

            // The panel's «olvidar todo» (DELETE /memory, scope all) takes the kept conversations with it.
            if (method == "DELETE" && route == "/memory" && memory.Status == 200)
            {
                _viewModel.ClearLogAndCaptures();
                OnEverythingForgotten();
            }

            return memory;
        }

        return Error("not_found", 404);
    }

    /// <summary>
    /// REV_LEGAL LEG-15 (2026-11-09): the privacy policy and the licenses go in the package (scripts/build_steam.ps1:
    /// <c>licenses\</c> beside <c>app\</c>, with <c>PRIVACIDAD.md</c> and <c>THIRD_PARTY_NOTICES.md</c>) and only existed as
    /// files: Settings › Privacidad opens them. «privacy» is the policy (its folder if Windows has no program for .md),
    /// «licenses» the folder of every text. The folder is the first <c>licenses</c> with the policy in it, from Baxy.exe's
    /// folder upwards (a development run finds the repository's). Nothing else can be named: the view sends a word, not a path.
    /// </summary>
    private FieldHttpResponse OpenLegal(string? doc)
    {
        if (doc is not ("privacy" or "licenses"))
        {
            return Error("invalid_settings", 400);
        }

        string? folder = null;
        for (DirectoryInfo? at = new(LegalStart); at is not null && folder is null; at = at.Parent)
        {
            string licenses = Path.Combine(at.FullName, "licenses");
            folder = File.Exists(Path.Combine(licenses, "PRIVACIDAD.md")) ? licenses : null;
        }

        if (folder is null)
        {
            return Error("legal_not_found", 404);
        }

        bool opened = doc == "privacy" && OpenShell(Path.Combine(folder, "PRIVACIDAD.md")) || OpenShell(folder);
        return opened ? Json(new JsonObject { ["ok"] = true }) : Error("legal_not_opened", 409);
    }

    private static bool ShellOpen(string path)
    {
        try
        {
            using var process = System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo(path) { UseShellExecute = true });
            return true;
        }
        catch (Exception exception) when (exception is System.ComponentModel.Win32Exception or InvalidOperationException)
        {
            return false;
        }
    }

    /// <summary>What a view that (re)connects receives: the current state, never fragments already published.</summary>
    internal IReadOnlyList<JsonObject> CreateSocketBootstrap() =>
    [
        StateEvent(),
        AgentEvent(),
        ModelEvent(),
        SurfacesEvent(),
        SessionEvent(),
        new() { ["type"] = "transcript", ["items"] = _transcript.Snapshot() },
        VoiceEvent(),
        BootEvent(),
        ContextEvent(),
        .. UpdateNotices(),
    ];

    // ---- the conversation ---------------------------------------------------------------------------------------

    private void OnMessageAdded(ConversationMessage message)
    {
        if (!message.IsUser)
        {
            ShellTraceSink.Record(ShellTraceScopes.Turn, ShellTraceSink.TurnId, ShellTraceStages.VisibleText);
        }

        if (message.IsUser)
        {
            if (_sessionLabel is null)
            {
                _sessionLabel = Clip(message.Body, 40);
                _sessionLabelBy = FieldSessionStore.LabelByFirst;
            }

            Publish(ItemEvent(_transcript.You(message.Body, _viewModel.ThinksByApi)));
            Publish(SessionEvent());
            return;
        }

        Publish(ItemEvent(_transcript.Words(message.Body, message.Silent, _viewModel.ThinksByApi)));
    }

    private void OnStepStarted(string id, string operation, JsonObject arguments)
    {
        JsonObject step = FieldStepProjection.Started(id, operation, arguments);
        Publish(ItemEvent(_transcript.Step(step)));
        Publish(StepEvent("start", step));
    }

    private void OnStepCompleted(NativeTurnStep step)
    {
        // What left the PC: a call that reaches the internet and got to its provider (the kernel let it through). An
        // update whose receipt says it asked no one (a store's copy, a development one) left nothing.
        bool english = UiLanguage.IsEnglish;
        string? net = step.Sent && NativeTurnLoop.Has(step.Operation, step.Arguments, OperationEffects.Network)
            && !(step.Operation == UpdatePanel.Operation && UpdatePanel.StayedIn(step))
            ? FieldStepProjection.NetWhat(step.Operation, step.Arguments, english)
            : null;
        JsonObject? view = FieldStepProjection.Finished(step.Id, step, net, english);
        if (english && view?["net"] is not null)
        {
            // The internet log the model reads (OwnReadings.Internet) keeps its Spanish words in an English view.
            view["netEs"] = FieldStepProjection.NetWhat(step.Operation, step.Arguments, english: false);
        }

        if (view is null)
        {
            if (_transcript.Drop(step.Id) is { } reply)
            {
                Publish(ItemEvent(reply));
            }

            return;
        }

        Publish(ItemEvent(_transcript.Step(view)));
        Publish(StepEvent("end", view));
        // The view lights «Salió a internet» and adds it to the session's log (the step keeps it in the transcript).
        if (net is not null)
        {
            Publish(new JsonObject
            {
                ["type"] = "net",
                ["what"] = net,
                ["ts"] = DateTimeOffset.Now.ToString("HH:mm", CultureInfo.InvariantCulture),
            });
        }

        // Bypass ran a call normal mode would have asked about: the conversation says so (design v4), as its step ended
        // (2026-10-22, review of the App: one that reached its provider and failed was said done too). «hecho» only for
        // an effect read back; a state already there, an input delivered unread or one that may have run say so. Uso real
        // 2026-11-02: a call the person said «sí» to was asked, whatever the mode is now, and is never said unasked.
        string? bypassed = step.Asked ? null : (string?)view["status"] switch
        {
            "ok" => UiLanguage.Say(english, "hecho sin preguntar", "done without asking"),
            "same" => UiLanguage.Say(english, "sin preguntar, ya estaba así", "without asking · already set"),
            "sent" => UiLanguage.Say(english, "enviado sin preguntar, sin comprobar", "sent without asking, not verified"),
            "read" => UiLanguage.Say(english, "leído sin preguntar", "read without asking"),
            "maybe" when step.Sent => UiLanguage.Say(english, "sin preguntar, puede haber corrido", "without asking, may have run"),
            _ => null,
        };
        if (bypassed is not null
            && ConfirmationModeStore.Read(MemoryOperationProtector.ResolveDataRoot()) == ConfirmationMode.Bypass
            && FieldStepProjection.NormalModeAsks(step.Operation, step.Arguments))
        {
            string title = FieldStepProjection.Label(step.Operation, step.Arguments, english);
            Publish(ItemEvent(_transcript.System("Bypass · " + bypassed + ": " + char.ToLowerInvariant(title[0]) + title[1..])));
        }

        if (step.Operation == "schedule.alarms" && step.Sent)
        {
            _triggerCount = null; // read again when the view asks
        }

        // The chat changed one of BAXY's own settings in the profile's file (baxy.settings.set): the App reads it again,
        // and a voice switched off stops speaking now, as the view's switch does (PutGeneral).
        if (step.Operation == "baxy.settings.set" && step.Sent)
        {
            _viewModel.Settings.Reload();
            if (_viewModel.Settings.VoiceMuted)
                _viewModel.SilenceVoice();
        }
    }

    private void OnConfirmationAsked(NativeTurnConfirmation asked, string? beatActivity)
    {
        // The card's words and its context in one language, read once.
        bool english = UiLanguage.IsEnglish;
        string? context = asked.Proposal ? beatActivity switch
        {
            HeartbeatMoment.Playing => UiLanguage.Say(english, "porque estás jugando", "because you're gaming"),
            HeartbeatMoment.InCall => UiLanguage.Say(english, "porque estás en una llamada", "because you're on a call"),
            HeartbeatMoment.Watching => UiLanguage.Say(english, "porque estás viendo algo", "because you're watching something"),
            _ => UiLanguage.Say(english, "por iniciativa propia", "unprompted"),
        } : null;
        string id = _transcript.NextId("k");
        JsonObject card = FieldStepProjection.Card(id, asked.Proposal ? "proposal" : "confirm",
            asked.Operation, asked.Arguments, asked.Risk, asked.ExpiresUtc, context, english, asked.EffectStarted, asked.Cause);
        _pendingCard = (id, asked);
        Publish(ItemEvent(_transcript.Card(card)));
    }

    private void OnConfirmationResolved(string outcome)
    {
        _pendingCard = null;
        string status = outcome switch
        {
            "approved" => "yes",
            "declined" => "no",
            "expired" => "expired",
            _ => "dropped",
        };
        if (_transcript.Resolve(status, null) is { } card)
        {
            Publish(ItemEvent(card));
        }
    }

    // The proposal on the card went to Windows as a notification (the person should not be spoken to): the card says
    // so from this fact, never from the activity the view reads later.
    private void OnProposalNotified(string question, string why, NativeTurnConfirmation asked)
    {
        if (_pendingCard is { } pending && ReferenceEquals(pending.Asked, asked)
            && _transcript.Notified(pending.Id) is { } card)
        {
            Publish(ItemEvent(card));
        }
    }

    private void OnVoicePartial(string text) => Publish(new JsonObject { ["type"] = "voice_partial", ["text"] = text });

    // The mouth moves with what is heard: the take's levels and when it sounds, or when the voice was cut.
    private void OnVoiceLip(JsonObject lip) => Publish(new JsonObject
    {
        ["type"] = "lip",
        ["t0"] = lip["t0"]?.DeepClone(),
        ["step"] = lip["step"]?.DeepClone(),
        ["env"] = lip["env"]?.DeepClone(),
        ["stop"] = lip["stop"]?.DeepClone(),
    });

    private void OnVoiceWake() => Publish(new JsonObject { ["type"] = "voice_wake" });

    private static JsonObject ItemEvent(JsonObject item) => new() { ["type"] = "item", ["item"] = item };

    private JsonObject StepEvent(string phase, JsonObject step)
    {
        var data = (JsonObject)step.DeepClone();
        data["type"] = "step";
        data["phase"] = phase;
        data["turn"] = _transcript.Turn ?? string.Empty;
        return data;
    }

    private async Task<FieldHttpResponse> HandleTurnAsync(string? body)
    {
        // The person's words arrived now; the turn may still wait for the engine's recovery or a heartbeat.
        long arrivedAt = System.Diagnostics.Stopwatch.GetTimestamp();
        string turnId = ShellTraceSink.TurnId;
        ShellTraceSink.Record(ShellTraceScopes.Bridge, turnId, ShellTraceStages.SubmitReceived);
        string text = (string?)ParseBody(body)?["text"] ?? string.Empty;
        await _viewModel.WaitForCoreRecoveryAsync().ConfigureAwait(true);
        if (!FieldBridgeContract.TryAcceptTurn(_viewModel.IsInputEnabled, text, out string turnError, out int turnStatus))
        {
            return Error(turnError, turnStatus);
        }

        try
        {
            _ = MissionInputContract.ValidateAndTrim(new MissionInput(text, MissionInputSource.Text));
        }
        catch (MissionInputRejectedException)
        {
            return Error("invalid_text", 400);
        }

        ShellTraceSink.Record(ShellTraceScopes.Bridge, turnId, ShellTraceStages.BridgeCrossed);
        if (!_viewModel.IsPowered)
        {
            // Writing to BAXY at rest wakes it (design v4), the voice too once the view turns its mode back on.
            await _viewModel.SetPowerAsync(true, _lifetimeCancellation).ConfigureAwait(true);
        }

        try
        {
            await _viewModel.SubmitAsync(new MissionInput(text, MissionInputSource.Text), arrivedAt, _lifetimeCancellation)
                .ConfigureAwait(true);
        }
        catch (MissionInputRejectedException)
        {
            return Error("invalid_text", 400);
        }

        ShellTraceSink.Record(ShellTraceScopes.Bridge, turnId, ShellTraceStages.ResponseFinal);
        return Json(new JsonObject { ["ok"] = true, ["status"] = "accepted" });
    }

    // ---- sessions -------------------------------------------------------------------------------------------------

    // The conversation's title as the model reads it (conversation.*): an untitled one is «Conversación nueva» whatever
    // the interface's language; the view says it in that language (ShownTitle).
    private string SessionTitle => _sessionLabel ?? "Conversación nueva";

    private string ShownTitle(bool english) => _sessionLabel ?? UiLanguage.Say(english, "Conversación nueva", "New conversation");

    private JsonObject SessionEvent() => new()
    {
        ["type"] = "session", ["id"] = _sessionId, ["label"] = ShownTitle(UiLanguage.IsEnglish),
    };

    private JsonObject Sessions()
    {
        bool english = UiLanguage.IsEnglish;
        var list = new JsonArray(new JsonObject
        {
            ["id"] = _sessionId,
            ["label"] = ShownTitle(english),
            ["ts"] = UiLanguage.Say(english, "ahora", "now"),
            ["turn_count"] = _transcript.Requests,
            ["current"] = true,
        });
        foreach (FieldSessionStore.Session kept in _sessions.List().Where(s => s.Id != _sessionId))
        {
            list.Add(new JsonObject
            {
                ["id"] = kept.Id,
                ["label"] = kept.Label.Length > 0 ? kept.Label : UiLanguage.Say(english, "Conversación", "Conversation"),
                ["ts"] = When(kept.Updated, english),
                ["turn_count"] = null,
                ["current"] = false,
            });
        }

        return new JsonObject { ["sessions"] = list, ["unsaved"] = _unsaved };
    }

    // ---- conversations asked by voice ------------------------------------------------------------------------------
    // pc-f6-sesiones (APLAZADOS f4-accesibilidad, 2026-10-25): what SessionsPanel and the chat's «+» do, asked by voice
    // (conversation.*, which NativeTurnLoop runs here after the catalog's schema and the kernel's policy). The turn that
    // asks belongs to the conversation on screen: its answer is kept there, and the conversation asked for opens once
    // that turn has let go (TurnReleased), with the same steps as the panel's. Its result says so (afterThisAnswer).

    private const int ConversationsListed = 20;
    // The conversation to open once the turn lets go: a kept one's id, or empty for a new one.
    private string? _openAfterTurn;

    private string? RunConversation(string operation, JsonObject arguments) => operation switch
    {
        "conversation.list" => ListConversations(),
        "conversation.new" => OpenAfterTurn(string.Empty, null),
        "conversation.open" => OpenConversation((string?)arguments["conversation"] ?? string.Empty),
        "conversation.rename" => RenameConversation((string?)arguments["conversation"],
            ((string?)arguments["title"] ?? string.Empty).Trim()),
        _ => null,
    };

    private string ListConversations()
    {
        List<(string Id, string Title, DateTimeOffset Updated)> all = AllConversations();
        return Ran(OperationVisibleFacts.VerificationOutputOnly, new JsonObject
        {
            ["conversations"] = new JsonArray([.. all.Take(ConversationsListed).Select(Listed)]),
            ["totalCount"] = all.Count,
        });
    }

    private string OpenConversation(string selector)
    {
        if (FindConversation(selector) is not { } found)
        {
            return NotFound(selector);
        }

        if (found.Id == _sessionId)
        {
            _openAfterTurn = null;
            return Ran(OperationVisibleFacts.VerificationUnchanged, new JsonObject
            {
                ["conversation"] = Listed(found),
                ["alreadyOpen"] = true,
            });
        }

        return OpenAfterTurn(found.Id, found);
    }

    // The result of an opening that waits for the turn: what opens, and that this turn's answer stays where it is.
    private string OpenAfterTurn(string id, (string Id, string Title, DateTimeOffset Updated)? kept)
    {
        _openAfterTurn = id;
        return Ran(OperationVisibleFacts.VerificationNone, new JsonObject
        {
            ["opens"] = kept is { } conversation ? Listed(conversation) : "new_conversation",
            ["afterThisAnswer"] = true,
            ["thisAnswerStaysIn"] = SessionTitle,
        });
    }

    private string RenameConversation(string? selector, string title)
    {
        (string Id, string Title, DateTimeOffset Updated)? found = selector is null
            ? (_sessionId, SessionTitle, DateTimeOffset.UtcNow)
            : FindConversation(selector);
        if (found is not { } conversation)
        {
            return NotFound(selector ?? string.Empty);
        }

        string renamed;
        if (conversation.Id == _sessionId && RenameCurrent(title))
        {
            renamed = SessionTitle;
        }
        else if (conversation.Id == _sessionId)
        {
            return Failed("conversation_not_renamed", null);
        }
        else if (_sessions.Rename(conversation.Id, title) && _sessions.Load(conversation.Id)?.Label is { } label)
        {
            renamed = label;
            Publish(SurfacesEvent());
        }
        else
        {
            return Failed("conversation_not_renamed", null);
        }

        return Ran(renamed == title ? OperationVisibleFacts.VerificationReadback : OperationVisibleFacts.VerificationNone,
            new JsonObject
            {
                ["conversation"] = Listed((conversation.Id, renamed, conversation.Updated)),
                ["previousTitle"] = conversation.Title,
            });
    }

    // The one on screen first, then the kept ones from the newest, as the panel lists them.
    private List<(string Id, string Title, DateTimeOffset Updated)> AllConversations() =>
    [
        (_sessionId, SessionTitle, DateTimeOffset.UtcNow),
        .. _sessions.List().Where(s => s.Id != _sessionId)
            .Select(static s => (s.Id, s.Label.Length > 0 ? s.Label : "Conversación", s.Updated)),
    ];

    // By its id, else by its whole title, else by a part of it, without case or accents; null when none or several.
    private (string Id, string Title, DateTimeOffset Updated)? FindConversation(string selector)
    {
        List<(string Id, string Title, DateTimeOffset Updated)> all = AllConversations();
        selector = selector.Trim();
        string folded = NetworkEgress.Folded(selector);
        List<(string Id, string Title, DateTimeOffset Updated)> found = [.. all.Where(c => c.Id == selector)];
        if (found.Count == 0)
        {
            found = [.. all.Where(c => NetworkEgress.Folded(c.Title) == folded)];
        }

        if (found.Count == 0)
        {
            found = [.. TitledWith(all, folded)];
        }

        return found.Count == 1 ? found[0] : null;
    }

    private static IEnumerable<(string Id, string Title, DateTimeOffset Updated)> TitledWith(
        IEnumerable<(string Id, string Title, DateTimeOffset Updated)> all, string folded) =>
        all.Where(c => folded.Length > 0 && NetworkEgress.Folded(c.Title).Contains(folded, StringComparison.Ordinal));

    // None answers to it, or several do (each one listed, to tell which).
    private string NotFound(string selector)
    {
        JsonNode[] several = [.. TitledWith(AllConversations(), NetworkEgress.Folded(selector.Trim()))
            .Take(ConversationsListed).Select(Listed)];
        return several.Length > 1
            ? Failed("conversation_ambiguous", new JsonObject { ["matches"] = new JsonArray(several) })
            : Failed("conversation_not_found", null);
    }

    private JsonObject Listed((string Id, string Title, DateTimeOffset Updated) conversation) => new()
    {
        ["id"] = conversation.Id,
        ["title"] = conversation.Title,
        ["when"] = conversation.Id == _sessionId ? "ahora" : Said(conversation.Updated),
        ["current"] = conversation.Id == _sessionId,
    };

    // When a kept conversation was last used, as the person would say it: «hoy 10:30», «ayer 21:05» or its date.
    private static string Said(DateTimeOffset utc)
    {
        DateTime local = utc.ToLocalTime().DateTime;
        string clock = local.ToString("HH:mm", CultureInfo.InvariantCulture);
        return (DateTime.Today - local.Date).Days switch
        {
            0 => "hoy " + clock,
            1 => "ayer " + clock,
            _ => local.ToString("yyyy-MM-dd ", CultureInfo.InvariantCulture) + clock,
        };
    }

    private static string Ran(string verification, JsonObject facts)
    {
        var result = new JsonObject
        {
            ["status"] = OperationStatuses.Completed,
            [OperationVisibleFacts.VerificationKey] = verification,
        };
        return With(result, facts);
    }

    private static string Failed(string error, JsonObject? facts) =>
        With(new JsonObject { ["status"] = OperationStatuses.Failed, ["error"] = error }, facts);

    private static string With(JsonObject result, JsonObject? facts)
    {
        foreach ((string key, JsonNode? value) in facts ?? [])
        {
            result[key] = value?.DeepClone();
        }

        return result.ToJsonString(SaidFolders.AsWritten);
    }

    // The turn that asked has let go: the conversation it asked for opens now, as the panel opens it. One the turn could
    // not take yet (a heartbeat took it first) waits for the next release.
    private async void OnTurnReleased()
    {
        if (_openAfterTurn is not { } id || _disposed)
        {
            return;
        }

        _openAfterTurn = null;
        try
        {
            FieldHttpResponse opened = id.Length == 0
                ? await NewSessionAsync(silence: false).ConfigureAwait(true)
                : await LoadSessionAsync(id).ConfigureAwait(true);
            if (opened.Status == 409 && opened.Body.Contains("turn_in_progress", StringComparison.Ordinal))
            {
                _openAfterTurn ??= id;
            }

            ShellTraceSink.Record(ShellTraceScopes.Bridge, ShellTraceSink.TurnId,
                opened.Status == 200 ? "conversation.opened" : "conversation.not_opened", "");
        }
        catch (Exception exception) when (exception is IOException or InvalidOperationException or JsonException
            or UnauthorizedAccessException or OperationCanceledException or ProtectedPayloadException)
        {
            ShellTraceSink.Record(ShellTraceScopes.Bridge, ShellTraceSink.TurnId, "conversation.not_opened",
                exception.GetType().Name.ToLowerInvariant());
        }
    }

    // Keeps the current conversation (what the view showed and the mind's own) when it holds anything: the mind's
    // conversation it kept, or null when there was nothing to keep or the mind exported none.
    private async Task<JsonArray?> SaveCurrentAsync(CancellationToken? cancellationToken = null)
    {
        if (_transcript.Items.Count == 0)
        {
            return null;
        }

        JsonArray? mind;
        try
        {
            mind = await _viewModel.ExportMindSessionAsync(cancellationToken ?? _lifetimeCancellation)
                .ConfigureAwait(true);
        }
        catch (OperationCanceledException) when (cancellationToken is not null)
        {
            // At close a mind that does not answer in time leaves what the view showed, still kept.
            mind = null;
        }

        // A mind lost in the turn exports nothing: its conversation stays as last kept, for the one that starts next
        // (2026-10-22, review of the App: the save wrote it away and the relaunched mind had nothing to get back).
        mind ??= _sessions.Load(_sessionId)?.Mind;
        Kept(_sessions.Save(new FieldSessionStore.Session(_sessionId, SessionTitle, _sessionCreated, DateTimeOffset.UtcNow,
            _transcript.Snapshot(), mind, _sessionLabelBy)));
        Publish(SurfacesEvent());
        return mind;
    }

    // Whether the conversation on screen reached the disk this time; a change makes the view read its history again.
    private void Kept(bool saved)
    {
        if (_unsaved == saved)
        {
            _unsaved = !saved;
            Interlocked.Increment(ref _sessionsRevision);
            ShellTraceSink.Record(ShellTraceScopes.Bridge, ShellTraceSink.TurnId,
                saved ? "conversation.kept_again" : "conversation.not_kept", "");
        }
    }

    // The person's name for the conversation on screen. One already on the disk gets it there first: a name that could
    // not be written is not given (REV_APP HIS-1, 2026-11-09: it lived in memory until the next save). One that is not
    // kept yet (nothing said in it) carries it to its first save.
    private bool RenameCurrent(string title)
    {
        if (_sessions.Load(_sessionId) is not null && !_sessions.Rename(_sessionId, title))
        {
            return false;
        }

        _sessionLabel = title;
        _sessionLabelBy = FieldSessionStore.LabelByPerson;
        Publish(SessionEvent());
        return true;
    }

    // What the conversation that closes needs to be named once the next one opened: its id and its mind conversation as
    // kept; nothing when the person named it (then it is never named again) or the mind kept none.
    private (string Id, JsonArray Mind)? Closing(JsonArray? mind) =>
        mind is not null && _sessionLabelBy != FieldSessionStore.LabelByPerson ? (_sessionId, mind) : null;

    /// <summary>
    /// Owner, 2026-11-08: «al momento de yo darle a nueva conversación … que el LLM reciba la instrucción de darle un
    /// nombre a la conversación … para después yo poder ubicarla». Asked once the next conversation opened, so the person
    /// never waits for it; the model writes it (session.title, Mind.title_of). With none, the conversation keeps its
    /// first words, and the panel shows when it was used beside them. A name the person gave meanwhile stays.
    /// </summary>
    private async Task NameClosedAsync((string Id, JsonArray Mind)? closing)
    {
        if (closing is not { } closed)
        {
            return;
        }

        string? title;
        try
        {
            title = await _viewModel.TitleMindSessionAsync(closed.Mind, _lifetimeCancellation).ConfigureAwait(true);
        }
        catch (Exception exception) when (exception is OperationCanceledException or IOException
            or InvalidOperationException or JsonException)
        {
            title = null;
        }

        if (_disposed || title is not { Length: > 0 and <= MaximumSessionLabel })
        {
            return;
        }

        if (closed.Id == _sessionId)
        {
            // Opened again before the name came: it is named on screen, unless the person named it meanwhile.
            if (_sessionLabelBy != FieldSessionStore.LabelByPerson)
            {
                _sessionLabel = title;
                _sessionLabelBy = FieldSessionStore.LabelByModel;
                Publish(SessionEvent());
            }

            return;
        }

        if (_sessions.Load(closed.Id) is { } kept && kept.LabelBy != FieldSessionStore.LabelByPerson
            && _sessions.Save(kept with { Label = title, LabelBy = FieldSessionStore.LabelByModel }))
        {
            Interlocked.Increment(ref _sessionsRevision);
            Publish(SurfacesEvent());
        }
    }

    private async Task<FieldHttpResponse> NewSessionAsync(bool silence = true)
    {
        if (_viewModel.IsBusy)
        {
            return Error("turn_in_progress", 409);
        }

        (string Id, JsonArray Mind)? closing = Closing(await SaveCurrentAsync().ConfigureAwait(true));
        if (!await _viewModel.StartNewUiSessionAsync(_lifetimeCancellation, silence).ConfigureAwait(true))
        {
            return Error(_viewModel.IsBusy ? "turn_in_progress" : "session_not_started", 409);
        }

        StartSession(NewSessionId(), null, DateTimeOffset.UtcNow, null);
        UnhandledFailures.Watch(NameClosedAsync(closing), "conversation.name");
        return Json(new JsonObject { ["ok"] = true, ["id"] = _sessionId });
    }

    private async Task<FieldHttpResponse> LoadSessionAsync(string id)
    {
        if (id == _sessionId)
        {
            return Json(new JsonObject { ["ok"] = true });
        }

        if (_sessions.Load(id) is not { } kept)
        {
            return Error("session_not_found", 404);
        }

        if (_viewModel.IsBusy)
        {
            return Error("turn_in_progress", 409);
        }

        (string Id, JsonArray Mind)? closing = Closing(await SaveCurrentAsync().ConfigureAwait(true));
        // The heartbeat reads the session's words; the mind gets its own conversation back as it was kept.
        var messages = new List<ConversationMessage>();
        foreach (JsonNode? node in kept.Items)
        {
            if (node is JsonObject item && (string?)item["text"] is { Length: > 0 } text
                && (string?)item["who"] is "you" or "baxy")
            {
                messages.Add(new ConversationMessage((string?)item["who"] == "you" ? "Tú" : "BAXY", text,
                    (string?)item["who"] == "you", kept.Updated));
            }
        }

        if (!await _viewModel.OpenSessionAsync(kept.Mind, messages, _lifetimeCancellation).ConfigureAwait(true))
        {
            return Error("session_not_opened", 409);
        }

        StartSession(kept.Id, kept.Label, kept.Created, kept.Items, kept.LabelBy);
        UnhandledFailures.Watch(NameClosedAsync(closing), "conversation.name");
        return Json(new JsonObject { ["ok"] = true });
    }

    private void StartSession(string id, string? label, DateTimeOffset created, JsonArray? items,
        string labelBy = FieldSessionStore.LabelByFirst)
    {
        _sessionId = id;
        _sessionLabel = string.IsNullOrWhiteSpace(label) ? null : label;
        _sessionLabelBy = labelBy;
        _sessionCreated = created;
        if (_unsaved)
        {
            // It was said of the conversation that was on screen; this one has had no save yet.
            _unsaved = false;
            Interlocked.Increment(ref _sessionsRevision);
        }

        Reopen(_transcript, items, _viewModel.Ringing);
        Publish(new JsonObject { ["type"] = "transcript", ["items"] = _transcript.Snapshot() });
        Publish(SessionEvent());
        Publish(SurfacesEvent());
    }

    /// <summary>The conversation the person opens: what rang in it when it was kept rings no more
    /// (<see cref="FieldTranscript.Replace"/>), and what still rings is in it, live, whatever conversation it rang in (INT16).</summary>
    internal static void Reopen(FieldTranscript transcript, JsonArray? items, IEnumerable<RingNow> ringing)
    {
        transcript.Replace(items);
        foreach (RingNow ring in ringing)
        {
            _ = transcript.Ring(RingItem(ring));
        }
    }

    private FieldHttpResponse RenameSession(JsonObject? payload)
    {
        string id = (string?)payload?["id"] ?? string.Empty;
        string title = ((string?)payload?["title"] ?? string.Empty).Trim();
        if (title.Length is < 1 or > MaximumSessionLabel)
        {
            return Error("invalid_session", 400);
        }

        if (id == _sessionId)
        {
            return RenameCurrent(title) ? Json(new JsonObject { ["ok"] = true }) : Error("session_not_saved", 500);
        }

        return _sessions.Rename(id, title) ? Json(new JsonObject { ["ok"] = true }) : Error("session_not_found", 404);
    }

    // BAXY Renew al máximo 11.4 (identity: «se puede ver, editar y borrar entera»): every conversation goes, the one
    // shown included, which the mind leaves for a new one first, never kept. Only by its own request, as the memory's.
    private async Task<FieldHttpResponse> DeleteSessionsAsync(JsonObject? payload)
    {
        if ((string?)payload?["scope"] != "all")
        {
            return Error("invalid_scope", 400);
        }

        if (_viewModel.IsBusy)
        {
            return Error("turn_in_progress", 409);
        }

        if (!await _viewModel.StartNewUiSessionAsync(_lifetimeCancellation).ConfigureAwait(true))
        {
            return Error(_viewModel.IsBusy ? "turn_in_progress" : "session_not_started", 409);
        }

        int deleted = _sessions.DeleteAll();
        _viewModel.ClearLogAndCaptures();
        StartSession(NewSessionId(), null, DateTimeOffset.UtcNow, null);
        await _viewModel.ForgetMindTraceAsync(_lifetimeCancellation).ConfigureAwait(true);
        return Json(new JsonObject { ["ok"] = true, ["deleted"] = deleted });
    }

    // Memory forgot everything (the chat's memory.forget or the panel's): the kept conversations, which hold what memory
    // calls read, go too; the one shown stays on screen and is kept again as it goes on.
    private void OnEverythingForgotten()
    {
        _sessions.DeleteAll(keep: _sessionId);
        UnhandledFailures.Watch(_viewModel.ForgetMindTraceAsync(_lifetimeCancellation), "trace.forget");
        Publish(SurfacesEvent());
    }

    /// <summary>
    /// PRV1 D7 (INFORME_PRV1 §9, 2026-11-10): what «Olvidar todo» takes besides the memories (the DELETE /memory route and
    /// <see cref="OnEverythingForgotten"/>): the kept conversations other than the one on screen, which stays, and the
    /// conversation's log. The memory panel offered the button only with memories, and with none these had no way out of
    /// the interface; it offers it whenever any of them is here.
    /// </summary>
    private JsonObject Kept() => new()
    {
        ["conversations"] = _sessions.List().Count(session => session.Id != _sessionId),
        ["log"] = _viewModel.ConversationLogHoldsAny,
    };

    private static string NewSessionId() => Guid.NewGuid().ToString("N")[..12];

    // When a kept conversation was last used, as the sessions panel says it in the interface's language.
    private static string When(DateTimeOffset utc, bool english)
    {
        DateTime local = utc.ToLocalTime().DateTime;
        int days = (DateTime.Today - local.Date).Days;
        CultureInfo culture = UiLanguage.CultureOf(english);
        return days switch
        {
            0 => local.ToString("HH:mm", CultureInfo.InvariantCulture),
            1 => UiLanguage.Say(english, "ayer", "yesterday"),
            < 7 => local.ToString("ddd", culture).TrimEnd('.'),
            _ => local.ToString(UiLanguage.Say(english, "d MMM", "MMM d"), culture).TrimEnd('.'),
        };
    }

    // ---- triggers (BAXY's alarms and reminders) -------------------------------------------------------------------

    private async Task<FieldHttpResponse> TriggersAsync()
    {
        OperationResponse? response = await _viewModel.SendPanelOperationAsync("schedule.alarms",
            new JsonObject { ["action"] = "list", ["limit"] = 50 }, _lifetimeCancellation).ConfigureAwait(true);
        return TriggersReply(response);
    }

    private async Task<FieldHttpResponse> CancelTriggerAsync(JsonObject? payload)
    {
        string at = ((string?)payload?["at"] ?? string.Empty).Trim();
        string kind = (string?)payload?["kind"] is "alarm" ? "alarm" : "reminder";
        if (at.Length is < 4 or > 32)
        {
            return Error("invalid_trigger", 400);
        }

        // The list says when it rings as «yyyy-MM-dd HH:mm» (next_local); schedule.alarms cancels by its local clock
        // («HH:mm»): the panel's Cancelar sent the whole date and was always refused (2026-10-17).
        Match clock = Regex.Match(at, @"(?<clock>\d{1,2}:\d{2})$", RegexOptions.CultureInvariant);
        if (clock.Success)
        {
            at = clock.Groups["clock"].Value;
        }

        OperationResponse? cancelled = await _viewModel.SendPanelOperationAsync("schedule.alarms",
            new JsonObject { ["action"] = "cancel", ["at"] = at, ["kind"] = kind }, _lifetimeCancellation).ConfigureAwait(true);
        if (cancelled is not { Status: OperationStatuses.Completed, Verified: true })
        {
            return Error(cancelled?.ErrorCode ?? "trigger_not_cancelled", 409);
        }

        return await TriggersAsync().ConfigureAwait(true);
    }

    private FieldHttpResponse TriggersReply(OperationResponse? response)
    {
        if (response is not { Status: OperationStatuses.Completed } || response.Result is not { ValueKind: JsonValueKind.Object } result
            || !result.TryGetProperty("notifications", out JsonElement notifications) || notifications.ValueKind != JsonValueKind.Array)
        {
            return Error(response?.ErrorCode ?? "triggers_unavailable", 503);
        }

        var items = new JsonArray();
        foreach (JsonElement item in notifications.EnumerateArray())
        {
            items.Add(new JsonObject
            {
                ["kind"] = item.TryGetProperty("kind", out JsonElement kind) ? kind.GetString() : "reminder",
                ["title"] = item.TryGetProperty("title", out JsonElement title) ? title.GetString() : null,
                ["next_local"] = item.TryGetProperty("nextRunLocal", out JsonElement next) ? next.GetString() : null,
                ["state"] = item.TryGetProperty("state", out JsonElement state) ? state.GetString() : null,
            });
        }

        int count = result.TryGetProperty("count", out JsonElement total) && total.TryGetInt32(out int n) ? n : items.Count;
        if (_triggerCount != count)
        {
            _triggerCount = count;
            Publish(SurfacesEvent());
        }

        return Json(new JsonObject { ["count"] = count, ["items"] = items, ["truncated"] = count > items.Count });
    }

    // ---- what rings now (ALR1) -------------------------------------------------------------------------------------

    // An alarm or a reminder this App rings: its card, with its words, until it is answered or ends.
    private void OnRingChanged(RingNow ring) => Publish(ItemEvent(_transcript.Ring(RingItem(ring))));

    // One card each time it rings (INT16B, third blind review): a daily alarm's task rings every day under the same name,
    // and named by the task alone, today's ring took the place of yesterday's card, up in the conversation, unseen.
    internal static JsonObject RingItem(RingNow ring) => new()
    {
        ["who"] = "ring",
        ["id"] = "ring-" + ring.TaskName[^32..] + "-" + ring.RangUtc.UtcTicks.ToString(CultureInfo.InvariantCulture),
        ["ts"] = ring.RangUtc.ToLocalTime().ToString("HH:mm", CultureInfo.InvariantCulture),
        ["ring"] = new JsonObject
        {
            ["id"] = ring.Id,
            ["kind"] = ring.Kind,
            ["title"] = ring.Title,
            ["clock"] = ring.Clock,
            ["words"] = ring.Words,
            ["status"] = ring.Status,
        },
    };

    // The card's Stop (or Done) and Snooze: schedule.alarms through the kernel, as the model's call would.
    private async Task<FieldHttpResponse> AnswerRingAsync(JsonObject? payload)
    {
        string id = ((string?)payload?["id"] ?? string.Empty).Trim();
        string action = (string?)payload?["action"] ?? string.Empty;
        if (!Regex.IsMatch(id, "^[0-9a-f]{8}$", RegexOptions.CultureInvariant) || action is not ("stop" or "snooze"))
        {
            return Error("invalid_ring_answer", 400);
        }

        OperationResponse? answered = await _viewModel.AnswerRingAsync(id, action, _lifetimeCancellation)
            .ConfigureAwait(true);
        return answered is { Status: OperationStatuses.Completed, Verified: true }
            ? Json(new JsonObject { ["ok"] = true })
            : Error(answered?.ErrorCode ?? "ring_not_answered", 409);
    }

    // ---- settings ---------------------------------------------------------------------------------------------------

    // «Arrancar con Windows» is the Run key's entry for this executable, when this copy may own the sign-in start
    // (WindowsAutostartRegistration); null when it may not («not_this_copy»: a worktree or development build) or the key
    // could not be read («unreadable»), so the view says which (it used to call both a failed read).
    private static (bool? On, string? Blocked) Autostart()
    {
        try
        {
            bool? on = WindowsAutostartRegistration.CreateDefault().IsRegisteredForCurrent();
            return (on, AutostartBlocked(on, AppContext.BaseDirectory));
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException or InvalidOperationException
            or System.Security.SecurityException)
        {
            return (null, "unreadable");
        }
    }

    /// <summary>
    /// Why this copy may not start with Windows, or null when it may (<paramref name="on"/> read). LEG1 §5 (2026-11-09): a copy
    /// from Steam or itch.io may not either (only the installed one and the owner's checkout do), and Settings called it a
    /// development copy that opens with run_renew.cmd; its store is said instead, from the packager's distribution.json beside
    /// <c>app\</c> (scripts/build_steam.ps1, read as BaxyDistribution.Read does).
    /// </summary>
    internal static string? AutostartBlocked(bool? on, string appFolder)
    {
        if (on is not null)
        {
            return null;
        }

        try
        {
            using JsonDocument marker = JsonDocument.Parse(File.ReadAllText(Path.Combine(appFolder, "..", "distribution.json")));
            JsonElement value = marker.RootElement;
            string? Text(string name) => value.ValueKind == JsonValueKind.Object && value.TryGetProperty(name, out JsonElement field)
                && field.ValueKind == JsonValueKind.String ? field.GetString() : null;
            return Text("schema") == "baxy.distribution.v1" && Text("channel") is "steam" or "itch" ? Text("channel") + "_copy" : "not_this_copy";
        }
        catch (Exception unreadable) when (unreadable is IOException or UnauthorizedAccessException or JsonException)
        {
            return "not_this_copy";
        }
    }

    private FieldHttpResponse PutGeneral(JsonObject? body)
    {
        if (body is null)
        {
            return Error("invalid_settings", 400);
        }

        if (body["autostart"] is JsonValue autostart && autostart.TryGetValue(out bool start))
        {
            try
            {
                if (!WindowsAutostartRegistration.CreateDefault().SetForCurrent(start, Environment.GetCommandLineArgs()))
                {
                    return Error("autostart_not_available", 409);
                }
            }
            catch (Exception exception) when (exception is IOException or UnauthorizedAccessException
                or InvalidOperationException or System.Security.SecurityException)
            {
                return Error("autostart_not_changed", 409);
            }
        }

        bool echoCancel = _viewModel.Settings.EchoCancel;
        _viewModel.Settings.ApplyGeneral(body);
        if (_viewModel.Settings.VoiceMuted)
            _viewModel.SilenceVoice();
        if (_viewModel.Settings.EchoCancel != echoCancel)
            _ = _viewModel.ApplyEchoCancelAsync(CancellationToken.None);
        return Json(_viewModel.Settings.GeneralJson(Autostart()));
    }

    // Steam (2026-11-04): the person's choice of language («auto», «es» or «en»), which the host keeps and the view reads
    // back in GET /settings/general («language», and «languageInUse» for what «auto» stands for). BAXY's own words follow
    // it from now on (UiLanguage), the tray and the start's screen from the file at the next start; what the model
    // reads does not change.
    private FieldHttpResponse PutLanguage(JsonObject? body)
    {
        string? choice = body?["lang"] is JsonValue value && value.TryGetValue(out string? said) ? said : null;
        if (!_viewModel.Settings.ApplyLanguage(choice))
        {
            return Error("invalid_language", 400);
        }

        UiLanguage.Use(choice);
        return Json(new JsonObject { ["ok"] = true, ["language"] = choice, ["languageInUse"] = UiLanguage.Current });
    }

    // The bypass switch of BAXY's own view writes the profile's confirmation mode through the same store the engine
    // reads on every invocation (ConfirmationModeStore). A body that names no policy changes nothing.
    private static FieldHttpResponse PutConfirmationMode(string? body)
    {
        ConfirmationMode? mode = ParseBody(body)?["confirmationPolicy"] is JsonValue policy
            && policy.TryGetValue(out string? raw)
            && raw is "normal" or "bypass"
                ? ConfirmationModeStore.Parse(raw)
                : null;
        if (mode is not { } chosen)
        {
            return Error("invalid_confirmation_policy", 400);
        }

        string root = MemoryOperationProtector.ResolveDataRoot();
        ConfirmationModeStore.Write(root, chosen);
        JsonObject written = ConfirmationPolicy(root);
        written["ok"] = true;
        return Json(written);
    }

    // The mode, and how long a card waits for the person: the engine's confirmation and a heartbeat's proposal (the
    // view says these, never the design's own 10 minutes).
    private static JsonObject ConfirmationPolicy(string root) => new()
    {
        ["confirmationPolicy"] = ConfirmationModeStore.Read(root) == ConfirmationMode.Bypass ? "bypass" : "normal",
        ["confirmSeconds"] = (int)Baxy.Kernel.Mission.ConfirmationLifetime.Challenge.TotalSeconds,
        ["proposalSeconds"] = (int)NativeTurnLoop.ProposalLifetime.TotalSeconds,
    };

    private static JsonObject PresentationMode(bool accessible) => new()
    {
        ["active"] = accessible ? PresentationModeStore.Accessible : PresentationModeStore.Normal,
    };

    // ---- state events -------------------------------------------------------------------------------------------------

    private void OnViewModelPropertyChanged(object? sender, PropertyChangedEventArgs eventArgs)
    {
        string? name = eventArgs.PropertyName;
        if (name is nameof(MainWindowViewModel.IsReady) or nameof(MainWindowViewModel.IsBusy)
            or nameof(MainWindowViewModel.Failure) or nameof(MainWindowViewModel.IsMindPreparing)
            or nameof(MainWindowViewModel.IsMindReady) or nameof(MainWindowViewModel.HasPendingConfirmation)
            or nameof(MainWindowViewModel.IsPowered) or nameof(MainWindowViewModel.IsAwaitingMind))
        {
            Publish(AgentEvent());
        }

        if (name is nameof(MainWindowViewModel.IsReady) or nameof(MainWindowViewModel.IsMindReady))
        {
            Publish(ModelEvent());
        }

        if (name is nameof(MainWindowViewModel.IsBusy) or nameof(MainWindowViewModel.IsListening)
            or nameof(MainWindowViewModel.IsVoiceSpeaking) or nameof(MainWindowViewModel.Failure)
            or nameof(MainWindowViewModel.StatusDescription) or nameof(MainWindowViewModel.IsMindReady))
        {
            Publish(StateEvent());
        }

        if (name is nameof(MainWindowViewModel.IsListening) or nameof(MainWindowViewModel.IsWakeListening)
            or nameof(MainWindowViewModel.IsVoiceSpeaking) or nameof(MainWindowViewModel.IsMicAvailable)
            or nameof(MainWindowViewModel.VoiceFailure) or nameof(MainWindowViewModel.VoicePieces))
        {
            Publish(VoiceEvent());
        }

        if (name is nameof(MainWindowViewModel.IsMindReady) or nameof(MainWindowViewModel.IsMindPreparing)
            or nameof(MainWindowViewModel.VoicePieces) or nameof(MainWindowViewModel.MindStartedAt)
            or nameof(MainWindowViewModel.MindReading))
        {
            Publish(BootEvent());
        }

        if (name is nameof(MainWindowViewModel.OwnerActivity))
        {
            Publish(ContextEvent());
        }

        // A turn that ended keeps the conversation as it stands (the session survives a restart).
        if (name is nameof(MainWindowViewModel.IsBusy) && !_viewModel.IsBusy && !_disposed)
        {
            UnhandledFailures.Watch(SaveCurrentAsync(), "conversation.save");
        }
    }

    // «quiet» is the state without the voice: the view shows «speaking» while the voice really sounds (its lip
    // timeline) and this one in the voice's grace after it, so a notice said while the turn runs goes back to thinking.
    private JsonObject StateEvent() => new()
    {
        ["type"] = "state",
        ["value"] = CurrentConversationState(),
        ["quiet"] = QuietConversationState(),
        // APP1 (REV_APP OVL-2): whether a turn runs, apart from listening or speaking; the overlay ends its turn with it
        ["busy"] = _viewModel.IsBusy,
    };

    private string CurrentConversationState() =>
        _viewModel.IsVoiceSpeaking ? "speaking" : QuietConversationState();

    private string QuietConversationState() =>
        _viewModel.IsListening ? "listening"
        : _viewModel.IsBusy ? "thinking"
        : _viewModel.Failure is not null || MindUnavailable ? "error"
        : "idle";

    internal JsonObject AgentEvent()
    {
        JsonObject agent = AgentStatus();
        agent["type"] = "agent";
        return agent;
    }

    // The interface's gate: whether a turn is accepted now, the failure's code and whether a call waits for the person.
    private JsonObject AgentStatus() => new()
    {
        ["built"] = _viewModel.IsReady,
        ["ready"] = _viewModel.IsReady && _viewModel.IsMindReady && !_viewModel.IsBusy && !_viewModel.IsMindPreparing,
        ["failure"] = _viewModel.Failure ?? (MindUnavailable ? "mind_unavailable" : null),
        ["pendingConfirmation"] = _viewModel.HasPendingConfirmation,
        // Uso 95 (F9): a message of the person's waits for the mind (it starts or is relaunched), and why the mind's last
        // start failed (ram_insuficiente, vram_insuficiente, memoria_insuficiente, …) while none is up: the view says
        // both instead of a turn that ended with nothing.
        ["waitingForMind"] = _viewModel.IsAwaitingMind,
        ["failureCause"] = _viewModel.MindFailureCause,
        // VIVO1 F4: why the server of another model refused the turn, in the translator's words (ExternalModel.Refusal).
        ["failureWhy"] = _viewModel.Failure is "model_refused" or "model_refused_after_call"
            ? _viewModel.ExternalModelState.Refusal
            : null,
        // REV_VISTA V-04: its kind, which the view says in its own language (an English view showed the Spanish words).
        ["failureKind"] = _viewModel.Failure is "model_refused" or "model_refused_after_call"
            ? _viewModel.ExternalModelState.RefusalKind
            : null,
        ["failureMemory"] = FailureMemory(),
        ["failureRead"] = FailureRead(),
        // At rest or active: the rail's power row and the tray menu change it, the view only shows it.
        ["powered"] = _viewModel.IsPowered,
    };

    private JsonObject VoiceEvent()
    {
        JsonObject voice = VoiceStatus();
        voice["type"] = "voice";
        return voice;
    }

    private bool NoWake() =>
        _viewModel.VoicePieces is { Pending: false, WakeAvailable: false, SttAvailable: true, WaitingMemory: null };

    private JsonObject VoiceStatus() => new()
    {
        ["available"] = _viewModel.IsMicAvailable,
        ["running"] = _viewModel.IsListening || _viewModel.IsWakeListening,
        ["mode"] = _viewModel.IsListening ? "direct" : _viewModel.IsWakeListening ? "wake" : "off",
        ["speaking"] = _viewModel.IsVoiceSpeaking,
        ["last_error"] = _viewModel.VoicePieces?.WaitingMemory is not null ? "voice_waiting_memory"
            : _viewModel.VoiceFailure ?? (_viewModel.IsMicAvailable ? null : "voice_unavailable"),
        // Uso 95 (uso real 2026-11-04 13:19): the ear waits for memory, not for a microphone: what it needs and found.
        ["waiting_memory"] = _viewModel.VoicePieces?.WaitingMemory is { } memory
            ? new JsonObject { ["need_mb"] = memory.NeedMb, ["left_mb"] = memory.LeftMb }
            : null,
        // uso-116: a microphone with no recogniser is not «no hay micrófono».
        ["no_recognizer"] = _viewModel.VoicePieces is { Pending: false, InputAvailable: true, SttAvailable: false, WaitingMemory: null },
        // V132: the voice settled with its recogniser and no wake word (its folder gone or changed: why, when the
        // installation named one): «Siempre activo» cannot answer to «BAXY» while holding to talk still can, and the view
        // says it instead of an ear that is silently off. An ear without its recogniser is said as such (no_recognizer).
        ["no_wake"] = NoWake(),
        ["wake_problem"] = NoWake() ? _viewModel.WakeProblem : null,
    };

    // The start's pieces, each marked only once the mind reports it (null before); no percentage is made up.
    internal JsonObject BootEvent()
    {
        MindVoiceStatus? voice = _viewModel.VoicePieces;
        return new JsonObject
        {
            ["type"] = "boot",
            ["stt"] = voice?.SttAvailable,
            ["wake"] = voice?.WakeAvailable,
            ["tts"] = voice?.SpeechAvailable,
            ["model"] = _viewModel.IsMindReady,
            ["startedAt"] = _viewModel.MindStartedAt.ToUnixTimeMilliseconds(),
            ["readyAt"] = _viewModel.MindReadyAt?.ToUnixTimeMilliseconds(),
            ["failed"] = !_viewModel.IsMindReady && _viewModel.MindFailed ? "mind_unavailable" : null,
            // Uso 95: a relaunch after a failed start shows why the start before failed (the lack of memory included).
            ["lastFailure"] = _viewModel.MindFailureCause,
            ["failureMemory"] = FailureMemory(),
            ["failureRead"] = FailureRead(),
            // N9 (L5): how far a slow start has read, from the server's own count, and why it is slow.
            ["reading"] = _viewModel.MindReading is { } reading
                ? new JsonObject { ["done"] = reading.Done, ["total"] = reading.Total, ["seconds_left"] = reading.SecondsLeft }
                : null,
            ["onProcessor"] = _viewModel.MindOnProcessor,
            // QWB2: the tuned model the person chose and this start could not use (missing or damaged).
            ["tunedProblem"] = _viewModel.TunedModelProblem,
        };
    }

    // uso-116 (N23): «falta tanta RAM»: the figures of the lack of memory the cause names (need_mb, free_mb, as the ear's).
    private JsonObject? FailureMemory() => _viewModel.MindFailureMemory is { } memory
        ? new JsonObject { ["need_mb"] = memory.NeedMb, ["free_mb"] = memory.FreeMb }
        : null;

    // N9 (L5): «prepararlo tardaría tanto»: the figures of the read too slow the cause names.
    private JsonObject? FailureRead() => _viewModel.MindFailureRead is { } read
        ? new JsonObject { ["tokens_per_s"] = read.TokensPerS, ["minutes"] = read.NeedMinutes }
        : null;

    private JsonObject ContextEvent() => new()
    {
        ["type"] = "context",
        ["activity"] = _viewModel.OwnerActivity switch
        {
            HeartbeatMoment.Playing => "game",
            HeartbeatMoment.InCall => "call",
            HeartbeatMoment.Watching => "video",
            HeartbeatMoment.Away => "away",
            _ => "free",
        },
    };

    private JsonObject Surfaces() => new()
    {
        ["sessions"] = 1 + _sessions.List().Count(s => s.Id != _sessionId),
        ["sessions_revision"] = Volatile.Read(ref _sessionsRevision),
        ["memory"] = _memory.Count,
        ["memory_revision"] = Volatile.Read(ref _memoryRevision),
        ["tools"] = Baxy.Kernel.Operations.ProductCatalog.ToolDescriptors.Count,
        ["triggers"] = _triggerCount,
    };

    private JsonObject SurfacesEvent()
    {
        JsonObject surfaces = Surfaces();
        surfaces["type"] = "surfaces";
        return surfaces;
    }

    private void OnMemoryChanged()
    {
        Interlocked.Increment(ref _memoryRevision);
        _memoryCountStale = true;
    }

    private async Task<FieldHttpResponse> VoiceStartAsync()
    {
        if (!FieldBridgeContract.TryAcceptVoiceControl(_viewModel.IsReady, out string error, out int status))
        {
            return Error(error, status);
        }

        bool running = _viewModel.IsWakeListening
            || await _viewModel.SetWakeVoiceAsync(true, _lifetimeCancellation).ConfigureAwait(true);
        return Json(new JsonObject
        {
            ["ok"] = running,
            ["running"] = running,
            ["last_error"] = running ? null : "voice_unavailable",
        }, running ? 200 : 503);
    }

    // ---- model, voice inventory, metrics ----------------------------------------------------------------------------

    internal static FieldModelIdentity ResolveModelIdentity(string? modelPath)
    {
        string fileName = string.IsNullOrWhiteSpace(modelPath) ? string.Empty : Path.GetFileName(modelPath);
        string alias = string.IsNullOrWhiteSpace(fileName) ? "local-model" : Path.GetFileNameWithoutExtension(fileName);
        string family = alias switch
        {
            var value when value.Contains("qwen3.5", StringComparison.OrdinalIgnoreCase) => "qwen 3.5",
            var value when value.Contains("qwen3", StringComparison.OrdinalIgnoreCase) => "qwen 3",
            var value when value.Contains("phi-4", StringComparison.OrdinalIgnoreCase) => "phi 4",
            var value when value.Contains("gemma-4", StringComparison.OrdinalIgnoreCase) => "gemma 4",
            var value when value.Contains("llama", StringComparison.OrdinalIgnoreCase) => "llama",
            _ => "local model",
        };
        Match parameterMatch = Regex.Match(alias, @"(?<![A-Za-z0-9])(?<value>\d+(?:\.\d+)?B)(?=$|[-_.])",
            RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);
        if (!parameterMatch.Success)
        {
            parameterMatch = Regex.Match(alias, @"E(?<value>\d+(?:\.\d+)?B)(?=$|[-_.])",
                RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);
        }

        return new FieldModelIdentity(alias, fileName, family,
            parameterMatch.Success ? parameterMatch.Groups["value"].Value.ToLowerInvariant() : "unknown");
    }

    // The voice models are the launcher's (BAXY_RENEW_STT_DIR, _TTS_DIR, _WAKE_DIR): each is named by its path and
    // shown as on disk only when the file the mind loads is there (voice.py, voice_output.py).
    private static JsonObject VoiceInventory()
    {
        string stt = Environment.GetEnvironmentVariable("BAXY_RENEW_STT_DIR") ?? string.Empty;
        string tts = Environment.GetEnvironmentVariable("BAXY_RENEW_TTS_DIR") ?? string.Empty;
        string wake = Environment.GetEnvironmentVariable("BAXY_RENEW_WAKE_DIR") ?? string.Empty;
        return new JsonObject
        {
            ["stt"] = new JsonObject
            {
                ["name"] = Path.GetFileName(stt.TrimEnd('\\', '/')),
                ["downloaded"] = stt.Length > 0 && File.Exists(Path.Combine(stt, "tokens.txt")),
            },
            ["tts"] = new JsonObject
            {
                ["name"] = Path.GetFileName(tts.TrimEnd('\\', '/')),
                ["downloaded"] = tts.Length > 0 && File.Exists(Path.Combine(tts, "baxy-voice.json"))
                    && File.Exists(Path.Combine(tts, "voice.bin")),
            },
            ["wake"] = new JsonObject
            {
                ["name"] = Path.GetFileName(wake.TrimEnd('\\', '/')),
                ["downloaded"] = wake.Length > 0 && File.Exists(Path.Combine(wake, "config.json")),
            },
        };
    }

    // The stock model the package carries (THIRD_PARTY_NOTICES.md: unsloth/Qwen3.5-4B-GGUF, Qwen3.5-4B-Q4_K_M.gguf), by its SHA-256.
    internal const string StockModelName = "Qwen3.5-4B";
    internal const string StockModelSha256 = "00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4";

    // The model the mind was given (BAXY_MIND_LLM_GGUF) and its context, and whether it is the stock model: by the SHA-256 the
    // registry gave with it (TunedModel puts the tuned one's in its place), null when a launcher set the file itself and none
    // was given (scripts/run_renew.cmd gives the development mind a tuned file as BAXY's own: the view never calls it stock).
    private JsonObject CurrentSettings()
    {
        FieldModelIdentity identity = ResolveModelIdentity(Environment.GetEnvironmentVariable("BAXY_MIND_LLM_GGUF"));
        string? sha256 = Environment.GetEnvironmentVariable(MindRuntimeDiscovery.GgufSha256Variable);
        return new JsonObject
        {
            ["modelAlias"] = identity.Alias,
            ["ggufPath"] = identity.FileName,
            ["ctxSize"] = ContextSize(),
            ["stockName"] = StockModelName,
            ["ownIsStock"] = string.IsNullOrWhiteSpace(sha256) ? null : string.Equals(sha256.Trim(), StockModelSha256, StringComparison.OrdinalIgnoreCase),
        };
    }

    private bool MindUnavailable => !_viewModel.IsMindReady && !_viewModel.IsMindPreparing;

    // The model event: its identity once the mind serving it is ready, null before.
    private JsonObject ModelEvent() =>
        new() { ["type"] = "model", ["info"] = _viewModel.IsMindReady ? ModelInfo() : null };

    private JsonObject ModelInfo()
    {
        FieldModelIdentity identity = ResolveModelIdentity(Environment.GetEnvironmentVariable("BAXY_MIND_LLM_GGUF"));
        return new JsonObject
        {
            ["family"] = identity.Family,
            ["params"] = identity.Parameters,
            ["runtime"] = "local",
            ["context_size"] = ContextSize(),
        };
    }

    private int ContextSize()
    {
        // The same variable the mind passes to llama-server, and without it the mind's default on the backend its last
        // start said (llm_server.default_context); NVIDIA's until one did.
        string? raw = Environment.GetEnvironmentVariable(LocalContext.Variable);
        return int.TryParse(raw, NumberStyles.Integer, CultureInfo.InvariantCulture, out int value) && value > 0
            ? value
            : LocalContext.Automatic(_viewModel.MindBackend) ?? LocalContext.CudaAutomatic;
    }

    // A reading the PC did not give (no GPU counter, no temperature, no model process) travels as null; the view
    // shows «—».
    private static JsonObject MetricsJson(FieldMetricSnapshot metrics) => new()
    {
        ["cpu"] = metrics.Cpu,
        ["gpu"] = metrics.Gpu,
        ["temp"] = metrics.GpuTemperature,
        ["model_vram_gb"] = metrics.ModelVramGb,
        ["model_ram_gb"] = metrics.ModelRamGb,
    };

    /// <summary>Settings › Personalización «Probar»: the overlay shows an example in its corner.</summary>
    internal event Action? OverlayPreviewRequested;

    private bool HasPendingCard => _viewModel.HasPendingConfirmation;

    /// <summary>
    /// The person's answer to the card it names, from the view or the overlay: null when taken, else why not
    /// (nothing_pending, card_not_pending, turn_in_progress). Auditoría de la App (2026-10-23): an answer that names no card,
    /// or one that ended, never answers the next. A press while a turn runs is refused, never taken and lost.
    /// </summary>
    internal async Task<string?> AnswerCardAsync(bool approve, string card, long arrivedAt)
    {
        if (!_viewModel.HasPendingConfirmation)
        {
            return "nothing_pending";
        }

        if (_pendingCard is not { } pending || pending.Id != card)
        {
            return "card_not_pending";
        }

        return await _viewModel.AnswerConfirmationAsync(approve, arrivedAt, _lifetimeCancellation, pending.Asked).ConfigureAwait(true)
            ? null
            : _viewModel.HasPendingConfirmation ? "turn_in_progress" : "nothing_pending";
    }

    private static JsonObject? ParseBody(string? body)
    {
        if (string.IsNullOrWhiteSpace(body))
        {
            return new JsonObject();
        }

        try
        {
            return JsonNode.Parse(body) as JsonObject;
        }
        catch (JsonException)
        {
            return null;
        }
    }

    private static string Clip(string text, int maximum)
    {
        string single = string.Join(' ', text.Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries));
        return single.Length <= maximum ? single : single[..(maximum - 1)].TrimEnd() + "…";
    }

    // The person's Sí to a new profile: the unreadable one set aside (renamed with the date, never deleted) and BAXY
    // started on a new one. A folder that could not be renamed is said (profile_not_set_aside) and nothing moved.
    private async Task<FieldHttpResponse> StartFreshProfileAsync()
    {
        try
        {
            string? setAside = await _viewModel.StartFreshProfileAsync(_lifetimeCancellation).ConfigureAwait(true);
            return setAside is null
                ? Error("profile_not_unreadable", 409)
                : Json(new JsonObject { ["ok"] = true, ["setAside"] = Path.GetFileName(setAside) });
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            return Error("profile_not_set_aside", 409);
        }
    }

    private static FieldHttpResponse Json(JsonObject body, int status = 200) => FieldHttpResponse.Json(body, status);

    private static FieldHttpResponse Error(string code, int status) =>
        Json(new JsonObject { ["ok"] = false, ["error"] = code }, status);

    private bool Publish(JsonObject eventData) => _sink.Publish(eventData);

    public async ValueTask DisposeAsync()
    {
        if (_disposed)
        {
            return;
        }

        _disposed = true;
        _viewModel.MessageAdded -= OnMessageAdded;
        _viewModel.PropertyChanged -= OnViewModelPropertyChanged;
        _viewModel.MemoryChanged -= OnMemoryChanged;
        _viewModel.EverythingForgotten -= OnEverythingForgotten;
        _viewModel.StepStarted -= OnStepStarted;
        _viewModel.StepCompleted -= OnStepCompleted;
        _viewModel.ConfirmationAsked -= OnConfirmationAsked;
        _viewModel.ConfirmationResolved -= OnConfirmationResolved;
        _viewModel.ProposalNotificationRequested -= OnProposalNotified;
        _viewModel.VoicePartial -= OnVoicePartial;
        _viewModel.VoiceLip -= OnVoiceLip;
        _viewModel.VoiceWake -= OnVoiceWake;
        _viewModel.KeptConversation = null;
        _viewModel.Conversation = null;
        _viewModel.TurnReleased -= OnTurnReleased;
        _viewModel.TunedModelOnline -= OnTunedModelOnline;
        _viewModel.ModelDownloadOnline -= OnModelDownloadOnline;
        _viewModel.RingChanged -= OnRingChanged;
        try
        {
            // The conversation as it stands is kept when BAXY closes. FT/proveedores goal (review of the App): the window
            // cancels the lifetime before this, so the save asked the mind with a cancelled token and was dropped on
            // every close; it has its own short deadline (the mind is still up: the view model ends after the bridge).
            using var closing = new CancellationTokenSource(TimeSpan.FromSeconds(5));
            await SaveCurrentAsync(closing.Token).ConfigureAwait(false);
        }
        catch (Exception exception) when (exception is OperationCanceledException or IOException or InvalidOperationException)
        {
        }
    }
}
