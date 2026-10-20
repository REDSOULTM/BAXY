using System.Text;
using System.Text.Json;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// BAXY Renew cu (C10 variante, C11): a format given to what the person has open in Word or Excel (bold, italic,
/// underline, an alignment), through the running application's own object model, and read back from it. By the
/// window's ribbon the 4B pressed the column header for «la fila 1», formatted before choosing, took Ctrl+A for select
/// all (in a Spanish Office it opens a file) and a folded ribbon hid «Negrita». Nothing is started: with no Word or
/// Excel running, nothing is done and it says so. Word formats its selection, its title or a paragraph by number; Excel its
/// selection, a row, a column or a range, which it leaves chosen as a click on its header would.
/// </summary>
internal sealed class OfficeFormatAdapter(IExternalProcessRunner? runner = null) : IExternalOperationAdapter
{
    internal const string Operation = "office.format.apply";

    private readonly IExternalProcessRunner _runner = runner ?? new ExternalProcessRunner();

    public bool CanHandle(string operation) => operation == Operation;

    public async ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        if (Request(arguments) is not { } request)
            return ExternalJson.FailureBeforeEffect(operation, "office_format_arguments_invalid");

        var effectBoundary = new ExternalEffectBoundary();
        effectBoundary.Cross(cancellationToken);
        ExternalProcessResult process;
        try
        {
            process = await _runner.RunPowerShellAsync(
                Script, [Convert.ToBase64String(Encoding.UTF8.GetBytes(request))], TimeSpan.FromSeconds(30), cancellationToken)
                .ConfigureAwait(false);
        }
        catch (Exception exception) when (exception is IOException or TimeoutException or InvalidOperationException
            or System.ComponentModel.Win32Exception)
        {
            return effectBoundary.Failure(operation, "office_format_adapter_failed");
        }

        string? line = process.Output.Split(['\r', '\n'], StringSplitOptions.RemoveEmptyEntries).LastOrDefault();
        if (line is null)
            return effectBoundary.Failure(operation, "office_format_no_receipt");
        using JsonDocument response = JsonDocument.Parse(line);
        return Receipt(operation, arguments, response.RootElement, effectBoundary);
    }

    // The arguments as the script reads them; null when they do not name one format of one application.
    internal static string? Request(JsonElement arguments)
    {
        if (arguments.ValueKind != JsonValueKind.Object)
            return null;
        string? app = Text(arguments, "app");
        string? style = Text(arguments, "style");
        string target = Text(arguments, "target") ?? "selection";
        if (app is not ("word" or "excel") || style is not ("bold" or "italic" or "underline" or "center" or "left" or "right"))
            return null;
        // Word formats its selection, its title or a paragraph by number; Excel its selection, a row, a column or cells.
        if (app == "word" ? target is not ("selection" or "title" or "paragraph") : target is not ("selection" or "row" or "column" or "cells"))
            return null;
        int? paragraph = arguments.TryGetProperty("paragraph", out JsonElement paragraphValue)
            && paragraphValue.ValueKind == JsonValueKind.Number && paragraphValue.TryGetInt32(out int numbered) ? numbered : null;
        if (target == "paragraph" && paragraph is not > 0)
            return null;
        int? row = arguments.TryGetProperty("row", out JsonElement rowValue) && rowValue.ValueKind == JsonValueKind.Number
            && rowValue.TryGetInt32(out int given) ? given : null;
        string? column = Text(arguments, "column");
        string? cells = Text(arguments, "cells");
        if ((target == "row" && row is not > 0) || (target == "column" && (column is null || !column.All(char.IsAsciiLetter)))
            || (target == "cells" && cells is null))
            return null;
        bool on = !(arguments.TryGetProperty("on", out JsonElement onValue) && onValue.ValueKind == JsonValueKind.False);
        var buffer = new System.Buffers.ArrayBufferWriter<byte>();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            writer.WriteStartObject();
            writer.WriteString("app", app);
            writer.WriteString("style", style);
            writer.WriteBoolean("on", on);
            writer.WriteString("target", target);
            if (row is int number) writer.WriteNumber("row", number); else writer.WriteNull("row");
            if (column is null) writer.WriteNull("column"); else writer.WriteString("column", column.ToUpperInvariant());
            if (cells is null) writer.WriteNull("cells"); else writer.WriteString("cells", cells);
            if (paragraph is int number2) writer.WriteNumber("paragraph", number2); else writer.WriteNull("paragraph");
            writer.WriteEndObject();
        }

        return Encoding.UTF8.GetString(buffer.WrittenSpan);
    }

    internal static ExternalCapabilityReceipt Receipt(
        string operation, JsonElement arguments, JsonElement answer, ExternalEffectBoundary effectBoundary)
    {
        bool effect = answer.TryGetProperty("effectObserved", out JsonElement observed) && observed.ValueKind == JsonValueKind.True;
        string error = Text(answer, "error") ?? string.Empty;
        if (!(answer.TryGetProperty("ok", out JsonElement ok) && ok.ValueKind == JsonValueKind.True))
        {
            string code = error.Length > 0 ? error : "office_format_not_read_back";
            return effect ? effectBoundary.Failure(operation, code, true) : ExternalJson.FailureBeforeEffect(operation, code);
        }

        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("app", Text(arguments, "app"));
            writer.WriteString("style", Text(arguments, "style"));
            writer.WriteBoolean("on", !(arguments.TryGetProperty("on", out JsonElement on) && on.ValueKind == JsonValueKind.False));
            writer.WriteString("document", Text(answer, "document"));
            if (Text(answer, "sheet") is { } sheet)
                writer.WriteString("sheet", sheet);
            // What received it: Excel's range by its address («1:1», «A:A», «B2:C4»), or Word's selection.
            writer.WriteString("applied", Text(answer, "applied"));
            if (answer.TryGetProperty("chars", out JsonElement chars) && chars.ValueKind == JsonValueKind.Number)
                writer.WriteNumber("characters", chars.GetInt32());
            writer.WriteString("authority", "office_com_object_model_postread");
            writer.WriteEndObject();
        });
        return ExternalJson.Switched(operation, result, effect);
    }

    private static string? Text(JsonElement element, string name) =>
        element.TryGetProperty(name, out JsonElement value) && value.ValueKind == JsonValueKind.String
            && value.GetString() is { Length: > 0 } text
            ? text.Trim()
            : null;

    private const string Script = """
        $ErrorActionPreference='Stop'
        $request=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($args[0])) | ConvertFrom-Json
        function Answer($h){ [pscustomobject]$h | ConvertTo-Json -Compress; exit 0 }
        $app=[string]$request.app; $style=[string]$request.style; $on=[bool]$request.on; $target=[string]$request.target
        # The running application the person has open: never one started here.
        try { $office=[Runtime.InteropServices.Marshal]::GetActiveObject($(if($app -eq 'word'){ 'Word.Application' } else { 'Excel.Application' })) }
        catch { Answer @{ ok=$false; effectObserved=$false; error='office_app_not_open' } }
        $sent=$false
        try {
          if($app -eq 'word'){
            if($office.Documents.Count -lt 1){ Answer @{ ok=$false; effectObserved=$false; error='office_no_document' } }
            $doc=$office.ActiveDocument
            if($target -eq 'selection'){
              $sel=$office.Selection
              # wdSelectionIP (1) is a caret with nothing selected: nothing to format.
              if([int]$sel.Type -eq 1 -or ([string]$sel.Text).Length -eq 0){ Answer @{ ok=$false; effectObserved=$false; error='office_selection_empty' } }
              $named='selection'
            } else {
              $chosen=$null
              if($target -eq 'paragraph'){
                if([int]$request.paragraph -gt $doc.Paragraphs.Count){ Answer @{ ok=$false; effectObserved=$false; error='office_target_invalid' } }
                $chosen=$doc.Paragraphs.Item([int]$request.paragraph); $named=('paragraph '+[int]$request.paragraph)
              } else {
                # The title: the paragraph styled as the document's Title or Heading 1 (wdStyleTitle -63, wdStyleHeading1
                # -2, by their local names), else the first one with text.
                $titles=@(); foreach($id in @(-63,-2)){ try { $titles+=[string]$doc.Styles.Item($id).NameLocal } catch {} }
                $index=0
                foreach($p in $doc.Paragraphs){ $index++; if(([string]$p.Range.Text).Trim().Length -gt 0 -and $titles -contains [string]$p.Style.NameLocal){ $chosen=$p; break } }
                if($null -eq $chosen){ $index=0; foreach($p in $doc.Paragraphs){ $index++; if(([string]$p.Range.Text).Trim().Length -gt 0){ $chosen=$p; break } } }
                if($null -eq $chosen){ Answer @{ ok=$false; effectObserved=$false; error='office_target_invalid' } }
                $named=('title, paragraph '+$index)
              }
              $sel=$chosen.Range
            }
            $align=@{ left=0; center=1; right=2 }
            $read={ switch($style){ 'bold' { [int]$sel.Font.Bold } 'italic' { [int]$sel.Font.Italic } 'underline' { [int]$sel.Font.Underline } default { [int]$sel.ParagraphFormat.Alignment } } }
            $sent=$true
            switch($style){
              'bold' { $sel.Font.Bold=$(if($on){ -1 } else { 0 }) }
              'italic' { $sel.Font.Italic=$(if($on){ -1 } else { 0 }) }
              'underline' { $sel.Font.Underline=$(if($on){ 1 } else { 0 }) }
              default { $sel.ParagraphFormat.Alignment=$align[$style] }
            }
            $after=& $read
            $held=$(if($align.ContainsKey($style)){ $after -eq $align[$style] } else { ($after -ne 0) -eq $on })
            Answer @{ ok=[bool]$held; effectObserved=$true; error=$(if($held){ '' } else { 'office_format_not_read_back' }); document=[string]$doc.Name; applied=$named; chars=([string]$sel.Text).Trim().Length }
          }
          if($office.Workbooks.Count -lt 1){ Answer @{ ok=$false; effectObserved=$false; error='office_no_document' } }
          $sheet=$office.ActiveSheet
          try {
            $range=$(switch($target){
              'row' { $sheet.Rows.Item([int]$request.row) }
              'column' { $sheet.Columns.Item([string]$request.column) }
              'cells' { $sheet.Range([string]$request.cells) }
              default { $office.Selection }
            })
          } catch { Answer @{ ok=$false; effectObserved=$false; error='office_target_invalid' } }
          if($null -eq $range){ Answer @{ ok=$false; effectObserved=$false; error='office_target_invalid' } }
          $xlAlign=@{ left=-4131; center=-4108; right=-4152 }
          $read={ switch($style){ 'bold' { $range.Font.Bold } 'italic' { $range.Font.Italic } 'underline' { $range.Font.Underline } default { $range.HorizontalAlignment } } }
          # The range the step names is the one the person sees chosen, as a click on its header would leave it.
          $sent=$true
          if($target -ne 'selection'){ [void]$range.Select() }
          switch($style){
            'bold' { $range.Font.Bold=$on }
            'italic' { $range.Font.Italic=$on }
            'underline' { $range.Font.Underline=$(if($on){ 2 } else { -4142 }) }
            default { $range.HorizontalAlignment=$xlAlign[$style] }
          }
          $after=& $read
          $held=$(if($xlAlign.ContainsKey($style)){ $after -eq $xlAlign[$style] } elseif($style -eq 'underline'){ ($after -eq 2) -eq $on } else { $after -eq $on })
          Answer @{ ok=[bool]$held; effectObserved=$true; error=$(if($held){ '' } else { 'office_format_not_read_back' }); document=[string]$office.ActiveWorkbook.Name; sheet=[string]$sheet.Name; applied=[string]$range.Address($false,$false) }
        } catch {
          # Excel editing a cell, or a modal dialog, refuses the call (RPC_E_CALL_REJECTED); past the first change it may
          # have been applied in part, and the receipt says so.
          Answer @{ ok=$false; effectObserved=$sent; error='office_busy' }
        }
        """;
}
