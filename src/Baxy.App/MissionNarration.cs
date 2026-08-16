namespace Baxy.App;

/// <summary>
/// Redacta el texto que BAXY dice sobre una misión multipaso: qué completó, por
/// qué se detuvo y qué se recuperó de una sesión anterior. No conoce la ventana
/// ni el estado del turno: recibe los resultados ya verificados y devuelve texto.
/// </summary>
internal static class MissionNarration
{
    internal static string CreateCompletionMessage(
        IReadOnlyList<string> completedMessages)
    {
        ArgumentNullException.ThrowIfNull(completedMessages);
        if (completedMessages.Count == 0)
        {
            throw new ArgumentException(
                "Una misión completada debe contener al menos un resultado.",
                nameof(completedMessages));
        }

        if (completedMessages.Count == 1)
        {
            return completedMessages[0].Trim();
        }

        return string.Concat(
            $"Completé y verifiqué los {completedMessages.Count} pasos de la misión.\n",
            CreateOutcomeList(completedMessages));
    }

    internal static string CreateFailureMessage(
        IReadOnlyList<string> completedMessages,
        string reason)
    {
        ArgumentNullException.ThrowIfNull(completedMessages);
        ArgumentException.ThrowIfNullOrWhiteSpace(reason);
        if (completedMessages.Count == 0)
        {
            return reason.Trim();
        }

        return string.Concat(
            "No pude completar toda la misión. ",
            $"Antes de detenerla, completé y verifiqué {completedMessages.Count} paso(s):\n",
            CreateOutcomeList(completedMessages),
            "\nMotivo: ",
            reason.Trim());
    }

    internal static string CreateRecoveryPrompt(PendingMindPlanExecution execution)
    {
        ArgumentNullException.ThrowIfNull(execution);
        if (MindPlanBoundary.CanRefreshConfirmationChallenge(execution))
        {
            return "Hay una misión multipaso cuyo paso actual ya había comenzado y puede haber producido un efecto. Conservé su evidencia de recuperación. Di «confirmar / confirm» para comprobar exactamente el mismo intento; «cancelar / cancel» detiene los pasos nuevos, pero no borra la evidencia incierta.";
        }

        if (execution.PendingEffectMayHaveOccurred)
        {
            return "Hay una misión multipaso con un efecto anterior que puede haber ocurrido. Conservé su evidencia de recuperación y no repetiré ni continuaré la misión hasta comprobarlo con el estado real.";
        }

        return "Hay una misión multipaso pendiente de una sesión anterior. Di «continuar» para reanudarla desde el último paso guardado o «cancelar» para detener sus pasos restantes.";
    }

    private static string CreateOutcomeList(IReadOnlyList<string> completedMessages)
    {
        return string.Join(
            '\n',
            completedMessages.Select(static (message, index) =>
                $"• Paso {index + 1}: {NormalizeOutcome(message)}"));
    }

    private static string NormalizeOutcome(string message)
    {
        if (string.IsNullOrWhiteSpace(message))
        {
            return "Completado y verificado.";
        }

        return string.Join(
            ' ',
            message.Split(
                ['\r', '\n'],
                StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries));
    }
}
