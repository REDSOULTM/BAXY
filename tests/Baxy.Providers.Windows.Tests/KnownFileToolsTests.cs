using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using Baxy.Providers.Windows.Filesystem;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// BAXY Renew agent tools (2026-10-15): file.find lists a known folder or finds files under it by name or by a text
/// inside them, and file.edit replaces an exact text in one of them with its previous version sent to the Recycle Bin
/// first (a stand-in bin here: the real one is checked by <see cref="WindowsRecycleBinLiveCheck"/>).
/// </summary>
[TestFixture]
public sealed class KnownFileToolsTests
{
    private static JsonElement Json(string text) => JsonDocument.Parse(text).RootElement.Clone();

    /// <summary>A bin that takes every file (or none) into a folder of its own, as the Recycle Bin would.</summary>
    internal sealed class FolderRecycleBin(string folder, bool accepts = true) : IRecycleBin
    {
        internal List<string> Recycled { get; } = [];

        public bool Recycle(string path)
        {
            if (!accepts) return false;
            Directory.CreateDirectory(folder);
            string destination = Path.Combine(folder, Guid.NewGuid().ToString("N") + "_" + Path.GetFileName(path));
            File.Move(path, destination);
            Recycled.Add(destination);
            return true;
        }
    }

    private sealed class TemporaryDirectory : IDisposable
    {
        internal string Path { get; } = System.IO.Path.Combine(
            System.IO.Path.GetTempPath(), "baxy-file-tools-tests-" + Guid.NewGuid().ToString("N"));

        internal TemporaryDirectory() => Directory.CreateDirectory(Path);

        public void Dispose()
        {
            try { Directory.Delete(Path, recursive: true); }
            catch (IOException) { }
            catch (UnauthorizedAccessException) { }
        }
    }

    private static (WindowsKnownFileAdapter Adapter, string Desktop, string Documents, FolderRecycleBin Bin) Folders(
        TemporaryDirectory temporary, bool binAccepts = true)
    {
        string desktop = Path.Combine(temporary.Path, "desktop");
        string documents = Path.Combine(temporary.Path, "documents");
        Directory.CreateDirectory(desktop);
        Directory.CreateDirectory(documents);
        var bin = new FolderRecycleBin(Path.Combine(temporary.Path, "bin"), binAccepts);
        var adapter = new WindowsKnownFileAdapter(temporary.Path, new Dictionary<string, string[]>
        {
            ["desktop"] = [desktop],
            ["documents"] = [documents],
        }, bin);
        return (adapter, desktop, documents, bin);
    }

    [Test]
    public async Task FindListsTheTopLevelFindsNamesAndPatternsAndGivesRelativePaths()
    {
        using TemporaryDirectory temporary = new();
        (WindowsKnownFileAdapter adapter, string desktop, string documents, _) = Folders(temporary);
        Directory.CreateDirectory(Path.Combine(desktop, "proyectos", "tesis"));
        await File.WriteAllTextAsync(Path.Combine(desktop, "presupuesto 2026.xlsx"), "x");
        await File.WriteAllTextAsync(Path.Combine(desktop, "proyectos", "tesis", "capitulo1.pdf"), "x");
        await File.WriteAllTextAsync(Path.Combine(documents, "Presupuesto viejo.txt"), "x");
        File.SetLastWriteTimeUtc(Path.Combine(documents, "Presupuesto viejo.txt"), DateTime.UtcNow.AddDays(-3));

        ExternalCapabilityReceipt listed = await adapter.InvokeAsync(
            "file.find", Json("""{"folder":"desktop"}"""), CancellationToken.None);
        ExternalCapabilityReceipt named = await adapter.InvokeAsync(
            "file.find", Json("""{"folder":"all_known","query":"presupuesto","order":"recent"}"""),
            CancellationToken.None);
        ExternalCapabilityReceipt pattern = await adapter.InvokeAsync(
            "file.find", Json("""{"folder":"all_known","query":"*.pdf"}"""), CancellationToken.None);
        ExternalCapabilityReceipt inside = await adapter.InvokeAsync(
            "file.find", Json("""{"folder":"desktop","subdirectory":"proyectos"}"""), CancellationToken.None);
        ExternalCapabilityReceipt missing = await adapter.InvokeAsync(
            "file.find", Json("""{"folder":"desktop","subdirectory":"no-existe"}"""), CancellationToken.None);

        Assert.That(listed.Verified, Is.True, listed.ErrorCode);
        Assert.Multiple(() =>
        {
            Assert.That(listed.EffectObserved, Is.False);
            Assert.That(listed.Result?.GetProperty("mode").GetString(), Is.EqualTo("list"));
            Assert.That(listed.Result?.GetProperty("entries").EnumerateArray()
                    .Select(entry => entry.GetProperty("kind").GetString() + ":" + entry.GetProperty("name").GetString()),
                Is.EqualTo(new[] { "folder:proyectos", "file:presupuesto 2026.xlsx" }));
            Assert.That(named.Result?.GetProperty("files").EnumerateArray()
                    .Select(file => file.GetProperty("folder").GetString() + ":" + file.GetProperty("name").GetString()),
                Is.EqualTo(new[] { "desktop:presupuesto 2026.xlsx", "documents:Presupuesto viejo.txt" }));
            Assert.That(pattern.Result?.GetProperty("files")[0].GetProperty("relativePath").GetString(),
                Is.EqualTo(Path.Combine("proyectos", "tesis", "capitulo1.pdf")));
            Assert.That(pattern.Result?.GetProperty("count").GetInt32(), Is.EqualTo(1));
            Assert.That(inside.Result?.GetProperty("entries")[0].GetProperty("relativePath").GetString(),
                Is.EqualTo(Path.Combine("proyectos", "tesis")));
            Assert.That(missing.ErrorCode, Is.EqualTo("known_subdirectory_not_found"));
            Assert.That(named.Result?.GetRawText(), Does.Not.Contain(temporary.Path.Replace("\\", "\\\\")));
        });
    }

    [Test]
    public async Task FindByContentGivesTheFirstMatchingLineAndSkipsWhatIsNotText()
    {
        using TemporaryDirectory temporary = new();
        (WindowsKnownFileAdapter adapter, _, string documents, _) = Folders(temporary);
        Directory.CreateDirectory(Path.Combine(documents, "actas"));
        await File.WriteAllTextAsync(Path.Combine(documents, "actas", "lunes.md"),
            "# Acta\n\nTemas varios\nAcordamos la Reunión con Juan el jueves.\nOtra reunión con Juan.\n");
        await File.WriteAllTextAsync(Path.Combine(documents, "compras.txt"), "pan\nleche\n");
        await File.WriteAllBytesAsync(Path.Combine(documents, "foto.jpg"), [0xFF, 0xD8, 0, 0, 0, 1, 2, 0, 0, 0]);
        await File.WriteAllTextAsync(Path.Combine(documents, "grande.log"), new string('x', 1_100_000));

        ExternalCapabilityReceipt found = await adapter.InvokeAsync(
            "file.find", Json("""{"folder":"documents","content":"reunión con juan"}"""), CancellationToken.None);
        ExternalCapabilityReceipt narrowed = await adapter.InvokeAsync(
            "file.find", Json("""{"folder":"documents","content":"pan","query":"*.md"}"""), CancellationToken.None);

        Assert.That(found.Verified, Is.True, found.ErrorCode);
        Assert.Multiple(() =>
        {
            JsonElement file = found.Result!.Value.GetProperty("files")[0];
            Assert.That(found.Result?.GetProperty("mode").GetString(), Is.EqualTo("content"));
            Assert.That(found.Result?.GetProperty("count").GetInt32(), Is.EqualTo(1));
            Assert.That(file.GetProperty("relativePath").GetString(), Is.EqualTo(Path.Combine("actas", "lunes.md")));
            Assert.That(file.GetProperty("line").GetInt32(), Is.EqualTo(4));
            Assert.That(file.GetProperty("lineText").GetString(), Is.EqualTo("Acordamos la Reunión con Juan el jueves."));
            JsonElement scope = found.Result!.Value.GetProperty("searchScope");
            Assert.That(scope.GetProperty("filesScanned").GetInt32(), Is.EqualTo(4));
            Assert.That(scope.GetProperty("skippedNotText").GetInt32(), Is.EqualTo(1));
            Assert.That(scope.GetProperty("skippedTooLarge").GetInt32(), Is.EqualTo(1));
            Assert.That(narrowed.Result?.GetProperty("count").GetInt32(), Is.Zero);
        });
    }

    // file.read of a PDF: the text it carries, through the mind runtime's pypdf, in pages like a text file.
    [Test]
    public async Task APdfIsReadThroughTheMindRuntimeInPages()
    {
        if (WindowsKnownFileAdapter.FindMindPython() is null)
            Assert.Ignore("The registered mind runtime (pypdf) is not installed on this machine.");
        using TemporaryDirectory temporary = new();
        (WindowsKnownFileAdapter adapter, _, string documents, _) = Folders(temporary);
        await File.WriteAllBytesAsync(Path.Combine(documents, "informe.pdf"),
            TextPdf("Primera pagina del informe", "Segunda pagina con el cierre"));

        ExternalCapabilityReceipt first = await adapter.InvokeAsync(
            "file.read", Json("""{"folder":"documents","fileName":"informe.pdf","maximumCharacters":200}"""),
            CancellationToken.None);
        ExternalCapabilityReceipt rest = await adapter.InvokeAsync(
            "file.read", Json("""{"folder":"documents","fileName":"informe.pdf","offset":28}"""),
            CancellationToken.None);

        Assert.That(first.Verified, Is.True, first.ErrorCode);
        Assert.Multiple(() =>
        {
            Assert.That(first.Result?.GetProperty("kind").GetString(), Is.EqualTo("pdf"));
            Assert.That(first.Result?.GetProperty("pages").GetInt32(), Is.EqualTo(2));
            Assert.That(first.Result?.GetProperty("characters").GetInt32(), Is.EqualTo(56));
            Assert.That(first.Result?.GetProperty("hasMore").GetBoolean(), Is.False);
            Assert.That(first.Result?.GetProperty("text").GetString(),
                Is.EqualTo("Primera pagina del informe\n\nSegunda pagina con el cierre"));
            Assert.That(rest.Result?.GetProperty("offset").GetInt32(), Is.EqualTo(28));
            Assert.That(rest.Result?.GetProperty("text").GetString(), Is.EqualTo("Segunda pagina con el cierre"));
        });
    }

    // A minimal PDF with one line of Helvetica text per page.
    private static byte[] TextPdf(params string[] pages)
    {
        var objects = new List<string>
        {
            "<< /Type /Catalog /Pages 2 0 R >>",
            "",
            "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        };
        var kids = new List<int>();
        foreach (string text in pages)
        {
            string stream = $"BT /F1 12 Tf 72 712 Td ({text}) Tj ET";
            objects.Add($"<< /Length {stream.Length} >>\nstream\n{stream}\nendstream");
            int content = objects.Count;
            objects.Add($"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {content} 0 R "
                + "/Resources << /Font << /F1 3 0 R >> >> >>");
            kids.Add(objects.Count);
        }
        objects[1] = $"<< /Type /Pages /Kids [{string.Join(" ", kids.Select(kid => $"{kid} 0 R"))}] /Count {kids.Count} >>";
        var output = new StringBuilder("%PDF-1.4\n");
        var offsets = new List<int>();
        for (int index = 0; index < objects.Count; index++)
        {
            offsets.Add(output.Length);
            output.Append(CultureInfo.InvariantCulture, $"{index + 1} 0 obj\n{objects[index]}\nendobj\n");
        }
        int xref = output.Length;
        output.Append(CultureInfo.InvariantCulture, $"xref\n0 {objects.Count + 1}\n0000000000 65535 f \n");
        foreach (int offset in offsets) output.Append(CultureInfo.InvariantCulture, $"{offset:D10} 00000 n \n");
        output.Append(CultureInfo.InvariantCulture, $"trailer\n<< /Size {objects.Count + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n");
        return Encoding.ASCII.GetBytes(output.ToString());
    }

    [Test]
    public async Task EditReplacesTheOneOccurrenceRecyclesThePreviousVersionAndKeepsTheBom()
    {
        using TemporaryDirectory temporary = new();
        (WindowsKnownFileAdapter adapter, string desktop, _, FolderRecycleBin bin) = Folders(temporary);
        string path = Path.Combine(desktop, "notas.txt");
        string original = "Reunión el lunes\r\nComprar pan el lunes temprano\r\n";
        await File.WriteAllTextAsync(path, original, new UTF8Encoding(true));
        byte[] before = await File.ReadAllBytesAsync(path);

        ExternalCapabilityReceipt ambiguous = await adapter.InvokeAsync(
            "file.edit", Json("""{"folder":"desktop","fileName":"notas.txt","oldText":"lunes","newText":"martes"}"""),
            CancellationToken.None);
        byte[] untouched = await File.ReadAllBytesAsync(path);
        ExternalCapabilityReceipt once = await adapter.InvokeAsync(
            "file.edit",
            Json("""{"folder":"desktop","fileName":"notas.txt","oldText":"Reunión el lunes","newText":"Reunión el martes"}"""),
            CancellationToken.None);
        ExternalCapabilityReceipt absent = await adapter.InvokeAsync(
            "file.edit", Json("""{"folder":"desktop","fileName":"notas.txt","oldText":"domingo","newText":"sábado"}"""),
            CancellationToken.None);
        byte[] after = await File.ReadAllBytesAsync(path);

        Assert.That(once.Verified, Is.True, once.ErrorCode);
        Assert.Multiple(() =>
        {
            Assert.That(ambiguous.ErrorCode, Is.EqualTo("known_edit_text_not_unique"));
            Assert.That(ambiguous.Result?.GetProperty("occurrences").GetInt32(), Is.EqualTo(2));
            Assert.That(untouched, Is.EqualTo(before));
            Assert.That(once.EffectObserved, Is.True);
            Assert.That(once.Result?.GetProperty("replacements").GetInt32(), Is.EqualTo(1));
            Assert.That(once.Result?.GetProperty("previousVersionRecycled").GetBoolean(), Is.True);
            Assert.That(once.Result?.GetProperty("previousSha256").GetString(),
                Is.EqualTo(Convert.ToHexStringLower(SHA256.HashData(before))));
            Assert.That(once.Result?.GetProperty("sha256").GetString(),
                Is.EqualTo(Convert.ToHexStringLower(SHA256.HashData(after))));
            Assert.That(once.Result?.GetProperty("newTextOccurrences").GetInt32(), Is.EqualTo(1));
            Assert.That(after[..3], Is.EqualTo(new byte[] { 0xEF, 0xBB, 0xBF }));
            Assert.That(Encoding.UTF8.GetString(after[3..]),
                Is.EqualTo("Reunión el martes\r\nComprar pan el lunes temprano\r\n"));
            Assert.That(bin.Recycled, Has.Count.EqualTo(1));
            Assert.That(File.ReadAllBytes(bin.Recycled[0]), Is.EqualTo(before));
            Assert.That(absent.ErrorCode, Is.EqualTo("known_edit_text_not_found"));
            Assert.That(Directory.GetFiles(desktop), Is.EqualTo(new[] { path }));
        });
    }

    [Test]
    public async Task EditReplacesEveryOccurrenceWhenAskedAndChangesNothingWhenTheBinRefuses()
    {
        using TemporaryDirectory temporary = new();
        (WindowsKnownFileAdapter adapter, _, string documents, FolderRecycleBin bin) = Folders(temporary);
        string path = Path.Combine(documents, "informe.md");
        await File.WriteAllTextAsync(path, "Año 2024. Cierre 2024. Meta 2024.\n");
        using TemporaryDirectory refusing = new();
        (WindowsKnownFileAdapter noBin, _, string otherDocuments, _) = Folders(refusing, binAccepts: false);
        string kept = Path.Combine(otherDocuments, "informe.md");
        await File.WriteAllTextAsync(kept, "Año 2024.\n");
        byte[] ansi = [0x63, 0x61, 0x66, 0xE9, 0x0A];
        await File.WriteAllBytesAsync(Path.Combine(documents, "ansi.txt"), ansi);

        ExternalCapabilityReceipt all = await adapter.InvokeAsync(
            "file.edit",
            Json("""{"folder":"documents","fileName":"informe.md","oldText":"2024","newText":"2025","replaceAll":true}"""),
            CancellationToken.None);
        ExternalCapabilityReceipt refused = await noBin.InvokeAsync(
            "file.edit", Json("""{"folder":"documents","fileName":"informe.md","oldText":"2024","newText":"2025"}"""),
            CancellationToken.None);
        ExternalCapabilityReceipt encoding = await adapter.InvokeAsync(
            "file.edit", Json("""{"folder":"documents","fileName":"ansi.txt","oldText":"caf","newText":"te"}"""),
            CancellationToken.None);

        Assert.That(all.Verified, Is.True, all.ErrorCode);
        Assert.Multiple(() =>
        {
            Assert.That(all.Result?.GetProperty("replacements").GetInt32(), Is.EqualTo(3));
            Assert.That(all.Result?.GetProperty("oldTextOccurrencesNow").GetInt32(), Is.Zero);
            Assert.That(File.ReadAllText(path), Is.EqualTo("Año 2025. Cierre 2025. Meta 2025.\n"));
            Assert.That(bin.Recycled, Has.Count.EqualTo(1));
            Assert.That(refused.Verified, Is.False);
            Assert.That(refused.ErrorCode, Is.EqualTo("previous_version_not_recycled"));
            Assert.That(refused.EffectMayHaveOccurred, Is.False);
            Assert.That(File.ReadAllText(kept), Is.EqualTo("Año 2024.\n"));
            Assert.That(Directory.GetFiles(otherDocuments), Is.EqualTo(new[] { kept }));
            Assert.That(encoding.ErrorCode, Is.EqualTo("known_text_encoding_unsupported"));
            Assert.That(File.ReadAllBytes(Path.Combine(documents, "ansi.txt")), Is.EqualTo(ansi));
        });
    }
}
