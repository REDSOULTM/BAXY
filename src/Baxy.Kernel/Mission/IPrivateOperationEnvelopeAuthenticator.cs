using System.Text.Json;
using Baxy.Contracts;
using Baxy.Kernel.Operations;

namespace Baxy.Kernel.Mission;

/// <summary>
/// Authenticates private operation envelopes at the mission boundary without
/// coupling the kernel to an operating-system protection mechanism.
/// </summary>
public interface IPrivateOperationEnvelopeAuthenticator
{
    bool AuthenticateArguments(OperationRequest request);

    bool AuthenticateResult(OperationRequest request, JsonElement result);
}

/// <summary>
/// Validates the authenticated clear payload against the product operation
/// schema while keeping it inside the private-envelope boundary.
/// </summary>
public interface IPrivateOperationArgumentSchemaValidator
{
    bool ValidateArguments(
        OperationRequest request,
        OperationArgumentsSchema argumentsSchema);
}
