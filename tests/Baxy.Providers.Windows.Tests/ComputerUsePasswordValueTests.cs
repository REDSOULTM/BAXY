using System.Diagnostics;
using System.Text;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Renew al máximo (lote 4, b): a field that says it holds a password (UIA <c>IsPassword</c>) is shown in the view as a
/// password field with no value: its ValuePattern is never read, so a provider that exposes the password in clear text
/// cannot put it in the view, the model or the trace. <c>Get-State</c> is taken from the script by its syntax tree and
/// run on described elements: no window is read or touched.
/// </summary>
[TestFixture]
public sealed class ComputerUsePasswordValueTests
{
    [Test]
    public void APasswordFieldsValueIsNeverRead()
    {
        const string script = """
            $ErrorActionPreference='Stop'
            Add-Type -AssemblyName UIAutomationClient
            Add-Type -AssemblyName UIAutomationTypes
            $tokens=$null;$errors=$null
            $ast=[System.Management.Automation.Language.Parser]::ParseFile($env:BAXY_FRAME_WORKER,[ref]$tokens,[ref]$errors)
            if($errors.Count -gt 0){ throw 'worker does not parse' }
            $found=@($ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Get-State' },$true))
            if($found.Count -ne 1){ throw 'rule function missing' }
            . ([scriptblock]::Create($found[0].Extent.Text))
            # A field whose provider gives its value in clear text: asking its ValuePattern is reading it.
            function New-Field([bool]$password){
              $field=[pscustomobject]@{ Cached=[pscustomobject]@{ IsPassword=$password; HasKeyboardFocus=$true; ControlType=[pscustomobject]@{ ProgrammaticName='ControlType.Edit' } } }
              $field | Add-Member -MemberType ScriptMethod -Name TryGetCachedPattern -Value {
                param($pattern,$out)
                if($pattern -eq [System.Windows.Automation.ValuePattern]::Pattern){ throw 'value read' }
                return $false
              }
              return $field
            }
            function Say($field){
              try { $info=Get-State $field; return ([string]$info.state)+'/'+$(if($null -eq $info.value){'null'}else{[string]$info.value}) }
              catch { $e=$_.Exception; while($null -ne $e.InnerException){ $e=$e.InnerException }; return [string]$e.Message }
            }
            $answers=@((Say (New-Field $true)), (Say (New-Field $false)))
            [Console]::Out.Write(($answers -join '|'))
            """;
        // The counter-case: a field that is no password has its value read.
        Assert.That(RunScript(script), Is.EqualTo("password focused/null|value read"));
    }

    private static string RunScript(string script)
    {
        string worker = Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1");
        Assume.That(File.Exists(worker), "the worker script is copied next to the tests");
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
        start.Environment["BAXY_FRAME_WORKER"] = worker;
        using Process process = Process.Start(start)!;
        Task<string> error = process.StandardError.ReadToEndAsync();
        string output = process.StandardOutput.ReadToEnd();
        Assert.That(process.WaitForExit(60_000), Is.True, "the rule answers");
        Assert.That(process.ExitCode, Is.EqualTo(0), error.Result);
        return output.Trim();
    }
}
