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

    internal WindowsDesktopInteractionAdapter()
        : this(null)
    {
    }

    /// <summary>The product's adapter: a mission's key or text goes to its window by window messages or UI Automation
    /// when its field takes them (<paramref name="fields"/>: the last view's fields), else by the keyboard.</summary>
    internal WindowsDesktopInteractionAdapter(IViewedFields? fields)
        : this(
            new ExternalProcessRunner(),
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
            return await InvokeActAsync(operation, arguments, cancellationToken).ConfigureAwait(false);
        }
        finally
        {
            _focusOwed = null;
        }
    }

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
        try
        {
            if (operation == "clipboard.copy")
                command.Add("-CopySelection");
            else if (operation == "clipboard.paste")
                command.Add("-PasteClipboard");
            else if (operation is "filesystem.folder.open" or "filesystem.file.open.latest")
            {
                command.Add(ExternalJson.RequiredString(arguments, "folder"));
                if (operation == "filesystem.folder.open"
                    && arguments.TryGetProperty("subdirectory", out JsonElement subdirectory)
                    && subdirectory.ValueKind == JsonValueKind.String
                    && !string.IsNullOrWhiteSpace(subdirectory.GetString()))
                {
                    command.Add("-Subdirectory");
                    command.Add(subdirectory.GetString()!);
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
            (ExternalProcessResult? watched, bool interrupted) = await LeasedInput.WatchHelperAsync(
                burst,
                run => _runner.RunAsync("powershell.exe", command, TimeSpan.FromSeconds(15), run),
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
        finally
        {
            _ = burst?.Restore();
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

    // The characters a burst types when the person's input cannot be told apart from BAXY's (no Raw Input).
    internal const int BlindBurstCharacters = 8;

    /// <summary>
    /// A key or a text sent to the window in front by SendInput from this process: verified when Windows accepted
    /// every event, with the foreground read before and after for the receipt. Nothing is sent while nobody holds
    /// the foreground or when the native INPUT record does not have its native size.
    /// Safety review 2026-10-07: a computer-use step names its mission's window (<c>window</c>, the hwnd of its last
    /// view), and its key or text is delivered to that window or nowhere. Goal v3 (point 0, fix 1): «bound» means the
    /// delivery is aimed at that window (its hwnd, process and process creation time, checked before every send), not
    /// that it holds the front. First without keyboard or foreground (<see cref="DeliverToWindowAsync"/>): a text to
    /// the field the step names (<c>index</c>, of the last view) or to the window's own focus, a single key to a
    /// classic control. Only what no message reaches (a chord, a field drawn by Chromium or XAML without a writable
    /// value) goes by the keyboard: the window is brought to the front and nothing is sent unless it holds it; a text
    /// stops the moment the window loses the front or the request is cancelled, and a text whose foreground process
    /// changed while it was typed is not verified. A mission's text carries no line break or tab (each would be a key
    /// of its own).
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
        string? key = null;
        string text = string.Empty;
        ushort[] chord = [];
        nint window = 0;
        int? index = null;
        bool replace = false;
        bool entry = false;
        bool fieldNamed = false;
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

            fieldNamed = typing && arguments.TryGetProperty("field", out JsonElement label)
                && label.ValueKind == JsonValueKind.String && !string.IsNullOrWhiteSpace(label.GetString());
        }
        catch (InvalidDataException)
        {
            return ExternalJson.FailureBeforeEffect(operation, "desktop_interaction_argument_invalid");
        }

        // Goal v3 point 2 (forms): a field named by its label that the mission found in no view has no index; the text
        // goes nowhere rather than to whatever holds the keyboard.
        if (fieldNamed && index is null)
            return ExternalJson.FailureBeforeEffect(operation, "input_field_not_found");
        // A replaced value needs the field it replaces: the window's own focus may be a document.
        if (replace && index is null)
            return ExternalJson.FailureBeforeEffect(operation, "input_field_not_replaceable");
        // Review of combos-galerias (finding 1): an entry of a list is chosen only in that list, by pattern, never typed;
        // without its box (or without the field reader) nothing is sent.
        if (entry && (index is null || window == 0 || _delivery is null || _fields is null))
            return ExternalJson.FailureBeforeEffect(operation, "input_field_not_found");

        // A field is named only inside a mission's window.
        if ((typing && text.Length > MaximumTypedText) || (!typing && !VirtualKeys.TryGetValue(key!, out chord!))
            || (typing && window != 0 && text.Any(char.IsControl)) || (index is not null && window == 0))
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
            return await SendInBurstAsync(operation, typing, key, text, chord, window, bursts, cancellationToken)
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
        CancellationToken cancellationToken)
    {
        DesktopForeground before = _keyboard.Foreground();
        if (before.Window == 0 || _keyboard.InputSize != (IntPtr.Size == 8 ? 40 : 28))
            return ExternalJson.FailureBeforeEffect(operation, "key_press_sendinput_failed");
        // v3 point 0: something may take the front back between fronting the window and the press (the person, or an
        // application opened behind that Windows activated late): the key is checked against the window right before
        // it goes, never sent to whatever holds the front now.
        if (window != 0 && !_keyboard.Holds(window))
            return ExternalJson.FailureBeforeEffect(operation, "input_window_changed");

        var effectBoundary = new ExternalEffectBoundary();
        effectBoundary.Cross(cancellationToken);
        uint expected = typing ? (uint)text.Length * 2 : (uint)chord.Length * 2;
        // The person touched the keyboard or the mouse between the pause and the first key: nothing goes.
        if (bursts.Current is { UserActed: true })
            return ExternalJson.FailureBeforeEffect(operation, "input_user_interrupted");
        bool interrupted = false;
        bool userActed = false;
        int pausesWaited = 0;
        string? refusedLater = null;
        bool KeepGoing()
        {
            userActed |= bursts.Current is { UserActed: true };
            bool stays = !cancellationToken.IsCancellationRequested
                && !userActed
                && (window != 0 ? _keyboard.Holds(window) : _keyboard.Foreground().ProcessId == before.ProcessId);
            interrupted |= !stays;
            return stays;
        }

        uint accepted = 0;
        string? focusAt = null;
        if (!typing)
        {
            // Revision 1 of r24b (v1): after a value set without the keyboard's focus, the key goes to that field or
            // nowhere: UI Automation puts the focus there (the window is in front now) and re-reads it.
            if (window != 0 && _delivery is not null && UnfocusedField(_delivery.Messages.Identity(window)) is string field)
            {
                if (!await FocusedAsync(window, field, cancellationToken).ConfigureAwait(false))
                    return ExternalJson.FailureBeforeEffect(operation, "input_field_not_focused");
                if (!_keyboard.Holds(window))
                    return ExternalJson.FailureBeforeEffect(operation, "input_window_changed");
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
                    if (bursts.Current is { UserActed: true })
                    {
                        personActed = true;
                        return false;
                    }

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

                // The person acted in the middle: their front first, then the rest after their next pause.
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
        try
        {
            await _keyboard.SettleAsync(cancellationToken).ConfigureAwait(false);
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            return effectBoundary.Failure(operation, "desktop_interaction_adapter_failed", effect);
        }

        DesktopForeground after = _keyboard.Foreground();
        // Given back before the receipt, which says whether it was.
        bool? restored = bursts.Current is null ? null : bursts.Restore();
        string stopped = refusedLater ?? (userActed ? "input_user_interrupted" : "input_window_changed");
        if (interrupted)
            return effect
                ? effectBoundary.Failure(operation, stopped, effect)
                : ExternalJson.FailureBeforeEffect(operation, stopped);
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
            writer.WriteString("method", "keyboard");
            writer.WriteNumber("acceptedEvents", accepted);
            writer.WriteNumber("expectedEvents", expected);
            writer.WriteNumber("inputSize", _keyboard.InputSize);
            writer.WriteNumber("lastWin32Error", lastError);
            writer.WriteNumber("foregroundProcessIdBefore", before.ProcessId);
            writer.WriteNumber("foregroundProcessIdAfter", after.ProcessId);
            writer.WriteString("foregroundTitleBefore", before.Title);
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
            writer.WriteString("authority", focusAt is null ? "win32_sendinput_return_count" : "uia_focus_reread_and_win32_sendinput");
            writer.WriteNull("error");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effect);
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
                    // «select»: a list-only combo box took the entry of that name (its selection re-read).
                    return FieldReceipt(operation, key, text, identity, frontBefore, new FieldDelivery(
                        method.GetString()!, whole, true, whole ? null : "input_effect_not_verified", fieldClass), keeper);
                }

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
            if (!ok)
                return effectBoundary.Failure(operation, error is { Length: > 0 } ? error : "field_no_receipt", true);
            if (!root.TryGetProperty("method", out JsonElement method) || method.ValueKind != JsonValueKind.String
                || method.GetString() != "select")
                return ExternalJson.FailureBeforeEffect(operation, "input_entry_not_found");
            bool whole = root.TryGetProperty("delivered", out JsonElement read) && read.ValueKind == JsonValueKind.True;
            string fieldClass = root.TryGetProperty("className", out JsonElement named) && named.ValueKind == JsonValueKind.String
                ? named.GetString() ?? string.Empty
                : string.Empty;
            return FieldReceipt(operation, null, text, identity, frontBefore, new FieldDelivery(
                "select", whole, true, whole ? null : "input_effect_not_verified", fieldClass), keeper);
        }
    }

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
            writer.WriteBoolean("effectObserved", true);
            writer.WriteString("action", key is null ? "text" : "key");
            if (key is null)
                writer.WriteNull("key");
            else
                writer.WriteString("key", key);
            writer.WriteNumber("textLength", text.Length);
            // How it got there: setvalue (UI Automation), em_replacesel or wm_char (the edit control's messages),
            // postmessage (a queued key). None of them needs the keyboard or the front.
            writer.WriteString("method", delivery.Method);
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
}
