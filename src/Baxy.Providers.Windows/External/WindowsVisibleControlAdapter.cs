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

    public bool CanHandle(string operation) => operation == "input.visible.click";

    public async ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
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

        ExternalCapabilityReceipt uia = await InvokeUiaAsync(
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

        return uia.ErrorCode is null
            ? ExternalJson.Failure(operation, "visible_button_not_found")
            : uia;
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
            return effectBoundary.Failure(operation, error, effect);
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
