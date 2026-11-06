using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Uso real 02-11 (encargo 2, A): values typed one after another into a spreadsheet's cells, by index, with no Enter nor
/// Tab, were told completed and verified while the sheet held something else (all in one cell). An item of a grid, list
/// or tree is edited in an editor of its own laid inside it (a cell's «Editar celda», measured on the desktop): while
/// that editor holds the keyboard's focus the edit is not confirmed, the item's value is not yet the text, and a value
/// set and read back equal then is lost when the edit is confirmed. Such an edit is said (editPending), never verified.
/// And a field with text that is neither selected nor focused (input_field_not_reachable) says what it held. Every
/// effect goes to fakes; the worker's own function runs on described elements.
/// </summary>
[TestFixture]
public sealed class EditNotConfirmedTests
{
    private static JsonElement Json(string value) => JsonDocument.Parse(value).RootElement.Clone();

    private static WindowsDesktopInteractionAdapter Adapter(FakeDesktopKeyboard keyboard, FakeViewedFields fields) =>
        new(new NoProcessRunner(), "folder.ps1", "file.ps1", "select.ps1", "keys.ps1", keyboard, fields, new FakeFieldMessages());

    private static string Cell(string more) =>
        """{"ok":true,"error":"","kind":"DataItem","className":"GridCell","nativeHwnd":0,"password":false,"readOnly":false,"enabled":true,"method":"","delivered":false"""
        + more + "}";

    // The worker found the item's own editor open (the text of an earlier act not confirmed): nothing is written, by no
    // path, and the receipt says the edit is pending.
    [Test]
    public async Task AnItemWhoseEditIsOpenTakesNothing()
    {
        var keyboard = new FakeDesktopKeyboard();
        var fields = new FakeViewedFields(Cell(""","focused":true,"valueLength":0,"editPending":true"""));

        ExternalCapabilityReceipt receipt = await Adapter(keyboard, fields).InvokeAsync(
            "input.text.type", Json("""{"text":"gamma","window":4660,"index":5}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_edit_not_confirmed"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(receipt.Result?.GetProperty("editPending").GetBoolean(), Is.True);
            Assert.That(keyboard.Texts, Is.Empty);
            Assert.That(keyboard.Fronted, Is.Empty);
        });
    }

    // A text the keyboard typed into the item it names (its value and messages do not reach it) is read again in that item:
    // an editor of its own still open means the text is not its value yet. Contracase: no edit open, verified as before.
    [TestCase(true)]
    [TestCase(false)]
    public async Task AKeyboardTextLeftInTheItemsOpenEditIsNotVerified(bool pending)
    {
        var keyboard = new FakeDesktopKeyboard();
        var fields = new FakeViewedFields(Cell(""","focused":true,"valueLength":4"""))
        {
            ReadAnswer = Cell($$""","focused":true,"valueLength":0,"editPending":{{(pending ? "true" : "false")}}"""),
        };

        ExternalCapabilityReceipt receipt = await Adapter(keyboard, fields).InvokeAsync(
            "input.text.type", Json("""{"text":"beta","window":4660,"index":5}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(keyboard.Texts.Single(), Is.EqualTo("beta"));
            Assert.That(receipt.Verified, Is.EqualTo(!pending));
            if (pending)
            {
                Assert.That(receipt.ErrorCode, Is.EqualTo("input_edit_not_confirmed"));
                Assert.That(receipt.EffectMayHaveOccurred, Is.True);
                Assert.That(receipt.Result?.GetProperty("editPending").GetBoolean(), Is.True);
                Assert.That(receipt.Result?.GetProperty("method").GetString(), Is.EqualTo("keyboard"));
            }

            Assert.That(fields.Requests.Select(request => request.Text), Is.EqualTo(new[] { "beta", null }),
                "the item is read again after the text, nothing written then");
        });
    }

    // A field that holds text, neither selected nor focused, is not reached (nothing sent): the receipt says it held
    // text and it was not selected. Contracase: an empty one says it held none.
    [TestCase(4, true)]
    [TestCase(0, false)]
    public async Task AFieldNotReachedSaysWhatItHeld(int length, bool hasText)
    {
        var keyboard = new FakeDesktopKeyboard();
        var fields = new FakeViewedFields(Cell($$""","focused":false,"valueLength":{{length}},"selected":false"""));

        ExternalCapabilityReceipt receipt = await Adapter(keyboard, fields).InvokeAsync(
            "input.text.type", Json("""{"text":"epsilon","window":4660,"index":7}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_field_not_reachable"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(receipt.Result?.GetProperty("fieldHasText").GetBoolean(), Is.EqualTo(hasText));
            Assert.That(receipt.Result?.GetProperty("textSelected").GetBoolean(), Is.False);
            Assert.That(receipt.Result?.GetProperty("fieldFocused").GetBoolean(), Is.False);
            Assert.That(keyboard.Texts, Is.Empty);
        });
    }

    // Encargo 10 (punto 5): a verified text typed by index is confirmed with no second trip to the worker unless the
    // field is a grid, list or tree item (the only kinds an edit can be pending in, Test-EditPending). The kind comes
    // from the view that handed the index out, so a plain field (Edit) is not read again. The measure is the worker
    // reads made after the write: one for an item, none for a plain field.
    [TestCase("DataItem", 1)]
    [TestCase("Edit", 0)]
    public async Task APlainFieldIsConfirmedWithoutASecondWorkerTrip(string kind, int confirmReads)
    {
        var keyboard = new FakeDesktopKeyboard();
        var fields = new FakeViewedFields(Cell(""","focused":true,"valueLength":4"""))
        {
            ReadAnswer = Cell(""","focused":true,"valueLength":0,"editPending":false"""),
            Seen = new ViewedIndex(4660, "4.2.5", 5, null, false, null, null, kind),
        };

        var adapter = Adapter(keyboard, fields);
        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.text.type", Json("""{"text":"beta","window":4660,"index":5}"""), CancellationToken.None);
        // Encargo 115: the first text for a cell by its index says what a table is, once; the same call again writes it.
        if (kind == "DataItem")
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo(WindowsDesktopInteractionAdapter.FirstCellText));
            Assert.That(keyboard.Texts, Is.Empty);
            receipt = await adapter.InvokeAsync(
                "input.text.type", Json("""{"text":"beta","window":4660,"index":5}"""), CancellationToken.None);
        }

        Assert.Multiple(() =>
        {
            Assert.That(keyboard.Texts.Single(), Is.EqualTo("beta"));
            Assert.That(receipt.Verified, Is.True);
            Assert.That(fields.Requests.Count(request => request.Text is null), Is.EqualTo(confirmReads),
                "only a grid/list/tree item is read again to see its edit is not pending");
        });
    }

    // The worker's test: an item (a grid's cell, a list's or a tree's item) with a text editor inside it that holds the
    // keyboard's focus is in an edit not confirmed. A text field itself is never «pending» (it is the editor), nor an
    // item with no such editor, nor one whose search fails.
    [Test]
    public void TheWorkerTellsAnItemWithItsOwnEditorFocused()
    {
        JsonElement answer = WorkerFunctions.Run(["Test-EditPending"], """
            function Item($found){
              $item=[pscustomobject]@{ Found=$found }
              $item | Add-Member -MemberType ScriptMethod -Name FindFirst -Value { param($scope,$condition) if($this.Found -eq 'throw'){ throw 'gone' }; return $this.Found }
              return $item
            }
            $editor=[pscustomobject]@{ Name='editor' }
            $values=@(
              (Test-EditPending (Item $editor) 'DataItem'),
              (Test-EditPending (Item $editor) 'ListItem'),
              (Test-EditPending (Item $editor) 'TreeItem'),
              (Test-EditPending (Item $null) 'DataItem'),
              (Test-EditPending (Item 'throw') 'DataItem'),
              (Test-EditPending (Item $editor) 'Edit'),
              (Test-EditPending (Item $editor) 'Document'),
              (Test-EditPending (Item $editor) 'Group'))
            [Console]::Out.Write((ConvertTo-Json -Compress $values))
            """);

        Assert.That(answer.EnumerateArray().Select(item => item.GetBoolean()),
            Is.EqualTo(new[] { true, true, true, false, false, false, false, false }));
    }

    private sealed class NoProcessRunner : IExternalProcessRunner
    {
        public ValueTask<ExternalProcessResult> RunAsync(
            string executable, IReadOnlyList<string> arguments, TimeSpan timeout,
            CancellationToken cancellationToken) =>
            throw new AssertionException("keys and text start no process");
    }
}
