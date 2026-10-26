using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// SensitiveText.Contains decides what memory.save refuses to keep as normal data (and what the transcript masks).
/// A base64-shaped secret with / + = (the shape of a cloud provider's secret access key) used to pass as normal text;
/// paths, URLs, dates and sentences must still pass. Every key here is made up.
/// </summary>
[TestFixture]
public sealed class SensitiveTextTests
{
    [TestCase("Zq8+Rk2/Lm4Tx7Vb9Np3Ws6Yd1Hf5Gj0Kc8Ue2")]
    [TestCase("guardá mi clave secreta del bucket: Zq8+Rk2/Lm4Tx7Vb9Np3Ws6Yd1Hf5Gj0Kc8Ue2")]
    [TestCase("FAKE_SECRET=Zq8+Rk2/Lm4Tx7Vb9Np3Ws6Yd1Hf5Gj0Kc8Ue2")]
    [TestCase("el valor es q7Wm2Kx9/Pz4Rb8Ln3Tc6Vy1Hd5Gf0Js8Ea2Qu4Ok7Mi9=.")]
    [TestCase("fakeTOKENvalue/x9Y8z7W6v5U4t3S2r1Q0p9O8n7M6==")]
    public void ABase64ShapedSecretIsSensitive(string text) =>
        Assert.That(SensitiveText.Contains(text), Is.True);

    [TestCase("/Users/Ana/Documents/Proyecto2024/Notas")]
    [TestCase("D:/Trabajo/Clientes/Informes/Proyecto-Nuevo")]
    [TestCase("https://www.example.com/path/to/Page2024?id=5")]
    [TestCase("https://example.com/Docs2/Guide3/Chapter4/Section5/Part6")]
    [TestCase("/home/user/projects/MyApp2/src/Components/Header3")]
    [TestCase("ConfigurationManager/Extensions2024/Version10+Beta2")]
    [TestCase("2+2=4 y 10/5=2, la reunión es el 25/10/2026 a las 21:35")]
    [TestCase("src/Baxy.App/SensitiveText.cs")]
    [TestCase("Mi cumpleaños es el 3/4 y me gusta el café con leche")]
    [TestCase("Reports/Q3+Q4/Summary2025/FinalVersion2=Approved")]
    public void PathsUrlsAndSentencesAreNotSensitive(string text) =>
        Assert.That(SensitiveText.Contains(text), Is.False);
}
