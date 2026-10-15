namespace Baxy.App;

/// <summary>
/// Contract between the Field view and the WPF shell: when a turn or a voice
/// control is admitted.
/// </summary>
internal static class FieldBridgeContract
{
    internal const string AgentNotReadyError = "agent_not_ready";

    internal const int AgentNotReadyStatus = 409;

    /// <summary>
    /// Chat and voice stay closed until the shell has a verified ready
    /// terminal. A rejected turn never starts a mission.
    /// </summary>
    internal static bool TryAcceptTurn(
        bool isInputEnabled,
        string? text,
        out string error,
        out int status)
    {
        if (!isInputEnabled)
        {
            error = AgentNotReadyError;
            status = AgentNotReadyStatus;
            return false;
        }

        if (string.IsNullOrWhiteSpace(text))
        {
            error = "invalid_text";
            status = 400;
            return false;
        }

        error = string.Empty;
        status = 200;
        return true;
    }

    internal static bool TryAcceptVoiceControl(bool isReady, out string error, out int status)
    {
        if (!isReady)
        {
            error = AgentNotReadyError;
            status = AgentNotReadyStatus;
            return false;
        }

        error = string.Empty;
        status = 200;
        return true;
    }
}
