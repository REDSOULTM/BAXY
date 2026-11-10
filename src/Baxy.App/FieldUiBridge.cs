using System.IO;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Windows;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.Wpf;

namespace Baxy.App;

internal sealed record FieldHttpResponse(
    int Status,
    string Body,
    IReadOnlyDictionary<string, string> Headers)
{
    internal static FieldHttpResponse Json(JsonNode body, int status = 200) =>
        new(
            status,
            body.ToJsonString(),
            new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
            {
                ["Content-Type"] = "application/json; charset=utf-8",
                ["Cache-Control"] = "no-store",
            });

    internal static FieldHttpResponse Empty(int status = 204) =>
        new(status, string.Empty, new Dictionary<string, string>());
}

internal sealed record FieldModelIdentity(
    string Alias,
    string FileName,
    string Family,
    string Parameters);

internal sealed class FieldUiBridge : IAsyncDisposable, IFieldEventSink
{
    internal const string Channel = "baxy.field.v1";
    internal const string TraceMarkKind = "trace_mark";
    private const int MaximumBridgeMessageCharacters = 1_048_576;

    private readonly Window _window;
    private WebView2 _webView;
    private readonly FieldTelemetrySampler _telemetry;
    private readonly FieldProductChannel _channel;
    private readonly CancellationToken _lifetimeCancellation;
    private readonly HashSet<string> _sockets = new(StringComparer.Ordinal);
    private bool _disposed;

    internal FieldUiBridge(
        Window window,
        WebView2 webView,
        MainWindowViewModel viewModel,
        FieldTelemetrySampler telemetry,
        CancellationToken lifetimeCancellation)
    {
        _window = window ?? throw new ArgumentNullException(nameof(window));
        _webView = webView ?? throw new ArgumentNullException(nameof(webView));
        ArgumentNullException.ThrowIfNull(viewModel);
        _telemetry = telemetry ?? throw new ArgumentNullException(nameof(telemetry));
        _lifetimeCancellation = lifetimeCancellation;
        // Design v4: the view scales itself (720p to 8K, its own accessible sizes); the host keeps the zoom at 1.
        _channel = new FieldProductChannel(viewModel, this, telemetry, lifetimeCancellation);
        _webView.WebMessageReceived += OnWebMessageReceived;
        _webView.NavigationStarting += OnNavigationStarting;
    }

    /// <summary>
    /// Auditoría de la App (2026-10-23): the document the sockets belong to is leaving (the loading page, a return to
    /// the view, a reload). It never says socket_close as it goes, so every later event was posted once more per socket
    /// of every document the view had had; the next one opens its own.
    /// </summary>
    internal void DocumentLeaving() => _sockets.Clear();

    /// <summary>The event sockets of the document shown now.</summary>
    internal int OpenSockets => _sockets.Count;

    private void OnNavigationStarting(object? sender, CoreWebView2NavigationStartingEventArgs eventArgs) =>
        DocumentLeaving();

    /// <summary>Every event the view is sent, as it is sent (the overlay reads the same; OverlayPresenter).</summary>
    internal event Action<JsonObject>? Published;

    /// <summary>Settings › Personalización «Probar»: the overlay shows an example.</summary>
    internal event Action? OverlayPreviewRequested
    {
        add => _channel.OverlayPreviewRequested += value;
        remove => _channel.OverlayPreviewRequested -= value;
    }

    /// <summary>The person's answer to a card, from the overlay: null when taken, else why not.</summary>
    internal Task<string?> AnswerCardAsync(bool approve, string card) =>
        _channel.AnswerCardAsync(approve, card, System.Diagnostics.Stopwatch.GetTimestamp());

    bool IFieldEventSink.Publish(JsonObject eventData)
    {
        Published?.Invoke(eventData);
        return PostEvent(eventData);
    }

    private async void OnWebMessageReceived(
        object? sender,
        CoreWebView2WebMessageReceivedEventArgs eventArgs)
    {
        if (_disposed
            || !HistoricalFieldOriginPolicy.IsTrustedDocumentSource(eventArgs.Source))
        {
            return;
        }

        string raw = eventArgs.WebMessageAsJson;
        if (raw.Length > MaximumBridgeMessageCharacters)
        {
            return;
        }

        JsonObject? message;
        try
        {
            message = JsonNode.Parse(raw) as JsonObject;
        }
        catch (JsonException)
        {
            return;
        }

        if (message is null
            || (string?)message["channel"] != Channel
            || message["kind"] is not JsonValue kindValue
            || !kindValue.TryGetValue(out string? kind)
            || string.IsNullOrWhiteSpace(kind))
        {
            return;
        }

        string? id = (string?)message["id"];
        string? failed = await AnswerAsync(
            async () =>
            {
                switch (kind)
                {
                    case "http":
                        FieldHttpResponse response = await HandleHttpAsync(message)
                            .ConfigureAwait(true);
                        Reply(id, HttpValue(response));
                        break;
                    case "socket_open":
                        OpenSocket(message);
                        break;
                    case "socket_close":
                        CloseSocket(message);
                        break;
                    case "window_command":
                        Reply(id, HandleWindowCommand((string?)message["command"]));
                        break;
                    case TraceMarkKind:
                        RecordDocumentMark(message);
                        break;
                }
            },
            () => _lifetimeCancellation.IsCancellationRequested,
            static failure => UnhandledFailures.Record("view", failure)).ConfigureAwait(true);
        if (failed is not null)
        {
            ReplyError(id, failed);
        }
    }

    /// <summary>
    /// Runs the handling of one message of the view; the error to answer it with when it threw, or null. APP1 (BRG-a,
    /// review of the App 2026-11-09): only a closed list of exceptions was answered, and any other (an
    /// HttpRequestException of a search, a TimeoutException, a call cancelled by its own time) left the view's request
    /// with no answer for the 30 s the bridge gives one, said then as «no answer» of a host that had failed at once.
    /// Whatever the handling throws is answered now; what the list did not expect is kept (UnhandledFailures), with no
    /// message of it going to the view.
    /// </summary>
    internal static async Task<string?> AnswerAsync(Func<Task> handle, Func<bool> closing, Action<Exception> keep)
    {
        try
        {
            await handle().ConfigureAwait(true);
            return null;
        }
        catch (OperationCanceledException) when (closing())
        {
            return "BAXY is closing";
        }
        // Every request of the view gets its answer, whatever handling it threw.
        catch (Exception exception)
        {
            if (!IsExpectedBridgeFailure(exception))
            {
                keep(exception);
            }

            return "The local BAXY bridge could not complete the request.";
        }
    }

    private Task<FieldHttpResponse> HandleHttpAsync(JsonObject message)
    {
        string method = ((string?)message["method"] ?? "GET").ToUpperInvariant();
        string path = (string?)message["path"] ?? "/";
        string? body = (string?)message["body"];
        return _channel.HandleHttpAsync(method, path, body);
    }


    /// <summary>
    /// Registra una marca temporal emitida por el documento. Sólo se aceptan
    /// etapas del vocabulario cerrado y sólo cuando el registro está activo:
    /// la vista no puede escribir texto libre ni inventar etapas, y sin
    /// instrumentación esta rama no hace nada.
    /// </summary>
    private static void RecordDocumentMark(JsonObject message)
    {
        string stage = (string?)message["stage"] ?? string.Empty;
        if (Array.IndexOf(ShellTraceStages.DocumentReportable, stage) < 0)
        {
            return;
        }

        ShellTraceSink.Record(
            ShellTraceScopes.Turn,
            ShellTrace.SanitizeId((string?)message["id"]),
            stage);
    }

    private void OpenSocket(JsonObject message)
    {
        string socketId = (string?)message["socketId"] ?? string.Empty;
        string url = (string?)message["url"] ?? string.Empty;
        if (socketId.Length is < 1 or > 128
            || !HistoricalFieldOriginPolicy.IsTrustedEventSocket(url))
        {
            return;
        }

        _sockets.Add(socketId);
        PostSocket(socketId, "open");
        // Un socket que se reconecta recibe el estado actual, nunca fragmentos
        // ya publicados: la indicación se recalcula, no se reproduce.
        foreach (JsonObject bootstrap in _channel.CreateSocketBootstrap())
        {
            PostSocketMessage(socketId, bootstrap);
        }
    }

    private void CloseSocket(JsonObject message)
    {
        string socketId = (string?)message["socketId"] ?? string.Empty;
        if (_sockets.Remove(socketId))
        {
            PostSocket(socketId, "close", code: 1000, reason: "closed");
        }
    }

    private JsonValue? HandleWindowCommand(string? command)
    {
        switch (command)
        {
            case "minimize":
                _window.WindowState = WindowState.Minimized;
                return JsonValue.Create(true);
            case "toggle_maximize":
                _window.WindowState = _window.WindowState == WindowState.Maximized
                    ? WindowState.Normal
                    : WindowState.Maximized;
                return JsonValue.Create(_window.WindowState == WindowState.Maximized);
            case "is_maximized":
                return JsonValue.Create(_window.WindowState == WindowState.Maximized);
            case "close":
                _window.Close();
                return JsonValue.Create(true);
            case "exit" when _window is MainWindow main:
                // Uso 85: «Salir» on a breakdown leaves BAXY as the tray's Exit does, whatever «Al cerrar la ventana» says.
                main.Exit("view");
                return JsonValue.Create(true);
            default:
                return JsonValue.Create(false);
        }
    }
    private static JsonObject HttpValue(FieldHttpResponse response)
    {
        var headers = new JsonObject();
        foreach ((string key, string value) in response.Headers)
        {
            headers[key] = value;
        }

        return new JsonObject
        {
            ["status"] = response.Status,
            ["body"] = response.Body,
            ["headers"] = headers,
        };
    }

    private void Reply(string? id, JsonNode? value)
    {
        if (string.IsNullOrWhiteSpace(id))
        {
            return;
        }

        PostEnvelope(new JsonObject
        {
            ["channel"] = Channel,
            ["kind"] = "reply",
            ["id"] = id,
            ["ok"] = true,
            ["value"] = value?.DeepClone(),
        });
    }

    private void ReplyError(string? id, string error)
    {
        if (string.IsNullOrWhiteSpace(id))
        {
            return;
        }

        PostEnvelope(new JsonObject
        {
            ["channel"] = Channel,
            ["kind"] = "reply",
            ["id"] = id,
            ["ok"] = false,
            ["error"] = error,
        });
    }

    private bool PostEvent(JsonObject eventData)
    {
        bool delivered = false;
        foreach (string socketId in _sockets.ToArray())
        {
            delivered |= PostSocketMessage(socketId, eventData);
        }

        return delivered;
    }

    private bool PostSocketMessage(string socketId, JsonObject eventData) =>
        PostSocket(socketId, "message", data: eventData.ToJsonString());

    private bool PostSocket(
        string socketId,
        string eventName,
        string? data = null,
        int? code = null,
        string? reason = null)
    {
        return PostEnvelope(new JsonObject
        {
            ["channel"] = Channel,
            ["kind"] = "socket_event",
            ["socketId"] = socketId,
            ["event"] = eventName,
            ["data"] = data,
            ["code"] = code,
            ["reason"] = reason,
        });
    }

    /// <summary>
    /// uso-116: the view was created anew (its browser process died). The channel stays, with the conversation it shows;
    /// what the old view's sockets were is gone with it, and the new view opens its own.
    /// </summary>
    internal void Rebind(WebView2 webView)
    {
        ArgumentNullException.ThrowIfNull(webView);
        _webView.WebMessageReceived -= OnWebMessageReceived;
        _webView.NavigationStarting -= OnNavigationStarting;
        _sockets.Clear();
        _webView = webView;
        _webView.WebMessageReceived += OnWebMessageReceived;
        _webView.NavigationStarting += OnNavigationStarting;
    }

    private bool PostEnvelope(JsonObject envelope)
    {
        if (_disposed)
        {
            return false;
        }

        try
        {
            // The getter itself throws once the control closed with its browser process (uso-116: unhandled, twice per kill).
            if (_webView.CoreWebView2 is not { } core)
            {
                return false;
            }

            core.PostWebMessageAsJson(envelope.ToJsonString());
            return true;
        }
        catch (Exception exception) when (exception is InvalidOperationException
            or System.Runtime.InteropServices.COMException)
        {
            // Navigation or teardown raced the event, or the view's process went away; the next state replay wins.
            return false;
        }
    }

    private static bool IsExpectedBridgeFailure(Exception exception) => exception is
        JsonException
        or IOException
        or InvalidOperationException
        or ArgumentException
        or UnauthorizedAccessException;

    public async ValueTask DisposeAsync()
    {
        if (_disposed)
        {
            return;
        }

        _disposed = true;
        _webView.WebMessageReceived -= OnWebMessageReceived;
        _webView.NavigationStarting -= OnNavigationStarting;
        foreach (string socketId in _sockets.ToArray())
        {
            PostSocket(socketId, "close", code: 1001, reason: "BAXY closing");
        }

        _sockets.Clear();
        await _channel.DisposeAsync();
        await _telemetry.DisposeAsync();
    }
}
