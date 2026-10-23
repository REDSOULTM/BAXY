using System.Security.Cryptography;
using System.Text;
using Baxy.Providers.Windows.Memory;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests.Memory;

[TestFixture]
public sealed class LocalMemoryExportWriterTests
{
    [Test]
    public void VerificationPinsTheExpectedInvocationPathAndDigest()
    {
        using TemporaryDirectory temporary = new();
        string invocationId = Guid.NewGuid().ToString("D");
        var writer = new LocalMemoryExportWriter(temporary.Path);
        MemoryExportResult result = writer.Export(
            new MemoryExportRequest(invocationId, [Record()]));
        var receipt = new MemoryExportVerificationRequest(
            invocationId,
            result.Path,
            result.RecordCount,
            result.Sha256);

        bool verified = writer.Verify(receipt);
        bool wrongInvocation = writer.Verify(receipt with
        {
            InvocationId = Guid.NewGuid().ToString("D"),
        });
        bool wrongDigest = writer.Verify(receipt with
        {
            Sha256 = new string('0', 64),
        });
        bool wrongCount = writer.Verify(receipt with
        {
            RecordCount = result.RecordCount + 1,
        });
        File.WriteAllText(result.Path, "{\"tampered\":true}\n", new UTF8Encoding(false));
        bool tampered = writer.Verify(receipt);
        File.Delete(result.Path);
        bool deleted = writer.Verify(receipt);

        Assert.Multiple(() =>
        {
            Assert.That(verified, Is.True);
            Assert.That(wrongInvocation, Is.False);
            Assert.That(wrongDigest, Is.False);
            Assert.That(wrongCount, Is.False);
            Assert.That(tampered, Is.False);
            Assert.That(deleted, Is.False);
        });
    }

    [Test]
    public void RenameConflictWithADeleteBlockingTargetLeavesNoPlaintextTemporaryFile()
    {
        using TemporaryDirectory temporary = new();
        string invocationId = Guid.NewGuid().ToString("D");
        string exportRoot = Path.Combine(
            temporary.Path,
            LocalMemoryExportWriter.ExportDirectoryName);
        string invocationHash = Convert.ToHexStringLower(
            SHA256.HashData(Encoding.UTF8.GetBytes(invocationId)));
        string targetPath = Path.Combine(exportRoot, $"memory-export-{invocationHash}.json");
        FileStream? blocker = null;
        var writer = new LocalMemoryExportWriter(
            temporary.Path,
            stage =>
            {
                if (stage != MemoryExportWriteStage.CandidateFlushed)
                    return;
                blocker = new FileStream(
                    targetPath,
                    FileMode.CreateNew,
                    FileAccess.ReadWrite,
                    FileShare.None);
            });
        MemoryRecord record = Record();

        try
        {
            Assert.That(
                () => writer.Export(new MemoryExportRequest(invocationId, [record])),
                Throws.TypeOf<UnsafeMemoryExportPathException>());
        }
        finally
        {
            blocker?.Dispose();
        }

        Assert.Multiple(() =>
        {
            Assert.That(Directory.EnumerateFiles(exportRoot, "*.tmp"), Is.Empty);
            Assert.That(new FileInfo(targetPath).Length, Is.Zero);
            Assert.That(File.ReadAllText(targetPath, Encoding.UTF8),
                Does.Not.Contain("CANARY-PLAINTEXT-EXPORT"));
        });
    }

    [Test]
    public void AttemptedPathSwapFailsClosedAndLeavesNoPlaintextCandidate()
    {
        using TemporaryDirectory temporary = new();
        string invocationId = Guid.NewGuid().ToString("D");
        string exportRoot = Path.Combine(
            temporary.Path,
            LocalMemoryExportWriter.ExportDirectoryName);
        string movedRoot = Path.Combine(temporary.Path, "moved-private-export");
        var writer = new LocalMemoryExportWriter(
            temporary.Path,
            stage =>
            {
                if (stage != MemoryExportWriteStage.CandidateFlushed)
                    return;
                Directory.Move(exportRoot, movedRoot);
                Directory.CreateDirectory(exportRoot);
            });

        Assert.That(
            () => writer.Export(new MemoryExportRequest(invocationId, [Record()])),
            Throws.TypeOf<MemoryExportUnavailableException>());

        Assert.Multiple(() =>
        {
            Assert.That(Directory.EnumerateFiles(exportRoot), Is.Empty);
            Assert.That(Directory.Exists(movedRoot), Is.False);
        });
    }

    // Ronda B: an export already published whose read-back fails says it may be there (it came out as a clean
    // memory_export_unavailable).
    [Test]
    public void APublishedExportThatDoesNotReadBackSaysItMayBeThere()
    {
        using TemporaryDirectory temporary = new();
        string invocationId = Guid.NewGuid().ToString("D");
        string exportRoot = Path.Combine(temporary.Path, LocalMemoryExportWriter.ExportDirectoryName);
        var writer = new LocalMemoryExportWriter(
            temporary.Path,
            stage =>
            {
                if (stage == MemoryExportWriteStage.Published)
                    File.WriteAllText(Directory.EnumerateFiles(exportRoot, "*.json").Single(), "{}", new UTF8Encoding(false));
            });

        Assert.That(
            () => writer.Export(new MemoryExportRequest(invocationId, [Record()])),
            Throws.TypeOf<MemoryExportPublishedUnverifiedException>());
    }

    // Renew al máximo (w8): the store keeps a value with a line break or a tab; the export takes it as kept (it was
    // memory_export_unavailable for every export until that record was forgotten).
    [Test]
    public void AValueWithALineBreakIsExported()
    {
        using TemporaryDirectory temporary = new();
        string invocationId = Guid.NewGuid().ToString("D");
        var writer = new LocalMemoryExportWriter(temporary.Path);

        MemoryExportResult result = writer.Export(
            new MemoryExportRequest(invocationId, [Record() with { Value = "primera línea\nsegunda\tcolumna" }]));

        Assert.Multiple(() =>
        {
            Assert.That(result.RecordCount, Is.EqualTo(1));
            Assert.That(File.ReadAllText(result.Path), Does.Contain("primera l"));
        });
    }

    private static MemoryRecord Record()
    {
        DateTimeOffset now = DateTimeOffset.UtcNow;
        return new MemoryRecord(
            Guid.NewGuid(),
            1,
            "tema",
            "Tema",
            "CANARY-PLAINTEXT-EXPORT",
            MemoryKind.Fact,
            MemoryOrigin.Explicit,
            MemorySensitivity.Normal,
            MemoryRetention.Persistent,
            [],
            now,
            now,
            null,
            null,
            now,
            null);
    }

    private sealed class TemporaryDirectory : IDisposable
    {
        public TemporaryDirectory()
        {
            Path = System.IO.Path.Combine(
                System.IO.Path.GetTempPath(),
                $"baxy-memory-export-{Guid.NewGuid():N}");
            Directory.CreateDirectory(Path);
        }

        public string Path { get; }

        public void Dispose()
        {
            if (Directory.Exists(Path))
            {
                Directory.Delete(Path, recursive: true);
            }
        }
    }
}
