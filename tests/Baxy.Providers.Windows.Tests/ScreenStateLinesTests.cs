using Baxy.Providers.Windows.External;
using NUnit.Framework;
using Line = Baxy.Providers.Windows.External.WindowsVisibleOcrLocator.LayoutLine;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Encargo H2 (tandas redpc t3-c09, «fijate si los auriculares están conectados»: the OCR read «Conectado» alone, the
/// state of «Ethernet» in Configuración's banner, and the final said the headphones were connected): a line that only
/// says a connection state is read with the line it sits under, its device.
/// </summary>
[TestFixture]
public sealed class ScreenStateLinesTests
{
    [Test]
    public void TheStateUnderEthernetIsEthernetsAndNoOtherLinesState()
    {
        // Configuración's banner on redpc: «REDPC / B760M H / Cambiar nombre», and to its right «Ethernet / Conectado».
        Line[] read =
        [
            new("REDPC", 330, 100, 90, 22), new("Ethernet", 700, 100, 80, 18), new("B760M H", 330, 126, 80, 18),
            new("Conectado", 700, 122, 90, 18), new("Cambiar nombre", 330, 150, 120, 16),
        ];

        string[] texts = ScreenStateLines.Grouped(read).Select(line => line.Text).ToArray();

        Assert.That(texts, Is.EqualTo(new[] { "REDPC", "Ethernet", "B760M H", "Ethernet: Conectado", "Cambiar nombre" }));
    }

    [Test]
    public void HeadphonesReallyConnectedAreNamedWithTheirState()
    {
        // Contracase (the notebook with its headphones paired): the card's subtitle names the headphones' state.
        Line[] read = [new("WH-1000XM4", 400, 500, 120, 20), new("Conectado", 400, 524, 90, 18), new("Música", 400, 546, 60, 16)];

        Assert.That(ScreenStateLines.Grouped(read).Select(line => line.Text),
            Is.EqualTo(new[] { "WH-1000XM4", "WH-1000XM4: Conectado", "Música" }));
    }

    [Test]
    public void AStateWithNothingRightAboveItAndOtherLinesStayAsRead()
    {
        // Contracases: a state far below (another row), one not aligned on the left, and a line that only mentions
        // the word among others keep their own text.
        Line[] read =
        [
            new("Bluetooth", 100, 100, 90, 20), new("Conectado", 100, 200, 90, 18), new("Wi-Fi", 400, 300, 50, 20),
            new("Connected", 520, 322, 90, 18), new("Dispositivo conectado recientemente", 100, 400, 260, 18),
        ];

        Assert.That(ScreenStateLines.Grouped(read).Select(line => line.Text), Is.EqualTo(read.Select(line => line.Text)));
    }

    [Test]
    public void TheStatesComeFromData()
    {
        Assert.Multiple(() =>
        {
            Assert.That(ScreenStateLines.IsState("Conectado."), Is.True);
            Assert.That(ScreenStateLines.IsState("Not connected"), Is.True);
            Assert.That(ScreenStateLines.IsState("Ethernet"), Is.False);
        });
    }
}
