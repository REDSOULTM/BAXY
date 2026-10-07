using System.Text.Json;

namespace Baxy.Providers.Windows.External;

internal sealed class WindowsDesktopInteractionAdapter : IExternalOperationAdapter
{
    private readonly IExternalProcessRunner _runner;
    private readonly string _folderScript;
    private readonly string _fileScript;
    private readonly string _keyPressScript;
    private readonly string _selectAllScript;
    private readonly IDesktopKeyboard _keyboard;

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
        string keyPressScript,
        IDesktopKeyboard? keyboard = null)
    {
        _runner = runner ?? throw new ArgumentNullException(nameof(runner));
        _folderScript = folderScript ?? throw new ArgumentNullException(nameof(folderScript));
        _fileScript = fileScript ?? throw new ArgumentNullException(nameof(fileScript));
        _selectAllScript = selectAllScript ?? throw new ArgumentNullException(nameof(selectAllScript));
        _keyPressScript = keyPressScript ?? throw new ArgumentNullException(nameof(keyPressScript));
        _keyboard = keyboard ?? new WindowsDesktopKeyboard();
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
        if (operation is "input.key.press" or "input.text.type")
            return await SendKeysAsync(operation, arguments, cancellationToken).ConfigureAwait(false);
        string script = operation switch
        {
            "clipboard.copy" => _keyPressScript,
            "clipboard.paste" => _keyPressScript,
            "filesystem.folder.open" => _folderScript,
            "filesystem.file.open.latest" => _fileScript,
            "input.keyboard.layout" => _keyPressScript,
            "input.keyboard.open" => _keyPressScript,
            "input.keyboard.status" => _keyPressScript,
            "input.pointer.control" => _keyPressScript,
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

    // The keys of input.key.press (ProductCatalog's enum) as the virtual keys pressed together. Motor de computer use
    // (CONTRATO_VISTA_ACCION.md §2): the shortcuts a person uses in any app; none closes a window or a process.
    private static readonly Dictionary<string, ushort[]> VirtualKeys = new(StringComparer.Ordinal)
    {
        ["alt_tab"] = [0x12, 0x09],
        ["arrow_down"] = [0x28],
        ["arrow_left"] = [0x25],
        ["arrow_right"] = [0x27],
        ["arrow_up"] = [0x26],
        ["backspace"] = [0x08],
        ["context_menu"] = [0x5D],
        ["control"] = [0x11],
        ["ctrl_a"] = [0x11, 0x41],
        ["ctrl_c"] = [0x11, 0x43],
        ["ctrl_f"] = [0x11, 0x46],
        ["ctrl_k"] = [0x11, 0x4B],
        // ctrl_l enfoca la barra de direcciones del navegador de delante.
        ["ctrl_l"] = [0x11, 0x4C],
        ["ctrl_shift_escape"] = [0x11, 0x10, 0x1B],
        ["ctrl_t"] = [0x11, 0x54],
        ["ctrl_v"] = [0x11, 0x56],
        ["ctrl_w"] = [0x11, 0x57],
        ["ctrl_z"] = [0x11, 0x5A],
        ["delete"] = [0x2E],
        ["end"] = [0x23],
        ["enter"] = [0x0D],
        ["escape"] = [0x1B],
        ["f5"] = [0x74],
        ["home"] = [0x24],
        ["page_down"] = [0x22],
        ["page_up"] = [0x21],
        ["shift"] = [0x10],
        ["space"] = [0x20],
        ["tab"] = [0x09],
        ["win"] = [0x5B],
    };

    private const int MaximumTypedText = 4096;

    /// <summary>
    /// A key or a text sent to the window in front by SendInput from this process: verified when Windows accepted
    /// every event, with the foreground read before and after for the receipt. Nothing is sent while nobody holds
    /// the foreground or when the native INPUT record does not have its native size.
    /// Safety review 2026-10-07: a computer-use step names its mission's window (<c>window</c>, the hwnd of its last
    /// view). That window is brought to the front and nothing is sent unless it holds it; a text stops the moment
    /// the window loses the front or the request is cancelled, and a text whose foreground process changed while it
    /// was typed is not verified. A mission's text carries no line break or tab (each would be a key of its own).
    /// </summary>
    private async ValueTask<ExternalCapabilityReceipt> SendKeysAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        bool typing = operation == "input.text.type";
        string? key = null;
        string text = string.Empty;
        ushort[] chord = [];
        nint window = 0;
        try
        {
            if (typing)
                text = ExternalJson.RequiredString(arguments, "text");
            else
                key = ExternalJson.RequiredString(arguments, "key");
            if (arguments.TryGetProperty("window", out JsonElement named) && named.ValueKind != JsonValueKind.Null)
            {
                if (named.ValueKind != JsonValueKind.Number || !named.TryGetInt64(out long handle) || handle <= 0)
                    throw new InvalidDataException("window");
                window = (nint)handle;
            }
        }
        catch (InvalidDataException)
        {
            return ExternalJson.FailureBeforeEffect(operation, "desktop_interaction_argument_invalid");
        }

        if ((typing && text.Length > MaximumTypedText) || (!typing && !VirtualKeys.TryGetValue(key!, out chord!))
            || (typing && window != 0 && text.Any(char.IsControl)))
            return ExternalJson.FailureBeforeEffect(operation, "desktop_interaction_argument_invalid");
        if (window != 0)
        {
            bool fronted;
            try
            {
                fronted = await _keyboard.FrontAsync(window, cancellationToken).ConfigureAwait(false);
            }
            catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
            {
                return ExternalJson.FailureBeforeEffect(operation, "desktop_interaction_adapter_failed");
            }

            if (!fronted)
                return ExternalJson.FailureBeforeEffect(operation, "input_window_not_in_front");
        }

        DesktopForeground before = _keyboard.Foreground();
        if (before.Window == 0 || _keyboard.InputSize != (IntPtr.Size == 8 ? 40 : 28))
            return ExternalJson.FailureBeforeEffect(operation, "key_press_sendinput_failed");

        var effectBoundary = new ExternalEffectBoundary();
        effectBoundary.Cross(cancellationToken);
        uint expected = typing ? (uint)text.Length * 2 : (uint)chord.Length * 2;
        bool interrupted = false;
        uint accepted = typing
            ? _keyboard.TypeText(text, () =>
            {
                bool stays = !cancellationToken.IsCancellationRequested
                    && (window != 0 ? _keyboard.Holds(window) : _keyboard.Foreground().ProcessId == before.ProcessId);
                interrupted |= !stays;
                return stays;
            })
            : _keyboard.PressChord(chord);
        bool verified = accepted == expected;
        int lastError = verified ? 0 : _keyboard.LastError();
        bool effect = accepted > 0;
        try
        {
            await _keyboard.SettleAsync(cancellationToken).ConfigureAwait(false);
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            return effectBoundary.Failure(operation, "desktop_interaction_adapter_failed", effect);
        }

        DesktopForeground after = _keyboard.Foreground();
        if (interrupted)
            return effect
                ? effectBoundary.Failure(operation, "input_window_changed", effect)
                : ExternalJson.FailureBeforeEffect(operation, "input_window_changed");
        // The text went whole, but another process took the front while it was typed: what it got is not proven.
        if (typing && after.ProcessId != before.ProcessId)
            return effectBoundary.Failure(operation, "input_window_changed", effect);
        if (!verified)
            return effectBoundary.Failure(operation, "input_effect_not_verified", effect);
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteBoolean("ok", true);
            writer.WriteBoolean("effectObserved", effect);
            writer.WriteString("action", typing ? "text" : "key");
            if (key is null)
                writer.WriteNull("key");
            else
                writer.WriteString("key", key);
            writer.WriteNumber("textLength", text.Length);
            writer.WriteNumber("acceptedEvents", accepted);
            writer.WriteNumber("expectedEvents", expected);
            writer.WriteNumber("inputSize", _keyboard.InputSize);
            writer.WriteNumber("lastWin32Error", lastError);
            writer.WriteNumber("foregroundProcessIdBefore", before.ProcessId);
            writer.WriteNumber("foregroundProcessIdAfter", after.ProcessId);
            writer.WriteString("foregroundTitleBefore", before.Title);
            writer.WriteString("authority", "win32_sendinput_return_count");
            writer.WriteNull("error");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effect);
    }
}
