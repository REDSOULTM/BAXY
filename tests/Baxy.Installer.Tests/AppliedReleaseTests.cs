using System.Net;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using NUnit.Framework;

namespace Baxy.Installer.Tests;

/// <summary>
/// AUT2 (orden del dueño, 13-11-2026: «No debe volver a descargar nada que ya exista»): the installer BAXY already has
/// applies a newer signed release instead of the release's own installer being downloaded, only when the release says it
/// is enough and brings the agreement it carries; and --fetch only downloads, telling how far it is.
/// </summary>
[TestFixture]
internal sealed class AppliedReleaseTests
{
    private const string Address = "https://example.test/v2.0.0/";
    private const string Agreement = "1111111111111111111111111111111111111111111111111111111111111111";
    private static readonly ECDsa Owner = ECDsa.Create(ECCurve.NamedCurves.nistP256);
    private static readonly string[] OwnerKeys = [Owner.ExportSubjectPublicKeyInfoPem()];
    private string directory = string.Empty;

    [SetUp]
    public void SetUp()
    {
        directory = Path.Combine(Path.GetTempPath(), "baxy-installer-tests", Path.GetRandomFileName());
        Directory.CreateDirectory(directory);
    }

    [TearDown]
    public void TearDown() => Directory.Delete(directory, recursive: true);

    [TestCase("--update --fetch --dir C:\\BAXY", true, null)]
    [TestCase("--update --dir C:\\BAXY --release https://example.test/v2.0.0/", false, "https://example.test/v2.0.0/")]
    [TestCase("--update --fetch --release=https://example.test/v2.0.0/", true, "https://example.test/v2.0.0/")]
    public void Fetch_and_release_go_with_update(string line, bool fetch, string? release)
    {
        CommandLine command = CommandLine.Parse(line.Split(' '));

        Assert.That(command.Error, Is.Null);
        Assert.That((command.Update, command.Fetch, command.Release), Is.EqualTo((true, fetch, release)));
    }

    [TestCase("--fetch")]
    [TestCase("--update --quiet --fetch")]
    [TestCase("--release https://example.test/v2.0.0/")]
    [TestCase("--update --release https://example.test/v2.0.0")]
    [TestCase("--update --release not-an-address/")]
    public void Without_update_or_with_quiet_or_a_bad_address_they_are_refused(string line) =>
        Assert.That(CommandLine.Parse(line.Split(' ')).Error, Is.Not.Null);

    [Test]
    public async Task A_newer_signed_release_this_installer_is_enough_for_is_read_with_its_files()
    {
        Served served = new(Release("1.5.3"));
        using HttpClient http = new(served);

        (ReleaseManifest manifest, FileManifest files) = await SignedRelease.ReadAsync(
            http, new Uri(Address), OwnerKeys, "1.5.3+abc", Agreement, CancellationToken.None);

        Assert.That(manifest.Version, Is.EqualTo("2.0.0"));
        Assert.That(files.Files.Single().Path, Is.EqualTo("app/Baxy.exe"));
        Assert.That(served.Asked, Is.EqualTo(new[] { "release.json", "release.json.sig", "files.json" }));
    }

    [TestCase("1.5.4", "1.5.3", null, TestName = "An_installer_older_than_installerMin_is_refused")]
    [TestCase(null, "1.5.3", null, TestName = "A_release_that_names_no_installerMin_is_its_own_installer_s")]
    [TestCase("1.5.3", "1.5.3", "2222222222222222222222222222222222222222222222222222222222222222",
        TestName = "A_release_with_another_agreement_is_its_own_installer_s")]
    public void A_release_this_installer_is_not_the_one_for_is_refused_before_its_files(string? oldest, string own, string? agreement)
    {
        Served served = new(Release(oldest, agreement ?? Agreement));
        using HttpClient http = new(served);

        Assert.That(
            async () => await SignedRelease.ReadAsync(http, new Uri(Address), OwnerKeys, own, Agreement, CancellationToken.None),
            Throws.TypeOf<InstallerTooOldException>());
        Assert.That(served.Asked, Does.Not.Contain("files.json"));
    }

    [Test]
    public void A_release_signed_by_no_built_in_key_is_refused()
    {
        Served served = new(Release("1.5.3"), ECDsa.Create(ECCurve.NamedCurves.nistP256));
        using HttpClient http = new(served);

        Assert.That(
            async () => await SignedRelease.ReadAsync(http, new Uri(Address), OwnerKeys, "1.5.3", Agreement, CancellationToken.None),
            Throws.TypeOf<UnsignedReleaseException>());
    }

    [Test]
    public void A_files_json_that_is_not_the_signed_one_is_refused()
    {
        Served served = new(Release("1.5.3"), files: "{\"version\":\"2.0.0\",\"files\":[]}");
        using HttpClient http = new(served);

        Assert.That(
            async () => await SignedRelease.ReadAsync(http, new Uri(Address), OwnerKeys, "1.5.3", Agreement, CancellationToken.None),
            Throws.TypeOf<UnsignedReleaseException>());
    }

    [Test]
    public void How_far_the_download_is_is_written_whole_and_its_end_says_what_was_downloaded()
    {
        DateTimeOffset at = new(2026, 11, 14, 1, 0, 0, TimeSpan.Zero);
        FetchProgress progress = new(directory, "2.0.0", () => at);
        string file = Path.Combine(directory, FetchProgress.FileName);

        progress.Report(InstallPhase.Downloading, 10, 100);
        JsonObject first = Read(file);
        progress.Report(InstallPhase.Downloading, 20, 100);
        progress.End(downloaded: 90, total: 100);
        JsonObject last = Read(file);

        Assert.That(((string?)first["phase"], (long?)first["done"], (long?)first["total"]), Is.EqualTo(("downloading", 10L, 100L)));
        Assert.That(((string?)last["phase"], (long?)last["done"], (long?)last["downloaded"]), Is.EqualTo(("fetched", 100L, 90L)));
        Assert.That((string?)last["version"], Is.EqualTo("2.0.0"));
        Assert.That(File.Exists(file + ".new"), Is.False);

        progress.Fail("network", 40);
        Assert.That(((string?)Read(file)["phase"], (string?)Read(file)["reason"]), Is.EqualTo(("failed", "network")));
    }

    private static JsonObject Read(string file) => (JsonObject)JsonNode.Parse(File.ReadAllText(file))!;

    private const string FilesJson = """
        {"version": "2.0.0", "files": [
          {"path": "app/Baxy.exe", "bytes": 3, "sha256": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad", "archive": "baxy.zip", "offset": 40, "packed": 3, "method": 0}
        ]}
        """;

    private static string Release(string? oldest, string agreement = Agreement)
    {
        byte[] files = Encoding.UTF8.GetBytes(FilesJson);
        Dictionary<string, object> manifest = new()
        {
            ["version"] = "2.0.0",
            ["baseUrl"] = Address,
            ["installedBytes"] = 3,
            ["archives"] = new[]
            {
                new Dictionary<string, object>
                {
                    ["name"] = "baxy.zip",
                    ["parts"] = new[] { new Dictionary<string, object> { ["file"] = "baxy.zip.000", ["bytes"] = 100, ["sha256"] = new string('a', 64) } },
                },
            },
            ["files"] = new Dictionary<string, object>
            {
                ["file"] = "files.json", ["bytes"] = files.Length, ["sha256"] = Convert.ToHexStringLower(SHA256.HashData(files)),
            },
            ["agreement"] = new Dictionary<string, object> { ["sha256"] = agreement },
        };
        if (oldest is not null)
        {
            manifest["installerMin"] = oldest;
        }

        return JsonSerializer.Serialize(manifest);
    }

    /// <summary>A release's folder: release.json, its signature with <c>key</c> (the owner's), and files.json.</summary>
    private sealed class Served(string release, ECDsa? key = null, string files = FilesJson) : HttpMessageHandler
    {
        internal List<string> Asked { get; } = [];

        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        {
            string name = request.RequestUri!.Segments[^1];
            Asked.Add(name);
            byte[] manifest = Encoding.UTF8.GetBytes(release);
            HttpResponseMessage response = name switch
            {
                "release.json" => new(HttpStatusCode.OK) { Content = new ByteArrayContent(manifest) },
                "release.json.sig" => new(HttpStatusCode.OK)
                {
                    Content = new StringContent(Convert.ToBase64String((key ?? Owner).SignData(manifest, HashAlgorithmName.SHA256)) + "\n"),
                },
                "files.json" => new(HttpStatusCode.OK) { Content = new ByteArrayContent(Encoding.UTF8.GetBytes(files)) },
                _ => new(HttpStatusCode.NotFound),
            };
            return Task.FromResult(response);
        }
    }
}
