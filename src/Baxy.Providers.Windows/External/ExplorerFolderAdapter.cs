using System.Text.Json;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// REOPEN1957 H0701 «Dime cuantos archivos .py hay en el directorio actual»
/// (D24): «el directorio actual» is the folder of the Explorer window in the
/// foreground; with no Explorer in front it is the Desktop. The count is of
/// first-level files by extension; only the folder's own name is reported,
/// never its path.
/// </summary>
internal sealed class ExplorerFolderAdapter : IExternalOperationAdapter
{
    private const string ForegroundFolderScript = """
        $signature = '[DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();'
        Add-Type -MemberDefinition $signature -Name ForegroundProbe -Namespace BaxyExplorer | Out-Null
        $foreground = [BaxyExplorer.ForegroundProbe]::GetForegroundWindow().ToInt64()
        $shell = New-Object -ComObject Shell.Application
        $path = ''
        foreach ($window in @($shell.Windows())) {
            try {
                if ([int64]$window.HWND -eq $foreground -and $window.FullName -like '*explorer.exe') {
                    $url = [string]$window.LocationURL
                    if ($url.StartsWith('file:///')) { $path = [System.Uri]::UnescapeDataString($url.Substring(8)).Replace('/', '\') }
                }
            } catch { }
        }
        @{ foreground = $foreground; path = $path } | ConvertTo-Json -Compress
        """;

    private readonly IExternalProcessRunner _runner;
    private readonly Func<string> _desktop;

    internal ExplorerFolderAdapter()
        : this(new ExternalProcessRunner(), static () => Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory))
    {
    }

    internal ExplorerFolderAdapter(IExternalProcessRunner runner, Func<string> desktop)
    {
        _runner = runner ?? throw new ArgumentNullException(nameof(runner));
        _desktop = desktop ?? throw new ArgumentNullException(nameof(desktop));
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

        string? explorerPath = null;
        try
        {
            ExternalProcessResult probe = await _runner.RunAsync(
                "powershell.exe",
                ["-NoProfile", "-NonInteractive", "-Command", "& {\n" + ForegroundFolderScript + "\n}"],
                TimeSpan.FromSeconds(20),
                cancellationToken).ConfigureAwait(false);
            if (probe.ExitCode == 0 && probe.Output.TrimStart().StartsWith('{'))
            {
                using JsonDocument document = JsonDocument.Parse(probe.Output);
                if (document.RootElement.TryGetProperty("path", out JsonElement pathElement)
                    && pathElement.ValueKind == JsonValueKind.String
                    && pathElement.GetString() is { Length: > 0 } path)
                {
                    explorerPath = path;
                }
            }
        }
        catch (Exception exception) when (exception is JsonException or IOException or TimeoutException)
        {
            explorerPath = null;
        }

        string source = explorerPath is not null ? "explorer_foreground" : "desktop";
        string folder = explorerPath ?? _desktop();
        if (!Directory.Exists(folder))
            return ExternalJson.FailureBeforeEffect(operation, "explorer_folder_unavailable");
        int count;
        int total;
        try
        {
            var options = new EnumerationOptions { IgnoreInaccessible = true, RecurseSubdirectories = false, AttributesToSkip = FileAttributes.ReparsePoint };
            string[] files = Directory.EnumerateFiles(folder, "*", options).ToArray();
            total = files.Length;
            count = files.Count(file => string.Equals(Path.GetExtension(file), extension, StringComparison.OrdinalIgnoreCase));
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
            writer.WriteString("authority", "explorer_foreground_folder_toplevel_count");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effectObserved: false);
    }
}
