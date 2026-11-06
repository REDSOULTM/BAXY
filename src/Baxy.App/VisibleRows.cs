using System.Runtime.InteropServices;
using System.Text.RegularExpressions;
using System.Windows.Automation;

namespace Baxy.App;

/// <summary>
/// Banco de uso 2026-11-03 (R11, R12): «manda al Grupo de prueba el mensaje …» with a chat application open whose window
/// is «Chat de prueba»: the chat named is a row of the list inside it, and the message refused for a channel not said
/// (NetworkEgress.Unsaid) told the model no window was named, so it asked the person the channel. This reads the visible
/// rows of the lists of the other applications' windows through UI Automation, and keeps only those whose whole name
/// the person said (the comparison given, NetworkEgress.NamesRow): no other row's name leaves this reader.
/// <para>
/// Fuentes: Microsoft Learn, «UI Automation Support for the ListItem Control Type» (a list item's Name comes from its
/// text; IsOffscreen says whether it is scrolled into view) and its DataItem and TreeItem pages; W3C Core-AAM 1.2 (the
/// web's listitem and option map to UIA ListItem, row to DataItem, treeitem to TreeItem, as the chat lists of web-based
/// clients are exposed); «UI Automation Threading Issues» (a client calls UI Automation from a thread of its own);
/// «Caching in UI Automation Clients» (the Name fetched with the search, one cross-process call per window).
/// </para>
/// <para>
/// Encargo 65 (cosecha F2): a request for the newest mail of one sender in a webmail the person named, with that site
/// open in a tab of their browser, read Outlook's newest mail instead. In the same pass this reads the tabs of those windows (TabItem: a tab
/// strip's tab, named by its page's title in Chromium and Gecko browsers, and whether it is the one shown,
/// SelectionItemPattern.IsSelected), shown or scrolled off the strip, and keeps those the second comparison accepts
/// (NetworkEgress.NamesTab). Microsoft Learn, «UI Automation Support for the TabItem Control Type»: a tab item is named
/// by its own text and supports SelectionItemPattern.
/// </para>
/// </summary>
internal static class VisibleRows
{
    /// <summary>How long the rows are read at most; what was read by then is what is said. Encargo 65: a Chrome window
    /// with two local pages took 2.3 s to search (measured 03-11, development PC), past the 1.5 s this was; it is read only when a
    /// rule asks (a message refused, the turn's first call failed or read another application).</summary>
    internal static readonly TimeSpan Budget = TimeSpan.FromMilliseconds(3000);

    private static readonly Condition Rows = new OrCondition(
        new AndCondition(
            new OrCondition(
                new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.ListItem),
                new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.DataItem),
                new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.TreeItem)),
            new PropertyCondition(AutomationElement.IsOffscreenProperty, false)),
        new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.TabItem));

    /// <summary>The rows <paramref name="named"/> accepts and the tabs <paramref name="namedTab"/> accepts, of the windows
    /// of other applications on screen.</summary>
    internal static IReadOnlyList<VisibleRow> Read(Func<string, bool> named, Func<string, bool> namedTab) =>
        Read(HeartbeatMoment.OtherWindowHandles(), named, namedTab, Budget);

    internal static IReadOnlyList<VisibleRow> Read(
        IReadOnlyList<nint> windows, Func<string, bool> named, Func<string, bool> namedTab, TimeSpan budget)
    {
        var reading = new Reading();
        long deadline = Environment.TickCount64 + (long)budget.TotalMilliseconds;
        var reader = new Thread(() => Collect(windows, named, namedTab, reading, deadline))
        {
            IsBackground = true,
            Name = "BAXY visible rows",
        };
        reader.SetApartmentState(ApartmentState.MTA);
        reader.Start();
        _ = reader.Join(budget);
        return reading.Close();
    }

    private static void Collect(
        IReadOnlyList<nint> windows, Func<string, bool> named, Func<string, bool> namedTab, Reading reading, long deadline)
    {
        foreach (nint window in windows)
        {
            if (Environment.TickCount64 >= deadline || reading.Closed)
            {
                return;
            }

            try
            {
                // The window's element is taken live, outside the cache request: one fetched with AutomationElementMode
                // None has no reference to search from.
                AutomationElement root = AutomationElement.FromHandle(window);
                var request = new CacheRequest { AutomationElementMode = AutomationElementMode.None };
                request.Add(AutomationElement.NameProperty);
                request.Add(AutomationElement.ControlTypeProperty);
                request.Add(SelectionItemPattern.IsSelectedProperty);
                List<AutomationElement> found;
                using (request.Activate())
                {
                    found = [.. root.FindAll(TreeScope.Descendants, Rows).Cast<AutomationElement>()];
                }

                // Opera GX (documentacion/NAVEGADOR_USUARIO.md, «Opera GX»): with its Quick Access page shown, the window's
                // first child is dead and a search from the root finds nothing; its other children are searched one by one.
                if (found.Count == 0 && DeadFirstChild(root) is { } children)
                {
                    foreach (AutomationElement child in children)
                    {
                        try
                        {
                            using (request.Activate())
                            {
                                found.AddRange(child.FindAll(TreeScope.Subtree, Rows).Cast<AutomationElement>());
                            }
                        }
                        catch (Exception exception) when (exception is ElementNotAvailableException or COMException)
                        {
                            // Another dead child gives nothing; the next is read.
                        }
                    }
                }

                string title = HeartbeatMoment.WindowTitle(window);
                (string Name, bool Shown)[] tabs = [.. found
                    .Where(static element => element.Cached.ControlType == ControlType.TabItem)
                    .Select(static element => (element.Cached.Name?.Trim() ?? string.Empty, element.GetCachedPropertyValue(
                        SelectionItemPattern.IsSelectedProperty, true) is true))
                    .Where(static tab => tab.Item1.Length > 0)];
                bool pages = PageStrip(title, tabs);
                bool selection = tabs.Any(static tab => tab.Shown);
                var kept = new List<(string Name, bool Tab, bool Shown)>();
                foreach (AutomationElement element in found)
                {
                    string name = element.Cached.Name?.Trim() ?? string.Empty;
                    bool tab = element.Cached.ControlType == ControlType.TabItem;
                    if (name.Length > 0 && (tab ? pages && namedTab(name) : named(name))
                        && !kept.Any(seen => seen.Name == name && seen.Tab == tab))
                    {
                        // A strip that says no tab selected (Chrome, measured 03-11) shows the one the window is titled by.
                        kept.Add((name, tab, tab && (selection
                            ? element.GetCachedPropertyValue(SelectionItemPattern.IsSelectedProperty, true) is true
                            : TitledBy(title, name))));
                    }
                }

                if (kept.Count > 0)
                {
                    reading.Add(title, HeartbeatMoment.ProcessOf(window), kept);
                }
            }
            catch (Exception exception) when (exception is ElementNotAvailableException or InvalidOperationException
                or COMException)
            {
                // A window closed or not answering while it was read gives no rows.
            }
        }
    }

    /// <summary>
    /// Encargo 65 (revisión): whether a window's tabs are a strip of pages or documents, the way a browser's (or an
    /// editor's) are: the window's title starts with the first part (before « - », « | », « – », « — ») of the name of the
    /// tab it shows, as every browser titles its window by the page in front. A ribbon's tabs («Inicio» in Word) or a
    /// page's own tabs are never what the window is titled by, so their names are not compared with the person's words.
    /// A strip whose tabs say none is selected (Chrome's, measured 03-11: SelectionItemPattern.IsSelected false on every
    /// tab) is one when the window is titled by any of them.
    /// </summary>
    internal static bool PageStrip(string title, IReadOnlyCollection<(string Name, bool Shown)> tabs)
    {
        bool selection = tabs.Any(static tab => tab.Shown);
        return tabs.Any(tab => (tab.Shown || !selection) && TitledBy(title, tab.Name));
    }

    // The window's title starts with the first part of the tab's name.
    private static bool TitledBy(string title, string tab) =>
        Regex.Split(tab, @"\s+[-|–—]\s+")[0].Trim() is { Length: > 0 } first
        && title.Trim().StartsWith(first, StringComparison.OrdinalIgnoreCase);

    // The window's children after the first, from the last, when the first is dead (its properties cannot be read);
    // null when it is alive or there is none.
    private static List<AutomationElement>? DeadFirstChild(AutomationElement root)
    {
        TreeWalker walker = TreeWalker.RawViewWalker;
        AutomationElement? first = walker.GetFirstChild(root);
        if (first is null)
        {
            return null;
        }

        try
        {
            _ = first.Current.ControlType;
            return null;
        }
        catch (Exception exception) when (exception is ElementNotAvailableException or COMException)
        {
            var children = new List<AutomationElement>();
            for (AutomationElement? child = walker.GetLastChild(root); child is not null && children.Count < 32;
                child = walker.GetPreviousSibling(child))
            {
                children.Add(child);
            }

            return children;
        }
    }

    // What the reader found until the caller stopped waiting; nothing is added after that.
    private sealed class Reading
    {
        private readonly List<VisibleRow> _rows = [];
        private readonly Lock _gate = new();

        internal bool Closed { get; private set; }

        internal void Add(string title, string? process, IEnumerable<(string Name, bool Tab, bool Shown)> rows)
        {
            lock (_gate)
            {
                if (!Closed)
                {
                    _rows.AddRange(rows.Select(row => new VisibleRow(title, process, row.Name, row.Tab, row.Shown)));
                }
            }
        }

        internal IReadOnlyList<VisibleRow> Close()
        {
            lock (_gate)
            {
                Closed = true;
                return [.. _rows];
            }
        }
    }
}

/// <summary>A row of a list (or, <see cref="Tab"/>, a tab of a tab strip, <see cref="Shown"/> when it is the one shown)
/// of another application's window, with that window's title and process.</summary>
internal readonly record struct VisibleRow(string Title, string? Process, string Name, bool Tab = false, bool Shown = false);
