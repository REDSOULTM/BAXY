using System.Text.Json;

namespace Baxy.Kernel.Operations;

public sealed record OperationInvocation(
    string RequestId,
    string MissionId,
    string InvocationId,
    JsonElement Arguments);
