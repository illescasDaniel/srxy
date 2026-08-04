package runtime

import (
	"os"
	"path/filepath"
	"testing"
)

func TestSpecFromVersion(t *testing.T) {
	cases := []struct {
		in   string
		want string
	}{
		{"1.6.0", "srxy>=1.6.0,<2"},
		{"2.1.0", "srxy>=2.1.0,<3"},
		{"v1.6.0", "srxy>=1.6.0,<2"},
		{"1.6.0+local", "srxy>=1.6.0,<2"},
		{"1.6.0-rc.1", "srxy>=1.6.0-rc.1,<2"},
	}
	for _, tc := range cases {
		got, err := SpecFromVersion(tc.in)
		if err != nil {
			t.Fatalf("SpecFromVersion(%q): %v", tc.in, err)
		}
		if got != tc.want {
			t.Fatalf("SpecFromVersion(%q)=%q want %q", tc.in, got, tc.want)
		}
	}
}

func TestSpecFromVersion_Empty(t *testing.T) {
	if _, err := SpecFromVersion(""); err == nil {
		t.Fatal("expected error")
	}
}

func TestBootstrapInstallSpec_Override(t *testing.T) {
	t.Setenv("SRXY_ONLINE_BOOTSTRAP_SPEC", "srxy @ /tmp/foo.whl")
	got, err := BootstrapInstallSpec(Meta{SrxyVersion: "1.6.0"})
	if err != nil {
		t.Fatal(err)
	}
	if got != "srxy @ /tmp/foo.whl" {
		t.Fatalf("got %q", got)
	}
}

func TestLoadMeta_Valid(t *testing.T) {
	dir := t.TempDir()
	path := dir + "/bootstrap-meta.json"
	raw := `{
  "uv_url": "https://example.com/uv.tar.gz",
  "uv_sha256": "abc",
  "python_version": "3.12",
  "installer_version": "3",
  "srxy_version": "1.6.0"
}
`
	if err := os.WriteFile(path, []byte(raw), 0o644); err != nil {
		t.Fatal(err)
	}
	meta, err := LoadMeta(path)
	if err != nil {
		t.Fatal(err)
	}
	if meta.PythonVersion != "3.12" || meta.SrxyVersion != "1.6.0" {
		t.Fatalf("unexpected meta: %+v", meta)
	}
}

func TestLoadMeta_Incomplete(t *testing.T) {
	dir := t.TempDir()
	path := dir + "/bootstrap-meta.json"
	if err := os.WriteFile(path, []byte(`{"uv_url":"https://x"}`), 0o644); err != nil {
		t.Fatal(err)
	}
	if _, err := LoadMeta(path); err == nil {
		t.Fatal("expected incomplete meta error")
	}
}

func TestDefaultCacheDir_Override(t *testing.T) {
	want := t.TempDir()
	t.Setenv("SRXY_ONLINE_BOOTSTRAP_CACHE", want)
	got, err := DefaultCacheDir()
	if err != nil {
		t.Fatal(err)
	}
	if got != want {
		t.Fatalf("got %q want %q", got, want)
	}
}

func TestResolvePaths_Layout(t *testing.T) {
	app := t.TempDir()
	cache := t.TempDir()
	paths := ResolvePaths(app, cache, Meta{})
	if paths.UvBin != filepath.Join(cache, "uv", "uv") {
		t.Fatalf("UvBin=%q", paths.UvBin)
	}
	if paths.VenvPython != filepath.Join(cache, "venv", "bin", "python") {
		t.Fatalf("VenvPython=%q", paths.VenvPython)
	}
	if paths.MetaPath != filepath.Join(app, "usr", "share", "srxy", "bootstrap-meta.json") {
		t.Fatalf("MetaPath=%q", paths.MetaPath)
	}
	if paths.AppDir != app {
		t.Fatalf("AppDir=%q want %q", paths.AppDir, app)
	}
}
