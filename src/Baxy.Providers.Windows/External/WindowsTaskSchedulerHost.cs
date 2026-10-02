using System.Runtime.InteropServices;
using System.Runtime.InteropServices.Marshalling;
using System.Security.Principal;
using Microsoft.Win32;

namespace Baxy.Providers.Windows.External;

/// <summary>What Get-ScheduledTask and Get-ScheduledTaskInfo report of one task; times are local.</summary>
internal sealed record ScheduledTaskSnapshot(
    string Name,
    int State,
    DateTime? NextRunLocal,
    DateTime? LastRunLocal,
    int LastTaskResult);

/// <summary>A Task Scheduler or environment call that failed; the native backend falls back on it.</summary>
internal sealed class TaskSchedulerHostException(string message, Exception? inner = null)
    : Exception(message, inner);

internal interface ITaskSchedulerHost
{
    /// <summary>Connects to the Task Scheduler folder the notifications live in.</summary>
    ITaskSchedulerSession Open();

    /// <summary>HKCU NOC_GLOBAL_SETTING_TOASTS_ENABLED as the script reads it; null when absent.</summary>
    int? ToastsEnabledSetting();

    /// <summary>The SID Register-ScheduledTask writes as the task principal (the current user).</summary>
    string CurrentUserSid();
}

internal interface ITaskSchedulerSession : IDisposable
{
    IReadOnlyList<string> TaskNames();

    /// <summary>Every task whose name starts with the prefix (ignoring case), read in one enumeration.</summary>
    IReadOnlyList<ScheduledTaskSnapshot> Read(string namePrefix);

    /// <summary>The task by name, or null when the folder has no such task.</summary>
    ScheduledTaskSnapshot? Find(string name);

    /// <summary>Registers (create or update) the task XML with the user's interactive token.</summary>
    void Register(string name, string xml);

    void Delete(string name);
}

/// <summary>
/// M119: the Task Scheduler 2.0 COM API in-process (CLSID TaskScheduler, ITaskService), so a
/// notification does not pay a powershell.exe start for Register-ScheduledTask (~2 s per turn).
/// </summary>
internal sealed partial class WindowsTaskSchedulerHost(string folderPath = "\\") : ITaskSchedulerHost
{
    private const string ToastSettingsKey =
        @"Software\Microsoft\Windows\CurrentVersion\Notifications\Settings";

    public ITaskSchedulerSession Open()
    {
        try
        {
            return new Session(folderPath);
        }
        catch (TaskSchedulerHostException)
        {
            throw;
        }
        catch (Exception exception)
        {
            throw new TaskSchedulerHostException("task_scheduler_open_failed", exception);
        }
    }

    public string CurrentUserSid()
    {
        using WindowsIdentity identity = WindowsIdentity.GetCurrent();
        return identity.User?.Value ?? throw new TaskSchedulerHostException("user_sid_unavailable");
    }

    public int? ToastsEnabledSetting()
    {
        try
        {
            using RegistryKey? key = Registry.CurrentUser.OpenSubKey(ToastSettingsKey);
            object? value = key?.GetValue("NOC_GLOBAL_SETTING_TOASTS_ENABLED");
            return value is null
                ? null
                : Convert.ToInt32(value, System.Globalization.CultureInfo.InvariantCulture);
        }
        catch (Exception exception)
        {
            throw new TaskSchedulerHostException("toast_setting_read_failed", exception);
        }
    }

    /// <summary>The connected ITaskService; the caller releases it with <see cref="Release"/>.</summary>
    internal static ITaskSchedulerService Connect()
    {
        int result = CoCreateInstance(
            in TaskSchedulerClassId, 0, ClsctxInprocServer, in TaskServiceInterfaceId, out nint pointer);
        if (result < 0 || pointer == 0)
            throw new TaskSchedulerHostException($"task_scheduler_create_failed:0x{result:X8}");
        object wrapper;
        try
        {
            wrapper = ComWrappers.GetOrCreateObjectForComInstance(pointer, CreateObjectFlags.UniqueInstance);
        }
        finally
        {
            Marshal.Release(pointer);
        }
        if (wrapper is not ITaskSchedulerService service)
        {
            Release(wrapper);
            throw new TaskSchedulerHostException("task_scheduler_interface_missing");
        }
        result = service.Connect(default, default, default, default);
        if (result < 0)
        {
            Release(service);
            throw new TaskSchedulerHostException($"task_scheduler_connect_failed:0x{result:X8}");
        }
        return service;
    }

    internal static void Release(object? comObject)
    {
        if (comObject is ComObject wrapper) wrapper.FinalRelease();
    }

    internal static void ThrowOnFailure(int result, string stage)
    {
        if (result < 0) throw new TaskSchedulerHostException($"{stage}:0x{result:X8}");
    }

    private sealed class Session : ITaskSchedulerSession
    {
        private const int TaskEnumHidden = 1;
        private const int TaskCreateOrUpdate = 6;
        private const int TaskLogonInteractiveToken = 3;
        private const int FileNotFound = unchecked((int)0x80070002);
        private const int PathNotFound = unchecked((int)0x80070003);
        private readonly bool _uninitialize;
        private ITaskSchedulerService? _service;
        private ITaskSchedulerFolder? _folder;

        internal Session(string folderPath)
        {
            int initialized = CoInitializeEx(0, CoinitMultithreaded);
            if (initialized < 0 && initialized != RpcEChangedMode)
                throw new TaskSchedulerHostException($"com_initialize_failed:0x{initialized:X8}");
            _uninitialize = initialized >= 0;
            try
            {
                _service = Connect();
                ThrowOnFailure(_service.GetFolder(folderPath, out ITaskSchedulerFolder? folder), "task_folder_open_failed");
                _folder = folder ?? throw new TaskSchedulerHostException("task_folder_missing");
            }
            catch
            {
                Dispose();
                throw;
            }
        }

        private ITaskSchedulerFolder Folder =>
            _folder ?? throw new ObjectDisposedException(nameof(WindowsTaskSchedulerHost));

        public IReadOnlyList<string> TaskNames() =>
            Enumerate((name, _) => name);

        public IReadOnlyList<ScheduledTaskSnapshot> Read(string namePrefix) =>
            Enumerate((name, task) => name.StartsWith(namePrefix, StringComparison.OrdinalIgnoreCase)
                ? Snapshot(task, name)
                : null);

        private List<T> Enumerate<T>(Func<string, IRegisteredTask, T?> select) where T : class =>
            Guard("task_enumeration_failed", () =>
            {
                ThrowOnFailure(Folder.GetTasks(TaskEnumHidden, out IRegisteredTaskCollection? tasks), "task_enumeration_failed");
                try
                {
                    ThrowOnFailure(tasks!.GetCount(out int count), "task_enumeration_failed");
                    List<T> selected = new(count);
                    for (int index = 1; index <= count; index++)
                    {
                        ThrowOnFailure(tasks.GetItem(TaskSchedulerVariant.Int32(index), out IRegisteredTask? task), "task_enumeration_failed");
                        try
                        {
                            ThrowOnFailure(task!.GetName(out string? name), "task_enumeration_failed");
                            if (name is not null && select(name, task) is T item) selected.Add(item);
                        }
                        finally
                        {
                            Release(task);
                        }
                    }
                    return selected;
                }
                finally
                {
                    Release(tasks);
                }
            });

        public ScheduledTaskSnapshot? Find(string name) => Guard("task_read_failed", () =>
        {
            int result = Folder.GetTask(name, out IRegisteredTask? task);
            if (result is FileNotFound or PathNotFound)
            {
                Release(task);
                return null;
            }
            ThrowOnFailure(result, "task_read_failed");
            try
            {
                ThrowOnFailure(task!.GetName(out string? observedName), "task_read_failed");
                return Snapshot(task, observedName ?? name);
            }
            finally
            {
                Release(task);
            }
        });

        private static ScheduledTaskSnapshot Snapshot(IRegisteredTask task, string name)
        {
            ThrowOnFailure(task.GetState(out int state), "task_read_failed");
            ThrowOnFailure(task.GetNextRunTime(out double nextRun), "task_read_failed");
            ThrowOnFailure(task.GetLastRunTime(out double lastRun), "task_read_failed");
            ThrowOnFailure(task.GetLastTaskResult(out int lastResult), "task_read_failed");
            return new ScheduledTaskSnapshot(name, state, LocalTime(nextRun), LocalTime(lastRun), lastResult);
        }

        public void Register(string name, string xml) => Guard("task_register_failed", () =>
        {
            ThrowOnFailure(Folder.RegisterTask(
                name, xml, TaskCreateOrUpdate, default, default, TaskLogonInteractiveToken, default,
                out IRegisteredTask? task), "task_register_failed");
            Release(task);
            return true;
        });

        public void Delete(string name) => Guard("task_delete_failed", () =>
        {
            ThrowOnFailure(Folder.DeleteTask(name, 0), "task_delete_failed");
            return true;
        });

        public void Dispose()
        {
            Release(Interlocked.Exchange(ref _folder, null));
            Release(Interlocked.Exchange(ref _service, null));
            if (_uninitialize) CoUninitialize();
        }

        // Task Scheduler reports «no time» as DATE 0 (1899-12-30); the CIM cmdlets report it as null.
        private static DateTime? LocalTime(double oaDate) =>
            oaDate == 0 ? null : DateTime.FromOADate(oaDate);

        private static T Guard<T>(string stage, Func<T> call)
        {
            try
            {
                return call();
            }
            catch (TaskSchedulerHostException)
            {
                throw;
            }
            catch (Exception exception)
            {
                throw new TaskSchedulerHostException(stage, exception);
            }
        }
    }

    private const uint ClsctxInprocServer = 1;
    private const uint CoinitMultithreaded = 0;
    private const int RpcEChangedMode = unchecked((int)0x80010106);
    private static readonly Guid TaskSchedulerClassId = new("0f87369f-a4e5-4cfc-bd3e-73e6154572dd");
    private static readonly Guid TaskServiceInterfaceId = new("2faba4c7-4da9-4013-9697-20cc3fd40f85");
    private static readonly StrategyBasedComWrappers ComWrappers = new();

    [LibraryImport("ole32.dll")]
    private static partial int CoInitializeEx(nint reserved, uint coInit);

    [LibraryImport("ole32.dll")]
    private static partial void CoUninitialize();

    [LibraryImport("ole32.dll")]
    private static partial int CoCreateInstance(
        in Guid classId, nint outer, uint classContext, in Guid interfaceId, out nint instance);
}

/// <summary>
/// A VARIANT that stays blittable with runtime marshalling on: VT_EMPTY (default) or VT_I4.
/// 24 bytes on 64-bit Windows, 16 on 32-bit, like the native one.
/// </summary>
[StructLayout(LayoutKind.Sequential)]
internal readonly struct TaskSchedulerVariant
{
    private const ushort VtI4 = 3;
    private readonly ushort _type;
    private readonly ushort _reserved1;
    private readonly ushort _reserved2;
    private readonly ushort _reserved3;
    private readonly nint _value;
    private readonly nint _record;

    private TaskSchedulerVariant(ushort type, nint value)
    {
        _type = type;
        _value = value;
    }

    internal static TaskSchedulerVariant Int32(int value) => new(VtI4, value);
}

// taskschd.h vtables (IDispatch first). Only the slots up to the last method BAXY calls are declared.
[GeneratedComInterface(
    StringMarshalling = StringMarshalling.Custom,
    StringMarshallingCustomType = typeof(BStrStringMarshaller),
    Options = ComInterfaceOptions.ComObjectWrapper)]
[Guid("2faba4c7-4da9-4013-9697-20cc3fd40f85")]
internal partial interface ITaskSchedulerService
{
    [PreserveSig] int GetTypeInfoCount(out uint count);
    [PreserveSig] int GetTypeInfo(uint index, uint locale, out nint typeInfo);
    [PreserveSig] int GetIDsOfNames(nint interfaceId, nint names, uint count, uint locale, nint dispatchIds);
    [PreserveSig] int Invoke(int dispatchId, nint interfaceId, uint locale, ushort flags, nint parameters, nint result, nint exception, nint argumentError);

    [PreserveSig]
    int GetFolder(
        string path,
        [MarshalUsing(typeof(UniqueComInterfaceMarshaller<ITaskSchedulerFolder>))] out ITaskSchedulerFolder? folder);

    [PreserveSig] int GetRunningTasks(int flags, out nint runningTasks);
    [PreserveSig] int NewTask(uint flags, out nint definition);
    [PreserveSig] int Connect(TaskSchedulerVariant serverName, TaskSchedulerVariant user, TaskSchedulerVariant domain, TaskSchedulerVariant password);
}

[GeneratedComInterface(
    StringMarshalling = StringMarshalling.Custom,
    StringMarshallingCustomType = typeof(BStrStringMarshaller),
    Options = ComInterfaceOptions.ComObjectWrapper)]
[Guid("8cfac062-a080-4c15-9a88-aa7c2af80dfc")]
internal partial interface ITaskSchedulerFolder
{
    [PreserveSig] int GetTypeInfoCount(out uint count);
    [PreserveSig] int GetTypeInfo(uint index, uint locale, out nint typeInfo);
    [PreserveSig] int GetIDsOfNames(nint interfaceId, nint names, uint count, uint locale, nint dispatchIds);
    [PreserveSig] int Invoke(int dispatchId, nint interfaceId, uint locale, ushort flags, nint parameters, nint result, nint exception, nint argumentError);

    [PreserveSig] int GetName(out string? name);
    [PreserveSig] int GetPath(out string? path);

    [PreserveSig]
    int GetFolder(
        string path,
        [MarshalUsing(typeof(UniqueComInterfaceMarshaller<ITaskSchedulerFolder>))] out ITaskSchedulerFolder? folder);

    [PreserveSig] int GetFolders(int flags, out nint folders);

    [PreserveSig]
    int CreateFolder(
        string subFolderName,
        TaskSchedulerVariant sddl,
        [MarshalUsing(typeof(UniqueComInterfaceMarshaller<ITaskSchedulerFolder>))] out ITaskSchedulerFolder? folder);

    [PreserveSig] int DeleteFolder(string subFolderName, int flags);

    [PreserveSig]
    int GetTask(
        string path,
        [MarshalUsing(typeof(UniqueComInterfaceMarshaller<IRegisteredTask>))] out IRegisteredTask? task);

    [PreserveSig]
    int GetTasks(
        int flags,
        [MarshalUsing(typeof(UniqueComInterfaceMarshaller<IRegisteredTaskCollection>))] out IRegisteredTaskCollection? tasks);

    [PreserveSig] int DeleteTask(string name, int flags);

    [PreserveSig]
    int RegisterTask(
        string path,
        string xmlText,
        int flags,
        TaskSchedulerVariant userId,
        TaskSchedulerVariant password,
        int logonType,
        TaskSchedulerVariant sddl,
        [MarshalUsing(typeof(UniqueComInterfaceMarshaller<IRegisteredTask>))] out IRegisteredTask? task);
}

[GeneratedComInterface(
    StringMarshalling = StringMarshalling.Custom,
    StringMarshallingCustomType = typeof(BStrStringMarshaller),
    Options = ComInterfaceOptions.ComObjectWrapper)]
[Guid("86627eb4-42a7-41e4-a4d9-ac33a72f2d52")]
internal partial interface IRegisteredTaskCollection
{
    [PreserveSig] int GetTypeInfoCount(out uint count);
    [PreserveSig] int GetTypeInfo(uint index, uint locale, out nint typeInfo);
    [PreserveSig] int GetIDsOfNames(nint interfaceId, nint names, uint count, uint locale, nint dispatchIds);
    [PreserveSig] int Invoke(int dispatchId, nint interfaceId, uint locale, ushort flags, nint parameters, nint result, nint exception, nint argumentError);

    [PreserveSig] int GetCount(out int count);

    [PreserveSig]
    int GetItem(
        TaskSchedulerVariant index,
        [MarshalUsing(typeof(UniqueComInterfaceMarshaller<IRegisteredTask>))] out IRegisteredTask? task);
}

[GeneratedComInterface(
    StringMarshalling = StringMarshalling.Custom,
    StringMarshallingCustomType = typeof(BStrStringMarshaller),
    Options = ComInterfaceOptions.ComObjectWrapper)]
[Guid("9c86f320-dee3-4dd1-b972-a303f26b061e")]
internal partial interface IRegisteredTask
{
    [PreserveSig] int GetTypeInfoCount(out uint count);
    [PreserveSig] int GetTypeInfo(uint index, uint locale, out nint typeInfo);
    [PreserveSig] int GetIDsOfNames(nint interfaceId, nint names, uint count, uint locale, nint dispatchIds);
    [PreserveSig] int Invoke(int dispatchId, nint interfaceId, uint locale, ushort flags, nint parameters, nint result, nint exception, nint argumentError);

    [PreserveSig] int GetName(out string? name);
    [PreserveSig] int GetPath(out string? path);
    [PreserveSig] int GetState(out int state);
    [PreserveSig] int GetEnabled(out short enabled);
    [PreserveSig] int SetEnabled(short enabled);
    [PreserveSig] int Run(TaskSchedulerVariant parameters, out nint runningTask);
    [PreserveSig] int RunEx(TaskSchedulerVariant parameters, int flags, int sessionId, string? user, out nint runningTask);
    [PreserveSig] int GetInstances(int flags, out nint runningTasks);
    [PreserveSig] int GetLastRunTime(out double lastRunTime);
    [PreserveSig] int GetLastTaskResult(out int lastTaskResult);
    [PreserveSig] int GetNumberOfMissedRuns(out int missedRuns);
    [PreserveSig] int GetNextRunTime(out double nextRunTime);
    [PreserveSig] int GetDefinition(out nint definition);
    [PreserveSig] int GetXml(out string? xml);
}
