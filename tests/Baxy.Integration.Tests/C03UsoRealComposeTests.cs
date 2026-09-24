using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Uso real 2026-09-23: the shell's twin of the mind's composition fixes. An
/// honest answer the mind publishes must not die in the shell, and the
/// dishonest shapes keep failing.
/// </summary>
[TestFixture]
public sealed class C03UsoRealComposeTests
{
    private const string NothingFound =
        """{"kind":"failure","polarity":"failure","cause":"mission_failed","stepCount":0,"steps":[],"reason":{"kind":"operation","operation":"media.status","polarity":"failure","verified":false,"succeeded":false,"error":"youtube_tab_not_found"}}""";

    [TestCase("No hay ningún video de YouTube sonando ahora mismo.")]
    [TestCase("No se está reproduciendo nada: no encuentro ningún video de YouTube abierto.")]
    [TestCase("Nothing is playing right now: there is no YouTube video open.")]
    public void TheAbsenceToldIsTheFailureTold(string reply)
    {
        var draft = new UserMessageDraft(NothingFound, "error", null);
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(reply, draft, "qué música se está reproduciendo"),
            Is.Null);
    }

    [Test]
    public void AnAbsenceCannotStandForAFailureThatIsNotOne()
    {
        var draft = new UserMessageDraft(TurnVisibleFacts.Failure("timeout"), "error", null);
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason("No hay música sonando.", draft, "qué suena"),
            Is.EqualTo("reversed_result"));
        var nothingFound = new UserMessageDraft(NothingFound, "error", null);
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason("Está sonando tu música en YouTube.", nothingFound, "qué suena"),
            Is.EqualTo("reversed_result"));
    }

    [Test]
    public void AVolumeClarificationForTheEnglishWordIsNotAnUnrequestedFamily()
    {
        Assert.That(UserMessagePolicy.ConversationReplyRejectionReason(
            "Volume más alto please",
            "¿Quieres que el volumen quede lo más alto posible o cuánto lo subo?",
            "mixed",
            clarification: true), Is.Null);
        Assert.That(UserMessagePolicy.ConversationReplyRejectionReason(
            "Volume más alto please", "¿Quieres que vacíe la papelera?", "mixed", clarification: true),
            Is.EqualTo("unsolicited_catalog"));
    }

    [Test]
    public void TheRegistrableSiteOfAResultHostIsObserved()
    {
        const string source =
            """{"kind":"operation","operation":"web.search","polarity":"success","verified":true,"succeeded":true,"observed":{"results":[{"title":"Lentejas estofadas","url":"https://recetasdecocina.elmundo.es/2026/01/lentejas.html","snippet":"Una receta tradicional."}]}}""";
        Assert.That(ObservedResponseLiterals.WithoutObservedNames("Según elmundo.es, es tradicional.", source),
            Is.EqualTo("Según ￼, es tradicional."));
        Assert.That(ObservedResponseLiterals.WithoutObservedNames("Según recetasdecocina.elmundo.es, es tradicional.", source),
            Is.EqualTo("Según ￼, es tradicional."));
        Assert.That(ObservedResponseLiterals.WithoutObservedNames("Según otrodiario.es, es tradicional.", source),
            Is.EqualTo("Según otrodiario.es, es tradicional."));
    }
}
