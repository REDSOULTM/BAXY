using System.Text.Json;
using Baxy.Contracts;

namespace Baxy.App;

/// <summary>
/// Redacta el texto de las operaciones que tocan datos del usuario —memoria
/// privada y audio—: la confirmación que pide, el fallo que reporta y lo que
/// quedó pendiente de comprobar. Sólo depende de la operación, no del turno.
/// </summary>
internal static class PrivateOperationNarration
{
    internal static string CreateMemoryClarification(MemoryParseResult result)
    {
        if (result.MustNotDelete)
        {
            return "No borraré nada todavía. Indica exactamente qué recuerdo quieres eliminar.";
        }

        if (result.MustNotPersist)
        {
            return "No guardaré nada todavía. Indica exactamente qué dato quieres conservar y por cuánto tiempo.";
        }

        if (result.MustNotInvent)
        {
            return "No inventaré recuerdos. Formula una consulta concreta sobre lo que quieres que revise.";
        }

        return "Necesito una petición de memoria más concreta. No guardé, borré ni consulté información.";
    }

    internal static string CreateMemoryConfirmationPrompt(
        PreparedOperation prepared,
        bool reconciliationRequired = false) =>
        reconciliationRequired
            ? "Esta acción pudo haber comenzado antes de perderse la respuesta. Responde únicamente «confirmar / confirm» para reconciliar exactamente el mismo intento; no iniciaré otra acción mientras el resultado siga incierto."
            : prepared.OperationName switch
            {
                "memory.sensitive.save" =>
                    "Guardar este dato sensible supone un riesgo de privacidad. Responde únicamente «confirmar / confirm» para guardarlo o «cancelar / cancel» para descartarlo.",
                "memory.forget" =>
                    "Esta acción eliminaría memoria local y no se puede deshacer. Responde únicamente «confirmar / confirm» o «cancelar / cancel».",
                "memory.enable" =>
                    "Habilitar la memoria local permitirá conservar datos que pidas recordar. Responde únicamente «confirmar / confirm» o «cancelar / cancel».",
                "memory.export" =>
                    "Exportar memoria a Documentos/BAXY puede exponer información privada; esa carpeta puede estar redirigida o sincronizada según tu configuración de Windows. Responde únicamente «confirmar / confirm» o «cancelar / cancel».",
                _ =>
                    "Esta acción de memoria requiere confirmación. Responde únicamente «confirmar / confirm» o «cancelar / cancel».",
            };

    internal static string CreateMemoryFailureMessage(
        string operationName,
        OperationResponse response)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(operationName);
        ArgumentNullException.ThrowIfNull(response);
        if (string.Equals(operationName, "memory.export", StringComparison.Ordinal)
            && response.Replayed)
        {
            return "No pude corroborar de nuevo el resultado anterior. Puede existir un archivo en Documentos/BAXY, pero no afirmaré que siga presente e íntegro; solicita una nueva exportación.";
        }

        return response.Status switch
        {
            OperationStatuses.Pending =>
                "La petición sobre la memoria local sigue pendiente de una comprobación segura. No afirmaré que terminó.",
            OperationStatuses.Rejected =>
                "No hice el cambio solicitado en la memoria local porque no superó las comprobaciones de seguridad.",
            OperationStatuses.Failed when string.Equals(
                response.ErrorCode,
                "memory_disabled",
                StringComparison.Ordinal) =>
                "La memoria local está deshabilitada. Habilítala primero si quieres guardar o consultar datos.",
            OperationStatuses.Failed =>
                "No pude completar la petición sobre la memoria local de forma segura.",
            _ =>
                "No recibí una respuesta segura para la petición sobre la memoria local.",
        };
    }

    internal static string CreateMemoryRecoveryPrompt(PreparedOperation prepared)
    {
        string category = prepared.OperationName switch
        {
            "memory.enable" or "memory.disable" => "un cambio de configuración de memoria",
            "memory.save" or "memory.sensitive.save" or "memory.correct" =>
                "una actualización de memoria privada",
            "memory.forget" or "memory.session.clear" => "un borrado de memoria privada",
            "memory.recall" or "memory.list" or "memory.status" =>
                "una consulta de memoria privada",
            "memory.export" => "una exportación de memoria privada",
            _ => "una petición de memoria privada",
        };
        return $"Quedó pendiente comprobar {category}. Responde «continuar / continue / retry» para reenviar exactamente la misma petición; no iniciaré otra acción mientras su resultado siga incierto.";
    }

    internal static string CreateAudioRecoveryPrompt(PreparedOperation operation)
    {
        JsonElement arguments = operation.Arguments;
        if (string.Equals(operation.OperationName, "audio.volume", StringComparison.Ordinal)
            && arguments.TryGetProperty("level", out JsonElement level)
            && level.ValueKind == JsonValueKind.Number
            && level.TryGetInt32(out int requestedLevel))
        {
            return $"Quedó pendiente confirmar el volumen solicitado ({requestedLevel} %). Responde «continuar / continue / retry» o repite esa misma petición para reconciliarla; no iniciaré otra acción mientras siga incierto.";
        }

        if (string.Equals(operation.OperationName, "audio.mute", StringComparison.Ordinal)
            && arguments.TryGetProperty("state", out JsonElement state)
            && state.ValueKind is JsonValueKind.True or JsonValueKind.False)
        {
            string requestedState = state.GetBoolean() ? "silenciar" : "reactivar";
            return $"Quedó pendiente confirmar el intento de {requestedState} el audio. Responde «continuar / continue / retry» o repite esa misma petición para reconciliarlo; no iniciaré otra acción mientras siga incierto.";
        }

        return "Quedó pendiente confirmar un ajuste de audio. Responde «continuar / continue / retry» o repite la misma petición para reconciliarlo; no iniciaré otra acción mientras siga incierto.";
    }
}
