using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// client.channel.open against the real client on this desktop, with no model: BAXY_REAL_CHAT_CLIENT (whatsapp, discord)
/// and BAXY_REAL_CHAT_NAME say which chat, the one its owner allowed; nothing is typed in a chat and nothing is sent.
/// Prints only the code and the booleans (names read by the client are private). Explicit.
/// </summary>
[TestFixture]
[Explicit("Drives a real messaging client: opens one chat by name.")]
[Category("LiveDesktop")]
[NonParallelizable]
public sealed class MessagingRealClientLiveCheck
{
    [Test]
    public async Task OpensTheOneChatItWasToldTo()
    {
        string? client = Environment.GetEnvironmentVariable("BAXY_REAL_CHAT_CLIENT");
        string? name = Environment.GetEnvironmentVariable("BAXY_REAL_CHAT_NAME");
        if (string.IsNullOrWhiteSpace(client) || string.IsNullOrWhiteSpace(name))
            Assert.Ignore("BAXY_REAL_CHAT_CLIENT and BAXY_REAL_CHAT_NAME are needed.");

        using var uia = new UiaWorkerHost(Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1"));
        await uia.PrewarmAsync(CancellationToken.None);
        using var adapter = new DesktopMessagingAdapter(new UiaClientInteractionProbe(uia));
        using JsonDocument arguments = JsonDocument.Parse(JsonSerializer.Serialize(new { client, name }));
        var clock = System.Diagnostics.Stopwatch.StartNew();
        ExternalCapabilityReceipt opened = await adapter.InvokeAsync("client.channel.open", arguments.RootElement, CancellationToken.None);
        bool? clientOpened = opened.Result is { } result && result.TryGetProperty("clientOpened", out JsonElement started)
            ? started.GetBoolean()
            : null;
        TestContext.Out.WriteLine(
            $"verified={opened.Verified} error={opened.ErrorCode} effect={opened.EffectObserved} clientOpened={clientOpened} "
            + $"{Shape(opened)} ms={clock.ElapsedMilliseconds}");
        if (opened.Result is { } shown && shown.TryGetProperty("openedRow", out JsonElement row)
            && shown.TryGetProperty("headerRead", out JsonElement header) && header.GetArrayLength() > 0)
        {
            string rowText = row.GetString() ?? string.Empty;
            string title = header[0].GetString() ?? string.Empty;
            TestContext.Out.WriteLine($"verified=shape row={Masked(rowText, name!)} title={Masked(title, name!)}");
        }
        Assert.That(opened.Verified, Is.True, opened.ErrorCode);
    }

    // A read, nothing sent: how many times the text is in the open chat's conversation (BAXY_REAL_CHAT_TEXT).
    [Test]
    public async Task CountsTheTextInTheOpenChat()
    {
        string? client = Environment.GetEnvironmentVariable("BAXY_REAL_CHAT_CLIENT");
        string? text = Environment.GetEnvironmentVariable("BAXY_REAL_CHAT_TEXT");
        if (string.IsNullOrWhiteSpace(client) || string.IsNullOrWhiteSpace(text))
            Assert.Ignore("BAXY_REAL_CHAT_CLIENT and BAXY_REAL_CHAT_TEXT are needed.");

        string process = client == "whatsapp" ? "WhatsApp.Root" : "Discord";
        using System.Diagnostics.Process window = System.Diagnostics.Process.GetProcessesByName(process)
            .First(candidate => candidate.MainWindowHandle != 0);
        using var uia = new UiaWorkerHost(Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1"));
        await uia.PrewarmAsync(CancellationToken.None);
        var probe = new ContentWindowProbe(new UiaClientInteractionProbe(uia));
        IReadOnlyList<ScreenBox> places = await probe.ShownNameBoxesAsync(window.MainWindowHandle, text, CancellationToken.None);
        TestContext.Out.WriteLine($"verified=shape lugares={places.Count} lefts={string.Join(',', places.Select(place => place.Left))}");
        Assert.That(places, Is.Not.Empty);
    }

    // A text with its letters and digits hidden and the chat asked for marked: only its form.
    private static string Masked(string text, string name) =>
        new string(text.Replace(name, "", StringComparison.OrdinalIgnoreCase)
            .Select(character => char.IsLetter(character) ? 'x' : char.IsDigit(character) ? '9' : character).ToArray())
            .Replace("", "[contacto]", StringComparison.Ordinal);

    // Which parts the receipt holds and how many items, never their text.
    private static string Shape(ExternalCapabilityReceipt receipt) =>
        receipt.Result is not { ValueKind: JsonValueKind.Object } result
            ? "result=none"
            : string.Join(' ', result.EnumerateObject().Select(part => part.Value.ValueKind switch
            {
                JsonValueKind.Array => $"{part.Name}[{part.Value.GetArrayLength()}]",
                JsonValueKind.True or JsonValueKind.False => $"{part.Name}={part.Value}",
                _ => part.Name,
            }));
}
