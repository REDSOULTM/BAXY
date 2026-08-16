using System.Diagnostics;
using System.Globalization;
using System.Text.RegularExpressions;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
[NonParallelizable]
public sealed partial class NaturalSystemTimeViewModelEndToEndTests
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
            Match match = TimeReply().Match(answer.Body);
            Assert.Multiple(() =>
            {
                Assert.That(answer.IsUser, Is.False);
                Assert.That(match.Success, Is.True, answer.Body);
                Assert.That(stopwatch.Elapsed, Is.LessThan(TimeSpan.FromSeconds(4)));
            });

            if (match.Success)
            {
                TimeOnly reported = TimeOnly.ParseExact(
                    match.Groups[1].Value,
                    "HH:mm",
                    CultureInfo.InvariantCulture);
                TimeOnly observed = TimeOnly.FromDateTime(DateTime.Now);
                double minuteDelta = Math.Abs((reported - observed).TotalMinutes);
                minuteDelta = Math.Min(minuteDelta, 24 * 60 - minuteDelta);
                Assert.That(minuteDelta, Is.LessThanOrEqualTo(1));
            }
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

    [GeneratedRegex("^La fecha local es [0-3][0-9]/[0-1][0-9]/[0-9]{4} y la hora local es ([0-2][0-9]:[0-5][0-9])\\.$", RegexOptions.CultureInvariant)]
    private static partial Regex TimeReply();
}
