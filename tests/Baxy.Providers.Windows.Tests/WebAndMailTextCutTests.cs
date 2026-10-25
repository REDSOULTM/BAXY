using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

// A text cut at a fixed number of UTF-16 units (a page read in parts, a mail's subject taken from its opening, a page's
// visible text sliced at its bound) can fall between the two halves of a character outside the BMP (an emoji).
[TestFixture]
public sealed class WebAndMailTextCutTests
{
    private const string Emoji = "\U0001F600";

    // browser.page.read (CDP): V8's JSON.stringify writes a lone surrogate (the slice at maximumCharacters cutting an
    // emoji in two, or one the page wrote itself) as a \udXXX escape, which System.Text.Json refuses to read as a
    // string: the ArgumentException escaped the adapter and the read failed as a provider failure.
    [Test]
    public void APageSnapshotWithALoneSurrogateIsReadWithTheReplacementCharacter()
    {
        CdpPageReadResult cut = CdpBrowserSession.ParsePageSnapshot(
            "page-1",
            6,
            """{"url":"https://example.com/","title":"Caras \ude00","text":"hola \ud83d","truncated":true,"readyState":"complete"}""");
        CdpPageReadResult whole = CdpBrowserSession.ParsePageSnapshot(
            "page-1",
            7,
            """{"url":"https://example.com/","title":"Caras","text":"hola 😀","truncated":false,"readyState":"complete"}""");
        CdpPageReadResult backslash = CdpBrowserSession.ParsePageSnapshot(
            "page-1",
            7,
            """{"url":"https://example.com/","title":"Caras","text":"a\\ud83d","truncated":false,"readyState":"complete"}""");

        Assert.Multiple(() =>
        {
            Assert.That(cut.Verified, Is.True, cut.ErrorCode);
            Assert.That(cut.Text, Is.EqualTo("hola �"));
            Assert.That(cut.Title, Is.EqualTo("Caras �"));
            Assert.That(cut.Truncated, Is.True);
            // A whole pair is the emoji, and an escaped backslash before «ud83d» is text, not an escape.
            Assert.That(whole.Text, Is.EqualTo("hola " + Emoji));
            Assert.That(backslash.Text, Is.EqualTo("a\\ud83d"));
        });
    }
}
