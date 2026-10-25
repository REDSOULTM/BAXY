using System.Text.Json.Nodes;

namespace Baxy.App;

/// <summary>
/// Práctica e2e E014 («abre la configuración de sonido», c3-junto-s0, 2026-10-25): the place this turn's app.open asked
/// for, so a look at that application's window says whether the place in sight is that one (ScreenViewProjection, aid
/// asked_place). The last app.open that completed holds: with a place, that application and place; with none, nothing
/// asked. A new turn or a heartbeat asks nothing.
/// </summary>
internal sealed class TurnPlace
{
    /// <summary>The application and place the turn's last completed app.open asked for; null when none was asked.</summary>
    internal (string Application, string Place)? Asked { get; private set; }

    /// <summary>A turn the person opened (not an answer to the waiting call) or a heartbeat.</summary>
    internal void NewTurn() => Asked = null;

    /// <summary>A call ran with <paramref name="arguments"/> as sent and ended with <paramref name="status"/>.</summary>
    internal void Ran(string operation, JsonObject arguments, string? status)
    {
        if (operation != "app.open" || status != "completed")
        {
            return;
        }

        Asked = Text(arguments["appId"]) is { } application && Text(arguments["place"]) is { } place
            ? (application, place)
            : null;
    }

    private static string? Text(JsonNode? node) =>
        node is JsonValue value && value.TryGetValue(out string? text) && !string.IsNullOrWhiteSpace(text) ? text.Trim() : null;
}
