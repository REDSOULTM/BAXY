using Baxy.Contracts;
using Baxy.Kernel.Mission;

namespace Baxy.Kernel.Tests;

/// <summary>
/// Auditoría del núcleo 2026-10-23: an invocation that started and did not end, whose run may have acted, is not run
/// again without the person. Its retry asks (reconciliationRequired) and runs on that yes; this is that retry.
/// </summary>
internal static class UncertainStart
{
    internal static async Task<(OperationResponse Asked, OperationResponse Confirmed)> RetryAsync(
        MissionEngine engine,
        OperationRequest request,
        CancellationToken cancellationToken = default)
    {
        OperationResponse asked = await engine.ExecuteAsync(
            request with { RequestId = Guid.NewGuid().ToString("D"), ConfirmationToken = null },
            cancellationToken);
        if (asked.ErrorCode != ConfirmationChallengeContract.RequiredErrorCode
            || !asked.Result!.Value.GetProperty("reconciliationRequired").GetBoolean())
        {
            throw new InvalidOperationException("The retry of an uncertain start did not ask for reconciliation.");
        }

        OperationResponse confirmed = await engine.ExecuteAsync(
            request with
            {
                RequestId = Guid.NewGuid().ToString("D"),
                ConfirmationToken = asked.Result!.Value.GetProperty("token").GetString(),
            },
            cancellationToken);
        return (asked, confirmed);
    }
}
