namespace Baxy.Providers.Windows.External;

/// <summary>
/// The inline scripts of Windows PowerShell 5.1 whose answer <see cref="ExternalProcessRunner"/> reads as UTF-8.
/// Measured on the notebook (Spanish Windows, console code page 850): PowerShell writes its stdout and stderr in the
/// console's code page unless the script switches it, so a calculator's «La expresión» arrived as «La expresi�n»;
/// <see cref="Utf8Output"/> switches it to UTF-8 without a BOM, so a JSON answer still starts with its brace. The setter
/// also moves the console's code page: cmd and netsh followed it; ipconfig still wrote CP850 and pnputil CP1252, so
/// their accents are lost. The script text itself arrives intact (the command line is UTF-16); -Command splits the
/// trailing arguments on spaces, which is why text goes to a script as Base64.
/// </summary>
internal static class PowerShellCommand
{
    /// <summary>The first line of every inline script; the helper .ps1 files started with -File carry the same line.</summary>
    internal const string Utf8Output = "[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false)\n";

    /// <summary>Runs <paramref name="script"/> as a block whose <c>$args</c> are <paramref name="scriptArguments"/>.</summary>
    internal static ValueTask<ExternalProcessResult> RunPowerShellAsync(
        this IExternalProcessRunner runner,
        string script,
        IReadOnlyList<string> scriptArguments,
        TimeSpan timeout,
        CancellationToken cancellationToken) =>
        runner.RunAsync(
            "powershell.exe",
            ["-NoProfile", "-NonInteractive", "-Command", Utf8Output + "& {\n" + script + "\n}", .. scriptArguments],
            timeout,
            cancellationToken);
}
