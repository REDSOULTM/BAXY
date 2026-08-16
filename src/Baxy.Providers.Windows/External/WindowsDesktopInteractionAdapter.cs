using System.Text.Json;

namespace Baxy.Providers.Windows.External;

internal sealed class WindowsDesktopInteractionAdapter : IExternalOperationAdapter
{
    private readonly IExternalProcessRunner _runner;
    private readonly string _folderScript;
    private readonly string _fileScript;
    private readonly string _keyPressScript;
    private readonly string _selectAllScript;

    internal WindowsDesktopInteractionAdapter()
        : this(
            new ExternalProcessRunner(),
            Path.Combine(AppContext.BaseDirectory, "KnownFolderOpen.ps1"),
            Path.Combine(AppContext.BaseDirectory, "KnownFileOpen.ps1"),
            Path.Combine(AppContext.BaseDirectory, "DesktopSelectAll.ps1"),
            Path.Combine(AppContext.BaseDirectory, "DesktopKeyPress.ps1"))
    {
    }

    internal WindowsDesktopInteractionAdapter(
        IExternalProcessRunner runner,
        string folderScript,
        string selectAllScript)
        : this(
            runner,
            folderScript,
            Path.Combine(Path.GetDirectoryName(folderScript) ?? string.Empty, "KnownFileOpen.ps1"),
            selectAllScript,
            Path.Combine(Path.GetDirectoryName(folderScript) ?? string.Empty, "DesktopKeyPress.ps1"))
    {
    }

    internal WindowsDesktopInteractionAdapter(
        IExternalProcessRunner runner,
        string folderScript,
        string fileScript,
        string selectAllScript)
        : this(
            runner,
            folderScript,
            fileScript,
            selectAllScript,
            Path.Combine(Path.GetDirectoryName(folderScript) ?? string.Empty, "DesktopKeyPress.ps1"))
    {
    }

    internal WindowsDesktopInteractionAdapter(
        IExternalProcessRunner runner,
        string folderScript,
        string fileScript,
        string selectAllScript,
        string keyPressScript)
    {
        _runner = runner ?? throw new ArgumentNullException(nameof(runner));
        _folderScript = folderScript ?? throw new ArgumentNullException(nameof(folderScript));
        _fileScript = fileScript ?? throw new ArgumentNullException(nameof(fileScript));
        _selectAllScript = selectAllScript ?? throw new ArgumentNullException(nameof(selectAllScript));
        _keyPressScript = keyPressScript ?? throw new ArgumentNullException(nameof(keyPressScript));
    }

    public bool CanHandle(string operation) => operation is
        "clipboard.copy" or
        "clipboard.paste" or
        "filesystem.folder.open" or "filesystem.file.open.latest" or
        "input.key.press" or "input.keyboard.layout" or "input.keyboard.open" or
        "input.keyboard.status" or
        "input.pointer.control" or "input.select.all" or
        "input.text.type";

    public async ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        string script = operation switch
        {
            "clipboard.copy" => _keyPressScript,
            "clipboard.paste" => _keyPressScript,
            "filesystem.folder.open" => _folderScript,
            "filesystem.file.open.latest" => _fileScript,
            "input.key.press" => _keyPressScript,
            "input.keyboard.layout" => _keyPressScript,
            "input.keyboard.open" => _keyPressScript,
            "input.keyboard.status" => _keyPressScript,
            "input.pointer.control" => _keyPressScript,
            "input.text.type" => _keyPressScript,
            _ => _selectAllScript,
        };
        if (!File.Exists(script))
            return ExternalJson.Failure(operation, "desktop_interaction_script_missing");
        var command = new List<string> { "-NoProfile", "-NonInteractive", "-STA", "-File", script };
        try
        {
            if (operation == "clipboard.copy")
                command.Add("-CopySelection");
            else if (operation == "clipboard.paste")
                command.Add("-PasteClipboard");
            else if (operation is "filesystem.folder.open" or "filesystem.file.open.latest")
                command.Add(ExternalJson.RequiredString(arguments, "folder"));
            else if (operation == "input.key.press")
                command.Add(ExternalJson.RequiredString(arguments, "key"));
            else if (operation == "input.keyboard.layout")
            {
                command.Add("-Layout");
                command.Add(ExternalJson.RequiredString(arguments, "language"));
            }
            else if (operation == "input.keyboard.open")
                command.Add("-OpenOnScreenKeyboard");
            else if (operation == "input.keyboard.status")
                command.Add("-ReadKeyboardLayout");
            else if (operation == "input.pointer.control")
            {
                command.Add("-PointerAction");
                command.Add(ExternalJson.RequiredString(arguments, "action"));
            }
            else if (operation == "input.text.type")
            {
                command.Add("-TextBase64");
                command.Add(Convert.ToBase64String(System.Text.Encoding.UTF8.GetBytes(
                    ExternalJson.RequiredString(arguments, "text"))));
            }
        }
        catch (InvalidDataException)
        {
            return ExternalJson.FailureBeforeEffect(
                operation, "desktop_interaction_argument_invalid");
        }
        var effectBoundary = new ExternalEffectBoundary();
        try
        {
            if (operation != "input.keyboard.status")
            {
                effectBoundary.Cross(cancellationToken);
            }
            ExternalProcessResult process = await _runner.RunAsync(
                "powershell.exe", command, TimeSpan.FromSeconds(15), cancellationToken)
                .ConfigureAwait(false);
            string? line = process.Output.Split(['\r', '\n'], StringSplitOptions.RemoveEmptyEntries)
                .LastOrDefault();
            if (line is null)
                return effectBoundary.Failure(operation, "desktop_interaction_no_receipt");
            using JsonDocument response = JsonDocument.Parse(line);
            JsonElement root = response.RootElement;
            bool effect = root.TryGetProperty("effectObserved", out JsonElement observed)
                && observed.ValueKind == JsonValueKind.True;
            if (!root.TryGetProperty("ok", out JsonElement ok) || ok.ValueKind != JsonValueKind.True)
            {
                string error = root.TryGetProperty("error", out JsonElement errorValue)
                    ? errorValue.GetString() ?? "desktop_interaction_not_verified"
                    : "desktop_interaction_not_verified";
                return effectBoundary.Failure(operation, error, effect);
            }
            return ExternalJson.Success(operation, root.Clone(), effect);
        }
        catch (OperationCanceledException) when (
            cancellationToken.IsCancellationRequested && effectBoundary.WasCrossed)
        {
            return effectBoundary.Failure(operation, "desktop_interaction_adapter_failed");
        }
        catch (Exception exception) when (exception is IOException or JsonException or TimeoutException)
        {
            return effectBoundary.Failure(operation, "desktop_interaction_adapter_failed");
        }
    }
}
