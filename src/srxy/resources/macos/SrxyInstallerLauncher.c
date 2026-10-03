/* Offline installer CFBundleExecutable — must be Mach-O.
 *
 * LaunchServices rejects shell scripts as CFBundleExecutable
 * (kLSNoExecutableErr / Finder "(null)"). Paths are resolved from this
 * binary's location so the .app stays relocatable (no baked absolute paths).
 *
 * Layout assumed:
 *   Contents/MacOS/srxy-installer-offline  (this file)
 *   Contents/Resources/venv/bin/python
 */
#include <limits.h>
#include <mach-o/dyld.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int main(int argc, char **argv)
{
	char exe[PATH_MAX];
	char resolved[PATH_MAX];
	char contents[PATH_MAX];
	char python[PATH_MAX];
	char *new_argv[64];
	uint32_t size = sizeof(exe);
	int i;

	if (_NSGetExecutablePath(exe, &size) != 0)
		return 127;
	if (realpath(exe, resolved) == NULL) {
		strncpy(resolved, exe, sizeof(resolved) - 1);
		resolved[sizeof(resolved) - 1] = '\0';
	}

	/* …/Contents/MacOS/<exe> → strip basename, then MacOS → Contents */
	{
		char *slash = strrchr(resolved, '/');
		if (slash != NULL)
			*slash = '\0';
		slash = strrchr(resolved, '/');
		if (slash != NULL)
			*slash = '\0';
	}
	strncpy(contents, resolved, sizeof(contents) - 1);
	contents[sizeof(contents) - 1] = '\0';

	snprintf(python, sizeof(python), "%s/Resources/venv/bin/python", contents);

	setenv("APPDIR", contents, 1);
	setenv("PYTHONNOUSERSITE", "1", 1);
	setenv("QT_QUICK_CONTROLS_STYLE", "macOS", 0);

	if (argc + 3 >= (int)(sizeof(new_argv) / sizeof(new_argv[0])))
		return 126;
	new_argv[0] = python;
	new_argv[1] = "-m";
	new_argv[2] = "srxy.adapters.inbound.installer";
	for (i = 1; i < argc; i++)
		new_argv[i + 2] = argv[i];
	new_argv[argc + 2] = NULL;

	execv(python, new_argv);
	perror("execv installer python");
	return 127;
}
