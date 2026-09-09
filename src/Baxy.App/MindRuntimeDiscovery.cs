using System.Globalization;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace Baxy.App;

internal sealed record MindRuntimeConfiguration(
    string Source,
    string Python,
    string PythonPath,
    string Gguf,
    string LlamaServer,
    string? SttDirectory,
    string? WakeManifest,
    int GpuLayers,
    bool WakeOnStart,
    string? CpuProseAdapter = null);

internal sealed record MindRuntimeEnvironmentSnapshot(
    string? Disabled,
    string? Python,
    string? PythonPath,
    string? Gguf,
    string? LlamaServer,
    string? SttDirectory,
    string? GpuLayers,
    string? WakeManifest,
    string? WakeCascadeManifest,
    string? WakeOnStart,
    string? Offline,
    string? AssetDescriptor,
    string? CpuProseAdapter = null);

internal sealed record MindRuntimeDiscoveryResult(
    MindRuntimeEnvironmentSnapshot Environment,
    MindRuntimeConfiguration? Runtime,
    AssetManifestDiagnostic? AssetDiagnostic,
    bool UpdateAssetDiagnostic,
    bool CanConfigure,
    bool Disabled);

/// <summary>
/// Loads a deliberately registered local mind runtime. The registration is
/// fail-closed, and an explicit environment configuration always wins.
/// </summary>
internal static class MindRuntimeDiscovery
{
    private const string RegistrationSchema = "baxy-mind-runtime-v1";
    private const int MaximumRegistrationBytes = 16 * 1024;
    private const int MaximumWakeManifestBytes = 64 * 1024;

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
        "stt_dir",
        "stt_sha256",
        "wake_manifest",
        "wake_manifest_sha256",
        "tts_model",
        "tts_sha256",
        "ngl",
        "wake_on_start",
    ];

    private static readonly string[] SttFiles =
    [
        "encoder.int8.onnx",
        "decoder.int8.onnx",
        "joiner.int8.onnx",
        "tokens.txt",
    ];

    private static readonly object ApplyLock = new();

    internal static AssetManifestDiagnostic? LastAssetDiagnostic { get; private set; }

    internal static bool TryConfigureCurrentProcess() =>
        TryConfigureCurrentProcess(DefaultRegistrationPath());

    internal static bool TryConfigureCurrentProcess(string registrationPath) =>
        ApplyVerified(DiscoverVerified(registrationPath));

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
                AssetDiagnostic: null,
                UpdateAssetDiagnostic: false,
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
                AssetDiagnostic: null,
                UpdateAssetDiagnostic: false,
                CanConfigure: false,
                Disabled: false);
        }

        MindRuntimeConfiguration? runtime = LoadRegistered(registrationPath);
        if (runtime is null)
        {
            AssetManifestDiagnostic diagnostic =
                AssetManifestDiscovery.InspectRequiredAssets(environment.AssetDescriptor);
            return new(
                environment,
                Runtime: null,
                diagnostic,
                UpdateAssetDiagnostic: true,
                CanConfigure: hasExplicitPython,
                Disabled: false);
        }

        return new(
            environment,
            runtime,
            AssetDiagnostic: null,
            UpdateAssetDiagnostic: true,
            CanConfigure: true,
            Disabled: false);
    }

    internal static bool ApplyVerified(MindRuntimeDiscoveryResult discovery)
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

            if (discovery.UpdateAssetDiagnostic)
            {
                LastAssetDiagnostic = discovery.AssetDiagnostic;
            }
            if (!discovery.CanConfigure)
            {
                return false;
            }

            MindRuntimeConfiguration? runtime = discovery.Runtime;
            if (runtime is null)
            {
                return true;
            }

            // Publish the interpreter last. MindSidecarClient.IsConfigured uses
            // this variable as its readiness flag, so no registered runtime can
            // become observable before every auxiliary value has been applied.
            SetIfMissing(MindSidecarClient.PythonPathEnvironmentVariable, runtime.PythonPath);
            SetIfMissing("BAXY_MIND_LLM_GGUF", runtime.Gguf);
            SetIfMissing("BAXY_MIND_LLAMA_SERVER", runtime.LlamaServer);
            if (runtime.CpuProseAdapter is not null
                && string.Equals(
                    Environment.GetEnvironmentVariable("BAXY_MIND_LLM_GGUF"),
                    runtime.Gguf,
                    StringComparison.OrdinalIgnoreCase))
            {
                SetIfMissing("BAXY_MIND_CPU_PROSE_ADAPTER", runtime.CpuProseAdapter);
            }
            SetIfMissing(
                "BAXY_MIND_NGL",
                runtime.GpuLayers.ToString(CultureInfo.InvariantCulture));
            if (!string.IsNullOrWhiteSpace(runtime.SttDirectory))
            {
                SetIfMissing("BAXY_MIND_STT_DIR", runtime.SttDirectory);
            }

            if (!string.IsNullOrWhiteSpace(runtime.WakeManifest))
            {
                if (string.IsNullOrWhiteSpace(
                        Environment.GetEnvironmentVariable("BAXY_VOICE_WAKE_MANIFEST"))
                    && string.IsNullOrWhiteSpace(
                        Environment.GetEnvironmentVariable("BAXY_VOICE_WAKE_CASCADE_MANIFEST")))
                {
                    // Hash-declared wake is published even when boot listen is
                    // off, so the visible switch can start it without a click
                    // that first installs the path.
                    SetIfMissing("BAXY_VOICE_WAKE_MANIFEST", runtime.WakeManifest);
                    SetIfMissing(
                        "BAXY_VOICE_WAKE_CASCADE_MANIFEST",
                        runtime.WakeManifest);
                }

                // The FAR gate did not promote this head (see costuras). The
                // runtime still names it; loading requires this explicit seam.
                SetIfMissing("BAXY_VOICE_WAKE_ALLOW_UNCALIBRATED", "1");
            }

            if (runtime.WakeOnStart)
            {
                SetIfMissing("BAXY_VOICE_WAKE_ON_START", "1");
            }

            SetIfMissing("HF_HUB_OFFLINE", "1");
            if (string.IsNullOrWhiteSpace(discovery.Environment.Python))
            {
                SetIfMissing(MindSidecarClient.PythonEnvironmentVariable, runtime.Python);
            }
            return true;
        }
    }

    internal static string DefaultRegistrationPath()
    {
        string localData = Environment.GetFolderPath(
            Environment.SpecialFolder.LocalApplicationData);
        return string.IsNullOrWhiteSpace(localData)
            ? string.Empty
            : Path.Combine(localData, "BAXYRuntime", "mind-runtime-v1.json");
    }

    internal static MindRuntimeConfiguration? LoadRegistered(string manifestPath)
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
                || !HasExactProperties(root, root.TryGetProperty("cpu_prose_adapter", out _)
                    ? [.. RegistrationProperties, "cpu_prose_adapter"]
                    : RegistrationProperties)
                || !string.Equals(
                    RequiredString(root, "schema"),
                    RegistrationSchema,
                    StringComparison.Ordinal))
            {
                return null;
            }

            string? python = ExistingFile(
                RequiredString(root, "python"),
                "python.exe",
                RequiredString(root, "python_sha256"));
            string? pythonPath = ExistingDirectory(RequiredString(root, "python_path"));
            string? gguf = ExistingFile(
                RequiredString(root, "gguf"),
                expectedName: null,
                RequiredString(root, "gguf_sha256"));
            string? server = ExistingFile(
                RequiredString(root, "llama_server"),
                "llama-server.exe",
                RequiredString(root, "llama_server_sha256"));
            string? stt = ExistingDirectory(RequiredString(root, "stt_dir"));
            if (python is null
                || pythonPath is null
                || gguf is null
                || !gguf.EndsWith(".gguf", StringComparison.OrdinalIgnoreCase)
                || server is null
                || stt is null
                || !File.Exists(Path.Combine(pythonPath, "baxy_mind", "__main__.py"))
                || !MatchesSttHash(stt, RequiredString(root, "stt_sha256")))
            {
                return null;
            }

            JsonElement nglElement = root.GetProperty("ngl");
            JsonElement wakeElement = root.GetProperty("wake_on_start");
            if (nglElement.ValueKind != JsonValueKind.Number
                || !nglElement.TryGetInt32(out int ngl)
                || ngl is < 0 or > 999
                || wakeElement.ValueKind is not JsonValueKind.True and not JsonValueKind.False)
            {
                return null;
            }
            bool wakeOnStart = wakeElement.GetBoolean();
            JsonElement wakeManifestElement = root.GetProperty("wake_manifest");
            JsonElement wakeHashElement = root.GetProperty("wake_manifest_sha256");
            string? wakeManifest = null;
            if (wakeManifestElement.ValueKind == JsonValueKind.Null
                && wakeHashElement.ValueKind == JsonValueKind.Null)
            {
                if (wakeOnStart)
                {
                    return null;
                }
            }
            else
            {
                if (wakeManifestElement.ValueKind != JsonValueKind.String
                    || wakeHashElement.ValueKind != JsonValueKind.String)
                {
                    return null;
                }

                wakeManifest = ExistingFile(
                    wakeManifestElement.GetString(),
                    expectedName: null,
                    wakeHashElement.GetString());
                if (wakeManifest is null || !HasSupportedWakeManifestSchema(wakeManifest))
                {
                    return null;
                }
            }

            JsonElement ttsModelElement = root.GetProperty("tts_model");
            JsonElement ttsHashElement = root.GetProperty("tts_sha256");
            if (ttsModelElement.ValueKind == JsonValueKind.Null
                && ttsHashElement.ValueKind == JsonValueKind.Null)
            {
                // Neural TTS is optional: SAPI remains the documented fallback.
            }
            else if (ttsModelElement.ValueKind != JsonValueKind.String
                || ttsHashElement.ValueKind != JsonValueKind.String
                || ExistingFile(
                    ttsModelElement.GetString(),
                    expectedName: null,
                    ttsHashElement.GetString()) is null)
            {
                return null;
            }

            string? cpuProseAdapter = null;
            if (root.TryGetProperty("cpu_prose_adapter", out JsonElement adapter))
            {
                if (adapter.ValueKind != JsonValueKind.Object
                    || !HasExactProperties(adapter, ["schema", "gguf", "gguf_sha256", "base_gguf_sha256"])
                    || RequiredString(adapter, "schema") != "baxy-cpu-prose-adapter-v1"
                    || RequiredString(adapter, "base_gguf_sha256") != RequiredString(root, "gguf_sha256"))
                {
                    return null;
                }
                string? adapterFile = ExistingFile(
                    RequiredString(adapter, "gguf"),
                    expectedName: null,
                    RequiredString(adapter, "gguf_sha256"));
                if (adapterFile is null || !adapterFile.EndsWith(".gguf", StringComparison.OrdinalIgnoreCase))
                {
                    return null;
                }
                cpuProseAdapter = JsonSerializer.Serialize(new
                {
                    schema = "baxy-cpu-prose-adapter-v1",
                    gguf = adapterFile,
                    gguf_sha256 = RequiredString(adapter, "gguf_sha256"),
                    base_gguf_sha256 = RequiredString(adapter, "base_gguf_sha256"),
                });
            }

            return new MindRuntimeConfiguration(
                info.FullName,
                python,
                pythonPath,
                gguf,
                server,
                stt,
                wakeManifest,
                ngl,
                wakeOnStart,
                cpuProseAdapter);
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

    private static string? ExistingFile(
        string? value,
        string? expectedName,
        string? expectedSha256)
    {
        string? canonical = CanonicalPath(value);
        if (canonical is null
            || !File.Exists(canonical)
            || !IsSha256(expectedSha256)
            || !string.Equals(
                FileSha256(canonical),
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

    private static bool HasSupportedWakeManifestSchema(string path)
    {
        var info = new FileInfo(path);
        if (!info.Exists || info.Length is <= 0 or > MaximumWakeManifestBytes)
        {
            return false;
        }

        using FileStream stream = info.OpenRead();
        using JsonDocument document = JsonDocument.Parse(
            stream,
            new JsonDocumentOptions
            {
                AllowTrailingCommas = false,
                CommentHandling = JsonCommentHandling.Disallow,
                MaxDepth = 8,
            });
        if (document.RootElement.ValueKind != JsonValueKind.Object
            || !document.RootElement.TryGetProperty("schema", out JsonElement schema)
            || schema.ValueKind != JsonValueKind.String)
        {
            return false;
        }

        return schema.GetString() is "baxy-wakeword-v1" or "baxy-wake-cascade-v1";
    }

    private static bool MatchesSttHash(string directory, string? expectedSha256)
    {
        if (!IsSha256(expectedSha256))
        {
            return false;
        }

        var fingerprint = new StringBuilder();
        foreach (string name in SttFiles)
        {
            string path = Path.Combine(directory, name);
            if (!File.Exists(path))
            {
                return false;
            }
            fingerprint.Append(name)
                .Append(':')
                .Append(FileSha256(path))
                .Append('\n');
        }

        byte[] digest = SHA256.HashData(Encoding.UTF8.GetBytes(fingerprint.ToString()));
        return string.Equals(
            Convert.ToHexStringLower(digest),
            expectedSha256,
            StringComparison.Ordinal);
    }

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

    private static bool HasExactProperties(JsonElement root, IReadOnlyCollection<string> expected)
    {
        var actual = new HashSet<string>(StringComparer.Ordinal);
        foreach (JsonProperty property in root.EnumerateObject())
        {
            if (!actual.Add(property.Name))
            {
                return false;
            }
        }

        return actual.SetEquals(expected);
    }

    private static MindRuntimeEnvironmentSnapshot CaptureEnvironment() =>
        new(
            Environment.GetEnvironmentVariable(MindSidecarClient.DisabledEnvironmentVariable),
            Environment.GetEnvironmentVariable(MindSidecarClient.PythonEnvironmentVariable),
            Environment.GetEnvironmentVariable(MindSidecarClient.PythonPathEnvironmentVariable),
            Environment.GetEnvironmentVariable("BAXY_MIND_LLM_GGUF"),
            Environment.GetEnvironmentVariable("BAXY_MIND_LLAMA_SERVER"),
            Environment.GetEnvironmentVariable("BAXY_MIND_STT_DIR"),
            Environment.GetEnvironmentVariable("BAXY_MIND_NGL"),
            Environment.GetEnvironmentVariable("BAXY_VOICE_WAKE_MANIFEST"),
            Environment.GetEnvironmentVariable("BAXY_VOICE_WAKE_CASCADE_MANIFEST"),
            Environment.GetEnvironmentVariable("BAXY_VOICE_WAKE_ON_START"),
            Environment.GetEnvironmentVariable("HF_HUB_OFFLINE"),
            Environment.GetEnvironmentVariable("BAXY_ASSET_DESCRIPTOR"),
            Environment.GetEnvironmentVariable("BAXY_MIND_CPU_PROSE_ADAPTER"));

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
            Environment.GetEnvironmentVariable("BAXY_MIND_STT_DIR"),
            expected.SttDirectory,
            StringComparison.Ordinal)
        && string.Equals(
            Environment.GetEnvironmentVariable("BAXY_MIND_NGL"),
            expected.GpuLayers,
            StringComparison.Ordinal)
        && string.Equals(
            Environment.GetEnvironmentVariable("BAXY_VOICE_WAKE_MANIFEST"),
            expected.WakeManifest,
            StringComparison.Ordinal)
        && string.Equals(
            Environment.GetEnvironmentVariable("BAXY_VOICE_WAKE_CASCADE_MANIFEST"),
            expected.WakeCascadeManifest,
            StringComparison.Ordinal)
        && string.Equals(
            Environment.GetEnvironmentVariable("BAXY_VOICE_WAKE_ON_START"),
            expected.WakeOnStart,
            StringComparison.Ordinal)
        && string.Equals(
            Environment.GetEnvironmentVariable("HF_HUB_OFFLINE"),
            expected.Offline,
            StringComparison.Ordinal)
        && string.Equals(
            Environment.GetEnvironmentVariable("BAXY_MIND_CPU_PROSE_ADAPTER"),
            expected.CpuProseAdapter,
            StringComparison.Ordinal)
        && string.Equals(
            Environment.GetEnvironmentVariable("BAXY_ASSET_DESCRIPTOR"),
            expected.AssetDescriptor,
            StringComparison.Ordinal);

    private static bool IsDisabled(string? value) =>
        string.Equals(value, "1", StringComparison.Ordinal);

    private static void SetIfMissing(string name, string value)
    {
        if (string.IsNullOrWhiteSpace(Environment.GetEnvironmentVariable(name)))
        {
            Environment.SetEnvironmentVariable(name, value);
        }
    }
}
