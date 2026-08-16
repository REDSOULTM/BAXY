using System.Diagnostics;
using System.Text.Json;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
[NonParallelizable]
public sealed class NaturalSystemStatusViewModelEndToEndTests
{
    [Test]
    public async Task NaturalConversationReadsVerifiedWindowsMetricsWithoutJsonOrResidualOutbox()
    {
        string root = PrivateDataRootTestSupport.NewPath("system-status-e2e");
        string? previousDataRoot = Environment.GetEnvironmentVariable("BAXY_DATA_DIR");
        Environment.SetEnvironmentVariable("BAXY_DATA_DIR", root);

        try
        {
            await using (var viewModel = new MainWindowViewModel(
                static route => route.ResolveStandaloneOperation()))
            {
                await viewModel.InitializeAsync(CancellationToken.None);
                Assert.That(viewModel.IsReady, Is.True);

                string summary = await SubmitAsync(viewModel, "revisa RAM y CPU");
                Assert.Multiple(() =>
                {
                    Assert.That(summary, Does.StartWith("CPU"));
                    Assert.That(summary, Does.Contain("RAM:"));
                    Assert.That(summary, Does.Not.Contain("Disco del sistema:"));
                    Assert.That(summary, Does.Not.Contain("Batería:"));
                    Assert.That(summary, Does.Not.Contain("Windows "));
                    Assert.That(summary, Does.Not.Contain("Tiempo activo:"));
                });

                string memory = await SubmitAsync(viewModel, "cuánta RAM tengo");
                Assert.That(memory, Does.StartWith("RAM:"));

                string disk = await SubmitAsync(viewModel, "how much disk space is left");
                Assert.That(disk, Does.StartWith("Disco del sistema:"));

                string battery = await SubmitAsync(viewModel, "battery status");
                Assert.That(
                    battery.StartsWith("Batería:", StringComparison.Ordinal)
                    || battery.StartsWith("Este equipo no informa una batería", StringComparison.Ordinal)
                    || battery.StartsWith("Windows no confirmó si hay una batería", StringComparison.Ordinal),
                    Is.True,
                    battery);

                string operatingSystem = await SubmitAsync(
                    viewModel,
                    "qué versión de Windows tengo");
                Assert.That(operatingSystem, Does.StartWith("Windows "));

                Assert.That(
                    viewModel.Messages.Where(static message => !message.IsUser),
                    Has.None.Matches<ConversationMessage>(static message =>
                        message.Body.TrimStart().StartsWith('{')
                        || message.Body.TrimStart().StartsWith('[')
                        || message.Body.Contains("system.status", StringComparison.Ordinal)));
            }

            string outboxPath = Path.Combine(root, "shell", "retry-outbox.v1.json");
            using JsonDocument outbox = JsonDocument.Parse(await File.ReadAllTextAsync(outboxPath));
            Assert.That(outbox.RootElement.GetProperty("entries").GetArrayLength(), Is.Zero);
        }
        finally
        {
            Environment.SetEnvironmentVariable("BAXY_DATA_DIR", previousDataRoot);
            if (Directory.Exists(root))
            {
                Directory.Delete(root, recursive: true);
            }
        }
    }

    private static async Task<string> SubmitAsync(
        MainWindowViewModel viewModel,
        string text)
    {
        int previousCount = viewModel.Messages.Count;
        viewModel.Draft = text;
        var stopwatch = Stopwatch.StartNew();
        await viewModel.SubmitAsync(CancellationToken.None);
        stopwatch.Stop();

        ConversationMessage[] added = viewModel.Messages.Skip(previousCount).ToArray();
        Assert.Multiple(() =>
        {
            Assert.That(stopwatch.Elapsed, Is.LessThan(TimeSpan.FromSeconds(4)), text);
            Assert.That(added, Has.Length.EqualTo(2));
            Assert.That(added[0].IsUser, Is.True);
            Assert.That(added[0].Body, Is.EqualTo(text));
            Assert.That(added[1].IsUser, Is.False);
            Assert.That(added[1].Speaker, Is.EqualTo("BAXY"));
            Assert.That(added[1].AccessibleText, Is.EqualTo($"BAXY: {added[1].Body}"));
        });
        return added[1].Body;
    }
}
