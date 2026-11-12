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
    bool Update = false,
    string? Directory = null,
    int? Original = null,
    string? Error = null)
{
    /// <summary>ERROR_INVALID_COMMAND_LINE, the code Windows Installer gives an argument it does not know.</summary>
    internal const int InvalidCommandLine = 1639;

    /// <summary>
    /// ERROR_UNKNOWN_PRODUCT, what Windows Installer answers an uninstall of something not installed («This action is
    /// only valid for products that are currently installed», Microsoft Learn, «MsiExec.exe and InstMsi.exe Error
    /// Messages»): an uninstall that found no BAXY where it was pointed (UNI1, REV8 U2).
    /// </summary>
    internal const int NotInstalled = 1605;

    internal const string UninstallRunOption = "--uninstall-run";

    /// <summary>The language of what is told: Spanish on a Spanish Windows, else English.</summary>
    internal static string Language => CultureInfo.CurrentUICulture.TwoLetterISOLanguageName == "es" ? "es" : "en";
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
                case "--update":
                    command = command with { Update = true };
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

        return command.DeleteData && !command.Uninstall ? command with { Error = "--delete-data only goes with --uninstall" }
            : command.Update && command.Uninstall ? command with { Error = "--update does not go with --uninstall" }
            : command;
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

    /// <summary>UNI1 (REV8 U2): an uninstall that found no BAXY where it was pointed, told before anything is touched.</summary>
    internal static string NothingToUninstall(string language, string folder) => language == "es"
        ? $"No hay ninguna BAXY en {folder}: no desinstalé nada y no toqué tus datos."
        : $"There is no BAXY in {folder}: I uninstalled nothing and didn’t touch your data.";

    /// <summary>UNI1 (REV8 U1): --delete-data of data another installed BAXY uses.</summary>
    internal static string DataStays(string language, string otherBaxy, string data) => language == "es"
        ? $"No desinstalé nada: la otra BAXY, en {otherBaxy}, usa tus datos ({data}). Para conservarlos, desinstala sin --delete-data."
        : $"I uninstalled nothing: the other BAXY, in {otherBaxy}, uses your data ({data}). To keep it, uninstall without --delete-data.";

    internal static string HelpText(string language, string defaultRoot) => language == "es"
        ? $"""
          BAXY-Instalador.exe [opciones]

          Sin opciones abre la ventana del instalador.

            --quiet            Instala sin ventana ni voz. Lo que pasa queda en {Program.LogPath}.
                               No muestra el acuerdo de licencia. La próxima actualización con ventana lo
                               muestra si no es el último que se aceptó en una ventana.
            --dir <carpeta>    Instala en esa carpeta (ruta completa) en vez de {defaultRoot}.
                               La carpeta debe no existir, estar vacía o tener ya BAXY.
            --no-voice         La ventana empieza con la voz del instalador apagada (sus frases dicen «BAXY»
                               y despertarían a un BAXY que escuche cerca).
            --uninstall        Desinstala BAXY (con ventana). Con --quiet, sin ventana; sin --dir, quita la
                               instalación donde está este instalador o, si no, la registrada en
                               «Aplicaciones instaladas». Donde no hay BAXY no hace nada y sale con {NotInstalled}.
            --delete-data      Con --uninstall: borra también los datos de BAXY (%LOCALAPPDATA%\BAXY).
                               Si otra BAXY instalada los usa, no hace nada y sale con 1.
            --update           Lo usa BAXY al actualizarse: espera a que BAXY se cierre, instala (ya dijiste que
                               sí en BAXY) y la vuelve a abrir. Si el acuerdo de licencia no es el que aceptaste,
                               antes lo muestra: sin aceptarlo no instala y vuelve a abrir la que tenías.
                               Si falla, la cancelas o cierras la ventana antes de cambiarla, también vuelve
                               a abrir la que tenías. Antes de bajar nada mira el espacio libre.
                               El instalador no toca tus datos.
                               Con --quiet no la abre: instala y termina.
            --help, -h, /?     Muestra esta ayuda.

          Salida:
            0      terminó.
            {QuietInstall.NotRegistered}      BAXY quedó instalada, pero sin acceso en Inicio o sin entrada en «Aplicaciones instaladas»:
                   Windows no dejó crearlos. Al repetir la instalación se intenta otra vez.
            {QuietInstall.NoGraphicsCard}   este PC no tiene tarjeta gráfica NVIDIA, AMD ni Intel: BAXY no funciona aquí. No se bajó nada.
            {NotInstalled}   --uninstall no encontró ninguna BAXY: no se tocó nada.
            {InvalidCommandLine}   una opción no vale.
            otro   no pudo terminar. El motivo queda en {Program.LogPath}.
          Con ventana, lo mismo: si se cierra sin haber terminado (BAXY seguía abierta, falló o la cancelaste),
          sale con {Program.Failure}. --uninstall con ventana sale enseguida con 0: la desinstalación sigue en otra ventana.
          Desde PowerShell, para esperar y leer la salida:
            (Start-Process .\BAXY-Instalador.exe -ArgumentList '--quiet' -Wait -PassThru).ExitCode
          """
        : $"""
          BAXY-Instalador.exe [options]

          Without options it opens the installer's window.

            --quiet            Installs with no window and no voice. What happens goes to {Program.LogPath}.
                               It does not show the license agreement. The next update with a window shows it
                               if it is not the last one accepted in a window.
            --dir <folder>     Installs in that folder (a full path) instead of {defaultRoot}.
                               The folder must not exist, be empty, or already hold BAXY.
            --no-voice         The window starts with the installer's voice off (its lines say «BAXY» and
                               would wake a BAXY listening nearby).
            --uninstall        Uninstalls BAXY (with a window). With --quiet, with none; without --dir, it removes
                               the installation this installer is in or, if none, the one registered in
                               «Installed apps». Where there is no BAXY it does nothing and exits with {NotInstalled}.
            --delete-data      With --uninstall: also deletes BAXY's data (%LOCALAPPDATA%\BAXY).
                               If another installed BAXY uses it, it does nothing and exits with 1.
            --update           Used by BAXY to update itself: waits for BAXY to close, installs (you said yes in
                               BAXY) and opens it again. If the license agreement is not the one you accepted, it
                               shows it first: without accepting it nothing is installed and the one you had opens again.
                               If it fails, you cancel it or close the window before it is replaced, the one
                               you had opens again too. Before downloading anything it checks the free space.
                               The installer does not touch your data.
                               With --quiet it does not open it: it installs and ends.
            --help, -h, /?     Shows this help.

          Exit code:
            0      it finished.
            {QuietInstall.NotRegistered}      BAXY is installed, but has no Start menu shortcut or no entry in «Installed apps»:
                   Windows did not let it create them. Installing again tries once more.
            {QuietInstall.NoGraphicsCard}   this PC has no NVIDIA, AMD or Intel graphics card: BAXY does not work here. Nothing was downloaded.
            {NotInstalled}   --uninstall found no BAXY: nothing was touched.
            {InvalidCommandLine}   an option is not valid.
            other  it could not finish. The reason is in {Program.LogPath}.
          With a window, the same: if it closes before finishing (BAXY was still open, it failed or you
          cancelled it), it exits with {Program.Failure}. --uninstall with a window exits at once with 0: the uninstall goes on in another window.
          From PowerShell, to wait and read the exit code:
            (Start-Process .\BAXY-Instalador.exe -ArgumentList '--quiet' -Wait -PassThru).ExitCode
          """;
}
