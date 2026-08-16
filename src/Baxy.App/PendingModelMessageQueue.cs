using System.Text.Json.Nodes;

namespace Baxy.App;

/// <summary>
/// Cola de respuestas ya verificadas que todavía no tienen texto redactado por el
/// modelo. Mantiene el orden, reintenta con espera creciente mientras la mente no
/// esté lista y entrega cada texto aceptado una sola vez.
///
/// No conoce la ventana ni el turno: recibe delegados para esperar a la mente,
/// publicar el resultado y anotar el fallo de composición.
/// </summary>
internal sealed class PendingModelMessageQueue
{
    private readonly object _lock = new();
    private readonly Queue<PendingModelMessage> _pending = new();
    private readonly Func<CancellationToken, Task<MindSidecarClient?>> _waitForMind;
    private readonly Func<string, string?, Task> _publishAsync;
    private readonly Func<string?, Task> _reportFailureAsync;
    private readonly Action _onQueued;
    private Task? _worker;
    private bool _isClosed;

    internal PendingModelMessageQueue(
        Func<CancellationToken, Task<MindSidecarClient?>> waitForMind,
        Func<string, string?, Task> publishAsync,
        Func<string?, Task> reportFailureAsync,
        Action onQueued)
    {
        ArgumentNullException.ThrowIfNull(waitForMind);
        ArgumentNullException.ThrowIfNull(publishAsync);
        ArgumentNullException.ThrowIfNull(reportFailureAsync);
        ArgumentNullException.ThrowIfNull(onQueued);
        _waitForMind = waitForMind;
        _publishAsync = publishAsync;
        _reportFailureAsync = reportFailureAsync;
        _onQueued = onQueued;
    }

    internal int Count
    {
        get
        {
            lock (_lock)
            {
                return _pending.Count;
            }
        }
    }

    internal void Enqueue(PendingModelMessage pending, CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(pending);
        lock (_lock)
        {
            if (_isClosed)
            {
                return;
            }

            _pending.Enqueue(pending);
            if (_worker is null || _worker.IsCompleted)
            {
                _worker = Task.Run(() => DrainAsync(cancellationToken), CancellationToken.None);
            }
        }

        _onQueued();
    }

    /// <summary>Cierra la cola y espera a que el trabajador en curso termine.</summary>
    internal async Task CloseAsync()
    {
        Task? worker;
        lock (_lock)
        {
            _isClosed = true;
            worker = _worker;
        }

        if (worker is null)
        {
            return;
        }

        try
        {
            await worker.ConfigureAwait(false);
        }
        catch (OperationCanceledException)
        {
            // El cierre cancela el trabajador a propósito.
        }
    }

    private async Task DrainAsync(CancellationToken cancellationToken)
    {
        while (!cancellationToken.IsCancellationRequested)
        {
            PendingModelMessage? pending;
            lock (_lock)
            {
                pending = _pending.Count > 0 ? _pending.Peek() : null;
            }

            if (pending is null)
            {
                return;
            }

            MindSidecarClient? mind = await _waitForMind(cancellationToken).ConfigureAwait(false);
            if (mind is null)
            {
                await Task.Delay(TimeSpan.FromSeconds(1), cancellationToken).ConfigureAwait(false);
                continue;
            }

            if (pending.Attempts > 0)
            {
                int delaySeconds = Math.Min(10, 1 << Math.Min(3, pending.Attempts - 1));
                await Task.Delay(TimeSpan.FromSeconds(delaySeconds), cancellationToken)
                    .ConfigureAwait(false);
            }

            ModelMessageCompositionOutcome outcome =
                await ComposeAsync(pending, mind, cancellationToken).ConfigureAwait(false);
            if (outcome.Text is null)
            {
                pending.Attempts++;
                await _reportFailureAsync(outcome.Failure).ConfigureAwait(false);
                continue;
            }

            lock (_lock)
            {
                if (_pending.Count > 0 && ReferenceEquals(_pending.Peek(), pending))
                {
                    _pending.Dequeue();
                }
            }

            await _publishAsync(outcome.Text, outcome.Failure).ConfigureAwait(false);
        }
    }

    private static async Task<ModelMessageCompositionOutcome> ComposeAsync(
        PendingModelMessage pending,
        MindSidecarClient mind,
        CancellationToken cancellationToken)
    {
        ShellTraceSink.Record(
            ShellTraceScopes.Turn,
            pending.TraceId,
            ShellTraceStages.ComposeStart,
            pending.Draft.Intent);
        try
        {
            return await ModelMessageComposer.ComposeAsync(
                pending.Draft,
                pending.UserText,
                pending.Facts,
                mind.ComposeUserMessageAsync,
                MindSidecarClient.IsCpuFallbackProfile,
                allowRecovery: true,
                cancellationToken).ConfigureAwait(false);
        }
        catch (Exception exception) when (ModelMessageComposer.IsTransientFailure(exception))
        {
            return new ModelMessageCompositionOutcome(
                null,
                "composer_request_failed",
                UsedRecovery: false);
        }
        finally
        {
            ShellTraceSink.Record(
                ShellTraceScopes.Turn,
                pending.TraceId,
                ShellTraceStages.ComposeEnd);
        }
    }
}

/// <summary>Una respuesta verificada a la espera de su texto redactado.</summary>
internal sealed record PendingModelMessage(
    UserMessageDraft Draft,
    string UserText,
    JsonObject Facts,
    string TraceId)
{
    public int Attempts { get; set; }
}
