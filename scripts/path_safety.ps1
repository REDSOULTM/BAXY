function Assert-StrictDescendantPath {
    param(
        [Parameter(Mandatory = $true)][string]$Parent,
        [Parameter(Mandatory = $true)][string]$Child
    )

    $parentFull = [IO.Path]::GetFullPath($Parent).TrimEnd(
        [IO.Path]::DirectorySeparatorChar,
        [IO.Path]::AltDirectorySeparatorChar)
    $childFull = [IO.Path]::GetFullPath($Child)
    foreach ($full in @($parentFull, $childFull)) {
        $volumeRoot = [IO.Path]::GetPathRoot($full)
        if ([string]::IsNullOrWhiteSpace($volumeRoot)) { throw "Path has no volume root: $full" }
        if ($full.IndexOf(':', $volumeRoot.Length) -ge 0) {
            throw "Refusing alternate data stream path: $full"
        }
    }
    if (-not $childFull.StartsWith(
            $parentFull + [IO.Path]::DirectorySeparatorChar,
            [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing path outside $parentFull`: $childFull"
    }
}

function Assert-ExistingPathChainHasNoReparsePoint {
    param([Parameter(Mandatory = $true)][string]$Path)

    $full = [IO.Path]::GetFullPath($Path)
    $volumeRoot = [IO.Path]::GetPathRoot($full)
    if ([string]::IsNullOrWhiteSpace($volumeRoot)) { throw "Path has no volume root: $full" }
    if ($full.IndexOf(':', $volumeRoot.Length) -ge 0) {
        throw "Refusing alternate data stream path: $full"
    }
    $current = New-Object IO.DirectoryInfo($volumeRoot)
    if (($current.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "Refusing path below a reparse point: $($current.FullName)"
    }

    $relative = $full.Substring($volumeRoot.Length)
    $segments = @($relative.Split(
        @([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar),
        [StringSplitOptions]::RemoveEmptyEntries))
    for ($index = 0; $index -lt $segments.Count; $index++) {
        $segment = $segments[$index]
        try {
            $matches = @($current.EnumerateFileSystemInfos() | Where-Object {
                [string]::Equals($_.Name, $segment, [StringComparison]::OrdinalIgnoreCase)
            })
        } catch {
            throw "Unable to inspect path component without traversal: $($current.FullName) ($($_.Exception.GetType().Name))"
        }
        if ($matches.Count -eq 0) { return $false }
        if ($matches.Count -ne 1) { throw "Ambiguous path component below $($current.FullName): $segment" }
        $entry = $matches[0]
        if (($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "Refusing reparse point in path: $($entry.FullName)"
        }
        if ($index -lt ($segments.Count - 1)) {
            if (($entry.Attributes -band [IO.FileAttributes]::Directory) -eq 0) {
                throw "Non-directory path component blocks path: $($entry.FullName)"
            }
            $current = New-Object IO.DirectoryInfo($entry.FullName)
        }
    }
    return $true
}

function Assert-TreeHasNoReparsePoint {
    param([Parameter(Mandatory = $true)][string]$Root)

    $pending = New-Object 'System.Collections.Generic.Stack[System.IO.DirectoryInfo]'
    $pending.Push((New-Object IO.DirectoryInfo([IO.Path]::GetFullPath($Root))))
    while ($pending.Count -gt 0) {
        $directory = $pending.Pop()
        if (($directory.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "Refusing reparse point in tree: $($directory.FullName)"
        }
        try {
            $entries = @($directory.EnumerateFileSystemInfos())
        } catch {
            throw "Unable to inspect tree without traversal: $($directory.FullName) ($($_.Exception.GetType().Name))"
        }
        foreach ($entry in $entries) {
            if (($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw "Refusing reparse point in tree: $($entry.FullName)"
            }
            if (($entry.Attributes -band [IO.FileAttributes]::Directory) -ne 0) {
                $pending.Push((New-Object IO.DirectoryInfo($entry.FullName)))
            }
        }
    }
}

function Remove-TreeFailClosed {
    param(
        [Parameter(Mandatory = $true)][string]$AllowedRoot,
        [Parameter(Mandatory = $true)][string]$Target
    )

    Assert-StrictDescendantPath -Parent $AllowedRoot -Child $Target
    $null = Assert-ExistingPathChainHasNoReparsePoint -Path $AllowedRoot
    $targetExists = Assert-ExistingPathChainHasNoReparsePoint -Path $Target
    if (-not $targetExists) { return }
    $targetItem = Get-Item -LiteralPath $Target -Force -ErrorAction Stop
    if (-not $targetItem.PSIsContainer) { throw "Destructive target is not a directory: $Target" }
    Assert-TreeHasNoReparsePoint -Root $Target
    if (-not (Assert-ExistingPathChainHasNoReparsePoint -Path $Target)) {
        throw "Destructive target disappeared during validation: $Target"
    }
    Remove-Item -LiteralPath $Target -Recurse -Force -ErrorAction Stop
}
