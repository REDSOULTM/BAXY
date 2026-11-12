using System.Diagnostics;
using System.Text;
using System.Text.Json;

namespace Baxy.Providers.Windows.External;

/// <summary>What the hidden page reader answered for one page: its outcome, the HTTP status of the page when it
/// arrived, its markup, and the address it ended on.</summary>
internal sealed record HiddenPage(HiddenPageOutcome Outcome, int? HttpStatus, string Html)
{
    internal Uri? Final { get; init; }
}

internal enum HiddenPageOutcome
{
    Loaded,
    Failed,
    Timeout,
    Unavailable,
}

/// <summary>The pages a web search reads where nobody sees them; the adapter's tests hand it scripted pages.</summary>
internal interface IHiddenPageSource
{
    /// <summary>The page at the address, waited for within the time given; with a settle time, also the text its
    /// scripts draw after it arrived, until it stops changing or that time is up.</summary>
    Task<HiddenPage> ReadAsync(Uri address, TimeSpan within, TimeSpan settle, CancellationToken cancellationToken);
}

/// <summary>
/// SRCH1 (owner, 2026-11-07 17:35): a web search is read by the browser BAXY embeds, invisible, from the person's own
/// machine and address; never a window in front of them. baxy-core is NativeAOT and cannot host WebView2's COM objects,
/// so the App's executable is started in its reader mode («Baxy.exe --hidden-page-reader &lt;folder&gt;»,
/// Baxy.App.HiddenPageReader) and asked one JSON line per page, as the UI Automation worker is (UiaWorkerHost): one page
/// at a time, a reader that stops answering is replaced, never trusted twice, and it dies with the Core
/// (HelperProcessJob). Its WebView2 folder is the Core's own («webview2-search» in the data root), apart from the
/// window's: what a search page keeps is never the view's. After a while unused it is ended, and started again by the
/// next search.
/// </summary>
internal sealed class HiddenPageReaderHost : IHiddenPageSource, IDisposable
{
    internal const string ExecutableOverride = "BAXY_HIDDEN_PAGE_READER";
    private static readonly TimeSpan StartupBudget = TimeSpan.FromSeconds(20);
    private static readonly TimeSpan AnswerMargin = TimeSpan.FromSeconds(5);
    private static readonly TimeSpan IdleEnd = TimeSpan.FromMinutes(10);
    // INT10: the reader's folder holds only what the pages it read left (no sign-in, nothing of the person), and nothing
    // of BAXY bounded it: Chromium caps each of its caches by itself, on Windows up to 4 × 80 MiB for the HTTP cache and
    // as much again for scripts' code (net/disk_cache/cache_util.cc, kDefaultCacheSize and size_limit; read 2026-11-07),
    // and a site's own storage up to its quota. Measured: 84 MB after ~70 reads (SRCH1), +1 MB a read (INT10). Past this
    // cap, Chromium's own default size of one cache (80 MiB) plus a fresh folder (~20 MB, INT10), it is emptied before a
    // reader starts on it.
    internal const long ProfileCap = 100L * 1024 * 1024;
    private readonly string? _executable;
    private readonly string _userDataFolder;
    private readonly SemaphoreSlim _gate = new(1, 1);
    private readonly Timer _idle;
    private Process? _process;
    private bool _disposed;

    internal HiddenPageReaderHost(string dataRoot)
        : this(FindExecutable(AppContext.BaseDirectory), Path.Combine(dataRoot, "webview2-search"))
    {
    }

    internal HiddenPageReaderHost(string? executable, string userDataFolder)
    {
        _executable = executable;
        _userDataFolder = userDataFolder ?? throw new ArgumentNullException(nameof(userDataFolder));
        _idle = new Timer(_ => EndIfIdle(), null, Timeout.Infinite, Timeout.Infinite);
    }

    /// <summary>The App's executable beside the Core (a development build) or one folder up (the product's «core»
    /// folder); a measurement fixture of a test build may name another (BAXY_HIDDEN_PAGE_READER). Null when there is none.</summary>
    internal static string? FindExecutable(string coreDirectory)
    {
#if DEBUG
        // APP2 (REV10 S2): only a test build (Debug) runs the executable the variable names; the product's is Release.
        string? named = Environment.GetEnvironmentVariable(ExecutableOverride);
        if (!string.IsNullOrWhiteSpace(named))
            return File.Exists(named) ? named : null;
#endif
        foreach (string candidate in new[]
                 {
                     Path.Combine(coreDirectory, "Baxy.exe"),
                     Path.Combine(coreDirectory, "..", "Baxy.exe"),
                 })
        {
            if (File.Exists(candidate))
                return Path.GetFullPath(candidate);
        }
        return null;
    }

    public async Task<HiddenPage> ReadAsync(
        Uri address, TimeSpan within, TimeSpan settle, CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(address);
        ObjectDisposedException.ThrowIf(_disposed, this);
        await _gate.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            _idle.Change(Timeout.Infinite, Timeout.Infinite);
            Process? process = await EnsureStartedAsync(cancellationToken).ConfigureAwait(false);
            if (process is null)
                return new(HiddenPageOutcome.Unavailable, null, string.Empty);
            using var budget = new CancellationTokenSource(within + settle + AnswerMargin);
            using var linked = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken, budget.Token);
            try
            {
                await process.StandardInput.WriteLineAsync(Request(address, within, settle).AsMemory(), linked.Token)
                    .ConfigureAwait(false);
                await process.StandardInput.FlushAsync(linked.Token).ConfigureAwait(false);
                string? line = await process.StandardOutput.ReadLineAsync(linked.Token).ConfigureAwait(false);
                if (line is null)
                {
                    Terminate();
                    return new(HiddenPageOutcome.Unavailable, null, string.Empty);
                }
                return Parse(line);
            }
            catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
            {
                // The answer left in the pipe would be read as the next page's: the reader is replaced.
                Terminate();
                throw;
            }
            catch (Exception exception) when (exception is IOException or JsonException or InvalidOperationException
                || exception is OperationCanceledException)
            {
                Terminate();
                return new(HiddenPageOutcome.Timeout, null, string.Empty);
            }
        }
        finally
        {
            if (!_disposed)
                _idle.Change(IdleEnd, Timeout.InfiniteTimeSpan);
            _gate.Release();
        }
    }

    internal static string Request(Uri address, TimeSpan within, TimeSpan settle)
    {
        using var buffer = new MemoryStream();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            writer.WriteStartObject();
            writer.WriteString("url", address.AbsoluteUri);
            writer.WriteNumber("withinMs", (long)within.TotalMilliseconds);
            if (settle > TimeSpan.Zero)
                writer.WriteNumber("settleMs", (long)settle.TotalMilliseconds);
            writer.WriteEndObject();
        }
        return Encoding.UTF8.GetString(buffer.ToArray());
    }

    internal static HiddenPage Parse(string line)
    {
        using JsonDocument answer = JsonDocument.Parse(line);
        JsonElement root = answer.RootElement;
        HiddenPageOutcome outcome = root.GetProperty("outcome").GetString() switch
        {
            "loaded" => HiddenPageOutcome.Loaded,
            "timeout" => HiddenPageOutcome.Timeout,
            "unavailable" => HiddenPageOutcome.Unavailable,
            _ => HiddenPageOutcome.Failed,
        };
        int? status = root.TryGetProperty("httpStatus", out JsonElement code) && code.TryGetInt32(out int value)
            ? value
            : null;
        string html = root.TryGetProperty("html", out JsonElement markup) ? markup.GetString() ?? string.Empty : string.Empty;
        Uri? final = root.TryGetProperty("final", out JsonElement ended)
            && Uri.TryCreate(ended.GetString(), UriKind.Absolute, out Uri? address) ? address : null;
        return new(outcome, status, html) { Final = final };
    }

    private async Task<Process?> EnsureStartedAsync(CancellationToken cancellationToken)
    {
        if (_process is { HasExited: false })
            return _process;
        Terminate();
        if (_executable is null || !File.Exists(_executable))
            return null;
        var start = new ProcessStartInfo(_executable)
        {
            UseShellExecute = false,
            RedirectStandardInput = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true,
            StandardInputEncoding = new UTF8Encoding(false),
            StandardOutputEncoding = Encoding.UTF8,
            StandardErrorEncoding = Encoding.UTF8,
            WorkingDirectory = Path.GetDirectoryName(_executable) ?? Environment.SystemDirectory,
        };
        start.ArgumentList.Add("--hidden-page-reader");
        start.ArgumentList.Add(_userDataFolder);
        EmptyPastCap(_userDataFolder);
        Process? process;
        try
        {
            process = Process.Start(start);
            HelperProcessJob.Assign(process);
        }
        catch (Exception exception) when (exception is IOException or InvalidOperationException
            or System.ComponentModel.Win32Exception)
        {
            return null;
        }
        if (process is null)
            return null;
        _ = process.StandardError.ReadToEndAsync(CancellationToken.None);
        _process = process;
        using var budget = new CancellationTokenSource(StartupBudget);
        using var linked = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken, budget.Token);
        try
        {
            await process.StandardInput.WriteLineAsync("{\"cmd\":\"ping\"}".AsMemory(), linked.Token).ConfigureAwait(false);
            await process.StandardInput.FlushAsync(linked.Token).ConfigureAwait(false);
            string? hello = await process.StandardOutput.ReadLineAsync(linked.Token).ConfigureAwait(false);
            // A reader without WebView2 says so («ok»: false): no page can be read on this machine now.
            if (hello is null || !hello.Contains("\"ok\":true", StringComparison.Ordinal))
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
        catch (OperationCanceledException)
        {
            Terminate();
            throw;
        }
        return process;
    }

    // The folder past ProfileCap loses all it holds before a reader of this host starts on it (the one before was waited
    // for, or its tree killed and waited for); a file its browser processes still hold stays for the next start, and
    // Chromium builds again what it misses. Links are not followed.
    internal static void EmptyPastCap(string folder)
    {
        var walk = new EnumerationOptions
        {
            RecurseSubdirectories = true,
            AttributesToSkip = FileAttributes.ReparsePoint,
            IgnoreInaccessible = true,
        };
        try
        {
            var root = new DirectoryInfo(folder);
            if (!root.Exists || root.EnumerateFiles("*", walk).Sum(file => file.Length) <= ProfileCap)
                return;
            foreach (FileSystemInfo entry in root.EnumerateFileSystemInfos())
            {
                try
                {
                    if (entry is DirectoryInfo directory && !entry.Attributes.HasFlag(FileAttributes.ReparsePoint))
                        directory.Delete(recursive: true);
                    else
                        entry.Delete();
                }
                catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
                {
                }
            }
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException
            or System.Security.SecurityException)
        {
        }
    }

    private void EndIfIdle()
    {
        if (_disposed || !_gate.Wait(0))
            return;
        try
        {
            Terminate();
        }
        finally
        {
            _gate.Release();
        }
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
                // The reader and its WebView2 processes: nothing of it opens anything for the person.
                if (!process.WaitForExit(2000))
                {
                    process.Kill(entireProcessTree: true);
                    process.WaitForExit(2000);
                }
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
        _idle.Dispose();
        Terminate();
        _gate.Dispose();
    }
}
