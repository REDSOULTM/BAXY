using System.Globalization;
using System.Windows;
using Baxy.Providers.Windows.SystemStatus;

namespace Baxy.App;

/// <summary>
/// INS2 (MIN1): on a PC with 4 GB of RAM, BAXY with no model of its own (window, helpers, mind) took all of it in 9-17 s,
/// before it could say anything, and «use another model» would not have helped. Before anything starts, the App says so
/// with the PC's figures and lets the person choose; the installer told the same before downloading (MachineGpu).
/// </summary>
internal static class StartupRam
{
    /// <summary>Less RAM installed than BAXY takes even thinking with a model by API; unread is not «too little».</summary>
    internal static bool TooLittle(long? installedMib) => installedMib is { } mib && mib < BaxyRamNeed.ByApiMib;

    /// <summary>What the person reads, in GB as the installer says them.</summary>
    internal static string Said(bool english, long installedMib, long? freeMib)
    {
        CultureInfo culture = UiLanguage.CultureOf(english);
        double installed = installedMib / 1024d;
        double free = (freeMib ?? 0) / 1024d;
        double need = BaxyRamNeed.ByApiMib / 1024d;
        return english
            ? string.Format(culture, "This PC has {0:0.#} GB of RAM and {1:0.#} is free now. Windows 11 asks for at least 4, and even thinking with a model by API I use about 2 more for the window, the voice and the mind: I need at least {2:0.#} GB. If I open, this PC may run out of memory before I get to tell you anything, with another model too.\n\nOpen me anyway?", installed, free, need)
            : string.Format(culture, "Este PC tiene {0:0.#} GB de RAM y ahora quedan {1:0.#} libres. Windows 11 pide al menos 4, y yo, aun pensando con un modelo por API, uso unos 2 más con la ventana, la voz y la mente: necesito al menos {2:0.#} GB. Si me abro, este equipo puede quedarse sin memoria antes de que yo alcance a decirte nada, también con otro modelo.\n\n¿Abrirme igual?", installed, free, need);
    }

    /// <summary>True to go on: enough RAM, or the person chose to open anyway. A Windows dialog, read by a screen reader
    /// and answered with the keyboard, since nothing that speaks has started yet; «No» is its default.</summary>
    internal static bool MayStart()
    {
        (long? installed, long? free) = BaxyRamNeed.Read();
        if (!TooLittle(installed))
        {
            return true;
        }

        return MessageBox.Show(
            Said(UiLanguage.IsEnglish, installed!.Value, free),
            "BAXY",
            MessageBoxButton.YesNo,
            MessageBoxImage.Warning,
            MessageBoxResult.No) == MessageBoxResult.Yes;
    }
}
