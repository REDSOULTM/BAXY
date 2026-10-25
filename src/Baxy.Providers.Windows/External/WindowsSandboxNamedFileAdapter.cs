using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Baxy.Providers.Windows.Filesystem;

namespace Baxy.Providers.Windows.External;

internal sealed class WindowsSandboxNamedFileAdapter : IExternalOperationAdapter
{
    // Holdout v5 V5E032/V5E040: how long the search for a file of the person's by its name walks (as file.read's).
    private static readonly TimeSpan WalkTimeLimit = TimeSpan.FromSeconds(8);
    private const int CandidatesShown = 5;

    private readonly string _root;
    private readonly Func<string, string?> _knownFolder;
    private readonly IReadOnlyList<string> _privateRoots;
    private readonly Func<DateTime> _utcNow;

    /// <param name="utcNow">The clock of the walk's time limit (tests stop it where they need).</param>
    internal WindowsSandboxNamedFileAdapter(
        string dataRoot,
        Func<string, string?>? knownFolder = null,
        IReadOnlyList<string>? privateRoots = null,
        Func<DateTime>? utcNow = null)
    {
        _root = Path.Combine(Path.GetFullPath(dataRoot), "filesystem-sandbox");
        _knownFolder = knownFolder ?? WindowsFileToolsAdapter.KnownFolderPath;
        _privateRoots = privateRoots ?? BaxyPrivateArea.DefaultRoots();
        _utcNow = utcNow ?? (() => DateTime.UtcNow);
    }

    public bool CanHandle(string operation) => operation is
        "filesystem.sandbox.diff.named" or "filesystem.sandbox.move.named";

    public ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        var effectBoundary = new ExternalEffectBoundary();
        try
        {
            return ValueTask.FromResult(operation switch
            {
                "filesystem.sandbox.diff.named" => Diff(operation, arguments),
                "filesystem.sandbox.move.named" => Move(
                    operation, arguments, effectBoundary),
                _ => ExternalJson.Failure(operation, "sandbox_named_operation_invalid"),
            });
        }
        catch (OperationCanceledException) when (
            cancellationToken.IsCancellationRequested && effectBoundary.WasCrossed)
        {
            return ValueTask.FromResult(effectBoundary.Failure(
                operation, "sandbox_named_filesystem_unavailable"));
        }
        catch (InvalidDataException exception)
        {
            return ValueTask.FromResult(effectBoundary.Failure(operation, exception.Message));
        }
        catch (Exception exception) when (exception is IOException
            or UnauthorizedAccessException or System.Security.SecurityException)
        {
            return ValueTask.FromResult(effectBoundary.Failure(
                operation, "sandbox_named_filesystem_unavailable"));
        }
    }

    private ExternalCapabilityReceipt Move(
        string operation,
        JsonElement arguments,
        ExternalEffectBoundary effectBoundary)
    {
        string sourceName = SafeFileName(ExternalJson.RequiredString(arguments, "sourceFileName"));
        string relativeDestination = ExternalJson.RequiredString(arguments, "destinationRelativePath")
            .Replace(Path.AltDirectorySeparatorChar, Path.DirectorySeparatorChar);
        bool copy = arguments.TryGetProperty("copy", out JsonElement copyElement)
            && copyElement.ValueKind == JsonValueKind.True;
        if (arguments.TryGetProperty("folder", out JsonElement folder))
            return InFolder(operation, arguments, folder.GetString() ?? string.Empty, sourceName, relativeDestination,
                copy, effectBoundary);
        string source = ResolveUnique(sourceName);
        string destination = ConfinedDestination(relativeDestination);
        if (File.Exists(destination) || Directory.Exists(destination))
            return ExternalJson.Failure(operation, "sandbox_move_destination_exists");
        string hash = Hash(source);
        effectBoundary.Cross();
        Directory.CreateDirectory(Path.GetDirectoryName(destination)!);
        if (!Transfer(source, destination, copy, hash))
            return ExternalJson.Failure(operation, "sandbox_move_postread_failed", true);
        return Moved(operation, sourceName, relativeDestination, hash, copy,
            "sandbox_named_move_hash_absence_postread", null);
    }

    // Holdout v5 V5E032/V5E040: a file of the person's, named by its name inside a known folder (or a subfolder of it),
    // moved or copied to a path inside that same folder. The file is the one of that name under it (file.read's walk,
    // 8 s at most); the destination is a file that does not exist yet, in a folder that does (a folder alone is that
    // folder, with the file's own name), never outside the folder named nor in BAXY's own area.
    private ExternalCapabilityReceipt InFolder(
        string operation,
        JsonElement arguments,
        string label,
        string sourceName,
        string relativeDestination,
        bool copy,
        ExternalEffectBoundary effectBoundary)
    {
        if (_knownFolder(label) is not { } known)
            return ExternalJson.Failure(operation, "known_folder_invalid");
        string root = Path.GetFullPath(known).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        string? subdirectory = null;
        if (arguments.TryGetProperty("subdirectory", out JsonElement subdirectoryElement))
        {
            subdirectory = subdirectoryElement.GetString()?.Trim() ?? string.Empty;
            root = WindowsKnownFileAdapter.SubdirectoryRoots([(label, root)], subdirectory, _privateRoots)[0].Root;
            if (!Directory.Exists(root))
                return ExternalJson.Failure(operation, "known_subdirectory_not_found");
        }

        (string[] matches, bool walkStopped) = FindInFolder(root, label, sourceName);
        // The one file a walk cut by its time limit saw is not the only one of that name (file.edit's rule,
        // known_file_search_incomplete): nothing is moved.
        if (matches.Length == 0 || (matches.Length == 1 && walkStopped))
            return ExternalJson.Failure(operation, walkStopped ? "named_file_search_incomplete" : "named_file_not_found");
        if (matches.Length > 1)
        {
            return new ExternalCapabilityReceipt(operation, false, false, ExternalJson.Create(writer =>
            {
                writer.WriteStartObject(); writer.WriteNumber("version", 1);
                writer.WriteStartArray("candidates");
                foreach (string match in matches.Take(CandidatesShown))
                    writer.WriteStringValue(Relative(root, match));
                writer.WriteEndArray();
                if (matches.Length > CandidatesShown) writer.WriteBoolean("candidatesTruncated", true);
                writer.WriteEndObject();
            }), "named_file_ambiguous");
        }

        string source = matches[0];
        if (subdirectory is not null && !Path.IsPathFullyQualified(relativeDestination))
            relativeDestination = WithoutRepeatedFolder(root, subdirectory, relativeDestination);
        string destination = Path.GetFullPath(Path.IsPathFullyQualified(relativeDestination) ? relativeDestination
            : Path.Combine(root, relativeDestination)).TrimEnd(Path.DirectorySeparatorChar);
        // A name with «:» past the folder is a stream of another file of theirs («otro.txt:oculto»), not a file in it.
        if (!destination.StartsWith(root + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase)
            || destination[(root.Length + 1)..].Split(Path.DirectorySeparatorChar)
                .Any(static part => part.IndexOfAny(Path.GetInvalidFileNameChars()) >= 0))
            return ExternalJson.Failure(operation, "named_file_destination_invalid");
        if (Directory.Exists(destination))
            destination = Path.Combine(destination, Path.GetFileName(source));
        if (BaxyPrivateArea.Holds(_privateRoots, destination))
            return ExternalJson.Failure(operation, "path_reserved");
        if (File.Exists(destination) || Directory.Exists(destination))
            return ExternalJson.Failure(operation, "named_file_destination_exists");
        string parent = Path.GetDirectoryName(destination)!;
        if (!Directory.Exists(parent))
            return ExternalJson.Failure(operation, "named_file_destination_folder_not_found");
        if (CrossesReparsePoint(root, parent))
            return ExternalJson.Failure(operation, "named_file_destination_invalid");
        string hash = Hash(source);
        effectBoundary.Cross();
        if (!Transfer(source, destination, copy, hash))
            return ExternalJson.Failure(operation, "named_file_move_postread_failed", true);
        return Moved(operation, sourceName, Relative(root, destination), hash, copy,
            "known_folder_named_move_hash_absence_postread", writer =>
            {
                writer.WriteString("folder", label);
                if (subdirectory is not null) writer.WriteString("subdirectory", subdirectory);
                writer.WriteString("sourceRelativePath", Relative(root, source));
            });
    }

    // The files of that whole name (case aside) under the folder, walked as the known-folder tools walk it.
    private (string[] Matches, bool WalkStopped) FindInFolder(string root, string label, string fileName)
    {
        var matches = new List<string>();
        DateTime deadline = _utcNow() + WalkTimeLimit;
        foreach (string file in Directory.EnumerateFiles(root, "*", WindowsKnownFileAdapter.WalkOptions(label)))
        {
            if (_utcNow() >= deadline)
                return ([.. matches], true);
            if (string.Equals(Path.GetFileName(file), fileName, StringComparison.OrdinalIgnoreCase)
                && !BaxyPrivateArea.Holds(_privateRoots, file))
            {
                matches.Add(file);
                if (matches.Count > CandidatesShown)
                    break;
            }
        }

        return ([.. matches], false);
    }

    // Holdout v5 V5E040 (int11): a destination that repeats the subfolder it is already in («BAXY-bench/copia.txt» in
    // BAXY-bench), when no folder of that name is there, names a path inside it.
    private static string WithoutRepeatedFolder(string root, string subdirectory, string relative)
    {
        string[] own = subdirectory.Split(['/', '\\'], StringSplitOptions.RemoveEmptyEntries);
        string[] given = relative.Split(['/', '\\'], StringSplitOptions.RemoveEmptyEntries);
        for (int count = Math.Min(own.Length, given.Length - 1); count > 0; count--)
        {
            if (own.AsSpan(own.Length - count).SequenceEqual(given.AsSpan(0, count), StringComparer.OrdinalIgnoreCase)
                && !Directory.Exists(Path.Combine(root, string.Join(Path.DirectorySeparatorChar, given, 0, count))))
                return string.Join(Path.DirectorySeparatorChar, given, count, given.Length - count);
        }

        return relative;
    }

    private static bool CrossesReparsePoint(string root, string folder)
    {
        for (string? current = folder; current is not null && current.Length > root.Length;
             current = Path.GetDirectoryName(current))
        {
            if ((File.GetAttributes(current) & FileAttributes.ReparsePoint) != 0)
                return true;
        }

        return false;
    }

    private static string Relative(string root, string path) => Path.GetRelativePath(root, path).Replace('\\', '/');

    // Moved, or copied with the source kept, and read back: the destination holds the source's hash, and the source is
    // gone after a move and still there after a copy.
    private static bool Transfer(string source, string destination, bool copy, string hash)
    {
        if (copy)
            File.Copy(source, destination, overwrite: false);
        else
            File.Move(source, destination);
        return File.Exists(source) == copy && File.Exists(destination)
            && string.Equals(Hash(destination), hash, StringComparison.Ordinal);
    }

    private static ExternalCapabilityReceipt Moved(
        string operation,
        string sourceName,
        string destination,
        string hash,
        bool copy,
        string authority,
        Action<Utf8JsonWriter>? place) =>
        ExternalJson.Success(operation, ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1);
            place?.Invoke(writer);
            writer.WriteString("sourceFileName", sourceName);
            writer.WriteString("destinationRelativePath", destination);
            writer.WriteString("sha256", hash);
            writer.WriteBoolean(copy ? "sourceKept" : "sourceAbsent", true);
            writer.WriteString("authority", copy ? authority.Replace("_absence_", "_kept_") : authority);
            writer.WriteEndObject();
        }), true);

    private ExternalCapabilityReceipt Diff(string operation, JsonElement arguments)
    {
        string left = ResolveUnique(SafeFileName(ExternalJson.RequiredString(arguments, "leftFileName")));
        string right = ResolveUnique(SafeFileName(ExternalJson.RequiredString(arguments, "rightFileName")));
        string[] leftLines = ReadLines(left);
        string[] rightLines = ReadLines(right);
        int maximum = Math.Max(leftLines.Length, rightLines.Length);
        var changes = Enumerable.Range(0, maximum)
            .Where(index => !string.Equals(
                index < leftLines.Length ? leftLines[index] : null,
                index < rightLines.Length ? rightLines[index] : null,
                StringComparison.Ordinal))
            .ToArray();
        int changedLineCount = changes.Length;
        changes = changes.Take(100).ToArray();
        return ExternalJson.Success(operation, ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1);
            writer.WriteString("leftName", Path.GetFileName(left));
            writer.WriteString("rightName", Path.GetFileName(right));
            writer.WriteString("leftSha256", Hash(left)); writer.WriteString("rightSha256", Hash(right));
            // Ronda final 7 (regla 3): the count is of every changed line; the list stops at 100 and says so.
            writer.WriteNumber("changedLineCount", changedLineCount);
            if (changedLineCount > changes.Length) writer.WriteBoolean("changedLinesTruncated", true);
            writer.WriteStartArray("changedLines");
            foreach (int line in changes) writer.WriteNumberValue(line + 1);
            writer.WriteEndArray(); writer.WriteString("authority", "sandbox_named_diff_hash_snapshot");
            writer.WriteEndObject();
        }), effectObserved: false);
    }

    // A file is the one named only when its whole name, case aside, is the name given; two such files anywhere in
    // the work folder are ambiguous and nothing is chosen.
    private string ResolveUnique(string fileName)
    {
        if (!Directory.Exists(_root)) throw new InvalidDataException("sandbox_named_root_not_found");
        string[] matches = Enumerate()
            .Where(path => string.Equals(Path.GetFileName(path), fileName, StringComparison.OrdinalIgnoreCase))
            .Take(2).ToArray();
        if (matches.Length == 0) throw new InvalidDataException("sandbox_named_file_not_found");
        if (matches.Length > 1) throw new InvalidDataException("sandbox_named_file_ambiguous");
        return matches[0];
    }

    private IEnumerable<string> Enumerate()
    {
        var options = new EnumerationOptions
        {
            RecurseSubdirectories = true,
            IgnoreInaccessible = true,
            AttributesToSkip = FileAttributes.ReparsePoint,
            MaxRecursionDepth = 20,
        };
        // The work folder's own private folder (the filesystem provider's .backups) holds no file of the person's.
        string backups = Path.Combine(_root, ".backups") + Path.DirectorySeparatorChar;
        return Directory.EnumerateFiles(_root, "*", options).Where(path =>
            !path.StartsWith(backups, StringComparison.OrdinalIgnoreCase));
    }

    private string ConfinedDestination(string relative)
    {
        if (string.IsNullOrWhiteSpace(relative) || Path.IsPathRooted(relative))
            throw new InvalidDataException("sandbox_move_destination_invalid");
        string root = Path.GetFullPath(_root).TrimEnd(Path.DirectorySeparatorChar);
        string destination = Path.GetFullPath(Path.Combine(root, relative));
        if (!destination.StartsWith(root + Path.DirectorySeparatorChar,
                StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException("sandbox_move_destination_invalid");
        return destination;
    }

    private static string SafeFileName(string value)
    {
        string name = value.Trim();
        if (name != Path.GetFileName(name) || name.IndexOfAny(Path.GetInvalidFileNameChars()) >= 0)
            throw new InvalidDataException("sandbox_named_file_name_invalid");
        return name;
    }

    private static string[] ReadLines(string path)
    {
        var info = new FileInfo(path);
        if (info.Length > 2 * 1024 * 1024)
            throw new InvalidDataException("sandbox_diff_file_too_large");
        return File.ReadAllLines(path, Encoding.UTF8);
    }

    private static string Hash(string path)
    {
        using FileStream stream = File.OpenRead(path);
        return Convert.ToHexStringLower(SHA256.HashData(stream));
    }
}
