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
    public void GlobalAndPagedNativeReadsPreserveLiteralTitleAndProcessSelectors()
    {
        string prefix = "BaxyInventory-" + Guid.NewGuid().ToString("N");
        string[] titles = [prefix + " Uno", prefix + " Dos", prefix + " Tres", "*"];
        var handles = new List<nint>();
        try
        {
            foreach (string title in titles)
            {
                nint handle = CreateWindowEx(0, "STATIC", title, 0x10CF0000,
                    60 + handles.Count * 20, 60, 240, 120, 0, 0, 0, 0);
                Assert.That(handle, Is.Not.EqualTo(nint.Zero));
                handles.Add(handle);
            }

            var provider = new WindowsWindowControlProvider();
            WindowResolveResult first = provider.ResolveAsync(prefix, 2, CancellationToken.None, byTitle: true)
                .AsTask().GetAwaiter().GetResult();
            WindowResolveResult last = provider.ResolveAsync(prefix, 2, CancellationToken.None, byTitle: true, offset: 2)
                .AsTask().GetAwaiter().GetResult();
            WindowResolveResult literal = provider.ResolveAsync("*", 50, CancellationToken.None, byTitle: true)
                .AsTask().GetAwaiter().GetResult();
            WindowResolveResult extension = provider.ResolveAsync("*.exe", 50, CancellationToken.None)
                .AsTask().GetAwaiter().GetResult();
            var globalTitles = new HashSet<string?>();
            int? offset = 0;
            do
            {
                WindowResolveResult page = provider.ResolveAsync("*", 50, CancellationToken.None, offset: offset.Value)
                    .AsTask().GetAwaiter().GetResult();
                Assert.That(page.Succeeded && page.Verified, Is.True, page.ErrorCode);
                Assert.That(page.Windows.Count, Is.LessThanOrEqualTo(50));
                Assert.That(page.Page!.ObservedCount, Is.GreaterThanOrEqualTo(page.Windows.Count));
                globalTitles.UnionWith(page.Windows.Select(window => window.Title));
                offset = page.Page.NextOffset;
            } while (offset.HasValue && !titles.All(globalTitles.Contains));

            Assert.Multiple(() =>
            {
                Assert.That(first.Succeeded && last.Succeeded, Is.True);
                Assert.That(first.Page!.ObservedCount, Is.EqualTo(3));
                Assert.That(first.Page.NextOffset, Is.EqualTo(2));
                Assert.That(last.Page!.NextOffset, Is.Null);
                Assert.That(first.Windows.Concat(last.Windows).Select(window => window.Title),
                    Is.EquivalentTo(titles.Take(3)));
                Assert.That(literal.Windows.Select(window => window.Title), Has.All.EqualTo("*"));
                Assert.That(literal.Windows.Any(window => window.ProcessId == Environment.ProcessId), Is.True);
                Assert.That(extension.Windows, Is.Empty);
                Assert.That(extension.Succeeded, Is.False, "*.exe must not acquire global scope after normalization.");
                Assert.That(globalTitles, Is.SupersetOf(titles));
            });
        }
        finally
        {
            foreach (nint handle in handles) _ = DestroyWindow(handle);
        }
    }

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
