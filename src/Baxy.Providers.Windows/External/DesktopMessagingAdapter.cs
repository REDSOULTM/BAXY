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
            // Owner decision 2026-09-18 (DECISIONES_DUENO_2026-09-18 §3): the mail
            // test destination is the owner's own test mailbox; the send goes out
            // through the owner's classic Outlook profile and is verified by the
            // copy in Sent Items.
            ["email"] = "autor@example.com",
        };

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

        if (string.Equals(channel, "email", StringComparison.Ordinal))
        {
            return await SendTestMailAsync(requestedRecipient, forced, text, cancellationToken)
                .ConfigureAwait(false);
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
    private const ushort VirtualKeyDown = 0x28;
    private const uint KeyUp = 0x0002;
    private const uint Unicode = 0x0004;

    // DISCORD1839 (client.channel.locate) inherited: the quick switcher is opened,
    // typed and READ inside one PowerShell process. A separate process steals the
    // foreground and Discord closes the switcher on blur, so the rows read from
    // outside were the DM list and Enter opened whatever it had selected
    // («Pedro», then «Julia», DISCORD1857 runs a-c). The rows the switcher adds
    // are the ones absent before it opened; Enter is pressed only after stepping
    // down to the first of them that names the recipient.
    private static readonly ExternalProcessRunner SwitcherRunner = new();

    private const string DiscordOpenDirectMessageScript = """
        $ErrorActionPreference='Stop';$label=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($args[0]));$needle=$label.ToLowerInvariant()
        Add-Type -AssemblyName UIAutomationClient;Add-Type -AssemblyName UIAutomationTypes;Add-Type -AssemblyName System.Windows.Forms
        $sig='using System;using System.Runtime.InteropServices;public static class BaxyDmWin{[DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);[DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();[DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h,int c);[DllImport("user32.dll")] public static extern bool SetCursorPos(int x,int y);[DllImport("user32.dll")] public static extern void mouse_event(uint f,int dx,int dy,uint d,int e);}'
        if(-not ([System.Management.Automation.PSTypeName]'BaxyDmWin').Type){Add-Type -TypeDefinition $sig}
        $root=[System.Windows.Automation.AutomationElement]::RootElement
        $cond=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ClassNameProperty,'Chrome_WidgetWin_1')
        $w=$null;foreach($c in $root.FindAll([System.Windows.Automation.TreeScope]::Children,$cond)){if($c.Current.Name -match 'Discord'){$w=$c;break}}
        if($null -eq $w){[pscustomobject]@{ok=$false;error='client_window_not_found'}|ConvertTo-Json -Compress;exit 2}
        $h=[IntPtr]$w.Current.NativeWindowHandle;[void][BaxyDmWin]::ShowWindow($h,9)
        $escaped=[regex]::Replace($label,'([+^%~(){}\[\]])','{$1}')
        function Find-Row {param($win,$nd) foreach($e in $win.FindAll([System.Windows.Automation.TreeScope]::Descendants,[System.Windows.Automation.Condition]::TrueCondition)){if($e.Current.ControlType.ProgrammaticName -eq 'ControlType.ListItem'){$n=$e.Current.Name;if($n -and $n.ToLowerInvariant().Contains($nd)){$rect=$e.Current.BoundingRectangle;if($rect.Width -gt 0 -and $rect.Height -gt 0){return [pscustomobject]@{name=$n.Substring(0,[Math]::Min(160,$n.Length));x=[int]($rect.X+$rect.Width/2);y=[int]($rect.Y+$rect.Height/2)}}}}};return $null}
        $opened=$false;$chosen='';$rounds=0
        for($round=0;$round -lt 4 -and -not $opened;$round++){
          $rounds=$round+1
          [void][BaxyDmWin]::SetForegroundWindow($h);Start-Sleep -Milliseconds 500
          if([BaxyDmWin]::GetForegroundWindow() -ne $h){Start-Sleep -Milliseconds 400;continue}
          [System.Windows.Forms.SendKeys]::SendWait('{ESC}');Start-Sleep -Milliseconds 300
          # No row names the recipient before the switcher opens (the test user has
          # no entry in the direct-message list); the row that names it after typing
          # is a switcher result and is clicked by its own rectangle. Counting the
          # rows the switcher added selected a neighbour instead (run d: «Julia»).
          if($null -ne (Find-Row $w $needle)){[pscustomobject]@{ok=$false;error='recipient_visible_before_search'}|ConvertTo-Json -Compress;exit 4}
          [System.Windows.Forms.SendKeys]::SendWait('^k');Start-Sleep -Milliseconds 1400
          if([BaxyDmWin]::GetForegroundWindow() -ne $h){[System.Windows.Forms.SendKeys]::SendWait('{ESC}');continue}
          [System.Windows.Forms.SendKeys]::SendWait('^a');Start-Sleep -Milliseconds 120
          [System.Windows.Forms.SendKeys]::SendWait('{BACKSPACE}');Start-Sleep -Milliseconds 120
          [System.Windows.Forms.SendKeys]::SendWait($escaped);Start-Sleep -Milliseconds 900
          $row=$null
          for($poll=0;$poll -lt 10 -and $null -eq $row;$poll++){$row=Find-Row $w $needle;if($null -ne $row){break};Start-Sleep -Milliseconds 400}
          if($null -eq $row){[System.Windows.Forms.SendKeys]::SendWait('{ESC}');Start-Sleep -Milliseconds 300;continue}
          $chosen=$row.name
          [void][BaxyDmWin]::SetCursorPos($row.x,$row.y);Start-Sleep -Milliseconds 150
          [BaxyDmWin]::mouse_event(0x0002,0,0,0,0);[BaxyDmWin]::mouse_event(0x0004,0,0,0,0)
          Start-Sleep -Milliseconds 1500
          $opened=$true
        }
        [pscustomobject]@{ok=$opened;title=$w.Current.Name;chosen=$chosen;rounds=$rounds}|ConvertTo-Json -Compress
        """;

    /// <summary>Open the Discord direct message whose switcher row names the
    /// recipient, inside one process; returns the window title afterwards, or null
    /// when no switcher row named it (nothing is opened and nothing is typed into
    /// an open chat).</summary>
    private static async ValueTask<string?> OpenDiscordDirectMessageAsync(
        string recipient,
        CancellationToken cancellationToken)
    {
        ExternalProcessResult process = await SwitcherRunner.RunAsync(
            "powershell.exe",
            ["-NoProfile", "-NonInteractive", "-Command", "& {" + "\n" + DiscordOpenDirectMessageScript + "\n" + "}",
                Convert.ToBase64String(Encoding.UTF8.GetBytes(recipient))],
            TimeSpan.FromSeconds(60),
            cancellationToken).ConfigureAwait(false);
        string[] lines = process.Output.Split(['\r', '\n'], StringSplitOptions.RemoveEmptyEntries);
        string line = lines.Length > 0 ? lines[^1] : "{}";
        AuditReading([], $"discord quick switcher (exit {process.ExitCode}): {line}\n{process.Error}");
        try
        {
            using JsonDocument document = JsonDocument.Parse(line);
            JsonElement root = document.RootElement;
            if (root.TryGetProperty("ok", out JsonElement ok) && ok.ValueKind == JsonValueKind.True
                && root.TryGetProperty("title", out JsonElement title) && title.ValueKind == JsonValueKind.String)
            {
                return title.GetString();
            }
        }
        catch (JsonException)
        {
        }

        return null;
    }

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
        // The header is read twice because the first frame after a resize or
        // focus change may still be transitional. (Escape must not be sent here:
        // in WhatsApp it closes the open conversation.)

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
            SendChord(VirtualKeyControl, VirtualKeyA);
            await Task.Delay(100, cancellationToken).ConfigureAwait(false);
            SendKey(VirtualKeyBack);
            SendText(recipient);
            await Task.Delay(350, cancellationToken).ConfigureAwait(false);
            byte[] composerAfter = CaptureRegion(handle, CaptureArea.Composer, channel);
            if (!CryptographicOperations.FixedTimeEquals(
                    SHA256.HashData(composerBefore),
                    SHA256.HashData(composerAfter)))
            {
                SendChord(VirtualKeyControl, VirtualKeyA);
                SendKey(VirtualKeyBack);
                return new(false, true, handle, processId, "search_focus_not_verified");
            }

            SendKey(VirtualKeyReturn);
        }
        else
        {
            // DISCORD1839 inherited: the switcher needs about 1.4 s to open and its
            // rows are read by UI Automation before Enter; the row that names the
            // recipient is selected with Down, and nothing is opened when no row
            // names it.
            // The switcher is opened, typed and read inside ONE process: a separate
            // process steals the foreground and Discord closes the switcher on blur,
            // so rows read from outside were the DM list and Enter opened whatever
            // was selected («Pedro», then «Julia»: DISCORD1857 runs a-c, nothing
            // sent, the title guard refused each time). Nothing is typed into an
            // open chat: the switcher swallows the name, and when no row of its own
            // names the recipient nothing is opened.
            // The composer band is NOT compared here: opening the intended chat
            // changes it too (its placeholder names the recipient), which refused a
            // correct open in run d. The guard is the window title, which the caller
            // reads again right after this block.
            string? openedTitle = await OpenDiscordDirectMessageAsync(recipient, cancellationToken)
                .ConfigureAwait(false);
            if (openedTitle is null)
            {
                return new(false, true, handle, processId, "recipient_not_in_quick_switcher");
            }
        }

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
            return new(bitmap, changed && (ContainsPhrase(observedText, text) || DeliveryMatches(observedText, text)));
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
        // The bubble's small text takes the same one-letter OCR noise as the
        // header title («probanda» for «probando»), so the tolerant word match
        // applies here too; the band changed and the header still names the
        // destination, which no other chat's text can satisfy at once.
        bool visible = ContainsPhrase(afterText, text) || DeliveryMatches(afterText, text);
        if (!visible)
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
                if (ContainsPhrase(widerText, text) || DeliveryMatches(widerText, text))
                {
                    visible = true;
                    afterHash = Convert.ToHexStringLower(SHA256.HashData(wider));
                    break;
                }
            }
        }

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
            return new(bitmap, changed && (ContainsPhrase(observedText, text) || DeliveryMatches(observedText, text)));
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
        return HeaderMatches(text, target);
    }

    // The header crop excludes the search box and the chat list, so the only
    // chat name in it is the open conversation's; Tesseract still misreads one
    // letter of it now and then («Misica» for «Música»), so a word of five or
    // more letters is accepted at one edit of distance.
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

    internal static bool HeaderMatches(string observed, string target)
    {
        string foldedObserved = Fold(observed);
        string foldedTarget = Fold(target);
        if (foldedTarget.Length == 0)
        {
            return false;
        }

        if (foldedObserved.Contains(foldedTarget, StringComparison.Ordinal))
        {
            return true;
        }

        string[] words = foldedObserved.Split(' ', StringSplitOptions.RemoveEmptyEntries);
        foreach (string token in foldedTarget.Split(' ', StringSplitOptions.RemoveEmptyEntries))
        {
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

        return true;
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
    // 400 rather than the 430 midpoint: right after a send the list narrowed by
    // about 35 px and the title, clipped at the crop's left edge, read as noise.
    private const int WhatsAppConversationPaneOffsetAt96Dpi = 400;
    private const int DiscordConversationPaneOffsetAt96Dpi = 320;
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
            int sourceX = string.Equals(channel, "whatsapp", StringComparison.Ordinal)
                ? Math.Min(
                    Math.Max(0, windowWidth - 1),
                    (int)(WhatsAppConversationPaneOffsetAt96Dpi * scale))
                : Math.Min(Math.Max(0, windowWidth - 1), (int)(DiscordConversationPaneOffsetAt96Dpi * scale));
            if (area == CaptureArea.LastMessages && outgoingBandWidthAt96Dpi > 0)
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

    private static void ClickAt(nint handle, int logicalX, int logicalY)
    {
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
