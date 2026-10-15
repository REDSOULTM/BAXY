namespace Baxy.Contracts;

public static class ApplicationCatalogContract
{
    public const int CurrentVersion = 1;
    public const int MaximumNames = 2_048;
    public const int MaximumNameUtf8Bytes = 512;
    public const int MaximumTotalNameUtf8Bytes = 262_144;
    public const int MaximumEscapedNamesUtf8Bytes = 262_144;
}
