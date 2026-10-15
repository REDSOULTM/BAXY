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
    private readonly ConcurrentDictionary<string, ResolvedRecipient> _recipients = new();
    private readonly SemaphoreSlim _interaction = new(1, 1);
    private readonly string _testDestinationsPath;

    internal DesktopMessagingAdapter(IClientInteractionProbe probe)
        : this(new WindowsDesktopMessagingAutomation(probe))
    {
    }

    internal DesktopMessagingAdapter(IDesktopMessagingAutomation automation, string? testDestinationsPath = null)
    {
        _automation = automation ?? throw new ArgumentNullException(nameof(automation));
        _testDestinationsPath = testDestinationsPath ?? DefaultTestDestinationsPath();
    }

    public bool CanHandle(string operation) =>
        operation is "message.recipient.resolve" or "message.send" or "message.draft"
            or "message.send.test";

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

    private static readonly ExternalProcessRunner MailRunner = new();

    private const string OutlookTestSendScript = """
        $ErrorActionPreference='Stop'
        $input=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($args[0]))|ConvertFrom-Json
        $effect=$false
        try {
          $outlook=New-Object -ComObject Outlook.Application
          $session=$outlook.GetNamespace('MAPI')
          $to=[string]$input.to;$text=[string]$input.text;$subject=[string]$input.subject
          $baseline=[DateTime]::UtcNow
          $mail=$outlook.CreateItem(0)
          $mail.To=$to;$mail.Subject=$subject;$mail.Body=$text
          $mail.Send();$effect=$true
          $sentFolder=$session.GetDefaultFolder(5)
          $sent=$null
          for($attempt=0;$attempt -lt 40 -and $null -eq $sent;$attempt++){
            Start-Sleep -Milliseconds 500
            $sentItems=$sentFolder.Items;$sentItems.Sort('[SentOn]',$true);$seen=0
            foreach($candidate in $sentItems){
              if($seen++ -ge 50){break}
              try {
                $sentOn=([DateTime]$candidate.SentOn).ToUniversalTime()
                if($sentOn -ge $baseline.AddMinutes(-2) -and ([string]$candidate.To).ToLowerInvariant().Contains($to.ToLowerInvariant()) -and ([string]$candidate.Body).StartsWith($text,[StringComparison]::Ordinal)){$sent=$candidate;break}
              }catch{}
            }
          }
          if($null -eq $sent){throw 'outlook_sent_postread_missing'}
          [pscustomobject]@{ok=$true;effectObserved=$true;sentEntryId=[string]$sent.EntryID;sentUtc=([DateTime]$sent.SentOn).ToUniversalTime().ToString('O');sentTo=[string]$sent.To}|ConvertTo-Json -Compress
        } catch {
          [pscustomobject]@{ok=$false;effectObserved=$effect;error='outlook_mail_failed'}|ConvertTo-Json -Compress
          exit 2
        }
        """;

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
        // D59 §1, ronda 19 (t1-c09, t2-c07, t3-c07 «mandale a Ron92 por discord …» with
        // Discord closed): the named client is opened before its recipient is looked
        // for, as the draft and the reviewed send already do; resolving against a
        // closed client only answered «<client>_client_not_running».
        DesktopClientReadiness client = await _automation.EnsureClientOpenAsync(
            channel,
            cancellationToken).ConfigureAwait(false);
        if (!client.Ready)
        {
            return Failure(
                "message.recipient.resolve",
                client.ErrorCode ?? $"{channel}_client_not_running",
                client.Opened);
        }

        DesktopRecipientObservation observation = await _automation.ResolveAsync(
            channel,
            recipient,
            cancellationToken).ConfigureAwait(false);
        if (Unresolved("message.recipient.resolve", observation) is { } unresolved)
        {
            return unresolved;
        }

        string recipientId = "recipient_" + Guid.NewGuid().ToString("N");
        var resolved = new ResolvedRecipient(
            recipientId,
            channel,
            recipient,
            observation.Shown!,
            observation.WindowHandle,
            observation.ProcessId);
        _recipients[recipientId] = resolved;
        return Success(
            "message.recipient.resolve",
            JsonObject(
                ("version", 1),
                ("recipientId", recipientId),
                ("channel", channel),
                ("recipient", recipient),
                ("displayName", resolved.Shown),
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
                ("displayName", recipient.Shown),
                ("contentSha256", Convert.ToHexStringLower(SHA256.HashData(
                    Encoding.UTF8.GetBytes(text)))),
                ("delivery", "visible_postcondition"),
                ("deliveryRead", observation.Read),
                ("deliveryMatch", observation.Match)));
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
            "draft_" + Guid.NewGuid().ToString("N"),
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
            return Failure("message.send.test", "test_destination_not_configured");
        }

        if (string.Equals(channel, "email", StringComparison.Ordinal))
        {
            return await SendTestMailAsync(requestedRecipient, forced, text, cancellationToken)
                .ConfigureAwait(false);
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
            "sendtest_" + Guid.NewGuid().ToString("N"),
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
                ("displayName", resolved.Shown),
                ("text", text),
                ("sent", true),
                ("clientOpened", client.Opened),
                ("evidenceHash", sent.EvidenceHash),
                ("deliveryRead", sent.Read),
                ("deliveryMatch", sent.Match),
                ("authority", "desktop_client_send_ocr_postread")));
    }

    // Owner decision 2026-09-18 §3: a mail request is really sent from the owner's
    // classic Outlook profile, always to the owner's own test mailbox; the copy in
    // Sent Items (recipient, text, time) is the delivery evidence.
    private static async ValueTask<ExternalCapabilityReceipt> SendTestMailAsync(
        string requestedRecipient,
        string forced,
        string text,
        CancellationToken cancellationToken)
    {
        string subject = text.Length <= 78 ? text : text[..75] + "…";
        string input = JsonObject(("to", forced), ("subject", subject), ("text", text)).GetRawText();
        ExternalProcessResult process = await MailRunner.RunAsync(
            "powershell.exe",
            ["-NoProfile", "-NonInteractive", "-Command", "& {\n" + OutlookTestSendScript + "\n}",
                Convert.ToBase64String(Encoding.UTF8.GetBytes(input))],
            TimeSpan.FromSeconds(90),
            cancellationToken).ConfigureAwait(false);
        string[] lines = process.Output.Split(['\r', '\n'], StringSplitOptions.RemoveEmptyEntries);
        string line = lines.Length > 0 ? lines[^1] : "{}";
        bool effect = false;
        string? sentEntryId = null;
        string? sentUtc = null;
        try
        {
            using JsonDocument response = JsonDocument.Parse(line);
            JsonElement root = response.RootElement;
            effect = root.TryGetProperty("effectObserved", out JsonElement observed)
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
                effect ? "message_delivery_not_verified" : "outlook_mail_send_failed",
                effect);
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

    private static ExternalCapabilityReceipt Failure(
        string operation,
        string error,
        bool effectObserved = false) =>
        new(operation, effectObserved, false, null, error);

    // C2, C3: a recipient is resolved only with what the client showed naming it; a lookup that did not end on the
    // recipient fails with its cause and, when a search row was read, that row as «observed».
    private static ExternalCapabilityReceipt? Unresolved(string operation, DesktopRecipientObservation observation) =>
        observation.Verified && observation.Shown is not null
            ? null
            : new(
                operation,
                observation.EffectObserved,
                false,
                observation.Shown is null ? null : JsonObject(("version", 1), ("observed", observation.Shown)),
                observation.ErrorCode ?? "recipient_identity_not_verified");

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
}

// Name: the recipient the model asked for, matched as whole words against what the client shows. Shown: what the
// client showed for it when it was resolved (its window title or conversation header).
internal sealed record ResolvedRecipient(
    string RecipientId,
    string Channel,
    string Name,
    string Shown,
    nint WindowHandle,
    int ProcessId);

// Shown: the title or header line that names the recipient when Verified; otherwise the search row read last, if any.
internal sealed record DesktopRecipientObservation(
    bool Verified,
    bool EffectObserved,
    nint WindowHandle,
    int ProcessId,
    string? ErrorCode,
    string? Shown = null);

// Read and Match (C4): the text read where the message was looked for, and «exact» or «tolerant» (TextMatch).
internal sealed record DesktopMessageObservation(
    bool Verified,
    bool EffectObserved,
    string EvidenceHash,
    string? ErrorCode,
    string? Read = null,
    string? Match = null);

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
        CancellationToken cancellationToken) =>
        ValueTask.FromResult(DesktopClientReadiness.AlreadyOpen);

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
    private const ushort VirtualKeyShift = 0x10;
    private const ushort VirtualKeyAlt = 0x12;
    private const ushort VirtualKeyDown = 0x28;
    private const ushort VirtualKeyRight = 0x27;
    private const uint KeyUp = 0x0002;
    private const uint Unicode = 0x0004;

    // D59 §1: after the client's open is verified, its main window must show
    // (Discord draws an updater splash first) within its cold-start clock
    // (ClientColdStart, data), and then gets a short settle so its chat list is
    // drawn before the chat is searched.
    private static readonly TimeSpan ClientSettleDelay = TimeSpan.FromSeconds(2);
    private static readonly TimeSpan ClientReadyPoll = TimeSpan.FromMilliseconds(250);

    private WindowsInstalledApplicationOpenProvider? _clientOpener;
    private readonly IForegroundLease? _lease;

    internal WindowsDesktopMessagingAutomation(IClientInteractionProbe probe, IForegroundLease? lease = null)
    {
        Probe = probe ?? throw new ArgumentNullException(nameof(probe));
        _lease = lease;
    }

    // v3 point 0, fix 3: the client is driven with the real keyboard and mouse (its chat search, composer and quick
    // switcher expose no pattern this flow can use), so each resolve, send and draft runs inside one burst of the
    // foreground lease: after the person's pause, every key and click asks the burst first, and the window in front
    // and the cursor are given back at the end.
    private IForegroundLease Lease => _lease ?? ForegroundLease.Shared;

    // Ronda 24: what says a client's window is ready to be used (content shown, a search input in focus). TZ-DC2: it
    // reads through the Core's own UI Automation worker, never a second one started by the first search.
    private IClientInteractionProbe Probe { get; }

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

    // C5: Ctrl+A selects whatever the focused field holds. When that field is the conversation's composer and it holds
    // text, the composer's picture (composer, taken just before) changes under the selection; a placeholder is not
    // selectable and a blinking caret is not a change. Text found is left as it was, the selection collapsed to its
    // end, and true is returned. Nothing is deleted here.
    private static async ValueTask<bool> ComposerHoldsTextAsync(
        nint handle,
        string channel,
        byte[] composer,
        CancellationToken cancellationToken)
    {
        SendChord(VirtualKeyControl, VirtualKeyA);
        await Task.Delay(150, cancellationToken).ConfigureAwait(false);
        if (!ContentChanged(composer, CaptureRegion(handle, CaptureArea.Composer, channel)))
        {
            return false;
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
            byte[] now = CaptureRegion(handle, CaptureArea.Composer, channel);
            return !CryptographicOperations.FixedTimeEquals(SHA256.HashData(composerBefore), SHA256.HashData(now));
        }
        catch (Exception exception) when (exception is IOException or InvalidOperationException or ExternalException)
        {
            // Not readable: the text may be there.
            return true;
        }
    }

    private static byte[]? TryCaptureComposer(nint handle, string channel)
    {
        try
        {
            return CaptureRegion(handle, CaptureArea.Composer, channel);
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
        // The reads that prove a window ready start now, off the turn: a client already open never waits for them.
        Probe.Prewarm();
        if (FindWindow(channel).Handle != 0)
        {
            return DesktopClientReadiness.AlreadyOpen;
        }

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

        // Encargo CS (banco fz1 s14): one clock for the whole start, as long as the client may take cold (data per
        // application); a window still without content when it runs out says the client is still starting.
        TimeSpan coldStart = ClientColdStart.For(ClientApplicationName(channel));
        var clock = Stopwatch.StartNew();
        while (clock.Elapsed < coldStart)
        {
            (nint handle, _) = FindWindow(channel);
            if (handle != 0 && ClientWindowReady(WindowTitle(handle)))
            {
                // Ronda 24 (t1-c09, t2-c07, t3-c07): the loading screen already carries the client's name as its
                // title, so a title is not readiness. Ready is a window that shows content a person interacts with
                // (an editable field or a list). Only when nothing can be read is the old settle kept.
                TimeSpan left = coldStart - clock.Elapsed;
                ContentWait content = await AwaitClientContentAsync(
                    token => Probe.ReadAsync(handle, content: true, token),
                    left < ClientContentBudget ? left : ClientContentBudget,
                    ClientReadyPoll,
                    cancellationToken).ConfigureAwait(false);
                if (content == ContentWait.NotShown)
                {
                    // Encargo CS: a splash titled as the client (its updater) gives way to its main window, another
                    // window: it is looked for again while the clock lasts.
                    continue;
                }

                if (content == ContentWait.Unanswered)
                {
                    await Task.Delay(ClientSettleDelay, cancellationToken).ConfigureAwait(false);
                }

                return new(true, true, null);
            }

            await Task.Delay(ClientReadyPoll, cancellationToken).ConfigureAwait(false);
        }

        return new(false, true, ClientStillStarting(channel));
    }

    /// <summary>Encargo CS: the client was launched and its main window did not show its content within its cold start.</summary>
    internal static string ClientStillStarting(string channel) => $"{channel}_client_still_starting";

    internal static string ClientApplicationName(string channel) =>
        string.Equals(channel, "whatsapp", StringComparison.Ordinal) ? "WhatsApp" : "Discord";

    // Not installed is said as such; any other open failure leaves the client
    // unverified (the launch may have happened).
    internal static DesktopClientReadiness? ClientOpenFailure(string channel, ApplicationOpenResult opened) =>
        opened.Succeeded && opened.Verified
            ? null
            : string.Equals(opened.ErrorCode, ApplicationOpenErrorCodes.ApplicationNotFound, StringComparison.Ordinal)
                ? new(false, false, $"{channel}_client_not_installed")
                : new(false, opened.Receipt.LaunchIssued, $"{channel}_client_open_not_verified");

    // A titled main window that is not the updater splash.
    internal static bool ClientWindowReady(string title) =>
        title.Trim().Length > 0
        && !title.Contains("Updater", StringComparison.OrdinalIgnoreCase)
        && !title.Contains("Updating", StringComparison.OrdinalIgnoreCase);

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

        return await LeasedInput.RunAsync(
            Lease,
            handle,
            token => ResolveInBurstAsync(channel, recipient, handle, processId, Probe, token),
            (code, sent) => new DesktopRecipientObservation(false, sent, handle, processId, LeaseStop(code)),
            cancellationToken).ConfigureAwait(false);
    }

    private static async ValueTask<DesktopRecipientObservation> ResolveInBurstAsync(
        string channel,
        string recipient,
        nint handle,
        int processId,
        IClientInteractionProbe probe,
        CancellationToken cancellationToken)
    {
        await NormalizeWindowAsync(channel, handle, cancellationToken).ConfigureAwait(false);
        // The header is read twice because the first frame after a resize or
        // focus change may still be transitional. (Escape must not be sent here:
        // in WhatsApp it closes the open conversation.)
        for (int attempt = 0; attempt < 2; attempt++)
        {
            if (await ShownRecipientAsync(handle, channel, recipient, cancellationToken).ConfigureAwait(false)
                is { } shownAlready)
            {
                return new(true, false, handle, processId, null, shownAlready);
            }

            await Task.Delay(500, cancellationToken).ConfigureAwait(false);
        }

        if (string.Equals(channel, "whatsapp", StringComparison.Ordinal))
        {
            // The chat search is focused by position in the normalized window (the
            // «Chats» sidebar icon first, so an archived or other view cannot hide
            // it), and Enter is pressed only if the open conversation's composer
            // did not change while the name was typed: with the archived view open,
            // Ctrl+F focused nothing and «Música» + Enter went into the open chat
            // as a message (MSGSEND1845, owner's deliberate test).
            ClickAt(handle, SidebarChatsLogicalX, SidebarChatsLogicalY);
            await Task.Delay(300, cancellationToken).ConfigureAwait(false);
            ClickAt(handle, ChatSearchLogicalX, ChatSearchLogicalY);
            await Task.Delay(250, cancellationToken).ConfigureAwait(false);
            byte[] composerBefore = CaptureRegion(handle, CaptureArea.Composer, channel);
            try
            {
                // C5: the search's old query is cleared only when the selection did not land on text in the
                // conversation's composer (the search not focused, the person's draft there).
                if (await ComposerHoldsTextAsync(handle, channel, composerBefore, cancellationToken).ConfigureAwait(false))
                {
                    return new(false, false, handle, processId, ComposerHasPersonDraft);
                }

                SendKey(VirtualKeyBack);
                SendText(recipient);
                await Task.Delay(350, cancellationToken).ConfigureAwait(false);
                byte[] composerAfter = CaptureRegion(handle, CaptureArea.Composer, channel);
                if (!CryptographicOperations.FixedTimeEquals(
                        SHA256.HashData(composerBefore),
                        SHA256.HashData(composerAfter)))
                {
                    // The composer held no text before (C5), so this clears only the name typed into it.
                    SendChord(VirtualKeyControl, VirtualKeyA);
                    SendKey(VirtualKeyBack);
                    return new(false, true, handle, processId, "search_focus_not_verified");
                }

                SendKey(VirtualKeyReturn);
            }
            catch (LeasedInput.BurstStoppedException stop)
            {
                // MSGSEND1845's cleanup did not run: if the name went into the open chat's composer, it is still there.
                throw ComposerAfterStop(stop, ComposerChanged(handle, channel, composerBefore));
            }
        }
        else
        {
            // DISCORD1839 inherited, driven from here: Escape closes anything open
            // (Ctrl+K toggles an already open switcher shut), Ctrl+K opens the
            // switcher and the name is typed; its active result is opened only when
            // it names the recipient (C3). The keys travel through the same
            // SendInput path that already sends WhatsApp messages; a PowerShell
            // helper stole the foreground, which closes the switcher.
            // Ronda 24 (t1-c09, t2-c07, t3-c07, client opened cold): the switcher is used only once it is there. After
            // the shortcut, a new editable field (or a result row of its list) must hold the focus (the composer keeps
            // its own); the old fixed 1.4 s is now the most it waits. Nothing seen on a client started just now:
            // Escape and the shortcut once more; still nothing, the name is never typed (it would go into whatever has
            // the focus, maybe a composer) and nothing was written. Nothing seen on a client running for longer, or a
            // window that cannot be read at all: the timed path of before is kept (revisión 2 de r24).
            ValueTask<ClientInteraction> Read(CancellationToken token) => probe.ReadAsync(handle, content: false, token);
            SendKey(VirtualKeyEscape);
            await Task.Delay(300, cancellationToken).ConfigureAwait(false);
            // The focus before the shortcut is read once anything open was closed: a search left open is not taken
            // for the conversation's field.
            ClientInteraction before = await Read(cancellationToken).ConfigureAwait(false);
            // The open conversation's composer, pictured before the shortcut (MSGSEND1845's check): only a composer
            // that looks the same once the search is closed lets the turn say nothing was written (revisión 1 de r24:
            // a cold client can focus its composer by itself while the shortcut does nothing yet).
            byte[]? composerBefore = TryCaptureComposer(handle, channel);
            // Revisión 2 de r24: only a client started just now may stop the name for a search not seen open.
            bool coldClient = ClientStartedRecently(ProcessStartTime(processId), DateTime.Now);
            SendChord(VirtualKeyControl, VirtualKeyK);
            InputWait input = await AwaitOpenedInputAsync(
                Read, before, SearchInputBudget, InteractionPoll, cancellationToken).ConfigureAwait(false);
            if (AfterSearchWait(input, coldClient, retried: false) == SearchStep.Retry)
            {
                SendKey(VirtualKeyEscape);
                await Task.Delay(300, cancellationToken).ConfigureAwait(false);
                SendChord(VirtualKeyControl, VirtualKeyK);
                input = await AwaitOpenedInputAsync(
                    Read, before, SearchInputRetryBudget, InteractionPoll, cancellationToken).ConfigureAwait(false);
            }

            if (AfterSearchWait(input, coldClient, retried: true) == SearchStep.Refuse)
            {
                SendKey(VirtualKeyEscape);
                return UnverifiedChat(handle, processId, composerUntouched: true);
            }

            AuditReading(CaptureRegion(handle, CaptureArea.Body, channel), "discord: after ctrl+k");
            // C5: the switcher opens with an empty input, so nothing is deleted before the name; a selection that
            // shows text in the conversation's composer means the keys go there, onto the person's draft.
            if (await ComposerHoldsTextAsync(
                    handle, channel, CaptureRegion(handle, CaptureArea.Composer, channel), cancellationToken)
                .ConfigureAwait(false))
            {
                return new(false, false, handle, processId, ComposerHasPersonDraft);
            }

            SendText(recipient);
            (bool named, string? row) = await AwaitNamedResultAsync(
                Read, name => NamesRecipient(name, recipient), InteractionPoll, cancellationToken).ConfigureAwait(false);
            AuditReading(CaptureRegion(handle, CaptureArea.Body, channel), $"discord: after typing «{recipient}», named {named}");
            if (named)
            {
                // No stray modifier key-up is sent here: a lone Alt release activates
                // the window menu in Chromium and closed the switcher, so the click
                // below landed on the conversation behind it.
                // The result is opened with the mouse: Enter only dismisses the
                // switcher on this client (the capture after typing shows the row
                // highlighted, the one after Enter shows the previous chat with the
                // composer focused). The switcher is centred in the window and its
                // first row, the active one that named the recipient, sits just below the input.
                ClickAtRelative(handle, 0.5, DiscordSwitcherFirstRowHeightFraction);
                // The title is read for up to 3 s from the click (r23 c07: one read at 900 ms missed a title that came
                // later), and the first read that names the recipient ends the wait.
                string? shown = null;
                bool opened = await PollUntilAsync(
                    async token => (shown = await ShownRecipientAsync(handle, channel, recipient, token)
                        .ConfigureAwait(false)) is not null,
                    ChatTitleBudget,
                    ChatTitlePoll,
                    cancellationToken).ConfigureAwait(false);
                AuditReading(CaptureRegion(handle, CaptureArea.Body, channel), "discord: after click, title " + WindowTitle(handle));
                if (opened)
                {
                    return new(true, true, handle, processId, null, shown);
                }
            }

            // C3: no result named the recipient, so nothing was clicked; the switcher (open even when it was not seen)
            // is closed. After a named row that did not open the chat, the search is closed only when it was seen
            // open. The name should have gone only into the switcher's own input: the composer is pictured again; a
            // composer that changed (or cannot be read) may hold the name.
            if (!named || input == InputWait.Opened)
            {
                SendKey(VirtualKeyEscape);
                await Task.Delay(300, cancellationToken).ConfigureAwait(false);
            }

            bool composerChanged = true;
            if (input == InputWait.Opened)
            {
                composerChanged = ComposerChanged(handle, channel, composerBefore);
            }

            DesktopRecipientObservation unverified = UnverifiedChat(handle, processId, ComposerUntouched(input, composerChanged));
            return named ? unverified : NotNamedInSearch(unverified, row);
        }

        await Task.Delay(900, cancellationToken).ConfigureAwait(false);
        string? header = await ShownRecipientAsync(handle, channel, recipient, cancellationToken).ConfigureAwait(false);
        return new(
            header is not null,
            true,
            handle,
            processId,
            header is not null ? null : "recipient_identity_not_verified",
            header);
    }

    public async ValueTask<DesktopMessageObservation> SendAsync(
        ResolvedRecipient recipient,
        string text,
        CancellationToken cancellationToken)
    {
        if (!ProcessStillOwnsWindow(recipient.WindowHandle, recipient.ProcessId))
        {
            return new(false, false, string.Empty, "messaging_focus_not_verified");
        }

        return await LeasedInput.RunAsync(
            Lease,
            recipient.WindowHandle,
            token => SendInBurstAsync(recipient, text, token),
            (code, sent) => new DesktopMessageObservation(false, sent, string.Empty, LeaseStop(code)),
            cancellationToken).ConfigureAwait(false);
    }

    private static async ValueTask<DesktopMessageObservation> SendInBurstAsync(
        ResolvedRecipient recipient,
        string text,
        CancellationToken cancellationToken)
    {
        await NormalizeWindowAsync(recipient.Channel, recipient.WindowHandle, cancellationToken)
            .ConfigureAwait(false);

        bool targetVerified = await ShownRecipientAsync(
            recipient.WindowHandle,
            recipient.Channel,
            recipient.Name,
            cancellationToken).ConfigureAwait(false) is not null;
        if (!targetVerified)
        {
            return new(false, false, string.Empty, "recipient_identity_changed");
        }

        if (!FocusComposer(recipient.WindowHandle, recipient.Channel))
        {
            return new(false, false, string.Empty, "message_composer_not_focused");
        }

        await Task.Delay(200, cancellationToken).ConfigureAwait(false);
        // C5: the composer is read before anything is typed; the person's draft there is never cleared.
        byte[] before = CaptureRegion(recipient.WindowHandle, CaptureArea.Composer, recipient.Channel);
        if (await ComposerHoldsTextAsync(recipient.WindowHandle, recipient.Channel, before, cancellationToken)
                .ConfigureAwait(false))
        {
            return new(false, false, string.Empty, ComposerHasPersonDraft);
        }

        byte[] beforeSend;
        try
        {
            SendText(text);

            MessageVisualObservation draftObservation = await ObserveTypedDraftAsync(
                recipient, text, before, cancellationToken).ConfigureAwait(false);
            if (!draftObservation.Verified)
            {
                // The composer was empty before (C5): only the text typed here is cleared.
                SendChord(VirtualKeyControl, VirtualKeyA);
                SendKey(VirtualKeyBack);
                return new(false, false, string.Empty, "message_draft_not_verified");
            }

            // The delivery is read from the band of last messages just above the
            // composer, where the new outgoing bubble appears; the whole pane never
            // reads it (MSGSEND1845: «hola» sent and visible, pane OCR without it).
            beforeSend = CaptureRegion(recipient.WindowHandle, CaptureArea.LastMessages, recipient.Channel);
            SendKey(VirtualKeyReturn);
        }
        catch (LeasedInput.BurstStoppedException stop)
        {
            // Stopped between the first character and Enter: the message, whole or in part, may sit in the composer.
            throw ComposerAfterStop(
                stop, ComposerChanged(recipient.WindowHandle, recipient.Channel, before));
        }

        await Task.Delay(900, cancellationToken).ConfigureAwait(false);
        byte[] after = CaptureRegion(recipient.WindowHandle, CaptureArea.LastMessages, recipient.Channel);
        string afterText = await ReadTextAsync(after, cancellationToken).ConfigureAwait(false);
        string afterHash = Convert.ToHexStringLower(SHA256.HashData(after));
        bool changed = !CryptographicOperations.FixedTimeEquals(
            SHA256.HashData(beforeSend),
            SHA256.HashData(after));
        // The bubble's small text takes the same one-letter OCR noise as the
        // header title («probanda» for «probando»), so the tolerant word match
        // applies here too; the band changed and the header still names the
        // destination, which no other chat's text can satisfy at once. C4: the
        // receipt says the text read and whether it matched exactly or tolerantly.
        string deliveryRead = afterText;
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
                string widerText = await ReadTextAsync(wider, cancellationToken).ConfigureAwait(false);
                match = TextMatch(widerText, text);
                if (match is not null)
                {
                    deliveryRead = widerText;
                    afterHash = Convert.ToHexStringLower(SHA256.HashData(wider));
                    break;
                }
            }
        }

        bool stillTarget = await ShownRecipientAsync(
            recipient.WindowHandle,
            recipient.Channel,
            recipient.Name,
            cancellationToken).ConfigureAwait(false) is not null;
        bool delivered = changed && match is not null && stillTarget;
        return new(
            delivered,
            true,
            afterHash,
            delivered ? null : "message_delivery_not_verified",
            deliveryRead.Trim(),
            match);
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
            token => DraftInBurstAsync(recipient, text, token),
            (code, sent) => new DesktopMessageObservation(false, sent, string.Empty, LeaseStop(code)),
            cancellationToken).ConfigureAwait(false);
    }

    private static async ValueTask<DesktopMessageObservation> DraftInBurstAsync(
        ResolvedRecipient recipient,
        string text,
        CancellationToken cancellationToken)
    {
        await NormalizeWindowAsync(recipient.Channel, recipient.WindowHandle, cancellationToken)
            .ConfigureAwait(false);

        bool targetVerified = await ShownRecipientAsync(
            recipient.WindowHandle,
            recipient.Channel,
            recipient.Name,
            cancellationToken).ConfigureAwait(false) is not null;
        if (!targetVerified)
        {
            return new(false, false, string.Empty, "recipient_identity_changed");
        }

        if (!FocusComposer(recipient.WindowHandle, recipient.Channel))
        {
            return new(false, false, string.Empty, "message_composer_not_focused");
        }

        await Task.Delay(200, cancellationToken).ConfigureAwait(false);
        // C5: the composer is read before anything is typed; the person's draft there is never cleared.
        byte[] before = CaptureRegion(recipient.WindowHandle, CaptureArea.Composer, recipient.Channel);
        if (await ComposerHoldsTextAsync(recipient.WindowHandle, recipient.Channel, before, cancellationToken)
                .ConfigureAwait(false))
        {
            return new(false, false, string.Empty, ComposerHasPersonDraft);
        }

        MessageVisualObservation draftObservation;
        try
        {
            SendText(text);

            draftObservation = await ObserveTypedDraftAsync(
                recipient, text, before, cancellationToken).ConfigureAwait(false);
            if (!draftObservation.Verified)
            {
                // The composer was empty before (C5): only the text typed here is cleared.
                SendChord(VirtualKeyControl, VirtualKeyA);
                SendKey(VirtualKeyBack);
                return new(false, true, string.Empty, "message_draft_not_verified");
            }
        }
        catch (LeasedInput.BurstStoppedException stop)
        {
            // A draft stopped while being typed, or while its unverified text was being cleared: part of it may remain.
            throw ComposerAfterStop(
                stop, ComposerChanged(recipient.WindowHandle, recipient.Channel, before));
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
            byte[] bitmap = CaptureRegion(recipient.WindowHandle, CaptureArea.Composer, recipient.Channel);
            // Past the horizon the frame is read once more whether or not it held still: a read that outlasted the
            // horizon must not leave the text that landed meanwhile unseen.
            bool expired = clock.ElapsedMilliseconds >= TypedDraftHorizonMs;
            if (previous is not null && ContentChanged(before, bitmap)
                && (expired || !ContentChanged(previous, bitmap))
                && (read is null || ContentChanged(read, bitmap)))
            {
                read = bitmap;
                string observed = await ReadTextAsync(bitmap, cancellationToken).ConfigureAwait(false);
                if (TextMatch(observed, text) is { } match)
                {
                    return new(bitmap, true, observed.Trim(), match);
                }
            }

            if (expired)
            {
                await AuditUnverifiedDraftAsync(before, bitmap, cancellationToken).ConfigureAwait(false);
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
    private const int CaretMaxWidthPixels = 4;

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
    // WhatsApp's header that does; null when it names someone else or nothing.
    private static async ValueTask<string?> ShownRecipientAsync(
        nint handle,
        string channel,
        string recipient,
        CancellationToken cancellationToken)
    {
        if (string.Equals(channel, "discord", StringComparison.Ordinal))
        {
            string title = WindowTitle(handle);
            return NamesRecipient(title, recipient) ? title : null;
        }

        byte[] header = CaptureRegion(handle, CaptureArea.Header, "whatsapp");
        return HeaderLine(await ReadTextAsync(header, cancellationToken).ConfigureAwait(false), recipient);
    }

    // C1: a shown name (a window title, a search row, a header line) names the recipient when it holds the recipient's
    // whole words in order, case and accents folded: «ron» is not «Ronaldo», «ana» is not «Juana».
    internal static bool NamesRecipient(string shown, string recipient) =>
        Fold(recipient).Length > 0 && ContainsPhrase(shown, recipient);

    // C2: the header crop excludes the search box and the chat list, so the only chat name in it is the open
    // conversation's; the line of its reading that names the recipient is what the client showed. No letter is
    // tolerated: an OCR slip fails the read (the six readings of ReadTextAsync give the name more than one chance),
    // and «Mario» never passes for «Maria».
    internal static string? HeaderLine(string observed, string target)
    {
        foreach (string line in observed.Split('\n'))
        {
            if (NamesRecipient(line, target))
            {
                return line.Trim();
            }
        }

        return null;
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

    internal static bool DeliveryMatches(string observed, string target)
    {
        if (SpacelessMatches(observed, target))
        {
            return true;
        }

        string[] words = Fold(observed).Split(' ', StringSplitOptions.RemoveEmptyEntries);
        string[] tokens = Fold(target).Split(' ', StringSplitOptions.RemoveEmptyEntries);
        bool anyLong = false;
        foreach (string token in tokens)
        {
            if (token.Length < 4)
            {
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

    // With the audit on, an unverified draft keeps the band before typing and the
    // last band seen (read even when unchanged, so its OCR is kept too).
    private static async ValueTask AuditUnverifiedDraftAsync(
        byte[] before,
        byte[] observed,
        CancellationToken cancellationToken)
    {
        string? directory = Environment.GetEnvironmentVariable("BAXY_MESSAGING_OCR_AUDIT_DIR");
        if (string.IsNullOrWhiteSpace(directory) || !Directory.Exists(directory))
        {
            return;
        }

        try
        {
            File.WriteAllBytes(
                Path.Combine(directory, $"{DateTime.UtcNow:yyyyMMdd-HHmmss-fff}-{Environment.ProcessId}-draft-before.bmp"),
                before);
        }
        catch (IOException)
        {
            // The audit never changes delivery evidence.
        }

        _ = await ReadTextAsync(observed, cancellationToken).ConfigureAwait(false);
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
        bool Verified,
        string? Read,
        string? Match);

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
    // the list item that both show the searched name.
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

    // Discord's own title bar (a thin band above the header row): an empty spot
    // right of the navigation arrows, left of the centered title.
    private const int DiscordTitleBarClickLogicalX = 600;
    private const int DiscordTitleBarClickLogicalY = 14;

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
        LastMessages,
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
                CaptureArea.Composer => windowHeight - composerBand,
                CaptureArea.LastMessages => windowHeight - composerBand - lastMessagesBand,
                _ => Math.Min(80, windowHeight / 8),
            };
            int width = Math.Max(1, windowWidth - sourceX);
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

    // Positions in the normalized WhatsApp window (logical px from its top-left):
    // the «Chats» sidebar icon and the chat search box.
    private const int SidebarChatsLogicalX = 40;
    private const int SidebarChatsLogicalY = 70;
    private const int ChatSearchLogicalX = 190;
    private const int ChatSearchLogicalY = 124;

    // DISCORD1869: the quick switcher's first result, as a fraction of the
    // window's height (its modal is centred; the input sits at about 28 % and the
    // first row about 10 % below it).
    private const double DiscordSwitcherFirstRowHeightFraction = 0.381;

    private static void ClickAtRelative(nint handle, double widthFraction, double heightFraction)
    {
        LeasedInput.EnsureMayMovePointer();
        nint previousDpi = SetThreadDpiAwarenessContext((nint)(-4));
        try
        {
            if (!GetWindowRect(handle, out Rect rectangle))
            {
                return;
            }

            int x = rectangle.Left + (int)((rectangle.Right - rectangle.Left) * widthFraction);
            int y = rectangle.Top + (int)((rectangle.Bottom - rectangle.Top) * heightFraction);
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
            if (previousDpi != 0)
            {
                _ = SetThreadDpiAwarenessContext(previousDpi);
            }
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
