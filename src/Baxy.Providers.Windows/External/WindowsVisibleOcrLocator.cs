using System.Globalization;
using System.Text;
using System.Text.Json;
using Windows.Globalization;
using Windows.Graphics.Imaging;
using Windows.Media.Ocr;
using Windows.Storage;
using Windows.Storage.Streams;

namespace Baxy.Providers.Windows.External;

internal sealed class WindowsVisibleOcrLocator : IVisibleControlLocator
{
    public string Stage => "ocr";

    public async ValueTask<ExternalCapabilityReceipt?> TryClickAsync(
        string operation,
        string label,
        CancellationToken cancellationToken)
    {
        VisibleControlSurface.CapturedWindow? captured =
            await VisibleControlSurface.CaptureForegroundAsync(cancellationToken)
                .ConfigureAwait(false);
        if (captured is null)
            return null;
        VisibleControlSurface.CapturedWindow before = captured.Value;
        try
        {
            OcrEngine? engine = OcrEngine.TryCreateFromUserProfileLanguages();
            if (engine is null)
                return null;
            StorageFile file = await StorageFile.GetFileFromPathAsync(before.Path);
            using IRandomAccessStream stream = await file.OpenReadAsync();
            BitmapDecoder decoder = await BitmapDecoder.CreateAsync(stream);
            using SoftwareBitmap bitmap = await decoder.GetSoftwareBitmapAsync(
                BitmapPixelFormat.Bgra8,
                BitmapAlphaMode.Ignore);
            OcrResult recognized = await engine.RecognizeAsync(bitmap);
            cancellationToken.ThrowIfCancellationRequested();
            WordHit? located = UniqueHit(recognized, label);
            if (located is null)
                return null;
            WordHit hit = located.Value;
            VisibleControlSurface.Click(before.Left + hit.CenterX, before.Top + hit.CenterY);
            await Task.Delay(400, cancellationToken).ConfigureAwait(false);
            VisibleControlSurface.CapturedWindow? after =
                await VisibleControlSurface.CaptureForegroundAsync(cancellationToken)
                    .ConfigureAwait(false);
            bool changed = after is not null && after.Value.Sha256 != before.Sha256;
            bool surfaceObserved = false;
            string observedText = "";
            if (after is not null)
            {
                (surfaceObserved, observedText) = await ObserveLabelAsync(
                    after.Value.Path,
                    engine,
                    label,
                    cancellationToken).ConfigureAwait(false);
                VisibleControlSurface.Delete(after.Value.Path);
            }
            bool ok = surfaceObserved || changed;
            JsonElement result = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteNumber("version", 1);
                writer.WriteBoolean("ok", ok);
                writer.WriteBoolean("effectObserved", true);
                writer.WriteString("error", ok ? "" : "visible_button_postread_unchanged");
                writer.WriteString("name", hit.Text);
                writer.WriteString("controlIdentity", "ocr." + hit.CenterX + "." + hit.CenterY);
                writer.WriteBoolean("absentOrDisabled", false);
                writer.WriteBoolean("selected", surfaceObserved);
                writer.WriteBoolean("surfaceChanged", changed);
                writer.WriteString("observedText", observedText.Length > 240 ? observedText[..240] : observedText);
                writer.WriteString("cascadeStage", Stage);
                writer.WriteString("authority", "windows_media_ocr_locate_click_postread");
                writer.WriteEndObject();
            });
            return ok
                ? ExternalJson.Success(operation, result, true)
                : ExternalJson.Failure(operation, "visible_click_postread_invalid", true);
        }
        catch (Exception exception) when (exception is IOException
            or UnauthorizedAccessException
            or InvalidDataException
            or ArgumentException)
        {
            return null;
        }
        finally
        {
            VisibleControlSurface.Delete(before.Path);
        }
    }

    private static async ValueTask<(bool observed, string text)> ObserveLabelAsync(
        string path,
        OcrEngine engine,
        string label,
        CancellationToken cancellationToken)
    {
        StorageFile file = await StorageFile.GetFileFromPathAsync(path);
        using IRandomAccessStream stream = await file.OpenReadAsync();
        BitmapDecoder decoder = await BitmapDecoder.CreateAsync(stream);
        using SoftwareBitmap bitmap = await decoder.GetSoftwareBitmapAsync(
            BitmapPixelFormat.Bgra8,
            BitmapAlphaMode.Ignore);
        OcrResult recognized = await engine.RecognizeAsync(bitmap);
        cancellationToken.ThrowIfCancellationRequested();
        string text = recognized.Text ?? "";
        return (LabelPresent(recognized, label), text);
    }

    private static bool LabelPresent(OcrResult recognized, string label)
    {
        string needle = Fold(label);
        if (needle.Length == 0)
            return false;
        HashSet<string> needles = Needles(needle);
        if (needles.Any(item => Fold(recognized.Text ?? "").Contains(item, StringComparison.Ordinal)))
            return true;
        foreach (OcrLine line in recognized.Lines)
        {
            if (needles.Contains(Fold(line.Text)))
                return true;
            foreach (OcrWord word in line.Words)
            {
                if (needles.Contains(Fold(word.Text)))
                    return true;
            }
        }
        return false;
    }

    private static HashSet<string> Needles(string needle)
    {
        HashSet<string> needles = new(StringComparer.Ordinal) { needle };
        if (needle is "biblioteca")
            needles.Add("library");
        if (needle is "library")
            needles.Add("biblioteca");
        if (needle is "configuracion")
            needles.Add("settings");
        if (needle is "settings")
            needles.Add("configuracion");
        return needles;
    }

    // Lo que está escrito en la ventana de delante, línea a línea. Hace falta
    // porque hay superficies que no exponen árbol de accesibilidad: la interfaz
    // de Steam devuelve un solo nodo, «Chrome Legacy Window», sin un hijo. Ahí
    // lo único que se puede leer es lo que se ve.
    internal static async ValueTask<string[]?> TryReadLinesAsync(
        int limit,
        CancellationToken cancellationToken)
    {
        VisibleControlSurface.CapturedWindow? captured =
            await VisibleControlSurface.CaptureForegroundAsync(cancellationToken)
                .ConfigureAwait(false);
        if (captured is null)
            return null;
        VisibleControlSurface.CapturedWindow window = captured.Value;
        try
        {
            OcrEngine? engine = OcrEngine.TryCreateFromUserProfileLanguages();
            if (engine is null)
                return null;
            StorageFile file = await StorageFile.GetFileFromPathAsync(window.Path);
            using IRandomAccessStream stream = await file.OpenReadAsync();
            BitmapDecoder decoder = await BitmapDecoder.CreateAsync(stream);
            using SoftwareBitmap bitmap = await decoder.GetSoftwareBitmapAsync(
                BitmapPixelFormat.Bgra8,
                BitmapAlphaMode.Ignore);
            OcrResult recognized = await engine.RecognizeAsync(bitmap);
            cancellationToken.ThrowIfCancellationRequested();
            var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            var lines = new List<string>();
            foreach (OcrLine line in recognized.Lines)
            {
                string text = line.Text.Trim();
                if (text.Length == 0 || text.Length > 80 || !seen.Add(text))
                    continue;
                lines.Add(text);
                if (lines.Count >= limit)
                    break;
            }
            return lines.ToArray();
        }
        catch (Exception exception) when (exception is IOException or InvalidOperationException
            or UnauthorizedAccessException)
        {
            return null;
        }
        finally
        {
            VisibleControlSurface.Delete(window.Path);
        }
    }

    private static WordHit? UniqueHit(OcrResult recognized, string label)
    {
        string needle = Fold(label);
        if (needle.Length == 0)
            return null;
        HashSet<string> needles = Needles(needle);
        List<WordHit> hits = [];
        List<double> heights = [];
        foreach (OcrLine line in recognized.Lines)
        {
            foreach (OcrWord word in line.Words)
            {
                if (!needles.Contains(Fold(word.Text)))
                    continue;
                global::Windows.Foundation.Rect box = word.BoundingRect;
                hits.Add(new WordHit(
                    word.Text,
                    (int)(box.X + box.Width / 2),
                    (int)(box.Y + box.Height / 2)));
                heights.Add(box.Height);
            }
        }
        if (hits.Count == 1)
            return hits[0];
        if (hits.Count != 0)
        {
            // UI1767: the same word printed twice is a control and the page
            // heading that names the open section («Biblioteca» in the Epic
            // Games Launcher's navigation and as the library page title). The
            // clearly smaller print is the control; equal prints stay ambiguous.
            // UI1771: the launcher's heading is only a fifth larger than its
            // navigation entry (17 px against 14 px), so any print smaller by
            // more than OCR jitter (5 %) is the control.
            int smallest = 0;
            for (int index = 1; index < heights.Count; index++)
            {
                if (heights[index] < heights[smallest])
                    smallest = index;
            }
            double next = double.MaxValue;
            for (int index = 0; index < heights.Count; index++)
            {
                if (index != smallest && heights[index] < next)
                    next = heights[index];
            }
            return heights[smallest] <= next * 0.95 ? hits[smallest] : null;
        }
        foreach (OcrLine line in recognized.Lines)
        {
            if (!needles.Any(item => Fold(line.Text).Contains(item, StringComparison.Ordinal)))
                continue;
            global::Windows.Foundation.Rect box = default;
            bool started = false;
            foreach (OcrWord word in line.Words)
            {
                if (!started)
                {
                    box = word.BoundingRect;
                    started = true;
                }
                else
                {
                    box.Union(word.BoundingRect);
                }
            }
            if (!started)
                continue;
            hits.Add(new WordHit(
                line.Text,
                (int)(box.X + box.Width / 2),
                (int)(box.Y + box.Height / 2)));
        }
        return hits.Count == 1 ? hits[0] : null;
    }

    private static string Fold(string value)
    {
        string form = value.Normalize(NormalizationForm.FormD).ToLowerInvariant();
        var builder = new StringBuilder(form.Length);
        foreach (char character in form)
        {
            if (CharUnicodeInfo.GetUnicodeCategory(character) != UnicodeCategory.NonSpacingMark)
                builder.Append(character);
        }
        return string.Join(' ', builder.ToString().Split(
            (char[]?)null, StringSplitOptions.RemoveEmptyEntries));
    }

    private readonly record struct WordHit(string Text, int CenterX, int CenterY);
}
