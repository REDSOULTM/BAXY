namespace Baxy.App;

internal sealed record ConversationMessage(
    string Speaker,
    string Body,
    bool IsUser,
    DateTimeOffset CreatedAt,
    string? Route = null);
