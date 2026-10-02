using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// M120 (owner decisions D59, 2026-10-02), the shell's twin of the mind:
/// §6 the limit on being told when there is news offers to search them now, and
/// that offer is the ruling, not a proposal of the reply's own;
/// §7 a turn not understood is asked with the person's own words quoted, which
/// neither hands the request back nor leaves a question unanswered.
/// Every phrasing is our own.
/// </summary>
[TestFixture]
public sealed class M120D59PolicyTests
{
    [TestCase("avísame cuando haya noticias de bitcoin",
        "No estoy pendiente de las noticias ni aviso cuando salen. ¿Quieres que busque ahora las noticias de bitcoin?", "es")]
    [TestCase("dime cuando haya noticias del partido de Colo-Colo",
        "No vigilo las noticias. ¿Quieres que busque ahora las noticias del partido de Colo-Colo?", "es")]
    [TestCase("keep me posted on news about the Mars rover",
        "I don't follow the news to tell you later. Want me to search the news about the Mars rover now?", "en")]
    [TestCase("let me know when there's news about the Artemis launch",
        "I don't keep watch on the news or tell you when it comes out. Do you want me to search the news about the Artemis launch now?", "en")]
    public void TheNewsWatchLimitWithItsSearchOfferIsPublished(string request, string reply, string language)
    {
        Assert.That(
            UserMessagePolicy.ConversationReplyRejectionReason(request, reply, language, unsupportedByMind: true),
            Is.Null);
    }

    [Test]
    public void AnotherOfferAfterTheNewsLimitIsStillItsOwnProposal()
    {
        Assert.That(
            UserMessagePolicy.ConversationReplyRejectionReason(
                "avísame cuando haya noticias de bitcoin",
                "No vigilo las noticias. ¿Quieres que abra Steam?",
                "es",
                unsupportedByMind: true),
            Is.EqualTo("unsolicited_catalog"));
    }

    [TestCase("y si allá son las diez de la mañana acá cuántas horas faltan", "¿Qué quieres que haga con \"si allá son las diez…\"?", "es")]
    [TestCase("lo de la gallina azul", "¿Qué quieres que haga con \"lo de la gallina azul\"?", "es")]
    [TestCase("what about the purple one near the thing", "What should I do with \"what about the purple one…\"?", "en")]
    [TestCase("the purple one near the thing", "What should I do with \"the purple one near the thing\"?", "en")]
    public void AQuestionWithThePersonsOwnWordsIsAsked(string request, string question, string language)
    {
        Assert.That(UserMessagePolicy.AsksWithThePersonsWords(request, question), Is.True);
        Assert.That(
            UserMessagePolicy.ConversationReplyRejectionReason(request, question, language, clarification: true),
            Is.Null);
    }

    [TestCase("lo de la gallina azul", "¿Qué quieres que haga con \"la vaca roja\"?")]
    [TestCase("lo de la gallina azul", "¿Qué quieres que haga con la gallina azul?")]
    [TestCase("lo de la gallina azul", "Lo de \"la gallina azul\" no lo entendí.")]
    public void OnlyAQuestionQuotingTheirWordsIsThatQuestion(string request, string reply)
    {
        Assert.That(UserMessagePolicy.AsksWithThePersonsWords(request, reply), Is.False);
    }
}
