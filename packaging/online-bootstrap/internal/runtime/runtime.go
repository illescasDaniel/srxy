package runtime

import (
	"archive/tar"
	"compress/gzip"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	"github.com/illescasDaniel/srxy/packaging/online-bootstrap/internal/bootserver"
	"github.com/illescasDaniel/srxy/packaging/online-bootstrap/internal/fetch"
)

// Meta is written next to the AppImage payload at build time.
type Meta struct {
	UvURL         string `json:"uv_url"`
	UvSHA256      string `json:"uv_sha256"`
	PythonVersion string `json:"python_version"`
	InstallerVer  string `json:"installer_version"`
	SrxyVersion   string `json:"srxy_version"`
}

type Paths struct {
	CacheDir   string
	UvBin      string
	VenvDir    string
	VenvPython string
	URLFile    string
	MetaPath   string
}

func DefaultCacheDir() (string, error) {
	if v := os.Getenv("SRXY_ONLINE_BOOTSTRAP_CACHE"); v != "" {
		return v, nil
	}
	base := os.Getenv("XDG_CACHE_HOME")
	if base == "" {
		home, err := os.UserHomeDir()
		if err != nil {
			return "", err
		}
		base = filepath.Join(home, ".cache")
	}
	return filepath.Join(base, "srxy", "online-bootstrap"), nil
}

func LoadMeta(path string) (Meta, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return Meta{}, err
	}
	var m Meta
	if err := json.Unmarshal(raw, &m); err != nil {
		return Meta{}, err
	}
	if m.UvURL == "" || m.PythonVersion == "" || m.SrxyVersion == "" {
		return Meta{}, fmt.Errorf("incomplete bootstrap meta at %s", path)
	}
	return m, nil
}

func ResolvePaths(appDir, cacheDir string, meta Meta) Paths {
	_ = meta
	return Paths{
		CacheDir:   cacheDir,
		UvBin:      filepath.Join(cacheDir, "uv", "uv"),
		VenvDir:    filepath.Join(cacheDir, "venv"),
		VenvPython: filepath.Join(cacheDir, "venv", "bin", "python"),
		URLFile:    filepath.Join(cacheDir, "installer.url"),
		MetaPath:   filepath.Join(appDir, "usr", "share", "srxy", "bootstrap-meta.json"),
	}
}

// SpecFromVersion builds srxy>=floor,<next_major from a semver-like version string.
func SpecFromVersion(version string) (string, error) {
	v := strings.TrimSpace(version)
	v = strings.TrimPrefix(v, "v")
	if v == "" {
		return "", fmt.Errorf("empty srxy version")
	}
	floor := v
	if i := strings.Index(floor, "+"); i >= 0 {
		floor = floor[:i]
	}
	majorPart := floor
	if i := strings.Index(majorPart, "-"); i >= 0 {
		majorPart = majorPart[:i]
	}
	parts := strings.Split(majorPart, ".")
	if len(parts) < 1 || parts[0] == "" {
		return "", fmt.Errorf("invalid srxy version %q", version)
	}
	major, err := strconv.Atoi(parts[0])
	if err != nil || major < 0 {
		return "", fmt.Errorf("invalid major in srxy version %q", version)
	}
	return fmt.Sprintf("srxy>=%s,<%d", floor, major+1), nil
}

// BootstrapInstallSpec returns the uv pip requirement for the installer package.
func BootstrapInstallSpec(meta Meta) (string, error) {
	if override := strings.TrimSpace(os.Getenv("SRXY_ONLINE_BOOTSTRAP_SPEC")); override != "" {
		return override, nil
	}
	return SpecFromVersion(meta.SrxyVersion)
}

// EnsureRuntime downloads uv, installs Python, creates venv, installs srxy from PyPI.
func EnsureRuntime(state *bootserver.State, paths Paths, meta Meta) error {
	state.SetStatus("uv", "Downloading uv…", 0.05)
	if err := ensureUv(state, paths, meta); err != nil {
		return err
	}
	state.SetStatus("python", "Installing Python…", 0.35)
	if err := ensurePython(state, paths, meta); err != nil {
		return err
	}
	state.SetStatus("venv", "Preparing installer environment…", 0.55)
	if err := ensureVenv(state, paths, meta); err != nil {
		return err
	}
	state.SetStatus("srxy", "Downloading srxy installer…", 0.7)
	if err := ensureSrxy(state, paths, meta); err != nil {
		return err
	}
	state.SetStatus("ready", "Starting installer…", 0.9)
	return nil
}

func ensureUv(state *bootserver.State, paths Paths, meta Meta) error {
	if st, err := os.Stat(paths.UvBin); err == nil && st.Mode().IsRegular() {
		return nil
	}
	archive := filepath.Join(paths.CacheDir, "uv.tar.gz")
	err := fetch.DownloadHTTPS(meta.UvURL, archive, meta.UvSHA256, func(done, total int64) {
		p := 0.05
		if total > 0 {
			p = 0.05 + 0.25*float64(done)/float64(total)
		}
		state.SetStatus("uv", "Downloading uv…", p)
	})
	if err != nil {
		return err
	}
	destDir := filepath.Join(paths.CacheDir, "uv")
	_ = os.RemoveAll(destDir)
	if err := os.MkdirAll(destDir, 0o755); err != nil {
		return err
	}
	if err := extractUvTarGz(archive, destDir); err != nil {
		return err
	}
	if _, err := os.Stat(paths.UvBin); err != nil {
		return fmt.Errorf("uv binary missing after extract: %w", err)
	}
	return os.Chmod(paths.UvBin, 0o755)
}

func extractUvTarGz(archive, destDir string) error {
	f, err := os.Open(archive)
	if err != nil {
		return err
	}
	defer f.Close()
	gz, err := gzip.NewReader(f)
	if err != nil {
		return err
	}
	defer gz.Close()
	tr := tar.NewReader(gz)
	for {
		hdr, err := tr.Next()
		if err == io.EOF {
			break
		}
		if err != nil {
			return err
		}
		base := filepath.Base(hdr.Name)
		if base != "uv" && base != "uvx" {
			continue
		}
		out := filepath.Join(destDir, base)
		if hdr.Typeflag != tar.TypeReg {
			continue
		}
		w, err := os.OpenFile(out, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0o755)
		if err != nil {
			return err
		}
		if _, err := io.Copy(w, tr); err != nil {
			w.Close()
			return err
		}
		w.Close()
	}
	return nil
}

func ensurePython(state *bootserver.State, paths Paths, meta Meta) error {
	_ = state
	cmd := exec.Command(paths.UvBin, "python", "install", meta.PythonVersion, "--install-dir", filepath.Join(paths.CacheDir, "python"))
	cmd.Env = append(os.Environ(), "UV_PYTHON_PREFERENCE=only-managed")
	out, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("uv python install: %w\n%s", err, out)
	}
	return nil
}

func ensureVenv(state *bootserver.State, paths Paths, meta Meta) error {
	_ = state
	pyDir := filepath.Join(paths.CacheDir, "python")
	pythonBin, err := findManagedPython(pyDir, meta.PythonVersion)
	if err != nil {
		return err
	}
	if _, err := os.Stat(paths.VenvPython); err != nil {
		cmd := exec.Command(paths.UvBin, "venv", "--python", pythonBin, "--link-mode", "copy", paths.VenvDir)
		out, err := cmd.CombinedOutput()
		if err != nil {
			return fmt.Errorf("uv venv: %w\n%s", err, out)
		}
	}
	return nil
}

func ensureSrxy(state *bootserver.State, paths Paths, meta Meta) error {
	_ = state
	spec, err := BootstrapInstallSpec(meta)
	if err != nil {
		return err
	}
	cmd := exec.Command(paths.UvBin, "pip", "install", "--python", paths.VenvPython, "--no-deps", spec)
	out, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("uv pip install %s: %w\n%s", spec, err, out)
	}
	return nil
}

func findManagedPython(root, version string) (string, error) {
	var found string
	err := filepath.Walk(root, func(path string, info os.FileInfo, err error) error {
		if err != nil || info.IsDir() {
			return err
		}
		name := info.Name()
		if name == "python"+version || name == "python3" || name == "python" {
			if strings.Contains(path, "bin") {
				found = path
				return io.EOF
			}
		}
		return nil
	})
	if err != nil && err != io.EOF {
		return "", err
	}
	if found == "" {
		return "", fmt.Errorf("managed python %s not found under %s", version, root)
	}
	return found, nil
}

// Child is a running Python installer process.
type Child struct {
	waitErr <-chan error
}

func (c *Child) Wait() error {
	return <-c.waitErr
}

// LaunchInstaller starts the Python online installer and returns its URL.
func LaunchInstaller(paths Paths) (*Child, string, error) {
	_ = os.Remove(paths.URLFile)
	cmd := exec.Command(
		paths.VenvPython,
		"-m", "srxy.adapters.inbound.installer_online",
		"--no-browser",
		"--url-file", paths.URLFile,
	)
	cmd.Stdout = os.Stderr
	cmd.Stderr = os.Stderr
	cmd.Env = append(os.Environ(), "PYTHONNOUSERSITE=1")
	if err := cmd.Start(); err != nil {
		return nil, "", err
	}
	waitErr := make(chan error, 1)
	go func() { waitErr <- cmd.Wait() }()

	deadline := time.Now().Add(60 * time.Second)
	for time.Now().Before(deadline) {
		select {
		case err := <-waitErr:
			if err != nil {
				return nil, "", fmt.Errorf("installer exited before writing URL: %w", err)
			}
			return nil, "", fmt.Errorf("installer exited before writing URL")
		default:
		}
		raw, err := os.ReadFile(paths.URLFile)
		if err == nil {
			u := strings.TrimSpace(string(raw))
			if strings.HasPrefix(u, "http://127.0.0.1:") {
				return &Child{waitErr: waitErr}, u, nil
			}
		}
		time.Sleep(50 * time.Millisecond)
	}
	_ = cmd.Process.Kill()
	<-waitErr
	return nil, "", fmt.Errorf("timeout waiting for installer URL file")
}
