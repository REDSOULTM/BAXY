namespace Baxy.Installer;

/// <summary>What the person's Pause holds: the work awaits it between reads, and a closed connection resumes by range.</summary>
internal sealed class PauseGate
{
    private readonly object sync = new();
    private TaskCompletionSource? paused;

    internal bool IsPaused
    {
        get
        {
            lock (sync)
            {
                return paused is not null;
            }
        }
    }

    internal void Pause()
    {
        lock (sync)
        {
            paused ??= new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        }
    }

    internal void Resume()
    {
        lock (sync)
        {
            paused?.TrySetResult();
            paused = null;
        }
    }

    internal Task WaitAsync(CancellationToken cancellation)
    {
        lock (sync)
        {
            return paused is null ? Task.CompletedTask : paused.Task.WaitAsync(cancellation);
        }
    }
}
