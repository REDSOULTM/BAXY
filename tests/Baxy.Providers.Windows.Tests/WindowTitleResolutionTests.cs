using System.Diagnostics;
using System.Runtime.InteropServices;
using Baxy.Providers.Windows.Windows;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

[TestFixture]
[NonParallelizable]
[Apartment(ApartmentState.STA)]
public sealed class WindowTitleResolutionTests
{
    [Test]
    public void VisibleTitlesDistinguishWindowsSharingAnOwnerWithoutLosingProcessLookup()
    {
        string prefix = "BaxyC03-" + Guid.NewGuid().ToString("N");
        string[] titles = [prefix + " Alfa", prefix + " Beta", prefix + "Extra"];
        var handles = new List<nint>();
        try
        {
            foreach (string title in titles)
            {
                nint handle = CreateWindowEx(0, "STATIC", title, 0x10CF0000,
                    40 + handles.Count * 30, 40, 240, 120, 0, 0, 0, 0);
                Assert.That(handle, Is.Not.EqualTo(nint.Zero), $"CreateWindowEx:{Marshal.GetLastWin32Error()}");
                handles.Add(handle);
            }

            var provider = new WindowsWindowControlProvider();
            WindowResolveResult exact = provider.ResolveAsync(titles[0], 20, CancellationToken.None, byTitle: true)
                .AsTask().GetAwaiter().GetResult();
            WindowResolveResult related = provider.ResolveAsync(prefix, 20, CancellationToken.None, byTitle: true)
                .AsTask().GetAwaiter().GetResult();
            WindowResolveResult missing = provider.ResolveAsync(prefix + " Missing", 20, CancellationToken.None, byTitle: true)
                .AsTask().GetAwaiter().GetResult();
            using Process self = Process.GetCurrentProcess();
            WindowResolveResult wrongProcess = provider.ResolveAsync(titles[0], 20, CancellationToken.None)
                .AsTask().GetAwaiter().GetResult();
            WindowResolveResult byProcess = provider.ResolveAsync(self.ProcessName + ".exe", 50, CancellationToken.None)
                .AsTask().GetAwaiter().GetResult();
            Assert.Multiple(() =>
            {
                Assert.That(exact.Verified, Is.True);
                Assert.That(exact.Windows.Select(window => window.Title), Is.EqualTo(new[] { titles[0] }));
                Assert.That(exact.Windows.Single().ProcessId, Is.EqualTo(Environment.ProcessId));
                Assert.That(related.Verified, Is.True);
                Assert.That(related.Windows.Select(window => window.Title), Is.EquivalentTo(titles.Take(2)));
                Assert.That(related.Windows.Select(window => window.WindowId).Distinct().Count(), Is.EqualTo(2));
                Assert.That(missing.Succeeded, Is.False);
                Assert.That(missing.ErrorCode, Is.EqualTo(WindowControlErrorCodes.WindowNotFound));
                Assert.That(wrongProcess.Succeeded, Is.False, "A title must not impersonate an explicitly requested process.");
                Assert.That(byProcess.Verified, Is.True);
                Assert.That(byProcess.Windows.Select(window => window.Title), Is.SupersetOf(titles));
            });
        }
        finally
        {
            foreach (nint handle in handles)
                _ = DestroyWindow(handle);
        }
    }

#pragma warning disable SYSLIB1054
    [DllImport("user32.dll", EntryPoint = "CreateWindowExW", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern nint CreateWindowEx(uint extendedStyle, string className, string title,
        uint style, int x, int y, int width, int height, nint parent, nint menu, nint instance, nint parameter);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool DestroyWindow(nint handle);
#pragma warning restore SYSLIB1054
}
