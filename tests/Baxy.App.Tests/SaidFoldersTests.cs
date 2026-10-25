using System.IO;
using System.Diagnostics;
using System.Reflection;
using System.Text.Json.Nodes;
using Baxy.App;
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
            Assert.That(next, Does.Contain("call file_write again with relativePath \"banco-local/apuntes.txt\";"));
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
            .And.Contain("file_find with folder \"home\" and subdirectory \"banco-local\" looks there"));
    }

    // E027 shape: a delete is never routed; it is refused with the call that names the folder.
    [Test]
    public void ADeleteThatLeavesOutTheFolderNamedIsRefused()
    {
        SaidFolders said = Heard("manda a la papelera viejo.txt de la carpeta banco-local");

        string next = (string?)said.Rule("filesystem.known.trash.named", Descriptor("filesystem.known.trash.named"),
            new JsonObject { ["fileName"] = "viejo.txt", ["folder"] = "all_known" })?.Refusal?["next"] ?? string.Empty;

        Assert.That(next, Does.Contain(
            "call filesystem_known_trash_named again with folder \"home\" and subdirectory \"banco-local\";"));
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
                ?.Refusal?["next"], Does.Contain("call file_write again with folder \"desktop\";"));
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
