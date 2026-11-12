using System.Security.Cryptography;
using System.Text;

namespace Baxy.Installer;

/// <summary>
/// PRV2 (decisión A5 del líder, 2026-11-10; INFORME_INS1, INS-10): an update installed a new agreement without showing it.
/// Now the window shows it, and asks for it to be accepted, when its text is not the one the installation accepted; the
/// same text is not shown again. What was accepted is kept as the SHA-256 of the agreement (both languages, line endings
/// as LF so a checkout's CRLF changes nothing) in the installation's licenses folder, written when the window installs.
/// An installation that never wrote it (every one before this version, or one installed only with --quiet) counts as
/// «not known» and is shown the agreement once. --quiet shows nothing, as it always did, records no acceptance and keeps
/// the fingerprint of the installation it replaces: the next update with a window shows the agreement if it is not the
/// last one accepted in a window.
/// The usual installers do the same: Inno Setup's license page is skipped by /SILENT and /VERYSILENT («the wizard and
/// the background window are not displayed», https://jrsoftware.org/ishelp/topic_setupcmdline.htm), and Valve keeps the
/// version of the EULA a user signed and asks again only for a newer one (ISteamUGC, WorkshopEULAStatus_t: «m_unVersion:
/// the version of the signed EULA», «m_bNeedsAction: true if the user needs to accept the latest Workshop EULA»,
/// https://partner.steamgames.com/doc/api/ISteamUGC). Both read 2026-11-10.
/// </summary>
internal static class AcceptedAgreement
{
    /// <summary>The fingerprint's file, beside the agreement the installer copies (WindowsIntegration.Register).</summary>
    internal const string FileName = "BAXY-acuerdo-aceptado.sha256";

    /// <summary>The fingerprint of the agreement this installer carries.</summary>
    internal static string Current { get; } = Of(WindowsIntegration.LicenseText("es"), WindowsIntegration.LicenseText("en"));

    internal static string Of(string spanish, string english)
    {
        string whole = Lf(spanish) + "\0" + Lf(english);
        return Convert.ToHexStringLower(SHA256.HashData(Encoding.UTF8.GetBytes(whole)));
    }

    /// <summary>The fingerprint the installation in <paramref name="paths"/> accepted, or null: none written, unreadable.</summary>
    internal static string? Read(InstallPaths paths)
    {
        try
        {
            string text = File.ReadAllText(PathIn(paths)).Trim();
            return text.Length == 64 && text.All(char.IsAsciiHexDigitLower) ? text : null;
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            return null;
        }
    }

    /// <summary>
    /// Whether the window must show the agreement and ask for it before installing: BAXY is already in the folder (an
    /// update; a first install says «by installing me you accept my license» on its greeting, as before) and what it
    /// accepted is not this text, or is not known.
    /// </summary>
    internal static bool MustBeAccepted(InstallPaths paths, string? accepted) => paths.HoldsBaxy && accepted != Current;

    /// <summary>Writes <paramref name="fingerprint"/> as accepted in <paramref name="paths"/>; what Windows refuses is
    /// logged and the next update shows the agreement once more.</summary>
    internal static void Write(InstallPaths paths, string fingerprint, Action<string>? log = null)
    {
        try
        {
            Directory.CreateDirectory(Path.GetDirectoryName(PathIn(paths))!);
            File.WriteAllText(PathIn(paths), fingerprint + Environment.NewLine);
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            log?.Invoke($"the accepted agreement was not recorded: {exception.Message}");
        }
    }

    private static string PathIn(InstallPaths paths) => Path.Combine(paths.Root, "licenses", FileName);

    private static string Lf(string text) => text.Replace("\r\n", "\n", StringComparison.Ordinal);
}
