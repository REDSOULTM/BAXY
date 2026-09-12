using System.Security.Cryptography;
using System.Text.Json;

namespace Baxy.Providers.Windows.External;

internal sealed class WindowsKnownFileAdapter : IExternalOperationAdapter
{
    private readonly string _trashRoot;
    private readonly IReadOnlyDictionary<string, string[]> _configuredRoots;

    internal WindowsKnownFileAdapter(string dataRoot)
        : this(dataRoot, DefaultRoots())
    {
    }

    internal WindowsKnownFileAdapter(
        string dataRoot,
        IReadOnlyDictionary<string, string[]> configuredRoots)
    {
        _trashRoot = Path.Combine(Path.GetFullPath(dataRoot), "known-file-trash");
        _configuredRoots = configuredRoots;
    }

    public bool CanHandle(string operation) => operation is
        "filesystem.known.duplicates" or "filesystem.known.search"
        or "filesystem.known.trash.named" or "filesystem.path.ensure.absent";

    public ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        var effectBoundary = new ExternalEffectBoundary();
        try
        {
            if (operation == "filesystem.path.ensure.absent")
                return ValueTask.FromResult(EnsureAbsent(operation, arguments, effectBoundary));
            string folder = ExternalJson.RequiredString(arguments, "folder");
            (string Label, string Root)[] roots = Roots(folder);
            if (arguments.TryGetProperty("subdirectory", out JsonElement subdirectoryElement))
            {
                string subdirectory = subdirectoryElement.GetString()?.Trim()
                    ?? throw new InvalidDataException("known_subdirectory_invalid");
                roots = SubdirectoryRoots(roots, subdirectory);
            }
            return ValueTask.FromResult(operation switch
            {
                "filesystem.known.duplicates" => Duplicates(
                    operation, roots, arguments, cancellationToken),
                "filesystem.known.search" => Search(operation, roots, arguments),
                "filesystem.known.trash.named" => Trash(
                    operation, roots, arguments, effectBoundary),
                _ => ExternalJson.Failure(operation, "known_file_operation_invalid"),
            });
        }
        catch (OperationCanceledException) when (
            cancellationToken.IsCancellationRequested && effectBoundary.WasCrossed)
        {
            return ValueTask.FromResult(effectBoundary.Failure(
                operation, "known_folder_filesystem_unavailable"));
        }
        catch (InvalidDataException exception)
        {
            return ValueTask.FromResult(effectBoundary.Failure(operation, exception.Message));
        }
        catch (Exception exception) when (exception is IOException
            or UnauthorizedAccessException or System.Security.SecurityException)
        {
            return ValueTask.FromResult(effectBoundary.Failure(
                operation, "known_folder_filesystem_unavailable"));
        }
    }

    private ExternalCapabilityReceipt EnsureAbsent(
        string operation,
        JsonElement arguments,
        ExternalEffectBoundary effectBoundary)
    {
        string requested = ExternalJson.RequiredString(arguments, "path").Trim()
            .Replace('/', Path.DirectorySeparatorChar);
        requested = Environment.ExpandEnvironmentVariables(requested);
        if (!Path.IsPathFullyQualified(requested))
            return ExternalJson.Failure(operation, "absolute_file_path_required");
        string path = Path.GetFullPath(requested);
        if (!File.Exists(path) && !Directory.Exists(path))
        {
            return ExternalJson.Success(operation, ExternalJson.Create(writer =>
            {
                writer.WriteStartObject(); writer.WriteNumber("version", 1);
                writer.WriteString("reviewLabel", Path.GetFileName(path));
                writer.WriteBoolean("alreadyAbsent", true);
                writer.WriteString("authority", "windows_absolute_path_absence_postread");
                writer.WriteEndObject();
            }), effectObserved: false);
        }
        if (Directory.Exists(path))
            return ExternalJson.Failure(operation, "absolute_path_is_directory");
        string profile = Path.GetFullPath(Environment.GetFolderPath(
            Environment.SpecialFolder.UserProfile)).TrimEnd(Path.DirectorySeparatorChar);
        string temporary = Path.GetFullPath(Path.GetTempPath())
            .TrimEnd(Path.DirectorySeparatorChar);
        bool allowed = path.StartsWith(profile + Path.DirectorySeparatorChar,
                StringComparison.OrdinalIgnoreCase)
            || path.StartsWith(temporary + Path.DirectorySeparatorChar,
                StringComparison.OrdinalIgnoreCase);
        if (!allowed) return ExternalJson.Failure(operation, "absolute_file_outside_recoverable_roots");
        if ((File.GetAttributes(path) & FileAttributes.ReparsePoint) != 0)
            return ExternalJson.Failure(operation, "absolute_file_reparse_point_rejected");
        effectBoundary.Cross();
        Directory.CreateDirectory(_trashRoot);
        string restoreId = "restore_" + Guid.NewGuid().ToString("N");
        string destination = Path.Combine(_trashRoot, restoreId + "_" + Path.GetFileName(path));
        string hash = Hash(path);
        File.Move(path, destination);
        if (File.Exists(path) || !File.Exists(destination)
            || !string.Equals(Hash(destination), hash, StringComparison.Ordinal))
            return ExternalJson.Failure(operation, "absolute_file_trash_postread_failed", true);
        return ExternalJson.Success(operation, ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1);
            writer.WriteString("reviewLabel", Path.GetFileName(path));
            writer.WriteString("restoreId", restoreId); writer.WriteString("sha256", hash);
            writer.WriteBoolean("alreadyAbsent", false);
            writer.WriteString("authority", "windows_absolute_file_private_trash_postread");
            writer.WriteEndObject();
        }), effectObserved: true);
    }

    private static ExternalCapabilityReceipt Duplicates(
        string operation,
        IReadOnlyList<(string Label, string Root)> roots,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        int limit = Math.Clamp(ExternalJson.OptionalInt(arguments, "limit", 20), 1, 100);
        var candidates = Enumerate(roots)
            .Select(item => (item.Label, item.Path, Length: new FileInfo(item.Path).Length))
            .GroupBy(item => item.Length)
            .Where(group => group.Count() > 1)
            .SelectMany(group => group)
            .Take(10_000)
            .ToArray();
        var hashed = new List<(string Label, string Path, long Length, string Sha256)>();
        foreach (var candidate in candidates)
        {
            cancellationToken.ThrowIfCancellationRequested();
            using FileStream stream = new(
                candidate.Path, FileMode.Open, FileAccess.Read,
                FileShare.ReadWrite | FileShare.Delete);
            hashed.Add((candidate.Label, candidate.Path, candidate.Length,
                Convert.ToHexStringLower(SHA256.HashData(stream))));
        }
        var groups = hashed
            .GroupBy(item => (item.Length, item.Sha256))
            .Where(group => group.Count() > 1)
            .OrderByDescending(group => group.Key.Length)
            .ThenBy(group => group.Key.Sha256, StringComparer.Ordinal)
            .Take(limit)
            .Select(group => group.OrderBy(item => Path.GetFileName(item.Path),
                    StringComparer.OrdinalIgnoreCase).ToArray())
            .ToArray();
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1);
            writer.WriteNumber("groupCount", groups.Length); writer.WriteStartArray("groups");
            foreach (var group in groups)
            {
                writer.WriteStartObject(); writer.WriteNumber("size", group[0].Length);
                writer.WriteString("sha256", group[0].Sha256); writer.WriteStartArray("files");
                foreach (var file in group)
                {
                    writer.WriteStartObject(); writer.WriteString("fileId", Identity(file.Label, file.Path));
                    writer.WriteString("name", Path.GetFileName(file.Path));
                    writer.WriteString("folder", file.Label); writer.WriteEndObject();
                }
                writer.WriteEndArray(); writer.WriteEndObject();
            }
            writer.WriteEndArray(); writer.WriteString(
                "authority", "windows_known_duplicates_size_sha256_snapshot");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effectObserved: false);
    }

    private static ExternalCapabilityReceipt Search(
        string operation,
        IReadOnlyList<(string Label, string Root)> roots,
        JsonElement arguments)
    {
        string query = ExternalJson.RequiredString(arguments, "query").Trim();
        int limit = Math.Clamp(ExternalJson.OptionalInt(arguments, "limit", 20), 1, 100);
        List<(string Label, string Root)> enumerationRoots = [];
        var matches = Enumerate(roots, enumerationRoots)
            .Where(item => MatchesQuery(Path.GetFileName(item.Path), query))
            .OrderBy(item => item.Label, StringComparer.Ordinal)
            .ThenBy(item => Path.GetFileName(item.Path), StringComparer.OrdinalIgnoreCase)
            .Take(limit)
            .Select(item => new
            {
                item.Label,
                Name = Path.GetFileName(item.Path),
                Length = new FileInfo(item.Path).Length,
                ModifiedUtc = File.GetLastWriteTimeUtc(item.Path),
                Identity = Identity(item.Label, item.Path),
            })
            .ToArray();
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1);
            writer.WriteString("query", query); writer.WriteNumber("count", matches.Length);
            writer.WriteStartArray("files");
            foreach (var match in matches)
            {
                writer.WriteStartObject(); writer.WriteString("fileId", match.Identity);
                writer.WriteString("name", match.Name); writer.WriteString("folder", match.Label);
                writer.WriteNumber("size", match.Length); writer.WriteString("modifiedUtc", match.ModifiedUtc);
                writer.WriteEndObject();
            }
            writer.WriteEndArray();
            writer.WriteStartObject("searchScope");
            writer.WriteStartArray("enumerationRoots");
            foreach (var root in enumerationRoots)
            {
                writer.WriteStartObject();
                writer.WriteString("folder", root.Label);
                writer.WriteString("path", root.Root);
                writer.WriteEndObject();
            }
            writer.WriteEndArray();
            writer.WriteNumber("maxRecursionDepth", 12);
            writer.WriteBoolean("ignoreInaccessible", true);
            writer.WriteBoolean("skipReparsePoints", true);
            writer.WriteNumber("resultLimit", limit);
            writer.WriteBoolean("resultsMayBeTruncated", matches.Length == limit);
            writer.WriteBoolean("exhaustive", false);
            writer.WriteEndObject();
            writer.WriteString("authority", "windows_known_folders_bounded_postread");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effectObserved: false);
    }

    private ExternalCapabilityReceipt Trash(
        string operation,
        IReadOnlyList<(string Label, string Root)> roots,
        JsonElement arguments,
        ExternalEffectBoundary effectBoundary)
    {
        string fileName = ExternalJson.RequiredString(arguments, "fileName").Trim();
        if (fileName != Path.GetFileName(fileName)
            || fileName.IndexOfAny(Path.GetInvalidFileNameChars()) >= 0
            || fileName.Contains('*') || fileName.Contains('?'))
            return ExternalJson.Failure(operation, "known_file_name_invalid");
        var matches = Enumerate(roots)
            .Where(item => string.Equals(
                Path.GetFileName(item.Path), fileName, StringComparison.OrdinalIgnoreCase))
            .Take(2)
            .ToArray();
        if (matches.Length == 0) return ExternalJson.Failure(operation, "known_file_not_found");
        if (matches.Length > 1) return ExternalJson.Failure(operation, "known_file_ambiguous");
        (string label, string source) = matches[0];
        effectBoundary.Cross();
        Directory.CreateDirectory(_trashRoot);
        string restoreId = "restore_" + Guid.NewGuid().ToString("N");
        string destination = Path.Combine(_trashRoot, restoreId + "_" + fileName);
        File.Move(source, destination);
        if (File.Exists(source) || !File.Exists(destination))
            return ExternalJson.Failure(operation, "known_file_trash_postread_failed", true);
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1);
            writer.WriteString("reviewLabel", fileName); writer.WriteString("folder", label);
            writer.WriteString("restoreId", restoreId); writer.WriteBoolean("sourceAbsent", true);
            writer.WriteString("sha256", Convert.ToHexStringLower(
                SHA256.HashData(File.ReadAllBytes(destination))));
            writer.WriteString("authority", "windows_known_file_private_trash_postread");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effectObserved: true);
    }

    private static IEnumerable<(string Label, string Path)> Enumerate(
        IReadOnlyList<(string Label, string Root)> roots,
        List<(string Label, string Root)>? enumerationRoots = null)
    {
        var options = new EnumerationOptions
        {
            RecurseSubdirectories = true,
            IgnoreInaccessible = true,
            AttributesToSkip = FileAttributes.ReparsePoint,
            MaxRecursionDepth = 12,
        };
        foreach ((string label, string root) in roots)
        {
            if (!Directory.Exists(root)) continue;
            // Record the attempted enumeration scope, not exhaustive access.
            // IgnoreInaccessible may skip descendants without reporting them.
            enumerationRoots?.Add((label, root));
            foreach (string file in Directory.EnumerateFiles(root, "*", options))
                yield return (label, file);
        }
    }

    private static bool MatchesQuery(string name, string query)
    {
        string normalized = query.Trim();
        if (normalized is "*.pdf" or ".pdf")
            return name.EndsWith(".pdf", StringComparison.OrdinalIgnoreCase);
        if (normalized is "*.txt" or ".txt")
            return name.EndsWith(".txt", StringComparison.OrdinalIgnoreCase);
        if (normalized is "*.doc" or "*.docx" or "*.doc*" or ".doc" or "word")
            return name.EndsWith(".doc", StringComparison.OrdinalIgnoreCase)
                || name.EndsWith(".docx", StringComparison.OrdinalIgnoreCase);
        if (normalized is "*.xls" or "*.xlsx" or "*.xls*" or ".xls" or "spreadsheet")
            return name.EndsWith(".xls", StringComparison.OrdinalIgnoreCase)
                || name.EndsWith(".xlsx", StringComparison.OrdinalIgnoreCase);
        return name.Contains(normalized, StringComparison.OrdinalIgnoreCase);
    }

    private (string Label, string Root)[] Roots(string folder)
    {
        if (folder == "all_known")
            return _configuredRoots.SelectMany(pair => pair.Value.Select(root =>
                (pair.Key, Path.GetFullPath(root)))).ToArray();
        if (!_configuredRoots.TryGetValue(folder, out string[]? roots))
            throw new InvalidDataException("known_folder_invalid");
        return roots.Select(root => (folder, Path.GetFullPath(root))).ToArray();
    }

    private static Dictionary<string, string[]> DefaultRoots() => new(StringComparer.Ordinal)
    {
        ["desktop"] = [Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory)],
        ["documents"] = [Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments)],
        ["downloads"] = [Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), "Downloads")],
    };

    private static (string Label, string Root)[] SubdirectoryRoots(
        IReadOnlyList<(string Label, string Root)> roots,
        string subdirectory)
    {
        if (string.IsNullOrWhiteSpace(subdirectory)
            || Path.IsPathRooted(subdirectory)
            || subdirectory.Split(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar)
                .Any(part => part is "" or "." or ".."))
            throw new InvalidDataException("known_subdirectory_invalid");
        return roots.Select(item =>
        {
            string root = Path.GetFullPath(item.Root)
                .TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
            string candidate = Path.GetFullPath(Path.Combine(root, subdirectory));
            if (!candidate.StartsWith(root + Path.DirectorySeparatorChar,
                    StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException("known_subdirectory_invalid");
            if (Directory.Exists(candidate)
                && (File.GetAttributes(candidate) & FileAttributes.ReparsePoint) != 0)
                throw new InvalidDataException("known_subdirectory_reparse_point");
            return (item.Label, candidate);
        }).ToArray();
    }

    private static string Identity(string label, string path)
    {
        byte[] hash = SHA256.HashData(System.Text.Encoding.UTF8.GetBytes(
            label + "\n" + Path.GetFullPath(path)));
        return "known_" + Convert.ToHexStringLower(hash.AsSpan(0, 12));
    }

    private static string Hash(string path)
    {
        using FileStream stream = File.OpenRead(path);
        return Convert.ToHexStringLower(SHA256.HashData(stream));
    }
}
