using System.Diagnostics;
using System.IO;

namespace Baxy.App;

/// <summary>
/// AUT2 (encargo: «sólo con un "sí, lo acepto" de la persona […] deja apuntada la aceptación con la huella del texto y
/// sigue sin ventana»; norma «todo por voz»). An update's new license agreement, once the person accepted it in their own
/// words (NativeTurnLoop.AnswerAgreementAsync): its fingerprint is written where the installer keeps what was accepted
/// (src/Baxy.Installer/AcceptedAgreement.cs, the installation's licenses\BAXY-acuerdo-aceptado.sha256), so the update
/// then runs with no window. And the text the engine downloaded and checked against the signed release, read or opened
/// when the person asks for it. The usual shape of a license accepted inside an app: Valve keeps the version of the EULA a
/// user signed and asks again only for a newer one (ISteamUGC, WorkshopEULAStatus_t, read 2026-11-10, PRV2).
/// </summary>
internal static class AgreementAcceptance
{
    private const string FileName = "BAXY-acuerdo-aceptado.sha256";

    /// <summary>The installation this App runs from: the folder above app\, where the installer keeps its licenses.</summary>
    internal static string Root { get; set; } =
        Path.GetDirectoryName(Path.TrimEndingDirectorySeparator(AppContext.BaseDirectory)) ?? AppContext.BaseDirectory;

    /// <summary>Writes the accepted fingerprint; null when written, else why not.</summary>
    internal static string? Write(string fingerprint)
    {
        if (fingerprint.Length != 64 || !fingerprint.All(char.IsAsciiHexDigitLower))
        {
            return "not_a_fingerprint";
        }

        try
        {
            string licenses = Path.Combine(Root, "licenses");
            Directory.CreateDirectory(licenses);
            File.WriteAllText(Path.Combine(licenses, FileName), fingerprint + Environment.NewLine);
            return null;
        }
        catch (Exception refused) when (refused is IOException or UnauthorizedAccessException)
        {
            return refused.GetType().Name;
        }
    }

    /// <summary>The agreement's text the engine left in the profile's updates folder; null when it cannot be read.</summary>
    internal static string? Text(string path)
    {
        try
        {
            return File.ReadAllText(path);
        }
        catch (Exception unread) when (unread is IOException or UnauthorizedAccessException or ArgumentException)
        {
            return null;
        }
    }

    /// <summary>Opens the agreement's text with the program Windows gives .txt files; false when it did not start.</summary>
    internal static bool Open(string path)
    {
        try
        {
            using Process? started = Process.Start(new ProcessStartInfo(path) { UseShellExecute = true });
            return File.Exists(path);
        }
        catch (Exception refused) when (refused is System.ComponentModel.Win32Exception or InvalidOperationException
            or FileNotFoundException)
        {
            return false;
        }
    }
}
