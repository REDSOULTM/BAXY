using System.Diagnostics;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
[NonParallelizable]
public sealed class NaturalSystemTimeViewModelEndToEndTests
{
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
            Assert.Multiple(() =>
            {
                Assert.That(answer.IsUser, Is.False);
                Assert.That(answer.Body, Does.Contain("system.time"), answer.Body);
                Assert.That(answer.Body, Does.Contain("\"polarity\":\"success\""), answer.Body);
                Assert.That(stopwatch.Elapsed, Is.LessThan(TimeSpan.FromSeconds(4)));
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
