using System.Diagnostics;
using System.Reflection;
using System.Text.Json;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
[NonParallelizable]
public sealed class PhysicalInstalledApplicationViewModelTests
{
    [TestCase("abre Steam", "Steam")]
    [TestCase(
        "abre notepad",
        "Bloc de notas",
        TestName = "ModelAuthoredNotepadAliasOpensThroughRealPipeline")]
    [TestCase("abre Bloc de notas", "Bloc de notas")]
    [TestCase("abre Discord si está instalado", "Discord")]
    [TestCase("abre Steam pero no maximices ni lances juegos", "Steam")]
    [Explicit("Abre y enfoca una aplicación real del menú Inicio de Windows.")]
    [Category("Physical")]
    public async Task HistoricalApplicationCommandOpensThroughTheRealPipelineUnderFourSeconds(
        string command,
        string expectedDisplayName)
    {
        string root = PrivateDataRootTestSupport.NewPath("physical-app-open-e2e");
        string tracePath = Path.Combine(root, "model-authored-app-open.jsonl");
        string? previousDataRoot = Environment.GetEnvironmentVariable("BAXY_DATA_DIR");
        bool previousCompositionBypass = UserMessagePolicy.BypassLlmCompositionForTests;
        Environment.SetEnvironmentVariable("BAXY_DATA_DIR", root);

        try
        {
            UserMessagePolicy.BypassLlmCompositionForTests = false;
            using (ShellTrace? trace = ShellTrace.TryCreate(tracePath))
            using (IDisposable traceScope = ShellTraceSink.Use(
                       trace
                       ?? throw new InvalidOperationException(
                           "The physical app-open test could not create its owned trace.")))
            {
                await using (var viewModel = new MainWindowViewModel())
                {
                    using var timeout = new CancellationTokenSource(TimeSpan.FromMinutes(3));
                    await viewModel.InitializeAsync(timeout.Token);
                    Assert.That(viewModel.IsReady, Is.True);
                    await WaitForMindAsync(viewModel, timeout.Token);

                    int previousCount = viewModel.Messages.Count;
                    viewModel.Draft = command;
                    var stopwatch = Stopwatch.StartNew();
                    await viewModel.SubmitAsync(timeout.Token);
                    stopwatch.Stop();

                    ConversationMessage[] assistantResponses = viewModel.Messages
                        .Skip(previousCount)
                        .Where(static message => !message.IsUser)
                        .ToArray();
                    Assert.That(
                        assistantResponses,
                        Has.Length.EqualTo(1),
                        $"composition_failure={viewModel.LastMessageCompositionFailure ?? "none"}");
                    ConversationMessage response = assistantResponses[0];
                    Assert.Multiple(() =>
                    {
                        Assert.That(response.Body, Does.Contain(expectedDisplayName).IgnoreCase);
                        Assert.That(
                            response.Body,
                            Does.Match(@"(?i)\b(?:abrí|enfoqué)\b"),
                            "The model-authored result lost BAXY's first-person action.");
                        Assert.That(stopwatch.Elapsed, Is.LessThan(TimeSpan.FromSeconds(4)));
                    });
                }
            }

            string[] stages = File.ReadLines(tracePath)
                .Select(static line => JsonDocument.Parse(line))
                .Select(static document =>
                {
                    using (document)
                    {
                        return document.RootElement.GetProperty("stage").GetString()
                            ?? string.Empty;
                    }
                })
                .ToArray();
            Assert.Multiple(() =>
            {
                Assert.That(stages, Does.Contain(ShellTraceStages.ComposeStart));
                Assert.That(stages, Does.Contain(ShellTraceStages.ComposeEnd));
            });
        }
        finally
        {
            UserMessagePolicy.BypassLlmCompositionForTests = previousCompositionBypass;
            Environment.SetEnvironmentVariable("BAXY_DATA_DIR", previousDataRoot);
            if (Directory.Exists(root))
            {
                Directory.Delete(root, recursive: true);
            }
        }
    }

    private static async Task WaitForMindAsync(
        MainWindowViewModel viewModel,
        CancellationToken cancellationToken)
    {
        FieldInfo mindField = typeof(MainWindowViewModel).GetField(
            "_mindClient",
            BindingFlags.Instance | BindingFlags.NonPublic)
            ?? throw new MissingFieldException(
                typeof(MainWindowViewModel).FullName,
                "_mindClient");
        while (mindField.GetValue(viewModel) is not MindSidecarClient { IsReady: true })
        {
            cancellationToken.ThrowIfCancellationRequested();
            if (viewModel.HasStartupError)
            {
                Assert.Fail("The shell reported a startup error before the mind became ready.");
            }

            await Task.Delay(TimeSpan.FromMilliseconds(100), cancellationToken);
        }
    }
}
