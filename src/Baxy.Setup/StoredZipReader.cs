using System.Text;

namespace Baxy.Setup;

internal sealed record StoredZipEntry(
    string Path,
    long Length,
    uint Crc32,
    long DataOffset,
    ushort DosTime,
    ushort DosDate);

internal static class StoredZipReader
{
    private const uint EndOfCentralDirectorySignature = 0x06054b50;
    private const uint CentralDirectoryHeaderSignature = 0x02014b50;
    private const uint LocalFileHeaderSignature = 0x04034b50;
    private const uint DataDescriptorSignature = 0x08074b50;
    private const ushort ExactVersion = 20;
    private const ushort ExactFlags = 0x0808;
    private const ushort StoredMethod = 0;
    private static readonly UTF8Encoding StrictUtf8 = new(false, true);

    internal static IReadOnlyList<StoredZipEntry> Read(Stream stream)
    {
        if (!stream.CanRead || !stream.CanSeek)
        {
            throw new ProductPackageException("The package stream must be readable and seekable.");
        }

        if (stream.Length is < 22 or > PackageContract.MaximumPackageBytes)
        {
            throw new ProductPackageException("The package length is outside the reviewed ZIP bounds.");
        }

        stream.Position = stream.Length - 22;
        using BinaryReader reader = new(stream, Encoding.UTF8, leaveOpen: true);
        if (reader.ReadUInt32() != EndOfCentralDirectorySignature)
        {
            throw new ProductPackageException("The ZIP end-of-central-directory record is not the final 22 bytes.");
        }

        ushort diskNumber = reader.ReadUInt16();
        ushort centralDisk = reader.ReadUInt16();
        ushort entriesOnDisk = reader.ReadUInt16();
        ushort totalEntries = reader.ReadUInt16();
        uint centralSize = reader.ReadUInt32();
        uint centralOffset = reader.ReadUInt32();
        ushort commentLength = reader.ReadUInt16();
        if (diskNumber != 0 || centralDisk != 0 || entriesOnDisk != totalEntries ||
            entriesOnDisk == ushort.MaxValue || centralSize == uint.MaxValue || centralOffset == uint.MaxValue)
        {
            throw new ProductPackageException("Multi-disk and ZIP64 packages are outside the BAXY contract.");
        }

        if (totalEntries != PackageContract.ZipPaths.Length || commentLength != 0 || stream.Position != stream.Length)
        {
            throw new ProductPackageException("The ZIP entry count, comment, or trailing-byte layout is non-canonical.");
        }

        long absoluteEocd = stream.Length - 22;
        long centralEnd = checked((long)centralOffset + centralSize);
        if (centralEnd != absoluteEocd)
        {
            throw new ProductPackageException("The ZIP central-directory bounds are non-canonical.");
        }

        List<StoredZipEntry> entries = new(totalEntries);
        HashSet<string> windowsNames = new(StringComparer.OrdinalIgnoreCase);
        stream.Position = centralOffset;
        long expectedLocalOffset = 0;
        string? previousName = null;
        for (int index = 0; index < totalEntries; index++)
        {
            if (reader.ReadUInt32() != CentralDirectoryHeaderSignature)
            {
                throw new ProductPackageException("A ZIP central-directory signature is invalid.");
            }

            ushort versionMadeBy = reader.ReadUInt16();
            ushort versionNeeded = reader.ReadUInt16();
            ushort flags = reader.ReadUInt16();
            ushort method = reader.ReadUInt16();
            ushort dosTime = reader.ReadUInt16();
            ushort dosDate = reader.ReadUInt16();
            uint crc32 = reader.ReadUInt32();
            uint compressedSize = reader.ReadUInt32();
            uint uncompressedSize = reader.ReadUInt32();
            ushort nameLength = reader.ReadUInt16();
            ushort extraLength = reader.ReadUInt16();
            ushort entryCommentLength = reader.ReadUInt16();
            ushort diskStart = reader.ReadUInt16();
            ushort internalAttributes = reader.ReadUInt16();
            uint externalAttributes = reader.ReadUInt32();
            uint localOffset = reader.ReadUInt32();

            if (versionMadeBy != ExactVersion || versionNeeded != ExactVersion || flags != ExactFlags ||
                method != StoredMethod || compressedSize != uncompressedSize)
            {
                throw new ProductPackageException("A ZIP entry version, flag, method, or stored size is non-canonical.");
            }

            if (compressedSize == uint.MaxValue || compressedSize > PackageContract.MaximumPayloadFileBytes ||
                nameLength is 0 or > PackageContract.MaximumRelativePathLength || extraLength != 0 ||
                entryCommentLength != 0 || diskStart != 0 || internalAttributes != 0 || externalAttributes != 0)
            {
                throw new ProductPackageException("A ZIP entry size, name, attribute, extra field, or comment is outside the contract.");
            }

            byte[] centralName = ReadExactBytes(reader, nameLength, "ZIP central entry name");
            string path;
            try
            {
                path = StrictUtf8.GetString(centralName);
            }
            catch (DecoderFallbackException exception)
            {
                throw new ProductPackageException("A ZIP entry name is not strict UTF-8.", exception);
            }

            PathSafety.ValidateRelativePath(path);
            if (!windowsNames.Add(path))
            {
                throw new ProductPackageException($"Duplicate ZIP path under Windows comparison rules: {path}");
            }

            if (previousName is not null && StringComparer.Ordinal.Compare(previousName, path) >= 0)
            {
                throw new ProductPackageException("ZIP entries are not in strict ordinal order.");
            }

            previousName = path;
            long nextCentralEntry = stream.Position;
            if (nextCentralEntry > absoluteEocd || localOffset != expectedLocalOffset)
            {
                throw new ProductPackageException("ZIP local entries are not contiguous and ordered before the central directory.");
            }

            stream.Position = localOffset;
            if (reader.ReadUInt32() != LocalFileHeaderSignature)
            {
                throw new ProductPackageException("A ZIP local-file signature is invalid.");
            }

            ushort localVersion = reader.ReadUInt16();
            ushort localFlags = reader.ReadUInt16();
            ushort localMethod = reader.ReadUInt16();
            ushort localTime = reader.ReadUInt16();
            ushort localDate = reader.ReadUInt16();
            uint localCrcPlaceholder = reader.ReadUInt32();
            uint localCompressedPlaceholder = reader.ReadUInt32();
            uint localUncompressedPlaceholder = reader.ReadUInt32();
            ushort localNameLength = reader.ReadUInt16();
            ushort localExtraLength = reader.ReadUInt16();
            if (localVersion != versionNeeded || localFlags != flags || localMethod != method ||
                localTime != dosTime || localDate != dosDate || localCrcPlaceholder != 0 ||
                localCompressedPlaceholder != 0 || localUncompressedPlaceholder != 0 ||
                localNameLength != nameLength || localExtraLength != 0)
            {
                throw new ProductPackageException("ZIP local and central metadata is inconsistent or non-canonical.");
            }

            byte[] localName = ReadExactBytes(reader, localNameLength, "ZIP local entry name");
            if (!localName.AsSpan().SequenceEqual(centralName))
            {
                throw new ProductPackageException("ZIP local and central entry names differ.");
            }

            long dataOffset = stream.Position;
            long descriptorOffset = checked(dataOffset + compressedSize);
            if (checked(descriptorOffset + 16) > centralOffset)
            {
                throw new ProductPackageException("ZIP entry data or descriptor crosses the central-directory boundary.");
            }

            stream.Position = descriptorOffset;
            if (reader.ReadUInt32() != DataDescriptorSignature || reader.ReadUInt32() != crc32 ||
                reader.ReadUInt32() != compressedSize || reader.ReadUInt32() != uncompressedSize)
            {
                throw new ProductPackageException("A ZIP data descriptor is missing or inconsistent.");
            }

            expectedLocalOffset = stream.Position;
            entries.Add(new StoredZipEntry(path, uncompressedSize, crc32, dataOffset, dosTime, dosDate));
            stream.Position = nextCentralEntry;
        }

        if (expectedLocalOffset != centralOffset || stream.Position != centralEnd)
        {
            throw new ProductPackageException("The ZIP local or central region contains non-canonical bytes.");
        }

        return entries;
    }

    private static byte[] ReadExactBytes(BinaryReader reader, int count, string context)
    {
        byte[] bytes = reader.ReadBytes(count);
        if (bytes.Length != count)
        {
            throw new ProductPackageException($"The {context} is truncated.");
        }

        return bytes;
    }
}

internal struct Crc32Accumulator
{
    private static readonly uint[] Table = CreateTable();
    private uint _value;
    private bool _started;

    internal void Append(ReadOnlySpan<byte> bytes)
    {
        if (!_started)
        {
            _value = 0xffffffffU;
            _started = true;
        }

        foreach (byte value in bytes)
        {
            _value = Table[(_value ^ value) & 0xff] ^ (_value >> 8);
        }
    }

    internal readonly uint GetCurrent() => _started ? ~_value : 0;

    private static uint[] CreateTable()
    {
        uint[] table = new uint[256];
        for (uint index = 0; index < table.Length; index++)
        {
            uint value = index;
            for (int bit = 0; bit < 8; bit++)
            {
                value = (value & 1) != 0 ? 0xedb88320U ^ (value >> 1) : value >> 1;
            }

            table[index] = value;
        }

        return table;
    }
}
