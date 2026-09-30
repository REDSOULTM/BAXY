using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// M83 (DEV-D v3o D-s111 «¿Cuál es la distancia de Barcelona a París?», D-p24-t1 a fantasy film with Elijah Wood):
/// the pages read did not state what was asked, and D35 (owner) has BAXY answer from memory with a short notice
/// instead of stopping at «no lo encontré». Over a verified search that notice is the scope of the read, like the
/// not-found; any other failure of BAXY's own still reverses the verified search.
/// </summary>
[TestFixture]
public sealed class M83MemoriaTrasNoEncontradoTests
{
    private const string VerifiedSearch =
        """{"kind":"operation","operation":"web.search","polarity":"success","verified":true,"succeeded":true,"observed":{"query":"¿Cuál es la distancia de Barcelona a París?","results":[{"title":"Partido de Liga de Campeones de la UEFA entre F. C. Barcelona y París Saint-Germain","url":"https://es.wikipedia.org/wiki/Partido","snippet":"El partido de fútbol fue celebrado el 8 de marzo de 2017 en el Camp Nou de Barcelona."}]}}""";

    [TestCase("No pude comprobarlo; de memoria, puede no ser exacto: son unos 1.000 km por carretera.",
        "¿Cuál es la distancia de Barcelona a París?")]
    [TestCase("I couldn't check this; from memory, it may not be exact: The Lord of the Rings (2001) is a fantasy film starring Elijah Wood.",
        "search for a nice fantasy movie like Elijah Wood")]
    public void AnAnswerFromMemoryWithItsNoticeIsTheScopeOfTheRead(string reply, string request)
    {
        var draft = new UserMessageDraft(VerifiedSearch, "status", null);
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(reply, draft, request), Is.Null);
    }

    [TestCase("No pude comprobarlo.")]
    [TestCase("No pude hacer la búsqueda; de memoria no sé.")]
    [TestCase("I couldn't check it, the search failed.")]
    public void ANoticeWithoutTheAnswerFromMemoryIsStillAFailure(string reply)
    {
        var draft = new UserMessageDraft(VerifiedSearch, "status", null);
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(reply, draft, "¿Cuál es la distancia de Barcelona a París?"),
            Is.EqualTo("reversed_result"));
    }
}
