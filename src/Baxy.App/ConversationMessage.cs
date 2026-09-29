namespace Baxy.App;

// SourceUrl (M53, D35): the page a consulted answer was written from, shown as a small
// «fuente» link under the message; never part of the body, so the voice never reads it.
internal sealed record ConversationMessage(
    string Speaker,
    string Body,
    bool IsUser,
    DateTimeOffset CreatedAt,
    string? Route = null,
    string? SourceUrl = null)
{
    public string TimeLabel => CreatedAt.ToLocalTime().ToString("HH:mm", System.Globalization.CultureInfo.CurrentCulture);

    public string AccessibleText => $"{Speaker}: {Body}";
}
