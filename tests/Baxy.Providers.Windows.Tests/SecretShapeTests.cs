using Baxy.Providers.Windows.Clipboard;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Banco de uso 05-11 (S07): what looks like a key or a password by its form. Every value here is invented. The shape reads
/// no word of the text: it cannot tell a key from a hash, so a hash goes too; that costs a read of a hash, and the opposite
/// mistake costs a key said aloud. A short, plain password («Perro2024») is not caught, and the receipt does not say
/// nothing is secret, only that a part looks like one.
/// </summary>
[TestFixture]
public sealed class SecretShapeTests
{
    private const string Mask = "•••";

    [TestCase("Zx8Qw2Lm9Tb4Rc7Yp1Vn6Kd3Hs5Gf0Aj", Mask, TestName = "a key alone")]
    [TestCase("--token Zx8Qw2Lm9Tb4Rc7Yp1Vn6Kd3Hs5Gf0Aj --x 1", "--token ••• --x 1", TestName = "a key in a command")]
    [TestCase("token=Zx8Qw2Lm9Tb4Rc7Yp1Vn6Kd3Hs5Gf0Aj", "token=•••", TestName = "after an equals sign")]
    [TestCase("\"clave\": \"Zx8Qw2Lm9Tb4Rc7Yp1Vn6Kd3Hs5Gf0Aj\"", "\"clave\": \"•••\"", TestName = "in JSON")]
    [TestCase("prefijo-demo-Zx8Qw2Lm9Tb4Rc7Yp1Vn6Kd3Hs5Gf0Aj", Mask, TestName = "a prefixed key")]
    [TestCase("eyJhbGciOiJIUzI1NiIsInR5cCI6.eyJzdWIiOiIxMjM0NTY3ODkwIiwi.SflKxwRJSMeKKF2QT4fwpMeJf36", Mask, TestName = "a dotted token")]
    [TestCase("9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08", Mask, TestName = "a long hex")]
    [TestCase("https://ejemplo.test/api?sig=Zx8Qw2Lm9Tb4Rc7Yp1Vn6Kd3Hs5Gf0Aj&x=1", "https://ejemplo.test/api?sig=•••&x=1", TestName = "in an address")]
    [TestCase("xK9#mQ2$vL", Mask, TestName = "a password alone")]
    [TestCase("la clave es xK9#mQ2$vLp!", "la clave es •••", TestName = "a password among words")]
    public void WhatLooksLikeAKeyIsMasked(string text, string shown)
    {
        Assert.That(SecretShape.Mask(text, out int parts), Is.EqualTo(shown));
        Assert.That(parts, Is.EqualTo(1));
    }

    [TestCase("Comprar pan, leche y dos kilos de papas para el domingo")]
    [TestCase("https://ejemplo.test/watch?v=dQw4w9WgXcQ")]
    [TestCase("https://ejemplo.test/noticias/como-hacer-pan-casero-en-casa-2024")]
    [TestCase(@"C:\Users\ana\Documents\Informe_Final_2024.pdf")]
    [TestCase("Informe_Final_2024.pdf")]
    [TestCase("ana.perez+compras@ejemplo.test")]
    [TestCase("+56 9 1234 5678")]
    [TestCase("2026-11-05T09:30:00Z")]
    [TestCase("MicrosoftWindowsDesktopInteractionAdapter")]
    [TestCase("WindowsVisibleControlAdapter.cs")]
    [TestCase("3f2504e0-4f89-11d3-9a0c-0305e82c3301")]
    [TestCase("12345678901234567890123456")]
    [TestCase("Hola, ¿cómo estás? Te mando el link mañana a las 10:30.")]
    [TestCase("Total: $1.234.567 (IVA incl.)")]
    [TestCase("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")]
    [TestCase("")]
    public void WhatDoesNotIsLeftAsItIs(string text)
    {
        Assert.That(SecretShape.Mask(text, out int parts), Is.EqualTo(text));
        Assert.That(parts, Is.Zero);
    }

    [Test]
    public void TwoKeysAreTwoParts()
    {
        Assert.That(SecretShape.Mask("Zx8Qw2Lm9Tb4Rc7Yp1Vn6Kd3 y Hs5Gf0AjZx8Qw2Lm9Tb4", out int parts), Is.EqualTo("••• y •••"));
        Assert.That(parts, Is.EqualTo(2));
    }
}
