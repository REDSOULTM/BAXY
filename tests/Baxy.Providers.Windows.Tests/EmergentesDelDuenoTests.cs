using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Ronda 24, palanca «emergentes-del-dueno-y-menus-que-se-reabren»: a menu or a list a window shows is part of its owner.
/// The entry of a popup reopens though the window under it shows a text of the same name (t-menu-3: the status bar's
/// «Zoom»), a chain of presses of one opener keeps the names before its first press (v3-11 t3), and the owner in front
/// holds its popup (t-menu-4).
/// </summary>
[TestFixture]
public sealed class EmergentesDelDuenoTests
{
    private static WindowsVisibleControlAdapter.ViewControl Control(string kind, string name) => new() { Kind = kind, Name = name };

    [Test]
    public void TMenu3TheStatusBarsTextNeverStopsThePopupsEntryFromReopening()
    {
        WindowsVisibleControlAdapter.OpenerNames names = WindowsVisibleControlAdapter.OpenerNames.Of(
            [Control("MenuItem", "Archivo"), Control("MenuItem", "Ver"), Control("Text", "Zoom"), Control("Document", "hello")]);
        Assert.Multiple(() =>
        {
            Assert.That(names, Is.EquivalentTo(new[] { "Archivo", "Ver" }));
            Assert.That(names.Described, Is.EquivalentTo(new[] { "Zoom", "hello" }));
            // The entry «Zoom» of the popup «Ver» opened (5000, died with the activation): reopened.
            Assert.That(WindowsVisibleControlAdapter.ReopensShownItem(
                "visible_control_identity_stale", "Zoom", "77.1", 5000, 4660, "9.1", names, false, [], names.Described), Is.True);
            // Contracase: an item of the opener's own window that the window already showed (its text) never reopens.
            Assert.That(WindowsVisibleControlAdapter.ReopensShownItem(
                "visible_button_not_found", "Zoom", "77.1", 4660, 4660, "9.1", names, true, [], names.Described), Is.False);
            // Contracase: a name a control that acts showed (a fixed entry of the bar) never reopens, in any window.
            Assert.That(WindowsVisibleControlAdapter.ReopensShownItem(
                "visible_button_not_found", "Archivo", "77.1", 5000, 4660, "9.1", names, false, [], names.Described), Is.False);
        });
    }

    [Test]
    public void ANameHeldByAControlThatActsIsNeverOnlyDescribed()
    {
        WindowsVisibleControlAdapter.OpenerNames names = WindowsVisibleControlAdapter.OpenerNames.Of(
            [Control("Text", "Zoom"), Control("Button", "Zoom")]);
        Assert.Multiple(() =>
        {
            Assert.That(names, Does.Contain("Zoom"));
            Assert.That(names.Described, Is.Empty);
        });
    }

    [Test]
    public void V311AChainOfPressesOfOneOpenerKeepsTheNamesBeforeItsFirstPress()
    {
        var first = new WindowsVisibleControlAdapter.OpenerNames(["Inicio", "Insertar"], []);
        var now = new WindowsVisibleControlAdapter.OpenerNames(["Inicio", "Insertar", "Renglones"], []);
        (nint, string, string, HashSet<string>, string?)? noted = (4660, "9.1", "Vista", first, null);
        Assert.Multiple(() =>
        {
            Assert.That(WindowsVisibleControlAdapter.ChainedNames(noted, 4660, "9.1", now), Is.SameAs(first));
            // Contracases: another control pressed, another window, or no opener noted (a click between broke the chain).
            Assert.That(WindowsVisibleControlAdapter.ChainedNames(noted, 4660, "9.2", now), Is.SameAs(now));
            Assert.That(WindowsVisibleControlAdapter.ChainedNames(noted, 4661, "9.1", now), Is.SameAs(now));
            Assert.That(WindowsVisibleControlAdapter.ChainedNames(null, 4660, "9.1", now), Is.SameAs(now));
        });
    }

    [TestCase(5000L, 4660L, 4660L, false, false, 7u, 7u, true, TestName = "TMenu4 the owner in front holds its menu that never activates")]
    [TestCase(5000L, 4660L, 4660L, false, true, 7u, 7u, false, TestName = "a modeless dialog with a title, owner in front, is never held")]
    [TestCase(5000L, 4660L, 9999L, false, false, 7u, 7u, false, TestName = "an owner that is not in front never holds it")]
    [TestCase(5000L, 4660L, 4660L, true, false, 7u, 7u, false, TestName = "a window with its own taskbar button is no popup")]
    [TestCase(5000L, 4660L, 4660L, false, false, 7u, 8u, false, TestName = "a window of another process is never held")]
    [TestCase(4660L, 4660L, 0L, false, false, 7u, 7u, false, TestName = "the window itself is no popup of itself")]
    public void APopupIsHeldByItsOwnerInFront(
        long window, long front, long owner, bool appWindow, bool activates, uint process, uint frontProcess, bool held)
    {
        bool decided = VisibleControlSurface.HeldByItsOwner(
            (nint)window,
            (nint)front,
            hwnd => hwnd == (nint)window ? (nint)owner : 0,
            _ => appWindow,
            _ => activates,
            hwnd => hwnd == (nint)window ? process : frontProcess);

        Assert.That(decided, Is.EqualTo(held));
    }

    // Review 1 of ronda 24 (finding 1): which styles take the activation. WS_POPUP 0x80000000, WS_CAPTION 0x00C00000,
    // WS_BORDER 0x00800000, WS_SYSMENU 0x00080000, WS_EX_NOACTIVATE 0x08000000, WS_EX_TOOLWINDOW 0x80.
    [TestCase(0x80800000L, 0x80L, false, TestName = "a menu or a drop-down list: a pop-up with a border and no title never activates")]
    [TestCase(0x80C80000L, 0x0L, true, TestName = "a modeless find dialog: a pop-up with a title bar activates")]
    [TestCase(0x00CF0000L, 0x0L, true, TestName = "an overlapped window activates")]
    [TestCase(0x80C80000L, 0x08000000L, false, TestName = "a window marked no-activate never activates, title or not")]
    [TestCase(unchecked((long)0xFFFFFFFF80800000UL), 0x0L, false, TestName = "a sign-extended pop-up style without a title never activates")]
    public void TakesActivationReadsTheStyles(long style, long exStyle, bool activates) =>
        Assert.That(VisibleControlSurface.TakesActivation(style, exStyle), Is.EqualTo(activates));
}
