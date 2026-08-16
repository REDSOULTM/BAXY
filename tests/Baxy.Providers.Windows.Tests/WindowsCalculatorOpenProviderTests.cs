using Baxy.Providers.Windows.Applications;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

[TestFixture]
public sealed class WindowsCalculatorOpenProviderTests
{
    [Test]
    public async Task LaunchCompletesOnlyAfterIndependentVisibleForegroundInventory()
    {
        var platform = new FakePlatform();
        var provider = new WindowsCalculatorOpenProvider(platform);
        var request = new ApplicationOpenRequest(
            ApplicationIds.Calculator, Guid.NewGuid().ToString("D"));

        ApplicationOpenResult result = await provider.OpenAsync(request, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Succeeded, Is.True);
            Assert.That(result.Verified, Is.True);
            Assert.That(result.DisplayName, Is.EqualTo("Calculadora"));
            Assert.That(result.ProcessId, Is.EqualTo(52));
            Assert.That(result.WindowHandle, Is.EqualTo(91));
            Assert.That(platform.LaunchCount, Is.EqualTo(1));
            Assert.That(platform.FocusCount, Is.EqualTo(1));
            Assert.That(platform.InventoryCount, Is.GreaterThanOrEqualTo(3));
            Assert.That(platform.DelayCount, Is.Zero);
        });
    }

    [Test]
    public async Task ForegroundVerificationWaitsOnlyWhenTheImmediatePostreadHasNotConverged()
    {
        var platform = new FakePlatform { FocusRequiresDelay = true };
        var provider = new WindowsCalculatorOpenProvider(platform);
        var request = new ApplicationOpenRequest(
            ApplicationIds.Calculator, Guid.NewGuid().ToString("D"));

        ApplicationOpenResult result = await provider.OpenAsync(request, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Succeeded, Is.True);
            Assert.That(result.Verified, Is.True);
            Assert.That(platform.FocusCount, Is.EqualTo(1));
            Assert.That(platform.DelayCount, Is.EqualTo(1));
        });
    }

    private sealed class FakePlatform : ICalculatorPlatform
    {
        private bool _launched;
        private bool _focused;
        public bool FocusRequiresDelay { get; init; }
        public int LaunchCount { get; private set; }
        public int FocusCount { get; private set; }
        public int InventoryCount { get; private set; }
        public int DelayCount { get; private set; }
        public IReadOnlyList<CalculatorSnapshot> Inventory()
        {
            InventoryCount++;
            return _launched
                ? [new CalculatorSnapshot(52, 638_880_000_000_000_000, 91, true, _focused)]
                : [];
        }
        public bool Launch() { LaunchCount++; _launched = true; return true; }
        public void RequestForeground(long windowHandle)
        {
            Assert.That(windowHandle, Is.EqualTo(91));
            FocusCount++;
            if (!FocusRequiresDelay) _focused = true;
        }
        public ValueTask DelayAsync(TimeSpan delay, CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            DelayCount++;
            _focused = true;
            return ValueTask.CompletedTask;
        }
    }
}
