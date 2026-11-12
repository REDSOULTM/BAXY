using System.Globalization;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Baxy.Providers.Windows.SystemStatus;

namespace Baxy.App;

internal sealed record MindRuntimeConfiguration(
    string Python,
    string PythonPath,
    string Gguf,
    string LlamaServer,
    int GpuLayers,
    MindRuntimePieces Pieces,
    string? LlamaBackend = null,
    string? GgufSha256 = null);

/// <summary>
/// QWB2 (documentacion/PLAN_QWEN_BASE.md §3): BAXY's tuned model, which a store's package offers and does not carry
/// (scripts/build_steam.ps1, tuned_*): its file name, its SHA-256, its size, the address pinned to its commit and its
/// license. The App downloads it only when the person asks (TunedModel) and keeps it only with this SHA-256.
/// </summary>
internal sealed record TunedModelOffer(string File, string Sha256, long Bytes, string Url, string License);

/// <summary>
/// The pieces beside the model that a registration names on this machine (entrega 1.1.0): BAXY's voice (Supertonic),
/// the ear (the k4 wake word and Parakeet Ultra), and the model's vision projector. Each is null when it is not registered
/// or is not what was registered: that piece stays off, and the mind says so (its voice's state; no projector on its server). uso-93: the low-latency wake package
/// (k6r-alto) heard beside the wake word, the first to fire telling «Baxy»; without it the wake word is heard alone.
/// </summary>
internal sealed record MindRuntimePieces(
    string? Voice,
    string? Wake,
    string? WakeFast,
    string? Stt,
    string? VisionProjector,
    string? WakeProblem = null);

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
    bool Disabled,
    bool NoSupportedGpu = false,
    string? Problem = null);

/// <summary>
/// Loads a deliberately registered local mind runtime (scripts/register_mind_runtime.ps1). The registration is
/// fail-closed, and an explicit environment configuration always wins. The interpreter, mind path, model, server and
/// GPU layers are required and verified. Entrega 1.1.0: BAXY installed and opened from the Start menu has no launcher,
/// and scripts/run_renew.cmd was the only way its voice, ear, System One and vision reached the mind; the registration
/// now names them (<see cref="MindRuntimePieces"/>), each verified by its SHA-256 and applied only where no variable
/// was given, so a bench still sets its own. The old voice entries and the adapters an older registration may carry
/// are allowed and not read. Any other property refuses the registration. uso-101: a store's package cannot rewrite its
/// registration (the folder is the store's) and has no installer to run gpu.py, so it names one server per backend
/// (llama_server, CUDA; llama_server_vulkan) and every start picks by the GPU's PCI vendor. The same file is both servers'
/// llama-server.exe, so its hash does not tell the backend: the mind holds the folder's DLL to the one chosen
/// (BAXY_MIND_LLAMA_BACKEND). A server given by a variable makes no choice; a registration with one server neither.
/// </summary>
internal static class MindRuntimeDiscovery
{
    private const string RegistrationSchema = "baxy-mind-runtime-v1";
    private const string RegistrationFileName = "mind-runtime-v1.json";
    private const string NotInstalled = "sin_instalar";
    private const string MissingComponent = "componente_ausente";
    private const int MaximumRegistrationBytes = 16 * 1024;

    /// <summary>The verified SHA-256 of the model the mind is given, which keys its kept prompt prefix (llm_server.prefix_key).</summary>
    internal const string GgufSha256Variable = "BAXY_MIND_LLM_GGUF_SHA256";

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
        "renew_tts_dir", "renew_tts_sha256", "renew_wake_dir", "renew_wake_sha256", "renew_wake_fast_dir",
        "renew_wake_fast_sha256", "renew_stt_dir", "renew_stt_sha256", "s1_gguf", "s1_gguf_sha256", "s1_threads", "mmproj",
        "mmproj_sha256", "llama_server_vulkan", "llama_server_vulkan_sha256",
        // QWB2: the tuned model the package offers (TunedOffer), never a piece this start loads.
        "tuned_gguf", "tuned_gguf_sha256", "tuned_gguf_bytes", "tuned_gguf_url", "tuned_gguf_license",
    ];

    // PCI vendor ids, as src/baxy_mind/gpu.py reads them for an installation (tests/test_mind_gpu.py compares the two):
    // 10DE NVIDIA, which wins beside another GPU (a laptop's integrated one); 1002 AMD and 8086 Intel.
    private static readonly Dictionary<uint, string> GpuBackends = new()
    {
        [0x10DE] = "cuda",
        [0x1002] = "vulkan",
        [0x8086] = "vulkan",
    };

    // The click's vision asks the mind's own llama-server (PLAN_GENERAL A5) on this port unless one is given.
    private const string VisionPort = "8077";

    private static readonly object ApplyLock = new();

    internal static MindRuntimeDiscoveryResult DiscoverVerified() =>
        DiscoverVerified(DefaultRegistrationPath());

    internal static MindRuntimeDiscoveryResult DiscoverVerified(string registrationPath) =>
        DiscoverVerified(registrationPath, WindowsGpuVendors.Read);

    internal static MindRuntimeDiscoveryResult DiscoverVerified(string registrationPath, Func<IReadOnlyList<uint>> gpuVendors)
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
                Disabled: false,
                Problem: MissingComponent);
        }

        MindRuntimeConfiguration? runtime = LoadRegistered(
            registrationPath, environment.LlamaServer, gpuVendors, out bool noSupportedGpu);
        return new(
            environment,
            runtime,
            CanConfigure: runtime is not null || hasExplicitPython,
            Disabled: false,
            NoSupportedGpu: noSupportedGpu && !hasExplicitPython,
            Problem: runtime is null && !hasExplicitPython && !noSupportedGpu ? RegistrationProblem(registrationPath) : null);
    }

    /// <summary>
    /// uso-116 (N23): why no runtime came out of a registration, as a cause the view says (causes.ts): none, its model not
    /// there, a model that is not the registered one, or any other required piece. Read once, only when it failed.
    /// </summary>
    private static string RegistrationProblem(string registrationPath)
    {
        try
        {
            var info = new FileInfo(Path.GetFullPath(registrationPath));
            if (!info.Exists)
            {
                return NotInstalled;
            }

            using JsonDocument document = JsonDocument.Parse(File.ReadAllBytes(info.FullName));
            // A store's package names its files relative to the registration (LoadRegistered).
            string? registered = OptionalString(document.RootElement, "gguf");
            string? gguf = registered is null ? null : Path.GetFullPath(Path.Combine(info.DirectoryName!, registered));
            if (gguf is null || !File.Exists(gguf))
            {
                return "modelo_ausente";
            }

            return RuntimeFileHashCache.ForRegistration(info.FullName, FileSha256).Sha256(gguf)
                == OptionalString(document.RootElement, "gguf_sha256")
                    ? MissingComponent
                    : "modelo_danado";
        }
        catch (Exception exception) when (exception is IOException
            or UnauthorizedAccessException
            or ArgumentException
            or NotSupportedException
            or JsonException
            or InvalidOperationException)
        {
            return MissingComponent;
        }
    }

    /// <summary>
    /// V132 (1.3.2): why the mind of this start hears no wake word although the registration names one (wake_missing: its
    /// folder is gone or empty; wake_changed: its files are not the registered ones), once applied; null when it hears the
    /// registered one or a variable named another (a bench's, <c>none</c> included). The App says it: the ear starts
    /// without it, and the person's «Siempre activo» could not answer to «BAXY».
    /// </summary>
    internal static string? WakeProblem(MindRuntimeDiscoveryResult discovery) =>
        string.IsNullOrWhiteSpace(Environment.GetEnvironmentVariable("BAXY_RENEW_WAKE_DIR"))
            ? discovery.Runtime?.Pieces.WakeProblem
            : null;

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
                ApplyServerKey();
                ApplyVision(localData);
                return true;
            }

            // Publish the interpreter last. MindSidecarClient.IsConfigured uses
            // this variable as its readiness flag, so no registered runtime can
            // become observable before every auxiliary value has been applied.
            SetIfMissing(MindSidecarClient.PythonPathEnvironmentVariable, runtime.PythonPath);
            // Its hash only with the registered model: a model given by a variable is not the one the registration hashed.
            if (string.IsNullOrWhiteSpace(Environment.GetEnvironmentVariable("BAXY_MIND_LLM_GGUF")))
            {
                Environment.SetEnvironmentVariable(GgufSha256Variable, runtime.GgufSha256);
            }

            SetIfMissing("BAXY_MIND_LLM_GGUF", runtime.Gguf);
            SetIfMissing("BAXY_MIND_LLAMA_SERVER", runtime.LlamaServer);
            SetIfMissing("BAXY_MIND_LLAMA_BACKEND", runtime.LlamaBackend);
            SetIfMissing(
                "BAXY_MIND_NGL",
                runtime.GpuLayers.ToString(CultureInfo.InvariantCulture));
            ApplyPieces(runtime.Pieces);
            ApplyServerKey();
            ApplyVision(localData);
            if (string.IsNullOrWhiteSpace(discovery.Environment.Python))
            {
                SetIfMissing(MindSidecarClient.PythonEnvironmentVariable, runtime.Python);
            }
            return true;
        }
    }

    /// <summary>
    /// The registered pieces, each where no variable names one; the projector not with BAXY_VISION_OFF, as
    /// scripts/run_renew.cmd starts a bench. uso-116 (N23): System One's decision model is not one of them: it was handed
    /// to every install while what is measured and what the owner runs have gone without it since 2026-10-31 (it added
    /// nothing, and takes 446 MiB of the 5 GB). A bench or a launcher still gives it with BAXY_S1_GGUF.
    /// </summary>
    private static void ApplyPieces(MindRuntimePieces pieces)
    {
        SetIfMissing("BAXY_RENEW_TTS_DIR", pieces.Voice);
        SetIfMissing("BAXY_RENEW_WAKE_DIR", pieces.Wake);
        SetIfMissing("BAXY_RENEW_WAKE_FAST_DIR", pieces.WakeFast);
        SetIfMissing("BAXY_RENEW_STT_DIR", pieces.Stt);
        if (string.IsNullOrEmpty(Environment.GetEnvironmentVariable("BAXY_VISION_OFF")))
        {
            SetIfMissing("BAXY_MIND_MMPROJ", pieces.VisionProjector);
        }
    }

    /// <summary>
    /// PRV1 (revisión de privacidad 2026-11-09, PRIV-04): the mind's llama-server started with no key, on a port any page
    /// open in a browser of this PC can reach (and with a projector, on a fixed one), and by default it «reflects any
    /// Origin header back with credentials allowed» (llama.cpp, tools/server/README.md, «CORS», read 2026-11-09). It takes
    /// a key («--api-key KEY … (env: LLAMA_API_KEY)», the same README) and then answers 401 without it. One key at random
    /// for each start of BAXY, made here before the mind and the engine start: the mind gives it to its server and
    /// sends it with every request (src/baxy_mind/llm_server.py, server_key), and the engine's vision calls send it too
    /// (LocalVisionEndpoint.Authorize). A key already given (a bench that shares a server) is kept.
    /// </summary>
    internal const string ServerKeyVariable = "BAXY_MIND_LLAMA_KEY";

    private static void ApplyServerKey() =>
        SetIfMissing(ServerKeyVariable, Convert.ToHexStringLower(RandomNumberGenerator.GetBytes(32)));

    /// <summary>
    /// With a projector on the mind's server (registered, or given by a bench), the click's vision is pointed at it
    /// before the core starts, which reads these variables (LocalVisionEndpoint): a pinned port (8077 unless one is
    /// given), its chat endpoint, the mind's slot on that server, and the folder where that slot's state is set aside meanwhile,
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
        string own = $"http://127.0.0.1:{port}/v1/chat/completions";
        SetIfMissing("BAXY_VISION_ENDPOINT", own);
        if (string.Equals(Environment.GetEnvironmentVariable("BAXY_VISION_ENDPOINT"), own, StringComparison.Ordinal))
        {
            // PRV1 (PRIV-04): the mind's own server asks its key of the engine's vision calls too.
            SetIfMissing("BAXY_VISION_API_KEY", Environment.GetEnvironmentVariable(ServerKeyVariable));
        }

        SetIfMissing("BAXY_VISION_MODEL", "baxy");
        // Encargo 11: on a server several machines' minds share (measurement), the mind's slot (BAXY_MIND_SLOT).
        string? mindSlot = Environment.GetEnvironmentVariable("BAXY_MIND_SLOT");
        SetIfMissing("BAXY_VISION_SLOT", string.IsNullOrWhiteSpace(mindSlot) ? "0" : mindSlot.Trim());
        if (!string.IsNullOrWhiteSpace(localData))
        {
            SetIfMissing("BAXY_VISION_SLOT_DIR", Path.Combine(localData, "BAXY", "renew", "slots"));
        }
    }

    internal static string DefaultRegistrationPath() =>
        DefaultRegistrationPath(
            AppContext.BaseDirectory,
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData));

    /// <summary>
    /// The registration the App ships one folder above itself (the Steam build, scripts/build_steam.ps1), which names
    /// the product's own files; otherwise the one this machine registered (scripts/register_mind_runtime.ps1).
    /// </summary>
    internal static string DefaultRegistrationPath(string appFolder, string localData)
    {
        string packaged = Path.GetFullPath(Path.Combine(appFolder, "..", RegistrationFileName));
        if (File.Exists(packaged))
        {
            return packaged;
        }

        return string.IsNullOrWhiteSpace(localData)
            ? string.Empty
            : Path.Combine(localData, "BAXYRuntime", RegistrationFileName);
    }

    /// <summary>
    /// Every published asset is still compared with its registered SHA-256; a
    /// file whose size and timestamps did not change since a verified start is
    /// not read again (see <see cref="RuntimeFileHashCache"/>).
    /// </summary>
    private static MindRuntimeConfiguration? LoadRegistered(
        string manifestPath, string? givenServer, Func<IReadOnlyList<uint>> gpuVendors, out bool noSupportedGpu)
    {
        noSupportedGpu = false;
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
            MindRuntimeConfiguration? runtime = LoadRegistered(info, hashes, givenServer, gpuVendors, out noSupportedGpu);
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

    private static MindRuntimeConfiguration? LoadRegistered(
        FileInfo info,
        RuntimeFileHashCache hashes,
        string? givenServer,
        Func<IReadOnlyList<uint>> gpuVendors,
        out bool noSupportedGpu)
    {
        noSupportedGpu = false;
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
            string folder = info.DirectoryName!;
            if (root.ValueKind != JsonValueKind.Object
                || !HasKnownProperties(root)
                || !string.Equals(
                    RequiredString(root, "schema"),
                    RegistrationSchema,
                    StringComparison.Ordinal))
            {
                return null;
            }

            string? backend = null;
            string serverProperty = "llama_server";
            if (OptionalString(root, "llama_server_vulkan") is not null && string.IsNullOrWhiteSpace(givenServer))
            {
                backend = BackendFor(gpuVendors());
                if (backend is null)
                {
                    noSupportedGpu = true;
                    return null;
                }

                serverProperty = backend == "vulkan" ? "llama_server_vulkan" : "llama_server";
                // The GitHub release installs the CUDA folder only where the installer saw an NVIDIA GPU (CUDA EULA 2.1): a
                // card added later computes with the Vulkan folder that every installation has instead of not starting. A
                // folder that is there and is not what was registered still starts nothing.
                if (backend == "cuda" && CanonicalPath(folder, RequiredString(root, serverProperty)) is { } cudaServer
                    && !File.Exists(cudaServer))
                {
                    backend = "vulkan";
                    serverProperty = "llama_server_vulkan";
                }
            }

            string? python = ExistingFile(
                hashes,
                folder,
                RequiredString(root, "python"),
                "python.exe",
                RequiredString(root, "python_sha256"));
            string? pythonPath = ExistingDirectory(folder, RequiredString(root, "python_path"));
            string? gguf = ExistingFile(
                hashes,
                folder,
                RequiredString(root, "gguf"),
                expectedName: null,
                RequiredString(root, "gguf_sha256"));
            string? server = ExistingFile(
                hashes,
                folder,
                RequiredString(root, serverProperty),
                "llama-server.exe",
                RequiredString(root, serverProperty + "_sha256"));
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

            string? wake = RegisteredDirectory(hashes, folder, root, "renew_wake_dir", "renew_wake_sha256");
            return new MindRuntimeConfiguration(
                python,
                pythonPath,
                gguf,
                server,
                ngl,
                new MindRuntimePieces(
                    RegisteredDirectory(hashes, folder, root, "renew_tts_dir", "renew_tts_sha256"),
                    wake,
                    RegisteredDirectory(hashes, folder, root, "renew_wake_fast_dir", "renew_wake_fast_sha256"),
                    RegisteredDirectory(hashes, folder, root, "renew_stt_dir", "renew_stt_sha256"),
                    RegisteredModel(hashes, folder, root, "mmproj", "mmproj_sha256"),
                    wake is null ? UnverifiedWake(folder, root) : null),
                backend,
                RequiredString(root, "gguf_sha256"));
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

    /// <summary>
    /// The tuned model a registration offers (QWB2), or null: none offered, a registration that cannot be read, or an offer
    /// that is not well formed (a bare .gguf file name, a lower-case SHA-256, a positive size, an https address and a
    /// license). The offer never refuses the registration: the stock model starts all the same.
    /// </summary>
    internal static TunedModelOffer? TunedOffer(string registrationPath)
    {
        try
        {
            var info = new FileInfo(Path.GetFullPath(registrationPath));
            if (!info.Exists || info.Length is <= 0 or > MaximumRegistrationBytes)
            {
                return null;
            }

            using JsonDocument document = JsonDocument.Parse(File.ReadAllBytes(info.FullName));
            JsonElement root = document.RootElement;
            if (root.ValueKind != JsonValueKind.Object
                || OptionalString(root, "tuned_gguf") is not { } file
                || OptionalString(root, "tuned_gguf_sha256") is not { } sha256
                || OptionalString(root, "tuned_gguf_url") is not { } url
                || OptionalString(root, "tuned_gguf_license") is not { Length: > 0 } license
                || !root.TryGetProperty("tuned_gguf_bytes", out JsonElement size)
                || size.ValueKind != JsonValueKind.Number
                || !size.TryGetInt64(out long bytes)
                || bytes <= 0
                || !IsSha256(sha256)
                || file != Path.GetFileName(file)
                || !file.EndsWith(".gguf", StringComparison.OrdinalIgnoreCase)
                || file.AsSpan().IndexOfAny(Path.GetInvalidFileNameChars()) >= 0
                || !Uri.TryCreate(url, UriKind.Absolute, out Uri? address)
                || address.Scheme != Uri.UriSchemeHttps)
            {
                return null;
            }

            return new TunedModelOffer(file, sha256, bytes, url, license);
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

    /// <summary>The backend of this machine's GPUs (their PCI vendors); CUDA beside any other; null with none we serve.</summary>
    private static string? BackendFor(IReadOnlyList<uint> vendors)
    {
        var found = vendors.Select(static vendor => GpuBackends.GetValueOrDefault(vendor)).ToHashSet();
        return found.Contains("cuda") ? "cuda" : found.Contains("vulkan") ? "vulkan" : null;
    }

    /// <summary>A registered GGUF beside the model (System One's, the projector) that is what was registered.</summary>
    private static string? RegisteredModel(
        RuntimeFileHashCache hashes, string folder, JsonElement root, string path, string sha256)
    {
        try
        {
            string? file = ExistingFile(hashes, folder, OptionalString(root, path), expectedName: null, OptionalString(root, sha256));
            return file is not null && file.EndsWith(".gguf", StringComparison.OrdinalIgnoreCase) ? file : null;
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            return null; // only this piece stays off
        }
    }

    /// <summary>
    /// A registered folder (the voice, the wake word, the fast wake package, the recognizer) whose files are what was
    /// registered.
    /// </summary>
    private static string? RegisteredDirectory(
        RuntimeFileHashCache hashes, string folder, JsonElement root, string path, string sha256)
    {
        try
        {
            string? directory = ExistingDirectory(folder, OptionalString(root, path));
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
    /// V132: a registered wake folder that did not verify, as the cause the App says: wake_missing when it is not there
    /// or has no file (Get-BaxyDirectorySha256 has no hash for it), wake_changed otherwise (a file changed, added or
    /// unreadable); null when the registration names no wake word.
    /// </summary>
    private static string? UnverifiedWake(string folder, JsonElement root)
    {
        if (OptionalString(root, "renew_wake_dir") is not { } registered)
        {
            return null;
        }

        try
        {
            string? directory = ExistingDirectory(folder, registered);
            return directory is null || Directory.GetFiles(directory).Length == 0 ? "wake_missing" : "wake_changed";
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            return "wake_changed";
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
        string folder,
        string? value,
        string? expectedName,
        string? expectedSha256)
    {
        string? canonical = CanonicalPath(folder, value);
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

    private static string? ExistingDirectory(string folder, string? value)
    {
        string? canonical = CanonicalPath(folder, value);
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

    /// <summary>
    /// A registered path as a full one. A relative path is of a file of the product beside the registration (the Steam
    /// build), whatever its install folder is called, and never one outside that folder.
    /// </summary>
    private static string? CanonicalPath(string folder, string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return null;
        }

        try
        {
            if (!Path.IsPathFullyQualified(value))
            {
                string inside = Path.GetFullPath(Path.Combine(folder, value));
                return inside.StartsWith(
                    Path.TrimEndingDirectorySeparator(folder) + Path.DirectorySeparatorChar,
                    StringComparison.OrdinalIgnoreCase) ? inside : null;
            }

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
