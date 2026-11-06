namespace Baxy.Installer;

/// <summary>Reads files as one seekable stream, so a zip cut into parts opens without a second copy on disk.</summary>
internal sealed class ConcatenatedStream : Stream
{
    private readonly FileStream[] files;
    private readonly long[] starts;
    private long position;

    internal ConcatenatedStream(IEnumerable<string> paths)
    {
        files = paths.Select(File.OpenRead).ToArray();
        starts = new long[files.Length];
        long start = 0;
        for (int index = 0; index < files.Length; index++)
        {
            starts[index] = start;
            start += files[index].Length;
        }

        Length = start;
    }

    public override bool CanRead => true;

    public override bool CanSeek => true;

    public override bool CanWrite => false;

    public override long Length { get; }

    public override long Position
    {
        get => position;
        set
        {
            ArgumentOutOfRangeException.ThrowIfNegative(value);
            position = value;
        }
    }

    public override int Read(byte[] buffer, int offset, int count) => Read(buffer.AsSpan(offset, count));

    public override int Read(Span<byte> buffer)
    {
        if (position >= Length || buffer.IsEmpty)
        {
            return 0;
        }

        int index = Array.BinarySearch(starts, position);
        index = index >= 0 ? index : ~index - 1;
        FileStream file = files[index];
        file.Position = position - starts[index];
        int read = file.Read(buffer);
        position += read;
        return read;
    }

    public override long Seek(long offset, SeekOrigin origin)
    {
        Position = origin switch
        {
            SeekOrigin.Begin => offset,
            SeekOrigin.Current => position + offset,
            _ => Length + offset,
        };
        return position;
    }

    public override void Flush()
    {
    }

    public override void SetLength(long value) => throw new NotSupportedException();

    public override void Write(byte[] buffer, int offset, int count) => throw new NotSupportedException();

    protected override void Dispose(bool disposing)
    {
        if (disposing)
        {
            foreach (FileStream file in files)
            {
                file.Dispose();
            }
        }

        base.Dispose(disposing);
    }
}
