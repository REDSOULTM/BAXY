using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Goal v3 ventana-misión (t-long-2, pasada r9): the look of a mission tied to its windows. Measured live: Word's one
/// process (WINWORD) held Documento1, created by the mission, and the owner's thesis, opened by a click on a recent
/// file and in front; the look bound to the process took the thesis. A tied look reads a window that came during the
/// mission (for the mission to keep or refuse) or its own window, never one it knows is another.
/// </summary>
[TestFixture]
public sealed class ComputerUseMissionWindowSurfaceTests
{
    private const uint Word = 60;

    // EnumWindows order, top first: the thesis in front, Documento1 behind it.
    private static readonly VisibleControlSurface.TopLevelWindow[] WordWindows =
    [
        new((nint)2002, Word, Usable: true, Area: 1_440_000),
        new((nint)1001, Word, Usable: true, Area: 1_440_000),
        new((nint)4004, Word, Usable: false, Area: 0),
        new((nint)9101, 91, Usable: true, Area: 400_000),
    ];

    [Test]
    public void TLong2TheThesisThatCameDuringTheMissionIsSaidBornUntilTheMissionKnowsIt()
    {
        nint[] mission = [1001];
        Assert.Multiple(() =>
        {
            Assert.That(VisibleControlSurface.BornWindow(WordWindows, Word, mission, new HashSet<nint>()), Is.EqualTo((nint)2002),
                "the thesis came during the mission: the mission decides on it");
            Assert.That(VisibleControlSurface.BornWindow(WordWindows, Word, mission, new HashSet<nint> { 2002 }), Is.EqualTo((nint)0),
                "refused once, never read again; an unusable window or another process's never comes");
        });
    }

    [Test]
    public void ATiedLookReadsTheBornWindowElseTheLatestMissionWindowAlive()
    {
        var alive = new HashSet<nint> { 1001, 3003 };
        Assert.Multiple(() =>
        {
            Assert.That(VisibleControlSurface.ChooseMissionWindow([3003, 1001], 0, alive.Contains, out bool born), Is.EqualTo((nint)3003));
            Assert.That(born, Is.False);
            Assert.That(VisibleControlSurface.ChooseMissionWindow([5150, 1001], 0, alive.Contains, out _), Is.EqualTo((nint)1001),
                "a closed dialog gives the look back to the window it belonged to");
            Assert.That(VisibleControlSurface.ChooseMissionWindow([1001], 2002, alive.Contains, out bool came), Is.EqualTo((nint)2002));
            Assert.That(came, Is.True);
            Assert.That(VisibleControlSurface.ChooseMissionWindow([5150], 0, alive.Contains, out _), Is.EqualTo((nint)0),
                "no window of the mission left: nothing, never the window in front instead");
        });
    }
}
