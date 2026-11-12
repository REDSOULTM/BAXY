using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Encargo LEC3 (the owner's 10-11 case, «¿qué se está haciendo en esta conversación?»): with the cap fixed (LEC2), the
/// answers left false were all «which is the last one» or «who said it». The text went by the 3×3 grid's bands, so a short
/// author line («Mamá · 19:30») fell in the left third and its message in the centre one, and the bottom band listed every
/// author first and every message after. These windows are laid out as such a window is: a narrow list at the left, a
/// wide panel with messages that each have a short author line on top, the newest at the bottom.
/// </summary>
[TestFixture]
public sealed class ReadingBlocksTests
{
    private const double Width = 1920;
    private const double Height = 1040;

    private static WindowsVisibleOcrLocator.LayoutLine Line(string text, double x, double y, double width) => new(text, x, y, width, 18);

    // A side list (rows 30 px apart, side by side with the panel), then the panel's messages: an author line, then one or
    // two lines of text 24 px apart, and 20 px between messages. OCR order: the side list first.
    private static List<WindowsVisibleOcrLocator.LayoutLine> Conversation(double panelEnd)
    {
        var read = new List<WindowsVisibleOcrLocator.LayoutLine>();
        for (int row = 0; row < 25; row++)
            read.Add(Line($"Charla {row} del grupo", 16, 70 + row * 30, 200));
        string[] who = ["Mamá · 18:02", "Ignacio · 18:05", "Valentina · 18:07", "Papá · 18:11"];
        double y = panelEnd - (4 * (18 + 24 + 24) + 3 * 20) + 6;
        for (int message = 0; message < who.Length; message++)
        {
            read.Add(Line(who[message], 360, y, 130));
            read.Add(Line($"Mensaje {message}: una frase larga que ocupa casi todo el ancho del panel abierto", 360, y + 24, 1300));
            read.Add(Line($"y sigue en otra línea del mismo mensaje {message}.", 360, y + 48, 420));
            y += 66 + 20;
        }

        return read;
    }

    private static string[] Texts(IReadOnlyList<WindowsVisibleOcrLocator.LayoutLine> block) => [.. block.Select(static line => line.Text)];

    [Test]
    public void EachColumnIsReadTopToBottomAndEachAuthorStaysWithItsMessage()
    {
        IReadOnlyList<WindowsVisibleOcrLocator.TextColumn> columns =
            WindowsVisibleOcrLocator.ReadingColumns(Conversation(900), Width, Height);

        Assert.That(columns, Has.Count.EqualTo(2), "the side list and the panel");
        Assert.Multiple(() =>
        {
            Assert.That(columns[0].Blocks.SelectMany(static block => block).All(static line => line.X < 300), Is.True, "the side list first");
            Assert.That(columns[1].Blocks, Has.Count.EqualTo(4), "one block a message");
            for (int message = 0; message < 4; message++)
            {
                Assert.That(Texts(columns[1].Blocks[message]), Has.Length.EqualTo(3));
                Assert.That(Texts(columns[1].Blocks[message])[1], Does.StartWith($"Mensaje {message}:"), "its author line on top");
            }

            Assert.That(Texts(columns[1].Blocks[^1])[0], Is.EqualTo("Papá · 18:11"), "the last block, the newest message");
            Assert.That(columns[1].ToBottomEdge, Is.False, "the panel ends well above the window's bottom");
        });
    }

    [Test]
    public void AColumnThatReachesTheBottomEdgeIsSaidToGoOn()
    {
        IReadOnlyList<WindowsVisibleOcrLocator.TextColumn> columns =
            WindowsVisibleOcrLocator.ReadingColumns(Conversation(Height - 4), Width, Height);

        Assert.That(columns, Has.Count.EqualTo(2));
        Assert.That(columns[1].ToBottomEdge, Is.True, "its last line is cut by the window's bottom edge");
    }

    // Control: a chat's bubbles, the person's at the right and the others' at the left, one under the other. They never sit
    // side by side, so they are one column in the order they were written, never «the left ones, then the right ones».
    [Test]
    public void BubblesAtTheLeftAndTheRightOneUnderTheOtherStayOneColumn()
    {
        var read = new List<WindowsVisibleOcrLocator.LayoutLine>();
        double y = 100;
        for (int message = 0; message < 6; message++)
        {
            bool mine = message % 2 == 1;
            // The person's time line is short and right-aligned above a bubble whose text starts further left.
            read.Add(Line(mine ? $"Tú · 10:0{message}" : $"Lucía · 10:0{message}", mine ? 1700 : 360, y, 120));
            read.Add(Line($"Burbuja {message} con su texto", mine ? 1300 : 360, y + 24, 520));
            y += 42 + 20;
        }

        IReadOnlyList<WindowsVisibleOcrLocator.TextColumn> columns = WindowsVisibleOcrLocator.ReadingColumns(read, Width, Height);

        Assert.That(columns, Has.Count.EqualTo(1));
        Assert.That(columns[0].Blocks, Has.Count.EqualTo(6), "one block a bubble, its short line on top joined to it");
        Assert.That(columns[0].Blocks.Select(static block => block[^1].Text),
            Is.EqualTo(Enumerable.Range(0, 6).Select(static message => $"Burbuja {message} con su texto")));
    }

    // Control: the window's title reaches across the gap between the list and the panel, and the list's rows and the
    // panel's mails share some gaps; the panel is still one column, its mails blocks in it, never a column each.
    [Test]
    public void ATitleOverTheListDoesNotCutThePanelIntoPieces()
    {
        var read = new List<WindowsVisibleOcrLocator.LayoutLine> { new("Correo — Paseo del puente festivo", 60, 8, 295, 14) };
        for (int row = 0; row < 30; row++)
            read.Add(new($"Carpeta {row}", 16, 70 + row * 30, 150, 14));
        // The panel's header, and its buttons at its right on the same row.
        read.Add(new("Paseo del puente festivo", 360, 60, 280, 20));
        read.Add(new("Responder", 1210, 62, 72, 14));
        read.Add(new("Reenviar", 1550, 62, 64, 14));
        double y = 110;
        for (int mail = 0; mail < 5; mail++)
        {
            read.Add(new($"Remitente {mail} · 3 nov 08:1{mail}", 360, y, 260, 16));
            y += 16;
            for (int line = 0; line < 3; line++)
            {
                y += 6;
                read.Add(Line($"Correo {mail}, línea {line} del cuerpo, que ocupa el ancho del panel", 360, y, 1300));
                y += 18;
            }

            y += 28;
        }

        IReadOnlyList<WindowsVisibleOcrLocator.TextColumn> columns = WindowsVisibleOcrLocator.ReadingColumns(read, Width, Height);

        WindowsVisibleOcrLocator.TextColumn panel = columns.Single(static column => column.Left >= 300);
        Assert.That(panel.Blocks.Select(static block => block[0].Text), Is.EqualTo(new[] { "Paseo del puente festivo" }
            .Concat(Enumerable.Range(0, 5).Select(static mail => $"Remitente {mail} · 3 nov 08:1{mail}"))));
    }

    // Control (encargo 119): a table's columns share every row; it is one column whose rows keep their cells together,
    // never «every name, then every figure».
    [Test]
    public void ATableStaysByRows()
    {
        string[] names = ["Tornillo", "Arandela", "Tuerca", "Clavo", "Perno", "Remache"];
        var read = new List<WindowsVisibleOcrLocator.LayoutLine>();
        for (int row = 0; row < names.Length; row++)
        {
            read.Add(Line(names[row], 400, 200 + row * 30, 80));
            read.Add(Line($"{120 + row}", 700, 200 + row * 30, 30));
            read.Add(Line($"{75 + row}", 1000, 200 + row * 30, 20));
        }

        IReadOnlyList<WindowsVisibleOcrLocator.TextColumn> columns =
            WindowsVisibleOcrLocator.ReadingColumns(read, Width, Height, static _ => false);

        Assert.That(columns, Has.Count.EqualTo(1));
        string first = columns[0].Blocks[0][0].Text;
        Assert.That(first, Does.Contain("Tornillo").And.Contain("120").And.Contain("75"));
    }

    // A side list with the panel's very leading: every row has a twin line in the panel, as a table's cells do, but the
    // panel's lines are long prose. Two columns.
    [Test]
    public void ASideListBesideAPanelWithTheSameLeadingIsTwoColumns()
    {
        var read = new List<WindowsVisibleOcrLocator.LayoutLine>();
        for (int row = 0; row < 30; row++)
            read.Add(Line($"Charla {row}", 16, 60 + row * 24, 160));
        for (int line = 0; line < 30; line++)
            read.Add(Line($"Línea {line} de un mensaje largo que ocupa casi todo el ancho del panel abierto", 290, 60 + line * 24, 1100));

        IReadOnlyList<WindowsVisibleOcrLocator.TextColumn> columns = WindowsVisibleOcrLocator.ReadingColumns(read, Width, Height);

        Assert.That(columns, Has.Count.EqualTo(2));
        Assert.That(columns[1].Blocks.SelectMany(static block => block).Count(), Is.EqualTo(30));
    }

    // As a real window read on the NB (LEC1's mail page in Edge): the title bar's text crosses the gap between the list
    // and the panel, 23 px above the list's first row.
    [Test]
    public void ATitleBarCrossingTheGapIsSetApart()
    {
        var read = new List<WindowsVisibleOcrLocator.LayoutLine> { new("Re: Salón para la fiesta - Correo", 41, 14, 364, 15) };
        for (int row = 0; row < 26; row++)
            read.Add(new($"Asunto de un correo número {row}", 25, 52 + row * 30, 250, 16));
        for (int line = 0; line < 9; line++)
            read.Add(new($"Párrafo {line} del correo abierto, largo como el ancho del panel", 371, 162 + line * 82, 900, 19));

        IReadOnlyList<WindowsVisibleOcrLocator.TextColumn> columns = WindowsVisibleOcrLocator.ReadingColumns(read, Width, Height);

        WindowsVisibleOcrLocator.TextColumn panel = columns.Single(static column => column.Left > 300);
        Assert.That(panel.Blocks, Has.Count.EqualTo(9));
        Assert.That(columns.Where(static column => column.Left < 300).SelectMany(static column => column.Blocks).SelectMany(static block => block)
            .Count(), Is.EqualTo(27), "the title and the list's rows, apart from the panel");
    }

    // Messages of one line each, far apart, and one of two lines: the gap between messages is the usual one, still each
    // message is a block (the column's leading is its two-line message's).
    [Test]
    public void OneLineMessagesFarApartAreABlockEach()
    {
        var read = new List<WindowsVisibleOcrLocator.LayoutLine>();
        for (int message = 0; message < 6; message++)
            read.Add(Line($"Mensaje {message} de una sola línea, largo como para llenar el panel", 370, 160 + message * 82, 900));
        read.Add(Line("y su segunda línea.", 370, 160 + 5 * 82 + 24, 400));

        IReadOnlyList<WindowsVisibleOcrLocator.TextColumn> columns = WindowsVisibleOcrLocator.ReadingColumns(read, Width, Height);

        Assert.That(columns.Single().Blocks.Select(static block => block.Count), Is.EqualTo(new[] { 1, 1, 1, 1, 1, 2 }));
    }

    // LEC3 held-out H01: beside a side list, the person's last bubble at the right is narrower than the others, so a gap
    // parts it from the others' bubbles; it shares rows only with the side list, two strips away. It is the panel's last
    // block, never a column of its own read after the panel.
    [Test]
    public void ThePersonsLastNarrowBubbleStaysTheLastBlockOfThePanel()
    {
        var read = new List<WindowsVisibleOcrLocator.LayoutLine>();
        for (int row = 0; row < 30; row++)
            read.Add(new($"Charla {row}", 16, 70 + row * 30, 200, 14));
        double y = 300;
        for (int message = 0; message < 6; message++)
        {
            bool mine = message == 5;
            read.Add(Line(mine ? "Tú · 21:52" : $"Pilar · 21:4{message}", mine ? 1795 : 360, y, 85));
            read.Add(Line($"Mensaje {message} con su texto", mine ? 1500 : 360, y + 24, mine ? 380 : 760));
            y += 42 + 20;
        }

        IReadOnlyList<WindowsVisibleOcrLocator.TextColumn> columns = WindowsVisibleOcrLocator.ReadingColumns(read, Width, Height);

        Assert.That(columns, Has.Count.EqualTo(2), "the side list and the panel");
        Assert.That(Texts(columns[1].Blocks[^1]), Is.EqualTo(new[] { "Tú · 21:52", "Mensaje 5 con su texto" }));
    }

    // Control: the lines of one paragraph, 4 px apart, are one block (pdfminer's line_margin: lines closer than half a line's
    // height are one paragraph), and a title across the whole window sits above both columns.
    [Test]
    public void ATitleAcrossTheWindowComesFirstAndAParagraphIsOneBlock()
    {
        var read = new List<WindowsVisibleOcrLocator.LayoutLine> { Line("Informe trimestral de la cooperativa", 16, 10, 1880) };
        for (int row = 0; row < 8; row++)
            read.Add(Line($"Carpeta {row}", 16, 80 + row * 30, 150));
        for (int line = 0; line < 10; line++)
            read.Add(Line($"Línea {line} del párrafo, que ocupa el ancho del panel", 360, 80 + line * 22, 1400));

        IReadOnlyList<WindowsVisibleOcrLocator.TextColumn> columns = WindowsVisibleOcrLocator.ReadingColumns(read, Width, Height);

        Assert.That(columns, Has.Count.EqualTo(3), "the title, the list, the panel");
        Assert.Multiple(() =>
        {
            Assert.That(Texts(columns[0].Blocks[0]), Is.EqualTo(new[] { "Informe trimestral de la cooperativa" }));
            Assert.That(columns[1].Blocks.SelectMany(static block => block).All(static line => line.X < 300), Is.True);
            Assert.That(columns[2].Blocks, Has.Count.EqualTo(1));
            Assert.That(columns[2].Blocks[0], Has.Count.EqualTo(10));
        });
    }
}
