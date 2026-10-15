using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Ronda 23 (live r21 v2-s01, «en la calculadora calculá 37*12»): the Enter evaluated nothing, the display read the
/// second operand typed («Se muestra 12») and the model's «done» citing it closed the sub-goal over the planned
/// «result:37*12», false on that very look. The model's «done» never contradicts an exact atom of the planned check
/// (result:, value:, count:, file:), and a citation whose numbers are only the operands typed is the typing.
/// </summary>
public sealed partial class ComputerUseLoopTests
{
    private const string S01Goal = "calcular 37*12";

    private static JsonObject S01View(string display = "12", string expression = "37 ×")
    {
        string json = ComputerUseRealViews.V2S01AfterEnter
            .Replace("\"La expresión es 37 ×\"", "\"La expresión es " + expression + "\"", StringComparison.Ordinal)
            .Replace("\"Se muestra 12\"", "\"Se muestra " + display + "\"", StringComparison.Ordinal);
        if (display != "12")
        {
            json = json.Replace("\"T\": [\"Historial\", \"37 x\", \"12\"]", "\"T\": [\"Historial\", \"" + display + "\"]", StringComparison.Ordinal);
        }

        return (JsonObject)JsonNode.Parse(json)!;
    }

    private static JsonArray S01Typed(bool enter = true, string typed = "37*12")
    {
        var steps = new JsonArray
        {
            new JsonObject { ["step"] = 2, ["operation"] = "input.text.type", ["ok"] = true, ["text"] = typed, ["method"] = "keyboard" },
        };
        if (enter)
        {
            steps.Add(new JsonObject { ["step"] = 3, ["operation"] = "input.key.press", ["ok"] = true, ["key"] = "enter", ["method"] = "keyboard" });
        }

        return steps;
    }

    // The real look of v2-s01 contradicts the planned check: in none of its four alternatives does «result:37*12» hold.
    // Contracase: the same look with the display at 444 does not, whatever step was taken (the stepDone atoms are not
    // read); a check with an alternative judged by names alone never contradicts a citation.
    [TestCase(ComputerUseRealViews.V2S01Check, "12", true)]
    [TestCase(ComputerUseRealViews.V2S01Check, "444", false)]
    [TestCase("stepDone:input.visible.click:igual&result:37*12", "444", false)]
    [TestCase("result:37*12|title:calculadora", "12", false)]
    [TestCase("title:calculadora", "12", false)]
    [TestCase("control:Es igual a", "12", false)]
    public void TheModelsDoneNeverContradictsAnExactAtomOfTheCheck(string check, string display, bool contradicts)
    {
        Assert.That(
            ComputerUseSuccessCheck.ExactCheckContradicts(check, S01View(display), S01Typed()),
            Is.EqualTo(contradicts));
    }

    // A display too narrow for the value shows it in exponent notation («1,219326311126353e+17» for 123456789*987654321,
    // «8,1e-12» for 0,0000009*0,000009): it is one number, the mantissa scaled, so the result shows and the done is not
    // contradicted. Contracase: another exponent is another value, and the exponent alone («17») is never read apart.
    [TestCase("stepDone:input.key.press:enter&result:123456789*987654321", "1,219326311126353e+17", false)]
    [TestCase("stepDone:input.key.press:enter&result:123456789*987654321", "1,219326311126353E17", false)]
    [TestCase("stepDone:input.key.press:enter&result:123456789*987654321", "1,219326311126353e+16", true)]
    [TestCase("result:0,0000009*0,000009", "8,1e-12", false)]
    [TestCase("result:0,0000009*0,000009", "8,1e-2", true)]
    [TestCase("result:17", "1,2e+17", true)]
    public void ANumberInExponentNotationIsOneNumber(string check, string display, bool contradicts)
    {
        Assert.That(
            ComputerUseSuccessCheck.ExactCheckContradicts(check, S01View(display), S01Typed()),
            Is.EqualTo(contradicts));
    }

    // Every exact kind counts, a value in a field among them; a named atom beside it in the same alternative is not read.
    [TestCase("value:Ancho=500&title:paint", "400", true)]
    [TestCase("value:Ancho=500&title:otra", "500", false)]
    [TestCase("count:Button>=3", "", false)]
    [TestCase("count:Button>=99", "", true)]
    public void ValueAndCountAreExactAtoms(string check, string width, bool contradicts)
    {
        var view = new JsonObject
        {
            ["window"] = new JsonObject { ["title"] = "Sin título - Paint", ["process"] = "mspaint", ["requested"] = true },
            ["controls"] = new JsonArray
            {
                new JsonObject { ["i"] = 0, ["kind"] = "Edit", ["name"] = "Ancho", ["value"] = width },
                new JsonObject { ["i"] = 1, ["kind"] = "Button", ["name"] = "Aceptar" },
                new JsonObject { ["i"] = 2, ["kind"] = "Button", ["name"] = "Cancelar" },
                new JsonObject { ["i"] = 3, ["kind"] = "Button", ["name"] = "Cerrar" },
            },
        };

        Assert.That(ComputerUseSuccessCheck.ExactCheckContradicts(check, view, []), Is.EqualTo(contradicts));
    }

    // Estabilización R16: the App's second judge of the done (EvidenceRefusal, with its operand rule CitesOnlyOperands
    // over ResultUnmet) is gone. On the real look of v2-s01 a citation of the operands typed («Se muestra 12» of
    // «37*12», «La expresión es 37 ×») was refused while the value did not show; the planned check the reader writes for
    // a calculation carries «result:» in every alternative (missions.read_clause), so the same done is refused by
    // ExactCheckContradicts, which the loop runs before (retry with «checkUnmet», then a stop: the test below). Each row
    // of the old judgement, on the same look: refused there ⇔ contradicted here; the value shown (also when it is an
    // operand: «5» of «10-5», «2» of «4/2») is never contradicted. The one row that changes is a check with an
    // alternative judged by names alone («|title:calculadora»), which never contradicts (already so in
    // TheModelsDoneNeverContradictsAnExactAtomOfTheCheck): no reader writes it for a calculation.
    [TestCase("result:37*12", "37*12", "12", "37 ×", true)]
    [TestCase("result:37*12|title:calculadora", "37*12", "12", "37 ×", false)]
    [TestCase("result:37*12", "37*12", "444", "37 × 12 =", false)]
    [TestCase("title:calculadora", "37*12", "12", "37 ×", false)]
    [TestCase("stepDone:input.visible.click:igual&result:10-5", "10-5", "5", "10 - 5 =", false)]
    [TestCase("result:4/2", "4/2", "2", "4 ÷ 2 =", false)]
    [TestCase("result:100/10", "100/10", "10", "100 ÷ 10 =", false)]
    [TestCase("result:9/3", "9/3", "3", "9 ÷ 3 =", false)]
    [TestCase("result:10-5", "10-5", "10", "10 -", true)]
    [TestCase("result:4/2", "4/2", "4", "4 ÷", true)]
    public void TheOperandsTypedOnTheDisplayContradictTheResultCheck(
        string check, string typed, string display, string expression, bool contradicts)
    {
        Assert.That(
            ComputerUseSuccessCheck.ExactCheckContradicts(check, S01View(display, expression), S01Typed(typed: typed)),
            Is.EqualTo(contradicts));
    }

    // Whether the value a «result:» atom asks for is missing from the view (the old ResultUnmet), now read by the one
    // check that remains. Contracase: shown, or no «result:» asked, or an alternative judged by names alone.
    [TestCase("result:37*12", "12", true)]
    [TestCase("result:37*12|title:calculadora", "12", false)]
    [TestCase("result:37*12", "444", false)]
    [TestCase("result:10-5", "5", false)]
    [TestCase("title:calculadora", "12", false)]
    [TestCase("", "12", false)]
    public void TheResultIsContradictedOnlyWhenItsValueDoesNotShow(string check, string display, bool unmet)
    {
        Assert.That(ComputerUseSuccessCheck.ExactCheckContradicts(check, S01View(display), S01Typed()), Is.EqualTo(unmet));
    }

    // v2-s01 through the loop: «37*12» typed, Enter pressed, the display at 12 and the model saying done citing it. The
    // done is refused, the model is asked again with the cause on the Enter («checkUnmet»), and the second such done
    // stops: the sub-goal never closes.
    [Test]
    public async Task ADoneOverAContradictedResultNeverClosesAndTheModelHearsWhy()
    {
        var harness = new Harness();
        harness.Screen = _ => harness.Acts.Count == 0 ? S01View("0", string.Empty) : S01View();
        harness.Mind = request => request.History.Count switch
        {
            0 => new MindComputerUseStep("input.text.type", new JsonObject { ["text"] = "37*12" }, "tecleo la cuenta", Source: "rule"),
            1 => new MindComputerUseStep("input.key.press", new JsonObject { ["key"] = "enter" }, "la evalúo", Source: "rule"),
            _ => Step("done", new JsonObject { ["evidence"] = "Se muestra 12" }),
        };
        var arguments = new JsonObject
        {
            ["goal"] = S01Goal,
            ["application"] = "Calculadora",
            ["successCheck"] = ComputerUseRealViews.V2S01Check,
        };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en la calculadora calculá 37*12", arguments), arguments, CancellationToken.None);
        JsonObject observed = Observed(result);

        Assert.Multiple(() =>
        {
            Assert.That((bool?)observed["reached"], Is.Not.True);
            Assert.That(result.Response!.Verified, Is.False);
            Assert.That(harness.Requests.Any(request => request.History.OfType<JsonObject>().Any(
                step => (string?)step["key"] == "enter" && (bool?)step["checkUnmet"] == true)), Is.True);
            Assert.That(harness.Requests.Count(request => request.History.Count >= 2), Is.GreaterThanOrEqualTo(2));
        });
    }

    // Contracase in the loop: the planned check asks for the «=» clicked, the model pressed Enter instead and the display
    // shows 444. The check's term is false (no such click) but its exact atom holds, so the model's done citing the value
    // closes as before (model_evidence). Revisión 2: also when the value is an operand typed («5» of «10-5», «2» of
    // «4/2», «10» of «100/10») and when the model cites the expression line beside the value shown.
    [TestCase("37*12", "444", "37 × 12 =", "Se muestra 444")]
    [TestCase("37*12", "444", "37 × 12 =", "La expresión es 37 × 12 =")]
    [TestCase("10-5", "5", "10 - 5 =", "Se muestra 5")]
    [TestCase("4/2", "2", "4 ÷ 2 =", "Se muestra 2")]
    [TestCase("100/10", "10", "100 ÷ 10 =", "Se muestra 10")]
    public async Task ADoneOverAResultThatShowsStillCloses(string typed, string display, string expression, string evidence)
    {
        var harness = new Harness();
        harness.Screen = _ => harness.Acts.Count == 0 ? S01View("0", string.Empty) : S01View(display, expression);
        harness.Mind = request => request.History.Count switch
        {
            0 => new MindComputerUseStep("input.text.type", new JsonObject { ["text"] = typed }, "tecleo la cuenta", Source: "rule"),
            1 => new MindComputerUseStep("input.key.press", new JsonObject { ["key"] = "enter" }, "la evalúo", Source: "rule"),
            _ => Step("done", new JsonObject { ["evidence"] = evidence }),
        };
        var arguments = new JsonObject
        {
            ["goal"] = "calcular " + typed,
            ["application"] = "Calculadora",
            ["successCheck"] = "stepDone:input.visible.click:igual&result:" + typed,
        };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en la calculadora calculá " + typed, arguments), arguments, CancellationToken.None);
        JsonObject observed = Observed(result);

        Assert.Multiple(() =>
        {
            Assert.That((bool?)observed["reached"], Is.True);
            Assert.That(harness.Requests.SelectMany(request => request.History.OfType<JsonObject>())
                .Any(step => step["checkUnmet"] is not null), Is.False);
        });
    }

    // The review's case through the loop: «123456789*987654321» typed, Enter pressed, the display in exponent notation
    // with the exact value and the model's done citing it. It closes at once (no «checkUnmet»).
    [Test]
    public async Task ADoneOverAResultInExponentNotationCloses()
    {
        const string goal = "calcular 123456789*987654321";
        var harness = new Harness();
        harness.Screen = _ => harness.Acts.Count == 0 ? S01View("0", string.Empty) : S01View("1,219326311126353e+17", "123456789 × 987654321 =");
        harness.Mind = request => request.History.Count switch
        {
            0 => new MindComputerUseStep("input.text.type", new JsonObject { ["text"] = "123456789*987654321" }, "tecleo la cuenta", Source: "rule"),
            1 => new MindComputerUseStep("input.key.press", new JsonObject { ["key"] = "enter" }, "la evalúo", Source: "rule"),
            _ => Step("done", new JsonObject { ["evidence"] = "Se muestra 1,219326311126353e+17" }),
        };
        var arguments = new JsonObject
        {
            ["goal"] = goal,
            ["application"] = "Calculadora",
            ["successCheck"] = "stepDone:input.key.press:enter&result:123456789*987654321",
        };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en la calculadora calculá 123456789*987654321", arguments), arguments, CancellationToken.None);
        JsonObject observed = Observed(result);

        Assert.Multiple(() =>
        {
            Assert.That((bool?)observed["reached"], Is.True);
            Assert.That(harness.Requests.SelectMany(request => request.History.OfType<JsonObject>())
                .Any(step => step["checkUnmet"] is not null), Is.False);
        });
    }

    // Revisión 3: a number written with a thousands mark («10.000», «1.500», as Spanish dictation writes them) is read
    // both ways, so the right value shows and the done is not contradicted. Contracase: a display where neither reading
    // shows (the operand typed, another number) still contradicts; a decimal read is still one («1.5 + 0.5» → 2).
    [TestCase("stepDone:input.key.press:enter&result:10.000-1", "9.999", false)]
    [TestCase("stepDone:input.key.press:enter&result:10.000-1", "9999", false)]
    [TestCase("stepDone:input.key.press:enter&result:1.500 + 500", "2.000", false)]
    [TestCase("stepDone:input.key.press:enter&result:1.000+1", "1.001", false)]
    [TestCase("stepDone:input.key.press:enter&result:1.000.000/1.000", "1.000", false)]
    [TestCase("stepDone:input.key.press:enter&result:10.000-1", "10.000", true)]
    [TestCase("stepDone:input.key.press:enter&result:10.000-1", "5", true)]
    [TestCase("stepDone:input.key.press:enter&result:1.500 + 500", "1.500", true)]
    [TestCase("stepDone:input.key.press:enter&result:1.5 + 0.5", "2", false)]
    [TestCase("stepDone:input.key.press:enter&result:1.5 + 0.5", "1.000", true)]
    public void ANumberWithAThousandsMarkIsReadBothWays(string check, string display, bool contradicts)
    {
        Assert.That(
            ComputerUseSuccessCheck.ExactCheckContradicts(check, S01View(display), S01Typed()),
            Is.EqualTo(contradicts));
    }

    // The review's case through the loop: «calculá 10.000-1» planned «result:10.000-1», the model types 10000-1 and
    // Enter, the display shows 9.999 and the model's done cites it. It closes at once (no «checkUnmet»).
    [TestCase("10.000-1", "10000-1", "9.999", "10.000 - 1 =")]
    [TestCase("1.500 + 500", "1500+500", "2.000", "1.500 + 500 =")]
    public async Task ADoneOverAResultWithAThousandsMarkCloses(string planned, string typed, string display, string expression)
    {
        var harness = new Harness();
        harness.Screen = _ => harness.Acts.Count == 0 ? S01View("0", string.Empty) : S01View(display, expression);
        harness.Mind = request => request.History.Count switch
        {
            0 => new MindComputerUseStep("input.text.type", new JsonObject { ["text"] = typed }, "tecleo la cuenta", Source: "rule"),
            1 => new MindComputerUseStep("input.key.press", new JsonObject { ["key"] = "enter" }, "la evalúo", Source: "rule"),
            _ => Step("done", new JsonObject { ["evidence"] = "Se muestra " + display }),
        };
        var arguments = new JsonObject
        {
            ["goal"] = "calcular " + planned,
            ["application"] = "Calculadora",
            ["successCheck"] = "stepDone:input.visible.click:igual&result:" + planned,
        };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en la calculadora calculá " + planned, arguments), arguments, CancellationToken.None);
        JsonObject observed = Observed(result);

        Assert.Multiple(() =>
        {
            Assert.That((bool?)observed["reached"], Is.True);
            Assert.That(harness.Requests.SelectMany(request => request.History.OfType<JsonObject>())
                .Any(step => step["checkUnmet"] is not null), Is.False);
        });
    }

    // The mind reads the cause only from the step the done was refused after.
    [Test]
    public void TheHistoryCarriesTheRefusedDonesCause()
    {
        JsonArray steps = S01Typed();
        ((JsonObject)steps[1]!)["checkUnmet"] = true;

        JsonArray history = ComputerUseMission.HistoryForMind(steps, 0);

        Assert.Multiple(() =>
        {
            Assert.That((bool?)history[1]!["checkUnmet"], Is.True);
            Assert.That(history[0]!["checkUnmet"], Is.Null);
        });
    }
}
