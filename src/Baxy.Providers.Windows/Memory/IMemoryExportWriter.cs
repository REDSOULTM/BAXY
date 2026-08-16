namespace Baxy.Providers.Windows.Memory;

public sealed record MemoryExportRequest(
    string InvocationId,
    IReadOnlyList<MemoryRecord> Records);

public sealed record MemoryExportResult(
    string Path,
    int RecordCount,
    string Sha256,
    bool Replayed);

public sealed record MemoryExportVerificationRequest(
    string InvocationId,
    string Path,
    int RecordCount,
    string Sha256);

public interface IMemoryExportWriter
{
    MemoryExportResult Export(MemoryExportRequest request);

    bool Verify(MemoryExportVerificationRequest request);
}

public abstract class MemoryExportException : Exception
{
    protected MemoryExportException(string message)
        : base(message)
    {
    }
}

public sealed class UnsafeMemoryExportPathException : MemoryExportException
{
    public UnsafeMemoryExportPathException()
        : base("The local memory export path is unsafe.")
    {
    }
}

public sealed class MemoryExportConflictException : MemoryExportException
{
    public MemoryExportConflictException()
        : base("The export invocation already has different durable content.")
    {
    }
}

public sealed class MemoryExportUnavailableException : MemoryExportException
{
    public MemoryExportUnavailableException()
        : base("The local memory export is unavailable.")
    {
    }
}
