using System.Diagnostics;
using System.Text;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Regresiones r2 M4 and molestia r2 (rama B, punto 2): the Calculator's expression is pressed on its own buttons by UI
/// Automation's Invoke, never typed with SendInput into a window brought to the front. Each character is the button
/// the keypad data names (keypad_keys.v1.json, Spanish and English), and the result is verified on the display. The
/// script's functions run over described buttons: no window is read or touched.
/// </summary>
[TestFixture]
public sealed class KeypadInvokeTests
{
    private static readonly string[] Spanish =
    [
        "Cero", "Uno", "Dos", "Tres", "Cuatro", "Cinco", "Seis", "Siete", "Ocho", "Nueve",
        "Más", "Menos", "Multiplicar por", "Dividir por", "Es igual a", "Separador decimal", "Borrar entrada", "Borrar",
        "Porcentaje",
    ];

    private static readonly string[] English =
    [
        "Zero", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
        "Plus", "Minus", "Multiply by", "Divide by", "Equals", "Decimal separator", "Clear entry", "Clear",
    ];

    [Test]
    public void EveryCharacterIsTheButtonTheDataNamesInEitherLanguage()
    {
        string answer = Run($$"""
            $es=[string[]]@({{Quoted(Spanish)}})
            $en=[string[]]@({{Quoted(English)}})
            function Plan($keys,$names){ $plan=Select-KeypadPresses $keys $names $map; if($null -eq $plan){ 'none' } else { ($plan -join ' ') } }
            $answers=@(
              (Plan '6*7=' $es),
              (Plan '1.5/2=' $en),
              (Plan '12-3=' $es),
              (Plan '(1+2)=' $es),
              (Plan '6*7=' ([string[]]@('Seis','Siete','Multiplicar por'))),
              [string](Find-KeypadButton $es @($map.clear)),
              [string](Find-KeypadButton $en @($map.clear))
            )
            [Console]::Out.Write(($answers -join ','))
            """);

        Assert.That(answer.Split(','), Is.EqualTo(new[]
        {
            "6 12 7 14",     // «Seis», «Multiplicar por», «Siete», «Es igual a»
            "1 15 5 13 2 14",
            "1 2 11 3 14",
            "none",          // counter-case: a character the keypad data names no button for presses nothing at all
            "none",          // counter-case: no «=» button, nothing is pressed
            "17",            // «Borrar» empties the entry, never «Borrar entrada» nor «Porcentaje»
            "17",
        }));
    }

    [Test]
    public void TheResultIsVerifiedOnTheDisplay()
    {
        string answer = Run("""
            $answers=@(
              [string](Test-ShowsLastOperand 'La expresión es 6 × 7=' '42' '6*7'),
              [string](Test-ShowsLastOperand '5 × 4=' '20' '2+3*4'),
              [string](Test-ShowsLastOperand '1,5 ÷ 2=' '0,75' '1.5/2'),
              [string](Test-ShowsLastOperand '6 × 8=' '48' '6*7'),
              [string](Test-ShowsLastOperand '6 × 7=' 'No se puede dividir' '6*7'),
              [string](Test-ShowsLastOperand '' '42' '6*7'),
              [string](Test-ShowsLastOperand '' '0' '6-6'),
              [string](Test-ShowsLastOperand '' '0,00' '6*0'),
              [string](Test-ShowsZero '0'),
              [string](Test-ShowsZero '-0,0'),
              [string](Test-ShowsZero '42'),
              [string](Test-ShowsZero '0,5')
            )
            [Console]::Out.Write(($answers -join ','))
            """);

        Assert.That(answer.Split(','), Is.EqualTo(new[]
        {
            "True",  // the expression line ends with the operand pressed and the display shows a number
            "True",  // Standard mode folds the earlier operands: the last one pressed shows
            "True",
            "False", // counter-case: another operand on the display
            "False", // counter-case: no number on the display
            "True",  // a mode without the expression line: a number other than the 0 «Borrar» left is the proof
            "False", // review r4 counter-case: without the expression line a 0 is not told from ignored presses
            "False",
            "True",  // what «Borrar» must leave on the display before any press
            "True",
            "False",
            "False",
        }));
    }

    [Test]
    public void TheCalculatorScriptSendsNoKeyAndBringsNoWindowUp()
    {
        string script = WindowsDeviceControlAdapter.CalculatorScript;
        Assert.Multiple(() =>
        {
            Assert.That(script, Does.Not.Contain("SendInput").And.Not.Contain("BaxyMarkedKeys"));
            Assert.That(script, Does.Not.Contain("SetForegroundWindow").And.Not.Contain("calculator_not_foreground"));
            Assert.That(script, Does.Contain("InvokePattern"));
            Assert.That(script, Does.Contain("Select-KeypadPresses"));
        });
    }

    // Review r4: a keypad that ignored the presses (the window suspended) left the previous result on the display,
    // read as the new expression's. The clear button is required (no button, nothing pressed) and the display must read
    // 0 after it before any other press.
    [Test]
    public void TheClearButtonIsRequiredAndMustLeaveZeroBeforeAnyPress()
    {
        string script = WindowsDeviceControlAdapter.CalculatorScript;
        int clearRequired = script.IndexOf("if($clear -lt 0){[pscustomobject]@{ok=$false;error='calculator_button_not_found'}", StringComparison.Ordinal);
        int zeroRequired = script.IndexOf("if(-not (Test-ShowsZero $cleared)){[pscustomobject]@{ok=$false;error='calculator_display_not_verified'", StringComparison.Ordinal);
        int firstPress = script.IndexOf("foreach($at in $plan)", StringComparison.Ordinal);
        Assert.Multiple(() =>
        {
            Assert.That(clearRequired, Is.GreaterThan(0));
            Assert.That(zeroRequired, Is.GreaterThan(clearRequired));
            Assert.That(firstPress, Is.GreaterThan(zeroRequired), "the expression is pressed only after the display read 0");
            Assert.That(script, Does.Not.Contain("if($clear -ge 0)"), "the clear button is no longer optional");
        });
    }

    // Renew al máximo (rendimiento): the display after the last press was read once after a fixed 300 ms. It is read
    // every 50 ms within the same 300 ms and taken at the second identical read that shows the last operand; a display
    // that never shows it is read at 300 ms, as before, for the caller's check to refuse.
    [Test]
    public void TheResultIsTakenWhenTheDisplayShowsItWithinTheSameBudget()
    {
        string answer = Run("""
            function Timed($reads,$keys){
              $count=@{n=0}
              $read={ $at=[Math]::Min($count.n,$reads.Count-1); $count.n++; $reads[$at] }
              $clock=[Diagnostics.Stopwatch]::StartNew()
              $got=Wait-ShownResult $read $keys 300 50
              return @($got.value,$count.n,$clock.ElapsedMilliseconds)
            }
            $shown=@{name='Se muestra 42';expr='6 × 7=';value='42'}
            $settled=Timed @($shown) '6*7'
            $wrong=Timed @(@{name='Se muestra 48';expr='6 × 8=';value='48'}) '6*7'
            $late=Timed @(@{name='Se muestra 7';expr='6 ×';value='7'},$shown) '6*7'
            $bare=Timed @(@{name='Se muestra 6';expr='';value='6'},@{name='Se muestra 42';expr='';value='42'}) '6*7'
            [Console]::Out.Write((@($settled,$wrong,$late,$bare) | ForEach-Object { $_ -join ' ' }) -join ',')
            """);

        string[][] runs = answer.Split(',').Select(run => run.Split(' ')).ToArray();
        Assert.Multiple(() =>
        {
            // Shown at once: taken at the second read, well before the 300 ms the fixed wait took.
            Assert.That(runs[0][0], Is.EqualTo("42"));
            Assert.That(runs[0][1], Is.EqualTo("2"));
            Assert.That(long.Parse(runs[0][2], System.Globalization.CultureInfo.InvariantCulture), Is.LessThan(250));
            // Counter-case: a display that never shows the last operand is read until the 300 ms, and that read goes
            // to the caller's check (which refuses it), as before.
            Assert.That(runs[1][0], Is.EqualTo("48"));
            Assert.That(long.Parse(runs[1][2], System.Globalization.CultureInfo.InvariantCulture), Is.GreaterThanOrEqualTo(300));
            // Counter-case: the expression not yet shown is waited for.
            Assert.That(runs[2][0], Is.EqualTo("42"));
            Assert.That(runs[2][1], Is.EqualTo("3"));
            // Counter-case: without the expression line a first number is not taken until it reads the same twice.
            Assert.That(runs[3][0], Is.EqualTo("42"));
            Assert.That(runs[3][1], Is.EqualTo("3"));
        });
    }

    [Test]
    public void TheDisplayAfterThePressesIsPolledNotWaitedForWhole()
    {
        string script = WindowsDeviceControlAdapter.CalculatorScript;
        Assert.Multiple(() =>
        {
            Assert.That(script, Does.Not.Contain("Start-Sleep -Milliseconds 300"));
            Assert.That(script, Does.Contain("Wait-ShownResult $read $keys 300 50"));
        });
    }

    private static string Quoted(IEnumerable<string> names) =>
        string.Join(",", names.Select(name => "'" + name.Replace("'", "''", StringComparison.Ordinal) + "'"));

    private static string Run(string body)
    {
        string keys;
        using (Stream stream = typeof(WindowsDeviceControlAdapter).Assembly.GetManifestResourceStream("Baxy.Providers.Windows.KeypadKeys.json")!)
        using (var reader = new StreamReader(stream, Encoding.UTF8))
        {
            keys = reader.ReadToEnd();
        }

        string script = "$ErrorActionPreference='Stop'\n"
            + "$map=([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($env:BAXY_KEYPAD_KEYS)) | ConvertFrom-Json)\n"
            + WindowsDeviceControlAdapter.KeypadFunctions + "\n" + body;
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

        start.ArgumentList.Add(Convert.ToBase64String(Encoding.Unicode.GetBytes(script)));
        start.Environment["BAXY_KEYPAD_KEYS"] = Convert.ToBase64String(Encoding.UTF8.GetBytes(keys));
        using Process process = Process.Start(start)!;
        Task<string> error = process.StandardError.ReadToEndAsync();
        string output = process.StandardOutput.ReadToEnd();
        Assert.That(process.WaitForExit(60_000), Is.True, "the script answers");
        Assert.That(process.ExitCode, Is.EqualTo(0), error.Result);
        return output.Trim();
    }
}
