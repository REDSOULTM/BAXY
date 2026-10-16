using System.Text;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Auditoría del cuaderno, ronda 1: the runner reads a PowerShell child as UTF-8 and Windows PowerShell 5.1 writes in
/// the console's code page, so the calculator's «La expresión» arrived as «La expresi�n» (20 of 20 practice results).
/// A real powershell.exe runs through the shared prologue and through a -File script with the same line, and the text
/// comes back exactly; the helper scripts the product starts carry that line.
/// </summary>
[TestFixture]
public sealed class PowerShellUtf8OutputTests
{
    private const string Text = "Canción ñandú — ¿qué?";

    [Test]
    public async Task AnInlineScriptAnswersItsAccentsExactlyOnStdoutStderrAndJson()
    {
        string encoded = Convert.ToBase64String(Encoding.UTF8.GetBytes(Text));

        ExternalProcessResult result = await new ExternalProcessRunner().RunPowerShellAsync(
            $$"""
            $text=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($args[0]))
            [Console]::Error.WriteLine($text)
            $text
            [pscustomobject]@{fromArgument=$text;fromScript='{{Text}}'}|ConvertTo-Json -Compress
            """,
            [encoded],
            TimeSpan.FromSeconds(60),
            CancellationToken.None);

        string[] lines = result.Output.Split(['\r', '\n'], StringSplitOptions.RemoveEmptyEntries);
        Assert.That(result.ExitCode, Is.Zero, result.Error);
        Assert.That(lines, Has.Length.EqualTo(2), result.Output);
        using JsonDocument answer = JsonDocument.Parse(lines[1]);
        Assert.Multiple(() =>
        {
            Assert.That(lines[0], Is.EqualTo(Text), "stdout, from its first character");
            Assert.That(answer.RootElement.GetProperty("fromArgument").GetString(), Is.EqualTo(Text));
            Assert.That(answer.RootElement.GetProperty("fromScript").GetString(), Is.EqualTo(Text));
            Assert.That(result.Error.Trim(), Is.EqualTo(Text), "stderr");
        });
    }

    [Test]
    public async Task AFileScriptWithTheSameLineAnswersItsArgumentExactly()
    {
        string folder = Path.Combine(Path.GetTempPath(), "baxy-ps-utf8-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(folder);
        try
        {
            string script = Path.Combine(folder, "answer.ps1");
            File.WriteAllText(
                script,
                "param([string]$Text)\n" + PowerShellCommand.Utf8Output
                    + "[pscustomobject]@{text=$Text}|ConvertTo-Json -Compress\n",
                new UTF8Encoding(false));

            ExternalProcessResult result = await new ExternalProcessRunner().RunAsync(
                "powershell.exe",
                ["-NoProfile", "-NonInteractive", "-File", script, "-Text", Text],
                TimeSpan.FromSeconds(60),
                CancellationToken.None);

            Assert.That(result.ExitCode, Is.Zero, result.Error);
            using JsonDocument answer = JsonDocument.Parse(result.Output);
            Assert.That(answer.RootElement.GetProperty("text").GetString(), Is.EqualTo(Text));
        }
        finally
        {
            Directory.Delete(folder, recursive: true);
        }
    }

    [TestCase("DesktopKeyPress.ps1")]
    [TestCase("DesktopSelectAll.ps1")]
    [TestCase("DesktopUiaWorker.ps1")]
    [TestCase("KnownFileOpen.ps1")]
    [TestCase("KnownFolderOpen.ps1")]
    [TestCase("SpotifyDesktopAutomation.ps1")]
    public void EachHelperScriptTheProductReadsWritesUtf8(string name)
    {
        string[] lines = File.ReadAllLines(Path.Combine(AppContext.BaseDirectory, name));

        Assert.That(lines, Does.Contain(PowerShellCommand.Utf8Output.TrimEnd('\n')));
    }

    // The helper scripts have no BOM and PowerShell 5.1 reads such a file as ANSI: a character beyond ASCII in their
    // code would arrive as two or three others (the worker's full-width colon «：» became «ï¼š»), so it goes as an
    // escape; only the comments, PowerShell's and those of the C# they compile, keep their accents.
    [TestCase("DesktopKeyPress.ps1")]
    [TestCase("DesktopSelectAll.ps1")]
    [TestCase("DesktopUiaWorker.ps1")]
    [TestCase("KnownFileOpen.ps1")]
    [TestCase("KnownFolderOpen.ps1")]
    [TestCase("SpotifyDesktopAutomation.ps1")]
    public void EachHelperScriptKeepsItsCodeAscii(string name)
    {
        string[] beyondAscii = File.ReadAllLines(Path.Combine(AppContext.BaseDirectory, name))
            .Select(line => line.Trim())
            .Where(line => !line.StartsWith('#') && !line.StartsWith("//", StringComparison.Ordinal))
            .Where(line => line.Any(character => character > '\x7f'))
            .ToArray();

        Assert.That(beyondAscii, Is.Empty);
    }
}
