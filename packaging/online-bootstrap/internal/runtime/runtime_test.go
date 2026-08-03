package runtime

import "testing"

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
