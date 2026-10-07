using System.Diagnostics;
using System.Text;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// A click by label alone finds every control with that name; several of them in one line of descent (measured on
/// Paint: each gallery entry is a ListItem holding a Button, both «Rectángulo redondeado») are one target, while
/// separate controls with the same name stay ambiguous. The worker's own rule (<c>Select-LineageOne</c>) is taken
/// from the script by its syntax tree and run on described controls: no window is read or touched.
/// </summary>
[TestFixture]
public sealed class ComputerUseNamedLineageTests
{
    [Test]
    public void OneLineOfDescentIsOneTargetAndSeparateControlsStayAmbiguous()
    {
        string worker = Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1");
        Assume.That(File.Exists(worker), "the worker script is copied next to the tests");
        const string cases = """
            [
              [{"name":"Rectángulo redondeado","key":"7.1","ancestors":["7.0","1"],"select":true},
               {"name":"Rectángulo redondeado","key":"7.2","ancestors":["7.1","7.0","1"],"invoke":true}],
              [{"name":"Rojo","key":"7.1","ancestors":["7.0"],"select":true},
               {"name":"Rojo","key":"7.2","ancestors":["7.1","7.0"]}],
              [{"name":"Rojo","key":"7.1","ancestors":["7.0"]},
               {"name":"Rojo","key":"7.2","ancestors":["7.1","7.0"]},
               {"name":"rojo","key":"7.3","ancestors":["7.2","7.1","7.0"]}],
              [{"name":"Guardar","key":"7.1","ancestors":["7.0"],"invoke":true},
               {"name":"Guardar","key":"7.2","ancestors":["7.0"],"invoke":true}],
              [{"name":"Azul","key":"","ancestors":[],"rect":{"x":0,"y":0,"w":40,"h":40}},
               {"name":"Azul","key":"","ancestors":[],"rect":{"x":4,"y":4,"w":20,"h":20}}],
              [{"name":"Azul","key":"","ancestors":[],"rect":{"x":0,"y":0,"w":20,"h":20}},
               {"name":"Azul","key":"","ancestors":[],"rect":{"x":30,"y":0,"w":20,"h":20}}],
              [{"name":"Rojo","key":"7.1","ancestors":["7.0"],"select":true},
               {"name":"Red","key":"7.2","ancestors":["7.1","7.0"],"invoke":true}]
            ]
            """;
        string answer = RunRule(worker, cases);
        Assert.That(answer.Split(','), Is.EqualTo(new[]
        {
            "1",  // the gallery entry: the Button that invokes, inside its ListItem
            "0",  // no invoke: the item that selects
            "2",  // neither: the innermost
            "-1", // two buttons side by side with one name: still ambiguous
            "1",  // no ancestor chain read: the rectangle inside the other
            "-1", // rectangles apart: separate controls
            "-1", // different names are never collapsed
        }));
    }

    private static string RunRule(string worker, string cases)
    {
        const string script = """
            $ErrorActionPreference='Stop'
            $tokens=$null;$errors=$null
            $ast=[System.Management.Automation.Language.Parser]::ParseFile($env:BAXY_LINEAGE_WORKER,[ref]$tokens,[ref]$errors)
            if($errors.Count -gt 0){ throw 'worker does not parse' }
            $wanted=@('Test-Contains','Select-LineageOne')
            $found=@($ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $wanted -contains $node.Name },$true))
            if($found.Count -ne 2){ throw 'rule functions missing' }
            foreach($definition in $found){ . ([scriptblock]::Create($definition.Extent.Text)) }
            $cases=[System.IO.File]::ReadAllText($env:BAXY_LINEAGE_CASES,[System.Text.Encoding]::UTF8) | ConvertFrom-Json
            [Console]::Out.Write((@($cases | ForEach-Object { [string](Select-LineageOne @($_)) }) -join ','))
            """;
        string casesFile = Path.Combine(Path.GetTempPath(), "baxy-lineage-" + Guid.NewGuid().ToString("N") + ".json");
        File.WriteAllText(casesFile, cases, new UTF8Encoding(false));
        try
        {
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
            start.Environment["BAXY_LINEAGE_WORKER"] = worker;
            start.Environment["BAXY_LINEAGE_CASES"] = casesFile;
            using Process process = Process.Start(start)!;
            Task<string> error = process.StandardError.ReadToEndAsync();
            string output = process.StandardOutput.ReadToEnd();
            Assert.That(process.WaitForExit(60_000), Is.True, "the rule answers");
            Assert.That(process.ExitCode, Is.EqualTo(0), error.Result);
            return output.Trim();
        }
        finally
        {
            File.Delete(casesFile);
        }
    }
}
