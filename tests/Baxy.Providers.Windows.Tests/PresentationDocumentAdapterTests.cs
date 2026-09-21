using System.IO.Compression;
using System.Text.Json;
using System.Xml.Linq;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// REOPEN1957 H0188 (D11): el paquete .pptx escrito es un Open XML válido con
/// una diapositiva por entrada; la postlectura cuenta las diapositivas.
/// </summary>
[TestFixture]
public sealed class PresentationDocumentAdapterTests
{
    private string _root = string.Empty;

    [SetUp]
    public void SetUp()
    {
        _root = Path.Combine(Path.GetTempPath(), "baxy-pptx-tests", Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(_root);
    }

    [TearDown]
    public void TearDown()
    {
        // BAXY_PPTX_KEEP keeps the written package so the root can open it in
        // the real PowerPoint by COM (the tanda's own postread does the same).
        if (Environment.GetEnvironmentVariable("BAXY_PPTX_KEEP") is { Length: > 0 })
            return;
        try { Directory.Delete(_root, recursive: true); } catch (IOException) { }
    }

    [Test]
    public async Task SixSlidesAreWrittenAsAWellFormedPackageAndCountedBack()
    {
        var adapter = new PresentationDocumentAdapter(folder => folder == "documents" ? _root : null);
        string[] slides =
        [
            "El amor\nUna presentación en seis diapositivas",
            "Qué es el amor\nUn vínculo\nUna elección diaria",
            "Formas de amor\nRomántico\nFamiliar\nDe amistad",
            "El amor en la literatura\nPoemas & novelas",
            "El amor en la vida cotidiana\nGestos pequeños",
            "Cierre\nGracias",
        ];

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "document.presentation.create",
            JsonSerializer.SerializeToElement(new { title = "Hablando de amor", slides, folder = "documents" }),
            CancellationToken.None);

        Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
        string path = Path.Combine(_root, "Hablando de amor.pptx");
        Assert.Multiple(() =>
        {
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(receipt.Result!.Value.GetProperty("slideCount").GetInt32(), Is.EqualTo(6));
            Assert.That(receipt.Result!.Value.GetProperty("name").GetString(), Is.EqualTo("Hablando de amor.pptx"));
            Assert.That(receipt.Result!.Value.GetProperty("slideTitles")[2].GetString(), Is.EqualTo("Formas de amor"));
            Assert.That(File.Exists(path), Is.True);
        });
        using ZipArchive archive = ZipFile.OpenRead(path);
        foreach (ZipArchiveEntry entry in archive.Entries.Where(entry => entry.FullName.EndsWith(".xml", StringComparison.Ordinal) || entry.FullName.EndsWith(".rels", StringComparison.Ordinal)))
        {
            using Stream stream = entry.Open();
            Assert.DoesNotThrow(() => XDocument.Load(stream), entry.FullName);
        }

        ZipArchiveEntry? slide4 = archive.GetEntry("ppt/slides/slide4.xml");
        Assert.That(slide4, Is.Not.Null);
        using StreamReader reader = new(slide4!.Open());
        string xml = reader.ReadToEnd();
        Assert.That(xml, Does.Contain("Poemas &amp; novelas"));
    }

    [Test]
    public async Task NoSlidesOrTooManyIsRefusedBeforeWriting()
    {
        var adapter = new PresentationDocumentAdapter(folder => _root);
        ExternalCapabilityReceipt none = await adapter.InvokeAsync(
            "document.presentation.create",
            JsonSerializer.SerializeToElement(new { title = "Vacía", slides = Array.Empty<string>() }),
            CancellationToken.None);
        ExternalCapabilityReceipt many = await adapter.InvokeAsync(
            "document.presentation.create",
            JsonSerializer.SerializeToElement(new { title = "Larga", slides = Enumerable.Repeat("t\nx", 13).ToArray() }),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(none.ErrorCode, Is.EqualTo("presentation_slides_invalid"));
            Assert.That(many.ErrorCode, Is.EqualTo("presentation_slides_invalid"));
            Assert.That(Directory.EnumerateFiles(_root), Is.Empty);
        });
    }
}
