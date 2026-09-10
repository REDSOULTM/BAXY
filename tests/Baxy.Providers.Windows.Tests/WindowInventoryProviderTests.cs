using System.ComponentModel;
using Baxy.Providers.Windows.Windows;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

[TestFixture]
public sealed class WindowInventoryProviderTests
{
    [TestCase("*", false, true, "*")]
    [TestCase(" * ", false, true, "*")]
    [TestCase("*.exe", false, false, "*")]
    [TestCase("EDITOR.EXE", false, false, "EDITOR")]
    [TestCase("edit*", false, false, "edit*")]
    [TestCase("*", true, false, "*")]
    [TestCase("Informe.exe", true, false, "Informe.exe")]
    public async Task OnlyExplicitGlobalProcessSelectorExpandsScope(
        string selector, bool byTitle, bool expectedGlobal, string expectedSelector)
    {
        var platform = new InventoryPlatform(3);
        var provider = new WindowsWindowControlProvider(platform);

        WindowResolveResult result = await provider.ResolveAsync(selector, 2,
            CancellationToken.None, byTitle: byTitle, offset: 1);

        Assert.Multiple(() =>
        {
            Assert.That(result.Verified, Is.True);
            Assert.That(platform.LastSelector, Is.EqualTo(expectedSelector));
            Assert.That(platform.LastByTitle, Is.EqualTo(byTitle));
            Assert.That(platform.LastGlobal, Is.EqualTo(expectedGlobal));
            Assert.That(platform.LastOffset, Is.EqualTo(1));
            Assert.That(platform.LastLimit, Is.EqualTo(2));
            Assert.That(platform.EffectCalls, Is.Zero);
        });
    }

    [TestCase(0, 2, 3, 2)]
    [TestCase(2, 2, 3, null)]
    [TestCase(0, 3, 3, null)]
    [TestCase(3, 2, 3, null)]
    [TestCase(int.MaxValue, 50, 3, null)]
    [TestCase(0, 50, 0, null)]
    public async Task PageReportsTheObservedInventoryWithoutConfusingPageCountWithTotal(
        int offset, int limit, int count, int? nextOffset)
    {
        var platform = new InventoryPlatform(count);
        var provider = new WindowsWindowControlProvider(platform);

        WindowResolveResult result = await provider.ResolveAsync("*", limit,
            CancellationToken.None, offset: offset);

        Assert.Multiple(() =>
        {
            Assert.That(result.Succeeded, Is.True);
            Assert.That(result.Verified, Is.True);
            Assert.That(result.Windows, Has.Count.EqualTo(Math.Min(limit, Math.Max(0, count - offset))));
            Assert.That(result.Page, Is.EqualTo(new WindowInventoryPage(limit, offset, count, true, nextOffset)));
            Assert.That(result.Windows.Select(window => window.WindowId), Is.Unique);
            Assert.That(result.Windows.All(window => window.WindowId.StartsWith("win_", StringComparison.Ordinal)), Is.True);
            Assert.That(platform.ObserveCalls, Is.EqualTo(result.Windows.Count));
            Assert.That(platform.EffectCalls, Is.Zero);
        });
    }

    [TestCase(0)]
    [TestCase(3)]
    public async Task PartialEnumerationKeepsItsUncertaintyEvenWithNoReadableWindows(int count)
    {
        var provider = new WindowsWindowControlProvider(new InventoryPlatform(count) { Complete = false });

        WindowResolveResult result = await provider.ResolveAsync("*", 2, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Succeeded, Is.True);
            Assert.That(result.Verified, Is.True);
            Assert.That(result.Page!.Complete, Is.False);
            Assert.That(result.Page.ObservedCount, Is.EqualTo(count));
            Assert.That(result.Windows.Count, Is.LessThanOrEqualTo(2));
        });
    }

    [Test]
    public async Task MissingConcreteProcessStillReturnsNotFound()
    {
        var provider = new WindowsWindowControlProvider(new InventoryPlatform(0));

        WindowResolveResult result = await provider.ResolveAsync("missing", 2, CancellationToken.None);

        Assert.That(result.ErrorCode, Is.EqualTo(WindowControlErrorCodes.WindowNotFound));
    }

    [TestCase("", 2, 0)]
    [TestCase("   ", 2, 0)]
    [TestCase("C:\\program.exe", 2, 0)]
    [TestCase("*", 0, 0)]
    [TestCase("*", 51, 0)]
    [TestCase("*", 2, -1)]
    public async Task InvalidSelectorsAndBoundsNeverEnumerate(string selector, int limit, int offset)
    {
        var platform = new InventoryPlatform(3);
        var result = await new WindowsWindowControlProvider(platform).ResolveAsync(
            selector, limit, CancellationToken.None, offset: offset);

        Assert.Multiple(() =>
        {
            Assert.That(result.ErrorCode, Is.EqualTo(WindowControlErrorCodes.InvalidSelector));
            Assert.That(platform.ReadCalls, Is.Zero);
        });
    }

    [Test]
    public async Task EnumerationFailureDoesNotBecomeAnEmptyCompleteInventory()
    {
        var platform = new InventoryPlatform(3) { FailEnumeration = true };
        WindowResolveResult result = await new WindowsWindowControlProvider(platform).ResolveAsync(
            "*", 2, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Succeeded, Is.False);
            Assert.That(result.Verified, Is.False);
            Assert.That(result.Page, Is.Null);
            Assert.That(result.ErrorCode, Is.EqualTo(WindowControlErrorCodes.InventoryFailed));
        });
    }

    [Test]
    public async Task ADisappearedWindowCannotReceiveAVerifiedId()
    {
        var platform = new InventoryPlatform(3) { FailVerification = true };
        WindowResolveResult result = await new WindowsWindowControlProvider(platform).ResolveAsync(
            "*", 2, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Verified, Is.False);
            Assert.That(result.Windows, Is.Empty);
            Assert.That(result.ErrorCode, Is.EqualTo(WindowControlErrorCodes.VerificationFailed));
            Assert.That(platform.EffectCalls, Is.Zero);
        });
    }

    [TestCase(false)]
    [TestCase(true)]
    public void CancellationBeforeOrDuringEnumerationNeverPublishesACompletedPage(bool during)
    {
        using var cancellation = new CancellationTokenSource();
        var platform = new InventoryPlatform(0)
        {
            AfterEnumeration = during ? cancellation.Cancel : null,
        };
        var provider = new WindowsWindowControlProvider(platform);
        if (!during) cancellation.Cancel();

        Assert.ThrowsAsync<OperationCanceledException>(async () =>
            await provider.ResolveAsync("*", 2, cancellation.Token));
        Assert.That(platform.ReadCalls, Is.EqualTo(during ? 1 : 0));
    }

    private sealed class InventoryPlatform(int count) : IWindowControlPlatform
    {
        private readonly WindowSnapshot[] _windows = Enumerable.Range(1, count)
            .Select(index => new WindowSnapshot(
                new WindowIdentity((nint)index, index + 10, index, $"editor{index}", DateTimeOffset.UnixEpoch),
                "normal", false, new WindowBounds(index * 20, 30, 640, 480), $"Documento {index}"))
            .ToArray();

        public DateTimeOffset UtcNow => DateTimeOffset.UnixEpoch;
        public bool Complete { get; init; } = true;
        public bool FailEnumeration { get; init; }
        public bool FailVerification { get; init; }
        public Action? AfterEnumeration { get; init; }
        public int ReadCalls { get; private set; }
        public int ObserveCalls { get; private set; }
        public int EffectCalls { get; private set; }
        public string? LastSelector { get; private set; }
        public bool LastByTitle { get; private set; }
        public bool LastGlobal { get; private set; }
        public int LastOffset { get; private set; }
        public int LastLimit { get; private set; }

        public WindowSnapshot? FindForegroundWindow() => null;

        public WindowEnumeration FindVisibleWindows(string processName, int limit,
            bool byTitle = false, int offset = 0, bool allWindows = false,
            CancellationToken cancellationToken = default)
        {
            cancellationToken.ThrowIfCancellationRequested();
            ReadCalls++;
            LastSelector = processName;
            LastByTitle = byTitle;
            LastGlobal = allWindows;
            LastOffset = offset;
            LastLimit = limit;
            if (FailEnumeration) throw new Win32Exception(5);
            AfterEnumeration?.Invoke();
            return new WindowEnumeration(_windows.Skip(offset).Take(limit).ToArray(), count, Complete);
        }

        public WindowSnapshot Observe(WindowIdentity identity)
        {
            ObserveCalls++;
            if (FailVerification) throw new WindowIdentityChangedException();
            return _windows.Single(window => window.Identity == identity);
        }

        public bool Execute(WindowIdentity identity, WindowControlAction action) { EffectCalls++; return false; }
        public bool SetBounds(WindowIdentity identity, WindowBounds bounds) { EffectCalls++; return false; }
        public bool RequestClose(WindowIdentity identity) { EffectCalls++; return false; }
        public bool RequestSystemClose(WindowIdentity identity) { EffectCalls++; return false; }
        public ValueTask DelayAsync(TimeSpan delay, CancellationToken cancellationToken) => ValueTask.CompletedTask;
    }
}
