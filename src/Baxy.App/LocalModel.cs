using System.IO;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace Baxy.App;

/// <summary>
/// MOD5 (MOD2 §1, path a: «la App no lo deja elegir»; MindRuntimeDiscovery took the stock model with its SHA-256, or the
/// tuned one, and another GGUF only through BAXY_MIND_LLM_GGUF): a GGUF of the person's own in BAXY's engine, chosen in
/// Settings → Model. Kept in <c>local-model/config.json</c> (<c>{ path, use }</c>) and taken by each start of the mind when
/// the file is there, is a GGUF whose chat template takes tools (as Settings → Model's search asks of a model: OpenModels)
/// and its own context holds BAXY's smallest profile. A start with it that fails goes back to the stock model at once and
/// says why (<see cref="FellBack"/>), until the person chooses again. The vision projector goes with it only when its
/// output is as wide as the model's embedding, which llama.cpp's mtmd requires of a projector and its model (mtmd.cpp:
/// «mismatch between text model (n_embd = …) and mmproj (n_embd = …)»): the stock model's, or one beside the file.
/// Otherwise vision is off, and Settings says so.
/// </summary>
internal sealed class LocalModel
{
    private const string GgufVariable = TunedModel.GgufVariable;
    private const string ProjectorVariable = "BAXY_MIND_MMPROJ";

    private readonly string _root;
    private readonly Func<int> _leastContext;
    private readonly Dictionary<string, string?> _replaced = [];
    private readonly Lock _replacedLock = new();
    private readonly Dictionary<string, string?> _mine = [];
    private string? _applied;
    private string? _failedChoice;
    // The person chose it again after a start with it failed (Apply): the next start tries it, even with the same file.
    private bool _askedAgain;

    /// <param name="dataRoot">BAXY's data folder for this profile.</param>
    /// <param name="leastContext">The cells a model's own context must hold: BAXY's largest ready-made profile's (its prompt
    /// and a turn), so that every profile the start may take fits it (the mind caps the cells at the model's own).</param>
    internal LocalModel(string dataRoot, Func<int> leastContext)
    {
        _root = dataRoot;
        _leastContext = leastContext;
    }

    /// <summary>The mind runs on the person's GGUF.</summary>
    internal bool Active { get; private set; }

    /// <summary>
    /// Why the last start is not on the person's GGUF although they chose it: <c>local_model_missing</c>,
    /// <c>local_model_not_gguf</c>, <c>local_model_no_tools</c>, <c>local_model_short_context</c>, or
    /// <c>local_model_failed</c> (a start with it did not come up; <see cref="FailedCause"/> says the mind's cause). Null
    /// with no problem.
    /// </summary>
    internal string? Problem { get; private set; }

    /// <summary>The mind's cause of the failed start with the person's GGUF (<see cref="FellBack"/>), or null.</summary>
    internal string? FailedCause { get; private set; }

    /// <summary>Whether the running start took a vision projector with the person's GGUF; null when it is not active.</summary>
    internal bool? Sees { get; private set; }

    /// <summary>What the person has chosen is not what the running mind was started with.</summary>
    internal bool NeedsSwitch => _applied is not null && (Choice() != _applied || _askedAgain);

    /// <summary>The person chose their GGUF (whether this start could take it or not).</summary>
    internal bool Chosen => Use(Config()) && Path() is not null;

    private string Folder => System.IO.Path.Combine(_root, "local-model");

    private string ConfigPath => System.IO.Path.Combine(Folder, "config.json");

    private string? Path() => Text(Config()["path"]) is { Length: > 0 } path ? path : null;

    // What a hand-edited or damaged file holds is no exception at a start: a text that is not one is none.
    private static string? Text(JsonNode? node) => node is JsonValue value && value.TryGetValue(out string? text) ? text : null;

    private static bool Use(JsonObject config) => config["use"] is JsonValue value && value.TryGetValue(out bool use) && use;

    internal JsonObject Json()
    {
        JsonObject config = Config();
        string? path = Path();
        GgufShape? shape = path is not null && File.Exists(path) ? GgufShape.Read(path) : null;
        return new JsonObject
        {
            ["path"] = path,
            ["use"] = Use(config),
            ["active"] = Active,
            ["problem"] = Problem,
            ["failedCause"] = FailedCause,
            ["sees"] = Sees,
            ["exists"] = path is not null && File.Exists(path),
            ["bytes"] = path is not null && File.Exists(path) ? new FileInfo(path).Length : null,
            ["contextLength"] = shape is { ContextLength: > 0 } ? shape.ContextLength : null,
            ["declaresTools"] = shape?.DeclaresTools,
        };
    }

    /// <summary>
    /// What the panel asks: <c>{ path }</c> to keep a file, <c>{ use }</c> to run on it or not (both at once too). A
    /// refusal's code when the file cannot be used (<see cref="Check"/>), null when kept.
    /// </summary>
    internal string? Apply(JsonObject body)
    {
        ArgumentNullException.ThrowIfNull(body);
        JsonObject config = Config();
        if (body["path"] is JsonNode given)
        {
            string? path = Text(given)?.Trim().Trim('"');
            if (string.IsNullOrEmpty(path))
            {
                return "local_model_missing";
            }

            config["path"] = path;
        }

        if (body["use"] is JsonValue asked && asked.TryGetValue(out bool use))
        {
            string? path = Text(config["path"]);
            if (use && (path is null ? "local_model_missing" : Check(path)) is { } refused)
            {
                return refused;
            }

            config["use"] = use;
            // Chosen again (or turned off) after a start with it failed: «Puedes elegirlo otra vez» is true, it is tried.
            _askedAgain = use && _failedChoice is not null;
            _failedChoice = null;
        }

        Save(config);
        return null;
    }

    /// <summary>
    /// Takes the person's GGUF for this start, once it is checked (<see cref="Check"/>), in the place of the model the
    /// registered runtime (or the tuned one) gave; and the projector only when it fits it (<see cref="FittingProjector"/>).
    /// Otherwise the start stays as it was and <see cref="Problem"/> says why.
    /// </summary>
    internal void Start()
    {
        string choice = Choice();
        if (choice != _applied)
        {
            Stop();
        }

        _applied = choice;
        bool again = _askedAgain;
        _askedAgain = false;
        if (!Chosen || Path() is not { } path)
        {
            Problem = null;
            FailedCause = null;
            return;
        }

        if (choice == _failedChoice && !again)
        {
            // A start with this same file and choice did not come up: the stock model, until the person chooses again.
            Problem = "local_model_failed";
            return;
        }

        if (Active)
        {
            // A start that is no switch (a lost mind, a retry) found the registered pieces put back where they were empty
            // (MindRuntimeDiscovery.ApplyPieces: the stock projector): this model's own are given again.
            Reassert();
            return;
        }

        FailedCause = null;
        Problem = Check(path);
        if (Problem is not null)
        {
            return;
        }

        string? projector = FittingProjector(path, Environment.GetEnvironmentVariable(ProjectorVariable));
        Replace(GgufVariable, path);
        // The registration's hash is the stock model's: another file has none.
        Replace(MindRuntimeDiscovery.GgufSha256Variable, null);
        Replace(ProjectorVariable, projector);
        Sees = projector is not null;
        Active = true;
    }

    private void Reassert()
    {
        lock (_replacedLock)
        {
            foreach ((string name, string? value) in _mine)
            {
                Environment.SetEnvironmentVariable(name, value);
            }
        }
    }

    /// <summary>
    /// MOD5 (3a): a start of the mind on the person's GGUF did not come up. True when it was on it: the variables go back to
    /// the model before it, this file and choice are not tried again until the person chooses again, and
    /// <see cref="Problem"/> says it with the mind's cause, for the stock model's start that follows at once.
    /// </summary>
    internal bool FellBack(string? cause)
    {
        if (!Active)
        {
            return false;
        }

        _failedChoice = Choice();
        Stop();
        Problem = "local_model_failed";
        FailedCause = cause;
        return true;
    }

    /// <summary>Back to the model before it: the mind's variables as they were.</summary>
    internal void Stop()
    {
        lock (_replacedLock)
        {
            foreach ((string name, string? value) in _replaced)
            {
                Environment.SetEnvironmentVariable(name, value);
            }

            _replaced.Clear();
            _mine.Clear();
        }

        Active = false;
        Sees = null;
    }

    /// <summary>Why <paramref name="path"/> cannot be BAXY's model, or null when it can.</summary>
    internal string? Check(string path)
    {
        if (!File.Exists(path))
        {
            return "local_model_missing";
        }

        if (GgufShape.Read(path) is not { } shape)
        {
            return "local_model_not_gguf";
        }

        if (!shape.DeclaresTools)
        {
            return "local_model_no_tools";
        }

        // Its own context holds BAXY's largest profile: the mind caps the cells at it (llm_server), and a profile whose
        // prompt is longer would not fit (a card's choice of profile does not look at the model's context).
        return shape.ContextLength > 0 && shape.ContextLength < _leastContext() ? "local_model_short_context" : null;
    }

    /// <summary>
    /// The projector that goes with <paramref name="model"/>: <paramref name="registered"/> (the stock model's) or one
    /// beside the file (<c>mmproj*.gguf</c>), the first whose <c>clip.vision.projection_dim</c> is the model's embedding
    /// width; null with none.
    /// </summary>
    internal static string? FittingProjector(string model, string? registered)
    {
        if (GgufShape.Read(model) is not { Embedding: > 0 } shape)
        {
            return null;
        }

        IEnumerable<string> beside = [];
        try
        {
            if (System.IO.Path.GetDirectoryName(model) is { Length: > 0 } folder && Directory.Exists(folder))
            {
                beside = Directory.EnumerateFiles(folder, "mmproj*.gguf").Order(StringComparer.OrdinalIgnoreCase).ToList();
            }
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            // a folder that cannot be listed has no projector beside it
        }

        IEnumerable<string> candidates = string.IsNullOrWhiteSpace(registered) ? beside : beside.Prepend(registered);
        return candidates.FirstOrDefault(projector => File.Exists(projector)
            && GgufShape.Number(projector, "clip.vision.projection_dim") == shape.Embedding);
    }

    private string Choice()
    {
        if (!Use(Config()) || Path() is not { } path)
        {
            return "off";
        }

        var file = new FileInfo(path);
        return file.Exists ? $"on|{path}|{file.Length}|{file.LastWriteTimeUtc.Ticks}" : $"on|{path}|missing";
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

    private void Replace(string name, string? value)
    {
        lock (_replacedLock)
        {
            _replaced.TryAdd(name, Environment.GetEnvironmentVariable(name));
            _mine[name] = value;
            Environment.SetEnvironmentVariable(name, value);
        }
    }
}
