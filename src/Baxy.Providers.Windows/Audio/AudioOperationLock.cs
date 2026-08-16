using System.Diagnostics;

namespace Baxy.Providers.Windows.Audio;

internal interface IAudioOperationLock
{
    IDisposable? TryAcquire(CancellationToken cancellationToken);
}

internal sealed class NamedAudioOperationLock : IAudioOperationLock
{
    internal const string DefaultName = @"Local\BAXY.Audio.DefaultOutput.v1";
    private static readonly TimeSpan MaximumWait = TimeSpan.FromSeconds(5);
    private static readonly TimeSpan PollInterval = TimeSpan.FromMilliseconds(25);

    private readonly string _name;

    public NamedAudioOperationLock()
        : this(DefaultName)
    {
    }

    internal NamedAudioOperationLock(string name)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(name);
        _name = name;
    }

    public IDisposable? TryAcquire(CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        Mutex mutex = new(initiallyOwned: false, _name);
        Stopwatch stopwatch = Stopwatch.StartNew();
        try
        {
            while (stopwatch.Elapsed < MaximumWait)
            {
                cancellationToken.ThrowIfCancellationRequested();
                try
                {
                    if (mutex.WaitOne(PollInterval))
                    {
                        return new MutexLease(mutex);
                    }
                }
                catch (AbandonedMutexException)
                {
                    return new MutexLease(mutex);
                }
            }

            mutex.Dispose();
            return null;
        }
        catch
        {
            mutex.Dispose();
            throw;
        }
    }

    private sealed class MutexLease(Mutex mutex) : IDisposable
    {
        private Mutex? _mutex = mutex;

        public void Dispose()
        {
            Mutex? current = Interlocked.Exchange(ref _mutex, null);
            if (current is null)
            {
                return;
            }

            try
            {
                current.ReleaseMutex();
            }
            finally
            {
                current.Dispose();
            }
        }
    }
}
