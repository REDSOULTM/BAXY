using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Auditoría semántica 2026-09-20 (REOPEN1993, grupo N): los titulares se
/// leen del canal tal cual, cada uno con su medio; las ausencias tienen nombre.
/// </summary>
[TestFixture]
public sealed class GoogleNewsHeadlinesAdapterTests
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
    public async Task TodaysHeadlinesAreReadWithTheirSourceAndTime()
    {
        string? asked = null;
        var adapter = new GoogleNewsHeadlinesAdapter((url, _) => { asked = url; return Task.FromResult(Feed); });

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.news.headlines",
            JsonSerializer.SerializeToElement(new { limit = 2 }),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(asked, Is.EqualTo("https://news.google.com/rss?hl=es-419&gl=CL&ceid=CL:es-419"));
        });
        JsonElement result = receipt.Result!.Value;
        JsonElement headlines = result.GetProperty("headlines");
        Assert.Multiple(() =>
        {
            Assert.That(result.GetProperty("count").GetInt32(), Is.EqualTo(2));
            Assert.That(headlines.GetArrayLength(), Is.EqualTo(2));
            Assert.That(headlines[0].GetProperty("title").GetString(), Is.EqualTo("Bachelet se retira de la carrera por la ONU"));
            Assert.That(headlines[0].GetProperty("source").GetString(), Is.EqualTo("BBC"));
            Assert.That(headlines[0].GetProperty("publishedAt").GetString(), Is.EqualTo("Sun, 20 Sep 2026 21:10:00 GMT"));
            Assert.That(headlines[1].GetProperty("source").GetString(), Is.EqualTo("Emol"));
            Assert.That(result.GetProperty("authority").GetString(), Is.EqualTo("google_news_rss_es419_cl"));
            // NEWS2029: the redirect link is not part of the result (it blew the visible-facts cap).
            Assert.That(headlines[0].TryGetProperty("url", out _), Is.False);
            Assert.That(result.GetRawText().Length, Is.LessThan(2048));
        });
    }

    [Test]
    public async Task ATopicAsksTheSearchFeedAndTravelsInTheReceipt()
    {
        string? asked = null;
        var adapter = new GoogleNewsHeadlinesAdapter((url, _) => { asked = url; return Task.FromResult(Feed); });

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.news.headlines",
            JsonSerializer.SerializeToElement(new { topic = "tecnología" }),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(asked, Does.StartWith("https://news.google.com/rss/search?q=tecnolog%C3%ADa&"));
            Assert.That(receipt.Result!.Value.GetProperty("topic").GetString(), Is.EqualTo("tecnología"));
            Assert.That(receipt.Result!.Value.GetProperty("count").GetInt32(), Is.EqualTo(3));
        });
    }

    [Test]
    public void ATitleWithoutASourceElementKeepsItsTrailingMediumAsSource()
    {
        List<GoogleNewsHeadlinesAdapter.Headline> parsed = GoogleNewsHeadlinesAdapter.Parse(
            Feed.Replace("Sin medio en el elemento", "Titular con cola - La Tercera", StringComparison.Ordinal), 10);

        Assert.Multiple(() =>
        {
            Assert.That(parsed[2].Title, Is.EqualTo("Titular con cola"));
            Assert.That(parsed[2].Source, Is.EqualTo("La Tercera"));
        });
    }

    [Test]
    public async Task AnEmptyFeedAndAnUnreadableOneAreNamedBeforeAnyRead()
    {
        var empty = new GoogleNewsHeadlinesAdapter((_, _) => Task.FromResult("<rss><channel></channel></rss>"));
        var broken = new GoogleNewsHeadlinesAdapter((_, _) => Task.FromResult("<html>not a feed"));

        ExternalCapabilityReceipt emptyReceipt = await empty.InvokeAsync(
            "web.news.headlines", JsonSerializer.SerializeToElement(new { topic = "xyzzy" }), CancellationToken.None);
        ExternalCapabilityReceipt brokenReceipt = await broken.InvokeAsync(
            "web.news.headlines", JsonSerializer.SerializeToElement(new { }), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(emptyReceipt.ErrorCode, Is.EqualTo("news_topic_without_headlines"));
            Assert.That(emptyReceipt.EffectMayHaveOccurred, Is.False);
            Assert.That(brokenReceipt.ErrorCode, Is.EqualTo("news_feed_unreadable"));
        });
    }
}
