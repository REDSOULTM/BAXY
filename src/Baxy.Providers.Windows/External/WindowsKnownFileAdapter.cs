using System.Globalization;
using System.IO.Enumeration;
using System.Security.Cryptography;
using System.Text.Json;
using System.Text;
using Baxy.Providers.Windows.Filesystem;
using Baxy.Providers.Windows.Infrastructure;

namespace Baxy.Providers.Windows.External;

internal sealed class WindowsKnownFileAdapter : IExternalOperationAdapter
{
    private readonly IReadOnlyDictionary<string, string[]> _configuredRoots;
    private readonly IRecycleBin _recycleBin;

    internal WindowsKnownFileAdapter()
        : this(DefaultRoots())
    {
    }

    internal WindowsKnownFileAdapter(
        IReadOnlyDictionary<string, string[]> configuredRoots,
        IRecycleBin? recycleBin = null,
        IReadOnlyList<string>? privateRoots = null,
        Func<DateTime>? utcNow = null,
        IReadOnlyList<string>? autostartRoots = null)
    {
        _configuredRoots = configuredRoots;
        _recycleBin = recycleBin ?? WindowsRecycleBin.Instance;
        _privateRoots = privateRoots ?? BaxyPrivateArea.DefaultRoots();
        _utcNow = utcNow ?? (() => DateTime.UtcNow);
        _autostartRoots = autostartRoots ?? AutostartArea.DefaultRoots();
    }

    // The folders Windows runs at sign-in (AutostartArea): never edited.
    private readonly IReadOnlyList<string> _autostartRoots;

    // The clock a walk's time limit is measured with (a test stops a walk where it wants).
    private readonly Func<DateTime> _utcNow;

    // BAXY's own state (BaxyPrivateArea): never read, edited, found or trashed as one of the person's files.
    private readonly IReadOnlyList<string> _privateRoots;

    public bool CanHandle(string operation) => operation is
        "file.edit" or "file.find" or "file.read"
        or "filesystem.known.duplicates" or "filesystem.known.trash.named";

    public ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        var effectBoundary = new ExternalEffectBoundary();
        try
        {
            string folder = ExternalJson.RequiredString(arguments, "folder");
            (string Label, string Root)[] roots = Roots(folder);
            bool inSubdirectory = arguments.TryGetProperty("subdirectory", out JsonElement subdirectoryElement);
            if (inSubdirectory)
            {
                string subdirectory = subdirectoryElement.GetString()?.Trim()
                    ?? throw new InvalidDataException("known_subdirectory_invalid");
                roots = SubdirectoryRoots(roots, subdirectory, _privateRoots);
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
            // FT/proveedores goal (review of receipts): a file another program holds open (a sharing or lock
            // violation, 32 or 33) is that file in use, not its folder unavailable («no puedo acceder a Documentos»).
            bool inUse = exception is IOException && (exception.HResult & 0xFFFF) is 32 or 33;
            return ValueTask.FromResult(effectBoundary.Failure(
                operation, inUse ? "file_in_use" : "known_folder_filesystem_unavailable"));
        }
    }

    private ExternalCapabilityReceipt Duplicates(
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
            .Take(10_001)
            .ToArray();
        // Ronda final 7 (regla 3): past 10 000 candidates the rest is not hashed, so the groups are not all of them.
        bool candidatesCapped = candidates.Length > 10_000;
        if (candidatesCapped)
            candidates = candidates[..10_000];
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
        var found = hashed
            .GroupBy(item => (item.Length, item.Sha256))
            .Where(group => group.Count() > 1)
            .ToArray();
        var groups = found
            .OrderByDescending(group => group.Key.Length)
            .ThenBy(group => group.Key.Sha256, StringComparer.Ordinal)
            .Take(limit)
            .Select(group => group.OrderBy(item => Path.GetFileName(item.Path),
                    StringComparer.OrdinalIgnoreCase).ToArray())
            .ToArray();
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1);
            writer.WriteNumber("groupCount", groups.Length);
            // Ronda final 7 (regla 3): how many were found, and whether the listing or the search was cut.
            writer.WriteNumber("groupsFound", found.Length);
            if (found.Length > groups.Length) writer.WriteBoolean("truncated", true);
            if (candidatesCapped) writer.WriteBoolean("candidatesCapped", true);
            WriteWalkScope(writer);
            writer.WriteStartArray("groups");
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
            && orderElement.GetString() is "recent" or "size" ? orderElement.GetString()! : "name";
        if (!roots.Any(root => Directory.Exists(root.Root)))
            return ExternalJson.Failure(
                operation, inSubdirectory ? "known_subdirectory_not_found" : "known_folder_unavailable");
        if (query is null && content is null) return List(operation, roots, arguments, order);

        int limit = Math.Clamp(ExternalJson.OptionalInt(arguments, "limit", 20), 1, 100);
        List<(string Label, string Root)> searched = [];
        var walk = new WalkBudget(_utcNow, WalkTimeLimit);
        IEnumerable<KnownEntry> named = Enumerate(roots, searched, walk);
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
        var shown = (order switch
                {
                    "recent" => files.OrderByDescending(item => item.Info.LastWriteTimeUtc),
                    "size" => files.OrderByDescending(item => item.Info.Length),
                    _ => files.OrderBy(item => item.File.Label, StringComparer.Ordinal)
                        .ThenBy(item => RelativeToFolder(item.File), StringComparer.OrdinalIgnoreCase),
                })
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
            foreach (string place in PlacesLooked(searched))
                writer.WriteStringValue(place);
            writer.WriteEndArray();
            writer.WriteNumber("maxRecursionDepth", 12);
            writer.WriteNumber("timeLimitSeconds", WalkTimeLimit.TotalSeconds);
            writer.WriteBoolean("timeLimitReached", walk.Reached);
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
                walk.Reached || (content is null ? hits.Count > limit : hits.Count >= limit || scanLimitReached));
            writer.WriteBoolean("exhaustive", false);
            writer.WriteEndObject();
            // Holdout v4 (falsedad, a partial read told as a whole one): a search that did not look at everything under
            // its folders (the walk's time limit, the scan's file limit, the limit of hits it stops at, files it could not
            // read as text) says so at its top, so a «no está» is told only of what was read.
            bool skippedFiles = skippedTooLarge + skippedNotText + skippedUnreadable > 0;
            if (walk.Reached || (content is not null && (scanLimitReached || hits.Count >= limit || skippedFiles)))
                writer.WriteBoolean("readInPart", true);
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
        int hiddenOrSystem = 0;
        foreach ((string label, string root) in roots)
        {
            if (!Directory.Exists(root)) continue;
            hiddenOrSystem += HiddenOrSystemEntries(root);
            foreach (string path in Directory.EnumerateFileSystemEntries(root, "*", options))
            {
                if (BaxyPrivateArea.Holds(_privateRoots, path)) continue;
                bool isFolder = Directory.Exists(path);
                entries.Add((
                    new KnownEntry(label, root, path),
                    isFolder,
                    isFolder ? 0 : new FileInfo(path).Length,
                    isFolder ? Directory.GetLastWriteTimeUtc(path) : File.GetLastWriteTimeUtc(path)));
            }
        }
        // Newest first, or largest file first (folders after the files), when asked; otherwise folders first, then
        // names.
        var shown = (order switch
                {
                    "recent" => entries.OrderByDescending(item => item.ModifiedUtc)
                        .ThenBy(item => Path.GetFileName(item.Entry.Path), StringComparer.OrdinalIgnoreCase),
                    "size" => entries.OrderBy(item => item.IsFolder ? 1 : 0)
                        .ThenByDescending(item => item.Size)
                        .ThenBy(item => Path.GetFileName(item.Entry.Path), StringComparer.OrdinalIgnoreCase),
                    _ => entries.OrderBy(item => item.IsFolder ? 0 : 1)
                        .ThenBy(item => Path.GetFileName(item.Entry.Path), StringComparer.OrdinalIgnoreCase),
                })
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
            // Renew al máximo (w6, rutas): which folder was listed, and that its subfolders were not walked.
            writer.WriteStartArray("listed");
            foreach (string place in PlacesLooked(roots))
                writer.WriteStringValue(place);
            writer.WriteEndArray();
            writer.WriteBoolean("topLevelOnly", true);
            writer.WriteString("order", order);
            writer.WriteNumber("resultLimit", limit);
            writer.WriteBoolean("resultsMayBeTruncated", entries.Count > shown.Length);
            writer.WriteBoolean("hiddenAndSystemSkipped", true);
            // Holdout v4 (falsedad: «Sí, porque no había .bak» with three .bak files present): a listing is of the top
            // level only; what it did not look at is said beside what it listed, so a «no hay» is told only of that: the
            // folders it lists were not opened, the hidden and system entries were left out, and the entries past
            // those listed here are not in it (readInPart when any of these is so).
            writer.WriteString("depth", "top_level");
            writer.WriteNumber("subfoldersNotOpened", folderCount);
            writer.WriteNumber("hiddenOrSystemSkipped", hiddenOrSystem);
            if (entries.Count > shown.Length) writer.WriteNumber("entriesNotListed", entries.Count - shown.Length);
            if (folderCount > 0 || hiddenOrSystem > 0 || entries.Count > shown.Length)
                writer.WriteBoolean("readInPart", true);
            writer.WriteString("authority", "windows_known_folder_toplevel_postread");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effectObserved: false);
    }

    // The hidden and system entries directly in a folder, which a listing of it leaves out (desktop.ini among them).
    internal static int HiddenOrSystemEntries(string folder)
    {
        var options = new EnumerationOptions
        {
            RecurseSubdirectories = false,
            IgnoreInaccessible = true,
            AttributesToSkip = 0,
        };
        try
        {
            return new DirectoryInfo(folder).EnumerateFileSystemInfos("*", options)
                .Count(entry => (entry.Attributes & (FileAttributes.Hidden | FileAttributes.System)) != 0);
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            return 0;
        }
    }

    private enum ContentScan
    {
        Found,
        Absent,
        TooLarge,
        NotText,
        Unreadable,
    }

    // Renew al máximo (w8): a log its program still writes is open for writing, and File.ReadAllBytes (FileShare.Read)
    // could not open it: file.read said file_in_use and a search by content skipped it as unreadable. A read shares
    // writing and deletion, as Notepad does, and takes the bytes the file had when it was opened.
    internal static byte[] ReadShared(string path)
    {
        using FileStream stream = new(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete);
        byte[] bytes = new byte[checked((int)stream.Length)];
        return bytes[..stream.ReadAtLeast(bytes, bytes.Length, throwOnEndOfStream: false)];
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
            string text = TextFileEncoding.Decode(ReadShared(path));
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

    // Al máximo, flujos: the name looked up before the person is asked; a name that names no one target fails here.
    public ValueTask<ExternalCapabilityReceipt?> PreflightAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        if (operation != "filesystem.known.trash.named")
            return ValueTask.FromResult<ExternalCapabilityReceipt?>(null);
        try
        {
            (string Label, string Root)[] roots = Roots(ExternalJson.RequiredString(arguments, "folder"));
            if (arguments.TryGetProperty("subdirectory", out JsonElement subdirectory))
                roots = SubdirectoryRoots(roots, subdirectory.GetString()?.Trim()
                    ?? throw new InvalidDataException("known_subdirectory_invalid"), _privateRoots);
            return ValueTask.FromResult(TrashTarget(operation, roots, arguments, out _));
        }
        catch (Exception exception) when (exception is InvalidDataException or IOException
            or UnauthorizedAccessException or System.Security.SecurityException)
        {
            return ValueTask.FromResult<ExternalCapabilityReceipt?>(null);
        }
    }

    private ExternalCapabilityReceipt Trash(
        string operation,
        IReadOnlyList<(string Label, string Root)> roots,
        JsonElement arguments,
        ExternalEffectBoundary effectBoundary)
    {
        if (TrashTarget(operation, roots, arguments, out KnownEntry target) is { } refused)
            return refused;
        string fileName = ExternalJson.RequiredString(arguments, "fileName").Trim();
        (string label, _, string source) = target;
        bool isFolder = Directory.Exists(source);
        int entries = isFolder
            ? Directory.EnumerateFileSystemEntries(source, "*", SearchOption.AllDirectories).Count()
            : 0;
        // To the Windows Recycle Bin, where the person restores it (BAXY Renew audit 2026-10-15: it went to a private
        // trash that nothing restored from). When the bin cannot take it, it stays where it was.
        effectBoundary.Cross();
        if (!_recycleBin.Recycle(source))
            return ExternalJson.Failure(operation, "known_file_not_recycled");
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1);
            writer.WriteString("reviewLabel", fileName); writer.WriteString("folder", label);
            writer.WriteBoolean("sourceAbsent", true);
            writer.WriteBoolean("inRecycleBin", true);
            writer.WriteBoolean("isFolder", isFolder);
            if (isFolder)
                writer.WriteNumber("entries", entries);
            writer.WriteString("authority", "windows_recycle_bin_postread");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effectObserved: true);
    }

    // The one file or folder of that name in the known folders, or the refusal: an invalid name, none (with the folders
    // walked) or several (with their places).
    private ExternalCapabilityReceipt? TrashTarget(
        string operation,
        IReadOnlyList<(string Label, string Root)> roots,
        JsonElement arguments,
        out KnownEntry target)
    {
        target = default;
        string fileName = ExternalJson.RequiredString(arguments, "fileName").Trim();
        if (fileName != Path.GetFileName(fileName)
            || fileName.IndexOfAny(Path.GetInvalidFileNameChars()) >= 0
            || fileName.Contains('*') || fileName.Contains('?'))
            return ExternalJson.Failure(operation, "known_file_name_invalid");
        // FILES1603 «Borra la carpeta CarterTest del escritorio»: a directory with
        // that name in a known folder is trashed the same way, whole.
        string? folded = ModelAids.On(ModelAids.NearNames) && FoldedName(fileName) is { Length: > 0 } words ? words : null;
        List<KnownEntry> found = [], near = [];
        foreach (KnownEntry item in Enumerate(roots).Concat(EnumerateDirectories(roots)))
        {
            string name = Path.GetFileName(item.Path);
            if (string.Equals(name, fileName, StringComparison.OrdinalIgnoreCase))
            {
                found.Add(item);
                if (found.Count > CandidatesShown) break;
            }
            // Holdout v5 (V5E052): the names alike are only said when the name itself is nowhere, from the same walk.
            else if (folded is not null && found.Count == 0 && near.Count <= CandidatesShown
                && FoldedName(name) == folded)
                near.Add(item);
        }
        KnownEntry[] matches = [.. found];
        if (matches.Length == 0 && near.Count > 0)
            return CandidatesRefusal(operation, "known_file_not_found", near,
                next: NearNamesNext("no file or folder", fileName, near, "case or accents", walkStopped: false));
        // BAXY Renew (notebook): none says the known folders it walked; two or more, their places as file.read
        // gives them, so the next call can name the right one.
        if (matches.Length == 0)
        {
            string[] searched = PlacesLooked(roots);
            string? missing = searched.Length == 0 ? MissingSubdirectoryNext(roots, fileName) : null;
            return new ExternalCapabilityReceipt(operation, false, false, ExternalJson.Create(writer =>
            {
                writer.WriteStartObject(); writer.WriteNumber("version", 1);
                writer.WriteStartArray("searchedFolders");
                foreach (string label in searched)
                    writer.WriteStringValue(label);
                writer.WriteEndArray();
                WriteWalkScope(writer);
                // Renew al máximo (E027): «all_known» walked desktop, documents and downloads, the file was in a folder
                // of home, and the answer was «no lo encontré en ninguna carpeta de tu PC». Said where it was not.
                if (missing is not null)
                    writer.WriteString("next", missing);
                else if (ModelAids.On(ModelAids.SearchScope))
                    writer.WriteString("next", NotFoundScope(fileName, searched));
                writer.WriteEndObject();
            }), "known_file_not_found");
        }
        if (matches.Length > 1) return CandidatesRefusal(operation, "known_file_ambiguous", matches);
        // Renew al máximo (auditoría de flujos): a folder that holds BAXY's own area would take it to the bin with it.
        if (Directory.Exists(matches[0].Path)
            && _privateRoots.Any(root => BaxyPrivateArea.Holds([matches[0].Path], root)))
            return ExternalJson.Failure(operation, "path_reserved");
        target = matches[0];
        return null;
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
        if (Locate(operation, roots, ExternalJson.RequiredString(arguments, "fileName"), out KnownEntry file,
                out bool walkStopped)
            is { } refused)
            return refused;
        var info = new FileInfo(file.Path);
        Action<Utf8JsonWriter> seen = StoppedWalkFacts(file, walkStopped);
        return info.Extension.Equals(".pdf", StringComparison.OrdinalIgnoreCase)
            ? ReadPdf(operation, file, info, offset, maximumCharacters, seen, cancellationToken)
            : ReadText(operation, file, info, offset, maximumCharacters, seen);
    }

    private static ExternalCapabilityReceipt ReadText(
        string operation,
        KnownEntry file,
        FileInfo info,
        int offset,
        int maximumCharacters,
        Action<Utf8JsonWriter> seen)
    {
        if (info.Length > MaximumTextBytes) return ExternalJson.Failure(operation, "known_text_too_large");
        byte[] bytes = ReadShared(file.Path);
        if (TextFileEncoding.LooksBinary(bytes)) return ExternalJson.Failure(operation, "known_file_not_text");
        string full = TextFileEncoding.Decode(bytes);
        return ExternalJson.Success(operation, ReadResult(
            file, "text", full.Length, LineCount(full), offset, LinesBefore(full, offset),
            Page(full, offset, maximumCharacters),
            writer =>
            {
                writer.WriteNumber("bytes", bytes.Length);
                seen(writer);
            },
            Convert.ToHexStringLower(SHA256.HashData(bytes)), "windows_known_text_file_read"), effectObserved: false);
    }

    private static ExternalCapabilityReceipt ReadPdf(
        string operation,
        KnownEntry file,
        FileInfo info,
        int offset,
        int maximumCharacters,
        Action<Utf8JsonWriter> seen,
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
                HelperProcessJob.Assign(process);
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
        int totalLines = IntOf(root, "lines");
        int pages = IntOf(root, "pages");
        int textPages = IntOf(root, "textPages");
        int unreadPages = IntOf(root, "unreadPages");
        return ExternalJson.Success(operation, ReadResult(
            file, "pdf", characters, totalLines, offset, IntOf(root, "linesBefore"), text,
            writer =>
            {
                writer.WriteNumber("pages", pages);
                writer.WriteNumber("textPages", textPages);
                // Ronda final 8 (regla 3): pages whose text could not be extracted are said apart, and «no text» is
                // said only when every page was read.
                if (unreadPages > 0) writer.WriteNumber("unreadPages", unreadPages);
                if (characters > 0 || unreadPages == 0) writer.WriteBoolean("hasText", characters > 0);
                seen(writer);
            },
            Hash(info.FullName), "windows_known_pdf_pypdf_text_extraction"), effectObserved: false);
    }

    // What a read says before the text itself, so a cut observation still shows how much there is and where to go on:
    // the lines of the whole text and of the page returned, counted here (the 4B miscounted them, e2e p6 E018).
    // Holdout v4 (falsedad): after pages up to line ~1,904 of 3,000 and a last read that failed, the answer was «revisé
    // todo el archivo y no apareció». Which lines of the whole this page holds (fromLine, toLine), whether it reaches the
    // end of the text (endReached), and, when it is not the whole text, readInPart: a text not in this page was not
    // looked for in the rest (the mind's outcome line says «leído en parte» from it).
    private static JsonElement ReadResult(
        KnownEntry file,
        string kind,
        int characters,
        int totalLines,
        int offset,
        int linesBefore,
        string text,
        Action<Utf8JsonWriter> kindFacts,
        string fileSha256,
        string authority) => ExternalJson.Create(writer =>
    {
        bool hasMore = offset + text.Length < characters;
        int lines = LineCount(text);
        writer.WriteStartObject(); writer.WriteNumber("version", 1);
        writer.WriteString("kind", kind);
        writer.WriteString("reviewLabel", Path.GetFileName(file.Path));
        writer.WriteString("folder", file.Label);
        writer.WriteNumber("characters", characters);
        writer.WriteNumber("totalLines", totalLines);
        writer.WriteNumber("offset", offset);
        writer.WriteNumber("lines", lines);
        if (lines > 0)
        {
            writer.WriteNumber("fromLine", linesBefore + 1);
            writer.WriteNumber("toLine", linesBefore + lines);
        }
        writer.WriteNumber("returnedCharacters", text.Length);
        writer.WriteBoolean("hasMore", hasMore);
        if (hasMore) writer.WriteNumber("nextOffset", offset + text.Length);
        writer.WriteBoolean("endReached", !hasMore);
        if (offset > 0 || hasMore) writer.WriteBoolean("readInPart", true);
        kindFacts(writer);
        writer.WriteString("fileSha256", fileSha256);
        writer.WriteString("text", text);
        writer.WriteString("authority", authority);
        writer.WriteEndObject();
    });

    // The lines of a text: each break (\r\n, \n or \r) ends one, and a last line without a break counts too; a final
    // break does not start another (it did, and a 137-line file was said to have 138).
    internal static int LineCount(string text)
    {
        int lines = 0;
        for (int index = 0; index < text.Length; index++)
        {
            if (text[index] == '\n' || (text[index] == '\r' && (index + 1 == text.Length || text[index + 1] != '\n')))
                lines++;
        }
        return text.Length > 0 && text[^1] is not ('\n' or '\r') ? lines + 1 : lines;
    }

    // The lines a text ends before offset (as LineCount counts their breaks): the page from offset starts on the next.
    internal static int LinesBefore(string text, int offset)
    {
        int end = Math.Min(offset, text.Length), lines = 0;
        for (int index = 0; index < end; index++)
        {
            if (text[index] == '\n' || (text[index] == '\r' && (index + 1 == text.Length || text[index + 1] != '\n')))
                lines++;
        }
        return lines;
    }

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
        if (Locate(operation, roots, ExternalJson.RequiredString(arguments, "fileName"), out KnownEntry file,
                out bool walkStopped)
            is { } refused)
            return refused;
        // Renew al máximo (velocidad): one file of that name seen before the walk's time limit is read as the one seen,
        // but never written: a copy deeper in what was not walked may be the one the person meant. Nothing is changed;
        // the one seen is named, so the next call can name it by its path.
        if (walkStopped)
            return SearchIncompleteRefusal(operation, file);
        // Revisión de fase 3: a file Windows runs at sign-in is read like any other, never edited.
        if (AutostartArea.Holds(_autostartRoots, file.Path))
            return ExternalJson.Failure(operation, "path_autostart");
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
                writer.WriteString("next", EditRefusalNext(occurrences, oldText, file.Path));
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

    // The file a stopped walk found is the one seen in the part walked, not proven the only one of its name: a read says
    // which one it is (relativePath) and how far the walk went. A whole walk adds nothing.
    // Renew al máximo (w8, F015): oldText was the file's own name and the refusal only said «not found». What to do is
    // said for any oldText the file does not hold as asked, and a name of the file given as oldText is named as that.
    internal static string EditRefusalNext(int occurrences, string oldText, string path)
    {
        if (occurrences > 1)
            return $"oldText appears {occurrences} times; nothing was changed; give a longer oldText that appears once, "
                + "or replaceAll true to change every one";
        string name = Path.GetFileName(path), stem = Path.GetFileNameWithoutExtension(path), asked = oldText.Trim();
        string read = "nothing was changed; oldText must be the exact text inside the file, copied from file_read; "
            + "file_write with the whole new content replaces all of it";
        // Holdout v5 (V5E061): oldText was the whole content of another file, and the next push was to rewrite this one.
        // That this file holds no such text is said as a fact about which file it is.
        string other = ModelAids.On(ModelAids.EditTextAbsent)
            ? $"{name} holds no such text, so it may not be the file the person means; " : "";
        return asked.Equals(name, StringComparison.OrdinalIgnoreCase) || asked.Equals(stem, StringComparison.OrdinalIgnoreCase)
            || asked.Equals(path, StringComparison.OrdinalIgnoreCase)
            ? "oldText was the file's name, not text inside it; " + read
            : "the file does not hold oldText exactly as given (spaces, line breaks and accents count); " + other + read;
    }

    private Action<Utf8JsonWriter> StoppedWalkFacts(KnownEntry file, bool walkStopped)
    {
        if (!walkStopped) return _ => { };
        string relativePath = RelativeToFolder(file);
        return writer =>
        {
            writer.WriteString("relativePath", relativePath);
            writer.WriteBoolean("onlyFileOfThatName", false);
            WriteWalkScope(writer, walkStopped: true);
        };
    }

    private ExternalCapabilityReceipt SearchIncompleteRefusal(string operation, KnownEntry file)
    {
        string relativePath = RelativeToFolder(file);
        return new ExternalCapabilityReceipt(operation, false, false, ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1);
            writer.WriteString("name", Path.GetFileName(file.Path));
            writer.WriteString("folder", file.Label);
            writer.WriteString("relativePath", relativePath);
            writer.WriteBoolean("changed", false);
            WriteWalkScope(writer, walkStopped: true);
            // Holdout v6 V6E055: «stopped» before «found» and the call only described, the model answered «no
            // encontré» in 2 of 4 runs; the call that edits the one found is said as said_folder says its call.
            if (ModelAids.On(ModelAids.SearchScope))
                writer.WriteString("next", $"nothing was changed: the search of {file.Label} found {relativePath} and "
                    + $"stopped at its {WalkTimeLimit.TotalSeconds:0} s limit before the rest of the folder, so another "
                    + $"file of that name may be there. If {relativePath} is the file the person means, call "
                    + $"{operation.Replace('.', '_')} again with fileName \"{relativePath}\"");
            writer.WriteEndObject();
        }), "known_file_search_incomplete");
    }

    private static int Occurrences(string text, string value)
    {
        int count = 0;
        for (int index = text.IndexOf(value, StringComparison.Ordinal); index >= 0;
             index = text.IndexOf(value, index + value.Length, StringComparison.Ordinal))
            count++;
        return count;
    }

    // file.read and file.edit name one file: by its name, found once anywhere under the folder, by its path
    // relative to the known folder (as file.find gives it, without a subdirectory), or by its full path inside the
    // folder. Two or more are refused with their places; none, with the files whose name without its extension is the
    // one asked, so the next call can name the right one.
    // Renew al máximo (velocidad): a bare name is looked for in one walk with file.find's time limit; under home the
    // walk had none and took 12-83 s (twice over when the name was not there: once for it, once for its stem). When
    // the limit stops the walk, whatever is said carries it (searchScope.timeLimitReached): none is «not in what was
    // walked», several are the places seen so far, and the one found is read as the one seen in what was walked
    // (onlyFileOfThatName false), never as the only one of that name; an edit of it is refused before any effect
    // (known_file_search_incomplete).
    private ExternalCapabilityReceipt? Locate(
        string operation,
        IReadOnlyList<(string Label, string Root)> roots,
        string requested,
        out KnownEntry located,
        out bool walkStopped)
    {
        located = default;
        walkStopped = false;
        string name = requested.Trim().Replace(Path.AltDirectorySeparatorChar, Path.DirectorySeparatorChar);
        // A full path names that one file: it is looked up at its place, never by its name elsewhere under the folder
        // (BAXY Renew audit 2026-10-15: one directly in the folder became a bare name searched in its subfolders).
        bool fullPath = Path.IsPathFullyQualified(name);
        if (fullPath)
        {
            (string Label, string Root)[] holding = [.. roots.Where(item => IsInside(item.Root, name))];
            if (holding.Length == 0) return ExternalJson.Failure(operation, "known_path_outside_folder");
            roots = [holding[0]];
            name = Path.GetRelativePath(holding[0].Root, Path.GetFullPath(name));
        }
        string[] parts = name.Split(Path.DirectorySeparatorChar);
        if (name.Length == 0 || Path.IsPathRooted(name) || name.Contains('*') || name.Contains('?')
            || parts.Any(part => part is "" or "." or ".." || part.IndexOfAny(Path.GetInvalidFileNameChars()) >= 0))
            return ExternalJson.Failure(operation, "known_file_name_invalid");
        List<KnownEntry> matches = [];
        List<KnownEntry> stems = [];
        string stem = parts[^1];
        string? folded = ModelAids.On(ModelAids.NearNames) && FoldedName(stem) is { Length: > 0 } words ? words : null;
        if (fullPath || parts.Length > 1)
        {
            foreach ((string label, string root) in roots)
            {
                string path = Path.GetFullPath(Path.Combine(root, name));
                if (BaxyPrivateArea.Holds(_privateRoots, path)) return ExternalJson.Failure(operation, "path_reserved");
                if (File.Exists(path) && !CrossesReparsePoint(root, path)) matches.Add(new KnownEntry(label, root, path));
            }
            // Holdout v5 (V5E052): a path no file has is looked for alike only in the folder it names, its top level.
            for (int index = 0; matches.Count == 0 && folded is not null && index < roots.Count; index++)
            {
                (string label, string root) = roots[index];
                string folder = Path.GetDirectoryName(Path.GetFullPath(Path.Combine(root, name)))!;
                if (!Directory.Exists(folder) || CrossesReparsePoint(root, folder)) continue;
                var topLevel = new EnumerationOptions
                {
                    IgnoreInaccessible = true, AttributesToSkip = WalkOptions(label).AttributesToSkip,
                };
                foreach (string file in Directory.EnumerateFiles(folder, "*", topLevel))
                {
                    if (stems.Count <= CandidatesShown && !BaxyPrivateArea.Holds(_privateRoots, file)
                        && StemOrAlike(Path.GetFileName(file), stem, folded))
                        stems.Add(new KnownEntry(label, root, file));
                }
            }
        }
        else
        {
            var walk = new WalkBudget(_utcNow, WalkTimeLimit);
            foreach (KnownEntry item in Enumerate(roots, budget: walk))
            {
                string fileName = Path.GetFileName(item.Path);
                if (string.Equals(fileName, name, StringComparison.OrdinalIgnoreCase))
                {
                    matches.Add(item);
                    if (matches.Count > CandidatesShown) break;
                }
                // The stems are only said when the name itself is nowhere: gathered in the same walk, not a second one.
                else if (matches.Count == 0 && stems.Count <= CandidatesShown && StemOrAlike(fileName, stem, folded))
                    stems.Add(item);
            }
            walkStopped = walk.Reached;
        }
        if (matches.Count == 1)
        {
            located = matches[0];
            return null;
        }
        bool stopped = walkStopped;
        KnownEntry[] candidates = matches.Count > 1 ? [.. matches] : [.. stems];
        string code = matches.Count > 1 ? "known_file_ambiguous" : "known_file_not_found";
        if (candidates.Length == 0)
        {
            string[] searched = PlacesLooked(roots);
            string? missing = searched.Length == 0 ? MissingSubdirectoryNext(roots, stem) : null;
            bool walked = !fullPath && parts.Length == 1;
            return new ExternalCapabilityReceipt(operation, false, false, ExternalJson.Create(writer =>
            {
                writer.WriteStartObject(); writer.WriteNumber("version", 1);
                // Renew al máximo (w6, rutas): where it was looked for, as file.find and the delete say it; a path is
                // looked up only at its place (walked false).
                writer.WriteStartArray("searchedFolders");
                foreach (string place in searched)
                    writer.WriteStringValue(place);
                writer.WriteEndArray();
                writer.WriteBoolean("walked", walked);
                WriteWalkScope(writer, stopped);
                if (missing is not null)
                    writer.WriteString("next", missing);
                else if (ModelAids.On(ModelAids.SearchScope) && (stopped || walked))
                    writer.WriteString("next", stopped ? StoppedWalkScope(stem, searched) : NotFoundScope(stem, searched));
                writer.WriteEndObject();
            }), code);
        }
        return CandidatesRefusal(operation, code, candidates, stopped, matches.Count == 0 && folded is not null
            ? NearNamesNext("no file", stem, candidates, "case, accents or extension", stopped)
            : null);
    }

    // The files a name found nowhere offers: its name with another extension, and (aid near_names, folded not null) the
    // names that fold to the same words.
    private static bool StemOrAlike(string fileName, string requested, string? folded) =>
        string.Equals(Path.GetFileNameWithoutExtension(fileName), requested, StringComparison.OrdinalIgnoreCase)
        || (folded is not null && (FoldedName(fileName) == folded
            || FoldedName(Path.GetFileNameWithoutExtension(fileName)) == folded));

    // Holdout v5 (V5E052): a name as a voice says it. Lower case, without accents, and the words between the separators a
    // voice does not dictate (space, -, _ and .) joined by one space: «Factura_Marzo.PDF» and «factura marzo.pdf» are the
    // same words. Only ever used to offer names; nothing is acted on by it.
    internal static string FoldedName(string name)
    {
        string decomposed;
        try
        {
            decomposed = name.Normalize(NormalizationForm.FormD);
        }
        catch (ArgumentException)
        {
            decomposed = name; // a name Windows allows with a lone surrogate has no normal form
        }
        var folded = new StringBuilder(decomposed.Length);
        bool gap = false;
        foreach (char character in decomposed)
        {
            if (CharUnicodeInfo.GetUnicodeCategory(character) == UnicodeCategory.NonSpacingMark) continue;
            if (character is ' ' or '-' or '_' or '.')
            {
                gap = folded.Length > 0;
                continue;
            }
            if (gap) folded.Append(' ');
            gap = false;
            folded.Append(char.ToLowerInvariant(character));
        }
        return folded.ToString();
    }

    // The names alike, said as what they are: not the name asked, its words otherwise written; the exact one is named
    // again to act on it (and then the core asks the yes for that one).
    private static string NearNamesNext(
        string nothing, string asked, IEnumerable<KnownEntry> alike, string otherwise, bool walkStopped) =>
        $"{nothing} {(walkStopped ? "in the part walked " : "")}is named exactly {asked}; these have the same words with "
        + $"other separators, {otherwise}: "
        + string.Join(", ", alike.Take(CandidatesShown).Select(item => $"\"{Path.GetFileName(item.Path)}\"")
            .Distinct(StringComparer.Ordinal))
        + "; to use one, call again with its exact name as fileName";

    // Holdout v5 (V5E047): a subdirectory that is not there walked no folder, and the next said «X is not in no folder».
    // Which subfolder of which known folder does not exist, as the model names it.
    private string? MissingSubdirectoryNext(IEnumerable<(string Label, string Root)> roots, string fileName)
    {
        if (!ModelAids.On(ModelAids.MissingSubdirectory)) return null;
        (string Label, string Place)[] missing = [.. roots.Where(item => !Directory.Exists(item.Root))
            .Select(item => (item.Label, Place: PlaceOf(item)))
            .Where(item => item.Place.Length > item.Label.Length)
            .Distinct()];
        if (missing.Length == 0) return null;
        return string.Join("; ", missing.Select(item =>
                $"{item.Label} has no subfolder \"{item.Place[(item.Label.Length + 1)..]}\" ({item.Place} does not exist)"))
            + $", so {fileName} was not looked for; file_find on "
            + string.Join(" or ", missing.Select(item => item.Label).Distinct(StringComparer.Ordinal))
            + " with no subdirectory lists its folders";
    }

    // A walk the time limit stopped knows only what it walked: the name is not in that part, and the rest is unknown.
    private static string StoppedWalkScope(string fileName, string[] searched) =>
        $"the search of {(searched.Length == 0 ? "the folder" : string.Join(", ", searched))} stopped at its "
        + $"{WalkTimeLimit.TotalSeconds:0} s limit: {fileName} is not in the part walked, and the rest was not searched; "
        + "a subdirectory or the relativePath file_find gives looks only there";

    // Only the folders walked are known not to hold it; a configured folder left out can be searched by its name.
    private string NotFoundScope(string fileName, string[] searched)
    {
        string[] others = [.. _configuredRoots.Keys.Where(key => !searched.Contains(key, StringComparer.Ordinal))];
        string where = searched.Length == 0 ? "no folder" : string.Join(", ", searched);
        return $"{fileName} is not in {where}, subfolders included; nothing else on the PC was searched"
            + (others.Length == 0 ? string.Empty
                : $"; folder {string.Join(" or ", others.Select(key => $"\"{key}\""))} searches more");
    }

    // Ronda final 41 (regla 3): at most this many candidates are given, and a list cut there says so
    // (candidatesTruncated), never read as all the places with that name.
    private const int CandidatesShown = 5;

    // A refusal with the places it saw: each one's name, known folder and path relative to that folder.
    private ExternalCapabilityReceipt CandidatesRefusal(
        string operation, string code, IEnumerable<KnownEntry> candidates, bool walkStopped = false, string? next = null) =>
        new(operation, false, false, ExternalJson.Create(writer =>
        {
            KnownEntry[] all = [.. candidates];
            writer.WriteStartObject(); writer.WriteNumber("version", 1);
            if (all.Length > CandidatesShown)
                writer.WriteBoolean("candidatesTruncated", true);
            // The places seen before the time limit stopped the walk: there may be more of that name past it.
            if (walkStopped) WriteWalkScope(writer, walkStopped: true);
            writer.WriteStartArray("candidates");
            foreach (KnownEntry candidate in all.Take(CandidatesShown))
            {
                writer.WriteStartObject();
                writer.WriteString("name", Path.GetFileName(candidate.Path));
                writer.WriteString("folder", candidate.Label);
                writer.WriteString("relativePath", RelativeToFolder(candidate));
                writer.WriteEndObject();
            }
            writer.WriteEndArray();
            if (next is not null) writer.WriteString("next", next);
            writer.WriteEndObject();
        }), code);

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
    // Renew al máximo (w6, rutas): where a call looked, as the model names it: the known folder, or the subfolder of it
    // the call named («home/proyecto»), never the absolute path. The searched folders said only «home» of a search
    // limited to home's proyecto, and «X is not in home, subfolders included» was read as the whole home searched.
    private string PlaceOf((string Label, string Root) looked)
    {
        string path = Path.GetFullPath(looked.Root).TrimEnd(Path.DirectorySeparatorChar);
        foreach (string folderRoot in _configuredRoots.TryGetValue(looked.Label, out string[]? roots) ? roots : [])
        {
            string root = Path.GetFullPath(folderRoot).TrimEnd(Path.DirectorySeparatorChar);
            if (path.StartsWith(root + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
                return looked.Label + "/" + Path.GetRelativePath(root, path).Replace(Path.DirectorySeparatorChar, '/');
        }
        return looked.Label;
    }

    private string[] PlacesLooked(IEnumerable<(string Label, string Root)> roots) =>
        [.. roots.Where(item => Directory.Exists(item.Root)).Select(PlaceOf).Distinct(StringComparer.Ordinal)];

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
        unread = 0
        for page in reader.pages:
            try:
                text = page.extract_text() or ""
            except Exception:  # noqa: BLE001 - one damaged page does not void the rest, and is counted unread
                text = ""
                unread += 1
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
            "unreadPages": unread,
            "characters": len(full),
            "lines": len(full.splitlines()),
            "linesBefore": full.count("\n", 0, offset),
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

    // Ronda final 8 (regla 3): how far a walk of WalkOptions looks, so «not found» or «these are the duplicates» is
    // never read as a search of everything.
    private static void WriteWalkScope(Utf8JsonWriter writer, bool walkStopped = false)
    {
        writer.WriteStartObject("searchScope");
        writer.WriteNumber("maxRecursionDepth", 12);
        // Said only when the limit stopped it (as file.find says it): the receipts of a whole walk stay as they were.
        if (walkStopped)
        {
            writer.WriteNumber("timeLimitSeconds", WalkTimeLimit.TotalSeconds);
            writer.WriteBoolean("timeLimitReached", true);
        }
        writer.WriteBoolean("ignoreInaccessible", true);
        writer.WriteBoolean("skipReparsePoints", true);
        writer.WriteBoolean("exhaustive", false);
        writer.WriteEndObject();
    }

    // The profile root (home) holds AppData and the system's own hidden folders, which are not where the person keeps
    // files: they are not walked (BAXY Renew 2026-10-15).
    internal static EnumerationOptions WalkOptions(string label) => new()
    {
        RecurseSubdirectories = true,
        IgnoreInaccessible = true,
        AttributesToSkip = label == "home"
            ? FileAttributes.ReparsePoint | FileAttributes.Hidden | FileAttributes.System
            : FileAttributes.ReparsePoint,
        MaxRecursionDepth = 12,
    };

    private IEnumerable<KnownEntry> EnumerateDirectories(
        IReadOnlyList<(string Label, string Root)> roots)
    {
        foreach ((string label, string root) in roots)
        {
            if (!Directory.Exists(root)) continue;
            foreach (string directory in Directory.EnumerateDirectories(root, "*", WalkOptions(label)))
            {
                if (!BaxyPrivateArea.Holds(_privateRoots, directory)) yield return new KnownEntry(label, root, directory);
            }
        }
    }

    // A search by name or content walks for at most this long and answers with what it found, saying so: under home
    // the walk passed the core's 30 s and the App restarted it, losing the turn (BAXY Renew e2e p3, 2026-10-15).
    private static readonly TimeSpan WalkTimeLimit = TimeSpan.FromSeconds(8);

    private sealed class WalkBudget(Func<DateTime> utcNow, TimeSpan limit)
    {
        private readonly DateTime _deadline = utcNow() + limit;

        internal bool Reached { get; private set; }

        internal bool Expired() => Reached = Reached || utcNow() >= _deadline;
    }

    private IEnumerable<KnownEntry> Enumerate(
        IReadOnlyList<(string Label, string Root)> roots,
        List<(string Label, string Root)>? enumerationRoots = null,
        WalkBudget? budget = null)
    {
        foreach ((string label, string root) in roots)
        {
            if (!Directory.Exists(root)) continue;
            // Record the attempted enumeration scope, not exhaustive access.
            // IgnoreInaccessible may skip descendants without reporting them.
            enumerationRoots?.Add((label, root));
            foreach (string file in Directory.EnumerateFiles(root, "*", WalkOptions(label)))
            {
                if (budget is not null && budget.Expired()) yield break;
                if (!BaxyPrivateArea.Holds(_privateRoots, file)) yield return new KnownEntry(label, root, file);
            }
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
        ["downloads"] = [Baxy.Providers.Windows.Filesystem.DownloadsFolder.Path()],
        ["home"] = [Environment.GetFolderPath(Environment.SpecialFolder.UserProfile)],
    };

    // The folder inside each known folder that subdirectory names, confined to it (also for ExplorerFolderAdapter).
    internal static (string Label, string Root)[] SubdirectoryRoots(
        IReadOnlyList<(string Label, string Root)> roots,
        string subdirectory,
        IReadOnlyList<string> privateRoots)
    {
        if (!string.IsNullOrWhiteSpace(subdirectory) && Path.IsPathFullyQualified(subdirectory))
        {
            // Renew al máximo (auditoría de flujos): the known folder's own full path is that folder, not a path outside it.
            string named = Path.GetFullPath(subdirectory).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
            (string Label, string Root)[] itself = [.. roots.Where(item => string.Equals(named,
                Path.GetFullPath(item.Root).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar),
                StringComparison.OrdinalIgnoreCase))];
            if (itself.Length > 0) return [itself[0]];
            (string Label, string Root)[] holding = [.. roots.Where(item => IsInside(item.Root, subdirectory))];
            if (holding.Length == 0) throw new InvalidDataException("known_path_outside_folder");
            roots = [holding[0]];
            subdirectory = Path.GetRelativePath(holding[0].Root, Path.GetFullPath(subdirectory));
        }
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
            if (BaxyPrivateArea.Holds(privateRoots, candidate)) throw new InvalidDataException("path_reserved");
            // Renew al máximo (auditoría de flujos): every part of the way is checked, not only the last; through
            // «AppData\Local\Application Data» (Windows' junction back to Local) BAXY's own area was edited.
            if (Directory.Exists(candidate) && CrossesReparsePoint(root, candidate))
                throw new InvalidDataException("known_subdirectory_reparse_point");
            return (item.Label, candidate);
        }).ToArray();
    }

    // A full path strictly inside a folder (the folder itself is not a path inside it). The model copies the path the
    // person said; a full path inside the named folder is the same place as its relative path (BAXY Renew 2026-10-15,
    // e2e p3 F013), and one outside it is refused before any effect.
    private static bool IsInside(string root, string path)
    {
        string folder = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        return Path.GetFullPath(path).StartsWith(folder + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase);
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
