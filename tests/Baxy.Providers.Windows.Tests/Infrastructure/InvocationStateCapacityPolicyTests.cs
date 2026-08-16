using Baxy.Providers.Windows.Applications;
using Baxy.Providers.Windows.Audio;
using Baxy.Providers.Windows.Infrastructure;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests.Infrastructure;

[TestFixture]
internal sealed class InvocationStateCapacityPolicyTests
{
    private string _stateDirectory = null!;

    [SetUp]
    public void SetUp()
    {
        _stateDirectory = Path.Combine(
            Path.GetTempPath(),
            $"baxy-invocation-capacity-{Guid.NewGuid():N}");
        Directory.CreateDirectory(_stateDirectory);
    }

    [TearDown]
    public void TearDown()
    {
        try
        {
            Directory.Delete(_stateDirectory, recursive: true);
        }
        catch (IOException)
        {
        }
        catch (UnauthorizedAccessException)
        {
        }
    }

    [Test]
    public void CountsEveryTopLevelJsonAndIgnoresOtherEntries()
    {
        File.WriteAllBytes(Path.Combine(_stateDirectory, "capacity.json"), new byte[4]);
        File.WriteAllBytes(Path.Combine(_stateDirectory, "ignored.tmp"), new byte[100]);
        string nestedDirectory = Path.Combine(_stateDirectory, "nested");
        Directory.CreateDirectory(nestedDirectory);
        File.WriteAllBytes(Path.Combine(nestedDirectory, "nested.json"), new byte[100]);
        string targetPath = Path.Combine(_stateDirectory, "target.json");

        InvocationStateCapacityViolation accepted = Evaluate(
            targetPath,
            replacementBytes: 4,
            maximumInvocationCount: 2,
            maximumTotalStateBytes: 8);
        InvocationStateCapacityViolation countRejected = Evaluate(
            targetPath,
            replacementBytes: 4,
            maximumInvocationCount: 1,
            maximumTotalStateBytes: 8);
        InvocationStateCapacityViolation bytesRejected = Evaluate(
            targetPath,
            replacementBytes: 4,
            maximumInvocationCount: 2,
            maximumTotalStateBytes: 7);

        Assert.Multiple(() =>
        {
            Assert.That(accepted, Is.EqualTo(InvocationStateCapacityViolation.None));
            Assert.That(
                countRejected,
                Is.EqualTo(InvocationStateCapacityViolation.Capacity));
            Assert.That(
                bytesRejected,
                Is.EqualTo(InvocationStateCapacityViolation.Capacity));
        });
    }

    [Test]
    public void ReplacementSubtractsTheExistingLengthAndDoesNotAddAnEntry()
    {
        string targetPath = Path.Combine(_stateDirectory, "target.json");
        File.WriteAllBytes(targetPath, new byte[8]);
        File.WriteAllBytes(Path.Combine(_stateDirectory, "other.json"), new byte[2]);

        InvocationStateCapacityViolation accepted = Evaluate(
            targetPath,
            replacementBytes: 3,
            maximumInvocationCount: 2,
            maximumTotalStateBytes: 10);
        InvocationStateCapacityViolation rejected = Evaluate(
            targetPath,
            replacementBytes: 9,
            maximumInvocationCount: 2,
            maximumTotalStateBytes: 10);

        Assert.Multiple(() =>
        {
            Assert.That(accepted, Is.EqualTo(InvocationStateCapacityViolation.None));
            Assert.That(rejected, Is.EqualTo(InvocationStateCapacityViolation.Capacity));
        });
    }

    [Test]
    public void ZeroLengthTargetStillCountsAsAnExistingEntry()
    {
        string targetPath = Path.Combine(_stateDirectory, "target.json");
        File.WriteAllBytes(targetPath, []);

        InvocationStateCapacityViolation result = Evaluate(
            targetPath,
            replacementBytes: 1,
            maximumInvocationCount: 1,
            maximumTotalStateBytes: 1);

        Assert.That(result, Is.EqualTo(InvocationStateCapacityViolation.None));
    }

    [Test]
    public void RechecksAnExternallyResizedJsonOnEveryEvaluation()
    {
        string fillerPath = Path.Combine(_stateDirectory, "capacity.json");
        File.WriteAllBytes(fillerPath, new byte[4]);
        string targetPath = Path.Combine(_stateDirectory, "target.json");

        InvocationStateCapacityViolation beforeResize = Evaluate(
            targetPath,
            replacementBytes: 4,
            maximumInvocationCount: 2,
            maximumTotalStateBytes: 8);
        using (FileStream stream = new(
            fillerPath,
            FileMode.Open,
            FileAccess.Write,
            FileShare.None))
        {
            stream.SetLength(5);
            stream.Flush(flushToDisk: true);
        }

        InvocationStateCapacityViolation afterResize = Evaluate(
            targetPath,
            replacementBytes: 4,
            maximumInvocationCount: 2,
            maximumTotalStateBytes: 8);

        Assert.Multiple(() =>
        {
            Assert.That(beforeResize, Is.EqualTo(InvocationStateCapacityViolation.None));
            Assert.That(afterResize, Is.EqualTo(InvocationStateCapacityViolation.Capacity));
        });
    }

    [Test]
    public void RejectsAnAlreadyOverCapacityDirectoryBeforeProjection()
    {
        File.WriteAllBytes(Path.Combine(_stateDirectory, "capacity.json"), new byte[9]);

        InvocationStateCapacityViolation result = Evaluate(
            Path.Combine(_stateDirectory, "target.json"),
            replacementBytes: 0,
            maximumInvocationCount: 2,
            maximumTotalStateBytes: 8);

        Assert.That(result, Is.EqualTo(InvocationStateCapacityViolation.Capacity));
    }

    [TestCase(-1L, 1, 1L, "replacementBytes")]
    [TestCase(0L, -1, 1L, "maximumInvocationCount")]
    [TestCase(0L, 1, -1L, "maximumTotalStateBytes")]
    public void RejectsNegativeNumericParameters(
        long replacementBytes,
        int maximumInvocationCount,
        long maximumTotalStateBytes,
        string expectedParameterName)
    {
        ArgumentOutOfRangeException? exception =
            Assert.Throws<ArgumentOutOfRangeException>(() => Evaluate(
                Path.Combine(_stateDirectory, "target.json"),
                replacementBytes,
                maximumInvocationCount,
                maximumTotalStateBytes));

        Assert.That(exception!.ParamName, Is.EqualTo(expectedParameterName));
    }

    [Test]
    public void JsonReparsePointIsReportedAndTranslatedByBothStores()
    {
        string targetDirectory = Path.Combine(_stateDirectory, "target");
        string targetPath = Path.Combine(targetDirectory, "outside.txt");
        string linkPath = Path.Combine(_stateDirectory, "linked.json");
        const string sentinel = "outside sentinel";
        Directory.CreateDirectory(targetDirectory);
        File.WriteAllText(targetPath, sentinel);

        _ = Baxy.Tests.NtfsTestJunction.Create(linkPath, targetDirectory);

        try
        {
            InvocationStateCapacityViolation violation = Evaluate(
                Path.Combine(_stateDirectory, "target.json"),
                replacementBytes: 1,
                maximumInvocationCount: 2,
                maximumTotalStateBytes: 1024);
            var applicationState = new ApplicationInvocationState(
                Guid.NewGuid().ToString("D"),
                ApplicationIds.Notepad,
                DateTime.UtcNow.Ticks,
                [],
                Receipt: null);
            var audioState = new AudioInvocationState(
                Guid.NewGuid().ToString("D"),
                AudioOperationIds.Volume,
                AudioTargetIds.DefaultOutput,
                new string('a', 64),
                RequestedLevel: 30,
                RequestedState: null,
                new AudioEndpointState(50, false),
                BaselineVolumeScalar: 0.5f,
                DateTime.UtcNow.Ticks,
                Receipt: null,
                FinalVolumeScalar: null);
            var applicationStore = new ApplicationInvocationStore(_stateDirectory);
            var audioStore = new AudioInvocationStore(_stateDirectory);

            ApplicationStateCorruptException? applicationException =
                Assert.Throws<ApplicationStateCorruptException>(
                    () => applicationStore.EnsureCompletionCapacity(applicationState));
            AudioStateCorruptException? audioException =
                Assert.Throws<AudioStateCorruptException>(
                    () => audioStore.EnsureCompletionCapacity(audioState));

            Assert.Multiple(() =>
            {
                Assert.That(
                    violation,
                    Is.EqualTo(InvocationStateCapacityViolation.ReparsePoint));
                Assert.That(
                    applicationException!.Message,
                    Is.EqualTo("A durable invocation entry is a reparse point."));
                Assert.That(
                    audioException!.Message,
                    Is.EqualTo("A durable invocation entry is a reparse point."));
                Assert.That(File.ReadAllText(targetPath), Is.EqualTo(sentinel));
            });
        }
        finally
        {
            Directory.Delete(linkPath);
        }
    }

    private InvocationStateCapacityViolation Evaluate(
        string targetPath,
        long replacementBytes,
        int maximumInvocationCount,
        long maximumTotalStateBytes) =>
        InvocationStateCapacityPolicy.Evaluate(
            _stateDirectory,
            targetPath,
            replacementBytes,
            maximumInvocationCount,
            maximumTotalStateBytes);
}
