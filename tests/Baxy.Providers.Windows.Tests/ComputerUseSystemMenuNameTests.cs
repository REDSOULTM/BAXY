using System.Diagnostics;
using System.Text;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Pasada r15b, v3-23: «hacer clic en sistema» in an MMC console (the Event Viewer) was a click by label alone; the
/// worker's lookup by name found the window's system menu («Sistema», a MenuItem inside the «Barra de menús del
/// sistema» MenuBar of the TitleBar), opened it (method expand, uia_surface) and the sub-goal was taken as done. A click
/// by name never lands there: the system menu is a menu control hanging from the window's TitleBar, and only a click
/// that carries the identity the view gave reaches it. The worker's rule (<c>Test-SystemMenuChain</c>) is taken from
/// the script by its syntax tree and run on described controls: no window is read or touched.
/// </summary>
[TestFixture]
public sealed class ComputerUseSystemMenuNameTests
{
    [Test]
    public void TheMenuOfTheTitleBarIsNoPlaceALabelNames()
    {
        string worker = Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1");
        Assume.That(File.Exists(worker), "the worker script is copied next to the tests");
        const string cases = """
            [
              {"kind":"MenuItem","ancestors":["MenuBar","TitleBar","Window"]},
              {"kind":"MenuBar","ancestors":["TitleBar","Window"]},
              {"kind":"DataItem","ancestors":["DataGrid","Pane","Window"]},
              {"kind":"TreeItem","ancestors":["TreeItem","Tree","Pane"]},
              {"kind":"MenuItem","ancestors":["MenuBar","Pane","Window"]},
              {"kind":"MenuItem","ancestors":["Menu","Window"]},
              {"kind":"Button","ancestors":["TitleBar","Window"]},
              {"kind":"MenuItem","ancestors":["MenuBar","Pane","TitleBar"]},
              {"kind":"ListItem","ancestors":["List","Pane","Window"]}
            ]
            """;
        string answer = RunRule(worker, cases);
        Assert.That(answer.Split(','), Is.EqualTo(new[]
        {
            "True",  // v3-23: «Sistema», the item of the system menu bar in the title bar
            "True",  // the system menu bar itself
            "False", // the «Sistema» log of the console's list (the place the goal names)
            "False", // a tree node
            "False", // the window's own menu bar («Archivo», «Acción»): not under the title bar
            "False", // an open popup menu's entry
            "False", // the frame's buttons (minimize, maximize, close) keep their own reading
            "False", // a menu drawn deeper inside a custom title area is the application's own
            "False", // a list entry named «Sistema» (Settings' page)
        }));
    }

    private static string RunRule(string worker, string cases)
    {
        const string script = """
            $ErrorActionPreference='Stop'
            $tokens=$null;$errors=$null
            $ast=[System.Management.Automation.Language.Parser]::ParseFile($env:BAXY_SYSMENU_WORKER,[ref]$tokens,[ref]$errors)
            if($errors.Count -gt 0){ throw 'worker does not parse' }
            $wanted=@('Test-SystemMenuChain')
            $found=@($ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $wanted -contains $node.Name },$true))
            if($found.Count -ne 1){ throw 'rule function missing' }
            foreach($definition in $found){ . ([scriptblock]::Create($definition.Extent.Text)) }
            $cases=[System.IO.File]::ReadAllText($env:BAXY_SYSMENU_CASES,[System.Text.Encoding]::UTF8) | ConvertFrom-Json
            [Console]::Out.Write((@($cases | ForEach-Object { [string](Test-SystemMenuChain ([string]$_.kind) @($_.ancestors | ForEach-Object { [string]$_ })) }) -join ','))
            """;
        string casesFile = Path.Combine(Path.GetTempPath(), "baxy-sysmenu-" + Guid.NewGuid().ToString("N") + ".json");
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
            start.Environment["BAXY_SYSMENU_WORKER"] = worker;
            start.Environment["BAXY_SYSMENU_CASES"] = casesFile;
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
