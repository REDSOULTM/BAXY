using System.Text.Json;

namespace Baxy.Providers.Windows.External;

internal sealed partial class WindowsDesktopInteractionAdapter
{
    internal const string CellBeingEdited = "input_cell_being_edited";
    internal const string CellNotActive = "input_cell_not_active";
    internal const string FirstCellText = "input_first_cell_text";

    // How long the model's choice of one value at a time holds for a window: a table asked later is told again.
    private const long FirstCellTextToldMs = 300_000;

    private readonly System.Collections.Concurrent.ConcurrentDictionary<nint, long> _firstCellTextTold = new();

    // The text refused over one still pending in a window, by window, until the next text goes.
    private readonly System.Collections.Concurrent.ConcurrentDictionary<nint, string> _pendingRefused = new();

    private bool FirstCellTextOwed(nint window)
    {
        long now = Ticks();
        if (_firstCellTextTold.TryGetValue(window, out long told) && now - told < FirstCellTextToldMs)
            return false;
        _firstCellTextTold[window] = now;
        return true;
    }
    internal const string CellsNotEmpty = "input_cells_not_empty";
    internal const string CellsNotReadBack = "input_cells_not_read_back";
    internal const string CellLeftTheTable = "input_cell_left_the_table";

    private const int BlockCellPolls = 10;
    private const int BlockCellPollMs = 50;

    // How many cells a receipt lists: a table this size is told by its corners and what differs.
    private const int ToldCells = 60;

    /// <summary>
    /// Encargo 115: a table given whole goes into a grid by its keys, as a person types one: Tab between the cells of a row,
    /// Enter at its end, which goes back under the column the row began at (measured on Excel 16; Microsoft documents the
    /// option that can change it, so it is read, not assumed). A paste would fill the cells too, but it replaces what the
    /// person holds on the clipboard, and what a restore gives back is not all of it (delayed rendering, ClipboardContracts.cs).
    /// Only a grid's active cell takes it, read right before the first key: anywhere else a line break can send what a field
    /// holds, and the text is refused as it always was. Cells that hold something are not typed over unless
    /// <paramref name="replace"/> says so. Each key is read back by the cell it reached, and the first one that reached
    /// another stops the rest (a row past the grid's end, a key the application took otherwise). The last cell is ended with
    /// the rest, and the receipt is what the cells hold, read back.
    /// </summary>
    private async ValueTask<ExternalCapabilityReceipt> CellBlockAsync(
        string operation, string text, nint window, int? index, bool replace, long deadline, CancellationToken cancellationToken)
    {
        CellBlock block = CellBlock.Parse(text);
        long fits = Math.Max(0, deadline - Ticks()) / TypedCharacterMs;
        if (block.Characters > fits)
        {
            return ExternalJson.FailureBeforeEffect(operation, "input_text_too_long_to_type") with
            {
                Result = ExternalJson.Create(writer =>
                {
                    writer.WriteStartObject();
                    writer.WriteNumber("charactersThatFit", fits);
                    writer.WriteNumber("charactersAsked", block.Characters);
                    writer.WriteEndObject();
                }),
            };
        }

        IInputBurst? burst = null;
        if (window != 0)
        {
            try
            {
                burst = await _keyboard.FrontAsync(window, cancellationToken).ConfigureAwait(false);
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
            return await CellBlockInFrontAsync(operation, block, window, index, replace, bursts, deadline, cancellationToken).ConfigureAwait(false);
        }
        finally
        {
            _ = bursts.Restore();
        }
    }

    private async ValueTask<ExternalCapabilityReceipt> CellBlockInFrontAsync(
        string operation, CellBlock block, nint window, int? index, bool replace, LeasedBursts bursts, long deadline, CancellationToken cancellationToken)
    {
        DesktopForeground before = _keyboard.Foreground();
        if (before.Window == 0 || _keyboard.InputSize != (IntPtr.Size == 8 ? 40 : 28))
            return ExternalJson.FailureBeforeEffect(operation, "key_press_sendinput_failed");
        if (window != 0 && !_keyboard.Holds(window))
            return ExternalJson.FailureBeforeEffect(operation, "input_window_changed");
        string sentToProcess = _keyboard.ProcessName(before.Window);

        if ((await ActiveCellAsync(before.Window, null, cancellationToken).ConfigureAwait(false)).Cell is not { } start)
            return ExternalJson.FailureBeforeEffect(operation, "desktop_interaction_argument_invalid") with
            {
                Result = BlockFact("a text with a tab or a line break goes only to a grid's active cell, and none holds the "
                    + "keyboard's focus here: nothing was typed. Each is a key of its own: input_key_press"),
            };

        // e75d (H1): after a look the model names cells by index. The keys go to the active cell whatever UI Automation's focus
        // says (live, Excel 16: SetFocus on C1 left the keys in A1), so a table aimed at another cell is not typed.
        if (index is int aimed
            && (_fields is null || !_fields.TryViewedField(aimed, out nint viewed, out string controlId)
                || viewed != before.Window || controlId != start.Id))
            return ExternalJson.FailureBeforeEffect(operation, CellNotActive) with
            {
                // T1, live: after a row the active cell was already the next one, and the model clicked and named an old index.
                Result = BlockFact($"nothing was typed: this table would go from the active cell, {start.Address}, not the one at "
                    + $"index {aimed}. With no index it goes from {start.Address}; for another cell, a click on it makes it the active one", start),
            };

        // What this adapter left pending in that cell is its own to take back when the table begins with it; what the person
        // left being edited is theirs.
        string? pending = start.Editing && _pendingCells.TryGetValue(before.Window, out PendingCell? held) && held.Address == start.Address
            ? held.Text
            : null;
        bool oursPending = pending is not null;
        if (start.Editing && !oursPending)
            return ExternalJson.FailureBeforeEffect(operation, CellBeingEdited) with
            {
                // Live, Excel 16: a click on a cell by its pattern leaves it being edited too. What the editor holds cannot be
                // read, so it may be the person's: the keys are the model's to choose.
                Result = BlockFact($"nothing was typed: {start.Address} is being edited. A key ends it: escape leaves the cell "
                    + "as it was, enter keeps what it holds", start),
            };
        if (oursPending && pending != block.Rows[0][0])
            return ExternalJson.FailureBeforeEffect(operation, CellStillPending) with
            {
                Result = BlockFact($"nothing was typed: «{pending}» is still pending in {start.Address}, where this table would "
                    + $"begin and which it would write over. A table that begins with «{pending}» takes its place", start),
            };

        int count = block.Rows.Length * block.Columns;
        GridCell[]? cellsBefore = await CellRangeAsync(before.Window, start, block, cancellationToken).ConfigureAwait(false);
        if (cellsBefore is null)
            return ExternalJson.FailureBeforeEffect(operation, CellsNotReadBack) with
            {
                Result = BlockFact($"nothing was typed: the {count} cells this table takes from {start.Address} could not be read, "
                    + "so what it writes could not be proved", start),
            };
        GridCell[] taken = [.. cellsBefore.Where((cell, at) => cell.Value.Length > 0 && !(oursPending && at == 0))];
        if (taken.Length > 0 && !replace)
            return ExternalJson.FailureBeforeEffect(operation, CellsNotEmpty) with
            {
                Result = ExternalJson.Create(writer =>
                {
                    writer.WriteStartObject();
                    writer.WriteNumber("version", 1);
                    WriteCells(writer, "holding", taken);
                    writer.WriteString("next", $"nothing was typed: this table from {start.Address} would write over what these "
                        + "cells hold. replace true writes over them; a table placed elsewhere begins in an empty cell");
                    writer.WriteEndObject();
                }),
            };

        var effectBoundary = new ExternalEffectBoundary();
        effectBoundary.Cross(cancellationToken);
        bool userActed = false, sentAny = false, outOfTime = false;
        bool KeepGoing()
        {
            userActed |= bursts.Current is { UserActed: true };
            outOfTime |= Ticks() >= deadline;
            return !cancellationToken.IsCancellationRequested && !userActed && !outOfTime
                && (window != 0 ? _keyboard.Holds(window) : _keyboard.Foreground().ProcessId == before.ProcessId);
        }

        ActiveCell? strayed = null;
        bool complete = true;
        if (oursPending)
        {
            uint escaped = _keyboard.PressChord(VirtualKeys["escape"], KeepGoing);
            complete = escaped == (uint)VirtualKeys["escape"].Length * 2;
            sentAny = true;
        }

        for (int row = 0; complete && strayed is null && row < block.Rows.Length; row++)
        {
            string[] cells = block.Rows[row];
            for (int column = 0; complete && strayed is null && column < cells.Length; column++)
            {
                if (cells[column].Length > 0)
                {
                    complete = _keyboard.TypeText(cells[column], KeepGoing, _typingPace) == (uint)cells[column].Length * 2;
                    sentAny = true;
                    if (!complete)
                        break;
                }

                bool rowEnds = column == cells.Length - 1;
                ushort[] end = VirtualKeys[rowEnds ? "enter" : "tab"];
                complete = _keyboard.PressChord(end, KeepGoing) == (uint)end.Length * 2;
                sentAny = true;
                if (!complete)
                    break;
                (int Row, int Column) expected = rowEnds ? (start.Row + row + 1, start.Column) : (start.Row + row, start.Column + column + 1);
                strayed = await StrayedFromAsync(before.Window, expected, cancellationToken).ConfigureAwait(false);
            }
        }

        _pendingCells.TryRemove(before.Window, out _);
        _pendingRefused.TryRemove(before.Window, out _);
        _firstCellTextTold[before.Window] = Ticks();
        try
        {
            await _keyboard.SettleAsync(cancellationToken).ConfigureAwait(false);
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            return effectBoundary.Failure(operation, "desktop_interaction_adapter_failed", sentAny);
        }

        // Read while the window still holds the front, as the worker reads the system's focus.
        GridCell[]? cellsAfter = await CellRangeAsync(before.Window, start, block, cancellationToken).ConfigureAwait(false);
        bool? restored = bursts.Current is null ? null : bursts.Restore();
        (GridCell Cell, string Asked)[] differing = cellsAfter is null ? [] : [.. Differing(block, cellsAfter)];
        // A sheet may change what it takes (live: «3/4» is a date, «aqui» is corrected to «aquí»): the cell holds it and the
        // receipt says what. A cell that holds nothing did not take it.
        string? failed = !complete
            ? (userActed ? "input_user_interrupted" : outOfTime ? "input_text_time_exhausted" : "input_window_changed")
            : strayed is not null ? CellLeftTheTable
            : cellsAfter is null || differing.Any(static one => one.Cell.Value.Length == 0) ? CellsNotReadBack
            : null;
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteBoolean("delivered", failed is null);
            writer.WriteString("action", "cells");
            writer.WriteString("method", "keyboard");
            WriteSentTo(writer, before, sentToProcess);
            writer.WriteBoolean("readBack", failed is null && differing.Length == 0);
            if (cellsAfter is not null)
            {
                writer.WriteStartObject("table");
                writer.WriteString("from", cellsAfter[0].Address);
                writer.WriteString("to", cellsAfter[^1].Address);
                writer.WriteNumber("rows", block.Rows.Length);
                writer.WriteNumber("columns", block.Columns);
                writer.WriteEndObject();
                WriteCells(writer, "cells", cellsAfter);
            }

            if (differing.Length > 0)
            {
                writer.WriteStartArray("differs");
                foreach ((GridCell cell, string asked) in differing.Take(ToldCells))
                {
                    writer.WriteStartObject();
                    writer.WriteString("address", cell.Address);
                    writer.WriteString("typed", asked);
                    writer.WriteString("holds", cell.Value);
                    writer.WriteEndObject();
                }

                writer.WriteEndArray();
            }

            if (failed is null && differing.Length > 0)
                writer.WriteString("next", "the sheet changed what these cells took: differs says what each one was typed and "
                    + "holds now");
            if (strayed is not null)
            {
                writer.WriteString("next", $"the keys stopped: after the last one the active cell was {strayed.Address}, not the "
                    + "next one of this table, so the rest was not typed; cells says what each one holds");
            }

            if (restored is bool back)
                writer.WriteBoolean("restored", back);
            writer.WriteEndObject();
        });
        return failed is null
            ? ExternalJson.Success(operation, result, sentAny)
            : effectBoundary.Failure(operation, failed, sentAny) with { Result = result };
    }

    // The cell the last key should have reached, polled as the grid takes a moment after a key; the one it reached instead,
    // or null when it is there. A grid that no longer answers (the focus left it) is a stray too: an empty address.
    private async ValueTask<ActiveCell?> StrayedFromAsync(nint window, (int Row, int Column) expected, CancellationToken cancellationToken)
    {
        ActiveCell? seen = null;
        for (int poll = 0; poll < BlockCellPolls; poll++)
        {
            if (poll > 0)
                await Task.Delay(BlockCellPollMs, cancellationToken).ConfigureAwait(false);
            seen = (await ActiveCellAsync(window, null, cancellationToken).ConfigureAwait(false)).Cell;
            if (seen is { } cell && cell.Row == expected.Row && cell.Column == expected.Column)
                return null;
        }

        return seen ?? new ActiveCell("no cell of a grid", -1, -1, false, string.Empty, string.Empty);
    }

    private async ValueTask<GridCell[]?> CellRangeAsync(nint window, ActiveCell start, CellBlock block, CancellationToken cancellationToken)
    {
        if (_fields is null)
            return null;
        int rows = block.Rows.Length, columns = block.Columns;
        try
        {
            using JsonDocument? answer = await _fields.CellRangeAsync(window, start.Row, start.Column, rows, columns, cancellationToken).ConfigureAwait(false);
            return answer is null ? null : CellBlock.ReadRange(answer.RootElement, rows * columns);
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            return null;
        }
    }

    // The cells asked to hold a text that show another one, in reading order; a cell the table leaves empty is not asked.
    private static IEnumerable<(GridCell Cell, string Asked)> Differing(CellBlock block, GridCell[] cells)
    {
        int columns = block.Columns;
        for (int row = 0; row < block.Rows.Length; row++)
        {
            for (int column = 0; column < block.Rows[row].Length; column++)
            {
                string asked = block.Rows[row][column];
                GridCell cell = cells[(row * columns) + column];
                if (asked.Length > 0 && !CellBlock.Shows(asked, cell.Value))
                    yield return (cell, asked);
            }
        }
    }

    private static void WriteCells(Utf8JsonWriter writer, string name, GridCell[] cells)
    {
        writer.WriteStartArray(name);
        foreach (GridCell cell in cells.Take(ToldCells))
        {
            writer.WriteStartObject();
            writer.WriteString("address", cell.Address);
            writer.WriteString("value", cell.Value);
            writer.WriteEndObject();
        }

        writer.WriteEndArray();
    }

    private static JsonElement BlockFact(string next, ActiveCell? cell = null) => ExternalJson.Create(writer =>
    {
        writer.WriteStartObject();
        writer.WriteNumber("version", 1);
        if (cell is not null)
            ActiveCell.WriteCell(writer, "cell", cell.Address, cell.Value);
        writer.WriteString("next", next);
        writer.WriteEndObject();
    });
}
