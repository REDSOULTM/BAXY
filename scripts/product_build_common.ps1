Set-StrictMode -Version Latest

if (-not (Get-Command Assert-StrictDescendantPath -ErrorAction SilentlyContinue)) {
    . (Join-Path $PSScriptRoot 'path_safety.ps1')
}
. (Join-Path $PSScriptRoot 'build_layout.ps1')

$script:BaxyBuildLayout = Get-BaxyBuildLayout `
    -RepositoryRoot (Join-Path $PSScriptRoot '..')
$script:BaxyBuildManifestSchema = 'baxy-product-build-v4'
$script:BaxyProductName = 'BAXY'
$script:BaxyDataSchema = 1
$script:BaxyRuntimeIdentifier = $script:BaxyBuildLayout.RuntimeIdentifier
$script:BaxyTargetFramework = $script:BaxyBuildLayout.WindowsTargetFramework
$script:BaxySemVerPattern = '^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-(0|[1-9][0-9]*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*)(\.(0|[1-9][0-9]*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*))*)?(\+[0-9A-Za-z-]+(\.[0-9A-Za-z-]+)*)?\z'
$script:BaxyUtf8NoBom = New-Object Text.UTF8Encoding($false, $true)
$script:BaxyProductPayloadPaths = @(
    'Baxy.exe',
    'D3DCompiler_47_cor3.dll',
    'DesktopClickVisible.ps1',
    'DesktopKeyPress.ps1',
    'DesktopSelectAll.ps1',
    'FieldUi/assets/index-CjozYCnU.css',
    'FieldUi/assets/index-D3QuhrLm.js',
    'FieldUi/index.html',
    'FieldUiHost/field-native-bridge.js',
    'KnownFileOpen.ps1',
    'KnownFolderOpen.ps1',
    'Microsoft.Web.WebView2.Core.xml',
    'Microsoft.Web.WebView2.WinForms.xml',
    'Microsoft.Web.WebView2.Wpf.xml',
    'PenImc_cor3.dll',
    'PresentationNative_cor3.dll',
    'SpotifyDesktopAutomation.ps1',
    'SpotifyMediaControl.ps1',
    'WebView2Loader.dll',
    'WindowsScheduledNotification.ps1',
    'core/DesktopClickVisible.ps1',
    'core/DesktopKeyPress.ps1',
    'core/DesktopSelectAll.ps1',
    'core/KnownFileOpen.ps1',
    'core/KnownFolderOpen.ps1',
    'core/SpotifyDesktopAutomation.ps1',
    'core/SpotifyMediaControl.ps1',
    'core/WindowsScheduledNotification.ps1',
    'core/baxy-core.exe',
    "runtimes/$($script:BaxyRuntimeIdentifier)/native/WebView2Loader.dll",
    'tools/mpv/mpv.exe',
    'tools/mpv/vulkan-1.dll',
    'tools/yt-dlp/yt-dlp.exe',
    'vcruntime140_cor3.dll',
    'wpfgfx_cor3.dll'
)

if ($null -eq ('BaxyNativeStreamInspector' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Runtime.InteropServices;

public static class BaxyNativeStreamInspector
{
    private const int FindStreamInfoStandard = 0;
    private const int ErrorNoMoreFiles = 18;
    private const int ErrorHandleEof = 38;
    private static readonly IntPtr InvalidHandleValue = new IntPtr(-1);

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct Win32FindStreamData
    {
        public long StreamSize;

        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 296)]
        public string StreamName;
    }

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern IntPtr FindFirstStreamW(
        string fileName,
        int infoLevel,
        out Win32FindStreamData findStreamData,
        int flags);

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool FindNextStreamW(
        IntPtr findStream,
        out Win32FindStreamData findStreamData);

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool FindClose(IntPtr findFile);

    public static string[] GetStreams(string path)
    {
        Win32FindStreamData data;
        IntPtr handle = FindFirstStreamW(path, FindStreamInfoStandard, out data, 0);
        if (handle == InvalidHandleValue)
        {
            int error = Marshal.GetLastWin32Error();
            if (error == ErrorNoMoreFiles || error == ErrorHandleEof)
            {
                return new string[0];
            }

            throw new Win32Exception(error, "Unable to enumerate NTFS streams for " + path);
        }

        var streams = new List<string>();
        try
        {
            streams.Add(data.StreamName);
            while (FindNextStreamW(handle, out data))
            {
                streams.Add(data.StreamName);
            }

            int error = Marshal.GetLastWin32Error();
            if (error != ErrorNoMoreFiles && error != ErrorHandleEof)
            {
                throw new Win32Exception(error, "Unable to continue enumerating NTFS streams for " + path);
            }
        }
        finally
        {
            FindClose(handle);
        }

        return streams.ToArray();
    }
}
'@
}

if ($null -eq ('BaxyZipStorageInspector' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.IO;
using System.Text;

public static class BaxyZipStorageInspector
{
    private const uint EndOfCentralDirectorySignature = 0x06054b50;
    private const uint CentralDirectoryHeaderSignature = 0x02014b50;
    private const uint LocalFileHeaderSignature = 0x04034b50;
    private const uint DataDescriptorSignature = 0x08074b50;
    private const ushort ExactVersion = 20;
    private const ushort ExactFlags = 0x0808;
    private const ushort StoredMethod = 0;

    public static void AssertStored(string path)
    {
        using (var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read))
        using (var reader = new BinaryReader(stream))
        {
            if (stream.Length < 22)
            {
                throw new InvalidDataException("ZIP is too short for the exact product layout.");
            }

            long absoluteEocd = stream.Length - 22;
            stream.Position = absoluteEocd;
            if (reader.ReadUInt32() != EndOfCentralDirectorySignature)
            {
                throw new InvalidDataException("ZIP end-of-central-directory must be the final 22-byte record.");
            }
            ushort diskNumber = reader.ReadUInt16();
            ushort centralDisk = reader.ReadUInt16();
            ushort entriesOnDisk = reader.ReadUInt16();
            ushort totalEntries = reader.ReadUInt16();
            uint centralSize = reader.ReadUInt32();
            uint centralOffset = reader.ReadUInt32();
            ushort eocdCommentLength = reader.ReadUInt16();
            if (diskNumber != 0 || centralDisk != 0 || entriesOnDisk != totalEntries ||
                entriesOnDisk == ushort.MaxValue || centralSize == uint.MaxValue || centralOffset == uint.MaxValue)
            {
                throw new InvalidDataException("Multi-disk and ZIP64 packages are outside the product ZIP contract.");
            }
            if (eocdCommentLength != 0 || stream.Position != stream.Length)
            {
                throw new InvalidDataException("ZIP comments and trailing bytes are outside the product layout.");
            }
            if ((long)centralOffset + centralSize != absoluteEocd)
            {
                throw new InvalidDataException("ZIP central-directory bounds are non-canonical.");
            }

            stream.Position = centralOffset;
            long expectedLocalOffset = 0;
            for (int entryIndex = 0; entryIndex < totalEntries; entryIndex++)
            {
                if (reader.ReadUInt32() != CentralDirectoryHeaderSignature)
                {
                    throw new InvalidDataException("ZIP central-directory entry signature is invalid.");
                }

                ushort centralVersionMadeBy = reader.ReadUInt16();
                ushort centralVersionNeeded = reader.ReadUInt16();
                ushort centralFlags = reader.ReadUInt16();
                ushort centralMethod = reader.ReadUInt16();
                ushort centralTime = reader.ReadUInt16();
                ushort centralDate = reader.ReadUInt16();
                uint centralCrc = reader.ReadUInt32();
                uint centralCompressedSize = reader.ReadUInt32();
                uint centralUncompressedSize = reader.ReadUInt32();
                ushort nameLength = reader.ReadUInt16();
                ushort extraLength = reader.ReadUInt16();
                ushort commentLength = reader.ReadUInt16();
                ushort diskStart = reader.ReadUInt16();
                ushort internalAttributes = reader.ReadUInt16();
                uint externalAttributes = reader.ReadUInt32();
                uint localOffset = reader.ReadUInt32();
                if (centralVersionMadeBy != ExactVersion || centralVersionNeeded != ExactVersion ||
                    centralFlags != ExactFlags || centralMethod != StoredMethod)
                {
                    throw new InvalidDataException("ZIP central entry version, flags, or method is non-canonical.");
                }
                if (centralCompressedSize != centralUncompressedSize ||
                    centralCompressedSize == uint.MaxValue || nameLength == 0 ||
                    extraLength != 0 || commentLength != 0 || diskStart != 0 ||
                    internalAttributes != 0 || externalAttributes != 0)
                {
                    throw new InvalidDataException("ZIP central entry sizes, attributes, extra data, or comments are non-canonical.");
                }
                byte[] centralName = reader.ReadBytes(nameLength);
                if (centralName.Length != nameLength)
                {
                    throw new EndOfStreamException("ZIP central entry name is truncated.");
                }
                new UTF8Encoding(false, true).GetString(centralName);
                long nextCentralEntry = stream.Position;
                if (nextCentralEntry > absoluteEocd || localOffset != expectedLocalOffset)
                {
                    throw new InvalidDataException("ZIP local entries are not contiguous and ordered before the central directory.");
                }

                stream.Position = localOffset;
                if (reader.ReadUInt32() != LocalFileHeaderSignature)
                {
                    throw new InvalidDataException("ZIP local-file entry signature is invalid.");
                }
                ushort localVersionNeeded = reader.ReadUInt16();
                ushort localFlags = reader.ReadUInt16();
                ushort localMethod = reader.ReadUInt16();
                ushort localTime = reader.ReadUInt16();
                ushort localDate = reader.ReadUInt16();
                uint localCrcPlaceholder = reader.ReadUInt32();
                uint localCompressedPlaceholder = reader.ReadUInt32();
                uint localUncompressedPlaceholder = reader.ReadUInt32();
                ushort localNameLength = reader.ReadUInt16();
                ushort localExtraLength = reader.ReadUInt16();
                if (localVersionNeeded != centralVersionNeeded || localFlags != centralFlags ||
                    localMethod != centralMethod || localTime != centralTime || localDate != centralDate ||
                    localCrcPlaceholder != 0 || localCompressedPlaceholder != 0 || localUncompressedPlaceholder != 0 ||
                    localNameLength != nameLength || localExtraLength != 0)
                {
                    throw new InvalidDataException("ZIP local and central entry metadata is inconsistent or non-canonical.");
                }
                byte[] localName = reader.ReadBytes(localNameLength);
                if (!BytesEqual(localName, centralName))
                {
                    throw new InvalidDataException("ZIP local and central entry names differ.");
                }

                long descriptorOffset = stream.Position + centralCompressedSize;
                if (descriptorOffset + 16 > centralOffset)
                {
                    throw new InvalidDataException("ZIP entry data or descriptor crosses the central-directory boundary.");
                }
                stream.Position = descriptorOffset;
                if (reader.ReadUInt32() != DataDescriptorSignature || reader.ReadUInt32() != centralCrc ||
                    reader.ReadUInt32() != centralCompressedSize || reader.ReadUInt32() != centralUncompressedSize)
                {
                    throw new InvalidDataException("ZIP data descriptor is missing or inconsistent with the central entry.");
                }
                expectedLocalOffset = stream.Position;

                stream.Position = nextCentralEntry;
            }

            if (expectedLocalOffset != centralOffset || stream.Position != (long)centralOffset + centralSize)
            {
                throw new InvalidDataException("ZIP local or central region contains non-canonical bytes.");
            }
        }
    }

    private static bool BytesEqual(byte[] left, byte[] right)
    {
        if (left == null || right == null || left.Length != right.Length) return false;
        for (int index = 0; index < left.Length; index++)
        {
            if (left[index] != right[index]) return false;
        }
        return true;
    }
}
'@
}

if ($null -eq ('BaxyStoredZipWriter' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.IO;
using System.Text;

public sealed class BaxyStoredZipSource
{
    public string Name { get; set; }
    public string FilePath { get; set; }
    public byte[] ContentBytes { get; set; }
}

public static class BaxyStoredZipWriter
{
    private const uint LocalFileHeaderSignature = 0x04034b50;
    private const uint DataDescriptorSignature = 0x08074b50;
    private const uint CentralDirectoryHeaderSignature = 0x02014b50;
    private const uint EndOfCentralDirectorySignature = 0x06054b50;
    private const ushort Version20 = 20;
    private const ushort Utf8AndDataDescriptorFlags = 0x0808;
    private const ushort StoredMethod = 0;
    private static readonly uint[] CrcTable = CreateCrcTable();

    private sealed class WrittenEntry
    {
        public byte[] Name;
        public uint Crc32;
        public uint Size;
        public uint LocalOffset;
    }

    public static void Write(string path, BaxyStoredZipSource[] sources, DateTime timestamp)
    {
        if (sources == null || sources.Length > ushort.MaxValue)
        {
            throw new InvalidDataException("ZIP entry count is outside the product contract.");
        }

        ushort dosTime = (ushort)((timestamp.Hour << 11) | (timestamp.Minute << 5) | (timestamp.Second / 2));
        ushort dosDate = (ushort)(((timestamp.Year - 1980) << 9) | (timestamp.Month << 5) | timestamp.Day);
        var written = new List<WrittenEntry>(sources.Length);

        using (var stream = new FileStream(path, FileMode.CreateNew, FileAccess.Write, FileShare.None))
        using (var writer = new BinaryWriter(stream, Encoding.UTF8, true))
        {
            foreach (BaxyStoredZipSource source in sources)
            {
                byte[] name = new UTF8Encoding(false, true).GetBytes(source.Name);
                if (name.Length == 0 || name.Length > ushort.MaxValue)
                {
                    throw new InvalidDataException("ZIP entry name is outside the product contract.");
                }
                if (stream.Position > uint.MaxValue)
                {
                    throw new InvalidDataException("ZIP64 is outside the product contract.");
                }

                uint localOffset = (uint)stream.Position;
                writer.Write(LocalFileHeaderSignature);
                writer.Write(Version20);
                writer.Write(Utf8AndDataDescriptorFlags);
                writer.Write(StoredMethod);
                writer.Write(dosTime);
                writer.Write(dosDate);
                writer.Write(0U);
                writer.Write(0U);
                writer.Write(0U);
                writer.Write((ushort)name.Length);
                writer.Write((ushort)0);
                writer.Write(name);

                Stream input = null;
                try
                {
                    input = source.FilePath != null
                        ? (Stream)new FileStream(source.FilePath, FileMode.Open, FileAccess.Read, FileShare.Read)
                        : new MemoryStream(source.ContentBytes ?? new byte[0], false);
                    uint crc = 0xffffffffU;
                    ulong length = 0;
                    byte[] buffer = new byte[1024 * 1024];
                    int read;
                    while ((read = input.Read(buffer, 0, buffer.Length)) > 0)
                    {
                        stream.Write(buffer, 0, read);
                        length += (uint)read;
                        if (length > uint.MaxValue)
                        {
                            throw new InvalidDataException("ZIP64 is outside the product contract.");
                        }
                        for (int index = 0; index < read; index++)
                        {
                            crc = CrcTable[(crc ^ buffer[index]) & 0xff] ^ (crc >> 8);
                        }
                    }
                    crc = ~crc;
                    uint size = (uint)length;
                    writer.Write(DataDescriptorSignature);
                    writer.Write(crc);
                    writer.Write(size);
                    writer.Write(size);
                    written.Add(new WrittenEntry { Name = name, Crc32 = crc, Size = size, LocalOffset = localOffset });
                }
                finally
                {
                    if (input != null) input.Dispose();
                }
            }

            if (stream.Position > uint.MaxValue)
            {
                throw new InvalidDataException("ZIP64 is outside the product contract.");
            }
            uint centralOffset = (uint)stream.Position;
            foreach (WrittenEntry entry in written)
            {
                writer.Write(CentralDirectoryHeaderSignature);
                writer.Write(Version20);
                writer.Write(Version20);
                writer.Write(Utf8AndDataDescriptorFlags);
                writer.Write(StoredMethod);
                writer.Write(dosTime);
                writer.Write(dosDate);
                writer.Write(entry.Crc32);
                writer.Write(entry.Size);
                writer.Write(entry.Size);
                writer.Write((ushort)entry.Name.Length);
                writer.Write((ushort)0);
                writer.Write((ushort)0);
                writer.Write((ushort)0);
                writer.Write((ushort)0);
                writer.Write(0U);
                writer.Write(entry.LocalOffset);
                writer.Write(entry.Name);
            }
            uint centralSize = checked((uint)(stream.Position - centralOffset));
            writer.Write(EndOfCentralDirectorySignature);
            writer.Write((ushort)0);
            writer.Write((ushort)0);
            writer.Write((ushort)written.Count);
            writer.Write((ushort)written.Count);
            writer.Write(centralSize);
            writer.Write(centralOffset);
            writer.Write((ushort)0);
            writer.Flush();
            stream.Flush(true);
        }
    }

    private static uint[] CreateCrcTable()
    {
        var table = new uint[256];
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
'@
}

function Write-BaxyUtf8NoBom {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][AllowEmptyString()][string]$Text
    )

    [IO.File]::WriteAllText($Path, $Text, $script:BaxyUtf8NoBom)
}

function ConvertTo-BaxyCanonicalJson {
    param([Parameter(Mandatory = $true)]$Value)

    return ($Value | ConvertTo-Json -Depth 12 -Compress)
}

function Get-BaxySha256 {
    param([Parameter(Mandatory = $true)][string]$Path)

    $algorithm = [Security.Cryptography.SHA256]::Create()
    $stream = New-Object IO.FileStream(
        $Path,
        [IO.FileMode]::Open,
        [IO.FileAccess]::Read,
        [IO.FileShare]::Read,
        1048576,
        [IO.FileOptions]::SequentialScan)
    try {
        return ([BitConverter]::ToString($algorithm.ComputeHash($stream))).Replace(
            '-',
            '').ToLowerInvariant()
    } finally {
        $stream.Dispose()
        $algorithm.Dispose()
    }
}

function Get-BaxyBytesSha256 {
    param([Parameter(Mandatory = $true)][AllowEmptyCollection()][byte[]]$Bytes)

    $algorithm = [Security.Cryptography.SHA256]::Create()
    try {
        return ([BitConverter]::ToString($algorithm.ComputeHash($Bytes))).Replace('-', '').ToLowerInvariant()
    } finally {
        $algorithm.Dispose()
    }
}

function Assert-BaxySafeRelativePath {
    param([Parameter(Mandatory = $true)][string]$Path)

    if ([string]::IsNullOrWhiteSpace($Path)) { throw 'Relative path is empty.' }
    if ($Path.Length -gt 240) { throw "Relative path is too long: $Path" }
    if (-not [string]::Equals(
            $Path,
            $Path.Normalize([Text.NormalizationForm]::FormC),
            [StringComparison]::Ordinal)) {
        throw "Relative path is not Unicode NFC: $Path"
    }
    if ($Path.StartsWith('/') -or $Path.EndsWith('/') -or $Path.Contains('//')) {
        throw "Relative path has an unsafe separator: $Path"
    }
    if ($Path.Contains('\') -or $Path.Contains(':')) {
        throw "Relative path has a forbidden Windows path form: $Path"
    }
    if ($Path -match '[\x00-\x1f<>"|?*]') {
        throw "Relative path has forbidden characters: $Path"
    }

    foreach ($segment in @($Path.Split('/'))) {
        if ($segment -eq '.' -or $segment -eq '..') {
            throw "Relative path traverses a directory: $Path"
        }
        if ($segment.Length -eq 0 -or $segment.Length -gt 255) {
            throw "Relative path has an invalid segment: $Path"
        }
        if ($segment.EndsWith('.') -or $segment.EndsWith(' ')) {
            throw "Relative path has a Windows-ambiguous segment: $Path"
        }
        if ($segment -match '^(?i:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?$') {
            throw "Relative path uses a reserved Windows device name: $Path"
        }
    }
}

function Get-BaxyRelativePath {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Path
    )

    $rootFull = [IO.Path]::GetFullPath($Root).TrimEnd(
        [IO.Path]::DirectorySeparatorChar,
        [IO.Path]::AltDirectorySeparatorChar)
    $pathFull = [IO.Path]::GetFullPath($Path)
    Assert-StrictDescendantPath -Parent $rootFull -Child $pathFull
    $relative = $pathFull.Substring($rootFull.Length + 1).Replace('\', '/')
    Assert-BaxySafeRelativePath -Path $relative
    return $relative
}

function Sort-BaxyFileRecordsOrdinal {
    param([Parameter(Mandatory = $true)][AllowEmptyCollection()][object[]]$Records)

    $list = New-Object 'System.Collections.Generic.List[object]'
    foreach ($record in @($Records)) { $list.Add($record) }
    $comparison = [Comparison[object]] {
        param($left, $right)
        return [StringComparer]::Ordinal.Compare([string]$left.path, [string]$right.path)
    }
    $list.Sort($comparison)
    return @($list.ToArray())
}

function Assert-BaxyExactProductPayloadFileSet {
    param([Parameter(Mandatory = $true)][AllowEmptyCollection()][object[]]$Files)

    $records = @(Sort-BaxyFileRecordsOrdinal -Records $Files)
    if ($records.Count -ne $script:BaxyProductPayloadPaths.Count) {
        throw "Product payload must contain exactly $($script:BaxyProductPayloadPaths.Count) reviewed files."
    }
    for ($index = 0; $index -lt $script:BaxyProductPayloadPaths.Count; $index++) {
        if (-not [string]::Equals(
                [string]$records[$index].path,
                [string]$script:BaxyProductPayloadPaths[$index],
                [StringComparison]::Ordinal)) {
            throw "Product payload has an unexpected path: $($records[$index].path)"
        }
    }
}

function Move-BaxyDirectoryAtomically {
    param(
        [Parameter(Mandatory = $true)][string]$AllowedRoot,
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination
    )

    $allowedFull = [IO.Path]::GetFullPath($AllowedRoot)
    $sourceFull = [IO.Path]::GetFullPath($Source)
    $destinationFull = [IO.Path]::GetFullPath($Destination)
    Assert-StrictDescendantPath -Parent $allowedFull -Child $sourceFull
    Assert-StrictDescendantPath -Parent $allowedFull -Child $destinationFull
    $null = Assert-ExistingPathChainHasNoReparsePoint -Path $allowedFull
    $null = Assert-ExistingPathChainHasNoReparsePoint -Path $sourceFull
    Assert-TreeHasNoReparsePoint -Root $sourceFull

    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
    foreach ($file in @(Get-ChildItem -LiteralPath $sourceFull -File -Recurse -Force -ErrorAction Stop)) {
        $openedExclusively = $false
        for ($probeAttempt = 1; $probeAttempt -le 25; $probeAttempt++) {
            try {
                $probe = New-Object IO.FileStream($file.FullName, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::None)
                $probe.Dispose()
                $openedExclusively = $true
                break
            } catch [IO.IOException] {
                if ($probeAttempt -eq 25) { throw }
                Start-Sleep -Milliseconds 200
            }
        }
        if (-not $openedExclusively) { throw "Unable to attest an exclusive staged file handle: $($file.FullName)" }
    }

    Remove-TreeFailClosed -AllowedRoot $allowedFull -Target $destinationFull

    for ($attempt = 1; $attempt -le 25; $attempt++) {
        try {
            [IO.Directory]::Move($sourceFull, $destinationFull)
            return
        } catch [IO.IOException] {
            if ($attempt -eq 25) { throw }
            Start-Sleep -Milliseconds 200
        } catch [UnauthorizedAccessException] {
            if ($attempt -eq 25) { throw }
            Start-Sleep -Milliseconds 200
        }
    }
}

function New-BaxyHeadWorktreeSnapshot {
    param(
        [Parameter(Mandatory = $true)][string]$RepositoryRoot,
        [Parameter(Mandatory = $true)][string]$AllowedRoot,
        [Parameter(Mandatory = $true)][string]$SnapshotRoot,
        [Parameter(Mandatory = $true)][string]$Commit
    )

    $repositoryFull = [IO.Path]::GetFullPath($RepositoryRoot)
    $allowedFull = [IO.Path]::GetFullPath($AllowedRoot)
    $snapshotFull = [IO.Path]::GetFullPath($SnapshotRoot)
    Assert-StrictDescendantPath -Parent $allowedFull -Child $snapshotFull
    $null = Assert-ExistingPathChainHasNoReparsePoint -Path $allowedFull
    if (Test-Path -LiteralPath $snapshotFull) {
        throw "Refusing to reuse an existing source snapshot path: $snapshotFull"
    }
    if ($Commit -notmatch '^[0-9a-f]{40}$') { throw 'Source snapshot commit is invalid.' }

    try {
        & git -C $repositoryFull worktree add --detach $snapshotFull $Commit | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'Unable to create detached Git source snapshot.' }
        $null = Assert-ExistingPathChainHasNoReparsePoint -Path $snapshotFull
        Assert-TreeHasNoReparsePoint -Root $snapshotFull
        $snapshotCommit = ([string](& git -C $snapshotFull rev-parse --verify HEAD)).Trim().ToLowerInvariant()
        if ($LASTEXITCODE -ne 0 -or -not [string]::Equals($snapshotCommit, $Commit, [StringComparison]::Ordinal)) {
            throw 'Detached source snapshot resolved to an unexpected commit.'
        }
        $snapshotStatus = @(& git -C $snapshotFull status --porcelain=v1 --untracked-files=all)
        if ($LASTEXITCODE -ne 0 -or $snapshotStatus.Count -ne 0) {
            throw 'Detached source snapshot is not clean.'
        }
    } catch {
        $failure = $_
        try { Remove-BaxyHeadWorktreeSnapshot -RepositoryRoot $repositoryFull -AllowedRoot $allowedFull -SnapshotRoot $snapshotFull } catch {
            throw "Source snapshot validation failed: $($failure.Exception.Message) Cleanup also failed closed: $($_.Exception.Message)"
        }
        throw $failure
    }
    return $snapshotFull
}

function Remove-BaxyHeadWorktreeSnapshot {
    param(
        [Parameter(Mandatory = $true)][string]$RepositoryRoot,
        [Parameter(Mandatory = $true)][string]$AllowedRoot,
        [Parameter(Mandatory = $true)][string]$SnapshotRoot
    )

    $repositoryFull = [IO.Path]::GetFullPath($RepositoryRoot)
    $allowedFull = [IO.Path]::GetFullPath($AllowedRoot)
    $snapshotFull = [IO.Path]::GetFullPath($SnapshotRoot)
    Assert-StrictDescendantPath -Parent $allowedFull -Child $snapshotFull
    $null = Assert-ExistingPathChainHasNoReparsePoint -Path $allowedFull
    & git -C $repositoryFull worktree remove --force $snapshotFull | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Unable to remove detached Git source snapshot: $snapshotFull" }
    if (Test-Path -LiteralPath $snapshotFull) {
        Remove-TreeFailClosed -AllowedRoot $allowedFull -Target $snapshotFull
    }
}

function Assert-BaxyNoAlternateDataStreams {
    param([Parameter(Mandatory = $true)][string]$Root)

    $rootFull = [IO.Path]::GetFullPath($Root)
    $entries = @((Get-Item -LiteralPath $rootFull -Force -ErrorAction Stop))
    $entries += @(Get-ChildItem -LiteralPath $rootFull -Recurse -Force -ErrorAction Stop)
    foreach ($entry in $entries) {
        $relative = if ([string]::Equals($entry.FullName, $rootFull, [StringComparison]::OrdinalIgnoreCase)) {
            '.'
        } else {
            Get-BaxyRelativePath -Root $rootFull -Path $entry.FullName
        }
        $streams = @([BaxyNativeStreamInspector]::GetStreams($entry.FullName))
        $defaultStreams = @($streams | Where-Object { [string]::Equals($_, '::$DATA', [StringComparison]::OrdinalIgnoreCase) })
        if (-not $entry.PSIsContainer -and $defaultStreams.Count -ne 1) {
            throw "Default data stream could not be attested: $relative"
        }
        foreach ($stream in @($streams | Where-Object { -not [string]::Equals($_, '::$DATA', [StringComparison]::OrdinalIgnoreCase) })) {
            throw "Alternate data stream is forbidden: $relative [$stream]"
        }
    }
}

function Get-BaxyPayloadFileRecords {
    param([Parameter(Mandatory = $true)][string]$PayloadRoot)

    $payloadFull = [IO.Path]::GetFullPath($PayloadRoot)
    if (-not (Test-Path -LiteralPath $payloadFull -PathType Container)) {
        throw "Payload directory is missing: $payloadFull"
    }
    $null = Assert-ExistingPathChainHasNoReparsePoint -Path $payloadFull
    Assert-TreeHasNoReparsePoint -Root $payloadFull
    Assert-BaxyNoAlternateDataStreams -Root $payloadFull

    $caseInsensitivePaths = New-Object 'Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
    $records = @()
    foreach ($file in @(Get-ChildItem -LiteralPath $payloadFull -File -Recurse -Force -ErrorAction Stop)) {
        $relative = Get-BaxyRelativePath -Root $payloadFull -Path $file.FullName
        if (-not $caseInsensitivePaths.Add($relative)) {
            throw "Duplicate payload path under Windows comparison rules: $relative"
        }
        if ([IO.Path]::GetExtension($relative) -match '^(?i:\.pdb|\.dbg)$') {
            throw "Debug symbol file is forbidden in the user payload: $relative"
        }
        $records += [pscustomobject][ordered]@{
            path = $relative
            bytes = [int64]$file.Length
            sha256 = Get-BaxySha256 -Path $file.FullName
        }
    }
    return @(Sort-BaxyFileRecordsOrdinal -Records $records)
}

function Assert-BaxyPropertySet {
    param(
        [Parameter(Mandatory = $true)]$Object,
        [Parameter(Mandatory = $true)][string[]]$Expected,
        [Parameter(Mandatory = $true)][string]$Context
    )

    if ($null -eq $Object) { throw "$Context is missing." }
    $actual = @($Object.PSObject.Properties.Name)
    if ($actual.Count -ne $Expected.Count) {
        throw "$Context has an unexpected property set."
    }
    foreach ($name in $Expected) {
        if (@($actual | Where-Object { [string]::Equals($_, $name, [StringComparison]::Ordinal) }).Count -ne 1) {
            throw "$Context has an unexpected property set."
        }
    }
}

function New-BaxyBuildManifest {
    param(
        [Parameter(Mandatory = $true)][string]$Version,
        [Parameter(Mandatory = $true)][ValidateSet('Debug', 'Release')][string]$Configuration,
        [Parameter(Mandatory = $true)][string]$Commit,
        [Parameter(Mandatory = $true)][bool]$Dirty,
        [Parameter(Mandatory = $true)][ValidateSet('git_head_snapshot', 'working_tree_clean', 'working_tree_development')][string]$SourceProvenance,
        [Parameter(Mandatory = $true)][int64]$SourceDateEpoch,
        [Parameter(Mandatory = $true)][string]$DotnetSdk,
        [Parameter(Mandatory = $true)][string]$PowerShellVersion,
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][object[]]$Files
    )

    $sortedFiles = @(Sort-BaxyFileRecordsOrdinal -Records $Files)
    $totalBytes = [int64]0
    foreach ($file in $sortedFiles) { $totalBytes += [int64]$file.bytes }
    return [ordered]@{
        schema = $script:BaxyBuildManifestSchema
        product = $script:BaxyProductName
        version = $Version
        data_schema = $script:BaxyDataSchema
        configuration = $Configuration
        runtime = $script:BaxyRuntimeIdentifier
        target_framework = $script:BaxyTargetFramework
        authenticity = 'not_provided'
        source = [ordered]@{
            commit = $Commit
            dirty = $Dirty
            provenance = $SourceProvenance
            source_date_epoch = $SourceDateEpoch
        }
        toolchain = [ordered]@{
            dotnet_sdk = $DotnetSdk
            powershell = $PowerShellVersion
        }
        deployment = [ordered]@{
            app = 'self_contained_single_file'
            native_libraries = 'adjacent_no_self_extraction'
            core = 'native_aot_self_contained'
            symbols = 'excluded_from_user_payload'
        }
        file_count = [int]$sortedFiles.Count
        total_bytes = $totalBytes
        files = @($sortedFiles)
    }
}

function Read-BaxyUtf8NoBom {
    param([Parameter(Mandatory = $true)][string]$Path)

    $bytes = [IO.File]::ReadAllBytes($Path)
    if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
        throw "UTF-8 BOM is forbidden in canonical file: $Path"
    }
    return $script:BaxyUtf8NoBom.GetString($bytes)
}

function ConvertFrom-BaxyUtf8NoBomBytes {
    param(
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][byte[]]$Bytes,
        [Parameter(Mandatory = $true)][string]$Context
    )

    if ($Bytes.Length -ge 3 -and $Bytes[0] -eq 0xEF -and $Bytes[1] -eq 0xBB -and $Bytes[2] -eq 0xBF) {
        throw "UTF-8 BOM is forbidden in canonical file: $Context"
    }
    return $script:BaxyUtf8NoBom.GetString($Bytes)
}

function Get-BaxyValidatedBuildManifest {
    param([Parameter(Mandatory = $true)][string]$BuildRoot)

    $buildFull = [IO.Path]::GetFullPath($BuildRoot)
    if (-not (Test-Path -LiteralPath $buildFull -PathType Container)) {
        throw "Build root is missing: $buildFull"
    }
    $null = Assert-ExistingPathChainHasNoReparsePoint -Path $buildFull
    Assert-TreeHasNoReparsePoint -Root $buildFull
    Assert-BaxyNoAlternateDataStreams -Root $buildFull

    $payloadRoot = Join-Path $buildFull 'app'
    $manifestPath = Join-Path $buildFull 'build-manifest.json'
    if (-not (Test-Path -LiteralPath $payloadRoot -PathType Container)) { throw 'Build payload directory app is missing.' }
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) { throw 'build-manifest.json is missing.' }

    $manifestBytes = [IO.File]::ReadAllBytes($manifestPath)
    $raw = ConvertFrom-BaxyUtf8NoBomBytes -Bytes $manifestBytes -Context $manifestPath
    try { $manifest = $raw | ConvertFrom-Json -ErrorAction Stop } catch { throw "Invalid build manifest JSON: $($_.Exception.Message)" }
    Assert-BaxyPropertySet -Object $manifest -Expected @(
        'schema', 'product', 'version', 'data_schema', 'configuration', 'runtime', 'target_framework',
        'authenticity', 'source', 'toolchain', 'deployment', 'file_count', 'total_bytes', 'files'
    ) -Context 'build manifest'
    Assert-BaxyPropertySet -Object $manifest.source -Expected @('commit', 'dirty', 'provenance', 'source_date_epoch') -Context 'build manifest source'
    Assert-BaxyPropertySet -Object $manifest.toolchain -Expected @('dotnet_sdk', 'powershell') -Context 'build manifest toolchain'
    Assert-BaxyPropertySet -Object $manifest.deployment -Expected @('app', 'native_libraries', 'core', 'symbols') -Context 'build manifest deployment'

    if (-not [string]::Equals([string]$manifest.schema, $script:BaxyBuildManifestSchema, [StringComparison]::Ordinal)) { throw 'Unsupported build manifest schema.' }
    if (-not [string]::Equals([string]$manifest.product, $script:BaxyProductName, [StringComparison]::Ordinal)) { throw 'Unexpected build manifest product.' }
    if ([string]$manifest.version -notmatch $script:BaxySemVerPattern) { throw 'Build manifest has an invalid semantic version.' }
    if ($manifest.data_schema -isnot [int] -or [int]$manifest.data_schema -ne $script:BaxyDataSchema) {
        throw 'Build manifest has an unsupported data schema.'
    }
    $isDebug = [string]::Equals([string]$manifest.configuration, 'Debug', [StringComparison]::Ordinal)
    $isRelease = [string]::Equals([string]$manifest.configuration, 'Release', [StringComparison]::Ordinal)
    if (-not $isDebug -and -not $isRelease) { throw 'Build manifest has an invalid configuration.' }
    if (-not [string]::Equals([string]$manifest.runtime, $script:BaxyRuntimeIdentifier, [StringComparison]::Ordinal)) { throw 'Build manifest has an unexpected runtime.' }
    if (-not [string]::Equals([string]$manifest.target_framework, $script:BaxyTargetFramework, [StringComparison]::Ordinal)) { throw 'Build manifest has an unexpected target framework.' }
    if (-not [string]::Equals([string]$manifest.authenticity, 'not_provided', [StringComparison]::Ordinal)) { throw 'Build manifest makes an unsupported authenticity claim.' }
    if ([string]$manifest.source.commit -notmatch '^[0-9a-f]{40}$') { throw 'Build manifest has an invalid Git commit.' }
    if ($manifest.source.dirty -isnot [bool]) { throw 'Build manifest dirty marker must be Boolean.' }
    $provenance = [string]$manifest.source.provenance
    $isHeadSnapshot = [string]::Equals($provenance, 'git_head_snapshot', [StringComparison]::Ordinal)
    $isWorkingTreeClean = [string]::Equals($provenance, 'working_tree_clean', [StringComparison]::Ordinal)
    $isWorkingTreeDevelopment = [string]::Equals($provenance, 'working_tree_development', [StringComparison]::Ordinal)
    if (-not $isHeadSnapshot -and -not $isWorkingTreeClean -and -not $isWorkingTreeDevelopment) {
        throw 'Build manifest source provenance is invalid.'
    }
    if ([bool]$manifest.source.dirty -and -not $isWorkingTreeDevelopment) {
        throw 'Dirty builds must declare working_tree_development provenance.'
    }
    if (-not [bool]$manifest.source.dirty -and $isWorkingTreeDevelopment) {
        throw 'Clean builds cannot declare working_tree_development provenance.'
    }
    if ($isRelease -and -not [bool]$manifest.source.dirty -and -not $isHeadSnapshot) {
        throw 'Clean Release builds must declare git_head_snapshot provenance.'
    }
    if ($isDebug -and -not [bool]$manifest.source.dirty -and -not $isWorkingTreeClean) {
        throw 'Clean Debug builds must declare working_tree_clean provenance.'
    }
    if ([int64]$manifest.source.source_date_epoch -lt 0) { throw 'Build manifest source_date_epoch is invalid.' }
    if ([string]::IsNullOrWhiteSpace([string]$manifest.toolchain.dotnet_sdk)) { throw 'Build manifest dotnet_sdk is missing.' }
    if ([string]::IsNullOrWhiteSpace([string]$manifest.toolchain.powershell)) { throw 'Build manifest powershell version is missing.' }
    if (-not [string]::Equals([string]$manifest.deployment.app, 'self_contained_single_file', [StringComparison]::Ordinal)) { throw 'Build manifest app deployment is invalid.' }
    if (-not [string]::Equals([string]$manifest.deployment.native_libraries, 'adjacent_no_self_extraction', [StringComparison]::Ordinal)) { throw 'Build manifest native library deployment is invalid.' }
    if (-not [string]::Equals([string]$manifest.deployment.core, 'native_aot_self_contained', [StringComparison]::Ordinal)) { throw 'Build manifest core deployment is invalid.' }
    if (-not [string]::Equals([string]$manifest.deployment.symbols, 'excluded_from_user_payload', [StringComparison]::Ordinal)) { throw 'Build manifest symbol policy is invalid.' }

    $manifestRecords = @()
    $caseInsensitivePaths = New-Object 'Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
    $previousPath = $null
    foreach ($record in @($manifest.files)) {
        Assert-BaxyPropertySet -Object $record -Expected @('path', 'bytes', 'sha256') -Context 'build manifest file record'
        $relative = [string]$record.path
        Assert-BaxySafeRelativePath -Path $relative
        if (-not $caseInsensitivePaths.Add($relative)) { throw "Duplicate manifest path under Windows comparison rules: $relative" }
        if ($null -ne $previousPath -and [StringComparer]::Ordinal.Compare($previousPath, $relative) -ge 0) {
            throw 'Build manifest file records are not in strict ordinal order.'
        }
        $previousPath = $relative
        if ([IO.Path]::GetExtension($relative) -match '^(?i:\.pdb|\.dbg)$') { throw "Debug symbol file is forbidden in the manifest: $relative" }
        if ([int64]$record.bytes -lt 0) { throw "Invalid manifest byte count: $relative" }
        if ([string]$record.sha256 -notmatch '^[0-9a-f]{64}$') { throw "Invalid manifest SHA-256: $relative" }
        $manifestRecords += [pscustomobject][ordered]@{
            path = $relative
            bytes = [int64]$record.bytes
            sha256 = [string]$record.sha256
        }
    }

    $actualRecords = @(Get-BaxyPayloadFileRecords -PayloadRoot $payloadRoot)
    Assert-BaxyExactProductPayloadFileSet -Files $actualRecords
    if ($manifestRecords.Count -ne $actualRecords.Count) { throw 'Manifest file set does not match the payload file set.' }
    for ($index = 0; $index -lt $actualRecords.Count; $index++) {
        $expected = $manifestRecords[$index]
        $actual = $actualRecords[$index]
        if (-not [string]::Equals([string]$expected.path, [string]$actual.path, [StringComparison]::Ordinal) -or
            [int64]$expected.bytes -ne [int64]$actual.bytes -or
            -not [string]::Equals([string]$expected.sha256, [string]$actual.sha256, [StringComparison]::Ordinal)) {
            throw "Manifest record does not match payload bytes: $($expected.path)"
        }
    }

    $rootFiles = @(Get-ChildItem -LiteralPath $buildFull -File -Recurse -Force -ErrorAction Stop)
    if ($rootFiles.Count -ne ($actualRecords.Count + 1)) { throw 'Build root contains bytes outside the manifest and payload.' }
    foreach ($rootFile in $rootFiles) {
        $relativeToBuild = Get-BaxyRelativePath -Root $buildFull -Path $rootFile.FullName
        if ([string]::Equals($relativeToBuild, 'build-manifest.json', [StringComparison]::Ordinal)) { continue }
        if (-not $relativeToBuild.StartsWith('app/', [StringComparison]::Ordinal)) {
            throw "Build root contains an unexpected file: $relativeToBuild"
        }
    }

    $canonical = New-BaxyBuildManifest `
        -Version ([string]$manifest.version) `
        -Configuration ([string]$manifest.configuration) `
        -Commit ([string]$manifest.source.commit) `
        -Dirty ([bool]$manifest.source.dirty) `
        -SourceProvenance ([string]$manifest.source.provenance) `
        -SourceDateEpoch ([int64]$manifest.source.source_date_epoch) `
        -DotnetSdk ([string]$manifest.toolchain.dotnet_sdk) `
        -PowerShellVersion ([string]$manifest.toolchain.powershell) `
        -Files $manifestRecords
    if ([int]$manifest.file_count -ne $manifestRecords.Count) { throw 'Build manifest file_count is invalid.' }
    if ([int64]$manifest.total_bytes -ne [int64]$canonical.total_bytes) { throw 'Build manifest total_bytes is invalid.' }
    $canonicalText = ConvertTo-BaxyCanonicalJson -Value $canonical
    if (-not [string]::Equals($raw, $canonicalText, [StringComparison]::Ordinal)) {
        throw 'build-manifest.json is not canonical.'
    }

    return [pscustomobject][ordered]@{
        manifest = $canonical
        manifest_path = $manifestPath
        manifest_text = $raw
        manifest_bytes = [byte[]]$manifestBytes
        manifest_sha256 = Get-BaxyBytesSha256 -Bytes $manifestBytes
        payload_root = $payloadRoot
        files = @($manifestRecords)
    }
}

function Get-BaxyFixedZipTimestamp {
    param([Parameter(Mandatory = $true)][int64]$SourceDateEpoch)

    $minimum = [DateTimeOffset]::new(1980, 1, 1, 0, 0, 0, [TimeSpan]::Zero)
    $maximum = [DateTimeOffset]::new(2107, 12, 31, 23, 59, 58, [TimeSpan]::Zero)
    try { $timestamp = [DateTimeOffset]::FromUnixTimeSeconds($SourceDateEpoch).ToUniversalTime() } catch { throw 'source_date_epoch cannot be represented.' }
    if ($timestamp -lt $minimum) { $timestamp = $minimum }
    if ($timestamp -gt $maximum) { $timestamp = $maximum }
    $timestamp = $timestamp.AddTicks(-($timestamp.Ticks % [TimeSpan]::TicksPerSecond))
    if (($timestamp.Second % 2) -ne 0) { $timestamp = $timestamp.AddSeconds(-1) }
    return $timestamp
}
