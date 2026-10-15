using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Live y7 («en la calculadora calculá 9 por 9»): the part was reached on the Enter alone, without looking at the
/// result, while the display read 0. The calculation's check (semantic/missions.py) now joins each act that asks for the
/// result with «result:&lt;expression&gt;»: the value of the expression on the screen, or, when it cannot be evaluated,
/// a number the sub-goal's first look did not show.
/// </summary>
[TestFixture]
public sealed class ComputerUseResultTests
{
    private const string Check =
        "stepDone:input.key.press:enter&result:9 × 9|stepDone:input.visible.click:igual&result:9 × 9" +
        "|stepDone:input.visible.click:=&result:9 × 9|stepDone:input.text.type:=&result:9 × 9";

    // The Calculator's view as the adapter reads it: its display is a text control that says what it shows.
    private static JsonObject Calculator(string display, string expression = "9 × 9 =", string? firstLook = null)
    {
        var view = new JsonObject
        {
            ["window"] = new JsonObject { ["title"] = "Calculadora", ["process"] = "CalculatorApp", ["requested"] = true },
            ["controls"] = new JsonArray
            {
                new JsonObject { ["i"] = 0, ["kind"] = "Text", ["name"] = "La expresión es " + expression },
                new JsonObject { ["i"] = 1, ["kind"] = "Text", ["name"] = "La pantalla muestra " + display },
                new JsonObject { ["i"] = 2, ["kind"] = "Button", ["name"] = "Nueve" },
                new JsonObject { ["i"] = 3, ["kind"] = "Button", ["name"] = "Es igual a" },
            },
        };
        if (firstLook is not null)
            view["subgoalFirstText"] = firstLook;
        return view;
    }

    private static JsonArray Entered() =>
    [
        new JsonObject { ["step"] = 1, ["operation"] = "input.text.type", ["ok"] = true, ["text"] = "9*9", ["method"] = "keyboard" },
        new JsonObject { ["step"] = 2, ["operation"] = "input.key.press", ["ok"] = true, ["key"] = "enter", ["method"] = "keyboard" },
    ];

    [Test]
    public void TheEnterAloneNeverReachesACalculationWhoseDisplayStillReadsZero()
    {
        // y7 as measured: Enter verified, display «0».
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.EvaluateReceipts(Check, Entered(), out _), Is.False,
                "a calculation is never reached on receipts alone");
            Assert.That(ComputerUseSuccessCheck.Evaluate(Check, Calculator("0"), Entered(), out _), Is.False);
        });
    }

    [Test]
    public void TheValueOnTheDisplayReachesTheCalculation()
    {
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate(Check, Calculator("81"), Entered(), out string? by), Is.True);
            Assert.That(by, Is.EqualTo("stepDone:input.key.press:enter&result:9 × 9"));
        });
    }

    // Contracase: the right value with no act that asked for it (typed, never entered) is not the calculation done.
    [Test]
    public void TheValueWithoutTheActThatAsksForItIsNotDone()
    {
        JsonArray typedOnly = [Entered()[0]!.DeepClone()];
        Assert.That(ComputerUseSuccessCheck.Evaluate(Check, Calculator("81"), typedOnly, out _), Is.False);
    }

    // A wrong number on the display (the person's 18, a key that went astray) is no result.
    [Test]
    public void AnotherNumberOnTheDisplayIsNoResult() =>
        Assert.That(ComputerUseSuccessCheck.Atom("result:9 × 9", Calculator("18"), Entered()), Is.False);

    [TestCase("9 × 9", "81", true)]
    [TestCase("12x7", "84", true)]
    [TestCase("37*12", "444", true)]
    [TestCase("1250 × 4", "5.000", true)]
    [TestCase("1250 × 4", "5,000", true)]
    [TestCase("7 ÷ 2", "3,5", true)]
    [TestCase("7 ÷ 2", "3.5", true)]
    [TestCase("2,5 + 1.5", "4", true)]
    [TestCase("2 ^ 10", "1.024", true)]
    [TestCase("(2 + 3) × 4", "20", true)]
    [TestCase("10 - 15", "-5", true)]
    [TestCase("7 ÷ 2", "3", false)]
    [TestCase("2 + 3 × 4", "20", false)]
    [TestCase("1 ÷ 0", "0", false)]
    public void TheValueIsReadWithEitherDecimalMark(string expression, string display, bool holds) =>
        Assert.That(ComputerUseSuccessCheck.Atom("result:" + expression, Calculator(display, expression), []), Is.EqualTo(holds));

    [TestCase("9 × 9", 81d)]
    [TestCase("2 + 3 × 4", 14d)]
    [TestCase("2 ^ 3 ^ 2", 512d)]
    [TestCase("-3 + 5", 2d)]
    [TestCase("1.250,5 + 0,5", 1251d)]
    [TestCase("9 × 9 =", 81d)]
    public void AnExpressionIsEvaluatedAsAPersonWritesIt(string expression, double value) =>
        Assert.That(ComputerUseSuccessCheck.CalculationValue(expression), Is.EqualTo(value).Within(1e-9));

    // Revisión 3 of ronda 23: a number whose marks each group three digits is read as decimal and as thousands.
    [TestCase("10.000-1", new[] { 9d, 9999d })]
    [TestCase("1.500 + 500", new[] { 501.5d, 2000d })]
    [TestCase("1.000.000/1.000", new[] { 1d, 1000d, 1000000d })]
    [TestCase("1.5 + 0.5", new[] { 2d })]
    [TestCase("1.250,5 + 0,5", new[] { 1251d })]
    [TestCase("1250 × 4", new[] { 5000d })]
    [TestCase("raíz de 2", new double[0])]
    public void AThousandsMarkIsReadBothWays(string expression, double[] values) =>
        Assert.That(ComputerUseSuccessCheck.CalculationValues(expression), Is.EquivalentTo(values));

    [TestCase("raíz de 2")]
    [TestCase("9 × ")]
    [TestCase("1 ÷ 0")]
    [TestCase("(2 + 3")]
    [TestCase("5%")]
    public void WhatIsNotAnExpressionHasNoValue(string expression) =>
        Assert.That(ComputerUseSuccessCheck.CalculationValue(expression), Is.Null);

    // An expression that cannot be evaluated: the display has to show a number the first look did not show.
    [Test]
    public void AnExpressionThatCannotBeEvaluatedNeedsTheDisplayToChangeToAnotherNumber()
    {
        string first = ComputerUseSuccessCheck.LookText(Calculator("0", "raíz de 2"));
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Atom("result:raíz de 2", Calculator("1,4142135623", "raíz de 2", first), []), Is.True);
            Assert.That(ComputerUseSuccessCheck.Atom("result:raíz de 2", Calculator("0", "raíz de 2", first), []), Is.False,
                "the display did not change");
            Assert.That(ComputerUseSuccessCheck.Atom("result:raíz de 2", Calculator("1,4142135623", "raíz de 2"), []), Is.False,
                "with no first look nothing tells a new number");
        });
    }
}
