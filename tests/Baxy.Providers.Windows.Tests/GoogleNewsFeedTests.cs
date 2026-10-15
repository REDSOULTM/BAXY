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
