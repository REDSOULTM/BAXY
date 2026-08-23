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
                    Assert.That(summary, Does.Contain("system.status"));
                    Assert.That(summary, Does.Contain("\"memory\""));
                    Assert.That(summary, Does.Contain("\"cpu\""));
                    Assert.That(summary, Does.Not.Contain("\"disk\""));
                    Assert.That(summary, Does.Not.Contain("\"battery\""));
                });

                string memory = await SubmitAsync(viewModel, "cuánta RAM tengo");
                Assert.That(memory, Does.Contain("system.status"));

                string disk = await SubmitAsync(viewModel, "how much disk space is left");
                Assert.That(disk, Does.Contain("system.status"));

                string battery = await SubmitAsync(viewModel, "battery status");
                Assert.That(battery, Does.Contain("system.status"));

                string operatingSystem = await SubmitAsync(
                    viewModel,
                    "qué versión de Windows tengo");
                Assert.That(operatingSystem, Does.Contain("system.status"));

                Assert.That(
                    viewModel.Messages.Where(static message => !message.IsUser),
                    Has.None.Matches<ConversationMessage>(static message =>
                        (message.Body.TrimStart().StartsWith('{')
                            && !UserMessagePolicy.IsStructuredFacts(message.Body))
                        || message.Body.TrimStart().StartsWith('[')));
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
