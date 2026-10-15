namespace Baxy.Providers.Windows.External;

/// <summary>
/// The labels written on a window without an accessible tree, each with the colour of its ink (CONTRATO_VISTA_ACCION.md
/// §1.7): what tells, without a model, which item of a row of navigation labels is the one the window is on (live
/// 2026-10-07 v2-s12, v2-c17: on its library a game launcher writes «BIBLIOTECA» blue and its neighbours white; on its
/// store, «TIENDA» blue). The ink is the colour of the glyphs, never of the box: the dominant colour of a label's box
/// (§1.5) is its background.
/// </summary>
internal static class VisibleTextMarks
{
    // Ink: the §1.5 class of the glyphs' cores; InkValue: their brightness (0–255), which tells two colourless inks
    // apart where a class cut would not (the launcher's labels are drawn at V 0.87, on the white/gray cut of §1.5);
    // BackgroundValue: the brightness the label is written on, which tells a label that stands out from a dimmed one.
    internal sealed record Mark(string Text, string Zone, int X, int Y, int W, int H, string Ink, int InkValue, int BackgroundValue);

    // A space wider than this many times the line's height parts two labels («TIENDA   BIBLIOTECA»); the space between
    // the words of one label is narrower than half that height.
    private const double LabelGap = 0.9;

    // A pixel is ink when its brightness is this far from the background's (|ΔV| > 0.25 of the full range).
    private const int InkContrast = 64;

    // Fewer ink pixels than this tell no colour.
    private const int FewestInkPixels = 6;

    private const int MostMarks = 80;

    /// <summary>
    /// The labels of the OCR lines over the 32-bit capture <paramref name="bmp"/>: each line split where its words are
    /// further apart than the line is tall, each label with its ink colour (§1.5 classes) and its box in the capture's
    /// pixels moved by (<paramref name="left"/>, <paramref name="top"/>). The same label read twice (the OCR's two
    /// passes) is kept once.
    /// </summary>
    internal static List<Mark> Read(
        byte[] bmp,
        int left,
        int top,
        IReadOnlyList<WindowsVisibleOcrLocator.LayoutLine> lines)
    {
        var marks = new List<Mark>();
        if (!VisibleControlColors.TryParse(bmp, out int offset, out int width, out int height) || width <= 0 || height == 0)
        {
            return marks;
        }

        var window = new WindowsVisibleControlAdapter.Rect(0, 0, width, Math.Abs(height));
        foreach (WindowsVisibleOcrLocator.LayoutLine line in lines)
        {
            foreach ((string text, double x, double y, double w, double h) in Labels(line))
            {
                int boxX = (int)Math.Floor(x);
                int boxY = (int)Math.Floor(y);
                int boxW = Math.Max(1, (int)Math.Ceiling(x + w) - boxX);
                int boxH = Math.Max(1, (int)Math.Ceiling(y + h) - boxY);
                if (marks.Any(mark => Same(mark, text, boxX + left, boxY + top, boxW, boxH)))
                {
                    continue;
                }

                (string ink, int inkValue, int background) = Ink(bmp, offset, width, height, boxX, boxY, boxW, boxH);
                marks.Add(new Mark(
                    text,
                    WindowsVisibleControlAdapter.Zone(x + w / 2, y + h / 2, window),
                    boxX + left,
                    boxY + top,
                    boxW,
                    boxH,
                    ink,
                    inkValue,
                    background));
                if (marks.Count >= MostMarks)
                {
                    return marks;
                }
            }
        }

        return marks;
    }

    // The labels of one line: its words joined while the space between them is narrower than the line is tall.
    internal static IEnumerable<(string Text, double X, double Y, double W, double H)> Labels(
        WindowsVisibleOcrLocator.LayoutLine line)
    {
        IReadOnlyList<WindowsVisibleOcrLocator.LayoutWord> words = line.Words ?? [];
        if (words.Count == 0)
        {
            yield return (line.Text, line.X, line.Y, line.Width, line.Height);
            yield break;
        }

        var ordered = words.Where(word => word.Text.Trim().Length > 0).OrderBy(word => word.X).ToList();
        int start = 0;
        for (int index = 1; index <= ordered.Count; index++)
        {
            bool ends = index == ordered.Count
                || ordered[index].X - (ordered[index - 1].X + ordered[index - 1].Width) > line.Height * LabelGap;
            if (!ends)
            {
                continue;
            }

            List<WindowsVisibleOcrLocator.LayoutWord> label = ordered.GetRange(start, index - start);
            double x0 = label.Min(word => word.X);
            double y0 = label.Min(word => word.Y);
            double x1 = label.Max(word => word.X + word.Width);
            double y1 = label.Max(word => word.Y + word.Height);
            yield return (string.Join(' ', label.Select(word => word.Text.Trim())), x0, y0, x1 - x0, y1 - y0);
            start = index;
        }
    }

    private static bool Same(Mark mark, string text, int x, int y, int w, int h)
    {
        if (!string.Equals(mark.Text, text, StringComparison.OrdinalIgnoreCase))
        {
            return false;
        }

        int overlapW = Math.Min(mark.X + mark.W, x + w) - Math.Max(mark.X, x);
        int overlapH = Math.Min(mark.Y + mark.H, y + h) - Math.Max(mark.Y, y);
        return overlapW > 0 && overlapH > 0 && overlapW * 2 >= Math.Min(mark.W, w) && overlapH * 2 >= Math.Min(mark.H, h);
    }

    /// <summary>
    /// The colour of the glyphs in a box: the background is the median brightness of a ring around the box; ink is a
    /// pixel at least <see cref="InkContrast"/> away from it, and the glyphs' cores are the tenth of the ink pixels
    /// furthest from the background (never fewer than <see cref="FewestInkPixels"/>), not their antialiased edges. The
    /// class is the cores' majority hue class (§1.5) when most of them are coloured, else white, gray or black by their
    /// median brightness, which is returned as well, with the background's. («», 0, background) when the box holds
    /// too little ink to tell.
    /// </summary>
    internal static (string Ink, int Value, int Background) Ink(
        byte[] bmp, int offset, int width, int height,
        int left, int top, int boxWidth, int boxHeight)
    {
        int rows = Math.Abs(height);
        int x0 = Math.Max(0, left);
        int y0 = Math.Max(0, top);
        int x1 = Math.Min(width, left + boxWidth);
        int y1 = Math.Min(rows, top + boxHeight);
        if (x1 <= x0 || y1 <= y0)
        {
            return (string.Empty, 0, 0);
        }

        bool bottomUp = height > 0;
        int stride = width * 4;
        int Index(int x, int y) => offset + (bottomUp ? rows - 1 - y : y) * stride + x * 4;
        int Brightness(int index) => Math.Max(bmp[index + 2], Math.Max(bmp[index + 1], bmp[index]));

        // The ring two pixels outside the box: what the label is written on.
        var ring = new List<int>();
        int ringX0 = Math.Max(0, x0 - 2);
        int ringY0 = Math.Max(0, y0 - 2);
        int ringX1 = Math.Min(width - 1, x1 + 1);
        int ringY1 = Math.Min(rows - 1, y1 + 1);
        for (int x = ringX0; x <= ringX1; x++)
        {
            ring.Add(Brightness(Index(x, ringY0)));
            ring.Add(Brightness(Index(x, ringY1)));
        }

        for (int y = ringY0; y <= ringY1; y++)
        {
            ring.Add(Brightness(Index(ringX0, y)));
            ring.Add(Brightness(Index(ringX1, y)));
        }

        ring.Sort();
        int background = ring[ring.Count / 2];
        var ink = new List<(int Contrast, int Index)>();
        int stepX = Math.Max(1, (x1 - x0) / 256);
        int stepY = Math.Max(1, (y1 - y0) / 64);
        for (int y = y0; y < y1; y += stepY)
        {
            for (int x = x0; x < x1; x += stepX)
            {
                int index = Index(x, y);
                if (index < 0 || index + 2 >= bmp.Length)
                {
                    continue;
                }

                int contrast = Math.Abs(Brightness(index) - background);
                if (contrast > InkContrast)
                {
                    ink.Add((contrast, index));
                }
            }
        }

        if (ink.Count < FewestInkPixels)
        {
            return (string.Empty, 0, background);
        }

        ink.Sort((a, b) => b.Contrast.CompareTo(a.Contrast));
        List<int> cores = ink.Take(Math.Max(FewestInkPixels, ink.Count / 10)).Select(pixel => pixel.Index).ToList();
        List<int> values = cores.Select(Brightness).OrderBy(value => value).ToList();
        int value = values[values.Count / 2];
        int[] histogram = new int[AchromaticFirst];
        int coloured = 0;
        foreach (int index in cores)
        {
            int named = VisibleControlColors.Classify(bmp[index + 2], bmp[index + 1], bmp[index]);
            if (named < AchromaticFirst)
            {
                histogram[named]++;
                coloured++;
            }
        }

        if (coloured * 2 <= cores.Count)
        {
            // §1.5's cuts on brightness for the colourless classes (V ≥ 0.85 white, V ≤ 0.2 black).
            return (value >= 217 ? "white" : value <= 51 ? "black" : "gray", value, background);
        }

        int best = 0;
        for (int index = 1; index < AchromaticFirst; index++)
        {
            if (histogram[index] > histogram[best])
            {
                best = index;
            }
        }

        return (VisibleControlColors.Names[best], value, background);
    }

    // VisibleControlColors.Names lists the hues first, then white, black and gray.
    private const int AchromaticFirst = 8;
}
