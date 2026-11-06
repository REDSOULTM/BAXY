using System.Text.Json;
using Baxy.Providers.Windows.Clipboard;

namespace Baxy.Providers.Windows.External;

/// <summary>What a paste into a new Office document did: whether it ran (the application was already running), whether it
/// read the pasted text back in that document, and its name.</summary>
public sealed record OfficePasteResult(bool Verified, bool EffectObserved, string? ErrorCode, string? Document, int Characters);

/// <summary>
/// BAXY Renew cu (C18 variante): «pega lo que tengo copiado en word» with Word already running. Launching Word again
/// hands the new document to the running instance, inside its own process, and the opening did not recognize it (no
/// window of its own nor an Edit to read), so nothing was pasted. With Word or Excel already running, the new document
/// is made through the application's object model (Documents.Add, Workbooks.Add) and the clipboard goes into that
/// document's own content (never the selection of another one), read back there. A closed application, or any other,
/// is not handled here (null): the ordinary opening and paste follow.
/// </summary>
public static class OfficeNewDocumentPaste
{
    /// <summary>The Office application an app.open name means, or null («Word», «Microsoft Word», «Excel»…).</summary>
    public static string? OfficeOf(string? application) =>
        application?.Trim().ToLowerInvariant() switch
        {
            "word" or "microsoft word" or "microsoft office word" => "word",
            "excel" or "microsoft excel" or "microsoft office excel" => "excel",
            _ => null,
        };

    public static ValueTask<OfficePasteResult?> TryAsync(string? application, CancellationToken cancellationToken) =>
        TryAsync(application, new ExternalProcessRunner(), new WindowsClipboardProvider(), cancellationToken);

    internal static async ValueTask<OfficePasteResult?> TryAsync(
        string? application, IExternalProcessRunner runner, IClipboardProvider clipboard, CancellationToken cancellationToken)
    {
        if (OfficeOf(application) is not { } office)
            return null;
        string state = await ClipboardStateAsync(clipboard, cancellationToken).ConfigureAwait(false);
        ExternalProcessResult process;
        try
        {
            process = await runner.RunPowerShellAsync(Script, [office, state], TimeSpan.FromSeconds(30), cancellationToken)
                .ConfigureAwait(false);
        }
        catch (Exception exception) when (exception is IOException or TimeoutException or InvalidOperationException
            or System.ComponentModel.Win32Exception)
        {
            return null;
        }

        string? line = process.Output.Split(['\r', '\n'], StringSplitOptions.RemoveEmptyEntries).LastOrDefault();
        if (line is null)
            return new OfficePasteResult(false, true, "office_paste_no_receipt", null, 0);
        using JsonDocument answer = JsonDocument.Parse(line);
        JsonElement root = answer.RootElement;
        // Not running: the ordinary way (the opening launches it and makes the new document).
        if (root.TryGetProperty("running", out JsonElement running) && running.ValueKind == JsonValueKind.False)
            return null;
        bool ok = root.TryGetProperty("ok", out JsonElement held) && held.ValueKind == JsonValueKind.True;
        bool effect = root.TryGetProperty("effectObserved", out JsonElement observed) && observed.ValueKind == JsonValueKind.True;
        string? error = root.TryGetProperty("error", out JsonElement said) && said.GetString() is { Length: > 0 } code ? code : null;
        string? document = root.TryGetProperty("document", out JsonElement named) ? named.GetString() : null;
        int characters = root.TryGetProperty("characters", out JsonElement count) && count.ValueKind == JsonValueKind.Number
            ? count.GetInt32() : 0;
        return new OfficePasteResult(ok, effect, ok ? null : error ?? "paste_not_read_back", document, characters);
    }

    // A8: the script's Get-Clipboard waited with no limit of its own on an owner that does not answer, the 30 s of the
    // whole script, and any failure of it read as empty. The read here is bounded and says which. The script still answers
    // with it only when the application is running: a closed one goes the ordinary way, whatever the clipboard holds.
    private static async ValueTask<string> ClipboardStateAsync(IClipboardProvider clipboard, CancellationToken cancellationToken)
    {
        try
        {
            ClipboardTextSnapshot text = await clipboard.ReadTextAsync(1, cancellationToken).ConfigureAwait(false);
            return text.Text.Length > 0 ? "text" : "clipboard_empty";
        }
        catch (ClipboardProviderException exception)
        {
            return exception.Code == "clipboard_has_no_text" ? "clipboard_empty" : exception.Code;
        }
    }

    internal const string Script = """
        $ErrorActionPreference='Stop'
        $app=[string]$args[0]
        $held=[string]$args[1]
        function Answer($h){ [pscustomobject]$h | ConvertTo-Json -Compress; exit 0 }
        # Only an application already running is used here; a closed one goes the ordinary way.
        try { $office=[Runtime.InteropServices.Marshal]::GetActiveObject($(if($app -eq 'word'){ 'Word.Application' } else { 'Excel.Application' })) }
        catch { Answer @{ ok=$false; running=$false; effectObserved=$false; error='office_app_not_open' } }
        if($held -ne 'text'){ Answer @{ ok=$false; running=$true; effectObserved=$false; error=$held } }
        $sent=$false
        try {
          if($app -eq 'word'){
            $doc=$office.Documents.Add(); $sent=$true
            # Into the new document's own content, never the selection of another one.
            $doc.Content.Paste()
            $doc.Activate(); $office.Activate()
            $got=([string]$doc.Content.Text).Trim().Length
            Answer @{ ok=($got -gt 0); running=$true; effectObserved=$true; error=$(if($got -gt 0){''}else{'paste_not_read_back'}); document=[string]$doc.Name; characters=$got }
          }
          $book=$office.Workbooks.Add(); $sent=$true
          $sheet=$book.Worksheets.Item(1)
          [void]$sheet.Range('A1').Select(); $sheet.Paste()
          $book.Activate(); $office.Visible=$true
          $first=[string]$sheet.Range('A1').Value2
          Answer @{ ok=($first.Length -gt 0); running=$true; effectObserved=$true; error=$(if($first.Length -gt 0){''}else{'paste_not_read_back'}); document=[string]$book.Name; characters=$first.Length }
        } catch {
          Answer @{ ok=$false; running=$true; effectObserved=$sent; error='office_busy' }
        }
        """;
}
