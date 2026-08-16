using System.Text;
using System.Text.Json;

namespace Baxy.Providers.Windows.External;

internal sealed class WindowsVisibleControlAdapter : IExternalOperationAdapter
{
    private readonly IExternalProcessRunner _runner;
    private readonly string _script;

    internal WindowsVisibleControlAdapter()
        : this(new ExternalProcessRunner(), Path.Combine(
            AppContext.BaseDirectory, "DesktopClickVisible.ps1"))
    {
    }

    internal WindowsVisibleControlAdapter(IExternalProcessRunner runner, string script)
    {
        _runner = runner;
        _script = script;
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
        string encoded = Convert.ToBase64String(Encoding.UTF8.GetBytes(label));
        var effectBoundary = new ExternalEffectBoundary();
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
            JsonElement root = document.RootElement;
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
            if (!effect || !root.GetProperty("absentOrDisabled").GetBoolean())
                return effectBoundary.Failure(
                    operation, "visible_click_postread_invalid", effect);
            return ExternalJson.Success(operation, root.Clone(), true);
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
    }
}
