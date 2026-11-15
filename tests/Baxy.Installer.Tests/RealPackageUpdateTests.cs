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
        await using (FileStream json = File.OpenRead(Path.Combine(twin, "release.json")))
        {
            carried = ReleaseManifest.Parse(json);
        }

        FileManifest? files = FileManifest.Named(await File.ReadAllBytesAsync(Path.Combine(twin, "files.json")), carried);
        Assert.That(files, Is.Not.Null, "files.json is the one release.json names");
        ReleaseManifest chosen = carried.ForMachine(MachineGpu.Installed());
        List<string> steps = [];
        List<string> log = [];
        using HttpClient http = new() { Timeout = Timeout.InfiniteTimeSpan };
        SilentUpdate update = SilentUpdate.Over(
            carried,
            chosen,
            files,
            paths,
            http,
            ReleaseSignature.Blocks(await File.ReadAllTextAsync(Need("AUT1_KEYS"))),
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
        JsonObject result = new()
        {
            ["case"] = which,
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
        };
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
