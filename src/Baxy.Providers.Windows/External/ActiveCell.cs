using System.Text.Json;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// Encargo 75 (R01, banco de entorno del NB): six values typed into a spreadsheet with no key between them all went into
/// its first cell, each call completed, and the reply told a table in two columns (2 of 3). A grid keeps a typed text in
/// an editor over the active cell until a key ends it, so the cell's own value does not show it and nothing said which
/// cell the keys went to. The active cell as the worker's «activecell» reads it through UI Automation's GridItem and
/// Value patterns (a grid's own patterns, of any application that publishes them), said in the receipt.
/// </summary>
internal sealed record ActiveCell(
    string Address, int Row, int Column, bool Editing, string Value, string Right, string Id = "", string Below = "", string Corner = "")
{
    internal static ActiveCell? Read(JsonElement root)
    {
        if (root.ValueKind != JsonValueKind.Object
            || !root.TryGetProperty("ok", out JsonElement ok) || ok.ValueKind != JsonValueKind.True
            || !root.TryGetProperty("address", out JsonElement address) || address.ValueKind != JsonValueKind.String
            || !root.TryGetProperty("row", out JsonElement row) || !row.TryGetInt32(out int rowNumber)
            || !root.TryGetProperty("column", out JsonElement column) || !column.TryGetInt32(out int columnNumber))
            return null;
        return new ActiveCell(
            address.GetString()!,
            rowNumber,
            columnNumber,
            root.TryGetProperty("editing", out JsonElement editing) && editing.ValueKind == JsonValueKind.True,
            root.TryGetProperty("value", out JsonElement value) && value.ValueKind == JsonValueKind.String
                ? value.GetString()!
                : string.Empty,
            root.TryGetProperty("right", out JsonElement right) && right.ValueKind == JsonValueKind.String
                ? right.GetString()!
                : string.Empty,
            root.TryGetProperty("id", out JsonElement id) && id.ValueKind == JsonValueKind.String ? id.GetString()! : string.Empty,
            root.TryGetProperty("below", out JsonElement below) && below.ValueKind == JsonValueKind.String ? below.GetString()! : string.Empty,
            root.TryGetProperty("corner", out JsonElement corner) && corner.ValueKind == JsonValueKind.String ? corner.GetString()! : string.Empty);
    }

    // The value of the cell asked by its row and column (the one a key just left), as the same answer brings it.
    internal static string? ValueAt(JsonElement root) =>
        root.ValueKind == JsonValueKind.Object
        && root.TryGetProperty("at", out JsonElement at) && at.ValueKind == JsonValueKind.Object
        && at.TryGetProperty("value", out JsonElement value) && value.ValueKind == JsonValueKind.String
            ? value.GetString()
            : null;

    internal bool Moved(ActiveCell before) => Row != before.Row || Column != before.Column;

    internal static void WriteCell(Utf8JsonWriter writer, string name, string address, string value, string? pending = null)
    {
        writer.WriteStartObject(name);
        writer.WriteString("address", address);
        writer.WriteString("value", value);
        if (pending is not null)
            writer.WriteString("pendingText", pending);
        writer.WriteEndObject();
    }

    private string Ends(nint window) =>
        $"A key ends {Address}: input_key_press with window {window} and key tab goes to "
        + (Right.Length == 0 ? "the cell on its right" : Right) + ", with key enter goes to the next row";

    // Encargo 115: what a table is to this tool, said where the model first needs it (CellBlock).
    private static string Whole(nint window) =>
        $"A whole table goes as one input_text_type with window {window}: all its rows in one text, from this cell, with a tab "
        + "between the cells of a row and a line break between rows; it ends every cell, the last one too, and reads them back";

    /// <summary>
    /// Encargo 115, measured with the real model in the world «hoja» (R01, H1, held-out and controls, 2 seeds each). A next
    /// that names a key is followed: the table stays in one row (0 of 16). Saying the table in the tool's description did not
    /// move it (1 of 16), nor did a call first (0 of 7). The fact first and the call last, with the skeleton by the cells'
    /// addresses, on the first text for a cell (nothing there yet to undo): R01 2 of 2, T5 2 of 2, H1 1 of 2, controls 6 of 6,
    /// which then write their one value by calling again.
    /// </summary>
    internal static string TableNext(nint window, string why, string single, ActiveCell? cell)
    {
        static string Goes(string address, string otherwise) =>
            address.Length == 0 ? $"<{otherwise}>" : $"<what goes in {address}>";
        string from = cell is null ? "the active cell" : $"the active cell {cell.Address}";
        string call = $"{Baxy.Kernel.Operations.WireNames.Of("input.text.type")} {{\"window\":{window},\"text\":\""
            + $"{Goes(cell?.Address ?? string.Empty, "a cell")}\\t{Goes(cell?.Right ?? string.Empty, "the next cell")}"
            + $"\\n{Goes(cell?.Below ?? string.Empty, "the next row's cell")}\\t{Goes(cell?.Corner ?? string.Empty, "the next cell")}\"}}";
        return $"{why}. A whole table goes in one call from {from}, one line per row of the sheet, each value in its own cell, the "
            + $"last one ended too, and reads them back: {call}. {single}";
    }

    internal string FirstTextNext(nint window) => TableNext(
        window, $"this call typed nothing: the keyboard's focus is on the cell {Address} of a sheet",
        "For this one value alone, call it again exactly as before", this);

    internal string PendingNext(nint window, string pending) =>
        $"«{pending}» is still pending in {Address}, and a text typed now would join it in that one cell. {Ends(window)}. "
        + Whole(window);

    internal string RefusedNext(nint window, string pending) => TableNext(
        window, $"this call typed nothing: «{pending}» is still pending in {Address} and this text would have joined it in that "
        + "one cell", "To join it to that cell, call it again exactly as before", this);
}
