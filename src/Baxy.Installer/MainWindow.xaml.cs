using System.Diagnostics;
using System.Globalization;
using System.Net.Http;
using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Automation;
using System.Windows.Automation.Peers;
using System.Windows.Controls;
using System.Windows.Controls.Primitives;
using System.Windows.Interop;
using System.Windows.Media;
using System.Windows.Media.Animation;
using System.Windows.Media.Imaging;
using System.Windows.Shapes;
using System.Windows.Threading;
using Path = System.Windows.Shapes.Path;

namespace Baxy.Installer;

internal enum Face
{
    Happy,
    Asleep,
    Waking,
    Sad,
}

internal sealed record ButtonView(string Label, bool Action, Action Click, bool IsDefault = false, bool IsCancel = false);

/// <summary>One screen of the installer: BAXY's face and words, what the person can press, and what BAXY says aloud.</summary>
internal sealed record ScreenView(
    Face Face,
    string Title,
    string Body,
    string Help = "",
    string Hint = "",
    IReadOnlyList<string>? Checks = null,
    bool Progress = false,
    ButtonView? First = null,
    ButtonView? Second = null,
    ButtonView? Third = null,
    string? Line = null,
    bool Alert = false,
    bool LongText = false);

internal sealed partial class MainWindow : Window, IDisposable
{
    private const double Gigabyte = 1_000_000_000d;
    private const int WindowsShare = 8;
    private const int DownloadShare = 80;
    private const uint AllowSleep = 0x80000000;
    private const uint StayAwake = AllowSleep | 0x1;
    private const int DarkTitleBar = 20;
    private const int CaptionColor = 35;
    private const int CaptionTextColor = 36;
    private static readonly double[] TextSizes = [16, 20, 24];
    private static readonly double[] WindowHeights = [620, 760, 900];
    private readonly Voice voice;
    private readonly HttpClient http = new() { Timeout = Timeout.InfiniteTimeSpan };
    private readonly DispatcherTimer ticker = new() { Interval = TimeSpan.FromMilliseconds(250) };
    private readonly object gate = new();
    private readonly InstallPaths paths;
    private readonly ReleaseManifest? manifest;
    private readonly ReleaseManifest? carried;
    private readonly bool uninstalling;
    private readonly bool updating;
    private readonly GpuSupport support;
    private readonly Installation? installation;
    private Texts texts;
    private ThemeKind theme;
    private int textStep;
    private Func<ScreenView> screen;
    private ScreenView? shown;
    private Face? faceShown;
    private string rowsShown = string.Empty;
    private CancellationTokenSource? work;
    private PauseGate pause = new();
    private int stage;
    private bool asking;
    private long done;
    private long total;
    private int announced = -1;
    private FailureKind failure;
    private string failureDetail = string.Empty;
    private string olderInstalled = string.Empty;
    private long dataBytes;
    // PRV2 (A5): the agreement the installation in the folder accepted (null: none recorded), read before the swap
    // replaces the folder; when it is not this installer's, the window asks for this one first (AcceptedAgreement).
    private readonly string? acceptedBefore;
    private bool agreementPending;
    // UPD1 (REV10 m3): the BAXY that started --update (it closes itself for it) opens again on any way out that did not
    // replace it: a failure, «Cancel», the agreement not accepted or the window closed. Never twice. Whether it was open is
    // --update itself: measured in vivo, BAXY often closes within a second, before this window could see its mutex.
    // Null until BAXY is brought back or opened; the window does not go while it is still being brought back.
    private Task? bringingBack;
    // «I'm already open»: BAXY did not close for the update. The window then goes at once; BAXY is there.
    private bool baxyStayedOpen;
    // APP2 (VIVO14): BAXY was open and the person had it closed here (OpenScreen): like the one an update closes, it opens
    // again on a way out that did not replace it, and the new one opens once installed.
    private bool closedBaxy;
    private bool closingBaxy;
    private bool baxyStillOpen;
    // What the window finished with, for its exit code (ExitCode): null until it installed or uninstalled.
    private int? finished;
    // The App's exit event (src/Baxy.App/App.xaml.cs, BaxyExitHandler.AppExitEventName): what its «Salir» sets.
    private const string BaxyExitEvent = @"Local\BAXY.Product.App.Exit";

    internal MainWindow(ReleaseManifest? manifest, bool uninstalling, InstallPaths paths, bool voiceAllowed, bool updating = false)
    {
        InitializeComponent();
        this.paths = paths;
        voice = new Voice(voiceAllowed);
        IReadOnlyList<GpuAdapter> adapters = MachineGpu.Installed();
        carried = manifest;
        this.manifest = manifest?.ForMachine(adapters);
        this.uninstalling = uninstalling;
        this.updating = updating && !uninstalling && this.manifest is not null;
        http.DefaultRequestHeaders.UserAgent.ParseAdd("BAXY-Instalador/" + (manifest?.Version ?? "0"));
        support = MachineGpu.WithRam(adapters, MachineRam.InstalledMib());
        if (this.manifest is not null)
        {
            Program.LogMachine(this.manifest, adapters, paths);
            installation = new Installation(this.manifest, paths, new PartFetcher(http, gate: new Func<PauseGate>(() => pause)));
        }

        texts = Texts.For(CultureInfo.CurrentUICulture.TwoLetterISOLanguageName == "es" ? "es" : "en");
        theme = SystemParameters.HighContrast ? ThemeKind.HighContrast : ThemeKind.Dark;
        textStep = WindowsTextStep();
        acceptedBefore = AcceptedAgreement.Read(paths);
        bool asksAgreement = !uninstalling && this.manifest is not null && AcceptedAgreement.MustBeAccepted(paths, acceptedBefore);
        agreementPending = asksAgreement;
        screen = FirstScreen<Func<ScreenView>>(uninstalling, this.updating, !uninstalling && BaxyIsOpenHere(), asksAgreement,
            UninstallScreen, OpenScreen, AgreementScreen, Greeting);
        ticker.Tick += (_, _) => Tick();
        SourceInitialized += (_, _) => TitleBarFollowsTheme();
        Loaded += (_, _) =>
        {
            Apply();
            if (this.updating && !asksAgreement)
            {
                screen = WorkingScreen;
                Render(speak: false);
                _ = UpdateWhenBaxyClosesAsync();
                return;
            }

            Render(speak: true);
            if (uninstalling)
            {
                _ = MeasureDataAsync();
            }
        };
        Closing += (_, closing) =>
        {
            if (agreementPending && this.updating)
            {
                // Revisión a ciegas de PRV2: the window's X on the agreement is «I don't accept it», and BAXY comes back.
                agreementPending = false;
                Program.Log("agreement not accepted: nothing installed");
            }

            work?.Cancel();
            closing.Cancel = installation?.IsSwapping == true;
            if (!closing.Cancel && bringingBack is not { IsCompleted: true }
                && (bringingBack is not null
                    || (BringsBaxyBack(this.updating || closedBaxy, installation?.HasReplaced == true) && !(baxyStayedOpen && Voice.BaxyIsOpen()))))
            {
                // The window goes once the BAXY that closed for the update is open again: its process ending first would
                // end the wait with it.
                closing.Cancel = true;
                bringingBack ??= OpenAgainWhenClosedAsync();
                _ = CloseAfterAsync(bringingBack);
            }
        };
        Apply();
    }

    public void Dispose()
    {
        voice.Dispose();
        http.Dispose();
        work?.Dispose();
    }

    /// <summary>Windows' «make text bigger» setting, as this installer's text sizes.</summary>
    private static int WindowsTextStep()
    {
        using Microsoft.Win32.RegistryKey? key = Microsoft.Win32.Registry.CurrentUser.OpenSubKey(@"Software\Microsoft\Accessibility");
        return key?.GetValue("TextScaleFactor") is int factor ? (factor >= 150 ? 2 : factor >= 125 ? 1 : 0) : 0;
    }

    private void Apply()
    {
        Theme.Apply(Resources, theme);
        double size = TextSizes[textStep];
        FontSize = size;
        TitleText.FontSize = size * 2.25;
        BodyText.FontSize = size * 1.125;
        HelpText.FontSize = size * 0.9375;
        HintText.FontSize = size * 0.875;
        PercentText.FontSize = size * 0.9375;
        foreach (AccessText label in new[] { VoiceLabel, TextLabel, ColorsLabel, LanguageLabel })
        {
            label.FontSize = size * 0.875;
        }

        // Growing must not hide the buttons behind the taskbar: the window moves up to stay on the screen.
        Rect screenArea = ScreenArea.Of(this);
        Height = Math.Min(WindowHeights[textStep], screenArea.Height);
        if (!double.IsNaN(Top) && Top + Height > screenArea.Bottom)
        {
            Top = Math.Max(screenArea.Top, screenArea.Bottom - Height);
        }

        TitleBarFollowsTheme();
    }

    private void TitleBarFollowsTheme()
    {
        nint handle = new WindowInteropHelper(this).Handle;
        if (handle != 0)
        {
            int dark = theme == ThemeKind.Light ? 0 : 1;
            DwmSetWindowAttribute(handle, DarkTitleBar, ref dark, sizeof(int));
            if (!SystemParameters.HighContrast)
            {
                // Windows 11 draws the title bar in BAXY's panel color; Windows 10 ignores it.
                int panel = theme == ThemeKind.HighContrast ? 0x000000 : 0x180A06;
                int text = 0xF0E8E4;
                DwmSetWindowAttribute(handle, CaptionColor, ref panel, sizeof(int));
                DwmSetWindowAttribute(handle, CaptionTextColor, ref text, sizeof(int));
            }
        }
    }

    private void Render(bool speak)
    {
        ScreenView view = screen();
        // A button that goes away (Pause, when the download ends) must not take the keyboard's place with it.
        bool changed = shown is null || shown.Title != view.Title || (shown.First is null) != (view.First is null);
        shown = view;
        ShowFace(view.Face);
        Language = System.Windows.Markup.XmlLanguage.GetLanguage(texts.Language);
        TitleText.Text = view.Title;
        BodyText.Text = view.Body;
        Show(HelpText, view.Help);
        Show(HintText, view.Hint);
        ProgressArea.Visibility = view.Progress ? Visibility.Visible : Visibility.Collapsed;
        FillRows(view);
        Bar.SetValue(AutomationProperties.NameProperty, texts.ProgressName);
        AutomationProperties.SetLiveSetting(BodyText, view.Alert ? AutomationLiveSetting.Assertive : AutomationLiveSetting.Polite);
        Dress(FirstButton, view.First);
        Dress(SecondButton, view.Second);
        Dress(ThirdButton, view.Third);
        RenderPreferences();
        if (changed)
        {
            Focus(view);
            Announce();
        }

        if (speak && view.Line is not null)
        {
            voice.Say(texts.Language, view.Line);
        }
    }

    private void Focus(ScreenView view)
    {
        Button? target = view.First is { IsDefault: true } ? FirstButton
            : view.Second is { IsDefault: true } ? SecondButton
            : view.First is not null ? FirstButton
            : view.Second is not null ? SecondButton
            : null;
        Scroller.Focusable = view.LongText;
        Scroller.ScrollToTop();
        if (view.LongText)
        {
            Scroller.Focus();
            return;
        }

        target?.Focus();
    }

    private void Announce()
    {
        foreach (TextBlock block in new[] { TitleText, BodyText })
        {
            AutomationProperties.SetLiveSetting(block, block == TitleText ? AutomationLiveSetting.Polite : AutomationProperties.GetLiveSetting(block));
            UIElementAutomationPeer.CreatePeerForElement(block)?.RaiseAutomationEvent(AutomationEvents.LiveRegionChanged);
        }
    }

    private static void Show(TextBlock block, string text)
    {
        block.Text = text;
        block.Visibility = text.Length == 0 ? Visibility.Collapsed : Visibility.Visible;
    }

    private void Dress(Button button, ButtonView? view)
    {
        button.Visibility = view is null ? Visibility.Collapsed : Visibility.Visible;
        if (view is null)
        {
            button.IsDefault = false;
            button.IsCancel = false;
            return;
        }

        button.Style = (Style)Resources[view.Action ? "ActionButton" : "QuietButton"];
        string said = view.Label.Replace("_", string.Empty, StringComparison.Ordinal);
        AccessText label = new() { Text = view.Label };
        AutomationProperties.SetName(label, said);
        button.Content = label;
        AutomationProperties.SetName(button, said);
        button.IsDefault = view.IsDefault;
        button.IsCancel = view.IsCancel;
    }

    private void FillRows(ScreenView view)
    {
        // Rebuilt only when they change: the ticker renders four times a second and a screen reader follows these rows.
        string key = $"{texts.Language}|{view.Progress}|{stage}|{string.Join('|', view.Checks ?? [])}";
        if (key == rowsShown)
        {
            return;
        }

        rowsShown = key;
        Rows.Children.Clear();
        Rows.Visibility = Visibility.Collapsed;
        if (view.Checks is not null)
        {
            Rows.Visibility = Visibility.Visible;
            foreach (string check in view.Checks)
            {
                Rows.Children.Add(CheckRow(check));
            }
        }

        if (view.Progress)
        {
            Rows.Visibility = Visibility.Visible;
            string[] steps = [texts.StepWindows, texts.StepDownload, texts.StepUnpack];
            for (int index = 0; index < steps.Length; index++)
            {
                Rows.Children.Add(StepRow(steps[index], index));
            }
        }
    }

    private static DockPanel CheckRow(string text)
    {
        Path tick = new()
        {
            Data = Geometry.Parse("M5,12.5 L9.5,17 L19,7.5"),
            Width = 22,
            Height = 22,
            Stretch = Stretch.None,
            StrokeThickness = 2.5,
            StrokeStartLineCap = PenLineCap.Round,
            StrokeEndLineCap = PenLineCap.Round,
            StrokeLineJoin = PenLineJoin.Round,
            Margin = new Thickness(0, 1, 10, 0),
            VerticalAlignment = VerticalAlignment.Top,
        };
        tick.SetResourceReference(Shape.StrokeProperty, "Ok");
        DockPanel row = new() { Margin = new Thickness(0, 0, 0, 10) };
        DockPanel.SetDock(tick, Dock.Left);
        row.Children.Add(tick);
        row.Children.Add(new TextBlock { Text = text, TextWrapping = TextWrapping.Wrap });
        return row;
    }

    private Border StepRow(string label, int index)
    {
        string state = index < stage ? texts.StateDone : index == stage ? texts.StateNow : texts.StateNext;
        TextBlock name = new() { Text = label, TextWrapping = TextWrapping.Wrap };
        if (index == stage)
        {
            name.SetResourceReference(TextBlock.FontFamilyProperty, "Strong");
        }

        TextBlock said = new() { Text = state, Margin = new Thickness(12, 0, 0, 0) };
        said.SetResourceReference(TextBlock.ForegroundProperty, index < stage ? "Ok" : index == stage ? "Now" : "Second");
        DockPanel.SetDock(said, Dock.Right);
        DockPanel row = new();
        row.Children.Add(said);
        row.Children.Add(name);
        Border line = new()
        {
            Child = row,
            Padding = new Thickness(0, 0, 0, 8),
            Margin = new Thickness(0, 0, 0, 8),
            BorderThickness = new Thickness(0, 0, 0, 1),
        };
        line.SetResourceReference(Border.BorderBrushProperty, "Line");
        AutomationProperties.SetName(line, $"{label}: {state}");
        return line;
    }

    private void ShowFace(Face face)
    {
        (string file, string description) = face switch
        {
            Face.Asleep => ("baxy_dormido.jpg", texts.FaceAsleep),
            Face.Waking => ("baxy_despierto.jpg", texts.FaceWaking),
            Face.Sad => ("baxy_error.jpg", texts.FaceSad),
            _ => ("baxy_contento.jpg", texts.FaceHappy),
        };
        AutomationProperties.SetName(FaceImage, description);
        if (faceShown == face)
        {
            return;
        }

        faceShown = face;
        FaceImage.Source = new BitmapImage(new Uri($"pack://application:,,,/Assets/faces/{file}"));
        if (SystemParameters.ClientAreaAnimation)
        {
            FaceImage.BeginAnimation(OpacityProperty, new DoubleAnimation(0, 1, TimeSpan.FromMilliseconds(400)));
        }
    }

    private void RenderPreferences()
    {
        Preference(VoiceButton, VoiceLabel, texts.VoiceLabel, voice.IsOn ? texts.On : texts.Off);
        VoiceButton.IsChecked = voice.IsOn;
        Preference(TextButton, TextLabel, texts.TextLabel, texts.TextSizes[textStep]);
        string colors = theme switch
        {
            ThemeKind.Light => texts.ColorLight,
            ThemeKind.HighContrast => texts.ColorHighContrast,
            _ => texts.ColorDark,
        };
        Preference(ColorsButton, ColorsLabel, texts.ColorsLabel, colors);
        Preference(LanguageButton, LanguageLabel, texts.LanguageLabel, texts.LanguageValue);
        AutomationProperties.SetName(PreferencesPanel, texts.PreferencesName);
    }

    private static void Preference(ButtonBase button, AccessText label, string name, string value)
    {
        string said = $"{name.Replace("_", string.Empty, StringComparison.Ordinal)}: {value}";
        label.Text = $"{name}: {value}";
        AutomationProperties.SetName(label, said);
        AutomationProperties.SetName(button, said);
    }

    private ScreenView Greeting()
    {
        long need = installation!.RequiredBytes;
        if (MissingBytes() > 0)
        {
            failure = FailureKind.Disk;
            return FailedScreen();
        }

        if (support != GpuSupport.Measured)
        {
            return WarningScreen();
        }

        string space = string.Format(CultureInfo.CurrentCulture, texts.CheckSpace, Math.Ceiling(need / Gigabyte));
        return new ScreenView(
            Face.Happy,
            texts.WelcomeTitle,
            texts.WelcomeBody,
            Help: texts.Honest,
            Hint: $"{texts.LicenseNotice} {texts.KeysHint}",
            Checks: [texts.CheckGraphics, space, texts.CheckNothingElse],
            First: new ButtonView(texts.InstallMe, true, Start, IsDefault: true),
            Second: new ButtonView(texts.NotNow, false, Close, IsCancel: true),
            Third: new ButtonView(texts.ReadLicense, false, ShowLicense),
            Line: "welcome");
    }

    private long MissingBytes() => Math.Max(
        0,
        installation!.StillNeededBytes - new DriveInfo(System.IO.Path.GetPathRoot(paths.Root)!).AvailableFreeSpace);

    /// <summary>
    /// UPD1 (REV10 M2): what stops the work before BAXY is waited for and before anything is downloaded or deleted: too
    /// little free space, or a folder beside the installation with BAXY's name that is not BAXY's (M4). --update went
    /// straight to the work, past <see cref="Greeting"/>, the only place that looked at the space.
    /// </summary>
    internal static FailureKind? RefusalBeforeAnything(long missingBytes, InstallPaths paths, out string folder)
    {
        folder = string.Empty;
        if (missingBytes > 0)
        {
            return FailureKind.Disk;
        }

        try
        {
            paths.RefuseWhatIsNotBaxys();
            return null;
        }
        catch (NotBaxysException foreign)
        {
            folder = foreign.Folder;
            return FailureKind.NotBaxys;
        }
    }

    /// <summary>Shows why the work cannot start, or says it can.</summary>
    private bool Refused()
    {
        FailureKind? refusal;
        string folder;
        try
        {
            refusal = RefusalBeforeAnything(MissingBytes(), paths, out folder);
        }
        catch (Exception unread) when (unread is IOException or UnauthorizedAccessException or ArgumentException)
        {
            // A drive that is not ready, a folder Windows does not let it read.
            Program.Log(unread.ToString());
            refusal = FailureKind.Other;
            folder = unread.Message;
        }

        if (refusal is not { } refused)
        {
            return false;
        }

        Program.Log($"refused before anything: {refused} {folder}");
        failure = refused;
        failureDetail = folder;
        screen = FailedScreen;
        Render(speak: true);
        BringBaxyBack();
        return true;
    }

    private ScreenView WarningScreen()
    {
        (string body, string line) = support switch
        {
            GpuSupport.NotMeasured => (texts.WarningIntel, "warningIntel"),
            GpuSupport.TooLittleMemory => (texts.WarningMemory, "warningMemory"),
            GpuSupport.TooLittleRam => (RamText(texts.WarningRam, integrated: false), "warningRam"),
            GpuSupport.TooLittleRamIntegrated => (RamText(texts.WarningRamIntegrated, integrated: true), "warningRamIntegrated"),
            _ => (texts.WarningNone, "warningNone"),
        };
        return new ScreenView(
            Face.Sad,
            support == GpuSupport.None ? texts.NoGpuTitle : texts.WarningTitle,
            body,
            Help: support is GpuSupport.TooLittleRam or GpuSupport.TooLittleRamIntegrated ? texts.WarningRamHelp : texts.WarningHelp,
            Hint: support == GpuSupport.None ? string.Empty : texts.LicenseNotice,
            First: new ButtonView(support == GpuSupport.None ? texts.Close : texts.NotNow, false, Close, IsDefault: true, IsCancel: true),
            Second: support == GpuSupport.None ? null : new ButtonView(texts.InstallAnyway, true, Start),
            Third: support == GpuSupport.None ? null : new ButtonView(texts.ReadLicense, false, ShowLicense),
            Line: line);
    }

    // VRAM5 (AUD1 F7): the RAM installed and the least BAXY needs, in GB as the person reads them.
    private static string RamText(string text, bool integrated) => string.Format(
        CultureInfo.CurrentCulture, text, (MachineRam.InstalledMib() ?? 0) / 1024d, MachineGpu.MinimumRamMib(integrated) / 1024d);

    private ScreenView LicenseScreen() => new(
        Face.Happy,
        texts.LicenseTitle,
        WindowsIntegration.LicenseText(texts.Language),
        First: new ButtonView(texts.Back, false, BackFromLicense, IsDefault: true, IsCancel: true),
        Line: "license",
        LongText: true);

    /// <summary>
    /// PRV2 (A5): BAXY is in the folder and the agreement it accepted is not this one, or is not known. Shown before
    /// anything is installed, by hand or as an update from BAXY; accepting goes on, not accepting installs nothing.
    /// </summary>
    private ScreenView AgreementScreen() => new(
        Face.Happy,
        acceptedBefore is null ? texts.AgreementUnknownTitle : texts.AgreementChangedTitle,
        WindowsIntegration.LicenseText(texts.Language),
        Help: texts.AgreementHelp,
        First: new ButtonView(texts.Accept, true, AcceptAgreement, IsDefault: true),
        Second: new ButtonView(texts.Decline, false, DeclineAgreement, IsCancel: true),
        Line: "agreement",
        LongText: true);

    private void AcceptAgreement()
    {
        if (!agreementPending)
        {
            return;
        }

        agreementPending = false;
        Program.Log("agreement accepted");
        if (updating)
        {
            screen = WorkingScreen;
            Render(speak: false);
            _ = UpdateWhenBaxyClosesAsync();
            return;
        }

        screen = Greeting;
        Render(speak: true);
    }

    private void DeclineAgreement()
    {
        if (!agreementPending)
        {
            return;
        }

        agreementPending = false;
        Program.Log("agreement not accepted: nothing installed");
        // With --update, BAXY closed itself for it: the version the person has comes back as it was, as the window goes.
        Close();
    }

    internal static bool BringsBaxyBack(bool updating, bool replaced) => updating && !replaced;

    /// <summary>
    /// REM1 (REV12 A-2): the BAXY in the way is the one running from this installation (<see cref="RunningBaxy"/>); one
    /// open from another folder holds the same mutex but its files are not these, and it is neither closed nor reopened.
    /// </summary>
    private bool BaxyIsOpenHere() => RunningBaxy.From(paths.App).Count > 0;

    /// <summary>REM1 (REV12 A-2): «Close me and go on» asks BAXY to exit only when the BAXY that would hear it is this
    /// folder's: some runs from here and none from elsewhere.</summary>
    internal static bool MayAskToExit(int runningHere, bool runningElsewhere) => runningHere > 0 && !runningElsewhere;

    /// <summary>
    /// APP2 (VIVO14, reparo 1): the first screen. Opened by hand with BAXY open, the window showed the agreement and the
    /// greeting and only after «Instalarme» said BAXY was open: that comes first now, with the offer to close it. With
    /// --update the BAXY that started it closes itself (<see cref="UpdateWhenBaxyClosesAsync"/>).
    /// </summary>
    internal static T FirstScreen<T>(bool uninstalling, bool updating, bool baxyOpen, bool asksAgreement, T uninstall, T open, T agreement, T greeting) =>
        uninstalling ? uninstall : baxyOpen && !updating ? open : asksAgreement ? agreement : greeting;

    /// <summary>APP2 (VIVO14): the window's exit code, as --quiet's (CommandLine's help): 0 when it installed or uninstalled,
    /// <see cref="QuietInstall.NotRegistered"/> installed without its shortcut or entry, and <see cref="Program.Failure"/>
    /// when it closed before finishing (BAXY open, a failure, cancelled). It always exited with 0.</summary>
    internal static int ExitCode(int? finished) => finished ?? Program.Failure;

    /// <summary>Asks the open BAXY to exit as its own «Salir» does (the App's exit event, BaxyExitHandler); false when no
    /// BAXY listens for it.</summary>
    internal static bool AskBaxyToExit(string eventName)
    {
        try
        {
            if (!EventWaitHandle.TryOpenExisting(eventName, out EventWaitHandle? exit))
            {
                return false;
            }

            using (exit)
            {
                return exit.Set();
            }
        }
        catch (Exception refused) when (refused is UnauthorizedAccessException or IOException)
        {
            Program.Log(refused.ToString());
            return false;
        }
    }

    /// <summary>The window's exit code (<see cref="ExitCode"/>).</summary>
    internal int Result => ExitCode(finished);

    // APP2: BAXY was open when the window opened or the work was to start; it is told before anything, with «close me».
    private ScreenView OpenScreen() => new(
        Face.Sad,
        texts.FailOpen,
        closingBaxy ? texts.OpenClosing : baxyStillOpen ? texts.OpenStillOpen : texts.OpenBody,
        Help: closingBaxy ? string.Empty : texts.OpenHelp,
        First: closingBaxy ? null : new ButtonView(texts.CloseMeAndGoOn, true, () => _ = CloseBaxyAndGoOnAsync(), IsDefault: true),
        Second: closingBaxy ? null : new ButtonView(texts.Close, false, Close, IsCancel: true),
        // No recorded line: the voice is off while BAXY is open (its lines say «BAXY»); a screen reader reads it.
        Line: null,
        Alert: true);

    private async Task CloseBaxyAndGoOnAsync()
    {
        Program.Log("BAXY is open: the person asked to close it");
        closingBaxy = true;
        baxyStillOpen = false;
        Render(speak: false);
        // REM1 (REV12 A-2): the exit event is every BAXY's: it is set only when the BAXY that hears it is this folder's, and
        // the wait is for those processes. A BAXY open from another folder stays open.
        IReadOnlyList<int> here = RunningBaxy.From(paths.App);
        bool elsewhere = RunningBaxy.AnyElsewhere(paths.App);
        bool asked = MayAskToExit(here.Count, elsewhere) && AskBaxyToExit(BaxyExitEvent);
        // Revisión ciega de APP2: from the moment it is asked, BAXY closes for this window, also if the window goes while
        // it waits; one the person closed by hand is not opened by it. A bringing back already over (an earlier round) is
        // not the one of this closing.
        closedBaxy |= asked;
        if (asked && bringingBack is { IsCompleted: true })
        {
            bringingBack = null;
        }

        // A minute at most, as an update waits for it (UpdateWhenBaxyClosesAsync).
        for (int waited = 0; asked && RunningBaxy.AnyAlive(here) && waited < 120; waited++)
        {
            await Task.Delay(TimeSpan.FromMilliseconds(500));
        }

        closingBaxy = false;
        if (!IsLoaded)
        {
            return;
        }

        if (BaxyIsOpenHere())
        {
            Program.Log(asked ? "BAXY did not close"
                : elsewhere ? "BAXY is open here and another BAXY too: its exit event could reach the other, so it was not set"
                : "BAXY is open and does not listen for its exit");
            baxyStillOpen = true;
            // BAXY is there: the window goes at once, without waiting to bring it back.
            baxyStayedOpen = true;
            shown = null;
            Render(speak: true);
            return;
        }

        Program.Log("BAXY closed for the installation");
        screen = agreementPending ? AgreementScreen : Greeting;
        shown = null;
        Render(speak: true);
    }

    /// <summary>UPD1 (REV10 m3): on a way out that leaves the window open (a failure, «Cancel»), BAXY comes back now.</summary>
    private void BringBaxyBack()
    {
        if (bringingBack is null && BringsBaxyBack(updating || closedBaxy, installation?.HasReplaced == true))
        {
            bringingBack = OpenAgainWhenClosedAsync();
        }
    }

    private async Task CloseAfterAsync(Task first)
    {
        // Out of Closing first: WPF refuses Close() inside it, and the bringing back may already be over.
        await Task.Yield();
        await first;
        Close();
    }

    /// <summary>The BAXY that closed for the update may still be closing: it is waited for a minute at most, as the update does.</summary>
    private async Task OpenAgainWhenClosedAsync()
    {
        for (int waited = 0; Voice.BaxyIsOpen() && waited < 120; waited++)
        {
            await Task.Delay(TimeSpan.FromMilliseconds(500));
        }

        if (Voice.BaxyIsOpen() || !paths.HoldsBaxy)
        {
            return;
        }

        Program.Log("the BAXY that closed for the update opens again, as it was");
        StartBaxy();
    }

    private void ShowLicense()
    {
        screen = LicenseScreen;
        Render(speak: true);
    }

    private void BackFromLicense()
    {
        screen = Greeting;
        Render(speak: false);
    }

    private ScreenView WorkingScreen()
    {
        bool paused = pause.IsPaused && stage == 1;
        long reached;
        long whole;
        bool needsPermission;
        lock (gate)
        {
            reached = done;
            whole = total;
            needsPermission = asking;
        }

        double fraction = whole > 0 ? (double)reached / whole : 0;
        int percent = stage switch
        {
            0 => 0,
            1 => WindowsShare + (int)(DownloadShare * fraction),
            _ => WindowsShare + DownloadShare + (int)((100 - WindowsShare - DownloadShare) * fraction),
        };
        Bar.Value = percent;
        PercentText.Text = string.Format(CultureInfo.CurrentCulture, texts.Percent, percent);
        string status = paused ? texts.StatusPaused
            : stage == 0 ? (needsPermission ? texts.StatusPermission : texts.StatusWindows)
            : stage == 1 ? string.Format(CultureInfo.CurrentCulture, texts.StatusDownload, reached / Gigabyte, whole / Gigabyte)
            : texts.StatusUnpack;
        return new ScreenView(
            stage == 2 ? Face.Waking : Face.Asleep,
            paused ? texts.PausedTitle : texts.WorkingTitle,
            status,
            Help: texts.KeepUsing,
            Progress: true,
            First: stage == 1 ? new ButtonView(paused ? texts.Resume : texts.Pause, false, TogglePause) : null,
            Second: new ButtonView(texts.Cancel, false, CancelWork, IsCancel: true),
            Line: null);
    }

    private ScreenView DoneScreen() => new(
        Face.Happy,
        texts.DoneTitle,
        texts.DoneBody,
        Help: texts.DoneHelp,
        First: new ButtonView(texts.OpenMe, true, OpenBaxy, IsDefault: true),
        Second: new ButtonView(texts.Close, false, Close, IsCancel: true),
        Line: "done");

    private ScreenView FailedScreen()
    {
        (string body, string help) = failure switch
        {
            FailureKind.Disk => (
                string.Format(CultureInfo.CurrentCulture, texts.FailDisk, MissingBytes() / Gigabyte),
                texts.FailDiskHelp),
            FailureKind.Network => (texts.FailNetwork, texts.FailNetworkHelp),
            FailureKind.Open => (texts.FailOpen, texts.FailOpenHelp),
            FailureKind.Damaged => (texts.FailDamaged, texts.FailDamagedHelp),
            FailureKind.Windows => (texts.FailWindows, texts.FailWindowsHelp),
            // Started by BAXY (--update): the person downloaded nothing, and the BAXY that closed for it is untouched.
            FailureKind.Unsigned => (texts.FailUnsigned, string.Format(
                CultureInfo.CurrentCulture, updating ? texts.FailUnsignedUpdateHelp : texts.FailUnsignedHelp, Program.LogPath)),
            FailureKind.Older => (
                string.Format(CultureInfo.CurrentCulture, texts.FailOlder, olderInstalled, carried?.Version),
                string.Format(CultureInfo.CurrentCulture, texts.FailOlderHelp, olderInstalled, carried?.Version)),
            FailureKind.NotBaxys => (string.Format(CultureInfo.CurrentCulture, texts.FailNotBaxys, failureDetail), texts.FailNotBaxysHelp),
            _ => (
                string.Format(CultureInfo.CurrentCulture, texts.FailOther, failureDetail),
                string.Format(CultureInfo.CurrentCulture, texts.FailOtherHelp, Program.LogPath)),
        };
        return new ScreenView(
            Face.Sad,
            uninstalling ? texts.FailUninstallTitle : texts.FailTitle,
            body,
            Help: help,
            First: new ButtonView(texts.Retry, true, Retry, IsDefault: true),
            Second: new ButtonView(texts.Close, false, Close, IsCancel: true),
            // The recorded lines say «I couldn't install myself».
            Line: uninstalling ? null : Failures.VoiceLine(failure),
            Alert: true);
    }

    // No recorded line says this one: it is read, and a screen reader says it (Alert).
    private ScreenView NotRegisteredScreen() => new(
        Face.Sad,
        texts.NotRegisteredTitle,
        texts.NotRegisteredBody,
        Help: string.Format(CultureInfo.CurrentCulture, texts.NotRegisteredHelp, Program.LogPath),
        First: new ButtonView(texts.Retry, true, Register, IsDefault: true),
        Second: new ButtonView(texts.OpenMe, false, OpenBaxy),
        Third: new ButtonView(texts.Close, false, Close, IsCancel: true),
        Alert: true);

    // LEG2 (T6): the spoken line names the alarms only when the screen does, that is, when they will be removed.
    // COX1: with another BAXY installed none are removed (RingsToRemove = 0) and the screen says how many stay.
    // UNI1 (REV8 U1): the same check (DataSharedWith) hides «delete your data» and the screen says why.
    private ScreenView UninstallScreen()
    {
        int rings = WindowsIntegration.RingsToRemove(paths);
        string? sharedWith = WindowsIntegration.DataSharedWith(paths);
        return new(
            Face.Sad,
            texts.UninstallTitle,
            texts.UninstallBodyFor(
                rings,
                dataBytes,
                WindowsPlaces.ForThisUser.Data,
                WindowsIntegration.RingsKept(paths),
                sharedWith),
            First: new ButtonView(texts.UninstallKeep, false, () => Uninstall(deleteData: false), IsDefault: true),
            Second: sharedWith is null ? new ButtonView(texts.UninstallDelete, false, () => Uninstall(deleteData: true)) : null,
            Third: new ButtonView(texts.Cancel, false, Close, IsCancel: true),
            Line: UninstallLine(rings));
    }

    internal static string UninstallLine(int rings) => rings > 0 ? "uninstallRings" : "uninstall";

    private ScreenView UninstalledScreen() => new(
        Face.Asleep,
        texts.UninstalledTitle,
        string.Empty,
        First: new ButtonView(texts.Close, false, Close, IsDefault: true, IsCancel: true),
        Line: "uninstalled");

    /// <summary>
    /// INS-9: how much «keep your data» leaves. The folder can hold very many files (measured in one in use: 134,738
    /// files, 56 s the first time), so they are counted off the window's thread and the screen gets the figure when
    /// there is one; until then, and if Windows does not let the folder be read, it gives none.
    /// </summary>
    private async Task MeasureDataAsync()
    {
        try
        {
            dataBytes = await Task.Run(() => WindowsIntegration.DataBytes());
        }
        catch (Exception unread) when (unread is IOException or UnauthorizedAccessException)
        {
            Program.Log(unread.ToString());
            return;
        }

        if (IsLoaded && shown?.Title == texts.UninstallTitle)
        {
            Render(speak: false);
            // The text changed under a screen reader that already read it: it is told, as the progress is.
            UIElementAutomationPeer.CreatePeerForElement(BodyText)?.RaiseAutomationEvent(AutomationEvents.LiveRegionChanged);
        }
    }

    /// <summary>
    /// UNI1 (REV8 S1): where «Retry» goes. A failure while the agreement was still to be answered sent it to the greeting,
    /// from which the window installs and records the agreement as accepted (<see cref="Register"/>): it goes back to
    /// the agreement instead.
    /// </summary>
    internal static T RetryTo<T>(bool uninstalling, bool agreementPending, T uninstall, T agreement, T greeting) =>
        uninstalling ? uninstall : agreementPending ? agreement : greeting;

    private void Retry()
    {
        screen = RetryTo<Func<ScreenView>>(uninstalling, agreementPending, UninstallScreen, AgreementScreen, Greeting);
        shown = null;
        Render(speak: true);
    }

    /// <summary>What nothing caught, as a failure the person can read, not a window that stops answering.</summary>
    internal void ShowFailure(Exception problem)
    {
        work?.Cancel();
        failure = FailureKind.Other;
        failureDetail = problem.Message;
        Finish(FailedScreen);
    }

    /// <summary>
    /// --update (BaxyUpdateHandler): the person said yes in BAXY, which closes itself after starting this. The swap would
    /// refuse while it runs, so this waits for it a minute at most; a BAXY still open then is told as any open one is.
    /// </summary>
    private async Task UpdateWhenBaxyClosesAsync()
    {
        if (Refused())
        {
            return;
        }

        // UPD1 (REV10 m3): «Cancel» while BAXY closes is heard too (the work, and its token, start after).
        work?.Dispose();
        work = new CancellationTokenSource();
        CancellationToken waiting = work.Token;
        for (int waited = 0; Voice.BaxyIsOpen() && waited < 120 && !waiting.IsCancellationRequested; waited++)
        {
            await Task.Delay(TimeSpan.FromMilliseconds(500));
        }

        if (waiting.IsCancellationRequested)
        {
            Finish(Greeting);
            BringBaxyBack();
            return;
        }

        Start();
    }

    private void Start()
    {
        // APP2 (VIVO14): a BAXY open now (opened after the window was) is told before anything, with «close me».
        if (!updating && BaxyIsOpenHere())
        {
            screen = OpenScreen;
            shown = null;
            Render(speak: true);
            return;
        }

        // UNI1 (REV8 S1): nothing is installed while the agreement is still to be answered, whatever screen led here.
        if (agreementPending)
        {
            screen = AgreementScreen;
            Render(speak: true);
            return;
        }

        if (Refused())
        {
            return;
        }

        if (BaxyIsOpenHere())
        {
            // Better now than after downloading gigabytes: the swap would refuse at the very end.
            failure = FailureKind.Open;
            baxyStayedOpen = true;
            screen = FailedScreen;
            Render(speak: true);
            return;
        }

        pause = new PauseGate();
        stage = 0;
        announced = -1;
        lock (gate)
        {
            done = 0;
            total = 0;
            asking = false;
        }

        screen = WorkingScreen;
        Render(speak: false);
        voice.Say(texts.Language, "working");
        ticker.Start();
        _ = SetThreadExecutionState(StayAwake);
        work?.Dispose();
        work = new CancellationTokenSource();
        _ = RunAsync(work.Token);
    }

    private async Task RunAsync(CancellationToken cancellation)
    {
        try
        {
            lock (gate)
            {
                asking = !Prerequisites.HasVisualCpp();
            }

            // UPD1 (REV10 M4): before the components of Windows are downloaded into the .download folder.
            paths.RefuseWhatIsNotBaxys();
            // FIR1: nothing of Windows nor of BAXY is installed before release.json's signature checks out.
            ReleaseManifest own = carried ?? throw new InvalidDataException("this installer carries no release manifest");
            await Task.Run(() => SignedRelease.ConfirmAsync(http, own, paths, SignedRelease.BuiltInKeys, cancellation), cancellation);
            await Task.Run(() => Prerequisites.InstallMissingAsync(http, paths.Downloads, cancellation), cancellation);
            await Task.Run(
                () => installation!.RunAsync(
                    (phase, reached, whole) =>
                    {
                        lock (gate)
                        {
                            stage = phase == InstallPhase.Downloading ? 1 : 2;
                            done = reached;
                            total = whole;
                        }
                    },
                    cancellation),
                cancellation);
            Register();
        }
        catch (OperationCanceledException) when (cancellation.IsCancellationRequested)
        {
            Finish(Greeting);
            BringBaxyBack();
        }
#pragma warning disable CA1031 // Whatever stopped the installation is told to the person, with its cause.
        catch (Exception problem)
#pragma warning restore CA1031
        {
            Program.Log(problem.ToString());
            failure = Failures.Classify(problem, Voice.BaxyIsOpen);
            baxyStayedOpen = failure == FailureKind.Open;
            failureDetail = (problem as NotBaxysException)?.Folder ?? problem.Message;
            olderInstalled = (problem as OlderReleaseException)?.Installed ?? string.Empty;
            Finish(FailedScreen);
            BringBaxyBack();
        }
    }

    /// <summary>
    /// The last step, with BAXY's files already in place. Windows refusing it is not «I couldn't install myself» (INS-5):
    /// BAXY is there and opens, and the person tries this step again alone, with nothing downloaded twice.
    /// </summary>
    private void Register()
    {
        // PRV2 (A5): the window installs only after the agreement was accepted (its greeting, or AgreementScreen).
        AcceptedAgreement.Write(paths, AcceptedAgreement.Current, Program.Log);
        try
        {
            WindowsIntegration.Register(paths, manifest!.Version, manifest.InstalledBytes);
        }
        catch (NotRegisteredException refused)
        {
            Program.Log(refused.ToString());
            finished = QuietInstall.NotRegistered;
            // The same screen again is said again: the person pressed «try again» and it was refused once more.
            shown = null;
            Finish(NotRegisteredScreen);
            return;
        }

        Program.Log("installed");
        finished = 0;
        Finish(DoneScreen);
        if (updating || closedBaxy)
        {
            // The person asked for the update in BAXY, or had it closed here: it comes back as it was before it closed.
            OpenBaxy();
        }
    }

    private void Finish(Func<ScreenView> next)
    {
        ticker.Stop();
        _ = SetThreadExecutionState(AllowSleep);
        if (IsLoaded)
        {
            screen = next;
            Render(speak: true);
        }
    }

    private void Tick()
    {
        int percent = (int)Bar.Value;
        Render(speak: false);
        int milestone = (int)Bar.Value / 10;
        if (milestone != announced)
        {
            announced = milestone;
            UIElementAutomationPeer.CreatePeerForElement(BodyText)?.RaiseAutomationEvent(AutomationEvents.LiveRegionChanged);
        }

        if (percent < 50 && Bar.Value >= 50)
        {
            voice.Say(texts.Language, "half");
        }
        else if (percent < 90 && Bar.Value >= 90)
        {
            voice.Say(texts.Language, "almost");
        }
    }

    private void TogglePause()
    {
        if (pause.IsPaused)
        {
            pause.Resume();
        }
        else
        {
            pause.Pause();
        }

        Render(speak: false);
    }

    private void CancelWork()
    {
        pause.Resume();
        work?.Cancel();
    }

    private void OpenBaxy()
    {
        bringingBack = Task.CompletedTask;
        StartBaxy();
        Close();
    }

    private void StartBaxy()
    {
        using Process? started = Process.Start(new ProcessStartInfo(paths.App)
        {
            UseShellExecute = true,
            WorkingDirectory = System.IO.Path.GetDirectoryName(paths.App)!,
        });
    }

    private void Uninstall(bool deleteData)
    {
        if (Voice.BaxyIsOpen())
        {
            failure = FailureKind.Open;
            screen = FailedScreen;
            Render(speak: true);
            return;
        }

        try
        {
            WindowsIntegration.Uninstall(paths, deleteData);
            finished = 0;
            screen = UninstalledScreen;
        }
        catch (Exception problem) when (problem is System.IO.IOException or UnauthorizedAccessException or InvalidOperationException)
        {
            Program.Log(problem.ToString());
            failure = FailureKind.Other;
            failureDetail = problem.Message;
            screen = FailedScreen;
        }

        Render(speak: true);
    }

    private void OnFirst(object sender, RoutedEventArgs e) => shown?.First?.Click();

    private void OnSecond(object sender, RoutedEventArgs e) => shown?.Second?.Click();

    private void OnThird(object sender, RoutedEventArgs e) => shown?.Third?.Click();

    private void OnVoice(object sender, RoutedEventArgs e)
    {
        voice.IsOn = !voice.IsOn;
        if (voice.IsOn && shown?.Line is not null)
        {
            voice.Say(texts.Language, shown.Line);
        }
        else
        {
            voice.Stop();
        }

        RenderPreferences();
    }

    private void OnText(object sender, RoutedEventArgs e)
    {
        textStep = (textStep + 1) % TextSizes.Length;
        Apply();
        Render(speak: false);
    }

    private void OnColors(object sender, RoutedEventArgs e)
    {
        theme = theme switch
        {
            ThemeKind.Dark => ThemeKind.Light,
            ThemeKind.Light => ThemeKind.HighContrast,
            _ => ThemeKind.Dark,
        };
        Apply();
        Render(speak: false);
    }

    private void OnLanguage(object sender, RoutedEventArgs e)
    {
        texts = Texts.For(texts.Language == "es" ? "en" : "es");
        shown = null;
        Render(speak: true);
    }

    [LibraryImport("kernel32.dll")]
    private static partial uint SetThreadExecutionState(uint flags);

    [LibraryImport("dwmapi.dll")]
    private static partial int DwmSetWindowAttribute(nint window, int attribute, ref int value, int size);
}
