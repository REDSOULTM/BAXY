using System.Text.Json;
using System.Text.Json.Nodes;

namespace Baxy.Providers.Windows.External;

/// <summary>Encargo 98: how a field's whole text was asked to be selected, and the dialog the keys raised, if any.</summary>
internal readonly record struct FieldSelection(bool ByUiAutomation, string? DialogTitle = null, bool DialogClosed = false);

/// <summary>
/// Encargo 98: what a shortcut can change that no window of its own shows (the worker's «focusstate»): the dialog drawn inside
/// the window that holds the focus, by its name, and the text attributes of the selection, in no language's words.
/// </summary>
internal sealed record FocusState(string? InnerWindow, string? Format, string? Place = null, string? Content = null)
{
    // The attributes of the worker's «format», in its order.
    private static readonly string[] FormatParts =
        ["weight", "italic", "underline", "strikethrough", "alignment", "first line indent", "indent", "size", "font", "color"];

    /// <summary>Encargo 100: what differs between two «format» reads, by the attribute's name: none of it depends on the language.</summary>
    internal static string FormatChange(string before, string after)
    {
        string[] was = before.Split('|'), now = after.Split('|');
        IEnumerable<string> changed = FormatParts.Where((_, part) => part < was.Length && part < now.Length && was[part] != now[part]);
        return was.Length == FormatParts.Length && now.Length == FormatParts.Length && changed.Any()
            ? string.Join(" and ", changed)
            : "format";
    }

    /// <summary>Encargo 100: how many characters the selection held, the last part of <see cref="Place"/>.</summary>
    internal int SelectedLength =>
        Place is { } place && int.TryParse(place[(place.LastIndexOf('|') + 1)..], out int length) ? length : 0;

    internal static string Command(nint window) => new JsonObject
    {
        ["cmd"] = "focusstate",
        ["hwnd"] = (long)window,
    }.ToJsonString();

    /// <summary>The worker's answer; null when it read nothing, or the focus is another window's.</summary>
    internal static FocusState? Read(JsonDocument? answer)
    {
        if (answer?.RootElement is not { ValueKind: JsonValueKind.Object } root
            || !root.TryGetProperty("ok", out JsonElement ok) || ok.ValueKind != JsonValueKind.True
            || !root.TryGetProperty("inside", out JsonElement inside) || inside.ValueKind != JsonValueKind.True)
            return null;
        return new FocusState(Named(root, "innerWindow"), Named(root, "format"), Named(root, "place"), Named(root, "content"));
    }

    internal static string CloseCommand(nint window) => new JsonObject
    {
        ["cmd"] = "focusdialogclose",
        ["hwnd"] = (long)window,
    }.ToJsonString();

    internal static bool CloseAsked(JsonDocument? answer) =>
        answer?.RootElement is { ValueKind: JsonValueKind.Object } root
        && root.TryGetProperty("asked", out JsonElement asked)
        && asked.ValueKind == JsonValueKind.True;

    private static string? Named(JsonElement root, string name) =>
        root.TryGetProperty(name, out JsonElement value) && value.ValueKind == JsonValueKind.String
            && value.GetString() is { Length: > 0 } text
            ? text
            : null;
}

/// <summary>Encargo 100: what the worker's «focusfind» reads, no text in it.</summary>
internal readonly record struct FindReach(bool MenuBar, bool EditableDocument, int Selected)
{
    internal static string Command(nint window) => new JsonObject
    {
        ["cmd"] = "focusfind",
        ["hwnd"] = (long)window,
    }.ToJsonString();

    internal static FindReach? Read(JsonDocument? answer) =>
        answer?.RootElement is { ValueKind: JsonValueKind.Object } root
        && root.TryGetProperty("ok", out JsonElement ok) && ok.ValueKind == JsonValueKind.True
        && root.TryGetProperty("menuBar", out JsonElement menuBar) && menuBar.ValueKind is JsonValueKind.True or JsonValueKind.False
        && root.TryGetProperty("editableDocument", out JsonElement editable) && editable.ValueKind is JsonValueKind.True or JsonValueKind.False
        && root.TryGetProperty("selected", out JsonElement selected) && selected.TryGetInt32(out int length)
            ? new FindReach(menuBar.GetBoolean(), editable.GetBoolean(), length)
            : null;

    internal static string TabCountCommand(nint window) => new JsonObject
    {
        ["cmd"] = "tabcount",
        ["hwnd"] = (long)window,
    }.ToJsonString();

    internal static int? TabCount(JsonDocument? answer) =>
        answer?.RootElement is { ValueKind: JsonValueKind.Object } root
        && root.TryGetProperty("tabs", out JsonElement tabs) && tabs.TryGetInt32(out int count)
            ? count
            : null;
}

/// <summary>
/// Encargo 98: Ctrl+A is a shortcut of the application, which each language binds as it likes (Microsoft, Keyboard
/// accelerators: «in the Spanish version of Windows, Ctrl+N is used for bold»; Windows 11's Notepad and Word in Spanish open
/// «Abrir» with Ctrl+A, measured). The focused field is asked first (ITextRangeProvider::Select on its DocumentRange, read
/// back); the keys are the last resort, for a field with no TextPattern, and a dialog they raise is closed as its Cancel and
/// told, so nothing typed next goes into it.
/// </summary>
internal static class FocusedFieldSelection
{
    private const int RaisedWaitMs = 300;
    private const int RaisedPollMs = 50;

    internal static string Command(nint window) => new JsonObject
    {
        ["cmd"] = "focusselect",
        ["hwnd"] = (long)window,
    }.ToJsonString();

    /// <summary>Only a selection the worker read back counts; any other answer leaves the keys.</summary>
    internal static bool Selected(JsonDocument? answer) =>
        answer?.RootElement is { ValueKind: JsonValueKind.Object } root
        && root.TryGetProperty("selected", out JsonElement selected)
        && selected.ValueKind == JsonValueKind.True;

    internal static async ValueTask<FieldSelection> SelectAsync(
        nint window,
        Func<nint, CancellationToken, ValueTask<bool>> byUiAutomation,
        Action pressKeys,
        IDesktopKeyboard windows,
        CancellationToken cancellationToken)
    {
        if (await byUiAutomation(window, cancellationToken).ConfigureAwait(false))
            return new FieldSelection(true);
        WindowWitness? before = windows.Witness(window);
        pressKeys();
        if (before is not { } witnessed)
            return new FieldSelection(false);
        for (int waited = 0; ; waited += RaisedPollMs)
        {
            if (windows.RaisedSince(witnessed, window) is { } raised)
                return new FieldSelection(false, raised.Title, windows.CloseRaised(raised.Window));
            if (waited >= RaisedWaitMs)
                return new FieldSelection(false);
            await Task.Delay(RaisedPollMs, cancellationToken).ConfigureAwait(false);
        }
    }
}
