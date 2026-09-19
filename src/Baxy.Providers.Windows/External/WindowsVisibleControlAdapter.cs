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

    internal WindowsVisibleControlAdapter()
        : this(
            new ExternalProcessRunner(),
            Path.Combine(AppContext.BaseDirectory, "DesktopClickVisible.ps1"),
            new WindowsVisibleOcrLocator(),
            new WindowsVisibleVisionLocator())
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
        IVisibleControlLocator? vision)
    {
        _runner = runner;
        _script = script;
        _ocr = ocr;
        _vision = vision;
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
        DateTime deadline = DateTime.UtcNow + LabelWaitBudget;
        ExternalCapabilityReceipt uia;
        while (true)
        {
            uia = await InvokeUiaAsync(
                operation, label, cancellationToken).ConfigureAwait(false);
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

            // UI1765: a cascade answer («not found yet», no accessible tree)
            // is worth waiting on; any other error (no surface, no window,
            // cancelled) ends the wait.
            if ((uia.ErrorCode is not null && !CascadeAfter.Contains(uia.ErrorCode))
                || DateTime.UtcNow >= deadline)
                break;
            await Task.Delay(LabelWaitInterval, cancellationToken).ConfigureAwait(false);
        }

        return uia.ErrorCode is null
            ? ExternalJson.Failure(operation, "visible_button_not_found")
            : uia;
    }

    private static readonly TimeSpan LabelWaitBudget = TimeSpan.FromSeconds(24);
    private static readonly TimeSpan LabelWaitInterval = TimeSpan.FromMilliseconds(1500);

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
            // de instalación de Steam, que devuelve «Chrome Legacy Window» y nada
            // más. Cuando pasa, se lee lo que está escrito.
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
        CancellationToken cancellationToken)
    {
        string encoded = Convert.ToBase64String(Encoding.UTF8.GetBytes(label));
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
                ["-NoProfile", "-NonInteractive", "-STA", "-File", _script, "-LabelBase64", encoded],
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
