namespace Baxy.Core.Operations;

/// <summary>
/// Where baxy.update keeps the installer it downloads (<see cref="BaxyUpdateHandler"/>): &lt;data&gt;\updates, under its
/// version, as a «.part» until its bytes are the published ones. The App links this file (Baxy.App.csproj) to say how much
/// of a download is here while the engine still answers nothing (UpdatePanel).
/// </summary>
internal static class UpdateInstallerFile
{
    /// <summary>
    /// REV_APP UPD-b (2026-11-09): how long the engine gives the download and its check. The App waits longer than this
    /// for the answer (UpdatePanel.InstallTimeout), so the engine never starts an installer after the App stopped waiting.
    /// </summary>
    internal static readonly TimeSpan Budget = TimeSpan.FromMinutes(9);

    internal static string Folder(string dataRoot) => System.IO.Path.Combine(dataRoot, "updates");

    internal static string Target(string dataRoot, string version) =>
        System.IO.Path.Combine(Folder(dataRoot), $"BAXY-Instalador-{version}.exe");

    internal static string Partial(string target) => target + ".part";
}
