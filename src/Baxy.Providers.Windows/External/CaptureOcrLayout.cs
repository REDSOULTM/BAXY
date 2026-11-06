using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace Baxy.Providers.Windows.External;

internal sealed record CaptureOcrWord(string Text, double X, double Y, double Width, double Height);

internal sealed record CaptureOcrLine(string Text, IReadOnlyList<CaptureOcrWord> Words);

internal static class CaptureOcrLayout
{
    internal static JsonElement CreateResult(
        string captureId, string language, string text, string imageSha256,
        int imageWidth, int imageHeight, DateTimeOffset recognizedAtUtc,
        double? textAngleDegrees, IReadOnlyList<CaptureOcrLine> lines, IReadOnlyList<string>? recognizerLanguages = null)
    {
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
