using System.Diagnostics;
using System.Text;
using System.Text.Json;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// One request to the UI Automation worker and its answer. The view and click
/// adapters talk to the worker only through this seam so their tests can hand
/// them scripted answers.
/// </summary>
internal interface IUiaWorker
{
    /// <summary>
    /// Sends one JSON command line and returns the parsed answer, or null when
    /// the worker could not answer inside the budget (it is restarted then).
    /// </summary>
    ValueTask<JsonDocument?> SendAsync(
        string commandJson,
        TimeSpan timeout,
        CancellationToken cancellationToken);
}

/// <summary>
/// Persistent PowerShell worker for UI Automation (CONTRATO_VISTA_ACCION.md §1.6).
/// The previous scripts paid a process spawn and an Add-Type compilation on
/// every view or click; the worker pays them once and then answers one JSON
/// line per command. One command at a time; a worker that dies or stalls is
/// replaced on the next command, never trusted twice.
/// </summary>
internal sealed class UiaWorkerHost : IUiaWorker, IDisposable
{
    private static readonly TimeSpan StartupBudget = TimeSpan.FromSeconds(20);
    private readonly string _script;
    private readonly SemaphoreSlim _gate = new(1, 1);
    private Process? _process;
    private bool _disposed;

    internal UiaWorkerHost()
        : this(Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1"))
    {
    }

    internal UiaWorkerHost(string script)
    {
        _script = script ?? throw new ArgumentNullException(nameof(script));
    }

    internal bool ScriptExists => File.Exists(_script);

    public async ValueTask<JsonDocument?> SendAsync(
        string commandJson,
        TimeSpan timeout,
        CancellationToken cancellationToken)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(commandJson);
        ObjectDisposedException.ThrowIf(_disposed, this);
        await _gate.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            Process? process = await EnsureStartedAsync(cancellationToken).ConfigureAwait(false);
            if (process is null)
                return null;
            using var budget = new CancellationTokenSource(timeout);
            using var linked = CancellationTokenSource.CreateLinkedTokenSource(
                cancellationToken, budget.Token);
            try
            {
                await process.StandardInput.WriteLineAsync(commandJson.AsMemory(), linked.Token)
                    .ConfigureAwait(false);
                await process.StandardInput.FlushAsync(linked.Token).ConfigureAwait(false);
                string? line = await process.StandardOutput.ReadLineAsync(linked.Token)
                    .ConfigureAwait(false);
                if (line is null)
                {
                    Terminate();
                    return null;
                }

                return JsonDocument.Parse(line);
            }
            catch (Exception exception) when (exception is IOException or JsonException
                or InvalidOperationException
                || (exception is OperationCanceledException && !cancellationToken.IsCancellationRequested))
            {
                // A worker that stops answering, or answers something that is
                // not one JSON line, cannot be resynchronised: it is replaced.
                Terminate();
                return null;
            }
        }
        finally
        {
            _gate.Release();
        }
    }

    private async ValueTask<Process?> EnsureStartedAsync(CancellationToken cancellationToken)
    {
        if (_process is { HasExited: false })
            return _process;
        Terminate();
        if (!File.Exists(_script))
            return null;
        var start = new ProcessStartInfo("powershell.exe")
        {
            UseShellExecute = false,
            RedirectStandardInput = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true,
            StandardInputEncoding = new UTF8Encoding(false),
            StandardOutputEncoding = Encoding.UTF8,
            StandardErrorEncoding = Encoding.UTF8,
        };
        foreach (string argument in new[] { "-NoProfile", "-NonInteractive", "-STA", "-ExecutionPolicy", "Bypass", "-File", _script })
            start.ArgumentList.Add(argument);
        Process? process;
        try
        {
            process = Process.Start(start);
        }
        catch (Exception exception) when (exception is IOException or InvalidOperationException
            or System.ComponentModel.Win32Exception)
        {
            return null;
        }

        if (process is null)
            return null;
        // Drain stderr in the background so a chatty worker can never block on
        // a full pipe; nothing it says there is part of the protocol.
        _ = process.StandardError.ReadToEndAsync(CancellationToken.None);
        _process = process;
        using var budget = new CancellationTokenSource(StartupBudget);
        using var linked = CancellationTokenSource.CreateLinkedTokenSource(
            cancellationToken, budget.Token);
        try
        {
            await process.StandardInput.WriteLineAsync("{\"cmd\":\"ping\"}".AsMemory(), linked.Token)
                .ConfigureAwait(false);
            await process.StandardInput.FlushAsync(linked.Token).ConfigureAwait(false);
            string? hello = await process.StandardOutput.ReadLineAsync(linked.Token)
                .ConfigureAwait(false);
            if (hello is null || !hello.Contains("\"ok\":", StringComparison.Ordinal))
            {
                Terminate();
                return null;
            }
        }
        catch (Exception exception) when (exception is IOException or InvalidOperationException
            || (exception is OperationCanceledException && !cancellationToken.IsCancellationRequested))
        {
            Terminate();
            return null;
        }

        return process;
    }

    private void Terminate()
    {
        Process? process = _process;
        _process = null;
        if (process is null)
            return;
        try
        {
            if (!process.HasExited)
            {
                try
                {
                    process.StandardInput.WriteLine("{\"cmd\":\"exit\"}");
                    process.StandardInput.Flush();
                }
                catch (IOException)
                {
                }

                if (!process.WaitForExit(500))
                    process.Kill(entireProcessTree: true);
            }
        }
        catch (Exception exception) when (exception is InvalidOperationException
            or System.ComponentModel.Win32Exception or IOException)
        {
        }
        finally
        {
            process.Dispose();
        }
    }

    public void Dispose()
    {
        if (_disposed)
            return;
        _disposed = true;
        Terminate();
        _gate.Dispose();
    }
}
