using System.Diagnostics;
using System.Runtime.InteropServices;
using Baxy.Providers.Windows.Applications;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

[TestFixture]
[NonParallelizable]
public sealed class InstalledApplicationWindowEnumerationTests
{
    [Test]
    public void InventoryIncludesEveryVisibleWindowOfOneProcessAndExcludesHiddenWindows()
    {
        nint foreground = GetForegroundWindow();
        var owned = new List<nint>();
        try
        {
            // Real HWNDs, outside the desktop and never activated. No user
            // application's windows are opened, focused, changed or closed.
            nint first = Create(100, 80, visible: true);
            nint second = Create(300, 200, visible: true);
            nint hidden = Create(120, 80, visible: false);
            using Process current = Process.GetCurrentProcess();
            var entry = new InstalledApplicationEntry(
                "C03 enumeration fixture", current.ProcessName + ".exe");

            IReadOnlyList<InstalledApplicationObservation> observations =
                new WindowsInstalledApplicationPlatform().Inventory(entry);
            long[] handles = observations.Select(item => item.WindowHandle).ToArray();
            Assert.Multiple(() =>
            {
                Assert.That(handles, Does.Contain(first.ToInt64()));
                Assert.That(handles, Does.Contain(second.ToInt64()));
                Assert.That(handles, Does.Not.Contain(hidden.ToInt64()));
                Assert.That(handles.Distinct().Count(), Is.EqualTo(handles.Length));
                Assert.That(GetForegroundWindow(), Is.EqualTo(foreground));
            });
        }
        finally
        {
            foreach (nint handle in owned)
                _ = DestroyWindow(handle);
        }

        nint Create(int width, int height, bool visible)
        {
            nint handle = CreateWindowEx(0x08000000, "STATIC", "C03 enumeration fixture",
                visible ? 0x90000000u : 0x80000000u,
                -31000, -31000, width, height, 0, 0, 0, 0);
            Assert.That(handle, Is.Not.EqualTo(nint.Zero),
                $"CreateWindowEx failed: {Marshal.GetLastPInvokeError()}");
            owned.Add(handle);
            return handle;
        }
    }

    // r27u (tandas v3b1 y r23q, t2-c04 t5 «ya quedo, cierra configuracion porfa»): window.resolve of Configuración gave
    // only SystemSettings' 71×41 «Host de ventanas emergentes» (owned); app.close closed it, the Settings frame stayed
    // and the reply said it was closed. Fake windows: handles and who owns them.
    private const long Frame = 100;
    private const long Main = 110;
    private const long Popup = 200;
    private const long Dialog = 210;

    [Test]
    public void APackagedApplicationsPopupGivesWayToItsFrame()
    {
        // SystemSettings shows only the popup host of its own; the frame that hosts it is the window.
        var observations = new List<InstalledApplicationObservation> { Observation(Popup, "SystemSettings") };

        WindowsInstalledApplicationPlatform.KeepOwnWindows(
            observations, static window => window == Popup, static found => found.Add(Observation(Frame, "ApplicationFrameHost")));

        Assert.That(observations.Select(static item => item.WindowHandle), Is.EqualTo(new[] { Frame }));
    }

    [Test]
    public void AnApplicationSeenOnlyThroughOwnedPopupsHasNoWindow()
    {
        // Classic (no frames to look for) and packaged with no frame on screen: nothing is offered as its window.
        var classic = new List<InstalledApplicationObservation> { Observation(Popup, "App"), Observation(Dialog, "App") };
        var packaged = new List<InstalledApplicationObservation> { Observation(Popup, "SystemSettings") };

        WindowsInstalledApplicationPlatform.KeepOwnWindows(classic, static _ => true, null);
        WindowsInstalledApplicationPlatform.KeepOwnWindows(packaged, static _ => true, static _ => { });

        Assert.Multiple(() =>
        {
            Assert.That(classic, Is.Empty);
            Assert.That(packaged, Is.Empty);
        });
    }

    [Test]
    public void AModalDialogGoesWithTheWindowThatOwnsIt()
    {
        var observations = new List<InstalledApplicationObservation> { Observation(Dialog, "App"), Observation(Main, "App") };
        bool framesLookedFor = false;

        WindowsInstalledApplicationPlatform.KeepOwnWindows(
            observations, static window => window == Dialog, _ => framesLookedFor = true);

        Assert.Multiple(() =>
        {
            Assert.That(observations.Select(static item => item.WindowHandle), Is.EqualTo(new[] { Main }));
            Assert.That(framesLookedFor, Is.False);
        });
    }

    [Test]
    public void APackagedApplicationWithNoWindowOfItsOwnIsItsFrameAsBefore()
    {
        var observations = new List<InstalledApplicationObservation>();

        WindowsInstalledApplicationPlatform.KeepOwnWindows(
            observations, static _ => false, static found => found.Add(Observation(Frame, "ApplicationFrameHost")));

        Assert.That(observations.Select(static item => item.WindowHandle), Is.EqualTo(new[] { Frame }));
    }

    // Contracaso: two windows nobody owns both stay (which one is asked, never guessed).
    [Test]
    public void WindowsNoOtherWindowOwnsAllStay()
    {
        var observations = new List<InstalledApplicationObservation> { Observation(1, "App"), Observation(2, "App") };

        WindowsInstalledApplicationPlatform.KeepOwnWindows(observations, static _ => false, null);

        Assert.That(observations.Select(static item => item.WindowHandle), Is.EqualTo(new long[] { 1, 2 }));
    }

    private static InstalledApplicationObservation Observation(long window, string process) =>
        new(77, 7, @"C:\Windows\System32\" + process + ".exe", window, Visible: true, Foreground: false, process);

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
}
