using System.Diagnostics;
using System.Reflection;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.App;
using Baxy.Contracts;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class CoreProcessClientTimeoutTests
{
    [TestCase(
        "{\"nested\":{\"type\":\"wrong\"},\"type\":\"operation.response\"}",
        "operation.response")]
    [TestCase("{\"ty\\u0070e\":\"hello\"}", "hello")]
    [TestCase(
        "{\"type\":\"hello\",\"type\":\"operation.response\"}",
        "operation.response")]
    [TestCase("{\"type\":1}", null)]
    [TestCase("[]", null)]
    public void ProtocolEnvelopeTypeScannerPreservesJsonObjectSemantics(
        string json,
        string? expected)
    {
        string? actual = CoreProcessClient.ReadProtocolMessageType(
            Encoding.UTF8.GetBytes(json));

        Assert.That(actual, Is.EqualTo(expected));
    }

    [Test]
    public void ProtocolEnvelopeTypeScannerValidatesTheCompleteFrame()
    {
        Assert.That(
            () => CoreProcessClient.ReadProtocolMessageType(
                "{\"type\":\"hello\"} {}"u8),
            Throws.InstanceOf<JsonException>());
        Assert.That(
            () => CoreProcessClient.ReadProtocolMessageType(
                "[] {}"u8),
            Throws.InstanceOf<JsonException>());
        Assert.That(
            () => CoreProcessClient.ReadProtocolMessageType(
                "[{}"u8),
            Throws.InstanceOf<JsonException>());
    }

    [Test]
    public async Task LateTerminalResponseIsReconciledWithoutDisconnectingTheCore()
    {
        var client = new CoreProcessClient();
        using Process currentProcess = Process.GetCurrentProcess();
        SetPrivateField(client, "_process", currentProcess);
        SetPrivateField(client, "_ready", true);
        int disconnectCount = 0;
        client.Disconnected += () => disconnectCount++;
        var response = new OperationResponse(
            ProtocolTypes.OperationResponse,
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            OperationStatuses.Completed,
            "Completed.",
            true,
            false,
            null,
            null);
        Task<OperationResponse> lateResponse = Task.Run(async () =>
        {
            await Task.Delay(40);
            return response;
        });

        try
        {
            OperationResponse observed = await client.AwaitResponseWithReconciliationAsync(
                lateResponse,
                TimeSpan.FromMilliseconds(10),
                TimeSpan.FromMilliseconds(200),
                CancellationToken.None);

            Assert.Multiple(() =>
            {
                Assert.That(observed, Is.SameAs(response));
                Assert.That(client.IsReady, Is.True);
                Assert.That(disconnectCount, Is.Zero);
            });
        }
        finally
        {
            SetPrivateField<Process?>(client, "_process", null);
            await client.DisposeAsync();
        }
    }

    [Test]
    public async Task UnreconciledTimeoutDisconnectsOnceRejectsFurtherSendsAndKeepsRetryIdentity()
    {
        string root = Path.Combine(
            Path.GetTempPath(),
            "baxy-timeout-tests",
            Guid.NewGuid().ToString("N"));
        string outbox = Path.Combine(root, "shell", "retry-outbox.v1.json");
        var routed = new RoutedOperation(
            "note.create",
            new JsonObject { ["title"] = "Una", ["content"] = "sola" });
        PreparedOperation prepared = new RetryableOperationRegistry(outbox).GetOrAdd(routed);
        var client = new CoreProcessClient();
        using Process currentProcess = Process.GetCurrentProcess();
        SetPrivateField(client, "_process", currentProcess);
        SetPrivateField(client, "_ready", true);
        int disconnectCount = 0;
        client.Disconnected += () => disconnectCount++;

        try
        {
            Assert.That(client.IsReady, Is.True);

            var never = new TaskCompletionSource<OperationResponse>(
                TaskCreationOptions.RunContinuationsAsynchronously);
            TimeoutException? timeout = null;
            try
            {
                _ = await client.AwaitResponseWithReconciliationAsync(
                    never.Task,
                    TimeSpan.FromMilliseconds(10),
                    TimeSpan.FromMilliseconds(10),
                    CancellationToken.None);
            }
            catch (TimeoutException observed)
            {
                timeout = observed;
            }
            PreparedOperation afterRestart = new RetryableOperationRegistry(outbox).GetOrAdd(routed);

            Assert.Multiple(() =>
            {
                Assert.That(timeout, Is.Not.Null);
                Assert.That(timeout!.Message, Does.Contain("tiempo"));
                Assert.That(client.IsReady, Is.False);
                Assert.That(disconnectCount, Is.EqualTo(1));
                Assert.That(afterRestart.MissionId, Is.EqualTo(prepared.MissionId));
                Assert.That(afterRestart.InvocationId, Is.EqualTo(prepared.InvocationId));
                Assert.That(
                    async () => await client.SendOperationAsync(
                        prepared,
                        TimeSpan.FromSeconds(1),
                        CancellationToken.None),
                    Throws.TypeOf<InvalidOperationException>());
            });
        }
        finally
        {
            SetPrivateField<Process?>(client, "_process", null);
            await client.DisposeAsync();
            if (Directory.Exists(root))
            {
                Directory.Delete(root, recursive: true);
            }
        }
    }

    [Test]
    public async Task StartedProcessWithoutAJobExitsWhenTheClientCleansUp()
    {
        var startInfo = new ProcessStartInfo
        {
            FileName = "powershell.exe",
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardInput = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
        };
        startInfo.ArgumentList.Add("-NoProfile");
        startInfo.ArgumentList.Add("-NonInteractive");
        startInfo.ArgumentList.Add("-Command");
        startInfo.ArgumentList.Add("$null = [Console]::In.ReadToEnd()");
        var child = new Process { StartInfo = startInfo };
        Assert.That(child.Start(), Is.True);
        using Process observer = Process.GetProcessById(child.Id);
        var client = new CoreProcessClient();
        SetPrivateField(client, "_process", child);

        try
        {
            await client.DisposeAsync();
            await observer.WaitForExitAsync().WaitAsync(TimeSpan.FromSeconds(5));
            Assert.That(observer.HasExited, Is.True);
        }
        finally
        {
            if (!observer.HasExited)
            {
                observer.Kill(entireProcessTree: true);
                await observer.WaitForExitAsync();
            }

            child.Dispose();
        }
    }

    private static void SetPrivateField<T>(CoreProcessClient client, string name, T value)
    {
        FieldInfo? field = typeof(CoreProcessClient).GetField(
            name,
            BindingFlags.Instance | BindingFlags.NonPublic);
        Assert.That(field, Is.Not.Null, name);
        field!.SetValue(client, value);
    }
}
