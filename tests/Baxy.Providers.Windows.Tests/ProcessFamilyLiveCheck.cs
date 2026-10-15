using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// v3 point 1, read only: with an application already open whose content a child process draws (named by
/// BAXY_CU_FAMILY_APP), the window resolved for it is the child's surface and the family names the application's
/// process first. Nothing is opened, clicked, typed or brought to the front. Never runs in a suite: it is Explicit and
/// also needs BAXY_CU_FAMILY_LIVE_CHECK=1.
/// </summary>
[TestFixture]
[Explicit("Reads the windows on the person's desktop.")]
public sealed class ProcessFamilyLiveCheck
{
    [Test]
    public async Task TheOpenApplicationsSurfaceIsItsChildsWindow()
    {
        if (Environment.GetEnvironmentVariable("BAXY_CU_FAMILY_LIVE_CHECK") != "1")
            Assert.Ignore("BAXY_CU_FAMILY_LIVE_CHECK=1 is required.");
        string application = Environment.GetEnvironmentVariable("BAXY_CU_FAMILY_APP") ?? string.Empty;
        nint byTitle = await VisibleControlSurface.ResolveTitledWindowAsync(application, CancellationToken.None);
        (int processId, string processName) = VisibleControlSurface.WindowProcess(byTitle);
        uint[]? family = VisibleControlSurface.SurfaceFamily(byTitle);
        nint frame = VisibleControlSurface.FamilyPeer(byTitle);
        nint byProcess = family is { Length: > 0 }
            ? await VisibleControlSurface.ResolveProcessWindowAsync(unchecked((int)family[0]), CancellationToken.None)
            : 0;
        TestContext.Out.WriteLine(
            $"surface={byTitle} class={VisibleControlSurface.ClassName(byTitle)} process={processName}:{processId} "
            + $"frame={frame} frameClass={VisibleControlSurface.ClassName(frame)} family=[{string.Join(",", family ?? [])}] "
            + $"byProcess={byProcess} cover={VisibleControlSurface.CoveringWindow(byTitle)}");
        Assert.Multiple(() =>
        {
            Assert.That(byTitle, Is.Not.EqualTo((nint)0));
            Assert.That(family, Is.Not.Null.And.Not.Empty, "the surface is a child process's window");
            Assert.That(byProcess, Is.EqualTo(byTitle), "resolved by the application's process, the same surface");
        });
    }
}
