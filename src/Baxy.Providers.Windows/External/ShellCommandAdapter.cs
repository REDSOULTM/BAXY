using System.Text.Json;
using System.Text.RegularExpressions;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// Auditoría semántica 2026-09-20 (REOPEN1993, comandos; D11): «ejecuta ls»,
/// «ejecuta pytest», «corré git status» se corren de verdad en una consola
/// PowerShell sin perfil, con un plazo y una salida acotados, y el recibo trae
/// la salida tal cual para que el final la cite. Lo que borra, mata, formatea
/// o toca la configuración del sistema no se corre por aquí: se nombra y para.
/// </summary>
internal sealed partial class ShellCommandAdapter : IExternalOperationAdapter
{
    internal static readonly TimeSpan CommandTimeout = TimeSpan.FromSeconds(60);
    internal const int MaximumOutputCharacters = 8 * 1024;

    private readonly IExternalProcessRunner _runner;
    private readonly string _defaultWorkingDirectory;

    internal ShellCommandAdapter()
        // Decisión de adaptador (Fase 5, 2026-09-21; H0048 «ejecuta pytest»): sin carpeta
        // nombrada, el comando corre en una carpeta de trabajo propia y vacía del producto
        // (<datos>/shell-cwd), nunca en el perfil del usuario, donde «pytest» o «dir /s»
        // recorrerían y ejecutarían cosas ajenas. Una carpeta conocida se nombra en `cwd`.
        : this(new ExternalProcessRunner(), DefaultWorkingDirectory())
    {
    }

    private static string DefaultWorkingDirectory()
    {
        string root = Environment.GetEnvironmentVariable("BAXY_DATA_DIR") is { Length: > 0 } configured
            ? configured
            : Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "BAXY", "development");
        string directory = Path.Combine(root, "shell-cwd");
        try
        {
            Directory.CreateDirectory(directory);
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            return Path.GetTempPath();
        }

        return directory;
    }

    private static readonly Dictionary<string, Environment.SpecialFolder> KnownFolders = new(StringComparer.OrdinalIgnoreCase)
    {
        ["desktop"] = Environment.SpecialFolder.DesktopDirectory,
        ["escritorio"] = Environment.SpecialFolder.DesktopDirectory,
        ["documents"] = Environment.SpecialFolder.MyDocuments,
        ["documentos"] = Environment.SpecialFolder.MyDocuments,
        ["downloads"] = Environment.SpecialFolder.UserProfile,
        ["descargas"] = Environment.SpecialFolder.UserProfile,
    };

    // «cwd» may be a known folder name (desktop/documents/downloads, or a subfolder of
    // one as «documents/proyecto») or an absolute path; anything else is refused.
    private static string? ResolveWorkingDirectory(string cwd)
    {
        string trimmed = cwd.Trim().Replace('/', Path.DirectorySeparatorChar);
        if (Path.IsPathFullyQualified(trimmed))
            return trimmed;
        string[] parts = trimmed.Split(Path.DirectorySeparatorChar, StringSplitOptions.RemoveEmptyEntries);
        if (parts.Length == 0 || !KnownFolders.TryGetValue(parts[0], out Environment.SpecialFolder folder))
            return null;
        string root = Environment.GetFolderPath(folder);
        if (parts[0].Equals("downloads", StringComparison.OrdinalIgnoreCase) || parts[0].Equals("descargas", StringComparison.OrdinalIgnoreCase))
            root = Path.Combine(root, "Downloads");
        if (parts.Skip(1).Any(part => part is "." or ".."))
            return null;
        return Path.Combine([root, .. parts.Skip(1)]);
    }

    internal ShellCommandAdapter(IExternalProcessRunner runner, string defaultWorkingDirectory)
    {
        _runner = runner ?? throw new ArgumentNullException(nameof(runner));
        _defaultWorkingDirectory = defaultWorkingDirectory ?? throw new ArgumentNullException(nameof(defaultWorkingDirectory));
    }

    public bool CanHandle(string operation) => operation is "shell.command.run";

    public async ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        string command;
        try
        {
            command = ExternalJson.RequiredString(arguments, "command").Trim();
        }
        catch (InvalidDataException)
        {
            return ExternalJson.FailureBeforeEffect(operation, "shell_command_argument_invalid");
        }

        string? cwd = arguments.TryGetProperty("cwd", out JsonElement directory)
            && directory.ValueKind == JsonValueKind.String
            && !string.IsNullOrWhiteSpace(directory.GetString())
                ? directory.GetString()!.Trim()
                : null;
        if (command.Length == 0 || command.Contains('\n') || command.Contains('\r'))
            return ExternalJson.FailureBeforeEffect(operation, "shell_command_argument_invalid");
        if (IsDestructive(command))
            return ExternalJson.FailureBeforeEffect(operation, "shell_command_destructive");

        string? workingDirectory = cwd is null ? _defaultWorkingDirectory : ResolveWorkingDirectory(cwd);
        if (workingDirectory is null || !Directory.Exists(workingDirectory))
            return ExternalJson.FailureBeforeEffect(operation, "shell_command_directory_not_found");

        // La consola se coloca en la carpeta antes del comando, dentro de la misma
        // orden, para que el corredor no necesite un directorio de trabajo propio.
        string script = "Set-Location -LiteralPath " + QuoteLiteral(workingDirectory) + "; " + command
            + "; exit $LASTEXITCODE";
        var effectBoundary = new ExternalEffectBoundary();
        DateTime started = DateTime.UtcNow;
        ExternalProcessResult process;
        try
        {
            effectBoundary.Cross(cancellationToken);
            process = await _runner.RunAsync(
                "powershell.exe",
                ["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
                CommandTimeout, cancellationToken).ConfigureAwait(false);
        }
        catch (TimeoutException)
        {
            return effectBoundary.Failure(operation, "shell_command_timeout", effectObserved: true);
        }
        catch (Exception exception) when (exception is IOException or System.ComponentModel.Win32Exception)
        {
            return effectBoundary.Failure(operation, "shell_command_not_started");
        }

        (string stdout, bool stdoutTruncated) = Bound(process.Output);
        (string stderr, bool stderrTruncated) = Bound(process.Error);
        string[] lines = stdout.Split('\n', StringSplitOptions.RemoveEmptyEntries)
            .Select(line => line.TrimEnd('\r'))
            .Where(line => line.Trim().Length > 0)
            .ToArray();
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("command", command);
            writer.WriteString("cwd", workingDirectory);
            writer.WriteNumber("exitCode", process.ExitCode);
            writer.WriteBoolean("succeeded", process.ExitCode == 0);
            writer.WriteString("stdout", stdout);
            writer.WriteString("stderr", stderr);
            writer.WriteNumber("lineCount", lines.Length);
            writer.WriteStartArray("lines");
            foreach (string line in lines.Take(60))
                writer.WriteStringValue(line);
            writer.WriteEndArray();
            writer.WriteBoolean("truncated", stdoutTruncated || stderrTruncated);
            writer.WriteNumber("durationMs", (long)(DateTime.UtcNow - started).TotalMilliseconds);
            writer.WriteString("shell", "powershell_noprofile_noninteractive");
            writer.WriteString("authority", "shell_process_exit_and_captured_output");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effectObserved: true);
    }

    // Lo que borra, mata, formatea, apaga o cambia la configuración del sistema
    // no se corre desde un pedido en lenguaje natural; las operaciones tipadas
    // del catálogo (papelera, procesos, energía) ya lo hacen con su
    // confirmación y su postlectura.
    internal static bool IsDestructive(string command)
    {
        string folded = command.ToLowerInvariant();
        return DestructiveRegex().IsMatch(folded);
    }

    [GeneratedRegex(
        @"(?:^|[\s;|&(])(?:rm|del|erase|rmdir|rd|remove-item|ri|rmi|remove-itemproperty|rp|format|diskpart|" +
        @"shutdown|restart-computer|stop-computer|logoff|stop-process|kill|taskkill|spps|reg|regedit|bcdedit|" +
        @"mkfs|dd|cipher|takeown|icacls|cacls|net\s+user|net\s+localgroup|clear-recyclebin|set-executionpolicy|" +
        @"invoke-expression|iex|start-process|saps|schtasks|sc|wmic|vssadmin|wevtutil|netsh\s+(?:advfirewall|interface)|" +
        @"set-mppreference|add-mppreference|new-itemproperty|set-itemproperty|remove-partition|clear-disk|initialize-disk|" +
        @"move-item|mv|move|ren|rename-item|rni|rename|robocopy\s+.*\s/(?:mir|purge)|del\s+/|rd\s+/|git\s+(?:push|reset\s+--hard|clean|checkout\s+--\s|branch\s+-d)|" +
        @"npm\s+(?:publish|unpublish)|pip\s+uninstall|winget\s+uninstall|choco\s+uninstall|curl\s+[^|]*\|\s*(?:sh|bash|iex|powershell)|" +
        @"invoke-webrequest[^|]*\|\s*iex)(?:$|[\s;|&)])",
        RegexOptions.CultureInvariant)]
    private static partial Regex DestructiveRegex();

    private static (string Text, bool Truncated) Bound(string text)
    {
        string normalized = text.Replace("\r\n", "\n");
        return normalized.Length <= MaximumOutputCharacters
            ? (normalized, false)
            : (normalized[..MaximumOutputCharacters], true);
    }

    private static string QuoteLiteral(string value) => "'" + value.Replace("'", "''") + "'";
}
