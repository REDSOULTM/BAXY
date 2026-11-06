using System.Diagnostics;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Renew al máximo (7.1): a completed act (a click, a text, a key) reads the same window's tree again by the look's own
/// path (the worker's «view», its caps and numbering) and its receipt carries «after»: the controls that appeared, those
/// no longer listed, those that changed or moved, and the title when it changed, with the new indices. That read becomes
/// the last view, so an index of it can be pressed and an index of the view before that is no longer there is refused.
/// A read that fails or runs out of time leaves the receipt as it was, without the section. Every effect goes to fakes:
/// the windows are off-screen ones of this test that take no activation.
/// </summary>
[TestFixture]
public sealed class ComputerUseAfterViewTests
{
    private static JsonElement Json(string value) => JsonDocument.Parse(value).RootElement.Clone();

    private const string Pressed =
        "{\"version\":2,\"ok\":true,\"effectObserved\":true,\"error\":\"\",\"name\":\"Abrir\",\"kind\":\"Button\"," +
        "\"controlIdentity\":\"1.1\",\"absentOrDisabled\":false,\"selected\":true,\"toggled\":false," +
        "\"surfaceChanged\":false,\"cascadeStage\":\"uia\",\"method\":\"invoke\"}";

    // The window after the press: «Guardar» appeared, «Buscar» moved from [1] to [2], «Cerrar» and «Salir» are gone.
    private const string ViewAfter =
        "{\"ok\":true,\"error\":\"\",\"window\":\"Documento\",\"controls\":[" +
        "{\"kind\":\"Button\",\"name\":\"Abrir\",\"id\":\"1.1\",\"state\":\"\",\"value\":null}," +
        "{\"kind\":\"Button\",\"name\":\"Guardar\",\"id\":\"1.5\",\"state\":\"\",\"value\":null}," +
        "{\"kind\":\"Edit\",\"name\":\"Buscar\",\"id\":\"1.2\",\"state\":\"\",\"value\":\"\"}]," +
        "\"controlCount\":3,\"disabled\":[{\"kind\":\"Button\",\"name\":\"Salir\"}],\"partial\":false}";

    private static ViewControlSpec[] Before =>
    [
        new(0, "1.1", "Button", "Abrir", ""),
        new(1, "1.2", "Edit", "Buscar", ""),
        new(2, "1.3", "Button", "Cerrar", ""),
        new(3, "1.4", "Button", "Salir", ""),
    ];

    // Ajuste c3 (humos del 31-10 en el NB, modelo sB): a click on «Escritorio» in a «Guardar como» filled its file list;
    // the view after renumbered the window and the name field went from [27] to [30], told only in an «after» cut at its
    // cap. The model wrote by [27], the field it saw, and the App took [27] of the new numbering (a folder of the
    // person's desktop). An index means the control the model saw at it: the one its last look listed there, unless an
    // «after» it was given since listed that index anew. That same control (its runtime id, else its automation id, kind
    // and name, once) is the one acted on wherever it is now, and the receipt says where; a control gone is never
    // replaced by whatever occupies its index now.
    private static string Control(string kind, string name, string id, string state = "") =>
        "{\"kind\":\"" + kind + "\",\"name\":\"" + name + "\",\"id\":\"" + id + "\",\"state\":\"" + state + "\",\"value\":null}";

    private static ViewControlSpec[] DialogSeen =>
    [
        new(0, "1.1", "TreeItem", "Escritorio", ""),
        .. Enumerable.Range(1, 20).Select(i => new ViewControlSpec(i, "3." + i, "Button", "b" + i, "")),
        new(21, "42.77", "Edit", "Nombre de archivo:", ""),
        new(22, "42.78", "Button", "Guardar", ""),
    ];

    private static string DialogAfter(bool fieldStays) =>
        "{\"ok\":true,\"error\":\"\",\"window\":\"Guardar como\",\"controls\":[" +
        string.Join(',', [
            Control("TreeItem", "Escritorio", "1.1", "selected"),
            .. Enumerable.Range(1, 20).Select(i => Control("Button", "b" + i, "3." + i, "readonly")),
            Control("ListItem", "carpeta de la persona", "2.1"),
            .. fieldStays ? [Control("Edit", "Nombre de archivo:", "42.77")] : Array.Empty<string>(),
            Control("Button", "Guardar", "42.78")]) +
        "],\"controlCount\":" + (fieldStays ? 24 : 23) + ",\"partial\":false}";

    [Test]
    public void AnIndexMeansTheControlTheModelSawThereNotWhatTheRenumberedViewHasThere()
    {
        WithWindow(window =>
        {
            string pressedField = Pressed.Replace("\"Abrir\"", "\"Nombre de archivo:\"", StringComparison.Ordinal)
                .Replace("\"Button\"", "\"Edit\"", StringComparison.Ordinal)
                .Replace("\"1.1\"", "\"42.77\"", StringComparison.Ordinal);
            var worker = new OrderedWorker(Pressed, DialogAfter(fieldStays: true), pressedField);
            WindowsVisibleControlAdapter adapter = Adapter(worker);
            RememberView(adapter, window, DialogSeen);

            ExternalCapabilityReceipt receipt = Click(adapter, window, "Escritorio", "1.1");

            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(Strings(receipt.Result!.Value.GetProperty("after"), "appeared"), Is.Empty,
                "the cap left the new item and the moved field untold");
            Assert.Multiple(() =>
            {
                Assert.That(adapter.TryViewedField(21, out nint viewed, out string id), Is.True);
                Assert.That(id, Is.EqualTo("42.77"), "[21] is the name field the look listed, not the folder now at [21]");
                Assert.That(viewed, Is.EqualTo(window));
                Assert.That(adapter.ViewedAt(21), Is.EqualTo(new ViewedIndex(window, "42.77", 21, 22, false, null, null, "Edit")));
                Assert.That(adapter.TryViewedField(0, out _, out string told) && told == "1.1", Is.True,
                    "an index the after listed is the control it listed");
            });

            // A click by that index presses the field where it is now and says its index now.
            ExternalCapabilityReceipt field = adapter.InvokeAsync(
                    "input.visible.click",
                    Json("{\"label\":\"Nombre de archivo:\",\"index\":21,\"window\":" + (long)window + "}"),
                    CancellationToken.None)
                .AsTask().GetAwaiter().GetResult();
            Assert.Multiple(() =>
            {
                Assert.That(field.Verified, Is.True, field.ErrorCode);
                Assert.That(worker.Commands[2], Does.Contain("42.77"), "the field the look listed was pressed");
                Assert.That(field.Result!.Value.GetProperty("indexNow").GetInt32(), Is.EqualTo(22));
                Assert.That(field.Result!.Value.GetProperty("indexAsked").GetInt32(), Is.EqualTo(21));
            });
        });
    }

    // The same control: its runtime id; a control whose runtime id changed, by its automation id, kind and name when one
    // control alone has them; anything else is gone, and only one control alone with its kind and name is its equivalent.
    [Test]
    public void TheSameControlIsItsRuntimeIdElseItsAutomationIdKindAndNameOnce()
    {
        static WindowsVisibleControlAdapter.ViewControl C(int index, string id, string aid, string kind, string name) =>
            new() { Index = index, Id = id, Aid = aid, Kind = kind, Name = name };
        var told = new Dictionary<int, WindowsVisibleControlAdapter.ViewControl> { [5] = C(5, "1.9", "nameBox", "Edit", "Nombre") };

        Assert.Multiple(() =>
        {
            Assert.That(WindowsVisibleControlAdapter.ResolveSeen(5, 7, [C(0, "7.7", "nameBox", "Edit", "Nombre"), C(5, "1.2", "", "ListItem", "x")], told),
                Is.EqualTo(new ViewedIndex(7, "7.7", 5, 0, false, null, null, "Edit")), "its id changed: automation id, kind and name");
            Assert.That(WindowsVisibleControlAdapter.ResolveSeen(5, 7, [C(0, "7.7", "otro", "Edit", "Nombre"), C(5, "1.2", "", "ListItem", "x")], told),
                Is.EqualTo(new ViewedIndex(0, string.Empty, 5, null, true, 0, "Edit «Nombre»")), "gone; one equivalent");
            Assert.That(WindowsVisibleControlAdapter.ResolveSeen(5, 7,
                    [C(0, "7.7", "a", "Edit", "Nombre"), C(1, "7.8", "b", "Edit", "Nombre"), C(5, "1.2", "", "ListItem", "x")], told),
                Is.EqualTo(new ViewedIndex(0, string.Empty, 5, null, true, null, "Edit «Nombre»")), "gone; no single equivalent");
            Assert.That(WindowsVisibleControlAdapter.ResolveSeen(5, 7, [C(5, "1.9", "nameBox", "Edit", "Nombre")], told),
                Is.EqualTo(new ViewedIndex(7, "1.9", 5, null, false, null, null, "Edit")), "where it was");
            Assert.That(WindowsVisibleControlAdapter.ResolveSeen(3, 7, [C(3, "1.3", "", "Button", "B")], null),
                Is.EqualTo(new ViewedIndex(7, "1.3", 3, null, false, null, null, "Button")), "a view the model saw whole");
        });
    }

    [Test]
    public void AnIndexWhoseControlIsGoneActsOnNothingAndSaysSo()
    {
        WithWindow(window =>
        {
            WindowsVisibleControlAdapter adapter = Adapter(new OrderedWorker(Pressed, DialogAfter(fieldStays: false)));
            RememberView(adapter, window, DialogSeen);

            ExternalCapabilityReceipt receipt = Click(adapter, window, "Escritorio", "1.1");

            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.Multiple(() =>
            {
                Assert.That(adapter.TryViewedField(21, out _, out _), Is.False, "the folder now at [21] is never taken");
                Assert.That(adapter.ViewedAt(21), Is.EqualTo(new ViewedIndex(0, string.Empty, 21, null, true, null,
                    "Edit «Nombre de archivo:»")));
            });
        });
    }

    [Test]
    public void ACompletedClickCarriesTheViewAfterItWithTheNewIndices()
    {
        WithWindow(window =>
        {
            var worker = new OrderedWorker(Pressed, ViewAfter);
            WindowsVisibleControlAdapter adapter = Adapter(worker);
            RememberView(adapter, window, Before);
            long viewsBefore = ViewsRead(adapter);

            ExternalCapabilityReceipt receipt = Click(adapter, window, "Abrir", "1.1");

            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            JsonElement after = receipt.Result!.Value.GetProperty("after");
            Assert.Multiple(() =>
            {
                Assert.That(Strings(after, "appeared"), Is.EqualTo(new[] { "[1] Button «Guardar»" }));
                Assert.That(Strings(after, "moved"), Is.EqualTo(new[] { "[2] Edit «Buscar» was [1]" }));
                Assert.That(Strings(after, "gone"), Is.EqualTo(new[] { "Button «Cerrar»", "Button «Salir» disabled" }));
                Assert.That(after.TryGetProperty("omitted", out _), Is.False);
                string view = worker.Commands[1];
                Assert.That(view, Does.Contain("\"cmd\":\"view\"").And.Contain("\"hwnd\":" + (long)window)
                    .And.Contain("\"limit\":60").And.Contain("\"seconds\":"), "the look's own request, bounded");
                Assert.That(ViewsRead(adapter), Is.EqualTo(viewsBefore + 1), "the read counts as a view");
                Assert.That(adapter.TryViewedField(1, out nint viewed, out string id) && viewed == window && id == "1.5",
                    Is.True, "the new index is of the view after the act");
            });
        });
    }

    // C67 (R8-NB-5): a click proved by the window's image (surfaceChanged) on a browser whose tree lists only an old
    // document came back completed with after «same», which the model read as «the window did not change» and pressed
    // again. The tree's view says only that its listed controls are the same («sameListed»), never the window unchanged;
    // without the image changed, «same» stays.
    [TestCase(true, TestName = "the image changed: only the listed controls are the same")]
    [TestCase(false, TestName = "counter-case: the image did not change: the same window")]
    public void AClickProvedByItsImageWhoseTreeListsTheSameIsNotTheSameWindow(bool surfaceChanged)
    {
        WithWindow(window =>
        {
            const string ViewSame =
                "{\"ok\":true,\"error\":\"\",\"window\":\"\",\"controls\":[" +
                "{\"kind\":\"Document\",\"name\":\"Inicio\",\"id\":\"1.1\",\"state\":\"\",\"value\":null}]," +
                "\"controlCount\":1,\"partial\":false}";
            string pressed = Pressed.Replace(
                "\"surfaceChanged\":false", "\"surfaceChanged\":" + (surfaceChanged ? "true" : "false"),
                StringComparison.Ordinal);
            WindowsVisibleControlAdapter adapter = Adapter(new OrderedWorker(pressed, ViewSame));
            RememberView(adapter, window, new ViewControlSpec(0, "1.1", "Document", "Inicio", ""));

            ExternalCapabilityReceipt receipt = Click(adapter, window, "Abrir", "1.1");

            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result.GetValueOrDefault().GetProperty("after").GetRawText(),
                Is.EqualTo(surfaceChanged ? "{\"sameListed\":true}" : "{\"same\":true}"));
        });
    }

    // C67 held-out (written from the contract by a reviewer who did not see the change): «Kind|Name|State» controls,
    // the same before and after unless the first is renamed.
    [TestCase("true", "uia", "invoke", "Button|Aceptar|", null, 1, "{\"sameListed\":true}")]
    [TestCase("true", "readback", "invoke", "Button|Guardar|;Edit|Nombre|;CheckBox|Recordar|", null, 3,
        "{\"sameListed\":true}")]
    [TestCase("true", "uia", "point", "Button|Buscar|;Edit|Consulta|", null, 2, "{\"sameListed\":true}")]
    [TestCase("true", "uia", "invoke", "TabItem|Pestaña 2|focused;TabItem|Pestaña 1|", null, 2, "{\"sameListed\":true}")]
    [TestCase("true", "readback", "point", "ListItem|Elemento 3|selected;List|Resultados|", null, 2,
        "{\"sameListed\":true}")]
    [TestCase("true", "uia", "invoke", "MenuItem|Configuración avanzada|;MenuItem|Ayuda|disabled", null, 2,
        "{\"sameListed\":true}")]
    [TestCase("false", "readback", "invoke", "Button|Guardar|;Edit|Nombre|;CheckBox|Recordar|", null, 3,
        "{\"same\":true}")]
    [TestCase(null, "uia", "invoke", "Button|Guardar|;Edit|Nombre|", null, 2, "{\"same\":true}")]
    [TestCase("true", "uia", "invoke", "Button|Activar|", "Desactivar", 1, "{\"changed\":[\"[0] Button «Desactivar»\"]}")]
    [TestCase("true", "uia", "invoke", "ListItem|Fila 1|;ListItem|Fila 2|", null, 80,
        "{\"sameListed\":true,\"cut\":true}")]
    public void HeldOutClicksWhoseTreeListsTheSame(
        string? surfaceChanged, string stage, string method, string controls, string? renamed, int controlCount,
        string expected)
    {
        WithWindow(window =>
        {
            string[][] rows = [.. controls.Split(';').Select(row => row.Split('|'))];
            string pressed =
                "{\"version\":2,\"ok\":true,\"effectObserved\":true,\"error\":\"\",\"name\":\"" + rows[0][1] + "\"," +
                "\"kind\":\"" + rows[0][0] + "\",\"controlIdentity\":\"1.1\",\"absentOrDisabled\":false," +
                "\"selected\":true,\"toggled\":false," +
                (surfaceChanged is null ? string.Empty : "\"surfaceChanged\":" + surfaceChanged + ",") +
                "\"cascadeStage\":\"" + stage + "\",\"method\":\"" + method + "\"}";
            string viewAfter =
                "{\"ok\":true,\"error\":\"\",\"window\":\"\",\"controls\":[" +
                string.Join(',', rows.Select((row, i) =>
                    "{\"kind\":\"" + row[0] + "\",\"name\":\"" + (i == 0 && renamed is not null ? renamed : row[1]) +
                    "\",\"id\":\"1." + (i + 1) + "\",\"state\":\"" + row[2] + "\",\"value\":null}")) +
                "],\"controlCount\":" + controlCount + ",\"partial\":false}";
            WindowsVisibleControlAdapter adapter = Adapter(new OrderedWorker(pressed, viewAfter));
            RememberView(adapter, window,
                [.. rows.Select((row, i) => new ViewControlSpec(i, "1." + (i + 1), row[0], row[1], row[2]))]);

            ExternalCapabilityReceipt receipt = Click(adapter, window, rows[0][1], "1.1");

            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            JsonElement after = receipt.Result.GetValueOrDefault().GetProperty("after");
            Assert.That(JsonElement.DeepEquals(after, Json(expected)), Is.True, after.GetRawText());
        });
    }

    [Test]
    public void AnIndexOfTheViewAfterIsPressedAndAnOldIndexThatIsGoneIsRefused()
    {
        WithWindow(window =>
        {
            var worker = new OrderedWorker(Pressed, ViewAfter, Pressed.Replace("1.1", "1.5", StringComparison.Ordinal));
            WindowsVisibleControlAdapter adapter = Adapter(worker);
            RememberView(adapter, window, Before);
            _ = Click(adapter, window, "Abrir", "1.1");

            ExternalCapabilityReceipt saved = adapter.InvokeAsync(
                    "input.visible.click", Json("{\"label\":\"Guardar\",\"index\":1,\"window\":" + (long)window + "}"),
                    CancellationToken.None)
                .AsTask().GetAwaiter().GetResult();
            _ = adapter.InvokeAsync(
                    "input.visible.click", Json("{\"label\":\"Salir\",\"index\":3,\"window\":" + (long)window + "}"),
                    CancellationToken.None)
                .AsTask().GetAwaiter().GetResult();

            Assert.Multiple(() =>
            {
                Assert.That(saved.Verified, Is.True, saved.ErrorCode);
                Assert.That(worker.Commands[2], Does.Contain("\"cmd\":\"click\"").And.Contain("\"controlId\":\"1.5\""),
                    "the index the receipt gave is pressed by its identity");
                Assert.That(worker.Commands.Any(command => command.Contains("\"controlId\":\"1.4\"", StringComparison.Ordinal)),
                    Is.False, "the old index's control is never pressed: " + string.Join(" | ", worker.Commands));
                Assert.That(adapter.TryViewedField(3, out _, out _), Is.False, "an index the view after has not");
            });
        });
    }

    // A read that does not answer, fails or is cut by its deadline: the receipt is the one of today, and the last view
    // stays the one the model has.
    [TestCase(null, TestName = "no answer: the receipt of today")]
    [TestCase("{\"ok\":false,\"error\":\"visible_controls_uia_failed\"}", TestName = "a failed read: the receipt of today")]
    [TestCase("partial", TestName = "a read cut by its deadline: the receipt of today")]
    public void AReadAfterThatFailsLeavesTheReceiptOfToday(string? answer)
    {
        WithWindow(window =>
        {
            string? view = answer == "partial" ? ViewAfter.Replace("\"partial\":false", "\"partial\":true", StringComparison.Ordinal) : answer;
            var worker = new OrderedWorker(view is null ? [Pressed] : [Pressed, view]);
            WindowsVisibleControlAdapter adapter = Adapter(worker);
            RememberView(adapter, window, Before);
            long viewsBefore = ViewsRead(adapter);

            ExternalCapabilityReceipt receipt = Click(adapter, window, "Abrir", "1.1");

            var today = new OrderedWorker(Pressed);
            WindowsVisibleControlAdapter without = Adapter(today, readsAfter: false);
            RememberView(without, window, Before);
            ExternalCapabilityReceipt expected = Click(without, window, "Abrir", "1.1");

            Assert.Multiple(() =>
            {
                Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
                Assert.That(receipt.Result!.Value.GetRawText(), Is.EqualTo(expected.Result!.Value.GetRawText()));
                Assert.That(ViewsRead(adapter), Is.EqualTo(viewsBefore), "no view was read");
                Assert.That(adapter.TryViewedField(3, out _, out string id) && id == "1.4", Is.True, "the last view stays");
            });
        });
    }

    // A click whose effect went to another window (a dialog it opened, a popup, a list or menu it opened, a window of
    // another process) is not read again here: the window's own tree does not show it.
    [TestCase("\"dialogOpened\":true")]
    [TestCase("\"popupBorn\":true")]
    [TestCase("\"opened\":true")]
    public void AClickWhoseEffectWentElsewhereIsNotReadAgain(string elsewhere)
    {
        WithWindow(window =>
        {
            var worker = new OrderedWorker(Pressed.Replace("\"method\":\"invoke\"", "\"method\":\"invoke\"," + elsewhere,
                StringComparison.Ordinal), ViewAfter);
            WindowsVisibleControlAdapter adapter = Adapter(worker);
            RememberView(adapter, window, Before);

            ExternalCapabilityReceipt receipt = Click(adapter, window, "Abrir", "1.1");

            Assert.Multiple(() =>
            {
                Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
                Assert.That(receipt.Result!.Value.TryGetProperty("after", out _), Is.False);
                Assert.That(worker.Commands, Has.Count.EqualTo(1), string.Join(" | ", worker.Commands));
            });
        });
    }

    // Contracase: a click that did not complete reads nothing again.
    [Test]
    public void AClickThatDidNotCompleteIsNotReadAgain()
    {
        WithWindow(window =>
        {
            const string Unchanged =
                "{\"version\":2,\"ok\":false,\"effectObserved\":true,\"error\":\"visible_click_failed\",\"name\":\"Abrir\"," +
                "\"kind\":\"Button\",\"controlIdentity\":\"1.1\"}";
            var worker = new OrderedWorker(Unchanged, ViewAfter);
            WindowsVisibleControlAdapter adapter = Adapter(worker);
            RememberView(adapter, window, Before);

            ExternalCapabilityReceipt receipt = Click(adapter, window, "Abrir", "1.1");

            Assert.Multiple(() =>
            {
                Assert.That(receipt.Verified, Is.False);
                Assert.That(worker.Commands.Count(command => command.Contains("\"cmd\":\"view\"", StringComparison.Ordinal)),
                    Is.Zero, string.Join(" | ", worker.Commands));
            });
        });
    }

    [Test]
    public void TheDifferenceIsCappedSaysWhatItLeftOutAndTheTitle()
    {
        var before = new List<WindowsVisibleControlAdapter.ViewControl>
        {
            new() { Index = 0, Id = "1.1", Kind = "Button", Name = "Abrir" },
            new() { Index = 1, Id = "1.2", Kind = "CheckBox", Name = "Negrita", State = "off" },
            new() { Index = 2, Id = "1.3", Kind = "Text", Name = "La pantalla muestra 0" },
        };
        var after = new List<WindowsVisibleControlAdapter.ViewControl>
        {
            new() { Index = 0, Id = "1.1", Kind = "Button", Name = "Abrir" },
            new() { Index = 1, Id = "1.2", Kind = "CheckBox", Name = "Negrita", State = "on" },
            new() { Index = 2, Id = "1.3", Kind = "Text", Name = "La pantalla muestra 5" },
        };
        for (int i = 0; i < 30; i++)
            after.Add(new() { Index = 3 + i, Id = "2." + i, Kind = "ListItem", Name = "Fila " + i });

        JsonElement capped = WindowsVisibleControlAdapter.ViewDifference(before, "Sin título", after, [], "Documento");
        JsonElement same = WindowsVisibleControlAdapter.ViewDifference(before, "Sin título", before, [], "Sin título");

        Assert.Multiple(() =>
        {
            Assert.That(Strings(capped, "appeared"), Has.Length.EqualTo(18));
            Assert.That(Strings(capped, "appeared")[0], Is.EqualTo("[3] ListItem «Fila 0»"));
            Assert.That(Strings(capped, "changed"), Is.EqualTo(new[]
            {
                "[1] CheckBox «Negrita» off → on", "[2] Text «La pantalla muestra 5»",
            }), "the same identity with another state or name is a change, never gone and appeared");
            Assert.That(capped.GetProperty("omitted").GetInt32(), Is.EqualTo(12), "30 + 2 entries, 20 shown");
            Assert.That(capped.GetProperty("title").GetString(), Is.EqualTo("Documento"));
            Assert.That(same.GetProperty("same").GetBoolean(), Is.True);
            Assert.That(same.EnumerateObject().Count(), Is.EqualTo(1), "nothing else said of a window that did not change");
        });
    }

    // Holdout v5 V5E029 (s1): «Modo de calculadora Estándar», a Text and not a button, was clicked; the window's image
    // changed because the display lost the focus ring, and the click came back completed. A click whose only proof is
    // the image, with the view after it differing only in the focus, is unchanged and carries that view; a view after
    // it with anything else changed keeps it completed.
    // Revisión w11: a view cut at its cap (the window had more controls than it listed) does not know its unlisted
    // controls the same: a press the tree made whose effect fell past the cap (a message sent, an item deleted at the end
    // of a long list) is not told unchanged, which would have the model press it again; it stays completed, with the
    // listed difference and its «cut».
    [TestCase("Se muestra 0", "visible_button_postread_unchanged", 2, TestName = "only the focus moved: unchanged")]
    [TestCase("Se muestra 0", null, 74, TestName = "only the listed focus moved, cut view: completed")]
    [TestCase("Se muestra 5", null, 2, TestName = "counter-case: the display changed: completed")]
    public void AClickProvedByItsImageWhoseViewAfterDiffersOnlyInTheFocusIsUnchanged(
        string shown, string? error, int controlCount)
    {
        WithWindow(window =>
        {
            const string PendingLabel =
                "{\"version\":2,\"ok\":false,\"effectObserved\":true,\"error\":\"visible_button_postread_pending\"," +
                "\"pending\":true,\"name\":\"Modo de calculadora Estándar\",\"kind\":\"Text\"," +
                "\"controlIdentity\":\"1.46\",\"absentOrDisabled\":false,\"selected\":false,\"toggled\":false}";
            const string UnchangedLabel =
                "{\"version\":2,\"ok\":false,\"effectObserved\":true,\"error\":\"visible_button_postread_unchanged\"," +
                "\"name\":\"Modo de calculadora Estándar\",\"controlIdentity\":\"1.46\",\"absentOrDisabled\":false}";
            string viewAfter =
                "{\"ok\":true,\"error\":\"\",\"window\":\"Calculadora\",\"controls\":[" +
                "{\"kind\":\"Text\",\"name\":\"" + shown + "\",\"id\":\"1.38\",\"state\":\"\",\"value\":null}," +
                "{\"kind\":\"Text\",\"name\":\"Modo de calculadora Estándar\",\"id\":\"1.46\",\"state\":\"\"," +
                "\"value\":null}]," +
                "\"controlCount\":" + controlCount + ",\"partial\":false}";
            var worker = new CommandWorker(command => command switch
            {
                "click" => PendingLabel,
                "postread" => UnchangedLabel,
                "view" => viewAfter,
                _ => null,
            });
            int captures = 0;
            // The three images before the click are the same; every one after it differs from them.
            ValueTask<VisibleControlSurface.CapturedWindow?> Capture(nint hwnd, bool? selfDrawn, CancellationToken token) =>
                ValueTask.FromResult<VisibleControlSurface.CapturedWindow?>(
                    new VisibleControlSurface.CapturedWindow(hwnd, [], 0, 0, 10, 10, captures++ < 3 ? "before" : "after"));
            var adapter = new WindowsVisibleControlAdapter(worker, null, null, elevated: _ => false, capture: Capture)
            {
                ReadsAfterAct = true,
                PopupsOf = _ => [],
            };
            RememberView(adapter, window,
                new(0, "1.38", "Text", "Se muestra 0", "focused"),
                new(1, "1.46", "Text", "Modo de calculadora Estándar", ""));

            ExternalCapabilityReceipt receipt = Click(adapter, window, "Modo de calculadora Estándar", "1.46");

            Assert.That(receipt.Result, Is.Not.Null, receipt.ErrorCode);
            JsonElement after = receipt.Result!.Value.GetProperty("after");
            Assert.Multiple(() =>
            {
                Assert.That(receipt.ErrorCode, Is.EqualTo(error));
                Assert.That(receipt.Verified, Is.EqualTo(error is null));
                Assert.That(after.TryGetProperty("focusOnly", out _), Is.EqualTo(error is not null));
                Assert.That(after.TryGetProperty("cut", out _), Is.EqualTo(controlCount > 2));
                Assert.That(Strings(after, "changed"), Is.EqualTo(new[] { $"[0] Text «{shown}» focused → (none)" }));
            });
        });
    }

    // Banco de uso 05-11 (U40, S03): with the keyboard on the window's menu bar a look read only the frame, typing failed, and
    // «Enviar» was pressed on an empty box. The press only took the focus off the menu: the image changed, every control
    // «appeared», the click came back completed and verified, and the model said the message went, with 0 sent. What the look
    // before never read cannot have appeared, and a changed image does not say what the press did.
    private static void RememberFrameOnly(WindowsVisibleControlAdapter adapter, nint window)
    {
        RememberView(adapter, window,
            new(0, "1.1", "MenuItem", "Sistema", "collapsed focused"),
            new(1, "1.2", "TitleBar", "Chat de prueba", ""));
        FieldInfo field = typeof(WindowsVisibleControlAdapter).GetField("_lastView", BindingFlags.NonPublic | BindingFlags.Instance)!;
        field.FieldType.GetProperty("FrameOnly", BindingFlags.NonPublic | BindingFlags.Instance)!
            .SetValue(field.GetValue(adapter), true);
    }

    private static CommandWorker ImageProvedWorker(string viewAfter) => new(command => command switch
    {
        "click" => "{\"version\":2,\"ok\":false,\"effectObserved\":true,\"error\":\"visible_button_postread_pending\",\"pending\":true," +
            "\"name\":\"Enviar\",\"kind\":\"Button\",\"controlIdentity\":\"1.46\",\"absentOrDisabled\":false,\"selected\":false,\"toggled\":false}",
        "postread" => "{\"version\":2,\"ok\":false,\"effectObserved\":true,\"error\":\"visible_button_postread_unchanged\"," +
            "\"name\":\"Enviar\",\"controlIdentity\":\"1.46\",\"absentOrDisabled\":false}",
        "view" => viewAfter,
        _ => null,
    });

    private static WindowsVisibleControlAdapter ImageProvedAdapter(IUiaWorker worker)
    {
        int captures = 0;
        ValueTask<VisibleControlSurface.CapturedWindow?> Capture(nint hwnd, bool? selfDrawn, CancellationToken token) =>
            ValueTask.FromResult<VisibleControlSurface.CapturedWindow?>(
                new VisibleControlSurface.CapturedWindow(hwnd, [], 0, 0, 10, 10, captures++ < 3 ? "before" : "after"));
        return new WindowsVisibleControlAdapter(worker, null, null, elevated: _ => false, capture: Capture)
        {
            ReadsAfterAct = true,
            PopupsOf = _ => [],
        };
    }

    private const string ChatRead =
        "{\"ok\":true,\"error\":\"\",\"window\":\"Chat de prueba\",\"controls\":[" +
        "{\"kind\":\"MenuItem\",\"name\":\"Sistema\",\"id\":\"1.1\",\"state\":\"collapsed\",\"value\":null}," +
        "{\"kind\":\"TitleBar\",\"name\":\"Chat de prueba\",\"id\":\"1.2\",\"state\":\"\",\"value\":null}," +
        "{\"kind\":\"Button\",\"name\":\"Enviar\",\"id\":\"1.46\",\"state\":\"\",\"value\":null}," +
        "{\"kind\":\"Edit\",\"name\":\"Escribe un mensaje\",\"id\":\"1.47\",\"state\":\"\",\"value\":\"\"}," +
        "{\"kind\":\"Edit\",\"name\":\"Sin patrón\",\"id\":\"1.48\",\"state\":\"\",\"value\":null}," +
        "{\"kind\":\"Edit\",\"name\":\"Mensajes\",\"id\":\"1.49\",\"state\":\"readonly focused\",\"value\":\"VALOR\"}]," +
        "\"controlCount\":6,\"partial\":false}";

    [TestCase("", TestName = "frame-only look, the box and the history read empty after the press")]
    [TestCase("Yo: llego a las siete", TestName = "frame-only look, the history holds the message after the press")]
    public void APressProvedOnlyByItsImageFromALookAtTheFrameIsNotToldReadBack(string history)
    {
        WithWindow(window =>
        {
            var adapter = ImageProvedAdapter(ImageProvedWorker(ChatRead.Replace("VALOR", history, StringComparison.Ordinal)));
            RememberFrameOnly(adapter, window);

            ExternalCapabilityReceipt receipt = Click(adapter, window, "Enviar", "1.46");

            Assert.That(receipt.Result, Is.Not.Null, receipt.ErrorCode);
            JsonElement result = receipt.Result!.Value;
            JsonElement after = result.GetProperty("after");
            string[] readNow = Strings(after, "readNow");
            Assert.Multiple(() =>
            {
                Assert.That(receipt.Verified, Is.True, "the press went, as a key's does");
                Assert.That(result.GetProperty("delivered").GetBoolean(), Is.True);
                Assert.That(result.GetProperty("readBack").GetBoolean(), Is.False);
                Assert.That(result.GetProperty("next").GetString(), Does.Contain("could not confirm").And.Contain("still failed"));
                Assert.That(OperationVisibleFacts.Verification("input.visible.click", result), Is.EqualTo("delivered_only"));
                Assert.That(after.TryGetProperty("appeared", out _), Is.False, "nothing is known to have appeared");
                Assert.That(after.GetProperty("before").GetString(), Does.Contain("frame"));
                Assert.That(readNow, Does.Contain("[3] Edit «Escribe un mensaje» empty"));
                // No value exposed is not known empty.
                Assert.That(readNow, Does.Contain("[4] Edit «Sin patrón»"));
                Assert.That(readNow, Does.Contain(history.Length == 0
                    ? "[5] Edit «Mensajes» readonly focused empty"
                    : "[5] Edit «Mensajes» readonly focused = " + history));
            });
        });
    }

    // Controls: a look that read the window compares as before, and a window that is drawn with no tree (a game, a launcher)
    // keeps its image as the proof: frame before, frame after, nothing newly read.
    [Test]
    public void APressFromALookThatReadTheWindowIsStillReadBack()
    {
        WithWindow(window =>
        {
            var adapter = ImageProvedAdapter(ImageProvedWorker(ChatRead.Replace("VALOR", "Yo: hola", StringComparison.Ordinal)));
            RememberView(adapter, window,
                new(0, "1.46", "Button", "Enviar", ""),
                new(1, "1.49", "Edit", "Mensajes", "readonly"));

            ExternalCapabilityReceipt receipt = Click(adapter, window, "Enviar", "1.46");

            JsonElement result = receipt.Result!.Value;
            Assert.Multiple(() =>
            {
                Assert.That(result.TryGetProperty("delivered", out _), Is.False);
                Assert.That(OperationVisibleFacts.Verification("input.visible.click", result), Is.EqualTo("readback"));
                Assert.That(result.GetProperty("after").TryGetProperty("appeared", out _), Is.True);
                Assert.That(result.GetProperty("after").TryGetProperty("before", out _), Is.False);
            });
        });
    }

    [Test]
    public void APressOnAWindowDrawnWithNoTreeKeepsItsImageAsProof()
    {
        const string frame =
            "{\"ok\":true,\"error\":\"\",\"window\":\"Lanzador\",\"frameOnly\":true,\"controls\":[" +
            "{\"kind\":\"MenuItem\",\"name\":\"Sistema\",\"id\":\"1.1\",\"state\":\"collapsed focused\",\"value\":null}," +
            "{\"kind\":\"TitleBar\",\"name\":\"Chat de prueba\",\"id\":\"1.2\",\"state\":\"\",\"value\":null}]," +
            "\"controlCount\":2,\"partial\":false}";
        WithWindow(window =>
        {
            var adapter = ImageProvedAdapter(ImageProvedWorker(frame));
            RememberFrameOnly(adapter, window);

            ExternalCapabilityReceipt receipt = Click(adapter, window, "Enviar", "1.46");

            JsonElement result = receipt.Result!.Value;
            Assert.Multiple(() =>
            {
                Assert.That(result.TryGetProperty("delivered", out _), Is.False);
                Assert.That(OperationVisibleFacts.Verification("input.visible.click", result), Is.EqualTo("readback"));
                Assert.That(result.GetProperty("after").TryGetProperty("sameListed", out _), Is.True);
            });
        });
    }

    // The pointer's stages (OCR, a tooltip, vision) say the same as the tree's: an image that changed with only the focus moved.
    // Kept completed: unlike the tree's press, a point on a drawn surface may have done what the tree does not list.
    [TestCase("{\"surfaceChanged\":true,\"cascadeStage\":\"ocr\"}", """{"changed":["[0] Button «Enviar» (none) → focused"],"focusOnly":true}""", true)]
    [TestCase("{\"surfaceChanged\":true,\"cascadeStage\":\"ocr\"}", """{"changed":["[0] Edit «Mensajes» = hola"]}""", false)]
    [TestCase("{\"surfaceChanged\":true,\"cascadeStage\":\"ocr\"}", """{"sameListed":true}""", false)]
    [TestCase("{\"surfaceChanged\":false,\"selected\":true}", """{"changed":["[0] ListItem «A» (none) → selected"]}""", false)]
    [TestCase("{\"surfaceChanged\":true,\"selected\":true}", """{"changed":["[0] ListItem «A» focused → (none)"],"focusOnly":true}""", false)]
    [TestCase("{\"surfaceChanged\":true,\"toggled\":true}", """{"before":"x","readNow":["[0] Button «A»"]}""", false)]
    [TestCase("{\"surfaceChanged\":true,\"cascadeStage\":\"ocr\"}", """{"before":"x","readNow":["[0] Button «A»"]}""", true)]
    public void AnImageAloneWithNothingElseReadIsNotReadBack(string receipt, string after, bool notReadBack)
    {
        using JsonDocument result = JsonDocument.Parse(receipt);
        using JsonDocument view = JsonDocument.Parse(after);

        JsonElement told = WindowsVisibleControlAdapter.WithImageAloneTold(
            new ExternalCapabilityReceipt("input.visible.click", true, true, result.RootElement.Clone(), null), view.RootElement).Result!.Value;

        Assert.Multiple(() =>
        {
            Assert.That(told.TryGetProperty("delivered", out _), Is.EqualTo(notReadBack));
            Assert.That(told.TryGetProperty("readBack", out _), Is.EqualTo(notReadBack));
        });
    }

    // Encargo 100, measured live: the model pressed a menu entry by its label, a web search opened in the person's browser with a
    // word of the document in its address, and the receipt said completed with nothing of it. Pressing an entry may be what the
    // person asked (a help page), so it is left open, and said.
    private static WindowsVisibleControlAdapter MenuAdapter(IUiaWorker worker, Func<BrowserWitness?> browsers)
    {
        int captures = 0;
        ValueTask<VisibleControlSurface.CapturedWindow?> Capture(nint hwnd, bool? selfDrawn, CancellationToken token) =>
            ValueTask.FromResult<VisibleControlSurface.CapturedWindow?>(
                new VisibleControlSurface.CapturedWindow(hwnd, [], 0, 0, 10, 10, captures++ < 3 ? "before" : "after"));
        return new WindowsVisibleControlAdapter(worker, null, null, elevated: _ => false, capture: Capture)
        {
            ReadsAfterAct = true,
            PopupsOf = _ => [],
            BrowsersNow = browsers,
        };
    }

    private static CommandWorker MenuWorker(string kind) => new(command => command switch
    {
        "click" => "{\"version\":2,\"ok\":false,\"effectObserved\":true,\"error\":\"visible_button_postread_pending\",\"pending\":true," +
            "\"name\":\"Entrada\",\"kind\":\"" + kind + "\",\"controlIdentity\":\"1.46\",\"absentOrDisabled\":false,\"selected\":false,\"toggled\":false}",
        "postread" => "{\"version\":2,\"ok\":false,\"effectObserved\":true,\"error\":\"visible_button_postread_unchanged\"," +
            "\"name\":\"Entrada\",\"controlIdentity\":\"1.46\",\"absentOrDisabled\":true}",
        "view" => "{\"ok\":true,\"error\":\"\",\"window\":\"Editor\",\"controls\":[{\"kind\":\"Edit\",\"name\":\"Texto\",\"id\":\"1.38\",\"state\":\"\",\"value\":null}]," +
            "\"controlCount\":1,\"partial\":false}",
        _ => null,
    });

    [Test]
    public void AMenuEntryThatOpenedABrowserSaysSoAndLeavesItOpen()
    {
        WithWindow(window =>
        {
            int reads = 0;
            var adapter = MenuAdapter(MenuWorker("MenuItem"), () => reads++ == 0
                ? new BrowserWitness([], new HashSet<string>(), window)
                : new BrowserWitness([new BrowserWindow(20, 50, "palabra - Buscar")], new HashSet<string> { "navegador" }, window));
            RememberView(adapter, window, new ViewControlSpec(0, "1.46", "MenuItem", "Entrada", ""));

            ExternalCapabilityReceipt receipt = Click(adapter, window, "Entrada", "1.46");

            Assert.That(receipt.Result, Is.Not.Null, receipt.ErrorCode);
            JsonElement result = receipt.Result!.Value;
            Assert.Multiple(() =>
            {
                Assert.That(result.TryGetProperty("browserOpened", out JsonElement opened), Is.True);
                Assert.That(opened.ValueKind == JsonValueKind.Object && opened.GetProperty("title").GetString() == "palabra - Buscar");
                Assert.That(opened.ValueKind == JsonValueKind.Object && !opened.GetProperty("closed").GetBoolean());
                Assert.That(result.TryGetProperty("next", out JsonElement next) ? next.GetString() : "",
                    Does.Contain("«palabra - Buscar»").And.Contain("may have gone out").And.Contain("still open"));
            });
        });
    }

    // Contracases: a menu that only opens its entries, and any other control (a link is what opens a browser on purpose): no
    // read of the browsers, so no time lost on them.
    [TestCase("MenuItem", "collapsed")]
    [TestCase("MenuItem", "expanded")]
    [TestCase("Button", "")]
    [TestCase("Hyperlink", "")]
    public void WhatIsNoMenuCommandIsNotWatched(string kind, string state)
    {
        WithWindow(window =>
        {
            int reads = 0;
            var adapter = MenuAdapter(MenuWorker(kind), () =>
            {
                reads++;
                return new BrowserWitness([], new HashSet<string>(), window);
            });
            RememberView(adapter, window, new ViewControlSpec(0, "1.46", kind, "Entrada", state));

            ExternalCapabilityReceipt receipt = Click(adapter, window, "Entrada", "1.46");

            Assert.Multiple(() =>
            {
                Assert.That(reads, Is.Zero);
                Assert.That(receipt.Result?.TryGetProperty("browserOpened", out _), Is.Not.True);
            });
        });
    }

    [Test]
    public void AMenuEntryThatOpenedNothingSaysNothingOfBrowsers()
    {
        WithWindow(window =>
        {
            var adapter = MenuAdapter(MenuWorker("MenuItem"), () => new BrowserWitness([], new HashSet<string>(), window));
            RememberView(adapter, window, new ViewControlSpec(0, "1.46", "MenuItem", "Entrada", ""));

            ExternalCapabilityReceipt receipt = Click(adapter, window, "Entrada", "1.46");

            Assert.That(receipt.Result?.TryGetProperty("browserOpened", out _), Is.Not.True);
        });
    }

    // Revisión de nb-w11-revision: a click that brings up a window of another process (a button that opens the browser)
    // leaves its own window inactive: its image changes (the title bar, the focus ring) and the view after it differs
    // only in the focus the window lost. That is the click's effect, never «unchanged» (the model would press it again:
    // a second browser window, a second send).
    [Test]
    public void AClickAfterWhichAnotherProcesssWindowCameIsNotFocusOnlyUnchanged()
    {
        WithWindow(window =>
        {
            const string PendingButton =
                "{\"version\":2,\"ok\":false,\"effectObserved\":true,\"error\":\"visible_button_postread_pending\"," +
                "\"pending\":true,\"name\":\"Abrir en el navegador\",\"kind\":\"Button\"," +
                "\"controlIdentity\":\"1.46\",\"absentOrDisabled\":false,\"selected\":false,\"toggled\":false}";
            const string UnchangedButton =
                "{\"version\":2,\"ok\":false,\"effectObserved\":true,\"error\":\"visible_button_postread_unchanged\"," +
                "\"name\":\"Abrir en el navegador\",\"controlIdentity\":\"1.46\",\"absentOrDisabled\":false}";
            const string ViewAfterIt =
                "{\"ok\":true,\"error\":\"\",\"window\":\"Ajustes\",\"controls\":[" +
                "{\"kind\":\"Edit\",\"name\":\"Buscar\",\"id\":\"1.38\",\"state\":\"\",\"value\":null}," +
                "{\"kind\":\"Button\",\"name\":\"Abrir en el navegador\",\"id\":\"1.46\",\"state\":\"\",\"value\":null}]," +
                "\"controlCount\":2,\"partial\":false}";
            var worker = new CommandWorker(command => command switch
            {
                "click" => PendingButton,
                "postread" => UnchangedButton,
                "view" => ViewAfterIt,
                _ => null,
            });
            int captures = 0;
            ValueTask<VisibleControlSurface.CapturedWindow?> Capture(nint hwnd, bool? selfDrawn, CancellationToken token) =>
                ValueTask.FromResult<VisibleControlSurface.CapturedWindow?>(
                    new VisibleControlSurface.CapturedWindow(hwnd, [], 0, 0, 10, 10, captures++ < 3 ? "before" : "after"));
            const int Clicked = 4100, Browser = 5200;
            const nint BrowserWindow = 9100;
            VisibleControlSurface.RootSnapshot Snapshot(nint front, params (nint Window, int Process)[] windows) =>
                new([.. windows.Select(item => new VisibleControlSurface.RootWindow(item.Window, item.Process))], front,
                    new HashSet<int> { Clicked }, 10, windows.ToDictionary(item => item.Process, _ => 4));
            int looked = 0;
            var adapter = new WindowsVisibleControlAdapter(worker, null, null, elevated: _ => false, capture: Capture)
            {
                ReadsAfterAct = true,
                PopupsOf = _ => [],
                RootWindows = _ => looked++ == 0
                    ? Snapshot(window, (window, Clicked))
                    : Snapshot(BrowserWindow, (BrowserWindow, Browser), (window, Clicked)),
                DescribeHanded = _ => null,
            };
            RememberView(adapter, window,
                new(0, "1.38", "Edit", "Buscar", "focused"),
                new(1, "1.46", "Button", "Abrir en el navegador", ""));

            ExternalCapabilityReceipt receipt = Click(adapter, window, "Abrir en el navegador", "1.46");

            Assert.That(receipt.ErrorCode, Is.Not.EqualTo("visible_button_postread_unchanged"),
                "a window of another process came after the click: its effect, not «unchanged»");
        });
    }

    // input.text.type and input.key.press: a completed act on a named window carries the view after it; one that did
    // not complete, or with no window named, reads nothing.
    [Test]
    public async Task ACompletedTextOnANamedWindowCarriesTheViewAfterIt()
    {
        var fields = new AfterFields(
            """{"ok":true,"error":"","kind":"Edit","className":"","nativeHwnd":0,"method":"setvalue","delivered":true}""");
        var adapter = new WindowsDesktopInteractionAdapter(
            new NoProcessRunner(), "folder.ps1", "file.ps1", "select.ps1", "keys.ps1", new FakeDesktopKeyboard(), fields,
            new FakeFieldMessages());

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.text.type", Json("""{"text":"mouse","window":4660,"index":3}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(fields.AfterAsked, Is.EqualTo(new nint[] { 4660 }));
            Assert.That(Strings(receipt.Result!.Value.GetProperty("after"), "changed"), Is.EqualTo(new[] { "[3] Edit «Buscar» = mouse" }));
            Assert.That(receipt.Result!.Value.GetProperty("method").GetString(), Is.EqualTo("setvalue"), "the receipt of today, kept");
        });
    }

    [Test]
    public async Task AKeyThatCompletedOnANamedWindowCarriesTheViewAfterIt()
    {
        var fields = new AfterFields("{}");
        var messages = new FakeFieldMessages();
        var adapter = new WindowsDesktopInteractionAdapter(
            new NoProcessRunner(), "folder.ps1", "file.ps1", "select.ps1", "keys.ps1", new FakeDesktopKeyboard(), fields,
            messages);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.key.press", Json("""{"key":"enter","window":4660}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(fields.AfterAsked, Is.EqualTo(new nint[] { 4660 }));
            Assert.That(receipt.Result!.Value.TryGetProperty("after", out _), Is.True);
        });
    }

    [Test]
    public async Task ATextThatDidNotCompleteOrNamedNoWindowReadsNothingAfter()
    {
        var failing = new AfterFields(
            """{"ok":true,"error":"","kind":"Edit","className":"","nativeHwnd":0,"method":"setvalue","delivered":false}""");
        var adapter = new WindowsDesktopInteractionAdapter(
            new NoProcessRunner(), "folder.ps1", "file.ps1", "select.ps1", "keys.ps1", new FakeDesktopKeyboard(), failing,
            new FakeFieldMessages());
        ExternalCapabilityReceipt notDone = await adapter.InvokeAsync(
            "input.text.type", Json("""{"text":"mouse","window":4660,"index":3}"""), CancellationToken.None);

        var unnamed = new AfterFields("{}");
        var keyboard = new FakeDesktopKeyboard();
        var front = new WindowsDesktopInteractionAdapter(
            new NoProcessRunner(), "folder.ps1", "file.ps1", "select.ps1", "keys.ps1", keyboard, unnamed,
            new FakeFieldMessages());
        _ = await front.InvokeAsync("input.key.press", Json("""{"key":"enter"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(notDone.Verified, Is.False);
            Assert.That(failing.AfterAsked, Is.Empty);
            Assert.That(unnamed.AfterAsked, Is.Empty, "a key to whatever is in front has no window to read again");
        });
    }

    // The worker's look takes the read's own deadline («seconds»), so a read after an act that runs long answers
    // «partial» before the host's budget instead of being killed. Do-View's statement that walks the tree, from the
    // script's syntax tree, with the walk described: no window is read.
    [Test]
    public void TheWorkersLookTakesTheReadsOwnDeadline()
    {
        string answer = RunWorker("""
            function Get-ShownDescendants($root,[long]$hwnd=0,[double]$seconds=0,[bool]$dimmed=$false){ $script:Asked+=@([string]$seconds); return ,(New-Object System.Collections.Generic.List[object]) }
            $script:ViewSeconds=12
            $script:Asked=@()
            $root=$null;$target=@{ hwnd=42 };$withDimmed=$false
            $request=[pscustomobject]@{ cmd='view'; hwnd=42; limit=60; seconds=1.5 }
            . ([scriptblock]::Create($env:BAXY_WALK_STATEMENTS))
            $request=[pscustomobject]@{ cmd='view'; hwnd=42; limit=60 }
            . ([scriptblock]::Create($env:BAXY_WALK_STATEMENTS))
            $request=[pscustomobject]@{ cmd='view'; hwnd=42; limit=60; seconds=600 }
            . ([scriptblock]::Create($env:BAXY_WALK_STATEMENTS))
            [Console]::Out.Write(($script:Asked -join '|'))
            """);
        Assert.That(answer.Split('|'), Is.EqualTo(new[] { "1.5", "0", "12" }));
    }

    // Revisión de nb-w11-cursor: with caret_place off the look reads the focused field's caret all the same (TextPattern
    // calls on every look, and the caret in the look's JSON); the look asks for no caret then, nor does a burst's look,
    // and the worker reads one only for a look that does not say caret false.
    [Test]
    public void TheCaretIsReadOnlyForALookOfTheModelWithItsAidOn()
    {
        string on = WindowsVisibleControlAdapter.ViewCommand(7, 60, []);
        string off;
        using (Baxy.Providers.Windows.Infrastructure.ModelAids.Use("none"))
            off = WindowsVisibleControlAdapter.ViewCommand(7, 60, []);
        string answer = RunWorker("""
            $read=@($ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.IfStatementAst] -and $node.Extent.Text -match 'Get-CaretPlace' -and $node.Extent.Text -match 'NotePropertyName caret' },$true) | Sort-Object { $_.Extent.Text.Length })
            if($read.Count -eq 0){ throw 'no caret read' }
            function Get-CaretPlace($el){ $script:Reads+=1; return 'end' }
            $focused=[pscustomobject]@{ kind='Edit'; id='1.2'; value='hola' }
            $elements=@{ '1.2'=$null }
            $said=@()
            foreach($request in @([pscustomobject]@{ cmd='view'; hwnd=7; limit=60 },[pscustomobject]@{ cmd='view'; hwnd=7; limit=60; caret=$false })){
              $script:Reads=0
              $focusedOut=[pscustomobject]@{ kind='Edit' }
              . ([scriptblock]::Create($read[0].Extent.Text))
              $said+=@("$($script:Reads):$($focusedOut.caret)")
            }
            [Console]::Out.Write(($said -join '|'))
            """);

        Assert.Multiple(() =>
        {
            Assert.That(on, Is.EqualTo("""{"cmd":"view","hwnd":7,"limit":60}"""));
            Assert.That(off, Is.EqualTo("""{"cmd":"view","hwnd":7,"limit":60,"caret":false}"""));
            Assert.That(answer.Split('|'), Is.EqualTo(new[] { "1:end", "0:" }));
        });
    }

    private static string RunWorker(string body)
    {
        string worker = Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1");
        Assume.That(File.Exists(worker), "the worker script is copied next to the tests");
        string script = """
            $ErrorActionPreference='Stop'
            $tokens=$null;$errors=$null
            $ast=[System.Management.Automation.Language.Parser]::ParseFile($env:BAXY_VIEW_WORKER,[ref]$tokens,[ref]$errors)
            if($errors.Count -gt 0){ throw 'worker does not parse' }
            $view=@($ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Do-View' },$true))
            if($view.Count -ne 1){ throw 'Do-View missing' }
            $statements=@($view[0].Body.EndBlock.Statements)
            $walk=@(); $taking=$false
            foreach($statement in $statements){
              if($statement.Extent.Text -match '^\$walkSeconds='){ $taking=$true }
              if($taking){ $walk+=@($statement.Extent.Text) }
              if($statement.Extent.Text -match '^\$all=Get-ShownDescendants'){ break }
            }
            if($walk.Count -eq 0){ throw 'the walk takes no deadline of its own' }
            $env:BAXY_WALK_STATEMENTS=($walk -join "`n")

            """ + body;
        var start = new ProcessStartInfo("powershell.exe")
        {
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true,
            StandardOutputEncoding = Encoding.UTF8,
        };
        foreach (string argument in new[] { "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand" })
            start.ArgumentList.Add(argument);
        start.ArgumentList.Add(Convert.ToBase64String(Encoding.Unicode.GetBytes("[Console]::OutputEncoding=[System.Text.Encoding]::UTF8\n" + script)));
        start.Environment["BAXY_VIEW_WORKER"] = worker;
        using Process process = Process.Start(start)!;
        Task<string> error = process.StandardError.ReadToEndAsync();
        string output = ChildOutput.Read(process);
        Assert.That(process.WaitForExit(60_000), Is.True, "the script answers");
        Assert.That(process.ExitCode, Is.EqualTo(0), error.Result);
        return output.Trim();
    }

    private static string[] Strings(JsonElement section, string name) =>
        section.TryGetProperty(name, out JsonElement list) && list.ValueKind == JsonValueKind.Array
            ? [.. list.EnumerateArray().Select(item => item.GetString() ?? string.Empty)]
            : [];

    private static long ViewsRead(WindowsVisibleControlAdapter adapter) =>
        (long)typeof(WindowsVisibleControlAdapter)
            .GetField("_viewsRead", BindingFlags.NonPublic | BindingFlags.Instance)!.GetValue(adapter)!;

    private static ExternalCapabilityReceipt Click(WindowsVisibleControlAdapter adapter, nint window, string label, string id) =>
        adapter.InvokeAsync(
                "input.visible.click",
                Json("{\"label\":\"" + label + "\",\"controlId\":\"" + id + "\",\"window\":" + (long)window + "}"),
                CancellationToken.None)
            .AsTask().GetAwaiter().GetResult();

    private static WindowsVisibleControlAdapter Adapter(OrderedWorker worker, bool readsAfter = true) =>
        new(worker, null, null, elevated: _ => false, capture: (_, _, _) =>
            ValueTask.FromResult<VisibleControlSurface.CapturedWindow?>(null))
        {
            ReadsAfterAct = readsAfter,
            PopupsOf = _ => [],
        };

    // An off-screen window of this test that takes no activation: alive for the adapter, never the person's.
    private static void WithWindow(Action<nint> test)
    {
        nint window = PumpedWindow.Create("BAXY after fixture");
        Assert.That(window, Is.Not.EqualTo(nint.Zero));
        try
        {
            test(window);
        }
        finally
        {
            PumpedWindow.Destroy(window);
        }
    }

    private readonly record struct ViewControlSpec(int Index, string Id, string Kind, string Name, string State);

    // The last view, as input.visible.controls leaves it.
    private static void RememberView(WindowsVisibleControlAdapter adapter, nint window, params ViewControlSpec[] specs)
    {
        FieldInfo field = typeof(WindowsVisibleControlAdapter).GetField(
            "_lastView", BindingFlags.NonPublic | BindingFlags.Instance)!;
        List<WindowsVisibleControlAdapter.ViewControl> controls = [.. specs.Select(spec =>
            new WindowsVisibleControlAdapter.ViewControl
            {
                Index = spec.Index, Id = spec.Id, Kind = spec.Kind, Name = spec.Name, State = spec.State,
            })];
        object view = Activator.CreateInstance(
            field.FieldType, BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance, null,
            [window, controls], null)!;
        field.SetValue(adapter, view);
    }

    // A worker that answers by the command's «cmd».
    private sealed class CommandWorker(Func<string?, string?> answer) : IUiaWorker
    {
        public ValueTask<JsonDocument?> SendAsync(string commandJson, TimeSpan timeout, CancellationToken cancellationToken)
        {
            using JsonDocument command = JsonDocument.Parse(commandJson);
            string? text = answer(command.RootElement.TryGetProperty("cmd", out JsonElement name)
                ? name.GetString()
                : null);
            return ValueTask.FromResult(text is null ? null : JsonDocument.Parse(text));
        }
    }

    // A worker that answers in order (null once its answers run out).
    private sealed class OrderedWorker(params string?[] answers) : IUiaWorker
    {
        private readonly Queue<string?> _answers = new(answers);

        internal List<string> Commands { get; } = [];

        public ValueTask<JsonDocument?> SendAsync(string commandJson, TimeSpan timeout, CancellationToken cancellationToken)
        {
            Commands.Add(commandJson);
            string? next = _answers.Count == 0 ? null : _answers.Dequeue();
            return ValueTask.FromResult(next is null ? null : JsonDocument.Parse(next));
        }
    }

    private sealed class NoProcessRunner : IExternalProcessRunner
    {
        public ValueTask<ExternalProcessResult> RunAsync(
            string executable, IReadOnlyList<string> arguments, TimeSpan timeout,
            CancellationToken cancellationToken) =>
            throw new AssertionException("keys and text start no process");
    }

    // The last view's fields of window 4660, the worker's «field» answer, and the view after an act it gives.
    private sealed class AfterFields(string answer) : IViewedFields
    {
        internal List<nint> AfterAsked { get; } = [];

        public bool TryViewedField(int index, out nint window, out string controlId)
        {
            window = 4660;
            controlId = "4.2." + index;
            return true;
        }

        public ValueTask<JsonDocument?> FieldAsync(
            nint window, string controlId, string? text, bool replace, CancellationToken cancellationToken) =>
            ValueTask.FromResult<JsonDocument?>(JsonDocument.Parse(answer));

        public ValueTask<JsonDocument?> EntryAsync(nint window, string controlId, string text, CancellationToken cancellationToken) =>
            ValueTask.FromResult<JsonDocument?>(JsonDocument.Parse(answer));

        public ValueTask<JsonElement?> AfterActAsync(nint window, CancellationToken cancellationToken)
        {
            AfterAsked.Add(window);
            return ValueTask.FromResult<JsonElement?>(Json("{\"changed\":[\"[3] Edit «Buscar» = mouse\"]}"));
        }
    }

}
