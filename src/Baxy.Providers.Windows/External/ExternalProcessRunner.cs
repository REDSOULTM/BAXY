using System.ComponentModel;
using System.Diagnostics;
using System.Text;

namespace Baxy.Providers.Windows.External;

internal sealed record ExternalProcessResult(int ExitCode, string Output, string Error);

internal interface IExternalProcessRunner
{
    ValueTask<ExternalProcessResult> RunAsync(
        string executable,
        IReadOnlyList<string> arguments,
        TimeSpan timeout,
        CancellationToken cancellationToken);
}

internal sealed class ExternalProcessRunner : IExternalProcessRunner
{
    internal const int MaximumCapturedCharacters = 1024 * 1024;
    private const int CaptureChunkCharacters = 8 * 1024;

    public async ValueTask<ExternalProcessResult> RunAsync(
        string executable,
        IReadOnlyList<string> arguments,
        TimeSpan timeout,
        CancellationToken cancellationToken)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(executable);
        ArgumentNullException.ThrowIfNull(arguments);
        if (timeout <= TimeSpan.Zero || timeout > TimeSpan.FromMinutes(5))
        {
            throw new ArgumentOutOfRangeException(nameof(timeout));
        }

        var start = new ProcessStartInfo(executable)
        {
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true,
            StandardOutputEncoding = Encoding.UTF8,
            StandardErrorEncoding = Encoding.UTF8,
        };
        foreach (string argument in arguments)
        {
            start.ArgumentList.Add(argument);
        }

        using Process process = Process.Start(start)
            ?? throw new IOException($"Could not start {executable}.");
        using var timeoutSource = new CancellationTokenSource(timeout);
        using var linked = CancellationTokenSource.CreateLinkedTokenSource(
            cancellationToken,
            timeoutSource.Token);
        bool completed = false;
        try
        {
            Task<string> output = CaptureAsync(process, process.StandardOutput, linked.Token);
            Task<string> error = CaptureAsync(process, process.StandardError, linked.Token);
            await process.WaitForExitAsync(linked.Token).ConfigureAwait(false);
            string capturedOutput = await output.ConfigureAwait(false);
            string capturedError = await error.ConfigureAwait(false);
            completed = true;
            return new ExternalProcessResult(process.ExitCode, capturedOutput, capturedError);
        }
        catch (OperationCanceledException)
        {
            if (cancellationToken.IsCancellationRequested)
            {
                throw;
            }
            throw new TimeoutException($"{executable} exceeded its execution budget.");
        }
        finally
        {
            if (!completed)
            {
                TryTerminate(process);
            }
        }
    }

    /// <summary>
    /// Captures one stream under its bound and terminates the child as soon as the
    /// bound is exceeded. Killing there is what unblocks a child that is stuck
    /// writing into a pipe nobody drains any more, so the caller observes the
    /// overflow instead of waiting for the execution budget to expire.
    /// </summary>
    private static async Task<string> CaptureAsync(
        Process process,
        TextReader reader,
        CancellationToken cancellationToken)
    {
        try
        {
            return await ReadBoundedAsync(reader, MaximumCapturedCharacters, cancellationToken)
                .ConfigureAwait(false);
        }
        catch (IOException)
        {
            TryTerminate(process);
            throw;
        }
    }

    /// <summary>
    /// Reads at most <paramref name="maximumCharacters"/> characters and fails as
    /// soon as the stream goes past them, so a runaway child cannot be
    /// materialised in full before its bound is applied.
    /// </summary>
    internal static async Task<string> ReadBoundedAsync(
        TextReader reader,
        int maximumCharacters,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(reader);
        ArgumentOutOfRangeException.ThrowIfNegativeOrZero(maximumCharacters);

        var captured = new StringBuilder();
        char[] chunk = new char[CaptureChunkCharacters];
        while (true)
        {
            int read = await reader.ReadAsync(chunk.AsMemory(), cancellationToken)
                .ConfigureAwait(false);
            if (read == 0)
            {
                return captured.ToString();
            }

            if (captured.Length + read > maximumCharacters)
            {
                throw new IOException("External process output exceeded its bound.");
            }

            captured.Append(chunk, 0, read);
        }
    }

    private static void TryTerminate(Process process)
    {
        try
        {
            if (!process.HasExited)
            {
                process.Kill(entireProcessTree: true);
            }
        }
        catch (Exception exception) when (exception is InvalidOperationException
            or Win32Exception
            or NotSupportedException
            or AggregateException)
        {
            // The child is already gone or is no longer reachable; the caller still
            // receives the failure that triggered the termination attempt.
        }
    }
}
