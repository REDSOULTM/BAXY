using System.Text.Json;
using Baxy.Kernel.Operations;
using Baxy.Kernel.Policy;
using NUnit.Framework;

namespace Baxy.Kernel.Tests;

/// <summary>
/// Encargo I8 (hallazgo de P1): «Pagar ahora» inside a long control name («Carrito con 3 artículos · Total 152,80 € ·
/// Pagar ahora · Envío gratis») was pressed without the person's yes, because the label words count only when the verb
/// opens a short label. The model reads the control and says what pressing it commits: a click or a key it declares
/// irreversible (pays, buys, deletes for good) asks, bound to that invocation, whatever its name says; the policy only
/// looks at the declared argument. The same name undeclared is judged as before, and Bypass asks nothing (decisión del
/// dueño 2026-11-02).
/// </summary>
[TestFixture]
public sealed class RiskPolicyDeclaredConsequenceTests
{
    // The words that pay or delete at the start, in the middle and at the end of a long name, as UIA gives it.
    [TestCase("Pagar ahora 49,90 € - Pedido de 3 artículos, entrega mañana")]
    [TestCase("Carrito con 3 artículos · Total 152,80 € · Pagar ahora · Envío estándar gratuito")]
    [TestCase("Total 58,40 € IVA incluido, 2 artículos, envío urgente · Pagar")]
    [TestCase("Order summary: 2 items, Confirm and pay $41.80, estimated delivery Tuesday")]
    [TestCase("Old backups folder (38 files, 4.6 GB) - Delete permanently - this cannot be undone")]
    public void AClickDeclaredIrreversibleAsksWhateverItsLongNameSays(string label) =>
        Assert.That(Click(new { label, consequence = "irreversible" }), Is.EqualTo(PolicyDecision.RequireConfirmation));

    [TestCase("Carrito con 3 artículos · Total 152,80 € · Pagar ahora · Envío estándar gratuito")]
    public void AResultChosenInASearchAndDeclaredIrreversibleAsks(string choose) =>
        Assert.That(
            Click(new { label = "Buscar", search = "pagar", choose, consequence = "irreversible" }),
            Is.EqualTo(PolicyDecision.RequireConfirmation));

    [Test]
    public void EnterDeclaredIrreversibleAsks() =>
        Assert.That(
            Evaluate("input.key.press", new { key = "enter", target = "text_field", consequence = "irreversible" }),
            Is.EqualTo(PolicyDecision.RequireConfirmation));

    // The same words on a harmless control, undeclared: a help link, a heading, a row of the history. The policy reads
    // nothing more into them than it did.
    [TestCase("Pagar ahora con tarjeta: cómo funciona - Centro de ayuda")]
    [TestCase("Pago realizado el 3 de marzo · 25,00 € · Pagar ahora no disponible")]
    [TestCase("Buy now, pay later: what it means and how it works")]
    public void TheSameWordsOnAHarmlessControlUndeclaredGoDirectly(string label) =>
        Assert.That(Click(new { label }), Is.EqualTo(PolicyDecision.Allow));

    // Decisión del dueño 2026-11-02: Bypass asks nothing, a declared payment included.
    [Test]
    public void BypassAsksNothingEvenDeclared() =>
        Assert.That(
            Click(new { label = "Pagar ahora", consequence = "irreversible" }, ConfirmationMode.Bypass),
            Is.EqualTo(PolicyDecision.Allow));

    // The catalog takes the declaration on both primitives, and only its own values.
    [TestCase("input.visible.click", """{"label":"Total 12 € · Pagar ahora","consequence":"irreversible"}""", true)]
    [TestCase("input.key.press", """{"key":"enter","consequence":"irreversible"}""", true)]
    [TestCase("input.visible.click", """{"label":"Pagar ahora","consequence":"pays"}""", false)]
    // Encargo I10 (revisión ciega): the policy asks on any declared string, so the catalog must reject before it every
    // spelling that is not its own (none reaches the policy to ask or not); null is no declaration.
    [TestCase("input.visible.click", """{"label":"Pagar ahora","consequence":"IRREVERSIBLE"}""", false)]
    [TestCase("input.visible.click", """{"label":"Pagar ahora","consequence":" irreversible"}""", false)]
    [TestCase("input.visible.click", """{"label":"Pagar ahora","consequence":""}""", false)]
    [TestCase("input.key.press", """{"key":"enter","consequence":1}""", false)]
    [TestCase("input.visible.click", """{"label":"Guardar","consequence":null}""", true)]
    public void TheCatalogTakesTheDeclaration(string operation, string json, bool valid)
    {
        using JsonDocument arguments = JsonDocument.Parse(json);
        Assert.That(
            OperationArgumentValidator.IsValid(arguments.RootElement, ProductCatalog.GetRequired(operation).ArgumentsSchema),
            Is.EqualTo(valid));
    }

    // Encargo I10 (revisión ciega): a press whose landing was read at a lower risk (landingRead) lifts only the
    // undeclared-landing rule, never a declared irreversible, as KeyPressLandingTests pins it for an overwrite.
    [TestCase("input.key.press", """{"key":"enter","consequence":"irreversible"}""")]
    [TestCase("input.visible.click", """{"label":"Total 12 € · Pagar ahora","consequence":"irreversible"}""")]
    public void ALoweredPressStillAsksForADeclaredIrreversible(string operation, string json)
    {
        using JsonDocument arguments = JsonDocument.Parse(json);
        Assert.That(
            RiskPolicy.Evaluate(OperationRisk.Reversible, ConfirmationMode.Normal, operation, arguments.RootElement,
                landingRead: true),
            Is.EqualTo(PolicyDecision.RequireConfirmation));
    }

    private static PolicyDecision Click(object arguments, ConfirmationMode mode = ConfirmationMode.Normal) =>
        Evaluate("input.visible.click", arguments, mode);

    private static PolicyDecision Evaluate(string operation, object arguments, ConfirmationMode mode = ConfirmationMode.Normal)
    {
        using JsonDocument document = JsonDocument.Parse(JsonSerializer.Serialize(arguments));
        return RiskPolicy.Evaluate(
            ProductCatalog.ToPolicyRisk(ProductCatalog.GetRequired(operation).Risk), mode, operation, document.RootElement);
    }
}
