using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// v3 point 1 (process family), measured live on a messaging client: its WinUI frame exposed eight elements and no
/// field, while its content was a top-level window of a WebView2 child process drawn over the frame with the whole
/// accessible tree. The application's surface is a window of a descendant process covering at least 90 % of the
/// application's window and lying over it; the front held by either window counts for the other, never for another
/// process. Pure rules: nothing on the desktop is touched.
/// </summary>
[TestFixture]
public sealed class ComputerUseProcessFamilyTests
{
    private static readonly (int, int, int, int) Frame = (0, 0, 1938, 1038);

    [Test]
    public void TheChildWindowDrawnOverAnEmptyFrameIsTheSurface()
    {
        VisibleControlSurface.FamilyWindow content = new(66, 11216, 0, 32, 1938, 1038, AboveFrame: true);
        VisibleControlSurface.FamilyWindow helper = new(67, 11217, 100, 100, 600, 400, AboveFrame: true);
        Assert.That(VisibleControlSurface.ChooseFamilySurface(Frame, [helper, content]), Is.EqualTo((nint)66));
    }

    [Test]
    public void AChildWindowThatIsNotTheContentLeavesTheFrameAsTheSurface()
    {
        Assert.Multiple(() =>
        {
            // A dialog or a pop-up of a helper covers part of the window only.
            Assert.That(VisibleControlSurface.ChooseFamilySurface(Frame,
                [new VisibleControlSurface.FamilyWindow(70, 5, 0, 0, 1938, 700, AboveFrame: true)]), Is.EqualTo((nint)0));
            // A borderless full screen started by a launcher over its maximized window is larger than it (the taskbar).
            Assert.That(VisibleControlSurface.ChooseFamilySurface((0, 0, 1920, 1032),
                [new VisibleControlSurface.FamilyWindow(71, 5, 0, 0, 1920, 1080, AboveFrame: true)]), Is.EqualTo((nint)0));
            // Under the application's window it is not what a person sees.
            Assert.That(VisibleControlSurface.ChooseFamilySurface(Frame,
                [new VisibleControlSurface.FamilyWindow(72, 5, 0, 32, 1938, 1038, AboveFrame: false)]), Is.EqualTo((nint)0));
        });
    }

    // Review of v3 point 1: geometry alone cannot tell the content from a window of its own a process of the
    // application opened (a browser it started maximized, a game a launcher started full screen with the taskbar
    // hidden). Such a window stays out of the surface and covers the application's window; the keys and the text of
    // the mission never go to it.
    [Test]
    public void AWindowOfItsOwnStartedByTheApplicationIsNeverItsSurfaceAndCoversIt()
    {
        // A browser the application started, maximized like it, with its own taskbar button and accessible content.
        VisibleControlSurface.FamilyWindow browser = new(80, 5, 0, 0, 1938, 1038, AboveFrame: true, ApplicationWindow: true);
        // A full screen over the launcher maximized with the taskbar hidden (1920×1078): 0.2 % larger, inside the 2 %.
        (int, int, int, int) launcher = (0, 0, 1920, 1078);
        VisibleControlSurface.FamilyWindow game = new(81, 6, 0, 0, 1920, 1080, AboveFrame: true, ApplicationWindow: true);
        Assert.Multiple(() =>
        {
            Assert.That(VisibleControlSurface.ChooseFamilySurface(Frame, [browser]), Is.EqualTo((nint)0));
            Assert.That(VisibleControlSurface.IsContentOf(Frame, browser), Is.False, "it covers the application's window");
            Assert.That(VisibleControlSurface.ChooseFamilySurface(launcher, [game]), Is.EqualTo((nint)0));
            Assert.That(VisibleControlSurface.IsContentOf(launcher, game), Is.False, "it covers the launcher");
            // Counter-case: the same geometry drawn as content (no button of its own) is the surface.
            Assert.That(VisibleControlSurface.ChooseFamilySurface(launcher, [game with { ApplicationWindow = false }]),
                Is.EqualTo((nint)81));
            Assert.That(VisibleControlSurface.IsContentOf(launcher, game with { ApplicationWindow = false }), Is.True);
        });
    }

    [Test]
    public void AnApplicationWindowIsOneWithItsOwnTaskbarButton()
    {
        const long appWindow = 0x00040000;
        const long toolWindow = 0x00000080;
        const long noActivate = 0x08000000;
        const long windowEdge = 0x00000100;
        Assert.Multiple(() =>
        {
            Assert.That(VisibleControlSurface.IsApplicationWindow(windowEdge, 0), Is.True, "unowned, a button of its own");
            Assert.That(VisibleControlSurface.IsApplicationWindow(appWindow | toolWindow, 0), Is.True);
            Assert.That(VisibleControlSurface.IsApplicationWindow(appWindow, 99), Is.True, "owned but forced on the taskbar");
            Assert.That(VisibleControlSurface.IsApplicationWindow(toolWindow, 0), Is.False);
            Assert.That(VisibleControlSurface.IsApplicationWindow(noActivate, 0), Is.False);
            Assert.That(VisibleControlSurface.IsApplicationWindow(windowEdge, 99), Is.False, "owned: no button");
        });
    }

    [Test]
    public void AProcessDescendsOnlyThroughProcessesStartedAfterTheApplication()
    {
        var started = new DateTime(2026, 10, 8, 12, 0, 0, DateTimeKind.Utc);
        var parents = new Dictionary<uint, uint> { [20] = 10, [30] = 20, [10] = 4, [40] = 10 };
        // 40 holds a reused parent id: it is older than the application.
        bool StartedAfter(uint process, DateTime root) => process != 40;
        Assert.Multiple(() =>
        {
            Assert.That(VisibleControlSurface.DescendsFrom(20, 10, started, parents, StartedAfter), Is.True);
            Assert.That(VisibleControlSurface.DescendsFrom(30, 10, started, parents, StartedAfter), Is.True, "a grandchild");
            Assert.That(VisibleControlSurface.DescendsFrom(40, 10, started, parents, StartedAfter), Is.False, "a reused parent id");
            Assert.That(VisibleControlSurface.DescendsFrom(4, 10, started, parents, StartedAfter), Is.False,
                "the process that started the application (the shell, an editor) is never its family");
            Assert.That(VisibleControlSurface.DescendsFrom(10, 10, started, parents, StartedAfter), Is.False);
        });
    }

    [Test]
    public void TheFrontOfTheFamilyPeerHoldsForTheWindowAndNoOtherDoes()
    {
        nint Root(nint hwnd) => hwnd;
        nint Owner(nint hwnd) => 0;
        Assert.Multiple(() =>
        {
            Assert.That(VisibleControlSurface.IsOrOwnedByFamily(66, 132, 132, Root, Owner), Is.True,
                "the application's frame in front takes the keys for the content drawn over it");
            Assert.That(VisibleControlSurface.IsOrOwnedByFamily(66, 132, 66, Root, Owner), Is.True);
            Assert.That(VisibleControlSurface.IsOrOwnedByFamily(66, 132, 900, Root, Owner), Is.False, "the person's window");
            Assert.That(VisibleControlSurface.IsOrOwnedByFamily(66, 0, 132, Root, Owner), Is.False, "no family: only the window");
        });
    }
}
