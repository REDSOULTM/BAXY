using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

// Goal h-web (2026-10-25): web.fetch with BAXY_WEB_FOCUS=1 reads a page's main content without what the page marks as
// boilerplate; unset, the page is read as before. Pages written for the test (Fixtures/Web), no network.
[TestFixture]
public sealed class PageMainTests
{
    private static string Fixture(string name) =>
        File.ReadAllText(Path.Combine(TestContext.CurrentContext.TestDirectory, "Fixtures", "Web", name));

    [Test]
    public void FocusReadsTheMainContentWithoutBannersMenusOrShareBars()
    {
        (string title, string text, int skipped) = PageText.Prose(Fixture("historia_metro.html"), mainOnly: true);

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
    public void FocusOffReadsThePageAsBefore()
    {
        string html = Fixture("historia_metro.html");
        (string title, string text, int skipped) = PageText.Prose(html, mainOnly: false);

        Assert.That((title, text, skipped), Is.EqualTo(PageText.Prose(html)));
        Assert.That(text, Does.Contain("Usamos cookies"));
        Assert.That(text, Does.Contain("Compartir en redes"));
    }

    [Test]
    public void FocusDropsEditLinksReferenceMarksNavboxesAndKeepsNestedContent()
    {
        (_, string text, _) = PageText.Prose(Fixture("rios_wiki.html"), mainOnly: true);

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

        (_, string text, _) = PageText.Prose(html, mainOnly: true);

        Assert.That(text, Does.Contain("Hola"));
        Assert.That(text, Does.Contain("Un párrafo largo fuera del elemento principal"));
    }

    [Test]
    public void AnAttributeHoldingMarkupNeverReachesTheText()
    {
        const string html = "<html><body><p>Fundada en 1945.</p>"
            + "<table data-mw='{\"parts\":[{\"wt\":\"<span>creado</span>\"}]}'><tr><td>Sede</td></tr></table>"
            + "</body></html>";

        (_, string text, _) = PageText.Prose(html, mainOnly: true);

        Assert.That(text, Is.EqualTo("Fundada en 1945.\nSede"));
    }

    [Test]
    public void AMarkedElementNeverClosedLeavesNothingOut()
    {
        const string html = "<html><body><div class=\"menu\"><p>Texto de la página que sigue sin cerrar el menú.</p>"
            + "</body></html>";

        (_, string text, _) = PageText.Prose(html, mainOnly: true);

        Assert.That(text, Does.Contain("Texto de la página"));
    }
}
