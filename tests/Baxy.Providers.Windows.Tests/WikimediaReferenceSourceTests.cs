using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

// M53 (paso 6, D35): las respuestas reales de MediaWiki (capturadas el 2026-09-28 con el
// User-Agent de D32, en Fixtures/Wikimedia) leídas como las lee el proveedor.
[TestFixture]
public sealed class WikimediaReferenceSourceTests
{
    internal static string Fixture(string name) =>
        File.ReadAllText(Path.Combine(TestContext.CurrentContext.TestDirectory, "Fixtures", "Wikimedia", name));

    [Test]
    public void TheMindsQueryNamesTheKindAndTheReferent()
    {
        Assert.Multiple(() =>
        {
            WikimediaReferenceSource.ReferenceAsk? recipe = WikimediaReferenceSource.Parse("receta pastel de choclo");
            Assert.That(recipe?.Kind, Is.EqualTo(WikimediaReferenceSource.ReferenceKind.Recipe));
            Assert.That(recipe?.Subject, Is.EqualTo(new[] { "pastel", "choclo" }));
            Assert.That(WikimediaReferenceSource.Parse("ingredientes pan de banana")?.Named,
                Is.EqualTo(new[] { "pan", "banana" }));
            Assert.That(WikimediaReferenceSource.Parse("recipe chicken alfredo")?.Named,
                Is.EqualTo(new[] { "chicken", "alfredo" }));
            WikimediaReferenceSource.ReferenceAsk? plot = WikimediaReferenceSource.Parse("resumen libro Hobbit");
            Assert.That(plot?.Kind, Is.EqualTo(WikimediaReferenceSource.ReferenceKind.Plot));
            // The work's class helps the search; the title does not carry it.
            Assert.That(plot?.Subject, Is.EqualTo(new[] { "libro", "hobbit" }));
            Assert.That(plot?.Named, Is.EqualTo(new[] { "hobbit" }));
            Assert.That(WikimediaReferenceSource.Parse("summary of the movie Inception")?.Named,
                Is.EqualTo(new[] { "inception" }));
            // The class word the mind wrote is in the person's language: that project first.
            Assert.That(WikimediaReferenceSource.CueLanguages("recipe chicken alfredo", ["es", "en"]),
                Is.EqualTo(new[] { "en", "es" }));
            Assert.That(WikimediaReferenceSource.CueLanguages("resumen libro hobbit", ["en", "es"]),
                Is.EqualTo(new[] { "es", "en" }));
            // Nothing of its class, or nothing named: not a reference ask.
            Assert.That(WikimediaReferenceSource.Parse("capital de Australia"), Is.Null);
            Assert.That(WikimediaReferenceSource.Parse("receta"), Is.Null);
            Assert.That(WikimediaReferenceSource.Parse("resumen del libro"), Is.Null);
        });
    }

    // es.wikibooks «Artes culinarias/Recetas/Pastel de choclo»: the template's ingredients
    // and steps, and the page's own description (sweet or savoury with «pino»), whose
    // photo is the Peruvian sweet variant the template writes.
    [Test]
    public void ASpanishRecipeIsReadFromItsTemplateWithItsDescription()
    {
        WikimediaReferenceSource.ReferenceReading? reading = WikimediaReferenceSource.ParseRecipeResponse(
            Fixture("wikibooks_es_pastel_choclo.json"), "es", ["pastel", "choclo"]);

        Assert.That(reading, Is.Not.Null);
        Assert.Multiple(() =>
        {
            Assert.That(reading!.Value.Title, Is.EqualTo("Pastel de choclo"));
            Assert.That(reading.Value.Url, Is.EqualTo("https://es.wikibooks.org/wiki/Artes_culinarias/Recetas/Pastel_de_choclo"));
            Assert.That(reading.Value.Authority, Is.EqualTo("wikibooks_es_api"));
            // «Nº de comensales» is the template's placeholder, not a number of servings.
            Assert.That(reading.Value.Servings, Is.Null);
            string evidence = reading.Value.Evidence;
            // The photo says which variant the template writes; the page's prose, what the dish is.
            Assert.That(evidence, Does.StartWith("Pastel dulce de choclo (Perú). Variante dulce, sin relleno y con pasas."));
            Assert.That(evidence, Does.Contain("El pastel de choclo es un plato preparado con una pasta horneada"));
            Assert.That(evidence, Does.Contain("Ingredientes:\n- 2 tazas de Maíz humedo tierno, denominado choclo."));
            Assert.That(evidence, Does.Contain("Preparación:\n1. Ponemos en la batidora los choclos"));
            Assert.That(evidence, Does.Not.Contain("{{").And.Not.Contain("[[").And.Not.Contain("'''"));
            Assert.That(evidence.Length, Is.LessThanOrEqualTo(WikimediaReferenceSource.EvidenceCharacters));
        });
    }

    // «sopaipillas» finds «Sopaipillas pasadas» first; the recipe whose name is the dish
    // itself («Sopaipilla», for 4, fried) is read. Its page keeps the template's blank
    // example inside a comment, which is not the recipe.
    [Test]
    public void TheRecipeNamedExactlyAsTheDishWinsOverAVariant()
    {
        WikimediaReferenceSource.ReferenceReading? reading = WikimediaReferenceSource.ParseRecipeResponse(
            Fixture("wikibooks_es_sopaipillas.json"), "es", ["sopaipillas"]);

        Assert.That(reading, Is.Not.Null);
        Assert.Multiple(() =>
        {
            Assert.That(reading!.Value.Title, Is.EqualTo("Sopaipilla"));
            Assert.That(reading.Value.Servings, Is.EqualTo(4));
            Assert.That(reading.Value.Evidence, Does.Contain("Ingredientes (para 4 personas):\n- 3 tazas de harina"));
            Assert.That(reading.Value.Evidence, Does.Contain("para freír"));
            Assert.That(reading.Value.Evidence, Does.Contain("Se fríen en aceite"));
            Assert.That(reading.Value.Evidence, Does.Not.Contain("Enumerar los ingredientes"));
        });
    }

    // «pan de banana» is not in the Spanish recipe book (the search offers «Rondon»); the
    // Spanish article names the dish in English and the Cookbook has it, in a table.
    [Test]
    public void ADishMissingInSpanishIsReadInTheEnglishCookbookByItsEnglishName()
    {
        Assert.Multiple(() =>
        {
            Assert.That(WikimediaReferenceSource.ParseRecipeResponse(
                Fixture("wikibooks_es_pan_banana.json"), "es", ["pan", "banana"]), Is.Null);
            Assert.That(WikimediaReferenceSource.ParseEnglishName(
                Fixture("wikipedia_es_langlinks_pan_banana.json"), ["pan", "banana"]), Is.EqualTo("Banana bread"));
            Assert.That(WikimediaReferenceSource.ParseEnglishName(
                Fixture("wikipedia_es_langlinks_pan_banana.json"), ["sopaipillas"]), Is.Null);
        });
        WikimediaReferenceSource.ReferenceReading? reading = WikimediaReferenceSource.ParseRecipeResponse(
            Fixture("wikibooks_en_banana_bread.json"), "en", ["banana", "bread"]);
        Assert.That(reading, Is.Not.Null);
        Assert.Multiple(() =>
        {
            Assert.That(reading!.Value.Title, Does.StartWith("Banana Bread"));
            Assert.That(reading.Value.Authority, Is.EqualTo("wikibooks_en_api"));
            Assert.That(reading.Value.Evidence, Does.Contain("Ingredients"));
            Assert.That(reading.Value.Evidence, Does.Contain("Bananas").IgnoreCase);
            Assert.That(reading.Value.Evidence, Does.Contain("Procedure:\n1. "));
            Assert.That(reading.Value.Evidence, Does.Not.Contain("%"));
        });
    }

    // es.wikipedia «El hobbit»: the «Argumento» section, not the introduction, cut at a
    // sentence within 1 500 characters; it is about Smaug's treasure.
    [Test]
    public void AWorksPlotIsItsArgumentSectionCutAtASentence()
    {
        WikimediaReferenceSource.ReferenceReading? reading = WikimediaReferenceSource.ParsePlotResponse(
            Fixture("wikipedia_es_plot_hobbit.json"), "es", ["hobbit"]);

        Assert.That(reading, Is.Not.Null);
        Assert.Multiple(() =>
        {
            Assert.That(reading!.Value.Title, Is.EqualTo("El hobbit"));
            Assert.That(reading.Value.Authority, Is.EqualTo("wikipedia_es_api"));
            Assert.That(reading.Value.Evidence, Does.StartWith("La historia comienza"));
            Assert.That(reading.Value.Evidence, Does.Contain("Smaug"));
            Assert.That(reading.Value.Evidence, Does.EndWith("."));
            Assert.That(reading.Value.Evidence.Length, Is.LessThanOrEqualTo(WikimediaReferenceSource.EvidenceCharacters));
            Assert.That(reading.Value.Evidence, Does.Not.Contain("=="));
            Assert.That(WikimediaReferenceSource.ParsePlotResponse(
                Fixture("wikipedia_es_plot_hobbit.json"), "es", ["silmarillion"]), Is.Null);
        });
    }

    // A ranking is the first table of the list whose title carries what is ranked and by
    // what (es.wikipedia «Anexo:», trimmed real answer: the two other pages cut to 400
    // characters, the list to its first 12 000); rows in their order, with their figures.
    [Test]
    public void ARankingIsTheListsFirstTableInItsOrder()
    {
        WikimediaReferenceSource.ReferenceAsk? ask = WikimediaReferenceSource.Parse("ranking estrellas brillantes");
        Assert.That(ask?.Kind, Is.EqualTo(WikimediaReferenceSource.ReferenceKind.Ranking));
        Assert.That(WikimediaReferenceSource.Parse("ranking objetos brillantes del cielo nocturno")?.Named,
            Is.EqualTo(new[] { "objetos", "brillantes" }));

        WikimediaReferenceSource.ReferenceReading? reading = WikimediaReferenceSource.ParseRankingResponse(
            Fixture("wikipedia_es_ranking_estrellas.json"), "es", ask!.Value.Named);

        Assert.That(reading, Is.Not.Null);
        Assert.Multiple(() =>
        {
            Assert.That(reading!.Value.Title, Is.EqualTo("Estrellas más brillantes"));
            Assert.That(reading.Value.Url, Does.StartWith("https://es.wikipedia.org/wiki/Anexo:"));
            string[] lines = reading.Value.Evidence.Split('\n');
            Assert.That(lines[0], Is.EqualTo("Estrellas más brillantes"));
            Assert.That(lines[1], Does.Contain("Magnitud V").And.Contain("Nombre propio"));
            Assert.That(lines[2], Does.Contain("Sol"));
            Assert.That(lines[3], Does.Contain("Sirio").And.Contain("1,47"));
            Assert.That(reading.Value.Evidence, Does.Not.Contain("simbad").IgnoreCase.Or.Contain("[http"));
            Assert.That(reading.Value.Evidence.Length, Is.LessThanOrEqualTo(WikimediaReferenceSource.EvidenceCharacters));
            // Nothing titled with what was asked: no answer, nothing invented.
            Assert.That(WikimediaReferenceSource.ParseRankingResponse(
                Fixture("wikipedia_es_ranking_estrellas.json"), "es", ["objetos", "brillantes"]), Is.Null);
        });
    }

    [Test]
    public void WikitextBecomesPlainText()
    {
        Assert.Multiple(() =>
        {
            Assert.That(WikimediaReferenceSource.PlainWikiText(
                "2 tazas de {{ing|Maíz}} y [[Cookbook:Butter|mantequilla]] '''fría'''<ref>nota</ref> [[Archivo:x.jpg|miniatura|foto]]"),
                Is.EqualTo("2 tazas de Maíz y mantequilla fría"));
            Assert.That(WikimediaReferenceSource.Sentences("Uno dos. Tres cuatro cinco seis.", 20), Is.EqualTo("Uno dos."));
        });
    }
}
