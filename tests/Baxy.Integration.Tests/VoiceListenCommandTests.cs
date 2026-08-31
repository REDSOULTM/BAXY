using System.Text.Json.Nodes;
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

    [Test]
    public void ListenTogglePublishesStructuredFactsNotCannedSpanish()
    {
        string on = MainWindowViewModel.VoiceListenVisibleFacts(true, true);
        string onFailed = MainWindowViewModel.VoiceListenVisibleFacts(true, false);
        string off = MainWindowViewModel.VoiceListenVisibleFacts(false, true);
        string offFailed = MainWindowViewModel.VoiceListenVisibleFacts(false, false);
        string source = File.ReadAllText(RepositoryPath("src", "Baxy.App", "MainWindowViewModel.cs"));

        Assert.Multiple(() =>
        {
            Assert.That(JsonNode.Parse(on)?["cause"]?.GetValue<string>(), Is.EqualTo("wake_listen_on"));
            Assert.That(JsonNode.Parse(on)?["kind"]?.GetValue<string>(), Is.EqualTo("status"));
            Assert.That(
                JsonNode.Parse(on)?["observed"]?["listening"]?.GetValue<bool>(),
                Is.True);
            Assert.That(
                JsonNode.Parse(onFailed)?["cause"]?.GetValue<string>(),
                Is.EqualTo("wake_listen_unavailable"));
            Assert.That(JsonNode.Parse(off)?["cause"]?.GetValue<string>(), Is.EqualTo("wake_listen_off"));
            Assert.That(
                JsonNode.Parse(offFailed)?["cause"]?.GetValue<string>(),
                Is.EqualTo("wake_listen_stop_failed"));
            Assert.That(on, Does.Not.Contain("Listo"));
            Assert.That(onFailed, Does.Not.Contain("No pude"));
            Assert.That(source, Does.Contain("VoiceListenVisibleFacts"));
            Assert.That(source, Does.Not.Contain("Listo, te escucho"));
            Assert.That(source, Does.Not.Contain("escucha permanente no está disponible"));
            Assert.That(source, Does.Not.Contain("ya no te escucho"));
            Assert.That(source, Does.Not.Contain("No pude apagar la escucha"));
        });
    }

    private static string RepositoryPath(params string[] path)
    {
        DirectoryInfo? current = new(TestContext.CurrentContext.TestDirectory);
        while (current is not null && !File.Exists(Path.Combine(current.FullName, "Baxy.slnx")))
        {
            current = current.Parent;
        }

        if (current is null)
        {
            throw new AssertionException("Could not locate the BAXY repository root.");
        }

        return path.Aggregate(current.FullName, Path.Combine);
    }
}
