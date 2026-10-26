using System.IO;
using System.Diagnostics;
using System.Reflection;
using System.Text.Json.Nodes;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// The folder the person named is the place of the turn's file calls (src/Baxy.App/SaidFolders.cs): a call that leaves
/// it out is routed into it when it only reads, refused before any effect with the call that names it otherwise, and
/// runs as written, saying it acted outside it, only when the model writes the same call again. Holdout v4 «archivos»
/// passed 3/10 in every configuration with these shapes: a full path said and a write that kept only the file's name
/// (E006, E017, E019), a folder named only by its name and a write, an append, a delete or an overwrite in the home
/// folder (E024, E027, E030), and a question about it answered from BAXY's working folder or the home folder (E020).
/// </summary>
[TestFixture]
[NonParallelizable]
public sealed class SaidFoldersTests
{
    private string _root = string.Empty;
    private string _home = string.Empty;

    [SetUp]
    public void SetUp()
    {
        _root = Path.Combine(Path.GetTempPath(), "baxy-said-" + Guid.NewGuid().ToString("N"));
        _home = Path.Combine(_root, "perfil");
        foreach (string folder in (string[])["Desktop", "Documents", "Downloads", "banco-local", "obra", "baxy",
                     Path.Combine("Documents", "obra"), Path.Combine("Desktop", "banco-local"), "Mi Obra Nueva"])
            Directory.CreateDirectory(Path.Combine(_home, folder));
        File.WriteAllText(Path.Combine(_home, "banco-local", "apuntes.txt"), "uno\n");
        File.WriteAllText(Path.Combine(_home, "banco-local", "viejo.txt"), "algo\n");
        var hidden = new DirectoryInfo(Path.Combine(_home, "secreta"));
        hidden.Create();
        hidden.Attributes |= FileAttributes.Hidden;
    }

    [TearDown]
    public void TearDown()
    {
        var hidden = new DirectoryInfo(Path.Combine(_home, "secreta"));
        if (hidden.Exists)
            hidden.Attributes &= ~FileAttributes.Hidden;
        Directory.Delete(_root, recursive: true);
    }

    // E006 / E017 shape: a full path said, and a write that kept only the file's name in the home folder.
    [Test]
    public void AWriteThatLeavesOutAFullPathSaidIsRefusedWithTheCallThatNamesIt()
    {
        SaidFolders said = Heard($@"guarda en {_home}\banco-local un archivo recados.txt que diga: comprar pan");
        var call = new JsonObject { ["relativePath"] = "recados.txt", ["text"] = "comprar pan", ["folder"] = "home" };

        SaidFolders.Ruling? first = said.Rule("file.write", Descriptor("file.write"), call);
        SaidFolders.Ruling? again = said.Rule("file.write", Descriptor("file.write"), call);

        Assert.Multiple(() =>
        {
            Assert.That(first?.Refusal, Is.Not.Null);
            string next = (string?)first!.Refusal!["next"] ?? string.Empty;
            Assert.That(next, Does.StartWith("nothing ran: the person named "));
            Assert.That(next, Does.Contain("call file_write again with relativePath \"banco-local/recados.txt\""));
            Assert.That(next, Does.Contain(Path.Combine(_home, "recados.txt")));
            Assert.That(first.Refusal["saidFolders"]!.AsArray().Select(static node => (string?)node),
                Is.EqualTo(new[] { Path.Combine(_home, "banco-local") }));
            // The same call written again runs as written, and its result says it acted outside the folder named.
            Assert.That(again?.Refusal, Is.Null);
            Assert.That(again?.Arguments.ToJsonString(), Is.EqualTo(call.ToJsonString()));
            Assert.That(again?.Note, Does.Contain("outside it, as it was written"));
        });
    }

    [TestCase("banco-local/recados.txt", "home")]
    [TestCase(@"banco-local\recados.txt", "home")]
    [TestCase("{home}\\banco-local\\recados.txt", "home")]
    [TestCase("{home}\\banco-local\\recados.txt", null)]
    public void AWriteInsideTheFolderSaidRunsAsItIs(string relativePath, string? folder)
    {
        SaidFolders said = Heard($@"guarda en {_home}\banco-local un archivo recados.txt que diga: comprar pan");
        var call = new JsonObject { ["relativePath"] = relativePath.Replace("{home}", _home), ["text"] = "pan" };
        if (folder is not null)
            call["folder"] = folder;

        Assert.That(said.Rule("file.write", Descriptor("file.write"), call), Is.Null);
    }

    // E024 / E030 shape: a folder named only by its name; the append (or the overwrite) went to the home folder.
    [Test]
    public void AnAppendThatLeavesOutAFolderNamedByItsNameIsRefused()
    {
        SaidFolders said = Heard("pon al final de apuntes.txt, en la carpeta banco-local, la frase revisar la estufa");
        var call = new JsonObject
        {
            ["relativePath"] = "apuntes.txt",
            ["text"] = "revisar la estufa",
            ["folder"] = "home",
            ["append"] = true,
        };

        SaidFolders.Ruling? ruling = said.Rule("file.write", Descriptor("file.write"), call);

        // banco-local is also on the Desktop, without apuntes.txt: the one that holds it is the place.
        string next = (string?)ruling?.Refusal?["next"] ?? string.Empty;
        Assert.Multiple(() =>
        {
            Assert.That(next, Does.Contain("call file_write again with relativePath \"banco-local/apuntes.txt\" (it acts in "
                + Path.Combine(_home, "banco-local", "apuntes.txt") + ");"));
            Assert.That(next, Does.Not.Contain("folder \"desktop\""));
            Assert.That(next, Does.Contain("If " + Path.Combine(_home, "banco-local")
                + " (apuntes.txt is there) is the place of this call"));
            Assert.That(said.Rule("file.write", Descriptor("file.write"), new JsonObject
            {
                ["relativePath"] = "banco-local/apuntes.txt",
                ["text"] = "revisar la estufa",
                ["folder"] = "home",
            }), Is.Null);
        });
    }

    // Holdout v6 (V6F010): a file named with its words otherwise separated («lista invitados.txt» for
    // lista_invitados.txt) is the file the folder holds: of two folders of the name said, the one that holds it is the
    // place, said with the file's own name.
    [Test]
    public void AFileNamedWithOtherSeparatorsIsHeldByTheFolderThatHasIt()
    {
        File.WriteAllText(Path.Combine(_home, "banco-local", "lista_invitados.txt"), "Ana\n");
        SaidFolders said = Heard("agrega a Pedro al final de lista invitados.txt, en la carpeta banco-local");
        SaidFolders.Ruling? ruling = said.Rule("file.write", Descriptor("file.write"), new JsonObject
        {
            ["relativePath"] = "lista invitados.txt",
            ["text"] = "Pedro",
            ["folder"] = "home",
            ["append"] = true,
        });

        string next = (string?)ruling?.Refusal?["next"] ?? string.Empty;
        Assert.Multiple(() =>
        {
            Assert.That(next, Does.Contain("If " + Path.Combine(_home, "banco-local")
                + " (lista_invitados.txt is there) is the place of this call"));
            Assert.That(next, Does.Not.Contain("folder \"desktop\""));
        });
    }

    // Of two folders of that name, neither holding the file, both are offered, each said with what it holds.
    [Test]
    public void ANameInTwoFoldersOffersBoth()
    {
        SaidFolders said = Heard("crea compras.txt en banco-local con leche");
        SaidFolders.Ruling? ruling = said.Rule("file.write", Descriptor("file.write"),
            new JsonObject { ["relativePath"] = "compras.txt", ["text"] = "leche", ["folder"] = "home" });

        string next = (string?)ruling?.Refusal?["next"] ?? string.Empty;
        Assert.Multiple(() =>
        {
            Assert.That(next, Does.Contain("If one of them is the place of this call"));
            Assert.That(next, Does.Contain("relativePath \"banco-local/compras.txt\" for "
                + Path.Combine(_home, "banco-local") + " (no compras.txt there)"));
            Assert.That(next, Does.Contain("relativePath \"banco-local/compras.txt\" and folder \"desktop\" for "));
        });
    }

    // E020 shape: a read of the home folder is routed into the folder named; «en mi carpeta de usuario» says which of
    // the two folders of that name it is.
    [Test]
    public void AReadThatLeavesOutTheFolderNamedIsRoutedThere()
    {
        SaidFolders said = Heard("¿qué archivo pesa más dentro de banco-local, en mi carpeta de usuario?");
        var call = new JsonObject { ["folder"] = "home", ["order"] = "size" };

        SaidFolders.Ruling? routed = said.Rule("file.find", Descriptor("file.find"), call);
        SaidFolders.Ruling? again = said.Rule("file.find", Descriptor("file.find"), call);

        Assert.Multiple(() =>
        {
            Assert.That(routed?.Refusal, Is.Null);
            Assert.That(routed?.Arguments.ToJsonString(),
                Is.EqualTo("{\"folder\":\"home\",\"order\":\"size\",\"subdirectory\":\"banco-local\"}"));
            Assert.That(routed?.Note, Does.Contain("this call looked in " + Path.Combine(_home, "banco-local")
                + " (subdirectory \"banco-local\") instead of " + _home));
            Assert.That(again?.Arguments.ToJsonString(), Is.EqualTo(call.ToJsonString()));
            Assert.That(again?.Note, Does.Contain("it did not look at or change anything in that folder"));
        });
    }

    [Test]
    public void AReadOfOtherFoldersByAFileNameIsRoutedToTheFolderThatHoldsIt()
    {
        SaidFolders said = Heard("lee apuntes.txt de banco-local");

        SaidFolders.Ruling? routed = said.Rule("file.read", Descriptor("file.read"),
            new JsonObject { ["fileName"] = Path.Combine(_home, "apuntes.txt"), ["folder"] = "all_known" });

        Assert.That(routed?.Arguments.ToJsonString(),
            Is.EqualTo("{\"fileName\":\"apuntes.txt\",\"folder\":\"home\",\"subdirectory\":\"banco-local\"}"));
    }

    // E020 shape: BAXY's working folder is not the person's.
    [Test]
    public void ALookAtTheWorkingFolderIsRefusedWithTheLookAtTheFolderNamed()
    {
        SaidFolders said = Heard("¿cuál es el archivo más grande de banco-local en mi carpeta de usuario?");

        string next = (string?)said.Rule("filesystem.list", Descriptor("filesystem.list"), new JsonObject())
            ?.Refusal?["next"] ?? string.Empty;

        Assert.That(next, Does.Contain("filesystem_list acts only in BAXY's own working folder")
            .And.Contain("to look there, call file_find with folder \"home\" and subdirectory \"banco-local\""));
    }

    // Holdout v6 V6E042: told only that file_find «looks there», the model wrote the same filesystem_search again; the
    // look is said as a call, with the name the search looked for.
    [Test]
    public void ASearchOfTheWorkingFolderIsRefusedWithTheCallThatLooksForItInTheFolderNamed()
    {
        Directory.CreateDirectory(Path.Combine(_home, "cajones", "azul"));
        SaidFolders said = Heard("busca en cajones dónde está el file llaves.txt, que no me acuerdo en cuál lo dejé");

        string next = (string?)said.Rule("filesystem.search", Descriptor("filesystem.search"),
            new JsonObject { ["query"] = "llaves.txt" })?.Refusal?["next"] ?? string.Empty;

        Assert.That(next, Does.Contain(
            "to look there, call file_find with query \"llaves.txt\" and folder \"home\" and subdirectory \"cajones\""));
    }

    // Holdout v6 V6E042 (cien s0 and s2): the refused search written again ran in the working folder, its note said only
    // what it had not looked at, and the model answered «no está en mi carpeta de trabajo». The note of the search that
    // ran as written says the look at the folder named as a call too.
    [Test]
    public void ASearchOfTheWorkingFolderWrittenAgainRunsAndItsNoteSaysTheCallThatLooksInTheFolderNamed()
    {
        Directory.CreateDirectory(Path.Combine(_home, "cajones", "azul"));
        SaidFolders said = Heard("busca en cajones dónde está el file llaves.txt, que no me acuerdo en cuál lo dejé");
        var search = new JsonObject { ["query"] = "llaves.txt" };

        said.Rule("filesystem.search", Descriptor("filesystem.search"), search);
        SaidFolders.Ruling? again = said.Rule("filesystem.search", Descriptor("filesystem.search"), search);

        Assert.Multiple(() =>
        {
            Assert.That(again?.Refusal, Is.Null);
            Assert.That(again?.Note, Does.Contain("it did not look at or change anything in that folder; to look there, "
                + "call file_find with query \"llaves.txt\" and folder \"home\" and subdirectory \"cajones\""));
        });
    }

    // E027 shape: a delete is never routed; it is refused with the call that names the folder.
    [Test]
    public void ADeleteThatLeavesOutTheFolderNamedIsRefused()
    {
        SaidFolders said = Heard("manda a la papelera viejo.txt de la carpeta banco-local");

        string next = (string?)said.Rule("filesystem.known.trash.named", Descriptor("filesystem.known.trash.named"),
            new JsonObject { ["fileName"] = "viejo.txt", ["folder"] = "all_known" })?.Refusal?["next"] ?? string.Empty;

        Assert.That(next, Does.Contain(
            "call filesystem_known_trash_named again with folder \"home\" and subdirectory \"banco-local\" (it acts in "
            + Path.Combine(_home, "banco-local") + ");"));
    }

    // E019 shape: with a full path said, a folder elsewhere with the name of the one to make is not a place.
    [Test]
    public void AFolderMadeOutsideTheFullPathSaidIsRefusedEvenIfOneOfThatNameExists()
    {
        SaidFolders said = Heard($@"en {_home}\banco-local crea una carpeta obra con las subcarpetas a y b");

        SaidFolders.Ruling? ruling = said.Rule("filesystem.create.directory", Descriptor("filesystem.create.directory"),
            new JsonObject { ["relativePath"] = "obra/a", ["folder"] = "home" });

        Assert.That((string?)ruling?.Refusal?["next"], Does.Contain("relativePath \"banco-local/obra/a\""));
    }

    [Test]
    public void ARelativePathFromAKnownFolderIsThatFolder()
    {
        SaidFolders said = Heard("crea el archivo lista.md en Documentos/obra");

        Assert.Multiple(() =>
        {
            Assert.That(said.Places().Select(static place => place.Path),
                Is.EqualTo(new[] { Path.Combine(_home, "Documents", "obra") }));
            Assert.That((string?)said.Rule("file.write", Descriptor("file.write"),
                    new JsonObject { ["relativePath"] = "lista.md", ["text"] = "x", ["folder"] = "documents" })
                ?.Refusal?["next"], Does.Contain("relativePath \"obra/lista.md\""));
            Assert.That(said.Rule("file.write", Descriptor("file.write"),
                new JsonObject { ["relativePath"] = "obra/lista.md", ["text"] = "x", ["folder"] = "documents" }), Is.Null);
        });
    }

    [Test]
    public void AKnownFolderByThePersonsNameForItIsAPlace()
    {
        SaidFolders said = Heard("guarda notas.txt en el escritorio");

        Assert.Multiple(() =>
        {
            Assert.That((string?)said.Rule("file.write", Descriptor("file.write"),
                    new JsonObject { ["relativePath"] = "notas.txt", ["text"] = "x", ["folder"] = "home" })
                ?.Refusal?["next"], Does.Contain("call file_write again with relativePath \"notas.txt\" and folder \"desktop\" (it acts in "
                    + Path.Combine(_home, "Desktop", "notas.txt") + "); any other call of this turn in that folder says it the same way, "
                    + "folder \"desktop\";"));
            Assert.That(said.Rule("file.write", Descriptor("file.write"),
                new JsonObject { ["relativePath"] = "notas.txt", ["text"] = "x", ["folder"] = "desktop" }), Is.Null);
        });
    }

    // A copy from a folder whose name is also on the Desktop to the Desktop: the Desktop stays a place of its own.
    [Test]
    public void AKnownFolderNamedBesideANameItAlsoHoldsStaysAPlace()
    {
        SaidFolders said = Heard("copia apuntes.txt de banco-local al escritorio");

        Assert.Multiple(() =>
        {
            Assert.That(said.Rule("file.write", Descriptor("file.write"),
                new JsonObject { ["relativePath"] = "apuntes.txt", ["text"] = "uno", ["folder"] = "desktop" }), Is.Null);
            Assert.That(said.Rule("file.read", Descriptor("file.read"), new JsonObject
            {
                ["fileName"] = "apuntes.txt",
                ["folder"] = "home",
                ["subdirectory"] = "banco-local",
            }), Is.Null);
        });
    }

    [Test]
    public void AFullPathWithSpacesIsTheFolderItNames()
    {
        SaidFolders said = Heard($@"crea x.txt en {_home}\Mi Obra Nueva por favor");

        Assert.That(said.Places().Select(static place => place.Path),
            Is.EqualTo(new[] { Path.Combine(_home, "Mi Obra Nueva") }));
    }

    // Contracases: no folder of the person's is named (BAXY's own name, a hidden folder, nothing), or the call is not
    // about files: nothing changes.
    [TestCase("baxy, crea compras.txt con leche")]
    [TestCase("crea secreta.txt en la carpeta secreta")]
    [TestCase("crea compras.txt con leche")]
    public void WithNoFolderOfThePersonsNamedTheCallRunsAsItIs(string words)
    {
        SaidFolders said = Heard(words);

        Assert.That(said.Rule("file.write", Descriptor("file.write"),
            new JsonObject { ["relativePath"] = "compras.txt", ["text"] = "leche", ["folder"] = "home" }), Is.Null);
    }

    [Test]
    public void ACallThatIsNotAboutFilesRunsAsItIs()
    {
        SaidFolders said = Heard("pon el volumen al 30 en banco-local");

        Assert.That(said.Rule("audio.volume", Descriptor("audio.volume"), new JsonObject { ["level"] = 30 }), Is.Null);
    }

    [Test]
    public void AToolThatCannotReachTheFolderSaysSo()
    {
        SaidFolders said = Heard("haz una presentación sobre el agua en banco-local");

        string next = (string?)said.Rule("document.presentation.create", Descriptor("document.presentation.create"),
            new JsonObject { ["folder"] = "documents", ["title"] = "El agua" })?.Refusal?["next"] ?? string.Empty;

        Assert.That(next, Does.Contain("document_presentation_create reaches only the folders"));
    }

    [Test]
    public void WithTheAidOffNothingChanges()
    {
        string? before = Environment.GetEnvironmentVariable("BAXY_AYUDAS");
        Environment.SetEnvironmentVariable("BAXY_AYUDAS", "none");
        try
        {
            SaidFolders said = Heard($@"guarda en {_home}\banco-local recados.txt");
            Assert.That(said.Rule("file.write", Descriptor("file.write"),
                new JsonObject { ["relativePath"] = "recados.txt", ["text"] = "x", ["folder"] = "home" }), Is.Null);
        }
        finally
        {
            Environment.SetEnvironmentVariable("BAXY_AYUDAS", before);
        }
    }

    // In the turn loop: the refused call never reaches the engine, and the model reads why.
    [Test]
    public async Task TheTurnLoopRefusesTheCallBeforeItReachesTheEngine()
    {
        using var fake = new FakeMind();
        fake.Script(new JsonObject
        {
            ["reply"] = new JsonObject
            {
                ["turn.decide"] = new JsonObject
                {
                    ["type"] = "turn.result",
                    ["kind"] = "action",
                    ["operation"] = "file.write",
                    ["arguments"] = new JsonObject { ["relativePath"] = "recados.txt", ["text"] = "pan", ["folder"] = "home" },
                },
                ["turn.continue"] = new JsonObject
                {
                    ["type"] = "turn.result",
                    ["kind"] = "clarify",
                    ["question"] = "¿Lo guardo en banco-local?",
                },
            },
        });
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        var core = new CoreProcessClient();
        const BindingFlags Private = BindingFlags.Instance | BindingFlags.NonPublic;
        typeof(CoreProcessClient).GetField("_ready", Private)!.SetValue(core, true);
        typeof(CoreProcessClient).GetField("_process", Private)!.SetValue(core, Process.GetCurrentProcess());
        var steps = new List<NativeTurnStep>();
        var registry = new RetryableOperationRegistry();
        var loop = new NativeTurnLoop(new NativeTurnLoop.Host
        {
            Core = () => core,
            Mind = () => mind,
            Registry = () => registry,
            MemoryProtector = static () => null,
            Publish = static (_, _) => { },
            Fail = static _ => { },
            Notice = static _ => { },
            StepCompleted = steps.Add,
            PersonFolder = Known,
        });

        await loop.RunAsync($@"guarda en {_home}\banco-local recados.txt que diga pan", Stopwatch.GetTimestamp(),
            CancellationToken.None);

        JsonNode? observed = JsonNode.Parse(steps.Single().Observation);
        Assert.Multiple(() =>
        {
            Assert.That((steps[0].Operation, steps[0].Status, steps[0].Sent), Is.EqualTo(("file.write", "rejected", false)));
            Assert.That((string?)observed?["error"], Is.EqualTo(SaidFolders.LeftOut));
            Assert.That((string?)observed?["next"], Does.Contain("relativePath \"banco-local/recados.txt\""));
        });
    }

    // Auditoría de la App (2026-10-23): a spoken «sí» to the waiting call keeps the folders of the turn that asked it, as
    // the Sí button does; before, «sí» replaced them and the write after it went to the home folder unruled.
    [Test]
    public async Task ASpokenYesKeepsTheFoldersOfTheTurnThatAsked()
    {
        using var fake = new FakeMind();
        fake.Script(new JsonObject
        {
            ["reply"] = new JsonObject
            {
                ["turn.decide"] = new JsonObject
                {
                    ["type"] = "turn.result",
                    ["kind"] = "action",
                    ["operation"] = "web.fetch",
                    ["arguments"] = new JsonObject { ["url"] = "https://exfil.example/c" },
                },
                ["turn.continue"] = new JsonObject
                {
                    ["type"] = "turn.result", ["kind"] = "conversation", ["reply"] = "¿Abro esa página?",
                },
            },
        });
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        var core = new CoreProcessClient();
        const BindingFlags Private = BindingFlags.Instance | BindingFlags.NonPublic;
        typeof(CoreProcessClient).GetField("_ready", Private)!.SetValue(core, true);
        typeof(CoreProcessClient).GetField("_process", Private)!.SetValue(core, Process.GetCurrentProcess());
        var steps = new List<NativeTurnStep>();
        var registry = new RetryableOperationRegistry();
        var loop = new NativeTurnLoop(new NativeTurnLoop.Host
        {
            Core = () => core,
            Mind = () => mind,
            Registry = () => registry,
            MemoryProtector = static () => null,
            Publish = static (_, _) => { },
            Fail = static _ => { },
            Notice = static _ => { },
            StepCompleted = steps.Add,
            PersonFolder = Known,
        });
        await loop.RunAsync($@"lee la página que te dije y guarda lo que diga en {_home}\banco-local",
            Stopwatch.GetTimestamp(), CancellationToken.None);
        Assert.That(loop.HasPendingConfirmation, Is.True);

        fake.Script(new JsonObject
        {
            ["reply"] = new JsonObject
            {
                ["turn.decide"] = new JsonObject
                {
                    ["type"] = "turn.result",
                    ["kind"] = "action",
                    ["operation"] = "file.write",
                    ["arguments"] = new JsonObject { ["relativePath"] = "pagina.txt", ["text"] = "x", ["folder"] = "home" },
                },
                ["turn.continue"] = new JsonObject
                {
                    ["type"] = "turn.result", ["kind"] = "clarify", ["question"] = "¿Lo guardo en banco-local?",
                },
            },
        });
        await loop.RunAsync("sí", Stopwatch.GetTimestamp(), CancellationToken.None);

        NativeTurnStep write = steps[^1];
        Assert.Multiple(() =>
        {
            Assert.That((write.Operation, write.Status, write.Sent), Is.EqualTo(("file.write", "rejected", false)));
            Assert.That((string?)JsonNode.Parse(write.Observation)?["error"], Is.EqualTo(SaidFolders.LeftOut));
        });
    }

    // Holdout v5 V5E043/V5E031 (notebook): «documentos» named Documents and also a folder «Documentos» inside it; the
    // inner one, as a folder the outer holds, took its place and sent «crea … en documentos» to Documentos\Documentos.
    [Test]
    public void AKnownFolderSaidStaysThePlaceWhenItHoldsAFolderOfItsName()
    {
        Directory.CreateDirectory(Path.Combine(_home, "Documents", "Documentos"));
        SaidFolders said = Heard("crea una carpeta que se llame Viaje Chiloé 2027 en documentos");

        Assert.Multiple(() =>
        {
            Assert.That(said.Places().Select(static place => place.Path),
                Is.EqualTo(new[] { Path.Combine(_home, "Documents") }));
            Assert.That(said.Rule("filesystem.create.directory", Descriptor("filesystem.create.directory"),
                new JsonObject { ["folder"] = "documents", ["relativePath"] = "Viaje Chiloé 2027" }), Is.Null);
        });
    }

    // Holdout v5 V5E043: the folder the person asked for, made in this turn, holds the file they asked to write in it;
    // the write that left it out (in Documents itself) went through because the folders named were read before it
    // existed.
    [Test]
    public void AFolderMadeInTheTurnIsThePlaceOfTheNextCall()
    {
        SaidFolders said = Heard("en documentos crea la carpeta viaje chiloe 2027 y dentro un archivo itinerario.txt");
        Assert.That(said.Rule("filesystem.create.directory", Descriptor("filesystem.create.directory"),
            new JsonObject { ["folder"] = "documents", ["relativePath"] = "viaje chiloe 2027" }), Is.Null);
        Directory.CreateDirectory(Path.Combine(_home, "Documents", "viaje chiloe 2027"));

        SaidFolders.Ruling? write = said.Rule("file.write", Descriptor("file.write"),
            new JsonObject { ["folder"] = "documents", ["relativePath"] = "itinerario.txt", ["text"] = "día 1" });

        Assert.That((string?)write?.Refusal?["next"],
            Does.Contain("call file_write again with relativePath \"viaje chiloe 2027/itinerario.txt\""));
    }

    // Holdout v8 (falsedades #16, cien and final2, s0 and s1): «haz una carpeta cumple_benja en BAXY-bench, adentro un
    // archivo lista.txt»; the model made BAXY-bench/cumple_benja and wrote lista.txt in the home folder, and the refusal
    // offered BAXY-bench/lista.txt, beside the folder just made. A folder BAXY made in this turn inside the folder named
    // is a place of it: the only one made is the place of a write that names what no place holds, and a read of what it
    // holds is routed into it. The folder named stays a place of its own.
    [Test]
    public void AFolderMadeInTheTurnInsideTheFolderNamedIsThePlaceOfTheWriteThatLeftItOut()
    {
        string bench = Path.Combine(_home, "taller-bench");
        string party = Path.Combine(bench, "cumple_benja");
        Directory.CreateDirectory(bench);
        File.WriteAllText(Path.Combine(bench, "invitados.txt"), "ana\n");
        SaidFolders said = Heard("haz una carpeta cumple_benja en taller-bench, adentro un archivo lista.txt que diga globos");
        var make = new JsonObject { ["relativePath"] = "taller-bench/cumple_benja", ["folder"] = "home" };
        Assert.That(said.Rule("filesystem.create.directory", Descriptor("filesystem.create.directory"), make), Is.Null);
        Directory.CreateDirectory(party);
        said.Ran("filesystem.create.directory", make, "completed");

        string next = (string?)said.Rule("file.write", Descriptor("file.write"), new JsonObject
        {
            ["relativePath"] = "lista.txt", ["text"] = "globos", ["folder"] = "home",
        })?.Refusal?["next"] ?? string.Empty;
        File.WriteAllText(Path.Combine(party, "lista.txt"), "globos\n");
        SaidFolders.Ruling? read = said.Rule("file.read", Descriptor("file.read"),
            new JsonObject { ["fileName"] = "lista.txt", ["folder"] = "home" });
        SaidFolders.Ruling? beside = said.Rule("file.read", Descriptor("file.read"),
            new JsonObject { ["fileName"] = "invitados.txt", ["folder"] = "home" });

        Assert.Multiple(() =>
        {
            Assert.That(next, Does.Contain($"If {party}, the folder this turn made in it, is the place of this call, call "
                + $"file_write again with relativePath \"taller-bench/cumple_benja/lista.txt\" (it acts in "
                + $"{Path.Combine(party, "lista.txt")})"));
            Assert.That(next, Does.Not.Contain("\"taller-bench/lista.txt\""));
            Assert.That(read?.Arguments["subdirectory"]?.GetValue<string>(), Is.EqualTo("taller-bench/cumple_benja"));
            Assert.That(beside?.Arguments["subdirectory"]?.GetValue<string>(), Is.EqualTo("taller-bench"));
            Assert.That(said.Rule("file.write", Descriptor("file.write"), new JsonObject
            {
                ["relativePath"] = "taller-bench/notas.txt", ["text"] = "x", ["folder"] = "home",
            }), Is.Null);
        });
    }

    // Final7 e2e: «hazme una carpeta viajes en BAXY-bench», then «y adentro deja itinerario.txt»; the turn that names no
    // folder was ruled by BAXY-bench, but the folder the previous request made was no place any more and the refusal
    // offered BAXY-bench/itinerario.txt, beside it. The folders a request made stay places of the next one that is ruled
    // by its folders, and go with them after a heartbeat.
    [Test]
    public void AFolderThePreviousRequestMadeIsThePlaceOfTheWriteOfTheNextOne()
    {
        string bench = Path.Combine(_home, "taller-bench");
        string trips = Path.Combine(bench, "viajes");
        Directory.CreateDirectory(bench);
        var make = new JsonObject { ["relativePath"] = "taller-bench/viajes", ["folder"] = "home" };
        var write = new JsonObject { ["relativePath"] = "itinerario.txt", ["text"] = "vuelo a las 9", ["folder"] = "home" };
        SaidFolders said = Heard("hazme una carpeta viajes en taller-bench");
        Directory.CreateDirectory(trips);
        said.Ran("filesystem.create.directory", make, "completed");
        said.Heard("y adentro deja itinerario.txt que diga vuelo a las 9");
        string next = (string?)said.Rule("file.write", Descriptor("file.write"), write)?.Refusal?["next"] ?? string.Empty;

        SaidFolders cleared = Heard("hazme una carpeta viajes en taller-bench");
        cleared.Ran("filesystem.create.directory", make, "completed");
        cleared.Clear();
        cleared.Heard("y adentro deja itinerario.txt que diga vuelo a las 9");

        Assert.Multiple(() =>
        {
            Assert.That(next, Does.StartWith("nothing ran: the person's previous request named «taller-bench»"));
            Assert.That(next, Does.Contain($"If {trips}, the folder that request made in it, is the place of this call, "
                + "call file_write again with relativePath \"taller-bench/viajes/itinerario.txt\""));
            Assert.That(next, Does.Not.Contain("\"taller-bench/itinerario.txt\""));
            Assert.That(cleared.Rule("file.write", Descriptor("file.write"), write), Is.Null);
        });
    }

    // Holdout v5 V5E034/V5E044: a count in a folder of theirs was refused with no call that could reach it.
    [Test]
    public void ACountLeavingOutTheFolderNamedIsRoutedIntoItsSubdirectory()
    {
        Directory.CreateDirectory(Path.Combine(_home, "Facturas Luz"));
        SaidFolders said = Heard("cuántos pdf hay en facturas luz");

        SaidFolders.Ruling? ruling = said.Rule("filesystem.explorer.count", Descriptor("filesystem.explorer.count"),
            new JsonObject { ["extension"] = ".pdf", ["folder"] = "home" });

        Assert.Multiple(() =>
        {
            Assert.That(ruling?.Refusal, Is.Null);
            Assert.That((string?)ruling?.Arguments["subdirectory"], Is.EqualTo("Facturas Luz"));
            Assert.That(ruling?.Note, Does.Contain("subdirectory \"Facturas Luz\""));
        });
    }

    // Holdout v5 V5E045/V5E047 (PC): a relative path with a space in a folder's name was cut at the space
    // («Documentos\Turnos Farmacia» became Documents\Turnos, which does not exist), and the model's right call was refused.
    [Test]
    public void ARelativePathSaidKeepsTheWordsOfAFolderWithSpacesInItsName()
    {
        string shifts = Path.Combine(_home, "Documents", "Turnos Farmacia");
        Directory.CreateDirectory(shifts);
        File.WriteAllText(Path.Combine(shifts, "horario.txt"), "lunes\n");
        SaidFolders said = Heard(@"reemplaza horario.txt en Documentos\Turnos Farmacia, por: martes");

        SaidFolders.Ruling? trash = said.Rule("filesystem.known.trash.named", Descriptor("filesystem.known.trash.named"),
            new JsonObject { ["fileName"] = "horario.txt", ["folder"] = "documents" });

        Assert.Multiple(() =>
        {
            Assert.That(said.Places().Select(static place => place.Path), Is.EqualTo(new[] { shifts }));
            Assert.That(said.Rule("file.write", Descriptor("file.write"), new JsonObject
            {
                ["relativePath"] = "Turnos Farmacia/horario.txt", ["text"] = "martes", ["folder"] = "documents",
            }), Is.Null);
            Assert.That((string?)trash?.Refusal?["next"], Does.Contain("subdirectory \"Turnos Farmacia\""));
        });
    }

    // The words after a relative path are its own only while they still name a folder that exists.
    [Test]
    public void ARelativePathSaidStopsWhereTheFolderItNamesEnds()
    {
        SaidFolders said = Heard(@"guarda en Documentos\obra nueva lista de materiales");

        Assert.That(said.Places().Select(static place => place.Path),
            Is.EqualTo(new[] { Path.Combine(_home, "Documents", "obra") }));
    }

    // Holdout v5 V5E044 (PC): «BAXY-bench/facturas» could start in the home folder or on the Desktop; only the home's
    // holds facturas, so it is the one place (the Desktop's, a path that does not exist, was a second one).
    [Test]
    public void ARelativePathThatExistsUnderOnlyOneOfItsStartsIsThatOne()
    {
        string sub = Path.Combine(_home, "banco-local", "facturas");
        Directory.CreateDirectory(sub);
        SaidFolders said = Heard("cuántos pdf hay en banco-local/facturas");

        Assert.That(said.Places().Select(static place => (place.Path, place.Sure)),
            Is.EqualTo(new[] { (sub, true) }));
    }

    // Holdout v5 V5E032: a move by name in a folder of theirs was refused with no call that could reach it, and the
    // model's destination repeated the folder («BAXY-bench/archivo-2025/…»).
    [Test]
    public void AMoveByNameInTheWorkFolderIsRefusedWithTheCallInTheFolderNamed()
    {
        string accounts = Path.Combine(_home, "contabilidad");
        Directory.CreateDirectory(Path.Combine(accounts, "archivo-2025"));
        File.WriteAllText(Path.Combine(accounts, "presupuesto.xlsx"), "x");
        SaidFolders said = Heard("mueve presupuesto.xlsx a archivo-2025 dentro de contabilidad");
        ProductOperationDescriptor move = Descriptor("filesystem.sandbox.move.named");

        SaidFolders.Ruling? sandbox = said.Rule("filesystem.sandbox.move.named", move, new JsonObject
        {
            ["sourceFileName"] = "presupuesto.xlsx",
            ["destinationRelativePath"] = "contabilidad/archivo-2025/presupuesto.xlsx",
        });

        string next = (string?)sandbox?.Refusal?["next"] ?? string.Empty;
        Assert.Multiple(() =>
        {
            Assert.That(next, Does.Contain("call filesystem_sandbox_move_named again with"));
            Assert.That(next, Does.Contain("destinationRelativePath \"archivo-2025/presupuesto.xlsx\""));
            Assert.That(next, Does.Contain("folder \"home\" and subdirectory \"contabilidad\""));
            Assert.That(said.Rule("filesystem.sandbox.move.named", move, new JsonObject
            {
                ["sourceFileName"] = "presupuesto.xlsx",
                ["destinationRelativePath"] = "archivo-2025/presupuesto.xlsx",
                ["folder"] = "home",
                ["subdirectory"] = "contabilidad",
            }), Is.Null);
        });
    }

    // Holdout v6 V6E034: told «destinationRelativePath … and subdirectory "BAXY-bench"» of a call that had folder "home",
    // the model wrote it without that folder; a place given by folder and subdirectory is said whole.
    [Test]
    public void AMoveRefusedInTheFolderNamedSaysItsFolderAndSubdirectoryTogether()
    {
        string bench = Path.Combine(_home, "banco-local");
        File.WriteAllText(Path.Combine(bench, "contrato.txt"), "x");
        SaidFolders said = Heard("en banco-local haz una copia de contrato.txt que se llame respaldo.txt");
        ProductOperationDescriptor move = Descriptor("filesystem.sandbox.move.named");

        string Next(JsonObject call) => (string?)said.Rule("filesystem.sandbox.move.named", move, call)?.Refusal?["next"]
            ?? string.Empty;

        Assert.Multiple(() =>
        {
            Assert.That(Next(new JsonObject
            {
                ["sourceFileName"] = "contrato.txt",
                ["destinationRelativePath"] = "banco-local/respaldo.txt",
                ["folder"] = "home",
            }), Does.Contain("again with destinationRelativePath \"respaldo.txt\" and folder \"home\" and subdirectory "
                + $"\"banco-local\" (it acts in {bench});"));
            Assert.That(Next(new JsonObject
            {
                ["sourceFileName"] = "contrato.txt",
                ["destinationRelativePath"] = "respaldo.txt",
                ["subdirectory"] = "banco-local",
            }), Does.Contain($"again with subdirectory \"banco-local\" and folder \"home\" (it acts in {bench});"));
        });
    }

    // Holdout v6 V6E034 (final_v5 s0): a filesystem_copy of BAXY's working folder, refused for the folder the person
    // named, was told only that it «cannot name a folder of theirs», and the answer was «No pude copiarlo: contrato.txt
    // está en BAXY-bench, que es una carpeta de la persona, no mi carpeta de trabajo». A call of the working folder whose
    // act another operation does in the person's folders is refused with that operation as a call, its arguments for
    // the folder named (aid «said_folder_counterpart»); with the aid off, as before.
    [TestCase("filesystem.copy", "all",
        "filesystem_copy cannot name a folder of theirs, and filesystem_sandbox_move_named does it there: call "
        + "filesystem_sandbox_move_named with destinationRelativePath \"respaldo.txt\" and folder \"home\" and subdirectory "
        + "\"archivador\" and copy true, and sourceFileName the file's own name. If the person asked")]
    [TestCase("filesystem.move", "all",
        "filesystem_move cannot name a folder of theirs, and filesystem_sandbox_move_named does it there: call "
        + "filesystem_sandbox_move_named with destinationRelativePath \"respaldo.txt\" and folder \"home\" and subdirectory "
        + "\"archivador\", and sourceFileName the file's own name. If the person asked")]
    [TestCase("filesystem.read.text", "all",
        "filesystem_read_text cannot name a folder of theirs, and file_read does it there: call file_read with folder "
        + "\"home\" and subdirectory \"archivador\", and fileName the file's own name. If the person asked")]
    [TestCase("filesystem.copy", "said_folder", "filesystem_copy cannot name a folder of theirs. If the person asked")]
    [TestCase("filesystem.read.text", "said_folder",
        "to look there, call file_find with folder \"home\" and subdirectory \"archivador\". If the person asked")]
    public void ACallOfTheWorkingFolderIsRefusedWithTheCallThatDoesItInTheFolderNamed(
        string operation, string aids, string told)
    {
        Directory.CreateDirectory(Path.Combine(_home, "archivador"));
        File.WriteAllText(Path.Combine(_home, "archivador", "contrato.txt"), "x");
        string? before = Environment.GetEnvironmentVariable("BAXY_AYUDAS");
        Environment.SetEnvironmentVariable("BAXY_AYUDAS", aids);
        try
        {
            SaidFolders said = Heard("en archivador haz una copia de contrato.txt que se llame respaldo.txt");
            var call = new JsonObject { ["resourceId"] = "fs_0123456789abcdef", ["expectedSha256"] = new string('a', 64) };
            if (operation != "filesystem.read.text")
                call["destinationRelativePath"] = "archivador/respaldo.txt";

            string next = (string?)said.Rule(operation, Descriptor(operation), call)?.Refusal?["next"] ?? string.Empty;

            Assert.That(next, Does.Contain(told));
        }
        finally
        {
            Environment.SetEnvironmentVariable("BAXY_AYUDAS", before);
        }
    }

    // Holdout v6 V6E043 (dictado, «en mis documentos dentro de la carpeta recetas abuela crea … sopaipillas punto
    // txt»): a folder recetas in the home folder was named too, and the call offered for Recetas Abuela kept the model's
    // recetas_abuela inside it; the model asked or wrote Recetas Abuela\recetas_abuela\sopaipillas.txt.
    // Revisión de final2: the same copy or move of the working folder written again runs as written; its note then said
    // the counterpart as a call to make, so the act already made in the working folder was followed by a second one in
    // the person's folder. After an act that ran, the note says only where it acted; a read still says its look there.
    [TestCase("filesystem.copy", false)]
    [TestCase("filesystem.move", false)]
    [TestCase("filesystem.read.text", true)]
    public void TheSameCallWrittenAgainIsNotToldTheCounterpartAsAnotherAct(string operation, bool told)
    {
        Directory.CreateDirectory(Path.Combine(_home, "archivador"));
        File.WriteAllText(Path.Combine(_home, "archivador", "contrato.txt"), "x");
        string? before = Environment.GetEnvironmentVariable("BAXY_AYUDAS");
        Environment.SetEnvironmentVariable("BAXY_AYUDAS", "all");
        try
        {
            SaidFolders said = Heard("en archivador haz una copia de contrato.txt que se llame respaldo.txt");
            var call = new JsonObject { ["resourceId"] = "fs_0123456789abcdef", ["expectedSha256"] = new string('a', 64) };
            if (operation != "filesystem.read.text")
                call["destinationRelativePath"] = "archivador/respaldo.txt";

            SaidFolders.Ruling? first = said.Rule(operation, Descriptor(operation), call);
            SaidFolders.Ruling? again = said.Rule(operation, Descriptor(operation), call);

            Assert.Multiple(() =>
            {
                Assert.That(first?.Refusal, Is.Not.Null);
                Assert.That(again?.Refusal, Is.Null);
                Assert.That(again?.Note, Does.Contain("outside it, as it was written"));
                Assert.That(again?.Note?.Contains("; filesystem_", StringComparison.Ordinal), Is.EqualTo(told));
            });
        }
        finally
        {
            Environment.SetEnvironmentVariable("BAXY_AYUDAS", before);
        }
    }

    [Test]
    public void ANameSaidAsPartOfALongerFolderNameIsThatFolderAndItsRespellingIsIt()
    {
        string recipes = Path.Combine(_home, "Documents", "Recetas Abuela");
        Directory.CreateDirectory(recipes);
        Directory.CreateDirectory(Path.Combine(_home, "recetas"));
        SaidFolders said = Heard("en mis documentos dentro de la carpeta recetas abuela crea un archivo sopaipillas punto "
            + "txt que diga harina zapallo y manteca");

        string next = (string?)said.Rule("file.write", Descriptor("file.write"), new JsonObject
        {
            ["relativePath"] = "recetas_abuela/sopaipillas.txt",
            ["text"] = "harina zapallo y manteca",
            ["folder"] = "documents",
        })?.Refusal?["next"] ?? string.Empty;

        Assert.Multiple(() =>
        {
            Assert.That(said.Places().Select(static place => place.Path), Is.EqualTo(new[] { recipes }));
            Assert.That(next, Does.Contain("call file_write again with relativePath \"Recetas Abuela/sopaipillas.txt\" (it acts in "
                + Path.Combine(recipes, "sopaipillas.txt") + ");"));
            // Counter-case: said alone, recetas is that folder.
            Assert.That(Heard("crea lista.txt en la carpeta recetas").Places().Select(static place => place.Path),
                Is.EqualTo(new[] { Path.Combine(_home, "recetas") }));
        });
    }

    // Holdout v6 V6E044 (dictado, «anota al final de gastos punto txt en baxi bench …»): the name came spelled by its
    // sounds and named no folder; the append went to the home folder.
    [TestCase("anota al final de gastos punto txt en baxi bench una linea nueva gas dieciocho mil")]
    [TestCase("anota al final de gastos punto txt en vaxy bench una linea nueva")]
    public void AFolderNameDictatedInAnotherSpellingOfItsSoundsIsThatFolder(string words)
    {
        string bench = Path.Combine(_home, "BAXY-bench");
        Directory.CreateDirectory(bench);
        File.WriteAllText(Path.Combine(bench, "gastos.txt"), "luz 32000\r\n");
        SaidFolders said = Heard(words);

        string next = (string?)said.Rule("file.write", Descriptor("file.write"), new JsonObject
        {
            ["relativePath"] = "gastos.txt", ["text"] = "gas 18000", ["folder"] = "home", ["append"] = true,
        })?.Refusal?["next"] ?? string.Empty;

        Assert.Multiple(() =>
        {
            Assert.That(said.Places().Select(static place => place.Path), Is.EqualTo(new[] { bench }));
            Assert.That(next, Does.Contain("call file_write again with relativePath \"BAXY-bench/gastos.txt\" (it acts in "
                + Path.Combine(bench, "gastos.txt") + ");"));
            // BAXY's own name, however it is spelled, is how the person speaks to it, never a folder (home has «baxy»).
            Assert.That(Heard("baxi, crea notas.txt").Places(), Is.Empty);
        });
    }

    // Revisión de nb-w11-arch: with two folders of one sound (Vaca and Baca), the one whose name the words spell is the
    // folder named, never also the other: a write in Baca for «la carpeta vaca» ran as inside the folder named.
    [Test]
    public void OfTwoFoldersOfOneSoundTheOneSpelledAsSaidIsTheFolderNamed()
    {
        string cow = Path.Combine(_home, "Vaca");
        string other = Path.Combine(_home, "Baca");
        Directory.CreateDirectory(cow);
        Directory.CreateDirectory(other);
        Directory.CreateDirectory(Path.Combine(_home, "cajon", "vino"));
        Directory.CreateDirectory(Path.Combine(_home, "cajon", "bino"));
        SaidFolders said = Heard("escribe notas.txt en la carpeta vaca que diga hola");

        SaidFolders.Ruling? ruling = said.Rule("file.write", Descriptor("file.write"), new JsonObject
        {
            ["relativePath"] = "Baca/notas.txt", ["text"] = "hola", ["folder"] = "home",
        });

        Assert.Multiple(() =>
        {
            Assert.That(said.Places().Select(static place => place.Path), Is.EqualTo(new[] { cow }));
            Assert.That(ruling?.Refusal, Is.Not.Null, "a write in the other folder of that sound ran unasked");
            // The same inside a folder, past a separator said as a word.
            Assert.That(Heard("cuantos pdf hay en cajon barra bino").Places().Select(static place => place.Path),
                Is.EqualTo(new[] { Path.Combine(_home, "cajon", "bino") }));
            Assert.That(Heard("cuantos pdf hay en cajon barra vino").Places().Select(static place => place.Path),
                Is.EqualTo(new[] { Path.Combine(_home, "cajon", "vino") }));
        });
    }

    // Holdout v5 V5E044 (dictado, «cuantos pdf hay en baxy bench barra facturas»): the separator said as a word left
    // the place at the outer folder, and the count looked only at its top level.
    [TestCase("barra")]
    [TestCase("slash")]
    [TestCase("diagonal")]
    public void ASeparatorSaidAsAWordLeadsIntoTheSubfolderItNames(string separator)
    {
        string bills = Path.Combine(_home, "cajon", "facturas");
        Directory.CreateDirectory(bills);
        SaidFolders said = Heard($"cuantos pdf hay en cajon {separator} facturas");

        Assert.That(said.Places().Select(static place => place.Path), Is.EqualTo(new[] { bills }));
    }

    // Holdout v5 V5E043: the person said «viaje chiloé 2027» and the folder was made as viaje_chiloe_2027; a name made
    // differs from theirs only in accents, separators or case, and it is offered as they said it.
    [Test]
    public void AFolderMadeWithTheNameSaidSpelledOtherwiseIsRefusedWithTheirSpelling()
    {
        SaidFolders said = Heard("en documentos crea una carpeta que se llame viaje chiloé 2027 y adentro un archivo");
        ProductOperationDescriptor create = Descriptor("filesystem.create.directory");
        var call = new JsonObject { ["relativePath"] = "viaje_chiloe_2027", ["folder"] = "documents" };

        SaidFolders.Ruling? ruling = said.Rule("filesystem.create.directory", create, call);
        SaidFolders.Ruling? again = said.Rule("filesystem.create.directory", create, call);

        Assert.Multiple(() =>
        {
            Assert.That((string?)ruling?.Refusal?["error"], Is.EqualTo(SaidFolders.NameChanged));
            Assert.That((string?)ruling?.Refusal?["next"], Does.Contain("relativePath \"viaje chiloé 2027\""));
            Assert.That(again?.Refusal, Is.Null);
            Assert.That(said.Rule("filesystem.create.directory", create,
                new JsonObject { ["relativePath"] = "Viaje Chiloé 2027", ["folder"] = "documents" }), Is.Null);
            Assert.That(said.Rule("filesystem.create.directory", create,
                new JsonObject { ["relativePath"] = "fotos", ["folder"] = "documents" }), Is.Null);
            // Only a name that folds to the same words: «viaje chiloe 2026» is another name, not theirs respelled.
            Assert.That(said.Rule("filesystem.create.directory", create,
                new JsonObject { ["relativePath"] = "viaje chiloe 2026", ["folder"] = "documents" }), Is.Null);
        });
    }

    // Counter-case: the person wrote the underscore themselves, so their spelling is the call's.
    [Test]
    public void AFolderMadeWithTheNameAsThePersonWroteItRuns()
    {
        SaidFolders said = Heard("crea en documentos la carpeta mis_notas_2027");

        Assert.That(said.Rule("filesystem.create.directory", Descriptor("filesystem.create.directory"),
            new JsonObject { ["relativePath"] = "mis_notas_2027", ["folder"] = "documents" }), Is.Null);
    }

    // Revisión de nb-w11-revision: the person's words with a character no folder name can hold («informe: tercer
    // trimestre») are no spelling to offer: the call that leaves it out is refused for nothing, and the one offered
    // fails (filesystem_path_invalid) before anything is made.
    [TestCase("crea en documentos la carpeta informe: tercer trimestre", "informe tercer trimestre")]
    [TestCase("crea en documentos la carpeta notas*viejas", "notas viejas")]
    public void ANameTheirWordsCannotSpellAsAFolderIsNotOffered(string words, string made)
    {
        SaidFolders said = Heard(words);

        Assert.That(said.Rule("filesystem.create.directory", Descriptor("filesystem.create.directory"),
            new JsonObject { ["relativePath"] = made, ["folder"] = "documents" })?.Refusal, Is.Null);
    }

    // Holdout v6 V6E065: a call into BAXY's working folder whose relativePath already began with the folder named was told
    // only folder "home", and the model wrote it again as relativePath "cotizaciones" (refused again, then «BAXY-bench es
    // mi carpeta de trabajo»). A path inside a folder is said with the folder it is inside. Holdout v8 V8E067 (final2 s1):
    // told both, the model still wrote relativePath "facturas2025"; the call is said with where it acts.
    [Test]
    public void AFolderChangedIsSaidWithThePathInsideItAndWhereItActs()
    {
        Directory.CreateDirectory(Path.Combine(_home, "taller-bench"));
        SaidFolders said = Heard("crea una carpeta que se llame cotizaciones en taller-bench");

        SaidFolders.Ruling? ruling = said.Rule("filesystem.create.directory", Descriptor("filesystem.create.directory"),
            new JsonObject { ["relativePath"] = "taller-bench/cotizaciones" });

        Assert.That((string?)ruling?.Refusal?["next"], Does.Contain(
            "call filesystem_create_directory again with relativePath \"taller-bench/cotizaciones\" and folder \"home\" "
            + $"(it acts in {Path.Combine(_home, "taller-bench", "cotizaciones")}); any other call of this turn in that "
            + "folder says it the same way: folder \"home\" with \"taller-bench\" at the start of relativePath;"));
    }

    // e2e final6c V6E044: told file_write's folder «as subdirectory, or at the start of relativePath or name», forms
    // file_write has not, the model answered without calling. The folder is said only in the forms of this call's
    // arguments: relativePath for file_write, subdirectory for file_edit.
    [Test]
    public void TheFolderIsSaidOnlyInTheFormsTheCallTakes()
    {
        string bench = Path.Combine(_home, "BAXY-bench");
        Directory.CreateDirectory(bench);
        SaidFolders said = Heard("anota en gastos.txt de BAXY-bench: gas 18000");

        string write = (string?)said.Rule("file.write", Descriptor("file.write"), new JsonObject
        {
            ["relativePath"] = "gastos.txt", ["text"] = "gas 18000", ["folder"] = "home", ["append"] = true,
        })?.Refusal?["next"] ?? string.Empty;
        string edit = (string?)Heard("anota en gastos.txt de BAXY-bench: gas 18000").Rule("file.edit",
            Descriptor("file.edit"), new JsonObject
            {
                ["fileName"] = "gastos.txt", ["folder"] = "home", ["oldText"] = "gas", ["newText"] = "gas 18000",
            })?.Refusal?["next"] ?? string.Empty;

        Assert.Multiple(() =>
        {
            Assert.That(write, Does.Contain("call file_write again with relativePath \"BAXY-bench/gastos.txt\" (it acts in "
                + Path.Combine(bench, "gastos.txt") + "); any other call of this turn in that folder says it the same way: "
                + "folder \"home\" with \"BAXY-bench\" at the start of relativePath;"));
            Assert.That(write, Does.Not.Contain("subdirectory"));
            Assert.That(edit, Does.Contain("any other call of this turn in that folder says it the same way: folder \"home\" "
                + "with \"BAXY-bench\" as subdirectory;"));
        });
    }

    // e2e final5 V6E048 (and V6E045, V6E047; 44 of the 93 repeated refusals in the saved runs): told file_edit with
    // subdirectory "Coro Parroquial", the model wrote it, read the file there, and then wrote file_edit and file_write
    // without that folder: three refusals in one turn, ~20 s. The first refusal says how every call of the turn in that
    // folder names it, in the form this call gives a place (subdirectory).
    [Test]
    public void TheFirstRefusalSaysHowEveryCallOfTheTurnNamesTheFolder()
    {
        string choir = Path.Combine(_home, "Documents", "Coro Taller");
        Directory.CreateDirectory(choir);
        File.WriteAllText(Path.Combine(choir, "repertorio.txt"), "uno\r\ndos\r\n");
        SaidFolders said = Heard("sobrescribe repertorio.txt de mi carpeta Coro Taller en Documentos con la palabra pendiente");

        string next = (string?)said.Rule("file.edit", Descriptor("file.edit"), new JsonObject
        {
            ["fileName"] = "repertorio.txt", ["folder"] = "documents", ["oldText"] = "uno", ["newText"] = "pendiente",
        })?.Refusal?["next"] ?? string.Empty;

        Assert.Multiple(() =>
        {
            Assert.That(next, Does.Contain($"call file_edit again with folder \"documents\" and subdirectory \"Coro Taller\" "
                + $"(it acts in {choir}); any other call of this turn in that folder says it the same way: folder "
                + "\"documents\" with \"Coro Taller\" as subdirectory;"));
            // As told, each form runs where the person said.
            Assert.That(said.Rule("file.write", Descriptor("file.write"), new JsonObject
            {
                ["relativePath"] = "Coro Taller/repertorio.txt", ["text"] = "pendiente", ["folder"] = "documents",
            }), Is.Null);
            Assert.That(said.Rule("file.edit", Descriptor("file.edit"), new JsonObject
            {
                ["fileName"] = "repertorio.txt", ["folder"] = "documents", ["subdirectory"] = "Coro Taller",
                ["oldText"] = "uno", ["newText"] = "pendiente",
            }), Is.Null);
        });
    }

    // Holdout v6 V6E058, V6E062 and V6E055: the folder of a request is left unsaid in the next one («uy, me equivoqué de
    // año, era fotos_2026»; «ábreme horario.txt que está ahí»; «que diga regar las orquídeas»), and the call acted in the
    // home folder: fotos_2026 beside BAXY-bench, «no encontré horario.txt», an edit refused after an 8 s walk of the home
    // folder. A turn whose words name no folder is ruled by the folders the person's previous request named: a call that
    // would act outside them is refused once with the call that names them; the same call again runs as written. A read
    // is not routed there (only the words of its own turn route a read), and a turn that names a folder is its own.
    [Test]
    public void ATurnThatNamesNoFolderKeepsTheFolderOfThePreviousRequest()
    {
        Directory.CreateDirectory(Path.Combine(_home, "taller-bench"));
        var said = new SaidFolders(Known);
        said.Heard("haz la carpeta fotos_2025 en taller-bench");
        said.Heard("uy, me equivoqué de año, era fotos_2026");
        var made = new JsonObject { ["relativePath"] = "fotos_2026", ["folder"] = "home" };
        var opened = new JsonObject { ["folder"] = "home", ["name"] = "horario.txt" };

        SaidFolders.Ruling? first = said.Rule("filesystem.create.directory", Descriptor("filesystem.create.directory"), made);
        SaidFolders.Ruling? again = said.Rule("filesystem.create.directory", Descriptor("filesystem.create.directory"), made);
        SaidFolders.Ruling? open = said.Rule("file.open", Descriptor("file.open"), opened);
        SaidFolders.Ruling? read = said.Rule("file.read", Descriptor("file.read"),
            new JsonObject { ["fileName"] = "horario.txt", ["folder"] = "home" });

        var named = new SaidFolders(Known);
        named.Heard("haz la carpeta fotos_2025 en taller-bench");
        named.Heard("ahora crea fotos_2026 en el escritorio");
        var cleared = new SaidFolders(Known);
        cleared.Heard("haz la carpeta fotos_2025 en taller-bench");
        cleared.Clear();
        cleared.Heard("uy, me equivoqué de año, era fotos_2026");

        Assert.Multiple(() =>
        {
            string next = (string?)first?.Refusal?["next"] ?? string.Empty;
            Assert.That(next, Does.StartWith("nothing ran: the person's previous request named «taller-bench»"));
            Assert.That(next, Does.Contain(
                "call filesystem_create_directory again with relativePath \"taller-bench/fotos_2026\""));
            Assert.That(again?.Refusal, Is.Null);
            Assert.That(again?.Note, Does.Contain("outside it, as it was written"));
            Assert.That((string?)open?.Refusal?["next"], Does.Contain("call file_open again with name \"taller-bench/horario.txt\""));
            Assert.That(read, Is.Null);
            Assert.That(named.Rule("filesystem.create.directory", Descriptor("filesystem.create.directory"),
                new JsonObject { ["relativePath"] = "fotos_2026", ["folder"] = "desktop" }), Is.Null);
            Assert.That(cleared.Rule("filesystem.create.directory", Descriptor("filesystem.create.directory"), made), Is.Null);
        });
    }

    // Revisión de nb-w11-multi: words that name a place that is no folder by its name (their home folder, BAXY's working
    // folder) are a place of their own: the previous request's folder does not rule them. A write in the home folder for
    // «en mi carpeta de usuario» was refused with the call that writes it in the previous request's folder.
    [TestCase("guarda recados.txt en mi carpeta de usuario que diga pan", "file.write", "home")]
    [TestCase("guarda recados.txt en tu carpeta de trabajo que diga pan", "filesystem.create.directory", null)]
    [TestCase("guarda recados.txt en la carpeta de baxy que diga pan", "filesystem.create.directory", null)]
    public void ATurnThatNamesAPlaceThatIsNoFolderByItsNameIsNotRuledByThePreviousRequest(
        string words, string operation, string? folder)
    {
        Directory.CreateDirectory(Path.Combine(_home, "taller-bench"));
        var said = new SaidFolders(Known);
        said.Heard("haz la carpeta fotos_2025 en taller-bench");
        said.Heard(words);
        var call = new JsonObject { ["relativePath"] = "recados.txt" };
        if (operation == "file.write")
            call["text"] = "pan";
        if (folder is not null)
            call["folder"] = folder;

        Assert.That(said.Rule(operation, Descriptor(operation), call)?.Refusal, Is.Null);
    }

    private SaidFolders Heard(string words)
    {
        var said = new SaidFolders(Known);
        said.Heard(words);
        return said;
    }

    private string? Known(string label) => label switch
    {
        "home" => _home,
        "desktop" => Path.Combine(_home, "Desktop"),
        "documents" => Path.Combine(_home, "Documents"),
        "downloads" => Path.Combine(_home, "Downloads"),
        "pictures" => Path.Combine(_home, "Pictures"),
        _ => null,
    };

    private static ProductOperationDescriptor Descriptor(string operation) =>
        ProductCatalog.TryGet(operation, out ProductOperationDescriptor? descriptor) && descriptor is not null
            ? descriptor
            : throw new AssertionException("no " + operation);
}
