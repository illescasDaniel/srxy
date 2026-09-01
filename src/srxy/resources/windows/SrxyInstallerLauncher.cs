// Minimal GUI launcher for the Windows PySide offline installer wrapper.
// Compiled at build time with:
//   csc /target:winexe /win32icon:srxy-installer.ico /r:System.Windows.Forms.dll /out:SrxyInstaller.exe SrxyInstallerLauncher.cs
// Resolves the payload root from this executable's own directory (the payload
// root ships the launcher next to python\, venv\, and share\), sets
// SRXY_INSTALLER_PAYLOAD so the shared installer engine finds the bundled
// wheel / installer_meta.toml / prebuilt app launcher (see
// srxy.adapters.inbound.installer.package_spec / meta / install), then execs
// the wizard-only venv's pythonw.exe with the installer package.
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
			string payloadDir = Path.GetDirectoryName(exe);
			if (string.IsNullOrEmpty(payloadDir))
				throw new InvalidOperationException("Could not resolve launcher directory.");

			string pythonw = Path.Combine(payloadDir, "venv", "Scripts", "pythonw.exe");
			if (!File.Exists(pythonw))
				throw new FileNotFoundException("Wizard python not found under " + payloadDir + "\\venv\\Scripts");

			Environment.SetEnvironmentVariable("SRXY_INSTALLER_PAYLOAD", payloadDir);
			Environment.SetEnvironmentVariable("PYTHONNOUSERSITE", "1");

			ProcessStartInfo psi = new ProcessStartInfo();
			psi.FileName = pythonw;
			psi.Arguments = "-m srxy.adapters.inbound.installer" + FormatArgs(args);
			psi.WorkingDirectory = payloadDir;
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
					"srxy Installer",
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
}
