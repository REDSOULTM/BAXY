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
    // FT/proveedores goal (review of receipts): a file another program holds open with no sharing is that file in use,
    // not its folder unavailable.
    [Test]
    public async Task AFileHeldOpenByAnotherProgramIsInUse()
    {
        using TemporaryDirectory temporary = new();
        string home = Path.Combine(temporary.Path, "home");
        Directory.CreateDirectory(home);
        string path = Path.Combine(home, "ventas.csv");
        await File.WriteAllTextAsync(path, "a;b");
        var adapter = new WindowsKnownFileAdapter(new Dictionary<string, string[]> { ["home"] = [home] },
            new FolderRecycleBin(Path.Combine(temporary.Path, "bin"), true));

        ExternalCapabilityReceipt read;
        using (new FileStream(path, FileMode.Open, FileAccess.ReadWrite, FileShare.None))
        {
            read = await adapter.InvokeAsync(
                "file.read", Json("""{"folder":"home","fileName":"ventas.csv"}"""), CancellationToken.None);
        }

        Assert.That(read.ErrorCode, Is.EqualTo("file_in_use"));
    }

    // Renew al máximo (B-SYS-1): BAXY's private area is not one of the person's files, under home or anywhere: file.edit
    // could turn confirmation-mode from normal to bypass. Read, edit, trash or a search there are refused or skip it.
    [Test]
    public async Task BaxysOwnStateIsNeitherReadEditedNorFound()
    {
        using TemporaryDirectory temporary = new();
        string home = Path.Combine(temporary.Path, "home");
        string privateArea = Path.Combine(home, "AppData", "Local", "BAXY");
        string mode = Path.Combine(privateArea, "1", "confirmation-mode");
        Directory.CreateDirectory(Path.GetDirectoryName(mode)!);
        await File.WriteAllTextAsync(mode, "normal");
        var bin = new FolderRecycleBin(Path.Combine(temporary.Path, "bin"));
        var adapter = new WindowsKnownFileAdapter(new Dictionary<string, string[]> { ["home"] = [home] }, bin,
            [privateArea]);

        ExternalCapabilityReceipt edited = await adapter.InvokeAsync("file.edit", Json(
            """{"folder":"home","fileName":"AppData\\Local\\BAXY\\1\\confirmation-mode","oldText":"normal","newText":"bypass"}"""),
            CancellationToken.None);
        ExternalCapabilityReceipt byFullPath = await adapter.InvokeAsync("file.read", Json(
            JsonSerializer.Serialize(new { folder = "home", fileName = mode })), CancellationToken.None);
        ExternalCapabilityReceipt inside = await adapter.InvokeAsync("file.find", Json(
            """{"folder":"home","subdirectory":"AppData/Local/BAXY"}"""), CancellationToken.None);
        ExternalCapabilityReceipt around = await adapter.InvokeAsync("file.find", Json(
            """{"folder":"home","subdirectory":"AppData/Local","query":"confirmation-mode"}"""), CancellationToken.None);
        ExternalCapabilityReceipt trashed = await adapter.InvokeAsync("filesystem.known.trash.named", Json(
            """{"folder":"home","subdirectory":"AppData/Local","fileName":"BAXY"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(edited.ErrorCode, Is.EqualTo("path_reserved"));
            Assert.That(byFullPath.ErrorCode, Is.EqualTo("path_reserved"));
            Assert.That(inside.ErrorCode, Is.EqualTo("path_reserved"));
            Assert.That(around.Result?.GetProperty("matchCount").GetInt32(), Is.Zero);
            Assert.That(trashed.EffectObserved, Is.False);
            Assert.That(File.ReadAllText(mode), Is.EqualTo("normal"));
            Assert.That(bin.Recycled, Is.Empty);
        });
    }

    // Renew al máximo (auditoría de flujos, archivos): a subdirectory reached through a link part way («AppData\Local\
    // Application Data» is Windows' own junction back to AppData\Local) is refused like one that is itself a link; only
    // the last part was checked, so BAXY's area was listed and its confirmation-mode edited to bypass through it.
    [Test]
    public async Task ASubdirectoryThroughALinkPartWayIsRefused()
    {
        using TemporaryDirectory temporary = new();
        string home = Path.Combine(temporary.Path, "home");
        string local = Path.Combine(home, "AppData", "Local");
        string privateArea = Path.Combine(local, "BAXY");
        string mode = Path.Combine(privateArea, "1", "confirmation-mode");
        Directory.CreateDirectory(Path.GetDirectoryName(mode)!);
        await File.WriteAllTextAsync(mode, "normal");
        _ = Baxy.Tests.NtfsTestJunction.Create(Path.Combine(local, "Application Data"), local);
        var bin = new FolderRecycleBin(Path.Combine(temporary.Path, "bin"));
        var adapter = new WindowsKnownFileAdapter(new Dictionary<string, string[]> { ["home"] = [home] }, bin,
            [privateArea]);

        ExternalCapabilityReceipt listed = await adapter.InvokeAsync("file.find", Json(
            """{"folder":"home","subdirectory":"AppData/Local/Application Data/BAXY/1"}"""), CancellationToken.None);
        ExternalCapabilityReceipt edited = await adapter.InvokeAsync("file.edit", Json(
            """{"folder":"home","subdirectory":"AppData/Local/Application Data/BAXY/1","fileName":"confirmation-mode","oldText":"normal","newText":"bypass"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(listed.ErrorCode, Is.EqualTo("known_subdirectory_reparse_point"));
            Assert.That(edited.ErrorCode, Is.EqualTo("known_subdirectory_reparse_point"));
            Assert.That(File.ReadAllText(mode), Is.EqualTo("normal"));
            Assert.That(bin.Recycled, Is.Empty);
        });
    }

    // Renew al máximo (auditoría de flujos, archivos): «¿qué hay en C:\Users\ana\Documents?» with the folder's own full
    // path as subdirectory is the folder itself; it was refused as known_path_outside_folder, a path outside it.
    [Test]
    public async Task TheKnownFolderItselfNamedByItsFullPathIsTheFolder()
    {
        using TemporaryDirectory temporary = new();
        string documents = Path.Combine(temporary.Path, "Documentos");
        Directory.CreateDirectory(documents);
        await File.WriteAllTextAsync(Path.Combine(documents, "informe.txt"), "hola");
        var adapter = new WindowsKnownFileAdapter(new Dictionary<string, string[]> { ["documents"] = [documents] },
            new FolderRecycleBin(Path.Combine(temporary.Path, "bin")), []);

        ExternalCapabilityReceipt listed = await adapter.InvokeAsync("file.find", Json(JsonSerializer.Serialize(
            new { folder = "documents", subdirectory = documents + Path.DirectorySeparatorChar })), CancellationToken.None);
        ExternalCapabilityReceipt read = await adapter.InvokeAsync("file.read", Json(JsonSerializer.Serialize(
            new { folder = "documents", subdirectory = documents, fileName = "informe.txt" })), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(listed.Verified, Is.True, listed.ErrorCode);
            Assert.That(listed.Result?.GetProperty("entries")[0].GetProperty("name").GetString(), Is.EqualTo("informe.txt"));
            Assert.That(read.Verified, Is.True, read.ErrorCode);
            Assert.That(read.Result?.GetProperty("text").GetString(), Is.EqualTo("hola"));
        });
    }

    // Renew al máximo (auditoría de flujos, archivos): a folder that holds BAXY's own area («Local» under AppData) is not
    // sent to the Recycle Bin by name: B-SYS-1 refused the area itself, and the folder around it took it all the same.
    [Test]
    public async Task AFolderHoldingBaxysOwnStateIsNotTrashed()
    {
        using TemporaryDirectory temporary = new();
        string home = Path.Combine(temporary.Path, "home");
        string privateArea = Path.Combine(home, "AppData", "Local", "BAXY");
        string mode = Path.Combine(privateArea, "1", "confirmation-mode");
        Directory.CreateDirectory(Path.GetDirectoryName(mode)!);
        await File.WriteAllTextAsync(mode, "normal");
        var bin = new FolderRecycleBin(Path.Combine(temporary.Path, "bin"));
        var adapter = new WindowsKnownFileAdapter(new Dictionary<string, string[]> { ["home"] = [home] }, bin,
            [privateArea]);

        ExternalCapabilityReceipt trashed = await adapter.InvokeAsync("filesystem.known.trash.named", Json(
            """{"folder":"home","subdirectory":"AppData","fileName":"Local"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(trashed.ErrorCode, Is.EqualTo("path_reserved"));
            Assert.That(trashed.EffectObserved, Is.False);
            Assert.That(File.ReadAllText(mode), Is.EqualTo("normal"));
            Assert.That(bin.Recycled, Is.Empty);
        });
    }

    internal sealed class FolderRecycleBin(string folder, bool accepts = true) : IRecycleBin
    {
        internal List<string> Recycled { get; } = [];

        public bool Recycle(string path)
        {
            if (!accepts) return false;
            Directory.CreateDirectory(folder);
            string destination = Path.Combine(folder, Guid.NewGuid().ToString("N") + "_" + Path.GetFileName(path));
            if (Directory.Exists(path)) Directory.Move(path, destination); else File.Move(path, destination);
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

    // BAXY Renew al máximo W5 (velocidad): a bare name found nowhere is walked once, keeping the files with its stem on
    // the way; the candidates are the ones the second walk gave, in its order, cut where it cut them. Found more than
    // CandidatesShown times, the walk stops where the name's own walk stopped.
    [TestCase(0)]
    [TestCase(1)]
    [TestCase(7)]
    public async Task ANameFoundNowhereOrTooOftenGivesTheCandidatesOfTheWalksItReplaces(int exact)
    {
        using TemporaryDirectory temporary = new();
        (WindowsKnownFileAdapter adapter, string desktop, string documents, _) = Folders(temporary);
        for (int i = 0; i < 8; i++)
        {
            string folder = Path.Combine(i % 2 == 0 ? desktop : documents, $"sub{i}");
            Directory.CreateDirectory(folder);
            await File.WriteAllTextAsync(Path.Combine(folder, i % 3 == 0 ? "informe.docx" : "informe.pdf"), "x");
            if (i < exact)
                await File.WriteAllTextAsync(Path.Combine(folder, "informe"), "y");
        }

        ExternalCapabilityReceipt read = await adapter.InvokeAsync(
            "file.read", Json("""{"folder":"all_known","fileName":"informe"}"""), CancellationToken.None);

        // The walks it replaces: the name's own, then (none found) the stem's, each the first six in walk order.
        var options = new EnumerationOptions
        {
            RecurseSubdirectories = true, IgnoreInaccessible = true, AttributesToSkip = FileAttributes.ReparsePoint,
            MaxRecursionDepth = 12,
        };
        (string Folder, string Path)[] walk = [.. new[] { ("desktop", desktop), ("documents", documents) }
            .SelectMany(root => Directory.EnumerateFiles(root.Item2, "*", options)
                .Select(file => (root.Item1, Path.GetRelativePath(root.Item2, file))))];
        (string, string)[] named = [.. walk.Where(item => Path.GetFileName(item.Path) == "informe").Take(6)];
        (string, string)[] stems = [.. walk.Where(item => Path.GetFileNameWithoutExtension(item.Path) == "informe").Take(6)];
        (string, string)[] expected = named.Length > 1 ? named : stems;
        if (exact == 1)
        {
            Assert.That(read.Verified, Is.True, read.ErrorCode);
            Assert.That(read.Result?.GetProperty("text").GetString(), Is.EqualTo("y"));
            return;
        }

        JsonElement[] candidates = [.. read.Result!.Value.GetProperty("candidates").EnumerateArray()];
        Assert.Multiple(() =>
        {
            Assert.That(read.ErrorCode, Is.EqualTo(exact > 1 ? "known_file_ambiguous" : "known_file_not_found"));
            Assert.That(candidates.Select(item => (item.GetProperty("folder").GetString()!,
                item.GetProperty("relativePath").GetString()!)), Is.EqualTo(expected.Take(5)));
            Assert.That(read.Result!.Value.TryGetProperty("candidatesTruncated", out JsonElement cut) && cut.GetBoolean(),
                Is.EqualTo(expected.Length > 5));
        });
    }

    private static (WindowsKnownFileAdapter Adapter, string Desktop, string Documents, FolderRecycleBin Bin) Folders(
        TemporaryDirectory temporary, bool binAccepts = true)
    {
        string desktop = Path.Combine(temporary.Path, "desktop");
        string documents = Path.Combine(temporary.Path, "documents");
        Directory.CreateDirectory(desktop);
        Directory.CreateDirectory(documents);
        var bin = new FolderRecycleBin(Path.Combine(temporary.Path, "bin"), binAccepts);
        var adapter = new WindowsKnownFileAdapter(new Dictionary<string, string[]>
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

    // The profile root (home) is read when it is named; «all_known» stays the known folders, so a file of the profile
    // is not found twice and AppData is never walked by a search of everything.
    [Test]
    public async Task HomeIsReadWhenNamedAndAllKnownLeavesItOut()
    {
        using TemporaryDirectory temporary = new();
        string home = Path.Combine(temporary.Path, "home");
        string desktop = Path.Combine(home, "Desktop");
        Directory.CreateDirectory(Path.Combine(home, "BAXY-bench"));
        Directory.CreateDirectory(desktop);
        await File.WriteAllTextAsync(Path.Combine(home, "BAXY-bench", "lista.txt"), "pan\n");
        await File.WriteAllTextAsync(Path.Combine(desktop, "lista vieja.txt"), "leche\n");
        var adapter = new WindowsKnownFileAdapter(new Dictionary<string, string[]>
        {
            ["desktop"] = [desktop],
            ["home"] = [home],
        }, new FolderRecycleBin(Path.Combine(temporary.Path, "bin"), true));

        ExternalCapabilityReceipt inHome = await adapter.InvokeAsync(
            "file.find", Json("""{"folder":"home","query":"lista"}"""), CancellationToken.None);
        ExternalCapabilityReceipt everywhere = await adapter.InvokeAsync(
            "file.find", Json("""{"folder":"all_known","query":"lista"}"""), CancellationToken.None);
        ExternalCapabilityReceipt read = await adapter.InvokeAsync(
            "file.read", Json("""{"folder":"home","fileName":"BAXY-bench/lista.txt"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(inHome.Verified, Is.True, inHome.ErrorCode);
            Assert.That(inHome.Result?.GetProperty("files").EnumerateArray()
                .Select(file => file.GetProperty("relativePath").GetString()),
                Does.Contain(Path.Combine("BAXY-bench", "lista.txt")));
            Assert.That(everywhere.Result?.GetProperty("files").EnumerateArray()
                .Select(file => file.GetProperty("relativePath").GetString()),
                Is.EqualTo(new[] { "lista vieja.txt" }));
            Assert.That(read.Verified, Is.True, read.ErrorCode);
            Assert.That(read.Result?.ToString(), Does.Contain("pan"));
        });
    }

    // The model copies the path the person said (e2e p3 F013): a full path inside the named folder is the same place as
    // its relative path, and one outside it is refused before anything is read.
    [Test]
    public async Task AFullPathInsideTheFolderIsItsRelativePathAndOneOutsideIsRefused()
    {
        using TemporaryDirectory temporary = new();
        string home = Path.Combine(temporary.Path, "home");
        Directory.CreateDirectory(Path.Combine(home, "BAXY-bench"));
        await File.WriteAllTextAsync(Path.Combine(home, "BAXY-bench", "lista.txt"), "pan\n");
        await File.WriteAllTextAsync(Path.Combine(temporary.Path, "fuera.txt"), "secreto\n");
        var adapter = new WindowsKnownFileAdapter(new Dictionary<string, string[]>
        {
            ["home"] = [home],
        }, new FolderRecycleBin(Path.Combine(temporary.Path, "bin"), true));
        string Args(string key, string value) => JsonSerializer.Serialize(new Dictionary<string, string>
        {
            ["folder"] = "home", [key] = value,
        });

        ExternalCapabilityReceipt read = await adapter.InvokeAsync(
            "file.read", Json(Args("fileName", Path.Combine(home, "BAXY-bench", "lista.txt"))), CancellationToken.None);
        ExternalCapabilityReceipt found = await adapter.InvokeAsync(
            "file.find", Json(Args("subdirectory", Path.Combine(home, "BAXY-bench"))), CancellationToken.None);
        ExternalCapabilityReceipt outside = await adapter.InvokeAsync(
            "file.read", Json(Args("fileName", Path.Combine(temporary.Path, "fuera.txt"))), CancellationToken.None);
        ExternalCapabilityReceipt outsideFolder = await adapter.InvokeAsync(
            "file.find", Json(Args("subdirectory", temporary.Path)), CancellationToken.None);
        // A full path to a file directly in the folder that is not there is not another file of that name below it.
        ExternalCapabilityReceipt elsewhere = await adapter.InvokeAsync(
            "file.read", Json(Args("fileName", Path.Combine(home, "lista.txt"))), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(read.Verified, Is.True, read.ErrorCode);
            Assert.That(read.Result?.ToString(), Does.Contain("pan"));
            Assert.That(found.Verified, Is.True, found.ErrorCode);
            Assert.That(found.Result?.GetProperty("entries").EnumerateArray()
                .Select(entry => entry.GetProperty("relativePath").GetString()),
                Is.EqualTo(new[] { Path.Combine("BAXY-bench", "lista.txt") }));
            Assert.That(outside.ErrorCode, Is.EqualTo("known_path_outside_folder"));
            Assert.That(outside.Result?.ToString() ?? string.Empty, Does.Not.Contain("secreto"));
            Assert.That(outsideFolder.ErrorCode, Is.EqualTo("known_path_outside_folder"));
            Assert.That(elsewhere.Verified, Is.False);
            Assert.That(elsewhere.Result?.ToString() ?? string.Empty, Does.Not.Contain("pan"));
        });
    }

    // A named file or folder goes to the Recycle Bin, where the person restores it; when the bin cannot take it, it
    // stays where it was.
    [Test]
    public async Task TrashSendsTheNamedFileOrFolderToTheRecycleBin()
    {
        using TemporaryDirectory temporary = new();
        (WindowsKnownFileAdapter adapter, string desktop, _, FolderRecycleBin bin) = Folders(temporary);
        await File.WriteAllTextAsync(Path.Combine(desktop, "viejo.txt"), "x");
        Directory.CreateDirectory(Path.Combine(desktop, "CarterTest", "sub"));
        await File.WriteAllTextAsync(Path.Combine(desktop, "CarterTest", "sub", "a.txt"), "x");
        using TemporaryDirectory other = new();
        (WindowsKnownFileAdapter refusing, string refusingDesktop, _, _) = Folders(other, binAccepts: false);
        await File.WriteAllTextAsync(Path.Combine(refusingDesktop, "queda.txt"), "x");

        ExternalCapabilityReceipt file = await adapter.InvokeAsync(
            "filesystem.known.trash.named", Json("""{"folder":"desktop","fileName":"viejo.txt"}"""), CancellationToken.None);
        ExternalCapabilityReceipt folder = await adapter.InvokeAsync(
            "filesystem.known.trash.named", Json("""{"folder":"desktop","fileName":"CarterTest"}"""), CancellationToken.None);
        ExternalCapabilityReceipt refused = await refusing.InvokeAsync(
            "filesystem.known.trash.named", Json("""{"folder":"desktop","fileName":"queda.txt"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(file.Verified, Is.True, file.ErrorCode);
            Assert.That(file.Result?.GetProperty("inRecycleBin").GetBoolean(), Is.True);
            Assert.That(File.Exists(Path.Combine(desktop, "viejo.txt")), Is.False);
            Assert.That(folder.Verified, Is.True, folder.ErrorCode);
            Assert.That(folder.Result?.GetProperty("entries").GetInt32(), Is.EqualTo(2));
            Assert.That(Directory.Exists(Path.Combine(desktop, "CarterTest")), Is.False);
            Assert.That(bin.Recycled, Has.Count.EqualTo(2));
            Assert.That(refused.ErrorCode, Is.EqualTo("known_file_not_recycled"));
            Assert.That(File.Exists(Path.Combine(refusingDesktop, "queda.txt")), Is.True);
        });
    }

    // Renew al máximo (E027): found nowhere in the folders walked, the result says nothing else was searched and which
    // configured folder searches more (the answer was «no lo encontré en ninguna carpeta de tu PC»); with
    // BAXY_AYUDAS=none, the folders walked alone.
    [TestCase("all", true)]
    [TestCase("none", false)]
    public async Task AFileFoundNowhereSaysNothingElseWasSearched(string aids, bool hint)
    {
        using IDisposable setting = Baxy.Providers.Windows.Infrastructure.ModelAids.Use(aids);
        using TemporaryDirectory temporary = new();
        string home = Path.Combine(temporary.Path, "home");
        string desktop = Path.Combine(home, "desktop");
        Directory.CreateDirectory(Path.Combine(home, "BAXY-bench"));
        Directory.CreateDirectory(desktop);
        await File.WriteAllTextAsync(Path.Combine(home, "BAXY-bench", "viejo.txt"), "x");
        var adapter = new WindowsKnownFileAdapter(new Dictionary<string, string[]>
        {
            ["desktop"] = [desktop],
            ["home"] = [home],
        }, new FolderRecycleBin(Path.Combine(temporary.Path, "bin"), true));

        ExternalCapabilityReceipt missing = await adapter.InvokeAsync(
            "filesystem.known.trash.named", Json("""{"folder":"all_known","fileName":"viejo.txt"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(missing.ErrorCode, Is.EqualTo("known_file_not_found"));
            Assert.That(missing.Result!.Value.TryGetProperty("next", out JsonElement next), Is.EqualTo(hint));
            if (hint)
            {
                Assert.That(next.GetString(), Is.EqualTo("viejo.txt is not in desktop, subfolders included; nothing else "
                    + "on the PC was searched; folder \"home\" searches more"));
            }
        });
    }

    // BAXY Renew (notebook): a name found nowhere says the folders walked; found twice, the places, as file.read
    // gives them; neither sends anything to the bin.
    [Test]
    public async Task TrashSaysWhereItLookedAndTheMatchesItCouldNotChooseBetween()
    {
        using TemporaryDirectory temporary = new();
        (WindowsKnownFileAdapter adapter, string desktop, string documents, FolderRecycleBin bin) = Folders(temporary);
        await File.WriteAllTextAsync(Path.Combine(desktop, "notas.txt"), "x");
        Directory.CreateDirectory(Path.Combine(documents, "viejas"));
        await File.WriteAllTextAsync(Path.Combine(documents, "viejas", "notas.txt"), "x");

        ExternalCapabilityReceipt missing = await adapter.InvokeAsync(
            "filesystem.known.trash.named", Json("""{"folder":"all_known","fileName":"nada.txt"}"""), CancellationToken.None);
        ExternalCapabilityReceipt ambiguous = await adapter.InvokeAsync(
            "filesystem.known.trash.named", Json("""{"folder":"all_known","fileName":"notas.txt"}"""), CancellationToken.None);

        JsonElement[] candidates = [.. ambiguous.Result!.Value.GetProperty("candidates").EnumerateArray()];
        Assert.Multiple(() =>
        {
            Assert.That(missing.ErrorCode, Is.EqualTo("known_file_not_found"));
            Assert.That(missing.EffectMayHaveOccurred, Is.False);
            Assert.That(missing.Result!.Value.GetProperty("searchedFolders").EnumerateArray().Select(item => item.GetString()),
                Is.EqualTo(new[] { "desktop", "documents" }));
            Assert.That(ambiguous.ErrorCode, Is.EqualTo("known_file_ambiguous"));
            Assert.That(candidates.Select(item => (item.GetProperty("folder").GetString(),
                    item.GetProperty("relativePath").GetString(), item.GetProperty("name").GetString())),
                Is.EquivalentTo(new[]
                {
                    ("desktop", "notas.txt", "notas.txt"),
                    ("documents", Path.Combine("viejas", "notas.txt"), "notas.txt"),
                }));
            Assert.That(bin.Recycled, Is.Empty);
        });
    }

    // Al máximo, flujos («¿Borro viejo.txt?» → «sí» → «no existe»): the name is looked up before the person is asked;
    // none or several is that refusal now (with its places), one leaves the call to ask; the read trashes nothing.
    [Test]
    public async Task TheReadBeforeTheYesRefusesANameThatIsNotThereOnce()
    {
        using TemporaryDirectory temporary = new();
        (WindowsKnownFileAdapter adapter, string desktop, string documents, FolderRecycleBin bin) = Folders(temporary);
        await File.WriteAllTextAsync(Path.Combine(desktop, "notas.txt"), "x");
        await File.WriteAllTextAsync(Path.Combine(documents, "notas.txt"), "x");
        await File.WriteAllTextAsync(Path.Combine(desktop, "viejo.txt"), "x");

        ExternalCapabilityReceipt? missing = await adapter.PreflightAsync(
            "filesystem.known.trash.named", Json("""{"folder":"all_known","fileName":"nada.txt"}"""), CancellationToken.None);
        ExternalCapabilityReceipt? ambiguous = await adapter.PreflightAsync(
            "filesystem.known.trash.named", Json("""{"folder":"all_known","fileName":"notas.txt"}"""), CancellationToken.None);
        ExternalCapabilityReceipt? one = await adapter.PreflightAsync(
            "filesystem.known.trash.named", Json("""{"folder":"desktop","fileName":"viejo.txt"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(missing?.ErrorCode, Is.EqualTo("known_file_not_found"));
            Assert.That(ambiguous?.ErrorCode, Is.EqualTo("known_file_ambiguous"));
            Assert.That(ambiguous?.Result?.GetProperty("candidates").GetArrayLength(), Is.EqualTo(2));
            Assert.That(one, Is.Null);
            Assert.That(bin.Recycled, Is.Empty);
            Assert.That(File.Exists(Path.Combine(desktop, "viejo.txt")), Is.True);
        });
    }

    [TestCase("", 0)]
    [TestCase("uno", 1)]
    [TestCase("uno\n", 1)]
    [TestCase("uno\ndos", 2)]
    [TestCase("uno\r\ndos\r\n", 2)]
    [TestCase("uno\rdos", 2)]
    [TestCase("uno\n\n", 2)]
    [TestCase("\n", 1)]
    public void LinesAreCountedAsAnEditorShowsThem(string text, int lines) =>
        Assert.That(WindowsKnownFileAdapter.LineCount(text), Is.EqualTo(lines));

    // «¿cuál es el archivo más grande?» (e2e p6 E020): the largest first, listing or searching.
    [Test]
    public async Task OrderBySizePutsTheLargestFirst()
    {
        using TemporaryDirectory temporary = new();
        (WindowsKnownFileAdapter adapter, string desktop, _, _) = Folders(temporary);
        Directory.CreateDirectory(Path.Combine(desktop, "fotos"));
        await File.WriteAllTextAsync(Path.Combine(desktop, "chico.txt"), "x");
        await File.WriteAllTextAsync(Path.Combine(desktop, "mediano.txt"), new string('x', 50));
        await File.WriteAllTextAsync(Path.Combine(desktop, "fotos", "grande.txt"), new string('x', 500));

        ExternalCapabilityReceipt listed = await adapter.InvokeAsync(
            "file.find", Json("""{"folder":"desktop","order":"size"}"""), CancellationToken.None);
        ExternalCapabilityReceipt searched = await adapter.InvokeAsync(
            "file.find", Json("""{"folder":"desktop","query":"*.txt","order":"size"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(listed.Result?.GetProperty("entries").EnumerateArray()
                    .Select(entry => entry.GetProperty("name").GetString()),
                Is.EqualTo(new[] { "mediano.txt", "chico.txt", "fotos" }));
            Assert.That(searched.Result?.GetProperty("files").EnumerateArray()
                    .Select(file => file.GetProperty("name").GetString() + ":" + file.GetProperty("size").GetInt64()),
                Is.EqualTo(new[] { "grande.txt:500", "mediano.txt:50", "chico.txt:1" }));
            Assert.That(searched.Result?.GetProperty("searchScope").GetProperty("timeLimitReached").GetBoolean(),
                Is.False);
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
            // Holdout v4 (falsedad): two files were not read as text, so the search read only part of the folder.
            Assert.That(found.Result?.GetProperty("readInPart").GetBoolean(), Is.True);
            Assert.That(narrowed.Result?.GetProperty("count").GetInt32(), Is.Zero);
            // Every *.md file was read as text: nothing read in part.
            Assert.That(narrowed.Result?.TryGetProperty("readInPart", out _), Is.False);
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

    // Renew al máximo (velocidad): a clock that stands still for the first files a walk looks at and then jumps past
    // its time limit, so a test stops the walk where it wants.
    private static Func<DateTime> StopAfter(int files)
    {
        DateTime start = new(2026, 10, 23, 12, 0, 0, DateTimeKind.Utc);
        int calls = 0;
        // The first call sets the deadline; each file looked at asks once more.
        return () => calls++ <= files ? start : start.AddHours(1);
    }

    private static WindowsKnownFileAdapter Home(string home, Func<DateTime>? utcNow = null) =>
        new(new Dictionary<string, string[]> { ["home"] = [home] },
            new FolderRecycleBin(Path.Combine(Path.GetDirectoryName(home)!, "bin"), true), utcNow: utcNow);

    // e2e pc-lote (notas.txt in home): file.read walked the whole profile with no limit (12-83 s) to refuse two copies
    // seen at once. With file.find's limit the walk stops, and what it says is only what it walked.
    [Test]
    public async Task ABareNameFoundOnceBeforeTheLimitIsReadAsTheOneSeenNotTheOnlyOne()
    {
        using TemporaryDirectory temporary = new();
        string home = Path.Combine(temporary.Path, "home");
        Directory.CreateDirectory(Path.Combine(home, "sub"));
        await File.WriteAllTextAsync(Path.Combine(home, "notas.txt"), "arriba");
        await File.WriteAllTextAsync(Path.Combine(home, "sub", "notas.txt"), "abajo");

        ExternalCapabilityReceipt stopped = await Home(home, StopAfter(1)).InvokeAsync(
            "file.read", Json("""{"folder":"home","fileName":"notas.txt"}"""), CancellationToken.None);
        ExternalCapabilityReceipt whole = await Home(home).InvokeAsync(
            "file.read", Json("""{"folder":"home","fileName":"notas.txt"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(stopped.ErrorCode, Is.Null);
            JsonElement result = stopped.Result!.Value;
            Assert.That(result.GetProperty("text").GetString(), Is.EqualTo("arriba"));
            Assert.That(result.GetProperty("relativePath").GetString(), Is.EqualTo("notas.txt"));
            Assert.That(result.GetProperty("onlyFileOfThatName").GetBoolean(), Is.False);
            Assert.That(result.GetProperty("searchScope").GetProperty("timeLimitReached").GetBoolean(), Is.True);
            Assert.That(result.GetProperty("searchScope").GetProperty("timeLimitSeconds").GetDouble(), Is.EqualTo(8));
            Assert.That(whole.ErrorCode, Is.EqualTo("known_file_ambiguous"));
            Assert.That(whole.Result!.Value.TryGetProperty("searchScope", out _), Is.False);
        });
    }

    // A whole walk says what it said before: a read of the one file of that name carries no walk facts.
    [Test]
    public async Task AWholeWalkReadsAsBefore()
    {
        using TemporaryDirectory temporary = new();
        string home = Path.Combine(temporary.Path, "home");
        Directory.CreateDirectory(Path.Combine(home, "sub"));
        await File.WriteAllTextAsync(Path.Combine(home, "sub", "registro.log"), "evento 1");

        ExternalCapabilityReceipt read = await Home(home).InvokeAsync(
            "file.read", Json("""{"folder":"home","fileName":"registro.log"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(read.ErrorCode, Is.Null);
            Assert.That(read.Result!.Value.GetProperty("text").GetString(), Is.EqualTo("evento 1"));
            Assert.That(read.Result!.Value.TryGetProperty("relativePath", out _), Is.False);
            Assert.That(read.Result!.Value.TryGetProperty("onlyFileOfThatName", out _), Is.False);
            Assert.That(read.Result!.Value.TryGetProperty("searchScope", out _), Is.False);
        });
    }

    // Two seen before the limit are ambiguous (that much is proven), and the places are the ones seen so far.
    [Test]
    public async Task TwoSeenBeforeTheLimitAreAmbiguousAndSaySoFar()
    {
        using TemporaryDirectory temporary = new();
        string home = Path.Combine(temporary.Path, "home");
        foreach (string folder in new[] { "a", "b", Path.Combine("c", "d") })
        {
            Directory.CreateDirectory(Path.Combine(home, folder));
            await File.WriteAllTextAsync(Path.Combine(home, folder, "notas.txt"), folder);
        }

        ExternalCapabilityReceipt stopped = await Home(home, StopAfter(2)).InvokeAsync(
            "file.read", Json("""{"folder":"home","fileName":"notas.txt"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(stopped.ErrorCode, Is.EqualTo("known_file_ambiguous"));
            JsonElement result = stopped.Result!.Value;
            Assert.That(result.GetProperty("candidates").EnumerateArray()
                    .Select(item => item.GetProperty("relativePath").GetString()),
                Is.EqualTo(new[] { Path.Combine("a", "notas.txt"), Path.Combine("b", "notas.txt") }));
            Assert.That(result.GetProperty("searchScope").GetProperty("timeLimitReached").GetBoolean(), Is.True);
        });
    }

    // None in what was walked is never «not there»: the walk stopped, and the rest of the folder was not searched.
    [TestCase("all", true)]
    [TestCase("none", false)]
    public async Task NoneBeforeTheLimitSaysTheRestWasNotSearched(string aids, bool hint)
    {
        using IDisposable setting = Baxy.Providers.Windows.Infrastructure.ModelAids.Use(aids);
        using TemporaryDirectory temporary = new();
        string home = Path.Combine(temporary.Path, "home");
        Directory.CreateDirectory(Path.Combine(home, "lejos"));
        await File.WriteAllTextAsync(Path.Combine(home, "otro.txt"), "x");
        await File.WriteAllTextAsync(Path.Combine(home, "lejos", "notas.txt"), "x");

        ExternalCapabilityReceipt stopped = await Home(home, StopAfter(1)).InvokeAsync(
            "file.read", Json("""{"folder":"home","fileName":"notas.txt"}"""), CancellationToken.None);
        ExternalCapabilityReceipt nowhere = await Home(home).InvokeAsync(
            "file.read", Json("""{"folder":"home","fileName":"nada.txt"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(stopped.ErrorCode, Is.EqualTo("known_file_not_found"));
            JsonElement result = stopped.Result!.Value;
            Assert.That(result.GetProperty("searchScope").GetProperty("timeLimitReached").GetBoolean(), Is.True);
            Assert.That(result.TryGetProperty("next", out JsonElement next), Is.EqualTo(hint));
            if (hint)
            {
                Assert.That(next.GetString(), Is.EqualTo("the search of home stopped at its 8 s limit: notas.txt is not "
                    + "in the part walked, and the rest was not searched; a subdirectory or the relativePath file_find "
                    + "gives looks only there"));
            }
            Assert.That(nowhere.ErrorCode, Is.EqualTo("known_file_not_found"));
            Assert.That(nowhere.Result!.Value.GetProperty("searchScope").TryGetProperty("timeLimitReached", out _),
                Is.False);
            Assert.That(nowhere.Result!.Value.TryGetProperty("next", out _), Is.False);
        });
    }

    // A name that is nowhere gives its stems from the same walk (it walked twice: once for the name, once for them).
    [Test]
    public async Task TheStemsOfANameThatIsNowhereComeFromTheSameWalk()
    {
        using TemporaryDirectory temporary = new();
        string home = Path.Combine(temporary.Path, "home");
        Directory.CreateDirectory(Path.Combine(home, "sub"));
        await File.WriteAllTextAsync(Path.Combine(home, "sub", "notas.md"), "x");
        int calls = 0;
        DateTime start = DateTime.UtcNow;

        ExternalCapabilityReceipt missing = await Home(home, () => { calls++; return start; }).InvokeAsync(
            "file.read", Json("""{"folder":"home","fileName":"notas"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(missing.ErrorCode, Is.EqualTo("known_file_not_found"));
            Assert.That(missing.Result!.Value.GetProperty("candidates").EnumerateArray()
                .Select(item => item.GetProperty("relativePath").GetString()), Is.EqualTo(new[]
                {
                    Path.Combine("sub", "notas.md"),
                }));
            // One deadline and one look at the one file: a single walk.
            Assert.That(calls, Is.EqualTo(2));
        });
    }

    // An edit of the one seen before the limit writes nothing: a deeper copy that was not walked may be the one meant.
    // It names the one seen, says the walk stopped and (aid search_scope) how to edit it; its path edits it.
    [TestCase("all", true)]
    [TestCase("none", false)]
    public async Task AnEditOfTheOneSeenBeforeTheLimitChangesNothingAndNamesIt(string aids, bool hint)
    {
        using IDisposable setting = Baxy.Providers.Windows.Infrastructure.ModelAids.Use(aids);
        using TemporaryDirectory temporary = new();
        string home = Path.Combine(temporary.Path, "home");
        Directory.CreateDirectory(Path.Combine(home, "sub"));
        await File.WriteAllTextAsync(Path.Combine(home, "notas.txt"), "lunes");
        await File.WriteAllTextAsync(Path.Combine(home, "sub", "notas.txt"), "lunes");
        var bin = new FolderRecycleBin(Path.Combine(temporary.Path, "bin"), true);
        var adapter = new WindowsKnownFileAdapter(
            new Dictionary<string, string[]> { ["home"] = [home] }, bin, utcNow: StopAfter(1));

        ExternalCapabilityReceipt refused = await adapter.InvokeAsync("file.edit", Json(
            """{"folder":"home","fileName":"notas.txt","oldText":"lunes","newText":"martes"}"""), CancellationToken.None);
        ExternalCapabilityReceipt byPath = await Home(home, StopAfter(0)).InvokeAsync("file.edit", Json(
            """{"folder":"home","fileName":"sub/notas.txt","oldText":"lunes","newText":"martes"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(refused.ErrorCode, Is.EqualTo("known_file_search_incomplete"));
            Assert.That(refused.EffectObserved, Is.False);
            Assert.That(refused.EffectMayHaveOccurred, Is.False);
            JsonElement result = refused.Result!.Value;
            Assert.That(result.GetProperty("relativePath").GetString(), Is.EqualTo("notas.txt"));
            Assert.That(result.GetProperty("changed").GetBoolean(), Is.False);
            Assert.That(result.GetProperty("searchScope").GetProperty("timeLimitReached").GetBoolean(), Is.True);
            Assert.That(result.TryGetProperty("next", out JsonElement next), Is.EqualTo(hint));
            if (hint)
            {
                Assert.That(next.GetString(), Is.EqualTo("nothing was changed: the search of home stopped at its 8 s "
                    + "limit after finding notas.txt, and the rest of the folder was not searched, so another file of "
                    + "that name may be there; naming the subdirectory or the path (fileName \"notas.txt\") edits that one"));
            }
            Assert.That(File.ReadAllText(Path.Combine(home, "notas.txt")), Is.EqualTo("lunes"), "nothing was written");
            Assert.That(bin.Recycled, Is.Empty, "nothing went to the bin");
            // Named by its place, the file is looked up there with no walk: the edit goes ahead.
            Assert.That(byPath.ErrorCode, Is.Null);
            Assert.That(File.ReadAllText(Path.Combine(home, "sub", "notas.txt")), Is.EqualTo("martes"));
        });
    }
}
