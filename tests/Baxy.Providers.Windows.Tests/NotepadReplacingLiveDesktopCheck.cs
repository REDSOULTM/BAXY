using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Práctica V5E061 on the real desktop: a text typed into a Notepad window and one part of it then replaced
/// (<c>replacing</c>) by the product's adapter, read back by window messages; an old text that is not there, or is there
/// more than once, changes nothing. Never runs in a suite: Explicit, BAXY_REPLACING_LIVE=1 and BAXY_REPLACING_WINDOW (the
/// handle of a Notepad window of a fresh temporary file, which the caller opens and closes without saving:
/// %TEMP%/claude/nb/cien/inv/reemplazo_vivo.ps1).
/// </summary>
[TestFixture]
[Explicit("Types into a Notepad window on the person's desktop.")]
[Category("LiveDesktop")]
public sealed class NotepadReplacingLiveDesktopCheck
{
    [Test]
    public async Task APartOfATextTypedIntoNotepadIsReplacedAndReadBack()
    {
        _ = long.TryParse(Environment.GetEnvironmentVariable("BAXY_REPLACING_WINDOW"), out long handle);
        if (Environment.GetEnvironmentVariable("BAXY_REPLACING_LIVE") != "1" || handle <= 0)
            Assert.Ignore("BAXY_REPLACING_LIVE=1 and BAXY_REPLACING_WINDOW are needed to touch the desktop.");
        using var uia = new UiaWorkerHost();
        var adapter = new WindowsDesktopInteractionAdapter(new WindowsVisibleControlAdapter(uia));
        var messages = new WindowsFieldMessages();

        async Task<ExternalCapabilityReceipt> TypeAsync(string arguments)
        {
            using JsonDocument parsed = JsonDocument.Parse(arguments);
            ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
                "input.text.type", parsed.RootElement, CancellationToken.None);
            TestContext.Out.WriteLine(
                $"{arguments} -> verified={receipt.Verified} error={receipt.ErrorCode} result={receipt.Result}");
            return receipt;
        }

        string Held()
        {
            nint field = messages.FocusOf((nint)handle);
            string held = messages.Text(field, messages.TextLength(field)) ?? "(unread)";
            TestContext.Out.WriteLine($"field {field} holds «{held}»");
            return held.Replace("\r", string.Empty, StringComparison.Ordinal);
        }

        ExternalCapabilityReceipt typed = await TypeAsync($$"""{"text":"reunión con Pedro el martes","window":{{handle}}}""");
        Assert.That(typed.Verified, Is.True, typed.ErrorCode);
        Assert.That(Held(), Is.EqualTo("reunión con Pedro el martes"));

        ExternalCapabilityReceipt replaced = await TypeAsync(
            $$"""{"text":"miércoles","replacing":"martes","window":{{handle}}}""");
        ExternalCapabilityReceipt absent = await TypeAsync(
            $$"""{"text":"viernes","replacing":"jueves","window":{{handle}}}""");
        ExternalCapabilityReceipt twice = await TypeAsync($$"""{"text":"a","replacing":"e","window":{{handle}}}""");

        Assert.Multiple(() =>
        {
            Assert.That(replaced.Verified, Is.True, replaced.ErrorCode);
            Assert.That(replaced.Result?.GetProperty("replaced").GetString(), Does.StartWith("«martes» was replaced"));
            Assert.That(absent.ErrorCode, Is.EqualTo("input_text_replacing_not_found"));
            Assert.That(twice.ErrorCode, Is.EqualTo("input_text_replacing_ambiguous"));
            Assert.That(Held(), Is.EqualTo("reunión con Pedro el miércoles"));
        });
    }
}
