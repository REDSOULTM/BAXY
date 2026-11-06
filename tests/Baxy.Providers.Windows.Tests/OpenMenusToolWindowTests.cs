using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// C17 on the worker's own text, with no window: a WPF menu opens as a top-level tool window with the Menu inside it, never
/// as a root child of type Menu (agent-desktop <c>probes/windows/FINDINGS.md</c> A23; <c>menu_state.rs</c>, its second source).
/// The tool windows are stubbed here: whether a real WPF menu has that shape is <see cref="OpenMenusLiveCheck"/>'s to say.
/// </summary>
[TestFixture]
public sealed class OpenMenusToolWindowTests
{
    private const string Setup = """
        $AE=[System.Windows.Automation.AutomationElement]
        $current=New-Object psobject -Property @{ BoundingRectangle=(New-Object System.Windows.Rect 500,300,100,30) }
        $el=New-Object psobject -Property @{ Current=$current }
        $root=New-Object psobject
        $script:Inside=@()
        $root | Add-Member -MemberType ScriptMethod -Name FindAll -Value { param($scope,$condition) return $script:Inside }

        """;

    // A process id no process has: the real root read finds no menu of it.
    private const int NoProcess = 999999;

    [TestCase("510,340,120,60", 1, TestName = "AToolWindowMenuNextToTheControlCounts")]
    [TestCase("1500,900,120,60", 0, TestName = "AToolWindowMenuFarFromTheControlDoesNot")]
    [TestCase("", 0, TestName = "NoToolWindowMenuCountsNothing")]
    public void TheMenusOfToolWindowsCountNextToTheControl(string rectangle, int expected)
    {
        string rects = rectangle.Length == 0 ? "@()" : $"@(New-Object System.Windows.Rect {rectangle})";
        string answer = ComputerUseListenedPressTests.Run(ComputerUseListenedPressTests.Worker(), ["Get-OpenMenus"], Setup + $$"""
            function Get-ToolMenuRects([int]$process,$menu){ return {{rects}} }
            [Console]::Out.Write([string](Get-OpenMenus $root {{NoProcess}} $el))
            """);
        Assert.That(answer, Is.EqualTo(expected.ToString(System.Globalization.CultureInfo.InvariantCulture)));
    }

    // Contracase: the Menu inside the window's own tree (a page's menu) counts as it did.
    [Test]
    public void AMenuInTheWindowsOwnTreeStillCounts()
    {
        string answer = ComputerUseListenedPressTests.Run(ComputerUseListenedPressTests.Worker(), ["Get-OpenMenus"], Setup + $$"""
            function Get-ToolMenuRects([int]$process,$menu){ return @() }
            $script:Inside=@('menu')
            [Console]::Out.Write([string](Get-OpenMenus $root {{NoProcess}} $el))
            """);
        Assert.That(answer, Is.EqualTo("1"));
    }
}
