using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Uso real v3 ronda 19 (tandas r17, %LOCALAPPDATA%/BAXY/cu-v3/tandas_r17): las entidades se resolvían con el primer
/// resultado. t2-c01 T4 «cuantos discos de estudio tienen los bunkers?» respondió con el artículo de UN disco
/// («Los Bunkers (álbum)»); t1-c03 #4 «tráiler de Avatar» reprodujo el tráiler de otra obra (la serie «Avatar: Los
/// Siete Refugios»), el primer vídeo de la lista.
/// </summary>
[TestFixture]
public sealed class Ronda19LugaresYEntidadesTests
{
    private const string AlbumSnippet =
        "Los Bunkers es el álbum debut de la banda de rock chilena del mismo nombre. Producido por Mauricio Melo y "
        + "Carlos Cabezas, sería originalmente grabado y publicado de forma independiente en julio del 2000, siendo más "
        + "tarde reeditado y relanzado de forma oficial el 3 de abril de 2001 por el sello Big Sur Records";

    private const string SongSnippet =
        "«Ven aquí» es una canción de la banda chilena Los Bunkers compuesta por los hermanos Durán. Es la primera del "
        + "disco Vida de perros y primer sencillo del álbum. Es una de las canciones más populares de la banda.";

    // The search snippet carries the query's words («primer álbum de estudio … discos»): by its words the page is
    // about the question, and still it is the page of one record.
    private const string AlbumSearchSnippet =
        "Los Bunkers es el primer álbum de estudio de la banda chilena Los Bunkers, el primero de sus discos";

    [Test]
    public void ACountOfAnEntitysWorksIsNotAnsweredByThePageOfOneWork()
    {
        Assert.Multiple(() =>
        {
            Assert.That(
                SearchPertinence.Judge("cuantos discos de estudio tienen los bunkers", "Los Bunkers (álbum)", AlbumSearchSnippet),
                Is.EqualTo(SearchPertinence.Pertinence.NamesOnly));
            // The same words on the entity's own page are about it.
            Assert.That(
                SearchPertinence.Judge("cuantos discos de estudio tienen los bunkers", "Los Bunkers", AlbumSearchSnippet),
                Is.EqualTo(SearchPertinence.Pertinence.About));
        });
    }

    [Test]
    public void TheOwnPageOfTheEntityIsAskedByTheNameTheWorkPageCarries()
    {
        Assert.Multiple(() =>
        {
            Assert.That(SearchPertinence.WorkQualifiedEntity("Los Bunkers (álbum)"), Is.EqualTo("Los Bunkers"));
            Assert.That(SearchPertinence.WorkQualifiedEntity("Ven aquí (canción de Los Bunkers)"), Is.EqualTo("Ven aquí"));
            Assert.That(SearchPertinence.WorkQualifiedEntity("Mercurio (planeta)"), Is.Null);
            Assert.That(SearchPertinence.WorkQualifiedEntity("Los Bunkers"), Is.Null);
            Assert.That(SearchPertinence.AsksACount("cuantos discos de estudio tienen los bunkers"), Is.True);
            Assert.That(SearchPertinence.AsksACount("¿de qué álbum es Ven aquí?"), Is.False);
        });
    }

    // Contracases: a question that is not a count keeps the work's own page; a count that names the work's kind for
    // itself («el álbum») is about that work.
    [TestCase("¿de qué álbum es Ven aquí?", "Ven aquí (canción de Los Bunkers)", SongSnippet)]
    [TestCase("cuántas canciones tiene el álbum Los Bunkers", "Los Bunkers (álbum)",
        AlbumSnippet + ". Contiene once canciones.")]
    // Revisión r19: a count of what the work itself has (not of works of its kind) is asked of the work's own page.
    [TestCase("cuantos premios gano titanic", "Titanic (película de 1997)",
        "Titanic es una película estadounidense de 1997 dirigida por James Cameron. Ganó once premios Óscar.")]
    [TestCase("cuantas temporadas tiene dark", "Dark (serie de televisión)",
        "Dark es una serie de televisión alemana de suspenso creada por Baran bo Odar. Consta de tres temporadas.")]
    [TestCase("how many copies did thriller sell", "Thriller (album)",
        "Thriller is the sixth studio album by Michael Jackson. It has sold over 70 million copies worldwide.")]
    [TestCase("cuantas canciones tiene thriller", "Thriller (álbum)",
        "Thriller es el sexto álbum de estudio de Michael Jackson. Contiene nueve canciones.")]
    public void TheWorkPageStillAnswersWhatIsAskedOfTheWork(string query, string title, string snippet) =>
        Assert.That(SearchPertinence.Judge(query, title, snippet), Is.EqualTo(SearchPertinence.Pertinence.About));

    private const string BandSnippet =
        "Los Bunkers fue una banda chilena de rock formada en Concepción en 1999 por los hermanos Durán.";

    // Revisión r19: the entity's own page found by its name is taken for the count only when it describes the maker
    // the work's page names; a namesake that is something else is judged as any other result.
    [Test]
    public void TheOwnPageOfTheEntityIsTheOneThatDescribesTheMakerOfTheWork()
    {
        Assert.Multiple(() =>
        {
            Assert.That(SearchPertinence.OwnPageOfTheWork("Los Bunkers (álbum)", AlbumSnippet, "Los Bunkers", BandSnippet),
                Is.True);
            Assert.That(SearchPertinence.OwnPageOfTheWork("Los Bunkers (álbum)", AlbumSnippet, "Los Bunkers",
                "Los Bunkers es una localidad del condado de Tulsa, en Oklahoma, Estados Unidos."), Is.False);
            Assert.That(SearchPertinence.OwnPageOfTheWork("Los Bunkers (álbum)", AlbumSnippet, "Los Bunkers (película)",
                BandSnippet), Is.False);
        });
    }

    private static string Page(params (string Id, string Title)[] videos) =>
        "var ytInitialData = {\"contents\":[" + string.Join(",", videos.Select(video =>
            "{\"videoRenderer\":{\"videoId\":\"" + video.Id + "\",\"thumbnail\":{\"thumbnails\":[]},\"title\":{\"runs\":[{\"text\":\""
            + video.Title + "\"}]}}}")) + "]};";

    [Test]
    public void TheVideoChosenCarriesTheQueryWithoutTheSubtitleOfAnotherWork()
    {
        string html = Page(
            ("serie000001", "Tráiler Oficial Avatar: Los Siete Refugios | Nueva Serie Original | Paramount+"),
            ("agua0000002", "Avatar: El Sentido del Agua | Tráiler Oficial"),
            ("pelicula003", "AVATAR | Tráiler Oficial (2009)"));

        Assert.That(YouTubeSearch.Parse(html, "tráiler de Avatar").VideoId, Is.EqualTo("pelicula003"));
    }

    // Contracases: a query that names the subtitle keeps it; a first result that fits, or no better one, is the first.
    [Test]
    public void ASubtitleTheQueryNamesIsKeptAndAFittingFirstResultIsNeverPassedOver()
    {
        string aang = Page(
            ("otraobra001", "Avatar: El Sentido del Agua | Tráiler Oficial"),
            ("aang0000002", "Avatar: La Leyenda de Aang | Tráiler Oficial | Netflix"));
        string single = Page(("unico000001", "Never Gonna Give You Up"), ("otro0000002", "Never Gonna Give You Up (Live)"));
        string none = Page(("serie000001", "Avatar: Los Siete Refugios | Tráiler"));

        Assert.Multiple(() =>
        {
            Assert.That(YouTubeSearch.Parse(aang, "Avatar La Leyenda de Aang").VideoId, Is.EqualTo("aang0000002"));
            Assert.That(YouTubeSearch.Parse(single, "never gonna give you up").VideoId, Is.EqualTo("unico000001"));
            Assert.That(YouTubeSearch.Parse(none, "tráiler de Avatar").VideoId, Is.EqualTo("serie000001"));
            Assert.That(YouTubeSearch.Parse(aang).VideoId, Is.EqualTo("otraobra001"));
        });
    }

    // Revisión r19 contracase: a subtitle that describes what was asked («NPR Music Tiny Desk Concert» for «tiny desk»)
    // is not another work; the first result is kept over a reaction that repeats the query.
    [Test]
    public void ADescriptiveSubtitleThatCarriesTheQueryDoesNotPassOverTheFirstResult()
    {
        string html = Page(
            ("tinydesk001", "Tyler, The Creator: NPR Music Tiny Desk Concert"),
            ("reaccion002", "Tyler The Creator Tiny Desk REACTION"));

        Assert.That(YouTubeSearch.Parse(html, "tyler the creator tiny desk").VideoId, Is.EqualTo("tinydesk001"));
    }
}
