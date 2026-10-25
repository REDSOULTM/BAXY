using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// The rail's sampler at shutdown: the window disposes it while a reading may still be under way, and that reading
/// released the lock DisposeAsync had already disposed (ObjectDisposedException from a reading nobody waits for).
/// </summary>
[TestFixture]
public sealed class FieldTelemetrySamplerTests
{
    [Test]
    public async Task AReadingUnderWayWhenTheSamplerIsDisposedEndsWithoutFailing()
    {
        var measuring = new TaskCompletionSource<FieldMetricSnapshot>(TaskCreationOptions.RunContinuationsAsynchronously);
        var sampler = new FieldTelemetrySampler(static () => null, _ => measuring.Task);

        Task<FieldMetricSnapshot> reading = sampler.SampleAsync(CancellationToken.None);
        await sampler.DisposeAsync();
        measuring.SetResult(new FieldMetricSnapshot(1, 2, 3, 4, 5));

        Assert.That((await reading).Cpu, Is.EqualTo(1));
        Assert.ThrowsAsync<ObjectDisposedException>(() => sampler.SampleAsync(CancellationToken.None));
    }
}
