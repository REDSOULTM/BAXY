using System.Text.Json;
using Baxy.Kernel.Policy;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// Auditoría del núcleo 2026-10-23: input.key.press's <c>target:"text_field"</c> is the model's own word, and RiskPolicy
/// lets Delete and Enter go unasked on it (Delete only erases characters there; Enter there sends nothing). The
/// key press's preflight reads what really holds the keyboard's focus (the UI Automation worker's «focuskind») before
/// either goes unasked: a focus that is no text field (a file list, a button, a message list), one outside the window
/// the key goes to, or one that cannot be read, asks the person, bound to that press. A messaging client's composer and
/// a console's line are text fields for typing, never for Enter, which sends or runs what they hold: Enter declared on a
/// text field asks in a window that is not ordinary (<see cref="KeyWindowKind"/>). Space types a space in a text field;
/// on another control it asks when that control's name is empty or would ask.
/// </summary>
internal static class DeclaredTextFieldPress
{
    internal const string Operation = "input.key.press";

    /// <summary>Pure: whether this call declares a text field for a key whose effect elsewhere needs the person's yes.</summary>
    internal static bool Applies(string operation, JsonElement arguments) =>
        operation == Operation
        && arguments.ValueKind == JsonValueKind.Object
        && Text(arguments, "target") == "text_field"
        && Text(arguments, "key") is "enter" or "space" or "delete";

    /// <summary>
    /// Whether the press needs the person's yes, from what holds the focus (<paramref name="focus"/>, null when it
    /// could not be read) and the kind of window the key goes to.
    /// </summary>
    internal static bool NeedsYes(JsonElement arguments, FocusRead? focus, KeyWindowKind window)
    {
        if (focus is not { Inside: true } read)
        {
            return true;
        }

        // Decisión del dueño 2026-10-25 («que Baxy no te moleste todo el tiempo… sino para cosas que realmente son
        // peligrosas»): space on a focus read inside the window that is no text field (a check box, a switch, a button)
        // toggles or presses that control. With a name read it asks only when a click on that name would ask (it sends,
        // buys, deletes: RiskPolicy); a control with no name read presses what nobody can judge and asks, as a click
        // under the pointer does. Delete and Enter there still ask.
        if (!read.IsTextField)
        {
            return Text(arguments, "key") != "space"
                || string.IsNullOrWhiteSpace(read.Name)
                || RiskPolicy.PressedNameAsksMoreThanItsLabel(null, read.Name);
        }

        return Text(arguments, "key") == "enter" && window != KeyWindowKind.Ordinary;
    }

    /// <summary>The worker's «focuskind» answer; null when it did not answer or said it could not read the focus.</summary>
    internal static FocusRead? Read(JsonDocument? answer)
    {
        if (answer?.RootElement is not { ValueKind: JsonValueKind.Object } root
            || !root.TryGetProperty("ok", out JsonElement ok) || ok.ValueKind != JsonValueKind.True)
        {
            return null;
        }

        return new FocusRead(
            Text(root, "kind") ?? string.Empty,
            Flag(root, "editable"),
            Flag(root, "text"),
            Flag(root, "inside"),
            Text(root, "name") ?? string.Empty)
        {
            ReadOnly = Flag(root, "readOnly"),
        };
    }

    private static string? Text(JsonElement element, string name) =>
        element.TryGetProperty(name, out JsonElement value) && value.ValueKind == JsonValueKind.String
            ? value.GetString()
            : null;

    private static bool Flag(JsonElement element, string name) =>
        element.TryGetProperty(name, out JsonElement value) && value.ValueKind == JsonValueKind.True;
}

/// <summary>What holds the keyboard's focus, as UI Automation reads it: its control type, whether its value can be edited,
/// whether it has a TextPattern, whether it lies inside the window the key goes to, and its name as a look gives it.</summary>
internal readonly record struct FocusRead(string Kind, bool Editable, bool HasText, bool Inside, string Name = "")
{
    /// <summary>An edit box or a document whose text can be written: where Delete erases characters.</summary>
    internal bool IsTextField => Kind is "Edit" or "Document" && (Editable || HasText);

    /// <summary>Revisión de la guarda F013 (teclas): a control that Enter and space press themselves (a button, a link,
    /// a menu entry); on any other, space toggles, types or selects, and Enter goes to the dialog's default button.</summary>
    internal bool IsPressedByAKey => Kind is "Button" or "SplitButton" or "Hyperlink" or "MenuItem";

    /// <summary>Encargo 36: its value says it cannot be edited (UI Automation's ValuePattern.IsReadOnly).</summary>
    internal bool ReadOnly { get; init; }

    /// <summary>
    /// Encargo 36 (banco uso-b4c4, R11, R12, R13, S08): a focus whose keys turn into something other than text, by UI
    /// Automation, as <see cref="WindowsTextDelivery.TakesNoText"/> is by a Win32 class: a menu (its letters are access
    /// keys), a button, a check box or a radio button, a list, a tree, a tab strip or a grid's header (their letters
    /// move the selection), a scroll bar, a slider or a toolbar, unless its own value can be edited; or an edit box or a
    /// document whose value says it is read-only (a page's document). A pane, a custom control or a document with no
    /// value (a console, a word processor) may take typing and is not judged.
    /// </summary>
    internal bool TakesNoText =>
        Kind is "Edit" or "Document" ? ReadOnly : !Editable && NoTextKinds.Contains(Kind);

    private static readonly HashSet<string> NoTextKinds = new(StringComparer.Ordinal)
    {
        "MenuBar", "Menu", "MenuItem", "Button", "SplitButton", "CheckBox", "RadioButton", "List", "ListItem", "Tree",
        "TreeItem", "Tab", "TabItem", "Header", "HeaderItem", "ScrollBar", "Slider", "ToolBar", "TitleBar",
    };
}
