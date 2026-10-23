using System.Diagnostics;
using System.Globalization;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Renew al máximo (rendimiento) on the real desktop: media.play.query timed through the adapter, rounds of one call
/// with the script of the base (BAXY_SPOTIFY_BASE_SCRIPT, a copy of the script before the change, run in a process of
/// its own per call as before), one with that script in the persistent worker («worker») and one with this branch's
/// (the worker and 100 ms polls), the order rotating and the searches rotating so no call presses what already plays.
/// One untimed call of each first (the client up, the workers started). Never runs in a suite: Explicit and BAXY_SPOTIFY_TIMING_LIVE=1, with Spotify installed and signed
/// in, while no one uses the desktop; it plays music, and the person pauses and closes the client after.
/// </summary>
[TestFixture]
[Explicit("Plays music in the Spotify client on the person's desktop.")]
[Category("LiveDesktop")]
public sealed class SpotifyTimingLiveDesktopCheck
{
    private static readonly string[] Queries = ["clair de lune debussy", "gymnopedie 1 satie", "canon in d pachelbel"];

    [Test]
    public async Task MediaPlayQueryBaseAgainstBranch()
    {
        if (Environment.GetEnvironmentVariable("BAXY_SPOTIFY_TIMING_LIVE") != "1")
            Assert.Ignore("BAXY_SPOTIFY_TIMING_LIVE=1 is needed to touch the desktop.");
        string baseScript = Environment.GetEnvironmentVariable("BAXY_SPOTIFY_BASE_SCRIPT") ?? string.Empty;
        Assert.That(File.Exists(baseScript), Is.True, "BAXY_SPOTIFY_BASE_SCRIPT names the base's script");
        int rounds = int.TryParse(Environment.GetEnvironmentVariable("BAXY_SPOTIFY_TIMING_ROUNDS"), out int value) ? value : 12;
        string branchScript = Path.Combine(AppContext.BaseDirectory, "SpotifyDesktopAutomation.ps1");
        var baseline = new SpotifyDesktopAdapter(new ExternalProcessRunner(), baseScript);
        using var worker = new PowerShellScriptWorker(branchScript);
        var branch = new SpotifyDesktopAdapter(worker, branchScript);
        using var baseWorker = new PowerShellScriptWorker(baseScript);
        var workerOnly = new SpotifyDesktopAdapter(baseWorker, baseScript);
        var times = new Dictionary<string, List<double>> { ["base"] = [], ["worker"] = [], ["branch"] = [] };
        int call = 0;

        async Task Play(string name, SpotifyDesktopAdapter adapter, bool timed)
        {
            string query = Queries[call++ % Queries.Length];
            using JsonDocument arguments = JsonDocument.Parse(
                JsonSerializer.Serialize(new { provider = "spotify", query }));
            var clock = Stopwatch.StartNew();
            ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
                "media.play.query", arguments.RootElement, CancellationToken.None);
            clock.Stop();
            if (timed)
                times[name].Add(clock.Elapsed.TotalMilliseconds);
            TestContext.Out.WriteLine(string.Create(CultureInfo.InvariantCulture,
                $"{name}{(timed ? "" : " (untimed)")} «{query}»: {clock.Elapsed.TotalMilliseconds:F0} ms verified={receipt.Verified} "
                + $"error={receipt.ErrorCode} result={receipt.Result?.GetRawText()}"));
        }

        (string Name, SpotifyDesktopAdapter Adapter)[] arms = [("base", baseline), ("worker", workerOnly), ("branch", branch)];
        foreach ((string name, SpotifyDesktopAdapter adapter) in arms)
            await Play(name, adapter, timed: false);
        for (int round = 0; round < rounds; round++)
        {
            for (int arm = 0; arm < arms.Length; arm++)
            {
                (string name, SpotifyDesktopAdapter adapter) = arms[(round + arm) % arms.Length];
                await Play(name, adapter, timed: true);
            }
        }

        foreach ((string name, List<double> list) in times)
        {
            double[] sorted = [.. list.Order()];
            TestContext.Out.WriteLine(string.Create(CultureInfo.InvariantCulture,
                $"{name}: N={sorted.Length} p50={Percentile(sorted, 0.5):F0} ms p90={Percentile(sorted, 0.9):F0} ms "
                + $"min={sorted[0]:F0} max={sorted[^1]:F0}"));
        }
    }

    // Nearest-rank percentile.
    private static double Percentile(double[] sorted, double rank) =>
        sorted[Math.Clamp((int)Math.Ceiling(rank * sorted.Length) - 1, 0, sorted.Length - 1)];
}
