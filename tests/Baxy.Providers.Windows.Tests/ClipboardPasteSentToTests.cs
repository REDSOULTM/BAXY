using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// BAXY Renew cu (C18): a clipboard.paste with no app opened first went into the window in front (a mail draft) and the
/// reply named the app asked for. Its receipt now says which window took it (sentTo: title and program), read from the
/// script's own measure of the front before the keys. No window is touched.
/// </summary>
[TestFixture]
public sealed class ClipboardPasteSentToTests
{
    [Test]
    public void ThePasteSaysTheWindowInFrontThatTookIt()
    {
        int self = Environment.ProcessId;
        using JsonDocument script = JsonDocument.Parse(
            $$"""{"ok":true,"effectObserved":true,"action":"paste","foregroundTitleBefore":"Borrador - Correo","foregroundProcessIdBefore":{{self}}}""");

        (string Title, string Process)? sentTo = WindowsDesktopInteractionAdapter.PastedInto(script.RootElement);

        Assert.That(sentTo, Is.EqualTo(("Borrador - Correo", System.Diagnostics.Process.GetCurrentProcess().ProcessName)));
    }

    // The model still named the app asked for with sentTo there (PC, C18): with the aid paste_target_next the same fact
    // goes as a sentence; with the aids off only sentTo.
    [TestCase("all", true)]
    [TestCase("none", false)]
    public void ThePasteSaysAsASentenceTheOneWindowThatReceivedIt(string aids, bool said)
    {
        using IDisposable setting = Baxy.Providers.Windows.Infrastructure.ModelAids.Use(aids);
        using JsonDocument script = JsonDocument.Parse("""{"ok":true,"effectObserved":true,"action":"paste"}""");

        JsonElement receipt = WindowsDesktopInteractionAdapter.AsDelivered(script.RootElement, ("Steam", "steamwebhelper"));

        Assert.Multiple(() =>
        {
            Assert.That(receipt.GetProperty("sentTo").GetProperty("process").GetString(), Is.EqualTo("steamwebhelper"));
            Assert.That(receipt.GetProperty("delivered").GetBoolean(), Is.True);
            Assert.That(receipt.TryGetProperty("next", out JsonElement next), Is.EqualTo(said));
            if (said)
                Assert.That(next.GetString(), Is.EqualTo("it went into the window of Steam (steamwebhelper); no other application received it"));
        });
    }

    // Contracase: with no front measured (no window, or a process gone) nothing is said.
    [TestCase("""{"ok":true,"foregroundTitleBefore":"x","foregroundProcessIdBefore":0}""")]
    [TestCase("""{"ok":true}""")]
    public void WithNoFrontMeasuredNothingIsSaid(string json)
    {
        using JsonDocument script = JsonDocument.Parse(json);

        Assert.That(WindowsDesktopInteractionAdapter.PastedInto(script.RootElement), Is.Null);
    }
}
