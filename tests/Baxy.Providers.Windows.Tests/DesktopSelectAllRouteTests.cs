using System.Diagnostics;
using System.Text;
using System.Text.Json;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Encargo 94 (verificación en vivo 84: «copia todo el texto del Bloc de notas», 0 de 14): Ctrl+A is a shortcut of the
/// application, which each language binds as it likes (Windows 11's Notepad in Spanish opens «Abrir» with it, and selects
/// all with Ctrl+E), so the selection is made by UI Automation and the keys are the last resort; a dialog they raise is
/// said and closed. The script's route is taken by its syntax tree and run over scripted pieces: no window is touched.
/// </summary>
[TestFixture]
public sealed class DesktopSelectAllRouteTests
{
    private const string Pieces = """
        $log=[System.Collections.ArrayList]::new()
        $state=@{ covered=$false; windows=@(@{handle=1L;title='Documento';owned=$false}) }
        $select={ [void]$log.Add('select'); $state.covered=$true }.GetNewClosure()
        $covered={ $state.covered }.GetNewClosure()
        $keys={ [void]$log.Add('keys'); [uint32]4 }.GetNewClosure()
        $windows={ $state.windows }.GetNewClosure()
        $close={ param($handle) [void]$log.Add("close:$handle"); $true }.GetNewClosure()
        function Show($answer){
            [Console]::Out.Write((@{
                verified=$answer.verified; selectedBy=$answer.selectedBy; error=$answer.error; effect=$answer.effect;
                dialog=$answer.dialog; log=@($log) } | ConvertTo-Json -Compress -Depth 4))
        }

        """;

    [Test]
    public void TheSelectionMadeByUiAutomationSendsNoKey()
    {
        using JsonDocument answer = Run("""
            Show (Select-BaxyWholeText $select $covered $keys $windows $close)
            """);

        JsonElement root = answer.RootElement;
        Assert.Multiple(() =>
        {
            Assert.That(root.GetProperty("verified").GetBoolean(), Is.True);
            Assert.That(root.GetProperty("selectedBy").GetString(), Is.EqualTo("ui_automation"));
            Assert.That(Log(root), Is.EqualTo(new[] { "select" }));
        });
    }

    // Contracase: a control whose Select does not reach its selection (or refuses) still has the keys, as a last resort.
    [Test]
    public void AControlThatRefusesTheSelectionGetsTheKeysAsALastResort()
    {
        using JsonDocument answer = Run("""
            $refuses={ [void]$log.Add('select'); throw 'not supported' }.GetNewClosure()
            $keysSelect={ [void]$log.Add('keys'); $state.covered=$true; [uint32]4 }.GetNewClosure()
            Show (Select-BaxyWholeText $refuses $covered $keysSelect $windows $close)
            """);

        JsonElement root = answer.RootElement;
        Assert.Multiple(() =>
        {
            Assert.That(root.GetProperty("verified").GetBoolean(), Is.True);
            Assert.That(root.GetProperty("selectedBy").GetString(), Is.EqualTo("keyboard"));
            Assert.That(Log(root), Is.EqualTo(new[] { "select", "keys" }));
        });
    }

    // The failure seen live, on a control whose Select does nothing: the keys raise a dialog that was not there. It is
    // said, and closed, and the state told is «nothing selected»: never success.
    [Test]
    public void ADialogTheKeysRaiseIsSaidAndClosed()
    {
        using JsonDocument answer = Run("""
            $noSelect={ [void]$log.Add('select') }.GetNewClosure()
            $keysOpen={ [void]$log.Add('keys')
                $state.windows=@($state.windows)+@(@{handle=7L;title='Abrir';owned=$true}); [uint32]4 }.GetNewClosure()
            Show (Select-BaxyWholeText $noSelect $covered $keysOpen $windows $close 50)
            """);

        JsonElement root = answer.RootElement;
        Assert.Multiple(() =>
        {
            Assert.That(root.GetProperty("verified").GetBoolean(), Is.False);
            Assert.That(root.GetProperty("error").GetString(), Is.EqualTo("select_all_opened_dialog"));
            Assert.That(root.GetProperty("dialog").GetProperty("title").GetString(), Is.EqualTo("Abrir"));
            Assert.That(root.GetProperty("dialog").GetProperty("closed").GetBoolean(), Is.True);
            Assert.That(Log(root), Is.EqualTo(new[] { "select", "keys", "close:7" }));
        });
    }

    // Contracase: a new window nobody owns is no dialog of this one, may be a document: said, not closed.
    [Test]
    public void ANewWindowNoOneOwnsIsSaidAndNotClosed()
    {
        using JsonDocument answer = Run("""
            $noSelect={ [void]$log.Add('select') }.GetNewClosure()
            $keysOpen={ [void]$log.Add('keys')
                $state.windows=@($state.windows)+@(@{handle=8L;title='Otra';owned=$false}); [uint32]4 }.GetNewClosure()
            Show (Select-BaxyWholeText $noSelect $covered $keysOpen $windows $close 50)
            """);

        JsonElement root = answer.RootElement;
        Assert.Multiple(() =>
        {
            Assert.That(root.GetProperty("error").GetString(), Is.EqualTo("select_all_opened_dialog"));
            Assert.That(root.GetProperty("dialog").GetProperty("closed").GetBoolean(), Is.False);
            Assert.That(Log(root), Is.EqualTo(new[] { "select", "keys" }));
        });
    }

    [Test]
    public void KeysThatDoNothingAreNotVerifiedAndThoseWindowsNotAcceptedAreSaid()
    {
        using JsonDocument nothing = Run("""
            $noSelect={ [void]$log.Add('select') }.GetNewClosure()
            Show (Select-BaxyWholeText $noSelect $covered $keys $windows $close 50)
            """);
        using JsonDocument refused = Run("""
            $noSelect={ [void]$log.Add('select') }.GetNewClosure()
            $keysRefused={ [void]$log.Add('keys'); [uint32]0 }.GetNewClosure()
            Show (Select-BaxyWholeText $noSelect $covered $keysRefused $windows $close 50)
            """);

        Assert.Multiple(() =>
        {
            Assert.That(nothing.RootElement.GetProperty("verified").GetBoolean(), Is.False);
            Assert.That(nothing.RootElement.GetProperty("error").GetString(), Is.EqualTo("select_all_postcondition_not_verified"));
            Assert.That(refused.RootElement.GetProperty("error").GetString(), Is.EqualTo("select_all_input_not_accepted"));
        });
    }

    private static string[] Log(JsonElement root) =>
        root.GetProperty("log").EnumerateArray().Select(static item => item.GetString()!).ToArray();

    private static JsonDocument Run(string body)
    {
        string helper = Path.Combine(AppContext.BaseDirectory, "DesktopSelectAll.ps1");
        Assert.That(File.Exists(helper), Is.True, "the helper script is copied next to the tests");
        string script = """
            $ErrorActionPreference='Stop'
            $tokens=$null;$errors=$null
            $ast=[System.Management.Automation.Language.Parser]::ParseFile($env:BAXY_SELECT_ALL,[ref]$tokens,[ref]$errors)
            if($errors.Count -gt 0){ throw 'the script does not parse' }
            foreach($name in 'Wait-BaxyPoll','Select-BaxyWholeText'){
                $found=@($ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name },$true))
                if($found.Count -ne 1){ throw "function missing: $name" }
                . ([scriptblock]::Create($found[0].Extent.Text))
            }

            """ + Pieces + body;
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
        start.Environment["BAXY_SELECT_ALL"] = helper;
        using Process process = Process.Start(start)!;
        Task<string> error = process.StandardError.ReadToEndAsync();
        string output = ChildOutput.Read(process);
        Assert.That(process.WaitForExit(60_000), Is.True, "the script answers");
        Assert.That(process.ExitCode, Is.EqualTo(0), error.Result);
        return JsonDocument.Parse(output.Trim());
    }
}
