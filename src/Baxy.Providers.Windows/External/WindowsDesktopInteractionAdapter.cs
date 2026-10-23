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
    private readonly IViewedFields? _fields;
    private readonly WindowsTextDelivery? _delivery;
    private readonly Func<string?>? _clipboardText;

    // Revision 1 of r24b (v1, measured on a store: SetValue «Spotify» into its search box without the keyboard's focus,
    // then an Enter that went to the control the window had focused and never searched): the field a verified SetValue
    // wrote while the keyboard's focus stayed elsewhere, by its window's identity. The next key to that window goes
    // only after UI Automation put the focus there (FocusAsync), and its receipt says where («focusAt»).
    // Revision 3 of r24b (finding 3): it belongs to the act right after the value was set, and to nothing later: that
    // act takes it whatever comes of it (a focus that failed included), a click in between («Clicks» of the viewed
    // fields) voids it, and it lasts one step's time at most (a later mission never inherits it).
    private (WindowIdentity Window, string ControlId, long Clicks, long SetAt)? _unfocusedValue;

    // The field the act now running owes the keyboard's focus to (taken from _unfocusedValue as the act starts).
    private (WindowIdentity Window, string ControlId)? _focusOwed;

    // Revision 3 of r24b: how long a value set without the keyboard's focus waits for the key after it (a step's look
    // and decision); the clock is a seam for the tests.
    internal const long PendingFocusLifetimeMilliseconds = 90_000;

    internal Func<long> Ticks { get; init; } = static () => Environment.TickCount64;

    /// <summary>The product's adapter: a mission's key or text goes to its window by window messages or UI Automation
    /// when its field takes them (<paramref name="fields"/>: the last view's fields), else by the keyboard.</summary>
    // Renew al máximo (w5): the key script (copy, paste, the pointer, the layout) runs in one persistent PowerShell
    // (PowerShellScriptWorker): a powershell.exe started cold and its Add-Type compiled cost 1.0-1.9 s of every copy and
    // paste on the notebook. The other scripts go on in their own process.
    internal WindowsDesktopInteractionAdapter(IViewedFields? fields)
        : this(
            KeyScriptRunner(Path.Combine(AppContext.BaseDirectory, "DesktopKeyPress.ps1")),
            Path.Combine(AppContext.BaseDirectory, "KnownFolderOpen.ps1"),
            Path.Combine(AppContext.BaseDirectory, "KnownFileOpen.ps1"),
            Path.Combine(AppContext.BaseDirectory, "DesktopSelectAll.ps1"),
            Path.Combine(AppContext.BaseDirectory, "DesktopKeyPress.ps1"),
            fields: fields,
            messages: new WindowsFieldMessages(),
            clipboardText: ClipboardText)
    {
        ChordLease = ForegroundLease.Shared;
    }

    /// <summary>
    /// v3 point 0, fix 3: the chords the helper scripts send by SendInput to the window in front (copy, paste, select
    /// all) wait for the person's pause and go in one helper burst of this lease; null runs them directly (the test
    /// seams, whose runners are fakes). The pointer actions are not leased: moving or clicking the pointer is the act
    /// the person asked for, and giving the cursor back would undo it.
    /// </summary>
    internal IForegroundLease? ChordLease { get; init; }

    /// <summary>The product's runner of the helper scripts: the key script in its persistent PowerShell, the rest each in
    /// a process of its own.</summary>
    internal static IExternalProcessRunner KeyScriptRunner(string keyPressScript) => new PowerShellScriptWorker(keyPressScript);

    /// <summary>
    /// Renew al máximo (rendimiento): the persistent UI Automation worker filesystem.folder.open's script runs in
    /// (<see cref="UiaWorkerScript"/>, its arguments by position); null starts a PowerShell for it, as before (the test
    /// seams' fake runners).
    /// </summary>
    internal IUiaWorker? Scripts { get; init; }

    internal WindowsDesktopInteractionAdapter(
        IExternalProcessRunner runner,
        string folderScript,
        string fileScript,
        string selectAllScript,
        string keyPressScript,
        IDesktopKeyboard? keyboard = null,
        IViewedFields? fields = null,
        IFieldMessages? messages = null,
        Func<string?>? clipboardText = null)
    {
        _runner = runner ?? throw new ArgumentNullException(nameof(runner));
        _folderScript = folderScript ?? throw new ArgumentNullException(nameof(folderScript));
        _fileScript = fileScript ?? throw new ArgumentNullException(nameof(fileScript));
        _selectAllScript = selectAllScript ?? throw new ArgumentNullException(nameof(selectAllScript));
        _keyPressScript = keyPressScript ?? throw new ArgumentNullException(nameof(keyPressScript));
        _keyboard = keyboard ?? new WindowsDesktopKeyboard();
        _fields = fields;
        // Without window messages (a test seam that names none) every key and text goes by the keyboard.
        _delivery = messages is null ? null : new WindowsTextDelivery(messages);
        _clipboardText = clipboardText;
    }

    /// <summary>The clipboard's whole Unicode text as BAXY reads it; null when it holds none, cannot be read or is
    /// longer than a read takes (a part pasted would not be what the person copied).</summary>
    private static string? ClipboardText()
    {
        try
        {
            Clipboard.ClipboardTextSnapshot read = new Clipboard.Win32ClipboardPlatform()
                .ReadText(Clipboard.WindowsClipboardProvider.MaximumCharacters);
            return read.Truncated ? null : read.Text;
        }
        catch (Clipboard.ClipboardProviderException)
        {
            return null;
        }
    }

    /// <summary>The kind of window a key lands on (K-2 refinada), for a declared text field's Enter.</summary>
    internal IKeyWindowReader KeyWindows { get; init; } = new KeyWindowReader();

    // Auditoría del núcleo 2026-10-23 (DeclaredTextFieldPress): a key press that declares a text field is read before it
    // goes unasked; nothing else this adapter does is.
    public bool PreflightMayRaise(string operation, JsonElement arguments) =>
        DeclaredTextFieldPress.Applies(operation, arguments);

    public async ValueTask<ExternalCapabilityReceipt?> PreflightAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        if (!DeclaredTextFieldPress.Applies(operation, arguments))
            return null;
        nint window = NamedWindow(arguments);
        FocusRead? focus = null;
        if (_fields is not null)
        {
            using JsonDocument? answer = await _fields.FocusKindAsync(window, cancellationToken).ConfigureAwait(false);
            focus = DeclaredTextFieldPress.Read(answer);
        }

        KeyWindowKind kind = KeyWindows.KindOf(window == 0 ? null : window);
        return DeclaredTextFieldPress.NeedsYes(arguments, focus, kind)
            ? new ExternalCapabilityReceipt(operation, false, false, null, null) { NeedsConfirmation = true }
            : null;
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
        _focusOwed = TakeUnfocusedValue();
        try
        {
            ExternalCapabilityReceipt receipt = await InvokeActAsync(operation, arguments, cancellationToken).ConfigureAwait(false);
            // Renew al máximo (7.1): a text or a key completed in a named window carries the view of that window after
            // it (the visible controls' adapter reads it again; it becomes the last view); nothing when it was not read.
            if (operation is "input.text.type" or "input.key.press" && _fields is not null
                && receipt is { Verified: true, ErrorCode: null, EffectObserved: true }
                && NamedWindow(arguments) is nint window and not 0
                && await _fields.AfterActAsync(window, cancellationToken).ConfigureAwait(false) is { } after)
                receipt = WindowsVisibleControlAdapter.WithAfter(receipt, after);
            return receipt;
        }
        finally
        {
            _focusOwed = null;
        }
    }

    // The window a step names («window»); 0 when it names none or not as a handle.
    private static nint NamedWindow(JsonElement arguments) =>
        arguments.ValueKind == JsonValueKind.Object && arguments.TryGetProperty("window", out JsonElement named)
        && named.ValueKind == JsonValueKind.Number && named.TryGetInt64(out long handle) && handle > 0
            ? (nint)handle
            : 0;

    // Revision 3 of r24b (finding 3): the pending focus, taken by the act that asks for it; null when a click came in
    // between or a step's time went by.
    private (WindowIdentity Window, string ControlId)? TakeUnfocusedValue()
    {
        (WindowIdentity Window, string ControlId, long Clicks, long SetAt)? pending = _unfocusedValue;
        _unfocusedValue = null;
        return pending is { } value && value.Clicks == (_fields?.Clicks ?? 0)
            && Ticks() - value.SetAt is >= 0 and <= PendingFocusLifetimeMilliseconds
                ? (value.Window, value.ControlId)
                : null;
    }

    private async ValueTask<ExternalCapabilityReceipt> InvokeActAsync(
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
        // The folder script's parameters by position (Folder, Subdirectory), as the worker's runspace takes them.
        var positional = new List<string>();
        try
        {
            if (operation == "clipboard.copy")
                command.Add("-CopySelection");
            else if (operation == "clipboard.paste")
                command.Add("-PasteClipboard");
            else if (operation is "filesystem.folder.open" or "filesystem.file.open.latest")
            {
                command.Add(ExternalJson.RequiredString(arguments, "folder"));
                positional.Add(command[^1]);
                if (operation == "filesystem.folder.open"
                    && arguments.TryGetProperty("subdirectory", out JsonElement subdirectory)
                    && subdirectory.ValueKind == JsonValueKind.String
                    && !string.IsNullOrWhiteSpace(subdirectory.GetString()))
                {
                    command.Add("-Subdirectory");
                    command.Add(subdirectory.GetString()!);
                    positional.Add(command[^1]);
                }
            }
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
        IInputBurst? burst = operation is "clipboard.copy" or "clipboard.paste" or "input.select.all"
            ? await LeasedInput.HelperBurstAsync(ChordLease, cancellationToken).ConfigureAwait(false)
            : null;
        if (burst?.Refusal is string refusal)
        {
            _ = burst.Restore();
            return ExternalJson.FailureBeforeEffect(operation, refusal);
        }

        var effectBoundary = new ExternalEffectBoundary();
        try
        {
            if (operation != "input.keyboard.status")
            {
                effectBoundary.Cross(cancellationToken);
            }
            // Renew al máximo (rendimiento): the folder's script runs in the worker, already started, with the same
            // budget; the PowerShell started cold for it cost a few hundred ms of every opening.
            (ExternalProcessResult? watched, bool interrupted) = await LeasedInput.WatchHelperAsync(
                burst,
                run => operation == "filesystem.folder.open" && Scripts is { } worker
                    ? UiaWorkerScript.RunAsync(
                        worker, File.ReadAllText(script), positional, TimeSpan.FromSeconds(15), run)
                    : _runner.RunAsync("powershell.exe", command, TimeSpan.FromSeconds(15), run),
                cancellationToken).ConfigureAwait(false);
            if (interrupted || watched is not { } process)
                return effectBoundary.Failure(operation, LeasedInput.Interrupted, true);
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
                // Ronda B: DesktopKeyPress.ps1 stopped by a check before any input (no window in front, an empty
                // clipboard, no on-screen keyboard) sent nothing: its own cause, before the effect.
                if (!effect && root.TryGetProperty("beforeInput", out JsonElement beforeInput)
                    && beforeInput.ValueKind == JsonValueKind.True)
                    return ExternalJson.FailureBeforeEffect(operation, error);
                return effectBoundary.Failure(operation, error, effect);
            }
            // Ronda final: a layout already Spanish or an on-screen keyboard already shown is the state reached
            // (changed:false), never a change this call made.
            if (root.TryGetProperty("alreadyReached", out JsonElement reached) && reached.ValueKind == JsonValueKind.True)
                return ExternalJson.Switched(operation, root.Clone(), effectObserved: false);
            // Ronda final: a paste, a click or a scroll is what SendInput accepted, as the keyboard's (CU12): delivered,
            // not an effect seen (nothing reads what the window did with it).
            bool deliveredOnly = operation == "clipboard.paste"
                || (operation == "input.pointer.control"
                    && !(root.TryGetProperty("pointerAction", out JsonElement pointer)
                        && pointer.ValueKind == JsonValueKind.String && pointer.GetString() == "move_center"));
            return ExternalJson.Success(operation, deliveredOnly
                ? AsDelivered(root, operation == "clipboard.paste" ? PastedInto(root) : null)
                : root.Clone(), effect);
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
        finally
        {
            _ = burst?.Restore();
        }
    }

    // The keys of input.key.press (ProductCatalog's enum) as the virtual keys pressed together. Motor de computer use
    // (CONTRATO_VISTA_ACCION.md §2): the shortcuts a person uses in any app. None ends a process; ctrl_w closes a tab
    // and, in many applications, the window, so it asks first (RiskPolicy.MayCloseAWindow, work_loss).
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
        ["ctrl_h"] = [0x11, 0x48],
        ["ctrl_k"] = [0x11, 0x4B],
        // ctrl_l enfoca la barra de direcciones del navegador de delante.
        ["ctrl_l"] = [0x11, 0x4C],
        ["ctrl_o"] = [0x11, 0x4F],
        ["ctrl_s"] = [0x11, 0x53],
        ["ctrl_shift_escape"] = [0x11, 0x10, 0x1B],
        ["ctrl_shift_s"] = [0x11, 0x10, 0x53],
        ["ctrl_t"] = [0x11, 0x54],
        ["ctrl_v"] = [0x11, 0x56],
        ["ctrl_w"] = [0x11, 0x57],
        ["ctrl_x"] = [0x11, 0x58],
        ["ctrl_z"] = [0x11, 0x5A],
        ["delete"] = [0x2E],
        ["end"] = [0x23],
        ["enter"] = [0x0D],
        ["escape"] = [0x1B],
        ["f10"] = [0x79],
        ["f5"] = [0x74],
        ["home"] = [0x24],
        ["page_down"] = [0x22],
        ["page_up"] = [0x21],
        ["shift"] = [0x10],
        // Shift+F10: the context menu of the focused control, where VK_APPS is missing from the keyboard.
        ["shift_f10"] = [0x10, 0x79],
        ["space"] = [0x20],
        ["tab"] = [0x09],
        ["win"] = [0x5B],
    };

    private const int MaximumTypedText = 4096;

    // Renew al máximo (B-CU-4): how long one act may type, from its start and counting the person's pauses it waits
    // for. The App waits 30 s for a step and 70 s more before it ends the Core, and 4096 characters at the keyboard's
    // pace (35 ms) take about 145 s: the Core was ended in the middle, the front never given back, and the text asked
    // again typed its beginning twice. At this budget the text stops, the front goes back and the receipt says how much
    // went in (input_text_time_exhausted, charactersTyped); a last wait for the person's pause (8 s at most) and the
    // read-back stay under 80 s.
    internal const long TypingBudgetMs = 70_000;

    // The characters a burst types when the person's input cannot be told apart from BAXY's (no Raw Input).
    internal const int BlindBurstCharacters = 8;

    // BAXY Renew al máximo (E017): how long a typed character waits for the marked edit control to have taken the ones
    // sent before it (polls of its length, apart): 300 ms at most, once; past it the rest go at the keyboard's pace.
    private const int TakenPolls = 60;
    private const int TakenPollMs = 5;

    /// <summary>
    /// A key or a text sent to the window in front by SendInput from this process: verified when Windows accepted
    /// every event, with the foreground read before and after for the receipt, which names the window the keys were
    /// sent to (<c>sentTo</c>). BAXY Renew (notebook), F004: a text with no window named is verified only when it is
    /// read back (<c>readBack</c>) in the edit control that had the keyboard's focus of the window in front (FT/proveedores
    /// goal (E2): or, in a document that is no edit control, in the paragraph at its caret read by UI Automation); otherwise
    /// its keys went in and what they wrote is not known (<c>input_text_not_read_back</c>, its effect possible).
    /// Nothing is sent while nobody holds the foreground or when the native INPUT record does not have its native size.
    /// Safety review 2026-10-07: a computer-use step names its mission's window (<c>window</c>, the hwnd of its last
    /// view), and its key or text is delivered to that window or nowhere. Goal v3 (point 0, fix 1): «bound» means the
    /// delivery is aimed at that window (its hwnd, process and process creation time, checked before every send), not
    /// that it holds the front. First without keyboard or foreground (<see cref="DeliverToWindowAsync"/>): a text to
    /// the field the step names (<c>index</c>, of the last view) or to the window's own focus, a single key to a
    /// classic control. Only what no message reaches (a chord, a field drawn by Chromium or XAML without a writable
    /// value) goes by the keyboard: the window is brought to the front and nothing is sent unless it holds it; a text
    /// stops the moment the window loses the front or the request is cancelled, and a text whose foreground process
    /// changed while it was typed is not verified. A text carries no line break or tab (each would be a key of its
    /// own).
    /// Companion rule (GOAL_COMPUTER_USE_V3 point 0, fix 3): on the keyboard path the mission's window is brought to
    /// the front only inside a burst of the foreground lease, after a pause of the person; the keys stop at the
    /// person's first input, and the window in front and the cursor are given back afterwards (the receipt says
    /// <c>waitedMs</c> and <c>restored</c>). A person who does not pause gets nothing sent: <c>input_user_not_paused</c>.
    /// </summary>
    private async ValueTask<ExternalCapabilityReceipt> SendKeysAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        bool typing = operation == "input.text.type";
        long typingDeadline = Ticks() + TypingBudgetMs;
        string? key = null;
        string text = string.Empty;
        ushort[] chord = [];
        nint window = 0;
        int? index = null;
        bool replace = false;
        bool entry = false;
        bool openedApplication = arguments.ValueKind == JsonValueKind.Object
            && arguments.TryGetProperty(WindowsExternalCapabilityProvider.OpenedApplicationArgument, out JsonElement opened)
            && opened.ValueKind == JsonValueKind.True;
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

            if (typing && arguments.TryGetProperty("index", out JsonElement field) && field.ValueKind != JsonValueKind.Null)
            {
                if (field.ValueKind != JsonValueKind.Number || !field.TryGetInt32(out int position) || position < 0)
                    throw new InvalidDataException("index");
                index = position;
            }

            if (typing && arguments.TryGetProperty("replace", out JsonElement replacing) && replacing.ValueKind != JsonValueKind.Null)
            {
                if (replacing.ValueKind is not (JsonValueKind.True or JsonValueKind.False))
                    throw new InvalidDataException("replace");
                replace = replacing.ValueKind == JsonValueKind.True;
            }

            if (typing && arguments.TryGetProperty("entry", out JsonElement listed) && listed.ValueKind != JsonValueKind.Null)
            {
                if (listed.ValueKind is not (JsonValueKind.True or JsonValueKind.False))
                    throw new InvalidDataException("entry");
                entry = listed.ValueKind == JsonValueKind.True;
            }
        }
        catch (InvalidDataException)
        {
            return ExternalJson.FailureBeforeEffect(operation, "desktop_interaction_argument_invalid");
        }

        // A replaced value needs the field it replaces: the window's own focus may be a document.
        if (replace && index is null)
            return ExternalJson.FailureBeforeEffect(operation, "input_field_not_replaceable");
        // Review of combos-galerias (finding 1): an entry of a list is chosen only in that list, by pattern, never typed;
        // without its box (or without the field reader) nothing is sent.
        if (entry && (index is null || window == 0 || _delivery is null || _fields is null))
            return ExternalJson.FailureBeforeEffect(operation, "input_field_not_found");

        // A field (index) is named only inside a looked-at window. A text carries no control character, with or without
        // a window (auditoría final 2, fila 11): a line break or a tab is a key of its own, and an Enter that sends what
        // was written goes through input.key.press and its confirmation, never inside a text.
        if ((typing && text.Length > MaximumTypedText) || (!typing && !VirtualKeys.TryGetValue(key!, out chord!))
            || (typing && text.Any(char.IsControl)) || (index is not null && window == 0))
            return ExternalJson.FailureBeforeEffect(operation, "desktop_interaction_argument_invalid");
        if (window != 0 && _delivery is not null)
        {
            // Read before anything is sent: the receipt states the front as it was, not as the delivery left it.
            DesktopForeground frontBefore = _keyboard.Foreground();
            if (entry)
                return await EntryToWindowAsync(operation, text, window, index!.Value, frontBefore, cancellationToken)
                    .ConfigureAwait(false);
            ExternalCapabilityReceipt? delivered = await DeliverToWindowAsync(
                operation, key, text, chord, window, index, replace, frontBefore, cancellationToken).ConfigureAwait(false);
            if (delivered is not null)
                return delivered;
            // Review of cierre-de-subobjetivos r2 (finding 1): a replacement turned into an insertion inside the delivery
            // (a field read empty) holds only if its messages wrote it. Null means they did not (its window is no edit
            // control, or not of this window): «replace» is still asked and is refused below; the keyboard, whose focus
            // may be another control, never takes it.
        }

        // Replacing a value needs the field itself (its value or its edit control): the keyboard would add the text
        // to what is there, or select a whole document with Ctrl+A. Nothing is sent.
        if (replace)
            return ExternalJson.FailureBeforeEffect(operation, "input_field_not_replaceable");

        IInputBurst? burst = null;
        if (window != 0)
        {
            try
            {
                burst = await _keyboard.FrontAsync(window, cancellationToken)
                    .ConfigureAwait(false);
            }
            catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
            {
                return ExternalJson.FailureBeforeEffect(operation, "desktop_interaction_adapter_failed");
            }

            if (burst.Refusal is string refusal)
            {
                _ = burst.Restore();
                return ExternalJson.FailureBeforeEffect(operation, refusal);
            }
        }

        var bursts = new LeasedBursts(burst);
        try
        {
            return await SendInBurstAsync(operation, typing, key, text, chord, window, bursts, cancellationToken,
                    openedApplication, typingDeadline)
                .ConfigureAwait(false);
        }
        finally
        {
            _ = bursts.Restore();
        }
    }

    // The bursts one key or text took, one after another: the last one is restored at the end, each earlier one before
    // the next is asked for, and the receipt adds up their waits and says whether every one was given back.
    private sealed class LeasedBursts(IInputBurst? first)
    {
        private bool _restored = true;

        internal IInputBurst? Current { get; private set; } = first;

        internal long WaitedMs { get; private set; } = first?.WaitedMs ?? 0;

        internal bool Restore()
        {
            if (Current is { } burst)
                _restored &= burst.Restore();
            return _restored;
        }

        // The next burst, taken once the current one was given back (never before: its restore would hand the front
        // the next burst just took back to the person).
        internal void Next(IInputBurst burst)
        {
            Current = burst;
            WaitedMs += burst.WaitedMs;
        }
    }

    private async ValueTask<ExternalCapabilityReceipt> SendInBurstAsync(
        string operation,
        bool typing,
        string? key,
        string text,
        ushort[] chord,
        nint window,
        LeasedBursts bursts,
        CancellationToken cancellationToken,
        bool openedApplication = false,
        long typingDeadline = long.MaxValue)
    {
        DesktopForeground before = _keyboard.Foreground();
        if (before.Window == 0 || _keyboard.InputSize != (IntPtr.Size == 8 ? 40 : 28))
            return ExternalJson.FailureBeforeEffect(operation, "key_press_sendinput_failed");
        string sentToProcess = _keyboard.ProcessName(before.Window);
        // v3 point 0: something may take the front back between fronting the window and the press (the person, or an
        // application opened behind that Windows activated late): the key is checked against the window right before
        // it goes, never sent to whatever holds the front now.
        if (window != 0 && !_keyboard.Holds(window))
            return ExternalJson.FailureBeforeEffect(operation, "input_window_changed");

        var effectBoundary = new ExternalEffectBoundary();
        // FT/proveedores goal (review of receipts): Ctrl+C or Ctrl+X as a key press was told done by the count of keys
        // Windows accepted, while clipboard.copy checks the clipboard; with nothing selected nothing was copied.
        bool copies = !typing && key is "ctrl_c" or "ctrl_x";
        uint clipboardBefore = copies ? _keyboard.ClipboardSequence() : 0;
        effectBoundary.Cross(cancellationToken);
        uint expected = typing ? (uint)text.Length * 2 : (uint)chord.Length * 2;
        // The person touched the keyboard or the mouse between the pause and the first key: nothing goes.
        if (bursts.Current is { UserActed: true })
            return ExternalJson.FailureBeforeEffect(operation, "input_user_interrupted");
        bool interrupted = false;
        bool userActed = false;
        int pausesWaited = 0;
        string? refusedLater = null;
        bool outOfTime = false;
        // Renew al máximo (B-CU-4): the act's own budget (TypingBudgetMs) is spent: the text stops there.
        bool OutOfTime()
        {
            outOfTime |= Ticks() >= typingDeadline;
            interrupted |= outOfTime;
            return outOfTime;
        }

        // The characters KeepGoing let go (each call comes before one), for the field to be waited for (AwaitTaken).
        int letGo = 0;
        bool KeepGoing()
        {
            AwaitTaken(letGo);
            userActed |= bursts.Current is { UserActed: true };
            if (!userActed && OutOfTime())
                return false;
            bool stays = !cancellationToken.IsCancellationRequested
                && !userActed
                && (window != 0 ? _keyboard.Holds(window) : _keyboard.Foreground().ProcessId == before.ProcessId);
            interrupted |= !stays;
            if (stays)
                letGo++;
            return stays;
        }

        // BAXY Renew (notebook), F004 (a text typed with no window named went into the Calculator in front, and was told
        // verified because Windows accepted its events): what the focused edit control of the window in front holds is
        // marked before the first key, so the text can be read back there afterwards.
        // Review of E6: so is a text the provider sent to the application app.open just opened (now in front).
        // FT/proveedores goal (review of receipts): and a text for a named window (it holds the front: checked above):
        // the right window was sure, the right field was not (a browser's address bar), and it was told verified with
        // no read-back. Where neither mark nor caret can be read, the receipt still says only what Windows accepted
        // (heldToReadBack, below).
        bool readsBack = typing;
        TypedMark? mark = readsBack ? _delivery?.Mark(before.Window, text.Length) : null;
        // FT/proveedores goal (E2): a document that is no edit control (Word's «_WwG») has no Win32 mark, and its text
        // was never read back. Its paragraph at the caret is read by UI Automation instead, before the first key, of the
        // front's own process only.
        CaretText? caretBefore = readsBack && mark is null
            ? await CaretTextAsync(before, cancellationToken).ConfigureAwait(false)
            : null;
        // BAXY Renew al máximo (e2e E017, pc-lote-A-s1: «lista: pilas, cables» typed into a busy Notepad landed as «lista
        // ilas, cables», and the read-back rightly said not read back): an editor that reads each key when it gets to it
        // loses or repeats the keys sent before it took the earlier ones (measured on Windows 11 Notepad, see
        // WindowsDesktopKeyboard.TypeText), and a fixed pace is too fast for it while the machine is loaded. With a mark,
        // each character after the first waits (bounded) until the marked control took the ones sent before it, and the
        // read-back waits for the last; a control that does not take them within the bound (the keys went elsewhere, or
        // it rewrites what it takes) leaves the rest at the keyboard's pace, as before.
        bool pacedByField = mark is not null;
        void AwaitTaken(int sent)
        {
            if (!pacedByField || sent <= 0 || mark is not { } marked)
                return;
            for (int poll = 0; !_delivery!.Took(marked, sent, text.Length); poll++)
            {
                if (poll >= TakenPolls)
                {
                    pacedByField = false;
                    return;
                }

                Thread.Sleep(TakenPollMs);
            }
        }

        uint accepted = 0;
        string? focusAt = null;
        if (!typing)
        {
            // Revision 1 of r24b (v1): after a value set without the keyboard's focus, the key goes to that field or
            // nowhere: UI Automation puts the focus there (the window is in front now) and re-reads it.
            if (window != 0 && _delivery is not null && UnfocusedField(_delivery.Messages.Identity(window)) is string field)
            {
                // Ronda final 17 (regla 3): the focus was asked of the window: it may have moved, an effect either way.
                if (!await FocusedAsync(window, field, cancellationToken).ConfigureAwait(false))
                    return ExternalJson.FailureAfterEffect(operation, "input_field_not_focused");
                if (!_keyboard.Holds(window))
                    return ExternalJson.FailureAfterEffect(operation, "input_window_changed");
                focusAt = field;
            }

            accepted = _keyboard.PressChord(chord);
        }
        else if (window == 0)
        {
            accepted = _keyboard.TypeText(text, KeepGoing);
        }
        else
        {
            // A mission's text goes whole in the person's pause (r4a M1, c6: cut into bursts of 8 characters, the
            // next burst was asked for while the window still held the front and the previous one's restore then
            // gave it back to the person, so every text stopped at its 8th character). It is cut only where the
            // person acts. A key, a click or the wheel of theirs while the window held the front went into the
            // mission's field, mixed with the text (review of fable/cu-v3-rafaga): the text ends there, said as
            // interrupted with its effect, never verified. Only a bare move of the mouse leaves the field as it was:
            // the front goes back to them at once, and the rest waits for their next pause. A front they moved
            // elsewhere is theirs, and the window is not brought up again over it.
            // Safety review r10a: without Raw Input the person's input is not told apart from BAXY's and a burst never
            // stops for them, so the text goes in bursts of BlindBurstCharacters, each after a pause of the whole
            // session's input (BAXY's own keys included): a person who types meanwhile delays the rest instead of
            // having a whole text typed over them.
            int start = 0;
            while (start < text.Length)
            {
                int sent = 0;
                bool personActed = false;
                bool blindCut = false;
                bool KeepTyping()
                {
                    AwaitTaken(start + sent);
                    if (bursts.Current is { UserActed: true })
                    {
                        personActed = true;
                        return false;
                    }

                    if (OutOfTime())
                        return false;
                    if (bursts.Current is { TellsPerson: false } && sent >= BlindBurstCharacters)
                    {
                        blindCut = true;
                        return false;
                    }

                    bool stays = !cancellationToken.IsCancellationRequested && _keyboard.Holds(window);
                    interrupted |= !stays;
                    if (stays)
                        sent++;
                    return stays;
                }

                uint accepting = _keyboard.TypeText(text[start..], KeepTyping);
                accepted += accepting;
                start += sent;
                if (interrupted || accepting != (uint)sent * 2 || start >= text.Length || !(personActed || blindCut))
                    break;
                if ((personActed && bursts.Current is { UserReached: true }) || !_keyboard.Holds(window))
                {
                    userActed = true;
                    interrupted = true;
                    break;
                }

                // The person acted in the middle: their front first, then the rest after their next pause, while the
                // act's budget lasts.
                if (OutOfTime())
                    break;
                pausesWaited++;
                _ = bursts.Restore();
                IInputBurst next;
                try
                {
                    next = await _keyboard.FrontAsync(window, cancellationToken).ConfigureAwait(false);
                }
                catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
                {
                    interrupted = true;
                    break;
                }

                bursts.Next(next);
                if (next.Refusal is string refusal)
                {
                    refusedLater = refusal;
                    interrupted = true;
                    break;
                }

                if (window != 0 && !_keyboard.Holds(window))
                {
                    interrupted = true;
                    break;
                }
            }
        }
        bool verified = accepted == expected;
        int lastError = verified ? 0 : _keyboard.LastError();
        bool effect = accepted > 0;
        // A failure once the keys went still names the window they were sent to.
        ExternalCapabilityReceipt SentFailure(string errorCode) => effectBoundary.Failure(operation, errorCode, effect) with
        {
            Result = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                WriteSentTo(writer, before, sentToProcess);
                // FT/proveedores goal (review of receipts): how much of the text went in (each character is a key down
                // and up), so a retry does not type its beginning twice.
                if (typing)
                {
                    writer.WriteNumber("charactersTyped", Math.Min(text.Length, (int)(accepted / 2)));
                    writer.WriteNumber("charactersAsked", text.Length);
                }
                writer.WriteEndObject();
            }),
        };
        try
        {
            await _keyboard.SettleAsync(cancellationToken).ConfigureAwait(false);
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            return SentFailure("desktop_interaction_adapter_failed");
        }

        DesktopForeground after = _keyboard.Foreground();
        // Given back before the receipt, which says whether it was.
        bool? restored = bursts.Current is null ? null : bursts.Restore();
        string stopped = refusedLater
            ?? (userActed ? "input_user_interrupted" : outOfTime ? "input_text_time_exhausted" : "input_window_changed");
        if (interrupted)
            return effect
                ? SentFailure(stopped)
                : ExternalJson.FailureBeforeEffect(operation, stopped);
        // The text went whole, but another process took the front while it was typed: what it got is not proven.
        if (typing && after.ProcessId != before.ProcessId)
            return SentFailure("input_window_changed");
        if (!verified)
            return SentFailure("input_effect_not_verified");
        if (copies && clipboardBefore != 0)
        {
            bool copied = false;
            for (int attempt = 0; attempt < 10 && !copied; attempt++)
            {
                copied = _keyboard.ClipboardSequence() != clipboardBefore;
                if (!copied)
                    await Task.Delay(50, cancellationToken).ConfigureAwait(false);
            }

            if (!copied)
                return SentFailure("clipboard_not_changed");
        }
        // Rule 3: Windows accepting every event proves the keys went in, not that the text reached the field meant. A text
        // with no window named is verified by its read-back alone.
        AwaitTaken((int)(accepted / 2));
        bool editReadBack = mark is { } typedMark && _delivery!.ReadsBack(typedMark, text);
        // FT/proveedores goal (E2): the paragraph at the caret read again by UI Automation; a read that fails leaves
        // the text not read back, as before.
        (bool caretReadBack, bool caretBounded) = caretBefore is { } caret
            ? await CaretReadsBackAsync(before, caret, text, cancellationToken).ConfigureAwait(false)
            : (false, false);
        bool readBack = editReadBack || caretReadBack;
        // A named window's text is held to its read-back only where one could be taken (a mark or a caret read before
        // the first key); with no window named (F004) or for the opened application, the read-back is the proof.
        bool heldToReadBack = window == 0 || openedApplication || mark is not null || caretBefore is not null;
        string? unread = readsBack && heldToReadBack && !readBack ? "input_text_not_read_back" : null;
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteBoolean("ok", unread is null);
            // CU12 (auditoría final 2): what Windows accepted (SendInput's count), delivered to the window in front;
            // what the control did with it is read only for a text with no window named («readBack»).
            writer.WriteBoolean("delivered", effect);
            writer.WriteString("action", typing ? "text" : "key");
            if (key is null)
                writer.WriteNull("key");
            else
                writer.WriteString("key", key);
            writer.WriteNumber("textLength", text.Length);
            writer.WriteString("method", "keyboard");
            writer.WriteNumber("acceptedEvents", accepted);
            writer.WriteNumber("expectedEvents", expected);
            writer.WriteNumber("inputSize", _keyboard.InputSize);
            writer.WriteNumber("lastWin32Error", lastError);
            writer.WriteNumber("foregroundProcessIdBefore", before.ProcessId);
            writer.WriteNumber("foregroundProcessIdAfter", after.ProcessId);
            WriteSentTo(writer, before, sentToProcess);
            if (readsBack)
                writer.WriteBoolean("readBack", readBack);
            // FT/proveedores goal (E2): a paragraph read cut at its bound (CaretReadableText) proves nothing, and says so.
            if (caretBefore is not null)
                writer.WriteBoolean("readBackBounded", caretBounded);
            if (bursts.Current is not null)
            {
                writer.WriteNumber("waitedMs", bursts.WaitedMs);
                writer.WriteBoolean("restored", restored == true);
                // The times the person acted in the middle of the text and its rest waited for their next pause.
                if (pausesWaited > 0)
                    writer.WriteNumber("pausesWaited", pausesWaited);
            }

            // Revision 1 of r24b: the field the key went to, its focus put and re-read by UI Automation right before it.
            if (focusAt is not null)
                writer.WriteString("focusAt", focusAt);
            writer.WriteString("authority", focusAt is not null ? "uia_focus_reread_and_win32_sendinput"
                : editReadBack ? "win32_sendinput_and_edit_text_reread"
                : caretReadBack ? "win32_sendinput_and_uia_text_reread"
                : "win32_sendinput_return_count");
            if (unread is null)
                writer.WriteNull("error");
            else
                writer.WriteString("error", unread);
            if (typing && (window == 0 || openedApplication)
                && Infrastructure.ModelAids.On(Infrastructure.ModelAids.TypedTargetNext))
                writer.WriteString("next", TypedInto(before.Title, sentToProcess, window == 0, readBack));
            writer.WriteEndObject();
        });
        // A text with no window named whose read-back did not find it: its keys went in, what they wrote is unknown.
        return unread is null
            ? ExternalJson.Success(operation, result, effect)
            : new ExternalCapabilityReceipt(operation, effect, false, result, unread) { EffectMayHaveOccurred = true };
    }

    // The entries a combo's list showed, as the worker read them.
    private static IReadOnlyList<string> Entries(JsonElement root) =>
        root.TryGetProperty("entries", out JsonElement entries) && entries.ValueKind == JsonValueKind.Array
            ? [.. entries.EnumerateArray().Where(entry => entry.ValueKind == JsonValueKind.String)
                .Select(entry => entry.GetString()!)]
            : [];

    // Renew al máximo (w5, F004): with sentTo «Calculadora» the reply still spoke of the Notepad the person named («no
    // pude comprobar que escribiste hola en el Bloc de notas») and of a focus change never tried. The same fact as a
    // sentence: the one window the text went into, and that nothing was opened or brought up for it.
    internal static string TypedInto(string title, string process, bool front, bool readBack)
    {
        string named = string.IsNullOrWhiteSpace(title) ? process : $"{title} ({process})";
        string where = front
            ? $"the text went by the keyboard into the window in front, of {named}; no other application received it, "
              + "and no application was opened or brought to the front for it"
            : $"the text went by the keyboard into the window of {named}, the application just opened; no other "
              + "application received it";
        return readBack ? where : where + "; it was not read back there";
    }

    // The window in front when the keys were sent, which took them (F004: the Calculator, not the Notepad), by its title
    // and the program a view names it by, read before the first key.
    private static void WriteSentTo(Utf8JsonWriter writer, DesktopForeground before, string process)
    {
        writer.WriteStartObject("sentTo");
        writer.WriteString("title", before.Title);
        writer.WriteString("process", process);
        writer.WriteEndObject();
    }

    // The field a value was set into without the keyboard's focus, when it is of this same window (same process and
    // creation); null otherwise.
    private string? UnfocusedField(WindowIdentity identity) =>
        _focusOwed is { } owed && identity.Alive && owed.Window == identity ? owed.ControlId : null;

    // Whether UI Automation put the keyboard's focus on the field (the worker's «focus», re-read).
    private async ValueTask<bool> FocusedAsync(nint window, string controlId, CancellationToken cancellationToken)
    {
        if (_fields is null)
            return false;
        JsonDocument? answer;
        try
        {
            answer = await _fields.FocusAsync(window, controlId, cancellationToken).ConfigureAwait(false);
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            return false;
        }

        if (answer is null)
            return false;
        using (answer)
        {
            JsonElement root = answer.RootElement;
            return root.TryGetProperty("ok", out JsonElement ok) && ok.ValueKind == JsonValueKind.True
                && root.TryGetProperty("focused", out JsonElement focused) && focused.ValueKind == JsonValueKind.True;
        }
    }

    // FT/proveedores goal (E2): how many times the paragraph at the caret is read after the text, a settle apart (the
    // document may take the last keys a moment after Windows accepted them).
    private const int CaretRereads = 3;

    // FT/proveedores goal (E2): the paragraph at the caret of the window in front, read by UI Automation (the worker's
    // «textcaret»); null when nothing answers, the read failed, or it answered for any process but the front's.
    private async ValueTask<CaretText?> CaretTextAsync(DesktopForeground front, CancellationToken cancellationToken)
    {
        if (_fields is null || front.Window == 0 || front.ProcessId <= 0)
            return null;
        JsonDocument? answer;
        try
        {
            answer = await _fields.CaretTextAsync(
                front.Window, front.ProcessId, WindowsTextDelivery.CaretReadableText, cancellationToken).ConfigureAwait(false);
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            return null;
        }

        if (answer is null)
            return null;
        using (answer)
        {
            JsonElement root = answer.RootElement;
            if (root.ValueKind != JsonValueKind.Object
                || !root.TryGetProperty("ok", out JsonElement ok) || ok.ValueKind != JsonValueKind.True
                || !root.TryGetProperty("processId", out JsonElement process) || process.ValueKind != JsonValueKind.Number
                || !process.TryGetInt32(out int processId)
                || processId != front.ProcessId
                || !root.TryGetProperty("text", out JsonElement read) || read.ValueKind != JsonValueKind.String
                || !root.TryGetProperty("unit", out JsonElement unit) || unit.ValueKind != JsonValueKind.String
                || !root.TryGetProperty("bounded", out JsonElement bounded)
                || bounded.ValueKind is not (JsonValueKind.True or JsonValueKind.False))
                return null;
            string text = read.GetString()!;
            // A read longer than its bound is not one this side asked for: it is taken as cut, never as whole.
            bool cut = bounded.ValueKind == JsonValueKind.True || text.Length > WindowsTextDelivery.CaretReadableText;
            int selection = root.TryGetProperty("selectionLength", out JsonElement selected)
                && selected.ValueKind == JsonValueKind.Number && selected.TryGetInt32(out int length) ? length : -1;
            return new CaretText(text, unit.GetString()!, cut, selection);
        }
    }

    // FT/proveedores goal (E2): whether the paragraph at the caret, read again, holds the typed text
    // (WindowsTextDelivery.CaretHolds), and whether a read was cut at its bound (the receipt says so).
    private async ValueTask<(bool ReadBack, bool Bounded)> CaretReadsBackAsync(
        DesktopForeground front, CaretText before, string text, CancellationToken cancellationToken)
    {
        // A read cut before, or a selection the text replaced: no read after can prove it.
        if (before.Bounded || before.SelectionLength != 0)
            return (false, before.Bounded);
        bool bounded = false;
        for (int read = 0; read < CaretRereads && !bounded; read++)
        {
            if (read > 0)
            {
                try
                {
                    await _keyboard.SettleAsync(cancellationToken).ConfigureAwait(false);
                }
                catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
                {
                    break;
                }
            }

            if (await CaretTextAsync(front, cancellationToken).ConfigureAwait(false) is not { } after)
                break;
            bounded |= after.Bounded;
            if (WindowsTextDelivery.CaretHolds(before, after, text))
                return (true, bounded);
        }

        return (false, bounded);
    }

    /// <summary>
    /// The key or text of a mission's step delivered to its window without keyboard or foreground; null when no
    /// message reaches it and the keyboard must (a chord, a key outside a classic control, a field without a writable
    /// value nor an edit control's window). A text goes to the field the step names (its <c>index</c> in the last
    /// view, which must be of this window): UI Automation's SetValue where replacing is the same as typing, else
    /// window messages to its edit control. Without a field, to the window's own focus when it is an edit control.
    /// A field that says it is read-only, a password or disabled gets nothing by any path (input_field_not_writable).
    /// A replacement asked for a field the worker read empty (its value, length 0) that has a window of its own is an
    /// insertion through that window's messages only: when they do not write it (null), the caller still holds the
    /// replacement and refuses it. Without that window the replacement stays refused (the keyboard's focus may be
    /// another control).
    /// </summary>
    private async ValueTask<ExternalCapabilityReceipt?> DeliverToWindowAsync(
        string operation,
        string? key,
        string text,
        ushort[] chord,
        nint window,
        int? index,
        bool replace,
        DesktopForeground frontBefore,
        CancellationToken cancellationToken)
    {
        WindowsTextDelivery delivery = _delivery!;
        WindowIdentity identity = delivery.Messages.Identity(window);
        if (!identity.Alive)
            return ExternalJson.FailureBeforeEffect(operation, "input_window_not_found");
        if (key == "ctrl_v")
            return await PasteToWindowAsync(operation, identity, frontBefore, cancellationToken).ConfigureAwait(false);
        if (key is not null)
        {
            // Revision 1 of r24b: the window's own focus is not the field the value was set into: the keyboard path
            // focuses it first.
            if (!WindowsTextDelivery.IsPostable(key) || chord.Length != 1 || UnfocusedField(identity) is not null)
                return null;
            nint focus = delivery.Messages.FocusOf(window);
            FieldDelivery? pressed = focus == 0 ? null : delivery.Press(identity, focus, key, chord[0]);
            return pressed is { } done
                ? FieldReceipt(operation, key, text, identity, frontBefore, done)
                : null;
        }

        nint field;
        // What the worker's front net saw while it read or wrote the field (r4a M1): part of the receipt.
        UiaFrontReport? keeper = null;
        // r25: a named field its value and its messages did not reach takes the keyboard only when it has its focus.
        bool fieldFocused = false, insertion = index is not null && !replace;
        if (index is int position)
        {
            if (_fields is null || !_fields.TryViewedField(position, out nint viewed, out string controlId) || viewed != window)
                return ExternalJson.FailureBeforeEffect(operation, "visible_control_identity_stale");
            var effectBoundary = new ExternalEffectBoundary();
            JsonDocument? answer;
            try
            {
                effectBoundary.Cross(cancellationToken);
                answer = await _fields.FieldAsync(window, controlId, text, replace, cancellationToken).ConfigureAwait(false);
            }
            catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
            {
                return effectBoundary.WasCrossed
                    ? effectBoundary.Failure(operation, "desktop_interaction_adapter_failed", true)
                    : ExternalJson.FailureBeforeEffect(operation, "desktop_interaction_adapter_failed");
            }

            if (answer is null)
                return effectBoundary.Failure(operation, "field_no_receipt", true);
            using (answer)
            {
                JsonElement root = answer.RootElement;
                keeper = UiaFrontReport.Read(root);
                fieldFocused = Flag(root, "focused", false);
                string? error = root.TryGetProperty("error", out JsonElement errorValue)
                    && errorValue.ValueKind == JsonValueKind.String
                        ? errorValue.GetString()
                        : null;
                bool ok = root.TryGetProperty("ok", out JsonElement okValue) && okValue.ValueKind == JsonValueKind.True;
                if (!ok && error is "visible_control_identity_stale" or "active_window_not_found")
                    return ExternalJson.FailureBeforeEffect(operation, "visible_control_identity_stale");
                // Ronda final 7: the lookup was cut short before anything was set: not found is not said.
                if (!ok && error == "visible_lookup_timeout")
                    return ExternalJson.FailureBeforeEffect(operation, "visible_lookup_timeout");
                // SetValue refused: nothing was set, the field's own window may still take the text by messages.
                if (!ok && error != "field_setvalue_refused")
                    return effectBoundary.Failure(operation, error is { Length: > 0 } ? error : "field_no_receipt", true);
                if (ok && root.TryGetProperty("method", out JsonElement method)
                    && method.ValueKind == JsonValueKind.String && method.GetString() is "setvalue" or "select")
                {
                    bool whole = root.TryGetProperty("delivered", out JsonElement read) && read.ValueKind == JsonValueKind.True;
                    string fieldClass = root.TryGetProperty("className", out JsonElement named)
                        && named.ValueKind == JsonValueKind.String
                            ? named.GetString() ?? string.Empty
                            : string.Empty;
                    // Revision 1 of r24b: a value set while the keyboard's focus stayed elsewhere (the worker's
                    // «focused» false) waits for the focus before the next key; any other delivery clears it.
                    _unfocusedValue = whole && method.GetString() == "setvalue"
                        && root.TryGetProperty("focused", out JsonElement focusedValue) && focusedValue.ValueKind == JsonValueKind.False
                            ? (identity, controlId, _fields.Clicks, Ticks())
                            : null;
                    // Ronda final: a field that already held that value, or a list with that entry already chosen (read
                    // before), is the state reached: nothing was written (changed:false).
                    if (whole && root.TryGetProperty("alreadyReached", out JsonElement reached)
                        && reached.ValueKind == JsonValueKind.True)
                        return ExternalJson.Switched(operation, root.Clone(), effectObserved: false);
                    // «select»: a list-only combo box took the entry of that name (its selection re-read), said as read.
                    return FieldReceipt(operation, key, text, identity, frontBefore, new FieldDelivery(
                        method.GetString()!, whole, true, whole ? null : "input_effect_not_verified", fieldClass,
                        ChosenEntry(root)), keeper);
                }

                // Ronda final 16 (regla 3): a list-only combo whose list was opened and closed without the entry
                // changed the window: an effect that may have occurred, never «nothing sent».
                if (Flag(root, "expanded", false))
                    return WindowsVisibleControlAdapter.NotNamed(operation, "input_entry_not_found", Entries(root))
                        with { EffectMayHaveOccurred = true };

                // Nothing was set (the worker sets no read-only, password or disabled field): neither its edit
                // control's messages nor the keyboard write there.
                if (Flag(root, "readOnly", false) || Flag(root, "password", false) || !Flag(root, "enabled", true))
                    return ExternalJson.FailureBeforeEffect(operation, "input_field_not_writable");
                field = root.TryGetProperty("nativeHwnd", out JsonElement native) && native.ValueKind == JsonValueKind.Number
                    && native.TryGetInt64(out long hwnd) && hwnd > 0
                        ? (nint)hwnd
                        : 0;
                // Review of cierre-de-subobjetivos (finding 2): a field read empty is written as an insertion only into
                // its own window (its edit control's messages). Without one, the keyboard's focus may be another
                // control (a subject, a search box): the replacement stays refused and nothing is sent.
                if (replace && field != 0 && root.TryGetProperty("valueLength", out JsonElement length)
                    && length.ValueKind == JsonValueKind.Number && length.TryGetInt32(out int held) && held == 0)
                {
                    replace = false;
                }

                // A document is never replaced whole (goal v3 point 2): its text is the person's work.
                if (replace && root.TryGetProperty("kind", out JsonElement fieldKind) && fieldKind.ValueKind == JsonValueKind.String
                    && fieldKind.GetString() == "Document")
                    return ExternalJson.FailureBeforeEffect(operation, "input_field_not_replaceable");
            }
        }
        else
        {
            field = delivery.Messages.FocusOf(window);
        }

        // Otherwise the keyboard would write wherever the window's focus is (a password, the page's search) and the
        // next Enter would send it: nothing is sent (r25 review, finding 1). A replacement is refused by the caller.
        ExternalCapabilityReceipt? unreached = insertion && !fieldFocused
            ? ExternalJson.FailureBeforeEffect(operation, "input_field_not_reachable")
            : null;
        if (field == 0)
            return unreached;
        FieldDelivery? typed = await delivery.TypeAsync(identity, field, text, cancellationToken, replace).ConfigureAwait(false);
        return typed is { } result
            ? FieldReceipt(operation, key, text, identity, frontBefore, result, keeper)
            : unreached;
    }

    /// <summary>
    /// Review of combos-galerias (findings 1 and 2): a closed list's entry named by the goal, chosen in the list box the
    /// view named (the worker's «field» with «entry»: its entry of that name selected by pattern, the selection and the
    /// box's value re-read). Never a text written into the box nor sent to its edit control or the keyboard: a list with
    /// no entry of that name changes nothing (<c>input_entry_not_found</c>).
    /// </summary>
    private async ValueTask<ExternalCapabilityReceipt> EntryToWindowAsync(
        string operation, string text, nint window, int index, DesktopForeground frontBefore, CancellationToken cancellationToken)
    {
        WindowIdentity identity = _delivery!.Messages.Identity(window);
        if (!identity.Alive)
            return ExternalJson.FailureBeforeEffect(operation, "input_window_not_found");
        if (!_fields!.TryViewedField(index, out nint viewed, out string controlId) || viewed != window)
            return ExternalJson.FailureBeforeEffect(operation, "visible_control_identity_stale");
        var effectBoundary = new ExternalEffectBoundary();
        JsonDocument? answer;
        try
        {
            effectBoundary.Cross(cancellationToken);
            answer = await _fields.EntryAsync(window, controlId, text, cancellationToken).ConfigureAwait(false);
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            return effectBoundary.WasCrossed
                ? effectBoundary.Failure(operation, "desktop_interaction_adapter_failed", true)
                : ExternalJson.FailureBeforeEffect(operation, "desktop_interaction_adapter_failed");
        }

        if (answer is null)
            return effectBoundary.Failure(operation, "field_no_receipt", true);
        using (answer)
        {
            JsonElement root = answer.RootElement;
            UiaFrontReport? keeper = UiaFrontReport.Read(root);
            string? error = root.TryGetProperty("error", out JsonElement errorValue) && errorValue.ValueKind == JsonValueKind.String
                ? errorValue.GetString()
                : null;
            bool ok = root.TryGetProperty("ok", out JsonElement okValue) && okValue.ValueKind == JsonValueKind.True;
            if (!ok && error is "visible_control_identity_stale" or "active_window_not_found")
                return ExternalJson.FailureBeforeEffect(operation, "visible_control_identity_stale");
            if (!ok && error == "visible_lookup_timeout")
                return ExternalJson.FailureBeforeEffect(operation, "visible_lookup_timeout");
            if (!ok)
                return effectBoundary.Failure(operation, error is { Length: > 0 } ? error : "field_no_receipt", true);
            // Auditoría C9: no entry is called so (folded); nothing was chosen, and the list's entries go back as they read.
            if (!root.TryGetProperty("method", out JsonElement method) || method.ValueKind != JsonValueKind.String
                || method.GetString() != "select")
                return WindowsVisibleControlAdapter.NotNamed(operation, "input_entry_not_found", Entries(root))
                    with { EffectMayHaveOccurred = Flag(root, "expanded", false) };
            bool whole = root.TryGetProperty("delivered", out JsonElement read) && read.ValueKind == JsonValueKind.True;
            // Ronda final: the entry already chosen (read before) is the state reached: nothing was chosen (changed:false).
            if (whole && root.TryGetProperty("alreadyReached", out JsonElement reached) && reached.ValueKind == JsonValueKind.True)
                return ExternalJson.Switched(operation, root.Clone(), effectObserved: false);
            string fieldClass = root.TryGetProperty("className", out JsonElement named) && named.ValueKind == JsonValueKind.String
                ? named.GetString() ?? string.Empty
                : string.Empty;
            return FieldReceipt(operation, null, text, identity, frontBefore, new FieldDelivery(
                "select", whole, true, whole ? null : "input_effect_not_verified", fieldClass, ChosenEntry(root)), keeper);
        }
    }

    // The entry a «select» chose, as the worker read its name; null when it said none.
    private static string? ChosenEntry(JsonElement root) =>
        root.TryGetProperty("chosen", out JsonElement chosen) && chosen.ValueKind == JsonValueKind.String
            && chosen.GetString() is { Length: > 0 } name
                ? name
                : null;

    /// <summary>
    /// cu-v3-scroll-pegar-direccion (t-long-1, measured: Ctrl+V to a text editor just opened behind the person's window
    /// was refused with input_window_not_in_front, the front not given to an application opened behind): the paste goes
    /// without keyboard or front, as the clipboard's text BAXY reads inserted at the caret of the window's edit control
    /// (its keyboard focus; only when the window reports no focus, its only visible edit control) by EM_REPLACESEL,
    /// proved by the control's text re-read. Null when the clipboard holds no one-line text or more than a typed text
    /// takes (<see cref="MaximumTypedText"/>), when the focus is on a control that is no edit control (the text would go
    /// elsewhere than a keyboard's Ctrl+V: a web or XAML box beside a filter field), or when the window has no such
    /// control: the keyboard takes the chord.
    /// </summary>
    private async ValueTask<ExternalCapabilityReceipt?> PasteToWindowAsync(
        string operation, WindowIdentity identity, DesktopForeground frontBefore, CancellationToken cancellationToken)
    {
        WindowsTextDelivery delivery = _delivery!;
        string? pasted = _clipboardText?.Invoke();
        // A text of several lines keeps the keyboard's paste: an edit control counts its line breaks its own way, so
        // the re-read could not prove it whole.
        if (string.IsNullOrEmpty(pasted) || pasted.Any(char.IsControl) || pasted.Length > MaximumTypedText)
            return null;
        nint focus = delivery.Messages.FocusOf(identity.Window);
        // The keyboard's Ctrl+V goes to the focus: a focus that is no edit control never hands the text to another one.
        nint field = focus == 0 ? delivery.Messages.SoleEditOf(identity.Window)
            : WindowsTextDelivery.IsEditClass(delivery.Messages.ClassName(focus)) ? focus
            : 0;
        if (field == 0)
            return null;
        FieldDelivery? put = await delivery.TypeAsync(identity, field, pasted, cancellationToken).ConfigureAwait(false);
        return put is { } done
            ? FieldReceipt(operation, "ctrl_v", pasted, identity, frontBefore, done)
            : null;
    }

    private static bool Flag(JsonElement root, string name, bool absent) =>
        root.TryGetProperty(name, out JsonElement value) && value.ValueKind is JsonValueKind.True or JsonValueKind.False
            ? value.ValueKind == JsonValueKind.True
            : absent;

    /// <summary>
    /// The receipt of a delivery without keyboard. The front is read before (by the caller) and after: measured live,
    /// UI Automation's SetValue on a XAML search box brought its window to the front. When the delivery moved the front
    /// to the mission's window (or its process) from a window of another process, the front goes back to that window
    /// (the person's), and the receipt says both (<c>frontChanged</c>, <c>frontRestored</c>), for the annoyance meter.
    /// A front another window took meanwhile is reported, never fought. The worker's front net may have given it back
    /// already while it acted (<paramref name="keeper"/>): then the front looks unchanged here, and the receipt still
    /// says it moved, and whether it came back.
    /// </summary>
    private ExternalCapabilityReceipt FieldReceipt(
        string operation, string? key, string text, WindowIdentity identity, DesktopForeground before,
        FieldDelivery delivery, UiaFrontReport? keeper = null)
    {
        if (!delivery.Delivered && !delivery.EffectMayHaveOccurred)
            return ExternalJson.FailureBeforeEffect(operation, delivery.Error ?? "input_effect_not_verified");
        nint window = identity.Window;
        DesktopForeground after = _keyboard.Foreground();
        bool frontChanged = after.Window != before.Window;
        bool frontRestored = false;
        // v3 point 1: measured live, SetValue on a field of a WebView2 surface brought that window up; the
        // application's own window (its family peer) coming up is the same activation.
        nint peer = VisibleControlSurface.FamilyPeer(window);
        if (frontChanged && before.Window != 0 && before.Window != window && before.ProcessId != identity.ProcessId
            && (peer == 0 || before.Window != peer)
            && (after.Window == window || after.ProcessId == identity.ProcessId || (peer != 0 && after.Window == peer)))
        {
            // Giving the person's window back takes nothing from them: no lease, no wait for their pause.
            frontRestored = _keyboard.GiveFront(before.Window);
        }

        // One report for both nets: a change seen here is the latest word; otherwise the worker's, if it saw one.
        if (!frontChanged && keeper is { } net)
        {
            frontChanged = true;
            frontRestored = net.Restored;
        }

        if (!delivery.Delivered)
            return ExternalJson.FailureAfterEffect(operation, delivery.Error ?? "input_effect_not_verified", true);
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteBoolean("ok", true);
            // Ronda final: a queued key is delivered as the keyboard's is (CU12), not an effect seen; the other methods
            // read the field back.
            writer.WriteBoolean(delivery.Method == "postmessage" ? "delivered" : "effectObserved", true);
            writer.WriteString("action", key is null ? "text" : "key");
            if (key is null)
                writer.WriteNull("key");
            else
                writer.WriteString("key", key);
            writer.WriteNumber("textLength", text.Length);
            // How it got there: setvalue (UI Automation), em_replacesel or wm_char (the edit control's messages),
            // postmessage (a queued key). None of them needs the keyboard or the front.
            writer.WriteString("method", delivery.Method);
            // Auditoría C9: the entry of the list that was chosen, as read, never the text asked.
            if (delivery.Entry is { } entry)
                writer.WriteString("entry", entry);
            writer.WriteString("fieldClass", delivery.FieldClass);
            writer.WriteNumber("window", window);
            writer.WriteString("windowTitle", VisibleControlSurface.WindowTitle(window));
            writer.WriteNumber("foregroundProcessIdBefore", before.ProcessId);
            writer.WriteNumber("foregroundProcessIdAfter", after.ProcessId);
            writer.WriteString("foregroundTitleBefore", before.Title);
            writer.WriteString("foregroundTitleAfter", after.Title);
            writer.WriteBoolean("frontChanged", frontChanged);
            writer.WriteBoolean("frontRestored", frontRestored);
            writer.WriteString("authority", delivery.Method switch
            {
                "setvalue" => "windows_uia_setvalue_reread",
                "select" => "windows_uia_selection_reread",
                "postmessage" => "win32_postmessage_queued",
                _ => "win32_edit_message_reread",
            });
            writer.WriteNull("error");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, true);
    }

    internal static JsonElement AsDelivered(JsonElement root, (string Title, string Process)? sentTo = null) =>
        ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            foreach (JsonProperty property in root.EnumerateObject())
            {
                if (property.NameEquals("effectObserved"))
                    writer.WriteBoolean("delivered", property.Value.ValueKind == JsonValueKind.True);
                else
                    property.WriteTo(writer);
            }

            if (sentTo is { } window)
            {
                writer.WriteStartObject("sentTo");
                writer.WriteString("title", window.Title);
                writer.WriteString("process", window.Process);
                writer.WriteEndObject();
                // The reply named the app asked for even with sentTo there (PC, C18): the same fact as a sentence.
                if (Infrastructure.ModelAids.On(Infrastructure.ModelAids.PasteTargetNext))
                    writer.WriteString("next", $"it went into the window of {window.Title} ({window.Process}); "
                        + "no other application received it");
            }

            writer.WriteEndObject();
        });

    // BAXY Renew cu (C18): a paste goes to the window in front; with no app opened first it went into another program's
    // window (a mail draft) and the reply named the app asked for. The window that took it, as the keys' sentTo says it:
    // its title and its program, read before the keys.
    internal static (string Title, string Process)? PastedInto(JsonElement root)
    {
        if (!root.TryGetProperty("foregroundTitleBefore", out JsonElement title) || title.ValueKind != JsonValueKind.String
            || !root.TryGetProperty("foregroundProcessIdBefore", out JsonElement id) || !id.TryGetInt32(out int processId)
            || processId <= 0)
            return null;
        try
        {
            using var process = System.Diagnostics.Process.GetProcessById(processId);
            return (title.GetString() ?? string.Empty, process.ProcessName);
        }
        catch (Exception exception) when (exception is ArgumentException or InvalidOperationException)
        {
            return null;
        }
    }
}
