using Baxy.App;
using NUnit.Framework;
using System.Diagnostics;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class MindRuntimeStartupOverlapBenchmarkTests
{
    private static readonly JsonSerializerOptions IndentedJson =
        new() { WriteIndented = true };

    [Test]
    [Explicit("A/B headless de verificación SHA y hello de Core; no es una compuerta temporal.")]
    [NonParallelizable]
    public async Task SequentialVersusOverlappedRuntimeVerificationAndCoreHello()
    {
        const int pairs = 6;
        string manifest = MindRuntimeDiscovery.DefaultRegistrationPath();
        Assert.That(File.Exists(manifest), Is.True);
        string localData = Environment.GetFolderPath(
            Environment.SpecialFolder.LocalApplicationData);
        string privateParent = Path.Combine(localData, "BAXY");
        string prefix = "startup-overlap-benchmark-" + Guid.NewGuid().ToString("N");
        string? previousDataRoot = Environment.GetEnvironmentVariable("BAXY_DATA_DIR");
        var createdRoots = new List<string>();
        var samples = new List<StartupSample>();
        try
        {
            for (int pair = 0; pair < pairs; pair++)
            {
                bool[] order = pair % 2 == 0
                    ? [false, true]
                    : [true, false];
                foreach (bool overlapped in order)
                {
                    string dataRoot = Path.Combine(
                        privateParent,
                        $"{prefix}-pair-{pair:D2}-{(overlapped ? "overlap" : "sequential")}");
                    createdRoots.Add(dataRoot);
                    samples.Add(await MeasureAsync(pair, overlapped, manifest, dataRoot));
                }
            }

            string[] catalogHashes = samples
                .Select(static sample => sample.CatalogSha256)
                .Distinct(StringComparer.Ordinal)
                .ToArray();
            Assert.Multiple(() =>
            {
                Assert.That(samples, Has.Count.EqualTo(pairs * 2));
                Assert.That(samples.All(static sample => sample.RuntimeVerified), Is.True);
                Assert.That(samples.All(static sample => sample.CoreReady), Is.True);
                Assert.That(catalogHashes, Has.Length.EqualTo(1));
            });

            double[] sequential = samples
                .Where(static sample => !sample.Overlapped)
                .Select(static sample => sample.TotalMilliseconds)
                .ToArray();
            double[] overlap = samples
                .Where(static sample => sample.Overlapped)
                .Select(static sample => sample.TotalMilliseconds)
                .ToArray();
            double[] pairedDeltas = Enumerable.Range(0, pairs)
                .Select(pair =>
                    samples.Single(sample => sample.Pair == pair && sample.Overlapped)
                        .TotalMilliseconds
                    - samples.Single(sample => sample.Pair == pair && !sample.Overlapped)
                        .TotalMilliseconds)
                .ToArray();
            var report = new
            {
                schema = "baxy.mind-runtime-core-overlap-ab.v1",
                pairs,
                sequential_p50_ms = Median(sequential),
                overlap_p50_ms = Median(overlap),
                overlap_minus_sequential_paired_p50_ms = Median(pairedDeltas),
                overlap_wins = pairedDeltas.Count(static delta => delta < 0),
                samples,
            };
            TestContext.Progress.WriteLine(JsonSerializer.Serialize(report, IndentedJson));
        }
        finally
        {
            Environment.SetEnvironmentVariable("BAXY_DATA_DIR", previousDataRoot);
            foreach (string createdRoot in createdRoots)
            {
                if (Directory.Exists(createdRoot))
                {
                    Directory.Delete(createdRoot, recursive: true);
                }
            }
        }
    }

    private static async Task<StartupSample> MeasureAsync(
        int pair,
        bool overlapped,
        string manifest,
        string dataRoot)
    {
        Directory.CreateDirectory(dataRoot);
        Environment.SetEnvironmentVariable("BAXY_DATA_DIR", dataRoot);
        await using var core = new CoreProcessClient();
        var total = Stopwatch.StartNew();
        Task<TimedDiscovery> discoveryTask;
        if (overlapped)
        {
            discoveryTask = Task.Run(() => Discover(manifest));
            Task<TimedCore> coreTask = MeasureCoreAsync(core);
            TimedDiscovery discovery = await discoveryTask;
            TimedCore coreMeasurement = await coreTask;
            total.Stop();
            return CreateSample(pair, true, total, coreMeasurement, discovery, core);
        }

        discoveryTask = Task.Run(() => Discover(manifest));
        TimedDiscovery sequentialDiscovery = await discoveryTask;
        TimedCore sequentialCore = await MeasureCoreAsync(core);
        total.Stop();
        return CreateSample(pair, false, total, sequentialCore, sequentialDiscovery, core);
    }

    private static async Task<TimedCore> MeasureCoreAsync(CoreProcessClient core)
    {
        var timer = Stopwatch.StartNew();
        await core.StartAsync(TimeSpan.FromSeconds(20), CancellationToken.None);
        timer.Stop();
        return new(timer.Elapsed.TotalMilliseconds);
    }

    private static TimedDiscovery Discover(string manifest)
    {
        var timer = Stopwatch.StartNew();
        MindRuntimeDiscoveryResult result =
            MindRuntimeDiscovery.DiscoverVerified(manifest);
        timer.Stop();
        return new(result, timer.Elapsed.TotalMilliseconds);
    }

    private static StartupSample CreateSample(
        int pair,
        bool overlapped,
        Stopwatch total,
        TimedCore coreMeasurement,
        TimedDiscovery discovery,
        CoreProcessClient core)
    {
        string catalog = string.Join(
            '\n',
            core.ApplicationCatalog?.Names ?? Array.Empty<string>());
        string catalogSha256 = Convert.ToHexStringLower(
            SHA256.HashData(Encoding.UTF8.GetBytes(catalog)));
        return new(
            pair,
            overlapped,
            total.Elapsed.TotalMilliseconds,
            discovery.ElapsedMilliseconds,
            coreMeasurement.ElapsedMilliseconds,
            discovery.Result.CanConfigure && discovery.Result.Runtime is not null,
            core.IsReady,
            catalogSha256);
    }

    private static double Median(IEnumerable<double> values)
    {
        double[] ordered = values.Order().ToArray();
        int middle = ordered.Length / 2;
        return ordered.Length % 2 == 0
            ? (ordered[middle - 1] + ordered[middle]) / 2
            : ordered[middle];
    }

    private sealed record TimedDiscovery(
        MindRuntimeDiscoveryResult Result,
        double ElapsedMilliseconds);

    private sealed record TimedCore(double ElapsedMilliseconds);

    private sealed record StartupSample(
        int Pair,
        bool Overlapped,
        double TotalMilliseconds,
        double DiscoveryMilliseconds,
        double CoreMilliseconds,
        bool RuntimeVerified,
        bool CoreReady,
        string CatalogSha256);
}
