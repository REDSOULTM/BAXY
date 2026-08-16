using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class NaturalAudioRequestParserTests
{
    [TestCase("Pon el volumen del PC al 0%", 0)]
    [TestCase("bajá el volumen al 20 por ciento", 20)]
    [TestCase("pon volumen 20", 20)]
    [TestCase("Pone el volumen del PC a 10.", 10)]
    [TestCase("sube el volumen al 50 porfa", 50)]
    [TestCase("volumen al 35 por ciento", 35)]
    [TestCase("set the pc volume to 20", 20)]
    [TestCase("change volume to 65", 65)]
    [TestCase("drop the volume to 20", 20)]
    [TestCase("turn the volume down to 15", 15)]
    [TestCase("make it 44 percent volume", 44)]
    [TestCase("Pon el volumen del pc 20", 20)]
    [TestCase("volume to 33", 33)]
    [TestCase("volume a 56", 56)]
    [TestCase("volume al 78", 78)]
    [TestCase("Cambia volumen al 25 y verifica", 25)]
    [TestCase("no, mejor pon el volumen a 30", 30)]
    [TestCase("subí el volumen al máximo", 100)]
    [TestCase("pon el volumen al maximo", 100)]
    [TestCase("poné el volumen al mínimo", 0)]
    [TestCase("pon el volumen del pc al minimo", 0)]
    [TestCase("pon el volumen a la mitad", 50)]
    [TestCase("baja el volumen a la mitad", 50)]
    [TestCase("pon el volumen del PC a diez", 10)]
    [TestCase("pon el volumen del PC a diez por ciento", 10)]
    [TestCase("pon el volumen del PC a veinte por ciento", 20)]
    public void ExplicitAbsoluteVolumeRoutesWithOneIntegerArgument(
        string text,
        int expectedLevel)
    {
        bool parsed = NaturalNoteRequestParser.TryParse(text, out RoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.True, text);
            Assert.That(operation?.Name, Is.EqualTo("audio.volume"), text);
            Assert.That(operation?.Arguments["level"]?.GetValue<int>(), Is.EqualTo(expectedLevel), text);
            Assert.That(operation?.Arguments, Has.Count.EqualTo(1), text);
        });
    }

    [TestCase("¿Qué volumen tengo?")]
    [TestCase("show me the volume")]
    [TestCase("show me el volumen")]
    public void ExplicitStatusQueryRoutesAsOneReadOnlyOperation(string text)
    {
        bool parsed = NaturalNoteRequestParser.TryParse(text, out RoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.True, text);
            Assert.That(operation?.Name, Is.EqualTo("audio.status"), text);
            Assert.That(operation?.Arguments, Is.Empty, text);
        });
    }

    [TestCase("mute", true)]
    [TestCase("mute everything", true)]
    [TestCase("mute system porfa", true)]
    [TestCase("ponelo en mute", true)]
    [TestCase("Silencia el PC", true)]
    [TestCase("unmute", false)]
    [TestCase("unmute the sound please", false)]
    [TestCase("desmutea el pc", false)]
    [TestCase("Quita el mute del PC", false)]
    public void ExplicitGlobalOutputMuteRoutesWithOneBooleanArgument(
        string text,
        bool expectedState)
    {
        bool parsed = NaturalNoteRequestParser.TryParse(text, out RoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.True, text);
            Assert.That(operation?.Name, Is.EqualTo("audio.mute"), text);
            Assert.That(operation?.Arguments["state"]?.GetValue<bool>(), Is.EqualTo(expectedState), text);
            Assert.That(operation?.Arguments, Has.Count.EqualTo(1), text);
        });
    }

    [TestCase("Baja el volumen 10%")]
    [TestCase("sube el volumen 10 puntos")]
    [TestCase("subí un poco el volumen")]
    [TestCase("turn the volume down a bit")]
    [TestCase("Sube el volumen del reproductor")]
    [TestCase("subí el volumen de Spotify")]
    [TestCase("mute my mic in Discord")]
    [TestCase("en Discord apretá silenciar")]
    [TestCase("pausa la música")]
    [TestCase("pause the video")]
    [TestCase("déjalo sin sonido")]
    [TestCase("silencia las notificaciones")]
    [TestCase("si termina la canción, pon el volumen a 20")]
    [TestCase("if Spotify opens, set the volume to 20")]
    [TestCase("set the volume to 20 if possible")]
    [TestCase("abre Spotify, pon música y baja volumen a 20")]
    [TestCase("subí el volumen y decime qué fecha es")]
    [TestCase("no subas el volumen")]
    [TestCase("no pongas el volumen a 30")]
    [TestCase("silenciá el audio")]
    [TestCase("pon el volumen al maximo!!")]
    [TestCase("pon el volumen del pc a diez?!")]
    public void RelativeScopedMediaConditionalNegatedAndCompositeRequestsFailClosed(string text)
    {
        AssertFailsClosed(text);
    }

    [TestCase("no, mejor pon el volumen a 101")]
    [TestCase("no, mejor pon el volumen a -1")]
    [TestCase("no, mejor pon el volumen a 30.5")]
    [TestCase("no, mejor pon el volumen a treinta")]
    [TestCase("no, mejor pon el volumen a 30 y abre Spotify")]
    [TestCase("no, mejor pon el brillo a 30")]
    [TestCase("no, mejor mutea el pc")]
    public void AuditedCorrectionExceptionDoesNotBroadenTheGlobalNegationGuard(string text)
    {
        AssertFailsClosed(text);
    }

    [Test]
    public void MalformedUtf16FailsClosedWithoutThrowing()
    {
        string malformed = string.Concat("pon el volumen a 30", '\uD800');
        RoutedOperation? operation = null;
        bool parsed = true;

        Assert.DoesNotThrow(() =>
            parsed = NaturalNoteRequestParser.TryParse(malformed, out operation));
        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.False);
            Assert.That(operation, Is.Null);
        });
    }

    private static void AssertFailsClosed(string text)
    {
        bool parsed = NaturalNoteRequestParser.TryParse(text, out RoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.False, text);
            Assert.That(operation, Is.Null, text);
        });
    }
}
