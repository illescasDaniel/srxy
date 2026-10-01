// Self-extracting GUI launcher for the Windows PySide offline installer.
// Compiled at build time with:
//   csc /target:winexe /win32icon:srxy-installer.ico
//       /r:System.Windows.Forms.dll
//       /r:System.IO.Compression.dll
//       /r:System.IO.Compression.FileSystem.dll
//       /out:SrxyInstaller.stub.exe SrxyInstallerLauncher.cs
// The build then appends a zip of python\ + venv\ + share\ plus a trailer:
//   [stub PE][zip bytes][sha256 32][zip_length uint64 LE][magic "SRXYISFX"]
// On launch the stub extracts the payload (once) under
// %LOCALAPPDATA%\srxy\is\<sha16>\p\ and execs
// venv\Scripts\pythonw.exe -m srxy.adapters.inbound.installer with
// SRXY_INSTALLER_PAYLOAD set (same contract as package_spec / meta / install).
using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Windows.Forms;

internal static class Program
{
	private const string Magic = "SRXYISFX";
	private const int TrailerSize = 32 + 8 + 8; // sha256 + zip_length + magic

	[STAThread]
	private static int Main(string[] args)
	{
		bool headless = args != null && args.Length > 0;
		try
		{
			string exe = Assembly.GetExecutingAssembly().Location;
			if (string.IsNullOrEmpty(exe))
				exe = Process.GetCurrentProcess().MainModule.FileName;
			exe = Path.GetFullPath(exe);

			string payloadDir = EnsurePayload(exe, headless);
			string pythonw = Path.Combine(payloadDir, "venv", "Scripts", "pythonw.exe");
			string python = Path.Combine(payloadDir, "venv", "Scripts", "python.exe");
			if (!File.Exists(pythonw))
				throw new FileNotFoundException("Wizard pythonw not found under " + payloadDir);
			if (!File.Exists(python))
				throw new FileNotFoundException("Wizard python not found under " + payloadDir);

			Environment.SetEnvironmentVariable("SRXY_INSTALLER_PAYLOAD", payloadDir);
			Environment.SetEnvironmentVariable("PYTHONNOUSERSITE", "1");

			ProcessStartInfo psi = new ProcessStartInfo();
			psi.FileName = headless ? python : pythonw;
			psi.Arguments = "-m srxy.adapters.inbound.installer" + FormatArgs(args);
			psi.WorkingDirectory = payloadDir;
			psi.UseShellExecute = false;
			psi.CreateNoWindow = true;
			Process child = Process.Start(psi);
			if (child == null)
				throw new InvalidOperationException("Failed to start installer process.");
			if (!headless)
				return 0;
			child.WaitForExit();
			return child.ExitCode;
		}
		catch (Exception ex)
		{
			try
			{
				string log = Path.Combine(Path.GetTempPath(), "srxy-installer-sfx-error.log");
				File.WriteAllText(log, DateTime.Now.ToString("o") + "\r\n" + ex.ToString() + "\r\n");
			}
			catch
			{
				// ignore log failures
			}
			// Never MessageBox on headless/CI — that hangs waiting for a click.
			if (!headless)
			{
				try
				{
					MessageBox.Show(
						ex.Message,
						"srxy Installer",
						MessageBoxButtons.OK,
						MessageBoxIcon.Error);
				}
				catch
				{
					// ignore UI failures
				}
			}
			return 1;
		}
	}

	private static string EnsurePayload(string exePath, bool headless)
	{
		EmbeddedPayload meta = ReadTrailer(exePath);
		// Keep the cache path short: deep PySide qml trees blow MAX_PATH when the
		// prefix includes a full sha256 + staging GUID (dist\payload\ was shorter).
		string localApp = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
		if (string.IsNullOrEmpty(localApp))
			localApp = Path.GetTempPath();
		string cacheRoot = Path.Combine(localApp, "srxy", "is", meta.ShaHex.Substring(0, 16));
		string payloadDir = Path.Combine(cacheRoot, "p");
		string readyMarker = Path.Combine(cacheRoot, ".ready");
		string pythonw = Path.Combine(payloadDir, "venv", "Scripts", "pythonw.exe");

		if (File.Exists(readyMarker) && File.Exists(pythonw))
			return payloadDir;

		Directory.CreateDirectory(cacheRoot);
		using (Mutex mutex = new Mutex(false, @"Local\srxy-is-" + meta.ShaHex.Substring(0, 16)))
		{
			bool owned = false;
			try
			{
				try
				{
					owned = mutex.WaitOne(TimeSpan.FromMinutes(30));
				}
				catch (AbandonedMutexException)
				{
					owned = true;
				}
				if (!owned)
					throw new TimeoutException("Timed out waiting for another installer extract.");

				if (File.Exists(readyMarker) && File.Exists(pythonw))
					return payloadDir;

				ExtractPayload(exePath, meta, cacheRoot, payloadDir, readyMarker, headless);
				return payloadDir;
			}
			finally
			{
				if (owned)
					mutex.ReleaseMutex();
			}
		}
	}

	private static void ExtractPayload(
		string exePath,
		EmbeddedPayload meta,
		string cacheRoot,
		string payloadDir,
		string readyMarker,
		bool headless)
	{
		// One-letter staging dir keeps deep Qt paths under MAX_PATH when possible.
		// Do not use \\?\ prefixes here: .NET Framework 4.x Directory/File APIs treat
		// '?' as illegal and throw ArgumentException before Win32 long-path handling.
		string stagingPayload = Path.Combine(cacheRoot, "t");
		if (Directory.Exists(stagingPayload))
			Directory.Delete(stagingPayload, true);
		Directory.CreateDirectory(stagingPayload);

		ExtractForm form = null;
		try
		{
			if (!headless)
			{
				form = new ExtractForm();
				form.Show();
				Application.DoEvents();
			}

			using (FileStream exe = new FileStream(exePath, FileMode.Open, FileAccess.Read, FileShare.Read))
			using (SliceStream slice = new SliceStream(exe, meta.ZipOffset, meta.ZipLength))
			using (ZipArchive archive = new ZipArchive(slice, ZipArchiveMode.Read, true))
			{
				int total = Math.Max(1, archive.Entries.Count);
				int done = 0;
				foreach (ZipArchiveEntry entry in archive.Entries)
				{
					string name = entry.FullName.Replace('/', Path.DirectorySeparatorChar);
					if (string.IsNullOrEmpty(name))
					{
						done++;
						continue;
					}
					// Zip-slip / absolute-entry guard.
					string dest = Path.GetFullPath(Path.Combine(stagingPayload, name));
					string stagingRoot = Path.GetFullPath(stagingPayload).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar)
						+ Path.DirectorySeparatorChar;
					if (!dest.StartsWith(stagingRoot, StringComparison.OrdinalIgnoreCase)
						&& !string.Equals(dest, Path.GetFullPath(stagingPayload), StringComparison.OrdinalIgnoreCase))
						throw new InvalidOperationException("Refusing zip entry outside payload root: " + entry.FullName);
					if (name.EndsWith(Path.DirectorySeparatorChar.ToString()) || string.IsNullOrEmpty(entry.Name))
					{
						Directory.CreateDirectory(dest);
					}
					else
					{
						string parent = Path.GetDirectoryName(dest);
						if (!string.IsNullOrEmpty(parent))
							Directory.CreateDirectory(parent);
						entry.ExtractToFile(dest, true);
					}
					done++;
					if (form != null)
					{
						form.SetProgress(done, total);
						Application.DoEvents();
					}
				}
			}

			byte[] actual;
			using (FileStream exe = new FileStream(exePath, FileMode.Open, FileAccess.Read, FileShare.Read))
			using (SHA256 sha256 = SHA256.Create())
			{
				exe.Seek(meta.ZipOffset, SeekOrigin.Begin);
				byte[] buf = new byte[1024 * 1024];
				long remaining = meta.ZipLength;
				while (remaining > 0)
				{
					int toRead = (int)Math.Min(buf.Length, remaining);
					int n = exe.Read(buf, 0, toRead);
					if (n <= 0)
						throw new EndOfStreamException("Unexpected EOF while hashing embedded payload.");
					sha256.TransformBlock(buf, 0, n, null, 0);
					remaining -= n;
				}
				sha256.TransformFinalBlock(new byte[0], 0, 0);
				actual = sha256.Hash;
			}
			if (!BytesEqual(actual, meta.ShaBytes))
				throw new InvalidOperationException("Installer embedded payload checksum mismatch (corrupt download?).");

			string pythonw = Path.Combine(stagingPayload, "venv", "Scripts", "pythonw.exe");
			if (!File.Exists(pythonw))
				throw new FileNotFoundException("Extracted payload is missing venv\\Scripts\\pythonw.exe");

			if (Directory.Exists(payloadDir))
				Directory.Delete(payloadDir, true);
			Directory.Move(stagingPayload, payloadDir);
			File.WriteAllText(readyMarker, meta.ShaHex + "\n", Encoding.ASCII);
		}
		finally
		{
			if (form != null)
			{
				form.Close();
				form.Dispose();
			}
			try
			{
				if (Directory.Exists(stagingPayload))
					Directory.Delete(stagingPayload, true);
			}
			catch
			{
				// best-effort cleanup
			}
		}
	}

	private static EmbeddedPayload ReadTrailer(string exePath)
	{
		using (FileStream fs = new FileStream(exePath, FileMode.Open, FileAccess.Read, FileShare.Read))
		{
			if (fs.Length < TrailerSize + 1)
				throw new InvalidOperationException("Installer executable has no embedded payload.");

			fs.Seek(-TrailerSize, SeekOrigin.End);
			byte[] trailer = new byte[TrailerSize];
			ReadExact(fs, trailer, 0, trailer.Length);

			byte[] sha = new byte[32];
			Buffer.BlockCopy(trailer, 0, sha, 0, 32);
			ulong zipLength = BitConverter.ToUInt64(trailer, 32);
			string magic = Encoding.ASCII.GetString(trailer, 40, 8);
			if (magic != Magic)
				throw new InvalidOperationException("Installer executable is not a self-extracting srxy payload (bad magic).");
			if (zipLength == 0 || (long)zipLength > fs.Length - TrailerSize)
				throw new InvalidOperationException("Installer embedded payload length is invalid.");

			long zipOffset = fs.Length - TrailerSize - (long)zipLength;
			if (zipOffset < 0)
				throw new InvalidOperationException("Installer embedded payload offset is invalid.");

			return new EmbeddedPayload(zipOffset, (long)zipLength, sha);
		}
	}

	private static void ReadExact(Stream stream, byte[] buffer, int offset, int count)
	{
		int read = 0;
		while (read < count)
		{
			int n = stream.Read(buffer, offset + read, count - read);
			if (n <= 0)
				throw new EndOfStreamException("Unexpected EOF reading installer trailer.");
			read += n;
		}
	}

	private static bool BytesEqual(byte[] a, byte[] b)
	{
		if (a == null || b == null || a.Length != b.Length)
			return false;
		for (int i = 0; i < a.Length; i++)
		{
			if (a[i] != b[i])
				return false;
		}
		return true;
	}

	private static string ToHex(byte[] bytes)
	{
		StringBuilder sb = new StringBuilder(bytes.Length * 2);
		for (int i = 0; i < bytes.Length; i++)
			sb.Append(bytes[i].ToString("x2"));
		return sb.ToString();
	}

	private static string FormatArgs(string[] args)
	{
		if (args == null || args.Length == 0)
			return "";
		StringBuilder sb = new StringBuilder();
		foreach (string arg in args)
		{
			sb.Append(' ');
			if (arg.IndexOfAny(new char[] { ' ', '"', '\t' }) >= 0)
				sb.Append('"').Append(arg.Replace("\"", "\\\"")).Append('"');
			else
				sb.Append(arg);
		}
		return sb.ToString();
	}

	private sealed class EmbeddedPayload
	{
		public readonly long ZipOffset;
		public readonly long ZipLength;
		public readonly byte[] ShaBytes;
		public readonly string ShaHex;

		public EmbeddedPayload(long zipOffset, long zipLength, byte[] shaBytes)
		{
			ZipOffset = zipOffset;
			ZipLength = zipLength;
			ShaBytes = shaBytes;
			ShaHex = ToHex(shaBytes);
		}
	}

	private sealed class SliceStream : Stream
	{
		private readonly Stream _inner;
		private readonly long _start;
		private readonly long _length;
		private long _position;

		public SliceStream(Stream inner, long start, long length)
		{
			_inner = inner;
			_start = start;
			_length = length;
			_position = 0;
			_inner.Seek(_start, SeekOrigin.Begin);
		}

		public override bool CanRead { get { return true; } }
		public override bool CanSeek { get { return true; } }
		public override bool CanWrite { get { return false; } }
		public override long Length { get { return _length; } }

		public override long Position
		{
			get { return _position; }
			set { Seek(value, SeekOrigin.Begin); }
		}

		public override void Flush() { }

		public override int Read(byte[] buffer, int offset, int count)
		{
			if (_position >= _length)
				return 0;
			long remaining = _length - _position;
			if (count > remaining)
				count = (int)remaining;
			int n = _inner.Read(buffer, offset, count);
			_position += n;
			return n;
		}

		public override long Seek(long offset, SeekOrigin origin)
		{
			long target;
			switch (origin)
			{
				case SeekOrigin.Begin:
					target = offset;
					break;
				case SeekOrigin.Current:
					target = _position + offset;
					break;
				case SeekOrigin.End:
					target = _length + offset;
					break;
				default:
					throw new ArgumentOutOfRangeException("origin");
			}
			if (target < 0 || target > _length)
				throw new IOException("Seek out of range for embedded payload slice.");
			_inner.Seek(_start + target, SeekOrigin.Begin);
			_position = target;
			return _position;
		}

		public override void SetLength(long value)
		{
			throw new NotSupportedException();
		}

		public override void Write(byte[] buffer, int offset, int count)
		{
			throw new NotSupportedException();
		}
	}

	private sealed class ExtractForm : Form
	{
		private readonly ProgressBar _bar;
		private readonly Label _label;

		public ExtractForm()
		{
			Text = "srxy Installer";
			FormBorderStyle = FormBorderStyle.FixedDialog;
			MaximizeBox = false;
			MinimizeBox = false;
			StartPosition = FormStartPosition.CenterScreen;
			ClientSize = new Size(420, 88);
			ShowInTaskbar = true;

			_label = new Label();
			_label.AutoSize = false;
			_label.TextAlign = ContentAlignment.MiddleLeft;
			_label.Location = new Point(12, 12);
			_label.Size = new Size(396, 20);
			_label.Text = "Preparing installer…";

			_bar = new ProgressBar();
			_bar.Location = new Point(12, 44);
			_bar.Size = new Size(396, 24);
			_bar.Minimum = 0;
			_bar.Maximum = 100;
			_bar.Style = ProgressBarStyle.Continuous;

			Controls.Add(_label);
			Controls.Add(_bar);
		}

		public void SetProgress(int done, int total)
		{
			int pct = (int)((done * 100L) / Math.Max(1, total));
			if (pct < 0) pct = 0;
			if (pct > 100) pct = 100;
			_bar.Value = pct;
			_label.Text = "Extracting installer files… " + pct + "%";
		}
	}
}
