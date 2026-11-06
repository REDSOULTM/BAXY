using System.Text.Json;
using Baxy.Kernel.Operations;
using Baxy.Kernel.Policy;

namespace Baxy.Providers.Windows.External;

internal sealed partial class WindowsDesktopInteractionAdapter : IExternalOperationAdapter
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

    // Uso-108 (review, items 2 and 3), for the act now running. An empty field with no window of its own that the keyboard
    // writes: a replacement of nothing is that insertion (_replacedByKeyboard), UI Automation first puts the focus there when it
    // lacks it (_focusFirst), and a field written and erased through its value was touched (_fieldTouched). A text past
    // the keyboard's pace on a Chromium surface goes at its own (_typingPace; 0 is the keyboard's). A value whose SetValue
    // refused is replaced with its whole text selected first (_selectWhole), and only the text whole verifies it.
    private bool _replacedByKeyboard;
    private bool _selectWhole;
    private string? _wholeRead;
    private string? _focusFirst;
    private bool _fieldTouched;
    private bool _onRenderSurface;
    private int _typingPace;

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
        KeySurface = KeySurfaceWitness.Product;
        PointerUnder = VisibleControlSurface.UnderPointer;
    }

    /// <summary>
    /// Uso-108 (hondo 11 finding 8, agent-desktop PR #490 window_at_point): the window under the pointer, as a view names
    /// it, read before a click where the pointer is; null reads nothing (the test seams that name none).
    /// </summary>
    internal Func<string?>? PointerUnder { get; init; }

    /// <summary>
    /// Uso-108 (B2): reads whether a plain key changed its window's image (<see cref="KeySurfaceWitness"/>); null reads
    /// nothing (the test seams that name none).
    /// </summary>
    internal KeySurfaceWitness? KeySurface { get; init; }

    // Whether the running key's image told nothing (brought up for it, unreadable, or moving by itself): its view after says
    // only what it lists is the same.
    private bool _keyImageUnread;

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
    // goes unasked; nothing else this adapter does is. Revisión de la guarda F013 (teclas): nor Enter or space, which
    // press the focused button of a dialog as a click on it does, while the last view's adapter can read that dialog.
    public bool PreflightMayRaise(string operation, JsonElement arguments) =>
        DeclaredTextFieldPress.Applies(operation, arguments) || AnswersADialog(operation, arguments);

    public async ValueTask<ExternalCapabilityReceipt?> PreflightAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        bool declared = DeclaredTextFieldPress.Applies(operation, arguments);
        bool answers = AnswersADialog(operation, arguments);
        if (!declared && !answers)
            return null;
        nint window = NamedWindow(arguments);
        if (declared)
        {
            FocusRead? focus = null;
            if (_fields is not null)
            {
                using JsonDocument? answer = await _fields.FocusKindAsync(window, cancellationToken).ConfigureAwait(false);
                focus = DeclaredTextFieldPress.Read(answer);
            }

            KeyWindowKind kind = KeyWindows.KindOf(window == 0 ? null : window);
            if (DeclaredTextFieldPress.NeedsYes(arguments, focus, kind))
                return new ExternalCapabilityReceipt(operation, false, false, null, null) { NeedsConfirmation = true };
        }

        // Revisión de la guarda F013 (teclas): the key that would say yes to «¿Reemplazar?» asks as the click does,
        // whatever the model declared of it; bound to this press by the engine (NeedsConfirmation raises its risk).
        if (answers && await _fields!.KeyAnswersDestructiveDialogAsync(
                window, arguments.GetProperty("key").GetString()!, cancellationToken).ConfigureAwait(false))
            return new ExternalCapabilityReceipt(operation, false, false, null, null) { NeedsConfirmation = true };

        // Auditoría de falsedades 2026-11-04 (P6, S03): an Enter with neither target nor onto, in a chat whose process is
        // no known messaging client, went unasked (K-2 refinada lowered it as an ordinary window) and sent the message
        // written in its field. Such an Enter asks while any field of its window that takes text holds text, wherever UI
        // Automation reads the focus, and when that cannot be read; a window whose fields hold none lets it go.
        return answers && UndeclaredEnter(operation, arguments)
            && await _fields!.HoldsTextAsync(window, cancellationToken).ConfigureAwait(false) is not false
            ? new ExternalCapabilityReceipt(operation, false, false, null, null) { NeedsConfirmation = true }
            : null;
    }

    // Pure: K-2's undeclared press (RiskPolicy.PressesUndeclared) of Enter, which sends what a field holds.
    private static bool UndeclaredEnter(string operation, JsonElement arguments) =>
        RiskPolicy.PressesUndeclared(operation, arguments)
        && arguments.GetProperty("key").GetString() == "enter";

    // Pure: Enter or space, which press the focused control, with the visible controls' adapter to read it.
    private bool AnswersADialog(string operation, JsonElement arguments) =>
        _fields is not null
        && operation == "input.key.press"
        && arguments.ValueKind == JsonValueKind.Object
        && arguments.TryGetProperty("key", out JsonElement key) && key.ValueKind == JsonValueKind.String
        && key.GetString() is "enter" or "space";

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
        _replacedByKeyboard = false;
        _selectWhole = false;
        _wholeRead = null;
        _focusFirst = null;
        _fieldTouched = false;
        _onRenderSurface = false;
        _typingPace = 0;
        try
        {
            // Ajuste c3 (E017): an Enter that confirms a common file dialog is judged on the dialog, as its button's click.
            CommonFileDialog.Facts? fileDialog = operation == "input.key.press" ? EnterConfirms(arguments) : null;
            DateTime actedUtc = DateTime.UtcNow;
            // Ajuste c3: what the text's index meant (the control the model saw there), said in its receipt.
            ViewedIndex? seenIndex = operation == "input.text.type" && _fields is not null && IndexOf(arguments) is int at
                ? _fields.ViewedAt(at)
                : null;
            ExternalCapabilityReceipt receipt = WindowsVisibleControlAdapter.WithSeenIndex(
                await InvokeActAsync(operation, arguments, cancellationToken).ConfigureAwait(false), seenIndex);
            if (fileDialog is not null && (receipt.Verified || receipt.EffectObserved))
            {
                CommonFileDialog.Outcome outcome = await CommonFileDialog.AwaitAsync(fileDialog, actedUtc, cancellationToken)
                    .ConfigureAwait(false);
                receipt = CommonFileDialog.Apply(receipt, fileDialog, outcome,
                    Infrastructure.ModelAids.On(Infrastructure.ModelAids.SaveDialogNext));
                if (outcome.Ending == CommonFileDialog.Ending.Closed)
                    return receipt;
            }

            // Renew al máximo (7.1): a text or a key completed in a named window carries the view of that window after
            // it (the visible controls' adapter reads it again; it becomes the last view); nothing when it was not read.
            if (operation is "input.text.type" or "input.key.press" && _fields is not null
                && receipt is { Verified: true, ErrorCode: null, EffectObserved: true }
                && NamedWindow(arguments) is nint window and not 0
                && await _fields.AfterActAsync(window, cancellationToken).ConfigureAwait(false) is { } after)
                receipt = WindowsVisibleControlAdapter.WithAfter(receipt, _keyImageUnread
                    ? WindowsVisibleControlAdapter.ListedSame(after)
                    : WindowsVisibleControlAdapter.ListedSameWhenSurfaceChanged(receipt.Result, after));
            // A failure after the field was written and erased (uso-108, review 3) never says nothing happened.
            if (_fieldTouched && !receipt.Verified && !receipt.EffectMayHaveOccurred)
                receipt = receipt with { EffectMayHaveOccurred = true };
            return LoneModifier(operation, arguments, receipt);
        }
        finally
        {
            _focusOwed = null;
        }
    }

    /// <summary>
    /// Holdout v6 V6E024 («on the calculator, hit the C button», both seeds): the key pressed was «control», alone, and
    /// the reply was that it was pressed and the display not checked. A modifier pressed by itself, as the fact of what it
    /// is beside the receipt, which stays: it writes nothing and is no shortcut; a button the window shows is pressed by
    /// its label. Any other receipt, as it came.
    /// </summary>
    internal static ExternalCapabilityReceipt LoneModifier(
        string operation, JsonElement arguments, ExternalCapabilityReceipt receipt) =>
        operation == "input.key.press" && receipt.Verified && arguments.ValueKind == JsonValueKind.Object
        && arguments.TryGetProperty("key", out JsonElement key) && key.ValueKind == JsonValueKind.String
        && key.GetString() is "control" or "shift"
        && Infrastructure.ModelAids.On(Infrastructure.ModelAids.LoneModifierNext)
            ? receipt with
            {
                Result = ExternalJson.Extended(receipt.Result, writer => writer.WriteString("next",
                    $"{key.GetString()} was pressed by itself: a modifier key alone writes nothing and is no shortcut; a "
                    + "button the window shows is pressed by its label (input_visible_click), after a look "
                    + "(input_visible_controls) gives the labels")),
            }
            : receipt;

    // Ajuste c3 (E017): the common file dialog an Enter would confirm: the one the key goes to (the window it names, or
    // the one in front, which a modal dialog of the named window is), unless its focus is on a push button other than
    // the one that saves or opens (Cancelar takes the Enter then, and the dialog closes without saving).
    private CommonFileDialog.Facts? EnterConfirms(JsonElement arguments)
    {
        if (arguments.ValueKind != JsonValueKind.Object || !arguments.TryGetProperty("key", out JsonElement key)
            || key.ValueKind != JsonValueKind.String || key.GetString() != "enter")
            return null;
        nint front = _keyboard.Foreground().Window;
        CommonFileDialog.Facts? facts = CommonFileDialog.Read(NamedWindow(arguments)) ?? CommonFileDialog.Read(front);
        if (facts is null)
            return null;
        nint focus = _delivery?.Messages.FocusOf(facts.Dialog) ?? 0;
        return focus != 0 && focus != facts.Accept && _delivery!.Messages.ClassName(focus) == "Button" ? null : facts;
    }

    // The index a step names («index»), as a number; null otherwise.
    private static int? IndexOf(JsonElement arguments) =>
        arguments.ValueKind == JsonValueKind.Object && arguments.TryGetProperty("index", out JsonElement named)
        && named.ValueKind == JsonValueKind.Number && named.TryGetInt32(out int index)
            ? index
            : null;

    // Ajuste c3 (humos del 31-10): the field the model saw at an index of the last view, wherever the view after an act put
    // it (IViewedFields.ViewedAt); false when no view handed it out or that control is gone (never what is there now).
    private bool SeenField(int index, out nint window, out string controlId)
    {
        ViewedIndex? seen = _fields?.ViewedAt(index);
        window = seen is { Gone: false } found ? found.Window : 0;
        controlId = seen is { Gone: false } kept ? kept.ControlId : string.Empty;
        return window != 0 && controlId.Length > 0;
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
            else if (operation == "filesystem.file.open.latest")
            {
                command.Add(ExternalJson.RequiredString(arguments, "folder"));
                positional.Add(command[^1]);
            }
            else if (operation == "filesystem.folder.open")
            {
                // P2.4 (ajuste c3): the folder as the person said it (PersonFolders.Place), as the script takes it: the
                // known folder and the subfolder inside it.
                if (Baxy.Providers.Windows.Filesystem.PersonFolders.Place(
                        ExternalJson.RequiredString(arguments, "path"),
                        Baxy.Providers.Windows.Filesystem.PersonFolders.PathLabels(operation),
                        WindowsFileToolsAdapter.KnownFolderPath) is not { } said)
                    return ExternalJson.FailureBeforeEffect(operation, "known_path_outside_folder");
                command.Add(said.Label);
                positional.Add(command[^1]);
                if (said.Relative.Length > 0)
                {
                    command.Add("-Subdirectory");
                    command.Add(said.Relative);
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

        // A click there says nothing of what it hit: the model could not tell the desktop from the application.
        string? under = operation == "input.pointer.control"
            && arguments.TryGetProperty("action", out JsonElement act) && act.ValueKind == JsonValueKind.String
            && act.GetString() == "click"
                ? PointerUnder?.Invoke()
                : null;
        var effectBoundary = new ExternalEffectBoundary();
        try
        {
            // R6-NB-3 (CU 36 C18, a paste into a new Notepad told «I did not look again»): the clipboard's text is marked
            // where the keys go, before them, as a typed text is (SendInBurstAsync), and read back after them; inside
            // the burst's restore.
            PasteMark? pasteMark = operation == "clipboard.paste"
                ? await MarkPasteAsync(cancellationToken).ConfigureAwait(false)
                : null;
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
                if (operation == "clipboard.copy" && error == "clipboard_not_changed")
                {
                    // Read while the window still holds the front (the burst gives it back after). Encargo 27 (banco
                    // uso-d4bd, U27): the keys go to the window in front, which may not be the one the person named (a
                    // Notepad started by a process not in front stays behind: SetForegroundWindow's rules), so the
                    // failure names it (sentTo), and its lengths are said only while that window is still in front.
                    DesktopForeground front = _keyboard.Foreground();
                    (string Title, string Process)? tookTheKeys = PastedInto(root);
                    bool moved = root.TryGetProperty("foregroundProcessIdBefore", out JsonElement before)
                        && before.TryGetInt32(out int beforeProcess) && beforeProcess > 0
                        && beforeProcess != front.ProcessId;
                    CopiedFrom read = moved
                        ? default
                        : await CopiedFromAsync(front, cancellationToken).ConfigureAwait(false);
                    (string Title, string Process)? sentTo = moved
                        ? tookTheKeys
                        : front.Window != 0 ? (front.Title, _keyboard.ProcessName(front.Window)) : tookTheKeys;
                    // Encargo 45 (U27): the clipboard read again unchanged and nothing selected in the window that took
                    // Ctrl+C, still in front: the copy did nothing there (WM_COPY copies the selection), an effect known,
                    // not lost. A console's Ctrl+C is an interrupt, an effect of its own: it stays uncertain.
                    bool knownNothing = !effect && !moved && read.SelectionLength == 0
                        && !Windows.Win32WindowControlPlatform.IsConsoleClass(_keyboard.ClassName(front.Window));
                    ExternalCapabilityReceipt failed = effectBoundary.Failure(operation, error, effect);
                    return failed with
                    {
                        EffectMayHaveOccurred = failed.EffectMayHaveOccurred && !knownNothing,
                        Result = ExternalJson.Create(writer =>
                        {
                            writer.WriteStartObject();
                            WriteCopiedFrom(writer, read);
                            if (sentTo is { } window)
                            {
                                writer.WriteStartObject("sentTo");
                                writer.WriteString("title", window.Title);
                                writer.WriteString("process", window.Process);
                                writer.WriteEndObject();
                            }

                            WriteSelectAllNext(writer, read, sentTo?.Title, front.Window);
                            writer.WriteEndObject();
                        }),
                    };
                }

                // Encargo 94: a dialog select all's last resort raised (Ctrl+A is «Abrir» in a language) is said, closed or
                // not: the person sees it, and this call selected nothing.
                if (root.TryGetProperty("dialogOpened", out JsonElement dialog) && dialog.ValueKind == JsonValueKind.Object)
                {
                    string title = dialog.TryGetProperty("title", out JsonElement titled) ? titled.GetString() ?? string.Empty : string.Empty;
                    bool closed = dialog.TryGetProperty("closed", out JsonElement shut) && shut.ValueKind == JsonValueKind.True;
                    return effectBoundary.Failure(operation, error, effect) with
                    {
                        Result = ExternalJson.Create(writer =>
                        {
                            writer.WriteStartObject();
                            writer.WritePropertyName("dialogOpened");
                            dialog.WriteTo(writer);
                            writer.WriteString("next", $"this call selected nothing: the window took Ctrl+A as another command and "
                                + $"opened «{title}», {(closed ? "which was closed again" : "which is still open")}");
                            writer.WriteEndObject();
                        }),
                    };
                }

                return effectBoundary.Failure(operation, error, effect);
            }
            // Ronda final: a layout already Spanish or an on-screen keyboard already shown is the state reached
            // (changed:false), never a change this call made.
            if (root.TryGetProperty("alreadyReached", out JsonElement reached) && reached.ValueKind == JsonValueKind.True)
                return ExternalJson.Switched(operation, root.Clone(), effectObserved: false);
            // Ronda final: a paste, a click or a scroll is what SendInput accepted, as the keyboard's (CU12): delivered,
            // not an effect seen; a paste says besides whether its text was read back where it went (readBack).
            if (operation == "clipboard.paste")
            {
                PasteRead read = await PasteReadsBackAsync(pasteMark, root, cancellationToken).ConfigureAwait(false);
                JsonElement pasted = AsDelivered(root, PastedInto(root), read);
                return read.Found == false
                    ? new ExternalCapabilityReceipt(operation, effect, false, pasted, PasteNotReadBack)
                    {
                        EffectMayHaveOccurred = true,
                    }
                    : ExternalJson.Success(operation, pasted, effect);
            }

            bool deliveredOnly = operation == "input.pointer.control"
                && !(root.TryGetProperty("pointerAction", out JsonElement pointer)
                    && pointer.ValueKind == JsonValueKind.String && pointer.GetString() == "move_center");
            return ExternalJson.Success(operation, deliveredOnly ? AsDelivered(root, under: under) : root.Clone(), effect);
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
    // or, in many applications, the window, gracefully, and goes directly (decisión del dueño 2026-10-25).
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
        // Holdout v5 V5E023: the end and the start of the whole text (End and Home alone stay on the line).
        ["ctrl_end"] = [0x11, 0x23],
        ["ctrl_f"] = [0x11, 0x46],
        ["ctrl_h"] = [0x11, 0x48],
        ["ctrl_home"] = [0x11, 0x24],
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

    // Row A10 (agent-desktop refuses before sending when the deadline cannot cover the text, delivered_chunks 0,
    // crates/windows/src/input/keyboard/keyboard_text.rs): what a typed character costs, to know before the first key
    // whether the text fits. Thread.Sleep(35) measured 36.1 ms at a timer of 0.5 ms; at Windows' default timer of 15.625 ms
    // it ends on the third tick, 46.9 ms (MS docs of Sleep: "the system clock ticks at a constant rate").
    // Uso-108 (review, 2d): WindowsDesktopKeyboard.TypeText now asks a timer of 1 ms while it types, so a character costs what
    // that timer gives: Sleep(35) measured 35.6 ms here; the one more is the send and the bound's margin. The 47 of the
    // default timer refused from 1490 characters what fits up to 1891.
    internal const int TypedCharacterMs = 37;

    // The same at WindowsDesktopKeyboard.SurfacePace (measured 13 ms a character).
    private const int SurfaceCharacterMs = 14;

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
        string? replacing = null;
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

            if (typing && arguments.TryGetProperty("replace", out JsonElement whole) && whole.ValueKind != JsonValueKind.Null)
            {
                if (whole.ValueKind is not (JsonValueKind.True or JsonValueKind.False))
                    throw new InvalidDataException("replace");
                replace = whole.ValueKind == JsonValueKind.True;
            }

            if (typing && arguments.TryGetProperty("entry", out JsonElement listed) && listed.ValueKind != JsonValueKind.Null)
            {
                if (listed.ValueKind is not (JsonValueKind.True or JsonValueKind.False))
                    throw new InvalidDataException("entry");
                entry = listed.ValueKind == JsonValueKind.True;
            }

            if (typing && arguments.TryGetProperty("replacing", out JsonElement part) && part.ValueKind != JsonValueKind.Null)
                replacing = ExternalJson.RequiredString(arguments, "replacing");
        }
        catch (InvalidDataException)
        {
            return ExternalJson.FailureBeforeEffect(operation, "desktop_interaction_argument_invalid");
        }

        // Encargo 115: a table given whole; only a grid's active cell takes it (CellBlockAsync).
        bool block = typing && CellBlock.Holds(text);
        // Práctica V5E061: one part of the field's text changed, never its whole value nor a list's entry; the old text
        // carries no control character either, as a typed one.
        if (replacing is not null && (replace || entry || block || replacing.Length > MaximumTypedText
            || replacing.Any(char.IsControl)))
            return ExternalJson.FailureBeforeEffect(operation, "desktop_interaction_argument_invalid");
        // A replaced value needs the field it replaces: the window's own focus may be a document.
        if (replace && index is null && !block)
            return ExternalJson.FailureBeforeEffect(operation, "input_field_not_replaceable");
        // Review of combos-galerias (finding 1): an entry of a list is chosen only in that list, by pattern, never typed;
        // without its box (or without the field reader) nothing is sent.
        if (entry && (index is null || window == 0 || _delivery is null || _fields is null))
            return ExternalJson.FailureBeforeEffect(operation, "input_field_not_found");

        // A field (index) is named only inside a looked-at window. A text carries no control character, with or without
        // a window (auditoría final 2, fila 11): a line break or a tab is a key of its own, and an Enter that sends what
        // was written goes through input.key.press and its confirmation, never inside a text.
        if ((typing && text.Length > MaximumTypedText) || (!typing && !VirtualKeys.TryGetValue(key!, out chord!))
            || (typing && !block && text.Any(char.IsControl)) || (index is not null && window == 0)
            || (block && entry))
            return ExternalJson.FailureBeforeEffect(operation, "desktop_interaction_argument_invalid");
        if (replacing is not null)
            return await ReplaceInFieldAsync(operation, replacing, text, window, index, cancellationToken)
                .ConfigureAwait(false);
        // uso-108 A9 (measured): a key sent to a window whose thread stopped pumping waited in its queue with a verified
        // receipt and arrived when it came back; held by the Ghost that stands for it after 5 s, it went nowhere, verified
        // too. Whatever window takes these keys, named or in front, it is asked first (VisibleControlSurface.NotResponding).
        nint asked = window != 0 ? window : _keyboard.Foreground().Window;
        try
        {
            if (VisibleControlSurface.NotResponding(asked, cancellationToken))
                return ExternalJson.FailureBeforeEffect(operation, VisibleControlSurface.WindowNotResponding);
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            return ExternalJson.FailureBeforeEffect(operation, "desktop_interaction_adapter_failed");
        }

        // Review of uso-108: the check may have waited seconds for a busy window. Keys with no window named go to the window
        // in front, and it is the one asked about that takes them: a person who went to another one meanwhile does not get
        // them there.
        if (window == 0 && _keyboard.Foreground().Window != asked)
            return ExternalJson.FailureBeforeEffect(operation, "input_window_changed");
        if (block)
            return await CellBlockAsync(operation, text, window, index, replace, typingDeadline, cancellationToken).ConfigureAwait(false);
        // e75d (H1): after a look the model names cells by index, one value at a time, until a row the view does not list.
        if (typing && !replace && !entry && replacing is null && index is int cellIndex && window != 0
            && _fields?.ViewedAt(cellIndex) is { Kind: "DataItem" } && FirstCellTextOwed(window))
        {
            ActiveCell? activeNow = (await ActiveCellAsync(window, null, cancellationToken).ConfigureAwait(false)).Cell;
            return ExternalJson.FailureBeforeEffect(operation, FirstCellText) with
            {
                Result = ExternalJson.Create(writer =>
                {
                    writer.WriteStartObject();
                    writer.WriteNumber("version", 1);
                    writer.WriteString("next", ActiveCell.TableNext(
                        window, $"this call wrote nothing: index {cellIndex} is a cell of a sheet",
                        "For this one value alone, call it again exactly as before", activeNow));
                    writer.WriteEndObject();
                }),
            };
        }
        // Ajuste c3 (E017, live on the notebook): a text typed into a dialog whose focus was its «Guardar» button went by the
        // keyboard, and its letters were the dialog's access keys («G» pressed &Guardar); in the smoke of 31-10 the focus
        // was the navigation tree after a click on «Escritorio», the letters moved its selection and the text was told
        // completed with nothing read back. A common file dialog whose focus is on no edit control takes the text in its
        // name field, the one field it has for a name; any other window whose focus is a Win32 control that takes no text
        // (a button, a tree, a list…) gets nothing, and the receipt says where the focus is.
        if (typing && window != 0 && index is null && _delivery is not null && _focusOwed is null)
        {
            nint focusedControl = _delivery.Messages.FocusOf(window);
            string focusedClass = focusedControl == 0 ? string.Empty : _delivery.Messages.ClassName(focusedControl);
            if (!WindowsTextDelivery.IsEditClass(focusedClass) && _delivery.Messages.FileNameFieldOf(window) is var name and not 0)
                return await IntoFileNameAsync(operation, text, window, name, cancellationToken).ConfigureAwait(false);
            if (WindowsTextDelivery.TakesNoText(focusedClass))
                return await FocusNotAFieldAsync(operation, text, window, $"a control of class {focusedClass}",
                    writer => writer.WriteString("focusedClass", focusedClass), cancellationToken).ConfigureAwait(false);
        }
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
        if (replace && !_replacedByKeyboard)
            return ExternalJson.FailureBeforeEffect(operation, "input_field_not_replaceable");

        // Row A10: from here on the text goes by the keyboard, which has a pace (messages and values have none, and went
        // above). A text past the budget would stop half typed in the person's window: nothing is sent, and the receipt
        // says how much fits; a retry cannot type its beginning twice. Uso-108 (review, 2c): a rich field of a Chromium
        // surface has no other route (SetValue is not heard by the page, C9), so a long text there goes at the surface's
        // pace; a paste would replace what the person holds on the clipboard (a write of text drops every other format,
        // ClipboardContracts.cs) and it could not be given back.
        if (typing && text.Length > Math.Max(0, typingDeadline - Ticks()) / TypedCharacterMs && _onRenderSurface)
            _typingPace = WindowsDesktopKeyboard.SurfacePace;
        if (typing && Math.Max(0, typingDeadline - Ticks()) / (_typingPace > 0 ? SurfaceCharacterMs : TypedCharacterMs) is var fits
            && text.Length > fits)
        {
            return ExternalJson.FailureBeforeEffect(operation, "input_text_too_long_to_type") with
            {
                Result = ExternalJson.Create(writer =>
                {
                    writer.WriteStartObject();
                    writer.WriteNumber("charactersThatFit", fits);
                    writer.WriteNumber("charactersAsked", text.Length);
                    writer.WriteEndObject();
                }),
            };
        }

        IInputBurst? burst = null;
        // Uso-108, review of batch 2 (B1): the front is about to be taken for the key and given back after it.
        bool behind = window != 0 && !_keyboard.Holds(window);
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

            // Uso-108 (review, 2b): the empty field the step names, without the keyboard's focus: UI Automation puts it there
            // now the window is in front, and re-reads it. Not there, nothing goes (r25 review: the keyboard would write
            // wherever the focus is). The focus was asked of the window: an effect either way.
            if (typing && _focusFirst is { } focusField && !await FocusedAsync(window, focusField, cancellationToken).ConfigureAwait(false))
            {
                _ = burst.Restore();
                return ExternalJson.FailureAfterEffect(operation, "input_field_not_focused");
            }

            // The whole text selected and read back (the worker's «focusselect»), or nothing is typed over part of it.
            if (typing && _selectWhole && !await _fields!.SelectFocusedTextAsync(window, cancellationToken).ConfigureAwait(false))
            {
                _ = burst.Restore();
                return ExternalJson.FailureAfterEffect(operation, "input_field_not_replaceable");
            }

            // Encargo 36 (banco uso-b4c4, R11, R12, R13, S08): a window drawn by WPF or Chromium has one Win32 control, so
            // its focus is judged by UI Automation, in front and right before the first key: a text for no field of
            // it went to its menu bar, to a list row (whose letters moved the selection to another chat) or to a page's
            // document, and was told delivered. A focus read inside the window that takes no text gets nothing.
            if (typing && index is null && _fields is not null)
            {
                FocusRead? focus;
                try
                {
                    using JsonDocument? answer = await _fields.FocusKindAsync(window, cancellationToken).ConfigureAwait(false);
                    focus = DeclaredTextFieldPress.Read(answer);
                }
                catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
                {
                    _ = burst.Restore();
                    return ExternalJson.FailureBeforeEffect(operation, "desktop_interaction_adapter_failed");
                }

                if (focus is { Inside: true, TakesNoText: true } held)
                {
                    _ = burst.Restore();
                    return await FocusNotAFieldAsync(operation, text, window,
                        held.Name.Length > 0 ? $"{held.Kind} «{held.Name}»" : held.Kind, writer =>
                        {
                            writer.WriteStartObject("focused");
                            writer.WriteString("kind", held.Kind);
                            writer.WriteString("name", held.Name);
                            writer.WriteBoolean("readOnly", held.ReadOnly);
                            writer.WriteEndObject();
                        }, cancellationToken).ConfigureAwait(false);
                }
            }
        }

        var bursts = new LeasedBursts(burst);
        try
        {
            ExternalCapabilityReceipt sent = await SendInBurstAsync(operation, typing, key, text, chord, window, bursts,
                    cancellationToken, openedApplication, typingDeadline, behind)
                .ConfigureAwait(false);
            return typing && index is int named && window != 0
                ? await ConfirmedOrPendingAsync(operation, sent, window, named, cancellationToken).ConfigureAwait(false)
                : sent;
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
        long typingDeadline = long.MaxValue,
        bool behind = false)
    {
        DesktopForeground before = _keyboard.Foreground();
        if (before.Window == 0 || _keyboard.InputSize != (IntPtr.Size == 8 ? 40 : 28))
            return ExternalJson.FailureBeforeEffect(operation, "key_press_sendinput_failed");
        string sentToProcess = _keyboard.ProcessName(before.Window);
        // Encargo 33 (U45): a console's window, read before the first key, as the window's class tells it.
        bool console = typing && Infrastructure.ModelAids.On(Infrastructure.ModelAids.ConsoleTypedNext)
            && Windows.Win32WindowControlPlatform.IsConsoleClass(_keyboard.ClassName(before.Window));
        // v3 point 0: something may take the front back between fronting the window and the press (the person, or an
        // application opened behind that Windows activated late): the key is checked against the window right before
        // it goes, never sent to whatever holds the front now.
        if (window != 0 && !_keyboard.Holds(window))
            return ExternalJson.FailureBeforeEffect(operation, "input_window_changed");
        // agent-desktop gates right before sending (windows physical_target.rs); MS docs of SendInput: UIPI blocking shows
        // neither in its count nor in GetLastError. The provider asked before the wait for the pause: a window above BAXY
        // that took the front since (measured: a hidden window of GameInputSvc, 80 minutes) would get a key told delivered.
        if (_keyboard.RunsAbove(before.ProcessId) is string above)
            return ExternalJson.FailureBeforeEffect(operation, above);

        var effectBoundary = new ExternalEffectBoundary();
        // FT/proveedores goal (review of receipts): Ctrl+C or Ctrl+X as a key press was told done by the count of keys
        // Windows accepted, while clipboard.copy checks the clipboard; with nothing selected nothing was copied.
        bool copies = !typing && key is "ctrl_c" or "ctrl_x";
        uint clipboardBefore = copies ? _keyboard.ClipboardSequence() : 0;
        // Ajuste c3 (E017): a shortcut (Ctrl or Alt with another key) is watched on its window: whether it changed what a
        // shortcut changes (ShortcutChangedAsync), so a key the application has not (Ctrl+S in a Spanish Notepad, whose
        // «Guardar» is Ctrl+G) is not told back as a mute completed.
        WindowWitness? witnessBefore = !typing && !copies && Shortcut(chord) ? _keyboard.Witness(before.Window) : null;
        // Uso-108 (B2): a key that is no shortcut has no such witness: its window's image, right before it. Review of batch
        // 2 (B1): only of a window that holds the front and keeps it. One brought up for the key is just activated before it
        // and inactive after it: caption, focus ring and selection colour differ with no key at all, and an image taken
        // before the person's pause proves nothing either (ronda final 19, WindowsVisibleOcrLocator). Unproved, so unread.
        bool plainKey = !typing && !copies && !Shortcut(chord) && KeySurface is not null;
        VisibleControlSurface.CapturedWindow? imageBefore = plainKey && !behind
            ? await KeySurface!.BeforeAsync(before.Window, cancellationToken).ConfigureAwait(false)
            : null;
        long pressedAt = Environment.TickCount64;
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
                letGo += WindowsDesktopKeyboard.CharacterUnits(text, letGo);
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
        // Encargo 75 (R01): the grid's active cell before the first key, and whether it was already being edited.
        ActiveCell? cellBefore = typing || !Shortcut(chord)
            ? (await ActiveCellAsync(before.Window, null, cancellationToken).ConfigureAwait(false)).Cell
            : null;
        // Only a text of this adapter's still pending in that same cell is refused: what the person left being edited in a
        // cell is theirs to continue, and a cell no longer being edited has nothing pending.
        string? pendingBefore = cellBefore is { Editing: true } && _pendingCells.TryGetValue(before.Window, out PendingCell? heldCell)
            && heldCell.Address == cellBefore.Address ? heldCell.Text : null;
        if (pendingBefore is null)
            _pendingCells.TryRemove(before.Window, out _);
        // Encargo 115: the first text for a cell of this window says what a table is, once; the same call written again runs.
        if (typing && cellBefore is { Editing: false } first && FirstCellTextOwed(before.Window))
            return ExternalJson.FailureBeforeEffect(operation, FirstCellText) with
            {
                Result = ExternalJson.Create(writer =>
                {
                    writer.WriteStartObject();
                    writer.WriteNumber("version", 1);
                    ActiveCell.WriteCell(writer, "cell", first.Address, first.Value);
                    writer.WriteString("next", first.FirstTextNext(before.Window));
                    writer.WriteEndObject();
                }),
            };
        // The model may mean it (a name in two parts): the text refused for this pending one, written again, joins it.
        bool joins = typing && pendingBefore is not null && _pendingRefused.TryGetValue(before.Window, out string? refusedText) && refusedText == text;
        if (typing && pendingBefore is not null && !joins)
        {
            _pendingRefused[before.Window] = text;
            return ExternalJson.FailureBeforeEffect(operation, CellStillPending) with
            {
                Result = ExternalJson.Create(writer =>
                {
                    writer.WriteStartObject();
                    writer.WriteNumber("version", 1);
                    ActiveCell.WriteCell(writer, "cell", cellBefore!.Address, cellBefore.Value, pendingBefore);
                    writer.WriteString("next", cellBefore.RefusedNext(before.Window, pendingBefore));
                    writer.WriteEndObject();
                }),
            };
        }

        TypedMark? mark = readsBack ? _delivery?.Mark(before.Window, text.Length) : null;
        // Ajuste c3 (F09, M1 and M2: «zzqxprueba» typed into WhatsApp's and Discord's search, «editor de fotos» into the
        // Microsoft Store's, each told input_text_not_read_back while the next look read the field holding it): a field
        // drawn by Chromium or XAML has no Win32 mark, and its paragraph at the caret did not prove it (the Store's field
        // is of another process than its frame; a Chromium field's paragraph did not grow by the text). The field with
        // the keyboard's focus inside the window is read by its value, as a look reads it, before the first key.
        CaretText? valueBefore = readsBack && mark is null
            ? await FocusedValueAsync(before.Window, cancellationToken).ConfigureAwait(false)
            : null;
        // FT/proveedores goal (E2): a document that is no edit control (Word's «_WwG») has no Win32 mark, and its text
        // was never read back. Its paragraph at the caret is read by UI Automation instead, before the first key, of the
        // front's own process only. Ajuste c3 (F09): only where no whole value of a field was read.
        CaretText? caretBefore = readsBack && mark is null && valueBefore is not { Bounded: false }
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
        bool selectedByUia = false;
        FocusState? focusBefore = null;
        BrowserWitness? browsersBefore = null;
        Dictionary<long, int>? tabsBefore = null;
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

            // Encargo 98: Ctrl+A is another command in some languages (Abrir, in Windows 11's Notepad and Word in Spanish).
            // The focused text is asked of UI Automation and read back; only a focus that cannot answer takes the keys.
            if (key == "ctrl_a" && _fields is not null)
            {
                try
                {
                    selectedByUia = await _fields.SelectFocusedTextAsync(before.Window, cancellationToken).ConfigureAwait(false);
                }
                catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
                {
                    return ExternalJson.FailureAfterEffect(operation, "desktop_interaction_adapter_failed");
                }
            }

            // Encargo 100: the find key is another command in some languages, one of which sends the selected text to a web
            // search; a receipt would come too late for that. Where the window can be asked otherwise, or text is selected, it
            // does not go.
            if (key == "ctrl_f" && _fields is not null)
            {
                FindReach? reach;
                try
                {
                    reach = await _fields.FindReachAsync(before.Window, cancellationToken).ConfigureAwait(false);
                }
                catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
                {
                    return ExternalJson.FailureBeforeEffect(operation, "desktop_interaction_adapter_failed");
                }

                if (reach is { } held && (held.MenuBar || held.EditableDocument || held.Selected > 0))
                    return ExternalJson.FailureBeforeEffect(operation, FindKeyNotSent) with
                    {
                        Result = ExternalJson.Create(writer =>
                        {
                            writer.WriteStartObject();
                            WriteSentTo(writer, before, sentToProcess);
                            writer.WriteBoolean("keySent", false);
                            writer.WriteNumber("selectedCharacters", held.Selected);
                            writer.WriteString("next", FindKeyHeld);
                            writer.WriteEndObject();
                        }),
                    };
            }

            // Encargo 98: read before the key, what it can change with no window of its own.
            if (!selectedByUia && witnessBefore is not null && _fields is not null && key is not ("alt_tab" or "ctrl_shift_escape"))
            {
                try
                {
                    focusBefore = await _fields.FocusStateAsync(before.Window, cancellationToken).ConfigureAwait(false);
                }
                catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
                {
                    return ExternalJson.FailureBeforeEffect(operation, "desktop_interaction_adapter_failed");
                }
            }

            // Ajuste c3 (E017): a chord is held key by key now, so each key goes down only while the window still holds
            // the front and the person has not acted, as each typed character.
            if (selectedByUia)
            {
                expected = 0;
            }
            else
            {
                // Encargo 100: read last, right before the key: whatever a browser shows after it is this key's.
                if (witnessBefore is not null && key is not ("alt_tab" or "ctrl_shift_escape"))
                {
                    browsersBefore = _keyboard.Browsers();
                    try
                    {
                        if (browsersBefore is not null && _fields is not null)
                            tabsBefore = await browsersBefore.TabsBehindAsync(before.ProcessId, _fields.TabCountAsync, cancellationToken).ConfigureAwait(false);
                    }
                    catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
                    {
                        return ExternalJson.FailureBeforeEffect(operation, "desktop_interaction_adapter_failed");
                    }
                }

                accepted = _keyboard.PressChord(chord, KeepGoing);
            }
        }
        else if (window == 0)
        {
            accepted = _keyboard.TypeText(text, KeepGoing, _typingPace);
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
                        sent += WindowsDesktopKeyboard.CharacterUnits(text, start + sent);
                    return stays;
                }

                uint accepting = _keyboard.TypeText(text[start..], KeepTyping, _typingPace);
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
        bool effect = accepted > 0 || selectedByUia;
        // A failure once the keys went still names the window they were sent to.
        ExternalCapabilityReceipt SentFailure(string errorCode, CopiedFrom? copiedFrom = null) => effectBoundary.Failure(operation, errorCode, effect) with
        {
            Result = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                WriteSentTo(writer, before, sentToProcess);
                if (copiedFrom is { } read)
                {
                    WriteCopiedFrom(writer, read);
                    WriteSelectAllNext(writer, read, before.Title, before.Window);
                }
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

        // Read while the window still holds the front: given back to the person, the front would always differ.
        bool? windowChanged = witnessBefore is { } witnessed && !interrupted && verified && !selectedByUia
            ? (bool?)await ShortcutChangedAsync(before.Window, witnessed, cancellationToken).ConfigureAwait(false)
            : null;
        // Encargo 98: what the key really did, read while the window holds the front: Escape and Ctrl+Z go in this burst.
        ShortcutAftermath aftermath = windowChanged is bool changedAny && witnessBefore is { } witnessedKey
            && key is not ("alt_tab" or "ctrl_shift_escape")
            ? await AfterShortcutAsync(key!, before, witnessedKey, changedAny, focusBefore, browsersBefore, tabsBefore, bursts, KeepGoing, cancellationToken)
                .ConfigureAwait(false)
            : default;
        if (aftermath.DialogTitle is not null)
            windowChanged = true;
        // Encargo 75 (R01): read while the window still holds the front, as the worker reads the system's focus.
        (ActiveCell? cellAfter, string? cellLeftValue) = cellBefore is { } cellWas && !interrupted && verified
            ? await CellAfterAsync(before.Window, typing, cellWas, cancellationToken).ConfigureAwait(false)
            : (null, null);
        DesktopForeground after = _keyboard.Foreground();
        // Uso-111 (G8, live in Edge 156 and Chromium 140: «le escribí pero no pude comprobarlo» with the text there): the field
        // is read through the window's keyboard focus, and with the front already given back the focus is another window's
        // (focus_window_mismatch), so every text for a window that was not in front said not read back. Read while it is held.
        bool readBeforeGivingBack = typing && verified && !interrupted && after.ProcessId == before.ProcessId;
        if (readBeforeGivingBack)
            AwaitTaken((int)(accepted / 2));
        string? landed = null;
        bool editReadBack = false;
        (bool ReadBack, bool Bounded) valueRead = default;
        (bool ReadBack, bool Bounded) caretRead = default;
        if (readBeforeGivingBack)
        {
            editReadBack = mark is { } typedMark && _delivery!.ReadsBack(typedMark, text, out landed);
            // Ajuste c3 (F09): the focused field's value read again (the same field: the window's focus), a settle apart.
            if (_selectWhole)
            {
                (bool read, bool bounded, _) = await WholeValueAsync(before.Window, text, cancellationToken).ConfigureAwait(false);
                valueRead = (read, bounded);
            }
            else if (valueBefore is { } value)
            {
                (bool read, bool bounded, _) = await ReadsBackAsync(
                    token => FocusedValueAsync(before.Window, token), value, text, cancellationToken).ConfigureAwait(false);
                valueRead = (read, bounded);
            }
            // FT/proveedores goal (E2): the paragraph at the caret read again by UI Automation; a read that fails leaves
            // the text not read back, as before.
            if (caretBefore is { } caret && !valueRead.ReadBack)
            {
                (bool read, bool bounded, _) = await CaretReadsBackAsync(before, caret, text, cancellationToken)
                    .ConfigureAwait(false);
                caretRead = (read, bounded);
            }
        }
        // Given back before the receipt, which says whether it was.
        bool? restored = bursts.Current is null ? null : bursts.Restore();
        // A screen copy shows what covers the window: only while it still holds the front.
        KeySurfaceVerdict surface = imageBefore is { } image && !interrupted && verified
            ? await KeySurface!.ChangedAsync(image, pressedAt, () => _keyboard.Holds(before.Window), cancellationToken)
                .ConfigureAwait(false)
            : KeySurfaceVerdict.Unknown;
        bool surfaceChanged = surface == KeySurfaceVerdict.Changed;
        // Measured with real keys: an arrow taken by a window that animates read «la ventana no cambió» from its tree.
        _keyImageUnread = plainKey && surface == KeySurfaceVerdict.Unknown;
        string stopped = refusedLater
            ?? (userActed ? "input_user_interrupted" : outOfTime ? "input_text_time_exhausted" : "input_window_changed");
        // Encargo 100: first of all: what opened in a browser is the one that can take the person's text out.
        if (aftermath.BrowserTitle is { } browser)
        {
            int selection = focusBefore?.SelectedLength ?? 0;
            return SentFailure(ShortcutOpenedBrowser) with
            {
                Result = ExternalJson.Create(writer =>
                {
                    writer.WriteStartObject();
                    WriteSentTo(writer, before, sentToProcess);
                    writer.WriteStartObject("browserOpened");
                    writer.WriteString("title", browser);
                    writer.WriteBoolean("closed", aftermath.BrowserClosed);
                    writer.WriteEndObject();
                    writer.WriteNumber("selectedCharacters", selection);
                    writer.WriteString("next", ShortcutTookAsBrowser(browser, aftermath.BrowserClosed, selection));
                    writer.WriteEndObject();
                }),
            };
        }

        // Before an interruption's code: a format left on the person's text, or a dialog over it, is what they need told.
        if (aftermath.FormatChanged)
            return SentFailure(ShortcutChangedFormat) with
            {
                Result = ExternalJson.Create(writer =>
                {
                    writer.WriteStartObject();
                    WriteSentTo(writer, before, sentToProcess);
                    writer.WriteBoolean("formatChanged", true);
                    writer.WriteBoolean("formatUndone", aftermath.FormatUndone);
                    writer.WriteString("next", ShortcutTookAsFormat(aftermath.FormatUndone, aftermath.FormatWhat ?? "format"));
                    writer.WriteEndObject();
                }),
            };
        if (aftermath.DialogTitle is { } opened && OpensNoWindow(key))
            return SentFailure(ShortcutOpenedDialog) with
            {
                Result = ExternalJson.Create(writer =>
                {
                    writer.WriteStartObject();
                    WriteSentTo(writer, before, sentToProcess);
                    WriteDialogOpened(writer, opened, aftermath.DialogClosed);
                    writer.WriteString("next", ShortcutTookAsAnother(opened, aftermath.DialogClosed));
                    writer.WriteEndObject();
                }),
            };
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
                return SentFailure("clipboard_not_changed",
                    await CopiedFromAsync(before, cancellationToken).ConfigureAwait(false));
        }
        // Rule 3: Windows accepting every event proves the keys went in, not that the text reached the field meant. A text
        // with no window named is verified by its read-back alone.
        if (!readBeforeGivingBack)
            AwaitTaken((int)(accepted / 2));
        (bool valueReadBack, bool valueBounded) = valueRead;
        (bool caretReadBack, bool caretBounded) = caretRead;
        bool readBack = editReadBack || valueReadBack || caretReadBack;
        // A named window's text is held to its read-back only where one could be taken (a mark, a field's value or a
        // caret read before the first key); with no window named (F004) or for the opened application, the read-back is
        // the proof.
        bool heldToReadBack = window == 0 || openedApplication || mark is not null || valueBefore is not null
            || caretBefore is not null || _selectWhole;
        string? unread = readsBack && heldToReadBack && !readBack ? "input_text_not_read_back" : null;
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteBoolean("ok", unread is null);
            if (unread is not null && _wholeRead is { } stayed)
                writer.WriteString("fieldNow", WindowsTextDelivery.ValueNow(stayed));
            // CU12 (auditoría final 2): what Windows accepted (SendInput's count), delivered to the window in front;
            // what the control did with it is read only for a text with no window named («readBack»).
            writer.WriteBoolean("delivered", effect);
            writer.WriteString("action", typing ? "text" : "key");
            if (key is null)
                writer.WriteNull("key");
            else
                writer.WriteString("key", key);
            writer.WriteNumber("textLength", text.Length);
            writer.WriteString("method", selectedByUia ? "ui_automation" : "keyboard");
            if (selectedByUia)
                writer.WriteString("selectedBy", "ui_automation");
            writer.WriteNumber("acceptedEvents", accepted);
            writer.WriteNumber("expectedEvents", expected);
            writer.WriteNumber("inputSize", _keyboard.InputSize);
            writer.WriteNumber("lastWin32Error", lastError);
            writer.WriteNumber("foregroundProcessIdBefore", before.ProcessId);
            writer.WriteNumber("foregroundProcessIdAfter", after.ProcessId);
            WriteSentTo(writer, before, sentToProcess);
            if (windowChanged is bool shortcutChanged)
            {
                writer.WriteBoolean("windowChanged", shortcutChanged);
                if (!shortcutChanged && Infrastructure.ModelAids.On(Infrastructure.ModelAids.ShortcutUnchangedNext))
                    writer.WriteString("next", ShortcutUnchanged);
            }

            if (aftermath.DialogTitle is { } left)
                WriteDialogOpened(writer, left, closed: false);
            if (surfaceChanged)
                writer.WriteBoolean("surfaceChanged", true);
            // Encargo 75 (R01): a key that moved the active cell was read back by the cell it reached.
            bool cellMoved = !typing && cellAfter is { } reached && cellBefore is { } cellLeftBy && reached.Moved(cellLeftBy);
            if (readsBack)
                writer.WriteBoolean("readBack", readBack);
            else if (cellMoved)
                writer.WriteBoolean("readBack", true);
            if (cellMoved)
                ActiveCell.WriteCell(writer, "cellLeft", cellBefore!.Address, cellLeftValue ?? string.Empty);
            string? pendingNow = typing && cellAfter is { Editing: true } ? (joins ? pendingBefore : null) + text : null;
            if (cellAfter is not null && (typing || cellMoved))
                ActiveCell.WriteCell(writer, "cell", cellAfter.Address, cellAfter.Value, pendingNow);
            // FT/proveedores goal (E2): a paragraph read cut at its bound (CaretReadableText) proves nothing, and says so.
            if (caretBefore is not null || valueBefore is not null)
                writer.WriteBoolean("readBackBounded", caretBounded || valueBounded);
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
            // Row C4: a key has no read-back, and the window just brought up had not taken the keyboard when its wait ran
            // out; a text's read-back already says what arrived.
            if (!typing && bursts.Current is { KeysNotConfirmed: true })
                writer.WriteBoolean("keysNotConfirmed", true);
            writer.WriteString("authority", selectedByUia ? "uia_textpattern_selection_postread"
                : focusAt is not null ? "uia_focus_reread_and_win32_sendinput"
                : editReadBack ? "win32_sendinput_and_edit_text_reread"
                : valueReadBack ? "win32_sendinput_and_uia_value_reread"
                : caretReadBack ? "win32_sendinput_and_uia_text_reread"
                : "win32_sendinput_return_count");
            if (unread is null)
                writer.WriteNull("error");
            else
                writer.WriteString("error", unread);
            // Práctica V5E023: where the text read back landed in what the edit control held.
            if (landed is not null)
                writer.WriteString("landed", landed);
            // Noche NB r1, hallazgo 5: whether the edit control read back holds text besides the one typed.
            if (editReadBack && mark is { } marked)
                writer.WriteBoolean("otherTextInField", marked.Expected > text.Length);
            string? typedInto = typing && (window == 0 || openedApplication)
                && Infrastructure.ModelAids.On(Infrastructure.ModelAids.TypedTargetNext)
                    ? TypedInto(before.Title, sentToProcess, window == 0, readBack)
                    : null;
            if (console)
                writer.WriteBoolean("commandRun", false);
            // The console's fact first: measured with the real model, Enter right after the text 15 of 15 (9 without).
            string? next = console ? (typedInto is null ? ConsoleTyped : ConsoleTyped + "; " + typedInto) : typedInto;
            // The call first: what ends the cell comes before anything else this receipt says.
            if (typing && cellAfter is { Editing: true } pending)
            {
                string ends = pending.PendingNext(before.Window, text);
                next = next is null ? ends : ends + "; " + next;
            }

            if (next is not null)
                writer.WriteString("next", next);
            writer.WriteEndObject();
        });
        _pendingRefused.TryRemove(before.Window, out _);
        if (typing && cellAfter is { Editing: true } pendingCell)
            _pendingCells[before.Window] = new PendingCell(pendingCell.Address, (joins ? pendingBefore : null) + text);
        else
            _pendingCells.TryRemove(before.Window, out _);
        // A text with no window named whose read-back did not find it: its keys went in, what they wrote is unknown.
        return unread is null
            ? ExternalJson.Success(operation, result, effect)
            : new ExternalCapabilityReceipt(operation, effect, false, result, unread) { EffectMayHaveOccurred = true };
    }

    // Ajuste c3 (E017): Ctrl or Alt held with another key, a shortcut (Alt+Tab is one too: its change is the front).
    internal static bool Shortcut(IReadOnlyList<ushort> chord) =>
        chord.Count > 1 && chord.Any(static key => key is 0x11 or 0x12);

    internal const string ShortcutOpenedDialog = "shortcut_opened_dialog";

    internal const string ShortcutChangedFormat = "shortcut_changed_format";

    internal const string ShortcutOpenedBrowser = "shortcut_opened_browser";

    internal const string FindKeyNotSent = "find_key_not_sent";

    internal const int ShortcutWaitMs = 1000;
    private const int ShortcutPollMs = 100;

    internal const string ShortcutUnchanged = "nothing of the window changed after this shortcut (its title, a dialog or "
        + "menu opened, its enabled state, the window in front): a shortcut that only edits the content changes none of "
        + "that, but one meant to open, save or close did not; the application may use another key in its language. Its "
        + "menus show their own shortcuts in a look while open ([atajo …]); a menu entry is pressed by its label "
        + "(input_visible_click) when its key is not one input_key_press sends; there, this key may have run another "
        + "command on the content, such as a format, which nothing here reads";

    // Encargo 98: keys whose purpose opens no window of the application: a dialog after one is another command's.
    private static bool OpensNoWindow(string? key) =>
        key is "ctrl_a" or "ctrl_end" or "ctrl_home" or "ctrl_l" or "ctrl_t" or "ctrl_v" or "ctrl_z";

    private static string ShortcutTookAsAnother(string title, bool closed) =>
        $"this key did not do what it is for here: the window took it as another command and opened «{title}», "
        + $"{(closed ? "which was closed again" : "which is still open")}; its menus show their own shortcuts in a look "
        + "while open ([atajo …]), and a menu entry is pressed by its label (input_visible_click)";

    private static void WriteDialogOpened(Utf8JsonWriter writer, string title, bool closed)
    {
        writer.WriteStartObject("dialogOpened");
        writer.WriteString("title", title);
        writer.WriteBoolean("closed", closed);
        writer.WriteEndObject();
    }

    // Encargo 98: keys none of whose purposes is a format (Word in Spanish, measured: Ctrl+S underlines, Ctrl+T centers,
    // Ctrl+K italics, Ctrl+H indents). The ones that edit the text (Ctrl+X, Ctrl+V, Ctrl+Z) or select it stay out.
    private static bool ChangesNoFormat(string? key) =>
        key is "ctrl_f" or "ctrl_h" or "ctrl_k" or "ctrl_l" or "ctrl_o" or "ctrl_s" or "ctrl_shift_s" or "ctrl_t" or "ctrl_w";

    // Measured with the real model: naming office_format_apply here took a save asked by its key to that call, 6 of 10 as an order and
    // 2 of 10 as a condition, and live it left a text underlined with nothing said. With only what changed, 0 of 10, and all 30 replies
    // said what was not done. A format asked by a key that took it is said not done, not given (0 of 20).
    private static string ShortcutTookAsFormat(bool undone, string changed) =>
        $"this key did not do what it is for here: the window took it as another command, which changed the {changed} of the text it "
        + "acted on, " + (undone ? "and that was undone, so the text is as it was; what the person asked was not done" : "and it is still changed");

    // Measured with the real model on the decisions bench (25 samples per text): a text that sent it to the window's menus had it
    // press the web search entry 15 of 25, 19 of 25 with a warning that named it, 0 of 25 with no menu and no web in the text.
    internal const string FindKeyHeld = "this key was not sent, and nothing was searched or changed. No find box opened, so a text typed now "
        + "goes into the person's own text. To find a word in this window, read its text with a look with includeText "
        + "(input_visible_controls) and say where the word is";

    private static string ShortcutTookAsBrowser(string title, bool closed, int selected) =>
        "this key did not do what it is for here: it opened a browser ("
        + (title.Length > 0 ? $"«{title}», " : "")
        + (closed ? "which was closed again" : "which is still open") + "). Tell the person that "
        + (selected > 0 ? $"their {selected} selected characters" : "the word at the caret")
        + " may have gone out to the web in its address, and that closing it does not take that back";

    private readonly record struct ShortcutAftermath(
        string? DialogTitle, bool DialogClosed, bool FormatChanged, bool FormatUndone, string? BrowserTitle = null, bool BrowserClosed = false,
        string? FormatWhat = null);

    /// <summary>
    /// Encargo 98: what a shortcut really did where the language of the application decides it. A dialog it raised, a window of
    /// its own (closed as its Cancel) or one drawn inside the window (closed with Escape), is said; a key not meant to open any
    /// closes it, so it is not left over the person's document. A format it changed on the selection is undone with Ctrl+Z, a
    /// key every language measured keeps, and read back. Encargo 100: what it opened in a browser goes first, closed and said.
    /// </summary>
    private async ValueTask<ShortcutAftermath> AfterShortcutAsync(
        string key,
        DesktopForeground sentTo,
        WindowWitness witness,
        bool windowChanged,
        FocusState? focusBefore,
        BrowserWitness? browsersBefore,
        Dictionary<long, int>? tabsBefore,
        LeasedBursts bursts,
        Func<bool> keepGoing,
        CancellationToken cancellationToken)
    {
        nint window = sentTo.Window;
        if (browsersBefore is not null
            && await BrowserWitness.AwaitOpenedAsync(
                () => _keyboard.BrowserSince(browsersBefore, sentTo.ProcessId), tabsBefore, _fields is null ? null : _fields.TabCountAsync, 0, cancellationToken)
                .ConfigureAwait(false) is { } opened)
        {
            bool shut = await CloseBrowserOpenedAsync(opened, window, () => bursts.Current is { UserActed: true }, cancellationToken)
                .ConfigureAwait(false);
            return new ShortcutAftermath(null, false, false, false, opened.Title, shut);
        }

        if (windowChanged && await RaisedByShortcutAsync(window, witness, cancellationToken).ConfigureAwait(false) is { } raised)
            return new ShortcutAftermath(raised.Title, OpensNoWindow(key) && _keyboard.CloseRaised(raised.Window), false, false);
        if (focusBefore is null || _fields is null
            || await _fields.FocusStateAsync(window, cancellationToken).ConfigureAwait(false) is not { } focus)
            return default;
        if (focus.InnerWindow is { } inner && inner != focusBefore.InnerWindow)
        {
            if (!OpensNoWindow(key))
                return new ShortcutAftermath(inner, false, false, false);
            bool Gone(FocusState now) => now.InnerWindow != inner;
            bool closed = (await _fields.CloseFocusedDialogAsync(window, cancellationToken).ConfigureAwait(false)
                    && await FocusReachesAsync(window, Gone, cancellationToken).ConfigureAwait(false))
                || (_keyboard.PressChord([0x1B], keepGoing) == 2
                    && await FocusReachesAsync(window, Gone, cancellationToken).ConfigureAwait(false));
            return new ShortcutAftermath(inner, closed, false, false);
        }

        // Another element or another selection holds other attributes, and Ctrl+Z could undo something of the person's.
        if (!ChangesNoFormat(key) || focusBefore.Format is not { } format || focus.Format is null || focus.Format == format
            || focus.Place != focusBefore.Place)
            return default;
        // Encargo 100: Ctrl+Z only for what this key just did. With the text changed too, it was not this key alone (the person
        // typed, or the command did more), and the top of the undo is not known to be its own.
        string changed = FocusState.FormatChange(format, focus.Format);
        if (focus.Content != focusBefore.Content || _keyboard.PressChord([0x11, 0x5A], keepGoing) != 4)
            return new ShortcutAftermath(null, false, true, false, FormatWhat: changed);
        // Exactly what was there, or the undo took something else (a format with no undo of its own leaves the person's last
        // edit on top): the redo gives that back, and the format is said still changed.
        bool undone = await FocusReachesAsync(window, now => now.Format == format && now.Content == focusBefore.Content, cancellationToken)
            .ConfigureAwait(false);
        if (!undone)
            _ = _keyboard.PressChord([0x11, 0x59], keepGoing);
        return new ShortcutAftermath(null, false, true, undone, FormatWhat: changed);
    }

    /// <summary>
    /// Encargo 100: its own window goes with WM_CLOSE; a tab, with its browser's Ctrl+W, and only while that window holds the front
    /// (brought up for this, and the front given back) and its tabs can be counted: one less, or it is said still open. Whatever
    /// opened while the person acted may be theirs.
    /// </summary>
    private async ValueTask<bool> CloseBrowserOpenedAsync(BrowserOpened opened, nint window, Func<bool> personActed, CancellationToken cancellationToken)
    {
        if (opened.Window == 0 || personActed())
            return false;
        bool closed = false;
        if (opened.OwnWindow)
        {
            closed = _keyboard.CloseRaised(opened.Window);
        }
        else
        {
            _ = _keyboard.GiveFront(opened.Window);
            if (_keyboard.Holds(opened.Window) && _fields is not null
                && await _fields.TabCountAsync(opened.Window, cancellationToken).ConfigureAwait(false) is int tabs)
                closed = _keyboard.PressChord([0x11, 0x57], () => !personActed() && _keyboard.Holds(opened.Window)) == 4
                    && await TabsReachAsync(opened.Window, tabs - 1, cancellationToken).ConfigureAwait(false);
        }

        _ = _keyboard.GiveFront(window);
        return closed;
    }

    private async ValueTask<bool> TabsReachAsync(nint window, int tabs, CancellationToken cancellationToken)
    {
        for (int waited = 0; ; waited += ShortcutPollMs)
        {
            if (await _fields!.TabCountAsync(window, cancellationToken).ConfigureAwait(false) == tabs)
                return true;
            if (waited >= RaisedWaitMs)
                return false;
            await Task.Delay(ShortcutPollMs, cancellationToken).ConfigureAwait(false);
        }
    }

    private async ValueTask<bool> FocusReachesAsync(nint window, Func<FocusState, bool> reached, CancellationToken cancellationToken)
    {
        for (int waited = 0; ; waited += ShortcutPollMs)
        {
            if (await _fields!.FocusStateAsync(window, cancellationToken).ConfigureAwait(false) is { } now && reached(now))
                return true;
            if (waited >= FocusReachWaitMs)
                return false;
            await Task.Delay(ShortcutPollMs, cancellationToken).ConfigureAwait(false);
        }
    }

    private const int FocusReachWaitMs = 500;

    // Measured live: a «Guardar como» cold takes past 500 ms to show after the window turned disabled.
    private const int RaisedWaitMs = 1500;

    // Encargo 98: the window turns disabled or the front moves a moment before its dialog shows: looked at while something
    // other than its title changed, for RaisedWaitMs at most.
    private async ValueTask<RaisedWindow?> RaisedByShortcutAsync(nint window, WindowWitness before, CancellationToken cancellationToken)
    {
        for (int waited = 0; ; waited += ShortcutPollMs)
        {
            if (_keyboard.RaisedSince(before, window) is { } raised)
                return raised;
            if (waited >= RaisedWaitMs || _keyboard.Witness(window) is not { } now
                || (now.Enabled == before.Enabled && now.Windows == before.Windows && now.Front == before.Front))
                return null;
            await Task.Delay(ShortcutPollMs, cancellationToken).ConfigureAwait(false);
        }
    }

    // Ajuste c3 (E017): whether the window's witness changed within ShortcutWaitMs of the shortcut (a window gone is a
    // change: Ctrl+W closed it).
    private async ValueTask<bool> ShortcutChangedAsync(nint window, WindowWitness before, CancellationToken cancellationToken)
    {
        for (int waited = 0; ; waited += ShortcutPollMs)
        {
            if (_keyboard.Witness(window) is not { } now || now != before)
                return true;
            if (waited >= ShortcutWaitMs)
                return false;
            await Task.Delay(ShortcutPollMs, cancellationToken).ConfigureAwait(false);
        }
    }

    // Noche NB r1, hallazgo 5 (T5-bloc: a window number that is no window, told «no encontré el campo de texto»): the
    // window asked and that it was not found, so the reply can tell it apart from a field not found in a window there.
    private static ExternalCapabilityReceipt WindowNotFound(string operation, nint window) =>
        new(operation, false, false, ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("window", window);
            writer.WriteBoolean("windowFound", false);
            writer.WriteEndObject();
        }), "input_window_not_found");

    // The entries a combo's list showed, as the worker read them.
    private static IReadOnlyList<string> Entries(JsonElement root) =>
        root.TryGetProperty("entries", out JsonElement entries) && entries.ValueKind == JsonValueKind.Array
            ? [.. entries.EnumerateArray().Where(entry => entry.ValueKind == JsonValueKind.String)
                .Select(entry => entry.GetString()!)]
            : [];

    // Encargo 33 (U45, banco de uso): «hostname» typed into a terminal came back with readBack true and nothing more; the
    // model then looked at the window instead of pressing Enter, or asked the person whether to press it. A console's
    // line runs only with Enter, a call of its own that the key press's preflight (KeyWindowReader, K-2 refinada)
    // confirms with the person in Normal mode.
    internal const string ConsoleTyped = "the text was typed on the command line of a console and not run: running "
        + "it is pressing Enter, another call (input_key_press with key enter) that BAXY confirms with the person by "
        + "itself when its mode asks for that, so it is not asked in words";

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
        where = readBack ? where : where + "; it was not read back there";
        // Holdout v5 (V5E066): the one look that gives another application's open window its number, and the text
        // typed again with it (never app_open, which may open a second window of it).
        return front
            ? where + "; the window of another application that is open is reached by looking at it by its name "
              + "(input_visible_controls with application), whose result gives that window's number, and typing the "
              + "text again as input_text_type with window set to that number"
            : where;
    }

    // Encargo 36: how many of the window's text fields a refusal names.
    private const int ListedTextFields = 6;

    /// <summary>
    /// A text with no field named for a window whose keyboard focus takes no text (<paramref name="focused"/>, said as
    /// the view says a control), refused before any key: what holds the focus, the fields of that window that take text,
    /// by the index the model knows each by, and a «next» that begins with the call that types it into each (the rule
    /// measured in encargos 20 and 28: the call first), or with the look that numbers them when no view of that window
    /// was taken. The last view of the window is read again first, as after an act («after»): a page's fields may not
    /// have been in it (encargo 36, S08: Chromium listed them only once a UI Automation client had asked).
    /// </summary>
    private async ValueTask<ExternalCapabilityReceipt> FocusNotAFieldAsync(
        string operation, string text, nint window, string focused, Action<Utf8JsonWriter> writeFocus,
        CancellationToken cancellationToken)
    {
        JsonElement? after = _fields is null
            ? null
            : await _fields.AfterActAsync(window, cancellationToken).ConfigureAwait(false);
        ViewedTextField[] fields = [.. (_fields?.TextFieldsOf(window) ?? []).Take(ListedTextFields)];
        string process = _keyboard.ProcessName(window);
        var refused = new ExternalCapabilityReceipt(operation, false, false, ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("window", window);
            writeFocus(writer);
            writer.WriteStartArray("textFields");
            foreach (ViewedTextField field in fields)
            {
                writer.WriteStartObject();
                writer.WriteNumber("index", field.Index);
                writer.WriteString("kind", field.Kind);
                writer.WriteString("name", field.Name);
                writer.WriteEndObject();
            }

            writer.WriteEndArray();
            if (Infrastructure.ModelAids.On(Infrastructure.ModelAids.FocusNotAFieldNext))
                writer.WriteString("next", FocusNotAFieldNext(window, process, text, focused, fields));
            writer.WriteEndObject();
        }), "input_focus_not_a_field");
        return after is { } seen ? WindowsVisibleControlAdapter.WithAfter(refused, seen) : refused;
    }

    internal static string FocusNotAFieldNext(
        nint window, string process, string text, string focused, IReadOnlyList<ViewedTextField> fields)
    {
        string nothing = $"nothing was typed: the window's keyboard focus is on {focused}, which takes no text (its keys "
            + "would press its access keys or move its selection)";
        if (fields.Count == 0)
            return $"{Baxy.Kernel.Operations.WireNames.Call("input.visible.controls", new() { ["application"] = process })} numbers the "
                + "window's fields, and input_text_type with this window and the index of the field types the text "
                + "there; " + nothing;
        IEnumerable<string> calls = fields.Select(field =>
            $"{Baxy.Kernel.Operations.WireNames.Call("input.text.type", new() { ["window"] = (long)window, ["index"] = field.Index, ["text"] = text })} "
            + $"types it into {field.Kind} «{field.Name}»");
        return string.Join("; ", calls) + "; " + nothing;
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

    // A replacement typed over the whole selection: the focused field's value read again, a settle apart, must be the text
    // whole. What it held last is said when it is not (a field that completes what it takes, an old part left).
    private async ValueTask<(bool Found, bool Bounded, bool Unanswered)> WholeValueAsync(
        nint window, string text, CancellationToken cancellationToken)
    {
        for (int read = 0; read < CaretRereads; read++)
        {
            if (read > 0)
                await _keyboard.SettleAsync(cancellationToken).ConfigureAwait(false);
            if (await FocusedValueAsync(window, cancellationToken).ConfigureAwait(false) is not { } now)
                return (false, false, true);
            _wholeRead = now.Text;
            if (!now.Bounded && string.Equals(now.Text.TrimEnd('\r', '\n'), text, StringComparison.Ordinal))
                return (true, false, false);
        }

        return (false, false, false);
    }

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
    // (WindowsTextDelivery.CaretHolds), and whether a read was cut at its bound (the receipt says so). R6-NB-3: and
    // whether a read did not answer or was not made (cancelled), which proves nothing either way (Unanswered).
    private ValueTask<(bool ReadBack, bool Bounded, bool Unanswered)> CaretReadsBackAsync(
        DesktopForeground front, CaretText before, string text, CancellationToken cancellationToken) =>
        ReadsBackAsync(token => CaretTextAsync(front, token), before, text, cancellationToken);

    // Ajuste c3 (F09, M1 and M2): the value of the field with the keyboard's focus inside the window (the worker's
    // «focusvalue»), as a CaretText of unit «value» compared by CaretHolds; null when nothing answers or the read failed.
    // Nothing of the value leaves this side.
    // Encargo 75 (R01): the worker's «activecell» answer; no cell when nothing answers or no grid's cell is active.
    private async ValueTask<(ActiveCell? Cell, string? ValueAt)> ActiveCellAsync(
        nint window, (int Row, int Column)? at, CancellationToken cancellationToken)
    {
        if (_fields is null || window == 0 || !Infrastructure.ModelAids.On(Infrastructure.ModelAids.GridCellFacts))
            return (null, null);
        try
        {
            using JsonDocument? answer = await _fields.ActiveCellAsync(window, at, cancellationToken).ConfigureAwait(false);
            return answer is null ? (null, null) : (ActiveCell.Read(answer.RootElement), ActiveCell.ValueAt(answer.RootElement));
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            return (null, null);
        }
    }

    // The grid takes a moment after the key: read again, bounded, until the key's change shows (a text's editor open, a
    // key's cell moved). A cell that never shows it is said as read.
    private async ValueTask<(ActiveCell? Cell, string? ValueAt)> CellAfterAsync(
        nint window, bool typing, ActiveCell before, CancellationToken cancellationToken)
    {
        (ActiveCell? Cell, string? ValueAt) read = (null, null);
        for (int poll = 0; poll < CellPolls; poll++)
        {
            if (poll > 0)
                await Task.Delay(CellPollMs, cancellationToken).ConfigureAwait(false);
            read = await ActiveCellAsync(window, typing ? null : (before.Row, before.Column), cancellationToken)
                .ConfigureAwait(false);
            if (read.Cell is { } cell && (typing ? cell.Editing || cell.Value != before.Value : cell.Moved(before)))
                break;
        }

        return read;
    }

    internal const string CellStillPending = "input_cell_still_pending";

    private sealed record PendingCell(string Address, string Text);

    // Encargo 75 (R01): the text this adapter left pending over a grid's active cell, by window, until a key ends it.
    private readonly System.Collections.Concurrent.ConcurrentDictionary<nint, PendingCell> _pendingCells = new();

    private const int CellPolls = 5;
    private const int CellPollMs = 60;

    private async ValueTask<CaretText?> FocusedValueAsync(nint window, CancellationToken cancellationToken)
    {
        if (_fields is null || window == 0)
            return null;
        JsonDocument? answer;
        try
        {
            answer = await _fields.FocusedValueAsync(window, WindowsTextDelivery.CaretReadableText, cancellationToken)
                .ConfigureAwait(false);
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
                || !root.TryGetProperty("text", out JsonElement read) || read.ValueKind != JsonValueKind.String
                || !root.TryGetProperty("bounded", out JsonElement bounded)
                || bounded.ValueKind is not (JsonValueKind.True or JsonValueKind.False))
                return null;
            string text = read.GetString()!;
            bool cut = bounded.ValueKind == JsonValueKind.True || text.Length > WindowsTextDelivery.CaretReadableText;
            // A field's value has no selection read: one the text replaced makes the value grow by less than the text,
            // which CaretHolds never takes as typed. The field's identity goes in its unit, so a value read after the
            // keys is compared only with the same field's (the focus may have gone to another field holding text).
            string field = root.TryGetProperty("id", out JsonElement id) && id.ValueKind == JsonValueKind.String
                ? id.GetString()! : string.Empty;
            return new CaretText(text, "value " + field, cut, 0);
        }
    }

    // Banco de uso 03-11 (U27, «copia todo lo que dice el bloc de notas»): a copy with nothing selected failed as
    // clipboard_not_changed alone, and nothing said why. What was there to copy in the window in front: the selection's
    // length (by UI Automation, at the caret) and the focused field's text length; lengths only, nothing of the text
    // leaves this side. A length that could not be read is null. Encargo 17 (banco uso-cf8d, U27): Windows 11's Notepad's
    // text area is a document with no value, so a field's value gave no length; then the length of its text, read by its
    // TextPattern in the worker (FocusedTextLengthAsync), is the one said.
    private readonly record struct CopiedFrom(int? SelectionLength, int? TextLength, bool TextBounded);

    private async ValueTask<CopiedFrom> CopiedFromAsync(DesktopForeground front, CancellationToken cancellationToken)
    {
        CaretText? caret = await CaretTextAsync(front, cancellationToken).ConfigureAwait(false);
        int? selection = caret is { SelectionLength: >= 0 } selected ? selected.SelectionLength : null;
        CaretText? value = await FocusedValueAsync(front.Window, cancellationToken).ConfigureAwait(false);
        if (value is not null)
            return new(selection, value.Value.Text.Length, value.Value.Bounded);
        (int Length, bool Bounded)? measured = await FocusedTextLengthAsync(front.Window, cancellationToken)
            .ConfigureAwait(false);
        return new(selection, measured?.Length, measured is { Bounded: true });
    }

    private async ValueTask<(int Length, bool Bounded)?> FocusedTextLengthAsync(
        nint window, CancellationToken cancellationToken)
    {
        if (_fields is null || window == 0)
            return null;
        JsonDocument? answer;
        try
        {
            answer = await _fields.FocusedTextLengthAsync(window, WindowsTextDelivery.CaretReadableText, cancellationToken)
                .ConfigureAwait(false);
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
            return root.ValueKind == JsonValueKind.Object
                && root.TryGetProperty("ok", out JsonElement ok) && ok.ValueKind == JsonValueKind.True
                && root.TryGetProperty("length", out JsonElement length) && length.ValueKind == JsonValueKind.Number
                && length.TryGetInt32(out int characters)
                && characters >= 0
                && root.TryGetProperty("bounded", out JsonElement bounded)
                && bounded.ValueKind is JsonValueKind.True or JsonValueKind.False
                    ? (characters, bounded.ValueKind == JsonValueKind.True)
                    : null;
        }
    }

    private static void WriteCopiedFrom(Utf8JsonWriter writer, CopiedFrom read)
    {
        if (read.SelectionLength is int selection)
            writer.WriteNumber("selectionLength", selection);
        if (read.TextLength is not int length)
            return;
        writer.WriteNumber("focusedTextLength", length);
        // A field longer than a read takes: its length is at least this.
        if (read.TextBounded)
            writer.WriteBoolean("focusedTextBounded", true);
    }

    // Encargo 35 (bancos ab-d4-1d y uso-8ded, U27, 0 of 6): with selectionLength 0 and focusedTextLength 35 the model
    // answered «no había nada seleccionado» (or «copié, pero no pude comprobarlo») and never selected. Nothing selected in
    // a field that holds text: the next leads with the two calls that copy all of it, as one route, and ends with what this
    // call did (encargos 20, 28 and 34). Measured with the real model: «input_select_all selects…, and clipboard_copy then
    // copies them» was asked about every time; the route said as the copy it makes was followed.
    // Encargo 45 (banco ab-93-ce, U27): with the effect known (above), that route alone was also followed when the person
    // had asked for what they selected (20 of 27); said as what copies all of the text if that is what they asked
    // (OpenAI Model Spec: act on the request, ask when it is ambiguous), the model selected and copied in 12 of 12 asks
    // for all of it and in none of 27 for the selection.
    // Encargo 61 (banco de uso U45, diag-f11d c2 and c4): in a console that route fails (select_all_postcondition_not_verified)
    // and the model gave up with the output already read, so it is told what does keep that text. Windows Terminal: «If no
    // selection exists, the key chord is sent directly to the terminal». Measured with held-out phrases (7 × 5 seeds, with
    // the cwd of ShellCommandAdapter read in the home folder): 15/34 with the route, 20/35 with this said as a fact, 25/35
    // with the call first; the model filled in both values every time.
    private void WriteSelectAllNext(Utf8JsonWriter writer, CopiedFrom read, string? window, nint from)
    {
        if (read.SelectionLength != 0 || read.TextLength is not > 0)
            return;
        if (Infrastructure.ModelAids.On(Infrastructure.ModelAids.ConsoleTypedNext)
            && Windows.Win32WindowControlPlatform.IsConsoleClass(_keyboard.ClassName(from)))
        {
            string write = WireNames.Call("file.write", new() { ["path"] = "<the file>", ["text"] = "<what it showed>" });
            writer.WriteString("next", $"{write} writes what {WireNames.Of("input.visible.controls")} with includeText read "
                + "from this console; this call copied nothing: a console has no selection here and its Ctrl+C is its interrupt");
            return;
        }

        string characters = (read.TextBounded ? "at least " : "all ")
            + read.TextLength.Value.ToString(System.Globalization.CultureInfo.InvariantCulture) + " characters of the text"
            + (string.IsNullOrWhiteSpace(window) ? string.Empty : " in " + window);
        writer.WriteString("next", $"if the person asked for all of its text: {WireNames.Call("input.select.all", new())} and then "
            + $"{WireNames.Call("clipboard.copy", new())} copy {characters}; this call copied nothing: nothing was selected");
    }

    // FT/proveedores goal (E2), ajuste c3 (F09): whether a read taken before the keys, read again (up to CaretRereads
    // times, a settle apart), holds the typed text by CaretHolds.
    private async ValueTask<(bool ReadBack, bool Bounded, bool Unanswered)> ReadsBackAsync(
        Func<CancellationToken, ValueTask<CaretText?>> reread, CaretText before, string text,
        CancellationToken cancellationToken)
    {
        // A read cut before, or a selection the text replaced: no read after can prove it.
        if (before.Bounded || before.SelectionLength != 0)
            return (false, before.Bounded, false);
        bool bounded = false;
        bool unanswered = false;
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
                    unanswered = true;
                    break;
                }
            }

            if (await reread(cancellationToken).ConfigureAwait(false) is not { } after)
            {
                unanswered = true;
                break;
            }

            bounded |= after.Bounded;
            if (WindowsTextDelivery.CaretHolds(before, after, text))
                return (true, bounded, false);
        }

        return (false, bounded, unanswered);
    }

    /// <summary>
    /// Ajuste c3 (smoke of 31-10, live on the notebook): a text for a common file dialog whose focus is on no edit
    /// control, written whole into the dialog's name field by that edit control's messages (as typing over its selected
    /// name does, the write the dialog takes for the name it saves or opens) and read back there; the receipt says it went
    /// to that field (<c>intoField</c>). The keyboard's focus stays where it was: a key that follows (Enter) puts it on
    /// the name field first, as after a value set without the focus.
    /// </summary>
    private async ValueTask<ExternalCapabilityReceipt> IntoFileNameAsync(
        string operation, string text, nint window, nint nameField, CancellationToken cancellationToken)
    {
        WindowsTextDelivery delivery = _delivery!;
        WindowIdentity identity = delivery.Messages.Identity(window);
        if (!identity.Alive)
            return WindowNotFound(operation, window);
        DesktopForeground frontBefore = _keyboard.Foreground();
        FieldDelivery? written = await delivery.TypeAsync(identity, nameField, text, cancellationToken, replace: true)
            .ConfigureAwait(false);
        if (written is not { } done)
            return ExternalJson.FailureBeforeEffect(operation, "input_field_not_reachable");
        ExternalCapabilityReceipt receipt = FieldReceipt(operation, null, text, identity, frontBefore, done);
        if (!receipt.Verified)
            return receipt;
        _unfocusedValue = (identity, NativeControlId(nameField), _fields?.Clicks ?? 0, Ticks());
        return receipt with
        {
            Result = ExternalJson.Extended(receipt.Result, writer => writer.WriteString("intoField", "file_name")),
        };
    }

    // The identity UI Automation gives a control that is a window of its own: «42.» and its handle.
    private static string NativeControlId(nint hwnd) =>
        "42." + ((long)hwnd).ToString(System.Globalization.CultureInfo.InvariantCulture);

    // The control a viewed identity names when it is a window of its own («42.<hwnd>») of the step's window; 0 otherwise.
    private nint NativeControl(string controlId, nint window)
    {
        const string Prefix = "42.";
        return controlId.StartsWith(Prefix, StringComparison.Ordinal)
            && long.TryParse(controlId.AsSpan(Prefix.Length), System.Globalization.NumberStyles.None,
                System.Globalization.CultureInfo.InvariantCulture, out long handle)
            && handle > 0 && _delivery!.Messages.Belongs(window, (nint)handle)
                ? (nint)handle
                : 0;
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
            return WindowNotFound(operation, window);
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
        bool focusMoved = false;
        // r25: a named field its value and its messages did not reach takes the keyboard only when it has its focus.
        bool fieldFocused = false, insertion = index is not null && !replace;
        // Uso real 02-11 (encargo 2, A(b)): the field's text as the worker read it before anything was sent (its length,
        // -1 when not read, and whether it was all selected), said when it is not reached.
        int fieldLength = -1;
        bool fieldSelected = false;
        if (index is int position)
        {
            if (_fields is null || !SeenField(position, out nint viewed, out string controlId) || viewed != window)
                return ExternalJson.FailureBeforeEffect(operation, "visible_control_identity_stale");
            // Ajuste c3 (smoke of 31-10, live on the notebook): «sv1.txt» set by UI Automation's SetValue into a «Guardar
            // como» name field read back as set, and the dialog saved under its old name; the same field written by its
            // edit control's messages is the name it saves. A viewed field that is a Win32 edit control (or an editable
            // combo box, through its edit) takes the text by those messages, as typing writes it: over its selection
            // (all of it, with «replace», or when it is a file dialog's name field, whose text is the one name it
            // takes), never a document replaced whole.
            if (NativeControl(controlId, window) is var own and not 0 && delivery.Messages.EditOf(own) is var edit and not 0)
            {
                if (replace && WindowsTextDelivery.IsMultiline(delivery.Messages.Style(edit)))
                    return ExternalJson.FailureBeforeEffect(operation, "input_field_not_replaceable");
                replace |= delivery.Messages.FileNameFieldOf(window) == edit;
                FieldDelivery? written = await delivery.TypeAsync(identity, edit, text, cancellationToken, replace)
                    .ConfigureAwait(false);
                if (written is { } done)
                {
                    // Revision 1 of r24b: written without the keyboard's focus, the next key goes to this field first.
                    _unfocusedValue = done.Delivered && delivery.Messages.FocusOf(window) != edit
                        ? (identity, controlId, _fields.Clicks, Ticks())
                        : null;
                    return FieldReceipt(operation, key, text, identity, frontBefore, done);
                }
            }

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
                focusMoved = Flag(root, "focusMoved", false);
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
                // The worker asks before it touches the window (Get-Root): nothing was written.
                if (!ok && error == VisibleControlSurface.WindowNotResponding)
                    return ExternalJson.FailureBeforeEffect(operation, VisibleControlSurface.WindowNotResponding);
                // SetValue refused, its value read back as it was (uso-108, A4: one that raised after applying is told by
                // the worker as what it read): the field's own window may still take the text by messages.
                if (!ok && error != "field_setvalue_refused")
                    return effectBoundary.Failure(operation, error is { Length: > 0 } ? error : "field_no_receipt", true);
                // Uso real 02-11 (encargo 2, A): the item's own editor was open (a text not confirmed): nothing was written.
                if (Flag(root, "editPending", false))
                    return EditPending(operation, null);
                fieldLength = root.TryGetProperty("valueLength", out JsonElement heldValue)
                    && heldValue.ValueKind == JsonValueKind.Number && heldValue.TryGetInt32(out int heldLength)
                        ? heldLength
                        : -1;
                fieldSelected = Flag(root, "selected", false);
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
                        ChosenEntry(root), FieldNow: FieldNow(root), FieldUnchanged: Flag(root, "fieldUnchanged", false)), keeper, focusMoved);
                }

                // Ronda final 16 (regla 3): a list-only combo whose list was opened and closed without the entry
                // changed the window: an effect that may have occurred, never «nothing sent».
                if (Flag(root, "expanded", false))
                    return NoSuchEntry(operation, root) with { EffectMayHaveOccurred = true };

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
                bool readEmpty = root.TryGetProperty("valueLength", out JsonElement length)
                    && length.ValueKind == JsonValueKind.Number && length.TryGetInt32(out int held) && held == 0;
                if (replace && field != 0 && readEmpty)
                {
                    replace = false;
                }

                // Uso-108 (review, 2a, 2b, 3): that focus is known here. An empty field that has it (the worker read its
                // own HasKeyboardFocus) takes the keyboard's insertion, and one whose text lives in child elements (a
                // role=textbox of Chromium, which hears no SetValue) gets the focus from UI Automation first.
                bool inChildren = Flag(root, "textInChildren", false);
                bool notDocument = !(root.TryGetProperty("kind", out JsonElement readKind) && readKind.ValueKind == JsonValueKind.String
                    && readKind.GetString() == "Document");
                _fieldTouched |= Flag(root, "erased", false);
                _onRenderSurface = inChildren;
                // Opera GX 138, measured on an own instance (base: 0 of 12): its address bar's SetValue raises E_FAIL and
                // changes nothing, in front or behind, with the focus or without it, and the replacement was refused. Keys
                // reach it. Value unchanged after the raise (the worker read it), so nothing is doubled.
                if (replace && !ok && field == 0 && notDocument && !readEmpty && fieldLength > 0 && _fields is not null)
                {
                    _replacedByKeyboard = true;
                    _selectWhole = true;
                    _onRenderSurface = inChildren;
                    if (!fieldFocused)
                        _focusFirst = controlId;
                    return null;
                }

                if (field == 0 && readEmpty && notDocument && (fieldFocused || inChildren))
                {
                    _replacedByKeyboard = true;
                    replace = false;
                    if (!fieldFocused)
                        _focusFirst = controlId;
                    return null;
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

        if (window != 0 && !_onRenderSurface && RenderSurfaceClasses.All.Contains(delivery.Messages.ClassName(delivery.Messages.FocusOf(window))))
            _onRenderSurface = true;

        // Otherwise the keyboard would write wherever the window's focus is (a password, the page's search) and the
        // next Enter would send it: nothing is sent (r25 review, finding 1). A replacement is refused by the caller.
        ExternalCapabilityReceipt? unreached = insertion && !fieldFocused
            ? NotReachable(operation, fieldLength, fieldSelected)
            : null;
        if (field == 0)
            return unreached;
        FieldDelivery? typed = await delivery.TypeAsync(identity, field, text, cancellationToken, replace).ConfigureAwait(false);
        return typed is { } result
            ? FieldReceipt(operation, key, text, identity, frontBefore, result, keeper, focusMoved)
            : unreached;
    }

    /// <summary>
    /// Uso real 02-11 (encargo 2, A(b)): a field named by its index that holds text, neither all selected nor with the
    /// keyboard's focus, is not reached and nothing is sent. The receipt says what the worker read there before: whether
    /// it held text (<c>fieldHasText</c>, absent when its value was not read), whether that text was selected
    /// (<c>textSelected</c>), and that it had no focus (<c>fieldFocused</c>).
    /// </summary>
    private static ExternalCapabilityReceipt NotReachable(string operation, int length, bool selected) =>
        ExternalJson.FailureBeforeEffect(operation, "input_field_not_reachable") with
        {
            Result = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                if (length >= 0)
                    writer.WriteBoolean("fieldHasText", length > 0);
                writer.WriteBoolean("textSelected", selected);
                writer.WriteBoolean("fieldFocused", false);
                writer.WriteEndObject();
            }),
        };

    /// <summary>
    /// Uso real 02-11 (encargo 2, A): an item of a grid, list or tree whose own editor holds the keyboard's focus is in an
    /// edit not confirmed: what is written there becomes its value only when the edit is confirmed or the focus leaves
    /// it, and a value set meanwhile is lost then. Never verified: <c>input_edit_not_confirmed</c> with
    /// <c>editPending</c>, before any effect (<paramref name="typed"/> null: the edit was already open, nothing written)
    /// or after the text the keyboard typed (its receipt's facts kept, its «ok» and «error» replaced by the code).
    /// </summary>
    private static ExternalCapabilityReceipt EditPending(string operation, ExternalCapabilityReceipt? typed)
    {
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            if (typed?.Result is { ValueKind: JsonValueKind.Object } sent)
            {
                foreach (JsonProperty property in sent.EnumerateObject())
                {
                    if (property.Name is not ("ok" or "error" or "editPending"))
                        property.WriteTo(writer);
                }
            }

            writer.WriteBoolean("editPending", true);
            writer.WriteEndObject();
        });
        return typed is null
            ? ExternalJson.FailureBeforeEffect(operation, "input_edit_not_confirmed") with { Result = result }
            : new ExternalCapabilityReceipt(operation, typed.EffectObserved, false, result, "input_edit_not_confirmed")
            {
                EffectMayHaveOccurred = true,
            };
    }

    /// <summary>
    /// Uso real 02-11 (encargo 2, A): a text the keyboard typed for the field a step names (its value and its messages did
    /// not reach it) may sit in an editor that field opened for it, not in the field. The field is read again (nothing
    /// written): its own editor still open makes the receipt an edit pending (<see cref="EditPending"/>). A field not read
    /// again leaves the receipt as it was.
    /// </summary>
    private async ValueTask<ExternalCapabilityReceipt> ConfirmedOrPendingAsync(
        string operation, ExternalCapabilityReceipt typed, nint window, int index, CancellationToken cancellationToken)
    {
        if (!typed.Verified || _fields is null || _fields.ViewedAt(index) is not { Gone: false } seen
            || seen.Window != window || seen.ControlId.Length == 0)
            return typed;
        // Encargo 10 (punto 5): only a grid, list or tree item is edited in an editor put inside it, so only there can an
        // edit be still pending (Test-EditPending refuses any other kind). The kind is already known from the view that
        // handed the index out, so a plain field is confirmed without a second trip to the worker (its Find-ById).
        if (seen.Kind is { Length: > 0 } kind && kind is not ("DataItem" or "ListItem" or "TreeItem"))
            return typed;
        using JsonDocument? read = await _fields.FieldAsync(window, seen.ControlId, null, false, cancellationToken)
            .ConfigureAwait(false);
        return read is not null && Flag(read.RootElement, "editPending", false) ? EditPending(operation, typed) : typed;
    }

    /// <summary>
    /// Práctica V5E061 («cámbialo, era el miércoles, no el martes»: the new text went in at the caret, and «replace» is
    /// refused for a document): the one part <paramref name="replacing"/> of a field's text changed into
    /// <paramref name="text"/> by the field's own edit control (<see cref="WindowsTextDelivery.Replace"/>), never by the
    /// keyboard, whose typing would add the text at the caret. The field is the one of the last view the step names
    /// (<c>index</c>, read by the worker without writing anything: its own window, and whether it is a password or
    /// read-only), else the keyboard's focus of the window named, else of the window in front, as a text with no window
    /// goes there. Anything else (no edit control there, a text not read whole) is refused before anything is sent.
    /// </summary>
    private async ValueTask<ExternalCapabilityReceipt> ReplaceInFieldAsync(
        string operation, string replacing, string text, nint window, int? index, CancellationToken cancellationToken)
    {
        DesktopForeground frontBefore = _keyboard.Foreground();
        if (_delivery is not { } delivery)
            return ExternalJson.FailureBeforeEffect(operation, "input_field_not_readable");
        WindowIdentity identity = delivery.Messages.Identity(window != 0 ? window : frontBefore.Window);
        if (!identity.Alive)
            return window != 0
                ? WindowNotFound(operation, window)
                : ExternalJson.FailureBeforeEffect(operation, "input_window_not_found");
        nint field;
        if (index is int position)
        {
            if (_fields is null || !SeenField(position, out nint viewed, out string controlId) || viewed != window)
                return ExternalJson.FailureBeforeEffect(operation, "visible_control_identity_stale");
            // Only the field's description: no text is given to the worker, so nothing is written.
            using JsonDocument? answer = await _fields.FieldAsync(window, controlId, null, false, cancellationToken)
                .ConfigureAwait(false);
            if (answer is null)
                return ExternalJson.FailureBeforeEffect(operation, "field_no_receipt");
            JsonElement root = answer.RootElement;
            string? error = root.TryGetProperty("error", out JsonElement errorValue) && errorValue.ValueKind == JsonValueKind.String
                ? errorValue.GetString()
                : null;
            if (!root.TryGetProperty("ok", out JsonElement ok) || ok.ValueKind != JsonValueKind.True)
                return ExternalJson.FailureBeforeEffect(operation, error is "active_window_not_found" ? "visible_control_identity_stale"
                    : error is { Length: > 0 } ? error : "field_no_receipt");
            if (Flag(root, "readOnly", false) || Flag(root, "password", false) || !Flag(root, "enabled", true))
                return ExternalJson.FailureBeforeEffect(operation, "input_field_not_writable");
            field = root.TryGetProperty("nativeHwnd", out JsonElement native) && native.ValueKind == JsonValueKind.Number
                && native.TryGetInt64(out long hwnd) && hwnd > 0
                    ? (nint)hwnd
                    : 0;
        }
        else
        {
            field = delivery.Messages.FocusOf(identity.Window);
        }

        FieldDelivery? replaced = field == 0 ? null : delivery.Replace(identity, field, replacing, text);
        if (replaced is not { } done)
            return ExternalJson.FailureBeforeEffect(operation, "input_field_not_readable");
        if (done.Error is "input_text_replacing_not_found" or "input_text_replacing_ambiguous")
            return new ExternalCapabilityReceipt(operation, false, false, ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteString("replacing", replacing);
                writer.WriteNumber("occurrences", done.Occurrences);
                writer.WriteString("next", done.Occurrences == 0
                    ? $"«{replacing}» is not in the text of that field, read whole and compared exactly (capitals and "
                      + "accents included); nothing was changed"
                    : $"«{replacing}» is in the text of that field {done.Occurrences} times, so which one to change is "
                      + "not known; nothing was changed; a replacing with more of the words around the one meant is "
                      + "there once");
                writer.WriteEndObject();
            }), done.Error);
        return FieldReceipt(operation, null, text, identity, frontBefore, done);
    }

    /// <summary>
    /// Review of combos-galerias (findings 1 and 2): a closed list's entry named by the goal, chosen in the list box the
    /// view named (the worker's «field» with «entry»: its entry of that name selected by pattern, the selection and the
    /// box's value re-read). Never a text written into the box nor sent to its edit control or the keyboard: a list with
    /// no entry of that name changes nothing (<see cref="NoSuchEntry"/>).
    /// </summary>
    private async ValueTask<ExternalCapabilityReceipt> EntryToWindowAsync(
        string operation, string text, nint window, int index, DesktopForeground frontBefore, CancellationToken cancellationToken)
    {
        WindowIdentity identity = _delivery!.Messages.Identity(window);
        if (!identity.Alive)
            return WindowNotFound(operation, window);
        if (!SeenField(index, out nint viewed, out string controlId) || viewed != window)
            return ExternalJson.FailureBeforeEffect(operation, "visible_control_identity_stale");
        var effectBoundary = new ExternalEffectBoundary();
        JsonDocument? answer;
        try
        {
            effectBoundary.Cross(cancellationToken);
            answer = await _fields!.EntryAsync(window, controlId, text, cancellationToken).ConfigureAwait(false);
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
            if (!ok && error == VisibleControlSurface.WindowNotResponding)
                return ExternalJson.FailureBeforeEffect(operation, VisibleControlSurface.WindowNotResponding);
            if (!ok)
                return effectBoundary.Failure(operation, error is { Length: > 0 } ? error : "field_no_receipt", true);
            // Auditoría C9: no entry is called so (folded); nothing was chosen, and the list's entries go back as they read.
            if (!root.TryGetProperty("method", out JsonElement method) || method.ValueKind != JsonValueKind.String
                || method.GetString() != "select")
                return NoSuchEntry(operation, root) with { EffectMayHaveOccurred = Flag(root, "expanded", false) };
            bool whole = root.TryGetProperty("delivered", out JsonElement read) && read.ValueKind == JsonValueKind.True;
            // Ronda final: the entry already chosen (read before) is the state reached: nothing was chosen (changed:false).
            if (whole && root.TryGetProperty("alreadyReached", out JsonElement reached) && reached.ValueKind == JsonValueKind.True)
                return ExternalJson.Switched(operation, root.Clone(), effectObserved: false);
            string fieldClass = root.TryGetProperty("className", out JsonElement named) && named.ValueKind == JsonValueKind.String
                ? named.GetString() ?? string.Empty
                : string.Empty;
            return FieldReceipt(operation, null, text, identity, frontBefore, new FieldDelivery(
                "select", whole, true, whole ? null : "input_effect_not_verified", fieldClass, ChosenEntry(root),
                FieldNow: FieldNow(root)), keeper);
        }
    }

    /// <summary>
    /// Uso-108 (A3; agent-desktop windows/src/actions/select.rs:161-178, PR #256 and #517): the list as the worker read it. No
    /// entry read at all is no statement about the entries: <c>input_list_not_read</c>. Otherwise none of them is called
    /// so: <c>input_entry_not_found</c> with the entries it read, and whether they are not all (<c>truncated</c>, with
    /// <c>candidateCount</c> when it knows how many): the first 30, or a list it did not read to its end.
    /// </summary>
    private static ExternalCapabilityReceipt NoSuchEntry(string operation, JsonElement root)
    {
        if (Flag(root, "listNotRead", false))
            return ExternalJson.FailureBeforeEffect(operation, "input_list_not_read");
        IReadOnlyList<string> entries = Entries(root);
        int total = root.TryGetProperty("entriesTotal", out JsonElement all) && all.TryGetInt32(out int counted) ? counted : 0;
        if (entries.Count == 0 || !Flag(root, "entriesPartial", false))
            return WindowsVisibleControlAdapter.NotNamed(operation, "input_entry_not_found", entries, total > 0 ? total : null);
        return new ExternalCapabilityReceipt(operation, false, false, ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteBoolean("truncated", true);
            writer.WriteStartArray("candidates");
            foreach (string entry in entries)
                writer.WriteStringValue(entry);
            writer.WriteEndArray();
            writer.WriteEndObject();
        }), "input_entry_not_found");
    }

    // Uso-108 (B12): what the field holds when it does not match, as the worker read it; null when it said nothing.
    private static string? FieldNow(JsonElement root) =>
        root.TryGetProperty("fieldNow", out JsonElement now) && now.ValueKind == JsonValueKind.String ? now.GetString() : null;

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

    internal const string PasteNotReadBack = "paste_not_read_back";
    internal const string PasteNotReadable = "not_readable";

    // R6-NB-3: the clipboard's text and where it was marked before a clipboard.paste: the focused edit control of the
    // window in front (Edit) or, in a document that is no edit control, the paragraph at its caret (Caret).
    // ClipboardSequence: the clipboard's sequence when its text was read, to tell it is the one the keys pasted.
    private readonly record struct PasteMark(
        string Text, DesktopForeground Front, TypedMark? Edit, CaretText? Caret, uint ClipboardSequence);

    /// <summary>R6-NB-3: whether a paste's text was read back where it went (<c>Found</c> null: nothing there could be
    /// read), and where it landed in what that control held.</summary>
    internal readonly record struct PasteRead(bool? Found, string? Landed);

    /// <summary>
    /// R6-NB-3: the mark a typed text takes before its first key (SendInBurstAsync), taken for the clipboard's text before
    /// the paste's keys. Null when nothing could prove it after: no one-line clipboard text a typed text could be (an
    /// edit control counts line breaks its own way, as PasteToWindowAsync says), nobody in front, a focus that is no
    /// edit control and a caret that does not answer, or one read cut or holding a selection the paste would replace.
    /// </summary>
    private async ValueTask<PasteMark?> MarkPasteAsync(CancellationToken cancellationToken)
    {
        uint sequence = _keyboard.ClipboardSequence();
        string? text = _clipboardText?.Invoke();
        if (string.IsNullOrEmpty(text) || text.Any(char.IsControl) || text.Length > MaximumTypedText)
            return null;
        DesktopForeground front = _keyboard.Foreground();
        if (front.Window == 0)
            return null;
        TypedMark? edit = _delivery?.Mark(front.Window, text.Length);
        CaretText? caret = edit is null
            && await CaretTextAsync(front, cancellationToken).ConfigureAwait(false) is { Bounded: false, SelectionLength: 0 } read
                ? read
                : null;
        return edit is null && caret is null ? null : new PasteMark(text, front, edit, caret, sequence);
    }

    // R6-NB-3: the marked control read again, a settle apart, as a typed text's caret is (CaretRereads). Only a control
    // read whole and without the text says false: a read that did not answer, was cut at its bound or was cancelled
    // proves nothing (not readable; a cancellation goes up as the act's own), and neither does a mark of another window
    // or of another clipboard than the ones the script pasted (its foregroundProcessIdBefore, clipboardSequenceBefore).
    private async ValueTask<PasteRead> PasteReadsBackAsync(
        PasteMark? mark, JsonElement pasted, CancellationToken cancellationToken)
    {
        if (mark is not { } marked || !PastedFrom(marked, pasted))
            return new PasteRead(null, null);
        if (marked.Edit is not { } edit || _delivery is not { } delivery)
        {
            if (marked.Caret is not { } caret)
                return new PasteRead(null, null);
            (bool found, bool bounded, bool unanswered) = await CaretReadsBackAsync(
                marked.Front, caret, marked.Text, cancellationToken).ConfigureAwait(false);
            cancellationToken.ThrowIfCancellationRequested();
            return new PasteRead(found ? true : bounded || unanswered ? (bool?)null : false, null);
        }

        for (int read = 0; read < CaretRereads; read++)
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

            if (delivery.ReadsBack(edit, marked.Text, out string? landed))
                return new PasteRead(true, landed);
        }

        cancellationToken.ThrowIfCancellationRequested();
        return new PasteRead(delivery.Readable(edit) ? false : null, null);
    }

    // The script's own reads before its keys: the process in front and the clipboard's sequence (a sequence it did not
    // read, or one this side could not, is not compared).
    private static bool PastedFrom(PasteMark mark, JsonElement pasted) =>
        pasted.TryGetProperty("foregroundProcessIdBefore", out JsonElement process)
        && process.ValueKind == JsonValueKind.Number
        && process.TryGetInt32(out int processId) && processId == mark.Front.ProcessId
        && (mark.ClipboardSequence == 0
            || !pasted.TryGetProperty("clipboardSequenceBefore", out JsonElement sequence)
            || sequence.ValueKind != JsonValueKind.Number
            || (sequence.TryGetUInt32(out uint read) && read == mark.ClipboardSequence));

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
        FieldDelivery delivery, UiaFrontReport? keeper = null, bool focusMoved = false)
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
            return WithWhatStayed(ExternalJson.FailureAfterEffect(operation, delivery.Error ?? "input_effect_not_verified", true), delivery);
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
            // Uso-108: the keyboard's focus went to that field inside the window, where the person's next keys land.
            if (focusMoved)
                writer.WriteBoolean("focusMoved", true);
            writer.WriteString("authority", delivery.Method switch
            {
                "setvalue" => "windows_uia_setvalue_reread",
                "select" => "windows_uia_selection_reread",
                "postmessage" => "win32_postmessage_queued",
                _ when delivery.Replaced is not null => "win32_edit_text_reread_whole",
                _ => "win32_edit_message_reread",
            });
            writer.WriteNull("error");
            // Práctica V5E061: the part changed and what the whole text read back showed of it.
            if (delivery.Replaced is { } old)
                writer.WriteString("replaced", $"«{old}» was replaced by «{text}» at its one place in the text; the whole "
                    + $"text was read back after it: it holds «{text}» there and nothing else in it changed");
            // Práctica V5E023 («agregué al final» said of a text that went in before the old one): where the text read
            // back landed in what the field held.
            if (delivery.Landed is { } landed)
                writer.WriteString("landed", landed);
            // Noche NB r1, hallazgo 5: whether the field read back holds text besides the one written.
            if (delivery.OtherText is bool other)
                writer.WriteBoolean("otherTextInField", other);
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, true);
    }

    /// <summary>
    /// Uso-108 (B12; agent-desktop #190: satisfied, provably unwritten, changed but not matching, no evidence): a value that
    /// does not match says what stayed: <c>fieldUnchanged</c> when the field holds what it held after the whole wait, or
    /// <c>fieldNow</c> when it holds something else (a field that reshapes what it takes: «3» became «3,00 cm»). Neither
    /// without a read. A password never gets here: nothing is written there, and its value is not read.
    /// </summary>
    private static ExternalCapabilityReceipt WithWhatStayed(ExternalCapabilityReceipt failed, FieldDelivery delivery) =>
        delivery.FieldNow is null && !delivery.FieldUnchanged
            ? failed
            : failed with
            {
                Result = ExternalJson.Create(writer =>
                {
                    writer.WriteStartObject();
                    if (delivery.FieldNow is { } now)
                        writer.WriteString("fieldNow", now);
                    else
                        writer.WriteBoolean("fieldUnchanged", true);
                    writer.WriteEndObject();
                }),
            };

    internal static JsonElement AsDelivered(
        JsonElement root, (string Title, string Process)? sentTo = null, PasteRead? read = null, string? under = null) =>
        ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            bool unread = read is { Found: false };
            if (under is not null)
                writer.WriteString("under", under);
            foreach (JsonProperty property in root.EnumerateObject())
            {
                if (property.NameEquals("effectObserved"))
                    writer.WriteBoolean("delivered", property.Value.ValueKind == JsonValueKind.True);
                else if (unread && property.NameEquals("ok"))
                    writer.WriteBoolean("ok", false);
                else if (unread && property.NameEquals("error"))
                    writer.WriteString("error", PasteNotReadBack);
                else
                    property.WriteTo(writer);
            }

            // R6-NB-3: true or false as read back where the paste went; not_readable when nothing there could be read.
            if (read is { } pasteRead)
            {
                if (pasteRead.Found is bool found)
                    writer.WriteBoolean("readBack", found);
                else
                    writer.WriteString("readBack", PasteNotReadable);
                if (pasteRead.Landed is { } landed)
                    writer.WriteString("landed", landed);
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
