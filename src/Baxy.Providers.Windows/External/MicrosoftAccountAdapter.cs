using System.IO.Compression;
using System.Diagnostics;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Xml;
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
            $events=@();$items=$calendar.Items;$items.IncludeRecurrences=$true;$items.Sort('[Start]')
            $filter="[Start] < '"+$end.ToLocalTime().ToString('g')+"' AND [End] > '"+$start.ToLocalTime().ToString('g')+"'"
            $restricted=$items.Restrict($filter)
            foreach($item in $restricted) {
              if($events.Count -ge 200){break}
              try {
                $itemStart=([DateTime]$item.Start).ToUniversalTime()
                $itemEnd=([DateTime]$item.End).ToUniversalTime()
                if($itemEnd -gt $start -and $itemStart -lt $end) {
                  $events+=@([pscustomobject]@{entryId=[string]$item.EntryID;title=[string]$item.Subject;startUtc=$itemStart.ToString('O');endUtc=$itemEnd.ToString('O')})
                }
              } catch {}
            }
            [pscustomobject]@{ok=$true;effectObserved=$false;events=$events}|ConvertTo-Json -Depth 5 -Compress
          } else {
            $appointment=$outlook.CreateItem(1)
            $appointment.Subject=[string]$input.title
            $appointment.Start=$start.ToLocalTime()
            $appointment.End=$end.ToLocalTime()
            $appointment.Save();$effect=$true
            $entry=[string]$appointment.EntryID
            $verified=$session.GetItemFromID($entry)
            $ok=([string]$verified.Subject -ceq [string]$input.title) -and (([DateTime]$verified.Start).ToUniversalTime() -eq $start) -and (([DateTime]$verified.End).ToUniversalTime() -eq $end)
            [pscustomobject]@{ok=$ok;effectObserved=$true;entryId=$entry;title=[string]$verified.Subject;startUtc=([DateTime]$verified.Start).ToUniversalTime().ToString('O');endUtc=([DateTime]$verified.End).ToUniversalTime().ToString('O')}|ConvertTo-Json -Depth 4 -Compress
          }
        } catch {
          [pscustomobject]@{ok=$false;effectObserved=$effect;error='outlook_com_failed'}|ConvertTo-Json -Compress
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
          if($null -eq $latest){throw 'outlook_inbox_empty'}
          $entryId=[string]$latest.EntryID
          $verified=$session.GetItemFromID($entryId)
          if($null -eq $verified -or [string]$verified.EntryID -cne $entryId){throw 'outlook_latest_identity_mismatch'}
          $sender=[string]$verified.SenderEmailAddress
          try {$exchange=$verified.Sender.GetExchangeUser();if($null -ne $exchange -and $exchange.PrimarySmtpAddress){$sender=[string]$exchange.PrimarySmtpAddress}}catch{}
          $body=[string]$verified.Body;if($body.Length -gt 65536){$body=$body.Substring(0,65536)}
          $subject=[string]$verified.Subject
          $received=([DateTime]$verified.ReceivedTime).ToUniversalTime()
          if($input.action -eq 'read') {
            [pscustomobject]@{ok=$true;effectObserved=$false;entryId=$entryId;subject=$subject;sender=$sender;receivedUtc=$received.ToString('O');body=$body}|ConvertTo-Json -Depth 4 -Compress
            exit 0
          }
          $text=[string]$input.text
          $baseline=[DateTime]::UtcNow
          $reply=$verified.Reply()
          $reply.Body=$text+"`r`n`r`n"+[string]$reply.Body
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
                if($sentOn -ge $baseline.AddMinutes(-1) -and ([string]$candidate.Body).StartsWith($text,[StringComparison]::Ordinal)){$sent=$candidate;break}
              }catch{}
            }
          }
          if($null -eq $sent){throw 'outlook_sent_postread_missing'}
          [pscustomobject]@{ok=$true;effectObserved=$true;entryId=$entryId;subject=$subject;sender=$sender;receivedUtc=$received.ToString('O');body=$body;sentEntryId=[string]$sent.EntryID;sentUtc=([DateTime]$sent.SentOn).ToUniversalTime().ToString('O')}|ConvertTo-Json -Depth 4 -Compress
        } catch {
          [pscustomobject]@{ok=$false;effectObserved=$effect;error='outlook_mail_failed'}|ConvertTo-Json -Compress
          exit 2
        }
        """;

    private readonly string _documentsRoot;
    private readonly IExternalProcessRunner _runner;
    private readonly bool _requireOutlookProfileProbe;

    internal MicrosoftAccountAdapter(string dataRoot)
        : this(
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments), "BAXY"),
            new ExternalProcessRunner(),
            requireOutlookProfileProbe: true)
    {
        _ = dataRoot;
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
        or "email.latest.read" or "email.latest.reply"
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
        string input = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteString("action", reply ? "reply" : "read");
            if (text is not null) writer.WriteString("text", text);
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
        if (!IsOk(response.RootElement))
            return effectBoundary.Failure(operation, "outlook_mail_operation_failed", effect);
        JsonElement result = EmailResult(response.RootElement, reply, text);
        return ExternalJson.Success(operation, result, effect);
    }

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
        DateTimeOffset start = RequireUtc(arguments, "startUtc");
        DateTimeOffset end = RequireUtc(arguments, "endUtc");
        if (end <= start || end - start > TimeSpan.FromDays(366))
        {
            return ExternalJson.Failure(operation, "calendar_range_invalid");
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
            return effectBoundary.Failure(
                operation, "outlook_calendar_operation_failed", effect);
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
        effectBoundary.Cross(cancellationToken);
        Directory.CreateDirectory(_documentsRoot);
        if (new DirectoryInfo(_documentsRoot).LinkTarget is not null)
        {
            throw new IOException("Office root cannot be a link.");
        }
        string safeName = string.Concat(title.Select(character =>
            Path.GetInvalidFileNameChars().Contains(character) ? '_' : character)).Trim();
        safeName = safeName.Length == 0 ? "Documento" : safeName[..Math.Min(safeName.Length, 80)];
        string path = Path.Combine(_documentsRoot, safeName + "-" + Guid.NewGuid().ToString("N") + "." + format);
        byte[] package = CreateOfficePackage(format, title);
        await File.WriteAllBytesAsync(path, package, cancellationToken).ConfigureAwait(false);
        if (!File.Exists(path) || new FileInfo(path).Length <= 0
            || !VerifyOfficePackage(path, format, title))
        {
            return ExternalJson.Failure(operation, "office_document_create_not_verified", true);
        }
        string documentId = DocumentId(path);
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1);
            writer.WriteString("documentId", documentId); writer.WriteString("format", format);
            writer.WriteString("title", title); writer.WriteNumber("length", new FileInfo(path).Length);
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
            writer.WriteString("authority", "iso29500_ooxml_snapshot"); writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effectObserved: false);
    }

    private async ValueTask<ExternalProcessResult> RunPowerShellAsync(
        string script,
        string input,
        CancellationToken cancellationToken) => await _runner.RunAsync(
            "powershell.exe",
            ["-NoProfile", "-NonInteractive", "-Command", "& {\n" + script + "\n}",
                Convert.ToBase64String(Encoding.UTF8.GetBytes(input))],
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

    private static DateTimeOffset RequireUtc(JsonElement arguments, string name)
    {
        string value = ExternalJson.RequiredString(arguments, name);
        if (!DateTimeOffset.TryParse(value, out DateTimeOffset parsed) || parsed.Offset != TimeSpan.Zero)
        {
            throw new InvalidDataException($"{name} must be an exact UTC timestamp.");
        }
        return parsed;
    }

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
        writer.WriteEndArray(); writer.WriteString("authority", "outlook_mapi_snapshot"); writer.WriteEndObject();
    });

    private static JsonElement EmailResult(JsonElement root, bool replied, string? replyText) =>
        ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1);
            writer.WriteString("messageId", Opaque("email", root.GetProperty("entryId").GetString() ?? string.Empty));
            writer.WriteString("subject", root.GetProperty("subject").GetString());
            writer.WriteString("sender", root.GetProperty("sender").GetString());
            writer.WriteString("receivedUtc", root.GetProperty("receivedUtc").GetString());
            writer.WriteString("body", root.GetProperty("body").GetString());
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

    private static byte[] CreateOfficePackage(string format, string title)
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
                    + "<w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\"><w:body><w:p><w:r><w:t>"
                    + EscapeXml(title) + "</w:t></w:r></w:p><w:sectPr/></w:body></w:document>");
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

    private static bool VerifyOfficePackage(string path, string format, string expectedTitle)
    {
        try
        {
            return string.Equals(ReadOfficeText(path, format), expectedTitle, StringComparison.Ordinal);
        }
        catch (InvalidDataException)
        {
            return false;
        }
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
