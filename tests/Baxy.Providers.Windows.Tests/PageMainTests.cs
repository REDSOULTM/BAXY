using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

// Goal h-web (2026-10-25): web.fetch reads a page's main content without what the page marks as boilerplate. Pages
// written for the test (Fixtures/Web), no network.
[TestFixture]
public sealed class PageMainTests
{
    private static string Fixture(string name) =>
        File.ReadAllText(Path.Combine(TestContext.CurrentContext.TestDirectory, "Fixtures", "Web", name));

    [Test]
    public void FocusReadsTheMainContentWithoutBannersMenusOrShareBars()
    {
        (string title, string text, int skipped) = PageText.Prose(Fixture("historia_metro.html"));

        Assert.That(title, Is.EqualTo("Nuestra historia | Metro de prueba"));
        Assert.That(text, Does.StartWith("Nuestra Historia"));
        Assert.That(text, Does.Contain("1975\nEl 15 de septiembre se inauguró oficialmente el primer trayecto"));
        Assert.That(text, Does.Contain("Línea 2"));
        foreach (string boilerplate in new[]
                 {
                     "cookies", "Aceptar", "Tarifas", "Gobierno corporativo", "Compartir", "También te puede",
                     "boletín", "derechos reservados", "no es la página",
                 })
            Assert.That(text, Does.Not.Contain(boilerplate), boilerplate);
        Assert.That(skipped, Is.GreaterThan(100));
    }

    [Test]
    public void FocusDropsEditLinksReferenceMarksNavboxesAndKeepsNestedContent()
    {
        (_, string text, _) = PageText.Prose(Fixture("rios_wiki.html"));

        Assert.That(text, Does.Contain("El Volga es el río más largo de Europa, con unos 3690 km"));
        Assert.That(text, Does.Contain("sus caudales medios"));
        Assert.That(text, Does.Contain("Criterios"));
        foreach (string boilerplate in new[]
                 {
                     "Ir al contenido", "editar", "[1]", "Atlas de prueba", "Ríos de Rusia", "Portada", "Categorías",
                     "última vez", "1 Criterios",
                 })
            Assert.That(text, Does.Not.Contain(boilerplate), boilerplate);
    }

    [Test]
    public void AMainWithLittleTextIsNotReadAlone()
    {
        const string html = "<html><body><main><h1>Hola</h1></main>"
            + "<div><p>Un párrafo largo fuera del elemento principal que sí es el contenido de la página, "
            + "escrito con texto suficiente para que sea lo que una persona lee al abrirla, y que no debe perderse "
            + "porque el sitio marcó como principal sólo su encabezado; la regla exige trescientos caracteres de texto "
            + "en el elemento principal antes de leerlo solo, y aquí no los hay.</p></div></body></html>";

        (_, string text, _) = PageText.Prose(html);

        Assert.That(text, Does.Contain("Hola"));
        Assert.That(text, Does.Contain("Un párrafo largo fuera del elemento principal"));
    }

    [Test]
    public void AnAttributeHoldingMarkupNeverReachesTheText()
    {
        const string html = "<html><body><p>Fundada en 1945.</p>"
            + "<table data-mw='{\"parts\":[{\"wt\":\"<span>creado</span>\"}]}'><tr><td>Sede</td></tr></table>"
            + "</body></html>";

        (_, string text, _) = PageText.Prose(html);

        Assert.That(text, Is.EqualTo("Fundada en 1945.\nSede"));
    }

    // Uso real 04-11 (F40): a store's <body class="… menu_background_overlap …"> matched the boilerplate rule, the whole
    // page went with it, and web.fetch answered «completed» with no text. What holds most of the page is the page.
    [TestCase("<body class=\"v6 app menu_background_overlap responsive_page\">", "</body>")]
    [TestCase("<body><div class=\"has-sidebar page_wrapper\">", "</div></body>")]
    public void AMarkedElementHoldingMostOfThePageIsThePage(string open, string close)
    {
        string html = "<html><head><title>Juego de prueba</title></head>" + open
            + "<div class=\"store_menu\"><a>Tienda</a></div>"
            + "<div role=\"main\"><h1>Juego de prueba</h1><p>" + new string('x', 20) + " " + string.Concat(Enumerable.Repeat(
                "Un juego de prueba con su descripción larga, sus requisitos y su precio. ", 8)) + "</p>"
            + "<div class=\"share_bar\">Compartir esto</div></div>" + close + "</html>";

        (_, string text, _) = PageText.Prose(html);

        Assert.Multiple(() =>
        {
            Assert.That(text, Does.Contain("descripción larga"));
            Assert.That(text, Does.Not.Contain("Tienda"), "what is marked inside it still goes");
            Assert.That(text, Does.Not.Contain("Compartir"), "what is marked inside it still goes");
        });
    }

    [Test]
    public void AMarkedElementNeverClosedLeavesNothingOut()
    {
        const string html = "<html><body><div class=\"menu\"><p>Texto de la página que sigue sin cerrar el menú.</p>"
            + "</body></html>";

        (_, string text, _) = PageText.Prose(html);

        Assert.That(text, Does.Contain("Texto de la página"));
    }
}
