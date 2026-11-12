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

    // FIR1: the owner's key (its private half signs release.json, scripts/ReleaseSigning.cs) and another one.
    private static readonly ECDsa Owner = ECDsa.Create(ECCurve.NamedCurves.nistP256);
    private static readonly ECDsa Stranger = ECDsa.Create(ECCurve.NamedCurves.nistP256);
    private static readonly string[] OwnerKeys = [Owner.ExportSubjectPublicKeyInfoPem()];

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
            Assert.That(http.Asked[0], Is.EqualTo($"https://api.github.com/repos/{Repository}/releases/latest"));
            Assert.That(http.Asked.Skip(1), Is.EqualTo(new[] { Asset("v1.4.0", "release.json"), Asset("v1.4.0", "release.json.sig") }));
            Assert.That(http.UserAgents.Distinct(), Is.EqualTo(new[] { "BAXY/1.3.2" }));
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

    // UNI1 (REV8 S2): between checking the installer's SHA-256 and starting it, another program of the person's could
    // change the file in <data>\updates. It is held open, with no sharing for writing or deleting, from the check to the
    // start: what starts is what was checked.
    [Test]
    public async Task TheCheckedInstallerCannotBeChangedBeforeItStarts()
    {
        Mark(GitHubMarker);
        string? refused = null;
        var handler = new BaxyUpdateHandler(
            _data,
            BaxyDistribution.Read(App()),
            new Version(1, 3, 2),
            new HttpClient(new Server(Release("v1.4.0"))),
            start =>
            {
                try
                {
                    File.WriteAllBytes(start.FileName, [0x4D, 0x5A, 0x00]);
                }
                catch (IOException sharing)
                {
                    refused = sharing.GetType().Name;
                }

                return true;
            },
            @"Local\BAXY.Tests.UpdateExit.none." + Guid.NewGuid().ToString("N"),
            null,
            null,
            OwnerKeys);

        OperationOutcome outcome = await handler.ExecuteAsync(Invocation("install"), CancellationToken.None);

        Assert.That(outcome.Succeeded, Is.True);
        Assert.That(refused, Is.Not.Null, "another writer changed the installer between the check and the start");
        Assert.That(File.ReadAllBytes(Path.Combine(_data, "updates", "BAXY-Instalador-1.4.0.exe")), Is.EqualTo(InstallerBytes));
    }

    // UNI1 (REV8 S2), measured: Windows starts an exe that is held open for reading with no sharing for writing or deleting.
    [Test]
    public void AnExeHeldOpenWithReadSharingStillStarts()
    {
        string exe = Path.Combine(_data, "held-ping.exe");
        Directory.CreateDirectory(_data);
        File.Copy(Path.Combine(Environment.SystemDirectory, "PING.EXE"), exe);
        using FileStream held = new(exe, FileMode.Open, FileAccess.Read, FileShare.Read);
        using System.Diagnostics.Process started = System.Diagnostics.Process.Start(new ProcessStartInfo(exe, "-n 1 127.0.0.1")
        {
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
        })!;

        Assert.That(started.WaitForExit(10_000), Is.True);
        Assert.That(started.ExitCode, Is.Zero);
    }

    // FIR1 (decisión A1, 10-11-2026): whoever holds BAXY's GitHub account uploads an installer and GitHub computes its digest,
    // so the digest says nothing about who made it. What the App runs is what release.json says, under the owner's signature.
    [TestCase("missing", TestName = "FIR1_SinFirma_NoSeInstalaNada")]
    [TestCase("stranger", TestName = "FIR1_FirmaMala_NoSeInstalaNada")]
    [TestCase("changed", TestName = "FIR1_JsonCambiado_NoSeInstalaNada")]
    [TestCase("older", TestName = "FIR1_FirmaViejaValida_BajoUnaEtiquetaNueva_NoSeInstala")]
    [TestCase("installed", TestName = "FIR1_FirmaDeLaVersionInstalada_BajoUnaEtiquetaNueva_NoSeInstala")]
    public async Task AnInstallerIsRunOnlyUnderTheOwnersSignatureOfThatVersion(string attack)
    {
        Mark(GitHubMarker);
        List<ProcessStartInfo> started = [];
        Signed release = attack switch
        {
            "missing" => Signed.For("1.4.0") with { Signature = null },
            "stranger" => Signed.For("1.4.0", Stranger),
            "changed" => Signed.For("1.4.0").Changed("\"version\":\"1.4.0\"", "\"version\":\"1.4.0\" "),
            "older" => Signed.For("1.3.1"),
            _ => Signed.For("1.3.2"),
        };
        var http = new Server(Release("v1.4.0", signed: release));

        OperationOutcome install = await Handler(http, started).ExecuteAsync(Invocation("install"), CancellationToken.None);
        InvocationPreflightResult preflight = await Handler(new Server(Release("v1.4.0", signed: release)), started)
            .PreflightAsync(Arguments("install"), CancellationToken.None);
        OperationOutcome check = await Handler(new Server(Release("v1.4.0", signed: release)), started)
            .ExecuteAsync(Invocation("check"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(install.ErrorCode, Is.EqualTo("baxy_update_not_signed"));
            Assert.That(install.Retryable, Is.False);
            Assert.That(install.Result?.GetProperty("signature").GetString(),
                Is.EqualTo(attack switch { "missing" => "missing", "older" or "installed" => "version", _ => "invalid" }));
            Assert.That(preflight.Failure?.ErrorCode, Is.EqualTo("baxy_update_not_signed"), "no yes is asked for it");
            Assert.That(check.ErrorCode, Is.EqualTo("baxy_update_not_signed"), "a check never offers it as newer");
            Assert.That(started, Is.Empty);
            Assert.That(http.Asked, Has.None.EndsWith("/BAXY-Instalador.exe"), "its installer is not even downloaded");
            Assert.That(Directory.Exists(Path.Combine(_data, "updates")), Is.False, "nothing is left behind");
        });
    }

    // The account's holder uploads another exe: GitHub's digest is that exe's, release.json still names the owner's.
    [Test]
    public async Task AnInstallerThatMatchesGitHubsDigestButNotTheSignedOneIsNeverRun()
    {
        Mark(GitHubMarker);
        List<ProcessStartInfo> started = [];
        byte[] planted = Encoding.UTF8.GetBytes("MZ planted installer!");
        var http = new Server(Release("v1.4.0", digestOf: planted), installer: planted);

        OperationOutcome outcome = await Handler(http, started).ExecuteAsync(Invocation("install"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("baxy_update_hash_mismatch"));
            Assert.That(started, Is.Empty);
            Assert.That(Directory.EnumerateFiles(Path.Combine(_data, "updates")), Is.Empty);
        });
    }

    // A key being replaced: the BAXY that trusts the old and the new key takes a release signed by either.
    [Test]
    public async Task EitherOfTheBuiltInKeysSigns()
    {
        Mark(GitHubMarker);
        List<ProcessStartInfo> started = [];
        var http = new Server(Release("v1.4.0", signed: Signed.For("1.4.0", Stranger)));
        string[] both = [.. OwnerKeys, Stranger.ExportSubjectPublicKeyInfoPem()];

        OperationOutcome outcome = await Handler(http, started, keys: both).ExecuteAsync(Invocation("install"), CancellationToken.None);

        Assert.That(outcome.Succeeded, Is.True, outcome.ErrorCode);
        Assert.That(started, Has.Count.EqualTo(1));
    }

    // What every build carries: at least one P-256 public key, and the one in the repository is it.
    [Test]
    public void TheCoreCarriesTheRepositorysKeys()
    {
        IReadOnlyList<string> built = ReleaseSignature.BuiltInKeys(typeof(BaxyUpdateHandler).Assembly);
        string file = File.ReadAllText(Path.Combine(TestContext.CurrentContext.TestDirectory, "..", "..", "..", "..", "..",
            "release-keys", "update-keys.pem"));

        Assert.That(built, Is.Not.Empty);
        Assert.That(built, Is.EqualTo(ReleaseSignature.Blocks(file)));
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

    // UPD1 (REV10 m1): the view says «lo borré y no lo abrí» for baxy_update_hash_mismatch. An installer left under the
    // same name by an earlier try, or one that changed before it was opened, stayed in <data>\updates.
    [Test]
    public async Task AnInstallerThatIsNotThePublishedOneIsDeletedWhereverItWas()
    {
        Mark(GitHubMarker);
        List<ProcessStartInfo> started = [];
        string left = Path.Combine(_data, "updates", "BAXY-Instalador-1.4.0.exe");
        Directory.CreateDirectory(Path.GetDirectoryName(left)!);
        await File.WriteAllBytesAsync(left, Encoding.UTF8.GetBytes("MZ left by an earlier try"));
        var http = new Server(Release("v1.4.0"), installer: Encoding.UTF8.GetBytes("MZ something else!!!"));

        OperationOutcome outcome = await Handler(http, started).ExecuteAsync(Invocation("install"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("baxy_update_hash_mismatch"));
            Assert.That(started, Is.Empty);
            Assert.That(Directory.EnumerateFiles(Path.Combine(_data, "updates")), Is.Empty);
        });
    }

    // UPD1 (REV10 m2): a disk that filled up while the installer came left its .part and was told as «la descarga se cortó».
    [Test]
    public async Task ADiskThatFillsUpWhileDownloadingIsToldAsSuchAndLeavesNoPart()
    {
        Mark(GitHubMarker);
        List<ProcessStartInfo> started = [];
        var handler = Handler(new Server(Release("v1.4.0"), body: new FillsTheDisk(InstallerBytes[..4])), started);

        OperationOutcome outcome = await handler.ExecuteAsync(Invocation("install"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("baxy_update_disk_full"));
            Assert.That(outcome.Retryable, Is.False, "trying again at once fills it again");
            Assert.That(started, Is.Empty);
            Assert.That(Directory.EnumerateFiles(Path.Combine(_data, "updates")), Is.Empty);
        });
    }

    // A cut download leaves no .part either: the next try starts the file again (FileMode.Create).
    [Test]
    public async Task ACutDownloadLeavesNoPart()
    {
        Mark(GitHubMarker);
        List<ProcessStartInfo> started = [];
        var body = new Trickle(InstallerBytes, stopAfter: 4);
        var handler = Handler(new Server(Release("v1.4.0"), body: body), started, stall: TimeSpan.FromMilliseconds(300));

        OperationOutcome outcome = await handler.ExecuteAsync(Invocation("install"), CancellationToken.None);
        body.Release();

        Assert.That(outcome.ErrorCode, Is.EqualTo("baxy_update_download_failed"));
        Assert.That(Directory.EnumerateFiles(Path.Combine(_data, "updates")), Is.Empty);
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
                @"Local\BAXY.Tests.UpdateExit.none." + Guid.NewGuid().ToString("N"), keys: OwnerKeys);
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
        await RunAsync("baxy_update_not_signed", "install", new Server(Release("v1.4.0", signed: Signed.For("1.4.0", Stranger))));

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
        TimeSpan? budget = null,
        IReadOnlyList<string>? keys = null) => new(
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
        budget,
        keys ?? OwnerKeys);

    private static string Asset(string tag, string name) => $"https://github.com/REDSOULTM/BAXY/releases/download/{tag}/{name}";

    // GitHub's answer for a release: its installer with the digest GitHub computed of what was uploaded, and (FIR1) its
    // release.json and release.json.sig, by default the owner's for the tag's version.
    private static string Release(string tag, string flags = "{}", Signed? signed = null, byte[]? digestOf = null)
    {
        string digest = Convert.ToHexStringLower(SHA256.HashData(digestOf ?? InstallerBytes));
        signed ??= Signed.For(tag.TrimStart('v'));
        Served[tag] = signed;
        string files = $$"""{"name":"release.json","size":{{signed.Manifest.Length}},"digest":"sha256:{{Convert.ToHexStringLower(SHA256.HashData(signed.Manifest))}}","browser_download_url":"{{Asset(tag, "release.json")}}"}""";
        if (signed.Signature is { } signature)
        {
            files += $$""",{"name":"release.json.sig","size":{{signature.Length}},"digest":"sha256:0","browser_download_url":"{{Asset(tag, "release.json.sig")}}"}""";
        }

        string assets = $$"""[{"name":"BAXY-Instalador.exe","size":{{(digestOf ?? InstallerBytes).Length}},"digest":"sha256:{{digest}}","browser_download_url":"{{Asset(tag, "BAXY-Instalador.exe")}}"},{{files}}]""";
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

    // What Release() last gave each tag, for the Server to hand out (tests in a fixture run one at a time).
    private static readonly Dictionary<string, Signed> Served = [];

    /// <summary>A release.json as scripts/build_github_release.py writes it, and its .sig as scripts/ReleaseSigning.cs does.</summary>
    private sealed record Signed(byte[] Manifest, byte[]? Signature)
    {
        internal static Signed For(string version, ECDsa? key = null)
        {
            string sha = Convert.ToHexStringLower(SHA256.HashData(InstallerBytes));
            byte[] manifest = Encoding.UTF8.GetBytes($$$"""{"version":"{{{version}}}","baseUrl":"https://github.com/REDSOULTM/BAXY/releases/download/v{{{version}}}/","installedBytes":1,"archives":[{"name":"baxy-{{{version}}}.zip","parts":[{"file":"baxy-{{{version}}}.zip.000","bytes":1,"sha256":"{{{sha}}}"}]}],"installer":{"file":"BAXY-Instalador.exe","bytes":{{{InstallerBytes.Length}}},"sha256":"{{{sha}}}"}}""");
            return new Signed(manifest, Encoding.ASCII.GetBytes(Convert.ToBase64String((key ?? Owner).SignData(manifest, HashAlgorithmName.SHA256)) + "\n"));
        }

        internal Signed Changed(string from, string to) =>
            this with { Manifest = Encoding.UTF8.GetBytes(Encoding.UTF8.GetString(Manifest).Replace(from, to, StringComparison.Ordinal)) };
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
            Signed? signed = Served.FirstOrDefault(pair => url.Contains($"/download/{pair.Key}/", StringComparison.Ordinal)).Value;
            HttpResponseMessage response = url.EndsWith("/releases/latest", StringComparison.Ordinal)
                ? new HttpResponseMessage(HttpStatusCode.OK) { Content = new StringContent(release) }
                : url.EndsWith("/release.json", StringComparison.Ordinal) && signed is not null
                    ? new HttpResponseMessage(HttpStatusCode.OK) { Content = new ByteArrayContent(signed.Manifest) }
                : url.EndsWith("/release.json.sig", StringComparison.Ordinal) && signed?.Signature is { } signature
                    ? new HttpResponseMessage(HttpStatusCode.OK) { Content = new ByteArrayContent(signature) }
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

    /// <summary>
    /// A download on a disk that fills up: some bytes, then Windows' ERROR_DISK_FULL (0x70) as an IOException, as a write to
    /// a full disk gives it (Microsoft Learn, System Error Codes 0-499).
    /// </summary>
    private sealed class FillsTheDisk(byte[] first) : MemoryStream(first)
    {
        public override async ValueTask<int> ReadAsync(Memory<byte> buffer, CancellationToken cancellationToken = default)
        {
            int read = await base.ReadAsync(buffer, cancellationToken).ConfigureAwait(false);
            return read > 0 ? read : throw new IOException("There is not enough space on the disk.", unchecked((int)0x80070070));
        }
    }
}
