namespace Baxy.Setup;

public sealed class ProductPackageException : Exception
{
    public ProductPackageException(string message)
        : base(message)
    {
    }

    public ProductPackageException(string message, Exception innerException)
        : base(message, innerException)
    {
    }
}

public sealed class InstallationSafetyException : Exception
{
    public InstallationSafetyException(string message)
        : base(message)
    {
    }

    public InstallationSafetyException(string message, Exception innerException)
        : base(message, innerException)
    {
    }
}

public sealed class SetupSimulatedCrashException : Exception
{
    public SetupSimulatedCrashException(SetupFaultPoint faultPoint)
        : base($"Simulated Setup crash at {faultPoint}.")
    {
        FaultPoint = faultPoint;
    }

    public SetupFaultPoint FaultPoint { get; }
}
