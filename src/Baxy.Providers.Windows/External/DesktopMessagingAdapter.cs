using System.Buffers;
using System.Buffers.Binary;
using System.Collections.Concurrent;
using System.Diagnostics;
using System.Globalization;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace Baxy.Providers.Windows.External;

internal sealed class DesktopMessagingAdapter : IExternalOperationAdapter, IDisposable
{
    private readonly IDesktopMessagingAutomation _automation;
    private readonly ConcurrentDictionary<string, ResolvedRecipient> _recipients = new();
    private readonly SemaphoreSlim _interaction = new(1, 1);

    internal DesktopMessagingAdapter()
        : this(new WindowsDesktopMessagingAutomation())
    {
    }

    internal DesktopMessagingAdapter(IDesktopMessagingAutomation automation) =>
        _automation = automation ?? throw new ArgumentNullException(nameof(automation));

    public bool CanHandle(string operation) =>
        operation is "message.recipient.resolve" or "message.send" or "message.draft"
            or "message.send.test";

    // MSG §6 (owner decision 2026-09-17): real sends are allowed ONLY to the
    // owner's own two test channels. message.send.test forces the destination to
    // these by construction; the requested recipient is recorded for a truthful
    // reply but is NEVER used as the send target, so no real third party can be
    // messaged.
    private static readonly Dictionary<string, string> ForcedTestDestination =
        new(StringComparer.Ordinal)
        {
            ["whatsapp"] = "Música",
            ["discord"] = "Valeria",
        };

    public void Dispose() => _interaction.Dispose();

    public async ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        await _interaction.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            return operation switch
            {
                "message.recipient.resolve" => await ResolveAsync(arguments, cancellationToken)
                    .ConfigureAwait(false),
                "message.send" => await SendAsync(arguments, cancellationToken)
                    .ConfigureAwait(false),
                "message.send.test" => await SendTestAsync(arguments, cancellationToken)
                    .ConfigureAwait(false),
                "message.draft" => await DraftAsync(arguments, cancellationToken)
                    .ConfigureAwait(false),
                _ => Failure(operation, "external_operation_not_supported"),
            };
        }
        finally
        {
            _interaction.Release();
        }
    }

    private async ValueTask<ExternalCapabilityReceipt> ResolveAsync(
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        string channel = RequiredString(arguments, "channel");
        string recipient = RequiredString(arguments, "recipient");
        DesktopRecipientObservation observation = await _automation.ResolveAsync(
            channel,
            recipient,
            cancellationToken).ConfigureAwait(false);
        if (!observation.Verified)
        {
            return Failure(
                "message.recipient.resolve",
                observation.ErrorCode ?? "recipient_identity_not_verified",
                observation.EffectObserved);
        }

        string recipientId = "recipient_" + Guid.NewGuid().ToString("N");
        var resolved = new ResolvedRecipient(
            recipientId,
            channel,
            recipient,
            observation.WindowHandle,
            observation.ProcessId);
        _recipients[recipientId] = resolved;
        return Success(
            "message.recipient.resolve",
            JsonObject(
                ("version", 1),
                ("recipientId", recipientId),
                ("channel", channel),
                ("displayName", recipient),
                ("verified", true)));
    }

    private async ValueTask<ExternalCapabilityReceipt> SendAsync(
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        string recipientId = RequiredString(arguments, "recipientId");
        string text = RequiredString(arguments, "text", allowEmpty: true);
        if (!_recipients.TryGetValue(recipientId, out ResolvedRecipient? recipient))
        {
            return Failure("message.send", "recipient_identity_expired");
        }

        DesktopMessageObservation observation = await _automation.SendAsync(
            recipient,
            text,
            cancellationToken).ConfigureAwait(false);
        if (!observation.Verified)
        {
            return Failure(
                "message.send",
                observation.ErrorCode ?? "message_delivery_not_verified",
                observation.EffectObserved);
        }

        string fingerprint = Convert.ToHexStringLower(SHA256.HashData(
            Encoding.UTF8.GetBytes(recipientId + "\n" + text + "\n" + observation.EvidenceHash)));
        return Success(
            "message.send",
            JsonObject(
                ("version", 1),
                ("messageId", "message_" + fingerprint[..24]),
                ("recipientId", recipientId),
                ("channel", recipient.Channel),
                ("displayName", recipient.DisplayName),
                ("contentSha256", Convert.ToHexStringLower(SHA256.HashData(
                    Encoding.UTF8.GetBytes(text)))),
                ("delivery", "visible_postcondition")));
    }

    private async ValueTask<ExternalCapabilityReceipt> DraftAsync(
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        // MSG1837 (owner decision 2026-09-17): the message is left written in
        // the client's composer and never sent; the person presses send.
        string channel = RequiredString(arguments, "channel");
        string recipient = RequiredString(arguments, "recipient");
        string text = RequiredString(arguments, "text");
        DesktopRecipientObservation observation = await _automation.ResolveAsync(
            channel,
            recipient,
            cancellationToken).ConfigureAwait(false);
        if (!observation.Verified)
        {
            return Failure(
                "message.draft",
                observation.ErrorCode ?? "recipient_identity_not_verified",
                observation.EffectObserved);
        }

        var resolved = new ResolvedRecipient(
            "draft_" + Guid.NewGuid().ToString("N"),
            channel,
            recipient,
            observation.WindowHandle,
            observation.ProcessId);
        DesktopMessageObservation draft = await _automation.DraftAsync(
            resolved,
            text,
            cancellationToken).ConfigureAwait(false);
        if (!draft.Verified)
        {
            return Failure(
                "message.draft",
                draft.ErrorCode ?? "message_draft_not_verified",
                draft.EffectObserved);
        }

        return Success(
            "message.draft",
            JsonObject(
                ("version", 1),
                ("channel", channel),
                ("displayName", recipient),
                ("text", text),
                ("draftVisible", true),
                ("sent", false),
                ("evidenceHash", draft.EvidenceHash),
                ("authority", "desktop_client_composer_ocr_postread")));
    }

    private async ValueTask<ExternalCapabilityReceipt> SendTestAsync(
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        // MSG §6: a real, verified send whose destination is ALWAYS one of the
        // owner's two test channels. The requested recipient is recorded only so
        // the reply can say the truth («I sent it to your test group Música, not
        // to Lucas»); it is never used as the target, so no third party is sent to.
        string channel = RequiredString(arguments, "channel");
        string requestedRecipient = RequiredString(arguments, "requestedRecipient");
        string text = RequiredString(arguments, "text");
        if (!ForcedTestDestination.TryGetValue(channel, out string? forced))
        {
            return Failure("message.send.test", "channel_not_a_test_channel");
        }

        DesktopRecipientObservation observation = await _automation.ResolveAsync(
            channel,
            forced,
            cancellationToken).ConfigureAwait(false);
        if (!observation.Verified)
        {
            return Failure(
                "message.send.test",
                observation.ErrorCode ?? "recipient_identity_not_verified",
                observation.EffectObserved);
        }

        var resolved = new ResolvedRecipient(
            "sendtest_" + Guid.NewGuid().ToString("N"),
            channel,
            forced,
            observation.WindowHandle,
            observation.ProcessId);
        DesktopMessageObservation sent = await _automation.SendAsync(
            resolved,
            text,
            cancellationToken).ConfigureAwait(false);
        if (!sent.Verified)
        {
            return Failure(
                "message.send.test",
                sent.ErrorCode ?? "message_delivery_not_verified",
                sent.EffectObserved);
        }

        return Success(
            "message.send.test",
            JsonObject(
                ("version", 1),
                ("channel", channel),
                ("requestedRecipient", requestedRecipient),
                ("forcedDestination", forced),
                ("text", text),
                ("sent", true),
                ("evidenceHash", sent.EvidenceHash),
                ("authority", "desktop_client_send_ocr_postread")));
    }

    private static string RequiredString(
        JsonElement arguments,
        string name,
        bool allowEmpty = false)
    {
        if (!arguments.TryGetProperty(name, out JsonElement value)
            || value.ValueKind != JsonValueKind.String)
        {
            throw new InvalidDataException($"Missing string argument: {name}.");
        }

        string result = value.GetString() ?? string.Empty;
        if (!allowEmpty && string.IsNullOrWhiteSpace(result))
        {
            throw new InvalidDataException($"Empty string argument: {name}.");
        }

        return result;
    }

    private static ExternalCapabilityReceipt Success(string operation, JsonElement result) =>
        new(operation, true, true, result, null);

    private static ExternalCapabilityReceipt Failure(
        string operation,
        string error,
        bool effectObserved = false) =>
        new(operation, effectObserved, false, null, error);

    private static JsonElement JsonObject(params (string Name, object Value)[] values)
    {
        var buffer = new ArrayBufferWriter<byte>();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            writer.WriteStartObject();
            foreach ((string name, object value) in values)
            {
                switch (value)
                {
                    case string text:
                        writer.WriteString(name, text);
                        break;
                    case int number:
                        writer.WriteNumber(name, number);
                        break;
                    case bool boolean:
                        writer.WriteBoolean(name, boolean);
                        break;
                    default:
                        throw new InvalidDataException("Unsupported evidence value.");
                }
            }

            writer.WriteEndObject();
        }

        using JsonDocument document = JsonDocument.Parse(buffer.WrittenMemory);
        return document.RootElement.Clone();
    }
}

internal interface IExternalOperationAdapter
{
    bool CanHandle(string operation);

    ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken);
}

internal sealed record ResolvedRecipient(
    string RecipientId,
    string Channel,
    string DisplayName,
    nint WindowHandle,
    int ProcessId);

internal sealed record DesktopRecipientObservation(
    bool Verified,
    bool EffectObserved,
    nint WindowHandle,
    int ProcessId,
    string? ErrorCode);

internal sealed record DesktopMessageObservation(
    bool Verified,
    bool EffectObserved,
    string EvidenceHash,
    string? ErrorCode);

internal interface IDesktopMessagingAutomation
{
    ValueTask<DesktopRecipientObservation> ResolveAsync(
        string channel,
        string recipient,
        CancellationToken cancellationToken);

    ValueTask<DesktopMessageObservation> SendAsync(
        ResolvedRecipient recipient,
        string text,
        CancellationToken cancellationToken);

    ValueTask<DesktopMessageObservation> DraftAsync(
        ResolvedRecipient recipient,
        string text,
        CancellationToken cancellationToken) =>
        throw new NotSupportedException("message drafts are not supported by this automation");
}

internal sealed partial class WindowsDesktopMessagingAutomation : IDesktopMessagingAutomation
{
    private const ushort VirtualKeyControl = 0x11;
    private const ushort VirtualKeyK = 0x4B;
    private const ushort VirtualKeyReturn = 0x0D;
    private const ushort VirtualKeyA = 0x41;
    private const ushort VirtualKeyBack = 0x08;
    private const ushort VirtualKeyEscape = 0x1B;
    private const uint KeyUp = 0x0002;
    private const uint Unicode = 0x0004;

    public async ValueTask<DesktopRecipientObservation> ResolveAsync(
        string channel,
        string recipient,
        CancellationToken cancellationToken)
    {
        (nint handle, int processId) = FindWindow(channel);
        if (handle == 0)
        {
            return new(false, false, 0, 0, $"{channel}_client_not_running");
        }

        if (!Focus(handle))
        {
            return new(false, false, handle, processId, "messaging_focus_not_verified");
        }

        await NormalizeWindowAsync(channel, handle, cancellationToken).ConfigureAwait(false);
        // Escape closes any search panel left open in the client (an in-conversation
        // search opened by Ctrl+F while the composer had focus hides the header),
        // and the header is read twice because the first frame after a resize or
        // focus change may still be transitional.
        SendKey(VirtualKeyEscape);
        await Task.Delay(250, cancellationToken).ConfigureAwait(false);

        ValueTask<bool> ObserveRecipientAsync(CancellationToken token) =>
            string.Equals(channel, "discord", StringComparison.Ordinal)
                ? ValueTask.FromResult(
                    Fold(WindowTitle(handle)).Contains(Fold(recipient), StringComparison.Ordinal))
                : HeaderContainsAsync(handle, recipient, token);
        for (int attempt = 0; attempt < 2; attempt++)
        {
            if (await ObserveRecipientAsync(cancellationToken).ConfigureAwait(false))
            {
                return new(true, false, handle, processId, null);
            }

            await Task.Delay(500, cancellationToken).ConfigureAwait(false);
        }

        SendChord(
            VirtualKeyControl,
            string.Equals(channel, "whatsapp", StringComparison.Ordinal)
                ? (ushort)0x46
                : VirtualKeyK);
        await Task.Delay(250, cancellationToken).ConfigureAwait(false);
        SendChord(VirtualKeyControl, VirtualKeyA);
        await Task.Delay(100, cancellationToken).ConfigureAwait(false);
        SendKey(VirtualKeyBack);
        SendText(recipient);
        await Task.Delay(350, cancellationToken).ConfigureAwait(false);
        SendKey(VirtualKeyReturn);

        await Task.Delay(900, cancellationToken).ConfigureAwait(false);
        bool verified = await ObserveRecipientAsync(cancellationToken).ConfigureAwait(false);
        return new(
            verified,
            true,
            handle,
            processId,
            verified ? null : "recipient_identity_not_verified");
    }

    public async ValueTask<DesktopMessageObservation> SendAsync(
        ResolvedRecipient recipient,
        string text,
        CancellationToken cancellationToken)
    {
        if (!ProcessStillOwnsWindow(recipient.WindowHandle, recipient.ProcessId)
            || !Focus(recipient.WindowHandle))
        {
            return new(false, false, string.Empty, "messaging_focus_not_verified");
        }

        await NormalizeWindowAsync(recipient.Channel, recipient.WindowHandle, cancellationToken)
            .ConfigureAwait(false);

        bool targetVerified = string.Equals(
            recipient.Channel,
            "discord",
            StringComparison.Ordinal)
                ? Fold(WindowTitle(recipient.WindowHandle)).Contains(
                    Fold(recipient.DisplayName),
                    StringComparison.Ordinal)
                : await HeaderContainsAsync(
                    recipient.WindowHandle,
                    recipient.DisplayName,
                    cancellationToken).ConfigureAwait(false);
        if (!targetVerified)
        {
            return new(false, false, string.Empty, "recipient_identity_changed");
        }

        if (!FocusComposer(recipient.WindowHandle))
        {
            return new(false, false, string.Empty, "message_composer_not_focused");
        }

        await Task.Delay(200, cancellationToken).ConfigureAwait(false);
        SendChord(VirtualKeyControl, VirtualKeyA);
        SendKey(VirtualKeyBack);
        await Task.Delay(150, cancellationToken).ConfigureAwait(false);
        byte[] before = CaptureRegion(recipient.WindowHandle, CaptureArea.Composer, recipient.Channel);
        SendText(text);

        async ValueTask<MessageVisualObservation> ObserveDraftAsync(CancellationToken token)
        {
            byte[] bitmap = CaptureRegion(recipient.WindowHandle, CaptureArea.Composer, recipient.Channel);
            bool changed = !CryptographicOperations.FixedTimeEquals(
                SHA256.HashData(before),
                SHA256.HashData(bitmap));
            string observedText = changed
                ? await ReadTextAsync(bitmap, token).ConfigureAwait(false)
                : string.Empty;
            return new(bitmap, changed && ContainsPhrase(observedText, text));
        }

        MessageVisualObservation draftObservation = await ObserveNowOrAtDeadlineAsync(
            ObserveDraftAsync,
            static observation => observation.Verified,
            TimeSpan.FromMilliseconds(350),
            cancellationToken).ConfigureAwait(false);
        if (!draftObservation.Verified)
        {
            SendChord(VirtualKeyControl, VirtualKeyA);
            SendKey(VirtualKeyBack);
            return new(false, false, string.Empty, "message_draft_not_verified");
        }

        // The delivery is read from the band of last messages just above the
        // composer, where the new outgoing bubble appears; the whole pane never
        // reads it (MSGSEND1845: «hola» sent and visible, pane OCR without it).
        byte[] beforeSend = CaptureRegion(recipient.WindowHandle, CaptureArea.LastMessages, recipient.Channel);
        SendKey(VirtualKeyReturn);
        await Task.Delay(900, cancellationToken).ConfigureAwait(false);
        byte[] after = CaptureRegion(recipient.WindowHandle, CaptureArea.LastMessages, recipient.Channel);
        string afterText = await ReadTextAsync(after, cancellationToken).ConfigureAwait(false);
        string afterHash = Convert.ToHexStringLower(SHA256.HashData(after));
        bool changed = !CryptographicOperations.FixedTimeEquals(
            SHA256.HashData(beforeSend),
            SHA256.HashData(after));
        bool visible = ContainsPhrase(afterText, text);
        bool stillTarget = string.Equals(recipient.Channel, "discord", StringComparison.Ordinal)
            ? Fold(WindowTitle(recipient.WindowHandle)).Contains(
                Fold(recipient.DisplayName),
                StringComparison.Ordinal)
            : await HeaderContainsAsync(
                recipient.WindowHandle,
                recipient.DisplayName,
                cancellationToken).ConfigureAwait(false);
        return new(
            changed && visible && stillTarget,
            true,
            afterHash,
            changed && visible && stillTarget ? null : "message_delivery_not_verified");
    }

    public async ValueTask<DesktopMessageObservation> DraftAsync(
        ResolvedRecipient recipient,
        string text,
        CancellationToken cancellationToken)
    {
        // MSG1837: the same path as a send up to the verified draft, then stop.
        if (!ProcessStillOwnsWindow(recipient.WindowHandle, recipient.ProcessId)
            || !Focus(recipient.WindowHandle))
        {
            return new(false, false, string.Empty, "messaging_focus_not_verified");
        }

        await NormalizeWindowAsync(recipient.Channel, recipient.WindowHandle, cancellationToken)
            .ConfigureAwait(false);

        bool targetVerified = string.Equals(
            recipient.Channel,
            "discord",
            StringComparison.Ordinal)
                ? Fold(WindowTitle(recipient.WindowHandle)).Contains(
                    Fold(recipient.DisplayName),
                    StringComparison.Ordinal)
                : await HeaderContainsAsync(
                    recipient.WindowHandle,
                    recipient.DisplayName,
                    cancellationToken).ConfigureAwait(false);
        if (!targetVerified)
        {
            return new(false, false, string.Empty, "recipient_identity_changed");
        }

        if (!FocusComposer(recipient.WindowHandle))
        {
            return new(false, false, string.Empty, "message_composer_not_focused");
        }

        await Task.Delay(200, cancellationToken).ConfigureAwait(false);
        SendChord(VirtualKeyControl, VirtualKeyA);
        SendKey(VirtualKeyBack);
        await Task.Delay(150, cancellationToken).ConfigureAwait(false);
        byte[] before = CaptureRegion(recipient.WindowHandle, CaptureArea.Composer, recipient.Channel);
        SendText(text);

        async ValueTask<MessageVisualObservation> ObserveDraftAsync(CancellationToken token)
        {
            byte[] bitmap = CaptureRegion(recipient.WindowHandle, CaptureArea.Composer, recipient.Channel);
            bool changed = !CryptographicOperations.FixedTimeEquals(
                SHA256.HashData(before),
                SHA256.HashData(bitmap));
            string observedText = changed
                ? await ReadTextAsync(bitmap, token).ConfigureAwait(false)
                : string.Empty;
            return new(bitmap, changed && ContainsPhrase(observedText, text));
        }

        MessageVisualObservation draftObservation = await ObserveNowOrAtDeadlineAsync(
            ObserveDraftAsync,
            static observation => observation.Verified,
            TimeSpan.FromMilliseconds(1200),
            cancellationToken).ConfigureAwait(false);
        if (!draftObservation.Verified)
        {
            SendChord(VirtualKeyControl, VirtualKeyA);
            SendKey(VirtualKeyBack);
            return new(false, true, string.Empty, "message_draft_not_verified");
        }

        return new(
            true,
            true,
            Convert.ToHexStringLower(SHA256.HashData(draftObservation.Bitmap)),
            null);
    }

    internal static async ValueTask<T> ObserveNowOrAtDeadlineAsync<T>(
        Func<CancellationToken, ValueTask<T>> observe,
        Func<T, bool> verified,
        TimeSpan horizon,
        CancellationToken cancellationToken,
        Func<TimeSpan, CancellationToken, ValueTask>? delay = null)
    {
        ArgumentNullException.ThrowIfNull(observe);
        ArgumentNullException.ThrowIfNull(verified);
        ArgumentOutOfRangeException.ThrowIfLessThan(horizon, TimeSpan.Zero);

        Stopwatch stopwatch = Stopwatch.StartNew();
        T observation = await observe(cancellationToken).ConfigureAwait(false);
        if (verified(observation))
        {
            return observation;
        }

        TimeSpan remaining = horizon - stopwatch.Elapsed;
        if (remaining > TimeSpan.Zero)
        {
            if (delay is null)
            {
                await Task.Delay(remaining, cancellationToken).ConfigureAwait(false);
            }
            else
            {
                await delay(remaining, cancellationToken).ConfigureAwait(false);
            }
        }

        return await observe(cancellationToken).ConfigureAwait(false);
    }

    private static async ValueTask<bool> HeaderContainsAsync(
        nint handle,
        string target,
        CancellationToken cancellationToken)
    {
        byte[] header = CaptureRegion(handle, CaptureArea.Header, "whatsapp");
        string text = await ReadTextAsync(header, cancellationToken).ConfigureAwait(false);
        return Fold(text).Contains(Fold(target), StringComparison.Ordinal);
    }

    private static async ValueTask<string> ReadTextAsync(
        byte[] bitmap,
        CancellationToken cancellationToken)
    {
        string? executable = FindTesseract();
        if (executable is null)
        {
            return string.Empty;
        }

        // A dark theme draws light text on a dark background, which Tesseract
        // reads as nothing (MSGSEND1845: «hola» typed in the WhatsApp composer
        // came back empty) while the inverted copy reads it; and the header
        // title at native size read «Misica» where the 2x copy reads «Musica»,
        // while the composer band reads only at native size. Every reading
        // counts, so the four passes are joined.
        byte[] doubled = Upscale2x(bitmap);
        var readings = new string[4];
        int index = 0;
        foreach (byte[] candidate in new[] { bitmap, InvertPixels(bitmap), doubled, InvertPixels(doubled) })
        {
            readings[index++] = await RunTesseractAsync(executable, candidate, cancellationToken)
                .ConfigureAwait(false);
        }

        string text = string.Join('\n', readings);
        AuditReading(bitmap, text);
        return text;
    }

    // Opt-in evidence of what the OCR saw (crop and the joined readings), like
    // the mind's compose audit: set BAXY_MESSAGING_OCR_AUDIT_DIR to a directory.
    private static void AuditReading(byte[] bitmap, string text)
    {
        string? directory = Environment.GetEnvironmentVariable("BAXY_MESSAGING_OCR_AUDIT_DIR");
        if (string.IsNullOrWhiteSpace(directory) || !Directory.Exists(directory))
        {
            return;
        }

        try
        {
            string stem = Path.Combine(
                directory,
                $"{DateTime.UtcNow:yyyyMMdd-HHmmss-fff}-{Environment.ProcessId}");
            File.WriteAllBytes(stem + ".bmp", bitmap);
            File.WriteAllText(stem + ".txt", text, Encoding.UTF8);
        }
        catch (IOException)
        {
            // The audit never changes delivery evidence.
        }
    }

    private static byte[] Upscale2x(byte[] bitmap)
    {
        const int header = 54;
        int width = BinaryPrimitives.ReadInt32LittleEndian(bitmap.AsSpan(18));
        int height = BinaryPrimitives.ReadInt32LittleEndian(bitmap.AsSpan(22));
        int stride = width * 4;
        byte[] pixels = new byte[checked(stride * 2 * height * 2)];
        for (int row = 0; row < height; row++)
        {
            ReadOnlySpan<byte> source = bitmap.AsSpan(header + row * stride, stride);
            Span<byte> target = pixels.AsSpan(row * 2 * stride * 2, stride * 2);
            for (int column = 0; column < width; column++)
            {
                ReadOnlySpan<byte> pixel = source.Slice(column * 4, 4);
                pixel.CopyTo(target.Slice(column * 8, 4));
                pixel.CopyTo(target.Slice(column * 8 + 4, 4));
            }

            target.CopyTo(pixels.AsSpan((row * 2 + 1) * stride * 2, stride * 2));
        }

        return EncodeBmp(width * 2, height * 2, pixels);
    }

    private static byte[] InvertPixels(byte[] bitmap)
    {
        const int header = 54;
        byte[] result = (byte[])bitmap.Clone();
        for (int index = header; index + 2 < result.Length; index += 4)
        {
            result[index] = (byte)~result[index];
            result[index + 1] = (byte)~result[index + 1];
            result[index + 2] = (byte)~result[index + 2];
        }

        return result;
    }

    private static async ValueTask<string> RunTesseractAsync(
        string executable,
        byte[] bitmap,
        CancellationToken cancellationToken)
    {
        string path = Path.Combine(Path.GetTempPath(), $"baxy-ocr-{Guid.NewGuid():N}.bmp");
        try
        {
            await File.WriteAllBytesAsync(path, bitmap, cancellationToken).ConfigureAwait(false);
            var start = new ProcessStartInfo(executable)
            {
                UseShellExecute = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                CreateNoWindow = true,
            };
            start.ArgumentList.Add(path);
            start.ArgumentList.Add("stdout");
            start.ArgumentList.Add("-l");
            start.ArgumentList.Add("eng");
            start.ArgumentList.Add("--psm");
            start.ArgumentList.Add("6");
            using Process process = Process.Start(start)
                ?? throw new IOException("Tesseract did not start.");
            return await ReadRedirectedOutputAsync(process, cancellationToken)
                .ConfigureAwait(false);
        }
        finally
        {
            try
            {
                File.Delete(path);
            }
            catch (IOException)
            {
                // A failed local cleanup does not change delivery evidence.
            }
        }
    }

    internal static async ValueTask<string> ReadRedirectedOutputAsync(
        Process process,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(process);
        Task<string> outputTask =
            process.StandardOutput.ReadToEndAsync(cancellationToken);
        Task<string> errorTask =
            process.StandardError.ReadToEndAsync(cancellationToken);
        await process.WaitForExitAsync(cancellationToken).ConfigureAwait(false);
        string[] streams = await Task.WhenAll(outputTask, errorTask).ConfigureAwait(false);
        return process.ExitCode == 0 ? streams[0] : string.Empty;
    }

    private readonly record struct MessageVisualObservation(
        byte[] Bitmap,
        bool Verified);

    private static string? FindTesseract()
    {
        string? path = Environment.GetEnvironmentVariable("PATH");
        foreach (string directory in (path ?? string.Empty).Split(Path.PathSeparator))
        {
            string candidate = Path.Combine(directory, "tesseract.exe");
            if (File.Exists(candidate))
            {
                return candidate;
            }
        }

        string fallback = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles),
            "Tesseract-OCR",
            "tesseract.exe");
        return File.Exists(fallback) ? fallback : null;
    }

    private static (nint Handle, int ProcessId) FindWindow(string channel)
    {
        string[] processNames = string.Equals(channel, "whatsapp", StringComparison.Ordinal)
            ? ["WhatsApp.Root"]
            : ["Discord"];
        foreach (string processName in processNames)
        {
            Process[] processes = Process.GetProcessesByName(processName);
            try
            {
                foreach (Process process in processes)
                {
                    if (process.MainWindowHandle != 0)
                    {
                        return (process.MainWindowHandle, process.Id);
                    }
                }
            }
            finally
            {
                foreach (Process process in processes)
                {
                    process.Dispose();
                }
            }
        }

        return (0, 0);
    }

    private static bool Focus(nint handle)
    {
        nint foreground = GetForegroundWindow();
        uint foregroundThread = GetWindowThreadProcessId(foreground, out _);
        uint currentThread = GetCurrentThreadId();
        bool attached = foregroundThread != 0
            && currentThread != foregroundThread
            && AttachThreadInput(currentThread, foregroundThread, true);
        try
        {
            _ = ShowWindow(handle, 9);
            _ = BringWindowToTop(handle);
            _ = SetForegroundWindow(handle);
            return GetForegroundWindow() == handle;
        }
        finally
        {
            if (attached)
            {
                _ = AttachThreadInput(currentThread, foregroundThread, false);
            }
        }
    }

    private static bool ProcessStillOwnsWindow(nint handle, int expectedProcessId)
    {
        _ = GetWindowThreadProcessId(handle, out uint processId);
        return handle != 0 && processId == (uint)expectedProcessId;
    }

    private static unsafe string WindowTitle(nint handle)
    {
        char[] title = new char[512];
        fixed (char* buffer = title)
        {
            int length = GetWindowText(handle, buffer, title.Length);
            return length > 0 ? new string(buffer, 0, length) : string.Empty;
        }
    }

    private static string Fold(string value)
    {
        string normalized = value.Normalize(NormalizationForm.FormD).ToLowerInvariant();
        var result = new StringBuilder(normalized.Length);
        foreach (char character in normalized)
        {
            UnicodeCategory category = CharUnicodeInfo.GetUnicodeCategory(character);
            if (category == UnicodeCategory.NonSpacingMark)
            {
                continue;
            }

            result.Append(char.IsLetterOrDigit(character) ? character : ' ');
        }

        return string.Join(' ', result.ToString().Split(
            ' ',
            StringSplitOptions.RemoveEmptyEntries));
    }

    internal static bool ContainsPhrase(string source, string expected)
    {
        string foldedExpected = Fold(expected);
        if (foldedExpected.Length == 0)
        {
            return expected.Length == 0;
        }

        string foldedSource = Fold(source);
        return string.Concat(" ", foldedSource, " ").Contains(
            string.Concat(" ", foldedExpected, " "),
            StringComparison.Ordinal);
    }

    private static void SendChord(ushort modifier, ushort key)
    {
        SendVirtualKey(modifier, keyUp: false);
        SendVirtualKey(key, keyUp: false);
        SendVirtualKey(key, keyUp: true);
        SendVirtualKey(modifier, keyUp: true);
    }

    private static void SendKey(ushort key)
    {
        SendVirtualKey(key, keyUp: false);
        SendVirtualKey(key, keyUp: true);
    }

    private static void SendVirtualKey(ushort key, bool keyUp)
    {
        Input[] inputs =
        [
            new()
            {
                Type = 1,
                Union = new InputUnion
                {
                    Keyboard = new KeyboardInput
                    {
                        VirtualKey = key,
                        Flags = keyUp ? KeyUp : 0,
                    },
                },
            },
        ];
        if (SendInput((uint)inputs.Length, inputs, Marshal.SizeOf<Input>()) != inputs.Length)
        {
            throw new IOException("Windows rejected keyboard input.");
        }
    }

    private static void SendText(string text)
    {
        foreach (char character in text)
        {
            SendUnicode(character, keyUp: false);
            SendUnicode(character, keyUp: true);
        }
    }

    private static void SendUnicode(char character, bool keyUp)
    {
        Input[] inputs =
        [
            new()
            {
                Type = 1,
                Union = new InputUnion
                {
                    Keyboard = new KeyboardInput
                    {
                        ScanCode = character,
                        Flags = Unicode | (keyUp ? KeyUp : 0),
                    },
                },
            },
        ];
        if (SendInput((uint)inputs.Length, inputs, Marshal.SizeOf<Input>()) != inputs.Length)
        {
            throw new IOException("Windows rejected Unicode input.");
        }
    }

    // WhatsApp Desktop is per-monitor DPI aware and widens its chat list at
    // large window widths (responsive breakpoints: the conversation header title
    // sat at 465 logical px in a 1425 px window and at 617 px maximized at
    // 1550 px), so no crop offset holds across sizes. The window is therefore
    // normalized to a fixed logical size below the breakpoint before any read
    // (MSGSEND1845: a 42 % cut read «ica», a fixed offset then missed the title
    // once the owner moved the window), which makes the layout deterministic:
    // the chat list ends at about 395 px and the header title starts at about
    // 465 px, so the crop starts between them and excludes the search box and
    // the list item that both show the searched name.
    private const int WhatsAppWindowLogicalWidth = 1280;
    private const int WhatsAppWindowLogicalHeight = 800;
    private const int WhatsAppConversationPaneOffsetAt96Dpi = 430;

    // Distance from the window's bottom edge to the middle of the composer input
    // (WhatsApp bar ≈ 48 px high with an 8 px margin; Discord's box sits within
    // the same band), scaled by the window's DPI like the pane offset.
    private const int ComposerBottomOffsetAt96Dpi = 56;

    private static async ValueTask NormalizeWindowAsync(
        string channel,
        nint handle,
        CancellationToken cancellationToken)
    {
        if (!string.Equals(channel, "whatsapp", StringComparison.Ordinal))
        {
            return;
        }

        nint previousDpi = SetThreadDpiAwarenessContext((nint)(-4));
        try
        {
            double scale = GetDpiForWindow(handle) / 96.0;
            int width = (int)(WhatsAppWindowLogicalWidth * scale);
            int height = (int)(WhatsAppWindowLogicalHeight * scale);
            if (GetWindowRect(handle, out Rect rectangle)
                && rectangle.Right - rectangle.Left == width
                && rectangle.Bottom - rectangle.Top == height)
            {
                return;
            }

            // SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE: only the size changes.
            _ = SetWindowPos(handle, 0, 0, 0, width, height, 0x0002 | 0x0004 | 0x0010);
        }
        finally
        {
            _ = SetThreadDpiAwarenessContext(previousDpi);
        }

        await Task.Delay(400, cancellationToken).ConfigureAwait(false);
    }

    // The typed draft is read from the composer band alone: Tesseract does not
    // segment that single line out of the whole conversation pane over the
    // doodle wallpaper (MSGSEND1845: «hola» read as «tt i>)» in the pane, as
    // «hola» in the band).
    private const int ComposerBandHeightAt96Dpi = 90;
    private const int LastMessagesBandHeightAt96Dpi = 200;

    private enum CaptureArea
    {
        Header,
        Body,
        Composer,
        LastMessages,
    }

    private static byte[] CaptureRegion(nint handle, CaptureArea area, string channel)
    {
        nint previousDpi = SetThreadDpiAwarenessContext((nint)(-4));
        try
        {
            if (!GetWindowRect(handle, out Rect rectangle))
            {
                throw new IOException("Messaging window bounds are unavailable.");
            }

            int windowWidth = rectangle.Right - rectangle.Left;
            int windowHeight = rectangle.Bottom - rectangle.Top;
            double scale = GetDpiForWindow(handle) / 96.0;
            int sourceX = string.Equals(channel, "whatsapp", StringComparison.Ordinal)
                ? Math.Min(
                    Math.Max(0, windowWidth - 1),
                    (int)(WhatsAppConversationPaneOffsetAt96Dpi * scale))
                : (int)(windowWidth * 0.42);
            int composerBand = Math.Min(windowHeight, (int)(ComposerBandHeightAt96Dpi * scale));
            int lastMessagesBand = Math.Min(
                windowHeight - composerBand,
                (int)(LastMessagesBandHeightAt96Dpi * scale));
            int sourceY = area switch
            {
                CaptureArea.Header => 0,
                CaptureArea.Composer => windowHeight - composerBand,
                CaptureArea.LastMessages => windowHeight - composerBand - lastMessagesBand,
                _ => Math.Min(80, windowHeight / 8),
            };
            int width = Math.Max(1, windowWidth - sourceX);
            int height = area switch
            {
                CaptureArea.Header => Math.Max(1, Math.Min(150, windowHeight / 4)),
                CaptureArea.Composer => Math.Max(1, composerBand),
                CaptureArea.LastMessages => Math.Max(1, lastMessagesBand),
                _ => Math.Max(1, windowHeight - sourceY),
            };
            nint screenDc = GetDC(0);
            if (screenDc == 0)
            {
                throw new IOException("Window DC is unavailable.");
            }

            nint memory = 0;
            nint bitmap = 0;
            nint previous = 0;
            try
            {
                memory = CreateCompatibleDC(screenDc);
                bitmap = CreateCompatibleBitmap(screenDc, width, height);
                previous = SelectObject(memory, bitmap);
                if (memory == 0 || bitmap == 0 || previous == 0
                    || !BitBlt(
                        memory,
                        0,
                        0,
                        width,
                        height,
                        screenDc,
                        rectangle.Left + sourceX,
                        rectangle.Top + sourceY,
                        0x40CC0020))
                {
                    throw new IOException("Messaging evidence capture failed.");
                }

                var info = new BitmapInfo
                {
                    Header = new BitmapInfoHeader
                    {
                        Size = (uint)Marshal.SizeOf<BitmapInfoHeader>(),
                        Width = width,
                        Height = height,
                        Planes = 1,
                        BitCount = 32,
                    },
                };
                byte[] pixels = new byte[checked(width * height * 4)];
                if (GetDIBits(memory, bitmap, 0, (uint)height, pixels, ref info, 0) != height)
                {
                    throw new IOException("Messaging evidence pixels are unavailable.");
                }

                return EncodeBmp(width, height, pixels);
            }
            finally
            {
                if (previous != 0 && memory != 0)
                {
                    _ = SelectObject(memory, previous);
                }

                if (bitmap != 0)
                {
                    _ = DeleteObject(bitmap);
                }

                if (memory != 0)
                {
                    _ = DeleteDC(memory);
                }

                _ = ReleaseDC(0, screenDc);
            }
        }
        finally
        {
            if (previousDpi != 0)
            {
                _ = SetThreadDpiAwarenessContext(previousDpi);
            }
        }
    }

    private static bool FocusComposer(nint handle)
    {
        nint previousDpi = SetThreadDpiAwarenessContext((nint)(-4));
        try
        {
            if (!GetWindowRect(handle, out Rect rectangle))
            {
                return false;
            }

            int width = rectangle.Right - rectangle.Left;
            // The composer bar has a constant height at the bottom of the window,
            // so its input is a fixed distance above the bottom edge; a fraction of
            // the window height landed on the bar's top edge once the window was
            // tall (MSGSEND1845: 944 px, 92 % = 868 px, input centred at 888 px,
            // «hola» typed into nothing, message_draft_not_verified).
            if (!SetCursorPos(
                    rectangle.Left + (int)(width * 0.76),
                    rectangle.Bottom - (int)(ComposerBottomOffsetAt96Dpi * GetDpiForWindow(handle) / 96.0)))
            {
                return false;
            }

            Input[] inputs =
            [
                MouseInput(0x0002),
                MouseInput(0x0004),
            ];
            return SendInput((uint)inputs.Length, inputs, Marshal.SizeOf<Input>())
                == inputs.Length;
        }
        finally
        {
            if (previousDpi != 0)
            {
                _ = SetThreadDpiAwarenessContext(previousDpi);
            }
        }
    }

    private static Input MouseInput(uint flags) => new()
    {
        Type = 0,
        Union = new InputUnion
        {
            Mouse = new NativeMouseInput { Flags = flags },
        },
    };

    private static byte[] EncodeBmp(int width, int height, byte[] pixels)
    {
        const int header = 54;
        byte[] result = new byte[checked(header + pixels.Length)];
        result[0] = (byte)'B';
        result[1] = (byte)'M';
        BinaryPrimitives.WriteInt32LittleEndian(result.AsSpan(2), result.Length);
        BinaryPrimitives.WriteInt32LittleEndian(result.AsSpan(10), header);
        BinaryPrimitives.WriteInt32LittleEndian(result.AsSpan(14), 40);
        BinaryPrimitives.WriteInt32LittleEndian(result.AsSpan(18), width);
        BinaryPrimitives.WriteInt32LittleEndian(result.AsSpan(22), height);
        BinaryPrimitives.WriteInt16LittleEndian(result.AsSpan(26), 1);
        BinaryPrimitives.WriteInt16LittleEndian(result.AsSpan(28), 32);
        BinaryPrimitives.WriteInt32LittleEndian(result.AsSpan(34), pixels.Length);
        pixels.CopyTo(result, header);
        return result;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct Rect
    {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct Input
    {
        public uint Type;
        public InputUnion Union;
    }

    [StructLayout(LayoutKind.Explicit, Size = 32)]
    private struct InputUnion
    {
        [FieldOffset(0)]
        public KeyboardInput Keyboard;

        [FieldOffset(0)]
        public NativeMouseInput Mouse;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct KeyboardInput
    {
        public ushort VirtualKey;
        public ushort ScanCode;
        public uint Flags;
        public uint Time;
        public nint ExtraInfo;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct NativeMouseInput
    {
        public int X;
        public int Y;
        public uint MouseData;
        public uint Flags;
        public uint Time;
        public nint ExtraInfo;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct BitmapInfoHeader
    {
        public uint Size;
        public int Width;
        public int Height;
        public ushort Planes;
        public ushort BitCount;
        public uint Compression;
        public uint SizeImage;
        public int XPelsPerMeter;
        public int YPelsPerMeter;
        public uint ColorsUsed;
        public uint ColorsImportant;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct BitmapInfo
    {
        public BitmapInfoHeader Header;
    }

    [LibraryImport("user32.dll")]
    private static partial nint GetForegroundWindow();

    [LibraryImport("user32.dll")]
    private static partial uint GetWindowThreadProcessId(nint handle, out uint processId);

    [LibraryImport("kernel32.dll")]
    private static partial uint GetCurrentThreadId();

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool AttachThreadInput(
        uint first,
        uint second,
        [MarshalAs(UnmanagedType.Bool)] bool attach);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool ShowWindow(nint handle, int command);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool BringWindowToTop(nint handle);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool SetForegroundWindow(nint handle);

    [LibraryImport("user32.dll", EntryPoint = "GetWindowTextW")]
    private static unsafe partial int GetWindowText(
        nint handle,
        char* text,
        int maximum);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool GetWindowRect(nint handle, out Rect rectangle);

    [LibraryImport("user32.dll")]
    private static partial nint SetThreadDpiAwarenessContext(nint context);

    [LibraryImport("user32.dll")]
    private static partial uint GetDpiForWindow(nint handle);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool SetWindowPos(
        nint handle,
        nint insertAfter,
        int x,
        int y,
        int width,
        int height,
        uint flags);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool SetCursorPos(int x, int y);

    [LibraryImport("user32.dll", SetLastError = true)]
    private static partial uint SendInput(uint count, [In, Out] Input[] inputs, int size);

    [LibraryImport("user32.dll")]
    private static partial nint GetDC(nint window);

    [LibraryImport("user32.dll")]
    private static partial int ReleaseDC(nint window, nint dc);

    [LibraryImport("gdi32.dll")]
    private static partial nint CreateCompatibleDC(nint dc);

    [LibraryImport("gdi32.dll")]
    private static partial nint CreateCompatibleBitmap(nint dc, int width, int height);

    [LibraryImport("gdi32.dll")]
    private static partial nint SelectObject(nint dc, nint value);

    [LibraryImport("gdi32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool BitBlt(
        nint destination,
        int x,
        int y,
        int width,
        int height,
        nint source,
        int sourceX,
        int sourceY,
        uint operation);

    [LibraryImport("gdi32.dll")]
    private static partial int GetDIBits(
        nint dc,
        nint bitmap,
        uint start,
        uint lines,
        [Out] byte[] bits,
        ref BitmapInfo info,
        uint usage);

    [LibraryImport("gdi32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool DeleteObject(nint value);

    [LibraryImport("gdi32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool DeleteDC(nint dc);
}
