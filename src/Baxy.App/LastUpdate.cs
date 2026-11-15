using System.IO;
using Baxy.Installer;

namespace Baxy.App;

/// <summary>
/// AUT1 (orden del dueño, 13-11-2026: «decir Baxi actualízate y que se actualice automáticamente»): what the BAXY that
/// opens after an update does with how it ended, which the installer left written in the profile's updates folder
/// (<see cref="UpdateOutcome"/>). The new BAXY says it started, so the installer lets the old one go (until then it is
/// kept, and comes back if this one never says so); and the outcome is told once, from that file and never from memory:
/// that it updated and to which version, or that it could not, why, and which version it still is. A line of the App in
/// the conversation, as a routine said at its time is (FieldProductChannel.RoutineSaidLine), said aloud with BAXY's voice.
/// </summary>
internal static class LastUpdate
{
    /// <summary>
    /// With the engine ready: confirms this BAXY to the installer that waits for it, and gives the line to tell, or null
    /// when there is nothing new to tell. <paramref name="told"/> is called once the line was told.
    /// </summary>
    internal static string? OnStart(string folder, string? installed, bool english, out Action told)
    {
        told = static () => { };
        if (installed is null || UpdateOutcome.Read(folder) is not { } outcome)
        {
            return null;
        }

        try
        {
            if (outcome.State == UpdateOutcome.Started && outcome.To == installed)
            {
                UpdateOutcome.Confirm(folder, installed);
            }

            if (outcome.WasTold(folder))
            {
                return null;
            }
        }
        catch (Exception refused) when (refused is IOException or UnauthorizedAccessException)
        {
            // The folder cannot be written: the installer goes back to the BAXY before, and nothing is told twice.
            return null;
        }

        told = () =>
        {
            try
            {
                outcome.MarkTold(folder);
            }
            catch (Exception refused) when (refused is IOException or UnauthorizedAccessException)
            {
                UnhandledFailures.Record("update.told", refused);
            }
        };
        return Line(outcome, installed, english);
    }

    /// <summary>The outcome in words, for the BAXY of version <paramref name="installed"/>; null when it is not about it.</summary>
    internal static string? Line(UpdateOutcome outcome, string installed, bool english)
    {
        if (outcome.Updated)
        {
            return outcome.To == installed
                ? UiLanguage.Say(english, $"Me actualicé a la {outcome.To}.", $"I updated to {outcome.To}.")
                : null;
        }

        if (outcome.From != installed)
        {
            return null;
        }

        if (outcome.State == UpdateOutcome.RolledBack)
        {
            return UiLanguage.Say(
                english,
                $"Instalé la {outcome.To}, pero no arrancó: volví a la {outcome.From}, que es la que tienes ahora.",
                $"I installed {outcome.To}, but it didn’t start: I went back to {outcome.From}, the one you have now.");
        }

        (string es, string en) = outcome.Reason switch
        {
            "network" => ("se cortó la conexión mientras bajaba; lo que bajé queda guardado y la próxima vez sigo desde ahí",
                "the connection dropped while I was downloading; what I downloaded is kept and next time I go on from there"),
            "slow" => ("la bajada iba tan lenta que preferí no dejarte más tiempo sin mí; lo que bajé queda guardado y la próxima vez sigo desde ahí",
                "the download was so slow that I’d rather not leave you without me any longer; what I downloaded is kept and next time I go on from there"),
            "disk" => ("falta espacio en el disco", "there isn’t enough free disk space"),
            "damaged" => ("un fichero llegó distinto de lo publicado y no lo instalé", "a file arrived different from what was published and I didn’t install it"),
            "unsigned" => ("no pude comprobar que la versión publicada venga firmada por BAXY", "I couldn’t check that the published version is signed by BAXY"),
            "open" => ("no llegué a cerrarme para poder cambiarme", "I didn’t get to close so that I could be replaced"),
            "older" => ("la versión que tienes es más nueva que la publicada", "the version you have is newer than the published one"),
            "windows" => ("Windows no pudo instalar un componente que necesito", "Windows couldn’t install a component I need"),
            _ => ("algo falló antes de cambiar nada", "something failed before anything was changed"),
        };
        return UiLanguage.Say(
            english,
            $"No pude actualizarme a la {outcome.To}: {es}. No cambié nada: sigo en la {outcome.From}.",
            $"I couldn’t update to {outcome.To}: {en}. I changed nothing: I’m still on {outcome.From}.");
    }
}
