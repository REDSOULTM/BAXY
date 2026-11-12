using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Encargo LEC2 (the owner's 10-11 case, «lee la conversación que tengo abierta»): the look's cap of OCR lines was spent in
/// the order Windows.Media.Ocr gives them, a side column of rows first, before the lines that only repeat a listed control
/// were left out; the list's rows filled the cap, vanished as repeats, and the conversation beside them stayed out.
/// A 1920×1080 window, laid out as the real one: a narrow column at the left with rows that name listed controls, and a
/// wide panel with the newest message at its bottom.
/// </summary>
[TestFixture]
public sealed class ReadingCapTests
{
    private const double Width = 1920;

    private static WindowsVisibleOcrLocator.LayoutLine Line(string text, double x, double y, double width) => new(text, x, y, width, 14);

    // OCR order: the side column's text block first, then the panel's.
    private static (List<WindowsVisibleOcrLocator.LayoutLine> Read, HashSet<string> Controls) Conversation(int panelLines)
    {
        var read = new List<WindowsVisibleOcrLocator.LayoutLine>();
        var controls = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        for (int row = 0; row < 40; row++)
        {
            string title = $"Charla número {row} con el grupo";
            controls.Add(title);
            read.Add(Line(title, 12, 40 + row * 25, 210));
            read.Add(Line($"hace {row + 1} días", 12, 52 + row * 25, 90));
        }

        for (int message = 0; message < panelLines; message++)
        {
            string text = message == panelLines - 1
                ? "Último mensaje: quedamos en revisar el presupuesto del techo el jueves a las nueve de la mañana"
                : $"Mensaje {message} de la conversación abierta, con una frase larga que ocupa casi todo el ancho del panel";
            read.Add(Line(text, 420, 60 + message * 32, 1400));
        }

        return (read, controls);
    }

    [Test]
    public void TheWidePanelIsKeptBeforeTheRowsOfAListOfControls()
    {
        (List<WindowsVisibleOcrLocator.LayoutLine> read, HashSet<string> controls) = Conversation(30);
        var leftOut = new List<WindowsVisibleOcrLocator.LayoutLine>();

        IReadOnlyList<WindowsVisibleOcrLocator.LayoutLine> kept =
            WindowsVisibleOcrLocator.Listed(read, 60, controls.Contains, Width, tail: false, leftOut);

        Assert.Multiple(() =>
        {
            Assert.That(kept.Count(static line => line.X >= 400), Is.EqualTo(30), "the panel, whole");
            Assert.That(kept.Select(static line => line.Text), Has.Some.StartsWith("Último mensaje"));
            // The repeats of listed controls are not what the cap counts: the projection leaves them out as repeats.
            Assert.That(kept.Count(line => controls.Contains(line.Text)), Is.EqualTo(40));
            Assert.That(leftOut, Has.Count.EqualTo(10));
            Assert.That(leftOut.All(static line => line.X < 400 && line.Text.StartsWith("hace", StringComparison.Ordinal)), Is.True,
                "what stays out is the list's rows");
            Assert.That(kept.Where(static line => line.X >= 400).Select(static line => line.Y), Is.Ordered, "in reading order");
        });
    }

    [Test]
    public void WithTailTheCutKeepsTheLastLinesOfTheText()
    {
        (List<WindowsVisibleOcrLocator.LayoutLine> read, HashSet<string> controls) = Conversation(30);
        List<WindowsVisibleOcrLocator.LayoutLine> panel = [.. read.Where(static line => line.X >= 400)];
        var leftOut = new List<WindowsVisibleOcrLocator.LayoutLine>();

        IReadOnlyList<WindowsVisibleOcrLocator.LayoutLine> kept =
            WindowsVisibleOcrLocator.Listed(panel, 20, controls.Contains, Width, tail: true, leftOut);

        Assert.Multiple(() =>
        {
            Assert.That(kept, Has.Count.EqualTo(20));
            Assert.That(kept[^1].Text, Does.StartWith("Último mensaje"));
            Assert.That(leftOut, Has.Count.EqualTo(10));
            Assert.That(leftOut.Max(static line => line.Y), Is.LessThan(kept.Min(static line => line.Y)));
        });
    }

    // Control: a narrow column of short lines that names no control (a column of figures, short replies) is text like any
    // other; the cut takes the reading order's last lines whatever their column.
    [Test]
    public void ANarrowColumnThatNamesNoControlIsNotTakenForAList()
    {
        var read = new List<WindowsVisibleOcrLocator.LayoutLine>();
        for (int row = 0; row < 40; row++)
            read.Add(Line($"{row},40", 12, 40 + row * 25, 60));
        for (int row = 0; row < 40; row++)
            read.Add(Line($"Párrafo {row} del informe, una frase larga que ocupa el ancho del panel principal", 420, 40 + row * 25, 1400));
        var leftOut = new List<WindowsVisibleOcrLocator.LayoutLine>();

        IReadOnlyList<WindowsVisibleOcrLocator.LayoutLine> kept =
            WindowsVisibleOcrLocator.Listed(read, 60, static _ => false, Width, tail: false, leftOut);

        Assert.Multiple(() =>
        {
            Assert.That(kept, Has.Count.EqualTo(60));
            Assert.That(leftOut.Count(static line => line.X < 400), Is.EqualTo(10));
            Assert.That(leftOut.Count(static line => line.X >= 400), Is.EqualTo(10));
        });
    }

    [Test]
    public void BelowTheCapEverythingStays()
    {
        (List<WindowsVisibleOcrLocator.LayoutLine> read, HashSet<string> controls) = Conversation(10);
        var leftOut = new List<WindowsVisibleOcrLocator.LayoutLine>();

        IReadOnlyList<WindowsVisibleOcrLocator.LayoutLine> kept =
            WindowsVisibleOcrLocator.Listed(read, 60, controls.Contains, Width, tail: false, leftOut);

        Assert.Multiple(() =>
        {
            Assert.That(kept, Has.Count.EqualTo(read.Count));
            Assert.That(leftOut, Is.Empty);
        });
    }
}
