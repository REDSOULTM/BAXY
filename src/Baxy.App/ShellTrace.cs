using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Text;

namespace Baxy.App;

/// <summary>
/// Etiquetas estables del camino de respuesta visible. Nunca contienen texto
/// del usuario, prosa del modelo ni datos privados: sólo identificadores fijos
/// que permiten correlacionar tiempos entre el puente, la vista y el motor.
/// </summary>
internal static class ShellTraceStages
{
    internal const string ProcessStart = "process.start";
    internal const string ProcessYielded = "process.yielded";
    internal const string WindowCreated = "window.created";
    internal const string WindowShown = "window.shown";
    internal const string StartupBegin = "startup.begin";
    internal const string StartupFieldBegin = "startup.field.begin";
    internal const string StartupFieldReady = "startup.field.ready";
    internal const string StartupShellBegin = "startup.shell.begin";
    internal const string StartupShellReady = "startup.shell.ready";
    internal const string StartupReady = "startup.ready";
    internal const string StartupFailed = "startup.failed";

    internal const string SubmitReceived = "submit.received";
    internal const string BridgeCrossed = "bridge.crossed";
    internal const string DecisionStart = "decision.start";
    internal const string QueueWaitStart = "queue.wait.start";
    internal const string QueueWaitEnd = "queue.wait.end";
    internal const string DecisionReady = "decision.ready";
    internal const string NarrationStart = "narration.start";
    internal const string NarrationReady = "narration.ready";

    /// <summary>Envío al Core hasta su respuesta verificada (incluye provider).</summary>
    internal const string CoreCallStart = "core.call.start";
    internal const string CoreCallEnd = "core.call.end";

    /// <summary>Grounding de argumentos contra el schema.</summary>
    internal const string ArgumentsStart = "arguments.start";
    internal const string ArgumentsEnd = "arguments.end";

    /// <summary>Composición final del mensaje visible por el LLM.</summary>
    internal const string ComposeStart = "compose.start";
    internal const string ComposeEnd = "compose.end";

    /// <summary>Pulsación real de la persona, reportada por el documento.</summary>
    internal const string KeyEnter = "key.enter";

    // NOTA DE HONESTIDAD: `paint.observed` es el segundo requestAnimationFrame
    // posterior a la mutación del DOM. Es un *proxy* de doble rAF, no una
    // confirmación del compositor del sistema operativo: acredita que el motor
    // de render pasó por dos vueltas de frame, no que el píxel llegó a la
    // pantalla. Etiquetarlo como «primer paint físico» exigiría una
    // observación externa correlacionada que aquí no existe.
    internal const string VisibleIndication = "visible.indication";
    internal const string VisibleText = "visible.text";
    internal const string ResponseFinal = "response.final";
    internal const string TurnCancelled = "turn.cancelled";
    internal const string TurnError = "turn.error";
    internal const string TurnRecovered = "turn.recovered";
    internal const string VoiceState = "voice.state";
    internal const string TraceTruncated = "trace.truncated";

    /// <summary>Marcas que sólo puede emitir el observador del documento.</summary>
    internal const string DomApplied = "dom.applied";
    internal const string PaintObserved = "paint.observed";

    /// <summary>
    /// Vocabulario cerrado que el documento tiene permitido reportar. Cualquier
    /// otra etiqueta llegada desde la vista se descarta: la instrumentación no
    /// es un canal de datos libres.
    /// </summary>
    internal static readonly string[] DocumentReportable =
    [
        DomApplied,
        PaintObserved,
        KeyEnter,
    ];

    internal static readonly string[] All =
    [
        ProcessStart,
        ProcessYielded,
        WindowCreated,
        WindowShown,
        StartupBegin,
        StartupFieldBegin,
        StartupFieldReady,
        StartupShellBegin,
        StartupShellReady,
        StartupReady,
        StartupFailed,
        SubmitReceived,
        BridgeCrossed,
        DecisionStart,
        QueueWaitStart,
        QueueWaitEnd,
        DecisionReady,
        NarrationStart,
        NarrationReady,
        CoreCallStart,
        CoreCallEnd,
        ArgumentsStart,
        ArgumentsEnd,
        ComposeStart,
        ComposeEnd,
        KeyEnter,
        VisibleIndication,
        VisibleText,
        ResponseFinal,
        TurnCancelled,
        TurnError,
        TurnRecovered,
        VoiceState,
        TraceTruncated,
        DomApplied,
        PaintObserved,
    ];
}

internal static class ShellTraceScopes
{
    internal const string Startup = "startup";
    internal const string Bridge = "bridge";
    internal const string Turn = "turn";
    internal const string Recovery = "recovery";
}

/// <summary>
/// Registro opcional y determinista del camino de respuesta visible. Está
/// apagado salvo que <c>BAXY_APP_TRACE</c> apunte a una ruta de archivo. Sólo
/// escribe identificadores estables y tiempos monotónicos: nunca el mensaje de
/// una persona, la prosa del modelo ni un dato privado.
/// </summary>
internal sealed class ShellTrace : IDisposable
{
    internal const string PathEnvironmentVariable = "BAXY_APP_TRACE";
    internal const int MaximumRecords = 50_000;
    internal const int MaximumLabelLength = 64;
    private const string InvalidLabel = "invalid";

    private readonly object _gate = new();
    private readonly StreamWriter _writer;
    private readonly long _origin = Stopwatch.GetTimestamp();
    private long _sequence;
    private int _records;
    private bool _truncated;
    private bool _disposed;

    private ShellTrace(StreamWriter writer)
    {
        _writer = writer;
    }

    /// <summary>Milisegundos monotónicos desde la creación del registro.</summary>
    internal double ElapsedMilliseconds =>
        (Stopwatch.GetTimestamp() - _origin) * 1000d / Stopwatch.Frequency;

    internal static ShellTrace? TryCreateFromEnvironment() =>
        TryCreate(Environment.GetEnvironmentVariable(PathEnvironmentVariable));

    internal static ShellTrace? TryCreate(string? path)
    {
        if (string.IsNullOrWhiteSpace(path))
        {
            return null;
        }

        try
        {
            string full = Path.GetFullPath(path);
            string? directory = Path.GetDirectoryName(full);
            if (string.IsNullOrEmpty(directory))
            {
                return null;
            }

            Directory.CreateDirectory(directory);
            var stream = new FileStream(
                full,
                FileMode.Append,
                FileAccess.Write,
                FileShare.ReadWrite,
                4096,
                FileOptions.SequentialScan);
            var writer = new StreamWriter(
                stream,
                new UTF8Encoding(encoderShouldEmitUTF8Identifier: false))
            {
                AutoFlush = true,
            };
            return new ShellTrace(writer);
        }
        catch (Exception exception) when (
            exception is IOException
                or UnauthorizedAccessException
                or ArgumentException
                or NotSupportedException
                or System.Security.SecurityException)
        {
            // Diagnostics can never make the visible path unavailable.
            return null;
        }
    }

    /// <summary>
    /// Registra un hito. <paramref name="id"/> correlaciona todo lo que ocurre
    /// en la misma solicitud; <paramref name="detail"/> admite sólo una
    /// etiqueta estable, nunca contenido.
    /// </summary>
    internal void Record(string scope, string id, string stage, string? detail = null)
    {
        if (_disposed)
        {
            return;
        }

        double elapsed = ElapsedMilliseconds;
        string safeScope = SanitizeLabel(scope);
        string safeId = SanitizeId(id);
        string safeStage = SanitizeLabel(stage);
        string? safeDetail = detail is null ? null : SanitizeLabel(detail);
        lock (_gate)
        {
            if (_disposed)
            {
                return;
            }

            if (_records >= MaximumRecords)
            {
                if (_truncated)
                {
                    return;
                }

                _truncated = true;
                safeScope = ShellTraceScopes.Startup;
                safeStage = ShellTraceStages.TraceTruncated;
                safeId = "trace";
                safeDetail = null;
            }
            else
            {
                _records++;
            }

            long sequence = ++_sequence;
            try
            {
                _writer.Write("{\"seq\":");
                _writer.Write(sequence.ToString(CultureInfo.InvariantCulture));
                _writer.Write(",\"ms\":");
                _writer.Write(elapsed.ToString("F3", CultureInfo.InvariantCulture));
                _writer.Write(",\"scope\":\"");
                _writer.Write(safeScope);
                _writer.Write("\",\"id\":\"");
                _writer.Write(safeId);
                _writer.Write("\",\"stage\":\"");
                _writer.Write(safeStage);
                if (safeDetail is null)
                {
                    _writer.Write("\",\"detail\":null}");
                }
                else
                {
                    _writer.Write("\",\"detail\":\"");
                    _writer.Write(safeDetail);
                    _writer.Write("\"}");
                }

                _writer.Write('\n');
            }
            catch (Exception exception) when (
                exception is IOException or ObjectDisposedException)
            {
                // A diagnostic write never escalates into the product path.
            }
        }
    }

    /// <summary>
    /// Reduce cualquier valor a una etiqueta estable en minúsculas. Un valor
    /// con contenido libre nunca llega al archivo: se sustituye por
    /// <c>invalid</c>.
    /// </summary>
    internal static string SanitizeLabel(string? value)
    {
        if (string.IsNullOrEmpty(value) || value.Length > MaximumLabelLength)
        {
            return InvalidLabel;
        }

        foreach (char character in value)
        {
            bool allowed = character is >= 'a' and <= 'z'
                || character is >= '0' and <= '9'
                || character is '.' or '_' or '-';
            if (!allowed)
            {
                return InvalidLabel;
            }
        }

        return value;
    }

    internal static string SanitizeId(string? value)
    {
        if (string.IsNullOrEmpty(value) || value.Length > MaximumLabelLength)
        {
            return InvalidLabel;
        }

        foreach (char character in value)
        {
            bool allowed = character is >= 'a' and <= 'z'
                || character is >= 'A' and <= 'Z'
                || character is >= '0' and <= '9'
                || character is '.' or '_' or '-';
            if (!allowed)
            {
                return InvalidLabel;
            }
        }

        return value;
    }

    public void Dispose()
    {
        lock (_gate)
        {
            if (_disposed)
            {
                return;
            }

            _disposed = true;
            try
            {
                _writer.Flush();
            }
            catch (Exception exception) when (
                exception is IOException or ObjectDisposedException)
            {
            }

            _writer.Dispose();
        }
    }
}

/// <summary>
/// Punto de acceso único al registro opcional. Se resuelve una sola vez desde
/// el entorno; las pruebas pueden sustituirlo de forma acotada.
/// </summary>
internal static class ShellTraceSink
{
    private static readonly object Gate = new();
    private static ShellTrace? _current;
    private static ShellTrace? _override;
    private static bool _resolved;

    private static string _turnId = "t0";

    /// <summary>
    /// Identificador del turno en curso. Lo publica el ViewModel para que los
    /// componentes de transporte —que no conocen el turno— puedan correlacionar
    /// sus tramos sin recibir una dependencia nueva.
    /// </summary>
    internal static string TurnId
    {
        get => Volatile.Read(ref _turnId);
        set => Volatile.Write(ref _turnId, value);
    }

    internal static ShellTrace? Current
    {
        get
        {
            ShellTrace? overridden = Volatile.Read(ref _override);
            if (overridden is not null)
            {
                return overridden;
            }

            if (Volatile.Read(ref _resolved))
            {
                return Volatile.Read(ref _current);
            }

            lock (Gate)
            {
                if (!_resolved)
                {
                    _current = ShellTrace.TryCreateFromEnvironment();
                    Volatile.Write(ref _resolved, true);
                }

                return _current;
            }
        }
    }

    internal static void Record(
        string scope,
        string id,
        string stage,
        string? detail = null) =>
        Current?.Record(scope, id, stage, detail);

    /// <summary>
    /// Sustituye el registro activo mientras dura el ámbito devuelto. Es la
    /// única vía por la que una prueba observa el instrumental.
    /// </summary>
    internal static IDisposable Use(ShellTrace trace)
    {
        ArgumentNullException.ThrowIfNull(trace);
        ShellTrace? previous = Interlocked.Exchange(ref _override, trace);
        return new OverrideScope(previous);
    }

    private sealed class OverrideScope(ShellTrace? previous) : IDisposable
    {
        private bool _disposed;

        public void Dispose()
        {
            if (_disposed)
            {
                return;
            }

            _disposed = true;
            Volatile.Write(ref _override, previous);
        }
    }
}
