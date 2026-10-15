using System.Text.RegularExpressions;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// r13a, cause 4 (measured: the Event Viewer's view 15-20 s, Services over 40 s, because the worker fetched the whole
/// tree with every property before cutting at 60), and the review of its first fix (a walk node by node: 2-4 times
/// slower on ordinary windows, rows Chromium marks offscreen dropped with their visible buttons, controlCount inflated
/// by hidden and virtual rows, the focus lost behind). The view asks the tree only for what is shown and enabled, a
/// condition UIA evaluates node by node without pruning, so the set and its order are the old one minus what was
/// skipped anyway (measured live: identical listings, counts and focus on Discord, WhatsApp, Settings, VS Code and
/// Edge; VS Code 1 634-1 870 -> 379-439 ms, Edge 417-470 -> 305-337 ms). Only a long list that is a window of its own
/// (a classic Win32 list, whose proxy answers row by row) is read row by row: its shown rows, at most 20 read, the
/// rest shown counted (measured on a classic list of 3 000 rows: over 90 s -> 1.0-1.5 s). Reads the worker script;
/// nothing on the desktop is touched.
/// </summary>
[TestFixture]
public sealed class ComputerUseViewWalkTests
{
    private static string Script()
    {
        string worker = Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1");
        Assume.That(File.Exists(worker), "the worker script is copied next to the tests");
        return File.ReadAllText(worker);
    }

    private static string Function(string script, string name)
    {
        int start = script.IndexOf("function " + name + "(", StringComparison.Ordinal);
        Assert.That(start, Is.GreaterThanOrEqualTo(0), name);
        int end = script.IndexOf("\nfunction ", start + 1, StringComparison.Ordinal);
        return script[start..(end < 0 ? script.Length : end)];
    }

    [Test]
    public void TheViewAsksTheTreeOnlyForWhatIsShown()
    {
        string script = Script();
        string view = Function(script, "Do-View");
        string shown = Function(script, "Get-ShownDescendants");
        Assert.Multiple(() =>
        {
            Assert.That(view, Does.Contain("$all=Get-ShownDescendants $root ([long]$target.hwnd)"));
            Assert.That(view, Does.Not.Contain("$all=Get-Descendants $root"), "the whole tree is what cost 15-40 s");
            Assert.That(script, Does.Match(@"\$script:ShownCondition=New-Object System\.Windows\.Automation\.AndCondition\(@\(\s*" +
                @"\(New-Object System\.Windows\.Automation\.PropertyCondition\(\$AE::IsEnabledProperty,\$true\)\),\s*" +
                @"\(New-Object System\.Windows\.Automation\.PropertyCondition\(\$AE::IsOffscreenProperty,\$false\)\)\)\)"));
            // Ronda 25 (latency): the same walk brings the shown disabled controls only when the view lists them; every
            // other walk keeps the shown-and-enabled condition.
            Assert.That(shown, Does.Contain("FindAll([System.Windows.Automation.TreeScope]::Descendants,(Get-WalkCondition))"));
            Assert.That(shown, Does.Contain("$script:WithDimmed=$dimmed"));
            Assert.That(shown, Does.Contain("[bool]$dimmed=$false"), "a walk brings no disabled control unless asked");
            Assert.That(Function(script, "Add-ShownSubtree"), Does.Contain("FindAll([System.Windows.Automation.TreeScope]::Descendants,(Get-WalkCondition))"));
            Assert.That(Function(script, "Get-WalkCondition"),
                Does.Contain("if($script:WithDimmed){ return $script:OnScreenCondition }; return $script:ShownCondition"));
            Assert.That(script, Does.Contain("$script:OnScreenCondition=New-Object System.Windows.Automation.PropertyCondition($AE::IsOffscreenProperty,$false)"));
            Assert.That(view, Does.Contain("$all=Get-ShownDescendants $root ([long]$target.hwnd) 0 $withDimmed"));
        });
    }

    // Contracase (review finding 1): a condition filters node by node and never prunes, so a shown button under a row
    // Chromium marks offscreen (Discord's «Eventos») still comes; no walk skips a hidden node's children.
    [Test]
    public void AHiddenParentNeverHidesItsShownChildren()
    {
        string script = Script();
        Assert.Multiple(() =>
        {
            Assert.That(script, Does.Not.Contain("function Add-ViewWalk("), "the walk that pruned hidden rows is gone");
            Assert.That(Function(script, "Add-ShownAround"), Does.Contain("elseif($paths.ContainsKey($id) -and $depth -lt 40){ Add-ShownAround"),
                "a child on the way to a long list is opened whether it is shown or not");
            Assert.That(Function(script, "Add-ShownAround"), Does.Contain("else { Add-ShownSubtree $kid $out }"),
                "every other child comes whole, shown or not, through the condition");
        });
    }

    // Contracase (review findings 3 and 4): the count is the distinct shown controls again, never hidden or virtual
    // rows, and the focus is read from the same shown nodes as before (HasKeyboardFocus, also behind the front).
    [Test]
    public void TheCountAndTheFocusMeanWhatTheyMeantBefore()
    {
        string view = Function(Script(), "Do-View");
        Assert.Multiple(() =>
        {
            Assert.That(view, Does.Contain("controlCount=($total+$script:ShownUnread)"));
            Assert.That(view, Does.Not.Contain("omitted"));
            Assert.That(view, Does.Not.Contain("RowCount"));
            Assert.That(view, Does.Contain("if($stateInfo.state -match '\\bfocused\\b' -and $null -eq $focused){ $focused=$entry }"));
            Assert.That(view, Does.Not.Contain("FocusedElement"), "the system focus is another process when the window is behind");
            Assert.That(view, Does.Contain("$near=Get-NearLabel $item $all"), "a field's label among every shown text, before or after it");
        });
    }

    [Test]
    public void OnlyALongListThatIsAWindowOfItsOwnIsReadRowByRow()
    {
        string script = Script();
        string lists = Function(script, "Get-LongLists");
        string rows = Function(script, "Add-ShownRows");
        Assert.Multiple(() =>
        {
            Assert.That(lists, Does.Contain("[BaxyUiaWorkerNative]::VisibleChildWindows([IntPtr]$hwnd,300)"));
            Assert.That(lists, Does.Contain("(Get-RowCount $el) -gt $script:LongList"));
            Assert.That(script, Does.Match(@"\$script:LongList=60\b"));
            Assert.That(script, Does.Match(@"\$script:RowsRead=20\b"));
            Assert.That(int.Parse(Regex.Match(script, @"\$script:RowsSeconds=(\d+)").Groups[1].Value, System.Globalization.CultureInfo.InvariantCulture),
                Is.LessThan(3), "never 3 s without a view");
            // A shown row past the cap is counted, never dropped from controlCount; the first hidden row after the
            // shown ones ends the list, and only a row ends it (a shown header before the rows does not).
            Assert.That(rows, Does.Contain("$rowsRead=$(if($script:AllRows){ [int]::MaxValue } else { $script:RowsRead })"));
            Assert.That(rows, Does.Contain("if($read -ge $rowsRead){ $script:ShownUnread++ }"));
            Assert.That(rows, Does.Contain("} elseif($seen){ break }"));
            Assert.That(rows, Does.Contain("$isRow=$script:RowKinds -contains"));
            // An expanded branch of a tree whose own row scrolled above still shows its children.
            Assert.That(rows, Does.Contain("[System.Windows.Automation.ExpandCollapseState]::Collapsed"));
        });
    }

    // Contracase (review finding 5): nothing shown is either a window that shows nothing (minimized: empty, at once) or
    // one with no tree yet or a dead first child (Opera GX after a new tab): the old path, its second look and its walk.
    [Test]
    public void NothingShownFallsBackToTheOldPathOnlyWhenTheTreeHasNothing()
    {
        string shown = Function(Script(), "Get-ShownDescendants");
        Assert.Multiple(() =>
        {
            Assert.That(shown, Does.Contain("if($null -ne $any){ return $shown }"));
            Assert.That(shown, Does.Contain("return (Get-Descendants $root)"));
        });
    }

    // Contracase: a row deep in a long list, left out of the view, is still found by its label and brought into view.
    [Test]
    public void ARowLeftOutOfTheViewIsStillReachableByLabelAndReveal()
    {
        string script = Script();
        string named = Function(script, "Find-Named");
        string any = Function(script, "Find-AnyNamed");
        string listed = Function(script, "Reveal-Listed");
        Assert.Multiple(() =>
        {
            // Round 21 (c17fa38e6): the label lookup goes through Get-LookupScope, which reads every row of the view (no row
            // cap) and the whole tree when an offscreen box is asked.
            string scope = Function(script, "Get-LookupScope");
            Assert.That(named, Does.Contain("Get-LookupScope $root $offscreenBox"), "the click by label goes through the lookup scope");
            Assert.That(scope, Does.Contain("$script:AllRows=$true"), "the lookup reads every row, never the view's row cap");
            Assert.That(scope, Does.Contain("return (Get-Descendants $root)"), "with an offscreen box it searches the whole tree");
            Assert.That(named, Does.Contain("$item.Cached.IsOffscreen"), "read from the cache, never one call per node");
            Assert.That(named, Does.Not.Contain(".Current.IsOffscreen"));
            Assert.That(any, Does.Contain("Get-Descendants $root"), "the reveal searches the whole tree, shown or not");
            Assert.That(listed, Does.Contain("ScrollIntoView()"));
            Assert.That(Function(script, "Test-ItemHolds"), Does.Contain("$kind=[string]$el.Cached.ControlType.ProgrammaticName"),
                "the cache first; the live value only for an element outside it");
        });
    }
}
