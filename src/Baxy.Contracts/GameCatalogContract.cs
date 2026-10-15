namespace Baxy.Contracts;

public static class GameCatalogContract
{
    public const int CurrentVersion = 1;
    public const int MaximumEntries = 4_096;
    public const int MaximumAppIdLength = 16;
    public const int MaximumNameUtf8Bytes = 512;
    public const int MaximumTotalUtf8Bytes = 512 * 1024;
}
