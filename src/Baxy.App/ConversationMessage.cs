namespace Baxy.App;

internal sealed record ConversationMessage(
    string Speaker,
    string Body,
    bool IsUser,
    DateTimeOffset CreatedAt,
    string? Route = null)
{
    public string TimeLabel => CreatedAt.ToLocalTime().ToString("HH:mm", System.Globalization.CultureInfo.CurrentCulture);

    public string AccessibleText => $"{Speaker}: {Body}";
}
