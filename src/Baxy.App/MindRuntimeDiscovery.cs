using System.Globalization;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace Baxy.App;

internal sealed record MindRuntimeConfiguration(
    string Python,
    string PythonPath,
    string Gguf,
    string LlamaServer,
    int GpuLayers,
    MindRuntimePieces Pieces);

/// <summary>
/// The pieces beside the model that a registration names on this machine (entrega 1.1.0): BAXY's voice (Supertonic),
/// the ear (the k4 wake word and Parakeet Ultra), System One's decision model and its CPU threads, and the model's vision
/// projector. Each is null when it is not registered or is not what was registered: that piece stays off, and the mind
/// says so (its voice's state; no decision model; no projector on its server).
/// </summary>
internal sealed record MindRuntimePieces(
    string? Voice,
    string? Wake,
    string? Stt,
    string? SystemOneGguf,
    int? SystemOneThreads,
    string? VisionProjector);

internal sealed record MindRuntimeEnvironmentSnapshot(
    string? Disabled,
    string? Python,
    string? PythonPath,
    string? Gguf,
    string? LlamaServer,
    string? GpuLayers);

internal sealed record MindRuntimeDiscoveryResult(
    MindRuntimeEnvironmentSnapshot Environment,
    MindRuntimeConfiguration? Runtime,
    bool CanConfigure,
    bool Disabled);

/// <summary>
/// Loads a deliberately registered local mind runtime (scripts/register_mind_runtime.ps1). The registration is
/// fail-closed, and an explicit environment configuration always wins. The interpreter, mind path, model, server and
/// GPU layers are required and verified. Entrega 1.1.0: BAXY installed and opened from the Start menu has no launcher,
/// and scripts/run_renew.cmd was the only way its voice, ear, System One and vision reached the mind; the registration
/// now names them (<see cref="MindRuntimePieces"/>), each verified by its SHA-256 and applied only where no variable
/// was given, so a bench still sets its own. The old voice entries and the adapters an older registration may carry
/// are allowed and not read. Any other property refuses the registration.
/// </summary>
internal static class MindRuntimeDiscovery
{
    private const string RegistrationSchema = "baxy-mind-runtime-v1";
    private const int MaximumRegistrationBytes = 16 * 1024;

    private static readonly string[] RegistrationProperties =
    [
        "schema",
        "python",
        "python_sha256",
        "python_path",
        "gguf",
        "gguf_sha256",
        "llama_server",
        "llama_server_sha256",
        "ngl",
    ];

    // The pieces (MindRuntimePieces), each optional: a path and its SHA-256 (of a folder, DirectorySha256).
    private static readonly string[] PieceProperties =
    [
        "renew_tts_dir", "renew_tts_sha256", "renew_wake_dir", "renew_wake_sha256", "renew_stt_dir", "renew_stt_sha256",
        "s1_gguf", "s1_gguf_sha256", "s1_threads", "mmproj", "mmproj_sha256",
    ];

    // The click's vision asks the mind's own llama-server (PLAN_GENERAL A5) on this port unless one is given.
    private const string VisionPort = "8077";

    private static readonly object ApplyLock = new();

    internal static MindRuntimeDiscoveryResult DiscoverVerified() =>
        DiscoverVerified(DefaultRegistrationPath());

    internal static MindRuntimeDiscoveryResult DiscoverVerified(string registrationPath)
    {
        MindRuntimeEnvironmentSnapshot environment = CaptureEnvironment();

        // A launcher may deliberately request the deterministic body. This
        // veto must win over inherited variables and registered discovery so
        // a manifest cannot silently reactivate the optional sidecar.
        if (IsDisabled(environment.Disabled))
        {
            return new(
                environment,
                Runtime: null,
                CanConfigure: false,
                Disabled: true);
        }

        string? explicitPython = environment.Python;
        bool hasExplicitPython = !string.IsNullOrWhiteSpace(explicitPython);
        if (hasExplicitPython
            && (!Path.IsPathFullyQualified(explicitPython!)
                || !File.Exists(explicitPython)))
        {
            return new(
                environment,
                Runtime: null,
                CanConfigure: false,
                Disabled: false);
        }

        MindRuntimeConfiguration? runtime = LoadRegistered(registrationPath);
        return new(
            environment,
            runtime,
            CanConfigure: runtime is not null || hasExplicitPython,
            Disabled: false);
    }

    internal static bool ApplyVerified(MindRuntimeDiscoveryResult discovery) =>
        ApplyVerified(discovery, Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData));

    internal static bool ApplyVerified(MindRuntimeDiscoveryResult discovery, string localData)
    {
        ArgumentNullException.ThrowIfNull(discovery);
        lock (ApplyLock)
        {
            if (discovery.Disabled
                || MindSidecarClient.IsDisabled
                || !EnvironmentMatches(discovery.Environment))
            {
                return false;
            }

            if (!discovery.CanConfigure)
            {
                return false;
            }

            MindRuntimeConfiguration? runtime = discovery.Runtime;
            if (runtime is null)
            {
                ApplyVision(localData);
                return true;
            }

            // Publish the interpreter last. MindSidecarClient.IsConfigured uses
            // this variable as its readiness flag, so no registered runtime can
            // become observable before every auxiliary value has been applied.
            SetIfMissing(MindSidecarClient.PythonPathEnvironmentVariable, runtime.PythonPath);
            SetIfMissing("BAXY_MIND_LLM_GGUF", runtime.Gguf);
            SetIfMissing("BAXY_MIND_LLAMA_SERVER", runtime.LlamaServer);
            SetIfMissing(
                "BAXY_MIND_NGL",
                runtime.GpuLayers.ToString(CultureInfo.InvariantCulture));
            ApplyPieces(runtime.Pieces, localData);
            ApplyVision(localData);
            if (string.IsNullOrWhiteSpace(discovery.Environment.Python))
            {
                SetIfMissing(MindSidecarClient.PythonEnvironmentVariable, runtime.Python);
            }
            return true;
        }
    }

    /// <summary>
    /// The registered pieces, each where no variable names one. System One's decision model and its threads not while
    /// the owner's switch is off (scripts/system_one.cmd off; the mind reads it too, for its thresholds), and the
    /// projector not with BAXY_VISION_OFF, as scripts/run_renew.cmd starts a bench.
    /// </summary>
    private static void ApplyPieces(MindRuntimePieces pieces, string localData)
    {
        SetIfMissing("BAXY_RENEW_TTS_DIR", pieces.Voice);
        SetIfMissing("BAXY_RENEW_WAKE_DIR", pieces.Wake);
        SetIfMissing("BAXY_RENEW_STT_DIR", pieces.Stt);
        if (!SystemOneSwitchedOff(localData))
        {
            SetIfMissing("BAXY_S1_GGUF", pieces.SystemOneGguf);
            SetIfMissing("BAXY_S1_THREADS", pieces.SystemOneThreads?.ToString(CultureInfo.InvariantCulture));
        }

        if (string.IsNullOrEmpty(Environment.GetEnvironmentVariable("BAXY_VISION_OFF")))
        {
            SetIfMissing("BAXY_MIND_MMPROJ", pieces.VisionProjector);
        }
    }

    /// <summary>
    /// With a projector on the mind's server (registered, or given by a bench), the click's vision is pointed at it
    /// before the core starts, which reads these variables (LocalVisionEndpoint): a pinned port (8077 unless one is
    /// given), its chat endpoint, the server's one slot, and the folder where that slot's state is set aside meanwhile,
    /// the server's own --slot-save-path (llm_server._slot_dir). A port or folder already given is kept.
    /// </summary>
    private static void ApplyVision(string localData)
    {
        if (!string.IsNullOrEmpty(Environment.GetEnvironmentVariable("BAXY_VISION_OFF"))
            || string.IsNullOrWhiteSpace(Environment.GetEnvironmentVariable("BAXY_MIND_MMPROJ")))
        {
            return;
        }

        SetIfMissing("BAXY_MIND_LLAMA_PORT", VisionPort);
        string port = Environment.GetEnvironmentVariable("BAXY_MIND_LLAMA_PORT")!.Trim();
        SetIfMissing("BAXY_VISION_ENDPOINT", $"http://127.0.0.1:{port}/v1/chat/completions");
        SetIfMissing("BAXY_VISION_MODEL", "baxy");
        SetIfMissing("BAXY_VISION_SLOT", "0");
        if (!string.IsNullOrWhiteSpace(localData))
        {
            SetIfMissing("BAXY_VISION_SLOT_DIR", Path.Combine(localData, "BAXY", "renew", "slots"));
        }
    }

    private static bool SystemOneSwitchedOff(string localData) =>
        !string.IsNullOrWhiteSpace(localData)
        && File.Exists(Path.Combine(localData, "BAXY", "renew", "system_one.off"));

    internal static string DefaultRegistrationPath()
    {
        string localData = Environment.GetFolderPath(
            Environment.SpecialFolder.LocalApplicationData);
        return string.IsNullOrWhiteSpace(localData)
            ? string.Empty
            : Path.Combine(localData, "BAXYRuntime", "mind-runtime-v1.json");
    }

    /// <summary>
    /// Every published asset is still compared with its registered SHA-256; a
    /// file whose size and timestamps did not change since a verified start is
    /// not read again (see <see cref="RuntimeFileHashCache"/>).
    /// </summary>
    private static MindRuntimeConfiguration? LoadRegistered(string manifestPath)
    {
        if (string.IsNullOrWhiteSpace(manifestPath)
            || !Path.IsPathFullyQualified(manifestPath))
        {
            return null;
        }

        try
        {
            var info = new FileInfo(Path.GetFullPath(manifestPath));
            if (!info.Exists || info.Length is <= 0 or > MaximumRegistrationBytes)
            {
                return null;
            }

            RuntimeFileHashCache hashes = RuntimeFileHashCache.ForRegistration(info.FullName, FileSha256);
            MindRuntimeConfiguration? runtime = LoadRegistered(info, hashes);
            hashes.Save();
            return runtime;
        }
        catch (Exception exception) when (exception is IOException
            or UnauthorizedAccessException
            or ArgumentException
            or NotSupportedException
            or JsonException)
        {
            return null;
        }
    }

    private static MindRuntimeConfiguration? LoadRegistered(FileInfo info, RuntimeFileHashCache hashes)
    {
        try
        {
            using FileStream stream = info.OpenRead();
            using JsonDocument document = JsonDocument.Parse(
                stream,
                new JsonDocumentOptions
                {
                    AllowTrailingCommas = false,
                    CommentHandling = JsonCommentHandling.Disallow,
                    MaxDepth = 4,
                });
            JsonElement root = document.RootElement;
            if (root.ValueKind != JsonValueKind.Object
                || !HasKnownProperties(root)
                || !string.Equals(
                    RequiredString(root, "schema"),
                    RegistrationSchema,
                    StringComparison.Ordinal))
            {
                return null;
            }

            string? python = ExistingFile(
                hashes,
                RequiredString(root, "python"),
                "python.exe",
                RequiredString(root, "python_sha256"));
            string? pythonPath = ExistingDirectory(RequiredString(root, "python_path"));
            string? gguf = ExistingFile(
                hashes,
                RequiredString(root, "gguf"),
                expectedName: null,
                RequiredString(root, "gguf_sha256"));
            string? server = ExistingFile(
                hashes,
                RequiredString(root, "llama_server"),
                "llama-server.exe",
                RequiredString(root, "llama_server_sha256"));
            if (python is null
                || pythonPath is null
                || gguf is null
                || !gguf.EndsWith(".gguf", StringComparison.OrdinalIgnoreCase)
                || server is null
                || !File.Exists(Path.Combine(pythonPath, "baxy_mind", "__main__.py")))
            {
                return null;
            }

            JsonElement nglElement = root.GetProperty("ngl");
            if (nglElement.ValueKind != JsonValueKind.Number
                || !nglElement.TryGetInt32(out int ngl)
                || ngl is < 0 or > 999)
            {
                return null;
            }

            return new MindRuntimeConfiguration(
                python,
                pythonPath,
                gguf,
                server,
                ngl,
                new MindRuntimePieces(
                    RegisteredDirectory(hashes, root, "renew_tts_dir", "renew_tts_sha256"),
                    RegisteredDirectory(hashes, root, "renew_wake_dir", "renew_wake_sha256"),
                    RegisteredDirectory(hashes, root, "renew_stt_dir", "renew_stt_sha256"),
                    RegisteredModel(hashes, root, "s1_gguf", "s1_gguf_sha256"),
                    root.TryGetProperty("s1_threads", out JsonElement threads)
                        && threads.ValueKind == JsonValueKind.Number
                        && threads.TryGetInt32(out int count)
                        && count is >= 1 and <= 64 ? count : null,
                    RegisteredModel(hashes, root, "mmproj", "mmproj_sha256")));
        }
        catch (Exception exception) when (exception is IOException
            or UnauthorizedAccessException
            or ArgumentException
            or NotSupportedException
            or JsonException)
        {
            return null;
        }
    }

    /// <summary>A registered GGUF beside the model (System One's, the projector) that is what was registered.</summary>
    private static string? RegisteredModel(RuntimeFileHashCache hashes, JsonElement root, string path, string sha256)
    {
        try
        {
            string? file = ExistingFile(hashes, OptionalString(root, path), expectedName: null, OptionalString(root, sha256));
            return file is not null && file.EndsWith(".gguf", StringComparison.OrdinalIgnoreCase) ? file : null;
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            return null; // only this piece stays off
        }
    }

    /// <summary>A registered folder (the voice, the wake word, the recognizer) whose files are what was registered.</summary>
    private static string? RegisteredDirectory(RuntimeFileHashCache hashes, JsonElement root, string path, string sha256)
    {
        try
        {
            string? directory = ExistingDirectory(OptionalString(root, path));
            string? expected = OptionalString(root, sha256);
            return directory is not null
                && IsSha256(expected)
                && string.Equals(DirectorySha256(hashes, directory), expected, StringComparison.Ordinal)
                ? directory
                : null;
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            return null;
        }
    }

    /// <summary>
    /// A folder's SHA-256 as scripts/mind_runtime_manifest.ps1 writes it (Get-BaxyDirectorySha256): of the UTF-8 lines
    /// «name:sha256», one per file directly in it by ordinal name, each ending in a line feed; null for a folder with
    /// no file. Subfolders are not part of it (the wake word's __pycache__, written when the mind imports its runtime).
    /// </summary>
    internal static string? DirectorySha256(RuntimeFileHashCache hashes, string directory)
    {
        string[] names = [.. Directory.GetFiles(directory).Select(static file => Path.GetFileName(file))
            .Order(StringComparer.Ordinal)];
        if (names.Length == 0)
        {
            return null;
        }

        var lines = new StringBuilder();
        foreach (string name in names)
        {
            lines.Append(name).Append(':').Append(hashes.Sha256(Path.Combine(directory, name))).Append('\n');
        }

        return Convert.ToHexStringLower(SHA256.HashData(Encoding.UTF8.GetBytes(lines.ToString())));
    }

    private static string? OptionalString(JsonElement root, string propertyName) =>
        root.TryGetProperty(propertyName, out JsonElement element) && element.ValueKind == JsonValueKind.String
            ? element.GetString()
            : null;

    // Allowed in a registration and never read here (audit 2026-10-15, App H23: they were required although nothing
    // in the App reads them, so a registration without voice was refused). The voice entries are those of a
    // registration written before entrega 1.1.0 (Definitivo's voice): it still starts the mind, with no piece.
    private static readonly string[] UnreadProperties =
    [
        "stt_dir", "stt_sha256", "wake_manifest", "wake_manifest_sha256", "tts_model", "tts_sha256", "wake_on_start",
        "cpu_prose_adapter", "decider_adapter",
    ];

    private static string? ExistingFile(
        RuntimeFileHashCache hashes,
        string? value,
        string? expectedName,
        string? expectedSha256)
    {
        string? canonical = CanonicalPath(value);
        if (canonical is null
            || !File.Exists(canonical)
            || !IsSha256(expectedSha256)
            || !string.Equals(
                hashes.Sha256(canonical),
                expectedSha256,
                StringComparison.Ordinal)
            || (expectedName is not null
                && !string.Equals(
                    Path.GetFileName(canonical),
                    expectedName,
                    StringComparison.OrdinalIgnoreCase)))
        {
            return null;
        }

        return canonical;
    }

    /// <summary>
    /// The App's own reading of a runtime file: the whole stream is hashed
    /// here, never taken from a launcher or a manifest. The cache only spares
    /// this read for a file whose identity did not change.
    /// </summary>
    private static string FileSha256(string path)
    {
        using FileStream stream = File.OpenRead(path);
        return Convert.ToHexStringLower(SHA256.HashData(stream));
    }

    private static bool IsSha256(string? value) =>
        value is { Length: 64 }
        && value.All(character => character is >= '0' and <= '9' or >= 'a' and <= 'f');

    private static string? ExistingDirectory(string? value)
    {
        string? canonical = CanonicalPath(value);
        return canonical is not null && Directory.Exists(canonical) ? canonical : null;
    }

    internal static bool IsForeignBaxyWorktree(string path)
    {
        if (string.IsNullOrWhiteSpace(path))
        {
            return false;
        }

        string full;
        try
        {
            full = Path.GetFullPath(path);
        }
        catch (Exception exception) when (exception is ArgumentException
            or NotSupportedException or PathTooLongException)
        {
            return false;
        }

        ReadOnlySpan<char> span = full.AsSpan();
        for (int index = 0; index < span.Length; index++)
        {
            if (span[index] is not '\\' and not '/')
            {
                continue;
            }

            int start = index + 1;
            if (start + 4 > span.Length
                || !span.Slice(start, 4).Equals("BAXY", StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }

            int after = start + 4;
            if (after == span.Length || span[after] is '\\' or '/')
            {
                return true;
            }
        }

        return false;
    }

    private static string? CanonicalPath(string? value)
    {
        if (string.IsNullOrWhiteSpace(value) || !Path.IsPathFullyQualified(value))
        {
            return null;
        }

        try
        {
            string full = Path.GetFullPath(value);
            return IsForeignBaxyWorktree(full) ? null : full;
        }
        catch (Exception exception) when (exception is ArgumentException
            or NotSupportedException or PathTooLongException)
        {
            return null;
        }
    }

    private static string? RequiredString(JsonElement root, string propertyName)
    {
        JsonElement element = root.GetProperty(propertyName);
        return element.ValueKind == JsonValueKind.String ? element.GetString() : null;
    }

    /// <summary>Every required property once, and no other but the pieces' and the unread ones.</summary>
    private static bool HasKnownProperties(JsonElement root)
    {
        var actual = new HashSet<string>(StringComparer.Ordinal);
        foreach (JsonProperty property in root.EnumerateObject())
        {
            if (!actual.Add(property.Name)
                || !(RegistrationProperties.Contains(property.Name, StringComparer.Ordinal)
                    || PieceProperties.Contains(property.Name, StringComparer.Ordinal)
                    || UnreadProperties.Contains(property.Name, StringComparer.Ordinal)))
            {
                return false;
            }
        }

        return RegistrationProperties.All(actual.Contains);
    }

    private static MindRuntimeEnvironmentSnapshot CaptureEnvironment() =>
        new(
            Environment.GetEnvironmentVariable(MindSidecarClient.DisabledEnvironmentVariable),
            Environment.GetEnvironmentVariable(MindSidecarClient.PythonEnvironmentVariable),
            Environment.GetEnvironmentVariable(MindSidecarClient.PythonPathEnvironmentVariable),
            Environment.GetEnvironmentVariable("BAXY_MIND_LLM_GGUF"),
            Environment.GetEnvironmentVariable("BAXY_MIND_LLAMA_SERVER"),
            Environment.GetEnvironmentVariable("BAXY_MIND_NGL"));

    private static bool EnvironmentMatches(MindRuntimeEnvironmentSnapshot expected) =>
        string.Equals(
            Environment.GetEnvironmentVariable(MindSidecarClient.DisabledEnvironmentVariable),
            expected.Disabled,
            StringComparison.Ordinal)
        && string.Equals(
            Environment.GetEnvironmentVariable(MindSidecarClient.PythonEnvironmentVariable),
            expected.Python,
            StringComparison.Ordinal)
        && string.Equals(
            Environment.GetEnvironmentVariable(MindSidecarClient.PythonPathEnvironmentVariable),
            expected.PythonPath,
            StringComparison.Ordinal)
        && string.Equals(
            Environment.GetEnvironmentVariable("BAXY_MIND_LLM_GGUF"),
            expected.Gguf,
            StringComparison.Ordinal)
        && string.Equals(
            Environment.GetEnvironmentVariable("BAXY_MIND_LLAMA_SERVER"),
            expected.LlamaServer,
            StringComparison.Ordinal)
        && string.Equals(
            Environment.GetEnvironmentVariable("BAXY_MIND_NGL"),
            expected.GpuLayers,
            StringComparison.Ordinal);

    private static bool IsDisabled(string? value) =>
        string.Equals(value, "1", StringComparison.Ordinal);

    private static void SetIfMissing(string name, string? value)
    {
        if (value is not null && string.IsNullOrWhiteSpace(Environment.GetEnvironmentVariable(name)))
        {
            Environment.SetEnvironmentVariable(name, value);
        }
    }
}
