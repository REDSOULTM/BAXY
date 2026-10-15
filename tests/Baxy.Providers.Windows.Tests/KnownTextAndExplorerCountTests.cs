using System.Text;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// REOPEN1957 H0299 (pasted path of a ROADMAP.md) and H0701 («cuántos .py hay
/// en el directorio actual»): a known-folder text file is read as UTF-8 and
/// the Explorer folder in the foreground (or the Desktop) is counted by
/// extension, naming the folder and never its path.
/// </summary>
[TestFixture]
public sealed class KnownTextAndExplorerCountTests
{
    private static JsonElement Json(string text) => JsonDocument.Parse(text).RootElement.Clone();

    private sealed class ScriptedRunner(string output) : IExternalProcessRunner
    {
        public ValueTask<ExternalProcessResult> RunAsync(
            string executable, IReadOnlyList<string> arguments, TimeSpan timeout, CancellationToken cancellationToken) =>
            ValueTask.FromResult(new ExternalProcessResult(0, output, ""));
    }

    private sealed class TemporaryDirectory : IDisposable
    {
        internal string Path { get; } = System.IO.Path.Combine(
            System.IO.Path.GetTempPath(), "baxy-text-explorer-tests-" + Guid.NewGuid().ToString("N"));

        internal TemporaryDirectory() => Directory.CreateDirectory(Path);

        public void Dispose()
        {
            try { Directory.Delete(Path, recursive: true); }
            catch (IOException) { }
            catch (UnauthorizedAccessException) { }
        }
    }

    [Test]
    public async Task ATextFileInASubfolderIsReadWithItsBomHonouredByNameOrRelativePath()
    {
        using TemporaryDirectory temporary = new();
        string desktop = Path.Combine(temporary.Path, "desktop");
        string project = Path.Combine(desktop, "ETC", "Programacion", "Probando Gemma 4", "gemma4_agent");
        Directory.CreateDirectory(project);
        string content = "# ROADMAP\n\nFase 1: agente local.\nFase 2: memoria.\n";
        await File.WriteAllTextAsync(Path.Combine(project, "ROADMAP.md"), content, new UTF8Encoding(true));
        await File.WriteAllBytesAsync(Path.Combine(desktop, "binario.md"), [0, 1, 2, 3, 0, 0, 0, 5, 6, 0]);
        var roots = new Dictionary<string, string[]> { ["desktop"] = [desktop] };
        var adapter = new WindowsKnownFileAdapter(roots);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "file.read",
            Json("""{"folder":"desktop","subdirectory":"ETC\\Programacion\\Probando Gemma 4\\gemma4_agent","fileName":"ROADMAP.md","maximumCharacters":200}"""),
            CancellationToken.None);
        ExternalCapabilityReceipt whole = await adapter.InvokeAsync(
            "file.read",
            Json("""{"folder":"desktop","fileName":"roadmap.md"}"""),
            CancellationToken.None);
        ExternalCapabilityReceipt byPath = await adapter.InvokeAsync(
            "file.read",
            Json("""{"folder":"desktop","fileName":"ETC/Programacion/Probando Gemma 4/gemma4_agent/ROADMAP.md"}"""),
            CancellationToken.None);
        ExternalCapabilityReceipt binary = await adapter.InvokeAsync(
            "file.read",
            Json("""{"folder":"desktop","fileName":"binario.md"}"""),
            CancellationToken.None);
        ExternalCapabilityReceipt missing = await adapter.InvokeAsync(
            "file.read",
            Json("""{"folder":"desktop","fileName":"nada.md"}"""),
            CancellationToken.None);
        ExternalCapabilityReceipt escaping = await adapter.InvokeAsync(
            "file.read",
            Json("""{"folder":"desktop","fileName":"..\\secreto.txt"}"""),
            CancellationToken.None);

        Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
        Assert.Multiple(() =>
        {
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.Result?.GetProperty("kind").GetString(), Is.EqualTo("text"));
            Assert.That(receipt.Result?.GetProperty("text").GetString(), Is.EqualTo(content));
            // Four lines: the break that ends the last one does not start a fifth (e2e p6 E018: 138 for 137).
            Assert.That(receipt.Result?.GetProperty("totalLines").GetInt32(), Is.EqualTo(4));
            Assert.That(receipt.Result?.GetProperty("lines").GetInt32(), Is.EqualTo(4));
            Assert.That(receipt.Result?.GetProperty("characters").GetInt32(), Is.EqualTo(content.Length));
            Assert.That(receipt.Result?.GetProperty("hasMore").GetBoolean(), Is.False);
            Assert.That(receipt.Result?.TryGetProperty("nextOffset", out _), Is.False);
            Assert.That(receipt.Result?.GetProperty("reviewLabel").GetString(), Is.EqualTo("ROADMAP.md"));
            Assert.That(receipt.Result?.GetRawText(), Does.Not.Contain("gemma4_agent"));
            Assert.That(whole.Verified, Is.True, whole.ErrorCode);
            Assert.That(byPath.Verified, Is.True, byPath.ErrorCode);
            Assert.That(byPath.Result?.GetProperty("text").GetString(), Is.EqualTo(content));
            Assert.That(binary.ErrorCode, Is.EqualTo("known_file_not_text"));
            Assert.That(missing.ErrorCode, Is.EqualTo("known_file_not_found"));
            Assert.That(escaping.ErrorCode, Is.EqualTo("known_file_name_invalid"));
        });
    }

    // BAXY Renew agent tools (2026-10-15): a long file is read in pages; each says the total, where it started and
    // where the next one starts, and the pages put together are the file.
    [Test]
    public async Task ALongTextFileIsReadInPagesThatTogetherAreTheWholeFile()
    {
        using TemporaryDirectory temporary = new();
        string documents = Path.Combine(temporary.Path, "documents");
        Directory.CreateDirectory(documents);
        string content = string.Concat(Enumerable.Range(0, 120).Select(index => $"línea {index:D3} del informe\n"));
        await File.WriteAllTextAsync(Path.Combine(documents, "informe.txt"), content, new UTF8Encoding(false));
        var adapter = new WindowsKnownFileAdapter(new Dictionary<string, string[]> { ["documents"] = [documents] });

        var pages = new List<JsonElement>();
        int offset = 0;
        for (int round = 0; round < 10; round++)
        {
            ExternalCapabilityReceipt page = await adapter.InvokeAsync(
                "file.read",
                Json($$"""{"folder":"documents","fileName":"informe.txt","offset":{{offset}},"maximumCharacters":1000}"""),
                CancellationToken.None);
            Assert.That(page.Verified, Is.True, page.ErrorCode);
            pages.Add(page.Result!.Value);
            if (!page.Result.Value.GetProperty("hasMore").GetBoolean()) break;
            offset = page.Result.Value.GetProperty("nextOffset").GetInt32();
        }
        ExternalCapabilityReceipt past = await adapter.InvokeAsync(
            "file.read",
            Json("""{"folder":"documents","fileName":"informe.txt","offset":999999}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(pages, Has.Count.EqualTo((content.Length + 999) / 1000));
            Assert.That(string.Concat(pages.Select(page => page.GetProperty("text").GetString())), Is.EqualTo(content));
            Assert.That(pages.Select(page => page.GetProperty("characters").GetInt32()), Has.All.EqualTo(content.Length));
            Assert.That(pages[1].GetProperty("offset").GetInt32(), Is.EqualTo(1000));
            Assert.That(pages[0].GetProperty("returnedCharacters").GetInt32(), Is.EqualTo(1000));
            Assert.That(past.Verified, Is.True, past.ErrorCode);
            Assert.That(past.Result?.GetProperty("text").GetString(), Is.Empty);
            Assert.That(past.Result?.GetProperty("hasMore").GetBoolean(), Is.False);
        });
    }

    // A UTF-16 file (what Windows PowerShell 5's «>» writes) is text: its NUL bytes are the encoding, not binary. Two
    // files with the same name are refused with both places, so the next call can name one by its relative path.
    [Test]
    public async Task AUtf16FileIsTextAndTwoFilesWithOneNameAreRefusedWithTheirPlaces()
    {
        using TemporaryDirectory temporary = new();
        string desktop = Path.Combine(temporary.Path, "desktop");
        string documents = Path.Combine(temporary.Path, "documents");
        Directory.CreateDirectory(Path.Combine(desktop, "viejo"));
        Directory.CreateDirectory(documents);
        await File.WriteAllTextAsync(Path.Combine(desktop, "procesos.txt"), "Name  Id\nbaxy  42\n", new UnicodeEncoding(false, true));
        await File.WriteAllTextAsync(Path.Combine(desktop, "viejo", "notas.txt"), "viejas");
        await File.WriteAllTextAsync(Path.Combine(documents, "notas.txt"), "nuevas");
        var adapter = new WindowsKnownFileAdapter(new Dictionary<string, string[]>
        {
            ["desktop"] = [desktop],
            ["documents"] = [documents],
        });

        ExternalCapabilityReceipt utf16 = await adapter.InvokeAsync(
            "file.read", Json("""{"folder":"desktop","fileName":"procesos.txt"}"""), CancellationToken.None);
        ExternalCapabilityReceipt twice = await adapter.InvokeAsync(
            "file.read", Json("""{"folder":"all_known","fileName":"notas.txt"}"""), CancellationToken.None);
        ExternalCapabilityReceipt stem = await adapter.InvokeAsync(
            "file.read", Json("""{"folder":"documents","fileName":"notas"}"""), CancellationToken.None);
        ExternalCapabilityReceipt named = await adapter.InvokeAsync(
            "file.read", Json("""{"folder":"desktop","fileName":"viejo\\notas.txt"}"""), CancellationToken.None);

        Assert.That(utf16.Verified, Is.True, utf16.ErrorCode);
        Assert.Multiple(() =>
        {
            Assert.That(utf16.Result?.GetProperty("text").GetString(), Is.EqualTo("Name  Id\nbaxy  42\n"));
            Assert.That(twice.ErrorCode, Is.EqualTo("known_file_ambiguous"));
            Assert.That(twice.Result?.GetProperty("candidates").EnumerateArray()
                    .Select(candidate => candidate.GetProperty("folder").GetString() + ":"
                        + candidate.GetProperty("relativePath").GetString()),
                Is.EquivalentTo(new[] { "desktop:" + Path.Combine("viejo", "notas.txt"), "documents:notas.txt" }));
            Assert.That(stem.ErrorCode, Is.EqualTo("known_file_not_found"));
            Assert.That(stem.Result?.GetProperty("candidates")[0].GetProperty("name").GetString(),
                Is.EqualTo("notas.txt"));
            Assert.That(named.Result?.GetProperty("text").GetString(), Is.EqualTo("viejas"));
        });
    }

    [Test]
    public async Task TheForegroundExplorerFolderOrTheNamedOneIsCountedAndWithNeitherItFails()
    {
        using TemporaryDirectory temporary = new();
        string project = Path.Combine(temporary.Path, "proyecto");
        string desktop = Path.Combine(temporary.Path, "Escritorio");
        Directory.CreateDirectory(Path.Combine(project, "sub"));
        Directory.CreateDirectory(desktop);
        foreach (string name in new[] { "a.py", "b.PY", "c.txt", Path.Combine("sub", "d.py") })
            await File.WriteAllTextAsync(Path.Combine(project, name), "x");
        await File.WriteAllTextAsync(Path.Combine(desktop, "solo.py"), "x");
        string url = "file:///" + project.Replace('\\', '/');
        Func<string, string?> known = folder => folder == "desktop" ? desktop : null;
        var inFront = new ExplorerFolderAdapter(
            new ScriptedRunner("{\"foreground\":123,\"path\":\"" + project.Replace("\\", "\\\\") + "\"}"),
            known);
        var noneInFront = new ExplorerFolderAdapter(new ScriptedRunner("{\"foreground\":123,\"path\":\"\"}"), known);

        ExternalCapabilityReceipt counted = await inFront.InvokeAsync(
            "filesystem.explorer.count", Json("""{"extension":".py"}"""), CancellationToken.None);
        ExternalCapabilityReceipt none = await noneInFront.InvokeAsync(
            "filesystem.explorer.count", Json("""{"extension":"py"}"""), CancellationToken.None);
        ExternalCapabilityReceipt named = await noneInFront.InvokeAsync(
            "filesystem.explorer.count", Json("""{"extension":"py","folder":"desktop"}"""), CancellationToken.None);

        Assert.That(counted.Verified, Is.True, counted.ErrorCode);
        Assert.Multiple(() =>
        {
            Assert.That(url, Does.StartWith("file:///"));
            Assert.That(counted.Result?.GetProperty("count").GetInt32(), Is.EqualTo(2));
            Assert.That(counted.Result?.GetProperty("filesInFolder").GetInt32(), Is.EqualTo(3));
            Assert.That(counted.Result?.GetProperty("folderName").GetString(), Is.EqualTo("proyecto"));
            Assert.That(counted.Result?.GetProperty("source").GetString(), Is.EqualTo("explorer_foreground"));
            Assert.That(counted.Result?.GetRawText(), Does.Not.Contain(temporary.Path.Replace("\\", "\\\\")));
            Assert.That(none.ErrorCode, Is.EqualTo("no_explorer_in_front"));
            Assert.That(named.Verified, Is.True, named.ErrorCode);
            Assert.That(named.Result?.GetProperty("count").GetInt32(), Is.EqualTo(1));
            Assert.That(named.Result?.GetProperty("source").GetString(), Is.EqualTo("known_folder"));
            Assert.That(named.Result?.GetProperty("folderName").GetString(), Is.EqualTo("Escritorio"));
        });
    }
}
