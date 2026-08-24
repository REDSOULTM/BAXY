using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class VoiceListenCommandTests
{
    [TestCase("deja de escucharme", false)]
    [TestCase("Stop listening.", false)]
    [TestCase("escucha siempre", true)]
    [TestCase("activa la wake word", true)]
    [TestCase("start listening", true)]
    public void WholeUtteranceTogglesBaxyListenNotWindowsMic(string text, bool enable)
    {
        Assert.That(VoiceListenCommand.TryParse(text, out bool parsed), Is.True);
        Assert.That(parsed, Is.EqualTo(enable));
    }

    [TestCase("abre spotify")]
    [TestCase("silencia el micrófono")]
    [TestCase("deja de escucharme y abre steam")]
    public void OtherRequestsAreNotListenCommands(string text)
    {
        Assert.That(VoiceListenCommand.TryParse(text, out _), Is.False);
    }
}
