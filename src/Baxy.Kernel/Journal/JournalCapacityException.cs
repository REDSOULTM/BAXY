namespace Baxy.Kernel.Journal;

public sealed class JournalCapacityException : IOException
{
    public JournalCapacityException(string message)
        : base(message)
    {
    }
}
