using System.Text;
using Baxy.Providers.Windows.Filesystem;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// BAXY Renew e2e (2026-10-15): «añade la línea 'revisar el router'» twice gave «revisar el routerrevisar el router».
/// Appended text is a line of its own, in the file's line-break style; a file already ending in a break gets none.
/// </summary>
[TestFixture]
public sealed class TextFileEncodingTests
{
    [TestCase("uno\ndos", "tres", "\ntres")]
    [TestCase("uno\r\ndos", "tres", "\r\ntres")]
    [TestCase("uno\ndos\n", "tres", "tres")]
    [TestCase("", "tres", "tres")]
    public void Appended_text_is_a_line_of_its_own(string existing, string text, string appended) =>
        Assert.That(
            Encoding.UTF8.GetString(TextFileEncoding.EncodeAppended(Encoding.UTF8.GetBytes(existing), text)),
            Is.EqualTo(appended));
}
