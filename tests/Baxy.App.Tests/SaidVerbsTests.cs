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

    private static string Currency(string amount, string rate) =>
        "{\"status\":\"completed\",\"verification\":\"output_only\",\"observed\":{\"version\":1,\"source\":\"currency\","
        + "\"results\":[{\"from\":\"CLP\",\"to\":\"COP\",\"amount\":" + amount + ",\"rate\":" + rate
        + ",\"date\":\"2026-11-03\",\"converted\":812500.00}],\"resultCount\":1,\"answeredBy\":\"Frankfurter\"}}";

    private static string? CalculatorNext(string words, string observation, string operation = "web.search")
    {
        var verbs = new SaidVerbs();
        verbs.Heard(words);
        return JsonNode.Parse(verbs.WithCalculatorNamed(operation, observation))!["observed"]?["next"]?.GetValue<string>();
    }

    // Encargo 61 (banco de uso R18, 6 of 6): «usa la calculadora para pasar…» went to the currency search, and the model
    // said the figure and never opened the Calculator. The result keeps the figure and says the call with the expression.
    [TestCase("Usa la calculadora para pasar 250 mil pesos chilenos a pesos colombianos con la tasa de hoy")]
    [TestCase("en la calcu pásame esos pesos")]
    [TestCase("Open the Windows calculator and convert it at today's rate")]
    public void ACurrencyResultSaysTheCallWhenTheirWordsNameTheCalculator(string words)
    {
        string? next = CalculatorNext(words, Currency("250000", "3.25"));

        Assert.That(next, Does.Contain("""calculator_expression_evaluate {"expression":"250000*3.25"}"""));
    }

    [TestCase("Pasa 250 mil pesos chilenos a pesos colombianos con la tasa de hoy")]
    [TestCase("¿a cuánto calculas que está el dólar?")]
    [TestCase("calcula cuánto son 250 mil pesos chilenos en colombianos")]
    public void ACurrencyResultStaysAsItIsWhenTheirWordsDoNotNameIt(string words) =>
        Assert.That(CalculatorNext(words, Currency("250000", "3.25")), Is.Null);

    // Encargo 61b: the Calculator is named by any name of the application the operation presses its keypad in, as the
    // names data hold it (app_aliases: its name and its abbreviations, whole words), not by a list of this aid's own.
    [TestCase("pásalo en la calc a pesos colombianos")]
    [TestCase("hazlo con la Calculadora de Windows")]
    [TestCase("abre la calc y pásame 1250.50 dólares a pesos mexicanos al cambio de hoy")]
    [TestCase("no sé a cuánto está el cambio hoy, así que hazlo en la calculadora: 18000 yenes a pesos argentinos")]
    public void TheCalculatorIsNamedByAnyNameOfItsApplication(string words) =>
        Assert.That(CalculatorNext(words, Currency("250000", "3.25")), Does.Contain("calculator_expression_evaluate"));

    // Encargo 61b («no uses la calculadora»: the result said «the person asked»): a name after a negation in its clause
    // is not asked for; the same name in another clause, or before the negation, is.
    [TestCase("no uses la calculadora, dime la tasa de hoy", false)]
    [TestCase("pasa esos pesos sin la calculadora", false)]
    [TestCase("pasa los pesos y nunca abras la calcu", false)]
    [TestCase("Don't use the calculator, just tell me the rate", false)]
    [TestCase("¿a cuánto está el euro en pesos colombianos hoy? sin usar la calculadora", false)]
    [TestCase("sin calculadora porfa cuanto es 12500 pesos argentinos en pesos chilenos hoy", false)]
    [TestCase("ni se te ocurra la calcu, dime a cuánto está el real brasileño hoy", false)]
    [TestCase("usa la calculadora, no el buscador", true)]
    [TestCase("no sé cuánto es; usa la calculadora para pasarlo", true)]
    public void ANegatedNameIsNotAsked(string words, bool asked) =>
        Assert.That(CalculatorNext(words, Currency("250000", "3.25")), asked ? Is.Not.Null : Is.Null);

    // What the Calculator can take: at most 6 decimals (the catalog's expression); a rate they round to nothing, or an
    // amount past its 12 digits, has no call to offer. Any other search or call stays as it is.
    [TestCase("1", "0.70774", "1*0.70774")]
    [TestCase("200000", "0.000241234", "200000*0.000241")]
    [TestCase("12.5", "940.25", "12.5*940.25")]
    public void TheExpressionIsOneTheCalculatorTakes(string amount, string rate, string expression) =>
        Assert.That(CalculatorNext("en la calculadora", Currency(amount, rate)), Does.Contain($"\"expression\":\"{expression}\""));

    [TestCase("1", "0.0000001")]
    [TestCase("1000000000000", "3.25")]
    public void AValueTheCalculatorCannotTakeHasNoCall(string amount, string rate) =>
        Assert.That(CalculatorNext("en la calculadora", Currency(amount, rate)), Is.Null);

    [Test]
    public void OtherResultsStayAsTheyAre()
    {
        string web = """{"status":"completed","observed":{"source":"web","results":[{"title":"t"}]}}""";
        var verbs = new SaidVerbs();
        verbs.Heard("en la calculadora");

        Assert.Multiple(() =>
        {
            Assert.That(verbs.WithCalculatorNamed("web.search", web), Is.EqualTo(web));
            Assert.That(verbs.WithCalculatorNamed("file.find", Currency("1", "2")), Is.EqualTo(Currency("1", "2")));
            Assert.That(verbs.WithCalculatorNamed("web.search", "no es json"), Is.EqualTo("no es json"));
        });
    }

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
            Assert.That((string?)ruled.Value.Arguments["path"], Is.EqualTo("documents/Liga de Futbolito/jugadores.txt"));
            Assert.That(ruled.Value.Note, Does.Contain("the person said to add to jugadores.txt: this call appended"));
        });
    }

    // Nothing changes when the words say to replace it and not overwrite it, say nothing of adding, the call already appends, the file
    // is not there (a new file), the text already holds the whole file (the model rewrote it with the new line), or no
    // words of the person's hold.
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
            call["path"] = "documents/Liga de Futbolito/nuevo.txt";

        Assert.That(Rule(words, call), Is.Null);
    }

    // e2e final6: «sobrescribe metas.txt de BAXY-bench con: …» and a file_write without hash, refused as a version
    // conflict (the model then asked the person itself). Before: it ran as written. Now it goes under the file's current
    // hash, which asks the person's «sí» on that first call, and its result says so.
    [Test]
    public void AWriteWithoutHashOverTheFileTheySaidToOverwriteGoesUnderItsHash()
    {
        string bench = Path.Combine(_root, "Documents", "BAXY-bench");
        Directory.CreateDirectory(bench);
        File.WriteAllText(Path.Combine(bench, "metas.txt"), "leer 10 páginas al día" + Environment.NewLine);
        string hash = Convert.ToHexStringLower(System.Security.Cryptography.SHA256.HashData(
            File.ReadAllBytes(Path.Combine(bench, "metas.txt"))));
        const string Words = "sobrescribe metas.txt de BAXY-bench con: correr 5 km los domingos";
        var call = new JsonObject
        {
            ["path"] = "documents/BAXY-bench/metas.txt", ["text"] = "correr 5 km los domingos",
        };

        (JsonObject Arguments, string Note)? ruled = Rule(Words, call);
        JsonObject With(string key, JsonNode value)
        {
            var given = (JsonObject)call.DeepClone();
            given[key] = value;
            return given;
        }

        Assert.That(ruled, Is.Not.Null);
        Assert.Multiple(() =>
        {
            Assert.That(ruled!.Value.Arguments.ToJsonString(), Is.EqualTo(new JsonObject
            {
                ["path"] = "documents/BAXY-bench/metas.txt", ["text"] = "correr 5 km los domingos",
                ["append"] = false, ["expectedSha256"] = hash,
            }.ToJsonString()));
            Assert.That(ruled.Value.Note, Does.Contain("the person said to overwrite metas.txt: this call replaces all"));
            Assert.That(Rule("escribe en metas.txt de BAXY-bench: correr 5 km los domingos", call), Is.Null);
            Assert.That(Rule(Words, With("expectedSha256", new string('a', 64))), Is.Null);
            Assert.That(Rule(Words, With("append", true)), Is.Null);
        });
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
                ["path"] = "documents/Liga de Futbolito/jugadores.txt", ["text"] = "pendiente",
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
    [TestCase("pon 53 en la calculadora y nada más", "53")]
    [TestCase("a lo que tiene la calculadora súmale 53", "47+53")]
    [TestCase("a lo que tiene la calculadora súmale 53", "-53")]
    [TestCase("a la calcu súmale 17 a lo que tiene", "17-17")]
    [TestCase("a la calcu súmale 17 a lo que tiene", "17+18")]
    [TestCase("a la calcu súmale 17 a lo que tiene", "53+53")]
    [TestCase("súmale 17 y luego réstale 3", "17+17")]
    // Uso real 04-11: an expression the model wrote whole runs as it is, whatever the words name: «N más N» went as «+N».
    [TestCase("en la calculadora 6 más 6", "6+6")]
    [TestCase("en la calculadora 3 menos 3", "3-3")]
    [TestCase("suma 5 y cinco en la calculadora", "5+5")]
    [TestCase("a la calcu súmale 17 a lo que tiene", "17+17")]
    // A number they did not say is the model's own: its answer to their sum, no operand.
    [TestCase("suma 4 y 4 en la calculadora", "8")]
    [TestCase("en la calculadora 4 más 4", "8")]
    [TestCase("", "17+17")]
    [TestCase("", "53")]
    public void OtherwiseTheExpressionRunsAsItIs(string words, string expression) =>
        Assert.That(Rule(words, "calculator.expression.evaluate", new JsonObject { ["expression"] = expression }),
            Is.Null);

    // Final7 e2e («copia X a Y»): the move ran without copy and the file left where it was. A call of an operation that
    // takes copy, without it, when the person said to copy, goes with copy, and its result says so.
    [TestCase("copia jugadores.txt de Liga de Futbolito a Respaldo")]
    [TestCase("cópiame jugadores.txt en la carpeta Respaldo")]
    [TestCase("haz una copia de jugadores.txt en Respaldo")]
    [TestCase("duplica jugadores.txt en Respaldo")]
    [TestCase("copy jugadores.txt to Respaldo")]
    public void AMoveTheyAskedAsACopyCopies(string words)
    {
        (JsonObject Arguments, string Note)? ruled = Rule(words, "filesystem.sandbox.move.named", Move(copy: null));

        Assert.That(ruled, Is.Not.Null);
        Assert.Multiple(() =>
        {
            Assert.That(ruled!.Value.Arguments["copy"]?.GetValue<bool>(), Is.True);
            Assert.That((string?)ruled.Value.Arguments["destinationRelativePath"], Is.EqualTo("Respaldo/jugadores.txt"));
            Assert.That(ruled.Value.Note, Does.Contain("copied the file with copy true and kept it where it was, "
                + "instead of moving it"));
        });
    }

    // Words of moving (a copy that is moved), a copy already, an operation that takes no copy, or no words: as written.
    [TestCase("mueve jugadores.txt a Respaldo", "filesystem.sandbox.move.named", null)]
    [TestCase("mueve la copia de jugadores.txt a Respaldo", "filesystem.sandbox.move.named", null)]
    [TestCase("copia jugadores.txt a Respaldo", "filesystem.sandbox.move.named", true)]
    [TestCase("copia jugadores.txt a Respaldo", "filesystem.move", null)]
    [TestCase("", "filesystem.sandbox.move.named", null)]
    public void OtherwiseTheMoveRunsAsItIs(string words, string operation, bool? copy) =>
        Assert.That(Rule(words, operation, Move(copy)), Is.Null);

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
                Assert.That(Rule("copia jugadores.txt a Respaldo", "filesystem.sandbox.move.named", Move(null)), Is.Null);
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

    private static JsonObject Move(bool? copy) => new()
    {
        ["sourceFileName"] = "jugadores.txt",
        ["destinationRelativePath"] = "Respaldo/jugadores.txt",
        ["path"] = "documents/Liga de Futbolito",
        ["copy"] = copy,
    };

    private static JsonObject Write(string text) => new()
    {
        ["path"] = "documents/Liga de Futbolito/jugadores.txt",
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
        ["path"] = subdirectory is null ? "documents/jugadores.txt" : $"documents/{subdirectory}/jugadores.txt",
        ["oldText"] = "Benja, delantero",
        ["newText"] = "pendiente",
    };
}
