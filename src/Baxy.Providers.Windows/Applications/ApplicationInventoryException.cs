namespace Baxy.Providers.Windows.Applications;

// The windows of an application could not be inventoried completely or their identity could not be read.
internal sealed class ApplicationInventoryException(string message) : Exception(message);
