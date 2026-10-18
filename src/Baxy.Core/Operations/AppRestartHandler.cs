using System.Buffers;
using System.Diagnostics;
using System.Text.Json;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Applications;
using Baxy.Providers.Windows.Windows;

namespace Baxy.Core.Operations;

/// <summary>
/// app.restart (auditoría de los pedidos reales, 2026-10-17): restarting an application had no operation of its own, and
/// the only one that said «restart» was system.power, which goes without the person's yes: a request about an app read
/// as the PC would have restarted the PC. The application's windows are closed gracefully, one by one, as app.close
/// does (never forced; a window that answers with a dialog of its own, such as asking to save, stops everything and is
/// said); then its processes must end on their own (an application that keeps running hidden is said, not killed);
/// then it is opened again by app.open, with all of app.open's verification, and only a process that is not one of the
/// closed ones counts as the restart.
/// </summary>
internal sealed class AppRestartHandler : IOperationHandler
{
    internal static readonly TimeSpan ExitWait = TimeSpan.FromSeconds(10);

    private readonly IWindowControlProvider _windows;
    private readonly Func<OperationInvocation, CancellationToken, ValueTask<OperationOutcome>> _open;
    private readonly Func<int, TimeSpan, CancellationToken, ValueTask<bool>> _exited;

    internal AppRestartHandler(
        IWindowControlProvider windows,
        Func<OperationInvocation, CancellationToken, ValueTask<OperationOutcome>> open,
        Func<int, TimeSpan, CancellationToken, ValueTask<bool>>? exited = null)
    {
        _windows = windows ?? throw new ArgumentNullException(nameof(windows));
        _open = open ?? throw new ArgumentNullException(nameof(open));
        _exited = exited ?? ProcessExitedAsync;
    }

    public OperationDefinition Definition { get; } = ProductCatalog.CreateDefinition("app.restart");

    public async ValueTask<OperationOutcome> ExecuteAsync(
        OperationInvocation invocation,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        if (invocation.Arguments.ValueKind != JsonValueKind.Object
            || !invocation.Arguments.TryGetProperty("appId", out JsonElement appIdValue)
            || appIdValue.ValueKind != JsonValueKind.String
            || appIdValue.GetString() is not { } requested
            || !ApplicationIds.IsValidRequest(requested))
        {
            return OperationOutcome.Failure("invalid_arguments");
        }

        string appId = requested;
        ApplicationWindowsClosed closing = await ApplicationWindowCloser.CloseAllAsync(_windows, appId, cancellationToken)
            .ConfigureAwait(false);
        var closedProcesses = new SortedSet<int>(closing.ProcessIds);
        int closedWindows = closing.ClosedWindows;
        if (closing.ErrorCode is { } stopped)
        {
            // Nothing of the application to close (not running, or its windows not read): nothing happened. Otherwise
            // it stopped while closing (a dialog of its own, such as saving; a close that failed): said, never reopened.
            return closing.Frames == 0
                ? OperationOutcome.Failure(stopped)
                : OperationOutcome.Failure(
                    stopped,
                    Receipt(appId, closedWindows, closedProcesses, stillRunning: [], reopened: null),
                    effectMayHaveOccurred: closing.EffectMayHaveOccurred);
        }

        var stillRunning = new List<int>();
        foreach (int processId in closedProcesses)
        {
            if (!await _exited(processId, ExitWait, cancellationToken).ConfigureAwait(false))
            {
                stillRunning.Add(processId);
            }
        }

        if (stillRunning.Count > 0)
        {
            // Its windows are closed but the application keeps running (hidden, in the notification area): reopening
            // would only show it again, which is not a restart, and ending it by force is not this operation's.
            return OperationOutcome.Failure(
                "app_kept_running",
                Receipt(appId, closedWindows, closedProcesses, stillRunning, reopened: null),
                effectMayHaveOccurred: true);
        }

        OperationOutcome opened = await _open(
            new OperationInvocation(
                invocation.RequestId,
                invocation.MissionId,
                invocation.InvocationId + ":open",
                JsonSerializer.SerializeToElement(
                    new OpenApplicationArguments(appId, ForControl: false, Foreground: true),
                    CoreJsonContext.Default.OpenApplicationArguments)),
            cancellationToken).ConfigureAwait(false);
        if (!opened.Succeeded || !opened.Verified || opened.Result is not { ValueKind: JsonValueKind.Object } facts)
        {
            return OperationOutcome.Failure(
                opened.ErrorCode ?? "app_reopen_failed",
                Receipt(appId, closedWindows, closedProcesses, stillRunning, reopened: null),
                effectMayHaveOccurred: true,
                causeCode: "app_reopen_failed");
        }

        bool alreadyRunning = facts.TryGetProperty("alreadyRunning", out JsonElement already)
            && already.ValueKind == JsonValueKind.True;
        int newProcess = facts.TryGetProperty("processId", out JsonElement pid) && pid.TryGetInt32(out int id) ? id : 0;
        if (alreadyRunning || newProcess == 0 || closedProcesses.Contains(newProcess))
        {
            // What app.open verified is a process that was already there: the application came back, it did not start
            // again.
            return OperationOutcome.Failure(
                "app_restart_not_verified",
                Receipt(appId, closedWindows, closedProcesses, stillRunning, facts),
                effectMayHaveOccurred: true);
        }

        return OperationOutcome.Success(Receipt(appId, closedWindows, closedProcesses, stillRunning, facts));
    }

    private static async ValueTask<bool> ProcessExitedAsync(int processId, TimeSpan wait, CancellationToken token)
    {
        Process process;
        try
        {
            process = Process.GetProcessById(processId);
        }
        catch (ArgumentException)
        {
            return true;
        }

        using (process)
        {
            using var timeout = CancellationTokenSource.CreateLinkedTokenSource(token);
            timeout.CancelAfter(wait);
            try
            {
                await process.WaitForExitAsync(timeout.Token).ConfigureAwait(false);
                return true;
            }
            catch (OperationCanceledException) when (!token.IsCancellationRequested)
            {
                return false;
            }
            catch (InvalidOperationException)
            {
                return true;
            }
        }
    }

    private static JsonElement Receipt(
        string appId,
        int closedWindows,
        IEnumerable<int> closedProcesses,
        List<int> stillRunning,
        JsonElement? reopened)
    {
        var buffer = new ArrayBufferWriter<byte>();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("appId", appId);
            writer.WriteNumber("closedWindows", closedWindows);
            writer.WriteStartArray("previousProcessIds");
            foreach (int id in closedProcesses)
                writer.WriteNumberValue(id);
            writer.WriteEndArray();
            if (stillRunning.Count > 0)
            {
                writer.WriteStartArray("stillRunningProcessIds");
                foreach (int id in stillRunning)
                    writer.WriteNumberValue(id);
                writer.WriteEndArray();
            }

            writer.WriteBoolean("reopened", reopened is not null);
            if (reopened is { } opened)
            {
                writer.WritePropertyName("opened");
                opened.WriteTo(writer);
            }

            writer.WriteString("authority", "window_close_absence_process_exit_app_open");
            writer.WriteEndObject();
        }

        using JsonDocument document = JsonDocument.Parse(buffer.WrittenMemory);
        return document.RootElement.Clone();
    }
}
