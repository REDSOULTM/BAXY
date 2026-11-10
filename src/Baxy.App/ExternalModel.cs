using System.ComponentModel;
using System.Diagnostics;
using System.Globalization;
using System.Runtime.InteropServices;
using System.IO;
using System.Net;
using System.Net.Http;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Providers.Windows.SystemStatus;
using Microsoft.Win32.SafeHandles;
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
    internal const int DefaultLocalContext = 78000;
    // The context sizes offered for a model on this PC (external_model.OLLAMA_CHOICES), each up to what it declares.
    internal static readonly int[] ContextChoices = [64000, 78000, 96000, 128000, 200000];
    // What BAXY's prompt takes with its tools and a turn (external_model.OLLAMA_NEEDS).
    internal const int MinimumLocalContext = 52000;
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
    private static readonly string[] PricedModels = [DefaultAnthropicModel, "claude-sonnet-5-5", "claude-fable-5-1"];
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
    // Holds the Ollama BAXY opened (and its runners): Windows ends them when this handle closes, also when BAXY is cut by its PID.
    private SafeFileHandle? _ollamaJob;
    private readonly Dictionary<string, bool> _localSees = [];
    // The names each place listed in this run (Remember): a model asked for without its place is checked against them.
    private readonly Dictionary<string, HashSet<string>> _listed = [];
    private bool? _activeSees;
    private int _activeContext;
    private readonly IGpuStatusProvider _gpu;
    // Measuring and connecting both load the model: at once, each takes the other's load out (gemma4:26b never finished, 2026-11-06).
    private readonly SemaphoreSlim _estimating = new(1, 1);

    /// <param name="gpu">A test's card in place of this PC's.</param>
    internal ExternalModel(string dataRoot, IGpuStatusProvider? gpu = null)
    {
        _folder = Path.Combine(dataRoot, "external-model");
        _gpu = gpu ?? new WindowsGpuStatusProvider();
        Open = new OpenModels(dataRoot);
        Open.OllamaInstalled += LeaveOlderOllama;
    }

    /// <summary>
    /// BAXY's own Ollama is installed: an older one BAXY opened goes, so that the next start opens this one. One the person opened
    /// themselves is theirs, and stays (it holds Ollama's port, and Settings goes on saying its version).
    /// </summary>
    private void LeaveOlderOllama()
    {
        Process? ollama = _ollama;
        try
        {
            if (ollama is { HasExited: false } && !string.Equals(ollama.MainModule?.FileName, Open.OwnOllama, StringComparison.OrdinalIgnoreCase))
            {
                _ollama = null;
                ollama.Kill(entireProcessTree: true);
                ollama.WaitForExit(5000);
                ollama.Dispose();
                _ollamaJob?.Dispose();
                _ollamaJob = null;
            }
        }
        catch (Exception exception) when (exception is InvalidOperationException or Win32Exception or AggregateException)
        {
            // already gone
        }
    }

    /// <summary>The search, Ollama's own install and a model's download (Settings → Model → Local).</summary>
    internal OpenModels Open { get; }

    internal static bool Available => Environment.GetEnvironmentVariable(Variable) != "0";

    internal bool Active { get; private set; }

    /// <summary>Whether the model the mind talks to runs on this PC: BAXY's own, or another one through Ollama; not a company's
    /// API. «Otra» counts as an API even at an address on this PC: it may pass the conversation on, as <c>_apiThisRun</c> says.</summary>
    internal bool ThinksOnThisPc => !Active || _activeLocal;

    internal string? Problem { get; private set; }

    // With Problem «no_cabe_vram»: what the model would take at its context, what was free, and the most that fits
    // (ModelMemory.Recommend), for the view to offer; and whether Ollama could run it partly in RAM (not on BAXY's server).
    private (int Context, long Need, long Free, int? Fitting, bool PartialPossible)? _short;

    /// <summary>The context the chosen tool profile's prompt and a turn take (ToolProfile.NeededContext; the view model sets it):
    /// a model of Ollama with less is not offered nor connected (VIVO1 F4). Completo's measured need when unset.</summary>
    internal Func<int>? Need { get; set; }

    /// <summary>The preset with the most tools that fits a context (ToolProfile.LargestFitting), for a model short of the chosen one.</summary>
    internal Func<int, string?>? Fitting { get; set; }

    /// <summary>What a preset's prompt and a turn take here (ToolProfile.NeededContext with the prefix the mind read).</summary>
    internal Func<string, int>? NeedOf { get; set; }

    internal int NeededNow => Need?.Invoke() ?? ToolProfile.NeededContext(ToolProfile.Completo, null, null);

    internal int NeedFor(string profile) => NeedOf?.Invoke(profile) ?? ToolProfile.NeededContext(profile, null, null);

    /// <summary>Why the translator's model refused the last turn, in the translator's words (ERROR[kind]: its own text, never the
    /// server's): what the screen says of a turn that ended in model_refused (VIVO1 F4). Null if its log ends otherwise.</summary>
    internal string? Refusal => LastError() is { } line && line.StartsWith("ERROR", StringComparison.Ordinal) && line.IndexOf(':', StringComparison.Ordinal) is > 0 and var colon
        ? line[(colon + 1)..].Trim()
        : null;

    /// <summary>The kind of that refusal (ERROR[kind]), for the view to say it in its own language (REV_VISTA V-04: the words are
    /// the translator's Spanish); null for a line with none.</summary>
    internal string? RefusalKind => LastError() is { } line && line.StartsWith("ERROR[", StringComparison.Ordinal)
        && line.IndexOf(']', StringComparison.Ordinal) is > 6 and var end
        ? line[6..end]
        : null;

    /// <summary>For each model of Ollama short of <paramref name="need"/> by its own context, the largest profile that fits it
    /// (<paramref name="fitting"/>), as «profile»: the view offers it (VIVO1 F4). None for one short of tools, or that fits.</summary>
    internal static void WithProfiles(JsonObject listed, int need, Func<int, string?> fitting)
    {
        ArgumentNullException.ThrowIfNull(listed);
        ArgumentNullException.ThrowIfNull(fitting);
        foreach (JsonObject row in (listed["models"] as JsonArray ?? []).OfType<JsonObject>())
        {
            if ((bool?)row["fits"] != true && (int?)row["context"] is > 0 and var context && context < need && fitting(context) is { } profile)
            {
                row["profile"] = profile;
            }
        }
    }

    /// <summary>
    /// MOD1 V-07 (REV_VISTA, 2026-11-09: «Modelos en este PC» said each model's weight on disk and nothing of the card): for each
    /// model of Ollama's that BAXY can use, the video memory it takes at the least context it would be connected with, as
    /// <c>vramBytes</c> at <c>vramContext</c>, from its own files (<c>modelFiles</c>, which no row keeps: no path goes to the
    /// view). That least is what the tool profile's prompt and a turn take (<paramref name="need"/>; for one offered with a
    /// smaller profile, that profile's, <paramref name="needFor"/>), up to what the model declares: it runs there on Ollama, with
    /// its f16 cache and its projector (<see cref="SayVideoMemory"/>). The card's room may give it more context, and more VRAM
    /// with it: the choice of context says that one. Nothing for a model whose files are not read, or that BAXY cannot use.
    /// </summary>
    internal static void WithVideoMemory(JsonObject listed, int need, Func<string, int> needFor)
    {
        ArgumentNullException.ThrowIfNull(listed);
        ArgumentNullException.ThrowIfNull(needFor);
        foreach (JsonObject row in (listed["models"] as JsonArray ?? []).OfType<JsonObject>())
        {
            (GgufShape Shape, long FileBytes, long ProjectorBytes)? files = ModelFiles(row["modelFiles"]);
            row.Remove("modelFiles");
            string? profile = (string?)row["profile"];
            if (files is not { } read || ((bool?)row["fits"] != true && profile is null))
            {
                continue;
            }

            // What Ollama's /api/show declares, else the file's own (<arch>.context_length).
            int declared = (int?)row["context"] is > 0 and var shown ? shown : read.Shape.ContextLength;
            int needed = profile is null ? need : needFor(profile);
            int least = declared > 0 ? Math.Min(needed, declared) : needed;
            row["vramBytes"] = ModelMemory.GpuBytes(read.Shape, read.FileBytes, least, "f16", projectorBytes: read.ProjectorBytes);
            row["vramContext"] = least;
        }
    }

    // A model of Ollama's as its files say it (/api/show's FROM lines): the first whose GGUF header reads is the model, and the
    // rest its projector (a file whose header names no layers). Null with none read, or with a path Windows does not take.
    private static (GgufShape Shape, long FileBytes, long ProjectorBytes)? ModelFiles(JsonNode? paths)
    {
        long fileBytes = 0, projectorBytes = 0;
        GgufShape? shape = null;
        foreach (string path in (paths as JsonArray ?? []).Select(static file => file is JsonValue value && value.TryGetValue(out string? text) ? text : null).OfType<string>())
        {
            try
            {
                if (new FileInfo(path) is not { Exists: true } file)
                {
                    continue;
                }

                if (shape is null && GgufShape.Read(path) is { } read)
                {
                    (shape, fileBytes) = (read, file.Length);
                }
                else
                {
                    projectorBytes += file.Length;
                }
            }
            catch (Exception exception) when (exception is IOException or UnauthorizedAccessException or ArgumentException or NotSupportedException)
            {
                return null;
            }
        }

        return shape is null ? null : (shape, fileBytes, projectorBytes);
    }

    /// <summary>The model chosen in the place chosen, on or off; empty with none.</summary>
    internal string ChosenModel
    {
        get
        {
            JsonObject config = Config();
            return ModelOf(config, ProviderOf(config));
        }
    }

    /// <summary>A tool profile the App put on to use a model of this PC with it («Usar con Esencial», VIVO2 F15), and what the
    /// person had before: lent to that model until its start ends.</summary>
    internal sealed record ProfileLoan(string Model, string Profile, JsonObject Before);

    private readonly Lock _loanLock = new();
    private ProfileLoan? _lent;
    private JsonObject? _profileBack;

    /// <summary>The loan no start has settled yet.</summary>
    internal ProfileLoan? Lent
    {
        get
        {
            lock (_loanLock)
            {
                return _lent;
            }
        }
    }

    /// <summary>The App put <paramref name="profile"/> on to use <paramref name="model"/>; the person had <paramref name="before"/>
    /// (ToolProfile.Json). A loan not settled yet keeps what the person had: the profile now is that loan's, not theirs.</summary>
    internal void Lend(string model, string profile, JsonObject before)
    {
        ArgumentNullException.ThrowIfNull(before);
        lock (_loanLock)
        {
            _lent = new ProfileLoan(model, profile, _lent?.Before ?? (JsonObject)before.DeepClone());
            _profileBack = null;
        }
    }

    /// <summary>The person chose a profile themselves (Settings → Tools): it is theirs, and nothing is given back.</summary>
    internal void ForgetLoan()
    {
        lock (_loanLock)
        {
            _lent = null;
            _profileBack = null;
        }
    }

    /// <summary>
    /// The model's start ended (StartAsync) with <paramref name="loan"/> standing when it began. Connected to that model, the
    /// profile stays. Otherwise BAXY goes on with its own model, which the profile was not for: what the person had is returned
    /// for the caller to put back, and the answer says it («profileBack») until the person's next gesture on a model. Null when
    /// there is nothing to put back: another loan took its place, or the profile now (<paramref name="profileNow"/>) is no
    /// longer the one lent.
    /// </summary>
    internal JsonObject? Settle(ProfileLoan loan, string profileNow)
    {
        ArgumentNullException.ThrowIfNull(loan);
        lock (_loanLock)
        {
            if (!ReferenceEquals(_lent, loan))
            {
                return null;
            }

            _lent = null;
            if ((Active && _activeLocal && _activeModel == loan.Model) || profileNow != loan.Profile)
            {
                return null;
            }

            _profileBack = new JsonObject { ["model"] = loan.Model, ["profile"] = loan.Profile, ["back"] = (string?)loan.Before["profile"] };
            return (JsonObject)loan.Before.DeepClone();
        }
    }

    private JsonObject? ProfileBack()
    {
        lock (_loanLock)
        {
            return (JsonObject?)_profileBack?.DeepClone();
        }
    }

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
        // An empty one written before 2026-11-08 is no choice: Anthropic's default stands (Apply removes it now).
        (string?)config["models"]?[provider] is { Length: > 0 } chosen ? chosen : (provider == Anthropic ? DefaultAnthropicModel : string.Empty);

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
            // The context it connected with (the person's, or the one recommended for the card), not only the one chosen.
            ["activeContext"] = Active && _activeLocal && _activeContext > 0 ? _activeContext : null,
            ["apiThisRun"] = _apiThisRun,
            ["switching"] = Switching,
            ["problem"] = fell ? "traductor_caido" : Problem,
            ["vramShort"] = Problem == ShortOfVram && _short is { } shortOf ? new JsonObject
            {
                ["context"] = shortOf.Context,
                ["needBytes"] = shortOf.Need,
                ["freeBytes"] = shortOf.Free,
                ["fittingContext"] = shortOf.Fitting,
                ["partialPossible"] = shortOf.PartialPossible,
            } : null,
            // Each start rewrites the log, so with this off its last line is an old run's.
            ["lastError"] = (bool?)config["enabled"] == true ? LastError() : null,
            ["context"] = provider == Local ? ContextOf(config, model) : null,
            ["spentUsd"] = SpentUsd(),
            ["ceilingUsd"] = CeilingOf(config),
            ["ceilingHolds"] = provider == Anthropic && PricedModels.Contains(model),
            ["open"] = Open.Json(),
            ["sees"] = Sees(provider, model),
            // VIVO2 F15: the profile put on for a model that did not connect was put back (Settle).
            ["profileBack"] = ProfileBack(),
            // REV_VISTA V-11: what the chosen tool profile's prompt takes, for the view's words (it said a fixed 49,000).
            ["promptTokens"] = NeededNow - LocalContext.TurnRoomTokens,
        };
    }

    /// <summary>What the panel asks: a provider, a model, a URL, a key, forgetting it, or the switch. The refusal's code, or null.</summary>
    internal string? Apply(JsonObject body)
    {
        Directory.CreateDirectory(_folder);
        JsonObject config = Config();
        // Another gesture on a model: what was said of the last one's profile is the last one's.
        if (body.ContainsKey("provider") || body.ContainsKey("model") || body.ContainsKey("enabled") || body.ContainsKey("context") || body.ContainsKey("partialRam"))
        {
            lock (_loanLock)
            {
                _profileBack = null;
            }
        }

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

            // REV_VISTA V-01: a name sent without its place is the chosen place's. One that only another place listed (a model
            // of this PC, with an API chosen) would be asked of the chosen one with its key: the conversation would leave to
            // where the person did not send it. Sent with its place, the place was changed above and is turned on again.
            if (body["provider"] is null && model != ModelOf(config, current) && IsAnothers(current, model))
            {
                return "external_model_other_provider";
            }

            JsonObject models = config["models"] as JsonObject ?? [];
            // Uso real 2026-11-08: an empty name took the place of Anthropic's default, and nothing could be turned on.
            if (model.Length == 0)
            {
                models.Remove(current);
            }
            else
            {
                models[current] = model;
            }

            config["models"] = models;
        }

        // Owner's order 2026-11-09: a model that does not fit the card at its context is loaded only once the person chose to run
        // it partly in RAM, more slowly, at that very context (or chose another context).
        if (body["partialRam"] is JsonValue partial && partial.TryGetValue(out bool runsPartly) && ModelOf(config, current).Length > 0)
        {
            JsonObject accepted = config["partialRam"] as JsonObject ?? [];
            if (runsPartly && ContextOf(config, ModelOf(config, current)) is { } at)
            {
                accepted[ModelOf(config, current)] = at;
            }
            else if (runsPartly && _short is { } shortOf)
            {
                accepted[ModelOf(config, current)] = shortOf.Context;
            }
            else
            {
                accepted.Remove(ModelOf(config, current));
            }

            config["partialRam"] = accepted;
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
            // A start for another choice says its own failure, never the last one's: a start refused before the translator runs
            // (no_cabe_vram) left the last model's line in the log (seen in the real App, 2026-11-09).
            try
            {
                File.Delete(LogPath);
            }
            catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
            {
                // still held by a translator that is ending: its line is said until the next start rewrites it
            }
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
        JsonObject? measured = null;
        long? free = null;
        if (provider == Local)
        {
            // Measured first, with BAXY's own model gone: the translator then knows what this one needs, and nothing takes it out afterwards.
            if (await EnsureOllamaAsync(cancellationToken).ConfigureAwait(true))
            {
                measured = await MeasuredAsync(model, UrlOf(config, provider), measure: true, cancellationToken).ConfigureAwait(true);
            }

            // Nothing chosen: the context recommended for this card (its own when it fits, ModelMemory.Recommend), with BAXY's
            // own model already gone from it; without the model's files, BAXY's default.
            free = measured is null ? null : (await CardAsync(0, cancellationToken).ConfigureAwait(true))?.Free;
            int? chosen = ContextOf(config, model);
            int? accepted = (int?)(config["partialRam"] as JsonObject)?[model];
            if (measured is not null)
            {
                // The context it will connect with is among the options measured, so its VRAM is said and checked.
                SayVideoMemory(measured, free, chosen ?? accepted, CommitFreeBytes(), NeededNow);
            }

            context = ConnectContext(chosen, accepted, measured, NeededNow);
            // Owner's order 2026-11-09: never load what its own estimate says does not fit without saying so first (gpt-oss crashed
            // Ollama's runner 9 times on this PC). Said with what it needs and what is free; the person picks a context that fits,
            // or, on Ollama, to run it partly in RAM at this context.
            if (ShortOfVramFor(measured, context, free, accepted) is { } shortOf)
            {
                _short = shortOf;
                Problem = ShortOfVram;
                return;
            }
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
            arguments.AddRange(["--contexto", context.ToString(CultureInfo.InvariantCulture), "--estimaciones", Path.Combine(_folder, "estimaciones.json"),
                "--necesita", NeededNow.ToString(CultureInfo.InvariantCulture)]);
            arguments.AddRange(MemoryArguments(measured, context, free, (int?)(config["partialRam"] as JsonObject)?[model]));
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
        _activeSees = await TranslatorSeesAsync(port, cancellationToken).ConfigureAwait(true);
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

    /// <summary>What this key or this PC can use, for the list in Settings: the translator's own answer (asking costs nothing).
    /// With <paramref name="onThisPc"/>, Ollama's models whatever place is chosen: «Modelos en este PC» lists them all (user
    /// test of INT17, 2026-11-09: with De serie chosen it said 1 though 6 were installed).</summary>
    internal async Task<JsonObject> ModelsAsync(CancellationToken cancellationToken, bool onThisPc = false)
    {
        JsonObject config = Config();
        string provider = onThisPc ? Local : ProviderOf(config);
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
        int need = NeededNow;
        if (provider == Local)
        {
            start.ArgumentList.Add("--necesita");
            start.ArgumentList.Add(need.ToString(CultureInfo.InvariantCulture));
        }

        if (url.Length > 0)
        {
            start.ArgumentList.Add("--url");
            start.ArgumentList.Add(url);
        }

        start.Environment[provider == Anthropic ? "ANTHROPIC_API_KEY" : "BAXY_EXTERNAL_API_KEY"] = key;
        JsonObject listed = await TranslatorAnswerAsync(start, TimeSpan.FromSeconds(45), cancellationToken).ConfigureAwait(true)
            ?? new JsonObject { ["error"] = "no se pudo leer la lista" };
        Remember(provider, listed);
        if (provider == Local)
        {
            WithProfiles(listed, need, Fitting ?? (static _ => null));
            // Each offered profile's need is read here, and the files' headers away from the window's thread.
            Dictionary<string, int> needs = (listed["models"] as JsonArray ?? []).OfType<JsonObject>()
                .Select(static row => (string?)row["profile"]).OfType<string>().Distinct(StringComparer.Ordinal)
                .ToDictionary(static profile => profile, NeedFor, StringComparer.Ordinal);
            await Task.Run(() => WithVideoMemory(listed, need, profile => needs[profile]), cancellationToken).ConfigureAwait(true);
            // What each model of Ollama says of its vision (/api/show «capabilities»), for Json's «sees».
            foreach (JsonObject row in (listed["models"] as JsonArray ?? []).OfType<JsonObject>())
            {
                if ((string?)row["id"] is { } id && row["vision"] is JsonValue sees && sees.TryGetValue(out bool value))
                {
                    _localSees[id] = value;
                }
            }
        }

        return listed;
    }

    /// <summary>Keeps the names a place just listed; an answer without a list (no key, no network) leaves the last one known.</summary>
    internal void Remember(string provider, JsonObject listed)
    {
        if (listed["models"] is JsonArray models)
        {
            _listed[provider] = [.. models.OfType<JsonObject>().Select(row => (string?)row["id"]).OfType<string>()];
        }
    }

    /// <summary>Whether another place listed this name and <paramref name="provider"/> did not (its list unread counts as not).</summary>
    private bool IsAnothers(string provider, string model) =>
        !(_listed.TryGetValue(provider, out HashSet<string>? own) && own.Contains(model))
        && _listed.Any(other => other.Key != provider && other.Value.Contains(model));

    /// <summary>
    /// Whether the chosen model takes images: Claude's, OpenAI's and Gemini's current models do (their models pages; Claude's API
    /// says it of each one, external_model.connection_problem); one in Ollama says it of itself; another API's is not known (null).
    /// Without it BAXY describes no capture and finds no control by its image, and says so (CaptureVisionAdapter).
    /// </summary>
    private bool? Sees(string provider, string model) =>
        Active && _activeModel == model ? _activeSees
        : provider == Local && _localSees.TryGetValue(model, out bool sees) ? sees
        : null;

    /// <summary>What the translator says of its model's vision (its /props «vision»: the API's own word, or what a refused image said).</summary>
    private static async Task<bool?> TranslatorSeesAsync(int port, CancellationToken cancellationToken)
    {
        using HttpClient http = DirectHttp(5);
        try
        {
            string props = await http.GetStringAsync(new Uri($"http://127.0.0.1:{port}/props"), cancellationToken).ConfigureAwait(true);
            return JsonNode.Parse(props)?["vision"] is JsonValue vision && vision.TryGetValue(out bool sees) ? sees : null;
        }
        catch (Exception exception) when ((exception is HttpRequestException or TaskCanceledException or JsonException)
            && !cancellationToken.IsCancellationRequested)
        {
            return null;
        }
    }

    /// <summary>Removes a model of Ollama, never the one connected (OpenModels.RemoveAsync); the refusal's code, or null.</summary>
    internal async Task<string?> RemoveModelAsync(string name, CancellationToken cancellationToken)
    {
        string? refused = await Open.RemoveAsync(name, Active ? _activeModel : null, EnsureOllamaAsync, cancellationToken).ConfigureAwait(true);
        if (refused is null)
        {
            _localSees.Remove(name);
            if (_listed.TryGetValue(Local, out HashSet<string>? onThisPc))
            {
                onThisPc.Remove(name);
            }

            JsonObject config = Config();
            if (ProviderOf(config) == Local && ModelOf(config, Local) == name)
            {
                _ = Apply(new JsonObject { ["model"] = string.Empty, ["enabled"] = false });
            }
        }

        return refused;
    }

    /// <summary>What Hugging Face has under these words, each said against the VRAM free for it on this PC's largest graphics
    /// card (<see cref="CardAsync"/>). The card's use is read beside the search, not before it: it reads every process's
    /// counters (1.0-1.6 s on the PC, INT12V), and the search waits on Hugging Face that long anyway.</summary>
    /// <param name="ownModelGb">What BAXY's own model takes now on the card, being read: it goes when another connects.</param>
    /// <param name="ownModelCommitGb">And what its processes hold of what Windows can promise, which a switch frees too.</param>
    internal async Task<JsonObject> SearchAsync(string words, Task<double?> ownModelGb, CancellationToken cancellationToken, Task<double?>? ownModelCommitGb = null)
    {
        Task<(long Total, long? Free)?> card = FreeForAnotherAsync(ownModelGb, cancellationToken);
        Task<(long? Vram, long? Commit)> room = RoomAsync(card, ownModelGb, ownModelCommitGb ?? Task.FromResult<double?>(null));
        // Against the chosen profile's need, as a connection goes; a model short of it, with the profile that fits it (Fitting).
        JsonObject found = await Open.SearchAsync(words, room, cancellationToken, NeededNow,
            context => Fitting?.Invoke(context) is { } profile ? (profile, NeedFor(profile)) : null).ConfigureAwait(false);
        if (await card.ConfigureAwait(false) is { } known)
        {
            found["vramTotalBytes"] = known.Total;
            found["vramFreeBytes"] = known.Free;
        }

        found["ramFreeBytes"] = (await room.ConfigureAwait(false)).Commit;

        return found;
    }

    // The VRAM free for another model and what Windows can promise for it: now, and what BAXY's own model frees of it when another
    // connects (CommitForAnother).
    private static async Task<(long? Vram, long? Commit)> RoomAsync(Task<(long Total, long? Free)?> card, Task<double?> ownModelGb, Task<double?> ownModelCommitGb)
    {
        long? free = (await card.ConfigureAwait(false))?.Free;
        return (free, CommitForAnother(CommitFreeBytes(), await ownModelGb.ConfigureAwait(false), await ownModelCommitGb.ConfigureAwait(false)));
    }

    /// <summary>What Windows can promise another model: what it can now (<paramref name="promised"/>, null when it does not say) and
    /// what BAXY's own model holds of it, which a switch frees: its processes' private bytes, or at least its VRAM (WDDM backs it
    /// 1:1, measured 2026-11-09). Seen in the real App: its llama-server held 6.7 GB for 4.8 GB of VRAM.</summary>
    internal static long? CommitForAnother(long? promised, double? ownVramGb, double? ownCommitGb) =>
        promised is { } now ? now + (long)((ownCommitGb ?? ownVramGb ?? 0) * (1L << 30)) : null;

    private async Task<(long Total, long? Free)?> FreeForAnotherAsync(Task<double?> ownModelGb, CancellationToken cancellationToken)
    {
        long held = await OllamaHeldBytesAsync(cancellationToken).ConfigureAwait(false);
        double? own = await ownModelGb.ConfigureAwait(false);
        return await CardAsync((own ?? 0) + (held / (double)(1L << 30)), cancellationToken).ConfigureAwait(false);
    }

    /// <summary>
    /// This PC's largest graphics card: its memory, and what is free on it for a model once <paramref name="goingGb"/> has gone
    /// (BAXY's own model, or the one connected now): the card's total less what Windows says is in use on it, all processes
    /// counted (the desktop's and other programs' too). Null with no card that says its memory.
    /// </summary>
    internal async Task<(long Total, long? Free)?> CardAsync(double? goingGb, CancellationToken cancellationToken)
    {
        GpuStatusSnapshot gpu = await _gpu.GetStatusAsync(GpuStatusScope.Usage, cancellationToken).ConfigureAwait(false);
        if (gpu.Adapters.MaxBy(static adapter => adapter.DedicatedVideoMemoryBytes) is not { DedicatedVideoMemoryBytes: > 0 } card)
        {
            return null;
        }

        long total = (long)card.DedicatedVideoMemoryBytes;
        long? free = card.DedicatedMemoryUsageBytes is { } used
            ? (long)Math.Clamp(total - (double)used + ((goingGb ?? 0) * (1L << 30)), 0, total)
            : null;
        return (total, free);
    }

    /// <summary>This PC's largest graphics card's memory, or null with none that says it (its identity only: nothing sampled).</summary>
    internal async Task<long?> CardTotalAsync(CancellationToken cancellationToken)
    {
        GpuStatusSnapshot gpu = await _gpu.GetStatusAsync(GpuStatusScope.Identity, cancellationToken).ConfigureAwait(false);
        return gpu.Adapters.Select(static adapter => (long)adapter.DedicatedVideoMemoryBytes).Where(static bytes => bytes > 0)
            .DefaultIfEmpty().Max() is var total and > 0 ? total : null;
    }

    /// <summary>What Windows can still promise (RAM and page file; a model's memory on the card counts against it too), as the
    /// translator reads it (external_model.commit_free, GlobalMemoryStatusEx's ullAvailPageFile); null when it does not say.</summary>
    internal static long? CommitFreeBytes()
    {
        var status = new MemoryStatus { Length = (uint)Marshal.SizeOf<MemoryStatus>() };
        return GlobalMemoryStatusEx(ref status) ? (long)status.AvailPageFile : null;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct MemoryStatus
    {
        public uint Length;
        public uint MemoryLoad;
        public ulong TotalPhys;
        public ulong AvailPhys;
        public ulong TotalPageFile;
        public ulong AvailPageFile;
        public ulong TotalVirtual;
        public ulong AvailVirtual;
        public ulong AvailExtendedVirtual;
    }

    [DllImport("kernel32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool GlobalMemoryStatusEx(ref MemoryStatus status);

    /// <summary>BAXY's own Ollama while a model of it is in use, for the model's readings (FieldTelemetrySampler); null otherwise,
    /// or when the Ollama running is not one BAXY opened.</summary>
    internal int? OwnOllamaInUse => Active && _activeLocal && _ollama is { HasExited: false } ollama ? ollama.Id : null;

    /// <summary>What the models Ollama has loaded hold on the card (its /api/ps size_vram), 0 when it does not answer: one
    /// that is loaded goes when another is chosen.</summary>
    private static async Task<long> OllamaHeldBytesAsync(CancellationToken cancellationToken)
    {
        try
        {
            using HttpClient http = DirectHttp(2);
            string listing = await http.GetStringAsync(new Uri(OllamaAddress() + "/api/ps"), cancellationToken).ConfigureAwait(false);
            return (JsonNode.Parse(listing)?["models"] as JsonArray ?? []).Sum(static model => (long?)model?["size_vram"] ?? 0);
        }
        catch (Exception failure) when (failure is HttpRequestException or TaskCanceledException or JsonException && !cancellationToken.IsCancellationRequested)
        {
            return 0;
        }
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
        // What goes when another context connects: BAXY's own model, Ollama's, or this model on BAXY's server, which Ollama does
        // not see (by Ollama's own count, which is under what the card holds: the free VRAM is never over).
        double going = (ownModelGb ?? 0) * (1L << 30) + ((long?)answer["loadedBytes"] ?? 0);
        if (Active && _activeLocal && _activeContext > ((int?)answer["contextLength"] ?? int.MaxValue))
        {
            going += (answer["options"] as JsonArray)?
                .FirstOrDefault(option => (int?)option?["context"] == _activeContext)?["bytes"]?.GetValue<long>() ?? 0;
        }

        (long Total, long? Free)? card = await CardAsync(going / (1L << 30), cancellationToken).ConfigureAwait(false);
        long? commitFree = (long?)answer["commitFreeBytes"] is { } promised
            ? promised + (long)((going * 1.2) + ((ownModelRamGb ?? 0) * (1L << 30))) : null;
        SayVideoMemory(answer, card?.Free, commitFree: commitFree, need: NeededNow);
        // What the chosen profile's prompt takes, for the view's «Deja unos N tokens para la conversación» (VIVO2: a fixed 49,000
        // went negative once a smaller profile's context could be recommended).
        answer["promptTokens"] = NeededNow - LocalContext.TurnRoomTokens;
        if (card is { } known)
        {
            answer["vramTotalBytes"] = known.Total;
            if (known.Free is { } free)
            {
                answer["vramFreeBytes"] = free;
                // It counts on the card and in what Windows can promise (external_model.COMMIT_PER_BYTE): free too once the other model is gone.
                if (commitFree is { } freed)
                {
                    answer["commitFreeBytes"] = freed;
                }
            }
        }

        return answer;
    }

    /// <summary>
    /// Each context option's VRAM from the model's own files (the translator's modelFiles, where Ollama keeps them; ModelMemory),
    /// as it will run: up to what the model declares, Ollama with its f16 cache and its projector (a file whose header names no
    /// layers); past it, BAXY's own llama-server with the mind's q8_0 cache and no projector (external_model.Engine). Without a
    /// readable file the options keep Ollama's own count, and say so (<c>bytesFrom</c>). With the files read, the context
    /// recommended for the <paramref name="free"/> VRAM (ModelMemory.Recommend: its own when it fits) is <c>recommended</c>,
    /// with <c>recommendedWhy</c> and the view's <c>contexts</c>, never under <paramref name="need"/>: what the chosen tool
    /// profile's prompt and a turn take (<see cref="NeededNow"/>), so a short model used with a smaller profile is offered what it
    /// declares and not BAXY's least for its whole catalog (VIVO2: mistral with Esencial was refused at 52,000).
    /// </summary>
    internal static void SayVideoMemory(JsonObject answer, long? free = null, int? chosen = null, long? commitFree = null, int need = MinimumLocalContext)
    {
        // With no file read (or a path Windows does not take) the options keep Ollama's count.
        (GgufShape Shape, long FileBytes, long ProjectorBytes)? files = ModelFiles(answer["modelFiles"]);
        answer.Remove("modelFiles");
        if (files is not { } read || answer["options"] is not JsonArray options)
        {
            answer["bytesFrom"] = "ollama";
            return;
        }

        (GgufShape shape, long fileBytes, long projectorBytes) = read;
        // What Ollama's /api/show declares, else the file's own (<arch>.context_length).
        int declared = (int?)answer["contextLength"] is > 0 and var shown ? shown : shape.ContextLength;
        long At(int context)
        {
            bool onOllama = declared <= 0 || context <= declared;
            return ModelMemory.GpuBytes(shape, fileBytes, context, onOllama ? "f16" : "q8_0", projectorBytes: onOllama ? projectorBytes : 0);
        }

        var offered = new List<int>();
        foreach (JsonObject option in options.OfType<JsonObject>())
        {
            if ((int?)option["context"] is { } context)
            {
                option["bytes"] = At(context);
                offered.Add(context);
            }
        }

        // What it may take is the VRAM free, and no more than Windows can promise for the translator's own check (seen in the real
        // App, 2026-11-09: llama3.2:3b recommended at the most the card held, then refused for RAM). This estimate is never under
        // Ollama's own count, so what it recommends passes that check.
        long? room = ModelMemory.Room(free, commitFree);
        JsonObject contexts = ModelMemory.ContextJson(At, declared, need, room, chosen is { } asked ? offered.Append(asked) : offered);
        if (chosen is { } picked && !offered.Contains(picked))
        {
            options.Add(new JsonObject { ["context"] = picked, ["bytes"] = At(picked) });
            offered.Add(picked);
        }

        int recommended = (int?)contexts["recommended"] ?? DefaultLocalContext;
        if (!offered.Contains(recommended))
        {
            options.Add(new JsonObject { ["context"] = recommended, ["bytes"] = At(recommended) });
        }

        answer["recommended"] = recommended;
        answer["recommendedWhy"] = (string?)contexts["why"];
        answer["contexts"] = contexts;
        answer["bytesFrom"] = "cabecera";
    }

    /// <summary>
    /// The context a model of Ollama connects with. The one the person chose, if it holds what the tool profile needs
    /// (<paramref name="need"/>); else the one they accepted to run partly in RAM (VIVO2: the recommendation moves once the mind
    /// reads the chosen profile's prompt, and the yes was for that context), if it still holds the need, is no more than the model
    /// declares and nothing fits the card whole; else what the card recommends (<see cref="SayVideoMemory"/>); else BAXY's default.
    /// Both are kept per model, so a bigger profile or a freer card afterwards must not connect it short of its prompt or in RAM.
    /// </summary>
    internal static int ConnectContext(int? chosen, int? partialAccepted, JsonObject? measured, int need)
    {
        if (chosen is { } own && own >= need)
        {
            return own;
        }

        int declared = (int?)measured?["contextLength"] ?? 0;
        if (partialAccepted is { } accepted && accepted >= need && (declared <= 0 || accepted <= declared)
            && (string?)measured?["recommendedWhy"] == "no_cabe")
        {
            return accepted;
        }

        return (string?)measured?["bytesFrom"] == "cabecera" && (int?)measured?["recommended"] is > 0 and var fitting ? fitting : DefaultLocalContext;
    }

    // A model too big for the card at its context, not loaded until the person chooses (Json's «vramShort»).
    internal const string ShortOfVram = "no_cabe_vram";

    /// <summary>
    /// Whether a model of Ollama's must not load at <paramref name="context"/> yet: its estimate (SayVideoMemory, from its files)
    /// is over the <paramref name="free"/> VRAM and the person did not choose to run it partly in RAM at that context
    /// (<paramref name="partialAccepted"/>). Then what it needs, what is free, the most that fits (null when none does) and whether
    /// Ollama could split it (up to what the model declares; past it BAXY's own server keeps every layer on the card). Null
    /// when it may load, or when there is no estimate or no free VRAM to go by.
    /// </summary>
    internal static (int Context, long Need, long Free, int? Fitting, bool PartialPossible)? ShortOfVramFor(
        JsonObject? measured, int context, long? free, int? partialAccepted)
    {
        if ((string?)measured?["bytesFrom"] != "cabecera" || free is not { } room || partialAccepted == context
            || (measured?["options"] as JsonArray)?.OfType<JsonObject>().FirstOrDefault(option => (int?)option["context"] == context)?["bytes"]
                ?.GetValue<long>() is not { } need || need <= room)
        {
            return null;
        }

        int declared = (int?)measured["contextLength"] ?? 0;
        int? fitting = (string?)measured["recommendedWhy"] is "nativo" or "tarjeta" ? (int?)measured["recommended"] : null;
        return (context, need, room, fitting, declared <= 0 || context <= declared);
    }

    /// <summary>
    /// What the translator checks the RAM by when a model of Ollama's connects at <paramref name="context"/> (external_model's
    /// connect_memory_problem): «--en-parte» when the person chose to run it partly in RAM at that context; BAXY's estimate from
    /// the model's files there (SayVideoMemory, the figure the view shows); and «--entero» when the estimate at that context, from
    /// the files or Ollama's own count, fits the <paramref name="free"/> VRAM, as the view counts it. Without them the translator
    /// goes by Ollama's measure or the file, and by the larger rule (INT18 blind review: a refused or failed measure left the file
    /// alone, whole on the card).
    /// </summary>
    internal static IEnumerable<string> MemoryArguments(JsonObject? measured, int context, long? free, int? partialAccepted)
    {
        bool partial = partialAccepted == context;
        if (partial)
        {
            yield return "--en-parte";
        }

        long? need = (measured?["options"] as JsonArray)?.OfType<JsonObject>()
            .FirstOrDefault(option => (int?)option["context"] == context)?["bytes"]?.GetValue<long>();
        if ((string?)measured?["bytesFrom"] == "cabecera" && need is { } estimate)
        {
            yield return "--vram-bytes";
            yield return estimate.ToString(CultureInfo.InvariantCulture);
        }

        if (!partial && need is { } fits && free is { } room && fits <= room)
        {
            yield return "--entero";
        }
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
    internal async Task<bool> EnsureOllamaAsync(CancellationToken cancellationToken)
    {
        if (await OllamaAnswersAsync(cancellationToken).ConfigureAwait(true))
        {
            return true;
        }

        if (Open.OllamaProgram() is not { } program)
        {
            return false;
        }

        if (_ollama is not { HasExited: false })
        {
            _ollama?.Dispose();
            _ollamaJob?.Dispose();
            try
            {
                _ollama = StartOwned(OllamaServer(program), out _ollamaJob);
            }
            catch (Exception exception) when (exception is Win32Exception or InvalidOperationException)
            {
                _ollama = null;
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

    /// <summary>
    /// Listening where BAXY calls it and nowhere else, whatever address its variable names; run from its own folder, never from
    /// BAXY's (INT12V 2026-11-08: one inheriting the App's folder as its working directory kept that folder from being removed).
    /// </summary>
    internal static ProcessStartInfo OllamaServer(string program)
    {
        var start = new ProcessStartInfo(program, "serve")
        {
            UseShellExecute = false,
            CreateNoWindow = true,
            WorkingDirectory = Path.GetDirectoryName(Path.GetFullPath(program)) ?? string.Empty,
        };
        start.Environment[OllamaHostVariable] = OllamaAddress();
        return start;
    }

    /// <summary>
    /// A process BAXY opens and must not outlive it, in a kill-on-close job with no breakaway, so what it starts (Ollama's runners)
    /// goes with it: closing BAXY ends it (<see cref="Dispose"/>), and so does BAXY ending any other way, its handle closed by Windows
    /// (the sidecars' WindowsKillOnCloseJob; JOBOBJECT_BASIC_LIMIT_INFORMATION, learn.microsoft.com/windows/win32/api/winnt/ns-winnt-jobobject_basic_limit_information).
    /// Without a job it still runs, and Dispose still ends it.
    /// </summary>
    internal static Process StartOwned(ProcessStartInfo start, out SafeFileHandle? job)
    {
        Process process = Process.Start(start) ?? throw new InvalidOperationException("the process did not start");
        try
        {
            job = WindowsKillOnCloseJob.CreateAndAssign(process, allowBreakaway: false);
        }
        catch (InvalidOperationException)
        {
            job = null;
        }

        return process;
    }

    /// <summary>For what is on this PC: a proxy set here would take it away, and a redirect could too.</summary>
    private static HttpClient DirectHttp(int seconds) =>
        new(new HttpClientHandler { UseProxy = false, AllowAutoRedirect = false }) { Timeout = TimeSpan.FromSeconds(seconds) };

    private async Task<bool> OllamaAnswersAsync(CancellationToken cancellationToken)
    {
        using HttpClient http = DirectHttp(2);
        try
        {
            using HttpResponseMessage reply = await http.GetAsync(new Uri(OllamaAddress() + "/api/version"), cancellationToken).ConfigureAwait(true);
            if (reply.IsSuccessStatusCode)
            {
                // Which one answers: an Ollama older than the one BAXY installs may not load today's models (Settings offers BAXY's).
                try
                {
                    Open.RunningVersion = (string?)JsonNode.Parse(await reply.Content.ReadAsStringAsync(cancellationToken).ConfigureAwait(true))?["version"];
                }
                catch (JsonException)
                {
                    Open.RunningVersion = null;
                }
            }

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
        Open.Dispose();
        Process? ollama = _ollama;
        _ollama = null;
        SafeFileHandle? job = _ollamaJob;
        _ollamaJob = null;
        using (job)
        {
            EndOllama(ollama);
        }
    }

    private static void EndOllama(Process? ollama)
    {
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
            CeilingOf(config)?.ToString(CultureInfo.InvariantCulture), provider == Local ? ContextOf(config, ModelOf(config, provider)) : null,
            // Choosing to run it partly in RAM is a new start too (ShortOfVramFor).
            provider == Local ? (int?)(config["partialRam"] as JsonObject)?[ModelOf(config, provider)] : null);
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
