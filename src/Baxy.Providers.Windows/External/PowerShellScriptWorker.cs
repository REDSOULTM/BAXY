using System.ComponentModel;
using System.Diagnostics;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// Renew al máximo (rendimiento): a persistent Windows PowerShell that runs one helper script file over and over, the
/// way <see cref="UiaWorkerHost"/> runs the computer-use commands. Each call of the Spotify helper paid a PowerShell
/// start (about 240 ms on the notebook) and its Add-Type of UIAutomationClient and of its native class (about 250 ms
/// more); here the first call pays them and later ones find them loaded (Add-Type of the same source is a no-op).
/// <para>
/// It is an <see cref="IExternalProcessRunner"/>: a run of <c>powershell.exe -NoProfile -NonInteractive -STA -File
/// &lt;script&gt; …</c> for its own script goes to the worker, which invokes the file with the same arguments
/// (<c>-Name value</c> pairs by name, the rest by position) in its own script scope, so a run sees nothing of the one
/// before and its <c>exit</c> ends the run, not the worker. Its pipeline output comes back as the run's output and its
/// exit code as the run's; anything else, or a run while another is in progress, is run once in its own process
/// (<see cref="ExternalProcessRunner"/>), as before.
/// </para>
/// <para>
/// A run cut short (its budget, the caller's token) kills the worker at once, as the one-shot runner kills its child,
/// and never its tree: the client a script opened for the person (Spotify, started by <c>spotify:</c>) is theirs. The
/// next run starts a new worker; so does one after the worker died. The worker belongs to the Core's helper job
/// (<see cref="HelperProcessJob"/>), so it dies with the Core, and ends when its stdin closes.
/// </para>
/// </summary>
internal sealed class PowerShellScriptWorker : IExternalProcessRunner, IDisposable
{
    // The answer line of a run; every other line the worker writes (a script's Write-Host) is that run's output.
    internal const string AnswerMarker = "<<baxy-script-worker>>";

    // The arguments before the script that a run must carry to be the worker's (the worker starts with the same ones).
    private static readonly string[] WorkerFlags = ["-NoProfile", "-NonInteractive", "-STA"];

    private static readonly Regex ParameterName = new("^-[A-Za-z][A-Za-z0-9_]*$", RegexOptions.CultureInvariant);

    // One line per run on stdin (JSON: script, named, positional); the answer is the marker and one JSON line
    // (exit, output, error). The pipeline output is formatted as the console would show it (Out-String -Stream) and
    // collected as it comes, so what a script wrote before a terminating error is kept, as the console kept it. No
    // double quote in it: Windows PowerShell 5.1 mangles them in a -Command argument.
    private const string Loop = """
        [Console]::InputEncoding=[System.Text.UTF8Encoding]::new($false)
        [Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false)
        while($true){
            $line=[Console]::In.ReadLine()
            if($null -eq $line -or $line -eq 'exit'){break}
            $request=ConvertFrom-Json $line
            $named=@{}
            foreach($property in @($request.named.PSObject.Properties)){$named[$property.Name]=[string]$property.Value}
            $positional=@(foreach($value in @($request.positional)){[string]$value})
            $lines=New-Object 'System.Collections.Generic.List[string]'
            $code=0
            $failure=''
            $global:LASTEXITCODE=0
            try{
                & $request.script @named @positional 2>$null|Out-String -Stream -Width 4096|ForEach-Object {$lines.Add($_)}
                $code=$global:LASTEXITCODE
            }catch{
                $code=1
                $failure=[string]$_.Exception.Message
            }
            $answer=[ordered]@{exit=[int]$code;output=($lines -join [string][char]10);error=$failure}
            [Console]::Out.WriteLine('<<baxy-script-worker>>'+(ConvertTo-Json -Compress $answer))
            [Console]::Out.Flush()
        }
        """;

    private readonly string _script;
    private readonly IExternalProcessRunner _oneShot;
    private readonly SemaphoreSlim _gate = new(1, 1);
    private Process? _process;
    private bool _disposed;

    internal PowerShellScriptWorker(string script, IExternalProcessRunner? oneShot = null)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(script);
        _script = Path.GetFullPath(script);
        _oneShot = oneShot ?? new ExternalProcessRunner();
    }

    /// <summary>How many worker processes this runner has started (the tests count the starts it saves).</summary>
    internal int Starts { get; private set; }

    /// <summary>The worker's process id while it is up, else null.</summary>
    internal int? WorkerProcessId
    {
        get
        {
            try
            {
                return _process is { HasExited: false } process ? process.Id : null;
            }
            catch (InvalidOperationException)
            {
                return null;
            }
        }
    }

    public async ValueTask<ExternalProcessResult> RunAsync(
        string executable,
        IReadOnlyList<string> arguments,
        TimeSpan timeout,
        CancellationToken cancellationToken)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(executable);
        ArgumentNullException.ThrowIfNull(arguments);
        if (timeout <= TimeSpan.Zero || timeout > TimeSpan.FromMinutes(5))
            throw new ArgumentOutOfRangeException(nameof(timeout));
        if (_disposed || ToRequest(executable, arguments) is not { } request || !_gate.Wait(0, CancellationToken.None))
            return await _oneShot.RunAsync(executable, arguments, timeout, cancellationToken).ConfigureAwait(false);
        try
        {
            return await RunInWorkerAsync(request, timeout, cancellationToken).ConfigureAwait(false);
        }
        finally
        {
            _gate.Release();
        }
    }

    // The worker's request for a run of its own script with the worker's flags, or null for any other run.
    internal string? ToRequest(string executable, IReadOnlyList<string> arguments)
    {
        if (!string.Equals(Path.GetFileName(executable), "powershell.exe", StringComparison.OrdinalIgnoreCase)
            || arguments.Count < WorkerFlags.Length + 2
            || !arguments.Take(WorkerFlags.Length).SequenceEqual(WorkerFlags, StringComparer.OrdinalIgnoreCase)
            || !string.Equals(arguments[WorkerFlags.Length], "-File", StringComparison.OrdinalIgnoreCase))
            return null;
        string script;
        try
        {
            script = Path.GetFullPath(arguments[WorkerFlags.Length + 1]);
        }
        catch (Exception exception) when (exception is ArgumentException or NotSupportedException or PathTooLongException)
        {
            return null;
        }

        if (!string.Equals(script, _script, StringComparison.OrdinalIgnoreCase))
            return null;
        using var buffer = new MemoryStream();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            writer.WriteStartObject();
            writer.WriteString("script", _script);
            writer.WriteStartObject("named");
            var positional = new List<string>();
            for (int index = WorkerFlags.Length + 2; index < arguments.Count; index++)
            {
                string argument = arguments[index];
                if (ParameterName.IsMatch(argument) && index + 1 < arguments.Count)
                {
                    writer.WriteString(argument[1..], arguments[++index]);
                    continue;
                }

                // A switch (a name with no value after it) is not a run the worker binds the way -File does.
                if (ParameterName.IsMatch(argument))
                    return null;
                positional.Add(argument);
            }

            writer.WriteEndObject();
            writer.WriteStartArray("positional");
            foreach (string argument in positional)
                writer.WriteStringValue(argument);
            writer.WriteEndArray();
            writer.WriteEndObject();
        }

        return Encoding.UTF8.GetString(buffer.ToArray());
    }

    private async ValueTask<ExternalProcessResult> RunInWorkerAsync(
        string request, TimeSpan timeout, CancellationToken cancellationToken)
    {
        using var timeoutSource = new CancellationTokenSource(timeout);
        using var linked = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken, timeoutSource.Token);
        bool completed = false;
        try
        {
            Process process = EnsureStarted();
            await process.StandardInput.WriteLineAsync(request.AsMemory(), linked.Token).ConfigureAwait(false);
            await process.StandardInput.FlushAsync(linked.Token).ConfigureAwait(false);
            var stray = new StringBuilder();
            while (true)
            {
                string? line = await process.StandardOutput.ReadLineAsync(linked.Token).ConfigureAwait(false)
                    ?? throw new IOException("The PowerShell script worker ended before it answered.");
                if (line.StartsWith(AnswerMarker, StringComparison.Ordinal))
                {
                    using JsonDocument answer = JsonDocument.Parse(line.AsMemory(AnswerMarker.Length));
                    JsonElement root = answer.RootElement;
                    string output = stray.Append(root.GetProperty("output").GetString()).ToString();
                    if (output.Length > ExternalProcessRunner.MaximumCapturedCharacters)
                        throw new ExternalProcessOutputTooLargeException("External process output exceeded its bound.");
                    completed = true;
                    return new ExternalProcessResult(
                        root.GetProperty("exit").GetInt32(), output, root.GetProperty("error").GetString() ?? string.Empty);
                }

                stray.Append(line).Append('\n');
                if (stray.Length > ExternalProcessRunner.MaximumCapturedCharacters)
                    throw new ExternalProcessOutputTooLargeException("External process output exceeded its bound.");
            }
        }
        catch (OperationCanceledException)
        {
            if (cancellationToken.IsCancellationRequested)
                throw;
            throw new TimeoutException("powershell.exe exceeded its execution budget.");
        }
        catch (Exception exception) when (exception is JsonException or KeyNotFoundException or InvalidOperationException)
        {
            // An answer that is not the worker's cannot be resynchronised: the worker is replaced.
            throw new IOException("The PowerShell script worker answered something else.", exception);
        }
        finally
        {
            // A run that did not end with its answer leaves the worker mid-script (still pressing, or with its answer
            // in the pipe): it is killed at once, as the one-shot runner kills its child.
            if (!completed)
                Terminate();
        }
    }

    private Process EnsureStarted()
    {
        if (_process is { HasExited: false } running)
            return running;
        Terminate();
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
        foreach (string flag in WorkerFlags)
            start.ArgumentList.Add(flag);
        start.ArgumentList.Add("-Command");
        start.ArgumentList.Add(Loop);
        Process process;
        try
        {
            process = Process.Start(start) ?? throw new IOException("Could not start powershell.exe.");
        }
        catch (Win32Exception exception)
        {
            throw new IOException("Could not start powershell.exe.", exception);
        }

        HelperProcessJob.Assign(process);
        Starts++;
        // Drained in the background so a chatty script never blocks on a full pipe; the one-shot runner's stderr was
        // read by nobody either.
        _ = process.StandardError.ReadToEndAsync(CancellationToken.None);
        _process = process;
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
                process.Kill(entireProcessTree: false);
        }
        catch (Exception exception) when (exception is InvalidOperationException or Win32Exception
            or NotSupportedException or AggregateException)
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
        // A run in progress ends with the kill; the gate is left to it.
        Terminate();
    }
}
