using System.Diagnostics;
using System.Globalization;
using System.IO.Compression;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using Baxy.Providers.Windows.Applications;
using Baxy.Providers.Windows.Filesystem;
using Microsoft.Win32;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// Auditoría semántica 2026-09-20 (REOPEN1957/1993, D11): las herramientas
/// tipadas de la mesa del PC que Windows verifica mejor que la pantalla —
/// comprimir y abrir un archivo de una carpeta conocida (H0542), cambiar el
/// fondo de escritorio (H0459) y bajar un archivo o imagen de la web (H0069,
/// H0077). Cada una deja su postlectura en el recibo y nombra sus ausencias.
/// </summary>
internal sealed partial class WindowsFileToolsAdapter : IExternalOperationAdapter, IDisposable
{
    private const int MaximumDownloadBytes = 50 * 1024 * 1024;
    private const int MaximumDownloadRedirects = 3;
    private static readonly string[] SafeOpenExtensions =
    [
        ".txt", ".md", ".log", ".pdf", ".rtf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
        ".csv", ".tsv", ".json", ".xml", ".yaml", ".yml", ".png", ".jpg", ".jpeg", ".gif", ".bmp",
        ".webp", ".svg", ".mp3", ".wav", ".m4a", ".flac", ".mp4", ".mkv", ".mov", ".webm", ".zip", ".7z",
    ];
    private readonly Func<string, string?> _knownFolder;
    private readonly HttpClient _http;
    private readonly Func<string, CancellationToken, Task<(byte[] Body, string ContentType)>>? _fetch;
    // cu-v3-abrir-archivo: the installed application a file is opened with (file.open «application»), by the same
    // opening app.open does: resolved in the Start catalog, opened behind the person's window, the front handed back.
    private Func<ApplicationOpenRequest, CancellationToken, ValueTask<ApplicationOpenResult>>? _openWith;

    internal WindowsFileToolsAdapter()
        : this(KnownFolderPath, null)
    {
    }

    internal WindowsFileToolsAdapter(
        Func<string, string?> knownFolder,
        Func<string, CancellationToken, Task<(byte[] Body, string ContentType)>>? fetch,
        Func<ApplicationOpenRequest, CancellationToken, ValueTask<ApplicationOpenResult>>? openWith = null,
        HttpMessageHandler? downloadHandler = null)
    {
        _knownFolder = knownFolder ?? throw new ArgumentNullException(nameof(knownFolder));
        _fetch = fetch;
        _openWith = openWith;
        // Auditoría final: a download reads only public web addresses, as web.fetch does (SearchPageReader): no cookie,
        // every redirect checked before it is followed, and a connection only to the public addresses a name resolves to.
        // Tests answer from their own handler.
        _http = new HttpClient(downloadHandler ?? new SocketsHttpHandler
        {
            UseCookies = false,
            AllowAutoRedirect = false,
            ConnectCallback = SearchPageReader.ConnectToPublicAddressAsync,
        })
        { Timeout = TimeSpan.FromSeconds(40) };
        _http.DefaultRequestHeaders.UserAgent.ParseAdd("Mozilla/5.0 BAXY/1.0 file-download");
    }

    /// <summary>BAXY's own state (<see cref="Baxy.Providers.Windows.Filesystem.BaxyPrivateArea"/>); tests point it at a temporary folder.</summary>
    internal IReadOnlyList<string> PrivateRoots { get; init; } = Baxy.Providers.Windows.Filesystem.BaxyPrivateArea.DefaultRoots();

    public bool CanHandle(string operation) =>
        operation is "file.compress" or "file.open" or "desktop.wallpaper.set" or "web.download";

    public async ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        try
        {
            return operation switch
            {
                "file.compress" => Compress(operation, arguments),
                "file.open" => await OpenAsync(operation, arguments, cancellationToken).ConfigureAwait(false),
                "desktop.wallpaper.set" => Wallpaper(operation, arguments),
                "web.download" => await DownloadAsync(operation, arguments, cancellationToken).ConfigureAwait(false),
                _ => ExternalJson.Failure(operation, "external_operation_not_supported"),
            };
        }
        catch (InvalidDataException)
        {
            return ExternalJson.FailureBeforeEffect(operation, "file_tool_argument_invalid");
        }
    }

    // ---- file.compress -------------------------------------------------------

    private ExternalCapabilityReceipt Compress(string operation, JsonElement arguments)
    {
        string folder = ExternalJson.RequiredString(arguments, "folder");
        string name = ExternalJson.RequiredString(arguments, "name").Trim();
        string? root = ResolveKnownFolder(folder);
        if (root is null)
            return ExternalJson.FailureBeforeEffect(operation, "known_folder_missing");
        string? source = SafeChild(root, name);
        if (source is null)
            return ExternalJson.FailureBeforeEffect(operation, "file_name_invalid");
        bool isDirectory = Directory.Exists(source);
        if (!isDirectory && !File.Exists(source))
            return ExternalJson.FailureBeforeEffect(operation, "file_not_found");
        // Revisión de calidad (archivos): BAXY's own state is not one of the person's files: a folder that holds it
        // (home's AppData) was zipped whole, its journal and memory store with it, beside the person's files.
        if (Baxy.Providers.Windows.Filesystem.BaxyPrivateArea.Holds(PrivateRoots, source)
            || (isDirectory && PrivateRoots.Any(root => Baxy.Providers.Windows.Filesystem.BaxyPrivateArea.Holds([source], root))))
            return ExternalJson.FailureBeforeEffect(operation, "path_reserved");
        string zipPath = source.TrimEnd(Path.DirectorySeparatorChar) + ".zip";
        if (File.Exists(zipPath))
            return ExternalJson.FailureBeforeEffect(operation, "zip_already_exists");
        var effectBoundary = new ExternalEffectBoundary();
        effectBoundary.Cross();
        try
        {
            if (isDirectory)
            {
                ZipFile.CreateFromDirectory(source, zipPath, CompressionLevel.Optimal, includeBaseDirectory: true);
            }
            else
            {
                using ZipArchive archive = ZipFile.Open(zipPath, ZipArchiveMode.Create);
                archive.CreateEntryFromFile(source, Path.GetFileName(source), CompressionLevel.Optimal);
            }
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException or InvalidDataException)
        {
            // Renew al máximo (auditoría de flujos): a file another program holds open (a sharing or lock violation)
            // is that file in use; the half-written zip, made by this call, goes, so nothing is left and a retry is not
            // told the zip already exists.
            string code = exception is IOException && (exception.HResult & 0xFFFF) is 32 or 33
                ? "file_in_use" : "zip_create_failed";
            try
            {
                if (File.Exists(zipPath)) File.Delete(zipPath);
            }
            catch (Exception cleanup) when (cleanup is IOException or UnauthorizedAccessException)
            {
                return effectBoundary.Failure(operation, code);
            }
            return File.Exists(zipPath)
                ? effectBoundary.Failure(operation, code)
                : ExternalJson.FailureBeforeEffect(operation, code);
        }

        int entries;
        try
        {
            using ZipArchive verify = ZipFile.OpenRead(zipPath);
            entries = verify.Entries.Count;
        }
        catch (Exception exception) when (exception is IOException or InvalidDataException)
        {
            return effectBoundary.Failure(operation, "zip_postread_failed", effectObserved: true);
        }

        if (entries == 0)
            return effectBoundary.Failure(operation, "zip_postread_failed", effectObserved: true);
        long bytes = new FileInfo(zipPath).Length;
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("folder", folder);
            writer.WriteString("source", Path.GetFileName(source.TrimEnd(Path.DirectorySeparatorChar)));
            writer.WriteBoolean("sourceIsFolder", isDirectory);
            writer.WriteString("zipName", Path.GetFileName(zipPath));
            writer.WriteNumber("entryCount", entries);
            writer.WriteNumber("bytes", bytes);
            writer.WriteString("authority", "zip_archive_postread");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effectObserved: true);
    }

    // ---- file.open -----------------------------------------------------------

    private async ValueTask<ExternalCapabilityReceipt> OpenAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        string folder = ExternalJson.RequiredString(arguments, "folder");
        string name = ExternalJson.RequiredString(arguments, "name").Trim();
        OpenTarget target = LocateOpenTarget(folder, name, cancellationToken: cancellationToken);
        if (target.Path is not { } path)
            return target.Error == "file_not_found"
                ? new ExternalCapabilityReceipt(operation, false, false, NotFoundResult(folder, name, target), target.Error)
                : ExternalJson.FailureBeforeEffect(operation, target.Error ?? "file_not_found");
        if (!SafeOpenExtensions.Contains(Path.GetExtension(path).ToLowerInvariant()))
            return ExternalJson.FailureBeforeEffect(operation, "file_extension_not_openable");
        if (arguments.TryGetProperty("application", out JsonElement named) && named.ValueKind == JsonValueKind.String
            && named.GetString()?.Trim() is { Length: > 0 } application)
        {
            // molestia-ayudantes: «foreground» when the person asked to see it (the App's rule by who asked, as app.open's:
            // a turn's file.open), never when a mission opens it to work in it (it stays behind the person's window).
            bool shown = arguments.TryGetProperty("foreground", out JsonElement front) && front.ValueKind == JsonValueKind.True;
            return await OpenWithAsync(operation, folder, path, application, shown, cancellationToken)
                .ConfigureAwait(false);
        }

        // Ronda final 31 (regla 3): without the windows read before the launch, a window already open would pass for new.
        if (TopLevelWindows() is not { } windowsBefore)
        {
            return ExternalJson.Failure(operation, "file_open_windows_not_read", false);
        }

        var effectBoundary = new ExternalEffectBoundary();
        effectBoundary.Cross(cancellationToken);
        int? processId = null;
        try
        {
            using Process? process = Process.Start(new ProcessStartInfo(path) { UseShellExecute = true });
            processId = process?.Id;
        }
        catch (Exception exception) when (exception is System.ComponentModel.Win32Exception or IOException or InvalidOperationException)
        {
            return effectBoundary.Failure(operation, "file_open_dispatch_rejected");
        }

        // El archivo se abre en su aplicación o, un zip, en una ventana del
        // Explorador: una ventana nueva cuyo título lleva el nombre es la prueba.
        // Ronda final 20 (regla 3): un proceso vivo no lo es (Word abierto con
        // «el archivo está dañado» sigue vivo); va como dato, sin dar la
        // apertura por hecha.
        string stem = Path.GetFileNameWithoutExtension(path);
        string fileName = Path.GetFileName(path);
        for (int attempt = 0; attempt < 16; attempt++)
        {
            await Task.Delay(250, cancellationToken).ConfigureAwait(false);
            (nint window, string title)? found = NewWindowTitled(windowsBefore, stem, fileName);
            if (found is { } opened)
            {
                JsonElement result = ExternalJson.Create(writer =>
                {
                    writer.WriteStartObject();
                    writer.WriteNumber("version", 1);
                    writer.WriteString("folder", folder);
                    writer.WriteString("name", fileName);
                    WriteOpenedPlace(writer, folder, path);
                    writer.WriteString("windowTitle", opened.title);
                    if (processId is not null) writer.WriteNumber("processId", processId.Value);
                    writer.WriteString("authority", "shell_open_window_title_postread");
                    writer.WriteEndObject();
                });
                return ExternalJson.Success(operation, result, effectObserved: true);
            }
        }

        if (processId is not null && ProcessAlive(processId.Value))
        {
            JsonElement result = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteNumber("version", 1);
                writer.WriteString("folder", folder);
                writer.WriteString("name", fileName);
                writer.WriteNumber("processId", processId.Value);
                writer.WriteBoolean("windowTitledWithFileSeen", false);
                writer.WriteString("authority", "shell_open_process_postread");
                writer.WriteEndObject();
            });
            return new ExternalCapabilityReceipt(operation, true, false, result, "file_open_not_verified");
        }

        return effectBoundary.Failure(operation, "file_open_not_verified", effectObserved: true);
    }

    // cu-v3-abrir-archivo (r9 v3-15, v3-17, v3-18): «abrí paisaje.jpg en Fotos» abre el archivo CON esa aplicación
    // por el shell (su activación de paquete para archivos, o su ejecutable con la ruta), sin teclas ni diálogo: la
    // misma apertura que app.open, delante cuando la persona pidió verlo («foreground») y detrás de su ventana cuando lo
    // abre una misión para trabajar en él. El archivo nunca se copia ni se mueve. La prueba
    // es la ventana de esa aplicación, o una nueva, cuyo título nombra el archivo.
    private async ValueTask<ExternalCapabilityReceipt> OpenWithAsync(
        string operation,
        string folder,
        string path,
        string application,
        bool foreground,
        CancellationToken cancellationToken)
    {
        if (TopLevelWindows() is not { } windowsBefore)
        {
            return ExternalJson.Failure(operation, "file_open_windows_not_read", false);
        }

        Dictionary<nint, string> titlesBefore = windowsBefore.ToDictionary(window => window, WindowTitle);
        var effectBoundary = new ExternalEffectBoundary();
        effectBoundary.Cross(cancellationToken);
        ApplicationOpenResult opened;
        try
        {
            _openWith ??= new WindowsInstalledApplicationOpenProvider().OpenAsync;
            opened = await _openWith(
                new ApplicationOpenRequest(
                    application, "fileopen_" + Guid.NewGuid().ToString("N"), Foreground: foreground, ForControl: true,
                    FilePath: path),
                cancellationToken).ConfigureAwait(false);
        }
        catch (Exception exception) when (exception is System.ComponentModel.Win32Exception or IOException or InvalidOperationException)
        {
            return effectBoundary.Failure(operation, "file_open_dispatch_rejected");
        }

        if (!opened.Verified)
        {
            // Nothing was launched (the application is not installed, is two, or takes no file): nothing happened.
            if (opened.Receipt.LaunchIssued)
                return ExternalJson.FailureAfterEffect(operation, "file_open_not_verified", effectObserved: true);
            // Renew al máximo (lote 4, a; R6.6): the installed names closest to the one asked, none of them opened,
            // travel with the failure as app.open's do (auditoría D1).
            return opened.Candidates is { Count: > 0 } candidates
                ? new ExternalCapabilityReceipt(operation, false, false, ExternalJson.Create(writer =>
                {
                    writer.WriteStartObject();
                    writer.WriteStartArray("candidates");
                    foreach (string candidate in candidates)
                        writer.WriteStringValue(candidate);
                    writer.WriteEndArray();
                    writer.WriteEndObject();
                }), opened.ErrorCode ?? "file_open_not_verified")
                : ExternalJson.FailureBeforeEffect(operation, opened.ErrorCode ?? "file_open_not_verified");
        }

        string stem = Path.GetFileNameWithoutExtension(path);
        string fileName = Path.GetFileName(path);
        // Review of cu-v3-abrir-archivo (findings 2 and 7): a title names the file only outside the application's own
        // name («lista.txt - Bloc de notas» does not name «notas.txt», «Fotos» does not name «foto.png»), and a new
        // window counts only when the application's own program draws it (one the person opens meanwhile is no proof).
        string? program = ProgramOf(opened.ProcessId ?? 0)
            ?? (opened.WindowHandle is > 0 and long owned ? ProgramOf(ForegroundHandBack.ProcessOf(owned)) : null);
        for (int attempt = 0; attempt < 16; attempt++)
        {
            // Ronda final 23-24 (regla 3): the opened application's window proves the file only when it is new or its
            // title changed to name it (Excel refusing a second «Informe.xlsx» keeps the first one's window).
            (nint Handle, string Title)? shown = opened.WindowHandle is > 0 and long handle
                && WindowTitle((nint)handle) is { Length: > 0 } title
                && (!titlesBefore.TryGetValue((nint)handle, out string? titleBefore) || titleBefore != title)
                && TitleNamesFile(title, stem, fileName, opened.DisplayName)
                    ? ((nint)handle, title)
                    : program is null
                        ? null
                        : NewWindowTitled(windowsBefore, stem, fileName, opened.DisplayName,
                            window => string.Equals(
                                ProgramOf(ForegroundHandBack.ProcessOf(window)), program, StringComparison.OrdinalIgnoreCase));
            if (shown is { } window)
            {
                int processId = ForegroundHandBack.ProcessOf(window.Handle);
                JsonElement result = ExternalJson.Create(writer =>
                {
                    writer.WriteStartObject();
                    writer.WriteNumber("version", 1);
                    writer.WriteString("folder", folder);
                    writer.WriteString("name", fileName);
                    WriteOpenedPlace(writer, folder, path);
                    writer.WriteString("application", opened.DisplayName);
                    writer.WriteString("windowTitle", window.Title);
                    writer.WriteNumber("processId", processId > 0 ? processId : opened.ProcessId ?? 0);
                    writer.WriteBoolean("alreadyRunning", opened.AlreadyRunning);
                    // As app.open's receipt: Windows activated the application by itself, and whether the front
                    // went back to the person's window (cu-v3-foco-segunda).
                    if (opened.WindowsActivation)
                    {
                        writer.WriteBoolean("windowsActivation", true);
                        writer.WriteBoolean("frontRestored", opened.FrontRestored);
                    }

                    writer.WriteString("authority", "application_file_open_window_title_postread");
                    writer.WriteEndObject();
                });
                return ExternalJson.Success(operation, result, effectObserved: true);
            }

            await Task.Delay(250, cancellationToken).ConfigureAwait(false);
        }

        return effectBoundary.Failure(operation, "file_open_not_verified", effectObserved: true);
    }

    private static bool TitleNamesFile(string title, string stem, string fileName) =>
        title.Contains(stem, StringComparison.OrdinalIgnoreCase) || title.Contains(fileName, StringComparison.OrdinalIgnoreCase);

    // A window of a named application names the file when, with the application's own name taken out of its title, the
    // title still holds the file's whole name, or its name without extension as a word of its own.
    internal static bool TitleNamesFile(string title, string stem, string fileName, string? application)
    {
        string rest = string.IsNullOrWhiteSpace(application)
            ? title
            : title.Replace(application.Trim(), " ", StringComparison.OrdinalIgnoreCase);
        if (rest.Contains(fileName, StringComparison.OrdinalIgnoreCase))
            return true;
        for (int at = stem.Length == 0 ? -1 : rest.IndexOf(stem, StringComparison.OrdinalIgnoreCase); at >= 0;
             at = rest.IndexOf(stem, at + 1, StringComparison.OrdinalIgnoreCase))
        {
            int end = at + stem.Length;
            if ((at == 0 || !char.IsLetterOrDigit(rest[at - 1])) && (end == rest.Length || !char.IsLetterOrDigit(rest[end])))
                return true;
        }

        return false;
    }

    private static string? ProgramOf(int processId)
    {
        if (processId <= 0)
            return null;
        try
        {
            using var process = System.Diagnostics.Process.GetProcessById(processId);
            return process.ProcessName;
        }
        catch (Exception exception) when (exception is ArgumentException or InvalidOperationException)
        {
            return null;
        }
    }

    // v3 ronda 3 (lugar M6; v3-15, v3-18, t-file-4): el nombre puede traer
    // subcarpetas relativas a la carpeta conocida («baxy-prueba-v3\paisaje.jpg»),
    // nunca «..» ni una ruta absoluta. Sólo se abre el archivo que está donde se
    // dijo (auditoría final 2: abrir otro de otra carpeta era elegir por el
    // modelo). Si no está, falla con file_not_found y el recibo dice dónde se vio
    // un archivo con ese nombre exacto en las carpetas conocidas (a lo sumo
    // cinco, y si la búsqueda terminó), para que el modelo lo abra desde ahí. Un
    // nombre con subcarpetas dice dónde está: no se busca en otro sitio.
    private static readonly string[] OpenSearchFolders = ["desktop", "documents", "downloads", "pictures"];
    private const int OpenSearchDepth = 4;
    // Holdout v6 V6E062 («ábreme horario.txt que está ahí», right after BAXY-bench in the home folder was opened): a bare
    // name asked in the home folder was looked for only in the four folders above, never in the person's own folders of
    // their home, and «no está en ningún otro lugar» was the answer. The home folder holds the whole profile; its folders
    // (its top level) are looked into one level down, before the four.
    private const int HomeSearchDepth = 1;
    private const int OpenSearchCandidates = 5;
    private static readonly TimeSpan OpenSearchBudget = TimeSpan.FromSeconds(3);

    // Where the file asked for is (Path), or why it is not opened (Error) and where a file of that exact name was seen.
    internal sealed record OpenTarget(
        string? Path,
        string? Error,
        IReadOnlyList<(string Folder, string RelativePath)> SeenElsewhere,
        bool SearchComplete,
        // Auditoría final (regla 3): false when nothing was searched (a name with subfolders is looked for only there).
        bool Searched = true);

    internal OpenTarget LocateOpenTarget(
        string folder,
        string name,
        TimeSpan? budget = null,
        CancellationToken cancellationToken = default)
    {
        string? root = ResolveKnownFolder(folder);
        if (root is null)
            return new(null, "known_folder_missing", [], true);
        string? path = SafeRelative(root, name);
        if (path is null)
            return new(null, "file_name_invalid", [], true);
        if (File.Exists(path))
            return new(path, null, [], true);
        string leaf = System.IO.Path.GetFileName(path);
        // Holdout v6 (V6F010): the one file there whose name is the one said with its words otherwise separated is it
        // (SpokenFileNames); of two, none is chosen, and the walk says them.
        if (SameWordsBeside(path, leaf) is [string same])
            return new(same, null, [], true);
        if (name.IndexOfAny(['\\', '/']) >= 0)
            return new(null, "file_not_found", [], false, Searched: false);
        TimeSpan limit = budget ?? OpenSearchBudget;
        var found = new List<(string Folder, string RelativePath)>();
        var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var clock = Stopwatch.StartNew();
        bool incomplete = false;
        bool OutOfTime()
        {
            if (!incomplete && (cancellationToken.IsCancellationRequested || clock.Elapsed > limit))
                incomplete = true;
            return incomplete;
        }

        var options = new EnumerationOptions
        {
            RecurseSubdirectories = true,
            MaxRecursionDepth = OpenSearchDepth,
            IgnoreInaccessible = true,
            AttributesToSkip = FileAttributes.Hidden | FileAttributes.System | FileAttributes.ReparsePoint,
        };
        var paths = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach ((string known, int depth) in OpenSearchPlaces(folder))
        {
            if (OutOfTime())
                break;
            string? knownRoot = ResolveKnownFolder(known);
            if (knownRoot is null || !seen.Add(knownRoot))
                continue;
            options.MaxRecursionDepth = depth;
            try
            {
                // El reloj y la cancelación se miran en cada entrada, no sólo en
                // cada coincidencia: un árbol sin el archivo también se corta.
                var entries = new System.IO.Enumeration.FileSystemEnumerable<string>(
                    knownRoot,
                    (ref System.IO.Enumeration.FileSystemEntry entry) => entry.ToFullPath(),
                    options)
                {
                    ShouldIncludePredicate = (ref System.IO.Enumeration.FileSystemEntry entry) =>
                        !OutOfTime()
                        && !entry.IsDirectory
                        && (entry.FileName.Equals(leaf.AsSpan(), StringComparison.OrdinalIgnoreCase)
                            || SpokenFileNames.Same(entry.FileName.ToString(), leaf)),
                    ShouldRecursePredicate = (ref System.IO.Enumeration.FileSystemEntry _) => !OutOfTime(),
                };
                // A known folder inside the home folder (its Desktop) is seen once, from the home folder.
                foreach (string candidate in entries.Where(paths.Add))
                {
                    found.Add((known, System.IO.Path.GetRelativePath(knownRoot, candidate)));
                    if (found.Count >= OpenSearchCandidates || OutOfTime())
                        break;
                }
            }
            catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
            {
                // Auditoría final (regla 3): a known folder whose listing failed was not searched.
                incomplete = true;
                continue;
            }

            if (found.Count >= OpenSearchCandidates)
                break;
        }

        return new(null, "file_not_found", found, !incomplete && found.Count < OpenSearchCandidates);
    }

    // The files beside path (hidden, system and linked ones left out, as the walk leaves them) whose name is its leaf
    // with the words otherwise separated; two at most, enough to know whether one is the file.
    private static string[] SameWordsBeside(string path, string leaf)
    {
        string? folder = System.IO.Path.GetDirectoryName(path);
        if (folder is null || !Directory.Exists(folder))
            return [];
        try
        {
            return [.. Directory.EnumerateFiles(folder, "*", new EnumerationOptions
            {
                IgnoreInaccessible = true,
                AttributesToSkip = FileAttributes.Hidden | FileAttributes.System | FileAttributes.ReparsePoint,
            }).Where(file => SpokenFileNames.Same(System.IO.Path.GetFileName(file), leaf)).Take(2)];
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            return [];
        }
    }

    // Where a bare name not in the folder asked is looked for, and how deep: the home folder's own folders first when it
    // was the one asked, then the four known folders.
    private static IEnumerable<(string Folder, int Depth)> OpenSearchPlaces(string folder) =>
        (OpenSearchFolders.Contains(folder) ? [] : new[] { (folder, HomeSearchDepth) })
            .Concat(OpenSearchFolders.Select(static known => (known, OpenSearchDepth)));

    private static JsonElement NotFoundResult(string folder, string name, OpenTarget target) => ExternalJson.Create(writer =>
    {
        writer.WriteStartObject();
        writer.WriteNumber("version", 1);
        writer.WriteString("folder", folder);
        writer.WriteString("name", name);
        writer.WriteStartArray("seenElsewhere");
        foreach ((string seenFolder, string relativePath) in target.SeenElsewhere)
        {
            writer.WriteStartObject();
            writer.WriteString("folder", seenFolder);
            writer.WriteString("name", relativePath);
            writer.WriteEndObject();
        }
        writer.WriteEndArray();
        if (!target.Searched)
        {
            // Only the path named was looked at: no other place was searched.
            writer.WriteBoolean("searchedElsewhere", false);
            writer.WriteEndObject();
            return;
        }
        writer.WriteBoolean("searchComplete", target.SearchComplete);
        // What the search covers, as it was made: the four known folders, four levels down (and the home folder asked,
        // one level), without hidden, system or unreadable folders and without links.
        writer.WriteStartArray("searchedFolders");
        foreach ((string known, _) in OpenSearchPlaces(folder))
            writer.WriteStringValue(known);
        writer.WriteEndArray();
        writer.WriteNumber("searchedDepth", OpenSearchDepth);
        if (!OpenSearchFolders.Contains(folder))
            writer.WriteNumber("homeSearchedDepth", HomeSearchDepth);
        writer.WriteBoolean("skipsHiddenSystemAndUnreadable", true);
        writer.WriteEndObject();
    });

    private void WriteOpenedPlace(Utf8JsonWriter writer, string folder, string path)
    {
        string? root = ResolveKnownFolder(folder);
        writer.WriteString(
            "relativePath",
            root is null ? System.IO.Path.GetFileName(path) : System.IO.Path.GetRelativePath(root, path));
    }

    internal static string? SafeRelative(string root, string name)
    {
        string[] parts = name.Split(['\\', '/'], StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
        if (parts.Length == 0 || parts.Length > 8 || name.Length > 200 || name.StartsWith('\\') || name.StartsWith('/')
            || parts.Any(part => part is "." or ".."))
        {
            return null;
        }

        string? path = Path.GetFullPath(root);
        foreach (string part in parts)
        {
            path = SafeChild(path, part);
            if (path is null)
                return null;
        }

        return path;
    }

    // ---- desktop.wallpaper.set ----------------------------------------------

    private ExternalCapabilityReceipt Wallpaper(string operation, JsonElement arguments)
    {
        string? color = arguments.TryGetProperty("color", out JsonElement colorElement) && colorElement.ValueKind == JsonValueKind.String
            ? colorElement.GetString()?.Trim() : null;
        string? folder = arguments.TryGetProperty("folder", out JsonElement folderElement) && folderElement.ValueKind == JsonValueKind.String
            ? folderElement.GetString() : null;
        string? name = arguments.TryGetProperty("name", out JsonElement nameElement) && nameElement.ValueKind == JsonValueKind.String
            ? nameElement.GetString()?.Trim() : null;
        string previousWallpaper = CurrentWallpaperPath();
        string previousColor = Registry.GetValue(@"HKEY_CURRENT_USER\Control Panel\Colors", "Background", null) as string ?? string.Empty;

        if (!string.IsNullOrWhiteSpace(color))
        {
            (byte r, byte g, byte b)? rgb = ParseColor(color);
            if (rgb is null)
                return ExternalJson.FailureBeforeEffect(operation, "wallpaper_color_unknown");
            // Ronda final: that solid colour already shown (no picture, same colour), read before: nothing is sent.
            string already = string.Create(CultureInfo.InvariantCulture, $"{rgb.Value.r} {rgb.Value.g} {rgb.Value.b}");
            if (previousWallpaper.Length == 0 && previousColor == already)
                return ExternalJson.Switched(operation, ExternalJson.Create(writer =>
                {
                    writer.WriteStartObject();
                    writer.WriteNumber("version", 1);
                    writer.WriteString("mode", "solid_color");
                    writer.WriteString("color", color);
                    writer.WriteString("rgb", already);
                    writer.WriteString("authority", "registry_desktop_color_preread");
                    writer.WriteEndObject();
                }), effectObserved: false);
            var effectBoundary = new ExternalEffectBoundary();
            effectBoundary.Cross();
            string value = string.Create(CultureInfo.InvariantCulture, $"{rgb.Value.r} {rgb.Value.g} {rgb.Value.b}");
            try
            {
                Registry.SetValue(@"HKEY_CURRENT_USER\Control Panel\Colors", "Background", value);
                int[] elements = [1];
                uint[] colors = [(uint)(rgb.Value.r | (rgb.Value.g << 8) | (rgb.Value.b << 16))];
                // Ronda final: the registry read back below is not the desktop; these two are what repaint it.
                if (!SetSysColors(1, elements, colors)
                    | !SystemParametersInfo(SpiSetDeskWallpaper, 0, string.Empty, SpifUpdateIniFile | SpifSendChange))
                    return effectBoundary.Failure(operation, "wallpaper_apply_unconfirmed", effectObserved: true);
            }
            catch (Exception exception) when (exception is IOException or UnauthorizedAccessException or System.Security.SecurityException)
            {
                return effectBoundary.Failure(operation, "wallpaper_set_failed");
            }

            string observedColor = Registry.GetValue(@"HKEY_CURRENT_USER\Control Panel\Colors", "Background", null) as string ?? string.Empty;
            string observedWallpaper = CurrentWallpaperPath();
            if (observedColor != value || observedWallpaper.Length != 0)
                return effectBoundary.Failure(operation, "wallpaper_postread_failed", effectObserved: true);
            JsonElement result = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteNumber("version", 1);
                writer.WriteString("mode", "solid_color");
                writer.WriteString("color", color);
                writer.WriteString("rgb", value);
                writer.WriteString("previousWallpaper", previousWallpaper);
                writer.WriteString("previousColor", previousColor);
                writer.WriteString("authority", "spi_desktop_wallpaper_registry_postread");
                writer.WriteEndObject();
            });
            return ExternalJson.Success(operation, result, effectObserved: true);
        }

        if (folder is null || string.IsNullOrWhiteSpace(name))
            return ExternalJson.FailureBeforeEffect(operation, "wallpaper_argument_invalid");
        string? root = ResolveKnownFolder(folder);
        if (root is null)
            return ExternalJson.FailureBeforeEffect(operation, "known_folder_missing");
        string? picture = SafeChild(root, name);
        if (picture is null)
            return ExternalJson.FailureBeforeEffect(operation, "file_name_invalid");
        if (!File.Exists(picture))
            return ExternalJson.FailureBeforeEffect(operation, "file_not_found");
        if (Path.GetExtension(picture).ToLowerInvariant() is not (".png" or ".jpg" or ".jpeg" or ".bmp" or ".gif" or ".webp"))
            return ExternalJson.FailureBeforeEffect(operation, "wallpaper_file_not_an_image");
        // Ronda final: that picture already the wallpaper, read before: the state reached, nothing is sent.
        if (string.Equals(previousWallpaper, picture, StringComparison.OrdinalIgnoreCase))
            return ExternalJson.Switched(operation, ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteNumber("version", 1);
                writer.WriteString("mode", "picture");
                writer.WriteString("folder", folder);
                writer.WriteString("name", Path.GetFileName(picture));
                writer.WriteString("authority", "spi_desktop_wallpaper_preread");
                writer.WriteEndObject();
            }), effectObserved: false);
        var boundary = new ExternalEffectBoundary();
        boundary.Cross();
        if (!SystemParametersInfo(SpiSetDeskWallpaper, 0, picture, SpifUpdateIniFile | SpifSendChange))
            return boundary.Failure(operation, "wallpaper_set_failed");
        string observed = CurrentWallpaperPath();
        if (!string.Equals(observed, picture, StringComparison.OrdinalIgnoreCase))
            return boundary.Failure(operation, "wallpaper_postread_failed", effectObserved: true);
        JsonElement pictureResult = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("mode", "picture");
            writer.WriteString("folder", folder);
            writer.WriteString("name", Path.GetFileName(picture));
            writer.WriteString("previousWallpaper", previousWallpaper);
            writer.WriteString("previousColor", previousColor);
            writer.WriteString("authority", "spi_desktop_wallpaper_postread");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, pictureResult, effectObserved: true);
    }

    // The colour as the model writes it, «#RRGGBB»; a name («azul») is the model's to turn into one (BAXY Renew audit
    // 2026-10-15: a dictionary of colour names here decided which blue the person meant).
    internal static (byte R, byte G, byte B)? ParseColor(string color)
    {
        Match hex = Regex.Match(color.Trim(), "^#?([0-9a-fA-F]{6})$");
        if (hex.Success)
        {
            int value = int.Parse(hex.Groups[1].Value, NumberStyles.HexNumber, CultureInfo.InvariantCulture);
            return ((byte)(value >> 16), (byte)((value >> 8) & 0xFF), (byte)(value & 0xFF));
        }

        return null;
    }

    // ---- web.download --------------------------------------------------------

    private async ValueTask<ExternalCapabilityReceipt> DownloadAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        string url = arguments.TryGetProperty("url", out JsonElement urlElement) && urlElement.ValueKind == JsonValueKind.String
            ? urlElement.GetString()?.Trim() ?? string.Empty : string.Empty;
        string folder = arguments.TryGetProperty("folder", out JsonElement folderElement) && folderElement.ValueKind == JsonValueKind.String
            ? folderElement.GetString() ?? "downloads" : "downloads";
        string? requestedName = arguments.TryGetProperty("name", out JsonElement nameElement) && nameElement.ValueKind == JsonValueKind.String
            ? nameElement.GetString()?.Trim() : null;
        if (url.Length == 0)
            return ExternalJson.FailureBeforeEffect(operation, "download_source_missing");
        string? root = ResolveKnownFolder(folder);
        if (root is null)
            return ExternalJson.FailureBeforeEffect(operation, "known_folder_missing");

        Uri? uri = null;
        Uri? pageUrl = null;
        byte[] body;
        string contentType;
        try
        {
            // Only an address: the image search by query scraped Bing's results page, which the search route had
            // retired by its terms (BAXY Renew audit 2026-10-15, O1); the model looks it up with web.search first.
            if (!url.Contains("://", StringComparison.Ordinal))
                url = "https://" + url;
            if (!Uri.TryCreate(url, UriKind.Absolute, out uri) || uri.Scheme is not ("http" or "https"))
                return ExternalJson.FailureBeforeEffect(operation, "download_url_invalid");
            if (!SearchPageReader.IsPublicPageAddress(uri))
                return ExternalJson.FailureBeforeEffect(operation, "download_url_not_public");

            (body, contentType) = await FetchAsync(uri, cancellationToken).ConfigureAwait(false);
            // H0077 «descarga la imagen de portada de wikipedia.org»: the address of a page downloads the image the
            // page itself announces as its cover (og:image), as the tool's description says, and the receipt names
            // both addresses (BAXY Renew audit 2026-10-15: it did so without saying it).
            if (contentType.StartsWith("text/html", StringComparison.OrdinalIgnoreCase))
            {
                string html = Encoding.UTF8.GetString(body);
                Match cover = Regex.Match(html, "<meta[^>]+property=[\"']og:image[\"'][^>]+content=[\"']([^\"']+)[\"']", RegexOptions.IgnoreCase)
                    is { Success: true } first ? first
                    : Regex.Match(html, "<meta[^>]+content=[\"']([^\"']+)[\"'][^>]+property=[\"']og:image[\"']", RegexOptions.IgnoreCase);
                if (!cover.Success)
                    return ExternalJson.FailureBeforeEffect(operation, "download_page_without_image");
                if (!Uri.TryCreate(uri, cover.Groups[1].Value, out Uri? image))
                    return ExternalJson.FailureBeforeEffect(operation, "download_page_without_image");
                if (!SearchPageReader.IsPublicPageAddress(image))
                    return ExternalJson.FailureBeforeEffect(operation, "download_url_not_public");
                pageUrl = uri;
                uri = image;
                (body, contentType) = await FetchAsync(uri, cancellationToken).ConfigureAwait(false);
            }
        }
        // Renew al máximo (w8): an answer of the server (404, 403, 500) is told with its status, and a connection cut in
        // the middle of the body (HttpIOException, an IOException) is the source's failure before anything was written;
        // it escaped this adapter and was told as external_provider_failed, an effect that may have occurred.
        catch (HttpRequestException exception) when (exception.StatusCode is { } status)
        {
            return DownloadSourceFailure(operation, "download_http_status", (int)status,
                "the server answered with an error status and nothing was saved; another address may work");
        }
        catch (Exception exception) when (exception is HttpRequestException or IOException)
        {
            return DownloadSourceFailure(operation, "download_source_unavailable", null,
                "the address could not be reached, or the connection was cut, and nothing was saved; trying again later "
                + "or another address may work");
        }
        catch (TaskCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            return DownloadSourceFailure(operation, "download_timed_out", null,
                "the server did not answer in time and nothing was saved; trying again later may work");
        }
        catch (InvalidDataException)
        {
            return ExternalJson.FailureBeforeEffect(operation, "download_too_large");
        }

        if (body.Length == 0)
            return ExternalJson.FailureBeforeEffect(operation, "download_empty");
        string fileName = SafeFileName(requestedName ?? Path.GetFileName(uri.LocalPath), contentType);
        string path = Path.Combine(root, fileName);
        path = UniquePath(path);
        var effectBoundary = new ExternalEffectBoundary();
        effectBoundary.Cross(cancellationToken);
        try
        {
            await File.WriteAllBytesAsync(path, body, cancellationToken).ConfigureAwait(false);
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException
            or OperationCanceledException)
        {
            // Renew al máximo (w8): a write cut short (disk full, cancelled) left a partial file under the new name.
            try
            {
                File.Delete(path);
            }
            catch (Exception cleanup) when (cleanup is IOException or UnauthorizedAccessException)
            {
            }
            if (exception is OperationCanceledException)
                throw;
            return effectBoundary.Failure(operation, "download_write_failed");
        }

        long bytes = new FileInfo(path).Length;
        if (bytes != body.Length)
            return effectBoundary.Failure(operation, "download_postread_failed", effectObserved: true);
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("sourceUrl", uri.AbsoluteUri);
            if (pageUrl is not null)
            {
                writer.WriteString("pageUrl", pageUrl.AbsoluteUri);
                writer.WriteBoolean("imageAnnouncedByPage", true);
            }
            writer.WriteString("folder", folder);
            writer.WriteString("name", Path.GetFileName(path));
            writer.WriteNumber("bytes", bytes);
            writer.WriteString("contentType", contentType);
            writer.WriteString("authority", "downloaded_file_size_postread");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effectObserved: true);
    }

    private static ExternalCapabilityReceipt DownloadSourceFailure(
        string operation, string code, int? status, string next) =>
        new(operation, false, false, ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            if (status is { } value) writer.WriteNumber("statusCode", value);
            writer.WriteBoolean("saved", false);
            writer.WriteString("next", next);
            writer.WriteEndObject();
        }), code);

    private async Task<(byte[] Body, string ContentType)> FetchAsync(Uri uri, CancellationToken cancellationToken)
    {
        if (_fetch is not null)
            return await _fetch(uri.AbsoluteUri, cancellationToken).ConfigureAwait(false);
        HttpResponseMessage response = await _http.GetAsync(uri, HttpCompletionOption.ResponseHeadersRead, cancellationToken)
            .ConfigureAwait(false);
        for (int hop = 0; (int)response.StatusCode is >= 300 and < 400; hop++)
        {
            Uri? next = response.Headers.Location is { } location
                ? location.IsAbsoluteUri ? location : new Uri(uri, location)
                : null;
            response.Dispose();
            if (next is null || hop == MaximumDownloadRedirects || !SearchPageReader.IsPublicPageAddress(next))
                throw new HttpRequestException("The download redirects to no public address.");
            uri = next;
            response = await _http.GetAsync(uri, HttpCompletionOption.ResponseHeadersRead, cancellationToken)
                .ConfigureAwait(false);
        }

        using HttpResponseMessage answered = response;
        response.EnsureSuccessStatusCode();
        if (response.Content.Headers.ContentLength is > MaximumDownloadBytes)
            throw new InvalidDataException("download too large");
        // Renew al máximo (auditoría de flujos): a size the server did not announce is bounded while reading; the whole
        // body (up to 2 GB) was read into memory and only then refused.
        (byte[] body, bool truncated) = await WebBrowserAdapter.ReadBoundedBytesAsync(
            response, MaximumDownloadBytes, cancellationToken).ConfigureAwait(false);
        if (truncated)
            throw new InvalidDataException("download too large");
        return (body, response.Content.Headers.ContentType?.MediaType ?? "application/octet-stream");
    }

    internal static string SafeFileName(string candidate, string contentType)
    {
        string name = string.Concat(candidate.Where(character => !Path.GetInvalidFileNameChars().Contains(character))).Trim();
        if (name.Length == 0 || name is "." or "..")
            name = "descarga";
        if (!Path.HasExtension(name))
        {
            string extension = contentType.ToLowerInvariant() switch
            {
                "image/png" => ".png",
                "image/jpeg" => ".jpg",
                "image/gif" => ".gif",
                "image/webp" => ".webp",
                "image/svg+xml" => ".svg",
                "application/pdf" => ".pdf",
                "text/plain" => ".txt",
                _ => ".bin",
            };
            name += extension;
        }

        return name.Length > 120 ? name[^120..] : name;
    }

    private static string UniquePath(string path)
    {
        if (!File.Exists(path))
            return path;
        string directory = Path.GetDirectoryName(path) ?? string.Empty;
        string stem = Path.GetFileNameWithoutExtension(path);
        string extension = Path.GetExtension(path);
        for (int counter = 2; counter < 1000; counter++)
        {
            string candidate = Path.Combine(directory, $"{stem} ({counter}){extension}");
            if (!File.Exists(candidate))
                return candidate;
        }

        return Path.Combine(directory, $"{stem} ({Guid.NewGuid():N}){extension}");
    }

    // ---- helpers ---------------------------------------------------------------

    private string? ResolveKnownFolder(string folder)
    {
        string? path = _knownFolder(folder);
        return path is not null && Directory.Exists(path) ? Path.GetFullPath(path) : null;
    }

    internal static string? KnownFolderPath(string folder) => folder switch
    {
        "desktop" => Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory),
        "documents" => Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments),
        "pictures" => Environment.GetFolderPath(Environment.SpecialFolder.MyPictures),
        "downloads" => Baxy.Providers.Windows.Filesystem.DownloadsFolder.Path(),
        "home" => Environment.GetFolderPath(Environment.SpecialFolder.UserProfile),
        _ => null,
    };

    internal static string? SafeChild(string root, string name)
    {
        if (name.Length == 0 || name.Length > 200 || name.Contains("..", StringComparison.Ordinal)
            || name.IndexOfAny(['/', '\\', ':', '*', '?', '"', '<', '>', '|']) >= 0)
        {
            return null;
        }

        string full = Path.GetFullPath(Path.Combine(root, name));
        return full.StartsWith(Path.GetFullPath(root) + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase) ? full : null;
    }

    private static bool ProcessAlive(int processId)
    {
        try
        {
            using Process process = Process.GetProcessById(processId);
            return !process.HasExited;
        }
        catch (ArgumentException)
        {
            return false;
        }
        catch (InvalidOperationException)
        {
            return false;
        }
    }

    private static HashSet<nint>? TopLevelWindows()
    {
        var handles = new HashSet<nint>();
        EnumWindowsProc callback = (handle, _) =>
        {
            if (IsWindowVisible(handle))
                handles.Add(handle);
            return true;
        };
        return EnumWindows(callback, 0) ? handles : null;
    }

    private static (nint, string)? NewWindowTitled(HashSet<nint> before, string stem, string fileName) =>
        NewWindowTitled(before, stem, fileName, null, null);

    private static (nint, string)? NewWindowTitled(
        HashSet<nint> before, string stem, string fileName, string? application, Func<nint, bool>? drawnBy)
    {
        (nint, string)? found = null;
        EnumWindowsProc callback = (handle, _) =>
        {
            if (before.Contains(handle) || !IsWindowVisible(handle))
                return true;
            string title = WindowTitle(handle);
            if (title.Length > 0
                && (application is null ? TitleNamesFile(title, stem, fileName) : TitleNamesFile(title, stem, fileName, application))
                && (drawnBy is null || drawnBy(handle)))
            {
                found = (handle, title);
                return false;
            }

            return true;
        };
        _ = EnumWindows(callback, 0);
        return found;
    }

    private static unsafe string WindowTitle(nint handle)
    {
        char[] title = new char[512];
        fixed (char* buffer = title)
        {
            int length = GetWindowText(handle, buffer, title.Length);
            return length > 0 ? new string(buffer, 0, length) : string.Empty;
        }
    }

    private static unsafe string CurrentWallpaperPath()
    {
        char[] path = new char[1024];
        fixed (char* buffer = path)
        {
            if (!SystemParametersInfoGet(SpiGetDeskWallpaper, (uint)path.Length, buffer, 0))
                return string.Empty;
            int length = Array.IndexOf(path, '\0');
            return new string(buffer, 0, length < 0 ? path.Length : length);
        }
    }

    public void Dispose() => _http.Dispose();

    private const uint SpiGetDeskWallpaper = 0x0073;
    private const uint SpiSetDeskWallpaper = 0x0014;
    private const uint SpifUpdateIniFile = 0x01;
    private const uint SpifSendChange = 0x02;

    [UnmanagedFunctionPointer(CallingConvention.Winapi)]
    private delegate bool EnumWindowsProc(nint hwnd, nint lParam);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool EnumWindows(EnumWindowsProc callback, nint lParam);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool IsWindowVisible(nint hwnd);

    [LibraryImport("user32.dll", EntryPoint = "GetWindowTextW")]
    private static unsafe partial int GetWindowText(nint handle, char* text, int maximum);

    [LibraryImport("user32.dll", EntryPoint = "SystemParametersInfoW", StringMarshalling = StringMarshalling.Utf16, SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool SystemParametersInfo(uint action, uint param, string value, uint flags);

    [LibraryImport("user32.dll", EntryPoint = "SystemParametersInfoW", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static unsafe partial bool SystemParametersInfoGet(uint action, uint param, char* value, uint flags);

    [LibraryImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool SetSysColors(int count, int[] elements, uint[] colors);
}
