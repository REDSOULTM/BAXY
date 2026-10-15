namespace Baxy.Kernel.Planning;

// The plan validator is gone (auditoría K4) and nothing throws this any more.
// It stays only because Baxy.App/FieldUiBridge.cs IsExpectedBridgeFailure still
// names it; it goes with that line.
public sealed class MissionPlanValidationException : Exception
{
    public MissionPlanValidationException(string message)
        : base(message)
    {
    }
}
