using System.Collections.Concurrent;
using System.ComponentModel;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using Baxy.Contracts;
using Baxy.Kernel.Operations;

namespace Baxy.App;

internal sealed class CoreProcessClient : IAsyncDisposable
{
    internal const int MaximumProtocolLineLength = 1_048_576;
    private const int MaximumDiagnosticLineLength = 2048;
    private const int MaximumDiagnostics = 64;
    private static readonly TimeSpan DefaultResponseReconciliationTimeout =
        TimeSpan.FromSeconds(70);
    private static readonly OperationDescriptor[] RequiredInteractiveOperations =
        ProductCatalog.ToolDescriptors
            .Select(static descriptor =>
                ProductCatalog.CreateToolDescriptor(new OperationDefinition(descriptor)))
            .ToArray();
    private readonly ConcurrentDictionary<string, PendingResponse> _pending = new(StringComparer.Ordinal);
    private readonly ConcurrentQueue<string> _diagnostics = new();
    private readonly SemaphoreSlim _writeLock = new(1, 1);
    private readonly SemaphoreSlim _lifecycleLock = new(1, 1);

    private Process? _process;
    private LocalJsonlSidecarProcess? _sidecar;
    private CancellationTokenSource? _pumpCancellation;
    private Task? _stdoutPump;
    private Task? _stderrPump;
    private TaskCompletionSource<ProtocolHello>? _helloCompletion;
    private IReadOnlyList<OperationDescriptor> _capabilities = Array.Empty<OperationDescriptor>();
    private ApplicationCatalogSnapshot? _applicationCatalog;
    private GameCatalogSnapshot? _gameCatalog;
    private bool _started;
    private bool _ready;
    private bool _disposed;
    private int _disconnectSignaled;

    public event Action? Disconnected;

    public bool IsReady => _ready && _process is { HasExited: false };

    public IReadOnlyList<OperationDescriptor> Capabilities => _capabilities;

    public ApplicationCatalogSnapshot? ApplicationCatalog => _applicationCatalog;

    public GameCatalogSnapshot? GameCatalog => _gameCatalog;

    public async Task StartAsync(TimeSpan handshakeTimeout, CancellationToken cancellationToken)
    {
        ObjectDisposedException.ThrowIf(_disposed, this);
        ArgumentOutOfRangeException.ThrowIfLessThanOrEqual(handshakeTimeout, TimeSpan.Zero);

        await _lifecycleLock.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            if (_started)
            {
                throw new InvalidOperationException("El cliente del core ya fue iniciado.");
            }

            var executable = ResolveCoreExecutable();
            var sidecar = LocalJsonlSidecarProcess.Start(new LocalJsonlSidecarDefinition(
                "core",
                executable,
                Path.GetDirectoryName(executable)!,
                drainStandardError: false));
            Process process = sidecar.Process;
            _process = process;
            _sidecar = sidecar;
            process.Exited += OnProcessExited;
            _pumpCancellation = new CancellationTokenSource();
            _helloCompletion = new TaskCompletionSource<ProtocolHello>(TaskCreationOptions.RunContinuationsAsynchronously);
            _started = true;
            _stdoutPump = PumpStandardOutputAsync(process, _pumpCancellation.Token);
            _stderrPump = PumpStandardErrorAsync(process, _pumpCancellation.Token);

            using var timeoutCancellation = new CancellationTokenSource(handshakeTimeout);
            using var linkedCancellation = CancellationTokenSource.CreateLinkedTokenSource(
                cancellationToken,
                timeoutCancellation.Token);
            ProtocolHello hello;
            try
            {
                hello = await _helloCompletion.Task.WaitAsync(linkedCancellation.Token).ConfigureAwait(false);
            }
            catch (OperationCanceledException) when (
                timeoutCancellation.IsCancellationRequested && !cancellationToken.IsCancellationRequested)
            {
                throw new TimeoutException("El core no emitió el saludo local a tiempo.");
            }

            if (hello.Pid != process.Id)
            {
                throw new InvalidDataException("El saludo no pertenece al proceso de core iniciado por BAXY.");
            }

            if (!SupportsInteractiveOperations(hello))
            {
                throw new InvalidDataException(
                    "El core no ofrece todas las operaciones requeridas por la interfaz.");
            }

            _capabilities = hello.Capabilities.ToArray();
            _applicationCatalog = hello.ApplicationCatalog is null
                ? null
                : hello.ApplicationCatalog with
                {
                    Names = hello.ApplicationCatalog.Names.ToArray(),
                };
            _gameCatalog = hello.GameCatalog is null
                ? null
                : hello.GameCatalog with
                {
                    Entries = hello.GameCatalog.Entries.ToArray(),
                };

            if (process.HasExited || Volatile.Read(ref _disconnectSignaled) != 0)
            {
                throw new IOException("El motor local terminó durante el saludo de protocolo.");
            }

            _ready = true;
            if (process.HasExited || Volatile.Read(ref _disconnectSignaled) != 0)
            {
                _ready = false;
                throw new IOException("El motor local terminó durante el saludo de protocolo.");
            }
        }
        catch
        {
            await StopProcessAsync().ConfigureAwait(false);
            throw;
        }
        finally
        {
            _lifecycleLock.Release();
        }
    }

    public async Task<OperationResponse> SendOperationAsync(
        PreparedOperation operation,
        TimeSpan timeout,
        CancellationToken cancellationToken,
        string? confirmationToken = null)
    {
        ObjectDisposedException.ThrowIf(_disposed, this);
        ArgumentNullException.ThrowIfNull(operation);
        ArgumentOutOfRangeException.ThrowIfLessThanOrEqual(timeout, TimeSpan.Zero);
        if (!IsReady)
        {
            throw new InvalidOperationException("El motor local no completó el saludo de protocolo.");
        }

        // El envío al Core cubre kernel, provider y verificación de
        // postcondición. Se marca aquí, en el único punto por el que pasan
        // todas las rutas, para que ese tramo no quede fundido con la
        // composición final del mensaje.
        ShellTraceSink.Record(
            ShellTraceScopes.Turn,
            ShellTraceSink.TurnId,
            ShellTraceStages.CoreCallStart,
            operation.OperationName);
        try
        {
            return await SendOperationCoreAsync(
                operation,
                timeout,
                confirmationToken,
                cancellationToken).ConfigureAwait(false);
        }
        finally
        {
            ShellTraceSink.Record(
                ShellTraceScopes.Turn,
                ShellTraceSink.TurnId,
                ShellTraceStages.CoreCallEnd);
        }
    }

    private async Task<OperationResponse> SendOperationCoreAsync(
        PreparedOperation operation,
        TimeSpan timeout,
        string? confirmationToken,
        CancellationToken cancellationToken)
    {
        OperationRequest request = operation.CreateRequest(confirmationToken);
        var pending = new PendingResponse(request.MissionId, request.InvocationId);
        if (!_pending.TryAdd(request.RequestId, pending))
        {
            throw new InvalidOperationException("The local request id is already in use.");
        }

        try
        {
            byte[] utf8Line = ProtocolJson.SerializeToUtf8Bytes(request);
            if (utf8Line.Length > MaximumProtocolLineLength)
            {
                throw new InvalidOperationException("The request exceeds the local protocol limit.");
            }

            var process = _process;
            LocalJsonlSidecarProcess? sidecar = _sidecar;
            if (process is null || sidecar is null)
            {
                throw new IOException("El motor local no está disponible.");
            }

            await _writeLock.WaitAsync(cancellationToken).ConfigureAwait(false);
            try
            {
                if (process.HasExited)
                {
                    throw new IOException("The local engine exited before receiving the request.");
                }

                if (string.Equals(operation.OperationName, "app.open", StringComparison.Ordinal))
                {
                    // Grant only the trusted core immediately before its serialized
                    // request can be observed. Final foreground identity is still
                    // independently verified by the provider.
                    _ = ForegroundPermission.AllowSetForegroundWindow(
                        unchecked((uint)process.Id));
                }

                await sidecar.WriteUtf8LineAsync(utf8Line, cancellationToken)
                    .ConfigureAwait(false);
            }
            finally
            {
                _writeLock.Release();
            }

            return await AwaitResponseWithReconciliationAsync(
                pending.Completion.Task,
                timeout,
                DefaultResponseReconciliationTimeout,
                cancellationToken).ConfigureAwait(false);
        }
        finally
        {
            _pending.TryRemove(request.RequestId, out _);
        }
    }

    public async ValueTask DisposeAsync()
    {
        if (_disposed)
        {
            return;
        }

        await _lifecycleLock.WaitAsync().ConfigureAwait(false);
        try
        {
            if (_disposed)
            {
                return;
            }

            _disposed = true;
            await StopProcessAsync().ConfigureAwait(false);
        }
        finally
        {
            _lifecycleLock.Release();
            _writeLock.Dispose();
            _lifecycleLock.Dispose();
        }
    }

    private async Task PumpStandardOutputAsync(Process process, CancellationToken cancellationToken)
    {
        var lineReader = new BoundedUtf8LineReader(
            process.StandardOutput.BaseStream,
            MaximumProtocolLineLength);
        try
        {
            while (!cancellationToken.IsCancellationRequested)
            {
                BoundedUtf8Line? received = await lineReader.ReadAsync(cancellationToken).ConfigureAwait(false);
                if (received is null)
                {
                    break;
                }

                if (received.Value.TooLarge || received.Value.Utf8 is not { Length: > 0 } utf8Line)
                {
                    throw new InvalidDataException("El core devolvió una línea de protocolo demasiado grande.");
                }

                string? messageType = ReadProtocolMessageType(utf8Line);
                if (messageType is null)
                {
                    throw new InvalidDataException("El core devolvió un envelope sin tipo.");
                }

                if (string.Equals(messageType, ProtocolTypes.Hello, StringComparison.Ordinal))
                {
                    var hello = ProtocolJson.DeserializeHello(utf8Line);
                    if (_helloCompletion is null || !_helloCompletion.TrySetResult(hello))
                    {
                        throw new InvalidDataException("El core emitió más de un saludo local.");
                    }

                    continue;
                }

                if (string.Equals(messageType, ProtocolTypes.ProtocolError, StringComparison.Ordinal))
                {
                    var protocolError = ProtocolJson.DeserializeError(utf8Line);
                    throw new InvalidDataException(
                        $"El core rechazó un mensaje local ({protocolError.ErrorCode}).");
                }

                if (!string.Equals(messageType, ProtocolTypes.OperationResponse, StringComparison.Ordinal))
                {
                    throw new InvalidDataException("El core devolvió un tipo de mensaje desconocido.");
                }

                var response = ProtocolJson.DeserializeResponse(utf8Line);
                if (!_pending.TryGetValue(response.RequestId, out var pending))
                {
                    continue;
                }

                if (!string.Equals(response.MissionId, pending.MissionId, StringComparison.Ordinal)
                    || !string.Equals(response.InvocationId, pending.InvocationId, StringComparison.Ordinal))
                {
                    throw new InvalidDataException(
                        "The core response does not match the requested mission.");
                }

                pending.Completion.TrySetResult(response);
            }

            if (!cancellationToken.IsCancellationRequested)
            {
                SignalDisconnected(new IOException("El canal local se cerró."));
            }
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            // Expected while the shell is shutting down.
        }
        catch (Exception exception) when (
            exception is IOException or JsonException or InvalidDataException or DecoderFallbackException)
        {
            SignalDisconnected(exception);
        }
    }

    internal static string? ReadProtocolMessageType(ReadOnlySpan<byte> utf8Line)
    {
        var reader = new Utf8JsonReader(utf8Line);
        if (!reader.Read())
        {
            throw new JsonException("Empty BAXY protocol envelope.");
        }

        if (reader.TokenType != JsonTokenType.StartObject)
        {
            reader.Skip();
            if (reader.Read())
            {
                throw new JsonException("Invalid BAXY protocol envelope.");
            }

            return null;
        }

        string? messageType = null;
        bool reachedEnd = false;
        while (reader.Read())
        {
            if (reader.TokenType == JsonTokenType.EndObject)
            {
                reachedEnd = true;
                break;
            }

            if (reader.TokenType != JsonTokenType.PropertyName)
            {
                throw new JsonException("Invalid BAXY protocol envelope.");
            }

            bool isType = reader.ValueTextEquals("type"u8);
            if (!reader.Read())
            {
                throw new JsonException("Incomplete BAXY protocol envelope.");
            }

            if (isType)
            {
                messageType = reader.TokenType == JsonTokenType.String
                    ? reader.GetString()
                    : null;
            }

            reader.Skip();
        }

        if (!reachedEnd || reader.Read())
        {
            throw new JsonException("Invalid BAXY protocol envelope.");
        }

        return messageType;
    }

    private async Task PumpStandardErrorAsync(Process process, CancellationToken cancellationToken)
    {
        var lineReader = new BoundedUtf8LineReader(
            process.StandardError.BaseStream,
            MaximumDiagnosticLineLength);
        try
        {
            while (!cancellationToken.IsCancellationRequested)
            {
                BoundedUtf8Line? received = await lineReader.ReadAsync(cancellationToken).ConfigureAwait(false);
                if (received is null)
                {
                    break;
                }

                string bounded = received.Value.TooLarge || received.Value.Utf8 is null
                    ? "stderr_line_too_large"
                    : Encoding.UTF8.GetString(received.Value.Utf8);
                _diagnostics.Enqueue(bounded);
                while (_diagnostics.Count > MaximumDiagnostics)
                {
                    _diagnostics.TryDequeue(out _);
                }
            }
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            // Expected while the shell is shutting down.
        }
        catch (Exception exception) when (exception is IOException or DecoderFallbackException)
        {
            _diagnostics.Enqueue("stderr_unavailable");
        }
    }

    private async Task StopProcessAsync()
    {
        _ready = false;
        var process = _process;
        LocalJsonlSidecarProcess? sidecar = _sidecar;
        _sidecar = null;
        try
        {
            if (process is not null)
            {
                try
                {
                    process.Exited -= OnProcessExited;
                }
                catch (Exception exception) when (
                    exception is InvalidOperationException or Win32Exception or NotSupportedException)
                {
                    _diagnostics.Enqueue("core_event_detach_failed");
                }
            }

            if (sidecar is not null)
            {
                await sidecar.StopAsync().ConfigureAwait(false);
            }
        }
        catch (Exception exception) when (
            exception is InvalidOperationException or IOException or Win32Exception)
        {
            _diagnostics.Enqueue("core_cleanup_failed");
        }
        finally
        {
            _pumpCancellation?.Cancel();
            await ObservePumpAsync(_stdoutPump).ConfigureAwait(false);
            await ObservePumpAsync(_stderrPump).ConfigureAwait(false);
            var closed = new IOException("El motor local se cerró.");
            _helloCompletion?.TrySetException(closed);
            FailPending(closed);

            if (sidecar is not null)
            {
                await sidecar.DisposeAsync().ConfigureAwait(false);
            }
            else
            {
                process?.Dispose();
            }

            _process = null;
            _pumpCancellation?.Dispose();
            _pumpCancellation = null;
            _stdoutPump = null;
            _stderrPump = null;
            _helloCompletion = null;
            _applicationCatalog = null;
            _gameCatalog = null;
            _started = false;
        }
    }

    private void OnProcessExited(object? sender, EventArgs eventArgs)
    {
        if (_disposed || !_started)
        {
            return;
        }

        SignalDisconnected(new IOException("El motor local terminó inesperadamente."));
    }

    private void SignalDisconnected(Exception exception)
    {
        _ready = false;
        _helloCompletion?.TrySetException(exception);
        FailPending(exception);
        if (Interlocked.Exchange(ref _disconnectSignaled, 1) == 0)
        {
            Disconnected?.Invoke();
        }
    }

    private void FailPending(Exception exception)
    {
        foreach (var pending in _pending.Values)
        {
            pending.Completion.TrySetException(exception);
        }
    }

    private static string ResolveCoreExecutable()
    {
        var candidates = new[]
        {
            Path.Combine(AppContext.BaseDirectory, "baxy-core.exe"),
            Path.Combine(AppContext.BaseDirectory, "core", "baxy-core.exe"),
        };

        foreach (var candidate in candidates)
        {
            var fullPath = Path.GetFullPath(candidate);
            if (File.Exists(fullPath))
            {
                return fullPath;
            }
        }

        throw new FileNotFoundException("No se encontró baxy-core.exe junto a la aplicación.");
    }

    internal static bool SupportsInteractiveOperations(ProtocolHello hello)
    {
        ArgumentNullException.ThrowIfNull(hello);
        if (hello.Capabilities.Count != RequiredInteractiveOperations.Length)
        {
            return false;
        }

        for (int index = 0; index < RequiredInteractiveOperations.Length; index++)
        {
            OperationDescriptor required = RequiredInteractiveOperations[index];
            OperationDescriptor supplied = hello.Capabilities[index];
            if (!string.Equals(supplied.Name, required.Name, StringComparison.Ordinal)
                || !string.Equals(supplied.Risk, required.Risk, StringComparison.Ordinal)
                || !string.Equals(
                    supplied.ArgumentsSchema.GetRawText(),
                    required.ArgumentsSchema.GetRawText(),
                    StringComparison.Ordinal)
                || !string.Equals(
                    supplied.VerifierContractId,
                    required.VerifierContractId,
                    StringComparison.Ordinal)
                || !string.Equals(
                    supplied.Description,
                    required.Description,
                    StringComparison.Ordinal))
            {
                return false;
            }
        }

        return true;
    }

    internal TimeoutException DisconnectForResponseTimeout()
    {
        var exception = new TimeoutException("El motor local agotó el tiempo de respuesta.");
        SignalDisconnected(exception);
        return exception;
    }

    internal async Task<OperationResponse> AwaitResponseWithReconciliationAsync(
        Task<OperationResponse> responseTask,
        TimeSpan responseTimeout,
        TimeSpan reconciliationTimeout,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(responseTask);
        ArgumentOutOfRangeException.ThrowIfLessThanOrEqual(responseTimeout, TimeSpan.Zero);
        ArgumentOutOfRangeException.ThrowIfLessThanOrEqual(
            reconciliationTimeout,
            TimeSpan.Zero);

        using (var responseCancellation = new CancellationTokenSource(responseTimeout))
        using (var linkedCancellation = CancellationTokenSource.CreateLinkedTokenSource(
            cancellationToken,
            responseCancellation.Token))
        {
            try
            {
                return await responseTask.WaitAsync(linkedCancellation.Token).ConfigureAwait(false);
            }
            catch (OperationCanceledException) when (
                responseCancellation.IsCancellationRequested
                && !cancellationToken.IsCancellationRequested)
            {
                // Keep the exact request registered with the stdout pump.
                // Providers can legitimately exceed the first-response budget;
                // Spotify UIA, for example, can use about 80 s across one
                // pre-effect retry. Its durable terminal response must win over
                // a timeout while the overall 90 s client budget stays bounded.
            }
        }

        using var reconciliationCancellation =
            new CancellationTokenSource(reconciliationTimeout);
        using var reconciliationLinked =
            CancellationTokenSource.CreateLinkedTokenSource(
                cancellationToken,
                reconciliationCancellation.Token);
        try
        {
            return await responseTask.WaitAsync(reconciliationLinked.Token).ConfigureAwait(false);
        }
        catch (OperationCanceledException) when (
            reconciliationCancellation.IsCancellationRequested
            && !cancellationToken.IsCancellationRequested)
        {
            throw DisconnectForResponseTimeout();
        }
    }

    private static async Task ObservePumpAsync(Task? pump)
    {
        if (pump is null)
        {
            return;
        }

        try
        {
            await pump.ConfigureAwait(false);
        }
        catch (OperationCanceledException)
        {
            // Cancellation is expected during shutdown.
        }
        catch (Exception)
        {
            // A pump failure must never prevent closing the Job Object and child process.
        }
    }

    private sealed class PendingResponse(string missionId, string invocationId)
    {
        public string MissionId { get; } = missionId;

        public string InvocationId { get; } = invocationId;

        public TaskCompletionSource<OperationResponse> Completion { get; } =
            new(TaskCreationOptions.RunContinuationsAsynchronously);
    }

    private static class ForegroundPermission
    {
        [DllImport("user32.dll", SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        public static extern bool AllowSetForegroundWindow(uint processId);
    }

}
