using System.IO;
using System.Text.Json.Nodes;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// The person's verb picks the call (src/Baxy.App/SaidVerbs.cs). C3-final6b e2e: the 4B model does not follow a receipt
/// that tells it the other call. Holdout v6 V6E041 («agrégale al file jugadores.txt … la línea: Matías, arquero»): a
/// file.write without append over the file goes as an append. Holdout v5 V5E021 («a lo que tiene la calculadora súmale
/// 53»): calculator.expression.evaluate «53» goes as «+53».
/// </summary>
[TestFixture]
[NonParallelizable]
public sealed class SaidVerbsTests
{
    private const string Players = "Benja, delantero\r\nTomi, defensa\r\nFeña, volante\r\n";
    private string _root = string.Empty;

    [SetUp]
    public void SetUp()
    {
        _root = Path.Combine(Path.GetTempPath(), "baxy-said-verbs-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(Path.Combine(_root, "Documents", "Liga de Futbolito"));
        File.WriteAllText(Path.Combine(_root, "Documents", "Liga de Futbolito", "jugadores.txt"), Players);
    }

    [TearDown]
    public void TearDown() => Directory.Delete(_root, recursive: true);

    // V6E041 as the model called it (read, then a replacement under the hash, or no hash at all): it goes as an append,
    // and its result says so.
    [TestCase(true)]
    [TestCase(false)]
    public void AWriteOverTheFileTheyAskedToAddToAppends(bool hashed)
    {
        var call = Write("Matías, arquero");
        if (hashed)
            call["expectedSha256"] = new string('a', 64);

        (JsonObject Arguments, string Note)? ruled = Rule(
            "agrégale al file jugadores.txt de mi carpeta Liga de Futbolito en Documents la línea: Matías, arquero", call);

        Assert.That(ruled, Is.Not.Null);
        Assert.Multiple(() =>
        {
            Assert.That((bool?)ruled!.Value.Arguments["append"], Is.True);
            Assert.That((string?)ruled.Value.Arguments["text"], Is.EqualTo("Matías, arquero"));
            Assert.That((string?)ruled.Value.Arguments["relativePath"], Is.EqualTo("Liga de Futbolito/jugadores.txt"));
            Assert.That(ruled.Value.Note, Does.Contain("the person said to add to jugadores.txt: this call appended"));
        });
    }

    // Nothing changes when the words say to replace it (V6E048), say nothing of adding, the call already appends, the file
    // is not there (a new file), the text already holds the whole file (the model rewrote it with the new line), or no
    // words of the person's hold.
    [TestCase("sobrescribe jugadores.txt de mi carpeta Liga de Futbolito en Documentos con la palabra pendiente", "pendiente", false, true)]
    [TestCase("agrega la línea Matías, arquero y reemplaza todo lo demás", "Matías, arquero", false, true)]
    [TestCase("escribe en jugadores.txt Matías, arquero", "Matías, arquero", false, true)]
    [TestCase("agrégale a jugadores.txt la línea Matías, arquero", "Matías, arquero", true, true)]
    [TestCase("agrega un archivo jugadores.txt con Matías, arquero", "Matías, arquero", false, false)]
    [TestCase("agrégale a jugadores.txt la línea Matías, arquero", Players + "Matías, arquero", false, true)]
    [TestCase("", "Matías, arquero", false, true)]
    public void OtherwiseTheWriteRunsAsItIs(string words, string text, bool append, bool there)
    {
        JsonObject call = Write(text);
        if (append)
            call["append"] = true;
        if (!there)
            call["relativePath"] = "Liga de Futbolito/nuevo.txt";

        Assert.That(Rule(words, call), Is.Null);
    }

    // e2e final6c V6E048: «sobrescribe … con la palabra pendiente» and a file_edit of one line, which kept the rest. The
    // edit goes as the file.write of its newText over the whole file under its current hash (the person's «sí» first),
    // and its result says so.
    [Test]
    public void AnEditOfTheFileTheySaidToOverwriteReplacesItWhole()
    {
        string hash = Convert.ToHexStringLower(System.Security.Cryptography.SHA256.HashData(
            File.ReadAllBytes(Path.Combine(_root, "Documents", "Liga de Futbolito", "jugadores.txt"))));

        (JsonObject Arguments, string Note)? ruled = Rule(
            "sobrescribe jugadores.txt de mi carpeta Liga de Futbolito en Documentos con la palabra pendiente", "file.edit",
            Edit("Liga de Futbolito"));

        Assert.That(ruled, Is.Not.Null);
        Assert.Multiple(() =>
        {
            Assert.That(ruled!.Value.Arguments.ToJsonString(), Is.EqualTo(new JsonObject
            {
                ["relativePath"] = "Liga de Futbolito/jugadores.txt", ["folder"] = "documents", ["text"] = "pendiente",
                ["append"] = false, ["expectedSha256"] = hash,
            }.ToJsonString()));
            Assert.That(ruled.Value.Note, Does.Contain("the person said to overwrite jugadores.txt: this call is file_write"));
        });
    }

    // «Reemplaza X por Y» and other words are an edit; a file not there under that folder, or no words: it runs as it is.
    [TestCase("reemplaza Benja, delantero por pendiente en jugadores.txt de Liga de Futbolito", "Liga de Futbolito")]
    [TestCase("cambia Benja, delantero por pendiente en jugadores.txt", "Liga de Futbolito")]
    [TestCase("sobrescribe jugadores.txt con la palabra pendiente", null)]
    [TestCase("", "Liga de Futbolito")]
    public void OtherwiseTheEditRunsAsItIs(string words, string? subdirectory) =>
        Assert.That(Rule(words, "file.edit", Edit(subdirectory)), Is.Null);

    [TestCase("a lo que tiene la calculadora súmale 53", "53", "+53")]
    [TestCase("réstale 7 a lo que muestra", "7", "-7")]
    [TestCase("multiplícalo por 2,5", "2,5", "*2,5")]
    [TestCase("divídelo entre 4", "4", "/4")]
    [TestCase("add 53 to what the calculator shows", "53", "+53")]
    public void ABareNumberGoesAsTheOperationTheyNamed(string words, string number, string expression)
    {
        (JsonObject Arguments, string Note)? ruled = Rule(words, "calculator.expression.evaluate",
            new JsonObject { ["expression"] = number });

        Assert.That(ruled, Is.Not.Null);
        Assert.Multiple(() =>
        {
            Assert.That((string?)ruled!.Value.Arguments["expression"], Is.EqualTo(expression));
            Assert.That(ruled.Value.Note, Does.Contain($"this call pressed {expression}"));
        });
    }

    // Several operations named, none, an expression that is no bare number, or no words: it runs as written.
    [TestCase("súmale 53 y luego réstale 3", "53")]
    [TestCase("pon 53 en la calculadora", "53")]
    [TestCase("a lo que tiene la calculadora súmale 53", "47+53")]
    [TestCase("a lo que tiene la calculadora súmale 53", "-53")]
    [TestCase("", "53")]
    public void OtherwiseTheExpressionRunsAsItIs(string words, string expression) =>
        Assert.That(Rule(words, "calculator.expression.evaluate", new JsonObject { ["expression"] = expression }),
            Is.Null);

    [Test]
    public void WithTheAidsOffNothingChanges()
    {
        string? before = Environment.GetEnvironmentVariable("BAXY_AYUDAS");
        Environment.SetEnvironmentVariable("BAXY_AYUDAS", "said_folder");
        try
        {
            Assert.Multiple(() =>
            {
                Assert.That(Rule("agrégale a jugadores.txt la línea Matías, arquero", Write("Matías, arquero")), Is.Null);
                Assert.That(Rule("súmale 53", "calculator.expression.evaluate", new JsonObject { ["expression"] = "53" }),
                    Is.Null);
            });
        }
        finally
        {
            Environment.SetEnvironmentVariable("BAXY_AYUDAS", before);
        }
    }

    // The words of the turn that asked still hold when the person answers its «sí»; after Clear none do.
    [Test]
    public void AnAnswerKeepsTheTurnsWordsAndClearDropsThem()
    {
        var verbs = new SaidVerbs();
        var call = new JsonObject { ["expression"] = "53" };
        verbs.Heard("súmale 53");
        verbs.Answered("sí");
        (JsonObject, string)? answered = verbs.Rule("calculator.expression.evaluate", call, (_, _) => null);
        verbs.Clear();

        Assert.Multiple(() =>
        {
            Assert.That(answered, Is.Not.Null);
            Assert.That(verbs.Rule("calculator.expression.evaluate", call, (_, _) => null), Is.Null);
        });
    }

    private static JsonObject Write(string text) => new()
    {
        ["relativePath"] = "Liga de Futbolito/jugadores.txt",
        ["folder"] = "documents",
        ["text"] = text,
    };

    private (JsonObject Arguments, string Note)? Rule(string words, JsonObject call) => Rule(words, "file.write", call);

    // As the turn loop rules a call: the file it names through SaidFolders, with «documents» in the temporary folder.
    private (JsonObject Arguments, string Note)? Rule(string words, string operation, JsonObject call)
    {
        var folders = new SaidFolders(label => label == "documents" ? Path.Combine(_root, "Documents") : null);
        var verbs = new SaidVerbs();
        folders.Heard(words);
        verbs.Heard(words);
        return verbs.Rule(operation, call, (named, given) => folders.FileThere(named,
            ProductCatalog.TryGet(named, out ProductOperationDescriptor? found) && found is not null
                ? found : throw new AssertionException("no " + named), given));
    }

    private static JsonObject Edit(string? subdirectory) => new()
    {
        ["fileName"] = "jugadores.txt",
        ["folder"] = "documents",
        ["subdirectory"] = subdirectory,
        ["oldText"] = "Benja, delantero",
        ["newText"] = "pendiente",
    };
}
