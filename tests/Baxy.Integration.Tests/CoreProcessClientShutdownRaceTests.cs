using System.Diagnostics;
using System.Reflection;
using System.Text.Json.Nodes;
using Baxy.App;
using Baxy.Contracts;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Deterministic shutdown races on the local core client: closing BAXY while the
/// engine is still handshaking, closing it twice, and asking it to work after it
/// is gone. Each case must end in a stated failure rather than a hang or a
/// silently swallowed request.
/// </summary>
[TestFixture]
public sealed class CoreProcessClientShutdownRaceTests
{
    [Test]
    public async Task ShutdownDuringSpawnFailsTheHandshakeInsteadOfHanging()
    {
        var client = new CoreProcessClient();
        // The handshake completion is the spawn window: the process exists but
        // has not greeted yet. Closing here must not leave a caller waiting.
        var handshake = new TaskCompletionSource<ProtocolHello>(
            TaskCreationOptions.RunContinuationsAsynchronously);
        SetPrivateField(client, "_helloCompletion", handshake);
        SetPrivateField(client, "_started", true);

        await client.DisposeAsync();

        IOException? observed = null;
        try
        {
            _ = await handshake.Task.WaitAsync(TimeSpan.FromSeconds(5));
        }
        catch (IOException exception)
        {
            observed = exception;
        }

        Assert.Multiple(() =>
        {
            Assert.That(observed, Is.Not.Null);
            Assert.That(observed!.Message, Does.Contain("cerró"));
            Assert.That(client.IsReady, Is.False);
        });
    }

    [Test]
    public async Task RepeatedShutdownIsIdempotentAndKeepsRejectingWork()
    {
        var client = new CoreProcessClient();
        using Process currentProcess = Process.GetCurrentProcess();
        SetPrivateField(client, "_process", currentProcess);
        SetPrivateField(client, "_ready", true);
        SetPrivateField<Process?>(client, "_process", null);

        await client.DisposeAsync();
        await client.DisposeAsync();
        await client.DisposeAsync();

        var routed = new RoutedOperation(
            "note.create",
            new JsonObject { ["title"] = "Una", ["content"] = "sola" });
        string outbox = Path.Combine(
            Path.GetTempPath(),
            "baxy-shutdown-race-tests",
            Guid.NewGuid().ToString("N"),
            "retry-outbox.v1.json");
        PreparedOperation prepared = new RetryableOperationRegistry(outbox).GetOrAdd(routed);

        try
        {
            Assert.Multiple(() =>
            {
                Assert.That(client.IsReady, Is.False);
                // A disposed client must name its own state, not fail later as
                // an unrelated protocol or IO error.
                Assert.That(
                    async () => await client.SendOperationAsync(
                        prepared,
                        TimeSpan.FromSeconds(1),
                        CancellationToken.None),
                    Throws.TypeOf<ObjectDisposedException>());
            });
        }
        finally
        {
            string? directory = Path.GetDirectoryName(outbox);
            if (directory is not null && Directory.Exists(directory))
            {
                Directory.Delete(directory, recursive: true);
            }
        }
    }

    private static void SetPrivateField<T>(CoreProcessClient client, string name, T value)
    {
        FieldInfo field = typeof(CoreProcessClient).GetField(
            name,
            BindingFlags.Instance | BindingFlags.NonPublic) ??
            throw new InvalidOperationException($"El campo {name} no existe.");
        field.SetValue(client, value);
    }
}
