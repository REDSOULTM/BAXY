namespace Baxy.Providers.Windows.External;

// WEB3 (2026-11-07): the one place where BAXY says who it is to the public services that ask it to (MET Norway,
// Wikimedia, Photon, Frankfurter). MET Norway's terms want «the application/domain name, optionally version number»
// and «a company email address or a link to the company website where we can find contact information»
// (https://api.met.no/doc/TermsOfService, revisión 2026-11-05); its FAQ accepts a «link to github repo with possibility
// to open issues» and prefers a non-personal email (https://api.met.no/doc/FAQ, read 2026-11-07), and wants the version
// «so that we can block misbehaving older versions after a fix has been released»: hence major.minor.patch.
// For the owner: a product contact email (never a person's) may replace Contact here, and only here.
// LEG-09 (2026-11-09): Contact is the repository's own address, the one the releases, the privacy text and «Installed
// apps» give (tests/test_contacto_declarado.py holds them together). It said the name the repository had before it was
// renamed, which GitHub only redirects while nobody creates another repository with that name
// (https://docs.github.com/en/repositories/creating-and-managing-repositories/renaming-a-repository, read 2026-11-09).
internal static class ProductIdentity
{
    internal const string Contact = "https://github.com/REDSOULTM/BAXY";

    // Formato recomendado por Wikimedia y aceptado por MET Norway: «<cliente>/<versión> (<contacto>)».
    internal static string UserAgent { get; } = "BAXY/"
        + (typeof(ProductIdentity).Assembly.GetName().Version is { } version ? version.ToString(3) : "1.0.0")
        + " (" + Contact + ")";
}
