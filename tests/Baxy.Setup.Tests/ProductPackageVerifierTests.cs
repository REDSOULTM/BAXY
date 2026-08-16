using System.Text;
using NUnit.Framework;

namespace Baxy.Setup.Tests;

[TestFixture]
public sealed class ProductPackageVerifierTests
{
    [Test]
    public void CanonicalV4PackageIsVerified()
    {
        byte[] bytes = TestProductPackageFactory.Create();
        using MemoryStream stream = TestProductPackageFactory.Open(bytes);

        VerifiedProductPackage package = new ProductPackageVerifier().Verify(stream);

        Assert.Multiple(() =>
        {
            Assert.That(package.DataSchema, Is.EqualTo(PackageContract.DataSchema));
            Assert.That(package.Version, Is.EqualTo("1.0.0"));
            Assert.That(package.PackageLength, Is.EqualTo(bytes.Length));
            Assert.That(package.PackageSha256, Has.Length.EqualTo(64));
            Assert.That(package.ManifestSha256, Has.Length.EqualTo(64));
            Assert.That(package.ContentId, Has.Length.EqualTo(64));
            Assert.That(package.Commit, Is.EqualTo(new string('a', 40)));
            Assert.That(package.SourceDateEpoch, Is.EqualTo(TestProductPackageFactory.SourceDateEpoch));
        });
    }

    [TestCase(0)]
    [TestCase(2)]
    public void UnsupportedProductDataSchemaIsRejected(int dataSchema)
    {
        byte[] bytes = TestProductPackageFactory.Create(dataSchema: dataSchema);
        using MemoryStream stream = TestProductPackageFactory.Open(bytes);

        Assert.That(
            () => new ProductPackageVerifier().Verify(stream),
            Throws.TypeOf<ProductPackageException>());
    }

    [Test]
    public void NonCanonicalProductDataSchemaOrderIsRejected()
    {
        byte[] bytes = TestProductPackageFactory.Create(manifestMutation: static manifest =>
            TestProductPackageFactory.ReplaceAscii(
                manifest,
                "\"version\":\"1.0.0\",\"data_schema\":1",
                "\"data_schema\":1,\"version\":\"1.0.0\""));
        using MemoryStream stream = TestProductPackageFactory.Open(bytes);

        Assert.That(
            () => new ProductPackageVerifier().Verify(stream),
            Throws.TypeOf<ProductPackageException>());
    }

    [TestCase("tamper")]
    [TestCase("truncated")]
    [TestCase("trailing")]
    [TestCase("traversal")]
    [TestCase("duplicate_case")]
    [TestCase("extra")]
    [TestCase("wrong_timestamp")]
    public void StructurallyOrCryptographicallyInvalidPackageIsRejected(string defect)
    {
        byte[] package = defect switch
        {
            "tamper" => TestProductPackageFactory.TamperPayloadByte(TestProductPackageFactory.Create()),
            "truncated" => TestProductPackageFactory.Create()[..^5],
            "trailing" => [.. TestProductPackageFactory.Create(), 0x42],
            "traversal" => TestProductPackageFactory.Create(entryMutation: static entries =>
            {
                entries.RemoveAll(static entry => entry.Path == "wpfgfx_cor3.dll");
                entries.Add(new TestProductPackageFactory.TestZipEntry("../escape.dll", [1]));
            }),
            "duplicate_case" => TestProductPackageFactory.Create(entryMutation: static entries =>
            {
                entries.RemoveAll(static entry => entry.Path == "wpfgfx_cor3.dll");
                entries.Add(new TestProductPackageFactory.TestZipEntry("baxy.exe", [1]));
            }),
            "extra" => TestProductPackageFactory.Create(entryMutation: static entries =>
                entries.Add(new TestProductPackageFactory.TestZipEntry("extra.bin", [1]))),
            "wrong_timestamp" => TestProductPackageFactory.Create(
                timestampEpoch: TestProductPackageFactory.SourceDateEpoch + 2),
            _ => throw new AssertionException("Unknown test defect."),
        };

        using MemoryStream stream = TestProductPackageFactory.Open(package);
        Assert.That(
            () => new ProductPackageVerifier().Verify(stream),
            Throws.TypeOf<ProductPackageException>());
    }

    [TestCase("source_null")]
    [TestCase("commit_null")]
    public void NullManifestGraphIsRejectedAsPackageFailure(string defect)
    {
        byte[] package = TestProductPackageFactory.Create(manifestMutation: bytes => defect switch
        {
            "source_null" => ReplaceSourceWithNull(bytes),
            "commit_null" => TestProductPackageFactory.ReplaceAscii(
                bytes,
                $"\"commit\":\"{new string('a', 40)}\"",
                "\"commit\":null"),
            _ => throw new AssertionException("Unknown test defect."),
        });
        using MemoryStream stream = TestProductPackageFactory.Open(package);

        Assert.That(
            () => new ProductPackageVerifier().Verify(stream),
            Throws.TypeOf<ProductPackageException>());
    }

    [TestCase("dirty")]
    [TestCase("debug")]
    [TestCase("checksum")]
    public void SelfConsistentButNonDeliveryPackageIsRejected(string defect)
    {
        byte[] package = defect switch
        {
            "dirty" => TestProductPackageFactory.Create(manifestMutation: static bytes =>
                TestProductPackageFactory.ReplaceAscii(bytes, "\"dirty\":false", "\"dirty\":true")),
            "debug" => TestProductPackageFactory.Create(manifestMutation: static bytes =>
                TestProductPackageFactory.ReplaceAscii(bytes, "\"configuration\":\"Release\"", "\"configuration\":\"Debug\"")),
            "checksum" => TestProductPackageFactory.Create(entryMutation: static entries =>
            {
                int index = entries.FindIndex(static entry => entry.Path == "SHA256SUMS");
                TestProductPackageFactory.TestZipEntry original = entries[index];
                byte[] changed = (byte[])original.Content.Clone();
                changed[0] = changed[0] == (byte)'0' ? (byte)'1' : (byte)'0';
                entries[index] = new TestProductPackageFactory.TestZipEntry(original.Path, changed);
            }),
            _ => throw new AssertionException("Unknown test defect."),
        };
        using MemoryStream stream = TestProductPackageFactory.Open(package);

        Assert.That(() => new ProductPackageVerifier().Verify(stream), Throws.TypeOf<ProductPackageException>());
    }

    [TestCase("flags")]
    [TestCase("method")]
    [TestCase("extra")]
    [TestCase("comment")]
    public void NonCanonicalZipMetadataIsRejected(string defect)
    {
        byte[] package = TestProductPackageFactory.Create();
        switch (defect)
        {
            case "flags":
                package[6] ^= 1;
                break;
            case "method":
                package[8] = 8;
                break;
            case "extra":
                package[28] = 1;
                break;
            case "comment":
                package[^2] = 1;
                break;
            default:
                throw new AssertionException("Unknown test defect.");
        }

        using MemoryStream stream = TestProductPackageFactory.Open(package);
        Assert.That(() => new ProductPackageVerifier().Verify(stream), Throws.TypeOf<ProductPackageException>());
    }

    [Test]
    public void EmbeddedAttestationBindsAllPackageIdentityFieldsAndRejectsNullDigest()
    {
        byte[] bytes = TestProductPackageFactory.Create();
        ProductPackageVerifier verifier = new();
        VerifiedProductPackage verified;
        using (MemoryStream stream = TestProductPackageFactory.Open(bytes))
        {
            verified = verifier.Verify(stream);
        }

        byte[] attestation = EmbeddedPackageSource.CreateCanonicalAttestation(verified);
        Assert.That(
            Encoding.UTF8.GetString(attestation),
            Does.StartWith("{\"schema\":\"baxy-setup-embedded-package-v2\",\"version\":\"1.0.0\",\"data_schema\":1"));
        using (MemoryStream stream = TestProductPackageFactory.Open(bytes))
        {
            VerifiedProductPackage embedded = EmbeddedPackageSource.VerifyStreams(stream, attestation, verifier);
            Assert.That(embedded.PackageSha256, Is.EqualTo(verified.PackageSha256));
        }

        byte[] nullDigest = TestProductPackageFactory.ReplaceAscii(
            attestation,
            $"\"manifest_sha256\":\"{verified.ManifestSha256}\"",
            "\"manifest_sha256\":null");
        using MemoryStream nullStream = TestProductPackageFactory.Open(bytes);
        Assert.That(
            () => EmbeddedPackageSource.VerifyStreams(nullStream, nullDigest, verifier),
            Throws.TypeOf<ProductPackageException>());

        byte[] foreignDataSchema = TestProductPackageFactory.ReplaceAscii(
            attestation,
            "\"data_schema\":1",
            "\"data_schema\":2");
        using MemoryStream foreignSchemaStream = TestProductPackageFactory.Open(bytes);
        Assert.That(
            () => EmbeddedPackageSource.VerifyStreams(foreignSchemaStream, foreignDataSchema, verifier),
            Throws.TypeOf<ProductPackageException>());
    }

    [Test]
    public void VerificationEvidenceRejectsAdsPathAndWritesCanonicalNewFile()
    {
        byte[] bytes = TestProductPackageFactory.Create();
        VerifiedProductPackage verified;
        using (MemoryStream stream = TestProductPackageFactory.Open(bytes))
        {
            verified = new ProductPackageVerifier().Verify(stream);
        }

        string root = Path.Combine(Path.GetTempPath(), "baxy-setup-evidence-tests", Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        try
        {
            string victim = Path.Combine(root, "victim.txt");
            File.WriteAllText(victim, "sentinel");
            Assert.That(
                () => EmbeddedPackageSource.WriteVerificationEvidence(victim + ":gate", verified),
                Throws.TypeOf<InstallationSafetyException>());
            Assert.That(File.ReadAllText(victim), Is.EqualTo("sentinel"));

            string evidence = Path.Combine(root, "evidence.json");
            EmbeddedPackageSource.WriteVerificationEvidence(evidence, verified);
            string text = File.ReadAllText(evidence);
            Assert.Multiple(() =>
            {
                Assert.That(
                    text,
                    Does.StartWith(
                        "{\"schema\":\"baxy-setup-embedded-verification-v2\",\"status\":\"passed\",\"version\":\"1.0.0\",\"data_schema\":1"));
                Assert.That(text, Does.EndWith("\n"));
            });
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }

    private static byte[] ReplaceSourceWithNull(byte[] bytes)
    {
        string text = Encoding.UTF8.GetString(bytes);
        const string marker = "\"source\":";
        int start = text.IndexOf(marker, StringComparison.Ordinal);
        int end = text.IndexOf(",\"toolchain\":", start, StringComparison.Ordinal);
        if (start < 0 || end < 0)
        {
            throw new InvalidOperationException("Unable to locate source object in test manifest.");
        }

        return Encoding.UTF8.GetBytes(text[..(start + marker.Length)] + "null" + text[end..]);
    }
}
