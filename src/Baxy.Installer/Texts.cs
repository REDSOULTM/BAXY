using System.Globalization;

namespace Baxy.Installer;

/// <summary>What BAXY says in its installer, in the first person and tuteando, as in documentacion/00_IDENTIDAD.md.
/// An underscore marks a button's Alt key. What it says aloud is in Assets/voice/lines.json.</summary>
internal sealed class Texts
{
    internal required string Language { get; init; }
    internal required string PreferencesName { get; init; }
    internal required string FaceHappy { get; init; }
    internal required string FaceAsleep { get; init; }
    internal required string FaceWaking { get; init; }
    internal required string FaceSad { get; init; }
    internal required string VoiceLabel { get; init; }
    internal required string On { get; init; }
    internal required string Off { get; init; }
    internal required string TextLabel { get; init; }
    internal required IReadOnlyList<string> TextSizes { get; init; }
    internal required string ColorsLabel { get; init; }
    internal required string ColorDark { get; init; }
    internal required string ColorLight { get; init; }
    internal required string ColorHighContrast { get; init; }
    internal required string LanguageLabel { get; init; }
    internal required string LanguageValue { get; init; }
    internal required string WelcomeTitle { get; init; }
    internal required string WelcomeBody { get; init; }
    internal required string CheckGraphics { get; init; }
    internal required string CheckSpace { get; init; }
    internal required string CheckNothingElse { get; init; }
    internal required string Honest { get; init; }
    internal required string KeysHint { get; init; }
    internal required string LicenseNotice { get; init; }
    internal required string ReadLicense { get; init; }
    internal required string LicenseTitle { get; init; }
    internal required string AgreementChangedTitle { get; init; }
    internal required string AgreementUnknownTitle { get; init; }
    internal required string AgreementHelp { get; init; }
    internal required string Accept { get; init; }
    internal required string Decline { get; init; }
    internal required string Back { get; init; }
    internal required string InstallMe { get; init; }
    internal required string NotNow { get; init; }
    internal required string WarningTitle { get; init; }
    internal required string WarningIntel { get; init; }

    internal required string FailUninstallTitle { get; init; }

    internal required string WarningMemory { get; init; }
    internal required string WarningNone { get; init; }
    internal required string NoGpuTitle { get; init; }
    internal required string WarningHelp { get; init; }
    internal required string InstallAnyway { get; init; }
    internal required string WorkingTitle { get; init; }
    internal required string PausedTitle { get; init; }
    internal required string StepWindows { get; init; }
    internal required string StepDownload { get; init; }
    internal required string StepUnpack { get; init; }
    internal required string StateDone { get; init; }
    internal required string StateNow { get; init; }
    internal required string StateNext { get; init; }
    internal required string StatusWindows { get; init; }
    internal required string StatusPermission { get; init; }
    internal required string StatusDownload { get; init; }
    internal required string StatusUnpack { get; init; }
    internal required string StatusPaused { get; init; }
    internal required string Percent { get; init; }
    internal required string ProgressName { get; init; }
    internal required string KeepUsing { get; init; }
    internal required string Pause { get; init; }
    internal required string Resume { get; init; }
    internal required string Cancel { get; init; }
    internal required string DoneTitle { get; init; }
    internal required string DoneBody { get; init; }
    internal required string DoneHelp { get; init; }
    internal required string OpenMe { get; init; }
    internal required string Close { get; init; }
    internal required string FailTitle { get; init; }
    internal required string FailDisk { get; init; }
    internal required string FailDiskHelp { get; init; }
    internal required string FailNetwork { get; init; }
    internal required string FailNetworkHelp { get; init; }
    internal required string FailOpen { get; init; }
    internal required string FailOpenHelp { get; init; }
    internal required string FailDamaged { get; init; }
    internal required string FailDamagedHelp { get; init; }
    internal required string FailWindows { get; init; }
    internal required string FailWindowsHelp { get; init; }
    internal required string FailUnsigned { get; init; }
    internal required string FailUnsignedHelp { get; init; }
    internal required string FailUnsignedUpdateHelp { get; init; }
    internal required string FailOlder { get; init; }
    internal required string FailOlderHelp { get; init; }
    internal required string FailOther { get; init; }
    internal required string FailOtherHelp { get; init; }
    internal required string NotRegisteredTitle { get; init; }
    internal required string NotRegisteredBody { get; init; }
    internal required string NotRegisteredHelp { get; init; }
    internal required string Retry { get; init; }
    internal required string UninstallTitle { get; init; }
    internal required string UninstallBody { get; init; }
    internal required string UninstallRings { get; init; }
    internal required string UninstallRingsKept { get; init; }
    internal required string UninstallSize { get; init; }
    internal required string UninstallKeep { get; init; }
    internal required string UninstallDelete { get; init; }
    internal required string UninstalledTitle { get; init; }

    internal static Texts For(string language) => language == "es" ? Spanish : English;

    /// <summary>What the uninstall screen says before the person chooses: what the data are, how much room they take
    /// when that is known (INS-9) and, when the uninstall will take alarms or reminders out of Windows
    /// (<see cref="WindowsIntegration.RingsToRemove"/>), that they go either way (INS-1); when they stay because the other
    /// BAXY shares the data (<see cref="WindowsIntegration.RingsKept"/>), how many and why (COX-1).</summary>
    internal string UninstallBodyFor(int rings, long dataBytes, string dataFolder, int kept = 0, string otherBaxy = "")
    {
        string body = dataBytes > 0
            ? UninstallBody + " " + string.Format(CultureInfo.CurrentCulture, UninstallSize, Size(dataBytes), dataFolder)
            : UninstallBody;
        if (rings > 0)
        {
            return body + " " + UninstallRings;
        }

        return kept > 0 ? body + " " + string.Format(CultureInfo.CurrentCulture, UninstallRingsKept, kept, otherBaxy) : body;
    }

    // In the units of the installer's other figures (1 GB = 1,000,000,000 bytes); what is there is never «0 MB».
    private static string Size(long bytes) => bytes >= 1_000_000_000
        ? string.Format(CultureInfo.CurrentCulture, "{0:0.0} GB", bytes / 1e9)
        : string.Format(CultureInfo.CurrentCulture, "{0:0} MB", Math.Max(1, Math.Round(bytes / 1e6)));

    internal static readonly Texts Spanish = new()
    {
        Language = "es",
        PreferencesName = "Cómo prefieres usar el instalador",
        FaceHappy = "BAXY sonríe con los ojos cerrados de alegría",
        FaceAsleep = "BAXY duerme mientras se instala",
        FaceWaking = "BAXY abre los ojos, todavía con sueño",
        FaceSad = "BAXY con cara de pena",
        VoiceLabel = "_Voz",
        On = "sí",
        Off = "no",
        TextLabel = "_Texto",
        TextSizes = ["normal", "grande", "muy grande"],
        ColorsLabel = "_Colores",
        ColorDark = "oscuro",
        ColorLight = "claro",
        ColorHighContrast = "alto contraste",
        LanguageLabel = "_Idioma",
        LanguageValue = "español",
        WelcomeTitle = "Hola, soy BAXY.",
        WelcomeBody = "Voy a vivir en tu PC para manejarlo contigo, por voz o por texto. Pienso aquí mismo, en tu equipo.",
        CheckGraphics = "Tu tarjeta gráfica me sirve.",
        CheckSpace = "Hay espacio: necesito unos {0:0} GB libres.",
        CheckNothingElse = "Instalo yo lo que falte. Si Windows te pide permiso, acéptalo.",
        Honest = "Mi voz es sintética. Sigo aprendiendo y a veces me equivoco.",
        KeysHint = "Enter instala. Escape sale. Al presionar Alt, cada botón muestra su letra.",
        LicenseNotice = "Al instalarme aceptas mi licencia.",
        ReadLicense = "Ver _licencia",
        LicenseTitle = "Mi licencia.",
        AgreementChangedTitle = "Mi licencia cambió desde la que aceptaste.",
        AgreementUnknownTitle = "Antes de actualizarme, lee mi licencia.",
        AgreementHelp = "Si no la aceptas, no me actualizo y sigues con la versión que tienes.",
        Accept = "La acepto",
        Decline = "No la acepto",
        Back = "Volver",
        InstallMe = "Instalarme",
        NotNow = "Ahora no",
        WarningTitle = "Puede que aquí no me vaya bien.",
        WarningIntel = "Tu PC sólo tiene gráficos Intel, y todavía no me han probado con ellos. Puedo ir muy lento o no funcionar.",
        WarningMemory = "Tu tarjeta gráfica tiene menos de 4 GB de memoria, y yo necesito 4. Es probable que no funcione bien.",
        WarningNone = "No encontré una tarjeta gráfica NVIDIA, AMD o Intel, y sin ella no puedo arrancar en este PC.",
        NoGpuTitle = "No puedo funcionar aquí.",
        WarningHelp = "Con una tarjeta NVIDIA o AMD de 4 GB sí sé que funciono.",
        InstallAnyway = "Instalarme i_gual",
        WorkingTitle = "Me estoy instalando.",
        PausedTitle = "En pausa.",
        StepWindows = "Lo que le falta a Windows",
        StepDownload = "Bajar mi modelo y mi voz",
        StepUnpack = "Dejar todo en su lugar",
        StateDone = "Hecho",
        StateNow = "Ahora",
        StateNext = "Falta",
        StatusWindows = "Revisando lo que le falta a Windows.",
        StatusPermission = "Windows te va a pedir permiso para instalar un componente de Microsoft que necesito.",
        StatusDownload = "Llevo {0:0.0} de {1:0.0} GB.",
        StatusUnpack = "Dejando todo en su lugar.",
        StatusPaused = "Sigo cuando me digas.",
        Percent = "{0} % completado",
        ProgressName = "Avance de la instalación",
        KeepUsing = "Puedes seguir usando tu PC. Si se corta internet, sigo donde quedé.",
        Pause = "_Pausar",
        Resume = "_Seguir",
        Cancel = "Cancelar",
        DoneTitle = "Listo, ya estoy en tu PC.",
        DoneBody = "Me encuentras en el menú Inicio.",
        DoneHelp = "La primera vez tardo unos minutos en despertar, porque reviso mis modelos.",
        OpenMe = "Abrirme",
        Close = "Cerrar",
        FailTitle = "No pude instalarme.",
        FailUninstallTitle = "No pude desinstalarme.",
        FailDisk = "Faltan {0:0.0} GB libres en el disco.",
        FailDiskHelp = "Libera espacio y vuelve a intentarlo. Lo que ya bajé no se pierde.",
        FailNetwork = "No logré conectarme a internet para bajar mis archivos.",
        FailNetworkHelp = "Revisa tu conexión y vuelve a intentarlo. Lo que ya bajé no se pierde.",
        FailOpen = "Ya estoy abierto en este PC.",
        FailOpenHelp = "Ciérrame y vuelve a intentarlo.",
        FailDamaged = "Un archivo llegó dañado y no lo voy a usar.",
        FailDamagedHelp = "Vuelve a intentarlo y lo bajo de nuevo.",
        FailWindows = "Windows no pudo instalar un componente que necesito.",
        FailWindowsHelp = "Vuelve a intentarlo. Si Windows te pide permiso, acéptalo.",
        FailUnsigned = "No pude comprobar que esta versión de BAXY venga firmada por quien hace BAXY, así que no instalé nada.",
        FailUnsignedHelp = "Baja el instalador otra vez desde la página de BAXY en GitHub. Si vuelve a pasar, no lo uses. El detalle quedó en {0}.",
        FailOlder = "En esta carpeta ya está BAXY {0}, más nuevo que el {1} que traigo, así que no instalé nada.",
        FailUnsignedUpdateHelp = "Tu BAXY de antes sigue instalada y sin cambios: ábrela desde el menú Inicio. Si vuelve a pasar, no instales esta versión. El detalle quedó en {0}.",
        FailOlderHelp = "Si de verdad quieres el {1}, desinstala primero el {0} eligiendo conservar tus datos.",
        FailOther = "{0}",
        FailOtherHelp = "Vuelve a intentarlo. El detalle quedó en {0}.",
        NotRegisteredTitle = "Ya estoy instalado, pero falta un paso.",
        NotRegisteredBody = "Windows no me dejó crear mi acceso en el menú Inicio o mi entrada en «Aplicaciones instaladas».",
        NotRegisteredHelp = "Reintenta sólo ese paso: no vuelvo a bajar nada. Mientras tanto puedes abrirme desde aquí. El detalle quedó en {0}.",
        Retry = "Reintentar",
        UninstallTitle = "¿Me desinstalo?",
        UninstallBody = "Tus datos son lo que recuerdo de ti, tus conversaciones, notas y ajustes, las claves que me diste, las capturas de pantalla que guardé y los modelos que bajé después de instalarme. Tú decides si se quedan.",
        UninstallRings = "Las alarmas y los recordatorios que me pediste se quitan de Windows en los dos casos: sin mí no suenan.",
        UninstallRingsKept = "Tus alarmas y recordatorios ({0}) se quedan en Windows y seguirán sonando: la otra BAXY, en {1}, usa estos mismos datos y también son suyos.",
        UninstallSize = "Hoy ocupan {0} en {1}.",
        UninstallKeep = "Desinstalarme y _conservar tus datos",
        UninstallDelete = "Desinstalarme y _borrar tus datos",
        UninstalledTitle = "Ya me desinstalé.",
    };

    internal static readonly Texts English = new()
    {
        Language = "en",
        PreferencesName = "How you prefer to use the installer",
        FaceHappy = "BAXY smiles with its eyes closed in joy",
        FaceAsleep = "BAXY sleeps while it installs",
        FaceWaking = "BAXY opens its eyes, still sleepy",
        FaceSad = "BAXY looks sad",
        VoiceLabel = "_Voice",
        On = "on",
        Off = "off",
        TextLabel = "_Text",
        TextSizes = ["normal", "large", "extra large"],
        ColorsLabel = "_Colors",
        ColorDark = "dark",
        ColorLight = "light",
        ColorHighContrast = "high contrast",
        LanguageLabel = "_Language",
        LanguageValue = "English",
        WelcomeTitle = "Hi, I’m BAXY.",
        WelcomeBody = "I’m going to live on your PC and run it with you, by voice or by text. I think right here, on your computer.",
        CheckGraphics = "Your graphics card works for me.",
        CheckSpace = "There’s room: I need about {0:0} GB free.",
        CheckNothingElse = "I’ll install whatever is missing. If Windows asks your permission, accept it.",
        Honest = "My voice is synthetic. I’m still learning and I sometimes get things wrong.",
        KeysHint = "Enter installs. Escape leaves. Press Alt and each button shows its letter.",
        LicenseNotice = "By installing me you accept my license.",
        ReadLicense = "Read the licen_se",
        LicenseTitle = "My license.",
        AgreementChangedTitle = "My license changed since the one you accepted.",
        AgreementUnknownTitle = "Before I update, read my license.",
        AgreementHelp = "If you don't accept it, I don't update and you keep the version you have.",
        Accept = "I accept it",
        Decline = "I don't accept it",
        Back = "Back",
        InstallMe = "Install me",
        NotNow = "Not now",
        WarningTitle = "I may not run well here.",
        WarningIntel = "Your PC only has Intel graphics, and I haven’t been tested on them yet. I may be very slow or not work.",
        WarningMemory = "Your graphics card has less than 4 GB of memory, and I need 4. I will probably not work well.",
        WarningNone = "I found no NVIDIA, AMD or Intel graphics card, and I can’t start on this PC without one.",
        NoGpuTitle = "I can’t work here.",
        WarningHelp = "I know I work with a 4 GB NVIDIA or AMD card.",
        InstallAnyway = "Install me an_yway",
        WorkingTitle = "I’m installing myself.",
        PausedTitle = "Paused.",
        StepWindows = "What Windows is missing",
        StepDownload = "Download my model and voice",
        StepUnpack = "Put everything in place",
        StateDone = "Done",
        StateNow = "Now",
        StateNext = "Next",
        StatusWindows = "Checking what Windows is missing.",
        StatusPermission = "Windows will ask your permission to install a Microsoft component I need.",
        StatusDownload = "{0:0.0} of {1:0.0} GB so far.",
        StatusUnpack = "Putting everything in place.",
        StatusPaused = "I’ll continue when you tell me.",
        Percent = "{0}% complete",
        ProgressName = "Installation progress",
        KeepUsing = "You can keep using your PC. If the internet drops, I’ll continue where I left off.",
        Pause = "_Pause",
        Resume = "Co_ntinue",
        Cancel = "Cancel",
        DoneTitle = "Done, I’m on your PC.",
        DoneBody = "You’ll find me in the Start menu.",
        DoneHelp = "The first time I take a few minutes to wake up, because I check my models.",
        OpenMe = "Open me",
        Close = "Close",
        FailTitle = "I couldn’t install myself.",
        FailUninstallTitle = "I couldn’t uninstall myself.",
        FailDisk = "The disk needs {0:0.0} GB more free space.",
        FailDiskHelp = "Free some space and try again. What I already downloaded is kept.",
        FailNetwork = "I couldn’t connect to the internet to download my files.",
        FailNetworkHelp = "Check your connection and try again. What I already downloaded is kept.",
        FailOpen = "I’m already open on this PC.",
        FailOpenHelp = "Close me and try again.",
        FailDamaged = "A file arrived damaged and I won’t use it.",
        FailDamagedHelp = "Try again and I’ll download it again.",
        FailWindows = "Windows couldn’t install a component I need.",
        FailWindowsHelp = "Try again. If Windows asks your permission, accept it.",
        FailUnsigned = "I couldn’t confirm that this version of BAXY is signed by BAXY’s maker, so I installed nothing.",
        FailUnsignedHelp = "Download the installer again from BAXY’s GitHub page. If it happens again, don’t use it. The details are in {0}.",
        FailOlder = "This folder already holds BAXY {0}, newer than the {1} I bring, so I installed nothing.",
        FailUnsignedUpdateHelp = "Your previous BAXY is still installed and unchanged: open it from the Start menu. If it happens again, don’t install this version. The details are in {0}.",
        FailOlderHelp = "If you really want {1}, uninstall {0} first, choosing to keep your data.",
        FailOther = "{0}",
        FailOtherHelp = "Try again. The details are in {0}.",
        NotRegisteredTitle = "I’m installed, but one step is missing.",
        NotRegisteredBody = "Windows didn’t let me create my Start menu shortcut or my entry in «Installed apps».",
        NotRegisteredHelp = "Try just that step again: I won’t download anything twice. Meanwhile you can open me from here. The details are in {0}.",
        Retry = "Try again",
        UninstallTitle = "Should I uninstall myself?",
        UninstallBody = "Your data is what I remember about you, your conversations, notes and settings, the keys you gave me, the screenshots I saved and the models I downloaded after I was installed. You decide whether it stays.",
        UninstallRings = "The alarms and reminders you asked me for are removed from Windows either way: they don’t ring without me.",
        UninstallRingsKept = "Your alarms and reminders ({0}) stay in Windows and will keep ringing: the other BAXY, in {1}, uses this same data and they’re its too.",
        UninstallSize = "Today it takes {0} in {1}.",
        UninstallKeep = "Uninstall me and _keep your data",
        UninstallDelete = "Uninstall me and _delete your data",
        UninstalledTitle = "I’ve been uninstalled.",
    };
}
