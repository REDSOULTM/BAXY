using System.Diagnostics;
using System.Globalization;
using System.Text.Json;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
[NonParallelizable]
public sealed class NaturalSystemTimeViewModelEndToEndTests
{
    [Test]
    public async Task InputStaysArmedWhileWelcomeWaitsForMind()
    {
        bool previousBypass = UserMessagePolicy.BypassLlmCompositionForTests;
        UserMessagePolicy.BypassLlmCompositionForTests = false;
        string root = PrivateDataRootTestSupport.NewPath("system-time-input");
        string? previousDataRoot = Environment.GetEnvironmentVariable("BAXY_DATA_DIR");
        Environment.SetEnvironmentVariable("BAXY_DATA_DIR", root);
        try
        {
            await using var viewModel = new MainWindowViewModel(
                static route => route.ResolveStandaloneOperation());
            await viewModel.InitializeAsync(CancellationToken.None);
            Assert.Multiple(() =>
            {
                Assert.That(viewModel.IsReady, Is.True);
                Assert.That(viewModel.IsInputEnabled, Is.True);
            });
        }
        finally
        {
            UserMessagePolicy.BypassLlmCompositionForTests = previousBypass;
            Environment.SetEnvironmentVariable("BAXY_DATA_DIR", previousDataRoot);
            if (Directory.Exists(root))
            {
                Directory.Delete(root, recursive: true);
            }
        }
    }

    [Test]
    public async Task NaturalTimeQueryReturnsVerifiedLocalTimeUnderFourSeconds()
    {
        string root = PrivateDataRootTestSupport.NewPath("system-time-e2e");
        string? previousDataRoot = Environment.GetEnvironmentVariable("BAXY_DATA_DIR");
        Environment.SetEnvironmentVariable("BAXY_DATA_DIR", root);

        try
        {
            await using var viewModel = new MainWindowViewModel(
                static route => route.ResolveStandaloneOperation());
            await viewModel.InitializeAsync(CancellationToken.None);
            Assert.That(viewModel.IsReady, Is.True);

            int previousCount = viewModel.Messages.Count;
            viewModel.Draft = "qué hora es";
            var stopwatch = Stopwatch.StartNew();
            await viewModel.SubmitAsync(CancellationToken.None);
            stopwatch.Stop();

            ConversationMessage answer = viewModel.Messages.Skip(previousCount).Last();
            using JsonDocument document = JsonDocument.Parse(answer.Body);
            JsonElement rootElement = document.RootElement;
            DateTimeOffset utc = DateTimeOffset.Parse(
                rootElement.GetProperty("observed").GetProperty("utc").GetString()!,
                CultureInfo.InvariantCulture);
            Assert.Multiple(() =>
            {
                Assert.That(answer.IsUser, Is.False);
                Assert.That(rootElement.GetProperty("operation").GetString(), Is.EqualTo("system.time"));
                Assert.That(rootElement.GetProperty("verified").GetBoolean(), Is.True);
                Assert.That(rootElement.GetProperty("succeeded").GetBoolean(), Is.True);
                Assert.That(stopwatch.Elapsed, Is.LessThan(TimeSpan.FromSeconds(4)));
                Assert.That(
                    Math.Abs((utc - DateTimeOffset.UtcNow).TotalSeconds),
                    Is.LessThanOrEqualTo(5));
            });
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
}
