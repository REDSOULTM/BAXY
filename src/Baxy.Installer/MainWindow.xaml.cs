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
    private long dataBytes;

    internal MainWindow(ReleaseManifest? manifest, bool uninstalling, InstallPaths paths, bool voiceAllowed, bool updating = false)
    {
        InitializeComponent();
        this.paths = paths;
        voice = new Voice(voiceAllowed);
        IReadOnlyList<GpuAdapter> adapters = MachineGpu.Installed();
        this.manifest = manifest?.ForMachine(adapters);
        this.uninstalling = uninstalling;
        this.updating = updating && !uninstalling && this.manifest is not null;
        http.DefaultRequestHeaders.UserAgent.ParseAdd("BAXY-Instalador/" + (manifest?.Version ?? "0"));
        support = MachineGpu.Choose(adapters);
        if (this.manifest is not null)
        {
            Program.LogMachine(this.manifest, adapters, paths);
            installation = new Installation(this.manifest, paths, new PartFetcher(http, gate: new Func<PauseGate>(() => pause)));
        }

        texts = Texts.For(CultureInfo.CurrentUICulture.TwoLetterISOLanguageName == "es" ? "es" : "en");
        theme = SystemParameters.HighContrast ? ThemeKind.HighContrast : ThemeKind.Dark;
        textStep = WindowsTextStep();
        screen = uninstalling ? UninstallScreen : Greeting;
        ticker.Tick += (_, _) => Tick();
        SourceInitialized += (_, _) => TitleBarFollowsTheme();
        Loaded += (_, _) =>
        {
            Apply();
            if (this.updating)
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
            work?.Cancel();
            closing.Cancel = installation?.IsSwapping == true;
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

    private ScreenView WarningScreen()
    {
        (string body, string line) = support switch
        {
            GpuSupport.NotMeasured => (texts.WarningIntel, "warningIntel"),
            GpuSupport.TooLittleMemory => (texts.WarningMemory, "warningMemory"),
            _ => (texts.WarningNone, "warningNone"),
        };
        return new ScreenView(
            Face.Sad,
            support == GpuSupport.None ? texts.NoGpuTitle : texts.WarningTitle,
            body,
            Help: texts.WarningHelp,
            Hint: support == GpuSupport.None ? string.Empty : texts.LicenseNotice,
            First: new ButtonView(support == GpuSupport.None ? texts.Close : texts.NotNow, false, Close, IsDefault: true, IsCancel: true),
            Second: support == GpuSupport.None ? null : new ButtonView(texts.InstallAnyway, true, Start),
            Third: support == GpuSupport.None ? null : new ButtonView(texts.ReadLicense, false, ShowLicense),
            Line: line);
    }

    private ScreenView LicenseScreen() => new(
        Face.Happy,
        texts.LicenseTitle,
        WindowsIntegration.LicenseText(texts.Language),
        First: new ButtonView(texts.Back, false, BackFromLicense, IsDefault: true, IsCancel: true),
        Line: "license",
        LongText: true);

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

    private ScreenView UninstallScreen() => new(
        Face.Sad,
        texts.UninstallTitle,
        texts.UninstallBodyFor(WindowsIntegration.RingsToRemove(paths), dataBytes, WindowsPlaces.ForThisUser.Data),
        First: new ButtonView(texts.UninstallKeep, false, () => Uninstall(deleteData: false), IsDefault: true),
        Second: WindowsIntegration.ADifferentBaxyIsInstalled() ? null : new ButtonView(texts.UninstallDelete, false, () => Uninstall(deleteData: true)),
        Third: new ButtonView(texts.Cancel, false, Close, IsCancel: true),
        Line: "uninstall");

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

    private void Retry()
    {
        screen = uninstalling ? UninstallScreen : Greeting;
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
        for (int waited = 0; Voice.BaxyIsOpen() && waited < 120; waited++)
        {
            await Task.Delay(TimeSpan.FromMilliseconds(500));
        }

        Start();
    }

    private void Start()
    {
        if (Voice.BaxyIsOpen())
        {
            // Better now than after downloading gigabytes: the swap would refuse at the very end.
            failure = FailureKind.Open;
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
        }
#pragma warning disable CA1031 // Whatever stopped the installation is told to the person, with its cause.
        catch (Exception problem)
#pragma warning restore CA1031
        {
            Program.Log(problem.ToString());
            failure = Failures.Classify(problem, Voice.BaxyIsOpen);
            failureDetail = problem.Message;
            Finish(FailedScreen);
        }
    }

    /// <summary>
    /// The last step, with BAXY's files already in place. Windows refusing it is not «I couldn't install myself» (INS-5):
    /// BAXY is there and opens, and the person tries this step again alone, with nothing downloaded twice.
    /// </summary>
    private void Register()
    {
        try
        {
            WindowsIntegration.Register(paths, manifest!.Version, manifest.InstalledBytes);
        }
        catch (NotRegisteredException refused)
        {
            Program.Log(refused.ToString());
            // The same screen again is said again: the person pressed «try again» and it was refused once more.
            shown = null;
            Finish(NotRegisteredScreen);
            return;
        }

        Program.Log("installed");
        Finish(DoneScreen);
        if (updating)
        {
            // The person asked for the update in BAXY: it comes back as it was before it closed.
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
        using Process? started = Process.Start(new ProcessStartInfo(paths.App)
        {
            UseShellExecute = true,
            WorkingDirectory = System.IO.Path.GetDirectoryName(paths.App)!,
        });
        Close();
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
