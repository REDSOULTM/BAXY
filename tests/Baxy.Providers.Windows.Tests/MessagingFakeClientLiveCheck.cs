using System.Diagnostics;
using System.Text;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// F1, G5 and G6 on the real desktop against a local fake of the client (a window of the test's own, compiled as the client's
/// process name, no network, no account): the real automation types, reads the title and the pixels, and the receipts
/// are compared with what the fake received. Refuses to run with a real client open. Explicit, and needs
/// BAXY_FAKE_CLIENT=path of the fake's executable. What it cannot say: whether the real client's layout still fits.
/// </summary>
[TestFixture]
[Explicit("Opens a window of its own and types into it.")]
[Category("LiveDesktop")]
[NonParallelizable]
public sealed class MessagingFakeClientLiveCheck : IDisposable
{
    private const string Mine = "Taller de ceramica";
    private const string Other = "Club de lectura";
    private Process? _client;
    private string _folder = string.Empty;
    private UiaWorkerHost? _uia;
    private DesktopMessagingAdapter? _adapter;

    [OneTimeSetUp]
    public void Open()
    {
        string? fake = Environment.GetEnvironmentVariable("BAXY_FAKE_CLIENT");
        if (string.IsNullOrWhiteSpace(fake))
            Assert.Ignore("BAXY_FAKE_CLIENT is needed to touch the desktop.");
        foreach (Process running in Process.GetProcessesByName(Path.GetFileNameWithoutExtension(fake)))
        {
            using (running)
            {
                if (!string.Equals(running.MainModule?.FileName, fake, StringComparison.OrdinalIgnoreCase))
                    Assert.Ignore("A real client is open: nothing runs.");
            }
        }

        // Read as a Windows without Tesseract does (BAXY's packages do not bring it).
        if (Environment.GetEnvironmentVariable("BAXY_FAKE_CLIENT_NO_TESSERACT") == "1")
            WindowsDesktopMessagingAutomation.TesseractLookup = () => null;
        _folder = Path.Combine(Path.GetTempPath(), "baxy-cliente-falso-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(_folder);
        File.WriteAllText(Path.Combine(_folder, "chats.txt"), Mine + "\n" + Other + "\n", Encoding.UTF8);
        Mode("normal");
        _client = Process.Start(new ProcessStartInfo(fake, '"' + _folder + '"') { UseShellExecute = false })!;
        for (int attempt = 0; attempt < 40 && _client.MainWindowHandle == 0; attempt++)
        {
            Thread.Sleep(250);
            _client.Refresh();
        }

        Assert.That(_client.MainWindowHandle, Is.Not.EqualTo(0));
        _uia = new UiaWorkerHost(Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1"));
        var probe = new UiaClientInteractionProbe(_uia);
        // In the product the core warms this worker at its start; a read before that goes unanswered and nothing is pressed.
        for (int attempt = 0; attempt < 120; attempt++)
        {
            if (probe.ReadAsync(_client.MainWindowHandle, content: false, CancellationToken.None).AsTask().GetAwaiter().GetResult().Answered)
                break;
            Thread.Sleep(250);
        }

        _adapter = new DesktopMessagingAdapter(probe);
    }

    public void Dispose()
    {
        _adapter?.Dispose();
        _uia?.Dispose();
        if (_client is { HasExited: false })
            _client.Kill();
        _client?.Dispose();
        TestContext.Out.WriteLine("eventos: " + Read("eventos.txt").Replace('\n', ';'));
        if (_folder.Length > 0)
            Directory.Delete(_folder, recursive: true);
    }

    private void Mode(string mode) => File.WriteAllText(Path.Combine(_folder, "modo.txt"), mode, Encoding.UTF8);

    private string Read(string name)
    {
        string path = Path.Combine(_folder, name);
        return File.Exists(path) ? File.ReadAllText(path, Encoding.UTF8) : string.Empty;
    }

    private async Task<ExternalCapabilityReceipt> Call(string operation, string json)
    {
        using JsonDocument arguments = JsonDocument.Parse(json);
        ExternalCapabilityReceipt receipt = await _adapter!.InvokeAsync(operation, arguments.RootElement, CancellationToken.None);
        TestContext.Out.WriteLine($"{operation}: verified={receipt.Verified} error={receipt.ErrorCode} result={receipt.Result}");
        return receipt;
    }

    private static string Send(string recipient, string text) =>
        JsonSerializer.Serialize(new { channel = "discord", recipient, text });

    [Test, Order(1)]
    public async Task G6_AConversationIsOpenedByNameAndNothingIsTyped()
    {
        ExternalCapabilityReceipt opened = await Call(
            "client.channel.open", JsonSerializer.Serialize(new { client = "discord", name = Other }));

        Assert.Multiple(() =>
        {
            Assert.That(opened.Verified, Is.True, opened.ErrorCode);
            Assert.That(Read("activo.txt"), Is.EqualTo(Other));
            Assert.That(Read("enviados.txt"), Is.Empty);
        });
    }

    [Test, Order(2)]
    public async Task G6_AnAbsentNameOpensNothing()
    {
        ExternalCapabilityReceipt opened = await Call(
            "client.channel.open", JsonSerializer.Serialize(new { client = "discord", name = "Nadie con ese nombre" }));

        Assert.Multiple(() =>
        {
            Assert.That(opened.Verified, Is.False);
            Assert.That(Read("activo.txt"), Is.EqualTo(Other));
        });
    }

    [Test, Order(3)]
    public async Task F1_ASentMessageIsReadBackAndSaidSent()
    {
        Mode("normal");
        ExternalCapabilityReceipt sent = await Call("message.send", Send(Mine, "Llego a las siete al taller"));

        Assert.Multiple(() =>
        {
            Assert.That(sent.Verified, Is.True, sent.ErrorCode);
            Assert.That(Read("enviados.txt"), Does.Contain(Mine + "\tLlego a las siete al taller"));
        });
    }

    [Test, Order(4)]
    public async Task F1_ADraftThatNeverShowsStopsBeforeEnterAndSaysNotSent()
    {
        Mode("sin_borrador");
        string before = Read("enviados.txt");
        ExternalCapabilityReceipt sent = await Call("message.send", Send(Mine, "Este texto nunca se dibuja"));

        Assert.Multiple(() =>
        {
            Assert.That(sent.Verified, Is.False);
            Assert.That(sent.Result?.GetProperty("sent").GetBoolean(), Is.False);
            Assert.That(sent.Result?.GetProperty("enterPressed").GetBoolean(), Is.False);
            Assert.That(sent.Result?.GetProperty("stoppedAt").GetString(), Is.EqualTo("draft_check"));
            Assert.That(Read("enviados.txt"), Is.EqualTo(before));
        });
    }

    [Test, Order(20)]
    public async Task F1_AChatThatChangesAfterTheDraftStopsBeforeEnterAndSaysNotSent()
    {
        Mode("cambia_chat");
        string before = Read("enviados.txt");
        ExternalCapabilityReceipt sent = await Call("message.send", Send(Mine, "Este texto no sale al chat que cambia"));

        Assert.Multiple(() =>
        {
            Assert.That(sent.Verified, Is.False);
            Assert.That(sent.Result?.GetProperty("sent").GetBoolean(), Is.False);
            Assert.That(sent.Result?.GetProperty("stoppedAt").GetString(), Does.StartWith("chat_check"));
            Assert.That(Read("enviados.txt"), Is.EqualTo(before));
        });
    }

    [Test, Order(5)]
    public async Task F1_EnterWithoutTheMessageShownIsNotSaidSent()
    {
        Mode("normal");
        _ = await Call("client.channel.open", JsonSerializer.Serialize(new { client = "discord", name = Mine }));
        Mode("sin_entrega");
        string before = Read("enviados.txt");
        ExternalCapabilityReceipt sent = await Call("message.send", Send(Mine, "Este texto se pierde tras el Enter"));

        Assert.Multiple(() =>
        {
            Assert.That(sent.Verified, Is.False);
            Assert.That(sent.Result?.GetProperty("enterPressed").GetBoolean(), Is.True);
            Assert.That(sent.Result?.GetProperty("sent").GetString(), Is.EqualTo("unknown"));
            Assert.That(Read("enviados.txt"), Is.EqualTo(before));
        });
    }

    // Uso real 2026-11-05 (G3): the message reached the chat and BAXY could not say so, as OCR read its line broken by what
    // lies beside it; UI Automation has it whole. The bubble here is drawn so that only UI Automation can read it.
    [Test, Order(8)]
    public async Task F1_AMessageInTheChatThatOcrCannotReadIsSaidSent()
    {
        Mode("burbuja_ilegible");
        await Task.Delay(300);
        ExternalCapabilityReceipt sent = await Call("message.send", Send(Mine, "Hoy llego un poco antes al taller"));

        Assert.Multiple(() =>
        {
            Assert.That(sent.Verified, Is.True, sent.ErrorCode);
            Assert.That(Read("enviados.txt"), Does.Contain(Mine + "\tHoy llego un poco antes al taller"));
        });
    }

    // The other way: the words anywhere else, or no new bubble, are never «sent».
    [TestCase("sin_entrega", "Esto no llega nunca al chat")]
    [TestCase("solo_vista_previa", "Esto queda solo en la vista previa")]
    [TestCase("viejo_sin_entrega", "Este mensaje ya estaba en la conversacion")]
    [Order(9)]
    public async Task F1_NoNewMessageInTheChatIsNeverSaidSent(string mode, string text)
    {
        Mode(mode);
        await Task.Delay(500);
        ExternalCapabilityReceipt sent = await Call("message.send", Send(Mine, text));

        Assert.Multiple(() =>
        {
            Assert.That(sent.Verified, Is.False);
            Assert.That(sent.ErrorCode, Is.EqualTo("message_delivery_not_verified"));
            Assert.That(sent.Result!.Value.GetProperty("sent").GetString(), Is.EqualTo("unknown"));
            Assert.That(Read("enviados.txt"), Does.Not.Contain(text));
        });
    }

    // An old message with the same words: the new one counts, the old one alone does not (the case above).
    [Test, Order(10)]
    public async Task F1_ANewMessageBesideAnOldOneWithTheSameWordsIsSaidSent()
    {
        Mode("viejo_y_nueva");
        await Task.Delay(500);
        ExternalCapabilityReceipt sent = await Call("message.send", Send(Mine, "Este mensaje ya estaba en la conversacion"));

        Assert.That(sent.Verified, Is.True, sent.ErrorCode);
    }

    // Seen in the chat, but the chat on the screen is no longer the recipient's by then.
    [Test, Order(11)]
    public async Task F1_AChatThatIsNoLongerTheRecipientsIsNotSaidSent()
    {
        Mode("otro_chat");
        await Task.Delay(300);
        ExternalCapabilityReceipt sent = await Call("message.send", Send(Mine, "Otro mensaje para el taller de hoy"));

        Assert.Multiple(() =>
        {
            Assert.That(sent.Verified, Is.False);
            Assert.That(sent.Result!.Value.GetProperty("recipientStillShown").GetBoolean(), Is.False);
        });
    }

    [Test, Order(21)]
    public async Task G5_DeafenSwitchesTheClientsButtonAndSaysBothStates()
    {
        var adapter = new WindowsDeviceControlAdapter(_folder, _folder);
        async Task<ExternalCapabilityReceipt> Deafen(bool on)
        {
            using JsonDocument arguments = JsonDocument.Parse(JsonSerializer.Serialize(new { client = "discord", deafened = on }));
            ExternalCapabilityReceipt receipt = await adapter.InvokeAsync("client.deafen.set", arguments.RootElement, CancellationToken.None);
            TestContext.Out.WriteLine($"deafen {on}: verified={receipt.Verified} error={receipt.ErrorCode} result={receipt.Result} client={Read("llamada.txt")}");
            return receipt;
        }

        ExternalCapabilityReceipt on = await Deafen(true);
        string afterOn = Read("llamada.txt");
        ExternalCapabilityReceipt again = await Deafen(true);
        ExternalCapabilityReceipt off = await Deafen(false);

        Assert.Multiple(() =>
        {
            Assert.That(on.Verified, Is.True, on.ErrorCode);
            Assert.That(afterOn, Is.EqualTo("micro=1 sordo=1"));
            Assert.That(again.Verified, Is.True, again.ErrorCode);
            Assert.That(off.Verified, Is.True, off.ErrorCode);
            Assert.That(Read("llamada.txt"), Is.EqualTo("micro=0 sordo=0"));
        });
    }
}
