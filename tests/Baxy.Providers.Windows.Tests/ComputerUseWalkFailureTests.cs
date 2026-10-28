using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Encargo WA5 (banco wab3, notebook, 4 de 4): a chat client's first look read 60 controls, the click on the contact
/// opened its chat, and the next look failed with <c>visible_controls_uia_failed</c>, so every mission stopped with «the
/// window could not be read». The worker cut a long name at 60 characters between the two halves of an emoji (the journal
/// shows the half as U+FFFD in a chat preview); once the look carried the goal's words and that name lay past the view's
/// cap, <c>Get-Folded</c> normalized it and .NET threw on the lone half, failing the whole look. Cuts keep pairs whole;
/// and a walk that throws on a window that is still there is read as a window without a tree (its drawn text), while a
/// window that is gone fails as before.
/// </summary>
[TestFixture]
public sealed class ComputerUseWalkFailureTests
{
    private static readonly string[] Functions =
        ["Format-Name", "Get-Cut", "Join-ViewControls", "Get-FoldedFields", "Test-WantedName", "Get-Folded", "Test-CenterWithin"];

    // The shape of wab3 with neutral text: a chat preview whose emoji straddles the cut (the 160th character since R6-NB-5,
    // with no space before it to fall back to), another one shorter than the cut that keeps its emoji whole; the first
    // look (no words) and the look after the click (with the contact's name) over more controls than the cap.
    [Test]
    public void ALongNameCutAtAnEmojiNoLongerBreaksTheLookThatCarriesTheGoalsWords()
    {
        string answer = Run("""
            $script:ViewRowKinds=@('ListItem','TreeItem','DataItem');$script:WantedRoom=10
            function Test-Broken([string]$s){
              for($k=0;$k -lt $s.Length;$k++){
                if([char]::IsHighSurrogate($s[$k])){ if($k+1 -ge $s.Length -or -not [char]::IsLowSurrogate($s[$k+1])){ return $true }; $k++; continue }
                if([char]::IsLowSurrogate($s[$k])){ return $true }
              }
              return $false
            }
            $flower=[char]::ConvertFromUtf32(0x1F33C)
            $head=('x'*159)+$flower+' sigue el texto de ejemplo ... Chat silenciado'
            $tail=('Contacto D '+('y'*80))+$flower+('z'*15)
            $old=$head.Substring(0,160)
            $oldThrows=$false
            try { $null=Get-Folded $old } catch { $oldThrows=$true }
            $cutHead=Format-Name $head
            $cutTail=Format-Name $tail
            $plain=('A'*60)+('B'*30)
            $primary=New-Object System.Collections.ArrayList
            for($k=0;$k -lt 60;$k++){ [void]$primary.Add(@{ kind='Button'; name=('Mensaje '+$k); systemMenu=$false }) }
            [void]$primary.Add(@{ kind='DataItem'; name=$cutHead; systemMenu=$false })
            [void]$primary.Add(@{ kind='DataItem'; name=$cutTail; systemMenu=$false })
            [void]$primary.Add(@{ kind='DataItem'; name='Abuela 23:18'; systemMenu=$false })
            $first=Join-ViewControls $primary @() @() 60
            $after=Join-ViewControls $primary @() @() 60 @('abuela')
            [Console]::Out.Write((@(
              [string]$oldThrows,
              [string](Test-Broken $cutHead),
              [string](Test-Broken $cutTail),
              [string]($cutHead -ceq (('x'*159)+' '+[char]0x2026)),
              [string]($cutTail -ceq $tail),
              [string](((Format-Name $plain) -ceq $plain) -and ((Format-Name (('A'*100)+' '+('B'*100))) -ceq (('A'*100)+' '+[char]0x2026))),
              [string]$first.controls.Count,
              [string]$after.controls.Count,
              [string]$after.reserved,
              [string]$after.controls[60].name) -join '|'))
            """);
        Assert.That(answer.Split('|'), Is.EqualTo(new[]
        {
            "True",   // the old cut left half an emoji, and folding it threw: the look of wab3
            "False",  // the cut name keeps no half of the emoji
            "False",  // the shorter name keeps its emoji whole
            "True",   // the cut falls before the emoji, not between its halves
            "True",   // the shorter name arrives whole
            "True",   // contracase: a name without pairs arrives whole up to 160, past it is cut at a word (R6-NB-5)
            "63",     // the look before the click: its 60 and, since no row was in them, the rows (C11, reserved room)
            "61", "1", "Abuela 23:18", // the look after it: the contact named by the goal's words, past the cap
        }));
    }

    // The wab3 sequence: the worker threw on the look after the click and the window is still there. The look goes on
    // as a window without a tree (the adapter then reads its drawn text), with the worker's reason; a window that is gone,
    // another worker error or a walk that answered leave the answer as it was.
    [Test]
    public void AWalkThatThrowsOnAWindowStillThereGoesOnAsAWindowWithoutATree()
    {
        JsonElement thrown = Json("""{"ok":false,"error":"visible_controls_uia_failed","detail":"Invalid Unicode code point found at index 59."}""");
        using JsonDocument? there = WindowsVisibleControlAdapter.WithoutTree(thrown, 7, _ => true);
        using JsonDocument? silent = WindowsVisibleControlAdapter.WithoutTree(
            Json("""{"ok":false,"error":"visible_controls_uia_failed"}"""), 7, _ => true);

        Assert.Multiple(() =>
        {
            Assert.That(there?.RootElement.GetProperty("ok").GetBoolean(), Is.True);
            Assert.That(there?.RootElement.GetProperty("controls").GetArrayLength(), Is.Zero);
            Assert.That(there?.RootElement.GetProperty("uiaFailed").GetString(), Does.Contain("index 59"));
            Assert.That(silent?.RootElement.GetProperty("uiaFailed").GetString(), Is.Empty);
            Assert.That(WindowsVisibleControlAdapter.WithoutTree(thrown, 7, _ => false), Is.Null, "a window that is gone");
            Assert.That(WindowsVisibleControlAdapter.WithoutTree(
                Json("""{"ok":false,"error":"visible_controls_root_unavailable"}"""), 7, _ => true), Is.Null);
            Assert.That(WindowsVisibleControlAdapter.WithoutTree(Json("""{"ok":true,"controls":[]}"""), 7, _ => true), Is.Null);
        });
    }

    // At the adapter (no window of the desktop is read): a window that is really gone still says it could not be read; a
    // look the worker answers is unchanged and says no failure; the answer a look goes on with carries its reason.
    [Test]
    public void AGoneWindowStillFailsAndAWorkingLookIsUnchanged()
    {
        nint gone = GoneWindow();
        ExternalCapabilityReceipt lost = Look(
            """{"ok":false,"error":"visible_controls_uia_failed","detail":"x"}""", gone);
        ExternalCapabilityReceipt read = Look(
            "{\"ok\":true,\"error\":\"\",\"hwnd\":" + (long)gone + ",\"window\":\"Chats\",\"controls\":[" +
            "{\"kind\":\"Button\",\"name\":\"Chats\",\"id\":\"4.2\",\"state\":\"\",\"value\":null,\"rect\":null," +
            "\"repeated\":0}],\"controlCount\":1,\"focused\":null}", gone);
        ExternalCapabilityReceipt without = Look("""{"ok":true,"controls":[],"uiaFailed":"razon"}""", gone);

        Assert.Multiple(() =>
        {
            Assert.That(VisibleControlSurface.IsAlive(gone), Is.False, "the fixture's window is gone");
            Assert.That(lost.Verified, Is.False);
            Assert.That(lost.ErrorCode, Is.EqualTo("visible_controls_uia_failed"));
            Assert.That(read.Verified, Is.True);
            Assert.That(read.Result?.GetProperty("controls").GetArrayLength(), Is.EqualTo(1));
            Assert.That(read.Result?.TryGetProperty("uiaFailed", out _), Is.False);
            Assert.That(without.Verified, Is.True);
            Assert.That(without.Result?.GetProperty("controls").GetArrayLength(), Is.Zero);
            Assert.That(without.Result?.GetProperty("uiaFailed").GetString(), Is.EqualTo("razon"));
        });
    }

    // P2.17 (noche 27-10): a walk the worker did not answer within its budget (a slow tree; the worker is ended) lost the
    // whole look («visible_controls_unavailable»). On a window that is still there the look goes on as one without a tree,
    // read from what it draws, saying the walk did not end; a window that is gone fails as before.
    [Test]
    public void AWalkPastItsBudgetOnAWindowStillThereGoesOnWithoutTreeAndSaysSo()
    {
        using JsonDocument? unfinished = WindowsVisibleControlAdapter.UnfinishedWalk(7, _ => true);
        ExternalCapabilityReceipt gone = Look(null, GoneWindow());

        Assert.Multiple(() =>
        {
            Assert.That(unfinished, Is.Not.Null);
            Assert.That(unfinished!.RootElement.GetProperty("ok").GetBoolean(), Is.True);
            Assert.That(unfinished.RootElement.GetProperty("controls").GetArrayLength(), Is.Zero);
            Assert.That(unfinished.RootElement.GetProperty("partial").GetBoolean(), Is.True);
            Assert.That(unfinished.RootElement.GetProperty("uiaFailed").GetString(),
                Is.EqualTo(WindowsVisibleControlAdapter.UnfinishedWalkReason));
            Assert.That(WindowsVisibleControlAdapter.UnfinishedWalk(7, _ => false), Is.Null);
            // Only a walk that spent the worker's budget did not end; a worker missing or broken answers nothing at once.
            Assert.That(WindowsVisibleControlAdapter.PastWalkBudget(Stopwatch.GetTimestamp()), Is.False);
            Assert.That(WindowsVisibleControlAdapter.PastWalkBudget(
                Stopwatch.GetTimestamp() - (long)(20 * Stopwatch.Frequency)), Is.True);
            Assert.That(gone.Verified, Is.False);
            Assert.That(gone.ErrorCode, Is.EqualTo("visible_controls_unavailable"));
        });
    }

    private static JsonElement Json(string value) => JsonDocument.Parse(value).RootElement.Clone();

    // A null answer: the worker answers nothing, as when its walk outlives WorkerViewBudget.
    private static ExternalCapabilityReceipt Look(string? answer, nint window) =>
        new WindowsVisibleControlAdapter(
                new ComputerUsePerceptionTests.ScriptedUiaWorker(answer is null ? [] : [answer]), null, null, requestedWindow: (_, _) => ValueTask.FromResult(window), elevated: _ => false,
                capture: (_, _, _) => ValueTask.FromResult<VisibleControlSurface.CapturedWindow?>(null))
            .InvokeAsync("input.visible.controls", Json("""{"application":"el navegador"}"""), CancellationToken.None)
            .AsTask().GetAwaiter().GetResult();

    private static nint GoneWindow()
    {
        nint window = CreateWindowEx(0x08000080, "STATIC", "BAXY walk failure gone fixture", 0u, 0, 0, 10, 10, 0, 0, 0, 0);
        Assert.That(window, Is.Not.Zero, $"CreateWindowEx failed: {Marshal.GetLastPInvokeError()}");
        Assert.That(DestroyWindow(window), Is.True);
        return window;
    }

    private static string Run(string body)
    {
        string worker = Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1");
        Assume.That(File.Exists(worker), "the worker script is copied next to the tests");
        string script = """
            $ErrorActionPreference='Stop'
            $tokens=$null;$errors=$null
            $ast=[System.Management.Automation.Language.Parser]::ParseFile($env:BAXY_WALK_WORKER,[ref]$tokens,[ref]$errors)
            if($errors.Count -gt 0){ throw 'worker does not parse' }
            foreach($name in ($env:BAXY_WALK_FUNCTIONS -split ',')){
              $found=@($ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name },$true))
              if($found.Count -ne 1){ throw ('function missing: '+$name) }
              . ([scriptblock]::Create($found[0].Extent.Text))
            }

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
        {
            start.ArgumentList.Add(argument);
        }

        start.ArgumentList.Add(Convert.ToBase64String(Encoding.Unicode.GetBytes("[Console]::OutputEncoding=[System.Text.Encoding]::UTF8\n" + script)));
        start.Environment["BAXY_WALK_WORKER"] = worker;
        start.Environment["BAXY_WALK_FUNCTIONS"] = string.Join(',', Functions);
        using Process process = Process.Start(start)!;
        Task<string> error = process.StandardError.ReadToEndAsync();
        string output = process.StandardOutput.ReadToEnd();
        Assert.That(process.WaitForExit(60_000), Is.True, "the script answers");
        Assert.That(process.ExitCode, Is.EqualTo(0), error.Result);
        return output.Trim();
    }

    [DllImport("user32.dll", EntryPoint = "CreateWindowExW",
        CharSet = CharSet.Unicode, ExactSpelling = true, SetLastError = true)]
    private static extern nint CreateWindowEx(uint extendedStyle, string className,
        string title, uint style, int x, int y, int width, int height,
        nint parent, nint menu, nint instance, nint parameter);

    [DllImport("user32.dll", ExactSpelling = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool DestroyWindow(nint window);
}
