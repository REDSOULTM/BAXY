using System.Globalization;
using System.Text.Json;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// Encargo 115 (R01, 0 of 21 with the held-out of encargo 75): a table typed cell by cell took a dozen calls, stayed in one
/// row and left its last cell being edited. Given whole it is one text: a tab between the cells of a row, a line break
/// between rows, as the model already writes a table for a file (e75a: <c>Material\tCantidad\tBodega\ncemento\t12…</c>).
/// </summary>
internal sealed record CellBlock(string[][] Rows)
{
    internal int Columns => Rows.Max(static row => row.Length);

    internal int Characters => Rows.Sum(static row => row.Sum(static cell => cell.Length));

    /// <summary>Whether the text has the form of a table: a tab or a line break, and no other control character.</summary>
    internal static bool Holds(string text) =>
        text.AsSpan().IndexOfAny('\t', '\n', '\r') >= 0
        && text.All(static character => !char.IsControl(character) || character is '\t' or '\n' or '\r');

    internal static CellBlock Parse(string text) => new(
        [.. text.ReplaceLineEndings("\n").TrimEnd('\n').Split('\n').Select(static row => row.Split('\t'))]);

    /// <summary>The worker's «activecell» answer with a range: each cell's address and value, row after row. Null when the
    /// grid did not answer or holds fewer cells than the table takes: nothing could prove it there.</summary>
    internal static GridCell[]? ReadRange(JsonElement root, int count)
    {
        if (root.ValueKind != JsonValueKind.Object || !root.TryGetProperty("range", out JsonElement range)
            || range.ValueKind != JsonValueKind.Array || range.GetArrayLength() != count)
            return null;
        var cells = new GridCell[count];
        int at = 0;
        foreach (JsonElement cell in range.EnumerateArray())
        {
            if (cell.ValueKind != JsonValueKind.Object
                || !cell.TryGetProperty("a", out JsonElement address) || address.ValueKind != JsonValueKind.String)
                return null;
            cells[at++] = new GridCell(
                address.GetString()!,
                cell.TryGetProperty("v", out JsonElement value) && value.ValueKind == JsonValueKind.String ? value.GetString()! : string.Empty);
        }

        return cells;
    }

    /// <summary>
    /// Whether a cell shows what was typed. A sheet shows a number by the cell's format («12.50» as 12.5, 1200 as 1,200)
    /// and a long value only in part (the worker reads 256 characters); anything else it changed (a date made of «3/4»)
    /// is told as what the cell holds.
    /// </summary>
    internal static bool Shows(string asked, string read)
    {
        string wanted = asked.Trim(), shown = read.Trim();
        if (string.Equals(wanted, shown, StringComparison.OrdinalIgnoreCase))
            return true;
        if (shown.Length >= MaximumRead && wanted.StartsWith(shown, StringComparison.OrdinalIgnoreCase))
            return true;
        // In the same culture both ways: «12.50» in a culture whose dot groups thousands is another number than «12.5».
        foreach (CultureInfo culture in (CultureInfo[])[CultureInfo.CurrentCulture, CultureInfo.InvariantCulture])
        {
            if (Number(wanted, culture) is decimal first && Number(shown, culture) is decimal second && first == second)
                return true;
        }

        return false;
    }

    private const int MaximumRead = 256;

    private static decimal? Number(string text, CultureInfo culture) =>
        decimal.TryParse(text, NumberStyles.Number | NumberStyles.AllowCurrencySymbol, culture, out decimal number) ? number : null;
}

internal readonly record struct GridCell(string Address, string Value);
