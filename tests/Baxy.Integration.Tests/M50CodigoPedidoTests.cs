using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Goal v3 paso 5 (M50): the shell's twin of the mind's fixes for the independent review of v3a-final (the official
/// window run, development set). Every reply here is the one that run recorded: the mind wrote the code the person
/// asked for and the shell refused it as internal code, or the shell let a limit or a failure through with broken
/// person or with the person named in the third person.
/// </summary>
[TestFixture]
public sealed class M50CodigoPedidoTests
{
    private const string AverageFunction = "baxy hazme una función en python que saque la media de una lista de números";
    private const string ExpensesFunction =
        "Che, mirá, estoy armando un scriptcito en Python para ordenar los gastos del mes, ¿viste? ¿Me escribís una "
        + "función que reciba una lista de montos y me devuelva el total y el promedio?";

    // F-w07-t1 (t164), F-w07-t3 (t166), F-w12-t1 (t184), F-w12-t2 (t185), F-w12-t3 (t186): the mind's replies the
    // shell refused with internal_code (posterior mindReplyRejection). The code is what was asked.
    [TestCase(AverageFunction, "",
        "def calcular_media(lista):\n    if not lista:\n        return 0\n    return sum(lista) / len(lista)")]
    [TestCase("mola ahora pásamela a javascript", AverageFunction + " vale pero que ignore los negativos",
        "Aquí tienes la función en JavaScript que filtra los números no negativos y calcula su media:\n\n```javascript\n"
        + "function calcularMedia(lista) {\n  const positivos = lista.filter(num => num >= 0);\n  if (positivos.length === 0) "
        + "return 0;\n  return positivos.reduce((sum, num) => sum + num, 0) / positivos.length;\n}\n```")]
    [TestCase(ExpensesFunction, "",
        "Aquí tienes la función en Python que suma los montos y calcula el promedio:\n\n```python\ndef calcular_gastos(montos):\n"
        + "    total = sum(montos)\n    promedio = total / len(montos) if montos else 0\n    return total, promedio\n```")]
    [TestCase("Buenísimo. ¿Y me la pasás a JavaScript? Es para una paginita", ExpensesFunction,
        "Sí, aquí tienes la función en JavaScript: `function calcular(montos) { const total = montos.reduce((a, b) => a + b, "
        + "0); const promedio = total / montos.length; return { total, promedio }; }`.")]
    public void TheCodeAskedForIsNotInternalCode(string userText, string priorUserText, string reply)
    {
        Assert.That(
            UserMessagePolicy.ConversationReplyRejectionReason(userText, reply, "es", priorUserText),
            Is.Null);
        var draft = new UserMessageDraft("""{"kind":"conversation"}""", "conversation", null);
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(reply, draft, userText, priorUserText), Is.Null);
    }

    // Outside a code request, and outside the code itself, an internal identifier is still refused.
    [Test]
    public void AnInternalIdentifierOutsideRequestedCodeIsStillRefused()
    {
        Assert.That(
            UserMessagePolicy.ConversationReplyRejectionReason(
                "qué es una lista en python", "def calcular_media(lista):\n    return sum(lista) / len(lista)", "es"),
            Is.EqualTo("internal_code"));
        Assert.That(
            UserMessagePolicy.ConversationReplyRejectionReason(
                AverageFunction, "Uso task.list para eso:\n```python\ndef media(l):\n    return sum(l) / len(l)\n```", "es"),
            Is.EqualTo("internal_code"));
    }

    [Test]
    public void TheCodeRequestReaderMatchesTheMind()
    {
        Assert.That(UserMessagePolicy.AsksForCode(AverageFunction, null), Is.True);
        Assert.That(UserMessagePolicy.AsksForCode("baxy escribeme un query de sql q me saque los users activos", null), Is.True);
        Assert.That(UserMessagePolicy.AsksForCode("ahora q salgan ordenados por fecha", "baxy escribeme un query de sql"), Is.True);
        Assert.That(UserMessagePolicy.AsksForCode("qué es una función lineal", null), Is.False);
        Assert.That(UserMessagePolicy.AsksForCode("abre python", null), Is.False);
    }

    // F-s007 «Pon la función Smart Camera» and F-s077 «Vas a leer los cuatro primeros SMSs»: limits with a plural verb
    // after BAXY's «yo» and an invented first person.
    [TestCase("Pon la función Smart Camera", "Eso no lo hago: la función Smart Camera no la activan yo.")]
    [TestCase("Vas a leer los cuatro primeros SMSs", "No leeo SMS ni mensajes de texto.")]
    public void ABrokenFirstPersonIsNotPublished(string userText, string reply)
    {
        Assert.That(
            UserMessagePolicy.ConversationReplyRejectionReason(userText, reply, "es", unsupportedByMind: true),
            Is.EqualTo("broken_person_conjugation"));
        Assert.That(
            UserMessagePolicy.ConversationReplyRejectionReason(
                userText, "Eso no lo hago: la función Smart Camera no la activo yo.", "es", unsupportedByMind: true),
            Is.Null);
    }

    // F-s074 (t74) and F-s091 (t91): the failure told the person about «the person's» Outlook.
    [TestCase("Show the emails, actually, the audio messages.",
        "The attempt to retrieve emails and audio messages failed because Outlook is not configured on this PC, "
        + "preventing access to the person's Outlook calendar or mail.")]
    [TestCase("Anything I should do after work today",
        "The calendar operation failed because Outlook is not configured on this computer, preventing access to the "
        + "person's calendar or email.")]
    public void ThePersonIsSpokenToNotAbout(string userText, string reply)
    {
        const string Failure =
            """{"outcome":"failed","reason":{"outcome":"failed","cause":"Outlook is not set up on this PC, so I cannot reach your Outlook calendar or mail here","operation":"email.latest.read"}}""";
        var draft = new UserMessageDraft(Failure, "error", null);
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(reply, draft, userText),
            Is.EqualTo("third_person_addressee"));
    }
}
