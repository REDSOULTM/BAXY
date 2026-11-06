namespace Baxy.Providers.Windows.Infrastructure;

/// <summary>
/// Encargo 61b: the application an operation acts in, by the name app.open takes, for an operation whose provider presses
/// inside one application's window (calculator.expression.evaluate: the Windows Calculator's keypad, read by UI
/// Automation). One source for that provider's own refusal («app_open … starts it») and for the App, which weighs the
/// person's words against that application's names (ApplicationAliases.FormsOf: its name and its abbreviations in the
/// names data) instead of a list of its own. Null for an operation that is no one application's.
/// </summary>
public static class OperationApplications
{
    /// <summary>The application <paramref name="operation"/> acts in; null when it is no one application's.</summary>
    public static string? Of(string operation) => operation switch
    {
        "calculator.expression.evaluate" => "Calculator",
        _ => null,
    };
}
