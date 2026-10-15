using System.IO.Enumeration;
using System.Security.Cryptography;
using System.Text.Json;
using System.Text;
using Baxy.Providers.Windows.Filesystem;

namespace Baxy.Providers.Windows.External;

internal sealed class WindowsKnownFileAdapter : IExternalOperationAdapter
{
    private readonly string _trashRoot;
    private readonly IReadOnlyDictionary<string, string[]> _configuredRoots;
    private readonly IRecycleBin _recycleBin;

    internal WindowsKnownFileAdapter(string dataRoot)
        : this(dataRoot, DefaultRoots())
    {
    }

    internal WindowsKnownFileAdapter(
        string dataRoot,
        IReadOnlyDictionary<string, string[]> configuredRoots,
        IRecycleBin? recycleBin = null)
    {
        _trashRoot = Path.Combine(Path.GetFullPath(dataRoot), "known-file-trash");
        _configuredRoots = configuredRoots;
        _recycleBin = recycleBin ?? WindowsRecycleBin.Instance;
    }

    public bool CanHandle(string operation) => operation is
        "file.edit" or "file.find" or "file.read"
        or "filesystem.known.duplicates" or "filesystem.known.trash.named" or "filesystem.path.ensure.absent";

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
            bool inSubdirectory = arguments.TryGetProperty("subdirectory", out JsonElement subdirectoryElement);
            if (inSubdirectory)
            {
                string subdirectory = subdirectoryElement.GetString()?.Trim()
                    ?? throw new InvalidDataException("known_subdirectory_invalid");
                roots = SubdirectoryRoots(roots, subdirectory);
            }
            return ValueTask.FromResult(operation switch
            {
                "file.edit" => Edit(operation, roots, arguments, effectBoundary),
                "file.find" => Find(operation, roots, arguments, inSubdirectory, cancellationToken),
                "file.read" => Read(operation, roots, arguments, cancellationToken),
                "filesystem.known.duplicates" => Duplicates(
                    operation, roots, arguments, cancellationToken),
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

    // BAXY Renew agent tools (2026-10-15), file.find: one way to see what a known folder holds. Without query or
    // content it lists the folder's top level (FILES1425 «qué hay en Descargas», FILES1433 «los 5 más recientes»); a
    // query matches names under it (a part of the name, or a pattern with * and ?); content looks inside the text
    // files under it, bounded, and gives the first line where the text appears. Each file comes with its path
    // relative to the known folder, which file.read and file.edit take as its name.
    private const int MaximumContentFiles = 2_000;
    private const long MaximumContentFileBytes = 1_048_576;
    private const int MaximumLineCharacters = 200;

    private ExternalCapabilityReceipt Find(
        string operation,
        (string Label, string Root)[] roots,
        JsonElement arguments,
        bool inSubdirectory,
        CancellationToken cancellationToken)
    {
        string? query = OptionalText(arguments, "query");
        string? content = OptionalText(arguments, "content");
        string order = arguments.TryGetProperty("order", out JsonElement orderElement)
            && orderElement.ValueKind == JsonValueKind.String
            && orderElement.GetString() == "recent" ? "recent" : "name";
        if (!roots.Any(root => Directory.Exists(root.Root)))
            return ExternalJson.Failure(
                operation, inSubdirectory ? "known_subdirectory_not_found" : "known_folder_unavailable");
        if (query is null && content is null) return List(operation, roots, arguments, order);

        int limit = Math.Clamp(ExternalJson.OptionalInt(arguments, "limit", 20), 1, 100);
        List<(string Label, string Root)> searched = [];
        IEnumerable<KnownEntry> named = Enumerate(roots, searched);
        if (query is not null) named = named.Where(item => NameMatches(Path.GetFileName(item.Path), query));
        List<(KnownEntry File, int Line, string LineText)> hits = [];
        int scanned = 0, skippedTooLarge = 0, skippedNotText = 0, skippedUnreadable = 0;
        bool scanLimitReached = false;
        if (content is null)
        {
            hits.AddRange(named.Select(item => (item, 0, "")));
        }
        else
        {
            foreach (KnownEntry item in named)
            {
                cancellationToken.ThrowIfCancellationRequested();
                if (scanned == MaximumContentFiles)
                {
                    scanLimitReached = true;
                    break;
                }
                scanned++;
                switch (FirstLineContaining(item.Path, content, out int line, out string lineText))
                {
                    case ContentScan.Found:
                        hits.Add((item, line, lineText));
                        break;
                    case ContentScan.TooLarge: skippedTooLarge++; break;
                    case ContentScan.NotText: skippedNotText++; break;
                    case ContentScan.Unreadable: skippedUnreadable++; break;
                }
                if (hits.Count == limit) break;
            }
        }
        var files = hits
            .Select(hit => (hit.File, hit.Line, hit.LineText, Info: new FileInfo(hit.File.Path)))
            .ToArray();
        var shown = (order == "recent"
                ? files.OrderByDescending(item => item.Info.LastWriteTimeUtc)
                : files.OrderBy(item => item.File.Label, StringComparer.Ordinal)
                    .ThenBy(item => RelativeToFolder(item.File), StringComparer.OrdinalIgnoreCase))
            .Take(limit)
            .ToArray();
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1);
            writer.WriteString("mode", content is null ? "name" : "content");
            if (query is not null) writer.WriteString("query", query);
            if (content is not null) writer.WriteString("content", content);
            writer.WriteNumber("count", shown.Length);
            // By name every match is known; by content the scan stops at the limit, so only what was found is.
            if (content is null) writer.WriteNumber("matchCount", hits.Count);
            writer.WriteStartArray("files");
            foreach (var file in shown)
            {
                writer.WriteStartObject();
                writer.WriteString("name", Path.GetFileName(file.File.Path));
                writer.WriteString("folder", file.File.Label);
                writer.WriteString("relativePath", RelativeToFolder(file.File));
                writer.WriteNumber("size", file.Info.Length);
                writer.WriteString("modifiedUtc", file.Info.LastWriteTimeUtc);
                if (content is not null)
                {
                    writer.WriteNumber("line", file.Line);
                    writer.WriteString("lineText", file.LineText);
                }
                writer.WriteEndObject();
            }
            writer.WriteEndArray();
            writer.WriteString("order", order);
            writer.WriteStartObject("searchScope");
            writer.WriteStartArray("folders");
            foreach (string label in searched.Select(root => root.Label).Distinct(StringComparer.Ordinal))
                writer.WriteStringValue(label);
            writer.WriteEndArray();
            writer.WriteNumber("maxRecursionDepth", 12);
            writer.WriteBoolean("ignoreInaccessible", true);
            writer.WriteBoolean("skipReparsePoints", true);
            if (content is not null)
            {
                writer.WriteNumber("filesScanned", scanned);
                writer.WriteNumber("maximumFilesScanned", MaximumContentFiles);
                writer.WriteBoolean("scanLimitReached", scanLimitReached);
                writer.WriteNumber("maximumFileBytes", MaximumContentFileBytes);
                writer.WriteNumber("skippedTooLarge", skippedTooLarge);
                writer.WriteNumber("skippedNotText", skippedNotText);
                writer.WriteNumber("skippedUnreadable", skippedUnreadable);
            }
            writer.WriteNumber("resultLimit", limit);
            writer.WriteBoolean("resultsMayBeTruncated",
                content is null ? hits.Count > limit : hits.Count >= limit || scanLimitReached);
            writer.WriteBoolean("exhaustive", false);
            writer.WriteEndObject();
            writer.WriteString("authority", content is null
                ? "windows_known_folders_name_search_postread"
                : "windows_known_folders_text_content_search_postread");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effectObserved: false);
    }

    private ExternalCapabilityReceipt List(
        string operation,
        (string Label, string Root)[] roots,
        JsonElement arguments,
        string order)
    {
        // The top-level entries of the folder, names and kinds only. Hidden and system entries (desktop.ini) are
        // not what the person sees.
        int limit = Math.Clamp(ExternalJson.OptionalInt(arguments, "limit", 50), 1, 100);
        var options = new EnumerationOptions
        {
            RecurseSubdirectories = false,
            IgnoreInaccessible = true,
            AttributesToSkip = FileAttributes.Hidden | FileAttributes.System,
        };
        List<(KnownEntry Entry, bool IsFolder, long Size, DateTime ModifiedUtc)> entries = [];
        foreach ((string label, string root) in roots)
        {
            if (!Directory.Exists(root)) continue;
            foreach (string path in Directory.EnumerateFileSystemEntries(root, "*", options))
            {
                bool isFolder = Directory.Exists(path);
                entries.Add((
                    new KnownEntry(label, root, path),
                    isFolder,
                    isFolder ? 0 : new FileInfo(path).Length,
                    isFolder ? Directory.GetLastWriteTimeUtc(path) : File.GetLastWriteTimeUtc(path)));
            }
        }
        // Newest first when asked; otherwise folders first, then names.
        var shown = (order == "recent"
                ? entries.OrderByDescending(item => item.ModifiedUtc)
                    .ThenBy(item => Path.GetFileName(item.Entry.Path), StringComparer.OrdinalIgnoreCase)
                : entries.OrderBy(item => item.IsFolder ? 0 : 1)
                    .ThenBy(item => Path.GetFileName(item.Entry.Path), StringComparer.OrdinalIgnoreCase))
            .Take(limit)
            .ToArray();
        int folderCount = entries.Count(item => item.IsFolder);
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1);
            writer.WriteString("mode", "list");
            writer.WriteNumber("count", entries.Count);
            writer.WriteNumber("fileCount", entries.Count - folderCount);
            writer.WriteNumber("folderCount", folderCount);
            writer.WriteStartArray("entries");
            foreach (var entry in shown)
            {
                writer.WriteStartObject();
                writer.WriteString("name", Path.GetFileName(entry.Entry.Path));
                writer.WriteString("kind", entry.IsFolder ? "folder" : "file");
                writer.WriteString("folder", entry.Entry.Label);
                writer.WriteString("relativePath", RelativeToFolder(entry.Entry));
                if (!entry.IsFolder) writer.WriteNumber("size", entry.Size);
                writer.WriteString("modifiedUtc", entry.ModifiedUtc);
                writer.WriteEndObject();
            }
            writer.WriteEndArray();
            writer.WriteNumber("shownCount", shown.Length);
            writer.WriteString("order", order);
            writer.WriteNumber("resultLimit", limit);
            writer.WriteBoolean("resultsMayBeTruncated", entries.Count > shown.Length);
            writer.WriteBoolean("hiddenAndSystemSkipped", true);
            writer.WriteString("authority", "windows_known_folder_toplevel_postread");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effectObserved: false);
    }

    private enum ContentScan
    {
        Found,
        Absent,
        TooLarge,
        NotText,
        Unreadable,
    }

    private static ContentScan FirstLineContaining(string path, string content, out int line, out string lineText)
    {
        line = 0;
        lineText = "";
        try
        {
            var info = new FileInfo(path);
            if (info.Length > MaximumContentFileBytes) return ContentScan.TooLarge;
            byte[] head = new byte[(int)Math.Min(info.Length, TextFileEncoding.ProbeBytes)];
            using (FileStream stream = new(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete))
                head = head[..stream.ReadAtLeast(head, head.Length, throwOnEndOfStream: false)];
            if (TextFileEncoding.LooksBinary(head)) return ContentScan.NotText;
            string text = TextFileEncoding.Decode(File.ReadAllBytes(path));
            int index = text.IndexOf(content, StringComparison.OrdinalIgnoreCase);
            if (index < 0) return ContentScan.Absent;
            int start = text.LastIndexOf('\n', Math.Max(0, index - 1)) + 1;
            if (index == 0) start = 0;
            int end = text.IndexOf('\n', index);
            if (end < 0) end = text.Length;
            line = 1 + text.AsSpan(0, start).Count('\n');
            string whole = text[start..end].TrimEnd('\r');
            int column = index - start;
            int from = whole.Length <= MaximumLineCharacters ? 0
                : Math.Clamp(column - MaximumLineCharacters / 4, 0, whole.Length - MaximumLineCharacters);
            lineText = whole.Substring(from, Math.Min(MaximumLineCharacters, whole.Length - from)).Trim();
            return ContentScan.Found;
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            return ContentScan.Unreadable;
        }
    }

    private static bool NameMatches(string name, string query) =>
        query.Contains('*') || query.Contains('?')
            ? FileSystemName.MatchesSimpleExpression(query, name, ignoreCase: true)
            : name.Contains(query, StringComparison.OrdinalIgnoreCase);

    private static string? OptionalText(JsonElement arguments, string name) =>
        arguments.TryGetProperty(name, out JsonElement value) && value.ValueKind == JsonValueKind.String
        && !string.IsNullOrWhiteSpace(value.GetString())
            ? value.GetString()!.Trim()
            : null;

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
        // FILES1603 «Borra la carpeta CarterTest del escritorio»: a directory with
        // that name in a known folder is trashed the same way, whole.
        var matches = Enumerate(roots)
            .Concat(EnumerateDirectories(roots))
            .Where(item => string.Equals(
                Path.GetFileName(item.Path), fileName, StringComparison.OrdinalIgnoreCase))
            .Take(2)
            .ToArray();
        if (matches.Length == 0) return ExternalJson.Failure(operation, "known_file_not_found");
        if (matches.Length > 1) return ExternalJson.Failure(operation, "known_file_ambiguous");
        (string label, _, string source) = matches[0];
        bool isFolder = Directory.Exists(source);
        effectBoundary.Cross();
        Directory.CreateDirectory(_trashRoot);
        string restoreId = "restore_" + Guid.NewGuid().ToString("N");
        string destination = Path.Combine(_trashRoot, restoreId + "_" + fileName);
        if (isFolder) MoveDirectory(source, destination); else File.Move(source, destination);
        bool gone = isFolder ? !Directory.Exists(source) : !File.Exists(source);
        bool arrived = isFolder ? Directory.Exists(destination) : File.Exists(destination);
        if (!gone || !arrived)
            return ExternalJson.Failure(operation, "known_file_trash_postread_failed", true);
        int entries = isFolder
            ? Directory.EnumerateFileSystemEntries(destination, "*", SearchOption.AllDirectories).Count()
            : 0;
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1);
            writer.WriteString("reviewLabel", fileName); writer.WriteString("folder", label);
            writer.WriteString("restoreId", restoreId); writer.WriteBoolean("sourceAbsent", true);
            writer.WriteBoolean("isFolder", isFolder);
            if (isFolder)
            {
                writer.WriteNumber("entries", entries);
                writer.WriteString("sha256", Convert.ToHexStringLower(SHA256.HashData(
                    Encoding.UTF8.GetBytes(string.Join("\n", Directory
                        .EnumerateFileSystemEntries(destination, "*", SearchOption.AllDirectories)
                        .Select(path => Path.GetRelativePath(destination, path))
                        .OrderBy(static path => path, StringComparer.Ordinal))))));
            }
            else
            {
                writer.WriteString("sha256", Convert.ToHexStringLower(
                    SHA256.HashData(File.ReadAllBytes(destination))));
            }
            writer.WriteString("authority", "windows_known_file_private_trash_postread");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effectObserved: true);
    }

    // file.read (BAXY Renew agent tools, 2026-10-15; before, document.text.read REOPEN1957 H0299 and
    // document.pdf.read PDF1689 H0666): the file named once in the known folders, by its name or by its path relative
    // to the folder (ambiguity refused, with the places). A text file is read in its own encoding (BOM honoured); a
    // PDF gives the text it already carries through the mind runtime's pypdf (no OCR, no rendering). A page of the
    // text from offset, with the total length and whether more remains, so the next call can go on reading.
    private const long MaximumTextBytes = 4L * 1024 * 1024;
    private const int DefaultReadCharacters = 4_000;

    private ExternalCapabilityReceipt Read(
        string operation,
        IReadOnlyList<(string Label, string Root)> roots,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        int offset = Math.Max(0, ExternalJson.OptionalInt(arguments, "offset", 0));
        int maximumCharacters = Math.Clamp(
            ExternalJson.OptionalInt(arguments, "maximumCharacters", DefaultReadCharacters), 200, 200_000);
        if (Locate(operation, roots, ExternalJson.RequiredString(arguments, "fileName"), out KnownEntry file)
            is { } refused)
            return refused;
        var info = new FileInfo(file.Path);
        return info.Extension.Equals(".pdf", StringComparison.OrdinalIgnoreCase)
            ? ReadPdf(operation, file, info, offset, maximumCharacters, cancellationToken)
            : ReadText(operation, file, info, offset, maximumCharacters);
    }

    private static ExternalCapabilityReceipt ReadText(
        string operation,
        KnownEntry file,
        FileInfo info,
        int offset,
        int maximumCharacters)
    {
        if (info.Length > MaximumTextBytes) return ExternalJson.Failure(operation, "known_text_too_large");
        byte[] bytes = File.ReadAllBytes(file.Path);
        if (TextFileEncoding.LooksBinary(bytes)) return ExternalJson.Failure(operation, "known_file_not_text");
        string full = TextFileEncoding.Decode(bytes);
        int lineCount = full.Length == 0 ? 0 : full.Split('\n').Length;
        return ExternalJson.Success(operation, ReadResult(
            file, "text", full.Length, offset, Page(full, offset, maximumCharacters),
            writer =>
            {
                writer.WriteNumber("bytes", bytes.Length);
                writer.WriteNumber("lines", lineCount);
            },
            Convert.ToHexStringLower(SHA256.HashData(bytes)), "windows_known_text_file_read"), effectObserved: false);
    }

    private static ExternalCapabilityReceipt ReadPdf(
        string operation,
        KnownEntry file,
        FileInfo info,
        int offset,
        int maximumCharacters,
        CancellationToken cancellationToken)
    {
        if (info.Length > MaximumPdfBytes) return ExternalJson.Failure(operation, "known_pdf_too_large");
        string? python = FindMindPython();
        if (python is null)
            return ExternalJson.Failure(operation, "pdf_text_extractor_unavailable");
        string output;
        using (var process = new System.Diagnostics.Process())
        {
            process.StartInfo = new System.Diagnostics.ProcessStartInfo
            {
                FileName = python,
                UseShellExecute = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                CreateNoWindow = true,
                StandardOutputEncoding = Encoding.UTF8,
                StandardErrorEncoding = Encoding.UTF8,
            };
            process.StartInfo.ArgumentList.Add("-X");
            process.StartInfo.ArgumentList.Add("utf8");
            process.StartInfo.ArgumentList.Add("-I");
            process.StartInfo.ArgumentList.Add("-c");
            process.StartInfo.ArgumentList.Add(PdfTextExtractor);
            process.StartInfo.ArgumentList.Add(info.FullName);
            process.StartInfo.ArgumentList.Add(offset.ToString(System.Globalization.CultureInfo.InvariantCulture));
            process.StartInfo.ArgumentList.Add(maximumCharacters.ToString(
                System.Globalization.CultureInfo.InvariantCulture));
            try
            {
                if (!process.Start())
                    return ExternalJson.Failure(operation, "pdf_text_extractor_unavailable");
                Task<string> stdout = process.StandardOutput.ReadToEndAsync(cancellationToken);
                Task<string> stderr = process.StandardError.ReadToEndAsync(cancellationToken);
                if (!process.WaitForExit(PdfExtractionTimeout))
                {
                    TryKillTree(process);
                    return ExternalJson.Failure(operation, "pdf_text_extraction_timeout");
                }
                output = stdout.GetAwaiter().GetResult();
                _ = stderr.GetAwaiter().GetResult();
                if (process.ExitCode == 3)
                    return ExternalJson.Failure(operation, "pdf_text_extractor_unavailable");
            }
            catch (Exception exception) when (exception is System.ComponentModel.Win32Exception
                or InvalidOperationException)
            {
                return ExternalJson.Failure(operation, "pdf_text_extractor_unavailable");
            }
        }
        if (output.Length > MaximumExtractorOutput)
            return ExternalJson.Failure(operation, "pdf_text_extraction_overflow");
        using JsonDocument? document = ParseExtractorOutput(output);
        if (document is null) return ExternalJson.Failure(operation, "known_pdf_unreadable");
        JsonElement root = document.RootElement;
        if (root.TryGetProperty("error", out JsonElement error))
        {
            return ExternalJson.Failure(operation, error.GetString() switch
            {
                "pdf_encrypted" => "known_pdf_encrypted",
                "pypdf_missing" => "pdf_text_extractor_unavailable",
                _ => "known_pdf_unreadable",
            });
        }
        string text = root.TryGetProperty("text", out JsonElement textElement)
            && textElement.ValueKind == JsonValueKind.String
            ? textElement.GetString() ?? "" : "";
        int characters = IntOf(root, "characters");
        int pages = IntOf(root, "pages");
        int textPages = IntOf(root, "textPages");
        return ExternalJson.Success(operation, ReadResult(
            file, "pdf", characters, offset, text,
            writer =>
            {
                writer.WriteNumber("pages", pages);
                writer.WriteNumber("textPages", textPages);
                writer.WriteBoolean("hasText", characters > 0);
            },
            Hash(info.FullName), "windows_known_pdf_pypdf_text_extraction"), effectObserved: false);
    }

    // What a read says before the text itself, so a cut observation still shows how much there is and where to go on.
    private static JsonElement ReadResult(
        KnownEntry file,
        string kind,
        int characters,
        int offset,
        string text,
        Action<Utf8JsonWriter> kindFacts,
        string fileSha256,
        string authority) => ExternalJson.Create(writer =>
    {
        bool hasMore = offset + text.Length < characters;
        writer.WriteStartObject(); writer.WriteNumber("version", 1);
        writer.WriteString("kind", kind);
        writer.WriteString("reviewLabel", Path.GetFileName(file.Path));
        writer.WriteString("folder", file.Label);
        writer.WriteNumber("characters", characters);
        writer.WriteNumber("offset", offset);
        writer.WriteNumber("returnedCharacters", text.Length);
        writer.WriteBoolean("hasMore", hasMore);
        if (hasMore) writer.WriteNumber("nextOffset", offset + text.Length);
        kindFacts(writer);
        writer.WriteString("fileSha256", fileSha256);
        writer.WriteString("text", text);
        writer.WriteString("authority", authority);
        writer.WriteEndObject();
    });

    private static string Page(string full, int offset, int maximumCharacters)
    {
        if (offset >= full.Length) return "";
        int length = Math.Min(maximumCharacters, full.Length - offset);
        // A page never ends between the two halves of a character.
        if (length < full.Length - offset && char.IsHighSurrogate(full[offset + length - 1])) length--;
        return full.Substring(offset, length);
    }

    // file.edit (BAXY Renew agent tools, 2026-10-15): an exact replacement in a text file of a known folder. The text
    // to replace must appear exactly once unless every occurrence is asked; otherwise nothing changes and the count is
    // said. The file keeps its encoding and BOM; its previous version goes to the Recycle Bin before the edited one
    // takes its place (recoverable, so no confirmation), and the result is read back.
    private ExternalCapabilityReceipt Edit(
        string operation,
        IReadOnlyList<(string Label, string Root)> roots,
        JsonElement arguments,
        ExternalEffectBoundary effectBoundary)
    {
        string oldText = arguments.TryGetProperty("oldText", out JsonElement oldElement)
            ? oldElement.GetString() ?? "" : "";
        string newText = arguments.TryGetProperty("newText", out JsonElement newElement)
            ? newElement.GetString() ?? "" : "";
        bool replaceAll = arguments.TryGetProperty("replaceAll", out JsonElement all)
            && all.ValueKind == JsonValueKind.True;
        if (oldText.Length == 0) return ExternalJson.Failure(operation, "known_edit_old_text_empty");
        if (string.Equals(oldText, newText, StringComparison.Ordinal))
            return ExternalJson.Failure(operation, "known_edit_text_unchanged");
        if (Locate(operation, roots, ExternalJson.RequiredString(arguments, "fileName"), out KnownEntry file)
            is { } refused)
            return refused;
        if (new FileInfo(file.Path).Length > MaximumTextBytes)
            return ExternalJson.Failure(operation, "known_text_too_large");
        byte[] before = File.ReadAllBytes(file.Path);
        if (TextFileEncoding.LooksBinary(before)) return ExternalJson.Failure(operation, "known_file_not_text");
        string? text = TextFileEncoding.DecodeExactly(before);
        if (text is null) return ExternalJson.Failure(operation, "known_text_encoding_unsupported");
        int occurrences = Occurrences(text, oldText);
        if (occurrences == 0 || (occurrences > 1 && !replaceAll))
        {
            return new ExternalCapabilityReceipt(operation, false, false, ExternalJson.Create(writer =>
            {
                writer.WriteStartObject(); writer.WriteNumber("version", 1);
                writer.WriteString("reviewLabel", Path.GetFileName(file.Path));
                writer.WriteString("folder", file.Label);
                writer.WriteNumber("occurrences", occurrences);
                writer.WriteBoolean("changed", false);
                writer.WriteEndObject();
            }), occurrences == 0 ? "known_edit_text_not_found" : "known_edit_text_not_unique");
        }
        int index = text.IndexOf(oldText, StringComparison.Ordinal);
        string edited = replaceAll
            ? text.Replace(oldText, newText, StringComparison.Ordinal)
            : string.Concat(text.AsSpan(0, index), newText, text.AsSpan(index + oldText.Length));
        byte[] after = TextFileEncoding.EncodeLike(before, edited);
        string previousSha256 = Convert.ToHexStringLower(SHA256.HashData(before));
        string expectedSha256 = Convert.ToHexStringLower(SHA256.HashData(after));
        string temporary = Path.Combine(
            Path.GetDirectoryName(file.Path)!, ".baxy-edit-" + Guid.NewGuid().ToString("N") + ".tmp");
        try
        {
            using (var stream = new FileStream(
                temporary, FileMode.CreateNew, FileAccess.Write, FileShare.None, 4096, FileOptions.WriteThrough))
            {
                stream.Write(after);
                stream.Flush(flushToDisk: true);
            }
            if (!string.Equals(Hash(file.Path), previousSha256, StringComparison.Ordinal))
                return ExternalJson.Failure(operation, "known_file_changed");
            effectBoundary.Cross();
            // When the bin cannot take the previous version it stays where it was, unchanged.
            if (!_recycleBin.Recycle(file.Path))
                return ExternalJson.Failure(operation, "previous_version_not_recycled");
            File.Move(temporary, file.Path);
        }
        finally
        {
            if (File.Exists(temporary)) File.Delete(temporary);
        }
        byte[] observed = File.ReadAllBytes(file.Path);
        string observedSha256 = Convert.ToHexStringLower(SHA256.HashData(observed));
        if (!string.Equals(observedSha256, expectedSha256, StringComparison.Ordinal))
            return ExternalJson.Failure(operation, "known_edit_postread_failed", effectObserved: true);
        string observedText = TextFileEncoding.Decode(observed);
        return ExternalJson.Success(operation, ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1);
            writer.WriteString("reviewLabel", Path.GetFileName(file.Path));
            writer.WriteString("folder", file.Label);
            writer.WriteNumber("replacements", replaceAll ? occurrences : 1);
            writer.WriteNumber("oldTextOccurrencesNow", Occurrences(observedText, oldText));
            writer.WriteNumber("newTextOccurrences", newText.Length == 0 ? 0 : Occurrences(observedText, newText));
            writer.WriteNumber("characters", observedText.Length);
            writer.WriteString("previousSha256", previousSha256);
            writer.WriteString("sha256", observedSha256);
            writer.WriteBoolean("previousVersionRecycled", true);
            writer.WriteString("authority", "windows_known_text_edit_recycle_postread");
            writer.WriteEndObject();
        }), effectObserved: true);
    }

    private static int Occurrences(string text, string value)
    {
        int count = 0;
        for (int index = text.IndexOf(value, StringComparison.Ordinal); index >= 0;
             index = text.IndexOf(value, index + value.Length, StringComparison.Ordinal))
            count++;
        return count;
    }

    // file.read and file.edit name one file: by its name, found once anywhere under the folder, or by its path
    // relative to the known folder (as file.find gives it, without a subdirectory). Two or more are refused with
    // their places; none, with the files whose name without its extension is the one asked, so the next call can name
    // the right one.
    private ExternalCapabilityReceipt? Locate(
        string operation,
        IReadOnlyList<(string Label, string Root)> roots,
        string requested,
        out KnownEntry located)
    {
        located = default;
        string name = requested.Trim().Replace(Path.AltDirectorySeparatorChar, Path.DirectorySeparatorChar);
        string[] parts = name.Split(Path.DirectorySeparatorChar);
        if (name.Length == 0 || Path.IsPathRooted(name) || name.Contains('*') || name.Contains('?')
            || parts.Any(part => part is "" or "." or ".." || part.IndexOfAny(Path.GetInvalidFileNameChars()) >= 0))
            return ExternalJson.Failure(operation, "known_file_name_invalid");
        List<KnownEntry> matches = [];
        if (parts.Length > 1)
        {
            foreach ((string label, string root) in roots)
            {
                string path = Path.GetFullPath(Path.Combine(root, name));
                if (File.Exists(path) && !CrossesReparsePoint(root, path)) matches.Add(new KnownEntry(label, root, path));
            }
        }
        else
        {
            matches.AddRange(Enumerate(roots)
                .Where(item => string.Equals(Path.GetFileName(item.Path), name, StringComparison.OrdinalIgnoreCase))
                .Take(5));
        }
        if (matches.Count == 1)
        {
            located = matches[0];
            return null;
        }
        string stem = parts[^1];
        KnownEntry[] candidates = matches.Count > 1
            ? [.. matches]
            : [.. Enumerate(roots)
                .Where(item => string.Equals(
                    Path.GetFileNameWithoutExtension(item.Path), stem, StringComparison.OrdinalIgnoreCase))
                .Take(5)];
        string code = matches.Count > 1 ? "known_file_ambiguous" : "known_file_not_found";
        if (candidates.Length == 0) return ExternalJson.Failure(operation, code);
        return new ExternalCapabilityReceipt(operation, false, false, ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1);
            writer.WriteStartArray("candidates");
            foreach (KnownEntry candidate in candidates)
            {
                writer.WriteStartObject();
                writer.WriteString("name", Path.GetFileName(candidate.Path));
                writer.WriteString("folder", candidate.Label);
                writer.WriteString("relativePath", RelativeToFolder(candidate));
                writer.WriteEndObject();
            }
            writer.WriteEndArray();
            writer.WriteEndObject();
        }), code);
    }

    private static bool CrossesReparsePoint(string root, string path)
    {
        string current = Path.GetFullPath(root);
        foreach (string part in Path.GetRelativePath(current, path).Split(Path.DirectorySeparatorChar))
        {
            current = Path.Combine(current, part);
            if ((File.GetAttributes(current) & FileAttributes.ReparsePoint) != 0) return true;
        }
        return false;
    }

    // The path of a file relative to the known folder it is in (never the absolute path), whatever subdirectory the
    // search started from.
    private string RelativeToFolder(KnownEntry entry)
    {
        if (_configuredRoots.TryGetValue(entry.Label, out string[]? folderRoots))
        {
            foreach (string folderRoot in folderRoots)
            {
                string root = Path.GetFullPath(folderRoot).TrimEnd(Path.DirectorySeparatorChar);
                if (entry.Path.StartsWith(root + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
                    return Path.GetRelativePath(root, entry.Path);
            }
        }
        return Path.GetRelativePath(entry.Root, entry.Path);
    }

    // The extractor, run as «python -X utf8 -I -c … <file> <offset> <maximumCharacters>» in the registered mind
    // runtime (the venv that carries pypdf): the text the PDF already carries, page by page, its total length and the
    // page of it from offset; no OCR, no rendering.
    private const string PdfTextExtractor = """
import json
import sys


def main() -> int:
    path = sys.argv[1]
    offset = max(0, int(sys.argv[2]))
    maximum = max(200, min(int(sys.argv[3]), 200_000))
    try:
        from pypdf import PdfReader
    except ImportError:
        print(json.dumps({"error": "pypdf_missing"}))
        return 3
    try:
        reader = PdfReader(path, strict=False)
        encrypted = bool(reader.is_encrypted)
        if encrypted:
            # A PDF with an empty user password opens; anything else is unreadable here.
            try:
                if reader.decrypt("") == 0:
                    print(json.dumps({"error": "pdf_encrypted", "encrypted": True}))
                    return 2
            except Exception:  # noqa: BLE001 - any decrypt failure is the same fact
                print(json.dumps({"error": "pdf_encrypted", "encrypted": True}))
                return 2
        pages = len(reader.pages)
        chunks = []
        for page in reader.pages:
            try:
                text = page.extract_text() or ""
            except Exception:  # noqa: BLE001 - one damaged page does not void the rest
                text = ""
            # Lone surrogates and control bytes from damaged fonts never reach the JSON.
            text = text.encode("utf-8", "replace").decode("utf-8", "replace")
            text = "".join(ch for ch in text if ch in "\n\t" or ord(ch) >= 32)
            text = "\n".join(line.rstrip() for line in text.splitlines()).strip()
            if text:
                chunks.append(text)
        full = "\n\n".join(chunks)
        print(json.dumps({
            "pages": pages,
            "textPages": len(chunks),
            "characters": len(full),
            "encrypted": encrypted,
            "text": full[offset:offset + maximum],
        }, ensure_ascii=False))
        return 0
    except Exception as exception:  # noqa: BLE001 - the provider reports the class, never a trace
        print(json.dumps({"error": "pdf_unreadable", "detail": type(exception).__name__}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
""";

    private const long MaximumPdfBytes = 64L * 1024 * 1024;
    private const int MaximumExtractorOutput = 1_048_576;
    private static readonly TimeSpan PdfExtractionTimeout = TimeSpan.FromSeconds(90);

    private static void TryKillTree(System.Diagnostics.Process process)
    {
        try
        {
            if (!process.HasExited)
            {
                process.Kill(entireProcessTree: true);
            }
        }
        catch (InvalidOperationException)
        {
        }
    }

    private static JsonDocument? ParseExtractorOutput(string output)
    {
        try
        {
            return JsonDocument.Parse(output.Trim());
        }
        catch (JsonException)
        {
            return null;
        }
    }

    private static int IntOf(JsonElement root, string name) =>
        root.TryGetProperty(name, out JsonElement value)
        && value.ValueKind == JsonValueKind.Number
        && value.TryGetInt32(out int number) ? number : 0;

    // The extractor runs in the registered mind runtime (the venv that carries
    // pypdf): BAXY_MIND_PYTHON, then the registration file, then the
    // conventional path under the local application data folder.
    internal static string? FindMindPython()
    {
        string? configured = Environment.GetEnvironmentVariable("BAXY_MIND_PYTHON");
        string localData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        string? registered = null;
        if (!string.IsNullOrWhiteSpace(localData))
        {
            string registration = Path.Combine(localData, "BAXYRuntime", "mind-runtime-v1.json");
            try
            {
                if (File.Exists(registration))
                {
                    using JsonDocument document = JsonDocument.Parse(File.ReadAllBytes(registration));
                    if (document.RootElement.ValueKind == JsonValueKind.Object
                        && document.RootElement.TryGetProperty("python", out JsonElement python)
                        && python.ValueKind == JsonValueKind.String)
                        registered = python.GetString();
                }
            }
            catch (Exception exception) when (exception is IOException
                or UnauthorizedAccessException or JsonException)
            {
                registered = null;
            }
        }
        string?[] candidates =
        [
            configured,
            registered,
            string.IsNullOrWhiteSpace(localData)
                ? null
                : Path.Combine(localData, "BAXYRuntime", "python", "mind-runtime-v1", "Scripts", "python.exe"),
        ];
        foreach (string? candidate in candidates)
        {
            if (string.IsNullOrWhiteSpace(candidate) || !Path.IsPathFullyQualified(candidate))
                continue;
            var file = new FileInfo(Path.GetFullPath(candidate));
            if (file.Exists && file.LinkTarget is null && file.Length > 0)
                return file.FullName;
        }
        return null;
    }

    // FILES1603: Directory.Move refuses another volume (the redirected Desktop
    // lives on D:, the private trash under the profile on C:); copy the tree
    // and remove the source only once every entry arrived.
    private static void MoveDirectory(string source, string destination)
    {
        if (string.Equals(Path.GetPathRoot(source), Path.GetPathRoot(destination),
                StringComparison.OrdinalIgnoreCase))
        {
            Directory.Move(source, destination);
            return;
        }
        var options = new EnumerationOptions
        {
            RecurseSubdirectories = true,
            IgnoreInaccessible = false,
            AttributesToSkip = FileAttributes.ReparsePoint,
            MaxRecursionDepth = 12,
        };
        Directory.CreateDirectory(destination);
        foreach (string directory in Directory.EnumerateDirectories(source, "*", options))
            Directory.CreateDirectory(Path.Combine(destination, Path.GetRelativePath(source, directory)));
        foreach (string file in Directory.EnumerateFiles(source, "*", options))
            File.Copy(file, Path.Combine(destination, Path.GetRelativePath(source, file)), overwrite: false);
        int expected = Directory.EnumerateFileSystemEntries(source, "*", options).Count();
        int arrived = Directory.EnumerateFileSystemEntries(destination, "*", options).Count();
        if (arrived < expected)
            throw new IOException("The folder did not arrive whole in the private trash.");
        Directory.Delete(source, recursive: true);
    }

    private static IEnumerable<KnownEntry> EnumerateDirectories(
        IReadOnlyList<(string Label, string Root)> roots)
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
            foreach (string directory in Directory.EnumerateDirectories(root, "*", options))
                yield return new KnownEntry(label, root, directory);
        }
    }

    private static IEnumerable<KnownEntry> Enumerate(
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
                yield return new KnownEntry(label, root, file);
        }
    }

    private (string Label, string Root)[] Roots(string folder)
    {
        // «all_known» is the three known folders; the profile root (home) holds them and AppData, so it is only read
        // when it is named.
        if (folder == "all_known")
            return _configuredRoots.Where(pair => pair.Key != "home").SelectMany(pair => pair.Value.Select(root =>
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
        ["home"] = [Environment.GetFolderPath(Environment.SpecialFolder.UserProfile)],
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

    /// <summary>A file (or folder) under a known folder: its folder's label, the root it was found from, its path.</summary>
    private readonly record struct KnownEntry(string Label, string Root, string Path);
}
