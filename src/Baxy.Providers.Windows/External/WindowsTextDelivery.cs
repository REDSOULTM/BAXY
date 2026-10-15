using System.Runtime.InteropServices;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// The Win32 side of a delivery aimed at one field of the mission's window (goal v3, point 0, fix 1): no keyboard,
/// no foreground. The adapter decides what is sent; this seam only reads the field and sends it messages.
/// </summary>
internal interface IFieldMessages
{
    /// <summary>The window's process and that process's creation time: hwnds are recycled, the pair is not.</summary>
    WindowIdentity Identity(nint window);

    /// <summary>Whether <paramref name="field"/> is the window itself or one of its children, of its own process.</summary>
    bool Belongs(nint window, nint field);

    string ClassName(nint hwnd);

    /// <summary>GWL_STYLE of the control: an edit control's ES_READONLY and ES_PASSWORD live there.</summary>
    long Style(nint hwnd);

    /// <summary>IsWindowEnabled: a disabled control takes no keyboard, so it takes no message either.</summary>
    bool IsEnabled(nint hwnd);

    /// <summary>The keyboard focus of the window's own GUI thread (0 when it reports none or it is outside the window).</summary>
    nint FocusOf(nint window);

    /// <summary>The window's only visible, enabled edit control (<see cref="WindowsTextDelivery.IsEditClass"/>) of its own
    /// process; 0 when it has none or several (which one would take a text is not known then).</summary>
    nint SoleEditOf(nint window);

    /// <summary>WM_GETTEXTLENGTH; -1 when the control did not answer.</summary>
    int TextLength(nint hwnd);

    /// <summary>WM_GETTEXT; null when the control did not answer.</summary>
    string? Text(nint hwnd, int length);

    /// <summary>EM_GETSEL's start and end when both fit its packed answer; null otherwise.</summary>
    (int Start, int End)? Selection(nint hwnd);

    /// <summary>EM_SETSEL(0, -1): the whole text selected, so what is inserted next replaces it; whether the control
    /// answered in time.</summary>
    bool SelectAll(nint hwnd);

    /// <summary>EM_REPLACESEL (undoable), sent and waited for; whether the control answered in time.</summary>
    bool ReplaceSelection(nint hwnd, string text);

    /// <summary>WM_CHAR queued to the control; whether Windows queued it.</summary>
    bool PostChar(nint hwnd, char character);

    /// <summary>WM_KEYDOWN and WM_KEYUP queued to the control; how many of the two Windows queued.</summary>
    int PostKey(nint hwnd, ushort virtualKey);

    /// <summary>Lets the control take what was queued before it is read again.</summary>
    ValueTask SettleAsync(CancellationToken cancellationToken);
}

/// <summary>The fields of the last view (WindowsVisibleControlAdapter): what a text aimed at a field names.</summary>
internal interface IViewedFields
{
    bool TryViewedField(int index, out nint window, out string controlId);

    /// <summary><paramref name="replace"/>: the step sets the field to the text (a form's value), so its current
    /// content is replaced; never in a document or a password (the worker refuses those).</summary>
    ValueTask<System.Text.Json.JsonDocument?> FieldAsync(
        nint window, string controlId, string? text, bool replace, CancellationToken cancellationToken);

    /// <summary>Review of combos-galerias (finding 1): the list box's own entry named <paramref name="text"/> chosen by
    /// pattern (the worker's «field» with «entry»); never a text written into the box.</summary>
    ValueTask<System.Text.Json.JsonDocument?> EntryAsync(
        nint window, string controlId, string text, CancellationToken cancellationToken);

    /// <summary>Revision 1 of r24b (v1): the keyboard's focus put on the viewed field by UI Automation (the worker's
    /// «focus»: SetFocus only with its window in front, HasKeyboardFocus re-read); null when nothing answers.</summary>
    ValueTask<System.Text.Json.JsonDocument?> FocusAsync(nint window, string controlId, CancellationToken cancellationToken) =>
        ValueTask.FromResult<System.Text.Json.JsonDocument?>(null);

    /// <summary>Revision 3 of r24b (finding 3): how many clicks the visible controls' adapter has made; a click after a
    /// value was set without the keyboard's focus voids the focus owed to that field.</summary>
    long Clicks => 0;
}

internal readonly record struct WindowIdentity(nint Window, int ProcessId, long Created)
{
    internal bool Alive => Window != 0 && ProcessId > 0;
}

/// <summary>What a delivery aimed at a field did: the method that took it, whether its re-read proves it was
/// delivered, whether anything may have reached the field, the failure when it did not, and the entry of a list a «select»
/// chose, as it was read (auditoría C9).</summary>
internal readonly record struct FieldDelivery(
    string Method, bool Delivered, bool EffectMayHaveOccurred, string? Error, string FieldClass, string? Entry = null);

/// <summary>
/// Text and keys delivered to the field of the mission's window by window messages (CONTRATO_VISTA_ACCION.md §2):
/// <list type="bullet">
/// <item>text: EM_REPLACESEL to a Win32 edit control (Edit or RichEdit, the class every classic and WinForms text box
/// derives from), which inserts at its caret as typing does; when the control ignores it, WM_CHAR queued one
/// character at a time. The proof is the control's text read back: its length grew by what was inserted (minus the
/// selection it replaced) and the text is in it. Delivery, never arrival.</item>
/// <item>keys: the non-modifier keys a classic control or a dialog takes from its message loop (Enter, Tab, the
/// arrows and the editing keys) queued as WM_KEYDOWN/WM_KEYUP. A chord is not: the application reads its modifiers
/// from the keyboard state, which a message does not carry.</item>
/// </list>
/// The window's identity (hwnd, process and its creation time) is checked before every message.
/// </summary>
internal sealed class WindowsTextDelivery
{
    private const int ReadableText = 1 << 20;
    private const long EsPassword = 0x0020;
    private const long EsReadOnly = 0x0800;

    // The single keys a classic control handles in its own window procedure, or its dialog in its message loop.
    private static readonly HashSet<string> PostableKeys = new(StringComparer.Ordinal)
    {
        "arrow_down", "arrow_left", "arrow_right", "arrow_up", "backspace", "delete", "end", "enter", "escape",
        "home", "page_down", "page_up", "tab",
    };

    private readonly IFieldMessages _messages;

    internal WindowsTextDelivery(IFieldMessages messages)
    {
        _messages = messages ?? throw new ArgumentNullException(nameof(messages));
    }

    internal IFieldMessages Messages => _messages;

    internal static bool IsPostable(string key) => PostableKeys.Contains(key);

    /// <summary>A Win32 edit control: «Edit», a RichEdit of any version, or a framework class derived from them
    /// («WindowsForms10.EDIT.app…»). These are Windows control classes, not applications.</summary>
    internal static bool IsEditClass(string? className)
    {
        if (string.IsNullOrEmpty(className))
            return false;
        foreach (string part in className.Split('.'))
        {
            if (part.Equals("Edit", StringComparison.OrdinalIgnoreCase)
                || part.StartsWith("RichEdit", StringComparison.OrdinalIgnoreCase))
                return true;
        }

        return false;
    }

    /// <summary>A classic control whose window procedure (or whose dialog's message loop) takes queued keys: the edit
    /// controls and the common list, tree, combo and button classes.</summary>
    internal static bool IsClassicControl(string? className)
    {
        if (IsEditClass(className))
            return true;
        if (string.IsNullOrEmpty(className))
            return false;
        foreach (string part in className.Split('.'))
        {
            if (part.Equals("ComboBox", StringComparison.OrdinalIgnoreCase)
                || part.Equals("ComboBoxEx32", StringComparison.OrdinalIgnoreCase)
                || part.Equals("ListBox", StringComparison.OrdinalIgnoreCase)
                || part.Equals("SysListView32", StringComparison.OrdinalIgnoreCase)
                || part.Equals("SysTreeView32", StringComparison.OrdinalIgnoreCase)
                || part.Equals("Button", StringComparison.OrdinalIgnoreCase))
                return true;
        }

        return false;
    }

    /// <summary>Whether an edit control with this style takes typed text: neither read-only nor a password box.
    /// EM_REPLACESEL writes into a read-only edit (it is how a read-only log gets its lines), so the style is checked
    /// before, not left to the control.</summary>
    internal static bool TakesTyping(long style) => (style & (EsReadOnly | EsPassword)) == 0;

    /// <summary>
    /// Inserts <paramref name="text"/> at the caret of <paramref name="field"/>, an edit control of the mission's
    /// window: EM_REPLACESEL, else WM_CHAR. Null when the field is not one this delivery can reach (nothing sent).
    /// A read-only, password or disabled edit control gets nothing by any path: input_field_not_writable, before any
    /// effect (the keyboard would not write there either; a password is never typed by a mission's message).
    /// With <paramref name="replace"/> (goal v3 point 2, a form's value) the whole text is selected first
    /// (EM_SETSEL 0, -1) so the insertion replaces it, and the proof is the control's text equal to the value.
    /// </summary>
    internal async ValueTask<FieldDelivery?> TypeAsync(
        WindowIdentity identity, nint field, string text, CancellationToken cancellationToken, bool replace = false)
    {
        string fieldClass = _messages.ClassName(field);
        if (!identity.Alive || !_messages.Belongs(identity.Window, field) || !IsEditClass(fieldClass))
            return null;
        if (!_messages.IsEnabled(field) || !TakesTyping(_messages.Style(field)))
            return new FieldDelivery("em_replacesel", false, false, "input_field_not_writable", fieldClass);
        int before = _messages.TextLength(field);
        if (before < 0)
            return null;
        if (replace)
        {
            if (!Same(identity))
                return new FieldDelivery("em_replacesel", false, false, "input_window_changed", fieldClass);
            // A selection the control did not take whole would leave part of the old value beside the new one.
            if (!_messages.SelectAll(field) || _messages.Selection(field) is not { } all || all.Start != 0 || all.End != before)
                return new FieldDelivery("em_replacesel", false, false, "input_field_not_replaced", fieldClass);
        }

        (int Start, int End)? selection = _messages.Selection(field);
        int replaced = selection is { } range && range.End >= range.Start ? range.End - range.Start : 0;
        int expected = before - replaced + text.Length;

        if (!Same(identity))
            return new FieldDelivery("em_replacesel", false, false, "input_window_changed", fieldClass);
        bool answered = _messages.ReplaceSelection(field, text);
        int after = _messages.TextLength(field);
        if (after == expected && Holds(field, text, after, replace))
            return new FieldDelivery("em_replacesel", true, true, null, fieldClass);
        // The control answered and its text did not move: it does not take EM_REPLACESEL, nothing was inserted.
        if (!answered || after != before)
            return new FieldDelivery("em_replacesel", false, true, "input_effect_not_verified", fieldClass);

        int queued = 0;
        foreach (char character in text)
        {
            if (cancellationToken.IsCancellationRequested || !Same(identity))
                break;
            if (!_messages.PostChar(field, character))
                break;
            queued++;
        }

        if (queued == 0)
            return new FieldDelivery("wm_char", false, false,
                Same(identity) ? "input_effect_not_verified" : "input_window_changed", fieldClass);
        try
        {
            await _messages.SettleAsync(cancellationToken).ConfigureAwait(false);
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            return new FieldDelivery("wm_char", false, true, "desktop_interaction_adapter_failed", fieldClass);
        }

        after = _messages.TextLength(field);
        bool whole = queued == text.Length && after == expected && Holds(field, text, after, replace);
        return whole
            ? new FieldDelivery("wm_char", true, true, null, fieldClass)
            : new FieldDelivery("wm_char", false, true,
                Same(identity) ? "input_effect_not_verified" : "input_window_changed", fieldClass);
    }

    /// <summary>
    /// Queues a single key to <paramref name="field"/>, a classic control of the mission's window. Null when the key
    /// or the field is not one a message reaches (nothing sent).
    /// </summary>
    internal FieldDelivery? Press(WindowIdentity identity, nint field, string key, ushort virtualKey)
    {
        string fieldClass = _messages.ClassName(field);
        if (!IsPostable(key) || !identity.Alive || !_messages.Belongs(identity.Window, field) || !IsClassicControl(fieldClass)
            || !_messages.IsEnabled(field))
            return null;
        if (!Same(identity))
            return new FieldDelivery("postmessage", false, false, "input_window_changed", fieldClass);
        int queued = _messages.PostKey(field, virtualKey);
        return queued == 2
            ? new FieldDelivery("postmessage", true, true, null, fieldClass)
            : new FieldDelivery("postmessage", false, queued > 0, "input_effect_not_verified", fieldClass);
    }

    private bool Same(WindowIdentity identity) => _messages.Identity(identity.Window) == identity;

    // The text is in the field; a replaced value is the field's whole text.
    private bool Holds(nint field, string text, int length, bool whole = false)
    {
        if (length > ReadableText)
            return !whole;
        string? content = _messages.Text(field, length)?.Replace("\r", string.Empty, StringComparison.Ordinal);
        return content is not null
            && (whole ? content == text : content.Contains(text, StringComparison.Ordinal));
    }
}

internal sealed partial class WindowsFieldMessages : IFieldMessages
{
    private const uint WmGetText = 0x000D;
    private const uint WmGetTextLength = 0x000E;
    private const uint WmKeyDown = 0x0100;
    private const uint WmKeyUp = 0x0101;
    private const uint WmChar = 0x0102;
    private const uint EmGetSel = 0x00B0;
    private const uint EmSetSel = 0x00B1;
    private const uint EmReplaceSel = 0x00C2;
    private const uint AbortIfHung = 0x0002;
    private const uint Timeout = 2000;
    private const uint QueryLimitedInformation = 0x1000;
    private const int GwlStyle = -16;

    private static readonly TimeSpan Settle = TimeSpan.FromMilliseconds(120);

    public WindowIdentity Identity(nint window)
    {
        if (window == 0 || !IsWindow(window))
            return new WindowIdentity(window, 0, 0);
        _ = GetWindowThreadProcessId(window, out uint processId);
        return new WindowIdentity(window, unchecked((int)processId), Created(processId));
    }

    public bool Belongs(nint window, nint field)
    {
        if (window == 0 || field == 0 || !IsWindow(field))
            return false;
        if (field != window && !IsChild(window, field))
            return false;
        _ = GetWindowThreadProcessId(window, out uint windowProcess);
        _ = GetWindowThreadProcessId(field, out uint fieldProcess);
        return windowProcess != 0 && windowProcess == fieldProcess;
    }

    public unsafe string ClassName(nint hwnd)
    {
        if (hwnd == 0)
            return string.Empty;
        char* buffer = stackalloc char[256];
        int length = GetClassNameW(hwnd, buffer, 256);
        return length <= 0 ? string.Empty : new string(buffer, 0, length);
    }

    public long Style(nint hwnd) => hwnd == 0 ? 0 : (long)GetWindowLongPtrW(hwnd, GwlStyle);

    public bool IsEnabled(nint hwnd) => hwnd != 0 && IsWindowEnabled(hwnd);

    public nint FocusOf(nint window)
    {
        if (window == 0)
            return 0;
        uint thread = GetWindowThreadProcessId(window, out _);
        if (thread == 0)
            return 0;
        var info = new GuiThreadInfo { Size = Marshal.SizeOf<GuiThreadInfo>() };
        if (!GetGUIThreadInfo(thread, ref info) || info.Focus == 0)
            return 0;
        return Belongs(window, info.Focus) ? info.Focus : 0;
    }

    public nint SoleEditOf(nint window)
    {
        if (window == 0)
            return 0;
        nint sole = 0;
        int count = 0;
        EnumChildProc callback = (child, _) =>
        {
            if (IsWindowVisible(child) && IsWindowEnabled(child) && WindowsTextDelivery.IsEditClass(ClassName(child))
                && Belongs(window, child))
            {
                sole = child;
                count++;
            }

            return count < 2;
        };
        _ = EnumChildWindows(window, callback, 0);
        GC.KeepAlive(callback);
        return count == 1 ? sole : 0;
    }

    public int TextLength(nint hwnd)
    {
        if (SendMessageTimeoutW(hwnd, WmGetTextLength, 0, 0, AbortIfHung, Timeout, out nint length) == 0)
            return -1;
        return length < 0 || length > int.MaxValue ? -1 : (int)length;
    }

    public unsafe string? Text(nint hwnd, int length)
    {
        if (length < 0)
            return null;
        char[] buffer = new char[length + 2];
        fixed (char* pointer = buffer)
        {
            if (SendMessageTimeoutW(hwnd, WmGetText, buffer.Length, (nint)pointer, AbortIfHung, Timeout, out nint copied) == 0)
                return null;
            return new string(pointer, 0, (int)Math.Clamp((long)copied, 0, buffer.Length));
        }
    }

    public (int Start, int End)? Selection(nint hwnd)
    {
        if (SendMessageTimeoutW(hwnd, EmGetSel, 0, 0, AbortIfHung, Timeout, out nint packed) == 0)
            return null;
        long value = packed;
        int start = (int)(value & 0xFFFF);
        int end = (int)((value >> 16) & 0xFFFF);
        // Past 65535 the packed answer is clipped: the selection is unknown.
        if (start == 0xFFFF || end == 0xFFFF)
            return null;
        return (start, end);
    }

    public bool SelectAll(nint hwnd) =>
        SendMessageTimeoutW(hwnd, EmSetSel, 0, -1, AbortIfHung, Timeout, out _) != 0;

    public unsafe bool ReplaceSelection(nint hwnd, string text)
    {
        fixed (char* pointer = text + "\0")
        {
            return SendMessageTimeoutW(hwnd, EmReplaceSel, 1, (nint)pointer, AbortIfHung, Timeout, out _) != 0;
        }
    }

    public bool PostChar(nint hwnd, char character) => PostMessageW(hwnd, WmChar, character, 1);

    public int PostKey(nint hwnd, ushort virtualKey)
    {
        uint scan = MapVirtualKeyW(virtualKey, 0);
        // The navigation block (Page Up … Down arrow, Delete) sits on the extended keys.
        bool extended = virtualKey is >= 0x21 and <= 0x28 or 0x2D or 0x2E;
        long down = 1L | ((long)scan << 16) | (extended ? 1L << 24 : 0L);
        long up = down | (1L << 30) | (1L << 31);
        int queued = 0;
        if (PostMessageW(hwnd, WmKeyDown, virtualKey, (nint)down))
            queued++;
        if (PostMessageW(hwnd, WmKeyUp, virtualKey, unchecked((nint)up)))
            queued++;
        return queued;
    }

    public ValueTask SettleAsync(CancellationToken cancellationToken) => new(Task.Delay(Settle, cancellationToken));

    private static long Created(uint processId)
    {
        nint process = OpenProcess(QueryLimitedInformation, false, processId);
        if (process == 0)
            return 0;
        try
        {
            return GetProcessTimes(process, out long created, out _, out _, out _) ? created : 0;
        }
        finally
        {
            _ = CloseHandle(process);
        }
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct GuiThreadInfo
    {
        public int Size;
        public uint Flags;
        public nint Active;
        public nint Focus;
        public nint Capture;
        public nint MenuOwner;
        public nint MoveSize;
        public nint Caret;
        public int CaretLeft;
        public int CaretTop;
        public int CaretRight;
        public int CaretBottom;
    }

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool IsWindow(nint hwnd);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool IsWindowVisible(nint hwnd);

    private delegate bool EnumChildProc(nint hwnd, nint parameter);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool EnumChildWindows(nint parent, EnumChildProc callback, nint parameter);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool IsChild(nint parent, nint hwnd);

    [LibraryImport("user32.dll")]
    private static partial uint GetWindowThreadProcessId(nint hwnd, out uint processId);

    [LibraryImport("user32.dll")]
    private static partial nint GetWindowLongPtrW(nint hwnd, int index);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool IsWindowEnabled(nint hwnd);

    [LibraryImport("user32.dll", StringMarshalling = StringMarshalling.Utf16)]
    private static unsafe partial int GetClassNameW(nint hwnd, char* name, int count);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool GetGUIThreadInfo(uint thread, ref GuiThreadInfo info);

    [LibraryImport("user32.dll")]
    private static partial nint SendMessageTimeoutW(
        nint hwnd, uint message, nint wParam, nint lParam, uint flags, uint timeout, out nint result);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool PostMessageW(nint hwnd, uint message, nint wParam, nint lParam);

    [LibraryImport("user32.dll")]
    private static partial uint MapVirtualKeyW(uint code, uint mapType);

    [LibraryImport("kernel32.dll")]
    private static partial nint OpenProcess(uint access, [MarshalAs(UnmanagedType.Bool)] bool inherit, uint processId);

    [LibraryImport("kernel32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool GetProcessTimes(nint process, out long created, out long exited, out long kernel, out long user);

    [LibraryImport("kernel32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool CloseHandle(nint handle);
}
