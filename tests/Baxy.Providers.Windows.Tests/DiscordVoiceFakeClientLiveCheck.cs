using System.Diagnostics;
using System.Text;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Uso-128 on the real desktop against a local fake of the client with a voice channel and its panel. The fake must have a
/// process name of its own (BAXY_FAKE_VOICE_CLIENT): the adapter looks only for that name here, so a real client that is open,
/// perhaps in a call, is never reached. Explicit. What it cannot say: whether the real client's row and panel still read so.
/// </summary>
[TestFixture]
[Explicit("Opens a window of its own and types into it.")]
[Category("LiveDesktop")]
[NonParallelizable]
public sealed class DiscordVoiceFakeClientLiveCheck : IDisposable
{
    private const string Text = "Taller de ceramica";
    private const string Voice = "Sala de ensayo";
    private const string Server = "Gremio";
    private Process? _client;
    private string _folder = string.Empty;
    private UiaWorkerHost? _uia;
    private DesktopMessagingAdapter? _adapter;
    private string[]? _realNames;

    [OneTimeSetUp]
    public void Open()
    {
        string? fake = Environment.GetEnvironmentVariable("BAXY_FAKE_VOICE_CLIENT");
        if (string.IsNullOrWhiteSpace(fake))
            Assert.Ignore("BAXY_FAKE_VOICE_CLIENT is needed to touch the desktop.");
        string process = Path.GetFileNameWithoutExtension(fake);
        if (string.Equals(process, "Discord", StringComparison.OrdinalIgnoreCase))
            Assert.Ignore("The fake needs a process name of its own: a real client may be open.");
        _realNames = WindowsDesktopMessagingAutomation.DiscordProcesses;
        WindowsDesktopMessagingAutomation.DiscordProcesses = [process];
        _folder = Path.Combine(Path.GetTempPath(), "baxy-voz-falso-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(_folder);
        File.WriteAllText(
            Path.Combine(_folder, "chats.txt"),
            string.Join('\n', Text, "Ronaldo Perez", $"{Voice} (canal de voz), {Server}", $"Sala de ensayo chica (canal de voz), {Server}") + "\n",
            Encoding.UTF8);
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
        if (_realNames is not null)
            WindowsDesktopMessagingAutomation.DiscordProcesses = _realNames;
        TestContext.Out.WriteLine("eventos: " + Read("eventos.txt").Replace('\n', ';'));
        if (_folder.Length > 0)
            Directory.Delete(_folder, recursive: true);
    }

    [OneTimeTearDown]
    public void Close() => Dispose();

    private void Mode(string mode) => File.WriteAllText(Path.Combine(_folder, "modo.txt"), mode, Encoding.UTF8);

    private string Read(string file)
    {
        string path = Path.Combine(_folder, file);
        return File.Exists(path) ? File.ReadAllText(path, Encoding.UTF8).Trim() : string.Empty;
    }

    private async Task<ExternalCapabilityReceipt> Call(string name)
    {
        using JsonDocument arguments = JsonDocument.Parse(JsonSerializer.Serialize(new { client = "discord", name }));
        ExternalCapabilityReceipt receipt = await _adapter!.InvokeAsync("client.channel.open", arguments.RootElement, CancellationToken.None);
        TestContext.Out.WriteLine($"{name}: verified={receipt.Verified} error={receipt.ErrorCode} result={receipt.Result} switcher={Read("cambiador.txt")}");
        return receipt;
    }

    private async Task<ExternalCapabilityReceipt?> Peek(string name)
    {
        using JsonDocument arguments = JsonDocument.Parse(JsonSerializer.Serialize(new { client = "discord", name }));
        DesktopMessagingAdapter adapter = _adapter!;
        ExternalCapabilityReceipt? receipt = await adapter.PreflightAsync("client.channel.open", arguments.RootElement, CancellationToken.None);
        TestContext.Out.WriteLine($"peek {name}: needs={receipt?.NeedsConfirmation} result={receipt?.Result} switcher={Read("cambiador.txt")}");
        return receipt;
    }

    [Test, Order(1)]
    public async Task ATextChannelIsOpenedAsBeforeAndAsksNothing()
    {
        ExternalCapabilityReceipt? asked = await Peek(Text);
        ExternalCapabilityReceipt opened = await Call(Text);
        Assert.Multiple(() =>
        {
            Assert.That(asked, Is.Null);
            Assert.That(opened.Verified, Is.True, opened.ErrorCode);
            Assert.That(opened.Result?.TryGetProperty("voiceChannel", out _), Is.False);
            Assert.That(Read("activo.txt"), Is.EqualTo(Text));
            Assert.That(Read("cambiador.txt"), Is.EqualTo("cerrado"));
            Assert.That(Read("llamada_voz.txt"), Is.Empty);
        });
    }

    // The read before the yes: what it is, nothing pressed, the switcher closed.
    [Test, Order(2)]
    public async Task AVoiceChannelAsksAndNothingIsPressedBeforeTheYes()
    {
        ExternalCapabilityReceipt? asked = await Peek(Voice);
        Assert.Multiple(() =>
        {
            Assert.That(asked?.NeedsConfirmation, Is.True);
            Assert.That(asked?.Result?.GetProperty("server").GetString(), Is.EqualTo(Server));
            Assert.That(Read("llamada_voz.txt"), Is.Empty);
            Assert.That(Read("cambiador.txt"), Is.EqualTo("cerrado"));
            Assert.That(Read("activo.txt"), Is.EqualTo(Text));
        });
    }

    // Only the name asked for: «chica» is another channel's call. After the yes, the panel says it, and the microphone stays.
    [Test, Order(3)]
    public async Task AfterTheYesItEntersAndThePanelSaysIt()
    {
        string micBefore = Read("llamada.txt");
        ExternalCapabilityReceipt entered = await Call(Voice);
        Assert.Multiple(() =>
        {
            Assert.That(entered.Verified, Is.True, entered.ErrorCode);
            Assert.That(entered.Result?.GetProperty("voiceChannel").GetBoolean(), Is.True);
            Assert.That(entered.Result?.GetProperty("joined").GetBoolean(), Is.True);
            Assert.That(entered.Result?.GetProperty("voiceServer").GetString(), Is.EqualTo(Server));
            Assert.That(Read("llamada_voz.txt"), Is.EqualTo(Voice));
            Assert.That(Read("llamada.txt"), Is.EqualTo(micBefore));
            Assert.That(Read("cambiador.txt"), Is.EqualTo("cerrado"));
        });
    }

    // Already inside: nothing pressed, its state already reached; and it stays.
    [Test, Order(4)]
    public async Task InsideAlreadyPressesNothingAndStays()
    {
        string events = Read("eventos.txt");
        ExternalCapabilityReceipt again = await Call(Voice);
        Assert.Multiple(() =>
        {
            Assert.That(again.Verified, Is.True, again.ErrorCode);
            Assert.That(again.StateAlreadyReached, Is.True);
            Assert.That(again.Result?.GetProperty("joined").GetBoolean(), Is.True);
            Assert.That(Read("eventos.txt"), Is.EqualTo(events));
            Assert.That(Read("llamada_voz.txt"), Is.EqualTo(Voice));
        });
    }

    // A press the client ignores, with the focus gone out of the switcher: not «inside», and the switcher does not stay.
    [Test, Order(5)]
    public async Task APressThatDoesNothingIsNotInsideAndLeavesNoSwitcher()
    {
        Mode("clic_sin_efecto");
        await Task.Delay(300);
        ExternalCapabilityReceipt pressed = await Call("Sala de ensayo chica");
        Mode("normal");
        Assert.Multiple(() =>
        {
            Assert.That(pressed.Verified, Is.False);
            Assert.That(pressed.ErrorCode, Is.EqualTo(WindowsDesktopMessagingAutomation.VoiceJoinNotVerified));
            Assert.That(pressed.Result?.GetProperty("joined").GetString(), Is.EqualTo("unknown"));
            Assert.That(Read("cambiador.txt"), Is.EqualTo("cerrado"));
        });
    }

    [Test, Order(6)]
    public async Task AMisheardNameOffersTheCloseOneAndOpensNothing()
    {
        string active = Read("activo.txt");
        ExternalCapabilityReceipt said = await Call("Ronaldino");
        Assert.Multiple(() =>
        {
            Assert.That(said.Verified, Is.False);
            Assert.That(said.Result?.GetProperty("opened").GetBoolean(), Is.False);
            Assert.That(said.Result?.GetProperty("alike")[0].GetString(), Is.EqualTo("Ronaldo Perez"));
            Assert.That(Read("activo.txt"), Is.EqualTo(active));
            Assert.That(Read("cambiador.txt"), Is.EqualTo("cerrado"));
        });
    }

    [Test, Order(7)]
    public async Task ANameNothingLooksLikeSaysNotFound()
    {
        ExternalCapabilityReceipt said = await Call("Xilofonista");
        Assert.Multiple(() =>
        {
            Assert.That(said.Verified, Is.False);
            Assert.That(said.Result?.TryGetProperty("alike", out _), Is.False);
            Assert.That(Read("cambiador.txt"), Is.EqualTo("cerrado"));
        });
    }
}
