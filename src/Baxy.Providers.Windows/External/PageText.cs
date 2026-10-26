using System.Text.RegularExpressions;

namespace Baxy.Providers.Windows.External;

// web.fetch: a page's title and its readable text, without what a reader skips (the head, scripts, styles, menus,
// headers, footers, side panels and buttons, and what PageMain leaves out by the page's markup), with how many
// characters of text those skipped sections held. Nothing of the page is chosen or left out by what it says. A form keeps its text (ronda final 10: a WebForms page holds its
// whole body in one).
internal static class PageText
{
    private static readonly TimeSpan RegexBudget = TimeSpan.FromSeconds(2);

    private static readonly Regex Unread = new(
        @"<!--.*?-->|<(head|script|style|noscript|svg|nav|header|footer|aside|template|iframe|button|select)\b.*?</\1\s*>",
        RegexOptions.Singleline | RegexOptions.IgnoreCase | RegexOptions.CultureInvariant, RegexBudget);

    private static readonly Regex Block = new(
        @"</?(?:p|li|h[1-6]|br|div|tr|td|th|dd|dt|blockquote|section|article|main|ul|ol|table|figcaption)\b[^>]*>",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant, RegexBudget);

    private static readonly Regex Tag = new("<[^>]*>", RegexOptions.CultureInvariant, RegexBudget);

    private static readonly Regex Title = new(
        @"<title\b[^>]*>(.*?)</title\s*>", RegexOptions.Singleline | RegexOptions.IgnoreCase | RegexOptions.CultureInvariant,
        RegexBudget);

    // Sections whose text a reader sees on the page but this text leaves out.
    private static readonly HashSet<string> SkippedReadable = new(StringComparer.OrdinalIgnoreCase)
    {
        "nav", "header", "footer", "aside", "button", "select",
    };

    // The page's title, its readable text, one block per line (web.fetch hands it out in pages), and the characters of
    // text in the menus, headers, footers, side panels, buttons and boilerplate it skipped. Goal h-web (2026-10-25):
    // what the page marks as boilerplate by its class or id (cookie banners, breadcrumbs, share bars, edit links,
    // reference marks, navigation boxes) is left out and, when the page names its main content (main, article or
    // role=main) with text enough, only that is read (PageMain). Measured on web searches: the same answers (4 of 4
    // against 3 of 3) and the first answer at 5.5 s against 11.7-15.2 s; behind BAXY_WEB_FOCUS until then.
    internal static (string Title, string Text, int SkippedCharacters) Prose(string html)
    {
        Match title = Title.Match(html);
        html = PageMain.Content(html, static part => Text(part).Length, out int boilerplate);
        int skipped = 0;
        string kept = Unread.Replace(html, match =>
        {
            if (match.Groups[1].Success && SkippedReadable.Contains(match.Groups[1].Value))
                skipped += Text(match.Value).Length;
            return " ";
        });
        string prose = System.Net.WebUtility.HtmlDecode(Tag.Replace(Block.Replace(kept, "\n"), " "));
        string text = string.Join('\n', prose.Split('\n')
            .Select(static line => string.Join(' ', line.Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries)))
            .Where(static line => line.Length > 0));
        return (title.Success ? Text(title.Groups[1].Value) : string.Empty, text, skipped + boilerplate);
    }

    internal static string Text(string html) =>
        string.Join(' ', System.Net.WebUtility.HtmlDecode(Tag.Replace(html, " "))
            .Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries));
}
