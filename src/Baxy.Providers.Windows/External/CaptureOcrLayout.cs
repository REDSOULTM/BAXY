using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace Baxy.Providers.Windows.External;

internal sealed record CaptureOcrWord(string Text, double X, double Y, double Width, double Height);

internal sealed record CaptureOcrLine(string Text, IReadOnlyList<CaptureOcrWord> Words);

/// <summary>PAN1: the text a window gives through UI Automation for one of its controls, in the capture's pixels.</summary>
internal sealed record AccessibleTextBox(string Text, double X, double Y, double Width, double Height);

/// <summary>PAN1: the OCR lines left after <see cref="CaptureOcrLayout.Sift"/>, the exact texts of the boxes it used, and
/// how many OCR words it left out.</summary>
internal sealed record ScreenTextReading(IReadOnlyList<CaptureOcrLine> Lines, IReadOnlyList<string> WindowText, int Withheld);

internal static class CaptureOcrLayout
{
    /// <summary>
    /// PAN1 (VIVO5-VIVO11: «Mira mi pantalla» read BAXY's own window as «88 capacidades», the grid icon before
    /// «Capacidades 191»): Windows.Media.Ocr gives no confidence (OcrWord: Text and BoundingRect only), and OCR1 measured
    /// that no threshold separates such a word. Where a window gives a control's text through UI Automation, that text is
    /// exact: an OCR word whose centre falls inside the control's box and that its text does not hold is left out. A box
    /// sifts an OCR line only when two thirds of that line's characters inside it are words of its text: that shows the
    /// capture still shows that control there (a picture under a link with another name, or a window that changed, keeps
    /// its OCR). What lies under no box (an image, a video, an application that gives no text) stays as the OCR read it.
    /// </summary>
    internal static ScreenTextReading Sift(IReadOnlyList<CaptureOcrLine> lines, IReadOnlyList<AccessibleTextBox> boxes)
    {
        var inside = new Dictionary<CaptureOcrWord, int>(ReferenceEqualityComparer.Instance);
        foreach (CaptureOcrWord word in lines.SelectMany(static line => line.Words))
        {
            double x = word.X + word.Width / 2, y = word.Y + word.Height / 2;
            int smallest = -1;
            for (int i = 0; i < boxes.Count; i++)
            {
                AccessibleTextBox box = boxes[i];
                if (x >= box.X && x <= box.X + box.Width && y >= box.Y && y <= box.Y + box.Height
                    && (smallest < 0 || box.Width * box.Height < boxes[smallest].Width * boxes[smallest].Height))
                    smallest = i;
            }
            if (smallest >= 0)
                inside[word] = smallest;
        }
        var tokens = boxes.Select(static box => Tokens(box.Text)).ToArray();
        // Each OCR line inside each box on its own, by characters: an icon beside its label («® Ajustes») is one or two
        // characters of the line, while a picture's text inside a link named otherwise («SE ALQUILA» under «Los locales …
        // se duplican», «6 AM AT THE POINT» under «… at Tidewater Point») shares some of the link's words and stays. Two
        // thirds: PAN1 held-out lots 1-3, 101 of 108 false words left out and no true one (half lost 5 true words of two
        // pictures in lot 3).
        var sifting = new HashSet<(int Line, int Box)>();
        for (int at = 0; at < lines.Count; at++)
        {
            foreach (IGrouping<int, CaptureOcrWord> part in lines[at].Words.Where(inside.ContainsKey).GroupBy(word => inside[word]))
            {
                int all = part.Sum(static word => word.Text.Length);
                int held = part.Where(word => Held(word.Text, tokens[part.Key])).Sum(static word => word.Text.Length);
                if (held > 0 && held * 3 >= all * 2)
                    sifting.Add((at, part.Key));
            }
        }
        var used = new SortedSet<int>(sifting.Select(static part => part.Box));
        // The OCR may put an icon on a line of its own, apart from its label (VIVO11: «memoria 88» across the panel,
        // «Capacidades 191» below): alone in a box another line confirmed, a word of one or two characters that is not the
        // box's text (what one glyph reads as) is not given either.
        for (int at = 0; at < lines.Count; at++)
        {
            foreach (IGrouping<int, CaptureOcrWord> part in lines[at].Words.Where(inside.ContainsKey).GroupBy(word => inside[word]))
            {
                if (used.Contains(part.Key) && part.Count() == 1 && part.First().Text.Trim().Length <= 2)
                    sifting.Add((at, part.Key));
            }
        }
        int withheld = 0;
        var kept = new List<CaptureOcrLine>(lines.Count);
        for (int at = 0; at < lines.Count; at++)
        {
            CaptureOcrLine line = lines[at];
            var words = line.Words.Where(word => !inside.TryGetValue(word, out int box) || !sifting.Contains((at, box))
                || Held(word.Text, tokens[box])).ToArray();
            withheld += line.Words.Count - words.Length;
            if (words.Length == line.Words.Count)
                kept.Add(line);
            else if (words.Length > 0)
                kept.Add(new CaptureOcrLine(string.Join(' ', words.Select(static word => word.Text)), words));
        }
        return new ScreenTextReading(kept, [.. used.Select(i => boxes[i].Text).Distinct(StringComparer.Ordinal)], withheld);
    }

    // A word is held by a text when, lowered and without the marks around it, it is one of the text's words. A word of
    // only marks («•», «→») is held when the text has that mark.
    private static bool Held(string word, HashSet<string> tokens) =>
        Fold(word) is { Length: > 0 } folded ? tokens.Contains(folded) : tokens.Contains(word.Trim());

    private static HashSet<string> Tokens(string text)
    {
        var tokens = new HashSet<string>(StringComparer.Ordinal);
        foreach (string part in text.Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries))
        {
            tokens.Add(part);
            if (Fold(part) is { Length: > 0 } folded)
                tokens.Add(folded);
        }
        return tokens;
    }

    private static string Fold(string word)
    {
        int start = 0, end = word.Length;
        while (start < end && !char.IsLetterOrDigit(word[start]))
            start++;
        while (end > start && !char.IsLetterOrDigit(word[end - 1]))
            end--;
        return word[start..end].ToLowerInvariant();
    }

    internal static JsonElement CreateResult(
        string captureId, string language, string text, string imageSha256,
        int imageWidth, int imageHeight, DateTimeOffset recognizedAtUtc,
        double? textAngleDegrees, IReadOnlyList<CaptureOcrLine> lines, IReadOnlyList<string>? recognizerLanguages = null,
        ScreenTextReading? sifted = null)
    {
        // PAN1: only the text changes. The window's texts written beside it («windowText», with «text is OCR and may have
        // errors») made the model answer from them and stop reading a picture's text (held-out lot 4: 18 of 36 → 9 of 36
        // answers read it; with the text alone, 19 of 36, and the false words told fell as much).
        if (sifted is { Withheld: > 0 })
        {
            lines = sifted.Lines;
            text = string.Join(' ', lines.Select(static line => line.Text));
        }
        if (imageWidth <= 0 || imageHeight <= 0
            || imageSha256.Length != 64 || !imageSha256.All(char.IsAsciiHexDigit)
            || (textAngleDegrees is double angle && !double.IsFinite(angle)))
        {
            throw new InvalidDataException("OCR image or angle is invalid.");
        }
        foreach (CaptureOcrWord word in lines.SelectMany(line => line.Words))
        {
            if (!double.IsFinite(word.X) || !double.IsFinite(word.Y)
                || !double.IsFinite(word.Width) || !double.IsFinite(word.Height)
                || word.X < 0 || word.Y < 0 || word.Width <= 0 || word.Height <= 0
                || word.X > imageWidth || word.Y > imageHeight
                || word.Width > imageWidth - word.X || word.Height > imageHeight - word.Y)
            {
                throw new InvalidDataException("OCR word bounds are outside the image.");
            }
        }

        return ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("captureId", captureId);
            writer.WriteString("language", language);
            writer.WriteString("text", text);
            writer.WriteString("textSha256",
                Convert.ToHexStringLower(SHA256.HashData(Encoding.UTF8.GetBytes(text))));
            writer.WriteNumber("lineCount", lines.Count);
            writer.WriteString("authority", "windows_media_ocr");
            // Encargo 119: what this read can and cannot say. The engine has no confidence: a foreign alphabet comes back as
            // nonsense, and faint text as nothing (130 on 160 grey at 16 px, on a capture that plainly shows it).
            if (recognizerLanguages is not null)
            {
                writer.WriteStartArray("recognizerLanguages");
                foreach (string recognizer in recognizerLanguages)
                {
                    writer.WriteStringValue(recognizer);
                }
                writer.WriteEndArray();
                writer.WriteString("limits", "this PC's OCR reads only those languages: text in another alphabet comes out as "
                    + "letters that make no sense, so say it could not be read, and a language's OCR pack is installed from "
                    + "Windows Settings");
                if (lines.Count == 0)
                {
                    writer.WriteString("nothingRead", "no text was recognized: it may have none, or text too faint, too small "
                        + "or turned; say that, not that it has no text");
                }
            }
            writer.WriteString("imageSha256", imageSha256);
            writer.WriteNumber("imageWidth", imageWidth);
            writer.WriteNumber("imageHeight", imageHeight);
            writer.WriteString("recognizedAtUtc", recognizedAtUtc.ToUniversalTime());
            writer.WriteStartObject("layout");
            writer.WriteBoolean("available", true);
            writer.WriteString("coordinateSystem", "image_pixels");
            // Raw Windows OCR boxes: TextAngle is retained, never silently flattened to zero.
            // Consumers must account for the engine's angle before overlaying these boxes.
            writer.WriteString("boundingRectFrame", "windows_media_ocr_text_angle");
            writer.WriteBoolean("rotationApplied", false);
            if (textAngleDegrees is double value)
            {
                writer.WriteNumber("textAngleDegrees", value);
            }
            else
            {
                writer.WriteNull("textAngleDegrees");
            }
            writer.WriteStartArray("lines");
            foreach (CaptureOcrLine line in lines)
            {
                writer.WriteStartObject();
                writer.WriteString("text", line.Text);
                writer.WriteStartArray("words");
                foreach (CaptureOcrWord word in line.Words)
                {
                    writer.WriteStartObject();
                    writer.WriteString("text", word.Text);
                    writer.WriteStartObject("boundingRect");
                    writer.WriteNumber("x", word.X);
                    writer.WriteNumber("y", word.Y);
                    writer.WriteNumber("width", word.Width);
                    writer.WriteNumber("height", word.Height);
                    writer.WriteEndObject();
                    writer.WriteEndObject();
                }
                writer.WriteEndArray();
                writer.WriteEndObject();
            }
            writer.WriteEndArray();
            writer.WriteEndObject();
            writer.WriteEndObject();
        });
    }

    internal static void WriteUnavailable(Utf8JsonWriter writer)
    {
        writer.WriteStartObject("layout");
        writer.WriteBoolean("available", false);
        writer.WriteString("reason", "backend_returns_flat_text");
        writer.WriteEndObject();
    }
}
