using System.IO;
using Baxy.Kernel.Journal;
using Baxy.Providers.Windows.External;

namespace Baxy.App;

/// <summary>
/// DIAX11: what the core set right at its start, told once with the truth, as the update's outcome is (LastUpdate): a
/// line in the conversation, and aloud when the voice is there. Two things: a journal tail after its committed end that
/// was set aside (FileInvocationJournal, «missions.jsonl.damaged-…»: a write a power cut or a full disk cut short) or, when
/// no copy could be written, cut back without one («….not-kept»), and the own Edge profile discarded because it held an
/// account (WindowsExternalCapabilityProvider.DiscardOwnBrowserProfilesWithAnAccount).
/// </summary>
internal static class StartRepairs
{
    /// <summary>The set-aside journal tails already told, one file name a line, beside them.</summary>
    internal const string ToldFile = "damaged-told";

    internal static string? OnStart(string dataRoot, bool english, out Action told) =>
        OnStart(dataRoot, english, WindowsExternalCapabilityProvider.OwnBrowserAccountNotice(dataRoot),
            () => WindowsExternalCapabilityProvider.ForgetOwnBrowserAccountNotice(dataRoot), out told);

    /// <param name="browsers">The own browsers whose profile was discarded and not yet told.</param>
    /// <param name="forgetBrowsers">Marks that notice told.</param>
    internal static string? OnStart(string dataRoot, bool english, IReadOnlyList<string> browsers, Action forgetBrowsers,
        out Action told)
    {
        told = static () => { };
        string journal = Path.Combine(dataRoot, "journal");
        string[] tails = SetAsideTails(journal);
        string[] alreadyTold = ReadTold(journal);
        string[] newTails = [.. tails.Where(tail => !alreadyTold.Contains(tail, StringComparer.Ordinal))];
        bool notKept = newTails.Any(tail => tail.EndsWith(FileInvocationJournal.NotKeptSuffix, StringComparison.Ordinal));
        bool kept = newTails.Any(tail => !tail.EndsWith(FileInvocationJournal.NotKeptSuffix, StringComparison.Ordinal));
        if (newTails.Length == 0 && browsers.Count == 0)
        {
            return null;
        }

        told = () =>
        {
            try
            {
                if (newTails.Length > 0)
                {
                    File.AppendAllLines(Path.Combine(journal, ToldFile), newTails);
                }
            }
            catch (Exception refused) when (refused is IOException or UnauthorizedAccessException)
            {
                UnhandledFailures.Record("start.repairs.told", refused);
            }

            if (browsers.Count > 0)
            {
                forgetBrowsers();
            }
        };
        return Line(kept, notKept, browsers.Count > 0, english);
    }

    internal static string Line(bool journalTail, bool tailNotKept, bool browserAccount, bool english)
    {
        var said = new List<string>();
        if (browserAccount)
        {
            // REVX2 DX11-1: what BAXY knows: its own Edge profile held an account (OwnBrowserProfile.IsSignedIn), and Edge
            // can sign in by itself with the Windows one (ImplicitSignInEnabled); not whose account, nor that it synced.
            said.Add(UiLanguage.Say(english,
                "Mi navegador propio, un Edge aparte, tenía una sesión iniciada con una cuenta (Edge puede iniciarla solo"
                + " con la de Windows, y yo no lo impedía). Ya no: lo cerré, borré ese perfil mío y ahora lo abro sin"
                + " sincronizar y sin que inicie sesión solo. Tu navegador y tu cuenta no los toqué.",
                "My own browser, a separate Edge, was signed in with an account (Edge can do that by itself with the"
                + " Windows one, and I did not stop it). Not any more: I closed it, deleted that profile of mine, and now"
                + " open it with no sync and no sign-in of its own. I did not touch your browser or your account."));
        }

        if (journalTail)
        {
            said.Add(UiLanguage.Say(english,
                "Al arrancar encontré a medias la última escritura de mi registro de acciones (pasa con un corte de luz o"
                + " el disco lleno). La aparté sin borrar nada, junto al registro, y seguí con todo lo demás: lo que ya"
                + " había hecho sigue anotado.",
                "On starting I found the last write of my action log half done (a power cut or a full disk does that). I"
                + " set it aside, deleting nothing, beside the log, and went on with everything else: what I had done is"
                + " still recorded."));
        }

        if (tailNotKept)
        {
            said.Add(UiLanguage.Say(english,
                "Al arrancar encontré a medias la última escritura de mi registro de acciones (pasa con un corte de luz o"
                + " el disco lleno). No pude guardar copia de esa parte dañada, así que la quité y seguí con todo lo"
                + " demás: lo que ya había hecho sigue anotado.",
                "On starting I found the last write of my action log half done (a power cut or a full disk does that). I"
                + " could not keep a copy of that damaged part, so I removed it and went on with everything else: what I"
                + " had done is still recorded."));
        }

        return string.Join(' ', said);
    }

    private static string[] SetAsideTails(string journal)
    {
        try
        {
            return Directory.Exists(journal)
                ? [.. Directory.EnumerateFiles(journal, "missions.jsonl" + FileInvocationJournal.DamagedTailMarker + "*")
                    .Select(Path.GetFileName).OfType<string>().Order(StringComparer.Ordinal)]
                : [];
        }
        catch (Exception unread) when (unread is IOException or UnauthorizedAccessException)
        {
            return [];
        }
    }

    private static string[] ReadTold(string journal)
    {
        try
        {
            string file = Path.Combine(journal, ToldFile);
            return File.Exists(file) ? File.ReadAllLines(file) : [];
        }
        catch (Exception unread) when (unread is IOException or UnauthorizedAccessException)
        {
            return [];
        }
    }
}
