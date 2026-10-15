using System.Diagnostics;
using System.Text;
using System.Text.Json;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Ronda 24 (v3-39, «windows terminal: open settings and tell me which profile is the default»): the datum of a box is
/// what it has chosen. The view kept one control per kind and name and dropped the chosen «Windows PowerShell» of the
/// «Perfil predeterminado» box because the profiles' list had another, unchosen, before it; and a box that exposes its
/// choice only by selection (no ValuePattern) showed no value. The worker's own functions are taken from the script by
/// its syntax tree and run on described elements: no window is read or touched.
/// </summary>
[TestFixture]
public sealed class ComputerUseChosenEntryTests
{
    [Test]
    public void AChosenControlIsNoDuplicateOfAnUnchosenOneButEqualRowsStayTogether()
    {
        JsonElement answer = RunWorker("""
            $keys=@(
              (Get-SeenKey 'ListItem' 'Windows PowerShell' ''),
              (Get-SeenKey 'ListItem' 'Windows PowerShell' 'selected'),
              (Get-SeenKey 'ListItem' 'Ubuntu' ''),
              (Get-SeenKey 'ListItem' 'Ubuntu' 'focused'),
              (Get-SeenKey 'CheckBox' 'Negrita' 'on focused'),
              (Get-SeenKey 'MenuItem' 'Archivo' 'collapsed'))
            [Console]::Out.Write((ConvertTo-Json -Compress $keys))
            """);

        string[] keys = answer.EnumerateArray().Select(item => item.GetString()!).ToArray();
        Assert.Multiple(() =>
        {
            Assert.That(keys[1], Is.Not.EqualTo(keys[0]), "the chosen entry of the box is listed beside the list's own");
            Assert.That(keys[3], Is.EqualTo(keys[2]), "counter-case: two equal rows without a distinct choice stay one (x2)");
            Assert.That(keys[2], Is.EqualTo("ListItem|Ubuntu"), "an unchosen control keeps the key the menu entries share");
            Assert.That(keys[4], Is.EqualTo("CheckBox|Negrita|on"));
            Assert.That(keys[5], Is.EqualTo("MenuItem|Archivo"));
        });
    }

    [Test]
    public void ABoxWithoutValueTellsItsChosenEntry()
    {
        JsonElement answer = RunWorker("""
            Add-Type -AssemblyName UIAutomationClient
            function Entry([string]$name){ return [pscustomobject]@{ Current=[pscustomobject]@{ Name=$name } } }
            function Box($chosen){
              $selection=[pscustomobject]@{ Chosen=$chosen }
              $selection | Add-Member -MemberType ScriptMethod -Name GetSelection -Value { return ,@($this.Chosen) }
              $pattern=[pscustomobject]@{ Current=$selection }
              $box=[pscustomobject]@{ Pattern=$pattern }
              $box | Add-Member -MemberType ScriptMethod -Name GetCurrentPattern -Value { param($which) return $this.Pattern }
              return $box
            }
            $none=[pscustomobject]@{}
            $none | Add-Member -MemberType ScriptMethod -Name GetCurrentPattern -Value { param($which) throw 'unsupported' }
            $values=@(
              (Get-ChosenEntry (Box @(Entry '  Windows   PowerShell '))),
              (Get-ChosenEntry (Box @())),
              (Get-ChosenEntry $none))
            [Console]::Out.Write((ConvertTo-Json -Compress @($values | ForEach-Object { if($null -eq $_){ '<null>' } else { $_ } })))
            """);

        Assert.That(answer.EnumerateArray().Select(item => item.GetString()), Is.EqualTo(new[]
        {
            "Windows PowerShell",   // the chosen entry's name, spaces folded
            "<null>",               // nothing chosen: no value is said
            "<null>",               // a box without selection: unknown, as before
        }));
    }

    private static string WorkerPath()
    {
        string worker = Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1");
        Assume.That(File.Exists(worker), "the worker script is copied next to the tests");
        return worker;
    }

    private static JsonElement RunWorker(string body)
    {
        string script = """
            $ErrorActionPreference='Stop'
            [Console]::OutputEncoding=New-Object System.Text.UTF8Encoding($false)
            $tokens=$null;$errors=$null
            $ast=[System.Management.Automation.Language.Parser]::ParseFile($env:BAXY_CHOSEN_WORKER,[ref]$tokens,[ref]$errors)
            if($errors.Count -gt 0){ throw 'worker does not parse' }
            $wanted=@('Get-SeenKey','Get-ChosenEntry','Get-Cut')
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
        start.Environment["BAXY_CHOSEN_WORKER"] = WorkerPath();
        using Process process = Process.Start(start)!;
        Task<string> error = process.StandardError.ReadToEndAsync();
        string output = process.StandardOutput.ReadToEnd();
        Assert.That(process.WaitForExit(60_000), Is.True, "the worker functions answer");
        Assert.That(process.ExitCode, Is.EqualTo(0), error.Result);
        return JsonDocument.Parse(output).RootElement.Clone();
    }
}
