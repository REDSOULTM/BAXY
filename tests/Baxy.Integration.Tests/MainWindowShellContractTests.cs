using System.Security.Cryptography;
using System.Text;
using System.Xml.Linq;
using System.Windows;
using Baxy.App;
using Baxy.App.Presentation;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class MainWindowShellContractTests
{
    private const string HistoricalCommit = "4a83f2d082d6b0fec8297e801b96a0da620b059e";
    private const string CurrentFieldTreeSha256 =
        "8EA5476375A1743AC6D17B15FFD8EB9A4752AD1C811C4A225CE6ADA5A8CFE80C";
    private static readonly XNamespace XamlNamespace =
        "http://schemas.microsoft.com/winfx/2006/xaml";

    [Test]
    public void FieldSourceAndRebuiltPayloadMatchTheCurrentSeal()
    {
        string root = RepositoryPath("src", "Baxy.FieldUi");
        string[] files = Directory.GetFiles(root, "*", SearchOption.AllDirectories)
            .Where(path => IsOriginalFieldFile(root, path))
            .ToArray();
        string origin = File.ReadAllText(Path.Combine(root, "ORIGIN.md"));
        string app = File.ReadAllText(Path.Combine(root, "src", "App.tsx"));
        string field = File.ReadAllText(
            Path.Combine(root, "src", "components", "FieldCenter.tsx"));
        string activity = File.ReadAllText(
            Path.Combine(root, "src", "components", "ActivityPanel.tsx"));
        string substrate = File.ReadAllText(
            Path.Combine(root, "src", "components", "SubstratePanel.tsx"));

        Assert.Multiple(() =>
        {
            Assert.That(files, Has.Length.EqualTo(38));
            Assert.That(ComputeTreeSha256(root), Is.EqualTo(CurrentFieldTreeSha256));
            Assert.That(origin, Does.Contain(HistoricalCommit));
            Assert.That(app, Does.Contain("<SubstratePanel"));
            Assert.That(app, Does.Contain("<FieldCenter"));
            Assert.That(app, Does.Contain("<ActivityPanel"));
            Assert.That(field, Does.Contain("ask, instruct, or paste"));
            Assert.That(substrate, Does.Contain("label: 'triggers'"));
            Assert.That(substrate, Does.Contain("label: 'tools'"));
            Assert.That(activity, Does.Contain("label: 'sessions'"));
            Assert.That(activity, Does.Contain("label: 'memory'"));
            Assert.That(activity, Does.Not.Contain("label: 'docs'"));
        });
    }

    [Test]
    public void WindowHostsTheHistoricalFieldWithoutASecondVisualShell()
    {
        XDocument document = XDocument.Load(
            RepositoryPath("src", "Baxy.App", "MainWindow.xaml"),
            LoadOptions.PreserveWhitespace);
        XElement root = document.Root
            ?? throw new AssertionException("MainWindow.xaml has no root element.");
        XElement webView = NamedElement(document, "FieldWebView");
        XElement surfaceLayer = NamedElement(document, "AppSurfaceLayer");
        string[] names = root.DescendantsAndSelf()
            .Select(element => element.Attribute(XamlNamespace + "Name")?.Value)
            .Where(static name => name is not null)
            .Cast<string>()
            .ToArray();

        Assert.Multiple(() =>
        {
            Assert.That(root.Attribute("WindowStyle")?.Value, Is.EqualTo("None"));
            Assert.That(root.Attribute("Width")?.Value, Is.EqualTo("1280"));
            Assert.That(root.Attribute("Height")?.Value, Is.EqualTo("800"));
            Assert.That(root.Attribute("MinWidth")?.Value, Is.EqualTo("1000"));
            Assert.That(root.Attribute("MinHeight")?.Value, Is.EqualTo("600"));
            Assert.That(
                document.Descendants().Count(element => element.Name.LocalName == "WindowChrome"),
                Is.EqualTo(1));
            Assert.That(webView.Name.LocalName, Is.EqualTo("WebView2"));
            Assert.That(
                webView.Attribute("AutomationProperties.AutomationId")?.Value,
                Is.EqualTo("HistoricalFieldUi"));
            Assert.That(surfaceLayer.Name.LocalName, Is.EqualTo("ContentControl"));
            Assert.That(surfaceLayer.Attribute("Visibility")?.Value, Is.EqualTo("Collapsed"));
            Assert.That(names, Does.Not.Contain("SubstrateColumn"));
            Assert.That(names, Does.Not.Contain("ActivityColumn"));
            Assert.That(names, Is.Unique);
        });
    }

    [Test]
    public void InitialWindowBoundsStayInsideTheDesktopWorkArea()
    {
        Rect compact = MainWindow.FitInitialBounds(
            new Size(1280, 800),
            new Size(1000, 600),
            new Rect(0, 0, 1280, 720));
        Rect spacious = MainWindow.FitInitialBounds(
            new Size(1280, 800),
            new Size(1000, 600),
            new Rect(0, 0, 1920, 1080));
        Rect smallerThanMinimum = MainWindow.FitInitialBounds(
            new Size(1280, 800),
            new Size(1000, 600),
            new Rect(100, 50, 900, 550));

        Assert.Multiple(() =>
        {
            Assert.That(compact, Is.EqualTo(new Rect(12, 12, 1256, 696)));
            Assert.That(spacious, Is.EqualTo(new Rect(320, 140, 1280, 800)));
            Assert.That(smallerThanMinimum, Is.EqualTo(new Rect(100, 50, 900, 550)));
        });
    }

    [Test]
    public void NativeSurfaceCatalogExtendsTheShellWithoutChangingTheFrozenField()
    {
        AppSurfaceCatalog catalog = AppSurfaceCatalog.CreateDefault();
        XDocument loadingSurface = XDocument.Load(
            RepositoryPath(
                "src",
                "Baxy.App",
                "Presentation",
                "FieldLoadingSurface.xaml"));
        XElement loadingStatus = NamedElement(loadingSurface, "StatusText");

        Assert.Multiple(() =>
        {
            Assert.That(
                catalog.Ids,
                Does.Contain(AppSurfaceIds.FieldLoading));
            Assert.That(catalog.Ids, Does.Not.Contain(AppSurfaceIds.HistoricalField));
            Assert.That(catalog.Ids, Is.Unique);
            Assert.That(
                loadingSurface
                    .Descendants()
                    .Any(element =>
                        element.Attribute("AutomationProperties.AutomationId")?.Value
                        == "FieldLoadingState"),
                Is.True);
            Assert.That(
                loadingStatus.Attribute("AutomationProperties.LiveSetting")?.Value,
                Is.EqualTo("Polite"));
        });
    }

    [Test]
    public void NativeBridgePreservesTheHistoricalContractLocally()
    {
        string script = File.ReadAllText(
            RepositoryPath("src", "Baxy.App", "Assets", "field-native-bridge.js"));
        string host = File.ReadAllText(
            RepositoryPath("src", "Baxy.App", "FieldUiBridge.cs"));
        string fieldUi = File.ReadAllText(
            RepositoryPath("src", "Baxy.FieldUi", "src", "App.tsx"));
        string window = File.ReadAllText(
            RepositoryPath("src", "Baxy.App", "MainWindow.xaml.cs"));

        Assert.Multiple(() =>
        {
            Assert.That(script, Does.Contain("baxy.field.v1"));
            Assert.That(script, Does.Contain("window.fetch = async"));
            Assert.That(script, Does.Contain("window.WebSocket = NativeWebSocket"));
            Assert.That(script, Does.Contain("window.pywebview"));
            Assert.That(script, Does.Contain("external_network_disabled"));
            Assert.That(script, Does.Contain("applyNativeBranding"));
            Assert.That(script, Does.Contain("BAXY · desktop"));
            Assert.That(script, Does.Contain(".settings-panel{width:960px!important}"));
            Assert.That(script, Does.Contain("Baxy.App · .NET 10"));
            Assert.That(script, Does.Contain("baxy_mind"));
            Assert.That(script, Does.Contain("managedSettingsTabs"));
            Assert.That(script, Does.Contain("'agent'"));
            Assert.That(script, Does.Contain("select[aria-label=\"confirmation policy\"]"));
            Assert.That(script, Does.Contain("label === 'apply'"));
            Assert.That(script, Does.Contain("diagnóstico local"));
            Assert.That(script, Does.Contain("el modo de confirmación es editable"));
            Assert.That(host, Does.Contain("new MissionInput(text, MissionInputSource.Text)"));
            Assert.That(host, Does.Contain("SetWakeVoiceAsync"));
            Assert.That(host, Does.Contain("StartDirectVoiceAsync"));
            Assert.That(host, Does.Contain("direct_tool_execution_disabled"));
            Assert.That(host, Does.Contain("MemoryPanel"));
            Assert.That(host, Does.Contain(".HandleAsync"));
            Assert.That(host, Does.Contain("SurfacesAsync"));
            Assert.That(host, Does.Contain("[\"memory\"] = memoryCount"));
            Assert.That(host, Does.Not.Contain("[\"memory\"] = 0"));
            Assert.That(host, Does.Not.Contain("private_memory_requires_chat"));
            Assert.That(fieldUi, Does.Contain("polledSurfaces ?? stream.surfaces"));
            Assert.That(window, Does.Contain("SetVirtualHostNameToFolderMapping"));
            Assert.That(window, Does.Contain("External network disabled"));
            Assert.That(window, Does.Not.Contain("http://"));
        });
    }

    [Test]
    public void AppCopiesTheFrozenDistAndUsesTheWebView2WpfHost()
    {
        XDocument project = XDocument.Load(
            RepositoryPath("src", "Baxy.App", "Baxy.App.csproj"));
        XElement root = project.Root
            ?? throw new AssertionException("Baxy.App.csproj has no root element.");
        string[] packages = root.Descendants("PackageReference")
            .Select(element => element.Attribute("Include")?.Value ?? string.Empty)
            .ToArray();
        XElement fieldContent = root.Descendants("Content")
            .Single(element =>
                element.Attribute("Include")?.Value == "..\\Baxy.FieldUi\\dist\\**\\*");

        Assert.Multiple(() =>
        {
            Assert.That(packages, Does.Contain("Microsoft.Web.WebView2"));
            Assert.That(
                fieldContent.Element("Link")?.Value,
                Is.EqualTo("FieldUi\\%(RecursiveDir)%(Filename)%(Extension)"));
            Assert.That(
                fieldContent.Element("CopyToOutputDirectory")?.Value,
                Is.EqualTo("PreserveNewest"));
        });
    }

    [TestCase("https://baxy.local/index.html", true)]
    [TestCase("https://baxy.local/index.html?debug", true)]
    [TestCase("https://baxy.local/assets/index.js", false)]
    [TestCase("http://baxy.local/index.html", false)]
    [TestCase("https://user@baxy.local/index.html", false)]
    [TestCase("https://baxy.local.evil.example/index.html", false)]
    [TestCase("https://baxy.local:444/index.html", false)]
    public void NativeBridgeAcceptsOnlyTheHistoricalEntryDocument(
        string source,
        bool expected)
    {
        Assert.That(
            HistoricalFieldOriginPolicy.IsTrustedDocumentSource(source),
            Is.EqualTo(expected));
    }

    [TestCase("https://baxy.local/assets/index.js", false)]
    [TestCase("https://baxy.local:443/assets/index.js", false)]
    [TestCase("http://baxy.local/assets/index.js", true)]
    [TestCase("https://user@baxy.local/assets/index.js", true)]
    [TestCase("https://example.com/index.js", true)]
    [TestCase("data:text/plain,local", false)]
    [TestCase("not a URI", true)]
    public void NativeResourcePolicyBlocksEveryUntrustedNetworkOrigin(
        string source,
        bool expectedBlocked)
    {
        Assert.That(
            HistoricalFieldOriginPolicy.ShouldBlockNetworkResource(source),
            Is.EqualTo(expectedBlocked));
    }

    [TestCase("wss://baxy.local/events", true)]
    [TestCase("wss://baxy.local:443/events", true)]
    [TestCase("ws://baxy.local/events", false)]
    [TestCase("wss://user@baxy.local/events", false)]
    [TestCase("wss://baxy.local/events?scope=all", false)]
    [TestCase("wss://baxy.local/other", false)]
    public void NativeEventSocketUsesTheSameExactAuthority(
        string source,
        bool expected)
    {
        Assert.That(
            HistoricalFieldOriginPolicy.IsTrustedEventSocket(source),
            Is.EqualTo(expected));
    }

    [TestCase("YOU", "YOU")]
    [TestCase("TOOL", "TOOL")]
    [TestCase("BAXY", "BAXY")]
    [TestCase("CONTEXT", "CONTEXT")]
    [TestCase("untrusted", "SYSTEM")]
    public void NativeBridgeNormalizesActivitySources(
        string source,
        string expected)
    {
        Assert.That(FieldUiBridge.NormalizeActivitySource(source), Is.EqualTo(expected));
    }

    [Test]
    public void NativeBridgeReportsTheActiveModelInsteadOfTheHistoricalBrand()
    {
        FieldModelIdentity qwen = FieldUiBridge.ResolveModelIdentity(
            @"D:\BAXYRuntime\assets\models\Qwen3-4B-Q4_K_M.gguf");
        FieldModelIdentity qwen35 = FieldUiBridge.ResolveModelIdentity(
            @"D:\BAXYRuntime\assets\models\Qwen3.5-4B-Q4_K_M.gguf");
        FieldModelIdentity unspecified = FieldUiBridge.ResolveModelIdentity(null);

        Assert.Multiple(() =>
        {
            Assert.That(qwen.Alias, Is.EqualTo("Qwen3-4B-Q4_K_M"));
            Assert.That(qwen.FileName, Is.EqualTo("Qwen3-4B-Q4_K_M.gguf"));
            Assert.That(qwen.Family, Is.EqualTo("qwen 3"));
            Assert.That(qwen.Parameters, Is.EqualTo("4b"));
            Assert.That(qwen.Quantization, Is.EqualTo("Q4_K_M"));
            Assert.That(qwen35.Family, Is.EqualTo("qwen 3.5"));
            Assert.That(qwen35.Parameters, Is.EqualTo("4b"));
            Assert.That(unspecified.Alias, Is.EqualTo("local-model"));
            Assert.That(unspecified.FileName, Is.Empty);
            Assert.That(unspecified.Family, Is.EqualTo("local model"));
            Assert.That(unspecified.Parameters, Is.EqualTo("unknown"));
            Assert.That(unspecified.Quantization, Is.EqualTo("local"));
        });
    }

    [Test]
    public void ProductCapturePreservesNativePixelsAndNeverOverwritesEvidence()
    {
        string script = File.ReadAllText(
            RepositoryPath("scripts", "capture_product.ps1"));

        Assert.Multiple(() =>
        {
            Assert.That(script, Does.Contain("Get-FileHash -LiteralPath $temporary -Algorithm SHA256"));
            Assert.That(script, Does.Contain("$contentAddressedName"));
            Assert.That(script, Does.Contain("native_width = $width"));
            Assert.That(script, Does.Contain("native_height = $height"));
            Assert.That(script, Does.Contain("resampled = $false"));
            Assert.That(script, Does.Not.Contain("HighQualityBicubic"));
            Assert.That(script, Does.Not.Contain("$evidenceWidth"));
            Assert.That(script, Does.Not.Contain("-Destination $OutputPath -Force"));
        });
    }

    private static string ComputeTreeSha256(string root)
    {
        using IncrementalHash hash = IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
        string[] files = Directory.GetFiles(root, "*", SearchOption.AllDirectories)
            .Where(path => IsOriginalFieldFile(root, path))
            .OrderBy(
                path => Path.GetRelativePath(root, path).Replace('\\', '/'),
                StringComparer.Ordinal)
            .ToArray();
        foreach (string file in files)
        {
            string relative = Path.GetRelativePath(root, file).Replace('\\', '/');
            hash.AppendData(Encoding.UTF8.GetBytes(relative));
            hash.AppendData([0]);
            hash.AppendData(File.ReadAllBytes(file));
            hash.AppendData([0]);
        }

        return Convert.ToHexString(hash.GetHashAndReset());
    }

    private static bool IsOriginalFieldFile(string root, string path)
    {
        string relative = Path.GetRelativePath(root, path).Replace('\\', '/');
        return relative != ".gitignore"
            && relative != "ORIGIN.md"
            // The maintainer handbook is not part of the frozen React source.
            && relative != "README.md"
            && relative != "tsconfig.node.json"
            && relative != "vite.config.ts"
            && !relative.StartsWith("node_modules/", StringComparison.Ordinal);
    }

    private static XElement NamedElement(XDocument document, string name) =>
        (document.Root ?? throw new AssertionException("XAML document has no root element."))
        .DescendantsAndSelf()
        .Single(element => element.Attribute(XamlNamespace + "Name")?.Value == name);

    private static string RepositoryPath(params string[] path)
    {
        DirectoryInfo? current = new(TestContext.CurrentContext.TestDirectory);
        while (current is not null && !File.Exists(Path.Combine(current.FullName, "Baxy.slnx")))
        {
            current = current.Parent;
        }

        if (current is null)
        {
            throw new AssertionException("Could not locate the BAXY repository root.");
        }

        return path.Aggregate(current.FullName, Path.Combine);
    }
}
