using System.Security.Cryptography;
using System.Text.Json;
using Baxy.Contracts;
using Baxy.Kernel.Operations;

namespace Baxy.Kernel.Mission;

internal static class PrivateOperationBoundary
{
    internal const string PublicSuccessMessage =
        DefaultOperationResponseNarrator.PrivateSuccessMessage;
    internal const string PublicFailureMessage =
        DefaultOperationResponseNarrator.PrivateFailureMessage;
    private const int MaximumCiphertextBytes = (256 * 1024) + 64;
    private const int MaximumCiphertextCharacters = ((MaximumCiphertextBytes + 2) / 3) * 4;
    private static readonly HashSet<string> AllowedFailureCodes = new(StringComparer.Ordinal)
    {
        "invalid_arguments",
        "memory_capacity_reached",
        "memory_conflict",
        "memory_disabled",
        "memory_export_conflict",
        "memory_export_unavailable",
        "memory_invocation_conflict",
        "memory_not_found",
        "memory_operation_failed",
        "memory_protection_failed",
        "memory_store_unavailable",
        "operation_failed",
        "reconciliation_required",
        "verification_failed",
    };

    internal static bool IsPrivateOperation(string operation) =>
        operation.StartsWith("memory.", StringComparison.Ordinal);

    internal static bool HasProtectedArguments(OperationRequest request) =>
        HasProtectedEnvelope(
            request.Arguments,
            CreatePurpose(
                "memory.arguments.v1",
                request.Operation,
                request.MissionId,
                request.InvocationId));

    internal static OperationOutcome NormalizeOutcome(
        OperationRequest request,
        OperationOutcome outcome,
        IPrivateOperationEnvelopeAuthenticator? authenticator)
    {
        ArgumentNullException.ThrowIfNull(request);
        ArgumentNullException.ThrowIfNull(outcome);
        if (!IsPrivateOperation(request.Operation))
        {
            return outcome;
        }

        if (outcome.Succeeded
            && outcome.Verified
            && outcome.ProtectedPrivateResult
            && outcome.Result is { ValueKind: JsonValueKind.Object } result
            && HasProtectedEnvelope(
                result,
                CreatePurpose(
                    "memory.result.v1",
                    request.Operation,
                    request.MissionId,
                    request.InvocationId))
            && AuthenticateResult(authenticator, request, result))
        {
            return OperationOutcome.PrivateSuccess(result);
        }

        string errorCode = outcome.ErrorCode is not null
            && AllowedFailureCodes.Contains(outcome.ErrorCode)
                ? outcome.ErrorCode
                : "memory_operation_failed";
        // La reducción a la lista cerrada protege la privacidad del código de
        // error y descarta `causeCode`, que es texto libre del handler. La
        // ambigüedad del efecto sí se conserva: es un booleano, no transporta
        // contenido, y perderlo convertiría «pudo haber ocurrido» en «no
        // ocurrió», que es justo lo que empuja a repetir una operación privada
        // ya aplicada a medias.
        return outcome.Retryable
            ? OperationOutcome.RetryableFailure(
                errorCode,
                effectMayHaveOccurred: outcome.EffectMayHaveOccurred)
            : OperationOutcome.Failure(
                errorCode,
                effectMayHaveOccurred: outcome.EffectMayHaveOccurred);
    }

    internal static OperationResponse NormalizeReplay(
        OperationRequest request,
        OperationResponse response,
        IPrivateOperationEnvelopeAuthenticator? authenticator,
        IOperationResponseNarrator narrator)
    {
        ArgumentNullException.ThrowIfNull(request);
        ArgumentNullException.ThrowIfNull(response);
        ArgumentNullException.ThrowIfNull(narrator);
        if (!IsPrivateOperation(request.Operation))
        {
            return response with
            {
                RequestId = request.RequestId,
                Replayed = true,
            };
        }

        if (string.Equals(response.Status, OperationStatuses.Completed, StringComparison.Ordinal)
            && response.Verified
            && response.ErrorCode is null
            && response.Result is { ValueKind: JsonValueKind.Object } result
            && HasProtectedEnvelope(
                result,
                CreatePurpose(
                    "memory.result.v1",
                    request.Operation,
                    request.MissionId,
                    request.InvocationId))
            && AuthenticateResult(authenticator, request, result))
        {
            return new OperationResponse(
                ProtocolTypes.OperationResponse,
                request.RequestId,
                request.MissionId,
                request.InvocationId,
                OperationStatuses.Completed,
                narrator.Narrate(
                    request.Operation,
                    OperationOutcome.PrivateSuccess(result)),
                true,
                true,
                result,
                null);
        }

        string errorCode = response.ErrorCode is not null
            && AllowedFailureCodes.Contains(response.ErrorCode)
                ? response.ErrorCode
                : "memory_operation_failed";
        // La ambigüedad viaja igual que en la primera ejecución. Reconstruir el
        // fallo sin ella haría que el replay de la misma invocationId dijera
        // «no ocurrió» sobre un efecto que sí pudo aplicarse, que es justo lo
        // que empuja a repetirlo. `causeCode` sigue descartado: es texto libre
        // del handler y podría llevar detalle privado.
        return new OperationResponse(
            ProtocolTypes.OperationResponse,
            request.RequestId,
            request.MissionId,
            request.InvocationId,
            OperationStatuses.Failed,
            narrator.Narrate(
                request.Operation,
                OperationOutcome.Failure(
                    errorCode,
                    effectMayHaveOccurred: response.EffectMayHaveOccurred)),
            false,
            true,
            null,
            errorCode,
            response.EffectMayHaveOccurred);
    }

    private static bool AuthenticateResult(
        IPrivateOperationEnvelopeAuthenticator? authenticator,
        OperationRequest request,
        JsonElement result)
    {
        if (authenticator is null)
        {
            return false;
        }

        try
        {
            return authenticator.AuthenticateResult(request, result);
        }
        catch (Exception)
        {
            return false;
        }
    }

    private static bool HasProtectedEnvelope(JsonElement envelope, string expectedPurpose)
    {
        if (envelope.ValueKind != JsonValueKind.Object)
        {
            return false;
        }

        var names = new HashSet<string>(StringComparer.Ordinal);
        foreach (JsonProperty property in envelope.EnumerateObject())
        {
            if (!names.Add(property.Name)
                || property.Name is not ("version" or "protection" or "purpose" or "ciphertext"))
            {
                return false;
            }
        }

        if (names.Count != 4
            || !envelope.TryGetProperty("version", out JsonElement version)
            || version.ValueKind != JsonValueKind.Number
            || !version.TryGetInt32(out int versionNumber)
            || versionNumber != 1
            || !string.Equals(version.GetRawText(), "1", StringComparison.Ordinal)
            || !envelope.TryGetProperty("protection", out JsonElement protection)
            || protection.ValueKind != JsonValueKind.String
            || !IsProtectionName(protection.GetString())
            || !envelope.TryGetProperty("purpose", out JsonElement purpose)
            || purpose.ValueKind != JsonValueKind.String
            || !string.Equals(purpose.GetString(), expectedPurpose, StringComparison.Ordinal)
            || !envelope.TryGetProperty("ciphertext", out JsonElement ciphertextElement)
            || ciphertextElement.ValueKind != JsonValueKind.String)
        {
            return false;
        }

        string? ciphertextText = ciphertextElement.GetString();
        if (string.IsNullOrEmpty(ciphertextText)
            || ciphertextText.Length > MaximumCiphertextCharacters
            || ciphertextText.Length % 4 != 0)
        {
            return false;
        }

        byte[] ciphertext;
        try
        {
            ciphertext = Convert.FromBase64String(ciphertextText);
        }
        catch (FormatException)
        {
            return false;
        }

        try
        {
            return ciphertext.Length is > 0 and <= MaximumCiphertextBytes
                && string.Equals(
                    Convert.ToBase64String(ciphertext),
                    ciphertextText,
                    StringComparison.Ordinal);
        }
        finally
        {
            CryptographicOperations.ZeroMemory(ciphertext);
        }
    }

    private static bool IsProtectionName(string? value)
    {
        if (string.IsNullOrEmpty(value) || value.Length > 64)
        {
            return false;
        }

        foreach (char character in value)
        {
            if (character is not (>= 'a' and <= 'z')
                and not (>= '0' and <= '9')
                and not '-')
            {
                return false;
            }
        }

        return true;
    }

    private static string CreatePurpose(
        string domain,
        string operation,
        string missionId,
        string invocationId) =>
        string.Concat(domain, "|", operation, "|", missionId, "|", invocationId);
}
