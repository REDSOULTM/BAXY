using System.Diagnostics;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Ronda final 38 (regla: efecto en la ventana de la persona sin pedido): a helper cut short ends alone, never its tree,
/// which holds what it opened for the person. The UI Automation worker runs helper scripts too (the folder's, which
/// starts explorer.exe with the folder asked; the calculator's; the Wi-Fi's): a worker that did not answer in its budget
/// is replaced, and what its script started stays. Nothing here touches a window: the script starts a hidden
/// PowerShell that sleeps.
/// </summary>
[TestFixture]
public sealed class UiaWorkerHostKillTests
{
    private string _folder = string.Empty;

    [SetUp]
    public void SetUp()
    {
        _folder = Path.Combine(Path.GetTempPath(), "baxy-uia-worker-kill-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(_folder);
    }

    [TearDown]
    public void TearDown()
    {
        try
        {
            Directory.Delete(_folder, recursive: true);
        }
        catch (IOException)
        {
        }
    }

    [Test]
    public async Task AScriptPastItsBudgetEndsTheWorkerButNotWhatTheScriptStarted()
    {
        string childFile = Path.Combine(_folder, "child.txt");
        string script = $$"""
            $child=Start-Process powershell.exe -ArgumentList '-NoProfile','-Command','Start-Sleep 30' -WindowStyle Hidden -PassThru
            Set-Content -LiteralPath '{{childFile}}' -Value $child.Id
            Start-Sleep -Seconds 10
            '{"ok":true}'
            """;
        using var worker = new UiaWorkerHost(Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1"));
        string command = new JsonObject { ["cmd"] = "script", ["script"] = script, ["args"] = new JsonArray() }.ToJsonString();

        using JsonDocument? answer = await worker.SendAsync(command, TimeSpan.FromSeconds(4), CancellationToken.None);
        Assert.That(answer, Is.Null, "the script did not answer within its budget");
        Assert.That(SpinWait.SpinUntil(() => File.Exists(childFile) && File.ReadAllText(childFile).Trim().Length > 0, 5000),
            Is.True);
        int child = int.Parse(File.ReadAllText(childFile).Trim(), System.Globalization.CultureInfo.InvariantCulture);
        try
        {
            Assert.That(Exited(child), Is.False, "what the script started is not killed with the worker");
        }
        finally
        {
            try
            {
                using Process process = Process.GetProcessById(child);
                process.Kill();
            }
            catch (Exception exception) when (exception is ArgumentException or InvalidOperationException)
            {
            }
        }
    }

    private static bool Exited(int pid)
    {
        try
        {
            using Process process = Process.GetProcessById(pid);
            return process.HasExited;
        }
        catch (ArgumentException)
        {
            return true;
        }
    }
}
