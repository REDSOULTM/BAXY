using System.Diagnostics;
using System.Text;
using System.Text.Json;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Functions of the UI Automation worker taken from its script by its syntax tree and run on described elements: no
/// window is read or touched. The body writes its answer to stdout as JSON.
/// </summary>
internal static class WorkerFunctions
{
    internal static JsonElement Run(string[] names, string body)
    {
        string worker = Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1");
        Assume.That(File.Exists(worker), "the worker script is copied next to the tests");
        string script = """
            $ErrorActionPreference='Stop'
            [Console]::OutputEncoding=New-Object System.Text.UTF8Encoding($false)
            Add-Type -AssemblyName UIAutomationClient
            $tokens=$null;$errors=$null
            $ast=[System.Management.Automation.Language.Parser]::ParseFile($env:BAXY_WORKER_SCRIPT,[ref]$tokens,[ref]$errors)
            if($errors.Count -gt 0){ throw 'worker does not parse' }
            $wanted=@($env:BAXY_WORKER_FUNCTIONS -split ',')
            $found=@($ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $wanted -contains $node.Name },$true))
            if($found.Count -ne $wanted.Count){ throw 'worker functions missing' }
            foreach($definition in $found){ . ([scriptblock]::Create($definition.Extent.Text)) }

            """ + body;
        var start = new ProcessStartInfo("powershell.exe")
        {
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true,
            StandardOutputEncoding = Encoding.UTF8,
        };
        foreach (string argument in new[] { "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand" })
            start.ArgumentList.Add(argument);
        start.ArgumentList.Add(Convert.ToBase64String(Encoding.Unicode.GetBytes(script)));
        start.Environment["BAXY_WORKER_SCRIPT"] = worker;
        start.Environment["BAXY_WORKER_FUNCTIONS"] = string.Join(',', names);
        using Process process = Process.Start(start)!;
        Task<string> error = process.StandardError.ReadToEndAsync();
        string output = ChildOutput.Read(process);
        Assert.That(process.WaitForExit(60_000), Is.True, "the worker functions answer");
        Assert.That(process.ExitCode, Is.EqualTo(0), error.Result);
        return JsonDocument.Parse(output).RootElement.Clone();
    }
}
