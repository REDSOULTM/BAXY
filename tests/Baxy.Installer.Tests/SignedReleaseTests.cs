using System.Net;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using NUnit.Framework;

namespace Baxy.Installer.Tests;

/// <summary>
/// FIR1 (decisión A1, 10-11-2026): the installer uses the hashes it carries only after the release.json published where the
/// parts are is signed with a key built into it and is that same manifest; and it never puts an older BAXY over a newer one.
/// </summary>
[TestFixture]
internal sealed class SignedReleaseTests
{
    private const string BaseUrl = "https://example.test/download/v1.1.0/";
    private static readonly ECDsa Owner = ECDsa.Create(ECCurve.NamedCurves.nistP256);
    private static readonly ECDsa Stranger = ECDsa.Create(ECCurve.NamedCurves.nistP256);
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

    [Test]
    public async Task TheOwnersSignatureOfItsOwnManifestLetsItGoOn()
    {
        InstallPaths paths = Paths();
        using HttpClient http = new(new Files(Manifest("1.1.0"), Owner));

        await SignedRelease.ConfirmAsync(http, Carried(), paths, OwnerKeys, CancellationToken.None);

        Assert.That(Directory.Exists(paths.Root) || Directory.Exists(paths.Downloads), Is.False);
    }

    [TestCase("missing", TestName = "FIR1_Instalador_SinFirma_NoInstalaNada")]
    [TestCase("stranger", TestName = "FIR1_Instalador_FirmaMala_NoInstalaNada")]
    [TestCase("changed", TestName = "FIR1_Instalador_JsonCambiado_NoInstalaNada")]
    [TestCase("older", TestName = "FIR1_Instalador_FirmaViejaValida_NoInstalaNada")]
    [TestCase("parts", TestName = "FIR1_Instalador_FirmaValidaDeOtrasPartes_NoInstalaNada")]
    public void AnythingButTheOwnersSignatureOfThisManifestStopsItBeforeAnyDownload(string attack)
    {
        InstallPaths paths = Paths();
        string json = Manifest("1.1.0");
        Files files = attack switch
        {
            "missing" => new Files(json, null),
            "stranger" => new Files(json, Stranger),
            "changed" => new Files(json, Owner, served: json.Replace("\"installedBytes\":5000", "\"installedBytes\":5001", StringComparison.Ordinal)),
            "older" => new Files(Manifest("1.0.0"), Owner),
            _ => new Files(json.Replace(new string('a', 64), new string('b', 64), StringComparison.Ordinal), Owner),
        };
        using HttpClient http = new(files);

        Assert.ThrowsAsync<UnsignedReleaseException>(() => SignedRelease.ConfirmAsync(http, Carried(), paths, OwnerKeys, CancellationToken.None));
        Assert.Multiple(() =>
        {
            Assert.That(files.Asked, Has.None.Contains(".zip"), "no part is asked for");
            Assert.That(Directory.Exists(paths.Root) || Directory.Exists(paths.Downloads), Is.False, "nothing is left behind");
            Assert.That(Failures.Classify(new UnsignedReleaseException("x"), () => false), Is.EqualTo(FailureKind.Unsigned));
        });
    }

    // A real exe with a newer version where BAXY's would be: an old installer, signed for real, does not replace it.
    [Test]
    public void ANewerBaxyInTheFolderIsNotReplacedByAnOlderOne()
    {
        InstallPaths paths = Paths();
        Directory.CreateDirectory(Path.GetDirectoryName(paths.App)!);
        File.Copy(typeof(object).Assembly.Location, paths.App);
        using HttpClient http = new(new Files(Manifest("1.1.0"), Owner));

        OlderReleaseException? older = Assert.ThrowsAsync<OlderReleaseException>(
            () => SignedRelease.ConfirmAsync(http, Carried(), paths, OwnerKeys, CancellationToken.None));

        Assert.Multiple(() =>
        {
            Assert.That(older?.Installed, Is.EqualTo(SignedRelease.InstalledVersion(paths.App)?.ToString(3)));
            Assert.That(older?.Offered, Is.EqualTo("1.1.0"));
            Assert.That(Failures.Classify(older!, () => false), Is.EqualTo(FailureKind.Older));
        });
    }

    // What the person reads says it in plain words in both languages, with no internal name in it.
    [TestCase("es")]
    [TestCase("en")]
    public void ItIsSaidPlainly(string language)
    {
        Texts texts = Texts.For(language);
        string said = texts.FailUnsigned + texts.FailUnsignedHelp + texts.FailUnsignedUpdateHelp + texts.FailOlder + texts.FailOlderHelp;

        Assert.That(said, Does.Not.Contain("release").And.Not.Contain("json").And.Not.Contain(".sig").And.Not.Contain("_"));
    }

    // The keys the installer carries are the repository's (Directory.Build.props, BaxyUpdateKeys).
    [Test]
    public void TheInstallerCarriesTheRepositorysKeys()
    {
        string file = File.ReadAllText(Path.Combine(TestContext.CurrentContext.TestDirectory, "..", "..", "..", "..", "..",
            "release-keys", "update-keys.pem"));

        Assert.That(SignedRelease.BuiltInKeys, Is.Not.Empty);
        Assert.That(SignedRelease.BuiltInKeys, Is.EqualTo(Baxy.Core.Operations.ReleaseSignature.Blocks(file)));
    }

    private InstallPaths Paths() => new(Path.Combine(directory, "BAXY-App"));

    private static ReleaseManifest Carried()
    {
        using MemoryStream json = new(Encoding.UTF8.GetBytes(Manifest("1.1.0")));
        return ReleaseManifest.Parse(json);
    }

    // As scripts/build_github_release.py writes it: the parts, and the installer's own entry the installer does not read.
    private static string Manifest(string version) => JsonSerializer.Serialize(new Dictionary<string, object>
    {
        ["version"] = version,
        ["baseUrl"] = BaseUrl,
        ["installedBytes"] = 5000,
        ["archives"] = new[]
        {
            new Dictionary<string, object>
            {
                ["name"] = "baxy.zip",
                ["parts"] = new[] { new Dictionary<string, object> { ["file"] = "baxy.zip.000", ["bytes"] = 10, ["sha256"] = new string('a', 64) } },
            },
        },
        ["installer"] = new Dictionary<string, object> { ["file"] = "BAXY-Instalador.exe", ["bytes"] = 3, ["sha256"] = new string('c', 64) },
    });

    /// <summary>Where the parts are: release.json (signed as given, served maybe changed) and its .sig when there is a key.</summary>
    private sealed class Files(string signed, ECDsa? key, string? served = null) : HttpMessageHandler
    {
        internal List<string> Asked { get; } = [];

        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        {
            string name = request.RequestUri!.Segments[^1];
            Asked.Add(name);
            byte[] manifest = Encoding.UTF8.GetBytes(signed);
            HttpResponseMessage response = name switch
            {
                "release.json" => new(HttpStatusCode.OK) { Content = new ByteArrayContent(Encoding.UTF8.GetBytes(served ?? signed)) },
                "release.json.sig" when key is not null => new(HttpStatusCode.OK)
                {
                    Content = new StringContent(Convert.ToBase64String(key.SignData(manifest, HashAlgorithmName.SHA256)) + "\n"),
                },
                _ => new(HttpStatusCode.NotFound),
            };
            return Task.FromResult(response);
        }
    }
}
