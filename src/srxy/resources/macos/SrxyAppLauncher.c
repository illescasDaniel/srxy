/* Srxy.app CFBundleExecutable — must be Mach-O (macOS rejects shell scripts).
 *
 * Compiled at install time with absolute paths baked in. Execs the in-bundle
 * Python (SrxyPython) with -m srxy so NSBundle.mainBundle stays Srxy.app.
 *
 * PYTHONHOME must point at the real CPython prefix: copying/linking the
 * interpreter into the .app changes argv[0], and without PYTHONHOME it looks
 * for stdlib under /install and fails to start.
 */
#include <limits.h>
#include <mach-o/dyld.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#ifndef SRXY_HOME_PATH
#error "SRXY_HOME_PATH must be defined at compile time"
#endif
#ifndef SRXY_PYTHONHOME
#error "SRXY_PYTHONHOME must be defined at compile time"
#endif
#ifndef SRXY_SITE_PACKAGES
#error "SRXY_SITE_PACKAGES must be defined at compile time"
#endif
#ifndef SRXY_PATH_PREFIX
#error "SRXY_PATH_PREFIX must be defined at compile time"
#endif
#ifndef SRXY_TESSDATA
#error "SRXY_TESSDATA must be defined at compile time"
#endif
#ifndef SRXY_LOG_FILE
#error "SRXY_LOG_FILE must be defined at compile time"
#endif

static void append_log(const char *line)
{
	FILE *fp = fopen(SRXY_LOG_FILE, "a");
	if (fp == NULL)
		return;
	fputs(line, fp);
	fputc('\n', fp);
	fclose(fp);
}

int main(int argc, char **argv)
{
	char exe[PATH_MAX];
	char resolved[PATH_MAX];
	char python[PATH_MAX];
	char path_env[PATH_MAX * 2];
	char *new_argv[64];
	uint32_t size = sizeof(exe);
	int i;

	if (_NSGetExecutablePath(exe, &size) != 0)
		return 127;
	if (realpath(exe, resolved) == NULL) {
		strncpy(resolved, exe, sizeof(resolved) - 1);
		resolved[sizeof(resolved) - 1] = '\0';
	}

	/* Strip /srxy → Contents/MacOS */
	{
		char *slash = strrchr(resolved, '/');
		if (slash != NULL)
			*slash = '\0';
	}
	snprintf(python, sizeof(python), "%s/SrxyPython", resolved);

	setenv("SRXY_HOME", SRXY_HOME_PATH, 1);
	setenv("VIRTUAL_ENV", SRXY_HOME_PATH "/.venv", 1);
	setenv("PYTHONHOME", SRXY_PYTHONHOME, 1);
	setenv("PYTHONPATH", SRXY_SITE_PACKAGES, 1);
	setenv("TESSDATA_PREFIX", SRXY_TESSDATA, 1);
	setenv("QT_QUICK_CONTROLS_STYLE", "macOS", 0);

	snprintf(path_env, sizeof(path_env), "%s:%s", SRXY_PATH_PREFIX,
		 getenv("PATH") ? getenv("PATH") : "");
	setenv("PATH", path_env, 1);

	append_log("===== srxy.app Mach-O launch =====");

	if (argc + 3 >= (int)(sizeof(new_argv) / sizeof(new_argv[0])))
		return 126;
	new_argv[0] = python;
	new_argv[1] = "-m";
	new_argv[2] = "srxy";
	for (i = 1; i < argc; i++)
		new_argv[i + 2] = argv[i];
	new_argv[argc + 2] = NULL;

	execv(python, new_argv);
	perror("execv SrxyPython");
	return 127;
}
