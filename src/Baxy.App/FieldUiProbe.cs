using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Runtime.InteropServices;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Interop;
using Microsoft.Web.WebView2.Core;

namespace Baxy.App;

/// <summary>
/// Escribe en el compositor real de la ventana y lee lo que la ventana muestra.
///
/// El conductor recorre la misma tubería pública pero sin ventana, así que no
/// acredita que la persona vea y entienda la respuesta. Sin esta pieza, la
/// única prueba de interfaz posible era el título de la ventana. La sonda no
/// abre ninguna vía nueva al producto: teclea en el mismo `input` que usa una
/// persona, envía el mismo formulario, pide una sesión nueva por la misma ruta
/// que el botón «+ new» y lee el mismo DOM.
///
/// Sólo se activa con <c>--ui-probe</c> en un arranque de desarrollo.
/// </summary>
internal static class FieldUiProbe
{
    internal const string TurnsArgument = "--ui-probe";
    internal const string CaptureArgument = "--ui-capture";
    internal const string TurnTimeoutArgument = "--ui-turn-timeout-ms";
    internal const string StableArgument = "--ui-stable-ms";

    internal static readonly TimeSpan DefaultTurnTimeout = TimeSpan.FromMinutes(4);
    internal static readonly TimeSpan DefaultStableWindow = TimeSpan.FromMilliseconds(2500);
    private static readonly TimeSpan PollInterval = TimeSpan.FromMilliseconds(250);

    /// <summary>Cuánto se espera a que el campo vuelva a ser legible antes de un turno.</summary>
    private static readonly TimeSpan SurfaceBudget = TimeSpan.FromSeconds(15);

    /// <summary>Escribe el texto en el input de React y envía el formulario.</summary>
    private const string SendScript = """
        (function (text) {
          const input = document.querySelector('input[aria-label="message input"]');
          if (!input) { return 'no_input'; }
          if (input.disabled) { return 'input_disabled'; }
          const setter = Object.getOwnPropertyDescriptor(
            window.HTMLInputElement.prototype, 'value').set;
          setter.call(input, text);
          input.dispatchEvent(new Event('input', { bubbles: true }));
          const form = input.closest('form');
          if (!form) { return 'no_form'; }
          form.requestSubmit
            ? form.requestSubmit()
            : form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
          return 'sent';
        })
        """;

    /// <summary>Lee las líneas que la ventana está mostrando ahora mismo.</summary>
    private const string ReadScript = """
        (function () {
          const rows = Array.from(document.querySelectorAll('.activity-scroll .act'));
          return JSON.stringify(rows.map(function (row) {
            const src = row.querySelector('.src');
            const msg = row.querySelector('.msg');
            const ts = row.querySelector('.ts');
            return {
              src: src ? src.textContent : '',
              msg: msg ? msg.textContent : '',
              ts: ts ? ts.textContent : ''
            };
          }));
        })()
        """;

    /// <summary>
    /// Lo que decide si un turno terminó: el input existe y está habilitado, el
    /// borrador quedó vacío (el compositor lo vacía cuando <c>/turn</c> vuelve),
    /// no hay etapa en curso, cuántas filas hay y cuál va en cabeza. La lista se
    /// pinta con la más nueva primero y se recorta a un tope: al llegar a él el
    /// recuento ya no cambia y sólo la cabeza dice que llegó una fila.
    /// </summary>
    private const string SurfaceScript = """
        (function () {
          const input = document.querySelector('input[aria-label="message input"]');
          const progress = document.querySelector('.turn-progress');
          const rows = document.querySelectorAll('.activity-scroll .act');
          return JSON.stringify({
            input: !!input,
            enabled: !!input && !input.disabled,
            draft: input ? input.value.length : 0,
            progress: progress ? (progress.textContent || '').trim().length : 0,
            rows: rows.length,
            head: rows.length > 0 ? (rows[0].textContent || '') : ''
          });
        })()
        """;

    /// <summary>
    /// La misma petición que el botón «+ new» de la ventana. El resultado queda
    /// en una variable de la página porque <c>ExecuteScriptAsync</c> no espera
    /// promesas.
    /// </summary>
    private const string NewSessionScript = """
        (function () {
          window.__baxyProbeSession = null;
          fetch('/sessions/new', { method: 'POST' })
            .then(function (r) { window.__baxyProbeSession = String(r.status); })
            .catch(function () { window.__baxyProbeSession = 'unreachable'; });
          return 'requested';
        })()
        """;

    private const string NewSessionResultScript =
        "(function(){return window.__baxyProbeSession || '';})()";

    internal static bool IsRequested(IReadOnlyList<string> arguments)
    {
        ArgumentNullException.ThrowIfNull(arguments);
        foreach (string argument in arguments)
        {
            if (argument.StartsWith(TurnsArgument, StringComparison.OrdinalIgnoreCase))
            {
                return true;
            }
        }

        return false;
    }

    internal static string? ValueOf(IReadOnlyList<string> arguments, string name)
    {
        ArgumentNullException.ThrowIfNull(arguments);
        for (int index = 0; index < arguments.Count; index++)
        {
            string argument = arguments[index];
            if (argument.StartsWith(name + "=", StringComparison.OrdinalIgnoreCase))
            {
                return argument[(name.Length + 1)..];
            }

            if (string.Equals(argument, name, StringComparison.OrdinalIgnoreCase)
                && index + 1 < arguments.Count)
            {
                return arguments[index + 1];
            }
        }

        return null;
    }

    /// <summary>Milisegundos de un argumento; ausente, inválido o no positivo da el valor por defecto.</summary>
    internal static TimeSpan MillisecondsOf(
        IReadOnlyList<string> arguments,
        string name,
        TimeSpan fallback)
    {
        string? raw = ValueOf(arguments, name);
        return int.TryParse(raw, NumberStyles.Integer, CultureInfo.InvariantCulture, out int value)
            && value > 0
            ? TimeSpan.FromMilliseconds(value)
            : fallback;
    }

    /// <summary>
    /// Una línea del archivo de turnos. <c>{"text":"…"}</c> es un turno;
    /// <c>{"cmd":"session.new"}</c> abre una sesión nueva. Los campos
    /// <c>conversation</c>, <c>turn</c> e <c>id</c> se copian a la captura para
    /// unir cada fila con su tanda.
    /// </summary>
    internal static ProbeCommand ParseCommand(string? line)
    {
        if (string.IsNullOrWhiteSpace(line))
        {
            return ProbeCommand.Skip;
        }

        JsonObject? command;
        try
        {
            command = JsonNode.Parse(line) as JsonObject;
        }
        catch (JsonException)
        {
            return new ProbeCommand(ProbeCommandKind.Invalid, string.Empty, null, "invalid_json");
        }

        if (command is null)
        {
            return new ProbeCommand(ProbeCommandKind.Invalid, string.Empty, null, "not_an_object");
        }

        JsonObject tags = new();
        foreach (string key in new[] { "conversation", "turn", "id" })
        {
            if (command[key] is JsonNode value)
            {
                tags[key] = value.DeepClone();
            }
        }

        JsonObject? echoed = tags.Count > 0 ? tags : null;
        string? cmd = command["cmd"] is JsonValue cmdValue
            && cmdValue.TryGetValue(out string? cmdText) ? cmdText : null;
        if (cmd is not null)
        {
            return cmd is "session.new" or "new-session" or "sessions/new"
                ? new ProbeCommand(ProbeCommandKind.NewSession, string.Empty, echoed, null)
                : new ProbeCommand(ProbeCommandKind.Invalid, string.Empty, echoed, "unknown_cmd");
        }

        string text = command["text"] is JsonValue textValue
            && textValue.TryGetValue(out string? textText) ? textText ?? string.Empty : string.Empty;
        return text.Trim().Length == 0
            ? ProbeCommand.Skip
            : new ProbeCommand(ProbeCommandKind.Turn, text, echoed, null);
    }

    internal static async Task RunAsync(
        CoreWebView2 core,
        IReadOnlyList<string> arguments,
        IFieldProbeWindow window,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(core);
        ArgumentNullException.ThrowIfNull(arguments);
        ArgumentNullException.ThrowIfNull(window);
        string? turnsPath = ValueOf(arguments, TurnsArgument);
        if (string.IsNullOrWhiteSpace(turnsPath) || !File.Exists(turnsPath))
        {
            return;
        }

        TimeSpan turnTimeout = MillisecondsOf(arguments, TurnTimeoutArgument, DefaultTurnTimeout);
        TimeSpan stableWindow = MillisecondsOf(arguments, StableArgument, DefaultStableWindow);
        string capturePath = Path.GetFullPath(ValueOf(arguments, CaptureArgument)
            ?? Path.Combine(Path.GetDirectoryName(turnsPath)!, "ui-probe.jsonl"));
        Directory.CreateDirectory(Path.GetDirectoryName(capturePath)!);
        await using var writer = new StreamWriter(capturePath, append: false);

        await WriteAsync(
            writer,
            new JsonObject
            {
                ["type"] = "meta",
                ["process"] = "Baxy.exe",
                ["pid"] = Environment.ProcessId,
                ["entry"] = "Baxy.exe " + TurnsArgument,
                ["turns_file"] = Path.GetFullPath(turnsPath),
                ["profile"] = Environment.GetEnvironmentVariable("BAXY_DATA_DIR"),
                ["started_utc"] = Utc(DateTime.UtcNow),
                ["turn_timeout_ms"] = (long)turnTimeout.TotalMilliseconds,
                ["stable_ms"] = (long)stableWindow.TotalMilliseconds,
            });

        var page = new ProbePage(
            script => core.ExecuteScriptAsync(script),
            ProbePage.DefaultScriptBudget,
            ProbePage.DefaultStallBudget);
        try
        {
            await RunTurnsAsync(
                page, window, writer, turnsPath, turnTimeout, stableWindow, cancellationToken);
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            // La ventana se cerró de verdad durante la tanda: queda dicho en la
            // captura en vez de una tanda que parece cortada sin motivo.
            await WriteAsync(writer, Terminal("cancelled", "window_closed"));
        }
        catch (Exception exception) when (exception is InvalidOperationException
            or COMException or JsonException or IOException)
        {
            // Cualquier fallo de la sonda acaba en un cierre legible; quien la
            // llama apaga la aplicación igualmente y el lanzador no se cuelga.
            await WriteAsync(
                writer,
                Terminal("error", exception.GetType().Name + ": " + exception.Message));
        }
    }

    private static async Task RunTurnsAsync(
        ProbePage page,
        IFieldProbeWindow window,
        StreamWriter writer,
        string turnsPath,
        TimeSpan turnTimeout,
        TimeSpan stableWindow,
        CancellationToken cancellationToken)
    {
        // La ventana habilita el input al terminar el arranque. Sin esa espera
        // se estaría midiendo el arranque, no la conversación.
        if (!await WaitForInputAsync(page, window, TimeSpan.FromMinutes(3), cancellationToken))
        {
            await WriteAsync(writer, Terminal(
                "blocked_environment",
                page.Unresponsive ? PageUnresponsive : "input_never_enabled"));
            return;
        }

        int index = 0;
        // Si el turno o la sesión anterior no se asentó, el siguiente espera a
        // una superficie ociosa y estable: una respuesta tardía no se cuela.
        bool previousSettled = true;
        // Una conversación cuya sesión nueva falló correría sobre el contexto
        // de la anterior: sus turnos no se envían hasta la siguiente sesión.
        string? sessionFailure = null;
        foreach (string line in await File.ReadAllLinesAsync(turnsPath, cancellationToken))
        {
            ProbeCommand command = ParseCommand(line);
            switch (command.Kind)
            {
                case ProbeCommandKind.Skip:
                    continue;
                case ProbeCommandKind.Invalid:
                    await WriteAsync(writer, Tagged(command, new JsonObject
                    {
                        ["type"] = "ui.invalid",
                        ["diagnostic"] = command.Diagnostic,
                        ["line"] = line,
                    }));
                    continue;
                case ProbeCommandKind.NewSession:
                    JsonObject session = await NewSessionAsync(
                        page, window, turnTimeout, stableWindow, cancellationToken);
                    string status = (string?)session["status"] ?? string.Empty;
                    sessionFailure = IsSessionReset(status) ? null : status;
                    previousSettled = (bool?)session["settled"] ?? false;
                    await WriteAsync(writer, Tagged(command, session));
                    continue;
                default:
                    index++;
                    JsonObject turn = sessionFailure is null
                        ? await TurnAsync(
                            page, window, command.Text, index, previousSettled,
                            turnTimeout, stableWindow, cancellationToken)
                        : Unsent(command.Text, index, SessionNotReset, sessionFailure);
                    if ((string?)turn["send"] == "sent")
                    {
                        previousSettled = (bool?)turn["settled"] ?? false;
                    }

                    await WriteAsync(writer, Tagged(command, turn));
                    continue;
            }
        }

        await WriteAsync(writer, new JsonObject
        {
            ["type"] = "terminal",
            ["kind"] = "done",
            ["finished_utc"] = Utc(DateTime.UtcNow),
        });
    }

    internal const string SessionNotReset = "session_not_reset";

    /// <summary>La página no devolvió una lectura en <see cref="ProbePage.DefaultStallBudget"/>.</summary>
    internal const string PageUnresponsive = "page_unresponsive";

    /// <summary>
    /// Marca la línea en la que la página dejó una lectura sin volver (o seguía
    /// colgada): la tanda sigue con la siguiente y el informe dice cuál fue.
    /// </summary>
    private static JsonObject MarkHung(JsonObject record, ProbePage page, int hangsBefore)
    {
        int hung = page.Hangs - hangsBefore;
        if (hung > 0 || page.Unresponsive)
        {
            record["hung"] = true;
            record["hung_reads"] = hung;
        }

        return record;
    }

    /// <summary>Sólo un 2xx de <c>/sessions/new</c> vació la sesión anterior.</summary>
    internal static bool IsSessionReset(string? status) =>
        status is { Length: 3 } && status[0] == '2' && char.IsAsciiDigit(status[1])
        && char.IsAsciiDigit(status[2]);

    private static JsonObject Unsent(string text, int index, string send, string? diagnostic) =>
        new()
        {
            ["type"] = "ui.turn",
            ["index"] = index,
            ["text"] = text,
            ["send"] = send,
            ["diagnostic"] = diagnostic,
            ["published"] = false,
            ["settled"] = false,
            ["new_rows"] = new JsonArray(),
        };

    private static async Task<JsonObject> TurnAsync(
        ProbePage page,
        IFieldProbeWindow window,
        string text,
        int index,
        bool previousSettled,
        TimeSpan turnTimeout,
        TimeSpan stableWindow,
        CancellationToken cancellationToken)
    {
        // Antes de teclear: una superficie legible y ociosa. Recién restaurada
        // la ventana, la primera lectura puede venir vacía (campo suspendido) y
        // tomarla por «cero filas» atribuiría toda la sesión a este turno.
        Stopwatch waited = Stopwatch.StartNew();
        int hangsBefore = page.Hangs;
        var gate = new SendGate(stableWindow, SurfaceBudget, turnTimeout, requireStable: !previousSettled);
        bool restored = false;
        SendGateState state;
        ProbeSurface ready;
        while (true)
        {
            cancellationToken.ThrowIfCancellationRequested();
            restored |= RestoreIfSuspended(window);
            ready = await ReadSurfaceAsync(page, cancellationToken);
            state = gate.Observe(waited.Elapsed, ready);
            if (state != SendGateState.Wait || page.Unresponsive)
            {
                break;
            }

            await Task.Delay(PollInterval, cancellationToken);
        }

        JsonArray? before = state == SendGateState.Ready ? await ReadRowsAsync(page) : null;
        if (before is null)
        {
            JsonObject unsent = Unsent(
                text,
                index,
                page.Unresponsive ? PageUnresponsive
                    : state == SendGateState.NotIdle ? "not_idle" : "no_surface",
                null);
            unsent["waited_ms"] = waited.ElapsedMilliseconds;
            unsent["window_restored"] = restored;
            return MarkHung(unsent, page, hangsBefore);
        }

        IReadOnlyList<ProbeRow> beforeRows = ProbeRow.ListOf(before);
        DateTime sentAt = DateTime.UtcNow;
        Stopwatch clock = Stopwatch.StartNew();
        string sent = (await page.RunAsync(
            $"({SendScript})({JsonSerializer.Serialize(text)})"))?.Trim('"') ?? "script_failed";
        var tracker = new TurnSettleTracker(ready.Rows, stableWindow, ready.Head);
        bool settled = false;
        if (sent == "sent")
        {
            (settled, bool restoredDuring) = await WaitForSettleAsync(
                page, window, tracker, clock, turnTimeout, cancellationToken);
            restored |= restoredDuring;
        }

        long elapsed = clock.ElapsedMilliseconds;
        JsonArray rows = await ReadRowsAsync(page) ?? new JsonArray();
        int freshCount = ProbeRow.FreshCount(beforeRows, ProbeRow.ListOf(rows));
        // La lista va con la más nueva primero: lo nuevo es el prefijo, y
        // new_rows conserva ese mismo orden que rendered.
        var fresh = new JsonArray();
        for (int row = 0; row < freshCount; row++)
        {
            fresh.Add(rows[row]?.DeepClone());
        }

        return MarkHung(new JsonObject
        {
            ["type"] = "ui.turn",
            ["index"] = index,
            ["text"] = text,
            ["send"] = sent,
            ["published"] = freshCount > 0,
            ["settled"] = settled,
            ["waited_ms"] = waited.ElapsedMilliseconds - elapsed,
            ["sent_utc"] = Utc(sentAt),
            ["settled_utc"] = Utc(sentAt.AddMilliseconds(elapsed)),
            ["elapsed_ms"] = elapsed,
            ["rows_before"] = beforeRows.Count,
            ["rows_after"] = rows.Count,
            ["window_restored"] = restored,
            ["new_rows_order"] = "newest_first",
            ["new_rows"] = fresh,
            ["rendered"] = rows,
        }, page, hangsBefore);
    }

    private static async Task<JsonObject> NewSessionAsync(
        ProbePage page,
        IFieldProbeWindow window,
        TimeSpan turnTimeout,
        TimeSpan stableWindow,
        CancellationToken cancellationToken)
    {
        bool restored = RestoreIfSuspended(window);
        int hangsBefore = page.Hangs;
        DateTime requestedAt = DateTime.UtcNow;
        Stopwatch clock = Stopwatch.StartNew();
        string status = string.Empty;
        // Un turno aún en curso responde 409: se reintenta mientras dure el tope.
        while (clock.Elapsed < turnTimeout && !page.Unresponsive)
        {
            if (await page.RunAsync(NewSessionScript) is null)
            {
                status = "script_failed";
                await Task.Delay(TimeSpan.FromSeconds(1), cancellationToken);
                restored |= RestoreIfSuspended(window);
                continue;
            }

            status = await WaitForSessionStatusAsync(page, cancellationToken);
            if (status != "409")
            {
                break;
            }

            await Task.Delay(TimeSpan.FromSeconds(1), cancellationToken);
        }

        if (page.Unresponsive && !IsSessionReset(status))
        {
            status = PageUnresponsive;
        }

        ProbeSurface after = await ReadSurfaceAsync(page, cancellationToken);
        var tracker = new TurnSettleTracker(after.Rows, stableWindow, after.Head);
        (bool settled, bool restoredDuring) = await WaitForSettleAsync(
            page, window, tracker, clock, turnTimeout, cancellationToken);
        return MarkHung(new JsonObject
        {
            ["type"] = "ui.session.new",
            ["status"] = status,
            ["reset"] = IsSessionReset(status),
            ["settled"] = settled,
            ["requested_utc"] = Utc(requestedAt),
            ["elapsed_ms"] = clock.ElapsedMilliseconds,
            ["window_restored"] = restored || restoredDuring,
            ["rendered"] = await ReadRowsAsync(page) ?? new JsonArray(),
        }, page, hangsBefore);
    }

    private static async Task<string> WaitForSessionStatusAsync(
        ProbePage page,
        CancellationToken cancellationToken)
    {
        DateTime deadline = DateTime.UtcNow + TimeSpan.FromSeconds(30);
        while (DateTime.UtcNow < deadline && !page.Unresponsive)
        {
            string status = (await page.RunAsync(NewSessionResultScript))?.Trim('"')
                ?? string.Empty;
            if (status.Length > 0)
            {
                return status;
            }

            await Task.Delay(PollInterval, cancellationToken);
        }

        return "timeout";
    }

    private static async Task<(bool Settled, bool Restored)> WaitForSettleAsync(
        ProbePage page,
        IFieldProbeWindow window,
        TurnSettleTracker tracker,
        Stopwatch clock,
        TimeSpan budget,
        CancellationToken cancellationToken)
    {
        bool restored = false;
        while (clock.Elapsed < budget && !page.Unresponsive)
        {
            cancellationToken.ThrowIfCancellationRequested();
            restored |= RestoreIfSuspended(window);
            ProbeSurface surface = await ReadSurfaceAsync(page, cancellationToken);
            if (tracker.Observe(clock.Elapsed, surface))
            {
                return (true, restored);
            }

            await Task.Delay(PollInterval, cancellationToken);
        }

        return (false, restored);
    }

    /// <summary>
    /// Una ventana minimizada u oculta (la X la oculta mientras la presencia
    /// sigue) suspende el campo (<see cref="MainWindow.ShouldKeepFieldActive"/>)
    /// y la sonda dejaría de leerlo. Sólo se toca si está suspendida, y sin
    /// activarla: el foco sigue donde la persona lo tenga.
    /// </summary>
    private static bool RestoreIfSuspended(IFieldProbeWindow window)
    {
        if (!window.IsMinimized && !window.IsHidden)
        {
            return false;
        }

        try
        {
            window.RestoreWithoutActivation();
            return true;
        }
        catch (InvalidOperationException)
        {
            // Una ventana ya cerrada no se vuelve a mostrar; la lectura
            // siguiente fallará y la tanda acaba con su cierre.
            return false;
        }
    }

    private static async Task<bool> WaitForInputAsync(
        ProbePage page,
        IFieldProbeWindow window,
        TimeSpan budget,
        CancellationToken cancellationToken)
    {
        DateTime deadline = DateTime.UtcNow + budget;
        while (DateTime.UtcNow < deadline && !page.Unresponsive)
        {
            cancellationToken.ThrowIfCancellationRequested();
            _ = RestoreIfSuspended(window);
            ProbeSurface surface = await ReadSurfaceAsync(page, cancellationToken);
            if (surface.InputPresent && surface.InputEnabled)
            {
                return true;
            }

            await Task.Delay(TimeSpan.FromMilliseconds(500), cancellationToken);
        }

        return false;
    }

    private static async Task<ProbeSurface> ReadSurfaceAsync(
        ProbePage page,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        // Sin superficie la lectura no está ociosa y el sondeo sigue.
        return ProbeSurface.Parse(await page.RunAsync(SurfaceScript));
    }

    /// <summary>Las filas que muestra la ventana, o <c>null</c> si no se pudieron leer.</summary>
    private static async Task<JsonArray?> ReadRowsAsync(ProbePage page)
    {
        string? result = await page.RunAsync(ReadScript);
        if (string.IsNullOrWhiteSpace(result))
        {
            return null;
        }

        try
        {
            return JsonNode.Parse(JsonSerializer.Deserialize<string>(result) ?? "[]") as JsonArray;
        }
        catch (JsonException)
        {
            return null;
        }
    }

    private static JsonObject Terminal(string kind, string diagnostic) => new()
    {
        ["type"] = "terminal",
        ["kind"] = kind,
        ["diagnostic"] = diagnostic,
        ["finished_utc"] = Utc(DateTime.UtcNow),
    };

    private static JsonObject Tagged(ProbeCommand command, JsonObject payload)
    {
        if (command.Tags is { } tags)
        {
            foreach ((string key, JsonNode? value) in tags)
            {
                payload[key] = value?.DeepClone();
            }
        }

        return payload;
    }

    private static string Utc(DateTime value) =>
        value.ToUniversalTime().ToString("O", CultureInfo.InvariantCulture);

    private static async Task WriteAsync(StreamWriter writer, JsonObject payload)
    {
        await writer.WriteLineAsync(payload.ToJsonString());
        await writer.FlushAsync();
    }
}

internal enum ProbeCommandKind
{
    Skip,
    Turn,
    NewSession,
    Invalid,
}

internal sealed record ProbeCommand(
    ProbeCommandKind Kind,
    string Text,
    JsonObject? Tags,
    string? Diagnostic)
{
    internal static ProbeCommand Skip { get; } =
        new(ProbeCommandKind.Skip, string.Empty, null, null);
}

/// <summary>Lo que la sonda lee del compositor en cada sondeo.</summary>
internal readonly record struct ProbeSurface(
    bool InputPresent,
    bool InputEnabled,
    int DraftLength,
    int ProgressLength,
    int Rows,
    string? Head = null)
{
    /// <summary>
    /// Sin turno en curso: input habilitado, borrador vacío (el compositor lo
    /// vacía cuando <c>/turn</c> responde) y ninguna etapa a la vista.
    /// </summary>
    internal bool Idle => InputPresent && InputEnabled && DraftLength == 0 && ProgressLength == 0;

    /// <summary>Lee el resultado de <c>ExecuteScriptAsync</c> (una cadena JSON con un objeto dentro).</summary>
    internal static ProbeSurface Parse(string? scriptResult)
    {
        try
        {
            string? inner = string.IsNullOrWhiteSpace(scriptResult)
                ? null
                : JsonSerializer.Deserialize<string>(scriptResult);
            if (inner is null || JsonNode.Parse(inner) is not JsonObject surface)
            {
                return default;
            }

            return new ProbeSurface(
                Flag(surface["input"]),
                Flag(surface["enabled"]),
                Number(surface["draft"]),
                Number(surface["progress"]),
                Number(surface["rows"]),
                surface["head"] is JsonValue head && head.TryGetValue(out string? text) ? text : null);
        }
        catch (JsonException)
        {
            return default;
        }
    }

    private static bool Flag(JsonNode? node) =>
        node is JsonValue value && value.TryGetValue(out bool flag) && flag;

    private static int Number(JsonNode? node) =>
        node is JsonValue value && value.TryGetValue(out int number) ? number : 0;
}

/// <summary>Una fila de la lista de actividad tal como la ventana la pinta.</summary>
internal readonly record struct ProbeRow(string Src, string Msg, string Ts)
{
    internal static IReadOnlyList<ProbeRow> ListOf(JsonArray? rows)
    {
        var list = new List<ProbeRow>();
        if (rows is null)
        {
            return list;
        }

        foreach (JsonNode? node in rows)
        {
            list.Add(new ProbeRow(Field(node, "src"), Field(node, "msg"), Field(node, "ts")));
        }

        return list;
    }

    /// <summary>
    /// Cuántas filas de <paramref name="after"/> son nuevas. La lista va con la
    /// más nueva primero y se recorta por la cola, así que lo nuevo es el
    /// prefijo más corto tras el cual lo que queda coincide, fila a fila, con
    /// el principio de <paramref name="before"/>. Comparar la secuencia entera
    /// (no sólo la cabeza) evita que una fila repetida engañe; si nada
    /// coincide (la sesión se vació a mitad), todo es nuevo.
    /// </summary>
    internal static int FreshCount(IReadOnlyList<ProbeRow> before, IReadOnlyList<ProbeRow> after)
    {
        ArgumentNullException.ThrowIfNull(before);
        ArgumentNullException.ThrowIfNull(after);
        if (before.Count == 0)
        {
            return after.Count;
        }

        for (int fresh = 0; fresh < after.Count; fresh++)
        {
            int overlap = Math.Min(before.Count, after.Count - fresh);
            bool aligned = true;
            for (int row = 0; row < overlap && aligned; row++)
            {
                aligned = after[fresh + row] == before[row];
            }

            if (aligned)
            {
                return fresh;
            }
        }

        return after.Count;
    }

    private static string Field(JsonNode? node, string name) =>
        node is JsonObject row && row[name] is JsonValue value && value.TryGetValue(out string? text)
            ? text ?? string.Empty
            : string.Empty;
}

/// <summary>
/// Decide cuándo terminó un turno. Contar «antes + 2 filas» fallaba: la fila
/// SYSTEM de una sesión nueva, las filas de progreso y las confirmaciones la
/// adelantaban. Aquí el turno termina cuando la superficie está ociosa y ni el
/// recuento de filas ni la de cabeza cambiaron durante toda la ventana de
/// estabilidad (al tope de filas el recuento ya no se mueve).
/// </summary>
internal sealed class TurnSettleTracker
{
    private readonly int _before;
    private readonly string? _headBefore;
    private readonly TimeSpan _stableWindow;
    private int _lastRows = -1;
    private string? _lastHead;
    private TimeSpan? _stableSince;

    internal TurnSettleTracker(int rowsBefore, TimeSpan stableWindow, string? headBefore = null)
    {
        ArgumentOutOfRangeException.ThrowIfNegative(rowsBefore);
        ArgumentOutOfRangeException.ThrowIfLessThan(stableWindow, TimeSpan.Zero);
        _before = rowsBefore;
        _headBefore = headBefore;
        _stableWindow = stableWindow;
    }

    /// <summary>
    /// Si alguna lectura mostró más filas que al empezar, o las mismas con otra
    /// en cabeza (lista llena). Menos filas es una sesión vaciada, no un turno.
    /// </summary>
    internal bool Grew { get; private set; }

    internal bool Observe(TimeSpan elapsed, ProbeSurface surface)
    {
        if (surface.InputPresent
            && (surface.Rows > _before
                || (surface.Rows == _before && _before > 0
                    && !string.Equals(surface.Head, _headBefore, StringComparison.Ordinal))))
        {
            Grew = true;
        }

        if (!surface.Idle
            || surface.Rows != _lastRows
            || !string.Equals(surface.Head, _lastHead, StringComparison.Ordinal))
        {
            _lastRows = surface.Rows;
            _lastHead = surface.Head;
            _stableSince = surface.Idle ? elapsed : null;
            return false;
        }

        _stableSince ??= elapsed;
        return elapsed - _stableSince.Value >= _stableWindow;
    }
}

internal enum SendGateState
{
    Wait,
    Ready,
    NoSurface,
    NotIdle,
}

/// <summary>
/// Decide si ya se puede teclear el turno siguiente. Hace falta una superficie
/// legible (con el campo suspendido la lectura vuelve vacía y no vale como «cero
/// filas») y ociosa. Si el turno anterior no se asentó, además estable durante
/// la ventana: su respuesta tardía no debe caer entre las filas del siguiente.
/// </summary>
internal sealed class SendGate
{
    private readonly TimeSpan _stableWindow;
    private readonly TimeSpan _surfaceBudget;
    private readonly TimeSpan _idleBudget;
    private readonly bool _requireStable;
    private bool _sawSurface;
    private TurnSettleTracker? _tracker;

    internal SendGate(
        TimeSpan stableWindow,
        TimeSpan surfaceBudget,
        TimeSpan idleBudget,
        bool requireStable)
    {
        _stableWindow = stableWindow;
        _surfaceBudget = surfaceBudget;
        _idleBudget = idleBudget;
        _requireStable = requireStable;
    }

    internal SendGateState Observe(TimeSpan elapsed, ProbeSurface surface)
    {
        if (surface.InputPresent)
        {
            bool first = !_sawSurface;
            _sawSurface = true;
            if (first && !_requireStable && surface.Idle)
            {
                return SendGateState.Ready;
            }

            _tracker ??= new TurnSettleTracker(surface.Rows, _stableWindow, surface.Head);
            if (_tracker.Observe(elapsed, surface))
            {
                return SendGateState.Ready;
            }
        }

        if (!_sawSurface && elapsed >= _surfaceBudget)
        {
            return SendGateState.NoSurface;
        }

        return elapsed >= _idleBudget
            ? (_sawSurface ? SendGateState.NotIdle : SendGateState.NoSurface)
            : SendGateState.Wait;
    }
}

/// <summary>
/// Los scripts de la sonda sobre la página, cada uno con tope. Encargo PH (tanda n3
/// t4, 2026-10-13 00:28): con la memoria virtual del sistema agotada, un proceso de
/// WebView2 quedó en «Unknown Hard Error», la vista no aplicó la respuesta del turno
/// y <c>ExecuteScriptAsync</c> no volvió nunca; la sonda esperó 7 h a su tope
/// externo. Una lectura que no vuelve en <see cref="DefaultScriptBudget"/> cuenta
/// como colgada; mientras siga sin volver no se encola otra (el render no la
/// correría) y cada lectura vuelve vacía al momento. Si la página sigue así
/// <see cref="DefaultStallBudget"/>, queda <see cref="Unresponsive"/> y los bucles
/// de la sonda dejan de esperarla. Si la lectura colgada vuelve, se sigue normal.
/// Con el campo suspendido o la vista cerrada WebView2 lanza: eso es «no hay
/// superficie» (vacío), no un fallo de la sonda.
/// </summary>
internal sealed class ProbePage
{
    internal static readonly TimeSpan DefaultScriptBudget = TimeSpan.FromSeconds(15);
    internal static readonly TimeSpan DefaultStallBudget = TimeSpan.FromSeconds(60);

    private readonly Func<string, Task<string>> _execute;
    private readonly TimeSpan _scriptBudget;
    private readonly TimeSpan _stallBudget;
    private readonly Stopwatch _stalled = new();
    private Task<string>? _hung;

    internal ProbePage(Func<string, Task<string>> execute, TimeSpan scriptBudget, TimeSpan stallBudget)
    {
        _execute = execute ?? throw new ArgumentNullException(nameof(execute));
        _scriptBudget = scriptBudget;
        _stallBudget = stallBudget;
    }

    /// <summary>Lecturas que no volvieron dentro de su tope.</summary>
    internal int Hangs { get; private set; }

    /// <summary>Una lectura lleva colgada al menos el tope de estancamiento.</summary>
    internal bool Unresponsive => Stalled && _stalled.Elapsed >= _stallBudget;

    private bool Stalled
    {
        get
        {
            if (_hung is { IsCompleted: true })
            {
                _hung = null;
                _stalled.Reset();
            }

            return _hung is not null;
        }
    }

    internal async Task<string?> RunAsync(string script)
    {
        if (Stalled)
        {
            return null;
        }

        try
        {
            Task<string> pending = _execute(script);
            using var timer = new CancellationTokenSource();
            if (await Task.WhenAny(pending, Task.Delay(_scriptBudget, timer.Token)) != pending)
            {
                Hangs++;
                _hung = pending;
                _stalled.Restart();
                // Si algún día falla, su excepción no queda sin observar.
                _ = pending.ContinueWith(
                    static task => _ = task.Exception,
                    CancellationToken.None,
                    TaskContinuationOptions.OnlyOnFaulted | TaskContinuationOptions.ExecuteSynchronously,
                    TaskScheduler.Default);
                return null;
            }

            await timer.CancelAsync();
            return await pending;
        }
        catch (Exception exception) when (exception is InvalidOperationException or COMException)
        {
            return null;
        }
    }
}

/// <summary>Lo único que la sonda necesita de la ventana nativa.</summary>
internal interface IFieldProbeWindow
{
    bool IsMinimized { get; }

    bool IsHidden { get; }

    void RestoreWithoutActivation();
}

/// <summary>
/// Muestra y restaura sin activar: oculta, <c>Show</c> con
/// <see cref="Window.ShowActivated"/> en falso (<c>SW_SHOWNA</c>); minimizada,
/// <c>SW_SHOWNOACTIVATE</c>. La ventana vuelve sin quitarle el foco a la
/// aplicación en la que esté la persona, y WPF reanuda el campo por el mismo
/// camino que cuando la persona la restaura.
/// </summary>
internal sealed class FieldProbeWindow : IFieldProbeWindow
{
    private const int ShowNoActivate = 4;
    private readonly Window _window;

    internal FieldProbeWindow(Window window)
    {
        _window = window ?? throw new ArgumentNullException(nameof(window));
    }

    public bool IsMinimized => _window.WindowState == WindowState.Minimized;

    public bool IsHidden => !_window.IsVisible;

    public void RestoreWithoutActivation()
    {
        if (IsHidden)
        {
            bool showActivated = _window.ShowActivated;
            _window.ShowActivated = false;
            try
            {
                _window.Show();
            }
            finally
            {
                _window.ShowActivated = showActivated;
            }
        }

        if (!IsMinimized)
        {
            return;
        }

        nint handle = new WindowInteropHelper(_window).Handle;
        if (handle != 0)
        {
            _ = NativeMethods.ShowWindow(handle, ShowNoActivate);
        }
    }

    private static class NativeMethods
    {
        [DllImport("user32.dll")]
        [return: MarshalAs(UnmanagedType.Bool)]
        internal static extern bool ShowWindow(nint hWnd, int nCmdShow);
    }
}
