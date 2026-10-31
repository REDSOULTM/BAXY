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

    /// <summary>Ajuste c3: the edit control a Win32 control is written through: the control itself when it is one, the
    /// edit of an editable combo box; 0 for any other.</summary>
    nint EditOf(nint control) => WindowsTextDelivery.IsEditClass(ClassName(control)) ? control : 0;

    /// <summary>Ajuste c3: the name field of the common file dialog the window is (<see cref="CommonFileDialog"/>); 0 when
    /// the window is no such dialog.</summary>
    nint FileNameFieldOf(nint window) => 0;

    /// <summary>WM_GETTEXTLENGTH; -1 when the control did not answer.</summary>
    int TextLength(nint hwnd);

    /// <summary>WM_GETTEXT; null when the control did not answer.</summary>
    string? Text(nint hwnd, int length);

    /// <summary>EM_GETSEL's start and end when both fit its packed answer; null otherwise.</summary>
    (int Start, int End)? Selection(nint hwnd);

    /// <summary>EM_SETSEL(0, -1): the whole text selected, so what is inserted next replaces it; whether the control
    /// answered in time.</summary>
    bool SelectAll(nint hwnd);

    /// <summary>EM_SETSEL(start, end): that range of the control's text selected, so what is inserted next replaces it;
    /// whether the control answered in time.</summary>
    bool Select(nint hwnd, int start, int end);

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

    /// <summary>FT/proveedores goal (E2): the paragraph (else the line) at the caret of the keyboard's focus of
    /// <paramref name="window"/>, read by UI Automation's TextPattern (the worker's «textcaret»): the focused element or
    /// its nearest ancestor with a TextPattern, both of <paramref name="processId"/> (the window's own process; another
    /// process's document is never read), at most <paramref name="maximum"/> characters and said when it was cut; null
    /// when nothing answers.</summary>
    ValueTask<System.Text.Json.JsonDocument?> CaretTextAsync(
        nint window, int processId, int maximum, CancellationToken cancellationToken) =>
        ValueTask.FromResult<System.Text.Json.JsonDocument?>(null);

    /// <summary>Ajuste c3 (F09, M1 and M2): the value of the field (an Edit or a ComboBox, never a password) that holds
    /// the keyboard's focus inside <paramref name="window"/>'s own tree, read by UI Automation's ValuePattern as a look
    /// reads it (the worker's «focusvalue»), at most <paramref name="maximum"/> characters and said when it was cut; null
    /// when nothing answers.</summary>
    ValueTask<System.Text.Json.JsonDocument?> FocusedValueAsync(
        nint window, int maximum, CancellationToken cancellationToken) =>
        ValueTask.FromResult<System.Text.Json.JsonDocument?>(null);

    /// <summary>Auditoría del núcleo 2026-10-23: what holds the keyboard's focus (the worker's «focuskind», a read) and
    /// whether it lies inside <paramref name="window"/> (0: the window in front); null when nothing answers.</summary>
    ValueTask<System.Text.Json.JsonDocument?> FocusKindAsync(nint window, CancellationToken cancellationToken) =>
        ValueTask.FromResult<System.Text.Json.JsonDocument?>(null);

    /// <summary>Revisión de la guarda F013 (teclas): whether <paramref name="key"/> (Enter or space) sent to
    /// <paramref name="window"/> (0: the one in front) would answer yes to a dialog that asks about destroying something,
    /// judged as a click on the control that would take it; a read only. False when it is not so or cannot tell.</summary>
    ValueTask<bool> KeyAnswersDestructiveDialogAsync(nint window, string key, CancellationToken cancellationToken) =>
        ValueTask.FromResult(false);

    /// <summary>Renew al máximo (7.1): the view of <paramref name="window"/> read again after a completed act, as the
    /// difference from its last view (which it replaces); null when it was not read (no last view of that window, a
    /// read that failed or ran out of time).</summary>
    ValueTask<System.Text.Json.JsonElement?> AfterActAsync(nint window, CancellationToken cancellationToken) =>
        ValueTask.FromResult<System.Text.Json.JsonElement?>(null);
}

internal readonly record struct WindowIdentity(nint Window, int ProcessId, long Created)
{
    internal bool Alive => Window != 0 && ProcessId > 0;
}

/// <summary>BAXY Renew (notebook), F004: the edit control that had the keyboard's focus of the window in front right
/// before a text was typed into it by the keyboard, and the length its text must reach once the text is in; and the text
/// it held then, read only for where the typed text lands (<see cref="WindowsTextDelivery.Landed"/>; null otherwise).</summary>
internal readonly record struct TypedMark(nint Field, int Expected, string? Was = null);

/// <summary>FT/proveedores goal (E2): the paragraph at the caret of a document that is no Win32 edit control (Word's
/// «_WwG»), as UI Automation read it: its text (at most the read's bound), the unit it was expanded to («paragraph» or
/// «line»), whether the read was cut at the bound, and how long the selection was (-1: unknown).</summary>
internal readonly record struct CaretText(string Text, string Unit, bool Bounded, int SelectionLength);

/// <summary>What a delivery aimed at a field did: the method that took it, whether its re-read proves it was
/// delivered, whether anything may have reached the field, the failure when it did not, and the entry of a list a «select»
/// chose, as it was read (auditoría C9); and, read back, where the text landed in what the field held (Práctica V5E023,
/// <see cref="WindowsTextDelivery.Landed"/>). Práctica V5E061: the part of the text a replacement changed
/// (<see cref="WindowsTextDelivery.Replace"/>), and how many times the field's text held it when it was refused. Noche
/// NB r1, hallazgo 5: a text typed and read back by the edit control's messages says whether the field holds text
/// besides the one written (<c>OtherText</c>); null for a replaced part, a key, or UI Automation.</summary>
internal readonly record struct FieldDelivery(
    string Method, bool Delivered, bool EffectMayHaveOccurred, string? Error, string FieldClass, string? Entry = null,
    string? Landed = null, string? Replaced = null, int Occurrences = 0, bool? OtherText = null);

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
    // The longest control text a re-read reads; a longer one proves nothing (Holds).
    internal const int ReadableText = 1 << 20;
    private const long EsPassword = 0x0020;
    private const long EsReadOnly = 0x0800;
    private const long EsMultiline = 0x0004;

    /// <summary>ES_MULTILINE: an edit control of several lines is a document, never replaced whole.</summary>
    internal static bool IsMultiline(long style) => (style & EsMultiline) != 0;

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

    /// <summary>
    /// Ajuste c3 (E017 and the smoke of 31-10, live on the notebook): a Win32 control that takes no text, whose letters a
    /// keyboard's text would turn into something else: a push button, check box or radio button (Button: its access keys),
    /// a tree, a list or a list box (they move their selection to the item those letters begin), a tab strip, a scroll bar,
    /// a slider, a header or a toolbar. These are Windows' own control classes, not applications.
    /// </summary>
    internal static bool TakesNoText(string? className)
    {
        if (string.IsNullOrEmpty(className))
            return false;
        foreach (string part in className.Split('.'))
        {
            if (NoTextClasses.Contains(part))
                return true;
        }

        return false;
    }

    private static readonly HashSet<string> NoTextClasses = new(StringComparer.OrdinalIgnoreCase)
    {
        "Button", "SysTreeView32", "SysListView32", "ListBox", "ComboLBox", "SysTabControl32", "ScrollBar",
        "msctls_trackbar32", "SysHeader32", "ToolbarWindow32",
    };

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
            // Ronda final 17 (regla 3): the select-all was sent to the person's field: its selection changed.
            if (!_messages.SelectAll(field) || _messages.Selection(field) is not { } all || all.Start != 0 || all.End != before)
                return new FieldDelivery("em_replacesel", false, true, "input_field_not_replaced", fieldClass);
        }

        int expected = Expected(field, before, text.Length);
        string? was = replace ? null : Was(field, before);

        if (!Same(identity))
            return new FieldDelivery("em_replacesel", false, replace, "input_window_changed", fieldClass);
        bool answered = _messages.ReplaceSelection(field, text);
        int after = _messages.TextLength(field);
        if (after == expected && Holds(field, text, after, replace, out string? now))
            return new FieldDelivery("em_replacesel", true, true, null, fieldClass, Landed: Landed(was, now, text),
                OtherText: expected > text.Length);
        // The control answered and its text did not move: it does not take EM_REPLACESEL, nothing was inserted. Unless
        // the insertion replaced a selection as long as itself and the text is too long to be read: then nothing tells
        // the two apart, and typing it again could put it in twice.
        if (!answered || after != before || (after == expected && after > ReadableText))
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

        // Ronda final 18 (regla 3): with replace, the select-all and EM_REPLACESEL were already sent.
        if (queued == 0)
            return new FieldDelivery("wm_char", false, replace,
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
        string? held = null;
        bool whole = queued == text.Length && after == expected && Holds(field, text, after, replace, out held);
        return whole
            ? new FieldDelivery("wm_char", true, true, null, fieldClass, Landed: Landed(was, held, text),
                OtherText: expected > text.Length)
            : new FieldDelivery("wm_char", false, true,
                Same(identity) ? "input_effect_not_verified" : "input_window_changed", fieldClass);
    }

    /// <summary>
    /// Práctica V5E061 («cámbialo, era el miércoles, no el martes»: the new text went in at the caret, after the old one):
    /// the one part <paramref name="replacing"/> of the text of <paramref name="field"/>, an edit control of the window,
    /// changed into <paramref name="text"/>. The control's whole text is read (WM_GETTEXT); the old text must be in it
    /// exactly once, by ordinal comparison, or nothing is sent (<c>input_text_replacing_not_found</c>,
    /// <c>input_text_replacing_ambiguous</c> with <see cref="FieldDelivery.Occurrences"/>). It is selected (EM_SETSEL, at
    /// the control's own position: a rich edit counts a line break as one character) and the selection re-read, typed
    /// over (EM_REPLACESEL, undoable) and the whole text read again: it must be the text before with that part changed and
    /// nothing else, line breaks aside. Null when the field is not an edit control of the window (nothing sent). A
    /// read-only, password or disabled control gets nothing (<c>input_field_not_writable</c>); a text that is not read
    /// whole, or too long for the selection to be re-read, is not changed (<c>input_field_not_readable</c>).
    /// </summary>
    internal FieldDelivery? Replace(WindowIdentity identity, nint field, string replacing, string text)
    {
        string fieldClass = _messages.ClassName(field);
        if (!identity.Alive || !_messages.Belongs(identity.Window, field) || !IsEditClass(fieldClass))
            return null;
        if (!_messages.IsEnabled(field) || !TakesTyping(_messages.Style(field)))
            return new FieldDelivery("em_replacesel", false, false, "input_field_not_writable", fieldClass);
        int length = _messages.TextLength(field);
        // EM_GETSEL's packed answer stops at 65535: past it the selection could not be re-read.
        string? was = length is >= 0 and < Packed ? _messages.Text(field, length) : null;
        if (was is null || was.Length != length)
            return new FieldDelivery("em_replacesel", false, false, "input_field_not_readable", fieldClass);
        int count = Occurrences(was, replacing);
        if (count != 1)
            return new FieldDelivery("em_replacesel", false, false,
                count == 0 ? "input_text_replacing_not_found" : "input_text_replacing_ambiguous", fieldClass,
                Occurrences: count);
        int at = was.IndexOf(replacing, StringComparison.Ordinal);
        int start = at - (IsRichEdit(fieldClass) ? Occurrences(was[..at], "\r\n") : 0);
        if (!Same(identity))
            return new FieldDelivery("em_replacesel", false, false, "input_window_changed", fieldClass);
        // Ronda final 17 (regla 3): from here the person's field has its selection moved, an effect either way.
        if (!_messages.Select(field, start, start + replacing.Length)
            || _messages.Selection(field) != (start, start + replacing.Length))
            return new FieldDelivery("em_replacesel", false, true, "input_effect_not_verified", fieldClass);
        // Revisión w11-rev4: the range selected holds the old text only while the text is the one read; a person who
        // wrote in the field meanwhile moved it, and nothing is typed over another part of their text.
        int still = _messages.TextLength(field);
        if (still != length || _messages.Text(field, still) != was)
            return new FieldDelivery("em_replacesel", false, true, "input_effect_not_verified", fieldClass);
        if (!Same(identity))
            return new FieldDelivery("em_replacesel", false, true, "input_window_changed", fieldClass);
        _ = _messages.ReplaceSelection(field, text);
        string expected = Plain(was[..at] + text + was[(at + replacing.Length)..]);
        int after = _messages.TextLength(field);
        string? now = after is >= 0 and <= ReadableText ? _messages.Text(field, after) : null;
        return now is not null && Plain(now) == expected
            ? new FieldDelivery("em_replacesel", true, true, null, fieldClass, Replaced: replacing)
            : new FieldDelivery("em_replacesel", false, true,
                Same(identity) ? "input_effect_not_verified" : "input_window_changed", fieldClass);
    }

    // The longest text whose selection EM_GETSEL re-reads (its packed answer stops at 65535).
    private const int Packed = 0xFFFF;

    // A rich edit (RichEdit of any version, or a framework class derived from one), whose positions count a line break
    // as one character where its WM_GETTEXT gives «\r\n»; a classic Edit counts both.
    private static bool IsRichEdit(string className) =>
        className.Split('.').Any(static part => part.StartsWith("RichEdit", StringComparison.OrdinalIgnoreCase));

    // A control's text with its line breaks as one character, as Holds reads it.
    private static string Plain(string value) => value.Replace("\r", string.Empty, StringComparison.Ordinal);

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

    /// <summary>
    /// BAXY Renew (notebook), F004: the mark of the control with the keyboard's focus of <paramref name="window"/> (the
    /// window in front) before a text of <paramref name="length"/> characters is typed into it, so the text can be read
    /// back as a delivery's is. Null when that focus is no edit control of the window's own process, or one that is
    /// disabled, read-only or a password (its text is never read), or one whose text does not answer.
    /// </summary>
    internal TypedMark? Mark(nint window, int length)
    {
        nint field = _messages.FocusOf(window);
        if (field == 0 || !IsEditClass(_messages.ClassName(field)) || !_messages.IsEnabled(field)
            || !TakesTyping(_messages.Style(field)))
            return null;
        int before = _messages.TextLength(field);
        return before < 0 ? null : new TypedMark(field, Expected(field, before, length), Was(field, before));
    }

    /// <summary>Whether the typed text is in the marked control, by the proof of a delivery: its text grew by the text
    /// (minus the selection it replaced) and holds it. Nothing of the control's text leaves this check but, read back,
    /// where the text landed (<paramref name="landed"/>, <see cref="Landed"/>).</summary>
    internal bool ReadsBack(TypedMark mark, string text, out string? landed)
    {
        landed = null;
        int after = _messages.TextLength(mark.Field);
        if (after != mark.Expected || !Holds(mark.Field, text, after, false, out string? now))
            return false;
        landed = Landed(mark.Was, now, text);
        return true;
    }

    /// <summary>R6-NB-3: whether the marked control's text can be read whole now (its length answers, within a read, and
    /// its text answers): a read-back that failed over a control that cannot be read proves nothing.</summary>
    internal bool Readable(TypedMark mark)
    {
        int length = _messages.TextLength(mark.Field);
        return length >= 0 && length <= ReadableText && _messages.Text(mark.Field, length) is not null;
    }

    /// <summary>
    /// Práctica V5E023 («agrega al final»: the text went in before «Hola equipo…», and «agregué al final» was said): where
    /// a text read back in an edit control landed in the text the control held before, said as a fact the reply can be
    /// held to. Only from the two reads: the text after is the text before with the typed one put in at one place (no
    /// selection replaced), and every such place is at its start, every one at its end, or every one inside it; null
    /// otherwise (no text before, a replacement, a read missing, a text the two reads place in more than one way).
    /// </summary>
    internal static string? Landed(string? was, string? now, string text)
    {
        if (was is not { Length: > 0 } || now is null || text.Length == 0 || now.Length != was.Length + text.Length)
            return null;
        int prefix = 0;
        while (prefix < was.Length && now[prefix] == was[prefix])
            prefix++;
        int suffix = 0;
        while (suffix < was.Length && now[now.Length - 1 - suffix] == was[was.Length - 1 - suffix])
            suffix++;
        // The text went in at «at» when what is before it is the old text's beginning and what is after it its end.
        int from = was.Length - suffix;
        if (from > prefix || prefix - from > LandingPlaces)
            return null;
        bool start = false, end = false, middle = false;
        for (int at = from; at <= prefix; at++)
        {
            if (string.CompareOrdinal(now, at, text, 0, text.Length) != 0)
                continue;
            start |= at == 0;
            end |= at == was.Length;
            middle |= at > 0 && at < was.Length;
        }

        return (start, end, middle) switch
        {
            (true, false, false) => "the text went in at the start of the text the field already had, before it",
            (false, true, false) => "the text went in at the end of the text the field already had, after it",
            (false, false, true) => "the text went in inside the text the field already had, neither at its start nor at its end",
            _ => null,
        };
    }

    // The places a text repeated around its insertion (typing «a» into «aaa») leaves to try; past them nothing is said.
    private const int LandingPlaces = 64;

    // The text a field holds before an insertion, only for where it lands (ModelAids.CaretPlace): its line breaks as one
    // character, as Holds reads it after; null with the aid off, an empty field or a text too long to read.
    private string? Was(nint field, int length) =>
        Infrastructure.ModelAids.On(Infrastructure.ModelAids.CaretPlace) && length is > 0 and <= ReadableText
            ? _messages.Text(field, length)?.Replace("\r", string.Empty, StringComparison.Ordinal)
            : null;

    /// <summary>BAXY Renew al máximo (E017): whether the marked control has taken the first <paramref name="sent"/>
    /// characters of a text of <paramref name="length"/> typed into it: its length reached what it had (minus the
    /// selection the first one replaced) plus them. Only the length is read, and the control answers it with the keys it
    /// already took, not with those still queued for it.</summary>
    internal bool Took(TypedMark mark, int sent, int length)
    {
        int now = _messages.TextLength(mark.Field);
        return now >= 0 && now >= mark.Expected - length + sent;
    }

    /// <summary>The characters of the paragraph at the caret a UI Automation re-read takes (twice the longest typed
    /// text, so the longest one still fits beside a paragraph of its own length); a longer paragraph is read cut,
    /// and a cut read proves nothing (<see cref="CaretHolds"/>).</summary>
    internal const int CaretReadableText = 8192;

    /// <summary>
    /// FT/proveedores goal (E2): whether the typed text is in the paragraph at the caret, by UI Automation's re-read of
    /// that paragraph before and after it was typed: the same unit both times, neither read cut at its bound, no
    /// selection before (typing would have replaced it, and what it replaced is not known), the paragraph grew by at
    /// least the text's length and holds it once more than it did before. Word's AutoFormat as you type rewrites quotes
    /// and dashes (' into ’, " into “ ” or « », -- into –): only those typographic substitutions are compared
    /// tolerantly (<see cref="Typographic"/>, on both sides), and so is the capital Word's AutoCorrect puts on the first
    /// letter of a sentence (measured live, 2026-10-18: «hola desde baxy» typed into a blank document became «Hola desde
    /// baxy», and the exact check left a text that was there unverified); any other rewrite (an autocorrected word) is
    /// not the text typed, and leaves it not read back. Nothing of the paragraph leaves this check.
    /// </summary>
    internal static bool CaretHolds(CaretText before, CaretText after, string text)
    {
        if (before.Bounded || after.Bounded || before.SelectionLength != 0
            || !string.Equals(before.Unit, after.Unit, StringComparison.Ordinal))
            return false;
        string typed = Typographic(text);
        if (typed.Length == 0)
            return false;
        string was = Typographic(before.Text);
        string now = Typographic(after.Text);
        if (now.Length < was.Length + typed.Length)
            return false;
        string capital = char.ToUpperInvariant(typed[0]) + typed[1..];
        return Occurrences(now, typed) > Occurrences(was, typed)
            || (capital != typed && Occurrences(now, capital) > Occurrences(was, capital));
    }

    // The quotes and dashes Word's AutoFormat as you type puts for the typed ones, as the typed ones; a run of dashes
    // as one («--» becomes «–»); the paragraph's own marks (\r, \v, a table cell's \a) dropped: a typed text carries
    // no control character.
    private static string Typographic(string value)
    {
        var folded = new System.Text.StringBuilder(value.Length);
        foreach (char character in value)
        {
            char plain = character switch
            {
                '‘' or '’' or '‚' or '‛' or '′' => '\'',
                '“' or '”' or '„' or '‟' or '″' or '«' or '»' => '"',
                '‐' or '‑' or '‒' or '–' or '—' or '―' or '−' => '-',
                _ => character,
            };
            if (char.IsControl(plain) || (plain == '-' && folded.Length > 0 && folded[^1] == '-'))
                continue;
            folded.Append(plain);
        }

        return folded.ToString();
    }

    // How many times «part» is in «value», overlapping ones included.
    private static int Occurrences(string value, string part)
    {
        int count = 0;
        for (int at = value.IndexOf(part, StringComparison.Ordinal); at >= 0;
             at = value.IndexOf(part, at + 1, StringComparison.Ordinal))
            count++;
        return count;
    }

    // The length a control's text has once a text of «length» characters is inserted at its caret, replacing its
    // selection.
    private int Expected(nint field, int before, int length)
    {
        (int Start, int End)? selection = _messages.Selection(field);
        int replaced = selection is { } range && range.End >= range.Start ? range.End - range.Start : 0;
        return before - replaced + length;
    }

    private bool Same(WindowIdentity identity) => _messages.Identity(identity.Window) == identity;

    // The text is in the field; a replaced value is the field's whole text. A text too long to be read proves
    // neither: its length alone is never taken for the text (rule 3).
    private bool Holds(nint field, string text, int length, bool whole, out string? content)
    {
        content = null;
        if (length > ReadableText)
            return false;
        content = _messages.Text(field, length)?.Replace("\r", string.Empty, StringComparison.Ordinal);
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

    public nint EditOf(nint control)
    {
        string className = ClassName(control);
        if (WindowsTextDelivery.IsEditClass(className))
            return control;
        // An editable combo box writes through its own Edit (ComboBoxEx32 holds a ComboBox that holds it).
        nint inner = className switch
        {
            "ComboBox" => FindWindowExW(control, 0, "Edit", null),
            "ComboBoxEx32" => FindWindowExW(control, 0, "ComboBox", null) is var combo and not 0
                ? FindWindowExW(combo, 0, "Edit", null)
                : 0,
            _ => 0,
        };
        return inner != 0 && Belongs(control, inner) ? inner : 0;
    }

    public nint FileNameFieldOf(nint window) => CommonFileDialog.Read(window)?.NameField ?? 0;

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

    public bool Select(nint hwnd, int start, int end) =>
        SendMessageTimeoutW(hwnd, EmSetSel, start, end, AbortIfHung, Timeout, out _) != 0;

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

    [LibraryImport("user32.dll", StringMarshalling = StringMarshalling.Utf16)]
    private static partial nint FindWindowExW(nint parent, nint after, string? className, string? title);

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
