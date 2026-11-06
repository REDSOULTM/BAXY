using System.Text.Json;
using Baxy.Kernel.Operations;

namespace Baxy.Core.Operations;

/// <summary>
/// Encargo 80 (toma del tráiler, 4 de 4 en español e inglés): calculator.expression.evaluate with no Calculator open
/// failed with calculator_window_not_found, the model opened it by app.open and wrote the same expression again. That
/// failure is not a decision for the model: this operation now opens it by app.open itself (in front, for control, as
/// the model wrote it each time) and presses the expression there, and its result says so.
/// </summary>
internal sealed class CalculatorOpeningHandler(
    IOperationHandler evaluate,
    Func<OperationInvocation, CancellationToken, ValueTask<OperationOutcome>> open,
    TimeSpan? keypadBudget = null,
    Func<TimeSpan, CancellationToken, ValueTask>? delay = null)
    : IOperationHandler
{
    private const string NotOpen = "calculator_window_not_found";

    // The names it is opened by. Its package's own, which no language translates (WinAppDriver's Calculator sample
    // launches that package), then the name Windows Server's classic Calculator bears (win32calc, U14/U15). With neither,
    // the failure stays as it was: its next gives the model the call, which takes the name the catalog shows it.
    private static readonly string[] Names = ["Microsoft.WindowsCalculator", "Calculator"];

    // Refused before any button is pressed, so asked again: the frame app.open verified may show before its keypad does.
    // WinAppDriver's Calculator sample polls for the elements it looks for the same way.
    private static readonly TimeSpan Poll = TimeSpan.FromMilliseconds(250);
    private readonly TimeSpan _keypadBudget = keypadBudget ?? TimeSpan.FromSeconds(10);
    private readonly Func<TimeSpan, CancellationToken, ValueTask> _delay =
        delay ?? ((wait, token) => new ValueTask(Task.Delay(wait, token)));

    private readonly IOperationHandler _evaluate = evaluate ?? throw new ArgumentNullException(nameof(evaluate));
    private readonly Func<OperationInvocation, CancellationToken, ValueTask<OperationOutcome>> _open =
        open ?? throw new ArgumentNullException(nameof(open));

    public OperationDefinition Definition => _evaluate.Definition;

    public async ValueTask<OperationOutcome> ExecuteAsync(
        OperationInvocation invocation,
        CancellationToken cancellationToken)
    {
        OperationOutcome first = await _evaluate.ExecuteAsync(invocation, cancellationToken).ConfigureAwait(false);
        return first.ErrorCode == NotOpen
            ? await OpenAndEvaluateAsync(invocation, first, cancellationToken).ConfigureAwait(false)
            : first;
    }

    private async ValueTask<OperationOutcome> OpenAndEvaluateAsync(
        OperationInvocation invocation,
        OperationOutcome notOpen,
        CancellationToken cancellationToken)
    {
        OperationOutcome opened = notOpen;
        foreach (string name in Names)
        {
            opened = await _open(
                new OperationInvocation(
                    invocation.RequestId,
                    invocation.MissionId,
                    invocation.InvocationId + ":open",
                    JsonSerializer.SerializeToElement(
                        new OpenApplicationArguments(name, Foreground: true, ForControl: true),
                        CoreJsonContext.Default.OpenApplicationArguments)),
                cancellationToken).ConfigureAwait(false);
            if (opened.Succeeded || opened.ErrorCode != "app_not_found")
                break;
        }

        // Nothing was pressed: the failure it had, its next included, and whether the opening may have left a window.
        if (!opened.Succeeded)
        {
            return OperationOutcome.Failure(
                NotOpen,
                result: notOpen.Result,
                effectMayHaveOccurred: opened.EffectMayHaveOccurred,
                causeCode: opened.ErrorCode);
        }

        var clock = System.Diagnostics.Stopwatch.StartNew();
        OperationOutcome pressed = await _evaluate.ExecuteAsync(invocation, cancellationToken).ConfigureAwait(false);
        while (pressed.ErrorCode is NotOpen or "calculator_button_not_found" && clock.Elapsed < _keypadBudget)
        {
            await _delay(Poll, cancellationToken).ConfigureAwait(false);
            pressed = await _evaluate.ExecuteAsync(invocation, cancellationToken).ConfigureAwait(false);
        }

        JsonElement said = WithOpened(pressed.Result, opened.Result);
        return pressed.Succeeded
            ? pressed with { Result = said }
            // The Calculator was opened before this failed: an effect that did occur, never «nothing happened».
            : OperationOutcome.Failure(
                pressed.ErrorCode ?? "calculator_display_not_read",
                result: said,
                effectMayHaveOccurred: true,
                causeCode: pressed.CauseCode);
    }

    // What the expression's own result says, and the Calculator it opened with the id the window operations take. A next
    // that says to open it (its window was still not found) is dropped: it has just been opened.
    private static JsonElement WithOpened(JsonElement? result, JsonElement? opened)
    {
        var buffer = new System.Buffers.ArrayBufferWriter<byte>();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            writer.WriteStartObject();
            if (result is { ValueKind: JsonValueKind.Object } read)
            {
                foreach (JsonProperty property in read.EnumerateObject())
                {
                    if (property.Name != "next")
                        property.WriteTo(writer);
                }
            }

            string? name = null;
            if (opened is { ValueKind: JsonValueKind.Object } facts)
            {
                name = facts.TryGetProperty("displayName", out JsonElement shown) ? shown.GetString() : null;
                foreach (string id in (string[])["windowId", "window"])
                {
                    if (facts.TryGetProperty(id, out JsonElement window))
                    {
                        writer.WritePropertyName(id);
                        window.WriteTo(writer);
                    }
                }
            }

            writer.WriteString("applicationOpened", name ?? "Calculator");
            writer.WriteEndObject();
        }

        using JsonDocument document = JsonDocument.Parse(buffer.WrittenMemory);
        return document.RootElement.Clone();
    }
}
