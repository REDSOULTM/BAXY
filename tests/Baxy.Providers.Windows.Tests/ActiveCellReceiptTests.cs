using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Encargo 75 (R01): six values typed into a spreadsheet with no key between them all went into its first cell, each call
/// completed with nothing of that cell, and the reply told a table in two columns. The receipts say which cell the keys
/// went to and what it holds, as UI Automation reads it; the worker's functions run on described elements.
/// </summary>
[TestFixture]
public sealed class ActiveCellReceiptTests
{
    private sealed class NoProcessRunner : IExternalProcessRunner
    {
        public ValueTask<ExternalProcessResult> RunAsync(
            string executable, IReadOnlyList<string> arguments, TimeSpan timeout,
            CancellationToken cancellationToken) =>
            throw new AssertionException("keys and text start no process");
    }

    private static JsonElement Json(string text) => JsonDocument.Parse(text).RootElement;

    private static string Cell(string address, int row, int column, bool editing, string value, string? at = null) =>
        JsonSerializer.Serialize(new Dictionary<string, object?>
        {
            ["ok"] = true,
            ["address"] = address,
            ["row"] = row,
            ["column"] = column,
            ["editing"] = editing,
            ["value"] = value,
            ["right"] = "B1",
            ["at"] = at is null ? null : new { value = at },
        });

    private static WindowsDesktopInteractionAdapter Adapter(FakeViewedFields fields) => new(
        new NoProcessRunner(), "folder.ps1", "file.ps1", "select.ps1", "keys.ps1", new FakeDesktopKeyboard(), fields, new FakeFieldMessages());

    private static Task<ExternalCapabilityReceipt> Type(FakeViewedFields fields, string text) => Adapter(fields).InvokeAsync(
        "input.text.type", Json(JsonSerializer.Serialize(new { text })), CancellationToken.None).AsTask();

    // Encargo 115: the cells of a range as the worker answers them.
    private static string Range(params (string Address, string Value)[] cells) => JsonSerializer.Serialize(new Dictionary<string, object?>
    {
        ["ok"] = true,
        ["range"] = cells.Select(static cell => new { a = cell.Address, v = cell.Value }).ToArray(),
    });

    private static readonly (string, string)[] EmptyTable = [("A1", ""), ("B1", ""), ("A2", ""), ("B2", "")];

    private static Task<ExternalCapabilityReceipt> TypeBlock(FakeViewedFields fields, FakeDesktopKeyboard keyboard, string text, bool replace = false) =>
        new WindowsDesktopInteractionAdapter(
            new NoProcessRunner(), "folder.ps1", "file.ps1", "select.ps1", "keys.ps1", keyboard, fields, new FakeFieldMessages())
            .InvokeAsync("input.text.type", Json(JsonSerializer.Serialize(new { text, replace })), CancellationToken.None).AsTask();

    [Test]
    public async Task ATableGivenWholeGoesByItsKeysEndsItsLastCellAndIsReadBack()
    {
        var fields = new FakeViewedFields("{}")
        {
            CellAnswers = new Queue<string>([Cell("A1", 1, 1, false, ""), Cell("B1", 1, 2, false, ""), Cell("A2", 2, 1, false, ""),
                Cell("B2", 2, 2, false, ""), Cell("A3", 3, 1, false, "")]),
            RangeAnswers = new Queue<string>([Range(EmptyTable), Range(("A1", "pera"), ("B1", "12.5"), ("A2", "uva"), ("B2", "30"))]),
        };
        var keyboard = new FakeDesktopKeyboard();

        ExternalCapabilityReceipt receipt = await TypeBlock(fields, keyboard, "pera\t12.50\nuva\t30");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.Null);
            Assert.That(keyboard.Texts, Is.EqualTo(new[] { "pera", "12.50", "uva", "30" }));
            Assert.That(keyboard.Chords.Select(static chord => chord[0]), Is.EqualTo(new ushort[] { 0x09, 0x0D, 0x09, 0x0D }));
            JsonElement result = receipt.Result!.Value;
            Assert.That(result.GetProperty("readBack").GetBoolean(), Is.True);
            Assert.That(result.GetProperty("table").GetProperty("from").GetString(), Is.EqualTo("A1"));
            Assert.That(result.GetProperty("table").GetProperty("to").GetString(), Is.EqualTo("B2"));
            Assert.That(result.GetProperty("cells")[1].GetProperty("value").GetString(), Is.EqualTo("12.5"));
        });
    }

    // Live, Excel 16: SetFocus on C1 left the keys in A1. A table goes from the active cell or is not typed.
    [TestCase("4.2.7", true)]
    [TestCase("4.2.9", false)]
    public async Task ATableAimedAtACellOfTheViewGoesOnlyIfItIsTheActiveOne(string activeId, bool goes)
    {
        string Active(string address, int row, int column) =>
            JsonSerializer.Serialize(new { ok = true, address, id = activeId, row, column, editing = false, value = "" });
        var fields = new FakeViewedFields("{}")
        {
            CellAnswers = new Queue<string>([Active("B2", 2, 2), Active("C2", 2, 3), Active("B3", 3, 2)]),
            RangeAnswers = new Queue<string>([Range(("B2", ""), ("C2", "")), Range(("B2", "a"), ("C2", "b"))]),
        };
        var keyboard = new FakeDesktopKeyboard();
        keyboard.Holding.Add(fields.ViewWindow);

        ExternalCapabilityReceipt receipt = await new WindowsDesktopInteractionAdapter(
                new NoProcessRunner(), "folder.ps1", "file.ps1", "select.ps1", "keys.ps1", keyboard, fields, new FakeFieldMessages())
            .InvokeAsync("input.text.type", Json(JsonSerializer.Serialize(new { text = "a\tb", window = (long)fields.ViewWindow, index = 7 })), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, goes ? Is.Null : Is.EqualTo(WindowsDesktopInteractionAdapter.CellNotActive));
            if (!goes)
                Assert.That(receipt.Result!.Value.GetProperty("next").GetString(), Does.Contain("With no index it goes from B2"));
            Assert.That(keyboard.Texts, goes ? Is.EqualTo(new[] { "a", "b" }) : Is.Empty);
            Assert.That(fields.Focuses, Is.Empty);
        });
    }

    [Test]
    public async Task ATableWhereNoCellHoldsTheFocusIsRefusedAndNothingIsTyped()
    {
        var keyboard = new FakeDesktopKeyboard();

        ExternalCapabilityReceipt receipt = await TypeBlock(new FakeViewedFields("{}"), keyboard, "hola\nadios");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("desktop_interaction_argument_invalid"));
            Assert.That(keyboard.Texts, Is.Empty);
            Assert.That(keyboard.Chords, Is.Empty);
        });
    }

    [Test]
    public async Task ATableIsNotTypedOverWhatCellsHoldUnlessReplaceSaysSo()
    {
        FakeViewedFields Fields() => new("{}")
        {
            CellAnswers = new Queue<string>([Cell("A1", 1, 1, false, ""), Cell("B1", 1, 2, false, ""), Cell("A2", 2, 1, false, ""),
                Cell("B2", 2, 2, false, ""), Cell("A3", 3, 1, false, "")]),
            RangeAnswers = new Queue<string>([Range(("A1", ""), ("B1", "de la persona"), ("A2", ""), ("B2", "")),
                Range(("A1", "a"), ("B1", "b"), ("A2", "c"), ("B2", "d"))]),
        };
        var refusedKeys = new FakeDesktopKeyboard();
        var replacedKeys = new FakeDesktopKeyboard();

        ExternalCapabilityReceipt refused = await TypeBlock(Fields(), refusedKeys, "a\tb\nc\td");
        ExternalCapabilityReceipt replaced = await TypeBlock(Fields(), replacedKeys, "a\tb\nc\td", replace: true);

        Assert.Multiple(() =>
        {
            Assert.That(refused.ErrorCode, Is.EqualTo(WindowsDesktopInteractionAdapter.CellsNotEmpty));
            Assert.That(refused.EffectMayHaveOccurred, Is.False);
            Assert.That(refusedKeys.Texts, Is.Empty);
            Assert.That(refused.Result!.Value.GetProperty("holding")[0].GetProperty("address").GetString(), Is.EqualTo("B1"));
            Assert.That(replaced.ErrorCode, Is.Null);
            Assert.That(replacedKeys.Texts, Has.Count.EqualTo(4));
        });
    }

    [Test]
    public async Task AKeyThatReachesAnotherCellStopsTheRestAndSaysWhere()
    {
        var fields = new FakeViewedFields("{}")
        {
            // Enter does not go back under the column the row began at: it stays in the next row's column B.
            CellAnswers = new Queue<string>([Cell("A1", 1, 1, false, ""), Cell("B1", 1, 2, false, ""), Cell("B2", 2, 2, false, "")]),
            RangeAnswers = new Queue<string>([Range(EmptyTable), Range(("A1", "a"), ("B1", "b"), ("A2", ""), ("B2", ""))]),
        };
        var keyboard = new FakeDesktopKeyboard();

        ExternalCapabilityReceipt receipt = await TypeBlock(fields, keyboard, "a\tb\nc\td");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo(WindowsDesktopInteractionAdapter.CellLeftTheTable));
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            Assert.That(keyboard.Texts, Is.EqualTo(new[] { "a", "b" }));
            Assert.That(receipt.Result!.Value.GetProperty("next").GetString(), Does.Contain("B2"));
        });
    }

    [Test]
    public async Task ACellTheSheetChangedIsToldAsWhatItHolds()
    {
        var fields = new FakeViewedFields("{}")
        {
            CellAnswers = new Queue<string>([Cell("A1", 1, 1, false, ""), Cell("B1", 1, 2, false, ""), Cell("A2", 2, 1, false, "")]),
            RangeAnswers = new Queue<string>([Range(("A1", ""), ("B1", "")), Range(("A1", "plazo"), ("B1", "04-mar"))]),
        };

        ExternalCapabilityReceipt receipt = await TypeBlock(fields, new FakeDesktopKeyboard(), "plazo\t3/4");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.Null);
            Assert.That(receipt.Result!.Value.GetProperty("readBack").GetBoolean(), Is.False);
            JsonElement differs = receipt.Result!.Value.GetProperty("differs")[0];
            Assert.That(differs.GetProperty("address").GetString(), Is.EqualTo("B1"));
            Assert.That(differs.GetProperty("typed").GetString(), Is.EqualTo("3/4"));
            Assert.That(differs.GetProperty("holds").GetString(), Is.EqualTo("04-mar"));
        });
    }

    [Test]
    public async Task ACellThatHoldsNothingOfWhatWasTypedIsNotReadBack()
    {
        var fields = new FakeViewedFields("{}")
        {
            CellAnswers = new Queue<string>([Cell("A1", 1, 1, false, ""), Cell("B1", 1, 2, false, ""), Cell("A2", 2, 1, false, "")]),
            RangeAnswers = new Queue<string>([Range(("A1", ""), ("B1", "")), Range(("A1", "pera"), ("B1", ""))]),
        };

        ExternalCapabilityReceipt receipt = await TypeBlock(fields, new FakeDesktopKeyboard(), "pera\t12");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo(WindowsDesktopInteractionAdapter.CellsNotReadBack));
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
        });
    }

    [Test]
    public async Task ACellThePersonIsEditingIsNotTouched()
    {
        var keyboard = new FakeDesktopKeyboard();
        var fields = new FakeViewedFields("{}") { CellAnswers = new Queue<string>([Cell("A1", 1, 1, true, "")]) };

        ExternalCapabilityReceipt receipt = await TypeBlock(fields, keyboard, "a\tb");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo(WindowsDesktopInteractionAdapter.CellBeingEdited));
            Assert.That(keyboard.Texts, Is.Empty);
            Assert.That(keyboard.Chords, Is.Empty);
        });
    }

    [Test]
    public void ATableIsCutAtItsTabsAndLineBreaksAndNoOtherControlCharacter()
    {
        CellBlock block = CellBlock.Parse("a\tb\r\nc\n");

        Assert.Multiple(() =>
        {
            Assert.That(block.Rows, Has.Length.EqualTo(2));
            Assert.That(block.Rows[0], Is.EqualTo(new[] { "a", "b" }));
            Assert.That(block.Rows[1], Is.EqualTo(new[] { "c" }));
            Assert.That(block.Columns, Is.EqualTo(2));
            Assert.That(CellBlock.Holds("una sola celda"), Is.False);
            Assert.That(CellBlock.Holds("a\u0007\tb"), Is.False);
            Assert.That(CellBlock.Shows("12.50", "12.5"), Is.True);
            Assert.That(CellBlock.Shows("3/4", "04-mar"), Is.False);
        });
    }

    // Encargo 115: told once what a table is, measured with the real model: the same call written again types its one value.
    [Test]
    public async Task TheFirstTextForACellSaysWhatATableIsAndTheSameCallAgainTypesIt()
    {
        var keyboard = new FakeDesktopKeyboard();
        var fields = new FakeViewedFields("{}")
        {
            CellAnswers = new Queue<string>([Cell("A1", 1, 1, false, ""), Cell("A1", 1, 1, false, ""), Cell("A1", 1, 1, true, "")]),
        };
        WindowsDesktopInteractionAdapter adapter = new(
            new NoProcessRunner(), "folder.ps1", "file.ps1", "select.ps1", "keys.ps1", keyboard, fields, new FakeFieldMessages());

        ExternalCapabilityReceipt first = await adapter.InvokeAsync("input.text.type", Json("""{"text":"pera"}"""), CancellationToken.None);
        int typedThen = keyboard.Texts.Count;
        ExternalCapabilityReceipt again = await adapter.InvokeAsync("input.text.type", Json("""{"text":"pera"}"""), CancellationToken.None);

        JsonElement told = first.Result!.Value;
        JsonElement result = again.Result!.Value;
        string next = result.GetProperty("next").GetString()!;
        Assert.Multiple(() =>
        {
            Assert.That(first.ErrorCode, Is.EqualTo(WindowsDesktopInteractionAdapter.FirstCellText));
            Assert.That(first.EffectMayHaveOccurred, Is.False);
            Assert.That(typedThen, Is.Zero);
            Assert.That(told.GetProperty("next").GetString(), Does.StartWith("this call typed nothing: the keyboard's focus is on the cell A1")
                .And.Contain("A whole table goes in one call").And.Contain("call it again exactly as before"));
            Assert.That(keyboard.Texts, Is.EqualTo(new[] { "pera" }));
            Assert.That(result.GetProperty("cell").GetProperty("address").GetString(), Is.EqualTo("A1"));
            Assert.That(result.GetProperty("cell").GetProperty("value").GetString(), Is.Empty);
            Assert.That(result.GetProperty("cell").GetProperty("pendingText").GetString(), Is.EqualTo("pera"));
            Assert.That(next, Does.StartWith("«pera» is still pending in A1"));
            Assert.That(next, Does.Contain("key tab goes to B1").And.Contain("key enter goes to the next row"));
        });
    }

    [Test]
    public void TheSkeletonOfATableNamesTheCellsItGoesIn()
    {
        var cell = new ActiveCell("C3", 3, 3, false, "", "D3", "1.2", "C4", "D4");

        string next = cell.FirstTextNext(7);

        Assert.Multiple(() =>
        {
            Assert.That(next, Does.Contain("""input_text_type {"window":7,"text":"<what goes in C3>\t<what goes in D3>\n<what goes in C4>\t<what goes in D4>"}"""));
            Assert.That(ActiveCell.TableNext(7, "why", "one", null), Does.Contain("from the active cell,").And.Contain("<a cell>\\t<the next cell>"));
        });
    }

    [Test]
    public async Task ASecondTextOverTheOnePendingIsRefusedOnceAndWrittenAgainJoinsIt()
    {
        var keyboard = new FakeDesktopKeyboard();
        var fields = new FakeViewedFields("{}")
        {
            CellAnswers = new Queue<string>([Cell("A1", 1, 1, false, ""), Cell("A1", 1, 1, false, ""), Cell("A1", 1, 1, true, "")]),
        };
        WindowsDesktopInteractionAdapter adapter = new(
            new NoProcessRunner(), "folder.ps1", "file.ps1", "select.ps1", "keys.ps1", keyboard, fields, new FakeFieldMessages());

        await adapter.InvokeAsync("input.text.type", Json("""{"text":"pera"}"""), CancellationToken.None);
        await adapter.InvokeAsync("input.text.type", Json("""{"text":"pera"}"""), CancellationToken.None);
        ExternalCapabilityReceipt refused = await adapter.InvokeAsync(
            "input.text.type", Json("""{"text":"uva"}"""), CancellationToken.None);
        JsonElement result = refused.Result!.Value;
        string[] typedThen = [.. keyboard.Texts];
        ExternalCapabilityReceipt joined = await adapter.InvokeAsync(
            "input.text.type", Json("""{"text":"uva"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(refused.Verified, Is.False);
            Assert.That(refused.ErrorCode, Is.EqualTo(WindowsDesktopInteractionAdapter.CellStillPending));
            Assert.That(typedThen, Is.EqualTo(new[] { "pera" }));
            Assert.That(result.GetProperty("cell").GetProperty("pendingText").GetString(), Is.EqualTo("pera"));
            Assert.That(result.GetProperty("next").GetString(), Does.StartWith("this call typed nothing: «pera» is still pending in A1")
                .And.Contain("To join it to that cell, call it again exactly as before"));
            Assert.That(keyboard.Texts, Is.EqualTo(new[] { "pera", "uva" }));
            Assert.That(joined.ErrorCode, Is.Not.EqualTo(WindowsDesktopInteractionAdapter.CellStillPending));
            Assert.That(joined.Result!.Value.GetProperty("cell").GetProperty("pendingText").GetString(), Is.EqualTo("perauva"));
        });
    }

    [Test]
    public async Task ATableIsNotToldAgainOnceItWasWritten()
    {
        var keyboard = new FakeDesktopKeyboard();
        var fields = new FakeViewedFields("{}")
        {
            CellAnswers = new Queue<string>([Cell("A1", 1, 1, false, ""), Cell("A2", 2, 1, false, ""), Cell("A2", 2, 1, false, ""), Cell("A2", 2, 1, true, "")]),
            RangeAnswers = new Queue<string>([Range(("A1", "")), Range(("A1", "pera"))]),
        };
        WindowsDesktopInteractionAdapter adapter = new(
            new NoProcessRunner(), "folder.ps1", "file.ps1", "select.ps1", "keys.ps1", keyboard, fields, new FakeFieldMessages());

        ExternalCapabilityReceipt table = await adapter.InvokeAsync("input.text.type", Json("""{"text":"pera\n"}"""), CancellationToken.None);
        ExternalCapabilityReceipt text = await adapter.InvokeAsync("input.text.type", Json("""{"text":"uva"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(table.ErrorCode, Is.Null);
            Assert.That(text.ErrorCode, Is.Not.EqualTo(WindowsDesktopInteractionAdapter.FirstCellText));
            Assert.That(keyboard.Texts, Is.EqualTo(new[] { "pera", "uva" }));
        });
    }

    [Test]
    public async Task AKeyEndsThePendingTextAndTheNextTextIsTyped()
    {
        var keyboard = new FakeDesktopKeyboard();
        var fields = new FakeViewedFields("{}")
        {
            CellAnswers = new Queue<string>([
                Cell("A1", 1, 1, false, ""), Cell("A1", 1, 1, false, ""), Cell("A1", 1, 1, true, ""),
                Cell("A1", 1, 1, true, ""), Cell("B1", 1, 2, false, "", at: "pera"),
                Cell("B1", 1, 2, false, ""), Cell("B1", 1, 2, true, "")]),
        };
        WindowsDesktopInteractionAdapter adapter = new(
            new NoProcessRunner(), "folder.ps1", "file.ps1", "select.ps1", "keys.ps1", keyboard, fields, new FakeFieldMessages());

        await adapter.InvokeAsync("input.text.type", Json("""{"text":"pera"}"""), CancellationToken.None);
        await adapter.InvokeAsync("input.text.type", Json("""{"text":"pera"}"""), CancellationToken.None);
        await adapter.InvokeAsync("input.key.press", Json("""{"key":"tab"}"""), CancellationToken.None);
        ExternalCapabilityReceipt typed = await adapter.InvokeAsync(
            "input.text.type", Json("""{"text":"120"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(typed.ErrorCode, Is.Not.EqualTo(WindowsDesktopInteractionAdapter.CellStillPending));
            Assert.That(keyboard.Texts, Is.EqualTo(new[] { "pera", "120" }));
        });
    }

    // What the person left being edited in a cell is not this adapter's to refuse.
    [Test]
    public async Task ATextOverACellThePersonIsEditingIsTyped()
    {
        var keyboard = new FakeDesktopKeyboard();
        var fields = new FakeViewedFields("{}")
        {
            CellAnswers = new Queue<string>([Cell("A1", 1, 1, true, ""), Cell("A1", 1, 1, true, "")]),
        };
        WindowsDesktopInteractionAdapter adapter = new(
            new NoProcessRunner(), "folder.ps1", "file.ps1", "select.ps1", "keys.ps1", keyboard, fields, new FakeFieldMessages());

        ExternalCapabilityReceipt typed = await adapter.InvokeAsync(
            "input.text.type", Json("""{"text":"uva"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(typed.ErrorCode, Is.Not.EqualTo(WindowsDesktopInteractionAdapter.CellStillPending));
            Assert.That(keyboard.Texts, Is.EqualTo(new[] { "uva" }));
        });
    }

    [Test]
    public async Task AKeyThatMovesTheCellSaysTheCellItLeftWithItsValueAndTheOneItReached()
    {
        var fields = new FakeViewedFields("{}")
        {
            CellAnswers = new Queue<string>([Cell("A1", 1, 1, true, ""), Cell("B1", 1, 2, false, "", at: "pera")]),
        };

        ExternalCapabilityReceipt receipt = await Adapter(fields).InvokeAsync(
            "input.key.press", Json("""{"key":"tab"}"""), CancellationToken.None);

        JsonElement result = receipt.Result!.Value;
        Assert.Multiple(() =>
        {
            Assert.That(fields.CellsAsked, Is.EqualTo(new[] { (1, 1) }));
            Assert.That(result.GetProperty("cellLeft").GetProperty("address").GetString(), Is.EqualTo("A1"));
            Assert.That(result.GetProperty("cellLeft").GetProperty("value").GetString(), Is.EqualTo("pera"));
            Assert.That(result.GetProperty("cell").GetProperty("address").GetString(), Is.EqualTo("B1"));
            Assert.That(result.GetProperty("readBack").GetBoolean(), Is.True);
        });
    }

    [Test]
    public async Task AWindowWithNoGridSaysNoCell()
    {
        var fields = new FakeViewedFields("{}")
        {
            CellAnswers = new Queue<string>(["""{"ok":false,"error":"no_active_cell"}"""]),
        };

        JsonElement result = (await Type(fields, "pera")).Result!.Value;

        Assert.Multiple(() =>
        {
            Assert.That(result.TryGetProperty("cell", out _), Is.False);
            Assert.That(result.TryGetProperty("next", out JsonElement next) && next.GetString()!.Contains(
                "key tab goes to", StringComparison.Ordinal), Is.False);
        });
    }

    // Measured: looking for a grid from a word processor's document cost a second per text.
    [Test]
    public void AFocusedDocumentIsNotSearchedForAGrid()
    {
        string script = File.ReadAllText(Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1"), System.Text.Encoding.UTF8);
        int at = script.IndexOf("function Do-ActiveCell(", StringComparison.Ordinal);
        string body = script[at..script.IndexOf("\nfunction ", at + 1, StringComparison.Ordinal)];

        Assert.That(body, Does.Contain("if($null -eq $cell -and $kind -ne 'Document'){"));
    }

    [Test]
    public void TheAddressIsTheOneTheGridGivesItsCellOrItsRowAndColumn()
    {
        JsonElement answer = WorkerFunctions.Run(["Get-CellAddress"], """
            function Node($name,$id){ [pscustomobject]@{ Current=[pscustomobject]@{ Name=$name; AutomationId=$id } } }
            @((Get-CellAddress (Node 'A1' 'A1') 1 1),(Get-CellAddress (Node 'contenido' '') 0 0),(Get-CellAddress (Node '' '') 2 3)) | ConvertTo-Json -Compress
            """);

        Assert.That(answer.EnumerateArray().Select(static item => item.GetString()),
            Is.EqualTo(new[] { "A1", "row 1, column 1", "row 3, column 4" }));
    }

    [Test]
    public void AnEditorStartsInsideTheCellEvenWhenItGrewOverTheNextOnes()
    {
        JsonElement answer = WorkerFunctions.Run(["Test-StartsInside"], """
            function Rect($x,$y,$w,$h){ [pscustomobject]@{ Current=[pscustomobject]@{ BoundingRectangle=[pscustomobject]@{ X=$x; Y=$y; Width=$w; Height=$h } } } }
            $cell=Rect 34 294 104 24
            @((Test-StartsInside (Rect 34 294 103 23) $cell),(Test-StartsInside (Rect 37 294 400 24) $cell),(Test-StartsInside (Rect 274 222 1646 48) $cell),(Test-StartsInside (Rect 34 294 0 0) $cell)) | ConvertTo-Json -Compress
            """);

        Assert.That(answer.EnumerateArray().Select(static item => item.GetBoolean()), Is.EqualTo(new[] { true, true, false, false }));
    }
}
