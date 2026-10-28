using System.IO.Compression;
using System.Diagnostics;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Xml;
using Baxy.Providers.Windows.Infrastructure;
using Microsoft.Win32;

namespace Baxy.Providers.Windows.External;

internal sealed class MicrosoftAccountAdapter : IExternalOperationAdapter
{
    private const string CalendarScript = """
        $ErrorActionPreference='Stop'
        $input=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($args[0]))|ConvertFrom-Json
        $effect=$false
        try {
          $outlook=New-Object -ComObject Outlook.Application
          $session=$outlook.GetNamespace('MAPI')
          $calendar=$session.GetDefaultFolder(9)
          $start=[DateTimeOffset]::Parse($input.startUtc).UtcDateTime
          $end=[DateTimeOffset]::Parse($input.endUtc).UtcDateTime
          if($input.action -eq 'list') {
            # Auditoría final (regla 3): an appointment whose fields could not be read is counted, never dropped, and a
            # list cut at 200 says so. Ronda final 40: sorted by [Start] before IncludeRecurrences and then restricted, the
            # order Outlook's Items.IncludeRecurrences documentation requires for recurring appointments to be expanded.
            $events=@();$unread=0;$truncated=$false;$items=$calendar.Items;$items.Sort('[Start]');$items.IncludeRecurrences=$true
            $filter="[Start] < '"+$end.ToLocalTime().ToString('g')+"' AND [End] > '"+$start.ToLocalTime().ToString('g')+"'"
            $restricted=$items.Restrict($filter)
            foreach($item in $restricted) {
              if($events.Count -ge 200){$truncated=$true;break}
              try {
                $itemStart=([DateTime]$item.Start).ToUniversalTime()
                $itemEnd=([DateTime]$item.End).ToUniversalTime()
                if($itemEnd -gt $start -and $itemStart -lt $end) {
                  $events+=@([pscustomobject]@{entryId=[string]$item.EntryID;title=[string]$item.Subject;startUtc=$itemStart.ToString('O');endUtc=$itemEnd.ToString('O')})
                }
              } catch {$unread++}
            }
            [pscustomobject]@{ok=$true;effectObserved=$false;events=$events;unreadCount=$unread;truncated=$truncated}|ConvertTo-Json -Depth 5 -Compress
          } else {
            $appointment=$outlook.CreateItem(1)
            $appointment.Subject=[string]$input.title
            $appointment.Start=$start.ToLocalTime()
            $appointment.End=$end.ToLocalTime()
            $appointment.Save();$effect=$true
            $entry=[string]$appointment.EntryID
            $verified=$session.GetItemFromID($entry)
            $ok=([string]$verified.Subject -ceq [string]$input.title) -and (([DateTime]$verified.Start).ToUniversalTime() -eq $start) -and (([DateTime]$verified.End).ToUniversalTime() -eq $end)
            if(-not $ok){[pscustomobject]@{ok=$false;effectObserved=$true;error='outlook_calendar_postread_mismatch';entryId=$entry;title=[string]$verified.Subject;startUtc=([DateTime]$verified.Start).ToUniversalTime().ToString('O');endUtc=([DateTime]$verified.End).ToUniversalTime().ToString('O')}|ConvertTo-Json -Compress;exit 2}
            [pscustomobject]@{ok=$true;effectObserved=$true;entryId=$entry;title=[string]$verified.Subject;startUtc=([DateTime]$verified.Start).ToUniversalTime().ToString('O');endUtc=([DateTime]$verified.End).ToUniversalTime().ToString('O')}|ConvertTo-Json -Depth 4 -Compress
          }
        } catch {
          [pscustomobject]@{ok=$false;effectObserved=$effect;error='outlook_calendar_com_failed'}|ConvertTo-Json -Compress
          exit 2
        }
        """;

    private const string MailScript = """
        $ErrorActionPreference='Stop'
        $input=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($args[0]))|ConvertFrom-Json
        $effect=$false
        try {
          $outlook=New-Object -ComObject Outlook.Application
          $session=$outlook.GetNamespace('MAPI')
          $inbox=$session.GetDefaultFolder(6)
          $items=$inbox.Items;$items.Sort('[ReceivedTime]',$true)
          $latest=$null;$candidate=$items.GetFirst()
          for($index=0;$index -lt 100 -and $null -ne $candidate;$index++){
            if([int]$candidate.Class -eq 43){$latest=$candidate;break}
            $candidate=$items.GetNext()
          }
          # Auditoría final (regla 3): what was looked at is what is said: the whole inbox without a mail item (it may
          # hold invitations or receipts), or only its newest 100 items.
          if($null -eq $latest){if($null -eq $candidate){throw 'outlook_inbox_has_no_mail_item'};throw 'outlook_no_mail_in_latest_100_items'}
          $entryId=[string]$latest.EntryID
          $verified=$session.GetItemFromID($entryId)
          if($null -eq $verified -or [string]$verified.EntryID -cne $entryId){throw 'outlook_latest_identity_mismatch'}
          $sender=[string]$verified.SenderEmailAddress
          try {$exchange=$verified.Sender.GetExchangeUser();if($null -ne $exchange -and $exchange.PrimarySmtpAddress){$sender=[string]$exchange.PrimarySmtpAddress}}catch{}
          $body=[string]$verified.Body;$bodyLength=$body.Length;if($body.Length -gt 6000){$body=$body.Substring(0,6000)}
          $subject=[string]$verified.Subject
          $received=([DateTime]$verified.ReceivedTime).ToUniversalTime()
          # Renew al máximo (w8): the reply goes only to the mail the person's yes named (expectedMessageId, the opaque id
          # email.latest.read gave, computed as the adapter's Opaque); a newer mail is said and nothing is sent.
          $sha=[Security.Cryptography.SHA256]::Create()
          $messageId='email_'+(-join ($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($entryId))|ForEach-Object {$_.ToString('x2')})).Substring(0,24)
          $expected=[string]$input.expectedMessageId
          if($input.action -eq 'reply' -and $expected.Length -gt 0 -and $messageId -cne $expected) {
            [pscustomobject]@{ok=$false;effectObserved=$false;error='email_latest_changed';entryId=$entryId;subject=$subject;sender=$sender;receivedUtc=$received.ToString('O')}|ConvertTo-Json -Compress
            exit 2
          }
          if($input.action -eq 'read') {
            [pscustomobject]@{ok=$true;effectObserved=$false;entryId=$entryId;subject=$subject;sender=$sender;receivedUtc=$received.ToString('O');body=$body;bodyLength=$bodyLength}|ConvertTo-Json -Depth 4 -Compress
            exit 0
          }
          $text=[string]$input.text
          $baseline=[DateTime]::UtcNow
          $reply=$verified.Reply()
          $reply.Body=$text+"`r`n`r`n"+[string]$reply.Body
          # Ronda final 33 (regla 3): only a sent mail of the same conversation is this reply (another «ok» sent a minute
          # ago would pass on its text alone).
          $conversation=[string]$verified.ConversationID
          $reply.Send();$effect=$true
          $sentFolder=$session.GetDefaultFolder(5)
          $sent=$null
          for($attempt=0;$attempt -lt 30 -and $null -eq $sent;$attempt++){
            Start-Sleep -Milliseconds 500
            $sentItems=$sentFolder.Items;$sentItems.Sort('[SentOn]',$true);$seen=0
            foreach($candidate in $sentItems){
              if($seen++ -ge 50){break}
              try {
                $sentOn=([DateTime]$candidate.SentOn).ToUniversalTime()
                if($sentOn -ge $baseline.AddMinutes(-1) -and $conversation.Length -gt 0 -and [string]$candidate.ConversationID -eq $conversation -and ([string]$candidate.Body).StartsWith($text,[StringComparison]::Ordinal)){$sent=$candidate;break}
              }catch{}
            }
          }
          if($null -eq $sent){throw 'outlook_sent_postread_missing'}
          [pscustomobject]@{ok=$true;effectObserved=$true;entryId=$entryId;subject=$subject;sender=$sender;receivedUtc=$received.ToString('O');body=$body;bodyLength=$bodyLength;sentEntryId=[string]$sent.EntryID;sentUtc=([DateTime]$sent.SentOn).ToUniversalTime().ToString('O')}|ConvertTo-Json -Depth 4 -Compress
        } catch {
          $code=[string]$_.Exception.Message;if(@('outlook_inbox_has_no_mail_item','outlook_no_mail_in_latest_100_items','outlook_latest_identity_mismatch','outlook_sent_postread_missing') -notcontains $code){$code='outlook_mail_com_failed'}
          [pscustomobject]@{ok=$false;effectObserved=$effect;error=$code}|ConvertTo-Json -Compress
          exit 2
        }
        """;

    private readonly string _documentsRoot;
    private readonly IExternalProcessRunner _runner;
    private readonly bool _requireOutlookProfileProbe;

    internal MicrosoftAccountAdapter()
        : this(
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments), "BAXY"),
            new ExternalProcessRunner(),
            requireOutlookProfileProbe: true)
    {
    }

    internal MicrosoftAccountAdapter(
        string documentsRoot,
        IExternalProcessRunner runner,
        bool requireOutlookProfileProbe = false)
    {
        _documentsRoot = Path.GetFullPath(documentsRoot);
        _runner = runner ?? throw new ArgumentNullException(nameof(runner));
        _requireOutlookProfileProbe = requireOutlookProfileProbe;
    }

    public bool CanHandle(string operation) => operation is
        "calendar.event.create" or "calendar.event.list"
        or "email.latest.read" or "email.latest.reply" or "email.send"
        or "office.document.create" or "office.document.read";

    public async ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        var effectBoundary = new ExternalEffectBoundary();
        try
        {
            return operation switch
            {
                "calendar.event.create" => await CalendarAsync(
                    operation, arguments, true, effectBoundary, cancellationToken)
                    .ConfigureAwait(false),
                "calendar.event.list" => await CalendarAsync(
                    operation, arguments, false, effectBoundary, cancellationToken)
                    .ConfigureAwait(false),
                "email.latest.read" => await MailAsync(
                    operation, arguments, false, effectBoundary, cancellationToken)
                    .ConfigureAwait(false),
                "email.latest.reply" => await MailAsync(
                    operation, arguments, true, effectBoundary, cancellationToken)
                    .ConfigureAwait(false),
                "email.send" => await SendMailAsync(
                    operation, arguments, effectBoundary, cancellationToken)
                    .ConfigureAwait(false),
                "office.document.create" => await CreateDocumentAsync(
                    operation, arguments, effectBoundary, cancellationToken)
                    .ConfigureAwait(false),
                "office.document.read" => await ReadDocumentAsync(operation, arguments, cancellationToken)
                    .ConfigureAwait(false),
                _ => ExternalJson.Failure(operation, "external_operation_not_supported"),
            };
        }
        catch (OperationCanceledException) when (
            cancellationToken.IsCancellationRequested && effectBoundary.WasCrossed)
        {
            return effectBoundary.Failure(operation, "microsoft_desktop_adapter_failed");
        }
        catch (Exception exception) when (exception is IOException
            or UnauthorizedAccessException or InvalidDataException or JsonException
            or TimeoutException)
        {
            return effectBoundary.Failure(operation, "microsoft_desktop_adapter_failed");
        }
    }

    private async ValueTask<ExternalCapabilityReceipt> MailAsync(
        string operation,
        JsonElement arguments,
        bool reply,
        ExternalEffectBoundary effectBoundary,
        CancellationToken cancellationToken)
    {
        if (_requireOutlookProfileProbe && !HasClassicOutlookProfile())
            return ExternalJson.Failure(operation, "outlook_profile_not_configured");
        string? text = reply ? ExternalJson.RequiredString(arguments, "text") : null;
        string? expected = null;
        if (reply && !TryExpectedMessageId(arguments, out expected))
            return ExpectedMessageIdInvalid(operation);
        string input = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteString("action", reply ? "reply" : "read");
            if (text is not null) writer.WriteString("text", text);
            if (expected is not null) writer.WriteString("expectedMessageId", expected);
            writer.WriteEndObject();
        }).GetRawText();
        if (reply)
        {
            effectBoundary.Cross(cancellationToken);
        }
        ExternalProcessResult process = await RunPowerShellAsync(MailScript, input, cancellationToken)
            .ConfigureAwait(false);
        using JsonDocument response = ParseProcessJson(process);
        bool effect = response.RootElement.TryGetProperty("effectObserved", out JsonElement observed)
            && observed.ValueKind == JsonValueKind.True;
        // Renew al máximo (w8): the script refused before Reply() because the newest mail is not the one named; nothing
        // was sent, and the result names the mail that is newest now.
        if (reply && !effect && ErrorCode(response.RootElement, string.Empty) == LatestChanged)
            return LatestMailRefusal(operation, response.RootElement, expected);
        if (!IsOk(response.RootElement))
            return effectBoundary.Failure(operation, ErrorCode(response.RootElement, "outlook_mail_operation_failed"), effect);
        JsonElement result = EmailResult(response.RootElement, reply, text);
        return ExternalJson.Success(operation, result, effect);
    }

    private const string LatestChanged = "email_latest_changed";
    private const string MessageIdRequired = "email_reply_message_id_required";

    private static readonly System.Text.RegularExpressions.Regex DotRuns = new(
        @"\.{2,}", System.Text.RegularExpressions.RegexOptions.CultureInvariant);
    private static readonly System.Text.RegularExpressions.Regex MessageIdShape = new(
        "^email_[0-9a-f]{24}$", System.Text.RegularExpressions.RegexOptions.CultureInvariant);

    // Renew al máximo (w8): before the person is asked to send a reply, the reply is bound to one mail. Without
    // expectedMessageId the «sí» named only {text}, and a mail that arrived between the yes and the run got the reply
    // (another person). A reply that names no mail, or names one that is no longer the newest, fails here with the mail
    // that is newest now (its messageId, sender, subject and time), so the yes asked next names it; the run compares
    // again in the script, before Reply(). Read only: the read is email.latest.read's own.
    public async ValueTask<ExternalCapabilityReceipt?> PreflightAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        if (operation != "email.latest.reply")
            return null;
        if (!TryExpectedMessageId(arguments, out string? expected))
            return ExpectedMessageIdInvalid(operation);
        ExternalCapabilityReceipt read;
        try
        {
            read = await MailAsync("email.latest.read", default, false, new ExternalEffectBoundary(), cancellationToken)
                .ConfigureAwait(false);
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException
            or InvalidDataException or JsonException or TimeoutException or KeyNotFoundException
            or InvalidOperationException)
        {
            read = ExternalJson.FailureBeforeEffect("email.latest.read", "outlook_mail_operation_failed");
        }

        if (!read.Verified || read.Result is not { } latest)
        {
            // The newest mail could not be read: with a mail named, the run reads and compares again; with none, no yes
            // is asked for a reply bound to no mail, and the read's own failure says why.
            return expected is not null
                ? null
                : new ExternalCapabilityReceipt(operation, false, false, MessageIdNext(null, null),
                    read.ErrorCode ?? MessageIdRequired);
        }

        string? now = latest.GetProperty("messageId").GetString();
        if (expected is not null && string.Equals(now, expected, StringComparison.Ordinal))
            return null;
        return new ExternalCapabilityReceipt(operation, false, false, MessageIdNext(latest, expected),
            expected is null ? MessageIdRequired : LatestChanged);
    }

    // Absent or null: no mail named (the run replies to the newest, as before; only Bypass runs it without a yes).
    private static bool TryExpectedMessageId(JsonElement arguments, out string? expected)
    {
        expected = null;
        if (arguments.ValueKind != JsonValueKind.Object
            || !arguments.TryGetProperty("expectedMessageId", out JsonElement value)
            || value.ValueKind == JsonValueKind.Null)
            return true;
        if (value.ValueKind != JsonValueKind.String || !MessageIdShape.IsMatch(value.GetString() ?? string.Empty))
            return false;
        expected = value.GetString();
        return true;
    }

    private static ExternalCapabilityReceipt ExpectedMessageIdInvalid(string operation) =>
        new(operation, false, false, ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1);
            writer.WriteString("argument", "expectedMessageId");
            if (ModelAids.On(ModelAids.ReplyMessageIdNext))
            {
                writer.WriteString("next",
                    "nothing was sent: expectedMessageId is the messageId email.latest.read gave (email_ and 24 hex digits)");
            }
            writer.WriteEndObject();
        }), "email_message_id_invalid");

    private static ExternalCapabilityReceipt LatestMailRefusal(string operation, JsonElement root, string? expected) =>
        new(operation, false, false, MessageIdNext(ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteString("messageId", Opaque("email", root.GetProperty("entryId").GetString() ?? string.Empty));
            writer.WriteString("sender", root.GetProperty("sender").GetString());
            writer.WriteString("subject", root.GetProperty("subject").GetString());
            writer.WriteString("receivedUtc", root.GetProperty("receivedUtc").GetString());
            writer.WriteEndObject();
        }), expected), LatestChanged);

    // The mail that is newest now (null: it could not be read) and, with aid reply_message_id_next, what to do next.
    private static JsonElement MessageIdNext(JsonElement? latest, string? expected) => ExternalJson.Create(writer =>
    {
        writer.WriteStartObject(); writer.WriteNumber("version", 1);
        string? now = null;
        if (latest is { ValueKind: JsonValueKind.Object } mail)
        {
            writer.WriteStartObject("latest");
            foreach (string name in LatestFacts)
            {
                if (mail.TryGetProperty(name, out JsonElement value) && value.ValueKind == JsonValueKind.String)
                    writer.WriteString(name, value.GetString());
            }
            writer.WriteEndObject();
            now = mail.TryGetProperty("messageId", out JsonElement id) ? id.GetString() : null;
        }
        if (expected is not null) writer.WriteString("expectedMessageId", expected);
        if (ModelAids.On(ModelAids.ReplyMessageIdNext))
        {
            writer.WriteString("next", "nothing was sent: " + (expected is null
                ? "a reply names the mail it answers"
                : "the newest mail is no longer the one named")
                + (now is null
                    ? "; email.latest.read gives its messageId"
                    : "; to answer the mail in latest, call email.latest.reply again with expectedMessageId " + now));
        }
        writer.WriteEndObject();
    });

    private static readonly string[] LatestFacts = ["messageId", "sender", "subject", "receivedUtc"];

    // Fase 7 (D4): a mail to a free address from the owner's classic Outlook profile,
    // verified by the copy in Sent Items (recipient, text, time). The address is
    // checked before anything runs; the subject defaults to the text's opening. The
    // copy is the one sent only when one of its recipients' addresses is the address,
    // case aside; the receipt carries the copy's recipients and subject as read.
    // message.send.test (its fixed test destination) sends through the same script.
    internal const string SendMailScript = """
        $ErrorActionPreference='Stop'
        $input=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($args[0]))|ConvertFrom-Json
        $effect=$false
        try {
          $outlook=New-Object -ComObject Outlook.Application
          $session=$outlook.GetNamespace('MAPI')
          $to=[string]$input.to;$text=[string]$input.text;$subject=[string]$input.subject
          $baseline=[DateTime]::UtcNow
          $sentFolder=$session.GetDefaultFolder(5)
          # Goal FT/proveedores (revision de recibos): lo que ya estaba en Enviados no es este envio (el margen de 2 min
          # del reloj dejaba que un correo anterior al mismo destinatario, con el mismo comienzo, lo confirmara).
          $before=@{};$older=$sentFolder.Items;$older.Sort('[SentOn]',$true);$seen=0
          foreach($candidate in $older){ if($seen++ -ge 50){break}; try { $before[[string]$candidate.EntryID]=$true } catch {} }
          $mail=$outlook.CreateItem(0)
          $mail.To=$to;$mail.Subject=$subject;$mail.Body=$text
          $mail.Send();$effect=$true
          $sent=$null
          for($attempt=0;$attempt -lt 40 -and $null -eq $sent;$attempt++){
            Start-Sleep -Milliseconds 500
            $sentItems=$sentFolder.Items;$sentItems.Sort('[SentOn]',$true);$seen=0
            foreach($candidate in $sentItems){
              if($seen++ -ge 50){break}
              try {
                $sentOn=([DateTime]$candidate.SentOn).ToUniversalTime()
                $addresses=@(foreach($recipient in $candidate.Recipients){[string]$recipient.Address})
                if($before.ContainsKey([string]$candidate.EntryID)){continue}
                if($sentOn -ge $baseline.AddMinutes(-2) -and ($addresses | Where-Object {$_ -ieq $to}) -and ([string]$candidate.Body).StartsWith($text,[StringComparison]::Ordinal)){$sent=$candidate;$sentTo=$addresses;break}
              }catch{}
            }
          }
          if($null -eq $sent){throw 'outlook_sent_postread_missing'}
          [pscustomobject]@{ok=$true;effectObserved=$true;sentEntryId=[string]$sent.EntryID;sentUtc=([DateTime]$sent.SentOn).ToUniversalTime().ToString('O');sentTo=@($sentTo);subject=[string]$sent.Subject}|ConvertTo-Json -Compress
        } catch {
          $code=[string]$_.Exception.Message;if($code -cne 'outlook_sent_postread_missing'){$code='outlook_mail_send_failed'}
          [pscustomobject]@{ok=$false;effectObserved=$effect;error=$code}|ConvertTo-Json -Compress
          exit 2
        }
        """;

    private static readonly System.Text.RegularExpressions.Regex MailAddress = new(
        @"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,63}$",
        System.Text.RegularExpressions.RegexOptions.Compiled);

    private async ValueTask<ExternalCapabilityReceipt> SendMailAsync(
        string operation,
        JsonElement arguments,
        ExternalEffectBoundary effectBoundary,
        CancellationToken cancellationToken)
    {
        string to = ExternalJson.RequiredString(arguments, "to").Trim();
        string text = ExternalJson.RequiredString(arguments, "text");
        string? subject = arguments.TryGetProperty("subject", out JsonElement subjectElement)
            && subjectElement.ValueKind == JsonValueKind.String
            ? subjectElement.GetString()?.Trim()
            : null;
        if (!MailAddress.IsMatch(to))
            return ExternalJson.Failure(operation, "mail_address_invalid");
        if (_requireOutlookProfileProbe && !HasClassicOutlookProfile())
            return ExternalJson.Failure(operation, "outlook_profile_not_configured");
        if (string.IsNullOrWhiteSpace(subject))
        {
            string firstLine = text.Split(['\r', '\n'], StringSplitOptions.RemoveEmptyEntries).FirstOrDefault() ?? text;
            subject = SubjectFromText(firstLine);
        }

        string input = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteString("to", to);
            writer.WriteString("subject", subject);
            writer.WriteString("text", text);
            writer.WriteEndObject();
        }).GetRawText();
        effectBoundary.Cross(cancellationToken);
        ExternalProcessResult process = await RunPowerShellAsync(SendMailScript, input, cancellationToken)
            .ConfigureAwait(false);
        using JsonDocument response = ParseProcessJson(process);
        JsonElement root = response.RootElement;
        bool effect = root.TryGetProperty("effectObserved", out JsonElement observed)
            && observed.ValueKind == JsonValueKind.True;
        if (!IsOk(root))
            return effectBoundary.Failure(operation, effect ? "mail_delivery_not_verified" : "outlook_mail_send_failed", effect);
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1);
            writer.WriteStartArray("sentTo");
            if (root.TryGetProperty("sentTo", out JsonElement sentTo) && sentTo.ValueKind == JsonValueKind.Array)
            {
                foreach (JsonElement address in sentTo.EnumerateArray())
                {
                    writer.WriteStringValue(address.GetString());
                }
            }
            writer.WriteEndArray();
            writer.WriteString("subject", root.TryGetProperty("subject", out JsonElement sentSubject)
                && sentSubject.ValueKind == JsonValueKind.String ? sentSubject.GetString() : string.Empty);
            writer.WriteString("text", text);
            writer.WriteBoolean("sent", true);
            writer.WriteString("sentMessageId", Opaque("email", root.GetProperty("sentEntryId").GetString() ?? string.Empty));
            writer.WriteString("sentUtc", root.GetProperty("sentUtc").GetString());
            writer.WriteString("authority", "outlook_sent_postread");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effect);
    }

    // The subject a mail takes from its text's opening when none is given: the text itself up to 78 characters, else its
    // first 75 and «…». The cut never falls between the two halves of a character (an emoji): one half alone went out
    // as «�» in the subject.
    internal static string SubjectFromText(string text) =>
        text.Length <= 78 ? text : text[..(char.IsHighSurrogate(text[74]) ? 74 : 75)] + "…";

    private async ValueTask<ExternalCapabilityReceipt> CalendarAsync(
        string operation,
        JsonElement arguments,
        bool create,
        ExternalEffectBoundary effectBoundary,
        CancellationToken cancellationToken)
    {
        if (_requireOutlookProfileProbe && !HasClassicOutlookProfile())
        {
            return ExternalJson.Failure(operation, "outlook_profile_not_configured");
        }
        // Renew al máximo (w5): a time that is not an exact instant threw, and came back «microsoft_desktop_adapter_failed»,
        // read as Outlook failing; a range the wrong way round was a bare code. Both say which argument and why, before
        // anything ran. A time with its own offset is that instant, taken in UTC.
        foreach (string name in (string[])["startUtc", "endUtc"])
        {
            if (!TryInstant(arguments, name, out _))
                return CalendarRefusal(operation, "calendar_time_not_exact", create, name,
                    $"{name} has no offset, so it names no exact time; write it in UTC with Z, like 2026-10-23T21:00:00Z");
        }
        TryInstant(arguments, "startUtc", out DateTimeOffset start);
        TryInstant(arguments, "endUtc", out DateTimeOffset end);
        if (end <= start)
        {
            return CalendarRefusal(operation, "calendar_range_invalid", create, "endUtc",
                "endUtc is not after startUtc");
        }
        // Renew al máximo (w8): Outlook keeps an appointment's times to the minute, so a create with seconds was saved,
        // failed its own post-read (outlook_calendar_postread_mismatch, with no event id) and a retry made a second one.
        if (create && (start.Ticks % TimeSpan.TicksPerMinute != 0 || end.Ticks % TimeSpan.TicksPerMinute != 0))
        {
            return CalendarRefusal(operation, "calendar_time_not_whole_minute", create,
                start.Ticks % TimeSpan.TicksPerMinute != 0 ? "startUtc" : "endUtc",
                "Outlook keeps an event's times to the minute; write them with :00 seconds");
        }
        if (end - start > TimeSpan.FromDays(366))
        {
            return CalendarRefusal(operation, "calendar_range_invalid", create, "endUtc",
                "the range is longer than 366 days; a shorter one, or several, is read");
        }
        string? title = create ? ExternalJson.RequiredString(arguments, "title") : null;
        string input = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteString("action", create ? "create" : "list");
            writer.WriteString("startUtc", start.ToString("O"));
            writer.WriteString("endUtc", end.ToString("O"));
            if (title is not null) writer.WriteString("title", title);
            writer.WriteEndObject();
        }).GetRawText();
        if (create)
        {
            effectBoundary.Cross(cancellationToken);
        }
        ExternalProcessResult process = await RunPowerShellAsync(CalendarScript, input, cancellationToken)
            .ConfigureAwait(false);
        using JsonDocument response = ParseProcessJson(process);
        bool effect = response.RootElement.TryGetProperty("effectObserved", out JsonElement observed)
            && observed.ValueKind == JsonValueKind.True;
        if (!IsOk(response.RootElement))
        {
            ExternalCapabilityReceipt failed = effectBoundary.Failure(
                operation, ErrorCode(response.RootElement, "outlook_calendar_operation_failed"), effect);
            // Renew al máximo (w8): an event saved whose read-back differs from what was asked exists: the failure
            // names it (its id and the times read), so it is not created a second time.
            return create && effect && response.RootElement.TryGetProperty("entryId", out JsonElement saved)
                && saved.ValueKind == JsonValueKind.String
                    ? failed with
                    {
                        Result = ExternalJson.Create(writer =>
                        {
                            writer.WriteStartObject(); writer.WriteNumber("version", 1);
                            writer.WriteString("eventId", Opaque("event", saved.GetString() ?? string.Empty));
                            foreach (string name in (string[])["title", "startUtc", "endUtc"])
                            {
                                if (response.RootElement.TryGetProperty(name, out JsonElement value)
                                    && value.ValueKind == JsonValueKind.String)
                                    writer.WriteString(name, value.GetString());
                            }
                            if (ModelAids.On(ModelAids.CalendarTimeNext))
                                writer.WriteString("next", "an event was created with the title and times read here, "
                                    + "which differ from those asked; creating it again makes a second event");
                            writer.WriteEndObject();
                        }),
                    }
                    : failed;
        }
        JsonElement result = create
            ? CalendarCreated(response.RootElement)
            : CalendarList(response.RootElement);
        return ExternalJson.Success(operation, result, effect);
    }

    private static bool HasClassicOutlookProfile()
    {
        using RegistryKey? profiles = Registry.CurrentUser.OpenSubKey(
            @"Software\Microsoft\Office\16.0\Outlook\Profiles",
            writable: false);
        if (profiles?.GetSubKeyNames().Length is not > 0) return false;
        foreach (Process process in Process.GetProcessesByName("OUTLOOK"))
        {
            using (process)
            {
                string title = process.MainWindowTitle;
                if (title.Contains("Bienvenido", StringComparison.OrdinalIgnoreCase)
                    || title.Contains("Welcome to Microsoft Outlook", StringComparison.OrdinalIgnoreCase))
                    return false;
            }
        }
        return true;
    }

    private async ValueTask<ExternalCapabilityReceipt> CreateDocumentAsync(
        string operation,
        JsonElement arguments,
        ExternalEffectBoundary effectBoundary,
        CancellationToken cancellationToken)
    {
        string format = ExternalJson.RequiredString(arguments, "format");
        if (format is not ("docx" or "xlsx"))
        {
            return ExternalJson.Failure(operation, "office_format_invalid");
        }
        string title = ExternalJson.RequiredString(arguments, "title");
        // Feria 2026-10-27: the body, one paragraph per line of each entry (blank lines left out); only Word has them.
        string[] paragraphs = arguments.TryGetProperty("paragraphs", out JsonElement paragraphsElement)
            && paragraphsElement.ValueKind == JsonValueKind.Array
            ? paragraphsElement.EnumerateArray()
                .SelectMany(item => (item.GetString() ?? string.Empty).ReplaceLineEndings("\n").Split('\n'))
                .Select(line => line.Trim()).Where(line => line.Length > 0).ToArray()
            : [];
        if (paragraphs.Length > 0 && format != "docx")
        {
            return ExternalJson.Failure(operation, "office_paragraphs_docx_only");
        }
        // A character XML cannot hold (a control character) would leave a file Office cannot open.
        if (!((string[])[title, .. paragraphs]).All(XmlCanHold))
        {
            return ExternalJson.Failure(operation, "office_text_invalid_character");
        }
        effectBoundary.Cross(cancellationToken);
        Directory.CreateDirectory(_documentsRoot);
        if (new DirectoryInfo(_documentsRoot).LinkTarget is not null)
        {
            throw new IOException("Office root cannot be a link.");
        }
        string safeName = string.Concat(title.Select(character =>
            Path.GetInvalidFileNameChars().Contains(character) ? '_' : character)).Trim();
        // file.open shows it by this name and refuses one with «..» in it (a title ending in «...»).
        safeName = DotRuns.Replace(safeName, ".");
        safeName = safeName.Length == 0 ? "Documento" : safeName[..Math.Min(safeName.Length, 80)];
        string path = Path.Combine(_documentsRoot, safeName + "-" + Guid.NewGuid().ToString("N") + "." + format);
        byte[] package = CreateOfficePackage(format, title, paragraphs);
        await File.WriteAllBytesAsync(path, package, cancellationToken).ConfigureAwait(false);
        if (!File.Exists(path) || new FileInfo(path).Length <= 0
            || !VerifyOfficePackage(path, format, string.Join('\n', [title, .. paragraphs])))
        {
            return ExternalJson.Failure(operation, "office_document_create_not_verified", true);
        }
        string documentId = DocumentId(path);
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1);
            writer.WriteString("documentId", documentId); writer.WriteString("format", format);
            writer.WriteString("title", title); writer.WriteString("name", Path.GetFileName(path));
            if (paragraphs.Length > 0)
            {
                writer.WriteNumber("paragraphCount", paragraphs.Length);
                writer.WriteNumber("wordCount", paragraphs.Sum(paragraph =>
                    paragraph.Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries).Length));
            }
            writer.WriteNumber("length", new FileInfo(path).Length);
            writer.WriteString("authority", "iso29500_ooxml_postread"); writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effectObserved: true);
    }

    private async ValueTask<ExternalCapabilityReceipt> ReadDocumentAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        string documentId = ExternalJson.RequiredString(arguments, "documentId");
        string? path = Directory.Exists(_documentsRoot)
            ? Directory.EnumerateFiles(_documentsRoot, "*.*", SearchOption.TopDirectoryOnly)
                .Where(candidate => Path.GetExtension(candidate) is ".docx" or ".xlsx")
                .SingleOrDefault(candidate => string.Equals(DocumentId(candidate), documentId, StringComparison.Ordinal))
            : null;
        if (path is null)
        {
            return ExternalJson.Failure(operation, "office_document_not_resolved");
        }
        string format = Path.GetExtension(path).TrimStart('.').ToLowerInvariant();
        string text = await Task.Run(() => ReadOfficeText(path, format), cancellationToken)
            .ConfigureAwait(false);
        // Ronda final 8 (regla 3): a text cut at 256 000 characters says it was cut, and how long it is.
        int textLength = text.Length;
        if (text.Length > 256_000)
        {
            text = text[..256_000];
        }
        string sha256 = Convert.ToHexStringLower(SHA256.HashData(Encoding.UTF8.GetBytes(text)));
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1);
            writer.WriteString("documentId", documentId); writer.WriteString("format", format);
            writer.WriteString("text", text); writer.WriteString("textSha256", sha256);
            if (textLength > text.Length)
            {
                writer.WriteBoolean("textTruncated", true);
                writer.WriteNumber("textLength", textLength);
            }
            writer.WriteString("authority", "iso29500_ooxml_snapshot"); writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effectObserved: false);
    }

    private async ValueTask<ExternalProcessResult> RunPowerShellAsync(
        string script,
        string input,
        CancellationToken cancellationToken) => await _runner.RunPowerShellAsync(
            script,
            [Convert.ToBase64String(Encoding.UTF8.GetBytes(input))],
            TimeSpan.FromSeconds(60),
            cancellationToken).ConfigureAwait(false);

    private static JsonDocument ParseProcessJson(ExternalProcessResult process)
    {
        string line = process.Output.Split(['\r', '\n'], StringSplitOptions.RemoveEmptyEntries)
            .LastOrDefault() ?? "{}";
        if (line.Length > 1024 * 1024)
        {
            throw new InvalidDataException("Microsoft adapter response exceeded its bound.");
        }
        return JsonDocument.Parse(line);
    }

    private static bool IsOk(JsonElement root) => root.TryGetProperty("ok", out JsonElement ok)
        && ok.ValueKind == JsonValueKind.True;

    // The cause the Outlook script named (its own codes only), or the operation's general failure.
    private static string ErrorCode(JsonElement root, string fallback) =>
        root.TryGetProperty("error", out JsonElement error) && error.ValueKind == JsonValueKind.String
            && error.GetString() is { Length: > 0 } code
            ? code
            : fallback;

    private static readonly System.Text.RegularExpressions.Regex ExplicitOffset = new(
        @"(?:[Zz]|[+-][0-9]{2}:?[0-9]{2})$", System.Text.RegularExpressions.RegexOptions.CultureInvariant);

    // An exact instant: a date and time that carries its offset (Z, or +hh:mm), in UTC.
    private static bool TryInstant(JsonElement arguments, string name, out DateTimeOffset instant)
    {
        string value = ExternalJson.RequiredString(arguments, name).Trim();
        instant = default;
        if (!ExplicitOffset.IsMatch(value)
            || !DateTimeOffset.TryParse(value, System.Globalization.CultureInfo.InvariantCulture,
                System.Globalization.DateTimeStyles.None, out DateTimeOffset parsed))
        {
            return false;
        }
        instant = parsed.ToUniversalTime();
        return true;
    }

    // A calendar call refused before anything ran: the argument, and (aid calendar_time_next) why, as a sentence.
    private static ExternalCapabilityReceipt CalendarRefusal(
        string operation, string code, bool create, string argument, string why) =>
        new(operation, false, false, ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1);
            writer.WriteString("argument", argument);
            if (ModelAids.On(ModelAids.CalendarTimeNext))
                writer.WriteString("next", why + (create ? "; no event was created" : "; no event was read"));
            writer.WriteEndObject();
        }), code);

    private static JsonElement CalendarCreated(JsonElement root)
    {
        string entryId = root.GetProperty("entryId").GetString() ?? string.Empty;
        return ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1);
            writer.WriteString("eventId", Opaque("event", entryId));
            writer.WriteString("title", root.GetProperty("title").GetString());
            writer.WriteString("startUtc", root.GetProperty("startUtc").GetString());
            writer.WriteString("endUtc", root.GetProperty("endUtc").GetString());
            writer.WriteString("authority", "outlook_mapi_postread"); writer.WriteEndObject();
        });
    }

    private static JsonElement CalendarList(JsonElement root) => ExternalJson.Create(writer =>
    {
        writer.WriteStartObject(); writer.WriteNumber("version", 1);
        writer.WriteStartArray("events");
        if (root.TryGetProperty("events", out JsonElement events) && events.ValueKind == JsonValueKind.Array)
        {
            foreach (JsonElement item in events.EnumerateArray().Take(200))
            {
                writer.WriteStartObject();
                writer.WriteString("eventId", Opaque("event", item.GetProperty("entryId").GetString() ?? string.Empty));
                writer.WriteString("title", item.GetProperty("title").GetString());
                writer.WriteString("startUtc", item.GetProperty("startUtc").GetString());
                writer.WriteString("endUtc", item.GetProperty("endUtc").GetString());
                writer.WriteEndObject();
            }
        }
        writer.WriteEndArray();
        if (root.TryGetProperty("unreadCount", out JsonElement unread) && unread.ValueKind == JsonValueKind.Number
            && unread.GetInt32() > 0)
            writer.WriteNumber("unreadAppointments", unread.GetInt32());
        if (root.TryGetProperty("truncated", out JsonElement truncated) && truncated.ValueKind == JsonValueKind.True)
            writer.WriteBoolean("truncatedAt200", true);
        writer.WriteString("authority", "outlook_mapi_snapshot"); writer.WriteEndObject();
    });

    private static JsonElement EmailResult(JsonElement root, bool replied, string? replyText) =>
        ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1);
            writer.WriteString("messageId", Opaque("email", root.GetProperty("entryId").GetString() ?? string.Empty));
            writer.WriteString("subject", root.GetProperty("subject").GetString());
            writer.WriteString("sender", root.GetProperty("sender").GetString());
            writer.WriteString("receivedUtc", root.GetProperty("receivedUtc").GetString());
            string? body = root.GetProperty("body").GetString();
            writer.WriteString("body", body);
            // Ronda final 8 (regla 3): a body cut (at 6 000 characters since the ronda 44) says it was cut, and how long it is.
            if (root.TryGetProperty("bodyLength", out JsonElement length) && length.TryGetInt32(out int whole)
                && whole > (body?.Length ?? 0))
            {
                writer.WriteBoolean("bodyTruncated", true);
                writer.WriteNumber("bodyLength", whole);
            }
            if (replied)
            {
                writer.WriteString("sentMessageId", Opaque("email", root.GetProperty("sentEntryId").GetString() ?? string.Empty));
                writer.WriteString("sentUtc", root.GetProperty("sentUtc").GetString());
                writer.WriteString("replyTextSha256", Convert.ToHexStringLower(SHA256.HashData(
                    Encoding.UTF8.GetBytes(replyText ?? string.Empty))));
            }
            writer.WriteString("authority", replied
                ? "outlook_mapi_sent_postread" : "outlook_mapi_latest_snapshot");
            writer.WriteEndObject();
        });

    private static string DocumentId(string path) => Opaque(
        "document",
        Path.GetFullPath(path).ToUpperInvariant());

    private static string Opaque(string prefix, string value) => prefix + "_"
        + Convert.ToHexStringLower(SHA256.HashData(Encoding.UTF8.GetBytes(value)))[..24];

    private static byte[] CreateOfficePackage(string format, string title, string[] paragraphs)
    {
        using var output = new MemoryStream();
        using (var archive = new ZipArchive(output, ZipArchiveMode.Create, leaveOpen: true))
        {
            if (format == "docx")
            {
                WriteEntry(archive, "[Content_Types].xml", """
                    <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
                    <Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>
                    """);
                WriteEntry(archive, "_rels/.rels", """
                    <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
                    <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>
                    """);
                WriteEntry(archive, "word/document.xml",
                    "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
                    + "<w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\"><w:body>"
                    + string.Concat(((string[])[title, .. paragraphs]).Select(paragraph =>
                        "<w:p><w:r><w:t>" + EscapeXml(paragraph) + "</w:t></w:r></w:p>"))
                    + "<w:sectPr/></w:body></w:document>");
            }
            else
            {
                WriteEntry(archive, "[Content_Types].xml", """
                    <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
                    <Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>
                    """);
                WriteEntry(archive, "_rels/.rels", """
                    <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
                    <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>
                    """);
                WriteEntry(archive, "xl/workbook.xml", """
                    <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
                    <workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Hoja 1" sheetId="1" r:id="rId1"/></sheets></workbook>
                    """);
                WriteEntry(archive, "xl/_rels/workbook.xml.rels", """
                    <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
                    <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>
                    """);
                WriteEntry(archive, "xl/worksheets/sheet1.xml",
                    "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
                    + "<worksheet xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\"><sheetData><row r=\"1\"><c r=\"A1\" t=\"inlineStr\"><is><t>"
                    + EscapeXml(title) + "</t></is></c></row></sheetData></worksheet>");
            }
        }
        return output.ToArray();
    }

    private static bool VerifyOfficePackage(string path, string format, string expectedText)
    {
        try
        {
            return string.Equals(ReadOfficeText(path, format), expectedText, StringComparison.Ordinal);
        }
        catch (InvalidDataException)
        {
            return false;
        }
    }

    // Every character is one XML holds (a surrogate pair counts as one).
    private static bool XmlCanHold(string text)
    {
        for (int index = 0; index < text.Length; index++)
        {
            if (XmlConvert.IsXmlChar(text[index]))
            {
                continue;
            }
            if (index + 1 < text.Length && XmlConvert.IsXmlSurrogatePair(text[index + 1], text[index]))
            {
                index++;
                continue;
            }
            return false;
        }
        return true;
    }

    private static string ReadOfficeText(string path, string format)
    {
        using ZipArchive archive = ZipFile.OpenRead(path);
        string entryName = format == "docx" ? "word/document.xml" : "xl/worksheets/sheet1.xml";
        ZipArchiveEntry entry = archive.GetEntry(entryName)
            ?? throw new InvalidDataException("Office document main part is missing.");
        if (entry.Length > 8 * 1024 * 1024)
        {
            throw new InvalidDataException("Office document main part exceeds its bound.");
        }
        var settings = new XmlReaderSettings
        {
            DtdProcessing = DtdProcessing.Prohibit,
            XmlResolver = null,
            MaxCharactersInDocument = 8 * 1024 * 1024,
        };
        using Stream stream = entry.Open();
        using XmlReader reader = XmlReader.Create(stream, settings);
        var text = new StringBuilder();
        while (reader.Read())
        {
            if (reader.NodeType == XmlNodeType.Element && reader.LocalName == "t")
            {
                if (text.Length > 0) text.Append('\n');
                text.Append(reader.ReadElementContentAsString());
            }
        }
        return text.ToString();
    }

    private static void WriteEntry(ZipArchive archive, string name, string content)
    {
        ZipArchiveEntry entry = archive.CreateEntry(name, CompressionLevel.Optimal);
        using Stream stream = entry.Open();
        using var writer = new StreamWriter(
            stream,
            new UTF8Encoding(encoderShouldEmitUTF8Identifier: false, throwOnInvalidBytes: true));
        writer.Write(content.Trim());
    }

    private static string EscapeXml(string value)
    {
        var output = new StringBuilder(value.Length + 32);
        foreach (char character in value)
        {
            output.Append(character switch
            {
                '&' => "&amp;",
                '<' => "&lt;",
                '>' => "&gt;",
                '\"' => "&quot;",
                '\'' => "&apos;",
                _ => character.ToString(),
            });
        }
        return output.ToString();
    }
}
