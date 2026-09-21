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
    public async Task ATextFileInASubfolderIsReadWithItsBomHonouredAndTruncated()
    {
        using TemporaryDirectory temporary = new();
        string desktop = Path.Combine(temporary.Path, "desktop");
        string project = Path.Combine(desktop, "ETC", "Programacion", "Probando Gemma 4", "gemma4_agent");
        Directory.CreateDirectory(project);
        string content = "# ROADMAP\n\nFase 1: agente local.\nFase 2: memoria.\n";
        await File.WriteAllTextAsync(Path.Combine(project, "ROADMAP.md"), content, new UTF8Encoding(true));
        await File.WriteAllBytesAsync(Path.Combine(desktop, "binario.md"), [0, 1, 2, 3, 0, 0, 0, 5, 6, 0]);
        var roots = new Dictionary<string, string[]> { ["desktop"] = [desktop] };
        var adapter = new WindowsKnownFileAdapter(temporary.Path, roots);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "document.text.read",
            Json("""{"folder":"desktop","subdirectory":"ETC\\Programacion\\Probando Gemma 4\\gemma4_agent","fileName":"ROADMAP.md","maximumCharacters":200}"""),
            CancellationToken.None);
        ExternalCapabilityReceipt whole = await adapter.InvokeAsync(
            "document.text.read",
            Json("""{"folder":"desktop","fileName":"roadmap.md"}"""),
            CancellationToken.None);
        ExternalCapabilityReceipt binary = await adapter.InvokeAsync(
            "document.text.read",
            Json("""{"folder":"desktop","fileName":"binario.md"}"""),
            CancellationToken.None);
        ExternalCapabilityReceipt missing = await adapter.InvokeAsync(
            "document.text.read",
            Json("""{"folder":"desktop","fileName":"nada.md"}"""),
            CancellationToken.None);

        Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
        Assert.Multiple(() =>
        {
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.Result?.GetProperty("text").GetString(), Is.EqualTo(content));
            Assert.That(receipt.Result?.GetProperty("lines").GetInt32(), Is.EqualTo(5));
            Assert.That(receipt.Result?.GetProperty("truncated").GetBoolean(), Is.False);
            Assert.That(receipt.Result?.GetProperty("reviewLabel").GetString(), Is.EqualTo("ROADMAP.md"));
            Assert.That(receipt.Result?.GetRawText(), Does.Not.Contain("gemma4_agent"));
            Assert.That(whole.Verified, Is.True, whole.ErrorCode);
            Assert.That(binary.ErrorCode, Is.EqualTo("known_file_not_text"));
            Assert.That(missing.ErrorCode, Is.EqualTo("known_file_not_found"));
        });
    }

    [Test]
    public async Task TheForegroundExplorerFolderIsCountedByExtensionOrTheDesktopWhenNoneIsInFront()
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
        var inFront = new ExplorerFolderAdapter(
            new ScriptedRunner("{\"foreground\":123,\"path\":\"" + project.Replace("\\", "\\\\") + "\"}"),
            () => desktop);
        var noneInFront = new ExplorerFolderAdapter(new ScriptedRunner("{\"foreground\":123,\"path\":\"\"}"), () => desktop);

        ExternalCapabilityReceipt counted = await inFront.InvokeAsync(
            "filesystem.explorer.count", Json("""{"extension":".py"}"""), CancellationToken.None);
        ExternalCapabilityReceipt fallback = await noneInFront.InvokeAsync(
            "filesystem.explorer.count", Json("""{"extension":"py"}"""), CancellationToken.None);

        Assert.That(counted.Verified, Is.True, counted.ErrorCode);
        Assert.Multiple(() =>
        {
            Assert.That(url, Does.StartWith("file:///"));
            Assert.That(counted.Result?.GetProperty("count").GetInt32(), Is.EqualTo(2));
            Assert.That(counted.Result?.GetProperty("filesInFolder").GetInt32(), Is.EqualTo(3));
            Assert.That(counted.Result?.GetProperty("folderName").GetString(), Is.EqualTo("proyecto"));
            Assert.That(counted.Result?.GetProperty("source").GetString(), Is.EqualTo("explorer_foreground"));
            Assert.That(counted.Result?.GetRawText(), Does.Not.Contain(temporary.Path.Replace("\\", "\\\\")));
            Assert.That(fallback.Verified, Is.True, fallback.ErrorCode);
            Assert.That(fallback.Result?.GetProperty("count").GetInt32(), Is.EqualTo(1));
            Assert.That(fallback.Result?.GetProperty("source").GetString(), Is.EqualTo("desktop"));
            Assert.That(fallback.Result?.GetProperty("folderName").GetString(), Is.EqualTo("Escritorio"));
        });
    }
}
