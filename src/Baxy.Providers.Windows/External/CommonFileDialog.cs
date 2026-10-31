using System.Runtime.InteropServices;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// Ajuste c3 (E017, order of the owner: «tiene que funcionar» in every application that opens it): Windows' common file
/// dialog («Guardar como», «Abrir», «Seleccionar carpeta»), told by its structure and never by the application that opened
/// it nor by a word of its language. Every variant measured live on the notebook (Notepad, Paint, Chrome, Edge, Word,
/// Excel, VS Code: the modern IFileDialog; the explorer-style dialog of GetSaveFileName/GetOpenFileName) is a top-level
/// «#32770» window holding the shell's folder view (SHELLDLL_DefView) and the push buttons with the dialog's standard ids
/// IDOK (1, the button that saves or opens) and IDCANCEL (2). Its name field is the editable combo's Edit (the only Edit
/// under a ComboBox outside the address and search bands; the explorer-style dialog's cmb13, 1148, or edt1, 1152), and
/// the folder it is in is the path its address bar's breadcrumb names («Dirección: C:\…»/«Address: C:\…»: only the path
/// is taken, from its drive or share on). In E017 the press on «Guardar» came back completed while the file was saved in
/// another folder (pc-c3r9b_1-sB s0), or an error box opened over the dialog and the press was told done because the
/// dialog's owner turned disabled (dialogOpened, NB live 30-10): what the press did is now read on the dialog itself.
/// </summary>
internal static partial class CommonFileDialog
{
    /// <summary>A child window of the dialog, as Win32 gives it (text read only for the classes that need it).</summary>
    internal readonly record struct ChildWindow(nint Handle, nint Parent, string Class, int Id, bool Visible, string Text);

    /// <summary>The dialog before an act: its buttons, the name its field holds and the folder its address shows.</summary>
    internal sealed record Facts(
        nint Dialog,
        nint Accept,
        string AcceptText,
        nint Cancel,
        string CancelText,
        nint NameField,
        string? Name,
        string? Address,
        string? Folder)
    {
        /// <summary>Where the file goes (or comes from): the name when it is a whole path, else the folder and the name.</summary>
        internal string? Path => Resolve(Folder, Name);
    }

    /// <summary>How the dialog ended after the act.</summary>
    internal enum Ending
    {
        /// <summary>The dialog closed: the application took the name.</summary>
        Closed,

        /// <summary>Another window of the dialog (an error, «¿Desea reemplazarlo?») disabled it: nothing is saved yet.</summary>
        Blocked,

        /// <summary>The dialog stayed open and enabled (it went into a folder, or refused the name without a word).</summary>
        Open,
    }

    /// <summary>What the act did to the dialog, and whether the file it names is there.</summary>
    internal sealed record Outcome(Ending Ending, string? Path, bool? Exists, string? BlockedBy, string? FolderNow, string? NameNow);

    // Ids every common file dialog keeps (commdlg.h, dlgs.h): IDOK, IDCANCEL, cmb13 and edt1.
    private const int IdOk = 1;
    private const int IdCancel = 2;
    private const int NameCombo = 0x047C;
    private const int NameEdit = 0x0480;
    private const string DialogClass = "#32770";

    // The bands of the dialog whose Edit is not the name (its address band and its search band).
    private static readonly string[] OtherBands = ["Address Band Root", "UniversalSearchBand", "Search Box"];

    // A path in what the address shows, from its drive or share on; the label before it is the language's.
    [GeneratedRegex(@"(?:[A-Za-z]:\\|\\\\[^\\]+\\[^\\]+).*$", RegexOptions.CultureInvariant)]
    private static partial Regex PathShown();

    /// <summary>Pure: the dialog's facts from its class and its child windows; null when it is no common file dialog.</summary>
    internal static Facts? Recognize(nint dialog, string dialogClass, IReadOnlyList<ChildWindow> children)
    {
        if (!string.Equals(dialogClass, DialogClass, StringComparison.Ordinal)
            || !children.Any(static child => child.Class == "SHELLDLL_DefView"))
            return null;
        ChildWindow accept = children.FirstOrDefault(child => child.Parent == dialog && child.Id == IdOk && child.Class == "Button");
        if (accept.Handle == 0)
            return null;
        ChildWindow cancel = children.FirstOrDefault(child => child.Parent == dialog && child.Id == IdCancel && child.Class == "Button");
        Dictionary<nint, ChildWindow> byHandle = [];
        foreach (ChildWindow child in children)
            byHandle.TryAdd(child.Handle, child);
        IEnumerable<ChildWindow> Ancestors(ChildWindow child)
        {
            nint up = child.Parent;
            for (int step = 0; step < 32 && up != dialog && byHandle.TryGetValue(up, out ChildWindow parent); step++)
            {
                yield return parent;
                up = parent.Parent;
            }
        }

        ChildWindow[] edits = [.. children.Where(child => child.Visible && child.Class == "Edit"
            && !Ancestors(child).Any(static up => OtherBands.Contains(up.Class, StringComparer.Ordinal)))];
        ChildWindow name = edits.FirstOrDefault(edit => edit.Id == NameEdit
            || Ancestors(edit).Take(2).Any(static up => up.Id == NameCombo));
        if (name.Handle == 0)
        {
            ChildWindow[] inCombo = [.. edits.Where(edit => byHandle.TryGetValue(edit.Parent, out ChildWindow parent)
                && parent.Class is "ComboBox" or "ComboBoxEx32")];
            if (inCombo.Length == 1)
                name = inCombo[0];
        }

        ChildWindow address = children.FirstOrDefault(child => child.Class == "ToolbarWindow32"
            && byHandle.TryGetValue(child.Parent, out ChildWindow parent) && parent.Class == "Breadcrumb Parent");
        string? shown = address.Handle == 0 ? null : Plain(address.Text);
        return new Facts(dialog, accept.Handle, Plain(accept.Text).Replace("&", string.Empty, StringComparison.Ordinal),
            cancel.Handle, Plain(cancel.Text).Replace("&", string.Empty, StringComparison.Ordinal), name.Handle,
            name.Handle == 0 ? null : name.Text, shown, FolderOf(shown));
    }

    /// <summary>Pure: the folder an address bar shows, when it is a path of the disk or a share; null for a place that
    /// is not one («Este equipo», a library) or nothing read.</summary>
    internal static string? FolderOf(string? address)
    {
        if (string.IsNullOrWhiteSpace(address))
            return null;
        Match path = PathShown().Match(Plain(address));
        if (!path.Success)
            return null;
        string folder = path.Value.Trim();
        return System.IO.Path.IsPathFullyQualified(folder) ? folder : null;
    }

    /// <summary>Pure: the whole path a name field gives (the name itself when it is one, else inside the folder); null
    /// when it cannot be known: no name, several names in quotes, a relative name with no folder of the disk.</summary>
    internal static string? Resolve(string? folder, string? name)
    {
        string said = (name ?? string.Empty).Trim();
        if (said.Length >= 2 && said[0] == '"' && said[^1] == '"' && said.Count(static c => c == '"') == 2)
            said = said[1..^1].Trim();
        if (said.Length == 0 || said.Contains('"') || said.IndexOfAny(System.IO.Path.GetInvalidPathChars()) >= 0)
            return null;
        try
        {
            if (System.IO.Path.IsPathFullyQualified(said))
                return System.IO.Path.GetFullPath(said);
            if (System.IO.Path.IsPathRooted(said) || folder is null)
                return null;
            return System.IO.Path.GetFullPath(System.IO.Path.Combine(folder, said));
        }
        catch (Exception exception) when (exception is ArgumentException or NotSupportedException or PathTooLongException)
        {
            return null;
        }
    }

    /// <summary>Pure: whether the control a click pressed is the dialog's button that saves or opens, by its window
    /// (UI Automation's runtime id of a window's own element is «42.» and its handle) or, pressed another way, by its
    /// caption.</summary>
    internal static bool PressedAccept(Facts facts, string? identity, string? name, string? kind) =>
        identity == "42." + facts.Accept.ToString(System.Globalization.CultureInfo.InvariantCulture)
        || (kind is null or "Button" or "SplitButton" && facts.AcceptText.Length > 0
            && string.Equals(Plain(name ?? string.Empty).Replace("&", string.Empty, StringComparison.Ordinal),
                facts.AcceptText, StringComparison.OrdinalIgnoreCase));

    /// <summary>
    /// Pure: the receipt of an act that confirmed the dialog, from what the dialog did. Closed with the file there: the
    /// act's own receipt, with where the file is. Closed with the file not there, still open, or answered by another
    /// window over it: a failure that says so, never a completed press (the save or the opening did not happen yet).
    /// </summary>
    internal static ExternalCapabilityReceipt Apply(ExternalCapabilityReceipt acted, Facts before, Outcome outcome, bool next)
    {
        void Facts(Utf8JsonWriter writer)
        {
            writer.WriteStartObject("fileDialog");
            writer.WriteBoolean("closed", outcome.Ending == Ending.Closed);
            if (outcome.Path is { } path)
                writer.WriteString("path", path);
            else
                writer.WriteBoolean("pathKnown", false);
            if (outcome.Exists is bool exists)
                writer.WriteBoolean("exists", exists);
            if (before.Address is { } shown && outcome.Path is null)
                writer.WriteString("folderShown", shown);
            if (outcome.BlockedBy is { } blocked)
                writer.WriteString("answeredBy", blocked);
            if (outcome.Ending == Ending.Open && outcome.FolderNow is { } folderNow)
                writer.WriteString("folderNow", folderNow);
            if (outcome.Ending == Ending.Open && outcome.NameNow is { } nameNow)
                writer.WriteString("nameNow", nameNow);
            writer.WriteEndObject();
        }

        string? code = outcome switch
        {
            { Ending: Ending.Blocked } => "file_dialog_answered_by_another_window",
            { Ending: Ending.Open } => "file_dialog_still_open",
            { Ending: Ending.Closed, Exists: false } => "file_dialog_file_missing",
            _ => null,
        };
        // The dialog closed with the file there: that is the act's proof, also when the press's own post-read was lost.
        if (code is null)
            return acted.Verified
                ? acted with { Result = ExternalJson.Extended(acted.Result, Facts) }
                : ExternalJson.Success(acted.Operation, ExternalJson.Extended(acted.Result, Facts));
        string? hint = !next ? null : outcome.Ending switch
        {
            Ending.Blocked => "the dialog did not save or open yet: another window of it opened over it (an error, or a "
                + "question such as replacing a file); look at it (input_visible_controls) to read what it says",
            Ending.Open => "the dialog is still open and nothing was saved or opened: a name that is a folder goes into it, "
                + "and a name the dialog refuses stays; look at it again, write the whole path (C:\\…\\name.ext) in its "
                + "name field and press its button again",
            _ => "the dialog closed but no file is at that path: the application may have written it elsewhere or not at "
                + "all; do not say it was saved there",
        };
        JsonElement result = ExternalJson.Extended(acted.Result, writer =>
        {
            Facts(writer);
            if (hint is not null)
                writer.WriteString("next", hint);
        });
        return new ExternalCapabilityReceipt(acted.Operation, acted.EffectObserved || outcome.Ending != Ending.Open, false,
            result, code)
        {
            EffectMayHaveOccurred = true,
        };
    }

    /// <summary>
    /// Pure: the common file dialog a window owns, among the visible top-level windows. Live on the notebook (Chrome's
    /// «Guardar como» and «Abrir», 30-10): Chrome shows the dialog from another of its processes, so the look at Chrome
    /// read the browser «tapada por Guardar como» and never the dialog (a modal dialog is followed only inside the
    /// window's own process, VisibleControlSurface.ModalSurface). A file dialog the window owns is the window's, whatever
    /// process draws it.
    /// </summary>
    internal static nint OwnedBy(nint owner, IEnumerable<nint> tops, Func<nint, nint> ownerOf, Func<nint, bool> isFileDialog) =>
        owner == 0 ? 0 : tops.FirstOrDefault(top => top != owner && ownerOf(top) == owner && isFileDialog(top));

    /// <summary>Live: the visible common file dialog the window owns, or 0.</summary>
    internal static nint OwnedBy(nint owner)
    {
        if (owner == 0)
            return 0;
        var tops = new List<nint>();
        EnumChildProc each = (top, _) =>
        {
            if (IsWindowVisible(top) && GetWindow(top, GwOwner) == owner)
                tops.Add(top);
            return true;
        };
        _ = EnumWindows(each, 0);
        GC.KeepAlive(each);
        return OwnedBy(owner, tops, top => GetWindow(top, GwOwner), top => Read(top) is not null);
    }

    /// <summary>Live: the facts of a window when it is a common file dialog.</summary>
    internal static Facts? Read(nint window)
    {
        if (window == 0 || !IsWindow(window))
            return null;
        string dialogClass = ClassName(window);
        if (!string.Equals(dialogClass, DialogClass, StringComparison.Ordinal))
            return null;
        var children = new List<ChildWindow>();
        EnumChildProc each = (child, _) =>
        {
            string kind = ClassName(child);
            int id = GetDlgCtrlID(child);
            nint parent = GetParent(child);
            bool visible = IsWindowVisible(child);
            // Only what the facts read is asked for its text: the buttons, the edits and the address's breadcrumb.
            string text = kind is "Edit" or "Button" or "ToolbarWindow32" ? Text(child) : string.Empty;
            children.Add(new ChildWindow(child, parent, kind, id, visible, text));
            return children.Count < 4096;
        };
        _ = EnumChildWindows(window, each, 0);
        GC.KeepAlive(each);
        return Recognize(window, dialogClass, children);
    }

    /// <summary>
    /// Live: waits (bounded) for the dialog to close, to be answered by another of its windows, or to stay open; once
    /// closed, for the file it named to be there (an application writes it after the dialog closes).
    /// </summary>
    internal static async Task<Outcome> AwaitAsync(Facts before, DateTime actedUtc, CancellationToken cancellationToken)
    {
        string? path = before.Path;
        Ending ending = Ending.Open;
        string? blockedBy = null;
        for (int waited = 0; waited <= EndingWaitMs; waited += PollMs)
        {
            if (!IsWindow(before.Dialog) || !IsWindowVisible(before.Dialog))
            {
                ending = Ending.Closed;
                break;
            }

            if (!IsWindowEnabled(before.Dialog) && OwnedWindowOf(before.Dialog) is { } owned)
            {
                ending = Ending.Blocked;
                blockedBy = owned;
                break;
            }

            await Task.Delay(PollMs, cancellationToken).ConfigureAwait(false);
        }

        if (ending == Ending.Open)
        {
            Facts? now = Read(before.Dialog);
            return new Outcome(Ending.Open, path, null, null, now?.Folder ?? now?.Address, now?.Name);
        }

        if (ending == Ending.Blocked || path is null)
            return new Outcome(ending, path, null, blockedBy, null, null);
        for (int waited = 0; ; waited += PollMs)
        {
            if (Found(path, actedUtc) is { } found)
                return new Outcome(Ending.Closed, found, true, null, null, null);
            if (waited >= FileWaitMs)
                return new Outcome(Ending.Closed, path, false, null, null, null);
            await Task.Delay(PollMs, cancellationToken).ConfigureAwait(false);
        }
    }

    /// <summary>
    /// The path when it is there; a name typed without extension, the file the dialog gave the type's extension to
    /// (written since the act).
    /// </summary>
    internal static string? Found(string path, DateTime actedUtc)
    {
        try
        {
            if (File.Exists(path) || Directory.Exists(path))
                return path;
            string? folder = System.IO.Path.GetDirectoryName(path);
            string stem = System.IO.Path.GetFileName(path);
            if (folder is null || stem.Length == 0 || System.IO.Path.HasExtension(stem) || !Directory.Exists(folder))
                return null;
            return new DirectoryInfo(folder).EnumerateFiles(stem + ".*")
                .Where(file => file.LastWriteTimeUtc >= actedUtc.AddSeconds(-2))
                .OrderByDescending(static file => file.LastWriteTimeUtc)
                .Select(static file => file.FullName)
                .FirstOrDefault();
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException or ArgumentException)
        {
            return null;
        }
    }

    internal const int PollMs = 100;
    internal const int EndingWaitMs = 3000;
    internal const int FileWaitMs = 5000;

    // The title of the visible window the dialog owns (what disabled it), or null.
    private static string? OwnedWindowOf(nint dialog)
    {
        string? title = null;
        EnumChildProc each = (top, _) =>
        {
            if (IsWindowVisible(top) && GetWindow(top, GwOwner) == dialog)
            {
                title = Text(top);
                return false;
            }

            return true;
        };
        _ = EnumWindows(each, 0);
        GC.KeepAlive(each);
        return title;
    }

    // Windows puts direction marks around the names it shows («\u200eBAXY-bench»).
    private static string Plain(string text) =>
        new([.. text.Where(static c => c is not ('\u200e' or '\u200f' or '\u202a' or '\u202c'))]);

    private static unsafe string ClassName(nint hwnd)
    {
        char* buffer = stackalloc char[256];
        int length = GetClassNameW(hwnd, buffer, 256);
        return length <= 0 ? string.Empty : new string(buffer, 0, length);
    }

    private static unsafe string Text(nint hwnd)
    {
        if (SendMessageTimeoutW(hwnd, WmGetTextLength, 0, 0, AbortIfHung, TextTimeoutMs, out nint length) == 0
            || length <= 0 || length > MaximumText)
            return string.Empty;
        char[] buffer = new char[(int)length + 2];
        fixed (char* pointer = buffer)
        {
            if (SendMessageTimeoutW(hwnd, WmGetText, buffer.Length, (nint)pointer, AbortIfHung, TextTimeoutMs, out nint copied) == 0)
                return string.Empty;
            return new string(pointer, 0, (int)Math.Clamp((long)copied, 0, buffer.Length));
        }
    }

    private const uint WmGetText = 0x000D;
    private const uint WmGetTextLength = 0x000E;
    private const uint AbortIfHung = 0x0002;
    private const uint TextTimeoutMs = 300;
    private const int MaximumText = 4096;
    private const uint GwOwner = 4;

    private delegate bool EnumChildProc(nint hwnd, nint parameter);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool EnumChildWindows(nint parent, EnumChildProc callback, nint parameter);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool EnumWindows(EnumChildProc callback, nint parameter);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool IsWindow(nint hwnd);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool IsWindowVisible(nint hwnd);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool IsWindowEnabled(nint hwnd);

    [LibraryImport("user32.dll")]
    private static partial nint GetParent(nint hwnd);

    [LibraryImport("user32.dll")]
    private static partial nint GetWindow(nint hwnd, uint command);

    [LibraryImport("user32.dll")]
    private static partial int GetDlgCtrlID(nint hwnd);

    [LibraryImport("user32.dll", StringMarshalling = StringMarshalling.Utf16)]
    private static unsafe partial int GetClassNameW(nint hwnd, char* name, int count);

    [LibraryImport("user32.dll")]
    private static partial nint SendMessageTimeoutW(
        nint hwnd, uint message, nint wParam, nint lParam, uint flags, uint timeout, out nint result);
}
