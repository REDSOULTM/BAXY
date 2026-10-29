using System.Text.Json;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// REOPEN1957 H0701 «Dime cuantos archivos .py hay en el directorio actual»
/// (D24): «el directorio actual» is the folder of the Explorer window in the
/// foreground (with none in front, of the only one open: holdout v6 V6E027),
/// or the known folder the model names. With neither, it fails:
/// it took the Desktop in silence (BAXY Renew audit 2026-10-15). The count is
/// of first-level files by extension; only the folder's own name is reported,
/// never its path.
/// </summary>
internal sealed class ExplorerFolderAdapter : IExternalOperationAdapter
{
    // Holdout v6 V6E027: every Explorer window and tab (Windows 11's tabs are shell windows of the same HWND) with the
    // folder it shows ('' for none: Home, This PC), and the window in front; which one is meant is chosen in C#
    // (ChosenFolder). A file:// URL of a share is its UNC path; a window that could not be read is said as such.
    private const string ForegroundFolderScript = """
        $signature = '[DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();'
        Add-Type -MemberDefinition $signature -Name ForegroundProbe -Namespace BaxyExplorer | Out-Null
        $foreground = [BaxyExplorer.ForegroundProbe]::GetForegroundWindow().ToInt64()
        $shell = New-Object -ComObject Shell.Application
        $windows = @();$unread = $false
        foreach ($window in @($shell.Windows())) {
            try {
                if ($window.FullName -like '*explorer.exe') {
                    $url = [string]$window.LocationURL
                    $path = if ($url.StartsWith('file:')) { ([System.Uri]$url).LocalPath } else { '' }
                    $windows += @{ hwnd = [int64]$window.HWND; path = [string]$path }
                }
            } catch { $unread = $true }
        }
        @{ foreground = $foreground; windows = $windows; unread = $unread } | ConvertTo-Json -Compress -Depth 3
        """;

    private readonly IExternalProcessRunner _runner;
    private readonly Func<string, string?> _knownFolder;
    private readonly IReadOnlyList<string> _privateRoots;

    internal ExplorerFolderAdapter()
        : this(new ExternalProcessRunner(), WindowsFileToolsAdapter.KnownFolderPath)
    {
    }

    internal ExplorerFolderAdapter(
        IExternalProcessRunner runner,
        Func<string, string?> knownFolder,
        IReadOnlyList<string>? privateRoots = null)
    {
        _runner = runner ?? throw new ArgumentNullException(nameof(runner));
        _knownFolder = knownFolder ?? throw new ArgumentNullException(nameof(knownFolder));
        _privateRoots = privateRoots ?? Baxy.Providers.Windows.Filesystem.BaxyPrivateArea.DefaultRoots();
    }

    public bool CanHandle(string operation) => operation == "filesystem.explorer.count";

    public async ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        string extension = ExternalJson.RequiredString(arguments, "extension").Trim().ToLowerInvariant();
        if (extension.StartsWith('*'))
            extension = extension[1..];
        if (!extension.StartsWith('.'))
            extension = "." + extension;
        if (extension.Length < 2 || extension.Length > 16 || extension.IndexOfAny(Path.GetInvalidFileNameChars()) >= 0)
            return ExternalJson.FailureBeforeEffect(operation, "extension_invalid");

        string? named = arguments.TryGetProperty("path", out JsonElement pathElement)
            && pathElement.ValueKind == JsonValueKind.String ? pathElement.GetString() : null;
        if (named is not null)
        {
            // P2.4 (ajuste c3): the folder as the person said it (PersonFolders.Place), in one of the known folders.
            if (Baxy.Providers.Windows.Filesystem.PersonFolders.Place(named,
                    Baxy.Providers.Windows.Filesystem.PersonFolders.PathLabels(operation), _knownFolder) is not { } said
                || _knownFolder(said.Label) is not { } known)
                return ExternalJson.FailureBeforeEffect(operation, "known_path_outside_folder");
            // Holdout v5 V5E034/V5E044: a folder inside the known one, confined to it as the other known-folder tools.
            if (said.Relative.Length > 0)
            {
                try
                {
                    known = WindowsKnownFileAdapter.SubdirectoryRoots(
                        [(said.Label, known)], said.Relative, _privateRoots)[0].Root;
                }
                catch (InvalidDataException exception)
                {
                    return ExternalJson.FailureBeforeEffect(operation, exception.Message);
                }
                catch (Exception exception) when (exception is ArgumentException or NotSupportedException
                    or IOException or UnauthorizedAccessException)
                {
                    return ExternalJson.FailureBeforeEffect(operation, "known_subdirectory_invalid");
                }

                if (!Directory.Exists(known))
                    return ExternalJson.FailureBeforeEffect(operation, "known_subdirectory_not_found");
            }

            return Count(operation, known, "known_folder", extension);
        }

        // Auditoría final (regla 3): «no Explorer» only from a probe that read every shell window; a probe that failed, or
        // a window it could not read, is the folder not read, and an Explorer showing no file folder is said as that.
        (string? Path, bool InFront, string NotCounted) chosen = (null, false, "explorer_front_not_read");
        try
        {
            ExternalProcessResult probe = await _runner.RunPowerShellAsync(
                ForegroundFolderScript,
                [],
                TimeSpan.FromSeconds(20),
                cancellationToken).ConfigureAwait(false);
            if (probe.ExitCode == 0 && probe.Output.TrimStart().StartsWith('{'))
            {
                using JsonDocument document = JsonDocument.Parse(probe.Output);
                chosen = ChosenFolder(document.RootElement);
            }
        }
        catch (Exception exception) when (exception is JsonException or IOException or TimeoutException
            or InvalidOperationException)
        {
            chosen = (null, false, "explorer_front_not_read");
        }

        return chosen.Path is null
            ? ExternalJson.FailureBeforeEffect(operation, chosen.NotCounted)
            : Count(operation, chosen.Path, chosen.InFront ? "explorer_foreground" : "explorer_open", extension);
    }

    /// <summary>
    /// The folder of the Explorer window meant, from the probe's windows (hwnd and the folder each tab shows, '' for none):
    /// the one in front; holdout v6 V6E027 («la carpeta que tengo abierta en el explorer», the Explorer behind the
    /// developer's editor: no_explorer_in_front, and the reply «no hay ninguna ventana del Explorador abierta»), with none
    /// in front, the only one open. One folder among a window's tabs is its folder only when they all show it. With
    /// several open and none in front, or the only one open showing no one folder, which is meant is not known
    /// (explorer_not_in_front); with none open, no_explorer_in_front.
    /// </summary>
    internal static (string? Path, bool InFront, string NotCounted) ChosenFolder(JsonElement probe)
    {
        if (!probe.TryGetProperty("unread", out JsonElement unread) || unread.ValueKind != JsonValueKind.False)
            return (null, false, "explorer_front_not_read");
        long front = probe.TryGetProperty("foreground", out JsonElement foreground) && foreground.TryGetInt64(out long hwnd)
            ? hwnd
            : 0;
        var tabs = new List<(long Window, string Path)>();
        if (probe.TryGetProperty("windows", out JsonElement windows) && windows.ValueKind == JsonValueKind.Array)
        {
            foreach (JsonElement window in windows.EnumerateArray())
            {
                if (!window.TryGetProperty("hwnd", out JsonElement handle) || !handle.TryGetInt64(out long shown)
                    || !window.TryGetProperty("path", out JsonElement path) || path.ValueKind != JsonValueKind.String)
                    return (null, false, "explorer_front_not_read");
                tabs.Add((shown, path.GetString()!));
            }
        }

        long[] open = [.. tabs.Select(tab => tab.Window).Distinct()];
        bool inFront = open.Contains(front);
        if (!inFront && open.Length != 1)
            return (null, false, open.Length == 0 ? "no_explorer_in_front" : "explorer_not_in_front");
        long meant = inFront ? front : open[0];
        string[] shownTabs = [.. tabs.Where(tab => tab.Window == meant).Select(tab => tab.Path)];
        string[] folders = [.. shownTabs.Where(path => path.Length > 0).Distinct(StringComparer.OrdinalIgnoreCase)];
        if (folders.Length == 1 && folders.Length == shownTabs.Distinct(StringComparer.OrdinalIgnoreCase).Count())
            return (folders[0], inFront, string.Empty);
        if (!inFront)
            return (null, false, "explorer_not_in_front");
        return (null, true, folders.Length == 0 ? "explorer_in_front_shows_no_file_folder" : "explorer_front_tab_not_known");
    }

    private static ExternalCapabilityReceipt Count(string operation, string folder, string source, string extension)
    {
        if (!Directory.Exists(folder))
            return ExternalJson.FailureBeforeEffect(operation, "explorer_folder_unavailable");
        int count;
        int total;
        int subfolders;
        int hiddenOrSystem;
        try
        {
            // Auditoría final (regla 3): the files the person sees there; a OneDrive file kept only in the cloud is a
            // reparse point and is counted (one level, no link is followed into), and hidden or system files, which the
            // Explorer hides by default, are not.
            var options = new EnumerationOptions
            {
                IgnoreInaccessible = true, RecurseSubdirectories = false,
                AttributesToSkip = FileAttributes.Hidden | FileAttributes.System,
            };
            string[] files = Directory.EnumerateFiles(folder, "*", options).ToArray();
            total = files.Length;
            count = files.Count(file => string.Equals(Path.GetExtension(file), extension, StringComparison.OrdinalIgnoreCase));
            subfolders = Directory.EnumerateDirectories(folder, "*", options).Count();
            hiddenOrSystem = new DirectoryInfo(folder).EnumerateFiles("*", new EnumerationOptions
                {
                    IgnoreInaccessible = true, RecurseSubdirectories = false, AttributesToSkip = 0,
                })
                .Count(file => (file.Attributes & (FileAttributes.Hidden | FileAttributes.System)) != 0);
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            return ExternalJson.FailureBeforeEffect(operation, "explorer_folder_unavailable");
        }

        string folderName = Path.GetFileName(folder.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar));
        if (folderName.Length == 0)
            folderName = folder.TrimEnd(Path.DirectorySeparatorChar);
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("folderName", folderName);
            writer.WriteString("source", source);
            writer.WriteString("extension", extension);
            writer.WriteNumber("count", count);
            writer.WriteNumber("filesInFolder", total);
            // Holdout v4 (falsedad: «Sí, porque no había .bak» with three .bak files present): the count is of the
            // files directly in the folder; what it did not look at is said beside it, so a «no hay» is told only of
            // that: its subfolders were not opened and its hidden and system files were not counted (readInPart when
            // there are any).
            writer.WriteString("depth", "top_level");
            writer.WriteNumber("subfoldersNotOpened", subfolders);
            writer.WriteNumber("hiddenOrSystemSkipped", hiddenOrSystem);
            if (subfolders > 0 || hiddenOrSystem > 0) writer.WriteBoolean("readInPart", true);
            writer.WriteString("authority", "explorer_foreground_folder_toplevel_count");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effectObserved: false);
    }
}
