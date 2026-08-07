// Minimal GUI launcher for the installed srxy prefix.
// Compiled at install/build time with:
//   csc /target:winexe /win32icon:srxy.ico /r:System.Windows.Forms.dll /out:Srxy.exe SrxyLauncher.cs
// Resolves SRXY_HOME from this executable's directory (…\bin\Srxy.exe → prefix).
using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Text;
using System.Windows.Forms;

internal static class Program
{
	[STAThread]
	private static int Main(string[] args)
	{
		try
		{
			string exe = Assembly.GetExecutingAssembly().Location;
			if (string.IsNullOrEmpty(exe))
				exe = Process.GetCurrentProcess().MainModule.FileName;
			string binDir = Path.GetDirectoryName(exe);
			if (string.IsNullOrEmpty(binDir))
				throw new InvalidOperationException("Could not resolve launcher directory.");
			string prefix = Path.GetFullPath(Path.Combine(binDir, ".."));
			string venvScripts = Path.Combine(prefix, ".venv", "Scripts");
			string pythonw = Path.Combine(venvScripts, "pythonw.exe");
			string srxyExe = Path.Combine(venvScripts, "srxy.exe");
			string logDir = Path.Combine(prefix, "logs");
			Directory.CreateDirectory(logDir);

			Environment.SetEnvironmentVariable("SRXY_HOME", prefix);
			string pathExtra = string.Join(";", new string[] {
				Path.Combine(prefix, "vendor", "tesseract", "bin"),
				Path.Combine(prefix, "vendor", "ffmpeg", "bin"),
				Path.Combine(prefix, "vendor", "uv"),
			});
			string path = Environment.GetEnvironmentVariable("PATH") ?? "";
			Environment.SetEnvironmentVariable("PATH", pathExtra + ";" + path);

			string tessDist = Path.Combine(prefix, "vendor", "tesseract", "dist", "tessdata");
			string tessData = Path.Combine(prefix, "vendor", "tesseract", "tessdata");
			Environment.SetEnvironmentVariable(
				"TESSDATA_PREFIX",
				Directory.Exists(tessDist) ? tessDist : tessData);

			string fileName;
			string arguments;
			if (File.Exists(pythonw))
			{
				fileName = pythonw;
				arguments = "-m srxy" + FormatArgs(args);
			}
			else if (File.Exists(srxyExe))
			{
				fileName = srxyExe;
				arguments = FormatArgs(args).TrimStart();
			}
			else
			{
				throw new FileNotFoundException(
					"Neither pythonw.exe nor srxy.exe found under " + venvScripts);
			}

			AppendLog(Path.Combine(logDir, "srxy.log"),
				"===== " + DateTime.Now.ToString("o") + " srxy start =====" + Environment.NewLine
				+ "SRXY_HOME=" + prefix + Environment.NewLine);

			ProcessStartInfo psi = new ProcessStartInfo();
			psi.FileName = fileName;
			psi.Arguments = arguments;
			psi.WorkingDirectory = prefix;
			psi.UseShellExecute = false;
			psi.CreateNoWindow = true;
			Process.Start(psi);
			return 0;
		}
		catch (Exception ex)
		{
			try
			{
				MessageBox.Show(
					ex.Message,
					"srxy",
					MessageBoxButtons.OK,
					MessageBoxIcon.Error);
			}
			catch
			{
				// ignore UI failures
			}
			return 1;
		}
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

	private static void AppendLog(string path, string text)
	{
		try
		{
			File.AppendAllText(path, text, Encoding.UTF8);
		}
		catch
		{
			// ignore logging failures
		}
	}
}
