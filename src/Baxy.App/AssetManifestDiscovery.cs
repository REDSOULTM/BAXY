using System.IO;
using System.Text.Json;

namespace Baxy.App;

internal sealed record AssetManifestDiagnostic(
    string Code,
    string Message,
    IReadOnlyList<string> Candidates);

/// <summary>
/// Reads the shared asset descriptor only for startup diagnostics. A discovered
/// candidate never bypasses the separately registered, SHA-256-verified runtime.
/// </summary>
internal static class AssetManifestDiscovery
{
    private const int MaximumDescriptorBytes = 64 * 1024;

    internal static AssetManifestDiagnostic InspectRequiredAssets(string? descriptorPath)
    {
        if (string.IsNullOrWhiteSpace(descriptorPath)
            || !Path.IsPathFullyQualified(descriptorPath))
        {
            return new(
                "asset_descriptor_missing",
                "No se indicó el descriptor de activos; ejecuta .\\scripts\\bootstrap.ps1.",
                []);
        }

        try
        {
            string fullPath = Path.GetFullPath(descriptorPath);
            using JsonDocument descriptor = ReadDocument(fullPath);
            JsonElement root = descriptor.RootElement;
            if (root.ValueKind != JsonValueKind.Object
                || RequiredString(root, "schema") != "baxy-assets-v1"
                || root.GetProperty("version").GetInt32() != 1
                || root.GetProperty("assets").ValueKind != JsonValueKind.Object)
            {
                return Invalid(fullPath);
            }

            string repositoryRoot = Path.GetDirectoryName(fullPath)!;
            Dictionary<string, List<string>> overrides = ReadOverrides(root, repositoryRoot);
            JsonElement assets = root.GetProperty("assets");
            var knownAssets = assets.EnumerateObject()
                .Select(asset => asset.Name)
                .ToHashSet(StringComparer.Ordinal);
            if (overrides.Keys.Any(name => !knownAssets.Contains(name)))
            {
                return Invalid(fullPath);
            }
            foreach (JsonProperty asset in assets.EnumerateObject())
            {
                JsonElement definition = asset.Value;
                if (definition.GetProperty("required").ValueKind != JsonValueKind.True)
                {
                    continue;
                }
                string kind = RequiredString(definition, "kind") ?? string.Empty;
                var candidates = new List<string>();
                string? environment = RequiredString(definition, "environment");
                AddCandidate(
                    candidates,
                    environment is null ? null : Environment.GetEnvironmentVariable(environment),
                    repositoryRoot);
                if (overrides.TryGetValue(asset.Name, out List<string>? local))
                {
                    foreach (string candidate in local)
                    {
                        AddCandidate(candidates, candidate, repositoryRoot);
                    }
                }
                foreach (JsonElement candidate in definition.GetProperty("candidates").EnumerateArray())
                {
                    AddCandidate(candidates, candidate.GetString(), repositoryRoot);
                }

                bool found = candidates.Any(candidate =>
                    kind == "file"
                        ? File.Exists(candidate)
                        : kind == "directory"
                        && Directory.Exists(candidate)
                        && RequiredFilesExist(definition, candidate));
                if (!found)
                {
                    string repair = RequiredString(definition, "repair")
                        ?? "Ejecuta .\\scripts\\bootstrap.ps1.";
                    return new(
                        "asset_missing",
                        $"{asset.Name} no está disponible. {repair}",
                        candidates);
                }
            }

            return new(
                "assets_ready",
                "El descriptor localiza todos los activos obligatorios.",
                []);
        }
        catch (Exception exception) when (exception is IOException
            or UnauthorizedAccessException
            or ArgumentException
            or NotSupportedException
            or JsonException
            or InvalidOperationException
            or KeyNotFoundException
            or FormatException
            or OverflowException)
        {
            return Invalid(descriptorPath);
        }
    }

    private static JsonDocument ReadDocument(string path)
    {
        var info = new FileInfo(path);
        if (!info.Exists || info.Length is <= 0 or > MaximumDescriptorBytes)
        {
            throw new IOException("Asset descriptor is missing or has an invalid size.");
        }
        using FileStream stream = info.OpenRead();
        return JsonDocument.Parse(
            stream,
            new JsonDocumentOptions
            {
                AllowTrailingCommas = false,
                CommentHandling = JsonCommentHandling.Disallow,
                MaxDepth = 6,
            });
    }

    private static Dictionary<string, List<string>> ReadOverrides(
        JsonElement descriptor,
        string repositoryRoot)
    {
        JsonElement local = descriptor.GetProperty("local_override");
        string environment = RequiredString(local, "environment")
            ?? throw new JsonException();
        string template = RequiredString(local, "default")
            ?? throw new JsonException();
        string schema = RequiredString(local, "schema")
            ?? throw new JsonException();
        string? configured = Environment.GetEnvironmentVariable(environment);
        string? overridePath = string.IsNullOrWhiteSpace(configured)
            ? ExpandPath(template, repositoryRoot)
            : Path.GetFullPath(configured);
        var result = new Dictionary<string, List<string>>(StringComparer.Ordinal);
        if (overridePath is null || !File.Exists(overridePath))
        {
            return result;
        }

        using JsonDocument document = ReadDocument(overridePath);
        JsonElement root = document.RootElement;
        if (root.EnumerateObject().Select(property => property.Name).ToHashSet(
                StringComparer.Ordinal) is not { Count: 2 } properties
            || !properties.SetEquals(["schema", "assets"])
            || RequiredString(root, "schema") != schema
            || root.GetProperty("assets").ValueKind != JsonValueKind.Object)
        {
            throw new JsonException();
        }
        foreach (JsonProperty asset in root.GetProperty("assets").EnumerateObject())
        {
            var values = new List<string>();
            if (asset.Value.ValueKind == JsonValueKind.String)
            {
                values.Add(asset.Value.GetString()!);
            }
            else if (asset.Value.ValueKind == JsonValueKind.Array)
            {
                values.AddRange(
                    asset.Value.EnumerateArray().Select(value =>
                        value.GetString() ?? throw new JsonException()));
            }
            else
            {
                throw new JsonException();
            }
            result.Add(asset.Name, values);
        }
        return result;
    }

    private static bool RequiredFilesExist(JsonElement definition, string directory)
    {
        if (!definition.TryGetProperty("required_files", out JsonElement files))
        {
            return true;
        }
        return files.ValueKind == JsonValueKind.Array
            && files.EnumerateArray().All(file =>
                File.Exists(Path.Combine(directory, file.GetString()!)));
    }

    private static void AddCandidate(
        List<string> candidates,
        string? template,
        string repositoryRoot)
    {
        if (string.IsNullOrWhiteSpace(template))
        {
            return;
        }
        string? expanded = ExpandPath(template, repositoryRoot);
        if (expanded is not null
            && !candidates.Contains(expanded, StringComparer.OrdinalIgnoreCase))
        {
            candidates.Add(expanded);
        }
    }

    private static string? ExpandPath(string template, string repositoryRoot)
    {
        var values = new Dictionary<string, string?>(StringComparer.Ordinal)
        {
            ["REPOSITORY_ROOT"] = repositoryRoot,
            ["LOCALAPPDATA"] = Environment.GetFolderPath(
                Environment.SpecialFolder.LocalApplicationData),
            ["USERPROFILE"] = Environment.GetFolderPath(
                Environment.SpecialFolder.UserProfile),
            ["BAXY_ASSETS_ROOT"] = Environment.GetEnvironmentVariable("BAXY_ASSETS_ROOT"),
        };
        string expanded = template;
        foreach ((string name, string? value) in values)
        {
            string token = "${" + name + "}";
            if (!expanded.Contains(token, StringComparison.Ordinal))
            {
                continue;
            }
            if (string.IsNullOrWhiteSpace(value))
            {
                return null;
            }
            expanded = expanded.Replace(token, value, StringComparison.Ordinal);
        }
        return expanded.Contains("${", StringComparison.Ordinal)
            ? null
            : Path.GetFullPath(expanded);
    }

    private static string? RequiredString(JsonElement root, string name)
    {
        JsonElement value = root.GetProperty(name);
        return value.ValueKind == JsonValueKind.String ? value.GetString() : null;
    }

    private static AssetManifestDiagnostic Invalid(string path) =>
        new(
            "asset_descriptor_invalid",
            $"El descriptor de activos no es válido: {path}. Ejecuta .\\scripts\\bootstrap.ps1.",
            []);
}
