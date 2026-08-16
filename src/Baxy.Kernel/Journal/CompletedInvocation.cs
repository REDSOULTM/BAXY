using Baxy.Contracts;

namespace Baxy.Kernel.Journal;

public sealed record CompletedInvocation(
    string RequestFingerprint,
    OperationResponse Response);
