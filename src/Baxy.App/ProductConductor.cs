using System.Text.Json.Nodes;

namespace Baxy.App;

internal enum ProductTurnTerminal
{
    Rejected,
    PublishedFinal,
    Filtered,
    AcceptedWithoutFinal,
    Silence,
    CompositionFailed,
}

internal sealed record ProductTurnResult(
    FieldHttpResponse Admission,
    ProductTurnTerminal Terminal,
    string? FinalText,
    string? Diagnostic,
    bool TimedOut,
    IReadOnlyList<JsonObject> PublicEvents,
    ProductPosteriorState Posterior);

internal sealed record ProductPosteriorState(
    int MessageCount,
    int UserMessageCount,
    bool IsBusy,
    bool IsInputEnabled,
    bool HasPendingPlan,
    int PendingCompositionCount,
    string? CompositionFailure,
    bool HasCompositionError,
    string? StatusDescription,
    string? MindReplyRejection);

/// <summary>
/// Windowless adapter over <see cref="FieldProductChannel"/>. Same admission,
/// turn and publication as the WebView bridge; adds diagnostic timeouts and
/// honest terminals. Does not invent a user-visible final or repair the session.
/// </summary>
internal sealed class ProductConductor : IAsyncDisposable
{
    private readonly MainWindowViewModel _viewModel;
    private readonly CollectingFieldEventSink _sink;
    private readonly FieldProductChannel _channel;
    private readonly FieldTelemetrySampler _telemetry;
    private readonly bool _ownsViewModel;

    internal ProductConductor(
        MainWindowViewModel viewModel,
        CollectingFieldEventSink sink,
        FieldProductChannel channel,
        FieldTelemetrySampler telemetry,
        bool ownsViewModel)
    {
        _viewModel = viewModel;
        _sink = sink;
        _channel = channel;
        _telemetry = telemetry;
        _ownsViewModel = ownsViewModel;
    }

    internal FieldProductChannel Channel => _channel;

    internal MainWindowViewModel ViewModel => _viewModel;

    internal CollectingFieldEventSink Sink => _sink;

    internal static ProductConductor Create(
        MainWindowViewModel viewModel,
        CancellationToken lifetime,
        bool ownsViewModel = false)
    {
        var sink = new CollectingFieldEventSink();
        var telemetry = new FieldTelemetrySampler();
        var channel = new FieldProductChannel(viewModel, sink, telemetry, lifetime);
        return new ProductConductor(viewModel, sink, channel, telemetry, ownsViewModel);
    }

    internal Task<FieldHttpResponse> HandleHttpAsync(
        string method,
        string path,
        string? body) =>
        _channel.HandleHttpAsync(method, path, body);

    internal Task<FieldHttpResponse> NewSessionAsync() =>
        HandleHttpAsync("POST", "/sessions/new", null);

    internal Task<FieldHttpResponse> UploadAsync() =>
        HandleHttpAsync("POST", "/upload", null);

    internal Task<ProductTurnResult> CancelAsync(
        TimeSpan timeout,
        CancellationToken cancellationToken) =>
        TurnAsync("cancelar", timeout, cancellationToken);

    internal Task<ProductTurnResult> ConfirmPendingAsync(
        ProductTurnResult initial,
        PendingOperationConfirmation? observed,
        string expectedOperation,
        JsonObject expectedArguments,
        TimeSpan timeout,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        if (initial.TimedOut || initial.Terminal != ProductTurnTerminal.PublishedFinal
            || initial.Diagnostic is not null || observed is null
            || !string.Equals(
                observed.Prepared.OperationName, expectedOperation, StringComparison.Ordinal)
            || !JsonNode.DeepEquals(
                JsonNode.Parse(observed.Prepared.Arguments.GetRawText()), expectedArguments)
            || !ReferenceEquals(observed, _viewModel.CaptureConductorConfirmation()))
        {
            return Task.FromResult(RejectConfirmation("confirmation_expectation_not_met"));
        }

        // No await between rechecking the same challenge/immutable Prepared
        // (including mission/invocation) and ordinary POST /turn. Its synchronous
        // submission reaches HandlePendingAsync and captures Confirmation before
        // its first await. The kernel still validates the token and expiry.
        return TurnAsync("confirmar", timeout, cancellationToken);
    }

    internal ProductTurnResult RejectConfirmation(string diagnostic) =>
        new(
            FieldHttpResponse.Json(new JsonObject { ["error"] = diagnostic }, 409),
            ProductTurnTerminal.Rejected,
            FinalText: null,
            Diagnostic: diagnostic,
            TimedOut: false,
            PublicEvents: [],
            CapturePosterior());

    internal async Task<ProductTurnResult> TurnAsync(
        string text,
        TimeSpan timeout,
        CancellationToken cancellationToken)
    {
        int startEvents = _sink.Snapshot().Count;
        int startMessages = _viewModel.Messages.Count;
        string body = new JsonObject { ["text"] = text }.ToJsonString();
        Task<FieldHttpResponse> admissionTask = _channel.HandleHttpAsync(
            "POST",
            "/turn",
            body);

        using var timeoutSource = CancellationTokenSource.CreateLinkedTokenSource(
            cancellationToken);
        timeoutSource.CancelAfter(timeout);
        FieldHttpResponse? admission = null;
        try
        {
            while (!timeoutSource.Token.IsCancellationRequested)
            {
                if (admission is null && admissionTask.IsCompleted)
                {
                    admission = await admissionTask.ConfigureAwait(true);
                    if (admission.Status != 200 || !IsAccepted(admission))
                    {
                        return new ProductTurnResult(
                            admission,
                            ProductTurnTerminal.Rejected,
                            FinalText: null,
                            Diagnostic: ReadError(admission) ?? "rejected",
                            TimedOut: false,
                            EventsSince(startEvents),
                            CapturePosterior());
                    }
                }

                if (admission is not null)
                {
                    ProductTurnResult? settled = TryClassify(
                        admission,
                        startEvents,
                        startMessages,
                        timedOut: false);
                    if (settled is not null)
                    {
                        return settled;
                    }
                }

                await Task.Delay(50, timeoutSource.Token).ConfigureAwait(true);
            }
        }
        catch (OperationCanceledException) when (
            timeoutSource.IsCancellationRequested
            && !cancellationToken.IsCancellationRequested)
        {
            // Diagnostic timeout: do not cancel the in-flight turn or repair
            // the session. The HTTP task may still be running.
        }

        FieldHttpResponse observed = admission
            ?? FieldHttpResponse.Json(
                new JsonObject
                {
                    ["ok"] = true,
                    ["status"] = "accepted",
                    ["pending"] = true,
                });
        ProductTurnResult? timedOut = TryClassify(
            observed,
            startEvents,
            startMessages,
            timedOut: true);
        if (timedOut is not null)
        {
            return timedOut;
        }

        string? published = LastPublishedBaxyText(EventsSince(startEvents));
        if (!string.IsNullOrWhiteSpace(published))
        {
            return new ProductTurnResult(
                observed,
                ProductTurnTerminal.PublishedFinal,
                published,
                Diagnostic: "timeout_after_published_final",
                TimedOut: true,
                EventsSince(startEvents),
                CapturePosterior());
        }

        return new ProductTurnResult(
            observed,
            ProductTurnTerminal.Silence,
            FinalText: null,
            Diagnostic: "timeout_without_visible_final",
            TimedOut: true,
            EventsSince(startEvents),
            CapturePosterior());
    }

    internal ProductPosteriorState CapturePosterior() =>
        new(
            _viewModel.Messages.Count,
            _viewModel.Messages.Count(static message => message.IsUser),
            _viewModel.IsBusy,
            _viewModel.IsInputEnabled,
            _viewModel.HasPendingPlan,
            _viewModel.PendingModelMessageCount,
            _viewModel.LastMessageCompositionFailure,
            _viewModel.HasCompositionError,
            _viewModel.StatusDescription,
            _viewModel.LastMindReplyRejection);

    private ProductTurnResult? TryClassify(
        FieldHttpResponse admission,
        int startEvents,
        int startMessages,
        bool timedOut)
    {
        IReadOnlyList<JsonObject> events = EventsSince(startEvents);
        string? finalText = LastPublishedBaxyText(events);
        bool discard = events.Any(static item =>
            (string?)item["type"] == "publication_discard");
        bool publicationError = events.Any(static item =>
            (string?)item["type"] == "publication_error");
        bool busy = _viewModel.IsBusy || _viewModel.PendingModelMessageCount > 0;
        string? compositionFailure = _viewModel.LastMessageCompositionFailure;
        int newBaxyMessages = _viewModel.Messages
            .Skip(startMessages)
            .Count(static message => !message.IsUser);

        bool exhaustedThisTurn = events.Any(static item =>
            (string?)item["type"] == "composition_failed");
        if (!busy && exhaustedThisTurn)
        {
            return new ProductTurnResult(
                admission,
                ProductTurnTerminal.CompositionFailed,
                LastSystemCompositionText(events) ?? compositionFailure,
                compositionFailure,
                TimedOut: false,
                events,
                CapturePosterior());
        }

        if (finalText is not null && (!busy || timedOut))
        {
            return new ProductTurnResult(
                admission,
                ProductTurnTerminal.PublishedFinal,
                finalText,
                Diagnostic: timedOut && busy ? "timeout_after_published_final" : null,
                TimedOut: timedOut,
                events,
                CapturePosterior());
        }

        if (discard)
        {
            return new ProductTurnResult(
                admission,
                ProductTurnTerminal.Filtered,
                FinalText: null,
                Diagnostic: "publication_discard:filtered",
                TimedOut: false,
                events,
                CapturePosterior());
        }

        // Una composición encolada sigue siendo este turno: cerrarlo aquí lo
        // deja mudo y publica la respuesta después, fuera de su pregunta.
        if (_viewModel.PendingModelMessageCount > 0 && !timedOut)
        {
            return null;
        }

        if (!busy && !string.IsNullOrWhiteSpace(compositionFailure) && newBaxyMessages == 0)
        {
            return new ProductTurnResult(
                admission,
                ProductTurnTerminal.Filtered,
                FinalText: null,
                Diagnostic: compositionFailure,
                TimedOut: false,
                events,
                CapturePosterior());
        }

        if (publicationError && !busy)
        {
            return new ProductTurnResult(
                admission,
                ProductTurnTerminal.AcceptedWithoutFinal,
                FinalText: null,
                Diagnostic: "publication_error:final_not_delivered",
                TimedOut: false,
                events,
                CapturePosterior());
        }

        if (timedOut && finalText is null)
        {
            bool anyProgress = events.Any(static item =>
                (string?)item["type"] == FieldBridgeContract.ProgressPayloadType);
            ProductTurnTerminal terminal = anyProgress && !busy
                ? ProductTurnTerminal.AcceptedWithoutFinal
                : ProductTurnTerminal.Silence;
            return new ProductTurnResult(
                admission,
                terminal,
                FinalText: null,
                Diagnostic: terminal == ProductTurnTerminal.Silence
                    ? "timeout_without_visible_final"
                    : "timeout_after_progress_without_final",
                TimedOut: true,
                events,
                CapturePosterior());
        }

        if (!busy && finalText is null)
        {
            return new ProductTurnResult(
                admission,
                ProductTurnTerminal.AcceptedWithoutFinal,
                FinalText: null,
                Diagnostic: compositionFailure ?? "accepted_without_published_final",
                TimedOut: false,
                events,
                CapturePosterior());
        }

        return null;
    }

    private JsonObject[] EventsSince(int start)
    {
        IReadOnlyList<JsonObject> all = _sink.Snapshot();
        return start >= all.Count ? [] : [.. all.Skip(start)];
    }

    private static bool IsAccepted(FieldHttpResponse admission)
    {
        try
        {
            if (JsonNode.Parse(admission.Body) is not JsonObject node)
            {
                return false;
            }

            return node["status"]?.GetValue<string>() == "accepted"
                || node["ok"]?.GetValue<bool>() == true;
        }
        catch (System.Text.Json.JsonException)
        {
            return false;
        }
    }

    private static string? ReadError(FieldHttpResponse admission)
    {
        try
        {
            return JsonNode.Parse(admission.Body)?["error"]?.GetValue<string>();
        }
        catch (System.Text.Json.JsonException)
        {
            return null;
        }
    }

    internal static string? LastPublishedBaxyText(IReadOnlyList<JsonObject> events)
    {
        string? text = null;
        foreach (JsonObject item in events)
        {
            if ((string?)item["type"] != "activity")
            {
                continue;
            }

            JsonObject? entry = item["entry"] as JsonObject;
            if ((string?)entry?["src"] == "BAXY")
            {
                text = (string?)entry?["msg"];
            }
        }

        return string.IsNullOrWhiteSpace(text) ? null : text;
    }

    private static string? LastSystemCompositionText(IReadOnlyList<JsonObject> events)
    {
        string? text = null;
        foreach (JsonObject item in events)
        {
            if ((string?)item["type"] != "activity")
            {
                continue;
            }

            JsonObject? entry = item["entry"] as JsonObject;
            if ((string?)entry?["src"] == "SYSTEM"
                && (string?)entry?["msg"] is { Length: > 0 } msg
                && msg.StartsWith("composition_failed", StringComparison.Ordinal))
            {
                text = msg;
            }
        }

        return string.IsNullOrWhiteSpace(text) ? null : text;
    }

    public async ValueTask DisposeAsync()
    {
        await _channel.DisposeAsync();
        await _telemetry.DisposeAsync();
        if (_ownsViewModel)
        {
            await _viewModel.DisposeAsync();
        }
    }
}

/// <summary>
/// UI adapter over the same <see cref="FieldProductChannel"/>. Origin
/// restrictions stay here: untrusted document sources never reach admission.
/// </summary>
internal sealed class FieldUiProductAdapter
{
    private readonly FieldProductChannel _channel;

    internal FieldUiProductAdapter(FieldProductChannel channel)
    {
        _channel = channel ?? throw new ArgumentNullException(nameof(channel));
    }

    internal FieldProductChannel Channel => _channel;

    internal static bool AcceptsDocumentSource(string source) =>
        HistoricalFieldOriginPolicy.IsTrustedDocumentSource(source);

    internal Task<FieldHttpResponse?> TryHandleFromDocumentAsync(
        string source,
        string method,
        string path,
        string? body)
    {
        if (!AcceptsDocumentSource(source))
        {
            return Task.FromResult<FieldHttpResponse?>(null);
        }

        return HandleTrustedAsync(method, path, body);
    }

    internal async Task<FieldHttpResponse?> HandleTrustedAsync(
        string method,
        string path,
        string? body)
    {
        FieldHttpResponse response = await _channel
            .HandleHttpAsync(method, path, body)
            .ConfigureAwait(true);
        return response;
    }
}
