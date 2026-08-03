package main

import (
	"crypto/rand"
	"encoding/base64"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"time"

	"github.com/illescasDaniel/srxy/packaging/online-bootstrap/internal/bootserver"
	appruntime "github.com/illescasDaniel/srxy/packaging/online-bootstrap/internal/runtime"
)

// Set via -ldflags at build time.
var (
	version = "dev"
)

func main() {
	os.Exit(run(os.Args[1:]))
}

func run(args []string) int {
	fs := flag.NewFlagSet("srxy-installer-online", flag.ContinueOnError)
	fs.SetOutput(os.Stderr)
	showHelp := fs.Bool("help", false, "Show help")
	showVersion := fs.Bool("version", false, "Print version")
	appDirFlag := fs.String("app-dir", "", "AppDir root (default: detect from executable)")
	if err := fs.Parse(args); err != nil {
		return 2
	}
	if *showHelp {
		fmt.Fprintf(os.Stderr, "srxy online installer bootstrap\n\n")
		fs.PrintDefaults()
		return 0
	}
	if *showVersion {
		fmt.Println(version)
		return 0
	}

	appDir, err := resolveAppDir(*appDirFlag)
	if err != nil {
		fmt.Fprintf(os.Stderr, "srxy-installer-online: %v\n", err)
		return 1
	}
	metaPath := filepath.Join(appDir, "usr", "share", "srxy", "bootstrap-meta.json")
	meta, err := appruntime.LoadMeta(metaPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "srxy-installer-online: %v\n", err)
		return 1
	}
	if meta.SrxyVersion != "" {
		version = meta.SrxyVersion
	}

	cacheDir, err := appruntime.DefaultCacheDir()
	if err != nil {
		fmt.Fprintf(os.Stderr, "srxy-installer-online: %v\n", err)
		return 1
	}
	if err := os.MkdirAll(cacheDir, 0o755); err != nil {
		fmt.Fprintf(os.Stderr, "srxy-installer-online: %v\n", err)
		return 1
	}
	paths := appruntime.ResolvePaths(appDir, cacheDir, meta)

	token, err := randomToken()
	if err != nil {
		fmt.Fprintf(os.Stderr, "srxy-installer-online: %v\n", err)
		return 1
	}
	state := bootserver.NewState(token)
	server, bootURL, err := bootserver.Start(state, staticFS())
	if err != nil {
		fmt.Fprintf(os.Stderr, "srxy-installer-online: %v\n", err)
		return 1
	}
	defer server.Shutdown()

	go state.WatchClient(3*time.Second, 20*time.Second)

	if err := bootserver.OpenBrowser(bootURL); err != nil {
		fmt.Fprintf(os.Stderr, "Could not open a browser automatically (%v).\nOpen this URL manually:\n  %s\n", err, bootURL)
	} else {
		fmt.Fprintf(os.Stderr, "Opened bootstrap UI:\n  %s\n", bootURL)
	}

	done := make(chan error, 1)
	go func() {
		done <- appruntime.EnsureRuntime(state, paths, meta)
	}()

	select {
	case <-state.Stopped():
		fmt.Fprintln(os.Stderr, "Bootstrap cancelled.")
		return 0
	case err := <-done:
		if err != nil {
			state.SetError(err.Error())
			fmt.Fprintf(os.Stderr, "srxy-installer-online: %v\n", err)
			// Keep boot UI up briefly so the user can read the error, then idle-exit.
			select {
			case <-state.Stopped():
			case <-time.After(30 * time.Second):
				state.Stop()
			}
			return 1
		}
	}

	cmd, installerURL, err := appruntime.LaunchInstaller(paths)
	if err != nil {
		state.SetError(err.Error())
		fmt.Fprintf(os.Stderr, "srxy-installer-online: %v\n", err)
		select {
		case <-state.Stopped():
		case <-time.After(30 * time.Second):
			state.Stop()
		}
		return 1
	}
	state.SetRedirect(installerURL)

	err = cmd.Wait()
	state.Stop()
	if err != nil {
		fmt.Fprintf(os.Stderr, "srxy-installer-online: installer exited: %v\n", err)
		return 1
	}
	return 0
}

func resolveAppDir(explicit string) (string, error) {
	if explicit != "" {
		return filepath.Clean(explicit), nil
	}
	if here := os.Getenv("APPDIR"); here != "" {
		return here, nil
	}
	exe, err := os.Executable()
	if err != nil {
		return "", err
	}
	// AppImage layout: $APPDIR/usr/bin/srxy-online-bootstrap
	binDir := filepath.Dir(exe)
	usrDir := filepath.Dir(binDir)
	appDir := filepath.Dir(usrDir)
	meta := filepath.Join(appDir, "usr", "share", "srxy", "bootstrap-meta.json")
	if _, err := os.Stat(meta); err == nil {
		return appDir, nil
	}
	// Dev fallback: packaging/online-bootstrap with meta beside binary.
	cwd, _ := os.Getwd()
	for _, cand := range []string{cwd, filepath.Dir(exe)} {
		meta = filepath.Join(cand, "bootstrap-meta.json")
		if _, err := os.Stat(meta); err == nil {
			return cand, nil
		}
	}
	return "", fmt.Errorf("could not locate AppDir / bootstrap-meta.json (set --app-dir or APPDIR)")
}

func randomToken() (string, error) {
	b := make([]byte, 18)
	if _, err := rand.Read(b); err != nil {
		return "", err
	}
	return base64.RawURLEncoding.EncodeToString(b), nil
}
