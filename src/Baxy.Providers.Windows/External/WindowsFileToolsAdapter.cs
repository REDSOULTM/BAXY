using System.Diagnostics;
using System.Globalization;
using System.IO.Compression;
using System.Net.Http;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using Baxy.Providers.Windows.Applications;
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
    private static readonly string[] SafeOpenExtensions =
    [
        ".txt", ".md", ".log", ".pdf", ".rtf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
        ".csv", ".tsv", ".json", ".xml", ".yaml", ".yml", ".png", ".jpg", ".jpeg", ".gif", ".bmp",
        ".webp", ".svg", ".mp3", ".wav", ".m4a", ".flac", ".mp4", ".mkv", ".mov", ".webm", ".zip", ".7z",
    ];
    private static readonly Dictionary<string, (byte R, byte G, byte B)> NamedColors = new(StringComparer.OrdinalIgnoreCase)
    {
        ["azul"] = (0, 78, 152),
        ["blue"] = (0, 78, 152),
        ["rojo"] = (170, 20, 20),
        ["red"] = (170, 20, 20),
        ["verde"] = (20, 120, 50),
        ["green"] = (20, 120, 50),
        ["negro"] = (0, 0, 0),
        ["black"] = (0, 0, 0),
        ["blanco"] = (255, 255, 255),
        ["white"] = (255, 255, 255),
        ["gris"] = (110, 110, 110),
        ["gray"] = (110, 110, 110),
        ["grey"] = (110, 110, 110),
        ["amarillo"] = (230, 200, 40),
        ["yellow"] = (230, 200, 40),
        ["naranja"] = (230, 120, 30),
        ["orange"] = (230, 120, 30),
        ["violeta"] = (110, 50, 160),
        ["morado"] = (110, 50, 160),
        ["purple"] = (110, 50, 160),
        ["rosa"] = (230, 120, 170),
        ["pink"] = (230, 120, 170),
        ["celeste"] = (120, 190, 240),
        ["lightblue"] = (120, 190, 240),
        ["marron"] = (110, 70, 40),
        ["brown"] = (110, 70, 40),
    };

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
        Func<ApplicationOpenRequest, CancellationToken, ValueTask<ApplicationOpenResult>>? openWith = null)
    {
        _knownFolder = knownFolder ?? throw new ArgumentNullException(nameof(knownFolder));
        _fetch = fetch;
        _openWith = openWith;
        _http = new HttpClient { Timeout = TimeSpan.FromSeconds(40) };
        _http.DefaultRequestHeaders.UserAgent.ParseAdd("Mozilla/5.0 BAXY/1.0 file-download");
    }

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
            return effectBoundary.Failure(operation, "zip_create_failed");
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
        string asked = ExternalJson.RequiredString(arguments, "folder");
        string name = ExternalJson.RequiredString(arguments, "name").Trim();
        (string? path, string folder, string? error) = LocateOpenTarget(asked, name, cancellationToken: cancellationToken);
        if (path is null)
            return ExternalJson.FailureBeforeEffect(operation, error ?? "file_not_found");
        if (!SafeOpenExtensions.Contains(Path.GetExtension(path).ToLowerInvariant()))
            return ExternalJson.FailureBeforeEffect(operation, "file_extension_not_openable");
        if (arguments.TryGetProperty("application", out JsonElement named) && named.ValueKind == JsonValueKind.String
            && named.GetString()?.Trim() is { Length: > 0 } application)
        {
            // molestia-ayudantes: «foreground» when the person asked to see it (the App's rule by who asked, as app.open's:
            // a turn's file.open), never when a mission opens it to work in it (it stays behind the person's window).
            bool shown = arguments.TryGetProperty("foreground", out JsonElement front) && front.ValueKind == JsonValueKind.True;
            return await OpenWithAsync(operation, asked, folder, path, application, shown, cancellationToken)
                .ConfigureAwait(false);
        }

        HashSet<nint> windowsBefore = TopLevelWindows();
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
        // Explorador: una ventana nueva cuyo título lleva el nombre, o un
        // proceso nuevo que sigue vivo, es la prueba.
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
                    WriteOpenedPlace(writer, asked, folder, path);
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
                WriteOpenedPlace(writer, asked, folder, path);
                writer.WriteNumber("processId", processId.Value);
                writer.WriteString("authority", "shell_open_process_postread");
                writer.WriteEndObject();
            });
            return ExternalJson.Success(operation, result, effectObserved: true);
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
        string asked,
        string folder,
        string path,
        string application,
        bool foreground,
        CancellationToken cancellationToken)
    {
        HashSet<nint> windowsBefore = TopLevelWindows();
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
            return opened.Receipt.LaunchIssued
                ? ExternalJson.FailureAfterEffect(operation, "file_open_not_verified", effectObserved: true)
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
            (nint Handle, string Title)? shown = opened.WindowHandle is > 0 and long handle
                && WindowTitle((nint)handle) is { Length: > 0 } title
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
                    WriteOpenedPlace(writer, asked, folder, path);
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
    // nunca «..» ni una ruta absoluta. Si el archivo no está donde se dijo, se
    // busca por su nombre exacto en las carpetas conocidas: uno solo se abre y
    // el recibo dice dónde estaba; dos o más no se adivinan. Un nombre con
    // subcarpetas dice dónde está: si no está ahí, no se busca otro. Una
    // búsqueda cortada por tiempo o cancelación no prueba que el hallado sea el
    // único: no se abre nada (file_search_incomplete).
    private static readonly string[] OpenSearchFolders = ["desktop", "documents", "downloads", "pictures"];
    private const int OpenSearchDepth = 4;
    private static readonly TimeSpan OpenSearchBudget = TimeSpan.FromSeconds(3);

    internal (string? Path, string Folder, string? Error) LocateOpenTarget(
        string folder,
        string name,
        TimeSpan? budget = null,
        CancellationToken cancellationToken = default)
    {
        string? root = ResolveKnownFolder(folder);
        if (root is null)
            return (null, folder, "known_folder_missing");
        string? path = SafeRelative(root, name);
        if (path is null)
            return (null, folder, "file_name_invalid");
        if (File.Exists(path))
            return (path, folder, null);
        if (name.IndexOfAny(['\\', '/']) >= 0)
            return (null, folder, "file_not_found");
        string leaf = System.IO.Path.GetFileName(path);
        TimeSpan limit = budget ?? OpenSearchBudget;
        var found = new List<(string Path, string Folder)>();
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
        foreach (string known in OpenSearchFolders)
        {
            if (OutOfTime())
                break;
            string? knownRoot = ResolveKnownFolder(known);
            if (knownRoot is null || !seen.Add(knownRoot))
                continue;
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
                        && entry.FileName.Equals(leaf.AsSpan(), StringComparison.OrdinalIgnoreCase),
                    ShouldRecursePredicate = (ref System.IO.Enumeration.FileSystemEntry _) => !OutOfTime(),
                };
                foreach (string candidate in entries)
                {
                    if (!found.Any(item => string.Equals(item.Path, candidate, StringComparison.OrdinalIgnoreCase)))
                        found.Add((candidate, known));
                    if (found.Count > 1 || OutOfTime())
                        break;
                }
            }
            catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
            {
                continue;
            }

            if (found.Count > 1)
                break;
        }

        if (found.Count > 1)
            return (null, folder, "file_ambiguous");
        if (incomplete)
            return (null, folder, "file_search_incomplete");
        return found.Count == 1 ? (found[0].Path, found[0].Folder, null) : (null, folder, "file_not_found");
    }

    private void WriteOpenedPlace(Utf8JsonWriter writer, string asked, string folder, string path)
    {
        string? root = ResolveKnownFolder(folder);
        string relative = root is null ? System.IO.Path.GetFileName(path) : System.IO.Path.GetRelativePath(root, path);
        writer.WriteString("relativePath", relative);
        if (!string.Equals(asked, folder, StringComparison.Ordinal)
            || !string.Equals(relative, System.IO.Path.GetFileName(path), StringComparison.Ordinal))
        {
            writer.WriteString("askedFolder", asked);
        }
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
            var effectBoundary = new ExternalEffectBoundary();
            effectBoundary.Cross();
            string value = string.Create(CultureInfo.InvariantCulture, $"{rgb.Value.r} {rgb.Value.g} {rgb.Value.b}");
            try
            {
                Registry.SetValue(@"HKEY_CURRENT_USER\Control Panel\Colors", "Background", value);
                int[] elements = [1];
                uint[] colors = [(uint)(rgb.Value.r | (rgb.Value.g << 8) | (rgb.Value.b << 16))];
                _ = SetSysColors(1, elements, colors);
                _ = SystemParametersInfo(SpiSetDeskWallpaper, 0, string.Empty, SpifUpdateIniFile | SpifSendChange);
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

    internal static (byte R, byte G, byte B)? ParseColor(string color)
    {
        string folded = new string(color.Normalize(NormalizationForm.FormD)
            .Where(character => System.Globalization.CharUnicodeInfo.GetUnicodeCategory(character) != UnicodeCategory.NonSpacingMark)
            .ToArray()).Trim().ToLowerInvariant();
        if (NamedColors.TryGetValue(folded, out (byte R, byte G, byte B) named))
            return named;
        Match hex = Regex.Match(folded, "^#?([0-9a-f]{6})$");
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
        string query = arguments.TryGetProperty("query", out JsonElement queryElement) && queryElement.ValueKind == JsonValueKind.String
            ? queryElement.GetString()?.Trim() ?? string.Empty : string.Empty;
        string folder = arguments.TryGetProperty("folder", out JsonElement folderElement) && folderElement.ValueKind == JsonValueKind.String
            ? folderElement.GetString() ?? "downloads" : "downloads";
        string? requestedName = arguments.TryGetProperty("name", out JsonElement nameElement) && nameElement.ValueKind == JsonValueKind.String
            ? nameElement.GetString()?.Trim() : null;
        if (url.Length == 0 && query.Length == 0)
            return ExternalJson.FailureBeforeEffect(operation, "download_source_missing");
        string? root = ResolveKnownFolder(folder);
        if (root is null)
            return ExternalJson.FailureBeforeEffect(operation, "known_folder_missing");

        Uri? uri = null;
        byte[] body;
        string contentType;
        try
        {
            if (url.Length == 0)
            {
                // REOPEN1957 H0069 «Tienes algun meme?»: the image search lists
                // its results with each picture's own address (murl); the first
                // one is the meme. Measured with the product's User-Agent.
                Uri search = new("https://www.bing.com/images/search?q=" + Uri.EscapeDataString(query) + "&first=1");
                (byte[] page, _) = await FetchAsync(search, cancellationToken).ConfigureAwait(false);
                string html = Encoding.UTF8.GetString(page);
                foreach (Match candidate in Regex.Matches(html, "&quot;murl&quot;:&quot;(https?://[^&]+?)&quot;", RegexOptions.IgnoreCase))
                {
                    if (Uri.TryCreate(candidate.Groups[1].Value, UriKind.Absolute, out Uri? image) && image.Scheme is "http" or "https")
                    {
                        uri = image;
                        break;
                    }
                }

                if (uri is null)
                    return ExternalJson.FailureBeforeEffect(operation, "download_query_without_image");
            }
            else
            {
                if (!url.Contains("://", StringComparison.Ordinal))
                    url = "https://" + url;
                if (!Uri.TryCreate(url, UriKind.Absolute, out uri) || uri.Scheme is not ("http" or "https"))
                    return ExternalJson.FailureBeforeEffect(operation, "download_url_invalid");
            }

            (body, contentType) = await FetchAsync(uri, cancellationToken).ConfigureAwait(false);
            // H0077 «descarga la imagen de portada de wikipedia.org»: a page is
            // not an image; its cover is the image the page itself announces.
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
                uri = image;
                (body, contentType) = await FetchAsync(uri, cancellationToken).ConfigureAwait(false);
            }
        }
        catch (HttpRequestException)
        {
            return ExternalJson.FailureBeforeEffect(operation, "download_source_unavailable");
        }
        catch (TaskCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            return ExternalJson.FailureBeforeEffect(operation, "download_source_unavailable");
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
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
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
            if (query.Length > 0)
                writer.WriteString("query", query);
            writer.WriteString("folder", folder);
            writer.WriteString("name", Path.GetFileName(path));
            writer.WriteNumber("bytes", bytes);
            writer.WriteString("contentType", contentType);
            writer.WriteString("authority", "downloaded_file_size_postread");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effectObserved: true);
    }

    private async Task<(byte[] Body, string ContentType)> FetchAsync(Uri uri, CancellationToken cancellationToken)
    {
        if (_fetch is not null)
            return await _fetch(uri.AbsoluteUri, cancellationToken).ConfigureAwait(false);
        using HttpResponseMessage response = await _http.GetAsync(uri, HttpCompletionOption.ResponseHeadersRead, cancellationToken)
            .ConfigureAwait(false);
        response.EnsureSuccessStatusCode();
        if (response.Content.Headers.ContentLength is > MaximumDownloadBytes)
            throw new InvalidDataException("download too large");
        byte[] body = await response.Content.ReadAsByteArrayAsync(cancellationToken).ConfigureAwait(false);
        if (body.Length > MaximumDownloadBytes)
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
        "downloads" => Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), "Downloads"),
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

    private static HashSet<nint> TopLevelWindows()
    {
        var handles = new HashSet<nint>();
        EnumWindowsProc callback = (handle, _) =>
        {
            if (IsWindowVisible(handle))
                handles.Add(handle);
            return true;
        };
        _ = EnumWindows(callback, 0);
        return handles;
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
