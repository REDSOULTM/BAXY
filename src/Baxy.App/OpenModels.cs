using System.IO;
using System.IO.Compression;
using System.Net.Http;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;
using Baxy.Installer;

namespace Baxy.App;

/// <summary>
/// Pedido del dueño 2026-11-08: «que el usuario escriba el modelo que quiere instalar… y le cambia así de fácil el modelo».
/// Settings → Model, «Usar otro modelo» → Local: the person writes a name, BAXY finds it on Hugging Face, says its size, license,
/// whether it can use tools and whether it fits the graphics card, and Ollama downloads it (ExternalModel then connects it).
/// <list type="bullet">
/// <item>Ollama is not in the package: each Windows build of it weighs 1.6 GB and the Steam package 5.9 GB. Its standalone build
/// (the zip «for embedding Ollama in existing applications», github.com/ollama/ollama/blob/main/docs/windows.mdx), MIT, is
/// downloaded only when the person asks, pinned by size and SHA-256 (its release's own digest), into BAXY's data: no tray app,
/// nothing at login, nothing on the PATH. BAXY already opens its server hidden and closes it on leaving (ExternalModel).</item>
/// <item>The search is Hugging Face's own API (huggingface.co/docs/hub/api), 500 calls per 5 minutes without an account; ollama.com
/// has no search API and its terms forbid «automated means» (ollama.com/terms). Ollama downloads a GGUF from there by
/// «hf.co/{repo}:{quant}» (huggingface.co/docs/hub/ollama).</item>
/// </list>
/// What is sent: the name the person wrote, to huggingface.co; nothing of a conversation. Both downloads go in «Salidas a internet».
/// </summary>
internal sealed partial class OpenModels : IDisposable
{
    // The release read on 2026-11-08 (api.github.com/repos/ollama/ollama/releases/latest): v0.40.15, 2026-11-03.
    internal const string OllamaVersion = "0.40.15";
    internal const string OllamaZip = "ollama-windows-amd64.zip";
    internal const long OllamaBytes = 1614941966;
    internal const string OllamaSha256 = "9ca74a7ab66ec86870b1eecac7df160df08dc4e3a291ab5d2d59bcf9310221c6";
    private const string OllamaUrl = "https://github.com/ollama/ollama/releases/download/v" + OllamaVersion + "/" + OllamaZip;
    private static readonly ReleasePart OllamaRelease = new(OllamaZip, OllamaBytes, OllamaSha256);
    private const string Hub = "https://huggingface.co";
    private const string HubApi = Hub + "/api/models";
    // The first bytes of a model's file asked for its header (GgufShape): the architecture's keys end in the first few KB.
    private const long HeaderBytes = 1L << 20;
    // Headers read in one repository while its files are of another architecture than the repository's (VIVO1).
    private const int HeadersTried = 3;
    // Repositories looked into for each search: one call each, of the 500 per 5 minutes Hugging Face gives without an account.
    private const int Looked = 8;
    private const long Headroom = 1L << 30;
    // The quantizations worth offering, best first for a card of 4 to 8 GB: Q4_K_M is Ollama's default for a GGUF repository.
    private static readonly string[] Preferred = ["Q4_K_M", "Q4_K_S", "Q4_0", "IQ4_XS", "Q5_K_M", "Q6_K", "Q8_0"];

    private readonly string _root;
    private readonly HttpClient _http;
    private readonly Func<string, long> _freeBytes;
    private readonly (string Url, ReleasePart Part) _ollama;
    private readonly object _sync = new();
    private CancellationTokenSource? _work;
    private long _downloaded;
    private string? _pulling;
    private long _pullTotal;
    private long _pullDone;
    private long _pullExpected;
    // Each layer Ollama downloads (the model, its projector...), by digest: the progress is all of them.
    private readonly Dictionary<string, (long Total, long Done)> _layers = new(StringComparer.Ordinal);
    // The last download that stopped before it ended: the same request goes on from what it left.
    private string? _stopped;
    // The tool profile a model was asked to be used with once it is here (the search's offer for one short of the chosen
    // profile), by its name in Ollama: kept for this run, so the same download asked again or resumed still ends with it.
    private readonly Dictionary<string, string> _askedWith = new(StringComparer.Ordinal);
    private readonly DownloadRate _ollamaRate = new();
    private readonly DownloadRate _pullRate = new();
    private readonly TimeSpan? _retryDelay;

    /// <param name="ollama">A test's own release in place of the pinned one.</param>
    /// <param name="retryDelay">A test's own pause between the tries of a download (PartFetcher's, by default).</param>
    internal OpenModels(string dataRoot, HttpMessageHandler? handler = null, Func<string, long>? freeBytes = null, (string Url, ReleasePart Part)? ollama = null,
        TimeSpan? retryDelay = null)
    {
        _root = dataRoot;
        _retryDelay = retryDelay;
        _ollama = ollama ?? (OllamaUrl, OllamaRelease);
        _freeBytes = freeBytes ?? TunedModel.FreeBytes;
        // No overall timeout: PartFetcher cuts a download that stalls, and a search has its own.
        _http = handler is null ? new HttpClient { Timeout = Timeout.InfiniteTimeSpan } : new HttpClient(handler) { Timeout = Timeout.InfiniteTimeSpan };
        _http.DefaultRequestHeaders.UserAgent.ParseAdd("BAXY");
    }

    /// <summary>A download or the search reached a server: what, for «Salidas a internet».</summary>
    internal event Action<string>? WentOnline;

    /// <summary>BAXY's own Ollama is unpacked, on a pool thread.</summary>
    internal event Action? OllamaInstalled;

    /// <summary>The version of the Ollama that last answered BAXY, or null.</summary>
    internal string? RunningVersion { get; set; }

    /// <summary>A model finished downloading in Ollama, on a pool thread: its name there, to connect it.</summary>
    internal event Action<string>? Pulled;

    /// <summary>The tool profile <paramref name="name"/>'s download was asked with, once: null if none.</summary>
    internal string? TakeProfile(string name)
    {
        lock (_sync)
        {
            return _askedWith.Remove(name, out string? profile) ? profile : null;
        }
    }

    /// <summary>Ollama being installed or a model being downloaded now.</summary>
    internal Task? Working { get; private set; }

    internal string? OllamaProblem { get; private set; }

    internal string? PullProblem { get; private set; }

    private string OllamaFolder => Path.Combine(_root, "ollama");

    /// <summary>BAXY's own copy of Ollama, once installed.</summary>
    internal string OwnOllama => Path.Combine(OllamaFolder, OllamaVersion, "ollama.exe");

    private bool Busy => Working is { IsCompleted: false };

    /// <summary>The Ollama BAXY opens when none answers: its own copy, or else the one Ollama's installer leaves for this user.</summary>
    internal string? OllamaProgram()
    {
        if (File.Exists(OwnOllama))
        {
            return OwnOllama;
        }

        string installed = Path.Combine(Environment.GetEnvironmentVariable("LOCALAPPDATA") ?? string.Empty, "Programs", "Ollama", "ollama.exe");
        return File.Exists(installed) ? installed : null;
    }

    /// <summary>The view's state: what is installed, and what is being downloaded with its bytes, speed and seconds left.</summary>
    internal JsonObject Json()
    {
        long total = Interlocked.Read(ref _pullTotal);
        bool installing = Busy && _pulling is null;
        bool pulling = Busy && _pulling is not null;
        return new JsonObject
        {
            ["ollamaVersion"] = OllamaVersion,
            ["ollamaBytes"] = _ollama.Part.Bytes,
            ["ollamaOwn"] = File.Exists(OwnOllama),
            ["ollamaRunning"] = RunningVersion,
            ["ollamaInstalling"] = installing,
            ["ollamaDownloadedBytes"] = Interlocked.Read(ref _downloaded),
            ["ollamaBytesPerSecond"] = installing ? _ollamaRate.BytesPerSecond : null,
            ["ollamaSecondsLeft"] = installing ? _ollamaRate.SecondsLeft(_ollama.Part.Bytes) : null,
            ["ollamaProblem"] = Busy ? null : OllamaProblem,
            ["pulling"] = Busy ? _pulling : null,
            ["pullTotal"] = total,
            ["pullDone"] = Interlocked.Read(ref _pullDone),
            ["pullBytesPerSecond"] = pulling ? _pullRate.BytesPerSecond : null,
            ["pullSecondsLeft"] = pulling ? _pullRate.SecondsLeft(total) : null,
            ["pullStopped"] = Busy ? null : _stopped,
            ["pullProblem"] = Busy ? null : PullProblem,
        };
    }

    /// <summary>Starts installing BAXY's copy of Ollama; the refusal's code when it cannot start.</summary>
    internal string? InstallOllama(CancellationToken lifetime)
    {
        lock (_sync)
        {
            if (Busy)
            {
                return "open_models_busy";
            }

            string zip = Path.Combine(OllamaFolder, OllamaZip);
            Directory.CreateDirectory(OllamaFolder);
            long part = File.Exists(zip + ".part") ? new FileInfo(zip + ".part").Length : 0;
            // The zip and what it holds, both on disk until it is unpacked; how much it holds is read once it is here.
            if (_freeBytes(zip) < (_ollama.Part.Bytes - part) + _ollama.Part.Bytes + Headroom)
            {
                OllamaProblem = "sin_espacio";
                return "open_models_no_space";
            }

            OllamaProblem = null;
            Interlocked.Exchange(ref _downloaded, 0);
            _ollamaRate.Reset();
            _work?.Dispose();
            _work = CancellationTokenSource.CreateLinkedTokenSource(lifetime);
            WentOnline?.Invoke(UiLanguage.Say("descarga de Ollama desde github.com", "download of Ollama from github.com"));
            Working = InstallOllamaAsync(zip, _work.Token);
            return null;
        }
    }

    private async Task InstallOllamaAsync(string zip, CancellationToken cancellation)
    {
        await Task.Yield();
        try
        {
            await new PartFetcher(_http, retryDelay: _retryDelay).FetchAsync(_ollama.Url, zip + ".part", _ollama.Part,
                moved => _ollamaRate.Saw(Interlocked.Add(ref _downloaded, moved)), cancellation).ConfigureAwait(false);
            File.Move(zip + ".part", zip, overwrite: true);
            string target = Path.GetDirectoryName(OwnOllama)!;
            string unpacking = target + ".tmp";
            await Task.Run(() => Unpack(zip, unpacking, target), cancellation).ConfigureAwait(false);
            File.Delete(zip);
            OllamaInstalled?.Invoke();
        }
        catch (OperationCanceledException) when (cancellation.IsCancellationRequested)
        {
            // stopped by the person or by BAXY closing: the «.part» goes on next time
        }
        catch (Exception failure) when (failure is HttpRequestException or IOException or InvalidDataException or OperationCanceledException
            or UnauthorizedAccessException)
        {
            OllamaProblem = failure switch
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

    /// <summary>Unpacked beside its folder and moved in whole: a cut leaves no half Ollama for the next start.</summary>
    private void Unpack(string zip, string unpacking, string target)
    {
        using ZipArchive archive = ZipFile.OpenRead(zip);
        long holds = archive.Entries.Sum(static entry => entry.Length);
        if (_freeBytes(zip) < holds + Headroom)
        {
            throw new IOException("There is not enough space on the disk.", unchecked((int)0x80070070));
        }

        if (Directory.Exists(unpacking))
        {
            Directory.Delete(unpacking, recursive: true);
        }

        archive.ExtractToDirectory(unpacking);
        if (!File.Exists(Path.Combine(unpacking, "ollama.exe")))
        {
            throw new InvalidDataException("ollama.exe is not at the zip's root");
        }

        if (Directory.Exists(target))
        {
            Directory.Delete(target, recursive: true);
        }

        Directory.Move(unpacking, target);
    }

    /// <summary>
    /// What Hugging Face has under the name the person wrote, the GGUF repositories most downloaded first: for each, the file
    /// BAXY would install, its size, its license, its downloads, its own context (its file's header, the card's as a hint) and
    /// whether its chat template takes tools; and from its header (ModelMemory) the context recommended for the
    /// <paramref name="vramBytes"/> free for it on the graphics card (0 or less: not known), the VRAM it takes with it and
    /// with each context offered, and whether it fits.
    /// </summary>
    internal Task<JsonObject> SearchAsync(string query, long vramBytes, CancellationToken cancellationToken) =>
        SearchAsync(query, Task.FromResult<(long?, long?)>((vramBytes > 0 ? vramBytes : null, null)), cancellationToken);

    /// <summary>The search with the free VRAM still being read (ExternalModel reads the card's use beside it).</summary>
    /// <param name="need">The context the chosen tool profile's prompt and a turn take (ExternalModel.Need).</param>
    /// <param name="lesser">For a model that declares less than <paramref name="need"/>: the preset with the most tools that
    /// fits its context, and what that one takes; null when none does.</param>
    internal async Task<JsonObject> SearchAsync(string query, Task<(long? Vram, long? Commit)> room, CancellationToken cancellationToken,
        int need = ExternalModel.MinimumLocalContext, Func<int, (string Profile, int Need)?>? lesser = null)
    {
        query = query.Trim();
        if (query.Length is 0 or > 100)
        {
            return new JsonObject { ["error"] = "empty" };
        }

        WentOnline?.Invoke(UiLanguage.Say("búsqueda de modelos en huggingface.co", "model search on huggingface.co"));
        using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        timeout.CancelAfter(TimeSpan.FromSeconds(30));
        try
        {
            string listing = await _http.GetStringAsync(new Uri(
                $"{HubApi}?search={Uri.EscapeDataString(query)}&filter=gguf&sort=downloads&direction=-1&limit={Looked}"), timeout.Token).ConfigureAwait(false);
            var listed = (JsonNode.Parse(listing) as JsonArray ?? [])
                .Select(static row => (Id: (string?)row?["id"], Downloads: (long?)row?["downloads"]))
                .Where(static row => row.Id is not null && RepositoryName().IsMatch(row.Id))
                .ToList();
            JsonObject?[] found = await Task.WhenAll(listed.Select(row => AnsweredAsync(row.Id!, row.Downloads, room, need, lesser, timeout.Token))).ConfigureAwait(false);
            var results = new JsonArray();
            // What BAXY can run first, then what does not fit or cannot; among each, as Hugging Face ordered them.
            foreach (JsonObject row in found.OfType<JsonObject>().OrderBy(static row => (string?)row["why"] is null ? 0 : 1))
            {
                results.Add(row);
            }

            // What the chosen profile takes: the view says it of a model offered with a smaller one.
            return new JsonObject { ["results"] = results, ["needContext"] = need };
        }
        catch (Exception failure) when (failure is HttpRequestException or TaskCanceledException or JsonException
            && !cancellationToken.IsCancellationRequested)
        {
            return new JsonObject { ["error"] = failure is HttpRequestException { StatusCode: System.Net.HttpStatusCode.TooManyRequests } ? "limite" : "sin_red" };
        }
    }

    // REV_APP SRCH-a: a repository Hugging Face answers for with a refusal (gone or made private since it was listed), or with
    // what is not its page, is left out as a gated one is; it failed the whole search as «sin red». No answer at all, or being
    // asked to wait, is the search's own failure.
    private async Task<JsonObject?> AnsweredAsync(string id, long? downloads, Task<(long? Vram, long? Commit)> room, int need,
        Func<int, (string Profile, int Need)?>? lesser, CancellationToken cancellationToken)
    {
        try
        {
            return await RepositoryAsync(id, downloads, room, need, lesser, cancellationToken).ConfigureAwait(false);
        }
        catch (HttpRequestException refused) when (refused.StatusCode is { } status && Failures.IsRefusal(status))
        {
            return null;
        }
        catch (JsonException)
        {
            return null;
        }
    }

    private async Task<JsonObject?> RepositoryAsync(string id, long? downloads, Task<(long? Vram, long? Commit)> room, int need,
        Func<int, (string Profile, int Need)?>? lesser, CancellationToken cancellationToken)
    {
        string text = await _http.GetStringAsync(new Uri($"{HubApi}/{id}?blobs=true"), cancellationToken).ConfigureAwait(false);
        if (JsonNode.Parse(text) is not JsonObject repo || repo["gated"] is JsonValue gated && gated.GetValueKind() != JsonValueKind.False)
        {
            return null;
        }

        // Only a file whole in the repository's root: Ollama names it by its quantization (hf.co/{repo}:{quant}).
        var root = (repo["siblings"] as JsonArray ?? [])
            .OfType<JsonObject>()
            .Select(static file => (Name: (string?)file["rfilename"] ?? string.Empty, Bytes: (long?)file["size"] ?? 0,
                Sha256: (string?)(file["lfs"] as JsonObject)?["sha256"] ?? string.Empty))
            .Where(static file => file.Name.EndsWith(".gguf", StringComparison.OrdinalIgnoreCase) && !file.Name.Contains('/', StringComparison.Ordinal)
                && !SplitFile().IsMatch(file.Name) && file.Bytes > 0)
            .ToList();
        // Its vision, apart: Ollama's «hf.co/{repo}:{quant}» brings the repository's projector too (measured on 2026-11-08, Qwen3.5-2B
        // took 1.95 GB in Ollama for its 1.28 GB file, the rest its 0.67 GB mmproj). Pedido del dueño 2026-11-08: the model alone is
        // what is installed, and its vision only if the person adds it. The smallest projector is said, as the least it adds.
        long projector = root.Where(static file => file.Name.Contains("mmproj", StringComparison.OrdinalIgnoreCase))
            .Select(static file => file.Bytes).DefaultIfEmpty(0).Min();
        var files = root
            .Where(static file => !file.Name.Contains("mmproj", StringComparison.OrdinalIgnoreCase))
            .Select(static file => (file.Name, file.Bytes, file.Sha256, Quant: QuantOf(file.Name)))
            .Where(static file => file.Quant is not null)
            .ToList();
        if (files.Count == 0)
        {
            return null;
        }

        JsonObject? gguf = repo["gguf"] as JsonObject;
        // VIVO1 (2026-11-09): beside its model a repository may hold a file that is not it, such as an EAGLE-3 draft head
        // (eagle3-gpt-oss-20b-Q8_0.gguf, 0.9 GB, beside the 12 GB gpt-oss-20b-MXFP4.gguf), which the preferred quantization
        // chose and offered as «cabe». Its header names another architecture than the one Hugging Face reads for the
        // repository (gguf.architecture): such a file is passed over for the next one, up to HeadersTried headers (each is
        // 1 MiB, under the search's 30 s). When none matches, what Hugging Face declared is the odd one (a repository that
        // mixes variants): the first file stays the choice, as before.
        string? declared = (string?)gguf?["architecture"];
        var ordered = files.OrderBy(static file => Array.IndexOf(Preferred, file.Quant!.ToUpperInvariant()) is var at and >= 0 ? at : Preferred.Length)
            .ThenBy(static file => file.Bytes)
            .ToList();
        var chosen = ordered[0];
        GgufShape? shape = null;
        for (int index = 0; index < Math.Min(ordered.Count, HeadersTried); index++)
        {
            GgufShape? read = await ShapeAsync(id, ordered[index].Name, cancellationToken).ConfigureAwait(false);
            if (index == 0)
            {
                shape = read;
            }

            if (declared is not { Length: > 0 } || read?.Architecture is not { Length: > 0 } its || string.Equals(its, declared, StringComparison.Ordinal))
            {
                chosen = ordered[index];
                shape = read;
                break;
            }
        }

        string template = (string?)gguf?["chat_template"] ?? string.Empty;
        int context = (int?)gguf?["context_length"] ?? 0;
        JsonObject? card = repo["cardData"] as JsonObject;
        string? license = (string?)card?["license_name"] ?? (card?["license"] as JsonValue)?.ToString();
        // A template that takes tools reads the request's «tools» (Jinja, as llama.cpp and Ollama read it): the form, not what it says.
        bool tools = ToolsVariable().IsMatch(template);
        // Its own context is its file's (<arch>.context_length); the card's is only a hint. As it will run: up to what it declares,
        // Ollama with its f16 cache; past it, BAXY's own llama-server with the mind's q8_0 cache (external_model.Engine). Past what
        // is free, Ollama puts the rest in RAM. What is installed is the model alone (Install), so its VRAM is the model's; the
        // vision it may add, apart (projectorVramBytes), as the person adds it.
        int native = shape?.ContextLength is > 0 and var own ? own : context;
        // Where it runs it must hold the chosen profile's prompt and a turn (external_model.local_backend): one that declares less
        // is offered with the preset with the most tools that fits it, as one already installed is (ExternalModel.WithProfiles),
        // and counted with that one's need (VIVO2 F13: 40,960 tokens were «muy poco contexto» in the search and «Usar con Esencial»
        // once installed).
        (string Profile, int Need)? smaller = tools && native > 0 && native < need && lesser?.Invoke(native) is { } fits && fits.Need <= native
            ? fits : null;
        int needs = smaller?.Need ?? need;
        string? why = !tools ? "sin_herramientas" : native > 0 && native < needs ? "poco_contexto" : null;
        // What is said of it is never past what it declares: it is not connected there (F13: «contexto máximo 40.960 tokens,
        // recomendado 52.000», with its VRAM at those 52,000).
        int least = native > 0 ? Math.Min(needs, native) : needs;
        (long? free, long? commit) = await room.ConfigureAwait(false);
        // As it is installed: the model alone (Install), its vision apart and optional (projectorVramBytes says what it adds).
        long At(int tokens) => ModelMemory.GpuBytes(shape!, chosen.Bytes, tokens, tokens <= native ? "f16" : "q8_0", projectorBytes: 0);
        // The same room and recommendation a connection goes by (ExternalModel.SayVideoMemory), against the need of the profile
        // it will be used with.
        JsonObject? contexts = shape is null ? null
            : ModelMemory.ContextJson(At, native, least, ModelMemory.Room(free, commit), ExternalModel.ContextChoices);
        int? running = (int?)contexts?["recommended"];
        long? vram = contexts?["options"]?.AsArray().FirstOrDefault(option => (int?)option?["tokens"] == running)?["vramBytes"]?.GetValue<long>();
        long bytes = chosen.Bytes;
        return new JsonObject
        {
            ["repo"] = id,
            ["file"] = chosen.Name,
            ["quant"] = chosen.Quant!.ToUpperInvariant(),
            // The model alone, as Install makes it from its file; with its vision, as Ollama pulls it from Hugging Face.
            ["name"] = $"{id}:{chosen.Quant!.ToUpperInvariant()}",
            ["visionName"] = projector > 0 ? $"hf.co/{id}:{chosen.Quant!.ToUpperInvariant()}" : null,
            ["sha256"] = chosen.Sha256,
            ["bytes"] = bytes,
            ["projectorBytes"] = projector,
            ["projectorVramBytes"] = ModelMemory.ProjectorGpuBytes(projector),
            ["license"] = license,
            ["downloads"] = downloads,
            ["context"] = native,
            ["architecture"] = shape?.Architecture ?? (string?)gguf?["architecture"],
            ["tools"] = tools,
            ["vramBytes"] = vram,
            ["vramContext"] = running,
            ["contexts"] = contexts,
            ["ramBytes"] = vram is { } whole ? ModelMemory.RamBytes(whole) : null,
            // Short of room: the card when not even the least context it would run with fits it, else what Windows can promise.
            ["fit"] = free is not { } cardFree || vram is null ? "desconocido"
                : (string?)contexts?["why"] != "no_cabe" ? "cabe"
                : At(least) > cardFree ? "no_cabe" : "no_cabe_ram",
            ["why"] = why,
            // The tool profile it is offered with, when the chosen one's prompt does not fit what it declares.
            ["profile"] = smaller?.Profile,
        };
    }

    /// <summary>The shape a model file's header gives, read from its first bytes on Hugging Face; null when it does not say.</summary>
    private async Task<GgufShape?> ShapeAsync(string id, string file, CancellationToken cancellationToken)
    {
        using var request = new HttpRequestMessage(HttpMethod.Get, new Uri($"{Hub}/{id}/resolve/main/{Uri.EscapeDataString(file)}"));
        request.Headers.Range = new System.Net.Http.Headers.RangeHeaderValue(0, HeaderBytes - 1);
        try
        {
            using HttpResponseMessage reply = await _http.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, cancellationToken).ConfigureAwait(false);
            if (!reply.IsSuccessStatusCode)
            {
                return null;
            }

            await using Stream body = await reply.Content.ReadAsStreamAsync(cancellationToken).ConfigureAwait(false);
            // Read in one go from a buffer: the header's reader is synchronous, and a range of 1 MiB is small.
            using var header = new MemoryStream();
            await body.CopyToAsync(header, cancellationToken).ConfigureAwait(false);
            header.Position = 0;
            return GgufShape.Read(header, tensors: false);
        }
        catch (Exception failure) when (failure is HttpRequestException or IOException)
        {
            return null;
        }
    }

    /// <summary>The quantization a GGUF's name ends in («Qwen3.5-4B-Q4_K_M.gguf» → Q4_K_M), or null.</summary>
    internal static string? QuantOf(string file) =>
        QuantName().Match(Path.GetFileNameWithoutExtension(file)) is { Success: true } match ? match.Groups[1].Value : null;

    /// <summary>
    /// Ollama downloads <paramref name="name"/> (hf.co/{repo}:{quant}); on success <see cref="Pulled"/> says it. Ollama goes
    /// on from what a cut download left (docs/api.md, /api/pull): asked again, the same name goes on. <paramref name="expectedBytes"/>
    /// is the size the search gave (the file and its projector), the total until Ollama has told every layer's.
    /// <paramref name="profile"/> is the tool profile to use it with once here (<see cref="TakeProfile"/>).
    /// </summary>
    internal string? Pull(string name, Func<CancellationToken, Task<bool>> ollamaUp, CancellationToken lifetime, long expectedBytes = 0,
        string? profile = null)
    {
        if (!HubName().IsMatch(name))
        {
            return "open_models_invalid_name";
        }

        lock (_sync)
        {
            if (Busy)
            {
                return "open_models_busy";
            }

            PullProblem = null;
            _pulling = name;
            if (profile is not null)
            {
                _askedWith[name] = profile;
            }

            _stopped = null;
            _layers.Clear();
            _pullRate.Reset();
            Interlocked.Exchange(ref _pullExpected, Math.Max(expectedBytes, 0));
            Interlocked.Exchange(ref _pullTotal, Math.Max(expectedBytes, 0));
            Interlocked.Exchange(ref _pullDone, 0);
            _work?.Dispose();
            _work = CancellationTokenSource.CreateLinkedTokenSource(lifetime);
            WentOnline?.Invoke(UiLanguage.Say($"descarga de {name[6..]} desde huggingface.co", $"download of {name[6..]} from huggingface.co"));
            Working = PullAsync(name, ollamaUp, _work.Token);
            return null;
        }
    }

    private async Task PullAsync(string name, Func<CancellationToken, Task<bool>> ollamaUp, CancellationToken cancellation)
    {
        await Task.Yield();
        try
        {
            if (!await ollamaUp(cancellation).ConfigureAwait(false))
            {
                PullProblem = "sin_ollama";
                return;
            }

            // Ollama's own address, on this PC: no proxy and no redirect take it elsewhere.
            using var local = new HttpClient(new HttpClientHandler { UseProxy = false, AllowAutoRedirect = false }) { Timeout = Timeout.InfiniteTimeSpan };
            using var body = new StringContent(new JsonObject { ["model"] = name, ["stream"] = true }.ToJsonString(), Encoding.UTF8, "application/json");
            using var request = new HttpRequestMessage(HttpMethod.Post, new Uri(ExternalModel.OllamaAddress() + "/api/pull")) { Content = body };
            using HttpResponseMessage reply = await local.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, cancellation).ConfigureAwait(false);
            using var reader = new StreamReader(await reply.Content.ReadAsStreamAsync(cancellation).ConfigureAwait(false), Encoding.UTF8);
            string? status = null;
            while (await reader.ReadLineAsync(cancellation).ConfigureAwait(false) is { } line)
            {
                if (line.Trim().Length == 0 || JsonNode.Parse(line) is not JsonObject step)
                {
                    continue;
                }

                if (step["error"] is not null)
                {
                    // Ollama's words may name the repository's own text: only that it failed, and whether Hugging Face refused it.
                    PullProblem = ((string?)step["error"] ?? string.Empty).Contains("not found", StringComparison.OrdinalIgnoreCase) ? "no_existe" : "ollama_fallo";
                    return;
                }

                status = (string?)step["status"];
                if ((long?)step["total"] is { } total)
                {
                    Layer((string?)step["digest"] ?? status ?? string.Empty, total, (long?)step["completed"] ?? 0);
                }
            }

            if (status == "success")
            {
                Pulled?.Invoke(name);
            }
            else
            {
                PullProblem = reply.IsSuccessStatusCode ? "cortado" : "ollama_fallo";
                _stopped = reply.IsSuccessStatusCode ? name : null;
            }
        }
        catch (OperationCanceledException) when (cancellation.IsCancellationRequested)
        {
            // stopped: Ollama goes on from there next time
            _stopped = name;
        }
        catch (Exception failure) when (failure is HttpRequestException or IOException or JsonException or OperationCanceledException)
        {
            PullProblem = "cortado";
            _stopped = name;
        }
        finally
        {
            _pulling = null;
        }
    }

    // One of Ollama's lines: this layer's bytes. The progress is every layer's sum, never under the size the search gave.
    private void Layer(string digest, long total, long done)
    {
        lock (_sync)
        {
            _layers[digest] = (total, Math.Min(done, total));
            long all = _layers.Values.Sum(static layer => layer.Total);
            long sum = _layers.Values.Sum(static layer => layer.Done);
            Interlocked.Exchange(ref _pullTotal, Math.Max(all, Interlocked.Read(ref _pullExpected)));
            Interlocked.Exchange(ref _pullDone, sum);
            _pullRate.Saw(sum);
        }
    }

    /// <summary>
    /// The model alone, with no projector, so it sees nothing and takes no memory for vision: its GGUF from Hugging Face, kept
    /// only with the SHA-256 the Hub gives it, made a blob of Ollama and a model of it (docs/api.md: «Push a Blob», then
    /// «Create a model from GGUF» with «files»; Ollama reads its template from the file). Measured on 2026-11-08 with Ollama
    /// 0.40.15: Qwen3.5-2B so made took 1.28 GB with «tools, thinking, completion», and «hf.co/…» 1.95 GB with «vision» too.
    /// A file Ollama already holds (the same SHA-256) is not downloaded again. On success <see cref="Pulled"/> says its name.
    /// <paramref name="profile"/> is the tool profile to use it with once here (<see cref="TakeProfile"/>).
    /// </summary>
    internal string? Install(string repo, string file, string sha256, long bytes, string quant, Func<CancellationToken, Task<bool>> ollamaUp,
        CancellationToken lifetime, string? profile = null)
    {
        if (!RepositoryName().IsMatch(repo) || !GgufName().IsMatch(file) || !Sha256Hex().IsMatch(sha256) || bytes <= 0
            || !QuantTag().IsMatch(quant))
        {
            return "open_models_invalid_name";
        }

        lock (_sync)
        {
            if (Busy)
            {
                return "open_models_busy";
            }

            PullProblem = null;
            _pulling = $"{repo}:{quant}";
            if (profile is not null)
            {
                _askedWith[_pulling] = profile;
            }

            // Not Ollama's pull: a cut install goes on from its «.part» when it is asked again, not by «Reanudar» (Pull).
            _stopped = null;
            _layers.Clear();
            _pullRate.Reset();
            Interlocked.Exchange(ref _pullExpected, bytes);
            Interlocked.Exchange(ref _pullTotal, bytes);
            Interlocked.Exchange(ref _pullDone, 0);
            _work?.Dispose();
            _work = CancellationTokenSource.CreateLinkedTokenSource(lifetime);
            Working = InstallAsync(repo, file, sha256, bytes, _pulling, ollamaUp, _work.Token);
            return null;
        }
    }

    private async Task InstallAsync(string repo, string file, string sha256, long bytes, string name, Func<CancellationToken, Task<bool>> ollamaUp,
        CancellationToken cancellation)
    {
        await Task.Yield();
        string kept = Path.Combine(OllamaFolder, "descargas", file);
        try
        {
            if (!await ollamaUp(cancellation).ConfigureAwait(false))
            {
                PullProblem = "sin_ollama";
                return;
            }

            // Ollama's own address, on this PC: no proxy and no redirect take it elsewhere.
            using var local = new HttpClient(new HttpClientHandler { UseProxy = false, AllowAutoRedirect = false }) { Timeout = Timeout.InfiniteTimeSpan };
            string ollama = ExternalModel.OllamaAddress();
            Uri blob = new(ollama + "/api/blobs/sha256:" + sha256);
            using (var asked = new HttpRequestMessage(HttpMethod.Head, blob))
            using (HttpResponseMessage held = await local.SendAsync(asked, cancellation).ConfigureAwait(false))
            {
                if (!held.IsSuccessStatusCode)
                {
                    Directory.CreateDirectory(Path.GetDirectoryName(kept)!);
                    long part = File.Exists(kept + ".part") ? new FileInfo(kept + ".part").Length : 0;
                    // The file, and Ollama's copy of it while it is handed over.
                    if (_freeBytes(kept) < (bytes - part) + bytes + Headroom)
                    {
                        PullProblem = "sin_espacio";
                        return;
                    }

                    WentOnline?.Invoke(UiLanguage.Say($"descarga de {repo} desde huggingface.co", $"download of {repo} from huggingface.co"));
                    await new PartFetcher(_http, retryDelay: _retryDelay).FetchAsync($"{Hub}/{repo}/resolve/main/{Uri.EscapeDataString(file)}", kept + ".part",
                        new ReleasePart(file, bytes, sha256), moved => _pullRate.Saw(Interlocked.Add(ref _pullDone, moved)), cancellation).ConfigureAwait(false);
                    File.Move(kept + ".part", kept, overwrite: true);
                    await using FileStream stream = File.OpenRead(kept);
                    using var handed = new HttpRequestMessage(HttpMethod.Post, blob) { Content = new StreamContent(stream) };
                    using HttpResponseMessage taken = await local.SendAsync(handed, cancellation).ConfigureAwait(false);
                    if (!taken.IsSuccessStatusCode)
                    {
                        PullProblem = "ollama_fallo";
                        return;
                    }
                }
            }

            Interlocked.Exchange(ref _pullDone, bytes);
            var files = new JsonObject { [file] = "sha256:" + sha256 };
            using var body = new StringContent(new JsonObject { ["model"] = name, ["files"] = files, ["stream"] = false }.ToJsonString(),
                Encoding.UTF8, "application/json");
            using HttpResponseMessage made = await local.PostAsync(new Uri(ollama + "/api/create"), body, cancellation).ConfigureAwait(false);
            string answer = await made.Content.ReadAsStringAsync(cancellation).ConfigureAwait(false);
            if (made.IsSuccessStatusCode && (string?)JsonNode.Parse(answer)?["status"] == "success")
            {
                Pulled?.Invoke(name);
            }
            else
            {
                PullProblem = "ollama_fallo";
            }
        }
        catch (OperationCanceledException) when (cancellation.IsCancellationRequested)
        {
            // stopped: the «.part» goes on next time
        }
        // REV_APP DL-b: a download cut for stalling is an OperationCanceledException nobody asked for; uncaught, the bar went
        // away with nothing said.
        catch (Exception failure) when (failure is HttpRequestException or IOException or InvalidDataException or JsonException
            or UnauthorizedAccessException or OperationCanceledException)
        {
            PullProblem = failure switch
            {
                InvalidDataException => "danado",
                _ when Failures.IsDiskFull(failure) => "sin_espacio",
                HttpRequestException { StatusCode: { } status } when Failures.IsRefusal(status) => "no_existe",
                UnauthorizedAccessException => "sin_permiso",
                IOException => "sin_disco",
                _ => "cortado",
            };
        }
        finally
        {
            _pulling = null;
            // Ollama keeps its own copy: this one is only the way there.
            if (File.Exists(kept))
            {
                try
                {
                    File.Delete(kept);
                }
                catch (IOException)
                {
                    // held a moment longer: the next install replaces it
                }
            }
        }
    }

    /// <summary>
    /// Removes a model from Ollama (docs/api.md, «Delete a Model»: its manifest; Ollama keeps a blob another model still uses), never
    /// the one in use, nor while something downloads. The refusal's code, or null.
    /// </summary>
    internal async Task<string?> RemoveAsync(string name, string? inUse, Func<CancellationToken, Task<bool>> ollamaUp, CancellationToken cancellationToken)
    {
        if (!OllamaName().IsMatch(name))
        {
            return "open_models_invalid_name";
        }

        if (string.Equals(name, inUse, StringComparison.OrdinalIgnoreCase))
        {
            return "open_models_in_use";
        }

        if (Busy)
        {
            return "open_models_busy";
        }

        if (!await ollamaUp(cancellationToken).ConfigureAwait(false))
        {
            return "open_models_no_ollama";
        }

        using var local = new HttpClient(new HttpClientHandler { UseProxy = false, AllowAutoRedirect = false }) { Timeout = TimeSpan.FromSeconds(30) };
        using var request = new HttpRequestMessage(HttpMethod.Delete, new Uri(ExternalModel.OllamaAddress() + "/api/delete"))
        {
            Content = new StringContent(new JsonObject { ["model"] = name }.ToJsonString(), Encoding.UTF8, "application/json"),
        };
        try
        {
            using HttpResponseMessage reply = await local.SendAsync(request, cancellationToken).ConfigureAwait(false);
            return reply.IsSuccessStatusCode ? null : reply.StatusCode == System.Net.HttpStatusCode.NotFound ? "open_models_not_found" : "open_models_failed";
        }
        catch (Exception failure) when (failure is HttpRequestException or TaskCanceledException && !cancellationToken.IsCancellationRequested)
        {
            return "open_models_no_ollama";
        }
    }

    /// <summary>Stops what is being downloaded now.</summary>
    internal void Cancel() => _work?.Cancel();

    public void Dispose()
    {
        _work?.Cancel();
        _work?.Dispose();
        _http.Dispose();
    }

    [GeneratedRegex(@"^[A-Za-z0-9][A-Za-z0-9_.-]{0,95}/[A-Za-z0-9][A-Za-z0-9_.-]{0,95}$")]
    private static partial Regex RepositoryName();

    [GeneratedRegex(@"^hf\.co/[A-Za-z0-9][A-Za-z0-9_.-]{0,95}/[A-Za-z0-9][A-Za-z0-9_.-]{0,95}:[A-Za-z0-9_]{1,20}$")]
    private static partial Regex HubName();

    [GeneratedRegex(@"^[A-Za-z0-9][A-Za-z0-9_.-]{0,150}\.gguf$", RegexOptions.IgnoreCase)]
    private static partial Regex GgufName();

    // An Ollama model's name: [host/][namespace/]model[:tag] (docs/api.md, «Model names»).
    [GeneratedRegex(@"^[A-Za-z0-9][A-Za-z0-9_.-]{0,95}(/[A-Za-z0-9][A-Za-z0-9_.-]{0,95}){0,2}(:[A-Za-z0-9_.-]{1,64})?$")]
    private static partial Regex OllamaName();

    [GeneratedRegex(@"^[0-9a-f]{64}$")]
    private static partial Regex Sha256Hex();

    [GeneratedRegex(@"^[A-Za-z0-9_]{1,20}$")]
    private static partial Regex QuantTag();

    [GeneratedRegex(@"-\d{5}-of-\d{5}\.gguf$", RegexOptions.IgnoreCase)]
    private static partial Regex SplitFile();

    // MXFP4: gpt-oss's own quantization, the only one OpenAI ships (developers.openai.com/cookbook, «Run gpt-oss locally with Ollama»).
    [GeneratedRegex(@"[-.]((?:I?Q\d(?:_[A-Z0-9]+)*)|MXFP4|BF16|F16|F32)$", RegexOptions.IgnoreCase)]
    private static partial Regex QuantName();

    [GeneratedRegex(@"\btools\b")]
    private static partial Regex ToolsVariable();
}
