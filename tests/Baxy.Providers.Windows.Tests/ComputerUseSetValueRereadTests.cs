using System.Diagnostics;
using System.Text;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Regresiones r2 M3 (live v8): a Chromium field published the value UI Automation's SetValue wrote a little after the
/// call; read again at 95 ms it still held the old one and the text was told «input_effect_not_verified». The worker now
/// reads the value again for at most 300 ms before saying so. The worker's function is taken from the script by its
/// syntax tree and run over a scripted reader: no window is read or touched.
/// </summary>
[TestFixture]
public sealed class ComputerUseSetValueRereadTests
{
    [Test]
    public void AValueThatShowsWithinTheShortPollIsVerifiedAndOneThatNeverShowsStopsAtTheBound()
    {
        string worker = Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1");
        Assume.That(File.Exists(worker), "the worker script is copied next to the tests");
        string answer = Run(worker, """
            $null=(Wait-ValueSet { 'hola' } 'hola' 300)
            $reads=@{ n=0 }
            $late={ $reads.n++; if($reads.n -ge 2){ 'hola' } else { 'viejo' } }.GetNewClosure()
            $answers=@()
            $answers+=(Wait-ValueSet $late 'hola' 300)
            $answers+=[string]$reads.n
            $watch=[System.Diagnostics.Stopwatch]::StartNew()
            $answers+=(Wait-ValueSet { 'viejo' } 'hola' 300)
            $elapsed=$watch.ElapsedMilliseconds
            $answers+=[string]($elapsed -ge 280 -and $elapsed -lt 600)
            $watch.Restart()
            $answers+=(Wait-ValueSet { 'viejo' } 'hola' 5000)
            $answers+=[string]($watch.ElapsedMilliseconds -lt 600)
            $answers+=(Wait-ValueSet { 'hola' } 'hola' 300)
            $answers+=[string](Wait-ValueSet { throw 'gone' } 'hola' 0)
            [Console]::Out.Write(($answers -join ','))
            """);

        Assert.That(answer.Split(','), Is.EqualTo(new[]
        {
            "hola", "2",      // the value Chromium publishes late (second read, ~40 ms) is verified at the read that shows it
            "viejo", "True",  // counter-case: a value that never comes is the old one after about 300 ms
            "viejo", "True",  // the bound is never more than 300 ms whatever is asked
            "hola",           // a value already there is read at once
            "",               // a field gone answers no value
        }));
    }

    private static string Run(string worker, string body)
    {
        string script = """
            $ErrorActionPreference='Stop'
            $tokens=$null;$errors=$null
            $ast=[System.Management.Automation.Language.Parser]::ParseFile($env:BAXY_SETVALUE_WORKER,[ref]$tokens,[ref]$errors)
            if($errors.Count -gt 0){ throw 'worker does not parse' }
            $found=@($ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Wait-ValueSet' },$true))
            if($found.Count -ne 1){ throw 'function missing: Wait-ValueSet' }
            . ([scriptblock]::Create($found[0].Extent.Text))

            """ + body;
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
        start.Environment["BAXY_SETVALUE_WORKER"] = worker;
        using Process process = Process.Start(start)!;
        Task<string> error = process.StandardError.ReadToEndAsync();
        string output = process.StandardOutput.ReadToEnd();
        Assert.That(process.WaitForExit(60_000), Is.True, "the script answers");
        Assert.That(process.ExitCode, Is.EqualTo(0), error.Result);
        return output.Trim();
    }
}
