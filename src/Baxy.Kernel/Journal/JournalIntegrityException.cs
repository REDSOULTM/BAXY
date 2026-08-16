namespace Baxy.Kernel.Journal;

public sealed class JournalIntegrityException : IOException
{
    public JournalIntegrityException(string message)
        : base(message)
    {
    }

    public JournalIntegrityException(string message, Exception innerException)
        : base(message, innerException)
    {
    }
}
