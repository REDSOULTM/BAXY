using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// M85: the shell's twins of the mind's fixes for the independent review of the official-window DEV-D run v3o
/// (development set). Every reply here is the one that run recorded.
/// </summary>
[TestFixture]
public sealed class M85AvisosRedaccionTests
{
    private const string CsvScriptRequest =
        "Hey Baxy, estoy haciendo un script en Python y necesito leer un CSV y sacar el promedio de la columna price, "
        + "can you write it?";

    // D-w20-t1 (t329): the mind wrote the script; the shell refused it as internal_code (mindReplyRejection) and the
    // composed fallback, the same code, died the same way (⚠ internal_code;retry_exhausted). M81 had taught only the
    // mind that a piece of code described first and asked for with a pronoun is code asked for.
    [Test]
    public void TheScriptAskedForWithAPronounIsNotInternalCode()
    {
        const string Reply =
            "```python\nimport csv\n\ndata = []\nwith open('file.csv', newline='') as f:\n    reader = csv.DictReader(f)\n"
            + "    for row in reader:\n        data.append(float(row['price']))\n\nprint(sum(data) / len(data))\n```";
        Assert.That(UserMessagePolicy.AsksForCode(CsvScriptRequest, null), Is.True);
        Assert.That(UserMessagePolicy.ConversationReplyRejectionReason(CsvScriptRequest, Reply, "mixed"), Is.Null);
        var draft = new UserMessageDraft("""{"kind":"conversation"}""", "conversation", null);
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(Reply, draft, CsvScriptRequest), Is.Null);
    }

    // D-p36-t2 (t246): the mind wrote the new lines of the dialogue asked for; Ash's «No puedo dejarlo ir» made the
    // shell refuse it as looks_like_failure, and the fallback published a narrative sentence.
    [Test]
    public void TheCharactersLinesAreNotBaxysFailure()
    {
        const string Request =
            "agrega a la conversación un fragmento donde se dan cuenta que el xenomorfo logro evadir la expulsion";
        const string Reply =
            "Ellen: \"Ash, mira la pantalla. El Xenomorfo ha evadido el sistema de expulsión. Está en la pasarela exterior.\"\n"
            + "Ash: \"Es una anomalía en el algoritmo de seguridad. Debería haber sido detectado y neutralizado antes de salir de la nave.\"\n"
            + "Ellen: \"Entonces, ¿qué vas a hacer? ¿Dejarlo ir?\"\n"
            + "Ash: \"No puedo dejarlo ir. Pero tampoco puedo actuar sin una orden.\"";
        Assert.That(UserMessagePolicy.ConversationReplyRejectionReason(Request, Reply, "es"), Is.Null);
        // A failure said by BAXY himself, outside any quote, is still one.
        Assert.That(
            UserMessagePolicy.ConversationReplyRejectionReason(Request, "No pude escribir el diálogo de \"Ash\".", "es"),
            Is.EqualTo("looks_like_failure"));
    }

    // D-p27-t1 (t216): the mind asked what the person likes; the shell refused it as looks_like_failure («can't») and
    // the fallback invented «the latest sci-fi flick about time travel».
    [Test]
    public void WhatBaxyCannotDoYetSaidToAskIsAQuestion()
    {
        const string Request = "Any good movies for me to watch?";
        const string Reply =
            "I don't know what you like, so I can't recommend anything specific. What kind of movies do you usually enjoy?";
        Assert.That(UserMessagePolicy.ConversationReplyRejectionReason(Request, Reply, "en"), Is.Null);
        Assert.That(
            UserMessagePolicy.ConversationReplyRejectionReason(Request, "I couldn't find a movie. What do you like?", "en"),
            Is.EqualTo("looks_like_failure"));
        // D-p26-t1's refused reply: an inability to act (BAXY does search the web) is still a failure told.
        Assert.That(
            UserMessagePolicy.ConversationReplyRejectionReason(
                Request, "I can't browse the internet to find current movies. What kind of movies do you usually enjoy?", "en"),
            Is.EqualTo("looks_like_failure"));
    }

    // D-p35-t1 (t242): «A la vez hazlo con la experiencia que tendría un experto en marketing» inside a request that names
    // the work (a FODA of Adidas) is no bare «hazlo»; the FODA the mind wrote was refused as ambiguous_without_question.
    [Test]
    public void HazloInsideARequestThatNamesTheWorkIsNotAmbiguous()
    {
        const string Request =
            "Has un análisis de FODA sobre la empresa Adidas. utiliza un tono casual. Un lenguaje coloquial y un tono "
            + "emocional, como el de un humano. A la vez hazlo con la experiencia que tendría un experto en marketing.";
        const string Reply =
            "Adidas tiene fortalezas enormes: una marca que todos reconocen y un diseño que siempre pega. Su debilidad es "
            + "depender mucho de pocos proveedores. Oportunidad: el running y lo sostenible. Amenaza: Nike y las marcas "
            + "baratas que aprietan por abajo.";
        Assert.That(UserMessagePolicy.ConversationReplyRejectionReason(Request, Reply, "es"), Is.Null);
        Assert.That(UserMessagePolicy.ConversationFallbackIntent("hazlo porfa"), Is.EqualTo("clarification"));
        Assert.That(UserMessagePolicy.ConversationFallbackIntent("ábreme eso"), Is.EqualTo("clarification"));
    }

    [TestCase("tengo un script que falla, ¿me lo puedes escribir de nuevo?", true)]
    [TestCase("necesito una función que ordene fechas, escríbela", true)]
    [TestCase("escríbelo en una nota", false)]
    [TestCase("write it down", false)]
    public void TheCodeRequestReaderMatchesTheMind(string userText, bool asked)
    {
        Assert.That(UserMessagePolicy.AsksForCode(userText, null), Is.EqualTo(asked));
    }
}
