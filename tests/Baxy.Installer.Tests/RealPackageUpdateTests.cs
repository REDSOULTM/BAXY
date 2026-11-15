using System.Diagnostics;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Core.Operations;
using NUnit.Framework;

namespace Baxy.Installer.Tests;

/// <summary>
/// AUT1: the update with no window (<see cref="SilentUpdate.Over"/>) over a real package, end to end: a real BAXY
/// folder, the real parts served by a local server, the signature checked with the test key. It runs only when asked
/// (documentacion/ACTUALIZAR_SOLA.md, «Prueba de punta a punta»), with what to use in the environment:
/// <list type="bullet">
/// <item>AUT1_ROOT: the installed BAXY (a copy made for the test: it is replaced).</item>
/// <item>AUT1_TWIN: the folder with the twin's release.json and files.json (the installer carries these two).</item>
/// <item>AUT1_KEYS: the public key (PEM) the signature is checked with.</item>
/// <item>AUT1_TOLD: the folder where the outcome is written (the profile's updates folder, in a real run).</item>
/// <item>AUT1_CASE: ok, no_start (the new BAXY ends without saying it started), hang (it never says it), busy (BAXY
/// never closes), disk (no room on the drive).</item>
/// <item>AUT1_RESULT: where what happened is written, as JSON.</item>
/// <item>AUT2_RELEASE (AUT2): the address of a newer release, which this installer applies as the one BAXY already has
/// does with --release (SignedRelease.ReadAsync, its version as AUT2_OWN); AUT2_FETCH=1: first what --fetch does with
/// BAXY open (Installation.FetchAsync), told apart in the result.</item>
/// </list>
/// What only a real machine has is stood in for: nothing is registered in Windows and no BAXY is opened; the stand-in
/// for the new BAXY confirms as the App does (LastUpdate.OnStart), by the version of the exe that is in the folder.
/// </summary>
[TestFixture]
[Explicit("Needs a real package served on this machine; see documentacion/ACTUALIZAR_SOLA.md")]
internal sealed class RealPackageUpdateTests
{
    [Test]
    public async Task The_update_with_no_window_over_a_real_package()
    {
        string Need(string name) => Environment.GetEnvironmentVariable(name) is { Length: > 0 } value
            ? value
            : throw new IgnoreException($"{name} is not set");
        InstallPaths paths = new(Need("AUT1_ROOT"));
        string twin = Need("AUT1_TWIN");
        string told = Need("AUT1_TOLD");
        string which = Need("AUT1_CASE");
        Directory.CreateDirectory(told);
        ReleaseManifest carried;
        FileManifest? files;
        IReadOnlyList<string> keys = ReleaseSignature.Blocks(await File.ReadAllTextAsync(Need("AUT1_KEYS")));
        using HttpClient http = new() { Timeout = Timeout.InfiniteTimeSpan };
        JsonObject result = new() { ["case"] = which };
        Stopwatch read = Stopwatch.StartNew();
        if (Environment.GetEnvironmentVariable("AUT2_RELEASE") is { Length: > 0 } release)
        {
            try
            {
                (carried, files) = await SignedRelease.ReadAsync(
                    http, new Uri(release), keys, Need("AUT2_OWN"), AcceptedAgreement.Current, CancellationToken.None);
            }
            catch (Exception refused) when (refused is UnsignedReleaseException or InstallerTooOldException or HttpRequestException)
            {
                // As the installer refuses it (Program.Applied): nothing is downloaded nor changed.
                result["refused"] = refused.GetType().Name;
                result["seconds"] = Math.Round(read.Elapsed.TotalSeconds, 1);
                result["installedNow"] = SignedRelease.InstalledVersion(paths.App)?.ToString(3);
                await File.WriteAllTextAsync(Need("AUT1_RESULT"), result.ToJsonString(new JsonSerializerOptions { WriteIndented = true }));
                return;
            }
        }
        else
        {
            await using (FileStream json = File.OpenRead(Path.Combine(twin, "release.json")))
            {
                carried = ReleaseManifest.Parse(json);
            }

            files = FileManifest.Named(await File.ReadAllBytesAsync(Path.Combine(twin, "files.json")), carried);
        }

        Assert.That(files, Is.Not.Null, "files.json is the one release.json names");
        ReleaseManifest chosen = carried.ForMachine(MachineGpu.Installed());
        List<string> steps = [];
        List<string> log = [];
        if (Environment.GetEnvironmentVariable("AUT2_FETCH") == "1")
        {
            // With BAXY open: nothing of the installation is touched, and how far it is gets written as --fetch writes it.
            Installation fetching = new(chosen, paths, new PartFetcher(http), files: files, ranges: new RangeFetcher(http))
            {
                FreeBytes = which == "disk" ? () => 50L << 20 : () => new DriveInfo(Path.GetPathRoot(paths.Root)!).AvailableFreeSpace,
            };
            FetchProgress progress = new(told, chosen.Version);
            List<long> told10 = [];
            Stopwatch fetchClock = Stopwatch.StartNew();
            string? fetchFailed = null;
            try
            {
                await fetching.FetchAsync((phase, done, total) =>
                {
                    progress.Report(phase, done, total);
                    if (told10.Count == 0 || done * 10 / Math.Max(total, 1) > told10[^1])
                    {
                        told10.Add(done * 10 / Math.Max(total, 1));
                    }
                }, CancellationToken.None);
                progress.End(fetching.DownloadedBytes, fetching.NeededBytes);
            }
#pragma warning disable CA1031 // As --fetch does: the progress file says why.
            catch (Exception failure)
#pragma warning restore CA1031
            {
                fetchFailed = SilentUpdate.Reason(Failures.Classify(failure, () => false));
                progress.Fail(fetchFailed, fetching.DownloadedBytes);
            }

            result["fetch"] = new JsonObject
            {
                ["seconds"] = Math.Round(fetchClock.Elapsed.TotalSeconds, 1),
                ["downloadedBytes"] = fetching.DownloadedBytes,
                ["neededBytes"] = fetching.NeededBytes,
                ["failed"] = fetchFailed,
                ["tenths"] = new JsonArray([.. told10.Select(tenth => JsonValue.Create(tenth))]),
                ["progressFile"] = JsonNode.Parse(await File.ReadAllTextAsync(Path.Combine(told, FetchProgress.FileName))),
                ["installedNow"] = SignedRelease.InstalledVersion(paths.App)?.ToString(3),
            };
            if (fetchFailed is not null)
            {
                await File.WriteAllTextAsync(Need("AUT1_RESULT"), result.ToJsonString(new JsonSerializerOptions { WriteIndented = true }));
                return;
            }
        }

        SilentUpdate update = SilentUpdate.Over(
            carried,
            chosen,
            files,
            paths,
            http,
            keys,
            told,
            () => which == "busy",
            _ => Task.CompletedTask,
            () => steps.Add("register"),
            () => steps.Add("unregister"),
            () =>
            {
                steps.Add("open " + SignedRelease.InstalledVersion(paths.App)?.ToString(3));
                return which switch
                {
                    "no_start" => new StartedBaxy(() => true, () => steps.Add("stop")),
                    "hang" => new StartedBaxy(() => false, () => steps.Add("stop")),
                    _ => StandIn(paths, told, steps),
                };
            },
            line => steps.Add("say " + line),
            log.Add,
            which == "disk" ? () => 50L << 20 : null) with
        {
            CloseLimit = TimeSpan.FromSeconds(3),
            StartLimit = TimeSpan.FromSeconds(which == "hang" ? 5 : 60),
        };

        Stopwatch clock = Stopwatch.StartNew();
        int exit = await update.RunAsync();
        clock.Stop();

        UpdateOutcome? outcome = UpdateOutcome.Read(told);
        foreach ((string key, JsonNode? value) in new JsonObject
        {
            ["exit"] = exit,
            ["seconds"] = Math.Round(clock.Elapsed.TotalSeconds, 1),
            ["from"] = outcome?.From,
            ["to"] = outcome?.To,
            ["state"] = outcome?.State,
            ["reason"] = outcome?.Reason,
            ["downloadedBytes"] = outcome?.DownloadedBytes,
            ["installedNow"] = SignedRelease.InstalledVersion(paths.App)?.ToString(3),
            ["previousKept"] = Directory.Exists(paths.Previous),
            ["stagingLeft"] = Directory.Exists(paths.Staging),
            ["downloadsLeft"] = Directory.Exists(paths.Downloads),
            ["steps"] = new JsonArray([.. steps.Select(step => JsonValue.Create(step))]),
            ["log"] = new JsonArray([.. log.Select(line => JsonValue.Create(line.Length > 400 ? line[..400] : line))]),
        })
        {
            result[key] = value?.DeepClone();
        }

        await File.WriteAllTextAsync(Need("AUT1_RESULT"), result.ToJsonString(new JsonSerializerOptions { WriteIndented = true }));
        TestContext.Out.WriteLine(result.ToJsonString());
        Assert.That(outcome, Is.Not.Null, "every way out is written");
    }

    // The new BAXY as the App behaves once its engine is ready: it confirms the update that names its own version.
    private static StartedBaxy StandIn(InstallPaths paths, string told, List<string> steps)
    {
        string? version = SignedRelease.InstalledVersion(paths.App)?.ToString(3);
        if (version is not null && UpdateOutcome.Read(told) is { State: UpdateOutcome.Started } outcome && outcome.To == version)
        {
            UpdateOutcome.Confirm(told, version);
            steps.Add("confirm " + version);
        }

        return new StartedBaxy(() => false, () => steps.Add("stop"));
    }
}
