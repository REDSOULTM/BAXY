using System.Buffers;
using System.Buffers.Binary;
using System.Collections.Concurrent;
using System.Diagnostics;
using System.Globalization;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Baxy.Providers.Windows.Applications;

namespace Baxy.Providers.Windows.External;

internal sealed class DesktopMessagingAdapter : IExternalOperationAdapter, IDisposable
{
    private readonly IDesktopMessagingAutomation _automation;
    private readonly SemaphoreSlim _interaction = new(1, 1);
    private readonly string _testDestinationsPath;

    internal DesktopMessagingAdapter(IClientInteractionProbe probe)
        : this(new WindowsDesktopMessagingAutomation(probe))
    {
    }

    internal DesktopMessagingAdapter(
        IDesktopMessagingAutomation automation,
        string? testDestinationsPath = null,
        IExternalProcessRunner? mailRunner = null)
    {
        _automation = automation ?? throw new ArgumentNullException(nameof(automation));
        _testDestinationsPath = testDestinationsPath ?? DefaultTestDestinationsPath();
        _mailRunner = mailRunner ?? new ExternalProcessRunner();
    }

    public bool CanHandle(string operation) =>
        operation is "message.draft" or "message.send" or "message.send.test" or "client.channel.open";

    // MSG §6 (owner decisions 2026-09-17 and 2026-09-18 §3): real sends are allowed ONLY to the owner's own test
    // destinations. message.send.test forces the destination to these by construction; the requested recipient is
    // recorded for a truthful reply but is NEVER used as the send target, so no real third party can be messaged.
    // C6: the destinations are the owner's private data, never source: <data>/messaging/test-destinations.v1.json,
    // {"whatsapp": "<chat>", "discord": "<direct message>", "email": "<mailbox>"}, read on each send. Without the file
    // or the channel in it there is no test destination and nothing is sent.
    private static string DefaultTestDestinationsPath()
    {
        string root = Environment.GetEnvironmentVariable("BAXY_DATA_DIR") is { Length: > 0 } configured
            ? configured
            : Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "BAXY", "development");
        return Path.Combine(root, "messaging", "test-destinations.v1.json");
    }

    private string? ReadTestDestination(string channel)
    {
        try
        {
            using JsonDocument document = JsonDocument.Parse(File.ReadAllBytes(_testDestinationsPath));
            return document.RootElement.ValueKind == JsonValueKind.Object
                && document.RootElement.TryGetProperty(channel, out JsonElement value)
                && value.ValueKind == JsonValueKind.String
                && !string.IsNullOrWhiteSpace(value.GetString())
                    ? value.GetString()
                    : null;
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException or JsonException)
        {
            return null;
        }
    }

    private readonly IExternalProcessRunner _mailRunner;

    public void Dispose() => _interaction.Dispose();

    // Encargo 58 (diagnóstico f11dcfa99, S03 6 de 6): with no test destination for the channel, the person was asked for
    // a yes to a send that could only fail after it. That is read before asking: the call fails with nothing touched.
    public bool PreflightMayRaise(string operation, JsonElement arguments) =>
        operation == "client.channel.open"
        && arguments.ValueKind == JsonValueKind.Object
        && arguments.TryGetProperty("client", out JsonElement client)
        && client.ValueKind == JsonValueKind.String
        && client.GetString() == "discord";

    // Uso-128 (D15, «Discord text direct, voice asks and stays, mic as is»; Discord joins a voice channel when its row is
    // pressed): what the name is, read before the person is asked: a voice channel asks, bound to this call, and says so.
    // The read remembers its answer: a run right after it that finds a voice row it did not see presses nothing (the yes was
    // never asked for it). No read at all is Bypass, where nothing asks (the engine reads this only in normal mode).
    private (string Key, bool Voice, long At)? _lastPeek;
    private const long PeekFreshMs = 30_000;

    private static string PeekKey(string name, string? server) => name + "\n" + server;

    private async ValueTask<ExternalCapabilityReceipt?> PeekConversationAsync(JsonElement arguments, CancellationToken cancellationToken)
    {
        string name = RequiredString(arguments, "name");
        string? server = OptionalServer(arguments);
        if (name.Any(char.IsControl) || server?.Any(char.IsControl) == true)
            return null;
        await _interaction.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            _lastPeek = (PeekKey(name, server), false, Environment.TickCount64);
            DesktopRecipientObservation? seen = await _automation.PeekConversationAsync("discord", name, server, cancellationToken)
                .ConfigureAwait(false);
            if (seen is not { VoiceChannel: true, VoiceJoined: false })
                return null;
            _lastPeek = (PeekKey(name, server), true, Environment.TickCount64);
            return new ExternalCapabilityReceipt(
                "client.channel.open",
                false,
                false,
                ExternalJson.Create(writer =>
                {
                    writer.WriteStartObject();
                    writer.WriteNumber("version", 1);
                    writer.WriteBoolean("voiceChannel", true);
                    writer.WriteString("name", name);
                    if ((seen.VoiceServer ?? server) is { } shownServer)
                        writer.WriteString("server", shownServer);
                    writer.WriteBoolean("joinsTheCall", true);
                    writer.WriteEndObject();
                }),
                null) { NeedsConfirmation = true };
        }
        finally
        {
            _interaction.Release();
        }
    }

    private static string? OptionalServer(JsonElement arguments) =>
        arguments.TryGetProperty("server", out JsonElement named) && named.ValueKind == JsonValueKind.String
        && named.GetString() is { } given && !string.IsNullOrWhiteSpace(given)
            ? given.Trim()
            : null;

    public ValueTask<ExternalCapabilityReceipt?> PreflightAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken) =>
        operation == "client.channel.open"
            ? PreflightMayRaise(operation, arguments)
                ? PeekConversationAsync(arguments, cancellationToken)
                : ValueTask.FromResult<ExternalCapabilityReceipt?>(null)
            : PreflightTestDestination(operation, arguments);

    private ValueTask<ExternalCapabilityReceipt?> PreflightTestDestination(string operation, JsonElement arguments) =>
        ValueTask.FromResult(operation == "message.send.test"
            && arguments.ValueKind == JsonValueKind.Object
            && arguments.TryGetProperty("channel", out JsonElement channel)
            && channel.ValueKind == JsonValueKind.String
            && ReadTestDestination(channel.GetString()!) is null
                ? NoTestDestination(arguments)
                : null);

    // The send reached no one: its next leads with the call that reaches the person the call named, filled in
    // (encargo 28: a failure's next that leads with the call was followed; the same route told after it was not).
    private static ExternalCapabilityReceipt NoTestDestination(JsonElement arguments)
    {
        string channel = arguments.GetProperty("channel").GetString()!;
        string? recipient = arguments.TryGetProperty("requestedRecipient", out JsonElement named)
            && named.ValueKind == JsonValueKind.String ? named.GetString() : null;
        string? text = arguments.TryGetProperty("text", out JsonElement said)
            && said.ValueKind == JsonValueKind.String ? said.GetString() : null;
        string? reaching = recipient is null || text is null
            ? null
            : channel == "email"
                ? Baxy.Kernel.Operations.WireNames.Call("email.send", new() { ["to"] = recipient, ["text"] = text })
                : Baxy.Kernel.Operations.WireNames.Call(
                    "message.send", new() { ["channel"] = channel, ["recipient"] = recipient, ["text"] = text });
        string fact = $"this call ran nothing: no test destination is configured for {channel}, so it reaches no one";
        return new ExternalCapabilityReceipt(
            "message.send.test",
            false,
            false,
            ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteNumber("version", 1);
                writer.WriteString("channel", channel);
                writer.WriteBoolean("sent", false);
                writer.WriteString("next", reaching is null
                    ? fact
                    : $"{reaching} sends it to «{recipient}» itself, and the person is asked before it goes; {fact}");
                writer.WriteEndObject();
            }),
            "test_destination_not_configured");
    }

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
                "message.send.test" => await SendTestAsync(arguments, cancellationToken)
                    .ConfigureAwait(false),
                "message.draft" => await DraftAsync(arguments, cancellationToken)
                    .ConfigureAwait(false),
                "message.send" => await SendAsync(arguments, cancellationToken)
                    .ConfigureAwait(false),
                "client.channel.open" => await OpenConversationAsync(arguments, cancellationToken)
                    .ConfigureAwait(false),
                _ => Failure(operation, "external_operation_not_supported"),
            };
        }
        finally
        {
            _interaction.Release();
        }
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
        if ((WithControlCharacters("message.draft", text, TextHasControlCharacters)
                ?? WithControlCharacters("message.draft", recipient, RecipientHasControlCharacters)
                ?? WithoutReadableText("message.draft", text)) is { } refused)
        {
            return refused;
        }

        // D59 §1: a closed client is opened first (app.open of that client, its
        // window waited for on a bounded clock); never sent from here.
        DesktopClientReadiness client = await _automation.EnsureClientOpenAsync(
            channel,
            cancellationToken).ConfigureAwait(false);
        if (!client.Ready)
        {
            return Failure(
                "message.draft",
                client.ErrorCode ?? $"{channel}_client_not_running",
                client.Opened);
        }

        DesktopRecipientObservation observation = await _automation.ResolveAsync(
            channel,
            recipient,
            cancellationToken).ConfigureAwait(false);
        if (Unresolved("message.draft", observation) is { } unresolved)
        {
            return unresolved;
        }

        var resolved = new ResolvedRecipient(
            channel,
            recipient,
            observation.Shown!,
            observation.WindowHandle,
            observation.ProcessId);
        DesktopMessageObservation draft = await _automation.DraftAsync(
            resolved,
            text,
            cancellationToken).ConfigureAwait(false);
        if (!draft.Verified)
        {
            if (draft.ErrorCode == WindowsDesktopMessagingAutomation.ComposerHasPersonDraft)
                return StoppedAtPersonDraft("message.draft", draft);
            ExternalCapabilityReceipt failed = Failure(
                "message.draft",
                draft.ErrorCode ?? "message_draft_not_verified",
                draft.EffectObserved,
                draft.EffectMayHaveOccurred);
            // Uso real 2026-11-03 (F1, 17:20): a draft not seen in the composer is cleared, and the model told «le dejé
            // escrito…» over a result that said only effectUncertain: it says it was not left written.
            return draft.StoppedBeforeEnter is { } step
                ? failed with
                {
                    Result = JsonObject(
                        ("version", 1),
                        ("messageWritten", false),
                        ("sent", false),
                        ("stoppedAt", step),
                        ("displayName", resolved.Shown)),
                }
                : failed;
        }

        return Success(
            "message.draft",
            JsonObject(
                ("version", 1),
                ("channel", channel),
                ("recipient", recipient),
                ("displayName", resolved.Shown),
                ("text", text),
                ("draftVisible", true),
                ("sent", false),
                ("clientOpened", client.Opened),
                ("evidenceHash", draft.EvidenceHash),
                ("draftRead", draft.Read),
                ("draftMatch", draft.Match),
                ("authority", "desktop_client_composer_ocr_postread")));
    }

    // Uso real 2026-11-03 (G6): «abre el chat con X en Discord» had no operation: client.channel.locate opens nothing by
    // design, and an improvised click on a visible row opened another person's chat of a similar name. The conversation
    // is opened by the same lookup message.draft makes (Discord's Ctrl+K switcher, the first row holding the name, never
    // a voice channel's; WhatsApp's chat search and its one exact row), verified by the title or header read afterwards,
    // and nothing is typed in it. A server's channel is matched with its server when one is named.
    private async ValueTask<ExternalCapabilityReceipt> OpenConversationAsync(
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        const string Operation = "client.channel.open";
        string client = RequiredString(arguments, "client");
        string name = RequiredString(arguments, "name");
        string? server = OptionalServer(arguments);
        if (server is not null && client != "discord")
            return Failure(Operation, "server_only_in_discord");
        if ((WithControlCharacters(Operation, name, RecipientHasControlCharacters)
                ?? (server is null ? null : WithControlCharacters(Operation, server, RecipientHasControlCharacters))) is { } refused)
            return refused;

        DesktopClientReadiness ready = await _automation.EnsureClientOpenAsync(client, cancellationToken).ConfigureAwait(false);
        if (!ready.Ready)
            return Failure(Operation, ready.ErrorCode ?? $"{client}_client_not_running", ready.Opened);

        // Uso-128: the read before the yes saw no voice channel under this name: this call's yes (none) does not cover one.
        bool voiceAsked = !(_lastPeek is { Voice: false } peek
            && peek.Key == PeekKey(name, server)
            && Environment.TickCount64 - peek.At < PeekFreshMs);
        _lastPeek = null;
        DesktopRecipientObservation observation = await _automation.OpenConversationAsync(
            client, name, server, voiceAsked, cancellationToken).ConfigureAwait(false);
        if (!observation.Verified || observation.Shown is null)
        {
            return new(
                Operation,
                observation.EffectObserved,
                false,
                ExternalJson.Create(writer =>
                {
                    writer.WriteStartObject();
                    writer.WriteNumber("version", 1);
                    writer.WriteBoolean("opened", false);
                    if (observation.Candidates is { } candidates)
                    {
                        writer.WriteNumber("candidateCount", Math.Max(observation.CandidateCount, candidates.Count));
                        writer.WriteStartArray("candidates");
                        foreach (string candidate in candidates)
                            writer.WriteStringValue(candidate);
                        writer.WriteEndArray();
                    }
                    else if (observation.Shown is not null)
                    {
                        writer.WriteString("observed", observation.Shown);
                    }

                    WriteVoice(writer, observation, name);
                    WriteOpened(writer, observation);
                    writer.WriteEndObject();
                }),
                observation.ErrorCode ?? "conversation_not_verified");
        }

        // Already open, nothing was pressed: its state already reached, with no effect of its own.
        return new(
            Operation,
            observation.EffectObserved,
            true,
            ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteNumber("version", 1);
                writer.WriteString("client", client);
                writer.WriteString("name", name);
                if (server is not null)
                    writer.WriteString("server", server);
                writer.WriteBoolean("opened", true);
                writer.WriteString("openedTitle", observation.Shown);
                writer.WriteBoolean("alreadyOpen", !observation.EffectObserved);
                WriteVoice(writer, observation, name);
                writer.WriteBoolean("clientOpened", ready.Opened);
                writer.WriteBoolean("inFront", observation.InFront);
                writer.WriteBoolean("typed", false);
                writer.WriteString("authority", observation.VoiceJoined
                    ? "discord_voice_panel_postread"
                    : client == "discord" ? "discord_window_title_postread" : "whatsapp_header_ocr_postread");
                writer.WriteEndObject();
            }),
            null)
        {
            StateAlreadyReached = !observation.EffectObserved,
        };
    }

    // Uso real 2026-10-21 (decisión del dueño: «si le pido que mande un mensaje, lo tiene que mandar»): the message is
    // sent to the person named, by the same verified send as the test channel's (written, send pressed, read back in
    // the chat). Its yes is RiskPolicy's (asked in normal mode, not in Bypass); the chat is opened only when its name
    // is exact, as the draft's is.
    private async ValueTask<ExternalCapabilityReceipt> SendAsync(
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        string channel = RequiredString(arguments, "channel");
        string recipient = RequiredString(arguments, "recipient");
        string text = RequiredString(arguments, "text");
        if ((WithControlCharacters("message.send", text, TextHasControlCharacters)
                ?? WithControlCharacters("message.send", recipient, RecipientHasControlCharacters)
                ?? WithoutReadableText("message.send", text)) is { } refused)
        {
            return refused;
        }

        DesktopClientReadiness client = await _automation.EnsureClientOpenAsync(
            channel,
            cancellationToken).ConfigureAwait(false);
        if (!client.Ready)
        {
            return Failure(
                "message.send",
                client.ErrorCode ?? $"{channel}_client_not_running",
                client.Opened);
        }

        DesktopRecipientObservation observation = await _automation.ResolveAsync(
            channel,
            recipient,
            cancellationToken).ConfigureAwait(false);
        if (Unresolved("message.send", observation) is { } unresolved)
        {
            return unresolved;
        }

        var resolved = new ResolvedRecipient(
            channel,
            recipient,
            observation.Shown!,
            observation.WindowHandle,
            observation.ProcessId);
        DesktopMessageObservation sent = await _automation.SendAsync(
            resolved,
            text,
            cancellationToken).ConfigureAwait(false);
        if (!sent.Verified)
        {
            if (sent.ErrorCode == WindowsDesktopMessagingAutomation.ComposerHasPersonDraft)
                return StoppedAtPersonDraft("message.send", sent);
            return SendNotVerified("message.send", sent, resolved.Shown);
        }

        return Success(
            "message.send",
            JsonObject(
                ("version", 1),
                ("channel", channel),
                ("recipient", recipient),
                ("displayName", resolved.Shown),
                ("text", text),
                ("sent", true),
                ("clientOpened", client.Opened),
                ("evidenceHash", sent.EvidenceHash),
                ("deliveryRead", sent.Read),
                ("deliveryMatch", sent.Match),
                ("networkDeliveryRead", false),
                ("authority", sent.ReadByUiAutomation ? "desktop_client_send_uia_postread" : "desktop_client_send_ocr_postread")));
    }

    private async ValueTask<ExternalCapabilityReceipt> SendTestAsync(
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        // MSG §6: a real, verified send whose destination is ALWAYS one of the
        // owner's test destinations. The requested recipient is recorded only so
        // the reply can say the truth («I sent it to your test chat, not to
        // Lucas»); it is never used as the target, so no third party is sent to.
        string channel = RequiredString(arguments, "channel");
        string requestedRecipient = RequiredString(arguments, "requestedRecipient");
        string text = RequiredString(arguments, "text");
        if (ReadTestDestination(channel) is not { } forced)
        {
            return NoTestDestination(arguments);
        }

        if (string.Equals(channel, "email", StringComparison.Ordinal))
        {
            return await SendTestMailAsync(requestedRecipient, forced, text, cancellationToken)
                .ConfigureAwait(false);
        }

        // The owner's test destination is the name typed into the chat search.
        if ((WithControlCharacters("message.send.test", text, TextHasControlCharacters)
                ?? WithControlCharacters("message.send.test", forced, RecipientHasControlCharacters)
                ?? WithoutReadableText("message.send.test", text)) is { } refused)
        {
            return refused;
        }

        // D59 §1: the test channel's client is opened first when it is closed.
        DesktopClientReadiness client = await _automation.EnsureClientOpenAsync(
            channel,
            cancellationToken).ConfigureAwait(false);
        if (!client.Ready)
        {
            return Failure(
                "message.send.test",
                client.ErrorCode ?? $"{channel}_client_not_running",
                client.Opened);
        }

        DesktopRecipientObservation observation = await _automation.ResolveAsync(
            channel,
            forced,
            cancellationToken).ConfigureAwait(false);
        if (Unresolved("message.send.test", observation) is { } unresolved)
        {
            return unresolved;
        }

        var resolved = new ResolvedRecipient(
            channel,
            forced,
            observation.Shown!,
            observation.WindowHandle,
            observation.ProcessId);
        DesktopMessageObservation sent = await _automation.SendAsync(
            resolved,
            text,
            cancellationToken).ConfigureAwait(false);
        if (!sent.Verified)
        {
            if (sent.ErrorCode == WindowsDesktopMessagingAutomation.ComposerHasPersonDraft)
                return StoppedAtPersonDraft("message.send.test", sent);
            return SendNotVerified("message.send.test", sent, resolved.Shown);
        }

        return Success(
            "message.send.test",
            JsonObject(
                ("version", 1),
                ("channel", channel),
                ("requestedRecipient", requestedRecipient),
                ("forcedDestination", forced),
                ("displayName", resolved.Shown),
                ("text", text),
                ("sent", true),
                ("clientOpened", client.Opened),
                ("evidenceHash", sent.EvidenceHash),
                ("deliveryRead", sent.Read),
                ("deliveryMatch", sent.Match),
                // Ronda final 11 (regla 3): the message is read in the chat; whether the network took it (WhatsApp's
                // pending clock, Discord's «could not be delivered») is not read.
                ("networkDeliveryRead", false),
                ("authority", sent.ReadByUiAutomation ? "desktop_client_send_uia_postread" : "desktop_client_send_ocr_postread")));
    }

    // Owner decision 2026-09-18 §3: a mail request is really sent from the owner's
    // classic Outlook profile, always to the owner's own test mailbox; the copy in
    // Sent Items (recipient, text, time) is the delivery evidence.
    private async ValueTask<ExternalCapabilityReceipt> SendTestMailAsync(
        string requestedRecipient,
        string forced,
        string text,
        CancellationToken cancellationToken)
    {
        string subject = MicrosoftAccountAdapter.SubjectFromText(text);
        string input = JsonObject(("to", forced), ("subject", subject), ("text", text)).GetRawText();
        ExternalProcessResult process = await _mailRunner.RunPowerShellAsync(
            MicrosoftAccountAdapter.SendMailScript,
            [Convert.ToBase64String(Encoding.UTF8.GetBytes(input))],
            TimeSpan.FromSeconds(90),
            cancellationToken).ConfigureAwait(false);
        string[] lines = process.Output.Split(['\r', '\n'], StringSplitOptions.RemoveEmptyEntries);
        string line = lines.Length > 0 ? lines[^1] : "{}";
        bool effect = false;
        // The script's own verdict ({ok, effectObserved}); a run that ended without it (PowerShell gone after Send may
        // have run) never says «nothing was sent».
        bool verdict = false;
        string? sentEntryId = null;
        string? sentUtc = null;
        try
        {
            using JsonDocument response = JsonDocument.Parse(line);
            JsonElement root = response.RootElement;
            verdict = root.ValueKind == JsonValueKind.Object
                && root.TryGetProperty("ok", out JsonElement said)
                && said.ValueKind is JsonValueKind.True or JsonValueKind.False
                && root.TryGetProperty("effectObserved", out JsonElement saidEffect)
                && saidEffect.ValueKind is JsonValueKind.True or JsonValueKind.False;
            effect = verdict && root.TryGetProperty("effectObserved", out JsonElement observed)
                && observed.ValueKind == JsonValueKind.True;
            if (root.TryGetProperty("ok", out JsonElement ok) && ok.ValueKind == JsonValueKind.True
                && root.TryGetProperty("sentEntryId", out JsonElement id) && id.ValueKind == JsonValueKind.String
                && root.TryGetProperty("sentUtc", out JsonElement at) && at.ValueKind == JsonValueKind.String)
            {
                sentEntryId = id.GetString();
                sentUtc = at.GetString();
            }
        }
        catch (JsonException)
        {
        }

        if (string.IsNullOrEmpty(sentEntryId) || string.IsNullOrEmpty(sentUtc))
        {
            return Failure(
                "message.send.test",
                effect || !verdict ? "message_delivery_not_verified" : "outlook_mail_send_failed",
                effect,
                effectMayHaveOccurred: !verdict);
        }

        string evidence = Convert.ToHexStringLower(
            SHA256.HashData(Encoding.UTF8.GetBytes(sentEntryId + "|" + sentUtc + "|" + text)));
        return Success(
            "message.send.test",
            JsonObject(
                ("version", 1),
                ("channel", "email"),
                ("requestedRecipient", requestedRecipient),
                ("forcedDestination", forced),
                ("text", text),
                ("sent", true),
                ("evidenceHash", evidence),
                ("authority", "outlook_sent_postread")));
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

    // Renew al máximo (w8): a send that failed after Enter came back with no result (the code and effectObserved only):
    // nothing said Enter was pressed, so «not verified» read as «not sent» and a model sent it again (twice in the chat).
    // It says Enter was pressed, that the message may be in the chat, what was read there and whether the chat still
    // named the recipient; every other failure is as before. Renew al máximo (w9): one stopped just before Enter because
    // the chat no longer named the recipient says the text was typed and not sent.
    // Uso real 2026-11-03 (F1): one that stopped at the draft check came back with no result (effectUncertain alone, for
    // the keys that reached the composer), and the model told «le mandé el mensaje». Every stop before Enter says where
    // it stopped, that Enter was not pressed and that nothing was sent; only the chat check right before Enter leaves
    // the typed text written.
    private static ExternalCapabilityReceipt SendNotVerified(
        string operation,
        DesktopMessageObservation sent,
        string displayName)
    {
        ExternalCapabilityReceipt failure = Failure(
            operation,
            sent.ErrorCode ?? "message_delivery_not_verified",
            sent.EffectObserved,
            sent.EffectMayHaveOccurred || sent.EnterPressed);
        if (!sent.EnterPressed && sent.StoppedBeforeEnter is { } step)
        {
            return failure with
            {
                Result = JsonObject(
                    ("version", 1),
                    ("messageWritten", sent.ErrorCode == WindowsDesktopMessagingAutomation.RecipientChangedBeforeEnter),
                    ("enterPressed", false),
                    ("sent", false),
                    ("stoppedAt", step),
                    ("displayName", displayName)),
            };
        }

        if (!sent.EnterPressed)
        {
            return failure;
        }

        return failure with
        {
            Result = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteNumber("version", 1);
                writer.WriteBoolean("messageWritten", true);
                writer.WriteBoolean("enterPressed", true);
                writer.WriteString("sent", "unknown");
                writer.WriteString("displayName", displayName);
                if (!string.IsNullOrWhiteSpace(sent.Read))
                    writer.WriteString("deliveryRead", sent.Read);
                if (sent.RecipientStillShown is { } shown)
                    writer.WriteBoolean("recipientStillShown", shown);
                if (Infrastructure.ModelAids.On(Infrastructure.ModelAids.MessageTextNext))
                {
                    writer.WriteString("next", "Enter was pressed in the chat of " + displayName
                        + ", so the message may already be there; sending it again may send it twice: say it may "
                        + "have been sent and let the person look at the chat");
                }

                writer.WriteEndObject();
            }),
        };
    }

    private static ExternalCapabilityReceipt Failure(
        string operation,
        string error,
        bool effectObserved = false,
        bool effectMayHaveOccurred = false) =>
        new(operation, effectObserved, false, null, error) { EffectMayHaveOccurred = effectMayHaveOccurred };

    // C2, C3: a recipient is resolved only with what the client showed naming it; a lookup that did not end on the
    // recipient fails with its cause and, when a search row was read, that row as «observed», or the rows of the chat
    // list as «candidates».
    // Uso real 2026-10-21 (e2e del notebook): a lookup that touched the client is an effect that may have occurred, and
    // the model told «le mandé el mensaje»; the message itself was neither written nor sent, and the result says so.
    private static ExternalCapabilityReceipt? Unresolved(string operation, DesktopRecipientObservation observation) =>
        observation.Verified && observation.Shown is not null
            ? null
            : new(
                operation,
                observation.EffectObserved,
                false,
                ExternalJson.Create(writer =>
                {
                    writer.WriteStartObject();
                    writer.WriteNumber("version", 1);
                    writer.WriteBoolean("messageWritten", false);
                    writer.WriteBoolean("sent", false);
                    if (observation.Candidates is { } candidates)
                    {
                        // Ronda final 10 (regla 3): the eight listed are never read as all the chat list held.
                        writer.WriteNumber("candidateCount", Math.Max(observation.CandidateCount, candidates.Count));
                        if (observation.CandidateCount > candidates.Count) writer.WriteBoolean("truncated", true);
                        writer.WriteStartArray("candidates");
                        foreach (string candidate in candidates)
                        {
                            writer.WriteStringValue(candidate);
                        }
                        writer.WriteEndArray();
                    }
                    else if (observation.Shown is not null)
                    {
                        writer.WriteString("observed", observation.Shown);
                    }

                    WriteOpened(writer, observation);
                    writer.WriteEndObject();
                }),
                observation.ErrorCode ?? "recipient_identity_not_verified");

    // Uso-128: a voice channel is a result of its own: what it is, its server, and whether the person is in its call; the
    // microphone is never touched and the call is never left from here (D15, «voice asks and stays, mic as is»).
    private static void WriteVoice(Utf8JsonWriter writer, DesktopRecipientObservation observation, string name)
    {
        if (!observation.VoiceChannel)
            return;
        writer.WriteBoolean("voiceChannel", true);
        if (observation.VoiceServer is { } server)
            writer.WriteString("voiceServer", server);
        if (observation.VoiceJoined)
        {
            writer.WriteBoolean("joined", true);
            writer.WriteBoolean("microphoneTouched", false);
        }
        else if (observation.ErrorCode == WindowsDesktopMessagingAutomation.VoiceJoinNotVerified)
        {
            writer.WriteString("joined", "unknown");
            writer.WriteString("next", $"«{name}» is a voice channel and its row was pressed; the client's voice panel did not say "
                + "the person is in its call, so it is not known whether they are: say that, not that they are in");
        }
        else
        {
            writer.WriteBoolean("joined", false);
            writer.WriteString("next", $"client_channel_open again with these arguments asks the person's yes and enters «{name}»: "
                + "it is a voice channel, it was found, and nothing was pressed");
        }
    }

    // G3: the chat a lookup left open without its header naming the recipient: what the header read and the row clicked.
    private static void WriteOpened(Utf8JsonWriter writer, DesktopRecipientObservation observation)
    {
        // Uso-128: a name no result holds, and names the window shows close to it: the person may have been misheard.
        if (observation.Alike is { Count: > 0 } alike)
        {
            writer.WriteStartArray("alike");
            foreach (string name in alike)
                writer.WriteStringValue(name);
            writer.WriteEndArray();
            writer.WriteString("next", "no result has the name asked for and nothing was opened; the window shows «"
                + string.Join("», «", alike) + "», close to it: ask the person whether they meant that, and open it only if they say so");
        }

        if (observation.HeaderRead is { Count: > 0 } header)
        {
            writer.WriteStartArray("headerRead");
            foreach (string line in header)
                writer.WriteStringValue(line);
            writer.WriteEndArray();
        }

        if (observation.OpenedRow is { } row)
            writer.WriteString("openedRow", row);
    }

    // Renew al máximo (auditoría de flujos): a line break or a tab typed into a chat is a key of its own (Enter types the
    // same WM_CHAR 13, and whether a client sends on it cannot be read), the rule input.text.type keeps (char.IsControl):
    // a text holding one is refused before the client is opened or anything typed, and says how many and which. So is a
    // name typed into the client's chat search (the recipient, or the owner's test destination): an Enter there opens a
    // result.
    private const string TextHasControlCharacters = "message_text_has_control_characters";
    private const string RecipientHasControlCharacters = "message_recipient_has_control_characters";

    internal const string TextNotVerifiable = "message_text_not_verifiable";

    // Renew al máximo (w8): the composer and the sent bubble are verified by OCR on letters and digits only (Fold), so a
    // text with neither («👍», «?!») could never be verified: it was typed, cleared and reported as a draft not verified
    // that may have had an effect. It is refused before the client is opened or anything typed.
    private static ExternalCapabilityReceipt? WithoutReadableText(string operation, string text)
    {
        if (WindowsDesktopMessagingAutomation.Fold(text).Length > 0)
        {
            return null;
        }

        return new(
            operation,
            false,
            false,
            ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteNumber("version", 1);
                writer.WriteBoolean("messageWritten", false);
                writer.WriteBoolean("sent", false);
                if (Infrastructure.ModelAids.On(Infrastructure.ModelAids.MessageTextNext))
                {
                    writer.WriteString("next", "nothing was written: what is written in a chat is verified by reading its "
                        + "letters and digits, and this text has none; a text with at least one word can be sent");
                }

                writer.WriteEndObject();
            }),
            TextNotVerifiable);
    }

    private static ExternalCapabilityReceipt? WithControlCharacters(string operation, string text, string errorCode)
    {
        char[] found = [.. text.Where(char.IsControl)];
        if (found.Length == 0)
        {
            return null;
        }

        return new(
            operation,
            false,
            false,
            ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteNumber("version", 1);
                writer.WriteBoolean("messageWritten", false);
                writer.WriteBoolean("sent", false);
                writer.WriteNumber("controlCharacterCount", found.Length);
                writer.WriteStartArray("controlCharacters");
                foreach (char character in found.Distinct())
                {
                    writer.WriteStringValue($"U+{(int)character:X4}");
                }

                writer.WriteEndArray();
                writer.WriteEndObject();
            }),
            errorCode);
    }

    // A flow stopped at the person's own draft in the composer, before the message was typed: nothing written or sent.
    private static ExternalCapabilityReceipt StoppedAtPersonDraft(string operation, DesktopMessageObservation observation) =>
        new(operation, observation.EffectObserved, false, JsonObject(("version", 1), ("messageWritten", false), ("sent", false)),
            WindowsDesktopMessagingAutomation.ComposerHasPersonDraft)
        { EffectMayHaveOccurred = observation.EffectMayHaveOccurred };

    private static JsonElement JsonObject(params (string Name, object? Value)[] values)
    {
        var buffer = new ArrayBufferWriter<byte>();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            writer.WriteStartObject();
            foreach ((string name, object? value) in values)
            {
                switch (value)
                {
                    case null:
                        writer.WriteNull(name);
                        break;
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

    // Al máximo, flujos: IExternalCapabilityProvider.PreflightAsync, for the operations this adapter claims.
    ValueTask<ExternalCapabilityReceipt?> PreflightAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken) =>
        ValueTask.FromResult<ExternalCapabilityReceipt?>(null);

    // Renew al máximo (guarda diálogo destructivo): IExternalCapabilityProvider.PreflightMayRaise, for its operations.
    bool PreflightMayRaise(string operation, JsonElement arguments) => false;
}

// G6: what a lookup opens: a message's recipient, or a conversation asked for by name (client.channel.open), which
// may be a server's channel (Server, when named: its switcher row and its title must also name that server).
internal sealed record ChatTarget(string Name, bool Conversation = false, string? Server = null)
{
    internal bool RowNames(string row) =>
        (Conversation && WindowsDesktopMessagingAutomation.VoiceChannelRow(row)
            ? WindowsDesktopMessagingAutomation.NamesRecipient(WindowsDesktopMessagingAutomation.RowOwnName(row), Name)
            : WindowsDesktopMessagingAutomation.RowNamesRecipient(row, Name))
        && (Server is null || WindowsDesktopMessagingAutomation.ContainsPhrase(row, Server));

    // Uso-128: whether this lookup may press a voice channel's row (its yes was asked, or nothing asks: Bypass), and whether it
    // only reads what the name is, pressing nothing.
    internal bool VoiceAsked { get; init; }

    internal bool Peek { get; init; }

    internal bool TitleNames(string title) => Conversation
        ? WindowsDesktopMessagingAutomation.TitleNamesConversation(title, Name, Server)
        : WindowsDesktopMessagingAutomation.TitleNamesRecipient(title, Name);
}

// Name: the recipient the model asked for, matched (folded, whole) against what the client shows. Shown: what the
// client showed for it when it was resolved (its window title or conversation header).
internal sealed record ResolvedRecipient(
    string Channel,
    string Name,
    string Shown,
    nint WindowHandle,
    int ProcessId);

// Shown: the title or header line that names the recipient when Verified; otherwise the search row read last, if any.
// Candidates: the lines of a chat list read when no single row of it was the recipient.
internal sealed record DesktopRecipientObservation(
    bool Verified,
    bool EffectObserved,
    nint WindowHandle,
    int ProcessId,
    string? ErrorCode,
    string? Shown = null)
{
    internal IReadOnlyList<string>? Candidates { get; init; }

    // Ronda final 10: how many distinct lines the chat list gave; Candidates holds the first eight.
    internal int CandidateCount { get; init; }

    // G3 (uso real 2026-11-03): a chat opened whose header (or window title) did not name the recipient: what it read
    // there, and the search row that was clicked to open it.
    internal IReadOnlyList<string>? HeaderRead { get; init; }

    internal string? OpenedRow { get; init; }

    // G6: a conversation opened to be seen: whether its window holds the front now.
    internal bool InFront { get; init; }

    // Uso-128: the name is a voice channel's; VoiceJoined: the client's voice panel says the person is in it.
    internal bool VoiceChannel { get; init; }

    internal bool VoiceJoined { get; init; }

    internal string? VoiceServer { get; init; }

    // Uso-128: names the window shows close to one no result holds.
    internal IReadOnlyList<string>? Alike { get; init; }
}

// Read and Match (C4): the text read where the message was looked for, and «exact» or «tolerant» (TextMatch).
// Renew al máximo (w8): an OCR read: its passes joined (Text, what every other reader takes) and each pass alone.
internal sealed record OcrText(string Text, IReadOnlyList<string> Passes)
{
    public static implicit operator string(OcrText read) => read.Text;
}

internal sealed record DesktopMessageObservation(
    bool Verified,
    bool EffectObserved,
    string EvidenceHash,
    string? ErrorCode,
    string? Read = null,
    string? Match = null)
{
    // Keys reached the composer without positive evidence of what they left (EffectObserved stays false).
    internal bool EffectMayHaveOccurred { get; init; }

    // Renew al máximo (w8): Enter was pressed in the chat; a failure after it is a message that may be there.
    internal bool EnterPressed { get; init; }

    // After Enter: whether the chat's header still named the recipient (null: not read).
    internal bool? RecipientStillShown { get; init; }

    // Uso real 2026-11-05 (G3): the message was read in the chat as a text element of the page, not by OCR.
    internal bool ReadByUiAutomation { get; init; }

    // Uso real 2026-11-03 (F1): the step of a send that stopped before Enter was pressed (window_check, chat_check,
    // composer_focus, draft_check, chat_check_before_enter); null when the flow ended elsewhere or the step is not known.
    internal string? StoppedBeforeEnter { get; init; }

    // Ronda B: the typed text was not seen in the composer and what was typed here is cleared (it was empty before,
    // C5); the keys reached it, and a part of the text may remain, so the failure says an effect may have occurred.
    internal static DesktopMessageObservation DraftNotVerified() =>
        new(false, false, string.Empty, "message_draft_not_verified") { EffectMayHaveOccurred = true, StoppedBeforeEnter = "draft_check" };
}

// D59 §1 (owner, 2026-10-02): WhatsApp and Discord are installed and signed in on
// this PC, so a message request that finds the client closed opens it first.
// Ready: the client's window is up (already, or after the open); Opened: the
// product opened it in this turn; ErrorCode when it could not be made ready.
internal sealed record DesktopClientReadiness(bool Ready, bool Opened, string? ErrorCode)
{
    internal static readonly DesktopClientReadiness AlreadyOpen = new(true, false, null);
}

internal interface IDesktopMessagingAutomation
{
    ValueTask<DesktopClientReadiness> EnsureClientOpenAsync(
        string channel,
        CancellationToken cancellationToken);

    ValueTask<DesktopRecipientObservation> ResolveAsync(
        string channel,
        string recipient,
        CancellationToken cancellationToken);

    // G6: client.channel.open's lookup (ChatTarget with Conversation).
    ValueTask<DesktopRecipientObservation> OpenConversationAsync(
        string channel,
        string name,
        string? server,
        CancellationToken cancellationToken);

    // Uso-128: the same, saying whether this call may press a voice channel's row (ChatTarget.VoiceAsked).
    ValueTask<DesktopRecipientObservation> OpenConversationAsync(
        string channel,
        string name,
        string? server,
        bool voiceAsked,
        CancellationToken cancellationToken) =>
        OpenConversationAsync(channel, name, server, cancellationToken);

    // Uso-128: what the name is, read in the switcher and closed, pressing nothing; null when it could not be read.
    ValueTask<DesktopRecipientObservation?> PeekConversationAsync(
        string channel,
        string name,
        string? server,
        CancellationToken cancellationToken) =>
        ValueTask.FromResult<DesktopRecipientObservation?>(null);

    ValueTask<DesktopMessageObservation> SendAsync(
        ResolvedRecipient recipient,
        string text,
        CancellationToken cancellationToken);

    ValueTask<DesktopMessageObservation> DraftAsync(
        ResolvedRecipient recipient,
        string text,
        CancellationToken cancellationToken);
}

internal sealed partial class WindowsDesktopMessagingAutomation : IDesktopMessagingAutomation
{
    private const ushort VirtualKeyControl = 0x11;
    private const ushort VirtualKeyK = 0x4B;
    private const ushort VirtualKeyReturn = 0x0D;
    private const ushort VirtualKeyA = 0x41;
    private const ushort VirtualKeyBack = 0x08;
    private const ushort VirtualKeyEscape = 0x1B;
    private const ushort VirtualKeyRight = 0x27;
    private const uint KeyUp = 0x0002;
    private const uint Unicode = 0x0004;

    // D59 §1: after the client's open is verified, its main window must show its content (Discord draws an updater
    // splash first) within its cold-start clock (ClientColdStart, data).
    private static readonly TimeSpan ClientReadyPoll = TimeSpan.FromMilliseconds(250);

    private WindowsInstalledApplicationOpenProvider? _clientOpener;
    private readonly IForegroundLease? _lease;

    private readonly Func<string?> _ocrEngine;

    internal WindowsDesktopMessagingAutomation(
        IClientInteractionProbe probe,
        IForegroundLease? lease = null,
        Func<string?>? ocrEngine = null)
    {
        Probe = new ContentWindowProbe(probe ?? throw new ArgumentNullException(nameof(probe)));
        _lease = lease;
        _ocrEngine = ocrEngine ?? AnyOcrEngine;
    }

    /// <summary>
    /// Renew al máximo (auditoría de flujos): no OCR engine was found, so neither the chat's name (WhatsApp's header)
    /// nor the typed or sent message could be read; nothing was opened, typed or sent.
    /// </summary>
    internal const string OcrUnavailable = "message_ocr_unavailable";

    // v3 point 0, fix 3: the client is driven with the real keyboard and mouse (its chat search, composer and quick
    // switcher expose no pattern this flow can use), so each resolve, send and draft runs inside one burst of the
    // foreground lease: after the person's pause, every key and click asks the burst first, and the window in front
    // and the cursor are given back at the end.
    private IForegroundLease Lease => _lease ?? ForegroundLease.Shared;

    // Ronda 24: what says a client's window is ready to be used (content shown, a search input in focus). TZ-DC2: it
    // reads through the Core's own UI Automation worker, never a second one started by the first search.
    private ContentWindowProbe Probe { get; }

    // The lease's refusal in this adapter's words: a window that could not be brought up is the focus not verified.
    internal static string LeaseStop(string code) =>
        code == "input_window_not_in_front" ? "messaging_focus_not_verified" : code;

    /// <summary>
    /// A flow stopped after it began typing into a conversation (the person's input, or the window losing the front)
    /// and the conversation's composer no longer looks as before: text may be left there, and the person's next Enter
    /// in that chat would send it. Said so, never as a bare «stopped halfway».
    /// </summary>
    internal const string DraftLeftAfterInterruption = "message_draft_left_after_interruption";

    /// <summary>
    /// C5: the conversation's composer already held text (the person's draft), seen before anything was deleted or
    /// typed: it is left as it was and the flow stops, nothing written.
    /// </summary>
    internal const string ComposerHasPersonDraft = "composer_has_person_draft";

    /// <summary>
    /// Renew al máximo (w9): the text was typed and seen in the composer, and just before Enter the chat's header no
    /// longer named the recipient: Enter was not pressed, nothing was sent, and the text typed is left in the composer.
    /// </summary>
    internal const string RecipientChangedBeforeEnter = "message_recipient_changed_before_enter";

    /// <summary>
    /// Encargo 98: the keys that select a field's text depend on the application's language, and the flow goes on to
    /// delete what is selected. A dialog the last resort raised stops the flow here, before any Backspace.
    /// </summary>
    internal const string FieldSelectOpenedDialog = "message_field_select_opened_dialog";

    internal const string FieldSelectDialogLeftOpen = "message_field_select_dialog_left_open";

    private static readonly WindowsDesktopKeyboard RaisedWindows = new();

    private static async ValueTask SelectFocusedFieldAsync(
        ContentWindowProbe probe,
        nint handle,
        CancellationToken cancellationToken)
    {
        LeasedInput.EnsureMayAct();
        FieldSelection selection = await FocusedFieldSelection.SelectAsync(
            handle,
            probe.SelectFocusedTextAsync,
            static () => SendChord(VirtualKeyControl, VirtualKeyA),
            RaisedWindows,
            cancellationToken).ConfigureAwait(false);
        if (selection.DialogTitle is not null)
            throw new LeasedInput.BurstStoppedException(selection.DialogClosed ? FieldSelectOpenedDialog : FieldSelectDialogLeftOpen);
    }

    // C5: selecting takes whatever the focused field holds. When that field is the conversation's composer and it holds
    // text, the composer's picture (composer, taken just before) changes under the selection; a placeholder is not
    // selectable and a blinking caret is not a change. Text found is left as it was, the selection collapsed to its
    // end, and true is returned. Nothing is deleted here.
    // e2e nb-28/nb-29 (Discord, intermittent): the composer band also holds the foot of the conversation, which settles
    // for a moment after the chat opens; a «before» taken while it moved made the select-all check see a change that
    // stayed (composer_has_person_draft with the composer empty). The band is read until two reads agree (a blinking
    // caret aside), for at most two seconds; the last read is the one used.
    private static async ValueTask<byte[]> SettledComposerAsync(nint handle, string channel, CancellationToken cancellationToken)
    {
        byte[] read = CaptureRegion(handle, CaptureArea.Composer, channel);
        for (int look = 0; look < 8; look++)
        {
            await Task.Delay(250, cancellationToken).ConfigureAwait(false);
            byte[] next = CaptureRegion(handle, CaptureArea.Composer, channel);
            bool settled = !ContentChanged(read, next);
            read = next;
            if (settled)
            {
                break;
            }
        }

        return read;
    }
    private static async ValueTask<bool> ComposerHoldsTextAsync(
        ContentWindowProbe probe,
        nint handle,
        string channel,
        byte[] composer,
        CancellationToken cancellationToken)
    {
        await SelectFocusedFieldAsync(probe, handle, cancellationToken).ConfigureAwait(false);
        await Task.Delay(150, cancellationToken).ConfigureAwait(false);
        if (!ContentChanged(composer, CaptureRegion(handle, CaptureArea.Composer, channel)))
        {
            return false;
        }

        // e2e nb-28 (Discord, intermittent): a selection stays drawn, a blinking caret comes and goes. The change is
        // looked at twice more across a blink; a composer seen as it was before is empty.
        for (int look = 0; look < 2; look++)
        {
            await Task.Delay(300, cancellationToken).ConfigureAwait(false);
            if (!ContentChanged(composer, CaptureRegion(handle, CaptureArea.Composer, channel)))
            {
                return false;
            }
        }

        SendKey(VirtualKeyRight);
        return true;
    }

    /// <summary>
    /// The stop of a flow that was typing near a conversation's composer: when the composer changed since
    /// <paramref name="composerBefore"/> (compared without any input, by its picture) the stop says text was left
    /// there; otherwise it keeps its own code.
    /// </summary>
    internal static LeasedInput.BurstStoppedException ComposerAfterStop(
        LeasedInput.BurstStoppedException stop,
        bool composerChanged) =>
        composerChanged ? new LeasedInput.BurstStoppedException(DraftLeftAfterInterruption, stop) : stop;

    private static bool ComposerChanged(nint handle, string channel, byte[]? composerBefore)
    {
        if (composerBefore is null)
        {
            // No picture from before: nothing proves the composer is as it was.
            return true;
        }

        try
        {
            // Uso real 2026-11-05 (G6, a name no chat has, on the real client): the focus coming back to the composer shows
            // its caret, and that was read as the name left there: «identity not verified» instead of «not found».
            return ContentChanged(composerBefore, CaptureRegion(handle, CaptureArea.Composer, channel));
        }
        catch (Exception exception) when (exception is IOException or InvalidOperationException or ExternalException)
        {
            // Not readable: the text may be there.
            return true;
        }
    }

    private static async ValueTask<byte[]?> TrySettledComposerAsync(nint handle, string channel, CancellationToken cancellationToken)
    {
        try
        {
            return await SettledComposerAsync(handle, channel, cancellationToken).ConfigureAwait(false);
        }
        catch (Exception exception) when (exception is IOException or InvalidOperationException or ExternalException)
        {
            return null;
        }
    }

    public async ValueTask<DesktopClientReadiness> EnsureClientOpenAsync(
        string channel,
        CancellationToken cancellationToken)
    {
        // Renew al máximo (auditoría de flujos): every flow reads the chat by OCR; without an engine it would type into the
        // person's chat, never see the text and clear it. Nothing is opened or typed then.
        if (_ocrEngine() is null)
        {
            return new(false, false, OcrUnavailable);
        }

        // The reads that prove a window ready start now, off the turn: a client already open never waits for them.
        Probe.Prewarm();
        (nint shown, _) = FindWindow(channel);
        // Uso-128 («abre Discord y ve a…»: the window was there, drawing its loading screen or its updater, and the search that
        // followed found nothing to work on): a window that answers without content, not minimized, gets its cold-start clock
        // to show it; one that does not answer is left as it was, and a client already drawn never waits. Nothing is launched.
        if (shown != 0)
        {
            ClientInteraction now = await Probe.ReadAsync(shown, content: true, cancellationToken).ConfigureAwait(false);
            if (!now.Answered || ClientInteractionReady(now) || IsIconic(shown))
                return DesktopClientReadiness.AlreadyOpen;
            return await AwaitWindowContentAsync(channel, opened: false, cancellationToken).ConfigureAwait(false);
        }

        // Uso-128: its process started moments ago and has no window yet: it is coming; a second launch would only duplicate.
        if (StartedMomentsAgo(channel))
            return await AwaitWindowContentAsync(channel, opened: false, cancellationToken).ConfigureAwait(false);

        // The same app.open the person can ask for: the installed client is
        // resolved from the Start catalog and launched (or its tray instance
        // shown), and its window verified.
        _clientOpener ??= new WindowsInstalledApplicationOpenProvider();
        ApplicationOpenResult opened = await _clientOpener.OpenAsync(
            new ApplicationOpenRequest(ClientApplicationName(channel), "msgclient_" + Guid.NewGuid().ToString("N")),
            cancellationToken).ConfigureAwait(false);
        if (ClientOpenFailure(channel, opened) is { } failure)
        {
            return failure;
        }

        return await AwaitWindowContentAsync(channel, opened: true, cancellationToken).ConfigureAwait(false);
    }

    private static bool StartedMomentsAgo(string channel)
    {
        TimeSpan coldStart = ClientColdStart.For(ClientApplicationName(channel));
        string[] names = string.Equals(channel, "whatsapp", StringComparison.Ordinal) ? WhatsAppProcesses : DiscordProcesses;
        foreach (string name in names)
        {
            Process[] processes = Process.GetProcessesByName(name);
            try
            {
                foreach (Process process in processes)
                {
                    try
                    {
                        if (DateTime.Now - process.StartTime < coldStart)
                            return true;
                    }
                    catch (Exception exception) when (exception is InvalidOperationException or System.ComponentModel.Win32Exception)
                    {
                        // Gone or not readable: says nothing of a client starting.
                    }
                }
            }
            finally
            {
                foreach (Process process in processes)
                    process.Dispose();
            }
        }

        return false;
    }

    private async ValueTask<DesktopClientReadiness> AwaitWindowContentAsync(
        string channel,
        bool opened,
        CancellationToken cancellationToken)
    {
        // Encargo CS (banco fz1 s14): one clock for the whole start, as long as the client may take cold (data per
        // application); a window still without content when it runs out says the client is still starting.
        TimeSpan coldStart = ClientColdStart.For(ClientApplicationName(channel));
        var clock = Stopwatch.StartNew();
        ContentWait content = ContentWait.Unanswered;
        while (clock.Elapsed < coldStart)
        {
            (nint handle, _) = FindWindow(channel);
            if (handle != 0)
            {
                // Uso real 2026-11-05 (G6, Discord closed): a client that was left minimized opens minimized (its own
                // settings remember it), and a minimized window draws nothing: no content was ever read and the clock ran
                // out at «still starting». It was opened to be used: it is brought up.
                if (IsIconic(handle))
                    _ = VisibleControlSurface.BringToFront(handle);

                // Ronda 24 (t1-c09, t2-c07, t3-c07), C14: ready is a window that shows content a person interacts
                // with (an editable field or a list), read by the probe. Its title is not (the loading screen and the
                // updater splash already carry the client's name), nor is a fixed settle. Encargo CS: a splash gives
                // way to the main window, another window, so it is looked for again while the clock lasts; so is a
                // window the probe could not read yet.
                TimeSpan left = coldStart - clock.Elapsed;
                content = await AwaitClientContentAsync(
                    token => Probe.ReadAsync(handle, content: true, token),
                    left < ClientContentBudget ? left : ClientContentBudget,
                    ClientReadyPoll,
                    cancellationToken).ConfigureAwait(false);
                if (content == ContentWait.Ready)
                {
                    return new(true, opened, null);
                }

                continue;
            }

            await Task.Delay(ClientReadyPoll, cancellationToken).ConfigureAwait(false);
        }

        return new(
            false,
            opened,
            content == ContentWait.NotShown ? ClientStillStarting(channel) : ClientReadyUnread(channel));
    }

    /// <summary>Encargo CS: the client was launched and its main window did not show its content within its cold start.</summary>
    internal static string ClientStillStarting(string channel) => $"{channel}_client_still_starting";

    /// <summary>C14: the client was launched and its window could not be read within its cold start: not said ready.</summary>
    internal static string ClientReadyUnread(string channel) => $"{channel}_client_ready_not_verified";

    internal static string ClientApplicationName(string channel) =>
        string.Equals(channel, "whatsapp", StringComparison.Ordinal) ? "WhatsApp" : "Discord";

    // Not found in the installed applications' catalog is said as such (ronda final: not «not installed», the catalog
    // is what was read); any other open failure leaves the client unverified (the launch may have happened).
    internal static DesktopClientReadiness? ClientOpenFailure(string channel, ApplicationOpenResult opened) =>
        opened.Succeeded && opened.Verified
            ? null
            : string.Equals(opened.ErrorCode, ApplicationOpenErrorCodes.ApplicationNotFound, StringComparison.Ordinal)
                ? new(false, false, $"{channel}_client_not_found")
                : new(false, opened.Receipt.LaunchIssued, $"{channel}_client_open_not_verified");

    public ValueTask<DesktopRecipientObservation> ResolveAsync(
        string channel,
        string recipient,
        CancellationToken cancellationToken) =>
        LookUpAsync(channel, new ChatTarget(recipient), cancellationToken);

    public ValueTask<DesktopRecipientObservation> OpenConversationAsync(
        string channel,
        string name,
        string? server,
        CancellationToken cancellationToken) =>
        OpenConversationAsync(channel, name, server, voiceAsked: true, cancellationToken);

    public async ValueTask<DesktopRecipientObservation?> PeekConversationAsync(
        string channel,
        string name,
        string? server,
        CancellationToken cancellationToken)
    {
        if (FindWindow(channel).Handle == 0)
            return null;
        return await LookUpAsync(
            channel, new ChatTarget(name, Conversation: true, server) { Peek = true }, cancellationToken).ConfigureAwait(false);
    }

    public async ValueTask<DesktopRecipientObservation> OpenConversationAsync(
        string channel,
        string name,
        string? server,
        bool voiceAsked,
        CancellationToken cancellationToken)
    {
        DesktopRecipientObservation opened = await LookUpAsync(
            channel, new ChatTarget(name, Conversation: true, server) { VoiceAsked = voiceAsked }, cancellationToken).ConfigureAwait(false);
        // Uso real 2026-11-05 (G6): the lease gives the front back when its flow ends, as it should for a message sent in
        // passing, and a window it found minimized goes back to minimized; here the person asked to see this chat, as
        // with an app they ask to open, and it was left behind what they had. Whether it came up is said.
        return opened.Verified
            ? opened with { InFront = VisibleControlSurface.BringToFront(opened.WindowHandle) }
            : opened;
    }

    private async ValueTask<DesktopRecipientObservation> LookUpAsync(
        string channel,
        ChatTarget target,
        CancellationToken cancellationToken)
    {
        (nint handle, int processId) = FindWindow(channel);
        if (handle == 0)
        {
            return new(false, false, 0, 0, $"{channel}_client_not_running");
        }

        return await LeasedInput.RunAsync(
            Lease,
            handle,
            token => InNormalizedWindowAsync(
                channel,
                handle,
                flow => ResolveInBurstAsync(channel, target, handle, processId, Probe, flow),
                token),
            (code, sent) => new DesktopRecipientObservation(false, sent, handle, processId, LeaseStop(code)),
            cancellationToken).ConfigureAwait(false);
    }

    // Uso real 2026-11-05 (the fake client, a key of the person's during client.channel.open): the stop sends nothing more, so
    // the search it had opened stays open; the same call again, which the receipt offers, then found the focus in a dialog
    // and refused (recipient_not_opened, again and again). Marked from the shortcut until the search is closed; the flow
    // that follows soon after closes it, and any other dialog found later is the person's and is left alone.
    private static readonly ConcurrentDictionary<nint, long> SwitcherLeftOpen = new();
    private const long SwitcherLeftOpenMs = 120_000;

    // Uso-128 (real client, a voice channel's row): the switcher stayed open over the window after a call that ended unverified,
    // for it was closed only by a focus read inside it. Whatever way the flow ended, with no key of the person's in between (a
    // stop goes on as SwitcherLeftOpen says), a dialog that was not open before the flow is closed, read by itself.
    private static async ValueTask<DesktopRecipientObservation> ResolveInBurstAsync(
        string channel,
        ChatTarget target,
        nint handle,
        int processId,
        ContentWindowProbe probe,
        CancellationToken cancellationToken)
    {
        if (!string.Equals(channel, "discord", StringComparison.Ordinal))
            return await ResolveStepsAsync(channel, target, handle, processId, probe, cancellationToken).ConfigureAwait(false);
        int? dialogsBefore = await probe.OpenDialogsAsync(handle, cancellationToken).ConfigureAwait(false);
        DesktopRecipientObservation result = await ResolveStepsAsync(channel, target, handle, processId, probe, cancellationToken)
            .ConfigureAwait(false);
        if (dialogsBefore is { } before)
        {
            for (int press = 0;
                press < SwitcherClosePresses
                    && await probe.OpenDialogsAsync(handle, cancellationToken).ConfigureAwait(false) is { } open
                    && open > before;
                press++)
            {
                SendKey(VirtualKeyEscape);
                await Task.Delay(300, cancellationToken).ConfigureAwait(false);
            }
        }

        // Uso-128: a name no result holds: the names the window shows close to it, read with the search closed.
        if (result is { Verified: false, ErrorCode: RecipientNotFound or "recipient_search_not_read" })
        {
            IReadOnlyList<string> rows = await probe.ShownRowsAsync(handle, cancellationToken).ConfigureAwait(false);
            IReadOnlyList<string> alike = AlikeNames(target.Name, result.Shown is { } row ? rows.Append(row) : rows);
            if (alike.Count > 0)
                return result with { Alike = alike };
        }

        return result;
    }

    private static async ValueTask<DesktopRecipientObservation> ResolveStepsAsync(
        string channel,
        ChatTarget target,
        nint handle,
        int processId,
        ContentWindowProbe probe,
        CancellationToken cancellationToken)
    {
        string recipient = target.Name;
        // Uso-128: already in that call (the voice panel says so): nothing is pressed, and that is the state already reached.
        if (target.Conversation && string.Equals(channel, "discord", StringComparison.Ordinal)
            && await probe.VoicePanelAsync(handle, DisconnectButtonNames, cancellationToken).ConfigureAwait(false) is { Connected: true } inCall
            && PlaceNames(inCall.Place, recipient, target.Server))
        {
            return new(true, false, handle, processId, null, inCall.Place)
            {
                VoiceChannel = true,
                VoiceJoined = true,
                VoiceServer = PlaceServer(inCall.Place),
            };
        }

        if (SwitcherLeftOpen.TryRemove(handle, out long leftAt) && Environment.TickCount64 - leftAt < SwitcherLeftOpenMs)
        {
            await CloseSwitcherAsync(token => probe.ReadAsync(handle, content: false, token), cancellationToken).ConfigureAwait(false);
        }

        // The header is read twice because the first frame after a resize or
        // focus change may still be transitional. (Escape must not be sent here:
        // in WhatsApp it closes the open conversation.)
        for (int attempt = 0; attempt < 2; attempt++)
        {
            if (await ShownRecipientAsync(handle, channel, recipient, cancellationToken, reread: false, target)
                    .ConfigureAwait(false)
                is { } shownAlready)
            {
                return new(true, false, handle, processId, null, shownAlready);
            }

            await Task.Delay(500, cancellationToken).ConfigureAwait(false);
        }

        string? openedRow = null;
        if (string.Equals(channel, "whatsapp", StringComparison.Ordinal))
        {
            // The «Chats» sidebar icon first, so an archived or other view cannot hide the chat search, and a result is
            // opened only if the open conversation's composer did not change while the name was typed: with the archived
            // view open, Ctrl+F focused nothing and «Música» + Enter went into the open chat as a message (MSGSEND1845,
            // owner's deliberate test).
            ClickAt(handle, SidebarChatsLogicalX, SidebarChatsLogicalY);
            await Task.Delay(300, cancellationToken).ConfigureAwait(false);
            // Uso real 2026-11-05 (G6): the search was clicked at a fixed point, and this client's design has moved it
            // (UI Automation: its field at 97-114 logical px down, the filter chips from 126, the point at 124). The field
            // is found where it is and the name goes on only with that field holding the focus; otherwise nothing is typed.
            if (ChatSearchField(await probe.EditableFieldsAsync(handle, cancellationToken).ConfigureAwait(false), WindowBox(handle))
                is not { } search)
            {
                return new(false, true, handle, processId, SearchFocusNotVerified);
            }

            ClickAtScreen(search.Box.CentreX, search.Box.CentreY);
            if (!await PollUntilAsync(
                    async token => HoldsTheFocus(search, await probe.EditableFieldsAsync(handle, token).ConfigureAwait(false)),
                    SearchFocusBudget,
                    InteractionPoll,
                    cancellationToken).ConfigureAwait(false))
            {
                return new(false, true, handle, processId, SearchFocusNotVerified);
            }

            byte[] composerBefore = CaptureRegion(handle, CaptureArea.Composer, channel);
            try
            {
                // C5: the search's old query is cleared only when the selection did not land on text in the
                // conversation's composer (the search not focused, the person's draft there).
                if (await ComposerHoldsTextAsync(probe, handle, channel, composerBefore, cancellationToken).ConfigureAwait(false))
                {
                    // Ronda final 12 (regla 3): the clicks and the selection already reached the client: an effect.
                return new(false, true, handle, processId, ComposerHasPersonDraft);
                }

                SendKey(VirtualKeyBack);
                SendText(recipient);
                await Task.Delay(350, cancellationToken).ConfigureAwait(false);
                if (ContentChanged(composerBefore, CaptureRegion(handle, CaptureArea.Composer, channel)))
                {
                    // The composer held no text before (C5), so this clears only the name typed into it.
                    await SelectFocusedFieldAsync(probe, handle, cancellationToken).ConfigureAwait(false);
                    SendKey(VirtualKeyBack);
                    return new(false, true, handle, processId, SearchFocusNotVerified);
                }

                // Auditoría final: the result is not taken blind with Enter. The chat list under the search box is
                // read, and only the one row that is the recipient is clicked; none, or several, and the search is
                // emptied again (the name went only into it) and the rows read come back as candidates.
                ChatListRead rows = await ReadChatListAsync(handle, recipient, cancellationToken).ConfigureAwait(false);
                if (rows.Hits.Count != 1)
                {
                    await SelectFocusedFieldAsync(probe, handle, cancellationToken).ConfigureAwait(false);
                    SendKey(VirtualKeyBack);
                    return UnresolvedChatList(handle, processId, rows.Lines, recipient);
                }

                openedRow = rows.Row;
                ClickAt(handle, rows.Hits[0].X, rows.Hits[0].Y);
            }
            catch (LeasedInput.BurstStoppedException stop)
            {
                // MSGSEND1845's cleanup did not run: if the name went into the open chat's composer, it is still there.
                throw ComposerAfterStop(stop, ComposerChanged(handle, channel, composerBefore));
            }
        }
        else
        {
            // DISCORD1839 inherited, driven from here: Ctrl+K opens the switcher and the name is typed; its active result
            // is opened only when it names the recipient (C3). The keys travel through the same SendInput path that
            // already sends WhatsApp messages; a PowerShell helper stole the foreground, which closes the switcher.
            // Rondas finales 26-29 (regla 3): no Escape first; no key with the focus already inside a dialog or a window
            // that did not answer; the switcher counts as open only with a new focus inside a dialog of the page (the
            // shortcut once more, then refused, on any client); the closing Escape only with the focus still in it.
            ValueTask<ClientInteraction> Read(CancellationToken token) => probe.ReadAsync(handle, content: false, token);
            // Ronda final 26 (regla 3): no Escape before the switcher is seen open: in Discord it marks the open channel
            // read, declines a call or cancels an edit of the person's. The focus before the shortcut is read as it is.
            ClientInteraction before = await Read(cancellationToken).ConfigureAwait(false);
            // The open conversation's composer, pictured before the shortcut (MSGSEND1845's check): only a composer
            // that looks the same once the search is closed lets the turn say nothing was written (revisión 1 de r24:
            // a cold client can focus its composer by itself while the shortcut does nothing yet).
            // Uso real 2026-11-05: read once it has settled, as a window just brought up or restored is still being drawn.
            byte[]? composerBefore = await TrySettledComposerAsync(handle, channel, cancellationToken).ConfigureAwait(false);
            // Ronda final 28 (regla 3): a focus inside a dialog may be the switcher already open: no key is sent
            // (Ctrl+K would close it and the name would reach the person's message box). Ronda final 29: nor with a
            // window that did not answer the read (since ronda 27 the name is never typed then, so a key would only
            // toggle the switcher).
            if (!before.Answered || SearchStateUnknown(before.Focused))
            {
                return UnverifiedChat(handle, processId, composerUntouched: true);
            }

            SwitcherLeftOpen[handle] = Environment.TickCount64;
            SendChord(VirtualKeyControl, VirtualKeyK);
            InputWait input = await AwaitOpenedInputAsync(
                Read, before, SearchInputBudget, InteractionPoll, cancellationToken).ConfigureAwait(false);

            if (AfterSearchWait(input, retried: false) == SearchStep.Retry)
            {
                // The shortcut once more, without an Escape onto whatever holds the focus.
                SendChord(VirtualKeyControl, VirtualKeyK);
                input = await AwaitOpenedInputAsync(
                    Read, before, SearchInputRetryBudget, InteractionPoll, cancellationToken).ConfigureAwait(false);
            }

            if (AfterSearchWait(input, retried: true) == SearchStep.Refuse)
            {
                // Ronda final 12 (regla 3): Ctrl+K reached the client: an effect, though nothing was typed (ronda final
                // 26: no Escape onto a focus not read as the switcher's).
                return UnverifiedChat(handle, processId, composerUntouched: true) with { EffectObserved = true };
            }

            // C5: the switcher opens with an empty input, so nothing is deleted before the name; a selection that
            // shows text in the conversation's composer means the keys go there, onto the person's draft.
            if (await ComposerHoldsTextAsync(
                    probe, handle, channel, CaptureRegion(handle, CaptureArea.Composer, channel), cancellationToken)
                .ConfigureAwait(false))
            {
                // Ronda final 12 (regla 3): the clicks and the selection already reached the client: an effect.
                return new(false, true, handle, processId, ComposerHasPersonDraft);
            }

            SendText(recipient);
            (bool named, string? row) = await AwaitNamedResultAsync(
                Read, target.RowNames, InteractionPoll, cancellationToken).ConfigureAwait(false);
            ClientFocus? active = named ? (await Read(cancellationToken).ConfigureAwait(false)).Focused : null;
            if (active is { InDialog: true, Box: { } rowBox } && target.RowNames(active.Name))
            {
                // No stray modifier key-up is sent here: a lone Alt release activates
                // the window menu in Chromium and closed the switcher, so the click
                // below landed on the conversation behind it.
                // The result is opened with the mouse: Enter only dismisses the
                // switcher on this client (the capture after typing shows the row
                // highlighted, the one after Enter shows the previous chat with the
                // composer focused). Uso real 2026-11-05: the row clicked is the active one that named the recipient,
                // where UI Automation says it is, never a share of the window's height another row may lie at.
                bool voiceRow = VoiceChannelRow(active.Name);
                // Uso-128: the read before the yes presses nothing: what the name is goes back, and the switcher is closed.
                if (target.Peek || (voiceRow && !target.VoiceAsked))
                {
                    await CloseSwitcherAsync(Read, cancellationToken).ConfigureAwait(false);
                    _ = SwitcherLeftOpen.TryRemove(handle, out _);
                    return new(false, !target.Peek, handle, processId, target.Peek ? null : VoiceChannelNotPressed)
                    {
                        VoiceChannel = voiceRow,
                        VoiceServer = voiceRow ? VoiceRowServer(active.Name) : null,
                    };
                }

                ClickAtScreen(rowBox.CentreX, rowBox.CentreY);
                if (voiceRow)
                {
                    // Uso-128: pressing a voice channel's row joins its call. It counts only when the client's voice panel
                    // says that channel; no other key follows and nothing leaves the call afterwards (D15).
                    _ = SwitcherLeftOpen.TryRemove(handle, out _);
                    VoicePanel panel = new(false, null);
                    bool joined = await PollUntilAsync(
                        async token =>
                        {
                            panel = await probe.VoicePanelAsync(handle, DisconnectButtonNames, token).ConfigureAwait(false);
                            return panel.Connected && PlaceNames(panel.Place, recipient, target.Server);
                        },
                        VoiceJoinBudget,
                        ChatTitlePoll,
                        cancellationToken).ConfigureAwait(false);
                    return joined
                        ? new(true, true, handle, processId, null, panel.Place)
                        {
                            VoiceChannel = true,
                            VoiceJoined = true,
                            VoiceServer = PlaceServer(panel.Place),
                        }
                        : new(false, true, handle, processId, VoiceJoinNotVerified, panel.Place)
                        {
                            VoiceChannel = true,
                            VoiceServer = VoiceRowServer(active.Name),
                        };
                }

                _ = SwitcherLeftOpen.TryRemove(handle, out _);
                // The title is read for up to 3 s from the click (r23 c07: one read at 900 ms missed a title that came
                // later), and the first read that names the recipient ends the wait.
                string? shown = null;
                string? account = target.Server is null ? RowAccount(active.Name, recipient) : null;
                bool opened = await PollUntilAsync(
                    async token =>
                    {
                        shown = await ShownRecipientAsync(handle, channel, recipient, token, target: target).ConfigureAwait(false);
                        // Uso real 2026-11-05 (G6): one person can show under two names, the switcher's «Ana, usuario, ana.91»
                        // and the title's «@Bea»; a row whose name is exactly the one asked for gives the account, and the
                        // direct chat left open showing it in its header (measured: a button there, no other element of the
                        // window), with the switcher read closed, says it is that row's person.
                        if (shown is null && account is not null && DirectChatTitle(WindowTitle(handle))
                            && await Read(token).ConfigureAwait(false) is { Answered: true, Focused: not { InDialog: true } }
                            && ShownInHeader(
                                await probe.ShownNameBoxesAsync(handle, account, token).ConfigureAwait(false),
                                WindowBox(handle),
                                (int)((HeaderRowTopAt96Dpi + HeaderRowHeightAt96Dpi) * (GetDpiForWindow(handle) / 96.0))))
                        {
                            shown = WindowTitle(handle);
                        }

                        return shown is not null;
                    },
                    ChatTitleBudget,
                    ChatTitlePoll,
                    cancellationToken).ConfigureAwait(false);
                if (opened)
                {
                    return new(true, true, handle, processId, null, shown);
                }
            }
            else if (named)
            {
                // The active row moved off the name before it could be clicked: nothing was opened, and the name is not
                // said absent either.
                (named, row) = (false, null);
            }

            // C3: no result named the recipient, so nothing was clicked; the switcher (open even when it was not seen)
            // is closed. After a named row that did not open the chat, the search is closed only when it was seen
            // open. The name should have gone only into the switcher's own input: the composer is pictured again; a
            // composer that changed (or cannot be read) may hold the name.
            // Ronda final 27 (regla 3): only a switcher seen open is closed (the name is typed only into one now).
            // Ronda final 29 (regla 3): and only while it still holds the focus, read now (a click on a named row
            // closes it and opens that chat, where an Escape would decline a call).
            if (input == InputWait.Opened)
            {
                await CloseSwitcherAsync(Read, cancellationToken).ConfigureAwait(false);
                _ = SwitcherLeftOpen.TryRemove(handle, out _);
            }

            bool composerChanged = true;
            if (input == InputWait.Opened)
            {
                // The switcher's backdrop takes a moment to fade off the band.
                composerChanged = !await PollUntilAsync(
                    _ => ValueTask.FromResult(!ComposerChanged(handle, channel, composerBefore)),
                    SearchInputBudget,
                    InteractionPoll,
                    cancellationToken).ConfigureAwait(false);
            }

            DesktopRecipientObservation unverified = UnverifiedChat(handle, processId, ComposerUntouched(input, composerChanged));
            // Ronda final 30 (regla 3): a named row was clicked: the shortcut, the name and the click reached the client.
            // G6 (uso real 2026-11-03): the chat it left open is said by its title and the row clicked, as WhatsApp's
            // header (G3), so the model knows whose chat is on screen.
            return named
                ? unverified with
                {
                    EffectObserved = true,
                    HeaderRead = WindowTitle(handle) is { Length: > 0 } title ? [title] : null,
                    OpenedRow = row,
                }
                : NotNamedInSearch(unverified, row);
        }

        await Task.Delay(900, cancellationToken).ConfigureAwait(false);
        (string? header, OcrText read) = await ReadWhatsAppHeaderAsync(handle, recipient, cancellationToken).ConfigureAwait(false);
        return header is not null
            ? new(true, true, handle, processId, null, header)
            : NotNamedInHeader(handle, processId, read, openedRow);
    }

    // Uso real 2026-11-03 (G3): the one row that was the recipient was clicked and the header did not name them; the
    // failure said only that, and the model could only try again. It says what the header read (its lines, the most
    // read first) and the row that was clicked, for the model to ask the person or name the chat as it is shown.
    internal static DesktopRecipientObservation NotNamedInHeader(nint handle, int processId, OcrText read, string? openedRow) =>
        new(false, true, handle, processId, "recipient_identity_not_verified")
        {
            HeaderRead = [.. read.Passes.SelectMany(pass => pass.Split('\n'))
                .Select(line => line.Trim())
                .Where(line => Fold(line).Length > 0)
                .GroupBy(line => line, StringComparer.Ordinal)
                .OrderByDescending(group => group.Count())
                .Select(group => group.Key)
                .Take(4)],
            OpenedRow = openedRow,
        };

    public async ValueTask<DesktopMessageObservation> SendAsync(
        ResolvedRecipient recipient,
        string text,
        CancellationToken cancellationToken)
    {
        if (!ProcessStillOwnsWindow(recipient.WindowHandle, recipient.ProcessId))
        {
            return new(false, false, string.Empty, "messaging_focus_not_verified") { StoppedBeforeEnter = "window_check" };
        }

        return await LeasedInput.RunAsync(
            Lease,
            recipient.WindowHandle,
            token => InNormalizedWindowAsync(
                recipient.Channel,
                recipient.WindowHandle,
                flow => SendInBurstAsync(Probe, recipient, text, flow),
                token),
            (code, sent) => new DesktopMessageObservation(false, sent, string.Empty, LeaseStop(code)),
            cancellationToken).ConfigureAwait(false);
    }

    private static async ValueTask<DesktopMessageObservation> SendInBurstAsync(
        ContentWindowProbe probe,
        ResolvedRecipient recipient,
        string text,
        CancellationToken cancellationToken)
    {
        bool targetVerified = await StillShownAsync(recipient, cancellationToken).ConfigureAwait(false);
        if (!targetVerified)
        {
            return new(false, false, string.Empty, "recipient_identity_changed") { StoppedBeforeEnter = "chat_check" };
        }

        if (!FocusComposer(recipient.WindowHandle, recipient.Channel))
        {
            // Ronda final 18 (regla 3): part of the click may have reached the window before the focus failed.
            return new(false, false, string.Empty, "message_composer_not_focused")
            {
                EffectMayHaveOccurred = true,
                StoppedBeforeEnter = "composer_focus",
            };
        }

        await Task.Delay(200, cancellationToken).ConfigureAwait(false);
        // C5: the composer is read before anything is typed; the person's draft there is never cleared.
        byte[] before = await SettledComposerAsync(recipient.WindowHandle, recipient.Channel, cancellationToken).ConfigureAwait(false);
        if (await ComposerHoldsTextAsync(probe, recipient.WindowHandle, recipient.Channel, before, cancellationToken)
                .ConfigureAwait(false))
        {
            // Ronda final 18 (regla 3): the composer was already clicked into (FocusComposer): an effect, though
            // nothing was typed over the person's draft.
            return new(false, false, string.Empty, ComposerHasPersonDraft) { EffectMayHaveOccurred = true };
        }

        // F1 (2026-11-03): the typed text is read from its own band (ComposerBandLeft), compared with that band now.
        byte[] textBefore = CaptureRegion(recipient.WindowHandle, CaptureArea.ComposerText, recipient.Channel);
        int inChatBefore = await MessagesInChatAsync(probe, recipient, text, cancellationToken).ConfigureAwait(false);
        byte[] beforeSend;
        byte[] beforePane;
        try
        {
            SendText(text);

            MessageVisualObservation draftObservation = await ObserveTypedDraftAsync(
                recipient, text, textBefore, cancellationToken).ConfigureAwait(false);
            if (!draftObservation.Verified)
            {
                // The composer was empty before (C5): only the text typed here is cleared.
                await SelectFocusedFieldAsync(probe, recipient.WindowHandle, cancellationToken).ConfigureAwait(false);
                SendKey(VirtualKeyBack);
                return DesktopMessageObservation.DraftNotVerified();
            }

            // The delivery is read from the band of last messages just above the
            // composer, where the new outgoing bubble appears; the whole pane never
            // reads it (MSGSEND1845: «hola» sent and visible, pane OCR without it).
            beforeSend = CaptureRegion(recipient.WindowHandle, CaptureArea.LastMessages, recipient.Channel);
            // The same rows over the whole pane, the widest read below: an old bubble with these words anywhere there
            // before Enter is not the delivery.
            beforePane = CaptureRegion(recipient.WindowHandle, CaptureArea.LastMessages, recipient.Channel, 0);
            if (!await PressEnterInVerifiedChatAsync(
                    token => StillShownAsync(recipient, token),
                    () => SendKey(VirtualKeyReturn),
                    cancellationToken).ConfigureAwait(false))
            {
                return new(false, false, string.Empty, RecipientChangedBeforeEnter)
                {
                    EffectMayHaveOccurred = true,
                    StoppedBeforeEnter = "chat_check_before_enter",
                };
            }
        }
        catch (LeasedInput.BurstStoppedException stop)
        {
            // Stopped between the first character and Enter: the message, whole or in part, may sit in the composer.
            throw ComposerAfterStop(
                stop, ComposerChanged(recipient.WindowHandle, recipient.Channel, before));
        }
        catch (Exception failure) when (failure is IOException or InvalidOperationException or ExternalException
            or OperationCanceledException)
        {
            // FT/proveedores goal (review of receipts): a capture, a read or a key that failed mid-way (a black capture
            // with the PC locked, the window gone, the OCR not starting, a cancel) left the text in the composer
            // unsaid, and the person's next Enter would send it; when the composer changed, that is what is said.
            if (ComposerChanged(recipient.WindowHandle, recipient.Channel, before))
                throw new LeasedInput.BurstStoppedException(DraftLeftAfterInterruption, failure);
            throw;
        }

        return await SentReadBackAsync(
            token => ReadBackAfterEnterAsync(probe, recipient, text, inChatBefore, beforeSend, beforePane, token),
            cancellationToken).ConfigureAwait(false);
    }

    /// <summary>
    /// Renew al máximo (w9): the chat was verified before typing, and the typed draft's OCR takes seconds; its header is
    /// read again just before Enter, and Enter is pressed only while it still names the recipient. Otherwise nothing is
    /// pressed or cleared (the composer in front may be another chat's) and the text typed is said to be left there.
    /// </summary>
    internal static async ValueTask<bool> PressEnterInVerifiedChatAsync(
        Func<CancellationToken, ValueTask<bool>> recipientShown,
        Action pressEnter,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(recipientShown);
        ArgumentNullException.ThrowIfNull(pressEnter);
        if (!await recipientShown(cancellationToken).ConfigureAwait(false))
        {
            return false;
        }

        pressEnter();
        return true;
    }

    /// <summary>
    /// The read-back of a message whose Enter was already pressed. Renew al máximo (auditoría de flujos): a capture, a
    /// read or a cancel that failed here escaped as a bare provider failure, and the message may already be in the chat
    /// (a model told «failed» sends it again); it is said as a delivery not verified, with its effect observed.
    /// </summary>
    internal static async ValueTask<DesktopMessageObservation> SentReadBackAsync(
        Func<CancellationToken, ValueTask<DesktopMessageObservation>> readBack,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(readBack);
        try
        {
            return await readBack(cancellationToken).ConfigureAwait(false);
        }
        catch (Exception failure) when (failure is IOException or InvalidOperationException or ExternalException
            or OperationCanceledException)
        {
            return new(false, true, string.Empty, "message_delivery_not_verified") { EnterPressed = true };
        }
    }

    // Uso real 2026-11-05 (G3, WhatsApp): the message reached the chat and the read said «unknown»: OCR read its line broken by
    // the panel beside it («… ignorar este G Mensajes temporales / mensaje»). This client's page has the message whole, as a
    // text element with exactly its words. One more of them in the conversation's pane than before Enter is the delivery; the
    // list of chats beside it (its preview shows the same words) and the box it was typed in do not count, and an old bubble
    // with the same words does not count by itself. OCR stays for what the page does not expose so (a text with an emoji).
    internal static readonly TimeSpan MessageInChatBudget = TimeSpan.FromSeconds(2);

    private static async ValueTask<int> MessagesInChatAsync(
        ContentWindowProbe probe,
        ResolvedRecipient recipient,
        string text,
        CancellationToken cancellationToken)
    {
        double scale = GetDpiForWindow(recipient.WindowHandle) / 96.0;
        return InConversationPane(
            await probe.ShownNameBoxesAsync(recipient.WindowHandle, text.Trim(), cancellationToken).ConfigureAwait(false),
            WindowBox(recipient.WindowHandle),
            (int)(ConversationPaneOffsetAt96Dpi(recipient.Channel) * scale));
    }

    internal static int InConversationPane(IReadOnlyList<ScreenBox> places, ScreenBox window, int paneOffset) =>
        places.Count(place => place.Left >= window.Left + paneOffset);

    private static async ValueTask<DesktopMessageObservation> ReadBackAfterEnterAsync(
        ContentWindowProbe probe,
        ResolvedRecipient recipient,
        string text,
        int inChatBefore,
        byte[] beforeSend,
        byte[] beforePane,
        CancellationToken cancellationToken)
    {
        await Task.Delay(900, cancellationToken).ConfigureAwait(false);
        byte[] after = CaptureRegion(recipient.WindowHandle, CaptureArea.LastMessages, recipient.Channel);
        if (await PollUntilAsync(
                async token => await MessagesInChatAsync(probe, recipient, text, token).ConfigureAwait(false) > inChatBefore,
                MessageInChatBudget,
                InteractionPoll,
                cancellationToken).ConfigureAwait(false))
        {
            bool inRecipientsChat = await StillShownAsync(recipient, cancellationToken).ConfigureAwait(false);
            return new(
                inRecipientsChat,
                true,
                Convert.ToHexStringLower(SHA256.HashData(after)),
                inRecipientsChat ? null : "message_delivery_not_verified",
                text.Trim(),
                "exact") { EnterPressed = true, RecipientStillShown = inRecipientsChat, ReadByUiAutomation = true };
        }

        OcrText afterText = await ReadTextAsync(after, cancellationToken).ConfigureAwait(false);
        string afterHash = Convert.ToHexStringLower(SHA256.HashData(after));
        bool changed = !CryptographicOperations.FixedTimeEquals(
            SHA256.HashData(beforeSend),
            SHA256.HashData(after));
        // The bubble's small text takes the same one-letter OCR noise as the
        // header title («probanda» for «probando»), so the tolerant word match
        // applies here too; the band changed and the header still names the
        // destination, which no other chat's text can satisfy at once. C4: the
        // receipt says the text read and whether it matched exactly or tolerantly.
        string deliveryRead = afterText.Text;
        string? match = TextMatch(afterText, text);
        if (match is null)
        {
            // A long message's bubble is wider than the narrow right-end band
            // (MSGCLAR1851: «prueba 1 de WhatsApp, ya funciona de nuevo» sent and
            // read as «atsApp, ya funciona de nuevo»): the same newest-bubble rows
            // are read again over a wider band, then over the whole pane. The
            // narrow band stays first because over the full band a short bubble
            // drowned in the wallpaper.
            foreach (int bandWidth in new[] { OutgoingBubbleBandWidthAt96Dpi * 2, 0 })
            {
                byte[] wider = CaptureRegion(
                    recipient.WindowHandle, CaptureArea.LastMessages, recipient.Channel, bandWidth);
                OcrText widerText = await ReadTextAsync(wider, cancellationToken).ConfigureAwait(false);
                match = TextMatch(widerText, text);
                if (match is not null)
                {
                    deliveryRead = widerText.Text;
                    afterHash = Convert.ToHexStringLower(SHA256.HashData(wider));
                    break;
                }
            }
        }

        bool stillTarget = await StillShownAsync(recipient, cancellationToken).ConfigureAwait(false);
        // Ronda final: a band that already showed the text before Enter (an old bubble with the same words) proves
        // nothing by showing it after: only text that was not there is the delivery.
        bool shownBefore = match is not null
            && (TextMatch(await ReadTextAsync(beforeSend, cancellationToken).ConfigureAwait(false), text) is not null
                || TextMatch(await ReadTextAsync(beforePane, cancellationToken).ConfigureAwait(false), text) is not null);
        bool delivered = changed && match is not null && !shownBefore && stillTarget;
        return new(
            delivered,
            true,
            afterHash,
            delivered ? null : "message_delivery_not_verified",
            deliveryRead.Trim(),
            match) { EnterPressed = true, RecipientStillShown = stillTarget };
    }

    public async ValueTask<DesktopMessageObservation> DraftAsync(
        ResolvedRecipient recipient,
        string text,
        CancellationToken cancellationToken)
    {
        // MSG1837: the same path as a send up to the verified draft, then stop.
        if (!ProcessStillOwnsWindow(recipient.WindowHandle, recipient.ProcessId))
        {
            return new(false, false, string.Empty, "messaging_focus_not_verified");
        }

        return await LeasedInput.RunAsync(
            Lease,
            recipient.WindowHandle,
            token => InNormalizedWindowAsync(
                recipient.Channel,
                recipient.WindowHandle,
                flow => DraftInBurstAsync(Probe, recipient, text, flow),
                token),
            (code, sent) => new DesktopMessageObservation(false, sent, string.Empty, LeaseStop(code)),
            cancellationToken).ConfigureAwait(false);
    }

    private static async ValueTask<DesktopMessageObservation> DraftInBurstAsync(
        ContentWindowProbe probe,
        ResolvedRecipient recipient,
        string text,
        CancellationToken cancellationToken)
    {
        bool targetVerified = await StillShownAsync(recipient, cancellationToken).ConfigureAwait(false);
        if (!targetVerified)
        {
            return new(false, false, string.Empty, "recipient_identity_changed");
        }

        if (!FocusComposer(recipient.WindowHandle, recipient.Channel))
        {
            // Ronda final 18 (regla 3): part of the click may have reached the window before the focus failed.
            return new(false, false, string.Empty, "message_composer_not_focused") { EffectMayHaveOccurred = true };
        }

        await Task.Delay(200, cancellationToken).ConfigureAwait(false);
        // C5: the composer is read before anything is typed; the person's draft there is never cleared.
        byte[] before = await SettledComposerAsync(recipient.WindowHandle, recipient.Channel, cancellationToken).ConfigureAwait(false);
        if (await ComposerHoldsTextAsync(probe, recipient.WindowHandle, recipient.Channel, before, cancellationToken)
                .ConfigureAwait(false))
        {
            // Ronda final 18 (regla 3): the composer was already clicked into (FocusComposer): an effect, though
            // nothing was typed over the person's draft.
            return new(false, false, string.Empty, ComposerHasPersonDraft) { EffectMayHaveOccurred = true };
        }

        // F1 (2026-11-03): the typed text is read from its own band (ComposerBandLeft), compared with that band now.
        byte[] textBefore = CaptureRegion(recipient.WindowHandle, CaptureArea.ComposerText, recipient.Channel);
        MessageVisualObservation draftObservation;
        try
        {
            SendText(text);

            draftObservation = await ObserveTypedDraftAsync(
                recipient, text, textBefore, cancellationToken).ConfigureAwait(false);
            if (!draftObservation.Verified)
            {
                // The composer was empty before (C5): only the text typed here is cleared.
                await SelectFocusedFieldAsync(probe, recipient.WindowHandle, cancellationToken).ConfigureAwait(false);
                SendKey(VirtualKeyBack);
                return DesktopMessageObservation.DraftNotVerified();
            }
        }
        catch (LeasedInput.BurstStoppedException stop)
        {
            // A draft stopped while being typed, or while its unverified text was being cleared: part of it may remain.
            throw ComposerAfterStop(
                stop, ComposerChanged(recipient.WindowHandle, recipient.Channel, before));
        }
        catch (Exception failure) when (failure is IOException or InvalidOperationException or ExternalException
            or OperationCanceledException)
        {
            // FT/proveedores goal (review of receipts): a capture, a read or a key that failed mid-way (a black capture
            // with the PC locked, the window gone, the OCR not starting, a cancel) left the text in the composer
            // unsaid, and the person's next Enter would send it; when the composer changed, that is what is said.
            if (ComposerChanged(recipient.WindowHandle, recipient.Channel, before))
                throw new LeasedInput.BurstStoppedException(DraftLeftAfterInterruption, failure);
            throw;
        }

        return new(
            true,
            true,
            Convert.ToHexStringLower(SHA256.HashData(draftObservation.Bitmap)),
            null,
            draftObservation.Read,
            draftObservation.Match);
    }

    // Typed text reaches a busy client's composer late: during a turn on the
    // notebook Discord showed it 0.6 to 0.85 s after typing (G1, 2026-10-11,
    // three sends polled without OCR) and not yet 2.6 s later while an OCR pass
    // held the CPU, so a 350 ms horizon failed and text that landed after the
    // clean-up went out with the next message. The band is polled without OCR
    // until its content changes and holds still (a caret blink is not a change),
    // and only then read, up to the horizon.
    private static async ValueTask<MessageVisualObservation> ObserveTypedDraftAsync(
        ResolvedRecipient recipient,
        string text,
        byte[] before,
        CancellationToken cancellationToken)
    {
        Stopwatch clock = Stopwatch.StartNew();
        byte[]? previous = null;
        byte[]? read = null;
        while (true)
        {
            byte[] bitmap = CaptureRegion(recipient.WindowHandle, CaptureArea.ComposerText, recipient.Channel);
            // Past the horizon the frame is read once more whether or not it held still: a read that outlasted the
            // horizon must not leave the text that landed meanwhile unseen.
            bool expired = clock.ElapsedMilliseconds >= TypedDraftHorizonMs;
            if (previous is not null && ContentChanged(before, bitmap)
                && (expired || !ContentChanged(previous, bitmap))
                && (read is null || ContentChanged(read, bitmap)))
            {
                read = bitmap;
                OcrText observed = await ReadTextAsync(bitmap, cancellationToken).ConfigureAwait(false);
                if (TextMatch(observed, text) is { } match)
                {
                    return new(bitmap, true, observed.Text.Trim(), match);
                }
            }

            if (expired)
            {
                return new(bitmap, false, null, null);
            }

            previous = bitmap;
            await Task.Delay(TypedDraftPollMs, cancellationToken).ConfigureAwait(false);
        }
    }

    private const int TypedDraftHorizonMs = 3000;
    private const int TypedDraftPollMs = 50;
    // A text caret is one or two pixels wide; a typed glyph, or the placeholder
    // that goes away with the first one, spans more columns than this.
    // Uso real 2026-10-21 (e2e del notebook, 125 %): Discord's caret blinking off changed 5 columns (measured on two
    // screenshots of an empty composer, nothing else changed), and an empty composer passed for the person's draft
    // (composer_has_person_draft); 6 also holds a caret at 150 %. A selection or the placeholder spans far more.
    internal const int CaretMaxWidthPixels = 6;

    // Whether two captures of the same band differ by more than a blinking caret:
    // the differing pixels must span more columns than a caret.
    internal static bool ContentChanged(byte[] before, byte[] after)
    {
        const int header = 54;
        if (before.Length != after.Length || before.Length < header)
        {
            return true;
        }

        int width = BinaryPrimitives.ReadInt32LittleEndian(before.AsSpan(18));
        int stride = width * 4;
        int left = int.MaxValue;
        int right = -1;
        for (int offset = header; offset + 3 < before.Length; offset += 4)
        {
            if (before[offset] != after[offset] || before[offset + 1] != after[offset + 1]
                || before[offset + 2] != after[offset + 2])
            {
                int column = (offset - header) % stride / 4;
                left = Math.Min(left, column);
                right = Math.Max(right, column);
            }
        }

        return right >= 0 && right - left + 1 > CaretMaxWidthPixels;
    }

    // What the open conversation shows when it names the recipient: Discord's window title, or the line of
    // WhatsApp's header that does; null when it names someone else or nothing. G3: «reread» false skips the Spanish
    // reading (HeaderNameAsync), for the look at whether the chat is already open, which a search settles otherwise.
    // G6: a conversation opened by name (client.channel.open) is matched by its own title rule (ChatTarget).
    private static async ValueTask<string?> ShownRecipientAsync(
        nint handle,
        string channel,
        string recipient,
        CancellationToken cancellationToken,
        bool reread = true,
        ChatTarget? target = null)
    {
        if (string.Equals(channel, "discord", StringComparison.Ordinal))
        {
            string title = WindowTitle(handle);
            return (target ?? new ChatTarget(recipient)).TitleNames(title) ? title : null;
        }

        return (await ReadWhatsAppHeaderAsync(handle, recipient, cancellationToken, reread).ConfigureAwait(false)).Named;
    }

    // Whether the chat a recipient was resolved to is still the one open: what ShownRecipientAsync reads, or the very title
    // it was resolved with (a person under two names, whose title never holds the name asked for: see the switcher's row).
    private static async ValueTask<bool> StillShownAsync(ResolvedRecipient recipient, CancellationToken cancellationToken) =>
        (string.Equals(recipient.Channel, "discord", StringComparison.Ordinal)
            && string.Equals(WindowTitle(recipient.WindowHandle), recipient.Shown, StringComparison.Ordinal))
        || await ShownRecipientAsync(recipient.WindowHandle, recipient.Channel, recipient.Name, cancellationToken)
            .ConfigureAwait(false) is not null;

    // Uso real 2026-11-05 (G6, a name no chat has, on the real client): with a query typed, the first Escape only took the
    // focus from the active row to the input (read: ListItem, then ComboBox, both in the dialog), and the search stayed open
    // over the chat. It is pressed again while the focus read is still in the dialog, no more than this.
    private const int SwitcherClosePresses = 3;

    private static async ValueTask CloseSwitcherAsync(
        Func<CancellationToken, ValueTask<ClientInteraction>> read,
        CancellationToken cancellationToken)
    {
        for (int press = 0;
            press < SwitcherClosePresses
                && (await read(cancellationToken).ConfigureAwait(false)).Focused is { InDialog: true };
            press++)
        {
            SendKey(VirtualKeyEscape);
            await Task.Delay(300, cancellationToken).ConfigureAwait(false);
        }
    }

    // WhatsApp's header: the line that names the recipient (null when none does) and the reading it came from.
    private static async ValueTask<(string? Named, OcrText Read)> ReadWhatsAppHeaderAsync(
        nint handle,
        string recipient,
        CancellationToken cancellationToken,
        bool reread = true)
    {
        byte[] header = CaptureRegion(handle, CaptureArea.Header, "whatsapp");
        return await HeaderNameAsync(header, recipient, cancellationToken, reread).ConfigureAwait(false);
    }

    // The header crop read and matched as the flow reads it (HeaderNameAsync); without Tesseract's Spanish model, as on a
    // machine whose runtime has none (spanishModel false).
    internal static async ValueTask<string?> ReadHeaderNameAsync(
        byte[] header,
        string recipient,
        CancellationToken cancellationToken,
        bool spanishModel = true) =>
        (await HeaderNameAsync(header, recipient, cancellationToken, spanishModel: spanishModel).ConfigureAwait(false))
        .Named;

    // G3 (held-out): the English model the reads were tuned with has no «ñ» and reads a Spanish name otherwise
    // («Feña» as «Fenia» or «Feha», «Don Hernán» as «Don Hernan fi»), while the Spanish one the runtime ships
    // (tessdata-fast, as CaptureVisionAdapter reads) reads «Feña», «Don Hernán». A header the English reading does not
    // name is read once more with it when it is there; a name is still only ever accepted exactly. The reading said
    // is the last one made.
    // Encargo 33: that model is no asset of the repository and the PC's runtime has none, so there «Feña» failed every
    // time. Without it the header is read once more by Windows' own OCR in the person's language (the first OCR
    // authority of capture.screenshot's ocr.read; es-MX on both machines reads «Feña» and «Don Hernán»), and only its
    // exact line names the recipient.
    private static async ValueTask<(string? Named, OcrText Read)> HeaderNameAsync(
        byte[] header,
        string recipient,
        CancellationToken cancellationToken,
        bool reread = true,
        bool spanishModel = true)
    {
        OcrText read = await ReadTextAsync(header, cancellationToken).ConfigureAwait(false);
        if ((HeaderLine(read, recipient)
                ?? await PictureTailNameAsync(header, read, recipient, cancellationToken).ConfigureAwait(false)) is { } named)
            return (named, read);
        if (!reread)
            return (null, read);
        if (!spanishModel || FindTesseract() is not { } executable
            || CaptureVisionAdapter.FindTessdata(executable, "es", out string spanish) is not { } tessdata)
        {
            OcrText windowsRead = await ReadWindowsTextAsync(header, cancellationToken).ConfigureAwait(false);
            return windowsRead.Passes.Count == 0 ? (null, read) : (HeaderLine(windowsRead, recipient), windowsRead);
        }

        OcrLanguage language = new(spanish, tessdata);
        OcrText spanishRead = await ReadTextAsync(header, cancellationToken, language).ConfigureAwait(false);
        return (HeaderLine(spanishRead, recipient)
            ?? await PictureTailNameAsync(header, spanishRead, recipient, cancellationToken, language).ConfigureAwait(false),
            spanishRead);
    }

    // Windows' OCR in the person's profile language, its lines as one pass; none when Windows has no engine for it.
    private static async ValueTask<OcrText> ReadWindowsTextAsync(byte[] bitmap, CancellationToken cancellationToken)
    {
        IReadOnlyList<WindowsVisibleOcrLocator.LayoutLine>? lines = await WindowsVisibleOcrLocator
            .ReadLayoutAsync(bitmap, int.MaxValue, cancellationToken).ConfigureAwait(false);
        if (lines is null)
            return new OcrText(string.Empty, []);
        string text = string.Join('\n', lines.Select(static line => line.Text));
        return new OcrText(text, [text]);
    }

    // A Tesseract language other than the engine's English, and the folder its model is in.
    private sealed record OcrLanguage(string Code, string Tessdata);

    // Uso real 2026-11-03 (G3): a contact saved with an emoji after its name («Rey 👑») is drawn by the client in colour
    // after the name, and Tesseract reads that picture as a symbol (folded away) or, for some, as letters («Rey wr»,
    // «Luna J»: 16 of 108 headers rendered in Chromium, both themes, 100-150 %), which failed every send to that chat.
    // A reading of the name with one word more is read again with Tesseract's word boxes (TSV), and that last word is
    // set aside only when its box is drawn in colour (ColourShare): a letter of the name is never coloured (0.00-0.01
    // measured, a trailing «B» or «Rosa» included; the emoji 0.13 and up, a muted 💼 0.59), so «Ana B» never passes for
    // «Ana».
    private static async ValueTask<string?> PictureTailNameAsync(
        byte[] header,
        OcrText read,
        string recipient,
        CancellationToken cancellationToken,
        OcrLanguage? language = null)
    {
        if (!read.Passes.SelectMany(pass => pass.Split('\n')).Any(line => OneWordAfterName(line, recipient))
            || FindTesseract() is not { } executable)
            return null;
        foreach ((byte[] copy, int scale) in new[] { (header, 1), (Upscale2x(header), 2) })
        {
            string boxes = await RunTesseractAsync(executable, copy, cancellationToken, boxes: true, language)
                .ConfigureAwait(false);
            if (PictureTailName(TsvWords(boxes), header, scale, recipient) is { } named)
                return named;
        }

        return null;
    }

    // A line whose folded words are the recipient's and one more.
    internal static bool OneWordAfterName(string line, string recipient)
    {
        string[] words = Fold(line).Split(' ', StringSplitOptions.RemoveEmptyEntries);
        string[] name = Fold(recipient).Split(' ', StringSplitOptions.RemoveEmptyEntries);
        return name.Length > 0 && words.Length == name.Length + 1 && words.Take(name.Length).SequenceEqual(name);
    }

    // A word of Tesseract's TSV output (level 5) with its line and its box, in the pixels of the picture it read.
    internal sealed record TsvWord(string Text, int Block, int Paragraph, int Line, int Left, int Top, int Width, int Height);

    internal static IReadOnlyList<TsvWord> TsvWords(string tsv)
    {
        List<TsvWord> words = [];
        foreach (string row in tsv.Split('\n'))
        {
            string[] cells = row.TrimEnd('\r').Split('\t');
            if (cells.Length == 12 && cells[0] == "5" && cells[11].Trim().Length > 0
                && int.TryParse(cells[2], out int block) && int.TryParse(cells[3], out int paragraph)
                && int.TryParse(cells[4], out int line) && int.TryParse(cells[6], out int left)
                && int.TryParse(cells[7], out int top) && int.TryParse(cells[8], out int width)
                && int.TryParse(cells[9], out int height))
                words.Add(new(cells[11].Trim(), block, paragraph, line, left, top, width, height));
        }

        return words;
    }

    // The recipient's name on a line of words whose last word is drawn in colour in the header crop (a BMP); null when
    // no line is so. The words before it may still carry a lettered avatar (WithoutAvatar).
    internal static string? PictureTailName(IReadOnlyList<TsvWord> words, byte[] header, int scale, string recipient)
    {
        foreach (IGrouping<(int, int, int), TsvWord> line in words.GroupBy(word => (word.Block, word.Paragraph, word.Line)))
        {
            TsvWord[] row = [.. line];
            if (row.Length < 2 || Fold(row[^1].Text).Length == 0)
                continue;
            string before = string.Join(' ', row[..^1].Select(word => word.Text));
            string? named = NamesRecipient(before, recipient) ? before.Trim() : WithoutAvatar(before, recipient);
            TsvWord tail = row[^1];
            if (named is not null && scale > 0
                && ColourShare(header, tail.Left / scale, tail.Top / scale, tail.Width / scale, tail.Height / scale)
                    >= PictureTailColourShare)
                return named;
        }

        return null;
    }

    // Measured (G3): the share of a word box's pixels that are coloured inside a horizontal run of five coloured pixels
    // (max-min of R, G and B over 40; WhatsApp's dark header is 19, its grey text less). ClearType's colour fringes
    // around a grey letter are one or two pixels wide and do not count; an emoji's filled colour does.
    private const double PictureTailColourShare = 0.10;
    private const int ColourChannelSpread = 40;
    private const int ColourRunReach = 2;

    internal static double ColourShare(byte[] bitmap, int left, int top, int width, int height)
    {
        const int header = 54;
        int bitmapWidth = BinaryPrimitives.ReadInt32LittleEndian(bitmap.AsSpan(18));
        int bitmapHeight = BinaryPrimitives.ReadInt32LittleEndian(bitmap.AsSpan(22));
        int counted = 0;
        int coloured = 0;
        for (int y = Math.Max(0, top); y < Math.Min(bitmapHeight, top + height); y++)
        {
            for (int x = Math.Max(0, left); x < Math.Min(bitmapWidth, left + width); x++)
            {
                counted++;
                bool run = true;
                for (int reach = -ColourRunReach; reach <= ColourRunReach && run; reach++)
                    run = Coloured(x + reach, y);
                if (run)
                    coloured++;
            }
        }

        return counted == 0 ? 0 : (double)coloured / counted;

        // The capture is bottom-up BGRA (EncodeBmp).
        bool Coloured(int x, int y)
        {
            if (x < 0 || x >= bitmapWidth)
                return false;
            int offset = header + (((bitmapHeight - 1 - y) * bitmapWidth) + x) * 4;
            byte blue = bitmap[offset], green = bitmap[offset + 1], red = bitmap[offset + 2];
            return Math.Max(red, Math.Max(green, blue)) - Math.Min(red, Math.Min(green, blue)) > ColourChannelSpread;
        }
    }

    // What the WhatsApp chat list under the search showed: its lines (null when it could not be read) and the logical
    // points, in the normalized window, of the rows that are the recipient.
    private sealed record ChatListRead(
        IReadOnlyList<WindowsVisibleOcrLocator.LayoutLine>? Lines,
        IReadOnlyList<(int X, int Y)> Hits)
    {
        // The text of the line of the one row that is the recipient (null with none or several).
        internal string? Row { get; init; }
    }

    // The list filters a moment after the name is typed: it is read until exactly one row is the recipient, for as
    // long as Discord's switcher rows are waited for (SearchResultBudget); the last read decides.
    private static async ValueTask<ChatListRead> ReadChatListAsync(
        nint handle,
        string recipient,
        CancellationToken cancellationToken)
    {
        ChatListRead read = new(null, []);
        await PollUntilAsync(
            async token =>
            {
                double scale = GetDpiForWindow(handle) / 96.0;
                byte[] capture = CaptureRegion(handle, CaptureArea.ChatList, "whatsapp");
                IReadOnlyList<WindowsVisibleOcrLocator.LayoutLine>? lines =
                    await WindowsVisibleOcrLocator.ReadLayoutAsync(capture, 80, token, placed: true).ConfigureAwait(false);
                IReadOnlyList<(double X, double Y)> points = lines is null ? [] : RowsNamingRecipient(lines, recipient);
                read = new(lines, [.. points.Select(point => ((int)(point.X / scale), ChatListTopAt96Dpi + (int)(point.Y / scale)))])
                {
                    Row = points.Count == 1
                        ? lines!.FirstOrDefault(line => points[0].Y >= line.Y && points[0].Y <= line.Y + line.Height)?.Text
                        : null,
                };
                return read.Hits.Count == 1;
            },
            SearchResultBudget,
            InteractionPoll,
            cancellationToken).ConfigureAwait(false);
        return read;
    }

    // A chat list where no single row was the recipient. Ronda final 11 (regla 3): the view was clicked to and the search
    // typed and emptied: an effect. Uso real 2026-11-02: when several rows are the recipient, the candidates are those
    // rows' lines, for the model to ask which one; the list's other lines (a name that only starts the same) are not
    // candidates. With none, the lines read come back, as before.
    internal static DesktopRecipientObservation UnresolvedChatList(
        nint handle,
        int processId,
        IReadOnlyList<WindowsVisibleOcrLocator.LayoutLine>? lines,
        string recipient)
    {
        if (lines is null)
            return new(false, true, handle, processId, "recipient_search_unreadable");
        bool ambiguous = RowsNamingRecipient(lines, recipient).Count > 1;
        string[] candidates = ambiguous
            ? [.. lines.Where(line => RowsNamingRecipient([line], recipient).Count > 0).Select(line => line.Text)]
            : [.. lines.Select(line => line.Text).Distinct()];
        return new(false, true, handle, processId, ambiguous ? "recipient_ambiguous" : RecipientNotFound)
        {
            Candidates = candidates.Take(8).ToArray(),
            CandidateCount = candidates.Length,
        };
    }

    // The centres, in capture pixels, of the rows of a chat-list reading that are the recipient: a run of a line's
    // words that is the recipient (NamesRecipient) and stands apart from the rest of its line (the time of the last
    // message at its right end) by a visual gap. A preview «Juan Pérez: hola» is not the row «Juan Pérez».
    internal static IReadOnlyList<(double X, double Y)> RowsNamingRecipient(
        IReadOnlyList<WindowsVisibleOcrLocator.LayoutLine> lines,
        string recipient)
    {
        List<(double X, double Y, WindowsVisibleOcrLocator.LayoutLine Line)> hits = [];
        foreach (WindowsVisibleOcrLocator.LayoutLine line in lines)
        {
            IReadOnlyList<WindowsVisibleOcrLocator.LayoutWord> words = line.Words is { Count: > 0 } read
                ? read
                : [new(line.Text, line.X, line.Y, line.Width, line.Height)];
            for (int start = 0; start < words.Count; start++)
            {
                for (int end = start + 1; end <= words.Count; end++)
                {
                    if (!NamesRecipient(string.Join(' ', words.Skip(start).Take(end - start).Select(word => word.Text)), recipient))
                        continue;
                    double left = words[start].X;
                    double top = words.Skip(start).Take(end - start).Min(word => word.Y);
                    double right = words[end - 1].X + words[end - 1].Width;
                    double bottom = words.Skip(start).Take(end - start).Max(word => word.Y + word.Height);
                    var box = new global::Windows.Foundation.Rect(left, top, right - left, bottom - top);
                    if (!WindowsVisibleOcrLocator.SetApart(box, Box(words, start - 1), Box(words, end))
                        || !EndsAsRowName(words, end))
                        continue;
                    (double X, double Y) centre = (left + (right - left) / 2, top + (bottom - top) / 2);
                    if (!hits.Any(hit => Math.Abs(hit.X - centre.X) <= 4 && Math.Abs(hit.Y - centre.Y) <= 4))
                        hits.Add((centre.X, centre.Y, line));
                }
            }
        }

        // Uso real 2026-11-03: a row's second line («X también está en este grupo», whose matched name the client paints
        // apart and the OCR reads as a line of its own) is never a row: a line right under another of the same column is.
        hits.RemoveAll(hit => lines.Any(above => !ReferenceEquals(above, hit.Line)
            && hit.Line.Y - above.Y > 0 && hit.Line.Y - above.Y <= 2 * hit.Line.Height
            && Math.Abs(above.X - hit.Line.X) <= 2.5 * hit.Line.Height));
        // The client ranks its results by sections (chats, contacts, groups, messages), each under a header that starts
        // left of the rows (the rows start after their picture): the one hit of the first section that holds any is the
        // chat; several there stay ambiguous.
        if (hits.Count > 1)
        {
            double rowsLeft = hits.Min(hit => hit.Line.X);
            double[] headers = [.. lines.Where(line => line.X < rowsLeft - 2.5 * line.Height).Select(line => line.Y)];
            int Section((double X, double Y, WindowsVisibleOcrLocator.LayoutLine Line) hit) =>
                headers.Count(header => header < hit.Line.Y);
            int first = hits.Min(Section);
            if (headers.Length > 0 && hits.Count(hit => Section(hit) == first) == 1)
                hits.RemoveAll(hit => Section(hit) != first);
        }

        return [.. hits.Select(static hit => (hit.X, hit.Y))];

        // Uso real 2026-11-02: what follows a row's name on its line is its stamp at most (the time, «11:10 p. m.», a
        // day); a message's author has its colon or the message's words after it («Ana 😀: nos vemos», whose emoji the
        // OCR drops, leaving a gap that set the author apart as if it were a row).
        static bool EndsAsRowName(IReadOnlyList<WindowsVisibleOcrLocator.LayoutWord> words, int end)
        {
            if (words[end - 1].Text.TrimEnd().EndsWith(':'))
                return false;
            List<string> after = [];
            foreach (WindowsVisibleOcrLocator.LayoutWord word in words.Skip(end))
            {
                if (Fold(word.Text).Length > 0)
                    after.Add(word.Text.TrimStart());
                else if (after.Count == 0 && word.Text.Contains(':', StringComparison.Ordinal))
                    return false;
            }

            return after.Count == 0
                || (!after[0].StartsWith(':') && (after.Count == 1 || after[0].Any(char.IsDigit)));
        }

        static global::Windows.Foundation.Rect? Box(IReadOnlyList<WindowsVisibleOcrLocator.LayoutWord> words, int index) =>
            index >= 0 && index < words.Count
                ? new global::Windows.Foundation.Rect(words[index].X, words[index].Y, words[index].Width, words[index].Height)
                : null;
    }

    // Auditoría final: a shown name (a header line, a chat-list row, the conversation part of a window title) names
    // the recipient only when it is the recipient, case, accents and punctuation folded: «Nube77» is not «Nube77 Fan».
    internal static bool NamesRecipient(string shown, string recipient) =>
        Fold(recipient).Length > 0 && string.Equals(Fold(shown), Fold(recipient), StringComparison.Ordinal);

    // Discord titles its window with the conversation and its own name («Discord | @Nube77», «Nube77 - Discord»,
    // «#general | BAXY - Discord»): with the client's part taken away, the one part left must be the recipient.
    internal static bool TitleNamesRecipient(string title, string recipient)
    {
        string[] parts = [.. title.Split([" | ", " - "], StringSplitOptions.RemoveEmptyEntries)
            .Where(part => !string.Equals(Fold(part), "discord", StringComparison.Ordinal))];
        return parts.Length == 1 && NamesRecipient(parts[0], recipient);
    }

    // G6 (uso real 2026-11-03, client.channel.open): a conversation opened by name is a direct chat or group, titled with
    // its one name, or a server's channel, titled with the channel and then its server («#general | Amigos»): the first
    // part must be the name and, when a server was named, the second the server.
    internal static bool TitleNamesConversation(string title, string name, string? server)
    {
        string[] parts = [.. title.Split([" | ", " - "], StringSplitOptions.RemoveEmptyEntries)
            .Where(part => !string.Equals(Fold(part), "discord", StringComparison.Ordinal))];
        return parts.Length switch
        {
            1 => server is null && NamesRecipient(parts[0], name),
            2 => NamesRecipient(parts[0], name) && (server is null || NamesRecipient(parts[1], server)),
            _ => false,
        };
    }

    // A row of Discord's quick switcher writes the name and, after it, the account («Nube77 .nubecita.0001»): the row is
    // opened when it holds the recipient's whole words (C1), and the window title, exact, decides whether it was them.
    // Ronda final 30 (regla 3): a voice channel's row («Sala de Pedro, Canal de voz, Servidor», the kind read as
    // client.channel.locate reads it) is never clicked: opening it could join the person to the call.
    internal static bool RowNamesRecipient(string row, string recipient) =>
        Fold(recipient).Length > 0 && ContainsPhrase(row, recipient) && !VoiceChannelRow(row);

    // A row of a person is «name, kind, account», and an account is written in lower case, digits, «.» and «_». Only a row
    // whose name is exactly the one asked for gives it: «Ana Pérez, usuario, anap» says nothing of «Ana».
    internal static string? RowAccount(string row, string recipient)
    {
        string[] parts = row.Split(", ", StringSplitOptions.TrimEntries | StringSplitOptions.RemoveEmptyEntries);
        return parts.Length == 3 && NamesRecipient(parts[0], recipient)
            && parts[2].All(static letter => char.IsAsciiLetterLower(letter) || char.IsAsciiDigit(letter) || letter is '.' or '_')
                ? parts[2]
                : null;
    }

    // Whether a place where a name was read lies in the band of the window's conversation header.
    internal static bool ShownInHeader(IReadOnlyList<ScreenBox> places, ScreenBox window, int headerBottom) =>
        places.Any(place => place.Top >= window.Top && place.Top + place.Height <= window.Top + headerBottom);

    // Discord titles a direct chat «@name», and a server's channel «#name | server».
    internal static bool DirectChatTitle(string title) => title.StartsWith('@');

    // Uso-128 (read on the real client on 2026-11-05: «General (canal de voz)», the kind inside the name's own part, which the
    // read of the second part alone took for a text channel): the row's kind, after its name in any of the forms it comes.
    // Review R1: «Sala (voz alta), Canal de texto, Club» and «Compras (invoices), …» are text channels (ReadRow).
    internal static bool VoiceChannelRow(string row) => ReadRow(row).Voice;

    // C2: the header crop excludes the search box and the chat list, so the only chat name in it is the open
    // conversation's; its name and the status under it («en línea») are read as separate lines, and the line that is
    // the recipient is what the client showed. No letter is tolerated: an OCR slip fails the read (the six readings of
    // ReadTextAsync give the name more than one chance), and «Mario» never passes for «Maria».
    internal static string? HeaderLine(string observed, string target)
    {
        foreach (string line in observed.Split('\n'))
        {
            if (NamesRecipient(line, target))
            {
                return line.Trim();
            }

            if (WithoutAvatar(line, target) is { } named)
            {
                return named;
            }
        }

        return null;
    }

    // Uso real 2026-10-21 (e2e del notebook): a contact without a photo has a lettered avatar left of the name, read on
    // the name's line («A Ana»), and the exact header read failed every send. Before the name only icons (no letter
    // or digit) and that one initial letter are set aside; the rest must still be the recipient exactly.
    internal static string? WithoutAvatar(string line, string target)
    {
        string folded = Fold(target);
        if (folded.Length == 0)
        {
            return null;
        }

        string[] words = line.Split(' ', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
        int start = 0;
        while (start < words.Length && !words[start].Any(char.IsLetterOrDigit))
        {
            start++;
        }

        if (start < words.Length && words[start].Length == 1 && Fold(words[start]) == folded[..1])
        {
            start++;
        }

        if (start == 0 || start >= words.Length)
        {
            return null;
        }

        string rest = string.Join(' ', words[start..]);
        return NamesRecipient(rest, target) ? rest : null;
    }

    // A sent bubble may wrap («prueba 1 de WhatsApp, ya funciona de nuevo») and
    // its short words («1», «de», «ya») take the most OCR noise, so the delivery
    // read requires every word of four or more letters (one edit tolerated from
    // five) and nothing else; a text without such a word needs the exact phrase.
    // Tesseract merges the words of a short typed line at this size («Hola test»
    // read as «Holatest», every single-word draft read fine), so the typed or
    // sent text is also accepted with all spaces removed, one edit tolerated
    // from five letters; the band changed and the header names the destination.
    internal static bool SpacelessMatches(string observed, string target)
    {
        string folded = Fold(target).Replace(" ", string.Empty);
        if (folded.Length == 0)
        {
            return false;
        }

        string haystack = Fold(observed).Replace(" ", string.Empty);
        if (haystack.Contains(folded, StringComparison.Ordinal))
        {
            return true;
        }

        if (folded.Length < 5)
        {
            return false;
        }

        for (int start = 0; start + folded.Length - 1 <= haystack.Length; start++)
        {
            for (int length = folded.Length - 1; length <= folded.Length + 1; length++)
            {
                if (length > 0 && start + length <= haystack.Length
                    && WithinOneEdit(haystack.Substring(start, length), folded))
                {
                    return true;
                }
            }
        }

        return false;
    }

    // C4: how a read shows the expected text: «exact» (its folded words, whole and in order), «tolerant» (the OCR
    // tolerance of DeliveryMatches: spaces lost, or one letter off in a word of five or more), or null.
    internal static string? TextMatch(string observed, string expected) =>
        ContainsPhrase(observed, expected) ? "exact" : DeliveryMatches(observed, expected) ? "tolerant" : null;

    // Renew al máximo (w8): a read joins its OCR passes, and the joined text could show the phrase across two passes
    // («hola» read twice made «hola hola» exact). «exact» is now one pass showing it whole; the tolerant match still pools
    // the passes as before (it already held whenever the joined phrase did), so what verifies is unchanged.
    internal static string? TextMatch(OcrText observed, string expected) =>
        observed.Passes.Any(pass => ContainsPhrase(pass, expected)) ? "exact"
            : DeliveryMatches(observed.Text, expected) ? "tolerant" : null;

    internal static bool DeliveryMatches(string observed, string target)
    {
        if (SpacelessMatches(observed, target))
        {
            return true;
        }

        string[] words = Fold(observed).Split(' ', StringSplitOptions.RemoveEmptyEntries);
        string[] tokens = Fold(target).Split(' ', StringSplitOptions.RemoveEmptyEntries);
        bool anyLong = false;
        for (int index = 0; index < tokens.Length; index++)
        {
            string token = tokens[index];
            if (token.Length < 4)
            {
                // FT/proveedores goal (review of receipts): a short word is not read with the OCR tolerance, but it is
                // read: a word the text has and the draft lacks («no») made a draft that says otherwise verified. It
                // is there as a word, or joined to its neighbour when the read lost the space between them.
                string before = index > 0 ? tokens[index - 1] + token : string.Empty;
                string after = index + 1 < tokens.Length ? token + tokens[index + 1] : string.Empty;
                if (!words.Any(word => word == token
                        || (before.Length > 0 && word.Contains(before, StringComparison.Ordinal))
                        || (after.Length > 0 && word.Contains(after, StringComparison.Ordinal))))
                {
                    return false;
                }

                continue;
            }

            anyLong = true;
            bool matched = false;
            foreach (string word in words)
            {
                if (word == token || (token.Length >= 5 && WithinOneEdit(word, token)))
                {
                    matched = true;
                    break;
                }
            }

            if (!matched)
            {
                return false;
            }
        }

        return anyLong;
    }

    private static bool WithinOneEdit(string left, string right)
    {
        if (Math.Abs(left.Length - right.Length) > 1)
        {
            return false;
        }

        int i = 0;
        int j = 0;
        int edits = 0;
        while (i < left.Length && j < right.Length)
        {
            if (left[i] == right[j])
            {
                i++;
                j++;
                continue;
            }

            if (++edits > 1)
            {
                return false;
            }

            if (left.Length > right.Length)
            {
                i++;
            }
            else if (left.Length < right.Length)
            {
                j++;
            }
            else
            {
                i++;
                j++;
            }
        }

        edits += (left.Length - i) + (right.Length - j);
        return edits <= 1;
    }

    private static async ValueTask<OcrText> ReadTextAsync(
        byte[] bitmap,
        CancellationToken cancellationToken,
        OcrLanguage? language = null)
    {
        string? executable = FindTesseract();
        if (executable is null)
        {
            return await ReadWithoutTesseractAsync(bitmap, cancellationToken).ConfigureAwait(false);
        }

        // A dark theme draws light text on a dark background, which Tesseract
        // reads as nothing (MSGSEND1845: «hola» typed in the WhatsApp composer
        // came back empty) while the inverted copy reads it; and the header
        // title at native size read «Misica» where the 2x copy reads «Musica»,
        // while the composer band reads only at native size. Every reading
        // counts, so the four passes are joined.
        // Both 2x copies: the blocky one reads the composer's typed text («hola»,
        // «probando») where the smooth one reads «hold», «probanda»; the smooth one
        // reads the sent bubble («test») where the blocky one reads «TES».
        byte[] blocky = Upscale2xNearest(bitmap);
        byte[] smooth = Upscale2x(bitmap);
        var readings = new string[6];
        int index = 0;
        foreach (byte[] candidate in new[]
                 {
                     bitmap, InvertPixels(bitmap),
                     blocky, InvertPixels(blocky),
                     smooth, InvertPixels(smooth),
                 })
        {
            readings[index++] = await RunTesseractAsync(executable, candidate, cancellationToken, language: language)
                .ConfigureAwait(false);
        }

        string text = string.Join('\n', readings);
        return new OcrText(text, readings);
    }

    // BAXY's packages do not bring Tesseract, so on a Windows without it every send ended in message_ocr_unavailable.
    // Windows' own OCR reads the band as it is and at twice its size, as the passes above do for Tesseract.
    private static async ValueTask<OcrText> ReadWithoutTesseractAsync(byte[] bitmap, CancellationToken cancellationToken)
    {
        OcrText native = await ReadWindowsTextAsync(bitmap, cancellationToken).ConfigureAwait(false);
        OcrText larger = await ReadWindowsTextAsync(Upscale2x(bitmap), cancellationToken).ConfigureAwait(false);
        string[] readings = [.. native.Passes, .. larger.Passes];
        return new OcrText(string.Join('\n', readings), readings);
    }

    private static byte[] Upscale2xNearest(byte[] bitmap)
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

    // Bilinear: the blocky glyphs of a replicated pixel read «TES»/«St eazy» for
    // a sent «test» while the smooth copy reads «test».
    private static byte[] Upscale2x(byte[] bitmap)
    {
        const int header = 54;
        int width = BinaryPrimitives.ReadInt32LittleEndian(bitmap.AsSpan(18));
        int height = BinaryPrimitives.ReadInt32LittleEndian(bitmap.AsSpan(22));
        int stride = width * 4;
        int targetStride = stride * 2;
        byte[] pixels = new byte[checked(targetStride * height * 2)];
        for (int targetRow = 0; targetRow < height * 2; targetRow++)
        {
            int row = targetRow / 2;
            int nextRow = Math.Clamp(targetRow % 2 == 0 ? row - 1 : row + 1, 0, height - 1);
            ReadOnlySpan<byte> line = bitmap.AsSpan(header + row * stride, stride);
            ReadOnlySpan<byte> nextLine = bitmap.AsSpan(header + nextRow * stride, stride);
            Span<byte> target = pixels.AsSpan(targetRow * targetStride, targetStride);
            for (int targetColumn = 0; targetColumn < width * 2; targetColumn++)
            {
                int column = targetColumn / 2;
                int nextColumn = Math.Clamp(targetColumn % 2 == 0 ? column - 1 : column + 1, 0, width - 1);
                for (int channel = 0; channel < 4; channel++)
                {
                    // Weights 9/3/3/1 over the pixel, its horizontal and vertical
                    // neighbours and the diagonal: the half-pixel bilinear sample.
                    int value = 9 * line[column * 4 + channel]
                        + 3 * line[nextColumn * 4 + channel]
                        + 3 * nextLine[column * 4 + channel]
                        + nextLine[nextColumn * 4 + channel];
                    target[targetColumn * 4 + channel] = (byte)((value + 8) / 16);
                }
            }
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

    // Renew al máximo (auditoría de flujos): the capture of a chat goes to Tesseract through its standard input; it was
    // written to %TEMP% for each pass and left there whenever its deletion failed (B-CU-5's rule: no chat on disk).
    private static async ValueTask<string> RunTesseractAsync(
        string executable,
        byte[] bitmap,
        CancellationToken cancellationToken,
        bool boxes = false,
        OcrLanguage? language = null)
    {
        var start = new ProcessStartInfo(executable)
        {
            UseShellExecute = false,
            RedirectStandardInput = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            // G3: Tesseract writes UTF-8 (CaptureVisionAdapter reads it so); the console's code page turned «®» into «┬«».
            StandardOutputEncoding = Encoding.UTF8,
            CreateNoWindow = true,
        };
        start.ArgumentList.Add("stdin");
        start.ArgumentList.Add("stdout");
        // The product's runtime keeps its languages apart from the executable (BAXYRuntime\ocr\tessdata-fast); an engine
        // with its own English model keeps reading with it, as the reads above were tuned.
        if (language is not null)
        {
            start.ArgumentList.Add("--tessdata-dir");
            start.ArgumentList.Add(language.Tessdata);
        }
        else if (!File.Exists(Path.Combine(Path.GetDirectoryName(executable) ?? string.Empty, "tessdata", "eng.traineddata"))
            && CaptureVisionAdapter.FindTessdata(executable, "en", out _) is { } tessdata)
        {
            start.ArgumentList.Add("--tessdata-dir");
            start.ArgumentList.Add(tessdata);
        }

        start.ArgumentList.Add("-l");
        start.ArgumentList.Add(language?.Code ?? "eng");
        start.ArgumentList.Add("--psm");
        start.ArgumentList.Add("6");
        // G3: the words with their boxes (TSV), for PictureTailName. The variable the «tsv» config file sets, since the
        // runtime's tessdata-fast folder has no configs folder to hold that file.
        if (boxes)
        {
            start.ArgumentList.Add("-c");
            start.ArgumentList.Add("tessedit_create_tsv=1");
        }
        using Process process = Process.Start(start)
            ?? throw new IOException("Tesseract did not start.");
        HelperProcessJob.Assign(process);
        return await ReadRedirectedOutputAsync(process, cancellationToken, bitmap)
            .ConfigureAwait(false);
    }

    internal static async ValueTask<string> ReadRedirectedOutputAsync(
        Process process,
        CancellationToken cancellationToken,
        byte[]? input = null)
    {
        ArgumentNullException.ThrowIfNull(process);
        Task<string> outputTask =
            process.StandardOutput.ReadToEndAsync(cancellationToken);
        Task<string> errorTask =
            process.StandardError.ReadToEndAsync(cancellationToken);
        if (input is not null)
        {
            // Read concurrently above, so a process that answers while it is still being fed never blocks the write.
            try
            {
                await process.StandardInput.BaseStream.WriteAsync(input, cancellationToken).ConfigureAwait(false);
                process.StandardInput.Close();
            }
            catch (IOException)
            {
                // The process stopped reading (it failed before the picture, a missing language): its exit code answers.
            }
        }

        await process.WaitForExitAsync(cancellationToken).ConfigureAwait(false);
        string[] streams = await Task.WhenAll(outputTask, errorTask).ConfigureAwait(false);
        return process.ExitCode == 0 ? streams[0] : string.Empty;
    }

    private readonly record struct MessageVisualObservation(
        byte[] Bitmap,
        bool Verified,
        string? Read,
        string? Match);

    // Renew al máximo (auditoría de flujos): first where the product's assets declare Tesseract (BAXY_TESSERACT_EXE,
    // BAXYRuntime, Program Files), the lookup ocr.read uses; PATH only after them, and only its absolute directories.
    internal static string? FindTesseract() => TesseractLookup();

    // How this machine's Tesseract is found; a live check replaces it to read as a Windows without one does.
    internal static Func<string?> TesseractLookup { get; set; } = InstalledTesseract;

    // What can read the chat: Tesseract, or Windows' own OCR in the person's language (ReadWithoutTesseractAsync).
    internal static string? AnyOcrEngine() =>
        FindTesseract() ?? (global::Windows.Media.Ocr.OcrEngine.TryCreateFromUserProfileLanguages() is null ? null : "windows");

    private static string? InstalledTesseract()
    {
        if (CaptureVisionAdapter.FindTesseract() is { } declared)
        {
            return declared;
        }

        string? path = Environment.GetEnvironmentVariable("PATH");
        foreach (string directory in (path ?? string.Empty).Split(Path.PathSeparator))
        {
            if (!Path.IsPathFullyQualified(directory))
            {
                continue;
            }

            string candidate = Path.Combine(directory, "tesseract.exe");
            if (File.Exists(candidate))
            {
                return candidate;
            }
        }

        return null;
    }

    // The processes whose main window is each channel's client (message.draft, message.send): read by FindWindow and
    // by the key press's preflight (KeyWindowReader, K-2 refinada), where Enter may send what was left written.
    private static readonly string[] WhatsAppProcesses = ["WhatsApp.Root"];
    // Only a live check against a fake of another process name moves this (it must never reach a real client that is open).
    internal static string[] DiscordProcesses { get; set; } = ["Discord"];

    /// <summary>The process names of every messaging client message.draft and message.send write into.</summary>
    internal static IReadOnlyList<string> ClientProcessNames { get; } = [.. WhatsAppProcesses, .. DiscordProcesses];

    private static (nint Handle, int ProcessId) FindWindow(string channel)
    {
        string[] processNames = string.Equals(channel, "whatsapp", StringComparison.Ordinal)
            ? WhatsAppProcesses
            : DiscordProcesses;
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

    internal static string Fold(string value)
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
        // Asked once before the chord: a chord is never left half pressed.
        LeasedInput.EnsureMayAct();
        SendVirtualKey(modifier, keyUp: false);
        SendVirtualKey(key, keyUp: false);
        SendVirtualKey(key, keyUp: true);
        SendVirtualKey(modifier, keyUp: true);
    }

    private static void SendKey(ushort key)
    {
        LeasedInput.EnsureMayAct();
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
                        ExtraInfo = unchecked((nint)BaxyInputMark.Value),
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
            LeasedInput.EnsureMayAct();
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
                        ExtraInfo = unchecked((nint)BaxyInputMark.Value),
                    },
                },
            },
        ];
        uint sent = SendInput((uint)inputs.Length, inputs, Marshal.SizeOf<Input>());
        // Raw Input never delivers a Unicode key: the pause detector is told it was BAXY's.
        WindowsUserInputPause.NoteOwnUndelivered();
        if (sent != inputs.Length)
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
    // the list item that both show the searched name. The person's size comes
    // back when the flow ends (C7, InNormalizedWindowAsync).
    private const int WhatsAppWindowLogicalWidth = 1280;
    private const int WhatsAppWindowLogicalHeight = 800;
    // 400 rather than the 430 midpoint: right after a send the list narrowed by
    // about 35 px and the title, clipped at the crop's left edge, read as noise.
    private const int WhatsAppConversationPaneOffsetAt96Dpi = 400;
    private const int DiscordConversationPaneOffsetAt96Dpi = 320;

    private static int ConversationPaneOffsetAt96Dpi(string channel) =>
        string.Equals(channel, "whatsapp", StringComparison.Ordinal)
            ? WhatsAppConversationPaneOffsetAt96Dpi
            : DiscordConversationPaneOffsetAt96Dpi;

    // Uso real 2026-10-21 (e2e del notebook, captured in the normalized 1280 px window): this WhatsApp's chat list ends
    // at about 452 logical px (the conversation's avatar starts at about 468), past the 400 the pane is read from. The
    // composer band then held the list's right edge, whose rows change when a name is typed into the search or the
    // search is cleared: read as typing into the composer (search_focus_not_verified) or as the person's draft
    // (composer_has_person_draft), and nothing could be sent. The composer band alone starts past the list; the header
    // keeps its crop (from 470 it would hold the avatar's letter before the name).
    internal const int WhatsAppComposerBandLeftAt96Dpi = 470;

    // Uso real 2026-10-21 (e2e del notebook, a 1296 px Discord window): the server column and the direct-messages list
    // reached about 374 logical px, past the 320 the pane is read from, and the composer band held the list's foot (the
    // person's own panel): an empty composer passed for the person's draft. Discord lets that column be widened, so the
    // band starts past a share of the window as well.
    // A third: past the list (about 29 % there) and short of the composer's text (about 36 %), which the send reads.
    private const double DiscordComposerBandShare = 0.33;

    internal static int DiscordComposerBandLeft(int windowWidth) => (int)(windowWidth * DiscordComposerBandShare);

    // Uso real 2026-11-03 (F1, el PC: Discord maximized at 1936 px and 125 %): the third above is past where the typed
    // text starts once the window is wider than the one it was fitted on (its 36 % there; the server column, the list
    // and the attach button keep their width as the window grows), so the start of every message was cut off the read
    // and no draft verified. The typed text (typedText) is read from the conversation pane's edge; a read for text
    // only needs the message's words to be there, and the list's foot beside them adds words, never takes any. The
    // band that looks for a change of picture (a person's draft, a selection) keeps the third, past that foot.
    internal static int ComposerBandLeft(string channel, bool typedText, int windowWidth, double scale)
    {
        int last = Math.Max(0, windowWidth - 1);
        if (string.Equals(channel, "whatsapp", StringComparison.Ordinal))
        {
            return Math.Min(last, (int)(WhatsAppComposerBandLeftAt96Dpi * scale));
        }

        int pane = Math.Min(last, (int)(ConversationPaneOffsetAt96Dpi(channel) * scale));
        return typedText ? pane : Math.Min(last, Math.Max(pane, DiscordComposerBandLeft(windowWidth)));
    }

    // Outgoing bubbles are right-aligned, so the delivery is read from the right
    // end of the last-messages band alone: over the full band the doodle
    // wallpaper drowned the bubble («hola 15:32» read as «era»).
    private const int OutgoingBubbleBandWidthAt96Dpi = 320;

    // The conversation header's title row in the normalized window: below the
    // window's own title bar, left of the header icons.
    private const int HeaderRowTopAt96Dpi = 38;
    private const int HeaderRowHeightAt96Dpi = 62;
    private const int HeaderRowWidthAt96Dpi = 420;

    // Distance from the window's bottom edge to the middle of the composer input
    // (WhatsApp bar ≈ 48 px high with an 8 px margin; Discord's box sits within
    // the same band), scaled by the window's DPI like the pane offset.
    private const int ComposerBottomOffsetAt96Dpi = 56;
    // From the conversation pane's left edge to a point inside the composer
    // input, past the attach and emoji buttons in both apps.
    private const int ComposerInputOffsetAt96Dpi = 200;

    // C7: a flow that needs the normalized layout runs inside it, and the person's window gets its own size back
    // afterwards, however the flow ends (its position, z-order and maximized state are never changed).
    private static async ValueTask<T> InNormalizedWindowAsync<T>(
        string channel,
        nint handle,
        Func<CancellationToken, ValueTask<T>> flow,
        CancellationToken cancellationToken)
    {
        WindowSize? person = NormalizeWindow(channel, handle);
        try
        {
            if (person is not null)
            {
                await Task.Delay(400, cancellationToken).ConfigureAwait(false);
            }

            return await flow(cancellationToken).ConfigureAwait(false);
        }
        finally
        {
            if (person is { } size)
            {
                ResizeWindow(handle, size);
            }
        }
    }

    private readonly record struct WindowSize(int Width, int Height);

    // The window's size before it was normalized (physical pixels), or null when it already had the normalized size
    // or is not WhatsApp's.
    private static WindowSize? NormalizeWindow(string channel, nint handle)
    {
        if (!string.Equals(channel, "whatsapp", StringComparison.Ordinal))
        {
            return null;
        }

        nint previousDpi = SetThreadDpiAwarenessContext((nint)(-4));
        try
        {
            double scale = GetDpiForWindow(handle) / 96.0;
            var normalized = new WindowSize(
                (int)(WhatsAppWindowLogicalWidth * scale),
                (int)(WhatsAppWindowLogicalHeight * scale));
            if (!GetWindowRect(handle, out Rect rectangle))
            {
                return null;
            }

            var person = new WindowSize(rectangle.Right - rectangle.Left, rectangle.Bottom - rectangle.Top);
            if (person == normalized)
            {
                return null;
            }

            ResizeWindow(handle, normalized);
            return person;
        }
        finally
        {
            _ = SetThreadDpiAwarenessContext(previousDpi);
        }
    }

    private static void ResizeWindow(nint handle, WindowSize size)
    {
        nint previousDpi = SetThreadDpiAwarenessContext((nint)(-4));
        try
        {
            // SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE: only the size changes.
            _ = SetWindowPos(handle, 0, 0, 0, size.Width, size.Height, 0x0002 | 0x0004 | 0x0010);
        }
        finally
        {
            _ = SetThreadDpiAwarenessContext(previousDpi);
        }
    }

    // The typed draft is read from the composer band alone: Tesseract does not
    // segment that single line out of the whole conversation pane over the
    // doodle wallpaper (MSGSEND1845: «hola» read as «tt i>)» in the pane, as
    // «hola» in the band).
    private const int ComposerBandHeightAt96Dpi = 90;
    // Only the newest bubble's line: over a taller band the older bubbles' small
    // text drowned the new one (MSGSEND1845 audit: «probando.» read as «Breer»,
    // «test» read as «TES» with the bubble above still in the band).
    // 80 px: the newest bubble plus a wrapped second line, still below the older
    // bubbles' bulk (a one-line bubble is about 40 px, two lines about 60 px).
    private const int LastMessagesBandHeightAt96Dpi = 80;

    private enum CaptureArea
    {
        Header,
        Body,
        Composer,
        // The composer band from the conversation pane's edge: where the typed text is read (ComposerBandLeft).
        ComposerText,
        LastMessages,
        ChatList,
    }

    private static byte[] CaptureRegion(
        nint handle,
        CaptureArea area,
        string channel,
        int outgoingBandWidthAt96Dpi = OutgoingBubbleBandWidthAt96Dpi)
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
            // Discord: the server column (72 px) and the DM list (240 px) sit left of
            // the conversation at 100 % zoom; a 42 % crop of a wide window started
            // past the composer's text and the newest message's start.
            int sourceX = Math.Min(Math.Max(0, windowWidth - 1), (int)(ConversationPaneOffsetAt96Dpi(channel) * scale));
            if (area is CaptureArea.Composer or CaptureArea.ComposerText)
            {
                sourceX = ComposerBandLeft(channel, area == CaptureArea.ComposerText, windowWidth, scale);
            }
            // WhatsApp's chat list is what lies left of the conversation pane.
            int listWidth = sourceX;
            if (area == CaptureArea.ChatList)
            {
                sourceX = 0;
            }
            // Only WhatsApp right-aligns the outgoing bubble: narrowing the band to
            // the right end is what makes it readable there. Discord's messages run
            // from the left of the conversation pane, so the band keeps its width
            // (DISCORD1869: «hola» was really sent and the narrow band read nothing).
            if (area == CaptureArea.LastMessages && outgoingBandWidthAt96Dpi > 0
                && string.Equals(channel, "whatsapp", StringComparison.Ordinal))
            {
                sourceX = Math.Max(sourceX, windowWidth - (int)(outgoingBandWidthAt96Dpi * scale));
            }

            int composerBand = Math.Min(windowHeight, (int)(ComposerBandHeightAt96Dpi * scale));
            int lastMessagesBand = Math.Min(
                windowHeight - composerBand,
                (int)(LastMessagesBandHeightAt96Dpi * scale));
            int sourceY = area switch
            {
                CaptureArea.Header => Math.Min(windowHeight - 1, (int)(HeaderRowTopAt96Dpi * scale)),
                CaptureArea.Composer or CaptureArea.ComposerText => windowHeight - composerBand,
                CaptureArea.LastMessages => windowHeight - composerBand - lastMessagesBand,
                CaptureArea.ChatList => Math.Min(windowHeight - 1, (int)(ChatListTopAt96Dpi * scale)),
                _ => Math.Min(80, windowHeight / 8),
            };
            int width = Math.Max(1, area == CaptureArea.ChatList ? listWidth : windowWidth - sourceX);
            if (area == CaptureArea.Header)
            {
                // The title row alone: with the window's own title bar, the avatar
                // and the header icons in the crop, Tesseract read the open chat's
                // name as «po y» or dropped it (MSGSEND1845 audit); the row reads
                // «Musica» in every mode.
                width = Math.Min(width, (int)(HeaderRowWidthAt96Dpi * scale));
            }

            int height = area switch
            {
                CaptureArea.Header => Math.Max(1, Math.Min(windowHeight - sourceY, (int)(HeaderRowHeightAt96Dpi * scale))),
                CaptureArea.Composer or CaptureArea.ComposerText => Math.Max(1, composerBand),
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

                // Ronda final 18 (regla 3): a copy all black (a window with display affinity, a locked session) is not
                // a reading of the composer: «unchanged» or «empty» is never said from it.
                if (Baxy.Providers.Windows.Capture.WindowsScreenshotProvider.IsBlack(
                        new Baxy.Providers.Windows.Capture.ScreenshotFrame(width, height, pixels)))
                    throw new IOException("Messaging evidence capture came back black.");
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

    // Positions in the normalized WhatsApp window (logical px from its top-left):
    // the «Chats» sidebar icon and the chat search box.
    private const int SidebarChatsLogicalX = 40;
    private const int SidebarChatsLogicalY = 70;
    // The chat list is read from below the search box, so the name typed there is never taken for a row.
    private const int ChatListTopAt96Dpi = 152;

    // The window's rectangle in screen pixels, the unit UI Automation reads elements in.
    private static ScreenBox WindowBox(nint handle)
    {
        nint previousDpi = SetThreadDpiAwarenessContext((nint)(-4));
        try
        {
            return GetWindowRect(handle, out Rect rectangle)
                ? new ScreenBox(rectangle.Left, rectangle.Top, rectangle.Right - rectangle.Left, rectangle.Bottom - rectangle.Top)
                : default;
        }
        finally
        {
            _ = SetThreadDpiAwarenessContext(previousDpi);
        }
    }

    // A click at a point read by UI Automation (screen pixels).
    private static void ClickAtScreen(int x, int y)
    {
        LeasedInput.EnsureMayMovePointer();
        nint previousDpi = SetThreadDpiAwarenessContext((nint)(-4));
        try
        {
            if (!SetCursorPos(x, y))
            {
                return;
            }

            Input[] inputs =
            [
                MouseInput(0x0002),
                MouseInput(0x0004),
            ];
            _ = SendInput((uint)inputs.Length, inputs, Marshal.SizeOf<Input>());
        }
        finally
        {
            _ = SetThreadDpiAwarenessContext(previousDpi);
        }
    }

    private static void ClickAt(nint handle, int logicalX, int logicalY)
    {
        LeasedInput.EnsureMayMovePointer();
        nint previousDpi = SetThreadDpiAwarenessContext((nint)(-4));
        try
        {
            if (!GetWindowRect(handle, out Rect rectangle))
            {
                return;
            }

            double scale = GetDpiForWindow(handle) / 96.0;
            if (!SetCursorPos(
                    rectangle.Left + (int)(logicalX * scale),
                    rectangle.Top + (int)(logicalY * scale)))
            {
                return;
            }

            Input[] inputs =
            [
                MouseInput(0x0002),
                MouseInput(0x0004),
            ];
            _ = SendInput((uint)inputs.Length, inputs, Marshal.SizeOf<Input>());
        }
        finally
        {
            _ = SetThreadDpiAwarenessContext(previousDpi);
        }
    }

    private static bool FocusComposer(nint handle, string channel)
    {
        LeasedInput.EnsureMayMovePointer();
        nint previousDpi = SetThreadDpiAwarenessContext((nint)(-4));
        try
        {
            if (!GetWindowRect(handle, out Rect rectangle))
            {
                return false;
            }

            double scale = GetDpiForWindow(handle) / 96.0;
            // The composer bar has a constant height at the bottom of the window,
            // so its input is a fixed distance above the bottom edge; a fraction of
            // the window height landed on the bar's top edge once the window was
            // tall (MSGSEND1845: 944 px, 92 % = 868 px, input centred at 888 px,
            // «hola» typed into nothing, message_draft_not_verified).
            // Across, the input starts a fixed distance into the conversation pane;
            // 76 % of a 1296 px Discord window fell on the profile panel at the
            // right and the typed text went nowhere (G1, notebook, 2026-10-11).
            if (!SetCursorPos(
                    rectangle.Left + (int)((ConversationPaneOffsetAt96Dpi(channel) + ComposerInputOffsetAt96Dpi) * scale),
                    rectangle.Bottom - (int)(ComposerBottomOffsetAt96Dpi * scale)))
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
            Mouse = new NativeMouseInput { Flags = flags, ExtraInfo = unchecked((nint)BaxyInputMark.Value) },
        },
    };

    internal static byte[] EncodeBmp(int width, int height, byte[] pixels)
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
    private static partial uint GetWindowThreadProcessId(nint handle, out uint processId);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool IsIconic(nint handle);

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
