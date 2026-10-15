namespace Baxy.App;

/// <summary>
/// The route of a line BAXY published, for the interface and the evidence: the model's answer, its question, or its
/// question about a call that waits for the person's Sí or No (the interface shows the two buttons for it).
/// </summary>
internal static class PublicResponseRoute
{
    internal const string Conversation = "conversation";
    internal const string Clarification = "clarification";
    internal const string Confirmation = "confirmation";
}
