using System.Net;
using System.Text;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

// Renew al máximo (velocidad): pc-t2 asked the vision stage for «Guardar como» three times in a row on the same Notepad
// (45, 21 and 21 s, each vision_point_on_other_label). The same label on the same drawing of the same window gets the
// answer it got a moment ago, and the two questions of one click set the mind's slot aside once.
[NonParallelizable]
public sealed class VisionAnswerMemoryTests
{
    private const int Width = 128;
    private const int Height = 64;

    // A 32-bit bottom-up BMP of the window, every pixel grey but the rectangles painted.
    private static VisibleControlSurface.CapturedWindow Frame(
        string tag, nint hwnd = 7, params (int X, int Y, int W, int H, byte Shade)[] paint)
    {
        int stride = Width * 4;
        var bmp = new byte[54 + (stride * Height)];
        bmp[0] = (byte)'B';
        bmp[1] = (byte)'M';
        BitConverter.GetBytes(bmp.Length).CopyTo(bmp, 2);
        BitConverter.GetBytes(54).CopyTo(bmp, 10);
        BitConverter.GetBytes(40).CopyTo(bmp, 14);
        BitConverter.GetBytes(Width).CopyTo(bmp, 18);
        BitConverter.GetBytes(Height).CopyTo(bmp, 22);
        BitConverter.GetBytes((short)1).CopyTo(bmp, 26);
        BitConverter.GetBytes((short)32).CopyTo(bmp, 28);
        bmp.AsSpan(54).Fill(0x80);
        foreach ((int x, int y, int w, int h, byte shade) in paint)
        {
            for (int row = y; row < y + h; row++)
                bmp.AsSpan(54 + ((Height - 1 - row) * stride) + (x * 4), w * 4).Fill(shade);
        }

        return new VisibleControlSurface.CapturedWindow(hwnd, bmp, 0, 0, Width, Height, tag);
    }

    [Test]
    public void TheSameDrawingIsTheSameImageOrOnlyACaretApart()
    {
        VisibleControlSurface.CapturedWindow first = Frame("a");
        Assert.Multiple(() =>
        {
            Assert.That(VisionAnswerMemory.SameDrawing(first, Frame("a")), Is.True, "the same image");
            // A caret 2 px wide and 18 tall, across two cells one above the other.
            Assert.That(VisionAnswerMemory.SameDrawing(first, Frame("b", 7, (40, 24, 2, 18, 0x00))), Is.True, "a caret");
            Assert.That(VisionAnswerMemory.SameDrawing(first, Frame("c", 7, (2, 2, 8, 8, 0x00))), Is.True, "one cell");
            Assert.That(VisionAnswerMemory.SameDrawing(first, Frame("d", 7, (28, 10, 8, 8, 0x00))), Is.False,
                "two cells side by side");
            Assert.That(VisionAnswerMemory.SameDrawing(first, Frame("e", 7, (0, 0, 100, 40, 0x00))), Is.False, "redrawn");
            Assert.That(VisionAnswerMemory.SameDrawing(first, Frame("a", 8)), Is.False, "another window");
        });
    }

    [Test]
    public void AnAnswerIsRecalledOnlyForTheSameLabelWhileItIsFresh()
    {
        DateTime now = new(2026, 10, 23, 12, 0, 0, DateTimeKind.Utc);
        var memory = new VisionAnswerMemory(() => now);
        memory.Note("Guardar como", Frame("a"), "vision_point_on_other_label");

        bool same = memory.Recall("Guardar como", Frame("a"), out string? code);
        bool other = memory.Recall("Guardar", Frame("a"), out _);
        now += VisionAnswerMemory.KeptFor + TimeSpan.FromSeconds(1);
        bool stale = memory.Recall("Guardar como", Frame("a"), out _);
        memory.Note("Bloc de notas", Frame("a"), null);
        bool none = memory.Recall("Bloc de notas", Frame("a"), out string? noPlace);
        memory.Forget();
        bool forgotten = memory.Recall("Bloc de notas", Frame("a"), out _);

        Assert.Multiple(() =>
        {
            Assert.That(same, Is.True);
            Assert.That(code, Is.EqualTo("vision_point_on_other_label"));
            Assert.That(other, Is.False);
            Assert.That(stale, Is.False);
            Assert.That(none, Is.True);
            Assert.That(noPlace, Is.Null);
            Assert.That(forgotten, Is.False);
        });
    }

    // The two questions of one click (the second told which label it is not) set the slot aside once and put it back
    // once; asked again on the same drawing, nothing is sent and the answer is the same; on another drawing, it asks.
    [Test]
    public async Task OneClickHoldsTheSlotOnceAndARetryOnTheSameDrawingAsksNothing()
    {
        string slots = Path.Combine(Path.GetTempPath(), "baxy-vision-slots-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(slots);
        string?[] saved = [.. Names.Select(Environment.GetEnvironmentVariable)];
        try
        {
            Environment.SetEnvironmentVariable("BAXY_VISION_ENDPOINT", "http://127.0.0.1:8090/v1/chat/completions");
            Environment.SetEnvironmentVariable("BAXY_VISION_MODEL", "vision-test");
            Environment.SetEnvironmentVariable("BAXY_VISION_SLOT_DIR", slots);
            var handler = new Recording();
            using var http = new HttpClient(handler);
            VisibleControlSurface.CapturedWindow shown = Frame("a");
            var locator = new WindowsVisibleVisionLocator(
                http,
                _ => ValueTask.FromResult<VisibleControlSurface.CapturedWindow?>(shown),
                (_, _) => ValueTask.FromResult<IReadOnlyList<WindowsVisibleOcrLocator.LayoutLine>?>(
                    new WindowsVisibleOcrLocator.LayoutLine[]
                    {
                        new("Archivo", 10, 10, 40, 12, [new WindowsVisibleOcrLocator.LayoutWord("Archivo", 10, 10, 40, 12)]),
                    }));

            ExternalCapabilityReceipt? first = await locator.TryClickAsync(
                "input.visible.click", "Guardar como", null, CancellationToken.None);
            string[] firstCalls = [.. handler.Calls];
            handler.Calls.Clear();
            ExternalCapabilityReceipt? again = await locator.TryClickAsync(
                "input.visible.click", "Guardar como", null, CancellationToken.None);
            string[] againCalls = [.. handler.Calls];
            handler.Calls.Clear();
            shown = Frame("z", 7, (0, 0, 100, 40, 0x00));
            ExternalCapabilityReceipt? redrawn = await locator.TryClickAsync(
                "input.visible.click", "Guardar como", null, CancellationToken.None);

            Assert.Multiple(() =>
            {
                Assert.That(first?.ErrorCode, Is.EqualTo("vision_point_on_other_label"));
                Assert.That(first?.EffectMayHaveOccurred, Is.False);
                Assert.That(firstCalls, Is.EqualTo(new[] { "save", "ask", "ask", "restore" }));
                Assert.That(again?.ErrorCode, Is.EqualTo("vision_point_on_other_label"));
                Assert.That(again?.EffectMayHaveOccurred, Is.False);
                Assert.That(againCalls, Is.Empty);
                Assert.That(redrawn?.ErrorCode, Is.EqualTo("vision_point_on_other_label"));
                Assert.That(handler.Calls, Is.EqualTo(new[] { "save", "ask", "ask", "restore" }));
            });
        }
        finally
        {
            for (int index = 0; index < Names.Length; index++)
                Environment.SetEnvironmentVariable(Names[index], saved[index]);
            Directory.Delete(slots, recursive: true);
        }
    }

    [Test]
    public async Task AQuestionPastItsTimeIsAnHonestTimeoutAndTheSlotGoesBack()
    {
        // P2.17 (noche 27-10): the shared server busy with the mind, the question outlasted the client's time; the timeout
        // escaped as an exception (a bare provider failure) instead of saying what happened.
        string slots = Path.Combine(Path.GetTempPath(), "baxy-vision-slots-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(slots);
        string?[] saved = [.. Names.Select(Environment.GetEnvironmentVariable)];
        try
        {
            Environment.SetEnvironmentVariable("BAXY_VISION_ENDPOINT", "http://127.0.0.1:8090/v1/chat/completions");
            Environment.SetEnvironmentVariable("BAXY_VISION_MODEL", "vision-test");
            Environment.SetEnvironmentVariable("BAXY_VISION_SLOT_DIR", slots);
            var handler = new Recording { Stalls = true };
            using var http = new HttpClient(handler) { Timeout = TimeSpan.FromMilliseconds(200) };
            VisibleControlSurface.CapturedWindow shown = Frame("t");
            var locator = new WindowsVisibleVisionLocator(
                http,
                _ => ValueTask.FromResult<VisibleControlSurface.CapturedWindow?>(shown),
                (_, _) => ValueTask.FromResult<IReadOnlyList<WindowsVisibleOcrLocator.LayoutLine>?>([]));

            ExternalCapabilityReceipt? receipt = await locator.TryClickAsync(
                "input.visible.click", "Guardar como", null, CancellationToken.None);

            Assert.Multiple(() =>
            {
                Assert.That(receipt?.ErrorCode, Is.EqualTo("vision_provider_timeout"));
                Assert.That(receipt?.EffectMayHaveOccurred, Is.False);
                Assert.That(handler.Calls, Is.EqualTo(new[] { "save", "ask", "restore" }));
            });
        }
        finally
        {
            for (int index = 0; index < Names.Length; index++)
                Environment.SetEnvironmentVariable(Names[index], saved[index]);
            Directory.Delete(slots, recursive: true);
        }
    }

    private static readonly string[] Names = ["BAXY_VISION_ENDPOINT", "BAXY_VISION_MODEL", "BAXY_VISION_SLOT_DIR"];

    // The server: a slot saved and restored, and every question answered with a place on «Archivo» (or, stalled, never).
    private sealed class Recording : HttpMessageHandler
    {
        internal List<string> Calls { get; } = [];

        internal bool Stalls { get; init; }

        protected override async Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        {
            string query = request.RequestUri?.Query ?? "";
            string call = query.Contains("action=save", StringComparison.Ordinal) ? "save"
                : query.Contains("action=restore", StringComparison.Ordinal) ? "restore"
                : "ask";
            Calls.Add(call);
            if (Stalls && call == "ask")
                await Task.Delay(Timeout.Infinite, cancellationToken);
            string body = call == "ask"
                ? """{"choices":[{"message":{"content":"{\"bbox_2d\": [100, 200, 300, 300]}"}}]}"""
                : "{}";
            return new HttpResponseMessage(HttpStatusCode.OK)
            {
                Content = new StringContent(body, Encoding.UTF8, "application/json"),
            };
        }
    }
}
