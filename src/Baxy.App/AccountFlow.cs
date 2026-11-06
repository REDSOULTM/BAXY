using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Contracts;

namespace Baxy.App;

/// <summary>
/// uso-90 (banco diag-9dea, U06 c1): YouTube showed no dialog BAXY could read and the model, unasked, pressed «Sign in»
/// and then «Next» on Google's sign-in page; nothing was typed, but the person's turn ended on that page. Entering or
/// going on with signing in to an account is an act on the person's own account (identity, «Peligro y confirmación»:
/// what only they decide; OWASP LLM06 Excessive Agency: a human approves a high-impact action), so in normal mode the
/// call waits for their «sí», bound to it (NativeTurnLoop.HeldForTheYes), and its receipt says why (<see cref="Cause"/>
/// and the page it reads). A form compared, never what the person meant: the page is known by the shape of what the
/// last look of its window read and by the call's own address, never by a site's name.
/// <list type="bullet">
/// <item>A field of the page that UI Automation says holds a password (IsPassword; Microsoft Learn,
/// «AutomationElement.IsPasswordProperty»; W3C HTML-AAM maps <c>input type=password</c> to an Edit with IsPassword
/// true), which the reader marks «password» and never reads.</item>
/// <item>An address of sign-in shape (<see cref="IsSignInAddress"/>): the page's own (its Document's value, the URL in
/// Chromium and Gecko browsers), the link a click presses (a Hyperlink's value), or the one a navigation opens.</item>
/// </list>
/// A click that enters (its link) or goes on (a page of that shape), a key or a text into such a page, and a navigation
/// to such an address wait; Bypass holds nothing (the owner's decision of 2026-11-02, in HeldForTheYes).
/// </summary>
internal sealed class AccountFlow
{
    /// <summary>The cause a call held here gives the model.</summary>
    internal const string Cause = "account_sign_in";

    /// <summary>What the model reads besides, after the question it asks.</summary>
    internal const string Next = "signing in to an account, or going on with it, is an act on the person's own account "
        + "that only they decide (signIn says what showed it): it waits for their «sí» even when they asked for it";

    // RFC 6749 §4.1.1 and §4.2.1 (an OAuth 2.0 authorization request carries response_type and client_id, both
    // required; OpenID Connect Core 1.0 §3.1.2.1 is that request), SAML 2.0 Bindings §3.4.4.1 (the HTTP-Redirect binding
    // carries SAMLRequest) and WS-Federation 1.2 §13.2 (wa=wsignin1.0).
    private static readonly string[] AuthorizationRequest = ["response_type", "client_id"];

    // The first label of an identity provider's host and the path segments of its sign-in pages, folded (lower case,
    // without «-», «_» and an extension), as the providers' own documentation gives their endpoints: login.<tenant host>
    // /…/oauth2/v2.0/authorize (Microsoft identity platform), accounts.<host>/o/oauth2/v2/auth and /ServiceLogin,
    // /signin/identifier (Google Identity), /oauth2/default/v1/authorize (Okta), /realms/{realm}/protocol/
    // openid-connect/auth (Keycloak), /u/login and /authorize (Auth0), /login and /oauth2/authorize (Amazon Cognito),
    // /users/sign_in and /users/sign_up (Devise, Rails). Shapes of an address, never a site's name.
    private static readonly HashSet<string> SignInHostLabels = new(StringComparer.Ordinal)
    {
        "login", "logon", "signin", "accounts", "account", "auth", "sso", "idp",
    };

    private static readonly HashSet<string> SignInPathSegments = new(StringComparer.Ordinal)
    {
        "login", "logon", "signin", "signup", "servicelogin", "sso", "oauth", "oauth2", "authorize", "auth", "saml",
        "saml2",
    };

    private readonly Dictionary<long, Page> _pages = [];

    // The window the last look read: a click, key or text that names none acts where it looked.
    private long _looked;

    /// <summary>What a completed call showed of a window: a look's page, or the sign-in page a click's link opened.</summary>
    internal void Saw(string operation, JsonObject arguments, string status, JsonElement? result)
    {
        if (!string.Equals(status, OperationStatuses.Completed, StringComparison.Ordinal))
        {
            return;
        }

        if (operation == "input.visible.controls" && result is { ValueKind: JsonValueKind.Object } view
            && view.TryGetProperty("window", out JsonElement window) && window.ValueKind == JsonValueKind.Object
            && window.TryGetProperty("hwnd", out JsonElement hwnd) && hwnd.TryGetInt64(out long handle) && handle > 0)
        {
            _pages[handle] = Page.Of(view);
            _looked = handle;
            return;
        }

        // The page a sign-in link opened is that window's page until a look reads it again.
        if (operation == "input.visible.click" && WindowOf(arguments) is { } clicked
            && _pages.TryGetValue(clicked, out Page? page) && page.Target(arguments)?.Link is { } link
            && IsSignInAddress(link))
        {
            _pages[clicked] = new Page(link, PasswordField: false, new Dictionary<int, Control>());
        }
    }

    /// <summary>Why this call waits for the person's «sí» here, with what showed it; null: it goes.</summary>
    internal (string Cause, JsonObject Facts)? Holds(string operation, JsonObject arguments)
    {
        switch (operation)
        {
            case "browser.navigate" or "browser.navigate.named":
                return Text(arguments["url"]) is { } url && Uri.TryCreate(url, UriKind.Absolute, out Uri? address)
                    && IsSignInAddress(address)
                        ? (Cause, Facts(address, passwordField: false, enters: true))
                        : null;
            case "input.visible.click":
            {
                if (WindowOf(arguments) is not { } window || !_pages.TryGetValue(window, out Page? page))
                {
                    return null;
                }

                if (page.Target(arguments)?.Link is { } link && IsSignInAddress(link))
                {
                    return (Cause, Facts(link, passwordField: false, enters: true));
                }

                return page.IsSignIn ? (Cause, Facts(page.Address, page.PasswordField, enters: false)) : null;
            }

            case "input.key.press" or "input.text.type":
                return WindowOf(arguments) is { } typed && _pages.TryGetValue(typed, out Page? on) && on.IsSignIn
                    ? (Cause, Facts(on.Address, on.PasswordField, enters: false))
                    : null;
            default:
                return null;
        }
    }

    /// <summary>A new session: no window it read counts.</summary>
    internal void Reset()
    {
        _pages.Clear();
        _looked = 0;
    }

    /// <summary>
    /// Whether an http(s) address is of sign-in shape: an OAuth 2.0 / OpenID Connect authorization request, a SAML
    /// request or a WS-Federation sign-in in its query, a host whose first label is an identity provider's, or a path
    /// segment of a sign-in page (<see cref="SignInHostLabels"/>, <see cref="SignInPathSegments"/>).
    /// </summary>
    internal static bool IsSignInAddress(Uri address)
    {
        if (!address.IsAbsoluteUri || address.Scheme is not ("http" or "https"))
        {
            return false;
        }

        string[] labels = address.Host.ToLowerInvariant().Split('.', StringSplitOptions.RemoveEmptyEntries);
        if (labels.Length > 2 && SignInHostLabels.Contains(labels[0]))
        {
            return true;
        }

        if (address.AbsolutePath.Split('/', StringSplitOptions.RemoveEmptyEntries).Any(static segment =>
                SignInPathSegments.Contains(Folded(Uri.UnescapeDataString(segment)))))
        {
            return true;
        }

        Dictionary<string, string> query = Query(address);
        return AuthorizationRequest.All(query.ContainsKey)
            || query.ContainsKey("samlrequest")
            || (query.TryGetValue("wa", out string? action) && action.Equals("wsignin1.0", StringComparison.OrdinalIgnoreCase));
    }

    private long? WindowOf(JsonObject arguments)
    {
        if (arguments["window"] is JsonValue named && named.TryGetValue(out long window) && window > 0)
        {
            return window;
        }

        return arguments["window"] is null && _looked > 0 ? _looked : null;
    }

    private static JsonObject Facts(Uri? address, bool passwordField, bool enters)
    {
        var facts = new JsonObject { ["enters"] = enters };
        if (address is not null)
        {
            facts["page"] = address.Host + address.AbsolutePath;
        }

        if (passwordField)
        {
            facts["passwordField"] = true;
        }

        return facts;
    }

    // Lower case, without «-» and «_», and without what follows a «.» (login.php, sign_in.aspx).
    private static string Folded(string segment)
    {
        int dot = segment.IndexOf('.', StringComparison.Ordinal);
        string name = dot > 0 ? segment[..dot] : segment;
        return name.ToLowerInvariant().Replace("-", string.Empty, StringComparison.Ordinal)
            .Replace("_", string.Empty, StringComparison.Ordinal);
    }

    private static Dictionary<string, string> Query(Uri address)
    {
        var query = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach (string pair in address.Query.TrimStart('?').Split('&', StringSplitOptions.RemoveEmptyEntries))
        {
            int equals = pair.IndexOf('=', StringComparison.Ordinal);
            string name = Uri.UnescapeDataString(equals < 0 ? pair : pair[..equals]).ToLowerInvariant();
            query.TryAdd(name, equals < 0 ? string.Empty : Uri.UnescapeDataString(pair[(equals + 1)..]));
        }

        return query;
    }

    private static string? Text(JsonNode? node) =>
        node is JsonValue value && value.TryGetValue(out string? text) && !string.IsNullOrWhiteSpace(text) ? text : null;

    private sealed record Control(string Name, Uri? Link);

    private sealed record Page(Uri? Address, bool PasswordField, IReadOnlyDictionary<int, Control> Controls)
    {
        internal bool IsSignIn => PasswordField || (Address is not null && IsSignInAddress(Address));

        internal static Page Of(JsonElement view)
        {
            var controls = new Dictionary<int, Control>();
            var documents = new List<Uri>();
            bool password = false;
            if (view.TryGetProperty("controls", out JsonElement listed) && listed.ValueKind == JsonValueKind.Array)
            {
                foreach (JsonElement control in listed.EnumerateArray())
                {
                    string kind = Property(control, "kind") ?? string.Empty;
                    string name = Property(control, "name") ?? string.Empty;
                    Uri? value = Property(control, "value") is { } written
                        && Uri.TryCreate(written, UriKind.Absolute, out Uri? url) && url.Scheme is "http" or "https"
                            ? url
                            : null;
                    password |= (Property(control, "state") ?? string.Empty)
                        .Split(' ', StringSplitOptions.RemoveEmptyEntries).Contains("password", StringComparer.Ordinal);
                    if (kind == "Document" && value is not null)
                    {
                        documents.Add(value);
                    }

                    if (control.TryGetProperty("i", out JsonElement index) && index.TryGetInt32(out int at))
                    {
                        controls[at] = new Control(name, kind == "Hyperlink" ? value : null);
                    }
                }
            }

            // The page's own address: its document's value; a sign-in document among them (a frame) counts.
            Uri? address = documents.FirstOrDefault(IsSignInAddress) ?? documents.FirstOrDefault();
            return new Page(address, password, controls);
        }

        // The control a click presses: the one at its index when that one bears its label (or it names none), else
        // the first that bears the label and links somewhere, else the first that bears it.
        internal Control? Target(JsonObject arguments)
        {
            string? label = Text(arguments["label"])?.Trim();
            if (arguments["index"] is JsonValue given && given.TryGetValue(out int index)
                && Controls.TryGetValue(index, out Control? at)
                && (label is null || string.Equals(at.Name.Trim(), label, StringComparison.OrdinalIgnoreCase)))
            {
                return at;
            }

            if (label is null)
            {
                return null;
            }

            Control[] named = [.. Controls.Values.Where(control =>
                string.Equals(control.Name.Trim(), label, StringComparison.OrdinalIgnoreCase))];
            return named.FirstOrDefault(static control => control.Link is not null) ?? named.FirstOrDefault();
        }

        private static string? Property(JsonElement control, string name) =>
            control.TryGetProperty(name, out JsonElement value) && value.ValueKind == JsonValueKind.String
                ? value.GetString()
                : null;
    }
}
