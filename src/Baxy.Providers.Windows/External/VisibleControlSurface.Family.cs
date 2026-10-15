using System.Collections.Concurrent;
using System.Runtime.InteropServices;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// v3 point 1 (process family): an application whose content is drawn by a process it started. Measured live on a
/// messaging client (WinUI frame + WebView2): the frame's own window exposes eight elements (its caption buttons and
/// two panes) and no field, while the content is a top-level window of a child process (Chrome_WidgetWin_1 of the
/// WebView2 runtime) drawn over the frame, unowned, with the whole accessible tree (81 elements, the search field among
/// them). The view, the keys and the text read and went to the empty frame. The application's surface is that
/// window: a visible top-level window of a process descended from the application's own that covers at least 90 % of
/// the application's window and lies over it (above it in the Z order, not larger than it). No application is named:
/// WebView2, CEF and Electron hosts all draw this way.
/// </summary>
internal static partial class VisibleControlSurface
{
    // The share of the application's window the descendant's window must cover, and how much larger than it it may be
    // (a window of its own, a game or a player started by a launcher and filling the screen, is not its content: a
    // borderless full screen over a maximized window is the taskbar's height larger, about 4 %).
    internal const double FamilyCover = 0.90;
    internal const double FamilyOverflow = 1.02;

    /// <summary>
    /// A window a process of the application's family shows, as the choice of the surface reads it.
    /// <paramref name="ApplicationWindow"/>: the window is an application's window of its own, with its own button on
    /// the taskbar and in Alt-Tab (<see cref="IsApplicationWindow"/>), never the content of another window.
    /// </summary>
    internal readonly record struct FamilyWindow(
        nint Window, uint ProcessId, int Left, int Top, int Right, int Bottom, bool AboveFrame, bool ApplicationWindow = false);

    /// <summary>
    /// Whether a top-level window with the extended style <paramref name="exStyle"/> and the owner
    /// <paramref name="owner"/> is an application's window of its own: Windows gives it a button on the taskbar and a
    /// place in Alt-Tab (WS_EX_APPWINDOW, or unowned and neither WS_EX_TOOLWINDOW nor WS_EX_NOACTIVATE). Review of v3
    /// point 1: geometry alone cannot tell a WebView2 or CEF content window from a browser the application started
    /// maximized, or a game a launcher started full screen with the taskbar hidden (the same size as the maximized
    /// launcher); those are windows of their own, the content drawn over a frame is not. Measured live: the messaging
    /// client's WebView2 content window had WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE (0x08280080) and its frame the only
    /// button; browsers and an editor (unowned, 0x00200100) and a launcher's web helper (WS_EX_APPWINDOW, 0x02040100)
    /// are windows of their own.
    /// </summary>
    internal static bool IsApplicationWindow(long exStyle, nint owner)
    {
        const long appWindow = 0x00040000;
        const long toolWindow = 0x00000080;
        const long noActivate = 0x08000000;
        return (exStyle & appWindow) != 0 || (owner == 0 && (exStyle & (toolWindow | noActivate)) == 0);
    }

    private static bool IsApplicationWindow(nint window) =>
        IsApplicationWindow(GetWindowLongPtrW(window, -20).ToInt64(), GetWindow(window, 4));

    /// <summary>
    /// Whether <paramref name="child"/> is the content of the window at <paramref name="frame"/> (left, top, right,
    /// bottom): it covers at least <see cref="FamilyCover"/> of it and is not much larger than it, or it lies inside it
    /// (<see cref="PopupSlack"/> pixels of slack) filling at least <see cref="ContainedCover"/> of it. Pasada r15b B2
    /// (v3-16): an image viewer's editor is a WebView2 window inside the viewer's window under its own title bar
    /// (201,252–1623,923 inside 192,192–1632,932: 89.5 %), and the view read the viewer's empty frame instead.
    /// </summary>
    internal static bool CoversAsSurface(
        (int Left, int Top, int Right, int Bottom) frame,
        (int Left, int Top, int Right, int Bottom) child)
    {
        long frameArea = Area(frame.Left, frame.Top, frame.Right, frame.Bottom);
        long childArea = Area(child.Left, child.Top, child.Right, child.Bottom);
        if (frameArea <= 0 || childArea <= 0)
            return false;
        long overlap = Area(
            Math.Max(frame.Left, child.Left), Math.Max(frame.Top, child.Top),
            Math.Min(frame.Right, child.Right), Math.Min(frame.Bottom, child.Bottom));
        if (overlap >= FamilyCover * frameArea && childArea <= FamilyOverflow * frameArea)
            return true;
        return childArea >= ContainedCover * frameArea && IsSurfaceOfFrame(frame, child, ownedByFrame: false);
    }

    // The share of the application's window a descendant's window lying inside it must fill to be its content (a
    // dialog or a side pane of a helper fills less: measured, a dialog over two thirds of the window).
    internal const double ContainedCover = 0.80;

    /// <summary>
    /// Whether the descendant's window <paramref name="candidate"/> is drawn as the content of the window at
    /// <paramref name="frame"/>: it covers it as <see cref="CoversAsSurface"/> says and it is not an application's
    /// window of its own. The one rule of the surface (<see cref="ChooseFamilySurface"/>) and of the cover
    /// (<see cref="IsFamilyContent"/>): what is not the content covers the window.
    /// </summary>
    internal static bool IsContentOf((int Left, int Top, int Right, int Bottom) frame, FamilyWindow candidate) =>
        !candidate.ApplicationWindow
        && CoversAsSurface(frame, (candidate.Left, candidate.Top, candidate.Right, candidate.Bottom));

    private static long Area(int left, int top, int right, int bottom) =>
        right <= left || bottom <= top ? 0 : (long)(right - left) * (bottom - top);

    /// <summary>
    /// The surface of the application's window <paramref name="frame"/> among the windows of its descendants
    /// (<paramref name="candidates"/>, each already known to be a descendant's): the one above the frame covering
    /// the most of it as <see cref="CoversAsSurface"/> says; 0 when none does (the frame is its own surface).
    /// Ronda 20 P6 (<paramref name="acceptUnder"/>): when the frame's own tree is only its chrome
    /// (<see cref="ShowsOnlyCaption"/>), a content window lying under the frame counts too, one above it first.
    /// </summary>
    internal static nint ChooseFamilySurface(
        (int Left, int Top, int Right, int Bottom) frame,
        IEnumerable<FamilyWindow> candidates,
        bool acceptUnder = false)
    {
        nint best = 0;
        long bestOverlap = 0;
        bool bestAbove = false;
        foreach (FamilyWindow candidate in candidates)
        {
            if ((!candidate.AboveFrame && !acceptUnder) || !IsContentOf(frame, candidate))
                continue;
            long overlap = Area(
                Math.Max(frame.Left, candidate.Left), Math.Max(frame.Top, candidate.Top),
                Math.Min(frame.Right, candidate.Right), Math.Min(frame.Bottom, candidate.Bottom));
            bool better = candidate.AboveFrame != bestAbove && best != 0
                ? candidate.AboveFrame
                : overlap > bestOverlap;
            if (best == 0 ? overlap > 0 : better)
            {
                bestOverlap = overlap;
                best = candidate.Window;
                bestAbove = candidate.AboveFrame;
            }
        }

        return best;
    }

    // Ronda 20 P6: the UI Automation control types that are a window's chrome wherever they lie: its title bar, and a
    // busy indicator drawn while the content loads (measured: an image viewer's frame showed a ProgressBar «Ocupado»
    // in its middle while its editor, a WebView2 window under the frame, loaded). Structural data, no application's.
    private static readonly HashSet<string> ChromeKinds = new(StringComparer.Ordinal) { "TitleBar", "ProgressBar" };

    /// <summary>
    /// Ronda 20 P6 (v3-15, v3-16, v3-17): whether the controls read from the application's window
    /// <paramref name="frame"/> are only its chrome, with the content window <paramref name="content"/> under it: a
    /// title bar or a busy indicator (<see cref="ChromeKinds"/>), or a control whose middle lies in the title band, from
    /// the frame's top to the lowest of its title bars' bottoms or, when the content lies inside the frame, to the
    /// content's top (the caption buttons, the system menu, the back button, the title text, the panes of the
    /// non-client input). The band is never deeper than <see cref="ContainedCover"/> leaves of the frame. A control
    /// without a rectangle, or one lying where the content is, is content of the frame's own (a viewer's gallery, a
    /// side navigation beside a web view): the frame stays the view. Measured live: after «Editar» the viewer's frame
    /// lay above its editor's window and showed Minimize, Maximize, Close, Atrás, the system menu, the non-client input
    /// sink, the custom title bar, the title text and «Ocupado»; before it, 35 controls of its own.
    /// </summary>
    internal static bool ShowsOnlyCaption(
        (int Left, int Top, int Right, int Bottom) frame,
        (int Left, int Top, int Right, int Bottom) content,
        IEnumerable<(string Kind, (int Left, int Top, int Right, int Bottom)? Box)> controls)
    {
        int height = frame.Bottom - frame.Top;
        if (height <= 0)
            return false;
        var listed = controls.ToList();
        int deepest = frame.Top + (int)Math.Floor((1 - ContainedCover) * height);
        int band = frame.Top;
        foreach ((string kind, var box) in listed)
        {
            if (kind == "TitleBar" && box is { } title)
                band = Math.Max(band, title.Bottom);
        }

        if (content.Top > frame.Top && content.Top < frame.Bottom)
            band = Math.Max(band, content.Top);
        band = Math.Min(band, deepest);
        foreach ((string kind, var box) in listed)
        {
            if (ChromeKinds.Contains(kind))
                continue;
            if (box is not { } rect || rect.Bottom <= rect.Top)
                return false;
            int middle = rect.Top + (rect.Bottom - rect.Top) / 2;
            if (middle < frame.Top - PopupSlack || middle > band)
                return false;
        }

        return true;
    }

    /// <summary>
    /// Ronda 20 P6: whether the frame's controls could be only chrome over some content window (the deepest one
    /// <see cref="ContainedCover"/> allows): the cheap test before the family's windows are looked for.
    /// </summary>
    internal static bool MayShowOnlyCaption(
        (int Left, int Top, int Right, int Bottom) frame,
        IEnumerable<(string Kind, (int Left, int Top, int Right, int Bottom)? Box)> controls) =>
        ShowsOnlyCaption(frame,
            (frame.Left, frame.Top + (int)Math.Floor((1 - ContainedCover) * (frame.Bottom - frame.Top)), frame.Right, frame.Bottom),
            controls);

    /// <summary>
    /// Ronda 20 P6: a top-level window of another process seen over or under the application's window, as the choice
    /// of a content window under a chrome-only frame reads it: whether its process descends from the application's
    /// (<see cref="DescendsFrom"/>, never a protected one), whether it is cloaked, its extended style and its owner.
    /// </summary>
    internal readonly record struct SeenWindow(
        nint Window, uint ProcessId, int Left, int Top, int Right, int Bottom, bool AboveFrame, bool Descendant,
        bool Cloaked, long ExStyle, nint Owner);

    /// <summary>
    /// Ronda 20 P6: the content window chosen for a chrome-only frame (0 when none) and why: «above» or «under» when
    /// taken; otherwise the reason the closest window was not («app_window»: a window of its own; «cloaked»;
    /// «geometry»: a descendant's window that neither covers nor fills the frame; «not_descendant»: a window covering
    /// it of a process the application did not start; «frame_content»: the frame's tree shows content where the
    /// window lies; «none»: no window of another process over or under it), with that window's extended style and owner.
    /// </summary>
    internal readonly record struct ContentChoice(nint Window, string Reason, long ExStyle, nint Owner)
    {
        internal static ContentChoice Nothing => new(0, "none", 0, 0);
    }

    /// <summary>
    /// Ronda 20 P6: the content window of the application's window <paramref name="frame"/> among the windows
    /// <paramref name="seen"/>, above or under it (<see cref="ChooseFamilySurface"/> with candidates under), and why
    /// none when none is (<see cref="ContentChoice"/>). Only a visible, uncloaked window of a descendant process that
    /// is no window of its own and covers or fills the frame (<see cref="IsContentOf"/>) is taken.
    /// </summary>
    internal static ContentChoice ChooseContentWindow(
        (int Left, int Top, int Right, int Bottom) frame,
        IEnumerable<SeenWindow> seen)
    {
        var listed = seen.ToList();
        FamilyWindow AsFamily(SeenWindow window) => new(
            window.Window, window.ProcessId, window.Left, window.Top, window.Right, window.Bottom, window.AboveFrame,
            IsApplicationWindow(window.ExStyle, window.Owner));
        var accepted = listed.Where(window => window.Descendant && !window.Cloaked).Select(AsFamily).ToList();
        nint chosen = ChooseFamilySurface(frame, accepted, acceptUnder: true);
        if (chosen != 0)
        {
            SeenWindow taken = listed.First(window => window.Window == chosen);
            return new ContentChoice(chosen, taken.AboveFrame ? "above" : "under", taken.ExStyle, taken.Owner);
        }

        bool Covers(SeenWindow window) =>
            CoversAsSurface(frame, (window.Left, window.Top, window.Right, window.Bottom));
        (string Reason, Func<SeenWindow, bool> Test)[] reasons =
        [
            ("app_window", window => window.Descendant && !window.Cloaked && Covers(window)),
            ("cloaked", window => window.Descendant && window.Cloaked && Covers(window)),
            ("geometry", window => window.Descendant && !Covers(window)),
            ("not_descendant", window => !window.Descendant && Covers(window)),
        ];
        foreach ((string reason, Func<SeenWindow, bool> test) in reasons)
        {
            if (listed.FirstOrDefault(test) is { Window: not 0 } closest)
                return new ContentChoice(0, reason, closest.ExStyle, closest.Owner);
        }

        return ContentChoice.Nothing;
    }

    /// <summary>
    /// Ronda 20 P6: the content window of the family of <paramref name="frame"/>'s process lying over or under it
    /// (<see cref="ChooseContentWindow"/>), taken as its surface only when <paramref name="accept"/> holds for its
    /// rectangle (the frame's tree is only chrome around it): then the pair is linked as <see cref="FamilySurface"/>
    /// links it, so the mission stays tied to the frame and the front held by either counts for the other. Never for
    /// the shell's windows, this product's or a protected one.
    /// </summary>
    internal static ContentChoice TakeContentWindow(nint frame, Func<(int Left, int Top, int Right, int Bottom), bool> accept)
    {
        if (frame == 0 || !TryBounds(frame, out int left, out int top, out int right, out int bottom))
            return ContentChoice.Nothing;
        _ = GetWindowThreadProcessId(frame, out uint owner);
        if (owner == 0 || owner == ShellProcess())
            return ContentChoice.Nothing;
        uint self = unchecked((uint)Environment.ProcessId);
        var found = new List<(nint Window, uint Process, int L, int T, int R, int B, bool Above, bool Cloaked, long ExStyle, nint Owner)>();
        bool frameSeen = false;
        EnumWindowsProc callback = (candidate, unused) =>
        {
            if (candidate == frame)
            {
                frameSeen = true;
                return true;
            }

            // An owned window is seen too (its owner is said in the trace): one under the frame is owned by no window
            // above it, and whether it is the content is told by its process, its style and where it lies.
            if (!IsWindowVisible(candidate))
                return true;
            _ = GetWindowThreadProcessId(candidate, out uint process);
            if (process == 0 || process == owner || process == self || IsShellSurface(candidate))
                return true;
            if (!TryBounds(candidate, out int l, out int t, out int r, out int b)
                || Area(Math.Max(left, l), Math.Max(top, t), Math.Min(right, r), Math.Min(bottom, b)) <= 0)
                return true;
            bool cloaked = DwmGetWindowAttribute(candidate, 14, out int cloak, sizeof(int)) == 0 && cloak != 0;
            found.Add((candidate, process, l, t, r, b, !frameSeen, cloaked,
                GetWindowLongPtrW(candidate, -20).ToInt64(), GetWindow(candidate, 4)));
            return true;
        };
        _ = EnumWindows(callback, nint.Zero);
        if (!frameSeen || found.Count == 0 || StartTime(owner) is not { } rootStarted)
            return ContentChoice.Nothing;
        Dictionary<uint, uint> parents = ParentByProcess();
        var seen = found.Select(window => new SeenWindow(
            window.Window, window.Process, window.L, window.T, window.R, window.B, window.Above,
            DescendsFrom(window.Process, owner, rootStarted, parents)
                && !ProtectedFrom(ProcessIdentity(window.Process).ProcessName, null),
            window.Cloaked, window.ExStyle, window.Owner)).ToList();
        ContentChoice choice = ChooseContentWindow((left, top, right, bottom), seen);
        if (choice.Window == 0)
            return choice;
        SeenWindow taken = seen.First(window => window.Window == choice.Window);
        if (!accept((taken.Left, taken.Top, taken.Right, taken.Bottom)))
            return choice with { Window = 0, Reason = "frame_content" };
        LinkFamily(frame, owner, taken.Window, taken.ProcessId, FamilyOf(owner, rootStarted, parents));
        return choice;
    }

    /// <summary>
    /// The window a person sees for the application's window <paramref name="window"/>: the window of a descendant
    /// process drawn over it as its content (<see cref="ChooseFamilySurface"/>), else the window itself. Never the
    /// shell's (every program started from the desktop descends from it), never this product's, never a developer's
    /// protected window. The pair is remembered so the front held by either counts for the other
    /// (<see cref="FamilyPeer"/>).
    /// </summary>
    internal static nint FamilySurface(nint window)
    {
        if (window == 0 || !TryBounds(window, out int left, out int top, out int right, out int bottom))
            return window;
        _ = GetWindowThreadProcessId(window, out uint owner);
        if (owner == 0 || owner == ShellProcess())
            return window;
        uint self = unchecked((uint)Environment.ProcessId);
        var candidates = new List<FamilyWindow>();
        bool frameSeen = false;
        EnumWindowsProc callback = (candidate, unused) =>
        {
            if (candidate == window)
            {
                frameSeen = true;
                return false;
            }

            if (!IsWindowVisible(candidate) || GetAncestor(candidate, 3) != candidate)
                return true;
            if (DwmGetWindowAttribute(candidate, 14, out int cloaked, sizeof(int)) == 0 && cloaked != 0)
                return true;
            _ = GetWindowThreadProcessId(candidate, out uint process);
            if (process == 0 || process == owner || process == self || IsShellSurface(candidate))
                return true;
            if (!TryBounds(candidate, out int l, out int t, out int r, out int b)
                || !CoversAsSurface((left, top, right, bottom), (l, t, r, b)))
                return true;
            candidates.Add(new FamilyWindow(candidate, process, l, t, r, b, AboveFrame: true, IsApplicationWindow(candidate)));
            return true;
        };
        _ = EnumWindows(callback, nint.Zero);
        if (!frameSeen || candidates.Count == 0)
            return window;

        Dictionary<uint, uint> parents = ParentByProcess();
        DateTime? rootStarted = StartTime(owner);
        if (rootStarted is null)
            return window;
        candidates.RemoveAll(candidate =>
            !DescendsFrom(candidate.ProcessId, owner, rootStarted.Value, parents)
            || ProtectedFrom(ProcessIdentity(candidate.ProcessId).ProcessName, null));
        nint surface = ChooseFamilySurface((left, top, right, bottom), candidates);
        if (surface == 0)
            return window;
        _ = GetWindowThreadProcessId(surface, out uint surfaceProcess);
        uint[] family = FamilyOf(owner, rootStarted.Value, parents);
        LinkFamily(window, owner, surface, surfaceProcess, family);
        return surface;
    }

    /// <summary>
    /// fable/cu-v3-clic-chromium: the windows a click bound to <paramref name="frame"/> may post its press into, among
    /// the windows of its descendants (<paramref name="candidates"/>): every one drawn as its content
    /// (<see cref="IsContentOf"/>), whether it lies above the frame or under it. Measured live on a WebView2 messaging
    /// client: once its frame was activated (by an opening) it lay above its content window in the Z order, so the
    /// view stayed on the frame (no field) while the person saw the content; a label read on the screen there is that
    /// content's. The surface of the view keeps its rule (<see cref="ChooseFamilySurface"/>); only a press sent to the
    /// content's render window at the point where a label was read uses these. A window of its own (a browser, a game)
    /// is never one.
    /// </summary>
    internal static IReadOnlyList<nint> ContentWindowsOf(
        (int Left, int Top, int Right, int Bottom) frame,
        IEnumerable<FamilyWindow> candidates) =>
        candidates.Where(candidate => IsContentOf(frame, candidate)).Select(candidate => candidate.Window).ToArray();

    /// <summary>
    /// The content windows of the family of <paramref name="window"/>'s process (<see cref="ContentWindowsOf"/>), above
    /// or under it; none for the shell's windows, this product's or a protected one.
    /// </summary>
    internal static IReadOnlyList<nint> FamilyContentWindows(nint window)
    {
        if (window == 0 || !TryBounds(window, out int left, out int top, out int right, out int bottom))
            return [];
        _ = GetWindowThreadProcessId(window, out uint owner);
        if (owner == 0 || owner == ShellProcess())
            return [];
        uint self = unchecked((uint)Environment.ProcessId);
        var candidates = new List<FamilyWindow>();
        bool frameSeen = false;
        EnumWindowsProc callback = (candidate, unused) =>
        {
            if (candidate == window)
            {
                frameSeen = true;
                return true;
            }

            if (!IsWindowVisible(candidate) || GetAncestor(candidate, 3) != candidate)
                return true;
            if (DwmGetWindowAttribute(candidate, 14, out int cloaked, sizeof(int)) == 0 && cloaked != 0)
                return true;
            _ = GetWindowThreadProcessId(candidate, out uint process);
            if (process == 0 || process == owner || process == self || IsShellSurface(candidate))
                return true;
            if (!TryBounds(candidate, out int l, out int t, out int r, out int b)
                || !CoversAsSurface((left, top, right, bottom), (l, t, r, b)))
                return true;
            candidates.Add(new FamilyWindow(candidate, process, l, t, r, b, AboveFrame: !frameSeen, IsApplicationWindow(candidate)));
            return true;
        };
        _ = EnumWindows(callback, nint.Zero);
        if (candidates.Count == 0)
            return [];
        Dictionary<uint, uint> parents = ParentByProcess();
        if (StartTime(owner) is not { } rootStarted)
            return [];
        candidates.RemoveAll(candidate =>
            !DescendsFrom(candidate.ProcessId, owner, rootStarted, parents)
            || ProtectedFrom(ProcessIdentity(candidate.ProcessId).ProcessName, null));
        return ContentWindowsOf((left, top, right, bottom), candidates);
    }

    /// <summary>
    /// Pasada r15b B2 (v3-17): whether a top-level window of the application's process family is one of the
    /// application's own surfaces next to its window <paramref name="frame"/> (left, top, right, bottom): owned by it
    /// (<paramref name="ownedByFrame"/>: its owner chain ends at the frame, a menu's or a dialog's popup host) or lying
    /// inside it (<paramref name="child"/> within the frame's rectangle, <see cref="PopupSlack"/> pixels of slack). A
    /// window of the family elsewhere on the screen (a browser it started, a window of its own) is none.
    /// </summary>
    internal static bool IsSurfaceOfFrame(
        (int Left, int Top, int Right, int Bottom) frame,
        (int Left, int Top, int Right, int Bottom) child,
        bool ownedByFrame)
    {
        if (ownedByFrame)
            return true;
        if (Area(child.Left, child.Top, child.Right, child.Bottom) <= 0 || Area(frame.Left, frame.Top, frame.Right, frame.Bottom) <= 0)
            return false;
        return child.Left >= frame.Left - PopupSlack && child.Top >= frame.Top - PopupSlack
            && child.Right <= frame.Right + PopupSlack && child.Bottom <= frame.Bottom + PopupSlack;
    }

    // A popup drawn flush with its window's border may pass it by its shadow's width.
    internal const int PopupSlack = 8;

    // A tooltip's window class (the common controls' «tooltips_class32», and any class named as one: the worker's own
    // reading of a tooltip, Get-TipName, takes the same).
    private static readonly System.Text.RegularExpressions.Regex TooltipClass = new(
        @"tool\s*tip", System.Text.RegularExpressions.RegexOptions.IgnoreCase | System.Text.RegularExpressions.RegexOptions.CultureInvariant);

    /// <summary>
    /// Review of fable/cu-v3-carga-preguntas (finding 2): whether the person's pointer rests on <paramref name="window"/>'s
    /// root now (inside its rectangle, physical pixels). A hover there shows a tooltip, or a link's status bubble, in
    /// a window of the application's own family, of the same kind as a menu's popup host: a popup born then says
    /// nothing of a click.
    /// </summary>
    internal static bool PointerRestsOn(nint window)
    {
        nint root = window == 0 ? 0 : GetAncestor(window, 2);
        if (root == 0 || !TryBounds(root, out int left, out int top, out int right, out int bottom))
            return false;
        return InPhysicalPixels(CursorNow) is { } cursor
            && cursor.X >= left && cursor.X < right && cursor.Y >= top && cursor.Y < bottom;
    }

    private static (int X, int Y)? CursorNow() => GetCursorPos(out Point point) ? (point.X, point.Y) : null;

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool GetCursorPos(out Point point);

    /// <summary>
    /// Pasada r15b B2 (v3-17 «...» opened «Host de ventanas emergentes» and its click was told
    /// visible_button_postread_unchanged): the visible, uncloaked top-level windows of <paramref name="window"/>'s
    /// process (or of the family its surface was found with) that are its root's own surfaces
    /// (<see cref="IsSurfaceOfFrame"/>), the root itself left out. What a click's post-read compares before and after:
    /// a popup born of the click is its effect, while the window's own image stays the same.
    /// </summary>
    internal static IReadOnlyList<nint> PopupsOf(nint window)
    {
        nint root = window == 0 ? 0 : GetAncestor(window, 2);
        if (root == 0 || !TryBounds(root, out int left, out int top, out int right, out int bottom))
            return [];
        _ = GetWindowThreadProcessId(root, out uint process);
        if (process == 0 || process == ShellProcess())
            return [];
        uint[] family = SurfaceFamily(window) ?? [process];
        nint frameOwner = FamilyPeer(window) is var peer and not 0 ? GetAncestor(peer, 2) : 0;
        var found = new List<nint>();
        EnumWindowsProc callback = (candidate, unused) =>
        {
            if (candidate == root || candidate == frameOwner || !IsWindowVisible(candidate))
                return true;
            if (DwmGetWindowAttribute(candidate, 14, out int cloaked, sizeof(int)) == 0 && cloaked != 0)
                return true;
            // A window the pointer passes through (WS_EX_TRANSPARENT: a shadow, an overlay) or the hover's tooltip is
            // no surface a click opened: a pointer resting on a control shows its tooltip by itself.
            if ((GetWindowLongPtrW(candidate, -20).ToInt64() & 0x20) != 0 || TooltipClass.IsMatch(ClassName(candidate)))
                return true;
            _ = GetWindowThreadProcessId(candidate, out uint owner);
            if (owner == 0 || !family.Contains(owner))
                return true;
            nint rootOwner = GetAncestor(candidate, 3);
            bool owned = rootOwner != candidate && (rootOwner == root || (frameOwner != 0 && rootOwner == frameOwner));
            if (TryBounds(candidate, out int l, out int t, out int r, out int b)
                && IsSurfaceOfFrame((left, top, right, bottom), (l, t, r, b), owned))
                found.Add(candidate);
            return true;
        };
        _ = EnumWindows(callback, nint.Zero);
        return found;
    }

    // The front held by a window and its family surface counts for the other (the frame takes the keys for the content
    // drawn over it, measured: keys sent with the frame in front reached the child window's focused field).
    private readonly record struct FamilyLink(nint Peer, uint PeerProcess, uint OwnProcess, uint[] Family, bool IsSurface);

    private static readonly ConcurrentDictionary<nint, FamilyLink> FamilyLinks = new();

    private static void LinkFamily(nint frame, uint frameProcess, nint surface, uint surfaceProcess, uint[] family)
    {
        FamilyLinks[surface] = new FamilyLink(frame, frameProcess, surfaceProcess, family, IsSurface: true);
        FamilyLinks[frame] = new FamilyLink(surface, surfaceProcess, frameProcess, family, IsSurface: false);
    }

    /// <summary>
    /// The other window of a family pair <see cref="FamilySurface"/> found (the application's window for its
    /// surface, the surface for the application's window), while both are alive and still owned by the processes
    /// they were found with; 0 otherwise. A window of any other process is never a peer.
    /// </summary>
    internal static nint FamilyPeer(nint window)
    {
        if (window == 0 || !FamilyLinks.TryGetValue(window, out FamilyLink link))
            return 0;
        if (IsWindow(link.Peer) && IsWindow(window)
            && GetWindowThreadProcessId(link.Peer, out uint peerProcess) != 0 && peerProcess == link.PeerProcess
            && GetWindowThreadProcessId(window, out uint ownProcess) != 0 && ownProcess == link.OwnProcess)
            return link.Peer;
        _ = FamilyLinks.TryRemove(window, out _);
        return 0;
    }

    /// <summary>
    /// The application's process and its descendants when <paramref name="surface"/> is the family surface of an
    /// application's window (the application's process first); null when the window is its own surface.
    /// </summary>
    internal static uint[]? SurfaceFamily(nint surface) =>
        FamilyPeer(surface) != 0 && FamilyLinks.TryGetValue(surface, out FamilyLink link) && link.IsSurface
            ? link.Family
            : null;

    /// <summary>
    /// Whether <paramref name="cover"/>, a window of <paramref name="coverProcess"/> drawn over the centre of
    /// <paramref name="window"/> (of <paramref name="process"/>), is that window's content and not a window over it:
    /// it lies over it as <see cref="CoversAsSurface"/> says, it is not an application's window of its own
    /// (<see cref="IsApplicationWindow(long, nint)"/>: a browser or a game the application started covers it) and
    /// its process descends from the window's. Only in that direction (a window of a process that started the
    /// application, a developer's editor or the shell, is always a cover), and never for the shell's windows.
    /// </summary>
    internal static bool IsFamilyContent(nint window, uint process, nint cover, uint coverProcess)
    {
        if (process == 0 || coverProcess == 0 || process == ShellProcess())
            return false;
        if (!TryBounds(window, out int left, out int top, out int right, out int bottom)
            || !TryBounds(cover, out int l, out int t, out int r, out int b)
            || !IsContentOf((left, top, right, bottom),
                new FamilyWindow(cover, coverProcess, l, t, r, b, AboveFrame: true, IsApplicationWindow(cover))))
            return false;
        return StartTime(process) is { } started && DescendsFrom(coverProcess, process, started, ParentByProcess());
    }

    /// <summary>
    /// Whether <paramref name="process"/> is the application's process <paramref name="application"/> or one it
    /// started (through processes it started, each started after it).
    /// </summary>
    internal static bool InApplicationFamily(uint application, uint process) =>
        application != 0 && process != 0
        && (process == application
            || StartTime(application) is { } started && DescendsFrom(process, application, started, ParentByProcess()));

    // Whether the process descends from the root, through parents each started after the root.
    internal static bool DescendsFrom(uint process, uint root, DateTime rootStarted, IReadOnlyDictionary<uint, uint> parents,
        Func<uint, DateTime, bool>? startedAfter = null)
    {
        startedAfter ??= StartedAfter;
        uint current = process;
        for (int depth = 0; depth < 16 && current != 0 && current != root; depth++)
        {
            if (!startedAfter(current, rootStarted) || !parents.TryGetValue(current, out uint parent) || parent == current)
                return false;
            current = parent;
        }

        return current == root && process != root;
    }

    private static uint[] FamilyOf(uint root, DateTime rootStarted, Dictionary<uint, uint> parents)
    {
        var family = new List<uint> { root };
        foreach (uint process in parents.Keys)
        {
            if (process != root && DescendsFrom(process, root, rootStarted, parents))
                family.Add(process);
        }

        return [.. family];
    }

    private static Dictionary<uint, uint> ParentByProcess()
    {
        var parents = new Dictionary<uint, uint>();
        foreach ((uint parent, List<uint> children) in ChildrenByParent())
        {
            foreach (uint child in children)
                parents[child] = parent;
        }

        return parents;
    }

    private static DateTime? StartTime(uint processId)
    {
        try
        {
            using var process = System.Diagnostics.Process.GetProcessById(unchecked((int)processId));
            return process.StartTime.ToUniversalTime();
        }
        catch (Exception exception) when (exception is ArgumentException
            or InvalidOperationException or System.ComponentModel.Win32Exception
            or NotSupportedException)
        {
            return null;
        }
    }

    // The process that holds the desktop and the taskbar: every program a person starts from them descends from it,
    // so its windows have no family surface.
    private static uint ShellProcess()
    {
        nint shell = GetShellWindow();
        if (shell == 0)
            return 0;
        _ = GetWindowThreadProcessId(shell, out uint process);
        return process;
    }

    /// <summary>The shell's desktop window (0 in a session without one): no application's and never the person's.</summary>
    internal static nint ShellWindow() => GetShellWindow();

    [LibraryImport("user32.dll")]
    private static partial nint GetShellWindow();
}
