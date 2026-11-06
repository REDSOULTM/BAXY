using System.Text.Json;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Filesystem;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// Auditoría semántica 2026-09-20 (REOPEN1993, comandos; D11): «ejecuta ls»,
/// «ejecuta pytest», «corré git status» se corren de verdad en una consola
/// PowerShell sin perfil, con un plazo y una salida acotados, y el recibo trae
/// la salida tal cual para que el final la cite. BAXY Renew (2026-10-15): lo que
/// no sólo lee (escribe, borra, instala, envía, corre un programa) lo confirma
/// antes el kernel con el comando exacto (RiskPolicy.ShellMayChange); aquí ya no
/// hay una lista de comandos rechazados que dejaba pasar escrituras y envíos.
/// </summary>
internal sealed class ShellCommandAdapter : IExternalOperationAdapter
{
    internal static readonly TimeSpan CommandTimeout = TimeSpan.FromSeconds(60);
    internal const int MaximumOutputCharacters = 8 * 1024;

    // Round A: the console's exit code is the last native command's when it failed, else 1 when the last statement
    // failed (a cmdlet sets $? but leaves $LASTEXITCODE as it was, so «Get-Item <missing>; exit $LASTEXITCODE» exited
    // 0 and the receipt said succeeded:true). $? and not $Error: $Error keeps errors the command itself handled. A
    // native command that failed earlier still marks the run as failed, as the plain «exit $LASTEXITCODE» did.
    internal const string ExitTail = "; if ($LASTEXITCODE) { exit $LASTEXITCODE } elseif (-not $?) { exit 1 }";

    private readonly IExternalProcessRunner _runner;
    private readonly string _defaultWorkingDirectory;

    internal ShellCommandAdapter()
        // Decisión de adaptador (Fase 5, 2026-09-21; H0048 «ejecuta pytest»): sin carpeta
        // nombrada, el comando corre en una carpeta de trabajo propia y vacía del producto
        // (<datos>/shell-cwd), nunca en el perfil del usuario, donde «pytest» o «dir /s»
        // recorrerían y ejecutarían cosas ajenas. Una carpeta conocida se nombra en `cwd`.
        : this(new ExternalProcessRunner(killTree: true), DefaultWorkingDirectory())
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

    // «cwd» is an absolute path, or read as a file tool reads its path (PersonFolders.Place): a known folder, a folder
    // inside one («documents/proyecto»), or any other inside the person's home («BAXY-bench»), and never out of them.
    // Encargo 61 (banco de uso U45): file.write and filesystem.create.directory read «BAXY-bench» in the home folder and
    // this call refused it, so the model created a folder that was there or asked the person whether it existed.
    private static string? ResolveWorkingDirectory(string cwd)
    {
        string trimmed = cwd.Trim().Replace('/', Path.DirectorySeparatorChar);
        if (Path.IsPathFullyQualified(trimmed))
            return trimmed;
        return PersonFolders.Place(trimmed, PersonFolders.PathLabels("file.write"), PersonFolders.Path) is { } place
            ? Path.Combine(place.Root, place.Relative)
            : null;
    }

    // Encargo 61 (banco de uso U45, held-out): the model wrote the home of the file tools' example, and the code alone left it
    // telling the person that their folder did not exist (Anthropic, «Writing effective tools for agents»: error responses
    // that «clearly communicate specific and actionable improvements» rather than «opaque error codes»). Where it looked,
    // their home and, when the path named another place, the call with the folder's own name, after the fact as encargo 57
    // measured for a call redone. Measured: 23/35 → 32/35.
    private static ExternalCapabilityReceipt NoFolder(string operation, string command, string cwd, string? looked)
    {
        string said = cwd.Trim().Replace('/', Path.DirectorySeparatorChar).TrimEnd(Path.DirectorySeparatorChar);
        string where = looked ?? said;
        string home = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
        string name = Path.GetFileName(said);
        string next = $"nothing ran: there is no folder {where}; this person's home is {home}";
        if (name.Length > 0 && name != said && name is not ("." or ".."))
        {
            next += "; to run it in their folder of that name, call "
                + WireNames.Call(operation, new() { ["command"] = command, ["cwd"] = name });
        }

        return new ExternalCapabilityReceipt(operation, false, false, ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteString("cwd", where);
            writer.WriteString("next", next);
            writer.WriteEndObject();
        }), "shell_command_directory_not_found");
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

        string? workingDirectory = cwd is null ? _defaultWorkingDirectory : ResolveWorkingDirectory(cwd);
        if (workingDirectory is null || !Directory.Exists(workingDirectory))
            return NoFolder(operation, command, cwd!, workingDirectory);

        // La consola se coloca en la carpeta antes del comando, dentro de la misma
        // orden, para que el corredor no necesite un directorio de trabajo propio.
        string script = "Set-Location -LiteralPath " + QuoteLiteral(workingDirectory) + "; " + command + ExitTail;
        // Auditoría final 2: what ran is an effect only when the command may change something (the kernel's own reading
        // of it, RiskPolicy.ShellMayChange); a command that only reads changed nothing.
        bool mayChange = Baxy.Kernel.Policy.RiskPolicy.ShellMayChange(operation, arguments);
        var effectBoundary = new ExternalEffectBoundary();
        DateTime started = DateTime.UtcNow;
        ExternalProcessResult process;
        try
        {
            effectBoundary.Cross(cancellationToken);
            process = await _runner.RunAsync(
                "powershell.exe",
                ["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command",
                    PowerShellCommand.Utf8Output + script],
                CommandTimeout, cancellationToken).ConfigureAwait(false);
        }
        catch (TimeoutException)
        {
            // Ronda B: a command stopped at its deadline ran without anything observed of what it did: what it changed
            // before that is uncertain only when it may change something, like an overflow.
            return Stopped(operation, "shell_command_timeout", mayChange);
        }
        catch (ExternalProcessOutputTooLargeException)
        {
            // The command ran and wrote more than the runner keeps, and was stopped there: what it changed before that
            // is uncertain when it may change something.
            return Stopped(operation, "shell_command_output_too_large", mayChange);
        }
        catch (Exception exception) when (exception is IOException or System.ComponentModel.Win32Exception)
        {
            return effectBoundary.Failure(operation, "shell_command_not_started");
        }

        (string stdout, bool stdoutTruncated) = Bound(process.Output);
        (string stderr, bool stderrTruncated) = Bound(process.Error);
        // Auditoría final: the output goes once, as stdout; its lines are counted, not repeated beside it.
        int lineCount = stdout.Split('\n').Count(line => line.Trim().Length > 0);
        // A non-zero exit is a failure, with its output and error text.
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
            writer.WriteNumber("lineCount", lineCount);
            writer.WriteBoolean("truncated", stdoutTruncated || stderrTruncated);
            writer.WriteNumber("durationMs", (long)(DateTime.UtcNow - started).TotalMilliseconds);
            writer.WriteString("shell", "powershell_noprofile_noninteractive");
            writer.WriteString("authority", "shell_process_exit_and_captured_output");
            // A command that may change something ran and exited; nothing read back what it changed (round 2: said as a
            // fact of the result, not as a failure of the run).
            if (mayChange)
                writer.WriteBoolean("effectReadBack", false);
            writer.WriteEndObject();
        });
        return process.ExitCode == 0
            ? ExternalJson.Success(operation, result, effectObserved: false)
            : new ExternalCapabilityReceipt(operation, false, false, result, "shell_command_exit_nonzero")
            {
                EffectMayHaveOccurred = mayChange,
            };
    }

    private static (string Text, bool Truncated) Bound(string text)
    {
        string normalized = text.Replace("\r\n", "\n");
        return normalized.Length <= MaximumOutputCharacters
            ? (normalized, false)
            : (normalized[..MaximumOutputCharacters], true);
    }

    private static ExternalCapabilityReceipt Stopped(string operation, string errorCode, bool mayChange) =>
        new(operation, false, false, null, errorCode) { EffectMayHaveOccurred = mayChange };

    private static string QuoteLiteral(string value) => "'" + value.Replace("'", "''") + "'";
}
