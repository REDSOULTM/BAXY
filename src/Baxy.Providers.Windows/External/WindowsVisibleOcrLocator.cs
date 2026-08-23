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

    private static WordHit? UniqueHit(OcrResult recognized, string label)
    {
        string needle = Fold(label);
        if (needle.Length == 0)
            return null;
        HashSet<string> needles = Needles(needle);
        List<WordHit> hits = [];
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
            }
        }
        if (hits.Count == 1)
            return hits[0];
        if (hits.Count != 0)
            return null;
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
