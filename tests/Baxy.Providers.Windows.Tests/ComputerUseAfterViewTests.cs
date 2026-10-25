using System.Diagnostics;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
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
        string output = process.StandardOutput.ReadToEnd();
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
        nint window = CreateWindowEx(0x08000080, "STATIC", "BAXY after fixture", 0x90000000u,
            -31000, -31000, 200, 120, 0, 0, 0, 0);
        Assert.That(window, Is.Not.EqualTo(nint.Zero));
        try
        {
            test(window);
        }
        finally
        {
            _ = DestroyWindow(window);
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

    [DllImport("user32.dll", EntryPoint = "CreateWindowExW",
        CharSet = CharSet.Unicode, ExactSpelling = true, SetLastError = true)]
    private static extern nint CreateWindowEx(uint extendedStyle, string className,
        string title, uint style, int x, int y, int width, int height,
        nint parent, nint menu, nint instance, nint parameter);

    [DllImport("user32.dll", ExactSpelling = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool DestroyWindow(nint window);
}
