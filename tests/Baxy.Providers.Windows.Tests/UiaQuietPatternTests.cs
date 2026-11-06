using System.Diagnostics;
using System.Text;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// The pattern calls on a window behind go through the COM client with <c>IUIAutomation2::AutoSetFocus</c> off (agent-desktop
/// #567; Microsoft's documentation of the property). Measured in <c>uso-108-foco</c> on WinForms, WPF and Chromium windows of
/// the probe's own: with the switch on, every pattern call took the front; with it off, none did, except the classic
/// controls that the in-process providers press themselves. These tests take the worker's own text and open no window.
/// </summary>
[TestFixture]
public sealed class UiaQuietPatternTests
{
    // The worker's native class and the timed press, from its text, in a PowerShell of their own.
    private const string Prelude = """
        $ErrorActionPreference='Stop'
        $text=[IO.File]::ReadAllText($env:BAXY_QUIET_WORKER)
        $tokens=$null;$errors=$null
        $ast=[System.Management.Automation.Language.Parser]::ParseInput($text,[ref]$tokens,[ref]$errors)
        $here=@($ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.StringConstantExpressionAst] -and ($node.Value.Contains('public static class BaxyUiaWorkerNative') -or $node.Value.Contains('public static class BaxyUiaTimedPress')) },$true))
        Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes,WindowsBase
        Add-Type -ReferencedAssemblies Accessibility -TypeDefinition (@($here | Where-Object { $_.Value.Contains('class BaxyUiaWorkerNative') })[0].Value)
        Add-Type -ReferencedAssemblies UIAutomationClient,UIAutomationTypes,WindowsBase -TypeDefinition (@($here | Where-Object { $_.Value.Contains('class BaxyUiaTimedPress') })[0].Value)

        """;

    [Test]
    public void TheComClientHasItsAutomaticFocusOff()
    {
        // agent-desktop #567's regression test, on BAXY's client: created, the property reads back false.
        string answer = RunNative("[Console]::Out.Write([BaxyUiaWorkerNative]::ClientFocusSwitch())");
        Assert.That(answer, Is.EqualTo("off"));
    }

    [Test]
    public void AnElementWithNoWindowOrIdentityIsNotRouted()
    {
        string answer = RunNative("""
            $answers=@(
              [BaxyUiaWorkerNative]::QuietPattern([IntPtr]::Zero,[int[]]@(42,1),'invoke',''),
              [BaxyUiaWorkerNative]::QuietPattern([IntPtr]1234,[int[]]@(),'invoke',''),
              [BaxyUiaWorkerNative]::QuietPattern([IntPtr]1234,$null,'toggle','')
            )
            [Console]::Out.Write(($answers -join ','))
            """);
        Assert.That(answer, Is.EqualTo("absent,absent,absent"), "nothing was sent: the managed path decides");
    }

    // The worker's own line that hands the quiet call over, run without its catch: a type literal PowerShell 5.1 could not
    // resolve left the route dead with every other test green (seen only when the worker ran it live).
    [Test]
    public void TheWorkerHandsTheQuietCallOver()
    {
        string script = File.ReadAllText(ComputerUseListenedPressTests.Worker());
        const string Start = "[BaxyUiaTimedPress]::Quiet=";
        int at = script.IndexOf(Start, StringComparison.Ordinal);
        Assert.That(at, Is.GreaterThan(0), "the worker hands it over");
        string statement = script[at..script.IndexOf(" } catch {}", at, StringComparison.Ordinal)];
        string answer = RunNative(statement + "\n[Console]::Out.Write($null -ne [BaxyUiaTimedPress]::Quiet)");
        Assert.That(answer, Is.EqualTo("True"));
    }

    // The enumeration behind Get-ToolMenuRects, read only: a process id no process has holds no tool window.
    [Test]
    public void AProcessThatDoesNotExistHasNoToolWindows()
    {
        string answer = RunNative("[Console]::Out.Write([string]@([BaxyUiaWorkerNative]::ToolWindowsOf([uint32]999999)).Count)");
        Assert.That(answer, Is.EqualTo("0"));
    }

    // What the worker does with each answer: «done» acted and nothing else is sent; «absent» sent nothing and the managed
    // call follows; a refusal raises as the managed call would (its callers read those exceptions), and is never sent again.
    [Test]
    public void TheWorkerFollowsTheAnswerOfTheQuietCall()
    {
        string answer = ComputerUseListenedPressTests.Run(ComputerUseListenedPressTests.Worker(), ["Invoke-QuietPattern"], """
            Add-Type -TypeDefinition @'
            public static class BaxyUiaTimedPress {
              public static string Answer;
              public static string QuietCall(object element, string op, string text) { return Answer; }
            }
            '@
            $answers=foreach($given in @('done','absent','refused:80040200','refused:80131509')){
              [BaxyUiaTimedPress]::Answer=$given
              try { [string](Invoke-QuietPattern 'el' 'select' '') } catch { $_.Exception.GetType().Name }
            }
            [Console]::Out.Write((@($answers) -join ','))
            """);
        Assert.That(answer.Split(','), Is.EqualTo(new[]
        {
            "True",
            "False",
            "ElementNotEnabledException",
            "InvalidOperationException",
        }));
    }

    // A test double with no such call, or an element that is no real one, stays on the managed path.
    [Test]
    public void WithoutTheQuietCallTheManagedPathFollows()
    {
        string answer = ComputerUseListenedPressTests.Run(ComputerUseListenedPressTests.Worker(), ["Invoke-QuietPattern"], """
            [Console]::Out.Write([string](Invoke-QuietPattern 'el' 'toggle' ''))
            """);
        Assert.That(answer, Is.EqualTo("False"));
    }

    private static string RunNative(string body)
    {
        string worker = ComputerUseListenedPressTests.Worker();
        var start = new ProcessStartInfo("powershell.exe")
        {
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true,
        };
        foreach (string argument in new[] { "-NoProfile", "-NonInteractive", "-STA", "-ExecutionPolicy", "Bypass", "-EncodedCommand" })
            start.ArgumentList.Add(argument);
        start.ArgumentList.Add(Convert.ToBase64String(Encoding.Unicode.GetBytes(Prelude + body)));
        start.Environment["BAXY_QUIET_WORKER"] = worker;
        using Process process = Process.Start(start)!;
        Task<string> error = process.StandardError.ReadToEndAsync();
        Task<string> answer = process.StandardOutput.ReadToEndAsync();
        if (!process.WaitForExit(60_000))
        {
            process.Kill(entireProcessTree: true);
            Assert.Fail("the script answers within 60 s");
        }

        Assert.That(process.ExitCode, Is.EqualTo(0), error.Result);
        return answer.Result;
    }
}
