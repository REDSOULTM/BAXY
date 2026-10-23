using System.Diagnostics;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Renew al máximo (rendimiento), manual check, opt-in only: times calculator.expression.evaluate and
/// filesystem.folder.open through the product's provider (prewarmed, one call not counted) and reports p50/p90 of
/// BAXY_PERF_LIVE_N calls (12 by default). Never runs in a suite: it is Explicit and also needs BAXY_PERF_LIVE_CHECK=1.
/// The Calculator it starts is closed after; the folder is a new one under the profile, each Explorer window that shows
/// it is closed after its call and the folder is removed at the end. Nothing the person had open is touched.
/// </summary>
[TestFixture]
[Explicit("Opens the Calculator and Explorer windows on the person's desktop.")]
public sealed class CalculatorFolderSpeedLiveCheck
{
    private static int Repetitions =>
        int.TryParse(Environment.GetEnvironmentVariable("BAXY_PERF_LIVE_N"), out int count) && count > 0 ? count : 12;

    [Test]
    public async Task CalculatorEvaluateIsTimed()
    {
        if (Environment.GetEnvironmentVariable("BAXY_PERF_LIVE_CHECK") != "1")
            Assert.Ignore("Set BAXY_PERF_LIVE_CHECK=1 to run the live check.");
        HashSet<int> before = Process.GetProcessesByName("CalculatorApp").Select(process => process.Id).ToHashSet();
        if (before.Count == 0)
        {
            using Process? started = Process.Start(new ProcessStartInfo("calc.exe") { UseShellExecute = true });
            await Task.Delay(3000);
        }

        string root = Path.Combine(Path.GetTempPath(), "baxy-perf-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        try
        {
            using var provider = new WindowsExternalCapabilityProvider(root);
            provider.Prewarm();
            JsonElement arguments = JsonDocument.Parse("""{"expression":"12*7+3"}""").RootElement;
            ExternalCapabilityReceipt warm = await provider.InvokeAsync(
                "calculator.expression.evaluate", arguments, CancellationToken.None);
            TestContext.Out.WriteLine($"warm ok={warm.Verified} error={warm.ErrorCode} result={warm.Result?.GetRawText()}");
            var times = new List<long>();
            for (int call = 0; call < Repetitions; call++)
            {
                var watch = Stopwatch.StartNew();
                ExternalCapabilityReceipt receipt = await provider.InvokeAsync(
                    "calculator.expression.evaluate", arguments, CancellationToken.None);
                times.Add(watch.ElapsedMilliseconds);
                Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
                Assert.That(receipt.Result?.GetProperty("value").GetString(), Is.EqualTo("87"));
            }

            Report("calculator.expression.evaluate", times);
        }
        finally
        {
            foreach (Process process in Process.GetProcessesByName("CalculatorApp"))
            {
                using (process)
                {
                    if (!before.Contains(process.Id))
                        process.Kill();
                }
            }

            Directory.Delete(root, recursive: true);
        }
    }

    [Test]
    public async Task FolderOpenIsTimed()
    {
        if (Environment.GetEnvironmentVariable("BAXY_PERF_LIVE_CHECK") != "1")
            Assert.Ignore("Set BAXY_PERF_LIVE_CHECK=1 to run the live check.");
        string name = "BAXY-perf-" + Guid.NewGuid().ToString("N")[..8];
        string folder = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), name);
        Directory.CreateDirectory(folder);
        string root = Path.Combine(Path.GetTempPath(), "baxy-perf-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        try
        {
            using var provider = new WindowsExternalCapabilityProvider(root);
            provider.Prewarm();
            JsonElement arguments = JsonDocument.Parse(
                $$"""{"folder":"home","subdirectory":"{{name}}"}""").RootElement;
            ExternalCapabilityReceipt warm = await provider.InvokeAsync(
                "filesystem.folder.open", arguments, CancellationToken.None);
            TestContext.Out.WriteLine($"warm ok={warm.Verified} error={warm.ErrorCode} result={warm.Result?.GetRawText()}");
            CloseExplorerOn(folder);
            var times = new List<long>();
            for (int call = 0; call < Repetitions; call++)
            {
                var watch = Stopwatch.StartNew();
                ExternalCapabilityReceipt receipt = await provider.InvokeAsync(
                    "filesystem.folder.open", arguments, CancellationToken.None);
                times.Add(watch.ElapsedMilliseconds);
                CloseExplorerOn(folder);
                Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            }

            Report("filesystem.folder.open", times);
        }
        finally
        {
            CloseExplorerOn(folder);
            Directory.Delete(folder, recursive: true);
            Directory.Delete(root, recursive: true);
        }
    }

    // Closes only the Explorer windows that show the check's own folder, and waits until none does.
    private static void CloseExplorerOn(string folder)
    {
        string script = "$p='" + folder.Replace("'", "''", StringComparison.Ordinal) + "';$s=New-Object -ComObject Shell.Application;"
            + "for($i=0;$i -lt 40;$i++){$n=0;foreach($w in @($s.Windows())){try{$u=[string]$w.LocationURL}catch{continue};"
            + "if($u.StartsWith('file:') -and [string]::Equals(([Uri]$u).LocalPath.TrimEnd('\\'),$p,'OrdinalIgnoreCase')){$n++;$w.Quit()}};"
            + "if($n -eq 0){break};Start-Sleep -Milliseconds 250}";
        using Process? closer = Process.Start(new ProcessStartInfo("powershell.exe")
        {
            ArgumentList = { "-NoProfile", "-NonInteractive", "-Command", script },
            UseShellExecute = false,
            CreateNoWindow = true,
        });
        closer?.WaitForExit(20_000);
    }

    private static void Report(string operation, List<long> times)
    {
        long[] sorted = [.. times.Order()];
        long Percentile(double share) => sorted[Math.Min(sorted.Length - 1, (int)Math.Ceiling(share * sorted.Length) - 1)];
        TestContext.Out.WriteLine(
            $"{operation} n={sorted.Length} p50={Percentile(0.5)} p90={Percentile(0.9)} min={sorted[0]} max={sorted[^1]} "
            + $"all=[{string.Join(",", times)}]");
    }
}
