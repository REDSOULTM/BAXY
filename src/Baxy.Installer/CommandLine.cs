using System.Globalization;

namespace Baxy.Installer;

/// <summary>
/// What the installer was asked to do from its command line, for installing and removing BAXY by script or remote
/// console (W1: tests on a borrowed machine). The options follow Inno Setup's (/DIR=, /SILENT, /HELP, /?) with the
/// double dash of this installer's --quiet; an unknown option is refused rather than ignored.
/// </summary>
internal sealed record CommandLine(
    bool Help = false,
    bool Quiet = false,
    bool Uninstall = false,
    bool UninstallRun = false,
    bool NoVoice = false,
    bool DeleteData = false,
    string? Directory = null,
    int? Original = null,
    string? Error = null)
{
    /// <summary>ERROR_INVALID_COMMAND_LINE, the code Windows Installer gives an argument it does not know.</summary>
    internal const int InvalidCommandLine = 1639;

    internal const string UninstallRunOption = "--uninstall-run";
    internal const string OriginalOption = "--original";

    internal static CommandLine Parse(IReadOnlyList<string> arguments)
    {
        CommandLine command = new();
        for (int index = 0; index < arguments.Count; index++)
        {
            string argument = arguments[index];
            string name = argument.Split('=', 2)[0].ToLowerInvariant();
            string? inline = argument.Contains('=', StringComparison.Ordinal) ? argument.Split('=', 2)[1] : null;
            switch (name)
            {
                case "--help" or "-h" or "/?" or "-?":
                    command = command with { Help = true };
                    break;
                case "--quiet":
                    command = command with { Quiet = true };
                    break;
                case "--uninstall":
                    command = command with { Uninstall = true };
                    break;
                case UninstallRunOption:
                    command = command with { Uninstall = true, UninstallRun = true };
                    break;
                case "--no-voice":
                    command = command with { NoVoice = true };
                    break;
                case "--delete-data":
                    command = command with { DeleteData = true };
                    break;
                case "--dir" or OriginalOption:
                    string? value = inline ?? (index + 1 < arguments.Count ? arguments[++index] : null);
                    if (string.IsNullOrWhiteSpace(value))
                    {
                        return command with { Error = $"{name} needs a value" };
                    }

                    if (name == "--dir")
                    {
                        command = command with { Directory = value };
                    }
                    else if (int.TryParse(value, NumberStyles.None, CultureInfo.InvariantCulture, out int process))
                    {
                        command = command with { Original = process };
                    }
                    else
                    {
                        return command with { Error = $"{name} needs a process id" };
                    }

                    break;
                default:
                    return command with { Error = $"unknown option: {argument}" };
            }
        }

        return command.DeleteData && !command.Uninstall ? command with { Error = "--delete-data only goes with --uninstall" } : command;
    }

    /// <summary>The arguments the copy that uninstalls gets, so it does what the original was asked.</summary>
    internal IReadOnlyList<string> ForTheCopy(string root, int original)
    {
        List<string> copy = [UninstallRunOption, "--dir", root];
        if (Quiet)
        {
            copy.AddRange(["--quiet", OriginalOption, original.ToString(CultureInfo.InvariantCulture)]);
        }

        if (NoVoice)
        {
            copy.Add("--no-voice");
        }

        if (DeleteData)
        {
            copy.Add("--delete-data");
        }

        return copy;
    }

    internal static string HelpText(string language, string defaultRoot) => language == "es"
        ? $"""
          BAXY-Instalador.exe [opciones]

          Sin opciones abre la ventana del instalador.

            --quiet            Instala sin ventana ni voz. Lo que pasa queda en {Program.LogPath}.
            --dir <carpeta>    Instala en esa carpeta (ruta completa) en vez de {defaultRoot}.
                               La carpeta debe no existir, estar vacía o tener ya BAXY.
            --no-voice         La ventana empieza con la voz del instalador apagada (sus frases dicen «BAXY»
                               y despertarían a un BAXY que escuche cerca).
            --uninstall        Desinstala BAXY (con ventana). Con --quiet, sin ventana; sin --dir, quita la
                               instalación registrada en «Aplicaciones instaladas».
            --delete-data      Con --uninstall: borra también los datos de BAXY (%LOCALAPPDATA%\BAXY).
            --help, -h, /?     Muestra esta ayuda.

          Salida: 0 si terminó; {InvalidCommandLine} si una opción no vale; otro número si no pudo terminar.
          Desde PowerShell, para esperar y leer la salida:
            (Start-Process .\BAXY-Instalador.exe -ArgumentList '--quiet' -Wait -PassThru).ExitCode
          """
        : $"""
          BAXY-Instalador.exe [options]

          Without options it opens the installer's window.

            --quiet            Installs with no window and no voice. What happens goes to {Program.LogPath}.
            --dir <folder>     Installs in that folder (a full path) instead of {defaultRoot}.
                               The folder must not exist, be empty, or already hold BAXY.
            --no-voice         The window starts with the installer's voice off (its lines say «BAXY» and
                               would wake a BAXY listening nearby).
            --uninstall        Uninstalls BAXY (with a window). With --quiet, with none; without --dir, it removes
                               the installation registered in «Installed apps».
            --delete-data      With --uninstall: also deletes BAXY's data (%LOCALAPPDATA%\BAXY).
            --help, -h, /?     Shows this help.

          Exit code: 0 when it finished; {InvalidCommandLine} when an option is not valid; any other number when it
          could not finish.
          From PowerShell, to wait and read the exit code:
            (Start-Process .\BAXY-Instalador.exe -ArgumentList '--quiet' -Wait -PassThru).ExitCode
          """;
}
