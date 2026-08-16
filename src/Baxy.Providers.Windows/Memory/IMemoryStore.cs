namespace Baxy.Providers.Windows.Memory;

public interface IMemoryStore
{
    string RootDirectory { get; }

    MemoryConfigurationResult Configure(MemoryConfigureRequest request);

    MemoryBeginSessionResult BeginSession(MemoryBeginSessionRequest request);

    MemoryStatusResult Status(MemoryStatusRequest request);

    MemorySaveResult Save(MemorySaveRequest request);

    MemoryRecallResult Recall(MemoryRecallRequest request);

    MemoryListResult List(MemoryListRequest request);

    MemoryCorrectResult Correct(MemoryCorrectRequest request);

    MemoryForgetResult Forget(MemoryForgetRequest request);
}
