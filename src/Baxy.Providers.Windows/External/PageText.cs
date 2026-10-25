using System.Text.RegularExpressions;

namespace Baxy.Providers.Windows.External;

// web.fetch: a page's title and its readable text, without what a reader skips (the head, scripts, styles, menus,
// headers, footers, side panels and buttons), with how many characters of text those skipped sections held. Nothing of
// the page is chosen or left out by what it says. A form keeps its text (ronda final 10: a WebForms page holds its
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

    // The page's title, its whole readable text, one block per line (web.fetch hands it out in pages), and the
    // characters of text in the menus, headers, footers, side panels and buttons it skipped.
    internal static (string Title, string Text, int SkippedCharacters) Prose(string html) =>
        Prose(html, MainOnly());

    // Goal h-web (2026-10-25): BAXY_WEB_FOCUS=1 also leaves out what the page marks as boilerplate by its class or id
    // (cookie banners, breadcrumbs, share bars, edit links, reference marks, navigation boxes) and, when the page names
    // its main content (main, article or role=main) with text enough, reads only that. Unset: the page as before.
    internal static bool MainOnly() =>
        Environment.GetEnvironmentVariable("BAXY_WEB_FOCUS") is { } focus && focus.Trim() == "1";

    internal static (string Title, string Text, int SkippedCharacters) Prose(string html, bool mainOnly)
    {
        Match title = Title.Match(html);
        int boilerplate = 0;
        if (mainOnly)
            html = PageMain.Content(html, static part => Text(part).Length, out boilerplate);
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
