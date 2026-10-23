using System.Text.Json;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// REOPEN1957 H0701 «Dime cuantos archivos .py hay en el directorio actual»
/// (D24): «el directorio actual» is the folder of the Explorer window in the
/// foreground, or the known folder the model names. With neither, it fails:
/// it took the Desktop in silence (BAXY Renew audit 2026-10-15). The count is
/// of first-level files by extension; only the folder's own name is reported,
/// never its path.
/// </summary>
internal sealed class ExplorerFolderAdapter : IExternalOperationAdapter
{
    private const string ForegroundFolderScript = """
        $signature = '[DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();'
        Add-Type -MemberDefinition $signature -Name ForegroundProbe -Namespace BaxyExplorer | Out-Null
        $foreground = [BaxyExplorer.ForegroundProbe]::GetForegroundWindow().ToInt64()
        $shell = New-Object -ComObject Shell.Application
        # Windows 11's tabs are shell windows of the same HWND: one folder among them is the one in front only when they
        # all show it; different folders leave the tab on show not known. A file:// URL of a share is its UNC path.
        # Every tab of that window counts: one that shows no file folder (Home, This PC) or could not be read leaves the
        # tab on show not known as well.
        $paths = @();$explorer = $false;$unread = $false;$tabs = 0;$other = 0
        foreach ($window in @($shell.Windows())) {
            try {
                if ([int64]$window.HWND -eq $foreground -and $window.FullName -like '*explorer.exe') {
                    $explorer = $true
                    $tabs++
                    $url = [string]$window.LocationURL
                    if ($url.StartsWith('file:')) { $paths += @(([System.Uri]$url).LocalPath) } else { $other++ }
                }
            } catch { $unread = $true }
        }
        $distinct = @($paths | Sort-Object -Unique)
        $known = (-not $unread) -and $other -eq 0 -and $distinct.Count -eq 1
        $path = if ($known) { [string]$distinct[0] } else { '' }
        $ambiguous = $distinct.Count -gt 1 -or ($distinct.Count -eq 1 -and $other -gt 0)
        @{ foreground = $foreground; path = $path; explorer = $explorer; unread = $unread; tabs = $(if ($ambiguous) { 2 } else { 1 }) } | ConvertTo-Json -Compress
        """;

    private readonly IExternalProcessRunner _runner;
    private readonly Func<string, string?> _knownFolder;

    internal ExplorerFolderAdapter()
        : this(new ExternalProcessRunner(), WindowsFileToolsAdapter.KnownFolderPath)
    {
    }

    internal ExplorerFolderAdapter(IExternalProcessRunner runner, Func<string, string?> knownFolder)
    {
        _runner = runner ?? throw new ArgumentNullException(nameof(runner));
        _knownFolder = knownFolder ?? throw new ArgumentNullException(nameof(knownFolder));
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

        string? named = arguments.TryGetProperty("folder", out JsonElement folderElement)
            && folderElement.ValueKind == JsonValueKind.String ? folderElement.GetString() : null;
        if (named is not null)
        {
            string? known = _knownFolder(named);
            return known is null
                ? ExternalJson.FailureBeforeEffect(operation, "known_folder_invalid")
                : Count(operation, known, "known_folder", extension);
        }

        // Auditoría final (regla 3): «no Explorer in front» only from a probe that read every shell window; a probe
        // that failed, or a window it could not read, is the front not read, and an Explorer showing no file folder is
        // said as that.
        string? explorerPath = null;
        string notCounted = "explorer_front_not_read";
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
                JsonElement root = document.RootElement;
                if (root.TryGetProperty("path", out JsonElement pathElement)
                    && pathElement.ValueKind == JsonValueKind.String
                    && pathElement.GetString() is { Length: > 0 } path)
                {
                    explorerPath = path;
                }
                else if (root.TryGetProperty("tabs", out JsonElement tabs) && tabs.ValueKind == JsonValueKind.Number
                    && tabs.GetInt32() > 1)
                {
                    notCounted = "explorer_front_tab_not_known";
                }
                else if (root.TryGetProperty("explorer", out JsonElement explorer) && explorer.ValueKind == JsonValueKind.True)
                {
                    notCounted = root.TryGetProperty("unread", out JsonElement partly) && partly.ValueKind == JsonValueKind.True
                        ? "explorer_front_not_read"
                        : "explorer_in_front_shows_no_file_folder";
                }
                else if (root.TryGetProperty("unread", out JsonElement unread) && unread.ValueKind == JsonValueKind.False)
                {
                    notCounted = "no_explorer_in_front";
                }
            }
        }
        catch (Exception exception) when (exception is JsonException or IOException or TimeoutException)
        {
            explorerPath = null;
        }

        return explorerPath is null
            ? ExternalJson.FailureBeforeEffect(operation, notCounted)
            : Count(operation, explorerPath, "explorer_foreground", extension);
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
