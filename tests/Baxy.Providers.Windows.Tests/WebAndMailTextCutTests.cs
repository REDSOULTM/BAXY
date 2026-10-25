using System.Net;
using System.Text;
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

    // email.send: the subject taken from the text's opening was cut at 75 UTF-16 units; an emoji there was cut in two
    // and the mail went out with «�» in its subject.
    [Test]
    public async Task AMailSubjectTakenFromTheTextNeverCutsAnEmojiInTwo()
    {
        const string output = "{\"ok\":true,\"effectObserved\":true,\"sentEntryId\":\"entry\"," +
            "\"sentUtc\":\"2026-10-25T20:00:00Z\",\"sentTo\":[\"persona@example.com\"],\"subject\":\"s\"}";
        string temporary = Path.Combine(Path.GetTempPath(), "baxy-cut-" + Guid.NewGuid().ToString("N"));
        var runner = new CapturingProcessRunner(output);
        var adapter = new MicrosoftAccountAdapter(temporary, runner);
        string text = new string('a', 74) + Emoji + new string('b', 20);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "email.send",
            JsonSerializer.SerializeToElement(new { to = "persona@example.com", text }),
            CancellationToken.None);
        using JsonDocument input = JsonDocument.Parse(
            Encoding.UTF8.GetString(Convert.FromBase64String(runner.LastArguments[^1])));
        string subject = input.RootElement.GetProperty("subject").GetString()!;

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(subject, Does.Not.Contain("�"));
            Assert.That(subject, Is.EqualTo(new string('a', 74) + "…"));
            Assert.That(input.RootElement.GetProperty("text").GetString(), Is.EqualTo(text));
            // message.send.test's mail takes its subject the same way.
            Assert.That(MicrosoftAccountAdapter.SubjectFromText(new string('a', 74) + Emoji + new string('b', 20)),
                Is.EqualTo(new string('a', 74) + "…"));
            Assert.That(MicrosoftAccountAdapter.SubjectFromText(new string('a', 73) + Emoji + new string('b', 20)),
                Is.EqualTo(new string('a', 73) + Emoji + "…"));
            Assert.That(MicrosoftAccountAdapter.SubjectFromText("hola " + Emoji), Is.EqualTo("hola " + Emoji));
        });
    }

    // web.fetch: a page read in parts was cut at maximumCharacters and at offset, UTF-16 units: an emoji on the cut lost
    // both halves (each written as «�»), one at the end of a part and one at the start of the next.
    [Test]
    public async Task AWebPageReadInPartsNeverCutsAnEmojiInTwo()
    {
        string profile = Path.Combine(Path.GetTempPath(), "baxy-cut-" + Guid.NewGuid().ToString("N"));
        using var browser = new CdpBrowserSession(profile);
        using var http = new HttpClient(new PageHandler(
            "<html><body><p>" + new string('a', 499) + Emoji + new string('b', 400) + "</p></body></html>"));
        using var adapter = new WebBrowserAdapter(browser, http);

        ExternalCapabilityReceipt first = await adapter.InvokeAsync(
            "web.fetch",
            JsonSerializer.SerializeToElement(new { url = "https://largo.example.com/", maximumCharacters = 500 }),
            CancellationToken.None);
        int next = first.Result!.Value.GetProperty("nextOffset").GetInt32();
        ExternalCapabilityReceipt second = await adapter.InvokeAsync(
            "web.fetch",
            JsonSerializer.SerializeToElement(new { url = "https://largo.example.com/", maximumCharacters = 500, offset = next }),
            CancellationToken.None);
        // An offset between the two halves (the one the old cut gave) starts at the character's first half.
        ExternalCapabilityReceipt inside = await adapter.InvokeAsync(
            "web.fetch",
            JsonSerializer.SerializeToElement(new { url = "https://largo.example.com/", maximumCharacters = 500, offset = 500 }),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(first.Verified, Is.True, first.ErrorCode);
            string firstText = first.Result!.Value.GetProperty("text").GetString()!;
            Assert.That(firstText, Does.Not.Contain("�"));
            Assert.That(firstText, Is.EqualTo(new string('a', 499)));
            Assert.That(next, Is.EqualTo(499));
            string secondText = second.Result!.Value.GetProperty("text").GetString()!;
            Assert.That(secondText, Does.StartWith(Emoji + "b"));
            Assert.That(secondText, Does.Not.Contain("�"));
            Assert.That(inside.Result!.Value.GetProperty("offset").GetInt32(), Is.EqualTo(499));
            Assert.That(inside.Result!.Value.GetProperty("text").GetString(), Does.StartWith(Emoji));
        });
    }

    private sealed class PageHandler(string page) : HttpMessageHandler
    {
        protected override Task<HttpResponseMessage> SendAsync(
            HttpRequestMessage request, CancellationToken cancellationToken) =>
            Task.FromResult(new HttpResponseMessage(HttpStatusCode.OK)
            {
                Content = new StringContent(page, Encoding.UTF8, "text/html"),
            });
    }

    private sealed class CapturingProcessRunner(string output) : IExternalProcessRunner
    {
        internal string[] LastArguments { get; private set; } = [];

        public ValueTask<ExternalProcessResult> RunAsync(
            string executable, IReadOnlyList<string> arguments, TimeSpan timeout,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            LastArguments = arguments.ToArray();
            return ValueTask.FromResult(new ExternalProcessResult(0, output, ""));
        }
    }
}
