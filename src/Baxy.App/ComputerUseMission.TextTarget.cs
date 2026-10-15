using System.Text.Json.Nodes;

namespace Baxy.App;

// Where typed text goes: the field a text step names, the focused field, a search field.
internal static partial class ComputerUseMission
{
    /// <summary>
    /// The field of this view that takes text (or a combo box) and that the label names: its name (its own, its
    /// LabeledBy, or the text that labels it on screen, which the view gives as its name) folded equal to the label.
    /// Two fields of one name (a size group and a skew group that both say «Horizontal»): the first in the view's
    /// reading order, the one a person fills first, as the mind's step names it (review of v3 point 2). Null when none
    /// does.
    /// </summary>
    internal static int? LabelledField(JsonObject? view, string label)
    {
        if (view?["controls"] is not JsonArray controls || FieldLabel(label) is not { Length: > 0 } wanted)
            return null;
        JsonObject[] named = [.. controls.OfType<JsonObject>()
            .Where(control => TakesText(control) && control["i"] is not null
                && FieldLabel((string?)control["name"]) == wanted)];
        return named.Length > 0 ? (int?)named[0]["i"] : null;
    }

    // A field's label folded the same on both sides, the step's and the view's: the colon that ends a label on screen
    // («Nombre de archivo:») is the label's punctuation, not a word of it.
    private static string FieldLabel(string? label) =>
        ComputerUseSuccessCheck.Fold(label).TrimEnd(':', '：', ' ');

    /// <summary>
    /// Where a text step goes, on its receipt. «into»: the control that had the keyboard on the view it was decided on
    /// (typed into a search it echoes in the suggestions; typed into a name box, a folder being created or renamed, it
    /// is the item's own name, check atom control:). «atCaret»: the step named no field and goes where the keyboard is,
    /// by no index or by the focused field's own index (<see cref="TextField"/> read from window.focused). That index is
    /// the App's, never a choice of the step (review 2 of r20 P1, finding 1: <see cref="OperationFloor.TypedIntoUnnamedPart"/>).
    /// </summary>
    internal static void NoteWhereTheTextGoes(JsonObject record, JsonObject arguments, JsonObject? view)
    {
        if ((string?)view?["window"]?["process"] is { Length: > 0 } typedOn)
        {
            // Ronda 23 (v3-58): the application typed on; a later turn reads its echo only on that application's window.
            record["typedOn"] = typedOn;
        }

        if (view?["window"]?["focused"] is JsonObject typedInto)
        {
            record["into"] = (string?)typedInto["name"] ?? string.Empty;
            // Review 3 of r20 P1 (B1): the control the window's title names is the document itself (Word's body is the
            // Document called as the file, «Proyecto de título»), never a part of it, whatever words that name holds.
            if (OperationFloor.NamesTheWindow((string?)typedInto["name"], (string?)view["window"]?["title"]))
                record["intoDocument"] = true;
        }

        // Ronda 24 (v3-59): the field the step named (by its name, or by an index other than the focus's) is the one that
        // took the text, never the control the keyboard was on: «Curicó» typed with field «Escribe el término de
        // búsqueda» while the address bar had the focus is a query in a search box, and its echo is read so.
        if (NamedField(arguments, view) is { Length: > 0 } named)
        {
            record["into"] = named;
            record.Remove("intoDocument");
        }

        if ((string?)arguments["field"] is not { Length: > 0 }
            && (arguments["index"] is null || (int?)arguments["index"] == FocusedTextField(view)))
            record["atCaret"] = true;

        // Ronda 24b (banco r23 c6): «intoSearch», the control that took the text is the window's search box (by its own
        // name, data «computerUse.searchField»); «otherField», the view had another field a text is written in (no
        // search, address, password or read-only part). A free «escribir X» typed at the caret into a search while such
        // a field was there is not written (check marker «stepDone:input.text.type:written»).
        JsonObject? keyboard = view?["window"]?["focused"] as JsonObject;
        string? intoName = (string?)record["into"];
        // Revisión 1 de r24b (B3): the named field is judged as the control it is (a Document by its whole name only).
        JsonObject? namedControl = NamedField(arguments, view) is { Length: > 0 } namedName
            ? (view?["controls"] as JsonArray ?? []).OfType<JsonObject>().FirstOrDefault(control =>
                ComputerUseSuccessCheck.Fold((string?)control["name"]).Trim() == ComputerUseSuccessCheck.Fold(namedName).Trim())
              ?? new JsonObject { ["kind"] = "Edit", ["name"] = namedName }
            : null;
        bool intoSearch = record.ContainsKey("into") && (namedControl is not null
            ? SearchField(namedControl, view)
            : keyboard is not null && SearchField(keyboard, view));
        if (intoSearch)
        {
            record["intoSearch"] = true;
            record["otherField"] = (view?["controls"] as JsonArray ?? []).OfType<JsonObject>().Any(control =>
                (string?)control["kind"] is "Edit" or "Document"
                && !((string?)control["state"] ?? string.Empty).Split(' ').Any(state => state is "password" or "readonly" or "disabled")
                && !SearchField(control, view)
                && !OperationFloor.AddressFieldName(ComputerUseSuccessCheck.Fold((string?)control["name"]))
                && ComputerUseSuccessCheck.Fold((string?)control["name"]).Trim() != ComputerUseSuccessCheck.Fold(intoName).Trim());
        }
    }

    // A text field that is the window's search by its own name (never a fallback name, «nameSource»), never a password:
    // the mind's cu_fields._search_field_box over the same data. Revisión 1 de r24b (B3): only an Edit or a ComboBox
    // is a search by a search word in its name; a Document is one only when its whole name is a search label («Buscar:»),
    // it is one line high and small, and no other Document of the view is larger (the mind's _search_document): a
    // document titled «Búsqueda de empleo» or «Ir a la playa» is the person's work, never a search.
    internal static bool SearchField(JsonObject control, JsonObject? view = null)
    {
        if ((string?)control["nameSource"] is { Length: > 0 }
            || ((string?)control["state"] ?? string.Empty).Contains("password", StringComparison.Ordinal))
        {
            return false;
        }

        string name = ComputerUseSuccessCheck.Fold((string?)control["name"]);
        switch ((string?)control["kind"])
        {
            case "Edit" or "ComboBox":
                return OperationFloor.SearchFieldName(name);
            case "Document":
                break;
            default:
                return false;
        }

        if (!OperationFloor.SearchLabelName(name.Trim().TrimEnd(':', '.', '…').Trim()))
        {
            return false;
        }

        if (control["rect"] is not JsonObject rect || Area(rect) <= 0)
        {
            return true;
        }

        double windowArea = view?["window"]?["rect"] is JsonObject windowRect ? Area(windowRect) : 0;
        if (Number(rect["h"]) > SearchDocumentLineHeight || (windowArea > 0 && Area(rect) > windowArea * SearchDocumentShare))
        {
            return false;
        }

        double[] larger = (view?["controls"] as JsonArray ?? []).OfType<JsonObject>()
            .Where(other => !ReferenceEquals(other, control) && (string?)other["kind"] == "Document"
                && !((int?)other["i"] is int at && (int?)control["i"] == at)
                && other["rect"] is JsonObject)
            .Select(other => Area((JsonObject)other["rect"]!)).Where(area => area > 0).ToArray();
        return larger.Length == 0 || larger.Max() > Area(rect);
    }

    // The mind's cu_view._ONE_LINE_HEIGHT and _SMALL_FIELD_SHARE.
    private const double SearchDocumentLineHeight = 80;
    private const double SearchDocumentShare = 1.0 / 20;

    // The name of the field a text step names other than the focused one: «field» when it differs from the focused
    // control's name, else the control of the view at «index» when that index is not the focus's. Null otherwise.
    private static string? NamedField(JsonObject arguments, JsonObject? view)
    {
        JsonObject? focused = view?["window"]?["focused"] as JsonObject;
        string focusedName = ComputerUseSuccessCheck.Fold((string?)focused?["name"]).Trim();
        if ((string?)arguments["field"] is { Length: > 0 } field)
            return ComputerUseSuccessCheck.Fold(field).Trim() == focusedName ? null : field;
        if (arguments["index"] is not JsonValue at || !at.TryGetValue(out int index)
            || (focused?["i"] is JsonValue focusedAt && focusedAt.TryGetValue(out int focusedIndex) && focusedIndex == index))
            return null;
        JsonObject? control = (view?["controls"] as JsonArray ?? []).OfType<JsonObject>().FirstOrDefault(item => (int?)item["i"] == index);
        return (string?)control?["name"] is { Length: > 0 } name && ComputerUseSuccessCheck.Fold(name).Trim() != focusedName ? name : null;
    }

    /// <summary>
    /// The field of this view a text goes to: the focused control when it takes text, else the field the sub-goal's
    /// last click aimed at (one control of this view carrying its label). A window in the background may not report
    /// its keyboard focus; the clicked field is what the person would have typed into. Null: no field named, the
    /// provider writes where the window's own focus is.
    /// </summary>
    internal static int? TextField(JsonObject? view, JsonArray? steps)
    {
        if (view?["controls"] is not JsonArray controls)
            return null;
        if (FocusedTextField(view) is int position)
            return position;
        if (steps is not { Count: > 0 } || steps[^1] is not JsonObject last
            || (string?)last["operation"] != "input.visible.click"
            || ComputerUseSuccessCheck.Fold((string?)last["label"]) is not { Length: > 0 } label)
            return null;
        JsonObject[] named = [.. controls.OfType<JsonObject>()
            .Where(control => TakesText(control) && control["i"] is not null
                && ComputerUseSuccessCheck.Fold((string?)control["name"]) == label)];
        return named.Length == 1 ? (int?)named[0]["i"] : null;
    }

    /// <summary>The index window.focused gives the control that has the keyboard, when that control of the view takes text.</summary>
    internal static int? FocusedTextField(JsonObject? view) =>
        view?["controls"] is JsonArray controls
        && view["window"]?["focused"] is JsonObject focused && focused["i"] is JsonValue at
        && at.TryGetValue(out int position)
        && controls.OfType<JsonObject>().Any(control => (int?)control["i"] == position && TakesText(control))
            ? position
            : null;

    // A control that takes typed text: a field, a document or an editable box, neither read-only nor a password.
    private static bool TakesText(JsonObject control) =>
        (string?)control["kind"] is "Edit" or "Document" or "ComboBox"
        && ((string?)control["state"] ?? string.Empty).Split(' ') is var states
        && !states.Contains("readonly") && !states.Contains("password");
}
