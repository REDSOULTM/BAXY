using System.Buffers.Binary;
using System.Globalization;
using System.Runtime.InteropServices;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace Baxy.Providers.Windows.External;

/// <summary>A rectangle in pixels (of the screen or of a capture).</summary>
internal readonly record struct PixelBox(int X, int Y, int W, int H)
{
    internal int Right => X + W;

    internal int Bottom => Y + H;

    internal int CenterX => X + W / 2;

    internal int CenterY => Y + H / 2;

    internal bool Intersects(PixelBox other) =>
        X < other.Right && other.X < Right && Y < other.Bottom && other.Y < Bottom;

    internal bool Contains(int x, int y) => x >= X && x < Right && y >= Y && y < Bottom;

    internal PixelBox Inflate(int by) => new(X - by, Y - by, W + 2 * by, H + 2 * by);

    internal PixelBox Offset(int dx, int dy) => new(X + dx, Y + dy, W, H);

    internal PixelBox Clip(int width, int height)
    {
        int left = Math.Clamp(X, 0, width);
        int top = Math.Clamp(Y, 0, height);
        int right = Math.Clamp(Right, 0, width);
        int bottom = Math.Clamp(Bottom, 0, height);
        return new PixelBox(left, top, Math.Max(0, right - left), Math.Max(0, bottom - top));
    }
}

/// <summary>A 32-bit capture decoded top-down (BGRA), and the pure readings of the tooltip stage on it.</summary>
internal sealed class TooltipImage
{
    private TooltipImage(int width, int height, byte[] bgra)
    {
        Width = width;
        Height = height;
        Bgra = bgra;
    }

    internal int Width { get; }

    internal int Height { get; }

    internal byte[] Bgra { get; }

    /// <summary>The 32-bit BMP the captures are kept as (bottom-up or top-down); null for anything else.</summary>
    internal static TooltipImage? FromBmp(byte[] bmp)
    {
        if (bmp is null || bmp.Length < 54 || bmp[0] != (byte)'B' || bmp[1] != (byte)'M')
            return null;
        int offset = BinaryPrimitives.ReadInt32LittleEndian(bmp.AsSpan(10));
        int width = BinaryPrimitives.ReadInt32LittleEndian(bmp.AsSpan(18));
        int height = BinaryPrimitives.ReadInt32LittleEndian(bmp.AsSpan(22));
        int bits = BinaryPrimitives.ReadInt16LittleEndian(bmp.AsSpan(28));
        bool topDown = height < 0;
        height = Math.Abs(height);
        if (bits != 32 || width < 1 || height < 1 || offset < 54
            || (long)offset + (long)width * height * 4 > bmp.Length)
            return null;
        byte[] pixels = new byte[width * height * 4];
        int stride = width * 4;
        for (int row = 0; row < height; row++)
        {
            int source = offset + (topDown ? row : height - 1 - row) * stride;
            Buffer.BlockCopy(bmp, source, pixels, row * stride, stride);
        }

        return new TooltipImage(width, height, pixels);
    }

    /// <summary>A part of the image as a 32-bit bottom-up BMP (what the OCR reads).</summary>
    internal byte[] CropBmp(PixelBox box)
    {
        PixelBox part = box.Clip(Width, Height);
        if (part.W < 1 || part.H < 1)
            return [];
        const int header = 14 + 40;
        int stride = part.W * 4;
        byte[] result = new byte[header + stride * part.H];
        result[0] = (byte)'B';
        result[1] = (byte)'M';
        BinaryPrimitives.WriteInt32LittleEndian(result.AsSpan(2), result.Length);
        BinaryPrimitives.WriteInt32LittleEndian(result.AsSpan(10), header);
        BinaryPrimitives.WriteInt32LittleEndian(result.AsSpan(14), 40);
        BinaryPrimitives.WriteInt32LittleEndian(result.AsSpan(18), part.W);
        BinaryPrimitives.WriteInt32LittleEndian(result.AsSpan(22), part.H);
        BinaryPrimitives.WriteInt16LittleEndian(result.AsSpan(26), 1);
        BinaryPrimitives.WriteInt16LittleEndian(result.AsSpan(28), 32);
        BinaryPrimitives.WriteInt32LittleEndian(result.AsSpan(34), stride * part.H);
        for (int row = 0; row < part.H; row++)
        {
            int source = ((part.Y + row) * Width + part.X) * 4;
            int target = header + (part.H - 1 - row) * stride;
            Buffer.BlockCopy(Bgra, source, result, target, stride);
        }

        return result;
    }

    private int Gray(int x, int y)
    {
        int at = (y * Width + x) * 4;
        return (Bgra[at] * 29 + Bgra[at + 1] * 150 + Bgra[at + 2] * 77) >> 8;
    }

    /// <summary>
    /// Icon candidates on a window without a tree (CONTRATO_VISTA_ACCION.md §3.2, §8.2), without a model: the edges of
    /// the image outside the written lines (<paramref name="text"/>, capture pixels), joined by a pixel, as connected
    /// shapes of 12–64 px with a ratio of 0.5–2 that do not touch the window's border. Those nearest an edge of the
    /// window come first (icons gather in bars), then in reading order; at most <paramref name="limit"/>.
    /// </summary>
    internal IReadOnlyList<PixelBox> IconCandidates(IReadOnlyList<PixelBox> text, int limit)
    {
        int width = Width;
        int height = Height;
        var edge = new bool[width * height];
        for (int y = 1; y < height; y++)
        {
            for (int x = 1; x < width; x++)
            {
                int here = Gray(x, y);
                int gradient = Math.Abs(here - Gray(x - 1, y)) + Math.Abs(here - Gray(x, y - 1));
                edge[y * width + x] = gradient >= 48;
            }
        }

        foreach (PixelBox line in text)
        {
            PixelBox masked = line.Inflate(3).Clip(width, height);
            for (int y = masked.Y; y < masked.Bottom; y++)
                Array.Clear(edge, y * width + masked.X, masked.W);
        }

        // Joined by one pixel: the strokes of one glyph-like icon become one shape.
        var joined = new bool[width * height];
        for (int y = 0; y < height; y++)
        {
            for (int x = 0; x < width; x++)
            {
                if (!edge[y * width + x])
                    continue;
                for (int dy = -1; dy <= 1; dy++)
                {
                    int row = y + dy;
                    if (row < 0 || row >= height)
                        continue;
                    for (int dx = -1; dx <= 1; dx++)
                    {
                        int column = x + dx;
                        if (column >= 0 && column < width)
                            joined[row * width + column] = true;
                    }
                }
            }
        }

        var found = new List<PixelBox>();
        var seen = new bool[width * height];
        var stack = new Stack<int>();
        for (int start = 0; start < joined.Length; start++)
        {
            if (!joined[start] || seen[start])
                continue;
            int left = width, top = height, right = -1, bottom = -1, count = 0;
            bool tooBig = false;
            seen[start] = true;
            stack.Push(start);
            while (stack.Count > 0)
            {
                int at = stack.Pop();
                int x = at % width;
                int y = at / width;
                count++;
                left = Math.Min(left, x);
                right = Math.Max(right, x);
                top = Math.Min(top, y);
                bottom = Math.Max(bottom, y);
                if (right - left > 96 || bottom - top > 96)
                    tooBig = true;
                if (x > 0) Visit(at - 1);
                if (x < width - 1) Visit(at + 1);
                if (y > 0) Visit(at - width);
                if (y < height - 1) Visit(at + width);
            }

            if (tooBig)
                continue;
            int w = right - left + 1;
            int h = bottom - top + 1;
            if (w < 12 || h < 12 || w > 64 || h > 64)
                continue;
            double ratio = (double)w / h;
            if (ratio < 0.5 || ratio > 2)
                continue;
            if (left <= 2 || top <= 2 || right >= width - 3 || bottom >= height - 3)
                continue;
            // A filled block or a photograph is not an icon: an icon is strokes on a plain ground.
            double filled = (double)count / (w * h);
            if (filled > 0.92)
                continue;
            found.Add(new PixelBox(left, top, w, h));
        }

        // A shape inside another one (the glyph inside its button's outline) is the same control: hovered once.
        var kept = new List<PixelBox>();
        foreach (PixelBox box in found
            .OrderBy(box => Math.Min(Math.Min(box.Y, Height - box.Bottom), Math.Min(box.X, Width - box.Right)) / 48)
            .ThenBy(box => box.Y / 16)
            .ThenBy(box => box.X))
        {
            if (kept.Count >= limit)
                break;
            if (kept.Any(other => other.Contains(box.CenterX, box.CenterY) || box.Contains(other.CenterX, other.CenterY)))
                continue;
            kept.Add(box);
        }

        return kept;

        void Visit(int next)
        {
            if (joined[next] && !seen[next])
            {
                seen[next] = true;
                stack.Push(next);
            }
        }
    }

    /// <summary>
    /// The print of a control's place (CONTRATO_VISTA_ACCION.md §8.2): an average hash of its pixels on an 8×8 grid and
    /// their mean grey, as «hash.mean». A remembered place is pressed only while its print still matches
    /// (<see cref="SamePrint"/>): another site, channel or page of the same window shows something else there. Null for
    /// a place outside the image or a flat one (nothing drawn there tells it from any other flat place).
    /// </summary>
    internal string? Print(PixelBox box)
    {
        PixelBox part = box.Clip(Width, Height);
        if (part.W < 8 || part.H < 8)
            return null;
        var cells = new double[64];
        for (int row = 0; row < 8; row++)
        {
            for (int column = 0; column < 8; column++)
            {
                int left = part.X + column * part.W / 8;
                int right = part.X + (column + 1) * part.W / 8;
                int top = part.Y + row * part.H / 8;
                int bottom = part.Y + (row + 1) * part.H / 8;
                long sum = 0;
                int count = 0;
                for (int y = top; y < bottom; y++)
                {
                    for (int x = left; x < right; x++)
                    {
                        sum += Gray(x, y);
                        count++;
                    }
                }

                cells[row * 8 + column] = count == 0 ? 0 : (double)sum / count;
            }
        }

        double mean = cells.Average();
        if (cells.Max() - cells.Min() < 16)
            return null;
        ulong hash = 0;
        for (int index = 0; index < 64; index++)
        {
            if (cells[index] >= mean)
                hash |= 1UL << index;
        }

        return string.Create(CultureInfo.InvariantCulture, $"{hash:x16}.{(int)Math.Round(mean)}");
    }

    /// <summary>Two prints of the same control: at most 6 of the 64 cells differ and the mean grey moved by 24 or less.</summary>
    internal static bool SamePrint(string? learned, string? now)
    {
        if (learned is null || now is null)
            return false;
        string[] first = learned.Split('.');
        string[] second = now.Split('.');
        if (first.Length != 2 || second.Length != 2
            || !ulong.TryParse(first[0], NumberStyles.HexNumber, CultureInfo.InvariantCulture, out ulong one)
            || !ulong.TryParse(second[0], NumberStyles.HexNumber, CultureInfo.InvariantCulture, out ulong two)
            || !int.TryParse(first[1], NumberStyles.Integer, CultureInfo.InvariantCulture, out int meanOne)
            || !int.TryParse(second[1], NumberStyles.Integer, CultureInfo.InvariantCulture, out int meanTwo))
            return false;
        return System.Numerics.BitOperations.PopCount(one ^ two) <= 6 && Math.Abs(meanOne - meanTwo) <= 24;
    }

    /// <summary>
    /// Whether the window changed outside <paramref name="skip"/> (in its pixels): at least 20 pixels moved by more than
    /// 30 levels, or its size changed. A press on an icon is proved by this, never by the hash of the whole capture: the
    /// cursor left on the icon brings back its tooltip and its highlight, which a click that did nothing also shows.
    /// </summary>
    internal static bool ChangedOutside(TooltipImage before, TooltipImage after, IReadOnlyList<PixelBox> skip)
    {
        if (before.Width != after.Width || before.Height != after.Height)
            return true;
        int count = 0;
        for (int y = 0; y < before.Height; y++)
        {
            for (int x = 0; x < before.Width; x++)
            {
                int at = (y * before.Width + x) * 4;
                int difference = Math.Abs(before.Bgra[at] - after.Bgra[at])
                    + Math.Abs(before.Bgra[at + 1] - after.Bgra[at + 1])
                    + Math.Abs(before.Bgra[at + 2] - after.Bgra[at + 2]);
                if (difference <= 30 || skip.Any(box => box.Contains(x, y)))
                    continue;
                if (++count >= 20)
                    return true;
            }
        }

        return false;
    }

    /// <summary>
    /// What changed between two images of the same window inside <paramref name="region"/>, leaving out
    /// <paramref name="hovered"/> (the control's own hover highlight): the box of the changed pixels, or null when
    /// nothing did, or when so much changed that it is not a tooltip (the page itself changed).
    /// </summary>
    internal static PixelBox? ChangedBox(TooltipImage before, TooltipImage after, PixelBox region, PixelBox hovered)
    {
        if (before.Width != after.Width || before.Height != after.Height)
            return null;
        PixelBox inside = region.Clip(before.Width, before.Height);
        PixelBox skip = hovered.Inflate(4);
        int left = int.MaxValue, top = int.MaxValue, right = -1, bottom = -1, count = 0;
        for (int y = inside.Y; y < inside.Bottom; y++)
        {
            for (int x = inside.X; x < inside.Right; x++)
            {
                if (skip.Contains(x, y))
                    continue;
                int at = (y * before.Width + x) * 4;
                int difference = Math.Abs(before.Bgra[at] - after.Bgra[at])
                    + Math.Abs(before.Bgra[at + 1] - after.Bgra[at + 1])
                    + Math.Abs(before.Bgra[at + 2] - after.Bgra[at + 2]);
                if (difference <= 30)
                    continue;
                count++;
                left = Math.Min(left, x);
                top = Math.Min(top, y);
                right = Math.Max(right, x);
                bottom = Math.Max(bottom, y);
            }
        }

        if (count < 20)
            return null;
        var box = new PixelBox(left, top, right - left + 1, bottom - top + 1);
        return box.W > 480 || box.H > 200 || box.H < 8 ? null : box;
    }

    /// <summary>
    /// The text a tooltip added: the lines read after the hover that were not there before (folded), joined, at most
    /// 80 characters; empty when none is new. A tooltip opens above or below its control, never beside it: a line in
    /// the hovered control's own row (<paramref name="hoveredRow"/>, in the same pixels as the lines) is the row's
    /// own text lit by the hover (measured live: a name beside the hovered icon read again with other OCR errors).
    /// </summary>
    internal static string NewText(
        IEnumerable<(string Text, PixelBox Box)> after, IEnumerable<string> before, PixelBox? hoveredRow = null)
    {
        var old = new HashSet<string>(before.Select(WindowsVisibleOcrLocator.Fold), StringComparer.Ordinal);
        string text = string.Join(' ', after
            .Where(line => hoveredRow is not { } row || line.Box.Bottom <= row.Y || line.Box.Y >= row.Bottom)
            .Select(line => line.Text.Trim())
            .Where(line => line.Length > 1 && !old.Contains(WindowsVisibleOcrLocator.Fold(line))));
        return text.Length > 80 ? text[..80].TrimEnd() : text;
    }

    /// <summary>The same for lines without boxes (no row to leave out).</summary>
    internal static string NewText(IEnumerable<string> after, IEnumerable<string> before) =>
        NewText(after.Select(line => (line, default(PixelBox))), before);
}

/// <summary>
/// The labels read from tooltips, by window signature (process, class, size in steps) and the control's place in it
/// rounded to 8 px, kept in the shell's data root, so a later mission on that window
/// presses the icon without hovering again. A later hover that reads another label replaces it; a press on a learned
/// place that changed nothing forgets it; an entry older than <see cref="Lifetime"/> is not used.
/// </summary>
internal sealed class TooltipLabelCache
{
    internal static readonly TimeSpan Lifetime = TimeSpan.FromDays(30);
    private const int MaximumWindows = 128;
    private const int MaximumPlaces = 64;
    private readonly string? _path;
    private readonly Func<DateTime> _now;
    private readonly object _gate = new();
    private JsonObject? _document;

    internal TooltipLabelCache(string? path, Func<DateTime>? now = null)
    {
        _path = path;
        _now = now ?? (() => DateTime.UtcNow);
    }

    internal static TooltipLabelCache CreateDefault()
    {
        string? configured = Environment.GetEnvironmentVariable("BAXY_DATA_DIR");
        string root = string.IsNullOrWhiteSpace(configured)
            ? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "BAXY", "1")
            : configured;
        return new TooltipLabelCache(Path.Combine(root, "computer-use", "tooltip-labels.v1.json"));
    }

    internal static string Signature(string processName, string className, int width, int height) =>
        string.Join('|', processName.Trim().ToLowerInvariant(), className.Trim(),
            (width / 160).ToString(CultureInfo.InvariantCulture), (height / 160).ToString(CultureInfo.InvariantCulture));

    /// <summary>The place of a control relative to its window, rounded to 8 px.</summary>
    internal static string Place(PixelBox relative) =>
        string.Join('.', Round(relative.X), Round(relative.Y), Round(relative.W), Round(relative.H));

    internal static PixelBox? FromPlace(string place)
    {
        string[] parts = place.Split('.');
        if (parts.Length != 4)
            return null;
        int[] values = new int[4];
        for (int index = 0; index < 4; index++)
        {
            if (!int.TryParse(parts[index], NumberStyles.Integer, CultureInfo.InvariantCulture, out values[index]))
                return null;
        }

        return new PixelBox(values[0], values[1], values[2], values[3]);
    }

    private static string Round(int value) =>
        ((int)Math.Round(value / 8.0, MidpointRounding.AwayFromZero) * 8).ToString(CultureInfo.InvariantCulture);

    /// <summary>
    /// A remembered label: the control's place, the label and its source, the print of the place when it was read
    /// (<see cref="TooltipImage.Print"/>) and where its tooltip showed (a place relative to the window; empty when unknown).
    /// </summary>
    internal readonly record struct Entry(string Place, string Label, string Source, string? Print, string Tip);

    /// <summary>The fresh labels known on a window.</summary>
    internal IReadOnlyList<Entry> For(string signature)
    {
        lock (_gate)
        {
            var result = new List<Entry>();
            if (Document()[signature] is not JsonObject places)
                return result;
            DateTime now = _now();
            foreach ((string place, JsonNode? node) in places)
            {
                if (node is not JsonObject entry
                    || (string?)entry["label"] is not { Length: > 0 } label
                    || !DateTime.TryParse((string?)entry["seenUtc"], CultureInfo.InvariantCulture,
                        DateTimeStyles.AdjustToUniversal | DateTimeStyles.AssumeUniversal, out DateTime seen)
                    || now - seen > Lifetime)
                    continue;
                result.Add(new Entry(place, label, (string?)entry["source"] ?? string.Empty, (string?)entry["print"],
                    (string?)entry["tip"] ?? string.Empty));
            }

            return result;
        }
    }

    internal void Put(string signature, string place, string label, string source, string? print = null, PixelBox? tip = null)
    {
        lock (_gate)
        {
            JsonObject document = Document();
            if (document[signature] is not JsonObject places)
            {
                while (document.Count >= MaximumWindows)
                    document.Remove(document.First().Key);
                places = new JsonObject();
                document[signature] = places;
            }

            places.Remove(place);
            while (places.Count >= MaximumPlaces)
                places.Remove(places.First().Key);
            places[place] = new JsonObject
            {
                ["label"] = label,
                ["source"] = source,
                ["seenUtc"] = _now().ToString("o", CultureInfo.InvariantCulture),
            };
            if (print is not null)
                places[place]!["print"] = print;
            if (tip is { } shown)
                places[place]!["tip"] = string.Create(CultureInfo.InvariantCulture, $"{shown.X}.{shown.Y}.{shown.W}.{shown.H}");
            Save();
        }
    }

    internal void Forget(string signature, string place)
    {
        lock (_gate)
        {
            if (Document()[signature] is JsonObject places && places.Remove(place))
                Save();
        }
    }

    private JsonObject Document()
    {
        if (_document is not null)
            return _document;
        _document = new JsonObject();
        if (_path is null || !File.Exists(_path))
            return _document;
        try
        {
            if (JsonNode.Parse(File.ReadAllText(_path))?["windows"] is JsonObject windows)
                _document = windows.DeepClone().AsObject();
        }
        catch (Exception exception) when (exception is IOException or JsonException or UnauthorizedAccessException)
        {
            _document = new JsonObject();
        }

        return _document;
    }

    private void Save()
    {
        if (_path is null)
            return;
        try
        {
            Directory.CreateDirectory(Path.GetDirectoryName(_path)!);
            var file = new JsonObject { ["version"] = 1, ["windows"] = Document().DeepClone() };
            string temporary = _path + ".tmp";
            File.WriteAllText(temporary, file.ToJsonString(), new System.Text.UTF8Encoding(false));
            File.Move(temporary, _path, overwrite: true);
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            // A label not kept is read again by the next hover; nothing else depends on the file.
        }
    }
}

/// <summary>The desktop the tooltip stage reads and moves the cursor on (fakes in tests).</summary>
internal interface ITooltipDesktop
{
    /// <summary>The window the calls are bound to (the mission's), alive; 0 when none is.</summary>
    nint BoundWindow();

    /// <summary>The window's process (the hosted app's for a shared frame).</summary>
    (int ProcessId, string ProcessName) Process(nint window);

    /// <summary>The processes whose tooltips may belong to the window: its own and its child windows'.</summary>
    IReadOnlyList<int> DrawingProcesses(nint window);

    string ClassName(nint window);

    ValueTask<VisibleControlSurface.CapturedWindow?> CaptureAsync(nint window, bool? selfDrawn, CancellationToken cancellationToken);

    /// <summary>A burst of the foreground lease on the window, after the person's pause.</summary>
    ValueTask<IInputBurst> AcquireAsync(nint window, CancellationToken cancellationToken);

    /// <summary>The window is in front and nothing else covers it at that screen point.</summary>
    bool HoldsPoint(nint window, int screenX, int screenY);

    /// <summary>The cursor rests on the point (moved there with a last one-pixel step), only while the burst may act.</summary>
    bool Hover(IInputBurst burst, int screenX, int screenY);

    /// <summary>The OCR lines of a 32-bit BMP, with their boxes in its pixels.</summary>
    ValueTask<IReadOnlyList<(string Text, PixelBox Box)>> ReadLinesAsync(byte[] bmp, CancellationToken cancellationToken);

    long NowMs { get; }

    ValueTask DelayAsync(int milliseconds, CancellationToken cancellationToken);
}

/// <summary>
/// The names of buttons that are only an icon, without a vision model (GOAL_COMPUTER_USE_V3 point 3,
/// CONTRATO_VISTA_ACCION.md §8.2). When a click's label is not in the view (UIA and OCR found nothing), on the window
/// bound to the mission only: the actionable controls that stay without a name after the fallback of §8.1 or, on a
/// window without a tree, icon-shaped regions outside the written lines, are hovered one by one, each inside a burst
/// of the foreground lease after a pause of the person; the tooltip is read by UI Automation (a ToolTip of the
/// window's process or inside it) and, only when none shows there, from what changed on the capture around the
/// cursor, by OCR. The cursor and the window in front are given back after every candidate; the label is kept by
/// window signature (<see cref="TooltipLabelCache"/>), so the next time the icon is pressed without hovering. The
/// control the label names is pressed like a point OCR found (through the tree, else the pointer inside a burst).
/// At most <see cref="MaxCandidates"/> candidates and <see cref="BudgetMs"/> per click; never a click while hovering.
/// </summary>
internal sealed class WindowsVisibleTooltipLocator : IVisibleControlLocator
{
    internal const int MaxCandidates = 6;
    internal const int TooltipWaitMs = 700;
    internal const int PollMs = 100;
    internal const int BudgetMs = 9000;
    private const int PostReadLooks = 6;
    private const int MinimumPollMs = 300;
    private const int SettleLooks = 6;
    private const int SettleMs = 120;
    private static readonly TimeSpan SettleTipsBudget = TimeSpan.FromMilliseconds(800);
    private const string BudgetSpent = "tooltip_budget_spent";
    private static readonly TimeSpan WorkerBudget = TimeSpan.FromSeconds(4);
    // Listing the tree is a whole walk (and a cold worker starts first): the view's own budget.
    private static readonly TimeSpan ListBudget = TimeSpan.FromSeconds(12);

    private readonly IUiaWorker _worker;
    private readonly ITooltipDesktop _desktop;
    private readonly TooltipLabelCache _cache;

    internal WindowsVisibleTooltipLocator(IUiaWorker worker, ITooltipDesktop? desktop = null, TooltipLabelCache? cache = null)
    {
        _worker = worker ?? throw new ArgumentNullException(nameof(worker));
        _desktop = desktop ?? new WindowsTooltipDesktop();
        _cache = cache ?? TooltipLabelCache.CreateDefault();
    }

    public string Stage => "tooltip";

    /// <summary>The caps of one click (a measurement raises them to read a whole window).</summary>
    internal int CandidateCap { get; init; } = MaxCandidates;

    internal int Budget { get; init; } = BudgetMs;

    /// <summary>What happened to each candidate (a measurement prints it); nothing in the product.</summary>
    internal Action<string>? Trace { get; init; }

    /// <summary>A candidate: its box on the screen, and whether it is a control of the tree or a drawn region.</summary>
    internal readonly record struct Candidate(PixelBox Screen, string Kind, string ControlId = "");

    /// <summary>
    /// What hovering one candidate gave: a label, its source and where its tooltip showed (screen pixels; without a
    /// label, why none), or a stop (the person acted or did not pause).
    /// </summary>
    internal readonly record struct Hovered(string? Label, string Source, string? Stop, PixelBox? Tip = null);

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
        if (string.IsNullOrWhiteSpace(label))
            return null;
        Learned? learned = await LearnAsync(label, cancellationToken).ConfigureAwait(false);
        if (learned is not { } found)
            return null;
        ExternalCapabilityReceipt? receipt = await PressAsync(operation, label, found, press, cancellationToken)
            .ConfigureAwait(false);
        if (!found.FromCache || receipt?.ErrorCode != NamedOther)
            return receipt;
        // A remembered place where the tree shows a control with another name was not pressed: it is forgotten and
        // the icons are hovered again, once.
        _cache.Forget(found.Signature, found.Place);
        if (await LearnAsync(label, cancellationToken).ConfigureAwait(false) is not { } again)
            return null;
        return await PressAsync(operation, label, again, press, cancellationToken).ConfigureAwait(false);
    }

    internal const string NamedOther = "visible_point_named_other";

    /// <summary>A label read (or remembered) on the bound window, with its place and the capture it is relative to.</summary>
    internal readonly record struct Learned(
        nint Window,
        string Signature,
        string Place,
        PixelBox Screen,
        string Label,
        string Source,
        bool FromCache,
        VisibleControlSurface.CapturedWindow Capture,
        string ControlId = "",
        PixelBox? Tip = null);

    /// <summary>
    /// The control <paramref name="label"/> names among the remembered labels of the bound window or, failing that,
    /// among the candidates hovered now (each read label is kept, the one named or not); null when none names it, or
    /// with no bound window, a protected window, a person who does not pause or one who acts.
    /// </summary>
    internal async ValueTask<Learned?> LearnAsync(string label, CancellationToken cancellationToken, List<Learned>? read = null)
    {
        nint window = _desktop.BoundWindow();
        if (window == 0)
            return null;
        (int processId, string processName) = _desktop.Process(window);
        if (processId <= 0 || VisibleControlSurface.ProtectedFrom(processName, null))
            return null;
        VisibleControlSurface.CapturedWindow? captured = await _desktop.CaptureAsync(window, null, cancellationToken)
            .ConfigureAwait(false);
        if (captured is not { } capture)
            return null;
        string signature = TooltipLabelCache.Signature(processName, _desktop.ClassName(window), capture.Width, capture.Height);
        var known = new HashSet<string>(StringComparer.Ordinal);
        TooltipImage? image = TooltipImage.FromBmp(capture.Bmp);
        foreach (TooltipLabelCache.Entry entry in _cache.For(signature))
        {
            if (TooltipLabelCache.FromPlace(entry.Place) is not { } relative)
                continue;
            // The signature is wide (every site or channel of a window shares it): a remembered place holds only while
            // the control drawn there is the one whose tooltip was read. Another one there forgets it and is hovered.
            if (!TooltipImage.SamePrint(entry.Print, image?.Print(relative)))
            {
                if (WindowsVisibleControlAdapter.SameLabel(label, entry.Label))
                    _cache.Forget(signature, entry.Place);
                continue;
            }

            known.Add(entry.Place);
            if (WindowsVisibleControlAdapter.SameLabel(label, entry.Label))
            {
                return new Learned(window, signature, entry.Place, relative.Offset(capture.Left, capture.Top), entry.Label,
                    entry.Source, true, capture, Tip: TooltipLabelCache.FromPlace(entry.Tip));
            }
        }

        // The whole stage, the listing included, fits in the click's budget: the listing gets at most all of it.
        long stopAt = _desktop.NowMs + Budget;
        IReadOnlyList<Candidate> candidates = await CandidatesAsync(
            window, capture, cancellationToken, TimeSpan.FromMilliseconds(Math.Min(ListBudget.TotalMilliseconds, Budget)))
            .ConfigureAwait(false);
        IReadOnlyList<int> owners = _desktop.DrawingProcesses(window);
        if (owners.Count == 0)
            owners = [processId];
        int hovered = 0;
        foreach (Candidate candidate in candidates)
        {
            if (hovered >= CandidateCap || _desktop.NowMs >= stopAt)
                break;
            string place = TooltipLabelCache.Place(candidate.Screen.Offset(-capture.Left, -capture.Top));
            if (!known.Add(place))
                continue;
            hovered++;
            Hovered outcome = await HoverAsync(window, owners, candidate, stopAt, cancellationToken).ConfigureAwait(false);
            Trace?.Invoke(string.Create(CultureInfo.InvariantCulture,
                $"{candidate.Kind} {candidate.Screen} -> {outcome.Label ?? "-"} ({outcome.Source}{outcome.Stop})"));
            if (outcome.Stop is not null)
                return null;
            if (outcome.Label is not { Length: > 0 } name)
                continue;
            PixelBox? tip = outcome.Tip?.Offset(-capture.Left, -capture.Top);
            _cache.Put(signature, place, name, outcome.Source,
                TooltipLabelCache.FromPlace(place) is { } at ? image?.Print(at) : null, tip);
            var learned = new Learned(
                window, signature, place, candidate.Screen, name, outcome.Source, false, capture, candidate.ControlId, tip);
            read?.Add(learned);
            if (read is null && WindowsVisibleControlAdapter.SameLabel(label, name))
                return learned;
        }

        return null;
    }

    /// <summary>The unnamed actionable controls of the tree; on a window without one, the icon-shaped regions.</summary>
    internal async ValueTask<IReadOnlyList<Candidate>> CandidatesAsync(
        nint window,
        VisibleControlSurface.CapturedWindow capture,
        CancellationToken cancellationToken,
        TimeSpan? listBudget = null)
    {
        var candidates = new List<Candidate>();
        int named = 0;
        bool listed = false;
        using (JsonDocument? answer = await _worker.SendAsync(
            new JsonObject { ["cmd"] = "unnamed", ["hwnd"] = (long)window, ["limit"] = 24 }.ToJsonString(),
            listBudget ?? ListBudget,
            cancellationToken).ConfigureAwait(false))
        {
            if (answer?.RootElement is { ValueKind: JsonValueKind.Object } root
                && root.TryGetProperty("ok", out JsonElement ok) && ok.ValueKind == JsonValueKind.True)
            {
                listed = true;
                if (root.TryGetProperty("named", out JsonElement count) && count.TryGetInt32(out int value))
                    named = value;
                if (root.TryGetProperty("controls", out JsonElement controls) && controls.ValueKind == JsonValueKind.Array)
                {
                    foreach (JsonElement control in controls.EnumerateArray())
                    {
                        if (ReadRect(control) is { } box)
                        {
                            string id = control.TryGetProperty("id", out JsonElement identity)
                                && identity.ValueKind == JsonValueKind.String ? identity.GetString() ?? "" : "";
                            candidates.Add(new Candidate(box, "control", id));
                        }
                    }
                }
            }
        }

        // Drawn regions only on a window whose tree was read and is empty: a worker that did not answer says nothing
        // about the tree, and a window with a tree names its icons there or not at all.
        Trace?.Invoke(string.Create(CultureInfo.InvariantCulture,
            $"tree listed={listed} named={named} unnamed={candidates.Count}"));
        if (!listed || candidates.Count > 0 || named > 1)
            return candidates;
        if (TooltipImage.FromBmp(capture.Bmp) is not { } image)
            return candidates;
        IReadOnlyList<(string Text, PixelBox Box)> lines = await _desktop.ReadLinesAsync(capture.Bmp, cancellationToken)
            .ConfigureAwait(false);
        foreach (PixelBox region in image.IconCandidates(lines.Select(line => line.Box).ToList(), CandidateCap * 2))
            candidates.Add(new Candidate(region.Offset(capture.Left, capture.Top), "region"));
        return candidates;
    }

    /// <summary>
    /// One candidate hovered inside a burst of the lease: the tooltip by UIA, else by OCR of what changed. Everything
    /// ends by <paramref name="stopAtMs"/> (the click's budget, on the real clock): the wait for the person's pause and
    /// every poll of the worker are cut there, a worker too slow to answer a poll is not asked again, and the burst is
    /// given back right after the last capture, before the OCR, which needs neither the cursor nor the front.
    /// </summary>
    internal async ValueTask<Hovered> HoverAsync(
        nint window,
        IReadOnlyList<int> owners,
        Candidate candidate,
        long stopAtMs,
        CancellationToken cancellationToken)
    {
        if (Left(stopAtMs) is not { } first)
            return new Hovered(null, string.Empty, BudgetSpent);
        List<Tip>? shownBefore = await TipsAsync(window, owners, first, cancellationToken).ConfigureAwait(false);
        bool polling = shownBefore is not null;
        var already = new HashSet<string>(shownBefore?.Select(tip => tip.Name) ?? [], StringComparer.Ordinal);
        // A tooltip names the candidate only where its tooltip opens: one elsewhere (the person's cursor back on another
        // control after the last candidate was given back, one shown late) is another control's.
        PixelBox strip = HoverStrip(candidate.Screen);
        if (Left(stopAtMs) is not { } waitBudget)
            return new Hovered(null, string.Empty, BudgetSpent);
        IInputBurst burst;
        using (var pause = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken))
        {
            pause.CancelAfter(waitBudget);
            try
            {
                burst = await _desktop.AcquireAsync(window, pause.Token).ConfigureAwait(false);
            }
            catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
            {
                return new Hovered(null, string.Empty, BudgetSpent);
            }
        }

        try
        {
            if (burst.Refusal is string refusal)
                return new Hovered(null, string.Empty, refusal);
            int x = candidate.Screen.CenterX;
            int y = candidate.Screen.CenterY;
            if (!_desktop.HoldsPoint(window, x, y))
                return new Hovered(null, "window_not_at_point", null);
            VisibleControlSurface.CapturedWindow? before = await _desktop.CaptureAsync(window, null, cancellationToken)
                .ConfigureAwait(false);
            if (!_desktop.Hover(burst, x, y))
                return new Hovered(null, string.Empty, "input_user_interrupted");
            long deadline = Math.Min(_desktop.NowMs + TooltipWaitMs, stopAtMs);
            while (_desktop.NowMs < deadline)
            {
                await _desktop.DelayAsync(PollMs, cancellationToken).ConfigureAwait(false);
                if (burst.UserActed)
                    return new Hovered(null, string.Empty, "input_user_interrupted");
                long left = deadline - _desktop.NowMs;
                if (!polling || left <= 0)
                    continue;
                List<Tip>? now = await TipsAsync(
                    window,
                    owners,
                    TimeSpan.FromMilliseconds(Math.Clamp(left + PollMs, MinimumPollMs, WorkerBudget.TotalMilliseconds)),
                    cancellationToken).ConfigureAwait(false);
                // No answer in time: the tree of this window is too slow to poll inside a pause; the capture decides.
                polling = now is not null;
                foreach (Tip tip in now ?? [])
                {
                    if (!already.Contains(tip.Name) && tip.Box is { } box && box.Intersects(strip))
                        return new Hovered(tip.Name, "tooltipUia", null, box);
                }
            }

            if (before is not { } earlier)
                return new Hovered(null, "no_capture", null);
            VisibleControlSurface.CapturedWindow? after = await _desktop.CaptureAsync(
                window, earlier.SelfDrawn, cancellationToken).ConfigureAwait(false);
            if (burst.UserActed)
                return new Hovered(null, string.Empty, "input_user_interrupted");
            // The cursor and the front go back now: what is left is reading two images.
            _ = burst.Restore();
            if (after is not { } later || later.Sha256 == earlier.Sha256
                || TooltipImage.FromBmp(earlier.Bmp) is not { } firstImage
                || TooltipImage.FromBmp(later.Bmp) is not { } second)
                return new Hovered(null, "nothing_changed", null);
            PixelBox hoveredBox = candidate.Screen.Offset(-earlier.Left, -earlier.Top);
            if (TooltipImage.ChangedBox(firstImage, second, HoverStrip(hoveredBox), hoveredBox) is not { } changed)
                return new Hovered(null, "change_is_no_tooltip", null);
            if (_desktop.NowMs >= stopAtMs)
                return new Hovered(null, string.Empty, BudgetSpent);
            PixelBox read = changed.Inflate(4);
            IReadOnlyList<(string Text, PixelBox Box)> newLines = await _desktop.ReadLinesAsync(
                second.CropBmp(read), cancellationToken).ConfigureAwait(false);
            IReadOnlyList<(string Text, PixelBox Box)> oldLines = await _desktop.ReadLinesAsync(
                firstImage.CropBmp(read), cancellationToken).ConfigureAwait(false);
            string text = TooltipImage.NewText(
                newLines, oldLines.Select(line => line.Text), hoveredBox.Offset(-read.X, -read.Y));
            return text.Length > 0
                ? new Hovered(text, "tooltipOcr", null, changed.Offset(earlier.Left, earlier.Top))
                : new Hovered(null, "tooltip_unread", null);
        }
        finally
        {
            _ = burst.Restore();
        }
    }

    /// <summary>
    /// The window before the press: for a label just read by hovering, after its tooltip is gone (by UIA) and two captures
    /// in a row are the same, at most <see cref="SettleLooks"/> looks; for a remembered one, at once.
    /// </summary>
    private async ValueTask<VisibleControlSurface.CapturedWindow?> SettledAsync(
        Learned learned, CancellationToken cancellationToken)
    {
        VisibleControlSurface.CapturedWindow? last = await _desktop.CaptureAsync(learned.Window, null, cancellationToken)
            .ConfigureAwait(false);
        if (learned.FromCache || last is null)
            return last;
        IReadOnlyList<int> owners = _desktop.DrawingProcesses(learned.Window);
        bool tipShown = learned.Source == "tooltipUia";
        for (int look = 0; look < SettleLooks; look++)
        {
            await _desktop.DelayAsync(SettleMs, cancellationToken).ConfigureAwait(false);
            VisibleControlSurface.CapturedWindow? next = await _desktop.CaptureAsync(
                learned.Window, last.Value.SelfDrawn, cancellationToken).ConfigureAwait(false);
            if (tipShown)
            {
                // A worker that does not answer in time says nothing more: the marks of the hover are left out anyway.
                List<Tip>? tips = await TipsAsync(learned.Window, owners, SettleTipsBudget, cancellationToken)
                    .ConfigureAwait(false);
                tipShown = tips is not null && tips.Any(tip => string.Equals(tip.Name, learned.Label, StringComparison.Ordinal));
            }

            bool still = next is { } now && now.Sha256 == last.Value.Sha256;
            if (next is not null)
                last = next;
            if (still && !tipShown)
                break;
        }

        return last;
    }

    private static bool ChangedBeyond(
        VisibleControlSurface.CapturedWindow before, VisibleControlSurface.CapturedWindow after, IReadOnlyList<PixelBox> marks) =>
        TooltipImage.FromBmp(before.Bmp) is not { } first || TooltipImage.FromBmp(after.Bmp) is not { } second
            || TooltipImage.ChangedOutside(first, second, marks);

    /// <summary>What is left of the budget for one call to the worker (at most its own budget); null when spent.</summary>
    private TimeSpan? Left(long stopAtMs)
    {
        long left = stopAtMs - _desktop.NowMs;
        return left <= 0 ? null : TimeSpan.FromMilliseconds(Math.Min(left, WorkerBudget.TotalMilliseconds));
    }

    /// <summary>A tooltip shown on the screen: its text and its rectangle (screen pixels), when the tree gave one.</summary>
    internal readonly record struct Tip(string Name, PixelBox? Box);

    /// <summary>
    /// The strip of at most 480×300 around a hovered control where its tooltip opens (on the screen, or in the pixels of
    /// a capture for a box in them): a tooltip elsewhere is another control's.
    /// </summary>
    internal static PixelBox HoverStrip(PixelBox hovered) => new(hovered.CenterX - 240, hovered.CenterY - 140, 480, 300);

    /// <summary>The tooltips shown now; null when the worker did not answer inside <paramref name="timeout"/>.</summary>
    private async ValueTask<List<Tip>?> TipsAsync(
        nint window, IReadOnlyList<int> owners, TimeSpan timeout, CancellationToken cancellationToken)
    {
        using JsonDocument? answer = await _worker.SendAsync(
            new JsonObject { ["cmd"] = "tooltips", ["hwnd"] = (long)window, ["pids"] = new JsonArray(owners.Select(owner => (JsonNode?)owner).ToArray()) }.ToJsonString(),
            timeout,
            cancellationToken).ConfigureAwait(false);
        if (answer is null)
            return null;
        var shown = new List<Tip>();
        if (answer.RootElement is { ValueKind: JsonValueKind.Object } root
            && root.TryGetProperty("tips", out JsonElement tips) && tips.ValueKind == JsonValueKind.Array)
        {
            foreach (JsonElement tip in tips.EnumerateArray())
            {
                if (tip.ValueKind == JsonValueKind.Object
                    && tip.TryGetProperty("name", out JsonElement name)
                    && name.ValueKind == JsonValueKind.String
                    && name.GetString() is { Length: > 0 } text)
                {
                    shown.Add(new Tip(text.Trim(), ReadRect(tip)));
                }
            }
        }

        return shown;
    }

    private static PixelBox? ReadRect(JsonElement control)
    {
        if (control.ValueKind != JsonValueKind.Object
            || !control.TryGetProperty("rect", out JsonElement rect) || rect.ValueKind != JsonValueKind.Object)
            return null;
        int Read(string name) =>
            rect.TryGetProperty(name, out JsonElement value) && value.TryGetInt32(out int number) ? number : -1;
        int w = Read("w");
        int h = Read("h");
        return w > 0 && h > 0 ? new PixelBox(Read("x"), Read("y"), w, h) : null;
    }

    /// <summary>
    /// The learned control pressed like a point OCR found: through the tree at its centre when a control there has a
    /// way (a control of the tree just hovered goes with its identity, so its pattern presses it without the mouse),
    /// else the pointer inside a burst of the lease; proved by the window changing outside the hover's own marks (the
    /// control's highlight and where its tooltip shows, which the cursor left on it brings back), read within 1.5 s.
    /// A label just read is pressed once its tooltip is gone and the window holds still, so the fading tooltip is not
    /// the baseline. A remembered place whose press changed nothing is forgotten.
    /// </summary>
    private async ValueTask<ExternalCapabilityReceipt?> PressAsync(
        string operation,
        string label,
        Learned learned,
        IPointPress? press,
        CancellationToken cancellationToken)
    {
        VisibleControlSurface.CapturedWindow? captured = await SettledAsync(learned, cancellationToken).ConfigureAwait(false);
        if (captured is not { } before)
            return null;
        PixelBox relative = learned.Screen.Offset(-learned.Capture.Left, -learned.Capture.Top);
        PixelBox[] marks = [relative.Inflate(6), (learned.Tip ?? HoverStrip(relative)).Inflate(8)];
        // A remembered place is pressed only where the tree shows no control of its size with another name.
        LocatedPointPress.Outcome pressed = await LocatedPointPress.PressAsync(
            press, operation, learned.Window, learned.Screen.CenterX, learned.Screen.CenterY, learned.Label,
            null, null, cancellationToken, learned.ControlId,
            learned.FromCache ? (learned.Screen.W, learned.Screen.H) : null).ConfigureAwait(false);
        if (pressed.Failure is { } refused)
            return refused;
        if (pressed.Before is { } fresh)
            before = fresh;
        IInputBurst? burst = pressed.Burst;
        bool changed = false;
        bool userActed = false;
        bool restored = true;
        try
        {
            for (int look = 0; look < PostReadLooks && !changed && burst is not { UserActed: true }; look++)
            {
                await _desktop.DelayAsync(look == 0 ? 300 : 220, cancellationToken).ConfigureAwait(false);
                VisibleControlSurface.CapturedWindow? after = await _desktop.CaptureAsync(
                    learned.Window, before.SelfDrawn, cancellationToken).ConfigureAwait(false);
                changed = after is { } later && later.Sha256 != before.Sha256 && ChangedBeyond(before, later, marks);
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

        changed &= !userActed;
        bool targeted = pressed.Method == "target" && pressed.Focused;
        bool ok = changed || targeted;
        if (!ok && learned.FromCache && !userActed)
            _cache.Forget(learned.Signature, learned.Place);
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteBoolean("ok", ok);
            writer.WriteBoolean("effectObserved", true);
            writer.WriteString("error", ok ? "" : userActed ? "input_user_interrupted" : "visible_button_postread_unchanged");
            writer.WriteString("name", learned.Label);
            writer.WriteString("nameSource", learned.Source);
            writer.WriteBoolean("learnedBefore", learned.FromCache);
            writer.WriteString("controlIdentity", "tooltip." + learned.Screen.CenterX + "." + learned.Screen.CenterY);
            writer.WriteBoolean("absentOrDisabled", false);
            writer.WriteBoolean("selected", false);
            writer.WriteBoolean("surfaceChanged", changed);
            writer.WriteString("method", pressed.Method);
            if (targeted)
            {
                writer.WriteBoolean("targeted", true);
                writer.WriteBoolean("focused", true);
            }

            writer.WriteString("cascadeStage", Stage);
            writer.WriteNumber("waitedMs", burst?.WaitedMs ?? 0);
            writer.WriteBoolean("restored", restored);
            writer.WriteString("authority", "tooltip_hover_locate_click_postread");
            writer.WriteEndObject();
        });
        return ok
            ? ExternalJson.Success(operation, result, true)
            : ExternalJson.Failure(operation, userActed ? "input_user_interrupted" : "visible_click_postread_invalid", true);
    }
}

/// <summary>The tooltip stage's desktop on Win32: the bound window, the lease, the cursor and the OCR.</summary>
internal sealed partial class WindowsTooltipDesktop : ITooltipDesktop
{
    private readonly ScreenPointer _pointer = new();

    public nint BoundWindow()
    {
        nint window = VisibleControlSurface.BoundWindow;
        return VisibleControlSurface.IsAlive(window) ? window : 0;
    }

    public (int ProcessId, string ProcessName) Process(nint window) => VisibleControlSurface.ViewProcess(window);

    public IReadOnlyList<int> DrawingProcesses(nint window) => VisibleControlSurface.DrawingProcesses(window);

    public string ClassName(nint window) => VisibleControlSurface.ClassName(window);

    public ValueTask<VisibleControlSurface.CapturedWindow?> CaptureAsync(
        nint window, bool? selfDrawn, CancellationToken cancellationToken)
    {
        try
        {
            return VisibleControlSurface.CaptureAsync(window, cancellationToken, selfDrawn: selfDrawn);
        }
        catch (Exception exception) when (exception is IOException or InvalidOperationException)
        {
            return ValueTask.FromResult<VisibleControlSurface.CapturedWindow?>(null);
        }
    }

    public ValueTask<IInputBurst> AcquireAsync(nint window, CancellationToken cancellationToken) =>
        _pointer.AcquireAsync(window, cancellationToken);

    public bool HoldsPoint(nint window, int screenX, int screenY)
    {
        if (!VisibleControlSurface.ForegroundIs(window))
            return false;
        nint hit = VisibleControlSurface.InPhysicalPixels(() => WindowFromPoint(new Point { X = screenX, Y = screenY }));
        if (hit == 0)
            return false;
        nint root = GetAncestor(hit, 2);
        return (root == 0 ? hit : root) == window;
    }

    public bool Hover(IInputBurst burst, int screenX, int screenY)
    {
        // Two placements, the last one pixel apart: a tooltip waits for a mouse move that rests on its control.
        if (!VisibleControlSurface.PointAt(burst, screenX - 1, screenY))
            return false;
        Thread.Sleep(30);
        return VisibleControlSurface.PointAt(burst, screenX, screenY);
    }

    public async ValueTask<IReadOnlyList<(string Text, PixelBox Box)>> ReadLinesAsync(
        byte[] bmp, CancellationToken cancellationToken)
    {
        if (bmp.Length == 0)
            return [];
        IReadOnlyList<WindowsVisibleOcrLocator.LayoutLine>? lines = await WindowsVisibleOcrLocator.ReadLayoutAsync(
            bmp, 80, cancellationToken).ConfigureAwait(false);
        return lines is null
            ? []
            : lines.Select(line => (line.Text, new PixelBox(
                (int)line.X, (int)line.Y, Math.Max(1, (int)Math.Ceiling(line.Width)), Math.Max(1, (int)Math.Ceiling(line.Height)))))
                .ToList();
    }

    public long NowMs => Environment.TickCount64;

    public ValueTask DelayAsync(int milliseconds, CancellationToken cancellationToken) =>
        new(Task.Delay(milliseconds, cancellationToken));

    [StructLayout(LayoutKind.Sequential)]
    private struct Point
    {
        public int X;
        public int Y;
    }

    [LibraryImport("user32.dll")]
    private static partial nint WindowFromPoint(Point point);

    [LibraryImport("user32.dll")]
    private static partial nint GetAncestor(nint window, uint flags);
}
