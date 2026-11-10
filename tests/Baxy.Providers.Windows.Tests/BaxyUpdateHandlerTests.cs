using System.Diagnostics;
using System.IO.Compression;
using System.Net;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// actualizar-ordenes-app (dueño, 2026-11-09: «un botón de actualizar y decirle BAXY actualízate»): BAXY knows where it was
/// published from the file its packager wrote (distribution.json), looks for GitHub's latest stable release, and moves to
/// it only with an installer whose bytes are the SHA-256 GitHub published. Steam and itch.io update it themselves: BAXY
/// opens their page and downloads nothing.
/// </summary>
[TestFixture]
public sealed class BaxyUpdateHandlerTests
{
    private const string Repository = "REDSOULTM/BAXY";
    private static readonly byte[] InstallerBytes = Encoding.UTF8.GetBytes("MZ installer of 1.4.0");

    private string _folder = string.Empty;
    private string _root = string.Empty;
    private string _data = string.Empty;

    [SetUp]
    public void SetUp()
    {
        _folder = Path.Combine(Path.GetTempPath(), "baxy-update-tests", Guid.NewGuid().ToString("N"));
        _root = Path.Combine(_folder, "BAXY-App");
        _data = Path.Combine(_folder, "data");
        Directory.CreateDirectory(Path.Combine(_root, "app"));
    }

    [TearDown]
    public void TearDown() => Directory.Delete(_folder, recursive: true);

    [Test]
    public void TheChannelIsTheOneItsPackagerWroteAndNoFileIsADevelopmentBuild()
    {
        Assert.That(BaxyDistribution.Read(App()).Channel, Is.EqualTo(BaxyDistribution.Development));

        Mark("""{"schema":"baxy.distribution.v1","channel":"github","repository":"REDSOULTM/BAXY"}""");
        BaxyDistribution github = BaxyDistribution.Read(App());
        Mark("""{"schema":"baxy.distribution.v1","channel":"steam"}""");
        BaxyDistribution steam = BaxyDistribution.Read(App());
        Mark("""{"schema":"baxy.distribution.v2","channel":"steam"}""");
        BaxyDistribution unknownSchema = BaxyDistribution.Read(App());
        Mark("""{"schema":"baxy.distribution.v1","channel":"github","repository":"../../evil"}""");
        BaxyDistribution badRepository = BaxyDistribution.Read(App());

        Assert.Multiple(() =>
        {
            Assert.That(github, Is.EqualTo(new BaxyDistribution("github", Path.GetFullPath(_root), Repository)));
            Assert.That(steam.Channel, Is.EqualTo("steam"));
            Assert.That(unknownSchema.Channel, Is.EqualTo(BaxyDistribution.Development));
            Assert.That(badRepository.Repository, Is.Null);
        });
    }

    /// <summary>AMD2 (installed 1.3.2 on an RX 7600, 2026-11-09): baxy-core.exe, which runs baxy.update, is published into
    /// app\core (scripts/build_product.ps1, CoreProcessClient), so the mark beside app\ is two folders up from it. Read from
    /// its own folder, the installed GitHub build said «development» and «BAXY, actualízate» never looked.</summary>
    [Test]
    public void TheCoreFindsTheMarkBesideAppAlthoughItRunsFromAppCore()
    {
        Directory.CreateDirectory(Path.Combine(_root, "app", "core"));
        Mark(GitHubMarker);

        BaxyDistribution core = BaxyDistribution.OfCore(Path.Combine(_root, "app", "core") + Path.DirectorySeparatorChar);

        Assert.That(core, Is.EqualTo(new BaxyDistribution("github", Path.GetFullPath(_root), Repository)));
    }

    [Test]
    public void ItchsPageComesFromTheReceiptAndOnlyWhenItIsItchIos()
    {
        Receipt("""{"game":{"url":"https://redsoultm.itch.io/baxy"}}""");
        Uri? page = new BaxyDistribution("itch", _root, null).ItchPage();
        Receipt("""{"game":{"url":"https://example.com/baxy"}}""");
        Uri? elsewhere = new BaxyDistribution("itch", _root, null).ItchPage();

        Assert.Multiple(() =>
        {
            Assert.That(page?.AbsoluteUri, Is.EqualTo("https://redsoultm.itch.io/baxy"));
            Assert.That(elsewhere, Is.Null);
        });
    }

    [TestCase("v1.3.1", "1.3.1")]
    [TestCase("1.3.2+abc1234.dirty", "1.3.2")]
    [TestCase("1.4.0-rc1", "1.4.0")]
    [TestCase("latest", null)]
    public void VersionsAreTheirFirstThreeNumbers(string text, string? expected) =>
        Assert.That(GitHubLatestRelease.ParseVersion(text)?.ToString(3), Is.EqualTo(expected));

    // GitHub's latest never is a prerelease or a draft; should one come, it is not offered.
    [TestCase("""{"prerelease":true}""")]
    [TestCase("""{"draft":true}""")]
    public void APrereleaseOrADraftIsNeverOffered(string flags)
    {
        using JsonDocument release = JsonDocument.Parse(Release("v1.4.0", flags));
        Assert.That(GitHubLatestRelease.Parse(release.RootElement), Is.Null);
    }

    [Test]
    public async Task CheckSaysTheNewerVersionAndItsSize()
    {
        Mark(GitHubMarker);
        var http = new Server(Release("v1.4.0"));

        JsonElement receipt = await ResultAsync(Handler(http), "check");

        Assert.Multiple(() =>
        {
            Assert.That(receipt.GetProperty("installed").GetString(), Is.EqualTo("1.3.2"));
            Assert.That(receipt.GetProperty("latest").GetString(), Is.EqualTo("1.4.0"));
            Assert.That(receipt.GetProperty("newer").GetBoolean(), Is.True);
            Assert.That(receipt.GetProperty("downloadBytes").GetInt64(), Is.EqualTo(InstallerBytes.Length));
            Assert.That(http.Asked.Single(), Is.EqualTo($"https://api.github.com/repos/{Repository}/releases/latest"));
            Assert.That(http.UserAgents.Single(), Is.EqualTo("BAXY/1.3.2"));
        });
    }

    [Test]
    public async Task InstallStartsTheCheckedInstallerOverThisFolderAndAsksTheAppToExit()
    {
        Mark(GitHubMarker);
        string exitName = @"Local\BAXY.Tests.UpdateExit." + Guid.NewGuid().ToString("N");
        using var exit = new EventWaitHandle(false, EventResetMode.AutoReset, exitName);
        List<ProcessStartInfo> started = [];
        var handler = Handler(new Server(Release("v1.4.0")), started, exitName);

        OperationOutcome outcome = await handler.ExecuteAsync(Invocation("install"), CancellationToken.None);
        string facts = OperationVisibleFacts.FromOutcome(BaxyUpdateHandler.Operation, outcome);
        ProcessStartInfo installer = started.Single();
        string kept = Path.Combine(_data, "updates", "BAXY-Instalador-1.4.0.exe");

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True);
            Assert.That(installer.FileName, Is.EqualTo(kept));
            Assert.That(installer.ArgumentList, Is.EqualTo(new[] { "--update", "--dir", Path.GetFullPath(_root) }));
            Assert.That(installer.WorkingDirectory, Does.Not.StartWith(_root));
            Assert.That(File.ReadAllBytes(kept), Is.EqualTo(InstallerBytes));
            Assert.That(exit.WaitOne(0), Is.True);
            Assert.That(JsonDocument.Parse(facts).RootElement.GetProperty("verification").GetString(),
                Is.EqualTo(OperationVisibleFacts.VerificationDeliveredOnly));
        });
    }

    // What came is not what GitHub published: deleted and never run.
    [Test]
    public async Task AnInstallerWhoseBytesAreNotThePublishedOnesIsNeverRun()
    {
        Mark(GitHubMarker);
        List<ProcessStartInfo> started = [];
        var http = new Server(Release("v1.4.0"), installer: Encoding.UTF8.GetBytes("MZ something else!!!"));

        OperationOutcome outcome = await Handler(http, started).ExecuteAsync(Invocation("install"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("baxy_update_hash_mismatch"));
            Assert.That(started, Is.Empty);
            Assert.That(Directory.EnumerateFiles(Path.Combine(_data, "updates")), Is.Empty);
        });
    }

    // REV_APP UPD-b (2026-11-09): HttpClient's timeout ends where the headers end («when using the ResponseHeadersRead
    // option, the timeout applies only up to where the headers end and the content starts»,
    // learn.microsoft.com/dotnet/api/system.net.http.httpcompletionoption), so a download that stopped dead waited for
    // ever: the App said «no sé si el instalador llegó a abrirse» at its limit and the engine could still start it.
    [Test]
    public async Task ADownloadThatStopsDeadIsCutAndTheInstallerIsNeverRun()
    {
        Mark(GitHubMarker);
        List<ProcessStartInfo> started = [];
        var body = new Trickle(InstallerBytes, stopAfter: 4);
        var handler = Handler(new Server(Release("v1.4.0"), body: body), started, stall: TimeSpan.FromMilliseconds(300));

        Task<OperationOutcome> install = handler.ExecuteAsync(Invocation("install"), CancellationToken.None).AsTask();
        bool ended = await Task.WhenAny(install, Task.Delay(TimeSpan.FromSeconds(10))) == install;
        body.Release();

        Assert.That(ended, Is.True, "a download that sends nothing more is cut");
        OperationOutcome outcome = await install;
        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("baxy_update_download_failed"));
            Assert.That(outcome.Retryable, Is.True);
            Assert.That(started, Is.Empty);
        });
    }

    // The engine answers before the App stops waiting for it (UpdateInstallerFile.Budget): a download too slow to end
    // by then is a failed download said as one, and no installer starts after the App said it did not know.
    [Test]
    public async Task ADownloadSlowerThanTheAppWaitsEndsAsFailedAndTheInstallerIsNeverRun()
    {
        Mark(GitHubMarker);
        List<ProcessStartInfo> started = [];
        var body = new Trickle(InstallerBytes, pause: TimeSpan.FromMilliseconds(100));
        var handler = Handler(new Server(Release("v1.4.0"), body: body), started, budget: TimeSpan.FromMilliseconds(250));

        OperationOutcome outcome = await handler.ExecuteAsync(Invocation("install"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("baxy_update_download_failed"));
            Assert.That(started, Is.Empty);
        });
    }

    // REV_APP COR-2 (2026-11-09): the copy went on past the bytes GitHub published, to the disk, until the sender ended.
    [Test]
    public async Task ADownloadIsCutAtThePublishedSize()
    {
        Mark(GitHubMarker);
        List<ProcessStartInfo> started = [];
        var body = new Trickle(new byte[64 << 20]);
        var handler = Handler(new Server(Release("v1.4.0"), body: body), started);

        OperationOutcome outcome = await handler.ExecuteAsync(Invocation("install"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("baxy_update_hash_mismatch"));
            Assert.That(started, Is.Empty);
            Assert.That(body.Sent, Is.LessThan(1 << 20), "nothing is read past the published size but the read in hand");
            Assert.That(Directory.EnumerateFiles(Path.Combine(_data, "updates")), Is.Empty);
        });
    }

    // No yes is asked for what cannot run, and the preflight never downloads nor starts anything.
    [Test]
    public async Task PreflightAsksNothingForAReadOrAStoreAndRefusesWhenThereIsNothingNewer()
    {
        Mark(GitHubMarker);
        List<ProcessStartInfo> started = [];
        InvocationPreflightResult check = await Handler(new Server(Release("v1.4.0")), started).PreflightAsync(Arguments("check"), CancellationToken.None);
        InvocationPreflightResult newer = await Handler(new Server(Release("v1.4.0")), started).PreflightAsync(Arguments("install"), CancellationToken.None);
        InvocationPreflightResult same = await Handler(new Server(Release("v1.3.2")), started).PreflightAsync(Arguments("install"), CancellationToken.None);
        Mark("""{"schema":"baxy.distribution.v1","channel":"steam"}""");
        InvocationPreflightResult steam = await Handler(new Server(Release("v1.4.0")), started).PreflightAsync(Arguments("install"), CancellationToken.None);
        File.Delete(Path.Combine(_root, BaxyDistribution.FileName));
        InvocationPreflightResult development = await Handler(new Server(Release("v1.4.0")), started).PreflightAsync(Arguments("install"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(check.Risk, Is.EqualTo(OperationRisk.ReadOnly));
            Assert.That(newer, Is.SameAs(InvocationPreflightResult.Proceed));
            Assert.That(same.Failure?.ErrorCode, Is.EqualTo("baxy_update_already_latest"));
            Assert.That(steam.Risk, Is.EqualTo(OperationRisk.Reversible));
            Assert.That(development.Failure?.ErrorCode, Is.EqualTo("baxy_update_development_build"));
            Assert.That(started, Is.Empty);
            Assert.That(Directory.Exists(Path.Combine(_data, "updates")), Is.False);
        });
    }

    // Steam updates what it installed: BAXY opens its library page and downloads nothing.
    [Test]
    public async Task OnSteamInstallOpensTheLibraryAndAsksNothingOfGitHub()
    {
        Mark("""{"schema":"baxy.distribution.v1","channel":"steam"}""");
        List<ProcessStartInfo> started = [];
        var http = new Server(Release("v1.4.0"));

        JsonElement checkedOnSteam = await ResultAsync(Handler(http, started), "check");
        OperationOutcome install = await Handler(http, started).ExecuteAsync(Invocation("install"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(checkedOnSteam.GetProperty("updatedBy").GetString(), Is.EqualTo("steam"));
            Assert.That(checkedOnSteam.GetProperty("storeUpdatesItself").GetBoolean(), Is.True);
            Assert.That(install.Succeeded, Is.True);
            Assert.That(started.Single().FileName, Is.EqualTo("steam://open/games"));
            Assert.That(started.Single().UseShellExecute, Is.True);
            Assert.That(http.Asked, Is.Empty);
        });
    }

    // MEN1-E (AMD2 §9, 2026-11-09: on a development build baxy.update failed before looking and the model answered «No
    // hay una versión más reciente»): nothing typed told «never looked» from «looked, and there is none» but the name of
    // the code. Every receipt now says whether this call read the latest version published; the mind says it in the
    // result's line for any tool (mind.NOT_CHECKED).
    [Test]
    public async Task TheReceiptSaysItDidNotCheckWhereTheLatestVersionWasNeverRead()
    {
        List<(string Code, OperationOutcome Outcome)> ends = [];
        async Task RunAsync(string code, string action, HttpMessageHandler http, bool opens = true)
        {
            var handler = new BaxyUpdateHandler(
                _data, BaxyDistribution.Read(App()), new Version(1, 3, 2), new HttpClient(http), _ => opens,
                @"Local\BAXY.Tests.UpdateExit.none." + Guid.NewGuid().ToString("N"));
            ends.Add((code, await handler.ExecuteAsync(Invocation(action), CancellationToken.None)));
        }

        await RunAsync("baxy_update_development_build", "check", new Server(Release("v1.4.0")));
        await RunAsync("baxy_update_development_build", "install", new Server(Release("v1.4.0")));
        Mark("""{"schema":"baxy.distribution.v1","channel":"github","repository":"../../evil"}""");
        await RunAsync("baxy_update_source_unknown", "check", new Server(Release("v1.4.0")));
        await RunAsync("baxy_update_source_unknown", "install", new Server(Release("v1.4.0")));
        Mark(GitHubMarker);
        await RunAsync("baxy_update_unreachable", "check", new Server("no release"));
        await RunAsync("baxy_update_unreachable", "install", new Server("no release"));
        await RunAsync("baxy_update_unreachable", "check", new Server(Release("v1.4.0", """{"prerelease":true}""")));
        Mark("""{"schema":"baxy.distribution.v1","channel":"steam"}""");
        await RunAsync("", "check", new Server(Release("v1.4.0")));
        await RunAsync("", "install", new Server(Release("v1.4.0")));
        await RunAsync("baxy_update_store_not_opened", "install", new Server(Release("v1.4.0")), opens: false);
        Mark("""{"schema":"baxy.distribution.v1","channel":"itch"}""");
        await RunAsync("", "check", new Server(Release("v1.4.0")));
        await RunAsync("baxy_update_by_itch_app", "install", new Server(Release("v1.4.0")));

        Assert.Multiple(() =>
        {
            foreach ((string code, OperationOutcome outcome) in ends)
            {
                Assert.That(outcome.ErrorCode ?? string.Empty, Is.EqualTo(code));
                Assert.That(Checked(outcome), Is.False, $"{code}: nothing read the latest version");
            }
        });
    }

    [Test]
    public async Task TheReceiptSaysItCheckedOnceTheLatestVersionWasRead()
    {
        Mark(GitHubMarker);
        List<(string Code, OperationOutcome Outcome)> ends = [];
        async Task RunAsync(string code, string action, Server http, bool starts = true)
        {
            var handler = new BaxyUpdateHandler(
                _data, BaxyDistribution.Read(App()), new Version(1, 3, 2), new HttpClient(http), _ => starts,
                @"Local\BAXY.Tests.UpdateExit.none." + Guid.NewGuid().ToString("N"));
            ends.Add((code, await handler.ExecuteAsync(Invocation(action), CancellationToken.None)));
        }

        await RunAsync("", "check", new Server(Release("v1.4.0")));
        await RunAsync("", "check", new Server(Release("v1.3.2")));
        await RunAsync("baxy_update_already_latest", "install", new Server(Release("v1.3.2")));
        await RunAsync("baxy_update_installer_missing", "install", new Server(Release("v1.4.0", """{"assets":[]}""")));
        await RunAsync("baxy_update_hash_mismatch", "install",
            new Server(Release("v1.4.0"), installer: Encoding.UTF8.GetBytes("MZ something else!!!")));
        await RunAsync("baxy_update_installer_not_started", "install", new Server(Release("v1.4.0")), starts: false);
        await RunAsync("", "install", new Server(Release("v1.4.0")));

        Assert.Multiple(() =>
        {
            foreach ((string code, OperationOutcome outcome) in ends)
            {
                Assert.That(outcome.ErrorCode ?? string.Empty, Is.EqualTo(code));
                Assert.That(Checked(outcome), Is.True, $"{code}: the latest version was read");
            }
        });
    }

    // What the model reads (OperationVisibleFacts.FromOutcome), byte for byte the receipts the measurement ran with
    // (scripts/renew/decisiones/casos/no_comprobado.json, nc-D1 and nc-K1's install).
    [Test]
    public async Task TheModelReadsWhetherTheLatestVersionWasRead()
    {
        OperationOutcome development = await Handler(new Server(Release("v1.4.0")))
            .ExecuteAsync(Invocation("check"), CancellationToken.None);
        Mark(GitHubMarker);
        OperationOutcome same = await Handler(new Server(Release("v1.3.2")))
            .ExecuteAsync(Invocation("install"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(OperationVisibleFacts.FromOutcome(BaxyUpdateHandler.Operation, development), Is.EqualTo(
                """{"status":"failed","error":"baxy_update_development_build","observed":{"version":1,"channel":"development","installed":"1.3.2","checked":false}}"""));
            Assert.That(OperationVisibleFacts.FromOutcome(BaxyUpdateHandler.Operation, same), Is.EqualTo(
                """{"status":"failed","error":"baxy_update_already_latest","observed":{"version":1,"channel":"github","installed":"1.3.2","checked":true,"latest":"1.3.2","newer":false}}"""));
        });
    }

    private static bool? Checked(OperationOutcome outcome) =>
        outcome.Result is { ValueKind: JsonValueKind.Object } result && result.TryGetProperty("checked", out JsonElement value)
        && value.ValueKind is JsonValueKind.True or JsonValueKind.False
            ? value.GetBoolean()
            : null;

    private const string GitHubMarker ="""{"schema":"baxy.distribution.v1","channel":"github","repository":"REDSOULTM/BAXY"}""";

    // INS-7: every update left its installer (about 80 MB) in <data>\updates for good. The version that starts removes
    // the ones that install it or an older one; a newer one, downloaded and not yet run, stays.
    [Test]
    public void AStartingVersionRemovesTheInstallersItNoLongerNeeds()
    {
        string updates = Path.Combine(_data, "updates");
        Directory.CreateDirectory(updates);
        string[] before =
        [
            "BAXY-Instalador-1.3.0.exe", "BAXY-Instalador-1.3.2.exe", "BAXY-Instalador-1.3.2.exe.part",
            "BAXY-Instalador-1.4.0.exe", "BAXY-Instalador-1.4.0.exe.part", "BAXY-Instalador-otra.exe", "notas.txt",
        ];
        foreach (string name in before)
        {
            File.WriteAllText(Path.Combine(updates, name), name);
        }

        BaxyUpdateHandler.RemoveInstallersUpTo(_data, new Version(1, 3, 2));

        Assert.That(
            Directory.EnumerateFiles(updates).Select(Path.GetFileName).Order(StringComparer.Ordinal),
            Is.EqualTo(new[] { "BAXY-Instalador-1.4.0.exe", "BAXY-Instalador-1.4.0.exe.part", "BAXY-Instalador-otra.exe", "notas.txt" }));
    }

    // The installer that just opened this BAXY may still be closing: Windows refuses to delete a file in use.
    [Test]
    public void AnInstallerStillInUseIsLeftForTheNextStart()
    {
        string updates = Path.Combine(_data, "updates");
        Directory.CreateDirectory(updates);
        string running = Path.Combine(updates, "BAXY-Instalador-1.3.2.exe");
        string older = Path.Combine(updates, "BAXY-Instalador-1.3.1.exe");
        File.WriteAllText(running, "running");
        File.WriteAllText(older, "older");

        using (new FileStream(running, FileMode.Open, FileAccess.Read, FileShare.None))
        {
            Assert.That(() => BaxyUpdateHandler.RemoveInstallersUpTo(_data, new Version(1, 3, 2)), Throws.Nothing);
            Assert.That(File.Exists(older), Is.False);
        }

        Assert.That(File.Exists(running), Is.True);
        BaxyUpdateHandler.RemoveInstallersUpTo(_data, new Version(1, 3, 2));
        Assert.That(File.Exists(running), Is.False);
    }

    [Test]
    public void ABaxyThatNeverUpdatedHasNothingToRemove()
    {
        Assert.That(() => BaxyUpdateHandler.RemoveInstallersUpTo(_data, new Version(1, 3, 2)), Throws.Nothing);
        Assert.That(Directory.Exists(Path.Combine(_data, "updates")), Is.False);
    }

    private string App() => Path.Combine(_root, "app");

    private void Mark(string json) => File.WriteAllText(Path.Combine(_root, BaxyDistribution.FileName), json);

    private void Receipt(string json)
    {
        Directory.CreateDirectory(Path.Combine(_root, ".itch"));
        using FileStream file = File.Create(Path.Combine(_root, ".itch", "receipt.json.gz"));
        using GZipStream zipped = new(file, CompressionLevel.Fastest);
        zipped.Write(Encoding.UTF8.GetBytes(json));
    }

    private BaxyUpdateHandler Handler(
        Server http,
        List<ProcessStartInfo>? started = null,
        string? exitName = null,
        TimeSpan? stall = null,
        TimeSpan? budget = null) => new(
        _data,
        BaxyDistribution.Read(App()),
        new Version(1, 3, 2),
        new HttpClient(http),
        start =>
        {
            started?.Add(start);
            return true;
        },
        exitName ?? @"Local\BAXY.Tests.UpdateExit.none." + Guid.NewGuid().ToString("N"),
        stall,
        budget);

    private static string Release(string tag, string flags = "{}")
    {
        string digest = Convert.ToHexStringLower(SHA256.HashData(InstallerBytes));
        string assets = $$"""[{"name":"BAXY-Instalador.exe","size":{{InstallerBytes.Length}},"digest":"sha256:{{digest}}","browser_download_url":"https://github.com/REDSOULTM/BAXY/releases/download/{{tag}}/BAXY-Instalador.exe"}]""";
        string release = $$"""{"tag_name":"{{tag}}","html_url":"https://github.com/REDSOULTM/BAXY/releases/tag/{{tag}}","draft":false,"prerelease":false,"assets":{{assets}}}""";
        using JsonDocument merged = JsonDocument.Parse(release);
        using JsonDocument extra = JsonDocument.Parse(flags);
        Dictionary<string, JsonElement> fields = merged.RootElement.EnumerateObject().ToDictionary(p => p.Name, p => p.Value.Clone());
        foreach (JsonProperty flag in extra.RootElement.EnumerateObject())
        {
            fields[flag.Name] = flag.Value.Clone();
        }

        return JsonSerializer.Serialize(fields);
    }

    private static JsonElement Arguments(string action) => JsonDocument.Parse($$"""{"action":"{{action}}"}""").RootElement.Clone();

    private static OperationInvocation Invocation(string action) => new("request", "mission", "invocation", Arguments(action));

    private static async Task<JsonElement> ResultAsync(BaxyUpdateHandler handler, string action)
    {
        OperationOutcome outcome = await handler.ExecuteAsync(Invocation(action), CancellationToken.None);
        Assert.That(outcome.Succeeded, Is.True, outcome.ErrorCode);
        return outcome.Result ?? default;
    }

    /// <summary>GitHub's API and its download, from memory.</summary>
    private sealed class Server(string release, byte[]? installer = null, Stream? body = null) : HttpMessageHandler
    {
        internal List<string> Asked { get; } = [];

        internal List<string> UserAgents { get; } = [];

        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        {
            string url = request.RequestUri?.AbsoluteUri ?? string.Empty;
            Asked.Add(url);
            UserAgents.Add(request.Headers.UserAgent.ToString());
            HttpResponseMessage response = url.EndsWith("/releases/latest", StringComparison.Ordinal)
                ? new HttpResponseMessage(HttpStatusCode.OK) { Content = new StringContent(release) }
                : url.EndsWith("/BAXY-Instalador.exe", StringComparison.Ordinal)
                    ? new HttpResponseMessage(HttpStatusCode.OK)
                    {
                        Content = body is null ? new ByteArrayContent(installer ?? InstallerBytes) : new StreamContent(body),
                    }
                    : new HttpResponseMessage(HttpStatusCode.NotFound);
            return Task.FromResult(response);
        }
    }

    /// <summary>A download's body as a line gives it: a few bytes at a time, with a pause, or none after some.</summary>
    private sealed class Trickle(byte[] bytes, TimeSpan? pause = null, int? stopAfter = null) : Stream
    {
        private readonly TaskCompletionSource _released = new(TaskCreationOptions.RunContinuationsAsynchronously);
        private int _sent;

        internal int Sent => Volatile.Read(ref _sent);

        public override bool CanRead => true;

        public override bool CanSeek => false;

        public override bool CanWrite => false;

        public override long Length => throw new NotSupportedException();

        public override long Position
        {
            get => throw new NotSupportedException();
            set => throw new NotSupportedException();
        }

        internal void Release() => _released.TrySetResult();

        public override async ValueTask<int> ReadAsync(Memory<byte> buffer, CancellationToken cancellationToken = default)
        {
            if (stopAfter is { } limit && _sent >= limit)
            {
                await _released.Task.WaitAsync(cancellationToken).ConfigureAwait(false);
                return 0;
            }

            if (pause is { } wait)
            {
                await Task.Delay(wait, cancellationToken).ConfigureAwait(false);
            }

            int most = pause is null && stopAfter is null ? buffer.Length : 4;
            int count = Math.Min(Math.Min(most, buffer.Length), bytes.Length - _sent);
            bytes.AsMemory(_sent, count).CopyTo(buffer);
            _sent += count;
            return count;
        }

        public override Task<int> ReadAsync(byte[] buffer, int offset, int count, CancellationToken cancellationToken) =>
            ReadAsync(buffer.AsMemory(offset, count), cancellationToken).AsTask();

        public override int Read(byte[] buffer, int offset, int count) => throw new NotSupportedException();

        public override void Flush()
        {
        }

        public override long Seek(long offset, SeekOrigin origin) => throw new NotSupportedException();

        public override void SetLength(long value) => throw new NotSupportedException();

        public override void Write(byte[] buffer, int offset, int count) => throw new NotSupportedException();
    }
}
