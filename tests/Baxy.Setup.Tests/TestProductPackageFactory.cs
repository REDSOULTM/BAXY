using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace Baxy.Setup.Tests;

internal static class TestProductPackageFactory
{
    internal const long SourceDateEpoch = 1_700_000_000;

    internal static byte[] Create(
        string version = "1.0.0",
        string salt = "a",
        Func<byte[], byte[]>? manifestMutation = null,
        Action<List<TestZipEntry>>? entryMutation = null,
        long timestampEpoch = SourceDateEpoch,
        int dataSchema = PackageContract.DataSchema)
    {
        Dictionary<string, byte[]> payload = PackageContract.PayloadPaths.ToDictionary(
            static path => path,
            path => Encoding.UTF8.GetBytes($"{salt}:{path}"),
            StringComparer.Ordinal);
        BuildFileRecord[] records = PackageContract.PayloadPaths.Select(path => new BuildFileRecord
        {
            Path = path,
            Bytes = payload[path].Length,
            Sha256 = Sha256(payload[path]),
        }).ToArray();
        BuildManifest manifest = new()
        {
            Schema = PackageContract.ManifestSchema,
            Product = PackageContract.Product,
            Version = version,
            DataSchema = dataSchema,
            Configuration = PackageContract.Configuration,
            Runtime = PackageContract.Runtime,
            TargetFramework = PackageContract.TargetFramework,
            Authenticity = PackageContract.Authenticity,
            Source = new BuildSource
            {
                Commit = new string('a', 40),
                Dirty = false,
                Provenance = PackageContract.SourceProvenance,
                SourceDateEpoch = SourceDateEpoch,
            },
            Toolchain = new BuildToolchain
            {
                DotnetSdk = "10.0.100",
                PowerShell = "5.1.0",
            },
            Deployment = new BuildDeployment
            {
                App = "self_contained_single_file",
                NativeLibraries = "adjacent_no_self_extraction",
                Core = "native_aot_self_contained",
                Symbols = "excluded_from_user_payload",
            },
            FileCount = records.Length,
            TotalBytes = records.Sum(static record => record.Bytes),
            Files = records,
        };
        byte[] manifestBytes = JsonSerializer.SerializeToUtf8Bytes(manifest, SetupJsonContext.Default.BuildManifest);
        if (manifestMutation is not null)
        {
            manifestBytes = manifestMutation(manifestBytes);
        }

        Dictionary<string, byte[]> checksumContent = new(payload, StringComparer.Ordinal)
        {
            ["build-manifest.json"] = manifestBytes,
        };
        StringBuilder checksums = new();
        foreach (string path in checksumContent.Keys.Order(StringComparer.Ordinal))
        {
            _ = checksums.Append(Sha256(checksumContent[path])).Append("  ").Append(path).Append('\n');
        }

        List<TestZipEntry> entries = checksumContent.Select(static pair => new TestZipEntry(pair.Key, pair.Value)).ToList();
        entries.Add(new TestZipEntry("SHA256SUMS", Encoding.UTF8.GetBytes(checksums.ToString())));
        entryMutation?.Invoke(entries);
        entries.Sort(static (left, right) => StringComparer.Ordinal.Compare(left.Path, right.Path));
        return WriteStoredZip(entries, timestampEpoch);
    }

    internal static byte[] ReplaceAscii(byte[] source, string oldValue, string newValue)
    {
        string text = new UTF8Encoding(false, true).GetString(source);
        string replaced = text.Replace(oldValue, newValue, StringComparison.Ordinal);
        if (string.Equals(text, replaced, StringComparison.Ordinal))
        {
            throw new InvalidOperationException("Test manifest mutation did not match source text.");
        }

        return Encoding.UTF8.GetBytes(replaced);
    }

    internal static byte[] TamperPayloadByte(byte[] package)
    {
        byte[] tampered = (byte[])package.Clone();
        byte[] marker = Encoding.UTF8.GetBytes("a:Baxy.exe");
        int offset = tampered.AsSpan().IndexOf(marker);
        if (offset < 0)
        {
            throw new InvalidOperationException("Test payload marker was not found.");
        }

        tampered[offset] ^= 1;
        return tampered;
    }

    internal static MemoryStream Open(byte[] bytes) => new(bytes, writable: false);

    private static byte[] WriteStoredZip(List<TestZipEntry> sources, long timestampEpoch)
    {
        const uint localSignature = 0x04034b50;
        const uint descriptorSignature = 0x08074b50;
        const uint centralSignature = 0x02014b50;
        const uint eocdSignature = 0x06054b50;
        const ushort version = 20;
        const ushort flags = 0x0808;

        DateTimeOffset timestamp = DateTimeOffset.FromUnixTimeSeconds(timestampEpoch).ToUniversalTime();
        if ((timestamp.Second & 1) != 0)
        {
            timestamp = timestamp.AddSeconds(-1);
        }

        ushort dosTime = checked((ushort)((timestamp.Hour << 11) | (timestamp.Minute << 5) | (timestamp.Second / 2)));
        ushort dosDate = checked((ushort)(((timestamp.Year - 1980) << 9) | (timestamp.Month << 5) | timestamp.Day));
        List<WrittenEntry> written = new(sources.Count);
        using MemoryStream stream = new();
        using BinaryWriter writer = new(stream, Encoding.UTF8, leaveOpen: true);
        foreach (TestZipEntry source in sources)
        {
            byte[] name = Encoding.UTF8.GetBytes(source.Path);
            uint offset = checked((uint)stream.Position);
            uint size = checked((uint)source.Content.Length);
            uint crc = ComputeCrc32(source.Content);
            writer.Write(localSignature);
            writer.Write(version);
            writer.Write(flags);
            writer.Write((ushort)0);
            writer.Write(dosTime);
            writer.Write(dosDate);
            writer.Write(0U);
            writer.Write(0U);
            writer.Write(0U);
            writer.Write(checked((ushort)name.Length));
            writer.Write((ushort)0);
            writer.Write(name);
            writer.Write(source.Content);
            writer.Write(descriptorSignature);
            writer.Write(crc);
            writer.Write(size);
            writer.Write(size);
            written.Add(new WrittenEntry(name, crc, size, offset));
        }

        uint centralOffset = checked((uint)stream.Position);
        foreach (WrittenEntry entry in written)
        {
            writer.Write(centralSignature);
            writer.Write(version);
            writer.Write(version);
            writer.Write(flags);
            writer.Write((ushort)0);
            writer.Write(dosTime);
            writer.Write(dosDate);
            writer.Write(entry.Crc32);
            writer.Write(entry.Size);
            writer.Write(entry.Size);
            writer.Write(checked((ushort)entry.Name.Length));
            writer.Write((ushort)0);
            writer.Write((ushort)0);
            writer.Write((ushort)0);
            writer.Write((ushort)0);
            writer.Write(0U);
            writer.Write(entry.LocalOffset);
            writer.Write(entry.Name);
        }

        uint centralSize = checked((uint)(stream.Position - centralOffset));
        writer.Write(eocdSignature);
        writer.Write((ushort)0);
        writer.Write((ushort)0);
        writer.Write(checked((ushort)written.Count));
        writer.Write(checked((ushort)written.Count));
        writer.Write(centralSize);
        writer.Write(centralOffset);
        writer.Write((ushort)0);
        writer.Flush();
        return stream.ToArray();
    }

    private static string Sha256(byte[] bytes) => Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant();

    private static uint ComputeCrc32(ReadOnlySpan<byte> bytes)
    {
        Crc32Accumulator crc = new();
        crc.Append(bytes);
        return crc.GetCurrent();
    }

    internal sealed record TestZipEntry(string Path, byte[] Content);

    private sealed record WrittenEntry(byte[] Name, uint Crc32, uint Size, uint LocalOffset);
}
