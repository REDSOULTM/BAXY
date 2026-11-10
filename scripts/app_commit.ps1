# PKG-2: the App of a package is the one built at the commit its mind is taken from. scripts\build_product.ps1 seals the commit
# in the App's product version, <version>+<first 12 of the commit> (or <version>.sha.<those 12> when the version already has
# a +), with .dirty after it for a worktree with changes; the .NET SDK then adds the whole commit, its SourceRevisionId
# (https://learn.microsoft.com/dotnet/core/project-sdk/msbuild-props#includesourcerevisionininformationalversion). Measured on
# 1.1.1's Baxy.exe: «1.1.1+97300d6813e7.97300d6813e740201c769ca1f3d0574fb2f81d11».
function Assert-BaxyAppCommit {
    param(
        [Parameter(Mandatory = $true)][AllowEmptyString()][string]$ProductVersion,
        [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-f]{40}$')][string]$Commit
    )

    $plus = $ProductVersion.IndexOf('+')
    $sealed = @(if ($plus -ge 0) { $ProductVersion.Substring($plus + 1).Split('.') })
    if ($sealed -ccontains 'dirty') {
        throw "steam_build_failed: the App ($ProductVersion) was built from a worktree with changes; run scripts\build_product.ps1 on the clean commit"
    }
    if ($sealed -cnotcontains $Commit.Substring(0, 12)) {
        throw "steam_build_failed: the App ($ProductVersion) is not of commit $Commit, the one the mind is taken from; run scripts\build_product.ps1 at this commit first"
    }
}
