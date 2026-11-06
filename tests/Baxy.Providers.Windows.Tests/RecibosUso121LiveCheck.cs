using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Banco de uso 05-11 (U40, S03), on the desktop with the bench's fictitious chat, a process of its own: the keyboard on the
/// window's menu bar makes a look read only its frame; «Enviar» is pressed on the empty box, with its file of what was sent as
/// the oracle, not the receipt's word. Never runs in a suite: Explicit, BAXY_RECIBOS_LIVE=1 and BAXY_CHAT_EXE (ChatPrueba.exe,
/// as lib_uso.ps1 builds it). Its window is closed by its exact process.
/// </summary>
[TestFixture]
[Explicit("Opens a window on the person's desktop and presses a key in it.")]
[Category("LiveDesktop")]
public sealed class RecibosUso121LiveCheck
{
    private const byte Alt = 0x12;
    private const uint KeyUp = 2;

    [Test]
    public async Task SendOnAnEmptyBoxFromALookAtTheFrameIsNotToldVerified()
    {
        string? exe = Environment.GetEnvironmentVariable("BAXY_CHAT_EXE");
        if (Environment.GetEnvironmentVariable("BAXY_RECIBOS_LIVE") != "1" || exe is null)
            Assert.Ignore("BAXY_RECIBOS_LIVE=1 and BAXY_CHAT_EXE are needed to touch the desktop.");
        string folder = Path.Combine(Path.GetTempPath(), "baxy-recibos-121-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(folder);
        string title = "Chat de prueba " + Guid.NewGuid().ToString("N")[..6];
        var utf8 = new UTF8Encoding(false);
        await File.WriteAllTextAsync(Path.Combine(folder, "chats.txt"), "Sala de prueba\nTaller de prueba", utf8);
        await File.WriteAllTextAsync(Path.Combine(folder, "titulo.txt"), title, utf8);
        var start = new ProcessStartInfo(exe) { UseShellExecute = false };
        start.ArgumentList.Add(folder);
        using Process chat = Process.Start(start) ?? throw new InvalidOperationException("the chat did not start");
        try
        {
            nint window = 0;
            for (int attempt = 0; attempt < 80 && window == 0; attempt++)
            {
                window = FindWindowW(null, title);
                if (window == 0)
                    await Task.Delay(250);
            }

            Assert.That(window, Is.Not.EqualTo((nint)0), "the window did not appear");
            await Task.Delay(800);
            TapAlt();
            _ = SetForegroundWindow(window);
            await Task.Delay(500);
            Assert.That(GetForegroundWindow(), Is.EqualTo(window), "another window holds the front: nothing was pressed");
            TapAlt();
            await Task.Delay(500);

            using var host = new UiaWorkerHost(Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1"));
            var adapter = new WindowsVisibleControlAdapter(host);
            using JsonDocument lookArguments = JsonDocument.Parse($$"""{"window":{{(long)window}},"includeText":true}""");
            ExternalCapabilityReceipt look = await adapter.InvokeAsync("input.visible.controls", lookArguments.RootElement, CancellationToken.None);
            TestContext.Out.WriteLine($"look: {look.Result}");
            using JsonDocument pressArguments = JsonDocument.Parse($$"""{"label":"Enviar","window":{{(long)window}}}""");
            ExternalCapabilityReceipt press = await adapter.InvokeAsync("input.visible.click", pressArguments.RootElement, CancellationToken.None);
            TestContext.Out.WriteLine($"press: {press.ErrorCode} {press.Result}");
            string sent = Path.Combine(folder, "enviados.txt");
            string[] Sent() => File.Exists(sent) ? [.. File.ReadAllLines(sent).Where(static line => line.Length > 0)] : [];
            string[] afterFirst = Sent();

            // With the focus off the menu a look reads the whole window: the same press on the same empty box.
            ExternalCapabilityReceipt lookAgain = await adapter.InvokeAsync("input.visible.controls", lookArguments.RootElement, CancellationToken.None);
            TestContext.Out.WriteLine($"look again: {lookAgain.Result}");
            ExternalCapabilityReceipt pressAgain = await adapter.InvokeAsync("input.visible.click", pressArguments.RootElement, CancellationToken.None);
            TestContext.Out.WriteLine($"press again: {pressAgain.ErrorCode} {pressAgain.Result}");
            string[] afterSecond = Sent();

            // Control: with text in the box the press sends, and it is told read back.
            var typing = new WindowsDesktopInteractionAdapter(adapter) { Scripts = host };
            int box = lookAgain.Result!.Value.GetProperty("controls").EnumerateArray()
                .First(static control => control.GetProperty("name").GetString() == "Escribe un mensaje").GetProperty("i").GetInt32();
            using JsonDocument typeArguments = JsonDocument.Parse($$"""{"text":"llego a las siete","window":{{(long)window}},"index":{{box}}}""");
            ExternalCapabilityReceipt typed = await typing.InvokeAsync("input.text.type", typeArguments.RootElement, CancellationToken.None);
            TestContext.Out.WriteLine($"typed: {typed.ErrorCode} {typed.Result}");
            ExternalCapabilityReceipt sentPress = await adapter.InvokeAsync("input.visible.click", pressArguments.RootElement, CancellationToken.None);
            TestContext.Out.WriteLine($"press with text: {sentPress.ErrorCode} {sentPress.Result}");
            string[] afterThird = Sent();

            static bool ToldReadBack(ExternalCapabilityReceipt receipt) => receipt.Verified && receipt.Result is { } result
                && OperationVisibleFacts.Verification("input.visible.click", result) == OperationVisibleFacts.VerificationReadback;
            Assert.Multiple(() =>
            {
                Assert.That(look.Result?.TryGetProperty("frameOnly", out _), Is.True, "the look read only the frame");
                Assert.That(afterFirst, Is.Empty, "the oracle: nothing went");
                Assert.That(ToldReadBack(press), Is.False, "a press that sent nothing is not told verified");
                Assert.That(afterSecond, Is.Empty, "the oracle: nothing went");
                Assert.That(ToldReadBack(pressAgain), Is.False, "from a whole look too");
                Assert.That(afterThird, Has.Length.EqualTo(1), "control: with text it went");
                Assert.That(ToldReadBack(sentPress), Is.True, "control: and it is told read back");
            });
        }
        finally
        {
            if (!chat.HasExited)
                chat.Kill();
            chat.WaitForExit(5000);
            Directory.Delete(folder, recursive: true);
        }
    }

    private static void TapAlt()
    {
        keybd_event(Alt, 0, 0, 0);
        keybd_event(Alt, 0, KeyUp, 0);
    }

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern nint FindWindowW(string? className, string title);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool SetForegroundWindow(nint window);

    [DllImport("user32.dll")]
    private static extern nint GetForegroundWindow();

    [DllImport("user32.dll")]
    private static extern void keybd_event(byte key, byte scan, uint flags, nuint extra);
}
