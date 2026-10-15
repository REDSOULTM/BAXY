using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Ronda 20 P6 (pasada r18: v3-15, v3-16, v3-17 t2): after «Editar» an image viewer's WinUI frame
/// (160,160–1600,900) lay above its editor, a WebView2 window of a process it started lying inside it
/// (169,220–1591,891, 89.5 % of it), and the view kept the frame's chrome: Minimize, Maximize, Close, Atrás, the system
/// menu, the non-client input sink, the custom title bar, the title text and the busy indicator «Ocupado». A frame
/// whose tree is only that chrome is read through its family's content window lying under it; a frame with a tree of
/// its own, a window of its own, a window of another process or a cloaked one never. Pure rules over synthetic windows
/// with the measured geometry: nothing on the desktop is touched.
/// </summary>
[TestFixture]
public sealed class ComputerUseChromeFrameContentTests
{
    private static readonly (int Left, int Top, int Right, int Bottom) Frame = (160, 160, 1600, 900);
    private static readonly (int Left, int Top, int Right, int Bottom) Editor = (169, 220, 1591, 891);

    // The WebView2 content window's extended style measured on the messaging client (WS_EX_TOOLWINDOW | NOACTIVATE).
    private const long ContentStyle = 0x08280080;

    private static (string, (int, int, int, int)?) Control(string kind, int left, int top, int right, int bottom) =>
        (kind, (left, top, right, bottom));

    // The frame after «Editar» (v2-v3-15 step 3, v2-v3-16 step 3): its title band (160–208) and the busy indicator.
    private static readonly (string, (int, int, int, int)?)[] ChromeAfterEdit =
    [
        Control("Button", 1462, 160, 1508, 200),   // Minimize
        Control("Button", 1508, 160, 1554, 200),   // Maximize
        Control("Button", 1554, 160, 1600, 200),   // Close
        Control("Button", 168, 164, 208, 204),     // Atrás
        Control("MenuItem", 160, 160, 168, 168),   // the system menu
        Control("Pane", 160, 160, 1600, 208),      // Non Client Input Sink Window
        Control("Pane", 900, 160, 1462, 208),      // AppWindow Custom Title Bar
        Control("ProgressBar", 840, 520, 920, 540), // «Ocupado»
        Control("Text", 216, 172, 300, 196),       // the title text
        Control("TitleBar", 160, 160, 1600, 200),
        Control("MenuBar", 160, 160, 190, 190),    // «Barra de menús del sistema»
    ];

    private static VisibleControlSurface.SeenWindow Seen(
        nint window, (int Left, int Top, int Right, int Bottom) box, bool above = false, bool descendant = true,
        bool cloaked = false, long exStyle = ContentStyle, nint owner = 0) =>
        new(window, 41664, box.Left, box.Top, box.Right, box.Bottom, above, descendant, cloaked, exStyle, owner);

    [Test]
    public void V3_15_And_V3_16_TheFramesChromeOverItsEditorIsOnlyChrome()
    {
        Assert.Multiple(() =>
        {
            Assert.That(VisibleControlSurface.MayShowOnlyCaption(Frame, ChromeAfterEdit), Is.True);
            Assert.That(VisibleControlSurface.ShowsOnlyCaption(Frame, Editor, ChromeAfterEdit), Is.True);
            // While the editor loads, the frame shows the busy indicator alone (seq 66-78): chrome too.
            Assert.That(VisibleControlSurface.ShowsOnlyCaption(Frame, Editor,
                [Control("TitleBar", 160, 160, 1600, 200), Control("ProgressBar", 840, 520, 920, 540)]), Is.True);
        });
    }

    [Test]
    public void V3_15_TheEditorUnderTheFrameIsTakenAsItsContent()
    {
        VisibleControlSurface.ContentChoice choice = VisibleControlSurface.ChooseContentWindow(Frame, [Seen(13373098, Editor)]);
        Assert.Multiple(() =>
        {
            Assert.That(choice.Window, Is.EqualTo((nint)13373098));
            Assert.That(choice.Reason, Is.EqualTo("under"));
            Assert.That(choice.ExStyle, Is.EqualTo(ContentStyle));
            // The surface rule of the view keeps its default: under the frame is no surface unless asked for.
            Assert.That(VisibleControlSurface.ChooseFamilySurface(Frame,
                [new VisibleControlSurface.FamilyWindow(13373098, 41664, 169, 220, 1591, 891, AboveFrame: false)]), Is.EqualTo((nint)0));
            Assert.That(VisibleControlSurface.ChooseFamilySurface(Frame,
                [new VisibleControlSurface.FamilyWindow(13373098, 41664, 169, 220, 1591, 891, AboveFrame: false)], acceptUnder: true),
                Is.EqualTo((nint)13373098));
        });
    }

    [Test]
    public void AContentWindowAboveTheFrameIsPreferredToOneUnderIt()
    {
        VisibleControlSurface.ContentChoice choice = VisibleControlSurface.ChooseContentWindow(Frame,
            [Seen(10, (160, 160, 1600, 900)), Seen(11, Editor, above: true)]);
        Assert.Multiple(() =>
        {
            Assert.That(choice.Window, Is.EqualTo((nint)11));
            Assert.That(choice.Reason, Is.EqualTo("above"));
        });
    }

    [Test]
    public void CounterCase_AViewerWithATreeOfItsOwnStaysTheView()
    {
        // Fotos before «Editar» (v2-v3-17 t2, 35 controls): its gallery and its command bar lie where the content is.
        (string, (int, int, int, int)?)[] viewer =
        [
            .. ChromeAfterEdit.Where(control => control.Item1 != "ProgressBar"),
            Control("Button", 300, 230, 380, 262),    // Editar, in the command bar under the title band
            Control("ListItem", 170, 300, 400, 340),  // a side navigation item
            Control("Text", 700, 860, 800, 880),      // «1920 x 1080»
        ];
        // A side navigation beside a web view filling 85 % of the frame is the frame's own content too.
        (string, (int, int, int, int)?)[] sideNavigation = [.. ChromeAfterEdit, Control("ListItem", 170, 480, 380, 520)];
        Assert.Multiple(() =>
        {
            Assert.That(VisibleControlSurface.MayShowOnlyCaption(Frame, viewer), Is.False);
            Assert.That(VisibleControlSurface.ShowsOnlyCaption(Frame, Editor, viewer), Is.False);
            Assert.That(VisibleControlSurface.ShowsOnlyCaption(Frame, (380, 208, 1600, 900), sideNavigation), Is.False);
            // A control the frame lists without a rectangle cannot be told chrome: the frame stays the view.
            Assert.That(VisibleControlSurface.ShowsOnlyCaption(Frame, Editor, [.. ChromeAfterEdit, ("Button", null)]), Is.False);
            // A title bar said to fill the frame never makes the whole frame a title band.
            Assert.That(VisibleControlSurface.ShowsOnlyCaption(Frame, Editor,
                [Control("TitleBar", 160, 160, 1600, 900), Control("Button", 300, 500, 380, 540)]), Is.False);
        });
    }

    [Test]
    public void CounterCase_AWindowOfItsOwnUnderAChromeFrameIsNeverTaken()
    {
        // A browser or a game the application started (WS_EX_APPWINDOW), lying under the chrome-only frame.
        VisibleControlSurface.ContentChoice browser = VisibleControlSurface.ChooseContentWindow(Frame,
            [Seen(20, Editor, exStyle: 0x02040100)]);
        // Unowned and neither a tool window nor a no-activate one: a window with its own taskbar button.
        VisibleControlSurface.ContentChoice editorOfItsOwn = VisibleControlSurface.ChooseContentWindow(Frame,
            [Seen(21, (160, 160, 1600, 900), exStyle: 0x00200100)]);
        Assert.Multiple(() =>
        {
            Assert.That(browser.Window, Is.EqualTo((nint)0));
            Assert.That(browser.Reason, Is.EqualTo("app_window"));
            Assert.That(browser.ExStyle, Is.EqualTo(0x02040100));
            Assert.That(editorOfItsOwn.Window, Is.EqualTo((nint)0));
            Assert.That(editorOfItsOwn.Reason, Is.EqualTo("app_window"));
        });
    }

    [Test]
    public void CounterCase_AnotherProcessesOrACloakedWindowIsNeverTaken()
    {
        VisibleControlSurface.ContentChoice stranger = VisibleControlSurface.ChooseContentWindow(Frame,
            [Seen(30, Editor, descendant: false)]);
        VisibleControlSurface.ContentChoice cloaked = VisibleControlSurface.ChooseContentWindow(Frame,
            [Seen(31, Editor, cloaked: true)]);
        VisibleControlSurface.ContentChoice small = VisibleControlSurface.ChooseContentWindow(Frame,
            [Seen(32, (400, 400, 900, 700))]);
        VisibleControlSurface.ContentChoice nothing = VisibleControlSurface.ChooseContentWindow(Frame, []);
        Assert.Multiple(() =>
        {
            Assert.That(stranger.Window, Is.EqualTo((nint)0));
            Assert.That(stranger.Reason, Is.EqualTo("not_descendant"));
            Assert.That(cloaked.Window, Is.EqualTo((nint)0));
            Assert.That(cloaked.Reason, Is.EqualTo("cloaked"));
            Assert.That(small.Window, Is.EqualTo((nint)0));
            Assert.That(small.Reason, Is.EqualTo("geometry"));
            // The editor did not come (it is slow or it failed): nothing is taken and the frame stays the view.
            Assert.That(nothing, Is.EqualTo(VisibleControlSurface.ContentChoice.Nothing));
            Assert.That(nothing.Reason, Is.EqualTo("none"));
        });
    }
}
