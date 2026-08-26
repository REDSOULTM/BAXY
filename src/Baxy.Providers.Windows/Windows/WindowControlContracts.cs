namespace Baxy.Providers.Windows.Windows;

public static class WindowSelector
{
    public static bool Matches(string selector, string processName, string title)
    {
        string needle = Fold(selector);
        if (needle.Length == 0)
        {
            return false;
        }

        string process = Fold(processName);
        string windowTitle = Fold(title);
        if (string.Equals(process, needle, StringComparison.Ordinal)
            || string.Equals(windowTitle, needle, StringComparison.Ordinal))
        {
            return true;
        }

        return needle.Length >= 4
            && (process.StartsWith(needle, StringComparison.Ordinal)
                || windowTitle.Contains(needle, StringComparison.Ordinal));
    }

    private static string Fold(string value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return string.Empty;
        }

        string trimmed = value.Trim();
        if (trimmed.EndsWith(".exe", StringComparison.OrdinalIgnoreCase))
        {
            trimmed = trimmed[..^4];
        }

        var folded = new System.Text.StringBuilder(trimmed.Length);
        foreach (char character in trimmed.Normalize(System.Text.NormalizationForm.FormD))
        {
            if (System.Globalization.CharUnicodeInfo.GetUnicodeCategory(character)
                == System.Globalization.UnicodeCategory.NonSpacingMark)
            {
                continue;
            }

            folded.Append(char.ToLowerInvariant(character));
        }

        return folded.ToString().Normalize(System.Text.NormalizationForm.FormC);
    }
}

public static class WindowControlErrorCodes
{
    public const string InvalidSelector = "invalid_selector";
    public const string WindowNotFound = "window_not_found";
    public const string InvalidOrExpiredWindowId = "invalid_or_expired_window_id";
    public const string WindowIdentityChanged = "window_identity_changed";
    public const string ActionFailed = "action_failed";
    public const string VerificationFailed = "verification_failed";
    public const string InventoryFailed = "inventory_failed";
}

public enum WindowControlAction
{
    Focus,
    Minimize,
    Maximize,
    Restore,
}

public sealed record WindowCandidate(
    string WindowId,
    int ProcessId,
    string ProcessName,
    string State,
    bool Foreground,
    int X,
    int Y,
    int Width,
    int Height);

public sealed record WindowResolveResult(
    bool Succeeded,
    bool Verified,
    IReadOnlyList<WindowCandidate> Windows,
    string? ErrorCode);

public sealed record WindowActionResult(
    bool Succeeded,
    bool Verified,
    WindowCandidate? Window,
    string? ErrorCode);

public sealed record WindowCloseResult(
    bool Succeeded,
    bool Verified,
    int? ProcessId,
    string? ErrorCode);

public interface IWindowControlProvider
{
    ValueTask<WindowResolveResult> ResolveForegroundAsync(
        CancellationToken cancellationToken);

    ValueTask<WindowResolveResult> ResolveAsync(
        string processName,
        int limit,
        CancellationToken cancellationToken);

    ValueTask<WindowActionResult> ExecuteAsync(
        string windowId,
        WindowControlAction action,
        CancellationToken cancellationToken);

    ValueTask<WindowActionResult> SetBoundsAsync(
        string windowId,
        int? x,
        int? y,
        int? width,
        int? height,
        CancellationToken cancellationToken);

    ValueTask<WindowCloseResult> CloseAsync(
        string windowId,
        CancellationToken cancellationToken);
}
