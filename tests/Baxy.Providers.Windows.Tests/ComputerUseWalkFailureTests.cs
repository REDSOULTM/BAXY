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

    // The shape of wab3 with neutral text: a chat preview whose emoji straddles the 60th character, another whose emoji
    // straddles the start of the kept end; the first look (no words) and the look after the click (with the contact's
    // name) over more controls than the cap.
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
            $prefix='Contacto B 22:55 Persona C : texto de ejemplo '
            $head=$prefix+('x'*(59-$prefix.Length))+$flower+' sigue el texto de ejemplo ... Chat silenciado'
            $tail=('Contacto D '+('y'*80))+$flower+('z'*15)
            $old=$head.Substring(0,60)
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
              [string]$cutHead.EndsWith('Chat silenciado'),
              [string]$cutHead.StartsWith($prefix),
              [string]((Format-Name $plain) -ceq (('A'*60)+' ... '+('B'*16))),
              [string]$first.controls.Count,
              [string]$after.controls.Count,
              [string]$after.reserved,
              [string]$after.controls[60].name) -join '|'))
            """);
        Assert.That(answer.Split('|'), Is.EqualTo(new[]
        {
            "True",   // the old cut left half an emoji, and folding it threw: the look of wab3
            "False",  // the start kept is whole
            "False",  // the end kept is whole
            "True", "True",
            "True",   // contracase: a name without pairs is cut exactly as before
            "60",     // the look before the click, unchanged
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
            "{\"i\":0,\"kind\":\"Button\",\"name\":\"Chats\",\"id\":\"4.2\",\"state\":\"\",\"value\":null,\"rect\":null," +
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

    private static JsonElement Json(string value) => JsonDocument.Parse(value).RootElement.Clone();

    private static ExternalCapabilityReceipt Look(string answer, nint window) =>
        new WindowsVisibleControlAdapter(
                new ComputerUsePerceptionTests.ScriptedUiaWorker(answer), null, null, browserWindow: new FixedWindow(window), elevated: _ => false,
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

    private sealed class FixedWindow(nint handle) : IUserBrowserWindowLocator
    {
        public nint FrontWindow() => handle;
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
