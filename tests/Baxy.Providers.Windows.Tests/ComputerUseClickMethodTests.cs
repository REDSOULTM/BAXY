using System.Diagnostics;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// A click without the mouse whenever the control has a way (GOAL v3, point 0, fix 2): the worker presses by the
/// first pattern (Invoke, SelectionItem.Select, Toggle, ExpandCollapse), designates a field that takes text instead
/// of clicking it, then tries LegacyIAccessible's default action and, in a classic Win32 window, a posted press; only
/// a control with none of these needs the pointer, which the adapter alone moves. Every receipt says which way it took
/// («method»). The worker's choice is taken from the script by its syntax tree and run on described controls; the
/// adapter's handling runs over scripted worker answers and a recorded pointer: no window is read or touched.
/// </summary>
[TestFixture]
public sealed class ComputerUseClickMethodTests
{
    private static JsonElement Json(string value) => JsonDocument.Parse(value).RootElement.Clone();

    [Test]
    public void TheWorkerPressesByThePatternFirstAndLeavesThePointerLast()
    {
        string worker = Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1");
        Assume.That(File.Exists(worker), "the worker script is copied next to the tests");
        const string cases = """
            [
              {"invoke":true,"kind":"Button"},
              {"select":true,"kind":"ListItem"},
              {"toggle":true,"kind":"CheckBox"},
              {"expand":true,"kind":"ComboBox"},
              {"invoke":true,"select":true,"toggle":true,"expand":true,"kind":"ListItem"},
              {"select":true,"expand":true,"kind":"TreeItem"},
              {"kind":"Edit","value":true},
              {"kind":"Document","value":true},
              {"invoke":true,"kind":"Edit","value":true},
              {"kind":"Edit","value":false},
              {"kind":"Text","value":true},
              {"kind":"Button","classic":true},
              {"kind":"ListItem"},
              {"kind":"Group","classic":false}
            ]
            """;
        string answer = RunPlanner(worker, cases);
        Assert.That(answer.Split(','), Is.EqualTo(new[]
        {
            "invoke",
            "select",
            "toggle",
            "expand",
            "invoke",                  // the order: Invoke before the others
            "select",                  // Select before ExpandCollapse
            "target legacy pointer",   // a field that takes text is designated (when it takes the focus), never clicked
            "target legacy pointer",   // a document whose value is written, too
            "invoke",                  // a pattern still comes first
            "legacy pointer",          // a read-only field is no destination
            "legacy pointer",          // a value on what is not a field is no destination
            "legacy message pointer",  // a classic Win32 window takes a posted press before the pointer
            "legacy pointer",          // counter-case: no pattern and not classic ends needing the pointer
            "legacy pointer",
        }));
    }

    [Test]
    public void WhatAPressChoosesGetsItsWaysInOrderAndAToggleNeverASecondOne()
    {
        // Recibo del clic por estado (pasada r15b v3-52, v3-46, v3-50): a list, tree, tab or grid item not chosen yet gets
        // an ordered list of ways, each tried only if the one before did not leave it chosen (Invoke-NamedControl reads
        // it back); a toggle, an item already chosen and the render surface keep their single way.
        string worker = Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1");
        Assume.That(File.Exists(worker), "the worker script is copied next to the tests");
        const string cases = """
            [
              {"invoke":true,"select":true,"kind":"ListItem"},
              {"invoke":true,"select":true,"kind":"ListItem","classic":true},
              {"select":true,"expand":true,"kind":"TreeItem"},
              {"select":true,"kind":"DataItem","classic":true},
              {"invoke":true,"select":true,"toggle":true,"kind":"ListItem"},
              {"invoke":true,"select":true,"kind":"ListItem","selected":true},
              {"invoke":true,"select":true,"kind":"ListItem","render":true},
              {"invoke":true,"select":true,"kind":"Button"}
            ]
            """;
        string answer = RunPlanner(worker, cases);
        Assert.That(answer.Split(','), Is.EqualTo(new[]
        {
            "invoke select",          // v3-52: a Qt row's Invoke did not make it current; Select next
            "invoke select message",  // a classic window's row: the posted press last
            "select",                 // v3-46: the tree item is chosen; opening it is the «open» manner, never this click
            "select message",
            "invoke",                 // contracase: a toggle never gets a second press
            "invoke",                 // contracase: an item already chosen keeps its single way
            "invoke",                 // the render surface keeps its measured order
            "invoke",                 // a button that also selects is no item of a list
        }));
    }

    [Test]
    public void AToolbarButtonSeenThroughItsMsaaProxyIsPressedByAPostedMessageBeforeItsInvoke()
    {
        // r20b palanca 4 (v3-42 «Actualizar «Programas y características» (F5)», controlIdentity 42.12650936.4.1; v3-43
        // «Atrás a Opciones de energía» and «Actualizar…»): the proxy's Invoke pressed with the physical mouse (an
        // unmarked click at the button's point within 200 ms). A Win32 button of a toolbar seen through its MSAA proxy
        // gets the press posted to the bar first; its Invoke stays as the reserve. Counter-cases: a native Win32 button
        // (its own window, no 42.* identity), a XAML or WPF button, a row: unchanged.
        string worker = Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1");
        Assume.That(File.Exists(worker), "the worker script is copied next to the tests");
        const string cases = """
            [
              {"invoke":true,"kind":"Button","classic":true,"toolbarProxy":true},
              {"invoke":true,"kind":"SplitButton","classic":true,"toolbarProxy":true},
              {"kind":"Button","classic":true,"toolbarProxy":true},
              {"invoke":true,"kind":"Button","classic":true},
              {"invoke":true,"kind":"Button"},
              {"invoke":true,"select":true,"kind":"ListItem","classic":true}
            ]
            """;
        string answer = RunPlanner(worker, cases);
        Assert.That(answer.Split(','), Is.EqualTo(new[]
        {
            "message invoke",          // v3-42/v3-43: the posted press first, the Invoke only as the reserve
            "message invoke",
            "message legacy pointer",  // no pattern: the posted press, then the ways it always had (never twice)
            "invoke",                  // counter-case: a native Win32 button (class Button, its own window)
            "invoke",                  // counter-case: a XAML or WPF button
            "invoke select message",   // counter-case: a classic row keeps its order
        }));
    }

    [Test]
    public void TheToolbarProxyIsToldByTheControlsMakeNeverByTheApplication()
    {
        // The fact comes from the evidence's identity (42.12650936.4.1 under a ToolBar): framework Win32, the MSAA proxy's
        // RuntimeId and a ToolBar parent; the bar's window and the child come from it. Any of the three missing: no proxy.
        string worker = Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1");
        Assume.That(File.Exists(worker), "the worker script is copied next to the tests");
        string answer = RunWorkerScript(worker, """
            foreach($name in @('Get-ToolbarProxy')){
              $found=@($ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name },$true))
              if($found.Count -ne 1){ throw ('function missing: '+$name) }
              . ([scriptblock]::Create($found[0].Extent.Text))
            }
            function Show($bar){ ([string]$bar.proxy)+'|'+$bar.window+'|'+$bar.child }
            $answers=@(
              (Show (Get-ToolbarProxy 'Win32' ([int[]]@(42,12650936,4,1)) 'ToolBar')),
              (Show (Get-ToolbarProxy 'Win32' ([int[]]@(42,-2,4,3)) 'ToolBar')),
              (Show (Get-ToolbarProxy 'Win32' ([int[]]@(42,12650936,4,1)) 'Pane')),
              (Show (Get-ToolbarProxy 'Win32' ([int[]]@(42,12650936)) 'ToolBar')),
              (Show (Get-ToolbarProxy 'Win32' ([int[]]@(7,1234,5)) 'ToolBar')),
              (Show (Get-ToolbarProxy 'XAML' ([int[]]@(42,12650936,4,1)) 'ToolBar')),
              (Show (Get-ToolbarProxy 'WPF' ([int[]]@(7,99,1,2)) 'ToolBar'))
            )
            [Console]::Out.Write((@($answers) -join ','))
            """);

        Assert.That(answer.Split(','), Is.EqualTo(new[]
        {
            "True|12650936|1",  // v3-42's «Actualizar»: the bar's window and its first child
            "True|4294967294|3", // a window number read back without its sign
            "False|0|0",        // counter-case: not under a ToolBar
            "False|0|0",        // counter-case: a native Win32 button (its own window's identity, 42.<hwnd>)
            "False|0|0",        // counter-case: not the MSAA proxy's identity
            "False|0|0",        // counter-case: a XAML button
            "False|0|0",        // counter-case: a WPF button
        }));
    }

    [Test]
    public void AToolbarButtonsInvokeIsOnlyTheReserveWhenNoBarIsAtItsPoint()
    {
        // The posted press goes only when the bar at the point and its own hit test give this button (ToolbarPress);
        // another window or another button there sends nothing at all (the proxy's Invoke would click what is there with
        // the physical mouse); no bar at the point (none) or no answer from it (nohit): the Invoke, as before. With
        // -PatternsOnly (a point the locator read) the posted press still comes first.
        string worker = Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1");
        Assume.That(File.Exists(worker), "the worker script is copied next to the tests");
        string answer = RunWorkerScript(worker, """
            Add-Type -TypeDefinition @'
            public static class BaxyUiaTimedPress {
              public static int Invoked = 0;
              public static bool InvokeWithin(object element, int milliseconds) { Invoked++; return true; }
            }
            '@
            function Get-ClickFacts($el){ return @{ invoke=$true; select=$false; toggle=$false; expand=$false; kind='Button'; value=$false; classic=$true; toolbarProxy=$true; toolbarWindow=[long]12650936; toolbarChild=1 } }
            $answers=foreach($case in @(@{step='posted';only=$false},@{step='other';only=$false},@{step='none';only=$false},@{step='nohit';only=$false},@{step='posted';only=$true})){
              [BaxyUiaWorkerNative]::BarStep=$case.step
              [BaxyUiaWorkerNative]::BarAsked.Clear()
              [BaxyUiaTimedPress]::Invoked=0
              $el=New-FakeField $false
              $done=$(if($case.only){ Invoke-NamedControl $el ([IntPtr]77) -PatternsOnly } else { Invoke-NamedControl $el ([IntPtr]77) })
              $method=$(if($null -eq $done){ 'null' } else { [string]$done.method })
              $method+'|'+[BaxyUiaTimedPress]::Invoked+'|'+(@([BaxyUiaWorkerNative]::BarAsked) -join ';')
            }
            [Console]::Out.Write((@($answers) -join ','))
            """);

        Assert.That(answer.Split(','), Is.EqualTo(new[]
        {
            "message|0|60:35|12650936.1", // the bar and its hit test give the button: posted, no Invoke, no cursor
            "null|0|60:35|12650936.1",    // another window or button at the point: nothing is sent
            "invoke|1|60:35|12650936.1",  // no bar at the point: the Invoke, as before
            "invoke|1|60:35|12650936.1",  // the bar did not answer its hit test: the Invoke, as before
            "message|0|60:35|12650936.1", // -PatternsOnly keeps the posted press
        }));
    }

    [Test]
    public void ARowWhoseInvokeActedAloneGetsNoOtherWay()
    {
        // Review r2 (finding 3): the chain invoke → select → message runs on a row the press must choose; an Invoke that
        // did something of its own (the row left the view, a modal dialog disabled its window, its window's title
        // changed: a file opened, a track played) is the receipt, and no other way presses the row again. Counter-case
        // (v3-52, a Qt row Invoke did not make current, nothing else moved): Select next.
        string worker = Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1");
        Assume.That(File.Exists(worker), "the worker script is copied next to the tests");
        string answer = RunWorkerScript(worker, """
            foreach($name in @('Test-InvokeActedAlone')){
              $found=@($ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name },$true))
              if($found.Count -ne 1){ throw ('function missing: '+$name) }
              . ([scriptblock]::Create($found[0].Extent.Text))
            }
            Add-Type -TypeDefinition @'
            public static class BaxyUiaTimedPress {
              public static int Invoked = 0;
              public static bool InvokeWithin(object element, int milliseconds) { Invoked++; return true; }
            }
            '@
            function Get-ClickFacts($el){ return @{ invoke=$true; select=$true; toggle=$false; expand=$false; kind='ListItem'; value=$false; classic=$true } }
            function Test-Selected($el){ return $false }
            function Wait-Chosen($el){ return $false }
            $script:Traces=@()
            function Get-InvokeTrace($el,[IntPtr]$top){ $next=$script:Traces[0]; $script:Traces=@($script:Traces | Select-Object -Skip 1); return $next }
            $still=@{ present=$true; enabled=$true; title='Ajustes' }
            $answers=foreach($after in @(@{ present=$false; enabled=$true; title='Ajustes' }, @{ present=$true; enabled=$false; title='Ajustes' }, @{ present=$true; enabled=$true; title='informe.pdf - Ajustes' }, $still)){
              $script:Traces=@($still,$after)
              $calls=@{ select=0 }
              $current=New-Object psobject -Property @{ NativeWindowHandle=0 }
              $el=New-Object psobject -Property @{ Current=$current; Calls=$calls }
              $el | Add-Member -MemberType ScriptMethod -Name TryGetCurrentPattern -Value { param($which,$into) $this.Calls.select++; return $false }
              $done=Invoke-NamedControl $el ([IntPtr]77) -PatternsOnly
              ([string]$done.method)+'|'+$calls.select
            }
            [Console]::Out.Write((@($answers) -join ','))
            """);

        Assert.That(answer.Split(','), Is.EqualTo(new[]
        {
            "invoke|0", // the row left the view: Invoke acted, nothing else is tried
            "invoke|0", // a modal dialog disabled its window
            "invoke|0", // its window's title changed (what the row names opened)
            "invoke|1", // counter-case: nothing moved, Select is tried next
        }));
    }

    [Test]
    public void AFieldIsTheTextsDestinationOnlyWithTheKeyboardsFocusAndNeverFocusedBehind()
    {
        // Review of fix 2: «target» counts only when the field took the keyboard's focus, and the focus is asked only
        // while its window is in front (the managed client's SetFocus brings a covered window forward: a theft).
        // Otherwise the next way is tried; here, with no default action and no classic window, the pointer. r25 review
        // (finding 2): behind, a field is never designated without focus (that would be a click held with no effect).
        string worker = Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1");
        Assume.That(File.Exists(worker), "the worker script is copied next to the tests");
        string answer = RunWorkerScript(worker, """
            $answers=foreach($case in @(@{front=$true;takes=$true},@{front=$true;takes=$false},@{front=$false;takes=$true},@{front=$false;takes=$false})){
              $script:InFront=$case.front
              $el=New-FakeField $case.takes
              $done=Invoke-NamedControl $el ([IntPtr]77)
              ([string]$done.method)+'|'+$el.Calls.focus+'|'+([string]$done.via)+'|'+([string]$done.focused)
            }
            [Console]::Out.Write((@($answers) -join ','))
            """);

        Assert.That(answer.Split(','), Is.EqualTo(new[]
        {
            "target|1||True", // in front and focused: designated
            "pointer|1||",    // counter-case: the focus did not take, so it is not a destination
            "pointer|0||",    // behind: never focused (no theft), never designated, the next way
            "pointer|0||",    // behind, whatever the field would do with a focus nobody asks for
        }));
    }

    [Test]
    public void APointIsPressedOnlyThroughAControlTheLabelNames()
    {
        // Review of fix 2: «at» chose the smallest control with a pattern holding the point, whatever its name (in a
        // web view, a control under a modal layer, or a row whose text the locator did not read). Now only a control
        // whose name, or the text inside it, is the label is a candidate; the innermost first, none over the limit.
        string worker = Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1");
        Assume.That(File.Exists(worker), "the worker script is copied next to the tests");
        string answer = RunWorkerScript(worker, """
            function Pick($entries,$aliases){ (@(Select-PointHolders $entries ([string[]]$aliases) 1000) -join ' ') }
            $answers=@(
              (Pick @(@{names=@('Tienda');area=40},@{names=@('','Biblioteca');area=200},@{names=@('Biblioteca');area=5000}) @('Biblioteca','Library')),
              (Pick @(@{names=@('Ir a la biblioteca');area=40},@{names=@('Biblioteca');area=90}) @('Biblioteca')),
              (Pick @(@{names=@('Library');area=60}) @('Biblioteca','Library')),
              (Pick @(@{names=@('Tienda');area=40},@{names=@('Inicio','Tienda');area=300}) @('Biblioteca')),
              (Pick @(@{names=@('Biblioteca');area=0}) @('Biblioteca'))
            )
            [Console]::Out.Write((@($answers) -join ','))
            """);

        Assert.That(answer.Split(','), Is.EqualTo(new[]
        {
            "1",   // the control whose text inside is the label; not the unnamed-by-label inner one, not one too large
            "0 1", // the label as whole words of a longer name counts too, innermost first
            "0",   // a bilingual alias
            "",    // counter-case: nothing there names the label, so nothing is pressed without the mouse
            "",    // a control with no area is no holder of the point
        }));
    }

    [Test]
    public void APointOnTheControlTheTreeAlreadyPressedIsNotPressedAgain()
    {
        // Review of lat-apertura-clic (finding 4): after the tree pressed a control and saw nothing change, a later
        // stage's point is refused when that control (or an ancestor that is it) holds the point; another control with
        // the same name (a hidden duplicate the tree chose, the visible one here) is still pressed.
        string worker = Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1");
        Assume.That(File.Exists(worker), "the worker script is copied next to the tests");
        string answer = RunWorkerScript(worker, """
            $answers=@(
              (Test-HoldsPressed @('42.7','1.2.3','42') '1.2.3'),
              (Test-HoldsPressed @('42.7','42') '1.2.3'),
              (Test-HoldsPressed @('42.7','') ''),
              (Test-HoldsPressed @() '1.2.3')
            )
            [Console]::Out.Write((@($answers) -join ','))
            """);
        string script = File.ReadAllText(worker, Encoding.UTF8);
        int at = script.IndexOf("function Do-At(", StringComparison.Ordinal);

        Assert.Multiple(() =>
        {
            Assert.That(answer.Split(','), Is.EqualTo(new[] { "True", "False", "False", "False" }));
            Assert.That(script.IndexOf("Test-HoldsPressed @($entries", at, StringComparison.Ordinal),
                Is.GreaterThan(at).And.LessThan(script.IndexOf("Select-PointHolders $entries", at, StringComparison.Ordinal)),
                "refused before any control at the point is chosen (neither its way nor the pointer)");
        });
    }

    [Test]
    public void TheWorkerNeverMovesTheCursorItself()
    {
        string worker = Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1");
        Assume.That(File.Exists(worker), "the worker script is copied next to the tests");
        string script = File.ReadAllText(worker, Encoding.UTF8);
        Assert.Multiple(() =>
        {
            Assert.That(script, Does.Not.Contain("ClickPoint"));
            Assert.That(script, Does.Not.Contain("SetCursorPos"));
            Assert.That(script, Does.Not.Contain("mouse_event"));
            // The worker takes SendInput out of the UI Automation client's imports (UiaQuietInputTests). Its own only
            // input is the front keeper's bid: one key-only INPUT of its hotkey, with BAXY's mark, which the system takes
            // as the hotkey and never delivers to a window (UiaSinFrenteLiveCheck logs what the person's window gets).
            Assert.That(Regex.Matches(script, @"extern\s+\S+\s+SendInput\s*\(").Count, Is.EqualTo(1));
            Assert.That(script, Does.Contain("SendInput(uint count, BidInput[] inputs"));
            Assert.That(Regex.Matches(script, @"[^.\w]SendInput\(1, keys,").Count, Is.EqualTo(1));
            Assert.That(Regex.Matches(script, @"[^.\w\x22]SendInput\(").Count, Is.EqualTo(2), "the declaration and the bid");
            Assert.That(script, Does.Contain("keys[0].Type = 1;").And.Contain("keys[0].Extra = new IntPtr(0x42415859)"));
            Assert.That(script, Does.Not.Contain("keybd_event"));
            Assert.That(script, Does.Contain("visible_click_needs_pointer"));
        });
    }

    [TestCase("invoke")]
    [TestCase("select")]
    [TestCase("toggle")]
    [TestCase("expand")]
    [TestCase("legacy")]
    [TestCase("message")]
    public async Task APressWithoutTheMouseCarriesItsMethodToTheReceipt(string method)
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(
            Pending("Aceptar", method),
            "{\"version\":2,\"ok\":true,\"effectObserved\":true,\"error\":\"\",\"name\":\"Aceptar\"," +
            "\"controlIdentity\":\"1.2.3\",\"absentOrDisabled\":true,\"selected\":false,\"toggled\":false," +
            "\"surfaceChanged\":false,\"cascadeStage\":\"uia\",\"method\":\"" + method + "\"}");
        var pointer = new RecordingPointer(ready: true);
        var adapter = new WindowsVisibleControlAdapter(worker, null, null, pointer: pointer);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"aceptar"}"""), CancellationToken.None);
        Assume.That(receipt.ErrorCode, Is.Not.EqualTo("active_window_not_found"), "a window is in front");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("method").GetString(), Is.EqualTo(method));
            Assert.That(pointer.Prepared, Is.Zero, "a press without the mouse never asks for the pointer");
            Assert.That(pointer.Clicks, Is.Empty);
        });
    }

    // Review of fable/cu-v3-recibo-del-clic-por-estado (finding 1): the worker's post-read answers a field that took the
    // focus (a ComboBox opened by «expand», v3-42) or the modal dialog the press opened (v3-51) as done, each under its own
    // key. The adapter took neither as proof: «visible_click_postread_invalid», and OCR or vision could press the same
    // label again. Now each is the receipt, at the first post-read, and nothing else is asked or pressed.
    [TestCase("fieldTook")]
    [TestCase("dialogOpened")]
    public async Task TheWorkersFieldAndDialogProofsAreTheReceipt(string proof)
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(
            Pending("Idioma", "expand"),
            "{\"version\":2,\"ok\":true,\"effectObserved\":true,\"error\":\"\",\"name\":\"Idioma\",\"kind\":\"ComboBox\"," +
            "\"controlIdentity\":\"1.2.3\",\"absentOrDisabled\":false,\"selected\":false,\"toggled\":false," +
            "\"surfaceChanged\":false,\"cascadeStage\":\"uia\",\"method\":\"expand\",\"" + proof + "\":true}");
        var pointer = new RecordingPointer(ready: true);
        var adapter = new WindowsVisibleControlAdapter(worker, null, null, pointer: pointer);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"idioma"}"""), CancellationToken.None);
        Assume.That(receipt.ErrorCode, Is.Not.EqualTo("active_window_not_found"), "a window is in front");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.Null, "before: visible_click_postread_invalid");
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty(proof).GetBoolean(), Is.True);
            Assert.That(worker.Commands.Count(command => command.Contains("\"cmd\":\"click\"")), Is.EqualTo(1),
                "pressed once");
            Assert.That(pointer.Clicks, Is.Empty);
        });
    }

    [Test]
    public void AFieldThatTookOrADialogHoldsAndAFocusAloneDoesNot()
    {
        Assert.Multiple(() =>
        {
            Assert.That(WindowsVisibleControlAdapter.PostreadHolds(Json(
                "{\"ok\":true,\"effectObserved\":true,\"fieldTook\":true,\"method\":\"expand\"}")), Is.True);
            Assert.That(WindowsVisibleControlAdapter.PostreadHolds(Json(
                "{\"ok\":true,\"effectObserved\":true,\"dialogOpened\":true,\"method\":\"invoke\"}")), Is.True);
            // Counter-case: «focused» alone is a designation's half, never a press's proof.
            Assert.That(WindowsVisibleControlAdapter.PostreadHolds(Json(
                "{\"ok\":true,\"effectObserved\":true,\"focused\":true,\"method\":\"invoke\"}")), Is.False);
            // r25 review (finding 2): a designation without the keyboard's focus is no click held, behind or in front.
            Assert.That(WindowsVisibleControlAdapter.PostreadHolds(Json(
                "{\"ok\":true,\"effectObserved\":true,\"targeted\":true,\"focused\":false,\"via\":\"behind\",\"method\":\"target\"}")), Is.False);
            Assert.That(WindowsVisibleControlAdapter.PostreadHolds(Json(
                "{\"ok\":true,\"effectObserved\":true,\"targeted\":true,\"focused\":false,\"method\":\"target\"}")), Is.False);
            Assert.That(WindowsVisibleControlAdapter.PostreadHolds(Json(
                "{\"ok\":true,\"effectObserved\":true,\"via\":\"behind\",\"method\":\"pointer\"}")), Is.False);
            Assert.That(WindowsVisibleControlAdapter.PostreadHolds(Json(
                "{\"ok\":true,\"effectObserved\":true,\"fieldTook\":false,\"dialogOpened\":false}")), Is.False);
        });
    }

    // Review of the branch, findings 2 and 7, on the worker's own text: a row's posted press goes only to the window
    // that holds it; opening a tree item never chooses it; the last way (Select) is not waited for.
    [Test]
    public void ARowsPostedPressOnlyReachesItsOwnWindowAndOpeningNeverChooses()
    {
        string worker = Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1");
        Assume.That(File.Exists(worker), "the worker script is copied next to the tests");
        string script = File.ReadAllText(worker, Encoding.UTF8);
        int named = script.IndexOf("function Invoke-NamedControl(", StringComparison.Ordinal);
        string press = script[named..script.IndexOf("\nfunction ", named + 10, StringComparison.Ordinal)];
        int start = script.IndexOf("function Invoke-MannerControl(", StringComparison.Ordinal);
        string manner = script[start..script.IndexOf("\nfunction ", start + 10, StringComparison.Ordinal)];
        int postread = script.IndexOf("function Do-Postread(", StringComparison.Ordinal);
        string read = script[postread..script.IndexOf("\nfunction ", postread + 10, StringComparison.Ordinal)];
        Assert.Multiple(() =>
        {
            Assert.That(script, Does.Contain("holder!=IntPtr.Zero && target==holder && PostPress(target,x,y,false)"));
            Assert.That(press, Does.Contain("if($choosing){ $null -ne $point -and [BaxyUiaWorkerNative]::PostClick($top,$point.x,$point.y,(Get-HolderWindow $el)) }"));
            Assert.That(press, Does.Contain("$methods[-1] -eq 'select' -or (Wait-Chosen $el)"));
            Assert.That(manner, Does.Not.Contain("SelectionItemPattern"), "opening a tree item never chooses it");
            Assert.That(read, Does.Contain("$took.fieldTook=$true").And.Contain("$took.dialogOpened=$true"));
        });
    }

    [Test]
    public async Task AFieldThatTakesTextIsDesignatedNotClicked()
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(
            "{\"version\":2,\"ok\":true,\"effectObserved\":true,\"error\":\"\",\"name\":\"Buscar\",\"kind\":\"Edit\"," +
            "\"controlIdentity\":\"1.2.9\",\"absentOrDisabled\":false,\"selected\":false,\"toggled\":false," +
            "\"surfaceChanged\":false,\"cascadeStage\":\"uia\",\"method\":\"target\",\"targeted\":true,\"focused\":true}");
        var pointer = new RecordingPointer(ready: true);
        var adapter = new WindowsVisibleControlAdapter(worker, null, null, pointer: pointer);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"buscar"}"""), CancellationToken.None);
        Assume.That(receipt.ErrorCode, Is.Not.EqualTo("active_window_not_found"), "a window is in front");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("method").GetString(), Is.EqualTo("target"));
            Assert.That(receipt.Result?.GetProperty("targeted").GetBoolean(), Is.True);
            Assert.That(worker.Commands.Count(command => command.Contains("\"cmd\":\"postread\"")), Is.Zero,
                "a designation answers at once");
            Assert.That(pointer.Clicks, Is.Empty);
        });
    }

    [Test]
    public void AnAnswerThatIsNeitherPressedNorDesignatedDoesNotHold()
    {
        // Counter-case of «targeted»: a receipt with nothing pressed, selected, toggled, changed or designated.
        JsonElement idle = Json(
            "{\"ok\":true,\"effectObserved\":true,\"absentOrDisabled\":false,\"selected\":false,\"toggled\":false," +
            "\"surfaceChanged\":false,\"targeted\":false,\"method\":\"target\"}");
        JsonElement designated = Json(
            "{\"ok\":true,\"effectObserved\":true,\"targeted\":true,\"focused\":true,\"method\":\"target\"}");
        // Review of fix 2: a field designated without the keyboard's focus is no destination (the next typing would go
        // to whatever its window had focused).
        JsonElement unfocused = Json(
            "{\"ok\":true,\"effectObserved\":true,\"targeted\":true,\"focused\":false,\"method\":\"target\"}");

        Assert.Multiple(() =>
        {
            Assert.That(WindowsVisibleControlAdapter.PostreadHolds(idle), Is.False);
            Assert.That(WindowsVisibleControlAdapter.PostreadHolds(designated), Is.True);
            Assert.That(WindowsVisibleControlAdapter.PostreadHolds(unfocused), Is.False);
        });
    }

    // Goal v3 B3 (orders in closed menus): the list a control's arrow opened, or the context menu asked for, read open
    // after the press is the step's proof; an answer that only says the manner was tried is not.
    [Test]
    public void AListOrAMenuReadOpenHoldsAsTheProof()
    {
        Assert.Multiple(() =>
        {
            Assert.That(WindowsVisibleControlAdapter.PostreadHolds(Json(
                "{\"ok\":true,\"effectObserved\":true,\"opened\":true,\"method\":\"expand\",\"manner\":\"open\"}")), Is.True);
            Assert.That(WindowsVisibleControlAdapter.PostreadHolds(Json(
                "{\"ok\":true,\"effectObserved\":true,\"opened\":false,\"method\":\"contextmenu\",\"manner\":\"menu\"}")), Is.False);
            // Ronda 20b, palanca 6 (review finding 1): the list read closed after its collapse; a collapse tried is no proof.
            Assert.That(WindowsVisibleControlAdapter.PostreadHolds(Json(
                "{\"ok\":true,\"effectObserved\":true,\"closed\":true,\"method\":\"collapse\",\"manner\":\"collapse\"}")), Is.True);
            Assert.That(WindowsVisibleControlAdapter.PostreadHolds(Json(
                "{\"ok\":true,\"effectObserved\":true,\"closed\":false,\"method\":\"collapse\",\"manner\":\"collapse\"}")), Is.False);
            Assert.That(WindowsVisibleControlAdapter.PostreadHolds(Json(
                "{\"ok\":true,\"effectObserved\":true,\"closed\":true,\"method\":\"escape\",\"manner\":\"dismiss\"}")), Is.True);
            Assert.That(WindowsVisibleControlAdapter.PostreadHolds(Json(
                "{\"ok\":true,\"effectObserved\":true,\"method\":\"escape\",\"manner\":\"dismiss\"}")), Is.False);
        });
    }

    // Review of B3, findings 2, 6 and 8, on the worker's own text: an arrow already open is no opening (nothing sent,
    // no proof); the classic double click goes only to the window that holds the element; a double click is not proven
    // by the selection its first press leaves; a top-level menu proves the context menu only next to the control.
    [Test]
    public void TheWorkersMannersProveOnlyWhatTheyDid()
    {
        string worker = Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1");
        Assume.That(File.Exists(worker), "the worker script is copied next to the tests");
        string script = File.ReadAllText(worker);
        int start = script.IndexOf("function Invoke-MannerControl(", StringComparison.Ordinal);
        string manner = script[start..script.IndexOf("\nfunction ", start + 10, StringComparison.Ordinal)];
        int postread = script.IndexOf("function Do-Postread(", StringComparison.Ordinal);
        string read = script[postread..script.IndexOf("\nfunction ", postread + 10, StringComparison.Ordinal)];
        int menus = script.IndexOf("function Get-OpenMenus(", StringComparison.Ordinal);
        string open = script[menus..script.IndexOf("\nfunction ", menus + 10, StringComparison.Ordinal)];
        Assert.Multiple(() =>
        {
            Assert.That(manner.IndexOf("visible_control_already_open", StringComparison.Ordinal),
                Is.GreaterThan(0).And.LessThan(manner.IndexOf("$ec.Expand()", StringComparison.Ordinal)));
            Assert.That(manner.IndexOf("visible_control_already_open", StringComparison.Ordinal),
                Is.LessThan(manner.IndexOf("[BaxyFrontKeeper]::Release()", StringComparison.Ordinal)), "nothing released for nothing");
            Assert.That(manner, Does.Contain("PostDoubleClick($top,$point.x,$point.y,(Get-HolderWindow $el))"));
            Assert.That(script, Does.Contain("target!=IntPtr.Zero && target==holder && PostPress(target,x,y,true)"));
            Assert.That(read.IndexOf("[string]$pending.manner -eq 'double'", StringComparison.Ordinal),
                Is.GreaterThan(0).And.LessThan(read.IndexOf("Test-Selected $button", StringComparison.Ordinal)));
            Assert.That(open, Does.Contain("$r.Right+64 -ge $box.Left"));
            // Ronda 20b, palanca 6 (review finding 1): a list no longer open is not touched, the collapse never releases
            // the net (the front goes back to the person after it) and its pattern counts as an act for that net.
            // Review 2 (finding 3): ExpandCollapse only on what is read expanded; otherwise Escape is posted only to a
            // popup read open beside the control, never to the mission's window or its root, and nothing is sent
            // without one.
            // Review 3 (finding 1): the list's collapse and the popup's dismiss are apart: the collapse never folds a tree
            // branch (TreeItem refused before any Collapse) and the dismiss never touches the control's ExpandCollapse.
            int collapse = manner.IndexOf("$manner -eq 'collapse'", StringComparison.Ordinal);
            int dismiss = manner.IndexOf("$manner -eq 'dismiss'", StringComparison.Ordinal);
            Assert.That(dismiss, Is.GreaterThan(collapse));
            string collapsing = manner[collapse..dismiss];
            string dismissing = manner[dismiss..manner.IndexOf("$point=Get-PressPoint", dismiss, StringComparison.Ordinal)];
            Assert.That(collapsing.IndexOf("ControlType]::TreeItem", StringComparison.Ordinal),
                Is.GreaterThan(0).And.LessThan(collapsing.IndexOf("$ec.Collapse()", StringComparison.Ordinal)));
            Assert.That(collapsing.IndexOf("ExpandCollapseState -ne $expanded){ return @{ error='visible_control_not_open' }", StringComparison.Ordinal),
                Is.GreaterThan(0).And.LessThan(collapsing.IndexOf("$ec.Collapse()", StringComparison.Ordinal)));
            Assert.That(collapsing, Does.Not.Contain("PostEscape"));
            Assert.That(dismissing, Does.Not.Contain("ExpandCollapse"));
            Assert.That(dismissing.IndexOf("visible_control_not_open", StringComparison.Ordinal),
                Is.GreaterThan(0).And.LessThan(dismissing.IndexOf("::PostEscape(", StringComparison.Ordinal)));
            Assert.That(collapsing + dismissing, Does.Not.Contain("[BaxyFrontKeeper]::Release()"));
            Assert.That(dismissing, Does.Contain("method='escape'; closed=$true"));
            int born = script.IndexOf("function Get-BornPopups(", StringComparison.Ordinal);
            string popups = script[born..script.IndexOf("\nfunction ", born + 10, StringComparison.Ordinal)];
            Assert.That(popups, Does.Contain("$holder -eq $top -or $holder -eq $frame"));
            Assert.That(popups, Does.Contain("$r.Right+64 -ge $box.Left"));
            Assert.That(script, Does.Contain("'render','collapse','escape')"));
            Assert.That(WindowsVisibleControlAdapter.PostreadHolds(Json(
                "{\"ok\":false,\"effectObserved\":false,\"error\":\"visible_control_already_open\",\"manner\":\"open\"}")), Is.False);
        });
    }

    [Test]
    public async Task AControlOpenedByItsArrowGoesToTheWorkerByItsIdentityWithTheManner()
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(
            "{\"version\":2,\"ok\":true,\"effectObserved\":true,\"error\":\"\",\"name\":\"Nueva pestaña\"," +
            "\"kind\":\"SplitButton\",\"controlIdentity\":\"1.2.3\",\"absentOrDisabled\":false,\"selected\":false," +
            "\"toggled\":false,\"surfaceChanged\":false,\"cascadeStage\":\"uia\",\"method\":\"expand\",\"opened\":true," +
            "\"manner\":\"open\"}");
        var pointer = new RecordingPointer(ready: true);
        var adapter = new WindowsVisibleControlAdapter(worker, null, null, pointer: pointer);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"Nueva pestaña","controlId":"1.2.3","manner":"open"}"""), CancellationToken.None);
        Assume.That(receipt.ErrorCode, Is.Not.EqualTo("active_window_not_found"), "a window is in front");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(worker.Commands.Single(command => command.Contains("\"cmd\":\"click\"")),
                Does.Contain("\"manner\":\"open\"").And.Contain("\"controlId\":\"1.2.3\""));
            Assert.That(pointer.Clicks, Is.Empty, "never the pointer");
        });
    }

    // Counter-case: a manner with no identity of the view (a label alone) presses nothing: the label's cascade (OCR,
    // vision, pointer) would be the ordinary click the manner exists to avoid.
    [Test]
    public async Task AMannerWithoutTheViewsIdentityPressesNothing()
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker();
        var adapter = new WindowsVisibleControlAdapter(worker, null, null);

        ExternalCapabilityReceipt menu = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"Windows PowerShell","manner":"menu"}"""), CancellationToken.None);
        ExternalCapabilityReceipt unknown = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"Windows PowerShell","controlId":"1.2.3","manner":"right"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(menu.ErrorCode, Is.EqualTo("visible_control_identity_stale"));
            Assert.That(menu.EffectMayHaveOccurred, Is.False);
            Assert.That(unknown.ErrorCode, Is.EqualTo("visible_click_argument_invalid"));
            Assert.That(worker.Commands, Is.Empty);
        });
    }

    // Revisión 1 de la ronda 21 (hallazgo 2): a choose with no search names no search result; never dropped while the
    // control is pressed by its own action (the split button «Nueva pestaña» opening another tab, v3-37), in no manner.
    // The search burst that carries both (search and choose) is the one that reads choose (SearchBurstTests).
    [Test]
    public async Task AChooseWithoutASearchPressesNothing()
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker();
        var adapter = new WindowsVisibleControlAdapter(worker, null, null);

        ExternalCapabilityReceipt chosen = await adapter.InvokeAsync(
            "input.visible.click",
            Json("""{"label":"Nueva pestaña","controlId":"1.2.3","choose":"Símbolo del sistema"}"""),
            CancellationToken.None);
        ExternalCapabilityReceipt opened = await adapter.InvokeAsync(
            "input.visible.click",
            Json("""{"label":"Nueva pestaña","controlId":"1.2.3","manner":"open","choose":"Símbolo del sistema"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(chosen.ErrorCode, Is.EqualTo("visible_click_argument_invalid"));
            Assert.That(chosen.EffectMayHaveOccurred, Is.False);
            Assert.That(opened.ErrorCode, Is.EqualTo("visible_click_argument_invalid"));
            Assert.That(worker.Commands, Is.Empty, "nothing pressed");
        });
    }

    [Test]
    public async Task AControlWithoutAnyWayNeedsThePointerWhichPressesItsPoint()
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(
            "{\"version\":2,\"ok\":false,\"effectObserved\":false,\"error\":\"visible_click_needs_pointer\"," +
            "\"name\":\"Servidor\",\"kind\":\"ListItem\",\"controlIdentity\":\"1.2.7\",\"absentOrDisabled\":false," +
            "\"selected\":false,\"toggled\":false,\"surfaceChanged\":false,\"cascadeStage\":\"uia\",\"pending\":false," +
            "\"method\":\"pointer\",\"needsPointer\":true,\"point\":{\"x\":120,\"y\":340}," +
            "\"rect\":{\"x\":100,\"y\":320,\"w\":40,\"h\":40}}",
            "{\"version\":2,\"ok\":true,\"effectObserved\":true,\"error\":\"\",\"name\":\"Servidor\"," +
            "\"controlIdentity\":\"1.2.7\",\"absentOrDisabled\":false,\"selected\":true,\"toggled\":false," +
            "\"surfaceChanged\":false,\"cascadeStage\":\"uia\",\"method\":\"pointer\"}");
        var pointer = new RecordingPointer(ready: true);
        var adapter = new WindowsVisibleControlAdapter(worker, null, null, pointer: pointer);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"servidor"}"""), CancellationToken.None);
        Assume.That(receipt.ErrorCode, Is.Not.EqualTo("active_window_not_found"), "a window is in front");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("method").GetString(), Is.EqualTo("pointer"));
            Assert.That(pointer.Prepared, Is.EqualTo(1));
            Assert.That(pointer.Clicks, Is.EqualTo(new[] { (120, 340) }));
            Assert.That(worker.Commands[^1], Does.Contain("\"cmd\":\"postread\""), "the pointer's press is post-read");
            // r4a M3: given back right after the press (the post-read reads the window behind); the restore after the
            // post-read only confirms it.
            Assert.That(pointer.Bursts.Single().Restores, Is.GreaterThanOrEqualTo(1), "front and cursor given back");
        });
    }

    [Test]
    public async Task ThePointerThatMayNotPressNowLeavesNothingPressed()
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(
            "{\"version\":2,\"ok\":false,\"effectObserved\":false,\"error\":\"visible_click_needs_pointer\"," +
            "\"name\":\"Servidor\",\"kind\":\"ListItem\",\"controlIdentity\":\"1.2.7\",\"absentOrDisabled\":false," +
            "\"pending\":false,\"method\":\"pointer\",\"needsPointer\":true,\"point\":{\"x\":120,\"y\":340}}");
        var pointer = new RecordingPointer(ready: false);
        var adapter = new WindowsVisibleControlAdapter(worker, null, null, pointer: pointer);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"servidor"}"""), CancellationToken.None);
        Assume.That(receipt.ErrorCode, Is.Not.EqualTo("active_window_not_found"), "a window is in front");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("input_window_not_in_front"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(pointer.Clicks, Is.Empty);
        });
    }

    [Test]
    public async Task APointALocatorReadIsPressedThroughTheControlThatHoldsIt()
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(Pending("Biblioteca", "select"));
        var adapter = new WindowsVisibleControlAdapter(worker, null, null);

        PointPressed pressed = await adapter.PressAtAsync(0x1234, 640, 380, "biblioteca", CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(pressed, Is.EqualTo(new PointPressed(PointPressOutcome.Pressed, "select", "Biblioteca", "ListItem")));
            Assert.That(worker.Commands, Has.Count.EqualTo(1));
            Assert.That(worker.Commands[0], Does.Contain("\"cmd\":\"at\""));
            Assert.That(worker.Commands[0], Does.Contain("\"x\":640"));
            Assert.That(worker.Commands[0], Does.Contain("\"y\":380"));
            Assert.That(worker.Commands[0], Does.Contain("\"aliases\":[\"Biblioteca\",\"Library\",\"biblioteca\"]"),
                "the worker is told the label the locator read, to press only a control that it names");
        });
    }

    [TestCase("{\"version\":2,\"ok\":false,\"effectObserved\":false,\"error\":\"visible_point_no_pattern\"}")]
    [TestCase("{\"version\":2,\"ok\":false,\"effectObserved\":false,\"error\":\"visible_click_needs_pointer\"," +
              "\"pending\":false,\"method\":\"pointer\",\"needsPointer\":true,\"point\":{\"x\":1,\"y\":1}}")]
    public async Task OnlyTheWorkersAnswerThatNothingThereHasAWayLeavesThePointerToTheLocator(string answer)
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(answer);
        var adapter = new WindowsVisibleControlAdapter(worker, null, null);

        PointPressed pressed = await adapter.PressAtAsync(0x1234, 10, 10, "Servidor", CancellationToken.None);

        Assert.That(pressed.Outcome, Is.EqualTo(PointPressOutcome.NothingThere));
    }

    // Review of fix 2: a silence (the worker killed at its budget while an Invoke opened a modal dialog), an error
    // after the press began, an answer from another way or a field without the keyboard's focus: the control may
    // have been pressed, so the pointer never presses the point again.
    [TestCase(null)]
    [TestCase("{\"version\":2,\"ok\":false,\"effectObserved\":false,\"error\":\"visible_button_not_invokable\"}")]
    [TestCase("{\"ok\":false,\"error\":\"visible_controls_uia_failed\",\"detail\":\"x\"}")]
    [TestCase("{\"version\":2,\"ok\":false,\"effectObserved\":true,\"error\":\"visible_button_postread_pending\"," +
              "\"pending\":true,\"method\":\"legacy\"}")]
    [TestCase("{\"version\":2,\"ok\":true,\"effectObserved\":true,\"error\":\"\",\"method\":\"target\"," +
              "\"targeted\":true,\"focused\":false}")]
    public async Task AnUnconfirmedPressAtAPointIsNeverPressedAgainByThePointer(string? answer)
    {
        var worker = answer is null
            ? new ComputerUsePerceptionTests.ScriptedUiaWorker(answers: [])
            : new ComputerUsePerceptionTests.ScriptedUiaWorker(answer);
        var pointer = new RecordingPointer(ready: true);
        var adapter = new WindowsVisibleControlAdapter(worker, null, null, pointer: pointer);

        LocatedPointPress.Outcome outcome = await LocatedPointPress.PressAsync(
            adapter, "input.visible.click", 0x1234, 10, 10, "Aceptar", CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Failure?.ErrorCode, Is.EqualTo("visible_point_press_unconfirmed"));
            Assert.That(outcome.Failure?.EffectMayHaveOccurred, Is.True);
            Assert.That(pointer.Prepared, Is.Zero);
            Assert.That(pointer.Clicks, Is.Empty);
        });
    }

    [Test]
    public async Task ALocatorsPointerKeepsThePointersGuard()
    {
        // Review of fix 2: OCR and vision no longer move the cursor by themselves. Nothing with a way at the point,
        // and the pointer may not press now (the window left the front, or the point is outside it): nothing pressed.
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(
            "{\"version\":2,\"ok\":false,\"effectObserved\":false,\"error\":\"visible_point_no_pattern\"}");
        var pointer = new RecordingPointer(ready: false);
        var adapter = new WindowsVisibleControlAdapter(worker, null, null, pointer: pointer);

        LocatedPointPress.Outcome outcome = await LocatedPointPress.PressAsync(
            adapter, "input.visible.click", 0x1234, 10, 10, "Servidor", CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Failure?.ErrorCode, Is.EqualTo("input_window_not_in_front"));
            Assert.That(outcome.Failure?.EffectMayHaveOccurred, Is.False);
            Assert.That(pointer.Prepared, Is.EqualTo(1));
            Assert.That(pointer.Clicks, Is.Empty);
            Assert.That(pointer.Bursts.Single().Restores, Is.EqualTo(1), "the burst it took is given back");
        });
    }

    [Test]
    public async Task ALocatorsPointerPressesThePointWhenItMay()
    {
        // Counter-case: with the guard passed, the point is pressed by the pointer and the receipt says so.
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(
            "{\"version\":2,\"ok\":false,\"effectObserved\":false,\"error\":\"visible_point_no_pattern\"}");
        var pointer = new RecordingPointer(ready: true);
        var adapter = new WindowsVisibleControlAdapter(worker, null, null, pointer: pointer);

        LocatedPointPress.Outcome outcome = await LocatedPointPress.PressAsync(
            adapter, "input.visible.click", 0x1234, 30, 40, "Servidor", CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Failure, Is.Null);
            Assert.That(outcome.Method, Is.EqualTo("pointer"));
            Assert.That(pointer.Clicks, Is.EqualTo(new[] { (30, 40) }));
            Assert.That(outcome.Burst, Is.SameAs(pointer.Bursts.Single()), "the caller reads the burst's UserActed");
            // r4a M3: given back right after the press, before the caller's post-read (it used to stay in front).
            Assert.That(pointer.Bursts.Single().Restores, Is.EqualTo(1));
        });
    }

    [Test]
    public async Task APressWithoutTheMouseAtAPointNeverAsksThePointer()
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(Pending("Biblioteca", "invoke"));
        var pointer = new RecordingPointer(ready: true);
        var adapter = new WindowsVisibleControlAdapter(worker, null, null, pointer: pointer);

        LocatedPointPress.Outcome outcome = await LocatedPointPress.PressAsync(
            adapter, "input.visible.click", 0x1234, 30, 40, "Biblioteca", CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Failure, Is.Null);
            Assert.That(outcome.Method, Is.EqualTo("invoke"));
            Assert.That(pointer.Prepared, Is.Zero);
            Assert.That(pointer.Clicks, Is.Empty);
        });
    }

    [Test]
    public async Task APointOnNoWindowAsksTheWorkerNothing()
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(Pending("Biblioteca", "invoke"));
        var adapter = new WindowsVisibleControlAdapter(worker, null, null);

        PointPressed pressed = await adapter.PressAtAsync(0, 10, 10, "Biblioteca", CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(pressed.Outcome, Is.EqualTo(PointPressOutcome.NothingThere));
            Assert.That(worker.Commands, Is.Empty);
        });
    }

    [Test]
    public void AStaleIdentityLooksForItsLabelOnlyOnTheViewsWindowEvenWhenItIsBehind()
    {
        // Review of fix 2: the click by identity no longer brings the view's window forward. When the identity went
        // stale, the cascade by label must stay on that window (behind, here: an off-screen window that takes no
        // activation) and never read or press the window the person has in front.
        nint window = CreateWindowEx(0x08000080, "STATIC", "BAXY click fixture", 0x90000000u,
            -31000, -31000, 200, 120, 0, 0, 0, 0);
        Assert.That(window, Is.Not.EqualTo(nint.Zero));
        try
        {
            Assume.That(GetForegroundWindow(), Is.Not.EqualTo(window), "the view's window is behind");
            var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(
                "{\"version\":2,\"ok\":false,\"effectObserved\":false,\"error\":\"visible_control_identity_stale\"," +
                "\"controlIdentity\":\"9.9\"}",
                "{\"version\":2,\"ok\":false,\"effectObserved\":false,\"error\":\"visible_button_not_found\"," +
                "\"name\":\"\",\"controlIdentity\":\"\",\"absentOrDisabled\":false}");
            var ocr = new BoundLocator("ocr");
            var vision = new BoundLocator("vision");
            var pointer = new RecordingPointer(ready: true);
            var adapter = new WindowsVisibleControlAdapter(
                worker, ocr, vision, timing: Quick, pointer: pointer);
            RememberView(adapter, window);

            ExternalCapabilityReceipt receipt = adapter.InvokeAsync(
                    "input.visible.click", Json("""{"label":"Buscar","controlId":"9.9"}"""), CancellationToken.None)
                .AsTask().GetAwaiter().GetResult();

            string bound = "\"hwnd\":" + (long)window;
            Assert.Multiple(() =>
            {
                Assert.That(receipt.Verified, Is.False);
                Assert.That(worker.Commands, Has.Count.GreaterThanOrEqualTo(2));
                Assert.That(worker.Commands, Has.All.Contain(bound), "every look by label is on the view's window");
                Assert.That(ocr.Calls, Is.GreaterThan(0));
                Assert.That(ocr.MayPressSeen.Concat(vision.MayPressSeen), Has.None.True,
                    "OCR and vision run bound to the view's window, which is not in front");
                Assert.That(pointer.Clicks, Is.Empty);
            });
        }
        finally
        {
            _ = DestroyWindow(window);
        }
    }

    [TestCase(true)]
    [TestCase(false)]
    public void AClickOnAnAdministratorsWindowIsRefusedBeforeAnyStageWithItsCause(bool elevated)
    {
        // v3 limits (M3, live v3-21): Task Manager runs as administrator and refuses UI Automation and input from
        // BAXY; the click said «nothing on the screen is called that». Every click route now asks first and answers
        // window_elevated without a look, an OCR, a tooltip or a pointer. Counter-case: a window that is not elevated
        // (Calculator) is clicked as before.
        nint window = CreateWindowEx(0x08000080, "STATIC", "BAXY elevated fixture", 0x90000000u,
            -31000, -31000, 200, 120, 0, 0, 0, 0);
        Assert.That(window, Is.Not.EqualTo(nint.Zero));
        try
        {
            var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(
                "{\"version\":2,\"ok\":false,\"effectObserved\":false,\"error\":\"visible_button_not_found\"," +
                "\"name\":\"\",\"controlIdentity\":\"\",\"absentOrDisabled\":false}");
            var ocr = new BoundLocator("ocr");
            var vision = new BoundLocator("vision");
            var pointer = new RecordingPointer(ready: true);
            var asked = new List<nint>();
            var adapter = new WindowsVisibleControlAdapter(
                worker, ocr, vision, timing: Quick, pointer: pointer,
                elevated: hwnd => { asked.Add(hwnd); return elevated; });

            ExternalCapabilityReceipt receipt = adapter.InvokeAsync(
                    "input.visible.click", Json("{\"label\":\"Details\",\"window\":" + (long)window + "}"),
                    CancellationToken.None)
                .AsTask().GetAwaiter().GetResult();

            Assert.Multiple(() =>
            {
                Assert.That(asked, Has.Member(window), "the click asks about the window it targets");
                Assert.That(pointer.Clicks, Is.Empty);
                if (elevated)
                {
                    Assert.That(receipt.ErrorCode, Is.EqualTo("window_elevated"));
                    Assert.That(receipt.EffectObserved, Is.False);
                    Assert.That(worker.Commands, Is.Empty, "nothing is read or pressed on an administrator's window");
                    Assert.That(ocr.Calls + vision.Calls, Is.Zero);
                }
                else
                {
                    Assert.That(receipt.ErrorCode, Is.EqualTo("visible_button_not_found"));
                    Assert.That(worker.Commands, Is.Not.Empty, "a window that is not elevated is looked at as before");
                }
            });
        }
        finally
        {
            _ = DestroyWindow(window);
        }
    }

    private static readonly VisibleClickTiming Quick = VisibleClickTiming.Default with
    {
        SettledLabel = TimeSpan.FromMilliseconds(60),
        Interval = TimeSpan.FromMilliseconds(20),
    };

    // The last view, as input.visible.controls leaves it, on a window of this test (no look brings anything forward).
    private static void RememberView(WindowsVisibleControlAdapter adapter, nint window)
    {
        FieldInfo field = typeof(WindowsVisibleControlAdapter).GetField(
            "_lastView", BindingFlags.NonPublic | BindingFlags.Instance)!;
        object controls = Activator.CreateInstance(
            typeof(List<>).MakeGenericType(typeof(WindowsVisibleControlAdapter.ViewControl)))!;
        object view = Activator.CreateInstance(
            field.FieldType, BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance, null,
            [window, controls], null)!;
        field.SetValue(adapter, view);
    }

    // A locator that finds nothing and notes whether it could have pressed (the window it is bound to is in front).
    private sealed class BoundLocator(string stage) : IVisibleControlLocator
    {
        internal int Calls { get; private set; }

        internal List<bool> MayPressSeen { get; } = [];

        public string Stage { get; } = stage;

        public ValueTask<ExternalCapabilityReceipt?> TryClickAsync(
            string operation, string label, CancellationToken cancellationToken)
        {
            Calls++;
            MayPressSeen.Add(VisibleControlSurface.MayPress());
            return ValueTask.FromResult<ExternalCapabilityReceipt?>(null);
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

    [DllImport("user32.dll", ExactSpelling = true)]
    private static extern nint GetForegroundWindow();

    private static string Pending(string name, string method) =>
        "{\"version\":2,\"ok\":false,\"effectObserved\":true,\"error\":\"visible_button_postread_pending\"," +
        "\"name\":\"" + name + "\",\"kind\":\"ListItem\",\"controlIdentity\":\"1.2.3\",\"absentOrDisabled\":false," +
        "\"selected\":false,\"toggled\":false,\"surfaceChanged\":false,\"cascadeStage\":\"uia\",\"pending\":true," +
        "\"method\":\"" + method + "\"}";

    // Merge of fable/cu-v3-pausa: the pointer acts inside a burst of the foreground lease (granted here at once), and
    // every burst it took is given back.
    private sealed class RecordingPointer(bool ready) : IPointerFallback
    {
        internal int Prepared { get; private set; }

        internal List<(int X, int Y)> Clicks { get; } = [];

        internal List<FakeInputBurst> Bursts { get; } = [];

        public ValueTask<IInputBurst> AcquireAsync(nint window, CancellationToken cancellationToken)
        {
            var burst = new FakeInputBurst();
            Bursts.Add(burst);
            return ValueTask.FromResult<IInputBurst>(burst);
        }

        public bool Prepare(nint window, int screenX, int screenY)
        {
            Prepared++;
            return ready;
        }

        public ValueTask<VisibleControlSurface.CapturedWindow?> CaptureAsync(
            nint window, CancellationToken cancellationToken) =>
            ValueTask.FromResult<VisibleControlSurface.CapturedWindow?>(null);

        public bool Click(IInputBurst burst, int screenX, int screenY)
        {
            Clicks.Add((screenX, screenY));
            return burst.MayAct;
        }
    }

    // Runs a script over the worker's own click functions (taken by their syntax tree) with described controls and
    // stand-ins for the window in front and the native calls: no window is read or touched.
    private static string RunWorkerScript(string worker, string body)
    {
        string script = """
            $ErrorActionPreference='Stop'
            Add-Type -AssemblyName UIAutomationClient
            Add-Type -AssemblyName UIAutomationTypes
            Add-Type -AssemblyName WindowsBase
            Add-Type -TypeDefinition @'
            using System;
            public static class BaxyUiaWorkerNative {
              public static string LegacyStep = "";
              public static string WindowDefault(IntPtr hwnd) { LegacyStep = "window"; return ""; }
              public static string LegacyDefault(IntPtr top, int[] id) { LegacyStep = "none"; return ""; }
              public static bool PostClick(IntPtr top, int x, int y) { return false; }
              public static bool PostClick(IntPtr top, int x, int y, IntPtr holder) { return false; }
              // The render surface (fable/cu-v3-clic-chromium): absent unless a test says it is there; every press
              // posted to it is recorded with the point (nothing is posted here: no surface).
              public class RenderHit { public string Name = ""; public int Left; public int Top; public int Width; public int Height; public int Role; }
              public static bool Render = false;
              public static System.Collections.Generic.List<string> Posted = new System.Collections.Generic.List<string>();
              public static bool HostsRender(IntPtr[] hosts, uint process) { return Render; }
              public static IntPtr RenderAt(IntPtr[] hosts, int x, int y, uint process) { return Render ? (IntPtr)1 : IntPtr.Zero; }
              public static bool SameDpi(IntPtr surface) { return true; }
              public static RenderHit[] HitChain(IntPtr surface, int x, int y) { return new RenderHit[0]; }
              public static bool PostAt(IntPtr surface, int x, int y) { Posted.Add(x + "," + y); return true; }
              // r20b palanca 4: what the toolbar's press finds at the point (none, other, nohit, posted), and each ask.
              public static string BarStep = "none";
              public static System.Collections.Generic.List<string> BarAsked = new System.Collections.Generic.List<string>();
              public static string ToolbarPress(IntPtr top, int x, int y, IntPtr bar, int child) { BarAsked.Add(x + ":" + y + "|" + bar.ToInt64() + "." + child); return BarStep; }
            }
            '@
            $tokens=$null;$errors=$null
            $ast=[System.Management.Automation.Language.Parser]::ParseFile($env:BAXY_CLICK_WORKER,[ref]$tokens,[ref]$errors)
            if($errors.Count -gt 0){ throw 'worker does not parse' }
            foreach($name in @('Select-ClickMethods','Invoke-NamedControl','Select-Element','Test-PlaceMoved','Get-SteadyPlace','Test-PlaceTooDear','Wait-PlaceMoved','Get-PressPoint','Get-CurrentRect','Test-NameMatch','Get-Folded','Test-NameHolds','Test-NamesLabel','Select-PointHolders','Test-HoldsPressed','Get-RenderHosts','Send-RenderPress','Test-HitIsElement','Test-HitNamesLabel')){
              $found=@($ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name },$true))
              if($found.Count -ne 1){ throw ('function missing: '+$name) }
              . ([scriptblock]::Create($found[0].Extent.Text))
            }
            $script:PatternMethods=@('invoke','select','toggle','expand','target')
            # Review 1 of r24b (B2): every choice of an item reads the place; here the window holds still.
            function Get-PlaceTrace([IntPtr]$top){ return @{ title=''; items=@{}; volatile=@{} } }
            $script:InFront=$false
            function Test-InFront([IntPtr]$top){ return $script:InFront }
            function Get-ClickFacts($el){ return @{ invoke=$false; select=$false; toggle=$false; expand=$false; kind='Edit'; value=$true; classic=$false } }
            function New-FakeField([bool]$takes){
              $calls=@{ focus=0; has=$false }
              $current=New-Object psobject -Property @{ NativeWindowHandle=0; Calls=$calls }
              $current | Add-Member -MemberType ScriptProperty -Name HasKeyboardFocus -Value { $this.Calls.has }
              $current | Add-Member -MemberType NoteProperty -Name BoundingRectangle -Value (New-Object System.Windows.Rect(10,20,100,30))
              $el=New-Object psobject -Property @{ Current=$current; Calls=$calls; Takes=$takes }
              $el | Add-Member -MemberType ScriptMethod -Name SetFocus -Value { $this.Calls.focus++; if($this.Takes){ $this.Calls.has=$true } }
              $el | Add-Member -MemberType ScriptMethod -Name GetRuntimeId -Value { return [int[]]@(42,7) }
              $el | Add-Member -MemberType ScriptMethod -Name GetClickablePoint -Value { return (New-Object System.Windows.Point(60,35)) }
              return $el
            }

            """ + body;
        return RunPowerShell(script, ("BAXY_CLICK_WORKER", worker));
    }

    private static string RunPowerShell(string script, params (string Name, string Value)[] environment)
    {
        var start = new ProcessStartInfo("powershell.exe")
        {
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true,
        };
        foreach (string argument in new[] { "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand" })
        {
            start.ArgumentList.Add(argument);
        }

        start.ArgumentList.Add(Convert.ToBase64String(Encoding.Unicode.GetBytes(script)));
        foreach ((string name, string value) in environment)
        {
            start.Environment[name] = value;
        }

        using Process process = Process.Start(start)!;
        Task<string> error = process.StandardError.ReadToEndAsync();
        string output = process.StandardOutput.ReadToEnd();
        Assert.That(process.WaitForExit(60_000), Is.True, "the script answers");
        Assert.That(process.ExitCode, Is.EqualTo(0), error.Result);
        return output.Trim();
    }

    private static string RunPlanner(string worker, string cases)
    {
        const string script = """
            $ErrorActionPreference='Stop'
            $tokens=$null;$errors=$null
            $ast=[System.Management.Automation.Language.Parser]::ParseFile($env:BAXY_CLICK_WORKER,[ref]$tokens,[ref]$errors)
            if($errors.Count -gt 0){ throw 'worker does not parse' }
            $found=@($ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Select-ClickMethods' },$true))
            if($found.Count -ne 1){ throw 'rule function missing' }
            . ([scriptblock]::Create($found[0].Extent.Text))
            $cases=[System.IO.File]::ReadAllText($env:BAXY_CLICK_CASES,[System.Text.Encoding]::UTF8) | ConvertFrom-Json
            $answers=foreach($case in $cases){
              $facts=@{ invoke=[bool]$case.invoke; select=[bool]$case.select; toggle=[bool]$case.toggle; expand=[bool]$case.expand; kind=[string]$case.kind; value=[bool]$case.value; classic=[bool]$case.classic; render=[bool]$case.render; selected=[bool]$case.selected; toolbarProxy=[bool]$case.toolbarProxy }
              (@(Select-ClickMethods $facts) -join ' ')
            }
            [Console]::Out.Write((@($answers) -join ','))
            """;
        string casesFile = Path.Combine(Path.GetTempPath(), "baxy-click-" + Guid.NewGuid().ToString("N") + ".json");
        File.WriteAllText(casesFile, cases, new UTF8Encoding(false));
        try
        {
            var start = new ProcessStartInfo("powershell.exe")
            {
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false,
                CreateNoWindow = true,
            };
            foreach (string argument in new[] { "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand" })
            {
                start.ArgumentList.Add(argument);
            }

            start.ArgumentList.Add(Convert.ToBase64String(Encoding.Unicode.GetBytes(script)));
            start.Environment["BAXY_CLICK_WORKER"] = worker;
            start.Environment["BAXY_CLICK_CASES"] = casesFile;
            using Process process = Process.Start(start)!;
            Task<string> error = process.StandardError.ReadToEndAsync();
            string output = process.StandardOutput.ReadToEnd();
            Assert.That(process.WaitForExit(60_000), Is.True, "the rule answers");
            Assert.That(process.ExitCode, Is.EqualTo(0), error.Result);
            return output.Trim();
        }
        finally
        {
            File.Delete(casesFile);
        }
    }
}
