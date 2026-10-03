using System.Globalization;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace Baxy.Providers.Windows.External;

internal interface IVisibleControlLocator
{
    string Stage { get; }

    ValueTask<ExternalCapabilityReceipt?> TryClickAsync(
        string operation,
        string label,
        CancellationToken cancellationToken);
}

// The application app.open brought up moments ago, if any: a click right after an opening acts on it.
internal interface IOpenedApplicationFocus
{
    VisibleControlSurface.OpenedApplication? TakeOpened();

    VisibleControlSurface.OpenedApplication? PeekOpened();

    // The opened application's main window, brought to the front (none yet: Window 0), and whether it looks drawn
    // (judged only when asked; otherwise drawn).
    ValueTask<VisibleControlSurface.OpenedSurface> FrontAsync(
        VisibleControlSurface.OpenedApplication opened,
        bool judgeDrawn,
        CancellationToken cancellationToken);

    // That window is still the one in front: the UI Automation stage reads the window in front.
    bool Holds(nint window);
}

internal sealed class OpenedApplicationFocus : IOpenedApplicationFocus
{
    // A click asked in the same breath as the opening, or answered after its confirmation, comes well inside this.
    private static readonly TimeSpan Freshness = TimeSpan.FromSeconds(90);

    public VisibleControlSurface.OpenedApplication? TakeOpened() =>
        VisibleControlSurface.TakeOpened(Freshness);

    public VisibleControlSurface.OpenedApplication? PeekOpened() =>
        VisibleControlSurface.PeekOpened(Freshness);

    public ValueTask<VisibleControlSurface.OpenedSurface> FrontAsync(
        VisibleControlSurface.OpenedApplication opened,
        bool judgeDrawn,
        CancellationToken cancellationToken) =>
        VisibleControlSurface.FrontOpenedAsync(opened, judgeDrawn, cancellationToken);

    public bool Holds(nint window) => VisibleControlSurface.ForegroundIs(window);
}

internal sealed class NoOpenedApplicationFocus : IOpenedApplicationFocus
{
    public VisibleControlSurface.OpenedApplication? TakeOpened() => null;

    public VisibleControlSurface.OpenedApplication? PeekOpened() => null;

    public ValueTask<VisibleControlSurface.OpenedSurface> FrontAsync(
        VisibleControlSurface.OpenedApplication opened,
        bool judgeDrawn,
        CancellationToken cancellationToken) => ValueTask.FromResult(default(VisibleControlSurface.OpenedSurface));

    public bool Holds(nint window) => true;
}

// How long a click looks for its label. M132 (owner script t42 «En … ve a crash bandicoot», 28 s for «no hay ningún
// elemento visible con ese nombre»): a label is waited on only while the surface may still be drawing — an
// application opened moments ago — and then for a bounded stretch once its window is up; on a window that was
// already there, a second look settles it and the honest «not there» comes at once.
internal sealed record VisibleClickTiming(
    TimeSpan LaunchSurface,
    TimeSpan ReusedSurface,
    TimeSpan OpenedLabel,
    TimeSpan SettledLabel,
    TimeSpan Interval)
{
    internal static VisibleClickTiming Default { get; } = new(
        LaunchSurface: TimeSpan.FromSeconds(30),
        ReusedSurface: TimeSpan.FromSeconds(5),
        OpenedLabel: TimeSpan.FromSeconds(10),
        SettledLabel: TimeSpan.FromSeconds(3),
        Interval: TimeSpan.FromMilliseconds(1500));
}

internal sealed class WindowsVisibleControlAdapter : IExternalOperationAdapter
{
    private static readonly HashSet<string> CascadeAfter = new(StringComparer.Ordinal)
    {
        "visible_button_not_found",
        "visible_button_uia_failed",
        "visible_click_no_receipt",
        "active_window_not_found",
    };

    // H0096 «aprieta en Among Us»: el script sólo emite este código después de
    // recorrer el árbol y los botones nativos y no encontrar nada con ese
    // nombre, es decir, antes de tocar nada. Marcarlo como «pudo haber efecto»
    // sólo porque la frontera se cruza al arrancar convertía una ausencia
    // medida en una duda, y el turno la contaba como un resultado sin
    // confirmar en vez de decir que ahí no había nada así.
    private static readonly HashSet<string> BeforeAnyPress = new(StringComparer.Ordinal)
    {
        "visible_button_not_found",
    };

    private readonly IExternalProcessRunner _runner;
    private readonly string _script;
    private readonly IVisibleControlLocator? _ocr;
    private readonly IVisibleControlLocator? _vision;
    private readonly IOpenedApplicationFocus _focus;
    private readonly VisibleClickTiming _timing;

    internal WindowsVisibleControlAdapter()
        : this(
            new ExternalProcessRunner(),
            Path.Combine(AppContext.BaseDirectory, "DesktopClickVisible.ps1"),
            new WindowsVisibleOcrLocator(),
            new WindowsVisibleVisionLocator(),
            new OpenedApplicationFocus(),
            VisibleClickTiming.Default)
    {
    }

    // Nombrar un control para pulsarlo exige saber como se llama. Esta lectura
    // dice que hay delante, y con ella un pedido sobre algo que no esta en la
    // pantalla se contesta diciendolo en vez de intentando un clic a ciegas.
    private string ListScript =>
        Path.Combine(Path.GetDirectoryName(_script) ?? AppContext.BaseDirectory,
            "DesktopListVisible.ps1");

    internal WindowsVisibleControlAdapter(IExternalProcessRunner runner, string script)
        : this(runner, script, ocr: null, vision: null)
    {
    }

    internal WindowsVisibleControlAdapter(
        IExternalProcessRunner runner,
        string script,
        IVisibleControlLocator? ocr,
        IVisibleControlLocator? vision,
        IOpenedApplicationFocus? focus = null,
        VisibleClickTiming? timing = null)
    {
        _runner = runner;
        _script = script;
        _ocr = ocr;
        _vision = vision;
        _focus = focus ?? new NoOpenedApplicationFocus();
        _timing = timing ?? VisibleClickTiming.Default;
    }

    public bool CanHandle(string operation) =>
        operation is "input.visible.click" or "input.visible.controls";

    public async ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        if (operation == "input.visible.controls")
            return await ListAsync(operation, arguments, cancellationToken).ConfigureAwait(false);
        if (!File.Exists(_script))
            return ExternalJson.Failure(operation, "visible_click_script_missing");
        string label;
        try
        {
            label = ExternalJson.RequiredString(arguments, "label");
        }
        catch (InvalidDataException)
        {
            return ExternalJson.FailureBeforeEffect(
                operation, "visible_click_argument_invalid");
        }

        // UI1731 → UI1735: an application that was just opened draws its
        // interface over several seconds (the Epic Games Launcher shows its
        // navigation about ten seconds after its window exists). A label that
        // no stage finds yet is looked for again, bounded, before the click is
        // declared not found — the way a person waits for a screen to load.
        // M132: that wait belongs to the application just opened, on its own
        // window. Its window is waited for (a client that updates itself shows
        // only a small updater at first) and, when it was launched now, its
        // page is waited on until it is drawn — nothing is looked at or pressed
        // meanwhile; then the label for a bounded stretch on each new main
        // window. Any other click looks two or three times and answers.
        VisibleControlSurface.OpenedApplication? opened = _focus.TakeOpened();
        nint surfaceWindow = 0;
        DateTime? lookingSince = null;
        ExternalCapabilityReceipt? uia = null;
        TimeSpan labelBudget = opened is null ? _timing.SettledLabel : _timing.OpenedLabel;
        DateTime settled = opened is { } noted
            ? noted.NotedUtc + (noted.Launched ? _timing.LaunchSurface : _timing.ReusedSurface)
            : DateTime.MinValue;
        // Whatever happens to the opened application's windows, the click ends by here.
        DateTime cap = (settled > DateTime.UtcNow ? settled : DateTime.UtcNow) + labelBudget;
        while (true)
        {
            bool look = true;
            if (opened is { } application)
            {
                VisibleControlSurface.OpenedSurface surface = await _focus.FrontAsync(
                    application, judgeDrawn: application.Launched, cancellationToken).ConfigureAwait(false);
                if (surface.Window != 0 && surface.Window != surfaceWindow)
                {
                    // A login window replaced by the main one is a new surface: its label gets its own wait.
                    surfaceWindow = surface.Window;
                    lookingSince = null;
                }
                bool settling = DateTime.UtcNow < settled;
                look = surface.Window != 0 && (surface.Drawn || !settling);
                if (!look && !settling && lookingSince is null)
                    break;
                if (DateTime.UtcNow >= cap)
                    break;
            }

            if (look)
            {
                lookingSince ??= DateTime.UtcNow;
                // Bound to the opened application's window: if the front moved
                // elsewhere (the person took it), nothing is read or pressed there.
                using IDisposable bound = VisibleControlSurface.RequireWindow(
                    opened is null ? 0 : surfaceWindow);
                uia = opened is null || _focus.Holds(surfaceWindow)
                    ? await InvokeUiaAsync(
                        operation, label, opened is null ? 0 : surfaceWindow, cancellationToken).ConfigureAwait(false)
                    : ExternalJson.FailureBeforeEffect(operation, "visible_button_not_found");
                if (ShouldKeep(uia))
                    return uia;

                if (_ocr is not null)
                {
                    ExternalCapabilityReceipt? ocr = await _ocr.TryClickAsync(
                        operation, label, cancellationToken).ConfigureAwait(false);
                    if (ocr is not null && ShouldKeep(ocr))
                        return ocr;
                    if (ocr is not null && !ShouldCascade(ocr))
                        return ocr;
                }

                if (_vision is not null)
                {
                    ExternalCapabilityReceipt? vision = await _vision.TryClickAsync(
                        operation, label, cancellationToken).ConfigureAwait(false);
                    if (vision is not null)
                        return vision;
                }
            }

            // UI1765: a cascade answer («not found yet», no accessible tree)
            // is worth waiting on; any other error (no surface, no window,
            // cancelled) ends the wait.
            if ((look && uia?.ErrorCode is { } code && !CascadeAfter.Contains(code))
                || (lookingSince is { } since && DateTime.UtcNow >= since + labelBudget))
                break;
            await Task.Delay(_timing.Interval, cancellationToken).ConfigureAwait(false);
        }

        // Nothing looked at means nothing pressed: no window of the opened application ever showed.
        if (uia is null)
            return ExternalJson.FailureBeforeEffect(operation, "visible_button_not_found");
        return uia.ErrorCode is null
            ? ExternalJson.Failure(operation, "visible_button_not_found")
            : uia;
    }

    // Lectura: nombra los controles de la ventana en primer plano, los que se
    // pueden accionar primero. No toca nada, de modo que no cruza frontera de
    // efecto y cabe en un turno ordinario.
    private async ValueTask<ExternalCapabilityReceipt> ListAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        string script = ListScript;
        if (!File.Exists(script))
            return ExternalJson.Failure(operation, "visible_controls_script_missing");
        // M132: a look right after an opening reads the application opened, not what was in front before it.
        if (_focus.PeekOpened() is { } opened)
            _ = await _focus.FrontAsync(opened, judgeDrawn: false, cancellationToken).ConfigureAwait(false);
        int limit = 40;
        if (arguments.ValueKind == JsonValueKind.Object
            && arguments.TryGetProperty("limit", out JsonElement requested)
            && requested.ValueKind == JsonValueKind.Number
            && requested.TryGetInt32(out int value))
        {
            limit = Math.Clamp(value, 1, 60);
        }

        try
        {
            ExternalProcessResult process = await _runner.RunAsync(
                "powershell.exe",
                [
                    "-NoProfile", "-NonInteractive", "-STA", "-File", script,
                    "-Limit", limit.ToString(CultureInfo.InvariantCulture),
                ],
                TimeSpan.FromSeconds(20), cancellationToken).ConfigureAwait(false);
            string? line = process.Output
                .Split(['\r', '\n'], StringSplitOptions.RemoveEmptyEntries)
                .LastOrDefault();
            if (line is null)
                return ExternalJson.Failure(operation, "visible_controls_no_receipt");
            using JsonDocument document = JsonDocument.Parse(line);
            JsonElement root = document.RootElement;
            if (!root.TryGetProperty("ok", out JsonElement ok)
                || ok.ValueKind != JsonValueKind.True)
            {
                string code = root.TryGetProperty("error", out JsonElement error)
                    && error.ValueKind == JsonValueKind.String
                    && error.GetString() is { Length: > 0 } text
                        ? text
                        : "visible_controls_unavailable";
                return ExternalJson.Failure(operation, code);
            }

            // Una ventana que sólo expone su contenedor no es una ventana sin
            // controles: es una que este canal no sabe leer. Medido en el diálogo
            // de instalación de un lanzador de juegos (CEF), que devuelve la
            // ventana heredada del motor y nada más. Cuando pasa, se lee lo que está escrito.
            int counted = root.TryGetProperty("controls", out JsonElement listed)
                && listed.ValueKind == JsonValueKind.Array
                    ? listed.GetArrayLength()
                    : 0;
            if (counted > 1)
                return ExternalJson.Success(operation, root.Clone(), false);

            string[]? lines = await WindowsVisibleOcrLocator
                .TryReadLinesAsync(limit, cancellationToken).ConfigureAwait(false);
            if (lines is null || lines.Length == 0)
                return ExternalJson.Success(operation, root.Clone(), false);

            string window = root.TryGetProperty("window", out JsonElement named)
                && named.ValueKind == JsonValueKind.String
                    ? named.GetString() ?? string.Empty
                    : string.Empty;
            JsonElement read = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteNumber("version", 1);
                writer.WriteBoolean("ok", true);
                writer.WriteString("error", string.Empty);
                writer.WriteString("window", window);
                writer.WriteNumber("controlCount", lines.Length);
                writer.WriteStartArray("controls");
                foreach (string line in lines)
                {
                    writer.WriteStartObject();
                    writer.WriteString("name", line);
                    writer.WriteString("kind", "Text");
                    writer.WriteEndObject();
                }

                writer.WriteEndArray();
                writer.WriteString("authority", "windows_media_ocr_lines");
                writer.WriteEndObject();
            });
            return ExternalJson.Success(operation, read, false);
        }
        catch (Exception exception) when (exception is IOException or JsonException
            or TimeoutException or OperationCanceledException)
        {
            return ExternalJson.Failure(operation, "visible_controls_receipt_invalid");
        }
    }

    private async ValueTask<ExternalCapabilityReceipt> InvokeUiaAsync(
        string operation,
        string label,
        nint window,
        CancellationToken cancellationToken)
    {
        string encoded = Convert.ToBase64String(Encoding.UTF8.GetBytes(label));
        List<string> arguments = ["-NoProfile", "-NonInteractive", "-STA", "-File", _script, "-LabelBase64", encoded];
        if (window != 0)
            arguments.AddRange(["-WindowHandle", ((long)window).ToString(CultureInfo.InvariantCulture)]);
        var effectBoundary = new ExternalEffectBoundary();
        // The descriptor admits «surface changed» as post-read. A Calculator
        // digit stays enabled and unselected after Invoke, so the surface is
        // the only evidence (UI1273); it is compared before/after the script.
        VisibleControlSurface.CapturedWindow? before = null;
        try
        {
            before = await VisibleControlSurface.CaptureForegroundAsync(cancellationToken)
                .ConfigureAwait(false);
        }
        catch (Exception exception) when (exception is IOException or InvalidOperationException)
        {
            before = null;
        }
        try
        {
            effectBoundary.Cross(cancellationToken);
            ExternalProcessResult process = await _runner.RunAsync(
                "powershell.exe",
                arguments,
                TimeSpan.FromSeconds(15), cancellationToken).ConfigureAwait(false);
            string? line = process.Output.Split(['\r', '\n'], StringSplitOptions.RemoveEmptyEntries)
                .LastOrDefault();
            if (line is null)
                return effectBoundary.Failure(operation, "visible_click_no_receipt");
            using JsonDocument document = JsonDocument.Parse(line);
            ExternalCapabilityReceipt receipt = ReceiptFromScript(
                operation, document.RootElement, effectBoundary);
            if (receipt.ErrorCode == "visible_button_postread_unchanged" && before is { } captured)
            {
                VisibleControlSurface.CapturedWindow? after = null;
                try
                {
                    after = await VisibleControlSurface.CaptureForegroundAsync(cancellationToken)
                        .ConfigureAwait(false);
                }
                catch (Exception exception) when (exception is IOException or InvalidOperationException)
                {
                    after = null;
                }
                bool changed = after is { } later
                    && later.Hwnd == captured.Hwnd
                    && !string.Equals(later.Sha256, captured.Sha256, StringComparison.Ordinal);
                VisibleControlSurface.Delete(after?.Path);
                if (changed)
                {
                    JsonObject node = JsonNode.Parse(document.RootElement.GetRawText())!.AsObject();
                    node["ok"] = true;
                    node["error"] = "";
                    node["surfaceChanged"] = true;
                    node["cascadeStage"] = "uia_surface";
                    using JsonDocument verified = JsonDocument.Parse(node.ToJsonString());
                    return ExternalJson.Success(operation, verified.RootElement.Clone(), true);
                }
            }
            return receipt;
        }
        catch (OperationCanceledException) when (
            cancellationToken.IsCancellationRequested && effectBoundary.WasCrossed)
        {
            return effectBoundary.Failure(operation, "visible_click_receipt_invalid");
        }
        catch (Exception exception) when (exception is IOException or JsonException or TimeoutException)
        {
            return effectBoundary.Failure(operation, "visible_click_receipt_invalid");
        }
        finally
        {
            VisibleControlSurface.Delete(before?.Path);
        }
    }

    internal static bool PostreadHolds(JsonElement root)
    {
        bool dismissed = root.TryGetProperty("absentOrDisabled", out JsonElement dismissedValue)
            && dismissedValue.ValueKind == JsonValueKind.True;
        bool selected = root.TryGetProperty("selected", out JsonElement selectedValue)
            && selectedValue.ValueKind == JsonValueKind.True;
        bool surface = root.TryGetProperty("surfaceChanged", out JsonElement surfaceValue)
            && surfaceValue.ValueKind == JsonValueKind.True;
        return dismissed || selected || surface;
    }

    private static ExternalCapabilityReceipt ReceiptFromScript(
        string operation,
        JsonElement root,
        ExternalEffectBoundary effectBoundary)
    {
        bool effect = root.TryGetProperty("effectObserved", out JsonElement observed)
            && observed.GetBoolean();
        bool ok = root.TryGetProperty("ok", out JsonElement accepted) && accepted.GetBoolean();
        if (!ok)
        {
            string error = root.TryGetProperty("error", out JsonElement errorValue)
                ? errorValue.GetString() ?? "visible_click_failed"
                : "visible_click_failed";
            return !effect && BeforeAnyPress.Contains(error)
                ? ExternalJson.FailureBeforeEffect(operation, error)
                : effectBoundary.Failure(operation, error, effect);
        }
        if (!effect || !PostreadHolds(root))
            return effectBoundary.Failure(
                operation, "visible_click_postread_invalid", effect);
        return ExternalJson.Success(operation, root.Clone(), true);
    }

    private static bool ShouldKeep(ExternalCapabilityReceipt receipt) =>
        receipt.Verified && receipt.ErrorCode is null;

    private static bool ShouldCascade(ExternalCapabilityReceipt receipt) =>
        receipt.ErrorCode is not null && CascadeAfter.Contains(receipt.ErrorCode);
}
