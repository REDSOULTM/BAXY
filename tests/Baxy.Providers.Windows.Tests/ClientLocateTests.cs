using System.Text;
using System.Text.Json;
using Baxy.Providers.Windows.Capture;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

// Uso real 05-11 (F46, F47, F48), what needs no desktop; the rest in ClientLocateFakeLiveCheck. Names invented.
[TestFixture]
[NonParallelizable]
public sealed class ClientLocateTests
{
    private sealed class Answering(string output) : IExternalProcessRunner
    {
        public IReadOnlyList<string> Arguments { get; private set; } = [];

        public ValueTask<ExternalProcessResult> RunAsync(
            string executable, IReadOnlyList<string> arguments, TimeSpan timeout, CancellationToken cancellationToken)
        {
            Arguments = arguments;
            return ValueTask.FromResult(new ExternalProcessResult(0, output, string.Empty));
        }
    }

    private static async Task<ExternalCapabilityReceipt> LocateAsync(IExternalProcessRunner runner, string name = "Sala Norte")
    {
        string scans = Path.Combine(Path.GetTempPath(), "baxy-locate-" + Guid.NewGuid().ToString("N"));
        var adapter = new WindowsDeviceControlAdapter(scans, scans, runner);
        using JsonDocument arguments = JsonDocument.Parse(JsonSerializer.Serialize(new { client = "discord", name }));
        return await adapter.InvokeAsync("client.channel.locate", arguments.RootElement, CancellationToken.None);
    }

    // F48: rows read without seeing the filter may be the recent ones: they say a name that is there, never one that is not.
    [Test]
    public async Task RowsThatMayBeTheRecentOnesNeverSayNotFound()
    {
        ExternalCapabilityReceipt receipt = await LocateAsync(new Answering(
            """{"ok":true,"unfiltered":true,"window":"x","items":["Tienda de pruebas","Club de lectura"]}"""));
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("client_quick_switcher_not_read"));
        });
    }

    [Test]
    public async Task RowsThatMayBeTheRecentOnesStillSayTheExactName()
    {
        ExternalCapabilityReceipt receipt = await LocateAsync(new Answering(
            """{"ok":true,"unfiltered":true,"window":"x","items":["Tienda de pruebas","Sala Norte, Canal de texto, Gremio"]}"""));
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result?.GetProperty("found").GetBoolean(), Is.True);
            Assert.That(receipt.Result?.GetProperty("server").GetString(), Is.EqualTo("Gremio"));
            Assert.That(receipt.Result?.GetProperty("switcherRows").GetArrayLength(), Is.EqualTo(1), "the recent ones are no list of results");
        });
    }

    // Held-out: a voice row's name is its own, in every form the client writes it; another's name, or a word of it, is not.
    [TestCase("Tertulia (canal de voz), Ateneo", "Tertulia", true, "voice", "Ateneo")]
    [TestCase("Tertulia (canal de voz)", "Tertulia", true, "voice", "")]
    [TestCase("Tertulia, Canal de voz, Ateneo", "Tertulia", true, "voice", "Ateneo")]
    [TestCase("Tertulia, Canal de texto, Ateneo", "Tertulia", true, "text", "Ateneo")]
    [TestCase("Tertulia (vieja)", "Tertulia", false, "", "")]
    [TestCase("Tertulia literaria (canal de voz), Ateneo", "Tertulia", false, "", "")]
    [TestCase("Almacén, Canal de texto, Tertulia", "Tertulia", false, "", "")]
    // Review R1: only the kind's own mark is set aside: what else a name holds in brackets or after a dash is that name's, so a
    // channel that does not exist is never confirmed out of another's first word.
    [TestCase("Tertulia (vieja) (canal de voz), Ateneo", "Tertulia", false, "", "")]
    [TestCase("Tertulia (vieja), Canal de voz, Ateneo", "Tertulia", false, "", "")]
    [TestCase("Tertulia — dos, Canal de voz, Ateneo", "Tertulia", false, "", "")]
    [TestCase("Tertulia (canal de voz antiguo), Ateneo", "Tertulia", false, "", "")]
    [TestCase("Tertulia (vieja) (canal de voz), Ateneo", "Tertulia vieja", true, "voice", "Ateneo")]
    [TestCase("Tertulia (vieja), Canal de voz, Ateneo", "Tertulia vieja", true, "voice", "Ateneo")]
    [TestCase("Tertulia — dos, Canal de voz, Ateneo", "Tertulia dos", true, "voice", "Ateneo")]
    // Review R1: a text channel with the letters of a kind in its name stays a text channel, with its own name and server.
    [TestCase("Tertulia (voz alta), Canal de texto, Ateneo", "Tertulia", false, "", "")]
    [TestCase("Compras (invoices), Canal de texto, Ateneo", "Compras", false, "", "")]
    [TestCase("Tertulia (canal de voz), Canal de texto, Ateneo", "Tertulia", false, "", "")]
    [TestCase("Tertulia (voz alta), Canal de texto, Ateneo", "Tertulia voz alta", true, "text", "Ateneo")]
    [TestCase("Compras (invoices), Canal de texto, Ateneo", "Compras invoices", true, "text", "Ateneo")]
    [TestCase("Tertulia, Contexto, Ateneo", "Tertulia", true, "contexto", "Ateneo")]
    // A blind review of R1's fix: a comma of a voice channel's name is the name's.
    [TestCase("Música, juegos (canal de voz), Ateneo", "Música", false, "", "")]
    [TestCase("Música, juegos, Canal de voz, Ateneo", "Música", false, "", "")]
    [TestCase("Música, juegos (canal de voz), Ateneo", "Música juegos", true, "voice", "Ateneo")]
    public async Task ARowsOwnNameIsTheOneAsked(string row, string name, bool found, string kind, string server)
    {
        ExternalCapabilityReceipt receipt = await LocateAsync(
            new Answering(JsonSerializer.Serialize(new { ok = true, window = "x", items = new[] { row } })), name);
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Result?.GetProperty("found").GetBoolean(), Is.EqualTo(found));
            Assert.That(receipt.Result?.GetProperty("channelKind").GetString(), Is.EqualTo(kind));
            Assert.That(receipt.Result?.GetProperty("server").GetString(), Is.EqualTo(server));
        });
    }

    // Review R1: the receipt names the channel with all of its own name.
    [TestCase("Tertulia (vieja) (canal de voz), Ateneo", "Tertulia vieja", "Tertulia (vieja)")]
    [TestCase("Tertulia — dos, Canal de voz, Ateneo", "Tertulia dos", "Tertulia — dos")]
    [TestCase("Tertulia (canal de voz), Ateneo", "Tertulia", "Tertulia")]
    public async Task TheReceiptSaysTheChannelsWholeName(string row, string name, string shown)
    {
        ExternalCapabilityReceipt receipt = await LocateAsync(
            new Answering(JsonSerializer.Serialize(new { ok = true, window = "x", items = new[] { row } })), name);
        Assert.That(receipt.Result?.GetProperty("channelName").GetString(), Is.EqualTo(shown));
    }

    // The filter seen with no row left: «not found», said as such.
    [Test]
    public async Task AFilterWithNoRowSaysNotFound()
    {
        ExternalCapabilityReceipt receipt = await LocateAsync(new Answering("""{"ok":true,"window":"x","items":[]}"""));
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result?.GetProperty("found").GetBoolean(), Is.False);
            Assert.That(receipt.Result?.GetProperty("switcherRows").GetArrayLength(), Is.Zero);
        });
    }

    // F47: the script is told whether this turn's opening asked for the client; only an opening of the client's own process.
    [Test]
    public async Task TheLookIsToldWhetherThisTurnOpenedTheClient()
    {
        string own = System.Diagnostics.Process.GetCurrentProcess().ProcessName;
        string[] real = WindowsDesktopMessagingAutomation.DiscordProcesses;
        const string Answer = """{"ok":true,"window":"x","items":["Otra sala"]}""";
        try
        {
            _ = VisibleControlSurface.TakeOpened(TimeSpan.FromHours(1));
            WindowsDesktopMessagingAutomation.DiscordProcesses = [own];
            var nothingOpened = new Answering(Answer);
            _ = await LocateAsync(nothingOpened);

            VisibleControlSurface.NoteOpened(Environment.ProcessId, launched: true);
            var clientOpened = new Answering(Answer);
            _ = await LocateAsync(clientOpened);

            WindowsDesktopMessagingAutomation.DiscordProcesses = ["ClienteQueNoEsEste"];
            var otherOpened = new Answering(Answer);
            _ = await LocateAsync(otherOpened);

            Assert.Multiple(() =>
            {
                Assert.That(nothingOpened.Arguments[^1], Is.EqualTo("0"));
                Assert.That(nothingOpened.Arguments[^2], Is.EqualTo(own));
                Assert.That(clientOpened.Arguments[^1], Is.EqualTo("1"));
                Assert.That(otherOpened.Arguments[^1], Is.EqualTo("0"));
                Assert.That(otherOpened.Arguments[^2], Is.EqualTo("ClienteQueNoEsEste"));
            });
        }
        finally
        {
            _ = VisibleControlSurface.TakeOpened(TimeSpan.FromHours(1));
            WindowsDesktopMessagingAutomation.DiscordProcesses = real;
        }
    }

    private static WindowImage Frame(string name) => new(1, 1, Encoding.ASCII.GetBytes(name), name);

    private static (WindowImage? Image, long Ms, int Draws) Settle(params object[] frames)
    {
        long now = 0;
        int draws = 0;
        WindowImage image = VisibleControlSurface.SettledDrawing(
            () =>
            {
                object frame = frames[Math.Min(draws, frames.Length - 1)];
                draws++;
                return frame as WindowImage ?? throw new IOException("no frame");
            },
            ms => now += ms,
            () => now);
        return (image, now, draws);
    }

    // F46: measured on a real Chromium window: an empty frame first, the page within 94 ms.
    [Test]
    public void AWindowJustShownIsReadOnceItsDrawingStopsChanging()
    {
        (WindowImage? image, long ms, int draws) = Settle(Frame("vacio"), Frame("pagina"), Frame("pagina"));
        Assert.Multiple(() =>
        {
            Assert.That(image?.Sha256, Is.EqualTo("pagina"));
            Assert.That(draws, Is.EqualTo(3));
            Assert.That(ms, Is.EqualTo(350));
        });
    }

    [Test]
    public void ADrawingAlreadyFinalCostsOneMoreLook()
    {
        (WindowImage? image, long ms, _) = Settle(Frame("pagina"), Frame("pagina"));
        Assert.Multiple(() =>
        {
            Assert.That(image?.Sha256, Is.EqualTo("pagina"));
            Assert.That(ms, Is.EqualTo(250));
        });
    }

    // A video never stops changing: taken as it is at the bound.
    [Test]
    public void ADrawingThatKeepsChangingIsTakenAtTheBound()
    {
        (WindowImage? image, long ms, _) = Settle(Frame("a"), Frame("b"), Frame("c"), Frame("d"), Frame("e"), Frame("f"), Frame("g"), Frame("h"));
        Assert.Multiple(() =>
        {
            Assert.That(image?.Sha256, Is.EqualTo("f"));
            Assert.That(ms, Is.EqualTo(650));
        });
    }

    // A frame that comes back black is no frame: the next one counts; with none at all the capture fails as it did.
    [Test]
    public void ABlackFrameIsWaitedOutAndNoFrameAtAllFails()
    {
        var failure = new IOException("no frame");
        (WindowImage? image, _, _) = Settle(failure, Frame("pagina"), Frame("pagina"));
        Assert.Multiple(() =>
        {
            Assert.That(image?.Sha256, Is.EqualTo("pagina"));
            Assert.Throws<IOException>(() => Settle(failure));
        });
    }

    // A last frame lost at the bound leaves the one before it.
    [Test]
    public void AFrameLostAtTheBoundLeavesTheOneBefore()
    {
        var failure = new IOException("no frame");
        (WindowImage? image, _, _) = Settle(Frame("a"), Frame("b"), Frame("c"), Frame("d"), Frame("e"), failure);
        Assert.That(image?.Sha256, Is.EqualTo("e"));
    }
}
