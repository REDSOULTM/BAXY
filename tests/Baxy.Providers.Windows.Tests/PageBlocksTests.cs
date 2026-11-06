using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Uso-111 (P3): a page that is a list of linked items is read as blocks, each fact beside its source, told by the page's
/// structure only; a page that is not (an article, a menu) is read as before. The shapes are the ones UI Automation gives
/// in Chromium, measured in Chromium 140 on a local page and on public result pages.
/// </summary>
[TestFixture]
public sealed class PageBlocksTests
{
    private static int s_line;

    private static PageNode Link(string name, string address, int depth = 2, int under = -1, int rise = 2, bool sameLine = false) =>
        new(true, name, address, depth, under, rise, false, Line(sameLine), Line(sameLine) + 16);

    private static PageNode Text(string name, int depth = 2, int under = -1, int rise = 2, bool sameLine = false, bool gap = false) =>
        new(false, name, string.Empty, depth, under, rise, gap, Line(sameLine), Line(sameLine) + 16);

    private static double Line(bool same)
    {
        if (!same)
            s_line += 10;
        return s_line * 2;
    }

    [SetUp]
    public void Reset() => s_line = 0;

    private static IReadOnlyList<PageBlock> Read(IReadOnlyList<PageNode> nodes, int textLength = 20, int maximum = 6_000) =>
        PageBlocks.Read(nodes, textLength, maximum, out _);

    [Test]
    public void ALinkThatHoldsItsHeadingWithTheTextBelowIsOneBlockEach()
    {
        IReadOnlyList<PageBlock> blocks = Read(
        [
            Link("Bus a Lima rutas.test", "https://rutas.test/lima"),
            Text("Bus a Lima", depth: 3, under: 0),
            Text("El viaje dura 54 horas."),
            Link("Vuelos a Lima vuelos.test", "https://vuelos.test/lima"),
            Text("Vuelos a Lima", depth: 3, under: 3),
            Text("El vuelo tarda 13 h 25 min."),
        ]);

        Assert.That(blocks, Is.EqualTo(new PageBlock[]
        {
            new("Bus a Lima", "https://rutas.test/lima", "rutas.test\nEl viaje dura 54 horas."),
            new("Vuelos a Lima", "https://vuelos.test/lima", "vuelos.test\nEl vuelo tarda 13 h 25 min."),
        }));
    }

    [Test]
    public void AHeadingThatHoldsItsLinkIsATitleAndLinksToTheSameAddressAreItsText()
    {
        IReadOnlyList<PageBlock> blocks = Read(
        [
            Text("Faro norte"),
            Link("Faro norte", "https://a.test/1", depth: 3, under: 0),
            Link("a.test/1", "https://a.test/1"),
            Link("Lo construyeron en 1888.", "https://a.test/1"),
            Text("Faro sur"),
            Link("Faro sur", "https://b.test/2", depth: 3, under: 4),
            Link("b.test/2", "https://b.test/2"),
            Link("Lo construyeron en 1920.", "https://b.test/2"),
        ]);

        Assert.That(blocks, Is.EqualTo(new PageBlock[]
        {
            new("Faro norte", "https://a.test/1", "a.test/1\nLo construyeron en 1888."),
            new("Faro sur", "https://b.test/2", "b.test/2\nLo construyeron en 1920."),
        }));
    }

    [Test]
    public void ASiteLinkOverTheTitleGoesWithItsItem()
    {
        IReadOnlyList<PageBlock> blocks = Read(
        [
            Link("uno.test", "https://uno.test/x"),
            Text("Título uno"),
            Link("Título uno", "https://uno.test/x", depth: 3, under: 1),
            Text("Dato uno."),
            Link("dos.test", "https://dos.test/y"),
            Text("Título dos"),
            Link("Título dos", "https://dos.test/y", depth: 3, under: 5),
            Text("Dato dos."),
        ]);

        Assert.That(blocks, Is.EqualTo(new PageBlock[]
        {
            new("Título uno", "https://uno.test/x", "uno.test\nDato uno."),
            new("Título dos", "https://dos.test/y", "dos.test\nDato dos."),
        }));
    }

    [Test]
    public void WordsMarkedInsideASentenceAreOneLine()
    {
        IReadOnlyList<PageBlock> blocks = Read(
        [
            Link("Título uno", "https://uno.test/x"),
            Text("El "),
            Text("dólar", sameLine: true),
            Text("está a 900.", sameLine: true, gap: true),
            Link("Título dos", "https://dos.test/y"),
            Text("Otro dato."),
        ]);

        Assert.That(blocks[0].Text, Is.EqualTo("El dólar está a 900."));
    }

    [Test]
    public void LeavingTheContainerEndsTheItem()
    {
        IReadOnlyList<PageBlock> blocks = Read(
        [
            Link("Título uno", "https://uno.test/x"),
            Text("Dato uno."),
            Link("Título dos", "https://dos.test/y"),
            Text("Dato dos."),
            Text("Búsquedas relacionadas", rise: 1),
        ]);

        Assert.That(blocks[1].Text, Is.EqualTo("Dato dos."));
    }

    [Test]
    public void AnArticleWithLinksInsideItsSentencesHasNoBlocks()
    {
        IReadOnlyList<PageBlock> blocks = Read(
        [
            Text("Lo construyeron en 1888 con "),
            Link("piedra", "https://a.test/piedra", sameLine: true),
            Text(" local.", sameLine: true),
            Text("Otro párrafo con "),
            Link("más datos", "https://a.test/datos", sameLine: true),
            Text(" dentro.", sameLine: true),
        ]);

        Assert.That(blocks, Is.Empty);
    }

    [Test]
    public void AMenuOfLinksWithNoTextOfTheirOwnHasNoBlocks()
    {
        IReadOnlyList<PageBlock> blocks = Read(
        [
            Link("Inicio", "https://a.test/"),
            Link("Noticias", "https://a.test/n"),
            Link("Contacto", "https://a.test/c"),
        ]);

        Assert.That(blocks, Is.Empty);
    }

    [Test]
    public void TwoCaptionsInALongArticleAreNoList()
    {
        PageNode[] nodes =
        [
            Link("Foto uno", "https://a.test/1"),
            Text("Una foto."),
            Link("Foto dos", "https://a.test/2"),
            Text("Otra foto."),
        ];

        Assert.Multiple(() =>
        {
            Assert.That(Read(nodes, textLength: 40), Has.Count.EqualTo(2));
            Assert.That(Read(nodes, textLength: 6_000), Is.Empty);
        });
    }

    [Test]
    public void AnItemWithAnArticlesTextIsNoListsItem()
    {
        IReadOnlyList<PageBlock> blocks = Read(
        [
            Link("Título uno", "https://uno.test/x"),
            Text(new string('a', 1_300)),
            Link("Título dos", "https://dos.test/y"),
            Text("Dato dos."),
        ], textLength: 1_400);

        Assert.That(blocks, Is.Empty);
    }

    [Test]
    public void ARowsWorthOfOtherLinksIsNoItem()
    {
        PageNode[] rows =
        [
            Link("Título uno", "https://uno.test/x"),
            Text("Dato uno."),
            Link("Título dos", "https://dos.test/y"),
            Text("Dato dos."),
            Link("Título tres", "https://tres.test/z"),
            Text("1 "),
            Link("a", "https://o.test/a", sameLine: true),
            Link("b", "https://o.test/b", sameLine: true),
            Link("c", "https://o.test/c", sameLine: true),
        ];

        Assert.That(Read(rows).Select(static block => block.Title), Is.EqualTo(new[] { "Título uno", "Título dos" }));
    }

    // Revisión: un logo solo en su línea sobre la introducción no es un resultado de la lista.
    [Test]
    public void WhereTheItemsHaveATitleABareLinkIsNoItem()
    {
        IReadOnlyList<PageBlock> blocks = Read(
        [
            Link("Logo", "https://motor.test/"),
            Text("Resultados de la búsqueda"),
            Text("Uno"),
            Link("Uno", "https://uno.test/x", depth: 3, under: 2),
            Text("Dato uno."),
            Text("Dos"),
            Link("Dos", "https://dos.test/y", depth: 3, under: 5),
            Text("Dato dos."),
        ]);

        Assert.That(blocks.Select(static block => block.Title), Is.EqualTo(new[] { "Uno", "Dos" }));
    }

    // Revisión: el 40 % se mide contra lo que la página tiene, no contra su texto cortado a 6.000.
    [Test]
    public void CardsBelowALongArticleAreNoListEvenWithTheTextCut()
    {
        IReadOnlyList<PageBlock> blocks = PageBlocks.Read(
        [
            Text(new string('a', 8_000)),
            Link("Uno", "https://uno.test/x"), Text(new string('b', 500)),
            Link("Dos", "https://dos.test/y"), Text(new string('c', 500)),
        ], textLength: 1_500, maximumCharacters: 6_000, out _);

        Assert.That(blocks, Is.Empty);
    }

    // Revisión: el sitio va encima del título, y dos resultados del mismo sitio no se saltan uno a otro.
    [Test]
    public void ASiteOverItsTitleLeavesNothingOfTheItemInTheText()
    {
        PageBlock[] blocks =
        [
            new("Título uno", "https://wiki.test/1", "wiki.test\nDato uno."),
            new("Título dos", "https://wiki.test/2", "wiki.test\nDato dos."),
            new("Título tres", "https://wiki.test/3", "wiki.test\nDato tres."),
        ];
        const string text = "Buscar\nwiki.test\nTítulo uno\nDato uno.\nwiki.test\nTítulo dos\nDato dos.\nwiki.test\nTítulo tres\nDato tres.\nPie";

        Assert.That(PageBlocks.TextOutside(text, blocks, 1_000, out _), Is.EqualTo("Buscar\nPie"));
    }

    [Test]
    public void ABudgetThatLeavesNoListSaysNoCut()
    {
        IReadOnlyList<PageBlock> blocks = PageBlocks.Read(
        [
            Link("Uno", "https://u.test"), Text(new string('a', 300)),
            Link("Dos", "https://d.test"), Text(new string('b', 300)),
        ], 600, 256, out bool cut);

        Assert.Multiple(() =>
        {
            Assert.That(blocks, Is.Empty);
            Assert.That(cut, Is.False);
        });
    }

    [Test]
    public void AWrappersLongAddressIsLeftOutAndTheTextStillSaysTheSite()
    {
        string wrapper = "https://motor.test/l/?u=" + new string('x', 300);
        IReadOnlyList<PageBlock> blocks = Read(
        [
            Link("Título uno", wrapper),
            Link("uno.test/x", wrapper),
            Link("Título dos", "https://dos.test/y"),
            Text("Dato dos."),
        ]);

        Assert.Multiple(() =>
        {
            Assert.That(blocks[0].Address, Is.Empty);
            Assert.That(blocks[0].Text, Is.EqualTo("uno.test/x"));
        });
    }

    [Test]
    public void TheBudgetCutsWholeBlocksAndSaysSo()
    {
        PageNode[] nodes =
        [
            Link("Uno", "https://u.test"), Text(new string('a', 100)),
            Link("Dos", "https://d.test"), Text(new string('b', 100)),
            Link("Tres", "https://t.test"), Text(new string('c', 100)),
        ];

        IReadOnlyList<PageBlock> blocks = PageBlocks.Read(nodes, 300, 340, out bool cut);

        Assert.Multiple(() =>
        {
            Assert.That(blocks, Has.Count.EqualTo(2));
            Assert.That(cut, Is.True);
        });
    }

    [Test]
    public void TheTextKeepsOnlyWhatTheBlocksDoNotHold()
    {
        PageBlock[] blocks =
        [
            new("Título uno", "https://uno.test/x", "uno.test\nDato uno."),
            new("Título dos", "https://dos.test/y", "Dato dos."),
        ];
        const string text = "Buscar\nTítulo uno\nuno.test\nDato uno.\nAnuncio entre medias\nTítulo dos\nDato dos.\nBúsquedas relacionadas\nDato dos.";

        string outside = PageBlocks.TextOutside(text, blocks, 1_000, out bool cut);

        Assert.Multiple(() =>
        {
            Assert.That(outside, Is.EqualTo("Buscar\nAnuncio entre medias\nBúsquedas relacionadas\nDato dos."));
            Assert.That(cut, Is.False);
        });
    }

    [Test]
    public void ThePiecesNotFoundStayAndTheBudgetCutsTheRest()
    {
        PageBlock[] blocks = [new("Otro título", string.Empty, "Otro dato.")];

        string outside = PageBlocks.TextOutside("Un texto de la página", blocks, 8, out bool cut);

        Assert.Multiple(() =>
        {
            Assert.That(outside, Is.EqualTo("Un texto"));
            Assert.That(cut, Is.True);
        });
    }

    [Test]
    public void AnEmbeddedObjectsMarkHasNothingToRead() =>
        Assert.That(PageBlocks.WithoutObjectMarks("Uno\n￼\n￼\nDos ￼ tres"), Is.EqualTo("Uno\nDos  tres"));
}
