using System.Diagnostics;
using System.Text;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// C49 (noche 28-10, medio 1 de PC-C46): «baja el brillo» said with no number is a step of 10, and a step down from 10
/// left the screen at 0, black. A step down stops at 10 (or where it already is, under 10); only a level said with
/// system_settings_set reaches 0. The real adjust script runs here against a fake WMI: no monitor is touched.
/// </summary>
[TestFixture]
public sealed class BrightnessStepFloorTests
{
    [TestCase(10, -10, 10)]
    [TestCase(15, -10, 10)]
    [TestCase(12, -50, 10)]
    [TestCase(5, -10, 5)]
    [TestCase(50, -10, 40)]
    [TestCase(5, 10, 15)]
    [TestCase(95, 10, 100)]
    public async Task AStepDownNeverLeavesTheScreenUnderTen(int before, int delta, int after)
    {
        using JsonDocument result = JsonDocument.Parse(await RunAdjustAsync(before, delta));

        Assert.Multiple(() =>
        {
            Assert.That(result.RootElement.GetProperty("ok").GetBoolean(), Is.True, result.RootElement.ToString());
            Assert.That(result.RootElement.GetProperty("baselineValues")[0].GetInt32(), Is.EqualTo(before));
            Assert.That(result.RootElement.GetProperty("values")[0].GetInt32(), Is.EqualTo(after));
        });
    }

    private static async Task<string> RunAdjustAsync(int before, int delta)
    {
        // Functions are found before cmdlets: the script's WMI reads and set go to this one-monitor fake.
        string script = "$global:level=" + before + """

            function Get-CimInstance { [pscustomobject]@{InstanceName='m';CurrentBrightness=$global:level} }
            function Invoke-CimMethod { param($InputObject,$MethodName,$Arguments) $global:level=[int]$Arguments.Brightness }
            & {
            """ + WindowsDeviceControlAdapter.BrightnessAdjustScript + "\n} '" + delta + "'";
        var start = new ProcessStartInfo("powershell.exe")
        {
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true,
        };
        foreach (string argument in new[] { "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand" })
        {
            start.ArgumentList.Add(argument);
        }

        start.ArgumentList.Add(Convert.ToBase64String(Encoding.Unicode.GetBytes(script)));
        using Process process = Process.Start(start) ?? throw new InvalidOperationException("powershell did not start");
        Task<string> error = process.StandardError.ReadToEndAsync();
        string output = await process.StandardOutput.ReadToEndAsync();
        Assert.That(process.WaitForExit(60_000), Is.True, "the script answers");
        Assert.That(process.ExitCode, Is.EqualTo(0), await error);
        return output.Trim().Split('\n')[^1];
    }
}
