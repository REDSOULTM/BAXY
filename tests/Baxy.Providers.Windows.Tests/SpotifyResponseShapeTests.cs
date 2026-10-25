using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Revisión nb-q-apps2: a last line of the Spotify script that is JSON but not its object, or a success without the
/// client's process id, is a clear receipt (spotify_uia_response_unreadable), never an InvalidOperationException. The
/// script is a stub: nothing is pressed or played.
/// </summary>
[TestFixture]
public sealed class SpotifyResponseShapeTests
{
    [TestCase("\"listo\"")]
    [TestCase("[1,2]")]
    [TestCase("42")]
    public async Task ALastLineThatIsNotAnObjectIsUnreadable(string line)
    {
        ExternalCapabilityReceipt receipt = await PlayAsync("starting\n" + line);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo(SpotifyDesktopAdapter.ResponseUnreadable));
        });
    }

    [TestCase("""{"ok":true,"effectObserved":true,"title":"Billie Jean"}""")]
    [TestCase("""{"ok":true,"effectObserved":true,"title":"Billie Jean","processId":"42"}""")]
    [TestCase("""{"ok":true,"effectObserved":true,"title":"Billie Jean","processId":4.5}""")]
    public async Task ASuccessWithoutTheClientsProcessIsUnreadableAfterItsEffect(string line)
    {
        ExternalCapabilityReceipt receipt = await PlayAsync(line);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo(SpotifyDesktopAdapter.ResponseUnreadable));
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
        });
    }

    private static async Task<ExternalCapabilityReceipt> PlayAsync(string output)
    {
        string script = Path.Combine(Path.GetTempPath(), "baxy-spotify-shape", "SpotifyDesktopAutomation.ps1");
        Directory.CreateDirectory(Path.GetDirectoryName(script)!);
        File.WriteAllText(script, "# stub: never run");
        var adapter = new SpotifyDesktopAdapter(new StubRunner(output), script);
        return await adapter.InvokeAsync(
            "media.play.exact",
            JsonDocument.Parse("""{"provider":"spotify","title":"Billie Jean"}""").RootElement.Clone(),
            CancellationToken.None);
    }

    private sealed class StubRunner(string output) : IExternalProcessRunner
    {
        public ValueTask<ExternalProcessResult> RunAsync(
            string executable, IReadOnlyList<string> arguments, TimeSpan timeout, CancellationToken cancellationToken) =>
            ValueTask.FromResult(new ExternalProcessResult(0, output, ""));
    }
}
