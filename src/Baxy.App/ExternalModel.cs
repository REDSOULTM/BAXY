using System.ComponentModel;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Net;
using System.Net.Http;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Providers.Windows.SystemStatus;
using Baxy.Security.Windows;

namespace Baxy.App;

/// <summary>
/// A model behind a company's API, with the person's own key, or a model the person downloaded in Ollama, in place of BAXY's
/// own: Settings lists what that key or this PC can use, and choosing one connects it. Off until the person turns it
/// on: BAXY by default runs its model here and sends no conversation anywhere, as its store page says. Settings offers the
/// provider, the model and the key. Each key is sealed for this Windows user in its own file, is never sent back to the
/// view, and reaches only the translator's environment: neither the mind nor this process's environment has it. While it
/// is on, the mind starts no llama-server. A change applies at once (MainWindowViewModel relaunches the mind, which gets its
/// conversation back). A key or a translator that does not work leaves BAXY on the local model, saying why, and turning
/// it off puts back what the mind's variables were. BAXY_API_EXTERNA=0 removes the setting (no route, no section).
/// </summary>
internal sealed class ExternalModel : IDisposable
{
    internal const string Variable = "BAXY_API_EXTERNA";
    // Another interpreter for the translator (a development machine whose runtime has no SDK); the mind's by default.
    internal const string PythonVariable = "BAXY_API_EXTERNA_PYTHON";
    internal const string CeilingVariable = "BAXY_API_EXTERNA_TOPE_USD";
    internal const string EffortVariable = "BAXY_API_EXTERNA_ESFUERZO";
    // A test's: the translator does not ask the API whether its fake key works.
    internal const string NoCheckVariable = "BAXY_API_EXTERNA_SIN_COMPROBAR";
    private const string Anthropic = "anthropic";
    private const string Compatible = "compatible";
    private const string Local = "local";
    private const string OllamaHostVariable = "OLLAMA_HOST";
    private const int DefaultOllamaPort = 11434;
    private const string DefaultOllama = "http://127.0.0.1:11434";
    // What the translator gives Ollama when the person chose nothing (external_model.OLLAMA_CONTEXT).
    private const int DefaultLocalContext = 78000;
    private const int MinimumContext = 2048;
    private const int MaximumContext = 2097152;
    // A model on this PC reads its whole prompt the first time, and may have to load first.
    private const string LocalTurnSeconds = "300";
    private const string DefaultAnthropicModel = "claude-opus-5-5";
    private const int MaximumKeyLength = 512;
    private const int MaximumFieldLength = 200;
    private const double MaximumCeilingUsd = 1000;
    // Uso real 2026-11-05: with the local model's 77,824, a prompt of 80,000 tokens cut the history at every step, which
    // restarts the API's cache: 0.41 USD per decision instead of 0.03, and the ceiling spent in five minutes.
    private const string Context = "200000";
    // Measured 2026-11-06 on a PC under load: the translator's first import of Anthropic's SDK took 9 to 66 s, before it listens.
    private static readonly TimeSpan StartBudget = TimeSpan.FromSeconds(90);
    // The translator may first load a model off the disk onto BAXY's own server (ENGINE_START_SECONDS).
    private static readonly TimeSpan LocalStartBudget = TimeSpan.FromSeconds(180);
    // The models whose prices the translator knows (traductor.py PRICES): only those can keep a spending ceiling.
    private static readonly string[] PricedModels = [DefaultAnthropicModel, "claude-sonnet-5-5"];
    private static readonly (string Id, string Label)[] Providers =
    [
        (Anthropic, "Anthropic"), ("openai", "OpenAI"), ("google", "Google"), (Local, "Local"), (Compatible, "Otra"),
    ];

    private readonly string _folder;
    private readonly Dictionary<string, string?> _replaced = [];
    private Process? _translator;
    private string? _activeModel;
    private bool _activeLocal;
    private bool _apiThisRun;
    private string? _applied;
    private Process? _ollama;
    private int _activeContext;
    private readonly WindowsGpuStatusProvider _gpu = new();
    // Measuring and connecting both load the model: at once, each takes the other's load out (gemma4:26b never finished, 2026-11-06).
    private readonly SemaphoreSlim _estimating = new(1, 1);

    internal ExternalModel(string dataRoot) => _folder = Path.Combine(dataRoot, "external-model");

    internal static bool Available => Environment.GetEnvironmentVariable(Variable) != "0";

    internal bool Active { get; private set; }

    internal string? Problem { get; private set; }

    /// <summary>The mind is being relaunched for a change the person just made.</summary>
    internal bool Switching { get; set; }

    /// <summary>What the person has chosen is not what the running mind was started with; the first start reads it anyway.</summary>
    internal bool NeedsSwitch => _applied is not null && Choice() != _applied;

    private string ConfigPath => Path.Combine(_folder, "config.json");

    private string SpendPath => Path.Combine(_folder, "gasto.jsonl");

    private string LogPath => Path.Combine(_folder, "traductor.log");

    private WindowsProtectedPayload Keys => new(Path.Combine(_folder, "keys.bin"));

    /// <summary>The spending ceiling the person wrote; with none, there is none.</summary>
    private static double? CeilingOf(JsonObject config) =>
        (double?)config["ceilingUsd"]
        ?? (double.TryParse(Environment.GetEnvironmentVariable(CeilingVariable), NumberStyles.Float, CultureInfo.InvariantCulture, out double usd)
            ? usd
            : null);

    private string KeyPath(string provider) => Path.Combine(_folder, $"key-{provider}.bin");

    private static string Purpose(string provider) => $"baxy.external-model.key.{provider}";

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
        string temporary = ConfigPath + ".tmp";
        File.WriteAllText(temporary, config.ToJsonString());
        File.Move(temporary, ConfigPath, overwrite: true);
    }

    private static string ProviderOf(JsonObject config) => (string?)config["provider"] ?? Anthropic;

    private static string ModelOf(JsonObject config, string provider) =>
        (string?)config["models"]?[provider] ?? (provider == Anthropic ? DefaultAnthropicModel : string.Empty);

    // Only «Otra» has one to write: a company's key goes to that company's address (the translator's BASE_URLS, Anthropic's own).
    private static string UrlOf(JsonObject config, string provider) => provider switch
    {
        Local => OllamaAddress(),
        Compatible => (string?)config["url"] ?? string.Empty,
        _ => string.Empty,
    };

    /// <summary>Where to call Ollama, read as Ollama reads its variable: 0.0.0.0 is where it listens, and with no scheme and no
    /// port it is its own port. Only on this PC: «Local» says nothing leaves it, so a variable naming another machine does not count.</summary>
    internal static string OllamaAddress()
    {
        string host = (Environment.GetEnvironmentVariable(OllamaHostVariable) ?? string.Empty).Trim();
        bool hasScheme = host.Contains("://", StringComparison.Ordinal);
        if (host.Length == 0 || !Uri.TryCreate(hasScheme ? host : "http://" + host, UriKind.Absolute, out Uri? address))
        {
            return DefaultOllama;
        }

        var builder = new UriBuilder(address);
        if (!hasScheme && address.IsDefaultPort)
        {
            builder.Port = DefaultOllamaPort;
        }

        if (address.Host is "0.0.0.0" or "[::]")
        {
            builder.Host = "127.0.0.1";
        }

        string called = builder.Uri.GetLeftPart(UriPartial.Authority);
        return IsLoopback(called) ? called : DefaultOllama;
    }

    private static int? ContextOf(JsonObject config, string model) => (int?)config["contexts"]?[model];

    private static bool NeedsKey(string provider, string url) =>
        provider != Local && !(provider == Compatible && IsLoopback(url));

    internal JsonObject Json()
    {
        JsonObject config = Config();
        string provider = ProviderOf(config);
        string model = ModelOf(config, provider);
        // Ended by itself: nothing starts it again until the person changes something.
        bool fell = Active && _translator is not { HasExited: false };
        var providers = new JsonArray();
        foreach ((string id, string label) in Providers)
        {
            providers.Add(new JsonObject
            {
                ["id"] = id,
                ["label"] = label,
                ["hasKey"] = File.Exists(KeyPath(id)),
                ["model"] = ModelOf(config, id),
            });
        }

        return new JsonObject
        {
            ["available"] = true,
            ["provider"] = provider,
            ["providers"] = providers,
            ["model"] = model,
            ["url"] = UrlOf(config, provider),
            ["enabled"] = (bool?)config["enabled"] ?? false,
            ["hasKey"] = File.Exists(KeyPath(provider)),
            ["active"] = Active && !fell,
            ["activeModel"] = _activeModel,
            ["activeLocal"] = _activeLocal,
            ["apiThisRun"] = _apiThisRun,
            ["switching"] = Switching,
            ["problem"] = fell ? "traductor_caido" : Problem,
            // Each start rewrites the log, so with this off its last line is an old run's.
            ["lastError"] = (bool?)config["enabled"] == true ? LastError() : null,
            ["context"] = provider == Local ? ContextOf(config, model) : null,
            ["spentUsd"] = SpentUsd(),
            ["ceilingUsd"] = CeilingOf(config),
            ["ceilingHolds"] = provider == Anthropic && PricedModels.Contains(model),
        };
    }

    /// <summary>What the panel asks: a provider, a model, a URL, a key, forgetting it, or the switch. The refusal's code, or null.</summary>
    internal string? Apply(JsonObject body)
    {
        Directory.CreateDirectory(_folder);
        JsonObject config = Config();
        if ((string?)body["provider"] is { } provider)
        {
            if (!Providers.Any(known => known.Id == provider))
            {
                return "external_model_invalid_provider";
            }

            // Another company's turn is sent only after it is chosen and turned on again.
            if (provider != ProviderOf(config))
            {
                config["provider"] = provider;
                config["enabled"] = false;
            }
        }

        string current = ProviderOf(config);
        if ((string?)body["model"] is { } model)
        {
            model = model.Trim();
            if (model.Length > MaximumFieldLength)
            {
                return "external_model_invalid_model";
            }

            JsonObject models = config["models"] as JsonObject ?? [];
            models[current] = model;
            config["models"] = models;
        }

        if (body.ContainsKey("context"))
        {
            if (body["context"] is JsonValue size && size.TryGetValue(out int context) && context is >= MinimumContext and <= MaximumContext
                && ModelOf(config, current).Length > 0)
            {
                JsonObject contexts = config["contexts"] as JsonObject ?? [];
                contexts[ModelOf(config, current)] = context;
                config["contexts"] = contexts;
            }
            else
            {
                return "external_model_invalid_context";
            }
        }

        if ((string?)body["url"] is { } url)
        {
            url = url.Trim();
            if (current == Compatible)
            {
                if (url.Length > 0 && !IsApiAddress(url))
                {
                    return "external_model_invalid_url";
                }

                url = url.Length > 0 ? AsChecked(url) : url;

                // Its key goes to this address: another one, even a typo, is sent nothing until it is turned on again.
                if (url != UrlOf(config, current))
                {
                    config["enabled"] = false;
                }

                config["url"] = url;
            }
        }

        if (body.ContainsKey("ceilingUsd"))
        {
            if (body["ceilingUsd"] is null)
            {
                config.Remove("ceilingUsd");
            }
            else if (body["ceilingUsd"] is JsonValue asked && asked.TryGetValue(out double ceiling)
                && ceiling is >= 0 and <= MaximumCeilingUsd)
            {
                config["ceilingUsd"] = ceiling;
            }
            else
            {
                return "external_model_invalid_ceiling";
            }
        }

        if ((string?)body["key"] is { } key)
        {
            key = key.Trim();
            if (key.Length is 0 or > MaximumKeyLength || key.Any(char.IsControl))
            {
                return "external_model_invalid_key";
            }

            string temporary = KeyPath(current) + ".tmp";
            File.WriteAllBytes(temporary, Keys.Seal(Encoding.UTF8.GetBytes(key), Purpose(current)));
            File.Move(temporary, KeyPath(current), overwrite: true);
            config["keyUrl"] = UrlOf(config, current);
        }

        if ((bool?)body["forgetKey"] == true)
        {
            File.Delete(KeyPath(current));
            config["enabled"] = false;
        }

        if ((bool?)body["enabled"] is { } on)
        {
            if (on && NeedsKey(current, UrlOf(config, current)) && !File.Exists(KeyPath(current)))
            {
                return "external_model_no_key";
            }

            if (on && ModelOf(config, current).Length == 0)
            {
                return "external_model_no_model";
            }

            if (on && current == Compatible && UrlOf(config, current).Length == 0)
            {
                return "external_model_no_url";
            }

            config["enabled"] = on;
            if (on)
            {
                config["keyUrl"] = UrlOf(config, current);
            }
        }

        Save(config);
        return null;
    }

    private static bool IsLoopback(string url) =>
        Uri.TryCreate(url, UriKind.Absolute, out Uri? address)
        && (address.Scheme == Uri.UriSchemeHttp || address.Scheme == Uri.UriSchemeHttps)
        && IsOnThisPc(address) && IsOnlyAnAddress(address);

    private static bool IsApiAddress(string url) =>
        Uri.TryCreate(url, UriKind.Absolute, out Uri? address)
        && (address.Scheme == Uri.UriSchemeHttps || (address.Scheme == Uri.UriSchemeHttp && IsOnThisPc(address)))
        && IsOnlyAnAddress(address);

    // As the translator reads it too (external_model._on_this_pc), which then goes past the proxy: Uri also calls [::127.0.0.1] loopback.
    private static bool IsOnThisPc(Uri address) =>
        address.IsLoopback && (!IPAddress.TryParse(address.DnsSafeHost, out IPAddress? ip) || IPAddress.IsLoopback(ip));

    // A key in the address would reach the log and the screen as the address does.
    private static bool IsOnlyAnAddress(Uri address) =>
        address.UserInfo.Length == 0 && address.Query.Length == 0 && address.Fragment.Length == 0;

    // What was checked is what the translator gets: Uri calls the name «loopback» localhost, and urllib would ask a network's
    // DNS for it, which may answer with any machine.
    private static string AsChecked(string url) => new Uri(url, UriKind.Absolute).AbsoluteUri;

    /// <summary>The translator up and the mind's variables pointed at it, when the person turned it on. Never throws for
    /// a translator that cannot start: <see cref="Problem"/> says why and the local model starts as always.</summary>
    internal async Task StartAsync(CancellationToken cancellationToken)
    {
        JsonObject config = Config();
        string choice = Choice();
        // Started for another choice, what runs must not serve this one: a mind relaunched outside a switch inherits its address.
        if (choice != _applied)
        {
            Stop();
        }

        _applied = choice;
        if (!Available || (bool?)config["enabled"] != true)
        {
            Problem = null;
            return;
        }

        if (Active && _translator is { HasExited: false })
        {
            return;
        }

        // One that died: if this start fails, the mind's variables must not go on naming its port.
        Stop();
        if (TranslatorProcess() is not { } start)
        {
            Problem = "falta_traductor";
            return;
        }

        string provider = ProviderOf(config);
        string model = ModelOf(config, provider);
        if (!TryReadKey(provider, out string key))
        {
            Problem = "clave_ilegible";
            return;
        }

        int context = 0;
        if (provider == Local)
        {
            // Measured first, with BAXY's own model gone: the translator then knows what this one needs, and nothing takes it out afterwards.
            if (await EnsureOllamaAsync(cancellationToken).ConfigureAwait(true))
            {
                _ = await MeasuredAsync(model, UrlOf(config, provider), measure: true, cancellationToken).ConfigureAwait(true);
            }

            context = ContextOf(config, model) ?? DefaultLocalContext;
            // The mind cuts its history to what the model really gets: with no server of BAXY's, what it declares (Engine in the translator).
            int admits = File.Exists(Environment.GetEnvironmentVariable("BAXY_MIND_LLAMA_SERVER"))
                ? 0
                : await OllamaContextLengthAsync(model, cancellationToken).ConfigureAwait(true);
            context = admits > 0 ? Math.Min(context, admits) : context;
        }

        int port = TranslatorPort();
        // The translator ends when this pipe closes, so a BAXY that dies leaves nothing behind.
        start.RedirectStandardInput = true;
        var arguments = new List<string>
        {
            "--puerto", port.ToString(CultureInfo.InvariantCulture),
            "--gasto", SpendPath, "--registro", LogPath, "--con-padre",
            "--proveedor", provider, "--modelo", model,
            "--esfuerzo", Environment.GetEnvironmentVariable(EffortVariable) ?? "medium",
        };
        if (Environment.GetEnvironmentVariable(NoCheckVariable) == "1")
        {
            arguments.Add("--sin-comprobar");
        }

        if (provider is Compatible or Local)
        {
            arguments.AddRange(["--url", UrlOf(config, provider)]);
        }

        if (provider == Local)
        {
            arguments.AddRange(["--contexto", context.ToString(CultureInfo.InvariantCulture), "--estimaciones", Path.Combine(_folder, "estimaciones.json")]);
        }

        if (CeilingOf(config) is { } ceiling)
        {
            arguments.AddRange(["--tope-usd", ceiling.ToString(CultureInfo.InvariantCulture)]);
        }

        foreach (string argument in arguments)
        {
            start.ArgumentList.Add(argument);
        }

        start.Environment[provider == Anthropic ? "ANTHROPIC_API_KEY" : "BAXY_EXTERNAL_API_KEY"] = key;
        try
        {
            _translator = Process.Start(start);
        }
        catch (Exception exception) when (exception is Win32Exception or InvalidOperationException)
        {
            _translator = null;
        }

        // From here the key may reach the company: the translator asks it whether the key works.
        _apiThisRun |= _translator is not null && provider != Local;
        Process? started = _translator;
        bool responds = false;
        try
        {
            responds = started is not null
                && await RespondsAsync(port, provider == Local ? LocalStartBudget : StartBudget, cancellationToken).ConfigureAwait(true)
                // Stopped while its answer was on the way: it no longer serves anything.
                && ReferenceEquals(_translator, started);
        }
        catch (OperationCanceledException)
        {
            StopTranslator();
            throw;
        }

        if (!responds)
        {
            Problem = "traductor_no_arranca";
            StopTranslator();
            return;
        }

        Problem = null;
        Active = true;
        _activeModel = model;
        _activeLocal = provider == Local;
        _activeContext = context;
        string address = port.ToString(CultureInfo.InvariantCulture);
        Replace("BAXY_MIND_LLAMA_REMOTE", address);
        Replace("BAXY_RENEW_CTX", provider == Local ? context.ToString(CultureInfo.InvariantCulture) : Context);
        Replace(MindSidecarClient.TurnSecondsVariable, provider == Local ? LocalTurnSeconds : "90");
        // Nothing to read ahead into: this server has no slot.
        Replace("BAXY_RENEW_PREFILL", "0");
        Replace("BAXY_RENEW_WAKE_WARM", "0");
        if (string.IsNullOrEmpty(Environment.GetEnvironmentVariable("BAXY_VISION_OFF")))
        {
            Replace("BAXY_VISION_ENDPOINT", $"http://127.0.0.1:{address}/v1/chat/completions");
        }
    }

    /// <summary>What this key or this PC can use, for the list in Settings: the translator's own answer (asking costs nothing).</summary>
    internal async Task<JsonObject> ModelsAsync(CancellationToken cancellationToken)
    {
        JsonObject config = Config();
        string provider = ProviderOf(config);
        string url = UrlOf(config, provider);
        if (provider == Local && !await EnsureOllamaAsync(cancellationToken).ConfigureAwait(true))
        {
            return new JsonObject { ["ollama"] = "missing" };
        }

        if (NeedsKey(provider, url) && !File.Exists(KeyPath(provider)))
        {
            return new JsonObject { ["needsKey"] = true };
        }

        if (provider == Compatible && url.Length == 0)
        {
            return new JsonObject { ["needsUrl"] = true };
        }

        if (TranslatorProcess() is not { } start || !TryReadKey(provider, out string key))
        {
            return new JsonObject { ["error"] = "no se pudo preguntar la lista" };
        }

        // The panel asks as soon as an address is written: a typo gets the key only once the person turns it on for that address.
        if (provider == Compatible && (string?)config["keyUrl"] != url)
        {
            key = string.Empty;
        }

        start.ArgumentList.Add("--listar");
        start.ArgumentList.Add("--proveedor");
        start.ArgumentList.Add(provider);
        if (url.Length > 0)
        {
            start.ArgumentList.Add("--url");
            start.ArgumentList.Add(url);
        }

        start.Environment[provider == Anthropic ? "ANTHROPIC_API_KEY" : "BAXY_EXTERNAL_API_KEY"] = key;
        return await TranslatorAnswerAsync(start, TimeSpan.FromSeconds(45), cancellationToken).ConfigureAwait(true)
            ?? new JsonObject { ["error"] = "no se pudo leer la lista" };
    }

    /// <summary>The context sizes for the chosen Ollama model, the memory of each and what the graphics card has, before talking to it.</summary>
    /// <param name="ownModelGb">What BAXY's own model takes now on the card: it goes when this one connects.</param>
    /// <param name="ownModelRamGb">And in RAM, with its mind.</param>
    internal async Task<JsonObject> EstimateAsync(double? ownModelGb, double? ownModelRamGb, CancellationToken cancellationToken)
    {
        JsonObject config = Config();
        string provider = ProviderOf(config);
        string model = ModelOf(config, provider);
        if (provider != Local || model.Length == 0)
        {
            return [];
        }

        if (!await EnsureOllamaAsync(cancellationToken).ConfigureAwait(true))
        {
            return new JsonObject { ["ollama"] = "missing" };
        }

        // Connected, the model stays loaded: what is known is said, and it is not measured now.
        JsonObject answer = await MeasuredAsync(model, UrlOf(config, provider), measure: !(Active && _activeLocal), cancellationToken).ConfigureAwait(true)
            ?? new JsonObject { ["error"] = "no se pudo calcular" };
        GpuStatusSnapshot gpu = await _gpu.GetStatusAsync(GpuStatusScope.Usage, cancellationToken).ConfigureAwait(false);
        if (gpu.Adapters.MaxBy(static adapter => adapter.DedicatedVideoMemoryBytes) is { DedicatedVideoMemoryBytes: > 0 } card)
        {
            answer["vramTotalBytes"] = card.DedicatedVideoMemoryBytes;
            if (card.DedicatedMemoryUsageBytes is { } used)
            {
                // What goes when another context connects: BAXY's own model, Ollama's, or this model on BAXY's server, which Ollama does not see.
                double going = (ownModelGb ?? 0) * (1L << 30) + ((long?)answer["loadedBytes"] ?? 0);
                if (Active && _activeLocal && _activeContext > ((int?)answer["contextLength"] ?? int.MaxValue))
                {
                    going += (answer["options"] as JsonArray)?
                        .FirstOrDefault(option => (int?)option?["context"] == _activeContext)?["bytes"]?.GetValue<long>() ?? 0;
                }

                answer["vramFreeBytes"] = (long)Math.Clamp(card.DedicatedVideoMemoryBytes - used + going, 0, card.DedicatedVideoMemoryBytes);
                // It counts on the card and in what Windows can promise (external_model.COMMIT_PER_BYTE): free too once the other model is gone.
                if ((long?)answer["commitFreeBytes"] is { } promised)
                {
                    answer["commitFreeBytes"] = promised + (long)((going * 1.2) + ((ownModelRamGb ?? 0) * (1L << 30)));
                }
            }
        }

        return answer;
    }

    private async Task<JsonObject?> MeasuredAsync(string model, string url, bool measure, CancellationToken cancellationToken)
    {
        if (TranslatorProcess() is not { } start)
        {
            return null;
        }

        foreach (string argument in new[] { "--estimar", "--proveedor", Local, "--modelo", model, "--url", url, "--estimaciones", Path.Combine(_folder, "estimaciones.json") })
        {
            start.ArgumentList.Add(argument);
        }

        if (!measure)
        {
            start.ArgumentList.Add("--sin-medir");
        }

        await _estimating.WaitAsync(cancellationToken).ConfigureAwait(true);
        try
        {
            // Reading a large model off the disk for the first time takes its time.
            return await TranslatorAnswerAsync(start, TimeSpan.FromMinutes(6), cancellationToken).ConfigureAwait(true);
        }
        finally
        {
            _estimating.Release();
        }
    }

    private static async Task<JsonObject?> TranslatorAnswerAsync(ProcessStartInfo start, TimeSpan limit, CancellationToken cancellationToken)
    {
        start.RedirectStandardOutput = true;
        start.RedirectStandardError = true;
        start.StandardOutputEncoding = Encoding.UTF8;
        using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        timeout.CancelAfter(limit);
        try
        {
            using Process process = Process.Start(start) ?? throw new InvalidOperationException();
            try
            {
                Task<string> errors = process.StandardError.ReadToEndAsync(timeout.Token);
                string output = await process.StandardOutput.ReadToEndAsync(timeout.Token).ConfigureAwait(true);
                await process.WaitForExitAsync(timeout.Token).ConfigureAwait(true);
                _ = await errors.ConfigureAwait(true);
                return JsonNode.Parse(output) as JsonObject;
            }
            catch (OperationCanceledException)
            {
                process.Kill(entireProcessTree: true);
                return null;
            }
        }
        // AggregateException: Kill of the whole tree, now on the path back to BAXY's own model.
        catch (Exception exception) when (exception is Win32Exception or InvalidOperationException or JsonException or IOException or AggregateException)
        {
            return null;
        }
    }

    private static async Task<int> OllamaContextLengthAsync(string model, CancellationToken cancellationToken)
    {
        using HttpClient http = DirectHttp(5);
        using var body = new StringContent(new JsonObject { ["model"] = model }.ToJsonString(), Encoding.UTF8, "application/json");
        try
        {
            using HttpResponseMessage reply = await http.PostAsync(new Uri(OllamaAddress() + "/api/show"), body, cancellationToken).ConfigureAwait(true);
            string answer = await reply.Content.ReadAsStringAsync(cancellationToken).ConfigureAwait(true);
            return (JsonNode.Parse(answer)?["model_info"] as JsonObject)?
                .Where(static field => field.Key.EndsWith(".context_length", StringComparison.Ordinal))
                .Select(static field => (int?)field.Value)
                .FirstOrDefault() ?? 0;
        }
        catch (Exception exception) when ((exception is HttpRequestException or TaskCanceledException or UriFormatException or JsonException)
            && !cancellationToken.IsCancellationRequested)
        {
            return 0;
        }
    }

    /// <summary>Ollama answering: if it is installed and closed, BAXY opens its server, with no window, and closes it on leaving.</summary>
    private async Task<bool> EnsureOllamaAsync(CancellationToken cancellationToken)
    {
        if (await OllamaAnswersAsync(cancellationToken).ConfigureAwait(true))
        {
            return true;
        }

        string program = Path.Combine(Environment.GetEnvironmentVariable("LOCALAPPDATA") ?? string.Empty, "Programs", "Ollama", "ollama.exe");
        if (!File.Exists(program))
        {
            return false;
        }

        if (_ollama is not { HasExited: false })
        {
            _ollama?.Dispose();
            try
            {
                _ollama = Process.Start(OllamaServer(program));
            }
            catch (Exception exception) when (exception is Win32Exception or InvalidOperationException)
            {
                return false;
            }
        }

        // It answers only after looking for the graphics cards (10 s measured on this PC, under load).
        DateTimeOffset until = DateTimeOffset.UtcNow + TimeSpan.FromSeconds(45);
        while (DateTimeOffset.UtcNow < until && _ollama is { HasExited: false })
        {
            if (await OllamaAnswersAsync(cancellationToken).ConfigureAwait(true))
            {
                return true;
            }

            await Task.Delay(250, cancellationToken).ConfigureAwait(true);
        }

        return false;
    }

    /// <summary>Listening where BAXY calls it and nowhere else, whatever address its variable names.</summary>
    internal static ProcessStartInfo OllamaServer(string program)
    {
        var start = new ProcessStartInfo(program, "serve") { UseShellExecute = false, CreateNoWindow = true };
        start.Environment[OllamaHostVariable] = OllamaAddress();
        return start;
    }

    /// <summary>For what is on this PC: a proxy set here would take it away, and a redirect could too.</summary>
    private static HttpClient DirectHttp(int seconds) =>
        new(new HttpClientHandler { UseProxy = false, AllowAutoRedirect = false }) { Timeout = TimeSpan.FromSeconds(seconds) };

    private static async Task<bool> OllamaAnswersAsync(CancellationToken cancellationToken)
    {
        using HttpClient http = DirectHttp(2);
        try
        {
            using HttpResponseMessage reply = await http.GetAsync(new Uri(OllamaAddress() + "/api/version"), cancellationToken).ConfigureAwait(true);
            return reply.IsSuccessStatusCode;
        }
        catch (Exception exception) when ((exception is HttpRequestException or TaskCanceledException or UriFormatException)
            && !cancellationToken.IsCancellationRequested)
        {
            return false;
        }
    }

    /// <summary>Frees the graphics card right away: BAXY's own model may be about to load.</summary>
    private static void UnloadFromOllama(string model)
    {
        _ = Task.Run(async () =>
        {
            try
            {
                using HttpClient http = DirectHttp(5);
                using var body = new StringContent(new JsonObject { ["model"] = model, ["keep_alive"] = 0 }.ToJsonString(), Encoding.UTF8, "application/json");
                using HttpResponseMessage reply = await http.PostAsync(new Uri(OllamaAddress() + "/api/generate"), body).ConfigureAwait(false);
            }
            catch (Exception exception) when (exception is HttpRequestException or TaskCanceledException or UriFormatException)
            {
                // Ollama ends the model by itself after its wait
            }
        });
    }

    private ProcessStartInfo? TranslatorProcess()
    {
        string? python = Environment.GetEnvironmentVariable(PythonVariable);
        if (string.IsNullOrWhiteSpace(python))
        {
            python = Environment.GetEnvironmentVariable(MindSidecarClient.PythonEnvironmentVariable);
        }

        string? mindPath = Environment.GetEnvironmentVariable(MindSidecarClient.PythonPathEnvironmentVariable);
        if (!File.Exists(python) || string.IsNullOrWhiteSpace(mindPath))
        {
            return null;
        }

        Directory.CreateDirectory(_folder);
        var start = new ProcessStartInfo(python)
        {
            UseShellExecute = false,
            CreateNoWindow = true,
            WorkingDirectory = _folder,
        };
        start.ArgumentList.Add("-m");
        start.ArgumentList.Add("baxy_mind.external_model");
        start.Environment["PYTHONUTF8"] = "1";
        start.Environment["PYTHONPATH"] = mindPath;
        return start;
    }

    private bool TryReadKey(string provider, out string key)
    {
        key = string.Empty;
        if (!File.Exists(KeyPath(provider)))
        {
            return true;
        }

        try
        {
            key = Encoding.UTF8.GetString(Keys.Open(File.ReadAllBytes(KeyPath(provider)), Purpose(provider)));
            return true;
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException or ProtectedPayloadException)
        {
            return false;
        }
    }

    /// <summary>Back to the local model's state: no translator, and the mind's variables as they were before it.</summary>
    internal void Stop()
    {
        StopTranslator();
        foreach ((string name, string? value) in _replaced)
        {
            Environment.SetEnvironmentVariable(name, value);
        }

        _replaced.Clear();
    }

    /// <summary>
    /// What the person left stops being sent now, not when the running turn ends. A mind running on that translator needs
    /// relaunching whatever is chosen next, even the same thing again: its port has nobody there. True when one was stopped.
    /// </summary>
    internal bool Cut()
    {
        bool there = _translator is not null;
        Stop();
        if (there)
        {
            _applied = "cut";
        }

        return there;
    }

    public void Dispose()
    {
        StopTranslator();
        Process? ollama = _ollama;
        _ollama = null;
        if (ollama is null)
        {
            return;
        }

        try
        {
            // With its children: the server's runner holds the graphics card otherwise.
            if (!ollama.HasExited)
            {
                ollama.Kill(entireProcessTree: true);
            }
        }
        catch (Exception exception) when (exception is InvalidOperationException or Win32Exception or AggregateException)
        {
            // already gone
        }
        finally
        {
            ollama.Dispose();
        }
    }

    private void Replace(string name, string value)
    {
        _replaced.TryAdd(name, Environment.GetEnvironmentVariable(name));
        Environment.SetEnvironmentVariable(name, value);
    }

    private string Choice()
    {
        JsonObject config = Config();
        if ((bool?)config["enabled"] != true)
        {
            return "off";
        }

        string provider = ProviderOf(config);
        return string.Join('|', provider, ModelOf(config, provider), UrlOf(config, provider), File.GetLastWriteTimeUtc(KeyPath(provider)).Ticks,
            CeilingOf(config)?.ToString(CultureInfo.InvariantCulture), provider == Local ? ContextOf(config, ModelOf(config, provider)) : null);
    }

    private async Task<bool> RespondsAsync(int port, TimeSpan budget, CancellationToken cancellationToken)
    {
        using HttpClient http = DirectHttp(2);
        DateTimeOffset until = DateTimeOffset.UtcNow + budget;
        while (DateTimeOffset.UtcNow < until && _translator is { HasExited: false })
        {
            try
            {
                using HttpResponseMessage reply = await http
                    .GetAsync(new Uri($"http://127.0.0.1:{port}/health"), cancellationToken).ConfigureAwait(true);
                if (reply.StatusCode == HttpStatusCode.OK)
                {
                    return true;
                }
            }
            catch (Exception exception) when ((exception is HttpRequestException or TaskCanceledException)
                && !cancellationToken.IsCancellationRequested)
            {
                // still starting
            }

            await Task.Delay(200, cancellationToken).ConfigureAwait(true);
        }

        return false;
    }

    private void StopTranslator()
    {
        Process? translator = _translator;
        _translator = null;
        if (_activeLocal && _activeModel is { } loaded)
        {
            UnloadFromOllama(loaded);
        }

        Active = false;
        _activeModel = null;
        _activeLocal = false;
        if (translator is null)
        {
            return;
        }

        try
        {
            if (!translator.HasExited)
            {
                // With its children: its server holds the graphics card otherwise.
                translator.Kill(entireProcessTree: true);
                translator.WaitForExit(2000);
            }

            WaitForItsLog();
        }
        catch (Exception exception) when (exception is InvalidOperationException or Win32Exception or AggregateException)
        {
            // already gone
        }
        finally
        {
            translator.Dispose();
        }
    }

    /// <summary>
    /// Gone before the next one opens its log and its port, and before anyone says it stopped. A virtual environment's
    /// python.exe is a launcher, and what serves is its child, which Windows ends a moment after the launcher: only the
    /// child holds this log, so the log says when it is gone.
    /// </summary>
    private void WaitForItsLog()
    {
        DateTimeOffset until = DateTimeOffset.UtcNow + TimeSpan.FromSeconds(2);
        while (DateTimeOffset.UtcNow < until)
        {
            try
            {
                using var alone = new FileStream(LogPath, FileMode.Open, FileAccess.ReadWrite, FileShare.None);
                return;
            }
            catch (FileNotFoundException)
            {
                return;
            }
            catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
            {
                Thread.Sleep(20);
            }
        }
    }

    /// <summary>
    /// The port the vision's address already names, when it is free: the core read that address when it started, so a
    /// translator on any other port leaves the click's vision asking a server that is gone (a change made while BAXY runs).
    /// </summary>
    private static int TranslatorPort()
    {
        if (int.TryParse(Environment.GetEnvironmentVariable("BAXY_MIND_LLAMA_PORT"), NumberStyles.None, CultureInfo.InvariantCulture, out int pinned))
        {
            try
            {
                using var probe = new TcpListener(IPAddress.Loopback, pinned);
                probe.Start();
                return pinned;
            }
            catch (SocketException)
            {
                // held by something else: the vision goes without, the model does not
            }
        }

        return FreePort();
    }

    private static int FreePort()
    {
        using var probe = new TcpListener(IPAddress.Loopback, 0);
        probe.Start();
        return ((IPEndPoint)probe.LocalEndpoint).Port;
    }

    private double SpentUsd()
    {
        double total = 0;
        foreach (string line in SharedLines(SpendPath))
        {
            try
            {
                total += JsonNode.Parse(line)?["usd"]?.GetValue<double>() ?? 0;
            }
            catch (Exception exception) when (exception is JsonException or InvalidOperationException or FormatException)
            {
                // a line being written
            }
        }

        return Math.Round(total, 4);
    }

    /// <summary>The translator's last line when it is a failure (a refused key, the ceiling); a later call that worked
    /// writes its own line after it. The log holds counts and the API's errors, never a conversation.</summary>
    private string? LastError()
    {
        string? last = SharedLines(LogPath).LastOrDefault(static line => line.Trim().Length > 0);
        return last is not null && (last.StartsWith("ERROR", StringComparison.Ordinal) || last.StartsWith("TOPE", StringComparison.Ordinal))
            ? last
            : null;
    }

    private static List<string> SharedLines(string path)
    {
        var lines = new List<string>();
        try
        {
            using var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete);
            using var reader = new StreamReader(stream, Encoding.UTF8);
            while (reader.ReadLine() is { } line)
            {
                lines.Add(line);
            }
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            // none yet
        }

        return lines;
    }
}
