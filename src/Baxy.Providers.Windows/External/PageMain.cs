using System.Text;
using System.Text.RegularExpressions;

namespace Baxy.Providers.Windows.External;

// Goal h-web (2026-10-25): the part of a page that is its content. web.fetch receipts were 30 % of
// every receipt's characters in the e2e traces (c3-*, ho6-*), and the 4B model paged through 8-14 pages of 4,000
// characters of a list until the context overflowed (V6E008/V6E014, V5E008). Two rules, by the page's own markup only,
// never by what its text says:
// 1. An element whose class or id names boilerplate (cookie or consent banners, breadcrumbs, share or social bars,
//    newsletters, related links, navigation boxes, edit links, reference marks) is left out with all it holds.
// 2. When the page names its main content (<main>, role="main", or <article>) and that holds text enough, only it is
//    read: what is around it is the site, not the page.
internal static class PageMain
{
    private static readonly TimeSpan RegexBudget = TimeSpan.FromSeconds(2);

    private static readonly Regex Tag = new(
        @"<(/?)([a-zA-Z][a-zA-Z0-9-]*)\b([^>]*)>", RegexOptions.CultureInvariant, RegexBudget);

    private static readonly Regex Marked = new(
        @"\b(?:class|id)\s*=\s*[""'][^""']*?(?:cookie|consent|gdpr|banner|breadcrumb|share|social|newsletter|subscribe|"
        + @"related|navbox|navbar|menu|sidebar|mw-editsection|reference|noprint|advert|promo|skip-link|toc\b|catlinks|"
        + @"mw-jump|printfooter|site-header|site-footer)[^""']*[""']",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant, RegexBudget);

    // Code and comments go first: a tag written inside a script's string is not the page's.
    private static readonly Regex Code = new(
        @"<!--.*?-->|<(script|style|noscript|template|svg).*?</\s*>",
        RegexOptions.Singleline | RegexOptions.IgnoreCase | RegexOptions.CultureInvariant, RegexBudget);

    // A tag whose quoted attribute holds «<» or «>» (Wikipedia's data-mw JSON): they are blanked inside the quotes, so
    // the tag ends where it ends and its attribute never reaches the text (renew_v1 traces: 3,441 characters of JSON
    // in the first page of «Organización de las Naciones Unidas»).
    private static readonly Regex QuotedTag = new(
        @"<[a-zA-Z](?:[^>""']|""[^""]*""|'[^']*')*>", RegexOptions.CultureInvariant, RegexBudget);

    private static string Unquoted(string html) => QuotedTag.Replace(html, static tag =>
        tag.Value.IndexOfAny(['<', '>'], 1) < tag.Length - 1
            ? tag.Value[0] + tag.Value[1..^1].Replace('<', ' ').Replace('>', ' ') + ">"
            : tag.Value);

    private static readonly HashSet<string> Void = new(StringComparer.OrdinalIgnoreCase)
    {
        "area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr",
    };

    // The smallest text the main element must hold to be read alone (a <main> holding only a heading is not the page).
    private const int MainFloor = 300;

    internal static string Content(string html, Func<string, int> textLength, out int leftOut)
    {
        string kept = WithoutMarked(Unquoted(Code.Replace(html, " ")), textLength, out leftOut);
        string? main = Main(kept, "main") ?? MainByRole(kept) ?? Main(kept, "article");
        if (main is not null && textLength(main) >= MainFloor)
        {
            leftOut += Math.Max(0, textLength(kept) - textLength(main));
            return main;
        }
        return kept;
    }

    // Rule 1: a marked element goes with its subtree; same-name tags inside it are counted so the right end closes it.
    private static string WithoutMarked(string html, Func<string, int> textLength, out int leftOut)
    {
        leftOut = 0;
        var kept = new StringBuilder(html.Length);
        int copied = 0, depth = 0, skipStart = 0;
        string? skipping = null;
        foreach (Match tag in Tag.Matches(html))
        {
            string name = tag.Groups[2].Value;
            bool closing = tag.Groups[1].Length > 0;
            bool selfClosing = tag.Groups[3].Value.EndsWith('/') || Void.Contains(name);
            if (skipping is null)
            {
                if (closing || selfClosing || !Marked.IsMatch(tag.Groups[3].Value))
                    continue;
                kept.Append(html, copied, tag.Index - copied);
                skipping = name;
                depth = 1;
                skipStart = tag.Index;
                continue;
            }
            if (!string.Equals(name, skipping, StringComparison.OrdinalIgnoreCase) || selfClosing)
                continue;
            depth += closing ? -1 : 1;
            if (depth > 0)
                continue;
            int end = tag.Index + tag.Length;
            leftOut += textLength(html[skipStart..end]);
            kept.Append(' ');
            copied = end;
            skipping = null;
        }
        if (skipping is not null)
            return html; // an element never closed: the markup is not what it seems, nothing is left out
        kept.Append(html, copied, html.Length - copied);
        return kept.ToString();
    }

    // Rule 2: from the first opening of the element to the last closing of it (pages with one main; several articles
    // are read together).
    private static string? Main(string html, string name)
    {
        Match open = new Regex($@"<{name}\b[^>]*>", RegexOptions.IgnoreCase | RegexOptions.CultureInvariant, RegexBudget)
            .Match(html);
        if (!open.Success)
            return null;
        int close = html.LastIndexOf($"</{name}", StringComparison.OrdinalIgnoreCase);
        return close > open.Index ? html[(open.Index + open.Length)..close] : null;
    }

    private static string? MainByRole(string html)
    {
        Match open = new Regex(@"<(div|section)\b[^>]*\brole\s*=\s*[""']main[""'][^>]*>",
            RegexOptions.IgnoreCase | RegexOptions.CultureInvariant, RegexBudget).Match(html);
        if (!open.Success)
            return null;
        string name = open.Groups[1].Value;
        int depth = 1;
        foreach (Match tag in Tag.Matches(html, open.Index + open.Length))
        {
            if (!string.Equals(tag.Groups[2].Value, name, StringComparison.OrdinalIgnoreCase))
                continue;
            depth += tag.Groups[1].Length > 0 ? -1 : 1;
            if (depth == 0)
                return html[(open.Index + open.Length)..tag.Index];
        }
        return null;
    }
}
