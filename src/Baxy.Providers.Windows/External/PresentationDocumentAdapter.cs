using System.Globalization;
using System.IO.Compression;
using System.Security;
using System.Text;
using System.Text.Json;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// Auditoría semántica 2026-09-20 (REOPEN1957 H0188 «Haz un powerpoint hablando
/// de amor de 6 diapositivas», D11): la presentación se escribe como un paquete
/// Open XML mínimo (sin Office ni bibliotecas): una diapositiva por entrada,
/// título y viñetas del texto que la mente redactó, guardada en una carpeta
/// conocida; la postlectura abre el paquete y cuenta sus diapositivas.
/// </summary>
internal sealed class PresentationDocumentAdapter : IExternalOperationAdapter
{
    private readonly Func<string, string?> _knownFolder;

    internal PresentationDocumentAdapter()
        : this(WindowsFileToolsAdapter.KnownFolderPath)
    {
    }

    internal PresentationDocumentAdapter(Func<string, string?> knownFolder) =>
        _knownFolder = knownFolder ?? throw new ArgumentNullException(nameof(knownFolder));

    public bool CanHandle(string operation) => operation is "document.presentation.create";

    public ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        string title;
        try
        {
            title = ExternalJson.RequiredString(arguments, "title").Trim();
        }
        catch (InvalidDataException)
        {
            return ValueTask.FromResult(ExternalJson.FailureBeforeEffect(operation, "presentation_argument_invalid"));
        }

        if (!arguments.TryGetProperty("slides", out JsonElement slidesElement) || slidesElement.ValueKind != JsonValueKind.Array)
            return ValueTask.FromResult(ExternalJson.FailureBeforeEffect(operation, "presentation_argument_invalid"));
        var slides = new List<(string Title, string[] Bullets)>();
        foreach (JsonElement item in slidesElement.EnumerateArray())
        {
            if (item.ValueKind != JsonValueKind.String)
                return ValueTask.FromResult(ExternalJson.FailureBeforeEffect(operation, "presentation_argument_invalid"));
            string[] lines = (item.GetString() ?? string.Empty).Replace("\r\n", "\n").Split('\n')
                .Select(line => line.Trim()).Where(line => line.Length > 0).ToArray();
            if (lines.Length == 0)
                continue;
            slides.Add((lines[0], lines.Skip(1).Take(8).ToArray()));
        }

        if (slides.Count == 0 || slides.Count > 12)
            return ValueTask.FromResult(ExternalJson.FailureBeforeEffect(operation, "presentation_slides_invalid"));
        string folder = arguments.TryGetProperty("folder", out JsonElement folderElement) && folderElement.ValueKind == JsonValueKind.String
            ? folderElement.GetString() ?? "documents" : "documents";
        string? root = _knownFolder(folder);
        if (root is null || !Directory.Exists(root))
            return ValueTask.FromResult(ExternalJson.FailureBeforeEffect(operation, "known_folder_missing"));
        string fileName = WindowsFileToolsAdapter.SafeFileName(title, "application/octet-stream");
        fileName = Path.GetFileNameWithoutExtension(fileName) + ".pptx";
        string path = Path.Combine(root, fileName);
        for (int counter = 2; File.Exists(path) && counter < 1000; counter++)
            path = Path.Combine(root, $"{Path.GetFileNameWithoutExtension(fileName)} ({counter}).pptx");

        var effectBoundary = new ExternalEffectBoundary();
        effectBoundary.Cross(cancellationToken);
        try
        {
            WritePackage(path, title, slides);
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            return ValueTask.FromResult(effectBoundary.Failure(operation, "presentation_write_failed"));
        }

        int observedSlides;
        try
        {
            using ZipArchive archive = ZipFile.OpenRead(path);
            observedSlides = archive.Entries.Count(entry =>
                entry.FullName.StartsWith("ppt/slides/slide", StringComparison.Ordinal) && entry.FullName.EndsWith(".xml", StringComparison.Ordinal));
        }
        catch (Exception exception) when (exception is IOException or InvalidDataException)
        {
            return ValueTask.FromResult(effectBoundary.Failure(operation, "presentation_postread_failed", effectObserved: true));
        }

        if (observedSlides != slides.Count)
            return ValueTask.FromResult(effectBoundary.Failure(operation, "presentation_postread_failed", effectObserved: true));
        long bytes = new FileInfo(path).Length;
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("title", title);
            writer.WriteString("folder", folder);
            writer.WriteString("name", Path.GetFileName(path));
            writer.WriteNumber("slideCount", observedSlides);
            writer.WriteStartArray("slideTitles");
            foreach ((string slideTitle, _) in slides)
                writer.WriteStringValue(slideTitle);
            writer.WriteEndArray();
            writer.WriteNumber("bytes", bytes);
            writer.WriteString("authority", "openxml_package_slide_count_postread");
            writer.WriteEndObject();
        });
        return ValueTask.FromResult(ExternalJson.Success(operation, result, effectObserved: true));
    }

    internal static void WritePackage(string path, string title, IReadOnlyList<(string Title, string[] Bullets)> slides)
    {
        using FileStream stream = new(path, FileMode.CreateNew, FileAccess.Write);
        using var zip = new ZipArchive(stream, ZipArchiveMode.Create);
        var contentTypes = new StringBuilder();
        contentTypes.Append("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>")
            .Append("<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">")
            .Append("<Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/>")
            .Append("<Default Extension=\"xml\" ContentType=\"application/xml\"/>")
            .Append("<Override PartName=\"/ppt/presentation.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml\"/>")
            .Append("<Override PartName=\"/ppt/slideMasters/slideMaster1.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml\"/>")
            .Append("<Override PartName=\"/ppt/slideLayouts/slideLayout1.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml\"/>")
            .Append("<Override PartName=\"/ppt/theme/theme1.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.theme+xml\"/>");
        for (int index = 1; index <= slides.Count; index++)
            contentTypes.Append(CultureInfo.InvariantCulture, $"<Override PartName=\"/ppt/slides/slide{index}.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.presentationml.slide+xml\"/>");
        contentTypes.Append("</Types>");
        Add(zip, "[Content_Types].xml", contentTypes.ToString());
        Add(zip, "_rels/.rels",
            "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
            + "<Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"ppt/presentation.xml\"/></Relationships>");

        var presentation = new StringBuilder();
        presentation.Append("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>")
            .Append("<p:presentation xmlns:a=\"http://schemas.openxmlformats.org/drawingml/2006/main\" xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\" xmlns:p=\"http://schemas.openxmlformats.org/presentationml/2006/main\">")
            .Append("<p:sldMasterIdLst><p:sldMasterId id=\"2147483648\" r:id=\"rIdMaster\"/></p:sldMasterIdLst><p:sldIdLst>");
        for (int index = 1; index <= slides.Count; index++)
            presentation.Append(CultureInfo.InvariantCulture, $"<p:sldId id=\"{255 + index}\" r:id=\"rIdSlide{index}\"/>");
        presentation.Append("</p:sldIdLst><p:sldSz cx=\"12192000\" cy=\"6858000\"/><p:notesSz cx=\"6858000\" cy=\"9144000\"/></p:presentation>");
        Add(zip, "ppt/presentation.xml", presentation.ToString());

        var presentationRels = new StringBuilder();
        presentationRels.Append("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">")
            .Append("<Relationship Id=\"rIdMaster\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster\" Target=\"slideMasters/slideMaster1.xml\"/>")
            .Append("<Relationship Id=\"rIdTheme\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme\" Target=\"theme/theme1.xml\"/>");
        for (int index = 1; index <= slides.Count; index++)
            presentationRels.Append(CultureInfo.InvariantCulture, $"<Relationship Id=\"rIdSlide{index}\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide\" Target=\"slides/slide{index}.xml\"/>");
        presentationRels.Append("</Relationships>");
        Add(zip, "ppt/_rels/presentation.xml.rels", presentationRels.ToString());

        Add(zip, "ppt/slideMasters/slideMaster1.xml",
            "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><p:sldMaster xmlns:a=\"http://schemas.openxmlformats.org/drawingml/2006/main\" xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\" xmlns:p=\"http://schemas.openxmlformats.org/presentationml/2006/main\">"
            + "<p:cSld><p:bg><p:bgPr><a:solidFill><a:srgbClr val=\"FFFFFF\"/></a:solidFill><a:effectLst/></p:bgPr></p:bg><p:spTree><p:nvGrpSpPr><p:cNvPr id=\"1\" name=\"\"/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x=\"0\" y=\"0\"/><a:ext cx=\"0\" cy=\"0\"/><a:chOff x=\"0\" y=\"0\"/><a:chExt cx=\"0\" cy=\"0\"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld>"
            + "<p:clrMap bg1=\"lt1\" tx1=\"dk1\" bg2=\"lt2\" tx2=\"dk2\" accent1=\"accent1\" accent2=\"accent2\" accent3=\"accent3\" accent4=\"accent4\" accent5=\"accent5\" accent6=\"accent6\" hlink=\"hlink\" folHlink=\"folHlink\"/>"
            + "<p:sldLayoutIdLst><p:sldLayoutId id=\"2147483649\" r:id=\"rIdLayout\"/></p:sldLayoutIdLst><p:txStyles><p:titleStyle><a:lvl1pPr><a:defRPr sz=\"4000\"/></a:lvl1pPr></p:titleStyle><p:bodyStyle><a:lvl1pPr><a:defRPr sz=\"2400\"/></a:lvl1pPr></p:bodyStyle><p:otherStyle/></p:txStyles></p:sldMaster>");
        Add(zip, "ppt/slideMasters/_rels/slideMaster1.xml.rels",
            "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
            + "<Relationship Id=\"rIdLayout\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout\" Target=\"../slideLayouts/slideLayout1.xml\"/>"
            + "<Relationship Id=\"rIdTheme\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme\" Target=\"../theme/theme1.xml\"/></Relationships>");
        Add(zip, "ppt/slideLayouts/slideLayout1.xml",
            "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><p:sldLayout xmlns:a=\"http://schemas.openxmlformats.org/drawingml/2006/main\" xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\" xmlns:p=\"http://schemas.openxmlformats.org/presentationml/2006/main\" type=\"obj\" preserve=\"1\">"
            + "<p:cSld name=\"Title and Content\"><p:spTree><p:nvGrpSpPr><p:cNvPr id=\"1\" name=\"\"/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x=\"0\" y=\"0\"/><a:ext cx=\"0\" cy=\"0\"/><a:chOff x=\"0\" y=\"0\"/><a:chExt cx=\"0\" cy=\"0\"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>");
        Add(zip, "ppt/slideLayouts/_rels/slideLayout1.xml.rels",
            "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
            + "<Relationship Id=\"rIdMaster\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster\" Target=\"../slideMasters/slideMaster1.xml\"/></Relationships>");
        Add(zip, "ppt/theme/theme1.xml",
            "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><a:theme xmlns:a=\"http://schemas.openxmlformats.org/drawingml/2006/main\" name=\"BAXY\"><a:themeElements>"
            + "<a:clrScheme name=\"BAXY\"><a:dk1><a:srgbClr val=\"1F1F1F\"/></a:dk1><a:lt1><a:srgbClr val=\"FFFFFF\"/></a:lt1><a:dk2><a:srgbClr val=\"44546A\"/></a:dk2><a:lt2><a:srgbClr val=\"E7E6E6\"/></a:lt2><a:accent1><a:srgbClr val=\"C0392B\"/></a:accent1><a:accent2><a:srgbClr val=\"E67E22\"/></a:accent2><a:accent3><a:srgbClr val=\"27AE60\"/></a:accent3><a:accent4><a:srgbClr val=\"2980B9\"/></a:accent4><a:accent5><a:srgbClr val=\"8E44AD\"/></a:accent5><a:accent6><a:srgbClr val=\"16A085\"/></a:accent6><a:hlink><a:srgbClr val=\"0563C1\"/></a:hlink><a:folHlink><a:srgbClr val=\"954F72\"/></a:folHlink></a:clrScheme>"
            + "<a:fontScheme name=\"BAXY\"><a:majorFont><a:latin typeface=\"Calibri Light\"/><a:ea typeface=\"\"/><a:cs typeface=\"\"/></a:majorFont><a:minorFont><a:latin typeface=\"Calibri\"/><a:ea typeface=\"\"/><a:cs typeface=\"\"/></a:minorFont></a:fontScheme>"
            + "<a:fmtScheme name=\"BAXY\"><a:fillStyleLst><a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill><a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill><a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill></a:fillStyleLst><a:lnStyleLst><a:ln w=\"6350\"><a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill></a:ln><a:ln w=\"12700\"><a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill></a:ln><a:ln w=\"19050\"><a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill></a:ln></a:lnStyleLst><a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle><a:effectStyle><a:effectLst/></a:effectStyle><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst><a:bgFillStyleLst><a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill><a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill><a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill></a:bgFillStyleLst></a:fmtScheme>"
            + "</a:themeElements></a:theme>");

        for (int index = 1; index <= slides.Count; index++)
        {
            (string slideTitle, string[] bullets) = slides[index - 1];
            var slide = new StringBuilder();
            slide.Append("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><p:sld xmlns:a=\"http://schemas.openxmlformats.org/drawingml/2006/main\" xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\" xmlns:p=\"http://schemas.openxmlformats.org/presentationml/2006/main\"><p:cSld><p:spTree>")
                .Append("<p:nvGrpSpPr><p:cNvPr id=\"1\" name=\"\"/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x=\"0\" y=\"0\"/><a:ext cx=\"0\" cy=\"0\"/><a:chOff x=\"0\" y=\"0\"/><a:chExt cx=\"0\" cy=\"0\"/></a:xfrm></p:grpSpPr>")
                .Append("<p:sp><p:nvSpPr><p:cNvPr id=\"2\" name=\"Título\"/><p:cNvSpPr><a:spLocks noGrp=\"1\"/></p:cNvSpPr><p:nvPr><p:ph type=\"title\"/></p:nvPr></p:nvSpPr><p:spPr><a:xfrm><a:off x=\"838200\" y=\"365125\"/><a:ext cx=\"10515600\" cy=\"1325563\"/></a:xfrm><a:prstGeom prst=\"rect\"><a:avLst/></a:prstGeom></p:spPr><p:txBody><a:bodyPr anchor=\"b\"/><a:lstStyle/><a:p><a:r><a:rPr lang=\"es-ES\" sz=\"4000\" b=\"1\"/><a:t>")
                .Append(SecurityElement.Escape(slideTitle))
                .Append("</a:t></a:r></a:p></p:txBody></p:sp>")
                .Append("<p:sp><p:nvSpPr><p:cNvPr id=\"3\" name=\"Contenido\"/><p:cNvSpPr><a:spLocks noGrp=\"1\"/></p:cNvSpPr><p:nvPr><p:ph idx=\"1\"/></p:nvPr></p:nvSpPr><p:spPr><a:xfrm><a:off x=\"838200\" y=\"1825625\"/><a:ext cx=\"10515600\" cy=\"4351338\"/></a:xfrm><a:prstGeom prst=\"rect\"><a:avLst/></a:prstGeom></p:spPr><p:txBody><a:bodyPr/><a:lstStyle/>");
            if (bullets.Length == 0)
                slide.Append("<a:p><a:endParaRPr lang=\"es-ES\"/></a:p>");
            foreach (string bullet in bullets)
            {
                slide.Append("<a:p><a:pPr marL=\"342900\" indent=\"-342900\"><a:buFont typeface=\"Arial\"/><a:buChar char=\"•\"/></a:pPr><a:r><a:rPr lang=\"es-ES\" sz=\"2400\"/><a:t>")
                    .Append(SecurityElement.Escape(bullet))
                    .Append("</a:t></a:r></a:p>");
            }

            slide.Append("</p:txBody></p:sp></p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>");
            Add(zip, $"ppt/slides/slide{index}.xml", slide.ToString());
            Add(zip, $"ppt/slides/_rels/slide{index}.xml.rels",
                "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
                + "<Relationship Id=\"rIdLayout\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout\" Target=\"../slideLayouts/slideLayout1.xml\"/></Relationships>");
        }

        _ = title;
    }

    private static void Add(ZipArchive zip, string name, string xml)
    {
        ZipArchiveEntry entry = zip.CreateEntry(name, CompressionLevel.Optimal);
        using Stream stream = entry.Open();
        byte[] bytes = new UTF8Encoding(false).GetBytes(xml);
        stream.Write(bytes, 0, bytes.Length);
    }
}
