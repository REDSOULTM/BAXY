using System.Globalization;
using System.Runtime.InteropServices.WindowsRuntime;
using System.Text;
using System.Text.Json;
using Windows.Globalization;
using Windows.Graphics.Imaging;
using Windows.Media.Ocr;
using Windows.Storage.Streams;

namespace Baxy.Providers.Windows.External;

internal sealed class WindowsVisibleOcrLocator : IVisibleControlLocator
{
    private const int PostReadLooks = 6;

    public string Stage => "ocr";

    public ValueTask<ExternalCapabilityReceipt?> TryClickAsync(
        string operation,
        string label,
        CancellationToken cancellationToken) => TryClickAsync(operation, label, null, cancellationToken);

    public async ValueTask<ExternalCapabilityReceipt?> TryClickAsync(
        string operation,
        string label,
        IPointPress? press,
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
            WordHit? located = await LocateAsync(engine, before.Bmp, label, cancellationToken).ConfigureAwait(false);
            if (located is null)
                return null;
            WordHit hit = located.Value;
            int screenX = before.Left + hit.CenterX;
            int screenY = before.Top + hit.CenterY;
            // The control under the word, pressed through the accessible tree when it has a way (no cursor); the
            // pointer only when the worker says nothing there has one, behind the pointer's guard and inside a burst
            // of the foreground lease (GOAL_COMPUTER_USE_V3 point 0, fix 3): after a pause of the person, with the
            // window read again inside the burst. Moved or resized, nothing is clicked; redrawn, the word is located
            // again on the new capture (a blinking caret redraws too), which is the baseline of the post-read, so a
            // change the person made while waited for is never the click's.
            async ValueTask<(int X, int Y)?> Relocate(VisibleControlSurface.CapturedWindow again, CancellationToken token)
            {
                WordHit? relocated = await LocateAsync(engine, again.Bmp, label, token).ConfigureAwait(false);
                if (relocated is not { } word)
                    return null;
                hit = word;
                return (again.Left + word.CenterX, again.Top + word.CenterY);
            }

            // Review of fable/cu-v3-clic-chromium (finding 3): a press without the mouse (a pattern, or a press posted to
            // a render surface) is proved by the window changing, so its baseline is the window right before the press,
            // not the one the OCR read seconds earlier: whatever the window drew by itself meanwhile (a message coming
            // in, a spinner) is not the press's. What is at the point when it is pressed is the worker's check.
            VisibleControlSurface.CapturedWindow? baseline =
                await VisibleControlSurface.CaptureForegroundAsync(cancellationToken).ConfigureAwait(false);
            LocatedPointPress.Outcome pressed = await LocatedPointPress.PressAsync(
                press, operation, before.Hwnd, screenX, screenY, label, before, Relocate, cancellationToken)
                .ConfigureAwait(false);
            if (pressed.Failure is { } refused)
                return refused;
            if (pressed.Before is { } fresh)
                before = fresh;
            else if (pressed.Burst is null && baseline is { } now && now.Hwnd == before.Hwnd)
                before = now;
            string method = pressed.Method;
            IInputBurst? burst = pressed.Burst;
            VisibleControlSurface.CapturedWindow? after = null;
            bool changed = false;
            bool userActed = false;
            bool restored = true;
            try
            {
                // Looked at until it changes, up to 1.5 s: a web view redraws later than 400 ms (measured on the Epic
                // Games launcher, whose «Biblioteca» click was judged unchanged at 400 ms). r4a M3: a pointer's burst
                // was given back right after the press, so its looks read the window's own drawing behind the person's,
                // the way its baseline was taken; the person's first input ends them.
                for (int look = 0; look < PostReadLooks && !changed && burst is not { UserActed: true }; look++)
                {
                    await Task.Delay(look == 0 ? 400 : 220, cancellationToken).ConfigureAwait(false);
                    after = burst is null
                        ? await VisibleControlSurface.CaptureForegroundAsync(cancellationToken).ConfigureAwait(false)
                        : await VisibleControlSurface.CaptureAsync(before.Hwnd, cancellationToken, selfDrawn: before.SelfDrawn)
                            .ConfigureAwait(false);
                    changed = after is not null && after.Value.Sha256 != before.Sha256;
                }
            }
            finally
            {
                if (burst is not null)
                {
                    userActed = burst.UserActed;
                    restored = burst.Restore();
                }
            }

            bool surfaceObserved = false;
            string observedText = "";
            if (after is not null)
            {
                (surfaceObserved, observedText) = await ObserveLabelAsync(
                    after.Value.Bmp,
                    engine,
                    label,
                    cancellationToken).ConfigureAwait(false);
            }
            // H0101: el diálogo de descarga del lanzador de juegos dice «Instalar» tres veces
            // —el título, el rótulo «INSTALAR EN:» y el botón—. Al pulsar el
            // rótulo no pasó nada, pero la palabra seguía en pantalla y eso se
            // daba por bueno: el turno publicó que el diálogo se había
            // completado cuando seguía abierto y sin descargar nada. Que la
            // etiqueta siga ahí no prueba nada; lo único que prueba un efecto
            // es que la superficie cambie. Se sigue anotando lo observado.
            // A field made the text's destination is proved by the designation itself, not by a redraw; a surface
            // that changed after the person acted proves nothing of the click.
            bool targeted = method == "target" && pressed.Focused;
            bool ok = (changed && !userActed) || targeted;
            JsonElement result = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteNumber("version", 1);
                writer.WriteBoolean("ok", ok);
                writer.WriteBoolean("effectObserved", true);
                writer.WriteString(
                    "error",
                    ok ? "" : userActed ? "input_user_interrupted" : "visible_button_postread_unchanged");
                writer.WriteBoolean("labelStillOnScreen", surfaceObserved);
                writer.WriteString("name", hit.Text);
                writer.WriteString("controlIdentity", "ocr." + hit.CenterX + "." + hit.CenterY);
                writer.WriteBoolean("absentOrDisabled", false);
                writer.WriteBoolean("selected", surfaceObserved);
                writer.WriteBoolean("surfaceChanged", changed);
                writer.WriteString("observedText", observedText.Length > 240 ? observedText[..240] : observedText);
                writer.WriteString("method", method);
                if (targeted)
                {
                    writer.WriteBoolean("targeted", true);
                    writer.WriteBoolean("focused", true);
                    writer.WriteString("kind", pressed.Kind);
                }
                writer.WriteString("cascadeStage", Stage);
                writer.WriteNumber("waitedMs", burst is null ? 0 : pressed.WaitedMs);
                writer.WriteBoolean("restored", restored);
                writer.WriteString("authority", "windows_media_ocr_locate_click_postread");
                writer.WriteEndObject();
            });
            return ok
                ? ExternalJson.Success(operation, result, true)
                : ExternalJson.Failure(
                    operation, userActed ? "input_user_interrupted" : "visible_click_postread_invalid", true);
        }
        catch (Exception exception) when (exception is IOException
            or UnauthorizedAccessException
            or InvalidDataException
            or ArgumentException)
        {
            return null;
        }
    }

    // The one word or run of words that reads the label on a capture, through both OCR passes.
    private static async ValueTask<WordHit?> LocateAsync(
        OcrEngine engine,
        byte[] bmp,
        string label,
        CancellationToken cancellationToken)
    {
        using SoftwareBitmap bitmap = await DecodeAsync(bmp);
        OcrResult recognized = await engine.RecognizeAsync(bitmap);
        cancellationToken.ThrowIfCancellationRequested();
        OcrResult? enhanced = null;
        using (SoftwareBitmap? darker = Darkened(bitmap))
        {
            if (darker is not null)
                enhanced = await engine.RecognizeAsync(darker);
        }

        cancellationToken.ThrowIfCancellationRequested();
        return UniqueHit(recognized, enhanced, label);
    }

    // A capture held in memory, decoded for the OCR engine (the bitmap a file read used to hand it).
    internal static async Task<SoftwareBitmap> DecodeAsync(byte[] bmp)
    {
        using IRandomAccessStream stream = new MemoryStream(bmp, writable: false).AsRandomAccessStream();
        BitmapDecoder decoder = await BitmapDecoder.CreateAsync(stream);
        return await decoder.GetSoftwareBitmapAsync(BitmapPixelFormat.Bgra8, BitmapAlphaMode.Ignore);
    }

    private static async ValueTask<(bool observed, string text)> ObserveLabelAsync(
        byte[] bmp,
        OcrEngine engine,
        string label,
        CancellationToken cancellationToken)
    {
        using SoftwareBitmap bitmap = await DecodeAsync(bmp);
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
        if (Fold(recognized.Text ?? "").Contains(needle, StringComparison.Ordinal))
            return true;
        foreach (OcrLine line in recognized.Lines)
        {
            if (Fold(line.Text) == needle)
                return true;
            foreach (OcrWord word in line.Words)
            {
                if (Fold(word.Text) == needle)
                    return true;
            }
        }
        return false;
    }

    private static global::Windows.Foundation.Rect SpanBox(IReadOnlyList<OcrWord> words, int start, int span)
    {
        global::Windows.Foundation.Rect first = words[start].BoundingRect;
        if (span == 1)
            return first;
        global::Windows.Foundation.Rect last = words[start + span - 1].BoundingRect;
        double top = Math.Min(first.Y, last.Y);
        double bottom = Math.Max(first.Y + first.Height, last.Y + last.Height);
        return new global::Windows.Foundation.Rect(first.X, top, Math.Max(1, last.X + last.Width - first.X), bottom - top);
    }

    /// <summary>One OCR line with its box in capture pixels (contract §1.2, text by zone) and its words' boxes, which
    /// tell apart the labels of a row read as one line («BIBLIOTECA COMUNIDAD», contract §1.7).</summary>
    internal sealed record LayoutLine(
        string Text, double X, double Y, double Width, double Height, IReadOnlyList<LayoutWord>? Words = null);

    /// <summary>One OCR word with its box in capture pixels.</summary>
    internal sealed record LayoutWord(string Text, double X, double Y, double Width, double Height);

    // Lo que está escrito en la ventana capturada, línea a línea y con su
    // posición. Hace falta porque hay superficies que no exponen árbol de
    // accesibilidad: la interfaz del lanzador de juegos devuelve un solo nodo
    // (la ventana heredada de CEF), sin un hijo. Ahí lo único que se puede
    // leer es lo que se ve.
    // Encargo WA-LEER: con «placed» cada línea vale por su sitio (las de un chat, semantic.chat_lines): un texto que se
    // repite en otro sitio es otra línea —trece burbujas «prueba BAXY imp», la hora y la fecha de la última burbuja que
    // la lista de chats repite— y sólo se descarta la segunda lectura del mismo texto en el mismo sitio; una línea larga
    // de un mensaje se guarda entera. Medido en redpc (chat «Abuela» abierto, 1938×1098): por texto quedaban 45 de 66
    // líneas, 12 de las 13 burbujas fuera.
    internal static async ValueTask<IReadOnlyList<LayoutLine>?> ReadLayoutAsync(
        byte[] capture,
        int limit,
        CancellationToken cancellationToken,
        bool placed = false)
    {
        try
        {
            OcrEngine? engine = OcrEngine.TryCreateFromUserProfileLanguages();
            if (engine is null)
                return null;
            using SoftwareBitmap bitmap = await DecodeAsync(capture);
            OcrResult recognized = await engine.RecognizeAsync(bitmap);
            cancellationToken.ThrowIfCancellationRequested();
            OcrResult? enhanced = null;
            using (SoftwareBitmap? darker = Darkened(bitmap))
            {
                if (darker is not null)
                    enhanced = await engine.RecognizeAsync(darker);
            }

            cancellationToken.ThrowIfCancellationRequested();
            var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            var lines = new List<LayoutLine>();
            // La segunda pasada nombra lo que la primera no alcanza a leer, como
            // el botón «Instalar» del lanzador de juegos: blanco sobre azul saturado.
            OcrResult[] readPasses = enhanced is null ? [recognized] : [recognized, enhanced];
            foreach (OcrResult pass in readPasses)
            {
                foreach (OcrLine line in pass.Lines)
                {
                    string text = line.Text.Trim();
                    if (text.Length == 0 || !placed && (text.Length > 80 || !seen.Add(text)))
                        continue;
                    global::Windows.Foundation.Rect box = default;
                    bool started = false;
                    var words = new List<LayoutWord>();
                    foreach (OcrWord word in line.Words)
                    {
                        global::Windows.Foundation.Rect wordBox = word.BoundingRect;
                        words.Add(new LayoutWord(word.Text, wordBox.X, wordBox.Y, wordBox.Width, wordBox.Height));
                        if (!started)
                        {
                            box = wordBox;
                            started = true;
                        }
                        else
                        {
                            box.Union(wordBox);
                        }
                    }

                    var read = new LayoutLine(text, box.X, box.Y, box.Width, box.Height, words);
                    if (placed && lines.Any(kept => ReadAgain(kept, read)))
                        continue;
                    lines.Add(read);
                    if (lines.Count >= limit)
                        break;
                }

                if (lines.Count >= limit)
                    break;
            }

            // Orden de lectura: arriba→abajo, izquierda→derecha, con las dos
            // pasadas fundidas.
            lines.Sort((left, right) =>
            {
                int byRow = (left.Y + left.Height / 2).CompareTo(right.Y + right.Height / 2);
                return Math.Abs(left.Y - right.Y) <= Math.Min(left.Height, right.Height) / 2
                    ? left.X.CompareTo(right.X)
                    : byRow;
            });
            return lines;
        }
        catch (Exception exception) when (exception is IOException or InvalidOperationException
            or UnauthorizedAccessException)
        {
            return null;
        }
    }

    /// <summary>Encargo WA-LEER: the same text read again where it was read (the darkened pass over the first).</summary>
    internal static bool ReadAgain(LayoutLine kept, LayoutLine line) =>
        string.Equals(kept.Text, line.Text, StringComparison.OrdinalIgnoreCase)
        && kept.X < line.X + line.Width && line.X < kept.X + kept.Width
        && kept.Y < line.Y + line.Height && line.Y < kept.Y + kept.Height;

    private static WordHit? UniqueHit(
        OcrResult recognized,
        OcrResult? enhanced,
        string label)
    {
        string needle = Fold(label);
        if (needle.Length == 0)
            return null;
        OcrResult[] passes = enhanced is null ? [recognized] : [recognized, enhanced];
        List<global::Windows.Foundation.Rect> words = [];
        foreach (OcrResult pass in passes)
        {
            foreach (OcrLine everyLine in pass.Lines)
            {
                foreach (OcrWord everyWord in everyLine.Words)
                    words.Add(everyWord.BoundingRect);
            }
        }

        int span = needle.Split(' ', StringSplitOptions.RemoveEmptyEntries).Length;
        List<WordHit> hits = [];
        List<double> heights = [];
        List<bool> continues = [];
        foreach (OcrResult pass in passes)
        {
            foreach (OcrLine line in pass.Lines)
            {
                // A label of several words («Página principal») is a run of consecutive words of one line; its box
                // spans them. A one-word label is one word, as before.
                IReadOnlyList<OcrWord> lineWords = line.Words;
                for (int start = 0; start + span <= lineWords.Count; start++)
                {
                    if (string.Join(' ', lineWords.Skip(start).Take(span).Select(each => Fold(each.Text))) != needle)
                        continue;
                    OcrWord word = lineWords[start];
                    global::Windows.Foundation.Rect box = SpanBox(lineWords, start, span);
                    var hit = new WordHit(
                        word.Text,
                        (int)(box.X + box.Width / 2),
                        (int)(box.Y + box.Height / 2));
                    // La misma palabra leída en las dos pasadas es una sola
                    // aparición, no dos: se cuenta una vez.
                    if (hits.Any(seen => Math.Abs(seen.CenterX - hit.CenterX) <= 4
                        && Math.Abs(seen.CenterY - hit.CenterY) <= 4))
                    {
                        continue;
                    }

                    hits.Add(hit);
                    heights.Add(box.Height);
                    continues.Add(ContinuesToTheRight(box, words));
                }
            }
        }
        // H0101: en el diálogo de descarga del lanzador de juegos la palabra «Instalar» sale
        // tres veces —el título, el rótulo «INSTALAR EN:» y el botón—, y el
        // rótulo, escrito en versalitas pequeñas, ganaba la regla del cuerpo
        // menor. Un rótulo así no es una etiqueta de control: sigue con más
        // texto pegado a su derecha, en su misma fila. La de un control termina
        // ahí. Cuando alguna termina, las que siguen se descartan.
        if (continues.Contains(false) && continues.Contains(true))
        {
            List<WordHit> kept = [];
            List<double> keptHeights = [];
            for (int index = 0; index < hits.Count; index++)
            {
                if (continues[index])
                    continue;
                kept.Add(hits[index]);
                keptHeights.Add(heights[index]);
            }
            hits = kept;
            heights = keptHeights;
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
        // Auditoría P3: a line that only holds the label among other words is not its control; nothing is pressed.
        return null;
    }

    // H0101: el boton «Instalar» del dialogo del lanzador de juegos es texto blanco sobre azul
    // saturado. El OCR de Windows, afinado para tinta oscura sobre fondo claro,
    // no lo lee: en la captura sólo encuentra el título y el rótulo «INSTALAR
    // EN:». Medido, una copia en gris con gamma 2,5 —que oscurece los medios
    // tonos y separa la letra del fondo— sí lo encuentra. De modo que se mira
    // dos veces: la imagen tal cual y esa copia. Nada se envía a ninguna parte.
    private static readonly byte[] DarkenedRamp = BuildRamp();

    private static byte[] BuildRamp()
    {
        var ramp = new byte[256];
        for (int level = 0; level < 256; level++)
            ramp[level] = (byte)Math.Round(255 * Math.Pow(level / 255.0, 2.5));
        return ramp;
    }

    private static SoftwareBitmap? Darkened(SoftwareBitmap source)
    {
        try
        {
            int width = source.PixelWidth;
            int height = source.PixelHeight;
            var pixels = new byte[4 * width * height];
            source.CopyToBuffer(pixels.AsBuffer());
            for (int index = 0; index + 3 < pixels.Length; index += 4)
            {
                int luminance = (int)(0.114 * pixels[index]
                    + 0.587 * pixels[index + 1]
                    + 0.299 * pixels[index + 2]);
                byte value = DarkenedRamp[luminance < 0 ? 0 : luminance > 255 ? 255 : luminance];
                pixels[index] = value;
                pixels[index + 1] = value;
                pixels[index + 2] = value;
            }

            var darker = new SoftwareBitmap(
                BitmapPixelFormat.Bgra8, width, height, BitmapAlphaMode.Ignore);
            darker.CopyFromBuffer(pixels.AsBuffer());
            return darker;
        }
        catch (Exception exception) when (exception is ArgumentException
            or InvalidOperationException or OutOfMemoryException)
        {
            return null;
        }
    }

    // Otra palabra en la misma fila, pegada a la derecha: menos de un cuerpo y
    // medio de separación y con los centros verticales a menos de media altura.
    // Así se distingue «INSTALAR EN:» —que sigue— del botón «Instalar» y del
    // título, que terminan ahí; «Cancelar», a 215 px, no cuenta como pegada.
    private static bool ContinuesToTheRight(
        global::Windows.Foundation.Rect box,
        IReadOnlyList<global::Windows.Foundation.Rect> words)
    {
        double centre = box.Y + box.Height / 2;
        double right = box.X + box.Width;
        foreach (global::Windows.Foundation.Rect other in words)
        {
            if (other.X <= box.X && other.Y <= box.Y)
                continue;
            if (Math.Abs(other.Y + other.Height / 2 - centre) > box.Height / 2)
                continue;
            if (other.X >= right && other.X - right <= box.Height * 1.5)
                return true;
        }
        return false;
    }

    internal static string Fold(string value)
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
