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
