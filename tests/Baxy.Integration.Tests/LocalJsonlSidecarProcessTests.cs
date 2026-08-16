using System.Diagnostics;
using System.Reflection;
using System.Text;
using System.Text.Json;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
[NonParallelizable]
public sealed class LocalJsonlSidecarProcessTests
{
    [Test]
    public async Task Utf8WriterPreservesExactJsonlFramingAndFlushesEachMessage()
    {
        await using var stream = new FlushTrackingStream();
        byte[] first = Encoding.UTF8.GetBytes("{\"type\":\"uno\",\"text\":\"caf\u00e9\"}");
        byte[] second = "{\"type\":\"dos\"}"u8.ToArray();

        await LocalJsonlSidecarProcess.WriteUtf8LineAsync(
            stream,
            first,
            CancellationToken.None);
        await LocalJsonlSidecarProcess.WriteUtf8LineAsync(
            stream,
            second,
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(
                stream.ToArray(),
                Is.EqualTo(
                    Encoding.UTF8.GetBytes(
                        "{\"type\":\"uno\",\"text\":\"caf\u00e9\"}\n" +
                        "{\"type\":\"dos\"}\n")));
            Assert.That(stream.FlushCalls, Is.EqualTo(2));
            Assert.That(
                first,
                Is.EqualTo(Encoding.UTF8.GetBytes("{\"type\":\"uno\",\"text\":\"caf\u00e9\"}")));
        });
    }

    [Test]
    public void Utf8WriterHonorsCancellationBeforePublishingAnyBytes()
    {
        using var stream = new FlushTrackingStream();
        using var cancellation = new CancellationTokenSource();
        cancellation.Cancel();

        Assert.That(
            async () => await LocalJsonlSidecarProcess.WriteUtf8LineAsync(
                stream,
                "{}"u8.ToArray(),
                cancellation.Token),
            Throws.InstanceOf<OperationCanceledException>());
        Assert.Multiple(() =>
        {
            Assert.That(stream.Length, Is.Zero);
            Assert.That(stream.FlushCalls, Is.Zero);
        });
    }

    [Test]
    public void CoreClientUsesTheReusableSidecarHost()
    {
        Type[] privateFieldTypes = typeof(CoreProcessClient)
            .GetFields(BindingFlags.Instance | BindingFlags.NonPublic)
            .Select(static field => field.FieldType)
            .ToArray();

        Assert.That(privateFieldTypes, Does.Contain(typeof(LocalJsonlSidecarProcess)));
    }

    [Test]
    public async Task DefectiveStandardErrorReadCannotMakePumpReapUnbounded()
    {
        var neverCompletes = new TaskCompletionSource<bool>(
            TaskCreationOptions.RunContinuationsAsynchronously);
        int closeCalls = 0;
        Stopwatch elapsed = Stopwatch.StartNew();

        bool reaped = await LocalJsonlSidecarProcess.ReapPumpWithinAsync(
            neverCompletes.Task,
            () => closeCalls++,
            TimeSpan.FromMilliseconds(20));

        Assert.Multiple(() =>
        {
            Assert.That(reaped, Is.False);
            Assert.That(closeCalls, Is.EqualTo(1));
            Assert.That(neverCompletes.Task.IsCompleted, Is.False);
            Assert.That(elapsed.Elapsed, Is.LessThan(TimeSpan.FromSeconds(2)));
        });
    }

    [Test]
    public async Task ConfigurableHostRunsIndependentCoreAndModelJsonlSidecarsUnderJobs()
    {
        string powershell = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.Windows),
            "System32",
            "WindowsPowerShell",
            "v1.0",
            "powershell.exe");
        Assert.That(File.Exists(powershell), Is.True);
        const string fixture =
            "$hello=[ordered]@{type='fixture.hello';kind=$env:BAXY_FIXTURE_KIND;pid=$PID};" +
            "[Console]::Out.WriteLine(($hello|ConvertTo-Json -Compress));" +
            "[Console]::Out.Flush();Start-Sleep -Seconds 30";

        LocalJsonlSidecarProcess? core = null;
        LocalJsonlSidecarProcess? model = null;
        try
        {
            core = StartFixture("core", powershell, fixture);
            model = StartFixture("model-python", powershell, fixture);

            await AssertHelloAsync(core, "core");
            await AssertHelloAsync(model, "model-python");
            Assert.That(model.Process.Id, Is.Not.EqualTo(core.Process.Id));

            await core.StopAsync();
            await model.StopAsync();
            Assert.Multiple(() =>
            {
                Assert.That(core.Process.HasExited, Is.True);
                Assert.That(model.Process.HasExited, Is.True);
                Assert.That(core.IsStandardErrorPumpCompleted, Is.True);
                Assert.That(model.IsStandardErrorPumpCompleted, Is.True);
            });
        }
        finally
        {
            if (core is not null)
            {
                await core.DisposeAsync();
            }

            if (model is not null)
            {
                await model.DisposeAsync();
            }
        }
    }

    [Test]
    public async Task StandardErrorPumpAllowsHelloAfterMoreThanPipeCapacity()
    {
        string powershell = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.Windows),
            "System32",
            "WindowsPowerShell",
            "v1.0",
            "powershell.exe");
        Assert.That(File.Exists(powershell), Is.True);
        const string fixture =
            "$chunk='x'*4096;" +
            "for($i=0;$i -lt 512;$i++){[Console]::Error.Write($chunk)};" +
            "[Console]::Error.Flush();" +
            "$hello=[ordered]@{type='fixture.hello';kind=$env:BAXY_FIXTURE_KIND;pid=$PID};" +
            "[Console]::Out.WriteLine(($hello|ConvertTo-Json -Compress));" +
            "[Console]::Out.Flush();Start-Sleep -Seconds 30";
        LocalJsonlSidecarProcess? sidecar = null;
        try
        {
            sidecar = StartFixture("stderr-before-hello", powershell, fixture);

            await AssertHelloAsync(sidecar, "stderr-before-hello");
            Assert.That(
                sidecar.StandardErrorBytesObserved,
                Is.GreaterThan(512L * 1024L));

            await sidecar.StopAsync();
            Assert.That(sidecar.IsStandardErrorPumpCompleted, Is.True);
        }
        finally
        {
            if (sidecar is not null)
            {
                await sidecar.DisposeAsync();
            }
        }
    }

    private static LocalJsonlSidecarProcess StartFixture(
        string kind,
        string powershell,
        string fixture)
    {
        var definition = new LocalJsonlSidecarDefinition(
            kind,
            powershell,
            Path.GetDirectoryName(powershell)!,
            ["-NoLogo", "-NoProfile", "-NonInteractive", "-Command", fixture],
            new Dictionary<string, string>(StringComparer.Ordinal)
            {
                ["BAXY_FIXTURE_KIND"] = kind,
            });
        return LocalJsonlSidecarProcess.Start(definition);
    }

    private static async Task AssertHelloAsync(
        LocalJsonlSidecarProcess sidecar,
        string expectedKind)
    {
        var reader = new BoundedUtf8LineReader(sidecar.Process.StandardOutput.BaseStream, 4096);
        using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(10));
        BoundedUtf8Line? line = await reader.ReadAsync(timeout.Token);
        Assert.That(line, Is.Not.Null);
        Assert.That(line!.Value.TooLarge, Is.False);
        using JsonDocument document = JsonDocument.Parse(line.Value.Utf8!);
        JsonElement root = document.RootElement;
        Assert.Multiple(() =>
        {
            Assert.That(root.GetProperty("type").GetString(), Is.EqualTo("fixture.hello"));
            Assert.That(root.GetProperty("kind").GetString(), Is.EqualTo(expectedKind));
            Assert.That(root.GetProperty("pid").GetInt32(), Is.EqualTo(sidecar.Process.Id));
        });
    }

    private sealed class FlushTrackingStream : MemoryStream
    {
        internal int FlushCalls { get; private set; }

        public override Task FlushAsync(CancellationToken cancellationToken)
        {
            FlushCalls++;
            return base.FlushAsync(cancellationToken);
        }
    }
}
