using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Auditoría semántica 2026-09-20 (REOPEN1993, grupo N): los titulares se leen del canal tal cual, cada uno con su
/// medio y su hora (web.search con source=news).
/// </summary>
[TestFixture]
public sealed class GoogleNewsFeedTests
{
    private const string Feed =
        """
        <?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0"><channel><title>Noticias destacadas - Google Noticias</title>
        <item><title>Bachelet se retira de la carrera por la ONU - BBC</title><link>https://news.google.com/rss/articles/a</link><pubDate>Sun, 20 Sep 2026 21:10:00 GMT</pubDate><source url="https://www.bbc.com">BBC</source></item>
        <item><title>Sube el dólar tras el anuncio - Emol</title><link>https://news.google.com/rss/articles/b</link><pubDate>Sun, 20 Sep 2026 20:00:00 GMT</pubDate><source url="https://www.emol.com">Emol</source></item>
        <item><title>Sin medio en el elemento</title><link>https://news.google.com/rss/articles/c</link><pubDate>Sun, 20 Sep 2026 19:00:00 GMT</pubDate></item>
        </channel></rss>
        """;

    [Test]
    public void HeadlinesAreReadWithTheirSourceAndTimeUpToTheLimit()
    {
        List<GoogleNewsFeed.Headline> parsed = GoogleNewsFeed.Parse(Feed, 2);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Has.Count.EqualTo(2));
            Assert.That(parsed[0].Title, Is.EqualTo("Bachelet se retira de la carrera por la ONU"));
            Assert.That(parsed[0].Source, Is.EqualTo("BBC"));
            Assert.That(parsed[0].PublishedAt, Is.EqualTo("Sun, 20 Sep 2026 21:10:00 GMT"));
            Assert.That(parsed[1].Source, Is.EqualTo("Emol"));
        });
    }

    [Test]
    public void ATitleWithoutASourceElementKeepsItsTrailingMediumAsSource()
    {
        List<GoogleNewsFeed.Headline> parsed = GoogleNewsFeed.Parse(
            Feed.Replace("Sin medio en el elemento", "Titular con cola - La Tercera", StringComparison.Ordinal), 10);

        Assert.Multiple(() =>
        {
            Assert.That(parsed[2].Title, Is.EqualTo("Titular con cola"));
            Assert.That(parsed[2].Source, Is.EqualTo("La Tercera"));
        });
    }

    [TestCase("https://news.google.com/rss/articles/CBMiabc", "CBMiabc")]
    [TestCase("https://news.google.com/articles/CBMiabc?hl=es-419", "CBMiabc")]
    [TestCase("https://news.google.com/rss/search?q=chile", null)]
    [TestCase("https://news.google.com/rss/articles/", null)]
    [TestCase("https://www.example.com/rss/articles/CBMiabc", null)]
    public void OnlyAGoogleNewsArticleLinkHasAnArticleId(string address, string? id) =>
        Assert.That(GoogleNewsFeed.ArticleId(new Uri(address)), Is.EqualTo(id));

    // The articles' addresses are asked in one request, each link's id with the signature and time its page carries, as
    // the page asks it (google-news-url-decoder's «garturlreq»), numbered by place; and read, by number, from Google
    // News' answer as it gave it on 2026-11-04 (its calls answered in any order).
    [Test]
    public async Task TheArticlesAreAskedWithTheirPagesSignaturesAndReadFromTheAnswerByNumber()
    {
        const string page = """<c-wiz><div jscontroller="aLI87" data-n-a-sg="AdwtSYOt_sg" data-n-a-ts="1793769327"></div></c-wiz>""";
        const string answer = ")]}'\n\n"
            +"""[["wrb.fr","Fbv4je","[\"garturlres\",\"https://www.dazn.com/es-MX/news/futbol/copas-argentina/1fwm\",1]",null,null,null,"3"],["wrb.fr","Fbv4je","[\"garturlres\",\"https://news.google.com/otra\",1]",null,null,null,"1"],["di",7],["af.httprm",6,"-89",12]]""";

        using FormUrlEncodedContent? ask = GoogleNewsFeed.ArticleAddressRequest(
            [("CBMiuno", page.Replace("AdwtSYOt_sg", "sg_uno", StringComparison.Ordinal)), ("CBMisin", "<html>sin firma</html>"),
                ("CBMitres", page)]);
        string body = Uri.UnescapeDataString((await ask!.ReadAsStringAsync()).Replace('+', ' '));
        Dictionary<int, Uri> addresses = GoogleNewsFeed.ArticleAddresses(answer);

        Assert.Multiple(() =>
        {
            Assert.That(body, Does.StartWith("f.req=[[[\"Fbv4je\",\"[\\\"garturlreq\\\","));
            Assert.That(body, Does.Contain("\\\"CBMiuno\\\",1793769327,\\\"sg_uno\\\"]\",null,\"1\"]"));
            Assert.That(body, Does.Contain("\\\"CBMitres\\\",1793769327,\\\"AdwtSYOt_sg\\\"]\",null,\"3\"]"));
            Assert.That(body, Does.Not.Contain("CBMisin"));
            Assert.That(GoogleNewsFeed.ArticleAddressRequest([("CBMisin", "<html>sin firma</html>")]), Is.Null);
            Assert.That(addresses.Keys, Is.EqualTo(new[] { 3 }), "an answer on Google News is no article");
            Assert.That(addresses[3].AbsoluteUri, Is.EqualTo("https://www.dazn.com/es-MX/news/futbol/copas-argentina/1fwm"));
            Assert.That(GoogleNewsFeed.ArticleAddresses(")]}'\n\nno es json"), Is.Empty);
        });
    }

    [Test]
    public void TheSearchAsksTheEditionOfTheLanguageChosen() =>
        Assert.Multiple(() =>
        {
            Assert.That(GoogleNewsFeed.SearchUri("tecnología", "es").AbsoluteUri,
                Is.EqualTo("https://news.google.com/rss/search?q=tecnolog%C3%ADa&hl=es-419&gl=CL&ceid=CL:es-419"));
            Assert.That(GoogleNewsFeed.SearchUri("chips", "en").AbsoluteUri,
                Is.EqualTo("https://news.google.com/rss/search?q=chips&hl=en-US&gl=US&ceid=US:en"));
        });
}
