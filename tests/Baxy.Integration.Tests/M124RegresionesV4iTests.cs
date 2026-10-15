using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// M124 (round v4i, owner's script t59 «pues investigala dime si tiene buena o malas reseñas»): the mind published
/// «… levelup.com también la llama una de las mejores adaptaciones de videojuegos.», naming the publisher a Google News
/// result carries in its snippet. The mind exempts identifiers written inside observed values (A7 E4,
/// llm._observed_identifier_tokens); the App's twin did not, refused it as internal_code and the turn ended in ⚠.
/// </summary>
[TestFixture]
public sealed class M124RegresionesV4iTests
{
    private const string Search =
        """{"kind":"operation","operation":"web.search","polarity":"success","verified":true,"succeeded":true,"observed":{"version":1,"query":"las reseñas de la nueva película de Resident Evil","count":2,"results":[{"title":"¿Resident Evil: Noche Cero es buena? La película recibe reseñas positivas","url":"https://news.google.com/rss/articles/CBMiiwJBVV95","snippet":"levelup.com, Wed, 16 Sep 2026 07:00:00 GMT"},{"title":"La nueva 'Resident Evil' es una salvajada divertidísima","url":"https://news.google.com/rss/articles/CBMiywFBVV95","snippet":"Espinof, Wed, 16 Sep 2026 07:00:00 GMT"}],"authority":"google_news_rss"}}""";

    private const string Reply =
        "El diario Espinof dice que la nueva película de Resident Evil es una salvajada divertidísima. "
        + "levelup.com también la llama una de las mejores adaptaciones de videojuegos.";

    [Test]
    public async Task APublisherTheResultObservedIsNotInternalCode()
    {
        var draft = new UserMessageDraft(Search, "status", null);
        const string request = "pues investigala dime si tiene buena o malas reseñas";
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(Reply, draft, request, "La nueva peli de resident evil es buena?"),
            Is.Null);
        ModelMessageCompositionOutcome result = await ModelMessageComposer.ComposeAsync(
            draft, request, ModelMessageComposer.CreateFacts(draft),
            (_, _, _, _, _) => Task.FromResult<MindComposedMessage?>(new(Reply)),
            cpuFallback: false, allowRecovery: false, CancellationToken.None);
        Assert.That(result.Text, Is.EqualTo(Reply));
    }

    [TestCase("Según levelup.com y web.search, la película gusta.")]
    [TestCase("Según rottentomatoes.com, la película gusta.")]
    public void ADottedTokenNobodyObservedIsStillRefused(string reply)
    {
        var draft = new UserMessageDraft(Search, "status", null);
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(reply, draft, "investígala", null),
            Is.EqualTo("internal_code"));
    }

    [Test]
    public void OnlyTheObservedValuesExempt()
    {
        // The operation that read them and its authority are what the result says about itself.
        Assert.That(ObservedResponseLiterals.WithoutObservedIdentifiers("vía web.search y google_news_rss", Search),
            Is.EqualTo("vía web.search y google_news_rss"));
        Assert.That(ObservedResponseLiterals.WithoutObservedIdentifiers("Lo dice levelup.com.", Search),
            Is.EqualTo("Lo dice ."));
        Assert.That(ObservedResponseLiterals.WithoutObservedIdentifiers("Lo dice levelup.com.", "no es json"),
            Is.EqualTo("Lo dice levelup.com."));
    }
}
