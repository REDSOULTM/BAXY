using System.Text.Json;
using Baxy.Contracts;
using Baxy.Kernel.Mission;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Memory;
using Baxy.Security.Windows;

namespace Baxy.Core.Operations;

internal sealed class MemoryEnvelopeAuthenticator(
    BoundProtectedJsonCodec codec,
    IMemoryExportWriter? exportVerifier = null)
    : IPrivateOperationEnvelopeAuthenticator, IPrivateOperationArgumentSchemaValidator
{
    private readonly BoundProtectedJsonCodec _codec =
        codec ?? throw new ArgumentNullException(nameof(codec));
    private readonly IMemoryExportWriter? _exportVerifier = exportVerifier;

    public bool AuthenticateArguments(OperationRequest request)
    {
        ArgumentNullException.ThrowIfNull(request);
        try
        {
            using OpenedBoundProtectedJson opened = _codec.OpenArguments(
                request.Arguments,
                request.Operation,
                request.MissionId,
                request.InvocationId);
            return ContractValidator.IsCanonicalIdentifier(opened.SessionId);
        }
        catch (Exception exception) when (IsAuthenticationFailure(exception))
        {
            return false;
        }
    }

    public bool AuthenticateResult(OperationRequest request, JsonElement result)
    {
        ArgumentNullException.ThrowIfNull(request);
        try
        {
            using OpenedBoundProtectedJson arguments = _codec.OpenArguments(
                request.Arguments,
                request.Operation,
                request.MissionId,
                request.InvocationId);
            using OpenedBoundProtectedJson privateResult = _codec.OpenResult(
                result,
                request.Operation,
                request.MissionId,
                request.InvocationId);
            if (!string.Equals(
                arguments.SessionId,
                privateResult.SessionId,
                StringComparison.Ordinal))
            {
                return false;
            }

            if (!string.Equals(request.Operation, MemoryOperationIds.Export, StringComparison.Ordinal))
            {
                return true;
            }

            MemoryExportWireResult? receipt = JsonSerializer.Deserialize(
                privateResult.Payload,
                MemoryHandlersJsonContext.Default.MemoryExportWireResult);
            return _exportVerifier is not null
                && receipt is not null
                && receipt.Version == 1
                && _exportVerifier.Verify(new MemoryExportVerificationRequest(
                    request.InvocationId,
                    receipt.Path,
                    receipt.RecordCount,
                    receipt.Sha256));
        }
        catch (Exception exception) when (IsAuthenticationFailure(exception))
        {
            return false;
        }
    }

    public bool ValidateArguments(
        OperationRequest request,
        OperationArgumentsSchema argumentsSchema)
    {
        ArgumentNullException.ThrowIfNull(request);
        ArgumentNullException.ThrowIfNull(argumentsSchema);
        try
        {
            using OpenedBoundProtectedJson opened = _codec.OpenArguments(
                request.Arguments,
                request.Operation,
                request.MissionId,
                request.InvocationId);
            return ContractValidator.IsCanonicalIdentifier(opened.SessionId)
                && OperationArgumentValidator.IsValid(opened.Payload, argumentsSchema);
        }
        catch (Exception exception) when (IsAuthenticationFailure(exception))
        {
            return false;
        }
    }

    private static bool IsAuthenticationFailure(Exception exception) => exception is
        ProtectedPayloadException
        or InvalidDataException
        or JsonException
        or ArgumentException;
}
