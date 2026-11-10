using System.IO;
using System.Net.Http;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Installer;

namespace Baxy.App;

/// <summary>
/// QWB2 (documentacion/PLAN_QWEN_BASE.md §4): BAXY's tuned model, which the package offers (MindRuntimeDiscovery.TunedOffer)
/// and does not carry since the owner's order of 2026-11-07. Settings → Model downloads it only when the person presses
/// Install: the installer's resumable download (PartFetcher, «Range») into &lt;data&gt;\models\&lt;file&gt;.part, renamed only once
/// its SHA-256 is the one the package's registration names. «Use it» points the mind's model at it the way ExternalModel
/// points the mind at its translator (Replace, and Stop puts back what was there), and the mind is relaunched
/// (MainWindowViewModel.SwitchMindAsync). Every start verifies it again; missing or damaged, the mind stays on the stock model
/// and Settings says why. Remove deletes it. Nothing here reads or changes what the model answers.
/// </summary>
internal sealed class TunedModel : IDisposable
{
    internal const string GgufVariable = "BAXY_MIND_LLM_GGUF";
    // Beyond its bytes: the hash cache and the configuration, and a disk not filled to its last byte.
    private const long Headroom = 64L << 20;

    private readonly string _root;
    private readonly Func<TunedModelOffer?> _offer;
    private readonly Func<string, long> _freeBytes;
    private readonly TimeSpan? _retryDelay;
    private readonly HttpClient _http;
    private readonly Dictionary<string, string?> _replaced = [];
    private readonly Lock _replacedLock = new();
    private readonly DownloadRate _rate = new();
    private readonly object _sync = new();
    private string? _applied;
    private CancellationTokenSource? _download;
    private long _downloaded;

    internal TunedModel(
        string dataRoot,
        Func<TunedModelOffer?> offer,
        TimeSpan? retryDelay = null,
        Func<string, long>? freeBytes = null)
    {
        _root = dataRoot;
        _offer = offer;
        _retryDelay = retryDelay;
        _freeBytes = freeBytes ?? FreeBytes;
        // No overall timeout: PartFetcher cuts a download that stalls, and 2.7 GB take what the line takes.
        _http = new HttpClient { Timeout = Timeout.InfiniteTimeSpan };
        _http.DefaultRequestHeaders.UserAgent.ParseAdd("BAXY");
    }

    /// <summary>The download reached a server: its host, for «Salidas a internet».</summary>
    internal event Action<string>? WentOnline;

    /// <summary>A download finished and verified, on a pool thread: the mind may have to switch to it (the person chose it).</summary>
    internal event Action? Installed;

    /// <summary>The mind runs on the tuned model.</summary>
    internal bool Active { get; private set; }

    /// <summary>Why the last start stayed on the stock model although the person chose this one, or null.</summary>
    internal string? Problem { get; private set; }

    /// <summary>The last download's failure, or null.</summary>
    internal string? DownloadProblem { get; private set; }

    /// <summary>The download running now, or null.</summary>
    internal Task? Installing { get; private set; }

    /// <summary>What the person has chosen is not what the running mind was started with.</summary>
    internal bool NeedsSwitch => _applied is not null && Choice() != _applied;

    private string Folder => Path.Combine(_root, "tuned-model");

    private string ConfigPath => Path.Combine(Folder, "config.json");

    private string? FilePath => _offer() is { } offer ? Path.Combine(_root, "models", offer.File) : null;

    private bool Downloading => Installing is { IsCompleted: false };

    /// <summary>The stock model's file: the mind's own (<see cref="GgufVariable"/>) as it was before this one took its place,
    /// whichever runs now (MOD1 V-07: the stock model's row says its size with the tuned one in use too).</summary>
    internal string? StockPath
    {
        get
        {
            lock (_replacedLock)
            {
                return _replaced.TryGetValue(GgufVariable, out string? before) ? before : Environment.GetEnvironmentVariable(GgufVariable);
            }
        }
    }

    /// <summary>This model's file once it is installed (as <see cref="Json"/> says it), or null.</summary>
    internal string? InstalledPath => FilePath is { } path && IsThere(path, Config()) ? path : null;

    // One the person asked to remove is gone for them, though a closing server may hold it a moment longer.
    private bool IsThere(string path, JsonObject config) =>
        File.Exists(path) && Problem != "ajustado_danado" && (bool?)config["remove"] != true;

    internal JsonObject Json()
    {
        TunedModelOffer? offer = _offer();
        if (offer is null)
        {
            return new JsonObject { ["available"] = false };
        }

        string path = FilePath!;
        JsonObject config = Config();
        bool downloading = Downloading;
        bool installed = IsThere(path, config);
        return new JsonObject
        {
            ["available"] = true,
            ["file"] = offer.File,
            ["bytes"] = offer.Bytes,
            ["license"] = offer.License,
            ["source"] = new Uri(offer.Url).Host,
            // Its repository on Hugging Face, as the notice before the download names it: the first two parts of the path.
            ["repo"] = string.Concat(new Uri(offer.Url).Segments.Skip(1).Take(2)).TrimEnd('/'),
            ["installed"] = installed,
            ["use"] = (bool?)config["use"] == true,
            ["active"] = Active,
            ["problem"] = Problem,
            ["downloading"] = downloading,
            ["downloadedBytes"] = downloading ? Interlocked.Read(ref _downloaded) : PartBytes(path),
            // D6: how fast it goes and how long it has left, as a model's download says them (OpenModels).
            ["downloadBytesPerSecond"] = downloading ? _rate.BytesPerSecond : null,
            ["downloadSecondsLeft"] = downloading ? _rate.SecondsLeft(offer.Bytes) : null,
            ["downloadProblem"] = downloading ? null : DownloadProblem,
            ["needBytes"] = offer.Bytes + Headroom,
        };
    }

    /// <summary>What the panel asks: use it or not, remove it, or stop the download. The refusal's code, or null.</summary>
    internal string? Apply(JsonObject body)
    {
        if (_offer() is null)
        {
            return "tuned_model_unavailable";
        }

        JsonObject config = Config();
        if ((bool?)body["cancel"] == true)
        {
            _download?.Cancel();
        }

        if ((bool?)body["remove"] == true)
        {
            _download?.Cancel();
            config["use"] = false;
            config["remove"] = true;
            Save(config);
            RemoveIfAsked();
            return null;
        }

        if ((bool?)body["use"] is { } use)
        {
            if (use && !File.Exists(FilePath))
            {
                return "tuned_model_not_installed";
            }

            config["use"] = use;
            config.Remove("remove");
            Save(config);
        }

        return null;
    }

    /// <summary>
    /// Starts the download the person asked for, with its refusal's code when it cannot start. What a cut download left in
    /// the «.part» is kept, and the next Install goes on from there.
    /// </summary>
    internal string? Install(CancellationToken lifetime)
    {
        TunedModelOffer? offer = _offer();
        if (offer is null)
        {
            return "tuned_model_unavailable";
        }

        lock (_sync)
        {
            if (Downloading)
            {
                return null;
            }

            string path = FilePath!;
            // REV_APP TUN-a: asked for again while its removal was still pending (the closing server maps the file, and the
            // view already says «Sin instalar»), the removal is taken back: left pending, the next start deleted the model
            // just asked for. The file that never went is the one installed; each start checks it as always.
            JsonObject config = Config();
            if ((bool?)config["remove"] == true)
            {
                config.Remove("remove");
                Save(config);
                if (IsThere(path, config))
                {
                    return null;
                }
            }

            Directory.CreateDirectory(Path.GetDirectoryName(path)!);
            if (_freeBytes(path) < offer.Bytes - PartBytes(path) + Headroom)
            {
                DownloadProblem = "sin_espacio";
                return "tuned_model_no_space";
            }

            // A damaged one is not kept: it would never verify. The mind runs the stock model and goes on with it: a file it
            // does not load is no change for it.
            if (File.Exists(path))
            {
                try
                {
                    File.Delete(path);
                }
                catch (Exception held) when (held is IOException or UnauthorizedAccessException)
                {
                    // still mapped by a server that is closing, or held by another program: asked again in a moment, it goes
                    return "tuned_model_file_busy";
                }

                if (!Active && _applied is not null)
                {
                    _applied = Choice();
                }
            }

            // Missing or damaged, it is being installed again now.
            Problem = null;
            DownloadProblem = null;
            _download?.Dispose();
            _download = CancellationTokenSource.CreateLinkedTokenSource(lifetime);
            // PartFetcher's first report is what the «.part» already holds: the speed is counted from there.
            Interlocked.Exchange(ref _downloaded, 0);
            _rate.Reset();
            WentOnline?.Invoke(new Uri(offer.Url).Host);
            Installing = DownloadAsync(offer, path, _download.Token);
            return null;
        }
    }

    private async Task DownloadAsync(TunedModelOffer offer, string path, CancellationToken cancellation)
    {
        await Task.Yield();
        string part = path + ".part";
        try
        {
            var fetcher = new PartFetcher(_http, retryDelay: _retryDelay);
            await fetcher.FetchAsync(
                offer.Url,
                part,
                new ReleasePart(offer.File, offer.Bytes, offer.Sha256),
                moved => _rate.Saw(Interlocked.Add(ref _downloaded, moved)),
                cancellation).ConfigureAwait(false);
            File.Move(part, path, overwrite: true);
            Installed?.Invoke();
        }
        catch (OperationCanceledException) when (cancellation.IsCancellationRequested)
        {
            // stopped by the person or by BAXY closing: the «.part» goes on next time
        }
        catch (Exception failure) when (failure is HttpRequestException or IOException or InvalidDataException or OperationCanceledException
            or UnauthorizedAccessException)
        {
            DownloadProblem = failure switch
            {
                InvalidDataException => "danado",
                _ when Failures.IsDiskFull(failure) => "sin_espacio",
                HttpRequestException { StatusCode: { } status } when Failures.IsRefusal(status) => "no_disponible",
                UnauthorizedAccessException => "sin_permiso",
                // REV_APP DL-c: PartFetcher turns a line that drops into an HttpRequestException; an IOException is the disk's.
                IOException => "sin_disco",
                _ => "sin_red",
            };
        }
    }

    /// <summary>
    /// At every start of the mind, before it starts: the tuned model where the person chose it and it is the one the package
    /// offers, by its size and SHA-256 (RuntimeFileHashCache spares the read when the file did not change). Otherwise the
    /// stock model, and <see cref="Problem"/> says why.
    /// </summary>
    internal async Task StartAsync(CancellationToken cancellationToken)
    {
        string choice = Choice();
        if (choice != _applied)
        {
            Stop();
        }

        _applied = choice;
        // The mind that held it has just been stopped, and its llama-server may still be ending (it maps the file).
        DateTimeOffset until = DateTimeOffset.UtcNow + TimeSpan.FromSeconds(10);
        while (!RemoveIfAsked() && DateTimeOffset.UtcNow < until)
        {
            await Task.Delay(250, cancellationToken).ConfigureAwait(true);
        }

        TunedModelOffer? offer = _offer();
        if (offer is null || (bool?)Config()["use"] != true)
        {
            Problem = null;
            return;
        }

        if (Active)
        {
            return;
        }

        string path = FilePath!;
        Problem = await Task.Run(() => Verify(offer, path), cancellationToken).ConfigureAwait(true);
        if (Problem is not null)
        {
            return;
        }

        Replace(GgufVariable, path);
        Replace(MindRuntimeDiscovery.GgufSha256Variable, offer.Sha256);
        Active = true;
    }

    /// <summary>Back to the stock model: the mind's variables as they were before.</summary>
    internal void Stop()
    {
        lock (_replacedLock)
        {
            foreach ((string name, string? value) in _replaced)
            {
                Environment.SetEnvironmentVariable(name, value);
            }

            _replaced.Clear();
        }

        Active = false;
    }

    public void Dispose()
    {
        _download?.Cancel();
        _download?.Dispose();
        _http.Dispose();
    }

    private string? Verify(TunedModelOffer offer, string path)
    {
        try
        {
            var file = new FileInfo(path);
            if (!file.Exists)
            {
                return "ajustado_ausente";
            }

            if (file.Length != offer.Bytes)
            {
                return "ajustado_danado";
            }

            Directory.CreateDirectory(Folder);
            var hashes = new RuntimeFileHashCache(Path.Combine(Folder, RuntimeFileHashCache.FileName), FileSha256);
            string sha256 = hashes.Sha256(path);
            hashes.Save();
            return sha256 == offer.Sha256 ? null : "ajustado_danado";
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            return "ajustado_danado";
        }
    }

    /// <summary>
    /// A removal the person asked for, once nothing holds the file (a running server maps it); false while one is pending.
    /// </summary>
    private bool RemoveIfAsked()
    {
        JsonObject config = Config();
        if ((bool?)config["remove"] != true || Active || FilePath is not { } path)
        {
            return (bool?)config["remove"] != true;
        }

        try
        {
            File.Delete(path);
            File.Delete(path + ".part");
            config.Remove("remove");
            Save(config);
            Problem = null;
            return true;
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            // still mapped by the server that is closing
            return false;
        }
    }

    // Which model the next start would load: off, or this file as it is now (a new download is a new choice).
    private string Choice()
    {
        if ((bool?)Config()["use"] != true || FilePath is not { } path)
        {
            return "off";
        }

        var file = new FileInfo(path);
        return file.Exists ? $"on|{file.Length}|{file.LastWriteTimeUtc.Ticks}" : "on|missing";
    }

    private JsonObject Config()
    {
        try
        {
            return JsonNode.Parse(File.ReadAllText(ConfigPath)) as JsonObject ?? [];
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException or JsonException)
        {
            return [];
        }
    }

    private void Save(JsonObject config)
    {
        Directory.CreateDirectory(Folder);
        string temporary = ConfigPath + ".tmp";
        File.WriteAllText(temporary, config.ToJsonString());
        File.Move(temporary, ConfigPath, overwrite: true);
    }

    private void Replace(string name, string value)
    {
        // Kept and put in one step: the view reads the stock model's file from another thread (StockPath).
        lock (_replacedLock)
        {
            _replaced.TryAdd(name, Environment.GetEnvironmentVariable(name));
            Environment.SetEnvironmentVariable(name, value);
        }
    }

    private static long PartBytes(string path) =>
        File.Exists(path + ".part") ? new FileInfo(path + ".part").Length : 0;

    // The volume that holds the folder, asked by the folder itself: a mounted folder or a junction there is on another disk
    // than its drive letter (GetDiskFreeSpaceExW: «a directory on the disk», mounted folders included,
    // https://learn.microsoft.com/windows/win32/api/fileapi/nf-fileapi-getdiskfreespaceexw).
    internal static long FreeBytes(string path)
    {
        string folder = Path.GetDirectoryName(Path.GetFullPath(path))!;
        return GetDiskFreeSpaceEx(folder + Path.DirectorySeparatorChar, out ulong free, out _, out _)
            ? (long)Math.Min(free, long.MaxValue)
            : new DriveInfo(Path.GetPathRoot(folder)!).AvailableFreeSpace;
    }

    [DllImport("kernel32.dll", EntryPoint = "GetDiskFreeSpaceExW", CharSet = CharSet.Unicode, SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool GetDiskFreeSpaceEx(string directory, out ulong freeBytesAvailable, out ulong totalBytes, out ulong totalFreeBytes);

    private static string FileSha256(string path)
    {
        using FileStream stream = File.OpenRead(path);
        return Convert.ToHexStringLower(SHA256.HashData(stream));
    }
}
