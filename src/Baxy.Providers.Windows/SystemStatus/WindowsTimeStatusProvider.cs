namespace Baxy.Providers.Windows.SystemStatus;

public sealed record TimeStatusSnapshot(DateTimeOffset UtcNow, int LocalUtcOffsetMinutes);

public interface ITimeStatusProvider
{
    ValueTask<TimeStatusSnapshot?> ReadVerifiedAsync(CancellationToken cancellationToken);
}

public sealed class WindowsTimeStatusProvider : ITimeStatusProvider
{
    private readonly ITimeStatusProbe _probe;
    private readonly WindowsTimeStatusVerifier _verifier;

    public WindowsTimeStatusProvider() : this(new SystemTimeStatusProbe()) { }

    internal WindowsTimeStatusProvider(ITimeStatusProbe probe)
    {
        _probe = probe ?? throw new ArgumentNullException(nameof(probe));
        _verifier = new WindowsTimeStatusVerifier(probe);
    }

    public ValueTask<TimeStatusSnapshot?> ReadVerifiedAsync(CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        TimeStatusSnapshot first = _probe.Read();
        cancellationToken.ThrowIfCancellationRequested();
        return ValueTask.FromResult(_verifier.Verify(first) ? first : null);
    }
}

internal sealed class WindowsTimeStatusVerifier(ITimeStatusProbe probe)
{
    public bool Verify(TimeStatusSnapshot supplied)
    {
        TimeStatusSnapshot observed = probe.Read();
        TimeSpan elapsed = observed.UtcNow - supplied.UtcNow;
        return supplied.UtcNow.Offset == TimeSpan.Zero
            && observed.UtcNow.Offset == TimeSpan.Zero
            && elapsed >= TimeSpan.Zero
            && elapsed <= TimeSpan.FromSeconds(2)
            && supplied.LocalUtcOffsetMinutes == observed.LocalUtcOffsetMinutes
            && supplied.LocalUtcOffsetMinutes is >= -14 * 60 and <= 14 * 60;
    }
}

internal interface ITimeStatusProbe { TimeStatusSnapshot Read(); }

// Renew al máximo (w8): TimeZoneInfo.Local is read once per process and kept; BAXY runs for days, so a zone changed
// while it runs (by hand, or set automatically on a trip) kept the old offset. The zone is read afresh on each read.
internal sealed class SystemTimeStatusProbe(Func<TimeZoneInfo> localZone) : ITimeStatusProbe
{
    public SystemTimeStatusProbe()
        : this(static () =>
        {
            TimeZoneInfo.ClearCachedData();
            return TimeZoneInfo.Local;
        })
    {
    }

    public TimeStatusSnapshot Read()
    {
        DateTimeOffset utc = DateTimeOffset.UtcNow;
        int offset = checked((int)localZone().GetUtcOffset(utc).TotalMinutes);
        return new TimeStatusSnapshot(utc, offset);
    }
}
