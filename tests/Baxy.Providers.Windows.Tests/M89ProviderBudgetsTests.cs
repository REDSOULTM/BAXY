using Baxy.Contracts;
using Baxy.Providers.Windows.Applications;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// M89 (DEV-D v3r, HEAD 50cee2c6). D-w11-t5 «¿Me abres el Spotify?»: the mission journal of the run has app.open
/// «started» at 20:28:33 and never «completed»; the shell gave up at 90 s and restarted the core, and the reply was «el
/// tiempo de espera se agotó». D-w10-t4 «ponme música tropical en YouTube»: the run's first watch page stayed
/// «youtube_playback_not_verified_watch_ready0_playing_network2_source_none» for the whole 45 s, and the next watch page
/// of the same profile (D-w14-t3) played in 6 s.
/// </summary>
[TestFixture]
public sealed class M89ProviderBudgetsTests
{
    private static readonly IReadOnlyList<InstalledApplicationEntry> Catalog =
    [
        new("Spotify", "SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify"),
    ];

    [Test]
    public async Task AFrontHandoffThatDoesNotAnswerLeavesTheOpenWindowObserved()
    {
        using var never = new ManualResetEventSlim(false);
        var platform = new HangingPlatform(Catalog) { ForegroundGate = never };
        var provider = new WindowsInstalledApplicationOpenProvider(platform);
        var clock = System.Diagnostics.Stopwatch.StartNew();

        ApplicationOpenResult result = await provider.OpenAsync(
            new ApplicationOpenRequest("Spotify", Guid.NewGuid().ToString("D")), CancellationToken.None);

        clock.Stop();
        never.Set();
        Assert.Multiple(() =>
        {
            Assert.That(result.Succeeded, Is.True);
            Assert.That(result.Verified, Is.True);
            Assert.That(result.AlreadyRunning, Is.True);
            Assert.That(platform.ActivateCalls, Is.Zero);
            Assert.That(clock.Elapsed, Is.LessThan(
                WindowsInstalledApplicationOpenProvider.ForegroundBudget + TimeSpan.FromSeconds(5)));
        });
    }

    [Test]
    public async Task ACatalogReadThatDoesNotAnswerEndsAsAnInventoryFailure()
    {
        var platform = new HangingPlatform(Catalog) { CatalogHangs = true };
        var provider = new WindowsInstalledApplicationOpenProvider(platform, TimeSpan.FromMilliseconds(200));
        var clock = System.Diagnostics.Stopwatch.StartNew();

        ApplicationOpenResult result = await provider.OpenAsync(
            new ApplicationOpenRequest("Spotify", Guid.NewGuid().ToString("D")), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Verified, Is.False);
            Assert.That(result.ErrorCode, Is.EqualTo(ApplicationOpenErrorCodes.InventoryFailed));
            Assert.That(platform.CatalogCancelled, Is.True);
            Assert.That(clock.Elapsed, Is.LessThan(TimeSpan.FromSeconds(10)));
        });
    }

    [Test]
    public void TheBudgetsEndWellInsideTheShellsWait()
    {
        // The shell waits 90 s for a core response before it restarts the core.
        TimeSpan worst = WindowsInstalledApplicationOpenProvider.DefaultCatalogReadBudget
            + WindowsInstalledApplicationOpenProvider.ForegroundBudget
            + WindowsInstalledApplicationOpenProvider.VerificationBudget;
        Assert.That(worst, Is.LessThan(TimeSpan.FromSeconds(60)));
    }

    [TestCase(true, "0", "none", true)] // v3r D-w10-t4: ready0 playing network2 source none
    [TestCase(true, "0", "consent", false)]
    [TestCase(true, "0", "bot", false)]
    [TestCase(true, "0", "unavailable", false)]
    [TestCase(true, "2", "none", false)]
    [TestCase(false, "0", "none", false)]
    public void AWatchPageWithNoDataAndNoGateIsAStalledLoad(bool watchPage, string ready, string gate, bool stalled)
    {
        Assert.That(CdpBrowserSession.YouTubeWatchPageStalled(watchPage, ready, gate), Is.EqualTo(stalled));
        Assert.That(CdpBrowserSession.YouTubeStallReloadAttempt * 250, Is.EqualTo(15_000));
    }

    private sealed class HangingPlatform(IReadOnlyList<InstalledApplicationEntry> catalog)
        : IInstalledApplicationPlatform
    {
        public ManualResetEventSlim? ForegroundGate { get; init; }

        public bool CatalogHangs { get; init; }

        public bool CatalogCancelled { get; private set; }

        public int ActivateCalls { get; private set; }

        public async ValueTask<IReadOnlyList<InstalledApplicationEntry>> ReadCatalogAsync(
            CancellationToken cancellationToken)
        {
            if (!CatalogHangs)
            {
                return catalog;
            }

            try
            {
                await Task.Delay(Timeout.Infinite, cancellationToken).ConfigureAwait(false);
            }
            catch (OperationCanceledException)
            {
                CatalogCancelled = true;
                throw;
            }

            return catalog;
        }

        public IReadOnlyList<InstalledApplicationObservation> Inventory(InstalledApplicationEntry entry) =>
        [
            new(
                ProcessId: 5150,
                ProcessCreationTimeUtcTicks: new DateTime(2026, 9, 30, 20, 0, 0, DateTimeKind.Utc).Ticks,
                ExecutablePath: @"C:\Program Files\WindowsApps\SpotifyAB.SpotifyMusic\Spotify.exe",
                WindowHandle: 91,
                Visible: true,
                Foreground: false),
        ];

        public bool Activate(InstalledApplicationEntry entry)
        {
            ActivateCalls++;
            return true;
        }

        public void RequestForeground(long windowHandle) => ForegroundGate?.Wait();

        public ValueTask DelayAsync(TimeSpan delay, CancellationToken cancellationToken) => ValueTask.CompletedTask;
    }
}
