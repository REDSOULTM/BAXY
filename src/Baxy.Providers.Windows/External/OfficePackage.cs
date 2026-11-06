using System.IO.Compression;
using System.Text;
using System.Xml;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// A minimal Office package (ISO/IEC 29500) and its read-back, for what writes one: office.document.create and, encargo
/// 115, file.write of a .docx (<see cref="Filesystem.LocalFilesystemProvider"/>).
/// </summary>
internal static class OfficePackage
{
    // The same text makes the same bytes, so a file.write of what is already there is the state reached (its hash).
    private static readonly DateTimeOffset FixedTime = new(1980, 1, 1, 0, 0, 0, TimeSpan.Zero);

    internal static byte[] Create(string format, string title, string[] paragraphs)
    {
        using var output = new MemoryStream();
        using (var archive = new ZipArchive(output, ZipArchiveMode.Create, leaveOpen: true))
        {
            if (format == "docx")
            {
                WriteEntry(archive, "[Content_Types].xml", """
                    <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
                    <Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>
                    """);
                WriteEntry(archive, "_rels/.rels", """
                    <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
                    <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>
                    """);
                WriteEntry(archive, "word/document.xml",
                    "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
                    + "<w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\"><w:body>"
                    + string.Concat(((string[])[title, .. paragraphs]).Select(paragraph =>
                        "<w:p><w:r><w:t>" + EscapeXml(paragraph) + "</w:t></w:r></w:p>"))
                    + "<w:sectPr/></w:body></w:document>");
            }
            else
            {
                WriteEntry(archive, "[Content_Types].xml", """
                    <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
                    <Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>
                    """);
                WriteEntry(archive, "_rels/.rels", """
                    <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
                    <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>
                    """);
                WriteEntry(archive, "xl/workbook.xml", """
                    <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
                    <workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Hoja 1" sheetId="1" r:id="rId1"/></sheets></workbook>
                    """);
                WriteEntry(archive, "xl/_rels/workbook.xml.rels", """
                    <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
                    <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>
                    """);
                WriteEntry(archive, "xl/worksheets/sheet1.xml",
                    "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
                    + "<worksheet xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\"><sheetData><row r=\"1\"><c r=\"A1\" t=\"inlineStr\"><is><t>"
                    + EscapeXml(title) + "</t></is></c></row></sheetData></worksheet>");
            }
        }
        return output.ToArray();
    }

    internal static bool Verify(string path, string format, string expectedText)
    {
        try
        {
            return string.Equals(ReadText(path, format), expectedText, StringComparison.Ordinal);
        }
        catch (InvalidDataException)
        {
            return false;
        }
    }

    // Every character is one XML holds (a surrogate pair counts as one).
    internal static bool XmlCanHold(string text)
    {
        for (int index = 0; index < text.Length; index++)
        {
            if (XmlConvert.IsXmlChar(text[index]))
            {
                continue;
            }
            if (index + 1 < text.Length && XmlConvert.IsXmlSurrogatePair(text[index + 1], text[index]))
            {
                index++;
                continue;
            }
            return false;
        }
        return true;
    }

    internal static string ReadText(string path, string format)
    {
        using ZipArchive archive = ZipFile.OpenRead(path);
        string entryName = format == "docx" ? "word/document.xml" : "xl/worksheets/sheet1.xml";
        ZipArchiveEntry entry = archive.GetEntry(entryName)
            ?? throw new InvalidDataException("Office document main part is missing.");
        if (entry.Length > 8 * 1024 * 1024)
        {
            throw new InvalidDataException("Office document main part exceeds its bound.");
        }
        var settings = new XmlReaderSettings
        {
            DtdProcessing = DtdProcessing.Prohibit,
            XmlResolver = null,
            MaxCharactersInDocument = 8 * 1024 * 1024,
        };
        using Stream stream = entry.Open();
        using XmlReader reader = XmlReader.Create(stream, settings);
        var text = new StringBuilder();
        while (reader.Read())
        {
            if (reader.NodeType == XmlNodeType.Element && reader.LocalName == "t")
            {
                if (text.Length > 0) text.Append('\n');
                text.Append(reader.ReadElementContentAsString());
            }
        }
        return text.ToString();
    }

    private static void WriteEntry(ZipArchive archive, string name, string content)
    {
        ZipArchiveEntry entry = archive.CreateEntry(name, CompressionLevel.Optimal);
        entry.LastWriteTime = FixedTime;
        using Stream stream = entry.Open();
        using var writer = new StreamWriter(
            stream,
            new UTF8Encoding(encoderShouldEmitUTF8Identifier: false, throwOnInvalidBytes: true));
        writer.Write(content.Trim());
    }

    private static string EscapeXml(string value)
    {
        var output = new StringBuilder(value.Length + 32);
        foreach (char character in value)
        {
            output.Append(character switch
            {
                '&' => "&amp;",
                '<' => "&lt;",
                '>' => "&gt;",
                '\"' => "&quot;",
                '\'' => "&apos;",
                _ => character.ToString(),
            });
        }
        return output.ToString();
    }
}
