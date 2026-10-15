using System.Security.Cryptography;
using System.Text.Json;
using System.Text;

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
        "filesystem.known.duplicates" or "filesystem.known.list" or "filesystem.known.search"
        or "filesystem.known.trash.named" or "filesystem.path.ensure.absent"
        or "document.pdf.read" or "document.text.read";

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
                "filesystem.known.list" => List(operation, roots, arguments),
                "filesystem.known.search" => Search(operation, roots, arguments),
                "filesystem.known.trash.named" => Trash(
                    operation, roots, arguments, effectBoundary),
                "document.pdf.read" => ReadPdf(operation, roots, arguments, cancellationToken),
                "document.text.read" => ReadText(operation, roots, arguments),
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

    private static ExternalCapabilityReceipt List(
        string operation,
        (string Label, string Root)[] roots,
        JsonElement arguments)
    {
        // FILES1425 «lista los archivos del escritorio», «qué hay en Descargas»:
        // the top-level entries of one known folder, names and kinds only.
        // Hidden and system entries (desktop.ini) are not what the person sees.
        int limit = Math.Clamp(ExternalJson.OptionalInt(arguments, "limit", 50), 1, 100);
        string order = arguments.TryGetProperty("order", out JsonElement orderElement)
            && orderElement.ValueKind == JsonValueKind.String
            && orderElement.GetString() == "recent" ? "recent" : "name";
        var options = new EnumerationOptions
        {
            RecurseSubdirectories = false,
            IgnoreInaccessible = true,
            AttributesToSkip = FileAttributes.Hidden | FileAttributes.System,
        };
        List<(string Name, bool IsFolder, long Size, DateTime ModifiedUtc)> entries = [];
        bool anyRoot = false;
        string folderLabel = roots.Length > 0 ? roots[0].Label : "";
        foreach ((string label, string root) in roots)
        {
            if (!Directory.Exists(root)) continue;
            anyRoot = true;
            folderLabel = label;
            foreach (string path in Directory.EnumerateFileSystemEntries(root, "*", options))
            {
                bool isFolder = Directory.Exists(path);
                entries.Add((
                    Path.GetFileName(path),
                    isFolder,
                    isFolder ? 0 : new FileInfo(path).Length,
                    isFolder ? Directory.GetLastWriteTimeUtc(path) : File.GetLastWriteTimeUtc(path)));
            }
        }
        if (!anyRoot) return ExternalJson.Failure(operation, "known_folder_unavailable");
        // FILES1433 «lista los 5 más recientes»: newest first when asked; otherwise
        // folders first, then names.
        var shown = (order == "recent"
                ? entries.OrderByDescending(item => item.ModifiedUtc)
                    .ThenBy(item => item.Name, StringComparer.OrdinalIgnoreCase)
                : entries.OrderBy(item => item.IsFolder ? 0 : 1)
                    .ThenBy(item => item.Name, StringComparer.OrdinalIgnoreCase))
            .Take(limit)
            .ToArray();
        int folderCount = entries.Count(item => item.IsFolder);
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1);
            writer.WriteString("folder", folderLabel);
            writer.WriteNumber("count", entries.Count);
            writer.WriteNumber("fileCount", entries.Count - folderCount);
            writer.WriteNumber("folderCount", folderCount);
            writer.WriteStartArray("entries");
            foreach (var entry in shown)
            {
                writer.WriteStartObject();
                writer.WriteString("name", entry.Name);
                writer.WriteString("kind", entry.IsFolder ? "folder" : "file");
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
        (string label, string source) = matches[0];
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

    // PDF1689 H0666 «resumime informe.pdf»: the named PDF is located once in
    // the known folders (ambiguity refused) and the text it already carries
    // is extracted by the mind runtime's pypdf; no OCR, no rendering, no
    // effect. The receipt carries the bounded text, the counts and its hash.
    private const long MaximumTextBytes = 4L * 1024 * 1024;

    // REOPEN1957 H0299: a text file of a known folder, read as UTF-8 (BOM
    // honoured); a file with control bytes in its head is not text and says so.
    private static ExternalCapabilityReceipt ReadText(
        string operation,
        IReadOnlyList<(string Label, string Root)> roots,
        JsonElement arguments)
    {
        string fileName = ExternalJson.RequiredString(arguments, "fileName").Trim();
        if (fileName != Path.GetFileName(fileName)
            || fileName.IndexOfAny(Path.GetInvalidFileNameChars()) >= 0
            || fileName.Contains('*') || fileName.Contains('?'))
            return ExternalJson.Failure(operation, "known_file_name_invalid");
        int maximumCharacters = Math.Clamp(
            ExternalJson.OptionalInt(arguments, "maximumCharacters", 4_000), 200, 200_000);
        var matches = Enumerate(roots)
            .Where(item => string.Equals(
                Path.GetFileName(item.Path), fileName, StringComparison.OrdinalIgnoreCase))
            .Take(2)
            .ToArray();
        if (matches.Length == 0) return ExternalJson.Failure(operation, "known_file_not_found");
        if (matches.Length > 1) return ExternalJson.Failure(operation, "known_file_ambiguous");
        (string label, string source) = matches[0];
        var file = new FileInfo(source);
        if (file.Length > MaximumTextBytes) return ExternalJson.Failure(operation, "known_text_too_large");
        byte[] bytes = File.ReadAllBytes(source);
        int probe = Math.Min(bytes.Length, 4_096);
        int control = 0;
        for (int index = 0; index < probe; index++)
        {
            byte value = bytes[index];
            if (value == 0 || (value < 0x20 && value is not (0x09 or 0x0A or 0x0D or 0x0C)))
                control++;
        }
        if (probe > 0 && control * 100 > probe)
            return ExternalJson.Failure(operation, "known_file_not_text");
        Encoding encoding = bytes.Length >= 2 && bytes[0] == 0xFF && bytes[1] == 0xFE ? Encoding.Unicode
            : bytes.Length >= 2 && bytes[0] == 0xFE && bytes[1] == 0xFF ? Encoding.BigEndianUnicode
            : new UTF8Encoding(encoderShouldEmitUTF8Identifier: false, throwOnInvalidBytes: false);
        string full = encoding.GetString(bytes).TrimStart('\uFEFF');
        int lineCount = full.Length == 0 ? 0 : full.Split('\n').Length;
        bool truncated = full.Length > maximumCharacters;
        string text = truncated ? full[..maximumCharacters] : full;
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1);
            writer.WriteString("reviewLabel", fileName); writer.WriteString("folder", label);
            writer.WriteNumber("bytes", file.Length);
            writer.WriteNumber("lines", lineCount);
            writer.WriteNumber("characters", full.Length);
            writer.WriteBoolean("truncated", truncated);
            writer.WriteString("text", text);
            writer.WriteString("fileSha256", Hash(file.FullName));
            writer.WriteString("authority", "windows_known_text_file_utf8_read");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effectObserved: false);
    }

    private static ExternalCapabilityReceipt ReadPdf(
        string operation,
        IReadOnlyList<(string Label, string Root)> roots,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        string fileName = ExternalJson.RequiredString(arguments, "fileName").Trim();
        if (fileName != Path.GetFileName(fileName)
            || fileName.IndexOfAny(Path.GetInvalidFileNameChars()) >= 0
            || fileName.Contains('*') || fileName.Contains('?'))
            return ExternalJson.Failure(operation, "known_file_name_invalid");
        if (!fileName.EndsWith(".pdf", StringComparison.OrdinalIgnoreCase))
            fileName += ".pdf";
        int maximumCharacters = Math.Clamp(
            ExternalJson.OptionalInt(arguments, "maximumCharacters", 12_000), 200, 200_000);
        var matches = Enumerate(roots)
            .Where(item => string.Equals(
                Path.GetFileName(item.Path), fileName, StringComparison.OrdinalIgnoreCase))
            .Take(2)
            .ToArray();
        if (matches.Length == 0) return ExternalJson.Failure(operation, "known_file_not_found");
        if (matches.Length > 1) return ExternalJson.Failure(operation, "known_file_ambiguous");
        (string label, string source) = matches[0];
        var file = new FileInfo(source);
        if (file.Length > MaximumPdfBytes) return ExternalJson.Failure(operation, "known_pdf_too_large");
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
            process.StartInfo.ArgumentList.Add(file.FullName);
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
        int pages = IntOf(root, "pages");
        int textPages = IntOf(root, "textPages");
        bool truncated = root.TryGetProperty("truncated", out JsonElement truncatedElement)
            && truncatedElement.ValueKind == JsonValueKind.True;
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1);
            writer.WriteString("reviewLabel", fileName); writer.WriteString("folder", label);
            writer.WriteNumber("pages", pages); writer.WriteNumber("textPages", textPages);
            writer.WriteNumber("characters", text.Length);
            writer.WriteBoolean("hasText", text.Length > 0);
            writer.WriteBoolean("truncated", truncated);
            writer.WriteString("text", text);
            writer.WriteString("textSha256", Convert.ToHexStringLower(
                SHA256.HashData(Encoding.UTF8.GetBytes(text))));
            writer.WriteString("fileSha256", Hash(file.FullName));
            writer.WriteString("authority", "windows_known_pdf_pypdf_text_extraction");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effectObserved: false);
    }

    // The extractor, run as «python -X utf8 -I -c … <file> <maximumCharacters>»
    // in the registered mind runtime (the venv that carries pypdf): the text
    // the PDF already carries, page by page, bounded; no OCR, no rendering.
    private const string PdfTextExtractor = """
import json
import sys


def main() -> int:
    path = sys.argv[1]
    maximum = max(200, min(int(sys.argv[2]), 200_000))
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
        text_pages = 0
        total = 0
        truncated = False
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
                text_pages += 1
            if total >= maximum:
                truncated = truncated or bool(text)
                continue
            if text:
                room = maximum - total
                if len(text) > room:
                    text = text[:room]
                    truncated = True
                chunks.append(text)
                total += len(text)
        print(json.dumps({
            "pages": pages,
            "textPages": text_pages,
            "characters": total,
            "truncated": truncated,
            "encrypted": encrypted,
            "text": "\n\n".join(chunks),
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

    private static IEnumerable<(string Label, string Path)> EnumerateDirectories(
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
                yield return (label, directory);
        }
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
