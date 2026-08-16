namespace Baxy.Providers.Windows.Memory;

public abstract class MemoryStoreException : Exception
{
    protected MemoryStoreException(string message)
        : base(message)
    {
    }

    protected MemoryStoreException(string message, Exception innerException)
        : base(message, innerException)
    {
    }
}

public sealed class MemoryDisabledException : MemoryStoreException
{
    public MemoryDisabledException()
        : base("Local memory is disabled.")
    {
    }
}

public sealed class MemoryConflictException : MemoryStoreException
{
    public MemoryConflictException()
        : base("The memory operation conflicts with the current record.")
    {
    }
}

public sealed class MemoryNotFoundException : MemoryStoreException
{
    public MemoryNotFoundException()
        : base("The requested memory record was not found.")
    {
    }
}

public sealed class MemoryCapacityException : MemoryStoreException
{
    public MemoryCapacityException()
        : base("The local memory store has reached a finite capacity limit.")
    {
    }
}

public sealed class MemoryInvocationConflictException : MemoryStoreException
{
    public MemoryInvocationConflictException()
        : base("The invocation identifier was already used for a different memory mutation.")
    {
    }
}

public sealed class MemoryStoreCorruptException : MemoryStoreException
{
    public MemoryStoreCorruptException()
        : base("The local memory store is incomplete, inconsistent, or cannot be authenticated.")
    {
    }

    internal MemoryStoreCorruptException(Exception innerException)
        : base("The local memory store is incomplete, inconsistent, or cannot be authenticated.", innerException)
    {
    }
}

public sealed class UnsafeMemoryStorePathException : MemoryStoreException
{
    public UnsafeMemoryStorePathException()
        : base("The local memory store path is not a safe local path.")
    {
    }
}
