using System.Globalization;
using System.IO;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace Baxy.App;

/// <summary>
/// Settings → Model → Context (owner's order of 2026-11-08, 00_IDENTIDAD «Abierto y personalizable»): the context BAXY's own
/// model runs with, stock or tuned (both are Qwen3.5-4B on the mind's llama-server), picked from fixed presets and kept in
/// &lt;data&gt;\local-context.v1.json. «Automático» keeps no file and gives the mind nothing: the mind then takes the cells
/// measured to fit 4 GB on its backend (llm_server.default_context), as before this setting existed. A preset goes to the
/// mind as BAXY_RENEW_CTX, which llama-server takes at its start («-c»): a change relaunches the mind once the running turn
/// ends (MainWindowViewModel.LocalContextChanged), as a change of model does. Another model (ExternalModel) sets its own
/// context, and this one is not applied while it runs.
/// </summary>
internal sealed class LocalContext
{
    internal const string FileName = "local-context.v1.json";
    internal const string Variable = "BAXY_RENEW_CTX";

    // What the mind keeps for a turn beside the prompt prefix: its reply and one result (mind.py TURN_ROOM_TOKENS).
    internal const int TurnRoomTokens = 3584;

    // The cells llm_server.default_context gives each backend with the product's q8_0 cache (CUDA_CONTEXT with the output
    // matrix in RAM, VULKAN_CONTEXT, CONTEXT); tests/test_mind_contexto_servidor.py holds them equal.
    internal const int CudaAutomatic = 77824;
    internal const int VulkanAutomatic = 61440;
    internal const int ProcessorAutomatic = 53248;

    // Multiples of 4,096 up to the 262,144 Qwen3.5-4B was trained for (its GGUF's qwen35.context_length, the stock one and
    // the tuned one); each automatic value is one of them.
    internal static readonly int[] Presets = [32768, 45056, 53248, 61440, 65536, 77824, 98304, 131072, 196608, 262144];

    // Perfiles de herramientas: the smallest preset the full catalog's prefix fits with a turn (49,086 tokens measured on
    // 2026-11-08 with Qwen3.5's tokenizer and the GGUF's template, + 3,584 = 52,670). The floor while no mind has told its
    // prefix, and what a change of tool profile keeps (ToolProfile): a smaller one may not fit the next profile's tools.
    internal const int FitsEveryProfile = 53248;

    // The model's budget on the graphics card (identity: BAXY works from 4 GB of VRAM), said when the person's is not known.
    private const long BudgetBytes = 4096L << 20;

    // A q8_0 cache past 1 GiB on an RX 7600 (62,464 cells or more) ran ~4 times slower (ft_v1/c5/INFORME_60.md).
    private const int VulkanSlowCells = 62464;

    // What the mind leaves free beside the server and the projector before it puts the projector on the card
    // (llm_server.projector_placement): the same 300 MiB it had.
    private const long VisionMarginBytes = 300L << 20;

    // The mind reads here the VRAM the projector needs free, the server's included, at the context it starts with.
    internal const string VisionNeedsVariable = "BAXY_VISION_GPU_NEEDS_MIB";

    private readonly string _path;
    private readonly object _sync = new();
    // What the environment had before this setting gave the mind anything (a bench's own BAXY_RENEW_CTX, or none):
    // «Automático» puts it back.
    private bool _captured;
    private string? _inherited;
    // The choice the last ApplyEnvironment gave the mind, and the one the running mind came up with on BAXY's own model
    // (null with none, or with another model, which does not run it).
    private string? _given;
    private string? _applied;
    // The header of each file of BAXY's own (the mind's, and the stock and tuned ones' for their rows), read once per size.
    private readonly Dictionary<string, (long Bytes, GgufShape? Shape)> _models = new(StringComparer.OrdinalIgnoreCase);

    internal LocalContext(string dataRoot)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(dataRoot);
        _path = Path.Combine(dataRoot, FileName);
    }

    /// <summary>The fewest cells a context needs for the prompt prefix and one turn beside it: less does not serve.</summary>
    internal static int MinimumContext(int prefixTokens) => prefixTokens + TurnRoomTokens;

    /// <summary>The cells the mind takes on this backend with nothing chosen (llm_server.default_context); null when the
    /// backend is not known yet.</summary>
    internal static int? Automatic(string? backend) => backend switch
    {
        "cuda" => CudaAutomatic,
        "vulkan" => VulkanAutomatic,
        "cpu" => ProcessorAutomatic,
        _ => null,
    };

    /// <summary>The preset the person chose, or null for «Automático».</summary>
    internal int? Chosen()
    {
        lock (_sync)
        {
            return Read();
        }
    }

    /// <summary>
    /// The person's change: <c>context</c> one of <see cref="Presets"/>, or null for «Automático». With the prompt prefix
    /// known (<paramref name="prefixTokens"/>), one with no room for it and a turn is refused. Null when kept, or why it was
    /// refused (nothing is kept then).
    /// </summary>
    internal string? Apply(JsonObject body, int? prefixTokens)
    {
        ArgumentNullException.ThrowIfNull(body);
        if (!body.ContainsKey("context"))
        {
            return "local_context_invalid";
        }

        int? context = null;
        if (body["context"] is { } given)
        {
            if (given is not JsonValue value || !value.TryGetValue(out int cells) || !Presets.Contains(cells))
            {
                return "local_context_invalid";
            }

            context = cells;
        }

        if (context is { } asked && asked < Floor(prefixTokens))
        {
            return "local_context_too_small";
        }

        lock (_sync)
        {
            try
            {
                if (context is null)
                {
                    File.Delete(_path);
                }
                else
                {
                    Directory.CreateDirectory(Path.GetDirectoryName(_path)!);
                    string temporary = _path + ".tmp";
                    File.WriteAllText(temporary, new JsonObject { ["context"] = context }.ToJsonString());
                    File.Move(temporary, _path, overwrite: true);
                }
            }
            catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
            {
                return "local_context_not_saved";
            }

            return null;
        }
    }

    /// <summary>Another tool profile was chosen: a preset smaller than <see cref="FitsEveryProfile"/> goes back to
    /// «Automático» (true when it did), so the next mind's prefix always fits.</summary>
    internal bool KeepForEveryProfile()
    {
        lock (_sync)
        {
            if (Read() is not { } chosen || chosen >= FitsEveryProfile)
            {
                return false;
            }

            try
            {
                File.Delete(_path);
                return true;
            }
            catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
            {
                return false;
            }
        }
    }

    // The fewest cells a choice may have: the running prefix's need, or before one is known, what every profile fits.
    private static int Floor(int? prefixTokens) => prefixTokens is { } prefix ? MinimumContext(prefix) : FitsEveryProfile;

    /// <summary>Before a mind starts on BAXY's own model: the chosen preset in BAXY_RENEW_CTX, or with «Automático» what
    /// was there before, and the VRAM the projector needs free beside the server at that context
    /// (<see cref="VisionNeedsVariable"/>) on <paramref name="backend"/>, the last one a mind said (NVIDIA's before any).</summary>
    internal void ApplyEnvironment(string? backend = null)
    {
        lock (_sync)
        {
            if (!_captured)
            {
                _inherited = Environment.GetEnvironmentVariable(Variable);
                _captured = true;
            }

            int? chosen = Read();
            _given = Key(chosen);
            Environment.SetEnvironmentVariable(Variable, chosen?.ToString(CultureInfo.InvariantCulture) ?? _inherited);
            string running = backend ?? "cuda";
            int context = int.TryParse(Environment.GetEnvironmentVariable(Variable), NumberStyles.Integer, CultureInfo.InvariantCulture, out int given) && given > 0
                ? given : Automatic(running) ?? CudaAutomatic;
            long? needs = ServerBytes(Model(), context, running) is { } server && ProjectorBytes() is { } projector
                ? server + projector + VisionMarginBytes : null;
            Environment.SetEnvironmentVariable(VisionNeedsVariable, needs is { } bytes ? (bytes >> 20).ToString(CultureInfo.InvariantCulture) : null);
        }
    }

    /// <summary>A mind came up, on BAXY's own model or not (<paramref name="ownModel"/>).</summary>
    internal void Started(bool ownModel)
    {
        lock (_sync)
        {
            _applied = ownModel ? _given : null;
        }
    }

    /// <summary>A mind on BAXY's own model came up with another choice than the one kept. Before any did (a start that
    /// failed, another model), the next start takes it as it is.</summary>
    internal bool NeedsSwitch
    {
        get
        {
            lock (_sync)
            {
                return _applied is not null && !string.Equals(Key(Read()), _applied, StringComparison.Ordinal);
            }
        }
    }

    /// <summary>
    /// The view's state: the choice, the automatic cells on this backend, and each preset with the video memory BAXY's model
    /// takes with it (ModelMemory, from its GGUF's header; null on the processor or with no model file), its projector
    /// included where the mind may put it on the card, whether that backend runs it slower, the room it leaves for the
    /// conversation beside the prompt prefix and a turn, and whether it fits them (with the prefix not known yet, every one;
    /// <paramref name="prefixTokens"/> is the prefix the running mind read, or another the caller knows it will read).
    /// <paramref name="cardBytes"/> is the memory of the person's graphics card, when known, and <paramref name="freeBytes"/>
    /// what is free on it with BAXY's own model gone: with it, <c>recommended</c> is the largest preset that fits, up to the
    /// model's own context (<c>native</c>, its GGUF's), and <c>recommendedWhy</c> says why («nativo», «tarjeta», «no_cabe»).
    /// «Automático» stays the factory's, measured for 4 GB. With the backend not known (<paramref name="backend"/> null) no
    /// video memory is said and nothing is recommended (REV_APP VRAM-b: the figures were NVIDIA's, under what an AMD or Intel
    /// card takes for the same context).
    /// </summary>
    internal JsonObject Json(int? prefixTokens, string? backend, bool switching, long? cardBytes = null, long? freeBytes = null)
    {
        int? minimum = prefixTokens is { } prefix ? MinimumContext(prefix) : null;
        string? running = backend;
        (string Path, long Bytes, GgufShape? Shape)? model = Model();
        var options = new JsonArray();
        foreach (int context in Presets)
        {
            bool fits = context >= Floor(prefixTokens);
            (long? vram, bool vision) = OnCard(model, context, running, cardBytes);
            options.Add(new JsonObject
            {
                ["context"] = context,
                ["vramBytes"] = vram,
                ["vision"] = vision,
                ["slower"] = running == "vulkan" && context >= VulkanSlowCells,
                ["room"] = fits && minimum is { } floor ? context - floor : null,
                ["fits"] = fits,
            });
        }

        int? native = model is { Shape: { ContextLength: > 0 } shape } ? shape.ContextLength : null;
        // Where the screen's reading goes on the card at some context, only a context that keeps it there is recommended:
        // past it the mind reads images on the processor, 8-16 s each instead of 0.5-1 (uso-125).
        bool visionKept = options.OfType<JsonObject>().Any(static option => (bool?)option["vision"] == true);
        var fitting = options.OfType<JsonObject>()
            .Where(option => (bool?)option["fits"] == true && (int?)option["context"] <= (native ?? int.MaxValue)
                && (!visionKept || (bool?)option["vision"] == true)
                && (long?)option["vramBytes"] is { } vram && freeBytes is { } free && vram <= free)
            .Select(static option => (int?)option["context"])
            .Max();
        return new JsonObject
        {
            ["chosen"] = Chosen(),
            ["automatic"] = Automatic(backend),
            ["native"] = native,
            ["recommended"] = freeBytes is null ? null : fitting,
            ["recommendedWhy"] = freeBytes is null || native is null || backend is null ? null : fitting == native ? "nativo" : fitting is null ? "no_cabe" : "tarjeta",
            ["prefixTokens"] = prefixTokens,
            ["minimum"] = minimum,
            ["cardBytes"] = cardBytes ?? BudgetBytes,
            ["cardKnown"] = cardBytes is not null,
            ["options"] = options,
            ["switching"] = switching || NeedsSwitch,
        };
    }

    /// <summary>
    /// MOD1 V-07 / VIVO2 F11 (2026-11-09: in «Modelos en este PC» the stock model said «—» for its size, and no model of BAXY's
    /// own its VRAM): what the file at <paramref name="path"/> takes, the stock model's or the tuned one's, whichever the mind
    /// runs now. <c>bytes</c> on disk, and <c>vramBytes</c> on the card with the context a mind would start it with
    /// (<c>vramContext</c>: the person's choice, else the automatic one on <paramref name="backend"/>), counted as each
    /// preset's figure in <see cref="Json"/>. No VRAM on the processor, nor while the backend is not known (REV_APP VRAM-b).
    /// Null without the file. No path goes to the view.
    /// </summary>
    internal JsonObject? OnDisk(string? path, string? backend, long? cardBytes = null)
    {
        if (Model(path) is not { } model)
        {
            return null;
        }

        int? context = Chosen() ?? Automatic(backend);
        return new JsonObject
        {
            ["bytes"] = model.Bytes,
            ["vramBytes"] = context is { } cells ? OnCard(model, cells, backend, cardBytes).Vram : null,
            ["vramContext"] = context,
        };
    }

    // What <paramref name="model"/> takes on the card at a context, and whether with its projector. The mind puts the projector
    // on the card only where the VRAM free when it starts holds both (llm_server.projector_placement); one that may is counted
    // with it, so the figure is never under what it takes.
    private static (long? Vram, bool Vision) OnCard((string Path, long Bytes, GgufShape? Shape)? model, int context, string? backend, long? cardBytes)
    {
        long? server = ServerBytes(model, context, backend);
        long? projector = ProjectorBytes();
        bool vision = server is { } alone && projector is { } reads
            && Environment.GetEnvironmentVariable("BAXY_VISION_OFFLOAD")?.Trim() != "0"
            && (cardBytes is not { } card || alone + reads + VisionMarginBytes <= card);
        return (server + (vision ? projector : 0), vision);
    }

    /// <summary>What llama-server takes with <paramref name="model"/> at <paramref name="context"/> on
    /// <paramref name="backend"/>, with the mind's own settings (llm_server.LlmServer): its cache type (BAXY_RENEW_KV, q8_0 by
    /// default; of two, the larger), the output matrix in RAM on CUDA unless BAXY_RENEW_OUTPUT_CPU=0, three slots on Vulkan.
    /// Null on the processor, with the backend not known, or without the model's file.</summary>
    private static long? ServerBytes((string Path, long Bytes, GgufShape? Shape)? found, int context, string? backend)
    {
        if (backend is null or "cpu" || found is not { Shape: { } shape } model)
        {
            return null;
        }

        string kv = (Environment.GetEnvironmentVariable("BAXY_RENEW_KV") ?? string.Empty).Split(',')
            .Select(static part => part.Trim().ToLowerInvariant())
            .Where(static part => part.Length > 0)
            .DefaultIfEmpty("q8_0")
            .MaxBy(ModelMemory.CacheBytesPerValue)!;
        bool outputInRam = backend == "cuda" && Environment.GetEnvironmentVariable("BAXY_RENEW_OUTPUT_CPU")?.Trim() != "0";
        return ModelMemory.GpuBytes(shape, model.Bytes, context, kv, outputInRam, sequences: backend == "vulkan" ? 3 : 1);
    }

    /// <summary>What the mind's vision projector (BAXY_MIND_MMPROJ) takes on the card, or null with none.</summary>
    private static long? ProjectorBytes()
    {
        string? path = Environment.GetEnvironmentVariable("BAXY_MIND_MMPROJ")?.Trim();
        try
        {
            return !string.IsNullOrEmpty(path) && new FileInfo(path) is { Exists: true, Length: > 0 } file
                ? ModelMemory.ProjectorGpuBytes(file.Length)
                : null;
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException or ArgumentException)
        {
            return null;
        }
    }

    // The mind's model (BAXY_MIND_LLM_GGUF, the stock one or the tuned one).
    private (string Path, long Bytes, GgufShape? Shape)? Model() => Model(Environment.GetEnvironmentVariable("BAXY_MIND_LLM_GGUF"));

    // A model's file, its header read once per file and size; null without the file.
    private (string Path, long Bytes, GgufShape? Shape)? Model(string? named)
    {
        string? path = named?.Trim();
        if (string.IsNullOrEmpty(path))
        {
            return null;
        }

        try
        {
            var file = new FileInfo(path);
            if (!file.Exists)
            {
                return null;
            }

            lock (_sync)
            {
                if (!_models.TryGetValue(path, out (long Bytes, GgufShape? Shape) known) || known.Bytes != file.Length)
                {
                    _models[path] = known = (file.Length, GgufShape.Read(path));
                }

                return (path, known.Bytes, known.Shape);
            }
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException or ArgumentException)
        {
            return null;
        }
    }

    private static string Key(int? chosen) => chosen?.ToString(CultureInfo.InvariantCulture) ?? "auto";

    // Unreadable, not an object or not a preset is no choice of the person's: «Automático», as with no file.
    private int? Read()
    {
        try
        {
            return File.Exists(_path)
                && JsonNode.Parse(File.ReadAllText(_path)) is JsonObject kept
                && kept["context"] is JsonValue value
                && value.TryGetValue(out int context)
                && Presets.Contains(context)
                    ? context
                    : null;
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException or JsonException)
        {
            return null;
        }
    }
}
