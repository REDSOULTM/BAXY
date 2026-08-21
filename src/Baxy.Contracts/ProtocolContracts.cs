using System.Text.Json;
using System.Text.Json.Serialization;

namespace Baxy.Contracts;

public sealed record ProtocolHello(
    [property: JsonRequired] string Type,
    [property: JsonRequired] string Protocol,
    [property: JsonRequired] string CoreVersion,
    [property: JsonRequired] int Pid,
    [property: JsonRequired] IReadOnlyList<OperationDescriptor> Capabilities,
    [property: JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    ApplicationCatalogSnapshot? ApplicationCatalog = null,
    [property: JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    GameCatalogSnapshot? GameCatalog = null);

public sealed record ApplicationCatalogSnapshot(
    [property: JsonRequired] int Version,
    [property: JsonRequired] bool Verified,
    [property: JsonRequired] bool Complete,
    [property: JsonRequired] IReadOnlyList<string> Names);

public sealed record GameCatalogSnapshot(
    [property: JsonRequired] int Version,
    [property: JsonRequired] bool Verified,
    [property: JsonRequired] bool Complete,
    [property: JsonRequired] IReadOnlyList<GameCatalogEntry> Entries);

public sealed record GameCatalogEntry(
    [property: JsonRequired] string Provider,
    [property: JsonRequired] string AppId,
    [property: JsonRequired] string Name);

public sealed record OperationDescriptor(
    [property: JsonRequired] string Name,
    [property: JsonRequired] JsonElement ArgumentsSchema,
    [property: JsonRequired] string Risk,
    [property: JsonRequired] string VerifierContractId,
    [property: JsonRequired] string Description);

public sealed record OperationRequest(
    [property: JsonRequired] string Type,
    [property: JsonRequired] string RequestId,
    [property: JsonRequired] string MissionId,
    [property: JsonRequired] string InvocationId,
    [property: JsonRequired] string Operation,
    [property: JsonRequired] JsonElement Arguments,
    [property: JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    string? ConfirmationToken = null)
{
    public override string ToString() =>
        $"{nameof(OperationRequest)} {{ Type = {Type}, RequestId = {RequestId}, "
        + $"MissionId = {MissionId}, InvocationId = {InvocationId}, Operation = {Operation}, "
        + "Arguments = [REDACTED], ConfirmationToken = [REDACTED] }";
}

/// <summary>
/// Autocorrección durable: la afirmación visible, la verificación que la
/// desmintió y el texto con el que se corrige. Viaja en la respuesta
/// terminal para que el journal y la App la lean igual.
/// </summary>
public sealed record HonestyCorrectionTrace(
    [property: JsonRequired] string Claim,
    [property: JsonRequired] string Verification,
    [property: JsonRequired] string Correction);

public sealed record OperationResponse(
    [property: JsonRequired] string Type,
    [property: JsonRequired] string RequestId,
    [property: JsonRequired] string MissionId,
    [property: JsonRequired] string InvocationId,
    [property: JsonRequired] string Status,
    [property: JsonRequired] string Message,
    [property: JsonRequired] bool Verified,
    [property: JsonRequired] bool Replayed,
    [property: JsonRequired] JsonElement? Result,
    [property: JsonRequired] string? ErrorCode,
    [property: JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingDefault)]
    bool EffectMayHaveOccurred = false,
    [property: JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    string? CauseCode = null,
    [property: JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    HonestyCorrectionTrace? HonestyCorrection = null)
{
    public override string ToString() =>
        $"{nameof(OperationResponse)} {{ Type = {Type}, RequestId = {RequestId}, "
        + $"MissionId = {MissionId}, InvocationId = {InvocationId}, Status = {Status}, "
        + $"Message = [REDACTED], Verified = {Verified}, Replayed = {Replayed}, "
        + $"Result = [REDACTED], ErrorCode = {ErrorCode}, "
        + $"EffectMayHaveOccurred = {EffectMayHaveOccurred}, CauseCode = {CauseCode}, "
        + $"HonestyCorrection = {(HonestyCorrection is null ? "null" : "[REDACTED]")} }}";
}

public sealed record ProtocolError(
    [property: JsonRequired] string Type,
    [property: JsonRequired] string ErrorCode,
    [property: JsonRequired] string Message);
